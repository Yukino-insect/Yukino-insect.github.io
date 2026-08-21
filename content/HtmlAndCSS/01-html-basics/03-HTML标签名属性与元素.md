+++
date = '2026-08-21T19:47:36+08:00'
draft = false
title = 'HTML 标签名、属性与元素：看懂一段标签到底在写什么'
+++

看到这样的代码时：

```html
<article class="post-card"></article>
```

初学者很容易产生几个问题：

- `<article>` 是不是标签名？
- `class` 是不是属性？
- `post-card` 又是什么？
- 不同标签是不是几乎没有共同属性，只能靠用多了慢慢记住？

这些问题问得很正常。HTML 表面看起来像是在背单词，其实背后有一套很固定的结构。先把这套结构看清楚，后面再遇到新标签，就不会只能硬记。

## 一、一段 HTML 标签由什么组成

先看最简单的一段：

```html
<article class="post-card">文章内容</article>
```

可以拆成几部分：

| 部分 | 名称 | 含义 |
| ---- | ---- | ---- |
| `<article class="post-card">` | 开始标签 | 元素开始的位置 |
| `article` | 标签名 | 告诉浏览器这是什么类型的元素 |
| `class="post-card"` | 属性 | 给这个元素补充信息 |
| `class` | 属性名 | 属性的名字 |
| `post-card` | 属性值 | 属性对应的值 |
| `文章内容` | 内容 | 元素里面包裹的内容 |
| `</article>` | 结束标签 | 元素结束的位置 |

所以，你的理解基本正确：

- `article` 是标签名。
- `class` 是属性名。
- `post-card` 是 `class` 属性的值。
- 从开始标签到结束标签形成一个 HTML 元素。

日常交流中，很多人会把“标签”和“元素”混着说。例如说“这个 `article` 标签”，通常是在指这一整个元素。严格一点说，标签是源码中的标记，元素是浏览器解析后形成的页面节点。

## 二、标签名表示元素的语义

标签名不是随便取的。HTML 内置了一批标签名，每个标签都有自己的语义或用途。

例如：

```html
<h1>页面主标题</h1>
<p>这是一段正文。</p>
<a href="/about">关于我们</a>
<button type="button">打开弹窗</button>
<article>一篇文章或一张独立卡片</article>
```

这些标签名告诉浏览器和开发者：这里是什么内容。

| 标签 | 常见语义 |
| ---- | -------- |
| `h1` 到 `h6` | 标题层级 |
| `p` | 段落 |
| `a` | 链接 |
| `button` | 按钮 |
| `img` | 图片 |
| `ul` / `ol` / `li` | 列表 |
| `form` | 表单 |
| `input` | 输入控件 |
| `article` | 独立内容 |
| `section` | 页面章节 |
| `nav` | 导航 |
| `main` | 页面主体 |

比如下面这段：

```html
<article class="post-card">
  <h2>HTML 标签入门</h2>
  <p>先理解标签名和属性，再去记具体用法。</p>
</article>
```

`article` 表示这是一个相对独立的内容块，可能是一篇文章、一张文章卡片、一条新闻、一条评论。`class="post-card"` 则是给它起一个样式或脚本上可识别的名字。

也就是说，**标签名主要回答“它是什么”，属性主要回答“它有什么补充信息或行为配置”**。

## 三、属性写在开始标签里

属性一般写在开始标签中：

```html
<a href="https://example.com" target="_blank">访问网站</a>
```

这里有两个属性：

- `href="https://example.com"`：链接地址。
- `target="_blank"`：打开方式。

再看图片：

```html
<img src="/images/avatar.png" alt="用户头像">
```

这里有两个属性：

- `src="/images/avatar.png"`：图片地址。
- `alt="用户头像"`：图片替代文本。

属性的基本格式是：

```html
<标签名 属性名="属性值">内容</标签名>
```

多个属性之间用空格隔开：

```html
<input id="username" name="username" type="text" required>
```

注意：属性属于某一个元素，不是单独存在的东西。`class`、`href`、`src` 这些属性都必须挂在具体标签上才有意义。

## 四、不是所有属性都需要属性值

大多数属性是 `属性名="属性值"` 这种形式，但有些属性是布尔属性。它只要出现，就表示开启。

例如：

```html
<input type="text" required>
<input type="checkbox" checked>
<button disabled>不能点击</button>
```

这里：

- `required` 表示必填。
- `checked` 表示默认选中。
- `disabled` 表示禁用。

也可以写成：

```html
<input type="text" required="required">
```

但在 HTML 中，布尔属性通常直接写属性名就够了。初学时知道这个规则即可，不必在这种地方显示得过于勤奋。代码不是靠把简单事写复杂来显得专业的。

## 五、HTML 有共同属性吗

有。HTML 并不是每个标签都从零开始，很多属性可以用于大多数 HTML 元素，这类属性通常叫 **全局属性**。

常见全局属性如下：

