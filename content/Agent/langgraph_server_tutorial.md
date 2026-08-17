+++
date = '2026-08-16T22:56:35+08:00'
draft = false
title = "LangGraph Server 教程：把 LangGraph Agent 运行成可调用服务"
+++

当前日期：2026-08-16

LangGraph Server，也常在官方文档中以 Agent Server 的形式出现，是把 LangGraph 应用变成后端服务的运行时。它负责暴露 API、管理 assistants、threads、runs、checkpoint、store、后台任务和流式输出。换句话说，LangGraph 让你写出 agent 的“大脑和流程”，LangGraph Server 让它成为一个可以被前端、脚本、服务端系统稳定调用的后端。只写 graph 不部署服务，就像写好剧本但没人上台，多少有些浪费。

## 目录

1. LangGraph Server 在 LangChain 中的作用
2. 它解决的问题和满足的需求
3. 核心概念：graph、assistant、thread、run、store
4. 基础使用步骤：本地启动 Agent Server
5. 基础使用步骤：通过 SDK 和 REST 调用
6. 进阶使用步骤：应用结构与 `langgraph.json`
7. 进阶使用步骤：持久化、队列、流式输出和后台任务
8. 进阶使用步骤：部署方式
9. 生产化建议
10. 常见问题
11. 总结
12. 参考资料

## 1. LangGraph Server 在 LangChain 中的作用

LangGraph Server 是 LangGraph 应用的服务化运行层。它把一个或多个 graph 加载到 API server 中，并提供统一的远程调用接口。

在 LangChain 生态中的位置：

| 组件 | 作用 |
| --- | --- |
| LangChain | 模型、消息、工具、结构化输出等基础抽象 |
| LangGraph | 用 graph 编排有状态、多步骤、可循环 agent |
| LangGraph Server / Agent Server | 把 graph 作为服务运行，并提供 API |
| LangGraph CLI | 本地启动、构建、部署 Server |
| LangGraph Studio | 连接 Server 做可视化调试 |
| LangSmith | 追踪、评测、监控和部署管理 |

一句话：

```text
LangGraph Server = 面向 agent 工作负载的 API runtime。
```

## 2. 它解决的问题和满足的需求

一个 LangGraph graph 在 Python 进程里可以直接 `.invoke()`，但真实应用通常还需要：

1. 前端通过 HTTP 调用。
2. 多用户会话隔离。
3. 多轮上下文和 checkpoint。
4. 后台长任务。
5. 实时 streaming。
6. 多 assistant 配置。
7. 生产部署、扩缩容和日志。
8. 与 LangSmith tracing/evaluation 集成。

LangGraph Server 正是为这些问题设计的。

| 需求 | Server 提供的能力 |
| --- | --- |
| 多轮对话 | threads |
| 不同 agent 配置 | assistants |
| 发起一次任务 | runs |
| 恢复中断执行 | checkpoint/persistence |
| 长任务 | background runs / task queue |
| 实时输出 | streaming |
| 长期记忆 | store |
| 服务化调用 | REST API / SDK |
| 可视化调试 | Studio 连接 |
| 生产观测 | LangSmith traces |

## 3. 核心概念：graph、assistant、thread、run、store

### 3.1 Graph

Graph 是你的 agent 流程蓝图。它可以是：

1. LangGraph 编写的 StateGraph。
2. 已编译的 `CompiledGraph`。
3. 工厂函数动态创建的 graph。
4. 通过 Functional API 或 wrapper 接入的其他框架 agent。

