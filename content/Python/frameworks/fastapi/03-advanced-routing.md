+++
date = '2026-09-28T00:35:00+08:00'
draft = false
title = 'FastAPI 高级路由：组织、匹配、依赖与接口契约'
aliases = [
  '/python/fastapi-%E9%AB%98%E7%BA%A7%E8%B7%AF%E7%94%B1%E7%BB%84%E7%BB%87%E5%8C%B9%E9%85%8D%E4%BE%9D%E8%B5%96%E4%B8%8E%E6%8E%A5%E5%8F%A3%E5%A5%91%E7%BA%A6/',
]
+++

当 FastAPI 应用只有两三个端点时，把所有内容放在 `main.py` 似乎并无不妥。可一旦同时出现账户、订单、管理后台、公开查询和多个 API 版本，真正难的问题不再是“怎样再写一个 `@app.get`”，而是：路径由谁拼接、相似路径会命中哪个端点、校验和认证放在哪里、响应承诺怎样稳定地交给调用方。

FastAPI 的高级路由并不是某个神秘开关。它是一套将**路径操作**、`APIRouter`、Pydantic 类型模型、依赖注入与 OpenAPI 元数据组合起来的机制。本文从一个可扩展的路由结构出发，说明路由匹配、参数校验、路由级依赖、响应契约和版本化分别解决什么问题，以及它们不该替代什么。

本文的示例使用 Python 3.10+、FastAPI 与 Pydantic v2 风格的 `Annotated`。涉及部分更新的具体语义，可继续阅读 [FastAPI 的 @router.patch：部分更新、请求方法与接口设计](01-patch-and-http-methods.md)。

## 一、先建立正确的模型：路由登记的是 HTTP 契约

下面的装饰器并不会立刻处理请求：模块被导入时，它会把函数、HTTP 方法、路径、参数规则、响应规则和文档元数据登记到 `router` 中。

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/orders/{order_id}")
async def get_order(order_id: int) -> dict[str, int]:
    return {"id": order_id}
```

应用启动后的某个请求才会经历下面的链路：

```text
HTTP 请求
  -> 按注册顺序寻找路径和方法都匹配的路由
  -> 从路径、查询串、请求头、请求体等位置提取参数
  -> 依据类型和约束校验参数，解析依赖
  -> 执行路径操作函数
  -> 按 response_model 过滤、序列化响应
  -> 返回 HTTP 状态码、头和响应体
```

因此，路由层应负责 HTTP 世界的边界：请求来自哪里、返回什么状态码、输入输出如何表示、需要哪些通用前置条件。它不应承载难以测试的业务编排或把数据库细节铺满每一个函数。`APIRouter` 正是把这层边界按领域拆开的容器；官方也将其定义为可被应用或另一个路由器包含、用于组织路径操作的对象。[FastAPI：APIRouter 参考](https://fastapi.tiangolo.com/reference/apirouter/)

## 二、用 `APIRouter` 按领域分层，而不是按技术名堆文件

一个简单且可持续的目录结构如下：

```text
app/
  main.py                 应用装配和最外层路由
  api/
    v1/
      router.py           v1 聚合路由
      orders.py           订单的 HTTP 端点
      users.py            用户的 HTTP 端点
  schemas/                请求与响应模型
  services/               业务用例
```

`orders.py` 只声明本领域的局部前缀和默认文档标签：

```python
# app/api/v1/orders.py
from typing import Annotated

from fastapi import APIRouter, Path
from pydantic import BaseModel


router = APIRouter(prefix="/orders", tags=["订单"])


class OrderOut(BaseModel):
    id: int
    status: str


@router.get("", response_model=list[OrderOut])
async def list_orders() -> list[OrderOut]:
    return []


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: Annotated[int, Path(gt=0)],
) -> OrderOut:
    return OrderOut(id=order_id, status="created")
```

版本聚合文件只负责组合：

```python
# app/api/v1/router.py
from fastapi import APIRouter

from .orders import router as orders_router
from .users import router as users_router

