+++
date = '2026-10-26T14:10:00+08:00'
draft = false
title = 'MySQL 触发器：执行时机、事务边界与使用边界'
+++

触发器（trigger）是绑定在一张表上的数据库程序：当该表发生 `INSERT`、`UPDATE` 或 `DELETE` 时，数据库在指定时机自动执行它。它适合实现少量、稳定且必须与数据写入同步的规则；它不适合充当一个看不见的业务服务层。

这个边界很重要。触发器能够让规则无法被某个遗漏的应用入口绕开，但也会让一条看似普通的 `UPDATE` 产生额外写入、额外锁和额外失败路径。自动发生的事情越多，排查成本越高；数据库不会因此突然获得读心能力。

## 触发器由什么组成

MySQL 触发器有三个核心维度：

| 维度 | 可选值 | 含义 |
| --- | --- | --- |
| 事件 | `INSERT`、`UPDATE`、`DELETE` | 哪一种 DML 会触发 |
| 时机 | `BEFORE`、`AFTER` | 写入目标行之前或之后执行 |
| 粒度 | `FOR EACH ROW` | 每受影响一行执行一次 |

MySQL 的触发器是**行级触发器**。例如一条 `UPDATE orders ... WHERE ...` 更新 500 行，触发器会执行 500 次，而不是只执行一次。没有 `FOR EACH STATEMENT` 形式可选，因此批量写入上的成本必须认真评估。

触发器还可读取“变化前后”的伪行：

- `INSERT`：可读写 `NEW.column`（仅 `BEFORE INSERT` 可以改写新行的可赋值列）。
- `UPDATE`：可读 `OLD.column` 与 `NEW.column`；`BEFORE UPDATE` 可以调整 `NEW`。
- `DELETE`：只能读取 `OLD.column`。

`OLD` 是已经存在的旧值，`NEW` 是将要写入或刚写入的新值。它们不是普通表，不要尝试对它们单独 `SELECT` 或 `UPDATE`。

## 用 BEFORE 触发器拒绝非法状态迁移

订单状态通常不是任意跳转。若业务规定“已发货订单不能退回待支付”，可以在写入前阻止这个修改：

```sql
DELIMITER //

CREATE TRIGGER trg_orders_reject_reverse_shipping
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
  IF OLD.status = 'SHIPPED' AND NEW.status = 'PENDING' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = '已发货订单不能改回待支付';
  END IF;
END //

DELIMITER ;
```

`SIGNAL SQLSTATE '45000'` 用于抛出自定义业务错误。语句失败后，该行更新不会完成；若它属于一个 InnoDB 事务，调用方仍要按自己的事务逻辑处理回滚和错误响应。

为什么这里选 `BEFORE`？因为规则是在写入前检查，失败时不应先落库再补救。`BEFORE` 也可用于规范化输入，例如把某个展示字段修整为统一格式，但不要把数据清洗当成掩盖脏数据来源的理由。

## 用 AFTER 触发器写审计记录

若确实需要与数据变更同事务地保存一个简短审计轨迹，可在成功写入后将旧值和新值记录到审计表。示例如下：

```sql
CREATE TABLE order_status_audit (
  audit_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id BIGINT NOT NULL,
  old_status VARCHAR(20) NOT NULL,
  new_status VARCHAR(20) NOT NULL,
  changed_at DATETIME NOT NULL,
  changed_by VARCHAR(128) NOT NULL
);

DELIMITER //

CREATE TRIGGER trg_orders_audit_status
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
  IF NOT (OLD.status <=> NEW.status) THEN
    INSERT INTO order_status_audit (
      order_id, old_status, new_status, changed_at, changed_by
    )
    VALUES (
      NEW.order_id, OLD.status, NEW.status, NOW(), CURRENT_USER()
    );
  END IF;
END //

DELIMITER ;
```

`<=>` 是 MySQL 的空值安全等号；它把两个 `NULL` 视为相等。若用 `OLD.status <> NEW.status`，任一侧为 `NULL` 时结果会变成 `NULL`，`IF` 不会当作真，审计可能被意外跳过。即使业务字段规定为 `NOT NULL`，理解这个差异也能避免把三值逻辑带进事故报告。

