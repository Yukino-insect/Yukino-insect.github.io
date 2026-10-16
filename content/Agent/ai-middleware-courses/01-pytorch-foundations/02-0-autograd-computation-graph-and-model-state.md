+++
date = '2026-10-16T21:00:00+08:00'
draft = false
title = 'PyTorch 自动求导与模型参数：计算图、Tensor 存储、state_dict 和 checkpoint'
math = true
+++

`loss.backward()` 经常被当成训练代码里不可省略的一句咒语，但它背后至少有四个独立问题：什么是参数，前向计算记录了什么，梯度怎样被算出来，参数和优化器状态如何被保存。若只知道“调用 `backward()` 会有梯度”，读模型加载、断点恢复和显存报错时仍会处处断裂。

本篇把这条链完整展开。它不要求你会推导深网络的全部导数，但要求你知道 PyTorch 在哪个对象上保存了什么，以及每个 API 到底改变了什么。

## 自动求导解决的是什么问题

训练要最小化经验损失：

$$
J(\theta)=\frac{1}{N}\sum_{i=1}^{N}\ell(f_\theta(x_i),y_i)
$$

- $x_i$：第 $i$ 条输入；
- $y_i$：对应标签；
- $f_\theta$：由参数 $\theta$ 决定的模型函数；
- $\ell$：单条样本的损失；
- $J$：训练集上的平均损失。

**自动求导（autograd）**不是自动寻找答案，也不是优化器。它做的是：在前向计算执行张量运算时记录依赖关系；当你从一个标量损失反向调用 `backward()` 时，按链式法则计算 $\partial J/\partial\theta$。优化器随后才读取这些梯度并修改参数。

```text
前向：参数 θ + 输入 x → 预测 → loss
记录：每一步运算怎样依赖前一步
反向：loss → 链式法则 → 每个参数的 gradient
更新：optimizer.step() 读取 gradient 并修改参数
```

没有标签和 loss 的普通推理只需要前向；没有 `optimizer.step()` 的 `backward()` 只会产生梯度，不会让模型学习。

## 从一个可手算例子看计算图

令：

$$
z=wx+b,\qquad L=(z-y)^2
$$

当 $w=2$、$b=1$、$x=3$、$y=10$ 时，$z=7$、$L=9$。根据链式法则：

$$
\frac{\partial L}{\partial w}=
\frac{\partial L}{\partial z}
\frac{\partial z}{\partial w}
=2(z-y)x=2(7-10)\times3=-18
$$

同理，$\partial L/\partial b=2(z-y)=-6$。负梯度表示在当前位置略微增大参数会降低损失。

```python
import torch

w = torch.tensor(2.0, requires_grad=True)
b = torch.tensor(1.0, requires_grad=True)
x = torch.tensor(3.0)
y = torch.tensor(10.0)

z = w * x + b
loss = (z - y).pow(2)

print(loss.item())       # 9.0
print(z.grad_fn)         # 由加法产生的反向函数
print(loss.grad_fn)      # 由 pow 产生的反向函数

loss.backward()
print(w.grad.item())     # -18.0
print(b.grad.item())     # -6.0
```

`grad_fn` 指向产生当前非叶子张量的反向规则。这里无需看懂其内部类名；关键是它说明 `z`、`loss` 不是孤立数字，而是连接到 `w`、`b` 的计算图节点。

## 叶子张量、非叶子张量和 `.grad`

上例的 `w`、`b` 是用户显式创建且 `requires_grad=True` 的**叶子张量（leaf tensor）**；它们没有 `grad_fn`，但在反向传播后默认将梯度累积到 `.grad`。

`z` 和 `loss` 是运算生成的**非叶子张量**。它们通常有 `grad_fn`，但 PyTorch 默认不保存它们的 `.grad`，因为训练真正需要更新的是叶子参数。若为了调试中间梯度而调用 `z.retain_grad()`，反传后才可以读取 `z.grad`；这会增加内存，不应成为日常训练模板。

```python
print(w.is_leaf, w.grad_fn)       # True, None
print(z.is_leaf, z.grad_fn)       # False, <AddBackward...>
```

模型的 `nn.Parameter` 本质上也是 `requires_grad=True` 的叶子 Tensor，只是被 `nn.Module` 注册为“可训练参数”。

## `requires_grad` 到底控制什么

`requires_grad=True` 表示“请为涉及它的可微运算建立反向所需记录”。它并不等于“这个数一定会被优化器更新”：优化器是否更新还取决于它是否被传入 `optimizer`、是否有 `.grad`、以及是否执行 `step()`。

以下几种操作经常被混淆：

| 操作 | 计算图 | 参数/梯度的结果 |
| ---- | ------ | --------------- |
| `tensor.requires_grad_(True)` | 从此后的运算开始追踪 | 可对该 tensor 求导 |
| `tensor.detach()` | 返回脱离当前图的视图 | 结果不再向原图反传 |
| `with torch.no_grad()` | 块内不记录普通运算 | 常用于手动更新或验证 |
| `with torch.inference_mode()` | 更严格的推理专用上下文 | 降低推理开销，不用于训练 |
| `loss.backward()` | 反向遍历已有图 | 梯度累积到叶子 `.grad` |

