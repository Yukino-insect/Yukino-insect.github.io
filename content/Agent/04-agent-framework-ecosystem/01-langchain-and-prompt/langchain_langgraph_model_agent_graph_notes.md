+++
date = '2026-08-17T18:34:14+08:00'
draft = false
title = "LangChain / LangGraph 中模型、消息、工具、Agent 与图的创建和调用"
+++

> 整理日期：2026-08-17  
> 主题：普通 chat model、agent、LangGraph graph 的输入输出边界  
> 语境：以下内容以 LangChain / LangGraph Python 当前官方文档的 v1 风格 API 为主。旧版 0.x 资料里会出现 `initialize_agent`、`LLMChain`、`ChatOpenAI` 旧导入路径等写法，概念仍有参考价值，但调用形态可能不同。阅读时请稍微克制一点，不要把旧教程当成圣旨。

## 0. 先给结论

你困惑的核心，其实不是“LangChain 到底有没有内置 `messages`”，而是你把三种不同层级的对象放在了一起比较：

| 对象 | 常见创建方式 | 调用输入 | 返回值 | 是否自动执行 tools |
| --- | --- | --- | --- | --- |
| standalone chat model | `init_chat_model(...)` 或 `ChatOpenAI(...)` | 字符串、消息列表、OpenAI 风格 dict 列表等 | 通常是 `AIMessage` | 否。可通过 `bind_tools` 让模型“提出工具调用”，但不会自动执行 |
| LangChain agent | `create_agent(model=..., tools=...)` | 状态更新，通常是 `{"messages": [...]}` | agent 状态 dict，通常含 `messages`，可含 `structured_response` | 是。agent loop 会让模型决定、调用工具、把结果放回上下文、继续直到结束 |
| LangGraph graph | `StateGraph(State).compile()` | 图的输入状态，通常是一个 dict，字段由你的 `State` schema 决定 | 图的最终状态，或按 stream 模式返回中间事件 | 取决于你图里怎么写。LangGraph 只负责编排，不凭空替你调用工具 |

所以：

- `model.invoke("你好")` 是普通 chat model 的调用。
- `model.invoke([SystemMessage(...), HumanMessage(...)])` 也是普通 chat model 的调用。
- `agent.invoke({"messages": [{"role": "user", "content": "..."}]})` 是 agent 图的调用。
- `graph.invoke({"messages": [...]})` 或 `graph.invoke({"query": "...", "docs": []})` 是你自己定义的 LangGraph 图的调用。

这些都叫 `invoke`，只是 LangChain 的 `Runnable` 统一接口让它们长得像同一家族。像是穿了同一套制服，但职位完全不同。看不出来也正常，文档有时确实不够怜悯初学者。

## 1. 普通模型的输入

### 1.1 `init_chat_model` 创建的是 chat model

在当前 LangChain 中：

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("openai:gpt-4.1-mini")
```

`init_chat_model(...)` 是一个统一的 chat model 初始化入口。它返回的是“聊天模型”接口对象，而不是传统 completion LLM。

因此它的核心输入概念是“消息”。

### 1.2 standalone chat model 的常见输入形态

#### 形态 A：直接传字符串

```python
response = model.invoke("用一句话解释 LangGraph 是什么")
print(response.content)
```

这适合一次性请求。对 chat model 来说，LangChain 会把这个字符串当成用户输入处理，近似理解为：

```python
[HumanMessage(content="用一句话解释 LangGraph 是什么")]
```

#### 形态 B：传消息对象列表

```python
from langchain.messages import SystemMessage, HumanMessage, AIMessage

messages = [
    SystemMessage("你是一个严谨的 Python 教学助手。"),
    HumanMessage("什么是 LangChain 的 message？"),
]

