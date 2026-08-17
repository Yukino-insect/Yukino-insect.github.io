+++
date = '2026-08-17T17:33:36+08:00'
draft = false
title = "如何写好 Prompt：以 Open Deep Research 为例"
+++

当前日期：2026-08-17

这份教程面向已经会一点 Python、正在学习 LangGraph / Agent 工程的人。它会先解释 `src/open_deep_research/prompts.py` 中每个 prompt 的作用，再抽象出一套可复用的 prompt 写法。

先把结论放在前面：好 prompt 不是“把话说得很华丽”，而是把模型在当前节点中必须遵守的契约写清楚。它要告诉模型：

- 你是谁。
- 你现在处在哪个流程阶段。
- 你要完成什么任务。
- 你能使用什么输入和工具。
- 你必须遵守哪些硬性约束。
- 你的输出格式是什么。
- 什么情况下应该停止、追问、继续或交给下一个节点。

如果这些都没有说清楚，却指望模型稳定地产出工程级结果，那就有些过于相信奇迹了。奇迹偶尔会发生，但生产系统最好不要靠它维持体面。

## 目录

1. 当前项目的 Prompt 总览
2. Deep Research 的工作流
3. `clarify_with_user_instructions`：判断是否需要澄清
4. `transform_messages_into_research_topic_prompt`：把对话改写成研究简报
5. `lead_researcher_prompt`：监督者如何拆分和调度研究
6. `research_system_prompt`：单个研究者如何搜索和反思
7. `compress_research_system_prompt`：压缩研究发现但不丢信息
8. `compress_research_simple_human_message`：切换到清理模式
9. `final_report_generation_prompt`：生成最终深度报告
10. `summarize_webpage_prompt`：网页内容摘要
11. 这些 Prompt 的共同设计模式
12. 写好 Prompt 的工程方法
13. 常用 Prompt 模板
14. Prompt 的坏味道
15. Agent Prompt 的专项建议
16. 测试和迭代 Prompt
17. 检查清单

## 1. 当前项目的 Prompt 总览

`src/open_deep_research/prompts.py` 是 Deep Research Agent 的提示词集中定义文件。它不是普通的“聊天指令集合”，而是 LangGraph 工作流中多个节点的行为说明。

| Prompt 名称 | 所属阶段 | 主要作用 | 典型输出 |
| --- | --- | --- | --- |
| `clarify_with_user_instructions` | 入口澄清 | 判断用户需求是否足够明确 | JSON / `ClarifyWithUser` |
| `transform_messages_into_research_topic_prompt` | 研究简报生成 | 把多轮对话转成具体研究问题 | `ResearchQuestion.research_brief` |
| `lead_researcher_prompt` | 监督者规划 | 让监督者拆分任务并调用子研究员 | tool calls |
| `research_system_prompt` | 子研究员执行 | 指导研究员搜索、反思、停止 | tool calls / 研究消息 |
| `compress_research_system_prompt` | 研究压缩 | 清理搜索发现，保留所有相关信息和引用 | 压缩后的研究报告 |
| `compress_research_simple_human_message` | 压缩触发 | 明确告诉模型进入“清理发现”任务 | 人类消息 |
| `final_report_generation_prompt` | 最终报告 | 根据研究简报和发现生成完整报告 | Markdown 报告 |
| `summarize_webpage_prompt` | 网页摘要 | 把网页原文压缩成结构化摘要 | JSON / `Summary` |

这些 prompt 分工很明确。它们对应的不是“一个大模型做所有事”，而是一个研究系统中不同角色的职责边界：

```text
用户消息
-> 是否需要澄清
-> 生成研究简报
-> 监督者规划和委派
-> 子研究员搜索和反思
-> 清理压缩研究发现
-> 生成最终报告
```

## 2. Deep Research 的工作流

理解 prompt 前，先看它们在 `deep_researcher.py` 中的调用位置。

### 主图

```text
START
-> clarify_with_user
-> write_research_brief
-> research_supervisor
-> final_report_generation
-> END
```

### 监督者子图

```text
supervisor
-> supervisor_tools
-> supervisor
```

监督者循环负责三件事：

- 用 `think_tool` 规划和复盘。
- 用 `ConductResearch` 创建子研究任务。
- 用 `ResearchComplete` 表示研究已完成。

### 研究者子图

```text
researcher
-> researcher_tools
-> researcher
-> compress_research
-> END
```

单个研究者负责搜索、调用 MCP 工具、反思搜索结果，并在完成后把原始研究发现压缩成可交给监督者的报告。

这里要注意一个工程事实：prompt 并不是只给模型看的“说明书”，它还必须和代码中的状态、工具、结构化输出 schema 对齐。否则 prompt 写得再认真，代码不承认，也只是礼貌地自言自语。

