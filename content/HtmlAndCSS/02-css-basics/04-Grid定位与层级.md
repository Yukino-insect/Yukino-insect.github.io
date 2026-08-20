+++
date = '2026-08-19T17:04:00+08:00'
draft = false
title = 'Grid、定位与层级：从卡片网格到悬浮按钮'
+++

Flex 适合一维布局，Grid 更适合二维布局。定位则用来处理脱离普通文档流的场景，比如固定导航、悬浮按钮、弹窗遮罩、角标。

这一篇讲 Grid、position 和 z-index。

## 一、Grid 适合什么

Grid 适合行和列同时存在的布局：

- 卡片网格。
- 仪表盘面板。
- 图片墙。
- 表单多列布局。
- 页面大区域布局。

开启 Grid：

```css
.grid {
  display: grid;
}
```

## 二、定义列

三列等宽：

```css
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}
```

也可以写：

```css
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
```

`fr` 表示剩余空间份额。

## 三、自适应网格

常见响应式写法：

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}
```

含义：

- 每个卡片最小 240px。
- 空间足够时自动多列。
- 空间不足时自动换行。

这比手写很多媒体查询更简洁。

## 四、Grid 和 Flex 怎么选

简单判断：

| 场景 | 推荐 |
| ---- | ---- |
| 一行按钮 | Flex |
| 左图右文 | Flex |
| 垂直排列卡片内容 | Flex |
| 多列卡片网格 | Grid |
| 页面仪表盘 | Grid |
| 表单两列布局 | Grid |

不要争谁更高级。工具没有虚荣心，人有。

## 五、普通文档流

默认情况下，元素按文档流排列：

```text
上一个元素
下一个元素
再下一个元素
```

大多数布局应该优先使用普通文档流、Flex 或 Grid。定位是特殊工具，不要一遇到布局就 `position: absolute`。

## 六、position

常见值：

| 值 | 含义 |
| -- | ---- |
| `static` | 默认定位 |
| `relative` | 相对自身原位置 |
| `absolute` | 相对最近的定位祖先 |
| `fixed` | 相对浏览器视口 |
| `sticky` | 滚动到某位置后吸附 |

## 七、absolute

角标示例：

```html
<div class="avatar">
  <img src="/avatar.png" alt="头像">
  <span class="badge">3</span>
</div>
```

```css
.avatar {
  position: relative;
  width: 64px;
  height: 64px;
}

.badge {
  position: absolute;
  top: 0;
  right: 0;
}
```

`absolute` 会找最近的非 `static` 祖先作为参照。所以父元素常常要写 `position: relative`。

## 八、fixed

固定底部按钮：

```css
.float-button {
  position: fixed;
  right: 24px;
  bottom: 24px;
}
```

它相对视口固定，不随页面滚动而离开。

## 九、sticky

吸顶导航：

```css
.header {
  position: sticky;
  top: 0;
  z-index: 10;
}
```

`sticky` 受父容器和滚动容器影响。如果没效果，要检查父元素是否设置了 `overflow`。

## 十、z-index

`z-index` 控制层叠顺序，但只对定位元素或特定布局上下文有效。

```css
.modal {
  position: fixed;
  z-index: 1000;
}
```

常见层级：

```text
普通内容 1
导航 10
下拉菜单 100
遮罩 900
弹窗 1000
提示 1100
```

不要随手写 `999999`。这不是解决层级问题，而是把问题推给下一个人。

## 十一、练习

实现一个响应式卡片网格：

- 容器使用 Grid。
- 每张卡片最小宽度 240px。
- 自动换列。
- 卡片右上角有状态角标。
- 页面右下角有固定发布按钮。

这个练习覆盖 Grid、absolute、fixed 和 z-index。做完后，你会发现复杂布局并不是靠乱调位置，而是靠选择正确布局模型。
