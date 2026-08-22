+++
date = '2026-08-22T15:40:00+08:00'
draft = false
title = 'RocketMQ Spring 集成使用'
+++

在 Spring Boot 项目里使用 RocketMQ，通常优先选择 `rocketmq-spring-boot-starter`。它会帮你自动创建 `RocketMQTemplate`，并通过 `@RocketMQMessageListener` 把消费者注册成消息监听容器。

下面示例基于 RocketMQ Spring 的常见用法。实际项目中版本最好交给公司的依赖管理或 Spring Boot BOM 统一控制，不要在每个业务模块里随手写一个版本号。版本乱了，问题会很勤奋地来找你。

## 一、添加依赖

```xml
<dependency>
    <groupId>org.apache.rocketmq</groupId>
    <artifactId>rocketmq-spring-boot-starter</artifactId>
    <version>2.3.6</version>
</dependency>
```

如果使用 RocketMQ 5.x 客户端能力，也可以关注 `rocketmq-v5-client-spring-boot-starter`。普通 Spring Boot 业务接入时，先确认服务端版本、客户端版本和公司中间件规范，再决定用哪条客户端线。

## 二、基础配置

`application.yml`：

```yaml
rocketmq:
  name-server: 127.0.0.1:9876
  producer:
    group: order-producer-group
    send-message-timeout: 3000
    retry-times-when-send-failed: 2
    retry-times-when-send-async-failed: 2
```

常用配置含义：

| 配置 | 含义 |
| --- | --- |
| `rocketmq.name-server` | NameServer 地址，多个地址用分号分隔 |
| `rocketmq.producer.group` | 默认生产者组 |
| `send-message-timeout` | 发送超时时间 |
| `retry-times-when-send-failed` | 同步发送失败重试次数 |
| `retry-times-when-send-async-failed` | 异步发送失败重试次数 |

## 三、定义消息对象

```java
public class OrderPaidEvent {

    private String orderId;
    private Long userId;
    private Integer amount;

    public OrderPaidEvent() {
    }

    public OrderPaidEvent(String orderId, Long userId, Integer amount) {
        this.orderId = orderId;
        this.userId = userId;
        this.amount = amount;
    }

    public String getOrderId() {
        return orderId;
    }

    public Long getUserId() {
        return userId;
    }

    public Integer getAmount() {
        return amount;
    }
}
```

消息体建议使用明确的事件对象，不要直接塞一段含义不明的字符串。字段含义清楚，后续排查和演进都会轻松一些。

## 四、同步发送

```java
@Service
public class OrderMessageProducer {

    private final RocketMQTemplate rocketMQTemplate;

    public OrderMessageProducer(RocketMQTemplate rocketMQTemplate) {
        this.rocketMQTemplate = rocketMQTemplate;
    }

    public SendResult sendOrderPaid(OrderPaidEvent event) {
        Message<OrderPaidEvent> message = MessageBuilder
            .withPayload(event)
            .setHeader(MessageConst.PROPERTY_KEYS, event.getOrderId())
            .build();

        return rocketMQTemplate.syncSend("order-topic:paid", message);
    }
}
```

`order-topic:paid` 中，冒号前面是 Topic，后面是 Tag。Tag 适合同一 Topic 下的二级分类，比如订单创建、支付、取消。

同步发送适合关键业务消息，因为调用方能拿到发送结果。但注意，发送成功只表示消息到达 Broker，不表示消费者业务已经成功执行。

## 五、异步发送

```java
public void sendOrderPaidAsync(OrderPaidEvent event) {
    Message<OrderPaidEvent> message = MessageBuilder
        .withPayload(event)
        .setHeader(MessageConst.PROPERTY_KEYS, event.getOrderId())
        .build();

    rocketMQTemplate.asyncSend("order-topic:paid", message, new SendCallback() {
        @Override
        public void onSuccess(SendResult sendResult) {
            System.out.println("send success: " + sendResult.getMsgId());
        }

        @Override
        public void onException(Throwable throwable) {
            System.err.println("send failed: " + throwable.getMessage());
        }
    });
}
```

