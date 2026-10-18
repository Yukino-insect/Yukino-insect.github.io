+++
date = '2026-09-06T10:30:00+08:00'
draft = false
title = 'LaTeX 是什么：从公式排版到在本站渲染'
math = true
+++

写数学内容时，最先令人困扰的往往不是公式本身，而是怎样让公式**既写得准确，又显示得像公式**。把 `x²`、`Δy / Δx` 直接塞进正文当然也能勉强阅读；但一旦出现分式、上下标、极限、积分、矩阵或分段函数，纯文本很快就会失去结构。把复杂关系交给读者猜，并不算一种排版风格。

LaTeX 正是为此而生的标记语言。本网站现在已经配置好 Hugo 与 MathJax：文章只要声明 `math = true`，并用规定的定界符书写公式，就可以直接渲染 LaTeX。

## 先给结论

在本站写数学公式，只需要记住下面三件事：

1. 在文章 front matter 中加入 `math = true`。
2. 用 `$...$` 写行内公式。
3. 用独占一行的 `$$...$$` 写展示公式。

例如，下面的 Markdown：

```md
函数 $f(x) = x^2$ 在 $x = 3$ 处的导数是 $f'(3) = 6$。

$$
f'(x) = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h}
$$
```

会显示为：函数 $f(x) = x^2$ 在 $x = 3$ 处的导数是 $f'(3) = 6$。

$$
f'(x) = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h}
$$

这就是完整的作者侧用法。至于它为何能生效，后面再拆开说明。

## LaTeX 到底是什么

LaTeX 读作“Lay-tech”或“Lah-tech”。严格来说，它不是一个所见即所得的公式编辑器，而是一套基于 TeX 的文档排版标记系统。作者写的是带命令的纯文本；排版引擎再按照这些命令生成最终版面。

例如，作者写：

```latex
\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
```

渲染后得到：

$$
\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

它的重点不在于让源文件变得神秘，而在于让数学结构明确：

- `\frac{分子}{分母}` 表示分式；
- `^` 表示上标，`_` 表示下标；
- `\sqrt{...}` 表示平方根；
- `\sum`、`\int`、`\lim` 分别表示求和、积分、极限；
- `{...}` 用来界定一个命令的参数范围。

因此，`x^10` 的意思是 $x^{10}$，而不是 $x^1$ 后面恰好跟着一个普通的 `0`。当上标或下标不止一个字符时，花括号不能省略：写作 `$x^{10}$`、`$a_{n+1}$`，而不是 `$x^10$`、`$a_n+1$`。公式排版里最昂贵的错误，通常不是难，而是看起来只少了一个括号。

## 它适合做什么，不适合做什么

LaTeX 最适合表达有明确结构的数学、物理、统计和工程公式。例如：

$$
\int_a^b f(x)\,dx,
\qquad
\sum_{i=1}^{n} x_i,
\qquad
\begin{cases}
x^2, & x \ge 0, \\
-x, & x < 0.
\end{cases}
$$

它也常用于化学式、逻辑表达式和算法复杂度：$\mathrm{H_2O}$、$P \Rightarrow Q$、$O(n \log n)$。

但普通句子、文件路径、命令行和程序代码仍然应使用普通 Markdown 或代码围栏。不要因为已经有了公式渲染器，就把一整段中文塞进数学模式。数学模式是给结构化符号服务的，不是给段落文字提供一种更昂贵的字体。

## 最常用的 LaTeX 写法

下面这些足以覆盖多数博客文章。

