+++
date = '2026-09-28T00:00:00+08:00'
draft = false
title = 'Python 线程池与进程池：任务调度、Future 与实战选择'
+++

当程序需要同时下载许多文件、并行处理一批图片，或把一组独立计算分配给多个 CPU 核时，`threading.Thread` 并不是唯一、也通常不是最省心的入口。标准库 `concurrent.futures` 把“提交任务、取得结果、处理异常、等待关闭”收束为统一模型：`ThreadPoolExecutor` 管理线程，`ProcessPoolExecutor` 管理进程，而 `Future` 代表一个尚未完成或已经完成的任务。

不过，线程池不等于让一切变快，进程池也不等于 CPU 密集任务的万能按钮。选择之前必须知道工作主要在等待 I/O，还是持续执行 Python 计算；还必须把任务数量、外部服务容量、序列化成本、异常与退出路径一起纳入设计。本文以执行器（executor）为中心解释这些边界，并给出可以迁移到普通脚本、批处理程序和服务内部任务的写法。

## 一、先建立模型：线程、进程与池

一个**线程**是进程中的执行流。同一进程的线程共享 Python 对象、文件描述符和大部分进程资源，因此传递对象很方便，但共享可变状态需要同步。

一个**进程**拥有独立的解释器和地址空间。进程能隔离故障，也能在常规 CPython 中利用多个 CPU 核执行纯 Python 计算；代价是参数和结果通常要序列化后跨进程传递。

线程池或进程池会预先维护有限数量的工作者。调用方把任务交给池，空闲工作者取走任务执行。与“每个任务新建一个线程/进程”相比，池避免了反复创建和销毁的成本，也给并发量设下了明确上限。

```text
主线程
  │ submit(task, arg)
  ▼
Executor 的等待队列 ──► 工作线程 / 工作进程 1 ──► 结果或异常
                   ├─► 工作线程 / 工作进程 2 ──► 结果或异常
                   └─► 工作线程 / 工作进程 N ──► 结果或异常
                                      │
                                      ▼
                                   Future
```

这里的 `Future` 不是任务本身，而是任务未来状态的句柄。它可以处于等待、正在运行、成功完成、异常完成或被取消等状态；调用方可在合适的时候读取结果，而不必自己维护线程对象与结果容器。

## 二、GIL 的边界：它影响性能，不替你保证正确性

在常见的 CPython 构建中，GIL 使同一个进程里的线程不能同时执行 Python 字节码。因此，两个线程同时跑很长的纯 Python 循环，通常不能因增加线程而获得接近两倍的 CPU 吞吐。这是纯 Python CPU 任务倾向选择进程池的根本原因。

但这句话有两个必要的限定。

- 线程等待网络、文件、数据库等阻塞 I/O 时，解释器或底层库通常会释放 GIL；其他线程仍可运行。因此线程池很适合并发调用已有的同步 HTTP、文件或数据库 API。
- GIL 不是业务锁。`if` 判断、更新多个对象、写数据库等操作不能因为“有 GIL”就视为一个原子事务。线程之间仍可能在多个语句之间交错，也仍会发生重复提交、丢失更新与状态不一致。

另一个容易忽略的例外是原生扩展。某些数值、压缩、图像或密码学库会在重计算时释放 GIL；此时线程池也可能利用多核。结论不该凭印象决定：查库的并发说明，再用目标数据测量。Python 3.13+ 的自由线程构建也会改变性能表现，但它不会消除共享内存的竞态条件。

## 三、选择执行器：先看等待在哪里

下面的表格只是起点；真正的 `max_workers` 还取决于连接池、远端配额、内存和单个任务大小。

| 工作负载 | 通常优先选择 | 原因 | 首先检查的风险 |
| -------- | ------------ | ---- | -------------- |
| 同步 HTTP、文件、数据库 I/O | `ThreadPoolExecutor` | 等待期间其他线程可以推进 | 超时、连接数、远端限流 |
| 纯 Python 编码、解析、计算 | `ProcessPoolExecutor` | 绕开常规 CPython 的单进程 GIL 限制 | pickle、数据复制、进程开销 |
| 很短且数量很少的任务 | 直接顺序执行 | 调度开销可能超过收益 | 不要为并发而并发 |
| 需要共享复杂可变对象 | 优先重构为队列或单一所有者 | 线程共享状态的协调成本高 | 锁、死锁、错误恢复 |
| 大量异步 I/O | `asyncio` 与异步客户端 | 单线程可高效管理大量等待 | 不能在事件循环中直接阻塞 |

