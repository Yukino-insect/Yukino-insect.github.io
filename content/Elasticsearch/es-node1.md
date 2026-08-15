+++
date = '2025-12-24T21:07:37+08:00'
draft = false
title = 'es-node1'
+++

## 集群部署

## setting

在学习 ES 集群方面的知识前。我们首先来学习一下 `setting` 配置

```json
{
  "settings": {
    /* 1. 分片与副本 */
    "number_of_shards": 3,
    "number_of_replicas": 1,

    /* 2. 写入 & 可见性控制 */
    "refresh_interval": "1s",

    /* 3. 查询保护参数 */
    "max_result_window": 10000,

    /* 4. translog */
    "translog": {
      "durability": "request",
      "sync_interval": "5s"
    },

    /* 5. merge / segment 行为 */
    "merge": {
      "policy": {
        "segments_per_tier": 10,
        "max_merged_segment": "5gb"
      }
    },

    /* 6. 分词器分析配置 */
    "analysis": {
      "analyzer": {
        /* 默认分析器 */
        "default": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": [
            "lowercase"
          ]
        },

        /* 查询期同义词分析器（推荐） */
        "search_synonym": {
          "type": "custom",
          "tokenizer": "whitespace",
          "filter": [
            "lowercase",
            "synonym_filter"
          ]
        }
      },

      "filter": {
        /* 同义词过滤器 */
        "synonym_filter": {
          "type": "synonym",
          "lenient": true,
          "synonyms": [
            "oa, dingding",
            "crm, customer"
          ]
        }
      }
    }
  }
}
```

### 分片与副本

```json
"number_of_shards": 3,
"number_of_replicas": 1
```

该配置是**用于配置 ES 分片数量和 ES 从节点数量**的。ES 分片就是将一个 Index 的数据分成不同的 Shard，每一个 Shard 独立存在。

#### `number_of_shards` 分片

```text
一个 index
 ├── shard 0（Lucene Index）
 ├── shard 1（Lucene Index）
 └── shard 2（Lucene Index）
```

当客户端向一个 index 写入数据时，ES 会通过路由策略选择一个分片

```text
routing（默认是 _id）
   ↓
hash(routing) % number_of_shards
   ↓
确定主 Shard
```

当查询分片时协调者节点会执行以下流程

```text
Client
 ↓
Coordinator Node
 ↓
并发向所有相关 Shard 发送请求
 ↓
各 Shard 本地执行查询
 ↓
Coordinator 汇总、排序、返回
```

ES 是通过 hash 选择分片的，如果该参数在线上被修改，那之前的 hash 规则将被废除。这是将是灾难性的事故。因此，该参数只能在构建索引是决定，不能在运行时修改。

在决定分片时，如果 Shard 太少，那么单 Shard 数据量过大，查询或 merge 压力集中，容易达到单点性能的瓶颈；如果 Shard 太多，每个 Shard 都有 Segment、file handle、内存结构，查询要 fan-out 到大量 Shard。集群管理成本将急剧上升。

#### `number_of_replicas` 副本

副本是每一个主分片的数据冗余，用于保证主分片所在服务挂掉之后，从分片可以继续提供服务。

```text
shard 0 -> 1 个 replica
shard 1 -> 1 个 replica
shard 2 -> 1 个 replica
```

当写请求到达主分片时，主分片在写入成功后才会将数据异步同步到 replica。当主分片挂掉后，从分片自动提升为主分片。读请求可被负载均衡到主从分片，减小 ES 读请求压力。副本参数可以在运行时被修改。

`number_of_shards` 决定了 ES 索引的数据切分方式和并行处理能力，是容量与写入扩展性的基础；`number_of_replicas` 决定了数据的冗余副本数量，用于提供高可用和提升查询吞吐。这两个参数共同影响索引的性能、稳定性和资源消耗，是 ES 索引设计中的核心参数。

### 写入 & 可见性控制

```json
"refresh_interval": "1s"
```

该参数**用于控制写入数据后多久可以被搜索引擎看到。**

该参数控制的是写数据多久对搜索可见。从这可以知道，当数据写入 ES 中时是不能被立刻查到的。因此，ES 被称为近实时的数据库。

