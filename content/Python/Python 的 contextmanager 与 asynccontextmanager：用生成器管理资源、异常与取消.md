+++
date = '2026-09-28T00:10:00+08:00'
draft = false
title = 'Python 的 @contextmanager 与 @asynccontextmanager：用生成器管理资源、异常与取消'
+++

文件、锁、数据库事务、网络客户端、临时目录这些对象有一个共同点：它们不能只在“正常执行完”时收尾。业务代码抛异常、函数提前 `return`、异步任务被取消时，资源仍然必须释放，事务仍然必须回滚，连接仍然必须归还给连接池。把清理代码散落在每个分支中并不会显得严谨，只会让遗漏成为迟早的事。

Python 的 `with` 与 `async with` 用上下文管理器（context manager）把这段生命周期固定为“进入、使用、退出”。`contextlib.contextmanager` 与 `contextlib.asynccontextmanager` 则进一步让你用一个生成器，把这三段逻辑按自然的顺序写在同一个函数里。

先给结论：

- `@contextmanager` 把**同步生成器函数**转换成可用于 `with` 的上下文管理器工厂。
- `@asynccontextmanager` 把**异步生成器函数**转换成可用于 `async with` 的上下文管理器工厂。
- `yield` 前是进入阶段，`yield` 交出的值绑定给 `as` 后的变量，`yield` 后是退出阶段。
- 无论 `with` 块正常结束还是抛出异常，退出阶段都有机会执行；把真正的清理放在 `finally` 中。
- 异步场景还必须正确对待任务取消：清理可以 `await`，但不能为了“安静”而吞掉 `CancelledError`。

这篇文章聚焦生成器式上下文管理器。若你还不熟悉普通 `with`、`__enter__` 和 `__exit__` 的基础用法，可先阅读 [Python 的 `with` 语句](python_with_feature.md)；异步调度与取消的基础可参见 [Python 协程](python_coroutine.md)。

## 一、上下文管理器究竟解决了什么问题

不使用上下文管理器时，打开和关闭资源通常会写成这样：

```python
file = open("settings.json", encoding="utf-8")
try:
    content = file.read()
finally:
    file.close()
```

这段代码并没有错。`finally` 让 `file.close()` 在读取失败、函数提前返回等情况下仍会执行。但当资源初始化、业务代码、提交/回滚、日志和清理都逐渐复杂时，每个调用点重复这套样板就不再合适。

上下文管理器把约定抽象为：

```text
进入上下文：申请资源、建立状态、开始计时或事务
       │
       ├── 执行 with / async with 块中的业务代码
       │
退出上下文：释放资源、提交或回滚、记录结果
```

例如文件对象本身实现了同步上下文管理器协议：

```python
with open("settings.json", encoding="utf-8") as file:
    content = file.read()
```

即使 `file.read()` 抛出异常，文件仍会关闭。`with` 管理的是资源生命周期，不会创建新的 Python 作用域；`content` 离开缩进块后依然可用这一点，详见 [with as 与作用域](python_with_statement_and_scope.md)。

## 二、先理解协议：`with` 与 `async with` 实际调用了什么

`@contextmanager` 是对协议的简化写法。先看协议本身，之后就不会把装饰器当成某种不可解释的特殊语法。

### 同步协议：`__enter__` 与 `__exit__`

一个同步上下文管理器需要提供 `__enter__` 和 `__exit__`：

```python
class ManagedResource:
    def __enter__(self) -> "ManagedResource":
        print("acquire")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        print("release")

        # 返回 False 或 None：异常（如果有）继续向外传播。
        return False


with ManagedResource() as resource:
    print("use resource")
```

输出顺序为：

```text
acquire
use resource
release
```

若块内抛出异常，`__exit__` 仍会被调用，并接收到异常类型、异常对象和 traceback。`__exit__` 返回真值时会**抑制异常**；返回假值或 `None` 时，异常会继续传播。除非你明确设计了可恢复的异常策略，否则不要随意返回真值。把错误悄悄吞掉不叫容错，只是让定位变得更晚一些。

概念上，下面两段代码的生命周期相近：

```python
with manager as value:
    use(value)
```

