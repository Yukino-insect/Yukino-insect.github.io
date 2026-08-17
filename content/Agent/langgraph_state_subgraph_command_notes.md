+++
date = '2026-08-17T17:52:52+08:00'
draft = false
title = "LangGraph 中 State、子图、节点参数与 Command 的状态流转"
+++

> 写于 2026-08-17。本文结合 `open_deep_research` 项目的 `src/open_deep_research/deep_researcher.py` 与 `src/open_deep_research/state.py`，解释 LangGraph 的状态流转模型。  
> 版本背景：本项目 `uv.lock` 中锁定的 `langgraph` 为 `1.2.9`，`langchain-core` 为 `1.4.8`。

## 1. 先建立一个正确的心智模型

LangGraph 里最容易误解的一句话是：“图有一个 State。”

更准确地说：

1. 每个 `StateGraph(...)` 都有自己的状态 schema。
2. 节点函数接收的是“当前图在当前 superstep 的状态快照”。
3. 节点返回的通常不是下一节点的完整输入，而是对图状态的“更新”。
4. LangGraph 把节点返回的更新按 reducer 合并进当前图状态。
5. 下一个节点看到的是“合并后的图状态”，不是上一个节点返回值本身。

所以，状态并不是像函数调用链那样：

```text
node_a_return -> node_b_argument
```

而更像：

```text
state_snapshot -> node_a -> update
current_state + update --reducer--> next_state_snapshot -> node_b
```

这里的 `reducer` 是核心。它决定某个 key 的更新是覆盖、追加，还是自定义合并。

## 2. 主图和子图的 State 必须完全一样吗？

不必须。

LangGraph 官方文档把子图通信分成两类：

1. 父图和子图共享 state key：可以把编译后的子图直接作为父图节点加入。
2. 父图和子图没有共享 key，或者需要状态转换：应该在普通节点里手动调用子图，并自己做输入输出映射。

这两种方式，本项目都用到了。

## 3. 本项目中的两种子图模式

### 3.1 `supervisor_subgraph`：编译后的子图直接作为主图节点

主图定义在 `deep_researcher.py`：

```python
deep_researcher_builder = StateGraph(
    AgentState,
    input=AgentInputState,
    config_schema=Configuration
)

deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)
```

`supervisor_subgraph` 自己的状态是：

```python
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
```

看上去主图是 `AgentState`，子图是 `SupervisorState`，二者确实不完全一样。问题在于：它们共享了一批 key。

`AgentState` 中有：

```python
supervisor_messages
research_brief
raw_notes
notes
```

`SupervisorState` 中也有：

```python
supervisor_messages
research_brief
notes
raw_notes
```

所以这个子图可以作为主图节点运行。LangGraph 会通过共享的 state channels 让父图和子图通信。子图内部还可以有自己的私有 key，比如：

```python
research_iterations
```

这个 key 属于 `SupervisorState`，主图 `AgentState` 没有它。它主要在 supervisor 子图内部循环时使用，不是主图后续节点需要消费的公共接口。

因此，`supervisor_subgraph` 的状态关系可以理解为：

```text
AgentState
  shared keys:
    supervisor_messages
    research_brief
    raw_notes
    notes

SupervisorState
  shared keys:
    supervisor_messages
    research_brief
    raw_notes
    notes

  private key:
    research_iterations
```

也就是说，父图和子图不是“必须同一个类”，而是“必须有可通信的 state channel”。如果直接把子图作为节点加入，最自然的方式就是让它们共享某些 key。

### 3.2 `researcher_subgraph`：在普通节点里手动调用子图

`researcher_subgraph` 没有被直接加到 `supervisor_builder.add_node(...)`。它是在 `supervisor_tools` 这个普通节点函数内部被调用的：

```python
researcher_subgraph.ainvoke({
    "researcher_messages": [
        HumanMessage(content=tool_call["args"]["research_topic"])
    ],
    "research_topic": tool_call["args"]["research_topic"]
}, config)
```

这就是官方文档说的第二种模式：父图和子图 state schema 不适合直接共享，就在节点函数里自己做转换。

这里的转换关系是：

```text
SupervisorState
  从 supervisor 的 tool call 中拿 research_topic
      |
      v
ResearcherState input
  researcher_messages
  research_topic
      |
      v
researcher_subgraph 执行
      |
      v
ResearcherOutputState
  compressed_research
  raw_notes
      |
      v
supervisor_tools 把结果转换成 ToolMessage 和 raw_notes 更新
```

