+++
date = '2026-08-20T19:12:00+08:00'
draft = false
title = 'JavaScript 异步线程模型：事件循环、任务队列、Promise 与 async await'
+++

很多人从 Python 学到 `async` / `await` 后，再看 JavaScript 的 `async` / `await`，会自然地问：JS 里的异步也是协程吗？它有没有线程？`await` 到底暂停了什么？

先给结论：

> JavaScript 的异步模型核心是事件循环。`async/await` 是 Promise 之上的语法，`await` 会暂停当前 async 函数的后续执行，把后续逻辑安排到 Promise 完成后的微任务中继续运行。

浏览器里的 JavaScript 代码通常运行在主线程上，但浏览器本身不是单线程。定时器、网络、渲染、事件分发、部分文件和底层 I/O 都由宿主环境协作完成。JavaScript 线程负责执行 JS 回调，事件循环负责安排“什么时候执行哪个回调”。

如果把所有东西都叫线程，理解会变得很松散。还是精确一点比较好，虽然听起来不够热闹。

## 一、JavaScript 主线程

浏览器页面中，绝大多数 JavaScript 业务代码运行在主线程。

主线程负责：

- 执行 JavaScript。
- 处理 DOM 操作。
- 响应用户事件回调。
- 参与样式计算和页面渲染调度。

这意味着一段耗时同步代码会卡住页面。

```js
const start = Date.now()

while (Date.now() - start < 5000) {
  // busy loop
}

console.log('done')
```

这 5 秒里，页面很可能无法响应点击、输入和渲染更新。

所以 JavaScript 异步不是为了让 CPU 计算自动变快，而是为了让等待网络、定时器、文件、用户事件这类任务时，不把主线程一直占住。

## 二、调用栈

JavaScript 执行同步代码时，会使用调用栈。

```js
function c() {
  console.log('c')
}

function b() {
  c()
}

function a() {
  b()
}

a()
```

执行过程：

```text
a 入栈
 -> b 入栈
 -> c 入栈
 -> console.log 执行
 -> c 出栈
 -> b 出栈
 -> a 出栈
```

同步代码必须等当前调用栈清空后，事件循环才有机会取出下一个任务执行。

这也是为什么下面代码中，定时器不会立刻执行：

```js
setTimeout(() => {
  console.log('timeout')
}, 0)

console.log('sync')
```

输出：

```text
sync
timeout
```

`setTimeout(..., 0)` 的意思不是“立刻插队”，而是“最早在后续某一轮任务中执行”。它没有贵宾通道。

## 三、宿主环境负责异步能力

JavaScript 语言本身定义了执行模型和 Promise 等机制，但很多异步能力来自宿主环境。

浏览器提供：

- `setTimeout`
- `setInterval`
- DOM 事件。
- `fetch`
- WebSocket。
- Web Worker。
- IndexedDB。

Node.js 提供：

- 文件系统 I/O。
- 网络 I/O。
- 定时器。
- `process.nextTick`。
- `setImmediate`。
- worker threads。

例如：

```js
fetch('/api/posts').then(response => response.json())
```

网络请求不是由 JavaScript 主线程傻等完成。浏览器的网络层负责请求，等响应可用后，再把相关回调安排回事件循环。

因此更准确的说法是：

```text
JS 主线程执行代码
宿主环境处理异步 I/O
事件循环把完成后的回调送回 JS 执行
```

## 四、任务队列

事件循环会从任务队列中取出任务执行。

常见任务包括：

- `setTimeout` 回调。
- `setInterval` 回调。
- 用户点击事件回调。
- 网络事件回调。
- script 初始执行。

示例：

```js
console.log('A')

setTimeout(() => {
  console.log('B')
}, 0)

console.log('C')
```

输出：

```text
A
C
B
```

同步代码先执行。等当前调用栈清空后，事件循环再取出定时器任务。

## 五、微任务队列

Promise 的 `.then()`、`.catch()`、`.finally()` 回调会进入微任务队列。

```js
console.log('A')

Promise.resolve().then(() => {
  console.log('B')
})

console.log('C')
```

输出：

```text
A
C
B
```

微任务也不会打断当前同步代码。它会在当前调用栈清空后执行。

但微任务和普通任务的顺序不同：

```js
console.log('A')

setTimeout(() => {
  console.log('timeout')
}, 0)

Promise.resolve().then(() => {
  console.log('promise')
})

console.log('B')
```

输出：

```text
A
B
promise
timeout
```

原因是：当前同步代码结束后，会先清空微任务队列，再进入下一个任务。

## 六、事件循环的一轮

可以用一个简化模型理解浏览器事件循环：

