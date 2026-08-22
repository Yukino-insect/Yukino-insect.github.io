+++
date = '2026-08-19T18:16:00+08:00'
draft = false
title = '接口请求、Pinia 与前端数据流：把服务端数据管起来'
+++

真实前端应用离不开接口。页面展示的数据、用户登录状态、分页列表、权限信息、提交结果都来自服务端。接口请求和状态管理如果没有统一设计，很快就会散成一地。

这篇文章讨论三件事：

- 接口请求应该怎样从组件里抽离出来。
- 什么状态适合放在 Pinia，什么状态应该留在页面。
- Pinia store 的状态到底存在浏览器哪里，和 `localStorage` 有什么关系。
- Store 怎样处理加载、失败、缓存、乐观更新和并发请求。

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

前端数据大致可以分成三类：

| 类型 | 例子 | 常见位置 |
| ---- | ---- | -------- |
| 服务端数据 | 文章列表、用户信息、权限菜单 | API 模块、Pinia、页面状态 |
| 客户端 UI 状态 | 弹窗开关、当前 tab、输入框内容 | 当前组件或组合函数 |
| 派生状态 | 是否登录、是否为空、是否还有更多 | `computed` |

这三类不要混在一起。服务端数据需要考虑请求、缓存、失败和刷新；UI 状态通常只服务当前页面；派生状态最好用 `computed` 算出来，而不是手动维护一个容易不同步的变量。

例如：

```ts
const posts = ref<PostCard[]>([])
const loading = ref(false)

const empty = computed(() => {
  return !loading.value && posts.value.length === 0
})
```

`empty` 不应该再额外写成一个 `ref(false)`，否则你就要保证每次修改 `posts` 和 `loading` 时都同步更新它。代码不会主动帮你记得这件事，它只会在你忘记时表现得很诚实。

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

API 模块还有一个重要职责：**把接口语义稳定下来。**

页面不应该知道后端接口叫 `/api/v1/post/page`，也不应该知道查询参数里到底是 `pageSize`、`size` 还是 `limit`。这些变化应该被 API 函数隔离：

```ts
export function fetchPostPage(params: {
  page: number
  pageSize: number
  keyword?: string
}) {
  return request<PageResult<PostCard>>('/api/v1/post/page', {
    method: 'POST',
    body: JSON.stringify({
      pageNo: params.page,
      size: params.pageSize,
      keyword: params.keyword
    })
  })
}
```

即使后端参数名改变，页面和 store 仍然调用 `fetchPostPage({ page, pageSize, keyword })`。这种隔离看起来普通，但普通的东西如果做对了，项目会安静很多。

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

判断状态该不该放 Pinia，可以看三个问题：

1. 离开当前页面后，这份状态是否还需要保留？
2. 是否有多个页面或多个远距离组件会读写它？
3. 它是否代表用户身份、权限、全局配置、跨页面缓存这类应用级信息？

如果三个问题都是否定，先放在页面里。页面局部状态并不低级，它只是边界正确。

例如搜索框关键字通常留在页面：

```ts
const keyword = ref('')
```

登录用户信息适合放 Pinia：

```ts
const authStore = useAuthStore()
```

文章列表要看场景。如果只有一个页面使用，放页面即可；如果列表需要跨路由缓存，或者详情页、收藏页、首页都会更新同一批文章数据，就可以考虑放 store。

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

Pinia 的价值不是“让状态看起来高级”，而是让跨组件、跨页面的数据有统一入口。一个 store 最好围绕一个业务领域组织，例如 `auth`、`post`、`cart`、`permission`。不要建一个巨大的 `commonStore`，然后把所有状态都塞进去。那只是把混乱换了一个文件名。

常见 store 边界：

```text
authStore：token、用户信息、登录、退出
permissionStore：菜单、按钮权限、角色信息
postStore：文章缓存、文章加载、点赞、刷新
settingsStore：主题、语言、布局偏好
```

一个好 store 通常具备这些特征：

