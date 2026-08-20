+++
date = '2026-08-19T16:03:00+08:00'
draft = false
title = 'HTML 与 CSS 基础：页面结构、布局和样式系统'
+++

前端页面最终要解决两个问题：内容如何组织，以及内容如何呈现。HTML 负责结构，CSS 负责样式。即使在 uni-app 项目里你看到的是 `<view>`、`<text>`、`<scroll-view>`，背后的思想仍然离不开 HTML 和 CSS。

在跨端项目中，你可能不会大量直接使用 `<div>`、`<span>`，而是使用 uni-app 的 `<view>`、`<text>`、`scroll-view` 等组件。但从工程理解上看，你仍然需要掌握 HTML/CSS 的基本模型，否则很难判断一个页面为什么乱、为什么滚不动、为什么样式没生效。

## 一、HTML 的本质

HTML 是页面结构描述语言。它通过标签组织内容：

```html
<main>
  <section>
    <h2>帖子列表</h2>
    <article>
      <h3>标题</h3>
      <p>正文内容</p>
    </article>
  </section>
</main>
```

浏览器会把 HTML 解析成 DOM 树：

```text
main
 -> section
   -> h2
   -> article
     -> h3
     -> p
```

Vue 模板本质上也是在描述一棵界面树：

```vue
<template>
  <view class="app">
    <view class="topBar">
      <text class="topBar-title">{{ schoolTitle }}</text>
    </view>
  </view>
</template>
```

只是 uni-app 使用跨端组件，编译时会根据目标平台转换成对应平台能理解的结构。

## 二、常见 HTML 标签

普通 Web 中常见标签：

| 标签 | 作用 |
| ---- | ---- |
| `div` | 通用块级容器 |
| `span` | 通用行内容器 |
| `p` | 段落 |
| `a` | 链接 |
| `img` | 图片 |
| `button` | 按钮 |
| `input` | 输入框 |
| `form` | 表单 |
| `ul` / `li` | 列表 |
| `main` / `section` / `article` | 语义结构 |

uni-app 常见组件：

| uni-app 组件 | 类似 Web 标签 |
| ------------ | ------------- |
| `view` | `div` |
| `text` | `span` |
| `image` | `img` |
| `scroll-view` | 可滚动容器 |
| `button` | 按钮 |
| `input` | 输入框 |

注意这只是类比，不是完全等价。小程序组件有自己的限制和事件模型，不能把浏览器 DOM API 直接套进去。

## 三、CSS 的作用

CSS 控制视觉表现：

```css
.title {
  color: #222;
  font-size: 18px;
  font-weight: 600;
}
```

CSS 由选择器和声明组成：

```text
selector {
  property: value;
}
```

常见选择器：

```css
.card {}
#app {}
view {}
.card .title {}
.button.active {}
```

Vue 单文件组件中通常写：

```vue
<style scoped>
.feedFooter {
  text-align: center;
}
</style>
```

`scoped` 表示样式只作用于当前组件生成的结构，减少全局污染。

## 四、盒模型

CSS 盒模型是布局基础：

```text
content
padding
border
margin
```

示例：

```css
.card {
  width: 200px;
  padding: 12px;
  border: 1px solid #ddd;
  margin-bottom: 16px;
}
```

默认情况下，`width` 只表示内容区宽度。设置 `box-sizing: border-box` 后，`width` 包含 padding 和 border。

```css
* {
  box-sizing: border-box;
}
```

移动端布局里，`border-box` 更容易控制尺寸。

## 五、块级与行内

普通 HTML 中：

- `div` 是块级元素，默认占一整行。
- `span` 是行内元素，宽高不按块级方式生效。

uni-app 中 `view` 常作为块级容器，`text` 常用于文字。

项目首页中：

```vue
<view class="topBar-brand">
  <view class="topBar-logo">墙</view>
  <text class="topBar-title">{{ schoolTitle }}</text>
</view>
```

`view` 用于容器和图标块，`text` 用于文本。这样结构比较清楚。

