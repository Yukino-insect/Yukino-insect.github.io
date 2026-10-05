+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '关系为什么会变复杂：图模型、Neo4j 与第一次查询'
+++

## 从一张关系表开始

设想一个学习社区：用户能加入多个小组，小组也有许多用户。关系型设计通常是三张表：`user`、`club`、`membership(user_id, club_id, joined_at)`。这没有错；查询“某人加入哪些小组”也很简单。但当问题变成“与阿明共同加入过两个小组的人，又关注了谁”，就会出现多次自连接。SQL 仍可完成，只是连接数量、别名和临时结果会很快掩盖问题本身。

图模型把 `User` 和 `Club` 表达成节点，把 `membership` 表达成关系。它的优势不是少建表，而是沿关系扩展时，查询形状仍接近问题的自然语言。

## 先做建模，而不是先写查询

一个实用规则是：有独立身份、会被其他对象引用、或自身需要描述的东西，优先建成节点；两个对象之间的动作、归属或依赖，优先建成关系。关系有方向，但查询可以选择忽略方向。属性只保存该节点或该关系自身的事实。

本章模型如下：

```text
(:Person {id, name})-[:JOINED {at}]->(:Club {id, name})
(:Person)-[:FOLLOWS]->(:Person)
```

`id` 是稳定业务标识，不要把 Neo4j 内部 ID 当作跨系统主键；内部 ID 可能因导入、恢复而变化。`JOINED.at` 放在关系上，因为“加入时间”描述的是人和小组这次连接。

## 建立约束：先防重复，再导入数据

**唯一约束（uniqueness constraint）**要求一组标签和属性值不重复，同时通常帮助按该键查找。把下面语句粘到 Browser 或 `cypher-shell`：

```cypher
CREATE CONSTRAINT person_id IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT club_id IF NOT EXISTS
FOR (c:Club) REQUIRE c.id IS UNIQUE;
```

预期每条语句返回创建或已存在的确认。执行 `SHOW CONSTRAINTS;` 应能看到两条约束。若数据库提示语法不兼容，先检查你的 Neo4j 大版本；不要为了通过而删掉唯一性要求。

## CREATE、MERGE 与第一批数据

`CREATE` 无条件创建数据，适合确定不存在的新记录；重复执行会产生重复节点。`MERGE` 会先按给出的模式匹配，找不到才创建，适合可重复运行的导入。初学者最常见的失误，是在一个很大的 `MERGE` 中混入不断变化的属性，导致每次都匹配失败。

```cypher
MERGE (a:Person {id: 'p-001'})
SET a.name = '阿明'
MERGE (b:Person {id: 'p-002'})
SET b.name = '小林'
MERGE (book:Club {id: 'c-book'})
SET book.name = '读书会'
MERGE (film:Club {id: 'c-film'})
SET film.name = '电影会'
MERGE (a)-[j:JOINED]->(book)
SET j.at = date('2026-01-10')
MERGE (b)-[:JOINED]->(book)
MERGE (b)-[:JOINED]->(film)
MERGE (a)-[:FOLLOWS]->(b);
```

预期 Browser 图视图中有两个人、两个小组和四类连接。用以下检查确认数据量，而不要只相信图形界面：

```cypher
MATCH (n) RETURN labels(n) AS labels, count(*) AS total;
MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS total;
```

## 用模式匹配提出问题

Cypher 的 `MATCH` 描述要找的图形模式，`RETURN` 决定输出字段。括号是节点，方括号是关系，箭头是方向。

```cypher
MATCH (p:Person {name: '阿明'})-[:JOINED]->(c:Club)
RETURN c.name AS club;

MATCH (a:Person {name: '阿明'})-[:FOLLOWS]->(friend)-[:JOINED]->(c:Club)
RETURN friend.name AS friend, collect(c.name) AS clubs;
```

第一条预期返回“读书会”；第二条预期返回小林和两个小组。这里的变量 `friend` 不是表名，而是匹配过程临时绑定的节点。

## 事务和更新的基本边界

Neo4j 写入在事务中完成：整条语句成功则提交，发生约束冲突等错误则不会留下半条语句的写入。应用程序中应使用参数，而不是把用户文本拼进 Cypher；参数既避免注入，也可提高计划复用率。

```cypher
MATCH (p:Person {id: $personId})
MATCH (c:Club {id: $clubId})
MERGE (p)-[r:JOINED]->(c)
ON CREATE SET r.at = date()
RETURN p.name, c.name, r.at;
```

预期是首次调用创建关系、重复调用保持一条关系。不要把 `ON CREATE SET` 改成每次都会更新的 `SET`，除非“最后写入时间”确实是你要保存的业务事实。

## 常见错误

- **把所有东西放成属性。** 如果要问“谁与谁有什么连接”，字符串数组很快难以查询；改为关系。
- **把每个小词都建节点。** 只为展示一个枚举值建立节点会增加跳数和维护成本；稳定、可复用、要连接的概念才值得建节点。
- **没有约束就用 MERGE。** 并发导入时可能产生重复；先建立稳定 ID 的唯一约束。
- **用内部 ID 做业务键。** 迁移或恢复后会失去含义；保存自己的 `id`。

## 小结

图模型用节点表示实体，用关系表示事实和连接。你已经完成了 Neo4j 的启动、约束、幂等写入和模式查询。下一章将学习如何控制路径查询的成本，并用索引和算法获得可解释结果。
