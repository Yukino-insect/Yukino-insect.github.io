+++
date = '2026-09-28T00:00:00+08:00'
draft = false
title = 'FastAPI 中间件：ASGI 请求链、使用边界与工程实践'
aliases = [
  '/python/fastapi-%E4%B8%AD%E9%97%B4%E4%BB%B6asgi-%E8%AF%B7%E6%B1%82%E9%93%BE%E4%BD%BF%E7%94%A8%E8%BE%B9%E7%95%8C%E4%B8%8E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E8%B7%B5/',
]
+++

中间件（middleware）常被概括为“在路由前后执行的代码”。这句话不算错，却不足以指导实际设计：它没有解释中间件为何能处理每个请求、多个中间件为何像洋葱一样嵌套、为什么认证有时不该放在中间件里，也没有说明流式响应和 `BaseHTTPMiddleware` 的陷阱。

本文的核心结论是：**FastAPI 中间件是包裹 ASGI 应用的通用协议层。**它适合请求 ID、CORS、访问日志、安全响应头、压缩、可信 Host 等与具体业务资源无关的横切规则；而当前用户、具体对象的权限、参数校验和数据库会话等需要路由语义的工作，通常应该使用依赖注入或路由本身。不要因为中间件“无处不在”，就让它承担一切。那只会让边界变得含混。

本文默认读者已会编写基本的 FastAPI 路由。路由、请求参数和 `APIRouter` 的基础可先参考 [FastAPI：从基础到工程化](00-fastapi-from-basics-to-engineering.md)；本文只讨论中间件这一层。

## 一、先建立正确模型：FastAPI 是一个 ASGI 应用

Uvicorn 之类的 ASGI 服务器接收网络连接后，不会直接调用 `@app.get()` 标记的函数。它会把一次连接表示为三样东西，交给 FastAPI（底层是 Starlette）这个 ASGI 可调用对象：

- `scope`：连接的元数据字典，例如类型、方法、路径、请求头、客户端地址；
- `receive`：异步函数，用于逐条读取输入事件，例如请求体分块或断连通知；
- `send`：异步函数，用于逐条发送输出事件，例如响应头和响应体分块。

一个最小 ASGI 应用就是如下形状：

```python
async def app(scope, receive, send):
    if scope["type"] != "http":
        return

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"hello",
            "more_body": False,
        }
    )
```

中间件同样是 ASGI 应用，只是它持有另一个 ASGI 应用，并在调用它之前、之后，或包装 `receive`、`send` 时加入行为。结构可以理解成：

```text
ASGI server
  -> 外层中间件
      -> 内层中间件
          -> FastAPI 路由匹配、依赖解析、端点函数
          <- 生成响应
      <- 处理响应
  <- 返回给客户端
```

所以中间件并不知道、也不应假装知道“订单是否属于当前用户”这类领域事实。它首先面对的是 HTTP/ASGI 连接，路由甚至可能尚未匹配成功。

### HTTP 以外的连接也可能经过 ASGI

ASGI 的 `scope["type"]` 不只有 `"http"`，常见还有 `"websocket"` 和 `"lifespan"`。`@app.middleware("http")` 与 `BaseHTTPMiddleware` 只覆盖 HTTP；需要同时处理 WebSocket，或需要直接观察事件流时，应编写纯 ASGI 中间件，并显式判断 `scope["type"]`。

## 二、最常用的写法：`@app.middleware("http")`

FastAPI 提供的装饰器把一个接受 `Request` 和 `call_next` 的异步函数登记为 HTTP 中间件。`call_next(request)` 会把控制权交给后续中间件、路由、依赖和端点，并返回生成的 `Response`。

```python
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1_000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response
```

这段代码有两个阶段：

1. `await call_next(...)` **之前**：可读取请求头、建立每请求上下文、快速拒绝请求，或记录开始时间；
2. `await call_next(...)` **之后**：可读取状态码、补充响应头、记录耗时，然后必须返回响应。

`time.perf_counter()` 是单调递增的高精度计时器，适合测量耗时；不要用可被系统校时影响的 `time.time()` 来做延迟统计。

### `call_next` 不是“调用当前路由函数”

将 `call_next` 理解成“直接执行端点”很容易误导。它实际上是把请求传给**中间件栈的下一层应用**：后续中间件、异常处理、路由匹配、依赖注入、响应序列化都在其中。因而：

- 不调用它并自行返回 `Response`，就是短路请求；
- 调用两次会让后续应用处理两次同一请求，几乎总是错误；
- 在它之前读取并消耗请求体，若没有正确重放给后续层，会使路由拿不到请求体。

