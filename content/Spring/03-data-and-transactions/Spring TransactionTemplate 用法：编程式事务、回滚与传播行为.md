+++
date = '2026-08-26T21:30:00+08:00'
draft = false
title = 'Spring TransactionTemplate 用法：编程式事务、回滚与传播行为'
+++

Spring 项目中，大多数事务都可以也应该使用 `@Transactional`。它简洁、声明性强，正常的 Service 方法往往不需要把事务控制代码写进业务逻辑。

但有些场景并不适合只靠注解：事务边界需要由运行时条件决定；同一个方法中只有一小段数据库操作需要事务；需要在捕获异常后明确选择回滚；或者同类内部调用绕过了事务代理。此时，`TransactionTemplate` 提供了一种更直接的**编程式事务**写法。

它的重点不是手动调用 `begin`、`commit`、`rollback`。相反，模板负责事务的开启、提交、回滚和资源清理，业务代码只放进回调函数。别因为它名字里有 Template，就把它当成一块可以随意嵌进去的事务魔法；事务边界、异常和外部副作用仍然需要你自己设计。

## 一、`TransactionTemplate` 是什么

`TransactionTemplate` 位于 `org.springframework.transaction.support` 包中，是 Spring 提供的命令式事务模板。它基于 `PlatformTransactionManager` 工作，并实现了 `TransactionOperations`。

一次典型执行可以抽象为：

```text
调用 transactionTemplate.execute(...)
  -> 根据传播行为取得或创建事务
  -> 执行 Lambda / 回调中的业务代码
  -> 正常返回：提交事务
  -> 抛出运行时异常：回滚事务并继续抛出异常
  -> 事务资源解绑与清理
```

与直接操作 `PlatformTransactionManager` 相比，`TransactionTemplate` 把容易遗漏的样板代码封装起来。你不必自己维护 `TransactionStatus`、在每个 `catch` 里判断是否回滚，也不必在 `finally` 中清理事务资源。

它与 `@Transactional` 的定位不同，但底层仍然使用同一套 Spring 事务抽象：

| 方式 | 事务边界 | 适合场景 | 主要代价 |
| ---- | -------- | -------- | -------- |
| `@Transactional` | 由方法和 AOP 代理声明 | 常规 Service 方法 | 需要理解代理边界与自调用限制 |
| `TransactionTemplate` | 由 `execute` 回调精确界定 | 动态边界、局部事务、显式回滚 | 业务代码耦合 Spring 事务 API |
| 直接使用 `PlatformTransactionManager` | 手动取得、提交、回滚 | 很少见的底层框架需求 | 样板代码多，异常路径更难写对 |

通常的选择是：**能清楚地用一个 Service 方法表达事务边界时，优先 `@Transactional`；只有事务边界真的需要在代码中控制时，再使用 `TransactionTemplate`。**

## 二、准备事务管理器与模板

`TransactionTemplate` 需要一个 `PlatformTransactionManager`。在 Spring Boot 项目中，若使用 JDBC 或 JPA 并完成相应的数据源配置，Boot 通常会自动配置合适的事务管理器；业务代码只需注入它。

下面是把模板注册为 Bean 的常见写法：

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

@Configuration
public class TransactionConfig {

