+++
date = '2026-10-11T20:00:00+08:00'
draft = false
title = '深度学习零基础：损失函数、反向传播与梯度下降'
math = true
+++

模型输出一个数字，并不意味着它已经完成了任务。这个数字是房价、某一类的概率，还是多个类别的原始分数，取决于任务定义。训练还需要回答第二个问题：**当前预测错得有多严重，参数应当朝哪个方向调整？** 损失函数负责前半句，反向传播和优化器负责后半句。

本篇将“任务、输出、标签、损失、梯度”连成一条明确的链。类名可能更新，这些输入契约却不会因为名字变得时髦就自行消失。

## 损失与指标不是同一个东西

对一个 batch，模型先给出预测 $\hat y$。**损失函数**将预测和正确标签 $y$ 变成一个标量 $L$，训练的目标是让训练数据上的平均损失下降。这个数必须对模型参数可导，梯度才能指出优化方向。

- **损失**是训练的优化目标，要求对参数可微、数值稳定。
- **指标**用于解释效果，例如 accuracy、Precision、Recall、F1 或 MAE；它不一定适合直接反向传播。

二分类 accuracy 会在阈值处突然跳变，不能为“概率从 0.49 提到 0.50”提供连续梯度；训练常用二元交叉熵，评估时再报告 accuracy。把两者都叫“误差”能少写几个字，却会丢掉关键的因果关系。

## 任务、输出、标签和损失必须配套

先按标签的真实含义选择任务类型，再决定模型输出和损失；不要从一个熟悉的函数反推任务。

| 任务 | 模型训练输出 | 标签格式 | 常用损失 | 推理时怎样得到结果 |
| ---- | ------------ | -------- | -------- | ------------------ |
| 回归 | `[B]` 或 `[B, 1]` 的连续值 | `float32`，同 shape | `MSELoss`、`L1Loss` | 直接使用输出 |
| 二分类 | 一个 logit，`[B]` 或 `[B, 1]` | `float32` 的 `0/1`，同 shape | `BCEWithLogitsLoss` | `sigmoid` 后按阈值判断 |
| 单标签多分类 | 每类一个 logit，`[B, C]` | `long` 类别编号 `[B]` | `CrossEntropyLoss` | `argmax(dim=1)` |
| 多标签分类 | 每类一个独立 logit，`[B, C]` | `float32` 的 0/1 矩阵 `[B, C]` | `BCEWithLogitsLoss` | 每列独立 sigmoid 与阈值 |

`B` 是 batch 大小，`C` 是类别数。单标签多分类表示图片只能是“猫、狗、鸟”中的一个；多标签分类表示图片可以同时有“人、自行车、树”。两者都有多个类别，却不能交换标签编码和损失函数。

## 回归：MSE 与 L1 衡量什么

回归标签是房价、温度等连续数值。均方误差（MSE）计算预测和标签差的平方平均：

$$
\operatorname{MSE}=\frac{1}{n}\sum_{i=1}^{n}(\hat y_i-y_i)^2
$$

平方使正负误差不会抵消，也让较大的偏差受到更强惩罚。若标签中有明显异常值，这种特性会使模型更受异常值影响。平均绝对误差（MAE，`nn.L1Loss`）为：

$$
\operatorname{MAE}=\frac{1}{n}\sum_{i=1}^{n}|\hat y_i-y_i|
$$

它对异常值相对稳健。没有哪个损失只凭名字就永远更好；它表达的是你愿意如何衡量错误。

```python
import torch
from torch import nn

prediction = torch.tensor([18.0, 25.0])
target = torch.tensor([20.0, 22.0])

print(nn.MSELoss()(prediction, target).item())  # (4 + 9) / 2 = 6.5
print(nn.L1Loss()(prediction, target).item())   # (2 + 3) / 2 = 2.5
```

两个张量的 shape 都是 `[2]`。若模型输出 `[B, 1]`，标签也应明确变为 `[B, 1]`，例如 `labels.unsqueeze(1)`；不要依赖广播让代码碰巧通过。

## 二分类：logit、sigmoid 与二元交叉熵

