+++
date = '2026-03-03T20:25:57+08:00'
draft = false
title = '使用 MySQL 的 Binlog 更新 ES 数据时，如何判断下一次数据读取的位置'
+++

用 MySQL Binlog 同步 Elasticsearch 时，最核心的问题不是“怎么解析一条变更”，而是：**程序重启、崩溃、重试之后，下一次应该从哪里继续读。**

这个位置通常叫：

- offset
- checkpoint
- binlog 位点
- 消费进度

名字很多，意思只有一个：**已经安全处理到哪里了。**

如果位点提交得太早，ES 还没写成功，程序却认为自己已经处理过了，就会丢数据。位点提交得太晚，程序重启后会重复消费。重复通常可以靠幂等解决，丢数据则更麻烦。所以工程上宁可重复，也不要丢。

## 一、Binlog 位点由什么组成

常见位点有两种表达方式。

### 1. file + position

最传统的方式是记录 binlog 文件名和位置：

```text
binlog_file = mysql-bin.000123
binlog_pos = 456789
```

启动时，Binlog client 从这个位置继续读取。

这种方式直观、通用，但在主从切换、binlog rotate、备份恢复等场景下，需要额外小心。

### 2. GTID set

如果 MySQL 开启了 GTID，更推荐记录 GTID set。

```text
gtid_set = 3E11FA47-71CA-11E1-9E33-C80AA9429562:1-12345
```

GTID 的优点：

- 每个事务有全局唯一 ID。
- 主从切换后更容易继续消费。
- 不强依赖某个具体 binlog 文件名。

如果基础设施支持 GTID，优先使用 GTID。否则使用 `file + position` 也完全可以，只是故障切换时要更谨慎。

## 二、checkpoint 应该什么时候提交

一句话规则：

> **checkpoint 必须在下游 ES 写入成功之后提交。**

不能先提交位点，再写 ES。

错误流程：

```text
读取 binlog event
  ↓
提交 checkpoint
  ↓
写 ES
  ↓
程序崩溃
```

这会导致程序重启后从新 checkpoint 继续读，但 ES 实际没有写成功，于是数据丢失。

正确流程：

```text
读取 binlog event
  ↓
转换为同步任务
  ↓
写 ES 成功
  ↓
提交 checkpoint
```

如果程序在 ES 写成功后、checkpoint 提交前崩溃，会发生重复消费。但只要 ES 写入是幂等的，重复消费可以接受。

## 三、保存 event start position 还是 next position

Binlog event 通常会有两个位置概念：

- event start position：当前事件开始的位置。
- event end position / next position：当前事件结束后，下一个事件开始的位置。

应该保存的是：

> **最后一条已成功处理事件的 next position。**

原因很简单：重启后从这个位置读，刚好从下一条事件开始。

如果保存 start position，重启后会重新读同一个事件。虽然幂等可以兜底，但没有必要主动制造重复。

## 四、事务边界比单条事件更重要

很多人会把 binlog event 当成一条条独立消息处理，但 MySQL 事务并不是这样。

一个事务可能包含多条 row event：

```text
BEGIN
  table_a row event
  table_b row event
  table_c row event
XID / COMMIT
```

如果在事务中间提交 checkpoint，程序崩溃后可能从半个事务的位置继续读，导致同步状态不完整。

更稳的做法是按事务提交：

```text
读取 BEGIN
  ↓
缓存同一事务内的 row events
  ↓
读取 XID / COMMIT
  ↓
批量写 ES
  ↓
全部成功后提交事务结束位点
```

也就是说，checkpoint 最好记录到**最后一个成功处理事务的提交点**。

## 五、批量处理时如何提交位点

实际同步服务不会每处理一条 event 就写一次 checkpoint，那样太慢。更常见的是批量提交。

示例流程：

```text
拉取一批 binlog events
  ↓
按事务聚合
  ↓
转换成 ES bulk 请求
  ↓
bulk 全部成功
  ↓
提交这一批中最后一个事务的 next position / GTID
```

需要注意：Bulk API 可能出现部分成功、部分失败。

因此不能只看 HTTP 状态码。必须检查每一条 item 的结果：

```json
{
  "errors": true,
  "items": [
    {
      "index": {
        "_id": "10001",
        "status": 200
      }
    },
    {
      "index": {
        "_id": "10002",
        "status": 429,
        "error": {
          "type": "es_rejected_execution_exception"
        }
      }
    }
  ]
}
```

