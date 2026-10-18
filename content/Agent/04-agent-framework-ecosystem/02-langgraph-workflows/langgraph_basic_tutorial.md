+++
date = '2026-08-16T19:38:50+08:00'
draft = false
title = "LangGraph 基础教学讲义"
+++

这份讲义面向已经会一点 Python、想系统学习 LangGraph 和 LangChain agent 工程的人。它不是某个项目的 README，而是一份基础课程：从模型初始化、结构化输出、工具调用、MCP 接入，到 LangGraph 的状态、节点、边、Server、CLI 和常见工程写法。

讲义会穿插 Open Deep Research 项目中用到的写法，例如 `init_chat_model()`、`.with_structured_output()`、`.bind_tools()`、`StateGraph`、`Command`、`config_schema`、MCP 工具加载等。这样你学到的不是“孤立 API”，而是一套能放进真实项目里的做法。

当前日期：2026-08-16

## 目录

1. LangChain、LangGraph、LangGraph Server 分别是什么
2. 环境准备和安装
3. 如何初始化一个模型
4. 消息格式和基础调用
5. 如何控制模型结构化输出
6. 如何使用工具函数
7. 手写工具调用循环
8. 用 LangGraph 管理工具调用
9. LangGraph 中的状态、节点和边
10. Reducer：状态如何合并
11. `Command`：节点如何动态跳转
12. 条件边、循环和 agent 主循环
13. 子图 subgraph
14. 配置系统：`RunnableConfig` 和 `config_schema`
15. MCP 是什么，如何调用 MCP
16. LangGraph 的记忆和持久化
17. Streaming：如何观察中间过程
18. LangGraph Server、CLI 和 `langgraph.json`
19. 项目结构建议
20. 当前项目常见写法解析
21. 常见坑和调试建议
22. 练习题
23. 参考资料

## 1. LangChain、LangGraph、LangGraph Server 分别是什么

先把几个名字分清楚。很多初学者的问题不是写错代码，而是一开始就把这些层混在了一起。嗯，概念没摆正，后面的代码自然会很有自己的想法。

| 名称 | 主要作用 | 你可以把它理解成 |
| --- | --- | --- |
| LangChain | 模型、消息、工具、结构化输出、agent 基础抽象 | LLM 应用开发工具箱 |
| LangGraph | 用图组织有状态、多步骤、可循环、可中断的 agent 工作流 | agent 编排引擎 |
| LangGraph Server | 把 LangGraph 应用作为服务运行，提供 threads、runs、assistants 等 API | agent 后端服务 |
| LangGraph CLI | 本地开发、构建、运行 LangGraph Server 的命令行工具 | 项目启动器和构建器 |
| LangSmith | 调试、追踪、评测、可视化运行过程 | observability 和 evaluation 平台 |

一句话版：

```text
LangChain 负责模型和工具抽象。
LangGraph 负责把多步骤 agent 组织成图。
LangGraph Server/CLI 负责把图作为服务运行。
LangSmith 负责观察和评测运行过程。
```

在 Open Deep Research 项目中：

```text
src/open_deep_research/deep_researcher.py
```

就是 LangGraph 图的主实现；`langgraph.json` 告诉 LangGraph CLI 应该加载哪个图。

## 2. 环境准备和安装

推荐使用 Python 3.11 或更高版本。很多 LangGraph 项目会使用 `uv` 管理环境。

### 新建环境

```powershell
mkdir D:\learning\Python\agent\langgraph_demo
cd D:\learning\Python\agent\langgraph_demo
uv venv
.venv\Scripts\activate
```

### 安装基础依赖

```powershell
uv add langchain langgraph langchain-openai python-dotenv
```

如果要使用 MCP：

```powershell
uv add langchain-mcp-adapters mcp
```

如果要启动 LangGraph Server：

```powershell
uv add "langgraph-cli[inmem]"
```

也可以不把 CLI 写进项目依赖，而是用：

```powershell
uvx --from "langgraph-cli[inmem]" langgraph dev
```

### `.env`

创建 `.env`：

