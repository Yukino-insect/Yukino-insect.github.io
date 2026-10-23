+++
date = '2026-10-20T15:30:00+08:00'
draft = false
title = 'Python 列表推导式与生成器表达式：求值时机、惰性迭代与使用边界'
+++

列表推导式和生成器表达式都能把“遍历、过滤、转换”压缩为一条表达式：

```python
squares = [number * number for number in range(10)]
square_stream = (number * number for number in range(10))
```

两者最本质的区别不是方括号和圆括号的形状，而是**何时产生结果**：列表推导式会立刻遍历输入并创建完整列表；生成器表达式只创建一个可迭代的生成器对象，等消费者请求下一个值时才计算对应元素。前者适合要保存、索引、重复遍历的结果，后者适合一次性聚合、短路判断和数据流处理。

这篇文章只聚焦这两种表达式。若还需要回顾切片、集合/字典推导式和 `sum`、`any`、`all` 等通用聚合，可参阅[Python 常用数值与序列表达式：推导式、切片、聚合和可变对象陷阱](Python 常用数值与序列表达式：推导式、切片、聚合和可变对象陷阱.md)。

## 一、先读懂共同语法

最基本的列表推导式语法为：

```python
result = [表达式 for 变量 in 可迭代对象 if 条件]
```

它可理解为下面这个普通循环的“收集结果”版本：

```python
result = []
for number in range(10):
    if number % 2 == 0:
        result.append(number * number)
```

对应的推导式是：

```python
result = [number * number for number in range(10) if number % 2 == 0]
```

两段代码的元素顺序和结果相同。推导式适合把循环体压缩为一个清晰的“筛选后映射”表达式；若循环中还要记录日志、处理异常、更新多个状态或包含复杂分支，普通 `for` 循环通常更易读。

生成器表达式只将外层方括号改为圆括号：

```python
result = (number * number for number in range(10) if number % 2 == 0)
```

此时 `result` 不是 `[0, 4, 16, 36, 64]`，而是一个等待被消费的生成器。

## 二、立即求值与惰性求值

用一个带输出的函数最容易观察时机差异：

```python
def double(number: int) -> int:
    print(f"计算 {number}")
    return number * 2


values = [double(number) for number in range(3)]
print("列表已创建", values)
```

创建 `values` 的那一刻就会依次打印三次“计算”，因为列表必须先拥有全部元素才能存在。

改成生成器表达式：

```python
stream = (double(number) for number in range(3))
print("生成器已创建")

first = next(stream)
print("第一个结果", first)
```

这里只会在 `next(stream)` 时计算 `0`。后续的 `1`、`2` 仍未发生，直到下一次 `next()` 或 `for` 循环继续请求它们。

```text
列表推导式：创建时遍历全部输入 -> 保存全部结果 -> 交给调用方
生成器表达式：创建生成器对象 -> 消费者请求一个值 -> 计算一个值 -> 再等待请求
```

惰性不等于“没有计算”，而是把计算推迟到真正需要结果的时刻。若最终仍会完整遍历生成器，计算总量通常没有消失；节省的主要是中间结果的驻留内存，有时还包括短路后根本不需要执行的后续计算。

## 三、生成器为何能节省内存

假设要对大量输入做一次求和：

```python
total = sum(number * number for number in range(10_000_000))
```

`sum()` 每次向生成器要一个平方数，累加后即可继续处理下一个值；它不需要先创建一千万个整数的列表。相比之下：

```python
total = sum([number * number for number in range(10_000_000)])
```

会先分配并填满一个巨大的临时列表，然后才开始求和。若列表没有其他用途，这笔内存和构建时间通常没有必要。

但“生成器更省内存”不应被简化为“任何地方都该用生成器”。如果后续确实需要索引、长度、排序、重复遍历或随机访问，最终仍要物化为列表；一开始直接创建列表反而更诚实：

```python
candidate_scores = [score(item) for item in candidates]
candidate_scores.sort(reverse=True)
top_ten = candidate_scores[:10]
```

生成器没有 `len()`、下标和 `.sort()`，因为它承诺的是“下一项如何产生”，不是“所有项已经放在哪里”。

## 四、一次性消费：生成器最容易被忽略的边界

列表可以重复遍历：

```python
items = [number * 2 for number in range(3)]
print(list(items))  # [0, 2, 4]
print(list(items))  # [0, 2, 4]
```

生成器在产生一个元素后会向前推进，耗尽后不能自动重头再来：

```python
stream = (number * 2 for number in range(3))

print(list(stream))  # [0, 2, 4]
print(list(stream))  # []
```

这不是 bug，而是迭代器协议的正常语义。若需要两次消费，通常有三种明确选择：

1. 一开始就使用列表；
2. 每次需要时重新创建生成器表达式；
3. 对输入流设计专门的缓存/重放策略，而不是隐式假设它能倒带。

尤其要注意调试代码：`print(list(stream))` 为了显示内容已经把生成器吃完了。之后业务逻辑拿到空结果，往往不是 Python 忘记了数据，而是调试语句先把它拿走了。

## 五、`any`、`all` 与 `next`：惰性带来的短路

生成器表达式与短路消费者搭配时，不仅减少内存，也可能避免无用工作。

```python
def is_invalid(name: str) -> bool:
    print(f"检查 {name}")
    return name == "bad"


names = ["good", "bad", "later"]
has_invalid = any(is_invalid(name) for name in names)
```

`any()` 一旦得到第一个真值就返回，因此不会检查 `"later"`。若写成列表推导式：

```python
has_invalid = any([is_invalid(name) for name in names])
```

所有检查会先完成，短路优势完全消失。类似地：

- `all(condition(item) for item in items)` 在第一个假值时停止；
- `next((item for item in items if matches(item)), None)` 找到第一个匹配项就停止；
- `max(score(item) for item in items)` 不保存全部分数，只维护当前最大值。

