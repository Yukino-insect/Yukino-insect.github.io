+++
date = '2026-08-20T18:20:00+08:00'
draft = false
title = 'JavaScript 网络编程与 fetch：从发请求到处理响应'
+++

前端代码离不开网络请求。登录、列表、详情、搜索、上传、下载，本质上都是浏览器通过 HTTP 和后端交换数据。

这一篇不只讲 `fetch` 怎么写，而是把一次请求拆开：URL、方法、请求头、请求体、响应、错误、超时、取消、跨域。否则你只会复制一段 `fetch('/api')`，遇到 401、CORS、JSON 解析失败时就只能盯着控制台沉默。沉默当然优雅，但解决不了问题。

## 一、浏览器里的网络能力

JavaScript 本身没有“联网”这个语法。浏览器提供了 Web API，前端代码通过这些 API 发起请求。

常见网络相关能力：

| 能力 | 常见 API |
| ---- | -------- |
| HTTP 请求 | `fetch`、`XMLHttpRequest` |
| URL 处理 | `URL`、`URLSearchParams` |
| 表单上传 | `FormData` |
| 文件数据 | `Blob`、`File` |
| 请求取消 | `AbortController` |
| 实时通信 | `WebSocket`、`EventSource` |

现代项目里普通 HTTP 请求优先使用 `fetch`。老项目可能还能看到 `XMLHttpRequest`，它不是不能用，只是写法更繁琐。

## 二、一次 HTTP 请求由什么组成

前端发请求时，最重要的是这几部分：

```text
请求方法 method
请求地址 url
请求头 headers
请求体 body
响应状态 status
响应头 response headers
响应体 response body
```

一个获取文章列表的请求可以这样写：

```js
async function loadPosts() {
  const response = await fetch('/api/posts')
  const data = await response.json()
  return data
}
```

这段代码省略了很多默认行为：

- 默认请求方法是 `GET`。
- 默认不携带请求体。
- 默认跟随重定向。
- 默认不会因为 HTTP 404 或 500 自动进入 `catch`。

最后一点尤其重要。`fetch` 只有在网络层失败时才会 reject，例如断网、DNS 失败、请求被取消。后端返回 500，仍然是一次成功收到的 HTTP 响应。

## 三、GET 请求与查询参数

查询参数不要手动字符串拼接，优先使用 `URLSearchParams`。

```js
function buildPostSearchUrl(params) {
  const search = new URLSearchParams()

  if (params.keyword) {
    search.set('keyword', params.keyword)
  }

  if (params.page) {
    search.set('page', String(params.page))
  }

  if (params.pageSize) {
    search.set('pageSize', String(params.pageSize))
  }

  return `/api/posts?${search.toString()}`
}
```

使用：

```js
async function searchPosts(params) {
  const response = await fetch(buildPostSearchUrl(params))
  return response.json()
}
```

这样可以避免空格、中文、特殊符号导致的编码问题。你当然也可以手动拼接，然后在某天被一个 `&` 字符教育，代价并不高，只是没必要。

## 四、POST 请求与 JSON 请求体

提交 JSON 数据时，需要设置请求方法、请求头和请求体。

```js
async function createPost(input) {
  const response = await fetch('/api/posts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  })

  return response.json()
}
```

`body` 不能直接传普通对象，因为 HTTP 传输的是字节数据。`JSON.stringify` 的作用是把对象序列化为 JSON 字符串。

请求体示例：

```json
{
  "title": "第一篇文章",
  "content": "正文内容"
}
```

后端通常会根据 `Content-Type: application/json` 判断如何解析请求体。如果少了这个请求头，某些后端框架可能拿不到参数。

## 五、处理 HTTP 错误

`fetch` 不会因为 404 或 500 自动抛错，所以需要自己检查 `response.ok`。

```js
async function requestJson(url, options) {
  const response = await fetch(url, options)

  let body = null
  const contentType = response.headers.get('Content-Type') ?? ''

  if (contentType.includes('application/json')) {
    body = await response.json()
  } else {
    body = await response.text()
  }

  if (!response.ok) {
    const message =
      typeof body === 'object' && body !== null
        ? body.message ?? '请求失败'
        : String(body || '请求失败')

    throw new Error(message)
  }

  return body
}
```

`response.ok` 表示状态码在 200 到 299 之间。

常见状态码：

| 状态码 | 含义 |
| ------ | ---- |
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 成功但没有响应体 |
| 400 | 请求参数错误 |
| 401 | 未登录或登录过期 |
| 403 | 没有权限 |
| 404 | 资源不存在 |
| 500 | 服务端错误 |

注意 `204 No Content` 通常没有响应体，直接 `response.json()` 可能报错。

## 六、技术错误与业务错误

前端请求失败通常有两层：

- **技术错误**：断网、超时、请求取消、响应不是合法 JSON。
- **业务错误**：未登录、无权限、参数错误、余额不足。

技术错误一般来自 `catch`：

```js
try {
  const posts = await requestJson('/api/posts')
  console.log(posts)
} catch (error) {
  console.error('加载失败', error)
}
```

业务错误可能来自 HTTP 状态码，也可能来自响应字段。

有些后端即使业务失败也返回 200：

```json
{
  "code": 401,
  "message": "登录已过期",
  "data": null
}
```

这时请求封装就要同时判断 HTTP 状态码和业务 `code`。

```js
async function requestApi(url, options) {
  const result = await requestJson(url, options)

  if (result.code !== 0) {
    throw new Error(result.message ?? '业务处理失败')
  }

  return result.data
}
```

