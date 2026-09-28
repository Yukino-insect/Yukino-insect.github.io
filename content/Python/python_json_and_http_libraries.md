+++
date = '2026-09-28T00:00:00+08:00'
draft = false
title = 'Python 常用 JSON 与 HTTP 库：从数据编解码到可靠请求'
+++

Python 程序经常要做两件事：把内存里的数据变成可传输、可保存的文本；再通过 HTTP 与另一个服务交换这些文本。前者通常使用标准库 `json`，后者可能使用标准库 `urllib.request`，也可能使用第三方的 `requests` 或 `httpx`。

它们看似只是几行调用，但真正可靠的代码要明确回答更多问题：数据类型能否无损表示？服务是否真的返回了成功状态？网络卡住时多久放弃？连接是否能复用？异步程序会不会被同步 I/O 阻塞？请求失败后能不能安全重试？这一篇从这些边界出发，建立一套可迁移到脚本、服务端和客户端程序中的基础用法。

## JSON：数据格式，而不是 Python 对象的完整副本

JSON（JavaScript Object Notation）是一种文本数据格式。它只有对象、数组、字符串、数字、布尔值和空值六类结构；而 Python 有 `datetime`、`Decimal`、`set`、`bytes`、数据类和任意自定义对象。因此，JSON 编解码本质上是在两套类型系统之间做**有边界的映射**，不是把任意 Python 对象原封不动地“存起来”。

标准库 `json` 的默认对应关系如下：

| JSON | Python |
| ---- | ------ |
| object | `dict` |
| array | `list` |
| string | `str` |
| number | `int` 或 `float` |
| true / false | `True` / `False` |
| null | `None` |

其中 `tuple` 在编码时会变成 JSON 数组，解码后自然只能得到 `list`；字典键最终也必须是字符串。这意味着 `loads(dumps(value))` 不一定与原来的 `value` 完全相等。若数据模型需要保留精确类型，应设计明确的字段格式，或使用相应的模型校验层，而不是期待 JSON 自动猜对。

### `dumps`、`loads` 与文件版本的 `dump`、`load`

名字中的 `s` 可以理解为 string：`dumps()` 把对象编码成字符串，`loads()` 从字符串（也接受 `bytes` / `bytearray`）解码。没有 `s` 的两个函数则面向文件对象。

```python
import json

payload = {
    "name": "雪乃",
    "enabled": True,
    "tags": ["python", "http"],
    "quota": None,
}

text = json.dumps(payload, ensure_ascii=False, indent=2)
print(text)

restored = json.loads(text)
assert restored["name"] == "雪乃"

with open("settings.json", "w", encoding="utf-8") as file:
    json.dump(payload, file, ensure_ascii=False, indent=2)

with open("settings.json", encoding="utf-8") as file:
    settings = json.load(file)
```

`ensure_ascii=False` 让中文等非 ASCII 字符直接输出，便于阅读；它不改变字符串的语义。`indent=2` 适合配置文件和日志样本，网络传输若确实在意体积可省略缩进，或设置 `separators=(",", ":")`。不要把多次 `json.dump()` 连续写入同一个普通文件后期待它仍是一个合法 JSON 文档：`{"a": 1}{"b": 2}` 并不是一个 JSON 值。需要逐行记录时，应明确采用 JSON Lines（每行一个完整 JSON）格式。

```python
import json

events = [{"event": "created"}, {"event": "deleted"}]

with open("events.jsonl", "w", encoding="utf-8") as file:
    for event in events:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

with open("events.jsonl", encoding="utf-8") as file:
    for line in file:
        event = json.loads(line)
        print(event["event"])
```

### 精度、非法数值与键的陷阱

JSON 小数通常会解为二进制浮点数 `float`，这对金额一类需要十进制精确性的值并不合适。可在解码时指定 `parse_float=Decimal`：

```python
import json
from decimal import Decimal

order = json.loads('{"price": 19.90}', parse_float=Decimal)
assert order["price"] == Decimal("19.90")
```

另一个容易被忽略的边界是 `NaN`、`Infinity` 和 `-Infinity`。它们不是严格 JSON 的合法数字，但 Python 标准库为了兼容常见 JavaScript 实现，默认可以编码和解码它们。对外协议、签名内容或持久化格式应选择严格模式：编码时使用 `allow_nan=False`；解码时用 `parse_constant` 明确拒绝。