router = APIRouter(prefix="/v1")
router.include_router(orders_router)
router.include_router(users_router)
```

最后，应用入口把这个版本纳入应用：

```python
# app/main.py
from fastapi import FastAPI

from app.api.v1.router import router as v1_router

app = FastAPI(title="Shop API", version="1.0.0")
app.include_router(v1_router, prefix="/api")
```

最终路径为 `/api/v1/orders/{order_id}`。前缀的规则只是逐层连接：`include_router()` 调用处的 `/api`，加聚合路由的 `/v1`，加领域路由的 `/orders`，再加端点字符串 `/{order_id}`。

### `include_router()` 是装配，不是一次额外的 HTTP 转发

常把 `include_router()` 想成“收到请求后交给子路由器”并不准确。它在应用构建阶段把已声明的路径操作纳入父路由表，同时可叠加 `prefix`、`tags`、`dependencies`、`responses` 与 `deprecated` 等公共配置。路由文件可以独立声明、入口统一装配，测试时也可以只创建一个小应用并包含目标 router。

```python
from fastapi import Depends, FastAPI

from app.api.v1.router import router as v1_router
from app.security import require_api_key

app = FastAPI()
app.include_router(
    v1_router,
    prefix="/api",
    dependencies=[Depends(require_api_key)],
    responses={401: {"description": "缺少或无效的 API Key"}},
)
```

不要在每个 `orders.py`、`users.py` 中硬编码 `/api/v1`。版本或部署前缀变动时，集中装配点能让改动只发生一次。反过来，过度嵌套三四层空路由器也不会制造架构；当一个层级没有公共前缀、依赖、文档规则或清晰边界时，它通常没有存在的必要。

## 三、路径匹配顺序：具体路径必须先于参数路径

路由器按**注册顺序**尝试匹配路径。若静态路径与参数路径都可能匹配同一个 URL，应先声明静态路径：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/me")
async def read_current_user() -> dict[str, str]:
    return {"user": "current"}


@router.get("/{user_id}")
async def read_user(user_id: str) -> dict[str, str]:
    return {"user": user_id}
```

此时 `GET /users/me` 命中 `read_current_user`。若将 `/{user_id}` 放在前面，它会先把 `me` 当成 `user_id`，后面的 `/me` 根本没有机会处理请求。FastAPI 的路径参数教程同样明确要求把固定路径放在参数路径之前。[FastAPI：路径参数顺序](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters)

类型校验发生在**某条路由被选中之后**，不会让框架回头尝试下一条路由。例如下面的 `GET /users/me` 会命中 `/{user_id}` 后因 `int` 校验失败返回 `422`，而不是自动改去寻找后面的 `/me`：

```python
@router.get("/{user_id}")
async def read_user(user_id: int) -> dict[str, int]:
    return {"id": user_id}


@router.get("/me")
async def read_current_user() -> dict[str, str]:
    return {"user": "current"}
```

这不是框架不够聪明，而是路由表需要确定、可预测。靠“校验失败后换一个端点试试”会让同一请求随着模型规则改变而进入不同业务逻辑。设计 URL 时也应避免过度重叠，例如将统计接口写为 `/orders/stats`，并把它声明在 `/orders/{order_id}` 之前。

### 路径参数和查询参数并不靠名称猜测

在 `/orders/{order_id}` 中出现的同名函数参数是路径参数；函数签名中未出现在路径模板里的标量参数默认是查询参数。

```python
from typing import Annotated

from fastapi import Query


@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    verbose: bool = False,
    fields: Annotated[list[str] | None, Query()] = None,
) -> dict[str, object]:
    return {
        "id": order_id,
        "verbose": verbose,
        "fields": fields,
    }
```

请求 `/orders/42?verbose=true&fields=id&fields=status` 会得到 `order_id=42`、`verbose=True` 和 `fields=["id", "status"]`。参数位置由路径模板和声明形式决定，不是由变量叫 `id`、`page` 或 `filter` 决定。

