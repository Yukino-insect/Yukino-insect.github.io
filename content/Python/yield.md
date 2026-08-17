+++

date = '2026-08-16T21:17:41+08:00'
draft = false
title = 'yield'

+++

`yield` 有两个身份：

1. 在普通  generator 里，`yield` 用来 **产出一个值**。类似暂停函数并把值交出去。
2. 在协程式 generator 里，`yield` 还可以 **接收一个值**，这个值由外部通过 `.send(value)` 传进来。

比如：

```python
n = yield r
```

这句代码的含义就是：先把 `r` yield 出去，函数暂停。等外部 send(...) 一个值回来。再把 send 进来的值赋给 `n`。

看一个简单的 generator：

```python
def gen():
    yield 1
    yield 2
    yield 3
   
g = gen()
print(next(g)) #1
print(next(g)) #2
print(next(g)) #3
```

当调用 `gen()` 时，函数体并不会立即执行，它只会创建一个 generator 对象。真正的执行发生在 `next(g)`

并且，每次遇到 `yield`，函数会暂停，并把 `yield` 后面的值交出去。

`send(value)` 可以把一个值送回 generator 内部。

比如：

```python
def gen():
    x = yield "hello"
    print('x = ', x)
   
g = gen()
print(g.send(None)) # hello
g.send(123)
```

同样 `g = gen()` 只是创建了一个 generator，但是并不执行函数体。

`g.send(None)` 会启动 generator，运行到 `x = yield 'hello'`。这时候它先把 `'hello'` 交出去，然后暂停。注意，此时 `x = ...` 还没有完成赋值。

然后调用 `g.send(123)`，generator 从暂停出恢复，刚才的 `yield 'hello'` 表达式会整个替换成 `123`，所以 `x = 123`。

为什么第一次要 `send(None)`

这是 Python generator 的规则：刚创建出来的 generator 还没有运行到第一个 `yield`，所以你不能一上来就给它发送一个真实值。

也就是说，这样会报错：

```python
g = gen()
g.send(123)
```

错误类似：

```python
TypeError: can't send non-None value to a just-started generator
```

因为 generator 还没有停在某个 `yield` 上，它还没准备好接收值。你得先让它运行到第一个 `yield`。

通常有两种写法：

```python
next(g)
```

或者：

```python
g.send(None)
```

它们在启动 generator 这件事上基本等价。 

一个 generator 执行 `close()` 会关闭 generator，后续不能继续 `send`。

## yield from

`yield from` 可以理解为：**把当前 generator 的一部分产出工作，委托给另一个可迭代对象或 generator**。

最简单的例子：

```python
def gen():
    yield from [1, 2, 3]

g = gen()
print(next(g)) # 1
print(next(g)) # 2
print(next(g)) # 3
```

它大致等价于：

```python
def gen():
    for item in [1, 2, 3]:
        yield item
```

所以，`yield from iterable` 的第一层含义就是：把 `iterable` 里面的元素一个个 yield 出去。

但如果被委托的是另一个 generator，`yield from` 就不只是简化 `for + yield` 这么简单了。它还会自动转发：

1. 外部传进来的 `.send(value)`
2. 外部抛进来的 `.throw(...)`
3. 外部调用的 `.close()`
4. 子 generator 的返回值

看一个稍微完整一点的例子：

```python
def child():
    x = yield "child ready"
    yield f"child got {x}"
    return "child result"

def parent():
    result = yield from child()
    yield f"parent got result: {result}"

g = parent()

print(next(g))       # child ready
print(g.send(100))   # child got 100
print(next(g))       # parent got result: child result
```

这里的关键点是：

```python
result = yield from child()
```

`parent()` 会把执行权交给 `child()`：

1. `child()` yield 出来的值，会直接交给 `parent()` 的调用方。
2. 调用方对 `parent()` 做 `.send(100)`，这个值会被转发给 `child()` 当前暂停的 `yield`。
3. `child()` 执行 `return "child result"` 后，这个返回值会成为 `yield from child()` 这个表达式的结果。
4. 所以 `result` 最终等于 `"child result"`。

注意，generator 里写 `return value` 并不是像普通函数那样直接把值返回给调用者，而是会抛出一个 `StopIteration(value)`。`yield from` 会捕获这个 `StopIteration`，并把其中的 `value` 取出来，作为 `yield from` 表达式的结果。

可以把上面的过程粗略理解成：

```python
try:
    while True:
        value = next(child_gen)
        yield value
except StopIteration as e:
    result = e.value
```

当然，真实的 `yield from` 还要处理 `.send()`、`.throw()`、`.close()` 等细节，所以它比这个伪代码更复杂。

`yield from` 常见用途：

1. 展开嵌套的可迭代对象

```python
def flatten(items):
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item

print(list(flatten([1, [2, 3], [4, [5, 6]]])))
# [1, 2, 3, 4, 5, 6]
```

2. 拆分复杂 generator，把一部分逻辑委托给子 generator

```python
def read_header():
    yield "read version"
    yield "read encoding"
    return {"version": 1, "encoding": "utf-8"}

def read_body():
    yield "read content"
    return "body"

def read_file():
    header = yield from read_header()
    body = yield from read_body()
    return {"header": header, "body": body}

g = read_file()

try:
    while True:
        print(next(g))
except StopIteration as e:
    print(e.value)

# read version
# read encoding
# read content
# {'header': {'version': 1, 'encoding': 'utf-8'}, 'body': 'body'}
```

3. 早期协程模型的基础

在 `async/await` 出现之前，Python 的协程曾经大量依赖 generator、`.send()` 和 `yield from`。一个协程可以 `yield from` 另一个协程，把控制权一路交给事件循环。

后来 Python 引入了原生协程：

```python
async def task():
    result = await other_task()
```

从概念上说，`await other_task()` 和早期的 `yield from other_task()` 有历史上的继承关系：它们都表示“当前任务先暂停，等待另一个可等待对象完成，然后再继续”。不过现代 Python 代码里，异步编程应该优先使用 `async def`、`await` 和 `asyncio`，而不是手写 generator 协程。

总结一下：

1. `yield value`：当前 generator 产出一个值，并暂停。
2. `x = yield value`：产出一个值，并等待外部 `.send(...)` 一个值回来赋给 `x`。
3. `yield from iterable`：把另一个可迭代对象里的值逐个产出。
4. `result = yield from generator`：把执行权委托给子 generator，并在子 generator 结束时拿到它的 `return` 值。
