+++
date = '2026-03-17T21:36:31+08:00'
draft = false
title = 'Elasticsearch 相似性搜索'
+++

传统 Elasticsearch 搜索主要依赖关键词匹配。用户搜索“苹果手机”，文档里最好也出现“苹果”“手机”这类词，才能得到较好的召回。

但真实搜索并不总是这么听话：

- 用户搜“适合拍照的高端手机”，文档标题可能是 “iPhone 15 Pro Max”。
- 用户搜“客服系统”，文档里可能写的是 “CRM 工单平台”。
- 用户搜“怎么让系统不崩”，文章标题可能是 “限流、熔断与降级”。

这些场景里，关键词不一定完全重合，但语义是相关的。相似性搜索要解决的就是这种问题。

在 ES 中，相似性搜索通常有三类：

1. **文本相关性搜索**：BM25、`match`、`multi_match`。
2. **向量相似性搜索**：Embedding、`dense_vector`、KNN。
3. **混合检索**：关键词召回和向量召回结合，再统一排序。

现代搜索系统里，第三种最常见。只靠关键词会漏召回，只靠向量又容易召回业务上不合法或不精确的结果。两个都用，才比较像一个成熟系统该有的样子。

## 一、Embedding 是什么

Embedding 是把文本、图片、音频等非结构化数据转换成固定维度向量的过程。

例如一句话：

```text
苹果最新款高端手机
```

经过 Embedding 模型后，可能变成：

```text
[0.021, -0.330, 0.870, ...]
```

这些数字不是随便来的，而是模型把语义压缩到向量空间后的表示。

可以这样理解：

```text
语义相近的文本 -> 向量空间中距离更近
语义无关的文本 -> 向量空间中距离更远
```

需要注意：

- 向量维度由模型决定，例如 384、768、1024、1536。
- 不同模型生成的向量不能随意混用。
- 向量通常不可逆，不能从向量还原原文。
- ES 不负责生成向量，向量需要由外部模型生成。

也就是说：

```text
Embedding 模型：负责把文本变成向量
Elasticsearch：负责存储向量并搜索相似向量
```

这两个职责要分清。否则系统边界会变得很混乱，混乱通常不会自己变好。

## 二、ES 在向量搜索中负责什么

ES 不是专门的 Embedding 模型服务，它在向量搜索中主要负责：

- 存储原始文档字段，例如标题、正文、标签。
- 存储向量字段，例如 `dense_vector`。
- 为向量字段建立近似最近邻索引。
- 根据查询向量召回相似文档。
- 与关键词查询、过滤条件、排序规则组合。

典型流程如下：

```text
用户输入文本
  ↓
调用 Embedding 服务生成 query_vector
  ↓
ES 执行 KNN 向量搜索
  ↓
结合关键词、过滤条件、业务排序
  ↓
返回文档
```

ES 返回的是文档，不是“向量的解释”。向量只是检索过程中的中间表示。

## 三、建立向量索引

先创建一个商品向量索引：