| 属性 | 作用 |
| ---- | ---- |
| `class` | 给元素添加一个或多个类名，常用于 CSS 和 JavaScript |
| `id` | 给元素设置唯一标识 |
| `style` | 直接写行内样式 |
| `title` | 鼠标悬停时的补充说明 |
| `hidden` | 隐藏元素 |
| `lang` | 指定内容语言 |
| `dir` | 指定文字方向 |
| `tabindex` | 控制键盘聚焦顺序 |
| `data-*` | 自定义数据属性 |

例如 `class` 可以写在很多标签上：

```html
<article class="post-card"></article>
<button class="primary-button">提交</button>
<img class="avatar" src="/avatar.png" alt="用户头像">
<section class="profile-section"></section>
```

`id` 也可以写在很多标签上：

```html
<section id="profile"></section>
<input id="username" type="text">
<h2 id="comments">评论区</h2>
```

所以不能说“标签基本没有共同属性”。准确说法应该是：

**HTML 有一批全局属性，很多标签都能用；同时，每个标签也有自己更常用、更有意义的专有属性。**

## 六、全局属性不等于随便使用

虽然 `class`、`id`、`style` 这些属性大多数标签都能写，但能写不代表应该乱写。

例如：

```html
<p class="text-muted">这是一段说明文字。</p>
<button class="primary-button" type="button">保存</button>
```

这是合理的，因为 `class` 用来给 CSS 提供选择目标。

但下面这种就不太推荐：

```html
<p style="color: red; font-size: 20px;">重要提示</p>
```

`style` 是全局属性，确实能用。但如果样式很多，最好写到 CSS 中：

```html
<p class="warning-text">重要提示</p>
```

```css
.warning-text {
  color: red;
  font-size: 20px;
}
```

`style` 适合临时测试或非常特殊的动态样式，不适合作为日常主要写法。否则 HTML 会很快变成一团混在一起的结构和样式。

## 七、专有属性更依赖标签本身

有些属性只在特定标签上才有意义。

例如链接的 `href`：

```html
<a href="/posts/html">阅读文章</a>
```

`href` 对 `a` 很重要，因为它表示跳转地址。你把 `href` 写到普通 `div` 上：

```html
<div href="/posts/html">阅读文章</div>
```

浏览器不会把它当成真正链接。这个属性虽然写上去了，但语义和默认行为都不成立。

再比如图片的 `src` 和 `alt`：

```html
<img src="/cover.png" alt="文章封面">
```

`src` 表示图片来源，`alt` 表示替代文本。它们对 `img` 很重要。

表单输入框的 `type`、`name`、`value`：

```html
<input type="email" name="email" value="">
```

这些属性和表单提交、输入类型、默认值有关。

常见专有属性可以这样理解：

| 标签 | 常见属性 | 含义 |
| ---- | -------- | ---- |
| `a` | `href`、`target`、`rel` | 链接地址、打开方式、关系说明 |
| `img` | `src`、`alt`、`width`、`height` | 图片地址、替代文本、尺寸 |
| `input` | `type`、`name`、`value`、`placeholder`、`required` | 输入类型、字段名、值、提示、校验 |
| `button` | `type`、`disabled` | 按钮类型、是否禁用 |
| `form` | `action`、`method` | 提交地址、提交方式 |
| `label` | `for` | 绑定输入控件 |
| `meta` | `charset`、`name`、`content` | 页面元信息 |
| `link` | `rel`、`href` | 外部资源关系和地址 |
| `script` | `src`、`type`、`defer` | 脚本地址、类型、加载方式 |

这个表不需要一次背完。先记住最常见的几组就够了：链接看 `href`，图片看 `src` 和 `alt`，表单看 `type`、`name`、`value`。

## 八、class 到底是什么

`class` 是最常用的全局属性之一，用来给元素添加类名。

```html
<article class="post-card"></article>
```

这里的 `post-card` 不是 HTML 标签，也不是浏览器内置关键字，而是你自己起的类名。

CSS 可以通过类选择器找到它：

```css
.post-card {
  padding: 16px;
  border: 1px solid #ddd;
}
```

一个元素可以有多个 class：

```html
<article class="post-card featured"></article>
```

表示这个元素同时拥有两个类名：

- `post-card`
- `featured`

CSS 可以分别写：

```css
.post-card {
  padding: 16px;
}

.featured {
  border-color: orange;
}
```

所以 `class` 的作用不是“改变标签语义”，而是给 CSS 和 JavaScript 一个稳定的选择目标。`article` 仍然是 `article`，只是它额外有了一个叫 `post-card` 的类名。

## 九、id 和 class 的区别

`id` 和 `class` 都能用来标识元素，但定位方式不同。

```html
<section id="profile"></section>
<article class="post-card"></article>
<article class="post-card"></article>
```

区别：

| 属性 | 特点 | 常见用途 |
| ---- | ---- | -------- |
| `id` | 页面中应该唯一 | 锚点、表单 label 绑定、少量脚本定位 |
| `class` | 可以重复使用 | 样式复用、组件命名、批量选择 |

写 CSS 时，初学阶段更推荐多用 `class`，少用 `id`。

```css
.post-card {
  padding: 16px;
}
```

`id` 选择器优先级比较高，后面样式覆盖时容易让人困惑。它不是不能用，只是不要把它当成普通样式命名工具。