    @Bean
    public TransactionTemplate transactionTemplate(
            PlatformTransactionManager transactionManager
    ) {
        TransactionTemplate template = new TransactionTemplate(transactionManager);

        template.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        template.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        template.setTimeout(10);
        template.setReadOnly(false);

        return template;
    }
}
```

几个配置项的含义如下：

| 配置 | 作用 | 常见取值 |
| ---- | ---- | -------- |
| 传播行为 | 遇到已有事务时如何参与 | `PROPAGATION_REQUIRED`、`PROPAGATION_REQUIRES_NEW` |
| 隔离级别 | 并发事务之间可见数据的规则 | `ISOLATION_READ_COMMITTED` 等 |
| 超时 | 事务允许执行的最长时间 | 秒数，例如 `10` |
| 只读标记 | 向事务管理器表达只读意图 | `true` / `false` |

没有显式设置时，`TransactionTemplate` 使用 Spring 的默认事务定义：传播行为是 `PROPAGATION_REQUIRED`，隔离级别是 `ISOLATION_DEFAULT`，超时为默认值，`readOnly` 为 `false`。具体隔离级别和只读优化是否真正生效，还取决于数据库、JDBC 驱动和事务管理器；把 `readOnly = true` 当成强制禁止写入的安全机制，并不可靠。

### 1. 模板可以作为单例 Bean，但不要运行时修改它

初始化完成后，`TransactionTemplate` 可作为单例 Bean 被多个线程使用。它本身不保存某次请求的会话状态，实际事务上下文由 Spring 与底层事务管理器按当前线程关联。

但模板的传播行为、超时、隔离级别等是可变配置。不要在请求处理过程中对一个共享模板反复调用 `setTimeout()` 或 `setPropagationBehavior()`；那会让并发请求读到彼此的配置。需要不同规则时，创建多个命名明确的模板 Bean，或者为特殊调用临时构造一个独立模板。

```java
@Bean
public TransactionTemplate requiredTransactionTemplate(
        PlatformTransactionManager transactionManager
) {
    return new TransactionTemplate(transactionManager);
}

