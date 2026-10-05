+++
date = '2026-10-02T20:04:00+08:00'
draft = false
title = 'MiddlewareBase：`onReasoning`、`onActing` 与可验证的顺序'
+++
AgentScope 的横切扩展不该塞进 Controller。实现 `MiddlewareBase` 后，`onReasoning` 可以改写本轮模型输入，`onActing` 可以包裹一批工具执行。Ragent 的用户记忆、上下文压缩、拒绝确认文案、Skill 工具遮蔽、工具批统计和 tracing 都走这些 API。

## 过滤本轮可见工具：`onReasoning`

```java
public Flux<AgentEvent> onReasoning(Agent agent, RuntimeContext ctx,
    ReasoningInput input, Function<ReasoningInput, Flux<AgentEvent>> next) {
  List<ToolSchema> visible = input.tools().stream()
      .filter(this::allowed).toList();
  return next.apply(new ReasoningInput(input.messages(), visible, input.options()));
}
```

`AgentSkillMaskingMiddleware` 按这一方式遮蔽“尚未加载 Skill 手册”的工具，并将遮蔽映射放入 `RuntimeContext`。`McpToolProxy.callAsync` 还会在真正执行前读取该映射二次拒绝，因此旧上下文/缓存意外产生的工具调用也不能绕过。

若访问 JDBC 或同步模型，要用 `Flux.defer` 延迟执行并用 `boundedElastic` 隔离。`AgentUserMemoryMiddleware` 只将调用级记忆快照放在 `RuntimeContext`，绝不放 Spring 单例字段；否则并发会话会串用户。

## 观察工具批：`onActing`

```java
public Flux<AgentEvent> onActing(Agent agent, RuntimeContext ctx,
    ActingInput input, Function<ActingInput, Flux<AgentEvent>> next) {
  Batch batch = begin(input.toolCalls());
  return next.apply(input).doFinally(signal -> end(batch));
}
```

`AgentToolBatchMiddleware` 正是用 `input.toolCalls()` 登记 call ID，再以 `doFinally` 收口。不要只在 `doOnComplete` 清理；异常和取消不会触发 complete，批会永久显示运行中。

## `order()` 是语义

Ragent 把追踪放外层，再依次记忆注入、压缩、确认拒绝改写、Skill 遮蔽，工具批中间件 `order() == 0` 贴近实际工具体。压缩必须先于 Skill 遮蔽：手册被压缩移除时，遮蔽层才能重新隐藏工具。每加一个 middleware，都应写测试明确它应看见原始 messages 还是上层处理后的 messages；顺序错误不是性能问题，而是功能与权限错误。

