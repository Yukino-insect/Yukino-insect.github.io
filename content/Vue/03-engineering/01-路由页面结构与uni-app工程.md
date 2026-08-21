+++
date = '2026-08-19T18:14:00+08:00'
draft = false
title = '路由、页面结构与 uni-app 工程：从单页到跨端应用'
+++

Vue 应用最终会被组织成一个个页面。组件解决局部展示和交互，页面解决业务流程，路由则负责把“用户要去哪里”翻译成“应用应该渲染哪个页面、携带哪些参数、允许不允许进入、进入之后如何回退”。

Web 项目常用 Vue Router。uni-app 项目通过 `pages.json` 声明页面，并使用 `uni.navigateTo`、`uni.redirectTo`、`uni.switchTab` 等 API 管理页面跳转。两者写法不同，但工程问题很相似：

- 页面入口在哪里。
- URL 或页面路径如何映射到页面文件。
- 参数从哪里来，应该传给谁。
- 页面能不能刷新、分享、回退。
- 权限、登录态、标题、布局这些页面级信息放在哪里。
- 页面和组件、API、store、组合函数之间的边界怎么划分。

如果这些问题没有想清楚，项目一开始也许能跑，后面就会出现很熟悉的场景：参数到处读，跳转到处写，权限判断散落在按钮、页面和接口回调里。到那时再说“重构一下”当然也可以，只是会比较辛苦。辛苦本身并不高贵，能避免就避免。

## 一、先建立路由的工程视角

路由不是简单的“地址对应组件”。在前端工程里，路由至少承担四类职责：

| 职责 | Web Vue Router | uni-app |
| ---- | ---- | ---- |
| 页面声明 | `routes` 配置 | `pages.json` |
| 页面渲染入口 | `<RouterView />` | 框架根据页面路径加载 |
| 页面跳转 | `router.push`、`router.replace` | `uni.navigateTo`、`uni.redirectTo`、`uni.switchTab` |
| 参数传递 | `params`、`query`、`state` | URL query、事件通道、store、本地缓存 |
| 页面级控制 | 路由守卫、`meta` | 生命周期、拦截封装、页面栈判断 |

路由设计的关键不是把配置写出来，而是确定页面边界。一个判断方式是：这个状态是否应该被用户刷新、复制链接、浏览器回退、页面分享感知到？

- 应该感知：放进路由，例如详情页 `id`、搜索页 `keyword`、分页页码、筛选条件。
- 不应该感知：放组件状态或页面状态，例如弹窗是否打开、某个输入框正在输入但还未提交。
- 多个页面都要用：考虑 store，例如登录用户信息、购物车数量、全局草稿。
- 跨端页面进入后才产生：uni-app 中可以考虑事件通道或 store，例如从列表页带一个完整对象到创建页预填。

URL 是应用状态的一部分。把该进 URL 的东西藏在组件里，用户一刷新就丢；把不该进 URL 的东西都塞进 URL，又会让路由变得又长又脆弱。能分清这两者，路由才算真正开始被你掌握。

## 二、Web 路由基本配置

Vue Router 的最小配置通常是这样：

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('@/pages/home/index.vue')
    },
    {
      path: '/posts/:id',
      component: () => import('@/pages/post-detail/index.vue')
    }
  ]
})
```

这里有几个值得注意的点。

第一，`path` 描述 URL 结构，`component` 描述这个地址命中的页面组件。页面组件通常放在 `pages` 或 `views` 目录，不建议和普通业务组件混在一起。

第二，`component: () => import(...)` 是懒加载写法。用户访问到对应页面时才加载这段页面代码。页面越多，这个写法越重要。否则首屏会把很多暂时用不到的页面一起打进入口包。

第三，路由表是一份页面协议。它应该稳定、清楚、可读，而不是临时拼凑出来的路径列表。路径一旦被用户收藏、被运营投放、被外部系统引用，就不只是前端内部实现了。

在 `main.ts` 中注册路由：

```ts
import { createApp } from 'vue'
import { router } from './router'
import App from './App.vue'

createApp(App)
  .use(router)
  .mount('#app')
```

在 `App.vue` 或布局组件中提供渲染出口：

```vue
<template>
  <RouterView />
</template>
```

`RouterView` 的含义是：当前 URL 命中的页面组件渲染在这里。没有它，路由配置只是配置，页面没有地方出现。

## 三、路由匹配顺序与动态路由

动态路由用于描述一类页面。例如文章详情页不是为每篇文章写一条路由，而是写成：

```ts
{
  path: '/posts/:id',
  name: 'post-detail',
  component: () => import('@/pages/post/detail.vue')
}
```

访问 `/posts/1` 时，`id` 是 `1`。访问 `/posts/200` 时，`id` 是 `200`。页面结构相同，数据不同。

在页面中读取：

```ts
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const postId = computed(() => {
  const value = Number(route.params.id)
  return Number.isFinite(value) ? value : 0
})
```

不要急着把 `route.params.id` 直接丢给 API。路由参数本质上来自 URL，是字符串，而且可能非法。页面层应该先做基本转换和校验，再把明确的业务参数传给 API：

```ts
if (!postId.value) {
  // 可以显示错误页，也可以跳回列表页
}

