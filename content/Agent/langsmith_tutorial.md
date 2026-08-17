+++
date = '2026-08-17T00:20:17+08:00'
draft = false
title = "LangSmith 教程：从追踪、调试到评测与生产监控"
+++

当前日期：2026-08-16

LangSmith 是 LangChain 生态里负责 observability、evaluation、prompt engineering 和部分部署工作流的平台。它不是“另一个模型框架”，也不是 LangGraph 的替代品。它更像是 agent 工程里的实验室、监控台和质量管理系统。没有它当然也能写 demo；但如果你想知道 agent 到底为什么失败、哪次改动让质量下降、生产请求里哪个工具调用拖慢了速度，就该把它请出来。它并不神秘，只是很会揭短。

## 目录

1. LangSmith 在 LangChain 中的作用
2. 它解决的问题和满足的需求
3. 核心概念
4. 基础使用步骤：开启 tracing
5. 基础使用步骤：查看 traces
6. 基础使用步骤：做第一次 evaluation
7. 进阶使用步骤：数据集、实验和回归测试
8. 进阶使用步骤：线上评测与监控
9. 进阶使用步骤：prompt、annotation、feedback
10. LangSmith 与 LangGraph、Studio、Server 的关系
11. 常见问题
12. 总结
13. 参考资料

## 1. LangSmith 在 LangChain 中的作用

LangChain 负责写 LLM 应用，LangGraph 负责组织复杂 agent 工作流，LangGraph Server 负责把 agent 作为服务运行。LangSmith 则负责观察、评测和持续改进。

一句话：

```text
LangSmith = LLM/Agent 应用的追踪、调试、评测、监控、反馈与部署协作平台。
```

它在工程链路里的位置：

| 阶段 | 没有 LangSmith 时 | 有 LangSmith 时 |
| --- | --- | --- |
| 原型开发 | print 日志、猜 prompt 问题 | 查看完整 trace、模型输入输出、工具调用 |
| 调试 | 只看到最终报错 | 看到每个 run 的输入、输出、耗时、异常 |
| 评测 | 手动试几个问题 | 用 dataset + evaluator 批量评估 |
| 回归测试 | 改完不知道有没有退化 | 比较多个 experiment |
| 生产监控 | 看接口日志和费用账单 | 看 trace、latency、error、feedback、online eval |
| 质量闭环 | 靠感觉改 prompt | 从失败 trace 进入数据集，再离线验证 |

## 2. 它解决的问题和满足的需求

LLM 应用和传统应用不太一样。传统函数输入相同，输出通常相同；LLM 和 agent 则会受到 prompt、模型版本、检索结果、工具状态、上下文窗口、采样参数的影响。

LangSmith 主要解决这些问题：

### 2.1 可观测性问题

你需要知道：

1. 用户输入是什么。
2. prompt 最终拼成了什么。
3. 模型实际返回了什么。
4. agent 调用了哪些工具。
5. 工具参数是否正确。
6. 检索返回了哪些文档。
7. 哪一步耗时最长。
8. 哪一步失败。

这些信息在 LangSmith 里通常表现为 trace 和 run。

### 2.2 质量评测问题

你需要回答：

1. 新 prompt 是否比旧 prompt 好？
2. 换模型后效果是否下降？
3. RAG 检索是否真的找到了相关文档？
4. agent 是否选对工具？
5. 输出格式是否稳定？
6. 生产中是否出现安全风险或幻觉？

LangSmith 用 datasets、examples、evaluators、experiments 来处理这些问题。

### 2.3 团队协作问题

当项目里有开发、产品、评审、标注人员时，大家需要看到同一批运行结果。LangSmith 支持 trace 分享、annotation queue、人工反馈、项目和数据集管理。

### 2.4 生产闭环问题

真实用户的失败样本最有价值。LangSmith 可以把生产 trace 中的问题沉淀为测试数据，再用离线评测验证修复。否则你就会陷入“修了一个 case，又弄坏三个 case”的循环。虽然这很符合人类工程史，但我们不必主动追求它。

## 3. 核心概念

