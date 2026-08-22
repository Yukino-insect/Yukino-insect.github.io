+++
date = '2026-03-17T21:35:47+08:00'
draft = false
title = 'Elasticsearch 数据同步方案'
+++

在大多数业务系统里，MySQL 才是事实数据源，Elasticsearch 只是为了搜索、筛选、聚合和排序而构建出来的**检索视图**。

这句话很重要。因为只要你把 ES 当成“另一个主库”，后面遇到的所有一致性问题都会变得理所当然地痛苦。ES 可以承载高性能搜索，但它不应该承担业务事务的最终裁决。

MySQL 到 ES 的同步通常分为两个阶段：

1. **全量同步**：初始化索引，或者重建索引。
2. **增量同步**：业务运行期间持续把变更同步到 ES。

生产上的完整方案还必须包含：

- 幂等写入。
- 失败重试。
- 乱序保护。
- 死信队列。
- 定时对账和补偿。
- 索引版本化与 alias 切换。

如果方案里只有“写 MySQL 后再写 ES”，那并不是方案，只是事故的开场白。

## 一、同步前先明确边界

### 1. MySQL 与 ES 的职责

| 系统 | 更适合做什么 | 不适合做什么 |
| ---- | ------------ | ------------ |
| MySQL | 事务、约束、主数据、精确查询 | 大规模全文检索、复杂相关性排序 |
| Elasticsearch | 搜索、过滤、聚合、排序、近实时检索 | 强事务、跨文档一致性、主数据裁决 |

因此通常采用这种模型：

```text
MySQL：事实数据源
  ↓
同步链路：复制和修复数据
  ↓
Elasticsearch：面向查询的冗余索引
```

ES 中的数据允许短暂落后，但不应该永久错误。也就是说，核心目标不是“永远实时一致”，而是**最终一致、可恢复、可观测**。

### 2. 文档 ID 必须稳定

最基础也最容易被忽视的一点：ES 文档 `_id` 应该使用 MySQL 的业务主键。

例如商品表：

```text
product.id = 10001
```

写入 ES 时：

```http
PUT /product_index/_doc/10001
{
  "id": 10001,
  "name": "iPhone 15 Pro",
  "price": 699900,
  "updated_at": "2026-08-22T10:00:00+08:00"
}
```

这样重复消费同一条消息时只是覆盖同一个文档，不会生成重复数据。

如果 ES `_id` 随机生成，后面的重试、补偿、对账都会变成一团漂亮的灾难。漂亮只是在说反话，不必误会。

## 二、全量同步

全量同步用于初始化索引、修复大面积错误、重建 mapping 或更换分词器。

常见流程如下：

```text
创建新索引 product_v2
  ↓
临时调低 refresh 频率
  ↓
分页读取 MySQL
  ↓
Bulk 写入 ES
  ↓
校验数量和关键字段
  ↓
切换 alias：product_alias -> product_v2
  ↓
保留旧索引一段时间，确认后删除
```

### 1. 定时任务 + Bulk API

最直接的方案是应用自己分页扫描 MySQL，然后使用 Bulk API 写入 ES。

适用场景：

- 数据量不算特别大。
- 同步逻辑强依赖业务代码。
- 需要在写入 ES 前做复杂字段组装。

关键注意点：

- 分页不要使用深度 `offset`，优先按主键范围或游标分页。
- 每批 Bulk 控制大小，例如 500 到 5000 条，根据文档大小和集群压力调整。
- 大批量导入时可以临时设置 `refresh_interval = -1` 或调大 refresh 周期。
- 导入完成后恢复 refresh，并执行一次 refresh。

示例：

```http
PUT /product_v2/_settings
{
  "index": {
    "refresh_interval": "-1"
  }
}
```

导入完成：

```http
PUT /product_v2/_settings
{
  "index": {
    "refresh_interval": "1s"
  }
}
```

```http
POST /product_v2/_refresh
```

为什么要控制 refresh？

因为 refresh 会把内存 buffer 变成新的 Segment，并打开新的 Searcher。大量写入时频繁 refresh 会产生大量小 Segment，增加 merge 压力，最终拖慢整个集群。

### 2. Logstash JDBC

Logstash 可以通过 JDBC 插件定时查询 MySQL，然后写入 ES。

工作模型：

```text
input -> filter -> output
```

MySQL 到 ES 的典型链路：

```text
MySQL -> JDBC Input -> Logstash -> Elasticsearch Output
```

