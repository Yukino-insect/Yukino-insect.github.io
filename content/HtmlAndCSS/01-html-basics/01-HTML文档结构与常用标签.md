+++
date = '2026-08-19T17:09:00+08:00'
draft = false
title = 'HTML 文档结构与常用标签：从第一张网页开始'
+++

HTML 是页面结构描述语言。它不负责计算，也不负责复杂逻辑，它负责告诉浏览器：页面里有哪些内容，这些内容之间是什么关系。

这一篇从完整 HTML 文档开始，逐步认识常用标签。

## 一、最小 HTML 页面

一个完整网页大致长这样：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的第一张网页</title>
  </head>
  <body>
    <h1>你好，前端</h1>
    <p>这是我的第一张网页。</p>
  </body>
</html>
```

每一部分的含义：

| 代码 | 作用 |
| ---- | ---- |
| `<!doctype html>` | 告诉浏览器使用现代 HTML 解析模式 |
| `<html>` | 整个页面的根元素 |
| `<head>` | 页面元信息，不直接显示在正文中 |
| `<body>` | 页面可见内容 |
| `<meta charset>` | 指定字符编码 |
| `<meta name="viewport">` | 适配移动端视口 |
| `<title>` | 浏览器标签标题 |

小白经常漏掉 `viewport`，然后移动端页面看起来很奇怪。它不是装饰，是移动端适配的基础。

## 二、标题和段落

标题从 `h1` 到 `h6`：

```html
<h1>网站主标题</h1>
<h2>章节标题</h2>
<h3>小节标题</h3>
```

段落使用 `p`：

```html
<p>HTML 负责页面结构，CSS 负责页面样式。</p>
```

注意：不要因为想让字变大就乱用标题。标题表达结构层级，字号应该交给 CSS。

## 三、链接

链接使用 `a`：

```html
<a href="https://example.com">访问示例网站</a>
```

新窗口打开：

```html
<a href="https://example.com" target="_blank" rel="noreferrer">
  新窗口打开
</a>
```

`href` 是链接地址。没有 `href` 的 `a` 标签就不像真正的链接，交互语义会变差。

## 四、图片

图片使用 `img`：

```html
<img src="/images/avatar.png" alt="用户头像">
```

`alt` 很重要：

- 图片加载失败时显示替代文本。
- 屏幕阅读器会读取它。
- 搜索引擎和辅助工具能理解图片含义。

如果图片只是装饰，也可以写空 `alt`：

```html
<img src="/images/line.png" alt="">
```

不要省略 `alt`。这是习惯问题，也是专业程度问题。

## 五、列表

无序列表：

```html
<ul>
  <li>HTML</li>
  <li>CSS</li>
  <li>JavaScript</li>
</ul>
```

有序列表：

```html
<ol>
  <li>安装编辑器</li>
  <li>创建 HTML 文件</li>
  <li>打开浏览器查看</li>
</ol>
```

列表适合表达一组同类内容，不要用一堆 `div` 假装列表。

## 六、通用容器

最常见容器是 `div` 和 `span`。

```html
<div class="card">
  <span class="tag">前端</span>
  <p>一段内容</p>
</div>
```

区别：

- `div` 默认是块级容器。
- `span` 默认是行内容器。

它们没有语义，只是通用包装。能用语义标签时，优先使用语义标签。

## 七、语义化标签

HTML5 提供了很多语义标签：

| 标签 | 语义 |
| ---- | ---- |
| `header` | 页头或区域头部 |
| `nav` | 导航 |
| `main` | 页面主体 |
| `section` | 章节区域 |
| `article` | 独立文章或卡片 |
| `aside` | 侧边内容 |
| `footer` | 页脚 |

示例：

```html
<main>
  <section>
    <h2>文章列表</h2>
    <article>
      <h3>HTML 入门</h3>
      <p>先理解结构，再学习样式。</p>
    </article>
  </section>
</main>
```

语义化的好处：

- 结构更清楚。
- 对搜索引擎更友好。
- 对辅助工具更友好。
- 代码可读性更好。

## 八、按钮

按钮使用 `button`：

```html
<button type="button">提交</button>
```

在表单中，`button` 默认可能触发表单提交。为了避免意外，普通按钮建议显式写 `type="button"`。

```html
<button type="submit">登录</button>
<button type="button">取消</button>
```

不要用 `div` 假装按钮。它缺少按钮语义和键盘可访问性。能用正确标签，就别绕远路。

## 九、注释

HTML 注释：

```html
<!-- 这里是页面主体 -->
<main></main>
```

注释应该解释结构目的，不要写无意义内容：

```html
<!-- 这是 div -->
<div></div>
```

这种注释并不会让代码更聪明。

## 十、练习

写一个个人资料卡片，要求包含：

- 头像。
- 姓名。
- 简介。
- 技能列表。
- 一个“查看详情”按钮。

参考结构：

```html
<article class="profile-card">
  <img src="/avatar.png" alt="用户头像">
  <h2>小白同学</h2>
  <p>正在学习 HTML 与 CSS。</p>
  <ul>
    <li>HTML</li>
    <li>CSS</li>
  </ul>
  <button type="button">查看详情</button>
</article>
```

先把结构写正确，再去考虑样式。页面结构一旦混乱，CSS 会变成补漏洞，而不是做设计。
