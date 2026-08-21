+++
date = '2026-08-19T18:18:00+08:00'
draft = false
title = '响应式原理与组合式 API：状态、派生数据和副作用'
+++

Vue 的核心不是“模板里可以写一些特殊语法”，而是**响应式状态驱动视图更新**。

写 Vue 页面时，你真正反复处理的是四类东西：

- **源状态**：页面最原始的数据，比如 `keyword`、`posts`、`loading`。
- **派生状态**：由源状态计算出来的数据，比如 `filteredPosts`、`totalLikes`。
- **副作用**：状态变化后要额外做的事，比如发请求、写本地存储、操作浏览器 API。
- **组合函数**：把一组相关的状态、计算和副作用封装起来复用。

如果这四类分不清，`ref`、`reactive`、`computed`、`watch` 就会变成一串要背的 API。这样学当然也能写出代码，只是每次写都像在猜，未免太不体面。

## 一、先理解响应式到底是什么

普通变量不会自动更新视图：

```ts
let count = 0

function increment() {
  count++
}
```

如果你只是在 JavaScript 里改了 `count`，浏览器页面不会自动知道这个变量变了。没有框架时，你需要手动操作 DOM：

```ts
const button = document.querySelector('button')
const counter = document.querySelector('#counter')

let count = 0

button?.addEventListener('click', () => {
  count++
  counter!.textContent = String(count)
})
```

这类代码的思路是：

```text
数据变了
 -> 手动找到 DOM
 -> 手动修改 DOM
```

Vue 的思路是：

```text
声明响应式状态
 -> 模板使用状态
 -> 状态变化
 -> Vue 自动更新用到它的视图
```

示例：

```vue
<script setup lang="ts">
import { ref } from 'vue'

const count = ref(0)

function increment() {
  count.value++
}
</script>

<template>
  <button @click="increment">
    点击次数：{{ count }}
  </button>
</template>
```

这里你没有手动修改按钮文本。你只修改了 `count.value`，Vue 会负责让模板中 `{{ count }}` 对应的位置更新。

这就是响应式最重要的心智模型：

```text
你改状态，Vue 改页面
```

## 二、响应式更新的大致过程

可以把 Vue 的响应式过程粗略理解成三步：

```text
组件渲染时读取响应式数据
 -> Vue 记录“这个模板依赖了哪些数据”
 -> 数据变化时，Vue 重新更新依赖它的视图
```

比如模板中使用了 `count`：

```vue
<p>{{ count }}</p>
```

组件渲染时，Vue 发现这里读取了 `count`。以后 `count` 变化，Vue 就知道这块视图需要更新。

再比如：

```vue
<p>{{ user.name }}</p>
<button :disabled="loading">提交</button>
```

Vue 会追踪这些读取关系：

```text
模板文本依赖 user.name
按钮 disabled 属性依赖 loading
```

所以响应式不是“所有东西都重新来一遍”这么粗暴。它的核心是依赖追踪：谁用到了响应式数据，数据变化后谁就需要更新。

当然，学习阶段不必钻进源码。先记住这条线就够了：

```text
响应式数据被读取时会被追踪
响应式数据被修改时会触发更新
```

## 三、ref：声明一个响应式值

`ref` 用来声明响应式值。

```ts
import { ref } from 'vue'

const count = ref(0)
```

在 `<script setup>` 中，读取和修改都要写 `.value`：

```ts
console.log(count.value)

count.value++
```

模板中可以直接使用，不需要 `.value`：

```vue
<template>
  <p>{{ count }}</p>
</template>
```

这是因为 Vue 会在模板中自动解包 `ref`。也就是说，模板里的：

```vue
{{ count }}
```

可以理解成：

```text
显示 count.value
```

`ref` 适合这些场景：

- 基础类型，比如 `string`、`number`、`boolean`。
- 数组，比如 `ref<Post[]>([])`。
- 需要整体替换的对象。
- DOM 引用，比如 `ref<HTMLInputElement | null>(null)`。

示例：

```ts
const keyword = ref('')
const loading = ref(false)
const posts = ref<Post[]>([])
```

修改方式：

```ts
keyword.value = 'vue'
loading.value = true
posts.value = await fetchPosts()
```

`ref` 的特点是：外层有一个 `.value` 容器。这个容器让 Vue 能够追踪读取和修改。

## 四、reactive：声明一个响应式对象

`reactive` 用来声明响应式对象：

```ts
import { reactive } from 'vue'

const form = reactive({
  username: '',
  password: ''
})
```

访问和修改属性时，不需要 `.value`：

```ts
form.username = 'admin'
form.password = '123456'
```

模板中也直接使用：

