+++
date = '2025-12-14T20:08:16+08:00'
draft = false
title = 'Elasticsearch查询DSL'
+++

这一篇从原来的基础文章中拆出来，专门整理 Elasticsearch 的查询 DSL。基础概念、mapping 和文档写入见 [Elasticsearch基础](./Elasticsearch基础.md)，聚合统计见 [Elasticsearch聚合查询](./Elasticsearch聚合查询.md)。

查询 DSL 可以先按用途分成三类：全文检索负责召回，精确匹配负责过滤，复合查询负责把多个条件组织在一起。排序、分页、高亮和地理查询则属于搜索结果的组织方式。

## 查询 DSL 总览

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

### 全文检索查询

全文检索涉及到**分词**和**相关度**

整个过程是：分词 -> 倒排 -> 算分 -> 排序。

常用的有

#### `match`

```json
{
  "match": {
    "title": "我永远喜欢雪之下雪乃"
  }
}
```

#### `multi_match`

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

### 精确匹配

一般是查找 `keyword`、数值、日期、`boolean` 等类型字段。这些字段不会被分词。

常见的有：

#### `term`

```json
{
  "term": {
    "status": "online"
  }
}
```

#### `terms`

```json
{
  "terms": {
    "status": ["online", "offline"]
  }
}
```

#### `range`

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

#### `exists`

```json
{
  "exists": {
    "field": "email"
  }
}
```

### 复合查询

复合查询主要是将多个查询条件组合起来，控制查询逻辑。

#### bool 查询

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

### 打分

我们上面讲的 bool 查询是涉及打分的。ES 中默认的 `must` 和 `should` 中的条件字段参与打分。

```json
{
  "bool": {
    "must": [ ... ],
    "should": [ ... ]
  }
}
```

同一个查询中，`must` 条件会参与算分；`should` 命中的条件越多，通常分数越高，默认排序也越靠前。

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

通过 `boost` 可以人为调整评分比重。

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

`function_score` 用来在 ES 默认 `_score` 的基础上，按照业务规则重新计算或调整分数。`query` 查询条件和 `functions` 自定义评分函数都放到该层。`query` 决定哪些文档能参与排序；`functions` 决定了评分规则。

`boost` 字段参与的是 ES 默认 BM25 算分过程的权重系数，用于调整不同查询或字段在相关度中的影响力。

`functions` 中的每一个函数，都会在 `filter` 条件满足时，产生一个函数分数，这个分数由 `weight` 决定。所有参与评分的条件都应该放在 `functions` 的 `filter` 字段中，比如 `term`、`must` 甚至 `bool` 的更加复杂的条件。

`score_mode` 用来规定自定义的多个 `function` 算出来的分数如何合计。常见的模式有 `sum` 相加、`multiply` 相乘、`max` 取最大、`min` 取最小、`avg` 取平均。

`boost_mode` 用来规定函数算出来的分数如何和原始 `_score` 合计。常见的模式和 `score_mode` 类似。

**`_score` 评分影响的是默认结果顺序。其结果顺序代表搜索结果的合理程度。但是它不会影响命中、返回字段和过滤结果。**

考虑 `_score` 的场景主要涉及搜索系统，内容推荐等。

### 地理坐标查询 

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

#### `geo_bounding_box`

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

#### `geo_distance`

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

### 排序

ES 的排序分为两大类：

1. 基于 `_score` 的排序，相关性排序，是默认的。
2. 基于字段值的排序，如数值、时间、`keyword`、`geo` 等

当我们显式指定 `sort` 时，结果会按照 `sort` 排序。若查询条件本身需要算分，ES 仍然可能计算 `_score`，只是 `_score` 不再参与最终排序。**需要注意，算分是有性能成本的，在大数据量场景下这部分影响会非常明显。**

那在使用过程中如何减小算分影响呢：

- 使用 `filter`，不用 `match`。`filter` 不参加评分，`match` 则相反。
- 显式声明 `track_scores: false`。ES 不会保留 `_score`，仍然会执行 `match` 的算分逻辑，但不会在排序阶段维护 `_score`。

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

### 分页

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

### 高亮

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


## 小结

- 全文检索主要使用 `match`、`multi_match`，重点是分词和相关度。
- 精确匹配主要使用 `term`、`terms`、`range`、`exists`，适合 `keyword`、数值、日期和布尔字段。
- `bool` 查询负责组合条件，`filter` 不参与算分，适合放结构化筛选条件。
- 排序和深分页会影响性能，深度翻页优先考虑 `search_after`。
- 高亮依赖查询命中和字段位置信息，前端通常优先展示 `highlight`，没有再回退到 `_source`。
