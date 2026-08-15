+++
date = '2025-10-07T01:51:33+08:00'
draft = false
title = 'Elasticsearch'
+++

elasticsearch 是一个基于 Lucene 的搜索服务器。它提供了一个基于 RESTful web 接口的分布式全文搜索引擎。elasticsearch 是用 Java语言开发的，并作为 Apache 许可条款下的开放源码发布，是一种流行的企业级搜索引擎。可以用来实现搜索、日志统计、分析、系统监控等功能

### elasticsearch 中常用的概念

#### 倒排索引

倒排索引的概念是基于 MySQL 这样的正向索引而言的。

现在有如下表

```markdown
|id|role_name|
--------------
|1 | 雪之下雪乃|
--------------
|2 | 雪之下八幡|
--------------
|3 | 牧濑红莉栖|
--------------
```

如果是根据 id 查询，直接会走索引，查询速度快。但是如果基于 role_name 做模糊查询，只能是逐行扫描数据，流程如下

* 用户搜索数据，条件是 role_name 符合 "%雪之下%"

* 逐行获取数据，比如 id 为1的数据

* 判断数据中的 role_name 是否符合用户搜索条件

* 如果符合则放入结果集，不符合则丢弃。回到步骤1。

逐行扫描，也就是全表扫描，随着数据量增加，其查询效率也会越来越低。当数据量达到数百万时，就是一场灾难。

**而倒排索引** 就不一样了

倒排索引中的几个概念：

- 文档（Document）：搜索的数据，搜索出的每一条数据就是一个文档
- 词条（Term）：对文档数据或用户搜索数据以某种算法分词，得到的具备含义的词语就是词条

创建倒排索引是对正向索引的一种特殊处理。流程如下：

- 将每一个文档的数据利用算法分词，得到一个个词条
- 创建到排索引表，每行数据包括词条，词条所在的文档 id，位置等信息
- 因为词条唯一性，可以给词条创建索引

```markdown
                |id|role_name|            |term |文档id|
                --------------            -------------
                |1 | 雪之下雪乃|            |雪之下| 1 2 |
                --------------    ---->   -------------
                |2 | 雪之下八幡|            | 牧濑 |  3  |
                --------------            --------------
                |3 | 牧濑红莉栖|
                --------------    
                  正向索引                      倒排索引
```

倒排索引的搜索流程如下

- 用户输入条件 “雪之下雪乃” 进行搜索
- 对用户输入的内容分词，得到词条 “雪之下”
- 拿着词条在倒排索引中查找，可以找到包含词条的文档id 1，2
- 拿着文档 id 到正向索引中查找具体文档

虽然要先查询倒排索引，再查询正向索引，但是无论是词条、还是文档id都建立了索引，查询速度非常快！**无需全表扫描。**

#### 我们来对比一下 MySQL 和 elasticsearch

| **MySQL** | **elasticsearch** | **说明**                                                     |
| --------- | ----------------- | ------------------------------------------------------------ |
| Table     | Index             | 索引(index)，就是文档的集合，类似数据库的表(table)           |
| Row       | Document          | 文档（Document），就是一条条的数据，类似数据库中的行（Row），文档都是JSON格式 |
| Column    | Field             | 字段（Field），就是JSON文档中的字段，类似数据库中的列（Column） |
| Schema    | Mapping           | Mapping（映射）是索引中文档的约束，例如字段类型约束。类似数据库的表结构（Schema） |
| SQL       | DSL               | DSL是elasticsearch提供的JSON风格的请求语句，用来操作elasticsearch，实现CRUD |

可以看到

##### Index

索引类似 MySQL 中的表，是相同类型文档的集合

##### mapping

映射就是每类文档的约束信息

而文档 

##### Document

类似 MySQL 中的一行数据，但是文档中的数据是以 json 的格式进行存储的

>  在操作 elasticsearch 的时候，可以配合 kibana 一起使用，它提供了一个 DevTools 界面，用来编写 DSL 操作 elasticSearch

#### 分词器

Elasticsearch 自带的 **默认分词器** 是：

> `standard` analyzer（标准分词器）

它适用于英文、数字等语言，比如：

```markdown
"中华人民共和国" -> ["中华人民共和国"]
"hello world" -> ["hello", "world"]
```

