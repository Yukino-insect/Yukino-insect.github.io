+++

date = '2026-08-18T17:40:36+08:00'
draft = false
title = "Python 中的 `*` 与 `**`：参数收集、参数展开与解包语法"

+++

Python 里的 `*` 和 `**` 很容易让人产生一种错觉：好像它们只是“可变参数”的标记。

其实不止如此。

在 Python 中，`*` 和 `**` 同时出现在函数定义、函数调用、容器字面量、赋值解包、类型注解等多个场景里。它们的核心含义可以概括成一句话：

`*` 面向“位置参数序列”，`**` 面向“关键字参数映射”。

当然，这句话只是入口。真正写代码时，细节才是决定你会不会踩坑的部分。

---

## 1. 函数定义中的 `*args`

在函数定义里，`*args` 用来收集多余的位置参数。

```python
def add_all(*args):
    total = 0
    for value in args:
        total += value
    return total


print(add_all(1, 2, 3))  # 6
```

调用：

```python
add_all(1, 2, 3)
```

函数内部得到：

```python
args == (1, 2, 3)
```

注意，`args` 是一个元组。

`args` 这个名字不是语法要求，只是约定俗成。下面这样也可以：

```python
def add_all(*numbers):
    return sum(numbers)
```

但大多数 Python 程序员看到 `*args` 会立刻明白它的含义，所以除非有非常明确的语义理由，否则用 `args` 就很好。

---

## 2. 函数定义中的 `**kwargs`

在函数定义里，`**kwargs` 用来收集多余的关键字参数。

```python
def create_user(**kwargs):
    print(kwargs)


create_user(name="Alice", age=18)
```

输出：

```python
{"name": "Alice", "age": 18}
```

函数内部得到的是一个字典：

```python
kwargs == {
    "name": "Alice",
    "age": 18,
}
```

同样，`kwargs` 这个名字也不是语法要求，只是约定俗成。下面也合法：

```python
def create_user(**options):
    print(options)
```

但在通用包装函数、装饰器、转发参数时，`**kwargs` 是最常见、也最容易被读懂的名字。

---

## 3. `*args` 和 `**kwargs` 一起使用

最常见的写法是：

```python
def func(*args, **kwargs):
    print(args)
    print(kwargs)


func(1, 2, name="Alice", age=18)
```

输出大致是：

```python
(1, 2)
{"name": "Alice", "age": 18}
```

含义是：

- 普通位置参数被收集进 `args`。
- 普通关键字参数被收集进 `kwargs`。

这种模式尤其常见于装饰器和代理函数：

```python
def wrapper(*args, **kwargs):
    print("before call")
    result = target_function(*args, **kwargs)
    print("after call")
    return result
```

这里函数定义处的 `*args, **kwargs` 是“收集参数”。

函数调用处的 `*args, **kwargs` 是“展开参数”。

两边长得一样，但方向相反。一个是把散的参数收起来，一个是把容器里的参数拆出去。看不清这一点，代码就会变成一团很安静的麻烦。

---

## 4. 函数定义中单独的 `*`：强制关键字参数

函数定义里可以单独写一个 `*`，不带名字。

它的意思是：从这里往后的参数必须使用关键字传参。

```python
def connect(host, port, *, timeout, use_ssl):
    print(host, port, timeout, use_ssl)
```

正确调用：

```python
connect("localhost", 5432, timeout=30, use_ssl=True)
```

错误调用：

```python
connect("localhost", 5432, 30, True)
```

因为 `timeout` 和 `use_ssl` 位于 `*` 后面，必须写成关键字参数。

这种写法很适合那些容易混淆的参数：

```python
def resize(width, height, *, keep_ratio=True, resample=True):
    ...
```

调用时必须写清楚：

```python
resize(800, 600, keep_ratio=True, resample=False)
```

比下面这种含义更明确：

```python
resize(800, 600, True, False)
```

后者当然短，但短并不总是美德。有些参数如果不写名字，读代码的人只能靠猜。那就不是简洁，是把理解成本转嫁给别人。

---

## 5. `*args` 后面的参数也是关键字专用参数

只要函数定义里出现了 `*args`，它后面的普通参数也必须通过关键字传递。

```python
def log(message, *values, level="INFO"):
    print(level, message, values)
```

调用：

```python
log("user login", "Alice", "127.0.0.1", level="DEBUG")
```

这里：

```python
message == "user login"
values == ("Alice", "127.0.0.1")
level == "DEBUG"
```

如果你写：