- 状态命名能看出业务含义。
- action 表达业务动作，而不是底层请求细节。
- getter 只派生状态，不偷偷修改状态。
- 失败时知道是否保留旧数据。
- 页面不需要知道请求 URL 和响应结构细节。

## 七、Pinia Store 到底存在哪里

很多初学者会把 Pinia 和 `localStorage` 混在一起理解，好像“用了 Pinia，数据就会自动存到浏览器里”。这当然不对。准确地说：

```text
Pinia store 默认存在 JavaScript 运行时内存里
localStorage 存在浏览器提供的本地持久化存储里
后端数据存在服务端数据库、缓存或文件系统里
```

这三者不是同一层东西。

### 1. Store 默认是内存状态

当 Vue 应用启动时，代码会执行：

```ts
const pinia = createPinia()

createApp(App)
  .use(pinia)
  .mount('#app')
```

`createPinia()` 会创建一个 Pinia 实例。之后你在组件里调用：

```ts
const authStore = useAuthStore()
```

Pinia 会根据 `defineStore('auth', ...)` 创建或复用一个 `auth` store。这个 store 可以理解成挂在当前 Vue 应用上的响应式对象。多个组件调用 `useAuthStore()`，拿到的是同一个应用里的同一份 `auth` 状态。

概念上可以把它想成这样：

```ts
const piniaState = {
  auth: {
    token: 'xxx',
    profile: {
      id: 1,
      nickname: 'Yukino'
    }
  },
  post: {
    posts: [],
    loaded: false
  }
}
```

这不是让你真的这样写代码，而是帮助你理解：store 是按 `id` 分组的应用状态树。`auth`、`post`、`settings` 这些名字不是装饰，它们决定了状态归属。名字随便起，后面自然也会随便乱。

但这份状态默认只存在于当前页面的 JavaScript 内存中。只要用户刷新页面、关闭标签页、重新打开网站，内存就会重新初始化。

```text
进入页面 -> 创建 Vue 应用 -> 创建 Pinia -> 初始化 store
刷新页面 -> 旧 JS 内存销毁 -> 重新创建 Vue 应用 -> 重新初始化 store
```

所以，Pinia 本身不负责“刷新后还在”。如果刷新后 token 还在，那通常是因为你手动把 token 写进了 `localStorage`、`sessionStorage`、Cookie，或者重新向后端请求了用户信息。功劳不要算错对象，虽然代码不会介意，但维护代码的人会。

### 2. Pinia 底层依赖 Vue 响应式

Pinia 不是另起一套神秘存储系统。它建立在 Vue 的响应式能力上。

组合式写法中：

```ts
export const useCounterStore = defineStore('counter', () => {
  const count = ref(0)
  const doubleCount = computed(() => count.value * 2)

  function increment() {
    count.value++
  }

  return {
    count,
    doubleCount,
    increment
  }
})
```

可以这样理解：

| 写法 | 在 store 中的角色 | 类比 |
| ---- | ---------------- | ---- |
| `ref()` / `reactive()` | state | 组件里的响应式数据 |
| `computed()` | getter | 根据 state 算出来的值 |
| `function` | action | 修改状态或发请求的业务动作 |

组件读取 `count`，模板就会追踪它；action 修改 `count`，依赖它的组件会重新渲染。这就是 Pinia 看起来“全局自动更新”的原因：它不是把数据存到了什么特殊地方，而是把共享状态做成了 Vue 能追踪的响应式状态。

### 3. Store 和组件状态的区别

组件里的 `ref`：

```ts
const keyword = ref('')
```

通常只属于当前组件实例。组件卸载后，这份状态就没了。

Pinia store 里的 `ref`：

```ts
export const useSearchStore = defineStore('search', () => {
  const keyword = ref('')

  return { keyword }
})
```

属于当前 Vue 应用的 store 实例。只要应用还在，路由切换、组件卸载、另一个组件重新挂载，都可以继续读到同一份状态。

差异可以简化成：