```python
import json

def reject_non_standard_number(value: str):
    raise ValueError(f"不接受非标准 JSON 数值：{value}")

json.dumps({"rate": float("nan")}, allow_nan=False)
# ValueError: Out of range float values are not JSON compliant

json.loads('{"rate": NaN}', parse_constant=reject_non_standard_number)
```

字典键也是信息丢失点。JSON 对象的键总是字符串，Python 的 `{1: "one"}` 编码再解码后会变成 `{"1": "one"}`。不要使用 `skipkeys=True` 去“解决”不支持的键，它会悄悄丢掉条目；更合理的是在建模阶段将键规范化，或让 `TypeError` 暴露数据错误。

### 编码 `datetime`、`Decimal` 与自定义对象

`json.dumps()` 能处理基础容器和基本标量，但遇到 `datetime`、`Decimal`、`UUID`、`set` 或实例对象会抛出 `TypeError`。最直接的扩展点是 `default`：它接收不认识的对象，必须返回一个 JSON 可编码的值；若仍然不能处理，应抛出 `TypeError`，不可胡乱转换为字符串来掩盖模型错误。

```python
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

def encode_extra(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"无法编码为 JSON：{type(value).__name__}")

record = {
    "created_at": datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc),
    "amount": Decimal("19.90"),
    "labels": {"new", "paid"},
}

text = json.dumps(record, default=encode_extra, ensure_ascii=False)
print(text)
```

这里的 `Decimal` 被编码成字符串并非偶然：JSON 的 number 没有“十进制定点小数”这一类型。协议应明示金额是字符串、最小货币单位整数，还是允许损失精度的 number；然后让生产者和消费者遵守同一个约定。若许多调用都要遵循同一规则，可以继承 `json.JSONEncoder` 并重写 `default()`，但对少量场景，一个小而明确的 `default` 函数通常更容易阅读。

反序列化时也有 `object_hook`，它会接收每一个已经解析出的 JSON 对象：

```python
import json
from datetime import datetime

def decode_event(value: dict):
    if value.get("type") == "login" and "at" in value:
        return {
            "type": "login",
            "at": datetime.fromisoformat(value["at"]),
            "user_id": value["user_id"],
        }
    return value

event = json.loads(
    '{"type": "login", "at": "2026-09-28T08:00:00+00:00", "user_id": 7}',
    object_hook=decode_event,
)
```

但来自网络、文件上传或第三方系统的 JSON 不应借助 `object_hook` 根据某个字段动态导入模块、查找类名或执行任意构造逻辑。JSON 是不可信输入，`object_hook` 应只完成白名单内的无副作用转换；随后仍应做字段、类型、长度和业务规则校验。需要将请求体绑定为 Web API 模型时，通常交给框架的校验模型更合适；可结合站内的 [FastAPI 基础到工程实践](frameworks/fastapi/00-fastapi-from-basics-to-engineering.md) 阅读。

### 解析不等于验证：JSON 的安全边界

`json.loads()` 的职责只是语法解析：它能告诉你文本是否符合 JSON，并不能证明字段合法、身份可信、金额合理或对象可安全使用。可靠的输入处理至少要有以下层次：

1. **限制输入来源和大小**：先读取受限长度的响应或上传内容。特别大的数组、深层嵌套和巨大的字符串都可能消耗大量内存和 CPU。
2. **捕获格式错误**：针对 `json.JSONDecodeError` 返回或记录“格式无效”，不要把调用栈暴露给用户。
3. **验证结构与语义**：确认根节点类型、必填键、字段类型、长度、枚举值和相互约束。`dict` 并不等于一个有效的业务对象。
4. **明确数值规则**：金额用 `Decimal` 或整数最小单位；对外协议禁用 `NaN` / `Infinity`；不要依赖浮点数相等比较。
5. **不把 JSON 当执行载体**：不要对外部数据使用 `eval()`、`pickle.loads()`，也不要把类型标签直接映射成可调用对象。

JSON 相比 `pickle` 的重要优势，是它只描述数据而不会在标准解析过程中执行 Python 代码；不过“不会执行代码”不等于“不会造成资源耗尽”或“数据天然可信”。这类区别，若忽略了，写再短的代码也只是在为未来的故障节省字符数而已。

