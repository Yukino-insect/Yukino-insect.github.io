# 博客维护说明

这个项目使用 `Hugo` 构建，主题为 `ananke`，但首页、分类页、文章页都使用了自定义模板。

站点维护的核心原则是：内容放在 `content/`，分类结构和图片资源放在 `data/`，模板只负责渲染。不要为了改一个分类或一张图片去改模板，除非你确实是在调整页面结构。

文章排版与 Markdown 写作规范请看：
[文章写作规范.md](D:/Project/blog/文章写作规范.md)

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
Python
Git
```

`工程实践` 分类已取消。`Git`、`ProjectExperience`、`RandomThoughts` 等真实内容目录仍然可以作为普通内容目录存在，但不会出现在首页泛化分类中。

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

新增一个首页一级分类：

1. 修改 `data/topic_groups.yaml`。
2. 创建 `content/groups/<一级分类 slug>/_index.md`。
3. 为每个二级分类创建 `content/groups/<一级分类 slug>/<二级分类 slug>/_index.md`。
4. 如需首页图标，修改 `data/category_icons.yaml` 的 `primary`。
5. 如需一级分类页顶部图片，修改 `data/category_icons.yaml` 的 `secondary`。
6. 如需二级分类页里的模块卡片图标，修改 `data/module_icons.yaml` 的共享图标池。
7. 运行 `hugo --cleanDestinationDir` 检查构建。

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
