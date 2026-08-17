# 博客维护说明

这个项目使用 `Hugo` 构建，主题为 `ananke`，但首页、分类页、文章页都使用了自定义模板。

站点维护的核心原则是：内容放在 `content/`，分类结构和图片资源放在 `data/`，模板只负责渲染。不要为了改一个分类或一张图片去改模板，除非你确实是在调整页面结构。

文章排版与 Markdown 写作规范请看：
[文章写作规范.md](D:/Project/blog/文章写作规范.md)

## 框架管理原则

这个博客框架按职责分为四层。日常维护时先判断自己要改的是哪一层，不要把内容、分类、样式和构建产物混在一起处理。

```text
content/      写文章和分类入口页
data/         配置首页分类、分类图标、模块图标、背景图
layouts/      修改页面结构、卡片交互、文章页样式和 Markdown 渲染规则
static/       存放图片、favicon、额外 CSS 等静态资源
public/       Hugo 生成结果，不手动维护
```

管理规则：

1. 新增或修改文章，只动 `content/`。
2. 调整首页大类、二级分类、三级模块、系列 tab，只动 `data/topic_groups.yaml` 和对应的 `content/groups/.../_index.md`。
3. 替换首页图标、模块图标、背景图，只动 `data/*.yaml` 和 `static/images/...`。
4. 修改页面布局、hover 展开、文章阅读卡宽度、Markdown 链接解析，才动 `layouts/`。
5. 不要手动编辑 `public/`，它会被 `hugo` 或 `hugo --cleanDestinationDir` 重新生成。
6. 每次改完框架配置或模板，都运行 `hugo --cleanDestinationDir`；只写文章时也建议至少跑一次，避免 front matter 或链接错误。

当前自定义模板的职责：

```text
layouts/index.html                         首页大类卡片
layouts/groups/list.html                   泛化分类页、二级分类页、三级模块卡片、系列 tab
layouts/_default/list.html                 原始 content 目录列表页
layouts/_default/single.html               文章详情页和阅读卡
layouts/_default/_markup/render-link.html  Markdown 中相对 .md 链接转 Hugo permalink
layouts/partials/page-display-title.html   标题兜底：front matter title -> 正文 H1 -> 文件名
```

文章详情页阅读卡在 `layouts/_default/single.html` 中维护。当前正文阅读区按 Typora 常见默认宽度设置为 `860px`，外层卡片宽度会自动加上左右内边距；如果以后要调整阅读宽度，优先修改 `.post-card` 里的 `--post-card-content-width`。

## 目录结构

```text
content/                         文章内容
content/groups/                  首页泛化分类和二级分类入口页
data/topic_groups.yaml           首页一级分类、二级分类、三级模块配置
data/category_icons.yaml         首页图标和一级分类页顶部图片配置
data/module_icons.yaml           二级分类页中三级模块卡片共享图标池
data/home_backgrounds.yaml       首页首屏背景图配置
data/page_backgrounds.yaml       分类页、目录页、文章页共享背景图配置
layouts/index.html               首页模板
layouts/groups/list.html         泛化分类页与二级分类页模板
layouts/_default/list.html       原内容目录文章列表页模板
layouts/_default/single.html     文章详情页模板
layouts/_default/_markup/         Markdown 渲染钩子
layouts/partials/                 模板复用片段
static/images/avatar/            首页图标、分类页顶部图片、模块图标、目录页文章头像
static/images/cover/             首页、分类页、目录页、文章页背景图
static/images/posts/             推荐存放文章正文图片
```

## 常用命令

本地预览：

```powershell
hugo server
```

预览地址：

```text
http://localhost:1313/
```

只生成静态文件：

```powershell
hugo
```

清理并重新生成：

```powershell
hugo --cleanDestinationDir
```

## 分类结构

首页不直接展示 `content/` 下所有真实目录，而是展示 `data/topic_groups.yaml` 中配置的泛化分类。

当前首页一级分类是：