| 状态位置 | 生命周期 | 共享范围 |
| -------- | -------- | -------- |
| 组件 `ref` | 组件创建到组件卸载 | 当前组件及其子组件 |
| 组合函数内部 `ref` | 调用组合函数的组件生命周期 | 通常是当前调用方 |
| Pinia store | 当前 Vue 应用运行期间 | 整个应用 |
| `localStorage` | 浏览器保存到被清理为止 | 同源页面 |
| 后端数据库 | 服务端决定 | 多设备、多用户、多会话 |

这张表很重要。状态管理最常见的错误，就是把生命周期不同的东西硬塞进同一个位置。页面临时输入值放进 store，会污染全局；登录 token 只放组件内，一刷新就丢。两者都不是什么高深错误，只是边界没想清楚。

### 4. localStorage 是什么

`localStorage` 是浏览器提供的 Web Storage API。它是一个按站点来源隔离的键值存储。

所谓“同源”，大致由协议、域名、端口共同决定：

```text
https://example.com
http://example.com
https://example.com:8080
```

这三个来源并不完全相同。浏览器会按来源隔离 `localStorage`，一个来源下写入的数据，另一个来源通常读不到。

最基本的用法：

```ts
localStorage.setItem('token', 'abc')

const token = localStorage.getItem('token')

localStorage.removeItem('token')
```

它有几个关键特点：

- 只能直接存字符串。
- 数据刷新页面后仍然存在。
- 数据不会像 Cookie 那样自动随请求发送给服务器。
- API 是同步的，读写很方便，但大量读写会阻塞主线程。
- 存储容量有限，通常适合小数据，不适合大列表、大文件。
- 浏览器环境才有，服务端渲染时不能直接访问 `window.localStorage`。

因为只能存字符串，所以对象要自己序列化：

```ts
const profile = {
  id: 1,
  nickname: 'Yukino'
}

localStorage.setItem('profile', JSON.stringify(profile))

const rawProfile = localStorage.getItem('profile')
const parsedProfile = rawProfile ? JSON.parse(rawProfile) as UserProfile : null
```

这也意味着，`localStorage` 里没有类型保护。你今天存的是 `UserProfile`，明天代码改了字段名，旧数据不会自动迁移。它只会安静地躺在那里，然后在某个用户浏览器里给你一份过期结构。很体贴吗？不，它只是没有判断力。

### 5. localStorage 和 Cookie、sessionStorage 的区别

常见本地存储可以粗略对比如下：

| 存储方式 | 是否刷新后保留 | 是否关闭标签页后保留 | 是否自动随请求发送 | 适合存什么 |
| -------- | -------------- | -------------------- | ------------------ | ---------- |
| 内存状态 | 否 | 否 | 否 | 当前运行期间的页面状态 |
| `localStorage` | 是 | 是 | 否 | 主题、语言、非敏感偏好、部分 token 场景 |
| `sessionStorage` | 是 | 通常否 | 否 | 单个标签页会话数据 |
| Cookie | 是，取决于过期时间 | 是，取决于过期时间 | 是 | 服务端需要识别的会话信息 |
| IndexedDB | 是 | 是 | 否 | 大量结构化本地数据 |

这里不展开 Cookie 的安全细节，但要记住一点：如果 token 放在 `localStorage`，一旦页面存在 XSS 漏洞，攻击脚本就可能读取它。前端存储不是保险柜。能不能存、存多久、怎么失效，要结合后端认证方案一起设计。

### 6. Store 和 localStorage 怎样配合

常见登录状态会这样设计：

```text
应用启动
 -> 从 localStorage 读取 token
 -> 初始化 authStore.token
 -> 请求 /me 获取用户资料
 -> 用户登录后更新 authStore，并写入 localStorage
 -> 用户退出后清空 authStore，并删除 localStorage
```

代码上大致是：

