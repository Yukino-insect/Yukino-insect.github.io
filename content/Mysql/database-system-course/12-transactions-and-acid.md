+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = '事务、ACID 与故障恢复'
+++

在线书店的一次下单，至少会写入订单、订单项，并减少商品库存。把这些动作拆成几条自动提交的 SQL，看似简单，却可能在服务器异常时留下“订单存在但没有扣库存”或“库存扣了而没有订单”的半成品。**事务**把一组必须共同成立的改变定义为一个逻辑工作单元：它们一起提交，或一起撤销。

本节先讨论通用的事务理论，再以 MySQL 8 的 InnoDB 展示 SQL。ACID 是数据库应提供的语义目标，InnoDB 是达到这些目标的一种产品实现；不要把某一引擎的内部术语误当成关系数据库的普遍定义。并发事务如何协调，见下一篇[并发控制、MVCC 与锁](13-concurrency-mvcc-and-locks.md)。

## 一、事务边界由业务不变量决定

事务不是“只要多条 SQL 就加上 `BEGIN`”。边界必须围绕业务不变量：对已确认的订单，订单项数量、商品价格、订单总额和库存变更应该彼此对应。可以先用一个小型模型把这些事实放进数据库约束之中：

```sql
CREATE TABLE book (
    id BIGINT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    sale_price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    CHECK (sale_price >= 0),
    CHECK (stock >= 0)
) ENGINE = InnoDB;

CREATE TABLE customer_order (
    id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    created_at DATETIME NOT NULL
) ENGINE = InnoDB;

CREATE TABLE order_item (
    order_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (order_id, book_id),
    FOREIGN KEY (order_id) REFERENCES customer_order(id),
    FOREIGN KEY (book_id) REFERENCES book(id),
    CHECK (quantity > 0)
) ENGINE = InnoDB;
```

主键、外键和 `CHECK` 能拒绝一部分非法状态，但并不会自动推导“订单金额必须等于明细之和”或“这次请求不是重复支付”。一致性来自约束、正确的 SQL、应用规则以及事务的配合；事务本身不是业务规则生成器。

## 二、ACID：四个互相配合的承诺

| 特性 | 对书店订单的要求 | 主要依靠 |
| ---- | ---------------- | -------- |
| 原子性 Atomicity | 扣库存、订单头和订单项不能只成功一部分 | 回滚与撤销信息 |
| 一致性 Consistency | 提交前后均满足约束与业务不变量 | 约束、应用逻辑、事务 |
| 隔离性 Isolation | 别的下单者不看到中间状态，也不破坏彼此 | 锁、多版本、隔离级别 |
| 持久性 Durability | 已确认的订单在进程或主机崩溃后仍可恢复 | 预写日志、刷盘与恢复 |

**原子性**的关键不是“不出错”，而是出错以后没有半次提交。**一致性**也不是“数据库替你保证所有业务正确”：若程序把 `total_amount` 算错，完全可以原子且持久地提交一笔错误订单。**隔离性**处理的是同时发生的事务；**持久性**处理的是时间上的断裂，例如断电或数据库进程崩溃。

## 三、用条件更新完成安全的下单

在默认自动提交模式中，每一条独立 DML 通常单独提交。以下流程显式组成一个事务，且用条件更新把“库存仍足够”和“扣减库存”合并为一次原子写入：

```sql
START TRANSACTION;

UPDATE book
SET stock = stock - 2
WHERE id = 101
  AND stock >= 2;

-- 应用必须检查受影响行数；为 0 时 ROLLBACK 并返回售罄。
INSERT INTO customer_order
    (id, customer_id, status, total_amount, created_at)
VALUES
    (90001, 7, 'PENDING_PAYMENT', 158.00, NOW());

INSERT INTO order_item (order_id, book_id, quantity, unit_price)
VALUES (90001, 101, 2, 79.00);

COMMIT;
```

真实程序应在第一条 `UPDATE` 后检查 `ROW_COUNT()` 是否为 1；库存不够时不要继续插入订单，而要回滚。相比“先 `SELECT stock`，随后无条件 `UPDATE`”，条件更新消除了两个会话都读到同一旧库存、再分别扣减的时间窗。下单接口还需用订单请求号上的唯一约束实现幂等：网络超时后重试的请求，不能再次扣货。

```sql
ALTER TABLE customer_order
ADD COLUMN request_no VARCHAR(64) NOT NULL,
ADD UNIQUE KEY uk_order_request_no (request_no);
```

