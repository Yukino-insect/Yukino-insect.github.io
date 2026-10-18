+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '文本检索与重排序：先找候选，再精细比较'
math = true
+++

若商品库有一千万条记录，让一个 Transformer 将 query 分别和一千万条文本拼接计算，等待时间会难以接受。排序系统因此通常分两步：**召回（retrieval）** 以低成本找出几十到几百个“可能相关”的 candidate，**重排序（rerank）** 再对这小批候选做昂贵但更细致的判断。

## 召回不是排序的同义词

假设用户搜索“适合办公的静音键盘”。倒排索引可按词命中寻找候选，向量索引可按语义相似度寻找候选，规则也可筛掉停售或无权限的条目。它们的共同目标是：**尽量别漏掉真正应该排在前面的东西**。如果目标候选根本没进入候选池，重排序再聪明也无从补救。

```text
query
  → 业务规则过滤（权限、库存、地域）
  → 召回 100 条候选（快，允许排序粗糙）
  → cross-encoder 逐条打分（慢，但更准确）
  → 返回前 10 条
```

预期理解是：`top_k=100` 不是神奇常数。它越大，可能提高最终质量，却会增加模型计算时间；应由离线评测和延迟预算决定。

## 两种编码方式

### Bi-encoder：分别编码，便于大范围检索

Bi-encoder 用同一个或两套编码器分别把 query 与 candidate 变成向量：

$$
\text{score}(q,d)=\frac{e_q \cdot e_d}{\|e_q\|\|e_d\|}
$$

candidate 向量可以预先计算并建立索引，因此查询时很快。代价是两个文本在编码阶段没有逐 token 交互；“键盘 静音”与“静音 鼠标”的细粒度差异不一定能被充分表达。

### Cross-encoder：一起编码，适合精排

Cross-encoder 输入的是一对文本：`[CLS] query [SEP] candidate [SEP]`。注意力层可以让 query 中的“静音”直接关注 candidate 中的“静音”“低噪”，所以通常更准确。代价是每个候选都要单独跑一次（可 batch），不能预先计算所有分数。

| 模型 | 适合位置 | 优点 | 主要代价 |
| ---- | -------- | ---- | -------- |
| Bi-encoder | 大规模召回 | 候选可预编码、便于索引 | 文本交互较弱 |
| Cross-encoder | 小候选池精排 | 能细看 query 与候选的关系 | 每对文本都要推理 |

## 最小排序实验

先用一个确定性的“词重叠分数”模拟排序过程。它不是机器学习模型，却能让我们观察输入、分数、原下标和稳定排序这些必要行为。

```python
import re

def terms(text: str) -> set[str]:
    # 中文没有天然空格；这个玩具实现把汉字按单字处理，英文仍按词处理。
    chinese = {ch for ch in text if '\u4e00' <= ch <= '\u9fff'}
    latin_words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return chinese | latin_words

def score(query: str, candidate: str) -> float:
    q, d = terms(query), terms(candidate)
    return len(q & d) / max(len(q), 1)

query = "静音 键盘"
candidates = ["静音机械键盘", "无线鼠标", "键盘收纳包"]
ranked = sorted(
    [{"index": i, "text": text, "score": score(query, text)}
     for i, text in enumerate(candidates)],
    key=lambda item: item["score"], reverse=True,
)
print(ranked)
```

预期输出中 `静音机械键盘` 位于第一位，且每项保留原始 `index`。真实模型应替换 `score`，而 API 应继续保留这种可追溯的结果结构。

## Token 长度为何会成为上限

Transformer 一次可处理的 token 数有上限，例如 512。query 与 candidate 拼接后还要占用特殊 token；候选文本过长必须截断、分段或选择字段。粗暴从末尾截断可能刚好丢掉关键条件，因此要以真实查询集验证截断策略。

例如可先设定 `max_length=256`，并记录每次截断数量。若大量候选被截断，不能只把数值调大：attention 的计算量大致随序列长度平方增长，延迟和显存都会明显上升。

## 用指标判断“排得更好”

假设人工标注了每个候选的相关等级 $rel_i$，第 $i$ 位的 DCG 可写为：

$$
DCG@K=\sum_{i=1}^{K}\frac{2^{rel_i}-1}{\log_2(i+1)}
$$

再除以理想排序的 DCG，得到 0 到 1 的 nDCG。MRR 则关注第一个正确结果的位置：$MRR=1/rank$。对于“只需尽快给一个正确答案”的任务，MRR 很有用；对于有多个好结果的搜索页，nDCG 更贴切。

```python
import math

def ndcg_at_k(relevances: list[int], k: int) -> float:
    def dcg(items):
        return sum((2 ** rel - 1) / math.log2(i + 2)
                   for i, rel in enumerate(items[:k]))
    ideal = dcg(sorted(relevances, reverse=True))
    return dcg(relevances) / ideal if ideal else 0.0

print(ndcg_at_k([2, 0, 1], 3))
```

预期输出约为 `0.96`，表示这个排列接近但不等于理想顺序。请用真实标注替换示例数字；没有标注，便没有可靠的“模型更好”结论。

## 常见错误与排查

- 精排后质量没有提升：先检查理想答案是否进入召回候选池，再看输入字段、截断比例和标注质量。
- 直接比较不同 query 的 score：这是常见误用。Cross-encoder 分数一般只适合同一 query 内排序。
- 将权限过滤交给模型：模型会犯错，权限、库存、价格范围等规则必须在排序前强制执行。
- 只用随机负例训练：随机负例太容易，模型会学到表面规律；应加入“看起来相关但实际不对”的 hard negative，并保留独立测试集。

## 小结

- 召回解决“别漏”，重排序解决“在少量候选里谁更靠前”。
- Bi-encoder 适合大范围候选生成，cross-encoder 适合小候选池精排。
- 长度、候选数和延迟相互制约；质量必须用固定标注集和指标评估。
