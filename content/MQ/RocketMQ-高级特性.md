+++
date = '2026-08-22T15:50:00+08:00'
draft = false
title = 'RocketMQ 高级特性'
+++

RocketMQ 的高级特性通常不是为了“写出更炫的代码”，而是为了处理真实业务里的麻烦：本地事务和消息发送的一致性、重复消费、失败重试、死信消息、顺序消费、延迟触发。

这些能力用得好，可以让系统更稳；用得随意，则只是把问题延后，并且换个更难排查的形态出现。技术很少凭空仁慈，这点还请记住。

## 一、事务消息解决什么问题

先看一个常见场景：订单创建成功后，需要发送一条 `order-created` 消息，让库存、优惠券、积分等系统异步处理。

如果直接这样写：

```java
orderService.createOrder(order);
rocketMQTemplate.syncSend("order-topic:created", event);
```

会有两个不一致问题：

- 本地订单创建成功，但消息发送失败，下游永远不知道订单创建。
- 消息发送成功，但本地订单事务回滚，下游却收到了不存在的订单。

事务消息要解决的正是“本地事务与消息发送”之间的一致性问题。

## 二、事务消息二阶段

RocketMQ 事务消息采用类似二阶段提交的机制，但它不是 XA。它的目标是让消息发送和本地事务达到最终一致。

流程如下：

```text
1. Producer -> Broker: 发送半消息
2. Broker -> Producer: 半消息写入成功，返回 ACK
3. Producer: 执行本地事务
4. Producer -> Broker: 提交 Commit 或 Rollback
5. Broker:
   - Commit: 消息对 Consumer 可见
   - Rollback: 删除或丢弃半消息
   - Unknown/超时: 发起事务回查
```

所谓半消息，就是 Broker 已经收到但暂时不投递给消费者的消息。只有第二阶段提交后，消费者才看得到它。

## 三、事务回查

事务回查用于处理不确定状态。

比如下面几种情况：

- Producer 执行完本地事务后宕机，没来得及提交 Commit。
- Producer 提交 Commit 时网络抖动，Broker 没收到结果。
- 本地事务执行时间过长，Producer 暂时返回 Unknown。

这时 Broker 会回查生产者集群中的某个实例，询问这条半消息对应的本地事务到底成功还是失败。

所以本地事务表非常重要。生产者必须能根据消息 Key 或事务 ID 查询本地事务状态：

| 本地状态 | 回查结果 |
| --- | --- |
| 订单已创建 | `COMMIT` |
| 订单不存在 | `ROLLBACK` |
| 订单处理中 | `UNKNOWN` |

如果回查逻辑写不可靠，事务消息就会失去意义。

## 四、事务消息的边界

事务消息只保证生产端本地事务和消息发送最终一致，不保证消费者处理一定成功。

换句话说：

```text
订单创建成功 -> 消息最终可投递
```

它不保证：

```text
库存一定扣减成功
积分一定发放成功
优惠券一定核销成功
```

消费者侧仍然要靠重试、幂等、补偿和死信处理来保证业务最终完成。

事务消息适合：

- 创建订单后通知下游。
- 支付成功后通知履约。
- 账户入账后通知对账。
- 本地状态变更后异步驱动多个系统。

不适合：

- 强一致同步事务。
- 不能接受中间状态的业务。
- 下游必须立即成功的链路。

## 五、事务消息代码骨架

发送事务消息：

```java
Message<OrderCreatedEvent> message = MessageBuilder
    .withPayload(event)
    .setHeader(MessageConst.PROPERTY_KEYS, event.getOrderId())
    .build();

rocketMQTemplate.sendMessageInTransaction(
    "order-topic:created",
    message,
    event.getOrderId()
);
```

事务监听器：

```java
@Component
@RocketMQTransactionListener
public class OrderTransactionListener implements RocketMQLocalTransactionListener {

    private final OrderService orderService;

    public OrderTransactionListener(OrderService orderService) {
        this.orderService = orderService;
    }

    @Override
    public RocketMQLocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        String orderId = (String) arg;
        try {
            orderService.createOrder(orderId);
            return RocketMQLocalTransactionState.COMMIT;
        } catch (DuplicateOrderException ex) {
            return RocketMQLocalTransactionState.COMMIT;
        } catch (Exception ex) {
            return RocketMQLocalTransactionState.UNKNOWN;
        }
    }

    @Override
    public RocketMQLocalTransactionState checkLocalTransaction(Message msg) {
        String orderId = String.valueOf(msg.getHeaders().get(MessageConst.PROPERTY_KEYS));
        OrderStatus status = orderService.queryStatus(orderId);

        if (status == OrderStatus.CREATED) {
            return RocketMQLocalTransactionState.COMMIT;
        }
        if (status == OrderStatus.NOT_FOUND) {
            return RocketMQLocalTransactionState.ROLLBACK;
        }
        return RocketMQLocalTransactionState.UNKNOWN;
    }
}
```

