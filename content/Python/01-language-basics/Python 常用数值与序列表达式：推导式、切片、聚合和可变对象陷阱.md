+++
date = '2026-10-17T15:00:00+08:00'
draft = false
title = 'Python 常用数值与序列表达式：推导式、切片、聚合和可变对象陷阱'
+++

Python 的表达式往往很短，却可能同时完成创建数据、遍历数据、筛选数据和计算结果。例如：

```python
squares_of_even_numbers = [number * number for number in numbers if number % 2 == 0]
```

这并不是某种神秘的“高级数值语法”。它只是把原本需要写成循环的步骤压缩成一行：依次取出 `numbers` 中的元素，保留偶数，再把它们平方并组成新列表。真正需要警惕的反而是另一类同样简短的表达式：

```python
res = [[0]] * n
```

它看起来像创建了 `n` 个独立的 `[0]`，实际上却让 `n` 个位置指向**同一个内部列表**。之后修改其中一项，所有“行”都会一起变化。短并不等于简单；把表达式求出的对象、是否创建副本，以及是否原地修改分清楚，代码才不会在最安静的地方出错。

本文讨论的是 Python 标准语法和内置函数中最常用的一组数值与序列表达式。目标不是背下尽可能多的技巧，而是建立一条可验证的判断路径：**表达式产出什么对象、对象是否可变、操作是创建新对象还是修改原对象、结果是否仍然共享内部对象。**

## 一、先建立边界：Python 列表不是数值数组

Python 的 `int`、`float` 可以直接参与数值计算，但 `list` 的 `+` 和 `*` 主要表示**拼接与重复**，不是线性代数中的向量运算。

```python
values = [1, 2, 3]

print(values * 2)        # [1, 2, 3, 1, 2, 3]
print(values + [4, 5])   # [1, 2, 3, 4, 5]
```

所以，下面的代码不会给每个元素乘以 `2`：

```python
values * 2
```

如果目标是逐元素计算，应明确写出计算规则：

```python
doubled = [value * 2 for value in values]
print(doubled)  # [2, 4, 6]
```

这个区别很重要：`list` 是通用的对象容器，不记录统一的数值类型、维度或矩阵形状。需要大规模逐元素计算、广播、矩阵乘法时，应使用 NumPy、PyTorch 等专门的数组库；它们的 `*` 才可能被定义为逐元素乘法。不要把一个库的运算符含义擅自套到 Python 内置列表上，解释器没有替你补课的义务。

## 二、整数和浮点数：先弄清每个运算符的结果

日常数值计算最常用的是算术、比较和逻辑运算。它们看起来基础，但整数除法与负数取模恰好是业务代码和算法题里很常见的错误来源。

### 1. 四则运算、整除、取模与幂

```python
a = 17
b = 5

print(a + b)   # 22
print(a - b)   # 12
print(a * b)   # 85
print(a / b)   # 3.4，普通除法总是得到 float
print(a // b)  # 3，向下取整的商
print(a % b)   # 2，余数
print(a ** b)  # 1419857，17 的 5 次方
```

`//` 不是“直接去掉小数部分”，它是**向负无穷取整**。这一区别在负数上才会显现：

```python
print(-17 // 5)  # -4
print(-17 % 5)   # 3
```

Python 保持下面的恒等式成立：

```text
a == (a // b) * b + (a % b)
```

将 `a = -17`、`b = 5` 代入：`-17 == (-4) * 5 + 3`。当除数 `b` 为正数时，余数位于 `0` 到 `b - 1`；这使得 `%` 很适合循环下标和周期映射：

```python
weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

for offset in range(10):
    print(weekdays[offset % len(weekdays)])
```

若同时需要商和余数，使用 `divmod()` 比分别计算 `//` 与 `%` 更清楚：

```python
total_seconds = 3671
hours, remainder = divmod(total_seconds, 3600)
minutes, seconds = divmod(remainder, 60)

print(hours, minutes, seconds)  # 1 1 11
```

`pow()` 是幂运算函数；三参数形式可高效计算模幂，常见于密码学和数论算法：