例如，一个维护窗口可以有意短路：

```python
from fastapi import Request
from fastapi.responses import JSONResponse


@app.middleware("http")
async def maintenance_mode(request: Request, call_next):
    if request.url.path != "/health" and is_maintenance_enabled():
        return JSONResponse(
            status_code=503,
            content={"detail": "service is temporarily unavailable"},
            headers={"Retry-After": "120"},
        )

    return await call_next(request)
```

短路应只用于明确、通用且廉价的入口规则，例如维护、网关已验证的签名格式或全局限流。它不应悄悄替代资源权限判断。

## 三、一个可直接理解的实践：请求 ID、日志和安全头

下面的示例将三类常见横切工作放在同一处：为每个请求建立关联 ID、记录访问日志、添加不依赖业务内容的安全响应头。

```python
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request

logger = logging.getLogger("api.access")
app = FastAPI()


@app.middleware("http")
async def observability_and_security(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # 记录上下文后继续抛出，让既有异常处理器统一生成错误响应。
        logger.exception(
            "unhandled request error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1_000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"

    logger.info(
        "request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/reports/{report_id}")
async def get_report(report_id: int, request: Request):
    return {"report_id": report_id, "request_id": request.state.request_id}
```

这里的 `request.state` 是当前请求携带的临时状态容器，适合让下游依赖和端点取得已经生成的请求 ID。不要把请求 ID 写到中间件实例的 `self.current_request_id` 上：一个实例会并发服务许多请求，这样会发生串号和数据竞争。

如果日志系统使用 `ContextVar` 自动给所有日志加请求 ID，也要留意后文的 `BaseHTTPMiddleware` 限制；中间件位置会影响上下文是否能向外层传播。

### 安全头不是一份到处复制的清单

`X-Content-Type-Options: nosniff` 对 API 通常合理，`Referrer-Policy` 也相对保守；但 `Content-Security-Policy`、`Strict-Transport-Security`、`Permissions-Policy` 都要根据是否服务 HTML、是否由反向代理终止 TLS、是否嵌入第三方资源来确定。中间件适合实施**已经决定好的统一策略**，不适合替代安全设计。

## 四、多个中间件的顺序：后添加者先处理请求

`app.add_middleware()` 或 `@app.middleware()` 每增加一个中间件，都会把已有应用包在里面。最后添加的中间件位于最外层，因此：

```python
app.add_middleware(FirstMiddleware)
app.add_middleware(SecondMiddleware)
```

实际顺序是：

```text
请求：SecondMiddleware -> FirstMiddleware -> 路由
响应：路由 -> FirstMiddleware -> SecondMiddleware
```

可用下面的日志验证这个洋葱模型：

```python
from starlette.middleware.base import BaseHTTPMiddleware


class NamedMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, name: str):
        super().__init__(app)
        self.name = name

    async def dispatch(self, request, call_next):
        print(f"{self.name}: in")
        response = await call_next(request)
        print(f"{self.name}: out")
        return response


app.add_middleware(NamedMiddleware, name="A")
app.add_middleware(NamedMiddleware, name="B")
```

一次命中路由的请求会输出 `B: in`、`A: in`、`A: out`、`B: out`。顺序应当是设计的一部分：例如，最外层的请求 ID/追踪层希望覆盖后续所有操作；CORS 则要能给相应的响应附加头；而对 `Host` 的过滤通常应尽早完成。

还应记住 Starlette 自身有错误处理相关的外层和内层保护层。不要手动用 `SomeMiddleware(app)` 覆盖 FastAPI 实例再胡乱导出，优先使用 `app.add_middleware()`，让框架维持异常处理栈。只有确实需要 CORS 覆盖未处理异常生成的 500 响应时，才需要按 Starlette 的“全局包裹”方式审慎调整应用导出结构并做集成测试。

## 五、CORS：浏览器的跨域许可，不是访问控制

