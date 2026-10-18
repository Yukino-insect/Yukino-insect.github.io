+++

date = '2026-08-17T21:19:41+08:00'
draft = false
title = 'Python 中的函数、可调用对象与类型注解'

+++
## 1. 先回答核心问题

在 Python 中，函数确实是一个可调用对象。

更准确地说：

- `def` 语句会创建一个函数对象。
- 函数名只是一个变量名，它引用这个函数对象。
- 函数对象可以通过 `()` 调用，所以它是 callable，也就是可调用对象。
- 普通 Python 函数的运行时类型通常是 `function`。
- 如果要在代码中引用这个类型，可以使用标准库 `types.FunctionType`。
- 类中定义的 `__call__` 方法也遵守同一个“可调用协议”：对象后面加 `()` 时，Python 会尝试调用它。
- 在函数参数中传递一个函数时，类型注解通常应该写成 `Callable[[参数类型...], 返回值类型]`。

这几个概念容易被混在一起。可惜，混在一起之后并不会更高级，只会更难调试。

---

## 2. 函数名不是函数本身，而是引用函数对象的名字

先看一个普通函数：

```python
def add(a: int, b: int) -> int:
    return a + b
```

这里发生了两件事：

1. Python 创建了一个函数对象。
2. Python 把名字 `add` 绑定到这个函数对象上。

所以 `add` 不是“函数的名称字符串”，而是一个变量，它引用了函数对象。

例如：

```python
def add(a: int, b: int) -> int:
    return a + b

other = add

print(add(1, 2))      # 3
print(other(1, 2))    # 3
print(add is other)   # True
```

`other = add` 并没有复制函数代码，而是让 `other` 也引用同一个函数对象。

因此，当我们说“把函数名传给另一个函数”时，准确地说，是“把函数对象的引用传给另一个函数”。

---

## 3. 函数是对象

Python 中函数是一等对象，也就是 first-class object。

这意味着函数可以像普通对象一样被使用：

- 可以赋值给变量。
- 可以作为参数传给另一个函数。
- 可以作为返回值返回。
- 可以放进列表、字典、集合等容器里。
- 可以拥有属性。

示例：

```python
def add(a: int, b: int) -> int:
    return a + b


def sub(a: int, b: int) -> int:
    return a - b


operations = {
    "add": add,
    "sub": sub,
}

print(operations["add"](10, 3))  # 13
print(operations["sub"](10, 3))  # 7
```

这里字典中存放的不是函数调用结果，而是函数对象本身。

注意下面两种写法的区别：

```python
operations = {
    "add": add,       # 保存函数对象
    "value": add(1, 2) # 保存函数调用结果，也就是 3
}
```

`add` 表示函数对象。

`add(1, 2)` 表示调用函数，并得到返回值。

---

## 4. 函数是可调用对象

所谓可调用对象，就是可以使用 `()` 调用的对象。

Python 提供了内置函数 `callable()` 来判断一个对象是否可调用：

```python
def add(a: int, b: int) -> int:
    return a + b

print(callable(add))  # True
print(callable(123))  # False
print(callable(str))  # True
```

为什么 `str` 也是可调用的？

因为类本身通常也是可调用对象：

```python
name = str(123)
print(name)  # "123"
```

`str(123)` 看起来像是在调用函数，实际上是在调用类对象，创建或转换出一个字符串对象。

所以，可调用对象并不只有函数。常见的可调用对象包括：

- 普通函数。
- 匿名函数 `lambda`。
- 内置函数，例如 `len`、`print`。
- 类，例如 `str`、`list`、`dict`。
- 方法，例如 `obj.method`。
- 实现了 `__call__` 方法的实例。
- 部分类对象通过元类也可以定制调用行为。

换句话说：

函数一定是常见的可调用对象，但可调用对象不一定是函数。

---

## 5. 函数对象在 Python 中是什么类型

普通 Python 函数的类型是 `function`。

示例：

```python
def add(a: int, b: int) -> int:
    return a + b

print(type(add))
```

输出类似：

```text
<class 'function'>
```

如果需要在代码中拿到这个类型，可以使用 `types.FunctionType`：

```python
from types import FunctionType


def add(a: int, b: int) -> int:
    return a + b


print(type(add) is FunctionType)  # True
print(isinstance(add, FunctionType))  # True
```