```vue
<input v-model="form.username">
<input v-model="form.password" type="password">
```

`reactive` 适合一组关系紧密的字段，比如表单：

```ts
const form = reactive({
  title: '',
  content: '',
  tags: [] as string[]
})
```

它的优势是写起来像普通对象，字段很多时比较自然。

不过要注意一个常见问题：不要随便解构 `reactive` 对象。

不推荐：

```ts
const { username, password } = form
```

这样解构出来的 `username`、`password` 是普通变量，不再保持和 `form` 的响应式连接。

如果确实需要解构，使用 `toRefs`：

```ts
import { toRefs } from 'vue'

const { username, password } = toRefs(form)
```

这时 `username` 和 `password` 都是 `ref`：

```ts
username.value = 'admin'
```

模板里仍然可以直接使用：

```vue
<input v-model="username">
```

## 五、ref 和 reactive 怎么选

初学时不用纠结得太复杂，可以先用下面这套规则：

| 场景 | 推荐 |
| ---- | ---- |
| 字符串、数字、布尔值 | `ref` |
| 接口列表 | `ref<T[]>([])` |
| 需要整体替换的数据 | `ref` |
| 表单对象 | `reactive` 或 `ref` 都可以 |
| DOM 引用 | `ref` |
| 很多字段关系紧密的对象 | `reactive` |

比如接口列表常用 `ref`：

```ts
const posts = ref<Post[]>([])

async function loadPosts() {
  posts.value = await fetchPosts()
}
```

因为接口返回后通常会整体替换数组：

```ts
posts.value = newPosts
```

表单可以用 `reactive`：

```ts
const form = reactive({
  username: '',
  password: ''
})
```

也可以用 `ref`：

```ts
const form = ref({
  username: '',
  password: ''
})
```

只是使用时要写：

```ts
form.value.username = 'admin'
```

如果你还没有形成偏好，可以先这样：

- 单个值用 `ref`。
- 接口数组用 `ref<T[]>([])`。
- 表单对象用 `reactive`。

这套规则不完美，但足够稳。

## 六、源状态和派生状态

理解 `computed` 前，必须先区分源状态和派生状态。

源状态是直接保存的数据：

```ts
const keyword = ref('')
const posts = ref<Post[]>([])
```

派生状态是根据源状态算出来的数据：

```ts
const filteredPosts = computed(() => {
  return posts.value.filter((post) => {
    return post.title.includes(keyword.value)
  })
})
```

这里：

- `keyword` 是源状态。
- `posts` 是源状态。
- `filteredPosts` 是派生状态。

派生状态不应该再单独存一份。

不推荐：

```ts
const posts = ref<Post[]>([])
const filteredPosts = ref<Post[]>([])

function search() {
  filteredPosts.value = posts.value.filter((post) => {
    return post.title.includes(keyword.value)
  })
}
```

这样会带来一个问题：你需要自己保证 `posts`、`keyword`、`filteredPosts` 三者永远同步。

一旦忘记在某个时机调用 `search()`，页面就会显示旧数据。代码不会主动提醒你，它只会安静地错下去。

推荐：

```ts
const filteredPosts = computed(() => {
  const text = keyword.value.trim().toLowerCase()

  if (!text) {
    return posts.value
  }

  return posts.value.filter((post) => {
    return post.title.toLowerCase().includes(text)
  })
})
```

这样 `filteredPosts` 永远来自 `keyword` 和 `posts`，不会出现“源数据变了，搜索结果忘了更新”的问题。

## 七、computed：声明派生数据

`computed` 用来声明派生数据。

```ts
import { computed, ref } from 'vue'

const firstName = ref('Yukino')
const lastName = ref('Yukinoshita')

const fullName = computed(() => {
  return `${firstName.value} ${lastName.value}`
})
```

模板中使用：

```vue
<p>{{ fullName }}</p>
```

在 `<script setup>` 中读取：

```ts
console.log(fullName.value)
```

这里 `fullName` 不是普通字符串，而是一个只读的 `ref`。它的值由 `firstName` 和 `lastName` 计算出来。

当 `firstName` 或 `lastName` 变化时，`fullName` 会变成“需要重新计算”。当下次读取 `fullName.value` 时，Vue 会得到新的结果。

简单理解：

```text
computed = 带缓存的响应式计算结果
```

## 八、为什么不用普通函数

这是非常关键的问题。

你当然可以定义一个普通函数，然后在模板里调用：

```vue
<script setup lang="ts">
import { ref } from 'vue'

const firstName = ref('Yukino')
const lastName = ref('Yukinoshita')

function getFullName() {
  return `${firstName.value} ${lastName.value}`
}
</script>

<template>
  <p>{{ getFullName() }}</p>
</template>
```

