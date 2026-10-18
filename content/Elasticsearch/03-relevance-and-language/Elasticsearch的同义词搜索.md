+++
date = '2026-03-17T21:32:33+08:00'
draft = false
title = 'Elasticsearch 的同义词搜索'
+++

同义词搜索要解决的问题是：用户输入的词和文档里的词不完全一样，但含义相近，仍然希望能够搜出来。

例如：

```text
用户搜索：手机
文档标题：移动电话

用户搜索：笔记本
文档标题：Laptop

用户搜索：CRM
文档标题：客户关系管理系统
```

如果只靠普通分词和关键词匹配，这些结果可能召回不足。同义词的作用就是在分析阶段把一个词扩展成一组语义等价或近似的词。

不过同义词不是越多越好。词库设计得粗糙，会导致召回变多但结果变差。搜索系统里，“搜不到”当然不好，“什么都搜得到”也并没有更高明。

## 一、同义词的两种写法

ES 同义词规则常见有两类。

### 1. 等价同义词

```text
手机, 移动电话, cell phone
```

表示三者互相等价：

```text
手机 <-> 移动电话 <-> cell phone
```

用户搜索其中任意一个，都可以扩展到另外几个。

### 2. 定向同义词

```text
苹果手机 => iphone
```

表示只从左边扩展到右边：

```text
苹果手机 -> iphone
```

但不表示：

```text
iphone -> 苹果手机
```

定向同义词适合做归一化，例如品牌别名、缩写、内部术语。

## 二、索引时同义词与搜索时同义词

同义词可以发生在两个阶段：

| 方案 | 发生时间 | 优点 | 缺点 |
| ---- | -------- | ---- | ---- |
| 索引时同义词 | 文档写入 ES 时 | 查询快，DSL 简单 | 词库变更通常要重建索引 |
| 搜索时同义词 | 用户查询时 | 词库变更更灵活，不污染索引 | 查询分析成本更高，召回需要调试 |

### 1. 索引时同义词

写入文档时就把同义词展开进倒排索引。

例如文档：

```text
手机
```

索引时扩展成：

```text
手机
移动电话
cell phone
```

之后用户搜 `cell phone` 也能命中。

问题是：如果同义词词库变了，已经写进倒排索引的旧数据不会自动改变，通常需要 reindex。

### 2. 搜索时同义词

索引时保持文档原始分词，查询时扩展用户输入。

例如用户搜索：

```text
手机
```

查询分析阶段扩展成：

```text
手机 OR 移动电话 OR cell phone
```

这类方案更适合生产系统，因为同义词词库变化频繁，不可能每改一个词就重建索引。

一般建议：

> **优先使用搜索时同义词。只有在词库稳定、查询性能要求极高且能接受重建成本时，才考虑索引时同义词。**

## 三、使用 `synonym_graph`

在搜索时同义词中，推荐优先使用 `synonym_graph`，尤其是包含短语同义词时。

例如：

```text
customer relationship management, crm
```

`synonym_graph` 能更好处理多词短语的 token 图关系。

创建索引示例：

```http
PUT /product_index
{
  "settings": {
    "analysis": {
      "filter": {
        "product_synonym_filter": {
          "type": "synonym_graph",
          "synonyms": [
            "手机, 移动电话, cell phone",
            "电脑, 计算机, pc",
            "客户关系管理, crm"
          ]
        }
      },
      "analyzer": {
        "product_index_analyzer": {
          "tokenizer": "standard",
          "filter": [
            "lowercase"
          ]
        },
        "product_search_analyzer": {
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "product_synonym_filter"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "product_index_analyzer",
        "search_analyzer": "product_search_analyzer"
      }
    }
  }
}
```

关键点：

- `analyzer` 用于索引时分析，不放同义词。
- `search_analyzer` 用于搜索时分析，放同义词。
- 这样词库变更对索引污染更小。

## 四、ES 8.x 同义词 API

较新的 ES 版本提供了同义词 API，可以把同义词集合作为独立资源管理。

创建同义词集合：

```http
PUT /_synonyms/product-synonyms
{
  "synonyms_set": [
    {
      "id": "mobile",
      "synonyms": "手机, 移动电话, cell phone"
    },
    {
      "id": "computer",
      "synonyms": "电脑, 计算机, pc"
    },
    {
      "id": "crm",
      "synonyms": "客户关系管理, crm"
    }
  ]
}
```

在分析器中引用：

```json
{
  "filter": {
    "product_synonym_filter": {
      "type": "synonym_graph",
      "synonyms_set": "product-synonyms",
      "updateable": true
    }
  }
}
```

这种方式的好处：

- 同义词不再硬编码在索引 settings 中。
- 多个索引可以复用同一套同义词集合。
- 词库可以集中管理。
- 更适合做后台维护和审核。

需要注意：具体动态更新行为要结合 ES 版本和 analyzer 类型验证。涉及搜索效果的配置，不要只看文档就直接上生产。至少用 `_analyze` 和回归查询集测一下。

