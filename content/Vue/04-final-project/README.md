+++
date = '2026-08-21T18:40:00+08:00'
draft = false
title = '综合练习：Vue 3 文章管理后台'
+++

前面的文章分别讲了模板、响应式、组件通信、Pinia、接口请求、表单、路由、错误态和项目结构。最后这个练习把它们合成一个小项目：文章管理后台。

项目不连接真实后端，而是使用本地 mock API 模拟异步请求。这样做的好处是你可以专注前端链路：登录、路由守卫、列表搜索、分页、点赞、创建文章、详情页、权限判断、loading、empty、error。至于真实接口，只是把 mock API 换成 HTTP 请求而已。别急着把问题复杂化，复杂度会自己来的，它向来很勤快。

## 一、功能目标

最终项目包含：

- 登录页：模拟登录并保存 token。
- 路由守卫：未登录不能进入文章管理页面。
- 文章列表：加载、搜索、空状态、错误状态、分页加载。
- 点赞操作：乐观更新，失败后回滚。
- 创建文章：表单校验、防重复提交、成功后跳转详情页。
- 文章详情：根据路由参数加载文章。
- 权限控制：只有作者或管理员可以看到编辑提示。
- Pinia：管理登录状态和文章状态。
- 组件拆分：页面、业务组件、通用状态组件分离。

## 二、创建项目

```bash
npm create vite@latest vue-final-blog-admin -- --template vue-ts
cd vue-final-blog-admin
npm install
npm install vue-router@4 pinia
npm run dev
```

如果浏览器打开后能看到 Vite 默认页面，说明工程已经可运行。接下来替换和新增文件。

## 三、目录结构

```text
src/
  api/
    mockDb.ts
    postApi.ts
  components/
    AppHeader.vue
    EmptyState.vue
    ErrorState.vue
    LoadingState.vue
    PostCard.vue
  pages/
    LoginPage.vue
    PostCreatePage.vue
    PostDetailPage.vue
    PostListPage.vue
  router/
    index.ts
  stores/
    authStore.ts
    postStore.ts
  types/
    post.ts
    user.ts
  App.vue
  main.ts
  style.css
```

## 四、基础类型

创建 `src/types/user.ts`：

```ts
export type UserRole = 'admin' | 'editor' | 'viewer'

export type UserProfile = {
  id: number
  username: string
  nickname: string
  roles: UserRole[]
}
```

创建 `src/types/post.ts`：

```ts
export type PostCard = {
  id: number
  title: string
  summary: string
  authorId: number
  authorName: string
  likes: number
  liked: boolean
  createdAt: string
}

export type PostDetail = PostCard & {
  content: string
}

export type CreatePostRequest = {
  title: string
  content: string
}

export type PostPageQuery = {
  keyword: string
  page: number
  pageSize: number
}

export type PageResult<T> = {
  records: T[]
  total: number
  page: number
  pageSize: number
}
```

## 五、Mock 数据与 API

创建 `src/api/mockDb.ts`：

```ts
import type { PostDetail } from '../types/post'
import type { UserProfile, UserRole } from '../types/user'

export const currentUser: UserProfile = {
  id: 1,
  username: 'admin',
  nickname: '课程管理员',
  roles: ['admin', 'editor']
}

export let posts: PostDetail[] = [
  {
    id: 1,
    title: 'Vue 项目为什么需要状态边界',
    summary: '状态不是越集中越好，关键是生命周期和共享范围。',
    content: '组件状态、URL 状态、Pinia 状态和服务端状态有不同的生命周期。写项目时先判断状态归属，再决定代码位置。',
    authorId: 1,
    authorName: '课程管理员',
    likes: 18,
    liked: true,
    createdAt: '2026-08-21'
  },
  {
    id: 2,
    title: '表单页面如何处理失败',
    summary: '校验、提交中、服务端错误和成功跳转缺一不可。',
    content: '真实表单不是点击提交就结束。你需要校验输入、防重复提交、展示服务端错误，并在成功后清理或跳转。',
    authorId: 2,
    authorName: '前端同学',
    likes: 9,
    liked: false,
    createdAt: '2026-08-20'
  },
  {
    id: 3,
    title: '列表页为什么要有 empty 和 error',
    summary: '空数据不是错误，错误也不是空数据。',
    content: '列表页至少处理 loading、error、empty、success。只写成功状态，会让页面在真实网络环境下显得非常脆弱。',
    authorId: 2,
    authorName: '前端同学',
    likes: 12,
    liked: false,
    createdAt: '2026-08-19'
  }
]

export function setPosts(nextPosts: PostDetail[]) {
  posts = nextPosts
}
```

