+++
date = '2026-10-02T20:10:00+08:00'
draft = false
title = 'Skill、确认与框架契约测试：动态工具面的正确用法'
+++
本模块的 `SkillLoadTool` 与 `AgentSkillMaskingMiddleware` 是 AgentScope 扩展 API 的实际用法：先只暴露 `load_skill`，模型命中业务场景后加载手册，再让对应工具进入本轮 `ReasoningInput.tools()`。它解决的是工具 schema 过多和需要 SOP 的写操作，不是权限系统的替代品。

## `load_skill` 的关键实现

`SkillLoadTool` 实现 `AgentTool`，参数只有 `skill_code`，成功结果在 metadata 写入：

```java
new ToolResultBlock(toolCallId, "load_skill", output,
    Map.of("ragent_loaded_skill", skill.skillCode()),
    ToolResultState.SUCCESS);
```

遮蔽 middleware 扫描上下文中成功且未被压缩逐出的 ToolResultBlock，计算未激活技能保护的工具，并从 `ReasoningInput.tools()` 过滤它们。一个工具被多份手册保护时，任意一份仍在上下文即可解锁。手册结果被上下文裁剪后工具会再次隐藏，这就是为什么 metadata 和裁剪标记必须保留。

## `PermissionDecision` 与确认续跑

MCP proxy 通过 `checkPermissions` 返回 `PermissionDecision.ask(...)`。当框架要求确认时，Ragent 保存确认卡；用户的确认请求只传 `conversationId`、`messageId` 和 `approved`。服务端重新读取 `agent.getAgentState(...).getContext()`，提取最后一条 assistant message 里 `ToolCallState.ASKING` 的 `ToolUseBlock`，再创建 `ConfirmResult`。这才是正确 API 用法。

```java
Msg resume = UserMessage.builder()
    .metadata(Map.of(Msg.METADATA_CONFIRM_RESULTS, confirmResults))
    .build();
agent.streamEvents(resume, runtimeContext);
```

不要让浏览器传 `toolName` 或 `arguments`；那会使用户看到的确认卡与实际执行参数脱钩。用户拒绝后，`AgentConfirmDenialMiddleware` 将框架默认文案改写为“用户取消，未执行”，使下一轮模型不会误判为权限故障。

## 必做的框架契约测试

- `AgentTool`：空参数、未知字段、业务异常、取消分别得到预期 `ToolResultState`，且错误文本不泄密。
- `MiddlewareBase`：未加载 Skill 时工具不在 `ReasoningInput.tools()`；手册被裁剪后工具再次消失；执行前 proxy 仍会二次拒绝。
- `AgentStateStore`：ASKING 调用存储后可恢复；重复确认只会有一次业务执行。
- MCP：初始化、`tools/list`、同名工具、`readOnlyHint` 缺省、`isError`、超时和 metadata 透传。
- 流与 tracing：取消后 `agent.interrupt` 被调用、`Disposable` 释放、span 结束、SSE 仅发一次终态。

模块现有的 `SkillLoadToolActivationTest`、`McpToolProxyTest`、`AgentMcpClientsModeTest`、`AgentRunHandleTest`、`AgentTraceScenarioTest` 正是这些契约的代码锚点。框架升级时先跑这些测试，再讨论“模型回答有没有更聪明”。

