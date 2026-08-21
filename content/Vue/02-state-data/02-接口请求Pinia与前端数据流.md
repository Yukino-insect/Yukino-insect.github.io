+++
date = '2026-08-19T18:16:00+08:00'
draft = false
title = '接口请求、Pinia 与前端数据流：把服务端数据管起来'
+++

真实前端应用离不开接口。页面展示的数据、用户登录状态、分页列表、权限信息、提交结果都来自服务端。接口请求和状态管理如果没有统一设计，很快就会散成一地。

这篇文章讨论三件事：

- 接口请求应该怎样从组件里抽离出来。
- 什么状态适合放在 Pinia，什么状态应该留在页面。
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

## 八、Store 请求状态设计

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

## 九、乐观更新

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

## 十、持久化边界

不是所有 store 状态都应该持久化到 `localStorage`。

适合持久化：

- token。
- 主题。
- 语言。
- 用户主动选择的布局偏好。

不适合持久化：

- loading。
- errorMessage。
- 临时弹窗状态。
- 可能过期的敏感用户资料。
- 很大的列表缓存。

以 token 为例，可以在登录和退出时显式同步：

```ts
async function login(form: LoginForm) {
  const result = await loginApi(form)
  token.value = result.token
  localStorage.setItem('token', result.token)
}

function logout() {
  token.value = null
  profile.value = null
  localStorage.removeItem('token')
}
```

持久化的关键不是“存进去”，而是知道什么时候清理。登录过期、退出登录、切换账号时，如果旧状态还留着，页面会展示出非常自信但完全错误的信息。

## 十一、状态渲染

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

## 十二、数据流排错顺序

接口数据异常时，不要直接怀疑组件。按顺序查：

1. API 函数是否拿到了正确参数。
2. 请求封装是否正确解析响应。
3. Store action 是否改变了正确状态。
4. 页面是否渲染了 loading、error、empty、success。

越靠近源头的问题，越不该在页面组件里补丁式处理。否则组件会变成接口、状态和错误的混合垃圾场，虽然很常见，但常见不代表值得学习。

## 十三、Pinia 使用检查清单

写 store 时可以按下面顺序检查：

- 这个状态是否真的需要跨页面或跨组件共享？
- store 名称是否对应明确业务领域？
- action 名称是否表达业务动作？
- getter 是否只做派生计算，没有副作用？
- 请求失败时是否保留旧数据，还是主动清空？
- 是否处理了重复请求或过期响应？
- 是否只有必要状态被持久化？
- 组件是否通过 `storeToRefs` 解构 state 和 getter？
- 页面是否仍然保留了只属于自己的局部 UI 状态？

Pinia 不是为了让页面变空，而是为了让状态归属变清楚。页面可以有状态，组件可以有状态，组合函数也可以有状态。关键在于状态属于哪里，而不是它看起来放在哪里最“高级”。

## 十四、练习讲解：实现文章 store

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
