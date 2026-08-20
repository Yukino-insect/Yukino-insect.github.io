+++
date = '2026-08-19T17:02:00+08:00'
draft = false
title = 'CSS 工程化与 Vue 样式实践：从能写到能维护'
+++

当页面变多、组件变多，CSS 最容易失控。选择器互相覆盖、颜色到处复制、间距没有规则、组件样式泄漏，这些问题不会在第一天爆炸，但会在项目变大后让人很难受。

这一篇讲基础工程实践，让小白从一开始就养成可维护的样式习惯。

## 一、样式分层

推荐把样式分为几层：

```text
全局重置
 -> 主题变量
 -> 基础排版
 -> 布局工具
 -> 组件样式
 -> 页面样式
```

目录示例：

```text
styles/
  reset.css
  variables.css
  base.css
  utilities.css
```

组件自己的样式写在组件里，公共规则写在全局文件里。

## 二、CSS Reset

浏览器有默认样式。适当重置可以减少差异：

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, sans-serif;
  color: #1f2937;
  background: #f7f8fa;
}

button,
input,
textarea,
select {
  font: inherit;
}
```

不要粗暴清空所有样式。重置是为了建立稳定基础，不是为了和浏览器打一架。

## 三、CSS 变量

把常用颜色和间距定义为变量：

```css
:root {
  --color-text: #1f2937;
  --color-muted: #64748b;
  --color-border: #e5e7eb;
  --color-primary: #2563eb;
  --space-sm: 8px;
  --space-md: 16px;
  --radius-md: 8px;
}
```

使用：

```css
.card {
  padding: var(--space-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
```

变量能减少重复，也能让视觉规则更统一。

## 四、命名习惯

类名应该表达结构或语义：

```css
.post-card {}
.post-card-title {}
.post-card-summary {}
```

不推荐：

```css
.red {}
.big {}
.left {}
```

因为需求会变。今天是红色，明天可能改成蓝色，类名却还叫 `.red`，这就有点尴尬。

## 五、组件样式

Vue 单文件组件中常见写法：

```vue
<template>
  <article class="post-card">
    <h2 class="post-card-title">{{ title }}</h2>
  </article>
</template>

<style scoped>
.post-card {
  padding: 16px;
}

.post-card-title {
  margin: 0;
}
</style>
```

`scoped` 可以降低样式泄漏风险。它适合组件局部样式，但全局变量、字体、重置样式仍然应该放全局。

## 六、避免深选择器滥用

有时需要影响子组件内部样式，会看到深选择器：

```css
:deep(.child-title) {
  color: #2563eb;
}
```

深选择器要少用。它会穿透组件边界，降低组件独立性。频繁需要深选择器，往往说明组件 API 设计不够好。

## 七、uni-app 样式注意点

uni-app 中常见单位：

- `px`：固定像素。
- `rpx`：响应式像素，常用于小程序。
- `%`：相对父容器。

常见组件类比：

| uni-app | Web |
| ------- | --- |
| `view` | `div` |
| `text` | `span` |
| `image` | `img` |
| `scroll-view` | 滚动容器 |

这只是类比，不是完全等价。不同平台对样式支持会有差异，跨端项目要多测目标平台。

## 八、工具类

少量工具类可以提高效率：

```css
.text-muted {
  color: var(--color-muted);
}

.mt-md {
  margin-top: var(--space-md);
}
```

但不要把所有样式都拆成工具类，尤其是小白阶段。先写清楚组件结构，再考虑是否抽工具。

## 九、常见坏味道

- 大量 `!important`。
- 选择器特别长。
- class 名和视觉强绑定。
- 全局样式随意覆盖组件。
- 一个颜色复制几十次。
- 每个页面都有自己的间距体系。
- 为了解决一个问题不断加 `position: absolute`。

`!important` 尤其要克制。它像拍桌子，偶尔可以，天天拍桌子说明沟通方式有问题。

## 十、样式检查清单

写完页面后检查：

- class 名是否能表达含义。
- 颜色和间距是否使用变量。
- 是否存在无意义的深层选择器。
- 小屏是否溢出。
- 图片是否变形。
- 文本是否可读。
- hover、focus、disabled 状态是否处理。

## 十一、练习

把前面做过的文章卡片改成 Vue 组件：

- props 接收标题、摘要、封面。
- 使用 `scoped` 样式。
- 颜色和间距使用 CSS 变量。
- 图片固定比例。
- 标题两行省略。
- 卡片 hover 时边框颜色变化。

从能写到能维护，中间隔着的不是天赋，而是习惯。好习惯一开始麻烦，后面省命。