## HTTP 客户端共有的模型

无论使用哪一个库，一次 HTTP 请求都由相同的概念构成：方法、URL、查询参数、请求头、请求体、超时，以及响应的状态码、响应头和响应体。

```text
客户端
  └─ method + URL + params + headers + body + timeout
                         │
                         ▼
                      网络与服务端
                         │
                         ▼
  ┌─ status code + headers + body
响应
```

常见状态码类别值得先记住：

| 状态码范围 | 含义 | 客户端通常应做什么 |
| ---------- | ---- | ------------------ |
| `2xx` | 请求成功 | 继续解析预期响应 |
| `3xx` | 重定向 | 明确是否允许跟随，注意认证头和目标主机 |
| `4xx` | 请求不符合要求或无权限 | 修正参数、认证或业务流程；通常不盲目重试 |
| `5xx` | 服务端暂时或永久故障 | 视操作幂等性、退避策略和服务约定决定是否重试 |

`response.json()` 或 `json.loads()` 都只负责解析响应体，**不会因为 HTTP 状态码是 404 或 500 而自动失败**。正确顺序通常是：设置超时，发送请求，检查状态码，限制或检查响应内容，再解析 JSON，最后校验业务结构。

## 标准库 `urllib.request`：零依赖但更接近底层

`urllib.request` 随 Python 提供，适合不希望增加依赖的脚本、受限运行环境或需要使用标准库 opener / handler 机制的场景。它的抽象较少，因此 URL 参数编码、请求对象、错误处理和响应读取都需要写得更明确一些。

### 发送 GET 请求和查询参数

查询参数应使用 `urllib.parse.urlencode()`，不要自己拼接字符串。它会处理空格、中文和保留字符的百分号编码。

```python
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

params = urlencode({"q": "Python HTTP", "page": 1})
url = f"https://api.example.com/search?{params}"

request = Request(
    url,
    headers={"Accept": "application/json", "User-Agent": "example-client/1.0"},
    method="GET",
)

with urlopen(request, timeout=5) as response:
    status = response.status
    charset = response.headers.get_content_charset() or "utf-8"
    body = response.read().decode(charset)

if not 200 <= status < 300:
    raise RuntimeError(f"请求失败，HTTP {status}")

data = json.loads(body)
```

`urlopen()` 返回的响应对象应放进 `with`，以便及时关闭连接和底层资源。务必显式提供 `timeout`；没有超时的网络调用可能长时间阻塞程序。此处的 `timeout` 主要控制套接字操作，并不等同于精细区分连接、读取、写入和连接池等待的完整超时模型。

### 发送 JSON 请求与处理异常

发送 JSON 时，先用 UTF-8 编码为 `bytes`，并同时声明 `Content-Type: application/json`。仅仅传入一个看起来像 JSON 的字符串却没有正确请求头，服务端未必会按 JSON 处理。

```python
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

payload = json.dumps({"name": "Ada"}, ensure_ascii=False).encode("utf-8")
request = Request(
    "https://api.example.com/users",
    data=payload,
    headers={
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    },
    method="POST",
)

try:
    with urlopen(request, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
except HTTPError as error:
    # HTTPError 同时带有响应体；只记录受控长度，避免日志被错误页淹没。
    detail = error.read(4096).decode("utf-8", errors="replace")
    raise RuntimeError(f"服务返回 HTTP {error.code}: {detail}") from error
except URLError as error:
    raise RuntimeError(f"无法连接服务：{error.reason}") from error
```

这里 `HTTPError` 表示服务器已经给出 HTTP 错误响应（例如 404、500），它是 `URLError` 的子类，因此应先捕获前者。`URLError` 常包装 DNS 解析、连接失败等网络层错误。超时在不同底层条件下也可能表现为 `URLError` 的原因；生产代码应根据业务需要保留原始异常链，而不要把所有异常一概伪装成“网络错误”。

`urllib.request` 并不意味着“落后”，只是它提供的是偏底层、偏标准库的积木。若需要舒适的 JSON 参数、会话、细粒度超时、同步与异步统一接口或测试替身，下面两个第三方库往往更合适。

## `requests`：同步 HTTP 的常用选择

`requests` 是广泛使用的同步 HTTP 客户端。它将查询参数、表单、JSON 请求体、响应解码和 cookie 等常见工作封装得较为直接。安装方式是：

