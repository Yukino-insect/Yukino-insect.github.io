+++
date = '2026-08-20T18:22:00+08:00'
draft = false
title = 'async 与 await 详解：用同步写法组织异步流程'
+++

`async/await` 是 Promise 之上的语法糖。它没有发明新的异步机制，而是让异步流程更像普通的顺序代码。

这句话听起来轻飘飘，但很重要：如果不理解 Promise，只学 `async/await`，就像只学会穿制服，却不知道自己属于哪个部门。代码看起来整齐，出错时仍然会迷路。

## 一、async 函数总是返回 Promise

在函数前加 `async`，这个函数就会返回 Promise。

```js
async function getNumber() {
  return 1
}

const result = getNumber()

console.log(result) // Promise
```

要拿到值，需要 `await` 或 `.then()`：

```js
getNumber().then(value => {
  console.log(value) // 1
})
```

普通返回值会被包装成 fulfilled Promise。

```js
async function getUser() {
  return {
    id: 1,
    name: 'Yuki'
  }
}
```

等价理解：

```js
function getUser() {
  return Promise.resolve({
    id: 1,
    name: 'Yuki'
  })
}
```

如果 `async` 函数里抛出异常，返回的是 rejected Promise。

```js
async function fail() {
  throw new Error('失败')
}

fail().catch(error => {
  console.error(error.message)
})
```

## 二、await 等待 Promise 完成

`await` 会等待右侧 Promise 完成，并取出成功结果。

```js
async function loadPosts() {
  const response = await fetch('/api/posts')
  const posts = await response.json()
  return posts
}
```

如果右侧不是 Promise，`await` 会把它当成已经成功的值。

```js
async function demo() {
  const value = await 1
  console.log(value)
}
```

不过工程代码里不建议随便 `await` 普通值。它能运行，不代表它表达清楚。

## 三、await 暂停的是当前 async 函数

`await` 不会阻塞整个 JavaScript 线程。它暂停的是当前 `async` 函数后面的逻辑，把控制权交回事件循环。

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

`B` 等当前同步代码执行完后再执行。

所以不要把 `await` 理解成“整个页面卡住等待”。如果页面真的卡住，通常是你写了耗时同步计算，而不是因为 `await fetch()`。

## 四、错误处理

`await` 遇到 rejected Promise 时会抛出异常，可以用 `try...catch` 捕获。

```js
async function loadPosts() {
  try {
    const response = await fetch('/api/posts')

    if (!response.ok) {
      throw new Error('请求失败')
    }

    return await response.json()
  } catch (error) {
    console.error('加载文章失败', error)
    return []
  }
}
```

`try...catch` 的范围要控制好。范围太大，可能分不清到底是哪一步失败。

更清晰的写法：

```js
async function loadPosts() {
  const response = await fetch('/api/posts')

  if (!response.ok) {
    throw new Error('请求失败')
  }

  return response.json()
}

async function initPage() {
  try {
    const posts = await loadPosts()
    renderPosts(posts)
  } catch (error) {
    renderError(error)
  }
}
```

底层函数负责抛出明确错误，页面函数负责决定如何展示错误。

## 五、串行与并发

两个异步任务有依赖关系时，应该串行。

```js
async function loadUserPosts(userId) {
  const user = await fetchUser(userId)
  const posts = await fetchPostsByUser(user.id)

  return {
    user,
    posts
  }
}
```

这里必须先拿到 `user.id`，再请求文章。

如果两个任务互不依赖，应该并发。

```js
async function loadHomeData() {
  const profilePromise = fetchProfile()
  const postsPromise = fetchPosts()

  const profile = await profilePromise
  const posts = await postsPromise

  return {
    profile,
    posts
  }
}
```

更常见的写法是 `Promise.all`：

```js
async function loadHomeData() {
  const [profile, posts] = await Promise.all([
    fetchProfile(),
    fetchPosts()
  ])

  return {
    profile,
    posts
  }
}
```

不要把并发写成串行：

```js
const profile = await fetchProfile()
const posts = await fetchPosts()
```

这不一定错，但如果二者没有依赖关系，就是白白增加等待时间。程序不会因为写得更慢就更沉稳。

## 六、循环里的 await

有些场景需要按顺序处理：

```js
async function uploadFilesInOrder(files) {
  const results = []

  for (const file of files) {
    const result = await uploadFile(file)
    results.push(result)
  }

  return results
}
```

这种写法会一个文件上传完再上传下一个。

如果可以并发：

```js
async function uploadFiles(files) {
  return Promise.all(files.map(file => uploadFile(file)))
}
```

如果要限制并发数，就不能简单 `Promise.all` 全部打出去。可以写一个小型并发池。

```js
async function runWithLimit(tasks, limit) {
  const results = []
  const executing = []

  for (const task of tasks) {
    const promise = Promise.resolve().then(task)
    results.push(promise)

    const cleanup = promise.finally(() => {
      const index = executing.indexOf(cleanup)
      if (index >= 0) {
        executing.splice(index, 1)
      }
    })

    executing.push(cleanup)

    if (executing.length >= limit) {
      await Promise.race(executing)
    }
  }

  return Promise.all(results)
}
```

