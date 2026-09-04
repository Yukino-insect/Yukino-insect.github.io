+++
date = '2026-08-31T16:30:00+08:00'
draft = false
title = 'Python 线程模型与并发控制：GIL、asyncio 与多进程'
+++

Python 的并发讨论常被一句“有 GIL，所以不用锁”带偏。那句话既不完整，也不适合当作设计依据：GIL 是 **CPython** 的实现机制，不是整个 Python 语言的同步模型；即使在常规 CPython 中，它也不能把多个 Python 语句组成的业务操作变成原子的；而从 Python 3.13 起，CPython 还提供了可禁用 GIL 的自由线程构建。

选择并发模型前，先回答任务在等待什么：等待网络、磁盘、数据库等 I/O，还是持续占用 CPU 计算？随后再决定使用线程、`asyncio` 协程、多进程，或它们的组合。正确的同步工具取决于共享的是什么、谁拥有它，而不是取决于 API 名字里是否带有 “async”。

## 一、三个概念：并发、并行与执行单元

**并发**表示多个任务的执行期重叠，它们可以在一个 CPU 核上轮流推进。**并行**表示多个任务在不同核心上同一时刻计算。Python 常见的执行单元有三种：

| 执行单元 | 调度者 | 内存关系 | 典型用途 |
| -------- | ------ | -------- | -------- |
| OS 线程（`threading`） | 操作系统 | 同一进程内共享对象 | 阻塞 I/O、调用阻塞库 |
| 协程/任务（`asyncio.Task`） | 事件循环 | 通常同一线程内共享对象 | 大量异步 I/O |
| 进程（`multiprocessing`） | 操作系统 | 默认隔离，需要序列化或显式共享 | CPU 密集型计算、隔离 |

```text
一个进程
├─ 线程 A ─┬─ asyncio 事件循环 ─ Task 1 / Task 2 / Task 3
│          └─ Python 对象、文件句柄、连接池等进程资源
└─ 线程 B ─── 可访问同一批 Python 对象

另一个进程 ─── 独立解释器与地址空间
```

协程不是线程，`await` 也不是把工作丢给新线程。默认事件循环通常在一个线程中运行；协程只有在 `await` 一个能挂起的对象、或主动把控制权交回事件循环时，其他任务才有机会运行。

## 二、Python 语言、实现与 GIL

### 1. GIL 到底限制了什么

在常规 CPython 中，全局解释器锁（GIL）让同一进程中的线程不能在同一时刻执行 Python 字节码。因此，用纯 Python 编写的 CPU 密集循环通常不能随着 `threading.Thread` 数量增加而在多核上等比例加速。

这不意味着线程毫无价值：阻塞 I/O 时，CPython 和许多扩展会释放 GIL，其他线程可以继续运行。一个线程在等待 socket、文件、数据库驱动或子进程时，其他线程仍能取得进展，所以线程很适合将已有的同步阻塞 I/O 并发化。

还要注意两点：

- GIL 是 CPython 的实现细节。PyPy、Jython 等实现不能用“CPython 现在恰好怎样做”替代其文档与契约。
- GIL 只是在解释器内部序列化一部分执行，并不替你表达业务层面的互斥、顺序、事务边界或对象所有权。

### 2. GIL 不是应用程序锁

下面的“先检查、后修改”跨越多个操作。即使每一个简单操作看似不会被撕裂，线程切换仍可发生在它们之间：

```python
if user_id not in active_users:
    active_users.add(user_id)
    charge_for_registration(user_id)
```

两个线程可能同时观察到 `user_id` 不在集合中，随后重复收费。不要依赖某版本 CPython 对某个内置操作的偶然原子性；用锁把“检查 + 修改 + 必须一起成立的副作用”保护为一个逻辑临界区，或者更好地把这项决定交给单一所有者/数据库的唯一约束。

```python
import threading

active_users: set[str] = set()
users_lock = threading.Lock()

def register_once(user_id: str) -> bool:
    with users_lock:
        if user_id in active_users:
            return False
        active_users.add(user_id)

    # 耗时或可能重入的外部调用应放在锁外；实际业务还需处理失败补偿。
    charge_for_registration(user_id)
    return True
```

这段代码也刻意留下一个设计问题：若收费失败，集合状态如何回滚？锁只保证并发访问的互斥，不自动替你定义业务事务。并发安全与业务一致性不是同义词，混在一起只会让两个问题都更难处理。

### 3. Python 3.13+ 的自由线程 CPython