## 3. `clarify_with_user_instructions`：判断是否需要澄清

### 位置

文件：`src/open_deep_research/prompts.py`

调用节点：`clarify_with_user`

结构化输出模型：`ClarifyWithUser`

```python
class ClarifyWithUser(BaseModel):
    need_clarification: bool
    question: str
    verification: str
```

### 它解决的问题

用户可能会说：

```text
帮我研究一下新能源汽车。
```

这个请求太宽了。要研究什么？

- 市场规模？
- 技术路线？
- 中国市场？
- 全球市场？
- 竞争格局？
- 政策？
- 投资？
- 论文？
- 某个时间范围？

如果不澄清，后续搜索会变得发散，最终报告也容易泛泛而谈。所以第一个 prompt 的任务是：判断是否需要追问用户。

### 核心输入

它把历史消息包在标签里：

```text
<Messages>
{messages}
</Messages>
```

并注入当前日期：

```text
Today's date is {date}.
```

日期对研究任务很重要，因为“最新”“今年”“最近”这类相对时间必须有参考点。

### 核心指令

这个 prompt 的关键约束包括：

- 判断是否需要澄清。
- 如果历史里已经问过澄清问题，通常不要再问一次。
- 遇到缩写、简称、不明术语，要让用户澄清。
- 问题要简洁，但收集必要信息。
- 不要重复询问用户已经提供的信息。
- 输出必须是合法 JSON，且只包含指定键。

### 输出契约

它要求模型返回：

```json
{
  "need_clarification": true,
  "question": "你的澄清问题",
  "verification": ""
}
```

或：

```json
{
  "need_clarification": false,
  "question": "",
  "verification": "确认将开始研究的简短说明"
}
```

虽然 prompt 写了 JSON，但代码里又用了 `.with_structured_output(ClarifyWithUser)`。这是一种“双保险”：

- prompt 从语言层面要求 JSON。
- Pydantic schema 从工程层面要求字段正确。
- `.with_retry()` 在结构化失败时重试。

### 设计亮点

这个 prompt 写得好的地方有三点：

1. 它不是一上来就追问，而是先判断是否真的需要追问。
2. 它限制“连续追问”的倾向，避免用户体验变成审问。
3. 它把两种情况的输出字段都固定下来，方便后续节点路由。

### 可以学到什么

凡是会影响工作流分支的 prompt，都应该有严格输出格式。比如：

- 是否需要澄清。
- 应该走哪个路由。
- 是否调用工具。
- 是否完成任务。
- 是否需要人工审批。

这种 prompt 不适合让模型自由发挥。自由发挥可以留给写报告，别留给流程控制。

## 4. `transform_messages_into_research_topic_prompt`：把对话改写成研究简报

### 位置

调用节点：`write_research_brief`

结构化输出模型：`ResearchQuestion`

```python
class ResearchQuestion(BaseModel):
    research_brief: str
```

### 它解决的问题

用户消息通常是对话式的，不适合直接交给研究 agent。比如：

```text
我想了解一下这个行业，最好重点看中国市场，别太学术，适合给老板汇报。
```

这句话对人来说还算明白，但对一个要执行搜索和报告生成的系统来说，需要转成更明确的研究简报：

```text
我需要一份面向管理层汇报的中国某行业研究报告，重点包括市场规模、增长驱动因素、主要公司、竞争格局、政策影响、风险和未来 3-5 年趋势。语气应商务、清晰，避免过度学术化。用户未指定具体数据来源，研究者应优先使用官方统计、上市公司公告、行业协会和权威媒体。
```

这个 prompt 的任务就是把上下文转译为“可执行研究问题”。

### 核心规则

它要求模型：

- 最大化具体性。
- 包含所有用户已知偏好。
- 如果必要维度缺失，要明确写成开放条件。
- 不要编造用户没有说的限制。
- 使用第一人称，从用户角度表达。
- 根据领域设置来源优先级。

### 来源策略

这个 prompt 特别有价值的部分是 Sources 指令：

- 产品和旅行研究：优先官方站、品牌站、制造商页面、可信电商用户评价。
- 学术和科学问题：优先原始论文或官方期刊页面。
- 人物研究：优先 LinkedIn 或个人网站。
- 如果查询是特定语言，优先该语言来源。

这不是装饰性的要求。它会直接影响后续搜索质量。

### 设计亮点

它强调“不做无根据假设”。这一点很重要。好的研究 brief 应该区分：

```text
用户已经指定的约束
```

和：

```text
研究时应保持开放的维度
```

例如用户没说预算，就不要写“预算有限”；用户没说地域，就不要写“只看美国”。听起来很基本，但模型很容易为了让任务显得完整而补过头。过度补全就是一种温柔的错误，温柔归温柔，还是错误。