### 3.1 Run

Run 是 LangSmith 记录的最小工作单元。一次模型调用、一次工具调用、一次检索、一次 parser 调用，都可以是 run。

如果你熟悉 OpenTelemetry，可以把 run 理解成类似 span 的东西。

### 3.2 Trace

Trace 是一次完整请求的运行树。一个用户请求可能触发：

```text
Agent run
  -> Prompt formatting run
  -> LLM call run
  -> Tool call run
  -> LLM call run
  -> Output parser run
```

这些 run 合在一起就是一个 trace。

### 3.3 Thread

Thread 是多轮会话。每一轮用户消息和 agent 响应可以形成一个 trace，多轮 trace 通过同一个 `thread_id` 串起来。

适合：

1. 聊天机器人。
2. 长任务 agent。
3. 有记忆的助手。
4. 多轮调试和回放。

### 3.4 Trajectory

Trajectory 是把一个 thread 中的消息按顺序铺平后展示 agent 行动路径的视图。它更接近“agent 到底走了哪条路”的叙事方式，适合看多轮工具调用过程。

### 3.5 Project

Project 用于组织 traces。你可以按应用、环境、分支、实验目标划分：

```text
research-agent-dev
research-agent-prod
rag-experiment-qwen2.5-7b-instruct
tool-router-ab-test
```

### 3.6 Dataset、Example、Experiment

| 概念 | 含义 |
| --- | --- |
| Dataset | 一组测试样本 |
| Example | 单条输入、参考输出或元数据 |
| Evaluator | 给运行结果打分的函数、人工规则或 LLM-as-judge |
| Experiment | 在某个 dataset 上运行应用并记录评测结果 |

## 4. 基础使用步骤：开启 tracing

### 4.1 注册账号与创建 API Key

1. 打开 LangSmith：`https://smith.langchain.com`
2. 登录或注册。
3. 进入 Settings -> API Keys。
4. 创建并保存 API Key。

### 4.2 安装依赖

如果你使用 LangChain/LangGraph：

```powershell
pip install -U langchain langgraph langsmith langchain-ollama python-dotenv
```

如果只是想手动追踪普通 Python 函数：

```powershell
pip install -U langsmith ollama
```

本教程后面的模型示例默认使用本地 Ollama 模型：

```powershell
ollama pull qwen2.5:7b-instruct
```

### 4.3 配置环境变量

PowerShell 临时设置：

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY="lsv2_..."
$env:LANGSMITH_PROJECT="langsmith-demo"
```

`.env` 文件：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=langsmith-demo
```

如果你的账号区域不是默认区域，还要设置 `LANGSMITH_ENDPOINT`。例如欧盟区域：

```dotenv
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

不要在 endpoint 末尾加斜杠。小事，但很能制造不必要的认证失败。

### 4.4 追踪 LangChain 调用

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(model="qwen2.5:7b-instruct")

response = llm.invoke("用三句话解释 LangSmith 的作用。")
print(response.content)
```

只要 LangSmith 环境变量正确，LangChain 调用会自动发送 trace 到 LangSmith。Ollama 需要本地服务正在运行，默认地址是 `http://localhost:11434`。

### 4.5 手动追踪普通函数

```python
from langsmith import traceable
from ollama import Client

client = Client(host="http://localhost:11434")

@traceable
def draft_answer(question: str) -> str:
    response = client.chat(
        model="qwen2.5:7b-instruct",
        messages=[
            {"role": "system", "content": "你是一个简洁的 Python 教师。"},
            {"role": "user", "content": question},
        ],
    )
    return response["message"]["content"]

print(draft_answer("什么是 LangSmith trace？"))
```

`@traceable` 适合把你的业务函数纳入 trace 树。这样你不只看到模型调用，也能看到自己的逻辑边界。

## 5. 基础使用步骤：查看 traces

运行代码后：

1. 打开 `https://smith.langchain.com`。
2. 进入 Tracing 或 Observability。
3. 找到你的 project，例如 `langsmith-demo`。
4. 点击某条 trace。
5. 展开每个 run。

