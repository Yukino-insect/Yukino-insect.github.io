+++

date = '2026-08-17T21:17:41+08:00'
draft = false
title = 'uv 和 pip 有什么区别'

+++
> 写作时间：2026-08-17  
> 适合对象：已经会运行 Python，正在学习虚拟环境、依赖安装、项目管理的学习者。

## 先给结论

`pip` 和 `uv` 都和 Python 包管理有关，但它们不是同一种层级的工具。

`pip` 是 Python 的经典包安装器。它主要负责“把包安装到某个 Python 环境里”，最典型的命令是：

```powershell
py -m pip install requests
```

`uv` 是 Astral 开发的现代 Python 包与项目管理工具。它不仅能安装包，还能创建虚拟环境、管理项目依赖、生成锁文件、运行命令、运行一次性工具、安装 Python 版本，并提供兼容 `pip` 风格的 `uv pip` 子命令。

```powershell
uv add requests
uv run python main.py
```

所以，粗略地说：

| 问题 | 简短答案 |
|---|---|
| `pip` 是包管理器吗？ | 广义上是，准确地说更像“包安装器 / installer”。 |
| `uv` 是包管理器吗？ | 是，而且是“包管理 + 项目管理 + 环境管理 + Python 版本管理 + 工具运行”的综合工具。 |
| 二者都能安装 PyPI 包吗？ | 能。`pip install xxx` 和 `uv add xxx` / `uv pip install xxx` 都可以。 |
| `uv` 是官方替代 `pip` 吗？ | 不是官方强制替代品。`pip` 仍是 Python Packaging User Guide 推荐的安装器；`uv` 是第三方高性能工具。 |
| 新手应该先学哪个？ | 先理解 `pip + venv`，再学 `uv`。不然只是把困惑从一个命令换到另一个命令上。 |

## 它们分别是什么

### pip：Python 的包安装器

`pip` 的官方定位是 Python 的 package installer。它可以从 PyPI 或其他符合规范的包索引安装 Python 包。

常见用途：

```powershell
# 安装包
py -m pip install requests

# 安装指定版本
py -m pip install "django==5.0.6"

# 从 requirements.txt 安装
py -m pip install -r requirements.txt

# 卸载包
py -m pip uninstall requests

# 查看当前环境的包
py -m pip list

# 导出当前环境包列表
py -m pip freeze > requirements.txt
```

请注意：`pip` 操作的是“当前 Python 环境”。如果你没有使用虚拟环境，它可能会安装到系统 Python、用户 Python、IDE 使用的 Python，或者某个你自己都不太记得的 Python 解释器里。于是“我明明安装了，为什么 import 不到”这种悲剧就出现了。原因并不神秘，只是环境不是同一个。

更稳妥的写法是：

```powershell
py -m pip install requests
```

而不是：

```powershell
pip install requests
```

因为 `py -m pip` 明确使用 Windows Python Launcher 选择到的 Python 来运行 pip，减少 `pip` 命令指向错误环境的概率。

### uv：现代 Python 包与项目管理工具

`uv` 是 Astral 开发的工具，使用 Rust 编写。它的定位比 `pip` 大得多。

它可以做这些事情：

| 能力 | uv 命令示例 | 大致替代或覆盖的传统工具 |
|---|---|---|
| 创建虚拟环境 | `uv venv` | `venv` / `virtualenv` |
| 安装包到环境 | `uv pip install requests` | `pip` |
| 管理项目依赖 | `uv add requests` / `uv remove requests` | Poetry、PDM、部分 pip 工作流 |
| 同步环境 | `uv sync` | `pip install -r ...`、`pip-tools` 的部分工作流 |
| 生成锁文件 | `uv lock` | `pip-tools`、Poetry lock |
| 运行项目命令 | `uv run python main.py` | 手动激活虚拟环境后运行 |
| 管理 Python 版本 | `uv python install 3.12` | `pyenv` 的部分场景 |
| 运行命令行工具 | `uvx ruff check .` | `pipx run` |
| 构建/发布包 | `uv build` / `uv publish` | `build` / `twine` 的部分场景 |

