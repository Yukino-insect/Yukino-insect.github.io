+++
date = '2026-08-16T23:44:58+08:00'
draft = false
title = "LangGraph Studio 教程：可视化调试 LangGraph Agent"
+++

当前日期：2026-08-16

LangGraph Studio 是用于查看、运行、调试 LangGraph/Agent Server 应用的交互式界面。它不是画流程图哄人开心的装饰品，而是让你真正看到 graph 如何执行、thread 如何变化、assistant 如何配置、memory 如何读写的开发工具。对复杂 agent 来说，这比在终端里盯着一排日志要体面得多。虽然日志也有尊严，只是它不太会照顾人类眼睛。

## 目录

1. LangGraph Studio 在 LangChain 中的作用
2. 它解决的问题和满足的需求
3. Studio、LangSmith、LangGraph Server 的关系
4. 基础使用步骤：连接本地 graph
5. 基础使用步骤：运行、查看和调试
6. 进阶使用步骤：threads、assistants、memory
7. 进阶使用步骤：断点、热重载、远程连接
8. Studio 调试 LangGraph 的典型流程
9. 常见问题
10. 总结
11. 参考资料

## 1. LangGraph Studio 在 LangChain 中的作用

LangGraph Studio 位于 LangGraph 开发与 LangSmith 平台之间。它连接一个正在运行的 Agent Server，然后提供可视化界面，让你与 graph 交互。

它可以连接两类 graph：

| 类型 | 说明 |
| --- | --- |
| 本地 graph | 通过 `langgraph dev` 启动的本地 Agent Server |
| 已部署 graph | 在 LangSmith Deployment 或自托管环境中运行的 Agent Server |

它的核心作用：

1. 运行 graph。
2. 查看 graph 执行过程。
3. 调试输入、输出、状态变化。
4. 管理和查看 threads。
5. 查看 assistants 配置。
6. 调试 memory 和 store。
7. 与 LangSmith traces 联动分析。

## 2. 它解决的问题和满足的需求

复杂 agent 的问题通常不在“某一行代码明显写错”，而在流程里：

1. 某个节点返回的 state 少了字段。
2. reducer 合并状态不符合预期。
3. 条件边跳错。
4. 工具调用参数被模型生成坏了。
5. 中断和恢复逻辑不清楚。
6. 多轮 thread 里历史消息污染了当前请求。
7. memory 写入了不该写的内容。

Studio 解决的就是这些“流程不可见”的问题。

| 问题 | Studio 的价值 |
| --- | --- |
| graph 结构看不清 | 可视化 graph 与运行入口 |
| state 变化不透明 | 查看运行时输入输出 |
| 多轮会话难复现 | 使用 thread 保留上下文 |
| assistant 配置难管理 | 查看和切换 assistant |
| 本地与部署环境割裂 | 同一 UI 可连本地或远程服务 |
| 只靠日志效率低 | 交互式运行和观察 |

## 3. Studio、LangSmith、LangGraph Server 的关系

三者关系可以这样理解：

```text
LangGraph 代码
  -> 通过 LangGraph CLI 启动为 Agent Server
  -> LangGraph Studio 连接这个 Server 进行交互式调试
  -> LangSmith 记录 traces、评测和监控
```

更具体一点：

| 组件 | 角色 |
| --- | --- |
| LangGraph | 定义 agent 的状态、节点、边、工具调用和控制流 |
| LangGraph CLI | 启动本地 Agent Server，如 `langgraph dev` |
| Agent Server | 暴露 assistants、threads、runs、store 等 API |
| Studio | 连接 Agent Server，提供可视化运行和调试 |
| LangSmith | 保存 traces、experiments、feedback、evaluations |

Studio 不是单独运行 graph 的后端。它需要一个 Agent Server。这个 Server 可以在你本机，也可以在部署环境里。

## 4. 基础使用步骤：连接本地 graph

### 4.1 安装 LangGraph CLI

```powershell
pip install -U "langgraph-cli[inmem]"
```

验证：

```powershell
langgraph --help
```

### 4.2 创建示例应用

这里我们简单写一个示例：