也就是说，它 **不会对中文做有效的分词**，中文会被当成一个整体词。
因此，如果需要中文搜索（尤其是模糊搜索、全文检索），就需要用更智能的分词器。

而 IK 分词器 `IK Analyzer` 是一个第三方的中文分词插件，它可以让 Elasticsearch 正确地把中文文本切分成有意义的词语。

比如：

```markdown
"中华人民共和国国歌"  
- ["中华人民共和国", "中华", "人民", "共和国", "国歌"]
```

IK **不是 Elasticsearch 默认内置的插件**，因此必须手动安装。

#### 索引库的 CRUD

- 创建索引库：PUT /索引库名
- 查询索引库：GET /索引库名
- 删除索引库：DELETE /索引库名
- 修改索引库（添加字段）：PUT /索引库名/_mapping

> PS：倒排索引结构虽然不复杂，但是一旦数据结构改变（比如改变了分词器），就需要重新创建倒排索引。因此索引库 **一旦创建，无法修改mapping**。
>
> 虽然无法修改mapping中已有的字段，但是却 **允许添加新的字段** 到mapping中，因为不会对倒排索引产生影响

#### 文档的 CRUD

- 创建文档：POST /{索引库名}/_doc/文档id
- 查询文档：GET /{索引库名}/_doc/文档id
- 删除文档：DELETE /{索引库名}/_doc/文档id
- 修改文档：
  - 全量修改：PUT /{索引库名}/_doc/文档id
  - 增量修改：POST /{索引库名}/_update/文档id { "doc": {字段}}

这里我们就不详细说了

Java 操作 ElasticSearch 有多种方法，现在我们先来介绍一下 ES 6.x - 7.x 推荐的方法

#### RestHighLevelClient

引入依赖

```xml
<dependency>
    <groupId>org.elasticsearch.client</groupId>
    <artifactId>elasticsearch-rest-high-level-client</artifactId>
    <version>7.17.10</version>
</dependency>
```

在 spring boot 的项目中可以在配置类里创建一个全局可复用的 Bean

```java
@Configuration
public class ElasticSearchConfig {

    @Bean
    public RestHighLevelClient restHighLevelClient() {
        return new RestHighLevelClient(
            RestClient.builder(
                new HttpHost("localhost", 9200, "http")
            )
        );
    }
}
```

新增文档

```java
@Autowired
private RestHighLevelClient client;

public void saveProduct() throws IOException {
    Map<String, Object> jsonMap = new HashMap<>();
    jsonMap.put("id", 1);
    jsonMap.put("name", "华为手机");
    jsonMap.put("price", 4999);

    IndexRequest request = new IndexRequest("product")
            .id("1")
            .source(jsonMap);

    IndexResponse response = client.index(request, RequestOptions.DEFAULT);
    System.out.println(response.getResult());
}
```

查询文档

```java
public void getProduct() throws IOException {
    GetRequest getRequest = new GetRequest("product", "1");
    GetResponse getResponse = client.get(getRequest, RequestOptions.DEFAULT);

    if (getResponse.isExists()) {
        System.out.println(getResponse.getSourceAsString());
    }
}
```

更新文档

```java
public void updateProduct() throws IOException {
    Map<String, Object> updateMap = new HashMap<>();
    updateMap.put("price", 4599);

    UpdateRequest request = new UpdateRequest("product", "1")
            .doc(updateMap);

    UpdateResponse response = client.update(request, RequestOptions.DEFAULT);
    System.out.println(response.getResult());
}
```

> 新增文档和更新文档中的数据源参数 `.source()` 或者 `.doc` 最后保存的文档是 `Json` 格式的，但是可以传入的参数可以是 `Json`，也可以是 `Map` 类型

删除文档

```java
public void deleteProduct() throws IOException {
    DeleteRequest request = new DeleteRequest("product", "1");
    DeleteResponse response = client.delete(request, RequestOptions.DEFAULT);
    System.out.println(response.getResult());
}
```

这个客户端在 ES 8.x+ 之后被标记为 **Deprecated**，转而推荐使用

#### ElasticsearchClient

`ElasticsearchClient` 是 **Elasticsearch 官方 Java API Client (从 8.x 版本开始)**，它取代了之前的 `RestHighLevelClient`，是基于 **Java POJO 与类型安全的请求/响应模型** 的

