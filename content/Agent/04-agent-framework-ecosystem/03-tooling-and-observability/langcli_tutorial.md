+++
date = '2026-08-16T22:56:35+08:00'
draft = false
title = "LangCLI 教程：LangChain/LangGraph 命令行工具入门与进阶"
+++

当前日期：2026-08-16

> 先把名字说清楚。严格地说，今天 LangChain 生态里最常用、最活跃的 agent 命令行工具是 `langgraph-cli`，安装后提供 `langgraph` 命令。旧一些的 `langchain-cli` 安装后提供 `langchain` 命令，主要用于 LangChain Templates 和 LangServe 项目脚手架。很多资料会把这些统称为 LangCLI；这种叫法方便，但不够精确。嗯，概念偷懒的时候，后面通常就会由代码替你吃苦。

## 目录

1. LangCLI 在 LangChain 中的作用
2. 它解决的问题和满足的需求
3. 现代推荐路线：LangGraph CLI
4. 旧路线：LangChain CLI 与 LangServe
5. 基础使用步骤
6. 进阶使用步骤
7. `langgraph.json` 配置文件
8. 本地开发、Docker、本地服务和云部署的区别
9. 常见问题
10. 总结
11. 参考资料

## 1. LangCLI 在 LangChain 中的作用

LangCLI 可以理解为 LangChain 生态的命令行入口。它本身不是模型框架，也不是 agent 编排引擎，而是帮助你把项目创建、运行、调试、构建、部署这些工程动作标准化。

今天学习时建议把它拆成两条线：

| 名称 | 安装包 | 命令 | 当前主要用途 | 适合谁 |
| --- | --- | --- | --- | --- |
| LangGraph CLI | `langgraph-cli` | `langgraph` | 创建、运行、构建、部署 LangGraph/Agent Server 应用 | 新项目、agent 项目、需要 LangGraph Server 的项目 |
| LangChain CLI | `langchain-cli` | `langchain` | 创建 LangServe 项目、添加模板、运行 LangServe 服务 | 维护旧项目、学习 LangServe、暴露 LCEL Runnable API |

在现代 LangChain agent 工程中，LangGraph CLI 更重要。它负责把一个 LangGraph 应用作为 Agent Server 跑起来，暴露 threads、runs、assistants、store 等 API，并能接入 LangGraph Studio、LangSmith Deployment。

## 2. 它解决的问题和满足的需求

没有 CLI 时，一个 agent 项目从“能跑”到“能部署”中间会出现很多琐碎问题：

| 问题 | CLI 怎么帮你 |
| --- | --- |
| 不知道项目该怎么组织 | `langgraph new` 可从模板创建应用 |
| 不知道服务该加载哪个 graph | `langgraph.json` 统一声明 graph 入口 |
| 本地调试麻烦 | `langgraph dev` 提供热重载、本地 Agent Server、Studio URL |
| API 测试成本高 | 本地服务自动提供 API docs 和 SDK 可调用接口 |
| Docker 构建容易漏依赖 | `langgraph build` 按配置构建镜像 |
| 部署流程重复 | `langgraph deploy` 可将应用部署到 LangSmith Deployment |
| 生产服务配置分散 | 用 `.env`、`langgraph.json`、部署配置集中管理 |

换句话说，CLI 不是为了让你少写一行模型调用代码，而是为了让项目从 notebook 里搬出来后，仍然能被团队运行、调试、部署和维护。

## 3. 现代推荐路线：LangGraph CLI

LangGraph CLI 是当前更值得优先学习的工具。官方文档把它定义为用于构建和本地运行 Agent Server 的命令行工具。运行后，本地服务会暴露 runs、threads、assistants 等 API，并提供 checkpoint/storage 所需的支持服务。

常用命令如下：

