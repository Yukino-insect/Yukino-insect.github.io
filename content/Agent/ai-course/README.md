+++
date = '2026-08-15T20:43:08+08:00'
draft = false
title = "RAG 与 Agentic AI 工程课程"
+++

这套讲义面向已经具备 Java Web 基础、想把 RAG 系统真正落到工程里的同学。它不是术语表，也不是把项目代码逐行翻译一遍；它要解决的是更麻烦、也更有价值的问题：你为什么要这样设计一条 RAG 链路，出了问题该从哪里查，面试或方案评审时又该怎样把取舍讲清楚。

课程以 Ragent 的实现为参照，把知识库建设、模型基础设施、问答链路、MCP 工具调用和评测体系串成一套完整工程视角。请注意，这里的“完整”不等于堆功能，而是每个环节都有边界、有失败模式、有可观测指标。只是把文档切块塞进向量库，并不能自动得到一个可靠的 AI 应用。嗯，这种幻想就像把书放在枕头边就以为第二天会背了一样，多少有些天真。

## 课程地图

### 1. RAG 基础概念

这一章建立共同语言：RAG 为什么出现、文档如何变成可检索资产、Embedding 和向量库到底负责什么、检索和生成之间怎样分工。

- [什么是 RAG 技术](01-rag-basics/01-what-is-rag.md)
- [大模型、调用方式与 Prompt 工程](01-rag-basics/02-foundation-llm-prompt.md)
- [文档解析、Chunk 策略与元数据](01-rag-basics/03-data-ingestion-chunk-metadata.md)
- [Embedding 与向量数据库](01-rag-basics/04-embedding-vector-db.md)
- [检索召回、生成策略与幻觉抑制](01-rag-basics/05-retrieval-generation-strategy.md)
- [MCP、Function Call 与工具体系](01-rag-basics/06-mcp.md)
- [记忆、重写与意图路由](01-rag-basics/07-dialogue-enhancement.md)
- [SSE 与流式响应](01-rag-basics/08-streaming-protocol.md)
- [RAG 评估与优化总览](01-rag-basics/09-rag-eval-overview.md)

### 2. AI 知识库建设

这一章关注入库链路：上传、对象存储、解析、分块、向量化、调度同步和 Chunk 管理。知识库不是文件夹，它是一套数据治理系统。

- [知识库建设总览](02-knowledge-base/README.md)
- [宏观设计与上传链路](02-knowledge-base/01-architecture-and-upload.md)
- [文件上传、内存占用与分布式限流](02-knowledge-base/02-upload-memory-and-rate-limit.md)
- [文档上传接口与开始分块接口](02-knowledge-base/03-document-ingestion-apis.md)
- [定时同步、调度引擎与故障恢复](02-knowledge-base/04-schedule-sync-and-recovery.md)
- [文档管理与 Chunk 管理](02-knowledge-base/05-document-chunk-management.md)

### 3. 大模型调度引擎实战

这一章把模型调用从“写一个 HTTP Client”提升为基础设施：多供应商、多能力路由、健康状态、熔断、首包探测、Embedding 与 Rerank 客户端抽象。

- [调度引擎总览](03-model-infra/README.md)
- [AI 基础设施层宏观设计](03-model-infra/01-ai-infra-architecture.md)
- [多模型路由、智能选择与三态熔断](03-model-infra/02-routing-and-circuit-breaker.md)
- [Chat 同步调用、SSE 解析与首包探测](03-model-infra/03-chat-streaming-and-first-packet.md)
- [Embedding 客户端与 Rerank 工具链](03-model-infra/04-embedding-rerank-clients.md)

### 4. AI 知识问答篇

这一章拆开一次真实问答：上下文记忆、查询重写、意图树路由、多通道检索、RRF 融合、Rerank、Prompt 拼装、智能体 Prompt 管理、SSE 输出和取消任务。

- [知识问答总览](04-ai-qa/README.md)
- [一次问答的八个阶段与记忆体系](04-ai-qa/01-chat-phases-and-memory.md)
- [查询重写、意图树与路由决策](04-ai-qa/02-rewrite-intent-routing.md)
- [多通道并行检索与结果裁剪](04-ai-qa/03-multi-channel-retrieval.md)
- [知识库答不了时如何转 MCP 与拼 Prompt](04-ai-qa/04-mcp-parameter-and-prompt.md)
- [流式生成、停止任务与并发坑位](04-ai-qa/05-streaming-cancel-and-concurrency.md)
- [智能体管理与运行时 Prompt 治理](04-ai-qa/06-agent-prompt-management.md)

### 5. RAG 评测

这一章回答“系统到底有没有变好”。评测不是上线前补一张表格，而是贯穿数据集、检索指标、生成指标、性能指标和回归分析的闭环。

- [评测总览](05-rag-evaluation/README.md)
- [评估集、初始化与评测系统设计](05-rag-evaluation/01-eval-system-and-dataset.md)
- [指标拆解、性能口径与 RAGAS](05-rag-evaluation/02-metrics-breakdown-and-ragas.md)
- [跑通评测、出报告与常见陷阱](05-rag-evaluation/03-running-report-and-pitfalls.md)

### 6. 面试高频考点

这一章不是背标准答案，而是训练工程表达：为什么不用某个框架，为什么主链路用 Java，为什么从 Milvus 转向 PGVector。能讲出边界和代价，才算真的懂。

- [面试高频考点总览](06-interview/README.md)
- [为什么不使用 Spring AI 或 LangChain4j](06-interview/01-framework-choice.md)
- [为什么不用 Python 实现 RAG 主链路](06-interview/02-why-java-not-python.md)
- [为什么会从 Milvus 转向 PGVector](06-interview/03-milvus-vs-pgvector.md)

## 推荐学习顺序

1. 先读 `01-rag-basics/`，建立术语和主链路。
2. 再读 `02-knowledge-base/`，理解知识如何进入系统。
3. 接着读 `03-model-infra/`，把模型调用从“接口”升级成“基础设施”。
4. 然后读 `04-ai-qa/`，完整跟踪一次问答的执行路径。
5. 最后读 `05-rag-evaluation/` 和 `06-interview/`，学会验证效果并表达工程取舍。

## 学习方法

每节课都建议带着三个问题读：

1. 这一层的输入和输出是什么？
2. 它的失败模式是什么？
3. 如果线上效果不好，我能通过什么指标或日志定位它？

只要能持续回答这三个问题，你就已经从“会调接口”走向“能设计系统”了。