`AFTER UPDATE` 表示目标行已经通过本次更新。不过“已经写入”不等于“已经永久提交”：在 InnoDB 中，审计表插入与原更新仍属于同一个事务。外层事务回滚时，两者通常都会回滚；外层提交时，两者才一起对其他事务可见。这正是触发器适合本地同步审计、却不适合外部通知的原因。

## 一次写入中的顺序与事务关系

将一个 `UPDATE` 简化为下面的链路会比较准确：

```text
应用执行 UPDATE
  -> 找到待更新行并取得所需锁
  -> BEFORE UPDATE 触发器（逐行）
  -> 写入目标行
  -> AFTER UPDATE 触发器（逐行）
  -> SQL 语句成功返回
  -> 外层事务 COMMIT 或 ROLLBACK
```

触发器不创建独立事务，也不会提前提交。若触发器中的语句报错，整个触发它的 DML 通常失败；若之后外层事务回滚，触发器已经完成的同事务写入也会被撤销。DDL 的隐式提交、非事务存储引擎等例外会让边界变得更复杂，关键业务不应依赖这些边缘行为。

还应注意：触发器执行期间不应对**正在被该触发器修改的同一张表**再次做会导致递归修改的操作。MySQL 会拒绝这类用法，以防无限递归和语义混乱。需要维护同表派生数据时，通常应重新设计表结构、在应用层显式更新，或使用独立的汇总表与作业。

## 哪些需求不该塞进触发器

下列职责通常不应由触发器承担：

- 发送短信、邮件、HTTP 请求或消息队列通知；数据库事务重试时，这些外部副作用难以做到恰好一次。
- 复杂下单、支付、库存、优惠、权限等跨表业务编排；规则隐藏在数据库里，应用代码、测试和监控很难看全链路。
- 大量批量导入时的重计算、全表汇总或长耗时操作；它会放大每行 DML 的延迟和锁持有时间。
- 本可由 `NOT NULL`、`CHECK`、唯一约束或外键表达的完整性规则；声明式约束更直观，也更容易被优化器和维护者理解。

例如，“余额不得为负”可以用带条件的 `UPDATE` 和受影响行数判断；“订单号唯一”应使用唯一索引；“订单项必须属于现有订单”应优先使用外键。触发器应当是最后一层小而明确的同步规则，而非数据库里的隐形框架。

## 部署、查看与删除

触发器定义属于数据库模式的一部分，应和建表、索引、迁移脚本一起版本化。线上修改触发器前，必须评估新旧版本在并发写入和回滚下的行为，而不是只在客户端里手工点一次。

可用下列语句检查定义：

```sql
SHOW TRIGGERS FROM app_db;
SHOW CREATE TRIGGER trg_orders_audit_status;
```

删除时必须指明名称：

```sql
DROP TRIGGER IF EXISTS trg_orders_audit_status;
```

MySQL 的触发器与表绑定，删除表时其触发器也会一并删除。对于包含敏感字段的审计表，还应同时设计访问权限、保留期限、脱敏和恢复演练；“留下一条日志”本身并不等于可审计。

## 小结

- MySQL 触发器在 `INSERT`、`UPDATE`、`DELETE` 的 `BEFORE` 或 `AFTER` 时按受影响行执行，可通过 `OLD`、`NEW` 读取变化。
- `BEFORE` 适合校验和拒绝非法写入；`AFTER` 可用于小而同步的审计记录。
- 触发器与触发它的 DML 处于同一事务，不会独立提交；失败和回滚会影响整条写入链路。
- 约束能表达的规则先用约束，复杂业务和外部副作用留在应用层或可靠消息流程中。
- 所有触发器都应被版本化、可测试、可观测，并让维护者能够一眼发现其副作用。

关于存储程序、视图与最小权限，可继续阅读 [SQL 高级对象与安全：视图、存储程序、事务与最小权限](../database-system-course/07-sql-advanced-objects-and-security.md)。
