+++
date = '2026-08-19T17:07:00+08:00'
draft = false
title = 'CSS 选择器、层叠与盒模型：样式为什么会生效或失效'
+++

CSS 最让小白困惑的地方不是属性很多，而是“为什么我写的样式没有生效”。要回答这个问题，必须理解选择器、层叠、继承和盒模型。

这一篇是 CSS 入门最重要的一篇。别急着跳过，布局问题大多都从这里开始。

## 一、CSS 写在哪里

CSS 有三种常见写法。

行内样式：

```html
<p style="color: red;">一段文字</p>
```

内部样式：

```html
<style>
  p {
    color: red;
  }
</style>
```

外部样式：

```html
<link rel="stylesheet" href="/styles.css">
```

工程项目中主要使用外部样式文件或组件内样式。行内样式优先级高，不利于维护，初学阶段少用。

## 二、基础选择器

标签选择器：

```css
p {
  color: #333;
}
```

类选择器：

```css
.card {
  padding: 16px;
}
```

id 选择器：

```css
#app {
  min-height: 100vh;
}
```

推荐主要使用类选择器。它语义清楚，复用性好，优先级也比较容易控制。

## 三、组合选择器

后代选择器：

```css
.card p {
  line-height: 1.8;
}
```

子元素选择器：

```css
.menu > li {
  padding: 8px;
}
```

多个类同时命中：

```css
.button.primary {
  background: #2563eb;
}
```

不要把选择器写得太长：

```css
.page .main .content .list .item .title {
  color: #222;
}
```

这种写法脆弱，结构稍微变化就失效。

## 四、伪类

常见伪类：

```css
a:hover {
  color: #2563eb;
}

input:focus {
  border-color: #2563eb;
}

button:disabled {
  opacity: 0.6;
}
```

伪类用于描述状态，例如悬停、聚焦、禁用、第几个元素。

## 五、层叠与优先级

CSS 的 C 是 Cascading，意思是层叠。多个规则命中同一个元素时，浏览器要决定哪个生效。

简单优先级：

```text
行内样式 > id 选择器 > class 选择器 > 标签选择器
```

示例：

```html
<p class="text" id="intro">内容</p>
```

```css
p {
  color: black;
}

.text {
  color: blue;
}

#intro {
  color: red;
}
```

最终是红色，因为 `id` 优先级最高。

## 六、继承

有些 CSS 属性会被子元素继承，例如：

- `color`。
- `font-family`。
- `font-size`。
- `line-height`。

有些不会继承，例如：

- `margin`。
- `padding`。
- `border`。
- `width`。
- `height`。

示例：

```css
body {
  color: #333;
  font-family: Arial, sans-serif;
}
```

页面内文字会继承这些基础字体样式。

## 七、盒模型

每个元素都可以看成一个盒子：

```text
content
 -> padding
 -> border
 -> margin
```

示例：

```css
.box {
  width: 200px;
  padding: 16px;
  border: 1px solid #ddd;
  margin: 20px;
}
```

默认情况下，`width` 只表示内容区宽度。实际占用宽度还要加上 padding 和 border。

## 八、box-sizing

工程中常用：

```css
* {
  box-sizing: border-box;
}
```

这样 `width` 会包含 content、padding 和 border。

```css
.box {
  width: 200px;
  padding: 16px;
  border: 1px solid #ddd;
}
```

最终盒子宽度仍然是 200px，而不是 234px。

这能减少很多布局计算麻烦。不是魔法，只是更符合人类直觉。

## 九、margin 折叠

垂直方向相邻块级元素的 `margin` 可能发生折叠。

```css
.a {
  margin-bottom: 20px;
}

.b {
  margin-top: 30px;
}
```

两者之间距离可能是 30px，而不是 50px。

初学时记住：如果垂直间距不符合预期，检查 margin 折叠。现代布局中也可以用 Flex/Grid 的 `gap` 管理间距，减少这类问题。

## 十、调试样式

浏览器开发者工具很重要：

- Elements 看 DOM 结构。
- Styles 看命中的 CSS。
- Computed 看最终计算值。
- Box Model 看盒模型尺寸。

排查顺序：

```text
元素是否选中
 -> class 是否存在
 -> 选择器是否命中
 -> 样式是否被划掉
 -> 是否被更高优先级覆盖
 -> 盒模型尺寸是否正确
```

如果你只靠猜，CSS 会显得很玄学。其实它很讲规则，只是不太主动解释自己。

## 十一、练习

写一个卡片样式：

```html
<article class="card">
  <h2 class="card-title">标题</h2>
  <p class="card-summary">摘要内容</p>
</article>
```

要求：

- 卡片宽度 320px。
- 内边距 16px。
- 边框 1px。
- 圆角 8px。
- 标题和摘要有不同颜色。
- 使用 `box-sizing: border-box`。

完成后用浏览器开发者工具查看盒模型。眼睛看到不如工具看到，工具可不会为了安慰你而撒谎。
