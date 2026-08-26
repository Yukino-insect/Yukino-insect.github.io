+++
date = '2026-08-26T22:30:00+08:00'
draft = false
title = 'Python 异常处理：except as、raise from、异常链与错误边界'
+++

下面这段代码很短，却包含了 Python 异常处理中几个最重要的概念：捕获特定异常、通过 `as` 取得异常对象、把底层异常转换为业务异常，以及使用 `from` 保留异常因果链。

```python
try:
    payload = response.json()
except ValueError as error:
    raise RuntimeError(
        f"接口未返回 JSON，HTTP {response.status_code}: {response.text[:500]}"
    ) from error
```

它并不是“发生错误就换一个错误信息”这么简单。它表达的是：**底层 JSON 解析失败，但在当前模块的语义里，更有价值的错误是“接口返回了不符合约定的响应”；同时，原始解析错误不能丢失。**

异常处理的目标不是把报错藏起来，更不是用 `except Exception: pass` 让程序假装一切正常。好的异常处理需要回答三个问题：发生了什么、当前层能否处理、上层还需要知道什么。本文以这段 HTTP 响应解析代码为起点，系统说明 `try`、`except ... as ...`、`raise ... from ...`、重新抛出、异常链、`else`、`finally` 与自定义异常的使用边界。

## 一、先拆开这段代码

```python
try:
    payload = response.json()
except ValueError as error:
    raise RuntimeError(
        f"接口未返回 JSON，HTTP {response.status_code}: {response.text[:500]}"
    ) from error
```

可以按执行顺序理解：

1. 执行 `response.json()`，尝试把响应体解析为 Python 对象。
2. 若没有异常，结果赋给 `payload`，跳过 `except`。
3. 若解析过程抛出与 `ValueError` 匹配的异常，进入 `except`。
4. `as error` 把当前异常实例绑定到名字 `error`。
5. 创建一个带有 HTTP 状态码和响应片段的新 `RuntimeError`。
6. `from error` 明确说明：新异常由刚才的解析异常直接导致。
7. 新异常向调用方传播；若无人处理，Traceback 同时展示原异常和新异常。

这段代码只包住 `response.json()`，范围很小。这样做很重要：`except ValueError` 只会处理“JSON 解析步骤”产生的匹配异常，不会意外把后续业务代码中的 `ValueError` 也误标成“接口未返回 JSON”。`try` 块越窄，错误含义越准确。

## 二、异常、`try` 与 `except` 的基本流程

Python 中，异常是在执行过程中出现错误或异常条件时打断正常控制流的一种机制。

```python
def divide(left: int, right: int) -> float:
    return left / right


result = divide(10, 0)
```

除以零会抛出 `ZeroDivisionError`。若没有合适的 `except` 处理，它会沿调用栈向外传播，最终打印 Traceback 并结束当前程序流程。

```python
try:
    result = divide(10, 0)
except ZeroDivisionError:
    result = 0.0
```

`try` 语句的核心规则是：

- `try` 块正常结束时，匹配的 `except` 块不会执行。
- `try` 块抛出异常后，其中剩余语句不再执行。
- Python 从上到下寻找第一个匹配的 `except`。
- 找到匹配项后执行该处理器，之后继续执行整个 `try` 语句之后的代码。
- 未匹配的异常继续向外传播。

异常类型本身有继承关系。`ValueError` 是 `Exception` 的子类，`Exception` 又是 `BaseException` 的子类。`except ValueError` 只处理 `ValueError` 及其子类；`except Exception` 会处理大多数常规应用异常；但通常不应捕获 `BaseException`，因为 `KeyboardInterrupt`、`SystemExit` 等控制程序退出的异常也继承自它。

```text
BaseException
├── KeyboardInterrupt
├── SystemExit
└── Exception
    ├── ValueError
    ├── TypeError
    ├── OSError
    ├── RuntimeError
    └── ...
```

## 三、`except ValueError as error` 中的 `as error`

### 1. `error` 是异常实例，不是异常类型

下面的写法：

```python
except ValueError as error:
    ...
```

