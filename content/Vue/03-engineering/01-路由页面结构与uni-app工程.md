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

## 十、练习

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

然后说明每个文件的职责。能说清职责，才有资格开始写代码。