```bash
python -m pip install requests
```

### 一次明确、可检查的请求

下面的写法涵盖了一次 JSON API 调用最重要的基本要素：使用 `params` 而不是手工拼 URL，使用 `json=` 而不是自行序列化字符串，设置超时，先检查状态码，再解析 JSON。

```python
import requests

try:
    response = requests.get(
        "https://api.example.com/articles",
        params={"page": 1, "size": 20},
        headers={"Accept": "application/json"},
        timeout=(3.05, 10),
    )
    response.raise_for_status()
    payload = response.json()
except requests.Timeout as error:
    raise RuntimeError("请求超时") from error
except requests.ConnectionError as error:
    raise RuntimeError("无法建立网络连接") from error
except requests.HTTPError as error:
    raise RuntimeError(f"服务返回错误状态：{error.response.status_code}") from error
except requests.JSONDecodeError as error:
    raise RuntimeError("服务响应不是合法 JSON") from error
```

`timeout=(3.05, 10)` 分别表示连接超时与读取超时；也可传一个数字作为两者共用的超时值。最重要的一点是：**`requests` 默认没有请求超时**。不写 `timeout` 的示例也许短了一点，却可能让工作线程、命令行任务或 Web 服务永远等待一个永远不会回来的响应。

`raise_for_status()` 会在 `4xx` / `5xx` 响应上抛出 `HTTPError`，`2xx` 不会抛出。它不验证响应 JSON 的结构，也不会使重定向、业务错误码或 204 空响应自动变成异常。响应预期为空时不要调用 `response.json()`；响应可能为 HTML 错误页时，即使状态是 200，也要按照协议校验 `Content-Type` 和数据结构。

发送 JSON 请求则使用 `json=`：

```python
import requests

response = requests.patch(
    "https://api.example.com/users/7",
    json={"nickname": "Yukino"},
    headers={"Accept": "application/json"},
    timeout=10,
)
response.raise_for_status()
```

`json=` 会负责 JSON 编码并设置合适的 `Content-Type`；`data=` 则用于表单或原始请求体。两者语义不同，不应为了“都能发数据”而混用。部分更新使用 `PATCH` 时，对缺失字段、`null`、幂等性与并发控制还有额外约定，可参阅 [FastAPI 的 @router.patch：部分更新、请求方法与接口设计](frameworks/fastapi/01-patch-and-http-methods.md)。

### `Session`：连接复用与共享请求配置

循环中反复调用模块级 `requests.get()` 虽然可行，却难以统一认证头、cookie 和连接复用。面向同一服务的多个请求，使用 `requests.Session()` 更清楚；它会在可复用的条件下保留 cookie 和底层连接池。

```python
import requests

with requests.Session() as session:
    session.headers.update({
        "Accept": "application/json",
        "Authorization": "Bearer <token>",
    })

    first = session.get("https://api.example.com/profile", timeout=5)
    first.raise_for_status()

    second = session.get("https://api.example.com/projects", timeout=5)
    second.raise_for_status()
```

`Session` 并不是把所有内容永久缓存，也不意味着可以无限期、跨线程随意共享。它保存了有状态信息和连接池；当其生命周期结束时应调用 `close()`，最简单的办法就是像上例一样使用 `with`。若应用有并发需求，应为各并发单元或受控的客户端层设计清楚的会话所有权，而不是把一个可变全局 Session 当作万能对象。

### 重试不是一个通用的 `except` 块

`requests` 默认不会自动重试普通请求。即使配置了重试，也不应把“任何异常都再发一次”当成默认策略。重试可能让服务端收到重复写操作，例如重复创建订单、重复扣费或重复发送消息。

一个安全的决策顺序是：

1. 判断操作语义是否幂等。读取通常较适合重试；`PUT` / `DELETE` 常被设计为幂等；`POST` / `PATCH` 是否安全则必须由具体接口、幂等键或去重机制决定。
2. 区分失败类型。DNS、连接建立失败、短暂的 502 / 503 / 504 可能可重试；大多数参数错误、认证失败和 4xx 不应该自动重试。
3. 限制次数并使用指数退避与抖动，尊重服务端的 `Retry-After`。无限重试只会将一次故障扩大为持续压力。
4. 保留超时。重试不能取代超时；没有超时的第一次尝试就已经足够让重试策略失去意义。