## 十、有些标签没有结束标签

大多数 HTML 元素有开始标签和结束标签：

```html
<p>一段文字</p>
<article>一张卡片</article>
<button>提交</button>
```

但有些元素没有结束标签，常见的有：

```html
<img src="/avatar.png" alt="用户头像">
<input type="text" name="username">
<br>
<hr>
<meta charset="UTF-8">
<link rel="stylesheet" href="/style.css">
```

这类元素通常叫空元素。它们不能包裹内容，所以不写 `</img>`、`</input>` 这类结束标签。

判断方法也不用神秘化：能包含内容的通常有结束标签，例如 `p`、`a`、`button`、`article`；本身就是一个独立资源或控件的，很多是空元素，例如 `img`、`input`、`meta`。

## 十一、到底要不要背标签和属性

答案是：**要记常用的，但不要靠死背学 HTML**。

更好的学习方式是按类别记：

### 1. 先记结构类标签

```html
<header></header>
<nav></nav>
<main></main>
<section></section>
<article></article>
<aside></aside>
<footer></footer>
<div></div>
```

它们主要负责页面结构。

### 2. 再记文本类标签

```html
<h1></h1>
<h2></h2>
<p></p>
<span></span>
<strong></strong>
<em></em>
```

它们主要负责文本语义。

### 3. 再记资源和跳转类标签

```html
<a href="/about">关于</a>
<img src="/avatar.png" alt="头像">
```

重点记住 `href`、`src`、`alt`。

### 4. 最后记表单类标签

```html
<form></form>
<label></label>
<input>
<textarea></textarea>
<select></select>
<option></option>
<button></button>
```

重点记住 `type`、`name`、`value`、`for`、`id`、`required`。

这样学会比把所有标签按字母表背一遍有效得多。按字母表背 HTML，多少有点像按新华字典学习写作文，不能说完全没用，但确实不像正常人会采用的路线。

## 十二、遇到陌生标签怎么判断

以后看到陌生标签，可以按这个顺序看：

```text
标签名是什么
 -> 它表达什么语义
 -> 它能不能包裹内容
 -> 它常用哪些属性
 -> 这些属性是全局属性还是专有属性
 -> CSS 或 JavaScript 有没有通过 class / id 选中它
```

例如：

```html
<article class="post-card" data-id="1001">
  <h2>文章标题</h2>
  <p>文章摘要</p>
</article>
```

可以这样分析：

- `article`：标签名，表示独立内容。
- `class="post-card"`：全局属性，类名是 `post-card`。
- `data-id="1001"`：自定义数据属性，保存业务数据。
- `h2`：文章标题。
- `p`：文章摘要。

`data-*` 也是全局属性的一种写法，常用于给元素挂一点自定义数据：

```html
<button type="button" data-action="delete" data-id="1001">删除</button>
```

JavaScript 可以读取这些数据，然后决定点击按钮时做什么。

## 十三、常见误区

### 1. 以为 class 是标签

错误理解：

```html
<article class="post-card"></article>
```

把 `post-card` 当成某种标签。

正确理解：

- `article` 是标签名。
- `class` 是属性名。
- `post-card` 是类名。

### 2. 以为属性随便写都会生效

```html
<div href="/about">关于我们</div>
```

这不会让 `div` 变成链接。要跳转就应该用：

```html
<a href="/about">关于我们</a>
```

HTML 不是许愿机。你写了一个属性，浏览器也许会保留它，但不代表它有对应行为。

### 3. 以为 div 可以替代一切

```html
<div class="button">提交</div>
```

看起来像按钮，不等于它就是按钮。真正的按钮应该写：

```html
<button type="button">提交</button>
```

正确标签自带语义、键盘交互和可访问性。先用正确标签，再用 CSS 改外观。

### 4. 以为所有东西都要背下来

常用标签和属性确实要熟，但不是第一天就全部背完。真正有效的方法是：

- 写页面时反复使用常见标签。
- 遇到陌生标签时查文档。
- 记住标签的类别和用途。
- 记住全局属性和常见专有属性。

前端开发不是闭卷考试。会查、会判断、会写出合理结构，比背一堆冷门标签更重要。

## 十四、小结

回到最开始的问题：

```html
<article class="post-card"></article>
```

可以总结为：

- `article` 是标签名。
- `<article>` 是开始标签。
- `</article>` 是结束标签。
- `class` 是属性名。
- `post-card` 是属性值，也是这个元素的类名。
- 从 `<article>` 到 `</article>` 这一整段形成一个元素。
- HTML 有很多共同属性，例如 `class`、`id`、`style`、`title`、`hidden`、`data-*`。
- 不同标签也有自己的专有属性，例如 `a` 的 `href`、`img` 的 `src`、`input` 的 `type`。
- 学习时不要死背全部标签，应该按结构、文本、链接图片、表单这些类别去理解和记忆。

HTML 入门最重要的不是“我认识多少标签”，而是看到一段结构时，能判断每个标签为什么存在，每个属性在补充什么信息。能做到这一点，再去学 CSS 选择器、布局和 Vue 模板，才不会总觉得页面是一堆符号堆出来的。