重点看这些字段：

| 字段 | 用途 |
| --- | --- |
| Inputs | 当前步骤收到的输入 |
| Outputs | 当前步骤返回的输出 |
| Metadata | 环境、版本、用户、thread_id 等上下文 |
| Tags | 便于筛选的标签 |
| Error | 异常信息 |
| Latency | 每一步耗时 |
| Token usage | token 消耗 |

调试 agent 时，建议先回答三个问题：

1. 模型看到的 prompt 是否包含你以为它包含的信息？
2. agent 选择工具的依据是否合理？
3. 失败发生在模型、工具、检索、格式解析，还是业务代码？

大多数时候，看到完整 trace 后，问题会变得不那么玄学。它只是暴露得比较晚而已。

## 6. 基础使用步骤：做第一次 evaluation

### 6.1 评测的基本流程

LangSmith evaluation 的基础流程是：

```text
创建 dataset
  -> 添加 examples
  -> 定义 target 函数
  -> 定义 evaluator
  -> 运行 experiment
  -> 分析结果
```

### 6.2 安装依赖

```powershell
pip install -U langsmith langchain-ollama
```

### 6.3 创建数据集

```python
from langsmith import Client

client = Client()

dataset = client.create_dataset(
    dataset_name="simple-qa-demo",
    description="用于测试问答助手的基础样本",
)

client.create_examples(
    inputs=[
        {"question": "LangSmith 的主要作用是什么？"},
        {"question": "LangGraph 主要解决什么问题？"},
    ],
    outputs=[
        {"answer": "追踪、调试、评测和监控 LLM/agent 应用。"},
        {"answer": "用图组织有状态、多步骤、可循环的 agent 工作流。"},
    ],
    dataset_id=dataset.id,
)
```

### 6.4 定义 target 函数

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(model="qwen2.5:7b-instruct", temperature=0)

def target(inputs: dict) -> dict:
    response = llm.invoke(inputs["question"])
    return {"answer": response.content}
```

### 6.5 定义 evaluator

先写一个简单的规则 evaluator：

```python
def contains_keywords(outputs: dict, reference_outputs: dict) -> bool:
    expected = reference_outputs["answer"]
    actual = outputs["answer"]
    keywords = [word for word in expected.replace("、", " ").split() if len(word) >= 2]
    return any(word in actual for word in keywords)
```

真实项目里不要只用这种简陋规则。这里用于说明流程，别让它承担不该承担的尊严。

### 6.6 运行评测

```python
from langsmith import evaluate

experiment_results = evaluate(
    target,
    data="simple-qa-demo",
    evaluators=[contains_keywords],
    experiment_prefix="qa-baseline",
)
```

运行后到 LangSmith UI 查看 experiment。你可以比较不同模型、prompt、检索策略的结果。

## 7. 进阶使用步骤：数据集、实验和回归测试

### 7.1 设计数据集

不要一开始就追求大数据集。先做小而精的集合。

建议从这些类型开始：

| 类型 | 示例 |
| --- | --- |
| 正常路径 | 用户按预期提问 |
| 边界输入 | 空输入、超长输入、多语言输入 |
| 高风险输入 | 安全、隐私、权限相关问题 |
| 易错工具调用 | 参数格式复杂、依赖外部服务 |
| 真实失败样本 | 从生产 trace 中挑选 |

每个关键组件先准备 5 到 10 条“什么叫好”的样本。官方评测概念也强调：先定义好质量标准，再谈自动评分。

### 7.2 离线评测

离线评测用于上线前：

1. 比较多个 prompt。
2. 比较多个模型。
3. 验证代码改动没有破坏关键能力。
4. 对历史失败样本做 backtesting。

示例实验命名：

```text
rag-v1-baseline
rag-v2-better-retriever
rag-v3-qwen2.5-7b-instruct
agent-tool-router-fix-2026-08-16
```

### 7.3 Experiment 对比

一次 experiment 是某个版本的应用在某个 dataset 上的运行结果。比较 experiment 时要关注：

| 指标 | 说明 |
| --- | --- |
| Correctness | 答案是否正确 |
| Helpfulness | 是否真正帮用户解决问题 |
| Faithfulness | 是否忠于检索材料 |
| Tool correctness | 工具选择与参数是否正确 |
| Format validity | 输出 JSON、Markdown、schema 是否符合要求 |
| Latency | 响应耗时 |
| Cost | token 或调用成本 |

对 agent 项目，单纯评估最终答案常常不够，还要评估 trajectory：工具有没有选对，顺序是否合理，是否不必要地重复调用。

### 7.4 在 CI 中使用评测

可以把小型关键数据集接入 CI：

```powershell
python -m pytest tests/eval_smoke.py
```

思路：

1. 只跑 10 到 30 条关键样本。
2. 使用低温度模型。
3. 设置最大并发和超时。
4. 对通过率设置阈值。
5. 避免在每个 commit 上跑昂贵的大规模评测。

示意断言：

```python
def test_eval_threshold():
    results = run_eval_suite()
    assert results["pass_rate"] >= 0.85
