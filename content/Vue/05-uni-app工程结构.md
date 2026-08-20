+++
date = '2026-08-19T16:05:00+08:00'
draft = false
title = 'uni-app 工程结构：从 main.ts、App.vue 到 pages.json'
+++

uni-app 的目标是用 Vue 风格写跨端应用。同一套代码可以构建到 H5、微信小程序等平台。它不是“普通 Vue 加一点配置”，而是在 Vue 之上增加了页面配置、跨端组件、平台 API、条件编译和多端构建流程。

理解一个典型 uni-app 工程结构，要先看三个文件：`src/main.ts`、`src/App.vue`、`src/pages.json`。它们分别对应应用创建、全局生命周期和页面注册。

## 一、入口 main.ts

项目入口：

```ts
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

export function createApp() {
  const app = createSSRApp(App)
  app.use(createPinia())
  return { app }
}
```

这里做了两件事：

- 创建 Vue 应用实例。
- 安装 Pinia 状态管理。

uni-app 要求导出 `createApp`。这和普通 Vue Web 项目的 `createApp(App).mount('#app')` 不完全一样，因为 uni-app 需要适配不同平台的启动方式。

`createSSRApp` 并不意味着这个项目一定在做服务端渲染。uni-app 模板中常用它作为跨端创建应用的入口。

## 二、根组件 App.vue

`App.vue` 是应用根组件。项目中：

```ts
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'
import { useNotifyStore } from '@/stores/notify'
import { setUnauthorizedHandler } from '@/api/http'
```

`onLaunch` 中做了应用启动初始化：

```ts
onLaunch(async () => {
  const auth = useAuthStore()
  const ui = useUIStore()
  const notify = useNotifyStore()
  setUnauthorizedHandler(() => {
    auth.logout()
    ui.openLogin('default')
    uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
  })
  await auth.restore()
  if (auth.isLoggedIn) void notify.refresh()
})
```

这段逻辑很有工程价值：

- 注册全局 401 处理器。
- token 失效时清理登录态。
- 打开登录弹窗。
- 应用启动时尝试恢复登录态。
- 已登录时刷新消息状态。

它把全局初始化放在根组件，而不是分散到每个页面。这个边界是正确的。

## 三、pages.json

`pages.json` 是 uni-app 的页面配置文件。项目中声明了很多页面：

```json
{
  "pages": [
    {
      "path": "pages/index/index",
      "style": {
        "navigationStyle": "custom",
        "navigationBarTextStyle": "black",
        "navigationBarTitleText": "河北科技大学微墙"
      }
    }
  ]
}
```

每个页面一般对应：

```text
src/pages/index/index.vue
```

页面路径和文件路径要匹配。新增页面时，仅创建 `.vue` 文件通常不够，还要在 `pages.json` 中注册。

`globalStyle` 定义全局导航栏和背景：

```json
{
  "globalStyle": {
    "navigationBarTextStyle": "black",
    "navigationBarTitleText": "河北科技大学微墙",
    "navigationBarBackgroundColor": "#FFFFFF",
    "backgroundColor": "#F6F6F8"
  }
}
```

## 四、easycom 自动组件

项目配置了 `easycom`：

```json
{
  "easycom": {
    "autoscan": true,
    "custom": {
      "^Avatar$": "@/components/common/Avatar.vue",
      "^WaterfallCard$": "@/components/feed/WaterfallCard.vue",
      "^LoginModal$": "@/components/modals/LoginModal.vue"
    }
  }
}
```

这表示模板中可以直接使用：

```vue
<Avatar />
<WaterfallCard />
<LoginModal />
```

而不用在每个页面手动导入。当然项目中有些页面仍然显式 import 组件，这在复杂类型或 IDE 识别场景下也很常见。

easycom 的价值：

- 减少重复 import。
- 统一组件注册。
- 让跨页面基础组件使用更方便。

但不要把所有东西都塞进 easycom。业务强绑定、只在单页使用的组件，显式导入反而更清楚。

## 五、页面目录