```env
OPENAI_API_KEY=你的 key
```

然后在 Python 中加载：

```python
from dotenv import load_dotenv

load_dotenv()
```

## 3. 如何初始化一个模型

LangChain 推荐通过统一接口初始化聊天模型：

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("openai:gpt-4.1-mini")

response = model.invoke("用一句话解释 LangGraph。")
print(response.content)
```

`init_chat_model()` 的好处是可以用统一字符串切换不同模型提供商，例如：

```python
openai:gpt-4.1-mini
openai:gpt-4.1
anthropic:claude-sonnet-4-20250514
google:gemini-2.5-flash
```

具体能不能用，取决于你安装的 provider 包和环境变量。

### 显式传参数

```python
model = init_chat_model(
    "openai:gpt-4.1-mini",
    max_tokens=1000,
    temperature=0,
)
```

### 延迟配置模型

Open Deep Research 里使用了这种写法：

```python
from langchain.chat_models import init_chat_model

configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)
```

它先创建一个“可配置模型”，真正调用时再通过 `.with_config()` 传模型名、token 上限和 key：

```python
model_config = {
    "model": "openai:gpt-4.1-mini",
    "max_tokens": 1000,
    "api_key": "...",
}

response = configurable_model.with_config(model_config).invoke("你好")
```

这种写法适合 LangGraph 项目，因为每个节点可能用不同模型：

- 澄清节点用轻量模型。
- 研究节点用强模型。
- 摘要节点用便宜模型。
- 最终报告节点用长上下文模型。

### 同步和异步调用

同步：

```python
response = model.invoke("你好")
```

异步：

```python
response = await model.ainvoke("你好")
```

LangGraph 节点通常写成 `async def`，所以项目里更常见 `ainvoke()`。

## 4. 消息格式和基础调用

聊天模型不只能接收字符串，也可以接收消息列表：

```python
from langchain_core.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage(content="你是一个严谨的 Python 教师。"),
    HumanMessage(content="解释一下 TypedDict。"),
]

response = model.invoke(messages)
print(response.content)
```

常见消息类型：

| 类型 | 作用 |
| --- | --- |
| `SystemMessage` | 系统指令 |
| `HumanMessage` | 用户消息 |
| `AIMessage` | 模型回复 |
| `ToolMessage` | 工具执行结果 |

LangGraph 的 `MessagesState` 默认就维护一个 `messages` 字段，适合做对话型 agent。

## 5. 如何控制模型结构化输出

结构化输出的目标是：不要让模型随意输出一段文字，而是强制它返回符合 schema 的数据。

例如你希望模型判断是否需要澄清：

```python
from pydantic import BaseModel, Field

class ClarifyResult(BaseModel):
    need_clarification: bool = Field(description="是否需要追问用户")
    question: str = Field(description="如果需要澄清，要问用户的问题")
    verification: str = Field(description="如果不需要澄清，给用户的确认信息")
```

然后：

```python
structured_model = model.with_structured_output(ClarifyResult)

result = structured_model.invoke(
    "用户说：帮我研究一下 AI。判断是否需要澄清。"
)

print(result.need_clarification)
print(result.question)
```

返回的 `result` 是 `ClarifyResult` 对象，而不是普通字符串。

### 当前项目里的写法

Open Deep Research 中：

```python
clarification_model = (
    configurable_model
    .with_structured_output(ClarifyWithUser)
    .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
    .with_config(model_config)
)
```

这里组合了三件事：

| 写法 | 作用 |
| --- | --- |
| `.with_structured_output(ClarifyWithUser)` | 要求模型返回 Pydantic schema |
| `.with_retry(...)` | 结构化失败或调用失败时重试 |
| `.with_config(...)` | 设置当前使用的模型、token、api key |

结构化输出特别适合：

- 路由判断。
- 参数抽取。
- 计划生成。
- 分类任务。
- 将自然语言转换成机器可读配置。

不适合：

- 长篇报告正文。
- 创意写作。
- 需要保留复杂格式的 Markdown。

### `Field(description=...)` 为什么重要

```python
class ResearchQuestion(BaseModel):
    research_brief: str = Field(
        description="用于指导研究的详细研究问题。"
    )
