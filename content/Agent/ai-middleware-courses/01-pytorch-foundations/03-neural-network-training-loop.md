+++
date = '2026-10-07T19:00:00+08:00'
draft = false
title = '深度学习入门：神经网络训练循环、优化与过拟合'
math = true
+++

现在把前两篇的概念放进同一个可运行程序。一个训练循环并不复杂：模型前向计算预测，损失函数比较预测和标签，反向传播写出梯度，优化器依梯度改参数。然而每一步都有明确的边界；少一步、顺序错一次，程序也许还能执行，训练却不会按你以为的方式发生。

## 从线性模型到神经网络

线性层只能画出直线或平面。若输入与目标之间是弯曲关系，需要在层之间加入非线性激活函数。两层感知机可写为：

$$
h=\operatorname{ReLU}(xW_1^T+b_1),\qquad z=hW_2^T+b_2
$$

ReLU 定义为 $\operatorname{ReLU}(a)=\max(0,a)$。它不是为了让公式显得更深奥，而是让若干线性变换的组合不再等价于单个线性变换。最后输出 $z$ 是二分类的 logit；交给 `BCEWithLogitsLoss` 即可，不要先自行 sigmoid。

## 一个完整、最小的二分类训练脚本

以下数据是人工构造的：当两个特征之和较大时，标签更可能为 `1`。它没有业务价值，正因为如此，才能把注意力放在训练步骤而非数据下载上。

```python
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

torch.manual_seed(42)

# 1. 准备并划分数据。每行一条样本、两列特征。
features = torch.randn(400, 2)
labels = ((features[:, 0] + features[:, 1]) > 0).float()
dataset = TensorDataset(features, labels)
train_set, valid_set = random_split(dataset, [320, 80])

train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
valid_loader = DataLoader(valid_set, batch_size=80, shuffle=False)

# 2. 定义模型、损失和优化器。
model = nn.Sequential(
    nn.Linear(2, 8),
    nn.ReLU(),
    nn.Linear(8, 1),
)
loss_fn = nn.BCEWithLogitsLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)

for epoch in range(1, 31):
    # 3. 训练：允许计算梯度，并让 optimizer 更新参数。
    model.train()
    for batch_features, batch_labels in train_loader:
        logits = model(batch_features).squeeze(1)  # [B, 1] -> [B]
        loss = loss_fn(logits, batch_labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # 4. 验证：不更新参数，也不构建梯度图。
    model.eval()
    correct = total = 0
    with torch.inference_mode():
        for batch_features, batch_labels in valid_loader:
            logits = model(batch_features).squeeze(1)
            predictions = (torch.sigmoid(logits) >= 0.5).float()
            correct += (predictions == batch_labels).sum().item()
            total += batch_labels.numel()

    if epoch % 5 == 0:
        print(f"epoch={epoch:02d}, train_loss={loss.item():.4f}, "
              f"valid_accuracy={correct / total:.3f}")
```

正常情况下，验证准确率会逐渐升高。每次运行的具体数字可以不同，但若 loss 长期不下降、准确率接近随机猜测，应先检查标签是否与样本对齐、损失函数是否接受当前输出格式、是否漏写 `optimizer.step()`，而不是立刻增加层数。问题若在输入边界，堆叠网络只会更快地把它掩埋。

## 训练循环中每句代码的职责

| 代码 | 职责 | 常见误用 |
| ---- | ---- | -------- |
| `model.train()` | 使 dropout、batch normalization 进入训练行为 | 验证时忘记切 `eval()` |
| `logits = model(x)` | 前向计算原始输出 | 提前误做 sigmoid/softmax |
| `loss_fn(logits, y)` | 将预测与标签变成可优化标量 | 标签 dtype 或 shape 不匹配 |
| `zero_grad()` | 清空上个 batch 累积的梯度 | 误以为 `step()` 会自动清零 |
| `loss.backward()` | 依计算图写出参数梯度 | 对非标量 loss 直接调用且没有说明 |
| `optimizer.step()` | 使用梯度更新参数 | 漏写后参数永远不变 |
| `model.eval()` + `inference_mode()` | 稳定且低开销地验证/推理 | 验证阶段仍保留梯度图 |

`train()` 和 `eval()` 不会自动开关梯度；`inference_mode()` 也不会替模型切换 dropout 的行为，因此它们常成对出现却不能互相取代。理解两者差异，能避免很多“同一个输入为何每次预测不同”的困惑。

## batch、epoch、学习率与优化器

- **batch**：一次用于计算一份梯度的样本数。更大 batch 的梯度通常更稳定，却需要更多内存，并不保证泛化更好。
- **epoch**：训练集被完整遍历一次。30 个 epoch 不是普遍正确值，应由验证曲线决定。
- **learning rate**：单步更新幅度。它通常是最敏感的超参数；过大使 loss 抖动或发散，过小则几乎不学习。
- **SGD / Adam**：都是更新参数的优化器。SGD 简单直接；Adam 会基于历史梯度调整不同参数的步长，常是小实验方便的起点，但并不免除学习率调试。

训练 loss 只对应最后一个 batch 当然不够严谨；生产实验应累计所有 batch 的加权平均，并记录训练和验证的曲线。示例为了突出骨架而保持简短，不能因此误解为日志设计的范本。

## 过拟合：会背题不等于会解题

模型容量变大、训练太久、训练样本太少或标签存在偶然噪声时，训练 loss 可能持续下降，验证损失却先降后升。这就是过拟合。处理它应从证据出发：

1. 保持验证集独立，画出训练与验证曲线；
2. 增加覆盖真实场景、标签可信的数据；
3. 适当降低模型复杂度，或使用 weight decay、dropout、数据增强；
4. 依据验证指标早停，而非机械追求更多 epoch；
5. 最后用从未参与选择的测试集评估一次。

weight decay 可以理解为对过大的权重施加约束，常在优化器中写为 `weight_decay=1e-4`。dropout 则在训练期随机置零一部分激活，迫使网络不过分依赖某一条路径。它们是降低过拟合风险的工具，不是弥补错误标签、泄漏数据或不匹配指标的万能药。

## 常见现象的排查顺序

- **loss 完全不变**：确认参数确实在优化器中、没有漏掉 `zero_grad → backward → step`，并打印一个参数在更新前后的值。
- **loss 为 `nan`**：检查输入和标签是否有 `NaN`/`Inf`，再尝试降低学习率，确认损失函数的输入范围和 dtype。
- **训练分数高、验证分数低**：检查数据泄漏与切分方式，再考虑正则化、早停或更多高质量数据。
- **准确率很高但业务效果差**：检查类别是否极不平衡，改看 Precision、Recall、F1 或任务定义的成本指标。
- **每次验证结果不同**：确认验证前调用 `model.eval()`，并固定随机种子以便调试；可复现不等于永远相同，却能让差异有迹可循。

## 小结

- 最小训练循环的因果顺序是：前向预测、计算损失、清梯度、反向传播、更新参数。
- `train/eval` 控制部分层的行为，梯度记录由自动求导上下文控制；二者不能相互替代。
- 学习率、batch、epoch 和优化器是需要验证集支撑的超参数，不是可凭印象固定的常数。
- 训练分数并不代表模型可用；泛化、数据泄漏和业务指标必须单独检验。

至此，你已经具备阅读和改写简单 PyTorch 训练代码所需的理论基础。接下来可进入[深度学习与 Transformer 基础](../02-model-inference-and-rerank/01-deep-learning-transformer-foundations.md)，将这套训练逻辑放到文本 token、embedding 和排序模型的真实结构中。
