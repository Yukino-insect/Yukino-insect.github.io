# 项目协作说明

本项目是使用 Hugo 构建的中文技术博客。主题为 `ananke`，但首页、分类页和文章页使用自定义模板。日常维护应先区分内容、分类数据、模板与构建产物；不要为单纯的内容或分类调整去修改模板。

## 先看哪些文档

- 写文章或修改文章排版前，先遵循 [文章写作规范.md](文章写作规范.md)。
- 新增专题、分类、图片或调整页面结构前，先遵循 [README.md](README.md)。
- 若本文件与上述文档的具体实现细节冲突，以现有模板和配置的实际行为为准，并在修改后同步更新文档。

## 职责边界与构建

```text
content/      文章和分类入口页
data/         首页分类、专题、图标、背景图等数据配置
layouts/      页面结构、样式、交互和 Markdown 渲染规则
static/       图片、favicon、额外 CSS 等静态资源
public/       Hugo 生成产物，不手动维护
```

1. 新增或修改文章，通常只修改 `content/`；正文图片放入 `static/images/posts/<分类名>/`。
2. 调整首页一级分类、二级分类、三级模块或系列 tab，修改 `data/topic_groups.yaml`，并维护对应 `content/groups/.../_index.md` 入口页。
3. 修改首页分类图标、模块图标、背景图时，分别修改相应的 `data/*.yaml` 和 `static/images/...`；只把图片放进 `static/` 不会自动生效。
4. 只有页面结构、样式、交互或 Markdown 渲染规则需要变化时才修改 `layouts/`。
5. **绝不手动编辑 `public/`**；它会被 Hugo 重新生成。
6. 修改 `data/`、`layouts/`、分类入口页或静态资源后必须运行 `hugo --cleanDestinationDir`。只改文章时也应至少运行一次 `hugo` 或用 `hugo server` 预览，确认 front matter 和链接无误。

## 文章写作

当用户要求在本项目中新增或修改文章时，应将内容写成适合目标读者循序学习的**教程**，而不是对问题作简短的问答式回应。除非用户明确要求简短回答、提纲或 FAQ，否则应：

- 先说明背景、要解决的问题和核心结论；
- 从基础概念开始，逐步引入术语、机制和推导；
- 使用恰当的示例、流程或对照帮助理解；
- 解释关键结论的原因、适用边界和常见误解；
- 在结尾总结读者应掌握的要点。

### Front matter 与标题

每篇文章开头使用 TOML front matter，且必须补齐 `title`、`date` 和 `draft`：

```toml
+++
date = '2026-06-01T20:00:00+08:00'
draft = false
title = '文章标题'
+++
```

- 文章页会将 front matter 的 `title` 渲染为 H1；正文不要再写相同的 `# 一级标题`，正文通常从 `##` 开始。
- 标题不要跳级，主要使用 `##`、`###`、`####`；一篇文章只讲一个明确主题。
- 文章列表的默认顺序是 `date` 倒序，因此新文章需填写正确的 `date`。

### Markdown、代码、表格、图片与链接

- 段落、列表、引用和 fenced code block 前后均留空行；无序列表统一使用 `-`。
- 代码块使用三反引号并指定正确语言，例如 `json`、`http`、`java`、`bash`、`yaml`、`xml`、`sql`、`js`；无法判断时使用 `text`。纯 JSON 不要标为 `http`。
- 表格只放简短的对比、字段或映射关系；宽表格和宽代码块虽可横向滚动，仍应避免无意义的超长行和过多列。
- 图片使用有意义的英文或拼音文件名，必须写非空 alt 文本，并以 `/images/posts/...` 的站点绝对路径引用。
- Markdown 中的相对 `.md` 链接会由 `layouts/_default/_markup/render-link.html` 转为 Hugo permalink；目标文章必须存在，否则链接可能保持原样并导致 404。

### LaTeX / MathJax 公式

本项目同时需要 Hugo 保留公式分隔符和页面加载 MathJax，因此**使用公式的每篇文章都必须在 front matter 设置 `math = true`**：

```toml
+++
date = '2026-06-01T20:00:00+08:00'
draft = false
title = '公式示例'
math = true
+++
```

- 行内公式可使用 `$...$`。
- 块级公式必须使用 `$$` 包裹，且前后留空行；单个 `$...$` 不会作为块级公式渲染。

```md
当 $n > 0$ 时，有：

$$
\sum_{i=1}^{n} i = \frac{n(n + 1)}{2}
$$
```

