+++
date = '2026-02-24T19:28:44+08:00'
draft = false
title = 'sse'
+++

今天我们介绍一种服务端向前端推送数据的方式 **SSE**。

先看一个示例代码：

```java
@Slf4j
@RestController
@RequestMapping("/sse")
public class SseController {

    @Autowired
    private UserGatewayService userGatewayService;

    // 保存所有客户端连接
    private static final Map<String, FluxSink<ServerSentEvent<Object>>> clients = new ConcurrentHashMap<>();

    /**
     * 前端连接后端时建立数据流通道
     * @param userId
     * @param gatewayId
     * @return
     */
    @GetMapping(value = "/connect/{userId}/{gatewayId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<Object>> connect(@PathVariable("userId") String userId, @PathVariable("gatewayId") String gatewayId) {
        String clientId = userId + "_" + gatewayId;
        // 心跳流 -- sse自动发送心跳包
        Flux<ServerSentEvent<Object>> heartbeatFlux = Flux
                .interval(Duration.ofSeconds(15))
                .map(seq -> ServerSentEvent.builder()
                        .event(SseEventEnums.PING.name())
                        .data(SseEventEnums.PING.getData())
                        .build());
        // 数据业务流
        Flux<ServerSentEvent<Object>> serverSentEventFlux = Flux.create((FluxSink<ServerSentEvent<Object>> sink) -> {
            FluxSink<ServerSentEvent<Object>> oldClient = clients.put(clientId, sink);
            if (!ObjectUtils.isEmpty(oldClient)) {
                oldClient.complete();
            }
            sink.onCancel(() -> {
                clients.remove(clientId);
                log.info("{} sse connect cancel", clientId);
            });
        }, FluxSink.OverflowStrategy.DROP);

        // 合并数据推送流和心跳流
        return Flux.merge(heartbeatFlux, serverSentEventFlux).doFinally(signal -> {
            clients.remove(clientId);
        });
    }

    /**
     * 对所有用户更新业务数据（非设备状态）
     * @param gatewayId
     * @param data
     * @param dataType
     */
    public void notifyFronts(String gatewayId, BaseDataDto data, DataType dataType) {
        List<Integer> userIds = userGatewayService.getUserIdsByGatewayId(gatewayId);
        if (CollectionUtils.isEmpty(userIds)) {
            return;
        }
        for (Integer userId : userIds) {
            this.notifyFront(userId + "_" + gatewayId, data, dataType);
        }
    }

    /**
     * 对单个用户更新业务数据（非设备状态）
     * @param clientId
     * @param data
     * @param dataType
     */
    private void notifyFront(String clientId, BaseDataDto data, DataType dataType) {
        FluxSink<ServerSentEvent<Object>> serverSentEventFluxSink = clients.get(clientId);
        if (ObjectUtils.isEmpty(serverSentEventFluxSink)) {
            return;
        }
        try {
            serverSentEventFluxSink.next(
                    ServerSentEvent
                            .builder()
                            .data(data)
                            .event(SseEventEnums.DATA.name() + ":" + dataType.name())
                            .build()
            );
        } catch (Exception e) {
            log.error("notify front error", e);
            clients.remove(clientId);
        }
    }

    /**
     * 更新设备状态
     * @param clientId
     * @param gatewayStatusEnum
     */
    public void updateGatewayStatus(String clientId, GatewayStatusEnum gatewayStatusEnum) {
        FluxSink<ServerSentEvent<Object>> serverSentEventFluxSink = clients.get(clientId);
        if (ObjectUtils.isEmpty(serverSentEventFluxSink)) {
            return;
        }
        try {
            serverSentEventFluxSink.next(
                    ServerSentEvent
                            .builder()
                            .data(gatewayStatusEnum.getState())
                            .event(SseEventEnums.GATEWAY_STATUS.name())
                            .build()
            );
        } catch (Exception e) {
            log.error("update gateway status error", e);
            clients.remove(clientId);
        }
    }

    /**
     * 清理断开的数据流通道
     */
    @PreDestroy
    public void destroy() {
        clients.values().forEach(FluxSink::complete);
        clients.clear();
        log.info("All SSE connections closed");
    }
}
```

## SSE 基本概念

**SSE** 是 HTML5 标准的一种单向 **服务器推送技术**。

客户端（浏览器或其他 HTTP 客户端）发起一次 HTTP 请求，服务器保持这个连接，并 **持续发送事件流**。典型用途：实时数据推送、状态更新、告警通知、股票行情、聊天消息等。

