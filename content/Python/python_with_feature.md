+++
date = '2026-08-27T10:10:00+08:00'
draft = false
title = 'Python with 语句：上下文管理器、资源清理与常见用法'
+++

Python 的 `with` 很常见：读文件时会用，拿锁时会用，数据库事务、临时目录、网络会话和异步连接也会用。

```python
with open("config.yaml", encoding="utf-8") as file:
    content = file.read()
```

初看它像一种“更短的打开文件语法”，但它真正表达的是更重要的约束：**进入代码块时获取或建立某种资源，离开代码块时，无论成功、失败还是提前返回，都要按约定完成收尾。**

这里的“资源”不只包括文件句柄。锁需要释放，数据库事务需要提交或回滚，临时目录需要清理，网络连接需要关闭，计时器需要停止。若每处都手写清理分支，漏掉一种控制流只是时间问题；`with` 的价值，就是把这件本该可靠完成的事变成语言结构的一部分。

## 一、最常见的用法：读取和写入文件

读取文本文件：

```python
from pathlib import Path


config_path = Path("config.yaml")
with config_path.open("r", encoding="utf-8") as file:
    content = file.read()
```

写入文本文件：

```python
from pathlib import Path


output_path = Path("report.txt")
with output_path.open("w", encoding="utf-8") as file:
    file.write("任务完成\n")
```

离开 `with` 块时，文件会自动关闭。即使块内读取失败、写入失败或抛出其他异常，关闭动作仍会执行。

```python
with open("data.txt", encoding="utf-8") as file:
    first_line = file.readline()
    if not first_line:
        return "empty"  # 即使在这里 return，文件也会先关闭
```

这比下面的写法更可靠：

```python
file = open("data.txt", encoding="utf-8")
content = file.read()
file.close()
```

后者一旦 `read()` 抛出异常，执行流不会到达 `file.close()`，文件句柄便可能长时间保持打开。对于一次性脚本，这也许暂时看不出后果；对长期运行的服务、批量任务或 Windows 上会被文件锁影响的工作流，这种侥幸不会总是温和。

## 二、`with` 与 `try/finally` 的关系

`with` 的核心可理解为 `try/finally` 的结构化写法。下面两段代码在“确保关闭文件”这一目标上等价：

```python
with open("data.txt", encoding="utf-8") as file:
    content = file.read()
```

```python
file = open("data.txt", encoding="utf-8")
try:
    content = file.read()
finally:
    file.close()
```

`finally` 的规则是：无论 `try` 块正常结束、`return`、`break`、`continue`，还是抛出异常，都会在控制流真正离开前执行。`with` 正是利用这一保证，让资源清理与资源使用靠在一起。

不过，把 `with` 单纯理解为“自动执行 `close()`”还不够准确。并非所有上下文管理器都有 `close()`；数据库事务可能提交或回滚，锁会释放，临时目录会删除。更一般地说，`with` 会在退出时调用对象约定的退出逻辑。

## 三、上下文管理器协议：`__enter__` 和 `__exit__`

能用于 `with` 的对象叫作**上下文管理器**（context manager）。它需要实现两个特殊方法：

```python
class Example:
    def __enter__(self):
        ...

    def __exit__(self, exc_type, exc_value, traceback):
        ...
```

概念上，这段代码：

```python
with manager as value:
    body()
```

大致会被解释为：

```python
manager_object = manager
value = manager_object.__enter__()
try:
    body()
except BaseException as error:
    suppress = manager_object.__exit__(
        type(error), error, error.__traceback__
    )
    if not suppress:
        raise
else:
    manager_object.__exit__(None, None, None)
```

这是为了理解而简化的伪代码，但关键步骤没有变：

1. 求值 `with` 后的表达式，取得上下文管理器对象。
2. 调用 `__enter__()`；其返回值会绑定给 `as` 后的名字。
3. 执行缩进块中的业务代码。
4. 无论块内是否发生异常，调用 `__exit__()`。
5. 若块内有异常，`__exit__()` 返回真值时可表示“该异常已被处理”；返回假值或 `None` 时，异常继续向外传播。