不过在类型注解中，通常不推荐把参数标成 `FunctionType`。

原因是 `FunctionType` 只表示“普通 Python 函数”，范围太窄。很多能正常调用的对象都不是 `FunctionType`。

例如：

```python
from types import FunctionType

print(isinstance(len, FunctionType))   # False，len 是内置函数
print(isinstance(str, FunctionType))   # False，str 是类
```

但是它们都是可调用的：

```python
print(callable(len))  # True
print(callable(str))  # True
```

所以如果你的代码只需要“能调用”，应该使用 `Callable`，而不是 `FunctionType`。

---

## 6. `__call__` 的作用

在类中定义 `__call__` 方法，可以让类的实例变成可调用对象。

示例：

```python
class Adder:
    def __init__(self, base: int) -> None:
        self.base = base

    def __call__(self, value: int) -> int:
        return self.base + value


add_ten = Adder(10)

print(add_ten(5))        # 15
print(callable(add_ten)) # True
```

执行：

```python
add_ten(5)
```

大致等价于：

```python
add_ten.__call__(5)
```

但实际写代码时，应该优先使用 `add_ten(5)` 这种调用形式。直接调用 `__call__` 通常只适合解释机制或做特殊调试。

### `__call__` 和普通函数是不是同样的作用

从“调用方式”上看，它们遵守同一个可调用协议：

```python
result = something(...)
```

只要 `something` 是可调用对象，这种语法就能工作。

但是从“对象类型”上看，它们不是同一种东西：

```python
from types import FunctionType


def add(a: int, b: int) -> int:
    return a + b


class Adder:
    def __call__(self, a: int, b: int) -> int:
        return a + b


adder = Adder()

print(type(add))                 # <class 'function'>
print(type(adder))               # <class '__main__.Adder'>
print(isinstance(add, FunctionType))    # True
print(isinstance(adder, FunctionType))  # False
print(callable(add))             # True
print(callable(adder))           # True
```

所以结论是：

- 普通函数对象本身可调用。
- 实现了 `__call__` 的实例也可调用。
- 它们都能被 `()` 调用。
- 它们的运行时类型不一样。
- 如果只关心“能否调用”，应该用 `Callable` 这个抽象概念。

---

## 7. 类本身为什么也可以被调用

下面这个写法很常见：

```python
user = User("Alice")
```

如果 `User` 是一个类，那么 `User("Alice")` 其实是在调用类对象。

类对象之所以能被调用，是因为类的调用行为通常由它的元类控制。默认情况下，绝大多数类的元类是 `type`，而 `type` 实现了调用逻辑。

简单理解即可：

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name


print(callable(User))  # True
```

调用 `User("Alice")` 时，Python 会创建实例，并调用初始化逻辑。

这和实例实现 `__call__` 是两个层次：

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self) -> str:
        return f"User: {self.name}"


print(callable(User))  # True，类对象可调用，用来创建实例

user = User("Alice")
print(callable(user))  # True，实例也可调用，因为定义了 __call__

print(user())          # User: Alice
```

---

## 8. 函数作为参数传递时，类型注解怎么写

最常用的写法是 `Callable`。

在 Python 3.9 及以上版本中，推荐从 `collections.abc` 导入：

```python
from collections.abc import Callable
```

在较旧代码中，也经常能看到：

```python
from typing import Callable
```

两者都能表达“可调用对象”。现代代码中，优先使用 `collections.abc.Callable` 是更自然的选择。

### 8.1 标注一个接收函数的参数

假设我们需要接收一个函数，这个函数：

- 接收两个 `int` 参数。
- 返回一个 `int`。

可以这样写：

```python
from collections.abc import Callable


def calculate(a: int, b: int, operation: Callable[[int, int], int]) -> int:
    return operation(a, b)


def add(a: int, b: int) -> int:
    return a + b


def multiply(a: int, b: int) -> int:
    return a * b


print(calculate(2, 3, add))       # 5
print(calculate(2, 3, multiply))  # 6
```

这里：

```python
Callable[[int, int], int]
```

表示：

```text
一个可调用对象，接收两个 int 参数，返回 int
```

格式是：

```python
Callable[[参数1类型, 参数2类型, ...], 返回值类型]
```