```python
print(pow(2, 10))       # 1024
print(pow(2, 10, 7))    # 2，等价于 (2 ** 10) % 7，但适合大整数
```

### 2. 比较链和条件表达式

Python 允许把连续比较写成链：

```python
score = 87
passed = 60 <= score < 100
print(passed)  # True
```

它等价于：

```python
passed = (60 <= score) and (score < 100)
```

不要把它误读成 `(60 <= score) < 100`。比较链会按区间判断，并且中间表达式不会被无意义地重复求值。

只有两个分支时，条件表达式可以让“根据条件取一个值”的意图保持紧凑：

```python
status = "pass" if score >= 60 else "fail"
```

它适合返回值简单、条件本身容易读懂的场景。若两个分支都包含多步计算、函数调用或副作用，请使用普通的 `if/else`。把三层业务判断折叠成一行，并不会令逻辑变高级，只会令调试变得比较漫长。

### 3. 浮点数不能用“看起来相等”代替比较规则

二进制浮点数无法精确表示许多十进制小数，因此：

```python
print(0.1 + 0.2 == 0.3)  # False
```

不要用四舍五入来掩盖所有误差，而应按业务容差比较：

```python
from math import isclose

result = 0.1 + 0.2
print(isclose(result, 0.3, rel_tol=1e-9, abs_tol=0.0))  # True
```

`rel_tol` 是相对误差容限，适合数值量级不固定的结果；`abs_tol` 是绝对误差容限，适合接近 `0` 的数。涉及金额时通常不应使用 `float`，而应按业务规则使用最小货币单位的整数，或使用 `decimal.Decimal`。精度不是展示层的小数位问题，而是数据模型的一部分。

## 三、`[0] * n` 为什么通常安全，`[[0]] * n` 为什么危险

先看一维列表：

```python
n = 4
zeros = [0] * n

print(zeros)  # [0, 0, 0, 0]
```

这里重复的是整数 `0`。整数是不可变对象，后续写：

```python
zeros[0] = 99
print(zeros)  # [99, 0, 0, 0]
```

发生的是第 `0` 个位置改为绑定另一个整数对象，其他位置不会受影响。因此，`[0] * n` 很适合初始化数字、`None`、布尔值、字符串等不可变元素组成的一维列表。

问题出现在被重复的元素本身是**可变对象**时：

```python
n = 3
res = [[0]] * n

res[0].append(1)
print(res)  # [[0, 1], [0, 1], [0, 1]]
```

`* n` 创建的是新的**外层列表**，但它只是把同一个内部列表的引用放了 `n` 次。概念关系如下：

```text
res[0] ─┐
res[1] ─┼──> 同一个列表对象 [0]
res[2] ─┘
```

因此，`append()` 修改该内部列表后，所有位置都观察到同一份变化。可以用 `is` 验证身份：

```python
res = [[0]] * 3

print(res[0] is res[1])  # True
print(res[1] is res[2])  # True
```

### 1. 创建独立二维列表的正确方式

每一行都应在循环的每一次迭代中重新创建：

```python
rows = 3
cols = 4
matrix = [[0] * cols for _ in range(rows)]

matrix[0][1] = 9
print(matrix)
# [[0, 9, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
```

这里外层推导式执行 `rows` 次，而每次执行 `[0] * cols` 都会创建一个新的行列表。验证结果：

```python
print(matrix[0] is matrix[1])  # False
```

错误写法与正确写法应放在一起记忆：

| 目标 | 容易出错的写法 | 正确写法 |
| ---- | -------------- | -------- |
| `n` 个独立空列表 | `[[]] * n` | `[[] for _ in range(n)]` |
| `rows × cols` 零矩阵 | `[[0] * cols] * rows` | `[[0] * cols for _ in range(rows)]` |
| `n` 个独立字典 | `[{}] * n` | `[{} for _ in range(n)]` |

### 2. 赋值、浅拷贝与深层嵌套

即使不使用 `*`，也可能意外共享内部对象：

```python
original = [[1, 2], [3, 4]]
copied = original.copy()

copied[0].append(99)
print(original)  # [[1, 2, 99], [3, 4]]
```