### 可以学到什么

中间层 prompt 的价值在于“把模糊输入改造成稳定任务”。它不负责最终回答，而是负责让后续 agent 不迷路。

适合使用这类 prompt 的场景：

- 把聊天记录转成工单。
- 把用户需求转成 SQL 查询计划。
- 把产品经理描述转成验收标准。
- 把研究想法转成调研 brief。
- 把自然语言转成 API 参数。

## 5. `lead_researcher_prompt`：监督者如何拆分和调度研究

### 位置

调用节点：`supervisor`

绑定工具：

```python
lead_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
```

### 它解决的问题

深度研究任务可能很复杂。一个模型直接搜索，很容易陷入：

- 搜索范围过宽。
- 重复搜索。
- 忘记比较维度。
- 没有判断是否已有足够材料。
- 对多个子问题无法并行。

所以项目引入“监督者”角色。监督者不直接做网页搜索，而是：

- 阅读研究 brief。
- 判断是否需要拆分。
- 调用 `ConductResearch` 委派子任务。
- 用 `think_tool` 做规划和复盘。
- 满意后调用 `ResearchComplete`。

### Prompt 中的角色设定

开头直接定义：

```text
You are a research supervisor.
```

这很关键。监督者不是普通研究员，也不是最终报告作者。它的责任是“管理研究”，不是“写答案”。

### 工具说明

它列出三个工具：

- `ConductResearch`：委派研究任务给专门子 agent。
- `ResearchComplete`：表示研究完成。
- `think_tool`：用于反思和战略规划。

并加了一个强约束：

```text
Use think_tool before calling ConductResearch, and after each ConductResearch.
Do not call think_tool with any other tools in parallel.
```

这相当于给 agent 加了一个“先想再行动，行动后复盘”的节奏。它不是为了展示思维过程，而是为了改善工具调用策略。

### 预算限制

这个 prompt 写得非常工程化，因为它明确限制：

- 默认偏向单个子 agent。
- 除非有明显并行机会，否则不要拆太多。
- 能自信回答就停止。
- 工具调用达到上限要停。
- 每轮最多 `{max_concurrent_research_units}` 个并行 agent。

这类限制对 agent 非常重要。没有预算意识的 agent 会不断追求“更全面”，最后花掉更多 token 和时间，却不一定产出更好答案。嗯，很像某些没有截止日期概念的会议。

### 拆分规则

它给出了非常实用的 scaling rules：

- 简单事实查询、列表、排名：单个子 agent。
- 用户请求中显式出现的比较对象：每个对象一个子 agent。
- 委派任务必须清晰、独立、互不重叠。
- 子 agent 看不到其他 agent 的工作，所以任务说明必须自包含。
- 不要使用缩写或简称。

### 可以学到什么

多 agent prompt 必须写清楚：

- 当前 agent 的层级角色。
- 它是否应该亲自执行任务。
- 它能调用哪些工具。
- 什么时候拆分。
- 拆分的粒度。
- 并发上限。
- 停止条件。
- 子任务说明是否必须自包含。

如果没有这些边界，多 agent 很容易变成“很多模型各忙各的”，看起来热闹，结果松散。

## 6. `research_system_prompt`：单个研究者如何搜索和反思

### 位置

调用节点：`researcher`

绑定工具来自：

```python
tools = await get_all_tools(config)
```

工具可能包括：

- `ResearchComplete`
- `think_tool`
- Tavily 搜索
- OpenAI 原生网页搜索
- Anthropic 原生网页搜索
- MCP 工具

### 它解决的问题

单个研究者拿到监督者分配的一个具体研究主题后，要负责实际查资料。

它的基本循环是：

```text
读任务
-> 搜索
-> 反思搜索结果
-> 缩小搜索
-> 判断是否足够
-> 完成
```

### 搜索策略

Prompt 要求：

- 先宽后窄。
- 每次搜索后暂停评估。
- 缺什么就做更窄的搜索。
- 能自信回答就停止。
- 不要为了完美无限搜索。

这其实是人类研究者的正常做法。先建立地图，再查细节；先看全局，再补缺口。

### 工具预算

它限制：

- 简单问题最多 2-3 次搜索。
- 复杂问题最多 5 次搜索。
- 搜不到也最多 5 次。

还规定遇到以下情况立即停止：

- 已经能全面回答。
- 已有 3 个以上相关例子或来源。
- 最近两次搜索返回相似信息。

这些停止条件能防止 agent 搜索过度。Prompt 工程里，“什么时候停”常常比“怎么做”更重要。

### MCP 注入点

这个 prompt 有一个变量：

```text
{mcp_prompt}
```

它来自配置：