---

## 9. 不关心参数类型时怎么写

如果只知道它是可调用对象，但不关心参数列表，可以写：

```python
from collections.abc import Callable
from typing import Any


def run_task(task: Callable[..., Any]) -> Any:
    return task()
```

这里：

```python
Callable[..., Any]
```

表示：

- 参数列表不限。
- 返回值可以是任意类型。

不过这是一种比较宽松的写法。它方便，但类型检查能力也比较弱。除非你确实不知道参数和返回值，否则应该尽量写得具体一些。

例如下面这样更好：

```python
from collections.abc import Callable


def run_task(task: Callable[[], None]) -> None:
    task()
```

`Callable[[], None]` 表示：

- 不接收参数。
- 返回 `None`。

---

## 10. 返回函数时的类型注解

函数也可以返回另一个函数。

示例：

```python
from collections.abc import Callable


def make_multiplier(factor: int) -> Callable[[int], int]:
    def multiply(value: int) -> int:
        return value * factor

    return multiply


double = make_multiplier(2)
print(double(10))  # 20
```

这里：

```python
def make_multiplier(factor: int) -> Callable[[int], int]:
```

表示 `make_multiplier` 返回一个可调用对象，这个可调用对象接收一个 `int`，返回一个 `int`。

---

## 11. 对装饰器使用类型注解

装饰器本质上也是“接收函数，返回函数”的函数。

一个简单装饰器可以这样写：

```python
from collections.abc import Callable
from typing import TypeVar


F = TypeVar("F", bound=Callable[..., object])


def log_call(func: F) -> F:
    def wrapper(*args: object, **kwargs: object) -> object:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
```

上面的写法可以工作，但并不完美，因为 `wrapper` 的类型信息不够精确。

更现代、更精确的写法可以使用 `ParamSpec`：

```python
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar


P = ParamSpec("P")
R = TypeVar("R")


def log_call(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper
```

这里：

- `P` 表示原函数的参数列表。
- `R` 表示原函数的返回值类型。
- `Callable[P, R]` 表示保持原函数的参数类型和返回值类型。

这对装饰器非常重要，否则装饰器一包，类型信息就容易被弄丢。

---

## 12. `Callable` 和 `FunctionType` 的区别

这两个东西很容易被误用。

| 写法 | 含义 | 适合场景 |
| --- | --- | --- |
| `Callable[[int], str]` | 一个可调用对象，接收 `int`，返回 `str` | 参数需要能被调用即可 |
| `Callable[..., Any]` | 一个参数任意、返回任意的可调用对象 | 暂时无法精确描述参数 |
| `types.FunctionType` | 普通 Python 函数对象的运行时类型 | 极少数需要检查“是不是普通函数”的场景 |
| `types.BuiltinFunctionType` | 内置函数的运行时类型 | 做底层 introspection 时可能用到 |
| `types.MethodType` | 绑定方法的运行时类型 | 做方法对象检查时可能用到 |

示例：

```python
from collections.abc import Callable
from types import BuiltinFunctionType, FunctionType, MethodType


def add(a: int, b: int) -> int:
    return a + b


class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b


calc = Calculator()

print(isinstance(add, FunctionType))          # True
print(isinstance(len, BuiltinFunctionType))   # True
print(isinstance(calc.add, MethodType))       # True

print(isinstance(add, Callable))              # True
print(isinstance(len, Callable))              # True
print(isinstance(calc.add, Callable))         # True
```

在大多数业务代码中，你需要的是 `Callable`，不是 `FunctionType`。

---

## 13. `Callable` 能表达什么，不能表达什么

`Callable` 能表达比较普通的调用签名：

```python
from collections.abc import Callable


Callback = Callable[[str, int], bool]
```

这表示：

```text
接收 str 和 int，返回 bool 的可调用对象
```

但是 `Callable` 对一些复杂函数签名表达得不够细：

- 它不能很好表达参数名必须是什么。
- 它不能精确表达某些关键字参数。
- 它不能精确表达重载函数的多个调用形式。
- 它不能像函数定义那样直观地表达默认值。

例如你希望传入的对象必须支持这样的调用：

```python
handler(event: str, *, retry: bool = False) -> None
```

这时可以考虑使用 `Protocol`：

