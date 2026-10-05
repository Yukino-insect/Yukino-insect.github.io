+++
date = '2026-10-02T20:02:00+08:00'
draft = false
title = 'OpenAIChatModel：兼容端点、流式、tools 与 DeepSeek 格式化'
+++
`agentscope-extensions-model-openai` 提供 `OpenAIChatModel`，它把 AgentScope 的 `Msg`、`ToolSchema` 和流式响应翻译为 OpenAI 风格 Chat API。它不是 OpenAI 官方 SDK，也不保证所有“OpenAI compatible”供应商的行为都一样。

## 依赖与 Builder

```xml
<dependency>
  <groupId>io.agentscope</groupId>
  <artifactId>agentscope-extensions-model-openai</artifactId>
  <version>2.0.2</version>
</dependency>
```

Ragent 的模型 Bean 等价于：

```java
OpenAIChatModel.Builder builder = OpenAIChatModel.builder()
    .baseUrl("https://provider.example")
    .endpointPath("/v1/chat/completions")
    .apiKey(apiKey)
    .modelName("deepseek-flash")
    .stream(true)
    .nativeStructuredOutputWithTools(false);
OpenAIChatModel model = builder.build();
```

`baseUrl` 和 `endpointPath` 分开，正是为了让供应商端点配置可替换。项目在构建前校验 `agent.chat.provider`、`agent.chat.model`、`ai.providers.*.url`、`endpoints.chat`；这类校验应该在启动期失败，而不是等用户请求时才给出空指针。

## `nativeStructuredOutputWithTools(false)` 不是装饰

`response_format` 与 tools 都会影响模型输出形态。一些兼容端点可分别支持二者，却无法同时解析，因此项目关闭原生“结构化输出 + 工具”的组合，优先保证工具循环。若最终必须得到 JSON，工具循环结束后再发一轮无工具的结构化请求，或使用 Java DTO 校验并要求修复；不要在没有供应商契约测试前把两个选项同时打开。

## DeepSeek formatter

```java
if (ModelProvider.DEEP_SEEK.matches(providerId)) {
    builder.formatter(new DeepSeekFormatter());
}
```

`DeepSeekFormatter` 处理 `reasoning_content` 回传与不支持的 `strict` 字段。它只应服务于实际需要的协议差异，不能当作通用优化。项目注释已指出：带 tools 的历史思考内容如果被供应商要求完整回传，当前筛选策略需要回退。升级模型、网关或 SDK 时至少测试：普通流、单工具、多轮 tool-result、带 reasoning history 的多轮工具。

## 流式重试规则

在第一个有效 chunk 前重试尚可讨论；一旦 SSE 已向用户输出 delta，重新订阅模型会出现“第一次半段 + 第二次完整段”。若工具已执行，风险会升级为重复副作用。因此 Ragent 用 `maxRetries=1`。任何写工具的恢复都应依赖业务幂等键与结果查询，不能指望模型层 retry。

源码锚点：`config/AgentEngineConfiguration.java`、`config/AgentProperties.java`。本类负责模型协议转换，不负责供应商 SLA、密钥轮换和模型路由；那些应放在上层基础设施。

