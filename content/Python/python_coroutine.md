---

date = '2026-08-17T22:03:31+08:00'
draft = false
title = 'Python 协程'

---

# Python 协程

## 1. 协程是什么

协程是一种**可以主动暂停、之后再从暂停处继续执行的函数式执行单元**。

普通函数一旦开始执行，通常会一直运行到 `return` 或抛出异常：

```python
def func():
    print("start")
    print("end")

func()
```

协程不同。协程可以在执行过程中遇到 `await` 时暂停，把控制权还给事件循环。等它等待的事情完成之后，再从暂停的位置继续往下执行。

```python
import asyncio

async def main():
    print("start")
    await asyncio.sleep(1)
    print("end")

asyncio.run(main())
```

这里的 `await asyncio.sleep(1)` 不会让整个线程傻等 1 秒。它会暂停当前协程，把执行权交还给事件循环。事件循环可以趁这 1 秒去运行别的协程。

所以，协程适合处理大量 I/O 等待型任务，例如：

1. 网络请求
2. 数据库访问
3. WebSocket 连接
4. 文件或管道 I/O
5. 定时任务
6. 高并发服务端程序

但协程并不会神奇地让 CPU 计算变快。CPU 密集型任务如果长时间不让出控制权，仍然会阻塞整个事件循环。

## 2. async def

`async def` 用来定义原生协程函数：

```python
async def fetch_data():
    return "data"
```

注意，调用协程函数不会立刻执行函数体，而是会创建一个 coroutine object：

```python
coro = fetch_data()
print(coro)
```

只有当这个 coroutine object 被 `await`、被封装成 `Task`，或交给事件循环运行时，函数体才会真正执行。

```python
import asyncio

async def fetch_data():
    print("running")
    return "data"

async def main():
    result = await fetch_data()
    print(result)

asyncio.run(main())
```

## 3. await

`await` 的含义是：**暂停当前协程，等待一个 awaitable 对象完成，然后拿到它的结果**。

常见的 awaitable 对象有三类：

1. coroutine object
2. `asyncio.Task`
3. `asyncio.Future`

例如：

```python
import asyncio

async def get_number():
    await asyncio.sleep(1)
    return 100

async def main():
    number = await get_number()
    print(number)

asyncio.run(main())
```

执行到：

```python
number = await get_number()
```

当前 `main()` 协程会暂停。等 `get_number()` 完成后，它的返回值 `100` 会成为 `await get_number()` 这个表达式的结果，于是赋值给 `number`。

`await` 只能出现在 `async def` 定义的协程函数内部。普通函数里不能直接使用 `await`。

## 4. asyncio.run()

`asyncio.run(coro)` 是运行异步程序最常用的入口：

```python
import asyncio

async def main():
    print("hello")

asyncio.run(main())
```

它会做几件事：

1. 创建一个新的事件循环。
2. 在事件循环里运行传入的 coroutine。
3. 等主 coroutine 执行结束。
4. 关闭事件循环。

通常，一个 Python 程序的最外层只调用一次 `asyncio.run()`。

不要在已经运行的事件循环里再调用 `asyncio.run()`。比如在某些异步框架、Notebook 或 GUI 程序中，事件循环可能已经存在，这时应该使用框架提供的运行方式，或者在协程内部使用 `await`。

## 5. asyncio.create_task()

如果只是写：

```python
result = await task()
```

那么当前协程会等待 `task()` 完成后再继续。这是顺序执行。

如果希望多个协程并发运行，可以用 `asyncio.create_task()` 把协程包装成 `Task`：

```python
import asyncio

async def worker(name, delay):
    await asyncio.sleep(delay)
    return f"{name} done"

async def main():
    task1 = asyncio.create_task(worker("A", 2))
    task2 = asyncio.create_task(worker("B", 1))

    result1 = await task1
    result2 = await task2

    print(result1)
    print(result2)

asyncio.run(main())
```

