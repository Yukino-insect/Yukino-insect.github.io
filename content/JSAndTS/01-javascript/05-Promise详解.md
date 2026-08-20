+++
date = '2026-08-20T18:21:00+08:00'
draft = false
title = 'Promise 详解：状态、链式调用、错误传播与并发控制'
+++

Promise 是 JavaScript 异步编程的核心。`fetch` 返回 Promise，`async` 函数返回 Promise，很多浏览器 API 和第三方库也以 Promise 表示异步结果。

如果只知道 `.then()` 和 `.catch()`，可以写出能跑的代码；但一旦遇到链式调用、并发请求、错误传播、微任务顺序，就容易开始凭感觉猜。工程代码不是占卜，至少这里不应该是。

## 一、Promise 解决什么问题

异步任务有一个共同点：结果现在还没有，将来才知道。

例如网络请求：

```js
const promise = fetch('/api/posts')
```

此时 `promise` 不是文章列表，而是一个“未来会得到响应”的对象。

Promise 用统一形式描述未来结果：

- 成功：得到一个值。
- 失败：得到一个错误。
- 进行中：还没有结果。

## 二、三种状态

Promise 有三种状态：

| 状态 | 含义 |
| ---- | ---- |
| `pending` | 等待中 |
| `fulfilled` | 已成功 |
| `rejected` | 已失败 |

状态一旦从 `pending` 变成 `fulfilled` 或 `rejected`，就不会再改变。

```js
const promise = new Promise((resolve, reject) => {
  resolve('success')
  reject(new Error('fail'))
})

promise.then(value => {
  console.log(value) // 'success'
})
```

后面的 `reject` 不会生效。Promise 的状态不是弹簧门，不会来回摆动。

## 三、创建 Promise

可以通过 `new Promise` 创建：

```js
const promise = new Promise((resolve, reject) => {
  setTimeout(() => {
    resolve('done')
  }, 1000)
})
```

构造函数接收一个 executor 函数，这个函数会**立即同步执行**。

```js
console.log('A')

const promise = new Promise(resolve => {
  console.log('B')
  resolve('C')
})

promise.then(value => {
  console.log(value)
})

console.log('D')
```

输出：

```text
A
B
D
C
```

`then` 回调是异步微任务，但 executor 本身是同步执行。这个细节很小，踩到时声音很响。

## 四、then 返回新的 Promise

`then` 不只是注册回调，它会返回一个新的 Promise。

```js
fetch('/api/posts')
  .then(response => response.json())
  .then(posts => {
    console.log(posts)
  })
```

第一段 `then` 返回 `response.json()`，第二段 `then` 接收解析后的数据。

链式调用的规则：

- 回调返回普通值：下一个 `then` 收到这个值。
- 回调返回 Promise：下一个 `then` 等这个 Promise 完成。
- 回调抛出异常：下一个 `catch` 捕获。

普通值示例：

```js
Promise.resolve(1)
  .then(value => value + 1)
  .then(value => {
    console.log(value) // 2
  })
```

返回 Promise 示例：

```js
Promise.resolve('/api/posts')
  .then(url => fetch(url))
  .then(response => response.json())
  .then(posts => {
    console.log(posts)
  })
```

抛出异常示例：

```js
Promise.resolve()
  .then(() => {
    throw new Error('出错了')
  })
  .catch(error => {
    console.error(error.message)
  })
```

## 五、catch 是错误分支

`catch` 用来捕获前面链路中的 rejected 状态。

```js
fetch('/api/posts')
  .then(response => {
    if (!response.ok) {
      throw new Error('请求失败')
    }
    return response.json()
  })
  .then(posts => {
    console.log(posts)
  })
  .catch(error => {
    console.error(error)
  })
```

`catch` 也会返回新的 Promise。如果 `catch` 中返回一个值，后面的 `then` 会继续成功执行。

```js
Promise.reject(new Error('fail'))
  .catch(() => {
    return []
  })
  .then(value => {
    console.log(value) // []
  })
```

这很适合兜底：

```js
function loadPosts() {
  return fetch('/api/posts')
    .then(response => response.json())
    .catch(() => [])
}
```

但不要随便吞掉错误。如果错误应该暴露给页面或日志系统，就不要假装它不存在。

## 六、finally 做收尾

`finally` 不关心成功还是失败，适合做收尾动作。

```js
let loading = true

fetch('/api/posts')
  .then(response => response.json())
  .catch(error => {
    console.error(error)
  })
  .finally(() => {
    loading = false
  })
```

常见用途：

- 关闭 loading。
- 释放临时资源。
- 清理定时器。
- 恢复按钮可点击状态。

`finally` 默认不会改变前面的结果，除非它自己抛错或返回 rejected Promise。

## 七、Promise.resolve 与 Promise.reject

`Promise.resolve` 可以把普通值包装成 fulfilled Promise。

```js
Promise.resolve(1).then(value => {
  console.log(value)
})
```

如果传入的本来就是 Promise，会直接采用它的状态。

```js
const original = fetch('/api/posts')
const wrapped = Promise.resolve(original)

console.log(original === wrapped) // true
```

`Promise.reject` 创建 rejected Promise：

