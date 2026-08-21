+++
date = '2025-09-18T22:09:15+08:00'
draft = false
title = 'Spring WebFlux 底层'
+++

Spring WebFlux 是 Spring 5 引入的响应式 Web 框架。它和 Spring MVC 都能写 HTTP 接口，但底层模型不同：MVC 主要基于 Servlet 阻塞式请求处理，WebFlux 基于 Reactive Streams、Reactor 和非阻塞 I/O。

一句话概括：**Spring MVC 用线程等待结果，WebFlux 用事件和回调在结果准备好时继续处理**。

## 一、MVC 和 WebFlux 的差异

先看最核心的差异：

| 对比项 | Spring MVC | Spring WebFlux |
| --- | --- | --- |
| 编程模型 | Servlet 阻塞式模型 | Reactive Streams 响应式模型 |
| 常见容器 | Tomcat、Jetty、Undertow | Reactor Netty，也可运行在支持异步的 Servlet 容器 |
| 线程模型 | 通常一个请求占用一个工作线程直到返回 | 少量事件循环线程处理大量连接 |
| 返回类型 | 普通对象、`Callable`、`DeferredResult` | `Mono`、`Flux` |
| 适合场景 | 大多数传统 CRUD、同步业务 | 高并发长连接、流式响应、非阻塞 I/O 聚合 |
| 关键风险 | 线程池耗尽 | 阻塞调用污染事件循环 |

WebFlux 不是 MVC 的“升级版”，而是另一套模型。普通业务系统如果主要访问阻塞式数据库和同步 RPC，直接迁移到 WebFlux 未必会更快。框架不是魔法，尤其不是替阻塞代码赎罪的魔法。

## 二、Reactive Streams

WebFlux 的底层契约来自 Reactive Streams，它定义了异步流处理中的四个角色：

| 接口 | 作用 |
| --- | --- |
| `Publisher` | 发布数据 |
| `Subscriber` | 订阅并消费数据 |
| `Subscription` | 表示订阅关系，可请求数据或取消 |
| `Processor` | 同时是发布者和订阅者，用于中间处理 |

关键点是**背压**。消费者可以通过 `Subscription#request(n)` 告诉生产者自己最多还能处理多少数据，避免生产速度远大于消费速度。

简化流程如下：

```text
Subscriber subscribe Publisher
 -> Publisher 调用 onSubscribe(subscription)
 -> Subscriber 调用 request(n)
 -> Publisher 推送 onNext(data)
 -> 完成时调用 onComplete()
 -> 出错时调用 onError(error)
```

WebFlux 上层的 `Mono` 和 `Flux` 就是 Reactor 对 Reactive Streams 的实现。

## 三、Mono 和 Flux

Reactor 中最常见的两个类型：

- `Mono<T>`：表示 0 到 1 个异步结果。
- `Flux<T>`：表示 0 到 N 个异步结果。

示例：

```java
@GetMapping("/users/{id}")
public Mono<UserVO> getUser(@PathVariable Long id) {
    return userService.findById(id);
}
```

流式返回：

```java
@GetMapping(value = "/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<String>> events() {
    return Flux.interval(Duration.ofSeconds(1))
            .map(sequence -> ServerSentEvent.builder("tick-" + sequence).build());
}
```

`Mono` 和 `Flux` 是惰性的。只有被订阅后，数据流才会开始执行：

```java
Mono<String> mono = Mono.fromSupplier(() -> {
    System.out.println("execute");
    return "data";
});

// 这里才真正触发执行
mono.subscribe(System.out::println);
```

在 WebFlux Controller 中，框架会替你订阅返回的 `Mono` 或 `Flux`，并把结果写入 HTTP 响应。

## 四、请求处理流程

WebFlux 的请求处理链路可以简化成：

```text
HTTP request
 -> HttpHandler
 -> WebHandler
 -> HandlerMapping
 -> HandlerAdapter
 -> Controller / RouterFunction
 -> HandlerResultHandler
 -> HttpMessageWriter
 -> HTTP response
```

常见组件：