需要在 `requests` 中统一设置重试时，可以通过其底层 `urllib3` 的 `HTTPAdapter` 配置。下面只是一个**只重试幂等读取操作**的示例，状态码、次数和退避参数都应按服务协议调整：

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=(502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
    respect_retry_after_header=True,
)

adapter = HTTPAdapter(max_retries=retry)

with requests.Session() as session:
    session.mount("https://", adapter)
    response = session.get("https://api.example.com/catalog", timeout=5)
    response.raise_for_status()
```

如果一次 `POST` 已经送达服务端但客户端在读取响应时超时，客户端通常无法仅靠异常判断服务端是否已执行成功。这时需要接口支持幂等键、可查询的操作状态或业务唯一约束；客户端的重试配置无法凭空补上这部分协议设计。

## `httpx`：同步与异步都可使用的 HTTP 客户端

`httpx` 提供与 `requests` 相近的同步接口，同时原生支持 `async` / `await`。当普通脚本或同步程序访问 HTTP 服务时，可以使用 `httpx.Client`；当程序已经运行在异步事件循环中，例如异步 Web 端点、爬取协调程序或并发 API 聚合任务中，使用 `httpx.AsyncClient`，避免同步网络 I/O 阻塞事件循环。

```bash
python -m pip install httpx
```

### 同步 `Client`

不要把模块级便利函数当成大量请求的长期客户端。连续访问同一服务时创建一个 `Client`，可以复用连接池和默认配置，并在结束时关闭：

```python
import httpx

with httpx.Client(
    base_url="https://api.example.com",
    headers={"Accept": "application/json"},
    timeout=httpx.Timeout(10.0, connect=3.0),
) as client:
    response = client.get("/articles", params={"page": 1})
    response.raise_for_status()
    articles = response.json()

    created = client.post("/articles", json={"title": "HTTP 基础"})
    created.raise_for_status()
```

`httpx.Timeout(10.0, connect=3.0)` 表示其他阶段使用 10 秒、连接阶段使用 3 秒。HTTPX 还可以分别指定 `read`、`write` 和 `pool` 超时，适合对下载、上传或连接池饱和有不同要求的客户端。HTTPX 默认启用了超时机制；但显式写出符合业务的限制仍然更清楚，因为“库的默认值”不是服务等级目标。

### 异步 `AsyncClient`

异步版本的请求必须用 `await`，客户端则应用 `async with` 管理。最常见的错误是，在 `async def` 中直接调用同步 `requests.get()`；这会把运行该协程的事件循环线程阻塞住，使同一进程中的其他协程无法及时运行。

```python
import httpx

async def fetch_profile(user_id: int) -> dict:
    timeout = httpx.Timeout(10.0, connect=3.0)

    async with httpx.AsyncClient(
        base_url="https://api.example.com",
        timeout=timeout,
        headers={"Accept": "application/json"},
    ) as client:
        response = await client.get(f"/users/{user_id}")
        response.raise_for_status()
        return response.json()
```

上例适合一个短小、独立的函数。若同一应用会反复发出请求，应在应用的受控生命周期中创建一个长期存活的 `AsyncClient`，在关闭阶段调用 `aclose()`；不要每个请求都创建一个新客户端，否则连接池无法复用。异步应用的创建与关闭阶段可使用上下文管理器或框架生命周期机制，`@asynccontextmanager` 的语义可见 [Python 的 @contextmanager 与 @asynccontextmanager：用生成器管理资源、异常与取消](Python 的 contextmanager 与 asynccontextmanager：用生成器管理资源、异常与取消.md)。

多个互不依赖的请求可并发等待：

```python
import asyncio
import httpx

async def fetch_dashboard() -> tuple[dict, dict]:
    async with httpx.AsyncClient(
        base_url="https://api.example.com",
        timeout=5,
    ) as client:
        profile_task = client.get("/profile")
        notices_task = client.get("/notices")
        profile, notices = await asyncio.gather(profile_task, notices_task)

        profile.raise_for_status()
        notices.raise_for_status()
        return profile.json(), notices.json()