这段代码能运行。

所以问题不是“普通函数行不行”，而是：

```text
普通函数什么时候会重新执行？
computed 什么时候会重新计算？
```

普通函数在模板里被调用时，只要组件重新渲染，它就会再次执行。

比如：

```vue
<script setup lang="ts">
import { ref } from 'vue'

const firstName = ref('Yukino')
const lastName = ref('Yukinoshita')
const count = ref(0)

function getFullName() {
  console.log('getFullName 执行了')
  return `${firstName.value} ${lastName.value}`
}
</script>

<template>
  <button @click="count++">点击次数：{{ count }}</button>
  <p>{{ getFullName() }}</p>
</template>
```

你点击按钮时，只改了 `count`，并没有改 `firstName` 或 `lastName`。但组件重新渲染时，模板里的 `getFullName()` 仍然可能再次执行。

如果换成 `computed`：

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'

const firstName = ref('Yukino')
const lastName = ref('Yukinoshita')
const count = ref(0)

const fullName = computed(() => {
  console.log('fullName 重新计算了')
  return `${firstName.value} ${lastName.value}`
})
</script>

<template>
  <button @click="count++">点击次数：{{ count }}</button>
  <p>{{ fullName }}</p>
</template>
```

点击按钮只改变 `count` 时，`fullName` 不需要重新计算，因为它依赖的是 `firstName` 和 `lastName`。

这就是 `computed` 和普通函数的关键区别：

| 写法 | 是否缓存 | 什么时候重新执行 |
| ---- | -------- | ---------------- |
| 普通函数 | 不缓存 | 模板重新渲染并调用它时 |
| `computed` | 缓存 | 依赖的响应式数据变化后，下次读取时 |

所以：

- 简单格式化、几乎没有成本的逻辑，用普通函数也可以。
- 需要根据响应式状态得到一个结果，并且希望结果跟随依赖自动更新，用 `computed`。
- 过滤列表、统计数量、计算按钮状态、计算展示文案，优先用 `computed`。

## 九、computed 适合放什么

`computed` 适合放**由已有状态推导出来的值**。

### 1. 搜索结果

```ts
const filteredPosts = computed(() => {
  const text = keyword.value.trim().toLowerCase()

  if (!text) {
    return posts.value
  }

  return posts.value.filter((post) => {
    return post.title.toLowerCase().includes(text)
      || post.summary.toLowerCase().includes(text)
  })
})
```

### 2. 按钮是否可用

```ts
const canSubmit = computed(() => {
  return form.title.trim() !== ''
    && form.content.trim() !== ''
    && !submitting.value
})
```

模板：

```vue
<button :disabled="!canSubmit">
  提交
</button>
```

### 3. 展示文案

```ts
const submitText = computed(() => {
  return submitting.value ? '提交中...' : '提交'
})
```

模板：

```vue
<button>{{ submitText }}</button>
```

### 4. 统计结果

```ts
const totalLikes = computed(() => {
  return posts.value.reduce((sum, post) => {
    return sum + post.likes
  }, 0)
})
```

`computed` 的判断标准很简单：

```text
如果一个值能从已有状态算出来，它通常就应该是 computed
```

## 十、computed 不适合做什么

`computed` 应该尽量保持纯粹：输入是响应式依赖，输出是计算结果。

不推荐在 `computed` 中做副作用：

```ts
const filteredPosts = computed(() => {
  localStorage.setItem('keyword', keyword.value)

  return posts.value.filter((post) => {
    return post.title.includes(keyword.value)
  })
})
```

这段代码的问题是：`computed` 本来应该只负责算 `filteredPosts`，现在却偷偷写了本地存储。以后别人读取 `filteredPosts` 时，可能会意外触发写入行为。

不推荐在 `computed` 中发请求：

```ts
const userInfo = computed(async () => {
  return await fetchUser(userId.value)
})
```

异步请求属于副作用，应该放到 `watch`、生命周期或组合函数里。

`computed` 更适合：

```text
根据已有状态计算一个同步结果
```

不适合：

```text
发请求
写缓存
改其他状态
操作 DOM
```

这些事情交给 `watch` 或生命周期。

## 十一、可写 computed

大多数 `computed` 是只读的：

```ts
const fullName = computed(() => {
  return `${firstName.value} ${lastName.value}`
})
```

有时你也可以定义可写的 `computed`：

```ts
const fullName = computed({
  get() {
    return `${firstName.value} ${lastName.value}`
  },
  set(value: string) {
    const [first, last] = value.split(' ')
    firstName.value = first ?? ''
    lastName.value = last ?? ''
  }
})
```

模板：

```vue
<input v-model="fullName">
```

不过初学阶段不要急着用可写 `computed`。它适合封装表单字段转换、组件 `v-model` 等场景。一般页面逻辑中，只读 `computed` 更常见，也更容易维护。

## 十二、watch：响应状态变化后做副作用

`watch` 用来监听响应式数据变化，然后执行副作用。

```ts
import { watch } from 'vue'