在 Server 中部署 graph，通常要在 `langgraph.json` 里声明：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "research": "./agent/research.py:graph"
  },
  "env": ".env"
}
```

### 3.2 Assistant

Assistant 是 graph 的一个配置实例。它不是另一个 graph，而是同一个 graph 的不同运行配置。

例如：

| Assistant | Graph | 配置 |
| --- | --- | --- |
| `fast` | `research` | 小模型、少搜索 |
| `deep` | `research` | 大模型、多搜索 |
| `strict` | `research` | 强制 JSON 输出 |

### 3.3 Thread

Thread 是会话容器，用于保存一段多轮交互的状态。每次用户输入和 agent 响应可以作为一个 run 加入同一个 thread。

适合：

1. 聊天应用。
2. 多轮研究任务。
3. human-in-the-loop。
4. 需要 checkpoint 恢复的工作流。

### 3.4 Run

Run 是一次执行。你可以对某个 thread 和 assistant 发起 run。

运行模式可能包括：

1. 等待完成。
2. 流式读取事件。
3. 后台运行。
4. 中断后恢复。

### 3.5 Store

Store 是长期数据或 memory 的存储层。它不同于 thread state：

| 类型 | 生命周期 |
| --- | --- |
| Thread state | 某个 thread 内 |
| Checkpoint | graph 执行恢复所需 |
| Store | 可跨 thread 保存 |

Store 可以配合 semantic search、TTL 等能力。

## 4. 基础使用步骤：本地启动 Agent Server

### 4.1 准备环境

```powershell
mkdir D:\learning\Python\agent\server_demo
cd D:\learning\Python\agent\server_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4.2 安装 CLI

本地快速开发：

```powershell
pip install -U "langgraph-cli[inmem]"
```

### 4.3 创建应用

```powershell
langgraph new . --template new-langgraph-project-python
pip install -e .
```

如果使用 `uv`：

```powershell
uv sync
```

### 4.4 配置环境变量

```powershell
Copy-Item .env.example .env
```

`.env`：

```dotenv
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=server-demo
```

### 4.5 启动本地 Server

```powershell
langgraph dev
```

默认地址通常是：

```text
API: http://127.0.0.1:2024
API Docs: http://127.0.0.1:2024/docs
Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

`langgraph dev` 的特点：

1. 不需要 Docker。
2. 启动快。
3. 支持热重载。
4. 支持调试端口。
5. 适合开发和测试。
6. 本地状态保存在本地目录。

### 4.6 使用 Docker 方式启动

更接近部署环境：

```powershell
pip install -U langgraph-cli
langgraph up --port 8123
```

访问：

```text
http://127.0.0.1:8123/docs
```

`langgraph up` 会使用 Docker 启动 API server，并可以接入本地或外部 Postgres 等服务。它比 `dev` 更接近运行时形态，但开发迭代没有 `dev` 那么轻。

## 5. 基础使用步骤：通过 SDK 和 REST 调用

### 5.1 安装 SDK

```powershell
pip install -U langgraph-sdk
```

### 5.2 同步 SDK 调用

```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://127.0.0.1:2024")

assistants = client.assistants.search()
assistant_id = assistants[0]["assistant_id"]

thread = client.threads.create()
thread_id = thread["thread_id"]

result = client.runs.wait(
    thread_id,
    assistant_id,
    input={
        "messages": [
            {"role": "user", "content": "请解释 LangGraph Server 的作用。"}
        ]
    },
)

print(result)
```

### 5.3 异步 SDK 调用

```python
import asyncio
from langgraph_sdk import get_client

async def main():
    client = get_client(url="http://127.0.0.1:2024")
    assistants = await client.assistants.search()
    assistant_id = assistants[0]["assistant_id"]

    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    result = await client.runs.wait(
        thread_id,
        assistant_id,
        input={
            "messages": [
                {"role": "user", "content": "用两句话说明 Agent Server。"}
            ]
        },
    )
    print(result)

asyncio.run(main())
```

### 5.4 REST API 调用思路

本地服务启动后打开：

```text
http://127.0.0.1:2024/docs
```

你会看到 OpenAPI 文档。典型流程：

1. 创建 thread。
2. 查找或创建 assistant。
3. 对 thread + assistant 创建 run。
4. 等待结果或消费 stream。

REST 比 SDK 更通用，适合前端、非 Python 服务、Postman 测试；SDK 更省心，适合 Python/JS 项目。

### 5.5 输入格式取决于 state

如果你的 graph state 是：

```python
from typing import TypedDict

class State(TypedDict):
    question: str
```

输入应该像：

```json
{
  "question": "LangGraph Server 是什么？"
}
```

如果你的 graph 使用 messages：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "LangGraph Server 是什么？"
    }
  ]
}
```

