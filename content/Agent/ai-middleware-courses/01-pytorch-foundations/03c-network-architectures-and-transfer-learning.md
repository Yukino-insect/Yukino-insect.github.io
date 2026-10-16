+++
date = '2026-10-13T20:00:00+08:00'
draft = false
title = '深度学习架构入门：MLP、CNN、RNN、Transformer 与迁移学习'
math = true
+++

网络架构并不是按“新旧”排出的等级榜。MLP、CNN、RNN 和 Transformer 的差异，首先来自它们对数据结构作出的不同假设。这种预先写进模型的假设叫作 **归纳偏置**：它会限制模型如何看数据，也会让模型更容易从符合该结构的数据中学习。

## 先根据数据结构选择问题，而不是追逐名称

| 架构 | 主要假设 | 典型输入 | 应先记住的边界 |
| ---- | -------- | -------- | ---------------- |
| MLP | 特征是一个无空间、无顺序的向量 | 表格、已提取特征 | 适合理解训练闭环，不理解像素邻近关系 |
| CNN | 相邻像素相关，局部模式可出现在不同位置 | 图片、视频帧、二维信号 | 用卷积共享参数，利用局部空间结构 |
| RNN / LSTM / GRU | 当前结果与过去顺序有关 | 时间序列、早期文本/语音 | 状态逐步传递，长序列并行度有限 |
| Transformer | 序列中任意位置都可能直接相关 | 文本、图像块、音频、多模态 | 注意力建全局关系，但长序列成本高 |

把商品表格硬改成图片送给 CNN，或为几十个普通数值特征堆一个大 Transformer，通常只会提高成本和排错难度。模型的复杂程度不替你理解数据；这项工作仍然需要由人完成，遗憾但相当公平。

## MLP：从特征向量开始

**多层感知机（MLP）** 反复组合线性层与激活函数。对输入向量 $x$，单层线性变换为：

$$
z=Wx+b
$$

若连续堆叠线性层而不加入激活函数，整体仍可化为一个线性变换。因此 MLP 必须在中间引入 ReLU、GELU 或 SiLU 等非线性，才能表达弯曲边界。当前课程前半段的二分类模型正是一个 MLP：它的价值不在于“先进”，而在于让数据、损失、梯度和优化器的因果链保持清晰。

MLP 默认不认为第一个特征与第二个特征在空间上相邻，也不知道一组数字是否有时间顺序。这个限制在表格数据中往往合理，在图像上却非常浪费：把一张图片完全展平后，模型必须重新学习“相邻像素通常相关”这种本可提前利用的规律。

下面是一个真正的 MLP。它说明“隐藏层”不是某种特殊对象，只是输出会继续交给后续函数的中间表示：

```python
from torch import nn

mlp = nn.Sequential(
    nn.Linear(10, 32),  # [B, 10] -> [B, 32]
    nn.ReLU(),          # [B, 32] -> [B, 32]
    nn.Linear(32, 3),   # [B, 32] -> [B, 3]，三分类 logits
)
print(sum(p.numel() for p in mlp.parameters()))
```

第一层参数量是 `10 × 32 + 32 = 352`，第二层是 `32 × 3 + 3 = 99`。这个简单算术解释了为什么将 `224×224×3` 的图像直接展平再接全连接层会迅速膨胀：仅一个 150,528 维输入到 1,000 维输出的线性层就需要约 1.5 亿个权重，还没有利用相邻像素的结构。

## CNN：为图像保留局部空间关系

卷积核可以看成一个小的可学习观察窗，例如 `3×3`。它在图像上滑动，并在每个位置复用同一组权重；若某个核学会识别横向边缘，它可以在任何位置识别横向边缘，而不必为左上角和右下角各学一次。卷积输出叫作特征图，浅层往往响应边缘和纹理，深层逐渐组合为部件与语义。

二维卷积在一个方向上的输出尺寸为：

$$
\left\lfloor\frac{N+2P-D(K-1)-1}{S}+1\right\rfloor
$$

其中 `N` 是输入尺寸，`P` 是 padding，`D` 是 dilation，`K` 是卷积核大小，`S` 是 stride。第五至第七篇的图像修复、Real-ESRGAN 与分块推理，都是这组空间约束在工程中的具体表现。

深层 CNN 常用 **残差连接**：

$$
F(x)+x
$$

它为信息和梯度保留一条更直接的路径，使网络更容易训练得很深。Real-ESRGAN 的 RRDB 也会在后续项目篇中以残差和稠密连接组合特征；这不是装饰性的层名，而是为信息流和梯度流建立更可靠的通路。

