+++
date = '2026-08-22T15:30:00+08:00'
draft = false
title = 'RocketMQ 架构设计'
+++

理解 RocketMQ，最好不要从 API 开始。API 只是入口，真正决定线上行为的是它的路由、队列、存储、消费进度和重平衡机制。

RocketMQ 的核心架构可以先记成一句话：

> NameServer 管路由，Broker 管存储和投递，Producer 写消息，Consumer 拉消息。

## 一、整体架构

RocketMQ 的主要组件如下：

```text
              +----------------+
              |   NameServer   |
              +----------------+
                ^            ^
       查询路由 |            | 注册路由和心跳
                |            |
+----------+  发送消息  +----------+  拉取消息  +----------+
| Producer | --------> |  Broker  | <-------- | Consumer |
+----------+           +----------+           +----------+
```

一个完整流程通常是：

1. Broker 启动后向所有 NameServer 注册自己的地址、Topic、Queue 等路由信息。
2. Producer 启动后从 NameServer 获取 Topic 的路由。
3. Producer 根据队列选择策略，把消息发送到某个 Broker 的某个 MessageQueue。
4. Consumer 从 NameServer 获取订阅 Topic 的路由。
5. Consumer 与 Broker 建立连接，从自己被分配到的队列拉取消息。
6. 消费成功后提交消费结果，Broker 更新消费进度。

NameServer 不参与消息读写，这让它足够轻量。它像一份路由通讯录，告诉客户端“某个 Topic 目前在哪里”。

## 二、NameServer

NameServer 是路由注册中心，保存 Topic、Broker、Queue 之间的映射关系。

它有几个特点：

- 无状态：NameServer 节点之间不互相同步。
- 可水平扩展：多个 NameServer 保存完整路由信息。
- 不参与消息传输：Producer 和 Consumer 拿到路由后直接访问 Broker。
- 依赖 Broker 心跳：Broker 周期性向 NameServer 上报自身状态。

为什么 NameServer 节点之间不通信也能工作？

因为每个 Broker 会向所有 NameServer 注册信息，客户端也会配置多个 NameServer 地址。只要客户端能连到其中一个可用 NameServer，就能查询到完整路由。

## 三、Broker

Broker 是 RocketMQ 的核心节点，主要负责：

- 接收 Producer 发送的消息。
- 将消息写入磁盘。
- 维护 Topic 下的 MessageQueue。
- 响应 Consumer 的拉取请求。
- 管理消费进度、消费重试、死信队列。
- 在主从部署下承担数据复制和高可用能力。

Broker 常见部署形态是 Master-Slave：

- Master：负责读写请求。
- Slave：从 Master 复制数据，用于容灾和读扩展。

在 Broker 配置中，`brokerId = 0` 通常表示 Master，非 0 表示 Slave。生产环境不要只部署单 Broker，否则 NameServer 再怎么轻量，也挡不住存储节点本身的单点风险。

## 四、Topic 与 MessageQueue

Topic 是业务维度的消息主题，MessageQueue 是 Topic 下的物理队列分片。

```text
Topic: order-topic
  - queue 0 on broker-a
  - queue 1 on broker-a
  - queue 2 on broker-b
  - queue 3 on broker-b
```

Queue 的作用有两个：

- 提升并发：多个队列可以分布在多个 Broker 上。
- 提供顺序边界：同一个队列内的消息天然按 offset 有序。

所以 RocketMQ 的顺序消息不是“整个 Topic 全局有序”，而是“同一个 MessageQueue 内有序”。如果要让同一个订单的状态消息有序，就要让相同订单号的消息进入同一个队列。

示例：

```java
producer.send(message, (mqs, msg, arg) -> {
    String orderId = (String) arg;
    int index = Math.abs(orderId.hashCode()) % mqs.size();
    return mqs.get(index);
}, orderId);
```

## 五、Producer 路由与队列选择

Producer 发送消息前会先拿到 Topic 的路由信息，然后选择一个队列发送。

普通消息默认通常使用轮询策略，让消息大致均匀分布到多个队列。顺序消息则需要自定义队列选择策略，让同一个业务 Key 固定到同一个队列。

发送方式可以分为：

| 方式 | 特点 | 适用场景 |
| --- | --- | --- |
| 同步发送 | 等待发送结果 | 订单、支付、积分等关键消息 |
| 异步发送 | 回调接收结果 | 主流程不想阻塞但仍关心成功失败 |
| 单向发送 | 不等待结果 | 日志、监控、埋点等可容忍丢失的消息 |

同步和异步发送失败时可以重试；单向发送没有可靠的失败反馈，不要用于关键业务。

## 六、ConsumerGroup 与消费模型