创建 `src/api/postApi.ts`：

```ts
import { currentUser, posts, setPosts } from './mockDb'
import type { CreatePostRequest, PageResult, PostCard, PostDetail, PostPageQuery } from '../types/post'
import type { UserProfile } from '../types/user'

function wait(ms = 450) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function maybeFail(message: string, rate = 0.12) {
  if (Math.random() < rate) {
    throw new Error(message)
  }
}

export async function loginApi(username: string, password: string): Promise<{
  token: string
  profile: UserProfile
}> {
  await wait()

  if (!username.trim() || !password.trim()) {
    throw new Error('请输入用户名和密码')
  }

  return {
    token: 'mock-token',
    profile: currentUser
  }
}

export async function fetchPostPage(query: PostPageQuery): Promise<PageResult<PostCard>> {
  await wait()
  maybeFail('文章列表加载失败，请重试')

  const keyword = query.keyword.trim().toLowerCase()
  const matched = posts.filter((post) => {
    if (!keyword) {
      return true
    }
    return post.title.toLowerCase().includes(keyword)
      || post.summary.toLowerCase().includes(keyword)
      || post.authorName.toLowerCase().includes(keyword)
  })

  const start = (query.page - 1) * query.pageSize
  const records = matched.slice(start, start + query.pageSize)

  return {
    records,
    total: matched.length,
    page: query.page,
    pageSize: query.pageSize
  }
}

export async function fetchPostDetail(id: number): Promise<PostDetail | null> {
  await wait()
  maybeFail('文章详情加载失败，请重试', 0.08)
  return posts.find((post) => post.id === id) ?? null
}

export async function createPostApi(payload: CreatePostRequest): Promise<PostDetail> {
  await wait()
  maybeFail('文章发布失败，请稍后重试', 0.1)

  const post: PostDetail = {
    id: Date.now(),
    title: payload.title,
    summary: payload.content.slice(0, 48),
    content: payload.content,
    authorId: currentUser.id,
    authorName: currentUser.nickname,
    likes: 0,
    liked: false,
    createdAt: new Date().toISOString().slice(0, 10)
  }

  setPosts([post, ...posts])
  return post
}

export async function updatePostLikeApi(id: number, liked: boolean): Promise<void> {
  await wait(280)
  maybeFail('点赞失败，已恢复原状态', 0.18)

  setPosts(posts.map((post) => {
    if (post.id !== id) {
      return post
    }

    const diff = liked === post.liked ? 0 : liked ? 1 : -1
    return {
      ...post,
      liked,
      likes: post.likes + diff
    }
  }))
}
```

## 六、Pinia Store

创建 `src/stores/authStore.ts`：

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { loginApi } from '../api/postApi'
import type { UserProfile } from '../types/user'

const TOKEN_KEY = 'vue-final-token'
const PROFILE_KEY = 'vue-final-profile'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const profile = ref<UserProfile | null>(
    localStorage.getItem(PROFILE_KEY)
      ? JSON.parse(localStorage.getItem(PROFILE_KEY) as string) as UserProfile
      : null
  )

  const loggedIn = computed(() => Boolean(token.value))

  function hasRole(role: UserRole) {
    return Boolean(profile.value?.roles.includes(role))
  }

  async function login(username: string, password: string) {
    const result = await loginApi(username, password)
    token.value = result.token
    profile.value = result.profile
    localStorage.setItem(TOKEN_KEY, result.token)
    localStorage.setItem(PROFILE_KEY, JSON.stringify(result.profile))
  }

  function logout() {
    token.value = null
    profile.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(PROFILE_KEY)
  }

  return {
    token,
    profile,
    loggedIn,
    hasRole,
    login,
    logout
  }
})
```

创建 `src/stores/postStore.ts`：

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { createPostApi, fetchPostPage, updatePostLikeApi } from '../api/postApi'
import type { CreatePostRequest, PostCard } from '../types/post'

export const usePostStore = defineStore('post', () => {
  const posts = ref<PostCard[]>([])
  const keyword = ref('')
  const page = ref(1)
  const pageSize = 2
  const total = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const errorMessage = ref('')

  const empty = computed(() => {
    return !loading.value && posts.value.length === 0
  })

  const finished = computed(() => {
    return posts.value.length >= total.value
  })

  async function loadFirstPage() {
    page.value = 1
    posts.value = []
    total.value = 0
    errorMessage.value = ''
    loading.value = true

    try {
      const result = await fetchPostPage({
        keyword: keyword.value,
        page: page.value,
        pageSize
      })
      posts.value = result.records
      total.value = result.total
      page.value = 2
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loadingMore.value || finished.value) {
      return
    }

    errorMessage.value = ''
    loadingMore.value = true

    try {
      const result = await fetchPostPage({
        keyword: keyword.value,
        page: page.value,
        pageSize
      })
      posts.value.push(...result.records)
      total.value = result.total
      page.value += 1
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载更多失败'
    } finally {
      loadingMore.value = false
    }
  }

  async function createPost(payload: CreatePostRequest) {
    const post = await createPostApi(payload)
    posts.value.unshift(post)
    total.value += 1
    return post
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
      await updatePostLikeApi(post.id, post.liked)
    } catch (error) {
      post.liked = previousLiked
      post.likes = previousLikes
      errorMessage.value = error instanceof Error ? error.message : '点赞失败'
    }
  }

  return {
    posts,
    keyword,
    page,
    pageSize,
    total,
    loading,
    loadingMore,
    errorMessage,
    empty,
    finished,
    loadFirstPage,
    loadMore,
    createPost,
    toggleLike
  }
})
```