```python
value = manager.__enter__()
try:
    use(value)
except BaseException as error:
    should_suppress = manager.__exit__(type(error), error, error.__traceback__)
    if not should_suppress:
        raise
else:
    manager.__exit__(None, None, None)
```

这是帮助理解的伪展开，不应在业务代码里手动调用这两个魔术方法。Python 对异常链、traceback 和边界情况有更精确的处理；交给 `with` 才是正确选择。

### 异步协议：`__aenter__` 与 `__aexit__`

异步资源的进入和退出本身也可能需要 I/O，例如建立连接、归还连接、关闭 HTTP 客户端。因此异步上下文管理器使用可等待的 `__aenter__` 和 `__aexit__`：

```python
class AsyncManagedResource:
    async def __aenter__(self) -> "AsyncManagedResource":
        print("acquire asynchronously")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        print("release asynchronously")
        return False


async def main() -> None:
    async with AsyncManagedResource() as resource:
        print("use resource")
```

`async with` 会等待进入和退出操作完成。它不是在 `with` 前面随意加一个 `async`：同步管理器不能放进 `async with`，异步管理器也不能放进普通 `with`。

| 使用场景 | 所需协议 | 语法 | 典型对象 |
| --- | --- | --- | --- |
| 同步资源 | `__enter__` / `__exit__` | `with` | 文件对象、`threading.Lock` |
| 异步资源 | `__aenter__` / `__aexit__` | `async with` | 异步 HTTP 响应、异步数据库连接、`asyncio.Lock` |

## 三、`@contextmanager`：把一个生成器变成同步上下文管理器

`contextlib.contextmanager` 适合资源逻辑能清晰写成“前置处理 → 交出资源 → 后置处理”的场景。最小示例如下：

```python
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def managed_message(name: str) -> Iterator[str]:
    print(f"enter: {name}")
    try:
        yield f"resource for {name}"
    finally:
        print(f"exit: {name}")


with managed_message("report") as resource:
    print(resource)
```

输出：

```text
enter: report
resource for report
exit: report
```

这里的函数和普通函数有一个关键区别：它含有 `yield`，所以调用 `managed_message("report")` 时不会立即从头执行到尾，而是创建生成器。装饰器把这个生成器包装为上下文管理器对象；真正进入 `with` 时，生成器才开始运行。

执行过程可以按下面理解：

```text
调用 managed_message("report")
    -> 得到一个上下文管理器对象

进入 with
    -> 运行生成器，直到第一个 yield
    -> yield 的值绑定给 as resource

执行 with 块

退出 with
    -> 恢复生成器执行
    -> 正常退出，或把块内异常注入 yield 位置
    -> finally 中的清理逻辑执行
```

`yield` 不是返回值的替代品，而是**生命周期的分界线**。其前面适合做获取与初始化，其后面适合做收尾；`yield value` 中的 `value` 才会赋给 `as` 后面的变量。

### 为什么 `finally` 必不可少

若只把清理代码放在 `yield` 后面，却没有 `finally`：

```python
@contextmanager
def fragile_resource() -> Iterator[None]:
    print("acquire")
    yield
    print("release")
```

当块内正常结束时，`release` 会执行；但当块内异常被重新抛入生成器时，生成器会在 `yield` 处收到异常，后面的普通语句可能被跳过。应该这样写：

```python
@contextmanager
def safe_resource() -> Iterator[None]:
    print("acquire")
    try:
        yield
    finally:
        print("release")
```

这与手写 `try ... finally` 的原则完全相同。`@contextmanager` 减少样板，不会取消异常控制流的基本规律。

### 一个可用的计时器

对于不需要交出资源、只需要在边界处做工作的场景，可以 `yield None`：

```python
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


@contextmanager
def measure(operation: str) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    finally:
        elapsed = perf_counter() - started_at
        print(f"{operation} took {elapsed:.3f}s")


with measure("generate report"):
    # 执行实际工作；即使这里失败，耗时仍会被记录。
    pass
```

它适合简单的埋点、临时状态切换和资源包装。不要为了把每一个 `try ... finally` 都变得“优雅”而层层包裹：资源边界若被抽象到难以看见，调试时只会多绕一圈。

## 四、异常怎样从 `with` 块回到生成器

