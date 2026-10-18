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

## 先建立一张抽象地图：谁保存什么，谁执行什么

一段 PyTorch 训练代码看起来像连续的函数调用，实际上包含几层不同职责的对象。把它们混成“模型在算 loss、优化器在求导”是后续读代码最常见的起点错误。

| 抽象 | 典型对象 | 输入与输出 | 负责的事 | 不负责的事 |
| --- | --- | --- | --- | --- |
| 数据与可微计算 | `torch.Tensor` | Tensor → Tensor | 保存数值、shape、dtype、device，并参与张量运算 | 自动成为模型参数 |
| 模型容器 | `nn.Module` | 输入 Tensor → 输出 Tensor | 组织子层、参数、buffer 和 `forward()` | 自动选择训练目标或更新规则 |
| 可训练模型状态 | `nn.Parameter` | 一种特殊 Tensor | 被 `Module` 注册，默认需要梯度 | 自己计算梯度或修改自己 |
| 训练目标 | `nn.Module` 损失类或 `torch.nn.functional` 函数 | 预测、标签 → loss Tensor | 把“预测好坏”的任务约定写成可微运算 | 更新模型参数 |
| 参数更新策略 | `torch.optim.Optimizer` 的子类 | 参数及其 `.grad` → 原地更新后的参数 | 管理学习率和动量等状态，并修改参数 | 从预测自动推断 loss |
| 自动求导系统 | autograd 引擎 | 前向运算记录 → 参数梯度 | 沿计算依赖关系应用链式法则 | 决定学习率和何时保存模型 |

所以，一次训练的因果链是：`Tensor` 承载输入和参数，`Module` 将若干可微运算组合成模型，损失函数把模型输出变成训练目标，autograd 为这个目标求参数梯度，最后 optimizer 读取 `.grad` 并原地改写参数数值。

```text
features ──→ model: nn.Module ──→ prediction: Tensor
                                      │
labels ───────────────────────────────┼──→ loss_fn ──→ loss: Tensor
                                      │                    │
                                      └─ autograd 记录依赖 ┘
                                                           │ backward()
parameters: nn.Parameter  ←────────────── parameter.grad ──┘
        │
        └──────── optimizer.step() 原地更新参数
```

这是一套 Python 可见的对象接口，但不能把它理解成“PyTorch 用 Python 循环实现了神经网络和求导”。Python 的类、属性和方法主要负责**表达模型结构与调用协议**；高性能张量算子、CPU/CUDA 内核和反向传播调度由 PyTorch 的底层实现执行。稍后会再准确划清这条边界。

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

## `nn.Module`：用 Python 对象表示一个可组合的模型

`nn.Module` 是 PyTorch 中最核心的**模型抽象基类**。线性层 `nn.Linear`、卷积层 `nn.Conv2d`、激活层 `nn.ReLU`、完整的 ResNet，以及我们自己写的网络，都是它的子类或由它们组合而成。它约定了三件事：

- 在 `__init__()` 中创建并持有层、参数和 buffer；
- 在 `forward()` 中定义“输入如何变成输出”；
- 通过 `model(input)` 这一统一入口完成调用、hook 处理和 `forward()` 执行。

下面的模型和前一节的 `nn.Linear(1, 1)` 数学上完全等价，但把结构显式写了出来：

```python
import torch
from torch import nn


class TinyRegressor(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(in_features=1, out_features=1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


tiny_model = TinyRegressor()
x = torch.tensor([[3.0]], dtype=torch.float32)
prediction = tiny_model(x)

print(prediction.shape)  # torch.Size([1, 1])
print(prediction.dtype)  # torch.float32
```

逐行看这段代码：

- `class TinyRegressor(nn.Module)` 使用 Python 的**继承**，表示该类遵守 `Module` 的模型协议；它不是给任意 Python 类贴一个标签。
- `super().__init__()` 必须先初始化父类内部用于登记模块、参数和 buffer 的容器。漏掉它时，把层赋给 `self.linear` 会出错或无法被正确管理。
- `self.linear = nn.Linear(1, 1)` 使用**对象组合**：`TinyRegressor` 不是手写矩阵乘法，而是持有一个子模块。`in_features=1` 要求最后一个输入维度为 1；`out_features=1` 使输出最后一个维度为 1；`bias=True` 额外创建偏置参数。
- `forward()` 的输入 `x` 是形状 `[batch_size, 1]` 的浮点 Tensor。示例的 `[[3.0]]` 中 batch size 是 1，因此输出也是 `[1, 1]`。类型标注帮助读者和工具理解接口，但不会在运行时自动把错误 shape 修正好。
- `model(x)` 返回预测 Tensor。这里的 Tensor 与模型参数同为 `float32`、同在 CPU；真实项目中还必须让输入和模型处于相同 device，否则会报错。

