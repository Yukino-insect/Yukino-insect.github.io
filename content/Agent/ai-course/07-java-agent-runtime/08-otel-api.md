+++
date = '2026-10-02T20:08:00+08:00'
draft = false
title = 'OpenTelemetry：SDK、OTLP HTTP、AgentScope tracing 与工具 span'
+++
这个模块使用 OpenTelemetry Java SDK 1.62.0，不是只引一个 annotation。`AgentTracingConfiguration` 显式创建 SDK、注册全局实例、配置 OTLP HTTP exporter，再将同一 SDK 的 `Tracer` 交给 AgentScope middleware 和项目工具 tracer。

## 最小 SDK 配置

```java
OtlpHttpSpanExporter exporter = OtlpHttpSpanExporter.builder()
    .setEndpoint(endpoint)
    .addHeader("Authorization", basicCredential)
    .build();
SdkTracerProvider provider = SdkTracerProvider.builder()
    .addSpanProcessor(BatchSpanProcessor.builder(exporter).build())
    .setResource(resource)
    .build();
OpenTelemetrySdk sdk = OpenTelemetrySdk.builder()
    .setTracerProvider(provider).buildAndRegisterGlobal();
Tracer tracer = sdk.getTracer("ragent-agent");
```

OTLP HTTP endpoint 必须与后端协议匹配；通用 OTLP HTTP trace 通常是 `/v1/traces`，本项目接 Langfuse 使用其 `/api/public/otel/v1/traces` 和 Basic key。`buildAndRegisterGlobal()` 只能有一个权威 SDK；项目在 `GlobalOpenTelemetry.isSet()` 时 fail fast，因为 AgentScope 官方 `OtelTracingMiddleware` 从全局实例取 tracer，双 SDK 会导致父子 span 分裂。

## 让 AgentScope 建模型/Agent span

`ReActAgentProvider` 最外层注册 `OtelTracingMiddleware`，这样 trace 覆盖记忆、压缩、模型推理和工具循环。项目还注册 `AgentTraceEnrichmentMiddleware` 补充会话、任务和批信息。不要只给 HTTP Controller 开 span：那只能看到总耗时，无法拆分哪一轮模型或哪一个工具慢。

## 给工具体建 span

工具层以 `AgentToolBodyTracer.trace(tool, param, supplier)` 包裹真实 `callAsync`。这比在接到 ToolUse 事件时开 span 更准确：ToolUse 表示模型的意图，工具体 span 才表示真正进入业务执行。项目将 `toolCallId`、状态、耗时事实同时写入 `AgentToolExecutionFacts`，供 SSE 与持久化使用；不要把 span 当业务事实唯一来源。

## 内容采集规则

Prompt、tool 参数、tool 结果可能包含隐私和密钥。`AgentTraceSerializer` 用 `capture-content`、字段长度和总属性预算控制写入；生产环境应默认白名单/脱敏。OTel 属性一旦被 exporter 批量发出，日志掩码已无济于事。还要用真实后端验证属性映射：项目的 `trace/README.md` 记录了 Langfuse 对 event 与 GenAI 字段的实际摄取结果，不能只凭代码“设置过属性”下结论。