```ts
const TOKEN_KEY = 'blog-token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const profile = ref<UserProfile | null>(null)

  const loggedIn = computed(() => Boolean(token.value))

  async function login(form: LoginForm) {
    const result = await loginApi(form)

    token.value = result.token
    profile.value = result.profile
    localStorage.setItem(TOKEN_KEY, result.token)
  }

  function logout() {
    token.value = null
    profile.value = null
    localStorage.removeItem(TOKEN_KEY)
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

这里有两份状态：

```text
authStore.token：运行时响应式状态，负责驱动页面更新
localStorage token：浏览器持久化副本，负责刷新后恢复
```

页面应该主要读 `authStore.token` 和 `authStore.loggedIn`，而不是每个组件都去 `localStorage.getItem('token')`。如果到处读写 `localStorage`，你就失去了 store 的统一入口。既然已经引入 Pinia，又绕过 Pinia 去拿状态，那就像买了门牌却从窗户进屋，倒也不是不行，只是没必要。

## 八、定义 Store

```ts
export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('token'))
  const profile = ref<UserProfile | null>(null)
  
  // getter
  const loggedIn = computed(() => Boolean(token.value))

  // action
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

`defineStore` 是 Vue 官方状态管理库 **Pinia** 用于定义并创建一个状态存储库（Store）的核心函数。

它的主要作用是将应用中的全局共享状态（state）、计算属性（getter）和修改逻辑（action）封装在一起，供跨组件复用。

`defineStore('auth', ...)` 里的 `'auth'` 是 store id。它应该稳定、唯一、能表达业务领域。这个 id 会参与 DevTools 展示、状态分组、插件处理和持久化逻辑。随手写成 `'store1'` 当然也能跑，只是后面排查问题时，你会为当时的随手付出一点并不浪漫的代价。

实际项目里通常按业务拆文件：

```text
src/
  stores/
    authStore.ts
    postStore.ts
    permissionStore.ts
    settingsStore.ts
```

一个 store 文件最好只管理一个业务领域。`authStore` 管登录和用户身份，`postStore` 管文章列表和文章动作。不要把登录、主题、文章、权限都塞进一个 `appStore`。那不叫集中管理，那只是集中混乱。

### 1. 在项目中注册 Pinia

使用 store 前，需要在入口文件注册 Pinia。

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

createApp(App)
  .use(createPinia())
  .mount('#app')
```

注册后，组件里就可以使用 store：

```ts
const authStore = useAuthStore()
```

### 2. 不要直接解构 store

Pinia store 本身是响应式对象。如果直接解构 state，容易丢失响应式。

不推荐：

```ts
const { token, profile } = useAuthStore()
```

推荐使用 `storeToRefs` 解构状态和 getter，函数可以直接解构：

```ts
import { storeToRefs } from 'pinia'

