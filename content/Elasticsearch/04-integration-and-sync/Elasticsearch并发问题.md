+++
date = '2026-03-22T15:37:57+08:00'
draft = false
title = 'Elasticsearch 并发问题'
+++

Elasticsearch 的并发问题主要分两类：

1. **多个客户端同时修改 ES 中的同一个文档**。
2. **外部数据同步消息乱序，导致旧数据覆盖新数据**。

这两类问题经常被混在一起讲，但它们的处理方式并不完全相同。前者更多依赖 ES 自身的乐观并发控制；后者通常还要结合 MySQL 版本号、消息队列分区、回查事实源和对账补偿。

## 一、ES 为什么使用乐观并发控制

ES 的底层存储来自 Lucene，而 Lucene 的 Segment 是不可变的。一次更新并不是在原位置修改文档，而是近似于：

```text
旧文档标记删除
  ↓
写入新文档
  ↓
等待 refresh 后对搜索可见
  ↓
后续 merge 清理旧数据
```

在高并发场景下，两个客户端可能同时读到同一份旧数据，然后分别提交修改。

例如：

```text
文档 count = 1

客户端 A 读取 count = 1
客户端 B 读取 count = 1

A 修改为 count = 2
B 修改为 count = 3
```

如果没有并发控制，后提交的请求会覆盖先提交的请求。至于谁赢，并不一定是业务上更正确的那个。工程系统并不会因为某个请求更有道理就自动偏袒它。

## 二、`_seq_no` 与 `_primary_term`

ES 7.x 以后，推荐使用 `_seq_no` 和 `_primary_term` 做乐观并发控制。

查询一条文档时，可以看到类似字段：

```json
{
  "_index": "product_index",
  "_id": "10001",
  "_seq_no": 10,
  "_primary_term": 3,
  "_source": {
    "name": "iPhone 15 Pro",
    "stock": 100
  }
}
```

两个字段的含义：

- `_seq_no`：主分片上每一次写操作都会分配一个递增序列号，用来标识操作顺序。
- `_primary_term`：主分片任期。主分片发生切换时会增加，用来避免旧主分片上的写入覆盖新主分片。

可以把它们合起来理解为：

```text
只有当“我读到的版本”仍然是当前版本时，才允许写入。
```

## 三、如何使用乐观锁更新

### 1. 先读取版本信息

```http
GET /product_index/_doc/10001
```

返回：

```json
{
  "_seq_no": 10,
  "_primary_term": 3,
  "_source": {
    "stock": 100
  }
}
```

### 2. 更新时携带条件

```http
POST /product_index/_update/10001?if_seq_no=10&if_primary_term=3
{
  "doc": {
    "stock": 99
  }
}
```

如果文档在这期间没有被别人修改，更新成功。

如果已经被修改，ES 会返回版本冲突：

```json
{
  "error": {
    "type": "version_conflict_engine_exception"
  },
  "status": 409
}
```

此时业务应该重新读取最新文档，再决定是否重试。

## 四、`retry_on_conflict` 适合什么场景

ES 的 update API 支持 `retry_on_conflict`：

```http
POST /product_index/_update/10001?retry_on_conflict=3
{
  "script": {
    "source": "ctx._source.stock -= params.count",
    "params": {
      "count": 1
    }
  }
}
```

它的含义是：如果内部更新时遇到版本冲突，ES 自动重新读取并重试。

适合：

- 计数器递增。
- 轻量字段累加。
- 冲突后可以安全重放的脚本更新。

不适合：

- 依赖用户之前看到的旧状态。
- 强业务校验。
- 复杂状态机流转。

例如订单状态从 `PAID` 改成 `SHIPPED`，就不应该简单依赖自动重试。因为状态变更需要业务层明确判断，而不是让 ES 帮你“试试看”。

## 五、`index` 覆盖写与 `update` 局部更新

无论是：

```http
PUT /product_index/_doc/10001
{
  "name": "iPhone 15 Pro",
  "stock": 99
}
```

还是：

```http
POST /product_index/_update/10001
{
  "doc": {
    "stock": 99
  }
}
```

只要文档发生变化，ES 都会产生新的版本信息。

区别在于：

- `index` 是整体覆盖文档。
- `update` 是读取旧文档、合并局部字段、再写入新文档。

如果 ES 文档是由 MySQL 宽表组装出来的，数据同步中通常更推荐整体覆盖写。因为同步服务可以回查 MySQL 最新状态，然后用稳定 `_id` 覆盖 ES 文档，逻辑更简单。