const post = await fetchPostDetail(postId.value)
```

还要注意匹配顺序。下面这个例子有问题：

```ts
const routes = [
  { path: '/posts/:id', component: () => import('@/pages/post/detail.vue') },
  { path: '/posts/create', component: () => import('@/pages/post/create.vue') }
]
```

如果路由器先匹配 `/posts/:id`，`/posts/create` 可能会被当成详情页，`id` 变成字符串 `create`。更稳妥的写法是把更具体的路由放在前面：

```ts
const routes = [
  { path: '/posts/create', component: () => import('@/pages/post/create.vue') },
  { path: '/posts/:id', component: () => import('@/pages/post/detail.vue') }
]
```

Vue Router 会对路径做自己的排序和评分，但工程上仍然建议把静态、具体的路由写在动态、宽泛的路由前面。让人一眼看懂，比事后解释框架规则更可靠。

## 四、params、query 和页面状态

路由参数主要有三类。

`params` 适合表达路径本身的一部分：

```text
/posts/42
```

对应：

```ts
const id = Number(route.params.id)
```

`query` 适合表达筛选、搜索、排序、分页这类可选状态：

```text
/posts?keyword=vue&page=2
```

读取方式：

```ts
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const keyword = computed(() => String(route.query.keyword ?? ''))
const page = computed(() => Number(route.query.page ?? 1))
```

更新查询条件时，可以使用 `router.push` 或 `router.replace`：

```ts
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

function search(keyword: string) {
  router.push({
    path: '/posts',
    query: {
      ...route.query,
      keyword,
      page: 1
    }
  })
}
```

如果用户每输入一个字都同步到 URL，更适合用 `replace`，避免浏览器历史记录塞满每次输入：

```ts
function syncKeyword(keyword: string) {
  router.replace({
    query: {
      ...route.query,
      keyword
    }
  })
}
```

`state` 则适合临时跳转数据，但它不应该成为关键业务数据的唯一来源。因为刷新、分享、跨端打开时，这类状态往往不可依赖。详情页需要 `id`，就把 `id` 放到路径里；需要展示的数据由页面进入后再请求。这样页面才是可恢复的。

一个简单判断：

- 详情页主键：用 `params`。
- 搜索条件、tab、排序、分页：用 `query`。
- 页面内弹窗、输入中状态：用组件状态。
- 登录用户、全局配置：用 store。
- 临时动画、局部展开折叠：不要放路由。

## 五、命名路由与跳转

直接写路径可以：

```ts
router.push(`/posts/${post.id}`)
```

但业务复杂后，命名路由会更稳：

```ts
const routes = [
  {
    path: '/posts/:id',
    name: 'post-detail',
    component: () => import('@/pages/post/detail.vue')
  }
]
```

跳转时：

```ts
router.push({
  name: 'post-detail',
  params: {
    id: post.id
  }
})
```

命名路由的好处是路径结构变化时，调用方不必到处拼字符串。例如你把 `/posts/:id` 改成 `/articles/:id`，很多跳转代码仍然可以保持不变。

模板中也可以使用：

```vue
<RouterLink
  :to="{ name: 'post-detail', params: { id: post.id } }"
>
  {{ post.title }}
</RouterLink>
```

`RouterLink` 适合普通导航，因为它会生成真实链接，也更利于浏览器行为、右键打开和可访问性。按钮适合提交、删除、打开弹窗这类命令。链接就是链接，按钮就是按钮，混用久了，页面行为会变得含糊。

## 六、嵌套路由与布局

很多后台系统会有共同布局：侧边栏、顶部栏、内容区。此时可以用嵌套路由：

```ts
const routes = [
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/admin/dashboard'
      },
      {
        path: 'dashboard',
        component: () => import('@/pages/admin/dashboard.vue')
      },
      {
        path: 'posts',
        component: () => import('@/pages/admin/posts.vue')
      }
    ]
  }
]
```

`AdminLayout.vue` 中放二级出口：

```vue
<template>
  <div class="admin-layout">
    <aside>...</aside>
    <main>
      <RouterView />
    </main>
  </div>