`create_task()` 做的是：把 coroutine 注册到当前正在运行的事件循环中，让事件循环有机会调度它执行。

注意，这里的并发不是多线程并行。默认情况下，`asyncio` 事件循环运行在一个线程里。多个协程是在同一个线程中交替执行，只是在等待 I/O 时主动让出控制权，所以看起来像同时进行。

## 6. asyncio.gather()

`asyncio.gather()` 用来并发等待多个 awaitable，并按照传入顺序返回结果：

```python
import asyncio

async def worker(name, delay):
    await asyncio.sleep(delay)
    return name

async def main():
    results = await asyncio.gather(
        worker("A", 2),
        worker("B", 1),
        worker("C", 3),
    )

    print(results)

asyncio.run(main())
```

输出结果是：

```python
['A', 'B', 'C']
```

虽然 `B` 最先完成，但 `gather()` 返回的结果顺序仍然和传入顺序一致。

如果其中一个任务抛出异常，默认情况下 `gather()` 会把异常抛给等待它的协程。其他任务如何处理要看具体状态和版本行为，实际写业务代码时，不要把“一个失败时其他任务一定如何如何”当成模糊印象，最好明确使用取消、超时或 `return_exceptions=True`。

```python
results = await asyncio.gather(
    worker("A", 1),
    worker("B", 1),
    return_exceptions=True,
)
```

设置 `return_exceptions=True` 后，异常会作为结果列表里的元素返回。

## 7. asyncio.TaskGroup

`asyncio.TaskGroup` 是 Python 3.11 引入的结构化并发 API。它可以把一组任务放在一个明确的作用域里管理：

```python
import asyncio

async def worker(name, delay):
    await asyncio.sleep(delay)
    print(f"{name} done")

async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(worker("A", 2))
        tg.create_task(worker("B", 1))

asyncio.run(main())
```

`TaskGroup` 的好处是：任务的生命周期被限制在 `async with` 块内。离开这个块时，里面创建的任务要么已经正常完成，要么异常会被统一处理。

如果任务组里有任务失败，`TaskGroup` 会取消组内其他未完成任务，并在退出时抛出异常组。相比手动创建多个 task 再到处 `await`，这种方式更不容易留下后台悬挂任务。

## 8. asyncio.sleep()

`asyncio.sleep()` 是异步睡眠：

```python
await asyncio.sleep(1)
```

它和 `time.sleep(1)` 的区别很重要：

```python
import time

time.sleep(1)
```

`time.sleep()` 会阻塞当前线程。如果在事件循环线程里调用它，整个事件循环都会停住，其他协程也没法运行。

而：

```python
await asyncio.sleep(1)
```

会暂停当前协程，把控制权交还给事件循环。其他协程仍然可以继续运行。

在异步代码中，如果只是想“等一会儿”，通常应该使用 `await asyncio.sleep(...)`。

## 9. wait_for() 和 timeout()

`asyncio.wait_for()` 可以给某个 awaitable 设置超时时间：

```python
import asyncio

async def slow():
    await asyncio.sleep(10)
    return "done"

async def main():
    try:
        result = await asyncio.wait_for(slow(), timeout=1)
        print(result)
    except asyncio.TimeoutError:
        print("timeout")

asyncio.run(main())
```

超时后，`wait_for()` 会取消被等待的任务，并抛出 `TimeoutError`。

Python 3.11 之后，也可以使用 `asyncio.timeout()`：

```python
import asyncio

async def main():
    try:
        async with asyncio.timeout(1):
            await asyncio.sleep(10)
    except TimeoutError:
        print("timeout")

asyncio.run(main())
```

`asyncio.timeout()` 更适合给一段异步代码设置统一的超时边界。

## 10. shield()

`asyncio.shield()` 可以保护一个 awaitable，使它不因为外层等待者被取消而立刻被取消：

```python
import asyncio

async def important_work():
    await asyncio.sleep(2)
    return "saved"

async def main():
    task = asyncio.create_task(important_work())

    try:
        result = await asyncio.shield(task)
        print(result)
    except asyncio.CancelledError:
        print("outer cancelled")

asyncio.run(main())
```