与 WebSocket 对比：

- SSE 是单向（服务器 -> 客户端），WebSocket 双向。
- SSE 基于 HTTP/1.1，自动重连，适合低频更新场景。
- SSE 事件流是文本（text/event-stream），浏览器自带 EventSource 支持。

## 上述代码的 SSE 实现

### （1）维护客户端连接

```java
private static final Map<String, FluxSink<ServerSentEvent<Object>>> clients = new ConcurrentHashMap<>();
```

- `clients` 用于保存所有已连接的客户端。
- **Key**：客户端唯一标识，比如 `"userId_gatewayId"`
- **Value**：`FluxSink`，通过它向客户端推送消息

> 使用 `ConcurrentHashMap` 是为了支持多线程安全访问。

------

### （2）前端连接后端建立通道

```java
@GetMapping(value = "/connect/{userId}/{gatewayId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<Object>> connect(@PathVariable("userId") String userId,
                                             @PathVariable("gatewayId") String gatewayId) { ... }
```

客户端访问 `/sse/connect/{userId}/{gatewayId}` 就建立 SSE 连接。`produces = MediaType.TEXT_EVENT_STREAM_VALUE` 告诉 Spring 这是一个 **事件流**。

#### (a) 心跳流

```java
Flux<ServerSentEvent<Object>> heartbeatFlux = Flux
        .interval(Duration.ofSeconds(15))
        .map(seq -> ServerSentEvent.builder()
                .event(SseEventEnums.PING.name())
                .data(SseEventEnums.PING.getData())
                .build());
```

- 每 15 秒发送一次心跳 `PING`
- 防止连接超时被浏览器或代理关闭

#### (b) 数据流

```java
Flux<ServerSentEvent<Object>> serverSentEventFlux = Flux.create((FluxSink<ServerSentEvent<Object>> sink) -> {
    FluxSink<ServerSentEvent<Object>> oldClient = clients.put(clientId, sink);
    if (!ObjectUtils.isEmpty(oldClient)) {
        oldClient.complete();
    }
    sink.onCancel(() -> {
        clients.remove(clientId);
    });
}, FluxSink.OverflowStrategy.DROP);
```

- `Flux.create()` 创建一个可主动推送事件的流
- 保存 `sink` 到 `clients`，以后就可以通过 `sink.next(...)` 向客户端发送数据
- 如果已有连接，先关闭旧的连接
- 当客户端断开时，通过 `onCancel` 删除 `clients` 中的映射

> `FluxSink.OverflowStrategy.DROP` 是什么？
>
> 它是 Reactor 的一种背压方案，`DROP` 表示当下游处理不过来时，直接丢弃新来的数据。
>
> `OverflowStrategy` 是 Reactor 基于 Reactive Streams 的规范。
>
> 核心思想是下游必须通过 `request(n)` 告诉上游自己能处理多少数据。即，背压（Backpressure）。
>
> 举个例子，假设：
>
> 1. 毫秒产生 100 条数据，而浏览器 1 秒只能处理 100 条。那会发生什么？
>
> 生产速度 >>> 消费速度
>
> 这时就会导致服务内存暴涨、队列堆积、OOM。。。
>
> 所以 Reactor 必须定义：
>
> 当数据堆积时怎么处理？这就是：`OverflowStrategy`
>
> `FluxSink.OverflowStrategy` 常见策略有
>
> - `BUFFER` 缓存所有数据（默认）
> - `DROP` 丢弃新数据
> - `LATEST` 只保留最新
> - `ERROR` 直接抛异常
> - `IGNORE` 忽略背压（危险）
>
> 因此，使用 `FluxSink.OverflowStrategy.DEOP` 如果上游的 request 超出了下游的承载能力。那么新来的 `next()` 会被直接丢。
>
> - 不会缓存
> - 不会报错
> - 不会阻塞

#### (c) 合并心跳和数据流

```java
return Flux.merge(heartbeatFlux, serverSentEventFlux).doFinally(signal -> {
    clients.remove(clientId);
});
```

- 将心跳流和业务数据流合并
- 保证客户端既能收到心跳，也能收到业务数据

------

### （3）向客户端推送数据

#### (a) 推送所有用户的业务数据

