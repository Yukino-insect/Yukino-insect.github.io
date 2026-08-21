+++
date = '2026-08-19T18:14:00+08:00'
draft = false
title = '路由、页面结构与 uni-app 工程：从单页到跨端应用'
+++

Vue 应用最终要组织成页面。Web 项目通常使用 Vue Router，uni-app 项目使用 `pages.json` 配置页面和导航。无论形式如何，核心问题都是：页面在哪里，如何进入，参数怎么传，权限怎么控制。

## 一、Web 路由基本概念

Vue Router 常见配置：

```ts
const routes = [
  {
    path: '/',
    component: () => import('@/pages/home/index.vue')
  },
  {
    path: '/posts/:id',
    component: () => import('@/pages/post-detail/index.vue')
  }
]
```

路由参数：

```ts
const route = useRoute()
const postId = Number(route.params.id)
```

查询参数：

```ts
const keyword = computed(() => String(route.query.keyword ?? ''))
```

把可分享、可回退的状态放进 URL，比藏在组件状态里更合适。

## 二、路由守卫

登录校验：

```ts
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

路由守卫适合页面级权限，不适合写大量业务逻辑。

## 三、uni-app 页面配置

uni-app 使用 `pages.json` 配置页面：

```json
{
  "pages": [
    {
      "path": "pages/index/index",
      "style": {
        "navigationBarTitleText": "首页"
      }
    },
    {
      "path": "pages/post/detail",
      "style": {
        "navigationBarTitleText": "详情"
      }
    }
  ]
}
```

页面文件通常对应：

```text
pages/
  index/
    index.vue
  post/
    detail.vue
```

## 四、页面生命周期

uni-app 有页面生命周期，例如：

```ts
onLoad((query) => {
  postId.value = Number(query.id)
  loadPost()
})

onShow(() => {
  refreshIfNeeded()
})
```

Vue 生命周期关注组件挂载，uni-app 页面生命周期关注页面进入、显示、隐藏、下拉刷新等跨端行为。两者可以同时存在，但语义不同。

## 五、跳转与参数

uni-app 跳转：

```ts
uni.navigateTo({
  url: `/pages/post/detail?id=${post.id}`
})
```

返回：

```ts
uni.navigateBack()
```

切换 tab：

```ts
uni.switchTab({
  url: '/pages/index/index'
})
```

参数要编码，尤其是包含中文或特殊字符时：

```ts
const keyword = encodeURIComponent(searchText.value)
uni.navigateTo({
  url: `/pages/search/index?keyword=${keyword}`
})
```

## 六、目录结构

推荐结构：

```text
src/
  pages/
  components/
  api/
  models/
  stores/
  composables/
  utils/
  styles/
```

职责：

- `pages`：页面入口。
- `components`：可复用组件。
- `api`：接口请求。
- `models`：类型定义。
- `stores`：全局状态。
- `composables`：组合函数。
- `utils`：无状态工具函数。
- `styles`：全局样式、变量和混入。

## 七、easycom

uni-app 支持 easycom 自动导入组件。配置后，符合规则的组件可以直接在模板里使用。

```json
{
  "easycom": {
    "autoscan": true,
    "custom": {
      "^Base(.*)": "@/components/base/Base$1.vue"
    }
  }
}
```

自动导入能减少样板代码，但命名规则要清楚。组件名混乱时，自动化只会自动制造混乱。

## 八、跨端条件编译

uni-app 支持条件编译：

```ts
// #ifdef H5
console.log('仅 H5 执行')
// #endif

// #ifdef MP-WEIXIN
console.log('仅微信小程序执行')
// #endif
```

条件编译应该集中、克制。到处散落平台判断，会让代码很难维护。

## 九、页面设计原则

- 页面负责组织业务流程。
- 组件负责展示和局部交互。
- API 模块负责请求。
- Store 负责跨页面状态。
- 组合函数负责复用逻辑。
- 工具函数负责纯数据处理。

当你不知道代码放哪里时，先判断它依赖什么、被谁复用、生命周期属于谁。

## 十、路由与页面边界

路由不是简单的 URL 到组件映射。它决定页面级生命周期、权限入口、参数来源和浏览器回退行为。页面组件应该接收路由参数、组织业务流程，然后把展示交给组件，把请求交给 API，把共享状态交给 store。把所有逻辑塞进路由守卫里，通常只是把问题搬到了一个更难调试的地方。

## 十一、练习讲解：设计并跑通文章模块目录

设计一个文章模块目录：

```text
pages/post/list.vue
pages/post/detail.vue
pages/post/create.vue
api/post.ts
models/post.ts
stores/post.ts
components/post/PostCard.vue
composables/usePostList.ts
```

然后说明每个文件的职责，并在 Web 路由中跑通列表、详情和创建页。能说清职责，才有资格开始写代码。

### 1. 运行步骤

```bash
npm create vite@latest vue-router-module-demo -- --template vue-ts
cd vue-router-module-demo
npm install
npm install vue-router@4
npm run dev
```

### 2. 建议目录

```text
src/
  api/
    post.ts
  models/
    post.ts
  composables/
    usePostList.ts
  components/
    post/
      PostCard.vue
  pages/
    post/
      list.vue
      detail.vue
      create.vue
  router.ts
  main.ts
  App.vue
```

### 3. 创建 `src/models/post.ts`

```ts
export type PostCard = {
  id: number
  title: string
  summary: string
}

export type PostDetail = PostCard & {
  content: string
}