```text
计算机基础
Java 技术栈
数据库与检索
分布式架构
AI 工程
随笔杂谈
Python
Git
```

`工程实践` 分类已取消。`ProjectExperience` 等真实内容目录仍然可以作为普通内容目录存在，但不会出现在首页泛化分类中，除非你把它们配置到 `data/topic_groups.yaml`。

## 修改首页一级分类

编辑：

```text
data/topic_groups.yaml
```

一级分类结构示例：

```yaml
- slug: java-stack
  title: Java 技术栈
  subtitle: 语言、虚拟机、框架
  lead: Java 基础、JVM、并发、Spring 生态和持久层框架放在一起看，脉络会清楚得多。
  sections:
    - javase
    - jvm
    - juc
  lanes:
    - title: 运行时与并发
      slug: runtime-concurrency
      summary: JVM 内存、类加载、GC、锁、线程池与并发工具。
      modules:
        - title: JVM
          summary: 对象、类加载、GC、调优。
          sections:
            - jvm
```

字段说明：

```text
slug       URL 片段，例如 /groups/java-stack/
title      页面显示名称
subtitle   一级分类页顶部短说明
lead       一级分类页顶部介绍
sections   这个一级分类聚合哪些 content 目录
lanes      二级分类
modules    三级模块
```

注意：`sections` 里写的是 Hugo 识别到的 section key，通常是 `content/<目录名>/` 的小写形式。例如 `content/JavaSE/` 对应 `javase`。

配置和入口页必须成对维护：

```text
data/topic_groups.yaml 中的 group.slug
    -> content/groups/<group.slug>/_index.md

data/topic_groups.yaml 中的 lane.slug
    -> content/groups/<group.slug>/<lane.slug>/_index.md
```

例如：

```yaml
- slug: ai-engineering
  lanes:
    - slug: rag-agent
```

必须有：

```text
content/groups/ai-engineering/_index.md
content/groups/ai-engineering/rag-agent/_index.md
```

如果 `slug` 和 `content/groups` 目录不一致，页面会出现 `Page Not Found`。例如 `slug: python` 对应的是 `/groups/python/`，入口页就必须是 `content/groups/python/_index.md`。

## 新增专题章节

这里的“专题章节”分两类：普通专题和系列专题。普通专题适合直接把某个 `content/<目录>/` 下的文章列出来；系列专题适合像 `content/Agent/ai-course/` 这样有多级目录、每个子目录又是一章的课程。

### 新增普通专题

普通专题使用 `sections` 聚合文章。以 `content/RandomThoughts/` 对应的“随笔杂谈”为例：

```yaml
- slug: random-thoughts
  title: 随笔杂谈
  subtitle: 项目、方案、零散问题
  lead: 这里写一级分类页介绍。
  sections:
    - randomthoughts
  lanes:
    - title: 随笔索引
      slug: notes
      summary: 这里写二级分类说明。
      modules:
        - title: RandomThoughts
          summary: 这里写三级模块说明。
          sections:
            - randomthoughts
```

然后创建两个入口页：

```text
content/groups/random-thoughts/_index.md
content/groups/random-thoughts/notes/_index.md
```

一级入口页内容：

```toml
+++
title = "随笔杂谈"
group = "random-thoughts"
+++
```

二级入口页内容：

```toml
+++
title = "随笔索引"
group = "random-thoughts"
lane = "notes"
+++
```

页面效果是：进入一级分类后先看到二级分类卡片；进入二级分类后看到三级模块卡片；鼠标移到三级模块卡片上，才会展开文章列表。

如果只想收集某个目录的文章，同时排除它下面的某个系列目录，可以使用 `paths` 和 `excludePaths`。例如 `content/Agent/` 下既有普通 LangChain/LangGraph 文章，也有 `content/Agent/ai-course/` 系列课程时：

```yaml
modules:
  - title: LangChain 与 LangGraph
    summary: LangChain、LangGraph、LangSmith、CLI、Server 和 Prompt 工程相关笔记。
    paths:
      - Agent/
    excludePaths:
      - Agent/ai-course/
```