ES 的底层是 Lucene，它的核心特性是写入快，但是搜索只能看到已 refresh 的 Segment。整个的写入流程大致如下：

```text
写请求
 ↓
内存 buffer（Indexing Buffer）
 ↓
refresh
 ↓
生成新的 Segment（可被搜索）
```

从上图可以清晰的看到，即使数据写入成功，如果没有 refresh 的话，是不会生成 Segment 将数据落盘的，这将直接导致不可搜索。

refresh 的主要作用就是把内存中的数据刷新成一个 Lucene segment，并打开一个新的 Searcher。Searcher 是 ES 在 Shard 层基于 Lucene 提供的只读查询视图，其封装了一组不可变 Segment，用于在高并发场景下提供一致、无锁、近实时的搜索能力。每当产生新的 Segment、合并出新的 Segment 都会生成一个 Searcher 供用户查询。

`refresh_interval: 1s` 表示 ES 每 1 秒才会将内存中的数据落盘，数据 1 秒后才可以被搜索到，这就是 ES 所谓的近实时搜索。

需要注意的是，refresh 操作是有成本的，每一次 refresh 都会，创建新 Segment、打开新 Searcher、增加 Segment 数量、触发后续 merge。refresh 越频繁影响越大，包括：Segment 数量变多、merge 压力增大、写入吞吐下降、IO 抖动增加。因为 refresh 涉及到了磁盘 IO。**但是 refresh 并不保证数据安全，数据写入安全是由 `translog` 保证的。**

### 查询保护参数

```json
"max_result_window": 10000
```

该参数**用于控制一次可以读多少数据**，是为了限制一次分页查询中 `from + size` 的最大值。它主要为了缓解分页深度问题。

MySQL 深度分页问题产生的原因：MySQL 要先读取前 10000 条数据，再丢弃前 9999 条数据，再拿到指定页数和数量的数据。而 ES 比这个开销更大，它的一次分页查询要涉及

```text
每个 Shard：取 from + size 条数据
  ↓
Coordinator 汇总所有 Shard 的结果
  ↓
全局排序
  ↓
丢弃前 from 条
  ↓
返回 size 条
```

它要查询每一个分片的数据，每一个分片数据分页以后汇总，再总体分页。这将对 CPU 造成极大的压力。10000 是 ES 团队给出的一个安全阈值，防止将 JVM 撑爆。

除此之外，ES 团队提供了 `search_after`，用于解决深度分页问题。它是基于上一次查询的位置继续查询

```json
{
  "size": 10,
  "sort": [
    { "create_time": "desc" },
    { "_id": "desc" }
  ],
  "search_after": ["2024-01-01T10:00:00", "abc123"]
}
```

或者使用 `Scroll` 批量导出

```http
POST index/_search?scroll=1m
```

`scroll` 查询用于在某一时间点对查询结果创建一个快照，并以游标方式批量遍历该结果集，常用于全量数据导出、离线处理和数据同步。`scroll` 并不适合实时分页查询，其设计目标是稳定遍历而非用户交互。

`scroll=1m` 含义是如果在 1 分钟内没有继续拉取下一页，这个 scroll context 就会被自动清理

使用 `scroll` 的步骤：

第一次查询

```http
POST index/_search?scroll=1m
{
  "size": 1000,
  "_source": ["id", "name", "age"],   // 建议只取需要的字段
  "query": {
    "match_all": {}
  },
  "sort": ["_doc"]                    // 非常重要：提高效率
}
```

返回值

```json
{
  "_scroll_id": "DXF1ZXJ5QW5kRmV0Y2gBAAAAA...",
  "hits": {
    "hits": [
      { "_id": "1", "_source": {...} }
    ]
  }
}
```

这一步会建立查询快照，返回第一批数据和一个 `_scroll_id`，这个 id 类似该快照的索引。`size` 参数代表本次查询需要返回的数量。

`scroll` 查询可以分批遍历一次查询命中的全部结果集，其总返回数量等于初始查询的命中总数。`scroll` 的性能开销主要来自搜索上下文的长期占用，持有 Segment 和 Searcher 的引用导致阻塞 Segment merge 等问题。