</template>
```

这表示 `/admin` 这一层负责布局，`/admin/dashboard`、`/admin/posts` 这些子页面只负责内容区。

嵌套路由不是为了显得高级，而是为了避免每个页面重复写布局。判断是否需要嵌套，可以问三个问题：

- 这些页面是否共享同一个外壳。
- 切换子页面时外壳是否应该保持。
- 权限、导航菜单、面包屑是否属于同一个区域。

如果答案基本是肯定的，就适合嵌套路由。如果只是两个页面恰好长得像，先用组件复用即可，不必急着引入路由层级。

## 七、路由 meta 与页面级信息

路由 `meta` 适合放页面级静态信息：

```ts
const routes = [
  {
    path: '/posts/create',
    name: 'post-create',
    component: () => import('@/pages/post/create.vue'),
    meta: {
      title: '发布文章',
      requiresAuth: true,
      roles: ['editor', 'admin']
    }
  }
]
```

常见用途：

- 页面标题。
- 是否需要登录。
- 需要哪些角色。
- 使用哪个布局。
- 是否缓存页面。
- 是否在菜单中展示。

例如统一设置页面标题：

```ts
router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : '默认标题'
  document.title = title
})
```

`meta` 不适合放会频繁变化的业务数据。它是路由记录的附加说明，不是状态管理工具。把文章详情数据塞进 `meta`，就像把饭菜倒进抽屉里，倒也不是完全放不进去，只是后果会比较明显。

## 八、路由守卫怎么写才克制

登录校验通常写在全局前置守卫：

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

角色校验可以继续放在守卫里：

```ts
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const roles = Array.isArray(to.meta.roles) ? to.meta.roles : []

  if (!roles.length) {
    return
  }

  const allowed = roles.some((role) => authStore.roles.includes(role))

  if (!allowed) {
    return '/403'
  }
})
```

但守卫要克制。它适合处理页面级准入，不适合写大量业务流程。

适合放守卫：

- 未登录不能进入。
- 没有角色不能进入。
- 页面标题、埋点这类页面级副作用。
- 某些页面进入前必须确认全局配置已加载。

不适合放守卫：

- 文章详情数据请求。
- 表单草稿保存。
- 页面内部 tab 切换。
- 按钮权限的细粒度展示。
- 复杂业务审批逻辑。

一个实用原则：守卫决定“能不能进这个页面”，页面决定“进来后做什么”。如果把“进来后做什么”全塞进守卫，调试时你会发现页面还没出现，逻辑已经绕了半天。那不是深奥，是麻烦。

## 九、刷新、404 与 history 模式

Vue Router 常见两种 history：

```ts
createWebHistory()
createWebHashHistory()
```

`createWebHistory()` 的 URL 更自然：

```text
https://example.com/posts/1
```

但服务器需要把前端路由回退到 `index.html`。否则用户刷新 `/posts/1` 时，服务器会以为你真的要访问 `/posts/1` 这个静态文件，结果返回 404。

Nginx 常见配置：

```text
location / {
  try_files $uri $uri/ /index.html;
}
```

`createWebHashHistory()` 的 URL 会带 `#`：

```text
https://example.com/#/posts/1
```

它对服务器要求低，因为 `#` 后面的内容不会发给服务器。但 URL 可读性差一些。后台系统、内网工具、静态托管限制较多时可以考虑 hash；面向用户的 Web 应用一般优先 history，并配好服务端回退。

404 页面也应该显式配置：

```ts
{
  path: '/:pathMatch(.*)*',
  name: 'not-found',
  component: () => import('@/pages/error/not-found.vue')
}
```

把它放在路由表最后。未知路径应该有明确兜底，不应该落到一个莫名其妙的页面里。

## 十、页面组件应该做什么

页面组件是路由命中的入口，它不应该只是大号组件，也不应该变成所有逻辑的仓库。

页面适合负责：

- 读取并校验路由参数。
- 调用组合函数组织页面状态。
- 调用 API 或 store action 加载数据。
- 处理 loading、empty、error。
- 组织页面布局和业务流程。
- 把数据传给展示组件。

页面不适合负责：

- 直接拼很多底层请求细节。
- 写大量纯数据格式化逻辑。
- 管理跨页面共享状态的全部细节。
- 承担多个不相关业务模块。

一个详情页可以这样组织：

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchPostDetail } from '@/api/post'
import type { PostDetail } from '@/models/post'

const route = useRoute()
const router = useRouter()

const post = ref<PostDetail | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const postId = computed(() => Number(route.params.id))

