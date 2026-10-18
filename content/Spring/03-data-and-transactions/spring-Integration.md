+++
date = '2025-10-19T16:37:19+08:00'
draft = false
title = 'spring-Integration'
+++

**Spring Integration** 框架基于 Spring 提供了一种实现企业集成模式的方式。用于不同企业应用实现消息传递，简化企业应用集成的复杂性

组成 Spring Integration 的三大组件是 **Message**、**Message Channel** 和 **Message Endpoint**

```markdown
		message			message			 message		message
channel--------->endpoint--------->channel-------->endpoint--------->

```

- Message：即消息本身，它由 Payload 和 Headers 两部分组成，Payload 载荷是实际传递的数据对象，如 Json、字符串、DTO 等。而 Headers 消息头中则包含了一些元数据，如消息 ID，时间戳、路由键等

  ```java
  Message<String> message = MessageBuilder
          .withPayload("Hello World")
          .setHeader("type", "greeting")
          .build();
  ```

- Message Channel：是消息传输的载体，通常可以分为 point-to-point（点对点）和 publish-subscribe（发布订阅）两种行为模式。此外从通道是否保存消息的角度来说，通道还分为 Pollable Channel 和 Subscribable Channel 两种。
  - Pollable Channel：保存消息，消费者需要主动拉取消息，核心接口为 PollableChannel。
  - Subscribable Channel：可订阅型通道，不存储消息，消费者被动通知消息，核心接口为 SubscribableChannel。这种划分方式也是API接口的划分方式，不同的通道类型对消息流程的处理会有不同的表现形式。

- Message Endpoint：消息端点，它是消息的消费端，通常与外部系统对接。Spring Integration 提供了多种不同的 EndPoint 满足不同的需求。

### 消息通道（Message Channel）

**Spring Integration** 提供了多种通道的实现

常见类型有：

- `DirectChannel`：同步调用，发出消息后立即由下游组件处理。
- `QueueChannel`：异步，消息进入队列，消费者异步处理。
- `PublishSubscribeChannel`：广播模式，多个订阅者同时收到消息。
- `ExecutorChannel`：基于线程池的异步通道。

### 消息端点（Message Endpoints）

消息端点是消息处理的核心组件，它是业务逻辑执行的地方

常见的端点类型有：

| 端点类型              | 功能                       |
| --------------------- | -------------------------- |
| **Service Activator** | 调用业务服务处理消息       |
| **Transformer**       | 转换消息内容格式           |
| **Filter**            | 过滤消息                   |
| **Router**            | 根据条件路由消息到不同通道 |
| **Splitter**          | 拆分消息                   |
| **Aggregator**        | 聚合多个消息               |
| **Bridge**            | 连接两个通道               |

看一个配置 

```java
// 配置通道类
@Configuration
public class ChannelConfig {

    @Bean
    public MessageChannel inputChannel() {
        return new DirectChannel();
    }

    @Bean
    public MessageChannel middleChannel() {
        return new DirectChannel();
    }
}
```

```java
@EnableIntegration
public class HandlerConfig {

    // 声明一个数据源，轮询器 poller 以固定时间将数据发送到绑定的 channel 上
    @InboundChannelAdapter(channel = "inputChannel", poller = @Poller(fixedRate = "500"))
    public Message<String> input() {
        return new Message<>() {
            @Override
            public String getPayload() {
                return "我永远喜欢雪之下雪乃";
            }

            @Override
            public MessageHeaders getHeaders() {
                return new MessageHeaders(Map.of());
            }
        };
    }

    // 消息端点
    @Transformer(inputChannel = "inputChannel", outputChannel = "middleChannel")
    public Message<?> middleTransformer(Message<?> message) {
        return new GenericMessage<>(
                message.getPayload(),
                Map.of("transformer", "middleTransformer")
        );
    }

    // 用于定义最终处理器
    @ServiceActivator(inputChannel = "middleChannel")
    public void handler(Message<String> message) {
        System.out.println(message.getHeaders().get("transformer"));
        System.out.println(message.getPayload());
    }
}
```