二分类模型通常输出一个任意实数 $z$，叫作 **logit**，它还不是概率。sigmoid 将它映射到 $(0,1)$：

$$
p=\sigma(z)=\frac{1}{1+e^{-z}}
$$

当 $z=0$ 时 $p=0.5$；$z$ 越大，正类概率越接近 1。二元交叉熵（BCE）衡量标签 $y\in\{0,1\}$ 和预测概率 $p$ 的差异：

$$
\operatorname{BCE}(p,y)=-[y\log p+(1-y)\log(1-p)]
$$

若真实标签为 1，模型给出很小的概率，损失会很大；标签为 0、模型却很自信地预测 1 时也是如此。它不仅关心“分对还是分错”，也会惩罚错误的自信。

训练中应使用 `nn.BCEWithLogitsLoss()`，并直接传入 logit：

```python
from torch import nn

loss_fn = nn.BCEWithLogitsLoss()
logits = model(features).squeeze(1)  # [B]，尚未 sigmoid
labels = labels.float()              # [B]，取值为 0.0 或 1.0
loss = loss_fn(logits, labels)
```

该类内部将 sigmoid 与 BCE 合并，以更稳定的数学形式计算。因此不应先手工 sigmoid：

```python
# 错误：BCEWithLogitsLoss 会再次执行 sigmoid。
loss = loss_fn(torch.sigmoid(logits), labels)
```

只有展示概率或按业务阈值作决定时，才需要 sigmoid：

```python
probabilities = torch.sigmoid(logits)
predictions = (probabilities >= 0.5).to(torch.int64)
```

阈值 `0.5` 只适合错误代价和类别分布大致对称的入门示例。漏诊代价很高时，可能需要降低阈值并重点查看 Recall；正类极少时，只看 accuracy 往往会得到一个看似安心却没有用的数字。

## 多分类：为什么不要在 `CrossEntropyLoss` 前调用 softmax

单标签多分类的最后一层输出 `C` 个 logit，形状为 `[B, C]`。softmax 可以把每行变为和为 1 的概率：

$$
p_j=\frac{e^{z_j}}{\sum_{k=1}^{C}e^{z_k}}
$$

`nn.CrossEntropyLoss()` 已经将 `log_softmax` 和负对数似然损失合并，并以稳定的方式计算。训练代码应传入原始 logits 与一维整数类别编号：

```python
import torch
from torch import nn

logits = torch.tensor([[2.2, 0.1, -1.3], [0.2, 1.5, 0.4]])  # [B=2, C=3]
targets = torch.tensor([0, 1], dtype=torch.long)             # [B]

loss = nn.CrossEntropyLoss()(logits, targets)
classes = logits.argmax(dim=1)
```

`targets=[0, 1]` 表示第一条样本属于第 0 类、第二条属于第 1 类。基础用法中，不要先做 one-hot 向量，也不要写 `CrossEntropyLoss()(torch.softmax(logits, dim=1), targets)`；那会重复处理概率并削弱数值稳定性。

## 一个 batch 的多个损失怎样变成标量

大多数损失默认 `reduction='mean'`：先计算每条样本的损失，再求平均，最终得到标量。这使不同 batch 大小时的 loss 更容易比较。

| `reduction` | 返回结果 | 常见用途 |
| ----------- | -------- | -------- |
| `'mean'` | 一个平均损失 | 常规训练默认值 |
| `'sum'` | 一个总损失 | 有明确总量语义时；须注意 batch 大小会改变梯度尺度 |
| `'none'` | 每个样本或元素的损失张量 | 加权、过滤或定位异常样本 |

`backward()` 最常见的入口是标量 loss。若保留了多个元素的损失，先显式 `.mean()` 或 `.sum()`，才能清楚表达优化目标。

## 反向传播：梯度如何穿过网络

前向传播中，数据依次经过线性层、激活函数、输出层和损失函数，得到 $L$。反向传播从 $L$ 开始应用**链式法则**，求每个参数对损失的影响：