const authStore = useAuthStore()
const { token, profile, loggedIn } = storeToRefs(authStore)
const { login, logout } = authStore
```

这样 `token`、`profile`、`loggedIn` 仍然保持响应式。这个细节很小，但如果忽略，页面就会出现“明明 store 改了，模板却没更新”的问题。很遗憾，它不会在报错信息里体贴地告诉你原因。

### 3. action 里可以调用 API

store action 适合封装业务动作：

```ts
async function loadProfile() {
  profile.value = await fetchProfile()
}
```

页面只需要表达“加载用户信息”：

```ts
await authStore.loadProfile()
```

而不是在页面里写请求 URL、响应解析、错误处理。页面越像流程编排，store 越像业务状态中心，代码越容易维护。

### 4. getter 不要产生副作用

`computed` 只应该根据现有状态计算结果。

推荐：

```ts
const loggedIn = computed(() => Boolean(token.value))
```

不推荐：

```ts
const loggedIn = computed(() => {
  if (!token.value) {
    localStorage.removeItem('token')
  }

  return Boolean(token.value)
})
```

清理 token 这类动作应该放在 `logout` 或请求错误处理里，而不是藏在 getter 里。getter 一旦有副作用，读取状态就可能改变状态，调试体验会非常不友好。

## 九、Store 请求状态设计

Store 处理请求时，至少要明确四个状态：

```ts
const posts = ref<PostCard[]>([])
const loading = ref(false)
const errorMessage = ref('')
const loaded = ref(false)
```

含义分别是：

- `posts`：当前可展示的数据。
- `loading`：是否正在请求。
- `errorMessage`：本次请求错误。
- `loaded`：是否至少成功加载过一次。

`loaded` 的作用是区分两种情况：

```text
还没请求过，所以页面是初始状态
请求成功过，但这次刷新失败，所以可以保留旧数据
```

示例：

```ts
async function loadPosts() {
  loading.value = true
  errorMessage.value = ''

  try {
    posts.value = await fetchPosts()
    loaded.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}
```

这里失败时没有清空 `posts`。如果用户已经看到旧列表，刷新失败时保留旧数据通常比直接清空页面更友好。是否清空不是固定答案，但必须是你主动做出的设计选择。

### 1. 避免重复请求

简单场景可以用 `loading` 防重复：

```ts
async function loadPosts() {
  if (loading.value) {
    return
  }

  loading.value = true
  try {
    posts.value = await fetchPosts()
  } finally {
    loading.value = false
  }
}
```

这适合“同一时间只允许一个请求”的场景，例如刷新按钮。

### 2. 处理过期响应

搜索、筛选这类场景可能连续发请求。后发出的请求不一定后返回，如果不处理，旧响应可能覆盖新响应。

可以用请求序号处理：

```ts
let requestId = 0

async function searchPosts(keyword: string) {
  const currentRequestId = ++requestId

  loading.value = true
  errorMessage.value = ''

  try {
    const result = await fetchPostPage({
      page: 1,
      pageSize: 20,
      keyword
    })

    if (currentRequestId !== requestId) {
      return
    }

    posts.value = result.records
  } catch (error) {
    if (currentRequestId !== requestId) {
      return
    }

    errorMessage.value = error instanceof Error ? error.message : '搜索失败'
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}
```

这段逻辑的意思是：只有最后一次请求有资格修改状态。搜索框输入很快时，这个判断尤其重要。

### 3. 缓存和刷新

如果 store 用来缓存列表，可以拆出 `load` 和 `refresh`：

```ts
async function loadPosts() {
  if (loaded.value) {
    return
  }

  await refreshPosts()
}

async function refreshPosts() {
  loading.value = true
  errorMessage.value = ''

  try {
    posts.value = await fetchPosts()
    loaded.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新失败'
  } finally {
    loading.value = false
  }
}
```

`loadPosts` 表示没有缓存时加载，`refreshPosts` 表示用户明确要刷新。名字清楚，页面调用时才不会猜。

## 十、乐观更新

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

如果状态在 store 里，乐观更新也应该放在 store action 里，而不是散落到每个组件。

```ts
async function toggleLike(postId: number) {
  const post = posts.value.find((item) => item.id === postId)
  if (!post) {
    return
  }

  const previousLiked = post.liked
  const previousLikes = post.likes

  post.liked = !post.liked
  post.likes += post.liked ? 1 : -1
  errorMessage.value = ''

  try {
    await updateLike(post.id, post.liked)
  } catch (error) {
    post.liked = previousLiked
    post.likes = previousLikes
    errorMessage.value = error instanceof Error ? error.message : '点赞失败'
  }
}
```

这样无论哪个页面触发点赞，失败回滚规则都是同一份。否则首页一种回滚，详情页另一种回滚，最后状态就会开始分裂，像一场没有主持人的辩论。

## 十一、持久化边界

持久化的意思是：页面刷新、关闭后，再次打开还能恢复某些状态。Pinia 默认不做这件事。你需要自己决定把哪些状态同步到 `localStorage`、`sessionStorage`、Cookie、IndexedDB，或者重新从后端拉取。

不是所有 store 状态都应该持久化到 `localStorage`。

适合持久化：

- token，前提是你的认证方案允许这样做。
- 主题。
- 语言。
- 用户主动选择的布局偏好。
- 不敏感、体积小、允许过期的草稿。

不适合持久化：

- `loading`。
- `errorMessage`。
- 临时弹窗状态。
- 只对当前页面有效的筛选面板展开状态。
- 可能过期的敏感用户资料。
- 很大的列表缓存。
- 后端权限、价格、库存这类必须保持新鲜的数据。

判断标准不是“能不能存”，而是“恢复旧值后会不会误导用户”。浏览器存储很听话，你让它存错东西，它也会认真存下去。问题当然还是你的。

### 1. 显式同步：适合登录、退出这类关键动作

登录状态建议在 action 中显式同步，因为登录和退出都有明确业务含义。

```ts
const TOKEN_KEY = 'blog-token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const profile = ref<UserProfile | null>(null)

  async function login(form: LoginForm) {
    const result = await loginApi(form)

    token.value = result.token
    profile.value = result.profile
    localStorage.setItem(TOKEN_KEY, result.token)
  }

  function logout() {
    token.value = null
    profile.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return {
    token,
    profile,
    login,
    logout
  }
})
```

这段代码把 `token` 当成两份数据处理：

```text
store 中的 token：页面运行时使用，响应式，驱动视图
localStorage 中的 token：刷新后恢复 store 的初始值
```

真正应该被组件依赖的是 store。`localStorage` 只是恢复手段，不应该变成组件之间共享状态的入口。

### 2. 初始化时要考虑坏数据

`localStorage` 里的数据不一定可信。它可能是旧版本留下的，也可能被用户手动改过，也可能是格式损坏的字符串。

读取对象时，不要直接裸 `JSON.parse`：

```ts
type UserSettings = {
  theme: 'light' | 'dark'
  language: 'zh-CN' | 'en-US'
}

const SETTINGS_KEY = 'blog-settings'

function readSettings(): UserSettings {
  const raw = localStorage.getItem(SETTINGS_KEY)

  if (!raw) {
    return {
      theme: 'light',
      language: 'zh-CN'
    }
  }

  try {
    const value = JSON.parse(raw) as Partial<UserSettings>

    return {
      theme: value.theme === 'dark' ? 'dark' : 'light',
      language: value.language === 'en-US' ? 'en-US' : 'zh-CN'
    }
  } catch {
    localStorage.removeItem(SETTINGS_KEY)
    return {
      theme: 'light',
      language: 'zh-CN'
    }
  }
}
```

然后在 store 中使用：

```ts
export const useSettingsStore = defineStore('settings', () => {
  const initialSettings = readSettings()

  const theme = ref(initialSettings.theme)
  const language = ref(initialSettings.language)

  function setTheme(value: UserSettings['theme']) {
    theme.value = value
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      theme: theme.value,
      language: language.value
    }))
  }

  function setLanguage(value: UserSettings['language']) {
    language.value = value
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      theme: theme.value,
      language: language.value
    }))
  }

  return {
    theme,
    language,
    setTheme,
    setLanguage
  }
})
```

这里看起来比直接 `JSON.parse(localStorage.getItem('settings')!)` 麻烦一点，但它至少承认了现实：用户浏览器里的旧数据不一定配合你的新代码。现实不配合时，代码最好不要也跟着任性。

### 3. 使用 `$subscribe` 自动同步

对于设置类 store，也可以用 Pinia 的 `$subscribe` 监听 state 变化，然后统一写入 `localStorage`。

```ts
const settingsStore = useSettingsStore()

