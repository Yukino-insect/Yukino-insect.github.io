+++
date = '2026-09-20T21:00:00+08:00'
draft = false
title = 'Netty 中的 I/O 多路复用：阻塞在哪里，线程又如何分工'
+++

很多人将 `epoll`、`Selector` 或 Netty 与“非阻塞”放在一起后，便顺势得出一个结论：I/O 多路复用不再阻塞，或者 Netty 会把每个网络请求立即交给一个工作线程。这个结论只对了一小部分，剩下的部分恰好最容易导致线上问题。

更准确的结论是：**I/O 多路复用仍是同步 I/O 模型中的一种等待方式。它让少量线程能够阻塞等待许多连接的就绪事件，减少的是“一个空闲连接占一个等待线程”的成本，而不是网络传输、内核处理、数据复制或业务计算的成本。**

放到 Netty 中，还要再补上一句：**默认情况下，`EventLoop` 不只负责等 I/O 事件，也会执行该连接 Pipeline 中的处理器。只有显式配置执行器，或自行提交任务到业务线程池，业务代码才会离开 I/O 线程。**把这两层区分清楚，才谈得上正确地使用 Netty。

## 一、先区分：阻塞的是哪一步

讨论“阻塞 I/O”前，先不要把一次网络请求当作一个不可分割的黑盒。以读取 TCP 数据为例，至少包含两个阶段：

1. **等待数据就绪**：网卡收包、内核协议栈处理后，数据进入 socket 接收缓冲区；在此之前，应用无法读到数据。
2. **实际读取数据**：应用调用 `read`，内核将数据交给用户态缓冲区，调用返回读取结果。

传统阻塞 I/O 中，线程直接调用某个连接的 `read`。如果这个连接暂时没有数据，线程会睡眠，直到该连接可读为止。一个线程通常只能这样等待一个连接。

```text
线程 A -> read(连接 1) -> 等待连接 1 有数据
线程 B -> read(连接 2) -> 等待连接 2 有数据
线程 C -> read(连接 3) -> 等待连接 3 有数据
```

这并不意味着 CPU 一直在忙；被阻塞的线程通常会被内核挂起。但当服务器维持几万条大多数时间空闲的连接时，为每条连接准备线程会带来大量线程栈内存、调度和上下文切换成本。

### I/O 多路复用把“等谁”交给内核

在 I/O 多路复用模型中，socket 会先被设为非阻塞，并注册给 `select`、`poll`、`epoll` 等就绪通知机制。应用线程不再轮流对每个连接调用 `read`，而是调用类似 `epoll_wait` 的接口，等待**一组连接**中任意连接发生事件。

```text
事件循环线程
    |
    +-> epoll_wait / Selector.select()  -- 阻塞等待任意连接就绪
    |
    +-> 获得“连接 7 可读、连接 12 可读”
    |
    +-> 对连接 7、12 执行非阻塞 read / write
    |
    +-> 继续等待下一批事件
```

所以，“多路复用是阻塞还是非阻塞”并不是一个可以脱离对象回答的问题：

- 对**被监听的 socket**，通常使用非阻塞模式。就绪后调用 `read`，若暂时没有数据不会把事件循环长期卡住，而是返回 `0` 或 `EAGAIN` 一类结果。
- 对**事件循环线程**，`epoll_wait` 或 Java `Selector.select()` 可以阻塞。它在等待内核报告就绪事件时不会做别的事。
- 对**整个模型**，它通常归入同步 I/O 的 I/O 多路复用模型：应用仍需在收到就绪通知后主动读取和写入数据，并自行推进协议解析。

把“事件循环可以阻塞等待事件”误说成“系统退化为一连接一线程”，显然不对；反过来，把“socket 非阻塞”误说成“没有线程会阻塞”，同样不对。术语本身没有问题，含混的表述才有问题。

## 二、多路复用没有消灭哪些成本

`epoll` 的价值不是让 I/O 凭空消失。它主要降低了大量连接处于空闲状态时的**等待与调度成本**，并能高效地把已就绪连接交给应用处理。以下工作仍然真实发生：

| 环节 | 是否由多路复用消除 | 说明 |
| ---- | ------------------ | ---- |
| 网卡接收、DMA、中断或轮询 | 否 | 数据仍必须从网络到达主机内存。 |
| TCP/IP 协议处理 | 否 | 校验、重组、确认、拥塞控制等仍由内核执行。 |
| 用户态与内核态切换 | 否 | `epoll_wait`、`read`、`write` 等仍是系统调用或相应运行时操作。 |
| 数据复制与缓冲管理 | 否 | 读写路径仍有缓冲区和数据移动；具体次数受 API、平台与零拷贝技术影响。 |
| HTTP 解码、序列化、加密 | 否 | 这些是应用或框架需要完成的 CPU 工作。 |
| 数据库、RPC、磁盘访问 | 否 | 下游慢，网络 I/O 再高效也不能替业务完成等待。 |

因此，连接数很多但活跃连接很少时，I/O 多路复用特别有利；而请求一到就要进行长时间计算、同步查库或阻塞 RPC 时，瓶颈会转移到业务执行与下游资源。把后者塞进事件循环线程，等于亲手把节省下来的线程资源浪费掉，多少有些本末倒置。

