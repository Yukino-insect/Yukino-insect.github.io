+++
date = '2026-08-17T20:30:28+08:00'
draft = false
title = "LangChain / LangGraph 高级特性讲义：Runnable、工具、持久化、检查点、记忆、中断与子图"
+++

> 整理日期：2026-08-17  
> 版本背景：当前项目 `uv.lock` 中锁定 `langchain==1.3.9`、`langchain-core==1.4.8`、`langgraph==1.2.9`。  
> 适用读者：已经了解 Python、LangChain 基础调用、LangGraph 的 `StateGraph` / node / edge / reducer，但对高级特性的边界和原理仍然有些模糊的人。  
> 语境提醒：LangChain / LangGraph 的 API 变化很快。旧资料里的 `LLMChain`、旧版 memory class、`initialize_agent`、旧路径导入等并不一定错，只是未必适合当前版本。把旧教程当法律条文使用，是一种很有效的自我折磨方式。

## 目录

1. 先回答你的三个问题
2. `Runnable` 到底是什么
3. `@tool` 为什么有 `.invoke`
4. 模型、工具、agent、graph 为什么都能 `.invoke`
5. `MessagesState`、`add_messages` 和 reducer
6. 短期记忆、长期记忆、线程：先把词分清楚
7. 持久性 persistence：LangGraph 到底持久化了什么
8. 检查点 checkpointer：使用方法和基础原理
9. 线程 thread：它不是操作系统线程
10. 记忆 memory：不是只有把 messages 越堆越长
11. 中断 interrupt：人机协作和恢复执行
12. 时间旅行 time travel、状态查看和状态修改
13. 子图 subgraph：组合、状态映射和持久化模式
14. `Command`、`Send`、并行 super-step 与 reducer 的关系
15. Functional API、task 与节点内持久化
16. 工程设计建议：怎样把这些特性放进真实 agent
17. 当前 `open_deep_research` 项目中的对应关系
18. 常见误区和排错清单
19. 练习题
20. 参考资料

## 1. 先回答你的三个问题

### 1.1 `@tool` 修饰后为什么可以 `.invoke`

简短回答：是的，核心原因是 LangChain 把 tool 包装成了实现 `Runnable` 接口的对象。

更准确地说：

```python
from langchain_core.tools import tool, BaseTool

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

print(type(add))
# <class 'langchain_core.tools.structured.StructuredTool'>

print(isinstance(add, BaseTool))
# True

print(add.invoke({"a": 1, "b": 2}))
# 3
```

在当前项目环境中验证可见：

```text
StructuredTool
  -> BaseTool
  -> RunnableSerializable[Union[str, dict, ToolCall], Any]
  -> RunnableSerializable
  -> Serializable
```

也就是说，被 `@tool` 装饰后的 `add` 已经不是原来的普通 Python 函数，而是一个 `StructuredTool` 对象。它有：

- `name`
- `description`
- `args_schema`
- `invoke`
- `ainvoke`
- `batch`
- `stream`
- 以及 LangChain Runnable 生态里的配置、追踪、重试等能力

所以它可以像模型一样 `.invoke(...)`。不过请注意，这只说明它们共享调用接口，不代表它们语义相同。

模型的 `.invoke` 是“向模型请求一次生成”。

工具的 `.invoke` 是“执行这个工具函数”。

graph 的 `.invoke` 是“运行这张图，直到结束或中断”。

接口统一，不等于东西一样。制服一样，不代表一个是学生会长另一个也是学生会长。请稍微尊重一下对象的职业分工。

### 1.2 `MessagesState` 的 messages 累加很粗糙，LangGraph 的记忆是不是靠检查点

这个问题要拆成两层。

第一层：`MessagesState` 的 `messages` 字段确实是短期上下文的常见载体。它使用 `add_messages` reducer，会把新消息加入已有消息列表，并且能根据 message id 覆盖已有消息。它比单纯的 `operator.add` 稍微聪明一些，但它本质上仍然是“把对话历史放进 state”。

第二层：LangGraph 的短期记忆确实依赖 checkpointer。只要图编译时传入 checkpointer，并且调用时传入 `thread_id`，LangGraph 就会把这个线程下的图状态保存成 checkpoints。下一次用同一个 `thread_id` 调用时，图可以从该线程的已有状态继续。

所以：

```text
messages reducer 负责“状态字段如何合并”。
checkpointer 负责“状态如何跨调用保存和恢复”。
thread_id 负责“保存到哪一条会话线上”。
```

这三者不是同一个概念。混在一起之后，就会出现“我已经用了 MessagesState，为什么没有记忆”之类的问题。嗯，很常见，也很合理，但确实是概念没有分层。

长期记忆则不是 checkpointer 的主要职责。LangGraph 的长期记忆通常使用 store。store 是跨线程的、应用自定义的 key-value/搜索存储，例如用户偏好、稳定事实、长期画像、知识条目等。

### 1.3 线程 thread 到底是什么，普通大模型对话是不是保存在一个线程中

LangGraph 的 thread 是逻辑线程，不是 Python `threading.Thread`，也不是 CPU 线程。

你可以把它理解成：

```text
thread_id = 一段可持续对话或任务流程的 ID
```

它类似聊天产品里的 conversation id、session id、chat id。

在普通聊天应用中，一次“新建聊天”通常就对应一个 conversation id。这个 conversation id 背后保存了历史消息、标题、创建时间、用户 id 等。LangGraph 里的 thread_id 就扮演类似角色，只不过它保存的不是单纯消息，而是整张图的状态和检查点历史。

一个用户可以有多个 thread：

```text
user_123
  thread_a: 研究 LangGraph 持久化
  thread_b: 写一份简历
  thread_c: 调试某个 agent 报错
```

同一个 thread 内的多次调用共享短期状态。不同 thread 之间默认隔离。长期记忆如果放进 store，则可以跨 thread 共享。

## 2. `Runnable` 到底是什么

`Runnable` 是 LangChain 的统一执行接口。官方参考文档把它描述为一个可以被调用、批处理、流式处理、转换和组合的工作单元。

更工程化地说，`Runnable` 是 LangChain 为所有“可执行组件”规定的一套标准协议。

常见 Runnable 包括：

| 对象 | 示例 | `.invoke` 的含义 |
| --- | --- | --- |
| chat model | `init_chat_model(...)`、`ChatOpenAI(...)` | 调一次模型 |
| prompt template | `ChatPromptTemplate.from_messages(...)` | 把变量格式化成 prompt/message |
| parser | `StrOutputParser()` | 把模型输出解析成目标格式 |
| tool | `@tool` 后的 `StructuredTool` | 执行工具函数 |
| graph | `StateGraph(...).compile()` | 运行图 |
| lambda wrapper | `RunnableLambda(fn)` | 调用 Python 函数并接入 Runnable 生态 |
| chain | `prompt | model | parser` | 按组合顺序执行 |

### 2.1 Runnable 的核心方法

常用方法可以这样理解：

