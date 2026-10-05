+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '文档图与 LightRAG：图数据库的一种可选应用'
+++

本章是可选内容。前面三章已经构成完整的图数据库入门；即使从不使用大语言模型，也完全可以学习和运用 Neo4j。这里讨论一种常见应用：从文档中抽取实体和关系，再让问答或检索系统沿着证据图寻找上下文。LightRAG 是这一思路的一种实现，不是图数据库，也不替代数据治理。

## 为什么文档问答会用到图

普通关键词或向量检索擅长找“与问题相似的段落”。但一些问题要求跨段落连接事实，例如“某产品受哪些政策影响，而这些政策又由哪些部门发布”。**文档图**把段落、实体、关系和来源连接起来，让系统能沿边扩展候选证据。

这不意味着图一定更好。问题只问一个明确事实、文档量很小、或抽取质量无法保证时，直接检索原文通常更简单可靠。图的代价是抽取、消歧、更新和错误传播。

## 先建立不依赖模型的证据图

我们用三段人工确认的文本，先做一个可审计的最小实验。节点 `Chunk` 是原始片段，节点 `Entity` 是提到的实体；关系 `MENTIONS` 表示“片段提到实体”，`RELATED_TO` 表示经过审核的实体关系。

```cypher
CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT entity_key IF NOT EXISTS
FOR (e:Entity) REQUIRE e.key IS UNIQUE;

MERGE (c1:Chunk {id: 'doc-1#p1'})
SET c1.text = '北辰公司在 2025 年发布了 Aurora 产品。',
    c1.source = 'sample-document', c1.page = 1
MERGE (c2:Chunk {id: 'doc-1#p2'})
SET c2.text = 'Aurora 产品采用 Orion 平台。',
    c2.source = 'sample-document', c2.page = 2
MERGE (company:Entity {key: 'company:beichen'}) SET company.name = '北辰公司'
MERGE (product:Entity {key: 'product:aurora'}) SET product.name = 'Aurora'
MERGE (platform:Entity {key: 'platform:orion'}) SET platform.name = 'Orion'
MERGE (c1)-[:MENTIONS]->(company)
MERGE (c1)-[:MENTIONS]->(product)
MERGE (c2)-[:MENTIONS]->(product)
MERGE (c2)-[:MENTIONS]->(platform)
MERGE (product)-[r:USES {sourceChunk: 'doc-1#p2'}]->(platform)
MERGE (company)-[p:PUBLISHED {sourceChunk: 'doc-1#p1'}]->(product);
```

预期图中每条实体关系都有 `sourceChunk`，所以它能回到原文证据。验证“北辰公司发布的产品用了什么平台”：

```cypher
MATCH (company:Entity {key: 'company:beichen'})-[:PUBLISHED]->(product)-[:USES]->(platform)
MATCH (chunk:Chunk)-[:MENTIONS]->(platform)
RETURN company.name, product.name, platform.name, chunk.id, chunk.text;
```

预期返回 Aurora、Orion 和第二段文本。最后一段 `MATCH` 很重要：答案中的关系不能脱离可展示的来源。

## 文档到图的通用流水线

无论是否采用 LightRAG 或其他库，可靠流程都可分成以下步骤：

1. **切分（chunking）**：保留文档 ID、页码、标题、字符范围；不能只留下纯文本。
2. **候选抽取**：模型或规则提出实体和关系，并附上原句、置信度和模型版本。
3. **规范化与消歧**：把“Orion 平台”“Orion”判断为同一实体或不同实体；不确定时保留候选，不能强行合并。
4. **审核与写入**：只有通过规则或人工门槛的断言成为可用事实；关系记录来源片段。
5. **查询与回链**：先找到实体或片段，再沿有限跳数扩展，最终返回原文证据。

**幻觉**在这里指模型生成了原文没有支持的实体或关系。图不会自动消除幻觉；一旦把错误断言写入图，它反而可能在多跳查询中放大错误。因此“来源关系”和抽取版本是最低要求。

## LightRAG 放在什么位置

LightRAG 一类工具通常把文档解析、实体关系抽取、向量检索和图检索封装起来。它适合原型验证，因为能减少胶水代码；但开始前仍应明确四件事：底层图数据库和索引在哪里、抽取结果的 schema 是什么、如何保存来源、如何删除或重新处理某一文档。

一个安全的接入方式是先在独立测试库导入少量文档，再用 Cypher 检查节点、关系、来源字段和重复率。不要一开始就把未经审查的整套内部文档喂给工具，更不要把模型生成的关系直接作为权限、合规或财务事实。

## 查询时怎样避免“图扩张”

用户问题可先定位一到多个实体，再沿指定关系类型扩展一到两跳，并对候选按来源质量、时间或文本相关性排序。绝不要从一个模糊名称开始无边界遍历。

```cypher
MATCH path = (e:Entity {key: $entityKey})-[:USES|PUBLISHED*1..2]-(nearby:Entity)
WHERE all(rel IN relationships(path) WHERE rel.sourceChunk IS NOT NULL)
RETURN DISTINCT nearby.name
LIMIT 20;
```

预期返回有限的邻居。这里的 `LIMIT` 只是最后保险；真正的控制仍是稳定实体键、允许的关系类型和最大跳数。

## 常见错误

- **把模型输出当真相。** 将它标为候选断言，保留置信度、原句和审核状态。
- **只有实体没有文本锚点。** 无法解释答案；保存 `Chunk` 和来源关系。
- **同名实体自动合并。** 人名、产品名极易冲突；以稳定键和消歧策略为准。
- **用图代替原文。** 图适合导航和结构化连接，最终回答仍应能引用原文。

## 小结

文档图是图数据库的一个应用，不是其定义。它的价值在于让跨文本连接可查询、可解释；它的风险在于抽取错误和实体混淆。保留来源、限制路径、独立验证，是任何 LightRAG 类实现都绕不开的基础。
