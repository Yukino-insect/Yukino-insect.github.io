+++
date = '2026-10-17T20:00:00+08:00'
draft = false
title = 'PyTorch 自动求导与模型参数：从一次训练到 state_dict'
math = true
+++

前一篇已经看到过 `loss.backward()`，但如果只记住“它会算梯度”，很容易在 `zero_grad()`、`optimizer.step()`、模型保存和断点续训处重新迷路。本篇只追踪**一次最小训练**中发生的事情：一个参数从哪里来，预测怎样变成 loss，梯度写到哪里，谁修改参数，最后又怎样保存下来。

读完后，你应能把下面这段常见代码按因果关系读出来，而不是逐行背诵：

```python
optimizer.zero_grad(set_to_none=True)
prediction = model(features)
loss = loss_fn(prediction, labels)
loss.backward()
optimizer.step()
```

## 先运行一个只有两个参数的模型

从公式开始。一个一维线性模型为：

$$
z=wx+b
$$

其中 $x$ 是输入，$w$ 是权重，$b$ 是偏置，$z$ 是预测。设正确答案是 $y$，使用平方误差：

$$
L=(z-y)^2
$$

下面故意把 $w$ 设为 2、$b$ 设为 1，并输入 $x=3$、目标 $y=10$。这样预测是 7，loss 是 9，所有数字都可以手算。

```python
import torch
from torch import nn

model = nn.Linear(1, 1)
with torch.no_grad():
    model.weight.fill_(2.0)  # w=2
    model.bias.fill_(1.0)    # b=1

x = torch.tensor([[3.0]])
y = torch.tensor([[10.0]])

prediction = model(x)
loss = (prediction - y).pow(2).mean()

print('预测：', prediction.item())  # 7.0
print('loss：', loss.item())        # 9.0
```

先停在这里确认一件事：这只是**前向传播**。`model(x)` 用当前的参数计算预测，`loss` 把预测和答案转换成一个“当前错多少”的数。到目前为止，$w$ 和 $b$ 都没有改变。

## 参数从哪里来，模型又如何记住它们

`nn.Linear(1, 1)` 创建了一个 `nn.Module`。它内部有两个可训练的 `nn.Parameter`：

```python
for name, parameter in model.named_parameters():
    print(name, parameter.shape, parameter.requires_grad)

# weight torch.Size([1, 1]) True
# bias   torch.Size([1])    True
```

可以把 `nn.Parameter` 理解为“被模型登记的、默认需要梯度的 Tensor”。因为它被登记在 `model` 中，所以：

- `model.parameters()` 能找到它；
- 优化器可以接收它；
- `model.state_dict()` 会保存它；
- `model.to('cuda')` 会把它和模型一起迁移。

优化器并不会自动扫描程序里所有浮点数。它只管理创建时明确传给它的参数：

```python
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
```

这就是“参数从哪里来”的答案：参数由 `nn.Module` 注册，优化器从 `model.parameters()` 得到同一批对象的引用。

## `backward()` 具体计算了什么

现在调用：

```python
loss.backward()

print('w 的梯度：', model.weight.grad.item())  # -18.0
print('b 的梯度：', model.bias.grad.item())    # -6.0
```

PyTorch 在前向计算时已经知道：`prediction` 由 `weight`、`bias` 和 `x` 算出，`loss` 又由 `prediction` 和 `y` 算出。`backward()` 就从 loss 沿这条依赖关系反向应用链式法则。

本例可以手算验证：

$$
\frac{\partial L}{\partial w}
=
\frac{\partial L}{\partial z}
\frac{\partial z}{\partial w}
=2(z-y)x
=2(7-10)\times3
=-18
$$

$$
\frac{\partial L}{\partial b}
=
\frac{\partial L}{\partial z}
\frac{\partial z}{\partial b}
=2(7-10)\times1
=-6
$$

负号表示：在当前位置略微增大 $w$ 或 $b$，loss 会下降。**自动求导**的职责正是计算这类导数；它不会替你选择学习率，也不会自行修改参数。