```python
researcher_prompt = research_system_prompt.format(
    mcp_prompt=configurable.mcp_prompt or "",
    date=get_today_str()
)
```

这允许用户或平台在运行时追加 MCP 工具使用说明。例如某个 MCP server 提供数据库、文档库、浏览器自动化工具，就可以在这里告诉研究者何时使用。

### 可以学到什么

工具型 agent prompt 要写清：

- 工具列表。
- 工具使用顺序。
- 每次工具调用后的反思要求。
- 搜索从宽到窄的策略。
- 最大工具调用次数。
- 停止条件。
- 外部工具的附加说明注入点。

## 7. `compress_research_system_prompt`：压缩研究发现但不丢信息

### 位置

调用节点：`compress_research`

### 它解决的问题

子研究者会产生很多消息：

- 搜索结果。
- 网页摘要。
- 工具返回。
- 反思。
- 可能还有重复信息。

这些原始消息直接交给监督者，会占用大量上下文，也会混杂无关内容。所以需要压缩。

但这里的“压缩”不是普通总结。它的关键目标是：

```text
清理格式，去重，保留所有相关信息和来源。
```

### Prompt 的关键矛盾

这个 prompt 同时要求：

- 去掉明显无关和重复内容。
- 所有相关信息都要保留。
- 关键内容可以 verbatim 保留。
- 输出可以很长。
- 必须保留所有来源和引用。

也就是说，它不是让模型写“简短摘要”，而是让模型写“干净版原始发现”。

### 输出格式

它规定：

```text
**List of Queries and Tool Calls Made**
**Fully Comprehensive Findings**
**List of All Relevant Sources (with citations in the report)**
```

并要求最终 Sources 顺序编号、无空号。

### 为什么这么设计

因为后面还有一个最终报告生成模型。压缩阶段如果丢了细节，最终报告就没法恢复。LLM 系统中，早期信息丢失往往是不可逆的。你不能指望最终写作模型凭空找回被压缩掉的证据，除非你真的希望它编。那就不叫研究了，叫即兴表演。

### 可以学到什么

摘要类 prompt 要明确区分：

| 类型 | 目标 | 写法 |
| --- | --- | --- |
| 普通摘要 | 更短、更易读 | 允许概括 |
| 研究压缩 | 减少噪音但保留证据 | 禁止丢相关细节 |
| 执行摘要 | 给决策者快速看 | 强调结论和建议 |
| 证据清单 | 给下游模型使用 | 强调来源、事实、原文片段 |

本项目的压缩 prompt 属于“证据清单 + 去重清理”，不是普通摘要。

## 8. `compress_research_simple_human_message`：切换到清理模式

### 位置

调用节点：`compress_research`

代码中会把它 append 到研究者消息末尾：

```python
researcher_messages.append(HumanMessage(content=compress_research_simple_human_message))
```

### 它解决的问题

系统提示词已经说明了压缩任务，为什么还要追加一条 human message？

因为模型在前面的对话中一直处于“研究者模式”：它搜索、调用工具、反思。现在流程要进入“清理发现模式”。追加一条人类消息，相当于在上下文末尾明确告诉模型：

```text
上面这些都是研究过程。现在请清理这些发现。
```

### 文案特点

它非常短，但很强硬：

```text
DO NOT summarize the information.
I want the raw information returned, just in a cleaner format.
```

它的作用是防止模型把压缩误解成“写一个概览”。这很有必要，因为很多模型见到“clean up findings”会自动开始概括。

### 可以学到什么

当一个节点要在同一段消息历史中切换任务模式时，可以在末尾追加一条短 human message，明确当前操作是什么。尤其适合：

- 从工具调用切到结果整理。
- 从头脑风暴切到执行计划。
- 从草稿切到审校。
- 从检索切到报告写作。

## 9. `final_report_generation_prompt`：生成最终深度报告

### 位置

调用节点：`final_report_generation`

### 它解决的问题

最终报告模型拿到三个上下文：

- `research_brief`：用户真实需求的研究简报。
- `messages`：用户对话上下文。
- `findings`：监督者和子研究者收集到的研究发现。

它的任务是写出最终报告。

### 语言匹配规则

这个 prompt 明确要求：

```text
Make sure the answer is written in the same language as the human messages.
```

并强调：

- 用户消息是英文，就用英文。
- 用户消息是中文，就整篇中文。
- 即使研究 brief 或 findings 是英文，也要翻译成用户语言。

这是面向真实用户体验的重要规则。如果用户用中文提问，最终给出英文报告，大概率不是专业，而是没听懂人话。礼貌一点说，是产品体验欠妥。

### 报告结构规则

它要求：

- 使用清晰 Markdown。
- 标题层级用 `#`、`##`、`###`。
- 包含具体事实和研究洞察。
- 用 `[Title](URL)` 引用相关来源。
- 保持全面、平衡、详尽。
- 最后必须有 Sources。

