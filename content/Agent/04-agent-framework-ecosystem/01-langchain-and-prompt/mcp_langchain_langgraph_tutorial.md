+++

date = '2026-08-18T17:33:36+08:00'
draft = false
title = "MCP 教程：从协议基础到 LangChain / LangGraph 调用"

+++

本文面向已经会写一点 Python、并且正在学习 LangChain / LangGraph 的开发者。目标很朴素：你应该能理解 MCP 是什么，能写一个最小 MCP Server，并且知道怎样在 LangChain 和 LangGraph 中调用 MCP 暴露出来的工具、资源和提示词。若只会背概念而不能把工具接进 agent，那未免太像考试前夜的幻觉了。

---

## 1. MCP 是什么

MCP，全称 Model Context Protocol，模型上下文协议。它是一个开放协议，用来标准化 AI 应用如何连接外部上下文、工具和数据源。

可以把它理解为三层关系：

| 角色 | 含义 | 例子 |
| --- | --- | --- |
| Host | 用户实际使用的 AI 应用 | Claude Desktop、IDE 插件、你写的 LangGraph Agent |
| Client | Host 内部负责连接某个 MCP Server 的客户端 | `MultiServerMCPClient` 创建的连接 |
| Server | 对外暴露能力的服务进程 | 文件系统服务、数据库服务、天气 API 服务、搜索服务 |

MCP Server 通常向客户端暴露三类能力：

| 能力 | 英文 | 作用 | LangChain 中的常见映射 |
| --- | --- | --- | --- |
| 工具 | Tools | 让模型调用函数执行动作 | 转成 LangChain Tool |
| 资源 | Resources | 让客户端读取数据或上下文 | 转成 Blob / 文档上下文 |
| 提示词 | Prompts | 提供可复用的提示词模板或消息 | 转成 LangChain messages |

MCP 底层使用 JSON-RPC 2.0 风格的消息通信。开发应用时，你通常不需要手写 JSON-RPC 请求；用 MCP SDK、FastMCP、`langchain-mcp-adapters` 这样的库即可。

---

## 2. MCP 解决了什么问题

没有 MCP 时，每个 agent 框架都要为数据库、浏览器、GitHub、文件系统、内部 API 各写一套工具适配逻辑。今天你给 LangChain 写一版，明天给 Claude Desktop 写一版，后天换成另一个 agent 框架又写一版。这样当然也能活，只是不太体面。

MCP 的核心价值是把“工具提供方”和“工具使用方”解耦：

1. 工具提供方只要实现 MCP Server。
2. 工具使用方只要实现 MCP Client。
3. 中间通过统一协议发现工具、描述参数、调用工具、读取结果。

也就是说，MCP 更像“工具和上下文的连接协议”，不是新的大模型，也不是新的 agent 框架。LangChain / LangGraph 可以作为 MCP Client 使用 MCP Server 暴露的工具。

---

## 3. 什么时候应该用 MCP

适合使用 MCP 的场景：

1. 你希望一个工具服务被多个客户端复用，例如 Claude Desktop、LangChain、LangGraph、内部 Agent 平台。
2. 你要接入的系统比较多，例如文件、数据库、HTTP API、搜索服务、工单系统。
3. 工具本身有独立生命周期，例如需要单独部署、认证、审计、升级。
4. 你需要把工具能力提供给不同语言或不同框架的客户端。

不一定需要 MCP 的场景：

1. 只有一个很小的 Python 函数，只在一个脚本里用一次。
2. 工具和业务代码强耦合，没有复用价值。
3. 你只需要普通 LangChain `@tool`，并不打算跨客户端复用。

请注意：MCP 并不会让工具天然安全。它只是让工具以标准方式被发现和调用。至于权限、审计、确认、密钥隔离，仍然是开发者自己的责任。协议能帮你把门做得标准，却不会替你决定谁该进门。

---

## 4. 常见传输方式

MCP 常见传输方式有两类：

| 传输方式 | 配置名 | 适合场景 | 特点 |
| --- | --- | --- | --- |
| stdio | `stdio` | 本地工具、开发环境、桌面应用 | 客户端启动一个本地子进程，通过标准输入输出通信 |
| HTTP / Streamable HTTP | `http` 或 `streamable-http` | 远程服务、团队共享、生产部署 | Server 独立运行，客户端通过 URL 连接 |

在 LangChain 的 Python MCP 适配器中，经常会看到这样的配置：