### 卷积、步长、池化和感受野

`nn.Conv2d(3, 16, kernel_size=3, padding=1)` 用 16 个可学习的 `3×3×3` 卷积核处理 RGB 输入，输出 `[B,16,H,W]`。同一组权重在每个空间位置复用，这叫权重共享；它假设“左上角检测到的横向边缘”在其他位置同样有意义。

```python
from torch import nn

cnn = nn.Sequential(
    nn.Conv2d(3, 16, kernel_size=3, padding=1),  # [B,3,32,32] -> [B,16,32,32]
    nn.ReLU(),
    nn.MaxPool2d(2),                             # [B,16,32,32] -> [B,16,16,16]
    nn.Conv2d(16, 32, kernel_size=3, padding=1), # [B,16,16,16] -> [B,32,16,16]
)
```

`stride=2` 卷积或 `MaxPool2d(2)` 会下采样，减少空间尺寸和计算量，但也会丢失精确位置。随着层数加深，一个输出位置能“看到”的输入区域不断扩大，这个区域叫**感受野**。分类通常希望更大感受野以理解物体整体；分割、修复和超分还要保留精细空间位置，所以它们会使用跳跃连接、编码器—解码器或上采样，而不能只不断池化。

卷积也不是视觉任务的唯一选择。它特别适合局部平移规律明显的数据；当图像中的远距离关系、全局布局非常重要时，注意力或 Fourier 模块可能提供额外能力。LaMa 的 Fourier Convolution 与 Real-ESRGAN 的残差稠密块，正是“图像结构假设不同，网络部件不同”的工程实例。

## RNN、LSTM 与 GRU：将过去压缩到状态中

对句子、传感器读数或用户行为序列，顺序常常有意义。RNN 在处理第 $t$ 个元素时，结合当前输入与上一时刻状态：

$$
h_t=\phi(W_xx_t+W_hh_{t-1}+b)
$$

隐藏状态 $h_t$ 可理解为“到目前为止的压缩记忆”。普通 RNN 在很长序列上反向传播时，许多小于 1 或大于 1 的因子连续相乘，容易出现梯度消失或爆炸。LSTM 和 GRU 通过门控机制控制保留、写入和遗忘信息的比例，从而缓解长期依赖问题。

它们仍需按时间步逐个计算，训练并行度受到限制。这正是许多文本任务后来转向 Transformer 的工程原因之一，而不是因为门控网络突然失去全部价值。

LSTM 的“门”可以先理解为三个 0 到 1 的控制系数：遗忘门决定旧记忆保留多少，输入门决定当前候选信息写入多少，输出门决定暴露多少状态。它们由 sigmoid 产生，因此不是 if/else 的硬开关，而是可微分的软比例。GRU 使用更少的门和状态，在一些任务上更轻量。它们缓解梯度长期连乘的问题，却不能彻底消除顺序计算带来的并行限制。

在 PyTorch 中，序列 batch 常用 `[B, T, D]`：

```python
import torch
from torch import nn

rnn = nn.GRU(input_size=8, hidden_size=16, batch_first=True)
sequence = torch.randn(4, 20, 8)  # 4 条序列、每条 20 步、每步 8 个特征
outputs, final_state = rnn(sequence)
print(outputs.shape, final_state.shape)  # [4,20,16]、[1,4,16]
```

这里的 `outputs[:, t]` 是各时间步的隐藏表示，`final_state` 是最后一步状态。是否应该只使用最后状态，取决于任务是“整段分类”还是“每一步都预测”；形状相同不代表语义相同。

## Transformer：用注意力直接建立关系

Transformer 让每个 token 通过 Query、Key、Value 三组表示查询其他位置：Query 表示“当前在找什么”，Key 表示“各位置可如何被匹配”，Value 是被聚合的内容。缩放点积注意力写作：

$$
Attention(Q,K,V)=softmax\left(\frac{QK^T}{\sqrt{d_k}}\right)V
$$

Self-Attention 使一个 token 能直接参考远处 token；多头注意力则从多个子空间学习不同关系。Transformer 还需要位置编码提供顺序、残差连接和 LayerNorm 稳定深层计算、前馈 MLP 做逐 token 的非线性变换。自回归生成还必须使用因果掩码，避免当前位置偷看未来 token。

标准完整注意力会比较大量位置对，序列长度为 $L$ 时，时间和显存开销通常与 $L^2$ 相关。因此“能看更长上下文”同时是能力问题和资源问题。下一套重排序课程会在文本 token 与 Cross-Encoder 的场景中继续展开它；这里首先要确认，注意力并不是一枚可以替代数据质量的万能印章。

