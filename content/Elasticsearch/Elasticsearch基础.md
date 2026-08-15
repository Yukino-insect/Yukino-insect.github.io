+++
date = '2025-12-14T20:07:16+08:00'
draft = false
title = 'Elasticsearch基础'

+++

最近找实习面试被面试官拷打了 ES，所以补一下这块的知识。

在我的认知里，ES 主要用于电商项目或日志处理中，为用户提供强大的搜索服务。

## 基础概念

ES 使用的是**倒排索引**。这个概念是相对于**正向索引**而言的。

MySQL 就是典型的使用正向索引的例子。直接通过索引字段查询目标数据。但是如果涉及模糊查询，正向索引就比较慢了。

> MySQL 通过索引查询的过程涉及到了索引的底层结构 B+ 树

当我们使用 ES 搜索数据时，倒排索引起到什么作用呢？

1. 首先，用户输入的文本将被分词器分词，得到相应的词项

   > **词项（Term）**：利用**分词算法**，将文档数据或用户查询时输入的文字分解成的具备一定含义的词或字。

2. 接着 ES 会拿着词项在倒排索引表中查找。其中每一个词条都会对应一组文档 id 集合。

3. 最后拿着文档 id，类似于随机访问一样查询具体文档。

> 需要注意的是，**倒排索引不是在创建 index 时生成的。它是在 refresh 时，由 Lucene segment 创建的。**
>
> **ES 的文档存储结构在逻辑上是 docID 对齐的数组，当我们通过倒排索引拿到 docID 之后，可以快速的随机访问文档内容，它不像关系数据库那样会有一个正向索引的过程。**

理解了倒排索引的概念后，我们来看一下 ES 中的一些基础概念

- **Document**：文档。ES 是面向文档存储的。文档可以是数据库中的一条商品数据、一个订单信息等任何数据。文档数据被序列化成 JSON 格式后会存入 ES。

- **Field**：字段。JSON 文档中会包含很多字段，类似于 MySQL 中的列

- **Index**：索引。索引类似于 MySQL 中的表。在 ES 中，相同类型的文档集合组成了索引。

- **mapping**：映射。类似于 MySQL 中的约束。

## ES 的使用

使用 ES 的第一步是到官网下载相关软件包。我选择的是 Elasticsearch 8.10.x 版本和与之对应的 Kibana。

ES 和 Kibana 的关系就像 MySQL Server 和 MySQL Client 一样。ES 是分布式搜索与分析引擎，负责存储和计算。而 Kibana 是其官方提供的可视化与管理界面，通过调用 ES API 提供查询、分析和运维能力，其本身并不存储业务数据。

下载好之后就可以在本地运行这两个组件。

需要注意的是，ES 底层是 Java 开发的。ES 需要在 Java 环境中运行，ES 默认会直接运行在自己提供的 JVM 上，不需要我们自己提供。但是默认的 JVM 堆内存比较大，应该调小一点。调整堆大小的配置文件在 `./config/jvm.options` 中。

当 Kibana 启动完毕访问该应用时，第一次登录需要输入一串 token。这个 token 会在你第一次启动 ES 时打印到终端，同时打印出来的还有登录密码。

登录成功后，我们可以在 Kibana 界面搜索栏中搜索 DevTools，DevTools 是用来编写 DSL 操作 ES 的。

### 分词器

分词器是 ES 的核心，它只在文本被分析的阶段使用。这个阶段主要发生在倒排索引构建阶段和查询文本的解析阶段。但是ES 默认提供的分词器对中文支持不友好，所以我们需要配置 IK 分词器作为中文分词器。

请自行搜索如何下载安装 IK 分词器。

我们在创建索引时显示指定 IK 分词器

```http
PUT /cartoons
{
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "ik_max_word",
        "search_analyzer": "ik_smart"
      }
    }
  }
}
```

`analyzer` 配置的是**写入数据时使用的分词器**；`search_analyzer` 配置的是**查询数据时使用的分词器**。

- `ik_max_word` 模式常用于 `analyzer`，它的特点是尽可能的细分。

- `ik_smart` 模式常用于 `search_analyzer`，它的特点是每个语义只保留一个最合理的词，词最少，且分词精准、干净。

为什么搜索和写入需要配置两个模式。**主要是当 ES 在写入文档时，ES 会使用分词器创建倒排索引，整个文档的倒排索引只在写入阶段创建一次。搜索时，查询文本会被分词器分词，通过词项取查倒排索引。**

我们可以使用 `_analyze` API 手动测试分词效果

```http
GET /_analyze
{
  "analyzer": "ik_max_word",
  "text": "我永远喜欢雪之下雪乃"
}
```

会返回类似

```json
{
  "tokens": [
    {
      "token": "我",
      "start_offset": 0,
      "end_offset": 1,
      "type": "CN_CHAR",
      "position": 0
    },
    {
      "token": "永远",
      "start_offset": 1,
      "end_offset": 3,
      "type": "CN_WORD",
      "position": 1
    },
    {
      "token": "喜欢",
      "start_offset": 3,
      "end_offset": 5,
      "type": "CN_WORD",
      "position": 2
    },
    {
      "token": "雪",
      "start_offset": 5,
      "end_offset": 6,
      "type": "CN_CHAR",
      "position": 3
    },
    {
      "token": "之下",
      "start_offset": 6,
      "end_offset": 8,
      "type": "CN_WORD",
      "position": 4
    },
    {
      "token": "下雪",
      "start_offset": 7,
      "end_offset": 9,
      "type": "CN_WORD",
      "position": 5
    },
    {
      "token": "乃",
      "start_offset": 9,
      "end_offset": 10,
      "type": "CN_CHAR",
      "position": 6
    }
  ]
}
```

需要强调的是，分词器也是按规则行使的，它的分词规则主要来自：

- 内置词典
- 自定义词典
- 停用词词典

> IK 分词器是靠词典文件驱动的

它的使用顺序是

```text
- IK 内置词典
- 自定义词典
- 分词策略（max_word / smart）
- 停用词过滤
- 输出 token
```

其中内置词典一般我们是不会动的。然后是自定义词典，我们为什么要有自定义词典呢？

在互联网大行其道的时代，过一段时间就会兴起一些网络流行词，这些词在 IK 分词器的内置词典中是没有的所以需要我们手动配置它。还有就是停用词。如果使用者不允许搜索停用词的相关内容，就需要在 IK 分词器的停用词配置文件中写明。

> 自定义词典文件的规则是每一个词项写一行