浏览器中的网页从 `https://console.example.com` 调用 `https://api.example.com` 时，二者的协议、主机或端口不同，浏览器会执行同源策略和 CORS 检查。`CORSMiddleware` 负责根据配置响应预检 `OPTIONS` 请求，并为实际跨域响应添加许可头。

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://console.example.com",
        "https://admin.example.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    max_age=600,
)
```

几个容易混淆的点：

- `Origin` 是“协议 + 主机 + 端口”，路径不是 Origin 的一部分；
- 带 `Origin`、`Access-Control-Request-Method` 的预检 `OPTIONS` 会被 CORS 中间件拦截并回答，不必给每个业务路由手写 `OPTIONS`；
- 若 `allow_credentials=True`，来源、方法和请求头不能偷懒写成 `*`，应列出明确值；
- 自定义响应头即使已经发给浏览器，前端 JavaScript 也只有在 `expose_headers` 中列出后才可读取；
- CORS 只限制浏览器是否允许网页脚本读取响应。`curl`、移动端和攻击者都可以直接发送 HTTP 请求，认证、授权和 CSRF 防护仍要由服务端完成。

既有的 `PATCH` 文章还说明了为何把 `PATCH` 和 `If-Match` 等实际使用的方法、请求头加入 CORS 允许列表：[FastAPI 的 `@router.patch`：部分更新、请求方法与接口设计](/python/fastapi-的-router.patch部分更新请求方法与接口设计/)。

## 六、三种自定义方式的取舍

FastAPI 项目常见的自定义中间件手段不止一种。选择的依据不是“哪一种代码更短”，而是所需的协议能力与限制。

| 方式 | 适合场景 | 主要限制 |
| ---- | -------- | -------- |
| `@app.middleware("http")` | 普通 HTTP 请求/响应前后逻辑 | 只处理 HTTP，不能直接控制 ASGI 事件 |
| `BaseHTTPMiddleware` | 需要可配置、可复用的简单 HTTP 类 | 有 `ContextVar` 传播限制 |
| 纯 ASGI 中间件 | WebSocket、流式事件、包装 `receive`/`send`、追踪上下文 | 更底层，需要理解事件协议 |

### `BaseHTTPMiddleware`：类形式不等于更底层

当一项通用行为需要配置参数时，类形式比闭包或装饰器更清晰：

```python
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, referrer_policy: str = "same-origin"):
        super().__init__(app)
        self.referrer_policy = referrer_policy

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = self.referrer_policy
        return response


app.add_middleware(
    SecurityHeadersMiddleware,
    referrer_policy="strict-origin-when-cross-origin",
)
```

但 `BaseHTTPMiddleware` 是对 ASGI 的请求/响应适配层，不是纯 ASGI。Starlette 官方明确指出，它会阻断端点中对 `contextvars.ContextVar` 所做的改动向上游中间件传播；若它位于栈中较外层，还会影响后续依赖 `ContextVar` 的纯 ASGI 中间件。对于分布式追踪、结构化日志或其他依赖上下文传播的基础设施，应优先使用库提供的纯 ASGI 中间件，或自行实现纯 ASGI 版本。

此外，中间件类应把跨请求不变的配置存到 `__init__`，把请求相关变量保存在 `dispatch()` 的局部变量中。可复用对象同时服务多个协程，把“当前用户”“本次状态码”写入 `self`，只是在并发环境里制造一个十分安静的错误。

### 纯 ASGI：何时需要，以及最小安全头实现

纯 ASGI 中间件直接包装 `send`，可以在 `http.response.start` 事件发送前修改原始响应头；它也能通过包装 `receive` 观察请求体分块。下面是只针对 HTTP、同时保持 WebSocket 等其他 scope 原样通过的安全头实现：

```python
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersASGIMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
            await send(message)

        await self.app(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersASGIMiddleware)
```

这个例子之所以使用局部的 `send_with_headers` 闭包，是因为它与这一次 `scope` 绑定。纯 ASGI 中间件可以适配任意遵循 ASGI 的框架和服务器，且可同时覆盖 HTTP 与 WebSocket；代价是开发者必须正确处理事件类型、断连和响应头的字节表示。

## 七、异常、依赖清理与流式响应：不要误判“之后”的含义

`await call_next()` 返回，并不总是意味着响应体已经完整传给客户端。对于普通 JSON 响应，它通常已经完成了路由处理和响应对象的准备；对于 `StreamingResponse`、SSE 或大文件，响应主体可能在中间件返回后才持续产出。因此：

- 中间件在 `call_next` 后添加响应头是可行的，因为响应开始事件尚未由外层发送；
- 此处测到的时间适合作为“路由处理到获得响应”的近似耗时，不必然等于客户端收到最后一个字节的总时长；
- 不要为了记录完整响应体而在中间件中遍历并缓存流。这样会破坏流式传输、增加内存占用，还可能改变延迟特征；
- 若确实要按字节统计流式传输，应在纯 ASGI 层包装 `send`，累加每个 `http.response.body` 事件，并在最后一个 `more_body=False` 时完成统计。

异常也有相似的边界。中间件可以记录异常，但捕获后应该 `raise`，让 `HTTPException`、验证错误和未处理异常走既有的异常处理体系。若中间件无差别地吞掉异常并返回 `200` 或含糊的 JSON，日志、监控和客户端契约都会被破坏。

FastAPI 的 `yield` 依赖资源清理在中间件之后执行，后台任务则在所有中间件之后执行。这也是为什么“请求结束”的定义要说清楚：是端点返回、响应体发送完，还是后台任务结束？指标名称应表达实际测量的范围。

## 八、何时该使用依赖，而不是中间件

中间件对每一个 HTTP 请求生效，包括文档页、未匹配的路径和静态内容（取决于挂载位置）。依赖（`Depends`）则绑定在路由或路由组上，能获得已经解析的参数，并自然参与 OpenAPI 文档。可按下面的原则选择：

| 需求 | 更合适的位置 | 原因 |
| ---- | ------------ | ---- |
| 请求 ID、协议日志、CORS、统一安全头 | 中间件 | 对所有请求的协议级规则 |
| 验证 Bearer Token 的格式并解析当前身份 | 依赖或安全依赖 | 可声明在哪些路由需要认证，便于测试和文档化 |
| 判断用户能否修改 `/reports/{report_id}` | 依赖 + 业务服务 | 需要路径参数、数据库对象和明确领域规则 |
| 数据库会话的创建与关闭 | `yield` 依赖 | 生命周期与需要它的路由绑定，便于注入和替换 |
| 某组路由统一增加权限前置条件 | `APIRouter(dependencies=[...])` | 作用域明确，不影响健康检查和公开接口 |

例如，下面的依赖比全局中间件更适合需要用户身份的端点：

```python
from fastapi import Depends, HTTPException, Request, status