> `@MessageEndpoint` 是 Spring Integration 提供的一个**组件标识注解**，用于表明某个类是一个**消息端点（Message Endpoint）**。
>
> 它的作用类似于：
>
> - `@Component`（用于标识普通 Bean）
> - `@Controller`（用于标识 Web 控制器）
> - `@Service`（用于标识业务逻辑组件）
>
> 换句话说，`@MessageEndpoint` 表示：
>
> 这是一个专门用于**接收、处理或发送消息**的 Spring Bean。
>
> `@EnableIntegration` 是 Spring Integration 提供的一个 **启用配置注解**，
>  类似于：
>
> - `@EnableScheduling` 启用定时任务
> - `@EnableAsync` 启用异步任务
> - `@EnableWebMvc` 启用 Spring MVC
>
> 它会自动注册运行时的消息基础设施，如通道、错误处理、生命周期、监控等，是所有 `@ServiceActivator`、`IntegrationFlow` 等组件能正常工作的前提条件

配置处理器

消息会通过 Channel 传递，消息端点会按照不同的规则处理消息

`@InboundChannelAdapter` 注解是用来定义消息源

`@ServiceActivator` 注解是用来定义定义最终消息处理器 

Spring Integration 还有

**Integration Flow（集成流程）**

- 定义了消息从输入到输出的完整处理路径。
- 可以用 **Java DSL** 来声明：

```java
@Bean
public IntegrationFlow demoFlow() {
    return IntegrationFlows.from("inputChannel")
            .filter((String msg) -> msg.startsWith("A"))
            .transform(String::toLowerCase)
            .handle(System.out::println)
            .get();
}
```

**Gateway（网关）**

- 是应用与集成系统之间的接口。
- 用于将普通方法调用转换为消息发送/接收。

```java
@MessagingGateway
public interface DeviceGateway {
    @Gateway(requestChannel = "deviceInputChannel")
    void sendToDevice(String data);
}
```

#### Adapter（适配器）

它是用于与 **外部系统** 进行连接的组件。

例如，我们上一个例子中的 **Inbound Adapter**，它可以从外部系统接收消息（HTTP、MQTT、Kafka、JMS、FTP、TCP…）

还有 **Outbound Adapter**，它是向外部系统发送消息

接下来我们在系统中集成一个 MQTT

### [Spring Integration MQTT](https://www.cnblogs.com/cxuanBlog/p/14917187.html)

在使用该框架之前，我们先了解一下 MQTT。

MQTT 是一种基于发布订阅模式的消息协议，基于 TCP/IP 协议。一般多用于物联网，广泛应用于工业级别的应用场景。主要面向 **长连接、弱网、低功耗** 设备。

设计目标：**最小报文、最少带宽、可靠可选**。典型用于 IoT 采集、设备控制、车联网、移动端推送等。

参与方有：

- **Broker（代理/服务器）**：转发中心（如 EMQX、Mosquitto、HiveMQ）。
- **Client（客户端）**：发布消息和订阅消息的都称之为客户端
- **Topic（主题）**：是一个层级字符串，用于路由消息（如 `device/123/telemetry`）。

#### 核心机制

**主题与通配符**
`+` 匹配单层；

`#` 匹配多层，但是只能出现在最后。
 例：订阅 `device/+/telemetry` 可接收任意设备的遥测；`device/#` 接收该前缀下所有消息。

> PS：发布时 **不能** 使用通配符，必须使用一个确切的主题；订阅时可以模糊订阅。

**QoS（服务质量等级）**

- **QoS 0**：消息最多送达一次，不保证送达。

  > 客户端发送消息给 Broker（或 Broker 发送给客户端），**不需要经过确认**。
  >
  > 但当网络断开时，消息可能**丢失**。
  >
  > 没有重发机制。

- **QoS 1**：消息至少送达一次，可能重复。

  > 发送方发送 `PUBLISH`（带 `QoS=1`）
  >
  > 接收方收到后回复 `PUBACK`（确认）
  >
  > 若发送方未收到 `PUBACK`，则重发消息
  >
  > 因为有重发机制，**接收方可能收到重复消息**

- **QoS 2**：消息只送达一次，不丢不重。

  > 发送方：`PUBLISH`
  >
  > 接收方：`PUBREC`（已收到）
  >
  > 发送方：`PUBREL`（确认发布）
  >
  > 接收方：`PUBCOMP`（完成）
  >
  > 整个流程确保：不会重复；不会丢失；但会增加延迟和网络流量

