+++
date = '2026-10-02T20:07:00+08:00'
draft = false
title = 'McpTool：把 MCP Tool 转为可由 ReActAgent 调用的 AgentScope 工具'
+++
MCP 的 `McpSchema.Tool` 不能直接放入 `Toolkit`。Ragent 的 `McpToolProxy` 继承 AgentScope `McpTool`，在标准 Schema/内容转换之外补了本项目必须拥有的确认、Skill 遮蔽、取消和观测边界。

## 构造 `McpTool`

`McpToolProxy` 构造器将发现结果和业务绑定转换为父类参数：

```java
super(binding.toolId(), binding.description(), binding.inputSchema(),
    binding.remote().definition().outputSchema(),
    binding.remote().client(), null,
    binding.remote().client().getName(), binding.readOnly());
```

因此模型看到的是 MCP tool 的 input JSON Schema；输出由 `McpContentConverter` 转成 `ToolResultBlock`。不要从 description 推断写操作与否：Ragent 从 MCP annotation 的 `readOnlyHint` 和本地意图配置生成 `binding.readOnly/needsConfirm`，缺省按可能有副作用处理。

## 使用 `checkPermissions`

```java
@Override
public Mono<PermissionDecision> checkPermissions(
    Map<String, Object> input, PermissionContextState context) {
  return Mono.just(needsConfirm
      ? PermissionDecision.ask("该操作执行前需要你确认")
      : PermissionDecision.allow("该工具无需执行前确认"));
}
```

`ask` 会让框架产生待确认流程；批准/拒绝要用 AgentScope 状态中原始 `ToolUseBlock` 构造 `ConfirmResult` 续跑。前端确认接口只提交 `approved + messageId`，不提交 tool name/arguments。`readOnlyHint` 和这张确认卡都只是客户端控制；MCP server 仍必须验证用户是否能操作目标资源。

## 实现 `callAsync`

```java
return Mono.defer(() -> client.callTool(getName(), param.getInput(), meta))
    .map(McpContentConverter::convertCallToolResult)
    .map(r -> r.getState() == ToolResultState.RUNNING
        ? r.withState(ToolResultState.SUCCESS) : r)
    .onErrorResume(e -> cancellation(e)
        ? Mono.just(ToolResultBlock.text("用户已停止").withState(INTERRUPTED))
        : Mono.just(ToolResultBlock.error("工具调用失败，请稍后重试")));
```

执行前，Ragent 还检查 `RuntimeContext` 中 `AgentSkillMaskingMiddleware.MASKED_TOOLS_ATTRIBUTE`。被遮蔽时返回 ERROR，要求先调用 `load_skill`；这很重要，因为模型可能基于旧上下文发出一个当前不应可见的调用。执行体再由 `AgentToolBodyTracer.trace` 包裹，使真实远端耗时进入追踪。

最常见错误是把所有 MCP tool 都直接注册，或以工具声明的只读属性代替服务端鉴权。前者造成 schema 膨胀和误调用，后者造成越权。