response = model.invoke(messages)
```

这是最标准、最清楚的 chat model 调用方式。多轮对话、系统指令、工具结果、历史上下文都可以通过消息列表表达。

#### 形态 C：传 OpenAI chat completions 风格的 dict 列表

```python
messages = [
    {"role": "system", "content": "你是一个严谨的 Python 教学助手。"},
    {"role": "user", "content": "什么是 LangChain 的 message？"},
]

response = model.invoke(messages)
```

这种写法更接近 OpenAI API 的消息格式。LangChain 会把它转换为自己的标准消息对象。

因此，普通 standalone chat model 的调用输入通常是：

```python
"一个字符串"
```

或：

```python
[
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
]
```

或：

```python
[
    SystemMessage("..."),
    HumanMessage("..."),
]
```

而 `{"messages": [...]}` 这种 dict 包装，一般出现在：

- `create_agent(...)` 创建出来的 agent；
- `LangGraph` 中使用 `MessagesState` 或自定义 state 且 state 里有 `messages` 字段；
- 你自己写的 chain / runnable 设计为接收一个 dict，比如 `{"question": "...", "history": [...]}`。

### 1.4 LangChain 不只支持 chat model

LangChain 的模型生态不止一种模型：

- chat model：输入输出以消息为中心，例如 `ChatOpenAI`、`ChatAnthropic`、`init_chat_model(...)` 返回的对象。
- legacy text completion LLM：输入通常是 prompt string，输出通常是 string。现在许多新应用不再优先使用这种接口。
- embedding model：输入文本或文本列表，输出向量。
- reranker、vector store、retriever 等：严格说不一定是“语言模型”，但也常在 LangChain 的 runnable 体系中一起组合。

因此，“普通模型”最好拆成两类：

- 普通 standalone chat model：可以直接调用，没有 agent loop。
- 普通 LLM / embedding / retriever 等其他组件：输入参数根据组件类型不同而不同。

## 2. LangChain 的消息类型有哪些？如何使用？

LangChain 的 message 是跨模型供应商的标准消息表示。一个 message 通常包含：

- role / type：谁说的，例如 system、user、assistant、tool。
- content：消息内容，可以是字符串，也可以是标准 content blocks，比如文本、图片、文件等。
- metadata：可选元数据，例如 token usage、response metadata、id、tool calls 等。

最常用的消息类型有四种。

### 2.1 `SystemMessage`

系统消息，用来规定模型行为、角色、风格、约束。

```python
from langchain.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage("你是一个严谨的代码审查助手。回答时先列风险，再给建议。"),
    HumanMessage("请审查下面这段 Python 代码。"),
]

response = model.invoke(messages)
```

常见用途：

- 设置角色：代码助手、翻译助手、客服助手。
- 设置行为规则：不要编造、必须给出处、必须返回 JSON。
- 设置回答风格：简洁、正式、教学式。

系统消息通常放在消息列表最前面。不同模型供应商对 system role 的支持略有差异，LangChain 会尽量适配，但具体效果仍取决于底层模型。

### 2.2 `HumanMessage`

用户消息，表示用户输入。

```python
from langchain.messages import HumanMessage

response = model.invoke([
    HumanMessage("LangGraph 的 state 是什么？")
])
```

等价的 dict 写法：

```python
response = model.invoke([
    {"role": "user", "content": "LangGraph 的 state 是什么？"}
])
```

常见用途：

- 当前用户问题。
- 多轮对话中的用户历史发言。
- 给模型看的业务输入，例如文章、代码、报错堆栈。

### 2.3 `AIMessage`

模型回复消息。你调用 chat model 后，通常得到的就是 `AIMessage`。

```python
response = model.invoke("解释一下 AIMessage")

print(type(response))       # AIMessage
print(response.content)     # 模型文本回复
print(response.response_metadata)
print(response.usage_metadata)
```

`AIMessage` 不只可以放文本。它还可能包含：

- `content`：模型自然语言输出。
- `tool_calls`：模型请求调用哪些工具，以及工具参数。
- `usage_metadata`：token 使用量。
- `response_metadata`：供应商返回的元信息。

多轮对话时，你可以把上一次的 `AIMessage` 放回消息历史：

```python
from langchain.messages import HumanMessage, AIMessage

