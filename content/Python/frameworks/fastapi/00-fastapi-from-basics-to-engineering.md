+++
date = '2026-09-26T20:00:00+08:00'
draft = false
title = 'FastAPI 教程：从第一个接口到工程化服务'
aliases = [
  '/python/fastapi_from_basics_to_engineering/',
]
+++
FastAPI 的吸引力不只是“写几行就能有接口文档”。它真正有价值的地方，是把 Python 类型标注、数据校验、接口契约与异步 Web 运行模型放在同一套框架里。初学者可以很快写出接口；而能否把它写成可维护的服务，取决于是否理解请求数据从哪里来、依赖何时创建和释放、同步与异步如何共处，以及错误、认证、文件和后台任务应该放在什么边界。

本文从零开始，并逐步推进到常见的工程实践。示例使用 FastAPI、Pydantic v2 和 SQLAlchemy 的同步会话；即使暂时不接数据库，也可以先运行前半部分。请不要把“能访问 `/docs`”误当成系统已经设计完成，文档只是契约的展示面，不是契约本身。

## 一、准备环境与第一个接口

创建虚拟环境并安装依赖：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0"
```

创建 `main.py`：

```python
from fastapi import FastAPI

app = FastAPI(title="任务 API", version="1.0.0")


@app.get("/health", tags=["健康检查"])
def health() -> dict[str, str]:
    return {"status": "ok"}
```

启动开发服务器：

```powershell
uvicorn main:app --reload
```

随后访问下列地址：

- `http://127.0.0.1:8000/health`：接口响应。
- `http://127.0.0.1:8000/docs`：Swagger UI。
- `http://127.0.0.1:8000/redoc`：ReDoc。
- `http://127.0.0.1:8000/openapi.json`：机器可读的 OpenAPI 契约。

`main:app` 的含义是“导入 `main.py` 中名为 `app` 的 ASGI 应用”。`--reload` 会在源文件改变时重启开发进程，适合本地开发；生产环境通常由进程管理器启动多个明确配置的 worker，而不是依赖文件监听。

## 二、路由、方法与状态码

HTTP 方法表达操作意图。最常见的资源接口可以这样设计：

```python
from fastapi import FastAPI, HTTPException, status

app = FastAPI()
tasks: dict[int, dict[str, object]] = {}


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(title: str) -> dict[str, object]:
    task_id = len(tasks) + 1
    task = {"id": task_id, "title": title, "done": False}
    tasks[task_id] = task
    return task


@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> dict[str, object]:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int) -> None:
    if tasks.pop(task_id, None) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
```

| 情形 | 常见状态码 | 含义 |
| --- | --- | --- |
| 查询成功 | `200 OK` | 返回资源或列表 |
| 成功创建 | `201 Created` | 新资源已经建立 |
| 接受异步工作 | `202 Accepted` | 已接收，但尚未完成 |
| 无响应体的成功操作 | `204 No Content` | 删除或回调确认成功 |
| 参数校验不通过 | `422 Unprocessable Entity` | 请求形状合法但数据不符合声明 |
| 未认证 / 无权限 | `401` / `403` | 缺少有效身份 / 身份没有此权限 |
| 不存在 / 状态冲突 | `404` / `409` | 资源不存在 / 当前状态不允许该操作 |

不要把所有业务失败包装成 `200` 加一个 `success: false`。HTTP 状态码、稳定的错误结构和错误消息共同构成接口协议；客户端、网关、监控系统都依赖它们做正确判断。

## 三、参数从哪里来：路径、查询、请求体、请求头与表单

FastAPI 依据路由模板、类型标注和参数默认值解析请求。下面的端点同时展示最常见来源：

```python
from typing import Annotated
from fastapi import FastAPI, Header, Path, Query
from pydantic import BaseModel, Field

app = FastAPI()


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=3, ge=1, le=5)


@app.post("/projects/{project_id}/tasks")
def create_project_task(
    project_id: Annotated[int, Path(gt=0)],
    payload: TaskCreate,
    notify: Annotated[bool, Query()] = False,
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "title": payload.title,
        "priority": payload.priority,
        "notify": notify,
        "request_id": request_id,
    }
```

| 参数形式 | 数据来源 | 示例 |
| --- | --- | --- |
| 出现在路径模板中 | 路径参数 | `project_id` |
| 标量参数配合 `Query` | 查询字符串 | `?notify=true` |
| `BaseModel` 参数 | JSON 请求体 | `payload` |
| `Header` | 请求头 | `X-Request-Id` |
| `Cookie` | Cookie | 会话标识、偏好等 |
| `File`、`Form` | `multipart/form-data` | 文件与表单上传 |

显式写 `Query`、`Path`、`Header` 的价值不止是“更长”：它使默认值、范围、别名和文档一目了然。路径 ID 这种关系到资源定位的输入，也应限制为正数、UUID 或业务允许的格式，而不是把所有字符串都交给后续代码猜测。

## 四、Pydantic：把 API 输入和输出变成明确契约

