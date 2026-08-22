+++
date = '2025-12-14T20:10:16+08:00'
draft = false
title = 'Elasticsearch Java Client 与 Spring 集成'
+++

这一篇整理 Spring Boot 中使用 Elasticsearch Java Client 的基本方式。它更偏工程落地：如何创建客户端、如何执行索引与文档操作、如何写查询、批处理、聚合和异步调用。

如果还不熟悉 ES 本身的 mapping、文档和 DSL，建议先读 [Elasticsearch基础](./Elasticsearch基础.md) 与 [Elasticsearch查询DSL](./Elasticsearch查询DSL.md)，否则 Java Client 的 Builder 写法只会显得很啰嗦。

## Spring 集成总览

在 Spring 中集成 Elasticsearch 常用的方式有两种：一是使用 Spring Data Elasticsearch，通过 Repository 和注解的方式进行简单的 CRUD 和查询搜索；二是使用官方提供的 Elasticsearch Java Client，直接构建 DSL 查询。前者写法更贴近 Spring 数据访问抽象，后者更贴近 ES 原生 API，复杂搜索和生产调优时通常会更可控。

接下来我们使用 Elasticsearch Java Client 操作 ES。

## 依赖

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

## 配置

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
                        "your-elastic-password"
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

## 使用

ES Java Client 把 JSON DSL 映射成强类型 Builder + Lambda 表达式。主要提供了以下操作：

### 索引操作

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

#### `PutMappingRequest` 更新 mapping，为 index 新增字段

```java
client.indices().putMapping(p -> p
    .index("order")
    .properties("newField", pr -> pr.keyword(k -> k))
);
```

在 ES 客户端中，`indices()` 是索引级别的操作命名空间，用于管理索引的生命周期和结构，例如创建索引、更新 mapping、设置别名等；而文档的 CRUD 和查询操作则位于客户端的其他 API 中，这是对 ES REST 层资源层级的直接映射。

### 文档操作

#### `IndexRequest`

```java
client.index(i -> i
    .index("order")
    .id("1")
    .document(orderDoc)
);
```

其中 `index("order")` 指定的是索引名；`id("1")` 指定了 `_id` 文档 id；`document(orderDoc)` 指定的是 `_source`，`orderDoc` 是内容，它会被序列化为 JSON。

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

`doc(Map.of())` 传入的是要更新的局部字段；`docAsUpsert(true)` 代表如果该文档不存在则插入该文档；`retryOnConflict()` 用于并发冲突。

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

### 查询 / 搜索

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

### 批处理 / 服务器端任务

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

### 聚合 / DSL

- `Query`
- `Aggregation`
- `SortOptions` 排序
- `Script` 脚本
- `FieldValue`：`term` / `terms` 的等值封装

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

从响应中拿出命中的文档。

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

### 异步

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

### 测试案例

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
                new CartoonDoc("1", "雪之下雪乃", "《我的青春恋爱物语果然有问题》"),
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


## 小结

- Spring Data Elasticsearch 适合简单 CRUD；复杂查询和生产搜索更推荐官方 Elasticsearch Java Client。
- ES 8.x 默认启用 HTTPS 与认证，本地开发可以临时信任自签名证书，生产环境应导入 CA 证书。
- Java Client 的 Builder 基本对应 REST DSL，理解 DSL 后再写 Java 代码会轻松很多。
- Bulk、Reindex、Update By Query、Delete By Query 都必须关注失败项、幂等性和任务执行成本。

## 参考

- https://blog.csdn.net/w1014074794/article/details/120523550
- https://www.jianshu.com/p/70d1c3045c11
- https://www.cnblogs.com/buchizicai/p/17093719.html
