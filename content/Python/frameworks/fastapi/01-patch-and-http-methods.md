+++
date = '2026-09-28T00:20:00+08:00'
draft = false
title = 'FastAPI 的 @router.patch：部分更新、请求方法与接口设计'
aliases = [
  '/python/fastapi-%E7%9A%84-router.patch%E9%83%A8%E5%88%86%E6%9B%B4%E6%96%B0%E8%AF%B7%E6%B1%82%E6%96%B9%E6%B3%95%E4%B8%8E%E6%8E%A5%E5%8F%A3%E8%AE%BE%E8%AE%A1/',
]
+++

在 FastAPI 项目中看到下面这行代码时，最容易产生两种误解：一是把它当作“直接修改数据”的函数调用；二是认为只要用了 `PATCH`，框架就会自动完成部分更新。

```python
@router.patch("/users/{user_id}")
```

两种理解都不对。**`@router.patch(...)` 是路径操作装饰器（path operation decorator）：它在应用导入和装配阶段，把紧随其后的函数注册为一个仅处理 HTTP `PATCH` 请求的路由。**它决定“哪种请求会到达这个函数”，并参与生成 OpenAPI 和 `/docs` 文档；它不会自行查数据库、合并字段、校验权限或提交事务。部分更新的具体语义仍必须由端点、Pydantic 模型和业务层共同实现。

本文从 `@router.patch` 出发，解释 `PATCH`、`PUT` 的区别，给出一套安全的 FastAPI 部分更新实现，并梳理 FastAPI 中常用的 HTTP 请求方法。HTTP 动词并不是装饰性的命名习惯；它影响调用方如何理解重试、缓存、并发和错误处理。接口契约若从一开始就含糊，后面无论补多少注释都很难挽回。

若还需要先建立 FastAPI 的路由、Pydantic 模型、依赖注入和生命周期基础，可先阅读 [FastAPI 从基础到工程实践](00-fastapi-from-basics-to-engineering.md)。这篇文章只聚焦请求方法与更新契约，不重复铺开整个框架。

## 一、`@router.patch` 到底做了什么

先看一个完整但精简的路由模块：

```python
from fastapi import APIRouter, status


router = APIRouter(prefix="/users", tags=["用户"])


@router.patch(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="部分更新用户资料",
)
def update_user(user_id: int) -> dict[str, int]:
    return {"id": user_id}
```

`router` 是 `APIRouter` 的实例。执行 `@router.patch("/{user_id}", ...)` 时，`patch()` 返回一个装饰器；该装饰器接收下面定义的 `update_user` 函数，并向路由器登记一条路径操作。等应用调用 `app.include_router(router)` 时，路由前缀、标签、依赖等配置会被合并进应用。

最终这条规则可以这样理解：

```text
HTTP 方法：PATCH
最终路径：/users/{user_id}
处理函数：update_user
```

如果应用又在外层挂载了版本前缀：

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(router)
app.include_router(api_v1)
```

最终路径便是：

```text
PATCH /api/v1/users/{user_id}
```

前缀会逐层叠加。也就是说，`@router.patch` 中写的 `"/{user_id}"` 是相对 `APIRouter.prefix` 的路径，而不是总 URL。把版本前缀散落在每个端点里，短期看似省事，长期则只会让迁移变成搜索替换的事故现场。

### 装饰器注册的内容不只有路径和方法

路径操作装饰器还可声明响应模型、状态码、标签、依赖、错误响应、文档摘要等：

```python
from fastapi import Depends, HTTPException, status


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    responses={404: {"description": "用户不存在"}},
    dependencies=[Depends(require_authenticated_user)],
    summary="部分更新用户资料",
)
def update_user(user_id: int, payload: UserPatch) -> UserOut:
    ...