示例配置：

```text
input {
  jdbc {
    jdbc_driver_library => "/opt/jdbc/mysql-connector-j-8.0.33.jar"
    jdbc_driver_class => "com.mysql.cj.jdbc.Driver"
    jdbc_connection_string => "jdbc:mysql://localhost:3306/shop"
    jdbc_user => "root"
    jdbc_password => "123456"

    statement => "
      SELECT id, name, price, update_time
      FROM product
      WHERE update_time > :sql_last_value
      ORDER BY update_time ASC
    "

    schedule => "*/1 * * * *"
    use_column_value => true
    tracking_column => "update_time"
    tracking_column_type => "timestamp"
  }
}

output {
  elasticsearch {
    hosts => ["http://localhost:9200"]
    index => "product_index"
    document_id => "%{id}"
  }
}
```

`sql_last_value` 表示上一次同步到的位置，`document_id => "%{id}"` 保证 MySQL 主键和 ES `_id` 一致。

它的优点是接入简单、无需改业务代码；缺点是实时性一般，而且依赖 `update_time` 这类字段时，要小心同一时间戳下的漏读问题。

### 3. Reindex 与 alias 切换

当只是 ES 内部索引迁移时，可以使用 `_reindex`。

```http
POST /_reindex
{
  "source": {
    "index": "product_v1"
  },
  "dest": {
    "index": "product_v2"
  }
}
```

生产上更推荐通过 alias 访问索引：

```text
product_alias -> product_v1
```

重建完成后原子切换：

```http
POST /_aliases
{
  "actions": [
    { "remove": { "index": "product_v1", "alias": "product_alias" } },
    { "add": { "index": "product_v2", "alias": "product_alias" } }
  ]
}
```

这样业务方一直访问 `product_alias`，不需要感知真实索引版本。

## 三、增量同步

增量同步用于把运行期的新增、修改、删除持续同步到 ES。

常见方案有四类：

| 方案 | 实时性 | 侵入性 | 可靠性 | 适用场景 |
| ---- | ------ | ------ | ------ | -------- |
| 同步双写 | 高 | 高 | 较差 | 小系统、低风险后台 |
| 异步双写 MQ | 中高 | 中 | 较好 | 常规业务系统 |
| Outbox 模式 | 中高 | 中 | 很好 | 对可靠投递要求高 |
| Binlog 监听 | 高 | 低 | 很好 | 业务零侵入、统一同步平台 |

### 1. 同步双写

同步双写是在一个业务请求里先写 MySQL，再写 ES。

```java
@Transactional
public void updateProduct(Product product) {
    productMapper.update(product);
    esService.update(product);
}
```

它看起来简单，但问题也非常明显：

- MySQL 事务和 ES 写入无法放进同一个本地事务。
- ES 慢会拖慢业务接口。
- ES 写入失败后，MySQL 已经提交，数据会不一致。
- 如果在事务内写 ES，还可能出现 ES 写成功但 MySQL 回滚的问题。

所以同步双写通常只适合低风险场景。核心交易链路不推荐。

### 2. 异步双写 MQ

更常见的方式是 MySQL 提交成功后发送 MQ，消费者再写 ES。

```text
业务服务
  ↓
写 MySQL
  ↓
发送 MQ
  ↓
ES 同步消费者
  ↓
写 Elasticsearch
```

示例：

```java
@Transactional
public void updateProduct(Product product) {
    productMapper.update(product);
    mqProducer.send("product-sync", product.getId());
}
```

消费者建议**重新查询 MySQL**，再覆盖写 ES：

```java
@MQListener(topic = "product-sync")
public void consume(Long productId) {
    Product product = productMapper.selectById(productId);

    if (product == null) {
        esService.delete(productId);
        return;
    }

    esService.index(productId, convert(product));
}
```

为什么建议重新查 MySQL？

因为 MQ 里只放 ID，可以降低消息体大小，也能避免旧消息携带旧字段直接覆盖 ES。消费者拿到 ID 后查询 MySQL 最新值，写入的是事实源当前状态。

但它仍然有一个问题：如果 MySQL 提交成功后，发送 MQ 失败怎么办？

这就需要 Outbox。

### 3. Outbox 模式

Outbox 模式的核心是：**业务数据和事件记录放在同一个 MySQL 事务里提交**。

```text
本地事务：
  1. 更新 product 表
  2. 插入 outbox_event 表
```