```

`description` 会帮助模型理解字段含义。  
字段名简短时尤其需要描述。否则模型可能凭感觉填，凭感觉这种事对人已经够危险了，对模型当然也一样。

## 6. 如何使用工具函数

工具 tool 是给模型调用的外部函数。模型不会直接执行 Python，它只是生成“我要调用哪个工具、参数是什么”的 tool call；真正执行工具的是你的程序或 LangGraph 节点。

### 最简单的工具

```python
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b
```

工具需要：

- 函数名。
- 参数类型标注。
- docstring 或 description。

docstring 会告诉模型什么时候使用这个工具。

### 带 description 的工具

```python
@tool(description="查询某个城市的天气。输入城市名，返回天气摘要。")
def get_weather(city: str) -> str:
    return f"{city} 今天晴，适合学习 LangGraph。"
```

### 绑定工具到模型

```python
tools = [add, get_weather]
model_with_tools = model.bind_tools(tools)

response = model_with_tools.invoke("北京天气怎么样？")

print(response)
print(response.tool_calls)
```

如果模型决定调用工具，`response.tool_calls` 里会有类似：

```python
[
    {
        "name": "get_weather",
        "args": {"city": "北京"},
        "id": "call_xxx",
    }
]
```

注意：`.bind_tools()` 只是让模型“可以选择工具”。它不会自动执行工具。

### 当前项目里的工具

Open Deep Research 中有：

```python
@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    return f"Reflection recorded: {reflection}"
```

还有搜索工具：

```python
@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: List[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    config: RunnableConfig = None,
) -> str:
    ...
```

这里的 `InjectedToolArg` 表示参数由系统注入，不让模型自己填。比如 `max_results`、`topic` 可以作为工程配置，而不是交给模型随便决定。

## 7. 手写工具调用循环

为了理解工具调用，先不用 LangGraph，手写一次。

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool

model = init_chat_model("openai:gpt-4.1-mini")

@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b

tools = [add]
tools_by_name = {t.name: t for t in tools}

model_with_tools = model.bind_tools(tools)

messages = [HumanMessage(content="23 + 19 等于多少？")]

ai_msg = model_with_tools.invoke(messages)
messages.append(ai_msg)

for tool_call in ai_msg.tool_calls:
    tool = tools_by_name[tool_call["name"]]
    result = tool.invoke(tool_call["args"])
    messages.append(
        ToolMessage(
            content=str(result),
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
    )

final = model_with_tools.invoke(messages)
print(final.content)
```

这个循环的核心是：

```text
用户消息 -> 模型决定是否调用工具 -> 程序执行工具 -> 工具结果放回消息 -> 模型继续回答
```

LangGraph 的工具 agent，本质上就是把这个循环组织成图。

## 8. 用 LangGraph 管理工具调用

LangGraph 可以手写工具节点，也可以使用预置的 `ToolNode`。

### 方式一：使用 `ToolNode`

```python
from typing import Annotated
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

@tool
def add(a: int, b: int) -> int:
    """计算两个整数之和。"""
    return a + b

tools = [add]
model = init_chat_model("openai:gpt-4.1-mini").bind_tools(tools)

def chatbot(state: State):
    return {"messages": [model.invoke(state["messages"])]}

builder = StateGraph(State)
builder.add_node("chatbot", chatbot)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", tools_condition)
builder.add_edge("tools", "chatbot")

graph = builder.compile()
```

这个图的逻辑：

```text
chatbot -> 如果模型要调用工具，去 tools
tools -> 执行完回到 chatbot
chatbot -> 如果不再调用工具，结束
```

`tools_condition` 会检查最后一条 AI 消息是否包含 tool calls。包含就去工具节点，不包含就结束。

### 方式二：手写工具执行节点

Open Deep Research 没有直接使用 `ToolNode`，而是手写了工具执行：