> `scroll` 会通过固定旧的 Searcher 视图，长期持有历史 Segment 的引用，从而阻止 merge 后旧 Segment 的回收，导致 Segment 数膨胀、IO 压力增大和查询性能下降，因此在现代 ES 中已不再推荐用于深度分页。

合理控制批大小、并发数量和及时清理 `scroll` 上下文，可以避免对集群造成显著性能压力。

接着带着该 `_scroll_id` 循环拉取下一批数据

```http
POST /_search/scroll
{
  "scroll": "1m",
  "scroll_id": "DXF1ZXJ5QW5kRmV0Y2gBAAAAA..."
}
```

用完后立即清除 scroll 

```http
DELETE /_search/scroll
{
  "scroll_id": "DXF1ZXJ5QW5kRmV0Y2gBAAAAA..."
}
```

`max_result_window` 用于限制基于 `from/size` 的分页查询中 `from` 与 `size` 之和的最大值，防止深度分页在分布式查询和全局排序过程中消耗过多内存和 CPU。它并不限制一次查询返回的总数据量，而是限制分页深度，深度分页应使用 `search_after` 或 `scroll` 等方式替代。

### translog

```json
"translog": {
  "durability": "request",
  "sync_interval": "5s"
}
```

**这个参数是 ES 写入可靠性与性能权衡的关键参数。**

`translog` 是 ES 的写入日志，`durability` 决定写入确定前是否强制落盘，`sync_interval` 决定多久把日志刷新到磁盘一次。

`translog` 可以保证数据的安全性，即使进程异常数据也可以恢复，`refresh` 则会在内存中生成 `segment` 保证数据可搜索。而 `flush` 是一个持久化检查点操作，它通过 Lucene commit 将当前磁盘上的 Segment 标记为一个安全状态，并清空旧的 translog，从而减少崩溃恢复时需要回放的日志量。

```text
客户端写请求
   ↓
写入 indexing buffer（内存）
   ↓
追加写入 translog
   ↓
返回成功（客户端看到成功）
   ↓
refresh -> 可搜索
   ↓
flush -> 持久化检查点操作
```

ES 在一次 Index 请求中，会在同一线程内串行完成 Lucene Index buffer 写入和 translog 追加；写入是否被确认成功并不取决于 Index buffer，而是取决于 translog 是否满足 durability 要求（如 request 模式下完成 fsync）。

如果数据写入了 Index buffer，没有执行 translog 追加，进程崩溃了。客户端将会返回失败响应，ES 是不会认为该条数据写入成功。

在 ES 中，`durability` 用于控制 translog 的持久化策略。当 `durability = request` 时，每一个写请求在返回成功之前，必须将对应的 translog 通过 `fsync` 同步到磁盘，这是最安全但性能开销较高的模式；当 `durability = async` 时，写请求在 translog 写入操作系统缓存后即可返回成功，不等待实际刷盘；后台线程会按照 `sync_interval`（如 5 秒）周期性地执行 translog 的 `fsync`，因此在异常宕机时，最多可能丢失一个 `sync_interval` 时间窗口内的数据。

在 ES 中，是否执行 `fsync` 决定了数据是否真正持久化；在 `durability = request` 模式下，没有完成 `fsync` 就不会认为写入成功，而在 `durability = async` 模式下，即使尚未执行 `fsync`，ES 也可能已经返回成功。

因此，`durability = async` 模式下，如果 translog 数据写入了缓存，但是没有落盘，ES 也会返回写入成功。这时如果进程崩溃，下次恢复时这部分数据就丢失了。

> `fsync` 是一个系统调用，用于强制将文件的脏数据和元数据从操作系统缓存同步到物理存储设备

### merge / Segment 行为

**用于控制 segment 的合并策略**

```json
"merge": {
  "policy": {
    "segments_per_tier": 10,
    "max_merged_segment": "5gb"
  }
}
```

Segment 是什么呢？

它本质上是一组不可变的索引文件。Segment 是不可变的，一旦生成便不能修改，不能更新。更新删除只是打标记，旧数据仍然存在。每次 refresh 都会产生新 Segment。refresh 越频繁 Segment 越多。如果不主动合并的话。一次查询就需要对每一个 Segment 执行一次操作。最后再将结果合并。这样 CPU 开销将变大，Cache 命中率越低。

