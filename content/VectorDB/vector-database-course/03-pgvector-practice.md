+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'pgvector 实战：建表、导入、索引、执行计划与维护'
math = true
+++

当向量和关系数据本来就需要一起保存时，`pgvector` 让 PostgreSQL 增加 `vector` 类型和距离操作符。它不是另一台神秘的“AI 数据库”，而是关系数据库的一项扩展：事务、SQL、约束、备份和权限仍然是 PostgreSQL 的规则。

本章从零启动一个独立容器。它不连接任何已有数据库，实验结束后删除容器即可重来。

## 先看问题：为什么不把向量放进 JSON

JSON 数组可以保存数字，却没有向量距离运算和 ANN 索引能力。`vector(32)` 则明确表示“恰好 32 维的浮点向量”，数据库可以拒绝错误维度，并对它建立 HNSW 或 IVFFlat 索引。元数据仍放在普通列中，便于事务与过滤。

```text
items
  id, tenant_id, status, title  -> ordinary relational columns
  embedding                    -> vector(32)
```

## 最小实验：启动独立 PostgreSQL

在实验目录创建 `compose.pgvector.yml`：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: lab_user
      POSTGRES_PASSWORD: lab_password_change_me
      POSTGRES_DB: vector_lab
    ports:
      - "55432:5432"
    volumes:
      - pgvector_lab_data:/var/lib/postgresql/data

volumes:
  pgvector_lab_data:
```

密码仅用于本机实验，绝不能复制到共享环境。启动并检查：

```powershell
docker compose -f .\compose.pgvector.yml up -d
docker compose -f .\compose.pgvector.yml ps
docker compose -f .\compose.pgvector.yml exec postgres psql -U lab_user -d vector_lab -c "SELECT version();"
```

预期 `ps` 中服务为 `running`，最后一条显示 PostgreSQL 版本。若端口 `55432` 被占用，换成未占用的主机端口；容器内端口仍是 `5432`。

## 建表：先让数据库保护数据契约

创建 `schema.sql`：

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS searchable_item (
    id BIGINT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    embedding vector(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS searchable_item_filter_idx
    ON searchable_item (tenant_id, status);
```

```powershell
Get-Content .\schema.sql | docker compose -f .\compose.pgvector.yml exec -T postgres psql -U lab_user -d vector_lab
```

预期出现 `CREATE EXTENSION`、`CREATE TABLE`、`CREATE INDEX`。`vector(32)` 是不可省略的契约：32 维数据写入 768 维列应当失败，早失败比静默得到错误结果可靠得多。

## 导入并完成第一次精确查询

创建 `load_pgvector.py`。参数化 SQL 不仅更安全，也避免手工拼接数千个浮点数字。

```python
import json
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

rows = [json.loads(line) for line in Path("lab-items.jsonl").read_text(encoding="utf-8").splitlines()]
with psycopg.connect("postgresql://lab_user:lab_password_change_me@localhost:55432/vector_lab") as conn:
    register_vector(conn)
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO searchable_item (id, tenant_id, status, topic, title, embedding)
               VALUES (%(id)s, %(tenant_id)s, %(status)s, %(topic)s, %(title)s, %(embedding)s)
               ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding""",
            rows,
        )
    conn.commit()
print(f"loaded {len(rows)} rows")
```

```powershell
python .\load_pgvector.py
```

预期输出 `loaded 3000 rows`。执行精确检索时，`<->` 是 L2 距离操作符，数值越小越近：

```sql
WITH q AS (SELECT embedding FROM searchable_item WHERE id = 1)
SELECT id, topic, embedding <-> (SELECT embedding FROM q) AS distance
FROM searchable_item
WHERE tenant_id = 1 AND status = 'active'
ORDER BY embedding <-> (SELECT embedding FROM q)
LIMIT 5;
```

将 SQL 保存为 `query.sql` 后执行：

```powershell
Get-Content .\query.sql | docker compose -f .\compose.pgvector.yml exec -T postgres psql -U lab_user -d vector_lab
```

预期返回五行，并且第一行常为 `id=1`（它在 `tenant_id=1` 且通常是 active）。请注意：若 query 本身不满足过滤条件，第一行不一定是它自己；这是 SQL 语义，不是向量算法异常。

## 再解释机制：精确扫描与两种索引

没有向量索引时，PostgreSQL 对满足 `WHERE` 的每行计算距离并排序，结果精确。对小表或强过滤，这常常已经足够。先看实际计划：

```sql
EXPLAIN (ANALYZE, BUFFERS)
WITH q AS (SELECT embedding FROM searchable_item WHERE id = 1)
SELECT id FROM searchable_item
WHERE tenant_id = 1 AND status = 'active'
ORDER BY embedding <-> (SELECT embedding FROM q)
LIMIT 10;
```

接着建 HNSW（本实验使用 L2）：

```sql
CREATE INDEX searchable_item_embedding_hnsw
ON searchable_item USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);

SET hnsw.ef_search = 80;
```

HNSW 的 `m` 和 `ef_construction` 含义见上一章；`ef_search` 是会话级探索宽度。IVFFlat 则必须先有数据，再训练建索引：

```sql
CREATE INDEX searchable_item_embedding_ivf
ON searchable_item USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);
SET ivfflat.probes = 10;
```

一次实验只保留一个向量索引，避免读者误判计划。建 IVF 前应先 `DROP INDEX searchable_item_embedding_hnsw;`。实际是否使用索引要以 `EXPLAIN` 为准，不能根据“我执行过 CREATE INDEX”推断。

## 故障排查与维护

### 索引没被使用

先确认 `ORDER BY embedding <-> query LIMIT k` 的形式匹配操作符类；再看数据量是否太小、过滤是否让普通索引扫描更便宜。不要强行关闭顺序扫描来“证明”索引有用，那是在改变实验而非理解计划。

### 维度或度量不一致

`vector(32)` 报维度错误时，不要补零或截断来通过写入。检查模型版本和管道；余弦距离应使用相应的余弦操作符类而不是把 L2 索引当作同一件事。

### 删除与膨胀

PostgreSQL 的 MVCC 不会让删除行立刻从物理文件消失。日常使用 `VACUUM (ANALYZE)` 更新统计信息；大批量重建索引可使用 `REINDEX INDEX CONCURRENTLY`（需在合适版本和权限下）。先在副本或维护窗口验证，别把生产恢复练习当作第一次操作。

### 备份与清理

验证备份最小闭环：

```powershell
docker compose -f .\compose.pgvector.yml exec -T postgres pg_dump -U lab_user vector_lab > .\vector_lab.sql
docker compose -f .\compose.pgvector.yml down -v
docker compose -f .\compose.pgvector.yml up -d
Get-Content .\vector_lab.sql | docker compose -f .\compose.pgvector.yml exec -T postgres psql -U lab_user -d vector_lab
```

恢复后重跑 `query.sql`。能生成备份不等于能恢复，能恢复并查询才是证据。实验结束时可以执行 `docker compose -f .\compose.pgvector.yml down -v` 删除实验卷。

## 小结

- `pgvector` 把向量作为 PostgreSQL 的强类型数据，而元数据过滤仍由 SQL 完成。
- 先观察精确查询的计划，再根据规模与指标选择 HNSW 或 IVFFlat。
- 索引、距离操作符、向量归一化和模型契约必须彼此匹配。
- 下一章学习专门的向量数据库，但相同的正确性契约不会改变。