规则：

1. `paths` 写相对 `content/` 的目录路径。
2. `excludePaths` 可选，用来排除某些子目录。
3. `paths` 适合“同一个 Hugo section 下有普通文章和系列文章，需要分开展示”的情况。
4. 如果只是展示整个 `content/<目录>/`，优先使用 `sections`，配置更短。

### 新增系列专题

系列专题使用 `tabs`，适合下面这种目录：

```text
content/Agent/ai-course/
content/Agent/ai-course/README.md
content/Agent/ai-course/01-rag-basics/README.md
content/Agent/ai-course/01-rag-basics/01-what-is-rag.md
content/Agent/ai-course/02-knowledge-base/README.md
content/Agent/ai-course/02-knowledge-base/01-architecture-and-upload.md
```

在 `data/topic_groups.yaml` 的某个二级分类模块下配置：

```yaml
modules:
  - title: RAG 与 Agentic AI 工程课程
    summary: 按课程章节组织的系列文章。
    intro:
      title: 课程导读
      path: Agent/ai-course/README.md
    tabs:
      - title: RAG 基础
        path: Agent/ai-course/01-rag-basics/
      - title: 知识库建设
        path: Agent/ai-course/02-knowledge-base/
```

规则：

1. `path` 写相对 `content/` 的目录路径，不要以 `/` 开头也可以，模板会兼容。
2. `intro.path` 可选，用来指定整套系列的总导读文章，例如 `content/Agent/ai-course/README.md`；`intro.title` 是导读 tab 的显示名称。
3. 每个 `tabs` 项会收集该目录下的 Markdown 文章。
4. `README.md` 会被保留：如果写在 `intro.path` 中，它会出现在导读 tab 中，样式和普通文章链接一致；如果写在某个 tab 目录下，它会排在对应 tab 的最前面，适合作为本章导读或总览。
5. 页面标题优先读取 front matter 的 `title`；没有 `title` 时，会读取正文第一个 `# 一级标题`；再没有才退回文件名。
6. 系列专题卡片默认只显示模块标题，鼠标移到卡片上后才展开导读 tab、章节 tab 和文章列表；移动端没有 hover，列表会直接展开。

如果你不希望生成 `/readme/` 这样的文章 URL，可以把导读文件命名为 `00-overview.md`、`00-intro.md` 或 `00-导读.md`。这时它会按文件名排序进入列表。若继续使用 `README.md`，显示标题不会是 `README`，只要正文里有正常的 `# 标题` 即可。

## 新增二级分类页面

如果你在 `data/topic_groups.yaml` 中新增了一个二级分类：

```yaml
- title: 新方向
  slug: new-lane
  summary: 这里写说明。
  modules:
    - title: 新模块
      summary: 这里写模块说明。
      sections:
        - javase
```

还需要创建对应入口页：

```text
content/groups/<一级分类 slug>/<二级分类 slug>/_index.md
```

示例：

```text
content/groups/java-stack/new-lane/_index.md
```

内容：

```toml
+++
title = "新方向"
group = "java-stack"
lane = "new-lane"
+++
```

一级分类入口页位于：

```text
content/groups/<一级分类 slug>/_index.md
```

内容示例：

```toml
+++
title = "Java 技术栈"
group = "java-stack"
+++
```

## 分类图标与顶部图片

分类相关图片只从下面这个文件读取：

```text
data/category_icons.yaml
```

当前维护两组图片：

```yaml
primary:
  - /images/avatar/avatar1.jpg
  - /images/avatar/avatar2.jpg
  - /images/avatar/avatar3.jpg
  - /images/avatar/avatar4.jpg

secondary:
  - /images/avatar/avatar7.jpg
  - /images/avatar/avatar8.jpg
```

规则：

