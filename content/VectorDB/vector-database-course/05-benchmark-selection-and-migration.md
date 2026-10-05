+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '向量数据库评测、选型与模型迁移：从能跑到可长期维护'
+++

到这里，你已经能在 pgvector 和 Milvus 中完成一次向量检索。可是“两个系统都能返回结果”不是选型结论。真正需要回答的是：在固定数据、固定查询、固定过滤和固定延迟预算下，它们各自能达到什么 Recall@K；当 embedding 模型更换、维度改变时，又怎样让旧数据平稳过渡。

本章给出一个小白也能执行的评测框架。它不宣称某个产品永远更快，而是教你如何为自己的数据得到可追溯的答案。

## 先定义评测和迁移术语

- **基准（benchmark）**：在固定输入、环境和指标下重复执行的测量。
- **真值（ground truth）**：精确扫描所得的 Top-K，ANN 用它计算召回。
- **Recall@K**：ANN 找回的真值 Top-K 占比，定义见[第二章](02-ann-indexes.md)。
- **吞吐量（throughput）**：单位时间完成的请求数，例如 QPS。
- **P95 延迟**：95% 请求不超过的耗时；它通常比平均值更能暴露尾部卡顿。
- **过滤选择性（selectivity）**：过滤后保留记录的比例。保留 1% 比保留 90% 更严格。
- **双写（dual write）**：迁移期间同时向旧库和新库写入数据。
- **回填（backfill）**：把历史对象用新模型重新生成向量并写入新存储。
- **切换（cutover）**：经过校验后，把读流量从旧版本转到新版本。

这些定义看似朴素，却能避免“QPS 很高”“模型升级完成”这类没有条件、无法复核的结论。

## 问题场景：为什么不能复制别人的参数

假设甲系统有 10 万条 384 维、全部单位化的文本向量，查询无过滤；乙系统有 1 000 万条 1 024 维图片向量，每次必须限制到一个很小的租户。即使二者都使用 HNSW，内存、索引时间、过滤后候选数和适合的 `ef_search` 也会不同。

因此评测的第一步不是启动压测工具，而是写清楚实验契约：

| 字段 | 示例 | 不能省略的原因 |
| --- | --- | --- |
| 数据版本 | `lab-items.jsonl`，3 000 条，32 维 | 数据规模和维度直接影响成本 |
| 模型契约 | 合成单位向量；L2 度量 | 真实项目应写模型名、版本、归一化规则 |
| 查询集 | 固定 30 个 query id | 避免每次测到不同难度的查询 |
| Top-K | 10 | K 改变会改变召回和延迟 |
| 过滤 | 无过滤、`tenant_id == 1` | 必须分开报告 |
| 环境 | CPU、内存、Docker 版本、数据库版本 | 否则结果无法复现 |

## 独立实验：先生成精确真值和查询集

在 `vector-db-lab` 中创建 `make_truth.py`。它不连接任何数据库，只用 NumPy 对相同数据做精确 L2 扫描，因此是之后每个 ANN 结果的共同裁判。

```python
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

rows = [json.loads(line) for line in Path("lab-items.jsonl").read_text(encoding="utf-8").splitlines()]
matrix = np.asarray([row["embedding"] for row in rows], dtype=np.float32)
query_indexes = list(range(0, len(rows), 97))[:30]


def exact_ids(query_index: int, filtered: bool) -> list[int]:
    candidates = list(range(len(rows)))
    if filtered:
        candidates = [i for i in candidates if rows[i]["tenant_id"] == 1 and rows[i]["status"] == "active"]
    candidate_matrix = matrix[candidates]
    distances = np.linalg.norm(candidate_matrix - matrix[query_index], axis=1)
    order = np.argsort(distances)[:10]
    return [rows[candidates[i]]["id"] for i in order]


truth = []
for query_index in query_indexes:
    truth.append({
        "query_id": rows[query_index]["id"],
        "all": exact_ids(query_index, filtered=False),
        "tenant_1_active": exact_ids(query_index, filtered=True),
    })

Path("truth-top10.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
print(f"wrote {len(truth)} queries to truth-top10.json")
```

```powershell
python .\make_truth.py
Get-Content .\truth-top10.json -TotalCount 8
```

预期第一条命令输出 `wrote 30 queries`。第二条会显示每个 `query_id` 的两组精确 Top-10；某些 query 不属于租户 1 时，过滤后的第一名自然不是它自己。

## 记录 ANN 结果并计算 Recall@K

无论你使用哪种数据库，都把每次搜索结果写成同一个格式：每行包含 `engine`、`parameter`、`filter_name`、`query_id`、`ids` 和 `latency_ms`。例如：

```json
{"engine":"milvus-hnsw","parameter":"ef=80","filter_name":"tenant_1_active","query_id":1,"ids":[1,16,31],"latency_ms":3.42}
```

创建 `score_results.py`：