@Bean
public TransactionTemplate requiresNewTransactionTemplate(
        PlatformTransactionManager transactionManager
) {
    TransactionTemplate template = new TransactionTemplate(transactionManager);
    template.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    return template;
}
```

如果项目中存在多个 `PlatformTransactionManager`，还要明确注入哪一个；可以通过 Bean 名称、`@Qualifier` 或 `TransactionManagementConfigurer` 消除歧义。更重要的是，事务管理器必须和实际访问的资源匹配：使用某个数据源执行 JDBC 操作，就应使用管理该数据源的事务管理器。否则代码看上去“在事务里”，实际却不一定包住了目标操作。

## 三、基本用法：有返回值的 `execute`

`execute` 接收一个 `TransactionCallback<T>`。这个接口是函数式接口，因此 Java 8 及以后通常直接写 Lambda；Lambda 的返回值就是 `execute` 的返回值。

以下示例在创建订单的同一个事务中扣减库存、写入订单和订单明细：

```java
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class OrderService {

    private final TransactionTemplate transactionTemplate;
    private final InventoryRepository inventoryRepository;
    private final OrderRepository orderRepository;
    private final OrderItemRepository orderItemRepository;

    public OrderService(
            TransactionTemplate transactionTemplate,
            InventoryRepository inventoryRepository,
            OrderRepository orderRepository,
            OrderItemRepository orderItemRepository
    ) {
        this.transactionTemplate = transactionTemplate;
        this.inventoryRepository = inventoryRepository;
        this.orderRepository = orderRepository;
        this.orderItemRepository = orderItemRepository;
    }

    public Long createOrder(CreateOrderCommand command) {
        return transactionTemplate.execute(status -> {
            boolean deducted = inventoryRepository.decrease(
                    command.productId(),
                    command.quantity()
            );

            if (!deducted) {
                throw new InsufficientStockException(command.productId());
            }

            Order order = Order.create(command.userId());
            orderRepository.save(order);
            orderItemRepository.save(
                    OrderItem.of(order.getId(), command.productId(), command.quantity())
            );

            return order.getId();
        });
    }
}
```

逻辑正常返回时，模板会尝试提交事务，并将订单 ID 返回给调用方。`InsufficientStockException` 若是 `RuntimeException` 的子类，模板会回滚事务并把异常继续抛出；库存扣减、订单和明细的数据库操作会一起回滚。

这段代码仍应遵守事务内的基本原则：

- 尽量只放必须原子提交的数据库操作。
- 不要把缓慢的远程 HTTP 调用、文件上传、用户交互塞进长事务。
- 回调返回的实体在事务结束后可能变为游离对象；若使用 JPA 的懒加载关联，离开事务后再访问可能失败，应按需要转换为 DTO。

事务能回滚数据库状态，却无法撤回已经发出的 HTTP 请求、邮件、消息或第三方支付。若这些副作用必须与数据库状态协调，应考虑事务后事件、Outbox、可靠消息等设计，而不是把一次网络调用包进事务后便假装问题已经消失。

## 四、无返回值操作：`executeWithoutResult`

如果回调只执行写操作，没有业务返回值，可以使用 `TransactionOperations` 提供的 `executeWithoutResult`：

```java
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class UserService {

    private final TransactionTemplate transactionTemplate;
    private final UserRepository userRepository;

    public UserService(
            TransactionTemplate transactionTemplate,
            UserRepository userRepository
    ) {
        this.transactionTemplate = transactionTemplate;
        this.userRepository = userRepository;
    }

    public void disableUser(Long userId) {
        transactionTemplate.executeWithoutResult(status -> {
            User user = userRepository.findByIdForUpdate(userId)
                    .orElseThrow(() -> new UserNotFoundException(userId));

            user.disable();
            userRepository.save(user);
        });
    }
}
```

`executeWithoutResult` 本质上仍在事务中执行回调，只是省去了返回 `null` 的噪声。旧代码中常见下面这个类：

```java
new TransactionCallbackWithoutResult() {
    @Override
    protected void doInTransactionWithoutResult(TransactionStatus status) {
        // 数据库操作
    }
};
```

这种写法在旧版 Spring 中很常见；在当前 Spring Framework 7 中，`TransactionCallbackWithoutResult` 已被标记为弃用，推荐改用 `executeWithoutResult(status -> { ... })`。如果项目还停留在较早的 Spring Framework 版本、没有该默认方法，则可以继续使用 `execute(status -> { ...; return null; })`，不要为了追求“新写法”而让依赖版本无法编译。

## 五、异常与回滚：最容易写错的地方

### 1. 抛出运行时异常：模板负责回滚并继续传播

最简单、最清晰的失败路径是让异常离开回调：

```java
transactionTemplate.executeWithoutResult(status -> {
    accountRepository.debit(fromAccountId, amount);

    if (!accountRepository.credit(toAccountId, amount)) {
        throw new TransferFailedException("target account not found");
    }
});
```

当回调抛出 `RuntimeException` 或 `Error` 时，`TransactionTemplate` 会将其视为致命异常，执行回滚并把异常传回调用方。这种写法最适合“此次业务操作失败，调用方也应感知失败”的场景。

### 2. 捕获异常后正常返回，事务可能会提交

下面的代码是典型陷阱：

```java
transactionTemplate.executeWithoutResult(status -> {
    accountRepository.debit(fromAccountId, amount);

    try {
        accountRepository.credit(toAccountId, amount);
    } catch (DataAccessException ex) {
        log.warn("credit failed", ex);
        // 回调正常结束
    }
});
```

异常被捕获并吞掉后，`executeWithoutResult` 会认为回调成功结束，于是尝试提交事务。结果可能是“扣款已提交，入账失败”。这显然不是转账应有的结果。

若捕获异常后仍要回滚，但不想把异常继续抛给上层，可以明确标记：

```java
transactionTemplate.executeWithoutResult(status -> {
    accountRepository.debit(fromAccountId, amount);

    try {
        accountRepository.credit(toAccountId, amount);
    } catch (DataAccessException ex) {
        log.warn("credit failed, transaction will roll back", ex);
        status.setRollbackOnly();
    }
});
```

`status.setRollbackOnly()` 请求事务管理器在结束时回滚。注意它不是“局部撤销刚才这一句 SQL”，而是把当前事务标记为只能回滚。

多数业务场景中，重新抛出领域异常会比“吞掉错误并仅标记回滚”更易维护：调用方能得到明确失败结果，日志和监控也更自然。只有业务确实要把失败转化为正常返回值时，才应当选择 `setRollbackOnly()` 并设计清楚返回语义。

### 3. 返回业务失败值，不等于回滚

这一点值得单独强调：

```java
boolean success = transactionTemplate.execute(status -> {
    if (!inventoryRepository.decrease(productId, quantity)) {
        return false;
    }

    orderRepository.save(Order.create(userId));
    return true;
});
```

`return false` 只是回调的正常返回值，模板会尝试提交事务。若在返回 `false` 前已经做过任何需要撤销的写入，必须显式调用 `status.setRollbackOnly()`，或者直接抛出异常。

```java
boolean success = transactionTemplate.execute(status -> {
    orderRepository.save(Order.create(userId));

    if (!inventoryRepository.decrease(productId, quantity)) {
        status.setRollbackOnly();
        return false;
    }

    return true;
});
```

当然，把“库存不足”当作一个可预期的业务分支时，通常更好的方案是先尝试条件更新库存，失败后根本不创建订单；这样没有已写入的数据需要回滚。事务不应成为补救任意执行顺序的橡皮擦。

### 4. 不要在回调中随意手动 `commit` 或 `rollback`

`TransactionTemplate` 已经拥有事务生命周期的控制权。回调中不应再通过底层连接、JPA `EntityTransaction` 或事务管理器手动提交、回滚同一个事务。

如果你需要表达“这次事务必须回滚”，使用传入的 `TransactionStatus`：

```java
transactionTemplate.executeWithoutResult(status -> {
    // ...
    status.setRollbackOnly();
});
```

模板和你的业务代码各自只负责一层职责，边界才不会混乱。

## 六、传播行为：嵌套调用时事务到底属于谁

`TransactionTemplate` 与 `@Transactional` 一样遵守传播行为。最常用的是 `PROPAGATION_REQUIRED`：当前线程已有事务就加入，没有就新建。

```text
外层事务存在
  -> REQUIRED 模板：加入外层事务
  -> 回调结束：通常不立即独立提交