settingsStore.$subscribe((_mutation, state) => {
  localStorage.setItem('blog-settings', JSON.stringify({
    theme: state.theme,
    language: state.language
  }))
})
```

`$subscribe` 适合“状态一变就同步”的场景，比如主题、语言、布局偏好。它不太适合登录退出这种需要清理多份状态、跳转页面、取消请求、重置权限的业务动作。那些动作应该放在明确的 action 里。

如果你想全局持久化所有 Pinia 状态，也可以监听 `pinia.state`，或者使用持久化插件。但在学习阶段先不要急着全自动。自动化会把错误也自动化，而且速度很快。

### 4. 用户信息不一定要长期存本地

很多项目会在登录后保存：

```text
token
profile
permissions
menus
```

但它们的持久化策略不一定相同。

| 数据 | 建议 |
| ---- | ---- |
| `token` | 根据认证方案决定是否持久化 |
| `profile` | 可以启动后通过 `/me` 重新获取 |
| `permissions` | 更建议启动后重新拉取，避免权限变更后仍用旧值 |
| `menus` | 可以缓存，但要有刷新或失效策略 |
| `loading` / `errorMessage` | 不持久化 |

例如应用启动时可以这样做：

```ts
async function bootstrap() {
  if (!token.value) {
    return
  }

  try {
    profile.value = await fetchCurrentUser()
  } catch {
    logout()
  }
}
```

这表示：`localStorage` 只负责告诉应用“以前可能登录过”，最终是否真的有效，要以后端校验为准。前端本地状态只能提升体验，不能替代服务端判断。这个边界如果想不明白，权限系统迟早会给你上一课。

持久化的关键不是“存进去”，而是知道什么时候清理、什么时候刷新、什么时候以后端为准。登录过期、退出登录、切换账号时，如果旧状态还留着，页面会展示出非常自信但完全错误的信息。

## 十二、状态渲染

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

如果 store 中保留旧数据，可以把错误提示和列表同时展示：

```vue
<p v-if="postStore.errorMessage" class="error">
  {{ postStore.errorMessage }}
