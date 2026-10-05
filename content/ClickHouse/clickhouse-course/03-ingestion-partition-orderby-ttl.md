+++
date = '2026-10-02T20:30:00+08:00'
draft = false
title = 'ClickHouse 摄入、分区、排序键与 TTL 实战'
+++

上一节已经可以插入和查询数据。真正使用 ClickHouse 时，问题很快会变成：上游每秒都来数据，应该一条条写还是攒一批写？网络超时后重试会不会重复？数据保留 90 天后如何处理？这些问题看似分散，其实都与 MergeTree 的 part 和后台 merge 有关。

## 1. 为什么“每条消息一个 INSERT”会出问题

回忆上一节：一次 INSERT 通常会形成一个 part。若一个程序每收到一条访问记录就发送一次 INSERT，数据库会不断产生很小的 part。小 part 多到一定程度后：

- 查询需要打开更多文件和索引；
- merge 线程必须持续合并，消耗 CPU、磁盘 IO 与临时空间；
- 新写入可能被节流，甚至出现 part 数过多的错误。

所以 ClickHouse 更喜欢**批量追加**。这不是说批次越大越好：极大的请求会占用更多内存，失败后重试成本也更高。一个实用起点是让生产者按“达到一定行数”或“等待一小段时间”两种条件之一提交，例如每几千到几万行或每数秒一次；随后依据事件大小、吞吐、延迟目标和 `system.parts` 测量调整。

```text
事件到达 -> 生产者暂存 -> 达到行数或等待时间
       -> INSERT 一批 -> 记录批次结果 -> 下一批
```

“HTTP 返回成功”只表示这个请求成功。为了能排查失败和重放，批次记录至少应有：来源名称、来源位置（例如文件偏移或消息 offset）、稳定事件 ID、批次 ID、尝试次数、行数和写入时间。

## 2. 用实验比较小批与大批

在**课程容器**中另建两张完全相同的表。先执行：

```sql
CREATE TABLE analytics_lab.tiny_batches
(
    event_time DateTime('UTC'),
    n UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, n);

CREATE TABLE analytics_lab.one_batch AS analytics_lab.tiny_batches;
```

为了不让练习拖慢电脑，先做 20 次很小的 INSERT。它刻意不是推荐的生产方式：

```sql
INSERT INTO analytics_lab.tiny_batches SELECT now(), number FROM numbers(100);
```

重复执行这条语句 20 次，然后一次性写入相同数量级数据：

```sql
INSERT INTO analytics_lab.one_batch
SELECT now(), number FROM numbers(2000);

SELECT
    table,
    count() AS active_parts,
    sum(rows) AS rows
FROM system.parts
WHERE database = 'analytics_lab'
  AND table IN ('tiny_batches', 'one_batch')
  AND active
GROUP BY table;
```

刚写完时，`tiny_batches` 往往有更多 part；等一会儿后 merge 可能降低它的 part 数，所以结果不是固定截图。这个实验的目标是理解趋势：人为制造大量小写入，会把本可一次完成的工作交给后台慢慢补课。练习结束可以执行 `DROP TABLE analytics_lab.tiny_batches;` 与 `DROP TABLE analytics_lab.one_batch;`。

## 3. 重试为何会造成重复：先定义你想要的语义

网络请求超时有三种可能：请求没有到达、服务端写入后响应丢失、服务端还在处理。客户端无法只靠超时判断，因此“直接重试”天然可能重复。

普通 `MergeTree` 不提供唯一约束。请根据业务选择并写清楚以下语义之一：

- **允许至少一次**：日志类数据允许极少重复，报表查询使用稳定 `event_id` 做去重或接受误差；
- **可重放且可对账**：每条事件带稳定 ID，批次记录来源范围，定期检查重复与缺失；
- **最后状态覆盖**：这是另一类“状态表”问题，可研究 `ReplacingMergeTree`，但它依赖后台 merge，不能把它当成立即事务更新。

下面为事件表加一个稳定 ID，并检查重复。这里使用 `UUID` 只是示例；来自其他系统时，应直接带入其稳定主键。

```sql
CREATE TABLE analytics_lab.events_with_id
(
    event_id UUID,
    event_time DateTime('UTC'),
    page LowCardinality(String),
    latency_ms UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, page, event_id);

INSERT INTO analytics_lab.events_with_id VALUES
    ('123e4567-e89b-12d3-a456-426614174000', '2026-10-02 10:00:00', '/home', 10),
    ('123e4567-e89b-12d3-a456-426614174000', '2026-10-02 10:00:00', '/home', 10);

SELECT event_id, count() AS copies
FROM analytics_lab.events_with_id
GROUP BY event_id
HAVING copies > 1;
```