| 方法 | 含义 |
| --- | --- |
| `invoke(input, config=None)` | 同步执行单个输入 |
| `ainvoke(input, config=None)` | 异步执行单个输入 |
| `batch(inputs, config=None)` | 批量执行多个输入 |
| `abatch(inputs, config=None)` | 异步批量执行 |
| `stream(input, config=None)` | 流式返回输出片段 |
| `astream(input, config=None)` | 异步流式返回 |
| `with_config(...)` | 给 Runnable 绑定运行配置 |
| `with_retry(...)` | 给 Runnable 增加重试 |
| `with_fallbacks(...)` | 给 Runnable 增加 fallback |
| `bind(...)` / `bind_tools(...)` | 绑定参数或工具 |

它的价值在于：不同组件可以用同一种方式拼接。

例如：

```python
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个严谨的 Python 教学助手。"),
    ("human", "请解释：{topic}"),
])

model = init_chat_model("openai:gpt-4.1-mini")
parser = StrOutputParser()

chain = prompt | model | parser

result = chain.invoke({"topic": "LangChain Runnable"})
```

这里的 `|` 能成立，是因为左右两边都是 Runnable 或可被自动包装成 Runnable 的对象。

### 2.2 RunnableConfig 是什么

很多 `.invoke` 都可以接收第二个参数 `config`：

```python
result = runnable.invoke(
    input_data,
    config={
        "tags": ["demo"],
        "metadata": {"source": "lecture"},
        "configurable": {"thread_id": "abc"},
    },
)
```

`RunnableConfig` 常见用途：

- `tags`: LangSmith 追踪标签
- `metadata`: 运行元数据
- `callbacks`: 回调处理器
- `max_concurrency`: 控制并发
- `recursion_limit`: LangGraph 最大 super-step 数
- `configurable`: 可配置字段，例如 `thread_id`、模型名、业务配置等

在 LangGraph 里，`thread_id` 通常放在：

```python
{"configurable": {"thread_id": "user-123-session-456"}}
```

这不是随便挑的位置。checkpointer 会从这里读取线程标识。放错地方，就像把钥匙贴在门外但没插进锁孔，形式上很努力，结果上很安静。

## 3. `@tool` 为什么有 `.invoke`

### 3.1 `@tool` 做了什么

`@tool` 装饰器会把一个普通 Python 函数转换成 LangChain tool 对象。

普通函数：

```python
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database."""
    return "..."
```

变成工具：

```python
from langchain_core.tools import tool

@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database."""
    return "..."
```

转换后，LangChain 会提取：

- 函数名作为 tool name
- docstring 作为 tool description
- type hints 作为输入 schema
- 函数体作为实际执行逻辑

这很重要。大模型看不到你的 Python 函数体，它主要看到的是工具名、描述和参数 schema。模型决定“是否调用工具”时，靠的是这些元信息，而不是读了你的源代码。它没有那么勤奋，虽然偶尔会表现得像已经读过。

### 3.2 工具的两种身份

一个 tool 有两种身份：

| 身份 | 给谁用 | 作用 |
| --- | --- | --- |
| schema / description | 给模型看 | 告诉模型这个工具能做什么、参数是什么 |
| executable Runnable | 给程序运行 | 真正执行工具函数 |

例如：

```python
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"{city}: sunny"

model = init_chat_model("openai:gpt-4.1-mini")
model_with_tools = model.bind_tools([get_weather])
```

`bind_tools` 的意思不是“模型现在会自动执行工具函数”。它的意思是“模型调用时可以产生 tool call”。

可能的模型输出类似：

```python
AIMessage(
    content="",
    tool_calls=[
        {
            "name": "get_weather",
            "args": {"city": "Shanghai"},
            "id": "call_xxx",
        }
    ],
)
```

真正执行工具，通常要由：

- 你自己写代码执行
- LangGraph 的 `ToolNode`
- LangChain `create_agent(...)` 创建的 agent loop
- 自定义 graph 中的工具执行节点

来完成。

### 3.3 手动执行 tool call

简化版：

```python
from langchain_core.messages import ToolMessage

tools = [get_weather]
tools_by_name = {tool.name: tool for tool in tools}

ai_message = model_with_tools.invoke("上海天气怎么样？")

tool_messages = []
for tool_call in ai_message.tool_calls:
    tool = tools_by_name[tool_call["name"]]
    observation = tool.invoke(tool_call["args"])
    tool_messages.append(
        ToolMessage(
            content=str(observation),
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
        )
    )
```

当前项目中 `src/open_deep_research/deep_researcher.py` 的 `researcher_tools` 就是这个思路：

```python
tools_by_name = {
    tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool
    for tool in tools
}

tool_execution_tasks = [
    execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config)
    for tool_call in tool_calls
]
```

其中：

```python
return await tool.ainvoke(args, config)
```

就是在调用 tool 这个 Runnable。

### 3.4 `@tool`、Pydantic schema 和结构化工具

复杂参数最好显式写 Pydantic 模型：

```python
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class WeatherInput(BaseModel):
    location: str = Field(description="城市名或坐标")
    units: Literal["celsius", "fahrenheit"] = "celsius"
    include_forecast: bool = False

@tool(args_schema=WeatherInput)
def get_weather(
    location: str,
    units: str = "celsius",
    include_forecast: bool = False,
) -> str:
    """Get current weather and optional forecast."""
    return f"{location}: 22 degrees {units}"
```

这不仅是为了 Python 类型好看，更是为了让模型知道怎么构造参数。工具 schema 写得含糊，模型调用就会含糊。你不能给它一张模糊地图，然后责怪它没有优雅地到达目的地。

## 4. 模型、工具、agent、graph 为什么都能 `.invoke`

因为它们都处在 Runnable 生态里。

但必须分清“调用入口统一”和“业务语义不同”。

| 调用 | 输入 | 输出 | 是否有状态 |
| --- | --- | --- | --- |
| `model.invoke(...)` | 字符串、消息列表、PromptValue | `AIMessage` | 模型自身通常无会话状态 |
| `tool.invoke(...)` | 字符串、dict、ToolCall | 工具函数返回值 | 工具自身通常无状态，除非你写了外部副作用 |
| `agent.invoke(...)` | 通常是 `{"messages": [...]}` | agent 状态 dict | 可以有状态，取决于 checkpointer |
| `graph.invoke(...)` | 图输入 state | 图最终 state 或中断信息 | 可以有状态，取决于 checkpointer |
| `chain.invoke(...)` | chain 第一个组件的输入 | chain 最后组件的输出 | 取决于组件 |

一个很容易误会的点：

```python
model.invoke([
    {"role": "user", "content": "你好"}
])
```

这不会自动保存历史。下一次：

```python
model.invoke([
    {"role": "user", "content": "你还记得我刚才说什么吗？"}
])
```

模型大概率不记得，因为你没有把历史消息再次传入。

而：

```python
graph.invoke(
    {"messages": [{"role": "user", "content": "你好"}]},
    {"configurable": {"thread_id": "1"}},
)
```

如果 graph 编译时使用了 checkpointer，那么这次更新会保存到 `thread_id="1"` 的图状态里。下一次同一个 thread 可以读取之前状态。这就是短期记忆的基础。

## 5. `MessagesState`、`add_messages` 和 reducer

### 5.1 StateGraph 的状态更新不是函数返回值传递

LangGraph 的节点通常返回“状态更新”，不是完整状态。

```text
current_state -> node -> partial_update
current_state + partial_update --reducer--> next_state
```

