+++
date = '2026-03-06T16:46:32+08:00'
draft = false
title = '发件箱模式（The Outbox Pattern）'
+++

发箱模式解决分布式事务

https://juejin.cn/post/6844903912453963784

https://godruoyi.com/posts/what-is-the-outbox-pattern/

outbox 是什么意思？它是一张用于存储 ES 和 MySQL 同步的记录表嘛

Outbox（**本地消息表 / 发件箱模式**）指的是：**在 MySQL 里建一张“要发送的事件/消息”表**，用来把“业务数据变更”可靠地转成“异步消息”，再由后台发送到 MQ（RocketMQ/Kafka），最终驱动 ES 同步。

所以它不是“ES 和 MySQL 的对账表/同步结果表”本身，但**可以承载同步所需的事件记录**，并且通常会包含发送/重试状态，从而保证“不丢消息”。

------

## Outbox 解决的核心问题是什么？

如果你直接这样做：

1. 事务里写 MySQL
2. 事务提交后发 MQ
3. 消费者写 ES

一旦在 **2** 这步发 MQ 失败（网络抖动、服务挂了），就会出现：

- MySQL 已经成功
- 但 MQ 没发出去
- ES 永远收不到增量变更
- **不一致且难以补救**

Outbox 的关键点是：
 **把“写业务数据”和“记录要发的消息”放在同一个数据库事务里完成**。

------

## Outbox 是一张什么表？一般存什么？

它是一张“待发送事件”表，典型字段：

- `id`（自增/雪花）
- `event_id`（全局唯一，做幂等）
- `biz_type`（业务类型，如 content）
- `biz_id`（业务主键）
- `op`（UPSERT/DELETE）
- `payload`（可选：消息体或必要字段）
- `status`（NEW/SENT/FAIL…）
- `retry_count / next_retry_time / last_error`
- `created_at / updated_at`

### 它是不是“用于存储 ES 和 MySQL 同步的记录表”？

**可以这么理解，但更准确的说法是：**

- Outbox 记录的是：**“MySQL 发生了哪些变更需要同步出去”**（同步事件）
- 不一定记录“ES 是否已经同步成功”，不过很多团队会在 outbox 里也记录发送/处理状态，或者再加一张 `index_status` 表来记录“ES 索引状态”。

------

## 一句话总结

- **Outbox = 业务变更事件的本地持久化队列**（存在 MySQL）
- 用来保证：**只要 MySQL 事务成功，这个变更就不会丢，最终一定能发到 MQ，从而同步到 ES**。