| 命令 | 用途 |
| --- | --- |
| `langgraph --help` | 查看 CLI 是否安装成功 |
| `langgraph new` | 创建 LangGraph 应用模板 |
| `langgraph dev` | 以开发模式启动本地 Agent Server，无需 Docker，支持热重载 |
| `langgraph up` | 用 Docker 启动本地 LangGraph API server |
| `langgraph build -t my-agent` | 根据 `langgraph.json` 构建 Docker 镜像 |
| `langgraph dockerfile Dockerfile` | 生成 Dockerfile，便于自定义镜像流程 |
| `langgraph deploy` | 部署到 LangSmith Deployment |
| `langgraph deploy list` | 查看部署列表 |
| `langgraph deploy logs -f` | 查看部署日志 |
| `langgraph deploy delete <ID>` | 删除部署 |

学习顺序建议：

```text
langgraph new
  -> langgraph dev
  -> Studio 调试
  -> langgraph.json 调整
  -> langgraph build
  -> langgraph deploy 或自托管部署
```

## 4. 旧路线：LangChain CLI 与 LangServe

`langchain-cli` 是较早的 LangChain 官方 CLI，安装后使用 `langchain` 命令。它与 LangServe、LangChain Templates 绑定更紧密。

典型旧式流程：

```powershell
pip install -U langchain-cli
langchain app new my-app
cd my-app
poetry add langchain-openai
poetry run langchain serve --port=8100
```

LangServe 的核心思路是：把 LangChain 的 Runnable 或 LCEL chain 暴露成 FastAPI REST API。

适合继续使用 LangServe 的情况：

| 场景 | 是否适合 LangServe |
| --- | --- |
| 已经有旧 LangServe 项目 | 适合维护 |
| 只想快速暴露一个 LCEL chain API | 可以 |
| 要做有状态、多轮、可中断、可恢复 agent | 更建议 LangGraph + Agent Server |
| 要用 Studio 可视化调试图状态 | 更建议 LangGraph CLI |
| 要走 LangSmith Deployment | 更建议 LangGraph CLI |

如果你是新学 LangChain agent 工程，我建议把 `langchain-cli` 当作历史知识了解即可，主要精力放在 `langgraph-cli` 上。不是它没用，只是时代变了，工具链也该体面地往前走。

## 5. 基础使用步骤

下面以 Python 项目为主。

### 5.1 准备 Python 环境

LangGraph CLI 的本地开发模式通常要求 Python 3.11 或更高版本。你可以用 `uv` 或 `venv`。

```powershell
mkdir D:\learning\Python\agent\langcli_demo
cd D:\learning\Python\agent\langcli_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

如果你使用 `uv`：

```powershell
mkdir D:\learning\Python\agent\langcli_demo
cd D:\learning\Python\agent\langcli_demo
uv venv
.\.venv\Scripts\Activate.ps1
```

### 5.2 安装 LangGraph CLI

本地快速开发推荐安装 `inmem` extra：

```powershell
pip install -U "langgraph-cli[inmem]"
```

如果你准备使用 Docker 构建和 `langgraph up`，也可以安装基础包：

```powershell
pip install -U langgraph-cli
```

验证：

```powershell
langgraph --help
```

### 5.3 创建一个 LangGraph 应用

```powershell
langgraph new .\my_agent_app --template new-langgraph-project-python
cd .\my_agent_app
```

不指定模板时，CLI 通常会进入交互式选择。

```powershell
langgraph new .\my_agent_app
```

### 5.4 安装项目依赖

如果模板使用 `pyproject.toml`：

```powershell
pip install -e .
```

如果你使用 `uv`：

```powershell
uv sync
```

### 5.5 配置 `.env`

复制 `.env.example` 为 `.env`，填入你的模型供应商 key 和 LangSmith key。

```powershell
Copy-Item .env.example .env
```

示例：

```dotenv
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=langcli-demo
```

如果你只想本地测试 Studio，不想把 trace 发到 LangSmith，可以设置：

```dotenv
LANGSMITH_TRACING=false
```

### 5.6 启动本地开发服务

```powershell
langgraph dev
```

默认情况下，它会在本机启动 Agent Server，常见地址是：

```text
API: http://127.0.0.1:2024
API Docs: http://127.0.0.1:2024/docs
Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