如果没有 reducer，默认行为是覆盖。

```python
from typing_extensions import TypedDict

class State(TypedDict):
    count: int
    logs: list[str]

def node_a(state: State):
    return {"logs": ["a"]}

def node_b(state: State):
    return {"logs": ["b"]}
```

如果 `logs` 没有 reducer，`node_b` 返回后，`logs` 会变成 `["b"]`，不是 `["a", "b"]`。

### 5.2 自定义 reducer

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict

class State(TypedDict):
    logs: Annotated[list[str], operator.add]
```

现在：

```text
["a"] + ["b"] -> ["a", "b"]
```

当前项目中 `src/open_deep_research/state.py` 有一个 `override_reducer`：

```python
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
```

这是一种很实用的工程技巧：

- 平时追加
- 必要时用 `{"type": "override", "value": ...}` 强制覆盖

例如项目里清空 `notes`：

```python
cleared_state = {"notes": {"type": "override", "value": []}}
```

### 5.3 `MessagesState` 是什么

`MessagesState` 等价于一个预置 state：

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

它只有一个核心字段：

```text
messages
```

这个字段使用 `add_messages` reducer。

### 5.4 `add_messages` 比 `operator.add` 多做了什么

如果只是追加消息，`operator.add` 也能做：

```python
messages = old_messages + new_messages
```

但消息有 id。某些场景下你需要更新已有消息，而不是永远追加。例如人类审批后修改某条消息、工具结果补写、状态回放时覆盖同 id 消息。

`add_messages` 的能力包括：

- 新 message 追加到列表
- 如果新 message 和旧 message 有相同 id，则替换旧 message
- 将 dict 形式的消息反序列化为 LangChain message 对象

所以在 node 中可以这样访问：

```python
last = state["messages"][-1]
print(last.content)
```

而不是永远对 dict 做 `["content"]`。当然，前提是你的 reducer 已经把它们转成了 message 对象。

### 5.5 `MessagesState` 不是完整记忆系统

`MessagesState` 只是状态 schema 和 reducer。它不会自动：

- 判断哪些消息重要
- 压缩历史
- 删除过期上下文
- 写入长期用户画像
- 做语义检索
- 解决上下文窗口过长

如果只是让 `messages` 无限增长，确实能形成某种“短期记忆”，但它很粗糙：

- token 成本越来越高
- 响应越来越慢
- 上下文超过模型限制会报错
- 旧信息干扰新任务
- 重要事实可能淹没在聊天噪声里

所以成熟系统通常会组合：

```text
MessagesState + checkpointer + message trimming/summarization + store + retrieval
```

请不要指望一个列表承担完整记忆系统的尊严。列表会累，它也没有申请过这个职位。

## 6. 短期记忆、长期记忆、线程：先把词分清楚

### 6.1 四个概念

| 概念 | 英文 | 作用 | 范围 |
| --- | --- | --- | --- |
| state | 状态 | 当前图运行时可读写的数据 | 图内部 |
| checkpoint | 检查点 | 某个时刻的 state 快照 | thread 内 |
| thread | 线程 | 一条会话或任务流程的逻辑 ID | 隔离短期状态 |
| store | 存储 | 长期记忆或应用数据 | 可跨 thread |

### 6.2 短期记忆

短期记忆通常是：

```text
某个 thread 内，图状态里保存的 conversation history 和中间结果
```

在 LangGraph 中，短期记忆由 checkpointer 实现持久化。

例如：

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END

builder = StateGraph(MessagesState)

def echo(state: MessagesState):
    return {"messages": [{"role": "assistant", "content": "收到。"}]}

builder.add_node("echo", echo)
builder.add_edge(START, "echo")
builder.add_edge("echo", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "thread-1"}}

graph.invoke(
    {"messages": [{"role": "user", "content": "你好"}]},
    config,
)
```

同一个 `thread_id` 的后续调用可以接上已有状态。

### 6.3 长期记忆

长期记忆通常是：

```text
跨 thread、跨会话、跨运行保存的用户偏好、事实、知识或业务数据
```

在 LangGraph 中，长期记忆一般使用 store。

例如：

```text
namespace = (user_id, "memories")
key = memory_id
value = {"data": "用户偏好深色主题"}
```

只要 namespace 设计为以 `user_id` 开头，这份记忆就可以被同一个用户的多个 thread 共享。

### 6.4 为什么说记忆和线程绑定

这句话通常指短期记忆。

因为 checkpointer 保存的是 thread 的 graph state。它用 `thread_id` 作为主键或主索引来保存和恢复检查点。

```text
checkpointer
  thread_id = "a"
    checkpoint_1
    checkpoint_2
    checkpoint_3
  thread_id = "b"
    checkpoint_1
    checkpoint_2
```

所以同一个图、同一个用户，如果你每次都传不同 `thread_id`，就像每次都新建聊天，当然“不记得”。

反过来，如果不同用户误用了同一个 `thread_id`，就可能串线。这在生产系统里是严重问题。

### 6.5 普通大模型对话是不是都保存在一个线程中

从产品概念看，通常是类似的。

比如一个聊天产品：

```text
用户点击“新建聊天”
  -> 后端创建 conversation_id
  -> 每次发送消息都带 conversation_id
  -> 后端取出历史消息
  -> 拼进模型上下文
  -> 保存新消息
```

LangGraph 的 thread_id 可以承担类似 conversation_id 的职责。

但注意：

- 普通 chat model API 本身通常是无状态的
- 是否保存历史，是应用层做的
- LangGraph 的 checkpointer 是一种应用层持久化机制
- LangGraph thread 保存的是 graph state，不只是消息

## 7. 持久性 persistence：LangGraph 到底持久化了什么

LangGraph 的 persistence 主要由两套系统组成：

| 系统 | 保存什么 | 典型用途 |
| --- | --- | --- |
| checkpointer | 每个 thread 的 graph state checkpoints | 短期记忆、恢复、中断、时间旅行、容错 |
| store | 应用自定义 key-value 数据 | 长期记忆、用户偏好、知识、跨 thread 数据 |

### 7.1 没有 checkpointer 时

如果你这样编译：

```python
graph = builder.compile()
```

那么图仍然能运行，但运行结束后状态不会自动持久化到某个 thread。

你可以把它理解成一次普通函数调用：

```text
输入 -> 执行 -> 输出
```

它不会自动记得上次运行。

当前项目的主图：

```python
deep_researcher = deep_researcher_builder.compile()
```

没有在定义处绑定 checkpointer。测试代码中会这样做：

```python
graph = deep_researcher_builder.compile(checkpointer=MemorySaver())
```

这说明项目本体把图结构和持久化选择分开了。对于教学、测试、部署，这是常见做法。

### 7.2 有 checkpointer 时

```python
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())
```

调用时必须传 `thread_id`：

```python
config = {"configurable": {"thread_id": "1"}}
graph.invoke(input_state, config)
```

LangGraph 会在 super-step 边界保存 state snapshot。

### 7.3 有 store 时

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
graph = builder.compile(store=store)
```

node 中可以通过 `Runtime` 访问：

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.graph import MessagesState

@dataclass
class Context:
    user_id: str

def remember_preference(state: MessagesState, runtime: Runtime[Context]):
    namespace = (runtime.context.user_id, "memories")
    runtime.store.put(
        namespace,
        "theme",
        {"data": "用户偏好深色主题"},
    )
    return {}
```

