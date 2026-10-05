+++
date = '2026-10-02T20:20:00+08:00'
draft = false
title = 'ClickHouse 25.12：Docker、SQL 与系统表动手实验'
+++

这一篇的目标很小也很具体：在自己的机器上运行一个独立 ClickHouse，创建一张表，写入数据，提出问题，再查看数据库为回答问题读了多少数据。只要完成这一轮，你就不再只是“知道 ClickHouse 有 part”，而是看过它。

## 1. 启动一个不会碰到其他服务的实验实例

下面的命令创建名为 `ch-lab` 的容器、两个以 `ch-lab` 开头的独立 volume，并将容器端口映射到本机不常用的端口。密码只存在于当前 PowerShell 会话；请换成自己的随机值，不要把它提交到仓库。

```powershell
$env:CH_LAB_PASSWORD = 'replace-with-a-local-random-secret'

docker run -d --name ch-lab `
  -e CLICKHOUSE_DB=analytics_lab `
  -e CLICKHOUSE_USER=lab_user `
  -e CLICKHOUSE_PASSWORD=$env:CH_LAB_PASSWORD `
  -p 18123:8123 -p 19000:9000 `
  -v ch-lab-data:/var/lib/clickhouse `
  -v ch-lab-logs:/var/log/clickhouse-server `
  clickhouse/clickhouse-server:25.12
```

这里 `8123` 是 HTTP 接口，`9000` 是原生 TCP 协议；左边的 `18123`、`19000` 是本机端口。等待十几秒后检查状态：

```powershell
docker ps --filter 'name=ch-lab'
docker logs --tail 30 ch-lab
docker exec ch-lab clickhouse-client --user lab_user --password $env:CH_LAB_PASSWORD --query 'SELECT version()'
```

最后一条会输出类似 `25.12.x.x`。若容器立刻退出，先运行 `docker logs ch-lab`；常见原因是端口已被占用、Docker 内存不足，或先前同名容器仍在。先解决明确错误，别通过反复重启掩盖它。

## 2. 认识 `clickhouse-client` 与第一条 SQL

`clickhouse-client` 是随服务镜像带的命令行客户端。下面的命令在容器内执行 SQL；你也可以省略 `--query` 进入交互模式，使用 `exit` 退出。

```powershell
docker exec -it ch-lab clickhouse-client `
  --user lab_user --password $env:CH_LAB_PASSWORD `
  --query 'SELECT currentDatabase(), now()'
```

预期会有两列：当前数据库 `analytics_lab` 与当前时间。SQL 语句末尾的分号对 `--query` 不是必须；在交互模式中建议保留，便于阅读。

## 3. 建立第一张事件表

把下面 SQL 原样送给客户端。`CREATE DATABASE IF NOT EXISTS` 的含义是“若不存在才创建”，便于重复执行实验。`SHOW CREATE TABLE` 会把数据库实际保存的 DDL 返回给你，这是检查建表是否符合预期的可靠方法。

```powershell
@'
CREATE DATABASE IF NOT EXISTS analytics_lab;

CREATE TABLE IF NOT EXISTS analytics_lab.page_events
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

SHOW CREATE TABLE analytics_lab.page_events;
'@ | docker exec -i ch-lab clickhouse-client --user lab_user --password $env:CH_LAB_PASSWORD --multiquery
```

请停下来对照上一节：`event_date` 由时间自动生成；月是分区；日期、页面、时间是 part 内排序顺序。不要现在就试图优化它，先让它产生可观察的数据。

## 4. 先手工插入三行，再批量生成十万行

手工数据帮助你确认字段顺序和查询结果。显式写出列名是好习惯：当表新增列时，插入语句不会悄悄错位。

```sql
INSERT INTO analytics_lab.page_events
    (event_time, user_id, page, status_code, latency_ms, request_body)
VALUES
    ('2026-10-01 09:00:00', 'u-1', '/home', 200, 18, 'first visit'),
    ('2026-10-01 09:00:02', 'u-2', '/search', 200, 55, 'find a book'),
    ('2026-10-01 09:00:05', 'u-1', '/checkout', 500, 731, 'payment failed');

SELECT event_time, user_id, page, status_code, latency_ms
FROM analytics_lab.page_events
ORDER BY event_time;
```

把这段粘贴到交互客户端，或通过上一节的 here-string 加 `--multiquery` 执行。预期返回 3 行，且 `event_date` 虽未插入也已被自动计算。

三行不足以显示分析特征。下面用内置的 `numbers(100000)` 产生 100,000 个递增整数，再用表达式构造模拟事件。它是数据库内部生成数据，不需要下载文件。

```powershell
@'
INSERT INTO analytics_lab.page_events
SELECT
    toDateTime('2026-10-01 00:00:00', 'UTC') + toIntervalSecond(number % 172800),
    concat('u-', toString(number % 1000)),
    arrayElement(['/home', '/search', '/product', '/checkout'], 1 + number % 4),
    if(number % 50 = 0, 500, 200),
    toUInt32(number % 1200),
    concat('payload-', toString(number))
