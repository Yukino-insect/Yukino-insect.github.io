+++
date = '2026-10-20T14:35:07+08:00'
draft = false
title = '使用 Hugo 从零制作静态网站：内容、模板、资源与 HTML'
+++

如果你想做一个博客、作品集或产品文档站，未必需要先搭一套数据库、后端接口和复杂的前端工程。对于主要展示文章、图片和固定页面的网站，**静态站点生成器**通常更直接：把 Markdown、模板和资源交给构建工具，生成浏览器可以直接访问的 HTML、CSS、JavaScript 与图片文件。

Hugo 是其中速度很快、单个可执行文件即可运行的一种工具。它并不会替你“设计一个网站”；它做的是把你写的内容和模板规则组合起来。这听起来朴素，但也正因此可靠：内容由 Markdown 管，页面骨架由 HTML 管，重复规则由模板管，资源由明确的目录管，而不是把一切都塞进某个神秘配置里。

本文会从零做一个小型个人站点，并解释四件事：如何创建和运行 Hugo 网站，如何写文章，如何用 Go Template 编写 HTML 页面，以及图片、CSS、JavaScript 等资源到底该放在哪里、怎样被页面使用。

## 一、先建立正确的心智模型

传统动态网站经常是“浏览器请求页面，服务器运行程序，再即时生成 HTML”。Hugo 的工作发生在部署之前：它读取源文件，**预先生成**所有页面；部署后，Web 服务器通常只负责把静态文件发给浏览器。

```text
content/*.md + layouts/*.html + static/ + assets/
                    │
                    ▼
                 hugo 构建
                    │
                    ▼
public/index.html、public/posts/...、CSS、JS、图片
                    │
                    ▼
              Nginx / GitHub Pages / 对象存储
                    │
                    ▼
                  浏览器访问
```

这里的“静态”不等于页面不能交互。搜索、主题切换、评论组件、图表等浏览器端功能仍可由 JavaScript 完成；它仅意味着 Hugo 构建时不会为每一次访问连接数据库并执行服务端业务逻辑。需要登录、支付、私密数据时，应把对应能力交给独立 API、认证服务或动态后端，而不要强行让静态文件扮演数据库。

一个 Hugo 项目最重要的目录如下：

| 目录 | 职责 | 是否直接写代码 |
| ---- | ---- | -------------- |
| `content/` | Markdown 内容、页面的 front matter | 是 |
| `layouts/` | HTML 模板和 Go Template 规则 | 是 |
| `static/` | 原样复制到站点根目录的资源 | 是 |
| `assets/` | 可被 Hugo 管道压缩、指纹化、处理的资源 | 是 |
| `public/` | 构建输出目录 | **否** |
| `themes/` | 主题代码（如果使用主题） | 按需 |

`public/` 是结果，不是源代码。手动改里面的 `index.html`，下一次 `hugo` 构建就会消失；这种做法和在编译后的 `.class` 文件里改 Java 一样，只是更容易让人误以为它有效。

## 二、安装 Hugo 并创建站点

先安装 **Hugo Extended**。它包含处理 SCSS 等扩展资源所需的能力，即使当前只写 CSS，安装 Extended 也能避免以后更换样式方案时重新踩坑。在 Windows 上可使用包管理器：

```powershell
winget install Hugo.Hugo.Extended
```

安装后重新打开终端，并检查版本：

```powershell
hugo version
```

创建一个名为 `my-site` 的站点：

```powershell
hugo new site my-site
Set-Location my-site
```

Hugo 会生成基础目录。先不要急着安装主题；自己做一个最小页面，才能知道主题到底替你完成了什么。创建下面的目录和文件后，项目结构应类似：

```text
my-site/
├── assets/
│   └── css/
│       └── site.css
├── content/
│   ├── _index.md
│   └── posts/
│       └── hello-hugo.md
├── layouts/
│   ├── _default/
│   │   ├── baseof.html
│   │   └── single.html
│   ├── partials/
│   │   └── header.html
│   └── index.html
├── static/
│   └── images/
│       └── avatar.svg
└── hugo.toml
```

## 三、先写内容：Markdown 与 front matter

Hugo 的文章是 Markdown 文件。文件头的 front matter 是元数据：标题、日期、是否草稿、标签等；其后的 Markdown 是正文。创建 `content/posts/hello-hugo.md`：

