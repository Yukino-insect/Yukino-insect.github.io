+++
date = '2026-10-02T20:00:00+08:00'
draft = false
title = '跨领域中间件与模型服务课程索引'
+++

这是一张跨分类的学习索引，而不是一个 AI 专题页。课程按组件的技术本体分别归入网站的“数据存储与检索”“分布式架构”和“AI 工程”：向量库、图数据库、对象存储与 ClickHouse 属于数据系统；etcd 属于分布式协调；模型推理、OCR、LLM 可观测性才属于 AI 模型服务。它们可以出现在同一项目，不能因此被误归为同一种技术。

每一套课都先解释组件自身解决的问题、核心原理、部署与运维，再把搜索、推荐、文档处理、分析或 AI 应用列作可选案例。读者应按正在学习的组件所在分类进入；这个页面只负责提供横向索引。

## 五套独立教程

### 向量检索与向量数据库

从 Embedding 的几何含义、距离度量和 ANN 索引开始，分别落到 PostgreSQL + pgvector 和 Milvus。它解决的是“怎样以可控的召回率、延迟和成本完成相似对象检索”。

- [课程导读](../../VectorDB/vector-database-course/00-overview.md)
- [Embedding、相似度与归一化](../../VectorDB/vector-database-course/01-embedding-and-similarity.md)
- [ANN 索引：HNSW 与 IVF](../../VectorDB/vector-database-course/02-ann-indexes.md)
- [pgvector 实战](../../VectorDB/vector-database-course/03-pgvector-practice.md)
- [Milvus 本地实验与使用](../../VectorDB/vector-database-course/04-milvus-practice.md)
- [基准测试、选型与迁移](../../VectorDB/vector-database-course/05-benchmark-selection-and-migration.md)

### PyTorch 与图像深度学习：从基础到项目推理

如果你刚接触 PyTorch，先从这里开始。它先把“模型为什么能从数据中学习”拆成数据、张量、梯度与训练循环，再以 CleanCanvas Studio 的 LaMa、Manga 与 Real-ESRGAN 代码讲解图像张量、TorchScript、权重加载、CPU/GPU、FP16、卷积网络和分块推理。学完后，你可以顺着真实项目代码理解推理链路，而不必把 `loss.backward()` 或 `model.to(device)` 当作必须照念的咒语。

- [零基础 PyTorch 课程导读：从 Python 程序到第一个会学习的模型](01-pytorch-foundations/00-overview.md)
- [机器学习零基础：样本、训练集、验证集与泛化](01-pytorch-foundations/01-machine-learning-data-and-generalization.md)
- [PyTorch 零基础：张量、形状与自动求导](01-pytorch-foundations/02-tensor-linear-algebra-and-gradients.md)
- [PyTorch 零基础实战：写出第一个训练循环并学会排错](01-pytorch-foundations/03-neural-network-training-loop.md)
- [项目实战：沿着 CleanCanvas Studio 读懂 PyTorch 图像推理调用链](01-pytorch-foundations/04-project-inference-reading-map.md)
- [项目实战：图像如何变成 PyTorch 张量——预处理、mask 与 LaMa 修复](01-pytorch-foundations/05-image-tensor-preprocessing-and-inpainting.md)
- [项目实战：加载预训练权重、选择 CPU/GPU 与正确进入推理模式](01-pytorch-foundations/06-model-loading-device-and-inference-mode.md)
- [项目实战：从卷积网络到分块推理——读懂 Real-ESRGAN 超分代码](01-pytorch-foundations/07-realesrgan-network-and-tiled-inference.md)
- [项目实战：PyTorch 与深度学习面试问答、排错清单与学习路线](01-pytorch-foundations/08-project-interview-and-debugging.md)

### 深度学习、模型推理与重排序

这套课以前置理论为基础，解释 Transformer 在文本排序中做了什么，并以 BGE Reranker 为例讲清楚 Cross-Encoder、PyTorch、CPU/GPU、FP16、批处理和 FastAPI 服务化。

