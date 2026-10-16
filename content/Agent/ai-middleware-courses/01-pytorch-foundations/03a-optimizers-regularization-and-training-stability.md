+++
date = '2026-10-13T20:00:00+08:00'
draft = false
title = 'PyTorch 训练进阶：优化器、批训练、正则化与训练稳定性'
math = true
+++

上一节已经完成了一个能更新参数的训练循环。不过，能运行只是起点：同一组数据换一个学习率、batch 大小或优化器，训练速度和最终效果都可能不同。本篇解释这些选择各自改变什么，以及怎样让训练过程稳定、可比较。

## 一个 epoch 中究竟发生了多少次更新

训练通常不把整个训练集一次塞进模型，而是按 **mini-batch（小批量）** 逐批处理。若训练集有 $N$ 条样本、`batch_size` 为 $B$，一轮完整遍历训练集大约会执行：

$$
\left\lceil\frac{N}{B}\right\rceil
$$

次参数更新。完整遍历一次训练集叫作一个 **epoch**，而 `optimizer.step()` 执行一次才是一条 **step**。两者不是同一个计数单位；把 3,200 条样本按每批 32 条送入模型，一个 epoch 约有 100 个 step。

小批量是现实中的折中：逐条更新噪声大、吞吐低；全量计算梯度稳定，却常常放不进显存，也会让一次等待太久。mini-batch 能利用 CPU/GPU 并行，同时保留适度的梯度噪声。`batch_size` 变大时通常需要更多内存；它并不保证一定更准或更快收敛。

### 全量梯度究竟“更准确”在哪里

先把“准确”拆开。设第 $i$ 条样本的损失是 $\ell_i(\theta)$，训练集经验风险为：

$$
J_N(\theta)=\frac{1}{N}\sum_{i=1}^{N}\ell_i(\theta)
$$

全量梯度为：

$$
g_{full}=\nabla J_N(\theta)=\frac{1}{N}\sum_{i=1}^{N}\nabla\ell_i(\theta)
$$

对**固定的训练集和固定参数**而言，它就是这份训练集平均损失的精确梯度；每次重新计算都相同，所以更新方向稳定。它并不是“对真实世界总体规律的精确梯度”——训练集本身也只是总体的一个有限样本。

若从训练集均匀随机抽取大小为 $B$ 的 mini-batch $\mathcal B$，并使用 mean reduction，则：

$$
g_{batch}=\frac{1}{B}\sum_{i\in\mathcal B}\nabla\ell_i(\theta),
\qquad
\mathbb E[g_{batch}]=g_{full}
$$

也就是说，小批量梯度通常是全量训练集梯度的**无偏估计**：平均很多次后会指向相同方向，但单次会因抽到哪些样本而波动。样本近似独立时，batch 均值的方差大致随 $1/B$ 降低；batch 越大，单次估计越接近全量梯度，显存和每步等待也越大。

下面用四条样本的“单样本梯度”做数值例子。假设当前参数处，这四个梯度分别为 `[-6, -2, 2, 10]`：

```python
import torch

per_example_grad = torch.tensor([-6.0, -2.0, 2.0, 10.0])
print('全量梯度：', per_example_grad.mean().item())  # 1.0

for indices in ([0, 1], [0, 2], [2, 3]):
    batch_grad = per_example_grad[indices].mean()
    print(indices, batch_grad.item())  # -4.0、-2.0、6.0
```

每个小批量的方向甚至可能与全量梯度不同；这正是“噪声”。但如果随机抽取很多 batch 并取平均，结果会回到 1。loss 也是同样关系：使用 `reduction='mean'` 的 batch loss 是全量平均训练 loss 的估计，而不是天然更小或更大的一种“不同单位”。

因此应得出的结论不是“全量一定更好”，而是：全量对当前训练集更稳定、每次更新次数更少；小批量的单步更嘈杂、更新更频繁、硬件利用率更高，且噪声有时能帮助跳出狭窄区域。实际效果还受学习率、数据顺序、模型、归一化层和总训练 step 数共同影响。

## 参数、超参数与优化器各管什么

不要把模型自己学到的数和人设定的训练策略混为一谈。

| 名称 | 谁决定 | 例子 | 作用 |
| ---- | ------ | ---- | ---- |
| 参数 | 训练过程更新 | 权重、偏置 | 决定模型具体怎样计算 |
| 超参数 | 人或实验策略设定 | 学习率、batch 大小、层数 | 决定学习过程与模型容量 |
| 优化器 | 人选择、代码执行 | SGD、AdamW | 根据梯度更新参数 |
| epoch | 训练循环计数 | `epochs=20` | 表示完整遍历训练集的次数 |

最基本的 SGD 沿当前梯度的反方向走一步。Momentum 会积累一段时间的更新方向，以减弱来回震荡；Adam 会根据历史梯度为不同参数调整更新尺度；**AdamW** 则将权重衰减与 Adam 的自适应更新分开处理，是许多现代任务可靠的起点。