这些配置都可以在 IK 分词器目录下的 config 中的配置文件中声明。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">
<properties>
	<comment>IK Analyzer 扩展配置</comment>
	<!--用户可以在这里配置自己的扩展字典 -->
	<entry key="ext_dict"></entry>
	 <!--用户可以在这里配置自己的扩展停止词字典-->
	<entry key="ext_stopwords"></entry>
	<!--用户可以在这里配置远程扩展字典 -->
	<!-- <entry key="remote_ext_dict">words_location</entry> -->
	<!--用户可以在这里配置远程扩展停止词字典-->
	<!-- <entry key="remote_ext_stopwords">words_location</entry> -->
</properties>
```

### ES 的 DSL

ES 对外提供了 RESTful API，而查询条件是通过 JSON 格式的 DSL 来描述的。

#### 索引库操作

我们先来看一下 ES 的整个约束结构

```json 
{
  "settings": { ... },
  "mappings": {
    "dynamic": true,
    "properties": {
      "field_name": {
        "type": "...",
        "fields": { ... },
        "analyzer": "...",
        "search_analyzer": "...",
        "index": true,
        "doc_values": true,
        "store": false,
        "null_value": "...",
        "ignore_above": 256,
        "copy_to": "...",
        "norms": true
      }
    }
  }
}
```

`mappings` 是定义约束的最上层，是所有字段约束的总入口。

#### `dynamic`

```json
"dynamic": true | false | "strict"
```

- `true` 的行为是，当写入未知字段时，自动推断字段类型，然后自动将该字段加入 mapping。

- `false` 代表，未定义字段是不进入 mapping，但原始字段和值仍然写进 `_source`，但是不可以搜索、排序聚合。

- `strict` 的行为是当出现未定义字段时，直接拒绝写入，返回错误。这样可以防止脏数据，防止 mapping 被污染，它可以定义在全局，也可以定义在字段局部。

`dynamic` 是 ES 中控制未定义字段写入行为的全局或局部策略，用来决定是否自动生成 mapping、是否忽略字段或直接拒绝写入，是 mapping 的第一道约束门。

#### `properties`

字段级约束有哪些：

类型约束 `type` 它是最根本的约束，它决定了字段底层使用哪种 Lucene Field 以及是否支持分词，是否支持排序聚合，使用哪种存储结构。常见的类型约束有：

type：字段数据类型，常见的简单类型有：

- 字符串：**text**（可分词的文本）、**keyword**（不可分词）

- 数值：long、integer、short、byte、double、float、

- 布尔：boolean

- 日期：date

- 对象：object

#### `fields`

 `fields` 是在 mapping 阶段定义的索引层概念，用于将同一个字段以多种方式建立索引，从而支持全文检索、精确匹配、排序和聚合等不同查询需求；查询和返回阶段只是对这些索引结构的使用。

#### `analyzer`

 定义写入时的分词器，决定文本被如何拆分成 token

#### `search_analyzer` 

定义查询时分词器，决定搜索时查询时分词器该如何分词

#### `index`

当字段 `index:false` 时，ES 不会为该字段建立倒排索引，字段仍会存入 `_source`，是否还能排序或聚合取决于 `doc_values`，但该字段永远不能用于搜索条件。

#### `doc_values`

`doc_values` 用于决定字段是否以列式结构存储，从而支持高效的排序、聚合和脚本取值；在实践中它主要用于不可分词（如 keyword、numeric、date）字段，其本质与是否分词无关，而是与按文档取字段值的访问模式有关。

`doc_values` 之所以能高效取值，是因为它将字段值按 docID 顺序以列式结构存储在磁盘上，并通过 mmap 映射到进程地址空间，使得 ES 可以直接、顺序或近似 O(1) 地按文档访问字段值，而无需反向遍历倒排索引或将数据加载到 JVM 堆中。
 借助列式布局、docID 对齐、OS 页缓存以及高效的编码方式，`doc_values` 成为了排序、聚合和脚本计算性能的根本基础。`doc_values` 本身只是是否启用该结构的配置开关，具体的数据布局与编码策略由 Lucene 内部根据字段类型自动决定。

#### `store`

 默认 `_source` 存的是**整条原始 JSON**。返回字段时，先读整个 `_source`，再解析 JSON，得到最终的结果。

`store` 用于决定字段是否以独立的 stored field 形式存储，从而在查询结果中可以不依赖 `_source` 直接返回该字段值；它不参与搜索、排序或聚合，主要用于优化字段取回路径，在 `_source` 很大或被禁用的场景下才有明显价值。

#### `null_value` 

当字段为 null 时，可以将 null 值替换成 `null_value` 指定值写入索引

#### `ignore_above`

#### `copy_to`

#### `norms`

`norms` 通过记录字段长度等信息，在 BM25 等相关性算法中对评分进行归一化，使短字段比长字段更容易获得高分，从而显著影响搜索结果的排序。

这些 mapping 参数本质是在“写入阶段”定义字段如何被拆分、索引、存储和评分，一旦写入就不可更改，是 ES 中最重要的结构性约束。

我们可以使用如下命令进行相关操作

- 创建索引库：PUT /索引库名
- 查询索引库：GET /索引库名
- 删除索引库：DELETE /索引库名
- 修改索引库：PUT /索引库名/_mapping

例如创建索引：

```http
PUT /users
{
  "mappings": {
    "properties": {
      "id": {
        "type": "keyword"
      },
      "name": {
        "type": "text",
        "analyzer": "ik_max_word",
        "search_analyzer": "ik_smart",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "age": {
        "type": "integer"
      },
      "createdAt": {
        "type": "date",
        "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"
      }
    }
  }
}
```

**Elasticsearch 的文档约束（mapping）一旦确定，已存在字段的核心属性（类型、分词、索引方式等）基本不可修改；允许的修改仅限于向前兼容的操作，如新增字段或为已有字段新增 multi-field。若需要真正修改字段定义，唯一安全方式是新建索引并通过 reindex 重建数据。**

### 文档操作

了解了索引操作后，再来了解一下文档操作。文档本质上就是一个 JSON对象。大概长这样

```json
{
  "_index": "user",
  "_id": "1",
  "_version": 3,
  "_seq_no": 15,
  "_primary_term": 1,
  "found": true,
  "_source": {
    "user": "zhangsan",
    "age": 18,
    "tags": ["java", "es"],
    "address": {
      "city": "beijing",
      "code": "100000"
    },
    "createTime": "2025-12-17T10:00:00"
  }
}
```

文档信息包括了一部分元数据和我们真正需要的文档内容 `_source`。

返回的元数据包括 `_index` 索引名、`_id` 文档主键、`_version` 版本号、`_seq_no` 并发控制序号、`_primary_term`、`found` 是否存在等。

我们在新增文档时，是不需要填写这些元数据的，我们只需要按照 mapping 规则填写正确的 `_source` 部分即可。

下面来看一下文档的相关操作：

- 查询文档 GET /索引/_doc /文档 id
- 更新文档 POST /索引/_update/文档 id
- 插入文档 POST /索引/_update/文档 id
- DELETE /索引/_doc/文档 id

> 这里列举一些 ES 向外暴露的 RESTful 接口路径
>
> - `_doc` —— 文档的统一入口
> - `_create` —— 防止覆盖的安全写入
> - `_update` —— 局部更新（但不是原地）
> - `_delete` —— 删除文档
> - `_bulk` —— 批量操作
> - `_mget` —— 批量按 ID 查询
> - `_search` —— 搜索入口（倒排索引）
> - `_update_by_query` —— 批量更新
> - `_delete_by_query` —— 批量删除

在新增文档时，推荐显示指定 `_id`

```http 
PUT /user/_doc/1
{
  "id": 1,
  "user": "zhangsan",
  "age": 18,
  "tags": ["java", "es"],
  "address": {
    "city": "beijing",
    "code": "100000"
  },
  "createTime": "2025-12-17T10:00:00"
}
```

如果不指定 `_id`，ES 会为每个文档自动生成一个。注意，URL 中的 `1` 才是 ES 里的 `_id`，JSON 中的 `id` 是我们规定的业务字段。**生产时比较建议将两者统一。因为这样，我们在更新该条文档时可以保证幂等，同时在更改查询删除时也可以直接按 `_id` 查找。**

在 REST 的语义中，`POST` 代表由服务端生成资源标识符。ES 的 `POST user/_doc` 是遵守 REST 语义的，因此该操作不能指定 `_id`，`_id` 由 ES 自动生成。如果同样的一条数据使用 `POST` 新增可能会生成两个文档，这样不能保证幂等。而 `PUT user/_doc/1` 则代表将指定的资源变成我给定的状态，这可以显示的标明相关信息。

当我们在执行 `PUT`、`DELETE` 等更新删除操作时，并不会操作原数据。在 ES 中，文档是存在于 segment 的，它是 Lucene 的最小索引单元。一旦生成就不会变了。

当我们执行 PUT 更新时，ES 会在 segment 定位原来的文档，标记该文档为删除。但数据仍然存在磁盘中并没有做任何操作。ES 最终会生成一个新的文档写入新的 segment。DELETE 同样如此。

#### 批量操作

我们很容易想到，将多个 HTTP 请求合并成一次网络请求可以极大提升性能，减少网络开销。ES 中的批量操作就是起到这样的作用。

Bulk 的核心路径

```http
POST /_bulk
```

限定索引

```http
POST /user/_bulk
```

它的请求格式

```http
POST /_bulk
{ "index":  { "_index": "user", "_id": "1" } }
{ "name": "zhangsan", "age": 18 }
{ "update": { "_index": "user", "_id": "2" } }
{ "doc": { "age": 20 } }
{ "delete": { "_index": "user", "_id": "3" } }
```

Bulk 的书写规则是奇数行操作元数据，偶数行操作文档内容（delete 操作没有）。每行必须是完整 JSON。每行结尾必须换行。

#### 条件查询

> 使用 ES 的原因之一便是因为它拥有强大的搜索功能

ES 条件查询的 JSON 格式是 

```http
POST index_name/_search
{
  "from": 0,
  "size": 10,
  "_source": ["field1", "field2"],
  "query": {
    ...
  },
  "sort": [
    { "field": "asc" }
  ],
  "aggs": {
    ...
  }
}
```

`from ` 是分页起始位置；`size` 是返回的条数；`_source` 控制返回哪些字段；`query` 查询条件；`sort` 排序条件；`aggs` 聚合。

接下来介绍一下常见的查询条件

#### 全文检索查询

全文检索涉及到**分词**和**相关度**

整个过程是：分词 -> 倒排 -> 算分 -> 排序。

常用的有

##### `match`

```json
{
  "match": {
    "title": "我永远喜欢雪之下雪乃"
  }
}
```

##### `multi_match`

```json
{
  "multi_match": {
    "query": "张三",
    "fields": ["name", "nickname", "description"]
  }
}
```

`match` 是根据一个字段查询，我们可以通过构建 `copy_to` 字段实现多字段检索

`multi_match` 是根据多个字段查询，参与的字段越多，查询性能越差。因此我们可以使用 `match` 配合 `copy_to` 来达到 `multi_match` 的效果。

#### 精确匹配

一般是查找 `keyword`、数值、日期、`boolean` 等类型字段。这些字段不会被分词。

常见的有：

##### `term`

```json
{
  "term": {
    "status": "online"
  }
}
```

##### `terms`

```json
{
  "terms": {
    "status": ["online", "offline"]
  }
}
```

##### `range`

```json
{
  "range": {
    "age": {
      "gte": 18,
      "lt": 60
    }
  }
}
```

`range` 支持的核心参数：

- `gt` ：大于
- `gte`：大于等于
- `lt`：小于
- `lte`：小于等于

##### `exists`

```json
{
  "exists": {
    "field": "email"
  }
}
```

#### 复合查询

复合查询主要是将多个查询条件组合起来，控制查询逻辑。

##### bool 查询

bool 查询是最常用的查询手段。它的整体 JSON 结构如下：

```json
{
  "query": {
    "bool": {
      "must": [],
      "should": [],
      "filter": [],
      "must_not": []
    }
  }
}
```

其中 `must` 是必须满足的条件，相当于 **AND** 逻辑，并且会参与算分；`should` 相当于 **OR**，参与算分；`filter` 作为筛选条件，它不会参与算分的；`must_not` 是必须不满足的条件，不会参与算分。

一个完整的查询命令：

```http
POST product/_search
{
  "from": 0,
  "size": 10,
  "_source": ["id", "title", "price", "createTime"],
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "title": "Java"
          }
        }
      ],
      "filter": [
        {
          "term": {
            "status": 1
          }
        },
        {
          "range": {
            "price": {
              "gte": 100,
              "lte": 500
            }
          }
        }
      ],
      "must_not": [
        {
          "term": {
            "deleted": true
          }
        }
      ]
    }
  },
  "sort": [
    {
      "createTime": {
        "order": "desc"
      }
    }
  ]
}
```

从我们的 REST 命令 `POST product/_search` 可以看出。带 JSON 体的查询是使用 POST 的。ES 同时支持两种查询方式

```http
GET  /index/_search
POST /index/_search
```

两者的语义完全一致。官方推荐凡是带 DSL body 的查询用 POST。简单、无 body 的查询用 GET

```http
GET /index/_doc/1
GET /index/_count
GET /index/_mapping
GET /_cluster/health
```

> Elasticsearch 的查询接口是 RESTful 的，DSL 查询通过 HTTP 请求体传递；在实际使用中，复杂条件查询和聚合通常使用 POST，而不是 GET，这是出于工程稳定性和兼容性的考虑，而非查询语义本身的限制。

##### 打分

我们上面讲的 bool 查询是涉及打分的。ES 中默认的 `must` 和 `should` 中的条件字段参与打分。

```json
{
  "bool": {
    "must": [ ... ],
    "should": [ ... ]
  }
}
```

同一个查询中 `must` 肯定算分，可以简单理解如果 `should` 命中的越多，分数越高，返回的自定义排序就越靠前。

我们也可以轻度自定义打分比重

```json
{
  "match": {
    "title": {
      "query": "Java",
      "boost": 2
    }
  }
}
```

通过 `boost` 认为调整评分比重。

**`function_score` 是 ES 为我们提供的自定义的打分机制。**

```json
{
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            { "match": { "title": "Java" } }
          ]
        }
      },
      "functions": [
        {
          "filter": { "term": { "isVip": true } },
          "weight": 5
        }
      ],
      "score_mode": "sum",
      "boost_mode": "sum"
    }
  }
}
```

`function_score` 用来在 ES 默认 `_score` 的基础上，按照业务规则重新计算或调整分数。`query` 查询条件和 `functins` 自定义评分函数都放到该层。`query` 决定哪些文档能参与排序；`functions` 决定了评分规则。

`boost` 字段参与的是ES 默认 BM25 算分过程的权重系数，用于调整不同查询或字段在相关度中的影响力。

`functions` 中的每一个函数，都会在 `filter` 条件满足时，产生一个函数分数，这个分数由 `weight` 决定。所有参与评分的条件都应该放在 `functions` 的 `filter` 字段中，比如 `term`、`must` 甚至 `bool` 的更加复杂的条件。

`score_mode` 用来规定自定义的多个 `function` 算出来的分数如何合计。常见的模式有 `sum` 相加、`multiply` 相乘、`max` 取最大、`min` 取最小、`avg` 取平均。

`boost_mode` 用来规定函数算出来的分数如何和原始 `_score` 合计。常见的模式和 `score_mode` 类似。

**`_score` 评分影响的是默认结果顺序。其结果顺序代表搜索结果的合理程度。但是它不会影响命中、返回字段和过滤结果。**

考虑 `_score` 的场景主要涉及搜索系统，内容推荐等。

#### 地理坐标查询 

> *Redis 也提供了地理位置 GEO*
>
> **常用命令**：
>
> ```bash
> GEOADD shop 116.4074 39.9042 shopA
> GEOADD shop 121.4737 31.2304 shopB
> ```
>
> **命令格式**
>
> ```java
> GEOADD key longitude latitude member
> ```
>
> 经度在前，纬度在后
>
> **查询两点距离**
>
> ```bash
> GEODIST shop shopA shopB km
> ```
>
> **查询附近 X km 内的点**
>
> ```bash
> GEOSEARCH shop
> FROMLONLAT 116.4074 39.9042
> BYRADIUS 5 km
> WITHDIST
> ```
>
> **查询某个点的坐标**
>
> ```bash
> GEOPOS shop shopA
> ```
>
> Redis GEO 速度极快，命令简单，适合高并发和实时数据。
>
> 但是 Redis GEO 只能做距离、半径等的简单操作。不支持复杂的过滤条件

ES 提供了专业级别的地理坐标查询的功能。支持 `geo_point` 和 `geo_shape` 两种级别

mapping 结构

```json
"mappings": {
    "properties": {
        "location": {
            "type": "geo_point"
        }
    }
}
```

##### `geo_bounding_box`

```json
{
  "query": {
    "bool": {
      "filter": [
        {
          "geo_bounding_box": {
            "location": {
              "top_left": {
                "lat": 40.0,
                "lon": 116.0
              },
              "bottom_right": {
                "lat": 39.5,
                "lon": 116.8
              }
            }
          }
        }
      ]
    }
  }
}
```

`top_left` 代表左上角；`bottom_right` 代表右下角。

`lat` 代表纬度；`lon` 代表经度。

如果不写单位，距离默认是 `m`。ES 提供了以下单位：`m`、`km`、` cm`、`mm`；`mi`、`yd`、`ft`、`in`。前半部分是公制单位，后半部分是英制单位。

##### `geo_distance`

```json
{
  "query": {
    "bool": {
      "filter": [
        {
          "geo_distance": {
            "distance": "5km",
            "location": {
              "lat": 39.9042,
              "lon": 116.4074
            }
          }
        }
      ]
    }
  }
}
```

`distance` 参数是半径；`location` 参数是圆心。

#### 排序

ES 的排序分为两大类：

1. 基于 `_score` 的排序，相关性排序，是默认的。
2. 基于字段值的排序，如数值、时间、`keyword`、`geo` 等

当我们显示指定 `sort` 时，结果的排序规则将按照 `sort`。但 ES 默认仍然会算 `_score`，`_score` 的结果不会参加排序。**但是我们需要注意，算分是有性能成本的，当再大数据量下，这部分影响非常明显。**

那在使用过程中如何减小算分影响呢：

- 使用 `filter`，不用 `match`。`filter` 不参加评分，`match` 则相反。
- 显示声明 `track_scores: false`。ES 不会保留 `_score`，仍然会执行 `match` 的算分逻辑，但不会在排序阶段维护 `_score`。

```json
{
  "query": {
    "match": {
      "title": "Java"
    }
  },
  "sort": [
    { "createTime": "desc" }
  ],
  "track_scores": false
}
```

在字段排序时需要注意，`text` 类型不能排序。因此，如果我们想要用 `text` 排序。可以使用 `fields`。

如果有多个字段参与排序，它的排序规则是：

1. 先按第一个字段排
2. 如果第一个相等则按第二个字段排
3. 一直比到有结果为止

#### 分页

基本语法

```json
{
  "from": 0,
  "size": 10,
  "query": {
    "match_all": {}
  }
}
```

`from` 代表跳过多少条；`size` 代表返回多少条。类似 MySQL 执行 `LIMIT offset, size`。

ES 分页时，默认 `from` + `size` 的值最大为 10000，这是为了防止深分页带来的高内存和高 CPU 消耗。ES 不是数据库，它是分布式搜索引擎。ES 的一个查询会打到多个分片上。每个分片都会查询、排序，然后合并。ES 分页的本质就是**在所有分片上取数据、排序、丢弃不需要的数据返回最终的结果**。

因此，当使用 ES 分页遇到**深度分页**问题时，会极大影响服务器的性能。

如何解决深度分页问题呢。

ES 官方提供了 `search_after`，和我们解决 MySQL 深度分页问题的方案类似

使用 `search_after` 会让分页接着其指定的位置开始。

```json
{
  "size": 10,
  "sort": [
    { "create_time": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [1700000000000, "abc123"]
}
```

#### 高亮

**高亮就是将命中的查询关键词在返回结果中用标签包起来。在 ES 中，高亮是搜索阶段的结果再加工。**

基本写法

```http
POST /product/_search
{
  "query": {
    "match": {
      "title": "Java"
    }
  },
  "highlight": {
    "fields": {
      "title": {}
    }
  }
}
```

返回结果结构

```json
{
  "hits": {
    "hits": [
      {
        "_source": {
          "title": "Java 并发编程"
        },
        "highlight": {
          "title": [
            "<em>Java</em> 并发编程"
          ]
        }
      }
    ]
  }
}
```

`_source.title` 是原文；`highlight.title[0]` 是高亮后的文本。前端一般优先用 `highlight`，没有就用 `_source`。

在 ES 里，高亮是否生效取决于两个条件同时满足：

1. 字段必须是可高亮字段，有可用于匹配的 token，一般是 `text` 类型，使用分词器 产生 token。像 `keyword`、`date` 等没有分词，不能产生 token。这样是很难高亮的。
2. 高亮展示的内容是 `query` 的命中词，只有参与 `match` 命中的 token 才可能被高亮。最常见的是查询条件中 `must`、`should` 字段中产生高亮字段。
3. ES 还必须能够还原字段的原始文本与命中词的位置信息。

#### 聚合查询

在 ES 中，一次 `_search` 请求中有两条平行流水线。

1. 查数据
1. 做统计

聚合查询相当于在查询结果集之上做统计分析，而不是返回文档本身。

ES 聚合的整个操作结构

```http
POST index/_search
{
  "size": 0,
  "query": { ... },
  "aggs": {
    "agg_name": {
      "agg_type": {
        "field": "field_name"
      }
    }
  }
}
```

`"size": 0` 表示不要文档，只要统计指标；`query` 是查询条件；`aggs` 表示统计操作。

ES 的三大类集合：

- Bucket：分桶。类似 SQL：`GROUP BY`

- Metric：指标，用于统计值。类似 SQL：`count / sum / avg / max`

- Pipeline：管道，对聚合结果再计算。类似 SQL：`having / 二次计算`

#### Bucket

##### `terms`

```json
{
  "aggs": {
    "by_status": {
      "terms": {
        "field": "status"
      }
    }
  }
}
```

`by_status` 是自定义的聚合操作名，该操作中的是聚合条件。

返回结果值：

```json
"aggregations": {
  "by_status": {
    "buckets": [
      { "key": 1, "doc_count": 120 },
      { "key": 2, "doc_count": 80 }
    ]
  }
}
```

`key` 是分组字段的分组值，`doc_count` 是该组的文档数。

> 分组条件字段必须是 `keyword`、数值等类型，`text` 类型的字段需要使用多字段。

##### `date_histogram`

```json
"aggs": {
  "by_day": {
    "date_histogram": {
      "field": "createTime",
      "calendar_interval": "day"
    }
  }
}
```

返回结果值

```json
{
  "key_as_string": "2024-01-01",
  "doc_count": 25
}
```

其中，聚合参数 `field` 表示用于聚合的字段；`calendar_interval` 表示基于日历语义的时间间隔。

##### `range`

```json
"aggs": {
  "price_range": {
    "range": {
      "field": "price",
      "ranges": [
        { "to": 100 },
        { "from": 100, "to": 500 },
        { "from": 500 }
      ]
    }
  }
}
```

它的返回值长这样

```json
"price_range": {
  "buckets": [
    {
      "key": "*-100.0",
      "to": 100.0,
      "doc_count": 12
    },
    {
      "key": "100.0-500.0",
      "from": 100.0,
      "to": 500.0,
      "doc_count": 36
    },
    {
      "key": "500.0-*",
      "from": 500.0,
      "doc_count": 8
    }
  ]
}
```

可以看到，`range` 操作将一组数据分割成了多个不同的区间。`to` 是上限区间；`from:to` 是双边区间；`from` 是下线区间。

##### `histogram`

```json
"aggs": {
  "score_hist": {
    "histogram": {
      "field": "score",
      "interval": 10
    }
  }
}
```

`filters` 多条件并行分桶

它会作用同一批数据，用多个 `filter` 并行分桶。每一个 `filter` 一个桶，桶之间互不影响、互不包容。

```json
"aggs": {
  "by_status": {
    "filters": {
      "filters": {
        "paid": { "term": { "status": "PAID" } },
        "cancel": { "term": { "status": "CANCEL" } }
      }
    }
  }
}
```

要注意上述第一个 `filters` 是自定义的聚合操作名称；第二个 `filters` 是 ES DSL 中真正的聚合类型，用多组过滤条件并行分桶；`paid` 是将来返回的桶的名称，将来出现在返回结果中。每个桶会对应一个 filter query，本质是一个 `bool.filter` 语义。

上述操作的返回结果是

```json
"by_status": {
  "buckets": {
    "paid": {
      "doc_count": 120
    },
    "cancel": {
      "doc_count": 10
    }
  }
}
```

##### `filter`

了解上述操作之后，这个操作就很简单了。

```json
"aggs": {
  "vip_orders": {
    "filter": {
      "term": { "isVip": true }
    }
  }
}
```

#### Metric

```http
POST order/_search
{
  "size": 0,
  "aggs": {
    "by_status": {
      "terms": {
        "field": "status"
      },
      "aggs": {
        "total_amount": {
          "sum": {
            "field": "amount"
          }
        }
      }
    }
  }
}
```

可以发现我们在这个桶内部嵌套了一个聚合操作，对当前桶中的数据做统计。ES 聚合操作的单位是桶，Bucket 类的操作会将索引中的文档分成多个桶。我们嵌套的 Metric、Pipeline 等操作会作用于每一个桶。

上面操作的返回的结果为：

```json
{
  "key": "PAID",
  "doc_count": 120,
  "total_amount": {
    "value": 23988.5
  }
}
```

Metric 主要是对桶中的数据做统计计算。最基础的 `count` 操作是 ES 的隐式指标，不需要我们显示操作，每个 bucket 天生自带，还有一些常用的有：

- `sum` 求和
- `avg` 求平均值
- `min`/`max` 最大最小值
- `cardinality` 近似去重
- `stats` 上述操作的集合，返回 `count / min / max / avg / sum`

还有一些高级操作，用到再学

#### Pipeline

会对已经聚合的结果再计算

ES 一次聚合的执行顺序是：

```text
query
- Bucket 聚合（建桶）
- Metric 聚合（算值）
- Pipeline 聚合（算桶 / 算指标）
```

Pipeline 的两大类

- Bucket Pipeline 作用于桶
  - `bucket_selector` 过滤桶
  - `bucket_sort` 排序，截断桶
- Metric Pipeline 用作于指标
  - `bucket_script` 算新指标
  - `sum_bucket` / `avg_bucket`
  - `max_bucket` / `min_bucket`

##### `bucket_selector`

```json
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": {
        "field": "category"
      },
      "aggs": {
        "keep_big": {
          "bucket_selector": {
            "buckets_path": {
              "cnt": "_count"
            },
            "script": "params.cnt > 100"
          }
        }
      }
    }
  }
}
```

其中 `keep_big` 是子聚合名。`bucket_selector` 是 Pipeline 聚合操作，其作用是根据已有的聚合结果，对桶做过滤。`buckets_path` 声明该操作要使用哪些已有指标。`cnt` 是声明的脚本变量名。`_count` 表示当前桶的 `doc_count`。`script` 是脚本操作。

`script` 是在 ES 执行过程中，允许使用脚本对值或结果做自定义的计算或判断的机制。它可以用于多种条件，具体等用到再学。这里关注一下 Pipeline 阶段的用法。

它主要有两种用法

 在 `bucket_selector` 中返回 booleam，起到过滤作用

```json
"bucket_selector": {
  "buckets_path": {
    "cnt": "_count"
  },
  "script": "params.cnt > 100"
}
```

如果返回 `true` 保留桶；`false` 丢弃桶。

##### `bucket_script`

```json
"bucket_script": {
  "buckets_path": {
    "amt": "total_amount",
    "cnt": "order_cnt"
  },
  "script": "params.cnt == 0 ? 0 : params.amt / params.cnt"
}
```

这是一个 Pipeline Metric 聚合，基于已有的 `total_amount`、`order_cnt` 指标再派生出一个新的 Metric。这个新的指标将会挂在当前桶上，作为返回值。

```json
"buckets_path": {
  "amt": "total_amount",
  "cnt": "order_cnt"
}
```

这是一个参数绑定声明，作用范围是当前桶。该部分的作用是引用当前桶中已存在的 Metric 聚合结果，将这些结果以只读参数的形式注入到 Pipeline script 的 `params` 中。

`params` 是 ES 再执行脚本时自动构造的只读参数 Map。

##### `bucket_sort`

它的作用是，在所有桶及其子聚合结果已经算完之后，按指定指标对桶进行排序，并只保留前 N 个桶。这就体现了 Pipeline 是对桶的操作，而不是文档之流。

```json
"bucket_sort": {
  "sort": [
    { "total_amount": { "order": "desc" } }
  ],
  "size": 5
}
```

该操作的含义是按每个桶里的 `total_amount` Metric 值排序，`size` 表示排序完成后只保留 5 个桶。

`sum_bucket` / `avg_bucket` 可以实现跨桶统计

这些操作把 `terms`、`date_histogram` 这样的多桶聚合操作生成的每一个桶里的指标拿出来进行操作。

```json
"aggs": {
  "by_category": {
    "terms": { "field": "category" },
    "aggs": {
      "total_amount": {
        "sum": { "field": "amount" }
      }
    }
  },
  "all_amount": {
    "sum_bucket": {
      "buckets_path": "by_category>total_amount"
    }
  }
}
```

`by_category>total_amount` 这时 Pipeline 聚合里的路径表达式，含义是从名为 `by_category` 的多桶聚合中，进入它的每一个桶，读取名为 `total_amount` 的 Metric 结果值。相当于跨桶取数。

然后 `sum_bucket` 就表示将这些数据求和。注意，该操作和 `by_category` 是统一级别。

返回值长这样

```json
"aggregations": {
  "by_category": {
    "buckets": [
      { "key": "BOOK", "total_amount": { "value": 300 } },
      { "key": "FOOD", "total_amount": { "value": 200 } },
      { "key": "GAME", "total_amount": { "value": 500 } }
    ]
  },
  "all_amount": {
    "value": 1000
  }
}
```

越学越觉得 ES 博大精深，等下次再被面试官拷打了再做补充。希望在日后有机会可以实战。

## Spring 集成

在 Spring 中集成 Elasticsearch 常用的方式有两种：一是使用 Spring Data Elasticsearch，通过 Repository 和注解的方式进行简单的 CRUD 和查询搜索；二是使用官方提供的 Elasticsearch Java Client，直接构建 DSL 查询，适合复杂搜索和生产环境。官方推荐使用第二种。

接下来我们使用 Elasticsearch Java Client 操作 ES。

### 依赖

在 `pom.xml` 文件中，添加如下依赖。

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
    </dependency>
    <dependency>
        <groupId>co.elastic.clients</groupId>
        <artifactId>elasticsearch-java</artifactId>
        <version>8.10.4</version>
    </dependency>

    <!-- JSON处理 -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
</dependencies>
```

