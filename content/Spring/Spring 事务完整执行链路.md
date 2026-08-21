+++
date = '2026-02-19T16:44:15+08:00'
draft = false
title = 'Spring 事务完整执行链路'
+++

## 一、注解阶段：`@Transactional` 是如何被发现的

### `@Transactional` 本身并不做任何事

```java
@Transactional
public void save() { ... }
```

本质只是一个 **元数据（Metadata）**：

- 不开事务
- 不回滚
- 不拦截方法

**它只是告诉 Spring：这里可能需要事务**

### 谁去扫描这个注解？

在启动时：

- `@EnableTransactionManagement`
- 或 Spring Boot 自动配置

会注册一个核心组件：

```java
AnnotationTransactionAttributeSource
```

它的职责只有一个：

> **读取方法 / 类上的 `@Transactional`，并转成 TransactionAttribute**

## 二、方法拦截阶段：AOP 是如何介入的

### Spring 为 Bean 创建代理

当 Spring 容器启动时：

- 如果一个 Bean 的方法上有 `@Transactional`
- Spring 会为它创建 **代理对象**

代理类型：

- JDK 动态代理（接口）
- CGLIB（类）

### 方法调用真正发生了什么？

当我们调用

```java
service.save();
```

实际执行的是：

```java
Proxy.save()
```

执行顺序：

```
代理方法
 ↓
TransactionInterceptor.invoke()
 ↓
真实方法
```

## 三、注解解析阶段：是否需要事务、用什么规则

### 进入 `TransactionInterceptor`

```java
public Object invoke(MethodInvocation invocation)
```

内部立刻调用：

```java
invokeWithinTransaction(...)
```

### 解析事务属性

```java
TransactionAttribute txAttr =
    transactionAttributeSource.getTransactionAttribute(method, targetClass);
```

这里完成：

- 查方法上的 `@Transactional`
- 查类上的 `@Transactional`
- 合并成一个 `TransactionAttribute`

包含：

- 传播行为
- 隔离级别
- 超时
- 只读
- 回滚规则

**如果 `txAttr == null`：直接执行方法，不走事务**

## 四、事务管理器选择阶段：谁来真正管事务？

### 选择 `PlatformTransactionManager`

```java
PlatformTransactionManager tm =
    determineTransactionManager(txAttr);
```

选择逻辑：

1. `@Transactional(transactionManager="xxx")`
2. Bean 名称匹配
3. 容器中唯一的 TransactionManager
4. 默认事务管理器

常见实现：

- `DataSourceTransactionManager`（JDBC / MyBatis）
- `JpaTransactionManager`
- `JtaTransactionManager`

**这一层决定事务由谁执行**

## 五、事务执行阶段：真正的事务生命周期

### 创建或加入事务

```java
TransactionStatus status = tm.getTransaction(txAttr);
```

这里会根据 **传播行为**：

- REQUIRED：
  - 有事务 -> 加入
  - 无事务 -> 新建
- REQUIRES_NEW：
  - 挂起旧事务
  - 新建事务
- SUPPORTS / NOT_SUPPORTED：
  - 可能不创建事务

并且：

- 获取数据库连接
- `setAutoCommit(false)`
- 绑定到 `ThreadLocal`

### 执行业务方法

```java
Object result = invocation.proceed();
```

此时：

- 所有 SQL
- 都使用同一个 Connection
- 都处于同一个事务上下文

### 异常发生时的处理

如果业务方法抛异常：

```java
catch (Throwable ex) {
    completeTransactionAfterThrowing(txInfo, ex);
}
```

内部逻辑：

- 判断 `rollbackFor / noRollbackFor`
- 决定：
  - `rollback()`
  - 或 `commit()`

### 正常返回时提交事务

```java
commitTransactionAfterReturning(txInfo);
```

最终执行：

```java
tm.commit(status);
```

## 六、资源清理阶段：事务结束后的善后工作

### 清理事务上下文

```java
cleanupTransactionInfo(txInfo);
```

做了什么？

- 清除 ThreadLocal 里的事务状态
- 解绑 Connection
- 恢复被挂起的事务
- 防止线程复用污染

### 释放数据库资源

由事务管理器完成：

- `ConnectionHolder.unbind()`
- `Connection.close()`（或归还连接池）

## 七、完整流程文字版时序图

```java
调用 @Transactional 方法
 ↓
AOP 代理拦截
 ↓
TransactionInterceptor
 ↓
解析 @Transactional -> TransactionAttribute
 ↓
选择 PlatformTransactionManager
 ↓
getTransaction()（新建 / 加入）
 ↓
执行业务方法
 ↓
异常？-> rollback
正常？-> commit
 ↓
清理 ThreadLocal & 连接
 ↓
方法返回
```

## 八、事务管理器的作用是什么？