因此，`as file` 并不等于把 `open()` 的返回值机械赋给 `file`；严格说，`file` 是 `__enter__()` 的返回值。文件对象恰好在进入时返回自身，所以日常使用中看起来没有区别。

## 四、自己实现一个上下文管理器

下面用一个计时器说明协议如何工作：

```python
from __future__ import annotations

from time import perf_counter


class Timer:
    def __enter__(self) -> Timer:
        self.started_at = perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        elapsed_ms = (perf_counter() - self.started_at) * 1000
        print(f"elapsed: {elapsed_ms:.1f} ms")
        return False
```

使用：

```python
with Timer() as timer:
    result = sum(range(1_000_000))
```

执行顺序是：

```text
Timer().__enter__()  -> 记录开始时间，并返回 timer
执行 sum(...)
Timer.__exit__(...)  -> 输出耗时
```

无论 `sum(...)` 成功还是抛出异常，`__exit__` 都会执行。这个例子的 `__exit__` 返回 `False`，表示不吞掉异常；若块内发生异常，计时结束后异常仍照常抛给调用方。

### 1. 退出方法能看到异常信息

可以据此在退出时决定提交、回滚或记录失败：

```python
class Transaction:
    def __enter__(self) -> "Transaction":
        self.connection.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()
        return False
```

规则很直观：`exc_type is None` 说明块内没有异常，因此提交；否则回滚。最后关闭连接，无论成功失败都不应遗漏。

真实数据库库往往已经提供自己的事务上下文管理器，应优先使用库的 API。上例的意义在于说明：`with` 不只适合“关闭一个东西”，它可以根据块内结局选择不同的收尾动作。

## 五、`__exit__` 返回 `True` 会抑制异常，必须谨慎

下面的上下文管理器会忽略 `FileNotFoundError`：

```python
class IgnoreMissingFile:
    def __enter__(self) -> "IgnoreMissingFile":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return exc_type is FileNotFoundError
```

```python
with IgnoreMissingFile():
    open("not-exist.txt", encoding="utf-8")

print("仍会执行")
```

因为 `__exit__` 对 `FileNotFoundError` 返回 `True`，异常不会继续传播。

这种能力很强，也因此不应随便使用。过宽地返回 `True`，例如无条件吞掉任何异常，会把真实程序错误伪装成成功：

```python
class BadContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return True  # 不要这样做
```

除非上下文管理器的职责就是有选择地恢复某类可预期错误，否则应返回 `False` 或 `None`，让异常继续传播。清理资源和隐瞒错误是两件不同的事，不能因为它们都发生在退出阶段就把它们混在一起。

## 六、`with ... as ...` 与变量作用域不是一回事

`with` 不会创建新的块级作用域。下面代码合法：

```python
with open("config.yaml", encoding="utf-8") as file:
    config_text = file.read()

print(config_text)
print(file.closed)  # True
```

离开块后，`config_text` 和 `file` 这两个名字通常都仍可在当前函数或模块作用域中访问；区别是 `file` 指向的文件资源已经关闭，所以不能再读取：

```python
file.read()  # ValueError: I/O operation on closed file.
```

所以应当区分：

```text
变量名是否可见：由 Python 的作用域规则决定
资源是否可用：由上下文管理器的退出逻辑决定
```

这也是下面配置加载代码能正常工作的原因：

```python
with config_path.open("r", encoding="utf-8") as file:
    config = yaml.safe_load(file) or {}

# 文件关闭；内存中的 config 字典仍可校验和返回。
validate_config(config)
```

Python 中 `if`、`for`、`while`、`try` 与 `with` 的普通缩进块也不会创建块级作用域；函数才是最常见的局部作用域边界。关于这一点的详细推理，可参阅同栏目中关于 `with as` 与作用域的文章。

## 七、文件处理中的几个实用模式

### 1. 指定编码和换行

文本文件应明确编码，尤其是配置、日志、中文内容或跨平台项目：

```python
with open("notes.txt", "r", encoding="utf-8") as file:
    text = file.read()
```

写入 CSV 等需要稳定换行语义的文件时，可能还要指定 `newline=""`：

```python
import csv


with open("users.csv", "w", encoding="utf-8", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["id", "name"])
```

