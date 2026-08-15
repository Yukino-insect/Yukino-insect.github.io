+++
date = '2026-03-17T21:36:31+08:00'
draft = false
title = 'Elasticsearch相似性搜索'

+++

在早期版本的 ES 中，并不支持向量搜索，相似性搜索主要依赖关键词匹配与相关性评分。这种方式的特点是：

- 必须命中相同或相近的关键词
- 对同义词、近义词、语义相似支持较弱
- 查询效果在表达方式不同但语义相同的场景下不理想

随着语义搜索和 AI 应用的发展，ES 从 7.x 版本开始逐步引入向量字段与近似最邻搜索能力。并在 8.x 版本中持续完善，逐步具备了向量数据库的核心能力。通过向量搜索，ES 完全可以：

- 不依赖关键词完全匹配
- 基于语义相似度进行搜索
- 显著提升相似性搜索效果

## Embedding

**Embedding（向量化）模型**，是将**非结构化数据（文本、图片、音频等）\**映射到一个\**固定维度的向量空间**中的模型。

- 原始文本本身**没有维度**
- 向量是一个由数字组成的数学对象，**具有固定维度**
- 向量的维度（如 384、512、768、1536）由 **Embedding 模型本身决定**

从数学角度看：

> 向量可以理解为一个高维空间中的**点**或**有方向的线段**，用于表示语义位置。

Embedding 模型有两类，分别是：

- **Word Embedding**：它可以将单个词映射为向量。主要用于词相似度，词义分析
- **Sentence Embedding**：将整句话/文档映射为向量。主要用于搜索、推荐、问答。

在现代搜索与 RAG（检索增强生成）场景中，**Sentence Embedding 是主流选择**，因为它能表达完整语义，而不是孤立的词义。

> 需要注意的是，不同向量模型训练的数据、模型结构和训练目标不一样，它最终得到的向量空间是不同的，向量是存在于这个空间的点或者有向线段，因此相同的数据最终得到的搜索效果也是不同的。不同向量模型生成的向量之间是不能够进行操作的。

## ES 向量数据库

向量数据库是什么？

向量数据库是指：

> 将一段文本或其他非结构化数据，通过 Embedding 模型转换得到的一组浮点数数组。

向量数据库的核心作用包括：

- 存储向量
- 构建向量索引
- 计算向量之间的相似度
- 返回与查询向量最相似的数据

> 需要明确的是，ES 并不负责生成向量，也不负责把向量还原成文本。

ES 只提供：

- 向量字段存储
- 向量索引
- 向量相似度计算
- 向量之间的计算

因此，在使用 ES 向量搜索时，必须引入外部 Embedding 服务，例如：

- 阿里云向量服务（DashScope）

- OpenAI / 通义千问

- 本地部署模型（BGE、E5、Sentence-BERT 等）

- 自建 Embedding 微服务

## ES 向量搜索流使用程

### 1. 在 ES 中建立索引

