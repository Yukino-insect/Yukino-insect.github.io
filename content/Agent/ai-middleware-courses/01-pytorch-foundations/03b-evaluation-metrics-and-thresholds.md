+++
date = '2026-10-13T20:00:00+08:00'
draft = false
title = '深度学习评估：Accuracy、Precision、Recall、F1 与分类阈值'
math = true
+++

训练循环打印出 `accuracy=0.95`，并不自动说明模型适合上线。它只说明：在当前验证集、当前阈值和当前类别分布下，预测正确的比例是 95%。如果漏掉一例疾病、欺诈或安全风险的代价很高，或者正类本身很稀少，这个数字可能恰好掩盖了最重要的问题。

## 先从二分类的四种结果读起

二分类将模型的概率与阈值比较，例如 `probability >= 0.5` 预测为正类。每一条样本都会落入下面四种情况之一。

| 真实情况 / 模型预测 | 正类 | 负类 |
| ------------------- | ---: | ---: |
| 实际为正类 | TP：正确命中 | FN：漏报 |
| 实际为负类 | FP：误报 | TN：正确排除 |

- **TP（true positive）**：真实为正，模型也报正；
- **TN（true negative）**：真实为负，模型也报负；
- **FP（false positive）**：误报，实际为负却报正；
- **FN（false negative）**：漏报，实际为正却报负。

先问清 FP 和 FN 哪个更昂贵，再选择指标与阈值。垃圾邮件初筛可以容忍一定漏报，却不应把正常邮件大规模拦截；疾病筛查则往往宁愿多复检，也不愿漏掉真正患者。指标不是模型的奖状，而是把业务错误代价翻译成可观察的信号。

## Accuracy 为什么不总可靠

准确率定义为：

$$
Accuracy=\frac{TP+TN}{TP+TN+FP+FN}
$$

若验证集中 99% 都是负类，一个永远预测负类的模型也能得到 99% Accuracy，却找不到任何正类。这不是公式错了，而是它平等地把每一条样本算作一次正确或错误，无法表达少数类的重要性。

因此，类别不均衡时至少应额外报告混淆矩阵，并关注下列指标。不要只保留一个好看的总分；那种做法和只看考试总分却不看哪道关键题全错，并没有本质区别。

## Precision、Recall 与 F1 分别回答什么

$$
Precision=\frac{TP}{TP+FP},\qquad Recall=\frac{TP}{TP+FN}
$$

**Precision（精确率）** 问的是：“模型判为正的样本里，有多少真的为正？”它高，说明误报少。**Recall（召回率）** 问的是：“所有真实正类中，有多少被模型找到了？”它高，说明漏报少。

F1 使用调和平均在两者之间取平衡：

$$
F1=2\cdot\frac{Precision\cdot Recall}{Precision+Recall}
$$

当 Precision 或 Recall 中任一个很低时，F1 会被明显拉低，因此比简单平均更能防止“一边很好、另一边几乎没用”的假象。不过 F1 也不是默认唯一答案：若业务明确更怕漏报，应优先以 Recall 和漏报量约束模型；若人工复核成本很高，则通常更在意 Precision。

## 阈值不是永远固定在 0.5

二分类模型常输出 logit，转换为概率后再由阈值判类：

```python
probabilities = torch.sigmoid(logits)
predictions = (probabilities >= threshold).long()
```

`0.5` 只是一个可解释的默认值。提高阈值会让模型更谨慎：通常正类预测更少，Precision 可能上升、Recall 可能下降；降低阈值则相反。正确做法是在验证集上比较候选阈值，并依据 FP/FN 的业务成本、人工处理能力与最低召回要求做决定。阈值本身也是由验证集选出的超参数，不能在测试集上反复试到满意为止。

下面的示例计算一个固定阈值下的四种计数。它刻意使用原始张量，以便你看清指标从哪里来：

```python
import torch

probabilities = torch.tensor([0.95, 0.72, 0.48, 0.11, 0.63])
targets = torch.tensor([1, 0, 1, 0, 1])
threshold = 0.5

predictions = (probabilities >= threshold).long()
tp = ((predictions == 1) & (targets == 1)).sum().item()
tn = ((predictions == 0) & (targets == 0)).sum().item()
fp = ((predictions == 1) & (targets == 0)).sum().item()
fn = ((predictions == 0) & (targets == 1)).sum().item()

precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

print({'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn})
print({'precision': precision, 'recall': recall, 'f1': f1})
```

真实项目还应保留对应的错误样本，而非只留下统计量。检查最高置信度的 FP 与 FN，经常能发现标签问题、输入缺失、群体偏差或任务定义本身的漏洞。

## PR-AUC、ROC-AUC 与多分类的边界

当你关心不同阈值下的性能时，可以观察整条曲线。**PR 曲线**展示 Precision 与 Recall 的取舍；正类稀少时，**PR-AUC** 往往比 Accuracy 和 ROC-AUC 更有解释力。**ROC 曲线**展示真正例率与假正例率的关系，ROC-AUC 衡量不同阈值下的整体排序能力，但在极端不均衡数据上可能显得过于乐观。

多分类任务不能直接把多个类别的分数当作互不相关的二分类结果。单标签多分类通常以 `argmax(logits, dim=1)` 选唯一类别，再按类别计算混淆矩阵、每类 Precision/Recall/F1，以及 macro、weighted 等聚合方式。多标签任务才是每个标签各自 sigmoid、各自设阈值。请先确认“一个样本能否同时属于多个类别”，再选择计算方式。

## 一份可复核的评估报告至少包含什么

- 验证或测试集的来源、切分时间与群体边界；
- 每个指标的数值、阈值和样本量；
- 混淆矩阵，或至少 TP、TN、FP、FN；
- 类别分布与宏平均/加权平均的说明；
- 代表性的高置信度错误样本及其分析；
- 指标与业务成本的对应关系。

只报一个 Accuracy，无法让其他人判断模型在哪儿有效、在哪儿会造成损失。可复核的报告不是额外文书，而是防止团队被单一数字误导的最小代价。

## 小结

- Accuracy 适合类别较均衡、各类错误代价相近的场景；不均衡任务不能单独依赖它。
- Precision 关注误报，Recall 关注漏报，F1 用于需要兼顾两者的情况。
- 阈值由业务代价决定，应在验证集上选择并固定，再到测试集做最后评估。
- 指标必须配合混淆矩阵和错误样本分析，才能变成可信的模型结论。

接下来会从模型架构的角度回到一个更早的问题：面对表格、图像和序列，为什么不应总用同一种网络。
