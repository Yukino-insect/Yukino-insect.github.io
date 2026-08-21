+++
date = '2025-10-07T18:42:03+08:00'
draft = false
title = 'Canal'
+++

Canal 是阿里巴巴开源的 MySQL binlog 增量订阅和消费组件。它会伪装成 MySQL 从库，订阅主库 binlog，把数据库中的 `insert`、`update`、`delete` 解析成变更事件，再推送给下游系统。

它常用于数据库增量同步、搜索索引更新、缓存刷新、审计日志和实时数仓链路。

## 工作原理

MySQL 主从复制的基本流程是：

```text
主库写入 binlog
  -> 从库通过 dump 协议拉取 binlog
  -> 从库重放 binlog
```

Canal 利用了这个机制：

```text
MySQL 主库
  -> binlog
  -> Canal Server 伪装成从库拉取日志
  -> 解析 RowData
  -> Canal Client / MQ / Adapter 消费变更
```

只要 MySQL 开启 binlog，并且 binlog 格式满足要求，Canal 就可以读取行级变更。

## 应用场景

常见场景：

- MySQL 到 Elasticsearch，保持搜索索引实时更新。
- MySQL 到 Redis，根据变更刷新或删除缓存。
- MySQL 到 Kafka，再由 Flink、业务服务或数据平台消费。
- MySQL 到 MySQL，实现跨库或跨机房增量同步。
- 监听关键表变更，生成审计日志或触发告警。

Canal 的核心价值是从数据库日志中捕获变更，避免在业务写路径里同步调用多个下游系统。

## 架构组件

```text
MySQL
  -> Canal Server
      -> Canal Instance
      -> Event Store
      -> Canal Client
      -> Canal Adapter / MQ
```

主要组件：

| 组件 | 说明 |
| --- | --- |
| Canal Server | 核心服务，负责连接 MySQL、拉取和解析 binlog |
| Canal Instance | 一个订阅通道，通常对应一个 MySQL 实例或一组过滤规则 |
| Canal Client | 业务代码直接连接 Canal Server 消费事件 |
| Canal Adapter | 将变更投递到 MQ、Elasticsearch、RDB 等下游 |
| Event Store | Canal 内部存储解析后的事件 |

一个 Canal Server 可以配置多个 Instance。每个 Instance 有独立的 `instance.properties`。

## MySQL 前置配置

MySQL 需要开启 binlog，并建议使用 row 格式：

```ini
[mysqld]
server-id=1
log-bin=mysql-bin
binlog-format=ROW
binlog-row-image=FULL
```

说明：

- `server-id` 必须配置，且在复制拓扑中唯一。
- `log-bin` 开启 binlog。
- `binlog-format=ROW` 记录行级变更，Canal 才能准确解析字段变化。
- `binlog-row-image=FULL` 会记录完整行数据，更适合下游同步。

创建 Canal 账号：

```sql
CREATE USER 'canal'@'%' IDENTIFIED BY 'canal_password';
GRANT SELECT, REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'canal'@'%';
FLUSH PRIVILEGES;
```

如果只授权部分库表，需要确保 Canal 能读取目标表结构，否则解析字段时可能出问题。

## 单实例配置

`conf/example/instance.properties` 示例：

```properties
canal.instance.master.address=127.0.0.1:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal_password

canal.instance.connectionCharset=UTF-8
canal.instance.filter.regex=demo\\..*
```

启动：

```bash
sh bin/startup.sh
```

停止：

```bash
sh bin/stop.sh
```

查看日志：

```bash
tail -f logs/canal/canal.log
tail -f logs/example/example.log
```

## 多实例配置

目录结构：

```text
conf/
  canal.properties
  example/
    instance.properties
  userdb/
    instance.properties
  orderdb/
    instance.properties
```

在 `canal.properties` 中指定需要加载的实例：

```properties
canal.destinations=example,userdb,orderdb
```

`userdb/instance.properties`：

```properties
canal.instance.master.address=127.0.0.1:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal_password
canal.instance.filter.regex=userdb\\..*
```

`orderdb/instance.properties`：

```properties
canal.instance.master.address=192.168.10.21:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal_password
canal.instance.filter.regex=orderdb\\.t_order
```

多实例适合按业务库、物理库或不同下游链路拆分订阅。拆分后故障隔离更清晰，但配置和监控也会更多。

## 表过滤

使用 `canal.instance.filter.regex` 指定要监听的库表：

```properties
# 监听 userdb 库所有表
canal.instance.filter.regex=userdb\\..*

# 监听两张指定表
canal.instance.filter.regex=userdb\\.t_user,orderdb\\.t_order

# 监听所有库下以 t_ 开头的表
canal.instance.filter.regex=.*\\.t_.*
```

使用 `canal.instance.filter.black.regex` 排除表：

```properties
canal.instance.filter.regex=.*\\..*
canal.instance.filter.black.regex=.*\\.(binlog_backup|sys_log)
```

注意 `.` 在正则里需要转义。配置错了不会替你害羞，它只会安静地监听错误的表。

## Java Client 消费

业务系统可以直接使用 Canal Client 拉取事件：

```java
CanalConnector connector = CanalConnectors.newSingleConnector(
        new InetSocketAddress("127.0.0.1", 11111),
        "example",
        "canal",
        "canal"
);

connector.connect();
connector.subscribe("demo\\..*");
connector.rollback();

while (running) {
    Message message = connector.getWithoutAck(100);
    long batchId = message.getId();

    try {
        if (batchId != -1 && !message.getEntries().isEmpty()) {
            handle(message);
        }
        connector.ack(batchId);
    } catch (Exception e) {
        connector.rollback(batchId);
        throw e;
    }
}
```

处理事件时只关心 `ROWDATA`：