生成器式上下文管理器最重要的地方在于：块内异常并不会绕过生成器。对 `@contextmanager` 而言，异常会在暂停的 `yield` 处被重新抛入；这使生成器可以回滚、转换或在极少数情况下抑制异常。

### 记录后继续抛出：最常见也最安全

```python
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def audit_operation(name: str) -> Iterator[None]:
    print(f"start: {name}")
    try:
        yield
    except Exception as error:
        print(f"failed: {name}; {error!r}")
        raise
    finally:
        print(f"finish: {name}")


with audit_operation("import"):
    raise ValueError("invalid input")
```

`raise` 没有携带新参数，会重新抛出原异常并保留 traceback。`finally` 仍会执行。这种“记录，但不改变原有失败语义”的做法，是日志、指标和多数通用资源包装器的合理默认值。

### 转换异常：保留原因链

如果当前抽象层确实需要向调用方暴露更稳定的领域异常，可以使用 `raise ... from error`：

```python
class ConfigurationError(RuntimeError):
    pass


@contextmanager
def loading_config() -> Iterator[None]:
    try:
        yield
    except OSError as error:
        raise ConfigurationError("配置文件无法读取") from error


with loading_config():
    open("missing-settings.json", encoding="utf-8").read()
```

调用方看到的是 `ConfigurationError`，但异常链中仍保留原始的 `FileNotFoundError` 或其他 `OSError`。这比直接丢弃原始错误信息可靠得多。

### 结束生成器会抑制异常，因而必须格外谨慎

下面的写法会吞掉 `KeyError`：

```python
@contextmanager
def ignore_absent_key() -> Iterator[None]:
    try:
        yield
    except KeyError:
        # 生成器正常结束，contextmanager 因而视为该异常已处理。
        pass


with ignore_absent_key():
    {}["missing"]

print("程序继续执行")
```

这种行为有时是有意的，例如“删除一个不存在的可选键”确实无害；但它的范围必须非常窄，而且函数名应明确表达抑制的异常。绝不能写成：

```python
# 错误示例：任何普通异常都会被悄悄隐藏。
@contextmanager
def dangerous_wrapper() -> Iterator[None]:
    try:
        yield
    except Exception:
        pass
```

更不应捕获 `BaseException` 并忽略它，那会连 `KeyboardInterrupt`、`SystemExit` 和异步取消相关的控制流都吞掉。若使用 `except BaseException` 是为了先回滚再重新抛出，必须紧跟 `raise`，后文会给出这种事务边界的例子。

## 五、生成器式上下文管理器的约束与类型标注

### 必须且只能 `yield` 一次

一个上下文管理器只有一次进入和一次退出，因此被装饰的生成器必须**恰好 `yield` 一次**。

没有 `yield`：

```python
@contextmanager
def invalid_manager() -> Iterator[None]:
    print("no yield")
```

它不是合格的生成器式上下文管理器，进入时会失败。

有两次 `yield`：

```python
# 错误示例：退出时生成器还会产出第二个值。
@contextmanager
def invalid_manager() -> Iterator[str]:
    yield "first"
    yield "second"
```

块退出时，`contextmanager` 期待生成器结束；第二次 `yield` 会导致运行时错误。若需求本身是“持续产出多个值”，应使用普通生成器或异步迭代器，而不是上下文管理器。

### 推荐使用 `Iterator[T]` 与 `AsyncIterator[T]`

同步生成器式上下文管理器通常标注为 `Iterator[T]`，异步版本通常标注为 `AsyncIterator[T]`；`T` 是 `as` 后得到的资源类型：

```python
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager


@contextmanager
def one_number() -> Iterator[int]:
    yield 1


@asynccontextmanager
async def one_text() -> AsyncIterator[str]:
    yield "ready"
```

这里的返回标注描述的是装饰前的生成器函数。装饰后，`one_number()` 和 `one_text()` 返回的是上下文管理器对象，不是裸 `Iterator[int]` 或 `AsyncIterator[str]`；类型检查器通常了解 `contextlib` 的装饰器签名，可以推断 `with` 块内变量的类型。

### 每次使用都应调用工厂函数

装饰后的函数是**上下文管理器工厂**。通常应每次使用时重新调用：