## 七、路由

创建 `src/router/index.ts`：

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/posts' },
    { path: '/login', component: () => import('../pages/LoginPage.vue') },
    {
      path: '/posts',
      component: () => import('../pages/PostListPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/posts/create',
      component: () => import('../pages/PostCreatePage.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/posts/:id',
      component: () => import('../pages/PostDetailPage.vue'),
      meta: { requiresAuth: true }
    }
  ]
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.loggedIn) {
    return {
      path: '/login',
      query: {
        redirect: to.fullPath
      }
    }
  }
})
```

## 八、通用组件

创建 `src/components/LoadingState.vue`：

```vue
<template>
  <p class="state">加载中...</p>
</template>
```

创建 `src/components/EmptyState.vue`：

```vue
<script setup lang="ts">
defineProps<{
  message: string
}>()
</script>

<template>
  <p class="state empty">{{ message }}</p>
</template>
```

创建 `src/components/ErrorState.vue`：

```vue
<script setup lang="ts">
defineProps<{
  message: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-state">
    <p>{{ message }}</p>
    <button @click="$emit('retry')">重试</button>
  </div>
</template>
```

创建 `src/components/AppHeader.vue`：

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const router = useRouter()
const authStore = useAuthStore()

function logout() {
  authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <header class="app-header">
    <RouterLink class="brand" to="/posts">文章管理后台</RouterLink>
    <nav>
      <RouterLink to="/posts">文章</RouterLink>
      <RouterLink to="/posts/create">发布</RouterLink>
      <span v-if="authStore.profile">{{ authStore.profile.nickname }}</span>
      <button @click="logout">退出</button>
    </nav>
  </header>
</template>
```

创建 `src/components/PostCard.vue`：

```vue
<script setup lang="ts">
import type { PostCard } from '../types/post'

defineProps<{
  post: PostCard
  canEdit: boolean
}>()

defineEmits<{
  like: [postId: number]
}>()
</script>

<template>
  <article class="post-card">
    <div class="post-main">
      <RouterLink class="post-title" :to="`/posts/${post.id}`">{{ post.title }}</RouterLink>
      <p>{{ post.summary }}</p>
      <div class="meta">
        <span>{{ post.authorName }}</span>
        <span>{{ post.createdAt }}</span>
        <span v-if="canEdit">可编辑</span>
      </div>
    </div>

    <button class="like-button" :class="{ active: post.liked }" @click="$emit('like', post.id)">
      {{ post.liked ? '已赞' : '点赞' }} · {{ post.likes }}
    </button>
  </article>
</template>
```

## 九、页面

创建 `src/pages/LoginPage.vue`：

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: 'admin',
  password: '123456'
})

const errorMessage = ref('')
const submitting = ref(false)