### 配置

我们在配置 ES 的 Java 客户端时需要注意，ES 8.x 默认开启 HTTPS；开启用户名和密码；使用自签名 SSL 证书。

ES 客户端的架构主要是

```text
ElasticsearchClient
 └── ElasticsearchTransport
      └── RestClient
           └── HttpHost + HttpClient 配置
```

我们最终得到的是 `ElasticsearchClient`，其余配置都是底层通信配置。

总体配置如下。

```java
@Configuration
public class ElasticsearchConfig {

    @Bean
    public ElasticsearchClient elasticsearchClient() throws Exception {

        // 忽略 SSL 证书校验（仅限本地开发）
        SSLContext sslContext = SSLContexts.custom()
                .loadTrustMaterial(null, (chain, authType) -> true)
                .build();

        // 账号密码
        CredentialsProvider credentialsProvider = new BasicCredentialsProvider();
        credentialsProvider.setCredentials(
                AuthScope.ANY,
                new UsernamePasswordCredentials(
                        "elastic",
                        "xAa9clAtHSbE5rq3q7_I"
                )
        );

        // 一定要用 https
        RestClientBuilder builder = RestClient.builder(
                new HttpHost("localhost", 9200, "https")
        );

        builder.setHttpClientConfigCallback(httpClientBuilder ->
                httpClientBuilder
                        .setSSLContext(sslContext)
                        .setDefaultCredentialsProvider(credentialsProvider)
        );

        RestClient restClient = builder.build();

        ElasticsearchTransport transport =
                new RestClientTransport(restClient, new JacksonJsonpMapper());

        return new ElasticsearchClient(transport);
    }
}
```