事务提交后，由后台任务或 CDC 工具把 `outbox_event` 发布到 MQ。

表结构示例：

```sql
CREATE TABLE outbox_event (
  id BIGINT PRIMARY KEY,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id BIGINT NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  payload JSON NULL,
  status VARCHAR(32) NOT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

写业务：

```java
@Transactional
public void updateProduct(Product product) {
    productMapper.update(product);

    outboxRepository.save(new OutboxEvent(
        "product",
        product.getId(),
        "PRODUCT_UPDATED"
    ));
}
```

优点：

- 业务更新和事件记录具备本地事务一致性。
- MQ 发送失败可以重试。
- 可审计、可补偿。

缺点：

- 多一张事件表和投递任务。
- 链路复杂度高于普通 MQ。

如果系统对同步可靠性要求较高，Outbox 比“事务后直接发 MQ”更稳。

### 4. Binlog 监听

Binlog 监听是通过 Canal、Debezium、Maxwell 等工具监听 MySQL binlog，将数据库变更转换成事件，再同步到 ES。

典型链路：

```text
MySQL
  ↓ binlog
Canal / Debezium
  ↓
Kafka / RocketMQ
  ↓
ES Sync Service
  ↓
Elasticsearch
```

优点：

- 对业务代码侵入低。
- 能统一处理多个业务表。
- 变更来源更接近数据库事实。
- 适合建设统一的数据同步平台。

难点：

- 要维护 binlog 位点。
- 要处理 DDL 变更。
- 要处理事务边界。
- 要处理消息乱序和重复消费。
- 删除事件、字段转换、宽表拼接都需要额外设计。

如果使用 Binlog 同步，建议继续阅读 [使用 MySQL 的 Binlog 更新 ES 数据时，如何判断下一次数据读取的位置](./使用%20MySQL%20的%20Binlog%20更新%20ES%20数据时，如何判断下一次数据读取的位置.md)。

## 四、删除如何同步

新增和更新一般用覆盖写即可，删除则必须额外关注。

常见策略有两种。

### 1. 物理删除同步

MySQL 删除后，同步服务删除 ES 文档：

```http
DELETE /product_index/_doc/10001
```

适合数据确实不需要展示的场景。

### 2. 软删除同步

业务表保留数据，只更新状态：

```text
deleted = 1
```

同步到 ES 后，搜索时加过滤条件：

```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "phone" } }
      ],
      "filter": [
        { "term": { "deleted": false } }
      ]
    }
  }
}
```

软删除更适合商品、内容、订单这类需要审计或可能恢复的数据。

## 五、一致性问题

### 1. 写入失败

ES 写入失败很常见：网络抖动、集群压力、mapping 冲突、线程池拒绝、磁盘水位过高，都可能导致失败。

处理方式：

- 可重试错误：指数退避重试。
- 不可重试错误：进入死信队列。
- 记录失败原因、业务 ID、事件 ID、重试次数。
- 定时任务扫描失败记录并补偿。

示例：

```java
public void writeEsWithRetry(ProductDoc doc) {
    int retry = 0;

    while (retry < 3) {
        try {
            esService.index(doc.getId(), doc);
            return;
        } catch (RetryableException ex) {
            retry++;
            sleep(1000L * retry);
        }
    }

    deadLetterRepository.save(doc.getId(), "ES_WRITE_FAILED");
}
```

不要无限重试。无限重试只是把一个错误变成一个持续制造压力的错误。

### 2. 消息重复

MQ 和 Binlog 同步通常都应该按**至少一次**处理，也就是允许重复。

应对方式：

- ES `_id = MySQL 主键`。
- 使用 `index` 覆盖写。
- 事件表记录 `event_id`，必要时做消费去重。

多数场景下，只要写入是幂等的，重复消费不是大问题。

### 3. 消息乱序

乱序才是真正麻烦的地方。

例如同一个商品连续更新两次：

```text
T1：price = 699900
T2：price = 649900
```

如果 T2 先写入 ES，T1 后写入 ES，就会发生旧数据覆盖新数据。

解决方案：

1. **消息只传 ID，消费者回查 MySQL 最新值**。
2. **同一业务 ID 进入同一个 MQ 分区或队列**。
3. **使用外部版本号**，旧版本写入时拒绝覆盖。
4. **ES 文档中保存 `updated_at` 或 `version`，脚本判断后再更新**。

使用外部版本号的思想是：MySQL 中维护一个单调递增版本。

```text
product.version = 128
```

写入 ES 时携带该版本。旧版本事件到达时，不允许覆盖新版本。

相关并发控制可继续看 [Elasticsearch 并发问题](./Elasticsearch并发问题.md)。

### 4. 消息丢失

消息丢失不能只靠“感觉应该不会”。工程系统如果只靠感觉，那就和在雨天相信纸伞不会湿差不多。

需要定时对账：

```text
定时扫描 MySQL 最近 N 分钟变更
  ↓