FROM numbers(100000);

SELECT count() AS rows, min(event_time), max(event_time)
FROM analytics_lab.page_events;
'@ | docker exec -i ch-lab clickhouse-client --user lab_user --password $env:CH_LAB_PASSWORD --multiquery
```

预期 `rows` 为 `100003`。若不是，先只运行最后一条 `SELECT count()`；不要直接再执行大批 INSERT，否则会让你难以判断是生成失败还是重复写入。

## 5. 从“取数据”到“问问题”

分析查询通常不是把每一行返回给应用，而是让数据库计算一个摘要。例如下面问题是“每个页面访问了几次，平均耗时多少，错误多少”：

```sql
SELECT
    page,
    count() AS visits,
    round(avg(latency_ms), 2) AS average_ms,
    countIf(status_code >= 500) AS errors
FROM analytics_lab.page_events
WHERE event_date = '2026-10-01'
GROUP BY page
ORDER BY visits DESC;
```

`countIf` 是条件计数；`GROUP BY page` 表示每个页面得到一组结果。注意这个查询只用到日期、页面、状态码和耗时，并没有读 `request_body` 的业务内容。这正是列式读取有优势的场景。

## 6. 看见 part：不要猜写入发生了什么

`system` 是 ClickHouse 自己维护的系统数据库。`system.parts` 记录每张 MergeTree 表的数据片段。只统计 `active` part，因为完成 merge 的旧 part 短暂存在也不代表当前查询会用它。

```sql
SELECT
    partition,
    name,
    rows,
    formatReadableSize(bytes_on_disk) AS disk_size
FROM system.parts
WHERE database = 'analytics_lab'
  AND table = 'page_events'
  AND active
ORDER BY partition, name;
```

你通常会看到至少一个 `202610` 分区和若干 part。具体 part 数不是固定答案：手工 INSERT 与批量 INSERT 各自可能形成一个 part，后台 merge 的完成时间也会影响结果。关键是理解 `rows` 相加应接近表行数，而不是期待截图中出现某个特定 part 名。

## 7. 用 `EXPLAIN` 和 query log 检查查询成本

先让 ClickHouse 展示它如何考虑索引条件：

```sql
EXPLAIN indexes = 1
SELECT count()
FROM analytics_lab.page_events
WHERE event_date = '2026-10-01'
  AND page = '/search';
```

输出格式会随小版本而变，阅读目标是确认条件出现在分区或主键过滤阶段。接着实际执行两条查询：一条带日期，一条故意不带日期。

```sql
SELECT count()
FROM analytics_lab.page_events
WHERE event_date = '2026-10-01' AND page = '/search';

SELECT count()
FROM analytics_lab.page_events
WHERE page = '/search';
```

刷新日志后查看 `read_rows` 和 `read_bytes`：

```sql
SYSTEM FLUSH LOGS;

SELECT
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes) AS read_bytes,
    query
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query LIKE '%page_events%'
ORDER BY event_time DESC
LIMIT 5;
```

十万行时两条查询可能都很快，这很正常。学习点是：读取行数和字节数是能随数据规模外推的证据；只看一次“耗时 3ms”通常没有意义。若 `query_log` 暂时为空，确认查询在同一实例执行，然后再执行一次 `SYSTEM FLUSH LOGS`。

## 8. 可选：用 HTTP 写一行

HTTP 接口适合脚本和 ETL。下面的例子使用 `JSONEachRow`，每行 JSON 对应一条记录。真实程序应在发送前校验数据，而不要把任意外部 JSON 直接写进数据库。

```powershell
$headers = @{ 'X-ClickHouse-User' = 'lab_user'; 'X-ClickHouse-Key' = $env:CH_LAB_PASSWORD }
$body = @'
{"event_time":"2026-10-02 12:00:00","user_id":"u-http","page":"/api","status_code":200,"latency_ms":42,"request_body":"from http"}
'@

Invoke-WebRequest -Method Post `
  -Uri 'http://localhost:18123/?query=INSERT%20INTO%20analytics_lab.page_events%20FORMAT%20JSONEachRow' `
  -Headers $headers -Body $body
```

再用 `SELECT *` 的简短投影确认这一行。HTTP 成功只证明请求被接受；批量摄入中仍需记录批次 ID、行数和源位置，下一篇会解释原因。

## 9. 实验结束后的清理

停止和删除容器不会删除 named volume。这样你可以之后重新启动并保留数据。只有明确不再需要练习数据时，才删除名称已经核对过的 volume。

```powershell
docker stop ch-lab
docker rm ch-lab
docker volume ls --filter 'name=ch-lab'
Write-Host '确认名称无误后才执行：docker volume rm ch-lab-data ch-lab-logs'
```

现在你已经看过表、行、列、part、分区、查询日志的实际形态。接下来学习那些决定它是否能长期稳定工作的选择：[摄入、分区、排序键与 TTL](03-ingestion-partition-orderby-ttl.md)。
