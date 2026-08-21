+++
date = '2026-08-19T18:18:00+08:00'
draft = false
title = '响应式原理与组合式 API：ref、reactive、computed 和 watch'
+++

Vue 的核心是响应式。你修改状态，视图自动更新。要写好 Vue，就必须理解哪些数据会触发更新、派生数据应该放哪里、副作用应该如何管理。

## 一、ref

`ref` 用来声明响应式值。

```ts
const count = ref(0)

function increment() {
  count.value++
}
```

在 `<script setup>` 中访问要写 `.value`，模板中会自动解包。

```vue
<template>
  <button @click="increment">{{ count }}</button>
</template>
```

适合使用 `ref` 的场景：

- 基础类型。
- 数组。
- 需要整体替换的对象。
- DOM 引用。

## 二、reactive

`reactive` 用来声明响应式对象。

```ts
const form = reactive({
  username: '',
  password: ''
})
```

修改属性：

```ts
form.username = 'admin'
```

注意不要直接解构 `reactive` 对象，否则可能丢失响应式。

```ts
const { username } = form
```

如果需要解构，使用 `toRefs`：

```ts
const { username, password } = toRefs(form)
```

## 三、ref 和 reactive 怎么选

简单规则：

- 基础值用 `ref`。
- 表单对象可用 `reactive`。
- 接口列表常用 `ref<T[]>([])`。
- 需要整体替换时用 `ref` 更直接。

示例：

```ts
const posts = ref<PostCard[]>([])

async function loadPosts() {
  posts.value = await fetchPosts()
}
```

如果用 `reactive([])`，后续整体替换会不方便。

## 四、computed

`computed` 用来声明派生数据。

```ts
const keyword = ref('')
const posts = ref<PostCard[]>([])

const filteredPosts = computed(() => {
  return posts.value.filter(post => post.title.includes(keyword.value))
})
```

派生数据不要再单独存一份。否则源数据和派生数据可能不一致。

不推荐：

```ts
const filteredPosts = ref([])

watch(keyword, () => {
  filteredPosts.value = posts.value.filter(...)
})
```

能用 `computed` 表达的，就不要用 `watch` 硬写。

## 五、watch

`watch` 用来处理状态变化后的副作用。

```ts
watch(keyword, value => {
  console.log('搜索关键字变化', value)
})
```

典型副作用：

- 发请求。
- 写本地存储。
- 打日志。
- 操作非 Vue 管理的对象。

监听多个值：

```ts
watch([page, keyword], () => {
  loadPosts()
})
```

立即执行：

```ts
watch(keyword, () => {
  loadPosts()
}, {
  immediate: true
})
```

## 六、watchEffect

`watchEffect` 会自动收集依赖。

```ts
watchEffect(() => {
  console.log(keyword.value, page.value)
})
```

它适合依赖简单、调试性质或组合函数内部逻辑。业务请求更推荐显式 `watch`，因为依赖关系更清楚。

## 七、生命周期

常用生命周期：

```ts
onMounted(() => {
  loadPosts()
})

onUnmounted(() => {
  cleanup()
})
```

`onMounted` 适合页面首次加载数据、注册事件。`onUnmounted` 适合清理定时器、取消订阅。

## 八、组合函数

组合函数用于复用有状态逻辑，通常以 `use` 开头。

```ts
export function useLoading() {
  const loading = ref(false)

  async function run<T>(task: () => Promise<T>): Promise<T> {
    loading.value = true
    try {
      return await task()
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    run
  }
}
```

页面中使用：

```ts
const { loading, run } = useLoading()

async function submit() {
  await run(() => createPost(form))
}
```

组合函数不是工具函数。工具函数通常无状态，组合函数可以包含响应式状态、生命周期和副作用。

## 九、响应式设计原则

- 源状态只保留一份。
- 派生状态用 `computed`。
- 副作用用 `watch` 或生命周期。
- 能局部管理就不要放全局。
- 组件卸载时清理外部资源。