含义是：若捕获到 `ValueError` 或其子类异常，就把**这一次实际抛出的异常对象**绑定给变量 `error`。

```python
try:
    int("not-a-number")
except ValueError as error:
    print(type(error))
    print(str(error))
    print(error.args)
```

输出类似：

```text
<class 'ValueError'>
invalid literal for int() with base 10: 'not-a-number'
("invalid literal for int() with base 10: 'not-a-number'",)
```

因此可以用 `error` 做几件事：

- 记录原始错误信息：`logger.warning("parse failed: %s", error)`。
- 根据异常携带的数据决定恢复策略。
- 作为异常链的原因：`raise NewError(...) from error`。
- 在确有必要时检查类型或特定属性。

变量名并不强制必须叫 `error`。`exc`、`err` 都很常见：

```python
except OSError as exc:
    ...
```

其中 `exc` 常被用作 exception 的简写。选择一个团队一致、能一眼看出含义的名字即可；这不是需要发挥创造力的地方。

### 2. 不需要异常对象时，可以省略 `as`

如果处理逻辑不需要查看原异常，也不需要把它作为原因传递，可以直接写：

```python
try:
    value = int(user_input)
except ValueError:
    value = 0
```

但在“转换异常”的场景中，省略 `as error` 就无法使用 `from error` 保留原始原因。因此你的示例需要它。

### 3. 不要依赖 `error` 在 `except` 之外继续存在

异常变量的适用范围应当视为 `except` 块内部。Python 会在异常处理结束后清除 `except ... as name` 中绑定的名字，以帮助打破异常对象、Traceback 和局部变量之间可能形成的引用环。

错误示例：

```python
try:
    int("bad")
except ValueError as error:
    message = str(error)

print(error)  # 不应这样使用；通常会得到 NameError
```

若确实需要错误信息，应在处理块内提取并保存需要的数据：

```python
try:
    int("bad")
except ValueError as error:
    message = str(error)

print(message)
```

更常见的做法是直接记录日志或通过 `raise ... from error` 继续传播，而不是把异常对象带出当前处理边界。

## 四、`raise`：主动抛出异常

Python 的 `raise` 用于主动产生异常：

```python
def parse_age(value: str) -> int:
    age = int(value)
    if age < 0:
        raise ValueError("age must not be negative")
    return age
```

可以抛出异常实例：

```python
raise ValueError("invalid age")
```

也可以抛出异常类，Python 会在需要时创建实例：

```python
raise ValueError
```

实际业务代码中推荐前一种，因为错误信息是定位问题的重要上下文。请让消息描述失败条件，而不是只写 `"error"`、`"failed"` 这种几乎没有信息量的句子。

### 1. 裸 `raise`：重新抛出当前异常

在 `except` 块中不带参数地写 `raise`，表示**原样重新抛出当前正在处理的异常**：

```python
try:
    payload = response.json()
except ValueError:
    logger.exception("response JSON decoding failed")
    raise
```

这适合当前层只负责记录、监控或补充操作，却不准备改变异常的语义。裸 `raise` 会保留原异常类型与原始 Traceback。

不要把它和下面的写法混淆：

```python
except ValueError as error:
    raise error
```

两者都会把 `ValueError` 继续抛出，但裸 `raise` 才是表达“原样继续传播”的惯用写法；`raise error` 会在当前行再次抛出该对象，Traceback 的呈现可能多出当前重新抛出的帧。没有特别目的时，使用裸 `raise`。

## 五、为什么要写 `from error`

### 1. 转换异常时保留因果关系

回到最初代码：

```python
try:
    payload = response.json()
except ValueError as error:
    raise RuntimeError("接口未返回 JSON") from error
```

这里不是简单地“再抛一个异常”，而是在建立显式异常链：

```text
底层原因：JSON 解析失败（ValueError）
  -> 当前层语义：接口响应不符合 JSON 契约（RuntimeError）
```

`from error` 会把原异常赋给新异常的 `__cause__` 属性。未处理时，Python 会先输出原始异常，再显示：

```text
The above exception was the direct cause of the following exception:
```