```

这些参数会影响 FastAPI 的请求解析、响应序列化与 OpenAPI 文档。尤其是 `response_model`：它既在 `/docs` 中声明响应结构，也会按模型过滤实际输出，避免 ORM 对象中的敏感字段因为一次“直接返回”而泄漏。FastAPI 官方参考中将 `patch()` 定义为“添加一个 HTTP PATCH 路径操作”，并列出了这些配置项；它并不替应用规定资源更新的业务规则。[FastAPI `patch()` 参考](https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.patch)

### `@app.patch` 和 `@router.patch` 的区别

两者最终都会注册 `PATCH` 路由，差别主要在组织层级：

| 写法 | 适用位置 | 典型用途 |
| --- | --- | --- |
| `@app.patch(...)` | 小型应用或应用入口 | 直接把端点注册到 `FastAPI` 实例 |
| `@router.patch(...)` | 按领域拆分模块 | 在 `APIRouter` 中组织用户、订单、文章等路由 |

项目一旦超过少量端点，通常应使用 `APIRouter` 分模块，再由 `main.py` 统一组合。装饰器的选择不改变 HTTP 语义；`router` 不是另一种协议，只是让路由结构不至于随着文件长度一起失控。

## 二、`PATCH` 的语义：修改一部分，不是替换整个资源

HTTP `PATCH` 用于对目标资源应用**部分修改**。例如当前用户资料是：

```json
{
  "id": 7,
  "display_name": "Yukino",
  "bio": "student",
  "email": "yukino@example.com",
  "role": "user"
}
```

客户端只想修改简介时，合理的请求是：

```http
PATCH /api/v1/users/7
Content-Type: application/json

{
  "bio": "backend engineer"
}
```

服务端应只改变 `bio`，保留 `display_name`、`email`、`role` 等未提交字段。FastAPI 的官方更新教程也将 `PATCH` 作为部分更新的常用操作，并建议从 Pydantic 模型中取出 `model_dump(exclude_unset=True)`，使只有客户端实际提交的字段参与合并。[FastAPI：部分更新](https://fastapi.tiangolo.com/tutorial/body-updates/)

这里有三个必须分清的层次：

1. `PATCH` 是 HTTP 方法，表达“对资源应用修改”的意图。
2. `@router.patch` 是 FastAPI 将该方法与 Python 函数绑定的方式。
3. `UserPatch`、字段白名单、权限、事务和并发检查，才决定这次修改是否安全、具体怎样落库。

FastAPI 不会因为请求方法是 `PATCH` 就替你完成第 3 层。它不可能知道“`role` 是否允许改”“`null` 是清空还是无操作”“余额改变是否需要账务流水”；这些是领域规则，不是路由框架能替你猜测的事情。

## 三、`PATCH`、`PUT`、`POST`：不要只按“都能改数据”来选

下表给出最常见的资源接口约定。它们是很有价值的语义约定，不是 FastAPI 强制执行的限制；框架允许你注册各种方法，但客户端、代理、监控和后续维护者不会自动理解你的个人习惯。

| 方法 | 常见意图 | 请求体的典型含义 | 安全性与幂等性 |
| --- | --- | --- | --- |
| `POST` | 创建子资源，或执行资源特定动作 | 创建输入、命令参数 | 通常非安全、非幂等 |
| `PUT` | 以请求表示替换目标资源 | 完整的新表示 | 非安全；通常应设计为幂等 |
| `PATCH` | 修改目标资源的一部分 | 局部字段或补丁文档 | 非安全；协议层面不保证幂等 |

### `PUT`：替换的意图

`PUT /users/7` 的传统语义是：请求体代表该资源希望成为的**完整表示**。如果客户端每次都提交完整对象，重试同一个 `PUT` 通常会得到相同的最终状态，因此它适合设计为幂等操作。

但要注意，“完整”并不等于“把数据库每一列都暴露给客户端”。API 表示可以是经过设计的可写模型，它应排除服务端生成字段、权限字段、密码散列、审计字段等。接口公开什么，永远由 API 契约决定，不由表结构决定。

### `PATCH`：部分修改的意图

`PATCH /users/7` 适合只提交发生变化的字段。它能减少客户端必须先读取完整资源再提交回去的负担，也能避免默认值在不经意间覆盖存量值。

不过 RFC 5789 将 `PATCH` 定义为非安全且**不天然幂等**的方法。一个“把昵称设置为某个确定值”的补丁可以被设计成幂等：重复执行后最终都是同一个昵称；但“余额加 10”“库存减 1”这样的补丁重复一次就会多执行一次。HTTP 的方法名不会替你获得幂等性，业务动作的内容才会。[RFC 5789：PATCH 方法](https://www.rfc-editor.org/rfc/rfc5789.html)

对容易被网络重试的写操作，应明确制定策略：将更新表达为“设置为目标值”，使用请求幂等键，或以业务流水/版本号保证重复提交不会造成重复扣款。把增量命令伪装成普通资料更新，通常只是在给未来的故障复盘预埋素材。

### `POST`：创建与动作

`POST /users` 常用于创建用户，`POST /orders/{id}/cancel` 也可表示一个不适合简单 CRUD 的命令动作。`POST` 并不等价于“任何写操作都放这里”；只是当语义是创建、提交、触发处理或非幂等命令时，它通常比强行套用 `PUT`/`PATCH` 更诚实。

HTTP 规范把 `PUT` 描述为以请求内容替换目标资源当前表示，并将 `PUT`、`DELETE` 和安全方法列为幂等方法；“幂等”约束的是请求的预期服务器效果，不要求重复请求得到完全相同的响应正文或日志记录。[RFC 9110：HTTP 语义](https://www.rfc-editor.org/rfc/rfc9110.html)

## 四、实现部分更新的关键：区分“未传”与“明确传 null”

部分更新最常见、也最隐蔽的 Bug，是把“客户端没有提交这个字段”误当成“客户端希望写入默认值或 `None`”。解决它不能靠猜测，而要用专用的更新模型和 `exclude_unset=True`。

下面给出一个可运行的内存示例。真实项目只需把字典读写换成仓储或 ORM 操作，输入白名单与合并逻辑仍然成立：

```python
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/users", tags=["用户"])


