+++
date = '2026-10-07T19:00:00+08:00'
draft = false
title = 'PyTorch 理论基础：张量、矩阵计算与自动求导'
math = true
+++

`tensor` 是 PyTorch 最常出现的名词。把它粗略理解成“多维数组”并没有错，但还不够：张量还带有 `shape`、数据类型、设备，以及在训练时至关重要的梯度记录信息。理解这些属性，才能解释为什么线性层需要特定形状，为什么某些运算会报错，以及 `backward()` 到底依据什么工作。

## 从标量到批量张量

张量的 `shape` 描述每个维度的长度。以下约定很常见：第一维是 batch，其余维度描述一条样本的结构。

| 数据 | 典型 shape | 含义 |
| ---- | ---------- | ---- |
| 一个温度 | `[]` | 标量 |
| 一条 3 维特征 | `[3]` | 向量 |
| 32 条、每条 3 个特征 | `[32, 3]` | 特征矩阵 |
| 16 张 RGB、224×224 图片 | `[16, 3, 224, 224]` | 图像批次 |
| 8 条、长度 128 的 token ID | `[8, 128]` | 文本批次 |

```python
import torch

x = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
print(x.shape)       # torch.Size([2, 3])
print(x.dtype)       # torch.float32
print(x[0].shape)    # torch.Size([3])
print(x[:, 1].shape) # torch.Size([2])
```

很多模型错误本质上是 shape 错误。调试时先打印输入、模型输出和标签的形状，远比对着长堆栈猜测更可靠。特别要注意：`[batch, feature]` 与 `[feature, batch]` 虽然元素总数相同，语义完全不同；框架无法替你从数字中读出本意。

## 线性层为什么是矩阵乘法

最简单的线性模型将 $d$ 维输入 $x$ 映射为 $k$ 维输出：

$$
z=xW^T+b
$$

其中 $W$ 是形状为 $[k, d]$ 的权重矩阵，$b$ 是长度 $k$ 的偏置。对一个 batch，输入 $X$ 的形状是 $[B, d]$，输出 $Z$ 则是 $[B, k]$。PyTorch 中 `nn.Linear(d, k)` 正是这个计算；其权重保存为 `[k, d]`，所以手写时需要转置。

```python
import torch
from torch import nn

x = torch.tensor([[1.0, 2.0], [3.0, 4.0]])  # [B=2, d=2]
layer = nn.Linear(2, 3)

z = layer(x)
manual = x @ layer.weight.T + layer.bias

print(z.shape)                     # torch.Size([2, 3])
print(torch.allclose(z, manual))   # True
```

矩阵乘法的内维必须相同：`[2, 2] @ [2, 3]` 可得到 `[2, 3]`，但 `[2, 2] @ [3, 2]` 不可相乘。错误信息里的 `mat1 and mat2 shapes cannot be multiplied` 并不神秘，它只是在拒绝一个数学上未定义的操作。

### 广播：方便，但不能拿来掩盖形状错误

PyTorch 可将长度为 `k` 的 bias 自动加到 `[B, k]` 的每一行，这叫 broadcasting（广播）。它让下面的写法简洁：

```python
scores = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
bias = torch.tensor([0.1, 0.2, 0.3])
print(scores + bias)
```

但广播也会悄悄放大误用。例如预测 shape 是 `[B, 1]`，标签误写为 `[B]`，相减时可能广播成 `[B, B]`，损失仍会产生一个数字，却已经不再逐样本比较。遇到相关警告时不要压掉它；显式将二分类输出和标签同时变为 `[B]`，或同时保留 `[B, 1]`，才是清晰的契约。

## 导数告诉参数应向哪里移动

训练的目标是让损失 $L$ 变小。若某个参数为 $w$，导数 $\frac{\partial L}{\partial w}$ 描述在当前位置轻微增大 $w$ 时，$L$ 上升还是下降得多快。最简单的梯度下降更新为：

$$
w \leftarrow w-\eta\frac{\partial L}{\partial w}
$$

$\eta$ 是 learning rate（学习率）。梯度为正时，减去它会让 $w$ 变小；梯度为负时，$w$ 反而变大，方向恰好都指向局部下降。学习率太小，训练慢得像没有发生；太大则可能越过低点、来回震荡，甚至让 loss 变成 `nan`。

神经网络由许多层复合而成，不能靠手工为每个参数展开公式。若 $L=g(f(w))$，链式法则给出：

$$
\frac{dL}{dw}=\frac{dL}{df}\frac{df}{dw}
$$

这正是反向传播的数学基础：从最终损失开始，按计算的反方向逐段应用链式法则，得到每个可学习参数的梯度。

## `requires_grad`、计算图与 `backward()`

PyTorch 会在涉及 `requires_grad=True` 张量的运算中记录计算关系。对一个标量 loss 调用 `backward()` 后，叶子张量的梯度出现在 `.grad` 中。

```python
import torch

w = torch.tensor(2.0, requires_grad=True)
x = torch.tensor(3.0)
loss = (w * x - 10) ** 2

loss.backward()

print(loss.item())  # 16.0
print(w.grad.item()) # -24.0
```

这里 $L=(3w-10)^2$，当 $w=2$ 时，$\frac{dL}{dw}=2(3w-10)\cdot3=-24$。负梯度表示增大 $w$ 可以降低 loss；若学习率为 `0.1`，一次梯度下降会把 $w$ 更新为 $2-0.1\times(-24)=4.4$。代码和公式不是两套故事，只是同一件事的两种表达。

模型参数默认需要梯度，优化器读取其 `.grad` 后更新参数。梯度会累积而非自动清空，因此每一个训练 batch 前都要调用 `optimizer.zero_grad()`。推理期则应使用 `torch.inference_mode()`，既不记录计算图，也避免无用内存开销；训练和推理的职责不同，不能只凭“看起来都在调用模型”便混成一段代码。

## 小结

- shape 不是装饰信息，它定义一批数据每个维度的含义；调试时优先检查它。
- `nn.Linear(in_features, out_features)` 计算矩阵乘法加偏置，输出形状由 batch 和 `out_features` 决定。
- 广播可处理偏置等兼容维度，亦可能让错误形状静默扩散，标签和预测应显式对齐。
- 自动求导通过计算图和链式法则获得 `.grad`；优化器才会依据梯度真正修改参数。

下一篇会将数据、线性层、损失、梯度和优化器拼成一个完整训练循环，并解释怎样判断它是在学习还是只是在记忆。