前面讲到，删除只是标记，旧数据仍在 Segment 中，只有执行了 merge 才会真正清理理应该删除的数据。merge 是把多个小 Segment 合并成一个更大的 Segment，并在过程中清理已删除的数据。

```text
Segment A + Segment B + Segment C
 ↓
生成一个新的 Segment D
 ↓
删除旧 Segment
```

`segments_per_tier` 参数的含义是每一层（tier）允许存在的 Segment 数量上限。Segment 在 ES 中是会按大小分层存储的：

```text
小 segment   ← tier 0
中 segment   ← tier 1
大 segment   ← tier 2
```

相同数量级的在一层，当某一层达到数量上限就会触发 merge。这样 Segment 数量级小的合并更积极，查询起来更快，IO 压力等大；数量级大的合并更保守，写入更稳，查询略慢。

当某一层的 Segment 数超过这个值，就会触发 merge，所以这个参数值的大小就决定了合并的频繁程度以及程序中 Segment 的多少。

`max_merged_segment` 代表合并后的 Segment，最大不能超过的数量级。Lucene 在 merge 时，不会生成超过这个限制的 Segment。这个值不能过大。超大的 Segment 会导致 `merge` 代价巨大。

在 ES 中，Segment 是 Lucene 索引的不可变最小单元，每次 refresh 都会生成新的 Segment。随着写入和删除的发生，Segment 数量会不断增加，导致查询成本上升和磁盘空间浪费。merge 操作通过将多个小 Segment 合并为更大的 Segment，清理已删除的数据，从而提升查询性能并回收空间。`segments_per_tier` 控制每个层级允许的 Segment 数量，`max_merged_segment` 用于限制单个合并后 Segment 的最大大小，两者共同在查询性能、IO 成本和稳定性之间取得平衡。

### 分词器分析配置

**用于配置分词器**

```json
"analysis": {
  "tokenizer": {
    "comma_tokenizer": {
      "type": "pattern",
      "pattern": ","
    }
  },
  "filter": {
    "my_lowercase": {
      "type": "lowercase"
    }
  },
  "analyzer": {
    "my_analyzer": {
      "type": "custom",
      "tokenizer": "comma_tokenizer",
      "filter": ["my_lowercase"]
    }
  }
}
```

```textt
analysis
 ├── analyzer        ← 定义“完整分析流程”
 │     └──（引用）
 │          ├── char_filter
 │          ├── tokenizer
 │          └── token_filter（filter）
 │
 ├── tokenizer       ← 定义“如何切词”
 │
 ├── filter          ← 定义“如何加工 token”
 │
 └── char_filter     ← 定义“分词前如何改文本”
```

ES 的分词器配置位于 Index settings 的 analysis 模块中，由 analyzer、tokenizer、token filter 和 char filter 组成。analyzer 通过组合这三类组件定义文本从原始字符串到最终 token 的完整处理流程。合理设计分词器是搜索效果与性能的基础，生产中需谨慎修改并优先在查询阶段使用复杂分析逻辑。

`analysis` 是 ES 分词体系的顶级容器，用于定义分词相关的组件，包括 analyzer、tokenizer、token filter 和 char filter。analyzer、tokenizer、token filter 和 char filter 之间是组合关系而非同级关系。

analyzer 本身不实现分词逻辑，而是通过引用在 analysis 下定义的 tokenizer、filter 和 char_filter，将它们按顺序组装成一条完整的文本分析流水线。

分词器的处理流程是 char_filter 文本预处理、tokenizer 切词、token filter 词加工

```text
char_filter -> tokenizer -> filter
```

`char_filter` 会对原始字符串做字符级别的替换或清洗，比如去除 HTML 标签，全角改为半角，符号统一，特殊字符替换。

`tokenizer` 是真正的分词器，它会将一整段文本切成一个一个的 token 词项。

ES 内置的分词器有：

- `standard`
- `whitespace`
- `simple`
- `letter`
- `pattern`

等

filter 会对词再加工，如小写化，去停用词、同义词拓展等操作都在这一阶段