watch(keyword, (newValue, oldValue) => {
  console.log('新关键字：', newValue)
  console.log('旧关键字：', oldValue)
})
```

副作用是指：不只是计算一个结果，而是会对外部世界或其他状态产生影响的行为。

常见副作用：

- 发请求。
- 写 `localStorage`。
- 打日志。
- 操作浏览器 API。
- 调用第三方库。
- 根据状态变化重置另一个状态。

比如关键字变化后写入本地存储：

```ts
watch(keyword, (value) => {
  localStorage.setItem('post-keyword', value)
})
```

比如页码或搜索条件变化后重新请求列表：

```ts
watch([page, keyword], () => {
  loadPosts()
})
```

这里 `watch` 的含义是：

```text
当 page 或 keyword 变化后，执行 loadPosts
```

## 十三、watch 监听 ref、getter 和多个来源

监听 `ref`：

```ts
watch(keyword, (value) => {
  console.log(value)
})
```

监听响应式对象的某个字段时，推荐用 getter：

```ts
watch(
  () => form.title,
  (title) => {
    console.log(title)
  }
)
```

监听多个来源：

```ts
watch([page, keyword], ([newPage, newKeyword], [oldPage, oldKeyword]) => {
  console.log(newPage, newKeyword)
  console.log(oldPage, oldKeyword)
})
```

监听一个计算结果：

```ts
watch(
  () => keyword.value.trim(),
  (text) => {
    console.log(text)
  }
)
```

这类 getter 很有用，因为它能明确告诉 Vue：你要监听的到底是什么。

## 十四、watch 的 immediate、deep 和 flush

`watch` 常见配置有几个。

### 1. immediate

默认情况下，`watch` 只有在监听目标变化后才执行。

如果希望创建监听时先执行一次：

```ts
watch(
  keyword,
  () => {
    loadPosts()
  },
  {
    immediate: true
  }
)
```

常见场景是进入页面时立即请求一次，后续条件变化时再重新请求。

### 2. deep

监听对象内部深层变化时，可以使用 `deep`：

```ts
watch(
  form,
  () => {
    console.log('表单变化了')
  },
  {
    deep: true
  }
)
```

不过 `deep` 要谨慎。对象很大时，深度监听成本更高，而且依赖关系不够清楚。

更推荐监听明确字段：

```ts
watch(
  () => [form.title, form.content],
  () => {
    console.log('标题或内容变化了')
  }
)
```

### 3. flush

`flush` 控制回调执行时机。

常用理解：

| 配置 | 含义 | 常见场景 |
| ---- | ---- | -------- |
| `pre` | 组件 DOM 更新前执行，默认值 | 普通副作用 |
| `post` | 组件 DOM 更新后执行 | 需要读取更新后的 DOM |
| `sync` | 状态变化后同步执行 | 极少数需要立即同步处理的场景 |

大部分业务代码不用改 `flush`。只有当你需要在状态变化后读取最新 DOM 时，才考虑：

```ts
watch(
  visible,
  () => {
    console.log(panelRef.value?.offsetHeight)
  },
  {
    flush: 'post'
  }
)
```

## 十五、watch 中处理异步请求

搜索框变化后请求接口，是 `watch` 常见场景：

```ts
watch(keyword, async (value) => {
  posts.value = await searchPosts(value)
})
```

但这里有一个真实问题：请求可能乱序返回。

比如用户依次输入：

```text
v
vu
vue
```

可能 `vue` 的请求先返回，`v` 的请求后返回。最后页面反而显示旧结果。

可以用 `onCleanup` 清理过期请求：

```ts
watch(keyword, async (value, _oldValue, onCleanup) => {
  const controller = new AbortController()

  onCleanup(() => {
    controller.abort()
  })

  const result = await fetch(`/api/posts?keyword=${value}`, {
    signal: controller.signal
  })

  posts.value = await result.json()
})
```

每次 `keyword` 变化时，上一次 watch 回调会被清理。这样可以取消旧请求，避免旧结果覆盖新结果。

如果你的请求库不支持取消，也可以用递增编号：

```ts
let requestId = 0

