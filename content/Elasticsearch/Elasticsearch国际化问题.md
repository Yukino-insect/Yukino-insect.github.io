+++
date = '2026-03-17T21:33:38+08:00'
draft = false
title = 'Elasticsearch国际化问题'

+++

我就面个实习，面试官询问跨境电商搜索业务。作为只会 CRUD ES 的、人怎么可能会。很自然的被拷打了，现在查阅资料了解一下。

跨境电商里的国际化至少有两类问题，必须分开谈：

1. **站内多语言体验（Language i18n）**
2. **多国家/地区站点本地化（Regionalization）**

> Language i18n 是字段与分词问题，而 Regionalization 是数据模型、索引拓扑、合规与权限问题。

第一类问题主要是为同一个地区的不同用户提供以下服务

- 不同语言的商品信息展示。如标题、属性、类目、品牌名的翻译。
- 使用不同的搜索语言可以匹配到正确的商品。如中文搜索、英文搜索都能命中同样的商品。

而第二类问题面对的问题就不一样了。它主要是**商品数据隔离问题**。不同国家/地区站点的商品集合是不一样的，不同商品集合之间天然存在：

- 可售不同（禁售/授权/类目限制）
- 价格/币种不同（税费、汇率、促销）
- 库存/仓覆盖/时效不同
- 合规不同（法务红线）
- 同一 SPU 在不同站点可能对应不同 SKU 或不同上架条目

因此，市场隔离是跨境电商搜索要面临的首要问题。我们提供的服务需要达到以下跨境搜索的目标：

- **不串货**：中国用户看不到日本可售商品

- **不出错价**：币种/税费/促销不混

- **不违规**：合规禁售必须快速生效

- **可演进**：支持重建索引、灰度、回滚

- **体验本地化**：地区内多语言、排序信号符合本地策略

## 站内多语言体验

在同一地区多语言搜索场景下，搜索服务要完成以下任务：

1. 在业务层实现语言选择。因为 ES 并不识别语言。
2. 用户选择的语言字段在结果排序中要占高权重，符合用于语言预期。
3. 要有其他语言字段低权重兜底，防止因商品数据不完整导致搜索不到目标。
4. 统一返回结果

> 为什么用户使用一种语言搜索，却要聚合返回多种语言的数据呢？
>
> 这种行为被称为**跨语言召回**。主要是因为有些地区的商品内容在多语言环境下往往是不完整，不对称的。跨语言召回主要是为了作为兜底机制，避免因语言差异导致召回的商品内容缺失。实现上通常以用户语言字段为主，其他语言字段低权重补充，既保证体验，又不影响相关性。

ES 层如何存不同语言的数据呢，现提供如下方案。

### 多字段方案

> 最推荐该方案。

在同一个业务字段中使用不同语言分词器建立多个字段。

它的 mapping 设计如下：

```http 
PUT /product_i18n
{
  "settings": {
    "analysis": {
      "analyzer": {
        "ik_zh": {
          "tokenizer": "ik_max_word"
        },
        "en_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "fields": {
          "zh": { "type": "text", "analyzer": "ik_zh" },
          "en": { "type": "text", "analyzer": "en_analyzer" }
        }
      }
    }
  }
}
```

`title` 是整体的业务字段；`title.zh` 是特定语言对应的业务字段内容

写入数据

```http
POST /product_i18n/_doc/1
{
  "title": {
    "zh": "苹果手机",
    "en": "iPhone"
  }
}
```

查询

```http
GET /product_i18n/_search
{
  "query": {
    "match": {
      "title.en": "iphone"
    }
  }
}
```

### 多索引方案

在该方案中，每种语言用一个索引，不同语言之间的内容隔离。但这样会导致很多问题，如：跨语言聚合困难、分页一致性难保证、同一商品需要多次写入、翻译更新需要同步多个索引等。

英文索引：

```http
PUT /product_en
{
  "settings": {
    "analysis": {
      "analyzer": {
        "en_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": { "type": "text", "analyzer": "en_analyzer" },
      "price": { "type": "double" }
    }
  }
}
```

### 语言决策层

现使用多字段方案存储数据，展示一下该方案在 Java 层的职责拆分

```text
HTTP 请求
↓
SearchController
↓
LanguageResolver      ← 决定主语言
↓
QueryBuilder          ← 构建多字段加权查询
↓
ElasticsearchClient   ← 执行查询
↓
ResultAssembler       ← 结果返回
```

从请求中解析用户选择的语言，该语言属于用户意图。

