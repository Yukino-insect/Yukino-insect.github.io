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

## 十、数据流排错顺序

接口数据异常时，不要直接怀疑组件。按顺序查：

1. API 函数是否拿到了正确参数。
2. 请求封装是否正确解析响应。
3. Store action 是否改变了正确状态。
4. 页面是否渲染了 loading、error、empty、success。

越靠近源头的问题，越不该在页面组件里补丁式处理。否则组件会变成接口、状态和错误的混合垃圾场，虽然很常见，但常见不代表值得学习。

## 十一、练习讲解：实现文章 store

实现一个文章 store：

- `posts`。
- `loading`。
- `errorMessage`。
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

  const empty = computed(() => {
    return !loading.value && posts.value.length === 0
  })

  async function loadPosts() {
    loading.value = true
    errorMessage.value = ''

    try {
      posts.value = await fetchPosts()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    await loadPosts()
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
import { onMounted } from 'vue'
import { usePostStore } from './stores/postStore'

const postStore = usePostStore()

onMounted(() => {
  postStore.loadPosts()
})
</script>

<template>
  <main class="page">
    <header class="toolbar">
      <h1>Pinia 文章 Store</h1>
      <button :disabled="postStore.loading" @click="postStore.refresh">
        {{ postStore.loading ? '加载中' : '刷新' }}
      </button>
    </header>

    <p v-if="postStore.errorMessage" class="error">{{ postStore.errorMessage }}</p>
    <p v-if="postStore.loading" class="state">正在加载文章...</p>
    <p v-else-if="postStore.empty" class="state">暂无文章</p>

    <section v-else class="list">
      <article v-for="post in postStore.posts" :key="post.id" class="card">
        <div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.summary }}</p>
        </div>
        <button :class="{ active: post.liked }" @click="postStore.toggleLike(post.id)">
          {{ post.liked ? '已赞' : '点赞' }} · {{ post.likes }}
        </button>
      </article>
    </section>
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