export type CreatePostRequest = {
  title: string
  content: string
}
```

### 4. 创建 `src/api/post.ts`

```ts
import type { CreatePostRequest, PostCard, PostDetail } from '../models/post'

let posts: PostDetail[] = [
  {
    id: 1,
    title: '路由参数应该在哪里读取',
    summary: '页面读取参数，API 接收明确的业务参数。',
    content: '详情页通过 useRoute 读取 id，然后调用 fetchPostDetail。'
  },
  {
    id: 2,
    title: '页面目录如何组织',
    summary: '页面按业务模块归档，组件按复用边界归档。',
    content: '列表、详情、创建都属于 post 页面模块。'
  }
]

function wait() {
  return new Promise((resolve) => window.setTimeout(resolve, 300))
}

export async function fetchPostList(): Promise<PostCard[]> {
  await wait()
  return posts.map(({ id, title, summary }) => ({ id, title, summary }))
}

export async function fetchPostDetail(id: number): Promise<PostDetail | null> {
  await wait()
  return posts.find((post) => post.id === id) ?? null
}

export async function createPost(payload: CreatePostRequest): Promise<PostDetail> {
  await wait()
  const post = {
    id: Date.now(),
    title: payload.title,
    summary: payload.content.slice(0, 40),
    content: payload.content
  }
  posts.unshift(post)
  return post
}
```

### 5. 创建 `src/composables/usePostList.ts`

```ts
import { onMounted, ref } from 'vue'
import { fetchPostList } from '../api/post'
import type { PostCard } from '../models/post'

export function usePostList() {
  const posts = ref<PostCard[]>([])
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadPosts() {
    loading.value = true
    errorMessage.value = ''
    try {
      posts.value = await fetchPostList()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  onMounted(loadPosts)

  return {
    posts,
    loading,
    errorMessage,
    loadPosts
  }
}
```

### 6. 创建 `src/components/post/PostCard.vue`

```vue
<script setup lang="ts">
import type { PostCard } from '../../models/post'

defineProps<{
  post: PostCard
}>()
</script>

<template>
  <RouterLink class="card" :to="`/posts/${post.id}`">
    <h2>{{ post.title }}</h2>
    <p>{{ post.summary }}</p>
  </RouterLink>
</template>

<style scoped>
.card {
  display: block;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: inherit;
  text-decoration: none;
}

h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

p {
  margin: 0;
  color: #64748b;
}
</style>
```

### 7. 创建页面文件

`src/pages/post/list.vue`

```vue
<script setup lang="ts">
import PostCard from '../../components/post/PostCard.vue'
import { usePostList } from '../../composables/usePostList'

const { posts, loading, errorMessage, loadPosts } = usePostList()
</script>

<template>
  <main class="page">
    <header class="toolbar">
      <h1>文章列表</h1>
      <RouterLink to="/posts/create">发布文章</RouterLink>
    </header>

    <p v-if="loading">加载中...</p>
    <p v-else-if="errorMessage">
      {{ errorMessage }}
      <button @click="loadPosts">重试</button>
    </p>
    <section v-else class="list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
    </section>
  </main>
</template>
```

`src/pages/post/detail.vue`

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPostDetail } from '../../api/post'
import type { PostDetail } from '../../models/post'

const route = useRoute()
const post = ref<PostDetail | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  post.value = await fetchPostDetail(Number(route.params.id))
  loading.value = false
})
</script>

<template>
  <main class="page">
    <RouterLink to="/posts">返回列表</RouterLink>
    <p v-if="loading">加载中...</p>
    <p v-else-if="!post">文章不存在</p>
    <article v-else>
      <h1>{{ post.title }}</h1>
      <p>{{ post.content }}</p>
    </article>
  </main>
</template>
```

`src/pages/post/create.vue`

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createPost } from '../../api/post'

const router = useRouter()
const submitting = ref(false)
const form = reactive({
  title: '',
  content: ''
})

async function submit() {
  if (!form.title.trim() || !form.content.trim() || submitting.value) {
    return
  }

  submitting.value = true
  const post = await createPost({
    title: form.title.trim(),
    content: form.content.trim()
  })
  submitting.value = false
  router.push(`/posts/${post.id}`)
}
</script>

<template>
  <main class="page">
    <h1>发布文章</h1>
    <form class="form" @submit.prevent="submit">
      <input v-model="form.title" placeholder="标题" />
      <textarea v-model="form.content" placeholder="内容" rows="6"></textarea>
      <button :disabled="submitting">{{ submitting ? '提交中' : '提交' }}</button>
    </form>
  </main>
</template>
```

### 8. 创建 `src/router.ts`、`src/main.ts` 和 `src/App.vue`

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/posts' },
    { path: '/posts', component: () => import('./pages/post/list.vue') },
    { path: '/posts/create', component: () => import('./pages/post/create.vue') },
    { path: '/posts/:id', component: () => import('./pages/post/detail.vue') }
  ]
})
```

```ts
import { createApp } from 'vue'
import { router } from './router'
import './style.css'
import App from './App.vue'

createApp(App).use(router).mount('#app')
```

```vue
<template>
  <RouterView />
</template>
```

### 9. 样式可直接放到 `src/style.css`

```css
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8fafc;
  color: #1f2937;
}

.page {
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.list,
.form {
  display: grid;
  gap: 12px;
}

input,
textarea {
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
}

button,
a {
  color: #2563eb;
}
```
