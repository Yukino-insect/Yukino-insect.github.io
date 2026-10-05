+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '向量数据库与向量检索实验：环境、数据与验收标准'
+++

当用户输入“适合初学者的数据库文章”时，传统数据库擅长按标题、标签或时间精确筛选，却不知道“初学者”和“入门”与哪些措辞相近。向量检索解决的是这种**按含义找近邻**的问题：先把对象表示成数字向量，再寻找几何空间中最接近的向量。

这门课不假定你学过机器学习，也不假定你已经有某个业务项目。读者会先用小数据理解向量与距离，再自己启动两种独立的数据库实验环境。产品名只在概念和实验已经站稳后出现；否则记住一串命令，和理解没有多少关系。

## 你将学会什么

完成课程后，你应能独立回答：

- Embedding、向量维度、距离度量和 Top-K 分别是什么；
- 为什么“分数最高”不总等于“最相关”，归一化又为什么重要；
- 精确检索如何作为正确性基准，HNSW、IVF 为什么能更快却可能漏掉结果；
- 如何在 PostgreSQL 的 `pgvector` 中建表、查询、查看执行计划和维护索引；
- 如何在 Milvus 中定义 collection、写入、建索引、加载和检索；
- 如何用同一数据和同一指标选择系统，并安全升级 embedding 模型。

## 学习路线

请按顺序阅读。后面的“快”建立在前面的“对”之上，跳过距离和精确检索直接调 ANN 参数，通常只会得到一份看似专业、实则无法解释的配置。

1. [Embedding、相似度与归一化](01-embedding-and-similarity.md)：从二维点和 NumPy 开始，理解向量如何比较。
2. [ANN 索引：HNSW、IVF 与可复现召回基准](02-ann-indexes.md)：用精确结果衡量近似结果。
3. [pgvector 实战](03-pgvector-practice.md)：在一套独立 PostgreSQL 容器里完成存储和查询。
4. [Milvus 实战](04-milvus-practice.md)：在另一套独立容器里完成 Collection 生命周期。
5. [向量数据库评测、选型与模型迁移](05-benchmark-selection-and-migration.md)：做可比较的实验，并处理模型升级。

## 先准备一个干净的实验目录

以下命令在 PowerShell 中执行。Python 3.10+ 与 Docker Desktop 是唯一前置条件。实验会创建名为 `vector-db-lab` 的目录；所有容器、数据文件和脚本都在这里，不修改现有应用或数据库。

```powershell
New-Item -ItemType Directory -Force .\vector-db-lab | Out-Null
Set-Location .\vector-db-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install numpy psycopg[binary] pgvector pymilvus
python --version
docker version
```

预期最后两条命令分别显示 Python 版本和 Docker Client/Server 信息。若激活脚本被当前 PowerShell 策略阻止，可只为本次窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

不要为了一个虚拟环境永久修改机器的执行策略；临时问题应使用临时权限解决。

## 统一实验数据

真实 embedding 由模型产生，本课程前两章却故意不调用模型。下面脚本用固定随机种子造出三个明显主题的 32 维单位向量，因此每次实验的结果可复现；它帮助我们分清“检索算法出了问题”和“模型语义本来就不好”这两回事。

保存为 `make_lab_data.py`：

```python
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

rng = np.random.default_rng(20261002)
dimension = 32
topics = ["database", "network", "python"]
centers = rng.normal(size=(len(topics), dimension)).astype("float32")
centers /= np.linalg.norm(centers, axis=1, keepdims=True)


def unit(values: np.ndarray) -> np.ndarray:
    return values / np.linalg.norm(values)


rows = []
for index in range(3_000):
    topic_index = index % len(topics)
    vector = unit(centers[topic_index] + rng.normal(0, 0.12, dimension))
    rows.append({
        "id": index + 1,
        "tenant_id": 1 + index % 5,
        "status": "active" if index % 23 else "inactive",
        "topic": topics[topic_index],
        "title": f"{topics[topic_index]} sample {index + 1}",
        "embedding": vector.tolist(),
    })

Path("lab-items.jsonl").write_text(
    "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
)
np.save("lab-centers.npy", centers)
print(f"wrote {len(rows)} rows, dimension={dimension}")
```

```powershell
python .\make_lab_data.py
Get-Content .\lab-items.jsonl -TotalCount 1
```

预期第一条命令输出 `wrote 3000 rows, dimension=32`；第二条输出一行 JSON，含 `id`、`tenant_id` 和长度为 32 的 `embedding`。它不是业务数据，也不代表任何真实模型效果。

## 每章都遵守的验收规则

向量数据库最危险的误解是“能返回结果就算成功”。本课程要求每次实验记录数据版本、维度、距离度量、Top-K、过滤条件和参数；ANN 还必须和精确扫描比较。

| 检查项 | 合格含义 |
| --- | --- |
| 数据契约 | 查询和库内向量来自同一模型、同一预处理、同一维度 |
| 过滤 | 租户、状态、权限等条件在服务端执行，而不是取回后再过滤 |
| 正确性 | 先有精确 Top-K 真值，才谈近似检索的 Recall@K |
| 可复现性 | 固定数据集、随机种子和 query 集，保存命令与输出 |
| 安全性 | 删除、重建和模型迁移可以重跑，并能验证结果 |

## 术语预览

- **向量（vector）**：有固定顺序的一串数字，例如 `[0.2, -0.1, 0.8]`。
- **Embedding**：把文本、图片、音频或其他对象映射为向量的模型输出。
- **维度（dimension）**：一个向量中数字的个数。32 维与 768 维不能直接比较。
- **距离度量（metric）**：定义“近”的规则，如余弦距离、内积、欧氏距离。
- **Top-K**：只返回最接近的 K 个候选。
- **向量数据库**：保存向量及其元数据，并提供向量检索、过滤、索引和运维能力的数据系统。

## 小结

- 从一个隔离目录和可复现数据开始，实验才有解释力。
- 课程顺序是：向量含义 → 精确真值 → 近似索引 → 数据库产品 → 评测与迁移。
- 下一章先解释“近”究竟是什么意思；在这之前，不必急着安装大型服务。