## 三、Netty 的两组 EventLoop：接收连接与处理连接

基于 Java NIO 的 Netty 服务端常创建两组 `NioEventLoopGroup`：

- `bossGroup`：关注监听 socket 的 `OP_ACCEPT` 事件，接收新 TCP 连接。
- `workerGroup`：管理已建立连接的读、写、连接关闭等 I/O 事件，并运行这些连接的 Pipeline。

下面是一个简化的结构图：

```text
客户端
  |
  v
监听端口 --可接受--> boss EventLoop
                         |
                         +-- accept 后将 Channel 注册给某个 worker EventLoop
                                                          |
                                                          v
                                             Selector / epoll 等待读写事件
                                                          |
                                                          v
                                      解码器 -> 业务 Handler -> 编码器 -> 写回
```

这里的 `workerGroup` 容易被误称为“业务工作线程池”，但默认情况下它不是这个含义。根据 Netty 的 `EventLoop` 约定，一个 `EventLoop` 在 `Channel` 注册后负责该 `Channel` 的全部 I/O；一个 `EventLoop` 通常会管理多个 `Channel`。`NioEventLoop` 则是在单线程事件循环中将多个 `Channel` 注册给 `Selector` 并进行多路复用。[Netty EventLoop API](https://netty.io/4.1/api/io/netty/channel/EventLoop.html) 与 [NioEventLoop API](https://netty.io/4.1/api/io/netty/channel/nio/NioEventLoop.html) 对此有明确说明。

这带来一个非常重要的性质：**同一条连接上的事件通常由同一个 EventLoop 串行执行。**这样可以减少同一 `Channel` 上的并发协调，也使 Pipeline 中大量状态不必处处加锁。但代价是，该 EventLoop 上任意一个处理器运行太久，都会拖慢它管理的其他连接。

## 四、Netty 默认并不会自动把请求分发到业务线程

先看一个最常见的启动方式：

```java
EventLoopGroup bossGroup = new NioEventLoopGroup(1);
EventLoopGroup workerGroup = new NioEventLoopGroup();

new ServerBootstrap()
        .group(bossGroup, workerGroup)
        .channel(NioServerSocketChannel.class)
        .childHandler(new ChannelInitializer<SocketChannel>() {
            @Override
            protected void initChannel(SocketChannel channel) {
                channel.pipeline()
                        .addLast(new HttpServerCodec())
                        .addLast(new HttpObjectAggregator(64 * 1024))
                        .addLast(new RequestHandler());
            }
        });
```

在这段代码中，`RequestHandler.channelRead0` 默认就在该连接所属的 **worker EventLoop 线程**上执行。它并不会因为“HTTP 请求已就绪”就被 Netty 自动提交到一个独立的业务线程池。

因此，下面这种写法会阻塞 EventLoop：

```java
@Override
protected void channelRead0(ChannelHandlerContext ctx, FullHttpRequest request) {
    String result = jdbcTemplate.queryForObject(
            "select slow_operation()", String.class); // 可能等待很久
    ctx.writeAndFlush(response(result));
}
```

阻塞的并非 `Selector.select()` 正在等待事件，而是处理器在占用事件循环线程。事件循环此时不能及时处理其余连接的可读、可写、心跳和关闭事件；如果这个线程管理的连接很多，尾延迟会一起变差。

同样需要避免的还有：长时间 `sleep`、同步文件 I/O、阻塞式 HTTP/RPC 调用、锁竞争严重的代码，以及无法快速结束的大量 CPU 计算。非阻塞网络框架不会把阻塞业务自动变成非阻塞业务，框架没有这种近乎魔法的职责。

## 五、何时以及怎样把业务卸载出去

如果 Handler 中的工作无法在很短时间内完成，常见做法是为该 Handler 指定独立的 `EventExecutorGroup`。这样网络收发、编解码仍留在 `workerGroup`，而指定 Handler 的回调转移到业务执行器。

```java
EventLoopGroup bossGroup = new NioEventLoopGroup(1);
EventLoopGroup workerGroup = new NioEventLoopGroup();
EventExecutorGroup businessGroup = new DefaultEventExecutorGroup(16);

new ServerBootstrap()
        .group(bossGroup, workerGroup)
        .channel(NioServerSocketChannel.class)
        .childHandler(new ChannelInitializer<SocketChannel>() {
            @Override
            protected void initChannel(SocketChannel channel) {
                channel.pipeline()
                        .addLast(new HttpServerCodec())
                        .addLast(new HttpObjectAggregator(64 * 1024))
                        .addLast(businessGroup, "business", new RequestHandler());
            }
        });
```

此时的职责边界可以概括为：

```text
worker EventLoop
  1. 等待就绪事件
  2. 读取 socket、编解码、驱动 Pipeline
  3. 将 business Handler 的回调安排到 businessGroup

businessGroup
  4. 执行可能阻塞或耗时的业务逻辑
  5. 调用 ctx.writeAndFlush(...) 产生响应

worker EventLoop
  6. 在所属 Channel 的事件循环中完成实际写出
```

`ctx.writeAndFlush(...)` 可以从业务线程调用；Netty 会保证把跨线程的 Channel 操作安全地安排回合适的事件循环。这里仍应把网络状态修改、Pipeline 结构调整等操作尽量保持在 EventLoop 语义中理解，不要因为“可以跨线程调用”就随意共享可变状态。

### 卸载不是免费的，也不是越多越好

业务卸载增加了任务排队、线程切换和线程间通信成本，并可能使不同连接的完成顺序交错。因此，轻量的协议解析、简单路由、参数校验和很短的内存计算，通常直接留在 EventLoop 更合适。

更重要的是，业务线程池必须有容量规划和过载策略：

- 线程数应依据任务是 CPU 密集还是经常等待下游资源来设置，不能只按连接数设置。
- 队列不能被当作无限缓冲区；请求积压会抬高延迟并最终耗尽内存。
- 当数据库、RPC 等下游已经慢下来时，需要限流、超时、熔断或拒绝策略，而不是只增加线程。
- 大请求体、慢客户端和写缓冲积压还要配合背压与连接级流量控制处理。

所以，正确的架构不是“所有请求一律先切到业务线程”，而是：**让 EventLoop 保持短小、可预测；仅将确实会阻塞或明显耗时的工作卸载到受控的执行器。**

## 六、一次请求在 Netty 中实际如何流动

假设客户端向服务端发送一个 HTTP 请求，业务需要访问数据库。一个较为准确的时序如下：

```text
1. 数据报到达网卡，内核 TCP 栈将有效负载放入 socket 接收缓冲区
2. 内核标记该连接可读，并唤醒正在 select/epoll_wait 的 EventLoop
3. worker EventLoop 取得就绪 Channel，执行非阻塞读取
4. Netty 将字节流经过 HTTP 解码器，形成完整请求对象
5. RequestHandler 被安排到 businessGroup，执行数据库访问
6. 业务线程得到结果，调用 writeAndFlush 创建响应
7. Channel 所属 EventLoop 将响应写入 socket；若暂时不可写，等待下一次写就绪
8. 内核协议栈负责后续 TCP 发送、确认与重传
```

第 2 步中 EventLoop 的阻塞等待，是 I/O 多路复用模型的正常组成部分；第 5 步中的数据库等待，则是业务层阻塞，需要隔离或改用异步客户端。二者不能混为一谈。至于第 8 步，网络传输和协议处理更不会因 Java 代码使用了 Netty 而不再耗费时间。

## 七、几个常见误解

### 误解一：使用 `epoll` 后，`read` 一定不会阻塞

在边缘条件、竞争或读取策略不当时，就绪状态可能在真正读取前变化。因此事件驱动服务器通常将 socket 配成非阻塞，并把“暂时不可读”作为正常结果处理。就绪通知表示“现在值得尝试 I/O”，不是“永远保证读到完整业务消息”。TCP 是字节流，一个 HTTP 请求也可能被拆成多次读取。

### 误解二：一个请求对应一个 EventLoop 线程

不是。一个 `EventLoop` 常管理多个 `Channel`；一条连接被注册后通常绑定到其中一个 EventLoop。线程数的目标是与 CPU、负载特征和运行时开销相匹配，不是与连接数或请求数一一对应。

### 误解三：`bossGroup` 和 `workerGroup` 就等于“IO 线程池 + 业务线程池”

不等于。`bossGroup` 主要接受连接，`workerGroup` 主要处理已连接 socket 的 I/O，且默认也执行 Pipeline Handler。业务线程池是额外设计的组件，例如上例的 `businessGroup`，或者应用自行管理的受控执行器。

### 误解四：I/O 多路复用天然更快

它并非单连接低延迟的万能优化。连接很少、处理逻辑简单时，传统阻塞 I/O 的实现可能更直接；多路复用的优势主要出现在需要维持大量并发连接、而多数连接并不持续活跃的场景。性能结论应来自压测与剖析，不应来自对名词的迷信。

## 八、总结

读完后，至少应能分清以下几点：

- I/O 多路复用让一个线程阻塞等待**多个**连接的就绪事件，它没有消除阻塞，只是改变了阻塞等待的组织方式。
- 它节省的是空闲连接对应的线程、调度和无效轮询成本；网络收发、协议处理、复制、编解码与业务访问仍然有成本。
- Netty 的 `NioEventLoop` 将多条连接复用到一个 Selector 上，并在默认情况下同时执行 I/O 和 Pipeline 回调。
- `workerGroup` 不是自动的业务线程池。任何可能长时间阻塞或明显耗时的 Handler，都应显式卸载到有边界、有过载策略的业务执行器。
- 让 EventLoop 做短而确定的事，把慢业务隔离出去，才是 Netty 高并发模型真正有效的使用方式。

参考资料：

- [Netty EventLoop API](https://netty.io/4.1/api/io/netty/channel/EventLoop.html)
- [Netty NioEventLoop API](https://netty.io/4.1/api/io/netty/channel/nio/NioEventLoop.html)