class UserOut(BaseModel):
    id: int
    display_name: str
    bio: str | None
    email: str
    role: str


class UserPatch(BaseModel):
    # 这两个字段允许省略；省略与显式传 null 的含义不同。
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=500)


users: dict[int, dict[str, object]] = {
    7: {
        "id": 7,
        "display_name": "Yukino",
        "bio": "student",
        "email": "yukino@example.com",
        "role": "user",
    }
}


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    user_id: Annotated[int, Path(gt=0)],
    payload: UserPatch,
) -> UserOut:
    stored = users.get(user_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提交一个可修改字段",
        )

    # `changes` 只可能包含 UserPatch 中明确声明的可写字段。
    stored.update(changes)
    return UserOut.model_validate(stored)
```

三个请求的结果分别是：

| 请求体 | `changes` | `bio` 的最终结果 |
| --- | --- | --- |
| `{}` | `{}` | 不修改；本例返回 `400` |
| `{"display_name": "Yuki"}` | `{"display_name": "Yuki"}` | 保持原来的 `"student"` |
| `{"bio": null}` | `{"bio": None}` | 清空为 `null` |

这正是 `exclude_unset=True` 的价值：它排除的是**没有在请求中出现**的字段，不是值为 `None` 的字段。若改用 `exclude_none=True`，第三个请求会把 `bio: null` 丢掉，客户端便无法清空可空字段；看上去只是一个参数不同，语义却已经错了。

### 更新模型应是可写字段的白名单

注意 `UserPatch` 中没有 `id`、`email`、`role`。这不是因为这些字段不存在，而是因为当前端点不允许修改它们。更危险的写法是：

```python
# 错误示例：把客户端提交的任意字段直接写入实体。
for field, value in payload.items():
    setattr(user, field, value)
```

一旦请求体里出现 `role: "admin"`、`owner_id`、`balance`、`password_hash` 等字段，这段代码就可能绕过所有业务约束。API 输入模型首先是安全边界，其次才是文档和类型提示。

### 需要做交叉字段校验时，不要只依赖 `update`

有些规则依赖更新后的完整状态，例如“公开资料必须有昵称”“状态已归档的文章不可再发布”“开始时间必须早于结束时间”。此时应按顺序做：

```text
读取当前资源
  -> 校验权限与资源状态
  -> 获取 exclude_unset 后的变化集
  -> 合并为候选新状态
  -> 校验跨字段和领域规则
  -> 在事务中持久化
  -> 返回受响应模型约束的结果
