+++
date = '2026-08-27T10:00:00+08:00'
draft = false
title = 'Python 的 with as 与作用域：为什么离开代码块后 config 仍然可用'
+++

看到下面的代码时，容易产生一个看似合理的疑问：`config` 是在 `with ... as ...` 内部创建的，为什么离开缩进块后，`for` 和 `if` 还可以访问它？

```python
def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    for key in ("api", "device", "selectors"):
        if key not in config:
            raise ValueError(f"config.yaml 缺少 {key} 配置段")

    if not config["api"].get("token") or "replace-with" in config["api"]["token"]:
        raise ValueError("请在 config.yaml 中配置真实 api.token")

    return config
```

结论先说：**`with`、`for` 和 `if` 的缩进块不会在 Python 中创建新的作用域。**`config` 是在 `load_config` 函数内部绑定的局部变量；只要函数尚未结束，它就可以在该函数中的后续语句里使用。

这里有两个彼此独立的概念：`with` 负责管理文件这类资源的生命周期，作用域规则则决定名字 `config` 在哪里可见。把二者混为一谈，是这个问题看起来麻烦的唯一原因。Python 并没有把它设计得那么曲折。

## 一、先看这段函数实际执行了什么

可以把它按顺序理解成下面这样：

```text
进入 load_config 函数
  -> 打开 config_path 指向的文件
  -> 把文件对象绑定为 file
  -> 从文件读取 YAML，并把解析结果绑定为 config
  -> 离开 with：关闭文件
  -> 检查 config 是否含有必要配置段
  -> 检查 api.token 是否是有效令牌
  -> 返回 config
离开 load_config 函数
```

离开 `with` 时，自动结束的是文件对象 `file` 对应的打开状态；不会自动删除 `config`。`config` 保存的是 YAML 解析后得到的 Python 字典，它已经独立存在于内存中，不需要继续保持文件打开。

这和读完纸质文件、把内容记到笔记本上再把文件夹合起来差不多：合上的是文件夹，不是笔记本。

## 二、Python 中“作用域”到底是什么

作用域（scope）回答的是：**某个名字在当前这行代码中能不能被解析到，以及它指向哪个对象。**

Python 常见的名字查找顺序可以用 LEGB 记忆：

```text
L：Local，当前函数的局部作用域
E：Enclosing，外层嵌套函数的作用域
G：Global，当前模块的全局作用域
B：Built-in，内置名称作用域
```

例如：

```python
name = "module"


def outer() -> None:
    name = "outer"

    def inner() -> None:
        name = "local"
        print(name)

    inner()


outer()  # local
```

`inner()` 中的 `name` 先在它自己的局部作用域找到，因此不会再向外寻找。若删去 `inner` 中的赋值，它会继续向外层函数找；再找不到，才会寻找模块变量和内置名称。

在问题中的函数里，`config` 的归属很明确：

```python
def load_config(config_path: Path) -> dict[str, Any]:
    # 从这整个函数的角度看，config 是局部变量。
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    return config
```

因为 `config = ...` 出现在函数体中，Python 会把 `config` 判定为这个函数的局部变量。`with` 所在的缩进层级不会改变这个结论。

## 三、`with`、`if`、`for`、`while`、`try` 不创建块级作用域

许多语言会给花括号或代码块单独建立作用域；例如 Java、C#、JavaScript 中以 `let` 声明的变量。Python 的常规缩进块不是这种规则。

下面这些变量在块结束后都仍可使用：

```python
def examples() -> None:
    if True:
        from_if = "if block"

    for number in range(1):
        from_for = number

    try:
        from_try = "try block"
    finally:
        pass

    with open("example.txt", "w", encoding="utf-8") as file:
        from_with = file.name

    print(from_if)    # if block
    print(from_for)   # 0
    print(from_try)   # try block
    print(from_with)  # example.txt
```

这不表示变量一定有值，而是表示这些语句不会额外创建一个独立作用域。比如循环从未执行，循环体内的赋值根本没有发生：

```python
for item in []:
    last_item = item

print(last_item)  # NameError：last_item 从未被绑定
```

同理，如果 `config_path.open()` 失败，或者 YAML 解析时抛出异常，`config = ...` 没有成功执行；函数会直接异常退出，后面的检查也不会运行。并不是 `with` 把 `config` “藏起来了”。

### 1. 循环变量也会留在当前作用域

初学者有时会对这一点感到意外：

```python
for key in ("api", "device", "selectors"):
    pass

print(key)  # selectors
```

