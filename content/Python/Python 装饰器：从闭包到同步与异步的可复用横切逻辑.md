+++
date = '2026-09-28T00:30:00+08:00'
draft = false
title = 'Python 装饰器：从闭包到同步与异步的可复用横切逻辑'
+++

日志、耗时统计、权限检查、缓存、重试和事务控制，往往不是某一个业务函数独有的工作。若在每个函数开头和结尾都手写一遍，重复很快会遮住真正的业务逻辑，也会让规则在不同位置悄悄分叉。Python 的装饰器（decorator）提供了一种在**不改动调用方式**的前提下，为函数或类附加这类通用行为的机制。

它不是神秘语法，也不是 Java 的注解代理。`@decorator` 只是把一个可调用对象传给另一个可调用对象，并把返回值重新绑定到原名字。理解函数是一等对象、闭包和调用时机后，装饰器的行为其实相当直接。

先记住几个结论：

- `@decorate` 近似等价于 `target = decorate(target)`；装饰发生在函数或类**定义时**，不是每次调用时。
- 最常见的函数装饰器返回一个闭包 `wrapper`，闭包既记住原函数，也保存装饰器配置。
- `functools.wraps` 应当成为默认选择；它保留名称、文档、注解和 `__wrapped__` 等元数据。
- 同步函数和 `async def` 的包装方式不同：异步包装器必须是 `async def`，并且要 `await` 原协程函数。
- 装饰器适合稳定、横切的技术规则；不要用它隐藏核心业务流程或悄悄改变返回类型。

本文只讨论通用 Python 技术。若需要先复习异步资源的进入、退出和取消边界，可阅读 [Python 的 `@contextmanager` 与 `@asynccontextmanager`](Python 的 contextmanager 与 asynccontextmanager：用生成器管理资源、异常与取消.md)；Web 接口中如何组合依赖、异常和异步处理，可继续阅读 [FastAPI 教程：从第一个接口到工程化服务](frameworks/fastapi/00-fastapi-from-basics-to-engineering.md)。

## 一、装饰器为何成立：函数是一等对象

在 Python 中，函数是对象。它可以赋值给变量、放进容器、作为参数传入，也可以作为返回值交给调用方。下面四种写法都围绕同一个事实：函数名只是指向函数对象的一个引用。

```python
def greet(name: str) -> str:
    return f"你好，{name}"


alias = greet
handlers = [greet]


def run(callback, value: str) -> str:
    return callback(value)


print(alias("雪乃"))
print(handlers[0]("八幡"))
print(run(greet, "结衣"))
```

因此，一个名为 `decorate` 的函数完全可以接收 `greet`，构造另一个函数，再把它返回。装饰器并没有获得“修改函数内部字节码”的超能力；通常只是让变量名改为指向一个新的可调用对象。

```text
定义前：greet ───────────────> 原函数对象

装饰后：greet ───────────────> wrapper ───────────────> 原函数对象
```

这也是装饰器既强大又需要克制的原因：外部调用者看到的仍是 `greet(...)`，但中间实际多经过了一层或多层包装。

## 二、从最小例子理解 `@` 语法

先写一个不使用 `@` 的高阶函数：

```python
from collections.abc import Callable


def announce(func: Callable[[str], str]) -> Callable[[str], str]:
    def wrapper(name: str) -> str:
        print("开始调用")
        result = func(name)
        print("调用结束")
        return result

    return wrapper


def welcome(name: str) -> str:
    return f"欢迎，{name}"


welcome = announce(welcome)
print(welcome("读者"))
```

`welcome = announce(welcome)` 会先把原函数交给 `announce`，再把 `wrapper` 绑定回 `welcome`。装饰器语法只是这段赋值的简写：

```python
@announce
def welcome(name: str) -> str:
    return f"欢迎，{name}"
```

两段代码在这个例子中等价。调用顺序则是：先进入 `wrapper`，再调用闭包中记住的 `func`，最后由包装器决定如何返回结果或处理异常。

### 闭包保存了什么

`wrapper` 定义在 `announce` 的内部，却还能在 `announce` 早已返回后访问 `func`。这就是**闭包**：内部函数捕获并保留外层作用域中仍被它使用的变量。