```python
with managed_message("first") as first:
    print(first)

with managed_message("second") as second:
    print(second)
```

不要把一次调用所得的管理器对象保存后重复进入：

```python
manager = managed_message("only once")

with manager:
    pass

# 错误：底层生成器已经结束，不能再次作为新的上下文进入。
with manager:
    pass
```

生成器实例本质上是一次性的。若希望同一套配置可多次使用，就保存参数或封装工厂函数，而不是复用已经消费的生成器对象。

## 六、事务边界：提交、回滚和原始异常

事务是 `@contextmanager` 的典型适用场景，因为它的生命周期天然具有三段式结构：开始事务、执行一组操作、根据结果提交或回滚。下面用一个抽象连接接口说明控制流：

```python
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class Transaction(Protocol):
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class Connection(Protocol):
    def begin(self) -> Transaction: ...


@contextmanager
def transaction(connection: Connection) -> Iterator[Connection]:
    tx = connection.begin()
    try:
        yield connection
    except BaseException:
        # 包括取消或中断在内的所有非正常退出都应回滚，随后原样继续传播。
        tx.rollback()
        raise
    else:
        tx.commit()
```

使用时，事务边界非常直观：

```python
with transaction(connection) as conn:
    create_order(conn)
    reserve_inventory(conn)
```

如果 `reserve_inventory` 失败，`tx.rollback()` 执行，原异常继续向上；两步都正常完成时才 `commit()`。这个例子使用 `except BaseException` 是有意的：它不是要忽略控制流异常，而是为了回滚后立即 `raise`。不要把这种受控用法误读为“以后所有异常处理都该捕获 `BaseException`”。

现实中还要确认数据库库自身的事务语义：有的连接对象自带事务上下文管理器，有的 ORM 的 `Session` 已经处理提交、回滚与关闭。优先使用库提供的成熟接口；自定义包装器应只补上项目真实缺失的边界。有关 SQLAlchemy 的事务与 `Session`，可参见 [SQLAlchemy 2.x 入门](frameworks/sqlalchemy/00-introduction.md)。

## 七、`@asynccontextmanager`：异步版本改变了什么

`contextlib.asynccontextmanager` 的结构和同步版本几乎一致，差异在于函数是 `async def`、返回的是**异步生成器**，并且进入与退出期间可以 `await`：

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def managed_connection() -> AsyncIterator["AsyncConnection"]:
    connection = await open_connection()
    try:
        yield connection
    finally:
        await connection.close()


async def load_user() -> None:
    async with managed_connection() as connection:
        user = await connection.fetch_user(1)
        print(user)
```

流程只是把同步的 `next()`／恢复执行替换为异步生成器的推进与等待：

```text
调用 managed_connection()
    -> 得到异步上下文管理器对象

进入 async with
    -> 等待异步生成器运行到第一个 yield
    -> yield 的 connection 绑定给 as connection

执行 async with 块

退出 async with
    -> 等待异步生成器继续运行或接收块内异常
    -> await finally 中的 close()
```

关键点在于：`asynccontextmanager` **不会把同步阻塞操作变成异步操作**。若 `open_connection()` 内部调用阻塞网络库、`time.sleep()` 或长时间 CPU 计算，事件循环照样会被阻塞。只有底层 API 真正是异步的、会在 I/O 等待时让出事件循环时，`await` 才有其应有的意义。

### 一个可运行的异步资源示例

下面不用第三方库，借助 `asyncio.sleep(0)` 模拟可等待的打开与关闭过程：

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class FakeAsyncConnection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    async def query(self, sql: str) -> str:
        if self.closed:
            raise RuntimeError("connection is closed")
        await asyncio.sleep(0)
        return f"{self.name}: {sql}"

    async def close(self) -> None:
        await asyncio.sleep(0)
        self.closed = True
        print(f"closed: {self.name}")


@asynccontextmanager
async def open_fake_connection(name: str) -> AsyncIterator[FakeAsyncConnection]:
    await asyncio.sleep(0)
    connection = FakeAsyncConnection(name)
    print(f"opened: {name}")
    try:
        yield connection
    finally:
        await connection.close()


async def main() -> None:
    async with open_fake_connection("primary") as connection:
        result = await connection.query("SELECT 1")
        print(result)


asyncio.run(main())
```

