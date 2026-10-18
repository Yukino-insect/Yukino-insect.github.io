+++
date = '2025-09-05T17:31:32+08:00'
draft = false
title = 'MySQL 事务'
+++

事务是数据库中的一个逻辑执行单元，由一组 SQL 组成。它要么全部成功提交，要么全部失败回滚。

在 MySQL 中，讨论事务通常默认指 InnoDB。MyISAM 这类存储引擎不支持事务，所以同样的 SQL，在不同存储引擎下行为可能并不一样。

## 一、ACID

事务的四个基本特性是 ACID：

| 特性 | 含义 |
| ---- | ---- |
| 原子性 Atomicity | 事务内操作要么全部成功，要么全部回滚 |
| 一致性 Consistency | 事务前后数据库约束和业务规则保持正确 |
| 隔离性 Isolation | 并发事务之间不能随意看到彼此的中间状态 |
| 持久性 Durability | 事务提交后，结果应能在崩溃恢复后保留下来 |

原子性依赖 undo log。修改失败时，可以根据 undo log 回滚。

持久性依赖 redo log。提交后的修改即使还没完全刷到数据页，也能通过 redo log 恢复。

隔离性依赖锁和 MVCC。不同隔离级别下，读写之间的可见性不同。

一致性不是单靠数据库某一个机制保证的，它还依赖主键、唯一约束、外键、检查约束和业务代码共同维护。

## 二、事务控制

MySQL 默认开启自动提交：

```sql
select @@autocommit;
```

每条 SQL 默认都是一个独立事务。如果要把多条语句放进同一个事务，需要显式开启：

```sql
begin;

update account
set balance = balance - 100
where id = 1;

update account
set balance = balance + 100
where id = 2;

commit;
```

失败时：

```sql
rollback;
```

也可以关闭自动提交：

```sql
set autocommit = 0;
```

不过在应用里更常见的是交给连接池、框架或事务管理器控制。

## 三、隔离级别

MySQL 支持四种标准隔离级别：

| 隔离级别 | 可能问题 | 说明 |
| -------- | -------- | ---- |
| READ UNCOMMITTED | 脏读、不可重复读、幻读 | 可以读到其他事务未提交数据，几乎不用 |
| READ COMMITTED | 不可重复读、幻读 | 每条语句读取最新已提交版本 |
| REPEATABLE READ | 幻读被 InnoDB 在很多场景下控制 | MySQL InnoDB 默认隔离级别 |
| SERIALIZABLE | 并发最低 | 通过更强锁行为让事务串行化 |

几个概念要区分：

1. 脏读：读到其他事务未提交的数据。
2. 不可重复读：同一事务内两次读同一行，结果不同。
3. 幻读：同一事务内两次范围查询，出现新增或消失的行。

InnoDB 的 `REPEATABLE READ` 通过 MVCC 让普通 `select` 使用一致性快照，所以同一事务内多次普通查询通常能看到一致结果。对于当前读，例如 `select ... for update`、`update`、`delete`，InnoDB 会配合记录锁、间隙锁、next-key lock 等机制控制并发插入带来的幻读问题。

## 四、快照读和当前读

普通查询通常是快照读：

```sql
select *
from orders
where id = 1;
```

快照读读取的是当前事务可见版本，不加行锁，适合展示、报表、普通列表查询。

当前读读取最新已提交或当前事务修改后的版本，并可能加锁：

```sql
select *
from orders
where id = 1
for update;
```

常见当前读包括：

1. `select ... for update`
2. `select ... lock in share mode`
3. `update`
4. `delete`
5. `insert`

读完要基于结果做强一致修改时，要考虑当前读和加锁。只是展示数据时，不要随便加锁。

## 五、常见锁

### 1. 记录锁

记录锁锁住索引中的某条记录。例如：

```sql
begin;
select *
from orders
where id = 1
for update;
```

如果 `id` 是主键，这通常锁住 `id = 1` 这一行。其他事务想修改同一行，需要等待。

### 2. 间隙锁

间隙锁锁住索引记录之间的范围，防止其他事务在范围内插入新记录。它常出现在 `REPEATABLE READ` 下的范围当前读中：

```sql
begin;
select *
from student
where age between 20 and 30
for update;
```

前提是查询条件能走合适索引。没有索引时，锁范围可能扩大，甚至造成严重阻塞。

### 3. Next-Key Lock

Next-Key Lock 可以理解为记录锁和间隙锁的组合，既锁住已有记录，也锁住记录前后的间隙。它是 InnoDB 在可重复读隔离级别下控制范围并发写入的重要机制。

### 4. 意向锁

意向锁是表级锁，由 InnoDB 自动维护，用来协调表锁和行锁。

例如事务 A 要锁某一行，InnoDB 会先在表上加意向排他锁。事务 B 如果想给整张表加写锁，就能通过意向锁快速判断是否存在行级锁冲突，而不用扫描全表每一行。

意向锁通常不需要开发者手动处理。

### 5. 共享锁和排他锁

共享锁允许多个事务同时读：

```sql
select *
from orders
where id = 1
lock in share mode;
```

排他锁用于写或准备写：

```sql
select *
from orders
where id = 1
for update;
```

排他锁之间互斥，排他锁也会和共享锁冲突。

## 六、事务和索引的关系

InnoDB 的行锁是加在索引上的。这个细节非常重要。

例如：

```sql
select *
from user
where mobile = '13800138000'
for update;
```

如果 `mobile` 有索引，锁范围通常更精确。如果没有索引，数据库可能扫描更多记录并加更多锁，导致本来只想锁一个用户，结果阻塞大片数据。

所以写加锁 SQL 时，一定要关注：

1. 条件是否能走索引。
2. 是否是唯一索引。
3. 范围条件会不会扩大锁范围。
4. 多事务加锁顺序是否一致。

## 七、死锁

死锁常见于多个事务以不同顺序持有锁。

例如：

```text
事务 A：先锁订单 1，再锁订单 2
事务 B：先锁订单 2，再锁订单 1
```

双方互相等待，就可能死锁。InnoDB 会检测死锁，并回滚其中一个事务。

降低死锁概率的方式：

1. 事务尽量短。
2. 同类业务按固定顺序加锁。
3. 加锁条件走索引。
4. 不在事务里做远程调用、长时间计算或等待用户输入。
5. 对死锁错误做有限重试。

## 八、总结

MySQL 事务不是只有 `begin`、`commit`、`rollback`。真正要理解的是：快照读解决读一致性，当前读和锁解决并发写一致性，undo log 支撑回滚，redo log 支撑持久性，索引决定锁能否足够精确。

事务越长，锁持有越久；加锁越随意，并发越差。数据库会提供机制，但不会替我们判断业务边界。
