+++
date = '2026-08-20T19:16:00+08:00'
draft = false
title = 'JavaScript 定时任务与定时器：setTimeout、setInterval 与事件循环'
+++

JavaScript 里的定时任务主要通过定时器 API 完成。最常见的是：

- `setTimeout`：延迟一段时间后执行一次。
- `setInterval`：每隔一段时间重复执行。
- `clearTimeout`：取消 `setTimeout`。
- `clearInterval`：取消 `setInterval`。

它们看起来很简单，但只要和事件循环、页面渲染、请求超时、轮询、节流防抖放在一起，就会出现很多细节。定时器不是闹钟那么老实，它只是把回调放进将来的任务队列里。到了时间不代表立刻执行，最多只能说“可以排队了”。这点如果不分清，调试时就会很委屈，虽然委屈并不能改变事件循环。

## 一、setTimeout 基础用法

`setTimeout` 用来延迟执行一个函数。

```js
setTimeout(() => {
  console.log('1 秒后执行')
}, 1000)
```

第二个参数是延迟时间，单位是毫秒。

```text
1000 毫秒 = 1 秒
```

也可以传普通函数：

```js
function sayHello() {
  console.log('hello')
}

setTimeout(sayHello, 1000)
```

注意，不要写成：

```js
setTimeout(sayHello(), 1000)
```

这会立刻执行 `sayHello()`，然后把它的返回值传给 `setTimeout`。

正确：

```js
setTimeout(sayHello, 1000)
```

如果要传参数，可以这样写：

```js
function greet(name) {
  console.log(`hello, ${name}`)
}

setTimeout(() => {
  greet('Yuki')
}, 1000)
```

也可以使用 `setTimeout` 后续参数：

```js
setTimeout(greet, 1000, 'Yuki')
```

工程代码里更常见的是箭头函数，因为它表达得更直观，也方便写多行逻辑。

## 二、setTimeout 不会立刻执行

即使延迟时间写成 `0`，也不会打断当前同步代码。

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

原因是：

```text
当前同步代码先执行
 -> setTimeout 回调被安排到后续任务中
 -> 当前调用栈清空
 -> 事件循环取出定时器任务
 -> 执行回调
```

所以 `setTimeout(fn, 0)` 的含义不是“马上执行”，而是“尽快安排到后面的任务里执行”。

这也是为什么它常用于把某段逻辑延后到当前同步流程之后：

```js
console.log('start')

setTimeout(() => {
  console.log('after current call stack')
}, 0)

console.log('end')
```

输出：

```text
start
end
after current call stack
```

## 三、定时器和事件循环

定时器回调属于任务队列中的任务。Promise 回调通常属于微任务。

看例子：

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

顺序是：

```text
同步代码
 -> 微任务
 -> 下一个任务中的 setTimeout 回调
```

这和 `setTimeout` 的延迟时间是否为 `0` 没有冲突。`0` 只是表示不额外等待指定时长，但它仍然要等当前同步代码和微任务处理完。

再看一个耗时同步代码的例子：

```js
const start = Date.now()

setTimeout(() => {
  console.log(Date.now() - start)
}, 100)

while (Date.now() - start < 1000) {
  // 模拟 1 秒同步阻塞
}
```

你可能以为会输出接近 `100`，但实际会接近 `1000`。

因为主线程被 `while` 占住了。定时器到时间后，回调也只能等调用栈空出来再执行。定时器不会把正在运行的 JavaScript 推开。它没有那么粗鲁，也没有那个能力。

## 四、clearTimeout 取消定时器

`setTimeout` 会返回一个定时器 id。

```js
const timerId = setTimeout(() => {
  console.log('执行')
}, 1000)
```

可以用 `clearTimeout` 取消：

```js
clearTimeout(timerId)
```

完整例子：

```js
const timerId = setTimeout(() => {
  console.log('不会执行')
}, 1000)

clearTimeout(timerId)
```

常见场景：

