+++
date = '2026-08-19T17:05:00+08:00'
draft = false
title = 'Flex 布局入门：让元素横着排、竖着排、居中排'
+++

Flex 是前端最常用的布局方式之一。它特别适合一维布局：横向排列一组按钮、纵向排列卡片内容、让元素居中、让左边固定右边自适应。

如果小白只能先学一种布局，先学 Flex。它使用频率高，见效也快。

## 一、开启 Flex

给父元素设置：

```css
.container {
  display: flex;
}
```

HTML：

```html
<div class="container">
  <div>1</div>
  <div>2</div>
  <div>3</div>
</div>
```

默认情况下，子元素会横向排列。

## 二、主轴和交叉轴

Flex 有两个方向：

- 主轴：元素排列方向。
- 交叉轴：和主轴垂直的方向。

默认：

```css
.container {
  display: flex;
  flex-direction: row;
}
```

主轴是水平方向。

改成纵向：

```css
.container {
  display: flex;
  flex-direction: column;
}
```

主轴变成垂直方向。

## 三、主轴对齐

使用 `justify-content`：

```css
.container {
  display: flex;
  justify-content: center;
}
```

常见值：

| 值 | 效果 |
| -- | ---- |
| `flex-start` | 靠起点 |
| `center` | 居中 |
| `flex-end` | 靠终点 |
| `space-between` | 两端对齐，中间分散 |
| `space-around` | 每个元素两侧有间距 |
| `space-evenly` | 间距完全均分 |

## 四、交叉轴对齐

使用 `align-items`：

```css
.container {
  display: flex;
  align-items: center;
}
```

常见值：

| 值 | 效果 |
| -- | ---- |
| `stretch` | 默认拉伸 |
| `flex-start` | 靠起点 |
| `center` | 居中 |
| `flex-end` | 靠终点 |

最常见的水平垂直居中：

```css
.center {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

## 五、gap 间距

现代浏览器可以用 `gap` 控制子元素间距：

```css
.toolbar {
  display: flex;
  gap: 12px;
}
```

这比给每个子元素写 `margin-right` 更清楚。

## 六、换行

默认不换行。开启换行：

```css
.list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
```

适合标签列表、卡片列表等。

## 七、子元素伸缩

`flex: 1` 表示占据剩余空间。

```css
.layout {
  display: flex;
}

.sidebar {
  width: 240px;
}

.content {
  flex: 1;
}
```

这样侧边栏固定，内容区自适应。

## 八、常见布局示例

### 1. 左图右文

```html
<article class="media-card">
  <img class="media-card-cover" src="/cover.jpg" alt="封面">
  <div class="media-card-body">
    <h2>标题</h2>
    <p>摘要内容</p>
  </div>
</article>
```

```css
.media-card {
  display: flex;
  gap: 16px;
}

.media-card-cover {
  width: 120px;
  height: 80px;
  object-fit: cover;
}

.media-card-body {
  flex: 1;
}
```

### 2. 两端对齐导航

```css
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
```

### 3. 纵向卡片

```css
.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
```

## 九、常见问题

### 1. 为什么 `justify-content` 没效果

可能是父元素没有剩余空间。元素本来就只占内容宽度时，就没有空间可分配。

```css
.container {
  display: flex;
  width: 100%;
}
```

### 2. 为什么元素被挤压

Flex 子项默认可能缩小。可以设置：

```css
.item {
  flex-shrink: 0;
}
```

### 3. 为什么文字撑破布局

长文本需要允许收缩：

```css
.content {
  min-width: 0;
}
```

这是 Flex 布局中非常常见的问题。记住 `min-width: 0`，它会在某些时刻救你一命。

## 十、练习

实现一个顶部导航：

- 左侧是网站名。
- 右侧是三个链接。
- 整体垂直居中。
- 左右两端对齐。
- 链接之间有 16px 间距。

然后实现一个文章卡片：

- 左边固定宽度封面。
- 右边自适应内容。
- 标题单行省略。
- 摘要两行省略。

这两个练习做熟，日常页面布局已经能解决一大半。
