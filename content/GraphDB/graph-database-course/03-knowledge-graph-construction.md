+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '图数据摄取与治理：稳定标识、幂等导入、时间与来源'
+++

图数据库最常见的事故不是查询语法错，而是导入半年后发现同一个人有五个节点、关系没有来源、无法判断一条事实何时失效。本章讲通用的摄取原则；它既适用于业务图，也适用于知识图谱。

## 导入前先定义“事实”

一条图事实至少应回答：它连接谁和谁？关系类型是什么？稳定标识是什么？来自哪里？何时生效？这里的**稳定标识**是源系统可重复提供的唯一键，例如 `customer-42`，不是显示名称，也不是 Neo4j 内部 ID。

例如“用户 p-001 在某日加入小组 c-book”可写成：

```text
主体：Person(id='p-001')
关系：JOINED
客体：Club(id='c-book')
关系属性：at、source、observedAt
```

**来源（provenance）**记录事实从哪个文件、系统或人工流程而来；**观测时间**记录系统何时看到它。来源不是可有可无的备注，它决定数据冲突时你能否追查和修正。

## 一个可重复运行的 CSV 实验

先建立两个 CSV 文件。为避免依赖本机路径，本节直接在 Browser 使用参数数组模拟 CSV 行；实际 CSV 导入时同样遵循这个模式。

```cypher
UNWIND [
  {id: 'p-003', name: '小周'},
  {id: 'p-004', name: '小陈'}
] AS row
MERGE (p:Person {id: row.id})
SET p.name = row.name,
    p.updatedAt = datetime()
RETURN count(p) AS processed;
```

预期 `processed` 为 2。重复执行后，检查节点总数只增加第一次的两个：

```cypher
MATCH (p:Person) RETURN p.id, p.name ORDER BY p.id;
```

这就是**幂等（idempotent）**：同一批输入执行一次或多次，最终状态相同。`MERGE` 中只放稳定键，其他可变字段用 `SET` 更新，是实现幂等的基本方法。

接着导入关系：

```cypher
UNWIND [
  {personId: 'p-003', clubId: 'c-book', joined: '2026-02-01', source: 'membership-export-v1'},
  {personId: 'p-004', clubId: 'c-film', joined: '2026-02-03', source: 'membership-export-v1'}
] AS row
MATCH (p:Person {id: row.personId})
MATCH (c:Club {id: row.clubId})
MERGE (p)-[r:JOINED]->(c)
SET r.at = date(row.joined), r.source = row.source, r.observedAt = datetime()
RETURN count(r) AS processed;
```

预期返回 2。若为 0，先检查端点是否存在；不要为了“导入成功”把不存在的 ID 悄悄创建为节点。

## 从文件导入时的安全做法

`LOAD CSV` 可由 Neo4j 读取允许位置的 CSV，但路径权限、编码、分隔符和换行都可能成为问题。先用小文件验证字段和计数，再批量导入；大型导入分批提交，保留批次号和源文件校验和。生产环境中，应用通过官方驱动以参数化批次 `UNWIND $rows` 写入往往更容易控制重试和审计。

无论使用 CSV、JSON、消息流还是关系库同步，顺序都相同：验证输入 → 先写节点 → 再写关系 → 检查计数与孤儿节点 → 记录批次结果。不要把“成功返回”误当成“内容正确”。

## 时间不是一个 `updatedAt` 就够了

**有效时间（valid time）**是事实在现实世界生效的时间，例如成员资格从何时到何时；**事务/观测时间**是数据库何时保存或看到它。二者可能不同：今天补录去年的合同，不代表合同今天才生效。

对需要追溯的关系，可保存 `validFrom`、`validTo`、`observedAt`；查询某日仍有效的关系：

```cypher
MATCH (p:Person)-[r:JOINED]->(c:Club)
WHERE r.validFrom <= date('2026-03-01')
  AND (r.validTo IS NULL OR r.validTo > date('2026-03-01'))
RETURN p.name, c.name;
```

预期只返回该日有效的成员关系。时间模型应在第一版就确定；事后从覆盖式更新恢复历史通常很困难。

## 冲突、消歧和质量检查

**实体消歧**是判断两个名称是否指同一个现实对象。例如“张伟”不能仅凭名字合并；需要可信外部 ID、附加证据或人工审核。错误合并会制造虚假的路径，风险通常大于暂时重复。

每次导入后至少运行三类检查：

```cypher
// 重复业务键应为零（约束启用前尤其重要）
MATCH (p:Person) WITH p.id AS id, count(*) AS n
WHERE n > 1 RETURN id, n;

// 找出没有任何关系的节点，判断是否符合预期
MATCH (n) WHERE NOT (n)--() RETURN labels(n), count(*) AS isolated;

// 检查关系端点类型
MATCH (:Person)-[r:JOINED]->(x)
WHERE NOT x:Club RETURN r, x;
```

预期前两类异常在这组小数据里为零或可解释。将这些断言写入导入任务，而不是靠人工偶尔打开 Browser 看一眼。

## 常见错误

- **用名称作为唯一键。** 名称会修改、重复、语言不同；保留稳定 ID。
- **关系没有来源。** 数据错后无法判断删谁、信谁；至少记录来源和批次。
- **全量同步直接删除。** 先计算差异、保留删除事件和恢复窗口。
- **大事务一次写完。** 失败难重试、事务日志压力大；分批并记录进度。

## 小结

可靠图谱来自可靠摄取：稳定键让写入幂等，来源与时间让事实可追溯，质量断言让错误尽早暴露。下一章会把这些原则放到一个可选的文档图应用中，但不会改变它们的通用性。