## 六、Flex 布局

Flex 是移动端和组件布局最常用的方案。

```css
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
```

常用属性：

| 属性 | 作用 |
| ---- | ---- |
| `display: flex` | 开启 Flex 布局 |
| `flex-direction` | 主轴方向 |
| `align-items` | 交叉轴对齐 |
| `justify-content` | 主轴对齐 |
| `gap` | 子项间距 |
| `flex: 1` | 占据剩余空间 |
| `flex-shrink: 0` | 不被压缩 |

项目中点赞区域、标题栏、搜索栏都适合用 Flex。比如首页热榜行中，标题占剩余空间，热度靠右：

```vue
<text class="t">{{ h.title }}</text>
<text style="flex-shrink:0">{{ formatHeat(h.hot) }}</text>
```

核心思路是：让主要内容伸缩，让辅助信息保持稳定宽度。

## 七、Grid 布局

Grid 更适合二维布局，例如图片九宫格、卡片矩阵。

Web 中可以写：

```css
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
```

项目的 `ImageGrid.vue` 没有直接用 CSS Grid，而是使用 Flex 加固定宽度：

```css
.image-grid-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
}

.grid-item {
  width: calc((100% - 16px) / 3);
  padding-bottom: calc((100% - 16px) / 3);
}
```

这是跨端兼容考虑。某些小程序环境对部分 CSS 特性支持不稳定，使用 Flex 和百分比撑开正方形会更可靠。

## 八、定位

CSS 定位常用：

| 值 | 含义 |
| ---- | ---- |
| `static` | 默认定位 |
| `relative` | 相对定位，常作为绝对定位参照 |
| `absolute` | 绝对定位 |
| `fixed` | 相对视口固定 |
| `sticky` | 滚动到指定位置后吸附 |

项目首页 tab 使用 sticky：

```vue
<view class="chTabs" style="position:sticky; top:0; z-index:2">
</view>
```

这表示 tab 滚动到顶部后吸住，继续留在页面上。

图片删除按钮使用 absolute：

```css
.close-btn {
  position: absolute;
  top: 4px;
  right: 4px;
}
```

父元素 `.grid-item` 设置：

```css
position: relative;
```

这样删除按钮会相对于当前图片格子定位，而不是跑到页面角落。

## 九、滚动容器

普通 Web 页面滚动通常依赖浏览器窗口。uni-app 中常用 `scroll-view`：

```vue
<scroll-view
  class="scroller"
  scroll-y
  refresher-enabled
  :lower-threshold="120"
  @refresherrefresh="handleRefresh"
  @scrolltolower="handleLoadMore"
>
</scroll-view>
```

这里表达了几个行为：

- `scroll-y`：允许纵向滚动。
- `refresher-enabled`：开启下拉刷新。
- `lower-threshold`：距离底部多少像素触发触底。
- `refresherrefresh`：下拉刷新事件。
- `scrolltolower`：滚动到底事件。

这不是简单容器，而是页面交互状态的一部分。滚动、刷新、加载更多、loading、空状态，都应该一起设计。

## 十、CSS 变量

项目使用了全局样式变量，例如：

```css
color: var(--brand);
background: var(--bg-2);
color: var(--ink-3);
```

CSS 变量通常在全局 token 文件中定义：

```css
:root {
  --brand: #ff5a47;
  --bg-2: #f6f6f8;
  --ink-3: #8e8e96;
}
```

好处：

- 统一颜色和间距。
- 换主题时成本更低。
- 避免每个组件写一套颜色。
- 让设计语言稳定。

后端同学可以把它理解成前端的常量配置。区别只是这些常量作用在视觉层。

## 十一、scoped CSS

Vue 中：

```vue
<style scoped>
.title {
  color: red;
}
</style>
```

`scoped` 会让样式只作用于当前组件。它不是 Shadow DOM，而是编译器给元素和选择器加上特殊属性。

优点：

- 避免组件样式互相污染。
- 组件移动时样式更独立。
- 页面级样式和组件级样式边界更清楚。