上述配置中

```java
SSLContext sslContext = SSLContexts.custom()
        .loadTrustMaterial(null, (chain, authType) -> true)
        .build();
```

这段代码的含义是无条件信任所有 SSL 证书。ES 8.x 默认生成的是自签名证书。JVM 默认不信任自签名证书。因此在本地开发环境下选择添加此配置。生产环境下需要把 ES 的 `http_ca.crt` 导入 JVM truststore 中。具体配置等在生产环境中有机会在研究。

从 Elasticsearch 8.x 开始，默认启用 Security；所有 HTTP 请求必须认证；不带认证直接返回 `401 Unauthorized`。因此，我们需要配置 `CredentialsProvider`，它会在每一次 HTTP 请求中自动添加 `Authorization: Basic xxx`。不需要手动写 header。

`RestClient` 是 Elastic Java Client 的 HTTP 底层，负责连接池；负责 HTTP 请求；负责序列化前的通信。

`RestClientTransport` 负责将 REST 请求包装成 ES API。`JacksonJsonpMapper` 用于 JSON 和 Java POJO 的映射。

### 使用

ES Java Client 把 JSON DSL 映射成强类型 Builder + Lambda 表达式。主要提供了以下操作：

#### 索引操作

#### `CreateIndexRequest` 创建索引

