+++
date = '2026-10-02T20:40:00+08:00'
draft = false
title = 'ClickHouse 查询观测、备份恢复与运行排障'
+++

前面三篇解决了“如何正确地把数据放进去”。最后还必须回答：报表变慢时先看哪里？part 变多意味着什么？有一个备份文件，为什么仍不能说数据安全？这一篇不要求你立刻成为数据库管理员，但会给出一套从证据出发的日常检查顺序。

## 1. 先区分正在发生的事和已经发生的事

ClickHouse 有很多 `system` 表。对初学者，先记住四张就够了：

| 系统表 | 回答的问题 |
| --- | --- |
| `system.processes` | 此刻哪些查询仍在执行、读了多少行、占多少内存？ |
| `system.query_log` | 已完成或失败的查询过去花了多久、读了多少数据？ |
| `system.parts` | 每张 MergeTree 表当前有哪些有效数据片段、占多少空间？ |
| `system.merges` | 此刻有哪些后台合并正在进行？ |

`processes` 像急诊室的实时看板，`query_log` 像病历，二者不能互相替代。先做一个简单查询，然后观察：

```sql
SELECT page, count()
FROM analytics_lab.page_events
WHERE event_date = '2026-10-01'
GROUP BY page;

SYSTEM FLUSH LOGS;

SELECT
    event_time,
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes) AS read_bytes,
    formatReadableSize(memory_usage) AS memory,
    query
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query LIKE '%analytics_lab.page_events%'
ORDER BY event_time DESC
LIMIT 5;
```

`SYSTEM FLUSH LOGS` 让内存中的日志尽快写入系统表，适合实验后的即时查看；它不是每条业务查询后都要调用的命令。输出中的重点是：

- `query_duration_ms`：总耗时，但会受机器负载、缓存和并发影响；
- `read_rows` / `read_bytes`：实际读了多少数据，是判断过滤是否有效的关键证据；
- `memory_usage`：这个查询的内存峰值线索；
- `query`：用于回到 SQL 本身检查条件、聚合、Join 或排序。

## 2. 慢查询的排查顺序：先少读，再少算

不要看到查询慢就先加机器或加“索引”。用下面顺序排查通常更有效。

### 第一步：确认问题 SQL 与样本量

按归一化查询哈希汇总，可以避免相同 SQL 因日期参数不同而散成多行：

```sql
SELECT
    normalized_query_hash,
    count() AS runs,
    quantileTDigest(0.50)(query_duration_ms) AS p50_ms,
    quantileTDigest(0.95)(query_duration_ms) AS p95_ms,
    round(avg(read_rows)) AS average_read_rows,
    formatReadableSize(toUInt64(avg(read_bytes))) AS average_read_bytes,
    any(query) AS example
FROM system.query_log
WHERE type = 'QueryFinish'
  AND event_time >= now() - INTERVAL 1 HOUR
GROUP BY normalized_query_hash
ORDER BY p95_ms DESC
LIMIT 20;
```

样本只有一次时，P95 并不可靠；先看 `runs`，再下结论。

### 第二步：检查是否能跳过无关数据

对可疑 SQL 用 `EXPLAIN indexes = 1`：

```sql
EXPLAIN indexes = 1
SELECT page, count()
FROM analytics_lab.page_events
WHERE event_date = '2026-10-01'
  AND page = '/search'
GROUP BY page;
```

问两个问题：是否给了时间范围？条件是否接近排序键左前缀？课程表的排序键是 `(event_date, page, event_time)`，因此上面的日期和页面条件通常有帮助。若报表每次都扫多年数据，先明确它是否真的需要多年明细，而不是先调 `index_granularity`。

### 第三步：检查计算是否过重

即使读得不多，以下操作也可能很重：高基数 `GROUP BY`、大表之间的 Join、全局 `ORDER BY`、`FINAL`、把大字符串取回客户端。先缩小时间窗、只选择必要列、限制结果集，并判断是否真的需要实时明细；重复的固定汇总才考虑上一篇的物化视图。

## 3. 正在运行的查询怎样安全处理

查看实时查询：

```sql
SELECT
    query_id,
    user,
    elapsed,
    read_rows,
    formatReadableSize(memory_usage) AS memory,
    query
FROM system.processes
ORDER BY elapsed DESC;
```

只有确认 `query_id`、发起用户和影响范围后，才可以取消自己的测试查询：

```sql
KILL QUERY WHERE query_id = 'replace-with-a-verified-query-id' SYNC;
```

不要复制别人的 query ID 或把 `KILL QUERY` 作为常规性能工具。它停止的是当前工作，不能修复导致查询过重的表设计或应用逻辑。

## 4. 从 part 和 merge 发现写入问题

`system.parts` 告诉你有效数据片段的数量与大小：