添加依赖

```xml
<dependency>
    <groupId>co.elastic.clients</groupId>
    <artifactId>elasticsearch-java</artifactId>
    <version>8.12.0</version>
</dependency>
```

创建客户端

```java
public class ESClientFactory {

    public static ElasticsearchClient createClient() {
        RestClient restClient = RestClient.builder(
                new HttpHost("localhost", 9200, "http")).build();

        // 使用 Jackson 映射器
        RestClientTransport transport = new RestClientTransport(
                restClient, new JacksonJsonpMapper());

        return new ElasticsearchClient(transport);
    }
}
```

>`RestClient` 是底层 HTTP 客户端，负责实际请求。
>
>`RestClientTransport` 用来封装传输，支持对象序列化/反序列化。
>
>`ElasticsearchClient` 是高层 API 客户端，通过 Transport 与 Elasticsearch 通信。
>
>`JacksonJsonpMapper` 是JSON 解析器，负责请求和响应的对象映射。
>
>**即 `ElasticsearchClient` 是通过组装底层 HTTP 客户端和传输层，形成的一个完整、类型安全的 Elasticsearch 操作客户端**

新增文档

```java
private final ElasticsearchClient client = ESClientFactory.createClient();

public void addProduct() throws Exception {
    Map<String, Object> product = new HashMap<>();
    product.put("name", "手机");
    product.put("price", 4599);

    IndexResponse response = client.index(i -> i
            .index("product")
            .id("1")
            .document(product)
    );

    System.out.println(response.result());
}
```

查询文档

```java
public void getProduct() throws Exception {
    GetResponse<Map> response = client.get(g -> g
            .index("product")
            .id("1"), Map.class);

    if (response.found()) {
        System.out.println(response.source());
    }
}
```

更新文档

```java
public void updateProduct() throws Exception {
    Map<String, Object> updateMap = new HashMap<>();
    updateMap.put("price", 4999);

    UpdateResponse<Map> response = client.update(u -> u
            .index("product")
            .id("1")
            .doc(updateMap), Map.class);

    System.out.println(response.result());
}

```

除了使用这些客户端直接操作 elasticsearch 之外，还可以使用 spring 封装程度更高的。Spring Data

### spring boot 集成 elasticsearch

添加 maven 依赖

```xml
<dependencies>
    <!-- Spring Boot Elasticsearch -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-elasticsearch</artifactId>
    </dependency>

    <!-- lombok（可选，简化实体类） -->
    <dependency>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok</artifactId>
        <optional>true</optional>
    </dependency>
</dependencies>
```

配置连接信息

```yaml
spring:
  data:
    elasticsearch:
      cluster-nodes: localhost:9200
      username: elastic
      password: your_password   # 如果设置了密码
      repositories:
        enabled: true
```

定义实体类

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Document(indexName = "products")  // 对应 Elasticsearch 的索引名
public class Product {

    @Id
    private String id;

    @Field(type = FieldType.Text, analyzer = "ik_max_word") // 中文分词
    private String name;

    @Field(type = FieldType.Double)
    private Double price;

    @Field(type = FieldType.Keyword)
    private String category;