不要在文章中自行改写 Hugo 的 MathJax 或 Goldmark 配置；站点已在 `hugo.toml` 和 `layouts/partials/head-extra.html` 配置 `$` / `$$` 分隔符。

## `data/topic_groups.yaml`：分类与专题

首页展示的是 `data/topic_groups.yaml` 中的泛化分类，不是 `content/` 下的所有真实目录。YAML 缩进和列表语法必须正确，列表项的 `-` 后必须有空格。

### 一级、二级分类与入口页必须成对

一级分类字段为 `slug`、`title`、`subtitle`、`lead`、`sections`、`lanes`；二级分类（lane）至少有 `title`、`slug`、`summary`、`modules`。

`slug` 决定 URL，同时必须与入口页路径保持一致：

```text
group.slug = <group>
  -> content/groups/<group>/_index.md

lane.slug = <lane>
  -> content/groups/<group>/<lane>/_index.md
```

一级入口页：

```toml
+++
title = "一级分类标题"
group = "<group-slug>"
+++
```

二级入口页：

```toml
+++
title = "二级分类标题"
group = "<group-slug>"
lane = "<lane-slug>"
+++
```

改动任何 `slug` 时，必须同步重命名或新建相应目录和 `_index.md`，否则会出现 `Page Not Found`。`sections` 写 Hugo section key，通常是 `content/<目录名>/` 的小写名称，例如 `content/JavaSE/` 对应 `javase`，不能写展示标题或任意路径。

### 普通专题：`sections`、`paths`、`excludePaths`

模块用 `sections` 聚合一个或多个完整 Hugo section：

```yaml
modules:
  - title: Java 基础
    summary: 类型、集合、异常与常用 API。
    sections:
      - java
```

- 展示完整 `content/<目录>/` 时优先使用 `sections`。
- 若同一 section 下要只收集某些路径，使用 `paths`；它写相对 `content/` 的路径，例如 `Agent/`，不能写成 `content/Agent/`，也不应以 `/` 开头。
- `excludePaths` 是可选项，用于排除 `paths` 下的子目录，例如 `Agent/ai-course/`。
- `paths` 的前缀匹配会包含子目录；规划专题时应避免彼此重叠，或明确使用 `excludePaths`。

```yaml
modules:
  - title: LangChain 与 LangGraph
    summary: 常规工程文章。
    paths:
      - Agent/
    excludePaths:
      - Agent/ai-course/
```

### 系列专题：`intro` 与 `tabs`

多章节课程或系列应在模块中使用 `tabs`，而不是用普通 `sections` 混在一起：

```yaml
modules:
  - title: RAG 与 Agentic AI 工程课程
    summary: 按章节组织的系列文章。
    intro:
      title: 课程导读
      path: Agent/ai-course/README.md
    tabs:
      - title: RAG 基础
        path: Agent/ai-course/01-rag-basics/
      - title: 知识库建设
        path: Agent/ai-course/02-knowledge-base/
```

- `intro.path` 可选，指向系列总导读；`tabs[].path` 指向章节目录。两者都写相对 `content/` 的路径。
- 每个 tab 收集目标目录下的 Markdown 文章；章节内的 `README.md` 会排在该 tab 最前，适合作为章节导读。
- 若不希望生成 `/readme/` URL，把导读文件命名为 `00-overview.md`、`00-intro.md` 或 `00-导读.md`，并以文件名顺序排序。
- 专题显示标题依次取 front matter 的 `title`、正文第一个 H1、文件名；仍应优先填写 `title`，不要依赖兜底。

### 专题文章排序

普通模块默认采用 `date-desc`，即按 `date` 倒序。对教程、课程、按编号递进的章节，必须显式配置 `sort: file`，并用可字典序排序的文件名前缀（如 `00-`、`01-`、`02-`、`10-`）保证顺序：

```yaml
modules:
  - title: TypeScript 类型系统
    summary: 从基础到工程建模。
    sort: file
    paths:
      - JSAndTS/02-typescript/
```

`sort: file` 按文件路径升序，而不是按日期或文章标题排序；编号不足十章时仍要补零，避免 `10-...` 排到 `2-...` 前面。

## 修改后核对

完成后运行构建并检查与改动相对应的页面：

```powershell
hugo --cleanDestinationDir
```

- 新文章：front matter、H1 是否未重复、公式/代码/表格/图片/相对 Markdown 链接是否正常。
- 分类或专题：首页分类、一级入口、二级入口、模块文章范围、系列 tab 和文章顺序是否符合配置。
- 图片：`/images/...` 地址是否可访问，且 YAML 中的路径和顺序是否正确。
- 模板：至少检查首页、一个分类页和一篇文章页。