```python
tools = await get_all_tools(config)
tools_by_name = {
    tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool
    for tool in tools
}

tool_calls = most_recent_message.tool_calls
tool_execution_tasks = [
    execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config)
    for tool_call in tool_calls
]
observations = await asyncio.gather(*tool_execution_tasks)
```

为什么要手写？

- 它要兼容 OpenAI/Anthropic 原生网页搜索。
- 它要加载 MCP 工具。
- 它要并行执行多个工具调用。
- 它要做自定义错误处理。
- 它要根据研究完成信号进入压缩阶段。

一般项目可以先用 `ToolNode`。  
当你需要强控制、复杂分支、并发工具执行、特殊错误处理时，再手写工具节点。

## 9. LangGraph 中的状态、节点和边

这是 LangGraph 的核心。

## State：状态

状态是图运行过程中共享的数据结构。

```python
from typing_extensions import TypedDict

class State(TypedDict):
    topic: str
    draft: str
    final_answer: str
```

每个节点都接收 `state`：

```python
def write_draft(state: State):
    topic = state["topic"]
    return {"draft": f"关于 {topic} 的草稿"}
```

节点返回的是部分更新：

```python
{"draft": "..."}
```

LangGraph 会把它合并进原 state。

## Node：节点

节点就是 Python 函数：

```python
def node_name(state: State):
    ...
    return {"some_key": "some value"}
```

异步节点：

```python
async def node_name(state: State):
    ...
    return {"some_key": "some value"}
```

带配置的节点：

```python
from langchain_core.runnables import RunnableConfig

async def node_name(state: State, config: RunnableConfig):
    configurable = config.get("configurable", {})
    ...
```

## Edge：边

边定义节点执行顺序：

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(State)
builder.add_node("write_draft", write_draft)
builder.add_node("finalize", finalize)

builder.add_edge(START, "write_draft")
builder.add_edge("write_draft", "finalize")
builder.add_edge("finalize", END)

graph = builder.compile()
```

## 完整最小例子

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    topic: str
    draft: str
    final_answer: str

def write_draft(state: State):
    return {"draft": f"这是一篇关于 {state['topic']} 的草稿。"}

def finalize(state: State):
    return {"final_answer": state["draft"] + " 已完成。"}

builder = StateGraph(State)
builder.add_node("write_draft", write_draft)
builder.add_node("finalize", finalize)

builder.add_edge(START, "write_draft")
builder.add_edge("write_draft", "finalize")
builder.add_edge("finalize", END)

graph = builder.compile()

result = graph.invoke({"topic": "LangGraph"})
print(result["final_answer"])
```

## 10. Reducer：状态如何合并

默认情况下，一个节点返回的新值会替换旧值。

但 agent 经常需要“追加消息”，而不是覆盖消息。所以需要 reducer。

### 用 `add_messages`

```python
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

这样每次返回：

```python
{"messages": [new_message]}
```

都会追加到旧消息列表。

### 用 `operator.add`

```python
import operator
from typing import Annotated

class State(TypedDict):
    notes: Annotated[list[str], operator.add]
```

每次返回：

```python
{"notes": ["新笔记"]}
```

都会追加。

### 自定义 reducer

Open Deep Research 中定义了：

```python
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
```

它允许两种模式：

追加：

```python
return {"notes": ["新的研究发现"]}
```

覆盖：

```python
return {
    "supervisor_messages": {
        "type": "override",
        "value": [system_message, human_message],
    }
}
```

这个写法适合既需要追加历史，又偶尔需要重置上下文的图。

## 11. `Command`：节点如何动态跳转

普通节点只返回 state 更新。  
`Command` 可以同时返回：

- state 更新。
- 下一步跳到哪个节点。

```python
from typing import Literal
from langgraph.types import Command

def route(state: State) -> Command[Literal["need_more_info", "answer"]]:
    if state["topic"] == "":
        return Command(
            goto="need_more_info",
            update={"final_answer": "请提供主题。"},
        )
    return Command(goto="answer")