### 写作行为限制

它明确要求：

- 不要自称报告作者。
- 不要写“我将要……”这种过程说明。
- 直接写报告。
- 默认段落形式，适合时用 bullet points。

这可以避免最终报告像模型自述，而不是专业文档。

### 引用规则

它要求：

- 每个唯一 URL 分配一个 citation number。
- Sources 从 1 开始连续编号。
- 每个来源单独一行。
- 引用非常重要。

注意这里有一个轻微风格张力：正文前面说“用 `[Title](URL)` 格式”，后面 Citation Rules 又要求编号 `[1] Source Title: URL`。这不一定会导致错误，但如果要继续优化 prompt，最好统一引用格式，比如正文全部用 `[1]`，末尾 Sources 列 URL；或者正文全部用 `[Title](URL)`，末尾 Sources 汇总链接。现在的写法能用，但不是最干净。

### 可以学到什么

最终报告 prompt 要控制的是“读者体验”：

- 语言。
- 结构。
- 深度。
- 语气。
- 引用。
- 不要自我旁白。
- 不要遗漏相关信息。

它和前面的工具 prompt 不同：工具 prompt 管行为，报告 prompt 管表达。

## 10. `summarize_webpage_prompt`：网页内容摘要

### 位置

调用函数：`summarize_webpage`

结构化输出模型：`Summary`

```python
class Summary(BaseModel):
    summary: str
    key_excerpts: str
```

### 它解决的问题

Tavily 搜索会返回网页原始内容。网页可能很长，直接塞进研究上下文会浪费 token，也可能引入噪音。所以先做网页摘要。

这个 prompt 要求模型：

- 保留网页主旨。
- 保留关键事实、统计和数据。
- 保留重要引文。
- 对时效内容保留时间顺序。
- 保留列表和步骤。
- 保留关键日期、人物、地点。
- 摘要长度约为原文的 25%-30%。

### 分类处理

它按内容类型给出摘要策略：

- 新闻：关注 who / what / when / where / why / how。
- 科学内容：保留方法、结果、结论。
- 观点文章：保留主要论点和支撑点。
- 产品页：保留功能、规格、卖点。

这类按类型处理的指令很实用，因为不同网页的“重要信息”定义不同。

### 输出格式

它要求 JSON：

```json
{
  "summary": "摘要内容",
  "key_excerpts": "重要摘录"
}
```

代码里同样使用 `.with_structured_output(Summary)`，所以最终会得到 Pydantic 对象。

### 可以学到什么

当 prompt 面向“不同输入类型”时，不要只写笼统的“总结重点”。你应该告诉模型每种类型的重点是什么。否则模型会用同一种摘要套路处理新闻、论文、产品页和法律文本，结果当然会参差。

## 11. 这些 Prompt 的共同设计模式

### 模式一：角色明确

每个 prompt 都会说明模型是谁：

- research supervisor
- research assistant
- report writer
- webpage summarizer

角色不是装饰，而是职责边界。监督者不写最终报告，研究者不做总调度，网页摘要器不评价市场趋势。

### 模式二：上下文用标签包裹

例如：

```text
<Messages>
{messages}
</Messages>
```

```text
<Research Brief>
{research_brief}
</Research Brief>
```

```text
<Findings>
{findings}
</Findings>
```

这种写法有三个好处：

- 模型更容易区分指令和数据。
- 降低用户内容覆盖系统意图的概率。
- 模板可读性更好。

### 模式三：任务、规则、格式分层

这些 prompt 常用类似结构：

```text
<Task>
...
</Task>

<Instructions>
...
</Instructions>

<Hard Limits>
...
</Hard Limits>

<Output Format>
...
</Output Format>
```

这是非常推荐的写法。长 prompt 如果没有结构，很容易变成一锅内容。模型和人一样，读一锅东西也会敷衍，只是它敷衍得比较像真的。

### 模式四：用硬限制控制成本

例如：

- 最多 5 次搜索。
- 简单任务 2-3 次搜索。
- 达到并发上限就拒绝多余研究。
- 搜索结果重复就停止。

Agent prompt 必须有资源意识。没有预算限制的 agent 会自然膨胀。

### 模式五：显式停止条件

好的 agent prompt 不只说“做什么”，还说“什么时候可以结束”。

例如：

```text
Stop when you can answer confidently.
Stop after 5 search calls.
Stop if the last 2 searches returned similar information.
```

这比“尽可能全面”更可控。

### 模式六：结构化输出配合 Pydantic

项目中用于路由或结构化数据的 prompt 都配合了 Pydantic：

- `ClarifyWithUser`
- `ResearchQuestion`
- `Summary`