$$
\frac{\partial L}{\partial w}
=\frac{\partial L}{\partial \hat y}
\cdot\frac{\partial \hat y}{\partial z}
\cdot\frac{\partial z}{\partial w}
$$

参数 $w$ 的微小变化先改变线性分数 $z$，再改变预测 $\hat y$，最终改变损失 $L$。将每一段的局部变化率相乘，就得到“此刻应怎样调这个参数”。计算方向从损失指向参数，所以叫反向传播；产生预测的方向仍是从输入指向输出。

下面的单参数例子没有 sigmoid，只是为了把导数保持简单：

$$
\hat y=wx,\qquad L=(\hat y-y)^2
$$

当 $x=3$、$y=10$、$w=2$ 时，预测是 6，损失是 16。梯度为：

$$
\frac{\partial L}{\partial w}=2(\hat y-y)x=2(6-10)\times3=-24
$$

负梯度表示在当前位置附近，增大 $w$ 会使损失下降。PyTorch 会得到同一个结果：

```python
import torch

w = torch.tensor(2.0, requires_grad=True)
x = torch.tensor(3.0)
y = torch.tensor(10.0)

prediction = w * x
loss = (prediction - y) ** 2
loss.backward()

print(w.grad.item())  # -24.0
```

`requires_grad=True` 让 PyTorch 在前向计算时记录必要的关系，形成动态**计算图**。`w` 是叶子张量，梯度累积在 `w.grad`；中间结果主要用于计算，默认不会保留 `.grad`。模型的可学习参数也是叶子张量，反传后可以从每个参数的 `.grad` 取得梯度。

## 从梯度到参数更新

最简单的 SGD 更新规则为：

$$
w\leftarrow w-\eta\frac{\partial L}{\partial w}
$$

$\eta$ 是学习率。它太小，训练可能很慢；太大则可能越过低点，使损失震荡甚至发散。梯度只描述当前位置附近的下降方向，不保证任何大小的步伐都安全。

PyTorch 将更新封装到优化器中：

```python
from torch import nn

model = nn.Linear(2, 1)
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

optimizer.zero_grad()  # 清除上一批残留在 parameter.grad 中的梯度
logits = model(features).squeeze(1)
loss = loss_fn(logits, labels)
loss.backward()        # 计算并累积本批梯度
optimizer.step()       # 读取梯度，更新模型参数
```

`zero_grad()` 必须在每次更新前出现，因为 PyTorch 默认将梯度累加到 `.grad`，以支持梯度累积等训练策略；它不会替你猜测上一批梯度是否还要保留。`backward()` 计算梯度但不改权重，`step()` 改权重但不计算梯度。

## `detach()`、`no_grad()` 与 `inference_mode()`

三者都与自动求导有关，却不应互相替换：

- `tensor.detach()`：得到不再追踪既有计算历史的张量，常用于记录、转 NumPy 或隔离某一分支。
- `with torch.no_grad():`：该代码块中执行的新运算不建立计算图；离开后可记录新运算，但块内未记录的历史不能事后补回。
- `with torch.inference_mode():`：面向纯推理的更严格上下文，通常开销更低；其中创建的 tensor 不适合再参与需要 autograd 的训练计算。

训练前向过程不要误放进这些上下文，否则损失无法正确反传。部署推理通常同时使用 `model.eval()` 和 `inference_mode()`，但 `eval()` 改变的是 Dropout、BatchNorm 等层的行为，并不负责关闭梯度记录。

## 小结

- 损失函数将预测与标签的差异变为可优化标量；指标用于解释效果，两者不能混为一谈。
- 任务类型决定输出 shape、标签 dtype、损失函数和推理后处理。二分类的 BCE 与多分类交叉熵尤其不能互换。
- `BCEWithLogitsLoss` 接收原始 logit，`CrossEntropyLoss` 接收每类原始 logits；训练时不要提前 sigmoid 或 softmax。
- 反向传播用链式法则将梯度写入 `.grad`；`optimizer.step()` 才真正修改参数。
- 现在数据、张量、网络、损失和梯度都已有明确含义。下一篇才把它们放入训练循环；顺序并非仪式感，而是为了避免把接口调用误会成理解本身。