**保留消息（Retained Message）**

Broker 会记住该主题 **最后一条** 消息，如果有新订阅者它会立刻收到这条消息。发送 **空载荷 + retain** 可清除该主题的保留消息。

**遗嘱消息（Last Will & Testament, LWT）**

客户端异常断开时，Broker 自动向指定主题发布 **离线/故障** 消息。

> 它可以用来判断设备的在线状态，主动下线的时候主动发送下线消息，但当异常下线的时候，就需要通过遗嘱消息来更新设备状态

**共享订阅（Shared Subscription）**：

多消费者 **分摊** 同一主题负载，类似 MQ 的集群消费。

常见语语法：`$share/<group>/device/+/telemetry`。同组内仅 **一台** 消费者收到某条消息（负载均衡）

接下来看一个例子

配置依赖

```xml
<dependency>
    <groupId>org.springframework.integration</groupId>
    <artifactId>spring-integration-mqtt</artifactId>
    <version>6.2.3</version>
</dependency>
```

Spring Integration 通过 `MqttPahoClientFactory` 创建和配置 MQTT 客户端。是 MQTT 客户端配置中心，负责统一提供客户端连接配置（Broker 地址、认证、超时、SSL 等）。供发布端和订阅端使用，避免重复配置，方便维护和扩展

```java
@Bean
public MqttPahoClientFactory mqttClientFactory() {
    DefaultMqttPahoClientFactory factory = new DefaultMqttPahoClientFactory();
    MqttConnectOptions options = new MqttConnectOptions();
    options.setServerURIs(new String[]{"tcp://127.0.0.1:1883"});
    options.setUserName("username");
    options.setPassword("password".toCharArray());
    factory.setConnectionOptions(options);
    return factory;
}
```

配置 Channel 

```java
@Bean
public MessageChannel mqttInputChannel() {
    return new DirectChannel();
}

@Bean
public MessageChannel mqttOutboundChannel() {
    return new DirectChannel();
}
```

Channel 用于消息的传递

订阅消息

让 Spring Integration 监听某个 Topic，收到消息后转发到 Channel

```java
@Bean
public MessageProducer inbound(MqttPahoClientFactory mqttClientFactory) {
    // Spring Integration 设配器，用来获取 MQTT Broker 发送的消息
    MqttPahoMessageDrivenChannelAdapter adapter =
            new MqttPahoMessageDrivenChannelAdapter(
                    "mqttClientSub", mqttClientFactory, "test/topic");
    adapter.setCompletionTimeout(5000);
    adapter.setConverter(new DefaultPahoMessageConverter());
    adapter.setQos(1);
    adapter.setOutputChannel(mqttInputChannel()); // 将从 Broker 订阅的消息发送到 mqttInputChannel 通道
    return adapter;
}

@ServiceActivator(inputChannel = "mqttInputChannel")
public void handleMessage(String payload) {
    System.out.println("收到消息: " + payload);
}
```

`MessageProducer` 是一个非常核心的接口，用来从外部系统接收消息并送入 Spring Integration 消息通道组件中

工作机制

```markdown
┌────────────────────┐
│   外部系统（MQTT） │
└────────┬───────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageProducer（生产者）    │
│ 负责接收消息，并封装成       │
│ org.springframework.messaging.Message │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageChannel（通道）        │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageHandler（处理器/消费者）│
└──────────────────────────────┘
```

`spring-integration-mqtt` 中最经典的实现类是 `MqttPahoMessageDrivenChannelAdapter`，用于从 MQTT Broker 订阅主题，接收消息，然后将其发送到对应的 `Channel`

`@ServiceActivator` 注解也是 Spring Integration 中的核心注解之一，负责监听某个通道，当有消息到达时就执行指定的方法或消息处理器

```java
@ServiceActivator(
    inputChannel = "mqttInboundChannel", // 要监听的通道
    outputChannel = "processedChannel",  // 处理消息后转发的通道
    requiresReply = false,               // 是否要求返回值作为回复消息
    async = false                        // 是否异步调用
)
```

它可以和方法绑定

```java
@Component
public class MqttMessageReceiver {

    @ServiceActivator(inputChannel = "mqttInboundChannel")
    public void handleMessage(String payload) {
        System.out.println("接收到消息: " + payload);
    }
} // 将是消息最终处理器
```