也就是说，`uv` 不只是“更快的 pip”。如果只这样理解，也不是不行，但未免太委屈它了。

## 它们的出生

### pip 的出生

`pip` 出现在 2008 年，由 Ian Bicking 创建，目标是作为 `easy_install` 的替代品。

更精确地说：

| 时间 | 事件 |
|---|---|
| 2004 年 | `setuptools` 出现，其中包含 `easy_install`。 |
| 2007 年 | Ian Bicking 创建 `virtualenv`，解决 Python 环境隔离问题。 |
| 2008 年 | Ian Bicking 创建 `pip`，作为 `easy_install` 的替代方案。 |
| 2008-10-28 | Ian Bicking 发文宣布把 `pyinstall` 改名为 `pip`。 |
| 2011-02-28 | PyPA 创建，接手维护 `pip` 和 `virtualenv` 等项目。 |
| Python 3.4 起 | 标准库的 `ensurepip` 让 Python 能更方便地自带或引导安装 pip。 |

`pip` 这个名字常被解释为递归缩写：`Pip Installs Packages`。这种命名方式有点程序员式的自得其乐，不过至少比“pyinstall”更短，算是它做对的一件事。

### uv 的出生

`uv` 由 Astral 发布。Astral 也是 `Ruff` 背后的团队。

更精确地说：

| 时间 | 事件 |
|---|---|
| 2024-02-15 | Astral 发布 `uv`，定位为使用 Rust 编写的高速 Python 包解析器和安装器。 |
| 初始目标 | 替代常见的 `pip` 与 `pip-tools` 工作流，提供 `uv pip` 兼容接口。 |
| 设计方向 | 逐步发展为类似 Rust `Cargo` 的统一 Python 项目与包管理工具。 |
| 后续扩展 | 加强项目管理、锁文件、Python 版本管理、工具运行、构建发布等能力。 |

`uv` 的出现背景很清楚：Python 包管理长期由很多工具拼起来完成，例如 `pip`、`venv`、`pip-tools`、`pipx`、`pyenv`、`poetry`、`twine`。这些工具各有价值，但组合起来对初学者并不友好。`uv` 想把很多常见工作流收束到一个速度很快的单一工具里。

## 核心区别

### 1. 定位不同

`pip` 的核心问题是：

> 我想把某个包安装进当前 Python 环境。

`uv` 的核心问题更大：

> 我想管理一个 Python 项目的依赖、环境、运行方式、Python 版本和工具链。

所以当你运行：

```powershell
py -m pip install requests
```

你是在对当前环境说：请安装 `requests`。

而当你运行：

```powershell
uv add requests
```

你是在对当前项目说：请把 `requests` 记录为项目依赖，更新 `pyproject.toml` 和锁文件，并让环境和项目声明保持一致。

这是思维方式的差别，不只是命令换了个名字。

### 2. 环境管理方式不同