```

Open Deep Research 里常见：

```python
return Command(
    goto="write_research_brief",
    update={"messages": [AIMessage(content=response.verification)]}
)
```

什么时候用 `Command`？

- 一个节点内部决定下一步。
- 需要同时更新 state 和跳转。
- 子图或复杂 agent 中需要精细路由。

什么时候不用？

- 固定流程，用普通 `add_edge()` 就够。
- 简单二分路由，可以用 `add_conditional_edges()`。

## 12. 条件边、循环和 agent 主循环

### 条件边

```python
def should_continue(state: State):
    if state["done"]:
        return END
    return "work"

builder.add_conditional_edges("check", should_continue)
```

### 循环

```python
builder.add_edge("work", "check")
builder.add_conditional_edges("check", should_continue)
```

这就形成了：

```text
work -> check -> work -> check -> ... -> END
```

### 典型工具 agent 循环

```text
model_node -> 如果有 tool_calls -> tool_node -> model_node
model_node -> 如果没有 tool_calls -> END
```

Open Deep Research 的研究者子图就是类似循环：

```text
researcher -> researcher_tools -> researcher -> researcher_tools -> compress_research
```

它不是用 `tools_condition`，而是手写了判断逻辑：

```python
if not has_tool_calls and not has_native_search:
    return Command(goto="compress_research")
```

以及：

```python
if exceeded_iterations or research_complete_called:
    return Command(goto="compress_research", update={...})
```

## 13. 子图 subgraph

复杂系统不要把所有节点塞进一个图。可以拆成子图。

```python
researcher_builder = StateGraph(ResearcherState)
...
researcher_subgraph = researcher_builder.compile()

main_builder = StateGraph(MainState)
main_builder.add_node("researcher", researcher_subgraph)
```

Open Deep Research 有三层：

```text
主图 deep_researcher
├── 监督者子图 supervisor_subgraph
└── 研究者子图 researcher_subgraph
```

好处：

- 主图更清楚。
- 子任务可单独测试。
- 每个图可以有自己的 state schema。
- 复杂 agent 更容易维护。

什么时候该拆子图？

- 一个流程内部有自己的循环。
- 某个模块有独立状态。
- 你想复用某段图逻辑。
- 你已经开始在一个节点里写太多分支。

## 14. 配置系统：`RunnableConfig` 和 `config_schema`

LangGraph 节点可以接收第二个参数：

```python
from langchain_core.runnables import RunnableConfig

def node(state: State, config: RunnableConfig):
    configurable = config.get("configurable", {})
    model_name = configurable.get("model", "openai:gpt-4.1-mini")
```

调用图时传配置：

```python
graph.invoke(
    {"messages": [{"role": "user", "content": "你好"}]},
    {"configurable": {"model": "openai:gpt-4.1-mini", "thread_id": "demo"}}
)
```

### 用 Pydantic 定义配置 schema

```python
from pydantic import BaseModel, Field

class Configuration(BaseModel):
    model: str = Field(default="openai:gpt-4.1-mini")
    max_tokens: int = Field(default=1000)
```

图构建：

```python
builder = StateGraph(State, config_schema=Configuration)
```

节点中：

```python
configurable = Configuration(**config.get("configurable", {}))
```

Open Deep Research 写得更完整：

```python
class Configuration(BaseModel):
    allow_clarification: bool = Field(default=True)
    search_api: SearchAPI = Field(default=SearchAPI.TAVILY)
    research_model: str = Field(default="openai:gpt-4.1")
    compression_model: str = Field(default="openai:gpt-4.1")
    final_report_model: str = Field(default="openai:gpt-4.1")
    mcp_config: Optional[MCPConfig] = Field(default=None)
```

并提供：

```python
@classmethod
def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> "Configuration":
    configurable = config.get("configurable", {}) if config else {}
    ...
```

这种封装的好处是每个节点只需要写：

```python
configurable = Configuration.from_runnable_config(config)
```

配置逻辑不会散落得到处都是。

## 15. MCP 是什么，如何调用 MCP

MCP 是 Model Context Protocol。它让模型应用通过统一协议连接外部工具、资源和提示词。  
你可以把 MCP server 看作“工具服务器”，LangGraph/LangChain 作为 client 去加载它暴露的工具。

### 安装

```powershell
uv add langchain-mcp-adapters mcp
```

### 连接一个 stdio MCP server

下面是一个常见写法：

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": ["math_server.py"],
            }
        }
    )

    tools = await client.get_tools()
    print([tool.name for tool in tools])

asyncio.run(main())
```