```python
# example_langgraph.py

from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END


class ResearchState(TypedDict):
    """
    LangGraph 的 State。
    每个节点都会读取这个状态，并返回一部分状态更新。
    """
    topic: str
    plan: list[str]
    current_step: int
    notes: list[str]
    final_answer: str


def plan_node(state: ResearchState) -> dict:
    """
    第一个节点：根据用户输入生成一个简单计划。
    这里为了示例，不调用 LLM。
    """
    topic = state["topic"]

    return {
        "plan": [
            f"了解 {topic} 的基本概念",
            f"总结 {topic} 的核心用途",
            f"给出一个 {topic} 的实践建议",
        ],
        "current_step": 0,
        "notes": [],
    }


def execute_node(state: ResearchState) -> dict:
    """
    第二个节点：执行当前步骤。
    这里模拟执行，把结果写入 notes。
    """
    step_index = state["current_step"]
    step = state["plan"][step_index]

    new_note = f"步骤 {step_index + 1}: {step}。这是该步骤的模拟结果。"

    return {
        "current_step": step_index + 1,
        "notes": state["notes"] + [new_note],
    }


def route_after_execute(state: ResearchState) -> Literal["execute", "summarize"]:
    """
    条件路由函数：
    如果还有步骤没执行，就继续回到 execute；
    如果计划完成，就进入 summarize。
    """
    if state["current_step"] < len(state["plan"]):
        return "execute"

    return "summarize"


def summarize_node(state: ResearchState) -> dict:
    """
    最后一个节点：汇总所有 notes，生成最终答案。
    """
    notes_text = "\n".join(state["notes"])

    final_answer = f"""
关于「{state["topic"]}」的简要研究结果：

{notes_text}

结论：
{state["topic"]} 适合用在需要“状态流转、条件分支、循环执行、多步骤协作”的场景。
""".strip()

    return {
        "final_answer": final_answer,
    }


"""
构建 LangGraph 工作流。
"""
graph_builder = StateGraph(ResearchState)

graph_builder.add_node("plan", plan_node)
graph_builder.add_node("execute", execute_node)
graph_builder.add_node("summarize", summarize_node)

graph_builder.add_edge(START, "plan")
graph_builder.add_edge("plan", "execute")

graph_builder.add_conditional_edges(
    "execute",
    route_after_execute,
    {
        "execute": "execute",
        "summarize": "summarize",
    },
)

graph_builder.add_edge("summarize", END)

graph = graph_builder.compile()

result = graph.invoke(
    {
        "topic": "LangGraph",
        "plan": [],
        "current_step": 0,
        "notes": [],
        "final_answer": "",
    }
)

print(result["final_answer"])
```

### 4.3 配置 `.env`

在 `.env` 文件中写入类似内容：

```dotenv
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=studio-demo
```

> 我们上面的示例没有用到真正的大模型

如果你只是本地试 Studio，不希望 trace 数据发送到 LangSmith：

```dotenv
LANGSMITH_TRACING=false
```

### 4.4 启动 Agent Server

```powershell
langgraph dev
```

正常启动后通常会看到：

```text
API: http://127.0.0.1:2024
Docs: http://127.0.0.1:2024/docs
Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

浏览器会自动打开 Studio。如果没有自动打开，手动访问：

```text
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

> 如果用的是 window 的话，可能出现以下问题：
> ```shell
> UnicodeDecodeError: 'gbk' codec can't decode byte 0x94 in position 1660: illegal multibyte sequence
> ```
>
> 这是因为 LangGraph 的开发服务器在启动时读取某个 OpenAPI 文件，Python 在 Windows 上默认用 `gbk` 编码打开文本文件，但那个文件实际更像是 `utf-8` 编码，于是读取失败。
>
> 最简单的解决方式是在当前 PowerShell 里启用 Python UTF-8 模式：
>
> ```powershell
> $env:PYTHONUTF8 = "1"
> langgraph dev
> ```

### 4.5 Safari 或 localhost 连接问题

某些浏览器或网络环境可能限制 Studio 访问 localhost。可以使用 tunnel：

```powershell
langgraph dev --tunnel
```

然后在 Studio 中把 tunnel URL 加到允许连接的本地服务里。

## 5. 基础使用步骤：运行、查看和调试

### 5.1 选择 graph

Studio 连接到 Server 后，会读取 `langgraph.json` 中声明的 graph。

示例：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "agent": "./graph_test.py:graph"
  },
  "env": ".env"
}
```

如果你有多个 graph：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "chat": "./agent/chat.py:graph",
    "research": "./agent/research.py:graph"
  },
  "env": ".env"
}
```

Studio 会让你选择要调试哪个 graph。

### 5.2 输入测试数据