发生唯一键冲突时，应用应按 `request_no` 查询首次请求结果，而不是把异常简单当作“再试一次”。数据库只能保证一次事务的原子性，无法从两个 HTTP 请求中猜出它们是否代表同一笔付款。

## 四、提交、回滚和保存点

`START TRANSACTION` 开启事务，`COMMIT` 才让修改对其他事务稳定可见；`ROLLBACK` 撤销整个未提交事务。`SAVEPOINT` 则提供局部撤销点，适合“可选赠品失败，但主商品仍可下单”这种有明确规则的场景：

```sql
START TRANSACTION;

INSERT INTO customer_order
    (id, customer_id, status, total_amount, created_at)
VALUES (90002, 7, 'PENDING_PAYMENT', 79.00, NOW());

SAVEPOINT optional_gift;
INSERT INTO order_item (order_id, book_id, quantity, unit_price)
VALUES (90002, 888, 1, 0.00);

-- 确认赠品不符合规则后：
ROLLBACK TO SAVEPOINT optional_gift;
INSERT INTO order_item (order_id, book_id, quantity, unit_price)
VALUES (90002, 101, 1, 79.00);
COMMIT;
```

保存点不是独立提交：外层事务后来失败，所有修改仍会一起回滚。对于库存不足、订单主记录写入失败这类必需步骤，也不应用保存点假装业务成功。应用中通常由连接池或框架控制自动提交和连接回收；不要在共享连接上随意 `SET autocommit = 0`，以免连接复用时带入未结束的事务。

## 五、从转账理解原子性与故障

转账是更小却更严格的例子：A 减少 100，B 增加 100；任何一步失败都不能改变任意一方。余额非负也应在写入条件中表达。

```sql
START TRANSACTION;

UPDATE account
SET balance = balance - 100.00
WHERE id = 1 AND balance >= 100.00;

-- 只有上一句影响一行，才执行下一句。
UPDATE account
SET balance = balance + 100.00
WHERE id = 2;

COMMIT;
```

若进程在 `COMMIT` 前崩溃，恢复时应撤销未完成事务；若已提交但还未来得及给客户端回响应，客户端会处于“不知道是否成功”的状态。最差的处理是盲目重放扣款。正确做法是按幂等业务号查询最终订单状态，或调用同一幂等命令。客户端超时是分布式通信问题，不会因为本地事务存在就消失。

## 六、故障分层与恢复边界

| 故障 | 例子 | 首要动作 |
| ---- | ---- | -------- |
| 语句失败 | 约束冲突、库存不足 | 回滚或按规则处理，返回可理解的错误 |
| 并发失败 | 死锁、锁等待超时 | 整个幂等事务有限退避重试 |
| 应用失败 | 异常退出、连接中断 | 确认连接被回滚且不可带状态复用 |
| 系统崩溃 | 数据库、操作系统或电源失效 | 启动时依据日志重做或撤销 |
| 介质故障 | 数据文件损坏、误删数据 | 从经验证的备份恢复，并按日志前滚 |

持久性通常通过“先把足以描述修改的日志可靠写入，再允许提交成功”的原则实现，称为 WAL（write-ahead logging）。不同系统对刷盘时机、日志格式和配置提供不同权衡，因此不能把“SQL 返回成功”粗暴等同于在所有硬件故障下绝不丢失。日志、检查点与恢复是后续运维主题；备份和副本的职责也不能混同。

## 七、事务设计的实践边界

事务应短小，只包住必须共同提交的数据库读写。不要在持锁事务内调支付网关、发邮件、上传文件或等待用户确认：这些慢而不可控的操作会放大锁竞争，并可能让外部世界成功而本地回滚。通常先原子记录本地意图和状态，再以可靠消息、幂等回调或补偿机制推进外部动作。

提交前应逐项检查：涉及的写入是否都在同一数据源、同一连接、同一事务里？每条条件更新是否检查了受影响行数？重复请求是否安全？异常是否真的会触发回滚？如果这些问题不能清楚回答，“已经加了事务”只是一句安慰。

## 八、小结

- 事务边界围绕必须共同成立的业务不变量，而不是围绕方法名或 SQL 数量。
- ACID 中的一致性需要约束和正确逻辑，原子性、隔离性、持久性分别抵御半完成、并发冲突和崩溃丢失。
- 库存扣减应使用带条件的原子 `UPDATE`，并检查影响行数；幂等键解决重复请求。
- `SAVEPOINT` 只用于允许局部放弃的步骤，最终仍由外层 `COMMIT` 或 `ROLLBACK` 决定。
- 崩溃恢复、复制与备份各有责任边界，不能以单一“事务”概念涵盖一切。
