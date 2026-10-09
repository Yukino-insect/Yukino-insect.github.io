+++
date = '2026-10-07T19:00:00+08:00'
draft = false
title = 'PyTorch 零基础实战：写出第一个训练循环并学会排错'
math = true
+++

现在已经有了数据、张量、模型、损失和梯度。它们并不是五个需要分别背诵的名词，而是同一条因果链上的五个环节：数据进入模型得到预测，预测与答案产生损失，损失产生梯度，优化器根据梯度修改模型。下面会先拆开完成**一次**更新，再把它放进完整训练循环。这样你看到 `backward()` 时，至少知道它不是某种必须原样念出的咒语。

## 先完成一次参数更新

以下代码只有四条样本。它并不追求学出好模型，只用来观察参数在 `step()` 前后真的发生变化。直接复制运行：

```python
import torch
from torch import nn

torch.manual_seed(42)

# 四条样本，每条有两个特征；标签 0.0 / 1.0 表示二分类答案。
features = torch.tensor(
    [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]],
    dtype=torch.float32,
)
labels = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float32)

# 输入两个特征，输出一个原始分数（logit）。
model = nn.Linear(2, 1)
loss_fn = nn.BCEWithLogitsLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

logits = model(features).squeeze(1)
loss = loss_fn(logits, labels)

print('更新前损失：', loss.item())
print('更新前权重：', model.weight.detach().clone())

optimizer.zero_grad()
loss.backward()
optimizer.step()

print('更新后权重：', model.weight.detach())
```

请特别注意中间三句的顺序：

1. `optimizer.zero_grad()`：清空上一次遗留的梯度；
2. `loss.backward()`：从损失反向计算每个参数的梯度；
3. `optimizer.step()`：读取梯度，真正改写模型参数。

`model(features)` 只是在计算预测，`loss.backward()` 只是在填写“该怎么改”的信息；直到 `optimizer.step()`，权重才改变。可以试着临时注释最后一行再运行，便会发现权重保持不变。这比记住一句“step 很重要”更可靠。

## 为什么二分类损失要使用 logit

`nn.Linear(2, 1)` 的输出是任意实数，例如 `-1.7` 或 `2.4`，称为 **logit**。它还不是 0 到 1 的概率。若需要把它解释成概率，可使用 sigmoid：

$$
p=\sigma(z)=\frac{1}{1+e^{-z}}
$$

在上面的训练代码中，损失函数是 `BCEWithLogitsLoss`。它内部会以数值稳定的方式完成 sigmoid 和二元交叉熵计算，因此训练时应把**原始 logit** 直接传入：

```python
logits = model(features).squeeze(1)
loss = loss_fn(logits, labels)
```

不要写成 `loss_fn(torch.sigmoid(logits), labels)`。这种把 sigmoid 做两次的错误经常不会立即报错，却会妨碍训练。只有在验证或预测阶段，要把分数转换为人能理解的概率并按阈值判类时，才调用 sigmoid：

```python
probabilities = torch.sigmoid(logits)
predictions = (probabilities >= 0.5).float()
```

## 一个可直接运行的完整训练程序

下面生成一份很简单的人工数据：两个输入数字相加大于 0 时，标签为 `1`，否则为 `0`。它没有业务价值，但规律足够清晰，可以让我们集中观察训练过程。这个程序使用 320 条训练样本和 80 条验证样本。

```python
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

torch.manual_seed(42)

# 1. 生成并切分数据。每一行是一个样本，每条样本有两个特征。
features = torch.randn(400, 2)
labels = ((features[:, 0] + features[:, 1]) > 0).float()
dataset = TensorDataset(features, labels)
train_set, valid_set = random_split(dataset, [320, 80])

train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
valid_loader = DataLoader(valid_set, batch_size=80, shuffle=False)

# 2. 定义模型、损失函数和优化器。
model = nn.Sequential(
    nn.Linear(2, 8),
    nn.ReLU(),
    nn.Linear(8, 1),
)
loss_fn = nn.BCEWithLogitsLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

for epoch in range(1, 31):
    # 3. 训练：每一个 batch 都会更新一次参数。
    model.train()
    total_train_loss = 0.0
    total_train_items = 0

    for batch_features, batch_labels in train_loader:
        logits = model(batch_features).squeeze(1)
        loss = loss_fn(logits, batch_labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_train_loss += loss.item() * batch_labels.size(0)
        total_train_items += batch_labels.size(0)

    # 4. 验证：只评估，不更新参数，也不记录梯度。
    model.eval()
    correct = 0
    total_valid_items = 0
    with torch.inference_mode():
        for batch_features, batch_labels in valid_loader:
            logits = model(batch_features).squeeze(1)
            predictions = (torch.sigmoid(logits) >= 0.5).float()
            correct += (predictions == batch_labels).sum().item()
            total_valid_items += batch_labels.size(0)

    if epoch % 5 == 0:
        average_loss = total_train_loss / total_train_items
        accuracy = correct / total_valid_items
        print(f'epoch={epoch:02d}, train_loss={average_loss:.4f}, valid_accuracy={accuracy:.3f}')
```