```python
from __future__ import annotations

import json
from pathlib import Path
from statistics import quantiles

truth = {entry["query_id"]: entry for entry in json.loads(Path("truth-top10.json").read_text(encoding="utf-8"))}
results = [json.loads(line) for line in Path("ann-results.jsonl").read_text(encoding="utf-8").splitlines()]

recalls = []
latencies = []
for result in results:
    expected = truth[result["query_id"]][result["filter_name"]]
    actual = result["ids"][:10]
    recalls.append(len(set(expected) & set(actual)) / 10)
    latencies.append(result["latency_ms"])

latencies.sort()
p95_index = max(0, int(len(latencies) * 0.95) - 1)
print(f"queries={len(results)}")
print(f"mean_recall_at_10={sum(recalls) / len(recalls):.3f}")
print(f"p50_ms={latencies[len(latencies) // 2]:.3f}")
print(f"p95_ms={latencies[p95_index]:.3f}")
```

先不要伪造 `ann-results.jsonl` 来“通过”脚本。应当由你在 pgvector 或 Milvus 中实际运行固定 30 个 query 后生成它。预期是得到四个数字，而不是某个预设的“优秀分数”。在 3 000 条合成数据上，任何数据库都可能很快；这个实验的价值在于流程可扩展到真实数据。

## 解释机制：pgvector 与 Milvus 应如何比较

它们不是“一个旧、一个新”的关系，而是不同数据系统边界的取舍。

| 先问的问题 | 倾向 pgvector 的信号 | 倾向 Milvus 的信号 |
| --- | --- | --- |
| 数据是否已属于 PostgreSQL 事务？ | 是，且希望 SQL、约束、备份统一 | 否，向量检索是独立高负载服务 |
| 规模和查询压力如何？ | 小到中等，精确或简单 ANN 已满足指标 | 索引、检索吞吐和资源隔离已成为独立问题 |
| 过滤与关联逻辑如何？ | 复杂 SQL 过滤、JOIN、事务语义重要 | 向量字段与标量过滤是主要查询形态 |
| 运维能力如何？ | 团队已擅长 PostgreSQL | 团队愿意承担独立服务、容量和备份演练 |

这张表不是容量阈值承诺。先运行同一查询集：pgvector 要记录 `EXPLAIN (ANALYZE, BUFFERS)`；Milvus 要记录索引参数、load 状态和客户端耗时。只有在**相同的 Recall@K 下**比较 P95、内存、写入延迟和维护复杂度，结论才公平。

## 模型或维度变更：为什么不能直接覆盖旧向量

向量的坐标意义由模型决定。模型升级后，即使新旧维度同为 768，也不能把一部分新向量和一部分旧向量放在同一个索引中比较；若维度改变，数据库通常会直接拒绝写入。安全流程是：

```text
新模型与新存储版本
        |
        v
回填历史对象 -> 抽样校验数量、维度、NaN 和检索结果
        |
        v
双写新数据 -> 对账旧/新写入延迟与失败记录
        |
        v
影子查询或小流量灰度 -> 比较业务质量、Recall、P95、错误率
        |
        v
切换读取 -> 保留旧版本直到回滚窗口结束
```

这里的“新存储版本”可以是 pgvector 的新列/新表，也可以是 Milvus 的新 Collection；不要把它理解成覆盖原索引。

最小的迁移清单如下：

1. 给 embedding 写明确版本，如 `embedding_model='model-x@2026-10'`；不要只写模糊的 `latest`。
2. 新建 `embedding_v2` 表或 `items_v2` Collection，定义正确的维度、度量和索引。
3. 分批回填，记录源对象 id、模型版本、成功/失败和重试次数；写入前检查维度与有限数值。
4. 对每批比较源对象数量与目标对象数量，并抽样执行精确与 ANN 查询。
5. 双写期间设计幂等键，处理“旧库成功、新库失败”的补偿；不能默默吞掉失败。
6. 灰度读取新版本，监控无结果率、P95、Recall 代理指标和业务质量；达到阈值才扩大流量。
7. 保留旧索引和回滚开关，确认备份与恢复后再在维护窗口清理。

## 常见错误

### 只报平均延迟

平均 5 ms 可能掩盖少数 300 ms 请求。至少同时报告 P50、P95、P99、超时比例和每个参数的 Recall@K；如果请求数量不够，诚实写明样本量不足。

### 把不同过滤条件放进同一张成绩单

无过滤检索与仅允许 1% 数据的检索不是同一道题。过滤会改变候选集，也会改变 ANN 的召回和时间；应该分别生成真值、结果文件和结论。

### 将 ETag、主键或文本 hash 当成 embedding 版本

它们能帮助发现内容变化，却不能说明向量由哪个模型、何种归一化和何种输入模板生成。版本信息必须显式保存。

### 迁移完成后立刻删除旧库

这会把“切换错误”“回填遗漏”和“模型质量下降”变成不可逆事故。先完成回滚窗口、对账和恢复演练，再进行有记录的清理。

## 小结

- 好的向量数据库评测必须固定数据、模型、查询、过滤、Top-K 和环境，并以精确真值计算 Recall@K。
- pgvector 与 Milvus 应按数据边界、查询形态、性能证据和运维能力选择，而不是按宣传语选择。
- embedding 升级是数据迁移：新版本、回填、双写、对账、灰度、回滚缺一不可。
- 至此，你已经有一条完整的学习路径：理解向量 → 建立真值 → 调近似索引 → 分别操作 pgvector/Milvus → 用评测和迁移让系统可维护。
