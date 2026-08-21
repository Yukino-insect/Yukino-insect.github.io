+++
date = '2025-10-07T15:35:58+08:00'
draft = false
title = 'Seata 分布式事务'
+++

Seata 是分布式事务框架，常用于解决微服务拆分后多个数据库之间的一致性问题。它提供 AT、TCC、Saga、XA 等事务模式，其中 AT 模式对业务代码侵入较小，是很多 Spring Cloud 项目最先接触的模式。

不过，分布式事务不是越早引入越好。能用本地事务解决的，就不要扩大成分布式事务；能用可靠消息和补偿处理的，也不必强行追求同步全局事务。

## 为什么需要分布式事务

在单体应用中，订单创建、库存扣减、余额扣减可能都在同一个服务、同一个数据库连接里完成：

```java
@Transactional
public void createOrder() {
    saveOrder();
    reduceStock();
    deductBalance();
}
```

这属于本地事务，数据库可以保证 ACID。

拆成微服务后，一个下单流程可能变成：

| 服务 | 职责 | 数据库 |
| --- | --- | --- |
| `order-service` | 创建订单 | 订单库 |
| `inventory-service` | 扣减库存 | 库存库 |
| `account-service` | 扣减余额 | 账户库 |

如果订单创建成功、库存扣减成功，但账户扣款失败，就会出现跨服务数据不一致。本地事务只能覆盖单个数据库连接，无法自动管理其他服务的数据库。

## 常见方案

### XA / 2PC

两阶段提交把事务拆成 Prepare 和 Commit/Rollback 两个阶段。协调者先让所有参与方预提交并锁定资源，再统一决定提交或回滚。

优点是语义接近强一致；缺点是阻塞、锁持有时间长、性能和可用性压力都比较大。

### TCC

TCC 把业务接口拆成 Try、Confirm、Cancel：

- Try：预留资源，例如冻结余额。
- Confirm：确认提交，例如真正扣款。
- Cancel：释放预留，例如解冻余额。

TCC 业务可控性强，但需要业务方显式设计三个动作，侵入性和开发成本都高。

### Saga

Saga 把一个长事务拆成多个本地事务，每一步失败时执行补偿动作。

例如下单流程中，如果扣款失败，就补偿库存并取消订单。Saga 适合长流程和跨系统业务，但只能保证最终一致性，补偿逻辑也必须认真设计。

### Outbox

Outbox 在本地事务中同时写业务表和事件表，再异步发布事件。它适合“数据库更新 + 发消息”的双写问题，性能好、侵入小，但同样是最终一致性。

### Seata AT

AT 模式通过代理数据源拦截 SQL，记录 `undo_log`，并由事务协调器统一决定全局提交或回滚。它对业务代码侵入较低，适合关系型数据库上的常见 CRUD 场景。

## 三个核心角色

Seata 有三个核心角色：

| 角色 | 全称 | 职责 |
| --- | --- | --- |
| TC | Transaction Coordinator | 事务协调器，维护全局事务和分支事务状态 |
| TM | Transaction Manager | 事务管理器，开启、提交或回滚全局事务 |
| RM | Resource Manager | 资源管理器，管理本地资源并注册分支事务 |

在业务调用链中，标注 `@GlobalTransactional` 的入口通常就是 TM。各服务中的数据库代理是 RM。TC 是独立的协调服务，负责根据全局事务状态通知各分支提交或回滚。

## AT 模式流程

AT 模式可以理解成“业务无感的一阶段提交 + 二阶段协调”。

### 一阶段

业务服务执行本地 SQL。Seata 的 `DataSourceProxy` 会拦截数据库操作，记录修改前后的镜像，并把镜像写入本地 `undo_log`。

业务 SQL 和 `undo_log` 在同一个本地事务中提交。提交后，本地锁会释放，但 Seata 会维护全局锁，避免其他全局事务修改同一批数据。

### 二阶段提交

如果全局事务成功，TC 通知各 RM 提交。AT 模式下一阶段本地事务已经提交，所以二阶段提交主要是异步清理 `undo_log`。

### 二阶段回滚

如果全局事务失败，TC 通知各 RM 回滚。RM 根据 `undo_log` 的前镜像生成反向 SQL，把数据恢复到事务执行前的状态。

## Spring 集成

引入 starter：

```xml
<dependency>
  <groupId>org.apache.seata</groupId>
  <artifactId>seata-spring-boot-starter</artifactId>
</dependency>
```

常见配置：

```yaml
spring:
  application:
    name: order-service

seata:
  application-id: order-service
  tx-service-group: order-service-tx-group
  enable-auto-data-source-proxy: true
  service:
    vgroup-mapping:
      order-service-tx-group: default
```