messages = [
    HumanMessage("把 hello 翻译成法语"),
    AIMessage("Bonjour"),
    HumanMessage("再翻译成德语"),
]

response = model.invoke(messages)
```

### 2.4 `ToolMessage`

工具消息，表示某次工具调用的执行结果。它一般不是用户直接写给模型的，而是在 tool calling 流程中，由框架或你的代码把工具结果包装后传回模型。

典型流程是：

1. 你把工具 schema 绑定给模型。
2. 模型返回 `AIMessage`，里面有 `tool_calls`。
3. 你的代码或 agent 执行工具。
4. 工具结果用 `ToolMessage` 放回消息历史。
5. 模型读到工具结果后，生成最终回答。

手动工具调用示意：

```python
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool

@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

model_with_tools = model.bind_tools([add])

messages = [HumanMessage("2 + 3 等于多少？")]

ai_msg = model_with_tools.invoke(messages)
messages.append(ai_msg)

for call in ai_msg.tool_calls:
    if call["name"] == "add":
        result = add.invoke(call["args"])
        messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=call["id"],
            )
        )

final = model_with_tools.invoke(messages)
print(final.content)
```

这里很容易产生误会：`bind_tools` 只是告诉模型“你可以请求调用这些工具”。真正执行工具的，是你的代码、LangChain agent、LangGraph 的 `ToolNode`，或模型供应商的 server-side tool use。别把“模型提出 tool call”和“工具已经被执行”混为一谈。那样会很辛苦，主要是你会辛苦。

### 2.5 其他相关消息形态

除上述四种常见消息外，你还会遇到：

- `AIMessageChunk`：流式输出中的消息片段，可合并成完整 `AIMessage`。
- `HumanMessageChunk`、`SystemMessageChunk` 等：少见，主要和 streaming 相关。
- `RemoveMessage`：在 LangGraph 消息状态中用于删除消息，常见于上下文裁剪、记忆管理。
- `FunctionMessage`：旧版 / 兼容场景中可能见到。现在主流 tool calling 更推荐使用 `ToolMessage`。

实际开发中，你先掌握 `SystemMessage`、`HumanMessage`、`AIMessage`、`ToolMessage` 就足够进入正题。

### 2.6 message-like 输入的几种写法

LangChain 很宽容，支持多种“像消息”的输入：

```python
# 1. 字符串：通常被视为用户消息
model.invoke("你好")

# 2. dict：OpenAI 风格
model.invoke([
    {"role": "system", "content": "你是一个助手。"},
    {"role": "user", "content": "你好。"},
])

# 3. tuple：有些 LangChain prompt / runnable 场景可用
model.invoke([
    ("system", "你是一个助手。"),
    ("human", "你好。"),
])

# 4. BaseMessage 对象
model.invoke([
    SystemMessage("你是一个助手。"),
    HumanMessage("你好。"),
])
```

建议：

- 教学、调试、复杂上下文：优先用 `SystemMessage` / `HumanMessage` 等对象，语义最清楚。
- 和 OpenAI 风格数据结构对接：用 dict。
- 简单一次性问题：直接传字符串即可。

## 3. 普通模型能不能调用 tools？必须 agent 才能调用吗？

### 3.1 严格回答：普通 chat model 可以“绑定工具”，但不会自动执行工具

普通 chat model 可以这样绑定 tools：

```python
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

model_with_tools = model.bind_tools([search])

response = model_with_tools.invoke("请搜索 LangGraph 的用途")
print(response.tool_calls)
```

此时模型可能返回：

```python
[
    {
        "name": "search",
        "args": {"query": "LangGraph 用途"},
        "id": "call_xxx",
        "type": "tool_call",
    }
]
```

这说明模型“决定要调用工具”，但工具还没有真正执行。

你需要自己执行：

```python
for tool_call in response.tool_calls:
    result = search.invoke(tool_call["args"])
