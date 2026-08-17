+++
date = '2025-10-07T15:35:58+08:00'
draft = false
title = 'Seata'
+++

为什么需要分布式事务？

在单体应用中，例如一个单体的 Spring Boot + MySQL 系统，所有业务逻辑、数据库操作都在同一个服务中完成，只要使用 **数据库事务（ACID）**

```java
@Transactional
public void createOrder() {
    saveOrder();
    reduceStock();
    deductBalance();
}
```

就可以保证上面这三个操作的事务一致性。

这是**本地事务（Local Transaction）**，非常简单、可靠。

> 本地事务只能保证同一个数据库的事务一致性，不能保证多个数据库事务的一致性
>
> 本地事务指在 **同一个数据库连接（Connection）**中执行的事务。由数据库自身提供的 **ACID（原子性、一致性、隔离性、持久性）**保证事务一致性
>
> 但一般在分布式系统中，往往每一个服务都会有各自的数据库，不会将所有的数据都存放在一个数据库中。因此本地事务不能保证同时操作多个数据库的事务一致性

但是在微服务中，业务往往被拆成多个独立服务

例如：

| 服务            | 功能         |
| --------------- | ------------ |
| order-service   | 负责订单创建 |
| product-service | 负责库存管理 |
| account-service | 负责余额扣减 |

那么一个下单操作，可能需要：

1. 订单服务创建订单；
2. 商品服务扣减库存；
3. 用户服务扣减余额。

这些服务 **不在同一个数据库**，甚至不在同一台机器上。

所以，**本地事务无法跨服务生效**。

因此，分布式事务就是解决一下问题的

假设你下单时发生以下情况：

| 步骤 | 服务     | 操作     | 状态             |
| ---- | -------- | -------- | ---------------- |
| 1    | 订单服务 | 创建订单 | 成功             |
| 2    | 商品服务 | 扣减库存 | 成功             |
| 3    | 用户服务 | 扣减余额 | 失败（余额不足） |

最后的结果却是：

订单表有记录，库存减少了了，但余额没扣。导致 **数据不一致！**

系统出现了脏数据，后续难以修复。

但如果引入了 **分布式事务**

在分布式系统中，就可以保证多个服务或数据库操作的 **最终一致性**。

### 常见的分布式事务解决方案

#### 两阶段提交（2PC / XA 模式）

**原理：**

- 阶段一（Prepare）：协调者让各参与方预执行并锁定资源；

- 阶段二（Commit/Rollback）：协调者决定提交或回滚。

该方案理论上能实现**强一致性**，并且对业务代码无侵入。

但是它是阻塞式的，性能差，协调者单点问题严重，并不适合高并发场景。

#### TCC 模式（Try-Confirm-Cancel）

**核心思路：**

- Try：预留资源；
- Confirm：确认并提交；
- Cancel：取消预留。

看一个转账例子

- Try：冻结 A、B 账户金额；
- Confirm：真正扣款、入账；
- Cancel：释放冻结金额。

该模式的业务可控、性能好，也能保证强一致。

但是业务代码入侵较大，开发成本高。

#### Saga 模式（补偿事务）

**核心思路：**

- 把大事务拆分为多个本地事务；
- 每个事务执行后，若后续失败，则执行相应的 **补偿操作**。

看一个订单例子

1. 创建订单；
2. 扣库存；
3. 扣余额；
   - 若扣余额失败 **则** 补偿库存、取消订单。

该模式是非阻塞，适合长流程。

但是只能保证 **最终一致性**，而且需要设计补偿逻辑。

#### 本地消息表（Outbox / 事务消息）

**核心思路：**

- 在本地事务中 **同时写业务数据和消息表**；
- 再异步投递消息至 MQ；
- 消费端处理失败可重试，确保 **最终一致性**。

再看一个下单例子

- 下单的同时，写订单表 + 消息表；
- 消息服务异步发送 MQ 通知库存系统。

该模式是高性能，没有协调者，可靠性高，且实现相对简单。

但是消息表需要清理，只保证最终一致性。

#### Seata AT 模式

它是比较主流的方案。该模式对传统的 2PC 模式做了改进，实现了 **非阻塞的 2PC 效果**

在不同场景下选择的方案

| 场景                       | 推荐方案      |
| -------------------------- | ------------- |
| 强一致核心业务（银行转账） | TCC 或 XA     |
| 长流程、可补偿业务（下单） | Saga          |
| 异步最终一致（MQ 通知）    | 本地消息表    |
| 常规微服务数据库事务       | Seata AT 模式 |

接下来详细讲解一下 Seata

### Seata