    @Field(type = FieldType.Date, format = DateFormat.date_hour_minute_second)
    private LocalDateTime createTime;
}
```

创建 Repository

```java
@Repository
public interface ProductRepository extends ElasticsearchRepository<Product, String> {
    // 自定义查询方法（通过命名规则）参照 Spring Data JPA
    List<Product> findByName(String name);
}
```

> `ElasticsearchRepository` 是 Spring Data Elasticsearch 提供的一个 **接口**，它对 Elasticsearch 的基本操作进行了封装，类似于 Spring Data JPA 的 `JpaRepository`。使用它可以免去自己手写大部分 CRUD 代码

编写 service

```java
@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductRepository repository;

    // 新增 / 更新
    public Product save(Product product) {
        product.setCreateTime(LocalDateTime.now());
        return repository.save(product);
    }

    // 批量添加
    public Iterable<Product> saveAll(List<Product> list) {
        return repository.saveAll(list);
    }

    // 查询
    public Optional<Product> findById(String id) {
        return repository.findById(id);
    }

    // 全量查询
    public Iterable<Product> findAll() {
        return repository.findAll();
    }

    // 根据名称搜索
    public List<Product> searchByName(String keyword) {
        return repository.findByName(keyword);
    }

    // 删除
    public void delete(String id) {
        repository.deleteById(id);
    }
}
```

编写 controller

```java
@RestController
@RequestMapping("/es/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService service;

    @PostMapping
    public Product save(@RequestBody Product product) {
        return service.save(product);
    }

    @GetMapping("/{id}")
    public Product findById(@PathVariable String id) {
        return service.findById(id).orElse(null);
    }

    @GetMapping
    public Iterable<Product> findAll() {
        return service.findAll();
    }

    @GetMapping("/search")
    public List<Product> search(@RequestParam String name) {
        return service.searchByName(name);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable String id) {
        service.delete(id);
    }
}
```

接下来讲解一下 **查询** 和 **聚合**

#### 查询（Query）

Elasticsearch 的查询分两大类：**全文查询（Full-Text Query）** 和 **精确值查询（Term/Exact Query）**。

查询 DSL

Elasticsearch 使用 **Query DSL（Domain Specific Language）** 表达查询。基本结构：

```json
GET /index/_search
{
  "query": {
    "match": {
      "field": "value"
    }
  }
}
```

- `query`：表示查询
- `match`：表示全文查询

全文查询（Full-Text Query）

适用于分词后的文本字段：

| 查询类型              | 说明                      |
| --------------------- | ------------------------- |
| `match`               | 匹配单个字段的全文内容    |
| `multi_match`         | 匹配多个字段              |
| `match_phrase`        | 短语查询（保持顺序）      |
| `query_string`        | 支持逻辑运算符（AND, OR） |
| `simple_query_string` | 简化版 `query_string`     |

> ##### `copy_to`
>
>  `copy_to` 是 **Elasticsearch 映射（mapping）中的一个字段属性**，用于 **把一个或多个字段的值“复制”到另一个字段**，方便搜索。
>
> 作用
>
> - 合并多个字段，构建一个 **统一搜索字段**（通常称作 `all` 字段）
> - 不改变原字段内容，只是生成一个新的字段用于搜索
> - 常与 `multi_match` 或 `match` 查询配合使用
>
> 假设有一张书籍索引 `books`：
>
> ```json
> PUT /books
> {
>   "mappings": {
>     "properties": {
>       "title": {
>         "type": "text",
>         "copy_to": "all_text"
>       },
>       "description": {
>         "type": "text",
>         "copy_to": "all_text"
>       },
>       "author": {
>         "type": "text",
>         "copy_to": "all_text"
>       },
>       "all_text": {
>         "type": "text"
>       }
>     }
>   }
> }
> ```
>
> `title`、`description`、`author` 都会把文本复制到 `all_text`，查询 `all_text` 就能匹配三个字段内容，原字段仍可独立搜索

**示例：匹配 title 字段包含 "Elasticsearch 教程"**

```json
GET /books/_search
{
  "query": {
    "match": {
      "title": "Elasticsearch 教程"
    }
  }
}
```

精确查询（Term/Exact Query）

适用于 keyword、数字、日期等精确匹配字段：

| 查询类型 | 说明                     |
| -------- | ------------------------ |
| `term`   | 精确匹配单个值           |
| `terms`  | 精确匹配多个值           |
| `range`  | 范围查询（>、<、>=、<=） |
| `exists` | 判断字段是否存在         |

**示例：查找 price 为 100 的商品**

```json
GET /product/_search
{
  "query": {
    "term": {
      "price": 100
    }
  }
}
```

**示例：查找价格在 100~500 的商品**

```json
GET /product/_search
{
  "query": {
    "range": {
      "price": {
        "gte": 100,
        "lte": 500
      }
    }
  }
}
```

组合查询（Bool Query）

布尔查询允许组合多个子查询：

- `must`：必须匹配（AND）
- `should`：可选匹配（OR）
- `must_not`：必须不匹配（NOT）
- `filter`：过滤（不影响评分）

**示例：查找 title 包含 “Elasticsearch” 并且 price < 500**

```json
GET /product/_search
{
  "query": {
    "bool": {
      "must": {
        "match": {
          "title": "Elasticsearch"
        }
      },
      "filter": {
        "range": {
          "price": {
            "lt": 500
          }
        }
      }
    }
  }
}
```

#### 聚合（Aggregation）

聚合用于 **统计、分析、分组**，类似 SQL 的 `GROUP BY` 和 `COUNT/SUM/AVG`。

聚合类型

桶聚合（Bucket Aggregation）

把文档分组，每个分组叫一个**桶**。常用类型：

| 聚合类型         | 说明                |
| ---------------- | ------------------- |
| `terms`          | 按字段值分组        |
| `range`          | 按数值/日期范围分组 |
| `date_histogram` | 按时间间隔分组      |
| `filters`        | 自定义多个过滤条件  |

**示例：按 category 字段分组**

```json
GET /product/_search
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": {
        "field": "category.keyword"
      }
    }
  }
}
```

指标聚合（Metric Aggregation）

对文档计算数值，如 `count`、`avg`、`sum`、`min`、`max`。

**示例：统计商品价格平均值**

```json
GET /product/_search
{
  "size": 0,
  "aggs": {
    "avg_price": {
      "avg": {
        "field": "price"
      }
    }
  }
}
```

嵌套聚合（Nested Aggregation）

聚合中可以再嵌套聚合，例如先分组再求平均：

**示例：每个 category 的平均价格**

```json
GET /product/_search
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": {
        "field": "category.keyword"
      },
      "aggs": {
        "avg_price": {
          "avg": {
            "field": "price"
          }
        }
      }
    }
  }
}
```

接下来我们看一下使用 `RestHighLevelClient` 如何进行这部分操作

创建客户端

```java
RestHighLevelClient client = new RestHighLevelClient(
    RestClient.builder(new HttpHost("localhost", 9200, "http"))
);