- [课程导读](02-model-inference-and-rerank/00-overview.md)
- [深度学习与 Transformer 基础](02-model-inference-and-rerank/01-deep-learning-transformer-foundations.md)
- [召回与 Cross-Encoder 重排序](02-model-inference-and-rerank/02-retrieval-and-cross-encoder-rerank.md)
- [PyTorch 加载、设备与精度](02-model-inference-and-rerank/03-pytorch-loading-device-and-precision.md)
- [FastAPI 重排序服务](02-model-inference-and-rerank/04-fastapi-rerank-service.md)
- [性能、评估与生产运行](02-model-inference-and-rerank/05-performance-evaluation-and-production.md)
- [模型下载、PaddleOCR 与自部署 Reranker](02-model-inference-and-rerank/06-模型文件、PaddleOCR与重排序部署.md)
- [Python 图像修复与指定区域 Inpainting](02-model-inference-and-rerank/07-Python图像修复与指定区域Inpainting.md)

### 文档智能与 OCR

这一套关注原始 PDF、扫描件和 Office 文件如何成为可信、可追溯的结构化文档资产。会从 OCR 的检测与识别讲到版面、表格和公式，再进入异步解析服务的接口与运维。

- [课程导读](03-document-intelligence-ocr/00-overview.md)
- [文档理解与 OCR 基础](03-document-intelligence-ocr/01-document-understanding-and-ocr-basics.md)
- [PaddleOCR、版面与结构化解析](03-document-intelligence-ocr/02-paddleocr-layout-and-structure.md)
- [Office、PDF、资产与溯源](03-document-intelligence-ocr/03-office-pdf-assets-and-provenance.md)
- [异步文档解析服务](03-document-intelligence-ocr/04-async-parser-service.md)
- [质量、部署与运行](03-document-intelligence-ocr/05-quality-deployment-and-operations.md)

### 图数据库、知识图谱与图检索

这套课从属性图、Cypher 与 Neo4j 开始，讨论如何构建可溯源的知识图谱、如何进行图查询和图算法计算。GraphRAG 与 LightRAG 是其中一个 AI 检索应用，而不是图数据库的定义。

- [课程导读](../../GraphDB/graph-database-course/00-overview.md)
- [图数据与 Neo4j 基础](../../GraphDB/graph-database-course/01-graph-and-neo4j-foundations.md)
- [Cypher、索引与图算法](../../GraphDB/graph-database-course/02-cypher-index-and-graph-algorithms.md)
- [知识图谱构建](../../GraphDB/graph-database-course/03-knowledge-graph-construction.md)
- [LightRAG 架构与检索](../../GraphDB/graph-database-course/04-lightrag-architecture-and-retrieval.md)
- [图检索与 GraphRAG 的评估与运维](../../GraphDB/graph-database-course/05-graphrag-evaluation-and-operations.md)

### LLM 可观测性与运行治理

大模型和 Agent 的问题不能只靠应用日志定位。这套课讲 Trace、Span、Token、成本、工具调用与评测闭环，并从 Langfuse 的实际依赖解释 ClickHouse、Redis、PostgreSQL 和对象存储各自的职责。

- [课程导读](05-llm-observability/00-overview.md)
- [LLM 可观测性基础](05-llm-observability/01-llm-observability-fundamentals.md)
- [Langfuse 数据流](05-llm-observability/02-langfuse-data-flow.md)
- [埋点、追踪与评测](05-llm-observability/03-trace-instrumentation-and-evaluation.md)
- [隐私、成本与可靠性](05-llm-observability/04-privacy-cost-and-reliability.md)
- [Compose 运维与排障](05-llm-observability/05-compose-operations-and-troubleshooting.md)

### RustFS、MinIO 与 S3 对象存储

RustFS 与 MinIO 都提供 S3 兼容对象存储接口。对象存储不是“放文件的 Docker 容器”，而是一套 Bucket、Key、对象版本、签名、权限、生命周期和恢复机制。本专题以 RustFS 为主要实战对象，并说明与 MinIO 的兼容边界。