```java
public class LanguageResolver {

    public static Lang resolve(HttpServletRequest request) {
        String header = request.getHeader("Accept-Language");
        if (header == null) {
            return Lang.EN; // 默认语言
        }
        return header.startsWith("zh") ? Lang.ZH : Lang.EN;
    }
}
```

提前构造好语言权重

```java
public class SearchFieldConfig {

    public static Map<Lang, Map<String, Float>> fieldBoosts() {
        Map<String, Float> zhBoost = Map.of(
                "title.zh", 3.0f,
                "title.en", 1.0f
        );

        Map<String, Float> enBoost = Map.of(
                "title.en", 3.0f,
                "title.zh", 1.0f
        );

        return Map.of(
                Lang.ZH, zhBoost,
                Lang.EN, enBoost
        );
    }
}
```

每种配置，主语言 boost 要高，满足用户预期，其他语言 boost 低，只保证最后的召回完整。

构建查询

```java
public class QueryBuilder {

    public static Query buildMultiLangQuery(String keyword, Lang lang) {
        Map<String, Float> boosts =
                SearchFieldConfig.fieldBoosts().get(lang);

        return Query.of(q -> q
            .multiMatch(mm -> {
                mm.query(keyword);
                boosts.forEach((field, boost) ->
                        mm.fields(field + "^" + boost)
                );
                return mm;
            })
        );
    }
}
```

执行搜索

```java
public class SearchService {

    private final ElasticsearchClient client;

    public SearchService(ElasticsearchClient client) {
        this.client = client;
    }

    public SearchResponse<ProductDoc> search(
            String index,
            String keyword,
            HttpServletRequest request) throws IOException {

        Lang lang = LanguageResolver.resolve(request);

        Query query = QueryBuilder.buildCrossLangQuery(keyword, lang);

        return client.search(s -> s
                .index(index)
                .query(query)
                .size(20),
            ProductDoc.class
        );
    }
}
```

## 多国家/地区站点本地化

解决第二类的方案整体上满足**单一搜索平台 + 多地区租户化**。

这里的单一搜索平台是指：统一使用一套搜索服务代码，但是不同地区的数据和信息隔离存储。

### Alias 路由 + 地区索引版本化

该方案比较推荐。它是将不同地区的索引单独存储。然后使用 alias 路由，实现无感索引重建。

示例：

索引命名规范

- 真实索引：`product_{region}_v{version}`
- 业务访问：`product_{region}_alias`

例如：

- `product_us_v1`, `product_us_v2`
- `product_us_alias` -> 指向当前版本

mapping

```http
PUT product_us_v1
{
  "settings": {
    "number_of_shards": 3,
    "analysis": {
      "analyzer": {
        "en_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "region": { "type": "keyword" },
      "listing_id": { "type": "keyword" },
      "spu_id": { "type": "keyword" },
      "sku_id": { "type": "keyword" },

      "saleable": { "type": "boolean" },
      "compliance_status": { "type": "keyword" },  
      "category_id": { "type": "keyword" },
      "brand": { "type": "keyword" },

      "currency": { "type": "keyword" },
      "price": { "type": "scaled_float", "scaling_factor": 100 }, 
      "promo_price": { "type": "scaled_float", "scaling_factor": 100 },

      "stock_status": { "type": "keyword" },         
      "eta_days": { "type": "integer" },             

      "title": {
        "type": "text",
        "analyzer": "en_analyzer",
        "fields": {
          "raw": { "type": "keyword" }
        }
      },

      "attrs": {
        "type": "text",
        "analyzer": "en_analyzer"
      },

      "sales_30d": { "type": "integer" },
      "quality_score": { "type": "float" },
      "updated_at": { "type": "date" }
    }
  }
}
```

绑定 alias

```http
POST _aliases
{
  "actions": [
    { "add": { "index": "product_us_v1", "alias": "product_us_alias" } }
  ]
}
```

文档数据

```http
POST product_us_alias/_doc/1
{
  "region": "US",
  "listing_id": "L10001",
  "spu_id": "SPU9",
  "sku_id": "SKU9-US",

  "saleable": true,
  "compliance_status": "PASS",
  "category_id": "phone",
  "brand": "Apple",

  "currency": "USD",
  "price": 69900,
  "promo_price": 64900,

  "stock_status": "IN_STOCK",
  "eta_days": 2,

  "title": "iPhone 15 Pro",
  "attrs": "256GB titanium",

  "sales_30d": 1200,
  "quality_score": 0.86,
  "updated_at": "2025-12-25T00:00:00Z"
}
```

这样在需要重建索引时，只需要构建新版本的 Index，进行 alias 切换，reindex 迁移数据就可以了。

**ES 是如何部署的？**