Seata 是阿里/Apache 社区的开源分布式事务框架，提供 **AT / TCC / SAGA / XA** 等多种事务模型以满足不同场景。

它的三大组件

- TC（Transaction Coordinator）：事务协调器，维护全局和分支事务的状态，负责协调并驱动全局事务的提交或回滚
- TM（Transaction Manager）：事务管理器，控制全局事务的边界，负责开启一个全局事务，并最终发起全局提交或全局回滚的决议
- RM（Resource Manager）：资源管理器，负责管理分支事务上的资源，向 TC 注册分支事务，上报分支事务的状态，接受 TC 的命令来提交或者回滚分支事务

> - TC（事务协调器）：就是 Seata 自身，负责维护全局事务和分支事务的状态，驱动全局事务提交或回滚。
> - TM（事务管理器）：就是标注全局事务注解 `@GlobalTransactional` 启动入口动作的微服务模块（比如订单模块），它是事务的发起者，负责定义全局事务的范围，并根据 TC 维护的全局事务和分支事务状态，作出开启全局事务、提交全局事务、回滚全局事务的决议。
> - RM（资源管理器）：就是 MySQL 数据库本身，可以有多个 RM，负责管理分支事务上的资源，向 TC 注册分支事务，上报分支事务状态，接受 TC 的命令来提交或者回滚分支事务。

常用模式

- **AT（Automatic Transaction）**：Seata 最常用、对业务侵入最小的模式。通过拦截 JDBC（DataSourceProxy），记录 `undo_log`（before-image），在全局提交时执行两阶段提交逻辑或回滚时用 undo_log 回滚。适合关系型数据库的典型场景
- **TCC（Try-Confirm-Cancel）**：业务接口需分成 Try/Confirm/Cancel，适合对业务语义要求明确并能实现补偿的场景。
- **SAGA**：编排/补偿式方案，适合长事务或参与方无法改造为 TCC 的情况。
- **XA**：使用数据库原生 XA 支持，通常侵入更小但依赖数据库驱动与性能/可用性考虑。

>  选择原则：简单的 CRUD 跨库一致性优先用 **AT**；需要业务级补偿或长流程用 **SAGA/TCC**；跨异构事务且能接受 XA 的复杂性可考虑 **XA**

这里只说一下 AT 模式的核心要点，以后的见到了再学

- **DataSourceProxy 拦截 SQL**：Seata 把应用的数据源用 `DataSourceProxy` 或自动代理包装，拦截 SQL 执行。代理会记录操作的前镜像/后镜像并写入本地 `undo_log`（用于回滚）。执行本地 SQL 时是立刻提交的，但分支事务的最终一致性由 TC 协调。

- **分支注册 + XID**：当某微服务在全局事务中执行 DB 操作时，它向 TC 注册分支事务（带 XID），TC 在全局提交时会协调分支提交或回滚。

>  AT 模式虽然表现不是完全经典的 2PC，整体由 TC 驱动全局决策，RM 根据 TC 的决定执行提交或用 undo_log 回滚。

##### 在 Spring 项目中集成 Seata

引入依赖

```xml
<dependency>
  <groupId>org.apache.seata</groupId>
  <artifactId>seata-spring-boot-starter</artifactId>
  <version>2.5.0</version>
</dependency>
```

##### 配置 DataSourceProxy

- **自动代理（starter 默认打开）**：seata starter 会自动代理 DataSource（auto proxy），通常不用手工创建代理 bean；自动代理可以通过配置关闭。若手动创建 `DataSourceProxy` bean，请把 `seata.enable-auto-data-source-proxy=false` 关掉，避免重复代理导致问题。
- **手动代理** 需要自己注册 Bean

`DataSourceProxy` 是 **Seata 客户端对数据库连接池的代理类**，位于包：

```java
import io.seata.rm.datasource.DataSourceProxy;
```

它的作用是 **拦截业务系统对数据库的操作（Connection、PreparedStatement 等），记录 `undo log` 并向 TC 汇报事务分支信息。**

通俗的讲，它把原本的数据库连接池（如 Druid、HikariCP）包装了一层。这层代理能在 SQL 执行前后插入 **Seata 的分布式事务控制逻辑**。

**Seata AT 模式依赖本地数据库的 undo_log 表来实现自动回滚**。

>  因此 **必须** 在参与数据库中创建 `undo_log` 表（Seata 提供样例 SQL），这是回滚依赖的本地日志。

假设业务是这样：

```java
@Transactional
public void createOrder() {
    orderMapper.insert(order);
    accountFeignClient.decreaseBalance(userId, amount);
}
```

如果两个服务都在 Seata 全局事务中，Seata 必须在：