`newline=""` 是 `csv` 模块推荐的用法，可避免不同平台出现额外空行或换行转换问题。

### 2. 二进制文件

图片、压缩包等二进制文件使用 `rb` 或 `wb`：

```python
from pathlib import Path


with Path("archive.zip").open("rb") as source:
    data = source.read()

with Path("archive-copy.zip").open("wb") as target:
    target.write(data)
```

大文件不要一次 `read()` 到内存；可逐块复制：

```python
from pathlib import Path


def copy_file(source_path: Path, target_path: Path) -> None:
    with source_path.open("rb") as source, target_path.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
```

这里同时使用了两个上下文管理器。退出时会按相反顺序清理：先退出 `target`，再退出 `source`。通常无需手工关心这个细节，但当多个资源存在依赖关系时，逆序释放正是合理的默认规则。

### 3. 原子写入的思路

直接以 `"w"` 打开目标文件会立刻截断旧内容。若程序在写到一半崩溃，配置或数据文件可能损坏。对重要文件，更可靠的思路是：写入同目录临时文件，完成并刷新后再替换目标文件。

```python
from pathlib import Path
from tempfile import NamedTemporaryFile


def write_text_atomically(path: Path, content: str) -> None:
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)

    temporary_path.replace(path)
```

`with` 保证临时文件先关闭，再执行替换；某些平台不允许替换仍打开的文件。实际需要更强的持久性保证时，还应考虑 `flush()`、`os.fsync()`、权限保留和失败后的临时文件清理。原子写入不是一行魔法，但将资源生命周期写清楚是正确的起点。

## 八、锁：确保并发临界区一定释放

锁是 `with` 的另一项典型用途：

```python
import threading


lock = threading.Lock()
counter = 0


def increment() -> None:
    global counter
    with lock:
        counter += 1
```

它等价于手写：

```python
lock.acquire()
try:
    counter += 1
finally:
    lock.release()
```

若临界区中抛出异常，`with lock:` 仍会释放锁；否则其他线程可能永久等待，最后表现为一次令人不太愉快的“程序怎么卡住了”。

锁块应当尽量短，只保护真正共享状态的操作。不要在持锁期间进行长时间网络请求、磁盘 I/O 或用户交互，否则并发程序会在最不该排队的地方排队。

## 九、数据库事务与网络资源

许多库为自己的资源提供上下文管理器，但进入与退出的具体含义由库决定，不能只凭 `with` 的外形猜测。

以 SQLite 为例，连接对象可以作为上下文管理器使用：

```python
import sqlite3


connection = sqlite3.connect("app.db")
try:
    with connection:
        connection.execute("INSERT INTO audit_log(message) VALUES (?)", ("started",))
finally:
    connection.close()
```

这里 `with connection:` 管理的是事务：正常离开时提交，发生异常时回滚；它**不会自动关闭连接**。因此连接本身仍要在外层 `finally` 中关闭，或使用能同时表达关闭语义的库 API。这个例子提醒我们：先阅读具体库文档，弄清 `__enter__` 和 `__exit__` 究竟承诺什么。

常见第三方 HTTP 客户端也可能提供：

```python
# 伪代码，具体接口请以所用 HTTP 库的文档为准
with HttpClient(timeout=5) as client:
    response = client.get(url)
```

通常这意味着会话、连接池或底层连接在退出时关闭。若客户端需要跨很多请求复用，不应在每个请求里频繁创建上下文；应让它覆盖一个明确的应用生命周期，并在服务停止时退出。

## 十、临时目录与 `contextlib`

标准库 `tempfile.TemporaryDirectory` 会在退出时删除目录及其内容：

```python
from pathlib import Path
from tempfile import TemporaryDirectory


with TemporaryDirectory(prefix="report-") as directory:
    report_path = Path(directory) / "report.txt"
    report_path.write_text("generated", encoding="utf-8")
    # 在这里可以安全使用临时文件

# 临时目录及其中内容已被清理
```

这比自己创建随机目录、在所有成功与失败分支里写删除逻辑可靠得多。

`contextlib` 模块还提供多种构建和组合上下文管理器的工具。

### 1. `contextlib.closing`

有些对象有 `.close()` 方法，却没有实现上下文管理器协议。可以用 `closing()` 包装：

