+++
date = '2026-10-22T20:00:00+08:00'
draft = false
title = "Python 中的 `...` 是什么：Ellipsis 对象、占位与类型标注"
+++

在 Python 代码中看到 `...` 时，很多人的第一反应是“省略号，暂时没写完”。这个理解并不算错，却不完整：`...` 不是注释，也不只是编辑器里的占位符；它是 Python 的**字面量语法**，求值后得到一个真实的内置单例对象 `Ellipsis`。

因此，下面这行代码完全可以执行：

```python
value = ...

print(value)       # Ellipsis
print(type(value)) # <class 'ellipsis'>
```

理解它的关键在于区分两件事：语法里的 `...`，以及运行时对象 `Ellipsis`。前者是写代码时使用的简写；后者才是程序实际拿到的值。它最初主要服务于扩展切片，如今也常见于类型标注和未完成实现的占位场景。

## `...` 与 `Ellipsis` 是同一个对象

`...` 是 `Ellipsis` 的字面量写法。两者指向同一个全局单例，因此应当用 `is` 判断身份：

```python
print(... is Ellipsis)  # True

first = ...
second = Ellipsis

print(first is second)  # True
```

这里的“单例”表示整个 Python 进程中，`Ellipsis` 只有这一个对象实例。类似的内置单例还有 `None`、`True`、`False` 和 `NotImplemented`。

可以把它们的写法和含义放在一起对照：

| 写法 | 对象名 | 通常表示 |
| ---- | ------ | -------- |
| `None` | `None` | 没有值、函数没有显式返回值 |
| `...` | `Ellipsis` | 省略、尚未指定或由上下文解释 |
| `NotImplemented` | `NotImplemented` | 某个特殊方法暂不处理该运算 |
| `pass` | 不产生对象 | 空语句，只是让语法块成立 |

尤其要注意最后一项：`pass` 不是值，不能赋值给变量；`...` 是值，能出现在表达式可以出现的地方。

```python
def todo_with_pass():
    pass


def todo_with_ellipsis():
    ...


print(todo_with_pass())      # None
print(todo_with_ellipsis())  # None
```

虽然两个函数调用后都返回 `None`，但原因不同：函数体中的表达式 `...` 被求值后又被丢弃，而 `pass` 根本没有可求值的内容。两者都适合临时让函数体合法；如果要让读者明确看到“这里还没有实现”，`...` 的意图往往更醒目一些。

## 它不是字符串，也不代表“任意值”

三个英文点并不等于字符串 `"..."`：

```python
print(... == "...")  # False
print(repr(...))      # Ellipsis
```

更重要的是，`Ellipsis` 没有固定的业务语义。Python 只保证它是那个单例对象；“省略了什么”要由使用它的库、框架或当前语法上下文决定。

例如某个配置函数可以约定：

```python
UNSET = ...


def update_profile(*, nickname=UNSET, city=UNSET):
    if nickname is not UNSET:
        print(f"更新昵称为：{nickname}")
    if city is not UNSET:
        print(f"更新城市为：{city}")


update_profile(nickname=None)
```

这里 `...` 被用作“调用方没有提供这个参数”的哨兵值。这样 `nickname=None` 仍然可以表达“明确把昵称设为空”，而不是被误解为“没有传入昵称”。这是 `Ellipsis` 可以胜任的一种设计，但并非唯一选择；很多项目也会写 `UNSET = object()` 创建私有哨兵，避免把一个通用内置对象暴露成业务约定。

## 最原始的用途：多维数组的扩展切片

`Ellipsis` 在 Python 语言层面最有辨识度的用途，是索引表达式中的扩展切片。它表示“这里省略若干个完整维度”。

这个语法主要由 NumPy 等多维数组库实现。下面以一个三维数组为例：

```python
import numpy as np

array = np.arange(2 * 3 * 4).reshape(2, 3, 4)

print(array[1, ...].shape)   # (3, 4)
print(array[..., 0].shape)   # (2, 3)
print(array[1, ..., 0].shape)  # (3,)
```

可以把它理解成下面的等价关系：

```text
array[1, ...]      等价于 array[1, :, :]
array[..., 0]      等价于 array[:, :, 0]
array[1, ..., 0]   等价于 array[1, :, 0]
```

`...` 会自动补足需要的 `:`，因此当数组维数较高、代码又需要兼容不同维度时，比手写大量冒号更稳定也更易读。

### 普通列表为什么不能这样切片

内置 `list` 只理解整数索引和 `slice` 对象，不理解 `Ellipsis`：

```python
items = [10, 20, 30]

# items[...]  # TypeError: list indices must be integers or slices, not ellipsis
```

这并不说明 `...` 不是 Python 语法。实际过程是：解释器把 `items[...]` 中的 `...` 解析为 `Ellipsis`，再把它交给 `list` 的索引逻辑；而 `list` 选择拒绝这种索引对象。

自定义类型可以自行解释它：

```python
class Grid:
    def __getitem__(self, index):
        if index is Ellipsis:
            return "所有维度"
        return f"索引：{index!r}"


grid = Grid()

print(grid[...])    # 所有维度
print(grid[1:3])    # 索引：slice(1, 3, None)
```

这正是 NumPy 能赋予 `...` 多维切片含义的基础：在 `__getitem__` 中接收并处理 `Ellipsis`。