注意这里对普通异常返回了 `UNKNOWN`。如果只是因为数据库短暂超时，直接 `ROLLBACK` 可能会把已经成功的本地事务对应消息回滚掉。是否返回 `ROLLBACK`，必须基于明确的本地事务失败事实。

## 六、重复消费与幂等

RocketMQ 默认是至少一次投递，因此重复消费是正常现象。

重复消费可能来自：

- Producer 发送重试导致 Broker 收到重复消息。
- Consumer 消费成功但提交 offset 前宕机。
- ConsumerGroup Rebalance 后，新实例从旧 offset 拉取。
- 消费超时后 Broker 认为失败并重新投递。
- 人工重新投递死信消息。

解决重复消费的方式不是祈祷它不要发生，而是让业务幂等。

常见做法：

```sql
CREATE TABLE mq_consume_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    consumer_group VARCHAR(128) NOT NULL,
    message_key VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_group_message (consumer_group, message_key)
);
```

消费时：

1. 取业务唯一 Key，比如 `orderId`。
2. 插入消费记录。
3. 如果唯一键冲突，说明已经处理过，直接返回成功。
4. 执行业务逻辑。
5. 更新消费记录状态。

示例：

```java
@Transactional
public void consume(OrderPaidEvent event) {
    boolean firstConsume = consumeLogRepository.tryInsert(
        "inventory-order-paid-group",
        event.getOrderId()
    );
    if (!firstConsume) {
        return;
    }

    inventoryService.deduct(event.getOrderId());
    consumeLogRepository.markSuccess("inventory-order-paid-group", event.getOrderId());
}
```

如果只是单机内存布隆过滤器，重启就会丢状态；如果是分布式集群，各实例之间也无法共享准确处理结果。布隆过滤器可以做前置拦截，但不能替代数据库唯一键、Redis 原子写入或业务状态机。

## 七、发送重试

生产者发送失败时，RocketMQ 可以自动重试。

常见配置：

```java
DefaultMQProducer producer = new DefaultMQProducer("order-producer-group");
producer.setRetryTimesWhenSendFailed(2);
producer.setRetryTimesWhenSendAsyncFailed(2);
producer.setRetryAnotherBrokerWhenNotStoreOK(true);
```

需要注意：

- 同步发送失败默认会重试。
- 异步发送失败可配置重试次数。
- 单向发送没有可靠失败反馈。
- 发送重试可能造成重复消息。

对关键业务来说，发送失败后还应记录本地发送日志，通过定时任务或 Outbox 机制补偿，而不是只依赖客户端内存里的重试。

## 八、消费重试

消费者消费失败后，可以通过抛异常或返回失败状态触发重试。

并发消费中：

```java
consumer.registerMessageListener((MessageListenerConcurrently) (msgs, context) -> {
    try {
        handle(msgs.get(0));
        return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
    } catch (Exception ex) {
        return ConsumeConcurrentlyStatus.RECONSUME_LATER;
    }
});
```

Spring 监听器中：

```java
@Override
public void onMessage(OrderPaidEvent event) {
    inventoryService.deduct(event.getOrderId());
}
```

如果 `deduct` 抛出异常，框架会认为消费失败并触发重试。

消费重试适合临时故障：

- 数据库短暂不可用。
- Redis 超时。
- 下游接口临时失败。
- 网络抖动。

不适合永久错误：

- 消息字段缺失。
- 业务状态已经不允许处理。
- 参数格式根本不合法。

永久错误应记录异常并结束重试，否则只是在认真地浪费机器。

## 九、死信队列

当消息超过最大重试次数仍然失败，就会进入死信队列。RocketMQ 中死信队列通常是以 ConsumerGroup 维度生成的特殊 Topic。

死信消息意味着：

