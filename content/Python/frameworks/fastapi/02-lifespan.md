+++
date = '2026-09-28T00:00:00+08:00'
draft = false
title = 'FastAPI 生命周期（Lifespan）：启动、关闭与共享资源管理'
aliases = [
  '/python/fastapi-%E7%94%9F%E5%91%BD%E5%91%A8%E6%9C%9Flifespan%E5%90%AF%E5%8A%A8%E5%85%B3%E9%97%AD%E4%B8%8E%E5%85%B1%E4%BA%AB%E8%B5%84%E6%BA%90%E7%AE%A1%E7%90%86/',
]
+++

一个 Web 服务并不只有“收到请求，执行路由函数，返回响应”这一瞬间。数据库连接池、HTTP 客户端、消息消费者、机器学习模型、临时文件目录等对象，都有一段更长的生命：它们应在应用开始接流量前创建，在应用停止时有序释放。

FastAPI 的 `lifespan` 就是为这段**应用级生命周期**准备的接口。它以 `@asynccontextmanager` 把“启动”和“关闭”配成同一个结构：`yield` 前准备资源，`yield` 后清理资源。这样写并不是语法上的小花样，而是在明确资源的所有者、可用时段、失败边界和测试方式。

本文只讨论通用的 FastAPI 基础机制。若还不熟悉 Python 的异步上下文管理器，可先阅读 [Python 的 `@contextmanager` 与 `@asynccontextmanager`：用生成器管理资源、异常与取消](../../Python 的 contextmanager 与 asynccontextmanager：用生成器管理资源、异常与取消.md)；路由、依赖注入等基础可参见 [FastAPI 教程：从第一个接口到工程化服务](00-fastapi-from-basics-to-engineering.md)。

## 一、先分清三种“生命周期”

同一个服务里常见的资源存在时间并不相同。把它们都放进 `lifespan`，或都在路由里临时创建，都会造成资源浪费或状态错误。

| 范围 | 起点与终点 | 典型对象 | 合适的机制 |
| ---- | ---------- | -------- | ---------- |
| 应用级 | 服务启动到停止 | 连接池、共享 HTTP 客户端、只读模型 | `lifespan` |
| 请求级 | 单个 HTTP 请求开始到响应完成 | 数据库会话、认证上下文、临时文件 | `Depends(... yield ...)` |
| 操作级 | 某个很小的代码块 | 打开的文件、锁、临时事务 | `with` / `async with` |

例如，一个 `httpx.AsyncClient` 内部维护连接池。每个请求都新建并关闭它，虽然能工作，却失去了连接复用；把一个 ORM `Session` 放成全局单例则相反，它携带单位工作、事务和对象状态，不应被并发请求共享。前者通常适合应用级，后者通常适合请求级。

因此，判断能否放入 `lifespan` 的问题不是“它是不是昂贵”，而是：**这个对象是否可以安全地被本进程内的多个请求共享，并且是否应只初始化一次？**

## 二、`lifespan` 在服务启动和停止时做什么

FastAPI 建立在 ASGI 之上。ASGI 服务器启动应用时会协商生命周期事件；应用完成启动阶段后，服务器才开始把 HTTP 请求交给它。停止时则进入关闭阶段。FastAPI 将此能力暴露为 `FastAPI(lifespan=...)` 参数。

一段应用生命周期可以这样理解：

```text
导入模块 / 创建 app 对象
        ↓
ASGI 服务器启动应用
        ↓
执行 lifespan 中 yield 之前的代码（启动）
        ↓
开始处理多个 HTTP / WebSocket 请求
        ↓
停止接收新工作，并等待运行中的连接与应用内后台任务结束
        ↓
执行 yield 之后的代码（关闭）
        ↓
进程退出
```

这里有两个容易遗漏的边界。

- 模块顶层代码在 **import 时**执行，不等同于应用启动。把昂贵初始化写在模块顶层会让导入、命令行工具和某些测试也产生副作用。
- `lifespan` 是**每个应用进程**的生命周期，而不是整个部署集群的全局单例。使用多个 worker 时，每个 worker 都会独立创建连接池、模型和内存缓存；热重载也可能让开发时的启动日志出现多次。跨进程共享或“只能执行一次”的工作必须交给外部协调机制，而不能寄望于内存变量。