```python
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=3e-3,
    weight_decay=1e-4,
)
```

这不是“最优模板”。视觉任务中仔细调参后的 SGD + Momentum 也常有良好表现；小型教学模型用 Adam 也完全合理。先明确任务、数据规模和可观察的验证指标，再比较方案。否则只是在为一个尚未定义清楚的问题挑选更华丽的方向盘。

## 优化器到底读取和保存了什么

优化器并不负责求导。`loss.backward()` 已经将每个 `nn.Parameter` 的梯度写入 `parameter.grad`；创建优化器时，`model.parameters()` 将注册参数交给它；`optimizer.step()` 才根据梯度和自己保存的历史状态修改参数。对象关系如下：

```text
nn.Module 注册的 Parameter
        ↓ model.parameters()
optimizer.param_groups
        ↓ loss.backward()
每个 Parameter.grad
        ↓ optimizer.step()
Parameter 的数值 + optimizer.state 中的历史统计
```

### SGD：最直接的基线

无动量 SGD 的更新是：

$$
\theta_{t+1}=\theta_t-\eta g_t
$$

其中 $g_t$ 是当前 batch 梯度，$\eta$ 是学习率。它没有记忆，因而容易理解；但在狭长损失谷中，梯度会在陡峭方向来回摆动，向真正需要前进的方向移动缓慢。

### Momentum：让更新具有惯性

动量法引入速度 $v_t$：

$$
v_t=\mu v_{t-1}+g_t,
\qquad
\theta_{t+1}=\theta_t-\eta v_t
$$

`μ` 常取接近 1 的值，例如 0.9。若多个 batch 的梯度方向一致，速度累积；若只是单个 batch 的随机抖动，正负更新会部分抵消。它不是“自动更聪明”，而是明确假设近期方向具有参考价值。

```python
optimizer = torch.optim.SGD(
    model.parameters(), lr=1e-2, momentum=0.9, weight_decay=1e-4
)
```

### Adam：为每个参数估计步长

Adam 对每个参数梯度维护一阶矩（类似平滑方向）和二阶矩（梯度平方的平滑尺度）：

$$
m_t=\beta_1m_{t-1}+(1-\beta_1)g_t
$$

$$
v_t=\beta_2v_{t-1}+(1-\beta_2)g_t^2
$$

再做偏差修正，并按 $\sqrt{\hat v_t}+\epsilon$ 缩放更新。直觉上，持续且稳定的方向得到较明确的更新；梯度尺度很大的参数会被相对缩小步长。常见默认 `betas=(0.9, 0.999)`、`eps=1e-8` 并非定律，而是经验起点。

### AdamW：把权重衰减从自适应更新中分离

L2 正则化常写为损失中加入 $\lambda\|\theta\|^2$。对普通 SGD，它与每次将参数向 0 轻微拉回的 weight decay 近似等价；在 Adam 的逐参数自适应缩放下，这个等价不再自然成立。AdamW 显式执行衰减，再执行 Adam 更新，因而现代 Transformer 等模型常优先使用它：

$$
\theta_{t+1}=(1-\eta\lambda)\theta_t-\eta\operatorname{AdamStep}(g_t)
$$

不是所有参数都适合衰减。实践中常将 bias、LayerNorm/BatchNorm 的缩放参数排除，形成两个 parameter group：

```python
decay, no_decay = [], []
for name, parameter in model.named_parameters():
    if not parameter.requires_grad:
        continue
    (no_decay if name.endswith('bias') or 'norm' in name.lower() else decay).append(parameter)

optimizer = torch.optim.AdamW([
    {'params': decay, 'weight_decay': 1e-4},
    {'params': no_decay, 'weight_decay': 0.0},
], lr=3e-4)
```

这不是所有架构都必须照抄的名单，而是展示 parameter group 的用途：同一个优化器可对不同参数集合使用不同学习率、权重衰减或其他设置。

### 查看优化器的真实状态

第一次 `step()` 前 AdamW 几乎没有每参数历史；执行一次更新后可以查看：

```python
state = optimizer.state_dict()
print(state['param_groups'])  # 学习率、weight_decay 和参数组配置
print(state['state'])         # 每个参数的 step、exp_avg、exp_avg_sq 等
```

这里的键会以参数 ID 等内部标识组织，不适合手动编辑；但它解释了为什么断点续训不仅要加载 `model.state_dict()`，也要加载 `optimizer.state_dict()`。否则参数数值相同，动量/矩估计却从零开始，接下来的训练轨迹会改变。

## 学习率：最值得先检查的旋钮

学习率 `lr` 决定每次参数更新迈多大步。它太大时，loss 可能剧烈震荡、发散，甚至出现 `NaN`；它太小时，loss 虽然不报错却长期几乎不动。训练不佳时，学习率通常比“再叠两层网络”更值得优先检查。

不要把“调学习率”理解成凭感觉改一个神秘数字。先用一个只有一个参数的函数观察步长：