`shield()` 不是让任务永远不可取消。它只是隔离一部分取消传播。任务本身仍然可能被直接取消，或者因为事件循环关闭而结束。

## 11. wait() 和 as_completed()

`asyncio.wait()` 可以等待一组任务，并返回完成和未完成的集合：

```python
done, pending = await asyncio.wait(tasks, timeout=1)
```

它适合需要自己管理“哪些完成了、哪些还没完成”的场景。

`asyncio.as_completed()` 会按照任务完成顺序产生结果：

```python
import asyncio

async def worker(name, delay):
    await asyncio.sleep(delay)
    return name

async def main():
    tasks = [
        asyncio.create_task(worker("A", 2)),
        asyncio.create_task(worker("B", 1)),
        asyncio.create_task(worker("C", 3)),
    ]

    for future in asyncio.as_completed(tasks):
        result = await future
        print(result)

asyncio.run(main())
```

这段代码会先打印 `B`，再打印 `A`，最后打印 `C`。

## 12. 取消任务

`Task.cancel()` 用来请求取消一个任务：

```python
import asyncio

async def worker():
    try:
        while True:
            print("working")
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("cancelled")
        raise

async def main():
    task = asyncio.create_task(worker())
    await asyncio.sleep(3)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print("task is cancelled")

asyncio.run(main())
```

取消不是粗暴地杀掉任务。它的机制是：在任务下一次恢复执行时，向协程内部抛入 `CancelledError`。

所以协程应该在必要时清理资源：

```python
async def worker():
    try:
        await do_work()
    finally:
        await cleanup()
```

如果捕获了 `CancelledError`，通常应该在清理后重新 `raise`。否则调用方可能误以为任务正常完成了。

## 13. Future 和 Task

`Future` 表示一个“未来会有结果”的占位对象。

它有几种可能状态：

1. pending：还没完成。
2. done：已经有结果或异常。
3. cancelled：已经被取消。

可以给 Future 设置结果：

```python
future.set_result(value)
```

也可以设置异常：

```python
future.set_exception(exc)
```

在日常业务代码里，很少需要直接创建 `Future`。它更多是库、框架和底层适配代码使用的对象。

`Task` 是 `Future` 的子类。它包装了一个 coroutine，并负责驱动这个 coroutine 执行。

简单说：

1. coroutine object 是“可以被运行的协程代码”。
2. Future 是“未来结果的容器”。
3. Task 是“被事件循环调度执行的 coroutine，同时也是一个 Future”。

## 14. 同步原语

`asyncio` 提供了一些异步版本的同步工具。它们不会阻塞线程，而是会在等待时暂停当前协程。

### Lock

`asyncio.Lock` 用来保护临界区：

```python
lock = asyncio.Lock()

async with lock:
    await update_shared_state()
```

### Semaphore

`asyncio.Semaphore` 用来限制并发数量：

```python
import asyncio

sem = asyncio.Semaphore(3)

async def fetch(url):
    async with sem:
        return await request(url)
```

这表示最多允许 3 个 `fetch()` 同时进入 `async with sem` 的区域。

### Event

`asyncio.Event` 用来通知多个协程某件事已经发生：

```python
event = asyncio.Event()

async def waiter():
    await event.wait()
    print("event happened")

async def setter():
    event.set()
```

### Queue

`asyncio.Queue` 常用于生产者消费者模型：

```python
import asyncio

async def producer(queue):
    for i in range(5):
        await queue.put(i)
    await queue.put(None)

async def consumer(queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        print(item)
        queue.task_done()

async def main():
    queue = asyncio.Queue()
    await asyncio.gather(
        producer(queue),
        consumer(queue),
    )

asyncio.run(main())
```

## 15. async with

`async with` 用来使用异步上下文管理器。

普通上下文管理器使用：