ES 的分词流程由 char_filter、tokenizer 和 token filter 三个阶段组成。char_filter 用于在分词前对原始文本进行字符级预处理，tokenizer 负责将文本切分为 token，而 token filter 则对这些 token 进行进一步加工。三者按固定顺序执行，共同构成 analyzer 的完整分析流程。

## 集群部署

首先要清楚，Index 是一个逻辑概念，代表一个 Shard 集合。Shard 是物理执行单元，每一个 Shard 本质上是一个独立的 Lucene Index。一个 Index 会被切成 n 个 Shard。

```http
PUT my_index
{
  "settings": {
    "number_of_shards": 3
  }
}
```

这个配置就代表着当前索引会有 3 个分片，这 3 个 Shard 会被 master 节点分配到 data 节点上。

Document 是最小的业务数据单位，它的写入流程如下：

1. 计算路由值 routing，routing 默认是 `_id`，也可以自定义 routing，例如按 userId 路由
2. 通过哈希 `shard_id = hash(routing) % number_of_primary_shards` 确定文档应该落到哪一个 Primary Shard。因此主分片数一旦确定，后续调整一般需要执行 `reindex`
3. 写入Primary Shard 的 Lucene Segment

Segment 是一个不可变的倒排索引文件块

```text 
Shard
 ├── Segment_1
 ├── Segment_2
 ├── Segment_3
 └── Segment_n
```

当新文档写入成功并且 `refresh` 后，就会创建新 Segment。当我们执行查询操作时： 

1. 客户端请求打到任意节点，该节点会临时充当 coordinating node
2. coordinating node 根据路由表，将请求分发到 相关 Shard
3. 每个 Shard 本地执行查询，返回 topN 的候选结果
4. 协调节点从对应 Shard 拉取真实 `_source` 等字段
5. 归并、排序、返回结果

由此可见，Shard 的数量会影响查询的速度。如果 Shard 太多，调度开销、线程切换、Segment 数量暴涨、merge 压力增大；如果 Shard 太少，并行度不足、单 Shard 数据过大导致查询慢、恢复慢。

在上文我们也看到了一些 ES 的集群中的部分角色，现在汇总以下，主要有这么几个角色：

- master 节点，它负责集群层面的控制工作。包括选主、维护 cluster state、分片分配与迁移决策、索引生命周期管理、映射与设置变更的协调等。在生产环境中，推荐 master 节点不承载数据分片（即不作为 data 节点），以保证集群稳定性。

- data 节点，它用于承载索引分片，负责文档写入、查询、聚合、排序、Segment merge、缓存维护等所有与数据直接相关的操作。
- coordinating，它并不是一种独立的节点类型，而是一种行为角色，任何节点都可能接到客户端请求并充当协调节点，区别是它是否承载数据 shard、是否参与选主与决策。

一个 ES 进程就是一个节点。而角色决定这个进程负责干什么。分片最终只会落在有 data 角色的数据节点上。一般单例运行时，一个 ES 实例就充当了所有角色。

现在我们在本地部署一个最小集群，它的结构如下：

```text
Node 1：master + data
Node 2：master + data
Node 3：master + data
```

复制 3 份 ES 实例。他们的配置如下：

```yaml
# es-node1
cluster.name: local-node-cluster
node.name: node-1

node.roles: [ master, data ]

cluster.initial_master_nodes: ["node-1","node-2","node-3"]

path.data: D:\JavaLearning\deployment-testing\es\elasticsearch-node1\data
path.logs: D:\JavaLearning\deployment-testing\es\elasticsearch-node1\logs

network.host: 127.0.0.1
http.port: 9200
transport.port: 9300

discovery.seed_hosts:
  - 127.0.0.1:9300
  - 127.0.0.1:9301
  - 127.0.0.1:9302

xpack.security.enabled: false
```

```yaml
# es-node2
cluster.name: local-node-cluster
node.name: node-2

node.roles: [ master, data ]

cluster.initial_master_nodes: ["node-1","node-2","node-3"]

path.data: D:\JavaLearning\deployment-testing\es\elasticsearch-node2\data
path.logs: D:\JavaLearning\deployment-testing\es\elasticsearch-node2\logs

network.host: 127.0.0.1
http.port: 9201
transport.port: 9301

discovery.seed_hosts:
  - 127.0.0.1:9300
  - 127.0.0.1:9301
  - 127.0.0.1:9302

xpack.security.enabled: false
```