如果端口冲突：

```powershell
langgraph dev --port 2025
```

如果浏览器不允许 Studio 连接 localhost，尤其是 Safari，可试：

```powershell
langgraph dev --tunnel
```

### 5.7 测试 API

安装 SDK：

```powershell
pip install -U langgraph-sdk
```

同步调用示意：

```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://127.0.0.1:2024")

thread = client.threads.create()
assistant = client.assistants.search()[0]

result = client.runs.wait(
    thread["thread_id"],
    assistant["assistant_id"],
    input={"messages": [{"role": "user", "content": "你好，请简单介绍 LangGraph。"}]},
)

print(result)
```

具体输入结构取决于你的 graph state。这里的 `messages` 只是常见聊天 agent 的例子。

## 6. 进阶使用步骤

### 6.1 维护 `langgraph.json`

`langgraph.json` 是 CLI 能否理解你的项目的关键。最小配置通常长这样：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/agent/graph.py:graph"
  },
  "env": ".env"
}
```

这里最重要的是：

| 字段 | 含义 |
| --- | --- |
| `dependencies` | 服务启动或构建镜像时要安装的依赖来源 |
| `graphs` | graph 名称到 Python 对象路径的映射 |
| `env` | 环境变量文件或环境变量字典 |
| `python_version` | 指定运行 Python 版本，如 `3.11`、`3.12`、`3.13` |
| `auth` | 自定义鉴权处理器 |
| `store` | 长期记忆、语义检索和 TTL 配置 |
| `checkpointer` | checkpoint 后端和过期策略 |
| `http` | HTTP 路由、middleware、headers 等服务行为 |

路径格式常见为：

```text
./包名/文件.py:变量名
./包名/文件.py:工厂函数名
```

推荐导出已经编译好的 graph：

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(dict)

def node(state: dict) -> dict:
    return state

builder.add_node("node", node)
builder.add_edge(START, "node")
builder.add_edge("node", END)

graph = builder.compile()
```

### 6.2 使用不同配置文件

开发、测试、生产可能用不同 graph 或 env。

```powershell
langgraph dev -c langgraph.dev.json
langgraph build -c langgraph.prod.json -t my-agent:prod
```

### 6.3 热重载与调试

开发时：

```powershell
langgraph dev --debug-port 5678
```

让服务等待调试器连接：

```powershell
langgraph dev --debug-port 5678 --wait-for-client
```

适合排查：

| 问题 | 调试方式 |
| --- | --- |
| 节点没有执行 | 在节点函数打断点 |
| state 字段丢失 | 检查 reducer 和返回 dict |
| 工具调用参数异常 | 在 tool 或 model node 上打断点 |
| 条件边跳转错误 | 打断点看 routing 函数返回值 |

### 6.4 构建 Docker 镜像

```powershell
langgraph build -t my-agent:local
```

指定平台：

```powershell
langgraph build -t my-agent:prod --platform linux/amd64
```

生成 Dockerfile：

```powershell
langgraph dockerfile Dockerfile
```

注意：如果你修改了 `langgraph.json`，需要重新生成 Dockerfile，否则 Dockerfile 不会自动同步这些变化。

### 6.5 使用 `langgraph up`

`langgraph dev` 是轻量开发服务器，不需要 Docker；`langgraph up` 会通过 Docker 启动更接近部署形态的 API server。

```powershell
langgraph up --port 8123
```

等待服务启动：

```powershell
langgraph up --port 8123 --wait
```

使用已有镜像：

```powershell
langgraph up --image my-agent:local --port 8123
```

如果你有额外服务，例如本地 Redis、数据库、向量库，可以通过 docker compose 扩展：

```powershell
langgraph up -d docker-compose.yml --port 8123
```

### 6.6 部署到 LangSmith Deployment

准备 `.env`：