```python
{
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
    },
    "weather": {
        "transport": "http",
        "url": "http://localhost:8000/mcp",
    },
}
```

`stdio` 适合本地开发，简单直接。`http` 更适合远程服务、容器化、统一认证和团队复用。

---

## 5. 环境准备

建议使用 Python 3.11 或更高版本。

在 PowerShell 中创建一个演示目录：

```powershell
mkdir D:\learning\Python\agent\mcp_demo
cd D:\learning\Python\agent\mcp_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

安装依赖：

```powershell
pip install -U langchain langgraph langchain-openai langchain-mcp-adapters fastmcp python-dotenv
```

如果使用 OpenAI 模型：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

如果你使用 Anthropic、Google 或其他模型提供商，只要 LangChain 当前版本支持，也可以替换示例里的模型名称。教程里用 OpenAI 只是为了让示例更短，不表示 MCP 依赖 OpenAI。

---

## 6. 编写第一个 MCP Server

新建 `math_server.py`：

```python
from fastmcp import FastMCP

mcp = FastMCP("Math")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("b must not be 0")
    return a / b


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

这个文件就是一个 MCP Server。它暴露了三个工具：`add`、`multiply`、`divide`。

这里有几个要点：

1. `FastMCP("Math")` 定义了服务名称。
2. `@mcp.tool()` 把普通 Python 函数注册为 MCP Tool。
3. 函数签名和 docstring 会被用来生成工具描述和参数 schema。
4. `mcp.run(transport="stdio")` 表示通过标准输入输出运行，适合由客户端启动。

你不需要手写 `tools/list` 或 `tools/call` JSON-RPC 消息。FastMCP 会处理这些细节。能少写样板代码时，就不要表现出对样板代码的执着。

---

## 7. 在 LangChain 中调用 MCP

LangChain 调用 MCP 的推荐方式是使用 `langchain-mcp-adapters`。

核心流程：

1. 用 `MultiServerMCPClient` 连接一个或多个 MCP Server。
2. 用 `await client.get_tools()` 把 MCP tools 转成 LangChain tools。
3. 把这些 tools 交给 LangChain agent 或手动调用。

### 7.1 直接加载并调用 MCP Tool

先写一个最小客户端 `langchain_direct_tool_call.py`：

```python
import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
            }
        }
    )

    tools = await client.get_tools()

    print("Loaded tools:")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    tools_by_name = {tool.name: tool for tool in tools}
    result = await tools_by_name["add"].ainvoke({"a": 2, "b": 40})
    print("add result:", result)


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```powershell
python langchain_direct_tool_call.py
```

这一步不需要大模型。它只是验证 LangChain 是否能发现并调用 MCP Server 暴露的工具。

如果这里失败，先不要急着怀疑模型。模型还没出场。通常是路径、虚拟环境、依赖或 server 启动方式出了问题。

### 7.2 用 LangChain Agent 自动选择 MCP Tool

接下来让模型自己决定何时调用工具。新建 `langchain_agent_mcp.py`：

```python
import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
            }
        }
    )

    tools = await client.get_tools()

    agent = create_agent(
        model="openai:gpt-4.1-mini",
        tools=tools,
        system_prompt=(
            "You are a careful math assistant. "
            "Use tools whenever arithmetic is needed."
        ),
    )

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请计算 (13 + 29) * 7，并说明你是怎么得到结果的。",
                }
            ]
        }
    )

    for message in result["messages"]:
        message.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
```

这里发生了什么：

1. `MultiServerMCPClient` 启动 `math_server.py` 并读取工具列表。
2. `client.get_tools()` 返回的是 LangChain 可用的 tool 对象。
3. `create_agent(...)` 把这些工具交给 agent。
4. 模型看到用户问题后，生成 tool call。
5. agent 执行 MCP tool，把结果作为 ToolMessage 加回对话。
6. 模型读取工具结果，生成最终回答。

注意：MCP tool 的名称、描述、参数 schema 会影响模型是否愿意正确调用它。工具描述写得含糊，模型就会像在没有路灯的雪夜里散步一样，方向感全靠运气。

### 7.3 同时连接多个 MCP Server

假设还有一个 HTTP 方式运行的天气服务：

```python
client = MultiServerMCPClient(
    {
        "math": {
            "transport": "stdio",
            "command": "python",
            "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
        },
        "weather": {
            "transport": "http",
            "url": "http://localhost:8000/mcp",
        },
    }
)