聊天类 graph 常见输入：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "请用三句话解释 LangGraph Studio。"
    }
  ]
}
```

我们编写的状态类 graph 输入是：

```json
{
    "topic": "LangGraph",
    "plan": [],
    "current_step": 0,
    "notes": [],
    "final_answer": "",
}
```

输入格式必须匹配你的 state schema。Studio 不会替你猜测业务含义；它只是把不匹配诚实地暴露出来。说起来，这已经比很多人类同事仁慈。

### 5.3 查看节点执行

运行后重点观察：

1. 哪些节点执行了。
2. 节点执行顺序是否符合预期。
3. 每个节点输入是什么。
4. 每个节点输出是什么。
5. state 是否被正确合并。
6. 条件边是否跳到正确节点。
7. 是否出现异常。

### 5.4 查看 messages

聊天 agent 通常把消息保存在 `messages` 字段。你要确认：

1. system prompt 是否存在。
2. user message 是否正确。
3. tool message 是否和 tool call 对应。
4. AI message 是否携带 tool_calls。
5. 最终回答是否落在预期字段。

### 5.5 与 LangSmith trace 对照

Studio 适合看 graph 运行与状态；LangSmith trace 适合看更细的模型、工具、检索、耗时和错误。调试时建议两边一起看：

| 想看什么 | 更适合用 |
| --- | --- |
| graph 节点怎么跳 | Studio |
| state 怎么变化 | Studio |
| 模型看到的 prompt | LangSmith trace |
| 工具调用参数 | LangSmith trace 或 Studio |
| token、latency、error | LangSmith trace |
| 多版本评测 | LangSmith Evaluation |

## 6. 进阶使用步骤：threads、assistants、memory

### 6.1 Thread

Thread 表示一次多轮会话。Agent Server 会把每轮 run 与 thread 关联起来。

适合调试：

1. 多轮上下文是否保留。
2. 上一轮工具结果是否影响下一轮。
3. checkpoint 是否正确恢复。
4. memory 是否被错误写入或读取。

示例问题：

```text
第一轮：请记住我正在学习 LangGraph。
第二轮：我刚才说我在学什么？
```

如果第二轮答不出来，可能是：

1. graph 没有 checkpoint。
2. thread 没有复用。
3. state schema 没保存消息。
4. memory 和 short-term state 混淆。

### 6.2 Assistant

Assistant 可以理解为 graph 的一个配置实例。一个 graph 可以有多个 assistant，每个 assistant 可以有不同配置。

例如同一个 research graph：

| Assistant | 配置 |
| --- | --- |
| `fast-researcher` | 小模型、低搜索深度 |
| `deep-researcher` | 大模型、高搜索深度 |
| `cn-writer` | 中文输出风格 |
| `strict-json` | 强制结构化输出 |

Studio 中切换 assistant，可以帮助你比较不同配置下 graph 的行为。

### 6.3 Memory 与 Store

LangGraph/Agent Server 中经常区分：

| 类型 | 含义 |
| --- | --- |
| Thread state | 某个会话内的短期状态 |
| Checkpoint | 用于恢复 graph 执行的状态快照 |
| Store | 跨 thread 或长期保存的数据 |
| Semantic memory | 可向量检索的长期记忆 |

Studio 可以辅助你检查 memory 是否符合预期。尤其要注意：

1. 不要把敏感信息写入长期记忆。
2. 不要把临时工具结果当成长期事实。
3. 不要让旧记忆覆盖用户当前明确指令。
4. 对 memory 加 metadata，便于筛选和删除。

### 6.4 Store 配置示例

`langgraph.json` 中可以配置 semantic search：

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

也可以配置 TTL：

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

学习时不必急着上这些配置。先把 thread state 和 checkpoint 搞明白，否则长期记忆只会把混乱保存得更持久。

## 7. 进阶使用步骤：断点、热重载、远程连接

### 7.1 热重载

`langgraph dev` 默认适合开发，会监听代码变化并自动重启。

```powershell
langgraph dev
```

如果你要关闭热重载：

```powershell
langgraph dev --no-reload
```

### 7.2 使用调试端口

```powershell
langgraph dev --debug-port 5678
```

等待调试器连接：

```powershell
langgraph dev --debug-port 5678 --wait-for-client
```

调试器适合排查：

1. 节点函数内部逻辑。
2. 工具函数参数。
3. 条件边 routing。
4. 自定义 reducer。
5. 配置读取。

### 7.3 绑定不同 host 和 port

```powershell
langgraph dev --host 127.0.0.1 --port 2025
```

对应 Studio URL：

```text
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2025
```

### 7.4 连接已部署 graph

对于已部署应用，可以在 LangSmith UI 的 Deployments 中进入对应 deployment，然后选择 Studio。Studio 会连接 live deployment，让你创建、读取、更新 threads、assistants 和 memory。

注意：

1. 不要在生产 Studio 中随意写入测试 memory。
2. 不要用真实用户 thread 做破坏性实验。
3. 区分 dev、staging、prod deployment。
4. 给测试 thread 加 metadata 或命名约定。

### 7.5 隔离本地 trace

如果你正在反复调试，不想污染生产项目：

```dotenv
LANGSMITH_PROJECT=studio-local-debug
```

如果不想发送 trace：

```dotenv
LANGSMITH_TRACING=false
```

## 8. Studio 调试 LangGraph 的典型流程

### 8.1 调试节点顺序

症状：

```text
agent 没有调用工具，直接回答了。
```

排查：

1. 在 Studio 看是否进入 tool routing 节点。
2. 看 LLM 节点输出是否包含 tool call。
3. 看条件边函数返回了什么。
4. 看 tool node 是否被注册。
5. 在 LangSmith trace 看模型是否知道有哪些工具。

### 8.2 调试 state 丢失

症状：

```text
前一个节点生成的字段，后一个节点拿不到。
```

排查：

1. 节点是否返回了正确 key。
2. state schema 是否声明了该字段。
3. reducer 是否覆盖了旧值。
4. 是否返回了完整 state 还是 partial update。
5. 并行节点是否写同一个字段导致冲突。

### 8.3 调试循环无法结束

症状：

```text
agent 一直循环调用模型或工具。
```

排查：

1. 条件边是否有 END 分支。
2. 是否设置了最大迭代次数。
3. 工具结果是否能让模型完成任务。
4. 模型是否一直生成同一个 tool call。
5. state 中的完成标记是否被正确更新。

建议给 agent 加保护：

```python
MAX_STEPS = 8