```

然后把结果包装成 `ToolMessage` 再发回模型。

### 3.2 agent 的价值：自动跑 tool-calling loop

agent 的核心不是“模型加了 tools”这么简单，而是：

```text
用户消息
  -> 模型判断是否需要工具
  -> 如果需要，生成 tool_calls
  -> agent 执行工具
  -> 工具结果作为 ToolMessage 回到 messages
  -> 模型继续判断 / 回答
  -> 直到不再需要工具，输出最终答案
```

LangChain 官方对 agent 的定义可以概括为：agent 是模型在循环中调用工具，直到任务完成。

创建 agent：

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[get_weather],
    system_prompt="你是一个准确、简洁的助手。",
)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": "旧金山天气怎么样？"}
    ]
})

print(result["messages"][-1].content)
```

### 3.3 agent 的输入参数是什么样的？

最常见的 agent 输入是一个 state update dict：

```python
{
    "messages": [
        {"role": "user", "content": "问题内容"}
    ]
}
```

也可以使用消息对象：

```python
from langchain.messages import HumanMessage

result = agent.invoke({
    "messages": [
        HumanMessage("帮我查一下今天的待办事项")
    ]
})
```

如果需要多轮记忆，通常要配合 checkpointer 和 `thread_id`：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.utils.uuid import uuid7

agent = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[get_weather],
    checkpointer=InMemorySaver(),
)

config = {
    "configurable": {
        "thread_id": str(uuid7())
    }
}

result = agent.invoke(
    {"messages": [{"role": "user", "content": "旧金山天气怎么样？"}]},
    config=config,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "那明天呢？"}]},
    config=config,
)
```

这里 `thread_id` 不是传进 `messages` 的，而是通过 `config` 传给 LangGraph / Runnable 运行时。这个设计看上去绕，但它把“业务输入”和“运行配置”分开了，是有道理的。

### 3.4 agent 的返回值是什么？

`create_agent` 返回的 agent 调用后，通常返回一个状态 dict：

```python
{
    "messages": [
        HumanMessage(...),
        AIMessage(... tool_calls=...),
        ToolMessage(...),
        AIMessage(...)
    ]
}
```

所以你经常会看到：

```python
final_message = result["messages"][-1]
print(final_message.content)
```

如果你在 agent 上设置了结构化输出：

```python
from pydantic import BaseModel

class Answer(BaseModel):
    summary: str
    confidence: float

agent = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[],
    response_format=Answer,
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "总结一下 LangGraph"}]
})

print(result["structured_response"])
```

则返回状态里还会包含类似 `structured_response` 的字段。

### 3.5 三种工具调用方式的比较

| 方式 | 谁决定用工具 | 谁执行工具 | 适合场景 |
| --- | --- | --- | --- |
| `model.bind_tools(...)` + 手动执行 | 模型 | 你自己的代码 | 想完全控制工具执行流程、审计、错误处理 |
| `create_agent(model, tools)` | 模型 + agent loop | LangChain agent | 常规工具调用、多步问答、搜索、API 查询 |
| LangGraph 自定义图 + `ToolNode` / 自写节点 | 你定义图结构，模型可参与决策 | LangGraph 节点 | 复杂流程、分支、循环、人工审批、持久化、可恢复执行 |

普通模型不是不能接 tools，而是缺少“自动执行工具并继续对话”的外层循环。agent 正是提供这个循环。LangGraph 则允许你把这个循环拆开、改造、加条件、加人工审批。层级就这么简单，当然，简单不代表文档会友善地告诉你。

## 4. 自己创建的 LangGraph 图：`invoke` / `ainvoke` 的输入是不是图的状态？

是的，通常可以这么理解：你自己创建的 LangGraph 图，在 `invoke` / `ainvoke` 时传入的是图的输入状态。

但要稍微精确一点：

- 你用 `StateGraph(State)` 定义图时，`State` 是图的状态 schema。
- 默认情况下，图的 input schema 和 output schema 与 state schema 相同。
- 节点接收当前 state。
- 节点返回 partial state update。
- LangGraph 根据 reducer 把 update 合并回 state。
- 图结束时返回最终 state。

### 4.1 最小 LangGraph 示例

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    question: str
    answer: str

def answer_node(state: State):
    return {
        "answer": f"你问的是：{state['question']}"
    }

builder = StateGraph(State)
builder.add_node("answer", answer_node)
builder.add_edge(START, "answer")
builder.add_edge("answer", END)

graph = builder.compile()

result = graph.invoke({
    "question": "LangGraph 的输入是什么？",
    "answer": "",
})

print(result)
```