- 页面卸载时取消定时器。
- 用户取消操作时停止延迟任务。
- 重复触发时取消上一次任务。
- 请求成功后取消超时定时器。

如果定时器已经执行过，再调用 `clearTimeout` 通常没有效果。

```js
const timerId = setTimeout(() => {
  console.log('done')
}, 100)

setTimeout(() => {
  clearTimeout(timerId)
}, 1000)
```

这里 1 秒后取消已经太晚，回调早就执行完了。

## 五、setInterval 基础用法

`setInterval` 用来重复执行任务。

```js
setInterval(() => {
  console.log('每秒执行一次')
}, 1000)
```

它会每隔指定时间把回调安排进任务队列。

取消：

```js
const intervalId = setInterval(() => {
  console.log('tick')
}, 1000)

clearInterval(intervalId)
```

一个倒计时例子：

```js
let seconds = 5

const timerId = setInterval(() => {
  console.log(seconds)
  seconds--

  if (seconds < 0) {
    clearInterval(timerId)
    console.log('结束')
  }
}, 1000)
```

输出：

```text
5
4
3
2
1
0
结束
```

`setInterval` 不会自动停止。只要不取消，它就会一直尝试执行。

## 六、setInterval 的风险

`setInterval` 的问题是：如果回调执行时间很长，或者回调里有异步请求，任务可能发生重叠。

例如：

```js
setInterval(async () => {
  const data = await fetch('/api/status').then(response => response.json())
  console.log(data)
}, 1000)
```

如果某次请求耗时 3 秒，而间隔是 1 秒，下一次请求仍然可能被启动。

结果就是：

```text
第 1 次请求还没结束
第 2 次请求开始
第 3 次请求开始
...
```

这可能导致：

- 请求堆积。
- 响应乱序。
- 旧响应覆盖新状态。
- 后端压力变大。
- 页面状态难以控制。

所以涉及异步请求的轮询，不一定适合直接用 `setInterval`。

## 七、递归 setTimeout

如果你希望“上一次任务完成后，再等待一段时间执行下一次”，可以使用递归 `setTimeout`。

```js
async function poll() {
  try {
    const response = await fetch('/api/status')
    const data = await response.json()
    console.log(data)
  } finally {
    setTimeout(poll, 1000)
  }
}

poll()
```

流程是：

```text
执行 poll
 -> 请求完成
 -> 等 1 秒
 -> 再执行 poll
```

这样不会出现同一个轮询任务重叠执行。

如果需要停止，可以加一个标记：

```js
let stopped = false

async function poll() {
  if (stopped) {
    return
  }

  try {
    const response = await fetch('/api/status')
    const data = await response.json()
    console.log(data)
  } finally {
    if (!stopped) {
      setTimeout(poll, 1000)
    }
  }
}

poll()

function stopPolling() {
  stopped = true
}
```

更完整一点，还可以保存 timer id：

```js
let timerId = null
let stopped = false

async function poll() {
  if (stopped) {
    return
  }

  try {
    const response = await fetch('/api/status')
    const data = await response.json()
    console.log(data)
  } finally {
    if (!stopped) {
      timerId = setTimeout(poll, 1000)
    }
  }
}

function startPolling() {
  stopped = false
  poll()
}

function stopPolling() {
  stopped = true

  if (timerId !== null) {
    clearTimeout(timerId)
    timerId = null
  }
}
```

轮询这种事，宁可写得稍微啰嗦一点，也不要让请求在后台排队排到自己都不好意思。

## 八、sleep 函数

JavaScript 没有内置同步睡眠函数。你不能写：

```js
sleep(1000)
```

然后期待当前函数暂停。浏览器里如果真的同步睡眠，主线程会被卡住，页面也会卡住。

通常可以用 Promise 封装一个异步 `sleep`：

```js
function sleep(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms)
  })
}
```

使用：

```js
async function demo() {
  console.log('start')
  await sleep(1000)
  console.log('end')
}

demo()
```

输出：

```text
start
end
```

中间相隔约 1 秒。

