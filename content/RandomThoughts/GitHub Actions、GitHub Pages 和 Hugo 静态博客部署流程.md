+++
date = '2026-08-17T22:07:12+08:00'
draft = false
title = 'GitHub Actions、GitHub Pages 和 Hugo 静态博客部署流程'
+++

我们平时说“把博客部署到 GitHub 上”，这句话其实有一点偷懒。

严格来说，GitHub 并不是在帮你运行一个博客程序。它做的是另一件事：先用 `GitHub Actions` 自动执行构建命令，把 Hugo 项目生成成一堆静态文件，然后用 `GitHub Pages` 把这些静态文件发布出去。

如果把这个过程说得更朴素一点，就是：

```text
Markdown 文章 + Hugo 模板 + 图片资源
    -> Hugo 构建
    -> 生成 public 目录
    -> GitHub Pages 托管 public 里的静态网页
```

所以，这不是一个后端服务部署流程，而是一个静态网站发布流程。两者差别很大。后端服务需要长期运行进程，静态网站只需要把文件放到能被浏览器访问的地方。这个区别如果没弄明白，后面就会把很多问题想复杂。虽然计算机并不会因为你想复杂而心软就是了。

## 三个工具分别负责什么

部署一个 Hugo 静态博客时，通常会同时看到三个名字：

- `Hugo`
- `GitHub Actions`
- `GitHub Pages`

它们不是同一个东西，也不是互相替代的关系。它们各自负责一段流程。

## Hugo 是生成器

`Hugo` 是一个静态网站生成器。

它的作用是把你写的 Markdown 文章、页面模板、主题、图片、配置文件整合起来，生成浏览器可以直接打开的静态页面。

比如一个 Hugo 项目里通常会有这些目录：

```text
content/     存放 Markdown 文章
layouts/     存放页面模板
static/      存放图片、CSS、favicon 等静态资源
themes/      存放主题
data/        存放结构化配置数据
hugo.toml    Hugo 项目配置
```

当你执行：

```powershell
hugo
```

Hugo 会读取这些内容，然后生成：

```text
public/
```

`public/` 目录里就是最终网站。

里面一般会有：

- `index.html`
- 各个文章页面的 `index.html`
- CSS 文件
- JavaScript 文件
- 图片资源
- RSS、sitemap 等辅助文件

也就是说，Hugo 本身不是线上服务器。它只是一个“构建工具”。它在部署流程中的职责是：

```text
把源码变成静态网站文件
```

## GitHub Pages 是静态文件托管服务

`GitHub Pages` 是 GitHub 提供的静态网站托管服务。

它能托管这些文件：

- HTML
- CSS
- JavaScript
- 图片
- 字体
- JSON
- 其他静态资源

但是它不能运行这些东西：

- Java 后端服务
- Spring Boot 项目
- Node.js 服务端程序
- Python Flask、Django 服务
- MySQL、Redis 等数据库
- 需要服务器常驻进程的任务

所以 GitHub Pages 适合托管 Hugo、Hexo、VuePress、VitePress、纯 HTML 网站这类静态站点。

它不负责把 Markdown 变成 HTML。它只负责把已经生成好的静态文件发布出去。

GitHub Pages 在这个流程中的职责是：

```text
把构建后的静态文件发布成可以访问的网站
```

## GitHub Actions 是自动化流水线

`GitHub Actions` 是 GitHub 提供的自动化执行环境。

你可以把它理解成 GitHub 仓库里的一个自动工人。只要你告诉它：

- 什么时候执行
- 在什么系统上执行
- 执行哪些命令
- 执行完把结果交给谁

它就会在云端帮你跑这些步骤。

比如你可以配置：

```text
当我 push 到 master 分支时：
1. 拉取代码
2. 安装 Hugo
3. 执行 hugo --minify
4. 上传 public 目录
5. 部署到 GitHub Pages
```

这就是 `GitHub Actions` 的工作。

它在这个流程中的职责是：

```text
自动构建和自动部署
```

## 三者之间的关系

把三者放到一起看，就清楚了：

| 工具 | 职责 | 类比 |
| --- | --- | --- |
| Hugo | 把 Markdown 和模板生成静态网站 | 工厂 |
| GitHub Actions | 自动执行构建和部署步骤 | 流水线 |
| GitHub Pages | 托管最终生成的静态网页 | 展厅 |

完整流程如下：

