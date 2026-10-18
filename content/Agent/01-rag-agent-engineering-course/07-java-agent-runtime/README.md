+++
date = '2026-10-02T20:00:00+08:00'
draft = false
title = 'Java Agent 框架实战：AgentScope、MCP 与 OpenTelemetry'
+++
本章只讲 `D:/Project/git/me/ragent/agent` 实际引入的框架怎样使用。它不是 Agent 架构介绍，也不会把项目没有使用的 Spring AI、LangChain4j 或 LangGraph4j 塞进来凑名词。

## 版本与边界

`agent/pom.xml` 直接依赖 `agentscope-core`、`agentscope-extensions-model-openai`、`opentelemetry-sdk`、`opentelemetry-exporter-otlp`；根工程锁定 Java 17、AgentScope **2.0.2**、OpenTelemetry **1.62.0**。MCP Java SDK **0.17.0** 由 AgentScope 传递引入、由根 POM 管理，代码通过 AgentScope 的 MCP wrapper 使用它，并非 `agent` POM 显式依赖。

| 组件 | 本模块的真实使用点 | 本章关注的 API |
| --- | --- | --- |
| AgentScope Core | `ReActAgentProvider` | `ReActAgent`、`RuntimeContext`、`AgentTool`、`Toolkit`、`MiddlewareBase`、`AgentStateStore`、`AgentEvent` |
| OpenAI 扩展 | `AgentEngineConfiguration` | `OpenAIChatModel.Builder`、`DeepSeekFormatter` |
| MCP | `AgentMcpClients`、`McpToolProxy` | `McpClientBuilder`、`McpClientWrapper`、`McpTool`、`McpMeta` |
| OTel | `AgentTracingConfiguration` | `OpenTelemetrySdk`、`Tracer`、`Span`、OTLP HTTP exporter |
| Reactor | 工具与聊天服务 | `Mono`、`Flux<AgentEvent>`、`Disposable`、`Schedulers` |

每篇均包含四部分：可以放进测试的最小代码、关键 API 的语义、Ragent 对应代码位置、最容易写错的地方。代码示例以 2.0.2 为准；升级 AgentScope 时必须重新跑文章末尾的契约测试。官方资料可交叉阅读 [AgentScope Java](https://doc.agentscope.io/)、[MCP Java SDK](https://java.sdk.modelcontextprotocol.io/) 与 [OpenTelemetry Java](https://opentelemetry.io/docs/languages/java/)。

## 文章顺序

1. [ReActAgent：创建、调用、事件消费与中断](01-agentscope-reactagent.md)
2. [OpenAIChatModel：兼容端点、流式、tools 与 DeepSeek](02-openai-chat-model.md)
3. [AgentTool 与 Toolkit：Schema、结果状态、同步边界](03-agent-tool-toolkit.md)
4. [MiddlewareBase：`onReasoning`、`onActing` 与顺序](04-middleware-api.md)
5. [AgentStateStore：用 PostgreSQL 恢复会话](05-state-store-api.md)
6. [MCP Client：Streamable HTTP、initialize、tools/list、tools/call](06-mcp-client-api.md)
7. [McpTool：把发现到的 MCP Tool 注册进 AgentScope](07-mcp-tool-proxy.md)
8. [OpenTelemetry：SDK、OTLP、AgentScope tracing 与工具 span](08-otel-api.md)
9. [Reactor/SSE：消费 `Flux<AgentEvent>`、取消和清理](09-reactor-sse-api.md)
10. [Skill、确认与框架契约测试](10-skills-confirm-testing.md)