- [课程导读](../../OSS/object-storage-course/00-overview.md)
- [S3 数据模型与 API](../../OSS/object-storage-course/01-s3-data-model-and-api.md)
- [RustFS / MinIO 本地实战](../../OSS/object-storage-course/02-rustfs-minio-local-practice.md)
- [SDK、分片上传与预签名](../../OSS/object-storage-course/03-sdk-upload-download-presign.md)
- [权限、生命周期、备份与运维](../../OSS/object-storage-course/04-security-lifecycle-backup-operations.md)

### etcd 分布式协调服务

etcd 是具有线性一致性语义的 KV 与协调服务，不是用来替代业务数据库的“可靠 Redis”。这一套从 Raft、revision、lease、watch 一直做到事务、选主、压缩、快照和恢复。

- [课程导读](../../Microservices/etcd-course/00-overview.md)
- [Raft、revision、watch 与 lease](../../Microservices/etcd-course/01-raft-revision-watch-lease.md)
- [etcdctl KV 实战](../../Microservices/etcd-course/02-etcd-dockerctlkv-practice.md)
- [事务、锁、选主与 watch](../../Microservices/etcd-course/03-transaction-lock-election-watch.md)
- [压缩、快照、恢复与运维](../../Microservices/etcd-course/04-compaction-snapshot-restore-operations.md)

### ClickHouse 列式分析数据库

ClickHouse 是面向高吞吐分析的列式数据库。本专题从 MergeTree 的 parts、分区、排序键与稀疏索引进入，再落到批量写入、系统表、TTL、备份和故障排查；Langfuse 只是它的一个使用者。

- [课程导读](../../ClickHouse/clickhouse-course/00-overview.md)
- [列式存储与 MergeTree](../../ClickHouse/clickhouse-course/01-columnar-merge-tree-data-model.md)
- [Docker 与 SQL 实战](../../ClickHouse/clickhouse-course/02-clickhouse-docker-sql-practice.md)
- [摄入、分区、排序键与 TTL](../../ClickHouse/clickhouse-course/03-ingestion-partition-orderby-ttl.md)
- [查询剖析、备份与运维](../../ClickHouse/clickhouse-course/04-query-observability-backup-operations.md)

## 组件与应用的关系

五套教程不是五个互不相干的产品说明，但也没有一条必须遵循的“唯一流水线”。同一个组件可服务于不同业务：

```text
向量数据库  -> 语义搜索 / 相似商品推荐 / 内容去重 / RAG
重排序服务  -> 站内搜索精排 / 广告或推荐候选排序 / RAG
文档智能    -> 档案数字化 / 合同审计 / 表单录入 / 无障碍阅读 / RAG
图数据库    -> 风控关系网络 / 权限与依赖分析 / 推荐 / GraphRAG
Langfuse    -> 客服助手 / 代码生成 / 审批 Agent / 内容生成 / RAG
```

它们在一个文档问答系统中也确实可以组合，但那只是一项综合实战，不应反过来定义组件本身。读完任一专题后，都应能回答四个问题：它的输入输出是什么、内部依赖怎样协作、什么指标说明它工作正常、发生故障时数据是否可以恢复。能回答这些，才算是掌握系统；会把容器启动起来，只能算它暂时没有反对你而已。

## 已有课程与补充专题

本轮不重复新建 Docker、Redis 或通用对象存储入门的平行文章：站内已有 [Docker 容器技术教程](../../Docker/docker-course/00-docker-learning-map.md)、[Redis 基础](../../Redis/Redis基础.md) 与 [MinIO](../../OSS/MinIO.md)。新的 S3、etcd 和 ClickHouse 专题补上旧文章没有系统展开的存储协议、协调语义和列式分析机制；向量课程中的 pgvector 实战则覆盖 PostgreSQL 与向量扩展的交界。

## 学习与实践边界

- 本课程没有纳入 Elasticsearch 和 RocketMQ；项目已有相应内容，且它们属于另一个明确的问题域。
- 文中的端口、版本与组件组合仅用于隔离实验，不等同于生产推荐。尤其镜像标签、驱动版本、密钥和资源配额必须在自己的环境重新核实。
- 不要把模型服务、向量索引或 OCR 直接暴露到公网。鉴权、网络隔离、密钥管理、限流和内容治理都属于系统设计的一部分。
