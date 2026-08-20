+++
date = '2026-08-19T16:06:00+08:00'
draft = false
title = '接口请求与 Pinia 状态管理：把前端数据流管起来'
+++

真实前端项目的难点通常不是“怎么发请求”，而是请求之后的数据要放在哪里、如何复用、如何更新、失败时如何恢复、多个页面如何保持一致。

一个可维护的 Vue/uni-app 工程通常会做这样的分层：`api/http.ts` 负责基础请求，`api/*.api.ts` 负责业务接口，`stores/*.ts` 负责跨页面状态，页面组件负责用户交互和展示。

## 一、前端数据流

推荐数据流如下：

```text
用户操作
 -> 页面事件函数
   -> Pinia action 或业务 API
     -> HTTP 请求封装
       -> 后端接口
     <- 响应数据
   <- 更新 store 或局部状态
 -> 模板自动渲染
```

这条链路的核心是：页面不要同时承担所有职责。

页面应该关心：

- 用户点了什么。
- 当前展示什么状态。
- 什么时候刷新。
- 什么时候跳转。

API 层应该关心：

- 请求哪个接口。
- 参数如何组织。
- 返回值类型是什么。

HTTP 层应该关心：

- base URL。
- token。
- 响应拆包。
- 统一错误。
- 401。
- 文件 URL 归一化。

Store 应该关心：

- 跨页面共享状态。
- 缓存。
- 乐观更新。
- 分页。
- 状态同步。

## 二、基础请求封装

项目的 `src/api/http.ts` 定义：

```ts
export const BASE_URL: string = import.meta.env.VITE_API_BASE || ''
```

用于读取接口基础路径。

URL 拼接：

```ts
export function resolveApiUrl(path: string): string {
  if (!BASE_URL) {
    return path
  }

  const normalizedBase = BASE_URL.replace(/\/+$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return normalizedBase + normalizedPath
}
```

这段代码处理了 base URL 尾部斜杠和接口路径开头斜杠，避免拼出：

```text
http://localhost:8080//api/posts
```

这种小处理很普通，但很必要。工程质量经常就藏在这些不显眼的地方。

## 三、统一响应格式

项目约定后端响应：

```ts
interface ApiResponse<T> {
  code: number
  data: T
  msg: string
}
```

成功条件：

```ts
body.code === 0
```

请求函数返回：

```ts
resolve(normalizeBackendFileUrls(body.data))
```

也就是说，页面和业务 API 拿到的是 `data`，不用每次都写：

```ts
if (res.code === 0) {
  return res.data
}
```

这就是统一封装的意义。

## 四、错误模型 ApiError

项目定义：

```ts
export class ApiError extends Error {
  code: number
  constructor(code: number, msg: string) {
    super(msg || `HTTP code ${code}`)
    this.code = code
  }
}
```

页面捕获时：

```ts
ui.showToast(e instanceof ApiError ? e.message : '加载失败')
```

这比抛字符串更好，因为错误对象带有 code，可以区分：

- HTTP 状态错误。
- 后端业务错误。
- 网络异常。
- 登录失效。

如果后续要处理权限不足、内容不存在、参数错误，也可以基于 `ApiError.code` 扩展。

## 五、token 注入与 401 处理

请求时注入 token：

```ts
const header: Record<string, string> = { 'Content-Type': 'application/json' }
if (!noAuth) {
  const t = getToken()
  if (t) header.Authorization = 'Bearer ' + t
}
```

401 时：

```ts
if (status === 401) {
  handleUnauthorized()
  reject(new ApiError(401, body?.msg || '登录已失效，请重新登录'))
  return
}
```

`handleUnauthorized` 会清 token 并通知全局处理器：

```ts
export function handleUnauthorized(): void {
  clearToken()
  notifyUnauthorized()
}
```

全局处理器在 `App.vue` 注册：

```ts
setUnauthorizedHandler(() => {
  auth.logout()
  ui.openLogin('default')
  uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
})
```

这个设计很好：HTTP 层知道发生了 401，但不直接依赖 UI store；根组件把“401 后如何展示”注入进去。职责边界比较干净。

## 六、本地存储

项目封装 token：

```ts
export function getToken(): string {
  try {
    return uni.getStorageSync(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}
```