**事务管理器 = 事务的执行者。它只负责：开、提交、回滚事务，不负责：什么时候开、为什么回滚、用什么规则。**

### 1. 事务管理器解决的核心问题

#### 把抽象事务翻译成具体技术动作

Spring 定义了统一接口：

```java
PlatformTransactionManager
```

但真正的事务操作依赖具体技术：

| 技术 | 实际事务操作                      |
| ---- | --------------------------------- |
| JDBC | `Connection.setAutoCommit(false)` |
| JPA  | `EntityManager.getTransaction()`  |
| JTA  | `UserTransaction.begin()`         |

**事务管理器就是适配器**

#### 负责事务的三个原子操作

所有事务管理器，只关心这三件事：

```java
getTransaction()
commit()
rollback()
```

- `getTransaction()`：
  - 新建事务 / 加入事务
  - 挂起 / 恢复事务
- `commit()`：提交
- `rollback()`：回滚

**没有任何业务语义判断**

#### 维护事务状态（TransactionStatus）

```java
TransactionStatus
```

- 是否新事务
- 是否已完成
- 保存点（嵌套事务）

**它只是状态，不是策略**

### 2. 事务管理器不知道这些事情

事务管理器 **完全不知道**：

- 方法上有没有 `@Transactional`
- rollbackFor 是什么
- propagation 是 REQUIRED 还是 REQUIRES_NEW
- 当前是不是 AOP 调用

**这些都不是它的职责**

## 九、TransactionAspectSupport 的作用是什么？

TransactionAspectSupport = Spring 声明式事务的总指挥
它决定：

- 什么时候用事务
- 用哪个事务管理器
- 如何处理传播行为
- 异常时回滚还是提交
- 事务结束后如何清理

### 1. 它在体系中的位置

```java
@Transaction
   ↓
AOP
   ↓
TransactionInterceptor
   ↓
TransactionAspectSupport   ← 核心调度层
   ↓
PlatformTransactionManager ← 执行层
   ↓
Database
```

**它站在策略层，而不是执行层**

### 2. TransactionAspectSupport 干的 6 件关键事情

#### 解析事务元数据

```java
TransactionAttribute txAttr =
    transactionAttributeSource.getTransactionAttribute(method, targetClass);
```

- 把 `@Transactional` 转成 `TransactionAttribute`
- 决定：要不要事务、用什么规则

#### 选择事务管理器

```java
PlatformTransactionManager tm =
    determineTransactionManager(txAttr);
```

- 支持多数据源
- 支持指定事务管理器

#### 创建 / 加入事务

```java
TransactionInfo txInfo =
    createTransactionIfNecessary(tm, txAttr, joinpointId);
```

- REQUIRED / REQUIRES_NEW
- 挂起 / 恢复事务

**传播行为不在事务管理器，而在这里**

#### 执行业务方法

```java
Object ret = invocation.proceed();
```

#### 决定提交还是回滚

```java
if (txAttr.rollbackOn(ex)) {
    tm.rollback(status);
} else {
    tm.commit(status);
}
```

- rollbackFor
- noRollbackFor
- RuntimeException 默认回滚

**这是事务语义的核心判断**

#### 清理事务上下文

```java
cleanupTransactionInfo(txInfo);
```

- 清理 ThreadLocal
- 恢复挂起事务
- 防止事务污染

## 十、TransactionAspectSupport 能做什么 / 不能做什么

### 1. 它能做的

1. **手动标记事务回滚**
2. **获取当前事务状态**
3. **在复杂分支中决定是否回滚**
4. **在不抛异常的情况下回滚事务**

### 2. 它不能做的

- 不能 `begin()` 新事务
- 不能 `commit()` 事务
- 不能脱离 Spring AOP 使用
- 不能跨线程使用

### 3. 手动回滚事务

业务失败，但你 **不想抛异常**，仍然希望事务回滚。

```java
@Service
public class OrderService {

    @Transactional
    public void createOrder() {

        orderMapper.insert(...);

        boolean success = callRemoteService();

        if (!success) {
            // 手动标记事务回滚
            TransactionAspectSupport.currentTransactionStatus()
                    .setRollbackOnly();
            return;
        }

        stockMapper.deduct(...);
    }
}
```

#### 发生了什么？

- Spring 已经开启事务（AOP）

- `TransactionAspectSupport` 只是：

  - **拿到当前 TransactionStatus**
  - **标记 rollbackOnly**

- 方法正常返回

- Spring 在提交阶段发现：

  ```java
  status.isRollbackOnly() == true
  ```

  **最终执行 rollback**

必须配合 @Transactional 使用才可以使用 `TransactionAspectSupport`

```java
@Transactional
public void method() {
    TransactionAspectSupport.currentTransactionStatus()
            .setRollbackOnly();
}
```