async function submit() {
  if (submitting.value) {
    return
  }

  errorMessage.value = ''
  submitting.value = true

  try {
    await authStore.login(form.username, form.password)
    router.replace(String(route.query.redirect ?? '/posts'))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <form class="login-panel" @submit.prevent="submit">
      <h1>登录</h1>
      <label>
        用户名
        <input v-model.trim="form.username" />
      </label>
      <label>
        密码
        <input v-model="form.password" type="password" />
      </label>
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
      <button :disabled="submitting">{{ submitting ? '登录中...' : '登录' }}</button>
    </form>
  </main>
</template>
```

创建 `src/pages/PostListPage.vue`：

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from '../components/AppHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import LoadingState from '../components/LoadingState.vue'
import PostCard from '../components/PostCard.vue'
import { useAuthStore } from '../stores/authStore'
import { usePostStore } from '../stores/postStore'
import type { PostCard as PostCardModel } from '../types/post'

const authStore = useAuthStore()
const postStore = usePostStore()

function canEdit(post: PostCardModel) {
  return authStore.profile?.id === post.authorId || authStore.hasRole('admin')
}

onMounted(() => {
  postStore.loadFirstPage()
})
</script>

<template>
  <AppHeader />
  <main class="page">
    <section class="page-head">
      <div>
        <h1>文章列表</h1>
        <p>搜索、分页、点赞和错误态都在这里。</p>
      </div>
      <RouterLink class="primary-link" to="/posts/create">发布文章</RouterLink>
    </section>

    <form class="search-bar" @submit.prevent="postStore.loadFirstPage">
      <input v-model="postStore.keyword" placeholder="搜索标题、摘要或作者" />
      <button>搜索</button>
    </form>

    <ErrorState
      v-if="postStore.errorMessage"
      :message="postStore.errorMessage"
      @retry="postStore.loadFirstPage"
    />

    <LoadingState v-if="postStore.loading" />
    <EmptyState v-else-if="postStore.empty" message="暂无文章，或者你的搜索条件过于冷酷。" />

    <section v-else class="post-list">
      <PostCard
        v-for="post in postStore.posts"
        :key="post.id"
        :post="post"
        :can-edit="canEdit(post)"
        @like="postStore.toggleLike"
      />
    </section>

    <button
      v-if="!postStore.empty"
      class="load-more"
      :disabled="postStore.finished || postStore.loadingMore"
      @click="postStore.loadMore"
    >
      {{ postStore.finished ? '没有更多了' : postStore.loadingMore ? '加载中...' : '加载更多' }}
    </button>
  </main>
</template>
```

创建 `src/pages/PostCreatePage.vue`：

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import { usePostStore } from '../stores/postStore'

type FormState = {
  title: string
  content: string
}

const router = useRouter()
const postStore = usePostStore()

const form = reactive<FormState>({
  title: '',
  content: ''
})

const errors = reactive<Partial<Record<keyof FormState, string>>>({})
const serverError = ref('')
const submitting = ref(false)

function validateForm() {
  errors.title = form.title.trim() ? '' : '标题不能为空'
  errors.content = form.content.trim().length >= 20 ? '' : '内容不能少于 20 个字符'
  return !errors.title && !errors.content
}

async function submit() {
  if (submitting.value) {
    return
  }

  serverError.value = ''

  if (!validateForm()) {
    return
  }

  submitting.value = true
  try {
    const post = await postStore.createPost({
      title: form.title.trim(),
      content: form.content.trim()
    })
    router.push(`/posts/${post.id}`)
  } catch (error) {
    serverError.value = error instanceof Error ? error.message : '发布失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppHeader />
  <main class="page narrow">
    <h1>发布文章</h1>

    <form class="editor-form" @submit.prevent="submit">
      <label>
        标题
        <input v-model.trim="form.title" />
      </label>
      <p v-if="errors.title" class="form-error">{{ errors.title }}</p>

      <label>
        内容
        <textarea v-model="form.content" rows="8"></textarea>
      </label>
      <p v-if="errors.content" class="form-error">{{ errors.content }}</p>

      <p v-if="serverError" class="form-error panel-error">{{ serverError }}</p>

      <div class="actions">
        <button :disabled="submitting">{{ submitting ? '发布中...' : '发布' }}</button>
        <RouterLink to="/posts">取消</RouterLink>
      </div>
    </form>
  </main>
</template>
```

创建 `src/pages/PostDetailPage.vue`：

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPostDetail } from '../api/postApi'
import AppHeader from '../components/AppHeader.vue'
import ErrorState from '../components/ErrorState.vue'
import LoadingState from '../components/LoadingState.vue'
import { useAuthStore } from '../stores/authStore'
import type { PostDetail } from '../types/post'

const route = useRoute()
const authStore = useAuthStore()

const post = ref<PostDetail | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const canEdit = computed(() => {
  if (!post.value) {
    return false
  }
  return authStore.profile?.id === post.value.authorId || authStore.hasRole('admin')
})

async function loadPost() {
  loading.value = true
  errorMessage.value = ''

  try {
    post.value = await fetchPostDetail(Number(route.params.id))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadPost)
</script>

<template>
  <AppHeader />
  <main class="page narrow">
    <RouterLink to="/posts">返回列表</RouterLink>

    <ErrorState v-if="errorMessage" :message="errorMessage" @retry="loadPost" />
    <LoadingState v-if="loading" />

    <p v-else-if="!post" class="state">文章不存在</p>

    <article v-else class="detail">
      <h1>{{ post.title }}</h1>
      <div class="meta">
        <span>{{ post.authorName }}</span>
        <span>{{ post.createdAt }}</span>
        <span>{{ post.likes }} 次点赞</span>
        <span v-if="canEdit">你可以编辑这篇文章</span>
      </div>
      <p>{{ post.content }}</p>
    </article>
  </main>
</template>
```

## 十、入口文件

替换 `src/main.ts`：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router'
import './style.css'
import App from './App.vue'

createApp(App)
  .use(createPinia())
  .use(router)
  .mount('#app')
```

替换 `src/App.vue`：

```vue
<template>
  <RouterView />
</template>
```

## 十一、全局样式

替换 `src/style.css`：

```css
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8fafc;
  color: #1f2937;
}

* {
  box-sizing: border-box;
}

a {
  color: #2563eb;
  text-decoration: none;
}

button,
input,
textarea {
  font: inherit;
}

button {
  padding: 9px 13px;
  border: 0;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

input,
textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.brand {
  color: #111827;
  font-weight: 700;
}

.app-header nav {
  display: flex;
  align-items: center;
  gap: 14px;
}

.app-header nav button {
  background: #475569;
}

.page {
  display: grid;
  gap: 18px;
  max-width: 960px;
  margin: 0 auto;
  padding: 28px 20px;
}

.page.narrow {
  max-width: 720px;
}

.login-page {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 20px;
}

.login-panel {
  display: grid;
  gap: 14px;
  width: min(100%, 380px);
  padding: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}

.page-head h1,
.login-panel h1,
.detail h1 {
  margin: 0;
}

.page-head p,
.detail p {
  margin: 8px 0 0;
  color: #475569;
}

.primary-link {
  padding: 9px 13px;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
}

.search-bar {
  display: flex;
  gap: 10px;
}

.post-list {
  display: grid;
  gap: 12px;
}

.post-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.post-main {
  min-width: 0;
}

.post-title {
  display: inline-block;
  margin-bottom: 8px;
  color: #111827;
  font-size: 18px;
  font-weight: 700;
}

.post-card p {
  margin: 0 0 10px;
  color: #475569;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #64748b;
  font-size: 14px;
}

.like-button {
  flex: 0 0 auto;
  min-width: 96px;
  background: #e2e8f0;
  color: #1f2937;
}

.like-button.active {
  background: #16a34a;
  color: #fff;
}

.state {
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
  background: #fff;
}

.empty {
  color: #475569;
}

.error-state,
.panel-error {
  padding: 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #991b1b;
}

.error-state {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.editor-form {
  display: grid;
  gap: 12px;
}

.editor-form label,
.login-panel label {
  display: grid;
  gap: 6px;
  font-weight: 600;
}

.form-error {
  margin: 0;
  color: #b91c1c;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.load-more {
  justify-self: center;
  min-width: 140px;
}

.detail {
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

@media (max-width: 640px) {
  .app-header,
  .page-head,
  .post-card,
  .search-bar,
  .error-state {
    align-items: stretch;
    flex-direction: column;
  }

  .app-header nav {
    flex-wrap: wrap;
  }
}
```

## 十二、运行与验收

启动项目：

```bash
npm run dev
```

验收路径：

1. 访问 `/posts`，未登录时会跳转 `/login`。
2. 登录页默认填好了用户名和密码，点击登录后进入文章列表。
3. 在列表页搜索关键字，比如 `Vue`、`表单`、`前端同学`。
4. 点击“加载更多”，观察分页追加。
5. 点击点赞，偶尔会模拟失败并回滚。
6. 点击“发布文章”，标题不能为空，内容不能少于 20 个字符。
7. 发布成功后进入详情页。
8. 在详情页能看到作者、日期、点赞数和权限提示。
9. 点击退出后再次访问 `/posts/create`，会被路由守卫拦回登录页。

## 十三、继续扩展

完成以后，可以继续做这些增强：

- 把 mock API 替换成真实后端接口。
- 给 `postStore` 增加 Vitest 单元测试。
- 给列表页增加 URL query 同步，让搜索条件可分享。
- 增加编辑文章页面。
- 增加统一请求封装和 401 处理。
- 增加虚拟列表或图片懒加载。

这个综合练习的重点不是功能数量，而是前端工程链路是否完整。能把一个普通后台页面写得边界清楚、状态完整、失败可控，比堆一堆看起来很高级的依赖更可靠。华丽并不稀缺，可靠才稀缺。