“I/O 密集”是指大部分墙上时间花在等待外部世界；“CPU 密集”是指核心持续忙于计算。一个任务既可能下载数据又可能做昂贵转换，常见做法是分阶段：I/O 阶段使用线程或异步客户端，计算阶段交给进程池。不要把一个包含长时间网络等待的巨大函数塞进进程池，白白承担进程通信成本。

## 四、原生线程与原生进程：何时直接管理生命周期

`Executor` 是高层任务调度工具，不会淘汰 `threading.Thread` 和 `multiprocessing.Process`。后两者让调用方直接持有执行单元，因而能自己定义启动时机、长期运行循环、停止信号和进程间通信协议；相应地，结果传递、异常收集、并发限制与回收都要自己负责。

### 1. `threading.Thread`：一个明确的后台执行流

下面是最小的线程启动与回收示例。`start()` 才会让目标函数在新线程执行，`join()` 等待其结束；省略 `join()` 可能使主程序提前退出，或使后续逻辑在结果尚未准备好时继续执行。

```python
import threading


def write_report(path: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write("报告内容\n")


worker = threading.Thread(
    target=write_report,
    args=("report.txt",),
    name="report-writer",
)
worker.start()
worker.join()
```

当只有一个或少量**长期存在、职责固定**的线程时，直接使用 `Thread` 很自然，例如一个专门从有界队列取任务的消费者线程、一个由 `threading.Event` 协作停止的监控线程。此时生命周期本身就是程序协议的一部分。不要把 `daemon=True` 当作可靠关闭方案：解释器退出时守护线程可能被直接终止，`finally`、文件刷新和网络清理都无法保证完成。

若工作是一批彼此独立、需要返回值或统一处理异常的短任务，优先 `ThreadPoolExecutor`。它避免手写线程列表、结果容器和空闲工作者管理，也能以 `Future` 清楚地交回失败。

### 2. `multiprocessing.Process`：显式的进程与消息通道

进程不共享普通 Python 内存。下面使用 `multiprocessing.Queue` 把子进程的计算结果发回父进程；`get()` 读取消息，`join()` 回收子进程。传给 `Process` 的目标函数同样应位于模块顶层。

```python
from multiprocessing import Process, Queue


def calculate(square_of: int, output: Queue) -> None:
    output.put(square_of * square_of)


def main() -> None:
    output = Queue()
    worker = Process(target=calculate, args=(12, output))
    worker.start()

    result = output.get(timeout=5)
    worker.join()
    print(result)


if __name__ == "__main__":
    main()
```

这里的 `Queue` 是跨进程 IPC 通道，不是线程中的 `queue.Queue`；其内容需要序列化。实际程序还应处理 `get()` 超时、子进程异常和非零 `exitcode`，并在不再使用队列时调用 `close()` 与 `join_thread()`，使后台缓冲线程有序结束。

直接使用 `Process` 适用于一个长期、独立的工作进程，或必须自行安排进程生命周期、IPC 协议、重启策略与隔离边界的场景。对于一批独立的 CPU 任务，优先 `ProcessPoolExecutor`：它提供有限并发、任务队列、`Future` 和统一关闭路径。手动创建一批 `Process` 再自己分发任务，通常只是在重写一个功能较少、异常处理更容易遗漏的进程池。

## 五、`ThreadPoolExecutor`：把阻塞 I/O 变成可管理的任务

### 1. `submit()` 与 `result()`

`submit(callable, *args, **kwargs)` 立即返回 `Future`，任务由空闲工作线程稍后执行。`future.result()` 会等待任务结束；任务成功时返回值，任务失败时**在调用 `result()` 的这一行重新抛出原始异常**。

```python
from concurrent.futures import ThreadPoolExecutor


def fetch_text(url: str) -> str:
    # 此处假设使用一个阻塞式 HTTP 客户端，并设置了超时。
    return blocking_http_get(url, timeout=5)


urls = [
    "https://example.test/a",
    "https://example.test/b",
]

with ThreadPoolExecutor(max_workers=8, thread_name_prefix="fetch") as pool:
    futures = [pool.submit(fetch_text, url) for url in urls]
    pages = [future.result() for future in futures]
```