传统 `pip` 工作流通常是：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install requests
python main.py
```

这里你需要自己：

1. 创建虚拟环境。
2. 激活虚拟环境。
3. 用 pip 安装包。
4. 确认运行代码时用的是同一个环境。

`uv` 项目工作流通常是：

```powershell
uv init demo
cd demo
uv add requests
uv run python main.py
```

`uv run` 会在项目环境中运行命令。很多时候你甚至不需要手动激活 `.venv`。

这不是说激活虚拟环境过时了，而是 `uv` 把“进入正确环境”这件事自动化了许多。

### 3. 依赖声明不同

`pip` 常见依赖文件是：

```text
requirements.txt
```

里面可能是：

```text
requests==2.32.3
pandas==2.2.2
```

`requirements.txt` 简单、通用、历史悠久。很多部署平台、教程和老项目都支持它。

`uv` 更推荐现代项目格式：

```text
pyproject.toml
uv.lock
```

其中：

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | 描述项目元数据、直接依赖、构建系统等。 |
| `uv.lock` | 锁定解析后的完整依赖版本，使环境更可复现。 |

例如：

```powershell
uv add requests
```

会把 `requests` 写进 `pyproject.toml`，并更新 `uv.lock`。

而：

```powershell
uv sync
```

会按照锁文件同步当前环境。

### 4. 速度不同

`uv` 的一个显著卖点是快。它用 Rust 编写，并使用全局缓存、并发下载、快速依赖解析等方式来提升速度。

在很多项目里，`uv` 比传统 `pip` 工作流快很多，尤其是：

| 场景 | uv 的优势 |
|---|---|
| CI 里频繁重建环境 | 缓存和解析速度明显有帮助。 |
| 大项目依赖很多 | 解析和安装更快。 |
| 多个项目共享相同依赖 | 全局缓存减少重复下载和占用。 |
| 频繁创建临时环境 | `uv run` / `uvx` 很方便。 |

不过要诚实一点：如果你只是偶尔安装一个很小的包，`pip` 和 `uv` 的体感差距未必重要。工具不是用来崇拜的，是用来减少麻烦的。

### 5. 锁文件与可复现性不同

`pip` 本身可以通过固定版本实现一定程度的可复现：

```text
requests==2.32.3
urllib3==2.2.2
certifi==2024.7.4
```

然后：

```powershell
py -m pip install -r requirements.txt
```

但 `pip` 本身不提供像 `uv.lock` 那样的项目级锁文件机制。传统上，如果你想把抽象依赖解析成完整锁定依赖，经常会搭配 `pip-tools`：

```text
requirements.in  ->  requirements.txt
```

`uv` 则把这部分做进了自己的项目工作流：

```powershell
uv lock
uv sync
```

这也是为什么 `uv` 更像一个项目管理器，而不是单纯安装器。

### 6. Python 版本管理不同

`pip` 不管理 Python 解释器版本。它是某个 Python 环境里的安装器。

也就是说，`pip` 不能替你安装 Python 3.12、3.13，也不能替项目固定 Python 版本。你需要自己安装 Python，或使用 `pyenv`、Windows Python Launcher、conda 等工具。

`uv` 可以管理 Python 版本：

```powershell
uv python install 3.12
uv python pin 3.12
uv run python --version
```

这对多项目开发很有价值。一个项目用 3.11，另一个项目用 3.12，这很常见；总不能每次都靠记忆力维持工程秩序，人的记忆力并没有那么值得信任。

## 命令对照表

### 安装包

pip：

```powershell
py -m pip install requests
```

uv，项目模式：

```powershell
uv add requests
```

uv，兼容 pip 模式：

```powershell
uv pip install requests
```

区别：

| 命令 | 含义 |
|---|---|
| `py -m pip install requests` | 安装到当前 Python 环境，不自动更新项目依赖声明。 |
| `uv add requests` | 添加为项目依赖，更新 `pyproject.toml` / `uv.lock`，并同步环境。 |
| `uv pip install requests` | 按接近 pip 的方式安装到环境，适合迁移旧工作流。 |

### 创建虚拟环境

pip 本身不创建虚拟环境，通常搭配 `venv`：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

uv：

```powershell
uv venv
```

### 运行项目代码

传统方式：

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

uv：

```powershell
uv run python main.py
```

### 导出依赖

pip：

```powershell
py -m pip freeze > requirements.txt
```

uv 的 pip 兼容方式：

```powershell
uv pip freeze > requirements.txt
```

uv 项目方式：

```powershell
uv lock
```

### 根据依赖文件安装

pip：

```powershell
py -m pip install -r requirements.txt
```

uv pip 兼容方式：

```powershell
uv pip install -r requirements.txt
```

uv 同步锁文件：

```powershell
uv sync
```

### 运行一次性命令行工具

传统方式可能要先安装：

```powershell
py -m pip install ruff
ruff check .
```

uv：

```powershell
uvx ruff check .
```

`uvx` 会在隔离环境里运行工具。适合临时使用 `ruff`、`black`、`mypy`、`pytest` 等命令行工具。

## 三种典型工作流

### 工作流 1：经典 pip + venv

适合：

| 场景 | 原因 |
|---|---|
| 初学 Python 基础 | 能清楚理解解释器、环境、包安装之间的关系。 |
| 老项目 | 很多项目仍然使用 `requirements.txt`。 |
| 教程/平台只写 pip | 跟随材料时少一些变量。 |

示例：

```powershell
mkdir demo-pip
cd demo-pip
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install requests
py -m pip freeze > requirements.txt
python -c "import requests; print(requests.__version__)"
```

目录大概是：

```text
demo-pip/
  .venv/
  requirements.txt
