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

## 十、练习

实现一个搜索列表：

- `keyword` 使用 `ref`。
- 原始列表使用 `ref<PostCard[]>([])`。
- 搜索结果使用 `computed`。
- 关键字变化时写入本地存储。
- 页面挂载时加载列表。

这一套组合起来，就是大量真实页面的基本骨架。
