+++
date = '2026-08-22T16:10:00+08:00'
draft = false
title = 'Kafka 架构设计'
+++

Kafka 的架构围绕一个核心抽象展开：分布式日志。

Topic 只是逻辑主题，真正承载读写和并发的是 Partition。每个 Partition 都是一段只能追加写入的有序日志，消息在分区内拥有递增的 offset。

## 一、整体架构

```text
+-----------+       +-------------------+       +-----------+
| Producer  | ----> | Kafka Cluster     | <---- | Consumer  |
+-----------+       |  Broker-1         |       +-----------+
                    |  Broker-2         |
                    |  Broker-3         |
                    +-------------------+
```

Kafka 集群由多个 Broker 组成。Producer 将消息写入某个 Topic 的某个 Partition，Consumer 从 Partition 拉取消息。

基本流程：

1. Producer 根据 Topic 元数据找到 Partition Leader。
2. Producer 按 key、分区器或指定分区把消息写入 Partition。
3. Broker 将消息追加到分区日志。
4. ConsumerGroup 内的 Consumer 被分配若干 Partition。
5. Consumer 主动 poll 消息并处理。
6. Consumer 提交 offset，记录自己消费到哪里。

## 二、Broker

Broker 是 Kafka 服务节点，负责：

- 接收生产者写入请求。
- 存储 Partition 日志。
- 响应消费者拉取请求。
- 复制分区副本。
- 参与集群元数据管理。

一个 Topic 的多个 Partition 会分布在多个 Broker 上。这样生产和消费都可以横向扩展。

```text
order-topic
  partition-0 -> broker-1
  partition-1 -> broker-2
  partition-2 -> broker-3
```

## 三、KRaft 与元数据

早期 Kafka 使用 ZooKeeper 管理集群元数据。现代 Kafka 已经转向 KRaft 模式，由 Kafka 自身的 quorum controller 管理元数据。

KRaft 管理的内容包括：

- Broker 注册信息。
- Topic 和 Partition 元数据。
- Partition Leader 选举。
- ACL 等集群元数据。

对使用者来说，日常最需要知道的是：新集群应优先按 KRaft 模式规划，不要再把 ZooKeeper 当作 Kafka 新架构的必需组件。

## 四、Topic 与 Partition

Topic 是消息主题，Partition 是 Topic 的分区。

```text
Topic: payment-topic
  Partition 0: offset 0, 1, 2, 3 ...
  Partition 1: offset 0, 1, 2, 3 ...
  Partition 2: offset 0, 1, 2, 3 ...
```

Partition 决定了 Kafka 的三个重要行为：

- 并发：一个 Topic 有多个 Partition，就可以被多个 Consumer 并行消费。
- 顺序：Kafka 只保证同一个 Partition 内消息有序。
- 扩展：Partition 可以分布在不同 Broker 上。

如果一个 Topic 只有 3 个 Partition，那么同一个 ConsumerGroup 内最多只有 3 个消费者实例能同时消费这个 Topic。第 4 个消费者实例会空闲。

## 五、Record

Kafka 中的一条消息通常叫 Record，包含：

- key：用于分区选择，也常作为业务唯一键。
- value：消息体。
- headers：扩展元数据。
- timestamp：消息时间戳。
- offset：消息在 Partition 内的位置。

key 很重要。默认情况下，相同 key 的消息会进入同一个 Partition，从而保证同一 key 维度的顺序。

比如订单状态流转：

```text
key=order-10001 -> partition-1: created -> paid -> shipped
key=order-10002 -> partition-2: created -> canceled
```

## 六、Producer 写入流程

Producer 写入 Kafka 时，并不是来一条消息就立即发送一次网络请求。它会先经过序列化、分区选择、批量缓存，再发送给 Broker。

简化流程：

```text
Record
  -> Serializer
  -> Partitioner
  -> RecordAccumulator
  -> Sender
  -> Broker Partition Leader
```

常见重要参数：

| 参数 | 含义 |
| --- | --- |
| `acks` | 生产者等待多少副本确认 |
| `batch.size` | 批量发送大小 |
| `linger.ms` | 等待更多消息组成批次的时间 |
| `retries` | 发送失败重试次数 |
| `enable.idempotence` | 是否启用幂等生产 |
| `compression.type` | 压缩算法 |

关键业务推荐：

```properties
acks=all
enable.idempotence=true
retries>0
```

吞吐优先场景可以通过 `batch.size`、`linger.ms`、压缩等参数优化，但要接受延迟和内存占用的变化。

## 七、副本与 Leader

Kafka 的每个 Partition 可以有多个副本。副本中有一个 Leader，其他是 Follower。