```

### 工作流 2：uv 项目模式

适合：

| 场景 | 原因 |
|---|---|
| 新项目 | 直接使用 `pyproject.toml` 和锁文件。 |
| 想要更快安装依赖 | uv 通常更快。 |
| 想减少手动激活虚拟环境 | `uv run` 可以直接在项目环境运行命令。 |
| 团队协作或 CI | `uv.lock` 让依赖更可复现。 |

示例：

```powershell
uv init demo-uv
cd demo-uv
uv add requests
uv run python -c "import requests; print(requests.__version__)"
```

目录大概是：

```text
demo-uv/
  .venv/
  main.py
  pyproject.toml
  uv.lock
```

### 工作流 3：uv pip 兼容模式

适合：

| 场景 | 原因 |
|---|---|
| 老项目迁移 | 不必立刻改掉 `requirements.txt`。 |
| 想保留 pip 命令习惯 | `uv pip install` 接近原来的命令语义。 |
| CI 加速 | 替换安装命令即可获得速度优势。 |

示例：

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv pip check
```

如果你已有：

```text
requirements.txt
```

可以先只把：

```powershell
py -m pip install -r requirements.txt
```

换成：

```powershell
uv pip install -r requirements.txt
```

这是一种比较温和的迁移方法。先让项目跑起来，再谈“工具链理想形态”，这比边迁移边制造新问题要体面得多。

## requirements.txt、pyproject.toml、uv.lock 的关系

### requirements.txt

传统 pip 世界最常见的依赖文件。

可能写成：

```text
requests
pandas>=2
```

也可能写成：

```text
requests==2.32.3
pandas==2.2.2
```

它的优点是简单、通用。缺点是表达项目元数据和锁定完整依赖图的能力有限。

### pyproject.toml

现代 Python 项目的核心配置文件。它不仅能描述依赖，也能描述项目名称、版本、构建系统、工具配置等。

示例：

```toml
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "requests>=2.32.0",
]
```

### uv.lock

`uv` 生成的锁文件，用来记录解析后的完整依赖结果。

你通常不手写它，而是让命令生成：

```powershell
uv lock
```

然后别人拿到项目后运行：

```powershell
uv sync
```

就可以根据锁文件创建一致的环境。

## 什么时候用 pip，什么时候用 uv

### 优先用 pip 的情况

| 场景 | 原因 |
|---|---|
| 正在学习 Python 最基础的包安装 | `pip + venv` 是基础知识，绕过去并不会让它消失。 |
| 教程、课程、考试明确要求 pip | 按要求来，别和题目争论人生。 |
| 目标环境只预装 pip | 服务器、教学环境、某些受限环境里 pip 更容易直接使用。 |
| 维护非常老的项目 | 老项目往往围绕 `requirements.txt` 和 pip 写了很多脚本。 |

### 优先用 uv 的情况

| 场景 | 原因 |
|---|---|
| 新建项目 | `uv init`、`uv add`、`uv sync` 的项目体验更完整。 |
| 依赖多，安装慢 | uv 的速度优势更明显。 |
| 希望锁定依赖 | `uv.lock` 让环境更可复现。 |
| 需要管理多个 Python 版本 | `uv python install` / `uv python pin` 很方便。 |
| 经常运行工具 | `uvx` 比先安装再运行更干净。 |
| CI/CD | 依赖恢复速度和锁文件一致性都很有价值。 |