```python
with open("a.txt") as f:
    ...
```

异步上下文管理器使用：

```python
async with resource:
    ...
```

它背后调用的是：

```python
await resource.__aenter__()
await resource.__aexit__(...)
```

常见场景包括：

1. 异步 HTTP client session
2. 异步数据库连接
3. 异步锁
4. `asyncio.TaskGroup`
5. `asyncio.timeout`

## 16. async for 和异步迭代器

`async for` 用来遍历异步迭代器：

```python
async for item in async_iterable:
    print(item)
```

异步迭代器需要实现：

```python
def __aiter__(self):
    return self

async def __anext__(self):
    ...
```

当没有更多元素时，`__anext__()` 应该抛出 `StopAsyncIteration`。

示例：

```python
import asyncio

class AsyncCounter:
    def __init__(self, limit):
        self.current = 0
        self.limit = limit

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.current >= self.limit:
            raise StopAsyncIteration

        await asyncio.sleep(1)
        self.current += 1
        return self.current

async def main():
    async for number in AsyncCounter(3):
        print(number)

asyncio.run(main())
```

## 17. 异步生成器

异步生成器是在 `async def` 里使用 `yield`：

```python
import asyncio

async def ticker():
    for i in range(3):
        await asyncio.sleep(1)
        yield i

async def main():
    async for item in ticker():
        print(item)

asyncio.run(main())
```

异步生成器适合表达“异步地产生一连串结果”的场景，比如流式响应、分页读取、消息订阅等。

它和普通 generator 的区别是：

1. 普通 generator 用 `for` 遍历。
2. 异步 generator 用 `async for` 遍历。
3. 异步 generator 内部可以使用 `await`。

## 18. to_thread() 和 run_in_executor()

如果必须在异步程序里调用阻塞函数，可以考虑把它放到线程里运行。

Python 3.9 之后常用 `asyncio.to_thread()`：

```python
import asyncio
import time

def blocking_io():
    time.sleep(2)
    return "done"

async def main():
    result = await asyncio.to_thread(blocking_io)
    print(result)

asyncio.run(main())
```

更底层的方式是 `loop.run_in_executor()`：

```python
import asyncio

def blocking_io():
    ...

async def main():
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, blocking_io)
    print(result)

asyncio.run(main())
```

`None` 表示使用默认线程池。

这类 API 适合临时兼容阻塞 I/O。对于大量 CPU 密集型计算，线程池未必能解决问题，因为 CPython 有 GIL。此时可能需要进程池、原生扩展、向量化计算或把计算任务拆到其他服务。

## 19. 当前任务和事件循环

在协程内部，可以获取当前运行的事件循环：

```python
loop = asyncio.get_running_loop()
```

可以获取当前 task：

```python
task = asyncio.current_task()
```

也可以查看当前事件循环中还没完成的任务：

```python
tasks = asyncio.all_tasks()
```

这些 API 更常用于调试、框架开发和高级控制。普通业务代码通常不需要频繁操作事件循环对象。

## 20. 协程的运行原理

理解协程的关键，是把它看成“可暂停的函数”。

一个 `async def` 函数被调用时，不会马上执行，而是返回一个 coroutine object：

```python
async def hello():
    print("hello")

coro = hello()
```

此时 `hello()` 的函数体还没有运行。

当 coroutine 被事件循环调度时，它才会开始执行。执行到 `await` 时，如果等待的对象还没完成，当前 coroutine 就会暂停，并把控制权交回事件循环。

事件循环大致做这些事情：

1. 保存一批待运行的任务。
2. 运行其中一个任务。
3. 任务遇到 `await`，表示它暂时无法继续。
4. 事件循环记录它在等待什么。
5. 事件循环去运行其他已经准备好的任务。
6. 某个 I/O、定时器或 Future 完成后，对应任务重新变成可运行。
7. 事件循环继续恢复这个任务。

这就是协程并发的核心：**不是同时执行多段 Python 代码，而是在等待期间切换到别的任务**。