</p>

<PostList
  v-if="postStore.posts.length > 0"
  :posts="postStore.posts"
/>

<EmptyView
  v-else-if="!postStore.loading"
/>
```

这表示：刷新失败时，用户仍然能看到旧列表；首次加载失败时，页面再显示空状态或错误重试。状态设计越细，用户体验越不容易被一次失败击穿。

## 十三、数据流排错顺序

接口数据异常时，不要直接怀疑组件。按顺序查：

1. API 函数是否拿到了正确参数。
2. 请求封装是否正确解析响应。
3. Store action 是否改变了正确状态。
4. 页面是否渲染了 loading、error、empty、success。

越靠近源头的问题，越不该在页面组件里补丁式处理。否则组件会变成接口、状态和错误的混合垃圾场，虽然很常见，但常见不代表值得学习。

## 十四、Pinia 使用检查清单

写 store 时可以按下面顺序检查：

- 这个状态是否真的需要跨页面或跨组件共享？
- store 名称是否对应明确业务领域？
- action 名称是否表达业务动作？
- getter 是否只做派生计算，没有副作用？
- 请求失败时是否保留旧数据，还是主动清空？
- 是否处理了重复请求或过期响应？
- 是否只有必要状态被持久化？
- 是否区分了 store 的内存状态和 `localStorage` 的持久化副本？
- 从 `localStorage` 读取对象时，是否处理了空值、坏数据和旧版本结构？
- 登录、退出、切换账号时，是否会清理相关 store 和本地存储？
- 权限、用户资料、菜单这类数据是否需要启动后重新向后端确认？
- 组件是否通过 `storeToRefs` 解构 state 和 getter？
- 页面是否仍然保留了只属于自己的局部 UI 状态？

Pinia 不是为了让页面变空，而是为了让状态归属变清楚。页面可以有状态，组件可以有状态，组合函数也可以有状态。关键在于状态属于哪里，而不是它看起来放在哪里最“高级”。

## 十五、练习讲解：实现文章 store

实现一个文章 store：

- `posts`。
- `loading`。
- `errorMessage`。
- `loaded`。
- `loadPosts`。
- `refresh`。
- `toggleLike`。

要求接口失败时保留旧数据，并展示错误信息。做到这一点，说明你开始理解前端数据流，而不只是会调用接口。

### 1. 运行步骤

```bash
npm create vite@latest vue-pinia-demo -- --template vue-ts
cd vue-pinia-demo
npm install
npm install pinia
npm run dev
```

### 2. 替换 `src/main.ts`

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'

createApp(App)
  .use(createPinia())
  .mount('#app')
```

### 3. 创建 `src/api/posts.ts`