正常情况下，`train_loss` 会总体下降，`valid_accuracy` 会升高并接近 `1.000`。每次的最后几位小数不必相同；`torch.manual_seed(42)` 固定了随机数来源，方便你在同一环境中反复比较改动。它只服务于调试和教学，不保证真实项目换设备、换库版本后仍得到完全相同的每一位结果。

## 按职责阅读训练循环

完整代码变长并不是因为它突然有了魔法，而是因为把“训练”和“验证”明确分开了：

| 代码 | 作用 | 初学者常见误解 |
| ---- | ---- | -------------- |
| `model.train()` | 切换到训练行为 | 它不会自动更新参数 |
| `logits = model(x)` | 用当前参数计算预测 | 它本身不会学习 |
| `loss_fn(logits, y)` | 计算“猜错多少” | 损失必须与输出、标签格式匹配 |
| `zero_grad()` | 清除旧梯度 | `step()` 不会自动清空梯度 |
| `backward()` | 计算梯度 | 它不直接修改权重 |
| `step()` | 用梯度更新参数 | 漏掉它，训练永远不会发生 |
| `model.eval()` | 切换到验证/推理行为 | 它不会关闭梯度记录 |
| `inference_mode()` | 不记录梯度，节省资源 | 它不会代替 `eval()` |

`train()` 与 `eval()` 在包含 dropout、batch normalization 等层时尤其重要：它们会使这些层采用训练或推理时不同的行为。`inference_mode()` 则控制自动求导是否记录计算。二者经常一起出现，但职责不同，正如钥匙和门锁一样，长得不像也不应互相代替。

## 把“训练成功”理解得更谨慎

示例数据的规律被我们亲手设定得很简单，所以准确率很高是预期结果。真实数据不会这么配合。训练时请同时查看训练损失和验证指标：

- 训练损失不下降：先确认 `zero_grad → backward → step` 都在循环中，标签与特征仍按同一行对应；
- 训练好、验证差：先检查数据切分和泄漏，再考虑模型是否太复杂、训练是否过久；
- loss 变为 `nan`：检查输入和标签是否包含 `NaN` / `Inf`，并尝试降低学习率；
- 准确率很高却没有业务价值：检查类别是否极不平衡，并改看 Precision、Recall、F1 或业务成本；
- 报形状错误：打印 `batch_features.shape`、`logits.shape` 和 `batch_labels.shape`，确认最后一维的含义。

不要在第一个结果不理想时立刻增加层数或 epoch。先用极小数据集验证代码能够过拟合：若连四条样本都无法学对，问题更可能出在数据、损失或训练循环，而不是“模型不够大”。这个小实验是排错时极其有效的基线。

## 可以安全尝试的三个改动

在原程序运行成功后，依次只改一个地方并观察输出：

1. 将 `batch_size=32` 改为 `16` 或 `64`，理解 batch 是一次更新使用的样本数量；
2. 将 `lr=0.01` 改为 `0.001`，观察较小学习率通常让学习更慢；
3. 删除 `optimizer.step()` 运行一次，再恢复它，确认参数更新发生在何处。

不要同时改五六个参数。否则结果变化后，你只能得到“似乎有影响”这种并不太有用的结论。一次只改变一个变量，是机器学习实验与普通调试都应保留的耐心。

## 小结

- 训练的固定顺序是：前向预测、计算损失、清梯度、反向传播、更新参数。
- `BCEWithLogitsLoss` 接收原始 logit；在评估时才用 sigmoid 将其转为概率和类别。
- `train/eval` 控制某些层的行为，梯度记录由 `inference_mode()` 控制；二者职责不同。
- 高训练分数不等于可用模型。必须用未参与更新的验证数据检查泛化，并首先从数据和形状排查问题。

至此，你已经可以理解并改写最小 PyTorch 训练脚本。下一阶段再学习 Transformer、embedding 或重排序模型时，仍然可以回到同一条主线：输入是什么、预测是什么、损失如何产生梯度、参数在哪里更新，以及用什么数据评价结果。

接下来请继续阅读[沿着 CleanCanvas Studio 读懂 PyTorch 图像推理调用链](04-project-inference-reading-map.md)，将训练时建立的张量、模型和推理概念落实到本项目的图像修复与超分代码中。完成本专题后，再进入[深度学习与 Transformer 基础](../02-model-inference-and-rerank/01-deep-learning-transformer-foundations.md)，把同一套逻辑放入文本 token、embedding 和排序模型的真实结构中。
