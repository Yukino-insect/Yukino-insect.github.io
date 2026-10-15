+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '读懂 Real-ESRGAN：卷积网络、残差函数与分块推理'
math = true
+++

本章不把 `RRDBNet` 当作一串需要背诵的类名。我们先回答“超分模型究竟学习什么函数”，再用一个最小 `Conv2d` 例子读懂形状，最后解释 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 为什么要分块处理大图。

## 超分辨率的任务与边界

输入低分辨率图像 $x$，模型输出高分辨率图像 $hat y=f_\theta(x)$。训练时用高质量图像 $y$ 计算损失，调整参数 $\theta$；推理时只有 $x$，因此输出是依据训练分布作出的合理猜测，不是丢失细节的历史证据。最近邻或双线性插值是固定函数，Real-ESRGAN 是带可学习参数的函数。

## 先运行一个最小卷积网络

```python
import torch
from torch import nn

class TinyUpscaler(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2),
            nn.Conv2d(8, 3, kernel_size=3, padding=1),
        )

    def forward(self, x):
        base = nn.functional.interpolate(x, scale_factor=2, mode='nearest')
        return base + self.features(nn.functional.interpolate(x, scale_factor=2, mode='nearest'))

model = TinyUpscaler().eval()
image = torch.randn(1, 3, 16, 20)
with torch.inference_mode():
    output = model(image)
print(image.shape, output.shape)  # [1, 3, 16, 20] -> [1, 3, 32, 40]
```

`Conv2d(3, 8, 3, padding=1)` 不是“处理 8 张图”，而是用 8 组可学习卷积核把 3 个输入通道变为 8 个特征通道。`LeakyReLU` 是非线性函数；它不是网络本身，也不是所有层都必须使用的固定组件。两层卷积和激活组合成一个函数，`base + features(...)` 则是残差函数：模型只学习对插值结果的修正。

## RRDBNet 的层次到底是什么

项目的 Anime 模型可从外到内读成：

```text
RRDBNet
  ├─ conv_first：RGB → 特征通道
  ├─ 多个 RRDB：稠密连接 + 残差连接
  ├─ 上采样：两次 ×2
  └─ conv_last：特征通道 → RGB
```

这不是神经网络的唯一固定模板。所谓“输入层、隐藏层、输出层”是描述功能位置的术语：第一段接收数据，中间段提取/组合表示，最后一段给出任务输出。一个网络可以没有显式的 `nn.Linear`，也可以有多个输出头；大模型只是更多模块的函数组合。网络作者选择这些层，是为了匹配图像局部结构、输出分辨率和训练稳定性。

### 卷积保留了局部结构

图像张量通常是 `[N, C, H, W]`。全连接层把所有像素混在一起，参数量随分辨率迅速增长；卷积核只看局部窗口，并在不同位置共享同一组权重。`kernel_size=3, stride=1, padding=1` 时高宽保持不变，因为：

$$
\left\lfloor\frac{H+2P-K}{S}\right\rfloor+1=H
$$

代入 $P=1,K=3,S=1$ 即可验证。这个尺寸推导直接决定后续特征能否相加、能否拼接。

### 激活函数为什么不能省

若只有卷积/线性变换，多个变换仍可合并为一次线性变换，无法表示复杂弯曲关系。`LeakyReLU(x)=max(x,0.2x)` 在负半轴保留小梯度，避免所有负值都变为 0；`PReLU` 则把斜率作为可学习参数。它们是函数 $g$，网络是诸如 $f(x)=W_2g(W_1x+b_1)+b_2$ 的组合，二者概念不同。

### 稠密连接与残差连接

稠密连接沿通道维拼接早期特征：`torch.cat((x, x1, x2), dim=1)`。后面的卷积因此能直接复用前面信息，但输入通道数也随拼接增加。残差连接写作 $F(x)+x$，让模块学习“需要改变什么”；在代码中常见 `return transformed * 0.2 + x`，`0.2` 让残差初期幅度更小，有助于深网络稳定。

## 两种上采样方式

Anime RRDBNet 使用两次 `interpolate(scale_factor=2)`，最终得到 4 倍高宽；General SRVGGNetCompact 常让卷积产生 `3×4×4=48` 个通道，再由 `PixelShuffle(4)` 重排为 `[3, 4H, 4W]`。`PixelShuffle` 不凭空产生元素，只改变元素的排列；真正的细节由前面的卷积函数计算。

## 为什么大图要 tile

4 倍放大后像素面积变为 16 倍，中间特征图也会占用大量显存。分块推理把输入切成 `tile_size × tile_size`，每次只保留一块的中间激活，再把输出拼回去。若直接把块边缘写回，卷积在边缘缺少上下文，容易出现接缝，因此每块输入通常增加 `tile_pad` 重叠区域，推理后只取中心有效区域：

```text
输入块： [左 pad | 中心 tile | 右 pad]
模型输出：保留中心区域 × scale
写回：只写中心，丢弃重叠边界
```

坐标必须同时考虑输入缩放和输出缩放。例如输入块从 `(x0, y0)` 开始、放大倍数为 4，写回坐标不是原来的 `x0`，而是 `4*x0`。tile 太小会增加拼接次数和边界比例，tile 太大则可能再次 OOM；它是显存与速度的可测量折中，不是越小越安全。

## 读项目代码时的固定问题

对 `RealESRGANEnhancer.enhance()`，按以下顺序检查：

1. 输入是否为 BGR `uint8 [H,W,3]`，模型需要的 RGB/float32 是否在边界处转换？
2. 模型和输入是否在同一 device，CUDA FP16 时 dtype 是否一致？
3. 输出是否裁剪到 `[0,1]`、转回 `uint8`，并恢复 BGR？
4. tile 的输入坐标、输出坐标和 overlap 是否都乘了放大倍数？
5. 是否在 `eval()` + `inference_mode()` 下调用，是否缓存模型而不是每帧加载？

## 小结

- Real-ESRGAN 学习的是从低分辨率图像到高分辨率图像的参数化函数，输出不能被当作真实细节证明。
- 卷积利用局部结构，激活提供非线性，残差/稠密连接改善信息和梯度流；它们是可组合的函数模块，不是固定层级仪式。
- tile 推理解决显存峰值，overlap 解决边界上下文；坐标和缩放因子必须一起推导。
