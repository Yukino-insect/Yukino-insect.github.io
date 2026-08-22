+++
date = '2026-08-22T16:14:00+08:00'
draft = false
title = 'Kafka 高级特性'
+++

Kafka 的高级特性主要围绕可靠性和吞吐展开：幂等生产、事务、顺序、重试、死信、日志压缩、积压治理。

先把一个常见误解说清楚：Kafka 的 exactly-once 不是说“你的整个业务世界都精确一次”。它主要解决的是 Kafka 内部生产、消费 offset 和再生产之间的一致性。外部数据库、HTTP 接口、缓存变更仍然需要业务自己保证幂等和补偿。

## 一、消息投递语义

Kafka 常见投递语义：

| 语义 | 含义 | 代价 |
| --- | --- | --- |
| At most once | 最多一次，可能丢失，不重复 | 可靠性低 |
| At least once | 至少一次，不丢但可能重复 | 需要幂等 |
| Exactly once | Kafka 内部读写链路精确一次 | 配置和事务成本更高 |

普通业务消费最常见的是至少一次：

```text
poll -> 处理业务 -> commit offset
```

如果处理成功但提交 offset 前宕机，消息会被重新消费。这不是 Kafka 出错，而是至少一次语义的正常结果。

## 二、幂等生产者

幂等生产者用于避免生产者重试导致同一分区内写入重复消息。

配置：

```properties
enable.idempotence=true
acks=all
retries=3
```

开启后，Producer 会为每个分区维护序列号。Broker 可以根据 Producer ID 和序列号识别重复写入。

幂等生产者能解决：

- 发送请求成功写入 Broker。
- ACK 在网络中丢失。
- Producer 误以为失败并重试。
- Broker 识别重复请求，不重复追加日志。

它不能解决：

- 业务代码自己调用了两次发送。
- 两个不同 Producer 发送了相同业务事件。
- 消费者重复消费。

所以消息 key 和业务幂等仍然必须存在。

## 三、Producer 可靠性配置

关键业务常用配置：

```properties
acks=all
enable.idempotence=true
retries=2147483647
delivery.timeout.ms=120000
request.timeout.ms=30000
max.in.flight.requests.per.connection=5
```

Broker 侧建议：

```properties
replication.factor=3
min.insync.replicas=2
unclean.leader.election.enable=false
```

含义：

- `acks=all`：等待 ISR 中副本确认。
- `min.insync.replicas=2`：至少两个同步副本才允许成功写入。
- `unclean.leader.election.enable=false`：避免选举落后副本导致数据丢失。
- `enable.idempotence=true`：避免生产重试重复写入。

可靠性越强，延迟和可用性压力越高。系统设计里很少有免费的午餐，有的只是账单被推迟。

## 四、Kafka 事务

Kafka 事务可以把多条写入和消费 offset 放进同一个事务中。

典型读处理写场景：

```text
consume input-topic
  -> process
  -> produce output-topic
  -> commit consumed offsets in transaction
```

如果事务提交成功：

- 输出消息对下游可见。
- 输入消息 offset 一起提交。

如果事务回滚：

- 输出消息不可见。
- 输入 offset 不提交，后续可以重新处理。

配置：

```properties
transactional.id=order-app-1
enable.idempotence=true
acks=all
```

Spring Kafka 中可以配置：

```yaml
spring:
  kafka:
    producer:
      transaction-id-prefix: order-tx-
```

代码：

```java
kafkaTemplate.executeInTransaction(operations -> {
    operations.send("order-result-topic", event.getOrderId(), resultEvent);
    operations.send("order-audit-topic", event.getOrderId(), auditEvent);
    return true;
});
```

## 五、事务与数据库

Kafka 事务不能自动覆盖数据库事务。

下面这段代码仍然有一致性风险：

```java
@Transactional
public void createOrder(Order order) {
    orderRepository.save(order);
    kafkaTemplate.send("order-topic", order.getId(), order);
}
```

可能出现：

- 数据库提交成功，Kafka 发送失败。
- Kafka 发送成功，数据库提交失败。
- 应用在两个动作之间宕机。

常见解决方案是 Outbox：

1. 在同一个数据库事务里写业务表和本地消息表。
2. 后台任务扫描本地消息表。
3. 发送 Kafka。
4. 发送成功后标记消息已发送。
5. 下游消费仍然按业务 key 幂等。

示例表：

```sql
CREATE TABLE outbox_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_event (aggregate_id, event_type)
);
```

Outbox 不花哨，但很可靠。可靠的东西通常没有那么戏剧化，像雪一样安静地落在地上，然后把坑填平。

## 六、顺序消息

Kafka 的顺序边界是 Partition。

要保证同一业务对象有序：

- Producer 使用稳定 key，比如 `orderId`。
- 相同 key 的消息进入同一 Partition。
- Consumer 对同一 Partition 按 poll 顺序处理。
- 不要在业务线程池里打乱同一 key 的处理顺序。

示例：

```java
kafkaTemplate.send("order-status-topic", event.getOrderId(), event);
```

不能保证全局顺序：

```text
partition-0: A1 A2 A3
partition-1: B1 B2 B3
```

不同 Partition 之间没有全局先后关系。如果要求整个 Topic 全局有序，只能使用一个 Partition，但吞吐和可用性都会受限。

## 七、消费者幂等

消费者幂等是 Kafka 业务可靠性的基础。

常用方案：

- 数据库唯一键。
- Redis `SETNX`。
- 业务状态机。
- 消费日志表。
- 幂等接口。

消费日志表示例：

```sql
CREATE TABLE kafka_consume_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    consumer_group VARCHAR(128) NOT NULL,
    topic VARCHAR(128) NOT NULL,
    message_key VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_consume (consumer_group, topic, message_key)
);
```