输出大致是：

```python
{
    "question": "LangGraph 的输入是什么？",
    "answer": "你问的是：LangGraph 的输入是什么？"
}
```

注意：这里没有 `messages`。因为你的 `State` 没有定义 `messages`。

### 4.2 使用 `MessagesState`

因为很多 agent 图都围绕消息列表运转，LangGraph 提供了 `MessagesState`：

```python
from langgraph.graph import MessagesState, StateGraph, START, END

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", END)

graph = builder.compile()

result = graph.invoke({
    "messages": [
        {"role": "user", "content": "你好，解释一下 MessagesState"}
    ]
})

print(result["messages"][-1].content)
```

`MessagesState` 内置了一个 `messages` 字段，并使用 `add_messages` reducer 追加消息，而不是简单覆盖整个列表。

这就是为什么你会经常看到：

```python
graph.invoke({"messages": [...]})
```

不是因为所有图都必须有 `messages`，而是因为“聊天型图”通常把 `messages` 作为状态核心。

### 4.3 自定义状态中加入 messages 和其他字段

实际项目经常这样写：

```python
from langgraph.graph import MessagesState

class ResearchState(MessagesState):
    topic: str
    documents: list[str]
    summary: str
```

调用时：

```python
result = graph.invoke({
    "messages": [
        {"role": "user", "content": "研究一下 LangGraph 的持久化机制"}
    ],
    "topic": "LangGraph persistence",
    "documents": [],
    "summary": "",
})
```

节点里可以读取：

```python
def retrieve_node(state: ResearchState):
    topic = state["topic"]
    messages = state["messages"]
    ...
```

### 4.4 `ainvoke` 与异步节点

如果节点或模型调用是异步的：

```python
async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": [response]}
```

图调用：

```python
result = await graph.ainvoke({
    "messages": [
        {"role": "user", "content": "异步调用有什么用？"}
    ]
})
```

`invoke` 和 `ainvoke` 的输入结构并没有本质差异；差异在运行方式。

### 4.5 `config` 和 `context` 不是 state

LangGraph / LangChain 调用经常有三个概念：

```python
graph.invoke(
    input={...},       # 图输入 / 状态更新
    config={...},      # 运行配置，例如 thread_id、recursion_limit、tags
    context={...},     # 运行时上下文，例如 user_id、llm_provider
)
```

示意：

```python
result = graph.invoke(
    {"messages": [{"role": "user", "content": "继续"}]},
    config={
        "configurable": {"thread_id": "thread-001"},
        "recursion_limit": 100,
    },
    context={
        "user_id": "u_123",
        "llm_provider": "openai",
    },
)
```

区别如下：

| 概念 | 是否进入 state | 典型用途 |
| --- | --- | --- |
| `input` | 是 | 业务数据、消息、任务字段 |
| `config` | 否 | thread_id、tags、recursion_limit、callbacks、tracing |
| `context` | 否 | 运行期依赖，例如当前用户、租户、模型供应商 |

不要把 `thread_id` 放进 `messages`。也不要把所有运行时配置塞进 state。能分清这些，图就已经顺眼很多。