`list.copy()` 只复制外层列表；内部两个行列表仍与 `original` 共享。若要逐行复制，可明确写：

```python
copied = [row.copy() for row in original]
```

更复杂、层数不固定的数据才考虑 `copy.deepcopy()`。但深拷贝不是默认的“安全按钮”：它会额外消耗时间和内存，也可能破坏本应共享的对象关系。优先回答“哪些层必须独立”，然后在那些层创建对象，才是更稳妥的设计。关于名称绑定、对象身份与可变性的完整心智模型，可继续阅读同栏目中的 [Python 没有 new：对象创建、名称绑定与“引用类型”](python_no_new_object_identity_and_references.md)。

## 四、列表、集合和字典推导式：把循环变成数据构造

**推导式**是从一个或多个可迭代对象按规则产生容器的表达式。最基本的列表推导式结构是：

```python
[表达式 for 变量 in 可迭代对象 if 条件]
```

其中 `if 条件` 可选。它可以逐项翻译为普通循环。

```python
numbers = [1, 2, 3, 4, 5, 6]
squares = [number * number for number in numbers if number % 2 == 0]

print(squares)  # [4, 16, 36]
```

等价的普通循环是：

```python
squares = []
for number in numbers:
    if number % 2 == 0:
        squares.append(number * number)
```

推导式并没有跳过循环，只是将“遍历、筛选、转换、收集”四件事并排写出。当表达式和条件都很短时，它比手写临时列表更容易看清数据流。

### 1. 条件放在末尾是筛选，放在表达式中是二选一映射

这两种写法外形接近，含义却不同：

```python
numbers = [1, 2, 3, 4]

only_even = [number for number in numbers if number % 2 == 0]
labels = ["even" if number % 2 == 0 else "odd" for number in numbers]

print(only_even)  # [2, 4]
print(labels)     # ['odd', 'even', 'odd', 'even']
```

- 末尾的 `if` 决定元素是否进入结果，所以结果更短。
- 表达式中的 `if ... else ...` 为每个输入元素选择一个输出，所以结果长度不变。

### 2. 字典与集合推导式

字典推导式用 `key: value` 产生键值对：

```python
names = ["alice", "bob", "carol"]
name_lengths = {name: len(name) for name in names}

print(name_lengths)
# {'alice': 5, 'bob': 3, 'carol': 5}
```

集合推导式适合转换后顺便去重：

```python
raw_tags = ["Python", "python", " SQL ", "sql"]
normalized_tags = {tag.strip().lower() for tag in raw_tags}

print(normalized_tags)  # {'python', 'sql'}，集合的显示顺序不保证固定
```

集合没有重复元素，也不保证按插入顺序索引；如果需要稳定顺序的去重结果，可配合一个 `seen` 集合写普通循环，或按实际需求使用 `dict.fromkeys()`。

### 3. 双层循环可以表达笛卡尔积，但别把它写成迷宫

```python
colors = ["red", "blue"]
sizes = ["S", "M"]

variants = [f"{color}-{size}" for color in colors for size in sizes]
print(variants)  # ['red-S', 'red-M', 'blue-S', 'blue-M']
```

它等价于外层 `for color`、内层 `for size`。推导式中的 `for` 顺序与普通嵌套循环的顺序一致。若出现三层循环、多个筛选条件、异常处理或重要副作用，改写为普通 `for` 循环通常更好；推导式应压缩重复结构，不应负责隐藏复杂控制流。

## 五、切片与步长：读取一段序列，也可以替换一段序列

切片的形式是：

```python
sequence[start:stop:step]
```

- `start`：起始下标，包含该位置。
- `stop`：结束下标，不包含该位置。
- `step`：步长，默认是 `1`。

```python
items = [10, 20, 30, 40, 50, 60]

print(items[1:4])   # [20, 30, 40]
print(items[:3])    # [10, 20, 30]
print(items[::2])   # [10, 30, 50]
print(items[-3:])   # [40, 50, 60]
print(items[::-1])  # [60, 50, 40, 30, 20, 10]
```

读取列表切片会创建一个新的**外层列表**：