```python
from contextlib import closing


with closing(create_legacy_resource()) as resource:
    resource.process()
```

退出时 `closing` 会调用 `resource.close()`。优先使用资源库原生提供的 `with` 支持；`closing` 适合确实只缺少上下文管理器包装的旧接口。

### 2. `contextlib.suppress`

若某个可预期异常在当前语义中可以忽略，可以写：

```python
from contextlib import suppress
from pathlib import Path


with suppress(FileNotFoundError):
    Path("temporary.txt").unlink()
```

它相当于一个非常窄的 `try/except FileNotFoundError: pass`。异常类型必须具体；不要写：

```python
with suppress(Exception):
    dangerous_operation()
```

这会吞掉网络故障、类型错误和程序 Bug。`suppress` 是让一个明确无害的例外安静离开，不是把错误处理问题埋进地毯下面。

### 3. `contextlib.nullcontext`

当某段代码有时接收一个已经打开的资源、有时接收路径并自行打开时，`nullcontext` 能统一写法：

```python
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO


def read_first_line(source: Path | TextIO) -> str:
    context = (
        source.open("r", encoding="utf-8")
        if isinstance(source, Path)
        else nullcontext(source)
    )

    with context as file:
        return file.readline()
```

当传入路径时，函数负责打开和关闭文件；当传入已打开文件时，`nullcontext` 原样交出它，且退出时不关闭它。资源由谁创建，通常就应由谁负责关闭；这个规则比记住某个技巧更重要。

## 十一、用 `@contextmanager` 简化自定义上下文管理器

若上下文管理器的逻辑适合顺序地写成“进入前做什么、块内使用什么、退出时做什么”，可使用 `contextlib.contextmanager`：

```python
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


@contextmanager
def measure(name: str) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - started_at) * 1000
        print(f"{name} finished in {elapsed_ms:.1f} ms")
```

使用：

```python
with measure("import data"):
    import_data()
```

`yield` 之前相当于 `__enter__`，`yield` 产出的对象相当于 `as` 后得到的值，`yield` 之后的 `finally` 相当于 `__exit__`。把清理放在 `finally` 中仍然是重点：即使 `import_data()` 失败，计时记录也要执行。

若要捕获并处理块内异常，可以在 `yield` 周围写 `try/except`；但若选择不重新抛出，效果就是由该上下文管理器抑制异常。应像实现 `__exit__` 一样，只处理明确预期的类型。

```python
@contextmanager
def ignore_missing_file() -> Iterator[None]:
    try:
        yield
    except FileNotFoundError:
        pass
```

## 十二、动态数量的资源：`ExitStack`

多个资源数量固定时，直接并列写即可：

```python
with open("input.txt", encoding="utf-8") as source, open(
    "output.txt", "w", encoding="utf-8"
) as target:
    target.write(source.read())
```

如果文件列表由运行时配置决定，嵌套或拼接许多 `with` 会很难维护。`contextlib.ExitStack` 可以动态注册任意数量的退出操作：

```python
from contextlib import ExitStack
from pathlib import Path


def read_all(paths: list[Path]) -> list[str]:
    with ExitStack() as stack:
        files = [
            stack.enter_context(path.open("r", encoding="utf-8"))
            for path in paths
        ]
        return [file.read() for file in files]
```

`enter_context()` 会立即进入一个上下文管理器，并把相应退出动作登记到 stack。离开最外层 `with ExitStack()` 时，所有已成功进入的资源按逆序退出。若打开第三个文件失败，前两个已打开的文件仍会被正确关闭；这正是动态资源管理最容易被手写代码遗漏的部分。

`ExitStack` 也可用 `stack.callback(...)` 登记任意清理函数。它适合资源集合、条件性资源和复杂初始化流程；固定的两三个资源则不必为了显得“抽象”而引入它。

## 十三、异步代码中的 `async with`

异步上下文管理器使用 `async with`：

```python
async with session.get(url) as response:
    payload = await response.json()
```

它对应的是 `__aenter__()` 和 `__aexit__()`，两者都可等待。常见场景包括异步 HTTP 响应、异步数据库连接、WebSocket、异步锁和异步文件库。