## 十、响应式排错思路

当页面没有按预期更新时，先检查三件事：

- 这个值是不是响应式数据，比如 `ref`、`reactive`、`computed`。
- 在 `<script setup>` 中是否忘了 `.value`。
- 是否把 `reactive` 对象解构成了普通变量。

响应式问题不要靠猜。沿着“源状态 -> 派生状态 -> 模板使用”的链路查，通常很快就能看到哪里断了。

## 十一、练习讲解：实现搜索列表

实现一个搜索列表：

- `keyword` 使用 `ref`。
- 原始列表使用 `ref<PostCard[]>([])`。
- 搜索结果使用 `computed`。
- 关键字变化时写入本地存储。
- 页面挂载时加载列表。

这一套组合起来，就是大量真实页面的基本骨架。

### 1. 运行步骤

```bash
npm create vite@latest vue-reactivity-demo -- --template vue-ts
cd vue-reactivity-demo
npm install
npm run dev
```

### 2. 替换 `src/App.vue`

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

type PostCard = {
  id: number
  title: string
  summary: string
  tags: string[]
}

const STORAGE_KEY = 'vue-course-keyword'

const keyword = ref(localStorage.getItem(STORAGE_KEY) ?? '')
const loading = ref(false)
const posts = ref<PostCard[]>([])

const filteredPosts = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) {
    return posts.value
  }

  return posts.value.filter((post) => {
    return post.title.toLowerCase().includes(text)
      || post.summary.toLowerCase().includes(text)
      || post.tags.some((tag) => tag.toLowerCase().includes(text))
  })
})

watch(keyword, (value) => {
  localStorage.setItem(STORAGE_KEY, value)
})

async function loadPosts() {
  loading.value = true
  try {
    await new Promise((resolve) => window.setTimeout(resolve, 400))
    posts.value = [
      {
        id: 1,
        title: 'ref 和 reactive 怎么选',
        summary: '基础类型优先 ref，需要整体替换的数据也适合 ref。',
        tags: ['vue', 'reactivity']
      },
      {
        id: 2,
        title: 'computed 不是 watch 的替代品',
        summary: 'computed 表达派生数据，watch 处理副作用。',
        tags: ['computed', 'watch']
      },
      {
        id: 3,
        title: '组合函数如何复用加载状态',
        summary: '组合函数可以包含响应式状态和业务动作。',
        tags: ['composable', 'loading']
      }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPosts()
})
</script>

<template>
  <main class="page">
    <h1>响应式搜索列表</h1>

    <input v-model="keyword" placeholder="搜索标题、摘要或标签" />

    <p v-if="loading" class="state">加载中...</p>
    <p v-else-if="filteredPosts.length === 0" class="state">没有匹配文章</p>

    <section v-else class="list">
      <article v-for="post in filteredPosts" :key="post.id" class="card">
        <h2>{{ post.title }}</h2>
        <p>{{ post.summary }}</p>
        <div class="tags">
          <span v-for="tag in post.tags" :key="tag">{{ tag }}</span>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 20px;
}

h1 {
  margin: 0 0 16px;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 16px;
}

.state {
  margin-top: 18px;
  color: #64748b;
}

.list {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.card {
  padding: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

p {
  margin: 0 0 12px;
  color: #475569;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tags span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 13px;
}
</style>
```

### 3. 实现步骤说明

1. `posts` 保存接口返回的原始列表，后续可以整体替换，所以使用 `ref<PostCard[]>([])`。
2. `filteredPosts` 是派生数据，用 `computed`，不再额外维护一份搜索结果。
3. `watch(keyword, ...)` 只负责写入本地存储，这是副作用。
4. `onMounted(loadPosts)` 模拟页面首次进入时加载数据。
5. 刷新页面后，搜索关键字能从 `localStorage` 恢复。