- 正常消费链路已经处理不了这条消息。
- 需要人工、补偿任务或专门的死信消费者介入。
- 不能简单删除，除非已经确认业务无需处理。

监听死信队列的示例：

```java
@Service
@RocketMQMessageListener(
    topic = "%DLQ%inventory-order-paid-group",
    consumerGroup = "inventory-dlq-handler-group"
)
public class InventoryDlqConsumer implements RocketMQListener<MessageExt> {

    @Override
    public void onMessage(MessageExt message) {
        String body = new String(message.getBody(), StandardCharsets.UTF_8);
        System.out.println("dlq message: " + body);
    }
}
```

实际项目中，死信处理通常要做：

- 记录消息体、Topic、Tag、Key、重试次数。
- 记录异常原因。
- 提供后台页面查看。
- 支持修复数据后重新投递。
- 支持标记忽略，但必须留审计记录。

## 十、顺序消息边界

顺序消息分两类：

- 全局有序：整个 Topic 只有一个队列，吞吐很低。
- 分区有序：同一个业务 Key 进入同一个队列，工程上更常用。

订单状态流转通常用分区有序：

```text
orderId=10001 -> queue0: created -> paid -> shipped
orderId=10002 -> queue1: created -> canceled
```

生产端要保证同一个订单号进入同一个队列：

```java
rocketMQTemplate.syncSendOrderly(
    "order-status-topic",
    message,
    event.getOrderId()
);
```

消费端要启用顺序消费：

```java
@RocketMQMessageListener(
    topic = "order-status-topic",
    consumerGroup = "order-status-group",
    consumeMode = ConsumeMode.ORDERLY
)
```

顺序消费失败时，同一队列后续消息会被阻塞。因此顺序消息的消费逻辑必须尽量短、稳定、可观测。

## 十一、延迟消息

延迟消息用于“过一段时间再触发检查”。

典型场景：

- 下单 30 分钟后检查是否支付。
- 支付后延迟检查履约状态。
- 任务提交后延迟检查执行结果。

示例：

```java
Message<String> message = MessageBuilder
    .withPayload(orderId)
    .setHeader(MessageConst.PROPERTY_KEYS, orderId)
    .build();

rocketMQTemplate.syncSend("order-delay-topic:close", message, 3000, 16);
```

延迟消息消费时要重新查询业务状态：

```java
public void onMessage(String orderId) {
    Order order = orderRepository.findById(orderId);
    if (order.isUnpaid()) {
        orderService.close(orderId);
    }
}
```

不要在发送延迟消息时就假设 30 分钟后一定要关闭订单。业务状态会变化，消息只是提醒你去检查。

## 十二、Topic 与 Tag 设计

Topic 和 Tag 的拆分建议：

| 判断维度 | 建议 |
| --- | --- |
| 业务域完全不同 | 拆 Topic |
| 消息类型不同 | 拆 Topic |
| 消息量级差异巨大 | 拆 Topic |
| 同一业务下的事件类型 | 用 Tag |
| 消费权限和隔离要求不同 | 拆 Topic |

例子：

```text
order-topic
  - created
  - paid
  - canceled

inventory-topic
  - locked
  - deducted
  - released
```

不要为了省 Topic 把毫不相关的消息都塞进去，也不要为了“看起来清晰”给每个小事件都建 Topic。设计不是数量竞赛。

## 十三、生产建议

上线前至少确认：

- 每条消息都有业务 Key。
- 消费者具备幂等处理。
- 消费失败能区分临时失败和永久失败。
- 死信队列有处理流程。
- 消费积压有监控。
- Producer 发送失败有日志和补偿。
- 重要 Topic 有合理队列数。
- 顺序消息的 sharding key 选择稳定。
- 事务消息有可靠本地事务查询。

## 十四、一句话总结

RocketMQ 的高级特性本质上都在处理“不确定性”：网络不确定、进程不确定、下游不确定、业务状态不确定。把这些不确定性设计进系统里，消息队列才会成为可靠的工程工具。

## 参考资料

- [Apache RocketMQ：Transaction Message](https://rocketmq.apache.org/docs/featureBehavior/04transactionmessage/)
- [Apache RocketMQ：Ordered Message](https://rocketmq.apache.org/docs/featureBehavior/03fifomessage/)
- [Apache RocketMQ：Consumption Retry](https://rocketmq.apache.org/docs/featureBehavior/10consumerretrypolicy/)
