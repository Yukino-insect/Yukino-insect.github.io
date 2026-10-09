+++
date = '2026-10-09T20:00:00+08:00'
draft = false
title = '项目实战：图像如何变成 PyTorch 张量——预处理、mask 与 LaMa 修复'
+++

深度学习图像代码最容易让初学者困惑的部分，往往不是网络，而是网络前后的十几行转换。它们看似只是 `transpose`、`astype`、`unsqueeze`，却决定模型看到的是正确颜色、正确范围、正确形状，还是一张被悄悄打乱的数据。以 `TorchScriptLaMaEngine.inpaint()` 为例，我们把这条链路完整拆开。

## 原始图像、模型图像与最终图像不是同一个对象

项目给修复引擎的原始输入有两个 NumPy 数组：

| 名称 | 常见 shape / dtype | 含义 |
| ---- | ------------------ | ---- |
| `image_bgr` | `[H, W, 3]` / `uint8` | OpenCV 图片或视频帧；通道顺序 BGR，数值 0–255 |
| `mask` | `[H, W]` / `uint8` | 与原图同尺寸；0 表示不修复，非零表示允许修复 |

模型并不直接接受这个格式。LaMa 路径最后送入 TorchScript 的是：

```text
image_tensor: [1, 3, H_pad, W_pad]，float32，RGB，范围 0 到 1
mask_tensor : [1, 1, H_pad, W_pad]，float32，二值 0 或 1
```

最前面的 `1` 是 batch 维度。即使一次只修一张图，PyTorch 图像模型也通常要求 batch 维，因为同一个网络结构需要同时支持 1 张或 N 张图片。`3` 是 RGB 三个颜色通道；单通道 mask 则为 `1`。这种 `[N, C, H, W]` 约定常被简称为 **NCHW**。

## 第一步：BGR 转 RGB

OpenCV 传统上以 BGR 存储图片，而大多数深度学习视觉模型训练时使用 RGB。项目执行：

```python
rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB)
```

`[:, :, :3]` 表示只取前三个通道，因此有 alpha 通道的输入也不会意外送给只能接受三通道的模型。若遗漏 BGR → RGB，代码仍然可以运行，形状也毫无问题，但红蓝通道会交换；模型等于看到了不符合训练分布的图片。这类错误比显式异常更危险，因为它给出的是“看似合理但质量变差”的结果。

## 第二步：对齐到网络要求的尺寸

LaMa 路径调用 `_pad_to_modulo(..., 8)`，将高和宽补到 8 的倍数；Manga 路径使用 16。原因是下采样/上采样网络通常多次以 2 为倍率改变空间大小。若宽高不能被总缩放倍数整除，编码器与解码器的特征图尺寸可能无法对齐。

项目对图像使用对称填充，对 mask 使用常数 0 填充：

```text
原图 H×W
  ├─ 图像：边缘镜像补齐，避免边界突然变成黑色
  └─ mask：补 0，表示补出的区域绝不要求模型修复
```

推理完成后，代码使用原来的 `height, width` 裁回原尺寸。padding 是模型内部兼容操作，不应改变用户看到的图像尺寸或修复区域坐标。

## 第三步：HWC 变 CHW，整数变浮点数

核心转换为：

```python
image_tensor = torch.from_numpy(
    padded_image.transpose(2, 0, 1).astype(np.float32) / 255.0
)
```

逐段理解即可：

1. `padded_image` 原形状是 `[H, W, 3]`，即 HWC；
2. `transpose(2, 0, 1)` 把最后的颜色维移动到前面，得到 `[3, H, W]`，即 CHW；
3. `astype(np.float32)` 将 0–255 的无符号整数变为 32 位浮点数；
4. `/ 255.0` 缩放到 0–1，这是 LaMa 权重训练时期待的数值范围；
5. `torch.from_numpy(...)` 将 NumPy 数组包装为 CPU Tensor。

随后用 `unsqueeze(0)` 在最前面加一个长度为 1 的维度：`[3, H, W] → [1, 3, H, W]`。注意，`from_numpy` 常与原 NumPy 数组共享底层内存；在创建后若继续原地修改数组，张量可能随之变化。在这里数组不再被修改，因此这种高效转换是安全的。

你可以用下面的小实验巩固：

```python
import numpy as np
import torch

image_bgr = np.zeros((4, 6, 3), dtype=np.uint8)
image_bgr[:, :, 2] = 255  # BGR 的红色通道
image_rgb = image_bgr[:, :, ::-1].copy()

tensor = torch.from_numpy(image_rgb.transpose(2, 0, 1)).float() / 255.0
batched = tensor.unsqueeze(0)

print(tensor.shape)   # torch.Size([3, 4, 6])
print(batched.shape)  # torch.Size([1, 3, 4, 6])
print(batched[:, 0].max().item())  # 1.0，RGB 的第 0 通道是红色
```

