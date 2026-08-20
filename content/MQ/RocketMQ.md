+++
date = '2025-10-04T18:27:52+08:00'
draft = false
title = 'RocketMQ'
+++

### 核心组件

#### Producer

生产者，发送消息到 Broker。支持同步/异步/单向，三种发送模式

并且内置失败重试，默认重试两次

#### Consumer

消息消费者，从 Broker 拉取消息并处理

支持两种消费模式，由 Broker Push（主动推送）或者是 消费者 Pull（拉取），实际内部统一为长轮询拉取

**两种消费模式**：

- **Push 模式**（伪推）：Broker 端维护长轮询，检测到消息即推送。

- **Pull 模式**：Consumer 主动轮询 Broker 拉取消息。

**消费策略**：

- **集群消费（Clustering）**：多实例分摊消费，提高吞吐。

- **广播消费（Broadcasting）**：每个实例都收到全量消息。

**负载均衡机制**：

- 消费者从 NameServer 获取队列信息。
- 基于 ConsumerGroup 做 Rebalance，动态分配队列。

**消费确认**：

- 消费成功返回 `CONSUME_SUCCESS`
- 消费失败，将重试或进入死信队列（DLQ）。

#### ProducerGroup

一组功能相同的 Producer 实例，共享同一个 Group 名称。同一组 Producer 必须发送相同类型的消息（同一业务逻辑）。Group 名必须唯一

#### ConsumerGroup

一组消费同一 Topic 的消费者实例。同一 Group 下的消费者订阅的 Topic 和 Tag 必须一致。广播模式下，每个消费者实例都会消费到全量消息

#### Broker

消息存储与转发中心。存储消息，维护消费队列，接收 Producer 发来的消息推送给 Consumer

Broker 支持主从架构，可以实现高可用和主从分离。Broker 的 Master 主要负责读写数据，Slave 节点负责拷贝 Master 节点的数据做保存，防止主节点挂掉导致数据丢失

#### NameServer

路由中心，保存 Topic 到 Broker 的映射关系

它是轻量级、无状态的。可以水平扩展。NameServer 可以形成集群，但每一个 NameServer 都保存着同样的数据

Broker 启动时会主动向其注册相关信息。Producer/Consumer 会向 NameServer 查询路由信息

这样做实现了路由和储存的解耦，避免 Broker 既存消息又做路由导致单点问题。

NameServer 不参与消息传输，避免性能瓶颈。

它类似于 DNS 的作用，让客户端能快速找到 Broker。

#### Topic

主题，消息的逻辑分类，Producer 按 Topic 发送，Consumer 按 Topic 订阅

每一个主题下会有多个队列，不同队列分布在不同的 Borker中。Producer 会把消息路由到某个队列

#### Tag

附属于 Topic 中的二级分类，一个 Topic 可以包含多个 Tag，例如

```markdown
Topic: OrderTopic
 ├─ TagA：订单创建
 ├─ TagB：订单支付
 ├─ TagC：订单取消
```

Tag 用在 Consumer 在订阅消息时对消息过滤。它可以指定 Tag，只接收某些 Tag 消息

Tag 可以实现逻辑分类，在同一个 Topic 中可以对消息做进一步分类，方便管理消息

#### Message Queue

消息队列，Topic 下的分区，Producer 写入时选择队列，Consumer 消费时分配队列

这样设计便于负载均衡和扩展

#### 分片

Topic 的分区策略，用于控制消息分布。

Producer 通过 **MessageQueueSelector** 自定义分配策略，例如根据订单号取模。

Broker 按 Queue 维度存储与管理数据

```java
producer.send(new Message("OrderTopic", "TagA", "OrderID-123".getBytes()),
    (mqs, msg, arg) -> mqs.get(Math.abs(arg.hashCode()) % mqs.size()), orderId);
```

保证相同业务 Key 的消息进入同一个分区。

#### RocketMQ的工作流程：

- 启动NameServer，NameServer启动后开始监听端口，等待Broker、Producer、Consumer连接。
- 启动Broker时，Broker会与所有的NameServer建立并保持长连接，然后每 30 秒向NameServer定时发送心跳包。
- 发送消息前，可以先创建Topic，创建Topic时需要指定该Topic要存储在哪些Broker上，当然，在创建Topic时也会将Topic与Broker的关系写入到NameServer中。不过，这步是可选的，也可以在发送消息时自动创建Topic。
- Producer发送消息，启动时先跟NameServer集群中的其中一台建立长连接，并从NameServer中获取路由信息，即当前发送的Topic消息的Queue与Broker的地址（IP+Port）的映射关系。然后根据算法策略从队选择一个Queue，与队列所在的Broker建立长连接从而向Broker发消息。当然，在获取到路由信息后，Producer会首先将路由信息缓存到本地，再每 30 秒从NameServer更新一次路由信息。
- Consumer跟Producer类似，跟其中一台NameServer建立长连接，获取其所订阅Topic的路由信息，然后根据算法策略从路由信息中获取到其所要消费的Queue，然后直接跟Broker建立长连接，开始消费其中的消息。Consumer在获取到路由信息后，同样也会每 30 秒从NameServer更新一次路由信息。不过不同于Producer的是，Consumer还会向Broker发送心跳，以确保Broker的存活状态。

接下来看一下如何使用 RocketMQ

首先要引入 maven 依赖

```xml
<dependency>
    <groupId>org.apache.rocketmq</groupId>
    <artifactId>rocketmq-client</artifactId>
    <version>4.9.2</version>
</dependency>
```

定义一个生产者