```java
private void handle(Message message) throws InvalidProtocolBufferException {
    for (CanalEntry.Entry entry : message.getEntries()) {
        if (entry.getEntryType() != CanalEntry.EntryType.ROWDATA) {
            continue;
        }

        CanalEntry.RowChange rowChange =
                CanalEntry.RowChange.parseFrom(entry.getStoreValue());
        CanalEntry.EventType eventType = rowChange.getEventType();

        for (CanalEntry.RowData rowData : rowChange.getRowDatasList()) {
            if (eventType == CanalEntry.EventType.INSERT) {
                handleInsert(rowData.getAfterColumnsList());
            } else if (eventType == CanalEntry.EventType.UPDATE) {
                handleUpdate(rowData.getBeforeColumnsList(), rowData.getAfterColumnsList());
            } else if (eventType == CanalEntry.EventType.DELETE) {
                handleDelete(rowData.getBeforeColumnsList());
            }
        }
    }
}
```

`getWithoutAck` 表示先拉取但不确认。处理成功后调用 `ack`，失败时调用 `rollback`，Canal 会重新投递该批消息。

## 直接消费还是接 MQ

小系统可以让业务服务直接连接 Canal。但生产环境更常见的方式是接入 MQ：

```text
MySQL
  -> Canal
  -> Kafka / RocketMQ
  -> 多个业务消费者
  -> ES / Redis / 数据仓库
```

接 MQ 的好处：

- Canal 和业务消费者解耦。
- 下游可以独立扩容。
- 消息可以被多个系统消费。
- 消费失败可以重试或补偿。
- 峰值流量可以被 MQ 缓冲。

代价是链路更长，需要处理消息堆积、重复消费、顺序性和监控。

## Canal 到 Kafka

Canal 可以配置 MQ 模式，把事件投递到 Kafka：

```yaml
canal:
  server:
    mode: kafka
  mq:
    servers: localhost:9092
    topic: canal-topic
```

消费者收到的通常是 JSON 消息，包含数据库、表、事件类型、变更前后数据等字段。业务侧可以根据 `database + table` 路由到不同处理器。

一个简单路由模型：

```text
CanalMessage
  -> database + table
  -> EventProcessor
  -> update ES / delete cache / audit log
```

这种模式比在一个消费者里写巨大 `if else` 更容易维护。

## 同步 Elasticsearch

MySQL 到 Elasticsearch 是 Canal 的典型场景。

常见流程：

```text
商品表发生变更
  -> Canal 捕获 binlog
  -> MQ 投递商品变更事件
  -> 消费者根据商品 ID 查询完整聚合数据
  -> 写入 Elasticsearch
```

为什么消费者收到变更后通常还要回查数据库？

- binlog 里只包含当前表的变更，不一定包含 ES 文档需要的完整聚合信息。
- 商品 ES 文档可能包含品牌、分类、库存、价格等多张表字段。
- 通过回查可以组装最终一致的搜索文档。

更新策略：

- `INSERT`：构建 ES 文档并写入。
- `UPDATE`：判断关键字段是否变化，必要时重建文档。
- `DELETE`：删除 ES 文档或标记下架。

如果变更来自品牌表、分类表这类维表，通常需要先查出受影响的商品 ID，再批量更新 ES 文档。

## 可靠性设计

Canal 链路天然是异步的，必须按“至少一次投递”设计。

### 幂等

消费者可能重复收到消息，所以写入下游要幂等：

- ES 使用业务主键作为 document id。
- Redis 删除缓存比直接更新缓存更稳。
- 审计日志使用事件唯一键去重。

### 顺序

同一行数据的多次变更最好进入同一个分区。Kafka 可以按主键作为 message key：

```text
key = table + ":" + primaryKey
```

这样同一主键的消息会尽量落在同一分区，保持局部顺序。

### 重试

消费失败不要直接丢弃：

- 短暂失败可以本地重试。
- 长时间失败进入重试队列或死信队列。
- 提供人工补偿或按主键重建索引能力。

### 全量校验

增量同步不等于永远正确。生产系统应提供定期校验或重建能力：

- 按更新时间扫描数据库。
- 对比 MySQL 和 ES 文档数量。
- 抽样校验关键字段。
- 支持按业务 ID 重新同步。

## 常见问题

### 监听不到数据

检查：

- MySQL 是否开启 binlog。
- `binlog-format` 是否为 `ROW`。
- Canal 账号是否有复制权限。
- `server-id` 是否冲突。
- `filter.regex` 是否匹配目标表。
- Canal instance 日志是否报错。

### 字段值不完整

检查 `binlog-row-image`。如果不是 `FULL`，UPDATE 事件里可能只有变化字段，下游无法获得完整行数据。

### 消费重复

这是正常现象。Canal 和 MQ 链路都可能重投，消费者必须幂等。

### ES 数据和 MySQL 不一致

常见原因：

- 消费失败后没有补偿。
- 消息乱序覆盖了新数据。
- 维表变更没有同步影响到主文档。
- 手工改库绕过了同步链路。
- 全量重建和增量消费没有处理时间窗口。

## 使用建议

- 能接 MQ 就不要让所有业务服务直接连 Canal。
- 消费者按表拆处理器，避免一个类吞掉所有逻辑。
- 下游写入必须幂等。
- 对关键索引提供重建和校验工具。
- 不要把 Canal 当强一致方案，它解决的是异步增量同步。
- 数据库表结构变更要和 Canal 消费逻辑一起评审。

Canal 很适合把数据库变更从业务写路径中解耦出来。它的边界也要记清楚：它提供的是 binlog 级别的增量事件，不是业务事务语义。真正可靠的同步链路，靠的是幂等、重试、顺序控制和补偿能力。