```python
import torch

for lr in (0.01, 0.2, 1.0):
    w = torch.tensor(0.0, requires_grad=True)
    for _ in range(5):
        loss = (w - 3) ** 2
        loss.backward()
        with torch.no_grad():
            w -= lr * w.grad
        w.grad.zero_()
    print(lr, round(w.item(), 3), round(loss.item(), 3))
```

梯度在这里是 $2(w-3)$，负梯度方向把 `w` 推向目标 3；`lr` 只决定每次走多远。较小的值靠近得慢，过大的值可能越过目标来回震荡。这个最小实验不能替代真实任务的搜索，但它把“学习率影响训练轨迹”变成了可以观察的事实。

实用做法是从一个保守值起步，只改一个变量并观察训练/验证曲线。例如在当前课程的小 MLP 中，可依次试 `1e-2`、`1e-3`、`3e-4`，而不是同时更换模型、batch、数据增强和优化器。实验若一次改动五处，结果再漂亮也无法说明究竟是谁起了作用。

训练后期往往需要更小的步长来细化收敛。常见调度策略包括按固定 epoch 衰减、余弦衰减，以及验证指标长期无改善时降低学习率：

```python
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode='min',
    factor=0.5,
    patience=2,
)

# 每轮验证后传入验证集损失，而不是训练集损失。
scheduler.step(valid_loss)
```

调度器只能调整步长，不能修复标签错位、数据泄漏或损失函数不匹配。先确保训练对象正确，再讨论怎样走得更优雅；顺序颠倒时，耐心通常只会被浪费得更久。

## 正则化：防止死记硬背，而不是万能加分项

训练集表现很好、验证集却明显变差时，模型可能正在过拟合。常见的缓解手段如下。

| 方法 | 核心做法 | 适合先考虑的场景 |
| ---- | -------- | ---------------- |
| 权重衰减 | 抑制权重过大 | 常规 MLP、CNN、Transformer 训练 |
| Dropout | 训练时随机暂时屏蔽部分特征 | 全连接层较多、验证差距明显时 |
| 数据增强 | 改变样本外观但保持标签 | 图像、语音等标签不随变换改变的任务 |
| 早停 | 验证集长期无改善时停止 | epoch 较多、需防止继续记忆训练集时 |
| 减小模型 | 降低表达能力 | 数据量有限且模型明显过大时 |

`weight_decay` 并非“越大越防过拟合”。如果训练集本身都学不好，增加 Dropout 或权重衰减只会进一步限制模型。处理顺序应是：先确认任务、标签、切分和训练循环；再根据训练/验证曲线判断欠拟合还是过拟合；最后选择有针对性的正则化手段。

## 训练模式、梯度裁剪与数值稳定性

有 Dropout 或 BatchNorm 时，训练和验证必须显式切换模式。训练时 `model.train()` 让 Dropout 生效、BatchNorm 使用当前 batch 的统计量；验证与推理时 `model.eval()` 关闭 Dropout，并改用累计的运行统计量。再配合 `torch.inference_mode()`，验证阶段既不更新参数，也不记录反向传播所需的计算图。

对 RNN、深网络或不稳定任务，梯度偶尔会异常大。梯度裁剪会限制更新前的总梯度范数：

```python
optimizer.zero_grad(set_to_none=True)
logits = model(features)
loss = loss_fn(logits, labels)
loss.backward()

torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

它适合处理梯度爆炸风险，但不该用来掩盖所有 `NaN`。遇到 `NaN` 或 `Inf` 时，先检查输入和标签、标准化除数、学习率、损失函数的数值稳定版本，以及混合精度下模型与输入的 dtype。`BCEWithLogitsLoss` 这类将激活与损失合并的实现，通常比先手动 sigmoid 再算损失稳定。

## 保存“最好的一轮”，而不是最后一轮

训练 loss 持续下降，并不意味着验证效果也持续变好。因此应以验证指标决定 checkpoint，而不是默认保存最后一个 epoch：

```python
best_valid_loss = float('inf')

for epoch in range(epochs):
    # 此处执行训练，并计算 valid_loss。
    if valid_loss < best_valid_loss:
        best_valid_loss = valid_loss
        torch.save(model.state_dict(), 'best-model.pt')
```

真实工程中还应同时保存模型配置、优化器状态、epoch、随机种子和数据版本。单独留下一个权重文件，往往不足以解释它为何有效，更无法稳妥地重现实验。

## 小结

- 一个 epoch 包含多个 batch 和多个 `optimizer.step()`；batch 大小同时影响内存、吞吐和梯度噪声。
- 优化器决定如何使用梯度，学习率决定每步多远；先一次只调整一个变量。
- 正则化用于处理过拟合，不能挽救还没学会训练集的模型。
- `train()` / `eval()`、数值稳定损失、梯度裁剪和最佳 checkpoint，是可靠训练循环的基本边界。

下一篇将讨论如何判断模型是否真的有用：Accuracy、Precision、Recall、F1 与阈值该怎样依据错误代价选择。