## 21. await 背后的控制权转移

可以把：

```python
result = await something()
```

粗略理解成：

1. 当前协程说：“我现在依赖 `something()` 的结果。”
2. 如果 `something()` 没完成，当前协程暂停。
3. 事件循环去执行其他任务。
4. `something()` 完成后，事件循环恢复当前协程。
5. `await something()` 表达式变成它的返回值。
6. 代码继续执行，赋值给 `result`。

从底层概念上说，`await` 依赖 awaitable 对象的 `__await__()` 方法。这个方法会返回一个迭代器，事件循环可以通过这个迭代器驱动等待过程。

早期 Python 的协程是基于 generator 的：

```python
def old_style():
    result = yield from another_coroutine()
```

现代写法是：

```python
async def new_style():
    result = await another_coroutine()
```

`async/await` 可以看成是对这套模型的语法级强化。它把“这里会暂停并等待”的意图表达得更明确，也避免普通 generator 和协程混在一起造成混乱。

## 22. Task 如何驱动 coroutine

`Task` 的职责是驱动 coroutine 往前运行。

可以用一个非常简化的模型理解它：

```python
class SimpleTask:
    def __init__(self, coro):
        self.coro = coro

    def step(self, value=None, exc=None):
        try:
            if exc is None:
                awaited = self.coro.send(value)
            else:
                awaited = self.coro.throw(exc)
        except StopIteration as e:
            self.result = e.value
            return

        # awaited 表示当前协程正在等待的东西
        # 等 awaited 完成后，再调用 step(...) 恢复协程
```

真实的 `asyncio.Task` 要复杂得多，要处理 Future、回调、取消、异常、上下文变量和事件循环集成。但核心思想就是这样：

1. 用 `.send(None)` 启动 coroutine。
2. coroutine 执行到 `await` 后暂停。
3. Task 记录 coroutine 等待的 Future。
4. Future 完成时，事件循环通过回调唤醒 Task。
5. Task 再次 `.send(result)`，把结果送回 coroutine。
6. coroutine 从 `await` 后面继续执行。

如果等待对象失败了，Task 会把异常通过 `.throw(exc)` 抛回 coroutine，使 `await` 那一行表现得像直接抛出了异常。

## 23. Future 如何唤醒 Task

`Future` 是事件循环和任务之间的重要连接点。

当一个 Task 等待某个 Future 时，大致会发生：

```python
future.add_done_callback(task_wakeup)
```

等 Future 完成后，它会执行回调：

```python
task_wakeup(future)
```

回调会取出 Future 的结果或异常，然后恢复 Task：

```python
try:
    result = future.result()
except Exception as exc:
    task.step(exc=exc)
else:
    task.step(value=result)
```

于是协程里的：

```python
result = await future
```

要么得到结果，要么抛出异常。

当然，真实实现不会这么草率。这里的代码只是为了说明控制流。把原理看清楚即可，不必把伪代码当源码背下来。

## 24. 事件循环到底循环什么

事件循环维护的东西大致包括：

1. ready 队列：现在就可以运行的回调或任务。
2. scheduled 队列：未来某个时间点运行的定时器。
3. I/O 监听：等待 socket、管道等文件描述符变为可读或可写。
4. Future 和 Task 的完成回调。

一次循环大致是：

1. 运行 ready 队列中的回调。
2. 检查定时器是否到期。
3. 根据最近的定时器和 I/O 状态决定等待多久。
4. I/O 就绪后，把相关回调放入 ready 队列。
5. 重复上述过程。

这也是为什么异步 I/O 可以节省资源：大量连接在等待网络响应时，并不需要大量线程都阻塞在那里。事件循环只要知道“哪个连接什么时候可读、哪个任务该恢复”即可。

## 25. 协程不是线程

协程和线程经常被放在一起比较，但它们的调度方式完全不同。

线程通常由操作系统抢占式调度。一个线程正在运行时，操作系统可以在某个时间片之后强行切走，换另一个线程运行。