### 连接 HTTP MCP server

Open Deep Research 中使用类似：

```python
mcp_server_config = {
    "server_1": {
        "url": server_url,
        "headers": auth_headers,
        "transport": "streamable_http",
    }
}

client = MultiServerMCPClient(mcp_server_config)
available_mcp_tools = await client.get_tools()
```

其中：

```python
server_url = configurable.mcp_config.url.rstrip("/") + "/mcp"
```

也就是说，如果配置的 URL 是：

```text
https://example.com
```

实际连接的是：

```text
https://example.com/mcp
```

### 把 MCP 工具绑定给模型

```python
tools = await client.get_tools()
model_with_tools = model.bind_tools(tools)
```

之后它和普通 LangChain tools 一样使用。

### MCP 与普通工具函数的区别

| 维度 | 普通 `@tool` | MCP 工具 |
| --- | --- | --- |
| 定义位置 | 当前 Python 进程 | 外部 MCP server |
| 适合场景 | 简单本地函数 | 外部系统、浏览器、数据库、SaaS |
| 部署 | 跟主项目一起部署 | 可独立部署 |
| 权限边界 | 由主项目控制 | 可由 MCP server 控制 |
| 扩展性 | 简单直接 | 更适合复杂生态 |

经验：如果只是一个小函数，用 `@tool`。如果是外部系统集成，用 MCP。不要为了优雅而引入 MCP，也不要为了省事把整个世界都塞进一个 `utils.py`。两种极端都不怎么体面。

## 16. LangGraph 的记忆和持久化

LangGraph 有两类持久化概念：

| 类型 | 作用 |
| --- | --- |
| Checkpointer | 保存 thread 内的图状态快照，属于短期记忆 |
| Store | 保存跨 thread 的长期数据，例如用户偏好 |

### 最小 checkpointer 示例

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-1"}}

graph.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
graph.invoke({"messages": [{"role": "user", "content": "我叫什么？"}]}, config)
```

关键是 `thread_id`。  
没有 `thread_id`，checkpointer 不知道这是哪条对话。

### 什么时候需要持久化

- 多轮对话。
- 人工审批后恢复执行。
- 长任务中断后继续。
- 调试时查看历史状态。
- 生产系统容错。

## 17. Streaming：如何观察中间过程

`invoke()` 只给最终结果。  
`stream()` / `astream()` 可以看中间过程。

```python
for event in graph.stream(
    {"messages": [{"role": "user", "content": "解释 LangGraph"}]},
    stream_mode="updates",
):
    print(event)
```

异步：

```python
async for event in graph.astream(
    {"messages": [{"role": "user", "content": "解释 LangGraph"}]},
    stream_mode="updates",
):
    print(event)