- 每个本地数据库执行 SQL 前后，记录数据修改前后的镜像；
- 一旦分支回滚，能根据 undo_log 自动回滚本地事务。

这一切都是由 **`DataSourceProxy` 自动完成** 的。

> 只有通过 `DataSourceProxy` 获取的数据库连接，Seata 才能感知、记录、回滚 SQL。

如果使用原生的 `DataSource`，未经 `DataSourceProxy` Seata 根本拦不住 SQL，也就无法回滚。

手动配置 `DataSourceProxy`

```java
@Configuration
public class DataSourceConfig {
    
    // 原生数据库连接池
    @Bean
    @ConfigurationProperties(prefix = "spring.datasource")
    public DataSource hikariDataSource() {
        return new HikariDataSource();
    }

    // 包装
    @Primary
    @Bean("dataSource")
    public DataSourceProxy dataSourceProxy(DataSource hikariDataSource) {
        return new DataSourceProxy(hikariDataSource);
    }
}
```

##### 配置 application.yml

> 注意：不同 Seata 版本属性名可能有差异，下面示例是常见写法

```yaml
spring:
  application:
    name: order-service
seata:
  application-id: order-service
  tx-service-group: order-service-tx-group
  enable-auto-data-source-proxy: true  # starter 默认 true
  service:
    vgroup-mapping:
      order-service-tx-group: default
```

##### 在业务代码开启全局事务

```java
import io.seata.spring.annotation.GlobalTransactional;
@Service
public class OrderService {

    @Autowired
    private InventoryClient inventoryClient; // 微服务调用

    @GlobalTransactional(name = "create-order-tx", rollbackFor = Exception.class)
    public void createOrder(OrderDTO dto) {
        // 本地数据库写入（被 DataSourceProxy 拦截并记录 undo_log）
        orderRepo.insert(...);

        // 远程服务（如库存）会通过 Feign/Rest 被自动带上 XID 并参与到同一全局事务
        inventoryClient.decreaseStock(...);
    }
}
```

> ##### 现在区分一下 `@GlobalTransactional` 和 `@Transactional` 的作用
>
> 要清楚使用`@GlobalTransactional` 后，这个方法的调用链路上所有访问数据库的操作，只要通过 **Seata 的代理数据源（`DataSourceProxy`）**，都会成为 **分支事务**
>
> 分支事务是如何被注册的？
>
> 整个过程如下 ：
>
> 1. **TM 开启全局事务：**
>    - `@GlobalTransactional` 触发 TM 开启一个全局事务。
>    - TM 向 TC 申请一个 `XID`（全局事务 ID）。
>    - 这个 `XID` 被绑定到当前线程上下文中（`RootContext.bind(xid)`）。
> 2. **业务调用中访问数据库：**
>    - 当 RM（数据库代理，即 `DataSourceProxy`）检测到当前线程有 `XID` 时，
>    - 它会自动向 TC 注册一个 **分支事务**。
> 3. **RM 执行 SQL 时：**
>    - Seata 会记录本地 `undo_log`（用于回滚的数据快照）。
>    - 事务提交时，Seata 通知 TC 分支提交。
>    - 如果全局回滚，TC 通知 RM 根据 `undo_log` 回滚数据库。
>
> > 即，分支事务的注册是由 `DataSourceProxy` 自动完成的，而不是由 `@Transactional` 决定的。
>
> `@Transactional` 起了什么作用？
>
> `@Transactional` 是 **Spring 本地事务**。
>  它的主要作用是：
>
> - 保证**方法内部多个 SQL 操作的原子性（在同一个 Connection 下）**；
> - 控制 **commit / rollback**。
>
> 而在 **Seata AT 模式**下，Seata **会接管 Connection 的 commit/rollback**，但是 `@Transactional` 依然有用，它能让多个 SQL 共用同一个数据库连接，没有它，多个 SQL 可能使用不同连接，**导致每个 SQL 被视为独立的分支事务**。

##### 注意 RPC（Feign/Rest）中 XID 的传播

Seata 对主流 RPC（Dubbo、gRPC、Spring Cloud/Feign/RestTemplate）提供集成/拦截器，负责把 XID 放到请求头并在提供端恢复（绑定 `RootContext`）。如果使用的是非标准链路或自定义客户端，需要确保把 XID （或整个 RootContext）在调用时带上；否则分支就不会参与全局事务。

接下来详细看一下：

当使用 `@GlobalTransactional` 开启全局事务时：

- Seata 会生成一个全局事务 ID（`XID`）。
- 这个 XID 会绑定到当前线程（`RootContext.bind(xid)`）。
- 只要调用链路中的下游服务也能拿到这个 XID，并且数据库连接被 Seata 的 `DataSourceProxy` 代理，就能自动注册成一个 **分支事务**。