### 为什么写 `model(x)`，却实现 `forward(x)`

`model(x)` 是 Python 的调用语法。解释器会调用对象的特殊方法 `model.__call__(x)`；`nn.Module` 提供了这个 `__call__` 实现，并在合适的内部流程中调用子类的 `forward(x)`。因此通常应写：

```python
prediction = model(x)       # 推荐：走 Module 的完整调用入口
prediction = model.forward(x)  # 不推荐：直接调用实现细节
```

两种写法在这个简单例子里数值可能相同，但前者能保留 `Module` 的前向/反向 hook、编译与其他框架机制所依赖的入口约定。`forward()` 是你定义网络函数的位置；`__call__()` 是框架把这个函数纳入统一调用生命周期的位置。`train()` 与 `eval()` 也只是切换模块树中的 `.training` 标志，是否改变计算要由 Dropout、BatchNorm 等具体层的 `forward()` 根据该标志决定。

### 注册不是普通赋值：`Module` 如何找到子层和参数

普通 Python 对象中，`self.answer = 42` 只是把一个属性放到对象上。`nn.Module` 则重写了属性赋值相关的 Python 协议：将一个 `nn.Module`、`nn.Parameter` 或通过专门方法注册的 buffer 赋给模块属性时，它除了保留属性访问方式，还会按名称记录到自己的注册表中。

```python
class RegistrationDemo(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(2.0))
        self.offset = torch.tensor(1.0)  # 普通 Tensor，不会自动注册为参数
        self.relu = nn.ReLU()
        self.register_buffer('version', torch.tensor(1, dtype=torch.int64))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(x * self.scale + self.offset)


demo = RegistrationDemo()
print(list(demo.named_parameters()))  # [('scale', Parameter containing: tensor(2., ...))]
print(list(demo.named_buffers()))      # [('version', tensor(1))]
print(list(demo.named_modules()))      # 包含自身和子模块 relu
```

这个例子刻意放入了三种状态：

- `scale` 是 `nn.Parameter`，所以进入 `named_parameters()`，可被优化器更新并写入 `state_dict()`；
- `relu` 是子 `nn.Module`，所以进入模块树；它没有可训练参数，但它的 `forward()` 仍会参与整个模型计算；
- `version` 使用 `register_buffer()` 显式登记为 buffer，会随 `state_dict()` 保存、随 `model.to(device)` 迁移，却不交给优化器；
- `offset` 只是普通 Tensor 属性，既不在参数也不在 buffer 中。它仍可参与本次 CPU 前向计算，但不会自动随模型迁移和保存。若它代表固定模型状态，应改用 `register_buffer()`。

为便于理解，可以把 `Module` 内部的注册关系概念化为 `_parameters`、`_buffers` 和 `_modules` 三张“名字 → 对象”的映射。它们是实现细节，业务代码应使用 `named_parameters()`、`named_buffers()` 和 `named_modules()` 等公开接口，而不是直接修改以下划线开头的属性。

这种自动登记依赖 Python 的类、继承、属性赋值拦截和对象引用；但登记后的 `nn.Linear` 矩阵乘法并不靠 Python 的 `for` 循环实现。模型树只是告诉 PyTorch“哪些对象属于模型”，实际张量计算仍交给底层算子。

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

### `Parameter` 是 Tensor 的子类，但“可训练”还需要完整链路

`nn.Parameter` 可以看作带有“请 Module 将我视为参数”语义的 Tensor 子类。它默认 `requires_grad=True`；但这不表示每个 `requires_grad=True` 的 Tensor 都会被模型保存或被 optimizer 更新。

```python
plain = torch.tensor(2.0, requires_grad=True)
registered = nn.Parameter(torch.tensor(2.0))

holder = nn.Module()
holder.plain = plain
holder.registered = registered

print(plain.requires_grad, registered.requires_grad)  # True True
print(list(holder.named_parameters()))                # 只有 registered
```