```

常见 stream mode：

| 模式 | 含义 |
| --- | --- |
| `updates` | 每个节点产生的状态更新 |
| `values` | 每步后的完整 state |
| `messages` | LLM token/message 流 |

调试 LangGraph 时，优先用 `updates`。它能告诉你哪个节点返回了什么。

## 18. LangGraph Server、CLI 和 `langgraph.json`

## LangGraph Server 是什么

LangGraph Server 会把你的 graph 变成一个服务，提供：

- assistants
- threads
- runs
- streaming
- persistence
- API docs
- Studio UI 调试入口

你本地运行：

```powershell
langgraph dev
```

本质上就是启动一个本地 Agent Server。

## LangGraph CLI 是什么

LangGraph CLI 是命令行工具。常见命令：

```powershell
langgraph dev
langgraph build
langgraph up
langgraph deploy
```

常用：

```powershell
uvx --from "langgraph-cli[inmem]" langgraph dev
```

或者在项目里安装：

```powershell
uv add "langgraph-cli[inmem]"
langgraph dev
```

## `langgraph.json`

最小结构：

```json
{
  "graphs": {
    "agent": "./agent.py:graph"
  },
  "env": "./.env",
  "dependencies": ["."],
  "python_version": "3.11"
}
```

含义：

| 字段 | 作用 |
| --- | --- |
| `graphs` | 注册 graph 名称和加载路径 |
| `env` | 指定环境变量文件 |
| `dependencies` | 指定依赖安装方式 |
| `python_version` | 指定 Python 版本 |
| `dockerfile_lines` | 追加系统构建步骤 |
| `auth` | 指定鉴权对象 |

Open Deep Research 的入口：

```json
"graphs": {
  "Deep Researcher": "./src/open_deep_research/deep_researcher.py:deep_researcher"
}
```

这表示 Studio 中显示的 assistant 名称是 `Deep Researcher`，实际加载 `deep_researcher.py` 中的 `deep_researcher` 对象。

## 19. 项目结构建议

一个基础 LangGraph 项目可以这样组织：

```text
my_agent/
├── .env
├── langgraph.json
├── pyproject.toml
├── src/
│   └── my_agent/
│       ├── __init__.py
│       ├── graph.py
│       ├── state.py
│       ├── configuration.py
│       ├── tools.py
│       └── prompts.py
└── tests/
```

对应职责：

| 文件 | 职责 |
| --- | --- |
| `graph.py` | 构建 `StateGraph`，注册节点和边 |
| `state.py` | 定义 state、结构化输出 schema、工具参数模型 |
| `configuration.py` | 定义运行时配置 |
| `tools.py` | 普通工具和 MCP 加载 |
| `prompts.py` | prompt 模板 |
| `langgraph.json` | Server/CLI 入口 |

Open Deep Research 的结构就是这种风格，只是规模更大。

## 20. 当前项目常见写法解析

这一章讲一些真实项目里常见、但初学者容易困惑的写法。

### 写法一：可配置模型

```python
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)
```

作用：先创建统一模型入口，每次调用再通过 config 选择模型。

适合：

- 多节点使用不同模型。
- Studio 中动态切换模型。
- OAP 或其他 UI 管理配置。

### 写法二：结构化输出 + retry

```python
model = (
    configurable_model
    .with_structured_output(ResearchQuestion)
    .with_retry(stop_after_attempt=3)
    .with_config(model_config)
)
```

作用：让模型返回 `ResearchQuestion` 对象，如果解析失败就重试。

### 写法三：工具绑定

```python
model = (
    configurable_model
    .bind_tools(tools)
    .with_retry(stop_after_attempt=3)
    .with_config(model_config)
)
```

作用：让模型能选择调用工具。

### 写法四：`Command` 动态路由

```python
return Command(
    goto="research_supervisor",
    update={"research_brief": response.research_brief}
)
```

作用：同时更新 state，并跳转到指定节点。

### 写法五：并行执行子研究

```python
tool_results = await asyncio.gather(*research_tasks)
```

作用：监督者一次拆多个研究任务，研究者并行执行。

需要注意：

- 并发会增加速率限制风险。
- 并发会增加 token 成本。
- 工具服务也可能被压垮。

### 写法六：手写 MCP 工具加载

```python
client = MultiServerMCPClient(mcp_server_config)
available_mcp_tools = await client.get_tools()
```

作用：从 MCP server 拉取工具，再交给模型使用。

### 写法七：状态覆盖协议

```python
{
    "type": "override",
    "value": [...]
}
```

这是项目自定义 reducer 的约定，不是 LangGraph 内置格式。它的好处是同一个字段既能追加，也能覆盖。

## 21. 常见坑和调试建议

### 坑一：以为 `bind_tools()` 会自动执行工具

不会。  
它只让模型生成 tool calls。你还需要 `ToolNode` 或自己写工具执行节点。

### 坑二：把 state 当普通全局变量

state 是图运行中的数据快照。节点应该返回 state 更新，而不是到处改全局变量。

### 坑三：忘记 reducer

如果 `messages` 没有 reducer，你可能每次都覆盖消息历史。  
对消息列表通常用：

```python
Annotated[list[AnyMessage], add_messages]
```

### 坑四：配置没生效

检查：

- `.env` 是否覆盖了运行时配置。
- `config_schema` 是否包含该字段。
- 节点是否真的读取了 `config`。
- Studio 中是否改的是正确 assistant 配置。

### 坑五：MCP 工具名冲突

如果 MCP tool 名称和已有工具名一样，项目可能会跳过它。  
命名要清楚，最好加前缀，例如：

```text
browser_open_url
filesystem_read_file
database_query
```

### 坑六：没有 `thread_id`

使用 checkpointer 时，必须提供：

```python
{"configurable": {"thread_id": "xxx"}}
```

否则无法正确保存和恢复对话状态。

### 坑七：旧代码改了，新入口没变

真实项目里经常存在 `legacy/`。  
先看 `langgraph.json`，确认 Server 加载的是哪个 graph。否则你可能认真改了一下午，运行路径完全没有碰到。是的，这种努力很纯粹，也很无效。

## 22. 练习题

### 练习一：最小图

写一个图：

```text
START -> ask_model -> END
```

输入 `question`，输出 `answer`。

### 练习二：结构化输出

定义：

```python
class RouteDecision(BaseModel):
    route: Literal["math", "chat"]
    reason: str