```text
partition-0
  leader   -> broker-1
  follower -> broker-2
  follower -> broker-3
```

生产者和消费者主要与 Leader 交互，Follower 从 Leader 复制数据。

重要概念：

| 概念 | 含义 |
| --- | --- |
| `replication.factor` | 副本数 |
| Leader | 处理读写请求的副本 |
| Follower | 从 Leader 同步日志 |
| ISR | 与 Leader 保持同步的副本集合 |
| `min.insync.replicas` | 写入成功所需最小同步副本数 |

如果使用：

```properties
acks=all
min.insync.replicas=2
replication.factor=3
```

含义是：一个分区有 3 个副本，至少 2 个同步副本确认后，生产者才认为写入成功。这样比 `acks=1` 更可靠。

## 八、ConsumerGroup

ConsumerGroup 是 Kafka 的消费负载均衡单位。

同一组内：

```text
topic partition-0 -> consumer-a
topic partition-1 -> consumer-b
topic partition-2 -> consumer-c
```

不同组之间：

```text
order-topic
  -> inventory-group
  -> risk-group
  -> statistics-group
```

每个组都可以独立消费一份消息，并维护自己的 offset。

## 九、Rebalance

Rebalance 是 ConsumerGroup 内 Partition 重新分配的过程。

触发场景：

- Consumer 加入组。
- Consumer 离开组。
- Consumer 心跳超时。
- Topic Partition 数量变化。
- 订阅关系变化。

Rebalance 的影响：

- 分区所有权发生变化。
- 消费可能短暂停顿。
- 如果 offset 提交不及时，可能重复消费。

Spring Kafka 和 Kafka 客户端都提供了多种分区分配策略。生产环境中，要尽量避免消费者频繁重启、处理时间超过 poll 限制、网络抖动导致的反复 Rebalance。

## 十、Offset

Offset 是 Partition 内消息的位置。

Kafka 的 offset 由 ConsumerGroup 维护，通常存储在内部 Topic `__consumer_offsets` 中。

消费过程可以理解为：

```text
poll records
  -> handle records
  -> commit offset
```

如果处理成功但提交 offset 前进程宕机，消息会被再次消费。这就是 Kafka 业务必须幂等的原因。

常见提交方式：

- 自动提交：客户端周期性提交，简单但容易在异常场景下产生语义偏差。
- 手动同步提交：处理完后阻塞提交，语义清晰但影响吞吐。
- 手动异步提交：吞吐更好，但需要处理提交失败。
- 事务提交：和 Kafka 事务配合，把输出消息和消费 offset 放进同一个事务。

## 十一、日志存储

Kafka Partition 在磁盘上是一组日志段文件。消息会顺序追加到日志末尾。

常见清理策略：

- 删除：超过时间或大小后删除旧日志。
- 压缩：按 key 保留最新值，适合状态变更类数据。

配置示例：

```properties
cleanup.policy=delete
retention.ms=604800000
```

日志压缩示例：

```properties
cleanup.policy=compact
```

`compact` 不表示只保留一条消息，而是后台压缩后尽量保留每个 key 的最新值。它适合用户状态、配置状态、库存快照等数据，不适合审计流水这类必须保留完整历史的场景。

## 十二、Kafka 的顺序边界

Kafka 只保证同一个 Partition 内消息有序。

要保证同一订单有序：

- Producer 必须使用订单号作为 key。
- Topic 的 Partition 数量变化要谨慎。
- Consumer 处理同一 Partition 时不能并发打乱顺序。

如果把同一个订单的消息发到不同 Partition，就不要再期待 Kafka 替你维持顺序。它是消息系统，不是读心术。

## 十三、架构排查清单

Kafka 线上排查可以按下面顺序看：

1. Topic 是否存在，Partition 数量是否符合预期。
2. Producer 是否写入成功，是否有序列化或超时错误。
3. `acks`、副本数、ISR 是否满足可靠性要求。
4. ConsumerGroup 是否正确。
5. Consumer lag 是否持续升高。
6. 是否发生频繁 Rebalance。
7. offset 是否正常提交。
8. 是否存在热点 key 导致单分区积压。
9. Broker 磁盘、网络、页缓存是否成为瓶颈。
10. 消费逻辑是否幂等。

## 十四、一句话总结

Kafka 架构的主线是 Partition：它决定吞吐、顺序、扩展、消费并发和故障恢复。理解 Partition，比背诵一堆名词有用得多。

## 参考资料

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Kafka：Concepts and Terms](https://kafka.apache.org/documentation/#intro_concepts_and_terms)
- [Apache Kafka：Producer Configs](https://kafka.apache.org/documentation/#producerconfigs)