## 5. 把三者放在一起看：调用形态对照

### 5.1 standalone chat model

```python
model = init_chat_model("openai:gpt-4.1-mini")

response = model.invoke("解释 LangChain")
print(response.content)
```

或：

```python
response = model.invoke([
    {"role": "system", "content": "你是一个教学助手。"},
    {"role": "user", "content": "解释 LangChain"},
])
```

输入重点：message-like input。

### 5.2 agent

```python
agent = create_agent(
    model="openai:gpt-4.1-mini",
    tools=[get_weather],
    system_prompt="你是一个有工具可用的助手。",
)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": "北京今天适合出门吗？"}
    ]
})

print(result["messages"][-1].content)
```

输入重点：agent state update，默认核心字段是 `messages`。

### 5.3 LangGraph graph

```python
class State(TypedDict):
    query: str
    answer: str

graph = builder.compile()

result = graph.invoke({
    "query": "LangGraph 是什么？",
    "answer": "",
})
```

输入重点：你定义的图 state。

### 5.4 自定义 LangGraph agent-like graph

```python
class State(MessagesState):
    scratchpad: list[str]

result = graph.invoke({
    "messages": [
        {"role": "user", "content": "帮我查资料并总结"}
    ],
    "scratchpad": [],
})
```

输入重点：仍然是图 state，只是这个 state 里包含 `messages`。

## 6. 常见误区纠正

### 误区 1：`messages` 是所有模型调用必须有的字段

不是。

standalone chat model 可以直接：

```python
model.invoke("你好")
```

也可以：

```python
model.invoke([{"role": "user", "content": "你好"}])
```

但 agent / graph 常常要求：

```python
agent.invoke({"messages": [...]})
```

因为 agent / graph 的输入是 state dict。

### 误区 2：chat model 不能用 tools

不准确。

chat model 可以：

```python
model_with_tools = model.bind_tools([tool])
```

但它只会返回工具调用请求。自动执行工具并继续循环，是 agent 或你自己写的图负责的。

### 误区 3：agent 和 graph 是两种完全无关的东西

不是。

当前 LangChain 的 agents 构建在 LangGraph 之上。`create_agent` 可以理解为 LangChain 帮你预组装好的 agent graph。你自己写 LangGraph，则是自己决定 state、nodes、edges、reducers、checkpoint、interrupt 等细节。

### 误区 4：`messages` 列表每次都会覆盖

在普通 dict 里，列表当然会覆盖。但在 LangGraph 的 `MessagesState` 中，`messages` 使用 `add_messages` reducer，节点返回：

```python
{"messages": [new_ai_message]}
```

通常表示“追加消息”，不是覆盖整个消息历史。

这点非常关键。否则你看到 node 只返回一条消息，会误以为历史丢了。其实是 reducer 在背后做合并。

### 误区 5：图的节点必须调用 LLM

不必。

LangGraph node 可以是任意 Python 函数：

```python
def validate_input(state):
    ...

def call_model(state):
    ...

def save_to_db(state):
    ...
```

LLM 只是节点里可能使用的一个组件。图本身是编排系统，不是模型。

## 7. 官方资料

以下链接是本讲义整理时参考的官方文档。框架更新频繁，遇到 API 细节争议时，优先看这里，而不是随便翻到的旧博客。

- LangChain Models：https://docs.langchain.com/oss/python/langchain/models
- LangChain Messages：https://docs.langchain.com/oss/python/langchain/messages
- LangChain Tools：https://docs.langchain.com/oss/python/langchain/tools
- LangChain Agents：https://docs.langchain.com/oss/python/langchain/agents
- LangChain Overview：https://docs.langchain.com/oss/python/langchain/overview
- LangGraph Graph API：https://docs.langchain.com/oss/python/langgraph/graph-api
- `init_chat_model` API reference：https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model
- `create_agent` API reference：https://reference.langchain.com/python/langchain/agents/factory/create_agent