切片 `[::-1]` 会产生负 stride；示例中的 `.copy()` 是为了得到 PyTorch 可接受的连续内存。项目使用 `cv2.cvtColor`，不会遇到这个切片细节。

## mask 为什么也要变成张量

代码先做：

```python
binary_mask = (mask > 0).astype(np.uint8)
mask_tensor = torch.from_numpy(padded_mask[np.newaxis].astype(np.float32))
```

这里不把 mask 当作灰度图的丰富亮度，而只关心“该像素是否在待修复区域”。所以任何大于 0 的原始值都转为 `1`，其余为 `0`。`np.newaxis` 在开头加入通道维，得到 `[1, H, W]`；再次 `unsqueeze(0)` 后变成 `[1, 1, H, W]`。

mask 的作用不是裁剪出一个小图，而是与**完整原图**一起给模型：

```text
完整图片：告诉模型周边人物、线条、气泡和纹理是什么
完整 mask：告诉模型只有哪些像素需要被生成式补全
```

这解释了一个常见现象：界面上的矩形只是影响 mask 的白色范围，LaMa 实际仍能看见框外的上下文。对复杂背景来说，这是必要的信息；但也意味着模型只能“推测”遮挡区域，不能保证恢复真实历史像素。

## 第四步：迁移设备并仅做前向推理

模型调用前，两个张量都执行 `.to(self.device)`：

```python
with torch.inference_mode():
    result = self.model(
        image_tensor.unsqueeze(0).to(self.device),
        mask_tensor.unsqueeze(0).to(self.device),
    )
```

模型的参数在 CPU 还是 CUDA，输入张量就必须在同一设备；CPU 模型和 CUDA 输入相加/卷积会报设备不一致错误。`inference_mode()` 表示不记录自动求导历史，推理阶段通常更省内存、开销更低。它不等于 `eval()`，模型加载时调用的 `.eval()` 已经负责切换某些层的推理行为；第六篇会把二者精确区分。

## 第五步：把结果还给 OpenCV

LaMa 输出第一个 batch 的形状通常为 `[3, H_pad, W_pad]`。后处理链路是：

```python
result_rgb = result[0].permute(1, 2, 0).detach().cpu().numpy()
result_bgr = cv2.cvtColor(
    np.clip(result_rgb[:height, :width] * 255, 0, 255).astype(np.uint8),
    cv2.COLOR_RGB2BGR,
)
```

- `result[0]` 去掉 batch 维；
- `permute(1, 2, 0)` 将 CHW 还原为 OpenCV/NumPy 习惯的 HWC；
- `detach()` 断开潜在计算图；虽在 `inference_mode()` 下通常没有图，显式写出仍清楚表达“结果不需要梯度”；
- `cpu()` 是 CUDA 张量转换成 NumPy 前的必要迁移；NumPy 不认识 CUDA 显存；
- 乘 255、截断至合法范围、转回 `uint8`，才是可编码的像素；
- 最后 RGB 转 BGR，保证后续 OpenCV 代码颜色正确。

## 为什么还要强制恢复 mask 外像素

神经网络一次处理整张图，即使用户只希望改一行文字，它也可能让 mask 外像素出现极轻微变化。项目最后执行类似下面的保护：

```python
result_bgr[binary_mask == 0] = image_bgr[:, :, :3][binary_mask == 0]
```

这是一条产品级约束：**mask 外的像素必须与原图完全一致。** 它比“模型通常不会改外面”更可靠，也便于测试。面试时可以将其概括为“用业务不变量约束生成模型的自由度”：模型负责 mask 内合理补全，确定性代码负责保证其他区域不被意外触及。

## Manga 路径为何不同

`MangaEngine` 先执行 `BGR → GRAY`，构造 `[1, 1, H, W]` 灰度张量；除主修复网络外还调用一份线稿模型，生成 `lines`。灰度和线稿归一化到 `[-1, 1]` 后，与二值 mask、随机噪声和全 1 张量一起喂给漫画修复网络。

因此彩色画面不适合 Manga：mask 内输出来自灰度模型，最终再 `GRAY → BGR` 后三个通道相同，色相和饱和度无法凭配置找回来。这不是“GPU 算得不够好”，而是输入信息在最开始就被丢弃了。

## 小结

- 图像推理要同时核对颜色顺序、数值范围、dtype、shape、设备和模型输入契约；任一项错了都可能静默降低质量。
- CleanCanvas Studio 的 LaMa 输入是 RGB `[1, 3, H, W]`、0–1 的 `float32`；mask 是 `[1, 1, H, W]` 的 0/1 浮点张量。
- padding 是为网络的下采样结构服务，结果必须裁回原尺寸。
- mask 决定可修改区域而非模型可见区域；最后恢复 mask 外原像素是一项明确的工程安全约束。