请求模型是客户端可写字段的白名单，响应模型是客户端可见字段的白名单。二者通常不能共用。

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("display_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("显示名称不能为空")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    created_at: datetime
```

```python
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate) -> UserOut:
    ...
```

`UserCreate` 允许提交密码，但 `UserOut` 不包含 `password` 或数据库中的 `password_hash`。这不是形式主义，而是防止敏感字段在一次“顺手返回对象”中泄漏的基本防线。`ConfigDict(from_attributes=True)` 让 Pydantic v2 可以从 ORM 实体属性生成输出模型；它不意味着应该把所有 ORM 字段公开。

部分更新应采用字段可选的专用模型，并通过 `model_dump(exclude_unset=True)` 区分“客户端没有传”和“客户端明确传了空值”：

```python
class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = None


def apply_update(user: object, payload: UserUpdate) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
```

这里仍要在业务层限制不可修改字段。不要接受任意字典再批量 `setattr`，那会把角色、余额、所有者等服务端字段暴露为可被客户端篡改的入口。

## 五、使用 `APIRouter` 组织模块

应用变大后，把所有端点写在 `main.py` 会很快失控。`APIRouter` 用来按领域组织路由，再在应用入口组合。

```python
# routers/tasks.py
from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.get("")
def list_tasks() -> list[dict[str, object]]:
    return []
```

```python
# main.py
from fastapi import FastAPI
from routers.tasks import router as tasks_router

app = FastAPI()
api = APIRouter(prefix="/api/v1")
api.include_router(tasks_router)
app.include_router(api)
```

最终 `list_tasks` 的路径是 `/api/v1/tasks`。前缀是逐层叠加的：应用或聚合路由的 `/api/v1` 加上领域路由的 `/tasks` 加上端点的空字符串。版本前缀只应在一个清晰位置统一定义，避免每个模块各自硬编码 `/api/v1` 后难以迁移。

推荐的最小结构如下：

```text
app/
  main.py          应用装配
  routers/         HTTP 路由
  schemas/         请求与响应模型
  services/        业务用例与事务边界
  models/          ORM 实体
  database.py      Engine、Session、依赖
```

目录不是架构本身。关键在于路由层处理 HTTP 细节和依赖，服务层表达业务动作，持久化层负责数据访问；不要为了“分层”而让一个简单查询绕过五个空函数。

## 六、依赖注入：共享逻辑与资源生命周期

`Depends` 会在执行端点前解析依赖，并把结果作为参数传入。它适合认证、数据库会话、分页规则、租户识别、配置读取等横切能力。

```python
from collections.abc import Generator
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .database import SessionLocal

app = FastAPI()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db)) -> object:
    user = ...
    if user is None:
        raise HTTPException(status_code=401, detail="无效或缺失的访问令牌")
    return user


@app.get("/me")
def me(current_user: object = Depends(get_current_user)) -> object:
    return current_user
```

生成器依赖特别适合资源管理：`yield` 前创建资源，端点结束后即使发生异常也会执行 `finally`。这不等于自动提交数据库事务；`close()` 只释放会话及其连接，成功持久化仍需要由业务边界明确 `commit()`。

一个请求内，FastAPI 默认会缓存同一依赖及其子依赖的结果。因此上例的 `get_current_user` 使用的 `Session` 与端点其它 `Depends(get_db)` 取得的是同一请求会话。不要绕过依赖在每个函数里随意 `SessionLocal()`，否则同一业务动作会无意中跨越多个事务。

## 七、认证、授权与中间件

认证回答“你是谁”，授权回答“你是否能做这件事”。一个最小 Bearer Token 认证依赖可以使用 `HTTPBearer`：

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="需要 Bearer Token")
    user = verify_access_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return user


def require_admin(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
```

即使用户已通过认证，也必须在读写资源时检查所有权。例如更新文章时，不能只按文章 ID 更新，而应同时确认 `article.owner_id == current_user.id`，或由管理员角色明确放行。这可以阻断“猜到别人的 ID 就能修改”的横向越权。

中间件适合处理每个请求都需要经过的协议级逻辑，例如请求 ID、访问日志、CORS、统一安全头，或“默认需要认证”的入口控制。它不适合隐藏复杂的业务授权规则；中间件看不到具体业务对象时，很难正确判断一个用户能否操作某一条数据。

浏览器跨域由 `CORSMiddleware` 处理：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://console.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)
```

不要在携带 Cookie 或 Authorization 的生产服务中习惯性写 `allow_origins=["*"]`。CORS 只是浏览器规则，不会阻止非浏览器客户端直接发请求，更不能代替认证授权。

## 八、文件上传、下载与静态资源

上传表单必须使用 `multipart/form-data`。文件和普通字段可以同时声明：

```python
from fastapi import File, Form, HTTPException, UploadFile


@app.post("/attachments", status_code=201)
async def upload_attachment(
    title: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, str]:
    allowed = {"image/png", "image/jpeg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="只支持 PNG 或 JPEG 图片")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 5 MiB")

    # 还应验证真实文件格式，生成服务端文件名，并写入受控存储。
    return {"title": title, "filename": file.filename or "upload"}