```

Match 查询

```java
SearchRequest searchRequest = new SearchRequest("books");
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();

sourceBuilder.query(QueryBuilders.matchQuery("title", "Elasticsearch 教程"));
searchRequest.source(sourceBuilder);

SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);
response.getHits().forEach(hit -> System.out.println(hit.getSourceAsString()));

```

> `SearchRequest searchRequest = new SearchRequest("books")` 中传入的参数是索引名
>
> `sourceBuilder` 构建的是查询条件
>
> `RequestOptions` 用来封装 HTTP 请求相关的配置，包括：
>
> - **Headers**：自定义请求头，例如 Authorization、TraceId 等。
> - **认证信息**：如果需要 Basic Auth 或 Token，可以通过 RequestOptions 设置。
> - **超时设置**：连接超时、请求超时等。
> - **其他 HTTP 选项**：如压缩、重试策略等。
>
> **`RequestOptions.DEFAULT`** 就是一个默认实例：
>
> - 不带额外 headers
> - 使用客户端默认的认证和超时
> - 一般大多数场景都可以直接用

Multi-Match 查询

```java
sourceBuilder.query(QueryBuilders.multiMatchQuery(
        "Elasticsearch 教程",
        "title", "description", "author"
));
```

Aggregation（聚合）

Terms 聚合（按字段分组）

```java
TermsAggregationBuilder aggregation = AggregationBuilders
        .terms("author_count")
        .field("author.keyword");

sourceBuilder.aggregation(aggregation);

SearchResponse aggResponse = client.search(searchRequest, RequestOptions.DEFAULT);
Terms authorTerms = aggResponse.getAggregations().get("author_count");
for (Terms.Bucket bucket : authorTerms.getBuckets()) {
    System.out.println(bucket.getKeyAsString() + " : " + bucket.getDocCount());
}
```

Metrics 聚合（例如求平均）

```java
AvgAggregationBuilder avgAgg = AggregationBuilders
        .avg("avg_price")
        .field("price");

sourceBuilder.aggregation(avgAgg);

SearchResponse metricResp = client.search(searchRequest, RequestOptions.DEFAULT);
Avg avg = metricResp.getAggregations().get("avg_price");
System.out.println("平均价格: " + avg.getValue());
```

使用 `ElasticsearchClient`

创建客户端

```java
RestClient restClient = RestClient.builder(new HttpHost("localhost", 9200)).build();
RestClientTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
ElasticsearchClient client = new ElasticsearchClient(transport);
```

查询操作

```java
SearchResponse<Map> response = client.search(s -> s
        .index("books")
        .query(q -> q
                .match(m -> m
                        .field("title")
                        .query("Elasticsearch 教程")
                )
        ), Map.class
);