`key` 在循环结束后仍绑定为最后一次迭代的值。这正是 `for` 没有块级作用域的直接结果。实际代码不要依赖这种“最后一个循环变量”的状态；它通常只会让阅读者多花时间猜测意图。

### 2. `with ... as file` 中的 `file` 也仍是同一作用域的名字

`as file` 只是把上下文管理器提供的对象绑定到变量 `file`。离开 `with` 后该名字通常仍然存在：

```python
with open("config.yaml", encoding="utf-8") as file:
    content = file.read()

print(file.closed)  # True
```

这里 `file` 这个名字还在，但它指向的文件已经关闭。名字是否存在，和对象是否还能执行某项操作，是两回事：

```python
file.read()  # ValueError: I/O operation on closed file.
```

因此，不要把“变量还可见”误解为“资源还可用”。在原始函数中，把解析得到的 `config` 留在 `with` 外正是正确做法；反过来，在 `with` 外继续读取 `file` 则不对。

## 四、真正创建作用域的结构有哪些

最实用的规则是：Python 主要由**模块、函数、类、推导式**创建新的名字空间或作用域；普通控制流块通常不会。

| 结构 | 是否建立独立作用域 / 名字空间 | 典型表现 |
| ---- | ----------------------------- | -------- |
| 模块文件 | 是 | 文件顶层赋值通常是模块全局名称 |
| `def` / `async def` | 是 | 函数内赋值默认是局部变量 |
| `lambda` | 是 | 参数仅在 Lambda 表达式内可用 |
| 类定义体 | 有独立类名字空间 | 类体赋值成为类属性，方法读取规则另有边界 |
| 列表、集合、字典推导式与生成器表达式 | 是 | 推导式迭代变量不会泄漏到外层 |
| `if`、`for`、`while`、`try`、`with`、`match` | 否 | 块内绑定的普通名字在外层仍可见 |

### 1. 函数作用域

函数调用时会建立局部作用域，函数返回或异常退出时，这个调用对应的局部名字通常不再可从外部访问：

```python
def build_config() -> dict[str, bool]:
    config = {"debug": True}
    return config


result = build_config()
print(result)  # {'debug': True}
# print(config)  # NameError：调用者作用域中没有 config
```

对象会不会继续存活取决于是否还有引用，而不是局部变量名字是否结束。上例中的字典通过 `result` 被引用，所以返回后仍可使用。

### 2. 嵌套函数与 `nonlocal`

嵌套函数读取外层函数的变量没有问题；但若要重新绑定外层变量，需要明确写 `nonlocal`：

```python
def make_counter():
    count = 0

    def increment() -> int:
        nonlocal count
        count += 1
        return count

    return increment
```

这里 `count` 属于 `make_counter` 的局部作用域，`increment` 通过 `nonlocal` 表示“修改外层函数里的那个 `count`”。

### 3. 模块变量与 `global`

若函数内要重新绑定模块级名字，则需要 `global`：

```python
DEFAULT_TIMEOUT = 5


def set_default_timeout(value: int) -> None:
    global DEFAULT_TIMEOUT
    DEFAULT_TIMEOUT = value
```

不过，可变全局状态会增加调用顺序和测试隔离的复杂度。配置加载函数返回字典、由调用方显式传递，通常比在函数里修改全局配置更清晰。

## 五、赋值会影响 Python 对名字的判断

一个容易踩到的规则是：只要函数体中某处对名字进行了普通赋值，Python 通常会把该名字当作**整个函数**的局部变量，而不是只从赋值那一行起才当局部变量。

```python
setting = "production"


def show_setting() -> None:
    print(setting)
    setting = "development"
```

调用 `show_setting()` 会得到：

```text
UnboundLocalError: cannot access local variable 'setting' where it is not associated with a value
```

原因不是第一行 `print` 执行得太早，而是 Python 在编译函数时已经看到 `setting = ...`，于是将 `setting` 分类为局部变量；第一行读取的是一个尚未赋值的局部名字。

下面的代码没有这个问题，因为 `config` 的第一次使用就是赋值，后续才读取：

```python
def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    return config
```

## 六、两个重要例外：`except ... as` 与推导式

“普通块不创建作用域”很有用，但也不能机械地理解成“块中所有名字都永远留下”。有两个常见细节值得记住。

### 1. 异常变量在 `except` 结束后会被清除

```python
try:
    int("not-a-number")
except ValueError as error:
    message = str(error)

print(message)  # 可以使用
print(error)    # NameError
```