def should_continue(state):
    if state.get("step_count", 0) >= MAX_STEPS:
        return "final"
    if state.get("done"):
        return "final"
    return "continue"
```

### 8.4 调试中断与恢复

对于 human-in-the-loop：

1. 检查 interrupt 是否在预期节点发生。
2. 检查 thread 是否保留。
3. 恢复时输入是否符合 Command 或 resume 格式。
4. 检查 checkpoint 是否存在。

这类问题只看最终输出通常看不出来。Studio 的意义就在这里。

## 9. 常见问题

### 9.1 Studio 打不开

检查：

1. `langgraph dev` 是否还在运行。
2. 地址是否是 `http://127.0.0.1:2024`，不是别的端口。
3. 浏览器是否拦截 localhost 连接。
4. 是否需要 `--tunnel`。
5. 防火墙或代理是否拦截请求。

### 9.2 Studio 连接成功但没有 graph

检查：

1. `langgraph.json` 是否在启动目录。
2. `graphs` 是否为空。
3. graph 路径是否写错。
4. Python 模块导入是否报错。
5. `pip install -e .` 或 `uv sync` 是否已执行。

### 9.3 输入后报 schema 错误

说明输入 JSON 与 state schema 不匹配。

比如 state 需要：

```python
class State(TypedDict):
    question: str
```

你却传：

```json
{
  "messages": []
}
```

那当然不行。模型还没开始犯错，人类已经领先一步了。

### 9.4 本地改代码后 Studio 还是旧行为

检查：

1. 是否用了 `--no-reload`。
2. 服务是否自动重启失败。
3. 是否在编辑另一个目录的代码。
4. 是否有旧 Python 包被安装到环境里。
5. 重启 `langgraph dev` 后再试。

### 9.5 Trace 没有出现在 LangSmith

检查：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=studio-demo
```

如果你设置了：

```dotenv
LANGSMITH_TRACING=false
```

那就不会发送 trace。这个结果完全合理，不必怀疑宇宙。

## 10. 总结

LangGraph Studio 的核心价值是让 LangGraph agent 从“黑盒运行”变成“可交互调试”。

你应该掌握：

1. 用 `langgraph dev` 启动本地 Agent Server。
2. 用 Studio URL 连接本地 graph。
3. 根据 state schema 构造输入。
4. 查看节点执行、state 变化、thread 行为。
5. 将 Studio 观察与 LangSmith trace 结合。
6. 对部署环境使用 Studio 时注意数据隔离和权限。

学 Studio 不要停留在“能打开页面”。真正有用的是用它回答这些问题：为什么这个节点执行了，为什么那个节点没执行，为什么 state 变成这样，为什么下一轮记住了不该记的东西。只要能回答这些，Studio 就不是 UI，而是你的调试武器。

## 11. 参考资料

- LangGraph Studio quickstart：https://docs.langchain.com/langsmith/quick-start-studio
- LangGraph 本地服务教程：https://docs.langchain.com/oss/python/langgraph/local-server
- LangGraph CLI 官方文档：https://docs.langchain.com/langsmith/cli
- LangSmith observability：https://docs.langchain.com/langsmith/observability
- LangSmith observability concepts：https://docs.langchain.com/langsmith/observability-concepts
- LangSmith Agent Server 文档：https://docs.langchain.com/langsmith/agent-server