watch(keyword, async (value) => {
  const currentId = ++requestId
  const result = await searchPosts(value)

  if (currentId !== requestId) {
    return
  }

  posts.value = result
})
```

异步副作用是最容易出错的地方之一。不是因为它难看，而是因为它太像“应该没问题”。

## 十六、watchEffect：自动收集依赖

`watchEffect` 也能处理副作用，但它和 `watch` 的依赖收集方式不同。

`watch` 是显式指定监听目标：

```ts
watch(keyword, () => {
  loadPosts()
})
```

`watchEffect` 是自动收集回调中读取到的响应式依赖：

```ts
watchEffect(() => {
  console.log(keyword.value)
  console.log(page.value)
})
```

这里读取了 `keyword.value` 和 `page.value`，所以任意一个变化都会重新执行。

`watchEffect` 适合：

- 调试响应式依赖。
- 组合函数内部做简单同步。
- 依赖很多但逻辑很短的场景。

比如：

```ts
watchEffect(() => {
  document.title = keyword.value
    ? `搜索：${keyword.value}`
    : '文章列表'
})
```

但业务请求更推荐 `watch`：

```ts
watch([page, keyword], () => {
  loadPosts()
}, {
  immediate: true
})
```

因为 `watch` 的依赖更明确。一个月后再看代码时，你能直接看出是什么变化触发了请求。代码最好不要靠读者猜，读者也没有欠它什么。

## 十七、computed、watch 和 watchEffect 怎么选

这是响应式 API 中最重要的判断。

| 需求 | 推荐 |
| ---- | ---- |
| 根据已有状态算一个值 | `computed` |
| 状态变化后发请求 | `watch` |
| 状态变化后写本地存储 | `watch` |
| 状态变化后操作 DOM 或第三方库 | `watch` 或生命周期 |
| 自动追踪一小段副作用依赖 | `watchEffect` |
| 页面挂载时加载数据 | `onMounted` 或 `watch(..., { immediate: true })` |
| 模板里展示过滤结果、统计结果、按钮状态 | `computed` |

再压缩一点：

```text
computed：我要一个值
watch：某个状态变了，我要做一件事
watchEffect：这段逻辑用到了什么响应式数据，就自动跟着它们变化
```

错误用法通常长这样：

```ts
watch(keyword, () => {
  filteredPosts.value = posts.value.filter(...)
})
```

如果 `filteredPosts` 只是由 `keyword` 和 `posts` 算出来，应该用 `computed`。

正确：

```ts
const filteredPosts = computed(() => {
  return posts.value.filter(...)
})
```

另一个错误用法：

```ts
const user = computed(async () => {
  return await fetchUser(userId.value)
})
```

请求是副作用，应该用 `watch`：

```ts
watch(userId, async (id) => {
  user.value = await fetchUser(id)
}, {
  immediate: true
})
```

## 十八、生命周期：在合适的时机做事

组合式 API 中常见生命周期函数：

```ts
import { onMounted, onUnmounted, onUpdated } from 'vue'
```

页面首次挂载后加载数据：

```ts
onMounted(() => {
  loadPosts()
})
```

组件卸载时清理资源：

```ts
let timer: number | undefined

onMounted(() => {
  timer = window.setInterval(() => {
    console.log('tick')
  }, 1000)
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})
```

`onUpdated` 会在组件因为响应式状态变化而更新 DOM 后执行：

```ts
onUpdated(() => {
  console.log('组件更新了')
})
```

它不适合随便放业务逻辑，因为组件可能频繁更新。更常见的做法是用 `watch` 精确监听某个状态。

生命周期适合处理：

- 页面进入时加载数据。
- 注册和清理事件监听。
- 创建和销毁第三方实例。
- 管理定时器、订阅、WebSocket 等外部资源。

## 十九、nextTick：等 DOM 更新完成

状态变化后，Vue 不一定立刻同步更新 DOM。它会把多次状态变化合并，然后在合适的时机更新视图。

如果你修改状态后马上读取 DOM，可能读到旧结果：

```ts
visible.value = true
console.log(panelRef.value?.offsetHeight)
```

可以使用 `nextTick` 等待 DOM 更新完成：

```ts
import { nextTick, ref } from 'vue'

const visible = ref(false)
const panelRef = ref<HTMLElement | null>(null)

async function openPanel() {
  visible.value = true
  await nextTick()
  console.log(panelRef.value?.offsetHeight)
}
```

模板：

```vue
<section v-if="visible" ref="panelRef">
  内容