不要把所有教程里的 `messages` 当成万能输入。它常见，但不是法律。幸好目前还没人为这个立法。

## 6. 进阶使用步骤：应用结构与 `langgraph.json`

### 6.1 推荐项目结构

```text
my-agent/
  agent/
    __init__.py
    state.py
    tools.py
    nodes.py
    graph.py
  tests/
    test_graph.py
  .env
  pyproject.toml
  langgraph.json
```

职责划分：

| 文件 | 作用 |
| --- | --- |
| `state.py` | 定义 State、reducer、配置 schema |
| `tools.py` | 定义工具 |
| `nodes.py` | 定义 graph 节点函数 |
| `graph.py` | 组装并 compile graph |
| `langgraph.json` | 告诉 Server 加载哪个 graph |
| `.env` | API key、环境变量 |

### 6.2 导出 compiled graph

推荐方式：

```python
# agent/graph.py
from langgraph.graph import StateGraph, START, END
from agent.state import State
from agent.nodes import call_model

builder = StateGraph(State)
builder.add_node("call_model", call_model)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", END)

graph = builder.compile()
```

`langgraph.json`：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent/graph.py:graph"
  },
  "env": ".env",
  "python_version": "3.11"
}
```

### 6.3 使用 graph 工厂函数

如果必须根据配置动态创建 graph，可以导出工厂函数：

```python
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

def make_graph(config: RunnableConfig):
    model_name = config.get("configurable", {}).get("model", "gpt-4.1-mini")

    builder = StateGraph(dict)

    def node(state: dict):
        return {"model": model_name, **state}

    builder.add_node("node", node)
    builder.add_edge(START, "node")
    builder.add_edge("node", END)
    return builder.compile()
```

配置：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent/graph.py:make_graph"
  },
  "env": ".env"
}
```

官方更推荐导出已经编译的 graph，因为 Server 可以在容器启动时加载一次并复用；工厂函数适合确实需要 per-run 定制的场景。

### 6.4 多 graph 服务

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "planner": "./agent/planner.py:graph",
    "researcher": "./agent/researcher.py:graph",
    "writer": "./agent/writer.py:graph"
  },
  "env": ".env"
}
```

适合把多个相关 agent 放在一个服务中，但不要无节制堆叠。graph 太多会让配置、权限、部署边界变得含糊。

## 7. 进阶使用步骤：持久化、队列、流式输出和后台任务

### 7.1 持久化与 checkpoint

Agent Server 需要保存：

1. assistants。
2. threads。
3. runs。
4. thread state。
5. long-term memory。
6. background task queue 状态。

LangSmith Cloud 部署会替你管理数据库。如果部署在自己的基础设施上，你需要自己配置 Postgres、Redis 等服务。

### 7.2 Postgres

在自托管 standalone server 中，`DATABASE_URI` 通常指向 Postgres。它用于保存 server 数据、thread state、long-term memory 和队列状态。

示意：

```dotenv
DATABASE_URI=postgres://user:password@localhost:5432/langgraph
```

同一个 Postgres 实例可以服务多个部署，但不同部署应该使用不同数据库，避免数据混用。

### 7.3 Redis

`REDIS_URI` 常用于 pub-sub broker，以支持后台 runs 的实时 streaming。

示意：

```dotenv
REDIS_URI=redis://localhost:6379/0
```

多个部署可以共享同一个 Redis 实例，但应使用不同 database number。

### 7.4 Streaming

Streaming 可以让客户端实时收到：

1. 节点进度。
2. 模型 token。
3. 工具调用事件。
4. 中间状态。
5. 最终结果。

适合：

1. 聊天 UI。
2. 长时间 research agent。
3. 后台任务进度条。
4. 调试复杂 graph。

### 7.5 后台任务

Agent Server 支持后台运行思路，适合耗时任务：

1. 深度研究。
2. 多文档分析。
3. 批量工具调用。
4. 定时任务。
5. 需要稍后查询结果的任务。

在生产环境中，后台任务必须关注：

1. 队列长度。
2. worker 数量。
3. 超时策略。
4. 重试策略。
5. 幂等性。
6. 优雅关闭与 run draining。

这些听起来不像教程开头最迷人的部分，但它们决定系统会不会在真正有用户时突然变得很有个性。

## 8. 进阶使用步骤：部署方式

截至 2026-08-16，官方文档中的部署拓扑主要包括：

| 方式 | 说明 | 适合场景 |
| --- | --- | --- |
| LangSmith Deployment Cloud | LangChain 托管控制面、数据面和数据库 | 快速上线、少运维 |
| Hybrid | LangChain 管控制面，你运行 Agent Server 和数据面 | agent workload 留在自己 VPC |
| Self-hosted with control plane | 自己在 Kubernetes 中运行 LangSmith 和 Deployment | 企业、数据驻留、完整自控 |
| Standalone Agent Server | 无控制面，用 Docker/Compose/Kubernetes 直接运行 Agent Server | 轻量自托管、已有平台 |

### 8.1 部署到 LangSmith Cloud

要求：

1. LangSmith 账号。
2. 有部署权限的 API key。
3. 项目有 `langgraph.json`。
4. 环境变量配置完整。

命令：

```powershell
langgraph deploy
```

指定名称：

```powershell
langgraph deploy --name research-agent
```

查看日志：

```powershell
langgraph deploy logs -f --name research-agent
```

Cloud 部署适合学习生产流程和小团队快速落地。

### 8.2 构建镜像后自托管

```powershell
langgraph build -t research-agent:latest
```

然后将镜像推送到你的 registry，由 Kubernetes、Docker 或其他平台运行。

### 8.3 Standalone server

Standalone server 不依赖 LangSmith Deployment control plane。你需要自己管理：

1. Agent Server 容器。
2. Postgres。
3. Redis。
4. Secret。
5. 日志。
6. 扩缩容。
7. 健康检查。
8. 滚动更新。

最低环境变量通常包括：

```dotenv
DATABASE_URI=postgres://...
REDIS_URI=redis://...
LANGSMITH_API_KEY=lsv2_...
LANGGRAPH_CLOUD_LICENSE_KEY=...
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