## 四、把输入校验写进契约，而不是留给 `if` 链猜测

FastAPI 根据类型标注与 `Path`、`Query`、`Header` 等声明解析数据，并在参数不满足规则时自动返回结构化的 `422` 错误。把约束放在声明处，既能阻止无意义的请求进入业务层，也能让 OpenAPI 文档和代码保持同一份事实。

```python
from typing import Annotated
from uuid import UUID

from fastapi import Header, Path, Query


@router.get("/orders/{order_id}")
async def get_order(
    order_id: Annotated[UUID, Path(description="订单的 UUID")],
    include_items: Annotated[bool, Query()] = False,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    request_id: Annotated[
        str | None,
        Header(alias="X-Request-Id", max_length=64),
    ] = None,
) -> dict[str, object]:
    return {
        "order_id": str(order_id),
        "include_items": include_items,
        "page_size": page_size,
        "request_id": request_id,
    }
```

常用选择如下：

| 需求 | 适合的声明 | 示例 |
| --- | --- | --- |
| URL 中定位资源 | `Path` + 强类型/范围 | `Path(gt=0)`、`UUID` |
| 分页、筛选、排序 | `Query` | `Query(ge=1, le=100)` |
| 链路标识、条件请求 | `Header` | `Header(alias="X-Request-Id")` |
| 结构化写入数据 | Pydantic `BaseModel` | `OrderCreate` |

### 校验是边界保护，不是全部业务规则

`page_size <= 100`、UUID 格式正确、字符串长度不超限属于输入形状规则，适合在路由参数中声明。可是“当前用户能否查看这张订单”“订单是否已经取消”“两个字段组合后是否满足库存规则”必须在认证、授权和业务层处理。

换言之，`422` 表示请求不符合已声明的参数契约；它不等同于所有业务失败。业务上不存在的资源通常是 `404`，没有身份是 `401`，身份没有权限是 `403`，当前状态不允许操作常是 `409` 或更具体的状态码。把每一种错误都压缩成 `422`，只是让调用方失去判断依据。

## 五、路由级依赖：统一前置条件，但别丢失返回值

若一组端点都需要认证、租户解析或审计检查，把依赖重复写在每个函数签名中会显得嘈杂。`APIRouter(dependencies=[...])` 可以令这些依赖在该路由器所有路径操作执行前运行：

```python
from fastapi import APIRouter, Depends, Header, HTTPException, status


async def require_api_key(
    x_api_key: str | None = Header(default=None),
) -> None:
    if x_api_key != "demo-secret":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效",
        )


admin_router = APIRouter(
    prefix="/admin",
    tags=["管理"],
    dependencies=[Depends(require_api_key)],
)


@admin_router.get("/metrics")
async def read_metrics() -> dict[str, int]:
    return {"active_users": 42}
```

没有合格 `X-API-Key` 的请求不会进入 `read_metrics`。依赖内部抛出的 `HTTPException` 会短路请求；这正适合无法通过就没有必要运行端点的前置条件。

但有一个常被忽略的区别：**写在 `dependencies=[...]` 中的依赖会执行，其返回值不会作为端点形参提供。**若端点本身需要当前用户对象，应在函数签名中声明该依赖：

```python
from typing import Annotated

from fastapi import Depends


class CurrentUser:
    def __init__(self, user_id: int, role: str) -> None:
        self.user_id = user_id
        self.role = role


async def get_current_user() -> CurrentUser:
    return CurrentUser(user_id=7, role="admin")


@admin_router.get("/profile")
async def read_my_profile(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, object]:
    return {"id": user.user_id, "role": user.role}
```

实践中可这样划分：

- router 级 `dependencies`：认证是否通过、租户头是否存在、统一权限门槛等，只需要成功或失败的前置检查；
- 端点参数 `Depends(...)`：端点需要使用的会话、当前用户、分页对象或其他计算结果；
- `include_router(..., dependencies=[...])`：在装配时给整组已存在路由附加外层策略，例如 `/api/v1` 全部端点都需访问令牌。

