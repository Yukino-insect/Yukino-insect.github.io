+++
date = '2026-08-15T20:46:38+08:00'
draft = false
title = "大模型调度引擎实战"
+++

模型调用层如果只是一堆 HTTP Client，业务代码很快会被供应商差异、超时、限流、降级和日志污染。RAG 系统需要把模型能力沉到基础设施层：Chat、Embedding、Rerank、VLM 各自抽象，路由器决定用谁，健康状态决定能不能用，调用执行器负责失败切换。

这一章关注模型基础设施，而不是某一家模型的参数说明。参数会变，工程约束长期存在。把这件事想清楚，项目才不会每接一个模型就多一片特殊逻辑。

## 学习目标

- 能设计多模型、多供应商的能力抽象。
- 能解释模型路由、熔断和半开恢复。
- 能处理同步 Chat、流式 Chat 和首包探测。
- 能说明 Embedding 与 Rerank 客户端的共性和差异。

## 章节

- [AI 基础设施层宏观设计](01-ai-infra-architecture.md)
- [多模型路由、智能选择与三态熔断](02-routing-and-circuit-breaker.md)
- [Chat 同步调用、SSE 解析与首包探测](03-chat-streaming-and-first-packet.md)
- [Embedding 客户端与 Rerank 工具链](04-embedding-rerank-clients.md)

## 主线

```text
业务请求 -> 能力类型 -> 模型候选 -> 健康过滤 -> 路由选择 -> 调用执行 -> 成功/失败回写健康状态
```

模型基础设施的目标是让业务层只关心“我要 Chat”或“我要 Embedding”，而不关心当前应该走哪个供应商、哪个模型、失败后如何切换。
