+++
date = '2026-08-19T17:01:00+08:00'
draft = false
title = 'HTML/CSS 常见问题排查：样式乱了该从哪里下手'
+++

小白学 HTML/CSS 时最痛苦的不是不会写，而是写了没效果。页面乱、图片变形、文字溢出、按钮不居中、滚动条出现或消失，这些问题都有排查方法。

这一篇不讲新概念，只讲遇到问题时怎么查。

## 一、样式没有生效

按顺序检查：

```text
文件是否引入
 -> 选择器是否写对
 -> class 是否真的在元素上
 -> 样式是否被覆盖
 -> 属性值是否无效
```

示例：

```html
<div class="post-card"></div>
```

```css
.postcard {
  padding: 16px;
}
```

这里 class 名不一致，样式当然不会生效。CSS 不会猜你的意思，它只是执行规则。

## 二、样式被划掉

开发者工具里如果样式被划掉，通常说明被其他规则覆盖。

可能原因：

- 后面的规则覆盖前面的规则。
- 选择器优先级更高。
- 行内样式优先级更高。
- `!important` 覆盖普通规则。

解决方式：

- 调整选择器。
- 调整样式顺序。
- 减少过高优先级。
- 尽量不用 `!important`。

## 三、元素没有居中

先判断你要居中的是什么：

- 文字水平居中：`text-align: center`。
- 块级元素自身居中：`margin: 0 auto`，并设置宽度。
- Flex 子元素居中：父元素使用 Flex。

Flex 居中：

```css
.center {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

不要把所有居中问题都交给 `margin-left`。它会工作一会儿，然后在换屏幕尺寸时背叛你。

## 四、宽度超出屏幕

常见原因：

- 元素写死宽度。
- 盒模型没有使用 `border-box`。
- 长文本不换行。
- Grid/Flex 子项最小宽度过大。
- 图片超过容器。

常用处理：

```css
* {
  box-sizing: border-box;
}

img {
  max-width: 100%;
}

.text {
  overflow-wrap: anywhere;
}

.flex-child {
  min-width: 0;
}
```

移动端出现横向滚动时，优先检查固定宽度和长内容。

## 五、文字溢出

单行省略：

```css
.title {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
```

多行省略：

```css
.summary {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
```

如果内容必须完整显示，就不要省略，应该允许换行。

## 六、图片变形

图片变形通常是同时设置了宽高，却没有设置合适的填充方式。

```css
.cover {
  width: 100%;
  height: 180px;
  object-fit: cover;
}
```

完整显示：

```css
.image {
  width: 100%;
  height: 180px;
  object-fit: contain;
}
```

头像、封面多用 `cover`；需要完整展示的图片用 `contain`。

## 七、滚动失效

局部滚动需要容器有明确高度或最大高度。

```css
.panel {
  max-height: 400px;
  overflow: auto;
}
```

如果父元素没有高度，子元素写 `height: 100%` 往往没有意义。百分比高度需要父级有可计算高度。

## 八、定位不对

`absolute` 元素找最近的定位祖先。

```css
.card {
  position: relative;
}

.badge {
  position: absolute;
  top: 8px;
  right: 8px;
}
```

如果忘了给父元素写 `position: relative`，角标可能跑到别的地方。

## 九、z-index 没效果

检查：

- 元素是否参与定位或层叠上下文。
- 父元素是否创建了新的层叠上下文。
- 是否被其他更高层级覆盖。
- `overflow: hidden` 是否裁剪了内容。

不要盲目加大 `z-index`。层级问题需要看上下文，不是数字竞赛。

## 十、排查工具

浏览器开发者工具：

- Elements：查看结构和 class。
- Styles：查看命中样式。
- Computed：查看最终样式。
- Layout：查看 Flex/Grid。
- Box Model：查看 margin、border、padding、content。

排查时尽量在开发者工具里临时改样式，确认有效后再写回代码。直接在源码里乱试，会让你忘记自己到底改了什么。

## 十一、最终检查表

遇到样式问题时问自己：

- HTML 结构对吗？
- class 名对吗？
- CSS 文件加载了吗？
- 选择器命中了吗？
- 样式被覆盖了吗？
- 盒模型算对了吗？
- 父元素布局影响了吗？
- 移动端宽度适配了吗？

CSS 没有什么神秘脾气。大多数问题只是规则没看清。规则不会因为你着急就改变，真是冷淡得很，但也因此可靠。