```java
client.indices().create(c -> c
    .index("order")
    .mappings(m -> m
        .properties("status", p -> p.integer(i -> i))
        .properties("title",  p -> p.text(t -> t))
        .properties("createTime", p -> p.date(d -> d))
    )
    .settings(s -> s
        .numberOfShards("3")
        .numberOfReplicas("1")
    )
);
```

该操作很形象，和 JSON 操作一一对应。

#### 删除索引

```java
// 删除单个索引
client.indices().delete(d -> d.index("order"));
// 删除多个
client.indices().delete(d -> d.index("order_v1", "order_v2"));
// 或者通配符
client.indices().delete(d -> d.index("order_*"));
```

执行结束后会有返回值 `DeleteIndexResponse`，用于确认是否删除。

```java
boolean acknowledged = response.acknowledged();
```

#### `ExistsRequest` 判断索引是否存在

```java
boolean exists = client.indices().exists(e -> e.index("order")).value();
```

#### `PutmappingRequest` 更新 mapping 为 index 新增字段

```java
client.indices().putmapping(p -> p
    .index("order")
    .properties("newField", pr -> pr.keyword(k -> k))
);
```

在 ES 客户端中，`indices()` 是索引级别的操作命名空间，用于管理索引的生命周期和结构，例如创建索引、更新 mapping、设置别名等；而文档的 CRUD 和查询操作则位于客户端的其他 API 中，这是对 ES REST 层资源层级的直接映射。