输出顺序是：

```text
opened: primary
primary: SELECT 1
closed: primary
```

注意最后一行 `await connection.close()` 在 `finally` 中。若 `query()` 失败，连接仍然会进入关闭流程；把它放在 `yield` 之后的普通语句中并不足够。

## 八、异步取消不是普通错误：清理后必须继续传播

异步任务可能因为超时、`TaskGroup` 中的兄弟任务失败、应用关闭或调用方主动取消而收到取消请求。取消会在协程的可等待点表现为 `asyncio.CancelledError`。`async with` 退出时，这个异常也会回到 `yield` 所在位置，因此 `finally` 仍是可靠的清理位置：

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def cancellable_resource() -> AsyncIterator[None]:
    print("acquire")
    try:
        yield
    finally:
        # 这里可 await：例如归还异步连接、停止后台资源等。
        await asyncio.sleep(0)
        print("release")


async def worker() -> None:
    async with cancellable_resource():
        await asyncio.sleep(60)


async def main() -> None:
    task = asyncio.create_task(worker())
    await asyncio.sleep(0)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        print("task was cancelled")


asyncio.run(main())
```

预期顺序是资源释放后，取消继续向等待任务的调用方传播：

```text
acquire
release
task was cancelled
```

这是正确行为。不要这样写：

```python
# 错误示例：可能破坏超时、TaskGroup 和应用关闭的取消语义。
@asynccontextmanager
async def swallow_everything() -> AsyncIterator[None]:
    try:
        yield
    except BaseException:
        pass
```

如果确实需要在取消时做额外记录或补偿，可以显式处理后重新抛出：

```python
@asynccontextmanager
async def log_cancellation() -> AsyncIterator[None]:
    try:
        yield
    except asyncio.CancelledError:
        print("operation cancelled; cleanup is complete")
        raise
```

大多数情况下甚至不需要 `except asyncio.CancelledError`；`finally` 已足以清理。只有需要额外的取消专属行为时才捕获它，并且默认应重新抛出。取消是协作式并发的控制信号，不是可以随手压平的日志噪声。

## 九、异步事务与 FastAPI 生命周期的两类实践

### 异步事务：等待回滚或提交

异步数据库驱动的事务操作通常也需要等待。下面仍使用抽象协议，强调控制流而非特定库 API：

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol


class AsyncTransaction(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class AsyncConnection(Protocol):
    async def begin(self) -> AsyncTransaction: ...


@asynccontextmanager
async def async_transaction(connection: AsyncConnection) -> AsyncIterator[AsyncConnection]:
    tx = await connection.begin()
    try:
        yield connection
    except BaseException:
        await tx.rollback()
        raise
    else:
        await tx.commit()
```

对于 SQLAlchemy 的异步 `Session`，更常见也更稳妥的是使用其原生的 `async with session.begin():` 事务上下文，而不是再包一层几乎等价的工具函数。框架已经为它的对象生命周期定义了契约时，自己重写一遍往往只会制造微妙差异。

### FastAPI `lifespan`：应用启动到关闭的一段长上下文

`@asynccontextmanager` 还适合定义应用生命周期。FastAPI 的 `lifespan` 参数接收的正是这样的异步上下文管理器函数：

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = httpx.AsyncClient(timeout=10)
    app.state.http_client = client
    try:
        # yield 前：应用启动完成，可以开始接收请求。
        yield
    finally:
        # yield 后：应用关闭，释放共享资源。
        await client.aclose()


app = FastAPI(lifespan=lifespan)
```

它的边界不是“一次请求”，而是“应用启动到停止”。因此适合创建需要跨请求复用的 HTTP 客户端、连接池、模型或后台资源；不适合为每个请求创建独立事务或临时文件。资源的生命周期应匹配业务所有权：谁创建资源，谁负责关闭；创建多久，清理边界就应覆盖多久。这个原则比记住装饰器名字重要得多。

项目中已有 FastAPI 生命周期的入门示例，可结合 [FastAPI 从基础到工程实践](frameworks/fastapi/00-fastapi-from-basics-to-engineering.md) 阅读。

## 十、何时不用它：已有管理器、动态资源与复杂状态机

`@contextmanager` 和 `@asynccontextmanager` 很方便，但不是所有资源都应该再包一层。

### 优先使用第三方库原生上下文管理器

如果库已经提供：

```python
async with client.stream("GET", url) as response:
    ...
