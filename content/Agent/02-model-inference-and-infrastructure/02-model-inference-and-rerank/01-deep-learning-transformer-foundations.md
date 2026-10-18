+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '深度学习与 Transformer 基础：文本为何能得到排序分数'
math = true
+++

深度学习并不是神秘的“理解文字”。它先把文字编码为数字，再用一组可调整的参数把输入映射成输出。排序模型的输出是一个分数；训练的目的，是让相关候选的分数高于不相关候选。

## 从一个最小张量实验开始

先不下载任何模型。下面的词表把少数词映射为 ID，`Embedding` 层再把每个 ID 查成长度为 4 的向量。`[2, 3]` 表示 2 个句子、每句 3 个 token；输出 `[2, 3, 4]` 表示每个 token 都有一个 4 维向量。

```python
import torch
from torch import nn

token_ids = torch.tensor([[1, 2, 0], [3, 4, 5]])
embedding = nn.Embedding(num_embeddings=6, embedding_dim=4)
vectors = embedding(token_ids)

print(token_ids.shape)
print(vectors.shape)
print(vectors[0, 0])
```

预期输出的前两行分别类似 `torch.Size([2, 3])` 和 `torch.Size([2, 3, 4])`。最后一行是四个随机小数，数值每次不同是正常的：初始参数本来就是随机的。

`0` 在这个玩具例子中表示补齐位置（padding）。真实 tokenizer 往往还会加入 `[CLS]`、`[SEP]` 等特殊 token，并同时返回 `attention_mask`：有效 token 是 `1`，补齐 token 是 `0`。模型必须看到这个 mask，否则会把补齐也误当作文字。

## 模型如何学习

一个最小分类器由“求平均、线性层、损失函数”组成。线性层计算 $y = xW + b$；$W$ 和 $b$ 就是参数。损失（loss）衡量预测与正确答案的差距，`backward()` 根据链式法则计算每个参数该往哪个方向调整，`optimizer.step()` 才真正修改参数。

```python
import torch
from torch import nn

features = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
labels = torch.tensor([1.0, 0.0, 1.0])
model = nn.Linear(2, 1)
loss_fn = nn.BCEWithLogitsLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

for step in range(20):
    logits = model(features).squeeze(1)
    loss = loss_fn(logits, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

print(loss.item())
print(torch.sigmoid(model(features).squeeze(1)))
```

预期现象是 loss 比初始值更低，第三个样本和第一个样本的 sigmoid 输出通常更接近 1，第二个更接近 0。这里数据少得可笑，目的是看清步骤，不是训练可用模型。

### 训练和推理不能混为一谈

训练需要标签、反向传播和优化器；推理只有前向计算。推理时使用 `model.eval()` 关闭 dropout 等训练期随机行为，并用 `torch.inference_mode()` 避免构建梯度图，减少内存和开销。

```python
model.eval()
with torch.inference_mode():
    probabilities = torch.sigmoid(model(features).squeeze(1))
print(probabilities)
```

## Transformer 到底多了什么

词向量本身不知道上下文。“苹果 发布 新手机”中的“苹果”和“苹果 很甜”中的“苹果”应有不同含义。Transformer 的自注意力让每个位置根据同一句中其他位置生成新的表示。

对于每个 token 向量 $X$，模型通过三组参数生成：

$$
Q=XW_Q,\quad K=XW_K,\quad V=XW_V
$$

注意力权重与输出为：

$$
\operatorname{Attention}(Q,K,V)=\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}+M\right)V
$$

其中 $M$ 是 mask：补齐位置会被赋予极小值，使 softmax 后的权重接近 0。不要急着手算矩阵；先把它理解为“每个 token 根据任务学习该参考谁”。多头注意力会并行学习多种参考关系，随后还有前馈网络、残差连接和层归一化来稳定训练。

## 把序列变成排序分数

排序模型常将 query 和 candidate 一起编码：`[CLS] query [SEP] candidate [SEP]`。取 `[CLS]` 位置的最终向量，再接一个线性层，就得到一个 logit。logit 是没有范围限制的原始分数；需要概率解释时才经过 sigmoid。排序时通常直接比较 logit 即可。

对于同一个 query 的正例 $s^+$ 和负例 $s^-$，一种直观目标是希望前者更大：

$$
L=\max(0, m-s^+ + s^-)
$$

这里 $m$ 是希望拉开的最小间隔。真实模型会使用更多样本、更复杂的损失和预训练权重，但“提高相关项、压低不相关项”的方向并未改变。

## 常见错误与排查

- `RuntimeError: expected scalar type ...`：输入、模型参数不在同一种 dtype 或同一设备；打印 `tensor.dtype`、`tensor.device`、`next(model.parameters()).device`。
- `index out of range in self`：token ID 大于 `nn.Embedding` 的词表大小，或把 padding ID 配错了。
- loss 是 `nan`：先检查输入是否有 NaN/Inf、学习率是否过大、标签是否在损失函数要求的范围内。
- 推理结果每次不同：确认已调用 `eval()`；含 dropout 的模型在 `train()` 状态下会随机丢弃部分激活。

## 小结

- 文本先经 tokenizer 变为 token ID，再经 embedding 变为向量张量。
- 参数通过“前向计算 → loss → backward → step”学习；推理只做前向计算。
- Transformer 的关键是让 token 根据上下文更新表示，attention mask 保证 padding 不参与语义计算。
- 下一篇将讨论：为何排序系统不能把所有候选一次性交给这种精细模型。