只有这一批里需要确认的事件全部处理成功，才能提交 checkpoint。

## 六、checkpoint 存在哪里

常见选择有三种。

### 1. MySQL 表

最通用，也最容易审计。

```sql
CREATE TABLE binlog_checkpoint (
  id BIGINT PRIMARY KEY,
  source_name VARCHAR(64) NOT NULL,
  binlog_file VARCHAR(128) NULL,
  binlog_pos BIGINT NULL,
  gtid_set TEXT NULL,
  last_event_time DATETIME NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uk_source_name (source_name)
);
```

适合大多数自研同步服务。

### 2. Redis

Redis 写入快，但要确保持久化和高可用。

如果 Redis 丢了 checkpoint，同步服务可能从较早位置重放大量数据。只要幂等还好；如果 binlog 已被清理，那就麻烦了。

### 3. 组件内置 offset store

例如 Kafka Connect、Debezium 一类工具有自己的 offset 存储机制。使用成熟组件时，优先遵循组件的位点管理方式，不要额外发明一套“看起来很聪明”的机制。

大多数时候，那并不聪明。

## 七、如何保证不丢不重

严格说，Binlog 到 ES 很难做到真正的 exactly-once。更现实的目标是：

> **至少一次消费 + 幂等写 ES + 可补偿对账。**

### 1. 至少一次

checkpoint 在 ES 写成功后提交。

这样崩溃时最多重复，不会丢。

### 2. 幂等写入

ES `_id` 使用 MySQL 主键：

```http
PUT /product_index/_doc/10001
{
  "id": 10001,
  "name": "iPhone 15 Pro"
}
```

重复写同一条数据，只会覆盖同一个文档。

### 3. 防止乱序覆盖

如果同步链路有多线程、MQ 重试、分区调整，就可能出现旧事件后到。

应对方式：

- 同一业务 ID 固定进入同一分区。
- ES 文档保存 `version` 或 `updated_at`。
- 写入时判断旧版本不能覆盖新版本。
- 或者事件只带 ID，消费者回查 MySQL 最新值后覆盖写 ES。

## 八、程序重启时的恢复流程

一个同步服务启动时，通常这样做：

```text
读取 checkpoint
  ↓
校验 binlog 文件是否还存在
  ↓
从 checkpoint 指定位置开始消费
  ↓
如果位点不存在，触发全量重建或人工修复
```

一定要检查 binlog 是否还在。

如果 MySQL 的 binlog 已经被清理，而 checkpoint 又落后太多，同步服务无法继续增量同步。此时通常只能：

1. 停止增量同步。
2. 重新做全量同步。
3. 切换 alias。
4. 再恢复增量链路。

这也是为什么要监控同步延迟。如果延迟大到超过 binlog 保留时间，后果就不会很可爱。

## 九、推荐实现流程

可以按下面的方式实现一个简化版同步器：

```text
启动
  ↓
读取 checkpoint
  ↓
连接 MySQL binlog
  ↓
按事务读取 row events
  ↓
转换出受影响的业务 ID
  ↓
回查 MySQL 组装完整 ES 文档
  ↓
Bulk 写入 ES
  ↓
检查 bulk item 是否全部成功
  ↓
提交 checkpoint
```

为什么推荐回查 MySQL？

因为 binlog 里的一次 row event 可能只是局部字段变更，而 ES 文档通常是宽表。回查 MySQL 可以组装当前最新完整状态，也能降低乱序覆盖风险。

## 十、监控指标

Binlog 同步至少要监控：

- 当前 checkpoint。
- 同步延迟，即 binlog event 时间与当前时间的差值。
- 每秒处理事件数。
- ES bulk 成功率。
- ES bulk 失败原因分布。
- 重试次数。
- 死信数量。
- binlog 文件保留时间是否足够。

没有监控的同步链路，看起来安静时不代表没问题，只是还没人发现它有问题。

## 十一、一句话答案

使用 MySQL Binlog 更新 ES 时，下一次读取位置应该记录为：

> **最后一个已经成功写入 ES 的事件或事务的 next position，或者对应的 GTID set。**

并且：

- checkpoint 必须在 ES 写入成功后提交。
- 最好按事务提交位点。
- Bulk 要检查每个 item 的结果。
- 重复消费靠 ES `_id` 幂等解决。
- 丢数据靠延迟监控、死信和定时对账补偿兜底。

这才是工程上真正能站得住的答案。