如果 traces 要发送到 self-hosted LangSmith，`LANGSMITH_ENDPOINT` 应指向自托管 LangSmith API 地址，末尾不要加斜杠。

### 8.4 生产推荐路径

官方文档更推荐生产级 standalone 使用 Kubernetes 和维护的 Helm chart。Docker 或非 Kubernetes 也能跑，但你要自己处理队列扩缩容、优雅下线、API/queue 分离、版本升级等细节。

## 9. 生产化建议

### 9.1 区分环境

至少区分：

```text
dev
staging
prod
```

并使用不同：

1. LangSmith project。
2. API key。
3. deployment name。
4. database。
5. Redis DB number。
6. secrets。

### 9.2 固定依赖版本

不要在生产镜像里完全依赖浮动最新版：

```toml
dependencies = [
  "langchain>=1.0,<2",
  "langgraph>=1.0,<2",
  "langchain-openai>=1.0,<2"
]
```

具体版本范围要根据项目实际测试结果决定。核心原则是：生产部署应可复现。

### 9.3 给 graph 加保护

常见保护：

1. 最大迭代次数。
2. 最大工具调用次数。
3. 单次工具超时。
4. 总 run 超时。
5. 输出 schema 校验。
6. 敏感工具权限校验。
7. 用户输入长度限制。

### 9.4 设计鉴权和租户隔离

如果服务对外提供：

1. 不要公开无鉴权 API。
2. 不要让用户任意访问别人的 thread。
3. thread、store、metadata 要带租户信息。
4. 工具调用前检查权限。
5. Studio 对生产环境的访问要受控。

### 9.5 接入 LangSmith

生产中建议开启：

1. tracing。
2. error monitoring。
3. feedback。
4. online evaluation。
5. 关键数据集的 offline regression。

### 9.6 健康检查和日志

至少检查：

1. `/ok` 健康检查。
2. API server 日志。
3. worker 日志。
4. Postgres 连接。
5. Redis 连接。
6. 队列积压。
7. latency。
8. error rate。

### 9.7 路由暴露面

