+++
date = '2026-08-26T21:50:00+08:00'
draft = false
title = 'Python 没有 new：对象创建、名称绑定与“引用类型”'
+++

如果从 Java、C# 或 C++ 转到 Python，常会自然地问：Python 为什么没有 `new`？既然写 `a = 1`、`items = []`、`user = User()` 都没有 `new`，那 Python 的对象是不是全都默认分配在堆上、变量是不是全都是引用类型？

简短答案是：

- Python **没有** Java/C++ 风格的 `new` 关键字。
- Python 有 `__new__()` 这个特殊方法，但它不是日常写代码时手工调用的 `new`。
- Python 的变量名保存的是对对象的**绑定**；赋值不会把对象内容复制进变量。
- 从 Python 语言语义看，不应把变量硬分成“值类型”和“引用类型”。Python 中的值都是对象，变量名只是绑定对象。
- 在 CPython 中，Python 对象通常由解释器的私有堆管理；但“所有对象都在堆上”是 **CPython 的实现视角**，不是 Python 语言对所有实现作出的保证。

这几句话看似都在讲“引用”，实际混杂了对象模型、赋值语义、内存分配和垃圾回收四层概念。把它们分开，很多关于可变对象、函数参数和 `is` 的疑问就会自行消失。

## 一、Python 没有显式的 `new` 关键字

Java 中常写：

```java
User user = new User("Yukino");
```

Python 写法是：

```python
user = User("Yukino")
```

`User(...)` 看起来像函数调用，实际上是**调用类对象**。类本身也是对象，并且通常是可调用对象；它的调用过程会负责创建并初始化实例。

对于普通类，可以把：

```python
user = User("Yukino")
```

粗略理解为下面两个阶段：

```text
1. User.__new__(User, "Yukino")  创建实例
2. User.__init__(instance, "Yukino")  初始化实例
```

这只是帮助理解的展开，并不是建议你日常手写的代码。正常情况下，直接调用类即可；语言已经替你完成了对象构造流程，没有必要再把样板工作重新搬回代码里。

### 1. `__new__` 负责“创建”，`__init__` 负责“初始化”

下面的例子能观察调用顺序：

```python
class User:
    def __new__(cls, name: str):
        print("1. 创建实例")
        return super().__new__(cls)

    def __init__(self, name: str):
        print("2. 初始化实例")
        self.name = name


user = User("Yukino")
print(user.name)
```

输出为：

```text
1. 创建实例
2. 初始化实例
Yukino
```

两者的职责不同：

| 方法 | 调用时机 | 主要职责 | 返回值 |
| ---- | -------- | -------- | ------ |
| `__new__(cls, ...)` | `__init__` 前 | 创建并返回对象 | 必须返回对象，通常是 `cls` 的实例 |
| `__init__(self, ...)` | 对象创建后 | 设置对象初始状态 | 必须返回 `None` |

绝大多数业务类只需要实现 `__init__`：

```python
class Article:
    def __init__(self, title: str, published: bool = False):
        self.title = title
        self.published = published
```

覆盖 `__new__` 常见于两类情况：

- 继承 `int`、`str`、`tuple` 等不可变类型时，要在创建阶段处理值。
- 实现单例、缓存或元类等需要控制对象实际创建过程的高级设计。

例如，不可变的 `int` 子类通常要在 `__new__` 中校验并创建值：

```python
class PositiveInt(int):
    def __new__(cls, value: int):
        if value <= 0:
            raise ValueError("value 必须是正整数")
        return super().__new__(cls, value)


count = PositiveInt(3)
print(count + 1)  # 4
```

`int` 对象的值一旦创建就不能修改，因此等到 `__init__` 再想“把整数内容改成正数”已经太晚了。这正是 `__new__` 存在的典型理由。

还有一个容易忽略的规则：如果 `__new__` 返回的不是当前类或其子类的实例，Python 不会再调用当前类的 `__init__`。所以 `__new__` 是构造流程的钩子，不是一个可以随意塞业务逻辑的普通方法。

## 二、Python 的赋值是“名称绑定”，不是把值塞进变量格子

看这段代码：

```python
a = ["Python", "SQLite"]
b = a
```

很多语言的学习经验会让人下意识把 `b = a` 理解成“把 `a` 的内容复制给 `b`”。在 Python 中，更准确的理解是：

```text
名称 a ─┐
        ├──> 同一个 list 对象
名称 b ─┘
```