这是一种成熟做法。需要机器读取的结果，不要只靠自然语言格式约定。

### 模式七：把来源当成一等公民

这个项目几乎所有研究相关 prompt 都强调来源：

- 搜索来源优先级。
- 压缩阶段保留所有来源。
- 最终报告包含 citations。
- Sources 连续编号。

深度研究的核心不是“说得像真的”，而是“能追溯”。这一点不复杂，但很容易被忽略。

## 12. 写好 Prompt 的工程方法

### 第一步：确定这个 Prompt 在流程中的位置

先问：

```text
这个 prompt 是入口判断、信息抽取、工具调用、结果压缩，还是最终写作？
```

不同位置的写法完全不同。

| 位置 | 重点 | 输出 |
| --- | --- | --- |
| 入口澄清 | 判断是否需要追问 | JSON / 路由字段 |
| 信息抽取 | 保留用户约束 | 结构化对象 |
| 工具调用 | 何时用工具、怎么停 | tool calls |
| 搜索研究 | 搜索策略、来源质量 | 研究笔记 |
| 压缩 | 去重但不丢证据 | 结构化发现 |
| 最终写作 | 读者体验和引用 | Markdown |

不要用一个万能 prompt 包揽所有阶段。所谓万能，通常只是所有地方都不够好听的说法。

### 第二步：写清任务目标

差的写法：

```text
请帮我分析用户需求。
```

好的写法：

```text
判断用户是否已经提供足够信息，可以开始研究。如果信息不足，只提出一个最关键的澄清问题；如果信息足够，返回确认消息并简要复述你理解的研究范围。
```

目标要可执行、可判定。

### 第三步：写清输入

把输入包在标签里：

```text
<UserMessages>
{messages}
</UserMessages>
```

如果有多个输入，分别命名：

```text
<ResearchBrief>
{research_brief}
</ResearchBrief>

<Findings>
{findings}
</Findings>
```

不要把不同来源的数据混在一段自然语言里。

### 第四步：写清约束

约束最好分成几类：

- 内容约束：必须包含什么，不能编造什么。
- 行为约束：是否可以追问，是否可以调用工具。
- 资源约束：最多几次搜索，最多几个子任务。
- 风格约束：语言、语气、读者对象。
- 格式约束：JSON、Markdown、表格、字段名。

### 第五步：给输出格式

如果输出会被程序读取，尽量使用结构化输出：

```python
class RouteDecision(BaseModel):
    route: Literal["clarify", "research", "answer"]
    reason: str
```

Prompt 中也同步写清：

```text
Return valid JSON with exactly these keys:
"route": "clarify" | "research" | "answer",
"reason": "<brief reason>"
```

### 第六步：写停止条件

尤其是 agent prompt，必须写：

```text
Stop when:
- you have enough information to answer;
- you have already called the search tool 5 times;
- the last 2 searches returned similar information.
```

停止条件越清楚，系统越稳定。

### 第七步：给示例，但不要喧宾夺主

示例适合：

- 输出格式复杂。
- 用户输入类型多变。
- 需要模型模仿某种结构。

但示例也有风险：模型可能过度模仿示例内容。示例应该展示形式，而不是暗示事实。

### 第八步：把 prompt 和代码契约对齐

Prompt 中提到的工具，代码必须真的绑定。

Prompt 中要求的字段，schema 必须真的定义。

Prompt 中说“最多 5 次”，代码最好也有上限。

Prompt 中说“输出中文”，最终节点必须拿得到用户消息语言。

自然语言约束可以提高概率，代码约束才能给系统兜底。两者缺一边，都会让人心情复杂。

## 13. 常用 Prompt 模板

### 模板一：澄清判断 Prompt

```text
You are an assistant deciding whether a user request is specific enough to proceed.

<Messages>
{messages}
</Messages>

Today's date is {date}.

Task:
Determine whether a clarifying question is required before starting the task.

Rules:
- Ask a clarifying question only if the missing information would materially change the result.
- Do not ask for information already provided.
- If acronyms or ambiguous terms appear, ask for clarification.
- Ask at most one concise question.

Return valid JSON with exactly these keys:
{
  "need_clarification": boolean,
  "question": string,
  "confirmation": string
}

If clarification is needed:
{
  "need_clarification": true,
  "question": "...",
  "confirmation": ""
}

If clarification is not needed:
{
  "need_clarification": false,
  "question": "",
  "confirmation": "..."
}
```

### 模板二：需求改写 Prompt

```text
You will convert the conversation into a concrete task brief.

<Messages>
{messages}
</Messages>

Today's date is {date}.

Guidelines:
- Preserve every explicit user requirement.
- Do not invent constraints the user did not provide.
- If an important dimension is unspecified, mark it as open-ended.
- Write from the user's first-person perspective.
- Include source preferences if relevant.

Return one detailed task brief.
```