tools = await client.get_tools()
agent = create_agent("openai:gpt-4.1-mini", tools)
```

建议在启动时打印工具名称：

```python
for tool in tools:
    print(tool.name)
```

如果多个 Server 暴露了同名工具，要主动改名或分拆职责，避免模型和运行时混淆。一个叫 `search`，另一个也叫 `search`，然后期待系统自己理解你的心意，这并不是架构设计，是许愿。

### 7.4 HTTP Server 示例

新建 `weather_server.py`：

```python
from fastmcp import FastMCP

mcp = FastMCP("Weather")


@mcp.tool()
async def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"The weather in {location} is sunny."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

运行：

```powershell
python weather_server.py
```

客户端配置：

```python
client = MultiServerMCPClient(
    {
        "weather": {
            "transport": "http",
            "url": "http://localhost:8000/mcp",
        }
    }
)
```

如果你的 FastMCP 版本默认端口或路径不同，请以启动日志为准。HTTP MCP Server 的本质是：Server 独立运行，客户端通过 URL 连接。

### 7.5 HTTP Header 和认证

连接远程 MCP Server 时，经常要传 token：

```python
client = MultiServerMCPClient(
    {
        "internal_search": {
            "transport": "http",
            "url": "https://mcp.example.com/mcp",
            "headers": {
                "Authorization": "Bearer YOUR_TOKEN",
                "X-Request-Source": "langchain-agent",
            },
        }
    }
)
```

生产环境不要把密钥硬编码在代码里。用环境变量、密钥管理服务或运行平台的 secret 注入机制。

---

## 8. 在 LangGraph 中调用 MCP

LangGraph 有两种常见接法：

1. 使用 `create_agent` 快速创建 agent 图。
2. 使用 `StateGraph` 显式定义节点、边和工具调用循环。

第一种更短，适合起步。第二种更清楚，适合需要状态、条件分支、人工审批、检查点、审计的生产流程。

### 8.1 LangGraph 快速方式：`create_agent`

在 LangChain 1.x 之后，`create_agent` 是推荐的高层 agent API。它背后使用 LangGraph 的 agent 运行机制，因此对很多项目而言，这就是最省事的 LangGraph + MCP 接法。

新建 `langgraph_create_agent_mcp.py`：

```python
import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
            }
        }
    )

    tools = await client.get_tools()

    graph_agent = create_agent(
        model="openai:gpt-4.1-mini",
        tools=tools,
        system_prompt="You are a precise assistant. Use MCP tools for calculations.",
    )

    result = await graph_agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "计算 21 * (8 + 4)，必须调用工具。",
                }
            ]
        }
    )

    for message in result["messages"]:
        message.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
```

这段代码看起来和 LangChain Agent 示例很像，因为 LangChain 的 agent API 和 LangGraph 已经深度整合。你可以把它理解为“LangGraph 的预制 agent 图”。

适合这种方式的场景：

1. 普通问答 + 工具调用。
2. 不需要复杂分支。
3. 不需要自己控制每个节点。
4. 希望尽快把 MCP 工具跑起来。

### 8.2 LangGraph 显式方式：`StateGraph` + `ToolNode`

如果你需要完全掌控图结构，可以自己写 `StateGraph`。

新建 `langgraph_stategraph_mcp.py`：

```python
import asyncio
from typing import Annotated

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


async def build_graph():
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
            }
        }
    )

    tools = await client.get_tools()

    model = init_chat_model(
        "openai:gpt-4.1-mini",
        temperature=0,
    )
    model_with_tools = model.bind_tools(tools)

    async def call_model(state: AgentState) -> dict:
        response = await model_with_tools.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You are a careful assistant. "
                        "When arithmetic is needed, call the available MCP tools."
                    )
                ),
                *state["messages"],
            ]
        )
        return {"messages": [response]}

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("agent", call_model)
    graph_builder.add_node("tools", ToolNode(tools))

    graph_builder.add_edge(START, "agent")
    graph_builder.add_conditional_edges("agent", tools_condition)
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile()


async def main() -> None:
    graph = await build_graph()

    result = await graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请计算 17 * (5 + 6)。",
                }
            ]
        }
    )

    for message in result["messages"]:
        message.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
```

这就是一个典型的 ReAct 工具调用循环：