调用时传 context：

```python
graph.invoke(
    {"messages": [{"role": "user", "content": "我喜欢深色主题"}]},
    {"configurable": {"thread_id": "thread-1"}},
    context=Context(user_id="user-1"),
)
```

这里要分清：

```text
thread_id 决定短期状态属于哪条对话。
context.user_id 决定长期记忆属于哪个用户。
```

它们可以相同，也可以不同。生产系统里更常见的是不同：

```text
user_id = "u_001"
thread_id = "chat_2026_08_17_001"
```

## 8. 检查点 checkpointer：使用方法和基础原理

### 8.1 最小用法

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END

builder = StateGraph(MessagesState)

def call_model(state: MessagesState):
    # 这里省略真实模型调用
    return {"messages": [{"role": "assistant", "content": "hello"}]}

builder.add_node("call_model", call_model)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "demo-thread"}}

graph.invoke(
    {"messages": [{"role": "user", "content": "hi"}]},
    config,
)
```

`InMemorySaver` 适合演示和测试。进程结束，数据就没了。生产环境应使用数据库后端，例如 Postgres checkpointer。

### 8.2 checkpointer 存的不是“最终结果”

它保存的是一系列 checkpoints。

一个 thread 可能长这样：

```text
thread_id = "demo-thread"

checkpoint 0: 输入进入 START 后的状态
checkpoint 1: node_a 执行后的状态
checkpoint 2: node_b 执行后的状态
checkpoint 3: END 前后的最终状态
```

如果是循环 agent：

```text
model -> tools -> model -> tools -> model -> END
```

每轮都会产生状态更新，checkpointer 会记录这些 super-step 边界上的状态。

### 8.3 super-step 是什么

LangGraph 的执行模型受 Pregel / BSP 思想影响。你可以简单理解为：

```text
一个 super-step = 当前被调度的一批节点并行执行的一轮 tick
```

顺序图：

```text
START -> A -> B -> END
```

大致会有：

```text
super-step 0: 输入
super-step 1: A
super-step 2: B
```

并行图：

```text
      -> B ->
START       -> D
      -> C ->
```

`B` 和 `C` 可能在同一个 super-step 执行。它们都返回更新，然后 LangGraph 用 reducer 合并。

这就是 reducer 对并行很重要的原因。如果两个并行节点都写同一个 key，而该 key 没有合适 reducer，你就会遇到冲突或覆盖。

### 8.4 checkpoint snapshot 通常包含什么

你通过：

```python
snapshot = graph.get_state(config)
```

拿到的是 `StateSnapshot`。它通常包含：

- `values`: 当前 state 值
- `next`: 下一步将执行的节点
- `tasks`: 待执行任务或中断信息
- `config`: 当前 checkpoint 对应配置
- `metadata`: checkpoint 元数据
- `created_at`: 创建时间
- `parent_config`: 父 checkpoint 配置

不同版本细节可能略有差异，但心智模型是稳定的：

```text
StateSnapshot = 某个 thread 在某个 checkpoint 的状态快照和执行位置
```

### 8.5 查看当前状态

```python
state = graph.get_state(config)
print(state.values)
print(state.next)
```

### 8.6 查看历史状态

```python
history = list(graph.get_state_history(config))
for snapshot in history:
    print(snapshot.created_at, snapshot.values)
```

这对调试 agent 非常有用。相比“凭感觉怀疑模型发疯”，看历史状态至少显得比较文明。

### 8.7 修改状态

```python
graph.update_state(
    config,
    {"messages": [{"role": "user", "content": "补充信息"}]},
)
```

如果某个字段有 reducer，`update_state` 也会按 reducer 写入。

有时你需要指定 `as_node`：

```python
graph.update_state(
    config,
    {"approved": True},
    as_node="human_review",
)
```

`as_node` 的含义是：这次状态更新被视为哪个节点产生的。它会影响后续执行从哪里继续。

### 8.8 pending writes 和容错

官方文档中提到，LangGraph 不只在 super-step 边界保存 checkpoint，也会记录节点级别的 writes。这样如果同一个 super-step 中有多个并行节点，某个节点成功、另一个失败，成功节点的写入可以被保留，恢复时不必全部重跑。

这个机制对长耗时、多工具、多并行分支的 agent 很重要。否则一次网络抖动就让所有已完成工具调用重跑，实在很浪费，也不怎么优雅。

### 8.9 生产 checkpointer

教学和测试：

```python
from langgraph.checkpoint.memory import InMemorySaver
checkpointer = InMemorySaver()
```

生产需要先安装对应持久化包，例如 Postgres checkpointer 通常需要：

```powershell
uv add "psycopg[binary,pool]" langgraph-checkpoint-postgres
```

然后使用数据库后端：

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
```

生产环境要考虑：

- 数据库连接池
- checkpoint 表迁移
- 序列化兼容
- thread_id 命名规则
- 用户权限隔离
- 数据清理策略
- 旧图版本和旧 checkpoint 的兼容

## 9. 线程 thread：它不是操作系统线程

### 9.1 thread 是 checkpoint 的命名空间

当你调用：

```python
config = {"configurable": {"thread_id": "abc"}}
graph.invoke(input_state, config)
```

checkpointer 会把 state 保存到 `thread_id="abc"` 下面。

下一次：

```python
graph.invoke(new_input, config)
```

会读取同一 thread 的已有状态，再合并新输入，继续执行。

### 9.2 thread、run、assistant 的关系

在 LangGraph Server 语境里，经常会看到：

| 概念 | 含义 |
| --- | --- |
| assistant | 某个已部署的 graph 配置或 agent 配置 |
| thread | 一条会话或任务状态线 |
| run | 在某个 thread 上执行一次 assistant |
| checkpoint | run 过程中保存的状态快照 |

关系大致是：

```text
assistant: deep_researcher
  thread: user_1_chat_a
    run_1
      checkpoint_1
      checkpoint_2
    run_2
      checkpoint_3
      checkpoint_4
  thread: user_1_chat_b
    run_1
      checkpoint_1
```

### 9.3 thread 设计建议

不要用固定字符串：

```python
{"thread_id": "1"}  # 教学可以，生产不行
```

建议：

```python
thread_id = f"{user_id}:{conversation_id}"
```

或者直接使用数据库生成的 conversation id：

```python
thread_id = "chat_01JABC..."
```

关键要求：

- 同一会话稳定
- 不同用户隔离
- 不暴露敏感信息
- 可追踪
- 可删除

### 9.4 thread 和权限

当前项目中 `src/security/auth.py` 做了 thread 权限控制：

```python
@auth.on.threads.create
@auth.on.threads.create_run
async def on_thread_create(ctx, value):
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
```

读取时：

```python
@auth.on.threads.read
@auth.on.threads.search
async def on_thread_read(ctx, value):
    return {"owner": ctx.user.identity}
```

这说明生产系统里 thread 不只是技术 ID，也是安全边界的一部分。

如果 thread 权限错了，用户 A 看到用户 B 的状态，那就不是“记忆功能有点小问题”，而是事故。

## 10. 记忆 memory