#### 文档操作

#### `IndexRequest`

```java
client.index(i -> i
    .index("order")
    .id("1")
    .document(orderDoc)
);
```

其中 `index("order")` 指定的是文档名；`id("1")` 指定了 `_id` 文档 id；`documnet(orderDoc)` 指定的是 `_source`，`orderDoc`  是内容，它会被序列化为 JSON

#### `UpdateRequest`

```java
client.update(u -> u
        .index("order")
        .id("1")
        .doc(Map.of("status", 2))
        .retryOnConflict(3)
        .docAsUpsert(true),
    OrderDoc.class
);
```

`doc(Map.of())` 传入的是要更新的局部字段；`docAsUpsert(ture)` 代表如果该文档不存在则插入该文档；`retryOnConflict()` 用于并发冲突。

#### `DeleteRequest`

```java
client.delete(d -> d.index("order").id("1"));
```

删除指定文档。

#### `GetRequest`

```java
var r = client.get(g -> g.index("order").id("1"), OrderDoc.class);
OrderDoc doc = r.source();
```

按 `_id` 获取指定文档

#### `BulkRequest` 批量操作

```java
BulkResponse resp = client.bulk(b -> {
    for (OrderDoc doc : docs) {
        b.operations(op -> op
            .index(i -> i.index("order").id(doc.getId()).document(doc))
        );
    }
    return b;
});
```