不要在训练中用 `.data` 绕开 autograd 修改参数。它会跳过版本检查和图的语义，错误有时不会立即爆炸，反而更难定位。参数更新应交给优化器；必须手动更新时用 `torch.no_grad()`。

### 为什么 loss 通常要化为标量

若模型有很多参数、输出有很多元素，完整 Jacobian（每个输出对每个参数的导数）会非常大。反向模式自动求导通常不显式构建整张 Jacobian，而是高效计算**向量—Jacobian 积**。标量 loss 可以看作上游向量为 1 的特例，因此 `loss.backward()` 有明确含义。

当损失保留为每样本向量，例如 `reduction='none'`，应明确说明如何聚合：

```python
per_item_loss = (prediction - target).pow(2)  # [B]
loss = per_item_loss.mean()                   # 标量，定义“平均优化目标”
loss.backward()
```

或者向非标量输出传入同 shape 的上游 `gradient`。日常监督训练中先 `.mean()` 或用损失函数默认的 mean reduction 最清楚；否则 PyTorch 无法猜测你想给每条样本多大的权重。

一次正常 `backward()` 后，PyTorch 会释放大部分中间保存量以节省内存。只有确实要对同一张图多次反传时才使用 `retain_graph=True`，并且要知道它会增加显存；它不是“第二次报错时加上即可”的通用补丁。

## 梯度为什么会累积

PyTorch 默认执行：

$$
p.\mathrm{grad}\leftarrow p.\mathrm{grad}+\frac{\partial L}{\partial p}
$$

这支持梯度累积：显存放不下一个大 batch 时，可处理多个小 batch、累加梯度，再只更新一次。但普通训练若不需要它，每次反传前都要清理旧梯度：

```python
optimizer.zero_grad(set_to_none=True)
logits = model(features)
loss = loss_fn(logits, labels)
loss.backward()
optimizer.step()
```

`set_to_none=True` 让 `.grad` 回到 `None`，通常可略省内存/写入；它的语义仍是“本次反传前没有旧梯度”。`zero_grad()` 不计算梯度，`backward()` 不更新参数，`step()` 不会替你清梯度。把三件事混为一件，训练循环自然会显得不可理喻。

## PyTorch Tensor 在对象层面保存什么

一个 Tensor 可以概念性地看成下面这组元数据：

```text
storage / data  实际数值所在的 CPU 内存或 GPU 显存
shape           每一维长度
stride          索引每一维时跨过多少存储元素
dtype           float32、float16、int64 等
device          cpu、cuda:0 等
layout          常见为 strided；稀疏 Tensor 另有布局
requires_grad   是否追踪可微运算
grad_fn / grad  反向规则或叶子参数累积到的梯度
```

`shape` 相同不代表内存布局相同。`permute()` 常改变 `stride` 而不复制数据；某些算子需要连续内存时才应调用 `.contiguous()`。这也是图像从 HWC 变 CHW 后偶尔出现“view size is not compatible”的根源：元素没有消失，只是它们在 storage 中不再按目标视图连续排列。

### 再向下一层：Python Tensor 并不直接等于一块显存

若你继续查看 PyTorch 的 C++/ATen 实现，可以把常见 eager Tensor 粗略理解为以下层次。具体字段和类名会随版本演进，不应把它当成稳定的业务 API；但这个模型足以解释 view、device 和 autograd 的行为：

```text
Python torch.Tensor
        ↓（持有 C++ 句柄）
TensorImpl：shape、stride、dtype、device、layout 等元数据
        ↓
Storage：底层内存块及其设备归属
        ↓
CPU RAM / CUDA 显存中的实际字节

AutogradMeta：requires_grad、grad、grad_fn 等求导元数据
```

`view()`、部分切片和 `permute()` 可以让多个 TensorImpl 以不同 shape/stride 解释同一 Storage，因此它们看起来“没有复制”；`clone()`、`contiguous()`（必要时）和类型/设备转换则会创建新的 storage。`.to('cuda')` 不是把 CPU 内存的指针改个标签，而是将数据复制/迁移到 CUDA 可访问的存储，并得到位于新 device 的 Tensor。

`nn.Parameter` 并不是另一种数值格式；它是 Tensor 的特殊子类/标记，使 `nn.Module` 在赋值时把它注册进参数树。模块注册、优化器 param group、autograd 元数据和 storage 是四个不同层次：不要因为它们都围绕“参数”而误以为是同一个对象。

可以用一个小实验观察这些属性：

```python
x = torch.arange(12, dtype=torch.float32).reshape(3, 4)
y = x.t()

print(x.shape, x.stride(), x.is_contiguous())  # [3,4], (4,1), True
print(y.shape, y.stride(), y.is_contiguous())  # [4,3], (1,4), False
print(y.contiguous().is_contiguous())
```

这不是要求初学者手写 stride 算法；它只是解释为何“转置看起来没有复制，某些后续操作却要求 contiguous”。

## `nn.Module` 怎样记录参数