项目页面目录：

```text
src/pages/
  index/
  hot/
  search/
  post-detail/
  user-profile/
  topic-detail/
  service/
  message/
  mine/
  edit-normal/
```

每个目录下通常有一个 `index.vue`。这种结构的好处是：

- 页面路径稳定。
- 后续可以在页面目录下放局部组件或工具。
- 和 `pages.json` 对应关系清楚。

例如：

```text
pages/post-detail/index
 -> src/pages/post-detail/index.vue
```

## 六、组件目录

组件按领域拆分：

```text
src/components/
  common/
  compose/
  feed/
  layout/
  modals/
  service/
  settings/
```

这是比“所有组件都放 components 下”更好的方式。

常见拆分标准：

| 目录 | 职责 |
| ---- | ---- |
| `common` | 通用基础组件 |
| `feed` | 信息流相关组件 |
| `compose` | 发布编辑相关组件 |
| `layout` | 布局组件 |
| `modals` | 弹窗 |
| `service` | 服务模块 |
| `settings` | 设置项组件 |

当组件目录越来越大时，按业务域拆分比按技术类型拆分更容易维护。

## 七、API 目录

项目 API 目录：

```text
src/api/
  http.ts
  post.api.ts
  user.api.ts
  topic.api.ts
  upload.api.ts
  message.api.ts
  service.api.ts
```

`http.ts` 是基础请求封装，业务 API 文件负责具体接口。

推荐调用链：

```text
页面/组件
 -> api/post.api.ts
   -> api/http.ts
     -> uni.request
```

不要在页面里随手写：

```ts
uni.request({ url: '/api/xxx' })
```

这会导致 token、错误处理、响应拆包、URL 拼接、loading 策略到处复制。复制一时爽，维护时就会很有教育意义。

## 八、models 目录

`src/models` 用于放业务类型：

```text
src/models/
  post.ts
  user.ts
  topic.ts
  notification.ts
  enums.ts
```

前端模型的作用：

- 描述接口返回数据。
- 给组件 props 提供类型。
- 给 store state 提供类型。
- 让 IDE 自动提示字段。
- 在接口变化时及时暴露编译错误。

后端字段变更时，前端模型也要同步更新。否则页面可能编译通过但运行异常，或者编译阶段直接报错。后者其实更好，因为越早失败越便宜。

## 九、stores 目录

项目使用 Pinia：

```text
src/stores/
  auth.ts
  feed.ts
  notify.ts
  ui.ts
  content-sync.ts
```

常见 store 职责：

| store | 职责 |
| ----- | ---- |
| `auth` | 登录态、用户资料、token 恢复 |
| `feed` | 首页帖子流、分页、点赞收藏状态 |
| `notify` | 消息状态 |
| `ui` | 弹窗、toast 等 UI 状态 |
| `content-sync` | 内容刷新标记 |

页面局部状态不必都放 store。只有跨页面共享、需要缓存、多个组件读写的状态，才适合放 Pinia。

## 十、router 目录

uni-app 的页面跳转通常使用 `uni.navigateTo`、`uni.switchTab` 等 API。项目封装了：

```text
src/router/navigator.ts
```

封装导航的好处：

- 统一路径拼接。
- 统一参数编码。
- 避免页面路径散落。
- 方便以后处理登录拦截或跳转策略。

比如：

```ts
navTo('/pages/search/index')
navPostDetail(props.post.id, props.post.author.seed)
```

路径是前端项目里很容易写错的东西。集中封装虽然看起来多一步，但比到处找字符串舒服得多。

## 十一、utils 目录

`src/utils` 放纯工具函数：

```text
format.ts
image.ts
share.ts
waterfall.ts
avatar.ts
hash.ts
```

例如首页瀑布流：

```ts
splitPostsIntoColumns(posts.value)
```

这个函数放在 `utils/waterfall.ts`，而不是写在页面里。原因很简单：页面应该组织业务流程，不应该塞太多算法细节。

工具函数适合：