```text
执行一个任务
 -> 执行这个任务里的同步代码
 -> 调用栈清空
 -> 清空微任务队列
 -> 浏览器有机会进行渲染
 -> 取下一个任务
 -> 重复
```

注意这是简化模型。真实浏览器还涉及渲染时机、用户交互优先级、任务源、后台标签页节流等细节。学习阶段先掌握这个模型已经足够解决大多数问题。

看一个综合例子：

```js
console.log('1')

setTimeout(() => {
  console.log('2')
}, 0)

Promise.resolve().then(() => {
  console.log('3')
})

queueMicrotask(() => {
  console.log('4')
})

console.log('5')
```

输出：

```text
1
5
3
4
2
```

执行顺序：

```text
同步代码：1、5
微任务：3、4
下一个任务：2
```

## 七、async await 在事件循环中的位置

`async/await` 是 Promise 之上的语法。

```js
async function demo() {
  console.log('A')
  await Promise.resolve()
  console.log('B')
}

console.log('start')
demo()
console.log('end')
```

输出：

```text
start
A
end
B
```

执行到：

```js
await Promise.resolve()
```

当前 `demo` 函数会暂停，`await` 后面的代码会被安排在 Promise 完成后的微任务中继续执行。

可以粗略理解成：

```js
function demo() {
  console.log('A')

  return Promise.resolve().then(() => {
    console.log('B')
  })
}
```

这不是完全等价的规范实现，只是帮助理解控制流。

重点是：

- `await` 暂停当前 async 函数。
- `await` 不阻塞整个 JS 主线程。
- `await` 后续代码通过 Promise 微任务恢复。

## 八、await 等待的是什么

`await` 可以等待 Promise，也可以等待普通值。

```js
async function demo() {
  const a = await Promise.resolve(1)
  const b = await 2

  console.log(a, b)
}
```

普通值会被当作已完成的 Promise 处理。

```js
await 2
```

可以理解成：

```js
await Promise.resolve(2)
```

但工程里不建议随便 `await` 普通值。它虽然能跑，但会让读者误以为这里有异步等待。

如果等待的是 rejected Promise，`await` 那一行会抛出异常：

```js
async function load() {
  try {
    await Promise.reject(new Error('failed'))
  } catch (error) {
    console.log(error.message)
  }
}
```

## 九、Promise 微任务和定时器任务

再看一个容易混淆的例子：

```js
async function demo() {
  console.log('A')
  await null
  console.log('B')
}

console.log('start')

setTimeout(() => {
  console.log('timeout')
}, 0)

demo()

Promise.resolve().then(() => {
  console.log('promise')
})

console.log('end')
```

输出：

```text
start
A
end
B
promise
timeout
```

为什么 `B` 在 `promise` 前面？

因为执行 `demo()` 时，`await null` 已经把恢复 `demo` 的微任务排进队列。后面的 `Promise.resolve().then(...)` 又排进另一个微任务。微任务按进入队列的顺序执行。

这类细节不用死背每一道题，但要知道判断方法：

```text
先执行同步代码
遇到 Promise / await，登记微任务
遇到 setTimeout，登记后续任务
同步代码结束后，按顺序清空微任务
最后执行下一个任务
```

## 十、JS 异步是协程吗

如果从“可暂停、之后恢复”的角度看，JavaScript 的 async 函数确实有协程味道。

但在日常学习中，更准确的说法是：

```text
JavaScript async/await 是 Promise 语法糖
它依赖事件循环和微任务队列恢复后续执行
```

和 Python `asyncio` 相似的地方：

- 都有 `async` / `await`。
- `await` 都会暂停当前异步函数。
- 都适合 I/O 等待型任务。
- 都不是让 CPU 密集型代码自动变快。
- 都需要事件循环调度。

不同的地方：

| 对比 | JavaScript | Python asyncio |
| ---- | ---------- | -------------- |
| 异步基础对象 | Promise | coroutine、Task、Future |
| 事件循环来源 | 浏览器或 Node 宿主环境 | `asyncio` 显式管理 |
| 启动方式 | 浏览器自动运行事件循环 | 常用 `asyncio.run()` |
| `await` 对象 | Promise / thenable / 普通值 | awaitable |
| 后续恢复 | Promise 微任务 | event loop 调度 Task |
| 并发组织 | `Promise.all` 等 | `gather`、`TaskGroup` 等 |

所以，不要简单说“JS 的 async/await 就是 Python 协程”。它们在使用体验上相似，但运行时对象、事件循环入口和调度细节不同。

## 十一、JS 有真正的多线程吗