```python
from typing import Protocol


class EventHandler(Protocol):
    def __call__(self, event: str, *, retry: bool = False) -> None:
        ...


def register_handler(handler: EventHandler) -> None:
    handler("user.created", retry=True)
```

`Protocol` 的好处是可以像写普通方法一样描述 `__call__` 的签名。

所以选择规则可以简单记成：

- 普通函数参数：用 `Callable[[...], ReturnType]`。
- 参数结构复杂、关键字参数重要：用带 `__call__` 的 `Protocol`。
- 做运行时底层检查：才考虑 `types.FunctionType` 等具体类型。

---

## 14. 常见写法对照

### 接收一个无参数、无返回值的回调

```python
from collections.abc import Callable


def on_finished(callback: Callable[[], None]) -> None:
    callback()
```

### 接收一个字符串处理函数

```python
from collections.abc import Callable


def format_name(name: str, formatter: Callable[[str], str]) -> str:
    return formatter(name)
```

### 接收一个判断函数

```python
from collections.abc import Callable


def filter_numbers(
    numbers: list[int],
    predicate: Callable[[int], bool],
) -> list[int]:
    return [number for number in numbers if predicate(number)]
```

### 接收一个任意可调用对象

```python
from collections.abc import Callable
from typing import Any


def execute(func: Callable[..., Any]) -> Any:
    return func()
```

### 返回一个函数

```python
from collections.abc import Callable


def make_prefixer(prefix: str) -> Callable[[str], str]:
    def add_prefix(text: str) -> str:
        return prefix + text

    return add_prefix
```

### 使用类型别名让代码更清楚

```python
from collections.abc import Callable


Validator = Callable[[str], bool]


def validate_username(username: str, validator: Validator) -> bool:
    return validator(username)
```

类型别名不是必须的，但当函数签名变长时，它能让代码清爽不少。

---

## 15. 一个完整示例

下面例子展示了普通函数、`lambda`、实现 `__call__` 的类实例，都可以作为 `Callable` 传入。

```python
from collections.abc import Callable


def apply_discount(
    price: float,
    discount_rule: Callable[[float], float],
) -> float:
    return discount_rule(price)


def ten_percent_off(price: float) -> float:
    return price * 0.9


class FixedDiscount:
    def __init__(self, amount: float) -> None:
        self.amount = amount

    def __call__(self, price: float) -> float:
        return max(price - self.amount, 0)


price = 100.0

print(apply_discount(price, ten_percent_off))          # 90.0
print(apply_discount(price, lambda p: p * 0.8))        # 80.0
print(apply_discount(price, FixedDiscount(15.0)))      # 85.0
```

`apply_discount` 并不关心传进来的是普通函数、匿名函数，还是某个类的实例。

它只关心一件事：

```text
这个对象能不能接收一个 float，并返回一个 float。
```

这就是 `Callable[[float], float]` 想表达的语义。

---

## 16. 小结

可以把这几个概念整理成一张表：

| 问题 | 答案 |
| --- | --- |
| Python 中函数是不是对象？ | 是，函数是一等对象 |
| 函数是不是可调用对象？ | 是，普通函数可以用 `()` 调用 |
| 函数对象的类型是什么？ | 普通 Python 函数通常是 `<class 'function'>`，可用 `types.FunctionType` 表示 |
| 函数名是什么？ | 函数名是引用函数对象的变量名 |
| `__call__` 有什么用？ | 让实例也可以像函数一样被 `()` 调用 |
| 实现了 `__call__` 的实例是不是函数？ | 不是普通函数，但它是可调用对象 |
| 函数参数中传函数，类型注解怎么写？ | 通常写 `Callable[[参数类型...], 返回值类型]` |
| 什么时候用 `Callable[..., Any]`？ | 参数和返回值确实无法精确描述时 |
| 什么时候用 `Protocol.__call__`？ | 需要精确表达关键字参数、参数名或复杂调用签名时 |
| 什么时候用 `FunctionType`？ | 极少数需要运行时判断“普通 Python 函数对象”的场景 |

最重要的一句话是：

```text
在类型注解里，优先描述“这个对象如何被调用”，而不是执着于“它是不是 function 类型”。
```

这也是 Python 类型系统里很实用的一种思路：面向行为，而不是只盯着具体实现类型。