但也要注意：

- 全局样式变量仍然可以使用。
- 深层子组件样式不是随便就能改。
- 过度依赖 scoped 不能替代合理命名。

## 十二、响应式尺寸

移动端页面不能写死太多像素宽度。常用方案：

- 百分比宽度。
- Flex 自适应。
- `calc()` 计算。
- `min-width`、`max-width` 限制。
- `aspect-ratio` 或 padding 撑比例。

项目 `WaterfallCard.vue` 中根据图片宽高计算 padding：

```ts
const coverPad = computed(() => {
  if (!first.value) return '0'
  return ((first.value.h / first.value.w) * 100).toFixed(2) + '%'
})
```

模板中：

```vue
<view class="cover" :style="{ paddingTop: coverPad }">
</view>
```

这是为了在图片加载前先占好比例，减少页面抖动。真实项目里这种细节很重要，因为内容流一抖，用户就会点错。

## 十三、图片显示

Web 中图片常用：

```html
<img src="/demo.png" alt="demo">
```

uni-app 中：

```vue
<image :src="url" mode="aspectFill" />
```

`mode="aspectFill"` 表示保持比例填满容器，多余部分裁剪。类似 Web 的：

```css
object-fit: cover;
```

项目中图片 URL 还会经过处理：

```ts
resolveRenderableImageUrl(first.url)
```

这是因为真实接口返回的图片路径可能是相对路径、后端文件路径、mock 路径或 data URL。统一处理后，组件不需要关心图片来源细节。

## 十四、表单和输入

表单不是只收集值，还要处理：

- 初始值。
- 输入校验。
- 禁用状态。
- 提交 loading。
- 错误提示。
- 成功后跳转或刷新。

在 Vue 中常用 `v-model` 做双向绑定：

```vue
<input v-model="form.title" />
```

uni-app 也支持类似写法，但不同组件事件细节可能不同。复杂表单建议把字段、校验、提交逻辑集中管理，不要散在模板里。

## 十五、CSS 常见问题

### 1. 文本溢出

单行省略：

```css
.text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
```

多行省略在 Web 中常用：

```css
.text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

项目 `WaterfallCard.vue` 中就用了这种思路展示短文本预览。

### 2. 元素被压扁

Flex 子项默认可能被压缩。可以加：

```css
flex-shrink: 0;
```

### 3. 绝对定位乱跑

检查父元素是否设置：

```css
position: relative;
```

### 4. 滚动事件不触发

检查：

- 容器是否真的有固定高度。
- 是否设置了 `scroll-y`。
- 内容高度是否超过容器。
- 事件名是否符合平台要求。

## 十六、可维护样式的基本分层

页面做出来只是第一步，能长期维护才是工程能力。样式建议按下面方式分层：

```text
设计变量
 -> 页面布局
   -> 组件样式
     -> 状态样式
```

设计变量放颜色、间距、字号、圆角、阴影等基础 token；页面布局负责整体结构，比如顶部栏、滚动区、底部导航；组件样式只管理组件内部元素；状态样式表达 active、disabled、loading、empty、error 等变化。

不要让页面样式深入修改子组件内部结构，例如：

```css
.page .card .button .icon {
  color: red;
}
```

这种选择器短期看起来有效，长期会让组件失去独立性。更好的方式是通过 props、class 或 CSS 变量暴露可配置点。

## 十七、小结

HTML/CSS 的核心不是背标签和属性，而是建立页面模型：

- HTML 或 uni-app 模板负责结构。
- CSS 负责布局和视觉。
- 盒模型决定尺寸。
- Flex 和 Grid 决定排列。
- 定位决定覆盖关系。
- 滚动容器决定页面交互。
- CSS 变量让样式系统可维护。
- scoped CSS 限制组件样式作用域。

学 Vue 之前先掌握这些，能少走很多弯路。否则你会在组件里写出很多“看起来像能跑，实际上靠运气”的样式。运气这种东西，用在抽奖上比较合适，用在布局上就不太体面了。