### 10.1 短期记忆的典型实现

```text
MessagesState.messages
  + checkpointer
  + thread_id
  = thread-scoped short-term memory
```

示意：

```python
graph = builder.compile(checkpointer=InMemorySaver())

graph.invoke(
    {"messages": [{"role": "user", "content": "我叫小明"}]},
    {"configurable": {"thread_id": "chat-1"}},
)

graph.invoke(
    {"messages": [{"role": "user", "content": "我叫什么？"}]},
    {"configurable": {"thread_id": "chat-1"}},
)
```

第二次调用可以访问第一次调用保存的 `messages`，前提是你的图节点确实把这些 messages 传给模型。

### 10.2 短期记忆不是越长越好

长对话的主要问题：

- 超过上下文窗口
- 成本升高
- 延迟增加
- 旧信息污染
- 模型注意力分散

所以常见策略有：

| 策略 | 做法 | 适合场景 |
| --- | --- | --- |
| trimming | 只保留最近 N 条或 N tokens | 简单聊天 |
| summarization | 把旧消息压缩成摘要 | 长对话 |
| selective memory | 只保留关键信息 | 任务型 agent |
| retrieval | 旧信息入库，需要时检索 | 长期知识 |
| explicit state | 把关键信息放结构化字段 | 工作流状态 |

### 10.3 修剪消息

可以在模型调用前修剪，而不是直接破坏 checkpoint 中的完整历史：

```python
from langchain_core.messages import trim_messages

trimmed = trim_messages(
    state["messages"],
    max_tokens=4000,
    strategy="last",
    token_counter=model,
)

response = model.invoke(trimmed)
```

也可以把修剪后的消息写回 state，但要谨慎。写回意味着历史真的被你删了。不是不能删，只是要知道自己在删。

### 10.4 摘要式短期记忆

可以扩展 state：

```python
from typing_extensions import TypedDict
from langgraph.graph import MessagesState

class State(MessagesState):
    summary: str
```

每隔几轮把旧消息压缩到 `summary`：

```python
def summarize_if_needed(state: State):
    if len(state["messages"]) < 20:
        return {}

    # 省略真实模型调用
    new_summary = "用户正在学习 LangGraph 的持久化和中断。"

    return {
        "summary": new_summary,
        # 可以结合 RemoveMessage 删除旧消息，或用自定义策略保留最近消息
    }
```

模型调用时：

```python
messages = [
    {"role": "system", "content": f"历史摘要：{state.get('summary', '')}"},
    *recent_messages,
]
```

这比无限堆 `messages` 更可控。

### 10.5 长期记忆 store

store 用于跨 thread 保存信息。

示例：

```python
import uuid
from dataclasses import dataclass
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

@dataclass
class Context:
    user_id: str

def memory_node(state: MessagesState, runtime: Runtime[Context]):
    namespace = (runtime.context.user_id, "memories")

    # 搜索已有记忆
    memories = runtime.store.search(
        namespace,
        query=state["messages"][-1].content,
        limit=3,
    )

    # 写入一条新记忆
    runtime.store.put(
        namespace,
        str(uuid.uuid4()),
        {"data": "用户正在学习 LangGraph 高级特性"},
    )

    info = "\n".join(item.value["data"] for item in memories)
    return {
        "messages": [
            {"role": "assistant", "content": f"参考记忆：{info or '暂无'}"}
        ]
    }

builder = StateGraph(MessagesState, context_schema=Context)
builder.add_node("memory_node", memory_node)
builder.add_edge(START, "memory_node")
builder.add_edge("memory_node", END)

graph = builder.compile(
    checkpointer=InMemorySaver(),
    store=InMemoryStore(),
)
```

调用：

```python
graph.invoke(
    {"messages": [{"role": "user", "content": "继续讲记忆"}]},
    {"configurable": {"thread_id": "thread-1"}},
    context=Context(user_id="user-1"),
)
```

### 10.6 长期记忆的 namespace 设计

常见设计：

```python
(user_id, "profile")
(user_id, "preferences")
(user_id, "facts")
(user_id, "projects", project_id)
("global", "product_docs")
```

不要把所有东西塞进一个 namespace。否则检索时会把“用户喜欢深色主题”和“上次工具调用失败栈”一起端上来，场面会很丰富，但不一定有用。

### 10.7 什么时候更新长期记忆

两种模式：

| 模式 | 含义 | 优点 | 缺点 |
| --- | --- | --- | --- |
| hot path | 回复用户前同步判断并写记忆 | 立即可用 | 增加延迟，模型可能多做一步 |
| background | 回复后异步提取记忆 | 不影响主响应 | 记忆稍后才可用，系统更复杂 |

教学阶段可以用 hot path。生产系统常常会把记忆提取作为后台任务。

## 11. 中断 interrupt：人机协作和恢复执行

### 11.1 interrupt 是什么

`interrupt()` 可以在节点执行中暂停图，并把一个 JSON 可序列化 payload 返回给调用方。

之后你可以用 `Command(resume=...)` 恢复执行。恢复值会成为 `interrupt()` 调用的返回值。

这适合：

- 人类审批
- 让用户补充信息
- 客户端执行 headless tool
- 等待外部系统回调
- 支付、权限、危险操作确认

### 11.2 最小示例

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    action: str
    approved: bool

def approval_node(state: State):
    approved = interrupt({
        "question": f"是否批准操作：{state['action']}？"
    })
    return {"approved": bool(approved)}

builder = StateGraph(State)
builder.add_node("approval", approval_node)
builder.add_edge(START, "approval")
builder.add_edge("approval", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "approval-1"}}

first = graph.invoke({"action": "delete_file"}, config)
print(first["__interrupt__"])

second = graph.invoke(Command(resume=True), config)
print(second["approved"])
```

### 11.3 interrupt 的三个必要条件

1. 编译 graph 时有 checkpointer
2. 调用时有 `thread_id`
3. 节点中调用 `interrupt(payload)`

没有 checkpointer，LangGraph 不知道恢复到哪里。

没有 thread_id，checkpointer 不知道保存到哪里。

payload 不能序列化，调用方就很难稳定接收和恢复。

### 11.4 interrupt 的执行原理

第一次运行到：

```python
approved = interrupt({"question": "是否批准？"})
```

LangGraph 会：

1. 保存当前 thread 的状态和执行位置
2. 暂停 graph
3. 向调用方返回 `__interrupt__`

之后恢复：

```python
graph.invoke(Command(resume=True), config)
```

LangGraph 会：

1. 根据 `thread_id` 找到暂停的 checkpoint
2. 从中断点所在节点恢复
3. 让 `interrupt(...)` 表达式返回 `True`
4. 继续执行节点后续代码

### 11.5 中断前的副作用要幂等

危险示例：

```python
def approval_node(state):
    charge_credit_card(state["amount"])
    approved = interrupt("批准吗？")
    return {"approved": approved}
```

如果恢复时节点从头执行，`charge_credit_card` 可能再次执行。于是你收了两次钱。用户可能会记住你，但不是以你希望的方式。

更好的写法：

```python
def approval_node(state):
    approved = interrupt("批准扣款吗？")
    if approved:
        charge_credit_card_once(
            amount=state["amount"],
            idempotency_key=state["payment_id"],
        )
    return {"approved": approved}