读取 ES 对应文档
  ↓
比较 version / updated_at / checksum
  ↓
不一致则重新写入 ES
```

示例：

```java
@Scheduled(cron = "0 */5 * * * ?")
public void reconcile() {
    List<Product> recentProducts = productMapper.selectUpdatedInLastMinutes(10);

    for (Product product : recentProducts) {
        ProductDoc esDoc = esService.get(product.getId());

        if (esDoc == null || !Objects.equals(product.getVersion(), esDoc.getVersion())) {
            esService.index(product.getId(), convert(product));
            repairLogRepository.save(product.getId(), "VERSION_NOT_MATCH");
        }
    }
}
```

对账不是失败后的临时手段，而应该是同步系统的一部分。

## 六、宽表与多表同步

很多 ES 文档不是单表字段，而是多个表拼出来的搜索宽表。

例如商品搜索文档可能来自：

```text
product
product_sku
product_price
product_stock
product_category
product_brand
```

这时同步要回答一个问题：任意一张表变更时，如何知道要更新哪一个 ES 文档？

常见做法：

- 建立反查关系，例如 `sku_id -> product_id`。
- 监听多个表变更，统一转换成 `product_id`。
- 消费端拿到 `product_id` 后重新查询 MySQL 组装完整文档。

流程：

```text
任意相关表变更
  ↓
解析出 product_id
  ↓
查询 MySQL 聚合完整商品信息
  ↓
覆盖写 product_index/_doc/{product_id}
```

不要直接用局部变更事件拼 ES 文档，除非你非常清楚字段之间的依赖。否则某个字段少一次更新，ES 里就会出现一种十分阴险的旧数据。

## 七、推荐的生产方案

如果是普通业务系统，可以这样选：

### 1. 中小系统

```text
MySQL
  ↓
业务事务后发送 MQ
  ↓
消费者按 ID 回查 MySQL
  ↓
幂等写 ES
  ↓
定时对账补偿
```

优点是实现简单，足够支撑大多数后台系统。

### 2. 对可靠性要求较高

```text
MySQL 本地事务
  ├── 更新业务表
  └── 写 outbox_event
       ↓
Outbox 投递 MQ
       ↓
ES 同步消费者
       ↓
对账补偿
```

优点是不会出现“业务提交成功但消息没发出去”的空洞。

### 3. 多业务统一同步平台

```text
MySQL binlog
  ↓
Canal / Debezium
  ↓
Kafka
  ↓
同步服务
  ↓
Elasticsearch
```

适合数据平台化、业务系统多、同步链路统一治理的场景。

## 八、上线检查清单

上线前至少检查这些问题：

- ES `_id` 是否使用 MySQL 主键。
- 同步失败是否有重试和死信。
- 消息重复消费是否安全。
- 同一业务 ID 的消息是否可能乱序。
- 删除事件是否正确处理。
- 是否有定时对账和修复。
- 是否记录同步延迟、失败数、重试数。
- mapping 变更是否需要重建索引。
- 是否通过 alias 支持灰度和回滚。
- 全量同步期间是否控制 refresh 和 bulk 大小。

## 九、总结

MySQL 同步 ES 的核心不是“把数据搬过去”，而是设计一条可恢复的数据复制链路。

可以记住下面几条原则：

- MySQL 是事实源，ES 是检索视图。
- 全量同步用于初始化和重建，增量同步用于运行期变更。
- ES 文档 ID 必须稳定，优先使用 MySQL 主键。
- 同步链路按至少一次设计，写入必须幂等。
- 乱序覆盖要靠回查 MySQL、分区有序或版本控制解决。
- 任何方案都必须有对账和补偿。
- 生产环境用 alias 管理索引版本，方便重建和回滚。

做到这些，ES 同步才算从“能跑”走向“出了问题也能救”。后者显然更重要，虽然它也更麻烦。很遗憾，工程里重要的东西通常都不会太轻松。