`plain` 仍能参加计算图并在 `backward()` 后获得 `.grad`，但它没有因为被赋值给 `holder` 就成为模型参数。要更新一个量，至少要同时满足三个问题的答案：它是否需要梯度（`requires_grad`）？它是否被模型正确注册（`Parameter`）？它是否被传给某个 optimizer（`optimizer` 的参数组）？少任意一个，常规训练循环都不会修改它。

反过来，`Parameter` 的值也不该在普通前向传播中用原地写操作随意改动。optimizer 会在不构建新的训练计算图的上下文中专门更新它；手动初始化才像文章开头那样放进 `torch.no_grad()`，明确表示“这是设定初值，不是一个需要求导的训练运算”。

## 损失函数：同一训练目标可以是 `Module`，也可以是函数

损失函数接收模型预测和目标标签，返回一个可微 Tensor。它定义的是任务约定，而不是模型结构的一部分。对回归问题，均方误差（MSE）常写为：

$$
L=\frac{1}{N}\sum_{i=1}^{N}(\hat{y}_i-y_i)^2
$$

其中 $N$ 是参与平均的元素个数，$\hat{y}_i$ 是第 $i$ 个预测值，$y_i$ 是对应真值。文章开头的 `mean()` 手写式正是这个公式。PyTorch 为同一个计算提供两类常见接口：

```python
import torch.nn.functional as F

mse_prediction = torch.tensor([[7.0]], requires_grad=True)
mse_target = torch.tensor([[10.0]])

loss_module = nn.MSELoss(reduction='mean')
loss_from_module = loss_module(mse_prediction, mse_target)
loss_from_function = F.mse_loss(mse_prediction, mse_target, reduction='mean')

print(loss_from_module.shape, loss_from_module.item())  # torch.Size([]), 9.0
print(loss_from_function.shape, loss_from_function.item())  # torch.Size([]), 9.0
```

`nn.MSELoss` 是 `nn.Module` 子类，`loss_module(prediction, target)` 同样经过 `__call__()` 再进入它的 `forward()`；`F.mse_loss` 则是一个直接调用的函数式接口。此处二者都没有待训练参数，数值结果相同。选 Module 形式常是为了把固定配置（例如 `reduction='mean'`）作为对象状态和模型风格的一部分；选 functional 形式常用于一次性的无状态运算。

并不是所有损失都完全无状态。例如 `nn.CrossEntropyLoss(weight=class_weight)` 可携带类别权重；有些模块还会持有 buffer。无论采用哪种接口，**loss 的返回 Tensor 才是 autograd 的起点**，而不是损失对象本身。

`reduction` 不能一笔带过：

- `'none'` 保留逐元素损失，形状通常与输入相同；
- `'sum'` 求和，batch 变大时梯度量级通常也会变大；
- `'mean'` 求平均，通常返回标量 `torch.Size([])`，适合直接调用 `backward()`。

预测与标签的 shape 应符合损失的任务契约。上例两者同为 `[1, 1]`；把 `[batch, 1]` 的回归输出和 `[batch]` 标签不加思考地混用，可能触发广播，得到数值能运行却语义错误的 loss。训练前应先打印两者的 `shape`、`dtype` 和任务含义。

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

### Python 看得到的 `grad_fn`，和真正执行反向传播的引擎

这里必须避免一个看似合理却不准确的说法：**计算图不是 Python 用列表和递归手写出来的教学对象。**前向时，Python 侧的 `Tensor` API 会分派到 PyTorch 的张量算子；只要相关输入需要梯度，底层 autograd 系统就为该次运算保留反向计算所需的节点、依赖关系和必要的中间信息。Python 中看到的 `tensor.grad_fn` 是对“这个结果如何反向计算”的可观察入口，不应依赖它的具体类名编写业务逻辑。

例如，以下代码中的 `+` 和 `*` 确实使用了 Python 的运算符协议：`a + b` 会触发张量对象的加法分派，`a * b` 会触发乘法分派。但分派之后的数值计算和大规模反向传播不是由 Python 逐元素循环完成的。

```python
a = torch.tensor(2.0, requires_grad=True)
b = torch.tensor(3.0, requires_grad=True)
c = a * b + 1.0

print(c.item())       # 7.0
print(c.requires_grad)  # True
print(c.grad_fn)      # 某个与加法反向计算对应的对象，具体名称不应依赖

c.backward()
print(a.grad.item())  # 3.0，dc/da = b
print(b.grad.item())  # 2.0，dc/db = a
```