response.hits().hits().forEach(hit -> System.out.println(hit.source()));
```

Multi-Match 查询

```java
SearchResponse<Map> multiResponse = client.search(s -> s
        .index("books")
        .query(q -> q
                .multiMatch(m -> m
                        .query("Elasticsearch 教程")
                        .fields("title", "description", "author")
                )
        ), Map.class
);
```

聚合操作

Terms 聚合

```java
SearchResponse<Void> aggResponse = client.search(s -> s
        .index("books")
        .aggregations("author_count", a -> a
                .terms(t -> t.field("author.keyword"))
        ), Void.class
);

aggResponse.aggregations().get("author_count").sterms().buckets().array()
        .forEach(bucket -> System.out.println(bucket.key() + " : " + bucket.docCount()));
```

Avg 聚合

```java
SearchResponse<Void> avgResponse = client.search(s -> s
        .index("books")
        .aggregations("avg_price", a -> a
                .avg(av -> av.field("price"))
        ), Void.class
);

Double avg = avgResponse.aggregations().get("avg_price").avg().value();
System.out.println("平均价格: " + avg);
```

**Spring Data Elasticsearch**（简称 **SDE**）如何在 Spring Boot 项目中进行查询和聚合操作

SDE 封装了 `ElasticsearchOperations` 来进行相关操作

`ElasticsearchOperations` 是 **接口**，定义了所有对 Elasticsearch 的操作方法，包括 CRUD、搜索、聚合等。

`ElasticsearchRestTemplate` 是它的 **默认实现类**，底层使用 `RestHighLevelClient`。

通过注入 `ElasticsearchOperations`，你就可以在项目中统一使用模板方法

注入其中一个类 

```java
@Autowired
private ElasticsearchOperations elasticsearchOperations;
```

使用 `NativeSearchQueryBuilder` 构建查询

```java
NativeSearchQuery searchQuery = new NativeSearchQueryBuilder()
        .withQuery(matchQuery("title", "Elasticsearch"))
        .withPageable(PageRequest.of(0, 10))
        .build();

SearchHits<Product> hits = elasticsearchOperations.search(searchQuery, Product.class);
for (SearchHit<Product> hit : hits) {
    System.out.println(hit.getContent());
}
```

> `Product.class` 对应索引映射的实体类。
>
> 返回值是 `SearchHits<T>`，包含总条数、分页信息和每条命中数据

Spring Data Elasticsearch 提供聚合接口，通过 `AggregationBuilders` 构建聚合条件

```java
NativeSearchQuery searchQuery = new NativeSearchQueryBuilder()
    // terms() 是 分组聚合（Terms Aggregation），作用类似 SQL 的 GROUP BY。
    // "categoryAgg" 是 聚合的名字（aggregation name），用于在返回结果中获取这个聚合数据
        .addAggregation(terms("categoryAgg").field("category.keyword"))
        .addAggregation(avg("avgPrice").field("price"))
        .build();
Aggregations aggregations = elasticsearchOperations.search(searchQuery, Product.class)
        .getAggregations();

Terms categoryAgg = aggregations.get("categoryAgg");
for (Terms.Bucket bucket : categoryAgg.getBuckets()) {
    System.out.println(bucket.getKeyAsString() + ": " + bucket.getDocCount());
}

Avg avgPrice = aggregations.get("avgPrice");
System.out.println("平均价格：" + avgPrice.getValue());
```

嵌套聚合

```java
NativeSearchQuery searchQuery = new NativeSearchQueryBuilder()
        .addAggregation(
            terms("categoryAgg").field("category.keyword")
                .subAggregation(avg("avgPrice").field("price"))
        )
        .build();

Terms categoryAgg = aggregations.get("categoryAgg");
for (Terms.Bucket bucket : categoryAgg.getBuckets()) {
    Avg avgPrice = bucket.getAggregations().get("avgPrice");
    System.out.println(bucket.getKeyAsString() + ": " + avgPrice.getValue());
}
```