ConsumerGroup 是消费负载均衡的基本单位。

同一个 ConsumerGroup 内的多个实例会分摊 Topic 的队列：

```text
order-topic: queue0 queue1 queue2 queue3

consumer-a -> queue0 queue1
consumer-b -> queue2 queue3
```

不同 ConsumerGroup 之间互不影响。比如订单消息可以同时被库存系统和积分系统消费：

```text
order-topic
  -> inventory-consumer-group
  -> points-consumer-group
```

这两个组各自维护消费进度，各自消费一份消息。

### 集群消费

集群消费是默认也是最常见的模式。同一 ConsumerGroup 内，每条消息只会被其中一个消费者实例处理。

适合：

- 订单处理。
- 库存扣减。
- 积分发放。
- 需要水平扩展吞吐的业务。

### 广播消费

广播消费下，同一 ConsumerGroup 内每个消费者实例都会收到全量消息。

适合：

- 本地缓存刷新。
- 配置变更通知。
- 每个节点都必须执行一次的任务。

广播消费不适合作为普通业务消费模式，因为它没有“分摊压力”的效果。

## 七、Rebalance

Rebalance 是 ConsumerGroup 内队列重新分配的过程。

触发场景包括：

- 消费者实例上线。
- 消费者实例下线。
- Topic 队列数量变化。
- Broker 变化。

Rebalance 让集群消费具备横向扩容能力，但它也会带来两个副作用：

- 短时间内部分队列暂停消费。
- 如果旧消费者处理成功但 offset 尚未提交，新消费者接手后可能重复消费。

所以消息消费必须做幂等。这里没有什么浪漫可言，线上系统会用重复投递提醒你：侥幸心理并不是架构设计。

## 八、Offset

Offset 是队列内的消费位置。

RocketMQ 控制台里常见的几个指标可以这样理解：

| 指标 | 含义 |
| --- | --- |
| Broker offset | 队列当前最大写入位置 |
| Consumer offset | 消费者组已经消费到的位置 |
| Diff | 未消费积压量 |

如果 `Diff` 持续升高，说明消费速度小于生产速度。常见原因有：

- 消费者实例太少。
- 单条消息处理太慢。
- 消费者不断失败重试。
- 下游数据库或接口成为瓶颈。

处理积压时，不要只盯着 MQ。MQ 很多时候只是把下游处理能力不足暴露出来。

## 九、存储模型

RocketMQ 的存储可以简化理解为两层：

- CommitLog：顺序写入所有消息的物理文件。
- ConsumeQueue：按 Topic 和 Queue 建立的逻辑索引。

消息先顺序写入 CommitLog，再为每个 Topic 的队列生成 ConsumeQueue 索引。Consumer 拉取时主要按 ConsumeQueue 定位消息，再到 CommitLog 读取真实消息内容。

这种设计的好处是：

- 写入是顺序写，吞吐高。
- 同一份消息数据可以被多个 ConsumerGroup 消费，不需要重复存储。
- Topic/Queue 维度的消费查询可以通过索引加速。

## 十、Pull 与 Push

RocketMQ 的 Push 模式本质仍然是 Consumer 长轮询 Broker。

它的过程大致是：

```text
Consumer 发起拉取请求
  -> Broker 有消息则立即返回
  -> Broker 暂时无消息则挂起请求
  -> 有新消息或超时后返回
  -> Consumer 回调业务监听器
```

所以 Push 更准确地说是“框架帮你持续拉取并回调”。它降低了使用成本，但并没有改变 Broker 被动响应的事实。

## 十一、架构排查清单

线上排查 RocketMQ 问题时，可以按下面顺序看：

1. NameServer 地址是否正确，客户端是否能查询到 Topic 路由。
2. Topic 是否已创建，队列数是否符合预期。
3. Producer 是否发送成功，是否有超时、重试、无可用 Broker。
4. ConsumerGroup 是否写错，订阅 Topic 和 Tag 是否一致。
5. 消费模式是集群还是广播。
6. Consumer offset 是否推进。
7. Diff 是否持续升高。
8. 是否发生大量 Rebalance。
9. 是否有消息进入重试队列或死信队列。
10. 消费逻辑是否幂等。

## 十二、一句话总结

RocketMQ 的架构重点不是“会不会发消息”，而是能否理解消息从 Producer 到 Broker、再到 Consumer 的每个状态边界。边界清楚了，重试、重复消费、积压、顺序和事务消息才不会显得像玄学。

## 参考资料

- [Apache RocketMQ：What is RocketMQ](https://rocketmq.apache.org/docs/4.x/introduction/02whatis/)
- [Apache RocketMQ：Domain Model](https://rocketmq.apache.org/docs/domainModel/01main/)