```python
source = [1, 2, 3]
copied = source[:]

print(copied == source)  # True：元素相同
print(copied is source)  # False：外层列表不同
```

这仍是浅拷贝；若元素是嵌套列表，内部对象照样可能共享。

### 1. 切片赋值会原地修改原列表

切片出现在赋值左侧时，含义不同：

```python
items = [10, 20, 30, 40, 50]
items[1:4] = [200, 300]

print(items)  # [10, 200, 300, 50]
```

它修改的是已有 `items` 对象，而不是让名字 `items` 重新绑定到新列表。删除一段元素也可以写成：

```python
del items[1:3]
```

当另一个变量也指向同一列表时，切片赋值的变化对两者都可见：

```python
items = [1, 2, 3]
alias = items
items[:] = [9, 8]

print(alias)  # [9, 8]
```

这在需要保留列表对象身份、但整体替换其内容的场景很有用；如果只是想得到新列表，写 `items = [9, 8]` 更明确。修改对象与重新绑定名称不是同一件事。

## 六、`range`、`enumerate` 与 `zip`：让遍历意图清楚

### 1. `range` 表示整数范围，不会先创建一大串整数

```python
for index in range(2, 10, 2):
    print(index)
```

输出 `2、4、6、8`。`range(start, stop, step)` 同样遵守“包含开始、不包含结束”的规则。它是惰性的范围对象，适合循环控制；只有显式写 `list(range(...))` 才会构造列表。

遍历列表元素时，不要因为能写下标就总写 `range(len(items))`：

```python
# 仅需要值时，直接遍历值。
for item in items:
    print(item)
```

### 2. 同时需要下标和值，用 `enumerate`

```python
students = ["Yukino", "Yui", "Hachiman"]

for index, student in enumerate(students, start=1):
    print(index, student)
```

`enumerate()` 每轮产生一对 `(index, value)`。它避免了手工维护计数器，也避免了为只读遍历而频繁使用 `students[index]`。

### 3. 并排遍历多个序列，用 `zip`

```python
names = ["Alice", "Bob", "Carol"]
scores = [91, 85, 98]

for name, score in zip(names, scores):
    print(f"{name}: {score}")
```

普通 `zip()` 会在最短的输入序列结束时停止：

```python
print(list(zip([1, 2, 3], [10, 20])))
# [(1, 10), (2, 20)]
```

若长度不一致代表数据错误，在 Python 3.10 及以上可使用 `strict=True`：

```python
for name, score in zip(names, scores, strict=True):
    print(name, score)
```

这会在长度不一致时抛出 `ValueError`，避免悄悄丢掉尾部数据。是否启用它取决于业务：配对字段通常应严格，展示时的可选数据则未必。

## 七、聚合函数：从一组数得到一个结果

**聚合**是把多个元素归约为一个结果，例如求和、计数、最值或布尔判断。

```python
scores = [91, 85, 98]

print(sum(scores))            # 274
print(len(scores))            # 3
print(sum(scores) / len(scores))  # 91.33333333333333
print(min(scores))            # 85
print(max(scores))            # 98
```

空序列是必须明确处理的边界。`sum([])` 返回 `0`，但 `min([])` 和 `max([])` 无法凭空决定结果，会抛出异常。若业务上存在合理默认值，可使用 `default`：

```python
scores = []
highest_score = max(scores, default=0)
print(highest_score)  # 0
```

注意默认值必须符合业务语义；若 `0` 不是合法分数，返回它会把“没有数据”伪装成“最高分为零”。此时 `None` 或显式异常更诚实。

### 1. 用 `key` 指定“按什么比较”

`min()`、`max()` 和 `sorted()` 不只能比较数字，也可以通过 `key` 先提取排序依据：

```python
users = [
    {"name": "Alice", "score": 91},
    {"name": "Bob", "score": 85},
    {"name": "Carol", "score": 98},
]

top_user = max(users, key=lambda user: user["score"])
print(top_user)  # {'name': 'Carol', 'score': 98}
```