```js
Promise.reject(new Error('fail')).catch(error => {
  console.error(error.message)
})
```

在封装统一接口时，这两个方法很有用。

## 八、Promise.all 并发等待

多个任务互不依赖时，可以并发执行。

```js
const [profile, posts] = await Promise.all([
  fetchProfile(),
  fetchPosts()
])
```

`Promise.all` 的特点：

- 所有任务都成功，整体成功。
- 任意一个任务失败，整体失败。
- 返回结果顺序和传入数组顺序一致，不是完成顺序。

```js
const result = await Promise.all([
  Promise.resolve('A'),
  Promise.resolve('B')
])

console.log(result) // ['A', 'B']
```

如果两个请求没有依赖关系，却写成一个等一个：

```js
const profile = await fetchProfile()
const posts = await fetchPosts()
```

总耗时会接近两者相加。并发写法通常更快。

## 九、Promise.allSettled

如果希望每个任务的成功失败都拿到结果，用 `Promise.allSettled`。

```js
const results = await Promise.allSettled([
  fetchProfile(),
  fetchPosts(),
  fetchNotifications()
])

for (const result of results) {
  if (result.status === 'fulfilled') {
    console.log(result.value)
  } else {
    console.error(result.reason)
  }
}
```

返回项有两种结构：

```js
{
  status: 'fulfilled',
  value: '成功结果'
}
```

```js
{
  status: 'rejected',
  reason: new Error('失败原因')
}
```

适合场景：

- 首页多个模块分别加载。
- 批量操作希望展示每项结果。
- 非核心请求失败不影响主流程。

## 十、Promise.race 与 Promise.any

`Promise.race` 谁先完成就采用谁的结果，不管成功还是失败。

```js
const result = await Promise.race([
  fetch('/api/posts'),
  timeout(5000)
])
```

可以用来实现超时：

```js
function timeout(ms) {
  return new Promise((_, reject) => {
    setTimeout(() => {
      reject(new Error('请求超时'))
    }, ms)
  })
}
```

`Promise.any` 谁先成功就采用谁的结果，只有全部失败才失败。

```js
const response = await Promise.any([
  fetch('/api/mirror-a/posts'),
  fetch('/api/mirror-b/posts')
])
```

它适合多个备用源，只要一个成功即可。

## 十一、把回调封装成 Promise

有些老 API 使用回调。可以包装成 Promise。

```js
function wait(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms)
  })
}

wait(1000).then(() => {
  console.log('1 秒后执行')
})
```

再例如把一次性事件封装成 Promise：

```js
function once(element, eventName) {
  return new Promise(resolve => {
    element.addEventListener(eventName, resolve, {
      once: true
    })
  })
}
```

这样就能用统一的 Promise 方式组织异步流程。

## 十二、Promise 与微任务

Promise 回调通常进入微任务队列。

```js
console.log('start')

Promise.resolve().then(() => {
  console.log('promise')
})

setTimeout(() => {
  console.log('timeout')
}, 0)

console.log('end')
```

输出：

```text
start
end
promise
timeout
```

简化顺序：

```text
同步代码
 -> 微任务
 -> 浏览器渲染或进入下一轮任务
 -> 定时器等宏任务
```

不要把 `then` 理解成“马上执行”。它会等当前同步代码跑完。

## 十三、常见反模式

### 1. Promise 构造器包 fetch

不推荐：

```js
function loadPosts() {
  return new Promise((resolve, reject) => {
    fetch('/api/posts')
      .then(response => response.json())
      .then(resolve)
      .catch(reject)
  })
}
```

推荐：

```js
function loadPosts() {
  return fetch('/api/posts').then(response => response.json())
}
```

`fetch` 已经返回 Promise，再包一层只是制造噪音。

### 2. 忘记 return

错误：

```js
fetch('/api/posts')
  .then(response => {
    response.json()
  })
  .then(posts => {
    console.log(posts) // undefined
  })
```

正确：

```js
fetch('/api/posts')
  .then(response => {
    return response.json()
  })
  .then(posts => {
    console.log(posts)
  })
```

箭头函数简写也可以：

```js
fetch('/api/posts')
  .then(response => response.json())
  .then(posts => {
    console.log(posts)
  })
```

### 3. catch 太早吞错

```js
fetch('/api/posts')
  .catch(() => [])
  .then(response => response.json())
```

这里如果 `fetch` 失败，`catch` 返回数组，后面再调用 `response.json()` 就会出新错误。错误处理要放在你真正知道如何恢复的位置。

## 十四、练习

实现一个 `loadDashboard`：

- 并发请求用户信息、文章列表、通知列表。
- 用户信息失败时整体失败。
- 文章和通知失败时使用空数组兜底。

参考方向：

```js
async function loadDashboard() {
  const [profile, postsResult, noticesResult] = await Promise.all([
    fetchProfile(),
    fetchPosts().catch(() => []),
    fetchNotices().catch(() => [])
  ])

  return {
    profile,
    posts: postsResult,
    notices: noticesResult
  }
}
```

Promise 的价值不在于语法好看，而在于它给异步结果建立了一套稳定规则：状态不可逆、链式传递、错误传播、并发组合。掌握这些规则，`async/await` 才不会只是换了一层皮。