## 计算图并不神秘：它只是“谁依赖谁”的记录

前向传播执行时，PyTorch 为需要梯度的运算建立临时的计算图：

```text
weight ─┐
        ├─ Linear ─→ prediction ─→ Square / Mean ─→ loss
bias ───┘                                      ↑
                                               target
```

`weight`、`bias` 是图的起点，称为**叶子张量**；它们的梯度会累积到 `.grad`。`prediction` 和 `loss` 是计算得到的中间结果，通常带有 `grad_fn`，表示“我是由哪种运算产生的”。

```python
print(model.weight.is_leaf, model.weight.grad_fn)  # True, None
print(prediction.is_leaf, prediction.grad_fn)      # False, 有对应的反向函数
print(loss.is_leaf, loss.grad_fn)                  # False, 有对应的反向函数
```

初学时只需记住：训练要更新叶子参数，所以梯度默认保存在参数 `.grad`；中间结果的 `.grad` 默认不保留。若为了调试而对中间张量调用 `retain_grad()`，会增加内存，不应成为日常训练模板。

## 为什么 loss 通常要是标量

如果一个 batch 中每条样本各有一个 loss，形状可能是 `[B]`。但“该怎样综合这 $B$ 条错误”是训练目标的一部分，框架不能替你猜。

```python
per_item_loss = (prediction - y).pow(2)  # 例如 [B, 1]
loss = per_item_loss.mean()              # 明确规定：优化平均误差
loss.backward()
```

标量 loss 的 `backward()` 表示“以 1 为上游权重，计算这个总目标对参数的梯度”。若直接对多元素 Tensor 调用 `backward()`，PyTorch 无法知道每个元素应占多大权重。真实任务有时确实需要逐样本加权，这时应显式乘权重后再求和/平均，而不是让默认行为替你做决定。

## 梯度写入 `.grad` 后，谁真正修改参数

`loss.backward()` 结束后，参数数值仍然是 2 和 1；变化只发生在 `.grad`。下一步由优化器完成：

```python
print('更新前：', model.weight.item(), model.bias.item())
optimizer.step()
print('更新后：', model.weight.item(), model.bias.item())
```

当前优化器是 `SGD(lr=0.1)`，它执行：

$$
\theta\leftarrow\theta-0.1\times\theta.\mathrm{grad}
$$

所以：

$$
w:2-0.1\times(-18)=3.8
$$

$$
b:1-0.1\times(-6)=1.6
$$

这一步之后再做前向计算，预测会更接近 10。至此，一次学习才真正发生。`backward()` 给方向，优化器决定怎样沿方向走；下一篇的优化器文章会继续解释 Momentum、Adam 和 AdamW 怎样在这里加入历史状态。

## 为什么每一批开始前都要 `zero_grad()`

PyTorch 默认将梯度**累加**到已有 `.grad`：

$$
p.\mathrm{grad}
\leftarrow
p.\mathrm{grad}+
\frac{\partial L}{\partial p}
$$

这是有意设计，便于“多个小 batch 累加后再更新”的训练策略。但普通训练希望每个 batch 只使用自己的梯度，因此完整顺序是：

```python
optimizer.zero_grad(set_to_none=True)  # 1. 清除上一批梯度
prediction = model(features)           # 2. 前向计算
loss = loss_fn(prediction, labels)     # 3. 得到标量训练目标
loss.backward()                        # 4. 将梯度写入 parameter.grad
optimizer.step()                       # 5. 根据梯度修改参数
```

`set_to_none=True` 让 `.grad` 回到 `None`，通常能少做一次置零写入；无论使用哪种形式，语义都是“不要把上一个 batch 的梯度误带进来”。

## `state_dict`：模型此刻真正需要保存的内容

训练结束或验证集变好时，最常保存的是：

```python
state = model.state_dict()
for name, value in state.items():
    print(name, value.shape, value.dtype)

torch.save(state, 'tiny-model.pth')
```