```python
def add_prefix(prefix: str):
    def decorate(func):
        def wrapper(name: str):
            return prefix + func(name)

        return wrapper

    return decorate


formal_welcome = add_prefix("【正式】")
```

`formal_welcome` 是一个装饰器，而它所返回的 `wrapper` 又同时记住了 `prefix` 和 `func`。这正是“带参数装饰器”能够工作的基础。

## 三、为何必须使用 `functools.wraps`

朴素的 `wrapper` 在功能上可以运行，却会替换原函数的元数据：`welcome.__name__` 变成 `wrapper`，文档字符串和类型注解也不再是原函数的。日志、调试器、测试工具、命令行框架、文档生成器和某些 Web 框架都会依赖这些信息。

标准库的 `functools.wraps` 会把必要的属性复制到包装器上，并设置 `__wrapped__` 指向原函数。实际代码应写成：

```python
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def announce(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"开始：{func.__qualname__}")
        try:
            return func(*args, **kwargs)
        finally:
            print(f"结束：{func.__qualname__}")

    return wrapper
```

`*args` 与 `**kwargs` 让包装器接受任意调用形状；`ParamSpec` 和 `TypeVar` 则让类型检查器知道：包装前后参数与返回值仍保持一致。运行时 Python 并不强制这些类型标注，但它们能让 IDE 和静态检查更准确。

`wraps` 并不会神奇地让 `inspect.signature()` 在每一种自定义场景中都变得完美，也不会阻止包装器改变行为；它只是把最重要的可观测元数据保留下来。省略它通常不是简洁，而是留下日后的排障成本。

## 四、带参数的装饰器：多一层不是多余

当使用 `@retry(times=3)` 时，Python 必须先调用 `retry(times=3)` 得到真正的装饰器，再用该装饰器接收目标函数。因此结构有三层：

```text
retry(times=3)
        │ 返回 decorate
        ▼
decorate(target)
        │ 返回 wrapper
        ▼
target 名字重新绑定为 wrapper
```

下面是一个只处理特定瞬态异常的重试装饰器。它刻意没有“捕获所有异常后继续试”的危险行为。

```python
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def retry(*, times: int, retry_on: tuple[type[Exception], ...]):
    if times < 1:
        raise ValueError("times 至少为 1")

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on:
                    if attempt == times:
                        raise
                    print(f"第 {attempt} 次失败，准备重试")

            raise AssertionError("循环不应到达这里")

        return wrapper

    return decorate


@retry(times=3, retry_on=(ConnectionError, TimeoutError))
def fetch_profile(user_id: int) -> dict[str, str]:
    # 此处仅演示；实际实现会请求远端服务。
    return {"id": str(user_id)}
```

重试还涉及退避时间、抖动、总超时、幂等性和可观测性。尤其是创建订单、扣款等非幂等操作，网络超时并不等价于服务端没有成功；盲目重试可能制造重复副作用。装饰器只能组织策略，无法替应用替你判断业务语义。

## 五、多个装饰器与执行时机

多个装饰器从离函数最近的那个开始应用：

```python
@outer
@inner
def work():
    pass
```

等价于：

```python
work = outer(inner(work))
```

这意味着定义阶段先执行 `inner(work)`，再执行 `outer(...)`；调用阶段则先进入 `outer` 的包装器，再进入 `inner` 的包装器，像一层层套上的外壳。

```text
定义阶段：原 work → inner → outer → 绑定给 work
调用阶段：outer 前置 → inner 前置 → 原 work → inner 后置 → outer 后置
```

不要把“装饰器函数被调用”和“包装器被调用”混为一谈。下面的输出揭示了两次时机：模块导入或类定义时打印“注册”，真正执行 `task()` 时才打印“运行”。

```python
from functools import wraps


def trace(label: str):
    print(f"注册装饰器：{label}")

    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"运行前：{label}")
            return func(*args, **kwargs)

        return wrapper

    return decorate


@trace("导入任务")
def task() -> None:
    print("任务本身")
```

因此，装饰器定义阶段不应执行数据库写入、网络请求或依赖尚未准备好的初始化。否则仅仅导入模块就会产生副作用，也会让测试和应用启动顺序变得难以推理。

## 六、日志、计时和异常：一个可靠的同步模板

