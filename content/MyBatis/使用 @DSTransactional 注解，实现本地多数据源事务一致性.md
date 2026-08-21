+++
date = '2026-03-03T20:22:42+08:00'
draft = false
title = '使用 @DSTransactional 实现本地多数据源事务一致性'
+++

在多数据源项目里，常见场景是同一个应用同时访问多个库，或者同一个数据库实例下的不同 schema 被配置成不同数据源。此时 Spring 的 `@Transactional` 默认只管理当前事务管理器对应的数据源，跨数据源写入时就可能出现一个库提交成功、另一个库回滚失败的问题。

`@DSTransactional` 是 dynamic-datasource 提供的本地多数据源事务方案。它能解决的核心问题是：**同一个应用实例、同一个线程、同一条调用链里，多个数据源的本地事务尽量一起提交或一起回滚**。

注意，它不是分布式事务。它没有二阶段提交协议，也不等价于 Seata、XA 或 TCC。

## 适用场景

适合使用 `@DSTransactional` 的场景：

- 同一个 Spring Boot 应用内访问多个数据源。
- 操作都发生在同一个线程里。
- 调用链没有跨服务、跨消息队列、异步线程切换。
- 需要在业务方法内保证多个数据源的本地事务统一提交或回滚。

不适合的场景：

- 跨微服务调用。
- MQ 消息发送和数据库写入需要强一致。
- 业务链路中存在异步线程、定时任务接力。
- 需要严格分布式事务语义。

如果业务已经跨服务，就不要把 `@DSTransactional` 当成万能胶。万能胶这个词听起来可靠，实际工程里通常只是把问题粘到以后。

## 多数据源配置

示例配置：

```yaml
spring:
  datasource:
    dynamic:
      primary: master
      strict: true
      datasource:
        master:
          driver-class-name: com.mysql.cj.jdbc.Driver
          url: jdbc:mysql://localhost:3306/db1?useSSL=false&serverTimezone=Asia/Shanghai
          username: root
          password: xxx
        slave:
          driver-class-name: com.mysql.cj.jdbc.Driver
          url: jdbc:mysql://localhost:3306/db2?useSSL=false&serverTimezone=Asia/Shanghai
          username: root
          password: xxx
```

`primary` 表示默认数据源。`strict: true` 表示找不到指定数据源时直接报错，而不是退回默认数据源。生产环境建议开启，否则数据写错库时排查会很难看。

## 使用 `@DS` 切换数据源

可以在 Service 或 Mapper 上使用 `@DS`：

```java
@DS("master")
public interface OrderMapper {
    int insertOrder(OrderDO order);
}
```

```java
@DS("slave")
public interface OrderLogMapper {
    int insertLog(OrderLogDO log);
}
```

也可以标在方法上：

```java
@Service
public class ReportService {

    @DS("slave")
    public List<ReportDO> listReport() {
        return reportMapper.selectList();
    }
}
```

方法级注解通常比类级注解优先级更高。为了降低阅读成本，建议项目内统一约定写在 Service 还是 Mapper，不要一半一半。

## 使用 `@DSTransactional`

跨数据源写入时，在编排业务的方法上添加 `@DSTransactional`：

```java
@Service
public class OrderBizService {

    private final OrderMapper orderMapper;
    private final OrderLogMapper orderLogMapper;

    public OrderBizService(OrderMapper orderMapper, OrderLogMapper orderLogMapper) {
        this.orderMapper = orderMapper;
        this.orderLogMapper = orderLogMapper;
    }

    @DSTransactional
    public void createOrder(OrderCreateCommand command) {
        OrderDO order = buildOrder(command);
        orderMapper.insertOrder(order);

        OrderLogDO log = buildOrderLog(order);
        orderLogMapper.insertLog(log);

        if (command.needFail()) {
            throw new IllegalStateException("mock rollback");
        }
    }
}
```

当方法正常结束时，事务组内的数据源事务会统一提交；当方法抛出异常时，事务组内已经开启的事务会统一回滚。

## 基本原理

可以把它理解成一个本地事务组：

```text
进入 @DSTransactional 方法
  -> 创建当前线程事务上下文
  -> 第一次访问 master，开启 master 本地事务
  -> 第一次访问 slave，开启 slave 本地事务
  -> 方法正常结束，依次 commit
  -> 方法抛出异常，依次 rollback
```

它依赖当前线程保存事务上下文。因此这些写法会破坏事务边界：

```java
@DSTransactional
public void createOrder(OrderCreateCommand command) {
    orderMapper.insertOrder(buildOrder(command));

    CompletableFuture.runAsync(() -> {
        orderLogMapper.insertLog(buildLog(command));
    });
}
```

异步线程拿不到原来的事务上下文，`orderLogMapper` 的事务不再由外层 `@DSTransactional` 管理。

## 和 `@Transactional` 的区别

| 注解 | 管理范围 | 典型用途 |
| --- | --- | --- |
| `@Transactional` | 单个事务管理器下的数据源 | 普通单库事务 |
| `@DSTransactional` | dynamic-datasource 管理的多个数据源 | 同应用内多数据源本地事务 |

如果一个业务方法只写一个数据源，使用 `@Transactional` 更直接。如果确实会切换多个数据源，再使用 `@DSTransactional`。

不要在同一个方法上随意叠加两个注解，除非已经明确框架版本、AOP 顺序和事务传播行为。事务最怕“看起来都加了”，因为它通常意味着没人知道到底谁生效。

## 回滚条件

默认情况下，运行时异常会触发回滚：

```java
throw new RuntimeException("rollback");
```

如果业务抛出受检异常，需要确认注解是否支持配置回滚异常，或在业务层转换为运行时异常：

```java
try {
    doSomething();
} catch (IOException e) {
    throw new IllegalStateException("create order failed", e);
}
```

同时要避免吞异常：

```java
@DSTransactional
public void createOrder(OrderCreateCommand command) {
    try {
        orderMapper.insertOrder(buildOrder(command));
        orderLogMapper.insertLog(buildLog(command));
    } catch (Exception e) {
        log.error("create order failed", e);
    }
}
```

这种写法方法会正常返回，外层事务可能认为应该提交。

## 自调用问题

`@DSTransactional` 基于 Spring AOP，和 `@Transactional` 一样存在自调用问题：

```java
@Service
public class OrderService {

    public void outer() {
        inner();
    }

    @DSTransactional
    public void inner() {
        // 这里可能不会经过代理
    }
}
```

`outer()` 直接调用同类的 `inner()`，没有经过 Spring 代理，注解可能不生效。

解决方式：

- 把事务方法放到另一个 Spring Bean。
- 从代理对象调用方法。
- 调整业务分层，让编排方法本身由外部 Bean 调用。

## 实战检查清单

使用前建议检查：

- 是否所有数据源都由 dynamic-datasource 管理。
- 是否开启了 `strict: true`。
- 跨库写入是否都在同一线程。
- 是否存在自调用导致 AOP 不生效。
- 异常是否被吞掉。
- 是否有异步、MQ、远程服务调用混入事务方法。
- 是否写了回滚验证测试。

## 结论

`@DSTransactional` 适合解决单体应用内的多数据源本地事务一致性。它的优点是接入成本低，能覆盖不少跨库写入场景；它的边界也很明确：不跨线程、不跨服务、不提供严格分布式事务保证。

真正重要的是先判断问题属于哪一类事务。如果只是本地多数据源，它很合适；如果已经跨系统，就应该设计分布式事务、最终一致性或补偿机制。