`Tensor` 对象保存或引用数值及其 autograd 元数据；autograd 引擎根据计算图调度反向任务，最后把叶子参数的结果累加到 `.grad`。这解释了为什么 `loss.backward()` 是一个很短的 Python 调用，却能计算由大量 GPU 算子构成的网络梯度。它也解释了为什么不要把 `grad_fn`、`_parameters` 等内部表示当作稳定 API：用户应该依赖 `requires_grad`、`backward()`、`autograd.grad()`、`parameters()` 等公开语义。

还有一个直接的内存后果：默认 `backward()` 完成后，本次前向图中不再需要的保存内容会被释放。因此同一个 `loss` 通常不能无条件地再次 `backward()`；正确做法通常是重新前向计算出新的 loss。`retain_graph=True` 只适用于确实要对同一图做多次反向的场景，并会增加内存占用，不能用来掩盖训练循环顺序错误。

## 为什么 loss 通常要是标量

如果一个 batch 中每条样本各有一个 loss，形状可能是 `[B]`。但“该怎样综合这 $B$ 条错误”是训练目标的一部分，框架不能替你猜。

```python
per_item_loss = (prediction - y).pow(2)  # 例如 [B, 1]
loss = per_item_loss.mean()              # 明确规定：优化平均误差
loss.backward()
```

标量 loss 的 `backward()` 表示“以 1 为上游权重，计算这个总目标对参数的梯度”。若直接对多元素 Tensor 调用 `backward()`，PyTorch 无法知道每个元素应占多大权重。真实任务有时确实需要逐样本加权，这时应显式乘权重后再求和/平均，而不是让默认行为替你做决定。

## 梯度写入 `.grad` 后，谁真正修改参数

`loss.backward()` 结束后，参数数值仍然是 2 和 1；变化只发生在 `.grad`。下一步由优化器完成。`torch.optim.Optimizer` 是**优化器抽象基类**，而 `SGD`、`Adam`、`AdamW` 等是它的具体策略。它们共同管理两类数据：

- `param_groups`：参数组列表。每组保存一批 `Parameter` 的引用和该组超参数，例如 `lr`、`weight_decay`；
- `state`：以具体参数对象为键的历史状态。纯 SGD 可能不需要额外历史，Momentum 会保存动量，Adam/AdamW 会保存一阶、二阶矩估计和步数。

创建 optimizer 时传入的不是参数数值副本，而是已注册 `Parameter` 对象的引用。`step()` 因而能在原对象上更新数值；它不会重新调用模型，也不会自动调用 `backward()`。

```python
optimizer = torch.optim.SGD(
    model.parameters(),
    lr=0.1,
    momentum=0.9,
)

print(len(optimizer.param_groups))          # 1
print(optimizer.param_groups[0]['lr'])       # 0.1
print(len(optimizer.param_groups[0]['params']))  # weight 和 bias，共 2 个
print(optimizer.state)  # 第一次 step 前通常为空；Momentum 使用后才出现每个参数的状态
```

实际模型常把不同参数放在不同组，例如微调时让新分类头学习得更快。下面例子中的 `backbone` 和 `head` 都是 `Module`，`parameters()` 分别递归产出其注册参数；两个组仍由**同一个** optimizer 在每次 `step()` 中统一更新。

```python
optimizer = torch.optim.AdamW(
    [
        {'params': model.backbone.parameters(), 'lr': 1e-4},
        {'params': model.head.parameters(), 'lr': 1e-3, 'weight_decay': 0.01},
    ]
)
```

这段只是参数组接口示意，前文的 `nn.Linear(1, 1)` 没有 `backbone` 与 `head` 属性，不能直接复制替换运行。`lr` 应依任务和训练策略设定；参数组不是“让网络多一层”，而是给已有参数指定不同更新规则。

回到本例，调用如下：

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

## 把这些对象放回同一段可运行训练代码

前面的片段分别观察了模型、损失、autograd 和优化器。下面把它们收回一个最小闭环；复制到安装了 PyTorch 的 Python 环境即可运行。数据满足 $y=2x+1$，我们故意从错误参数开始，只训练一步来观察每个对象的职责。