```

原则：

- `interrupt()` 前避免不可重复副作用
- 必须有副作用就使用 idempotency key
- 数据库写入使用 upsert 或唯一约束
- 外部 API 调用要有请求去重

### 11.6 interrupt 和静态 breakpoint 的区别

| 类型 | 特点 |
| --- | --- |
| interrupt | 在代码里动态触发，可以条件判断，可以携带 payload |
| breakpoint | 编译或运行配置中的静态暂停点，常用于调试 |

需要业务人机协作时，用 `interrupt()`。

需要调试某个节点前后状态时，用 breakpoint。

## 12. 时间旅行 time travel、状态查看和状态修改

### 12.1 为什么需要时间旅行

Agent 的错误常常不是最后一步才出现的。

可能是：

- 第 2 步提取需求错了
- 第 4 步调用工具参数错了
- 第 6 步摘要丢了关键信息
- 第 8 步才表现为最终答案跑偏

如果有 checkpoints，你可以回看每一步 state。

### 12.2 查看历史

```python
history = list(graph.get_state_history(config))

for snapshot in history:
    print("created:", snapshot.created_at)
    print("next:", snapshot.next)
    print("values:", snapshot.values)
```

### 12.3 从历史 checkpoint 分叉

思路：

1. 找到某个历史 snapshot
2. 拿到它的 config
3. 用 `update_state` 修改状态
4. 从该 checkpoint 继续运行

示例伪代码：

```python
history = list(graph.get_state_history(config))
old = history[-3]

fork_config = graph.update_state(
    old.config,
    {"topic": "LangGraph checkpoint 原理"},
)

result = graph.invoke(None, fork_config)
```

这会从旧 checkpoint 分叉出一条新的执行路径。

### 12.4 update_state 的 reducer 影响

如果 state 是：

```python
class State(MessagesState):
    tags: Annotated[list[str], operator.add]
```

那么：

```python
graph.update_state(config, {"tags": ["new"]})
```

不是覆盖，而是追加。想覆盖就要设计覆盖 reducer，或使用 LangGraph 支持的覆盖机制。当前项目的 `override_reducer` 就是为了这个需求。

### 12.5 不要把 `Command(update=...)` 当成普通新输入

在当前 LangGraph 语境中，`Command(resume=...)` 是作为 `invoke` 输入恢复 interrupt 的典型方式。

不要在一个已经结束的 thread 上随手：

```python
graph.invoke(Command(update={"messages": [...]}), config)
```

这可能让图从最后 checkpoint 继续，而不是从 `START` 开始。多轮普通对话，应传新的 input state：

```python
graph.invoke(
    {"messages": [{"role": "user", "content": "继续"}]},
    config,
)
```

只有恢复中断时才传：

```python
graph.invoke(Command(resume=user_feedback), config)
```

## 13. 子图 subgraph：组合、状态映射和持久化模式

### 13.1 子图是什么

子图就是一张编译后的 graph，被放进另一张 graph 里作为节点使用，或者被某个节点手动调用。

它适合：

- 多 agent
- 可复用 workflow
- 分层任务
- 将复杂流程拆成独立模块
- 给不同子流程单独 state schema

### 13.2 模式一：共享 state key，直接作为节点

如果父图和子图有共享 key，可以直接：

```python
parent_builder.add_node("research_supervisor", supervisor_subgraph)
```

当前项目就是这样：

```python
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)
```

父图 `AgentState` 有：

```python
supervisor_messages
research_brief
raw_notes
notes
```

子图 `SupervisorState` 也有这些共享字段。于是子图能读写这些 key，返回后父图继续拿到合并后的状态。

### 13.3 模式二：手动调用子图，自己做输入输出映射

当前项目的监督者调用研究者子图：

```python
tool_results = await asyncio.gather(*[
    researcher_subgraph.ainvoke({
        "researcher_messages": [
            HumanMessage(content=tool_call["args"]["research_topic"])
        ],
        "research_topic": tool_call["args"]["research_topic"]
    }, config)
    for tool_call in allowed_conduct_research_calls
])
```

这是手动调用：

- 父图/监督者 state 里没有直接把全部字段给研究者
- 只传研究者需要的输入
- 拿回 `compressed_research` 和 `raw_notes`
- 再转成 `ToolMessage` 写回监督者上下文

这在多 agent 中很常见。子 agent 有自己的 state，不必污染父图。

### 13.4 什么时候直接嵌入，什么时候手动调用

| 场景 | 建议 |
| --- | --- |
| 父子共享同一批状态字段 | 直接把 compiled subgraph 作为节点 |
| 父子状态结构不同 | 在普通节点中手动调用子图 |
| 需要并行启动多个子任务 | 手动 `ainvoke` 或使用 `Send` |
| 子图是可复用工具型 workflow | 手动调用更清晰 |
| 需要子图保留自己的多轮 thread 记忆 | 使用子图 checkpointer 的 per-thread 模式 |

### 13.5 子图持久化模式

根据官方文档，子图持久化大致有三种模式：

| `checkpointer=` | 行为 |
| --- | --- |
| `None` 默认 | per-invocation。通常继承父图 checkpointer，以支持单次调用内的 interrupt 和 durable execution |
| `True` | per-thread。子图在同一 thread 上跨调用累积自己的状态 |
| `False` | stateless。禁用 checkpoint，像普通函数调用 |

普通多 agent 子任务，默认模式通常够用。

如果子 agent 本身需要多轮对话记忆，比如“研究助手”在多次用户请求间持续积累上下文，就考虑 per-thread。

如果子图纯计算、无中断、无恢复需求，可以 stateless。

### 13.6 父图 checkpointer 很关键

子图要支持中断、状态检查、持久化，父图通常也要有 checkpointer。否则父图本身不能保存执行位置，子图暂停后也难以从完整上下文恢复。

### 13.7 子图和 `Command.PARENT`

子图内部节点可以通过 `Command(graph=Command.PARENT, goto=...)` 跳回父图某个节点。

示意：

```python
from typing import Literal
from langgraph.types import Command

def sub_node(state) -> Command[Literal["parent_node"]]:
    return Command(
        update={"foo": "bar"},
        goto="parent_node",
        graph=Command.PARENT,
    )
```

注意：如果子图向父图更新共享 key，父图 state 上必须有合理 reducer。否则并行或跨图更新可能冲突。

## 14. `Command`、`Send`、并行 super-step 与 reducer 的关系

### 14.1 `Command`

`Command` 可以同时表达：

- `update`: 更新 state
- `goto`: 跳转到下一个节点
- `resume`: 恢复 interrupt
- `graph`: 指定跳转目标图，例如父图

节点返回：

```python
from typing import Literal
from langgraph.types import Command

def node(state) -> Command[Literal["next_node"]]:
    return Command(
        update={"foo": "bar"},
        goto="next_node",
    )