`with` 块退出时会调用 `shutdown(wait=True)`：不再接受新任务，并等待已提交的任务结束。它适合“这一批工作必须处理完才继续”的场景。要注意，上例按 `urls` 的提交顺序等待；第一个慢任务会使后面已经完成的结果暂时不能被处理。

### 2. 按完成顺序处理：`as_completed()`

当每个任务的完成时间差异很大，或希望尽早输出成功结果、尽早发现失败时，使用 `as_completed()`。把 `Future` 映射回输入，错误日志才能准确指出哪一个任务失败。

```python
from concurrent.futures import ThreadPoolExecutor, as_completed


with ThreadPoolExecutor(max_workers=8) as pool:
    future_to_url = {
        pool.submit(fetch_text, url): url
        for url in urls
    }

    for future in as_completed(future_to_url):
        url = future_to_url[future]
        try:
            text = future.result()
        except OSError as exc:
            print(f"请求失败：{url}: {exc}")
        else:
            save_page(url, text)
```

不要只调用 `submit()` 后就离开，让异常默默停留在 `Future` 中。异常不会自动在主线程爆出；至少应统一读取所有 `Future` 的结果，或通过回调将失败交给一个明确的协调者。

### 3. `map()` 适合什么，哪里容易误会

`executor.map(function, iterable)` 的写法简洁，迭代结果时会按**输入顺序**产出，并在对应位置重新抛异常。

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as pool:
    for text in pool.map(fetch_text, urls, timeout=10):
        consume(text)
```

它适合输入和输出一一对应、顺序有意义、失败可直接中止的批处理。它不适合需要把异常和丰富上下文关联、需要按完成顺序处理、或需要对每个任务做不同重试策略的场景；此时 `submit()` 加 `as_completed()` 更清楚。

`timeout=10` 限制的是从调用 `map()` 起等待下一个结果的时间，不是给每一个 HTTP 请求自动设置网络超时。底层 I/O 的连接、读取超时仍必须由 HTTP 客户端单独配置。这两个层次混为一谈，往往正是“明明设置了 timeout 却仍卡住”的原因。

### 4. 并发上限不是一个越大的数字

若一个服务只允许 20 个并发连接，线程池开到 200 并不会凭空提高吞吐，反而可能造成排队、超时、重试风暴和本地内存增长。合理的起点是由下游容量反推，再通过压测调整。

此外，执行器内部等待队列并不替应用提供无限安全的背压。若生产者一次性为数百万条输入都调用 `submit()`，主进程自身就可能先耗尽内存。可使用有界 `queue.Queue` 搭配固定工作线程，或按批次提交并在每批中回收结果。关键不是“把任务都提交进去”，而是让尚未完成的任务数量保持可控。

## 六、`ProcessPoolExecutor`：用隔离和通信换取多核计算

### 1. 任务必须可跨进程传递

进程池会把可调用对象、参数和结果传给另一个进程，通常依赖 `pickle`。因此，提交给 `ProcessPoolExecutor` 的函数应定义在模块顶层；局部函数、lambda、嵌套闭包、打开的文件对象、锁和网络连接等通常不能可靠地传递。

```python
from concurrent.futures import ProcessPoolExecutor


def count_primes(limit: int) -> int:
    total = 0
    for number in range(2, limit):
        if is_prime(number):
            total += 1
    return total


def main() -> None:
    limits = [200_000, 220_000, 240_000, 260_000]
    with ProcessPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(count_primes, limits))
    print(counts)


if __name__ == "__main__":
    main()
```

`if __name__ == "__main__":` 不是形式主义。在 Windows 和采用 `spawn` 启动方式的环境中，工作进程会重新导入启动模块；若创建池的代码放在模块顶层，每个子进程又会继续创建新池，最终递归启动或直接报错。把“定义函数”和“启动并发工作”分开，也使模块更容易被测试和导入。

### 2. 进程池不适合小任务雨点般落下

跨进程传输有启动、pickle、复制和 IPC 成本。把一百万个只需几微秒的小函数逐个提交给进程池，可能比单线程更慢。应提高每个任务的粒度，例如让一个任务处理一个数据块。

```python
from concurrent.futures import ProcessPoolExecutor