CPython 从 3.13 开始提供自由线程（free-threaded）构建，可在运行时禁用 GIL，使多个线程能够并行执行 Python 代码。它不是常规构建的默认模式；不支持自由线程的 C 扩展被导入时还可能重新启用 GIL。可通过 `sysconfig.get_config_var("Py_GIL_DISABLED")` 判断构建是否支持，Python 3.14 还可用 `sys._is_gil_enabled()` 检查当前运行时状态。

这带来的结论并不浪漫：原本依赖 GIL 偶然工作起来的代码会更早暴露问题。自由线程构建为部分内置容器提供内部保护，但官方建议仍是：跨多个操作的不变量、可变共享状态和需要可移植行为的代码，应使用显式同步或避免共享。把锁写成正确的协议，才能同时适应常规 CPython、自由线程 CPython 和其他实现。

## 三、`threading`：操作系统线程与共享内存

### 1. 创建、会合与异常

线程对象在 `start()` 后才开始运行；`join()` 等待它结束。线程内未捕获的异常不会自动在创建者线程重新抛出，而是经 `threading.excepthook` 处理。因此，涉及结果或异常的任务通常更适合 `concurrent.futures`。

```python
import threading

def download(url: str) -> None:
    # 调用一个阻塞的 HTTP 客户端
    fetch_and_store(url)

thread = threading.Thread(target=download, args=("https://example.test/data",))
thread.start()
thread.join()
```

守护线程（`daemon=True`）会在仅剩守护线程时被解释器直接终止；它们的 `finally`、文件刷新和网络清理不应被依赖。需要可靠完成或清理的工作应使用非守护线程，并显式发送停止信号后 `join()`。

### 2. `Lock`：默认的互斥工具

`threading.Lock` 保护一段临界区。用 `with` 获取锁可以确保异常或 `return` 时释放锁：

```python
import threading

class Counter:
    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._value += 1
            return self._value
```

锁应该保护一个**不变量**，而不是机械地保护单个变量。若订单状态、库存和审计记录必须一同更新，应让它们遵从同一个同步协议。锁内避免执行网络 I/O、长时间计算、未知回调或再次获取其他锁的代码；这些操作会扩大竞争范围，并为死锁埋下条件。

`threading.RLock` 允许同一线程重复获取同一把锁，适合少数必须重入的封装边界，但不能修复不同线程间的死锁。看到它时，更应该审视调用结构是否绕得太远。

### 3. 条件变量、事件与信号量

| 原语 | 表达的问题 | 使用要点 |
| ---- | ---------- | -------- |
| `Condition` | “队列是否非空”“状态是否满足” | 必须在循环/`wait_for` 中重新检查谓词 |
| `Event` | 一个可保持的开/关信号 | `set()` 后的等待者可立即通过，适合启动/停止通知 |
| `Semaphore` | 最多允许多少个执行者 | 用于连接数、并发请求数等容量限制 |
| `Barrier` | 一组线程都到达某个阶段 | 适合阶段性算法，需处理参与者失败 |

条件变量等待的是**共享状态表达的条件**，不是一次通知。`wait()` 可能伪唤醒，通知也不保存历史，因此应把状态和检查放在锁的保护下：

```python
import collections
import threading

jobs: collections.deque[str] = collections.deque()
closed = False
condition = threading.Condition()

def take_job() -> str | None:
    with condition:
        condition.wait_for(lambda: closed or jobs)
        if not jobs:
            return None
        return jobs.popleft()

def put_job(job: str) -> None:
    with condition:
        jobs.append(job)
        condition.notify()

def close_queue() -> None:
    global closed
    with condition:
        closed = True
        condition.notify_all()
```

### 4. 用 `queue.Queue` 实现生产者—消费者

自己维护队列、锁和条件变量很容易遗漏关闭、异常或任务完成计数。普通生产者—消费者场景优先使用 `queue.Queue`：它本身是线程安全的，并可通过 `maxsize` 形成**背压**，避免生产者无限堆积任务占满内存。

```python
from queue import Queue
import threading

STOP = object()
jobs: Queue[str | object] = Queue(maxsize=100)

def worker() -> None:
    while True:
        job = jobs.get()
        try:
            if job is STOP:
                return
            process(job)
        finally:
            jobs.task_done()

workers = [threading.Thread(target=worker) for _ in range(4)]
for thread in workers:
    thread.start()

for item in load_jobs():
    jobs.put(item)  # 队列满时阻塞，向上游施加背压

for _ in workers:
    jobs.put(STOP)

jobs.join()
for thread in workers:
    thread.join()
```