```java
public class RocketMQDemoTest {
    @Test
    public void test01() throws Exception{
        // 1.创建消息生产者 producer，并指定生产者组名
        DefaultMQProducer producer = new DefaultMQProducer("test-group");
        // 2.指定 Namesrv 地址
        producer.setNamesrvAddr("192.168.10.138:9876");
        // 3.启动生产者
        producer.start();
        // 4.创建消息
        for (int i = 0; i <10; i++) {
            // 第一个参数：主题的名字
            // 第二个参数：消息内容
            Message msg = new Message("TopicTest", ("Hello RocketMQ "+ i).getBytes());
            // 5.发送消息
            SendResult send = producer.send(msg);
            System.out.println(send);
        }
        //6.关闭实例
        producer.shutdown();
    }
}
```

定义一个消费者

```java
@Test
public void testConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("consumer-group");
    // 设置 NameServer 地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费 参数1：主题名称  参数2：订阅表达式 * 表示没有过滤参数 表示订阅这个主题的任何消息
    consumer.subscribe("TopicTest", "*");
    // 注册一个消费监听 MessageListenerConcurrently 是多线程消费，默认20个线程
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            String message = new String(msgs.get(0).getBody());
            System.out.println(Thread.currentThread().getName() + "----"+ message);
            // 返回消费的状态 如果是 CONSUME_SUCCESS 则成功，若为 RECONSUME_LATER 则该条消息会被重回队列，重新被投递
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    // 这个 start 一定要写在 registerMessageListener 下面
    consumer.start();
    System.in.read();
}
```

分别运行之后，消息就会被投送到 Topic 中的 4 个队列中。投送的过程遵循 **轮询策略**，每个队列拥有的消息大致均匀

消费者在消费的时候，同组的消费者只能消费同一个 Topic 的消息，不能出现一个消费者组的消费者消费不同 Topic

> 这里讲一下两种消费模式和两种消费策略
>
> ##### 消费模式
>
> ##### Push 模式（“伪推”，推荐）
>
> **本质**：客户端维持长轮询向 Broker 拉取；一有消息即回调监听器。
>  **特点**
>
> - 业务是“消息驱动”的：实现监听器即可（并发或有序两种监听）。
> - 自动做拉取、流控、重试与位点提交，开发成本最低。
> - 典型监听器：
>   - `MessageListenerConcurrently`：并发消费（吞吐高，**不保证顺序**）
>   - `MessageListenerOrderly`：队列级单线程消费（**保证分区/队列内顺序**）
>
> **常用参数**
>
> - `consumeThreadMin/Max`：消费线程池大小
> - `consumeMessageBatchMaxSize`：一次回调的消息条数（默认 1）
> - `pullInterval`：两次拉取间隔
> - `consumeTimeout`：单条消息处理超时（默认 15 分钟）
>
> **示例（并发）**
>
> ```java
> DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("demo_consumer");
> consumer.setNamesrvAddr("127.0.0.1:9876");
> consumer.subscribe("OrderTopic", "TagA || TagB");
> consumer.registerMessageListener((MessageListenerConcurrently) (msgs, ctx) -> {
>     for (MessageExt m : msgs) {/* 处理业务 */ }
>     return ConsumeConcurrentlyStatus.CONSUME_SUCCESS; // or RECONSUME_LATER
> });
> consumer.start();
> ```
>
> **示例（顺序）**
>
> ```java
> consumer.registerMessageListener((MessageListenerOrderly) (msgs, ctx) -> {
>     for (MessageExt m : msgs) {/* 串行处理同队列消息 */ }
>     return ConsumeOrderlyStatus.SUCCESS; // or SUSPEND_CURRENT_QUEUE_A_MOMENT
> });
> ```
>
> ##### Pull 模式（手动拉取）
>
> **本质**：应用自主控制“拉取—处理—提交位点”的节奏。
> **适用**：需要**自定义拉取节拍、二次过滤、按需回溯**等专业场景。
> **代价**：需自己维护位点、流控、重试。
>
> **关键点**
>
> - 选择要拉取的 `MessageQueue`
> - 调 `pull()`/`pullBlockIfNotFound()` 拉取
> - 业务处理完**手动更新消费进度（offset）**
>
> **示例（简化）**
>
> ```java
> DefaultMQPullConsumer c = new DefaultMQPullConsumer("demo_pull");
> c.setNamesrvAddr("127.0.0.1:9876");
> c.start();
> Set<MessageQueue> mqs = c.fetchSubscribeMessageQueues("OrderTopic");
> for (MessageQueue q : mqs) {
>   long offset = c.fetchConsumeOffset(q, true);
>   PullResult r = c.pull(q, "TagA || TagB", offset, 32);
>   if (r.getMsgFoundList() != null) for (MessageExt m : r.getMsgFoundList()) {/* 处理 */}
>   c.updateConsumeOffset(q, r.getNextBeginOffset());
> }
> ```
>
> ##### 消费策略
>
> ##### 集群消费（Clustering，默认）
>
> **语义**：同一 ConsumerGroup 里的多个实例**分摊**同一 Topic 的消息（每条消息只被其中一个实例消费）。
> **负载均衡（Rebalance）**
>
> - 客户端周期性取回 Topic 下所有 `MessageQueue` 列表
> - 以 Group 为单位进行**队列分配**（常见算法）：
>   - `AllocateMessageQueueAveragely`（平均分配，默认）
>   - `…ByCircle`（轮转分配）
>   - `…ConsistentHash`（一致性哈希，按 key 固定到实例）
>   - `…MachineRoomNearby`（机房就近）
>
> **重试 / DLQ**
>
> - 失败（抛异常/返回重试）-> Broker 按退避策略重投（默认最多 16 次）
> - 超过阈值进入 **死信队列**：`%DLQ%<consumerGroup>`
> - **位点存储**：**Broker 端**统一维护（`CONSUMER_OFFSET`）
>
> **适用**
>
> - 线上绝大多数业务：高吞吐、可水平扩展、可重试与 DLQ
>
> ##### 广播消费（Broadcasting）
>
> **语义**：同一 Group 的**每个实例都消费全量消息**（广播分发）。
> **特性**
>
> - **无重试 / 无 DLQ**（广播下不支持重投；失败仅打印日志）
> - **位点存储**：**本地文件**（各实例各自维护）
> - **负载均衡**：无（每实例订阅 Topic 下所有队列）
>
> 在广播消费（Broadcasting）模式下，同一 ConsumerGroup 下的每个消费者实例都会消费所有消息