```python
log("user login", "Alice", "127.0.0.1", "DEBUG")
```

那么 `"DEBUG"` 不会自动变成 `level`，而是会被收进 `values`：

```python
values == ("Alice", "127.0.0.1", "DEBUG")
level == "INFO"
```

这就是 `*args` 后面的参数必须用关键字传参的原因。

---

## 6. 函数参数顺序

函数定义中，参数大致按下面顺序排列：

```python
def func(
    positional_only,
    /,
    positional_or_keyword,
    *args,
    keyword_only,
    **kwargs,
):
    ...
```

其中 `/` 表示它前面的参数只能按位置传递；`*` 表示它后面的参数只能按关键字传递。

虽然这篇文章重点是 `*` 和 `**`，但把 `/` 放在一起看，会更容易理解 Python 的参数系统。

示例：

```python
def func(a, /, b, *args, c, **kwargs):
    print(a, b, args, c, kwargs)
```

合法调用：

```python
func(1, 2, 3, 4, c=5, d=6)
```

结果：

```python
a == 1
b == 2
args == (3, 4)
c == 5
kwargs == {"d": 6}
```

不能这样调用：

```python
func(a=1, b=2, c=3)
```

因为 `a` 在 `/` 前面，是 positional-only 参数。

也不能这样调用：

```python
func(1, 2, 3)
```

因为 `c` 在 `*args` 后面，是 keyword-only 参数，必须写成 `c=...`。

---

## 7. 函数调用中的 `*`：展开可迭代对象

在函数调用里，`*` 用来把一个可迭代对象展开成位置参数。

```python
def add(a, b, c):
    return a + b + c


values = [1, 2, 3]

print(add(*values))  # 6
```

等价于：

```python
add(1, 2, 3)
```

`*` 后面不一定是列表，也可以是元组、字符串、生成器等任何可迭代对象：

```python
print(*"abc")
```

等价于：

```python
print("a", "b", "c")
```

如果数量对不上，会报错：

```python
def add(a, b, c):
    return a + b + c


values = [1, 2]

add(*values)
```

会得到类似错误：

```text
TypeError: add() missing 1 required positional argument: 'c'
```

`*` 只是负责展开，不负责替你补参数。Python 没有那么体贴，也没有义务那么体贴。

---

## 8. 函数调用中的 `**`：展开映射为关键字参数

在函数调用里，`**` 用来把一个映射展开成关键字参数。

```python
def create_user(name, age):
    print(name, age)


data = {
    "name": "Alice",
    "age": 18,
}

create_user(**data)
```

等价于：

```python
create_user(name="Alice", age=18)
```

`**` 后面通常是字典，也可以是其他 mapping 对象。

关键点：

- `**` 展开出来的是关键字参数。
- key 必须是字符串。
- 如果 key 对应不上函数参数名，除非函数有 `**kwargs` 接收，否则会报错。
- 如果同一个参数被传了两次，也会报错。

示例：

```python
def create_user(name, age):
    print(name, age)


create_user(name="Bob", **{"name": "Alice", "age": 18})
```

这里 `name` 被传了两次，会报错：

```text
TypeError: create_user() got multiple values for argument 'name'
```

再看一个有 `**kwargs` 的函数：

```python
def create_user(name, **kwargs):
    print(name)
    print(kwargs)


create_user(name="Alice", age=18, city="Tokyo")
```

函数内部：

```python
name == "Alice"
kwargs == {"age": 18, "city": "Tokyo"}
```

---

## 9. 多个 `*` 和多个 `**` 展开

现代 Python 允许在函数调用中使用多个 `*` 和多个 `**`。

```python
def func(a, b, c, d, e):
    print(a, b, c, d, e)


values1 = [1, 2]
values2 = [3, 4]

func(*values1, *values2, 5)
```

等价于：

```python
func(1, 2, 3, 4, 5)
```

`**` 也可以多个：

```python
def create_user(name, age, city):
    print(name, age, city)


base = {"name": "Alice"}
extra = {"age": 18, "city": "Tokyo"}

create_user(**base, **extra)
```

等价于：

```python
create_user(name="Alice", age=18, city="Tokyo")
```

但是函数调用中如果同一个关键字重复，仍然会报错：

```python
create_user(**{"name": "Alice"}, **{"name": "Bob", "age": 18, "city": "Tokyo"})
```

会得到类似错误：

```text
TypeError: create_user() got multiple values for keyword argument 'name'
```