主线程上的 JavaScript 通常一次只执行一段 JS 代码。

但这不表示 JavaScript 世界没有多线程能力。

浏览器有 Web Worker：

```js
const worker = new Worker('/worker.js')

worker.postMessage({
  type: 'start'
})

worker.onmessage = event => {
  console.log(event.data)
}
```

Worker 在独立线程中运行，适合处理：

- 大量计算。
- 数据压缩。
- 图片处理。
- 不需要直接操作 DOM 的任务。

注意：Worker 不能直接访问 DOM。它和主线程通过消息通信。

Node.js 中也有 worker threads，可以用于 CPU 密集型任务。

所以更准确的说法是：

```text
JS 主线程执行模型通常是单线程事件循环
宿主环境可以有其他线程处理 I/O 或 Worker
真正并行计算需要 Worker 等机制
```

## 十二、异步不等于并行

看这段代码：

```js
async function cpuHeavy() {
  let total = 0

  for (let i = 0; i < 10_000_000_000; i++) {
    total += i
  }

  return total
}

cpuHeavy()
```

虽然函数标了 `async`，但循环本身仍然是同步 CPU 计算。它不会因为 `async` 就自动让出主线程。

`async` 只影响返回值和 `await` 行为。没有遇到 `await` 之前，函数体仍然同步执行。

如果要避免长计算卡住页面，可以：

- 拆分任务，分批执行。
- 使用 `requestIdleCallback`。
- 使用 Web Worker。
- 把计算放到后端。
- 使用更高效的数据结构或算法。

不要把 `async` 当性能优化开关。它不是，真的不是。给函数穿上异步外套，里面的同步循环仍然会原地堵门。

## 十三、常见异步来源

### 定时器

```js
setTimeout(() => {
  console.log('later')
}, 1000)
```

### DOM 事件

```js
button.addEventListener('click', () => {
  console.log('clicked')
})
```

### 网络请求

```js
const response = await fetch('/api/posts')
const posts = await response.json()
```

### Promise

```js
Promise.resolve()
  .then(() => {
    console.log('promise done')
  })
```

### 动态导入

```js
const module = await import('./editor.js')
module.mountEditor()
```

它们都会以不同方式把后续工作交给事件循环调度。

## 十四、浏览器渲染与异步

浏览器渲染通常需要主线程参与。如果你连续执行大量同步代码，浏览器就没有机会及时渲染。

```js
button.textContent = '加载中'

heavySyncWork()

button.textContent = '完成'
```

如果 `heavySyncWork()` 很耗时，用户可能根本看不到“加载中”，因为主线程一直被占着，浏览器没机会渲染中间状态。

可以把重任务延后到下一轮任务：

```js
button.textContent = '加载中'

setTimeout(() => {
  heavySyncWork()
  button.textContent = '完成'
}, 0)
```

这至少给浏览器一次处理渲染的机会。更好的方案仍然是拆分任务或使用 Worker。

## 十五、常见误区

### 1. 以为 setTimeout 0 会立刻执行

```js
setTimeout(() => console.log('timeout'), 0)
console.log('sync')
```

输出：

```text
sync
timeout
```

定时器回调至少要等当前同步代码执行完。

### 2. 以为 await 会阻塞整个线程

```js
await fetch('/api/posts')
```

它暂停的是当前 async 函数，不是整个 JS 主线程。

### 3. 以为 async 函数会自动并行

```js
async function demo() {
  heavySyncWork()
}
```

`heavySyncWork()` 仍然同步执行。

### 4. 忘记 Promise 微任务优先于定时器任务

```js
setTimeout(() => console.log('timeout'), 0)
Promise.resolve().then(() => console.log('promise'))
```

输出：

```text
promise
timeout
```

### 5. 把并发写成串行

```js
const user = await fetchUser()
const posts = await fetchPosts()
```

如果二者没有依赖，可以：

```js
const [user, posts] = await Promise.all([
  fetchUser(),
  fetchPosts()
])
```

## 十六、练习

判断输出顺序：

```js
console.log('1')

setTimeout(() => {
  console.log('2')
}, 0)

async function demo() {
  console.log('3')
  await Promise.resolve()
  console.log('4')
}

demo()

Promise.resolve().then(() => {
  console.log('5')
})

console.log('6')
```

答案：

```text
1
3
6
4
5
2
```

原因：

```text
同步代码：1、3、6
微任务：4、5
下一个任务：2
```

最后记住这句话：

> JavaScript 异步模型不是“开很多线程同时跑 JS”，而是“主线程执行同步代码，宿主环境处理等待，事件循环把回调和 Promise 后续逻辑排队送回主线程”。