异步发送不要忘记处理失败回调。忽略失败回调，就相当于告诉系统“出事了也别告诉我”，这并不优雅。

## 六、单向发送

```java
public void sendLogEvent(String text) {
    rocketMQTemplate.sendOneWay("log-topic", text);
}
```

单向发送没有发送结果确认，适合日志、埋点等可容忍丢失的场景。订单、支付、库存这类消息不要用单向发送。

## 七、消费者

```java
@Service
@RocketMQMessageListener(
    topic = "order-topic",
    selectorExpression = "paid",
    consumerGroup = "inventory-order-paid-group"
)
public class InventoryOrderPaidConsumer implements RocketMQListener<OrderPaidEvent> {

    @Override
    public void onMessage(OrderPaidEvent event) {
        System.out.println("deduct inventory for order: " + event.getOrderId());
    }
}
```

`@RocketMQMessageListener` 会创建并启动底层消费者容器。常用属性如下：

| 属性 | 含义 |
| --- | --- |
| `topic` | 订阅的 Topic |
| `selectorExpression` | Tag 表达式，默认 `*` |
| `selectorType` | 过滤方式，常见为 Tag 或 SQL92 |
| `consumerGroup` | 消费者组 |
| `messageModel` | 集群消费或广播消费 |
| `consumeMode` | 并发消费或顺序消费 |

## 八、Tag 过滤

同一个 Topic 下可以用 Tag 区分业务子类型：

```text
Topic: order-topic
  - created
  - paid
  - canceled
```

消费者只订阅支付消息：

```java
@RocketMQMessageListener(
    topic = "order-topic",
    selectorExpression = "paid",
    consumerGroup = "points-order-paid-group"
)
public class PointsConsumer implements RocketMQListener<OrderPaidEvent> {

    @Override
    public void onMessage(OrderPaidEvent event) {
        System.out.println("grant points: " + event.getOrderId());
    }
}
```

如果多个消息之间没有业务关联，应该拆 Topic；如果是同一业务域内的子类型，才适合用 Tag。

## 九、SQL92 过滤

如果需要按消息属性过滤，可以使用 SQL92：

```java
Message<OrderPaidEvent> message = MessageBuilder
    .withPayload(event)
    .setHeader("source", "app")
    .setHeader("amountLevel", "high")
    .build();

rocketMQTemplate.syncSend("order-topic:paid", message);
```

消费者：

```java
@Service
@RocketMQMessageListener(
    topic = "order-topic",
    selectorType = SelectorType.SQL92,
    selectorExpression = "amountLevel = 'high'",
    consumerGroup = "risk-high-amount-group"
)
public class RiskConsumer implements RocketMQListener<OrderPaidEvent> {

    @Override
    public void onMessage(OrderPaidEvent event) {
        System.out.println("risk check: " + event.getOrderId());
    }
}
```

SQL 过滤依赖 Broker 侧能力，生产环境使用前要确认服务端配置支持。

## 十、延迟消息

RocketMQ 4.x 常见延迟消息是延迟等级机制。比如订单 30 分钟未支付自动关闭：

```java
public void sendCloseOrderDelayMessage(String orderId) {
    Message<String> message = MessageBuilder
        .withPayload(orderId)
        .setHeader(MessageConst.PROPERTY_KEYS, orderId)
        .build();

    int delayLevel = 16;
    rocketMQTemplate.syncSend("order-delay-topic:close", message, 3000, delayLevel);
}
```

常见默认延迟等级包括：

```text
1s 5s 10s 30s 1m 2m 3m 4m 5m 6m 7m 8m 9m 10m 20m 30m 1h 2h
```

延迟消息适合做“到时间后检查状态”，而不是假设时间一到业务一定成立。比如关闭订单时仍然要查数据库状态，确认订单未支付后再关闭。

## 十一、顺序消息