```sql
SELECT
    partition,
    count() AS active_parts,
    sum(rows) AS rows,
    formatReadableSize(sum(bytes_on_disk)) AS disk_size
FROM system.parts
WHERE database = 'analytics_lab'
  AND table = 'page_events'
  AND active
GROUP BY partition
ORDER BY active_parts DESC;

SELECT database, table, elapsed, progress, num_parts, result_part_name
FROM system.merges
ORDER BY elapsed DESC;
```

part 数持续增长且 merge 长期追不上，最常见的根因是小批 INSERT、过细分区或上游失败重试。正确的第一动作是回看写入批次和生产者日志，而不是对整张表执行：

```sql
-- 不要把它当作日常“修复”命令：
OPTIMIZE TABLE analytics_lab.page_events FINAL;
```

`FINAL` 会请求强制合并，可能同时占用大量读取、写入、CPU 和额外磁盘空间；它在繁忙大表上反而可能扩大事故。仅在理解影响范围、有足够空间的隔离或维护窗口里，对小范围练习验证其作用。

磁盘也要从数据库自身观察：

```sql
SELECT
    name,
    path,
    formatReadableSize(free_space) AS free,
    formatReadableSize(total_space) AS total
FROM system.disks;
```

容量不能只按当前表大小估计。merge 期间旧 part 与新 part 会短暂共存，备份也要空间，日志和操作余量同样要保留。删掉数据后空间没有立即下降时，先查看活跃 part、正在执行的 merge/mutation 和文件系统情况，别连续进行未知范围的删除。

## 5. 给查询设置保护栏

分析库的 SQL 表达能力很强，意味着错误查询也可能非常昂贵。成熟环境通常会按用户或 workload 设置最大内存、最大执行时间、最大读行数/字节、并发数等限制，并把交互查询与离线批处理隔离。

具体阈值必须依据真实负载测试，不能照抄示例。即使数据库有保护栏，应用也应做四件基础事情：

- 只允许参数化查询或白名单拼接，避免把外部输入拼成 SQL；
- 对交互页面强制时间范围与结果上限；
- 为报表和批任务使用不同身份，便于追责和限流；
- 记录查询目的和数据敏感级别，避免日志意外暴露个人数据。

## 6. 备份、恢复与验证：三件不同的事

**备份**是取得一个可用于恢复的一致副本；**恢复**是把副本变回一个可读的数据库对象；**验证**是证明恢复结果确实正确。把正在运行的 Docker volume 直接复制到某个目录，通常不能代替经过验证的数据库备份。

ClickHouse 支持 `BACKUP` / `RESTORE`，但备份目标必须由服务端配置为允许使用的磁盘或对象存储。不要为了跑通下面的命令随意把任意宿主机目录暴露给数据库进程。准备好独立的受控备份目标 `backups` 后，示意流程如下：

```sql
BACKUP TABLE analytics_lab.page_events
TO Disk('backups', 'clickhouse-course/page-events-demo');

SELECT id, status, error, start_time, end_time
FROM system.backups
ORDER BY start_time DESC
LIMIT 5;
```

只有状态成功还不够。请在**隔离实例**恢复到新数据库名，防止覆盖原表：

```sql
RESTORE TABLE analytics_lab.page_events
AS analytics_restore.page_events
FROM Disk('backups', 'clickhouse-course/page-events-demo');

SELECT
    (SELECT count() FROM analytics_lab.page_events) AS source_rows,
    (SELECT count() FROM analytics_restore.page_events) AS restored_rows;

SELECT event_date, count()
FROM analytics_restore.page_events
GROUP BY event_date
ORDER BY event_date;
```

再抽样比较关键聚合、表 DDL 和分区。记录这次演练花了多久（RTO 的线索）以及备份数据离故障时刻有多久（RPO 的线索）。若还没有受控备份目标，先完成设计和隔离测试；不要假装“有 volume”就已经具备恢复能力。

## 7. 常见症状与第一动作

| 症状 | 先查什么 | 不要立刻做什么 |
| --- | --- | --- |
| INSERT 越来越慢 | 写入批次、分区数、`system.parts`、重试日志 | 对整表 `OPTIMIZE FINAL` |
| 某个报表很慢 | `query_log` 的读量、时间条件、`EXPLAIN` | 先换机器或乱加索引 |
| 磁盘快速增长 | active part、merge、备份、日志、TTL | 删除不确定的分区 |
| 数据重复 | 稳定事件 ID、上游超时与重试记录 | 假设后台 merge 会自动去重 |
| 备份“成功”但不放心 | 隔离恢复、行数、聚合、抽样、DDL | 仅凭备份文件存在宣布安全 |

## 课程回顾

你现在应当能串起一条完整因果链：分析查询读少数列；批量写入形成 part；part 在分区内按排序键排列并由后台 merge；查询日志与系统表让你验证读量和存储状态；TTL、备份和隔离恢复让数据生命周期可管理。

这就是 ClickHouse 的基本功。更复杂的副本、分片、集群与专用引擎应建立在这套单机、可观察、可恢复的基础上；否则规模只会把原本看不见的问题放大。