注意，`await sleep(1000)` 暂停的是当前 `async` 函数，不是整个 JavaScript 主线程。

## 九、请求超时

定时器经常用于实现请求超时。

例如配合 `AbortController`：

```js
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController()

  const timerId = setTimeout(() => {
    controller.abort()
  }, options.timeout ?? 5000)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    })

    return response
  } finally {
    clearTimeout(timerId)
  }
}
```

使用：

```js
const response = await fetchWithTimeout('/api/posts', {
  timeout: 3000
})
```

关键点：

- 定时器到时间后调用 `controller.abort()`。
- 请求成功或失败后都在 `finally` 中清理定时器。
- 不清理定时器，可能导致请求完成后仍然触发 abort。

这里的 `finally` 很重要。它不是装饰，是清理资源的位置。

## 十、延迟执行和防抖

定时器常用于防抖。防抖的意思是：连续触发时，只执行最后一次。

搜索输入框很常见：

```js
let timerId = null

function onInput(keyword) {
  if (timerId !== null) {
    clearTimeout(timerId)
  }

  timerId = setTimeout(() => {
    search(keyword)
  }, 300)
}
```

用户连续输入：

```text
j
ja
jav
java
```

每次输入都会取消上一次定时器，只保留最后一次。停下 300ms 后才真正搜索。

可以封装：

```js
function debounce(fn, delay) {
  let timerId = null

  return function (...args) {
    if (timerId !== null) {
      clearTimeout(timerId)
    }

    timerId = setTimeout(() => {
      fn(...args)
    }, delay)
  }
}
```

使用：

```js
const handleSearch = debounce(keyword => {
  search(keyword)
}, 300)

input.addEventListener('input', event => {
  handleSearch(event.target.value)
})
```

防抖适合：

- 搜索框输入。
- 窗口尺寸变化后的重新计算。
- 表单自动保存。
- 连续点击后的最后一次提交。

防抖的核心是“等你停下来再做”。很符合人类在混乱时的理想处理方式，可惜人类自己不总能做到。

## 十一、节流

节流的意思是：一段时间内最多执行一次。

比如滚动事件触发很频繁：

```js
window.addEventListener('scroll', () => {
  console.log('scroll')
})
```

如果每次滚动都执行复杂计算，性能可能不好。

可以节流：

```js
function throttle(fn, delay) {
  let timerId = null

  return function (...args) {
    if (timerId !== null) {
      return
    }

    timerId = setTimeout(() => {
      fn(...args)
      timerId = null
    }, delay)
  }
}
```

使用：

```js
const handleScroll = throttle(() => {
  console.log(window.scrollY)
}, 200)

window.addEventListener('scroll', handleScroll)
```

节流适合：

- 滚动事件。
- 鼠标移动。
- 拖拽过程。
- 高频按钮操作。
- 高频状态同步。

防抖和节流的区别：

| 技术 | 含义 | 适合场景 |
| ---- | ---- | -------- |
| 防抖 | 停止触发一段时间后执行 | 搜索输入、自动保存 |
| 节流 | 固定时间内最多执行一次 | 滚动、拖拽、窗口 resize |

如果你想“最后一次触发后再执行”，用防抖。  
如果你想“持续触发时也保持固定频率执行”，用节流。

## 十二、this 问题

定时器回调里的 `this` 容易让人误会。

```js
const user = {
  name: 'Yuki',
  sayLater() {
    setTimeout(function () {
      console.log(this.name)
    }, 1000)
  }
}

user.sayLater()
```

这里的 `this` 不一定是 `user`。在浏览器非严格场景下，它可能指向 `window`；严格模式下可能是 `undefined`。总之，不要期待它自动记住外层对象。

更稳的写法是使用箭头函数：

```js
const user = {
  name: 'Yuki',
  sayLater() {
    setTimeout(() => {
      console.log(this.name)
    }, 1000)
  }
}

user.sayLater()
```

箭头函数没有自己的 `this`，会使用外层 `sayLater` 的 `this`。

也可以先保存：