| 节点 / 边 | 作用 |
| --- | --- |
| `agent` 节点 | 调用绑定了 MCP tools 的模型 |
| `tools_condition` | 判断模型是否返回了 tool calls |
| `tools` 节点 | `ToolNode` 执行具体工具 |
| `tools -> agent` | 把工具结果交还给模型，让模型继续推理或回答 |
| `END` | 没有工具调用时结束 |

这里最容易漏掉的是 `model.bind_tools(tools)`。如果不绑定工具，模型通常不会生成 tool calls；如果没有 `ToolNode(tools)`，图也不知道怎样执行这些 tool calls。一个负责“提出调用”，一个负责“执行调用”，二者不是同一件事。

### 8.3 为什么要在 LangGraph 里显式接 MCP

如果只是简单问答，`create_agent` 足够。显式 `StateGraph` 的价值在于你可以继续加东西：

1. 在工具调用前加入审批节点。
2. 对危险工具做权限判断。
3. 根据工具结果路由到不同分支。
4. 给长任务加 checkpoint。
5. 在状态里保留业务字段，例如 `user_id`、`task_status`、`retrieved_docs`。
6. 为不同工具失败设计重试或降级路径。

例如你可以在 `AgentState` 加一个字段：

```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    approved: bool
```

再写一个路由函数，在调用工具前检查 `approved`。MCP 负责“工具怎样暴露”，LangGraph 负责“流程怎样控制”。把这两个职责混在一起，后期会很难维护。

---

## 9. 加载 MCP Resources

Tools 是给模型执行动作的，Resources 是给客户端读取上下文的。

例如某个 MCP Server 暴露了文件、数据库记录或文档片段，可以这样读取：

```python
import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "docs": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )

    blobs = await client.get_resources("docs")

    for blob in blobs:
        print("URI:", blob.metadata.get("uri"))
        print("MIME:", blob.mimetype)
        print(blob.as_string()[:500])


if __name__ == "__main__":
    asyncio.run(main())
```

也可以按 URI 读取：

```python
blobs = await client.get_resources(
    "docs",
    uris=["file:///project/README.md"],
)
```

资源一般不会像 tool 那样自动让模型调用。常见做法是：

1. 客户端先读取 resource。
2. 把 resource 内容放进 prompt 或检索系统。
3. 再让模型基于这些上下文回答。

如果资源很大，不要一股脑塞进上下文。先做检索、截断、摘要或分块。上下文窗口不是垃圾桶，虽然很多人似乎对此颇有误解。

---

## 10. 加载 MCP Prompts

Prompts 是 MCP Server 暴露的可复用提示词或消息模板。

示例：

```python
import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "prompt_server": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )

    messages = await client.get_prompt(
        "prompt_server",
        "code_review",
        arguments={
            "language": "python",
            "focus": "security",
        },
    )

    for message in messages:
        print(message.type, message.content)


if __name__ == "__main__":
    asyncio.run(main())
```

Prompts 适合团队统一规范，例如：

1. 代码审查模板。
2. SQL 分析模板。
3. 客服回复模板。
4. 工具使用说明模板。

不过别把安全策略完全写进 prompt 里。Prompt 是指导，不是门禁系统。真正的权限控制应该在工具、服务端、网关或 LangGraph 控制流里实现。

---

## 11. Stateful Session：什么时候需要持久会话

`MultiServerMCPClient` 默认是偏无状态的：每次工具调用创建会话、执行、清理。对普通工具来说这很好，简单，干净。

但有些 MCP Server 是有状态的，例如：

1. 一个浏览器自动化 server 需要保留当前页面。
2. 一个数据库分析 server 需要保留临时表或会话变量。
3. 一个远程工作区 server 需要保留当前目录、任务上下文。

这时可以显式创建 session：

```python
import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "stateful_browser": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )

    async with client.session("stateful_browser") as session:
        tools = await load_mcp_tools(session)
        agent = create_agent("openai:gpt-4.1-mini", tools)

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "打开示例网站，然后总结首页标题。",
                    }
                ]
            }
        )

        for message in result["messages"]:
            message.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
```

原则很简单：

1. 工具之间不需要共享状态，用默认方式。
2. 工具之间需要共享状态，用显式 session。
3. 如果状态涉及用户身份、浏览器、文件系统、数据库事务，要格外小心生命周期和权限边界。

---

## 12. MCP Tool 返回结构化内容