```text
开发者写文章
    -> git push 到 GitHub
    -> GitHub Actions 被触发
    -> Actions 安装 Hugo
    -> Actions 执行 hugo --minify
    -> Hugo 生成 public/
    -> Actions 上传 public/
    -> GitHub Pages 发布 public/
    -> 用户通过浏览器访问网站
```

浏览器最终访问到的不是你的 Markdown 文件，也不是 Hugo 程序，而是 Hugo 生成后的 HTML 页面。

## 从零部署一个 Hugo 静态博客

下面从一个小白视角讲完整流程。

目标是：你在本地写 Markdown，推送到 GitHub 后，GitHub 自动帮你发布成一个博客网站。

## 准备工作

你需要准备：

- 一个 GitHub 账号
- 本地安装 Git
- 本地安装 Hugo
- 一个 GitHub 仓库
- 一点点命令行基础

如果只是使用 GitHub Actions 自动构建，严格来说本地不安装 Hugo 也能部署。但本地安装 Hugo 会方便预览和排查问题。所以，建议安装。是的，建议。不是因为它优雅，而是因为出问题时你不会只能盯着 Actions 日志发呆。

## 创建 Hugo 项目

在本地选择一个目录，执行：

```powershell
hugo new site blog
```

进入项目：

```powershell
cd blog
```

初始化 Git 仓库：

```powershell
git init
```

添加一个主题。以 `ananke` 为例：

```powershell
git submodule add https://github.com/theNewDynamic/gohugo-theme-ananke themes/ananke
```

然后在 `hugo.toml` 中配置主题：

```toml
baseURL = 'https://你的用户名.github.io/'
languageCode = 'zh-cn'
title = '我的博客'
theme = 'ananke'
```

如果你的仓库是用户主页仓库，仓库名通常是：

```text
你的用户名.github.io
```

那么 `baseURL` 可以写：

```toml
baseURL = 'https://你的用户名.github.io/'
```

如果你的仓库是普通项目仓库，比如仓库名叫：

```text
blog
```

那么 Pages 地址通常是：

```text
https://你的用户名.github.io/blog/
```

这时 `baseURL` 应该写：

```toml
baseURL = 'https://你的用户名.github.io/blog/'
```

这个地方很重要。很多静态资源 404、页面样式丢失、文章链接跳错，都是 `baseURL` 没写对造成的。

## 写一篇文章

创建一篇文章：

```powershell
hugo new posts/hello.md
```

打开生成的文件，内容大概是：

```toml
+++
date = '2026-08-17T20:00:00+08:00'
draft = true
title = 'Hello'
+++
```

如果要发布，需要把：

```toml
draft = true
```

改成：

```toml
draft = false
```

然后在下面写正文：

```md
## 第一篇文章

这是我的第一篇 Hugo 博客。
```

## 本地预览

执行：

```powershell
hugo server
```

默认访问地址通常是：

```text
http://localhost:1313/
```

如果能在本地看到页面，说明 Hugo 项目本身基本没问题。

也可以只构建，不启动预览服务：

```powershell
hugo
```

执行后会生成：

```text
public/
```

这个目录就是最终静态网站。

一般不建议把 `public/` 提交到 Git，因为它是构建产物，可以由 GitHub Actions 自动生成。

可以在 `.gitignore` 中加入：

```gitignore
/public/
/resources/_gen/
/.hugo_build.lock
```

## 创建 GitHub 仓库

接下来在 GitHub 上创建一个仓库。

有两种常见选择。

第一种是用户主页仓库：

```text
你的用户名.github.io
```

这种仓库部署后的地址通常是：

```text
https://你的用户名.github.io/
```

第二种是普通项目仓库：

```text
blog
```

这种仓库部署后的地址通常是：

```text
https://你的用户名.github.io/blog/
```

如果你只是想做一个个人博客首页，用户主页仓库更直观。如果你以后还会做多个项目页面，普通项目仓库也可以。

## 推送代码到 GitHub

假设你的远程仓库地址是：

```text
https://github.com/你的用户名/你的仓库名.git
```

执行：

```powershell
git remote add origin https://github.com/你的用户名/你的仓库名.git
git add .
git commit -m "init hugo blog"
git branch -M master
git push -u origin master
```

这里使用 `master` 是因为后面的 Actions 配置会监听 `master` 分支。

如果你想使用 `main` 分支，也可以，但要把 workflow 里的分支名一起改成 `main`。分支名不是装饰品，写错了就不会触发部署。

## 配置 GitHub Actions

在项目中创建文件：