```

不要只验证单个入参后立刻 `update()`。单字段格式正确，不等于整份资源仍然满足业务不变量。

## 五、`PATCH` 请求体没有唯一格式

HTTP `PATCH` 规定了“应用部分修改”的方法语义，但不强制所有 API 使用同一种补丁文档格式。常见选择有：

| 格式 | 常见 Content-Type | 特点 | 适用情况 |
| --- | --- | --- | --- |
| 领域专用 JSON | `application/json` | 由 `UserPatch` 等模型声明可改字段 | 大多数业务 API 的首选 |
| JSON Merge Patch | `application/merge-patch+json` | 对象字段合并，`null` 常表示删除/清空 | 简单 JSON 文档更新 |
| JSON Patch | `application/json-patch+json` | 用 `add`、`remove`、`replace` 等操作数组表达 | 需要精确数组路径操作、通用文档补丁 |

本文的 `UserPatch` 是第一种：**领域专用更新 DTO**。它可让 OpenAPI 文档、Pydantic 校验、权限白名单和业务名称保持一致，通常也是业务服务最清楚的选择。

不要因为方法叫 `PATCH` 就默认客户端可以发送 JSON Patch 操作数组；除非端点明确声明并实现该媒体类型和语义。尤其对列表字段，`{"tags": ["new"]}` 是“替换所有标签”“追加一个标签”还是“合并集合”，没有一条 HTTP 动词能替你作决定，必须写进接口契约。

## 六、并发更新：部分更新仍可能覆盖彼此

`PATCH` 只更新部分字段，并不自动消除并发问题。若两个客户端都先读取同一资源，再分别修改同一个字段，后提交的一方仍可能覆盖先提交的一方。

一种常见方案是乐观并发控制：

```text
GET /users/7
  -> 响应头：ETag: "user-7-v12"

PATCH /users/7
If-Match: "user-7-v12"
{
  "bio": "backend engineer"
}
```

服务端在更新时比较当前版本。版本不匹配则拒绝请求并返回 `412 Precondition Failed`，客户端重新读取后由用户决定如何处理冲突。也可以在数据库更新条件中加入 `version = :expected_version`，受影响行数为零时视为冲突。

无论采用 ETag、版本列还是业务修订号，关键都是把“基于哪个版本修改”写入协议。否则所谓部分更新只是在降低字段覆盖概率，而不是解决并发一致性。

## 七、FastAPI 中常用的请求方法

FastAPI 为常见 HTTP 方法提供对应的路径操作装饰器：`@router.get()`、`@router.post()`、`@router.put()`、`@router.patch()`、`@router.delete()`、`@router.options()`、`@router.head()` 和 `@router.trace()`。官方入门文档将它们统称为路径操作装饰器，并强调 FastAPI 不会强制某个动词必须实现何种业务语义。[FastAPI：路径操作装饰器](https://fastapi.tiangolo.com/tutorial/first-steps/)

实际业务 API 最常用的是前五种，其余方法要按协议需求谨慎使用。

### `GET`：读取资源或查询集合

```python
@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int) -> UserOut:
    ...


@router.get("")
def list_users(page: int = 1, page_size: int = 20) -> list[UserOut]:
    ...
```

`GET` 应表达读取意图，不应用来触发扣款、发送邮件、删除数据等有副作用的动作。HTTP 将 `GET` 定义为安全方法，调用方和缓存层会据此做预取、重试或缓存等处理。查询条件通常放在 query string，例如 `/users?page=1&page_size=20&active=true`。

不要依赖 `GET` 请求体。FastAPI 可以在极端场景接受它，但 HTTP 规范对 GET body 的语义没有普遍定义，Swagger UI 不会为它展示请求体，许多代理也不支持这种用法。复杂筛选若确实不适合 query 参数，应设计一个清晰的 `POST /users/search` 或领域查询端点，而不是让 GET 带着一个没人敢正确转发的 body。

### `POST`：创建资源或提交命令

```python
@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserOut:
    ...