MCP Tool 可以返回文本，也可以返回结构化内容。结构化内容适合订单、天气、数据库查询、搜索结果这类机器可解析数据。

在 LangChain MCP adapter 中，结构化内容通常可以从 ToolMessage 的 artifact 里读取：

```python
from langchain.messages import ToolMessage

result = await agent.ainvoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "查询订单 order_123 的状态。",
            }
        ]
    }
)

for message in result["messages"]:
    if isinstance(message, ToolMessage) and message.artifact:
        print(message.artifact)
```

如果你的业务后续要使用这些数据，不要只让模型“读一段文本再猜”。能拿结构化字段，就拿结构化字段。让模型做解释，让程序做校验；职责分清，大家都轻松。

---

## 13. 常见错误与排查

### 13.1 `ModuleNotFoundError`

确认当前虚拟环境安装了依赖：

```powershell
pip show langchain-mcp-adapters
pip show fastmcp
```

如果是在 IDE 中运行，确认 IDE 使用的是同一个 Python 解释器。

### 13.2 stdio Server 启动失败

检查：

1. `args` 里的路径是否正确。
2. 路径是否需要使用 raw string，例如 `r"D:\path\to\server.py"`。
3. Server 文件是否能单独运行。
4. 虚拟环境里是否安装了 server 所需依赖。

### 13.3 Agent 不调用工具

检查：

1. 是否执行了 `tools = await client.get_tools()`。
2. 是否把 `tools` 传给了 `create_agent`，或执行了 `model.bind_tools(tools)`。
3. 工具描述是否清楚。
4. 用户问题是否真的需要工具。
5. 模型是否支持 tool calling。

### 13.4 工具参数错误

检查函数签名和类型注解：

```python
@mcp.tool()
def search(query: str, limit: int = 5) -> list[dict]:
    ...
```

比起：

```python
@mcp.tool()
def search(x):
    ...
```

前者对模型友好得多。模型不是你的同事，不会从一个叫 `x` 的参数里自动读出你的人生规划。

### 13.5 HTTP 连接失败

检查：

1. Server 是否已经启动。
2. URL、端口、路径是否正确。
3. 防火墙或代理是否拦截。
4. 是否需要认证 header。
5. 客户端 transport 配置是否与 server 一致。

---

## 14. 生产实践建议

### 14.1 工具设计

好的 MCP Tool 应该满足：

1. 名称清晰，例如 `get_order_status`，不要叫 `do_work`。
2. 描述明确，说明何时使用、输入是什么、输出是什么。
3. 参数使用类型注解。
4. 返回值尽量结构化。
5. 副作用工具要谨慎，例如删除、支付、发邮件、改数据库。

### 14.2 安全与权限

MCP Server 可以暴露任意代码执行路径，因此必须当作高风险边界处理。

建议：

1. 最小权限运行 MCP Server。
2. 对危险操作做人类确认或审批。
3. 不把用户密钥暴露给不可信 Server。
4. 对工具调用做日志和审计。
5. 对远程 Server 使用认证和 HTTPS。
6. 不信任工具描述和 annotations，除非 Server 来源可信。
7. 在 LangGraph 中显式加入权限节点，而不是只靠 prompt 约束。

### 14.3 工具数量控制

不要一次给模型塞几十上百个工具。工具太多时，模型选择正确工具的概率会下降。

更好的做法：

1. 按场景加载工具。
2. 按用户权限加载工具。
3. 按任务阶段加载工具。
4. 用 LangGraph 路由到不同子图，每个子图只暴露必要工具。

### 14.4 可观测性

建议接入 LangSmith 或你自己的 tracing 系统，至少记录：

1. 用户请求。
2. 模型选择了哪个工具。
3. 工具参数。
4. 工具返回。
5. 错误信息。
6. 每步耗时。

没有日志的 agent 系统，调试时基本靠祈祷。而祈祷不属于可靠工程方法。

---

## 15. 推荐项目结构

一个小型 MCP + LangGraph 项目可以这样组织：

```text
mcp_demo/
  .env
  requirements.txt
  servers/
    math_server.py
    weather_server.py
  clients/
    langchain_agent_mcp.py
    langgraph_create_agent_mcp.py
    langgraph_stategraph_mcp.py
  app/
    graph.py
    state.py
    nodes.py
    config.py
```

职责划分：

