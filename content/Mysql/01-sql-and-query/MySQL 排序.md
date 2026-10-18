+++
date = '2026-03-18T14:55:58+08:00'
draft = false
title = 'MySQL 排序'
+++

MySQL 的 `ORDER BY` 看起来只是排序，背后却可能走完全不同的执行路径。性能差异最大的地方不是排序算法名字，而是：**能不能直接按索引顺序返回，需不需要额外 `filesort`，会不会使用临时表或落盘。**

## 一、常见执行方式

从执行路径看，`ORDER BY` 大致分三类：按索引顺序直接返回、额外执行 `filesort`、在复杂查询中配合临时表排序。下面按成本从低到高展开。

## 二、按索引顺序返回

这是最理想的情况。如果 `ORDER BY` 能被索引满足，MySQL 可以按索引顺序读取数据，避免额外排序。

例如：

```sql
select id, title, create_time
from post
where status = 1
order by create_time desc, id desc
limit 20;
```

适合的联合索引：

```sql
create index idx_post_status_time_id
on post(status, create_time desc, id desc);
```

这里 `status = 1` 用于过滤，`create_time desc, id desc` 用于有序扫描。

如果查询列都在索引里，还可能形成覆盖索引：

```sql
select id, create_time
from post
where status = 1
order by create_time desc, id desc
limit 20;
```

覆盖索引能减少回表成本。

## 三、Using filesort

如果索引无法满足排序，MySQL 会进入额外排序阶段，`EXPLAIN` 中常见 `Using filesort`。

需要注意：`Using filesort` 不等于一定使用磁盘文件。它只是表示 MySQL 需要额外排序，而不是直接按索引顺序返回。

排序数据较少时，可能在内存中完成。数据较多、排序字段较大、返回列较宽时，可能需要临时文件或多轮归并。

例如：

```sql
select *
from post
where status = 1
order by title;
```

如果没有适合 `(status, title)` 的索引，就可能触发 `filesort`。

## 四、临时表和落盘

有些 SQL 不只是排序，还会创建内部临时表。例如：

1. `order by` 和 `group by` 不一致。
2. `distinct` 搭配复杂排序。
3. 多表 join 后按非驱动表字段排序。
4. 窗口函数、派生表、复杂聚合。

`EXPLAIN` 中可能看到：

```text
Using temporary; Using filesort
```

这通常比单纯 `Using filesort` 更重。临时表如果超过内存阈值，还可能落到磁盘。

## 五、性能大致排序

一般可以这样理解：

```text
覆盖索引顺序返回
> 非覆盖索引顺序返回
> 内存 filesort
> 临时表 / 磁盘 filesort
```

但这不是绝对规则。比如“按索引顺序扫描大量数据再随机回表”有时不一定比“小结果集内存排序”快。最终仍要看优化器估算和真实执行数据。

## 六、哪些写法容易退化

### 1. ORDER BY 列和索引顺序不匹配

只有两个单列索引：

```sql
key idx_a(a),
key idx_b(b)
```

查询：

```sql
select *
from t
order by a, b;
```

通常不能同时靠两个单列索引完成 `a, b` 的整体排序。更合适的是联合索引：

```sql
create index idx_t_a_b on t(a, b);
```

### 2. 排序列上做表达式

```sql
select *
from t
order by date(create_time) desc;
```

这类写法通常无法直接利用 `create_time` 的普通索引排序。可以改为直接按原字段排序，或用生成列加索引。

### 3. 前置模糊或函数处理

```sql
where name like '%Tom'
order by create_time desc
```

如果过滤阶段已经无法有效走索引，排序阶段的输入数据就可能变多。

### 4. 多表 join 后排序字段位置不合适

```sql
select *
from a
join b on b.a_id = a.id
order by b.create_time desc
limit 20;
```

如果执行计划中不能以 `b` 的有序索引作为合适驱动，可能需要先 join 出大量结果，再临时表排序。

## 七、优化方式

### 1. 设计 WHERE + ORDER BY 联合索引

常见列表查询：

```sql
select id, title, create_time
from post
where status = 1
order by create_time desc, id desc
limit 20;
```

索引：

```sql
create index idx_post_status_time_id
on post(status, create_time desc, id desc);
```

不要只给 `status`、`create_time` 分别建两个单列索引就以为万事大吉。优化器不一定能把它们拼成你想要的排序路径。

### 2. 给排序补稳定字段

不推荐：

```sql
order by create_time desc
```

如果多行 `create_time` 相同，分页时顺序可能不稳定。

推荐：

```sql
order by create_time desc, id desc
```

`id` 作为 tiebreaker，可以让排序结果稳定，也方便做游标分页。

### 3. 深分页改成游标分页

深分页：

```sql
select id, title, create_time
from post
where status = 1
order by create_time desc, id desc
limit 100000, 20;
```

数据库要处理前面十万行再丢弃。

游标分页：

```sql
select id, title, create_time
from post
where status = 1
  and (
    create_time < :last_create_time
    or (create_time = :last_create_time and id < :last_id)
  )
order by create_time desc, id desc
limit 20;
```

它更适合信息流、列表下一页、后台滚动加载。

### 4. 先取 ID，再取大字段

如果表行很宽，正文、JSON、大文本字段很多，可以先用覆盖索引拿 ID：

```sql
select id
from post
where status = 1
order by create_time desc, id desc
limit 20;
```

再按主键取详情：

```sql
select id, title, author, content
from post
where id in (...);
```

这样可以减少排序阶段携带的数据量。

### 5. 统计信息保持新鲜

大批量导入、删除、冷热数据变化后，统计信息不准可能导致优化器选错执行计划：

```sql
analyze table post;
```

这不是万能药，但在执行计划明显不合理时值得检查。

### 6. Hint 只作为兜底

如果非常确定优化器选错，可以考虑：

```sql
select *
from post force index for order by (idx_post_status_time_id)
where status = 1
order by create_time desc, id desc
limit 20;
```

Hint 会把执行计划和当前索引绑定得更紧，后续数据分布变化时可能反而变差。所以它应该是兜底手段，不是日常习惯。

## 八、MySQL 排序时排什么

最终返回给客户端的结果一定是按 `ORDER BY` 排好的。

但内部排序阶段不一定搬整行数据去排。`filesort` 可能排序：

1. 排序键 + 行定位信息。
2. 排序键 + 需要返回的部分字段。
3. 排序键 + 打包后的附加字段。

因此 `select *` 往往会增加排序或回表成本。列表页尽量只查需要的列，详情页再按主键取完整数据。

## 九、排查方式

先看执行计划：

```sql
explain select ...
```

MySQL 8.0 可以看真实执行：

```sql
explain analyze select ...
```

重点关注：

1. 是否出现 `Using filesort`。
2. 是否出现 `Using temporary`。
3. 扫描行数是否过大。
4. 是否使用了预期索引。
5. 是否出现大量回表。

也可以观察排序相关状态：

```sql
show global status like 'Sort%';
show global status like 'Created_tmp%';
```

## 十、总结

优化 `ORDER BY` 的优先级是：

1. 尽量让排序走联合索引。
2. 排序字段加稳定 tiebreaker。
3. 避免深分页大 offset。
4. 减少排序阶段携带的大字段。
5. 用 `EXPLAIN` 验证，而不是靠感觉。

最实用的一句话：**能按索引顺序返回，就不要让 MySQL 额外排序；必须排序时，就尽量让参与排序的数据更少。**