FastAPI 官方推荐使用 `lifespan` 管理这类成对的启动/关闭工作；它比把两端拆成互不相干的函数更容易保证资源的获取和释放相匹配。[FastAPI 生命周期文档](https://fastapi.tiangolo.com/advanced/events/)

## 三、`@asynccontextmanager` 与 `yield` 的精确含义

`lifespan` 的类型是一个接收 `FastAPI` 实例、返回异步上下文管理器的可调用对象。`@asynccontextmanager` 将包含一次 `yield` 的异步生成器变成这种管理器：

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("startup: prepare shared resources")
    try:
        yield
    finally:
        print("shutdown: release shared resources")


app = FastAPI(lifespan=lifespan)
```

FastAPI 会以近似下面的方式使用它，应用代码不需要也不应该自己再调用 `async with lifespan(app)`：

```python
async with lifespan(app):
    # 只有在这里的时间段内，应用才接收请求。
    await serve_requests()
```

所以：

- `yield` **之前**是启动阶段。初始化失败时，应用不应开始提供服务。
- `yield` **期间**是应用可服务的区间。
- `yield` **之后**是关闭阶段。无论服务区间因为正常停机还是异常而结束，清理逻辑都应放在 `finally` 中。

`asynccontextmanager` 生成器必须恰好 `yield` 一次。没有 `yield`，它无法进入可服务状态；`yield` 两次会违反上下文管理器协议。不要把它理解为“暂停一下再继续的普通协程”，它表达的是一对严格配对的进入/退出动作。

## 四、一个可复用的共享 HTTP 客户端示例

下面的例子创建一个应用级 `httpx.AsyncClient`，路由通过 `request.app.state` 取得它。`app.state` 是挂在应用对象上的命名空间，适合保存由应用拥有的共享对象。

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        app.state.http_client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/health/upstream")
async def check_upstream(request: Request) -> dict[str, int]:
    client: httpx.AsyncClient = request.app.state.http_client
    response = await client.get("https://example.com")
    return {"upstream_status": response.status_code}
```

这里 `async with` 同时解决了两件事：进入时建立客户端及其连接池，退出时调用异步关闭逻辑。路由并不拥有该客户端，因此路由不应调用 `await client.aclose()`；它只借用资源。所有权与关闭责任保持一致，清理顺序才不会变成猜谜游戏。

### `app.state` 与 lifespan state

上述方式直观，但 `app.state` 的属性由运行时动态添加，静态类型检查无法可靠地知道它们存在。Starlette 的 lifespan 还支持从 `yield` 返回一个字典，框架会将它作为请求的 state（请求获得的是浅拷贝）。对于希望把共享状态做成明确数据结构的应用，可以采用这种写法：

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import httpx
from fastapi import FastAPI, Request


class AppResources(TypedDict):
    http_client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[AppResources]:
    async with httpx.AsyncClient() as client:
        yield {"http_client": client}


app = FastAPI(lifespan=lifespan)


@app.get("/proxy-status")
async def proxy_status(request: Request) -> dict[str, int]:
    client = request.state.http_client
    response = await client.get("https://example.com")
    return {"status": response.status_code}
```

两种方式的关键不在“哪一种更时髦”，而在资源边界是否清楚。`app.state` 访问直接，适合小而清晰的应用；返回 state 字典可让“lifespan 输出哪些资源”更显式。无论选哪种，都应避免把可变的**请求专属状态**放进去。

## 五、多个资源：按依赖顺序创建，按相反顺序关闭

真实服务往往不只一个共享资源：日志/指标组件可能最早可用，连接池依赖配置，后台任务又依赖连接池。若手写一串 `try ... finally`，漏关一个资源并不困难。`contextlib.AsyncExitStack` 可以把已经成功获得的资源登记起来，并在退出时按 LIFO（后进先出）顺序释放。

```python
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI


class SearchClient:
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        http_client = await stack.enter_async_context(httpx.AsyncClient())

        search_client = SearchClient()
        await search_client.connect()
        stack.push_async_callback(search_client.close)

        app.state.http_client = http_client
        app.state.search_client = search_client
        yield


app = FastAPI(lifespan=lifespan)
```

如果 `connect()` 之后的某一步失败，`AsyncExitStack` 仍会关闭此前登记的 `http_client` 和 `search_client`。关闭顺序与创建顺序相反也很重要：后创建的对象往往依赖前创建的对象，先关闭依赖者才不会在释放过程中访问已失效的依赖。

对于长期运行的协程，不要在启动阶段随意 `asyncio.create_task()` 后就不再保存它。应为任务建立明确的停止信号，并在关闭阶段等待或取消它；Starlette 文档也建议用任务组管理异步任务。否则应用表面上关闭了，后台协程却可能还持有连接、吞掉异常或阻止进程退出。

## 六、失败、取消与关闭异常

生命周期代码最有价值的部分，恰好是“并非一切顺利”的时候。

### 启动失败：不要假装服务已就绪

在 `yield` 前抛出异常意味着资源未准备好。应用不应开始接收请求；运维系统可据此重启实例、告警或将其留在未就绪状态。更糟糕的做法是捕获连接失败后只记录日志、继续 `yield`，然后让所有路由在第一次实际访问资源时随机失败。

需要区分两类失败：

- **不可替代的核心依赖**：如服务没有它就无法完成关键功能，应让启动失败。
- **可降级的附加能力**：如可选的统计上报，可记录明确状态并让对应功能返回受控的降级结果；不要让一个空对象在深层代码中触发 `AttributeError`。

前文的 `AsyncExitStack` 特别适合部分启动失败的场景。资源一经取得，就立即登记清理；不要等到所有初始化成功后才想着“最后统一关闭”。

### 关闭阶段：`finally` 负责清理，但不要吞掉取消

关闭时可能发生任务取消或某个 `close()` 失败。资源释放要置于 `finally`，并让取消语义继续传播。下面的写法会错误地把取消伪装成成功：

```python
try:
    yield
except BaseException:
    # 错误：吞掉了 CancelledError 和其他关键异常。
    pass
```

更可靠的结构是只在必要时记录异常，并在 `finally` 执行清理；没有充分理由就不要抑制异常：

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    resource = await open_resource()
    try:
        yield
    finally:
        await resource.aclose()
```

关闭操作本身也可能失败。此时应记录足以定位问题的日志和指标；若多个资源都要关闭，应使用 `AsyncExitStack`，尽量让已登记的清理继续执行，而不是第一个异常就中断整个清理链。不要在关闭回调中执行没有超时限制的远程操作，否则优雅停机可能无限等待。

## 七、`lifespan`、依赖项与后台任务的分工

三者都与“开始/结束”有关，但对象不同，不能互相替代。

| 机制 | 管理的对象 | 创建次数 | 释放时机 |
| ---- | ---------- | -------- | -------- |
| `lifespan` | 应用共享资源 | 每个应用进程一次 | 应用停止时 |
| `Depends` + `yield` | 请求专属资源 | 通常每个请求一次 | 请求处理完成后 |
| `BackgroundTasks` | 响应后的短任务 | 每次需要时 | 响应发送后，由应用执行 |

以数据库为例，Engine 或异步连接池通常是应用级资源；一次请求使用的 session/transaction 则应由依赖项创建和关闭。这样会话不会在线程、协程或用户之间串用，而底层连接池仍能复用。

```python
from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_session(
    request: Request,
) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


@app.get("/documents/{document_id}")
async def read_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    return {"id": document_id}
```

请注意，`BackgroundTasks` 并不是可靠的跨进程任务队列，也不是 application lifespan 的替代品。它适合轻量、与当前响应相关的后续工作；需要重试、持久化、独立扩缩容或跨进程协调的工作，应使用专门的队列和 worker。

## 八、旧式 `@app.on_event` 与挂载子应用

过去常见如下写法：

```python
@app.on_event("startup")
async def startup() -> None:
    await prepare_resources()


@app.on_event("shutdown")
async def shutdown() -> None:
    await release_resources()
```

FastAPI 已将这组事件处理器标为替代方案，推荐新代码改用 `lifespan`。尤其不要把两种机制混搭：当 `FastAPI(lifespan=...)` 被提供时，`startup` 和 `shutdown` 事件处理器不会再被调用。`lifespan` 让启动与关闭逻辑在同一作用域中配对，资源不必借助模块全局变量在两个函数之间传递。

另一个常见误解是：主应用把另一个 FastAPI/Starlette 应用 `mount()` 到路径后，子应用也会自动执行自己的 lifespan。FastAPI 文档明确说明，挂载的 sub-application 不会自动执行其各自的启动/关闭事件。需要子应用资源时，应在主应用生命周期统一编排，或为子应用采用明确、经测试的启动策略。不要只因为本地访问过一次路由就假定它的初始化发生过。

## 九、如何测试生命周期

生命周期没有经过测试，通常只会在部署时才暴露“启动没跑”“资源未关”“测试环境连到了真实外部服务”之类的问题。同步测试中，`TestClient` 必须作为上下文管理器使用，才能确保进入和退出 lifespan。

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

events: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    events.append("startup")
    app.state.answer = 42
    try:
        yield
    finally:
        events.append("shutdown")


app = FastAPI(lifespan=lifespan)


@app.get("/answer")
async def answer() -> dict[str, int]:
    return {"answer": app.state.answer}


def test_lifespan_runs_in_order() -> None:
    assert events == []

    with TestClient(app) as client:
        assert events == ["startup"]
        response = client.get("/answer")
        assert response.status_code == 200
        assert response.json() == {"answer": 42}

    assert events == ["startup", "shutdown"]
```

测试时尤其要覆盖以下场景：

- 启动成功后，路由确实能取得共享资源；
- 启动失败时，不会进入“看似成功、实际不可用”的状态；
- 即使路由抛出异常，退出 `TestClient` 后清理逻辑仍会执行；
- 外部依赖使用测试替身或隔离配置，绝不连接真实生产服务；
- 多次创建测试应用时，状态没有通过模块全局变量泄漏到下一项测试。

使用异步测试客户端时，同样要选择会驱动 ASGI lifespan 的测试方式。最稳妥的原则不是记住某个客户端的默认行为，而是明确断言启动和关闭产生的可观察效果。

## 十、设计检查表

为一个新资源决定放置位置前，可以逐项检查：

- 它是全应用共享，还是一次请求独占？
- 它是否支持并发使用，是否与事件循环、线程或进程绑定？
- 初始化失败时，服务应拒绝启动还是允许受控降级？
- 谁拥有资源，谁负责关闭？关闭是否位于 `finally` 或上下文管理器中？
- 多 worker 部署时，每个进程重复初始化是否安全？
- 它的停止信号、超时和异常记录是否明确？
- 测试是否实际走过启动与关闭，而不是只调用了路由函数？

## 十一、总结

FastAPI 的 `lifespan` 解决的不是“开机时执行一段代码”这么狭窄的问题，而是把应用级资源的完整边界写进程序结构。

- 用 `FastAPI(lifespan=...)` 和 `@asynccontextmanager` 管理启动到关闭之间共享的资源。
- `yield` 前初始化，`yield` 后释放；清理应放在 `finally` 或可靠的异步上下文管理器中。
- 每个 worker 都有自己的生命周期，内存中的资源并非部署级单例。
- 共享客户端、连接池和只读模型适合应用级；数据库 session 等请求专属对象应交给 `Depends(... yield ...)`。
- 多资源初始化使用 `AsyncExitStack`，让部分启动失败和反向关闭顺序可控。
- 使用 `TestClient` 的上下文管理器验证生命周期；新代码优先选用 `lifespan`，不要与旧式事件处理器混用。

当资源的归属、初始化失败和关闭路径都能被清楚回答时，生命周期代码才算完成。否则即使服务能跑起来，也只是在把问题推迟到最不方便排查的停机或发布时刻而已。
