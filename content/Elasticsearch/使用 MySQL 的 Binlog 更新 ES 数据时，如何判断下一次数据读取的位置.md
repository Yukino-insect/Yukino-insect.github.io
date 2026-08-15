+++
date = '2026-03-03T20:25:57+08:00'
draft = false
title = '使用 MySQL 的 Binlog 更新 ES 数据时，如何判断下一次数据读取的位置'
+++

用 MySQL Binlog 同步 ES（无论你用 Canal、Debezium、Maxwell、自己写 Binlog client），核心就是**维护一个“位点（offset/checkpoint）”**：下次从哪里继续读。

位点通常由两部分组成：

- **binlog 文件名**：`mysql-bin.000123`
- **binlog 位置**：`pos=456789`
   -（可选更稳）**GTID set**：`uuid:1-12345`（MySQL 开启 GTID 时）

------

## 1) 最通用做法：记录 `(binlog_file, position)` 作为 checkpoint

### 读取时的起点

启动/重启时：

1. 先从你自己的存储（MySQL/Redis/本地文件/ZK）读出上次保存的 `file+pos`
2. Binlog client 从该位置继续拉

### 什么时候更新 checkpoint？

不要每条事件都写 checkpoint（太慢），常用策略：

- **按批次**：一批事件处理完（写 ES 成功）再更新一次 checkpoint
- **按时间**：每 N 秒刷一次 checkpoint（且只刷“已确认成功处理”的最大位点）

 关键原则：**checkpoint 必须在“下游处理成功”之后提交**
 否则会出现：位点前移了但 ES 没写成功 -> 数据丢失。

------

## 2) 更稳的做法：用 GTID 做位点（强烈推荐有 GTID 就用）

如果 MySQL 开启 GTID，位点用 **GTID set** 更靠谱：

- 不怕 binlog rotate（文件切换）
- 主从切换/故障转移时更容易继续（只要 GTID 连续）

做法同样是：

- 处理成功后记录 “已消费到的 GTID set”
- 重启后从 GTID set 开始继续

> Debezium/Canal 等成熟组件大多支持 GTID/pos 两套方案。

------

## 3) “下一次读取的位置”具体怎么判断？（精确规则）

###  正确方式：用**最后一条已成功处理事件**的位点

对于每个 binlog event，client 都能拿到一个“事件结束位置”或“下一个位置”（next_position）。
 你应保存：

> `next_position`（或 event end position），而不是 event start position。

这样重启后从该位置开始，不会重复读同一条事件。

------

## 4) 事务边界怎么处理？（很多人踩坑）

binlog 里事务是多事件组成（BEGIN/ROW events/XID）。如果你在事务中间就更新 checkpoint，会导致重启后可能从事务中间开始，出现不一致。

常见策略：

- **只在事务提交（XID）后提交 checkpoint**
- 或者“按事务聚合”：收齐同一事务的 row events -> 写 ES 成功 -> 再提交该事务对应的位点

这也是为什么很多工具会提供 “transactional” 的 offset 提交方式。

------

## 5) 如何保证“不丢不重”（至少一次 / 精确一次）

严格来说，Binlog->ES 很难做到真正 exactly-once，工程上通常做：

### A. 至少一次（At-least-once）+ ES 写入幂等（最常见）

- checkpoint 在 ES 写成功后提交 -> 可能重复消费（崩溃在 checkpoint 前）
- ES 写入用幂等策略：
  - `_id = mysql primary key`
  - 更新覆盖 `index()` 或 `update()`
     这样重复事件不会导致脏数据，只是多写一次。

### B. 防止乱序覆盖（可选增强）

如果你的更新可能乱序到达（多线程、重试），在 ES 文档里存：

- `update_time` 或 `version`
   写 ES 时做版本判断（小于现有版本就丢弃）。

------

## 6) 实战推荐：checkpoint 存哪儿？

常见三选一：

1. **MySQL 一张表**（最通用、可审计）
2. **Redis**（快，但要持久化/高可用，否则丢位点）
3. **Kafka Connect / Debezium 内置 offset store**（如果你用它们）

一张表的设计示例：

```
CREATE TABLE binlog_checkpoint (
  id BIGINT PRIMARY KEY,
  source VARCHAR(64) NOT NULL,         -- 比如 mysql1 / shard1
  binlog_file VARCHAR(64) NOT NULL,
  binlog_pos BIGINT NOT NULL,
  gtid_set TEXT NULL,
  updated_at DATETIME NOT NULL
);
```

------

## 7) 一句话答案

> **下一次读取位置 = 上次“已成功写入 ES 的最后事件/最后事务”的 binlog 文件 + next_position（或 GTID set）**。
>  checkpoint 必须在下游成功后提交，且最好按事务提交点提交。