</section>
```

`nextTick` 不是用来“修复响应式”的。它只是在你确实需要读取更新后的 DOM 时使用。

## 二十、组合式 API 到底组合了什么

组合式 API 的重点不是把 `data`、`methods` 换成 `ref`、`function`。它真正解决的是：**按业务逻辑组织代码**。

选项式 API 常见结构是：

```ts
export default {
  data() {
    return {
      keyword: '',
      posts: [],
      loading: false
    }
  },
  computed: {
    filteredPosts() {
      return this.posts.filter(...)
    }
  },
  methods: {
    loadPosts() {},
    submit() {}
  },
  mounted() {
    this.loadPosts()
  }
}
```

当页面很复杂时，同一个功能的代码会分散在 `data`、`computed`、`methods`、`mounted` 里。

组合式 API 的写法是：

```ts
const keyword = ref('')
const posts = ref<Post[]>([])
const loading = ref(false)

const filteredPosts = computed(() => {
  return posts.value.filter(...)
})

async function loadPosts() {
  loading.value = true
  try {
    posts.value = await fetchPosts()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPosts()
})
```

它允许你把同一个功能相关的状态、计算、方法和副作用放在一起。

更进一步，你可以把它提取成组合函数。

## 二十一、组合函数：把响应式逻辑提取出去

组合函数通常以 `use` 开头，比如 `usePosts`、`useLoading`、`useSearch`。

示例：封装文章搜索逻辑。

```ts
import { computed, ref } from 'vue'

type Post = {
  id: number
  title: string
  summary: string
}

export function usePostSearch(initialPosts: Post[]) {
  const keyword = ref('')
  const posts = ref<Post[]>(initialPosts)

  const filteredPosts = computed(() => {
    const text = keyword.value.trim().toLowerCase()

    if (!text) {
      return posts.value
    }

    return posts.value.filter((post) => {
      return post.title.toLowerCase().includes(text)
        || post.summary.toLowerCase().includes(text)
    })
  })

  return {
    keyword,
    posts,
    filteredPosts
  }
}
```

页面中使用：

```vue
<script setup lang="ts">
import { usePostSearch } from './composables/usePostSearch'

const { keyword, filteredPosts } = usePostSearch([
  { id: 1, title: 'Vue 响应式', summary: '状态驱动视图。' },
  { id: 2, title: '组合式 API', summary: '按逻辑组织代码。' }
])
</script>

<template>
  <input v-model="keyword">

  <article v-for="post in filteredPosts" :key="post.id">
    {{ post.title }}
  </article>
</template>
```

组合函数和普通工具函数不同。

普通工具函数通常是无状态的：

```ts
export function formatDate(value: string) {
  return value.slice(0, 10)
}
```

组合函数可以包含响应式状态：

```ts
const keyword = ref('')
const filteredPosts = computed(...)
watch(keyword, ...)
```

也可以包含生命周期：

```ts
onMounted(() => {
  loadPosts()
})
```

一句话：

```text
工具函数复用普通计算
组合函数复用响应式逻辑
```

## 二十二、封装 useLoading

加载状态是很常见的逻辑，可以封装成组合函数：

```ts
import { ref } from 'vue'

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

模板：

```vue
<button :disabled="loading" @click="submit">
  {{ loading ? '提交中...' : '提交' }}
</button>
```

这里 `useLoading` 封装的是：

- 一个响应式状态 `loading`。
- 一个负责切换状态的函数 `run`。
- 异步任务完成后自动恢复状态。

这就是组合函数的价值：把常见的响应式流程收起来，让页面代码更专注于业务。

## 二十三、toRef、toRefs、unref 和 readonly

除了核心的 `ref`、`reactive`、`computed`、`watch`，还有几个常见辅助 API。

### 1. toRef

`toRef` 可以把响应式对象的某个属性转成 `ref`，并保持连接：

```ts
import { reactive, toRef } from 'vue'

const form = reactive({
  title: '',
  content: ''
})

const title = toRef(form, 'title')

title.value = 'Vue'
console.log(form.title)
```

修改 `title.value` 会同步影响 `form.title`。

### 2. toRefs

`toRefs` 可以把响应式对象的所有属性转成 `ref`：

```ts
import { reactive, toRefs } from 'vue'

const form = reactive({
  title: '',
  content: ''
})

const { title, content } = toRefs(form)
```

适合在组合函数返回 `reactive` 对象的字段时使用。

### 3. unref

`unref` 用来读取可能是 `ref`、也可能是普通值的数据：

```ts
import { unref, type Ref } from 'vue'

function print(value: string | Ref<string>) {
  console.log(unref(value))
}
```

如果是 `ref`，返回 `.value`；如果不是，直接返回原值。

### 4. readonly

`readonly` 用来创建只读代理：

```ts
import { readonly, ref } from 'vue'

const count = ref(0)
const readonlyCount = readonly(count)
```