Bulk 的一次请求中包含多条 index/update/delete。执行完之后，我们必须检查执行结果

```java
if (resp.errors()) {
    for (var item : resp.items()) {
        if (item.error() != null) {
            // item.id(), item.error().type(), item.error().reason()
        }
    }
}
```

`BulkOperation` 是 Bulk 中的单条动作抽象。

#### 查询 / 搜索

#### `SearchRequest` 

```java
SearchResponse<OrderDoc> resp = client.search(s -> s
        .index("order")
        .query(q -> q.bool(b -> b
            .filter(f -> f.term(t -> t.field("status").value(1)))
            .must(m -> m.match(mm -> mm.field("title").query("java")))
        ))
        .sort(so -> so.field(f -> f.field("createTime").order(co.elastic.clients.elasticsearch._types.SortOrder.Desc)))
        .from(0)
        .size(10),
    OrderDoc.class
);
```

`SearchResponse` 是结果的包装，我们可以从中读取想要的文档

```java
for (var hit : resp.hits().hits()) {
    OrderDoc doc = hit.source();
    String id = hit.id();
}
```

#### `ScrollRequest` 全量拉取导出

首次导出

```java
SearchResponse<OrderDoc> first = client.search(s -> s
        .index("order")
        .size(1000)
        .scroll(sc -> sc.time("1m")),
    OrderDoc.class
);
String scrollId = first.scrollId();
```

根据上次的快照 id，继续从当前快照导出

```java
var next = client.scroll(sc -> sc
        .scrollId(scrollId)
        .scroll(t -> t.time("1m")),
    OrderDoc.class
);
```

使用完需要 `ClearScrollRequest` 释放 scroll 上下文

```java
client.clearScroll(c -> c.scrollId(scrollId));
```

#### 批处理 / 服务器端任务

#### `ReindexRequest` 服务器端重建，迁移索引数据

```java
client.reindex(r -> r
    .source(s -> s.index("order_v1"))
    .dest(d -> d.index("order_v2"))
);
```

将 `source` 中的索引内容导到 `dest` 的索引中。

ES 在 `reindex` 迁移过程中不会自动进行字段类型转换，它只是读取旧索引的 `_source` 并按新索引的 mapping 重新解析；如果需要类型变更，必须通过脚本显式完成转换，否则会出现失败或不可预期的结果。

