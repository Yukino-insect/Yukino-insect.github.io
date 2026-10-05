+++
date = '2026-10-02T20:09:00+08:00'
draft = false
title = 'Reactor 与 SseEmitter：消费 `Flux<AgentEvent>`、取消和收尾'
+++
AgentScope 的 `streamEvents` 是 Reactor `Flux<AgentEvent>`，而 Ragent 的 Web 层是 Spring MVC `SseEmitter`，不是 WebFlux Controller。二者必须显式桥接，不能因为底层用了 Reactor 就在 Servlet 线程里随意 `block()`。

## 正确订阅位置

Ragent 在订阅前创建 `AgentRunHandle`、注册 `taskId` 取消回调、发送 SSE 元信息，再订阅：

```java
Flux<AgentEvent> events = agent.streamEvents(input, runtimeContext)
    .doFinally(signal -> runHandle.markUpstreamTerminated());
Disposable d = events.subscribe(bridge::onEvent, bridge::onError, bridge::onComplete);
runHandle.bindStream(d, () -> agent.interrupt(userId, conversationId));
```

`doFinally` 覆盖 complete、error、cancel。文本增量、工具开始/结束、确认、最大迭代和终答由 `AgentStreamEventBridge` 转为业务 SSE event；不要在浏览器端识别 AgentScope 类名。

## `SseEmitter` 的三个断开入口

```java
emitter.onTimeout(cancel);
emitter.onError(e -> cancel.run());
emitter.onCompletion(cancel);
```

页面关闭时有的 Servlet 容器只触发 completion；只监听 timeout 会造成模型与工具继续空跑。`cancel` 需要调用任务管理器，进而 interrupt Agent 并 dispose 订阅。对已执行的写工具，取消不等于未成功：网络可能在下游提交后才断开，因此结果要靠幂等键/查询确认。

## 不要阻塞错误的线程

`McpClientWrapper.initialize().block()` 是启动期受控阻塞；`KnowledgeSearchTool` 的同步检索用 `subscribeOn(boundedElastic)`；上下文压缩里的同步模型调用也转入该 scheduler。反之，在 `AgentEvent` 回调内等待数据库、MCP 或另一个 `block()` 会拖慢整个流，甚至产生死锁式饥饿。

## 资源收尾测试

为 normal/error/cancel/confirm 四条路径分别断言：SSE 有且仅有一次 DONE、文本块封口、运行中工具改为终态、任务注销、会话锁释放、必要状态已保存。只验证“前端收到了字符串”不能证明这条 Agent 流正确收口。