我们在 RocketMQ 控制台面板上可以看到以下概念

```markdown
|代理者位点|消费者位点|差值|
------------------------
|    3    |    2   |  1 |
```

这是什么意思？

其实代理者位点就是生产者实际生产消息投递到队列的位置(索引)，消费者位点就是消费者实际消费队列里面消息的位置(索引)。差值就是代理者位点减去消费者位点的差值，通过差值可以判定未被消费的消息数量

上面只是以发送 **同步消息** 做一个例子，它在发送之后会有返回值，也就是 MQ 服务器接收到消息后返回的确认消息。这种方式是非常安全的，但是性能上却相对较差。接下来看以下另外的一些方式

#### 异步发送

异步消息通常用在对响应时间敏感的业务场景，即发送端不能容忍长时间地等待 Broker 的响应。发送完以后会有一个异步消息通知。

生产者

```java
/**
  * 发送异步消息
  * @throws Exception
  */
@Test
public void testSendAsyncMessage() throws Exception{
    // 1.创建消息生产者producer，并指定生产者组名
    DefaultMQProducer producer = new DefaultMQProducer("async-group");
    // 2.指定Namesrv地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 3.启动生产者
    producer.start();
    // 准备一个消息
    Message message = new Message("asyncTopic","这是一个异步消息".getBytes());
    producer.send(message, new SendCallback() {
        //消息发送成功触发的回调方法
        public void onSuccess(SendResult sendResult) {
            System.out.println("消息发送成功");
        }

        //消息发送失败触发的回调方法
        public void onException(Throwable throwable) {
            System.out.println("消息发送失败:" + throwable.getMessage());
        }
    });

    System.out.println("主线程先执行");
    System.in.read();
    //6.关闭实例
    producer.shutdown();
}
```

消息消费者

```java
/**
  * 异步消息消费者
  * @throws Exception
  */
@Test
public void testAsyncConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("consumer-group");
    // 设置 NameServer 地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费 * 表示没有过滤参数 表示这个主题的任何消息
    consumer.subscribe("asyncTopic", "*");
    // 注册一个消费监听 MessageListenerConcurrently 是并发消费
    // 默认是20个线程一起消费，可以参看 consumer.setConsumeThreadMax()
    consumer.registerMessageListener(new MessageListenerConcurrently() {

        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            String message = new String(msgs.get(0).getBody());
            // 这里执行消费的代码 默认是多线程消费
            System.out.println(Thread.currentThread().getName() + "----"+ message);
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

#### 单向发送消息

这种方式主要用在不关心发送结果的场景，这种**方式吞吐量很大，但是存在消息丢失的风险**，例如日志信息的发送。

消息生产者

```java
/**
  * 发送单向消息
  * @throws Exception
  */
