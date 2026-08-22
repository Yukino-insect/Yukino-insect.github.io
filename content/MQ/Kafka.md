+++
date = '2026-08-22T16:00:00+08:00'
draft = false
title = 'Kafka 总览'
+++

Kafka 是一套以分布式日志为核心的消息与事件流平台。它既可以作为传统 MQ 使用，也常被用于日志采集、用户行为流、数据同步、实时计算和事件驱动架构。

如果用一句话概括 Kafka：

> Kafka 把消息按 Topic 和 Partition 组织成可持久化、可顺序追加、可重复读取的日志。

这点和很多传统消息队列的直觉不一样。Kafka 不只是“把消息推给消费者”，它更像是一组可以被多个消费者组独立读取的分布式日志文件。

## 文章拆分

Kafka 内容拆成几个模块：

- [Kafka 架构设计](/mq/kafka-架构设计/)：Broker、Topic、Partition、ConsumerGroup、复制和 KRaft。
- [Kafka Spring 集成使用](/mq/kafka-spring集成使用/)：Spring Kafka 依赖、生产者、消费者、序列化、错误处理。
- [Kafka 高级特性](/mq/kafka-高级特性/)：幂等生产者、事务、顺序、重试、死信、积压治理。

## 基本模型

Kafka 的基本链路如下：

```text
Producer -> Topic Partition -> Broker 磁盘日志
ConsumerGroup -> Consumer 拉取 Partition -> 处理消息 -> 提交 Offset
```

核心概念：

| 概念 | 含义 |
| --- | --- |
| `Topic` | 消息主题 |
| `Partition` | Topic 下的分区，Kafka 并发和顺序的基本单位 |
| `Record` | Kafka 中的一条消息，包含 key、value、headers、timestamp |
| `Broker` | Kafka 服务节点，存储分区日志 |
| `ConsumerGroup` | 消费者组，同组内实例分摊分区 |
| `Offset` | 分区内消息位置 |
| `Replica` | 分区副本，用于高可用 |
| `Controller` | 管理集群元数据、分区 leader 等状态的节点 |

## Kafka 的特点

Kafka 最重要的特点有几个：

- 高吞吐：顺序写磁盘、批量发送、零拷贝等机制让 Kafka 适合大流量数据。
- 分区并发：Topic 拆成多个 Partition，生产和消费都可以并行。
- 消息可回放：只要消息还在保留期内，消费者可以重置 offset 重新消费。
- 多消费者组独立消费：不同 ConsumerGroup 互不影响。
- 日志语义清晰：每个 Partition 内消息按 offset 有序。
- 生态完整：Kafka Connect、Kafka Streams、Flink、Spark 等系统都常与 Kafka 集成。

## Kafka 与 RocketMQ 的直观差异

| 维度 | Kafka | RocketMQ |
| --- | --- | --- |
| 核心定位 | 分布式日志、事件流平台 | 业务消息系统 |
| 路由中心 | Broker/Controller 管理元数据，现代版本使用 KRaft | NameServer 管路由 |
| 消息组织 | Topic -> Partition -> Log | Topic -> MessageQueue -> CommitLog/ConsumeQueue |
| 延迟消息 | 原生不以延迟等级为核心能力 | 常见内置延迟消息能力 |
| 事务语义 | Kafka 内部读写和 offset 的事务一致 | 半消息 + 本地事务回查 |
| 消费方式 | Consumer 主动 poll | Push 模式本质也是长轮询 |
| 常见场景 | 日志、流处理、数据管道、事件流 | 业务解耦、事务消息、订单状态流转 |

这不是谁更高级的问题。工具没有自尊心，只有适用边界。

## 什么时候适合用 Kafka

适合：

- 日志采集和实时分析。
- 用户行为事件流。
- 多系统数据同步。
- 订单、支付、风控等事件流转。
- Flink、Spark、Kafka Streams 等实时计算输入源。
- 需要消息回放和多消费者组独立读取的场景。

不适合：

- 复杂延迟消息作为核心需求，却不想引入额外设计。
- 希望 MQ 帮你处理所有业务补偿。
- 单条消息极低延迟但吞吐很小的简单场景。
- 没有幂等设计，却要求绝对不重复消费。

## 学习顺序

建议按下面顺序理解 Kafka：

1. Topic、Partition、Offset。
2. Producer 如何按 key 选择 Partition。
3. ConsumerGroup 如何分配 Partition。
4. Offset 提交和重复消费。
5. 副本、Leader、ISR、高水位。
6. 幂等生产者和事务。
7. Spring Kafka 的监听器、错误处理和死信主题。

## 一句话总结

Kafka 的本质是一套分布式、可持久化、可回放的日志系统。把它只看成“消息队列”，也不是错，只是会错过它真正锋利的地方。

## 参考资料

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Kafka：Concepts and Terms](https://kafka.apache.org/documentation/#intro_concepts_and_terms)
- [Spring for Apache Kafka Reference](https://docs.spring.io/spring-kafka/reference/)