同一请求内，FastAPI 默认缓存同一个依赖及其子依赖的结果。因此不要为“既做鉴权又取得用户”机械调用两套完全相同的数据库查询；应让依赖链表达清楚的数据流。反之，是否共享数据库事务、怎样提交回滚，仍需要由服务层和会话生命周期明确设计，不能因为依赖被缓存便认为事务已经自动正确。

## 六、响应模型和状态码：明确服务承诺，而非仅美化文档

`response_model` 同时作用于文档、序列化和输出过滤。它使“客户端能看见哪些字段”成为可执行的白名单。

```python
from datetime import datetime

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime


@router.post(
    "/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "幂等键冲突或订单状态冲突"}},
)
async def create_order() -> object:
    entity = create_order_in_service()
    return entity
```

即使 `entity` 是 ORM 实体并带有 `internal_note`、`cost_price` 或其他内部字段，响应模型也只输出 `OrderOut` 声明的字段。不要把“数据来自可信数据库”误当成“可以原样返回客户端”；泄露通常就发生在这样的省略里。

状态码应表达结果，而非只给成功统一返回 `200`：

| 结果 | 常用状态码 | 何时使用 |
| --- | --- | --- |
| 读取或普通操作成功 | `200 OK` | 返回资源、列表或操作结果 |
| 新资源已经创建 | `201 Created` | `POST` 创建成功 |
| 已接收、尚未完成 | `202 Accepted` | 排队的异步工作 |
| 删除成功且无响应体 | `204 No Content` | 不返回 JSON 正文 |
| 输入不符合声明 | `422 Unprocessable Entity` | 类型、范围、模型校验失败 |
| 当前状态冲突 | `409 Conflict` | 重复创建、版本或状态冲突 |

`responses={...}` 的主要作用是补充 OpenAPI 中可能出现的响应说明和模型；它不会自行生成 409。实际代码仍需在发生冲突时抛出 `HTTPException(status_code=409, ...)` 或返回相应 `Response`。这一区别很朴素，却常被“文档里写了所以行为已经存在”的错觉遮住。

当端点会返回 `204 No Content` 时，不要再返回 JSON 数据；当端点返回文件、流或重定向时，应使用对应的响应类并准确描述媒体类型。`response_model` 不是把每一种响应都改成 JSON 的魔法，而是 JSON 结构化响应的一部分契约。有关输入模型、输出模型和 ORM 属性读取的基本关系，可参阅 [FastAPI 教程：从第一个接口到工程化服务](00-fastapi-from-basics-to-engineering.md)。

## 七、版本化：让不兼容变更能与旧客户端共存

版本化要解决的不是“每次发布都加一个数字”，而是让破坏性变更拥有可预测的迁移窗口。最常见、最容易被网关和调用方识别的办法是路径版本：

```text
/api/v1/orders
/api/v2/orders
```

它可由两个聚合 router 自然实现：

```python
app.include_router(v1_router, prefix="/api")
app.include_router(v2_router, prefix="/api")
```

不要为每一次增加可选字段都创建 `/v2`。通常可兼容的变更包括：响应中增加客户端可忽略的字段、为请求增加有默认值的可选字段、修正文档示例。删除或重命名字段、改变字段类型/含义、收紧原先允许的输入、改变成功或错误语义，则可能破坏客户端，应当通过新版本、协商媒体类型或明确迁移计划处理。

版本数也不等于 API 文档中的 `app.version`。`FastAPI(version="1.0.0")` 是 OpenAPI 信息中的应用版本，而 `/api/v1` 是请求 URL 的兼容性边界；两者可以协调命名，但用途不同。为某个旧版本设置 `deprecated=True` 会在 OpenAPI/Swagger UI 中标示弃用，它不会阻止实际访问。下线需要公告、观测真实调用量、设置迁移期限，并最终移除路由或由网关拒绝请求。

## 八、让 `/docs` 成为可靠的合同：标签、摘要与 `operation_id`