这里的哨兵数量与工作线程数相同；每个工作线程取到一个哨兵后退出。若 `process` 会抛异常，生产环境应把异常传回协调者、记录失败或触发停止，而不是静静让工作线程消失。

### 5. 用 `ThreadPoolExecutor` 管理任务

线程池避免重复创建线程，并以 `Future` 传回返回值和异常。它适合一批独立的阻塞 I/O 任务；线程数需要与外部服务容量、连接池和背压一起规划，并非越多越好。

```python
from concurrent.futures import ThreadPoolExecutor

def fetch(url: str) -> bytes:
    return blocking_http_get(url)

with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(fetch, url) for url in urls]
    pages = [future.result() for future in futures]  # 在这里重新抛出任务异常
```

## 四、`asyncio`：协作式并发，而不是隐式多线程

### 1. 事件循环与调度点

协程函数由 `async def` 定义；调用它只得到协程对象，只有被 `await`、封装为任务或交给事件循环运行后才会执行。事件循环在任务可等待 I/O 时切换到别的任务。

```python
import asyncio

async def fetch(url: str) -> str:
    response = await async_http_get(url)
    return response.text

async def main() -> None:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(fetch(url)) for url in urls]

    pages = [task.result() for task in tasks]

asyncio.run(main())
```

`TaskGroup`（Python 3.11+）是结构化并发工具：离开 `async with` 时会等待组内任务；若其中任务失败，它会取消尚未完成的同组任务，并以异常组向外报告。相比创建“无人管理的后台任务”，任务的生命周期、异常和取消边界都更清楚。

不要在事件循环线程中调用 `time.sleep()`、同步 HTTP 客户端或耗时 CPU 循环；它们会卡住整个事件循环。使用异步库，或将不可避免的阻塞调用转移出去：

```python
result = await asyncio.to_thread(blocking_function, argument)
```

`to_thread` 只是把阻塞函数交给线程运行；对常规 CPython 的纯 Python CPU 计算，它通常不能绕过 GIL。CPU 密集型任务仍应考虑进程池或释放 GIL 的原生扩展。

### 2. 协程也会发生竞态条件

协程通常只在 `await` 处让出控制权，因此下面的纯同步片段执行时不会被另一个 asyncio 任务插入：

```python
total += 1
```

但只要“读取—等待—写回”之间有 `await`，竞态条件马上出现：

```python
balance = 0

async def add_one() -> None:
    global balance
    current = balance
    await asyncio.sleep(0)  # 此处可能切换到另一个任务
    balance = current + 1
```

使用 `asyncio.Lock` 保护跨 `await` 的共享不变量：

```python
import asyncio

balance = 0
balance_lock = asyncio.Lock()

async def add_one() -> None:
    global balance
    async with balance_lock:
        balance += 1
```

`asyncio` 的 `Lock`、`Event`、`Condition`、`Semaphore` 等原语**不是线程安全的**，只能协调同一事件循环中的任务；不要拿它们给 OS 线程同步。线程之间使用 `threading` 原语，跨进程则使用 `multiprocessing` 原语、队列或外部服务。

### 3. 取消、超时和限流

取消在协程中通常以 `asyncio.CancelledError` 的形式在下一次可取消的等待点送达。除非确实要清理后重新抛出，否则不要粗暴地吞掉它；否则上层认为任务已取消，任务却可能继续运行。

```python
import asyncio

async def fetch_with_limit(url: str, limit: asyncio.Semaphore) -> str:
    async with limit:
        async with asyncio.timeout(10):
            return await async_http_get_text(url)
```

信号量控制的是并发数量，不等同于速率限制；服务端允许“每秒 10 个请求”时还需要令牌桶等节流策略。超时也不自动停止底层不可取消的阻塞 I/O，所以要确认所用客户端对取消和超时的语义。

## 五、`multiprocessing`：用进程换取并行与隔离

进程有独立地址空间和各自的 Python 解释器，因此常规 CPython 下 CPU 密集型工作可使用多个 CPU 核。代价是创建进程、序列化参数与结果、进程间通信（IPC）和内存占用。

```python
from concurrent.futures import ProcessPoolExecutor

def count_primes(limit: int) -> int:
    # 纯 CPU 计算；必须在模块顶层，便于子进程导入
    return sum(is_prime(n) for n in range(limit))

if __name__ == "__main__":
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(count_primes, [500_000, 600_000]))
    print(results)
```

在 Windows 以及采用 `spawn` 启动方式的平台，子进程会重新导入主模块；因此创建进程池的顶层入口必须由 `if __name__ == "__main__":` 保护。传给进程池的函数和参数通常需要可 pickle；大型数据反复复制时，进程池可能得不偿失，应评估批处理、共享内存或改用原生计算库。