顺序消息的关键是：相同业务 Key 的消息必须进入同一个队列，消费端也要使用顺序消费模式。

生产者：

```java
public void sendOrderStatus(OrderStatusEvent event) {
    Message<OrderStatusEvent> message = MessageBuilder
        .withPayload(event)
        .setHeader(MessageConst.PROPERTY_KEYS, event.getOrderId())
        .build();

    rocketMQTemplate.syncSendOrderly(
        "order-status-topic",
        message,
        event.getOrderId()
    );
}
```

消费者：

```java
@Service
@RocketMQMessageListener(
    topic = "order-status-topic",
    consumerGroup = "order-status-group",
    consumeMode = ConsumeMode.ORDERLY
)
public class OrderStatusConsumer implements RocketMQListener<OrderStatusEvent> {

    @Override
    public void onMessage(OrderStatusEvent event) {
        System.out.println(event.getOrderId() + " -> " + event.getStatus());
    }
}
```

顺序消息只保证同一个队列内顺序。用订单号作为 sharding key，可以保证同一个订单的状态流转有序，但不同订单之间仍然可以并发处理。

## 十二、消费失败与重试

使用 `RocketMQListener` 时，如果 `onMessage` 正常返回，框架会认为消费成功。如果抛出异常，消息会进入重试流程。

```java
@Override
public void onMessage(OrderPaidEvent event) {
    if (!inventoryService.tryDeduct(event.getOrderId())) {
        throw new IllegalStateException("deduct inventory failed");
    }
}
```

业务上要区分两类失败：

- 临时失败：数据库短暂不可用、下游接口超时，可以抛异常让 MQ 重试。
- 永久失败：消息格式错误、业务状态不合法，继续重试也无意义，应记录异常并返回成功，交给人工或补偿流程。

## 十三、事务消息

RocketMQ Spring 支持事务消息，核心步骤是：

1. 发送事务半消息。
2. 执行本地事务。
3. 根据本地事务结果提交或回滚消息。
4. 如果 Broker 没收到最终结果，会回查本地事务状态。

发送：

```java
public void sendOrderCreatedInTransaction(OrderCreatedEvent event) {
    Message<OrderCreatedEvent> message = MessageBuilder
        .withPayload(event)
        .setHeader(MessageConst.PROPERTY_KEYS, event.getOrderId())
        .build();

    rocketMQTemplate.sendMessageInTransaction(
        "order-topic:created",
        message,
        event.getOrderId()
    );
}
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
        } catch (Exception ex) {
            return RocketMQLocalTransactionState.ROLLBACK;
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

RocketMQ Spring 2.1.0 之后，`@RocketMQTransactionListener` 不再通过 `txProducerGroup` 绑定事务生产者，而是与对应的 `RocketMQTemplate` 关联；如果有多个 `RocketMQTemplate`，可以通过 `rocketMQTemplateBeanName` 指定。

## 十四、接口设计建议

生产者发送消息前，应先想清楚几个问题：

- Topic 是业务主题还是技术主题。
- Tag 是否能表达事件类型。
- Message Key 是否使用业务唯一 ID。
- 消费端是否能幂等。
- 失败后是否允许重试。
- 最终失败后如何进入补偿或人工处理。

消费者处理消息时，建议按这个顺序写：

1. 校验消息格式。
2. 按业务 Key 做幂等判断。
3. 查询当前业务状态。
4. 执行业务变更。
5. 记录处理结果。

## 十五、一句话总结

Spring Boot 让 RocketMQ 的接入变简单了，但并没有让消息系统的语义变简单。发送、重试、顺序、事务和幂等这些边界仍然要由业务代码负责表达清楚。

## 参考资料

- [Apache RocketMQ Spring](https://github.com/apache/rocketmq-spring)
- [RocketMQ Spring FAQ](https://github.com/apache/rocketmq-spring/wiki/FAQ)
- [Spring Tips: Apache RocketMQ](https://spring.io/blog/2020/02/25/spring-tips-apache-rocketmq/)