注意，这和字典字面量里的 `**` 不同。字典合并时，后面的 key 会覆盖前面的 key；函数调用时，重复关键字是错误。

---

## 10. 容器字面量中的 `*`

`*` 也可以在列表、元组、集合字面量中展开可迭代对象。

列表：

```python
values = [1, 2, 3]

result = [0, *values, 4]

print(result)  # [0, 1, 2, 3, 4]
```

元组：

```python
values = [1, 2, 3]

result = (0, *values, 4)

print(result)  # (0, 1, 2, 3, 4)
```

集合：

```python
values = [1, 2, 2, 3]

result = {0, *values, 4}

print(result)  # {0, 1, 2, 3, 4}
```

集合会去重，所以 `2` 只保留一个。

这种写法经常用来拼接容器：

```python
new_items = [*old_items, new_item]
```

不过，如果只是合并列表，下面这样也很清楚：

```python
new_items = old_items + [new_item]
```

语法糖不是越多越好。能让代码更清楚时，它才算有价值。

---

## 11. 字典字面量中的 `**`

`**` 可以在字典字面量中展开另一个映射。

```python
default_config = {
    "timeout": 30,
    "retries": 3,
}

user_config = {
    "timeout": 10,
}

config = {
    **default_config,
    **user_config,
}

print(config)
```

结果：

```python
{
    "timeout": 10,
    "retries": 3,
}
```

如果 key 重复，后面的会覆盖前面的。

这个规则很适合做配置合并：

```python
config = {
    **base_config,
    **env_config,
    **user_config,
}
```

含义是：

```text
先使用 base_config
再用 env_config 覆盖
最后用 user_config 覆盖
```

Python 3.9 以后，字典还支持 `|` 合并运算符：

```python
config = base_config | env_config | user_config
```

两种写法都常见。

如果你只是想创建一个新字典并覆盖少量字段，`**` 很直观：

```python
new_user = {
    **user,
    "is_active": True,
}
```

---

## 12. 赋值解包中的 `*`

`*` 还可以出现在赋值语句左侧，用来接收多个值。

```python
first, *middle, last = [1, 2, 3, 4, 5]

print(first)   # 1
print(middle)  # [2, 3, 4]
print(last)    # 5
```

这里 `middle` 会接收中间所有剩余值。

注意，在赋值解包里，被 `*` 标记的变量得到的是列表，不是元组。

再看几个例子：

```python
head, *tail = [1, 2, 3]

print(head)  # 1
print(tail)  # [2, 3]
```

```python
*body, last = [1, 2, 3]

print(body)  # [1, 2]
print(last)  # 3
```

```python
first, *rest = [1]

print(first)  # 1
print(rest)   # []
```

这个语法常用于拆分序列：

```python
command, *args = input_line.split()
```

例如：

```python
input_line = "copy source.txt target.txt"

command, *args = input_line.split()

print(command)  # copy
print(args)     # ["source.txt", "target.txt"]
```

---

## 13. `for` 循环里的星号解包

赋值解包规则也适用于 `for` 循环。

```python
rows = [
    ("Alice", 18, "Tokyo", "Engineer"),
    ("Bob", 20, "Osaka", "Designer"),
]

for name, age, *extra in rows:
    print(name, age, extra)
```

输出：

```python
Alice 18 ["Tokyo", "Engineer"]
Bob 20 ["Osaka", "Designer"]
```

因为 `for name, age, *extra in rows` 本质上就是每轮循环做一次解包赋值。

---

## 14. `*` 在函数定义和调用中的方向相反

这是理解 `*args` 最重要的一点。

函数定义时：

```python
def func(*args):
    ...
```

意思是收集参数。

函数调用时：

```python
func(*args)
```

意思是展开参数。

完整例子：

```python
def target(a, b, c):
    print(a, b, c)


def wrapper(*args):
    target(*args)


wrapper(1, 2, 3)
```

调用过程是：

```text
wrapper(1, 2, 3)
```

进入 `wrapper` 后：

```python
args == (1, 2, 3)
```

然后：

```python
target(*args)
```

等价于：

```python
target(1, 2, 3)
```

`**kwargs` 也是一样。

定义时：

```python
def func(**kwargs):
    ...
```

收集关键字参数。

调用时：

```python
func(**kwargs)
```

展开关键字参数。

---

## 15. 装饰器中最常见的 `*args, **kwargs`

装饰器经常需要包装一个“不知道参数长什么样”的函数。

这时就会使用：