## 作为类、函数和条件分支的占位符

因为 `...` 是合法表达式，所以它能单独构成一条表达式语句。这使它可以暂时填充本来不能为空的代码块。

```python
class PaymentGateway:
    ...


def calculate_discount(total: float) -> float:
    ...


if False:
    ...
```

在这些位置，`...` 与 `pass` 都能防止 `SyntaxError`。选择时应看表达意图：

- 用 `pass`：这个代码块有意什么都不做，例如捕获某个可忽略异常。
- 用 `...`：这里是声明、接口或草稿，具体行为还待补充。

```python
try:
    optional_cleanup()
except FileNotFoundError:
    pass  # 文件不存在时确实无需处理


class UserRepository:
    def find_by_id(self, user_id: int):
        ...  # 接口示例：实现尚未提供
```

不过，`...` **不会自动阻止函数继续运行**。若一个未实现的方法被调用，它只会返回 `None`，错误可能在更晚的地方才出现。对于运行时绝不能被调用的抽象操作，更适合明确抛出异常：

```python
class Storage:
    def save(self, data: bytes) -> None:
        raise NotImplementedError("子类必须实现 save")
```

如果要定义真正的抽象基类，则可使用 `abc`：

```python
from abc import ABC, abstractmethod


class Storage(ABC):
    @abstractmethod
    def save(self, data: bytes) -> None:
        ...
```

此处的 `...` 只填充方法体；禁止直接实例化 `Storage` 的效果来自 `@abstractmethod` 和 `ABC`，不是 `Ellipsis` 本身造成的。

## 类型标注中的 `...`

在类型系统中，`...` 常用于表达“参数细节在这里省略”。最常见的是可调用对象 `Callable`：

```python
from collections.abc import Callable


handler: Callable[..., int]
```

`Callable[..., int]` 表示：`handler` 可以接受任意形式的参数，但其返回值应为 `int`。它不是说函数返回 `Ellipsis`。

如果参数签名已知，应写得更精确：

```python
from collections.abc import Callable


formatter: Callable[[str, int], str]
```

这表示 `formatter` 接受一个 `str` 和一个 `int`，返回 `str`。`...` 只适合调用约定确实未知、或当前层次不需要约束参数的场合；滥用它会降低静态检查的价值。

它还会出现在类型存根文件（`.pyi`）中。存根文件只声明 API 的类型与签名，不提供可执行实现：

```python
def parse_port(value: str) -> int: ...


class Client:
    timeout: float

    def close(self) -> None: ...
```

这里的 `...` 明确告诉类型检查器和读者：实现位于别处，当前文件只描述接口。这是比 `pass` 更常用、更符合惯例的写法。

## 不要把它与 `NotImplemented` 混淆

`Ellipsis` 和 `NotImplemented` 都像“尚未处理”的标记，但它们服务于不同机制。

`NotImplemented` 是富比较、算术等特殊方法与解释器之间的协商信号。通常应当**返回**它：

```python
class Distance:
    def __eq__(self, other):
        if not isinstance(other, Distance):
            return NotImplemented
        return True
```

解释器看到这个返回值后，会尝试对方的对应方法，或采用该运算的默认行为。相反，`...` 没有这种解释器协议：

```python
class WrongDistance:
    def __eq__(self, other):
        return ...
```

上例返回的是 `Ellipsis` 对象，而不是“请 Python 继续尝试”。在布尔上下文中它目前为真，比较表达式的行为也会变得令人费解。因此，特殊方法无法处理操作数类型时，应使用 `NotImplemented`，而不是 `...`。

## 常见误解与使用建议

### `...` 能否替代 `None`？

只有在 API 明确定义了两者不同含义时才可以。比如一个参数中，`None` 代表“清空配置”，`...` 代表“保留原值”。若不存在这种三态需求，使用 `None` 更符合读者的预期。

### 能否用 `...` 标记所有待办事项？

可以作为短期草稿，但不宜让它长期留在业务逻辑中。被调用的 `...` 函数会静默返回 `None`，相比之下 `raise NotImplementedError` 更容易在测试阶段暴露缺失实现。

### 可以用 `==` 判断吗？

应使用 `is`：

```python
if value is Ellipsis:
    print("收到省略号哨兵")
```

单例和哨兵值通常关注“是不是这个对象”，而不是“两个对象的值是否相等”。`is` 恰好表达这一点。

## 总结

`...` 在 Python 中不是普通标点，而是 `Ellipsis` 单例对象的字面量。

- `... is Ellipsis` 恒为 `True`；判断时使用 `is`。
- 在 NumPy 等多维数组中，它表示省略的完整维度，用于扩展切片。
- 它可以填充类、函数和分支等暂未实现的代码块，但被调用的函数仍会默认返回 `None`。
- 在 `.pyi` 存根和 `Callable[..., ReturnType]` 等类型标注中，它表示省略实现或参数细节。
- 它不是 `None`，更不能代替特殊方法中应返回的 `NotImplemented`。

所以，看见 `...` 时先别急着把它当成“以后再说”。先观察它位于数组索引、类型标注，还是普通运行时代码中；语法给出的只是 `Ellipsis`，真正的语义永远来自它所在的上下文。毕竟，同样的三个点，放错位置也不会替你省略理解成本。