```

并发不等于无限并发。大量任务同时访问同一依赖会耗尽本地套接字、连接池或远端配额；应根据服务能力配置连接限制、信号量、超时和取消策略。异步的价值是等待 I/O 时让出执行权，并不会使远端服务变得无限快。

### HTTPX 的响应、流式读取与异常

HTTPX 与 `requests` 一样，`response.json()` 不会替你检查状态码，仍然应调用 `raise_for_status()`。捕获异常时可先关注三个层次：`httpx.TimeoutException` 代表超时，`httpx.RequestError` 覆盖请求传输过程的错误，`httpx.HTTPStatusError` 则由 `raise_for_status()` 对非成功状态抛出。

下载大响应体时，不要无条件读取进内存。使用 `stream()` 增量读取，并在上下文结束时关闭响应：

```python
import httpx

with httpx.stream(
    "GET",
    "https://example.com/large-file",
    timeout=30,
) as response:
    response.raise_for_status()
    with open("large-file.bin", "wb") as file:
        for chunk in response.iter_bytes():
            file.write(chunk)
```

异步版本对应 `async with client.stream(...)` 与 `async for chunk in response.aiter_bytes()`。使用手动流式模式时，响应关闭责任属于调用者；遗漏关闭会让连接无法回到连接池，最终表现为难以解释的连接耗尽。这里并没有什么神秘之处，只是资源所有权没有被诚实地写出来而已。

HTTPX 也可设置 `follow_redirects=True` 跟随重定向，但应基于协议决定。对携带凭据的请求尤其要注意重定向后的目标地址、认证信息是否应转发，以及 `POST` 在某些重定向状态下的方法变化；“能自动跳过去”从来不是安全策略本身。

## 如何选择：不要把库名当成架构

下表总结的是常见选择，而不是不可逾越的等级制度：

| 场景 | 更合适的起点 | 理由 |
| ---- | ------------ | ---- |
| 无第三方依赖的小脚本、受限环境 | `urllib.request` | 标准库可用，控制更直接 |
| 普通同步脚本、命令行工具、传统同步应用 | `requests` | API 成熟直接，生态广泛 |
| 同时需要同步与异步客户端，或异步服务内发请求 | `httpx` | 同时提供 `Client` 与 `AsyncClient` |
| 框架已有推荐客户端或 SDK | 遵循框架 / SDK | 连接、认证、重试和可观测性往往已统一 |

选择 `requests` 还是 `httpx` 的首要标准不是“哪个更流行”，而是调用位置是否已经是异步环境、是否需要统一客户端生命周期、是否有 HTTP/2 或细粒度超时等需求。反过来，若只有一个偶发的同步脚本任务，专门引入异步模型往往只会增加复杂度。技术选型的体面，不在于工具有多新，而在于它是否诚实匹配问题的形状。

## 一份可复用的请求检查清单

无论使用哪个库，在代码审查或故障排查时都可以逐项核对：

- 是否使用了正确的 HTTP 方法、URL 和 `params` 编码，而不是手工拼接不可信输入？
- 是否为每次请求设置了合理超时，并区分了连接、读取、写入或整体时限的需求？
- 是否在解析响应体前检查状态码，并处理空响应、非 JSON 响应和业务错误结构？
- 是否在多个请求间复用受控的 Session / Client，并在生命周期结束时关闭它？
- 是否避免在 `async def` 内执行同步网络 I/O？
- 是否仅对可安全重试的失败和操作做有限次数、带退避的重试？
- 是否限制了不可信 JSON 和大响应的大小，并在解析后完成结构与业务校验？
- 是否避免在日志中记录 `Authorization`、Cookie、完整令牌、密码或敏感响应体？

## 总结

- `json` 负责数据的文本编解码，不负责业务校验；基础类型之外需要明确的编码约定，金额、`NaN`、非字符串键和不可信输入尤其要谨慎。
- `urllib.request` 是零依赖的标准库 HTTP 工具，但需要更明确地处理请求对象、编码、响应关闭和异常。
- `requests` 适合同步 HTTP 调用；一定显式设置 `timeout`，用 `raise_for_status()` 检查错误，并使用 `Session` 管理重复请求的连接与状态。
- `httpx` 同时支持同步与异步；在异步程序中使用 `AsyncClient`、`await` 和受控生命周期，避免阻塞事件循环并复用连接池。
- 超时、状态检查、资源关闭、输入校验和重试语义不是“生产环境才需要的附加项”；它们正是一个 HTTP 调用从演示代码走向可靠代码的基本组成。