```python
import torch
from torch import nn

torch.manual_seed(0)

# 1. 数据契约：两个样本、每个样本一个特征和一个回归目标，均为 float32。
features = torch.tensor([[1.0], [3.0]], dtype=torch.float32)  # shape: [2, 1]
labels = torch.tensor([[3.0], [7.0]], dtype=torch.float32)    # shape: [2, 1]

# 2. 模型：Linear 持有 weight: [1, 1] 与 bias: [1] 两个 Parameter。
model = nn.Linear(in_features=1, out_features=1)
with torch.no_grad():
    model.weight.fill_(0.0)
    model.bias.fill_(0.0)

# 3. 目标和更新规则：二者都是配置对象，不会自己执行一个 batch。
loss_fn = nn.MSELoss(reduction='mean')
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

# 4. 一次训练步骤。
optimizer.zero_grad(set_to_none=True)
prediction = model(features)                # [2, 1]，经 Module.__call__ 进入 forward
loss = loss_fn(prediction, labels)          # 标量 Tensor，shape: []
loss.backward()                             # 将 d(loss)/d(parameter) 累加到 .grad

print('loss:', loss.item())                 # 29.0
print('weight.grad:', model.weight.grad)    # tensor([[-24.]])
print('bias.grad:', model.bias.grad)        # tensor([-10.])

optimizer.step()                            # 原地修改两个 Parameter 的数值
print('updated weight:', model.weight.item())  # 2.4
print('updated bias:', model.bias.item())      # 1.0
```

这段代码有几个可迁移的阅读点：

- `features`、`labels` 是普通 Tensor；它们的 `[2, 1]` 分别表示两个样本、每样本一个值。它们不需要 `requires_grad=True`，因为训练中要求的是 loss 对模型参数的导数，不是对输入数据的导数。
- `model.parameters()` 返回由 `nn.Linear` 注册的 `weight` 和 `bias`。optimizer 保存的是它们的引用，因此 `step()` 后再访问 `model.weight`，看见的就是更新后的值，而不是新建的另一份模型。
- `loss_fn` 把逐元素的平方误差平均为标量。初值下预测全为 0，误差平方是 $3^2$ 与 $7^2$，所以 loss 为 $(9+49)/2=29$。此处可手算验证，说明“loss 是什么”由任务目标决定，而非 optimizer 决定。
- 初始时 $\partial L/\partial w=-24$、$\partial L/\partial b=-10$。`SGD(lr=0.1)` 因此将 $w$ 从 0 更新到 $0-0.1\times(-24)=2.4$，将 $b$ 更新到 1.0。数值变化发生在最后一行 `step()`，不是 `backward()`。
- `loss.item()` 只将单元素 Tensor 转成 Python `float` 以便打印；不要在训练计算中用 `.item()` 后再拿回去继续构造 loss，因为这会离开 Tensor 计算图。

如果加入 GPU，正确的迁移对象是模型和本 batch 的输入/标签，而不是只迁移其中一个：

```python
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = model.to(device)
features = features.to(device)
labels = labels.to(device)
```

`model.to(device)` 会递归迁移已注册的参数和 buffer；前面故意展示的普通 Tensor 属性则不会因此自动迁移。这也是模型状态必须通过 `Parameter` 或 `register_buffer()` 正确登记的实际原因。

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

- `nn.Module` 是模型与层的组合/注册抽象；你实现 `forward()`，日常调用则写 `model(input)`，由 `Module.__call__()` 进入完整框架入口。
- `nn.Parameter` 是被 Module 登记为可训练状态的 Tensor；普通 `requires_grad=True` Tensor 可以求导，但不会自动进入 `model.parameters()`。
- 损失可以是 `nn.Module`（配置可作为对象状态）或 `torch.nn.functional` 函数（常用于无状态计算）；它们都应返回定义训练目标的 Tensor。
- 自动求导记录并计算梯度；优化器读取梯度并更新参数，两者不是同一件事。
- 优化器只管理传给它的 `model.parameters()` 或参数组；`param_groups` 保存更新超参数，`state` 保存 Momentum、Adam 等策略所需的历史。
- `.grad` 默认累加；除非故意做梯度累积，否则每批开始前清理。
- Python 的类、`__call__`、属性注册和运算符分派组织了接口；底层张量算子和 autograd 引擎并不是纯 Python 逐元素实现。
- `state_dict` 保存参数和 buffer 的数值，不保存模型 Python 代码；加载前必须重建对应结构。
- checkpoint 比单独权重多保存优化器和训练过程状态，适合继续训练；部署推理通常不需要携带这些额外状态。

下一篇会回到“这些参数如何组成神经网络函数”：线性层、隐藏表示、激活函数和输出层各自负责什么。
