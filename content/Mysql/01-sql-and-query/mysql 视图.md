+++
date = '2026-02-19T12:33:48+08:00'
draft = false
title = 'MySQL 视图'
+++

视图是数据库中保存好的查询定义。它本身通常不存储数据，查询视图时，MySQL 会把视图展开成底层 SQL 执行。

可以把视图理解成：**给复杂 SQL 起了一个数据库层面的名字。**

## 一、创建视图

示例：

```sql
create view v_user_order as
select
  u.id as user_id,
  u.username,
  o.id as order_id,
  o.amount
from user u
join orders o on o.user_id = u.id;
```

之后可以像查询表一样查询视图：

```sql
select *
from v_user_order
where amount > 100;
```

视图隐藏了底层 join 细节，但不改变数据实际存放位置。

## 二、视图和表的区别

| 对比项 | 表 | 视图 |
| ------ | -- | ---- |
| 是否存储数据 | 存储 | 通常不存储 |
| 是否占用大量空间 | 会 | 通常很少 |
| 数据来源 | 自身数据页 | 底层查询 |
| 是否可更新 | 可以 | 有条件 |
| 主要价值 | 持久化数据 | 封装查询、统一口径、权限隔离 |

视图不是临时表，也不是缓存。普通视图不会因为创建出来就提前把结果算好。

## 三、为什么使用视图

视图的价值主要体现在结构治理上：复用复杂 SQL、隔离权限、统一字段命名和统计口径。它解决的是“查询定义到处散落”的问题，而不是替代索引或缓存。

## 四、简化复杂 SQL

如果多个接口都要复用同一段复杂 SQL：

```sql
select year, xzcd, sum(amount) as total_amount
from water_stat
where year between 2015 and 2020
group by year, xzcd;
```

可以封装成视图：

```sql
create view v_water_year_xzcd as
select year, xzcd, sum(amount) as total_amount
from water_stat
group by year, xzcd;
```

查询时：

```sql
select *
from v_water_year_xzcd
where year >= 2018;
```

这样可以减少重复 SQL，让统计口径集中维护。

## 五、权限隔离

视图可以限制用户只能看到某些列或某些过滤后的数据。

例如只暴露报表字段：

```sql
create view v_user_report as
select id, username, create_time
from user
where deleted = 0;
```

授权：

```sql
grant select on v_user_report to 'report_user'@'%';
```

这样报表用户不需要直接访问原始用户表，也看不到敏感字段。

## 六、统一字段口径

老系统里经常出现字段名混乱、join 规则分散的问题。视图可以在数据库层提供统一出口：

```sql
create view v_order_simple as
select
  o.id as order_id,
  u.username as user_name,
  o.amount,
  o.create_time
from orders o
join user u on u.id = o.user_id;
```

对外统一查 `v_order_simple`，比每个地方手写一遍 join 更稳定。

## 七、视图能不能更新

简单视图在满足条件时可以更新，例如只来源于单表、没有聚合、没有分组、没有 `distinct`、没有复杂表达式。

复杂视图通常不能直接更新：

```sql
create view v_order_stat as
select user_id, count(*) as total
from orders
group by user_id;
```

这个视图是聚合结果，数据库无法把“更新 total”明确映射回底层哪些订单行。

实践中，视图更多用于查询封装。需要写入时，优先直接写真实表。

## 八、视图性能

MySQL 普通视图不是性能优化工具。

查询：

```sql
select *
from v_user_order
where amount > 100;
```

本质上仍要执行底层 SQL。视图能提高结构清晰度，但不会天然减少扫描、join 或排序成本。

性能要点：

1. 底层表索引仍然重要。
2. 视图嵌套过深会降低可读性和排查效率。
3. 复杂聚合视图高频查询时，要考虑汇总表或物化方案。
4. 查询视图也要看 `EXPLAIN`。

## 九、总结

MySQL 视图适合封装复杂查询、统一字段口径、做权限隔离。它不适合被当成缓存，也不适合幻想成“创建之后查询就一定更快”的优化手段。

视图的价值主要在结构，而不是速度。