```js
const user = {
  name: 'Yuki',
  sayLater() {
    const self = this

    setTimeout(function () {
      console.log(self.name)
    }, 1000)
  }
}
```

现代代码更常用箭头函数。

## 十三、传字符串给 setTimeout

`setTimeout` 允许传字符串：

```js
setTimeout("console.log('hello')", 1000)
```

但不推荐。

原因：

- 类似 `eval`，有安全风险。
- 不利于静态分析。
- 不利于压缩和重构。
- 可读性差。

应该传函数：

```js
setTimeout(() => {
  console.log('hello')
}, 1000)
```

能不用字符串执行代码，就不要用。把代码藏进字符串里，通常只是把问题藏到工具更难帮你的地方。

## 十四、定时器 id 在浏览器和 Node 中不同

在浏览器中，`setTimeout` 通常返回一个数字 id。

```js
const timerId = setTimeout(() => {}, 1000)
```

在 Node.js 中，`setTimeout` 返回的是一个定时器对象。

```js
const timer = setTimeout(() => {}, 1000)
```

但无论是浏览器还是 Node.js，都可以传给 `clearTimeout`：

```js
clearTimeout(timerId)
```

或：

```js
clearTimeout(timer)
```

如果你写 TypeScript，会遇到类型差异：

```ts
let timerId: ReturnType<typeof setTimeout> | null = null
```

这种写法能同时兼容浏览器和 Node 类型环境。

纯 JavaScript 学习阶段，先记住：保存返回值，取消时交给 `clearTimeout`。

## 十五、页面和组件中的清理

定时器如果不清理，可能导致：

- 页面离开后仍然执行回调。
- 组件销毁后仍然更新状态。
- 重复进入页面创建多个定时器。
- 内存泄漏。
- 重复请求。

普通页面中：

```js
const timerId = setInterval(() => {
  console.log('tick')
}, 1000)

window.addEventListener('beforeunload', () => {
  clearInterval(timerId)
})
```

框架中通常在组件卸载时清理。

以 Vue 组合式 API 为例：

```js
import { onMounted, onUnmounted } from 'vue'

let timerId = null

onMounted(() => {
  timerId = setInterval(() => {
    console.log('tick')
  }, 1000)
})

onUnmounted(() => {
  if (timerId !== null) {
    clearInterval(timerId)
  }
})
```

React 中常见写法：

```js
useEffect(() => {
  const timerId = setInterval(() => {
    console.log('tick')
  }, 1000)

  return () => {
    clearInterval(timerId)
  }
}, [])
```

不管框架是什么，原则一样：谁创建定时器，谁负责在合适时机清理。

## 十六、requestAnimationFrame

如果任务和动画或渲染有关，不一定应该用 `setTimeout`。

浏览器提供 `requestAnimationFrame`，它会在浏览器下一次重绘前执行回调。

```js
function animate() {
  // 更新动画状态
  requestAnimationFrame(animate)
}

requestAnimationFrame(animate)
```

它适合：

- 动画。
- 与屏幕刷新相关的 DOM 更新。
- canvas 绘制。

一个简单动画：

```js
const box = document.querySelector('.box')
let x = 0

function move() {
  x += 2
  box.style.transform = `translateX(${x}px)`

  if (x < 300) {
    requestAnimationFrame(move)
  }
}

requestAnimationFrame(move)
```

为什么不用 `setInterval` 做动画？

```js
setInterval(() => {
  x += 2
  box.style.transform = `translateX(${x}px)`
}, 16)
```

这看起来像 60 FPS，但它并不真正和浏览器刷新节奏对齐。后台标签页、设备刷新率、页面负载都会影响实际表现。

动画优先考虑 `requestAnimationFrame`，定时业务逻辑再考虑 `setTimeout` / `setInterval`。

## 十七、后台标签页和时间不准

浏览器可能会限制后台标签页中的定时器频率。

例如页面切到后台后：

- `setTimeout` 可能被延迟。
- `setInterval` 可能变慢。
- 高频定时器可能被节流。