绑定到 MessageHandler Bean

```java
@Bean
@ServiceActivator(inputChannel = "mqttOutboundChannel")
public MessageHandler mqttOutbound(MqttPahoClientFactory factory) {
    MqttPahoMessageHandler handler =
        new MqttPahoMessageHandler("publisherClient", factory);
    handler.setAsync(true);
    handler.setDefaultTopic("device/data");
    return handler;
} // 会调用调用 MessageHandler Bean 的 handlerMessage() 方法处理消息
```

上面的代码就是一个向外部发送消息的处理器，会将从 `mqttOutboundChannel` 通道中的消息发送到 `device/data` 主题

`mqttOutboundChannel` 通道中的消息可以通过定义一个网关发送

```java
@MessagingGateway(defaultRequestChannel = "mqttOutboundChannel")
public interface MqttSenderGateway {

    // 发送消息到默认主题
    void sendToMqtt(String payload);

    // 发送消息到指定主题
    void sendToMqtt(@Header(MqttHeaders.TOPIC) String topic, String payload);

    // 指定 QoS
    void sendToMqtt(@Header(MqttHeaders.TOPIC) String topic,
                    @Header(MqttHeaders.QOS) int qos,
                    String payload);
}
```

`MessageProducer` 是从外部接收消息的核心接口，`MessageHandler` 就是 Spring Integration 处理或向外部发送消息的核心接口。在 Spring Integration 的世界里，一切最终处理或发送到外部系统的逻辑，都是通过 `MessageHandler` 来完成的

```markdown
┌────────────────────┐
│ 外部系统（MQTT）   │
└────────┬───────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageProducer (入口)       │ ← 负责接收消息
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageChannel (管道)        │ ← 用于异步或同步传递消息
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ MessageHandler (出口)        │ ← 负责处理或发送消息
└──────────────────────────────┘
```

spring integration mqtt 中的典型实现类是 `MqttPahoMessageHandler`

`@MessagingGateway` 是 Spring Integration 中最优雅、最高层的消息发送入口机制。它可以像调用普通方法一样，向 Spring Integration 的消息通道发送消息。

我们如果使用 `MessageChannel` 手动发送消息

```java
@SpringBootApplication
public class DemoApplication {

    public static void main(String[] args) {
        var context = SpringApplication.run(DemoApplication.class, args);

        // 从容器中获取定义的通道
        MessageChannel channel = context.getBean("demoChannel", MessageChannel.class);

        // 构建消息对象
        Message<String> message = MessageBuilder
                .withPayload("hello spring integration!") // 消息体
                .setHeader("sender", "manualTest")        // 可选：添加自定义 header
                .build();

        // 发送消息
        boolean sent = channel.send(message);
        System.out.println(" 消息是否发送成功: " + sent);
    }

    /**
     * 定义一个消息通道
     */
    @Bean
    public MessageChannel demoChannel() {
        return new DirectChannel();
    }

    /**
     * 定义消息消费者（监听 demoChannel）
     */
    @Bean
    @ServiceActivator(inputChannel = "demoChannel")
    public MessageHandler printMessageHandler() {
        return msg -> {
            System.out.println("收到消息: " + msg.getPayload());
            System.out.println("Headers: " + msg.getHeaders());
        };
    }
}
```

这样使用十分麻烦，而有了 `@MessagingGateway` 我们只需要调用

```java
mqttGateway.sendToMqtt("hello");
```

Spring 会自动帮忙完成

```markdown
方法调用 -> 封装为 Message -> 发送到指定 MessageChannel -> MessageHandler 处理
```

`@MessagingGateway` 会为接口自动创建一个 **代理类 (Proxy)**，这个代理类会把方法调用**转换成一条消息**并发送到指定的通道

`@MessagingGateway` 定义一个消息网关（gateway）接口；`defaultRequestChannel` 表示默认发送到哪个通道；方法参数可以使用 `@Header` 来指定消息头；方法体留空，由 Spring 自动生成代理。

整个的过程是

```markdown
业务方法调用
   ↓
MessagingGateway 代理
   ↓
MessageChannel（mqttOutboundChannel）
   ↓
MqttPahoMessageHandler
   ↓
MQTT Broker
```