```http
PUT /product_vector
{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
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

`title` 是给关键词检索用的文本字段；`embedding` 是给向量检索用的 `dense_vector` 字段。

`embedding` 向量字段中存储的是一个浮点数组。

`type` 表示字段值是一个向量；`dims` 表示该向量字段的维度。向量的维度值必须与这个值相等；`index` 表示是否对这个向量字段建立近似最近邻索引；`similarity` 设置选择向量近似度计算方式。

这套结构写入后，ES 内部会生成两套索引体系：

1. 对 `title`：倒排索引。用于关键词检索（match、multi_match 等）。
2. 对 `embedding`：向量 ANN 索引（常见是 HNSW）。用于向量近似最近邻检索（knn）。

可以理解为在**同一个文档，在 ES 里同时具备文本检索能力和向量检索能力。**

检索时可以使用纯关键词

```json
{
  "query": {
    "match": { "title": "苹果手机" }
  }
}
```

也可以纯向量检索

```json
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.021, -0.33, 0.87, ...],
    "k": 10,
    "num_candidates": 100
  }
}
```

最推荐的使用混合检索。

先用 `knn` 召回语义相近的文档信息。

再结合 `query` 做关键词加权、过滤信息、排序之类的。

### 2. 写入向量数据

```http
POST /product_vector/_doc/1
{
  "title": "iPhone 15 Pro",
  "embedding": [0.021, -0.33, 0.87, ...]
}
```

### 3. 查询流程

之前简单看过查询 JSON 了。值得注意的是，查询的文本数据需要在外部将其转成向量，再用向量查询 ES。

```http
POST /product_vector/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [0.021, -0.33, 0.87, ...],
    "k": 10,
    "num_candidates": 100
  }
}
```

`knn` 是 ES 向量搜索中固定的查询关键字，和 `query` 一个级别；`field` 用于指定在哪个向量字段上做 KNN 搜索；`query_vector` 指定查询用的向量；`k` 用于指定最终返回的最近的 K 条文档；`num_candidates` 在 ANN 搜索过程中，先从向量索引中选出的候选文档数量，可以理解为初筛文档数量。

> 需要注意的是，向量是不可逆的。我们在写入时，文本加向量一起存：
>
> ```json
> {
> "title": "iPhone 15 Pro",
> "content": "苹果最新款高端手机，支持钛合金机身",
> "embedding": [0.021, -0.33, 0.87, ...]
> }
> ```
>
> 但是相似性搜索返回的是文档
>
> ```json
> {
> "_id": "1",
> "_score": 0.87,
> "_source": {
>  "title": "iPhone 15 Pro",
>  "content": "苹果最新款高端手机，支持钛合金机身"
> }
> }
> ```
>
> 如果不显示告诉要对应的向量。ES 只会返回对应的文档，并不会返回向量本身
>
> ```json
> {
> "_id": "1",
> "_score": 0.87,
> "_source": {
>  "title": "iPhone 15 Pro",
>  "content": "苹果最新款高端手机，支持钛合金机身"
> }
> }
> ```
>
> 相似性搜索只是用来计算和搜索内容最相似的文档内容。

### 相似度算法

ES 支持多种向量相似度计算方式：

- `cosine`：余弦相似度（最常用，适合文本）
- `dot_product`：点积
- `l2_norm`：欧式距离

**文本语义搜索中，推荐使用 `cosine`。**

## 在 Java 中使用该功能

整体流程：

```text
用户输入文本
      ↓
Java 服务
      ↓
Embedding 服务（外部）
      ↓
向量 float[]
      ↓
Elasticsearch KNN 搜索
      ↓
返回文档 ID + 文本字段
      ↓
Java 业务处理 / 返回前端
```

### Embedding 服务接口

```java
public interface EmbeddingClient {
    float[] embed(String text);
}
```

该接口用来调用像阿里云 DashScope、OpenAI、本地模型等一些向量模型。

### Java 写入文档

在这之前需要创建好索引

``` java
public void indexDoc(String id, String title, String content) {
    float[] vector = embeddingClient.embed(content);

    Map<String, Object> doc = new HashMap<>();
    doc.put("title", title);
    doc.put("content", content);
    doc.put("embedding", vector);

    esClient.index(i -> i
        .index("product_vector")
        .id(id)
        .document(doc)
    );
}
```

### Java 相似性搜索

```java
// 用户输入
String queryText = "苹果手机";
float[] queryVector = embeddingClient.embed(queryText);
// 构建 KNN 查询
SearchResponse<Map> response = esClient.search(s -> s
    .index("product_vector")
    .knn(k -> k
        .field("embedding")
        .queryVector(Arrays.stream(queryVector).boxed().toList())
        .k(10)
        .numCandidates(100)
    ),
    Map.class
);
// 解析返回结果
List<Map> results = response.hits().hits().stream()
    .map(hit -> hit.source())
    .toList();