```http
PUT /product_vector
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text"
      },
      "category": {
        "type": "keyword"
      },
      "status": {
        "type": "keyword"
      },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

字段说明：

- `title`：用于关键词检索。
- `category`、`status`：用于业务过滤。
- `embedding`：用于向量检索。
- `dims`：向量维度，必须和 Embedding 模型输出一致。
- `index: true`：为向量建立近似最近邻索引。
- `similarity: cosine`：使用余弦相似度，文本语义检索中很常见。

同一个文档可以同时具备关键词检索和向量检索能力：

```text
title -> 倒排索引 -> match / multi_match
embedding -> HNSW 向量索引 -> knn
category/status -> keyword -> filter
```

## 四、写入向量数据

写入前，先调用外部 Embedding 服务生成向量。

然后把文本字段和向量字段一起写入 ES：

```http
PUT /product_vector/_doc/10001
{
  "title": "iPhone 15 Pro",
  "category": "phone",
  "status": "ON_SALE",
  "embedding": [0.021, -0.330, 0.870]
}
```

真实向量会比示例长得多，这里只是简写。

为什么要同时保存文本和向量？

因为搜索结果最终要展示给用户，用户看的不是向量，而是标题、摘要、价格、标签这些业务字段。

## 五、执行 KNN 查询

查询时，同样要先把用户输入转成向量。

例如用户输入：

```text
适合拍照的高端手机
```

外部模型生成 `query_vector` 后，执行 KNN：

```http
POST /product_vector/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.018, -0.271, 0.903],
    "k": 10,
    "num_candidates": 100
  }
}
```

参数说明：

- `field`：向量字段。
- `query_vector`：查询向量。
- `k`：最终返回最相似的 K 条。
- `num_candidates`：近似搜索时先召回的候选数量。

`num_candidates` 越大，召回质量通常越好，但查询成本也越高。它不是越大越好，虽然很多参数初学者都喜欢往大了调，仿佛调大就能解决人生问题。

## 六、相似度算法

ES 常见向量相似度包括：

| 算法 | 适合场景 | 说明 |
| ---- | -------- | ---- |
| `cosine` | 文本语义相似度 | 关注方向相似，常用于文本 embedding |
| `dot_product` | 已归一化向量、部分模型推荐 | 计算快，但要符合模型要求 |
| `l2_norm` | 距离度量 | 欧式距离，关注空间距离 |

文本语义搜索中，`cosine` 很常见。但最终应该以 Embedding 模型文档和实际评测结果为准。

## 七、混合检索

纯向量搜索容易出现一个问题：语义相似，但业务条件不满足。

例如用户搜索“苹果手机”，向量可能召回“手机壳”“安卓旗舰机评测”等内容。如果业务只允许返回在售手机，就必须加过滤。

示例：

```http
POST /product_vector/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.018, -0.271, 0.903],
    "k": 20,
    "num_candidates": 200,
    "filter": {
      "bool": {
        "filter": [
          { "term": { "category": "phone" } },
          { "term": { "status": "ON_SALE" } }
        ]
      }
    }
  }
}
```

更完整的搜索系统通常会做多路召回：

```text
关键词召回：match / multi_match
  +
向量召回：knn
  +
业务召回：热销、类目、运营配置
  ↓
合并去重
  ↓
重排
```

重排阶段可以结合：

- BM25 分数。
- 向量相似度。
- 点击率。
- 销量。
- 新鲜度。
- 库存。
- 价格。
- 用户偏好。

向量解决的是语义相似，不负责替你理解所有业务规则。它已经很忙了，不要什么都推给它。

## 八、Java 中的基本使用

整体流程：

```text
用户输入文本
  ↓
Java 服务
  ↓
EmbeddingClient 生成向量
  ↓
Elasticsearch KNN 搜索
  ↓
返回文档
```

### 1. Embedding 服务接口

```java
public interface EmbeddingClient {
    List<Float> embed(String text);
}
```

这个接口可以对接：

- OpenAI / 通义千问 / DashScope。
- 本地 BGE、E5、Sentence-BERT。
- 公司内部 Embedding 服务。

### 2. 写入文档

```java
public void indexDoc(String id, String title, String category) throws IOException {
    List<Float> vector = embeddingClient.embed(title);

    Map<String, Object> doc = new HashMap<>();
    doc.put("title", title);
    doc.put("category", category);
    doc.put("status", "ON_SALE");
    doc.put("embedding", vector);

    esClient.index(i -> i
        .index("product_vector")
        .id(id)
        .document(doc)
    );
}
```

### 3. 相似性搜索

```java
public List<Map> searchSimilar(String queryText) throws IOException {
    List<Float> queryVector = embeddingClient.embed(queryText);

    SearchResponse<Map> response = esClient.search(s -> s
        .index("product_vector")
        .knn(k -> k
            .field("embedding")
            .queryVector(queryVector)
            .k(10)
            .numCandidates(100)
        ),
        Map.class
    );

    return response.hits().hits().stream()
        .map(hit -> hit.source())
        .toList();
}
```

实际项目中还要补上：

- 超时控制。
- Embedding 缓存。
- 批量向量化。
- ES 查询过滤。
- 失败降级。
- 结果重排。

## 九、基于 ES 做简单推荐

推荐系统的简化版可以这样理解：

> 用户最近看过什么，就推荐语义上相似的内容。

整体结构：

```text
用户行为
  ↓
