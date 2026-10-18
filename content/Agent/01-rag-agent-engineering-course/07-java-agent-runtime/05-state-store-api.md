+++
date = '2026-10-02T20:05:00+08:00'
draft = false
title = 'AgentStateStore：用 PostgreSQL 保存并恢复 AgentScope 会话'
+++
`AgentStateStore` 是 AgentScope 保存运行状态的 SPI。它保存的不只是聊天文本，还可能包含工具调用、工具结果和等待确认的中间态；因此不能把它当成前端聊天记录表，也不要随意换 JSON 序列化器。

## 实现 SPI

Ragent 的 `PgAgentStateStore` 以 `(userId, sessionId, key)` 为主键，将框架 `State` JSON UPSERT 到 PostgreSQL：

```java
public final class PgAgentStateStore implements AgentStateStore {
  public void save(String userId, String sessionId, String key, State value) {
    mapper.upsert(userId, sessionId, key, JsonUtils.getJsonCodec().toJson(value));
  }
  public <T extends State> Optional<T> get(String userId, String sessionId,
      String key, Class<T> type) {
    String json = mapper.selectPayload(userId, sessionId, key);
    return StrUtil.isBlank(json) ? Optional.empty()
        : Optional.ofNullable(JsonUtils.getJsonCodec().fromJson(json, type));
  }
}
```

还必须实现 list 版 `save/getList`、`exists`、按 session/key 删除和 `listSessionIds`；具体签名以 2.0.2 的 `AgentStateStore` 为准。列表读取不能直接强转：项目先反序列化为 `List<?>`，再用框架 codec `convertValue` 转成 `itemType`，保留多态 block 的结构。

## 接入 Agent

```java
PgAgentStateStore store = new PgAgentStateStore(agentStateMapper);
ReActAgent agent = ReActAgent.builder()
    .model(model).stateStore(store).build();
```

调用时 `RuntimeContext.userId/sessionId` 决定状态位置。用户确认写操作后，Ragent 从 `agent.getAgentState(userId, conversationId).getContext()` 找回状态为 `ASKING` 的原始 `ToolUseBlock`；前端只传批准/拒绝。若改成让前端回传工具参数，就把确认接口变成参数篡改入口。

## 三个容易混淆的对象

| 数据 | 应存在哪里 | 目的 |
| --- | --- | --- |
| AgentScope state JSON | `AgentStateStore` | 恢复 ReAct 循环 |
| 会话标题、消息块、确认卡 | 业务会话/消息表 | 查询、回放、审计 |
| Agent 本地缓存 | `ReActAgent` 内存 | 减少状态读取 |

`clearStateCache(userId, sessionId)` 只清当前 JVM 的缓存，不会删除 PostgreSQL。多节点时共享数据库仍不足：状态变更后需要 Redis 广播失效或版本校验；同时保留同会话的 Redisson 锁，避免两个节点读取同一旧状态并各自执行一次写工具。

## 测试

为 store 写 round-trip 测试：存单个 `State`、存 `List<State>`、空值、删除、列会话，以及含 `ToolUseBlock`/`ToolResultBlock` 的状态。再做一条确认恢复测试，验证重启后仍能从 DB 找回 ASKING 调用。不要只测“JSON 字符串不为空”。