```

`content_type` 和客户端文件名都可伪造，因此安全上传至少需要：大小限制、扩展名与魔数/实际内容校验、服务端生成的存储名、受控目录、病毒或内容安全检查，以及与业务数据的一致性处理。大文件不应一口气 `read()` 到内存；应按存储后端采用流式写入或分片上传。

`StaticFiles` 只适合真正公开的资源，例如站点图标、公开封面或构建后的前端文件。私有附件、购买后下载的文件、导出报表必须经过普通端点的认证和授权检查后才返回 `FileResponse` 或流式响应；把受保护目录直接挂成静态目录，会直接绕过所有权限代码。

## 九、同步、异步与后台工作

FastAPI 能同时定义 `def` 和 `async def`：

```python
@app.get("/sync")
def sync_endpoint() -> dict[str, bool]:
    return {"ok": True}


@app.get("/async")
async def async_endpoint() -> dict[str, bool]:
    return {"ok": True}
```

同步端点会被放进外部线程池执行，适合现有同步库，例如标准 SQLAlchemy `Session`、同步 SDK 或阻塞文件 API。异步端点适合需要 `await` 的异步网络、异步数据库驱动或流式 I/O。二者最重要的区别不是语法，而是**不能在事件循环线程中直接运行长时间阻塞操作**。

```python
import asyncio


@app.get("/reports/{report_id}")
async def get_report(report_id: int) -> dict[str, object]:
    result = await asyncio.to_thread(build_report_with_sync_sdk, report_id)
    return result
```

`asyncio.to_thread()` 是把阻塞函数移出事件循环的过渡方式，不会让计算或 SQL 本身更快。若服务整体采用异步数据库栈，应从驱动、Engine、Session 到调用链统一使用异步 API；不要在一个函数里把同步 `Session` 和 `AsyncSession` 随意混用。

`BackgroundTasks` 可以把较短的后续操作安排在响应发出后执行：

```python
from fastapi import BackgroundTasks


def send_welcome_email(address: str) -> None:
    ...


@app.post("/users", status_code=201)
def register_user(payload: UserCreate, background_tasks: BackgroundTasks) -> dict[str, str]:
    user = create_user_in_database(payload)
    background_tasks.add_task(send_welcome_email, user.email)
    return {"id": str(user.id)}
```

它适合失败可容忍、运行很短的邮件通知、日志转发等工作；它不是消息队列。进程重启、部署滚动更新或任务抛异常时，任务没有持久化重试保证。耗时计算、支付履约、视频转码等必须可靠执行的任务，应使用持久任务状态、专用 worker 与队列，并设计重试、幂等、超时和可观测性。

## 十、应用生命周期、错误处理与测试

`lifespan` 用于管理应用启动和关闭时配对出现的资源：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：加载配置、检查依赖、建立共享客户端。
    yield
    # 关闭：停止消费、关闭客户端、释放进程级资源。


app = FastAPI(lifespan=lifespan)
```

它适合进程级资源，不适合请求级数据库会话。数据库迁移是否应在 Web 服务启动时执行，要结合多实例部署的锁、失败策略和发布流程审慎决定；无论采用何种方式，都不能在服务已接流量时默默运行一半迁移。

对于稳定的领域错误，可以定义异常和异常处理器，避免每个端点复制相同 JSON 结构：

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class DomainConflict(Exception):
    def __init__(self, message: str):
        self.message = message


@app.exception_handler(DomainConflict)
async def conflict_handler(_: Request, exc: DomainConflict) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})
```

测试优先验证 HTTP 契约和可观察结果，而不是只测内部函数是否被调用：

```python
from fastapi.testclient import TestClient


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

使用 `TestClient` 上下文可触发 lifespan，适合检验启动依赖。涉及数据库时应为测试使用隔离库或事务回滚策略；绝不能让测试配置指向生产数据库。外部支付、邮件、对象存储等服务则通过依赖覆盖或测试替身隔离，重点验证自己的请求、状态转换和错误处理。

## 总结

一条稳健的 FastAPI 请求链可以概括为：

```text
HTTP 请求
  -> 中间件处理协议级横切逻辑
  -> 路由匹配与类型校验
  -> Depends 创建身份、会话等请求级依赖
  -> 服务层执行带授权和事务边界的业务动作
  -> response_model 过滤并序列化输出
  -> HTTP 响应
```

- 用 Pydantic 分离输入模型与输出模型，让可写、可见字段成为明确白名单。
- 用 `APIRouter` 组织领域路由，用 `Depends` 管理可复用逻辑和资源生命周期。
- 把认证、授权、CORS、文件权限、后台可靠性分别放在正确边界，不互相替代。
- 同步库配合同步端点；异步 I/O 配合完整的异步调用链，避免阻塞事件循环。
- 对长任务、支付回调和资源修改，优先思考幂等性、状态机、事务与失败恢复。

接下来可以继续阅读 [SQLAlchemy ORM 进阶实践：查询、事务、并发与迁移](../sqlalchemy/01-advanced-practice.md)，把 Web 请求如何进入服务，与数据如何可靠落库连接起来。