```

当前项目大量使用 `Command`：

```python
return Command(
    goto="research_supervisor",
    update={
        "research_brief": response.research_brief,
        "supervisor_messages": {
            "type": "override",
            "value": [
                SystemMessage(content=supervisor_system_prompt),
                HumanMessage(content=response.research_brief),
            ],
        },
    },
)
```

这比“节点只返回 state，然后条件边再路由”更集中，适合业务分支明确的流程。

### 14.2 不要同时给同一节点写静态边和 `Command(goto=...)`

如果节点返回：

```python
return Command(goto="b")
```

同时你又定义了：

```python
builder.add_edge("a", "c")
```

那么可能 `b` 和 `c` 都会执行。除非你就是想这样，否则不要混用。

一个节点要么靠静态边/条件边路由，要么靠 `Command` 路由。清清楚楚，世界会少很多不必要的热闹。

### 14.3 `Send`

`Send` 用于动态 fan-out，常见于 map-reduce。

```python
from langgraph.types import Send

def route_to_workers(state):
    return [
        Send("worker", {"topic": topic})
        for topic in state["topics"]
    ]
```

下游多个 worker 会并行执行。它们写回同一个父 state key 时，必须有 reducer。

### 14.4 并行写入与 reducer

并行节点：

```text
worker_1 -> {"results": ["a"]}
worker_2 -> {"results": ["b"]}
```

如果：

```python
results: Annotated[list[str], operator.add]
```

合并后：

```python
["a", "b"]
```

如果没有 reducer，LangGraph 不知道两个更新该如何合并，或者后写覆盖先写。

多 agent、并行搜索、并行工具调用里，reducer 不是可选装饰，是交通规则。

## 15. Functional API、task 与节点内持久化

### 15.1 Functional API 是什么

LangGraph 除了 `StateGraph`，还有 Functional API，例如 `@entrypoint` 和 `@task`。它适合把 workflow 写得更像普通函数，同时保留 checkpoint、恢复、重试等能力。

示意：

```python
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

@task
def step_a(x: int) -> int:
    return x + 1

@entrypoint(checkpointer=checkpointer)
def workflow(x: int, *, previous: int | None = None) -> int:
    base = previous or 0
    return step_a(x).result() + base
```

同一个 thread 下，`previous` 可以拿到上一次 invocation 的结果。适合一些函数式 workflow。

### 15.2 `@task` 的价值

普通节点是一个函数。checkpoint 通常在 super-step 边界保存，不在节点函数内部每一行都保存。

如果一个节点内部做多件昂贵事情：

```python
def node(state):
    a = slow_api_1()
    b = slow_api_2()
    c = slow_api_3()
    return {"result": [a, b, c]}
```

中途失败后，可能整个节点重跑。

用 `@task` 可以让节点内部的子任务结果也被 checkpoint 记录。恢复时已完成 task 可以复用。

示意：

```python
from langgraph.func import task

@task
def fetch(url: str):
    return requests.get(url).text[:100]

def call_api(state):
    futures = [fetch(url) for url in state["urls"]]
    return {"results": [f.result() for f in futures]}
```

适合：

- 节点内多 API 调用
- 节点内并行任务
- 昂贵且可缓存的步骤
- 希望恢复时减少重复工作的流程

## 16. 工程设计建议：怎样把这些特性放进真实 agent

### 16.1 推荐心智模型

```text
Runnable:
  统一调用接口

StateGraph:
  定义 agent 的状态机和执行流

State:
  保存工作流当前需要知道的东西

Reducer:
  定义并发/连续更新如何合并

Checkpointer:
  保存每个 thread 的 state 历史

Thread:
  一条对话或任务线

Store:
  跨 thread 的长期记忆和应用数据

Interrupt:
  暂停图，等待外部输入后恢复

Subgraph:
  把复杂工作流拆成可组合模块
```

### 16.2 agent 状态不要只靠 messages

坏设计：

```python
class State(MessagesState):
    pass
```

然后所有东西都塞进对话消息里。

更好的设计：

```python
class ResearchState(MessagesState):
    research_brief: str
    notes: Annotated[list[str], operator.add]
    raw_notes: Annotated[list[str], operator.add]
    final_report: str
    summary: str
```

原则：

- 模型要看的自然语言上下文放 `messages`
- 程序要稳定读写的数据放结构化字段
- 大段原始材料放 `raw_notes` 或外部 store
- 最终结果放明确字段

当前项目就是这种风格：

```python
class AgentState(MessagesState):
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: Optional[str]
    raw_notes: Annotated[list[str], override_reducer]
    notes: Annotated[list[str], override_reducer]
    final_report: str