随后输出新异常。这样调用方看到的是对当前业务层更有意义的 `RuntimeError`，排查者仍能看到 JSON 解码器为什么失败。

可以通过代码观察：

```python
try:
    try:
        int("not-a-number")
    except ValueError as error:
        raise RuntimeError("input is not a valid integer") from error
except RuntimeError as outer_error:
    print(type(outer_error).__name__)           # RuntimeError
    print(type(outer_error.__cause__).__name__) # ValueError
```

### 2. 不写 `from` 也会有链，但语义不同

若在处理异常时直接抛出新异常：

```python
try:
    int("not-a-number")
except ValueError:
    raise RuntimeError("input is not a valid integer")
```

Python 仍会保存原异常，但它是隐式上下文，存放在 `__context__` 中。Traceback 典型提示是：

```text
During handling of the above exception, another exception occurred:
```

这只说明“处理前一个异常时，又发生了新异常”。它不一定表示新异常由旧异常**直接导致**；例如 `except` 块中的日志格式化又因为别的 Bug 失败，也会形成这种隐式上下文。

`raise NewError(...) from error` 则是明确的因果声明，Traceback 会使用 “direct cause” 提示。对于把基础设施异常转换为领域或边界异常的代码，应优先使用显式 `from`。

| 写法 | 新异常类型 | 原异常关系 | Traceback 语义 |
| ---- | ---------- | ---------- | -------------- |
| `raise` | 不变 | 原异常继续传播 | 原样重新抛出 |
| `raise NewError(...)` | 改变 | 隐式 `__context__` | 处理期间又发生异常 |
| `raise NewError(...) from error` | 改变 | 显式 `__cause__` | 原异常是直接原因 |
| `raise NewError(...) from None` | 改变 | 隐藏展示的上下文 | 对外只展示新异常 |

### 3. `from None`：有意隐藏底层上下文

有时低层异常只是实现细节，对当前调用方没有帮助，甚至会暴露不应展示的内部信息。可以写：

```python
def get_required_setting(settings: dict[str, str], name: str) -> str:
    try:
        return settings[name]
    except KeyError:
        raise ValueError(f"missing required setting: {name}") from None
```

`from None` 会抑制默认 Traceback 中的异常上下文展示。最终用户看到的是更清晰的 `ValueError`，不会看到实现细节 `KeyError`。

但不要把 `from None` 当作“让日志干净”的万能办法。调试、监控和内部服务调用往往需要底层原因；在这些边界上，保留 `from error` 通常更有价值。若信息中可能含有密钥、Cookie、用户数据或完整上游响应，应当在构造新消息时进行脱敏，而不是仅靠隐藏异常链。

## 六、回到 HTTP JSON 示例：更健壮的写法

假设 `response` 来自 `requests`。`Response.json()` 在 JSON 解码失败时会抛出 JSON 解码相关异常，捕获 `ValueError` 是一种较宽的兼容写法；若代码明确依赖 `requests`，捕获 `requests.exceptions.JSONDecodeError` 的意图会更清楚。

```python
import requests


class UpstreamResponseError(RuntimeError):
    """上游接口的响应不符合本服务的契约。"""


def parse_json_response(response: requests.Response) -> object:
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as error:
        preview = response.text[:500]
        raise UpstreamResponseError(
            "接口未返回合法 JSON："
            f"HTTP {response.status_code}，响应前 500 个字符：{preview!r}"
        ) from error
```

这里有几个改进点：

- 使用自定义 `UpstreamResponseError`，调用方可以按“上游响应异常”这一语义处理，而不是捕获过于笼统的 `RuntimeError`。
- `preview!r` 使用 `repr()` 风格输出，换行、制表符等不可见字符会更明显。
- 限制为前 500 个字符，避免把完整 HTML 错误页或大响应写进异常和日志。
- `from error` 保留解析器给出的行、列、字符位置等底层信息。

不过，`response.text` 可能包含敏感信息，例如访问令牌、身份证号或服务端错误页中的内部数据。生产代码应按实际协议脱敏，必要时仅记录长度、内容类型和请求 ID：

