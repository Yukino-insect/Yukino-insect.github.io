+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'Milvus 实战：从 Collection 到 HNSW 检索'
+++

上一章的 pgvector 很适合“关系数据和向量放在同一个 PostgreSQL 数据库里”的情况。但有时，向量数量、检索吞吐或索引构建成本已经值得使用专门的向量数据库。Milvus 就是这样的系统：它把向量、标量字段、索引和检索生命周期作为一等能力管理。

本章不需要已有项目。我们会在一个空目录启动 Milvus，写入上一章生成的 3 000 条实验数据，完成一次带过滤的 HNSW 检索，并亲眼确认每一步的状态。

## 先定义这次会遇到的术语

- **Collection**：Milvus 中一组同类记录，类似关系数据库中的表。
- **Schema**：Collection 的字段定义，包括字段名、类型、主键和向量维度。
- **主键（primary key）**：唯一标识一条记录的字段；本实验使用整数 `id`。
- **标量字段（scalar field）**：整数、字符串、布尔值等普通字段，常用于过滤。
- **索引（index）**：为向量检索构建的辅助结构；本章使用 HNSW。
- **load**：把 Collection 的检索所需数据载入查询节点。创建索引不等于已经可以检索。
- **filter**：在服务器端限制允许返回的记录，例如 `tenant_id == 1`。

Milvus 把“数据已写入”“索引已创建”“Collection 已加载”分成不同状态。初学者经常以为 `insert()` 成功后立刻能得到和最终环境相同的检索表现，这正是本章要避免的误解。

## 本地实验：启动一个隔离的 Milvus

在上一章的 `vector-db-lab` 目录创建 `compose.milvus.yml`。这是独立实验配置；它只创建本地命名卷，不读取或修改任何已有 Compose 工程。

```yaml
services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.18
    command: etcd -advertise-client-urls=http://0.0.0.0:2379 -listen-client-urls=http://0.0.0.0:2379
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
      ETCD_SNAPSHOT_COUNT: "50000"
    volumes:
      - milvus_etcd:/etcd

  minio:
    image: minio/minio:RELEASE.2024-10-02T17-50-41Z
    command: minio server /minio_data
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - milvus_minio:/minio_data

  milvus:
    image: milvusdb/milvus:v2.6.6
    command: ["milvus", "run", "standalone"]
    security_opt:
      - seccomp:unconfined
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - etcd
      - minio
    volumes:
      - milvus_data:/var/lib/milvus

volumes:
  milvus_etcd:
  milvus_minio:
  milvus_data:
```

`etcd` 保存协调元数据，MinIO 提供 S3 兼容对象存储，Milvus 承担向量写入、索引和检索。它们是 Milvus standalone 的运行依赖，不是应用业务服务；正式集群的拓扑、认证、TLS 和备份策略应另行设计。

启动并等待服务就绪：

```powershell
docker compose -f .\compose.milvus.yml up -d
docker compose -f .\compose.milvus.yml ps
docker compose -f .\compose.milvus.yml logs milvus --tail 30
```

预期 `ps` 中三个容器均为 `running`，日志中出现服务启动完成的记录。第一次拉取镜像和初始化卷会较慢；若 `milvus` 不断重启，先看 `docker compose ... logs milvus`，不要反复执行创建 Collection 的脚本。

## 写入、建索引和检索：一段完整但最小的 Python 程序

确认环境中已有 `pymilvus`；没有则执行：

```powershell
pip install 'pymilvus>=2.6,<2.7'
```

创建 `milvus_lab.py`。程序使用 `lab-items.jsonl`，所以与 pgvector 实验的数据、维度、距离度量完全相同。

```python
from __future__ import annotations

import json
from pathlib import Path

from pymilvus import (
    DataType,
    MilvusClient,
)

URI = "http://localhost:19530"
COLLECTION = "items_lab"
DIMENSION = 32

rows = [json.loads(line) for line in Path("lab-items.jsonl").read_text(encoding="utf-8").splitlines()]
client = MilvusClient(uri=URI)

if client.has_collection(COLLECTION):
    client.drop_collection(COLLECTION)

schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
schema.add_field("id", DataType.INT64, is_primary=True)
schema.add_field("tenant_id", DataType.INT64)
schema.add_field("status", DataType.VARCHAR, max_length=16)
schema.add_field("topic", DataType.VARCHAR, max_length=32)
schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=DIMENSION)

index_params = client.prepare_index_params()
index_params.add_index(
    field_name="embedding",
    index_type="HNSW",
    metric_type="L2",
    params={"M": 16, "efConstruction": 64},
)

client.create_collection(
    collection_name=COLLECTION,
    schema=schema,
    index_params=index_params,
)

for start in range(0, len(rows), 500):
    batch = rows[start:start + 500]
    client.insert(
        collection_name=COLLECTION,
        data=[{
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "status": row["status"],
            "topic": row["topic"],
            "embedding": row["embedding"],
        } for row in batch],
    )

client.load_collection(COLLECTION)
query = rows[0]["embedding"]
result = client.search(
    collection_name=COLLECTION,
    data=[query],
    anns_field="embedding",
    limit=5,
    filter="tenant_id == 1 and status == 'active'",
    output_fields=["tenant_id", "status", "topic"],
    search_params={"metric_type": "L2", "params": {"ef": 80}},
)

for hit in result[0]:
    print(f"id={hit['id']} distance={hit['distance']:.6f} fields={hit['entity']}")

client.release_collection(COLLECTION)
```