```

这比只靠 `messages` 清楚得多。

### 16.3 短期记忆建议

推荐：

```text
graph state 保存当前任务需要的结构化状态
messages 保存最近对话和模型交互
summary 保存压缩历史
checkpointer 保存 thread 内状态
```

不要：

```text
所有东西无限追加到 messages
```

### 16.4 长期记忆建议

推荐：

```text
store 保存跨 thread 的稳定信息
namespace 用 user_id / org_id / project_id 分层
写入前判断这是否真值得长期保存
检索后再注入 prompt
```

不要：

```text
把每句话都写长期记忆
```

长期记忆不是垃圾桶。它应该更像档案室，虽然很多系统把它用得像杂物间。

### 16.5 中断建议

适合中断的点：

- 发送邮件前
- 删除数据前
- 支付或下单前
- 执行代码前
- 调用高风险外部 API 前
- 研究报告大纲确认前

中断 payload 建议：

```python
{
    "type": "approval",
    "title": "确认发送邮件",
    "details": {...},
    "options": ["approve", "reject", "edit"],
}
```

不要只返回：

```python
"OK?"
```

调用方需要结构化信息来渲染 UI 和决定恢复值。

### 16.6 checkpointer 和 store 的生产选择

开发：

```python
InMemorySaver()
InMemoryStore()
```

生产：

```text
PostgresSaver / 数据库 checkpointer
PostgresStore / 数据库 store
```

部署到 LangGraph Server 时，很多持久化能力可以由平台/服务端托管，但你仍然要理解 thread、run、checkpoint 的关系。不了解基础而直接上平台，只会更快地把问题规模扩大。

## 17. 当前 `open_deep_research` 项目中的对应关系

### 17.1 Runnable

项目中的模型：

```python
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)
```

它是 Runnable，所以可以：

```python
await configurable_model.with_config(...).ainvoke(messages)
```

项目中的工具：

```python
tools = await get_all_tools(config)
...
return await tool.ainvoke(args, config)
```

工具也是 Runnable。

项目中的子图：

```python
researcher_subgraph = researcher_builder.compile()
...
await researcher_subgraph.ainvoke(..., config)
```

编译后的 graph 也可以 invoke。

### 17.2 reducer

项目中的 `override_reducer` 很关键：

```python
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
```

它使得这些字段平时能追加：

```python
raw_notes
notes
supervisor_messages
```

必要时能覆盖：

```python
"notes": {"type": "override", "value": []}
```

### 17.3 子图

主图：

```python
deep_researcher_builder = StateGraph(
    AgentState,
    input=AgentInputState,
    config_schema=Configuration,
)
```

监督者子图：

```python
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
supervisor_subgraph = supervisor_builder.compile()
```

研究者子图：

```python
researcher_builder = StateGraph(
    ResearcherState,
    output=ResearcherOutputState,
    config_schema=Configuration,
)
researcher_subgraph = researcher_builder.compile()
```

主图直接嵌入监督者子图：

```python
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)
```

监督者手动并行调用研究者子图：

```python
tool_results = await asyncio.gather(*research_tasks)
```

这体现了两种子图用法。

### 17.4 checkpointer

项目主图默认：

```python
deep_researcher = deep_researcher_builder.compile()
```

测试中：

```python
graph = deep_researcher_builder.compile(checkpointer=MemorySaver())
```

并传：

```python
{"configurable": {"thread_id": str(uuid.uuid4())}}
```

这说明项目测试希望每次运行有独立 thread，并保存过程中状态，便于中断、查看或评测。

### 17.5 当前项目还可以扩展的记忆设计

如果要给 `open_deep_research` 加更成熟的记忆，可以考虑：

| 需求 | 方案 |
| --- | --- |
| 同一研究会话连续追问 | 编译时加入 checkpointer，前端维持同一个 thread_id |
| 用户偏好报告风格 | store namespace `(user_id, "preferences")` |
| 用户常用资料源 | store namespace `(user_id, "sources")` |
| 项目级长期研究资料 | store namespace `(user_id, "projects", project_id, "memories")` |
| 长报告防超限 | `raw_notes` 外部化存储，模型前检索或分块压缩 |
| 大纲审批 | 在报告生成前加入 `interrupt()` |

## 18. 常见误区和排错清单

### 18.1 “我用了 MessagesState，为什么没有记忆”

检查：

- graph 编译时有没有 `checkpointer=...`
- invoke 时有没有传 `{"configurable": {"thread_id": ...}}`
- 每次是不是用了同一个 thread_id
- node 调模型时有没有把 `state["messages"]` 传进去
- 是否在某个节点覆盖了 messages

### 18.2 “我用了 checkpointer，为什么长期记忆没有跨会话”

因为 checkpointer 是 thread-scoped 短期状态。跨 thread 的长期记忆应该用 store。

### 18.3 “我调用 `model.bind_tools` 后，工具为什么没有执行”

`bind_tools` 只是让模型可以生成 tool call。执行工具需要 agent loop、ToolNode 或你自己写工具执行节点。

### 18.4 “为什么工具能 `.invoke`”

因为 `@tool` 后是 `StructuredTool`，继承 `BaseTool`，而 `BaseTool` 继承 `RunnableSerializable`。

### 18.5 “thread 是不是 Python 线程”

不是。它是逻辑会话 ID，是 checkpointer 组织状态的键。

### 18.6 “为什么并行节点写 state 报错或丢数据”

检查被多个节点写入的 key 是否定义了 reducer。

### 18.7 “interrupt 恢复后副作用重复执行”

检查 `interrupt()` 前是否有数据库写入、外部 API 调用、扣款、发邮件等副作用。把副作用放到中断后，或加 idempotency key。

### 18.8 “子图状态为什么没带回父图”

检查：

- 父图和子图是否共享 key
- 共享 key 的名称是否完全一致
- 父图 state 是否有 reducer
- 如果是手动调用子图，是否把子图输出显式写回父图 state

### 18.9 “多轮对话为什么卡住”

检查你是不是在已经结束的 thread 上用 `Command(update=...)` 当新输入。普通新一轮对话应该传 state input；只有恢复 interrupt 时才用 `Command(resume=...)`。

## 19. 练习题

### 练习 1：验证 `@tool` 的类型

写一个 `multiply(a: int, b: int)` 工具，打印：

```python
type(multiply)
multiply.name
multiply.description
multiply.args_schema
multiply.invoke({"a": 2, "b": 3})
```

观察它和普通函数的区别。

### 练习 2：实现一个有短期记忆的聊天图

要求：

- 使用 `MessagesState`
- 编译时传 `InMemorySaver`
- 调用时传固定 `thread_id`
- 连续调用两次
- 第二次在 node 中打印完整 `state["messages"]`

目标：确认同一 thread 下消息被保存。

### 练习 3：给 messages 加摘要

扩展 state：

```python
class State(MessagesState):
    summary: str
```

当消息超过 6 条时，把前面的消息压缩成 `summary`，模型调用只使用：

```text
system: 历史摘要
最近几条 messages
```

目标：不要无限堆上下文。

### 练习 4：实现长期记忆 store

要求：

- 使用 `InMemoryStore`
- context 中传 `user_id`
- 用户说“记住我喜欢 X”时写入 `(user_id, "memories")`
- 另一个 thread 中询问“我喜欢什么”时从 store 搜索

目标：理解跨 thread 记忆。

### 练习 5：实现审批中断

写一个图：

```text
draft_email -> approval -> send_email
```

`approval` 中调用 `interrupt()`，用户恢复时传：

```python
Command(resume={"approved": True})
```

目标：理解中断和恢复。

### 练习 6：子图状态映射

写一个父图：

```text
planner -> worker_subgraph -> final
```

要求：

- worker 子图有自己的 state
- 父图手动调用 worker 子图
- worker 输出写回父图 `results`

目标：理解“直接嵌入子图”和“手动调用子图”的区别。

## 20. 参考资料

以下资料以当前官方文档和 API reference 为主：

- LangChain Tools 文档：<https://docs.langchain.com/oss/python/langchain/tools>
- LangChain Runnable API reference：<https://reference.langchain.com/python/langchain-core/runnables/base/Runnable>
- LangChain runnables overview：<https://reference.langchain.com/python/langchain-core/runnables>
- LangChain BaseChatModel API reference：<https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel>
- LangGraph Graph API：<https://docs.langchain.com/oss/python/langgraph/graph-api>
- LangGraph Persistence：<https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph Checkpointers：<https://docs.langchain.com/oss/python/langgraph/checkpointers>
- LangGraph Memory：<https://docs.langchain.com/oss/python/langgraph/add-memory>
- LangChain Memory concepts：<https://docs.langchain.com/oss/python/concepts/memory>
- LangChain Short-term memory：<https://docs.langchain.com/oss/python/langchain/short-term-memory>
- LangGraph Stores：<https://docs.langchain.com/oss/python/langgraph/stores>
- LangGraph Interrupts：<https://docs.langchain.com/oss/python/langgraph/interrupts>
- LangGraph Time travel：<https://docs.langchain.com/oss/python/langgraph/use-time-travel>
- LangGraph Subgraphs：<https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
- LangGraph Functional API：<https://docs.langchain.com/oss/python/langgraph/functional-api>

## 结语

把 LangChain / LangGraph 的高级特性串起来后，其实它们并不神秘：

```text
Runnable 统一“怎么调用”。
StateGraph 定义“怎么流转”。
Reducer 定义“怎么合并”。
Checkpointer 定义“怎么保存和恢复短期状态”。
Thread 定义“保存到哪条会话线”。
Store 定义“哪些信息可以跨会话长期存在”。
Interrupt 定义“在哪里停下来等人或外部系统”。
Subgraph 定义“如何把复杂流程拆成可复用模块”。
```

真正困难的不是 API 名字，而是边界感：什么应该放消息，什么应该放 state，什么应该进 checkpoint，什么应该进 store，什么必须中断审批，什么又应该保持无状态。

这些边界分清楚后，LangGraph 就不是一团“会调用模型的流程图”，而是一套可以被调试、恢复、审计、扩展的 agent 运行时。到这里才算稍微像个工程系统。嗯，只是稍微，别太得意。