```dotenv
LANGSMITH_API_KEY=lsv2_...
OPENAI_API_KEY=sk-...
```

部署：

```powershell
langgraph deploy
```

指定部署名：

```powershell
$env:LANGSMITH_DEPLOYMENT_NAME="research-agent"
langgraph deploy
```

或者：

```powershell
langgraph deploy --name research-agent
```

查看部署：

```powershell
langgraph deploy list
```

查看日志：

```powershell
langgraph deploy logs -f --name research-agent
```

更新已有部署：

```powershell
langgraph deploy --deployment-id <deployment-id>
```

删除部署：

```powershell
langgraph deploy delete <deployment-id>
```

截至 2026-08-16，`langgraph deploy` 仍属于官方标注的 beta 能力，适合学习和采用，但生产流程里要关注版本更新、区域、计费和组织权限。

### 6.7 自定义鉴权

如果你要把 Agent Server 暴露给外部系统，不应默认裸奔。可以通过 `auth` 字段接入自定义鉴权。

示意：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "chat": "./chat/graph.py:graph"
  },
  "auth": {
    "path": "./auth.py:auth"
  }
}
```

思路：

1. 在 `auth.py` 里定义鉴权处理器。
2. 校验 `Authorization`、`X-API-Key` 或你自己的租户 token。
3. 把用户身份、租户、权限放进请求上下文。
4. 在 graph 节点或 server middleware 中读取身份信息。

### 6.8 生产配置最小化暴露面

开发时 `/docs`、`/info`、`/metrics` 很方便；生产时未必都应该公开。可以通过 `http` 配置禁用某些内置路由。

示意：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "chat": "./chat/graph.py:graph"
  },
  "http": {
    "disable_meta": true
  }
}
```

禁用元信息路由后，`/ok` 健康检查仍可保留给 Kubernetes 等编排系统使用。

## 7. `langgraph.json` 配置文件

### 7.1 最小 Python 项目结构

```text
my-agent/
  agent/
    __init__.py
    graph.py
  .env
  pyproject.toml
  langgraph.json
```

`agent/graph.py`：

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    text: str

def echo(state: State) -> State:
    return {"text": state["text"]}

builder = StateGraph(State)
builder.add_node("echo", echo)
builder.add_edge(START, "echo")
builder.add_edge("echo", END)

graph = builder.compile()
```

`langgraph.json`：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "echo": "./agent/graph.py:graph"
  },
  "env": ".env",
  "python_version": "3.11"
}
```

### 7.2 多 graph 配置

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "chat": "./agent/chat.py:graph",
    "research": "./agent/research.py:graph",
    "summarizer": "./agent/summarizer.py:graph"
  },
  "env": ".env"
}
```

适合一个服务里提供多个 agent：

| graph | 用途 |
| --- | --- |
| `chat` | 普通多轮对话 |
| `research` | 深度研究、搜索、整理 |
| `summarizer` | 文档摘要 |

### 7.3 长期记忆与语义检索

如果 Agent Server 使用 store，你可以在配置里为 store 加 semantic index：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "memory_agent": "./agent/graph.py:graph"
  },
  "store": {
    "index": {
      "embed": "openai:text-embedding-3-small",
      "dims": 1536,
      "fields": ["$"]
    }
  }
}
```