`a` 和 `b` 都绑定到了同一个列表对象，因此通过任意一个名称修改列表，另一个都会看到变化：

```python
a = ["Python", "SQLite"]
b = a

b.append("Linux")

print(a)  # ['Python', 'SQLite', 'Linux']
print(a is b)  # True
```

这里发生的不是“`b` 修改了 `a`”，而是“`b` 和 `a` 指向同一个可变对象，修改了该对象”。说法上的细节看似挑剔，却会直接决定你能否正确理解后续的参数传递、浅拷贝和默认参数问题。

### 1. 重新绑定和修改对象不是一件事

再看：

```python
a = [1, 2]
b = a

b = [3, 4]

print(a)  # [1, 2]
print(b)  # [3, 4]
```

`b = [3, 4]` 创建（或取得）了另一个列表对象，然后让名称 `b` 改为绑定新对象；原来的列表没有被修改，所以 `a` 不受影响：

```text
名称 a ───> [1, 2]
名称 b ───> [3, 4]
```

可以把核心区别记成：

| 操作 | 影响什么 | 示例 |
| ---- | -------- | ---- |
| 修改对象 | 同一对象的所有别名都会观察到变化 | `items.append("x")` |
| 重新绑定名称 | 只改变当前名称指向谁 | `items = ["x"]` |

## 三、不可变对象也不是“按值传递”

整数、字符串、元组（前提是其内部内容也不可变）常被称为不可变对象。对不可变对象做“修改”时，实际发生的是计算出另一个对象，再重新绑定名称：

```python
score = 10
alias = score

score += 1

print(score)  # 11
print(alias)  # 10
```

这不是因为 `int` 是某种特殊的“值类型”，而是因为整数对象不可原地修改。`score += 1` 的效果接近于：

```python
score = score + 1
```

也就是让 `score` 绑定到表示 `11` 的对象；`alias` 仍绑定到表示 `10` 的对象。

与此对照，列表是可变对象：

```python
items = ["Python"]
alias = items

items += ["SQLite"]

print(items)  # ['Python', 'SQLite']
print(alias)  # ['Python', 'SQLite']
```

对 `list` 而言，`+=` 通常会在原对象上扩展内容，因此两个名称都能看到变化。不能只背“`+=` 等价于 `=` 加法”；对可变对象，它的具体行为可能是原地修改。

### 1. “可变/不可变”才是这里真正重要的分类

把 Python 类型粗略分为“值类型”和“引用类型”并不合适。更有用的分类是：

| 分类 | 常见类型 | 对象内容能否原地改变 | 常见现象 |
| ---- | -------- | -------------------- | -------- |
| 不可变对象 | `int`、`float`、`bool`、`str`、`tuple`、`frozenset` | 不能 | 看起来像修改，实际是名称重新绑定 |
| 可变对象 | `list`、`dict`、`set`、大多数自定义实例 | 能 | 多个名称绑定同一对象时会共享修改 |

元组本身不能增删元素，但它可以包含可变对象：

```python
data = (["draft"], "article")
data[0].append("published")

print(data)  # (['draft', 'published'], 'article')
```

元组的两个位置没有改变，改变的是其中列表对象的内容。因此“容器不可变”不等于“递归地包含的所有东西都不可变”。

## 四、函数参数是对象共享（call by object sharing）

Python 里既不是 C++ 意义上的“传值”与“传引用”二选一，也不是 Java 术语可以原样套用的“引用传递”。更精确的说法是：**函数调用把对象引用所代表的对象共享给形参名称**，形参是函数局部作用域中的新名称绑定。

```python
def add_tag(tags: list[str]) -> None:
    tags.append("python")


article_tags = ["database"]
add_tag(article_tags)

print(article_tags)  # ['database', 'python']
```

调用时的关系可以理解为：

```text
article_tags ─┐
              ├──> 同一个 list 对象
tags ─────────┘
```

函数通过 `tags.append(...)` 修改了共享列表，因此调用方能看到变化。

但如果函数只是重新绑定形参，调用方不会变：

```python
def reset_tags(tags: list[str]) -> None:
    tags = ["new"]


article_tags = ["database"]
reset_tags(article_tags)

print(article_tags)  # ['database']
```

`tags = ["new"]` 仅改变函数内部名称 `tags` 的绑定，不会反向改变调用方名称 `article_tags`。理解了“名称绑定”和“对象修改”的差别，这个现象就没有任何神秘之处。