```

CI 评测不必解决所有质量问题，它只负责阻止明显退化。

## 8. 进阶使用步骤：线上评测与监控

### 8.1 Online evaluation 是什么

离线评测跑的是 curated dataset；线上评测跑的是生产 traces、runs 或 threads。

适合线上评测的问题：

1. 输出是否包含敏感信息。
2. 是否违反安全规则。
3. 是否出现格式错误。
4. 是否超过延迟阈值。
5. 是否有异常工具调用。
6. 用户反馈是否持续下降。

### 8.2 采样与成本控制

不要对所有生产请求都用大模型 evaluator。建议：

| 流量类型 | 策略 |
| --- | --- |
| 高价值企业客户 | 较高采样率 |
| 普通请求 | 低采样率 |
| 错误请求 | 全量或高采样 |
| 新版本灰度 | 提高采样 |
| 高成本 evaluator | 只在过滤后运行 |

### 8.3 从线上问题回流到离线数据集

推荐闭环：

```text
线上 trace 发现问题
  -> 加入 dataset
  -> 写或调整 evaluator
  -> 本地修复 prompt/工具/graph
  -> 跑离线 experiment
  -> 通过后部署
  -> 继续线上监控
```

这是 LangSmith 最有价值的地方之一：把“偶然失败”变成“以后必须通过的测试”。

## 9. 进阶使用步骤：prompt、annotation、feedback

### 9.1 Prompt 管理

LangSmith 可以用于 prompt engineering。对于团队项目，prompt 不应散落在代码各处：

```text
prompts/
  planner.md
  researcher.md
  summarizer.md
```

更进一步，可以把 prompt 版本、实验和部署联系起来：

| 动作 | 目的 |
| --- | --- |
| 保存 prompt 版本 | 知道哪次改动引起变化 |
| 对 prompt 做 experiment | 用数据而不是感觉比较 |
| 部署后保留 trace | 关联线上表现 |
| 失败样本回流 | 持续改进 |

### 9.2 Annotation queue

人工评审仍然重要，尤其是：

1. 主观质量。
2. 品牌语气。
3. 复杂任务完成度。
4. 安全和合规。
5. 多轮 agent 行为是否合理。

可以把需要人工判断的 traces 加入 annotation queue，让评审人员打分或标注原因。

### 9.3 用户反馈

生产应用里可以收集：

1. 点赞/点踩。
2. 纠错文本。
3. 评分。
4. “是否解决问题”。
5. 用户选择了哪个候选回答。

反馈要进入 trace 或 metadata，后续才能按用户、版本、功能、环境筛选分析。

## 10. LangSmith 与 LangGraph、Studio、Server 的关系

### 10.1 与 LangGraph

LangGraph 定义 agent 流程，LangSmith 观察流程执行。

例如：

```text
LangGraph 节点：
  plan -> search -> read -> synthesize -> final

LangSmith trace：
  记录每个节点、模型调用、工具调用、输入、输出、耗时、错误