```text
.github/workflows/hugo.yml
```

内容如下：

```yaml
name: Deploy Hugo site to GitHub Pages

on:
  push:
    branches:
      - master

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v5
        with:
          submodules: true
          fetch-depth: 0

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: 'latest'
          extended: true

      - name: Build
        run: hugo --minify

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v5
        with:
          path: ./public

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build

    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v5
```

这份配置可以拆开理解。

## 触发条件

```yaml
on:
  push:
    branches:
      - master
```

意思是：当代码推送到 `master` 分支时，执行这个 workflow。

如果你推送到别的分支，它不会执行。

## 权限

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

这几行是在告诉 GitHub Actions：

- 可以读取仓库内容
- 可以写入 GitHub Pages
- 可以使用身份令牌完成部署认证

如果权限不足，构建可能成功，但部署会失败。

## 拉取代码

```yaml
- name: Checkout
  uses: actions/checkout@v5
  with:
    submodules: true
    fetch-depth: 0
```

`actions/checkout` 负责把你的仓库代码拉到 GitHub 的构建机器上。

其中：

- `submodules: true` 表示同时拉取 Git 子模块
- `fetch-depth: 0` 表示拉取完整 Git 历史

如果主题是用 Git submodule 添加的，这里的 `submodules: true` 非常重要。否则 GitHub Actions 构建时可能找不到主题。

## 安装 Hugo

```yaml
- name: Setup Hugo
  uses: peaceiris/actions-hugo@v3
  with:
    hugo-version: 'latest'
    extended: true
```

这一步会在 GitHub Actions 的运行环境里安装 Hugo。

`extended: true` 表示安装 Hugo Extended 版本。有些主题需要 Extended 版本处理 SCSS、Sass 等资源，所以通常建议打开。

## 构建网站

```yaml
- name: Build
  run: hugo --minify
```

这一步是真正把 Hugo 项目构建成静态网站。

`--minify` 表示压缩生成结果，让 HTML、CSS、JS 更小一些。

执行完成后，会生成：

```text
public/
```

## 上传构建产物

```yaml
- name: Upload artifact
  uses: actions/upload-pages-artifact@v5
  with:
    path: ./public
```

这一步把 `public/` 目录作为 GitHub Pages 的发布产物上传。

注意，上传的是 `public/`，不是整个项目源码。

## 部署到 Pages

```yaml
- name: Deploy to GitHub Pages
  id: deployment
  uses: actions/deploy-pages@v5
```

这一步把前面上传的静态文件部署到 GitHub Pages。

部署成功后，GitHub Actions 页面里会显示访问地址。

## 配置 GitHub Pages 来源

进入 GitHub 仓库页面：

```text
Settings -> Pages
```

在 Build and deployment 里，把 Source 选择为：

```text
GitHub Actions
```

这样 GitHub Pages 就会使用你的 workflow 部署结果。

如果这里还选着从某个分支发布，比如 `main` 或 `gh-pages`，那它就不会按上面的 Actions 流程来部署。配置不是心灵感应，必须让它们说的是同一种语言。

## 再次推送并观察部署

添加 workflow 后，提交并推送：

```powershell
git add .
git commit -m "add github pages deployment"
git push
```

然后打开 GitHub 仓库的：

```text
Actions
```

你应该能看到一个名为：

```text
Deploy Hugo site to GitHub Pages
```

的 workflow 正在执行。

执行过程通常包括两个 job：

- `build`
- `deploy`

`build` 成功说明 Hugo 构建通过。  
`deploy` 成功说明 GitHub Pages 发布成功。

## 部署完成后访问网站

如果是用户主页仓库：

```text
https://你的用户名.github.io/
```

如果是普通项目仓库：

```text
https://你的用户名.github.io/仓库名/
```

第一次部署可能需要等一会儿。不要看到页面没立刻出现就马上重写配置。部署系统不是即时泡面，虽然它偶尔也会表现得像没加热成功。

## 这套流程的原理

部署流程可以分成两个阶段。

## 阶段一：构建

构建发生在 GitHub Actions 里。

GitHub 会临时分配一台机器，通常是 Ubuntu 环境，然后按 `.github/workflows/hugo.yml` 执行步骤。

这台机器会：

1. 拉取你的仓库代码
2. 拉取主题子模块
3. 安装 Hugo
4. 执行 `hugo --minify`
5. 得到 `public/`

构建结束后，这台临时机器会被释放。

