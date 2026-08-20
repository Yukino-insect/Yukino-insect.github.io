+++
date = '2026-08-19T18:16:00+08:00'
draft = false
title = '接口请求、Pinia 与前端数据流：把服务端数据管起来'
+++

真实前端应用离不开接口。页面展示的数据、用户登录状态、分页列表、权限信息、提交结果都来自服务端。接口请求和状态管理如果没有统一设计，很快就会散成一地。

## 一、前端数据流

典型流程：

```text
页面触发加载
 -> API 模块发请求
 -> 请求封装处理响应和错误
 -> 页面或 store 保存状态
 -> 组件根据状态渲染
```

不要让组件直接到处写底层请求逻辑。接口路径、token、错误处理、响应解析应该统一管理。

## 二、统一响应类型

常见响应结构：

```ts
type ApiResponse<T> = {
  code: number
  message: string
  data: T
}
```

分页结构：

```ts
type PageResult<T> = {
  records: T[]
  total: number
  page: number
  pageSize: number
}
```

文章卡片：

```ts
type PostCard = {
  id: number
  title: string
  summary: string
  liked: boolean
}
```

组合：

```ts
type PostPageResponse = ApiResponse<PageResult<PostCard>>
```

## 三、请求封装

以 `fetch` 为例：

```ts
type RequestOptions = RequestInit & {
  auth?: boolean
}

export async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)

  if (options.auth !== false) {
    const token = localStorage.getItem('token')
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const response = await fetch(url, {
    ...options,
    headers
  })

  const body = await response.json() as ApiResponse<T>

  if (!response.ok || body.code !== 0) {
    throw new Error(body.message || '请求失败')
  }

  return body.data
}
```

这只是简化示例。真实项目还可能处理超时、刷新 token、文件上传、重复请求取消、全局错误提示。

## 四、API 模块

按业务拆 API。

```ts
export function fetchPostPage(params: {
  page: number
  pageSize: number
  keyword?: string
}) {
  const search = new URLSearchParams()
  search.set('page', String(params.page))
  search.set('pageSize', String(params.pageSize))

  if (params.keyword) {
    search.set('keyword', params.keyword)
  }

  return request<PageResult<PostCard>>(`/api/posts?${search}`)
}
```

页面不应该关心 URL 拼接细节。页面要表达的是“我要加载文章分页”。

## 五、页面局部状态

只在当前页面使用的数据，放页面内即可。

```ts
const posts = ref<PostCard[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function loadPosts() {
  loading.value = true
  errorMessage.value = ''

  try {
    const page = await fetchPostPage({
      page: 1,
      pageSize: 20
    })
    posts.value = page.records
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}
```

不要所有东西都放 Pinia。全局状态不是垃圾桶。

## 六、什么时候用 Pinia

适合放 Pinia 的状态：

- 登录用户。
- token。
- 全局权限。
- 跨页面共享的设置。
- 需要缓存的业务列表。
- 多个页面都会修改的状态。

不适合放 Pinia 的状态：

- 某个输入框临时内容。
- 某个弹窗是否打开。
- 当前页面的局部 loading。
- 只在一个组件内部使用的展开状态。

## 七、定义 Store

```ts
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const profile = ref<UserProfile | null>(null)

  const loggedIn = computed(() => Boolean(token.value))

  async function login(form: LoginForm) {
    const result = await loginApi(form)
    token.value = result.token
    localStorage.setItem('token', result.token)
    profile.value = result.profile
  }

  function logout() {
    token.value = null
    profile.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    profile,
    loggedIn,
    login,
    logout
  }
})
```

Store 中可以有 state、getter、action。组合式写法下，`ref` 是 state，`computed` 是 getter，函数是 action。

## 八、乐观更新

点赞这类交互可以先更新 UI，再请求接口。

```ts
async function toggleLike(post: PostCard) {
  const previous = post.liked
  post.liked = !post.liked

  try {
    await updateLike(post.id, post.liked)
  } catch (error) {
    post.liked = previous
    throw error
  }
}
```

乐观更新必须能回滚。没有回滚的乐观，是冲动。

## 九、状态渲染

页面至少考虑四种状态：

```text
loading
error
empty
success
```

模板：

```vue
<LoadingView v-if="loading" />
<ErrorView v-else-if="errorMessage" :message="errorMessage" @retry="loadPosts" />
<EmptyView v-else-if="posts.length === 0" />
<PostList v-else :posts="posts" />
```

这比只写成功状态成熟得多。真实世界不会永远按成功路径运行。

## 十、练习

实现一个文章 store：

- `posts`。
- `loading`。
- `errorMessage`。
- `loadPosts`。
- `refresh`。
- `toggleLike`。

要求接口失败时保留旧数据，并展示错误信息。做到这一点，说明你开始理解前端数据流，而不只是会调用接口。