| 文件 | 职责 |
| --- | --- |
| `servers/` | MCP Server 实现 |
| `clients/` | 调用示例或测试客户端 |
| `app/graph.py` | LangGraph 图结构 |
| `app/state.py` | LangGraph state 类型 |
| `app/nodes.py` | 节点函数 |
| `app/config.py` | MCP Server 地址、模型配置、环境变量 |

---

## 16. 一份完整依赖文件

`requirements.txt`：

```text
fastmcp
langchain
langchain-openai
langchain-mcp-adapters
langgraph
python-dotenv
```

安装：

```powershell
pip install -r requirements.txt
```

---

## 17. 最小可运行闭环

如果你只想验证“LangGraph 调 MCP”是否跑通，最少需要两个文件。

第一个：`math_server.py`

```python
from fastmcp import FastMCP

mcp = FastMCP("Math")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

第二个：`run_graph.py`

```python
import asyncio
from typing import Annotated

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": [r"D:\learning\Python\agent\mcp_demo\math_server.py"],
            }
        }
    )

    tools = await client.get_tools()
    model = init_chat_model("openai:gpt-4.1-mini", temperature=0).bind_tools(tools)

    async def agent_node(state: State) -> dict:
        response = await model.ainvoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    graph = builder.compile()

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "What is 2 + 40? Use the tool."}]}
    )

    result["messages"][-1].pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```powershell
python run_graph.py
```

这就是完整闭环：

```text
用户问题 -> LangGraph agent 节点 -> 模型生成 tool call
       -> ToolNode 执行 MCP tool -> 工具结果回到 agent 节点
       -> 模型生成最终回答
```

---

## 18. LangChain 与 LangGraph 调用 MCP 的区别

| 维度 | LangChain Agent | LangGraph 显式图 |
| --- | --- | --- |
| 上手成本 | 低 | 中等 |
| 代码量 | 少 | 多 |
| 控制能力 | 适合常规工具调用 | 适合复杂流程控制 |
| 状态管理 | 由 agent 抽象处理 | 你自己定义 state |
| 条件分支 | 不明显 | 非常明确 |
| 人工审批 | 需要额外扩展 | 很适合做成节点 |
| 生产可维护性 | 简单场景足够 | 复杂场景更清楚 |

选择建议：

1. 刚接 MCP：先用 `create_agent`。
2. 要做业务流程：用 `StateGraph`。
3. 要做人类审批、检查点、任务恢复：用 LangGraph。
4. 只想调用工具拿结果：直接 `tool.ainvoke(...)` 即可。

---

## 19. 学习路线

建议按这个顺序练习：

1. 写一个只有 `add` 的 MCP Server。
2. 用 `client.get_tools()` 打印工具列表。
3. 直接 `tool.ainvoke(...)` 调用工具。
4. 用 `create_agent` 让模型自动调用工具。
5. 用 `StateGraph + ToolNode` 手写 ReAct 循环。
6. 改成 HTTP MCP Server。
7. 加入资源 Resources。
8. 加入提示词 Prompts。
9. 在 LangGraph 中加入审批节点。
10. 加 tracing 和错误处理。

这样学不会显得快，但会稳。学习框架时，稳比快有用得多。快而不稳，最后只是把错误传播得更有效率。

---

## 20. 参考资料

1. Model Context Protocol 官方规范：<https://modelcontextprotocol.io/specification/2025-06-18>
2. MCP Tools 官方规范：<https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
3. LangChain Python MCP 文档：<https://docs.langchain.com/oss/python/langchain/mcp>
4. `langchain-mcp-adapters` GitHub：<https://github.com/langchain-ai/langchain-mcp-adapters>
5. LangGraph Quickstart：<https://docs.langchain.com/oss/python/langgraph/quickstart>

---

## 21. 总结

MCP 是工具和上下文的标准连接协议；LangChain / LangGraph 是使用这些能力构建 agent 的应用框架。

最关键的代码路径只有三步：

```python
client = MultiServerMCPClient({...})
tools = await client.get_tools()
agent = create_agent("openai:gpt-4.1-mini", tools)
```

如果你使用显式 LangGraph：

```python
tools = await client.get_tools()
model_with_tools = model.bind_tools(tools)
tool_node = ToolNode(tools)
```

记住这件事就够了：MCP 负责暴露工具，LangChain 负责把工具交给 agent，LangGraph 负责把工具调用放进可控的流程。三者各司其职，系统才不容易变成一团看似智能、实际难以追踪的雾。