特别注意 `researcher_builder` 的定义：

```python
researcher_builder = StateGraph(
    ResearcherState,
    output=ResearcherOutputState,
    config_schema=Configuration
)
```

这里的内部状态是 `ResearcherState`，但对子图调用者暴露的输出被过滤为 `ResearcherOutputState`。所以 `supervisor_tools` 拿到的 `observation` 主要就是：

```python
compressed_research
raw_notes
```

这就是为什么不同状态 schema 可以工作：这里不是“自动共享状态”，而是“手动把父图状态转换成子图输入，再把子图输出转换回父图更新”。

## 4. 节点函数的参数应该是什么？

最普通的节点函数可以只有一个参数：

```python
def node(state: State):
    return {"some_key": "some_value"}
```

异步节点也可以：

```python
async def node(state: State):
    return {"some_key": "some_value"}
```

本项目里经常写成：

```python
async def researcher(state: ResearcherState, config: RunnableConfig):
    ...
```

这里的 `config` 不是图状态的一部分。它是 LangChain / LangGraph Runnable 体系的运行时配置，通常由调用图时传入：

```python
graph.invoke(
    input_state,
    config={
        "configurable": {
            "research_model": "openai:gpt-4.1",
            "max_react_tool_calls": 10,
        },
        "tags": ["experiment"],
        "metadata": {"case": "demo"},
        "recursion_limit": 50,
    },
)
```

`RunnableConfig` 常见字段包括：

```python
{
    "tags": list[str],
    "metadata": dict,
    "callbacks": ...,
    "run_name": str,
    "max_concurrency": int,
    "recursion_limit": int,
    "configurable": dict,
    "run_id": UUID,
}
```

在本项目中，`Configuration.from_runnable_config(config)` 会读取：

```python
config.get("configurable", {})
```

然后生成项目自己的 `Configuration` 对象。比如这些配置：

```python
allow_clarification
max_concurrent_research_units
max_researcher_iterations
max_react_tool_calls
research_model
compression_model
final_report_model
mcp_config
```

都不是 State，而是运行时配置。它们影响节点如何执行，却不作为图状态流转。

可以这样区分：

```text
State:
  业务数据，会在图中被节点读写和持久化，例如 messages、research_brief、notes。

RunnableConfig:
  运行参数，控制这次执行怎么跑，例如模型、API key、tags、recursion_limit、callbacks。
```

这一区分很重要。把 config 当成 state，会把图的业务数据和运行环境搅在一起。那样虽然也许能跑，但设计上并不清爽。

## 5. 节点返回值应该是什么？

节点返回值最常见有三类。

### 5.1 返回 dict：最常见

```python
def node(state: State):
    return {"foo": "bar"}
```

这个 dict 是“状态更新”，不是“完整的新 State”。当然，你可以返回很多 key，看起来像完整 State，但 LangGraph 仍然会把它当成 update，对每个 key 分别应用 reducer。

### 5.2 返回完整 State：技术上常常能跑，但要小心

例如：

```python
def node(state: State):
    new_state = dict(state)
    new_state["foo"] = "bar"
    return new_state
```

这看起来像“返回新的 State”。但在 LangGraph 语义里，它仍然是“返回一组更新”。如果某些字段有追加型 reducer，比如 `operator.add`，你返回完整列表就可能导致重复追加。

所以，更推荐只返回本节点真正修改的 key：

```python
return {"foo": "bar"}
```

这也是 LangGraph 文档反复强调的 partial update 思路。

### 5.3 返回 Command：同时更新状态和决定下一跳

本项目大量使用：

```python
return Command(
    goto="researcher_tools",
    update={
        "researcher_messages": [response],
        "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
    }
)
```

`Command` 可以把两件事合在一起：

```text
update: 本节点对状态的更新
goto: 下一步去哪个节点
```

它适合“节点执行完后，下一步由节点内部逻辑决定”的场景。

## 6. 当前节点返回值会直接成为下一个节点的内容吗？

不会。

这句话请记住：

> 节点返回值不是下一个节点的参数；节点返回值是对图状态的更新。

流程是：

```text
当前 state
  |
  v
node(state)
  |
  v
返回 update 或 Command(update=...)
  |
  v
LangGraph 按 key 应用 reducer
  |
  v
形成新的 state
  |
  v
下一个节点接收新的 state
```