Redis 保存最近行为
  ↓
读取行为对应内容向量
  ↓
聚合成用户兴趣向量
  ↓
ES KNN 搜索相似内容
  ↓
过滤已看过内容
  ↓
返回推荐列表
```

### 1. 保存用户近期行为

可以用 Redis ZSet：

```text
ZADD user:behavior:1001 1787385600 item_123
ZADD user:behavior:1001 1787385660 item_456
ZADD user:behavior:1001 1787385720 item_789
```

ZSet 的 score 使用时间戳，方便取最近 N 条。

行为可以包括：

- 浏览内容。
- 点击详情。
- 收藏。
- 搜索关键词。
- 停留超过一定时间。

行为要控制规模，也要做清理。什么都存，只会让系统像囤积癖一样越来越难打扫。

### 2. 构建用户兴趣向量

假设用户最近看过 A、B、C：

```text
userVector = avg(vec(A), vec(B), vec(C))
```

更精细一点可以加时间衰减：

```text
userVector = weighted_avg(
  vec(A) * 0.2,
  vec(B) * 0.3,
  vec(C) * 0.5
)
```

越新的行为权重越高。

### 3. 搜索相似内容

```java
SearchResponse<Map> response = esClient.search(s -> s
    .index("content_index")
    .knn(k -> k
        .field("embedding")
        .queryVector(userVector)
        .k(20)
        .numCandidates(200)
    ),
    Map.class
);
```

然后过滤用户已经看过的内容：

```java
List<Map> results = response.hits().hits().stream()
    .filter(hit -> !recentItemIds.contains(hit.id()))
    .map(hit -> hit.source())
    .toList();
```

真实推荐系统还会加入召回融合、特征排序、探索机制和效果评估。这里的方案只是一个轻量版本，适合理解向量检索在推荐中的位置。

## 十、常见坑

### 1. 写入向量维度不一致

mapping 中 `dims = 768`，写入 1024 维向量会失败。

换 Embedding 模型时，通常需要重建索引。

### 2. 不同模型向量混用

BGE 生成的向量和另一个模型生成的向量不在同一个语义空间里，不能直接混合检索。

### 3. 只做向量，不做过滤

向量相似不等于业务合法。商品是否上架、地区是否可售、权限是否允许，都要用 filter 控制。

### 4. 向量字段过大

向量会增加存储和内存压力。维度越高、文档越多，成本越明显。

### 5. 不做离线评测

向量搜索效果不能只靠肉眼看几个例子。至少要准备查询集、期望结果和指标，例如 Recall、NDCG、MRR。

## 十一、总结

ES 相似性搜索可以这样理解：

- Embedding 模型负责把文本变成向量。
- ES 负责存储向量，并用 KNN 找相似文档。
- `dense_vector` 是向量字段，`knn` 是向量召回方式。
- 文本语义搜索常用 `cosine`，但要以模型和评测结果为准。
- 生产中更推荐关键词检索 + 向量检索 + 业务过滤 + 重排的混合检索。
- 推荐系统可以用用户近期行为向量做 KNN 召回，但完整推荐远不止这一步。

向量搜索很有用，但它不是魔法。它只是把“词是否相同”的问题，扩展成“语义是否接近”的问题。至于业务是否正确、结果是否可控、系统是否稳定，仍然要靠工程设计来负责。
