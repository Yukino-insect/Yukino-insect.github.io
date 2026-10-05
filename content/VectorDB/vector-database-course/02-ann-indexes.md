+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'ANN 索引：HNSW、IVF 与可复现召回基准'
math = true
+++

精确检索的做法很朴素：把查询向量与库中每一个向量计算距离，再取最小的 K 个。它一定正确，却要做 $N$ 次距离计算；当 $N$ 很大、查询很多时，成本会变得刺眼。**ANN（Approximate Nearest Neighbor，近似最近邻）**的承诺是更快，而代价是有机会漏掉精确 Top-K 中的对象。

“近似”不是失败，也不是产品缺陷；它是明确的工程交换。真正的问题是：漏了多少、快了多少、在过滤条件下是否仍可接受。本章先建立真值，再谈 HNSW 和 IVF。

## 最小实验：先写一个精确 Top-K

使用上一章生成的 `lab-items.jsonl`，创建 `exact_baseline.py`：

```python
import json
import time
from pathlib import Path

import numpy as np

rows = [json.loads(line) for line in Path("lab-items.jsonl").read_text(encoding="utf-8").splitlines()]
matrix = np.asarray([row["embedding"] for row in rows], dtype=np.float32)
query = matrix[0]

started = time.perf_counter()
distances = np.linalg.norm(matrix - query, axis=1)
top = np.argsort(distances)[:10]
elapsed_ms = (time.perf_counter() - started) * 1000

print("exact ids:", [rows[i]["id"] for i in top])
print(f"elapsed_ms={elapsed_ms:.3f}")
```

```powershell
python .\exact_baseline.py
```

预期第一个 `id` 是 `1`，因为查询本身也在库中，且耗时会是很小的毫秒数。小数据上扫描很快正是重点：不要在只有几千条向量时为了“使用向量数据库”而过早引入近似索引。此脚本输出的十个 `id` 就是本 query 的**真值集合**。

## 先定义指标：Recall@K 和延迟

设精确结果集合为 $E_K$，ANN 返回集合为 $A_K$，则：

$$
\operatorname{Recall@K}=\frac{|E_K\cap A_K|}{K}
$$

`Recall@10 = 0.9` 表示十个真正最近邻中找回了九个；它不评价排序位置，也不评价业务相关性。延迟应至少记录 P50、P95 和 P99，而不是只报一次“平均 3 ms”。

创建 `metrics.py`，用于比较任何两个 id 列表：

```python
def recall_at_k(exact_ids: list[int], approx_ids: list[int], k: int) -> float:
    exact = set(exact_ids[:k])
    approx = set(approx_ids[:k])
    return len(exact & approx) / k


print(recall_at_k([1, 2, 3, 4, 5], [1, 2, 9, 4, 8], 5))
```

```powershell
python .\metrics.py
```

预期输出 `0.6`。后面无论数据库报告什么“相似度”，都回到这个共同语言比较。

## HNSW：在小世界图中找近邻

**HNSW（Hierarchical Navigable Small World）**把向量连成多层图。上层节点少、跨度大，用来迅速靠近目标区域；下层节点多、连接细，负责局部搜索。查询时从高层入口开始，每步移动到更近邻居，逐层下降并保留若干候选。

```text
level 2:  o-------------------o
             \             /
level 1:   o---o---o---o---o
              \     |     /
level 0:  o--o--o--o--o--o--o
```

它不访问所有点，因而快；若入口、图连接或候选宽度不足，可能走进一个“看似近”的区域而错过真正更近的点。

| 参数 | 直觉 | 增大后的通常代价 |
| --- | --- | --- |
| `M` | 每个节点保留的最大连接数 | 内存和建索引时间上升，图更易走通 |
| `ef_construction` | 建图时保留的候选宽度 | 建索引变慢，通常提高图质量 |
| `ef_search` | 查询时探索候选宽度 | 查询更慢，通常提高召回 |

这些不是“越大越好”的旋钮。先选业务可接受的 P95，再在该预算内测 Recall@K。

## IVF：先分桶，再在少数桶里扫

**IVF（Inverted File Index）**先用聚类把空间划为 `nlist` 个中心。写入时每个向量归入最近中心；查询时先找最近的 `nprobe` 个桶，只扫描其中的向量。

```text
query -> nearest centroids -> selected lists -> exact scan inside lists -> Top-K
```

| 参数 | 含义 | 太小的风险 |
| --- | --- | --- |
| `nlist` | 桶（聚类中心）总数 | 桶太粗，单桶扫描仍很慢 |
| `nprobe` | 每次查询扫描的桶数 | 真正近邻在未扫描桶中，Recall 下降 |

IVF 的索引训练依赖样本能代表真实分布；只用极少或单一主题数据训练，桶就没有什么解释价值。与 HNSW 相比，IVF 常更容易控制内存和批量建索引，但参数需随数据规模重新测试。

## 可复现实验设计

不要只测一个 query。生成一份固定 query id 列表，分别在无过滤与有过滤时测试。这里的“有过滤”模拟常见的租户或状态限制；它会改变候选空间，因而可能显著改变 ANN 的真实召回。

```python
import json
from pathlib import Path

rows = [json.loads(line) for line in Path("lab-items.jsonl").read_text().splitlines()]
query_ids = [row["id"] for row in rows[::97]][:30]
Path("queries.json").write_text(json.dumps(query_ids), encoding="utf-8")
print(f"wrote {len(query_ids)} query ids")
```

每个参数组合至少保存以下字段到 CSV：`engine,index,metric,top_k,filter,parameter,query_id,latency_ms,recall_at_k`。同时保存 CPU、内存、数据量、维度和软件版本。脱离这些条件的“QPS”只是一句缺乏上下文的口号。

## 故障排查

### Recall 很低

先确认精确基准和 ANN 使用同一度量、同一 query、同一过滤。然后提高 `ef_search` 或 `nprobe`，观察 Recall 是否上升；若不上升，问题可能是索引没有真正生效、数据没有加载，或向量本身混入了不同模型版本。

### 有过滤时空结果或大幅变慢

过滤不是检索之后的装饰。可用候选很少时，ANN 需要扩大探索范围才能在合法集合中凑足 Top-K；若先 ANN 后在应用层过滤，既会漏结果，也会越权取回不该看见的数据。应对“过滤后的精确结果”单独计算 Recall@K。

### 指标很好，用户仍不满意

ANN Recall 只说明近似算法接近了当前 embedding 的精确排序，并不证明 embedding 排序符合人的意图。应另建人工标注或业务点击数据评估相关性；索引指标与模型质量是两层问题，不能互相代替。

## 小结

- 精确扫描是 ANN 的真值基准；没有真值就谈不上“召回”。
- HNSW 用多层邻居图换取速度，IVF 用聚类分桶减少扫描范围。
- 参数必须在真实 Top-K、过滤和延迟预算下测试。
- 下一章把这些概念放入 PostgreSQL，观察同一查询如何由数据库执行。