不过，生成器延迟执行也会延迟异常。例如除零发生在元素被请求时，而不是创建表达式时：

```python
stream = (10 / number for number in [2, 1, 0])

print(next(stream))  # 5.0
print(next(stream))  # 10.0
print(next(stream))  # 此时才抛出 ZeroDivisionError
```

这对流式处理很自然，但要求异常处理的边界包住**消费**操作，而不只是包住生成器表达式的创建。

## 六、多个 `for` 和 `if` 的执行顺序

推导式可以包含嵌套循环：

```python
pairs = [
    (row, column)
    for row in range(2)
    for column in range(3)
]

print(pairs)
# [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
```

阅读顺序与普通嵌套循环一致：第一个 `for` 在外，后面的 `for` 在内。它等价于：

```python
pairs = []
for row in range(2):
    for column in range(3):
        pairs.append((row, column))
```

`if` 写在某个 `for` 后面时，过滤的是该 `for` 已绑定变量的当前组合：

```python
pairs = [
    (row, column)
    for row in range(3)
    for column in range(3)
    if row != column
]
```

若表达式本身需要二选一，使用条件表达式而不是过滤 `if`：

```python
labels = ["even" if number % 2 == 0 else "odd" for number in range(4)]
```

下面这种写法在语义上不同：

```python
# 只保留偶数，而不是为奇数产生 "odd"。
labels = ["even" for number in range(4) if number % 2 == 0]
```

区分“筛掉元素”和“为每个元素选择结果”，能避免不少看似只是语法位置不同的错误。

## 七、作用域：推导变量不会泄漏到外层

在现代 Python 3 中，列表、集合、字典推导式和生成器表达式都有自己的隐式作用域：

```python
number = "outer"
squares = [number * number for number in range(3)]

print(number)  # outer
```

推导式里的 `number` 不会覆盖外层同名变量。这与 Python 2 的历史行为不同；不要依据旧资料推导今天的代码。

生成器表达式还有一个容易遗漏的细节：最左侧可迭代对象会在创建生成器时求值，其余部分在迭代时求值。实践中最安全的理解仍是：**不要依赖这种微妙的时机安排来表达副作用或资源生命周期**。若输入必须在特定时刻打开、关闭或捕获异常，使用显式的 `with` 和普通循环会更可靠。

## 八、生成器表达式、生成器函数与迭代器

生成器表达式是创建生成器的简写：

```python
stream = (transform(item) for item in source if keep(item))
```

当逻辑需要多步处理、`try/finally`、资源管理或可读的命名步骤时，使用含 `yield` 的生成器函数更合适：

```python
def valid_lines(lines: list[str]):
    for line in lines:
        stripped = line.strip()
        if stripped:
            yield stripped


for line in valid_lines([" first ", "", " second "]):
    print(line)
```

生成器函数在调用时同样不会立刻执行整个函数体；它返回生成器，第一次 `next()`/循环推进时才运行到第一个 `yield`。表达式适合短小、线性的转换；`yield` 函数适合需要解释步骤的流式算法。为了节省两行而把复杂流程压成多层生成器表达式，读者并不会因此获得同样的节省。

迭代器也不限于生成器。文件对象、许多数据库游标和 `map`、`filter` 的返回值都可能是一次性迭代器。面对任何数据源，都应先问：它能否重复遍历、何时读取下一项、谁负责关闭资源？不要只因为它能写进 `for` 循环就默认它等同于列表。

## 九、实际选择：用结果需求决定容器

| 需求 | 首选 | 理由 |
| ---- | ---- | ---- |
| 需要返回完整结果、索引或切片 | 列表推导式 | 结果可重复使用、可随机访问 |
| 只做一次 `sum`、`max`、`any`、`all` | 生成器表达式 | 避免无用中间列表 |
| 可能在首个匹配项停止 | 生成器表达式 | 可利用短路，不计算后续元素 |
| 处理文件、网络、数据库等流 | 生成器表达式或 `yield` 函数 | 按需处理，控制驻留内存 |
| 处理过程有复杂分支/副作用 | 普通 `for` 循环 | 控制流和错误处理更清楚 |
| 要多次遍历一个输入流 | 列表或可重建的迭代器工厂 | 生成器耗尽后不能重放 |

还有一个常见性能误区：不要先用列表推导式构造数据，又立刻把它包进生成器表达式：

```python
# 没有意义：列表已经先完整创建。
total = sum(value for value in [transform(item) for item in source])
```

应直接写成：

```python
total = sum(transform(item) for item in source)
```

同样，不要为了“肯定更快”盲目把每个列表推导式改为生成器。小而需要复用的结果列表通常更简单；性能判断应来自实际数据规模、访问模式和测量，而不是括号形状。

## 十、总结

- 列表推导式立即遍历并保存所有结果；生成器表达式按需产生元素。
- 只需一次聚合或可短路判断时，生成器表达式通常能避免中间列表与后续无用计算。
- 生成器是一次性迭代器：被 `list()`、`sum()`、`for` 等消费后不会自动重置，调试打印也会消耗它。
- 嵌套推导式的 `for`/`if` 顺序与普通嵌套循环一致；过滤 `if` 和条件表达式解决的是不同问题。
- Python 3 推导变量有独立作用域；生成器还会延迟执行计算和异常。
- 简短的映射/过滤适合表达式；复杂步骤、资源管理和副作用适合 `yield` 生成器函数或普通循环。

选择标准很简单：如果你需要“已经存在、可反复查看的一组结果”，就创建列表；如果你只需要“下一项如何产生”，就交给生成器。写出恰好符合消费方式的数据结构，比事后为了节省一点括号或几行代码而补救要可靠得多。