只要将 `nn.Module`、`nn.Parameter` 或子模块赋给模块属性，PyTorch 会把它们注册到树状模块中：

```python
from torch import nn

class TinyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.hidden = nn.Linear(2, 4)
        self.scale = nn.Parameter(torch.ones(()))
        self.register_buffer('mean', torch.zeros(2))

    def forward(self, x):
        return self.hidden(x - self.mean) * self.scale

model = TinyNet()
print(list(model.named_parameters()))
print(list(model.named_buffers()))
```

- `hidden.weight`、`hidden.bias`、`scale` 是参数：会出现在 `model.parameters()`，可交给优化器；
- `mean` 是 buffer：会随模型移动设备、会进入 `state_dict()`，但默认不求导也不由优化器更新；BatchNorm 的 running mean/variance 是典型 buffer；
- 普通 Python 数字、列表或没有注册的 Tensor 不会自动成为参数或 buffer。

因此，优化器不是从某个全局变量“自动找参数”。`torch.optim.AdamW(model.parameters(), ...)` 接收的是当前模块树中已注册参数的迭代器；之后在 `step()` 中逐个读取其 `.grad`。

## `state_dict`、checkpoint 与模型文件到底有什么区别

文件扩展名 `.pt`、`.pth`、`.bin` 只是约定，不决定格式。真正要看保存时写入了什么，以及加载 API 是否匹配。

| 保存内容 | 典型保存方式 | 文件中有什么 | 恢复时还需要什么 |
| -------- | ------------ | ------------ | ---------------- |
| 模型 `state_dict` | `torch.save(model.state_dict(), path)` | 参数和 persistent buffer 的字典 | 相同模型类/配置 |
| 训练 checkpoint | `torch.save({...}, path)` | 模型、优化器状态、epoch、配置等 | 相同模型和相应优化器 |
| TorchScript | `torch.jit.save(scripted, path)` | 可执行图/模块和参数 | `torch.jit.load()` |
| safetensors | 专用库保存张量 | 不执行 Python pickle 的张量文件 | 结构、配置与 safetensors 加载器 |

观察一个 `state_dict` 最直接：

```python
state = model.state_dict()
for name, value in state.items():
    print(name, value.shape, value.dtype)

torch.save(state, 'tiny-net.pth')
```

键名往往类似 `hidden.weight`、`hidden.bias`、`mean`，值是 CPU/GPU Tensor 的数值快照。它不包含 `forward()` 的 Python 代码、训练数据或“这个模型要解决什么任务”的自然语言说明；因此加载前必须先创建同结构模型：

```python
restored = TinyNet()
state = torch.load('tiny-net.pth', map_location='cpu', weights_only=True)
restored.load_state_dict(state, strict=True)
```

`strict=True` 要求键名和 shape 都匹配。少键、多键或层宽度不同都应尽早失败，而不是带着半个模型开始推理。

## 优化器状态为何也必须保存

SGD with momentum、Adam、AdamW 不只使用当前梯度，它们还保存每个参数的历史状态。以 Adam 为例，常有一阶矩 `exp_avg` 和二阶矩 `exp_avg_sq`。这就是为什么“加载模型权重后继续训练”和“从同样权重重新开始优化”并不等价。

```python
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
epoch = 3

checkpoint = {
    'model_state': model.state_dict(),
    'optimizer_state': optimizer.state_dict(),
    'epoch': epoch,
    'config': {'lr': 1e-3, 'architecture': 'TinyNet'},
}
torch.save(checkpoint, 'checkpoint.pt')
```

恢复训练时应先重建模型和相同类型的优化器，再分别 `load_state_dict()`。仅用于部署推理时通常只保存模型权重和必要配置即可，避免把无用的优化器状态带到生产环境。

## 一次训练步骤中对象如何变化

```text
model.parameters()      参数 Tensor，初始 grad=None
        ↓ forward
logits / loss           非叶子 Tensor，带 grad_fn
        ↓ backward
parameter.grad          梯度被累积到每个叶子参数
        ↓ optimizer.step
parameter.data          参数数值改变；优化器内部状态也更新
        ↓ zero_grad
parameter.grad          清为空，等待下一批
```

这条时间线能解释大多数初学者困惑：参数来自 `nn.Module` 的注册树，梯度来自对 loss 的反向计算，优化器从传给它的参数列表读取梯度，文件则只是这些状态在某一时刻的序列化快照。

## 小结

- autograd 记录前向可微运算的依赖关系，用链式法则把 loss 的影响传回叶子参数；它不更新参数。
- `nn.Parameter` 会被 `nn.Module` 注册，`model.parameters()` 才是优化器获得参数的来源；buffer 会保存和迁移，但不参与默认优化。
- Tensor 除数值外还有 shape、stride、dtype、device、requires_grad 和计算图元数据。
- `state_dict` 是参数/buffer 字典；checkpoint 还应包含优化器和训练状态；TorchScript 是另一种可执行模块格式；扩展名本身没有语义魔法。
- 保存和加载的核心检查是结构、配置、键名、shape、dtype、设备与优化器状态是否匹配。