外层事务结束
  -> 一次性提交或回滚全部操作
```

这意味着，`status.setRollbackOnly()` 在加入外层事务的场景中会影响整个事务。外层代码若继续正常完成，到最终提交时可能收到 `UnexpectedRollbackException`：内层早已把事务标记为必须回滚，外层却还在期待提交。

### 1. `PROPAGATION_REQUIRED`：默认且最常用

```java
TransactionTemplate required = new TransactionTemplate(transactionManager);
required.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
```

适用于内外操作本来就必须“要么全部成功、要么全部失败”的情况。例如创建订单时写订单、扣库存、写明细，应当参与同一个事务。

### 2. `PROPAGATION_REQUIRES_NEW`：暂停外层，创建独立事务

```java
TransactionTemplate auditTemplate = new TransactionTemplate(transactionManager);
auditTemplate.setPropagationBehavior(
        TransactionDefinition.PROPAGATION_REQUIRES_NEW
);

auditTemplate.executeWithoutResult(status -> {
    auditLogRepository.save(AuditLog.of("order created"));
});
```

若外层已经存在事务，`REQUIRES_NEW` 会先暂停它，再开启一个独立事务。内层成功提交后，即使外层后来回滚，内层提交的数据通常仍会保留。

审计日志有时会使用这种方式，但应谨慎：

- “审计必须保留”与“主业务必须成功”是不同业务语义，不要只为绕开回滚而使用它。
- 内层事务需要自己的数据库连接；在高并发且连接池很紧张时，外层连接被占用、内层又等待连接，可能导致资源耗尽甚至类似死锁的等待。
- 独立事务无法自动保证外部系统和主事务的一致性。

### 3. `PROPAGATION_NESTED`：依赖保存点，不等于独立事务

`NESTED` 在已有事务中通常依赖数据库保存点：内层失败可回滚到保存点，外层仍有机会继续。它不是 `REQUIRES_NEW`，不会创建真正独立的物理事务。

是否支持 `NESTED` 取决于具体事务管理器与底层资源。不要假定 JPA、JTA、不同数据库驱动都能以同样方式工作；使用前应针对项目实际的事务管理器和数据库做集成测试。

## 七、用它处理 `@Transactional` 的自调用问题

`@Transactional` 通常通过 Spring AOP 代理生效。同一个对象内部直接调用自己的另一个带注解方法时，调用没有经过代理，事务注解可能不生效：

```java
@Service
public class ImportService {

    public void importAll(List<Row> rows) {
        for (Row row : rows) {
            importOne(row);  // 同类直接调用，可能绕过事务代理
        }
    }

    @Transactional
    public void importOne(Row row) {
        // 数据库操作
    }
}
```

若业务要求每一行独立事务，可以直接在循环中使用传播行为为 `REQUIRES_NEW` 的模板：

```java
@Service
public class ImportService {