消费逻辑：

```java
@Transactional
public void consume(OrderPaidEvent event) {
    boolean inserted = consumeLogRepository.tryInsert(
        "inventory-order-group",
        "order-topic",
        event.getOrderId()
    );
    if (!inserted) {
        return;
    }

    inventoryService.deduct(event.getOrderId());
    consumeLogRepository.markSuccess(event.getOrderId());
}
```

如果业务状态天然幂等，也可以直接依赖状态机：

```text
UNPAID -> PAID -> SHIPPED
```

重复收到 `PAID` 事件时，如果订单已经是 `PAID` 或更后续状态，就直接忽略。

## 八、重试与死信主题

Kafka 本身没有像 RocketMQ 那样的消费重试等级队列。Spring Kafka 通常通过错误处理器、重试主题或死信主题实现。

简单重试 + DLT：

```java
@Bean
public DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> kafkaTemplate) {
    DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(
        kafkaTemplate,
        (record, ex) -> new TopicPartition(record.topic() + ".DLT", record.partition())
    );
    return new DefaultErrorHandler(recoverer, new FixedBackOff(1000L, 3L));
}
```

设计建议：

- 临时错误可以重试。
- 永久错误不要无限重试。
- DLT 消息必须可观测、可查询、可重新投递。
- DLT 主题分区数不要少于原 Topic。

对于需要多级延迟重试的场景，可以设计：

```text
order-topic
  -> order-topic.retry.1m
  -> order-topic.retry.5m
  -> order-topic.retry.30m
  -> order-topic.DLT
```

Spring Kafka 也提供非阻塞重试主题能力，可以减少监听线程被阻塞的时间。

## 九、延迟消息

Kafka 不以原生延迟消息为核心能力。常见实现方式有：

- Spring Kafka retry topic。
- 单独的延迟调度服务。
- 时间轮服务。
- 数据库定时扫描。
- Kafka Streams 按时间窗口处理。

订单超时关闭这类业务，不建议强行把 Kafka 当定时器。更稳妥的方式通常是：

1. 订单创建时写入过期时间。
2. 调度任务扫描到期未支付订单。
3. 发送关闭事件或直接关闭。
4. 消费端再次校验订单状态。

如果一定要用 Kafka 做延迟重试，至少要把重试 Topic、时间粒度、最大重试次数和 DLT 都设计清楚。

## 十、日志压缩

Kafka 的 `cleanup.policy=compact` 可以按 key 保留最新值。

适合：

- 用户状态快照。
- 商品库存快照。
- 配置变更。
- 维表同步。

示例：

```properties
cleanup.policy=compact
```

如果写入：

```text
key=user-1 value={"name":"A"}
key=user-1 value={"name":"B"}
key=user-2 value={"name":"C"}
```

压缩后最终会尽量保留 `user-1` 的最新值和 `user-2` 的最新值。

不适合：

- 支付流水。
- 审计日志。
- 需要完整历史的业务事件。

## 十一、积压治理

Kafka 消费积压通常表现为 consumer lag 持续升高。

常见原因：

- 消费者数量少于 Partition 数。
- 单条消息处理太慢。
- 下游数据库或接口慢。
- 单个 key 过热，导致单分区积压。
- Rebalance 频繁。
- 批量参数太小。

治理思路：

1. 先确认是所有分区积压，还是单分区积压。
2. 如果所有分区积压，增加消费者实例或优化处理逻辑。
3. 如果单分区积压，检查热点 key。
4. 如果下游慢，优先治理下游，而不是盲目加消费者。
5. 如果 Partition 数不足，评估扩分区对顺序和 key 分布的影响。

扩 Partition 要小心。Partition 数增加后，相同 key 的取模结果可能变化，后续消息可能进入新分区，从而破坏该 key 的历史顺序连续性。

## 十二、监控指标

生产环境至少关注：

- Producer 发送失败率。
- Producer 请求延迟。
- Broker 磁盘使用率。
- Broker 网络吞吐。
- Under replicated partitions。
- Offline partitions。
- Consumer lag。
- Rebalance 次数。
- 消费处理耗时。
- DLT 消息数量。

Kafka 很擅长吞吐，但吞吐不是免死金牌。监控缺失时，高吞吐只是更快地把问题推向下游。

## 十三、生产建议

上线 Kafka 业务前确认：

- Topic 分区数和副本数合理。
- 关键消息使用 `acks=all` 和幂等生产者。
- 消息 key 使用稳定业务 ID。
- 消费者关闭自动提交 offset。
- 处理成功后再提交 offset。
- 消费逻辑幂等。
- 错误处理和 DLT 已配置。
- DLT 有告警和处理流程。
- 消费耗时小于 `max.poll.interval.ms`。
- 外部数据库一致性使用 Outbox 或补偿机制。

## 十四、一句话总结

Kafka 的高级特性不是为了让系统“绝对不会出错”，而是让系统在网络抖动、进程宕机、重复投递和下游失败时仍然知道该怎么继续。成熟系统的美感，大概就在这种不慌不忙里。

## 参考资料

- [Apache Kafka：Message Delivery Semantics](https://kafka.apache.org/documentation/#semantics)
- [Apache Kafka：Producer Configs](https://kafka.apache.org/documentation/#producerconfigs)
- [Apache Kafka：Log Compaction](https://kafka.apache.org/documentation/#compaction)
- [Spring Kafka：Non-Blocking Retries](https://docs.spring.io/spring-kafka/reference/retrytopic.html)
- [Spring Kafka：Transactions](https://docs.spring.io/spring-kafka/reference/kafka/transactions.html)
