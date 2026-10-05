+++
date = '2026-10-02T20:03:00+08:00'
draft = false
title = 'AgentTool 与 Toolkit：Schema、结果状态、异步执行与注册'
+++
AgentScope 只会调 `Toolkit` 中注册的 `AgentTool`。模型看到的是工具名、description 和 JSON Schema；Java 代码收到的是 `ToolCallParam`，必须自行验证并返回 `ToolResultBlock`。项目的 `KnowledgeSearchTool` 是最直接的范本。

## 实现一个只读工具

```java
public final class LookupTool implements AgentTool {
  public String getName() { return "lookup_policy"; }
  public String getDescription() { return "按完整问题查询制度知识库"; }
  public Map<String, Object> getParameters() {
    return Map.of("type", "object", "properties", Map.of(
      "query", Map.of("type", "string", "description", "完整独立问题")),
      "required", List.of("query"), "additionalProperties", false);
  }
  public boolean isReadOnly() { return true; }
  public Mono<ToolResultBlock> callAsync(ToolCallParam param) { /* 下文 */ }
}
```

Schema 是给模型的 API 文档，`additionalProperties: false` 也只能减少模型乱传字段。`callAsync` 仍需检查 `param`、`input`、类型、空白、长度与用户权限。不要因为模型“应该遵守 schema”而跳过服务端校验。

## 正确包装同步业务代码

```java
public Mono<ToolResultBlock> callAsync(ToolCallParam param) {
  return Mono.fromCallable(() -> {
    String query = requireString(param.getInput(), "query");
    String result = facade.search(query);
    return ToolResultBlock.builder().id(callId(param)).name(getName())
        .output(TextBlock.builder().text(result).build())
        .state(ToolResultState.SUCCESS).build();
  }).subscribeOn(Schedulers.boundedElastic())
    .onErrorResume(e -> Mono.just(ToolResultBlock.error("查询暂不可用")));
}
```

JDBC、阻塞 HTTP 或旧 SDK 放在 `boundedElastic`；原生返回 `Mono` 的客户端直接组合即可。Ragent 的 `KnowledgeSearchTool` 对用户取消返回 `ToolResultState.INTERRUPTED`，而不是 ERROR：后者会诱导模型再次尝试。异常结果必须是安全业务文案，SQL、内网地址、密钥和栈信息不能进入 `ToolResultBlock`，因为它会重新进入模型上下文。

## 结果状态和工具箱

`SUCCESS` 表示可供下一轮推理使用的 Observation，`ERROR` 表示本次工具失败，`INTERRUPTED` 表示用户/任务停止，`DENIED` 用于权限拒绝。状态不是展示颜色，而是模型下轮决策的信号。

Ragent 由 `AgentToolCatalog.buildToolkit(catalog)` 统一创建 `Toolkit`，而不让 Controller 临时 new 工具；目录同样用于前端展示名和 Agent 缓存指纹。注册时应拒绝重名工具、稳定排序，并将工具 description 视为受版本控制的模型输入。

写工具要额外做到服务端鉴权、业务幂等、审计与超时后的状态查询。`isReadOnly()` 只是 AgentScope 权限决策的输入，不是数据库权限系统。