### 一个 Transformer block 里实际有什么

一个常见预归一化 Transformer block 可以概括为：

```text
x
 ├─ LayerNorm → Multi-Head Self-Attention ─┐
 └──────────────────────────────────────────+→ x'
     x'
      ├─ LayerNorm → MLP（扩张、激活、投影） ─┐
      └────────────────────────────────────────+→ 输出
```

注意力负责 token 之间的信息交换；逐 token MLP 提供非线性特征变换；残差避免信息必须穿过每个子层；LayerNorm 让数值尺度更稳定。文本输入还需要 embedding 将离散 token ID 映射成浮点向量，并加入位置信息；视觉 Transformer 则常将图片切为 patch，再把每个 patch 当作一个 token。

```python
import torch
from torch import nn

block = nn.TransformerEncoderLayer(
    d_model=64, nhead=4, dim_feedforward=256, batch_first=True
)
tokens = torch.randn(2, 128, 64)  # [B, T, D]
encoded = block(tokens)
print(encoded.shape)              # [2, 128, 64]
```

`nhead=4` 表示将表示分为多个头去学习不同关系，不是四个相互独立的大模型。自回归生成还必须提供因果 mask，保证第 `t` 个 token 不能读取未来 token；编码器式分类模型通常不使用这张因果 mask。把它们都叫 Transformer 会掩盖关键差别。

## 预训练、迁移学习与微调

从随机参数训练大型视觉或语言模型需要大量数据与算力。现实项目更常从预训练模型开始：模型已在广泛数据上学到通用的边缘、纹理、语言或结构表示，再适配到下游任务。

| 策略 | 做法 | 优点 | 适用起点 |
| ---- | ---- | ---- | -------- |
| Linear Probing | 冻结主干，只训练新任务头 | 成本低、风险小 | 数据较少、先验证任务可行性 |
| 全量微调 | 全部参数继续训练 | 适应性强 | 数据较多、与预训练领域差异明显 |
| 参数高效微调 | 冻结大部分参数，只学习增量，如 LoRA | 显存和存储压力小 | 大模型、多任务或资源受限 |

微调学习率通常远小于从零训练，因为预训练权重已经位于一个可用起点附近。无论采用哪一种策略，验证集、任务定义、标签审查和数据泄漏检查都不能省略。更强的预训练模型不会修复错误流程；它往往只是更高效地把错误包装成漂亮数字。

### 一个视觉迁移学习的最小起点

以下示例将 ImageNet 预训练 ResNet-18 改为三分类器。先冻结主干，只训练最后分类头；这是验证数据和任务是否匹配的低风险起点：

```python
import torch
from torch import nn
from torchvision.models import resnet18, ResNet18_Weights

model = resnet18(weights=ResNet18_Weights.DEFAULT)
for parameter in model.parameters():
    parameter.requires_grad = False

in_features = model.fc.in_features
model.fc = nn.Linear(in_features, 3)  # 新头默认可训练

optimizer = torch.optim.AdamW(model.fc.parameters(), lr=1e-3)
```

冻结并不等于省略 `model.train()`：如果主干含 BatchNorm，训练/验证模式仍影响其行为。需要全量微调时，将参数重新设为可训练，使用更小学习率，并常为主干和新头设置不同 parameter group。这样做的原因不是“新头更重要”，而是新头从随机初始化开始，主干已有预训练能力，二者适合不同更新速度。

```python
for parameter in model.parameters():
    parameter.requires_grad = True

backbone_parameters = [
    parameter for name, parameter in model.named_parameters()
    if not name.startswith('fc.')
]
optimizer = torch.optim.AdamW([
    {'params': model.fc.parameters(), 'lr': 1e-3},
    {'params': backbone_parameters, 'lr': 1e-4},
], weight_decay=1e-4)
```

实际项目还要将训练和推理时的图像 resize、颜色顺序、归一化保持一致。预训练权重迁移的是表示能力，不会自动迁移你的标签定义或数据流程。

## 小结

- 架构选择应匹配数据的空间、顺序和全局关系，而不是追逐更新的术语。
- MLP 适合表格与训练闭环；CNN 用局部连接和权重共享处理图像；RNN 逐步传递状态；Transformer 用注意力建立长程关系。
- 残差连接、位置编码、归一化和掩码分别服务于深层信息流、顺序、稳定性与因果约束。
- 预训练能降低下游任务的起点，但无法替代可信的数据和评估流程。

最后一篇训练基础补充会把这些概念收束成通用的实验记录与诊断顺序，然后再进入 CleanCanvas Studio 的真实推理代码。