```java
public void notifyFronts(String gatewayId, BaseDataDto data, DataType dataType) {
    List<Integer> userIds = userGatewayService.getUserIdsByGatewayId(gatewayId);
    for (Integer userId : userIds) {
        this.notifyFront(userId + "_" + gatewayId, data, dataType);
    }
}
```

- 根据网关 ID 找到所有关联的用户
- 遍历每个用户，调用 `notifyFront` 推送数据

#### (b) 推送单个客户端数据

```java
private void notifyFront(String clientId, BaseDataDto data, DataType dataType) {
    FluxSink<ServerSentEvent<Object>> sink = clients.get(clientId);
    if (sink == null) return;
    sink.next(ServerSentEvent.builder()
                  .data(data)
                  .event(SseEventEnums.DATA.name() + ":" + dataType.name())
                  .build());
}
```

- 通过 `FluxSink.next()` 将 `ServerSentEvent` 发送到客户端
- `event(...)` 指定事件类型，前端可以区分不同类型数据
- 遇到异常或断开连接会移除客户端

------

### （4）更新设备状态

```java
public void updateGatewayStatus(String clientId, GatewayStatusEnum gatewayStatusEnum) {
    FluxSink<ServerSentEvent<Object>> sink = clients.get(clientId);
    if (sink != null) {
        sink.next(ServerSentEvent.builder()
                     .data(gatewayStatusEnum.getState())
                     .event(SseEventEnums.GATEWAY_STATUS.name())
                     .build());
    }
}
```

- 用于单独推送设备状态更新事件
- 逻辑和 `notifyFront` 类似

------

### （5）服务关闭时清理连接

```java
@PreDestroy
public void destroy() {
    clients.values().forEach(FluxSink::complete);
    clients.clear();
}
```

- 当服务停机时，主动关闭所有 SSE 连接
- 防止资源泄漏

------

## 前端使用示例

```javascript
const evtSource = new EventSource("/sse/connect/123/abc");
evtSource.onmessage = function(event) {
    console.log("收到数据:", event.data);
};

evtSource.addEventListener("PING", function(event) {
    console.log("心跳:", event.data);
});

evtSource.addEventListener("DATA:POINTS", function(event) {
    console.log("业务数据:", event.data);
});
```

- `EventSource` 自动处理重连
- 可以通过 `addEventListener` 区分不同类型事件

我们通常使用 Map 来维护 `FluxSink`。那为什么要用 Map？

1. **快速定位客户端**
   - SSE 是 **基于 HTTP 的单向流**，服务端要主动推送消息给某个客户端，就必须有它的 `FluxSink` 或输出流对象。
   - 使用 Map，Key 通常是 `userId`、`clientId` 或 `userId_gatewayId`，Value 是 `FluxSink`。
   - 这样在推送时可以 **O(1) 定位**对应客户端。
2. **支持多客户端**
   - 一个用户可能有多个设备或浏览器标签同时连接 SSE。
   - Map 可以存多个客户端对象，方便统一管理、广播消息或单独推送。
3. **管理生命周期**
   - 客户端断开时，可以直接从 Map 移除。
   - 服务停机时，可以遍历 Map 完成资源释放。

## 核心类讲解

### `ServerSentEvent` — SSE 消息本身

- **作用**：封装 **要推送给前端的数据**，包含事件类型、数据内容、ID 等。
- **对应概念**：水流里的水珠。

常用字段：

| 字段    | 说明                                                   |
| ------- | ------------------------------------------------------ |
| `data`  | 推送给前端的具体数据对象                               |
| `event` | 事件类型（可选），用于前端 `addEventListener` 区分事件 |
| `id`    | 消息 ID，可用于前端断线重连后继续接收                  |
| `retry` | 重试时间，可控制前端 SSE 重连间隔                      |

示例：

```java
ServerSentEvent.builder()
    .event("DATA_UPDATE")
    .data(someData)
    .id("123")
    .build();
```

> 这个对象本身**只是消息载体**，不会主动发送。

### `FluxSink` — SSE 消息发送的出口

- **作用**：服务端 **向前端发送 SSE 消息的接口**，可以调用 `next()` 推送。
- **对应概念**：水管，`FluxSink` 是输出管道，SSE 消息通过它流向客户端。

使用示例：

```java
FluxSink<ServerSentEvent<Object>> sink = ...;
sink.next(ServerSentEvent.builder()
    .event("DATA_UPDATE")
    .data(someData)
    .build());
```