接口规范不同，封装方式也不同。重点不是记住某一种格式，而是把“HTTP 成败”和“业务成败”分清楚。

## 七、请求超时与取消

`fetch` 本身没有 `timeout` 参数，但可以用 `AbortController` 取消请求。

```js
async function requestWithTimeout(url, options = {}, timeout = 10000) {
  const controller = new AbortController()

  const timer = setTimeout(() => {
    controller.abort()
  }, timeout)

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal
    })
  } finally {
    clearTimeout(timer)
  }
}
```

使用：

```js
try {
  const response = await requestWithTimeout('/api/posts', {}, 5000)
  const posts = await response.json()
  console.log(posts)
} catch (error) {
  if (error.name === 'AbortError') {
    console.error('请求超时或被取消')
  } else {
    console.error('请求失败', error)
  }
}
```

取消请求常见于：

- 用户离开页面。
- 用户连续输入搜索关键字，只保留最后一次请求。
- 上传或下载时点击取消。
- 请求耗时过长，页面需要恢复可操作状态。

## 八、避免旧请求覆盖新结果

搜索框联想是典型场景。用户输入很快，旧请求可能比新请求更晚返回。

```js
let currentController = null

async function searchKeyword(keyword) {
  if (currentController) {
    currentController.abort()
  }

  currentController = new AbortController()

  try {
    const response = await fetch(`/api/search?keyword=${encodeURIComponent(keyword)}`, {
      signal: currentController.signal
    })

    return await response.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      return []
    }
    throw error
  }
}
```

也可以用请求序号保证只接受最后一次结果：

```js
let requestId = 0

async function loadLatestPosts() {
  const id = ++requestId
  const posts = await requestApi('/api/posts')

  if (id !== requestId) {
    return
  }

  renderPosts(posts)
}
```

这类问题不是后端慢，而是异步天然会乱序。既然世界不按你的心情排序，代码就要自己建立秩序。

## 九、携带 Cookie 与认证信息

如果登录态依赖 Cookie，并且请求同源，浏览器通常会自动携带 Cookie。

跨域请求想携带 Cookie，需要设置 `credentials`：

```js
fetch('https://api.example.com/user/profile', {
  credentials: 'include'
})
```

常见取值：

| 值 | 含义 |
| ---- | ---- |
| `same-origin` | 默认值，同源请求携带凭证 |
| `include` | 跨域也携带凭证 |
| `omit` | 不携带凭证 |

如果使用 Token，通常放在 `Authorization` 请求头：

```js
fetch('/api/profile', {
  headers: {
    Authorization: `Bearer ${token}`
  }
})
```

Token 放哪里、如何刷新、过期后怎么跳登录页，属于认证体系设计。前端请求封装至少要把 401 统一处理掉，不要散落在每个页面里。

## 十、跨域与 CORS

浏览器有同源策略。协议、域名、端口都相同，才算同源。

```text
https://example.com:443
协议 https
域名 example.com
端口 443
```

前端访问不同源接口时，浏览器会检查服务端是否允许跨域。CORS 不是前端单方面能解决的问题，它需要服务端返回正确响应头。

常见响应头：

```http
Access-Control-Allow-Origin: https://www.example.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
```

开发环境常用代理解决跨域：

```text
浏览器 -> Vite 开发服务器 /api -> 后端服务
```

这样浏览器看到的是同源请求，开发服务器再转发到后端。

## 十一、上传文件

上传文件通常使用 `FormData`。

```js
async function uploadAvatar(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/avatar', {
    method: 'POST',
    body: formData
  })

  return response.json()
}
```

使用 `FormData` 时不要手动设置 `Content-Type`。浏览器会自动生成包含边界信息的 `multipart/form-data`，手动设置反而可能出错。

## 十二、下载文件

下载二进制内容时可以使用 `blob()`。

```js
async function downloadReport() {
  const response = await fetch('/api/report')

  if (!response.ok) {
    throw new Error('下载失败')
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = 'report.xlsx'
  link.click()

  URL.revokeObjectURL(url)
}
```

`blob()` 表示把响应体当作二进制数据处理，适合图片、Excel、PDF 等文件。

## 十三、一个简单请求封装

项目里通常不会在每个页面直接写完整的 `fetch`。可以先封装一个小工具：

```js
async function http(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  })

  if (response.status === 204) {
    return null
  }

  const result = await response.json()

  if (!response.ok) {
    throw new Error(result.message ?? '请求失败')
  }

  return result
}

export function get(url) {
  return http(url)
}

export function post(url, data) {
  return http(url, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}
```

这只是教学版封装。真实项目还会加上：

- baseURL。
- Token 注入。
- 401 跳转登录。
- 统一错误提示。
- 请求超时。
- 重试策略。
- 日志埋点。

## 十四、练习

实现一个 `loadPostDetail(id)`：

- 使用 `GET /api/posts/{id}`。
- 处理 404，提示文章不存在。
- 处理 401，提示需要重新登录。
- 网络失败时返回兜底结构。

参考方向：

```js
async function loadPostDetail(id) {
  try {
    const response = await fetch(`/api/posts/${id}`)

    if (response.status === 404) {
      throw new Error('文章不存在')
    }

    if (response.status === 401) {
      throw new Error('登录已过期')
    }

    if (!response.ok) {
      throw new Error('加载文章失败')
    }

    return {
      data: await response.json(),
      error: null
    }
  } catch (error) {
    return {
      data: null,
      error
    }
  }
}
```

网络编程的重点不是“把请求发出去”，而是把不稳定的远端世界整理成页面可以承受的状态。能做到这一点，前端代码才算真正进入工程层面。
