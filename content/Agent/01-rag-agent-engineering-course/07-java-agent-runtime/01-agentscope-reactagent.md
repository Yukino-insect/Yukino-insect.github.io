+++
date = '2026-10-02T20:01:00+08:00'
draft = false
title = 'AgentScope ReActAgent：创建、调用、事件消费与中断'
+++
本模块的执行器是 `io.agentscope.core.ReActAgent`。你使用它时不是手写“模型调用 while 循环”，而是提供模型、`Toolkit`、会话状态和中间件，由 `streamEvents` 返回运行事件。项目的 `ReActAgentProvider.buildAgent()` 已经给出一份可直接拆解的生产装配。

## 依赖与最小实例

```xml
<dependency>
  <groupId>io.agentscope</groupId>
  <artifactId>agentscope-core</artifactId>
  <version>2.0.2</version>
</dependency>
```

```java
ReActAgent agent = ReActAgent.builder()
    .name("demo-agent")
    .sysPrompt("只在确有必要时调用工具。")
    .model(chatModel)
    .toolkit(toolkit)
    .maxIters(10)
    .maxRetries(1)
    .stateStore(stateStore)
    .build();
```

`model` 是必需的。`toolkit` 为空时仍可做普通对话；`stateStore` 为空时会话状态只能留在当前进程。`maxIters` 限的是 ReAct 轮数，不是 token 数；第 10 轮仍不能得到终答时，框架发出达到上限的事件。`maxRetries` 是单次模型调用的**最大尝试次数，含首次**：Ragent 设 `1`，表示不做框架层重试。

## 正确调用 `streamEvents`

```java
RuntimeContext ctx = RuntimeContext.builder()
    .userId("42")
    .sessionId("conversation-1001")
    .build();

Flux<AgentEvent> flow = agent.streamEvents(
    new UserMessage("查询公司差旅制度"), ctx);
Disposable subscription = flow.subscribe(
    event -> System.out.println(event.getClass().getSimpleName()),
    error -> log.error("agent failed", error),
    () -> log.info("agent completed"));
```

`Flux` 在订阅前不执行。`RuntimeContext` 是调用级容器，Ragent 还用它传递 MCP metadata、追踪对象、任务 ID；不能把这些数据放在 `ReActAgent` 或单例 middleware 成员字段中。`userId + sessionId` 同时是框架状态存取维度，尤其不要把全站所有请求固定成一个 `sessionId`。

## 事件消费不要只看文本

真正要处理的是 `AgentEvent` 的不同子类：文本/思考 delta、工具调用开始、工具结果开始/结束、`RequireUserConfirmEvent`、`AllToolsDeniedEvent`、`ExceedMaxItersEvent` 和最终结果。Ragent 的 `AgentStreamEventBridge` 将这些转换成自己的 SSE event 与可回放消息块；不要直接把 SDK 事件 JSON 返回浏览器，否则升级 SDK 就会破坏前端协议。

## 中断与状态清理

Web 请求断开时，调用 `agent.interrupt(userId, sessionId)`，并释放 `Disposable`。只 dispose SSE 订阅并不能保证框架和工具停止。Ragent 的 `AgentRunHandle` 在取消/错误收尾时按“必要时保存状态 -> 清本地缓存 -> 释放 Redis 会话锁”的顺序执行；该顺序不能调换，否则下一请求可能读到半截状态或被旧请求清掉新缓存。

对应源码：`config/ReActAgentProvider.java`、`service/impl/AgentChatServiceImpl.java`、`service/handler/AgentStreamEventBridge.java`。先用没有写副作用的工具跑通本篇，再进入工具章节。