写入：

```ts
export function setToken(token: string): void {
  if (token) uni.setStorageSync(TOKEN_KEY, token)
  else uni.removeStorageSync(TOKEN_KEY)
}
```

清除：

```ts
export function clearToken(): void {
  try {
    uni.removeStorageSync(TOKEN_KEY)
  } catch {
    // ignore
  }
}
```

跨端项目优先使用 `uni.getStorageSync`，不要直接使用浏览器 `localStorage`。否则 H5 能跑，小程序可能就不认账。

## 七、文件 URL 归一化

项目中有：

```ts
resolveBackendFileUrl()
normalizeBackendFileUrls()
```

它们的作用是把后端返回的文件路径统一转换成可访问 URL。

为什么需要这层？

后端可能返回：

```text
/files/a.png
/api/files/a.png
http://server/files/a.png
mock://xxx
data:image/png;base64,...
```

如果每个组件自己处理这些情况，图片逻辑会散得到处都是。统一归一化后，组件只负责渲染。

这就是 API 层对页面的保护：页面少知道一点，项目就少乱一点。

## 八、业务 API 模块

业务接口应该按领域拆分：

```text
post.api.ts
user.api.ts
topic.api.ts
upload.api.ts
message.api.ts
service.api.ts
```

一个典型 API 函数可以写成：

```ts
export function fetchPostDetail(id: string): Promise<Post> {
  return request<Post>(`/api/posts/${id}`)
}
```

带参数时：

```ts
export function fetchHomePosts(options: FetchHomePostsOptions): Promise<PostPage> {
  const qs = buildQS(options)
  return request<PostPage>(`/api/posts/home${qs}`)
}
```

项目中 `buildQS` 会跳过空值：

```ts
if (v === undefined || v === null || v === '') continue
```

这能避免拼出没有意义的查询参数。

## 九、Pinia 基础

Pinia 是 Vue 官方推荐的状态管理库。

项目中：

```ts
import { defineStore } from 'pinia'
```

定义 store：

```ts
export const useFeedStore = defineStore('feed', {
  state: (): FeedState => ({
    posts: [],
    loaded: false,
    pageSize: 10,
    hasMore: true,
  }),
  getters: {},
  actions: {},
})
```

使用 store：

```ts
const feed = useFeedStore()
await feed.reload()
```

在模板中保持响应式，项目使用：

```ts
const { posts, hasMore, loadingMore } = storeToRefs(feed)
```

`storeToRefs` 会把 store 中的 state 和 getter 转成 ref，避免解构后丢失响应式。

## 十、state、getters、actions

Pinia 三个核心概念：

| 概念 | 作用 |
| ---- | ---- |
| state | 状态数据 |
| getters | 派生数据 |
| actions | 修改状态和执行业务流程 |

`feed` store 中 state：

```ts
interface FeedState {
  posts: Post[]
  loaded: boolean
  pageSize: number
  hasMore: boolean
  loadingMore: boolean
}
```

getters：

```ts
getById: (state) => (id: string): Post | undefined =>
  state.posts.find((p) => p.id === id)
```

actions：

```ts
async reload(opts = {}) {
  const response = await fetchHomePosts(...)
  this.posts = response.items
  this.loaded = true
}
```

actions 可以是异步的，也可以直接修改 state。

## 十一、登录态 store

`auth` store 管理：

- 是否登录。
- 用户资料。
- 是否已恢复登录态。
- 登录。
- 注册。
- 刷新用户资料。
- 登出。

启动恢复逻辑：

```ts
async restore(): Promise<void> {
  if (this.restored) return
  this.restored = true
  const token = getToken()
  if (!token) return
  const cached = readCachedProfile()
  if (cached) {
    this.profile = cached
    this.isLoggedIn = true
  }
  // 再请求 /me 校验
}
```

这里有一个体验上的细节：如果本地有缓存资料，先渲染缓存，再异步校验并刷新最新资料。这样应用启动时不会空白等待。

非 401 错误时保留缓存登录态：

```ts
if (!(e instanceof ApiError) || e.code !== 401) {
  if (cached) return
}
```

这避免了网络抖动导致用户被误登出。真实产品里，这种判断比“失败就清空”更合理。