```python
raise UpstreamResponseError(
    "接口未返回合法 JSON："
    f"HTTP {response.status_code}，"
    f"Content-Type={response.headers.get('Content-Type')!r}，"
    f"Request-Id={response.headers.get('X-Request-Id')!r}"
) from error
```

### 1. 先处理 HTTP 状态码，再解析 JSON

若约定只有 2xx 响应才表示成功，通常先调用 `raise_for_status()`：

```python
def fetch_profile(url: str) -> dict[str, object]:
    response = requests.get(url, timeout=5)

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise UpstreamResponseError(
            f"调用用户接口失败，HTTP {response.status_code}"
        ) from error

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise UpstreamResponseError(
            f"用户接口返回非 JSON，HTTP {response.status_code}"
        ) from error

    if not isinstance(payload, dict):
        raise UpstreamResponseError("用户接口 JSON 顶层不是对象")

    return payload
```

HTTP 成功不代表响应一定是合法 JSON；JSON 合法也不代表字段满足业务契约。因此可以把失败分为三层：

```text
网络 / HTTP 层：连接失败、超时、4xx、5xx
  -> 内容编码层：不是合法 JSON
    -> 业务契约层：JSON 结构或字段不符合预期
```

每一层都应抛出对本层有意义的异常，并在转换底层异常时保留原因。这样调用方能选择统一处理 `UpstreamResponseError`，日志中又不会丢失根因。

### 2. 不要把整个函数都放进一个宽泛 `try`

不推荐：

```python
try:
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    payload = response.json()
    return transform_profile(payload)
except Exception as error:
    raise UpstreamResponseError("请求用户接口失败") from error
```

它会把网络错误、HTTP 错误、JSON 错误，甚至 `transform_profile()` 里本应修复的 `KeyError`、`TypeError` 都伪装成同一种“上游接口失败”。排查时会失去关键分类，也会掩盖自己代码的 Bug。

推荐按操作与异常类型缩小边界：

```python
try:
    response = requests.get(url, timeout=5)
except requests.RequestException as error:
    raise UpstreamResponseError("请求用户接口时发生网络错误") from error

try:
    response.raise_for_status()
except requests.HTTPError as error:
    raise UpstreamResponseError(
        f"用户接口返回 HTTP {response.status_code}"
    ) from error

try:
    payload = response.json()
except requests.exceptions.JSONDecodeError as error:
    raise UpstreamResponseError("用户接口响应不是合法 JSON") from error

return transform_profile(payload)
```

如果 `transform_profile` 失败，异常应按它自己的语义暴露或在它自己的边界转换。异常处理不是把所有错误收进同一个袋子，然后把袋口扎紧。

## 七、`else` 与 `finally`：成功路径和清理路径

### 1. `else`：仅在 `try` 成功时执行

`else` 在 `try` 块没有抛出异常时执行：

```python
try:
    payload = response.json()
except ValueError as error:
    raise UpstreamResponseError("接口响应不是 JSON") from error
else:
    return transform_profile(payload)
```

这样 `transform_profile(payload)` 不在 `try` 块中。若转换逻辑自身抛出 `KeyError` 或 `TypeError`，不会被错误地当作 JSON 解析错误捕获。

`else` 并非每次都必须写，但它能自然地缩小受保护代码范围，特别适合“只有一两行可能抛出预期异常，后续成功处理不属于该异常语义”的情况。

### 2. `finally`：无论成功失败都执行清理

`finally` 用来做必须执行的清理工作：

```python
file = open("report.txt", encoding="utf-8")
try:
    content = file.read()
finally:
    file.close()
```

无论 `file.read()` 成功、失败，还是上层代码从 `try` 中 `return`，`file.close()` 都会执行。

但文件、锁、数据库连接等资源更推荐使用上下文管理器：

```python
with open("report.txt", encoding="utf-8") as file:
    content = file.read()
```

`with` 会在离开代码块时完成清理，通常比手写 `try/finally` 更简洁且不易遗漏。

不要在 `finally` 中随意 `return`、`break`、`continue`，也不要抛出无关的新异常。它们可能覆盖原本正在传播的异常，让真正的错误消失。清理代码本身也应尽量可靠、短小、可预期。