这是浏览器为了省电和降低资源占用做的优化。

所以不要用前端定时器做严格计时。

不推荐：

```js
let seconds = 0

setInterval(() => {
  seconds++
}, 1000)
```

如果要求更准确，应该基于时间戳计算：

```js
const start = Date.now()

setInterval(() => {
  const elapsedSeconds = Math.floor((Date.now() - start) / 1000)
  console.log(elapsedSeconds)
}, 1000)
```

这样即使某次定时器延迟，也能根据真实时间差得到更接近实际的结果。

定时器从来没有承诺“精确准点”。它只是承诺“到了时间后尽量安排”。这两句话差别很大，足够产生很多 bug。

## 十八、常见误区

### 1. 以为 `setTimeout(fn, 0)` 立刻执行

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

它要等当前同步代码执行完。

### 2. 忘记清理定时器

```js
setInterval(() => {
  fetch('/api/status')
}, 1000)
```

如果页面离开后还在执行，就会造成无意义请求。应该保存 id 并清理。

### 3. 用 setInterval 做异步轮询

```js
setInterval(async () => {
  await fetch('/api/status')
}, 1000)
```

如果请求慢于间隔，可能重叠。递归 `setTimeout` 更可控。

### 4. 用定时器做精确计时

定时器可能延迟，也可能在后台标签页被节流。精确计时应该基于时间戳。

### 5. 回调里 this 丢失

```js
setTimeout(function () {
  console.log(this.name)
}, 1000)
```

如果需要外层 `this`，使用箭头函数。

## 十九、练习

### 1. 判断输出顺序

```js
console.log('A')

setTimeout(() => {
  console.log('B')
}, 0)

Promise.resolve().then(() => {
  console.log('C')
})

console.log('D')
```

答案：

```text
A
D
C
B
```

### 2. 实现 sleep

```js
function sleep(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms)
  })
}
```

使用：

```js
async function main() {
  console.log('start')
  await sleep(1000)
  console.log('end')
}
```

### 3. 实现防抖

```js
function debounce(fn, delay) {
  let timerId = null

  return function (...args) {
    if (timerId !== null) {
      clearTimeout(timerId)
    }

    timerId = setTimeout(() => {
      fn(...args)
    }, delay)
  }
}
```

### 4. 实现可停止轮询

```js
function createPolling(task, delay) {
  let timerId = null
  let stopped = true

  async function run() {
    if (stopped) {
      return
    }

    try {
      await task()
    } finally {
      if (!stopped) {
        timerId = setTimeout(run, delay)
      }
    }
  }

  return {
    start() {
      if (!stopped) {
        return
      }

      stopped = false
      run()
    },

    stop() {
      stopped = true

      if (timerId !== null) {
        clearTimeout(timerId)
        timerId = null
      }
    }
  }
}
```

使用：

```js
const polling = createPolling(async () => {
  const response = await fetch('/api/status')
  const data = await response.json()
  console.log(data)
}, 1000)

polling.start()

setTimeout(() => {
  polling.stop()
}, 10000)
```

## 二十、总结

JavaScript 定时任务可以这样记：

```text
setTimeout      -> 延迟执行一次
clearTimeout    -> 取消延迟任务
setInterval     -> 固定间隔重复执行
clearInterval   -> 取消重复任务
递归 setTimeout -> 更适合异步轮询
Promise + setTimeout -> 可以封装 sleep
requestAnimationFrame -> 更适合动画
```

最重要的几点：

- 定时器回调不会打断当前同步代码。
- `setTimeout(fn, 0)` 也要等当前调用栈和微任务处理完。
- 定时器时间不是精确执行时间，只是最早可调度时间。
- `setInterval` 可能导致异步任务重叠。
- 创建定时器后要考虑取消和清理。
- 动画优先使用 `requestAnimationFrame`。

如果只记一句话：

> 定时器不是让 JavaScript 睡觉，也不是让回调准点插队；它只是让宿主环境在指定时间后，把回调安排进事件循环等待执行。