但如果 XID 没有传过去，下游服务的事务就只是普通的本地事务，不会被 Seata 管控。

一下是自动在请求中添加 XID 进行全局传递的客户端

| 框架                                                | 是否自动透传 XID | 说明                                                         |
| --------------------------------------------------- | ---------------- | ------------------------------------------------------------ |
| **Dubbo（官方支持）**                               | 自动透传         | Seata 提供了 `seata-dubbo` 模块，会自动在请求头中添加/解析 XID。 |
| **Spring Cloud Alibaba (OpenFeign + RestTemplate)** | 自动透传         | 如果引入了 `seata-spring-boot-starter`，默认会为 Feign 和 RestTemplate 注册拦截器。 |
| **gRPC（Seata 1.6+）**                              | 自动透传         | 需引入 `seata-grpc` 模块，内部使用 `ClientInterceptor` 自动添加 XID。 |

Seata **不会自动透传 XID** 的情况

以下框架或调用方式 **默认不会** 自动传递 XID，需要手动注册拦截器。

| 场景 / 框架                                 | 是否自动透传 | 解决方案                                                     |
| ------------------------------------------- | ------------ | ------------------------------------------------------------ |
| **原生 HTTP 调用（如 OkHttp、HttpClient）** | 否           | 手动在请求头中添加 `"TX_XID"`： `request.addHeader(RootContext.KEY_XID, RootContext.getXID())` |
| **gRPC（未引入 seata-grpc 模块）**          | 否           | 手动实现 `ClientInterceptor` 注入 XID                        |
| **WebClient (Reactor)**                     | 否           | 需自定义 `ExchangeFilterFunction` 添加请求头                 |
| **Kafka / RocketMQ / RabbitMQ 消息传递**    | 否           | Seata 不会自动传播 XID 到消息中，需要你在发送消息时手动携带 XID，并在消费端手动绑定 `RootContext.bind(xid)` |
| **自定义 RPC 框架 / Netty 通信**            | 否           | 需要自己定义协议字段传递 XID                                 |

介绍几个手动定义拦截器添加 XID 的例子

Feign 自定义拦截器（如果你用的是原生 Feign 而非 Spring Cloud Alibaba）

```java
@Component
public class SeataFeignInterceptor implements RequestInterceptor {
    @Override
    public void apply(RequestTemplate template) {
        String xid = RootContext.getXID();
        if (xid != null) {
            template.header(RootContext.KEY_XID, xid);
        }
    }
}
```

> `RootContext` 是 Seata 的核心类，用来保存 **全局事务上下文信息（主要是 XID）**。
>
> 可以理解为：
>
> > Seata 通过 `RootContext` 在当前线程中保存当下属于哪个全局事务。
>
> 具体实现：
>
> ```java
> public class RootContext {
>     private static final ThreadLocal<String> CONTEXT_HOLDER = new ThreadLocal<>();
> 
>     public static void bind(String xid) {
>         CONTEXT_HOLDER.set(xid);
>     }
> 
>     public static String getXID() {
>         return CONTEXT_HOLDER.get();
>     }
> 
>     public static void unbind() {
>         CONTEXT_HOLDER.remove();
>     }
> }
> ```
>
> - `bind(xid)`：绑定当前线程的 XID；
> - `getXID()`：获取当前线程的 XID；
> - `unbind()`：清除线程中的 XID（通常在请求完成后）

RestTemplate 拦截器

```java
@Bean
public RestTemplate restTemplate() {
    RestTemplate restTemplate = new RestTemplate();
    restTemplate.getInterceptors().add((request, body, execution) -> {
        String xid = RootContext.getXID();
        if (xid != null) {
            request.getHeaders().add(RootContext.KEY_XID, xid);
        }
        return execution.execute(request, body);
    });
    return restTemplate;
}
```

消息队列场景（RocketMQ 示例）

**发送消息时：**

```java
String xid = RootContext.getXID();
Message msg = new Message("topic", "tag", ("Hello").getBytes());
msg.putUserProperty(RootContext.KEY_XID, xid);
rocketMQTemplate.syncSend("topic", msg);
```

**消费消息时：**

```java
@RocketMQMessageListener(topic = "topic", consumerGroup = "testGroup")
public class TestConsumer implements RocketMQListener<MessageExt> {
    @Override
    public void onMessage(MessageExt message) {
        String xid = message.getUserProperty(RootContext.KEY_XID);
        if (xid != null) {
            RootContext.bind(xid);
        }
        // ... 执行业务逻辑
        RootContext.unbind();
    }
}
```