### 一个实用建议

如果你是初学者，可以按这个顺序学：

1. 理解 Python 解释器：`py`、`python`、`python3` 到底指向谁。
2. 学会虚拟环境：`py -m venv .venv`。
3. 学会 pip：`py -m pip install`、`pip list`、`pip freeze`。
4. 学会现代项目格式：`pyproject.toml`。
5. 再学 uv：`uv init`、`uv add`、`uv run`、`uv sync`。

工具越高级，越需要你知道它替你做了什么。否则出了问题，你只能盯着终端沉默，而终端从来不会因为你沉默就变得仁慈。

## 常见误区

### 误区 1：uv 等于 pip 的新版

不准确。

`uv` 可以提供 `uv pip` 接口，覆盖很多 pip 工作流；但它不是 `pip` 的官方新版，也不是 Python 官方把 pip 改名成 uv。

准确说法：

> uv 是第三方现代 Python 包与项目管理工具，提供 pip 兼容接口，并扩展了项目、环境、锁文件和 Python 版本管理能力。

### 误区 2：有了 uv 就不用懂虚拟环境

不对。

`uv` 会帮你管理虚拟环境，但虚拟环境的概念仍然存在。`.venv` 仍然是隔离项目依赖的关键。

你可以少敲命令，但不能少理解概念。

### 误区 3：pip 安装慢，所以 pip 已经过时

不严谨。

`pip` 仍然是 Python 生态里最基础、最通用的安装器。它兼容性强、文档多、几乎所有 Python 开发者都认识。

`uv` 很好，但“新工具更好用”和“旧工具毫无价值”不是同一句话。把两者混为一谈，是偷懒。

### 误区 4：requirements.txt 和 uv.lock 是同一种东西

不完全是。

`requirements.txt` 可以是直接依赖，也可以是冻结后的完整依赖列表，具体取决于团队怎么用。

`uv.lock` 则是 uv 项目工作流里的锁文件，记录完整解析结果，目标是让环境同步更可复现。

## Windows 上的推荐命令

### 查看 Python

```powershell
py --version
py -0p
```

### pip 基础

```powershell
py -m pip --version
py -m pip install requests
py -m pip list
```

### 创建并激活虚拟环境

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 不允许激活脚本，可能需要调整执行策略：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 安装 uv

官方 Windows 安装方式之一：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

也可以用 pip 安装：

```powershell
py -m pip install uv
```

安装后检查：

```powershell
uv --version
```

## 一个完整对比例子

假设你要创建一个使用 `requests` 的小项目。

### 用 pip

```powershell
mkdir demo-pip
cd demo-pip
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install requests
New-Item -ItemType File main.py
python main.py
py -m pip freeze > requirements.txt
```

`main.py`：

```python
import requests

response = requests.get("https://www.python.org", timeout=10)
print(response.status_code)
```

别人拿到项目后：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
python main.py
```

### 用 uv

```powershell
uv init demo-uv
cd demo-uv
uv add requests
```

`main.py`：

```python
import requests

