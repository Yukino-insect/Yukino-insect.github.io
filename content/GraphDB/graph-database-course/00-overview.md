+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '图数据库入门课程：从关系数据到 Neo4j 实战'
+++

图数据库不是把关系型数据库换一个名字。它解决的是另一类问题：**数据之间的连接本身很重要，而且需要反复沿着连接向外探索**。例如“某员工通过哪些角色获得某系统权限”“某笔交易在三跳内是否关联高风险账户”“这个零件的上游供应商中哪些已经停产”。

本课程以 Neo4j 为实验工具，但先学习图模型和查询思维；即使以后改用别的图数据库，这些基础也仍然成立。知识图谱、推荐、风控、依赖分析只是图技术的应用，不是本课程的前提。

## 适合谁，以及学完能做什么

假定你会一点 SQL 和命令行，但从未接触节点、关系或 Cypher。完成课程后，你应能：

- 判断一个需求是否真的适合图数据库；
- 为实体、关系、属性和时间设计一个不会立刻失控的图模型；
- 在本机启动 Neo4j，并用 Browser 和 `cypher-shell` 写入、查询数据；
- 用约束、索引、执行计划和图算法把查询做得正确且可解释；
- 导入可重跑的数据，完成备份、恢复和基本排障。

不要把图数据库当作万能数据库。订单扣库存、强事务账本、按列聚合报表仍常常更适合关系型数据库或分析数据库。图数据库擅长的是以连接为中心的查询，不是取代所有存储。

## 先认识四个最小术语

**节点（node）**表示一个实体，例如人、设备、服务或城市。**关系（relationship）**表示两个节点之间有方向的连接，例如 `(:Person)-[:FOLLOWS]->(:Person)`。**标签（label）**是节点的类型标记，如 `:Person`；一个节点可有多个标签。**属性（property）**是附在节点或关系上的键值，例如 `name`、`createdAt`、`amount`。

下图表达“阿明在 2026 年加入读书会”：

```text
(:Person {name: '阿明'})
  -[:JOINED {at: date('2026-01-10')}]->
(:Club {name: '读书会'})
```

这里“加入”不是一个字符串字段，而是一条可被查询、可携带时间属性的关系。后面所有实验都围绕这个区别展开。

## 贯穿实验环境

请先安装 Docker Desktop 或可运行 Docker 的环境。下面命令启动一个独立、临时的 Neo4j Community 容器；请为实际工作设置自己的强密码，不要把示例密码带入公网环境。

```powershell
docker run --name neo4j-course --rm -d `
  -p 7474:7474 -p 7687:7687 `
  -e NEO4J_AUTH=neo4j/change-this-password `
  neo4j:5-community

docker logs -f neo4j-course
```

预期日志最终出现数据库已可接受连接的提示。随后访问 `http://localhost:7474`，使用用户名 `neo4j` 和你设置的密码登录 Neo4j Browser。也可进入命令行：

```powershell
docker exec -it neo4j-course cypher-shell -u neo4j -p change-this-password
```

预期会看到 `neo4j@neo4j>` 提示符。停止实验时执行 `docker stop neo4j-course`；因为这里使用 `--rm` 且未挂载数据卷，容器删除后数据也会消失。这是刻意的：先理解操作，再学习持久化和备份。

常见错误：7474 或 7687 端口被占用时，改用 `-p 17474:7474 -p 17687:7687`；登录失败时先确认 `NEO4J_AUTH` 设置的是首次启动密码，并用 `docker logs neo4j-course` 检查初始化是否完成。

## 学习路线

1. [关系问题、图模型与 Neo4j 上手](01-graph-and-neo4j-foundations.md)：从一张多对多表开始，亲手建立第一张图。
2. [Cypher、索引与图算法](02-cypher-index-and-graph-algorithms.md)：学习模式匹配、路径边界、执行计划和基础算法。
3. [通用数据摄取与图治理](03-knowledge-graph-construction.md)：解决稳定 ID、幂等导入、时间和来源。
4. [文档图与 LightRAG：可选应用](04-lightrag-architecture-and-retrieval.md)：了解图如何参与文档问答，但不把它误认为图数据库本身。
5. [测试、备份与运行维护](05-graphrag-evaluation-and-operations.md)：让图数据在失败后仍可验证和恢复。

## 小结

这是一门先动手、再抽象的课程。每一章都给出术语、实验步骤、预期结果和错误处理。开始前只需确认 Docker 容器能启动；其余概念会在需要时逐层引入。