def summarize_chunk(numbers: list[int]) -> int:
    return sum(transform(number) for number in numbers)


def chunks(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


if __name__ == "__main__":
    batches = chunks(load_numbers(), 10_000)
    with ProcessPoolExecutor() as pool:
        total = sum(pool.map(summarize_chunk, batches))
    print(total)
```

同样的道理也适用于大对象：反复把数 GB 的列表发送到多个子进程，可能使复制成本远大于计算收益。先传路径、索引或小的不可变描述；确实需要共享大量数值数据时，再评估 `multiprocessing.shared_memory` 或专门的数值计算库。

### 3. 子进程异常和池损坏

普通任务异常会在 `future.result()` 或迭代 `map()` 结果时回到父进程。异常本身最好也能被 pickle；无法序列化时，调用方看到的可能是包装后的异常，诊断信息会变差。

若工作进程被强行终止、解释器崩溃或初始化失败，池可能进入损坏状态，后续提交会抛出 `BrokenProcessPool`。这种情况不能假装“重试同一个 Future”就能修复：先记录输入和根因，关闭损坏的池，再按幂等性与资源限制决定是否用新池重试。

## 七、`Future`：结果、超时、异常和取消的真实语义

### 1. 常用方法

| 方法 | 作用 | 容易误解的地方 |
| ---- | ---- | -------------- |
| `result(timeout=None)` | 等待结果或重新抛出任务异常 | 超时只让等待者停止等，不会停止正在运行的任务 |
| `exception(timeout=None)` | 取得异常对象或 `None` | 也会等待；被取消时会抛 `CancelledError` |
| `done()` | 任务是否已结束 | 结束也可能是失败或取消 |
| `cancel()` | 尝试取消尚未开始的任务 | 返回 `False` 通常表示任务已运行或已结束 |
| `cancelled()` | 是否确已取消 | 不能据此判断业务操作有没有发生 |
| `add_done_callback(fn)` | 完成后调回调 | 回调应短小，不能阻塞工作者或抛失控异常 |

线程和进程都不能安全地被 Python 强制“杀死”。因此已开始运行的同步函数通常无法通过 `future.cancel()` 终止；`result(timeout=...)` 也只能让主线程不再等待。若需要可取消的长任务，应由任务函数协作检查停止信号，或把工作切成小块，在块之间检查是否应退出。

```python
import threading


stop_requested = threading.Event()


def copy_in_chunks(source: str, destination: str) -> None:
    with open(source, "rb") as reader, open(destination, "wb") as writer:
        while chunk := reader.read(1024 * 1024):
            if stop_requested.is_set():
                raise RuntimeError("复制被请求停止")
            writer.write(chunk)
```

进程池则应使用 `multiprocessing.Event` 等可跨进程协调的原语，且要认识到这只控制任务在检查点退出；它不会中断一个正在执行的不可中断系统调用。设计外部副作用时，幂等键、临时文件加原子重命名、事务与补偿往往比“试图强杀任务”更可靠。

### 2. 有限地等待与关闭队列

`shutdown(wait=True, cancel_futures=True)`（Python 3.9+）会拒绝新任务、取消尚未开始的等待任务，并等待正在运行的任务结束。它适合收到停止信号后不再接收新工作、尽量快速收尾的程序。

```python
from concurrent.futures import ThreadPoolExecutor, as_completed


pool = ThreadPoolExecutor(max_workers=8)
try:
    futures = [pool.submit(fetch_text, url) for url in urls]
    for future in as_completed(futures):
        handle_result(future)
finally:
    pool.shutdown(wait=True, cancel_futures=True)
```

这里仍会等待已运行任务；如果它们没有网络超时、永远卡在外部调用中，关闭也会一直等待。资源关闭策略必须与任务内部的超时、取消协议和外部客户端的关闭方式配套，不能只寄希望于执行器的 `shutdown()`。

## 八、共享状态：线程用锁，进程用消息

线程池中的任务共享内存，所以最危险的写法往往不是显式使用 `Lock`，而是“没有锁却碰巧看起来能工作”。下面的递增包括读取、计算、写入三个逻辑步骤；多个线程执行时可能丢失更新。

```python
import threading


class SafeCounter:
    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._value += 1
            return self._value
```

锁应保护完整的**不变量**，而不仅是一行赋值。锁内不要执行网络请求、长计算或未知回调：这些操作会拖慢所有竞争者，还可能因锁顺序交错而死锁。若任务只需报告结果，优先让每个任务返回不可变结果，再由一个协调者在主线程汇总；这通常比让所有任务同时修改一个 dict 更容易验证。

进程之间没有普通 Python 对象的自然共享。优先让子进程返回结果，父进程合并；或使用队列发送消息。`Manager` 的代理 dict/list 虽方便，却每次访问都可能是 IPC，性能与一致性模型都不同于本地容器，不能无意识地替换普通字典。

## 九、常见误用与修正

| 误用 | 后果 | 更稳妥的做法 |
| ---- | ---- | ------------ |
| CPU 密集纯 Python 循环开很多线程 | 上下文切换增加，吞吐未必提升 | 用进程池并按数据块提交，测量后定规模 |
| 对每个 I/O 任务新建线程 | 资源失控、难以关闭和收集异常 | 用有上限的 `ThreadPoolExecutor` |
| 提交后从不读取 `Future` | 失败被隐藏，结果无处安放 | 收集 `result()`，或在协调层统一记录处理 |
| 以为 `cancel()` 能停止正在运行的函数 | 外部请求仍继续，副作用可能已经发生 | 设计协作取消、超时和幂等性 |
| `result(timeout=...)` 当作网络超时 | 任务还在后台占着工作者 | 同时给底层客户端设置连接/读取超时 |
| 把 lambda、实例连接或巨大对象交给进程池 | pickle 失败或复制成本过高 | 使用顶层函数，传轻量参数，增大任务粒度 |
| 忘记 `__main__` 保护 | Windows/spawn 环境下递归创建进程 | 将启动逻辑放入 `main()` 并加保护 |
| 在锁中做慢 I/O | 吞吐降低，甚至死锁 | 缩小临界区；用队列或两阶段设计 |
| 把线程池当可靠任务队列 | 进程退出或崩溃时任务消失 | 需要持久重试时使用数据库或专用任务系统 |

## 十、落地前的检查清单

- 任务真正受限于 I/O 还是 CPU？是否用基准测试验证过？
- `max_workers` 是否同时受本机 CPU、内存、数据库连接池和远端限流约束？
- 是否限制了已提交但尚未完成的任务数量，避免无界队列占满内存？
- 每一个 `Future` 是否都能被读取、记录或以其他方式处理其结果和异常？
- 底层 HTTP、数据库、文件操作是否有自己的超时和资源关闭？
- 长任务能否协作停止？重试或重复执行会不会造成不可逆副作用？
- 进程池的函数、参数、返回值和异常能否序列化？任务粒度是否足够大？
- Windows 或 `spawn` 环境下，启动逻辑是否位于 `if __name__ == "__main__":` 之内？
- 共享状态是否由锁保护完整不变量，或者能否改为消息传递和单一汇总者？

## 十一、总结

`ThreadPoolExecutor` 与 `ProcessPoolExecutor` 的价值，不是把函数神奇地“并行化”，而是建立有限工作者、`Future`、异常传播和关闭路径这一整套任务协调模型。

- 阻塞 I/O 通常选择线程池；纯 Python CPU 计算通常选择进程池，但都应先测量成本与瓶颈。
- `Future.result()` 是结果和任务异常回到协调者的边界；超时和 `cancel()` 并不等于强制停止正在运行的工作。
- 线程共享内存，需要用锁或队列表达所有权；进程隔离内存，需要承担序列化与 IPC 成本。
- `with Executor(...)` 或显式 `shutdown()` 只解决执行器的收尾；任务本身仍要拥有超时、取消、资源释放与副作用幂等策略。

先把并发量、任务生命周期和状态归属定义清楚，再选择线程池或进程池。否则即使程序看起来同时做了很多事，也只是把原本可见的问题拆散到了更难追踪的地方而已。

## 参考资料

- [Python `concurrent.futures` 官方文档](https://docs.python.org/3/library/concurrent.futures.html)
- [Python `threading` 官方文档](https://docs.python.org/3/library/threading.html)
- [Python `multiprocessing` 官方文档](https://docs.python.org/3/library/multiprocessing.html)