### 1. 可变默认参数为什么会出问题

下面的函数通常不是你想要的：

```python
def add_item(item: str, items: list[str] = []):
    items.append(item)
    return items
```

默认列表只在函数定义时创建一次。之后的每一次调用都绑定到同一个列表对象：

```python
print(add_item("Python"))  # ['Python']
print(add_item("SQLite"))  # ['Python', 'SQLite']
```

推荐写成：

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

这里 `None` 是单例对象，常用于表达“调用方没有提供列表”。每次进入 `items is None` 分支才创建新的列表，调用之间不会共享状态。

## 五、对象身份、相等性与 `is`

Python 中可以区分两个概念：

- **对象身份（identity）**：是不是同一个对象。
- **对象值（value）**：内容是否相等。

对应的运算符是：

```python
first = ["Python"]
second = ["Python"]
third = first

print(first == second)  # True：内容相等
print(first is second)  # False：不是同一个对象
print(first is third)   # True：同一个对象
```

`==` 调用对象的相等性规则，通常用于比较业务值；`is` 比较对象身份，通常用于与单例比较：

```python
if value is None:
    print("没有值")
```

不要依赖下面这种写法：

```python
# 不要这样比较普通整数或字符串
if a is 256:
    ...
```

CPython 会缓存一部分小整数，也可能复用字符串或折叠常量；其他 Python 实现和不同代码上下文的行为不应被当成稳定契约。即使某次 `a is 256` 看似成立，它表达的也不是“数值是否等于 256”。数值比较该写 `a == 256`，否则代码只是碰巧得到了一个令你满意的结果。

`id(obj)` 可返回对象的身份标识。在 CPython 中，它通常表现为对象内存地址对应的整数；但 Python 语言只保证：对象存活期间，两个同时存在且身份不同的对象有不同的 `id`。不要把 `id()` 当成跨运行、跨实现或对象销毁后仍可用的物理地址。

## 六、“对象都在堆上吗”：语言语义与 CPython 实现要分开

这个问题必须先问“你在讨论哪一层”。

### 1. Python 语言层：不规定栈和堆

Python 语言向开发者暴露的是对象、名称、作用域、生命周期和垃圾回收可观察到的行为，而不是“这个对象到底在 CPU 栈还是进程堆”的内存布局。Python 有 CPython、PyPy、Jython、MicroPython 等不同实现，不能把某一个解释器的分配策略当成所有 Python 都必须遵守的语言规则。

因此，下面这句话在语言层不够严谨：

> Python 的所有对象默认都在堆上。

更准确的说法是：

> Python 程序按对象和名称绑定的语义运行；对象的实际内存位置与具体分配策略由解释器实现决定。

### 2. CPython 实现层：Python 对象通常由私有堆管理

CPython 是最常见的 Python 实现。它有自己的私有堆和对象内存分配器，普通 Python 对象通常由这个内存管理系统分配与管理。局部变量所在的调用帧保存的是对象引用；列表、字典等容器保存的也通常是对其他对象的引用。

可以画成一个**概念模型**：

```text
函数调用帧 / 命名空间
  name: "items" ───────> list 对象
                              ├──> str 对象 "Python"
                              └──> str 对象 "SQLite"
```

它说明的是名称和对象的关系，不是 CPython 保证的逐字节内存布局。实际实现还可能涉及小对象分配器、对象缓存、字符串驻留、自由列表、常量折叠和垃圾回收器。你写 `1`、`"abc"` 或 `()` 时，也不该假设每一次表达式求值都会产生一个全新的物理对象。

### 3. “引用类型”是可用类比，但不是 Python 的正式类型系统

在 Java/C# 中，语言对值类型与引用类型有明确、可见的分类，并会影响变量存储与赋值规则。Python 没有这种面向开发者的类型分类：

- `1`、`"hello"`、`[]`、`{}`、函数、类和模块都属于对象。
- 名称绑定对象，而不是把对象内容嵌入变量槽位。
- 对象是否可变决定了共享后修改是否可见。
- 解释器决定对象如何分配、缓存与回收。

所以可以用“变量持有对象引用”作为初学阶段的心智模型，但不应进一步推导为“Python 的 `int` 就等于 Java 基本类型”或“所有对象每次都 `new` 一份在堆上”。这两种推导都过于整齐，现实通常没这么配合。