async function loadPost() {
  if (!Number.isFinite(postId.value)) {
    router.replace('/404')
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    post.value = await fetchPostDetail(postId.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadPost)
</script>
```

这里的边界很清楚：页面读取路由，API 接收 `id`，展示组件接收 `post`。API 不知道路由是什么，组件也不需要知道页面参数从哪里来。

## 十一、uni-app 的页面配置

uni-app 不使用 Vue Router 作为页面路由核心，而是通过 `pages.json` 声明页面：

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

对应文件通常是：

```text
pages/
  index/
    index.vue
  post/
    detail.vue
```

`pages` 数组里的第一项通常是应用入口页。这个顺序很重要，不要随便调整。入口页变了，应用打开后的第一屏也会变。

页面路径不带 `.vue` 后缀，路径开头也通常不写 `/`。跳转时则经常写成：

```ts
uni.navigateTo({
  url: '/pages/post/detail?id=1'
})
```

注意这里有一点容易混淆：

- `pages.json` 里写 `"path": "pages/post/detail"`。
- 跳转 API 里写 `url: "/pages/post/detail?id=1"`。

配置是声明页面，跳转是访问页面。两者形式略有差异，记住即可，不必假装它很优雅。工程里有些东西就是这样，朴素地记住比强行解释更省事。

## 十二、uni-app 的 tabBar、分包和页面结构

小程序和 App 常见底部 tab，需要在 `pages.json` 里配置 `tabBar`：

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
      "path": "pages/profile/index",
      "style": {
        "navigationBarTitleText": "我的"
      }
    }
  ],
  "tabBar": {
    "list": [
      {
        "pagePath": "pages/index/index",
        "text": "首页"
      },
      {
        "pagePath": "pages/profile/index",
        "text": "我的"
      }
    ]
  }
}
```

tab 页面只能用 `uni.switchTab` 跳转：

```ts
uni.switchTab({
  url: '/pages/profile/index'
})
```

普通 `navigateTo` 不能跳到 tabBar 页面。这是很多人第一次写 uni-app 时会踩的坑。不是你的代码玄学，是 API 规则如此。

页面多了以后，可以使用分包：

```json
{
  "pages": [
    {
      "path": "pages/index/index"
    }
  ],
  "subPackages": [
    {
      "root": "packages/post",
      "pages": [
        {
          "path": "detail",
          "style": {
            "navigationBarTitleText": "文章详情"
          }
        }
      ]
    }
  ]
}
```

分包页面路径：

```ts
uni.navigateTo({
  url: '/packages/post/detail?id=1'
})
```

分包的目的主要是控制小程序首包体积。首页、登录、核心 tab 放主包；低频页面、复杂模块、活动页可以放分包。不要为了“看起来架构复杂”而分包，分包也是有维护成本的。

## 十三、uni-app 页面生命周期

uni-app 页面有自己的生命周期：

```ts
import { onLoad, onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'

onLoad((query) => {
  postId.value = Number(query.id)
  loadPost()
})

onShow(() => {
  refreshIfNeeded()
})

onPullDownRefresh(async () => {
  await loadPost()
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  loadMoreComments()
})
```

常见含义：

| 生命周期 | 触发时机 | 常见用途 |
| ---- | ---- | ---- |
| `onLoad` | 页面首次加载 | 读取参数、初始化请求 |
| `onShow` | 页面显示 | 返回页面后刷新、恢复状态 |
| `onHide` | 页面隐藏 | 暂停计时、停止轮询 |
| `onUnload` | 页面销毁 | 清理资源 |
| `onPullDownRefresh` | 下拉刷新 | 重新加载列表或详情 |
| `onReachBottom` | 滚动到底部 | 分页加载 |

Vue 的 `onMounted` 关注组件挂载，uni-app 的 `onLoad` 关注页面进入。两者可以同时存在，但语义不同。

一个常见做法是：

- 页面参数读取放 `onLoad`。
- 需要每次显示都刷新的轻量逻辑放 `onShow`。
- 组件内部 DOM 相关逻辑放 Vue 生命周期。
- 下拉刷新和触底加载放 uni-app 页面生命周期。

不要把所有请求都放 `onShow`。从详情页返回列表时刷新当然合理，但页面每显示一次都重刷重请求，可能会造成闪烁、重复请求和滚动位置丢失。刷新策略要看业务，不要把生命周期当成万能按钮。

## 十四、uni-app 跳转方式与页面栈

uni-app 常见跳转 API：

```ts
uni.navigateTo({
  url: '/pages/post/detail?id=1'
})
```

`navigateTo` 会保留当前页面，打开新页面。适合列表进入详情、详情进入编辑这类需要返回的场景。

```ts
uni.redirectTo({
  url: '/pages/login/index'
})
```

`redirectTo` 会关闭当前页面并跳转。适合提交成功后不希望用户回到提交页，或者登录流程中替换中间页。

```ts
uni.reLaunch({
  url: '/pages/index/index'
})
```

`reLaunch` 会关闭所有页面并打开某个页面。适合退出登录、切换租户、初始化失败后回首页这类重置应用栈的场景。

```ts
uni.navigateBack({
  delta: 1
})
```

`navigateBack` 返回上一页。`delta` 表示返回几层。

```ts
uni.switchTab({
  url: '/pages/index/index'
})
```

`switchTab` 用于 tabBar 页面。

简单对比：

| API | 是否保留当前页 | 能否跳 tabBar | 常见场景 |
| ---- | ---- | ---- | ---- |
| `navigateTo` | 是 | 否 | 列表到详情 |
| `redirectTo` | 否 | 否 | 表单提交后替换页面 |
| `reLaunch` | 清空全部 | 可以 | 退出登录、重置首页 |
| `navigateBack` | 返回已有页面 | 不涉及 | 返回上一页 |
| `switchTab` | 切换 tab | 是 | 首页、我的、消息 |

uni-app 有页面栈概念。页面一层层 `navigateTo` 会进入栈中，返回时从栈顶退出。小程序平台通常有页面栈层数限制，所以不要无限 `navigateTo`。比如从列表页进入详情页，再从详情页进入另一个详情页，如果没有控制，很容易堆出很深的页面栈。

可以查看当前页面栈：

```ts
const pages = getCurrentPages()
const currentPage = pages[pages.length - 1]

console.log(currentPage?.route)
```

页面栈 API 可以用于调试或少量兜底判断，但不要让业务流程过度依赖它。页面路径和跳转策略应该尽量清楚，而不是靠“猜当前栈里有什么”来决定。

## 十五、uni-app 参数传递

最常见的是 query：

```ts
uni.navigateTo({
  url: `/pages/post/detail?id=${post.id}`
})
```

接收：

```ts
onLoad((query) => {
  const id = Number(query.id)
})
```

参数包含中文、空格、特殊符号时要编码：

```ts
const keyword = encodeURIComponent(searchText.value)

uni.navigateTo({
  url: `/pages/search/index?keyword=${keyword}`
})
```

接收时解码：

```ts
onLoad((query) => {
  const keyword = decodeURIComponent(String(query.keyword ?? ''))
})
```

不要在 URL 里传复杂对象：

```ts
// 不推荐
uni.navigateTo({
  url: `/pages/post/detail?post=${JSON.stringify(post)}`
})
```

对象一大，URL 会变长；对象里有特殊字符，还要处理编码；数据过期时，也不容易保证一致性。详情页通常只传 `id`，然后进入页面后请求详情。

如果确实需要传比较复杂的临时数据，可以考虑：

- 用 store 暂存，目标页进入后读取。
- 用本地缓存临时保存草稿。
- App 和小程序支持的场景下使用事件通道。
- 只传必要字段，不传完整后端对象。

例如用 store 暂存创建页草稿：

```ts
const draftStore = useDraftStore()

draftStore.setPostDraft({
  title: title.value,
  content: content.value
})

uni.navigateTo({
  url: '/pages/post/preview'
})
```

目标页读取 store：

```ts
const draftStore = useDraftStore()
const draft = computed(() => draftStore.postDraft)
```

这种方式不能替代关键业务参数。预览草稿可以这么做，文章详情主键就不该这么做。

## 十六、封装跳转，别让路径散落

小项目里直接写跳转路径没有问题：

```ts
uni.navigateTo({
  url: `/pages/post/detail?id=${id}`
})
```

但项目变大后，同一个页面路径可能出现在很多文件里。一旦路径调整，就要全项目搜索替换。更稳的方式是集中封装：

```ts
export const pages = {
  postDetail(id: number) {
    return `/pages/post/detail?id=${id}`
  },
  postCreate() {
    return '/pages/post/create'
  },
  home() {
    return '/pages/index/index'
  }
}
```

使用：

```ts
uni.navigateTo({
  url: pages.postDetail(post.id)
})
```

也可以继续封装跳转动作：

```ts
export function openPostDetail(id: number) {
  return uni.navigateTo({
    url: pages.postDetail(id)
  })
}
```

封装到哪一层取决于项目规模。路径常量解决“路径散落”，动作函数解决“跳转方式散落”。如果一个页面有固定跳转方式，例如详情页永远 `navigateTo`，封装动作会很清晰。如果某个路径有时 `redirectTo`、有时 `navigateTo`，只封装路径更灵活。

## 十七、uni-app 中的登录拦截

uni-app 没有完全等同于 Vue Router `beforeEach` 的统一页面守卫。常见做法是封装跳转函数，在跳转前做登录判断：

```ts
const authPages = [
  '/pages/post/create',
  '/pages/profile/index'
]

function isAuthPage(url: string) {
  return authPages.some((page) => url.startsWith(page))
}

export function navigateTo(url: string) {
  const authStore = useAuthStore()

  if (isAuthPage(url) && !authStore.loggedIn) {
    return uni.navigateTo({
      url: `/pages/login/index?redirect=${encodeURIComponent(url)}`
    })
  }

  return uni.navigateTo({ url })
}
```

登录成功后：

```ts
onLoad((query) => {
  redirectUrl.value = decodeURIComponent(String(query.redirect ?? ''))
})

function afterLogin() {
  if (redirectUrl.value) {
    uni.redirectTo({
      url: redirectUrl.value
    })
    return
  }

  uni.switchTab({
    url: '/pages/index/index'
  })
}
```

这个封装只能管住通过你封装函数发起的跳转。对于用户直接打开某个页面、小程序分享进入、扫码进入等场景，目标页面自身也要做必要校验：

```ts
onLoad(() => {
  const authStore = useAuthStore()

  if (!authStore.loggedIn) {
    uni.redirectTo({
      url: '/pages/login/index'
    })
  }
})
```

也就是说，封装跳转负责体验，页面校验负责兜底。只做前者会漏，只有后者体验会生硬。两者配合，才像一个认真写过的应用。

## 十八、目录结构怎么设计

小到中型项目可以使用技术分层：

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

- `pages`：页面入口，接收路由参数，组织业务流程。
- `components`：可复用组件，关注展示和局部交互。
- `api`：接口请求，输入业务参数，返回业务数据。
- `models`：类型定义，表达前后端数据契约。
- `stores`：跨页面共享状态。
- `composables`：可复用组合逻辑。
- `utils`：无状态工具函数。
- `styles`：全局样式、变量和混入。

当业务模块变多，可以按 feature 收拢：

```text
src/
  pages/
    post/
      list.vue
      detail.vue
      create.vue
  features/
    post/
      api.ts
      model.ts
      store.ts
      composables/
        usePostList.ts
      components/
        PostCard.vue
      index.ts
  shared/
    components/
    utils/
    styles/
```

`pages/post/detail.vue` 是路由入口，`features/post` 是文章业务能力，`shared` 是跨业务复用代码。

页面可以依赖 feature：

```ts
import { fetchPostDetail, PostCard } from '@/features/post'
```

但 feature 内部不应该反过来依赖某个具体页面。否则业务模块会被页面绑死，复用和测试都会变困难。

当你不知道代码放哪里时，先问：

- 它是否直接依赖路由参数或页面生命周期？是的话，多半在页面。
- 它是否只是展示一块 UI？是的话，多半在组件。
- 它是否跨页面共享？是的话，考虑 store。
- 它是否是某个业务领域的请求或类型？是的话，放到对应 feature。
- 它是否和任何业务都无关？是的话，放 shared 或 utils。

目录结构不是为了让项目看起来整齐，而是为了让修改时少猜。工程的尊严大概就在这里，不华丽，但有用。

## 十九、easycom 自动导入

uni-app 支持 easycom 自动导入组件。配置后，符合规则的组件可以直接在模板里使用。

```json
{
  "easycom": {
    "autoscan": true,
    "custom": {
      "^Base(.*)": "@/components/base/Base$1.vue",
      "^Post(.*)": "@/features/post/components/Post$1.vue"
    }
  }
}
```

例如组件文件：

```text
components/
  base/
    BaseButton.vue
features/
  post/
    components/
      PostCard.vue
```

模板中可以直接写：

```vue
<template>
  <PostCard :post="post" />
</template>
```

easycom 能减少导入样板，但前提是命名规则清楚。组件名混乱时，自动导入只会自动制造混乱。

建议：

- 基础组件统一前缀，例如 `BaseButton`、`BaseEmpty`。
- 业务组件带业务名，例如 `PostCard`、`UserAvatar`。
- 不要让两个目录里出现同名组件。
- 自动导入规则写少一点，稳定一点。

组件不显式 import 以后，读代码的人更依赖命名判断来源。命名如果不可靠，维护体验会下降得很快。

## 二十、跨端条件编译

uni-app 支持条件编译：

```ts
// #ifdef H5
console.log('仅 H5 执行')
// #endif

// #ifdef MP-WEIXIN
console.log('仅微信小程序执行')
// #endif
```

也可以用于模板：

```vue
<template>
  <!-- #ifdef H5 -->
  <button @click="shareToBrowser">复制链接</button>
  <!-- #endif -->

  <!-- #ifdef MP-WEIXIN -->
  <button open-type="share">分享给好友</button>
  <!-- #endif -->
</template>
```

条件编译应该集中、克制。到处散落平台判断，会让代码很难维护。

推荐做法是把平台差异包在少数适配函数里：

```ts
export function getRuntimePlatform() {
  // #ifdef H5
  return 'h5'
  // #endif

  // #ifdef MP-WEIXIN
  return 'mp-weixin'
  // #endif

  // #ifdef APP-PLUS
  return 'app'
  // #endif

  return 'unknown'
}
```

页面中使用：

```ts
const platform = getRuntimePlatform()
```

对于 API、登录、分享、支付、上传这类平台差异明显的能力，尽量建立适配层：

```text
src/
  platform/
    share.ts
    upload.ts
    auth.ts
```

跨端不是“一套代码到处完美运行”，而是“一套代码在差异中尽量复用”。承认差异，然后控制差异的扩散范围，这才是跨端工程里比较实际的态度。

## 二十一、页面设计原则

页面、组件、API、store、组合函数之间的边界可以概括为：

- 页面负责组织业务流程。
- 组件负责展示和局部交互。
- API 模块负责请求。
- Store 负责跨页面状态。
- 组合函数负责复用逻辑。
- 工具函数负责纯数据处理。
- 路由配置负责页面入口和页面级元信息。

再具体一点：

| 逻辑 | 推荐位置 |
| ---- | ---- |
| 从 URL 读取文章 `id` | 页面 |
| 根据 `id` 请求文章详情 | 页面调用 API，或页面调用 store action |
| 请求函数如何拼接口地址 | API |
| 文章卡片怎么展示标题和摘要 | 组件 |
| 搜索关键词如何过滤列表 | 组合函数或页面 computed |
| 登录用户信息 | store |
| 数字格式化 | utils |
| 是否允许进入发布页 | 路由守卫或跳转封装加页面兜底 |

边界不是死规矩，而是降低理解成本的约定。约定稳定，团队就能少花时间猜代码在哪里。

## 二十二、常见错误

第一，把所有跳转路径散落在组件里。

```ts
uni.navigateTo({ url: '/pages/post/detail?id=1' })
```

项目小时没事，项目大了会很难改。可以集中封装页面路径。

第二，在组件里直接读路由并请求数据。

普通展示组件如果直接 `useRoute()`，它就被某个页面绑死了。更好的方式是页面读参数，请求数据，再把数据通过 props 传给组件。

第三，把所有接口结果都塞进 store。

store 适合跨页面共享，不是接口缓存垃圾桶。只在当前页面使用的数据，放页面状态即可。

第四，路由守卫里写太多业务逻辑。

守卫负责准入，页面负责流程。这个边界破了，调试会变得很不愉快。

第五，uni-app 里用错跳转 API。

tabBar 页面用 `switchTab`，普通页面用 `navigateTo`，提交后不想回退用 `redirectTo`，退出登录重置页面栈用 `reLaunch`。

第六，复杂对象通过 URL 传递。

URL 适合传稳定、短小、可恢复的状态。完整对象应该重新请求，或在临时场景中使用 store、缓存、事件通道。

## 二十三、练习讲解：设计并跑通文章模块目录

这个练习把前面的原则落到一个小项目里：文章列表、文章详情、发布文章。目标不是写一个多漂亮的页面，而是把路由、页面、组件、API、类型、组合函数的边界跑通。

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
    error/
      not-found.vue
  router.ts
  main.ts
  App.vue
```

这个目录采用技术分层，适合练习和中小项目。页面入口放 `pages`，文章卡片放 `components/post`，接口放 `api/post.ts`，类型放 `models/post.ts`，列表加载逻辑放 `composables/usePostList.ts`。

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

类型文件表达数据契约。列表页只需要 `PostCard`，详情页需要 `PostDetail`，创建接口需要 `CreatePostRequest`。不要所有地方都用一个巨大的 `Post` 类型，否则字段到底什么时候存在会变得含糊。

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

这里用内存数组模拟接口。真实项目中，`api/post.ts` 会调用 `request` 封装：

```ts
export function fetchPostDetail(id: number) {
  return request<PostDetail>(`/api/posts/${id}`)
}
```

API 层只关心请求和返回，不弹窗、不跳路由、不直接改组件状态。页面或 store 决定错误怎么展示、成功后跳到哪里。

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

组合函数把列表页的加载状态、错误状态、重试逻辑收拢起来。这样页面模板不需要关心请求细节，只需要渲染这些状态。

如果这个列表只在一个页面使用，也可以直接写在页面里。抽成组合函数的理由不是“所有逻辑都要抽”，而是它确实形成了一个可复用、可测试、可命名的行为单元。

### 6. 创建 `src/components/post/PostCard.vue`

```vue
<script setup lang="ts">
import type { PostCard } from '../../models/post'

defineProps<{
  post: PostCard
}>()
</script>

<template>
  <RouterLink class="card" :to="{ name: 'post-detail', params: { id: post.id } }">
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

`PostCard` 只负责展示文章卡片，并提供进入详情页的链接。它不请求列表，也不读取当前路由。这样同一个组件以后也可以放在搜索页、作者主页、推荐列表里。

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
      <RouterLink :to="{ name: 'post-create' }">发布文章</RouterLink>
    </header>

    <p v-if="loading">加载中...</p>

    <p v-else-if="errorMessage">
      {{ errorMessage }}
      <button @click="loadPosts">重试</button>
    </p>

    <section v-else-if="posts.length" class="list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
    </section>

    <p v-else>暂无文章</p>
  </main>
</template>
```

列表页的职责是组织列表流程：加载、失败、空状态、进入创建页。卡片怎么展示由 `PostCard` 负责。

`src/pages/post/detail.vue`

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchPostDetail } from '../../api/post'
import type { PostDetail } from '../../models/post'

const route = useRoute()
const router = useRouter()

const post = ref<PostDetail | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const postId = computed(() => Number(route.params.id))

async function loadPost() {
  if (!Number.isFinite(postId.value)) {
    router.replace({ name: 'not-found' })
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    post.value = await fetchPostDetail(postId.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadPost)
</script>

<template>
  <main class="page">
    <RouterLink :to="{ name: 'post-list' }">返回列表</RouterLink>

    <p v-if="loading">加载中...</p>
    <p v-else-if="errorMessage">{{ errorMessage }}</p>
    <p v-else-if="!post">文章不存在</p>

    <article v-else>
      <h1>{{ post.title }}</h1>
      <p>{{ post.content }}</p>
    </article>
  </main>
</template>
```

详情页读取 `route.params.id`，转换成数字，校验后调用 API。API 不知道 `route`，这点很重要。路由是页面入口的知识，不应该污染到请求层。

`src/pages/post/create.vue`

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createPost } from '../../api/post'

const router = useRouter()
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  title: '',
  content: ''
})