response = requests.get("https://www.python.org", timeout=10)
print(response.status_code)
```

运行：

```powershell
uv run python main.py
```

别人拿到项目后：

```powershell
uv sync
uv run python main.py
```

对比一下：

| 操作 | pip 工作流 | uv 工作流 |
|---|---|---|
| 创建环境 | 手动 `py -m venv .venv` | 通常由 uv 管理，也可 `uv venv` |
| 添加依赖 | `py -m pip install requests` | `uv add requests` |
| 记录依赖 | `pip freeze > requirements.txt` | 自动更新 `pyproject.toml` 和 `uv.lock` |
| 运行代码 | 激活环境后 `python main.py` | `uv run python main.py` |
| 复现环境 | `pip install -r requirements.txt` | `uv sync` |

## 和 conda 的关系

顺便说一句，`uv` 和 `pip` 都主要围绕 Python 包生态，尤其是 PyPI。

`conda` 的范围不同。它能管理 Python，也能管理很多非 Python 的二进制依赖，比如某些科学计算库、CUDA 相关组件、系统级动态库等。

所以：

| 工具 | 主要领域 |
|---|---|
| pip | 安装 Python 包 |
| uv | Python 包、项目、环境、工具、Python 版本管理 |
| conda | 跨语言包、二进制依赖、科学计算环境管理 |

如果你做 Web、脚本、普通 Python 应用，`uv` 很适合。  
如果你做复杂科学计算、GPU、地理信息、依赖大量本地二进制库的项目，`conda` 仍然有存在价值。

## 学习路线

### 第一步：确认自己在用哪个 Python

```powershell
py -0p
py --version
```

### 第二步：用 pip 练一次最基础流程

```powershell
mkdir learn-pip
cd learn-pip
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install requests
python -c "import requests; print(requests.__version__)"
py -m pip freeze > requirements.txt
```

### 第三步：用 uv 练一次现代项目流程

```powershell
uv init learn-uv
cd learn-uv
uv add requests
uv run python -c "import requests; print(requests.__version__)"
uv tree
```

### 第四步：观察文件变化

在 pip 项目里看：

```text
requirements.txt
```

在 uv 项目里看：

```text
pyproject.toml
uv.lock
```

真正的理解通常就从这里开始。命令只是表面，文件才说明工具的思路。

## 速查表

| 目标 | pip / 传统方式 | uv 方式 |
|---|---|---|
| 安装包 | `py -m pip install requests` | `uv add requests` |
| 卸载包 | `py -m pip uninstall requests` | `uv remove requests` |
| 创建虚拟环境 | `py -m venv .venv` | `uv venv` |
| 激活虚拟环境 | `.\.venv\Scripts\Activate.ps1` | 通常可用 `uv run` 代替手动激活 |
| 查看包列表 | `py -m pip list` | `uv pip list` |
| 导出当前包 | `py -m pip freeze > requirements.txt` | `uv pip freeze > requirements.txt` |
| 从 requirements 安装 | `py -m pip install -r requirements.txt` | `uv pip install -r requirements.txt` |
| 同步项目环境 | 依赖外部约定 | `uv sync` |
| 生成锁文件 | 通常搭配 `pip-tools` | `uv lock` |
| 运行项目命令 | 激活环境后运行 | `uv run ...` |
| 运行临时工具 | 先安装再运行，或用 pipx | `uvx ...` |
| 安装 Python 版本 | 不支持 | `uv python install 3.12` |

## 最后怎么选

如果你只是问“哪个更值得学”，我的答案是：

> 基础阶段：必须懂 `pip + venv`。  
> 新项目实践：优先尝试 `uv`。  
> 老项目维护：先尊重项目原来的依赖管理方式。  
> 团队协作和 CI：认真考虑 `uv lock` / `uv sync`。

一种比较稳妥的组合是：

1. 概念上理解 `pip`、`venv`、`requirements.txt`。
2. 实践中新项目使用 `uv init`、`uv add`、`uv run`。
3. 遇到老项目时用 `uv pip install -r requirements.txt` 加速，但不要急着重构整个依赖管理。

这样你既不会被旧工具困住，也不会因为追新工具而丢掉基本判断。对学习 Python 来说，这大概是比较体面的路线。

## 参考资料

- pip 官方文档：<https://pip.pypa.io/>
- Python Packaging User Guide - Installing Packages：<https://packaging.python.org/en/latest/tutorials/installing-packages/>
- PyPA Packaging History：<https://www.pypa.io/en/latest/history/>
- Ian Bicking：pyinstall is dead, long live pip!：<https://ianbicking.org/blog/2008/10/pyinstall-is-dead-long-live-pip.html>
- uv 官方文档：<https://docs.astral.sh/uv/>
- uv Features：<https://docs.astral.sh/uv/getting-started/features/>
- Astral 发布文章：uv: Python packaging in Rust：<https://astral.sh/blog/uv>
- uv GitHub 仓库：<https://github.com/astral-sh/uv>