## 七、CPython 如何回收对象

在 CPython 中，最常见的回收机制是**引用计数**：当一个对象不再被任何名称、容器、栈帧或其他对象引用时，它的引用计数可以降为零，并通常会立即被释放。

```python
items = ["Python"]
alias = items

del items
# 列表仍被 alias 引用，尚不能回收

del alias
# 在 CPython 中，列表通常此时可立即释放
```

`del` 的含义是删除一个名称绑定或容器项目，不是“强制销毁对象”。只要还有其他引用存在，对象就仍然存活。

引用计数处理不了循环引用，例如两个对象互相保存对方：

```python
left = []
right = []
left.append(right)
right.append(left)
```

即使外部名称后来都解绑，两个列表仍会互相引用。CPython 还提供循环垃圾回收器来发现并处理这类可达性之外的循环。开发业务代码时，通常不应依赖析构时机来释放文件、数据库连接和锁；应使用上下文管理器：

```python
with open("article.md", encoding="utf-8") as file:
    text = file.read()
```

`with` 会在代码块结束时按协议关闭资源，比等待垃圾回收可靠得多。资源管理和内存管理相关，但不是同一件事，把两者混为一谈常常会留下迟早出现的泄漏。

## 八、需要复制时，明确选择浅拷贝或深拷贝

赋值只增加名称绑定。如果确实需要独立的对象，应主动复制。

```python
original = ["Python", "SQLite"]
copied = original.copy()

copied.append("Linux")

print(original)  # ['Python', 'SQLite']
print(copied)    # ['Python', 'SQLite', 'Linux']
```

对于嵌套对象，普通复制通常是浅拷贝：外层容器变了，内部元素仍可能共享：

```python
original = [["draft"]]
copied = original.copy()

copied[0].append("published")

print(original)  # [['draft', 'published']]
```

需要递归复制时可使用 `copy.deepcopy()`，但应先确认它真的符合业务需求。深拷贝可能昂贵，也可能复制掉本应共享的对象；“为了安全先深拷贝一下”有时只是把数据关系弄得更难理解。

## 九、最后用一张表纠正几个常见说法

| 常见说法 | 是否准确 | 更准确的理解 |
| -------- | -------- | ------------ |
| Python 没有 `new` | 基本准确 | 没有显式 `new` 关键字；正常通过调用类创建实例 |
| Python 有 `__new__` | 准确 | 它是实例创建钩子，通常不需要业务代码重写 |
| `a = b` 会复制对象 | 不准确 | 它让名称 `a` 绑定到 `b` 当前绑定的同一对象 |
| Python 都是引用传递 | 不严谨 | 更准确是对象共享：形参是新的局部名称绑定 |
| Python 所有变量都是引用类型 | 不推荐这样说 | Python 名称绑定对象；应关注对象身份与可变性 |
| Python 所有对象都在堆上 | 仅对 CPython 心智模型大致成立 | 语言规范不规定内存位置，具体实现策略不同 |
| 不可变对象赋值不会共享 | 不准确 | 赋值仍可绑定到同一对象，只是对象不能原地修改 |
| `del obj` 会立刻销毁对象 | 不准确 | `del` 删除绑定；对象何时回收取决于是否仍被引用和解释器实现 |

## 十、总结

理解 Python 对象模型，最有用的不是寻找一个 `new` 的替代关键字，而是建立这条链路：

```text
表达式求值产生或取得对象
 -> 名称通过赋值绑定对象
   -> 多个名称可以绑定同一个对象
     -> 可变对象的原地修改会被所有别名观察到
     -> 重新赋值只会改变当前名称的绑定
```

普通对象创建写 `ClassName(...)`；需要定制创建过程时才考虑 `__new__`。讨论日常代码时，优先关心“对象是否可变、谁还持有它、这里是修改还是重新绑定”；讨论 CPython 底层时，再关心私有堆、引用计数和分配器。把实现细节直接当语言规则，往往就像把某次考试的座位表当成学校章程——看上去很具体，实际并不可靠。

## 参考资料

- [Python 数据模型：`__new__`、`__init__` 与对象身份](https://docs.python.org/3/reference/datamodel.html)
- [Python 简单语句：赋值与名称重新绑定](https://docs.python.org/3/reference/simple_stmts.html)
- [CPython C API：Python 堆与对象内存管理](https://docs.python.org/3/c-api/memory.html)