```

### 10.2 与 LangGraph Studio

Studio 是可视化调试图的界面，通常从 LangSmith UI 访问。它可以连接：

1. 本地 `langgraph dev` 启动的 Agent Server。
2. 已部署的 LangSmith Deployment。

Studio 更偏“交互式开发和调试”，LangSmith Observability 更偏“追踪、监控和分析”。它们协作，而不是互相替代。

### 10.3 与 LangGraph Server

Agent Server 暴露 assistants、threads、runs 等 API。LangSmith 可以记录这些 API 调用背后的 trace，并在部署场景里提供监控、评测和 Studio 入口。

### 10.4 与 Deployment

LangSmith Cloud、BYOC、自托管都可以用于 observability/evaluation。LangSmith Deployment 则负责运行 agent 工作负载。平台运行在哪里，和 agent runtime 运行在哪里，是两个相关但不同的问题。

## 11. 常见问题

### 11.1 为什么 UI 里没有 trace？

检查：

1. `LANGSMITH_TRACING=true`。
2. `LANGSMITH_API_KEY` 正确。
3. `LANGSMITH_PROJECT` 是否写到另一个项目名。
4. 区域是否需要 `LANGSMITH_ENDPOINT`。
5. 代码是否真的执行了被追踪的 LangChain/LangGraph/traceable 调用。

### 11.2 Trace 里看不到自定义函数

需要给函数加 `@traceable`，或者使用 LangChain/LangGraph 自带的可追踪对象。

```python
from langsmith import traceable

@traceable
def retrieve(query: str):
    ...
```

### 11.3 评测结果不稳定

可能原因：

1. 模型温度太高。
2. evaluator prompt 不稳定。
3. 样本太少。
4. 评测标准模糊。
5. target 函数依赖实时网络或随机检索。

处理方式：

1. 关键评测使用较低 temperature。
2. 固定模型版本。
3. 拆分 evaluator：格式、事实、工具调用分别评。
4. 给 LLM-as-judge 明确 rubric。
5. 对重要样本多次运行取稳定趋势，而不是迷信单次分数。

### 11.4 是否必须使用 LangSmith？

不是。学习 LangChain 基础调用时，可以不用。但当你进入 agent、RAG、多工具、多轮、多版本比较、生产监控阶段，LangSmith 会明显降低调试和评测成本。

### 11.5 数据会不会离开本地？

如果启用 `LANGSMITH_TRACING=true`，trace 数据会发送到 LangSmith。若本地调试不想发送数据，可以设置：

```dotenv
LANGSMITH_TRACING=false
```

企业场景可考虑 BYOC 或 self-hosted，具体取决于数据合规要求和预算。

## 12. 总结

LangSmith 的核心价值不是“让应用显得更专业”，而是让你能看见、衡量和改进 LLM/agent 的行为。

请记住：

1. Trace 解决“发生了什么”。
2. Dataset 解决“用什么标准测试”。
3. Evaluator 解决“怎么判断好坏”。
4. Experiment 解决“哪个版本更好”。
5. Online evaluation 解决“生产中是否仍然可靠”。
6. Feedback 和 annotation 解决“真实用户和人工评审如何进入质量闭环”。

学 LangSmith 不要从复杂平台功能开始。先打开 tracing，看懂一次完整 trace；再做一个 10 条样本的小 dataset；然后比较两个 prompt。能走完这三步，你就已经从“凭感觉调 prompt”迈进了工程化的大门。虽然这扇门并不华丽，但它通向少一点混乱的地方。

## 13. 参考资料

- LangSmith Observability 官方文档：https://docs.langchain.com/langsmith/observability
- LangSmith observability concepts：https://docs.langchain.com/langsmith/observability-concepts
- LangSmith tracing quickstart：https://docs.langchain.com/langsmith/observability-quickstart
- LangSmith Evaluation 官方文档：https://docs.langchain.com/langsmith/evaluation
- LangSmith evaluation concepts：https://docs.langchain.com/langsmith/evaluation-concepts
- LangSmith platform setup：https://docs.langchain.com/langsmith/platform-setup