```python
def decorator(func):
    def wrapper(*args, **kwargs):
        print("before")
        result = func(*args, **kwargs)
        print("after")
        return result

    return wrapper
```

使用：

```python
@decorator
def add(a, b):
    return a + b


print(add(1, 2))
```

这里：

- `wrapper(*args, **kwargs)` 负责接住所有传给 `add` 的参数。
- `func(*args, **kwargs)` 负责把这些参数原样转交给原函数。

如果没有这套机制，装饰器就必须为每一种函数签名单独写一版。那样并不优雅，只是工作量很勤奋地增加了。

---

## 16. 类型注解中的 `*args` 和 `**kwargs`

`*args` 和 `**kwargs` 也可以写类型注解。

```python
def add_all(*args: int) -> int:
    return sum(args)
```

这里的含义不是 `args` 这个元组整体是 `int`，而是每一个被收集的位置参数都是 `int`。

也就是说：

```python
add_all(1, 2, 3)
```

是符合注解的。

`**kwargs` 也类似：

```python
def create_user(**kwargs: str) -> None:
    print(kwargs)
```

含义是每个关键字参数的值都是 `str`。

也就是说，静态类型工具会把它理解成类似：

```python
kwargs: dict[str, str]
```

不过在真实项目里，如果关键字参数结构固定，通常更推荐显式写出参数：

```python
def create_user(name: str, email: str, age: int) -> None:
    ...
```

如果参数结构复杂，可以考虑 `TypedDict`、`Unpack` 等更精确的类型工具。但那已经属于类型系统进阶内容，不必急着一次吞下去。

---

## 17. 常见错误

位置参数展开数量不匹配：

```python
def func(a, b):
    ...


func(*[1, 2, 3])
```

错误：

```text
TypeError: func() takes 2 positional arguments but 3 were given
```

关键字参数重复：

```python
def func(name):
    ...


func("Alice", **{"name": "Bob"})
```

错误：

```text
TypeError: func() got multiple values for argument 'name'
```

`**` 的 key 不是字符串：

```python
def func(**kwargs):
    ...


func(**{1: "one"})
```

错误：

```text
TypeError: keywords must be strings
```

把 `*args` 和 `**kwargs` 顺序写反：

```python
def func(**kwargs, *args):
    ...
```

这是语法错误。`*args` 必须在 `**kwargs` 前面。

---

## 18. 常见模式总结

收集位置参数：

```python
def func(*args):
    ...
```

收集关键字参数：

```python
def func(**kwargs):
    ...
```

强制后续参数必须使用关键字：

```python
def func(a, b, *, c, d):
    ...
```

展开列表或元组为位置参数：

```python
func(*values)
```

展开字典为关键字参数：

```python
func(**options)
```

列表中展开：

```python
items = [first, *others, last]
```

元组中展开：

```python
items = (first, *others, last)
```

集合中展开：

```python
items = {first, *others, last}
```

字典中展开：

```python
config = {
    **default_config,
    **user_config,
}
```

赋值解包：

```python
first, *middle, last = values
```

装饰器转发参数：

```python
def wrapper(*args, **kwargs):
    return func(*args, **kwargs)
```

---

## 19. 结论

`*` 和 `**` 的核心可以这样记：

- 在函数定义里，`*args` 是收集多个位置参数。
- 在函数定义里，`**kwargs` 是收集多个关键字参数。
- 在函数定义里，单独的 `*` 表示后面的参数必须通过关键字传递。
- 在函数调用里，`*iterable` 是把可迭代对象展开成位置参数。
- 在函数调用里，`**mapping` 是把映射展开成关键字参数。
- 在列表、元组、集合字面量里，`*` 可以展开可迭代对象。
- 在字典字面量里，`**` 可以展开映射，重复 key 时后面的覆盖前面的。
- 在赋值解包里，`*name` 可以接收多个剩余值，得到的是列表。

最容易混淆的地方是：同样写成 `*args`，在函数定义处是收集，在函数调用处是展开。

```python
def wrapper(*args, **kwargs):
    return func(*args, **kwargs)
```

这段代码里，第一处 `*args, **kwargs` 把外部传进来的参数收进来；第二处 `*args, **kwargs` 又把它们拆开，原样传给 `func`。

看懂这个方向差异，Python 里的装饰器、代理函数、回调封装、配置合并、参数转发，都会清楚很多。语法糖当然是糖，但它并不是为了甜，而是为了让表达力更集中。若只是为了显得熟练而滥用，那就只是把代码写得更像谜语而已。