| 组件 | 作用 |
| --- | --- |
| `HttpHandler` | 最底层 HTTP 处理抽象 |
| `WebHandler` | WebFlux 的核心处理入口 |
| `HandlerMapping` | 找到匹配的处理器 |
| `HandlerAdapter` | 调用处理器 |
| `HandlerResultHandler` | 处理返回值 |
| `HttpMessageReader` | 读取请求体 |
| `HttpMessageWriter` | 写出响应体 |
| `WebFilter` | 类似 Servlet Filter 的 WebFlux 过滤器 |

如果使用注解式 Controller，代码风格和 Spring MVC 很像：

```java
@RestController
@RequestMapping("/users")
public class UserController {

    @GetMapping("/{id}")
    public Mono<UserVO> get(@PathVariable Long id) {
        return userService.get(id);
    }
}
```

如果使用函数式路由，则写法更接近显式组合：

```java
@Bean
RouterFunction<ServerResponse> routes(UserHandler handler) {
    return RouterFunctions.route()
            .GET("/users/{id}", handler::get)
            .build();
}
```

## 五、Reactor Netty 线程模型

WebFlux 默认常和 Reactor Netty 搭配。Netty 使用事件循环模型处理网络 I/O。

简化结构：

```text
EventLoopGroup
 -> EventLoop 1
    -> Channel A
    -> Channel B
 -> EventLoop 2
    -> Channel C
    -> Channel D
```

一个 `EventLoop` 通常绑定一个线程，负责多个连接上的 I/O 事件。这样少量线程可以处理大量连接。

关键要求是：**不要在事件循环线程里执行阻塞操作**。

错误示例：

```java
@GetMapping("/{id}")
public Mono<UserVO> get(@PathVariable Long id) {
    User user = jdbcTemplate.queryForObject("select * from user where id = ?", User.class, id);
    return Mono.just(convert(user));
}
```

这段代码使用阻塞式 JDBC 查询，会阻塞 Netty 事件循环线程。连接一多，整个服务会变得迟钝。

如果必须调用阻塞方法，应切换到适合阻塞任务的调度器：

```java
@GetMapping("/{id}")
public Mono<UserVO> get(@PathVariable Long id) {
    return Mono.fromCallable(() -> userRepository.findById(id))
            .subscribeOn(Schedulers.boundedElastic())
            .map(this::convert);
}
```

这只是折中方案，不是最佳模型。更理想的是使用非阻塞客户端，例如 R2DBC、WebClient、响应式 Redis 客户端。

## 六、调度器

Reactor 常见调度器：

| 调度器 | 适合场景 |
| --- | --- |
| `Schedulers.parallel()` | CPU 密集型短任务 |
| `Schedulers.boundedElastic()` | 阻塞 I/O、文件操作、旧 SDK 调用 |
| `Schedulers.single()` | 单线程顺序任务 |
| `Schedulers.immediate()` | 当前线程执行 |

常见写法：

```java
Mono.fromCallable(() -> blockingClient.call())
        .subscribeOn(Schedulers.boundedElastic())
        .timeout(Duration.ofSeconds(3));
```

`subscribeOn` 影响上游订阅和执行线程，`publishOn` 影响后续操作线程：

```java
Mono.fromCallable(this::loadData)
        .subscribeOn(Schedulers.boundedElastic())
        .publishOn(Schedulers.parallel())
        .map(this::calculate);
```

线程切换不是免费的。不要为了“看起来响应式”到处切调度器，那只是把复杂性切成更多片。

## 七、WebClient

WebFlux 生态里推荐使用 `WebClient` 进行非阻塞 HTTP 调用：

```java
public Mono<UserVO> getUser(Long id) {
    return webClient.get()
            .uri("/users/{id}", id)
            .retrieve()
            .bodyToMono(UserVO.class);
}
```

组合多个异步调用：

```java
public Mono<UserDetailVO> getUserDetail(Long id) {
    Mono<UserVO> userMono = userClient.getUser(id);
    Mono<List<OrderVO>> orderMono = orderClient.listOrders(id);

    return Mono.zip(userMono, orderMono)
            .map(tuple -> new UserDetailVO(tuple.getT1(), tuple.getT2()));
}
```