| 目的 | 源码 | 渲染结果 |
| --- | --- | --- |
| 上标 | `$x^2$` | $x^2$ |
| 多字符上标 | `$x^{n+1}$` | $x^{n+1}$ |
| 下标 | `$a_n$` | $a_n$ |
| 分式 | `$\frac{a+b}{c}$` | $\frac{a+b}{c}$ |
| 根式 | `$\sqrt{x}$` | $\sqrt{x}$ |
| 希腊字母 | `$\alpha, \beta, \Delta, \varepsilon$` | $\alpha, \beta, \Delta, \varepsilon$ |
| 比较与趋近 | `$x \ne y,\ x \to 0,\ x \ge 0$` | $x \ne y,\ x \to 0,\ x \ge 0$ |
| 极限 | `$\lim_{x \to 0} \frac{\sin x}{x}$` | $\lim_{x \to 0} \frac{\sin x}{x}$ |
| 积分 | `$\int_a^b f(x)\,dx$` | $\int_a^b f(x)\,dx$ |

对于需要多行对齐的推导，使用 `aligned`：

```latex
$$
\begin{aligned}
(x+y)^2 &= x^2 + 2xy + y^2, \\
(x-y)^2 &= x^2 - 2xy + y^2.
\end{aligned}
$$
```

其显示结果为：

$$
\begin{aligned}
(x+y)^2 &= x^2 + 2xy + y^2, \\
(x-y)^2 &= x^2 - 2xy + y^2.
\end{aligned}
$$

`&` 是对齐点，`\\` 是换行。它们不是装饰；删掉其中一个，结果通常会很坦诚地告诉你什么叫语法错误。

## 当前网站如何渲染 LaTeX

本网站是 Hugo 静态站点。Hugo 负责把 Markdown 文章构建成 HTML；浏览器随后加载 MathJax，把 HTML 中保留下来的 LaTeX 转换成可见公式。整个路径如下：

```text
Markdown 中的 $...$ / $$...$$
        -> Hugo Goldmark 原样透传
        -> 生成页面保留 LaTeX 源码
        -> 浏览器加载 MathJax
        -> MathJax 排版为公式
```

这里有两个缺一不可的部分。

### 1. Hugo 必须保留公式源码

Markdown 渲染器本身并不理解 LaTeX 的全部语法。若让它按普通文本处理，反斜杠可能被当作 Markdown 转义字符，撇号也可能被替换成排版引号。比如公式中的 `\,` 是细小间距命令；如果反斜杠消失，它就只剩下一个逗号，含义已经变了。

因此，项目根目录的 `hugo.toml` 中启用了 Goldmark 的 `passthrough` 扩展：

```toml
[markup]
  [markup.goldmark]
    [markup.goldmark.extensions]
      [markup.goldmark.extensions.passthrough]
        enable = true
        [markup.goldmark.extensions.passthrough.delimiters]
          block = [['$$', '$$']]
          inline = [['$', '$']]
```

这段配置的含义很直接：被 `$...$` 或 `$$...$$` 包围的内容不再由 Markdown 改写，而是连同定界符一起原样输出到 HTML。没有这一步，公式源代码在到达浏览器之前就可能已经变形；后面再接入多好的渲染器也无济于事。

### 2. 浏览器必须有公式排版器

原样输出 LaTeX 仍只是文本。浏览器并不会因为看见 `\frac` 就突然具备数学修养，它需要 JavaScript 排版器。

本项目在 `layouts/partials/head-extra.html` 中按页面加载 MathJax 4：

```html
{{ if .Params.math }}
<script>
  MathJax = {
    tex: {
      inlineMath: { '[+]': [['$', '$']] },
      displayMath: { '[+]': [['$$', '$$']] },
      processEscapes: true
    }
  };
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-chtml.js"></script>
{{ end }}
```

关键点是 `{{ if .Params.math }}`。它读取文章 front matter 中的 `math` 参数：

- `math = true`：加载 MathJax，公式会渲染；
- 未设置或为 `false`：不加载 MathJax，普通文章没有额外网络请求。

因此，新建含公式的文章时，front matter 应写成：

```toml
+++
date = '2026-09-06T10:30:00+08:00'
draft = false
title = '文章标题'
math = true
+++
```

这里的前后 `+++` 是 TOML front matter 的边界，不是数学公式的一部分。把它写错，Hugo 会先拒绝构建；这个问题至少比数学上的歧义要容易诊断一些。