所以 GitHub 并不会一直运行 Hugo。Hugo 只在构建时短暂执行一次。

## 阶段二：托管

托管发生在 GitHub Pages 里。

GitHub Pages 拿到 `public/` 后，只需要把里面的静态文件暴露给浏览器访问。

用户访问你的博客时，过程大概是：

```text
用户打开浏览器
    -> 请求 https://你的用户名.github.io/
    -> GitHub Pages 返回 index.html
    -> 浏览器继续加载 CSS、JS、图片
    -> 页面显示出来
```

这个过程中没有数据库查询，没有服务端模板渲染，也没有后端接口参与。

所以静态博客通常有这些优点：

- 部署简单
- 成本低
- 访问速度快
- 安全风险相对小
- 很适合文章、文档、作品集

但它也有明显限制：

- 不能直接写服务端登录逻辑
- 不能直接连接数据库
- 不能直接在 GitHub Pages 上运行后台任务
- 动态评论、搜索、统计等功能通常要依赖第三方服务或前端方案

## 常见问题

下面这些问题很常见。提前知道它们，可以少浪费很多时间。

## Actions 没有触发

先检查 workflow 里的分支：

```yaml
on:
  push:
    branches:
      - master
```

如果这里写的是 `master`，但你推送到 `main`，它就不会触发。

解决方式有两个：

- 把代码推送到 `master`
- 把 workflow 里的 `master` 改成 `main`

二选一即可，不要两个都改到一半。

## Hugo 构建失败

常见原因包括：

- Markdown front matter 写错
- 主题没有拉下来
- 模板语法错误
- 配置文件格式错误
- 某些文章引用了不存在的资源

如果报错里出现 theme 相关内容，优先检查：

```yaml
with:
  submodules: true
```

以及 `.gitmodules` 是否正确。

## 页面打开了，但没有样式

这通常是 `baseURL` 或部署路径不对。

如果网站实际地址是：

```text
https://你的用户名.github.io/blog/
```

但 `baseURL` 写成：

```toml
baseURL = 'https://你的用户名.github.io/'
```

就可能导致 CSS、图片、链接路径错误。

普通项目仓库一般要带仓库名：

```toml
baseURL = 'https://你的用户名.github.io/blog/'
```

用户主页仓库一般不带仓库名：

```toml
baseURL = 'https://你的用户名.github.io/'
```

## 文章没有显示

检查文章 front matter：

```toml
+++
date = '2026-08-17T20:00:00+08:00'
draft = false
title = '文章标题'
+++
```

如果是：

```toml
draft = true
```

正式构建时默认不会发布这篇文章。

本地 `hugo server` 有时会使用额外参数显示草稿，但线上构建通常不会。不要让草稿状态偷偷替你决定文章是否存在。

## 图片路径错误

Hugo 中，放在 `static/` 下的文件会原样复制到站点根路径。

比如图片在：

```text
static/images/demo.png
```

Markdown 中通常这样引用：

```md
![示例图片](/images/demo.png)
```

不要写成本地磁盘路径：

```md
![示例图片](D:/Project/blog/static/images/demo.png)
```

浏览器访问的是网站路径，不认识你的本地磁盘。

## 是否需要提交 public 目录

通常不需要。

推荐做法是：

```text
源码提交到 GitHub
GitHub Actions 生成 public
GitHub Pages 发布 public
```

`public/` 是构建产物，不是源代码。把它提交进去，容易导致仓库混乱，也容易出现“本地构建结果”和“线上构建结果”不一致的问题。

## 小结

部署 Hugo 静态博客时，真正要理解的是这条链路：

```text
Hugo 负责生成
GitHub Actions 负责自动执行
GitHub Pages 负责托管结果
```

再展开就是：

```text
写 Markdown
    -> push 到 GitHub
    -> Actions 拉代码
    -> Actions 安装 Hugo
    -> Hugo 生成 public
    -> Actions 上传 public
    -> Pages 发布网站
```

只要明白这一点，很多问题就不再神秘：

- 样式丢了，多半看 `baseURL`
- Actions 没跑，多半看分支触发条件
- 主题找不到，多半看 submodule
- 文章不显示，多半看 `draft`
- GitHub Pages 不能跑后端，因为它只托管静态文件

所谓部署静态网站，本质不是“让 GitHub 运行你的项目”，而是“让 GitHub 自动生成并托管你的静态文件”。这个说法虽然不那么热血，但准确。技术问题上，准确通常比热血有用。
