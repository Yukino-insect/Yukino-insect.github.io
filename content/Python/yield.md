+++
date = '2026-08-15T20:25:31+08:00'
draft = false
title = 'yield 的使用'
+++
`yield` 有两个身份：

1. 在普通  generator 里，`yield` 用来 **产出一个值**，类似暂停函数并把值交出去。
2. 在协程式 generator 里，`yield` 还可以 **接收一个值**，这个值由外部通过 `.send(value)` 传进来

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

`g.send(None)` 会启动 generator，运行到 `x = yield 'hello'`。这时候它先把 `'hello'` 交出去，然后暂停。注意，此时 `x = ...` 还没由完成赋值。

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

一个 generator 执行 `close()` 会关闭 generator，后续不能继续 `send`