```md
+++
title = '我的第一篇 Hugo 文章'
date = 2026-10-20T10:00:00+08:00
draft = false
description = '用 Hugo 创建的第一篇文章。'
tags = ['Hugo', '静态网站']
+++

Hugo 会把这份 Markdown 转换为 HTML。

## 这一页从哪里来

页面的标题来自 front matter，正文由 Markdown 渲染，
而外层的页面结构来自 `layouts/` 中的 HTML 模板。

- 内容与样式应分开维护。
- 站内链接可以使用相对 Markdown 链接。
```

再创建首页内容文件 `content/_index.md`：

```md
+++
title = '林间笔记'
description = '一个由 Hugo 生成的小型静态网站。'
+++

这里记录技术、阅读和正在制作的东西。
```

目录会影响 URL。上例的文章通常会生成到 `/posts/hello-hugo/`，首页会生成到 `/`。如果你希望 URL 更稳定，不要过度依赖中文文件名和自动推导；可以在 front matter 中显式指定 `slug` 或 `url`。不过没有明确的迁移需求时，也不必把每个路径都手工写死。

## 四、配置站点的基本信息

编辑根目录的 `hugo.toml`：

```toml
baseURL = 'https://example.com/'
languageCode = 'zh-CN'
title = '林间笔记'

[params]
  description = '一个由 Hugo 生成的小型静态网站。'

[[menu.main]]
  name = '首页'
  pageRef = '/'
  weight = 10

[[menu.main]]
  name = '文章'
  pageRef = '/posts'
  weight = 20
```

`baseURL` 应填写正式部署地址，并保留末尾 `/`。本地预览时 Hugo 会使用开发服务器地址；部署到 GitHub Pages 的项目子路径、反向代理子目录等场景，则尤其需要验证生成的链接是否正确。配置不是越多越好，先保留标题、语言、地址和真正会被模板读取的参数即可。

## 五、用模板“编程” HTML 页面

Hugo 模板文件本质上是 HTML，只是在其中加入 Go Template 语法。双花括号 `{{ ... }}` 用来输出值、执行条件或循环；HTML 仍然负责结构与语义。把两者混为一谈，之后排查页面问题只会比普通 HTML 更痛苦。

### 1. 定义所有页面共享的骨架

创建 `layouts/_default/baseof.html`：

```html
<!doctype html>
<html lang="{{ site.Language.Lang }}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{{ with .Description }}{{ . }}{{ else }}{{ site.Params.description }}{{ end }}">
    <title>{{ if .IsHome }}{{ site.Title }}{{ else }}{{ .Title }} | {{ site.Title }}{{ end }}</title>

    {{ $style := resources.Get "css/site.css" | minify | fingerprint }}
    <link rel="stylesheet" href="{{ $style.RelPermalink }}" integrity="{{ $style.Data.Integrity }}">
  </head>
  <body>
    {{ partial "header.html" . }}
    <main class="page-shell">
      {{ block "main" . }}{{ end }}
    </main>
  </body>
</html>
```

它把每个页面共有的 `doctype`、`head`、导航和主体区域放在一起。这里有几个关键点：

- `.` 代表当前正在渲染的页面，因此 `.Title` 是当前页面标题，`.Description` 是当前页面描述。
- `site` 是全站对象，能读取 `hugo.toml` 中的站点配置。
- `with` 仅在值存在时进入块；文章有 `description` 就用文章描述，否则回退到全站描述。
- `block "main" .` 留出一个可被首页、文章页填充的区域。布局复用依赖它，而不是复制整份 HTML。
- `resources.Get` 从 `assets/` 取资源；`minify` 压缩 CSS，`fingerprint` 根据内容计算哈希，生成适合长期缓存的文件名，并提供完整性校验值。

模板变量进入 HTML 属性时，Hugo 会按上下文进行转义。不要为了“让它显示出来”就滥用 `safeHTML`；只有内容来源可信、且你明确知道绕过转义的安全后果时，才应使用它。

### 2. 写可复用的导航局部模板

创建 `layouts/partials/header.html`：

```html
<header class="site-header">
  <a class="site-brand" href="{{ site.Home.RelPermalink }}">{{ site.Title }}</a>
  <nav aria-label="主导航">
    <ul class="site-nav">
      {{ range site.Menus.main.ByWeight }}
        <li><a href="{{ .URL }}">{{ .Name }}</a></li>
      {{ end }}
    </ul>
  </nav>
</header>
```