1. `primary` 的顺序对应首页一级分类顺序。
2. 首页有几个一级分类，`primary` 就建议配置几张图。
3. `secondary` 用于一级分类页顶部标题区图片、分类索引页图片等非首页分类图标场景，随机使用。
4. 二级分类卡片不显示图标。
5. 二级分类页顶部标题区不显示图片。
6. 如果首页图标不存在，首页会显示文字兜底头像。
7. 除首页一级分类图标外，同一页面出现多张图片时会先去重、再随机分配，尽量避免重复展示。

新增图标时：

1. 把图片放入：

```text
static/images/avatar/
```

2. 在 `data/category_icons.yaml` 中追加路径：

```yaml
primary:
  - /images/avatar/new-icon.jpg
```

如果是一级分类页顶部图片，就追加到 `secondary`。

## 三级模块卡片图标

二级分类页中的三级模块卡片图标由独立文件维护：

```text
data/module_icons.yaml
```

配置结构是一个共享图标池：

```yaml
icons:
  - /images/avatar/avatar1.jpg
  - /images/avatar/avatar2.jpg
  - /images/avatar/avatar3.jpg
```

规则：

1. 所有三级模块总卡片共享 `icons` 里的图片，不需要按一级分类或二级分类单独配置。
2. 每个二级分类页会先对 `icons` 去重、再随机分配，保证同一页内不重复使用同一张图。
3. 如果可用图标数量少于当前页面模块数量，缺少的模块会显示文字兜底头像。
4. 这里的图标只用于三级模块总卡片，不用于文章标题列表。

## 背景图配置

首页首屏背景图单独配置：

```text
data/home_backgrounds.yaml
```

示例：

```yaml
images:
  - /images/cover/cover1.jpg
  - /images/cover/cover2.jpg
```

分类页、二级分类页、原内容目录页、文章页共享背景图配置：

```text
data/page_backgrounds.yaml
```

示例：

```yaml
images:
  - /images/cover/cover1.jpg
  - /images/cover/cover2.jpg
```

新增背景图时：

1. 首页背景图放到 `static/images/cover/`，再写入 `data/home_backgrounds.yaml`。
2. 分类页和文章页背景图放到 `static/images/cover/`，再写入 `data/page_backgrounds.yaml`。
3. 背景图会从 YAML 中随机选择；首页背景点击切换时会先打乱图片池，并在一轮内避免重复。

## 新增文章

方式一：手动创建。

```text
content/JavaSE/Java异常机制.md
```

文章开头写 front matter：

```toml
+++
date = '2026-06-01T20:00:00+08:00'
draft = false
title = 'Java异常机制'
+++
```

正文不要再写同名一级标题。文章页模板会把 front matter 的 `title` 渲染成页面 H1，如果正文再写：

```md
# Java异常机制
```

页面就会出现连续重复标题。推荐正文从二级标题开始：

```md
## 异常是什么

正文内容……
```

方式二：使用 Hugo 命令。

```powershell
hugo new JavaSE/Java异常机制.md
```

生成模板来自：

```text
archetypes/default.md
```

文章列表排序默认按 `date` 倒序，新文章会排在前面。

## 文章正文图片

推荐把正文图片放到：

```text
static/images/posts/<分类名>/
```

示例：

```text
static/images/posts/javase/exception-flow.png
```

Markdown 引用：

```md
![异常流程图](/images/posts/javase/exception-flow.png)
```

## 原内容目录页

除了首页泛化分类，真实内容目录仍然可以直接访问，例如：

```text
/JavaSE/
/Mysql/
/Redis/
```

这些页面使用：

```text
layouts/_default/list.html
```

背景图同样来自：

```text
data/page_backgrounds.yaml
```

## 推荐维护流程

新增一篇已有目录下的文章：

1. 在 `content/<目录>/` 下新建 `.md`。
2. 写好 `title`、`date`、`draft`。
3. 正文图片放到 `static/images/posts/...`。
4. 运行 `hugo server` 预览。

新增一篇系列文章：

