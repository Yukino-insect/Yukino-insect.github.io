+++
date = '2025-12-14T20:07:16+08:00'
draft = false
title = 'Elasticsearch基础'
+++

最近找实习面试被面试官拷打了 ES，所以补一下这块的知识。

在我的认知里，ES 主要用于电商项目或日志处理中，为用户提供强大的搜索服务。

这篇文章只保留入门阶段最应该先理解的内容：基础概念、分词器、mapping、索引库操作和文档写入。查询、聚合和 Spring 集成已经拆到独立文章里，否则这篇会长得像一份不太体面的复习提纲。

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

## 分词器

分词器是 ES 的核心，它只在文本被分析的阶段使用。这个阶段主要发生在倒排索引构建阶段和查询文本的解析阶段。但是ES 默认提供的分词器对中文支持不友好，所以我们需要配置 IK 分词器作为中文分词器。

请自行搜索如何下载安装 IK 分词器。

我们在创建索引时显式指定 IK 分词器。

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

为什么搜索和写入需要配置两个模式？**主要是因为 ES 在写入文档时会使用 `analyzer` 分词，并在 refresh 后由 Lucene segment 生成倒排索引；搜索时，查询文本会被 `search_analyzer` 分词，再通过词项去查倒排索引。**

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

## Mapping 与基础 DSL

ES 对外提供了 RESTful API，而查询条件是通过 JSON 格式的 DSL 来描述的。

### 索引库操作

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

### `dynamic`

```json
"dynamic": true | false | "strict"
```

- `true` 的行为是，当写入未知字段时，自动推断字段类型，然后自动将该字段加入 mapping。

- `false` 代表，未定义字段是不进入 mapping，但原始字段和值仍然写进 `_source`，但是不可以搜索、排序聚合。

- `strict` 的行为是当出现未定义字段时，直接拒绝写入，返回错误。这样可以防止脏数据，防止 mapping 被污染，它可以定义在全局，也可以定义在字段局部。

`dynamic` 是 ES 中控制未定义字段写入行为的全局或局部策略，用来决定是否自动生成 mapping、是否忽略字段或直接拒绝写入，是 mapping 的第一道约束门。

### `properties`

字段级约束有哪些：

类型约束 `type` 它是最根本的约束，它决定了字段底层使用哪种 Lucene Field 以及是否支持分词，是否支持排序聚合，使用哪种存储结构。常见的类型约束有：

type：字段数据类型，常见的简单类型有：

- 字符串：**text**（可分词的文本）、**keyword**（不可分词）

- 数值：long、integer、short、byte、double、float、

- 布尔：boolean

- 日期：date

- 对象：object

### `fields`

 `fields` 是在 mapping 阶段定义的索引层概念，用于将同一个字段以多种方式建立索引，从而支持全文检索、精确匹配、排序和聚合等不同查询需求；查询和返回阶段只是对这些索引结构的使用。

### `analyzer`

 定义写入时的分词器，决定文本被如何拆分成 token

### `search_analyzer` 

定义查询时分词器，决定搜索时查询时分词器该如何分词

### `index`

当字段 `index:false` 时，ES 不会为该字段建立倒排索引，字段仍会存入 `_source`，是否还能排序或聚合取决于 `doc_values`，但该字段永远不能用于搜索条件。

### `doc_values`

`doc_values` 用于决定字段是否以列式结构存储，从而支持高效的排序、聚合和脚本取值；在实践中它主要用于不可分词（如 keyword、numeric、date）字段，其本质与是否分词无关，而是与按文档取字段值的访问模式有关。

`doc_values` 之所以能高效取值，是因为它将字段值按 docID 顺序以列式结构存储在磁盘上，并通过 mmap 映射到进程地址空间，使得 ES 可以直接、顺序或近似 O(1) 地按文档访问字段值，而无需反向遍历倒排索引或将数据加载到 JVM 堆中。
 借助列式布局、docID 对齐、OS 页缓存以及高效的编码方式，`doc_values` 成为了排序、聚合和脚本计算性能的根本基础。`doc_values` 本身只是是否启用该结构的配置开关，具体的数据布局与编码策略由 Lucene 内部根据字段类型自动决定。

### `store`

 默认 `_source` 存的是**整条原始 JSON**。返回字段时，先读整个 `_source`，再解析 JSON，得到最终的结果。

`store` 用于决定字段是否以独立的 stored field 形式存储，从而在查询结果中可以不依赖 `_source` 直接返回该字段值；它不参与搜索、排序或聚合，主要用于优化字段取回路径，在 `_source` 很大或被禁用的场景下才有明显价值。

### `null_value` 

当字段为 null 时，可以将 null 值替换成 `null_value` 指定值写入索引

### `ignore_above`

`ignore_above` 常用于 `keyword` 字段，表示当字符串长度超过指定值时，该字段不会被写入索引，也不会进入 `doc_values`。原始值仍然保留在 `_source` 中，但不能通过该字段过滤、排序或聚合。

### `copy_to`

`copy_to` 用于把多个字段的内容复制到一个统一字段中建立索引。常见场景是把 `title`、`subtitle`、`description` 写入一个 `all` 字段，然后对 `all` 做一次 `match`，避免在查询时使用过多字段的 `multi_match`。

### `norms`

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

## 文档操作

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

在新增文档时，推荐显式指定 `_id`。

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

### 批量操作

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


## 延伸阅读

- [Elasticsearch查询DSL](./Elasticsearch查询DSL.md)：整理 `match`、`term`、`bool`、排序、分页、高亮和地理查询。
- [Elasticsearch聚合查询](./Elasticsearch聚合查询.md)：整理 Bucket、Metric 和 Pipeline 聚合。
- [Elasticsearch Java Client 与 Spring 集成](./Elasticsearch%20Java%20Client%20与%20Spring%20集成.md)：整理 Spring Boot 中使用官方 Java Client 的方式。

## 参考

- https://blog.csdn.net/w1014074794/article/details/120523550
- https://www.jianshu.com/p/70d1c3045c11
- https://www.cnblogs.com/buchizicai/p/17093719.html