- `next()`：推送一个 `ServerSentEvent` 消息到客户端
- `complete()`：关闭 SSE 连接
- `error(Throwable)`：在流中抛出异常，前端会收到关闭事件

#### 两者关系总结

| 概念              | 角色   | 说明                                    |
| ----------------- | ------ | --------------------------------------- |
| `ServerSentEvent` | 消息   | 要推送的数据内容及元信息                |
| `FluxSink`        | 输出流 | 服务端推送 `ServerSentEvent` 的管道接口 |

**关系**：

```java
ServerSentEvent (消息) --> 通过 FluxSink.next() --> 客户端浏览器 SSE 流
```

### Flux 是什么？

`Flux<T>` 是一个 **异步数据流**，它实现了 `Publisher<T>`，遵循 Reactive Streams 规范，可以发出 0 ~ N 个元素。

核心接口来自：

```java
org.reactivestreams.Publisher
```

Reactive Streams 定义了 3 个核心角色：

| 角色         | 说明               |
| ------------ | ------------------ |
| Publisher    | 数据生产者（Flux） |
| Subscriber   | 数据消费者         |
| Subscription | 连接两者的控制器   |

#### Flux 懒加载

```java
Flux<Integer> flux = Flux.just(1,2,3);
```

这时候什么都没发生。

只有当：

```java
flux.subscribe(...)
```

才真正开始执行。

这叫：

> Lazy execution（惰性执行）

#### Flux 的数据流模型

Flux 运行时会触发：

```bash
subscribe()
   ↓
onSubscribe()
   ↓
request(n)
   ↓
onNext()
   ↓
onComplete() / onError()
```

这是 Reactive Streams 的标准协议。

### Flux 的创建方式

Flux 有两种类型的创建方式：

#### 被动式创建（推荐）

```java
Flux.just()
Flux.fromIterable()
Flux.interval()
Flux.range()
```

这些是 Reactor 自己控制数据生产节奏，不能手动 push 数据。

#### 主动式创建

```java
Flux.create()
Flux.push()
```

这时你可以手动往流里推数据。这就需要 `FluxSink`

#### FluxSink 的本质

`FluxSink<T>` 是 `Flux` 的写入口

允许你主动调用：

- next()
- error()
- complete()

本质是一个桥梁，让外部世界可以往响应式流里发送数据

#### 为什么需要 FluxSink？

因为响应式流是 pull 模型（带背压的），但现实世界是 push 模型，比如：

- 回调函数
- 监听器
- MQ 消息
- SSE 推送
- WebSocket 事件

`FluxSink` 解决了如何把 push 模型转换为响应式流

#### `Flux#create` 的内部逻辑

来看：

```java
Flux.create(sink -> {
    sink.next("A");
});
```

内部发生什么？

1. 创建一个 `FluxCreate` 对象
2. 当 subscribe 时：
   - 创建一个内部 `Emitter`
   - 把 `Emitter` 传给你的 lambda（sink）
3. `sink.next()` 实际调用的是：
   - 下游 `subscriber#onNext`

简化流程：

```bash
sink.next(data)
    ↓
subscriber.onNext(data)
    ↓
HTTP 输出（SSE）
```

#### `FluxSink` 的核心方法

| 方法                      | 作用                 |
| ------------------------- | -------------------- |
| next(T)                   | 推送一个元素         |
| error(Throwable)          | 终止并抛错           |
| complete()                | 正常结束流           |
| onCancel()                | 客户端取消订阅时回调 |
| onDispose()               | 资源释放时回调       |
| requestedFromDownstream() | 查看下游请求数量     |

我们上面是基于 Spring WebFlux 的，当然，传统 Spring MVC 也支持 SSE，但基于 **阻塞式 IO**：

- 核心类：`SseEmitter`
- 使用方式：

```java
@GetMapping("/sse/mvc")
public SseEmitter sseMvc() {
    SseEmitter emitter = new SseEmitter();
    new Thread(() -> {
        try {
            for (int i = 0; i < 5; i++) {
                emitter.send(SseEmitter.event()
                    .name("message")
                    .data("Hello " + i));
                Thread.sleep(1000);
            }
            emitter.complete();
        } catch (Exception e) {
            emitter.completeWithError(e);
        }
    }).start();
    return emitter;
}
```

- **特点**：
  - 每个客户端占一个 Servlet 线程（阻塞），高并发场景线程消耗大
  - API 简单，兼容性好
  - 适合低并发 SSE 推送