for (Map doc : results) {
    String title = (String) doc.get("title");
    String content = (String) doc.get("content");
}
```

在生活中，具有兴趣推荐的软件无处不在，我们可以通过 ES 的相似性搜索简单实现它的核心功能。

> 兴趣推荐的本质是找到和自己近期行为语义上相似的内容。

我们可以实现一个简单的兴趣推荐功能。

整体架构

```text
用户行为（浏览 / 点击 / 搜索）
          ↓
【用户近期行为存储模块】
（Redis / 内存 / KV）
          ↓
构建用户兴趣向量
          ↓
【ES 相似性搜索模块】
（向量 KNN）
          ↓
返回推荐内容
```

一个简单但有效的兴趣推荐模块，可以拆分为两个核心部分：

1. 一是用户近期行为存储模块，用于记录用户最近一段时间内的浏览或点击内容；
2. 二是基于 Elasticsearch 向量相似性搜索的推荐模块，通过将用户近期行为向量化并聚合，构建用户兴趣向量，从而在内容库中检索语义相似的内容作为推荐结果。

### 用户近期行为存储模块

> 快速轻量地保存用户最近一段时间关心什么。

可以使用 Redis。

key 设计

```text
user:behavior:{userId}
```

value 可以是 List/ZSet。以 ZSet 为例

```text
ZADD user:behavior:1001 1700000000 item_123
ZADD user:behavior:1001 1700000100 item_456
ZADD user:behavior:1001 1700000200 item_789
```

为什么用 ZSet？

- 自动按时间排序
- 可以只取最近 N 条
- 方便做时间衰减

#### 行为采集

可以简单的采集

- 用户浏览内容

- 用户点击详情

- 用户停留超过 X 秒

- 用户搜索关键词

> 数据一定要控制规模

### 基于 ES 的相似性推荐模块

> 根据用户最近行为，推荐相似内容

#### 前置条件

相关内容已经向量化并存入 ES。每条内容应该如下：

```json
{
  "id": "item_123",
  "title": "iPhone 15 Pro",
  "content": "苹果最新款手机",
  "embedding": [ ... ]
}
```

#### 构建用于兴趣向量

伪代码

```java
List<float[]> vectors = new ArrayList<>();

for (String itemId : recentItems) {
    float[] v = getEmbeddingFromES(itemId);
    vectors.add(v);
}

float[] userVector = average(vectors);
```

#### 用用户兴趣向量做 ES KNN 搜索

```json
SearchResponse<Map> response = esClient.search(s -> s
    .index("content_index")
    .knn(k -> k
        .field("embedding")
        .queryVector(
            Arrays.stream(userVector)
                  .boxed()
                  .toList()
        )
        .k(10)
        .numCandidates(200)
    ),
    Map.class
);
```

注意一定要过滤用户已经看过的内容

```java
List<Content> results = response.hits().hits().stream()
    .map(hit -> {
        Map<String, Object> source = hit.source();
        Content c = new Content();
        c.setId(hit.id());
        c.setTitle((String) source.get("title"));
        c.setContent((String) source.get("content"));
        return c;
    })
    .toList();

results.removeIf(item -> recentItemIds.contains(item.getId()));
```

### 一个完整的推荐流程

Step 1：用户浏览内容

```text
用户 -> 内容 A
```

写入 Redis：

```text
user:behavior:1001 += A
```

Step 2：用户进入推荐页

```text
GET /recommend?userId=1001
```

Step 3：读取用户最近行为

```text
[A, B, C, D]
```

Step 4：构建用户兴趣向量

```text
userVector = avg(vec(A), vec(B), vec(C), vec(D))
```

Step 5：ES 向量相似性搜索

```text
Top-K 相似内容
```

Step 6：过滤 + 返回

```text
返回用户没看过的内容
```

参考：

**https://zhuanlan.zhihu.com/p/80737146**