async def require_current_user(request: Request) -> dict:
    token = request.headers.get("Authorization")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing credentials",
        )
    return {"id": "user-42"}


@app.get("/me")
async def read_me(user: dict = Depends(require_current_user)):
    return user
```

实际项目应使用 FastAPI 的安全工具、正确验证签名和声明认证方案；这个例子只说明放置边界。把“每个请求先把用户塞到 `request.state`”作为默认方案，会让公开接口、文档路由、WebSocket、权限范围和测试替换都变得更难处理。

## 九、常用内置中间件与最后检查

在自己造轮子之前，先看 FastAPI/Starlette 已有的成熟实现：

- `CORSMiddleware`：浏览器跨域许可；
- `GZipMiddleware`：按客户端 `Accept-Encoding` 压缩合适的响应；
- `HTTPSRedirectMiddleware`：将 HTTP/WS 重定向到 HTTPS/WSS；
- `TrustedHostMiddleware`：限制允许的 `Host`，降低 Host Header 攻击风险；
- `SessionMiddleware`：基于签名 Cookie 的会话数据。

其中 HTTPS 重定向常与 TLS 终止代理配合配置；若代理没有正确传递原始协议，应用可能错误地重定向或形成循环。`GZipMiddleware` 对流式响应也能工作，但压缩与分块会改变传输特性；SSE 常需要避免被缓冲或压缩。部署环境而非一段复制来的代码，决定了这些中间件是否正确。

为中间件提交代码前，至少确认：

- 它的作用域真的是全局，而不是某一组路由；
- 多个中间件的添加顺序与请求/响应方向相符；
- 不把任何请求状态存入中间件实例；
- 不消耗请求体或缓存响应流，除非实现了完整的事件转发与大小控制；
- CORS 配置的是精确 Origin、实际方法和必要头，且没有把它当认证；
- 异常被记录后仍按既定异常处理器传播；
- 若使用 `BaseHTTPMiddleware`，已评估 `ContextVar` 与流式/追踪需求；
- 至少覆盖正常响应、异常响应、预检请求和流式响应的测试。

## 十、总结

FastAPI 中间件的重点从来不是记住一个装饰器，而是保持层次清楚：

- ASGI 中间件通过包裹应用处理 `scope`、`receive` 与 `send`，FastAPI 的 HTTP 装饰器是这个模型的易用入口；
- `@app.middleware("http")` 适合简单的 HTTP 前后处理，最后添加的中间件最先接收请求、最后处理响应；
- 请求 ID、耗时日志、安全头、CORS 等是合适的横切职责，但对象级授权和资源生命周期通常属于依赖；
- `BaseHTTPMiddleware` 可读性不错，却存在 `ContextVar` 上下文传播限制；涉及 ASGI 事件、WebSocket、严格追踪或流式统计时，使用纯 ASGI 中间件；
- 流式响应、异常和后台任务让“请求完成”具有不同层次，指标与清理逻辑必须明确自己覆盖的是哪一层。

中间件是接口系统的边界层。边界干净，路由才会保持可读；边界失控，任何一个看似方便的全局钩子，都会在以后变成难以解释的隐式规则。