    private final TransactionTemplate requiresNewTransactionTemplate;
    private final RowRepository rowRepository;

    public ImportService(
            TransactionTemplate requiresNewTransactionTemplate,
            RowRepository rowRepository
    ) {
        this.requiresNewTransactionTemplate = requiresNewTransactionTemplate;
        this.rowRepository = rowRepository;
    }

    public void importAll(List<Row> rows) {
        for (Row row : rows) {
            requiresNewTransactionTemplate.executeWithoutResult(status -> {
                rowRepository.save(row);
            });
        }
    }
}
```

这里不依赖代理拦截，`executeWithoutResult` 被调用时就会走事务管理器。不过这只说明它能解决“自调用导致注解未拦截”的技术问题；是否应该每行独立提交仍是业务选择。批量导入量很大时，每行一个新事务会带来明显开销，也会使整体失败后留下部分已提交数据。

## 八、常见误区与实践建议

### 1. 以为模板会自动回滚所有失败

模板只能根据回调的结束方式和 `TransactionStatus` 做决定：

- 回调正常返回：提交。
- 抛出运行时异常：回滚并传播。
- 调用 `setRollbackOnly()`：回滚。

异常被捕获后静默返回、返回一个 `false` 或 `null`，都不是自动回滚信号。

### 2. 以为 `readOnly` 能阻止写操作

`readOnly` 是对事务管理器和底层资源的提示，有些实现会据此优化 Flush 模式或连接配置，有些数据库也可能施加限制，但不能把它视为权限控制。真正禁止写入应使用数据库账号权限、SQL 审核或应用层授权。

### 3. 把整个 Controller 或远程调用包进事务

事务持有数据库连接和锁。事务范围越大，并发冲突、连接占用和超时风险越高。推荐让 `execute` 回调只覆盖必要的本地持久化操作：

```text
校验请求参数
调用远程服务 / 组装数据
  -> TransactionTemplate.execute(...)
       -> 必须原子完成的数据库读写
  -> 事务结束
发送后续通知或交给 Outbox
```

具体顺序必须按一致性要求设计，但“把慢操作挪出数据库事务”通常是值得优先考虑的原则。

### 4. 多个模板的 Bean 注入不明确

项目同时声明 `requiredTransactionTemplate` 和 `requiresNewTransactionTemplate` 后，下面的构造器参数可能产生按类型注入歧义：

```java
public ImportService(TransactionTemplate transactionTemplate) {
    // 可能不知道该注入哪一个
}
```

可以用 `@Qualifier` 明确表达意图：

```java
public ImportService(
        @Qualifier("requiresNewTransactionTemplate")
        TransactionTemplate transactionTemplate
) {
    this.transactionTemplate = transactionTemplate;
}
```

名称本身也是设计的一部分。叫 `transactionTemplate2` 并不会让代码变得更抽象，只会让将来读到它的人增加一次无意义的猜测。

## 九、总结

`TransactionTemplate` 是 Spring 命令式事务管理的首选高级 API。它把事务生命周期交给模板，但把事务边界和失败语义明确留给业务代码。

- 使用 `execute(status -> value)` 执行并返回事务内产生的结果。
- 无返回值操作优先使用 `executeWithoutResult(status -> { ... })`；在 Spring Framework 7 中，不再推荐 `TransactionCallbackWithoutResult`。
- 让运行时异常离开回调，模板会回滚并继续传播；捕获异常后正常返回会导致提交，除非显式 `status.setRollbackOnly()`。
- 默认 `PROPAGATION_REQUIRED` 会加入外层事务；`REQUIRES_NEW` 是独立事务，`NESTED` 依赖保存点支持，三者不能混为一谈。
- `TransactionTemplate` 能避开同类自调用对 AOP 代理的限制，但不意味着每次都应把事务写进循环。
- 事务只能协调受同一事务资源管理器控制的本地资源；外部副作用需要另外设计可靠性方案。

如果一个事务边界能自然地等同于一个 Service 方法，`@Transactional` 仍然更干净。只有当边界、传播或回滚策略必须由运行时逻辑精确决定时，才让 `TransactionTemplate` 出场。工具本身没有问题，问题通常出在用它掩盖了本该先想清楚的业务一致性。 