运行：

```powershell
python .\milvus_lab.py
```

预期输出五行。第一行通常是 `id=1` 且距离接近 `0`，因为它满足 `tenant_id == 1` 与 `active` 过滤，并且查询向量正是该记录的向量。L2 距离越小代表越近；不要把它当作“置信度百分比”。

## 逐步解释：为什么程序的顺序不能随意打乱

1. **Schema 先于数据。** `FLOAT_VECTOR` 的 `dim=32` 让 Milvus 拒绝 31 或 33 维向量。`VARCHAR` 还必须指定最大长度。
2. **写入可分批进行。** 批大小影响客户端内存、网络往返和失败重试粒度；500 只是本机教学值，不是通用生产参数。
3. **索引定义度量。** HNSW 的 `metric_type="L2"` 必须与搜索的 `metric_type="L2"` 匹配。若使用归一化 embedding，也可以选择 IP 或 COSINE，但必须从模型契约重新验证排序。
4. **load 是可检索状态。** `load_collection()` 让服务准备搜索资源；`release_collection()` 则释放它们。较大的 Collection 会受可用内存和部署方式影响。
5. **过滤和向量检索是一条请求。** `filter` 由 Milvus 执行，不是先取五条再让 Python 排除。过滤越严格，越应使用“过滤后的精确真值”评估 Recall@K。

## 验证：不要只看“返回了五行”

用下面的查询确认 Collection 的实际记录数。把代码追加到脚本末尾、`release_collection` 之前：

```python
count = client.query(
    collection_name=COLLECTION,
    filter="id >= 0",
    output_fields=["count(*)"],
)
print("count:", count)
```

不同 `pymilvus` 小版本对聚合返回的字典形状可能略有差异，但预期可观察到 `3000`。还应故意将一条向量截成 31 维再插入，确认服务报出维度错误；这证明 schema 真在保护数据，而不是只出现在文档中。

若要测 HNSW 近似检索的 Recall@K，把第二章的精确 Top-K 与本章每个 query 的返回 `id` 比较，并分别记录 `ef=20`、`80`、`160` 的延迟和 Recall。不要只测查询自身，也不要把带过滤和不带过滤的成绩混在一起。

## 常见错误与排查

### 连接被拒绝或超时

先执行 `docker compose -f .\compose.milvus.yml ps` 确认容器状态，再检查 `19530` 是否被其他程序占用。Windows 上 Docker Desktop 未启动时，Python 客户端的错误只是结果，根因在 Docker 服务本身。

### `collection not loaded`

创建、插入或建立索引之后没有执行 `load_collection()`，或代码在检索前调用了 `release_collection()`。把生命周期写成明确的“创建 → 写入 → load → search → release”即可避免。

### 空结果或第一名不是查询自身

先检查过滤条件。`id=1` 并不保证一定是 `active`，而且查询本身可能不在指定租户；在有过滤的语义中，这种结果是正确的。随后检查维度、度量以及实际插入条数。

### 重跑脚本报 Collection 已存在或数据重复

本例启动时主动 `drop_collection()`，因此可重复运行。生产中绝不能照抄“先删再建”：应使用新 Collection 名称、双写、校验和切换别名完成迁移，下一章会说明。

### 容器能启动但数据丢失

确认 Compose 中的命名卷还在；`docker compose down -v` 会删除它们。本机卷只解决重启后的持久化，并不等于跨机器、跨故障域备份。

## 清理与小结

本章实验可以随时清理：

```powershell
docker compose -f .\compose.milvus.yml down -v
```

- Milvus 的核心对象是 Collection、Schema、标量字段、向量字段、索引和 load 生命周期。
- HNSW 的参数和距离度量不是产品魔法，仍应通过精确真值和 Recall@K 验证。
- 独立 Docker 实验能帮助你学习服务本身；不要把本机默认账号、单节点依赖关系或删除重建流程搬到正式环境。
- 下一章讨论如何用同一套数据比较 pgvector 与 Milvus，并在模型或维度变化时迁移而不丢数据。
