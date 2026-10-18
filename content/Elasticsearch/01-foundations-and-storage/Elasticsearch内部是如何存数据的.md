+++
date = '2026-03-17T21:34:59+08:00'
draft = false
title = 'Elasticsearch 内部是如何存数据的'
+++

Elasticsearch 并不是自己从零实现了一套存储引擎。它的底层检索和存储核心来自 Apache Lucene。

可以简单分工：

```text
Elasticsearch：分布式、集群、路由、副本、REST API
Lucene：倒排索引、Segment、DocValues、向量索引、文件落盘
```

理解 ES 内部存储，关键不是背文件格式，而是抓住几个核心概念：

- 一个 Shard 本质上是一个 Lucene Index。
- Lucene 使用不可变 Segment 存储数据。
- 更新不是原地修改，而是删除旧文档再写新文档。
- refresh 决定数据什么时候可搜索。
- translog 决定写入失败后如何恢复。
- merge 决定旧 Segment 和删除数据什么时候被清理。

## 一、逻辑结构

从业务视角看，ES 的层级大致如下：

```text
Index（索引）
  └── Shard（分片）
       └── Lucene Index
            ├── Segment
            │    ├── 倒排索引
            │    ├── DocValues
            │    ├── _source
            │    └── 向量索引
            └── Segment
```

### 1. Index

Index 是 ES 中的逻辑索引，类似一个面向搜索的表。

例如：

```text
product_index
article_index
order_search_index
```

一个 Index 由多个 Shard 组成。

### 2. Shard

Shard 是 ES 分布式存储和查询的基本单位。

一个 Index 可以拆成多个主分片：

```text
product_index
  ├── primary shard 0
  ├── primary shard 1
  └── primary shard 2
```

每个 Shard 本质上就是一个独立的 Lucene Index。

这意味着：当你创建 3 个主分片时，底层并不是一个 Lucene 索引被简单切成三份，而是创建了 3 个独立的 Lucene Index，然后由 ES 负责路由和汇总。

## 二、Segment 是真正的物理存储单元

Lucene 的核心设计是不可变 Segment。

Segment 可以理解为一批已经写好的只读索引文件。

```text
Shard
  ├── Segment A
  ├── Segment B
  ├── Segment C
  └── Segment D
```

一旦 Segment 生成，它就不会被原地修改。

这带来几个结果：

- 写入新文档会生成新的 Segment。
- 更新文档会写入新版本，旧版本标记删除。
- 删除文档只是打删除标记。
- 真正释放磁盘空间依赖后续 merge。

这种设计的好处是读性能好、并发控制简单；代价是更新和删除不会立刻回收空间。世上当然没有免费的午餐，系统设计尤其没有。

## 三、Segment 中存了什么

一个 Segment 里会包含多类数据结构。

### 1. 倒排索引

倒排索引用于全文检索。

结构可以简化为：

```text
term -> docID 列表
```

例如：

```text
apple -> [1, 3, 9]
phone -> [1, 2, 8]
```

当执行：

```json
{
  "query": {
    "match": {
      "title": "apple phone"
    }
  }
}
```

ES 会先分析查询文本，再到倒排索引中找到相关 term 对应的文档集合，并计算相关性分数。

### 2. DocValues

DocValues 是面向列的存储结构，主要用于：

- 排序。
- 聚合。
- 脚本计算。
- 部分过滤场景。

例如商品价格字段：

```text
docID -> price
1 -> 699900
2 -> 399900
3 -> 1299900
```

如果要按价格排序或做价格区间聚合，列式结构比从 `_source` 中逐条解析 JSON 高效得多。

因此：

- `text` 字段主要服务全文检索。
- `keyword`、数值、日期等字段通常依赖 DocValues 做排序和聚合。

### 3. `_source`

`_source` 保存的是写入时的原始 JSON 文档，通常以压缩形式存储。

例如写入：

```json
{
  "title": "iPhone 15 Pro",
  "price": 699900
}
```

搜索返回结果时，ES 会从 `_source` 中取出原始字段。

注意：

- `_source` 不是倒排索引。
- 查询匹配不直接依赖 `_source`。
- 返回字段、高亮、重建索引等功能经常依赖 `_source`。

不要轻易关闭 `_source`。关闭后看似节省空间，但很多能力会变得麻烦。

### 4. 向量索引

如果字段是 `dense_vector` 且启用了索引，ES 会为向量构建近似最近邻索引，常见底层结构是 HNSW。

可以理解为：

```text
文本字段 -> 倒排索引
排序聚合字段 -> DocValues
原始文档 -> _source
向量字段 -> HNSW 向量索引
```

向量搜索不走倒排索引。它是另一套并列的检索结构。

## 四、写入流程

一次写入大致经过这些步骤：