## 写一篇公式文章的完整示例

假设要写一篇关于等比数列求和的文章，可以这样写：

```md
+++
date = '2026-09-06T10:30:00+08:00'
draft = false
title = '等比数列求和公式'
math = true
+++

设首项为 $a$，公比为 $r$，且 $r \ne 1$。

前 $n$ 项和为：

$$
S_n = a + ar + ar^2 + \cdots + ar^{n-1}
    = \frac{a(1-r^n)}{1-r}
$$
```

其显示效果如下：设首项为 $a$，公比为 $r$，且 $r \ne 1$。

$$
S_n = a + ar + ar^2 + \cdots + ar^{n-1}
    = \frac{a(1-r^n)}{1-r}
$$

行内公式适合嵌在一句话里；公式过长、需要换行或值得读者单独停下来看的内容，使用展示公式更合适。不要把很长的公式硬塞进行内模式，页面宽度和读者耐心通常都不是无限的。

## 如何本地验证

写完后，在项目根目录运行：

```powershell
hugo server
```

浏览器打开本地地址后，检查三件事：

1. 页面中公式是否已经排版，而不是显示 `$`、`\frac` 等原始字符；
2. 浏览器开发者工具的 Network 面板中，MathJax 脚本是否加载成功；
3. 终端中是否有 Hugo 的 front matter 或模板错误。

也可以只构建一次：

```powershell
hugo --minify
```

这会生成 `public/` 目录。构建成功证明 Hugo 配置与 Markdown 语法至少能够通过；公式的最终可视效果则仍应在浏览器中确认，因为 MathJax 在客户端运行。

## 常见问题

### 公式原样显示，没有被渲染

先检查文章 front matter 是否有：

```toml
math = true
```

没有这个字段时，模板不会加载 MathJax。这并不是渲染器失职，而是页面没有提出请求。

接着检查公式是否使用了本站约定的定界符：行内是 `$...$`，块级是 `$$...$$`。`\(...\)` 和 `\[...\]` 虽然也是常见 LaTeX 定界符，但当前 Hugo 的透传配置没有为它们注册规则；在本站请优先使用 `$` 和 `$$`，以免把可选写法误当成已启用写法。

### 页面上有公式源码，但格式不对

先检查大括号是否成对，例如 `$x^{n+1}$`；再检查命令拼写，例如 `\frac`、`\sqrt`、`\lim`。LaTeX 命令通常区分精确拼写，`\Frac` 并不会因为“看起来也像分数”就自动被理解。

对于包含多行的 `aligned`、`cases` 等环境，确认每行除了最后一行外都以 `\\` 结束，并确保 `\begin{...}` 和 `\end{...}` 成对出现。

### 本地能看到源码，线上仍没有公式

MathJax 通过 jsDelivr CDN 从浏览器加载。应检查浏览器网络是否能访问：

```text
https://cdn.jsdelivr.net/npm/mathjax@4/tex-chtml.js
```

若 CDN 请求失败，Hugo 生成的页面仍然是正常的 HTML，只是没有客户端脚本把 LaTeX 排版出来。此时应排查网络、内容安全策略或 CDN 可用性；不要反过来怀疑 `\frac` 为什么突然失去工作意愿。

## 小结

LaTeX 是用文本表达数学结构的排版语言，而不是一套需要背诵的神秘咒语。对本站作者而言，实际规则可以再次压缩为：

```text
数学文章：front matter 中写 math = true
行内公式：$...$
展示公式：$$...$$
本地验证：hugo server 或 hugo --minify
```

网站之所以能正确显示这些公式，是因为 Hugo 的 Goldmark 透传配置负责**保留** LaTeX，MathJax 负责在浏览器中**排版** LaTeX。前者保护源码，后者生成视觉结果；少了任意一环，公式都只会停留在“看起来像代码”的阶段。这样的分工并不复杂，只是比把一段字符扔进 Markdown 后祈祷它自动变漂亮可靠得多。