生产中可以考虑禁用不需要的 meta/docs 路由：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent/graph.py:graph"
  },
  "http": {
    "disable_meta": true
  }
}
```

这样可以减少暴露的服务信息。健康检查 `/ok` 仍可用于编排系统。

## 10. 常见问题

### 10.1 LangGraph Server 和 LangServe 有什么区别？

| 项目 | LangGraph Server | LangServe |
| --- | --- | --- |
| 核心对象 | graph / assistant / thread / run | Runnable / LCEL chain |
| 状态管理 | 原生支持 thread/checkpoint | 需自行设计 |
| Agent 工作负载 | 更适合 | 简单场景可用 |
| Studio | 原生连接 | 不作为主要路径 |
| 部署路线 | LangSmith Deployment / Agent Server | FastAPI 服务 |
| 新项目推荐 | 更推荐 | 适合旧项目或简单 API |

### 10.2 `langgraph dev` 和 `langgraph up` 怎么选？

| 命令 | 特点 | 适合 |
| --- | --- | --- |
| `langgraph dev` | 无 Docker、热重载、启动快 | 开发和调试 |
| `langgraph up` | Docker、本地 API server、更接近部署 | 本地集成测试、镜像验证 |

### 10.3 Server 启动时报导入错误

检查：

1. 是否安装项目：`pip install -e .`。
2. `dependencies` 是否包含 `"."`。
3. `graphs` 路径是否正确。
4. Python 包是否有 `__init__.py`。
5. 当前虚拟环境是否正确。

### 10.4 Thread 不保留上下文

可能原因：

1. 每次请求都创建了新 thread。
2. graph state 没有保存 messages。
3. 没有正确使用 checkpointer。
4. 客户端没有传同一个 thread id。

### 10.5 本地能跑，部署后失败

优先检查：

1. `.env` 是否在部署环境存在。
2. secret 是否正确注入。
3. Docker 镜像是否包含本地包。
4. 外部工具服务是否可访问。
5. Python 版本是否一致。
6. 依赖版本是否漂移。
7. LangSmith endpoint 区域是否正确。

### 10.6 是否必须使用 LangSmith Deployment？

不是。你可以 standalone 自托管 Agent Server。但如果你不想自己管理 Postgres、Redis、队列、部署、扩缩容和控制面，LangSmith Deployment 会更省心。所谓自由，很多时候意味着自己修凌晨三点的服务。选择前最好诚实一点。

## 11. 总结

LangGraph Server 是把 LangGraph agent 工程化的关键一层。它让 graph 不只是本地函数，而是有 API、有 thread、有 assistant、有 run、有持久化、有流式输出、有部署路径的服务。

你应该掌握：

1. 用 `langgraph dev` 启动本地 Agent Server。
2. 用 Studio 和 `/docs` 调试服务。
3. 用 SDK 创建 thread、选择 assistant、发起 run。
4. 用 `langgraph.json` 声明 graph、依赖和环境变量。
5. 理解 assistant、thread、run、store 的区别。
6. 用 `langgraph build` 和 `langgraph deploy` 进入部署流程。
7. 生产环境中认真处理鉴权、持久化、队列、日志、评测和扩缩容。

如果只想写一个 demo，直接 `.invoke()` 就够了。但如果你想让 agent 被真实用户调用，LangGraph Server 就是必须认真学习的部分。服务化不是炫技，它只是把“能跑”变成“能被可靠调用”。

## 12. 参考资料

- Agent Server 官方文档：https://docs.langchain.com/langsmith/agent-server
- LangGraph 本地服务教程：https://docs.langchain.com/oss/python/langgraph/local-server
- LangGraph CLI 官方文档：https://docs.langchain.com/langsmith/cli
- LangSmith Application Structure：https://docs.langchain.com/langsmith/application-structure
- LangSmith Deployment 官方文档：https://docs.langchain.com/langsmith/deployment
- LangSmith Cloud deploy quickstart：https://docs.langchain.com/langsmith/deployment-quickstart
- Standalone Agent Server 自托管文档：https://docs.langchain.com/langsmith/deploy-standalone-server