协程是协作式调度。一个协程只有在执行到 `await` 等挂起点时，才会主动让出控制权。

这带来两个结果：

1. 协程切换成本通常比线程低。
2. 如果一个协程长时间不 `await`，它会卡住整个事件循环。

例如：

```python
async def bad():
    while True:
        pass
```

这个协程不会主动让出控制权，事件循环也就没机会运行其他任务。

如果确实有长循环，至少应该周期性让出控制权：

```python
async def better():
    while True:
        await asyncio.sleep(0)
```

不过这只是让调度有机会发生，不代表 CPU 密集型代码就适合放进事件循环。

## 26. 常见错误

### 忘记 await

```python
async def get_data():
    return "data"

async def main():
    data = get_data()
    print(data)
```

这里的 `data` 是 coroutine object，不是 `"data"`。

应该写成：

```python
data = await get_data()
```

### 在异步代码里使用阻塞调用

```python
async def main():
    time.sleep(5)
```

这会阻塞事件循环。应该改成：

```python
await asyncio.sleep(5)
```

如果是无法改造的阻塞函数，可以考虑：

```python
await asyncio.to_thread(blocking_func)
```

### 创建 Task 后不等待

```python
asyncio.create_task(do_work())
```

如果没有保存 task，也没有在合适的位置等待它，任务可能在后台失败而无人处理，或者在事件循环结束时被取消。

更稳妥的方式：

```python
task = asyncio.create_task(do_work())
await task
```

或者使用：

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(do_work())
```

### 吞掉 CancelledError

```python
try:
    await do_work()
except asyncio.CancelledError:
    pass
```

这通常是不好的。取消请求被吞掉后，上层代码可能以为任务已经正常结束。

更合理的写法：

```python
try:
    await do_work()
except asyncio.CancelledError:
    await cleanup()
    raise
```

## 27. 一个完整示例

下面是一个带并发限制、超时、取消处理的示例：

```python
import asyncio

async def fetch(url, delay):
    await asyncio.sleep(delay)
    return f"{url} ok"

async def bounded_fetch(url, delay, sem):
    async with sem:
        try:
            async with asyncio.timeout(3):
                return await fetch(url, delay)
        except TimeoutError:
            return f"{url} timeout"
        except asyncio.CancelledError:
            print(f"{url} cancelled")
            raise

async def main():
    sem = asyncio.Semaphore(2)
    jobs = [
        ("A", 1),
        ("B", 2),
        ("C", 5),
        ("D", 1),
    ]

    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(bounded_fetch(url, delay, sem))
            for url, delay in jobs
        ]

    for task in tasks:
        print(task.result())

asyncio.run(main())
```

这段代码里：

1. `Semaphore(2)` 限制最多两个任务同时执行核心逻辑。
2. `asyncio.timeout(3)` 给每个任务设置 3 秒超时。
3. `TaskGroup` 管理所有任务的生命周期。
4. `await asyncio.sleep(delay)` 模拟异步 I/O。

## 28. 总结

协程的核心不是“快”，而是“在等待时不浪费执行权”。

可以这样记：

1. `async def` 定义协程函数。
2. 调用协程函数得到 coroutine object，不会立刻执行。
3. `await` 暂停当前协程，等待另一个 awaitable 完成。
4. `asyncio.run()` 是异步程序的常见入口。
5. `create_task()` 让协程进入事件循环并发执行。
6. `gather()`、`TaskGroup` 用来组织多个任务。
7. `Future` 表示未来结果，`Task` 是被事件循环驱动的 coroutine。
8. 事件循环负责调度 ready 任务、定时器、I/O 和回调。
9. 协程是协作式调度，只有遇到 `await` 才会让出控制权。
10. 异步代码里不要随便调用阻塞函数。

如果只写一句话：

> Python 协程就是通过 `async/await` 把“等待”变成可调度的暂停点，让一个线程能高效管理大量 I/O 任务。