对这个模型，`state` 大致是：

```text
{
  'weight': tensor([[3.8]]),
  'bias': tensor([1.6])
}
```

它是“名字 → Tensor 数值”的字典快照。它保存参数和需要持久化的 buffer，但不保存你的 Python `forward()` 代码、训练数据、任务说明或标签含义。因此加载时必须先建立相同结构：

```python
restored = nn.Linear(1, 1)
state = torch.load('tiny-model.pth', map_location='cpu', weights_only=True)
restored.load_state_dict(state, strict=True)
restored.eval()
```

`strict=True` 会检查键名与 shape 是否匹配。若将 `[1, 1]` 的权重加载到输入维度不同的线性层，应该立刻报错；悄悄忽略不匹配只会制造更晚、更难追踪的结果错误。

### 参数与 buffer 的区别

有些模型状态需要保存，却不应由优化器更新。例如 BatchNorm 的运行均值和方差。它们通常作为 **buffer** 注册：

```python
class Center(nn.Module):
    def __init__(self):
        super().__init__()
        self.scale = nn.Parameter(torch.ones(()))
        self.register_buffer('mean', torch.zeros(2))
```

`scale` 会出现在 `named_parameters()`，`mean` 会出现在 `named_buffers()`。二者都会随 `model.to(device)` 和 `state_dict()` 移动/保存；默认只有 `scale` 有梯度并交给优化器。这正是“模型状态”比“可训练参数”更宽的原因。

## 继续训练时，为什么还要保存优化器

若使用最简单的 SGD，模型权重通常已经足够继续；但 Momentum、Adam、AdamW 会为每个参数保存历史，例如动量、`exp_avg` 和 `exp_avg_sq`。因此完整 checkpoint 常写成：

```python
checkpoint = {
    'model_state': model.state_dict(),
    'optimizer_state': optimizer.state_dict(),
    'epoch': 3,
    'config': {'lr': 0.1, 'architecture': 'Linear(1, 1)'},
}
torch.save(checkpoint, 'checkpoint.pt')
```

部署推理通常只需要模型 `state_dict` 与模型配置；断点续训则应额外恢复优化器状态、epoch、学习率调度器、随机数状态和数据版本。文件名后缀 `.pt`、`.pth`、`.bin` 没有魔法含义，关键是文件内部保存的对象和对应的加载方式。

## 再往下一层：Tensor 为什么有 shape、stride 和 device

到这里已经足以写可靠训练代码。若你对 PyTorch 底层感兴趣，可以把一个 Tensor 概念性地看成：

```text
实际数值：CPU 内存或 CUDA 显存中的 storage
如何解释数值：shape、stride、dtype、device、layout
是否参与求导：requires_grad、grad、grad_fn 等 autograd 元数据
```

`view()`、部分切片和 `permute()` 可以用不同 shape/stride 解释同一块 storage，所以不一定复制数据；`clone()`、必要时的 `contiguous()`、dtype 转换或 `.to('cuda')` 会创建/迁移存储。实现层中常可看到 `TensorImpl`、Storage、AutogradMeta 等名字，但它们是 PyTorch 内部实现细节，会随版本演进；理解上面的三层关系已经足够解释大多数 shape、连续内存和设备问题。

## 最容易混淆的结论

- 自动求导记录并计算梯度；优化器读取梯度并更新参数，两者不是同一件事。
- 参数来自 `nn.Module` 的注册树；优化器只管理传给它的 `model.parameters()` 或参数组。
- `.grad` 默认累加；除非故意做梯度累积，否则每批开始前清理。
- `state_dict` 保存参数和 buffer 的数值，不保存模型 Python 代码；加载前必须重建对应结构。
- checkpoint 比单独权重多保存优化器和训练过程状态，适合继续训练；部署推理通常不需要携带这些额外状态。

下一篇会回到“这些参数如何组成神经网络函数”：线性层、隐藏表示、激活函数和输出层各自负责什么。