### 模板三：工具 Agent Prompt

```text
You are a task-focused agent with access to tools.

<Task>
{task}
</Task>

Available tools:
- search_tool: use for web research.
- database_tool: use for internal records.
- think_tool: use after each search to assess progress.

Instructions:
1. Read the task carefully.
2. Start with broad search if the topic is unfamiliar.
3. Use narrower searches to fill concrete gaps.
4. After each search, call think_tool to evaluate findings.
5. Stop when you can answer confidently.

Hard limits:
- Use at most 5 search calls.
- Stop if the last 2 searches return similar information.
- Do not call tools that are irrelevant to the task.
```

### 模板四：研究压缩 Prompt

```text
You are cleaning research findings for a downstream report writer.

<Task>
Clean the raw findings while preserving all relevant facts, source details, dates, names, numbers, and citations.
</Task>

Rules:
- Do not write an executive summary.
- Remove only obvious duplication and irrelevant text.
- Preserve all evidence that could help answer the research question.
- Keep source URLs attached to the facts they support.
- If multiple sources support the same fact, mention all of them.

Output format:
1. Queries and tools used
2. Comprehensive cleaned findings
3. Sources
```

### 模板五：最终报告 Prompt

```text
Create a comprehensive report answering the research brief.

<ResearchBrief>
{research_brief}
</ResearchBrief>

<Findings>
{findings}
</Findings>

Requirements:
- Write in the same language as the user's messages.
- Use clear Markdown headings.
- Use specific facts from the findings.
- Provide balanced analysis.
- Cite sources consistently.
- Do not refer to yourself.
- Do not describe the writing process.
- End with a Sources section.
```

### 模板六：网页摘要 Prompt

```text
Summarize the following webpage for a downstream research agent.

<WebpageContent>
{webpage_content}
</WebpageContent>

Preserve:
- main topic;
- key facts and statistics;
- dates, names, organizations, locations;
- methodology and conclusions for scientific content;
- feature/specification details for product content;
- important quotes or excerpts.

Return JSON:
{
  "summary": "...",
  "key_excerpts": "..."
}
```

## 14. Prompt 的坏味道

### 坏味道一：目标空泛

```text
请尽可能全面地回答。
```

问题：全面到什么程度？是否需要引用？是否需要比较？是否需要搜索？

改成：

```text
请从市场规模、主要玩家、技术路线、监管政策、风险和未来趋势六个维度回答，并引用权威来源。
```

### 坏味道二：多个任务混在一起

```text
请理解需求、搜索资料、生成结论、写成报告、检查引用。
```

可以拆成：

```text
需求澄清 -> 研究 brief -> 搜索 -> 压缩 -> 报告
```

也就是当前项目的做法。

### 坏味道三：输出格式只用自然语言描述

```text
请返回一个 JSON。
```

不够。

改成：

```text
Return valid JSON with exactly these keys:
"need_clarification": boolean,
"question": string,
"verification": string
```

代码里再配合 Pydantic schema。

### 坏味道四：没有停止条件

```text
不断搜索直到找到足够信息。
```

这句话听起来勤奋，实际很危险。

改成：

```text
Use at most 5 search calls. Stop earlier if you have 3 or more high-quality sources or if the last 2 searches return similar information.
```

### 坏味道五：让模型猜用户没说的东西

```text
根据常识补全用户需求。
```

改成：

```text
If a necessary dimension is not specified, state that it is open-ended instead of inventing a constraint.
```

### 坏味道六：风格要求压过任务要求

```text
用非常优美、震撼、有感染力的语言回答。
```

如果是研究报告，这种要求很容易牺牲准确性。

更稳的写法：

```text
Use clear, professional language. Prefer precise claims over rhetorical flourish.
```

### 坏味道七：引用规则不统一

比如同时要求：

```text
Use [Title](URL)
```

和：

```text
Use numbered citations [1]
```

不是不能混用，但最好统一。否则最终报告可能出现两套引用系统。

## 15. Agent Prompt 的专项建议

### 1. 工具说明要具体

不要只写：

```text
You have access to search.
```

要写：

```text
Use search_tool for current, factual, source-backed information. Start with broad queries, then use narrower queries to fill gaps.
```

### 2. 工具调用要有节奏

当前项目的 `think_tool` 设计值得学习：

```text
Search -> Think -> Search -> Think -> Stop
```

它给 agent 加了一个“评估间隔”，避免连续盲搜。

### 3. 子任务必须自包含

多 agent 委派时，子 agent 通常看不到监督者完整上下文。所以监督者调用 `ConductResearch` 时，研究主题必须包含完整背景。

差的子任务：