以本项目为例，`write_research_brief` 返回：

```python
Command(
    goto="research_supervisor",
    update={
        "research_brief": response.research_brief,
        "supervisor_messages": {
            "type": "override",
            "value": [
                SystemMessage(content=supervisor_system_prompt),
                HumanMessage(content=response.research_brief)
            ]
        }
    }
)
```

下一节点 `research_supervisor` 不是收到这个 `Command` 对象作为参数。它收到的是已经更新后的状态，其中：

```python
state["research_brief"]
state["supervisor_messages"]
```

已经被写入或合并。

## 7. reducer 决定 update 如何合并

`state.py` 里有一个自定义 reducer：

```python
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
```

这个 reducer 的语义是：

1. 如果更新值是 `{"type": "override", "value": ...}`，就直接覆盖。
2. 否则就用 `operator.add` 追加或相加。

所以：

```python
supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
raw_notes: Annotated[list[str], override_reducer]
notes: Annotated[list[str], override_reducer]
```

这些字段默认会追加，但也允许通过特殊结构强制覆盖。

例如 `write_research_brief` 中：

```python
"supervisor_messages": {
    "type": "override",
    "value": [...]
}
```

这里不是追加消息，而是重置 supervisor 的消息上下文。

再看 `ResearcherState`：

```python
researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
```

这个字段每次返回：

```python
{"researcher_messages": [response]}
```

都会被追加到已有列表后面。

没有显式 reducer 的字段，比如：

```python
research_brief: Optional[str]
final_report: str
research_iterations: int
tool_call_iterations: int
```

默认策略是覆盖：新值替换旧值。

## 8. Command 指定了 goto，还需要定义边吗？

分情况。

如果一个节点返回：

```python
return Command(goto="node_b", update={...})
```

那么从这个节点到 `node_b` 的运行时跳转不需要再写：

```python
builder.add_edge("node_a", "node_b")
```

官方文档也把 `Command(goto=...)` 描述为“可以替代边或条件边”的控制方式。

但你仍然需要：

1. 把目标节点通过 `add_node(...)` 加进图里。
2. 保证当前节点本身能被执行到，例如从 `START` 或其他节点有路径进入。
3. 最好在返回类型上写 `Command[Literal["node_b", "node_c"]]`，这样图可视化和静态分析更清楚。

### 8.1 不要随便同时使用 Command goto 和静态边

在本项目锁定的 `langgraph==1.2.9` 上，如果某节点既返回 `Command(goto="b")`，又存在静态边：

```python
builder.add_edge("a", "c")
```

那么实际可能会同时调度 `b` 和 `c`。这就变成 fan-out，而不是二选一。

如果 `b` 和 `c` 在同一个 superstep 写同一个没有 reducer 的 key，还会触发类似：

```text
InvalidUpdateError: Can receive only one value per step.
```

所以实践建议是：

```text
用 Command 做动态路由时，就让 Command 管这段路由；
用静态 edge 做固定拓扑时，就让 edge 管这段路由。
```

不要把两者混在同一个节点出口上，除非你明确想要并行分支，并且状态 reducer 已经处理好并发更新。

## 9. 本项目为什么有些节点没有普通边也能流转？

例如 supervisor 子图：

```python
supervisor_builder.add_edge(START, "supervisor")
```

只定义了入口边，没有写：

```python
supervisor_builder.add_edge("supervisor", "supervisor_tools")
supervisor_builder.add_edge("supervisor_tools", "supervisor")
```

这是因为节点自己返回了 `Command`：

```python
return Command(
    goto="supervisor_tools",
    update={...}
)
```

以及：

```python
return Command(
    goto="supervisor",
    update=update_payload
)
```

或者：

```python
return Command(
    goto=END,
    update={...}
)
```

也就是说，supervisor 子图的循环控制不是写在 `add_edge` 里，而是写在节点返回的 `Command` 里。

研究者子图也是类似：

```python
researcher -> researcher_tools -> researcher
```

以及：

```python
researcher_tools -> compress_research
```

这些动态跳转都靠 `Command(goto=...)` 完成。唯一写死的边是：

```python
researcher_builder.add_edge(START, "researcher")
researcher_builder.add_edge("compress_research", END)
```

入口和最终出口是静态的，中间循环是动态的。结构上并不矛盾。

## 10. 图中的状态到底始终是同一个，还是改变过？