## 五、文件方式维护同义词

除了 API，也可以使用文件方式：

```text
config/analysis/product_synonyms.txt
```

内容：

```text
手机, 移动电话, cell phone
电脑, 计算机, pc
客户关系管理, crm
```

配置：

```json
{
  "filter": {
    "product_synonym_filter": {
      "type": "synonym_graph",
      "synonyms_path": "analysis/product_synonyms.txt"
    }
  }
}
```

文件方式的问题：

- 每个节点都要有同一份文件。
- 发布和回滚要依赖运维流程。
- 容器化环境下要考虑挂载和版本管理。

如果同义词由业务后台频繁维护，API 方式通常更适合。

## 六、如何验证同义词是否生效

使用 `_analyze`：

```http
POST /product_index/_analyze
{
  "analyzer": "product_search_analyzer",
  "text": "手机"
}
```

观察 token 是否包含同义词。

也可以验证短语：

```http
POST /product_index/_analyze
{
  "analyzer": "product_search_analyzer",
  "text": "客户关系管理"
}
```

不要只凭搜索结果猜测同义词是否生效。搜索结果还会受到分词、评分、过滤、排序、文档数据影响，直接看 `_analyze` 才更清楚。

## 七、同义词与评分

同义词扩展会影响召回，也会影响评分。

例如用户搜索：

```text
手机
```

扩展为：

```text
手机 OR 移动电话 OR cell phone
```

可能导致包含 `cell phone` 的英文文档也被召回。问题在于，用户可能更期望中文结果排前面。

常见处理方式：

- 主语言字段 boost 更高。
- 同义词召回字段权重略低。
- exact match 单独加权。
- title 命中高于 description 命中。
- 点击率、转化率参与重排。

示例：

```json
{
  "query": {
    "multi_match": {
      "query": "手机",
      "fields": [
        "title^3",
        "title.synonym^1.5",
        "description"
      ]
    }
  }
}
```

同义词的目标是扩大召回，不是让所有召回结果平起平坐。

## 八、同义词词库怎么设计

同义词词库不是越大越好。设计时要区分几类词：

### 1. 真正等价词

```text
手机, 移动电话
```

这类适合双向同义词。

### 2. 缩写和全称

```text
crm, customer relationship management
```

可以双向，也可以根据业务做定向。

### 3. 品牌别名

```text
apple, 苹果
```

要小心歧义。`苹果` 可能是水果，也可能是品牌。电商里还要结合类目。

### 4. 上下位词

```text
手机, 电子产品
```

这不一定是真同义词。把上下位词当同义词，可能导致召回过宽。

### 5. 错别字和俗称

```text
爱疯, iphone
```

这类可以做定向扩展，但要结合搜索日志验证。

## 九、常见坑

### 1. 把同义词放在索引时，结果频繁重建

词库变更后旧索引不变，只能 reindex。除非词库非常稳定，否则不推荐。

### 2. 同义词过宽

例如：

```text
电脑, 数码, 办公, 设备
```

这会让搜索结果变得非常散。用户搜电脑，不一定想看所有办公设备。

### 3. 忽略多语言

跨语言同义词要结合字段权重和语言识别，否则可能出现用户搜中文却英文结果排满第一页。

### 4. 没有审核流程

业务后台维护同义词时，要有审核、灰度、回滚和日志。一个错误同义词可能影响大量搜索结果。

### 5. 不做效果评估

每次词库变更至少要验证：

- 召回是否增加。
- 前几名结果是否变差。
- 是否引入明显误召回。
- 热门 query 是否受影响。

## 十、推荐实践

生产上可以采用下面的结构：

```text
业务同义词后台
  ↓
审核 / 灰度
  ↓
同义词集合
  ↓
搜索时 analyzer
  ↓
_analyze 验证
  ↓
查询回归评测
  ↓
正式发布
```

索引设计上：

```text
title：原始全文字段
title.keyword：精确匹配 / 排序
title.synonym：同义词召回字段，可降低权重
```

查询时：

```text
exact match 高权重
  +
普通 match 中权重
  +
同义词 match 低权重
  ↓
业务排序和重排
```

## 十一、总结

Elasticsearch 同义词搜索可以这样记：

- 同义词用于解决表达不同但含义接近的召回问题。
- `a, b, c` 是双向同义词，`a => b` 是定向同义词。
- 生产中通常优先使用搜索时同义词，减少 reindex 成本。
- 包含短语同义词时，优先考虑 `synonym_graph`。
- ES 8.x 的同义词 API 更适合集中管理词库。
- 同义词会影响评分，需要配合字段权重和重排。
- 词库必须审核、测试、灰度和回滚。

同义词不是搜索质量的万能药。它更像一把手术刀，用得好能精准补召回，用得粗糙就会把搜索结果切得七零八落。至于哪种更常见，嗯，这个问题就不必回答得太残忍了。
