+++
date = '2025-10-04T18:27:52+08:00'
draft = false
title = 'RocketMQ 总览'
+++

RocketMQ 是一套面向业务异步解耦、削峰填谷、顺序事件和最终一致性的分布式消息系统。它的核心模型并不复杂：生产者把消息发送到 Topic，Broker 负责存储和投递，消费者按 ConsumerGroup 订阅 Topic 并处理消息。

真正需要认真理解的是它在工程层面的几个边界：

- RocketMQ 不是“远程方法调用”，发送成功只代表消息进入 Broker，不代表下游业务已经完成。
- RocketMQ 默认是至少一次投递，业务必须按消息 Key 做幂等。
- 顺序消息只能保证同一个队列内有序，不是天然全局有序。
- 事务消息解决的是“本地事务与消息发送”的最终一致，不负责保证消费者业务一定成功。
- 重试和死信队列是兜底机制，不应该被当作正常业务分支。

## 文章拆分

RocketMQ 的内容已经拆成几个模块。直接把所有概念塞在一篇里当然也能读，只是读者会比较辛苦，而辛苦通常不是学习本身的必要条件。

- [RocketMQ 架构设计](/mq/rocketmq-架构设计/)：核心组件、路由发现、存储模型、消费负载均衡。
- [RocketMQ Spring 集成使用](/mq/rocketmq-spring集成使用/)：Spring Boot 依赖、生产者、消费者、Tag、顺序与延迟消息。
- [RocketMQ 高级特性](/mq/rocketmq-高级特性/)：事务二阶段、重试、死信队列、幂等、顺序消息边界。

如果只是快速使用，可以先读 Spring 集成；如果要排查线上问题，架构设计和高级特性更重要。

## 基本模型

RocketMQ 的基本链路如下：

```text
Producer -> NameServer 查询路由 -> Broker 写入消息
Consumer -> NameServer 查询路由 -> Broker 拉取消息 -> 执行业务 -> 提交消费结果
```

其中 `NameServer` 不参与消息传输，只维护 Topic 到 Broker 的路由信息；`Broker` 才是实际存储消息、维护队列、处理消费进度和重试的节点。

## 核心概念

| 概念 | 作用 | 需要注意 |
| --- | --- | --- |
| `Topic` | 消息的一类业务主题 | 不同业务、不同消息类型建议拆 Topic |
| `Tag` | Topic 内的二级过滤标签 | 适合同一业务下的子类型过滤 |
| `MessageQueue` | Topic 下的队列分片 | 顺序消息的顺序边界就在队列内 |
| `ProducerGroup` | 生产者组 | 事务消息回查会依赖生产者组内实例 |
| `ConsumerGroup` | 消费者组 | 同组内实例分摊消息，不同组各自消费一份 |
| `Offset` | 消费进度 | 集群消费进度通常由 Broker 管理 |
| `DLQ` | 死信队列 | 消费多次失败后的异常消息归宿 |

## 发送方式

RocketMQ 常见发送方式有三种：

- 同步发送：等待 Broker 返回发送结果，可靠性更好，适合订单、支付等关键链路。
- 异步发送：注册回调，不阻塞主流程，适合对响应时间敏感但仍关心结果的场景。
- 单向发送：只发送不等待结果，吞吐高，但存在丢失风险，适合日志、埋点等可容忍丢失的场景。

示例：

```java
Message message = new Message(
    "order-topic",
    "paid",
    "orderId-10001",
    "{\"orderId\":\"10001\"}".getBytes(StandardCharsets.UTF_8)
);

SendResult result = producer.send(message);
System.out.println(result.getSendStatus());
```

## 消费方式

RocketMQ 客户端看起来支持 Push 和 Pull 两类消费方式，但 Push 本质上仍是客户端长轮询拉取。框架帮你维护拉取、缓存、回调、重试和位点提交，所以大多数业务使用 Push 模式即可。

消费模型主要有两种：

- 集群消费：同一 ConsumerGroup 下多个实例分摊 Topic 的队列，是线上最常见模式。
- 广播消费：同一 ConsumerGroup 下每个实例都消费全量消息，适合配置刷新、本地缓存刷新等少数场景。

## 什么时候适合用 RocketMQ

适合：

- 订单、库存、支付、物流等业务事件流转。
- 瞬时流量高峰需要削峰填谷。
- 本地事务完成后，需要异步通知多个下游系统。
- 需要事务消息、延迟消息、顺序消息这类业务消息能力。

不适合：

- 需要同步返回结果的调用链。那是 RPC 或 HTTP 的工作。
- 不能接受重复消费、又没有幂等设计的业务。
- 把消息队列当数据库长期查询历史数据。
- 用 MQ 隐藏本该被治理的强一致事务问题。

## 学习顺序

推荐按下面的顺序读：

1. 先理解 Topic、Tag、Queue、ConsumerGroup。
2. 再看生产者发送和消费者订阅。
3. 然后理解队列分片、Rebalance 和 Offset。
4. 最后看事务消息、重试、死信队列、幂等和顺序消息。

## 参考资料

- [Apache RocketMQ：What is RocketMQ](https://rocketmq.apache.org/docs/4.x/introduction/02whatis/)
- [Apache RocketMQ：Domain Model](https://rocketmq.apache.org/docs/domainModel/01main/)
- [Apache RocketMQ Spring](https://github.com/apache/rocketmq-spring)