如果我们想不停机完成索引迁移，可以使用别名。

首先当前业务中使用的索引名就是事先规定好的别名。然后使用如下命令，让别名指向真正的物理索引名。让客户端可以正常访问。

```java
client.indices().putAlias(a -> a
    .index("order_v1")
    .name("order")
);
```

接着执行迁移

```java
client.reindex(r -> r
    .source(s -> s.index("order_v1"))
    .dest(d -> d.index("order_v2"))
);
```

最后切换别名

```java
client.indices().updateAliases(a -> a
    .actions(act -> act
        .remove(r -> r
            .index("order_v1")
            .alias("order")
        )
    )
    .actions(act -> act
        .add(ad -> ad
            .index("order_v2")
            .alias("order")
        )
    )
);
```

新索引稳定后可以选择清理旧索引

```java
client.indices().delete(d -> d.index("order_v1"));
```

这很像 MySQL 中的动态切换表名。

**这就是 ES 提供的索引级操作 `UpdateAliasesRequest`。**

在 ES 中，`reindex` 负责数据迁移，而 `alias` 负责流量切换；标准做法是先通过 `reindex` 将数据从旧索引复制到新索引，再通过原子性的 `alias` 更新操作将业务访问从旧索引切换到新索引，从而实现零停机索引迁移。

#### `UpdateByQueryRequest` 按 query 批量更新

```java
client.updateByQuery(u -> u
    .index("order")
    .query(q -> q.term(t -> t.field("status").value(0)))
    .script(s -> s.inline(i -> i.source("ctx._source.status = 1")))
);
```

#### `DeleteByQueryRequest` 按 query 批量删除

```java
client.deleteByQuery(d -> d
    .index("order")
    .query(q -> q.range(r -> r.field("createTime").lt(v -> v.stringValue("2024-01-01"))))
);
```

#### 聚合 / DSL

- `Query`
- `Aggregation`
- `SortOptions` 排序
- `Script` 脚本
- `FieldValue` `term\terms` 的等值封装

一个完整的查询操作

```java
SearchResponse<OrderDoc> response = client.search(s -> s
        .index("order")
        .query(q -> q
            .bool(b -> b
                .filter(f -> f.terms(t -> t
                    .field("status")
                    .terms(ts -> ts.value(List.of(
                        FieldValue.of(1),
                        FieldValue.of(2)
                    )))
                ))
            )
        )
        .aggregations("by_category", a -> a
            .terms(t -> t.field("category"))
            .aggregations("total_amount", aa -> aa.sum(su -> su.field("amount")))
        )
        .sort(so -> so.field(f -> f.field("createTime").order(SortOrder.Desc)))
        .size(0),
    OrderDoc.class
);

```

从相应中拿出命中的文档

```java
List<Hit<OrderDoc>> hits = response.hits().hits();
```

处理聚合结果

```java
// 返回不同聚合操作
Map<String, Aggregate> aggs = response.aggregations();
// 取出指定的聚合
TermsAggregate byCategory = aggs.get("by_category").terms();
// 遍历该聚合生成的桶
for (TermsBucket bucket : byCategory.buckets().array()) {
    String key = bucket.key().stringValue();
    long docCount = bucket.docCount();
}
// 取每个桶的子聚合
double totalAmount =
    bucket.aggregations()
          .get("total_amount")
          .sum()
          .value();
```

#### 异步

ES 官方提供了可以执行异步操作的客户端 `ElasticsearchAsyncClient`。用于执行并行批处理、IO 密集型、吞吐优化等场景的任务。

当使用 ES 异步客户端时，客户端操作和同步一致，只不过异步的返回值变成了 `CompletableFuture`

```java
CompletableFuture<SearchResponse<OrderDoc>> future =
    asyncClient.search(s -> s
        .index("order")
        .query(q -> q.term(t -> t.field("status").value(1))),
    OrderDoc.class
);
```

处理返回值

```java
future.thenAccept(resp -> {
    // 和同步 resp 的用法一模一样
    resp.hits().hits().forEach(hit -> {
        OrderDoc doc = hit.source();
    });
});
```

下面给出一个测试案例：

```java
@SpringBootTest
public class ESTest {

    @Autowired
    private ElasticsearchClient elasticsearchClient;

    String indexName = "cartoons";

    @Test
    public void createIndex() throws IOException {

        boolean exists = elasticsearchClient.indices()
                .exists(e -> e.index(indexName))
                .value();

        if (!exists) {
            elasticsearchClient.indices().create(c -> c
                    .index(indexName)
                    .mappings(m -> m
                            .properties("id", p -> p.keyword(k -> k))
                            .properties("personName", p -> p.text(t -> t))
                            .properties("compositionName", p -> p.text(t -> t))
                    )
            );
        }
    }

    @Test
    public void bulkInsert() throws IOException {
        List<CartoonDoc> cartoonDocs = List.of(
                new CartoonDoc("1", "雪之下雪乃", "《我的青春物语果然后问题》"),
                new CartoonDoc("2", "牧濑红莉栖", "《命运石之门》")
        );
        BulkRequest.Builder builder = new BulkRequest.Builder();
        for (CartoonDoc cartoonDoc : cartoonDocs) {
            builder.operations(op -> op
                    .index(idx -> idx
                            .index("cartoons")
                            .id(cartoonDoc.getId())
                            .document(cartoonDoc)
                    )
            );
        }
        BulkResponse bulk = elasticsearchClient.bulk(builder.build());
        // 检查是否有失败
        if (bulk.errors()) {
            for (BulkResponseItem item : bulk.items()) {
                if (item.error() != null) {
                    System.out.println(item.error());
                }
            }
        }
    }

    @Test
    public void search() throws IOException {
        SearchResponse<CartoonDoc> response = elasticsearchClient.search(s -> s
                        .index(indexName)
                        .query(q -> q
                                .bool(b -> b
                                        .filter(f -> f
                                                .match(m -> m
                                                        .field("personName")
                                                        .query("我永远喜欢雪之下雪乃")
                                                )
                                        )
                                )
                        )
                        .size(5),
                CartoonDoc.class
        );
        List<CartoonDoc> list = response.hits().hits().stream()
                .map(Hit::source)
                .toList();
        for (CartoonDoc cartoonDoc : list) {
            System.out.println(cartoonDoc);
        }
    }
}
```

参考：

**https://blog.csdn.net/w1014074794/article/details/120523550**

**https://www.jianshu.com/p/70d1c3045c11**

**https://www.cnblogs.com/buchizicai/p/17093719.html**