```ts
export type PostCard = {
  id: number
  title: string
  summary: string
  likes: number
  liked: boolean
}

let mockPosts: PostCard[] = [
  { id: 1, title: '请求封装要处理什么', summary: '响应码、错误信息、token 和超时。', likes: 8, liked: false },
  { id: 2, title: 'Pinia 不是所有状态的归宿', summary: '跨页面共享的数据才适合进入 store。', likes: 15, liked: true },
  { id: 3, title: '乐观更新必须能回滚', summary: '先改 UI 可以，但失败后要恢复。', likes: 5, liked: false }
]

function wait(ms = 500) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function randomFail() {
  return Math.random() < 0.25
}

export async function fetchPosts(): Promise<PostCard[]> {
  await wait()
  if (randomFail()) {
    throw new Error('文章列表加载失败，请稍后重试')
  }
  return structuredClone(mockPosts)
}

export async function updatePostLike(id: number, liked: boolean): Promise<void> {
  await wait(300)
  if (randomFail()) {
    throw new Error('点赞失败，状态已回滚')
  }

  mockPosts = mockPosts.map((post) => {
    if (post.id !== id) {
      return post
    }
    const diff = liked === post.liked ? 0 : liked ? 1 : -1
    return {
      ...post,
      liked,
      likes: post.likes + diff
    }
  })
}
```

### 4. 创建 `src/stores/postStore.ts`

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchPosts, updatePostLike, type PostCard } from '../api/posts'

export const usePostStore = defineStore('post', () => {
  const posts = ref<PostCard[]>([])
  const loading = ref(false)
  const errorMessage = ref('')
  const loaded = ref(false)

  const empty = computed(() => {
    return loaded.value && !loading.value && posts.value.length === 0
  })

  async function refresh() {
    if (loading.value) {
      return
    }

    loading.value = true
    errorMessage.value = ''

    try {
      posts.value = await fetchPosts()
      loaded.value = true
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function loadPosts() {
    if (loaded.value) {
      return
    }

    await refresh()
  }

  async function toggleLike(postId: number) {
    const post = posts.value.find((item) => item.id === postId)
    if (!post) {
      return
    }

    const previousLiked = post.liked
    const previousLikes = post.likes

    post.liked = !post.liked
    post.likes += post.liked ? 1 : -1
    errorMessage.value = ''

    try {
      await updatePostLike(post.id, post.liked)
    } catch (error) {
      post.liked = previousLiked
      post.likes = previousLikes
      errorMessage.value = error instanceof Error ? error.message : '点赞失败'
    }
  }

  return {
    posts,
    loading,
    errorMessage,
    loaded,
    empty,
    loadPosts,
    refresh,
    toggleLike
  }
})
```

### 5. 替换 `src/App.vue`

```vue
<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'
import { usePostStore } from './stores/postStore'

const postStore = usePostStore()
const { posts, loading, errorMessage, empty } = storeToRefs(postStore)
const { loadPosts, refresh, toggleLike } = postStore

onMounted(() => {
  loadPosts()
})
</script>

<template>
  <main class="page">
    <header class="toolbar">
      <h1>Pinia 文章 Store</h1>
      <button :disabled="loading" @click="refresh">
        {{ loading ? '加载中' : '刷新' }}
      </button>
    </header>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-if="loading && posts.length === 0" class="state">正在加载文章...</p>

    <section v-else-if="posts.length > 0" class="list">
      <article v-for="post in posts" :key="post.id" class="card">
        <div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.summary }}</p>
        </div>
        <button :class="{ active: post.liked }" @click="toggleLike(post.id)">
          {{ post.liked ? '已赞' : '点赞' }} · {{ post.likes }}
        </button>
      </article>
    </section>

    <p v-else-if="empty" class="state">暂无文章</p>
    <p v-else class="state">加载失败后可以点击刷新重试。</p>
  </main>
</template>

<style scoped>
.page {
  max-width: 840px;
  margin: 0 auto;
  padding: 32px 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

h1 {
  margin: 0;
  font-size: 26px;
}

.error {
  padding: 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #991b1b;
}

.state {
  color: #64748b;
}

.list {
  display: grid;
  gap: 12px;
}

.card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

p {
  margin: 0;
}

button {
  padding: 8px 12px;
  border: 1px solid #94a3b8;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

button.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}
</style>
```

### 6. 检查结果

页面会随机模拟请求失败。列表加载失败时，旧数据会保留；点赞失败时，会恢复原来的点赞状态并展示错误信息。这比“请求成功就赋值”更接近真实项目。