## 六、外部消息乱序

如果 MySQL 是事实源，ES 只是检索视图，那么更常见的问题不是多个客户端同时改 ES，而是同步消息乱序。

例如：

```text
T1：商品价格 699900
T2：商品价格 649900
```

正常顺序应该是 T1 后 T2。可是经过 MQ、重试、多线程消费后，可能变成：

```text
T2 先写入 ES
T1 后写入 ES
```

最终 ES 价格被旧消息覆盖成 699900。

这里使用 ES 的 `_seq_no` 并不一定合适。因为 `_seq_no` 管的是 ES 内部写入顺序，而业务真正关心的是 MySQL 变更顺序。

## 七、解决外部乱序的几种方式

### 1. 消息只传 ID，消费者回查 MySQL

这是最常用、也最稳的方案之一。

```text
MQ 消息：productId = 10001
  ↓
消费者查询 MySQL 当前最新商品
  ↓
覆盖写 ES
```

即使旧消息后到，它回查到的也是 MySQL 当前最新状态，因此不容易把 ES 写旧。

缺点是会增加 MySQL 查询压力，需要缓存、批量查询或读库来配合。

### 2. 同一业务 ID 固定到同一分区

发送 MQ 时使用业务 ID 作为 sharding key：

```java
String shardingKey = String.valueOf(productId);
mqProducer.send("product-sync", shardingKey, productId);
```

这样同一个商品的消息进入同一个队列或分区，由单个消费者顺序处理。

它能减少乱序，但不能解决所有问题。例如重试、死信回放、人工补偿时仍然可能打破顺序。

### 3. 使用 MySQL 版本号

在业务表中维护单调递增版本：

```text
product.version = 128
```

ES 文档中也保存该版本：

```json
{
  "id": 10001,
  "name": "iPhone 15 Pro",
  "price": 649900,
  "version": 128
}
```

写入时，如果事件版本小于 ES 当前版本，就拒绝覆盖。

可以使用脚本更新表达这个逻辑：

```http
POST /product_index/_update/10001
{
  "scripted_upsert": true,
  "script": {
    "source": """
      if (ctx._source.version == null || params.version >= ctx._source.version) {
        ctx._source.putAll(params.doc);
      } else {
        ctx.op = 'none';
      }
    """,
    "params": {
      "version": 128,
      "doc": {
        "name": "iPhone 15 Pro",
        "price": 649900,
        "version": 128
      }
    }
  },
  "upsert": {
    "name": "iPhone 15 Pro",
    "price": 649900,
    "version": 128
  }
}
```

这个方案的关键在于：版本必须来自事实源，而不是来自消费者本地时间。

### 4. 使用外部版本控制

ES 支持外部版本号语义。写入时由外部系统提供版本，旧版本不能覆盖新版本。

```http
PUT /product_index/_doc/10001?version=128&version_type=external
{
  "id": 10001,
  "name": "iPhone 15 Pro",
  "price": 649900
}
```

如果之后来了版本 127 的写入，会被拒绝。

这种方式适合你已经有严格递增的业务版本号、binlog 版本号或时间戳版本。需要注意的是，版本语义必须设计清楚，否则它只会让问题看起来更高级。

## 八、并发控制策略怎么选

| 场景 | 推荐方案 |
| ---- | -------- |
| 用户编辑同一份 ES 文档 | `_seq_no` + `_primary_term` |
| 简单计数累加 | `retry_on_conflict` + 脚本 |
| MySQL 同步 ES | 业务主键作为 `_id`，覆盖写 |
| MQ 消息可能乱序 | 回查 MySQL 或业务版本号 |
| 同一 ID 高频更新 | MQ 分区有序 + 版本控制 |
| 强一致业务状态机 | 回到 MySQL 事务中处理，ES 只同步结果 |

## 九、总结

ES 并发问题可以这样记：

- `_seq_no` 和 `_primary_term` 解决的是 ES 内部文档并发写。
- `retry_on_conflict` 只适合可安全重试的更新。
- MySQL 同步 ES 时，业务版本顺序比 ES 内部版本更重要。
- 外部乱序消息优先通过回查事实源、分区有序、业务版本号解决。
- ES 是检索视图，不应该承担强事务状态判断。

把“ES 内部并发”和“外部同步乱序”分开看，很多问题就会清楚得多。混在一起当然也能讲，只是那样比较适合制造面试恐慌，不太适合写可靠系统。