也可以配置 TTL，让记忆自动过期：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "memory_agent": "./agent/graph.py:graph"
  },
  "store": {
    "ttl": {
      "refresh_on_read": true,
      "sweep_interval_minutes": 60,
      "default_ttl": 10080
    }
  }
}
```

这类配置更适合生产或准生产应用。学习阶段先理解 `graphs`、`dependencies`、`env` 即可。

## 8. 本地开发、Docker、本地服务和云部署的区别

| 方式 | 命令 | 依赖 | 适合场景 |
| --- | --- | --- | --- |
| 直接运行 Python | `python script.py` | 无 CLI 必需 | 学单个 graph 或节点 |
| 本地开发 Agent Server | `langgraph dev` | `langgraph-cli[inmem]` | 快速迭代、Studio 调试 |
| Docker 本地服务 | `langgraph up` | Docker、API key | 接近部署形态测试 |
| 构建镜像 | `langgraph build` | Docker | 自托管、CI/CD |
| LangSmith Cloud 部署 | `langgraph deploy` | LangSmith Deployment 权限 | 托管生产或测试环境 |

一个务实的学习路径：

1. 先用普通 Python 跑通 graph。
2. 用 `langgraph dev` 看 Studio、调 API。
3. 用 `langgraph.json` 固化服务入口。
4. 用 `langgraph build` 检查依赖和镜像是否完整。
5. 最后再考虑 `langgraph deploy` 或自托管。

## 9. 常见问题

### 9.1 `langgraph dev` 找不到 graph

优先检查：

1. `langgraph.json` 是否在当前目录。
2. `graphs` 路径是否写对。
3. Python 文件是否能被导入。
4. 导出的变量是否真的是 compiled graph。
5. 依赖是否已 `pip install -e .`。

### 9.2 修改代码后服务没变化

检查：

```powershell
langgraph dev
```

是否使用了默认热重载。如果你加了：

```powershell
langgraph dev --no-reload
```

那就需要手动重启服务。

### 9.3 `.env` 不生效

检查：

1. `langgraph.json` 里是否写了 `"env": ".env"`。
2. `.env` 是否在项目根目录。
3. key 名是否正确，比如 `LANGSMITH_API_KEY`、`OPENAI_API_KEY`。
4. PowerShell 当前 shell 里是否还有旧环境变量覆盖了 `.env`。

### 9.4 `langgraph build` 依赖缺失

常见原因是 `dependencies` 配错。不要把它写成：

```json
{
  "dependencies": ["requirements.txt"]
}
```

更常见写法是：

```json
{
  "dependencies": ["."]
}
```

或者：

```json
{
  "dependencies": ["./"]
}
```

意思是让 CLI 从目录中的 `pyproject.toml`、`setup.py` 或 `requirements.txt` 推断依赖。

### 9.5 什么时候还学 `langchain-cli`

如果你遇到这些内容，就可以学：

1. 旧教程里出现 `langchain app new`。
2. 项目使用 LangServe。
3. 你只想把一个 LCEL Runnable 暴露成 FastAPI。
4. 公司已有 LangServe 服务需要维护。

如果你正在学习现代 agent，则优先学 `langgraph` 命令。

## 10. 总结

LangCLI 不是一个单一产品名，而是学习时常见的统称。现代 LangChain agent 工程里，真正应该重点掌握的是 `langgraph-cli` 和它提供的 `langgraph` 命令。

你需要记住五件事：

1. `langgraph new` 用于创建应用。
2. `langgraph dev` 用于本地开发和 Studio 调试。
3. `langgraph.json` 是 Agent Server 加载 graph 的核心配置。
4. `langgraph build` 和 `langgraph up` 让你进入 Docker/部署形态。
5. `langgraph deploy` 负责部署到 LangSmith Deployment，但要注意权限、计费、区域和 beta 状态。

旧的 `langchain-cli` 仍有价值，但它主要服务于 LangServe 和 Templates。新项目不必从那里开始。工具的演进就是这样，认真分辨一下，并不会让人变得啰嗦，只会少走弯路。

## 11. 参考资料

- LangGraph CLI 官方文档：https://docs.langchain.com/langsmith/cli
- LangGraph 本地服务官方教程：https://docs.langchain.com/oss/python/langgraph/local-server
- LangSmith Deployment 官方文档：https://docs.langchain.com/langsmith/deployment
- LangSmith 应用结构官方文档：https://docs.langchain.com/langsmith/application-structure
- LangServe GitHub 文档中的 LangChain CLI 部分：https://github.com/langchain-ai/langserve
- `langchain-cli` PyPI 页面：https://pypi.org/project/langchain-cli/