在提供跨境搜索时，电商大多使用的是单集群 + 多地索引。

为什么是使用一个集群，而不是不同国家维护不同的集群提供服务呢？

原因：

- 搜索是**读密集型**
- 跨地区数据量可控
- alias + index 已能实现强隔离
- 运维成本远低于多集群

什么时候用多集群？

- 数据主权要求（GDPR / 国别法规）
- 数据规模极大（百亿级文档）
- 网络延迟不可接受

**跨境电商的数据库如何设计？**

通常可以在一个数据库中存放按地区划分的表

```text
db_product
 ├── product_listing_us
 ├── product_listing_jp
 ├── product_listing_sg
```

访问时选择正确的表：

```java
String table = "product_listing_" + region;
```

也可以选择分库分表

```text
db_product_us
 └── product_listing

db_product_jp
 └── product_listing

db_product_sg
 └── product_listing
```

### 单集群 + 多索引

该方案和上一个方案的区别就是没有使用 alias

索引按地区拆分，然后由业务层路由

```text
product_us
product_jp
product_sg
```

查询时选择索引

```http
GET product_jp/_search
{ ... }
```

在没有使用 alias 的情况下，数据迁移可能会很麻烦

### 单索引 + region filter

该方案是在同一个索引中存放不同地区的文档数据。查询的时候按地区过滤。它的缺陷比较严重，不推荐使用

```http
GET /product_global/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "title": "iphone" } }
      ],
      "filter": [
        { "term": { "region": "US" } },
        { "term": { "saleable": true } },
        { "term": { "compliance_status": "PASS" } }
      ]
    }
  }
}
```

### 跨境搜索的调用链路

1. **Region 决策层**
   - 域名/站点（us.xxx.com）
   - 用户账号绑定 region
   - IP/Geo 兜底（谨慎，可能误判）
2. **路由层**
   - 选择 `product_{region}_alias`
   - 绑定该地区的检索配置：语言、同义词、排序模板
3. **检索执行层（ES）**
   - 召回：match/multi_match + filters
   - 过滤：合规、可售、类目、品牌黑白名单
4. **排序层**
   - 相关性（文本匹配）
   - 本地信号（热销、转化、时效、库存、价格策略）
5. **展示层**
   - 返回地区币种价格、地区语言字段
   - 高亮使用对应 analyzer 的字段

### 业务层路由代码

Java 伪代码。

region 决策 + alias 路由

```java
public class SearchRouter {

    // region -> alias 映射（也可来自配置中心）
    private static final Map<String, String> REGION_ALIAS = Map.of(
        "US", "product_us_alias",
        "JP", "product_jp_alias",
        "SG", "product_sg_alias"
    );

    public String resolveRegion(HttpServletRequest req, UserProfile user) {
        // 1) 站点/域名优先
        String host = req.getHeader("Host"); // us.xxx.com
        if (host != null && host.startsWith("us.")) return "US";
        if (host != null && host.startsWith("jp.")) return "JP";

        // 2) 登录用户站点
        if (user != null && user.getRegion() != null) return user.getRegion();

        // 3) IP/Geo 兜底（注意误判风险）
        return "US";
    }

    public String resolveIndexAlias(String region) {
        String alias = REGION_ALIAS.get(region);
        if (alias == null) throw new IllegalArgumentException("Unsupported region: " + region);
        return alias;
    }
}
```

构建查询

```java
public SearchRequest buildRequest(String indexAlias, String keyword) {
    return new SearchRequest.Builder()
        .index(indexAlias)
        .query(q -> q.bool(b -> b
            .must(m -> m.multiMatch(mm -> mm
                .query(keyword)
                .fields("title^3", "attrs")
            ))
            .filter(f -> f.term(t -> t.field("saleable").value(true)))
            .filter(f -> f.term(t -> t.field("compliance_status").value("PASS")))
        ))
        .size(20)
        .build();
}
```

整体架构

```text
┌─────────────┐
│  用户请求   │
└─────┬───────┘
      ↓
┌───────────────────┐
│  Region 决策层    │ ← 域名 / IP / 用户站点
└─────┬─────────────┘
      ↓
┌───────────────────┐
│  搜索路由层       │ ← 选 index / alias
└─────┬─────────────┘
      ↓
┌───────────────────┐
│  ES 搜索执行层    │ ← 分词 / 召回 / 排序
└─────┬─────────────┘
      ↓
┌───────────────────┐
│  本地化排序/过滤  │ ← 价格 / 库存 / 合规
└───────────────────┘
```

参考：

**https://juejin.cn/post/7325806646063497242**