```text
Research Tesla.
```

好的子任务：

```text
Research Tesla's current position in the global electric vehicle market, focusing on 2024-2026 delivery trends, pricing strategy, profitability, autonomous driving claims, major competitors, and regulatory risks. Prioritize Tesla investor relations, official filings, government data, and reputable financial publications.
```

### 4. 并发不是越多越好

并发适合：

- 明确比较多个对象。
- 多个独立维度。
- 不同地区或行业可以分开查。

不适合：

- 简单事实查询。
- 强依赖顺序推理的任务。
- 用户需求还没澄清的任务。

### 5. 让 prompt 承认资源有限

像当前项目这样写：

```text
Think like a human researcher with limited time.
```

这句话很有用。它让模型不要以“无限努力”为默认策略。

### 6. 用代码约束兜底

Prompt 中写了最多搜索 5 次，代码中也应该有：

```python
exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
```

只写 prompt 不写代码约束，相当于把刹车画在墙上。看着像那么回事，真要停的时候就知道问题了。

## 16. 测试和迭代 Prompt

### 1. 给每个 prompt 准备测试样例

澄清 prompt 可以测：

- 明确请求。
- 模糊请求。
- 已经追问过的对话。
- 包含缩写的请求。
- 用户拒绝澄清的请求。

研究 brief prompt 可以测：

- 多轮需求。
- 有明确来源偏好的需求。
- 缺少时间范围的需求。
- 多语言需求。

最终报告 prompt 可以测：

- 中文输入必须中文输出。
- 引用是否连续。
- 是否遗漏来源。
- 是否出现自我旁白。

### 2. 记录失败模式

每次 prompt 失败，都不要只改一句“请更认真”。先归类：

- 是输出格式错？
- 是任务理解错？
- 是工具调用太多？
- 是停止太早？
- 是引用丢失？
- 是语言不匹配？
- 是模型没有拿到必要上下文？

问题类型不同，修法也不同。

### 3. 用评测指标约束

Prompt 的好坏最好不要只靠感觉。可以给每类 prompt 设置指标：

| Prompt | 指标 |
| --- | --- |
| 澄清 | 不必要追问率、漏追问率 |
| 研究 brief | 用户约束保留率、无根据假设数量 |
| 搜索 agent | 平均搜索次数、来源质量、重复搜索率 |
| 压缩 | 信息保留率、引用保留率、重复率 |
| 最终报告 | 结构完整性、引用正确率、语言匹配率 |

### 4. 小步修改

不要一次性重写整个 prompt。每次只改一个问题：

- 增加停止条件。
- 调整输出格式。
- 加来源优先级。
- 加一个反例。
- 强化语言要求。

否则效果变了，你也不知道是哪一段起了作用。

## 17. 检查清单

写完一个 prompt 后，可以用这份清单检查。

### 基础检查

- 是否说明了角色？
- 是否说明了任务？
- 是否提供了必要上下文？
- 是否区分了指令和输入数据？
- 是否包含当前日期，尤其是涉及“最新”“最近”“今年”时？
- 是否避免要求模型编造未提供的信息？

### 输出检查

- 输出格式是否明确？
- 字段名是否固定？
- 是否能被程序稳定解析？
- 是否需要配合 Pydantic 或 JSON schema？
- 是否给了正反两种输出情况？

### Agent 检查

- 工具列表是否和代码绑定的工具一致？
- 是否说明每个工具何时使用？
- 是否限制最大工具调用次数？
- 是否说明停止条件？
- 是否说明工具调用后的反思或复盘？
- 多 agent 委派任务是否自包含？

### 研究检查

- 是否指定来源优先级？
- 是否要求保留日期、数字、组织、人名？
- 是否要求保留 URL 和引用？
- 是否区分事实、推断和观点？
- 是否有防止过度总结的规则？

### 报告检查

- 是否指定读者语言？
- 是否指定结构？
- 是否要求引用？
- 是否避免自我旁白？
- 是否要求平衡分析？
- 是否说明 Sources 格式？

## 最后总结

`prompts.py` 展示的是一套相当典型的 Agent Prompt 工程：每个 prompt 只负责一个阶段，靠结构化输出、工具调用、状态流转和引用规则连接成完整系统。

真正值得学习的不是某一句措辞，而是它背后的设计原则：

- 把复杂任务拆成阶段。
- 每个阶段定义清楚角色和职责。
- 需要程序读取的结果使用结构化输出。
- 工具 agent 要有预算、反思和停止条件。
- 研究类任务必须保护来源和证据。
- 最终写作要服务读者，而不是展示模型过程。

Prompt 写得好，不是因为它看起来很聪明，而是因为它让模型在复杂系统里少犯无谓的错。工程里，这已经是很不错的美德了。
