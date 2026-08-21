+++
date = '2026-02-17T21:48:00+08:00'
draft = false
title = 'FOR UPDATE'
+++

`select ... for update` 的作用是把普通查询变成当前读，并对读取到的索引记录加排他锁。它常用于“先读，再根据读取结果更新”的并发场景。

如果只是查询详情、展示列表、做报表，不需要 `for update`。随手加锁并不显得严谨，只会让系统更容易阻塞。

## 一、快照读和当前读

普通 `select` 通常是快照读：

```sql
select *
from product
where id = 1;
```

在 InnoDB 的 MVCC 下，它读取的是当前事务可见的数据版本，不会阻塞其他事务更新同一行。

`for update` 是当前读：

```sql
select *
from product
where id = 1
for update;
```

它读取当前最新可见版本，并加排他锁。其他事务想更新这行数据，就要等待当前事务提交或回滚。

## 二、什么时候需要 FOR UPDATE

典型场景是“读、判断、写”必须作为一个并发安全整体。

例如扣库存：

```sql
begin;

select stock
from product
where id = 1
for update;

-- 应用判断 stock 是否足够

update product
set stock = stock - 3
where id = 1;

commit;
```

如果不加锁，两个事务可能同时读到 `stock = 5`，都判断可以扣，最后导致超卖。

适合使用 `for update` 的场景：

1. 读完要更新同一行，并且不能让其他事务同时处理。
2. 状态流转，例如订单从 `WAIT_PAY` 改为 `PAID`。
3. 任务领取，例如多个 worker 抢同一批待处理任务。
4. 基于当前余额、库存、额度做强一致判断。

## 三、什么时候不需要

不需要 `for update` 的场景：

1. 只读展示、列表、报表。
2. 存在性检查只是为了提示用户。
3. 插入唯一数据时，已经有唯一索引兜底。
4. 允许失败后重试或最终一致。

例如“如果不存在就插入”这种逻辑，真正可靠的做法通常是唯一索引：

```sql
create unique index uk_user_mobile on user(mobile);
```

然后直接插入，捕获唯一冲突：

```sql
insert into user(mobile, name)
values ('13800138000', 'Tom');
```

如果先 `select` 再 `insert`，两个事务仍可能同时判断“不存在”。除非你能锁住对应范围，否则还是会竞争。既然数据库已经有唯一索引，就不要用一段脆弱的代码假装自己比索引更可靠。

## 四、使用时要注意索引

`for update` 的锁依赖索引。条件越精确，锁越精确。

推荐：

```sql
select *
from orders
where id = 10001
for update;
```

如果 `id` 是主键，通常只锁一行。

风险较高：

```sql
select *
from orders
where status = 'WAIT_PAY'
for update;
```

如果 `status` 没有合适索引，或者命中大量数据，可能锁住大量记录，导致阻塞明显。

范围查询也要谨慎：

```sql
select *
from orders
where create_time >= '2026-08-21 00:00:00'
for update;
```

在 `REPEATABLE READ` 下，InnoDB 可能使用 next-key lock 锁住范围，防止其他事务插入影响当前范围的记录。范围越大，影响越大。

## 五、任务领取场景

多个 worker 抢任务时，可以使用 `for update`。在支持的版本中，`skip locked` 可以跳过已经被其他事务锁住的行：

```sql
begin;

select id
from job
where status = 'READY'
order by id
limit 10
for update skip locked;

update job
set status = 'RUNNING'
where id in (...);

commit;
```

这样不同 worker 更容易拿到不同任务，减少等待。使用前仍要确认 MySQL 版本和业务语义，因为跳过锁意味着它不会严格按全局顺序处理每一条记录。

## 六、替代写法

有些扣减场景可以直接用一条原子 `update`，减少先查再改：

```sql
update product
set stock = stock - 3
where id = 1
  and stock >= 3;
```

然后检查影响行数：

1. 影响 1 行：扣减成功。
2. 影响 0 行：库存不足或记录不存在。

这种写法常常比 `select for update` 更简洁，也减少事务持锁时间。

## 七、总结

`for update` 解决的是并发下“基于读取结果继续写”的一致性问题。它不是普通查询的增强版，也不是唯一性约束的替代品。

使用前问三个问题：

1. 读完是否马上要写。
2. 是否必须阻止其他事务同时修改。
3. 查询条件是否能走足够精确的索引。

三个答案都清楚时，再加锁。否则，锁只是把不确定性换成了阻塞。