- 格式化数字和时间。
- 图片 URL 判断。
- 瀑布流分列。
- 分享菜单封装。
- hash 和随机头像。

## 十二、styles 目录

项目有：

```text
src/styles/tokens.css
```

并在 `App.vue` 中引入：

```css
@import '@/styles/tokens.css';
```

全局样式变量应该放在这里，而不是每个组件各写一套颜色。

常见变量类型：

- 品牌色。
- 背景色。
- 文本色。
- 边框色。
- 阴影。
- 圆角。
- 字号。
- 间距。

工程越大，样式 token 越重要。否则同一个灰色会出现十几个相近值，最后没人知道哪个才是对的。

## 十三、uni API

uni-app 提供跨端 API，例如：

```ts
uni.request()
uni.showToast()
uni.getStorageSync()
uni.setStorageSync()
uni.removeStorageSync()
```

项目中 HTTP 层使用 `uni.request`：

```ts
uni.request({
  url: resolveApiUrl(path),
  method,
  header,
  data,
  success: (res) => {},
  fail: (err) => {},
})
```

登录态使用本地存储：

```ts
uni.setStorageSync(TOKEN_KEY, token)
uni.getStorageSync(TOKEN_KEY)
uni.removeStorageSync(TOKEN_KEY)
```

这些 API 在 H5、小程序、App 中有统一入口，但底层实现不同。跨端项目要优先使用 uni API，而不是直接使用浏览器的 `localStorage` 或 `fetch`。

## 十四、条件编译

uni-app 支持条件编译：

```ts
// #ifdef MP-WEIXIN
showWechatShareMenu()
// #endif
```

这表示这段代码只在微信小程序构建时生效。

常见平台标识：

| 标识 | 平台 |
| ---- | ---- |
| `H5` | 浏览器 H5 |
| `MP-WEIXIN` | 微信小程序 |
| `APP-PLUS` | App |

条件编译要少用、慎用。能用统一 API 解决，就不要拆平台逻辑。只有平台能力确实不同，才写条件编译。

## 十五、开发与构建

项目脚本：

```bash
npm run dev:h5
npm run dev:mp-weixin
npm run build:h5
npm run build:mp-weixin
```

开发 H5 适合快速调试页面和接口。微信小程序构建适合检查平台兼容、组件行为、分享能力和小程序限制。

提交前建议：

```bash
npm run type-check
npm run build:h5
```

如果改了小程序相关能力，再跑：

```bash
npm run build:mp-weixin
```

## 十六、目录演进建议

项目早期目录可以简单，但不要让所有内容永远堆在 `pages` 和 `components` 里。随着业务增长，可以按下面顺序演进：

```text
先按页面拆分
 -> 抽通用组件
 -> 抽业务组件
 -> 抽 API 模块
 -> 抽 Pinia store
 -> 抽 composable
 -> 沉淀 models 和 utils
```

判断一个逻辑该放哪里，可以看它依赖什么：

- 依赖页面生命周期：优先放页面或 composable。
- 依赖跨页面共享状态：优先放 Pinia。
- 只做数据转换：放 utils。
- 只描述接口调用：放 api。
- 只描述数据结构：放 models。

这样目录不是一开始就“设计得很复杂”，而是随着业务复杂度自然长出来。工程结构最怕两种极端：要么什么都不分，要么还没复杂就先抽象出一座迷宫。

## 十七、小结

uni-app 工程的主线很清楚：

- `main.ts` 创建应用并安装插件。
- `App.vue` 处理应用生命周期和全局初始化。
- `pages.json` 注册页面和导航样式。
- `pages` 放页面。
- `components` 放组件。
- `api` 放请求封装和业务接口。
- `models` 放类型模型。
- `stores` 放跨页面状态。
- `utils` 放纯工具函数。
- `styles` 放全局样式变量。

把这些目录职责记住，再看项目就不会迷路。前端工程也有自己的分层，只是它的边界不是 Controller、Service、Mapper，而是页面、组件、状态、接口和构建配置。
