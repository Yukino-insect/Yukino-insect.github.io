+++
date = '2026-08-15T20:48:26+08:00'
draft = false
title = "AI 知识问答篇"
+++

知识问答是 RAG 系统的在线主链路。用户看到的是一个输入框和一段流式答案，后端实际经历了记忆读取、问题重写、意图分类、检索范围计算、多通道召回、融合、Rerank、Prompt 拼装、模型生成、引用补齐和消息落库。

这一章按一次问答的执行顺序拆解。请特别关注每一步的输入输出，因为线上排查时，真正有用的问题通常不是“答案为什么错”，而是“从哪一步开始偏”。

## 学习目标

- 能描述一次问答的完整 Pipeline。
- 能解释记忆、重写、意图路由和检索范围的关系。
- 能说明多通道检索、RRF 和 Rerank 的分工。
- 能处理 MCP 转接、Prompt 拼装、流式输出和取消任务。

## 章节

- [一次问答的八个阶段与记忆体系](01-chat-phases-and-memory.md)
- [查询重写、意图树与路由决策](02-rewrite-intent-routing.md)
- [多通道并行检索与结果裁剪](03-multi-channel-retrieval.md)
- [知识库答不了时如何转 MCP 与拼 Prompt](04-mcp-parameter-and-prompt.md)
- [流式生成、停止任务与并发坑位](05-streaming-cancel-and-concurrency.md)