`partial` 可以理解为服务器构建阶段的组件：导航只维护一份，所有页面共享。`range` 遍历配置中的菜单，`.ByWeight` 按 `weight` 排序。需要注意，这不是运行到浏览器里的 Vue 或 React 组件；它在执行 `hugo` 时就已经输出为普通 HTML 了。

### 3. 编写首页：循环生成文章卡片

创建 `layouts/index.html`：

```html
{{ define "main" }}
  <section class="hero">
    <p class="eyebrow">{{ site.Params.description }}</p>
    <h1>{{ .Title }}</h1>
    {{ .Content }}
  </section>

  <section aria-labelledby="latest-posts-title">
    <h2 id="latest-posts-title">最新文章</h2>
    <div class="post-grid">
      {{ range site.RegularPages.ByDate.Reverse }}
        <article class="post-card">
          <p class="post-date">{{ .Date.Format "2006-01-02" }}</p>
          <h3><a href="{{ .RelPermalink }}">{{ .LinkTitle }}</a></h3>
          {{ with .Description }}<p>{{ . }}</p>{{ end }}
        </article>
      {{ end }}
    </div>
  </section>
{{ end }}
```

`{{ define "main" }}` 会填充基础模板预留的 `main` 块。`site.RegularPages` 取得普通内容页，`ByDate.Reverse` 将它们按日期倒序排列，`range` 则为每篇文章生成一张语义化的 `<article>` 卡片。你写的是一次循环规则，Hugo 构建时才把它展开为多段 HTML；这正是静态站点也可以“编程”页面的含义。

### 4. 编写文章页：让 Markdown 落入页面容器

创建 `layouts/_default/single.html`：

```html
{{ define "main" }}
  <article class="post">
    <header class="post-header">
      <p class="post-date">{{ .Date.Format "2006 年 01 月 02 日" }}</p>
      <h1>{{ .Title }}</h1>
      {{ with .Description }}<p class="post-summary">{{ . }}</p>{{ end }}
    </header>

    <div class="post-content">
      {{ .Content }}
    </div>
  </article>
{{ end }}
```

`.Content` 是 Hugo 将 Markdown 渲染后的 HTML。不要在 Markdown 正文里重复写与 front matter 相同的 `# 标题`：模板已经输出了 `h1`，重复标题会破坏页面层级和搜索引擎语义。

## 六、为页面加入 CSS 与图片资源

创建 `assets/css/site.css`：

```css
:root {
  color: #1f2937;
  background: #f7f7f5;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

.site-header,
.page-shell {
  width: min(100% - 32px, 960px);
  margin-inline: auto;
}

.site-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 64px;
}

.site-brand,
.site-nav a,
.post-card a {
  color: inherit;
}

.site-nav,
.post-grid {
  display: flex;
  gap: 16px;
  padding: 0;
  list-style: none;
}

.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.post-card,
.post {
  padding: 24px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
}

.post-date,
.eyebrow {
  color: #6b7280;
  font-size: 0.875rem;
}

.post-content {
  line-height: 1.8;
}
```

这个 CSS 文件位于 `assets/`，所以才能被 `resources.Get`、压缩和指纹化。适合放 `assets/` 的是你希望 Hugo 处理的资源，例如全站 CSS、需要压缩的 JS、要缩放或转码的图片。

若文件不需要 Hugo 处理，应放 `static/`。例如将头像保存为 `static/images/avatar.svg` 后，模板可直接引用：

```html
<img src="{{ "images/avatar.svg" | relURL }}" alt="站长头像" width="80" height="80">
```

构建时它会原样复制为 `public/images/avatar.svg`。`relURL` 会根据站点地址和部署路径生成正确的站内 URL，比硬编码 `/images/avatar.svg` 更适合可能部署在子目录的网站。

### `static/` 与 `assets/` 该如何选择

| 需求 | 放置位置 | 页面获取方式 |
| ---- | -------- | ------------ |
| favicon、原样 SVG、下载文件 | `static/` | `relURL` 或普通 URL |
| 要压缩、合并或加哈希的 CSS/JS | `assets/` | `resources.Get` |
| 要裁剪、缩放、转 WebP 的图片 | `assets/` | `resources.Get` 后处理 |
| Markdown 正文配图 | 通常 `static/images/posts/` | `/images/posts/...` |