## 十二、信息流 store

`feed` store 管理首页帖子流：

- `reload`：刷新列表。
- `loadMore`：加载更多。
- `upsert`：插入或更新帖子。
- `patchPost`：局部更新帖子。
- `removePost`：删除帖子。
- `toggleFlag`：点赞、收藏、蹲帖。

分页状态包括：

```ts
hasMore
sessionFinished
recommendationExhausted
loadingMore
cursor
nextPostId
sessionId
```

这说明推荐流不是简单 page/pageSize，而是有会话、游标、下一条 ID、已使用 ID 等复杂状态。前端必须配合后端推荐策略管理状态。

## 十三、乐观更新

点赞逻辑：

```ts
const prev = !!post[flag]
const prevLikes = post.likes
const optimistic = !prev
post[flag] = optimistic
if (flag === 'liked') post.likes += optimistic ? 1 : -1
```

这叫乐观更新：用户点击后先更新 UI，再请求后端。

成功后用后端结果修正：

```ts
const res = await setPostLike(postId, optimistic)
this.patchPost(postId, {
  liked: res.liked,
  likes: nextLikes,
})
```

失败后回滚：

```ts
catch {
  post[flag] = prev
  post.likes = prevLikes
}
```

乐观更新适合点赞、收藏这类高频轻操作。它能让交互更顺滑，但必须准备失败回滚，否则 UI 会欺骗用户。欺骗用户这种事，通常不会有好下场。

## 十四、局部状态与全局状态

不是所有状态都应该放 Pinia。

适合放局部状态：

- 当前输入框内容。
- 当前页面 loading。
- 当前 tab。
- 临时弹窗内部字段。

适合放 Pinia：

- 登录态。
- 用户资料。
- 多页面共享的信息流。
- 消息未读数。
- 全局弹窗状态。
- 需要跨页面触发刷新的 token。

首页中：

```ts
const active = ref<PostListSort>('rec')
const hotToday = ref<HotItem[]>([])
const topics = ref<string[]>([])
```

这些更偏页面局部，所以放在页面内部。

而帖子列表 `posts` 来自 feed store，因为详情页、收藏页等也可能需要同步。

## 十五、类型建模

Store state 应该有明确类型：

```ts
interface AuthState {
  isLoggedIn: boolean
  profile: MeProfile | null
  restored: boolean
}
```

API 返回值也应该有明确类型：

```ts
request<T>(path: string): Promise<T>
```

页面 props：

```ts
const props = defineProps<{ post: Post }>()
```

这样前端形成完整类型链：

```text
后端接口返回
 -> API 返回类型
 -> Store state 类型
 -> 组件 props 类型
 -> 模板字段访问
```

类型链越完整，接口变化越容易被发现。

## 十六、接口契约的落地方式

前后端协作时，接口契约最好不要只停留在口头说明。至少应该把这些内容落到代码或文档里：

- 请求方法和路径。
- query、path、body 参数。
- 成功响应结构。
- 错误码和错误消息。
- 分页字段。
- 空值规则。
- 枚举值范围。
- 文件路径和访问 URL 的格式。

在前端代码中，可以用 TypeScript 类型把契约固化下来：

```ts
interface PageResult<T> {
  items: T[]
  hasMore: boolean
  nextCursor?: string | null
}
```

如果后端返回字段变了，类型越明确，问题越容易在开发阶段暴露。不要等用户点开页面才发现 `undefined is not an object`，那样错误虽然诚实，但并不体面。

## 十七、小结

接口请求和状态管理是前端工程的骨架：

- HTTP 基础封装处理通用问题。
- 业务 API 模块表达具体接口。
- TypeScript 泛型连接接口返回类型。
- Pinia 管理跨页面共享状态。
- 页面局部状态不必过度上升。
- 乐观更新要配合失败回滚。
- 401 处理要全局统一。
- 文件 URL、token、响应拆包都应集中处理。

读这个项目时，可以从 `pages/index/index.vue` 的 `refreshHome` 开始，顺着 `feed.reload`、`fetchHomePosts`、`request<T>` 往下看。看完这条链路，你就能理解一个真实前端页面如何从用户操作走到后端接口，再回到 UI 状态。