```

或：

```python
with Session(engine) as session:
    ...
```

就优先使用它。原生实现通常知道连接池、事务嵌套、错误处理和版本兼容的细节。自定义包装器只应负责项目的额外横切需求，例如统一审计字段、固定的领域异常转换或特定指标。

### 资源数量在运行时决定时，使用 `ExitStack`

生成器式管理器很适合单个资源或固定的一小组资源。若文件、锁或其他资源的数量由配置决定，手工嵌套许多 `with` 不够清楚，应考虑 `contextlib.ExitStack`；异步版本使用 `AsyncExitStack`。

```python
from contextlib import ExitStack
from pathlib import Path


paths = [Path("a.txt"), Path("b.txt")]

with ExitStack() as stack:
    files = [stack.enter_context(path.open(encoding="utf-8")) for path in paths]
    contents = [file.read() for file in files]
```

它会按进入的反序自动退出所有资源，即使中途打开某个文件失败也会正确清理已经打开的文件。有关 `ExitStack` 与其他 `contextlib` 工具，可回看前述 `with` 文章。

### 需要多阶段、可重入或复杂状态时，显式类更清楚

生成器式写法最擅长一次进入、一次退出的线性流程。若资源需要多次进入、支持复杂配置、暴露多个状态、与继承体系深度结合，显式实现 `__enter__` / `__exit__` 或 `__aenter__` / `__aexit__` 的类通常更清晰。不要为了少写一个类名，把一个状态机塞进 `yield` 前后的两段代码里。

## 十一、常见误用检查表

| 现象 | 原因 | 正确做法 |
| --- | --- | --- |
| 清理只在成功时执行 | `yield` 后没有 `finally` | 把关闭、释放、回滚放进 `finally` |
| 块内错误突然消失 | 捕获后没有重新抛出 | 只抑制明确且无害的异常；默认 `raise` |
| `async with` 报协议错误 | 传入同步上下文管理器 | 改用 `with`，或使用真正的异步资源接口 |
| 事件循环仍被卡住 | 管理器内调用了阻塞函数 | 使用异步 I/O 库，或把阻塞工作移出事件循环 |
| 任务取消后继续“假装成功” | 吞掉了 `CancelledError` | 在 `finally` 清理；若捕获取消则立即重新抛出 |
| 退出时报“generator didn't stop” | 函数 `yield` 了多次 | 一个上下文管理器只保留一个 `yield` |
| 再次使用同一管理器对象失败 | 复用了已经结束的生成器实例 | 每次 `with` / `async with` 都重新调用工厂函数 |
| 连接频繁创建和关闭 | 生命周期边界选错 | 请求级与应用级资源分别管理，避免混用 |

## 十二、总结

`@contextmanager` 和 `@asynccontextmanager` 的价值不在于把 `try ... finally` 隐藏起来，而在于把资源的获取、交付与清理组织成一个明确、可复用且异常安全的边界。

- 同步资源使用 `@contextmanager` 与 `with`；异步资源使用 `@asynccontextmanager` 与 `async with`。
- `yield` 前做初始化，`yield` 交出 `as` 变量，`yield` 后进入退出阶段；真正的清理应始终置于 `finally`。
- 块内异常会回到 `yield` 所在位置。记录后重抛是默认选择；异常转换要用 `raise ... from ...` 保留原因链；抑制异常必须是明确而狭窄的业务决定。
- 异步取消同样会触发退出路径。清理可以等待，但取消通常必须继续传播。
- 一次调用得到的生成器式管理器通常只能进入一次；每次使用都重新调用工厂函数。
- 优先采用库已提供的上下文管理器；动态资源使用 `ExitStack`，复杂多状态资源则使用显式类。

当你写下一个 `yield` 时，最好能明确回答：进入前我获得了什么，交给块内代码的是什么，退出时无论成功、失败还是取消，我要负责恢复什么状态。能回答清楚这些问题，才说明上下文边界真的被设计好了，而不是只是在代码里摆放了一个看起来很整齐的装饰器。