例如把封面图放在 `assets/images/cover.jpg`，可以在模板中生成一张裁剪后的 WebP：

```html
{{ with resources.Get "images/cover.jpg" }}
  {{ $cover := .Fill "1200x480 Center webp q82" }}
  <img src="{{ $cover.RelPermalink }}" width="{{ $cover.Width }}" height="{{ $cover.Height }}" alt="网站首页封面">
{{ end }}
```

这段逻辑由 Hugo 在构建时执行，浏览器最终只拿到生成好的图片 URL 与普通 `<img>` 标签。若图片不是全站公用资源，而是某篇文章独有的图片，也可以使用 page bundle；初学阶段先分清 `static/` 与 `assets/`，已经足够避免大部分目录混乱。

## 七、运行、构建与查看生成结果

在项目根目录启动开发服务器：

```powershell
hugo server --buildDrafts
```

终端会显示本地访问地址，通常是 `http://localhost:1313/`。保存 Markdown、模板或 CSS 后，Hugo 会自动重新构建；浏览器刷新即可看到变化。

准备发布时执行：

```powershell
hugo --minify
```

这会生成 `public/`。你可以打开 `public/index.html` 看看：里面已经没有 `{{ range ... }}`、`.Content` 或 Markdown 标记，只有浏览器实际接收的 HTML。这个检查很有价值，它能清楚地区分“模板代码没按预期执行”和“浏览器 CSS/JavaScript 显示异常”两类问题。

一个稳妥的发布流程是：

```text
修改 content / layouts / assets / static
        -> hugo server 本地预览
        -> hugo --minify 正式构建
        -> 检查 public/ 中的链接、图片和 HTML
        -> 上传 public/ 到静态托管服务
```

GitHub Pages、Netlify、Cloudflare Pages、对象存储加 CDN，或一台 Nginx 服务器都可以托管 `public/`。差别主要在构建由谁执行、域名和缓存如何配置；Hugo 的源文件结构不需要因此改变。

## 八、主题、覆盖顺序与常见误解

不想从零写模板时，可以安装主题。但主题不是一个不可触碰的黑盒。Hugo 会优先使用项目根目录的 `layouts/`，再回退到主题中的同名模板。因此你可以使用主题提供的多数页面，只在自己的 `layouts/` 中覆盖某个页面或 partial。

这也带来几个容易犯的错误：

- **在 `public/` 改页面。** 构建结果必然会覆盖它；应改 `content/`、`layouts/` 或资源目录。
- **把 CSS 放进 `static/`，却使用 `resources.Get` 读取。** 两套资源机制不是同一个目录；前者应直接引用，后者才走资源管道。
- **所有图片都塞进模板。** 内容图片应随内容组织，模板只负责页面结构；否则文章迁移和复用都会很难看。
- **把原始 HTML 当成 Markdown 的万能逃生门。** Hugo 的 Markdown 渲染默认会保护输出；需要稳定、可复用的复杂 HTML 时，优先写模板或 shortcode，而不是在每篇文章里复制大段标签。
- **把 Hugo 当作带数据库的应用框架。** 它能生成静态页面，却不会替你完成用户注册、实时权限校验或安全的私密数据存取。

如果某种内容需要在 Markdown 中反复使用，例如提示框、视频、文章卡片，可以进一步创建 shortcode。它本质上仍是一个小模板，只是由作者在 Markdown 中主动调用；这比复制一大段 HTML 更容易统一样式和修复问题。

## 九、到这里应该掌握什么

用 Hugo 制作网站的核心不是记住多少命令，而是分清构建链路中的职责：

- `content/` 保存可阅读、可版本管理的 Markdown 内容与元数据。
- `layouts/` 用 HTML 加 Go Template 定义页面结构、循环、条件和复用片段。
- `static/` 放原样发布的文件，`assets/` 放需要 Hugo 编译或处理的文件。
- `hugo server` 用于开发预览，`hugo --minify` 将源文件生成可部署的 `public/`。
- 浏览器最终看到的始终是 HTML、CSS、JS 和资源文件；模板只是构建阶段的程序。

先用本文的最小站点做出首页和一篇文章，再逐步加入文章列表、标签页、图片处理和短代码。网站工程最怕的不是功能少，而是在还没理解内容、模板与构建产物的边界前，就让目录和工具先失去秩序。那样的复杂，通常没有任何值得骄傲的地方。