从业务语义上说：它是“同一个图运行中的状态”，不断被更新。

从实现心智模型上说：不要把它想成“同一个 Python dict 对象被原地修改”。更稳妥的理解是：

```text
每个 superstep 都有一个状态快照；
节点基于快照计算 update；
LangGraph 合并 update 后得到下一份状态快照。
```

所以：

```text
schema 稳定，values 变化。
```

对于主图：

```text
AgentState schema 稳定；
messages、research_brief、notes、final_report 等值不断变化。
```

对于 supervisor 子图：

```text
SupervisorState schema 稳定；
supervisor_messages、research_iterations、raw_notes 等值不断变化。
```

对于 researcher 子图：

```text
ResearcherState schema 稳定；
researcher_messages、tool_call_iterations、compressed_research 等值不断变化。
```

当子图作为父图节点运行时，子图有自己的内部状态流转。它完成后，能与父图通信的 shared/output keys 会作为这个“子图节点”的输出更新，继续合并回父图状态。

## 11. 把本项目的状态流转串起来

主图：

```text
START
  |
  v
clarify_with_user
  |
  | Command(goto="write_research_brief") 或 Command(goto=END)
  v
write_research_brief
  |
  | update research_brief
  | override supervisor_messages
  | goto research_supervisor
  v
research_supervisor  # supervisor_subgraph
  |
  | 子图内部循环：
  | supervisor -> supervisor_tools -> supervisor ...
  |
  | 子图结束后输出 notes、raw_notes、research_brief 等共享字段
  v
final_report_generation
  |
  | update final_report
  | append messages
  | override notes = []
  v
END
```

supervisor 子图中，当模型调用 `ConductResearch` 工具时：

```text
supervisor_tools
  |
  | 从 tool_call 里取 research_topic
  v
researcher_subgraph.ainvoke(...)
  |
  | researcher -> researcher_tools -> researcher ...
  | researcher_tools -> compress_research -> END
  v
返回 compressed_research/raw_notes
  |
  | compressed_research 变成 ToolMessage
  | raw_notes 合并到 supervisor raw_notes
  v
supervisor
```

这个设计的好处是：

1. 主图只关心用户输入、研究简报、研究笔记、最终报告。
2. supervisor 子图关心任务拆分和研究调度。
3. researcher 子图关心单个研究任务的搜索、工具调用和压缩。
4. 三层图的状态 schema 不必完全相同，只要边界通信清楚。

## 12. 最简规则总结

### 12.1 State

State 是图的业务状态 schema。节点读它，但通常只返回局部更新。

```python
class State(TypedDict):
    messages: list
    answer: str
```

### 12.2 Reducer

Reducer 决定某个 key 如何接收更新。

```python
class State(TypedDict):
    logs: Annotated[list[str], operator.add]
```

没有 reducer 时，默认覆盖。

### 12.3 Node

普通节点：

```python
def node(state: State):
    return {"answer": "ok"}
```

带运行时配置的节点：

```python
def node(state: State, config: RunnableConfig):
    configurable = config.get("configurable", {})
    return {"answer": configurable.get("answer", "ok")}
```

异步节点：

```python
async def node(state: State, config: RunnableConfig):
    return {"answer": "ok"}
```

### 12.4 Command

Command 同时做状态更新和路由。

```python
return Command(
    update={"foo": "bar"},
    goto="next_node"
)
```

如果 `goto` 已经指定了下一节点，这段跳转通常不需要再定义静态边。

### 12.5 Subgraph

共享 state key 时，可以直接作为节点：

```python
parent_builder.add_node("child", compiled_subgraph)
```

不同 state schema 且需要转换时，在普通节点里调用：

```python
def call_child(state: ParentState):
    child_output = child_graph.invoke({"child_key": state["parent_key"]})
    return {"parent_key": child_output["child_key"]}
```

## 参考资料

1. LangGraph 官方文档：Subgraphs  
   https://docs.langchain.com/oss/python/langgraph/use-subgraphs

2. LangGraph 官方文档：Graph API / State / Reducers  
   https://docs.langchain.com/oss/python/langgraph/graph-api

3. LangGraph 官方文档：Use the graph API / Command  
   https://docs.langchain.com/oss/python/langgraph/use-graph-api

4. LangChain Core 官方 API：RunnableConfig  
   https://reference.langchain.com/python/langchain-core/runnables/config/RunnableConfig