这类 I/O 聚合是 WebFlux 比较擅长的场景：多个远程调用可以并发执行，线程不用阻塞等待。

## 八、错误处理

Reactor 中错误也是数据流的一部分。常见处理方式：

```java
return userService.get(id)
        .switchIfEmpty(Mono.error(new NotFoundException("用户不存在")))
        .onErrorMap(DataAccessException.class, ex -> new SystemException("查询用户失败", ex));
```

兜底返回：

```java
return remoteClient.getUser(id)
        .timeout(Duration.ofSeconds(2))
        .onErrorResume(TimeoutException.class, ex -> Mono.just(UserVO.empty()));
```

全局异常处理可以使用 `@RestControllerAdvice`，但在响应式链路中，不要在中间随意 `block()` 后再抛异常。那样既破坏非阻塞模型，也会让错误栈更难读。

## 九、背压和流式响应

`Flux` 可以表示持续数据流，例如 SSE：

```java
@GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<String>> stream() {
    return Flux.interval(Duration.ofSeconds(1))
            .map(index -> ServerSentEvent.builder("message-" + index)
                    .event("message")
                    .id(String.valueOf(index))
                    .build());
}
```

如果生产速度过快，可以使用背压相关操作：

```java
sourceFlux
        .onBackpressureBuffer(100)
        .sample(Duration.ofMillis(200));
```

常见策略：

- 缓冲一部分数据。
- 丢弃过旧或过新的数据。
- 采样或限速。
- 从源头控制生产速度。

背压不是“无限缓存”。如果消费者长期处理不过来，最终仍要降级、断开或丢弃。

## 十、什么时候该用 WebFlux

适合 WebFlux 的场景：

- 长连接、SSE、流式响应。
- 大量并发连接但单个请求计算量不大。
- 服务需要聚合多个非阻塞远程调用。
- 技术栈中已经有响应式数据库、缓存和 HTTP 客户端。
- 对线程资源占用非常敏感。

不一定适合的场景：

- 主要是传统 CRUD。
- 数据访问基于阻塞式 JDBC。
- 业务代码里大量调用阻塞 SDK。
- 团队对 Reactor 调试和错误处理不熟。
- 只是希望“性能更好”但没有明确瓶颈。

WebFlux 的收益来自端到端非阻塞。如果中间塞满阻塞调用，它就会变成写法更复杂的 MVC。这样的交换并不划算，除非你很喜欢把生活难度调高。

## 十一、常见问题

### 1. 能不能在 WebFlux 中使用 `block()`

技术上可以，实践上应尽量避免。`block()` 会把异步流重新变成阻塞等待，在事件循环线程上调用还可能导致性能问题甚至运行时错误。

### 2. WebFlux 一定比 MVC 快吗

不一定。CPU 密集型业务、阻塞数据库访问、普通 CRUD 接口中，MVC 往往更简单也足够快。WebFlux 的优势主要在高并发 I/O 和流式场景。

### 3. WebFlux 能不能部署到 Tomcat

可以运行在支持 Servlet 3.1+ 异步 I/O 的 Servlet 容器上，但最常见组合是 WebFlux + Reactor Netty。

### 4. Controller 里返回 `Mono` 是否就非阻塞

不一定。关键看 `Mono` 内部有没有阻塞调用。如果内部执行的是 JDBC、文件 I/O、同步 HTTP SDK，那仍然是阻塞的，只是外面套了一个响应式类型。

## 十二、总结

理解 WebFlux 要抓住四点：

- `Mono` 表示 0 到 1 个异步结果，`Flux` 表示 0 到 N 个异步结果。
- WebFlux 基于 Reactive Streams 和 Reactor，支持异步、非阻塞和背压。
- Reactor Netty 依靠事件循环线程处理大量连接，事件循环中不能执行阻塞操作。
- WebFlux 适合端到端非阻塞 I/O、流式响应和高并发连接，不是所有 MVC 项目的默认升级路线。

把 WebFlux 用好，重点不是把返回值全改成 `Mono` 和 `Flux`。真正要改的是思维模型：不要等待结果，而是描述结果到来以后该怎样继续。