```

让模型判断用户问题应该进入数学工具，还是普通聊天。

### 练习三：工具调用

定义工具：

```python
@tool
def multiply(a: int, b: int) -> int:
    """计算两个整数乘积。"""
    return a * b
```

让模型回答：

```text
123 * 456 是多少？
```

### 练习四：工具 agent 图

用 `ToolNode` 和 `tools_condition` 写一个工具 agent。

要求：

```text
chatbot -> tools -> chatbot
chatbot -> END
```

### 练习五：自定义 reducer

写一个 state：

```python
class State(TypedDict):
    notes: Annotated[list[str], operator.add]
```

让三个节点分别追加一条 note。

### 练习六：MCP

启动一个简单 MCP server，然后用 `MultiServerMCPClient` 获取工具列表。

目标：

```python
tools = await client.get_tools()
print([tool.name for tool in tools])
```

### 练习七：`langgraph.json`

创建一个最小 LangGraph 项目，并通过：

```powershell
langgraph dev
```

在 Studio 中运行。

## 23. 参考资料

以下资料建议优先读官方文档。搜索引擎上教程很多，但 LangGraph 和 LangChain 更新很快，过期代码并不少，足以让人产生一些并不必要的怀疑人生体验。

- LangGraph Graph API overview：<https://docs.langchain.com/oss/python/langgraph/graph-api>
- Use the graph API：<https://docs.langchain.com/oss/python/langgraph/use-graph-api>
- LangGraph persistence：<https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph memory：<https://docs.langchain.com/oss/python/langgraph/add-memory>
- LangGraph CLI：<https://docs.langchain.com/langsmith/cli>
- LangGraph application structure：<https://docs.langchain.com/langsmith/application-structure>
- LangChain tools：<https://docs.langchain.com/oss/python/langchain/tools>
- LangChain structured output：<https://docs.langchain.com/oss/python/langchain/structured-output>
- LangChain MCP：<https://docs.langchain.com/oss/python/langchain/mcp>
- `MultiServerMCPClient` API reference：<https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient>

## 最后总结

学习 LangGraph，最重要的是不要一开始就迷恋复杂 agent。先把这条线走顺：

```text
模型初始化
-> 消息调用
-> 结构化输出
-> 工具函数
-> 工具调用循环
-> StateGraph
-> state / node / edge
-> reducer
-> Command / conditional edges
-> subgraph
-> MCP
-> Server / CLI / langgraph.json
```

等这条线清楚以后，再去看 Open Deep Research 这种项目，就不会觉得它是一团函数和 prompt 缠在一起。它其实是一组图：主图负责总流程，监督者子图负责拆任务，研究者子图负责搜索和压缩。复杂系统不可怕，前提是你知道它复杂在哪里。