`except ... as error` 中的异常变量是特殊处理。异常对象会引用 Traceback，Traceback 又可能引用当前栈帧和局部变量；Python 在处理器结束后清除该异常变量，可帮助打破潜在引用环。

要在处理器之外使用错误信息，就保存必要内容，例如 `message`，或者在处理器内部使用 `raise NewError(...) from error`。不要设计依赖于 `error` 离开 `except` 后仍存在的代码。

### 2. 推导式的迭代变量有独立作用域

Python 3 中，推导式不会把其迭代变量泄漏到外层：

```python
key = "outer"
names = [key.upper() for key in ("api", "device")]

print(names)  # ['API', 'DEVICE']
print(key)    # outer
```

这与普通 `for` 循环不同：

```python
key = "outer"
for key in ("api", "device"):
    pass

print(key)  # device
```

两种写法外形相近，名字规则却不同。推导式是表达式，Python 为它安排了独立作用域；普通循环则只是当前作用域中的控制流。

## 七、`with` 的本职工作：资源管理，而不是变量隔离

`with` 使用的是上下文管理器协议。概念上，下面的写法：

```python
with config_path.open("r", encoding="utf-8") as file:
    config = yaml.safe_load(file) or {}
```

大致等价于：

```python
manager = config_path.open("r", encoding="utf-8")
file = manager.__enter__()
try:
    config = yaml.safe_load(file) or {}
finally:
    manager.__exit__(None, None, None)
```

真正的实现还会把 `try` 块中发生的异常信息传给 `__exit__`；上下文管理器也可以选择处理该异常。文件对象通常只负责关闭资源，不会吞掉 YAML 解析异常。

因此，`with` 给出的保证是：不论读取和解析成功、抛出异常，还是在块内 `return`，退出块时都会尝试关闭文件。它相当于更安全、更易读的 `try/finally` 模式。

```python
with open("config.yaml", encoding="utf-8") as file:
    config = yaml.safe_load(file) or {}
# 文件已关闭；config 作为内存中的字典仍可使用。
```

这正是配置读取时应有的资源边界：打开文件的时间尽量短，数据加载完成后立即释放文件句柄，验证逻辑再对内存中的数据进行处理。

## 八、回到原函数：它的作用域和生命周期

为避免概念混杂，可以把关键名字分别列出来：

| 名字 | 绑定位置 | 可见范围 | 离开 `with` 后的状态 |
| ---- | -------- | -------- | --------------------- |
| `config_path` | 函数参数 | 整个 `load_config` 调用 | 仍可用，直到函数结束 |
| `file` | `with ... as file` | 整个函数局部作用域 | 名字通常仍在，但文件已关闭 |
| `config` | `with` 块内的赋值 | 整个函数局部作用域 | 仍可用，字典内容仍在内存 |
| `key` | `for` 循环目标 | 整个函数局部作用域 | 循环正常结束时，保留最后一个键 |

`return config` 执行后，`load_config` 这个调用的局部作用域结束。但返回的字典被调用方接住时，字典当然仍然可以继续使用：

```python
config = load_config(Path("config.yaml"))
print(config["api"])
```

变量名可以在不同作用域重复使用。调用方的 `config` 与函数内部的 `config` 不是同一个“变量槽位”；只是函数把一个对象返回了，调用方再把它绑定到了自己的名字上。

## 九、实践建议

- 把 `with` 理解为“资源必须在这里被正确收尾”，不要把它理解为“变量只能活在这里”。
- 把 `def` 当作局部变量的重要边界；函数结束后，局部名字不再属于调用方。
- 不要指望 `if`、`for`、`while`、`try` 或 `with` 代替函数作用域来隔离临时变量。
- 不要在 `with` 外继续操作已经关闭的文件、锁、数据库会话等资源，即使绑定它们的变量名仍可见。
- 对于 `except ... as error`，在 `except` 内记录、转换或提取所需信息，不要在外部依赖异常变量。
- 当一段逻辑需要真正隔离临时名称、控制可见性或缩短对象生命周期时，拆成函数通常最清楚。

## 十、总结

原代码能够正常工作，是因为 Python 的普通缩进块不建立块级作用域：

```python
with ... as file:
    config = ...

# 仍在同一个 load_config 函数的局部作用域中
for key in ...:
    ... config ...
```

离开 `with` 后，自动发生的是文件资源的清理，而不是删除 `config`。`config` 是解析后的字典，`file` 是需要关闭的文件对象；二者的生命周期本来就不应相同。

只要记住一句话就够了：**Python 中的缩进主要表达代码结构，函数才是最常见的局部作用域边界；`with` 管资源，不管变量的可见性。**
