+++
date = '2026-08-22T16:12:00+08:00'
draft = false
title = 'Kafka Spring 集成使用'
+++

Spring Boot 集成 Kafka 通常使用 `spring-kafka`。它提供了 `KafkaTemplate`、`@KafkaListener`、监听容器、错误处理器、事务管理等能力。

实际项目中，如果使用 Spring Boot，优先让 Boot 的依赖管理决定 `spring-kafka` 版本。自己强行指定版本也不是不可以，只是要同时承担兼容性问题。既然可以不自找麻烦，就不必表现得那么勤奋。

## 一、添加依赖

Spring Boot 项目：

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
</dependency>
```

如果不是 Spring Boot 管理依赖，需要显式指定版本：

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
    <version>4.0.0</version>
</dependency>
```

版本请以项目使用的 Spring Boot 版本和公司依赖规范为准。

## 二、基础配置

`application.yml`：

```yaml
spring:
  kafka:
    bootstrap-servers: 127.0.0.1:9092
    producer:
      acks: all
      retries: 3
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
      properties:
        enable.idempotence: true
    consumer:
      group-id: order-consumer-group
      auto-offset-reset: earliest
      enable-auto-commit: false
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      properties:
        spring.json.trusted.packages: "com.example.demo.message"
    listener:
      ack-mode: manual
```

几个关键配置：

| 配置 | 含义 |
| --- | --- |
| `bootstrap-servers` | Kafka Broker 地址 |
| `acks=all` | 等待所有 ISR 副本确认 |
| `enable.idempotence=true` | 开启幂等生产者 |
| `enable-auto-commit=false` | 关闭自动提交 offset |
| `auto-offset-reset` | 没有初始 offset 时从哪里开始消费 |
| `ack-mode=manual` | 由业务处理成功后手动确认 |

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

Kafka Record 天然包含 key 和 value。业务事件建议把业务唯一 ID 放在 key 里，比如 `orderId`。这样相同订单的消息会进入同一个 Partition，便于维持订单维度的顺序。

## 四、生产者

```java
@Service
public class OrderEventProducer {

    private final KafkaTemplate<String, OrderPaidEvent> kafkaTemplate;

    public OrderEventProducer(KafkaTemplate<String, OrderPaidEvent> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public CompletableFuture<SendResult<String, OrderPaidEvent>> sendOrderPaid(OrderPaidEvent event) {
        ProducerRecord<String, OrderPaidEvent> record = new ProducerRecord<>(
            "order-topic",
            event.getOrderId(),
            event
        );
        record.headers().add("eventType", "order-paid".getBytes(StandardCharsets.UTF_8));

        return kafkaTemplate.send(record);
    }
}
```

`KafkaTemplate#send` 返回 `CompletableFuture`，可以处理成功和失败：

```java
producer.sendOrderPaid(event)
    .whenComplete((result, ex) -> {
        if (ex != null) {
            System.err.println("send failed: " + ex.getMessage());
            return;
        }
        RecordMetadata metadata = result.getRecordMetadata();
        System.out.println("send success: " + metadata.topic() + "-" + metadata.partition());
    });
```

关键业务不要忽略发送失败。否则系统会很安静，安静到你上线后才知道消息没有出去。

## 五、消费者

```java
@Component
public class OrderPaidConsumer {

    private final InventoryService inventoryService;

    public OrderPaidConsumer(InventoryService inventoryService) {
        this.inventoryService = inventoryService;
    }

    @KafkaListener(
        topics = "order-topic",
        groupId = "inventory-order-group"
    )
    public void onMessage(
        ConsumerRecord<String, OrderPaidEvent> record,
        Acknowledgment acknowledgment
    ) {
        OrderPaidEvent event = record.value();
        inventoryService.deduct(event.getOrderId());
        acknowledgment.acknowledge();
    }
}
```

手动 ack 的语义更清楚：业务处理成功后再提交 offset。如果处理过程中抛异常，不确认 offset，消息后续会按错误处理策略重试。

## 六、监听指定分区

一般不建议业务代码固定消费某个分区，因为这会削弱 ConsumerGroup 的自动负载均衡能力。但排查问题或特殊任务时可以指定：

```java
@KafkaListener(
    topicPartitions = @TopicPartition(
        topic = "order-topic",
        partitions = {"0", "1"}
    ),
    groupId = "debug-order-group"
)
public void onPartitionMessage(ConsumerRecord<String, OrderPaidEvent> record) {
    System.out.println(record.partition() + ":" + record.offset());
}
```

## 七、批量消费

批量消费可以提升吞吐，但业务逻辑要能处理部分失败。