装饰器常用于观测，而不是代替错误处理。下面的计时器会在成功和失败时都记录耗时；异常仍然自然地抛回调用方。

```python
import logging
from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
logger = logging.getLogger(__name__)


def timed(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = perf_counter()
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("调用失败：%s", func.__qualname__)
            raise
        finally:
            elapsed_ms = (perf_counter() - started) * 1_000
            logger.info("调用结束：%s，耗时 %.2f ms", func.__qualname__, elapsed_ms)

    return wrapper
```

这里使用 `logger.exception` 记录当前异常栈，随后裸 `raise` 保持原始异常和 traceback。将异常记录后直接 `return None`，会把真实失败伪装成普通结果；除非 API 契约明确要求转换为某种错误对象，否则不要在通用装饰器中吞掉异常。

还应避免在日志中直接输出完整的 `args`、`kwargs`：密码、令牌、个人信息和大对象可能就藏在那里。较稳妥的做法是记录函数名、请求标识、耗时和经过脱敏的少量字段。

## 七、装饰 `async def`：必须保留 `await`

协程函数调用后返回的是协程对象；只有被 `await` 才会在事件循环中执行。若用普通 `def wrapper` 直接 `return func(*args, **kwargs)`，表面上仍可能“能跑”，但计时、异常捕获等包裹逻辑只包住了**创建协程对象**的瞬间，而不是其真正执行过程。

正确的异步计时器应当是异步包装器：

```python
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
logger = logging.getLogger(__name__)


def async_timed(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = perf_counter()
        try:
            return await func(*args, **kwargs)
        except Exception:
            logger.exception("异步调用失败：%s", func.__qualname__)
            raise
        finally:
            elapsed_ms = (perf_counter() - started) * 1_000
            logger.info("异步调用结束：%s，耗时 %.2f ms", func.__qualname__, elapsed_ms)

    return wrapper
```

异步代码中也不能为了“统一捕获异常”而吞掉取消。任务取消是一种协作式控制流：清理工作可放在 `finally`，随后应继续传播取消。需要进一步理解资源清理与取消的配合时，可参见前述 [生成器式上下文管理器文章](Python 的 contextmanager 与 asynccontextmanager：用生成器管理资源、异常与取消.md)。

### 同时支持同步与异步函数

一个装饰器可以用 `inspect.iscoroutinefunction` 分支处理两种目标，但返回类型与实现都会更复杂。只有确实需要为同一规则装饰两类函数时才值得如此做；否则拆成 `timed` 和 `async_timed` 更清晰。尤其要避免在异步包装器中调用阻塞 I/O，或在同步函数内偷偷运行新的事件循环。

## 八、类也能被装饰：类装饰器与可调用类

装饰器的目标不限于函数。类定义完毕后，类对象同样会传入装饰器：

```python
def add_repr(cls):
    def __repr__(self):
        values = ", ".join(f"{key}={value!r}" for key, value in vars(self).items())
        return f"{cls.__name__}({values})"

    cls.__repr__ = __repr__
    return cls


@add_repr
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
```

类装饰器常用于注册、补充方法或检查类定义。它直接修改类时要格外谨慎，因为继承、数据描述符、`dataclass` 和类型检查可能都受影响；当类的创建过程本身需要深度定制时，元类或 `__init_subclass__` 才是更合适的工具。

另一种形式是让实例实现 `__call__`。这样的**可调用类**可以保存配置和状态，适合比较复杂、可复用的装饰器：

```python
from collections.abc import Callable
from functools import update_wrapper
from time import perf_counter


class CountCalls:
    def __init__(self, func: Callable[..., object]) -> None:
        update_wrapper(self, func)
        self.func = func
        self.calls = 0

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        return self.func(*args, **kwargs)


@CountCalls
def square(value: int) -> int:
    return value * value


square(3)
print(square.calls)  # 1
```

这里 `square` 不再是函数，而是 `CountCalls` 的实例。`update_wrapper` 同样用于保留元数据。若这个对象要装饰实例方法，还必须理解描述符协议，或者实现 `__get__`；对初学阶段而言，优先使用函数闭包通常更不容易出错。

## 九、装饰器与“装饰器模式”不是完全同一件事

