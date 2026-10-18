+++
date = '2025-12-14T20:09:16+08:00'
draft = false
title = 'Elasticsearch聚合查询'
+++

这一篇专门整理 Elasticsearch 的聚合查询。聚合适合做统计分析、分组计数、区间分布、趋势报表和二次指标计算；如果只是返回命中文档本身，应优先看 [Elasticsearch查询DSL](./Elasticsearch查询DSL.md)。

聚合不是另一种搜索结果展示方式，而是在查询命中的文档集合之上执行统计。理解这一点，就不会把 `hits`、`aggs` 和 `_score` 混在一起。

## 聚合查询总览

在 ES 中，一次 `_search` 请求中有两条平行流水线。

1. 查数据
2. 做统计

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

ES 的三大类聚合：

- Bucket：分桶。类似 SQL：`GROUP BY`

- Metric：指标，用于统计值。类似 SQL：`count / sum / avg / max`

- Pipeline：管道，对聚合结果再计算。类似 SQL：`having / 二次计算`

## Bucket

### `terms`

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

### `date_histogram`

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

### `range`

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

可以看到，`range` 操作将一组数据分割成了多个不同的区间。`to` 是上限区间；`from:to` 是双边区间；`from` 是下限区间。

### `histogram`

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

### `filter`

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

## Metric

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

上面操作返回的结果为：

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

## Pipeline

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

### `bucket_selector`

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

在 `bucket_selector` 中返回 boolean，起到过滤作用。

```json
"bucket_selector": {
  "buckets_path": {
    "cnt": "_count"
  },
  "script": "params.cnt > 100"
}
```

如果返回 `true` 保留桶；`false` 丢弃桶。

### `bucket_script`

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

### `bucket_sort`

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


## 小结

- Bucket 聚合负责建桶，典型代表是 `terms`、`date_histogram`、`range`、`histogram`、`filter`。
- Metric 聚合负责在桶内计算指标，常见指标包括 `sum`、`avg`、`min`、`max`、`cardinality`、`stats`。
- Pipeline 聚合不直接看文档，而是基于已经产生的桶或指标继续计算。
- 聚合查询常配合 `size: 0` 使用，只返回统计结果，不返回命中文档。