`key` 函数接收每个元素，返回用于比较的值；原来的字典不会被替换成分数。简单字段访问也可以用 `operator.itemgetter("score")`，但 `lambda` 对初学者已足够清晰。

### 2. `any()` 与 `all()`：把多个条件归约为一个布尔值

```python
scores = [91, 85, 98]

has_failed = any(score < 60 for score in scores)
all_passed = all(score >= 60 for score in scores)

print(has_failed)  # False
print(all_passed)  # True
```

`any()` 在遇到第一个真值后即可结束，`all()` 在遇到第一个假值后即可结束；后面的生成器表达式不必全部计算。它们在空输入上的规则是：

```python
print(any([]))  # False：不存在一个真元素
print(all([]))  # True：不存在反例
```

`all([]) == True` 是逻辑上的“空集没有反例”，不是“空列表的检查已经成功完成”。如果“至少有一条数据”也是条件，应一起写明：

```python
valid = bool(scores) and all(score >= 60 for score in scores)
```

## 八、排序、去重与频次统计：区分“返回新值”和“原地修改”

`sorted()` 接收任意可迭代对象并返回新列表；`list.sort()` 则原地修改已有列表，并返回 `None`。

```python
scores = [91, 85, 98]

ascending = sorted(scores)
print(ascending)  # [85, 91, 98]
print(scores)     # [91, 85, 98]，原列表没变

scores.sort(reverse=True)
print(scores)     # [98, 91, 85]，原列表已改变
```

不要写：

```python
scores = scores.sort()
```

这会让 `scores` 变为 `None`。`sort()` 返回 `None` 正是在提醒你：它的结果已经写回对象本身，不需要、也不应再接一个结果变量。

### 1. 保序去重

集合可以去重，但不应被用来承诺排序结果。若要保留第一次出现的顺序，现代 Python 中可写：

```python
items = ["python", "sql", "python", "redis", "sql"]
unique_items = list(dict.fromkeys(items))

print(unique_items)  # ['python', 'sql', 'redis']
```

字典键不能重复，且 Python 3.7 以后语言保证字典保持插入顺序，因此 `dict.fromkeys()` 能完成保序去重。若需要自定义“相同”的规则，例如按 `name.lower()` 去重，使用显式循环会更容易说明判断依据。

### 2. 统计频次

标准库 `collections.Counter` 能把元素映射到出现次数：

```python
from collections import Counter

languages = ["python", "java", "python", "go", "python", "java"]
counts = Counter(languages)

print(counts["python"])       # 3
print(counts.most_common(2))   # [('python', 3), ('java', 2)]
```

它适合可哈希元素，例如字符串、整数、元组。列表和字典是可变且不可哈希的，不能直接作为 `Counter` 的键；那不是 `Counter` 的任性，而是字典键必须在存储期间保持可哈希的基本要求。

## 九、生成器表达式：不需要中间列表时，让数据按需流动

列表推导式立即创建完整列表：

```python
squares = [number * number for number in range(1_000_000)]
```

若最终只需要一个聚合结果，就没有必要先把一百万个平方数都保存下来。生成器表达式使用圆括号：

```python
total = sum(number * number for number in range(1_000_000))
```

这里 `sum()` 逐个请求生成器产生下一个平方数；每个数被累加后即可丢弃，内存占用更低。对 `sum()`、`any()`、`all()`、`max()` 这类只消费一次输入的函数，生成器表达式尤其自然。

需要注意两点：

- 生成器只能从前往后消费一次；消费完后再次遍历不会重新得到数据。
- 如果后续确实需要索引、重复遍历或展示完整结果，就应创建列表，不必为了“节省内存”强行牺牲可读性。

```python
numbers = (number * number for number in range(3))

print(list(numbers))  # [0, 1, 4]
print(list(numbers))  # []，已经被消费
```

## 十、一个完整的小例子：从原始分数到可用报告

下面把前面的表达式放进一条清晰的数据处理链。输入是学生与分数的记录，其中分数可能是字符串，也可能缺失：

```python
records = [
    {"name": "Alice", "score": "91"},
    {"name": "Bob", "score": "58"},
    {"name": "Carol", "score": None},
    {"name": "Dave", "score": "98"},
]
```