经典设计模式中的 Decorator Pattern 是：用一个对象包裹另一个对象，同时保持相同接口，并逐层增加职责。Python 的 `@` 语法借用了“装饰”这个思想，但它是语言层面的声明语法，可用于函数和类，通常通过闭包或可调用对象实现。

两者共享“在外层附加行为”的结构，却不应机械等同：

- 经典对象装饰器强调对象组合和接口替代；
- Python 函数装饰器强调定义阶段的可调用对象转换；
- `@property`、`@staticmethod`、`@classmethod` 也是类属性上的装饰器应用，但其返回值分别是不同的描述符对象；
- Web 框架中的路由装饰器常在定义阶段登记函数，而不是在每次请求前简单地套一层 `wrapper`。

例如，FastAPI 的 `@router.get(...)` 会登记路径操作及其元数据；有关路由方法和接口契约的区别，可阅读 [FastAPI 的 `@router.patch`：部分更新、请求方法与接口设计](frameworks/fastapi/01-patch-and-http-methods.md)。把所有 `@xxx` 都想成“运行前后打印两行日志”，显然会误解它们的职责。

## 十、常见陷阱与检查清单

| 现象 | 常见原因 | 改进方式 |
| ---- | -------- | -------- |
| 日志显示函数名为 `wrapper` | 未使用 `@wraps` | 在每层包装器上加 `@wraps(func)` |
| 异步计时接近零 | 未 `await` 原协程 | 使用 `async def wrapper` 与 `await func(...)` |
| 导入模块就发起请求 | 定义阶段执行了副作用 | 将副作用放进 `wrapper` 或显式初始化流程 |
| 重试后产生重复数据 | 重试了非幂等操作 | 设计幂等键、去重或只重试安全步骤 |
| 框架无法识别参数 | 包装器只写 `*args, **kwargs` 且无元数据 | 使用 `wraps`，必要时检查框架签名规则 |
| 异常消失而结果异常 | 通用装饰器吞掉了异常 | 记录后 `raise`，或明确转换为领域错误 |
| 类实例方法绑定异常 | 可调用类缺少描述符处理 | 优先用函数装饰器，或实现 `__get__` |

还有两个经常被忽略的边界：第一，装饰器层数过多会让调用栈和调试路径变长，应该按“认证、事务、重试、观测”这样的明确责任组织，并控制数量。第二，装饰器顺序是语义的一部分。例如“计时包住重试”测的是整次请求，“重试包住计时”测的是每次尝试；二者没有谁天然正确，取决于你想观察和保证什么。

## 十一、何时使用，何时换一种工具

适合使用装饰器的场景有明显共性：它们对很多目标函数的规则一致，主要关注函数调用的外围，而不需要改变核心业务的阅读顺序。例如鉴权、缓存键生成、埋点、审计日志、输入前置检查和测试标记。

不适合时应及时换工具：

- 多个资源要按动态顺序进入和退出，使用 `contextlib.ExitStack` 或上下文管理器；
- 需要为不同调用者提供不同显式策略，使用普通函数、策略对象或依赖注入；
- 需要表达业务流程、补偿步骤或状态机，把步骤写在服务层而不是藏进多层 `@`；
- 需要在应用启动和关闭时管理共享资源，使用框架提供的生命周期机制或上下文管理器。

装饰器的价值是让重复的外围规则集中、可组合并保持调用点整洁；它不是把复杂性消失掉，而是把复杂性安置到一个应该被认真设计的位置。

## 十二、总结

- 函数和类都是对象，装饰器依赖“接收对象、返回对象、重新绑定名字”这一机制。
- `@decorator` 是定义阶段的语法糖；带参数装饰器因此需要“配置 → 装饰器 → 包装器”三层结构。
- 闭包让包装器保存原函数和配置，`functools.wraps` 则保留调用方与工具需要的元数据。
- 同步包装器直接调用原函数；异步包装器必须 `await` 原协程，且不能吞掉取消或真实异常。
- 日志、计时、重试等适合封装为装饰器，但重试范围、异常传播、敏感数据和多层顺序必须显式设计。
- 当问题本质是资源生命周期、动态组合或核心业务流程时，选择上下文管理器、普通对象或显式流程，通常比继续堆叠装饰器更诚实。