如果 starter 自动代理数据源，通常不需要手动创建 `DataSourceProxy`。如果要手动代理，应关闭自动代理，避免重复代理导致异常。

```java
@Configuration
public class DataSourceConfig {

    @Bean
    @ConfigurationProperties(prefix = "spring.datasource")
    public DataSource rawDataSource() {
        return new HikariDataSource();
    }

    @Primary
    @Bean("dataSource")
    public DataSourceProxy dataSourceProxy(DataSource rawDataSource) {
        return new DataSourceProxy(rawDataSource);
    }
}
```

AT 模式还要求每个参与事务的数据库都创建 `undo_log` 表，否则无法自动回滚。

## 开启全局事务

业务入口使用 `@GlobalTransactional`：

```java
@Service
public class OrderService {

    private final InventoryClient inventoryClient;
    private final AccountClient accountClient;

    @GlobalTransactional(name = "create-order", rollbackFor = Exception.class)
    public void createOrder(CreateOrderCommand command) {
        orderRepository.save(command.toOrder());
        inventoryClient.deduct(command.getSkuId(), command.getQuantity());
        accountClient.deduct(command.getUserId(), command.getAmount());
    }
}
```

只要下游服务能拿到同一个 XID，并且本地数据库连接被 Seata 代理，它们执行的数据库操作就会注册为同一个全局事务下的分支事务。

## `@GlobalTransactional` 与 `@Transactional`

`@GlobalTransactional` 管的是全局事务边界，它会向 TC 申请 XID，并把 XID 绑定到当前线程上下文。

`@Transactional` 管的是本地事务边界，它保证同一个方法里的多个 SQL 在同一个本地事务里执行。

在 AT 模式中，即使 Seata 会接管提交和回滚协调，`@Transactional` 仍然有意义。它能让多个 SQL 共用同一个数据库连接和本地事务，避免每条 SQL 变成独立分支。

比较常见的做法是：入口方法使用 `@GlobalTransactional`，本地复杂写操作仍按需要使用 `@Transactional` 控制本地原子性。

## XID 传播

Seata 依赖 XID 串联调用链。入口服务开启全局事务后，XID 会保存在 `RootContext` 中。远程调用下游服务时，需要把 XID 传过去，下游再绑定到自己的上下文里。

常见自动传播情况：

| 调用方式 | XID 传播 |
| --- | --- |
| Dubbo 集成 | 通常可自动传播 |
| Spring Cloud OpenFeign / RestTemplate 集成 | 引入对应 Seata 集成后通常可自动传播 |
| 原生 HTTP 客户端 | 需要手动添加请求头 |
| WebClient / Reactor | 需要额外处理响应式上下文 |
| MQ 消息 | 不建议把一个同步全局事务跨到消息消费端 |

原生 Feign 拦截器示例：

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

消息队列场景要谨慎。消费端通常不是同一个同步事务的一部分，更推荐使用 Outbox、事务消息、重试和补偿来实现最终一致性。

## AT 模式限制

AT 模式不是所有场景都适合：

- SQL 需要能被 Seata 正确解析并生成镜像。
- 每个参与库必须支持本地事务。
- 业务写入热点行时，全局锁竞争可能明显降低吞吐。
- 外部接口、缓存、文件、MQ 这类非数据库资源不能靠 `undo_log` 自动回滚。
- 长事务会放大全局锁占用和回滚风险。
- 回滚依赖前镜像，脏写、绕过代理的数据修改都会破坏一致性。

因此，AT 更适合短事务、关系型数据库、常规增删改场景。涉及复杂业务语义、长流程、外部资源时，应优先评估 TCC、Saga 或 Outbox。

## 选型建议

| 场景 | 更合适的方案 |
| --- | --- |
| 单服务单数据库 | 本地事务 |
| 数据库更新后可靠发消息 | Outbox / 事务消息 |
| 长业务流程，可补偿 | Saga |
| 强业务语义，需要预留和确认 | TCC |
| 多库关系型短事务，侵入要低 | Seata AT |
| 数据库原生强协调事务 | XA |

## 总结

Seata AT 的关键点只有几个：代理数据源、`undo_log`、全局锁、XID 传播、TC 协调。理解这些之后，就不会把它误认为“加一个注解就能让所有外部操作自动回滚”。

分布式事务解决的是一致性问题，但它本身也会带来复杂度。选择它之前，先判断业务到底需要强事务语义，还是只需要可重试、可补偿、可观测的最终一致性。
