+++
date = '2026-03-11T15:01:47+08:00'
draft = false
title = 'MySQL 中 IN 条件的查询机制'
+++

`IN` 用于判断某个字段是否属于一组候选值。它看起来像多个 `OR` 条件的简写，但 MySQL 优化器执行时不一定只是逐个比较。

真正影响性能的不是 `IN` 这个关键字本身，而是候选值数量、索引、数据分布和执行计划。

## 一、常量 IN 列表

常见写法：

```sql
select *
from user
where id in (1, 3, 5, 7);
```

如果 `id` 是主键或唯一索引，MySQL 通常可以对候选值做多次索引定位，再合并结果。这类查询一般效率不错。

如果候选值非常多：

```sql
where id in (...几千个 id...)
```

就要注意：

1. SQL 文本变长，解析成本增加。
2. 优化器估算成本上升。
3. 执行计划可能不稳定。
4. 网络传输和参数绑定也会变重。

大量 ID 查询时，可以考虑分批、临时表、派生表或业务侧改造。

## 二、IN 和 OR

逻辑上：

```sql
where id in (1, 2, 3)
```

等价于：

```sql
where id = 1 or id = 2 or id = 3
```

但不能简单说 `IN` 一定比 `OR` 快，或者 `OR` 一定导致索引失效。优化器会根据条件、索引和数据分布决定执行计划。

一般来说，同一个字段上的多个等值判断，用 `IN` 可读性更好：

```sql
where status in ('PAID', 'REFUNDING', 'CLOSED')
```

不同字段上的 `OR` 要更谨慎：

```sql
where mobile = ?
   or email = ?
```

这种查询是否高效，要看是否有合适索引，以及优化器是否能使用 index merge 或其他策略。

## 三、子查询 IN

子查询写法：

```sql
select *
from orders
where user_id in (
  select id
  from user
  where status = 1
);
```

MySQL 可能把它改写为半连接，也可能使用物化子查询等策略。具体行为取决于版本、优化器开关、索引和数据规模。

排查重点：

1. 子查询结果集是否很大。
2. 子查询过滤字段是否有索引。
3. 外层关联字段是否有索引。
4. 是否可以改写成 `exists` 或 `join` 后更清晰。

例如：

```sql
select *
from orders o
where exists (
  select 1
  from user u
  where u.id = o.user_id
    and u.status = 1
);
```

`IN`、`EXISTS`、`JOIN` 没有绝对谁更快。要用执行计划说话。

## 四、NOT IN 的 NULL 问题

`NOT IN` 遇到 `NULL` 很容易出乎意料。

例如：

```sql
select *
from orders
where user_id not in (
  select user_id
  from blacklist
);
```

如果子查询结果里包含 `NULL`，整个判断可能变成 unknown，导致返回结果和预期不同。

更稳妥的做法是过滤掉 `NULL`：

```sql
where user_id not in (
  select user_id
  from blacklist
  where user_id is not null
)
```

或者改成 `not exists`：

```sql
select *
from orders o
where not exists (
  select 1
  from blacklist b
  where b.user_id = o.user_id
);
```

## 五、实践建议

1. 小规模常量列表，用 `IN` 没问题。
2. 几百个值可以接受，但要看 SQL 频率和执行计划。
3. 几千个值以上，要考虑分批、临时表或业务改造。
4. `IN` 字段要有合适索引。
5. 子查询 `IN` 要关注内外层关联字段索引。
6. `NOT IN` 要特别注意 `NULL`。

排查时使用：

```sql
explain select ...
```

MySQL 8.0 中可以进一步看真实执行：

```sql
explain analyze select ...
```

## 六、总结

`IN` 是常用条件表达式，不是性能问题本身。性能由索引、候选值数量、数据分布和优化器选择决定。

不要迷信“IN 比 OR 快”或“IN 一多就一定慢”这种结论。数据库不会因为口诀变快，只会按照执行计划工作。