@Test
public void testOnewayProducer() throws Exception {
    // 创建默认的生产者
    DefaultMQProducer producer = new DefaultMQProducer("test-group");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 启动实例
    producer.start();
    Message msg = new Message("oneWayTopic", ("单向消息").getBytes());
    // 发送单向消息
    producer.sendOneway(msg);
    // 关闭实例
    producer.shutdown();
}
```

消息消费者

```java
@Test
public void testOnewayConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("consumer-group");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   *表示没有过滤参数 表示这个主题的任何消息
    consumer.subscribe("oneWayTopic", "*");
    // 注册一个消费监听 MessageListenerConcurrently是并发消费
    consumer.registerMessageListener(new MessageListenerConcurrently() {

        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            String message = new String(msgs.get(0).getBody());
            // 这里执行消费的代码 默认是多线程消费
            System.out.println(Thread.currentThread().getName() + "----"+ message);
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

#### 发送延迟消息

消息放入 mq 后，过一段时间，才会被监听到，然后消费。比如下订单业务，提交了一个订单就可以发送一个延时消息，30min后去检查这个订单的状态，如果还是未付款就取消订单释放库存。

生产者

```java
/**
  * 生产者发送延迟消息
  */
@Test
public void testDelayProducer() throws Exception{
    // 创建默认的生产者
    DefaultMQProducer producer = new DefaultMQProducer("test-group");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 启动实例
    producer.start();
    Message msg = new Message("TopicTest", ("延迟消息").getBytes());
    // 给这个消息设定一个延迟等级
    // messageDelayLevel = "1s 5s 10s 30s 1m 2m 3m 4m 5m 6m 7m 8m 9m 10m 20m 30m 1h 2h
    msg.setDelayTimeLevel(3); // 延时10秒
    // 发送延时消息
    producer.send(msg);
    // 打印发送时间
    System.out.println("发送时间:" + new Date());
    // 关闭实例
    producer.shutdown();
}
```

消息消费者

```java
@Test
public void testDelayConsumer() throws Exception{
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("consumer-group");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   *表示没有过滤参数 表示这个主题的任何消息
    consumer.subscribe("TopicDelay", "*");
    // 默认是20个线程一起消费，可以参看 consumer.setConsumeThreadMax()
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            String message = new String(msgs.get(0).getBody());
            // 这里执行消费的代码 默认是多线程消费
            System.out.println(Thread.currentThread().getName() + "----"+ message + ",收到的消息时间是:" + new Date());
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

#### 发送批量消息

Rocketmq 可以一次性发送一组消息，那么这一组消息会被当做一个消息消费。

生产者

```java
/**
  * 批量发送消息
  * @throws Exception
  */
@Test
public void testBatchProducer() throws Exception {
    // 创建默认的生产者
    DefaultMQProducer producer = new DefaultMQProducer("test-group");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 启动实例
    producer.start();
    List<Message>msgs = Arrays.asList(
        new Message("batchTopic", "我是一组消息的A消息".getBytes()),
        new Message("batchTopic", "我是一组消息的B消息".getBytes()),
        new Message("batchTopic", "我是一组消息的C消息".getBytes())

    );
    SendResult send = producer.send(msgs);
    System.out.println(send);
    // 关闭实例
    producer.shutdown();
}
```

消费者

```java
/**
  * 消费批量发送的消息
  * @throws Exception
  */
Test
public void testBatchConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("consumer-group");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   表达式，默认是*
    consumer.subscribe("batchTopic", "*");
    // 注册一个消费监听 MessageListenerConcurrently是并发消费
    // 默认是20个线程一起消费，可以参看 consumer.setConsumeThreadMax()
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            // 这里执行消费的代码 默认是多线程消费
            System.out.println(Thread.currentThread().getName() + "----"+ new String(msgs.get(0).getBody()));
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

#### MQ 发送顺序消息

假设现在又这样一个场景：有一个业务流程为下订单、发短信、发货。每个业务流程都会发送下订单的消息、发短信的消息、发货的消息。在消费者端，我们需要保证订单消息、发短信消息、发货消息**按照顺序**进行消费。

我们知道 MQ 队列具备先进先出(FIFO)的特性，它本身就保证了消息投递和消费的顺序性。但是，在实际场景中我们的消息投递并不是投递在一个队列里面。通过前面的学习我们指定，RocketMQ为了提高消息的吞吐量，在Broker里面默认创建4个队列。在发送消息的时候，采取轮询的方式将消息投递在队列里面

```markdown
生产者 ------>  queue1
               queue2
               queue3  ---------> 消费者
               queue4
```

此时消息分布在不同的队列里面。消费者端默认使用 **并发模式** 进行消费，也就是多个线程一起来消费队列里面的消息，如果多个线程并发消费队列里面的消息，并不能保证消费顺序是正确。

如果使用单线程模式的方式进行消费，但是消费者可能先消费队列2里面的消息，再消费队列3里面的消息，最后再消费队列1里面的消息，依然不能保证消息消费的顺序性。

但是如果控制发送的顺序消息只依次发送到同一个 queue 中，消费的时候只从这个 queue 上依次拉取，则就保证了顺序。当发送和消费参与的 queue 只有一个，则是全局有序；如果多个 queue 参与，则为分区有序，即相对每个 queue，消息都是有序的。

接下来演示一下

场景需求：

>模拟一个订单的发送流程，创建两个订单，发送的消息分别是
>
>* 订单号111 消息流程 下订单->物流->签收
>
>* 订单号112 消息流程 下订单->物流->拒收

创建生产者

```java
@Test
public void testOrderlyProducer() throws Exception {
    // 创建默认的生产者
    DefaultMQProducer producer = new DefaultMQProducer("orderly-producer");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 启动实例
    producer.start();
    List<Order> orderList = Arrays.asList(
        new Order(1, 111, 59.0, new Date(), "下订单"),
        new Order(2, 111, 59.0, new Date(), "物流"),
        new Order(3, 111, 59.0, new Date(), "签收"),
        new Order(4, 112, 66.0, new Date(), "下订单"),
        new Order(5, 112, 66.0, new Date(), "物流"),
        new Order(6, 112, 66.0, new Date(), "拒收")
    );
    // 循环集合开始发送
    orderList.forEach(order -> {
        Message message = new Message("topicOrder", order.toString().getBytes());
        try {
            // 发送的时候 相同的订单号选择同一个队列
            producer.send(message, new MessageQueueSelector() {
                public MessageQueue select(List<MessageQueue> mqs, Message msg, Object arg) {
                    // 当前主题有多少个队列
                    int queueNumber = mqs.size();
                    // 这个arg就是后面传入的 order.getOrderNumber()
                    Integer i = (Integer) arg;
                    // 用这个值去%队列的个数得到一个队列
                    int index = i % queueNumber;
                    // 返回选择的这个队列即可 ，那么相同的订单号 就会被放在相同的队列里 实现FIFO了
                    return mqs.get(index);
                }
            }, order.getOrderNumber()); // order.getOrderNumber() 就会传递给select方法中的arg参数中。
        } catch (Exception e) {
            e.printStackTrace();
        }
    });
    // 关闭实例
    producer.shutdown();
  
}
```

创建消费者

```java
@Test
public void testOrderlyConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("orderly-consumer");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   *表示没有过滤参数 表示这个主题的任何消息
    consumer.subscribe("topicOrder", "*");
    // 注册一个消费监听 MessageListenerOrderly 是顺序消费 单线程消费
    consumer.registerMessageListener(new MessageListenerOrderly() {
        public ConsumeOrderlyStatus consumeMessage(List<MessageExt> msgs, ConsumeOrderlyContext context) {
            System.out.println("线程id:" + Thread.currentThread().getId());
            MessageExt messageExt = msgs.get(0);
            System.out.println(new String(messageExt.getBody()));
            return ConsumeOrderlyStatus.SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

**它内部是如何实现有序消费的呢**

RocketMQ 的 **Push 模式** 并非真正由 Broker 主动推送消息，而是客户端（Consumer）在后台启动一个 **长轮询线程池**，周期性地从 Broker **拉取消息**。拉取到消息后交给业务线程池异步回调处理。

也就是说，**Push 只是让用户不必显式编写拉取逻辑**。
 整个过程仍然是：

> Broker ←（被动响应）← Consumer 发起拉取请求

RocketMQ 的顺序消费是 **队列内顺序（Partition Ordered）**，不是全局顺序。
 也就是说：

- 同一个 **MessageQueue** 内的消息按发送顺序消费；
- 不同的队列之间可以并发消费。

因此要实现有序消费，RocketMQ 必须保证：

1. **拉取顺序**：按 MessageQueue 中消息的 offset 顺序拉取；
2. **消费顺序**：同一 MessageQueue 的消息只允许一个线程顺序处理。

Push 模式下的有序拉取逻辑

在 **Rebalance 分配阶段**

- 当消费者启动或变动时，客户端会从 NameServer 拉取队列列表；
- 按队列分配算法（默认平均分配）分配给不同消费者；
- 每个消费者获得若干 MessageQueue 的所有权。

**拉取阶段**

- `PullMessageService` 线程从每个分配到的队列中，按 **nextOffset** 顺序拉取消息；
- Broker 返回消息列表；
- Consumer 缓存这些消息，等待业务消费。

> 当消费者（Consumer）从 Broker 拉取到消息后，并不是立刻交给业务线程消费，而是先存储到本地内存中的一个中间结构 —— **ProcessQueue（消息处理队列）**。
>
> 整个过程如下
>
> ```markdown
> Broker ──> PullRequest（拉取请求）
>          └─> 拉取到消息列表 List<MessageExt>
>               └─> 放入本地 ProcessQueue
>                    └─> 提交给消费线程池 ConsumeMessageService
>                         └─> 消费成功后更新 offset
> ```

**消费阶段（顺序保证）**

- Push 模式下的有序消费使用 `MessageListenerOrderly`；
- RocketMQ 客户端会在每个 MessageQueue 上维护一个独立的锁；
- 消费线程池中的一个线程会独占该锁，**串行消费该队列的消息**；
- 消费完一批后再提交 offset 并继续拉取下一批。

> 因为一个 MessageQueue 同时只会被一个线程消费，所以自然保证了**拉取顺序 + 消费顺序**的一致性。

#### RocketMQ中的标签(Tag)和key

在电商业务中，如果我们给每一种商品消息都创建一个 Topic 来传递，这样不同订单类型的消息越来越多，我们就要创建对应多的消息，这样会显得麻烦。

这时我们就可以使用 Tag 这个消息属性来解决这个问题。同一类消息使用一个 Topic，但是每一类消息又按照 Tag 区分不同种

代码实现

生产者

```java
/**
  * 发送带有标签消息的生产者
  */
@Test
public void sendMessageWithTag() throws Exception{
    // 创建默认的生产者
    DefaultMQProducer producer = new DefaultMQProducer("tagMessage-producer-group");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    // 启动实例
    producer.start();
    Message msg1 = new Message("TopicWithTag","tagA", "我是一个带tagA标记的消息".getBytes());
    Message msg2 = new Message("TopicWithTag","tagB", "我是一个带tagB标记的消息".getBytes());
    SendResult send1 = producer.send(msg1);
    SendResult send2 = producer.send(msg2);
    System.out.println(send1);
    System.out.println(send2);
    // 关闭实例
    producer.shutdown();
}
```

消费者

```java
/**
  * 消费者1
  * @throws Exception
  */
@Test
public void testTagConsumer1() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("tagMessage-consumer-group1");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   表达式，默认是*,支持"tagA || tagB || tagC"这样或者的写法 只要是符合任何一个标签都可以消费
    consumer.subscribe("TopicWithTag", "tagA || tagB");
    // 注册一个消费监听 MessageListenerConcurrently是并发消费
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        @Override
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            // 这里执行消费的代码 默认是多线程消费
            System.out.println( "消费者1消费的消息是:"+ new String(msgs.get(0).getBody()));
            System.out.println(msgs.get(0).getTags());
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

那么什么时候该用 Topic，什么时候该用 Tag？

不同的业务应该使用不同的 Topic 如果是相同的业务里面有不同表的表现形式，那么我们要使用 Tag 进行区分。

可以从以下几个方面进行判断：

>1.消息类型是否一致：如普通消息、事务消息、定时（延时）消息、顺序消息，不同的消息类型使用不同的 Topic，无法通过 Tag 进行区分。
>
>2.业务是否相关联：没有直接关联的消息，如淘宝交易消息，京东物流消息使用不同的 Topic 进行区分；而同样是天猫交易消息，电器类订单、女装类订单、化妆品类订单的消息可以用 Tag 进行区分。
>
>3.消息优先级是否一致：如同样是物流消息，盒马必须半小时内送达，天猫超市 24 小时内送达，淘宝物流则相对会慢一些，不同优先级的消息用不同的 Topic 进行区分。
>
>4.消息量级是否相当：有些业务消息虽然量小但是实时性要求高，如果跟某些万亿量级的消息使用同一个 Topic，则有可能会因为过长的等待时间而“饿死”，此时需要将不同量级的消息进行拆分，使用不同的 Topic。

**总的来说，针对消息分类，可以选择创建多个 Topic，或者在同一个 Topic 下创建多个 Tag。但通常情况下，不同的 Topic 之间的消息没有必然的联系，而 Tag 则用来区分同一个 Topic 下相互关联的消息，例如全集和子集的关系、流程先后的关系。**

#### 消息重复消费

在负载均衡模(CLUSTERING)式下,如果一个Topic被多个ConsumerGroup消费，会出现消息重复消费的问题。在CLUSTERING模式下，即使在同一个消费者组里面，一个队列只会分配给一个消费者，看起来好像是不会重复消费。但是，有个特殊情况：**一个消费者新上线后，同组的所有消费者要重新负载均衡**（反之一个消费者掉线后，也一样）。一个队列所对应的新的消费者要获取之前消费的offset（偏移量，也就是消息消费的点位），此时之前的消费者可能已经消费了一条消息，但是并没有把offset提交给broker，那么新的消费者可能会重新消费一次。

**那么如果在CLUSTERING（负载均衡）模式下，并且在同一个消费者组中，不希望一条消息被重复消费，改怎么办呢？我们可以想到去重操作，找到消息唯一的标识，可以是msgId也可以是你自定义的唯一的key，这样就可以去重了。**

##### 基于布隆过滤器解决消息重复消费

生产者

```java
@Test
public void testRepeatProducer() throws Exception {
    // 创建默认的生产者
    DefaultMQProducer producer = new MyProducer("repeat-producer-group");
    // 设置nameServer地址
    producer.setNamesrvAddr("192.168.10.138:9876");
    producer.setMqClientApiTimeout(1000*30);
    // 启动实例
    producer.start();
    // 我们可以使用自定义key当做唯一标识
    String keyId = UUID.randomUUID().toString();
    System.out.println(keyId);
    Message msg = new Message("topicRepeat", "tagA", keyId, "我是一个测试消息".getBytes());
    Message repeatMsg = new Message("topicRepeat", "tagA", keyId, "我是一个测试消息".getBytes());
    SendResult send1 = producer.send(msg,1000*30);
    SendResult send2 = producer.send(repeatMsg,1000*30);
    System.out.println(send1);
    System.out.println(send2);
    // 关闭实例
    producer.shutdown();
}
```

消费者

```java
/**
  * 在springBoot项目中可以使用@Bean在整个容器中放置一个单例对象
  */
public static BitMapBloomFilter bloomFilter = new BitMapBloomFilter(100);

@Test
public void testRepeatConsumer() throws Exception {
    // 创建默认消费者组
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("repeat-consumer-group");
    // 设置nameServer地址
    consumer.setNamesrvAddr("192.168.10.138:9876");
    // 订阅一个主题来消费   表达式，默认是*,支持"tagA || tagB || tagC"这样或者的写法 只要是符合任何一个标签都可以消费
    consumer.subscribe("topicRepeat", "tagA");
    // 注册一个消费监听 MessageListenerConcurrently是并发消费
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        @Override
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs,
                                                        ConsumeConcurrentlyContext context) {
            MessageExt messageExt = msgs.get(0);
            String keys = messageExt.getKeys(); //获取消息的key
            // 判断是否存在布隆过滤器中
            if (bloomFilter.contains(keys)) {
                // 直接返回了 不往下处理业务
                return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
            }
            // 这个处理业务，然后放入过滤器中
            bloomFilter.add(keys);
            System.out.println( "消费者消费的消息是:"+ new String(messageExt.getBody()));
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

#### RocketMQ 的消息重试和死信队列

##### 消息发送重试

Producer 对发送失败的消息进行重新发送的机制，称为消息发送重试机制，也称为消息重投机制。对于消息重投，我们需要明白几点：

>- 生产者在发送消息时，若采用同步或异步发送方式，发送失败会重试，但 oneway 消息发送方式发送失败是没有重试机制的。
>- 只有普通消息具有发送重试机制，顺序消息是没有的。
>- 消息重投机制可以保证消息尽可能发送成功、不丢失，但可能会造成消息重复。消息重复在RocketMQ中是无法避免的问题。
>- 消息发送重试有三种策略可以选择：同步发送失败策略、异步发送失败策略、消息刷盘失败策略。

**同步发送消息失败策略：**

对于普通消息，消息发送默认采用 round-robin 策略来选择所发送到的队列。如果发送失败，默认重试 2 次。但在重试时是不会选择上次发送失败的 Broker，而是选择其它B roker。当然，若只有一个 Broker 其也只能发送到该 Broker，但其会尽量发送到该 Broker 上的其它 Queue。

```java
DefaultMQProducer producer = new DefaultMQProducer("retry-producer-group");
producer.setNamesrvAddr("192.168.10.138:9876");
// 设置同步发送失败时重试发送的次数，默认为 2 次
producer.setRetryTimesWhenSendFailed( 3 );
```

**异步发送消息失败策略：**

异步发送失败重试时，异步重试不会选择其他 Broker，仅在同一个 Broker 上做重试，所以该策略无法保证消息不丢。

```java
DefaultMQProducer producer = new DefaultMQProducer("retry-producer-group");
producer.setNamesrvAddr("192.168.10.138:9876");
 // 指定异步发送失败后进行重试发送的次数，默认为 2 次
producer.setRetryTimesWhenSendAsyncFailed(2);
```

**消息刷盘失败策略：**

消息刷盘超时（Master或Slave）或 slave 不可用（slave 在做数据同步时向 master 返回状态不是 SEND_OK）时，默认是不会将消息尝试发送到其他 Broker 的。不过，对于重要消息可以通过在 Broker 的配置文件设置 retryAnotherBrokerWhenNotStoreOK 属性为 true来开启。

##### 消息消费重试机制

**顺序消息的消费重试：**

对于顺序消息，当 Consumer 消费消息失败后，为了保证消息的顺序性，其会自动不断地进行消息重试，直到消费成功。消费重试默认间隔时间为 1000 毫秒。重试期间应用会出现消息消费被阻塞的情况。

```java
DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("retry-consumer-group");
// 顺序消息消费失败的消费重试时间间隔，单位毫秒，默认为 1000 ，其取值范围为[10,30000]
consumer.setSuspendCurrentQueueTimeMillis( 100 );
```

>由于对顺序消息的重试是无休止的，不间断的，直至消费成功，所以，对于顺序消息的消费，务必要保证应用能够及时监控并处理消费失败的情况，避免消费被永久性阻塞。
>
>注意，顺序消息没有发送失败重试机制，但具有消费失败重试机制。

**无序消息的消费重试：**

对于无序消息（普通消息、延时消息、事务消息），当 Consumer 消费消息失败时，可以通过设置返回状态达到消息重试的效果。不过需要注意，无序消息的重试 **只对集群消费方式生效**，广播消费方式不提供失败重试特性。即对于广播消费，消费失败后，失败消息不再重试，继续消费后续消息。

对于 **无序消息集群** 消费下的重试消费，每条消息默认最多重试 16 次，但每次重试的间隔时间是不同的，会逐渐变长。每次重试的间隔时间如下表。

| 重试次数 | 与上次重试的间隔时间 | 重试次数 | 与上次重试的间隔时间 |
| -------- | -------------------- | -------- | -------------------- |
| 1        | 10秒                 | 9        | 7分钟                |
| 2        | 30秒                 | 10       | 8 分钟               |
| 3        | 1分钟                | 11       | 9 分钟               |
| 4        | 2分钟                | 12       | 10分钟               |
| 5        | 3分钟                | 13       | 20分钟               |
| 6        | 4分钟                | 14       | 30分钟               |
| 7        | 5分钟                | 15       | 1小时                |
| 8        | 6分钟                | 16       | 2 小时               |

>若一条消息在一直消费失败的前提下，将会在正常消费后的第 4 小时 46 分后进行第 16 次重试。若仍然失败，则将消息投递到 **死信队列**

当然我们也可以修改消息消费的重试次数：

```java
DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("retry-consumer-group");
// 修改消费重试次数
consumer.setMaxReconsumeTimes( 10 );
```

**创建消息生产者：**

```java
@Test
public void retryProducer() throws Exception {
    DefaultMQProducer producer = new MyProducer("retry-producer-group");
    producer.setMqClientApiTimeout(1000*30);
    producer.setNamesrvAddr("192.168.10.138:9876");
    producer.start();
    // 生产者发送消息 重试次数
    producer.setRetryTimesWhenSendFailed(2);
    producer.setRetryTimesWhenSendAsyncFailed(2);
    String key = UUID.randomUUID().toString();
    System.out.println(key);
    Message message = new Message("retryTopic", "vip1", key, "我是vip666的文章".getBytes());
    producer.send(message,1000*30);
    System.out.println("发送成功");
    producer.shutdown();
}
```

**创建消息消费者：**

```java
@Test
public void retryConsumer() throws Exception {
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("retry-consumer-group");
    consumer.setNamesrvAddr("192.168.10.138:9876");
    consumer.subscribe("retryTopic", "*");
    // 设定重试次数
    consumer.setMaxReconsumeTimes(2);
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        @Override
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs, ConsumeConcurrentlyContext context) {
            MessageExt messageExt = msgs.get(0);
            System.out.println(new Date());
            System.out.println("消息消费重试次数:" + messageExt.getReconsumeTimes());//获取重试次数
            System.out.println(new String(messageExt.getBody()));
            //返回 RECONSUME_LATER 都会重试
            return ConsumeConcurrentlyStatus.RECONSUME_LATER;
        }
    });
    consumer.start();
    System.in.read();
}
```

前面我们知道，默认会进行16次重试消费，如果依然重试不成功，消息就会进入死信队列。所以我们可以创建一个消费者专门来消费死信队列里面的消息。死信队列其实就是一个特殊的 Topic。名称是：%DLQ%consumerGroup

```java
//直接监听死信主题的消息,记录下拉 通知人工介入处理
@Test
public void retryDeadConsumer() throws Exception {
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("retry-dead-consumer-group");
    consumer.setNamesrvAddr("192.168.10.138:9876");
    consumer.subscribe("%DLQ%retry-consumer-group", "*");
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        @Override
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs, ConsumeConcurrentlyContext context) {
            MessageExt messageExt = msgs.get(0);
            System.out.println(new Date());
            System.out.println(new String(messageExt.getBody()));
            System.out.println("记录到特别的位置 文件 mysql 通知人工处理");
            // 业务报错了 返回null 返回 RECONSUME_LATER 都会重试
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

有一种方案：我们还可以自定义重试次数，如果超过了重试次数，我们直接记录消息，进行 人工处理。

```java
@Test
public void retryConsumer2() throws Exception {
    DefaultMQPushConsumer consumer = new DefaultMQPushConsumer("retry-consumer-group");
    consumer.setNamesrvAddr("192.168.10.138:9876");
    consumer.subscribe("retryTopic", "*");
    // 设定重试次数
    consumer.registerMessageListener(new MessageListenerConcurrently() {
        @Override
        public ConsumeConcurrentlyStatus consumeMessage(List<MessageExt> msgs, ConsumeConcurrentlyContext context) {
            MessageExt messageExt = msgs.get(0);
            System.out.println(new Date());
            try {
                // 模拟消息消费出现异常
                int i = 10 /0;
            } catch (Exception e) {
                // 重试
                int reconsumeTimes = messageExt.getReconsumeTimes();
                if (reconsumeTimes >= 3) {
                    // 不要重试了
                    System.out.println("记录到特别的位置 文件 mysql 通知人工处理");
                    return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
                }
                return ConsumeConcurrentlyStatus.RECONSUME_LATER;
            }
            // 业务报错了 返回null 返回 RECONSUME_LATER 都会重试
            return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
        }
    });
    consumer.start();
    System.in.read();
}
```

##### 死信队列

什么是死信队列：当一条消息初次消费失败，消息队列会自动进行消费重试；达到最大重试次数后，若消费依然失败，则表明消费者在正常情况下无法正确地消费该消息，此时，消息队列不会立刻将消息丢弃，而是将其发送到该消费者对应的特殊队列中。这个队列就是死信队列（Dead-Letter Queue，DLQ），而其中的消息 则称为死信消息（Dead-Letter Message，DLM）。**一句话：死信队列是用于处理无法被正常消费的消息的。**

死信队列具有如下特性：

>- 死信队列中的消息不会再被消费者正常消费，即DLQ对于消费者是不可见的
>- 死信存储有效期与正常消息相同，均为 3 天（commitlog文件的过期时间）， 3 天后会被自动删除
>- 死信队列就是一个特殊的Topic，名称为%DLQ%consumerGroup@consumerGroup，即每个消费者组都有一个死信队列
>- 如果一个消费者组未产生死信消息，则不会为其创建相应的死信队列

**死信队列的处理：**

实际上，当一条消息进入死信队列，就意味着系统中某些地方出现了问题，从而导致消费者无法正常消费该消息，比如代码中原本就存在Bug。因此，对于死信消息，通常需要开发人员进行特殊处理。最关键的步骤是要排查可疑因素，解决代码中可能存在的Bug，然后再将原来的死信消息再次进行投递消费。

#### SpringBoot 集成 MQ

添加依赖

```xml
<dependency>
    <groupId>org.apache.rocketmq</groupId>
    <artifactId>rocketmq-spring-boot-starter</artifactId>
    <version>2.3.0</version>
</dependency>
```

`application.yml`

```yaml
rocketmq:
  name-server: 127.0.0.1:9876   # RocketMQ NameServer 地址
  producer:
    group: demo-producer-group  # ProducerGroup 名称
    send-message-timeout: 3000  # 超时时间(ms)
    retry-times-when-send-failed: 2  # 发送失败重试次数
  consumer:
    group: demo-consumer-group  # ConsumerGroup 名称
    message-model: CLUSTERING   # 可选：BROADCASTING 或 CLUSTERING
```

生产者

```java
@Service
public class ProducerService {

    @Autowired
    private RocketMQTemplate rocketMQTemplate;

    // 同步发送
    public void sendSync(String topic, String message) {
        rocketMQTemplate.convertAndSend(topic, message);
        System.out.println("发送成功: " + message);
    }

    // 异步发送
    public void sendAsync(String topic, String message) {
        rocketMQTemplate.asyncSend(topic, message, new SendCallback() {
            @Override
            public void onSuccess(SendResult sendResult) {
                System.out.println("异步发送成功：" + sendResult);
            }

            @Override
            public void onException(Throwable e) {
                System.err.println("发送失败：" + e.getMessage());
            }
        });
    }

    // 延迟消息
    public void sendDelay(String topic, String message, int delayLevel) {
        rocketMQTemplate.syncSend(topic, MessageBuilder.withPayload(message).build(), 3000, delayLevel);
    }

    // 发送带Tag的消息
    public void sendWithTag(String topic, String tag, String message) {
        rocketMQTemplate.convertAndSend(topic + ":" + tag, message);
    }
}
```

> `convertAndSend()` 会自动将对象序列化成 JSON

消费者通过 `@RocketMQMessageListener` 注解实现

```java
@Service
@RocketMQMessageListener(
    topic = "demo-topic", 
    consumerGroup = "demo-consumer-group",
    messageModel = MessageModel.CLUSTERING // 或 BROADCASTING
)
public class ConsumerService implements RocketMQListener<String> {

    @Override
    public void onMessage(String message) {
        System.out.println("消费者收到消息: " + message);
    }
}
```

> 默认消费模式为 **集群模式（Clustering）**，也可以设置为 **广播模式（Broadcasting）** 来实现每个实例都收到所有消息。

`@RocketMQMessageListener` 实际上会帮你创建一个 **DefaultMQPushConsumer** 实例。Spring Boot 集成 RocketMQ 时，**框架层面只封装了 Push 模式**，Pull 模式需要自己手动实现

Spring Boot 自动完成的流程：

- 启动时扫描到注解 -> 注册 `DefaultRocketMQListenerContainer`
- 创建并启动一个 **DefaultMQPushConsumer**
- 根据注解参数配置订阅信息：`topic`, `selectorType`, `selectorExpression`, `messageModel`
- 设置消息监听器：
  - 将 `DemoListener` 注册为回调处理器
  - 实际调用 `consumer.registerMessageListener(MessageListenerConcurrently)`
    - 启动消费线程 -> 开始长轮询从 Broker 拉取消息
    - 拉到消息后自动回调 `onMessage()`

RocketMQ 与 Spring Boot 集成也支持事务消息，只需实现 `RocketMQLocalTransactionListener`

```java
@RocketMQTransactionListener(txProducerGroup = "tx-producer-group")
public class TransactionListenerImpl implements RocketMQLocalTransactionListener {

    @Override
    public RocketMQLocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        try {
            // 执行本地事务逻辑
            System.out.println("执行本地事务：" + msg);
            return RocketMQLocalTransactionState.COMMIT; // 提交
        } catch (Exception e) {
            return RocketMQLocalTransactionState.ROLLBACK; // 回滚
        }
    }

    @Override
    public RocketMQLocalTransactionState checkLocalTransaction(Message msg) {
        // Broker 回查本地事务
        return RocketMQLocalTransactionState.COMMIT;
    }
}
```

#### 与 Spring Cloud Stream 集成

引入依赖

```xml
<dependency>
  <groupId>com.alibaba.cloud</groupId>
  <artifactId>spring-cloud-starter-stream-rocketmq</artifactId>
</dependency>
```

配置

```yaml
spring:
  cloud:
    stream:
      rocketmq:
        binder:
          name-server: 127.0.0.1:9876
      bindings:
        output:                # 生产者绑定
          destination: order-topic
        input:                 # 消费者绑定
          destination: order-topic
          group: order-group
```

```java
@EnableBinding({Source.class, Sink.class})
public class StreamDemo {

    @Autowired
    private MessageChannel output;

    @StreamListener(Sink.INPUT)
    public void receive(String message) {
        System.out.println("收到消息: " + message);
    }

    public void send(String msg) {
        output.send(MessageBuilder.withPayload(msg).build());
    }
}
```

> 适合需要统一接入 Kafka / RabbitMQ / RocketMQ 的多消息中间件微服务体系