```

创建成功通常返回 `201 Created`，并可附带 `Location` 头指向新资源。若服务只接受了一个异步任务、尚未完成实际处理，则用 `202 Accepted` 更准确。

由于网络超时后客户端可能不知道服务端是否已经处理请求，创建订单、支付、发货等 `POST` 端点往往需要 `Idempotency-Key` 等去重机制。客户端“重发一次试试”这种看似无害的行为，在没有幂等保护时可能真的再创建一笔业务记录。

### `PUT`：以完整表示替换

```python
@router.put("/{user_id}", response_model=UserOut)
def replace_user(user_id: int, payload: UserReplace) -> UserOut:
    ...
```

`UserReplace` 一般要求客户端提供创建该资源所需的完整可写字段。若团队决定用 `PUT` 做部分更新，也不是 FastAPI 的错误；但必须在 OpenAPI 描述、模型必填性、默认值与客户端约定中明确说明。否则用户以为是替换，服务端却悄悄保留旧值，接口语义会变得难以预测。

### `PATCH`：部分修改

```python
@router.patch("/{user_id}", response_model=UserOut)
def patch_user(user_id: int, payload: UserPatch) -> UserOut:
    ...
```

这是本文的重点：专用 Patch 模型、`exclude_unset=True`、权限白名单、领域校验、事务和并发控制，缺一不可。对“设置某字段为目标值”类 PATCH，建议有意设计为幂等；对“增加”“扣减”“推进状态”类命令，则应认真考虑是否应使用专门的 `POST` 动作端点与去重键。

### `DELETE`：删除资源

```python
from fastapi import Response


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int) -> Response:
    ...
```

`DELETE` 表示删除目标资源。它通常设计为幂等：重复删除后资源都处于“不存在”状态；但首次返回 `204`、后续返回 `404` 并不违反幂等性，因为幂等关注最终效果而非每次响应必须逐字相同。是否做软删除、能否恢复、关联资源如何处理，仍应由业务规则明确。

### `HEAD`：只取响应头

`HEAD` 与 `GET` 的语义相近，但服务端不发送响应内容，适合检查资源是否存在、比较 `ETag`、获知 `Content-Length` 等。它不应被当作“轻量 GET 但可以修改数据”。HTTP 规范要求 HEAD 不带响应内容；若 API 需要公开这种能力，可以显式注册 `@router.head(...)` 并测试代理与框架行为。[RFC 9110：HEAD](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.2)

### `OPTIONS`：能力协商与 CORS 预检

浏览器进行跨域的非简单请求时，可能先发起 `OPTIONS` 预检。FastAPI 项目一般应使用 `CORSMiddleware` 配置允许的来源、方法和头，而不是为每个业务资源手写一个“总是返回成功”的 OPTIONS 端点：

```python
from fastapi.middleware.cors import CORSMiddleware


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://console.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "If-Match"],
)
```

这里将 `PATCH` 和 `If-Match` 放入允许列表，是因为浏览器会检查实际请求的方法和自定义头是否被服务器允许。CORS 只约束浏览器，不是认证或授权机制；非浏览器客户端可以直接请求你的 API，因此权限校验仍必须在服务端执行。

### `TRACE` 与 `CONNECT`：普通业务 API 通常不需要

`TRACE` 用于诊断请求链路，`CONNECT` 用于建立隧道。它们不属于通常的 REST 业务端点集合；除非你正在实现代理、网关或有明确协议需求，否则不要为了“方法齐全”而开放它们。少暴露一条没有业务意义的攻击面，并不会损失任何架构品位。

## 八、安全性、幂等性与缓存：方法选择背后的约束

HTTP 方法的三个性质常被混为一谈，实际含义不同：

| 性质 | 问题 | 典型方法 |
| --- | --- | --- |
| 安全（safe） | 请求的预期语义是否仅用于读取 | `GET`、`HEAD`、`OPTIONS` |
| 幂等（idempotent） | 同一请求执行多次，预期最终效果是否相同 | 安全方法、`PUT`、`DELETE` |
| 可缓存（cacheable） | 响应是否可以被缓存复用 | 常见是 `GET`、`HEAD`，但还取决于响应缓存指令 |

安全不表示服务端绝不能写访问日志、更新监控指标；它表示客户端请求该方法的意图不是改变资源状态。幂等也不表示响应必须相同，例如第一次删除返回 `204`、第二次返回 `404`，资源的预期终态仍是“已删除”。RFC 9110 对这些语义作了明确定义，代理和客户端的重试策略正是建立在这些约定之上。[RFC 9110：安全与幂等方法](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2)

在接口设计中，可以用下面的判断顺序：

1. 这是读取资源，还是提交会改变状态的命令？读取优先 `GET`。
2. 是创建子资源/触发动作，还是替换一个已知 URI 的资源？前者通常 `POST`，后者考虑 `PUT`。
3. 是完整表示还是部分字段变化？完整替换用 `PUT`，部分更新用 `PATCH`。
4. 重试同一请求会怎样？如果可能重复扣费、重复创建，就补上幂等键、版本控制或其他去重语义。
5. 浏览器是否跨域？若是，CORS 配置是否包括实际使用的 `PATCH` 方法和请求头？

这套判断不是教条。HTTP 标准本身也承认应用可以定义资源特定的处理方式；但若偏离常见语义，应在接口名称、文档和错误响应中把差异写得足够清楚，不能要求每个调用方靠阅读实现源码来猜。

## 九、为 `PATCH` 端点写测试

部分更新至少应测试“只改提交字段”“明确 null 清空字段”“不允许越权字段”“资源不存在”“空更新”“并发版本冲突”等情况。下面是前述内存示例的基础测试：

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_patch_keeps_unsent_fields() -> None:
    response = client.patch("/users/7", json={"display_name": "Yuki"})

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Yuki"
    assert body["bio"] == "student"
    assert body["role"] == "user"


def test_patch_null_clears_nullable_field() -> None:
    response = client.patch("/users/7", json={"bio": None})

    assert response.status_code == 200
    assert response.json()["bio"] is None


def test_patch_rejects_server_managed_field() -> None:
    response = client.patch("/users/7", json={"role": "admin"})

    # Pydantic 默认忽略未知字段时，此请求会变成空更新并被端点拒绝。
    assert response.status_code == 400
```