```text
客户端写请求
  ↓
协调节点根据 routing 找到主分片
  ↓
主分片写入 indexing buffer
  ↓
追加 translog
  ↓
复制到副本分片
  ↓
返回写入成功
  ↓
refresh 后生成可搜索 Segment
  ↓
flush 后形成持久化提交点
```

这里有三个容易混淆的动作：refresh、flush、translog。

## 五、refresh：让数据可搜索

refresh 的作用是把内存中的数据生成新的 Segment，并打开新的 Searcher，让这些数据可以被搜索到。

默认情况下，ES 是近实时搜索。写入成功后，并不代表立刻能搜到。

```text
写入成功
  ↓
等待 refresh
  ↓
搜索可见
```

`refresh_interval` 默认常见为 1 秒，所以通常说 ES 是 near real-time。

refresh 的成本：

- 创建新 Segment。
- 打开新 Searcher。
- 增加 Segment 数量。
- 后续触发更多 merge。

大批量导入时，频繁 refresh 会降低吞吐。因此全量同步时经常临时关闭或调大 refresh。

## 六、translog：保证写入可恢复

写入 ES 时，数据不仅会进入内存 buffer，还会追加到 translog。

translog 的作用是：如果节点崩溃，还可以通过日志恢复尚未 flush 的写入。

简化流程：

```text
写入 indexing buffer
  ↓
写入 translog
  ↓
返回成功
```

需要区分：

- refresh 负责搜索可见性。
- translog 负责崩溃恢复。

也就是说，数据没 refresh 不代表丢了；只要 translog 可靠，节点恢复时还能重放。

## 七、flush：建立持久化提交点

flush 会触发 Lucene commit，并清理不再需要的旧 translog。

可以理解为：

```text
当前 Segment 状态已经安全提交
  ↓
旧 translog 可以释放
```

flush 不是每次写入都执行。它主要用于控制恢复成本和 translog 大小。

refresh、translog、flush 的关系可以这样记：

| 机制 | 主要作用 |
| ---- | -------- |
| refresh | 让新写入的数据可搜索 |
| translog | 保证崩溃后可以恢复写入 |
| flush | 建立持久化提交点，清理旧 translog |

## 八、更新和删除为什么不立刻生效到磁盘

Lucene Segment 不可变，所以 ES 更新文档时不会原地修改。

更新相当于：

```text
旧文档标记删除
  ↓
写入新文档
```

删除相当于：

```text
文档打删除标记
  ↓
查询时跳过它
  ↓
merge 时真正清理
```

因此你会看到几个现象：

- 删除大量文档后磁盘不一定立刻下降。
- 频繁更新会增加 Segment 和 merge 压力。
- 写多读少与读多写少的调优策略不同。

这不是 ES “删除失败”，而是 Lucene 的存储模型决定的。

## 九、merge：清理旧 Segment

随着不断 refresh，Shard 中会出现越来越多 Segment。

```text
Segment A + Segment B + Segment C
  ↓ merge
Segment D
```

merge 会做几件事：

- 合并多个小 Segment。
- 清理被删除的文档。
- 减少查询需要访问的 Segment 数量。
- 回收一部分磁盘空间。

merge 的代价也很明显：

- 消耗 CPU。
- 消耗磁盘 IO。
- 可能影响写入吞吐。
- 大 Segment 合并成本高。

所以 ES 需要在后台持续做 merge 策略调度。

## 十、搜索流程

一次搜索大致如下：

```text
客户端请求
  ↓
协调节点接收请求
  ↓
发送到相关 Shard
  ↓
每个 Shard 查询自己的 Segment
  ↓
Shard 返回 topN
  ↓
协调节点全局归并排序
  ↓
返回结果
```

在 Shard 内部，不同字段会走不同结构：

| 查询能力 | 底层结构 |
| -------- | -------- |
| `match` / `term` | 倒排索引 |
| 排序 / 聚合 | DocValues |
| 返回原文 | `_source` |
| KNN 向量检索 | HNSW 向量索引 |

## 十一、总结

ES 内部存储可以用一句话概括：

> Elasticsearch 负责分布式组织数据，Lucene 负责在每个 Shard 内通过不可变 Segment 存储倒排索引、DocValues、`_source` 和向量索引。

进一步说：

- Index 是逻辑索引。
- Shard 是分布式执行和存储单位。
- 每个 Shard 是一个 Lucene Index。
- Segment 是不可变的物理文件集合。
- refresh 决定搜索可见性。
- translog 决定崩溃恢复能力。
- flush 建立持久化提交点。
- merge 清理旧 Segment 和删除数据。

理解这些之后，ES 的许多现象就不再奇怪：为什么写入后不是立刻可搜索，为什么删除后磁盘不马上下降，为什么大批量写入要控制 refresh，为什么频繁更新会带来 merge 压力。它们不是孤立知识点，而是同一个底层模型自然长出来的结果。