async function submit() {
  if (!form.title.trim() || !form.content.trim() || submitting.value) {
    return
  }

  submitting.value = true
  errorMessage.value = ''

  try {
    const post = await createPost({
      title: form.title.trim(),
      content: form.content.trim()
    })

    router.push({
      name: 'post-detail',
      params: {
        id: post.id
      }
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '提交失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>发布文章</h1>

    <form class="form" @submit.prevent="submit">
      <input v-model="form.title" placeholder="标题" />
      <textarea v-model="form.content" placeholder="内容" rows="6"></textarea>
      <p v-if="errorMessage">{{ errorMessage }}</p>
      <button :disabled="submitting">
        {{ submitting ? '提交中' : '提交' }}
      </button>
    </form>
  </main>
</template>
```

创建页提交成功后跳到详情页。这里使用命名路由，避免手写 `/posts/${post.id}` 这种路径字符串。

### 8. 创建 `src/router.ts`

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: { name: 'post-list' }
    },
    {
      path: '/posts',
      name: 'post-list',
      component: () => import('./pages/post/list.vue'),
      meta: {
        title: '文章列表'
      }
    },
    {
      path: '/posts/create',
      name: 'post-create',
      component: () => import('./pages/post/create.vue'),
      meta: {
        title: '发布文章',
        requiresAuth: true
      }
    },
    {
      path: '/posts/:id',
      name: 'post-detail',
      component: () => import('./pages/post/detail.vue'),
      meta: {
        title: '文章详情'
      }
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('./pages/error/not-found.vue')
    }
  ]
})

router.afterEach((to) => {
  document.title = typeof to.meta.title === 'string' ? to.meta.title : 'Vue Router Demo'
})
```

注意 `/posts/create` 放在 `/posts/:id` 前面。具体路径先写，动态路径后写，读起来也更清楚。

如果加了 `not-found` 页面，还需要创建 `src/pages/error/not-found.vue`：

```vue
<template>
  <main class="page">
    <h1>页面不存在</h1>
    <RouterLink :to="{ name: 'post-list' }">返回文章列表</RouterLink>
  </main>
</template>
```

### 9. 创建 `src/main.ts` 和 `src/App.vue`

`src/main.ts`

```ts
import { createApp } from 'vue'
import { router } from './router'
import './style.css'
import App from './App.vue'

createApp(App)
  .use(router)
  .mount('#app')
```

`src/App.vue`

```vue
<template>
  <RouterView />
</template>
```

`RouterView` 是路由页面出口。当前 URL 命中的页面会渲染到这里。

### 10. 样式可直接放到 `src/style.css`

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

### 11. 练习检查点

跑通后，逐项检查：

- `/posts` 能显示文章列表。
- 点击文章卡片能进入 `/posts/:id`。
- 详情页刷新后仍然能根据 URL 加载文章。
- `/posts/create` 能创建文章，并跳转到详情页。
- `/posts/create` 不会被 `/posts/:id` 错误匹配。
- 随便访问一个不存在的路径，会进入 404 页面。
- API 文件没有读取路由。
- 展示组件没有直接请求列表。

能跑通这些点，说明你不只是写了几个页面，而是理解了页面入口、参数来源、业务边界和路由行为之间的关系。这才是路由这部分真正要学的东西。

## 二十四、总结

Web 路由和 uni-app 页面配置看起来不同，本质都在解决页面组织问题。

Vue Router 的重点是 URL、路由表、`RouterView`、动态参数、query、嵌套路由、守卫和 history 部署。uni-app 的重点是 `pages.json`、页面生命周期、页面栈、跳转 API、tabBar、分包和跨端条件编译。

写项目时可以记住这几条：

- 页面入口必须清楚。
- 参数应该可恢复、可校验。
- 详情页主键放路径，搜索筛选放 query。
- 页面读路由，API 接收业务参数。
- 守卫管准入，页面管流程。
- tabBar 页面用 `switchTab`。
- uni-app 复杂对象不要硬塞 URL。
- 平台差异要收拢，不要散落。
- 目录结构服务于边界，不服务于表演。

路由不是教程里那几行配置。它是应用的骨架之一。骨架歪了，页面写得再热闹也只是暂时热闹；骨架清楚，后面的功能才有地方安放。