1. 找到系列目录，例如 `content/Agent/ai-course/01-rag-basics/`。
2. 新建按顺序命名的 Markdown，例如 `10-new-topic.md`。
3. 写好 front matter，正文从 `##` 开始。
4. 如果该章节 README 里维护了目录链接，同步追加一条相对链接。
5. 运行 `hugo --cleanDestinationDir`，确认 `.md` 链接被 render hook 转成真实页面链接。

新增一个首页一级分类：

1. 修改 `data/topic_groups.yaml`。
2. 创建 `content/groups/<一级分类 slug>/_index.md`。
3. 为每个二级分类创建 `content/groups/<一级分类 slug>/<二级分类 slug>/_index.md`。
4. 如需首页图标，修改 `data/category_icons.yaml` 的 `primary`。
5. 如需一级分类页顶部图片，修改 `data/category_icons.yaml` 的 `secondary`。
6. 如需二级分类页里的模块卡片图标，修改 `data/module_icons.yaml` 的共享图标池。
7. 运行 `hugo --cleanDestinationDir` 检查构建。

修改博客框架样式或交互：

1. 首页卡片改 `layouts/index.html`。
2. 分类页、模块卡片、hover 展开、系列 tab 改 `layouts/groups/list.html`。
3. 文章阅读页、阅读卡宽度、正文排版改 `layouts/_default/single.html`。
4. 原始内容目录列表页改 `layouts/_default/list.html`。
5. Markdown 链接渲染规则改 `layouts/_default/_markup/render-link.html`。
6. 标题兜底逻辑改 `layouts/partials/page-display-title.html`。
7. 改完运行 `hugo --cleanDestinationDir`，再检查至少一个首页、一个分类页、一个文章页。

新增或替换背景图：

1. 把图片放到对应 `static/images/...` 目录。
2. 修改 `data/home_backgrounds.yaml` 或 `data/page_backgrounds.yaml`。
3. 运行 `hugo server` 预览。

## 容易踩坑

1. 改了 `data/topic_groups.yaml` 里的二级分类 `slug`，但忘了同步改 `content/groups/.../_index.md`，页面会找不到对应分类数据。
2. `sections` 必须写 Hugo section key，通常是目录名小写。
3. 首页一级分类图标顺序由 `data/category_icons.yaml` 的 `primary` 决定，不是按文件名自动匹配。
4. 二级分类卡片不显示图标；三级模块卡片图标来自 `data/module_icons.yaml` 的共享图标池。
5. 除首页一级分类图标外，其它图片池都会去重后随机展示；如果图片池数量少于同页展示数量，超出的项会使用文字兜底。
6. 背景图必须写进 YAML，单纯把图片放进 `static/` 不会被页面随机到。
7. 宽表格和宽代码块会隐藏明显的滚动条，但仍可横向滚动查看。
8. Markdown 中相对 `.md` 链接由 `layouts/_default/_markup/render-link.html` 转换；如果目标文章不存在，链接会保持原样，点击时可能 404。
9. 文章必须尽量补齐 front matter；缺少 `title` 时虽然有兜底，但排序、元信息和页面标题都不够稳定。
10. 不要在已有 `title` 的文章正文开头重复写同名 `# 一级标题`，否则文章页会出现重复标题。
11. `paths` 和 `excludePaths` 写的是相对 `content/` 的路径，不要写成 `content/Agent/...`。
12. YAML 列表的 `-` 后面必须有空格，例如 `- Agent/ai-course/`，不要写成 `-Agent/ai-course/`。

## 修改后检查

每次改完建议至少运行：

```powershell
hugo --cleanDestinationDir
```

重点检查：

1. 首页是否只显示预期的一级分类。
2. 首页图标顺序是否符合 `data/category_icons.yaml`。
3. 一级分类页是否只显示二级分类卡片。
4. 二级分类页是否显示三级模块和文章列表。
5. 文章页代码块、表格是否没有明显底部滑条。
6. 新增图片是否能通过 `/images/...` 路径正常访问。
7. 系列导读和章节 README 是否都出现在预期 tab 中。
8. 文章内相对 Markdown 链接是否已经变成 `/xxx/yyy/` 形式。