它适合在组合函数中只暴露读取能力，不希望外部随便修改内部状态。

```ts
export function useCounter() {
  const count = ref(0)

  function increment() {
    count.value++
  }

  return {
    count: readonly(count),
    increment
  }
}
```

这样外部可以读 `count`，但修改只能通过 `increment`。

## 二十四、shallowRef 和 shallowReactive

默认的 `ref` 和 `reactive` 会对对象内部做响应式处理。

有些场景不需要深层响应式，比如保存第三方库实例：

```ts
const editor = shallowRef<Editor | null>(null)
```

`shallowRef` 只追踪 `.value` 本身的变化，不深度追踪对象内部属性。

```ts
editor.value = createEditor()
```

这种替换会触发更新。

但如果修改：

```ts
editor.value!.options.theme = 'dark'
```

Vue 不会深度追踪这个内部变化。

常见使用场景：

- 第三方库实例。
- 大型不可变对象。
- 不希望 Vue 深度代理的复杂对象。

初学阶段不必主动使用它。只有当你明确知道“不需要深层响应式”时，再考虑。

## 二十五、响应式排错思路

页面没有按预期更新时，按这条链路查：

```text
源状态是否是响应式的
 -> 修改状态的方式是否正确
 -> 派生状态是否写成 computed
 -> 模板是否使用了正确的值
```

常见问题一：普通变量不是响应式。

```ts
let count = 0
```

应该改成：

```ts
const count = ref(0)
```

常见问题二：在 `<script setup>` 中忘了 `.value`。

```ts
count++
```

应该写：

```ts
count.value++
```

常见问题三：把 `reactive` 对象直接解构。

```ts
const { title } = form
```

应该使用：

```ts
const { title } = toRefs(form)
```

常见问题四：把派生状态手动存成另一份。

```ts
const filteredPosts = ref([])
```

如果它只是由 `posts` 和 `keyword` 算出来，应该写：

```ts
const filteredPosts = computed(() => {
  return posts.value.filter(...)
})
```

常见问题五：用 `computed` 做副作用。

```ts
const result = computed(() => {
  localStorage.setItem('keyword', keyword.value)
  return keyword.value
})
```

应该把副作用放进 `watch`：

```ts
watch(keyword, (value) => {
  localStorage.setItem('keyword', value)
})
```

## 二十六、练习讲解：实现搜索列表

这个练习要把响应式状态、派生状态、副作用和生命周期串起来。

实现目标：

- `keyword` 使用 `ref` 保存搜索关键字。
- `posts` 使用 `ref<Post[]>([])` 保存原始列表。
- `filteredPosts` 使用 `computed` 计算搜索结果。
- `emptyText` 使用 `computed` 计算空状态文案。
- `watch(keyword, ...)` 把关键字写入本地存储。
- `watch([page, keyword], ...)` 在页码和关键字变化时加载数据。
- `onMounted` 初始化文章数据。

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
import { computed, onMounted, reactive, ref, watch } from 'vue'

type Post = {
  id: number
  title: string
  summary: string
  tags: string[]
  likes: number
}

const STORAGE_KEY = 'vue-course-keyword'

const keyword = ref(localStorage.getItem(STORAGE_KEY) ?? '')
const loading = ref(false)
const posts = ref<Post[]>([])
const page = ref(1)

const form = reactive({
  title: '',
  summary: ''
})

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

const totalLikes = computed(() => {
  return filteredPosts.value.reduce((sum, post) => {
    return sum + post.likes
  }, 0)
})

const canCreate = computed(() => {
  return form.title.trim() !== ''
    && form.summary.trim() !== ''
    && !loading.value
})

const emptyText = computed(() => {
  return keyword.value.trim()
    ? '没有匹配文章。搜索条件并不会因为你期待它宽容就自动变宽。'
    : '暂无文章。'
})

watch(keyword, (value) => {
  localStorage.setItem(STORAGE_KEY, value)
  page.value = 1
})

watch([page, keyword], () => {
  loadPosts()
})

async function loadPosts() {
  loading.value = true

  try {
    await new Promise((resolve) => window.setTimeout(resolve, 300))

    posts.value = [
      {
        id: 1,
        title: 'ref 和 reactive 怎么选',
        summary: '基础类型优先 ref，需要整体替换的数据也适合 ref。',
        tags: ['vue', 'reactivity'],
        likes: 12
      },
      {
        id: 2,
        title: 'computed 为什么不是普通函数',
        summary: 'computed 会缓存结果，只在依赖变化后重新计算。',
        tags: ['computed'],
        likes: 18
      },
      {
        id: 3,
        title: 'watch 适合处理哪些副作用',
        summary: '请求、本地存储和第三方库同步都属于副作用。',
        tags: ['watch', 'effect'],
        likes: 9
      }
    ]
  } finally {
    loading.value = false
  }
}