FastAPI 会从路由声明生成 OpenAPI，从而提供 `/docs` 与 `/openapi.json`。自动文档很方便，但它只会忠实展示你登记的契约；含糊的路径名、默认函数名、漏写的错误响应都会原封不动地变成含糊的文档。

```python
@router.get(
    "/{order_id}",
    response_model=OrderOut,
    summary="查询单个订单",
    description="返回当前调用方有权访问的订单。",
    response_description="订单详情",
    operation_id="getOrderById",
    responses={404: {"description": "订单不存在或无权访问"}},
)
async def get_order(
    order_id: Annotated[int, Path(gt=0)],
) -> OrderOut:
    order = find_visible_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order
```

这些选项的职责不同：

- `tags`：把一组端点归类到文档界面；可在 `APIRouter` 上统一设置；
- `summary` 与 `description`：给人阅读的简短标题与详细说明；
- `response_description`：描述成功响应语义；
- `operation_id`：OpenAPI 中唯一的操作标识，代码生成 SDK 通常据此命名方法；
- `responses`：补充非默认状态码的描述、响应模型和头部信息；
- `deprecated=True`：在文档中标记不建议继续使用的端点；
- `include_in_schema=False`：从 OpenAPI 中隐藏端点，但不关闭实际路由。

`operation_id` 必须在整个 OpenAPI 文档中唯一。手写它的优点是 SDK 方法名稳定且语义清晰；代价是团队必须维护唯一性。若不手写，FastAPI 会生成默认 ID；接口已经被外部 SDK 使用时，不应因为改了 Python 函数名或路径组织就无意改变其公开识别符。官方的 [路径操作配置说明](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/) 列出了这些文档元数据，而 `APIRouter` 也支持为整组操作统一设置标签、依赖、额外响应和是否纳入 schema。

隐藏 `include_in_schema=False` 不等于保护接口。健康检查、内部调试端点即使不出现在 `/docs`，仍可被知道路径的人请求；真正的保护仍是认证、授权和网络边界。把安全寄托在“不写进文档”，是把门牌摘了再宣称房间不存在，未免过分乐观。

## 九、一份路由设计检查清单

在新增或评审一个路由模块时，可以依次核对：

- 路径是否以资源和层级关系表达，而不是暴露内部函数名？
- 静态路径是否注册在会与之冲突的 `/{param}` 路径之前？
- 路径、查询、头、请求体的来源和限制是否都明确声明？
- 输入模型是否只允许客户端真正可写的字段，响应模型是否只暴露客户端真正可见的字段？
- 通用前置检查是否放在合适的 router/app 级依赖中；端点是否仍能拿到自己需要的依赖返回值？
- 成功和失败的状态码、错误结构、附加响应是否与真实行为一致？
- 是否真的发生了不兼容变更，才引入新的 URL 版本？
- `tags`、`summary`、`operation_id` 和弃用标记能否让人和自动生成客户端都正确理解 API？

## 总结

FastAPI 的高级路由能力本质上是把 API 的组织和契约显式化：

- 用 `APIRouter` 和 `include_router()` 将领域路由与应用装配分开，前缀、标签、依赖等规则按层叠加；
- 路由按登记顺序匹配，因此固定路径必须排在参数路径之前，不能期待校验失败后自动回退；
- 用类型标注、`Path`、`Query`、`Header` 与 Pydantic 模型声明输入边界，但把授权和业务不变量留在正确的业务层；
- 路由级依赖适合统一前置检查，只有写进端点参数的依赖结果才能直接供端点使用；
- `response_model`、状态码和 `responses` 共同构成调用方可依赖的输出合同；
- 路径版本、`operation_id`、标签和弃用标志让兼容性与文档不再依赖口头约定。

当路由表能够让调用者、测试、文档和服务代码对“这个请求会去哪里、需要什么、可能得到什么”给出同一个答案时，路由才不只是装饰器堆出的入口，而是稳定 API 的骨架。