## 八、自定义异常：让调用方按业务语义处理

当模块需要把多个底层异常统一为一个稳定的领域概念时，定义自定义异常很有价值：

```python
class UpstreamResponseError(RuntimeError):
    """上游服务返回的内容无法满足本模块的响应契约。"""


class UpstreamUnavailableError(RuntimeError):
    """上游服务不可访问，或未返回成功 HTTP 状态。"""
```

调用方可以按业务决策捕获：

```python
try:
    profile = fetch_profile(url)
except UpstreamUnavailableError:
    return cached_profile()
except UpstreamResponseError as error:
    logger.error("upstream contract violation: %s", error)
    raise
```

自定义异常通常继承 `Exception` 或其合适子类。若想表达“运行时服务失败”，继承 `RuntimeError` 可以；若异常只是一个新的业务分类、没有额外运行时含义，直接继承 `Exception` 也完全合理。

异常类型是 API 的一部分。它让调用方不必靠匹配错误字符串来决定重试、降级、返回 4xx 还是报警。字符串是写给人看的，类型才是给程序分支用的。

## 九、异常处理的常见错误

### 1. 捕获过宽后静默忽略

错误：

```python
try:
    payload = response.json()
except Exception:
    payload = {}
```

这会吞掉比 JSON 错误广得多的问题，也可能让系统在错误输入下继续以空数据运行，直到在更远的地方出现更难理解的异常。

至少应捕获预期类型、记录上下文，并清楚决定是恢复还是继续传播。

### 2. 转换异常时丢失原始原因

不够好：

```python
try:
    payload = response.json()
except ValueError:
    raise UpstreamResponseError("接口响应不是 JSON")
```

更好：

```python
try:
    payload = response.json()
except ValueError as error:
    raise UpstreamResponseError("接口响应不是 JSON") from error
```

后者可以从 Traceback 直接看到原始 JSON 解码错误，定位效率差别很大。

### 3. 用错误字符串控制程序逻辑

不推荐：

```python
except RuntimeError as error:
    if "不是 JSON" in str(error):
        ...
```

应使用不同的异常类型、结构化字段或明确返回值。错误消息可能因国际化、库版本或文案调整而改变，不能承担程序协议的职责。

### 4. 记录日志后又在每一层重复记录

异常会向上传播。每一层都使用 `logger.exception(...)` 再 `raise`，很容易在同一个请求中打印多份几乎相同的完整 Traceback。

通常应选择一个边界记录完整异常：例如 Web 框架的统一异常处理器、任务消费者入口或命令行入口；中间层在需要时补充上下文，使用 `raise ... from error` 继续传播。日志不是越多越好，重复的堆栈只会让真正的信号被淹没。

## 十、总结

最初的代码：

```python
try:
    payload = response.json()
except ValueError as error:
    raise RuntimeError(
        f"接口未返回 JSON，HTTP {response.status_code}: {response.text[:500]}"
    ) from error
```

体现了一个很实用的异常处理模式：**捕获边界处可预期的底层异常，补充当前层的业务上下文，显式保留原始异常原因，然后继续向上层传播。**

- `except ValueError as error` 中的 `error` 是本次抛出的异常实例。
- 裸 `raise` 原样重新抛出当前异常，适合只记录不转换的场景。
- `raise NewError(...) from error` 建立显式异常链，新的 `__cause__` 指向原异常。
- `raise NewError(...) from None` 会抑制 Traceback 中的底层上下文展示，应谨慎使用。
- `else` 用来放只应在 `try` 成功后执行的代码；`finally` 用来保证清理，但资源管理通常优先使用 `with`。
- `try` 应尽量小，`except` 应尽量具体；不要用宽泛捕获把自己的程序错误伪装成外部故障。

异常转换并不是掩盖错误，而是翻译错误：把 JSON 解码器知道的“第几列无法解析”，翻译成你的业务边界知道的“上游接口违反了响应契约”。而 `from error` 的价值就在于，翻译之后仍然保留原文。