function createPost() {
  if (!canCreate.value) {
    return
  }

  posts.value.unshift({
    id: Date.now(),
    title: form.title,
    summary: form.summary,
    tags: ['draft'],
    likes: 0
  })

  form.title = ''
  form.summary = ''
}

onMounted(() => {
  loadPosts()
})
</script>

<template>
  <main class="page">
    <h1>响应式搜索列表</h1>

    <section class="panel">
      <input v-model="keyword" placeholder="搜索标题、摘要或标签" />
      <p>当前结果总点赞数：{{ totalLikes }}</p>
    </section>

    <section class="panel">
      <input v-model="form.title" placeholder="文章标题" />
      <textarea v-model="form.summary" placeholder="文章摘要"></textarea>
      <button :disabled="!canCreate" @click="createPost">
        新增文章
      </button>
    </section>

    <p v-if="loading" class="state">加载中...</p>

    <p v-else-if="filteredPosts.length === 0" class="state">
      {{ emptyText }}
    </p>

    <section v-else class="list">
      <article v-for="post in filteredPosts" :key="post.id" class="card">
        <h2>{{ post.title }}</h2>
        <p>{{ post.summary }}</p>
        <div class="meta">
          <span v-for="tag in post.tags" :key="tag">{{ tag }}</span>
          <strong>{{ post.likes }} 次点赞</strong>
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
  font-size: 28px;
}

.panel {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}

input,
textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
}

textarea {
  min-height: 92px;
  resize: vertical;
}

button {
  justify-self: start;
  padding: 8px 12px;
  border: 1px solid #2563eb;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}

button:disabled {
  border-color: #94a3b8;
  background: #94a3b8;
  cursor: not-allowed;
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
  margin: 0;
  color: #475569;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 13px;
}

.meta strong {
  color: #475569;
  font-size: 13px;
}
</style>
```

### 3. 关键点解释

`keyword`、`loading`、`posts`、`page` 是源状态：

```ts
const keyword = ref('')
const loading = ref(false)
const posts = ref<Post[]>([])
const page = ref(1)
```

`filteredPosts`、`totalLikes`、`canCreate`、`emptyText` 是派生状态：

```ts
const filteredPosts = computed(...)
const totalLikes = computed(...)
const canCreate = computed(...)
const emptyText = computed(...)
```

它们不需要手动维护，只要依赖的源状态变化，就会得到新的结果。

`watch(keyword, ...)` 是副作用：

```ts
watch(keyword, (value) => {
  localStorage.setItem(STORAGE_KEY, value)
  page.value = 1
})
```

它不是为了算一个值，而是为了在关键字变化后写入本地存储，并重置页码。

`watch([page, keyword], ...)` 也是副作用：

```ts
watch([page, keyword], () => {
  loadPosts()
})
```

它表示页码或搜索关键字变化后重新加载列表。

`onMounted` 处理组件首次进入：

```ts
onMounted(() => {
  loadPosts()
})
```

整个页面的数据流是：

```text
用户输入 keyword
 -> keyword 变化
 -> filteredPosts 自动重新计算
 -> watch 把 keyword 写入 localStorage
 -> 模板自动显示新的 filteredPosts
```

这就是响应式页面的基本工作方式。

## 二十七、总结

学这一篇，最重要的不是背 API，而是分清责任：

- `ref`：创建一个响应式值。
- `reactive`：创建一个响应式对象。
- `computed`：根据已有状态计算一个新值，有缓存，适合派生状态。
- 普通函数：可以在模板中调用，但不会缓存，组件重新渲染时可能重复执行。
- `watch`：监听明确的状态变化，处理副作用。
- `watchEffect`：自动收集依赖，适合简单副作用和组合函数内部逻辑。
- 生命周期：在组件挂载、更新、卸载等时机做事。
- `nextTick`：等待 DOM 更新完成后再读取 DOM。
- 组合函数：把一组响应式状态、计算、方法和副作用封装起来复用。

最后再记住这一组判断：

```text
原始数据，用 ref 或 reactive
能从原始数据算出来，用 computed
状态变化后要做事，用 watch
多个页面都要复用的响应式逻辑，提成组合函数
```

这就是 Vue 组合式 API 的主线。API 名字很多，但别被它们吓到。大多数时候，你只是在回答一个朴素的问题：这段代码是在保存状态、计算状态、响应变化，还是复用一组逻辑？问题问对了，答案通常不会太难看。
