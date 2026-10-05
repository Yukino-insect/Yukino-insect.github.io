+++
date = '2026-10-02T20:10:00+08:00'
draft = false
title = 'ClickHouse 列式存储、MergeTree 与数据模型'
+++

上一节把 ClickHouse 定位为分析数据库。现在从最小的数据出发，理解它怎样存数据。先不要把 `MergeTree` 当成一个必须记住的名词；它本质上是在回答三个朴素问题：数据按什么顺序放、每次写入留下什么、许多小块数据怎样变得便于查询。

## 从一张访问记录表开始

假设每一次页面访问都产生下列记录：

| event_time | user_id | page | status_code | latency_ms | request_body |
| --- | --- | ---: | ---: | ---: | --- |
| 10:00:01 | u-7 | `/home` | 200 | 18 | 很长的文本 |
| 10:00:03 | u-8 | `/search` | 200 | 55 | 很长的文本 |
| 10:00:06 | u-7 | `/checkout` | 500 | 731 | 很长的文本 |

若问题是“找出 `u-7` 的这一笔记录并修改状态”，行式数据库很自然：一行的所有字段通常放在一起，定位这一行后读写都方便。

若问题变为“过去 30 天每个页面的平均耗时”，绝大多数时候只需要 `event_time`、`page` 和 `latency_ms`。列式数据库把同一列的值连续保存，因此能跳过 `user_id`、`status_code` 和很长的 `request_body`。同类数值和重复字符串连在一起，也更容易压缩。

这就是列存的直觉，并不是魔法：查询读的列越少、过滤越有效，优势越明显；若每次都需要取回一整行、频繁改一行，优势就会减弱。

## 数据库、表和列：先建立可操作的边界

在 ClickHouse 中：

- **数据库**像文件柜的标签，用来组织表，例如 `analytics_lab`；
- **表**定义列、数据类型和存储引擎，例如 `page_events`；
- **列**定义每行必须提供或可计算的字段，例如 `event_time DateTime`；
- **行**是一条事件。分析查询往往一次处理大量行。

一张适合课程实验的表如下：

```sql
CREATE TABLE analytics_lab.page_events
(
    event_time DateTime('UTC'),
    event_date Date MATERIALIZED toDate(event_time),
    user_id String,
    page LowCardinality(String),
    status_code UInt16,
    latency_ms UInt32,
    request_body String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, page, event_time);
```

这里的 `MATERIALIZED` 表示 `event_date` 由 `event_time` 自动计算，写入时不用手填。`UInt16`、`UInt32` 是无符号整数类型；类型选得恰当会减少空间并避免“本应是数字却存成字符串”的问题。`LowCardinality(String)` 适合页面名这类重复很多的短字符串，不适合几乎每行都不同的请求 ID。

## MergeTree：数据先成为 part，再在后台合并

上面 `ENGINE = MergeTree` 选择了最常用的 ClickHouse 表引擎。一次 `INSERT` 不会像传统 B-tree 那样把每行插进一个长期存在的页中，而通常会写出一个新的 **part**。可以把 part 想成“按规定排序、按列保存的一小批不可变数据文件”。

```text
INSERT 批次 A  -> part A
INSERT 批次 B  -> part B    -> 后台 merge -> 更大的 part AB
INSERT 批次 C  -> part C
```

**merge** 是后台工作：它把同一分区内的小 part 合成较大的 part，并重写相关数据文件和索引标记。这样查询要打开的文件更少，压缩效果通常更好。

由此立刻得到两个实践结论：

- 每秒写一行会制造很多小 part，查询和后台合并都会变重；应尽量汇成批次写入。
- 合并需要同时读旧 part、写新 part，短时间内会多占 CPU、磁盘 IO 和空间；不要按“原始 CSV 大小”一项估算磁盘。

part 是文件组织单位，不是分区，不是一行，也不是业务对象。下一篇会用 `system.parts` 亲眼看到它。

## 分区：为了管理大块数据，不是为了加速所有查询

`PARTITION BY toYYYYMM(event_date)` 把 2026 年 10 月的数据、11 月的数据放到不同的逻辑分区。分区最重要的用途是：

- 管理保留期，例如整月过期后可以整体移除；
- 控制 merge 的边界，只有同一分区的 part 会合并；
- 在查询条件恰好带日期时，排除完全无关的月份。

初学者很容易写出 `PARTITION BY user_id`。这通常是反例：用户多就会有海量小分区，元数据、part 与 merge 管理都会失控。也不要默认按小时分区；数据量很大且必须按小时删除时才可能合理。对常见事件表而言，月分区是一个值得先实验的起点，而不是放之四海皆准的规则。

## 排序键：决定 part 内数据怎样排队

`ORDER BY (event_date, page, event_time)` 不是查询末尾的 `ORDER BY`，它是写入时的物理排列规则：每个 part 内先按日期，再按页面，最后按时间排序。

ClickHouse 会基于这个顺序保存**稀疏主键索引**。它不是“每一行一个索引条目”的 MySQL B-tree，而是每隔一批行保存一个标记（mark）。查询条件满足排序键左侧前缀时，例如“某天、某页面、某段时间”，引擎可以跳过很多不可能匹配的数据块；但它仍可能在选中的数据块内扫描多行。

因此请记住三件事：

1. `ORDER BY` **不保证唯一**。重复的事件 ID 可以被写入；需要去重必须另外设计。
2. 排序键的左侧更重要。表按 `(event_date, page, event_time)` 排序时，按日期和页面过滤通常受益最大；只按 `user_id` 过滤就不一定能跳过很多数据。
3. 排序键要从高频查询倒推，而不是从“哪个字段名字看起来重要”倒推。

例如，报表总是问“某天某页面的错误数”，当前排序合理；若所有报表都是“某个用户的完整历史”，则 `user_id` 可能更接近访问路径。一个表无法同时为每种查询做到最优，先选择主要路径，其他路径再考虑派生表或汇总表。

## `PRIMARY KEY`、索引粒度和唯一性的边界

未单独写 `PRIMARY KEY` 时，MergeTree 的主键默认使用 `ORDER BY`。这里的“主键”主要服务于稀疏索引和数据跳过，**不是关系数据库中的唯一约束**。不要因为列名叫 `event_id` 就假设 ClickHouse 会拒绝重复值。

`index_granularity` 控制两个标记之间大致有多少行。调小可能让高选择性条件少扫描一些行，也会增加索引和元数据；调大则相反。它是测量后的参数，不是入门阶段要盲调的旋钮。先在下一篇比较查询读取量，再决定是否需要改变。

## 用查询决定表设计的一个练习

在建表前写下最常见的三条问题，例如：

```sql
SELECT event_date, page, count()
FROM analytics_lab.page_events
WHERE event_date >= today() - 7
GROUP BY event_date, page;

SELECT quantile(0.95)(latency_ms)
FROM analytics_lab.page_events
WHERE event_date = '2026-10-02' AND page = '/search';
```

它们都从日期开始并按页面筛选，于是 `(event_date, page, event_time)` 有明确理由。若无法写出查询，任何 `ORDER BY` 都只是猜测。

## 这一篇需要带走什么

ClickHouse 的基础结构可以浓缩为一句话：**一次批量写入形成按排序键排列的列式 part；同一分区的小 part 由后台合并，查询利用分区和稀疏索引减少要读的数据。**

下一篇不再停留在纸面上：请启动独立容器，执行建表和写入，并用系统表验证这句话的每个部分：[Docker、SQL 与系统表动手实验](02-clickhouse-docker-sql-practice.md)。
