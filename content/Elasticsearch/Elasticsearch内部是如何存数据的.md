+++
date = '2026-03-17T21:34:59+08:00'
draft = false
title = 'Elasticsearch内部是如何存数据的'
+++

> **Elasticsearch 并不是自己实现了一套存储引擎，它的底层存储核心是 Apache Lucene。ES 负责分布式、路由、集群管理；Lucene 负责真正的数据落盘与索引结构。**

## ES 从逻辑结构上如何组织数据？

从上到下是这样的层级：

```text
Index（索引）
 └── Shard（分片）
      └── Lucene Index
           ├── Segment（段）
           │    ├── 倒排索引文件
           │    ├── 正排 / DocValues
           │    ├── 向量索引（HNSW）
           │    └── 存储字段（_source）
           └── Segment（段）
```

## Index 和 Shard 层

### Index（索引）

- 逻辑概念，类似数据库的**表**
- 我们自己创建的 `content_index`、`product_index` 都是 Index

### Shard（分片）

- 一个 Index 会被切成多个 **Shard**
- 每个 Shard**本质上就是一个独立的 Lucene Index**
- Shard 是**ES 水平扩展和并行搜索的最小单位**

> ES 层面只负责： **请求发到哪个 shard**

## Lucene 层才是真正的存储引擎

> **Lucene 是一个基于文件系统的、不可变段（Segment）搜索引擎**

### Segment 是什么？

- Segment 是 Lucene 的最小物理存储单元
- 一个 Segment 是一组**只读文件**
- 写入数据时：
  - **不会修改已有 Segment**
  - 只会生成新的 Segment

这点非常重要：
 **Lucene 几乎不做原地更新**

### Segment 里存了什么？

一个 Segment 内部，包含多种不同用途的文件结构：

#### 倒排索引（Inverted Index）

用于全文检索（text 字段）

```text
term -> [docID1, docID2, docID3]
```

- 每个 term 对应一组 docID
- 查询时非常快
- 支持 BM25 等评分算法

#### 正排数据 / DocValues

用于：

- 排序
- 聚合
- 脚本计算
- filter

特点：

- **列式存储**
- 非全文检索用途
- 不走倒排

#### _source（原始 JSON）

- `_source` 是**写入的完整 JSON**
- 以**压缩后的二进制**形式存储
- 默认是**存在磁盘上的，不进内存**

> ES 返回搜索结果时，就是从 `_source` 里反序列化出来的

### 向量字段（dense_vector）的存储

#### 向量数据分两部分存：

##### 向量原始值

- 以二进制形式存储
- 用于：
  - script_score
  - 精排
  - 重建索引

##### 向量索引（ANN / HNSW）

- 单独的图结构文件
- 专门用于 **近似最近邻搜索**
- 与倒排索引是**完全不同的体系**

向量搜索**不走倒排索引**

## 写入数据时，ES 到底做了什么？

当执行：

```http
POST index/_doc
{
  "title": "苹果手机",
  "embedding": [ ... ]
}
```

### 实际发生的步骤：

1. 文档写入**内存 Buffer**
2. 同步写入 **translog（事务日志）**
3. 到达阈值：
   - Buffer 刷盘
   - 生成新的 Segment
4. Segment 被打开，可被搜索
5. 后台定期做 **Segment Merge（段合并）**

## 为什么 ES 更新 / 删除看起来很慢？

因为

> **Lucene 的 Segment 是不可变的**

所以

- update = delete + insert
- delete 只是打标记（软删除）
- 真正释放空间靠 **merge**

这也是 ES 的几个典型特性来源：

- 删除后磁盘不立刻变小
- 索引越大，merge 越重要
- 写多读少 vs 读多写少性能差异明显

## 搜索时 ES 到底是怎么查的？

以一次查询为例：

1. ES 把请求路由到多个 Shard
2. 每个 Shard 内：
   - 多个 Segment **并行查询**
3. 每个 Segment：
   - text -> 倒排索引
   - vector -> HNSW
4. Shard 汇总结果
5. Coordinator 节点做全局排序 & 返回

## 向量搜索在底层插在哪里？

看下表：

| 功能         | 底层结构          |
| ------------ | ----------------- |
| match / term | 倒排索引          |
| sort / agg   | DocValues         |
| `_source`    | 压缩 JSON         |
| **knn**      | **HNSW 向量索引** |

**向量索引与倒排索引并列存在，不互相干扰**

> Elasticsearch 是底层基于 Lucene 存储数据。ES 在逻辑上以 Index 和 Shard 组织数据，而每个 Shard 实际上是一个 Lucene Index。Lucene 通过不可变的 Segment 文件将倒排索引、列式存储（DocValues）、原始文档（_source）以及向量索引（HNSW）分别落盘，从而在保证搜索性能的同时实现高效的写入和并发查询。