最后一个测试的具体结果取决于模型的 `extra` 配置。对于安全敏感 API，可以在更新模型中配置 `extra="forbid"`，让未知字段直接产生 `422`；或者保留默认忽略策略，但像本例一样在空变化集时拒绝。无论选择哪一种，都应有测试锁定契约。最不可取的是未知字段被静默忽略，同时端点仍返回“更新成功”，因为客户端会误以为敏感修改已经生效或失败原因无从判断。

## 十、总结

`@router.patch` 的作用可以浓缩为一句话：**它将一个 Python 函数注册为处理指定路径 `PATCH` 请求的 FastAPI 路径操作，并把相关契约信息纳入 OpenAPI 文档。**它不是数据库更新函数，也不会自动替你实现部分更新。

写一个可靠的 `PATCH` 端点，需要同时做到：

- 用 `APIRouter` 前缀和路径操作装饰器清晰登记路由；
- 用专门的 `Patch` Pydantic 模型作为可写字段白名单；
- 用 `model_dump(exclude_unset=True)` 区分未传字段和明确的 `null`；
- 读取当前资源后合并变化集，再校验权限、资源状态和跨字段规则；
- 在明确的事务边界中持久化，并用 `response_model` 限制输出；
- 对有并发修改风险的资源使用 ETag 或版本号；
- 根据操作真实语义选择 `GET`、`POST`、`PUT`、`PATCH`、`DELETE`，而不是把它们都当成不同拼写的“请求”。

当一个端点的 HTTP 方法、请求模型、响应模型、状态码和并发策略能说同一种语言时，接口才真正算得上可维护。至于把所有更新都写成 `POST /do-something`，当然也能运行；只是那更像是在要求未来的每位调用者从遗迹里考古，而不是在设计协议。