配置：

```yaml
spring:
  kafka:
    listener:
      type: batch
      ack-mode: manual
    consumer:
      max-poll-records: 100
```

监听器：

```java
@KafkaListener(topics = "order-topic", groupId = "batch-order-group")
public void onBatchMessage(
    List<ConsumerRecord<String, OrderPaidEvent>> records,
    Acknowledgment acknowledgment
) {
    for (ConsumerRecord<String, OrderPaidEvent> record : records) {
        handle(record.value());
    }
    acknowledgment.acknowledge();
}
```

批量消费中，如果第 80 条失败，前 79 条是否已经成功、能否重复处理，必须由幂等设计保证。

## 八、JSON 序列化

Spring Kafka 提供 `JsonSerializer` 和 `JsonDeserializer`。为了反序列化安全，需要配置可信包：

```yaml
spring:
  kafka:
    consumer:
      properties:
        spring.json.trusted.packages: "com.example.demo.message"
```

如果生产者和消费者不是同一个 Java 工程，建议约定稳定的 JSON Schema、Avro、Protobuf 或其他跨语言协议，而不是依赖 Java 类名。

## 九、错误处理

Spring Kafka 可以通过 `DefaultErrorHandler` 配置重试和死信主题。

```java
@Configuration
public class KafkaConsumerConfig {

    @Bean
    public DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> kafkaTemplate) {
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(
            kafkaTemplate,
            (record, ex) -> new TopicPartition(record.topic() + ".DLT", record.partition())
        );

        FixedBackOff backOff = new FixedBackOff(1000L, 3L);
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
```

含义：

- 消费失败后间隔 1 秒重试。
- 最多重试 3 次。
- 仍然失败后发送到 `原Topic.DLT`。
- DLT 使用原分区，便于保留排查线索。

创建 DLT 主题时，分区数最好不少于原 Topic，否则指定原分区可能失败。

## 十、死信主题消费者

```java
@Component
public class OrderDltConsumer {

    @KafkaListener(topics = "order-topic.DLT", groupId = "order-dlt-handler-group")
    public void onDlt(ConsumerRecord<String, OrderPaidEvent> record) {
        System.out.println("dlt key: " + record.key());
        System.out.println("dlt offset: " + record.offset());
    }
}
```

死信主题不是垃圾桶。它应该连接告警、排查、修复和重新投递流程。

## 十一、事务发送

如果只需要在 Kafka 内保证多条消息作为一个事务提交，可以启用生产者事务：

```yaml
spring:
  kafka:
    producer:
      transaction-id-prefix: order-tx-
```

使用：

```java
@Service
public class OrderTxProducer {

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public OrderTxProducer(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void sendInTransaction(OrderPaidEvent event) {
        kafkaTemplate.executeInTransaction(operations -> {
            operations.send("order-topic", event.getOrderId(), event);
            operations.send("order-audit-topic", event.getOrderId(), event);
            return true;
        });
    }
}
```

这能保证两个 Kafka 发送要么一起提交，要么一起回滚。但它不自动把数据库事务也纳入 Kafka 事务。外部数据库一致性需要 Outbox、本地消息表或业务补偿设计。

## 十二、常见配置建议

生产者：

```yaml
spring:
  kafka:
    producer:
      acks: all
      retries: 3
      properties:
        enable.idempotence: true
        linger.ms: 5
        compression.type: lz4
```

消费者：

```yaml
spring:
  kafka:
    consumer:
      enable-auto-commit: false
      max-poll-records: 100
      properties:
        max.poll.interval.ms: 300000
        session.timeout.ms: 45000
    listener:
      ack-mode: manual
```

注意：

- `max.poll.interval.ms` 要大于一次批量处理的最长时间。
- 消费逻辑不要在监听线程里做无限等待。
- 业务处理很慢时，应考虑线程池、批量处理或拆分 Topic。

## 十三、一句话总结

Spring Kafka 的 API 很简单，但真正重要的是 offset 提交、错误处理、死信主题和幂等。能发能收只是入门，能失败得有秩序才算开始像工程。

## 参考资料

- [Spring for Apache Kafka Reference](https://docs.spring.io/spring-kafka/reference/)
- [Spring Kafka：Receiving Messages](https://docs.spring.io/spring-kafka/reference/kafka/receiving-messages/listener-annotation.html)
- [Spring Kafka：Handling Exceptions](https://docs.spring.io/spring-kafka/reference/kafka/annotation-error-handling.html)
- [Spring Kafka：Transactions](https://docs.spring.io/spring-kafka/reference/kafka/transactions.html)