使用：

```js
const tasks = files.map(file => {
  return () => uploadFile(file)
})

await runWithLimit(tasks, 3)
```

实际项目里也可以使用成熟工具库。关键是知道“并发越多越快”并不永远成立，浏览器连接数、后端压力、失败重试都会影响结果。

## 七、await 与 return

在 `async` 函数里，下面两种写法很多时候效果接近：

```js
async function loadPosts() {
  return fetchPosts()
}
```

```js
async function loadPosts() {
  return await fetchPosts()
}
```

通常可以直接 `return fetchPosts()`。

但如果你需要在当前函数里捕获错误，就必须 `await`：

```js
async function loadPosts() {
  try {
    return await fetchPosts()
  } catch (error) {
    console.error('加载文章失败', error)
    return []
  }
}
```

如果写成：

```js
async function loadPosts() {
  try {
    return fetchPosts()
  } catch (error) {
    return []
  }
}
```

`fetchPosts()` 返回的 rejected Promise 不会被这个同步 `try...catch` 捕获。

## 八、顶层 await

现代 ES Module 支持顶层 `await`。

```js
const config = await fetch('/api/config').then(response => response.json())

export default config
```

它只能在模块中使用，不能在普通脚本里随便写。

顶层 `await` 会影响模块加载：依赖这个模块的其他模块要等它完成。适合少数初始化场景，不适合在公共工具模块里滥用，否则整个应用启动都会被拖住。

## 九、请求取消

`async/await` 本身不提供取消能力。取消通常依赖具体 API，例如 `fetch` 的 `AbortController`。

```js
async function loadPosts(signal) {
  const response = await fetch('/api/posts', {
    signal
  })

  if (!response.ok) {
    throw new Error('请求失败')
  }

  return response.json()
}
```

页面中使用：

```js
const controller = new AbortController()

loadPosts(controller.signal).catch(error => {
  if (error.name === 'AbortError') {
    return
  }

  console.error(error)
})

controller.abort()
```

离开页面、切换路由、重复搜索时，取消旧请求可以减少无效工作，也能避免旧响应覆盖新状态。

## 十、页面状态建模

异步请求最终要落到页面状态。不要只想着“拿数据”，还要表达加载中、失败、空数据。

```js
const state = {
  loading: false,
  data: null,
  error: null
}

async function loadProfile() {
  state.loading = true
  state.error = null

  try {
    state.data = await fetchProfile()
  } catch (error) {
    state.error = error
    state.data = null
  } finally {
    state.loading = false
  }
}
```

更明确的状态可以用字符串表达：

```js
const state = {
  status: 'idle',
  data: null,
  error: null
}

async function loadProfile() {
  state.status = 'loading'

  try {
    state.data = await fetchProfile()
    state.status = 'success'
  } catch (error) {
    state.error = error
    state.status = 'error'
  }
}
```

页面逻辑会更清楚：

```text
idle    -> 还没开始
loading -> 加载中
success -> 加载成功
error   -> 加载失败
```

## 十一、常见误区

### 1. 忘记 await

```js
async function loadPosts() {
  const posts = fetchPosts()
  console.log(posts) // Promise
}
```

如果你要的是结果，需要：

```js
const posts = await fetchPosts()
```

如果你要的是并发任务，先不 `await` 是可以的，但要清楚自己正在保存 Promise。

### 2. 在 forEach 中 await

不推荐：

```js
items.forEach(async item => {
  await saveItem(item)
})
```

`forEach` 不会等待内部 async 回调完成。

按顺序执行：

```js
for (const item of items) {
  await saveItem(item)
}
```

并发执行：

```js
await Promise.all(items.map(item => saveItem(item)))
```

### 3. catch 后继续使用错误数据

```js
const posts = await fetchPosts().catch(() => null)

console.log(posts.length)
```

如果失败，`posts` 是 `null`，后面会继续报错。兜底值要和后续代码的预期一致。

```js
const posts = await fetchPosts().catch(() => [])

console.log(posts.length)
```

## 十二、练习

实现一个保存文章的流程：

- 先保存文章基础信息。
- 再并发上传封面和附件。
- 任意一步失败时返回错误状态。
- 无论成功失败，都关闭 loading。

参考方向：

```js
async function submitPost(input) {
  const state = {
    loading: true,
    data: null,
    error: null
  }

  try {
    const post = await savePost(input)

    const [cover, attachments] = await Promise.all([
      uploadCover(input.cover),
      uploadAttachments(input.attachments)
    ])

    state.data = {
      ...post,
      cover,
      attachments
    }
  } catch (error) {
    state.error = error
  } finally {
    state.loading = false
  }

  return state
}
```

`async/await` 的意义，是让你用更接近业务流程的方式组织异步代码。但它不会替你判断依赖关系、并发边界、错误范围和页面状态。这些才是真正需要认真对待的部分。