```yaml
# es-node3
cluster.name: local-node-cluster
node.name: node-3

node.roles: [ master, data ]

cluster.initial_master_nodes: ["node-1","node-2","node-3"]

path.data: D:\JavaLearning\deployment-testing\es\elasticsearch-node3\data
path.logs: D:\JavaLearning\deployment-testing\es\elasticsearch-node3\logs

network.host: 127.0.0.1
http.port: 9202
transport.port: 9302

discovery.seed_hosts:
  - 127.0.0.1:9300
  - 127.0.0.1:9301
  - 127.0.0.1:9302

xpack.security.enabled: false
```

`xpack.security.enabled: false` 我们关掉了 ES 8.x 默认开启的安全模块。如果当前 ES 实例之前启动过，请删除 `data` 文件夹和 `elasticsearch.keystore` 配置文件。`data` 文件夹下会有之前的 ES 数据，集群部署时，这些已存在的数据 ES 不知道如何分配，会报错。`elasticsearch.keystore` 是之前启动 ES 时生成的安全模块文件，仍然会影响当前集群启动。

 `cluster.initial_master_nodes: ["node-1","node-2","node-3"]` 配置是首次启动时的候选 master 节点，最后 master 节点会在这几个节点中选出。该配置只用于首次引导，成功后必须删除。`node.roles: [ master, data ]` 配置代表该节点的角色，`transport.port: 9302` 配置是节点间内部的通信端口，在执行选举或者其他程序时会用到。`discovery.seed_hosts` 是声明通信端口的配置。`network.host: 127.0.0.1` 它决定改节点绑定的网络地址，`127.0.0.1` 只允许本机访问，如果要让局域网其他机器访问，需要绑定机器内网 IP 或 `0.0.0.0`。

当程序成功运行后，在终端执行下面命令，验证集群是否成功：

```http
curl http://127.0.0.1:9200/_cat/nodes?v
```

如果出现以下内容，说明集群启动成功。`master:*` 代表 `node-2` 是 master 节点。

```bash
ip        heap.percent ram.percent cpu load_1m load_5m load_15m node.role master name
127.0.0.1           62          90  10                          dm        -      node-1
127.0.0.1           37          90   9                          dm        *      node-2
127.0.0.1           40          90   9                          dm        -      node-3
```

创建一个测试索引

```http
PUT /test_index
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1
  }
}
```

查看分片

```http
GET /_cat/shards?v
```

> `GET /_cat/shards?v` 用来以表格形式查看当前集群中所有分片的分布、状态和所在节点。`?v` 参数用来显示表头。

```http
GET /_cat/shards/test_index?v
```

只查询你想看的索引下的分片信息。

可以发现，我们并没有单独配置从节点，因为 ES 一个 data node 上可能承载某些 Shard 的 primary，也可能承载其他 Shard 的 replica。ES 的副本不是另起一个进程，也不是设置专门的副本节点。ES 的副本只是一个 Shard 的另一份拷贝，会被分配到某个 data 节点上，并满足一个核心规则：**同一个 Shard 的 primary 和 replica 不会被分配到同一个节点。**

为什么 ES 没有把不同职责的节点拆成独立进程呢？这样一个节点承担多个职能会不会显得冗余？

ES 通过在节点中声明角色来实现逻辑上的职责分离。这种设计看似存在能力冗余，但实际上避免了服务间复杂的 RPC 调用，提升了系统弹性和扩展性，使集群能够在节点动态变化的情况下自动重平衡，是一种典型的分布式系统设计取舍。

ES 的主节点是通过内置选举机制自动产生的，负责集群状态和分片调度，不参与数据读写。在数据写入时，请求首先由协调节点路由到目标主分片，所有写操作只在主分片上执行，主分片写入成功后会将相同的写操作同步到副本分片，待副本确认后才返回成功。如果主分片所在节点故障，Master 会自动将副本分片提升为新的主分片，从而保证数据不丢失。