`multiprocessing.Queue`、`Pipe`、共享内存和 `Manager` 可用于 IPC。优先让进程通过消息传递协作；`Manager` 提供的代理对象方便，但会引入 IPC 开销，不能当作普通 dict/list 的无代价替代品。

## 六、选择模型：先按工作负载，再按边界

| 场景 | 首选 | 关键控制点 |
| ---- | ---- | ---------- |
| 少量已有阻塞 I/O | `ThreadPoolExecutor` / `threading` | 队列上限、超时、连接池容量 |
| 大量异步网络 I/O | `asyncio` + 异步客户端 | 不阻塞事件循环、限流、取消传播 |
| 纯 Python CPU 计算（常规 CPython） | `ProcessPoolExecutor` / `multiprocessing` | 序列化成本、数据分片、入口保护 |
| 原生库计算且释放 GIL | 线程池可能有效 | 查库文档、控制原生线程数 |
| 多线程共享复杂可变状态 | 尽量改成队列/单一所有者 | `Lock` 保护不变量、明确关闭协议 |
| 跨机器或需要持久可靠任务 | 外部队列、数据库或任务系统 | 幂等、重试、事务、可观测性 |

自由线程 CPython 可以改变“纯 Python CPU 任务是否适合线程”的性能结论，却不改变同步设计的原则。即使没有 GIL，线程仍共享内存；即使有 GIL，业务操作仍可能跨多个步骤。模型选择应服从测量和所有权，而不是对某个解释器版本的想象。

## 七、混合模型与跨边界通信

实际服务常常混合使用模型：事件循环负责网络连接；`asyncio.to_thread()` 接入少量遗留阻塞 API；进程池完成 CPU 密集计算。边界必须保持清楚：

- 从 `asyncio` 任务交给线程：用 `asyncio.to_thread()`；不要在事件循环里直接执行阻塞函数。
- 从外部线程提交协程：用 `asyncio.run_coroutine_threadsafe(coro, loop)`，不要直接操作另一个线程正在运行的事件循环对象。
- 线程与协程分别使用自己的同步原语；`asyncio.Queue` 不是线程安全队列，`queue.Queue` 也不应在协程中用阻塞式 `get()`。
- 进程边界把对象变成消息；把大而可变的对象“共享给所有人”通常只会扩大协调成本。

## 八、并发代码审查清单

- 任务是 I/O 密集还是 CPU 密集？所选模型能否真正提供预期的并发或并行？
- 共享可变状态由谁拥有？是否能改为消息传递、不可变数据或单一写者？
- 锁保护的是完整不变量吗？是否存在检查后再执行的竞态条件？
- 条件等待是否检查状态谓词，而不是只等待一次 `notify()`？
- 队列是否有容量上限、关闭信号、异常传播和任务完成策略？
- `asyncio` 任务中是否误用了阻塞 I/O 或 `time.sleep()`？
- 超时和取消是否会传递到子任务，并正确释放资源？
- 线程、任务和进程在退出时是否被等待；守护线程是否被错误地当作可靠后台任务？
- 是否把 CPython 当前的 GIL 行为当成了跨版本、跨实现的线程安全保证？

## 九、总结

Python 并发没有唯一的“最快方案”，只有与工作负载和状态边界匹配的模型。

- `threading` 共享内存，适合阻塞 I/O；GIL 不取代应用层同步。
- `asyncio` 在协作式调度点切换任务，适合大量异步 I/O；它的同步原语只能用于任务间协调。
- `multiprocessing` 以隔离和序列化成本换取多核并行，适合常规 CPython 中的 CPU 密集工作。
- 锁解决互斥，队列解决交接与背压，结构化并发解决任务生命周期；没有一个能代替另一个。
- 自由线程 CPython 让多线程并行成为可能，但更要求代码用明确的所有权与同步协议表达正确性。

先让状态的拥有者唯一、任务的结束路径明确、错误能回到协调者；之后再谈并发度。否则程序也许跑得很快，只是更快地跑向一个难以复现的问题。

## 参考资料

- [Python `threading` 官方文档](https://docs.python.org/3/library/threading.html)
- [Python 自由线程支持说明](https://docs.python.org/3/howto/free-threading-python.html)
- [Python `asyncio` 同步原语](https://docs.python.org/3/library/asyncio-sync.html)
- [Python `asyncio` 协程与任务](https://docs.python.org/3/library/asyncio-task.html)