预期会看到 `copies = 2`。这不是 ClickHouse 出错，而是表引擎兑现了“追加写”的语义。先认清这一点，才谈得上可靠的上游重试策略。

## 4. 再次区分分区和排序键

从第 1 篇知道：分区管理大块数据，排序键决定 part 内局部顺序。现在用两个反例巩固它：

```sql
-- 常见反例：每个用户都成为一个分区
PARTITION BY user_id

-- 常见反例：每小时都成为一个分区
PARTITION BY toYYYYMMDDhh(event_time)
```

用户数或小时数增长时，这些表达式会制造大量分区，增加元数据和后台管理负担。多数按时间分析的事件表可以先从月分区开始：

```sql
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_date, page, event_time)
```

为什么 `event_date` 放在排序键前面？不是因为它“看起来像主键”，而是因为课程中的查询通常先限定时间、再限定页面。若你的真实查询总是围绕设备 ID，排序键可能完全不同。**分区按什么删，排序键按什么查。** 这句话比背模板更有用。

当一个完整月份确实不再需要时，可以删除整个分区：

```sql
ALTER TABLE analytics_lab.page_events DROP PARTITION 202610;
```

这是不可逆的数据删除。执行前必须先通过 `system.parts` 核实 `partition` 的实际值、确认备份和影响范围。课程中只应对自己创建的练习表操作；不要把这条命令当作日常清理按钮。

## 5. TTL：给数据声明生命周期

**TTL（time to live）** 是“数据活到什么时候”的规则。它很适合临时明细、监控原始事件等有明确保留期的数据。创建一张短保留期练习表：

```sql
CREATE TABLE analytics_lab.ttl_demo
(
    event_time DateTime('UTC'),
    page String,
    latency_ms UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, page)
TTL event_time + INTERVAL 7 DAY DELETE;
```

写入一行 8 天前、一行当前数据：

```sql
INSERT INTO analytics_lab.ttl_demo VALUES
    (now() - INTERVAL 8 DAY, '/old', 1),
    (now(), '/new', 2);

SELECT * FROM analytics_lab.ttl_demo ORDER BY event_time;
```

你可能会先看到两行。原因是 TTL 通常由后台 merge 执行，它不是到了某个秒数就同步 `DELETE` 的闹钟。用于学习时可以在空闲的**练习表**上请求合并：

```sql
OPTIMIZE TABLE analytics_lab.ttl_demo FINAL;
SELECT * FROM analytics_lab.ttl_demo ORDER BY event_time;
```

之后预期只剩 `/new`。`OPTIMIZE ... FINAL` 会强制合并，可能很消耗资源；不要把它当作生产环境中让 TTL“立即生效”的通用手段。若法规要求精确删除时刻，还必须审计备份、对象存储副本、访问权限和恢复流程，不能仅凭表上出现 TTL 就得出“数据已经消失”。

## 6. 物化视图：写入时顺便生成汇总

当“按小时、按页面的访问量”被反复查询时，每次扫描明细表会浪费计算。**物化视图** 可以在数据插入源表时执行一个 SELECT，并把结果写入目标表。它不是自动查询缓存，也不会自动处理已经存在的历史数据。

下面的例子把每小时、每页面的计数写到专门的汇总表：

```sql
CREATE TABLE analytics_lab.hourly_page_counts
(
    hour DateTime('UTC'),
    page LowCardinality(String),
    visits AggregateFunction(count)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, page);

CREATE MATERIALIZED VIEW analytics_lab.page_events_to_hourly
TO analytics_lab.hourly_page_counts
AS SELECT
    toStartOfHour(event_time) AS hour,
    page,
    countState() AS visits
FROM analytics_lab.page_events
GROUP BY hour, page;
```

此后**新插入** `page_events` 的数据会经过视图。读取聚合状态时要使用对应的 `countMerge`：

```sql
SELECT hour, page, countMerge(visits) AS visits
FROM analytics_lab.hourly_page_counts
GROUP BY hour, page
ORDER BY hour, page;
```

如果你在创建视图前已写了历史数据，目标表不会神奇地补齐；要设计单独的回填、核对与切换步骤。数据量很小或维度经常变时，直接查询明细表往往更容易维护。

## 7. 本篇小结与下一步

稳定摄入的关键不是某一个参数，而是四项可解释的约定：批量写入、稳定事件标识、可审计重试、按时间管理生命周期。分区和 TTL 是强大的管理工具，因此误用时破坏性也强。

下一篇进入最后一环：[查询观测、备份恢复与故障排查](04-query-observability-backup-operations.md)。它会回答“报表为什么变慢”“磁盘为什么增长”“备份如何证明真的能恢复”。