```python
import asyncio


lock = asyncio.Lock()


async def update_shared_state() -> None:
    async with lock:
        # 修改共享状态；退出时锁会释放
        pass
```

`async with` 不是在普通 `with` 前面随意加一个关键字。只有对象实现异步上下文管理器协议时才能使用；同步文件对象、`threading.Lock` 等仍应使用普通 `with`。同样，异步块中的收尾逻辑也会在异常或取消发生时被等待执行，因此对连接归还、锁释放等资源尤其重要。

## 十四、使用 `with` 时的常见误区

### 1. 认为离开块后变量自动消失

不对。`with` 管理的是资源生命周期，不是变量作用域：

```python
with open("data.txt", encoding="utf-8") as file:
    text = file.read()

print(text)         # 可以
print(file.closed)  # True
```

### 2. 在块外继续使用已经关闭的资源

```python
with open("data.txt", encoding="utf-8") as file:
    pass

file.read()  # 错误：文件已关闭
```

如果后续仍要读取，应把相关读取逻辑留在块内；如果只需数据，应在块内读出并保存数据。

### 3. 用 `with` 包住过大的业务范围

```python
with lock:
    payload = request_remote_service()  # 可能很慢
    update_shared_state(payload)
```

锁仅需要保护共享状态时，网络请求不应包含在临界区中：

```python
payload = request_remote_service()
with lock:
    update_shared_state(payload)
```

同样，数据库事务块不应无必要地覆盖耗时外部调用。资源持有时间越长，竞争、超时与失败影响越大。

### 4. 用异常抑制掩盖问题

无论是自定义 `__exit__` 返回真值，还是 `contextlib.suppress`，都应只处理你可以证明无害且有明确恢复策略的异常。尤其不要捕获 `Exception`、更不要捕获 `BaseException`；后者还会吞掉 `KeyboardInterrupt`、`SystemExit` 等控制流程异常。

### 5. 不清楚第三方库的 `with` 语义

`with` 不意味着“对象一定被关闭”。它只意味着退出时执行该对象定义的 `__exit__`。数据库连接、事务对象、HTTP 响应、会话对象各自可能关闭、提交、回滚、归还连接池或什么也不做。遇到第三方库时，应查看其文档或类型定义，确认资源所有权和退出效果。

## 十五、什么时候应该优先使用 `with`

只要代码满足“获取后必须释放、恢复或完成收尾”的特征，就应先问一句：这个 API 是否提供上下文管理器？常见对象包括：

- 文件、压缩文件、套接字与 HTTP 响应。
- 线程锁、进程锁、异步锁。
- 数据库事务、游标、会话或连接池借用对象。
- 临时目录、临时文件。
- 跟踪、计时、日志上下文和权限切换等成对操作。

相反，如果对象没有外部资源、没有必须配对的结束动作，仅仅是普通数据处理，就不必勉强造一个 `with`。结构应表达真实的生命周期，不是为了让代码看起来更有仪式感。

## 十六、总结

`with` 的本质不是文件语法糖，而是上下文管理协议：

```text
进入上下文：__enter__ / __aenter__
  -> 执行业务代码
退出上下文：__exit__ / __aexit__
  -> 无论成功、异常或提前返回，都完成资源收尾
```

实践中可以这样记忆：

- 文件读写使用 `with open(...) as file`，明确编码并让文件及时关闭。
- 锁使用 `with lock` 或 `async with lock`，确保异常时也释放。
- 数据库和网络资源先确认库的退出语义，尤其区分“结束事务”和“关闭连接”。
- 自定义资源可实现 `__enter__` / `__exit__`，简单场景可用 `@contextmanager`。
- 固定多个资源并列写 `with`；动态资源集合使用 `ExitStack`。
- `__exit__` 返回真值会吞掉异常，除非这是经过设计的恢复行为，否则不要这样做。
- `with` 不创建块级作用域；离开块后变量名可能还在，但资源往往已经不可再用。

把资源的获取、使用和清理放在同一个清晰边界里，代码才能在正常路径之外也保持正确。毕竟，真正考验程序设计的，通常不是“文件成功读完”这一刻，而是它恰好在读到一半失败时，是否仍然愿意把残局收好。
