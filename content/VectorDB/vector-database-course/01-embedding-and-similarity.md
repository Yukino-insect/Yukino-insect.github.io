+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'Embedding、相似度与归一化：用 NumPy 验证检索分数'
math = true
+++

上一章生成了一批数字，但数字为何能表达“相似”？先不要把它神秘化。Embedding 是模型做出的坐标分配：训练目标使语义或特征相近的对象倾向落在邻近区域。它是模型的表示，不是原文的加密版，也不是天然正确的事实判断。

本章只解决一个问题：给定查询向量，如何严格地排出“最接近”的对象。这个问题看似基础，却决定了后续索引、数据库操作符和评测是否都在做同一件事。

## 先看问题：同一批点可以有不同排序

二维空间更容易观察。查询点在右上方；若我们只比较夹角，方向一致的点更近；若比较直线距离，长度也会影响结果。

```text
          y
          ^       query (2, 2)
          |          *
          |     B *
          | A *
          +----------------> x
```

“距离”不是向量自带的属性，而是人为选定的函数。选错函数，数据库仍会忠实执行，只是忠实地返回错误排序。

## 基础术语与公式

向量 $x=[x_1, x_2, \ldots, x_d]$ 的维度为 $d$。两向量的常见比较方法如下。

### 点积与余弦相似度

点积为：

$$
x \cdot y = \sum_{i=1}^{d}x_i y_i
$$

向量长度（L2 范数）为 $\lVert x \rVert_2=\sqrt{x \cdot x}$。余弦相似度只看夹角：

$$
\operatorname{cosine}(x,y)=\frac{x\cdot y}{\lVert x\rVert_2\lVert y\rVert_2}
$$

欧氏距离是两点的直线距离：

$$
d_2(x,y)=\sqrt{\sum_{i=1}^{d}(x_i-y_i)^2}
$$

**L2 归一化**将非零向量除以自身长度，使长度变为 1。对于单位向量，余弦相似度、内积与 L2 距离严格单调对应：

$$
\lVert x-y\rVert_2^2=2-2(x\cdot y)
$$

所以单位化后，用三种方式排序应一致；没单位化时则不保证。这是可验证的结论，不是记忆题。

## 最小实验：亲自比较三种排序

在实验目录中新建 `similarity_demo.py`：

```python
import numpy as np

query = np.array([1.0, 1.0])
items = {
    "same_direction_long": np.array([10.0, 10.0]),
    "nearby": np.array([1.1, 0.9]),
    "different_direction": np.array([-1.0, 1.0]),
}


def normalize(vector: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vector)
    if length == 0:
        raise ValueError("zero vector cannot be normalized")
    return vector / length


def report(q: np.ndarray, values: dict[str, np.ndarray]) -> None:
    for name, vector in values.items():
        dot = float(q @ vector)
        cosine = dot / (np.linalg.norm(q) * np.linalg.norm(vector))
        l2 = float(np.linalg.norm(q - vector))
        print(f"{name:22} dot={dot:7.3f} cosine={cosine:6.3f} l2={l2:7.3f}")
    print("dot order:", sorted(values, key=lambda n: q @ values[n], reverse=True))
    print("cos order:", sorted(values, key=lambda n: (q @ values[n]) / (np.linalg.norm(q) * np.linalg.norm(values[n])), reverse=True))
    print("l2 order: ", sorted(values, key=lambda n: np.linalg.norm(q - values[n])))


print("before normalization")
report(query, items)
print("\nafter normalization")
report(normalize(query), {name: normalize(v) for name, v in items.items()})
```

```powershell
python .\similarity_demo.py
```

预期在 `before normalization` 中，点积把 `same_direction_long` 排在前面，因为它长度很大；L2 距离把 `nearby` 排在前面。`after normalization` 中三组排序都应以 `same_direction_long`、`nearby`、`different_direction` 的同一顺序出现。具体小数不必手抄，排序才是结论。

## 从文本到向量：模型实际做了什么

文本 embedding 模型通常先将文本切成 token，经过神经网络得到每个 token 的隐藏状态，再通过池化得到固定长度向量。简化流程如下：

```text
"数据库索引入门"
  -> tokenizer: [token id ...]
  -> neural network: [token, hidden dimension]
  -> pooling: [hidden dimension]
  -> optional L2 normalization: vector
```

“固定长度”不代表不同模型可以混用。向量空间由训练数据、tokenizer、模型权重、池化方法、提示词前缀和归一化共同定义。即使两个模型恰好都是 768 维，彼此向量也没有可比较的坐标含义。

## 参数与选择：先问模型的契约

在创建索引前，应记录模型文档或自己的实验结论：

| 问题 | 为什么重要 |
| --- | --- |
| 输出维度是多少？ | 数据库列和 collection 必须完全匹配 |
| 是否建议归一化？ | 决定余弦、内积和 L2 是否能互换 |
| 输入如何截断？ | 截断会直接改变检索质量 |
| 查询与文档是否有不同前缀？ | 有些检索模型要求不同提示词 |
| 分数方向是什么？ | 避免把“距离最小”写成“分数最大” |

## 常见故障与排查

### 零向量和 NaN

归一化零向量会除以 0；包含 `NaN` 的向量会污染排序。写入前应检查：

```python
def validate_embedding(vector: np.ndarray, dimension: int) -> None:
    if vector.shape != (dimension,):
        raise ValueError(f"expected dimension {dimension}, got {vector.shape}")
    if not np.isfinite(vector).all():
        raise ValueError("embedding contains NaN or infinity")
    if np.linalg.norm(vector) == 0:
        raise ValueError("embedding is a zero vector")
```

### 结果看似随机

先检查四项，而不是立刻换数据库：查询和文档是否同一模型版本、是否使用同一预处理、维度是否一致、距离方向是否颠倒。对固定 query 手工打印前十个 `id` 和分数；如果精确扫描都不合理，索引没有责任替模型补救。

### 元数据过滤后结果太少

“先取 Top-K 再在应用层过滤”会丢掉本来排在第 K+1 的合法对象。过滤必须成为数据库查询的一部分；第二章会用此现象解释 ANN 的评测。

## 小结

- Embedding 是模型生成的坐标表示，只有同一表示空间内的向量才可比较。
- 距离函数定义“近”；分数方向必须在接口边界写清楚。
- 单位化后，余弦、内积和 L2 的排序可对应；未单位化时不能想当然。
- 下一章用精确扫描作为真值，再学习为何索引可以牺牲少量准确性来换速度。