先只保留能转换为整数的记录。这里用普通循环而不是一条复杂推导式，因为 `try/except` 是明确的异常边界，写开更容易维护：

```python
valid_records = []

for record in records:
    raw_score = record["score"]
    if raw_score is None:
        continue

    try:
        score = int(raw_score)
    except ValueError:
        continue

    valid_records.append({**record, "score": score})
```

`{**record, "score": score}` 创建一个新字典：保留原有字段，并用整数 `score` 覆盖字符串分数。它不会修改 `records` 中原始字典，这对保留原始输入与转换后数据的边界很有帮助。

接着计算统计结果：

```python
scores = [record["score"] for record in valid_records]
passed_names = [
    record["name"]
    for record in valid_records
    if record["score"] >= 60
]

report = {
    "count": len(scores),
    "average": sum(scores) / len(scores) if scores else None,
    "highest": max(scores, default=None),
    "all_passed": bool(scores) and all(score >= 60 for score in scores),
    "passed_names": passed_names,
}

print(report)
```

输出为：

```python
{
    'count': 3,
    'average': 82.33333333333333,
    'highest': 98,
    'all_passed': False,
    'passed_names': ['Alice', 'Dave'],
}
```

这个例子里有几条可迁移的规则：

- 用 `continue` 与 `try/except` 明确清洗失败的边界，而不是假定输入永远正确。
- 用推导式从结构化记录提取数值、筛选名称。
- 对可能为空的数据，在除法前用条件表达式处理，并为 `max()` 给出符合语义的默认值。
- 用生成器表达式传给 `all()`，避免先创建只会使用一次的布尔列表。
- 用字典解包创建转换后的记录，避免无意修改调用方或上游还会使用的原始数据。

## 十一、选择表达式时的检查清单

面对一行看似巧妙的 Python 代码，可以按下面顺序判断，而不是凭感觉猜它会不会“自动复制”：

1. 操作对象是什么？是数字、字符串、列表、字典，还是第三方数组对象？同一个 `*` 在不同类型上的含义可能完全不同。
2. 表达式是创建新对象还是原地修改？`sorted(items)` 与 `items.sort()`、`items + other` 与 `items.extend(other)` 就分别属于两类。
3. 若创建了容器，内部元素是否是可变对象？`[0] * n` 通常安全，`[[]] * n` 则共享同一个列表。
4. 结果会不会为空？除法、`min()`、`max()`、`all()` 的边界语义是否符合业务约定？
5. 推导式是否仍比普通循环清楚？一旦包含多层条件、异常处理、日志或副作用，就应把步骤拆开。
6. 是否真的需要完整列表？只做一次聚合时，可以把生成器表达式直接交给 `sum()`、`any()` 或 `all()`。

## 十二、总结

Python 的常用表达式可以分成几类理解：

- 数值运算中，`/`、`//`、`%`、`divmod()` 与 `pow()` 各自有明确的结果规则；负数整除和浮点比较尤其不能靠直觉。
- 内置 `list` 的 `+` 与 `*` 是拼接和重复，不是逐元素数值计算；逐元素处理通常使用推导式。
- `[0] * n` 可以初始化不可变值的一维列表；`[[0]] * n` 会重复同一个可变内部列表。独立二维结构应使用嵌套推导式。
- 推导式适合短小的“遍历—筛选—转换—收集”流程；复杂控制流应保留为普通循环。
- 切片读取产生浅拷贝，切片赋值原地修改；两者的对象身份语义不同。
- `enumerate()`、`zip()`、`sum()`、`min()`、`max()`、`any()`、`all()` 和 `sorted()` 能清楚表达遍历、配对、聚合与排序意图，但空输入和原地修改是必须先想清楚的边界。
- 生成器表达式适合只消费一次的聚合；需要复用结果时，列表反而更合适。

所谓“高级表达式”并不在于把更多动作塞进更少字符，而在于它能否准确表达数据流与对象关系。先让正确性变得显而易见，再考虑是否值得把循环压缩成一行；这比事后追查一排同时变掉的矩阵行，要体面得多。
