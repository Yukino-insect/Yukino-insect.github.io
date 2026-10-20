+++
date = '2026-10-20T16:30:00+08:00'
draft = false
title = '读懂图像推理中的数值计算：Python、NumPy 与 PyTorch 操作详解'
math = true
+++

前面的图像张量章节已经说明了 BGR、RGB、HWC、NCHW 和 `uint8`/`float32` 的基本边界。但当你真正打开 CleanCanvas Studio 的 `backend/inpaint/engine.py` 或 `backend/enhance/realesrgan.py` 时，仍会连续遇到 `//`、`ceil`、切片、`astype`、`np.newaxis`、布尔 mask、`transpose`、`unsqueeze`、`clamp` 等操作。它们看起来零散，实际构成了模型输入输出契约的一部分。

本章只讲一个主题：**怎样从 Python 标量运算、NumPy 数组运算和 PyTorch Tensor 运算三层，读懂图像推理代码中的数值流动。** 不需要先理解 Real-ESRGAN 的网络结构；读完后，你应能解释一行计算改变了什么数值、shape、dtype、device 和内存关系，并能据此定位错误。

## 一条图像推理链上有三种“数值对象”

以 Real-ESRGAN 的 `enhance()` 为例，同一张图片在一次调用中会依次成为三种不同对象：

```text
Python 标量：height、width、scale、tile_size、坐标
        ↓ 控制循环、边界和最终尺寸
NumPy 数组：OpenCV BGR 图像、RGB 浮点图、mask、tile
        ↓ 表示 CPU 内存中的像素矩阵
PyTorch Tensor：NCHW 输入、模型特征图、4×输出 Tensor
        ↓ 在 CPU 或 CUDA 上执行网络计算
NumPy 数组：最终 BGR uint8 图像
```

它们不是谁“更高级”的替代品，而是职责不同：Python 标量适合流程控制；NumPy 和 OpenCV 适合文件 I/O、颜色转换和像素级处理；PyTorch Tensor 适合让已训练网络在 CPU/GPU 上做卷积计算。理解项目时，先问“这一行的输入和输出属于哪一层”，通常比背函数名有效。

| 对象 | 例子 | 擅长的工作 | 常见误解 |
| ---- | ---- | ---------- | -------- |
| Python `int` / `float` / `bool` | `width`、`scale=1.5`、`tile_x` | 循环、比较、坐标和尺寸计算 | 标量不是图像，不能拿它调用 `.shape` 或 `.to('cuda')` |
| `numpy.ndarray` | `image_bgr`、`rgb`、`binary_mask` | CPU 像素数组、切片、OpenCV 互操作 | 数组不是模型输入格式；HWC/BGR/`uint8` 通常仍需转换 |
| `torch.Tensor` | `tensor`、`tile_output`、`output` | 模型前向、GPU、自动求导/推理模式 | Tensor 也可能在 CPU；不是每个 Tensor 都能直接 `.numpy()` |

## Python 标量：尺寸、坐标和边界的算术基础

深度学习代码中的绝大多数 `height`、`width`、坐标和倍率，首先只是 Python 整数或浮点数。不要因为它们出现在 AI 项目里，就把普通算术当成神秘仪式。

### `/`、`//`、`%`、`ceil` 和 `round` 分别回答什么问题

Python 的普通除法 `/` 返回浮点数；地板除 `//` 丢弃小数部分；取余 `%` 得到余数。它们在 padding、分块和最终输出尺寸中各有明确用途：

```python
import math

height = 721
modulo = 8

print(height / modulo)        # 90.125：普通除法，结果是 float
print(height // modulo)       # 90：完整的 8 像素组数
print(height % modulo)        # 1：还差 7 个像素才整除
print(math.ceil(height / modulo))  # 91：至少需要 91 组
print(round(1280 * 1.5))      # 1920：最终显示尺寸可用整数
```

LaMa 的 `_pad_to_modulo()` 使用下面的纯整数写法计算补齐后的边长：

```python
padded_height = (height + modulo - 1) // modulo * modulo
```

它等价于：

$$
H'=\left\lceil\frac{H}{m}\right\rceil m
$$

其中 $H$ 是原始高度，$m$ 是网络要求的倍数，$H'$ 是补齐后的高度。对 `H=721`、`m=8`，有：

$$
H' = \left\lceil\frac{721}{8}\right\rceil\times8=91\times8=728
$$

整数式中的 `height + modulo - 1` 会把“不整除时应向上取整”的需求转换成一次 `//`：`(721+7)//8=91`。若高度原本就是 720，`(720+7)//8=90`，不会多补一整组。这里的乘法与地板除都发生在 Python 整数上，不会创建图像副本。

`round()` 又是另一种语义。项目在非原生 4×倍率时使用 `round(input_width * scale)` 计算 OpenCV resize 的目标尺寸。例如宽 1280、倍率 1.5 得到 1920。注意 Python 的 `round` 在恰好位于 .5 时采用“ties to even（舍入到偶数）”规则，例如 `round(2.5)` 是 2、`round(3.5)` 是 4；因此不要把它简单理解成“永远 .5 向上”。这里它的任务只是稳定地把最终像素尺寸变为整数，不参与模型内部 4×计算。

### `min`、`max` 与 Python 切片：tile 不越界的原因

Real-ESRGAN 的 tile 循环中有：

```python
right = min(left + tile_size, width)
pad_left = max(left - tile_pad, 0)
```

`min` 选择较小值，防止最后一块超出右边界；`max` 选择较大值，防止向左扩展的上下文 pad 变成负坐标。假设宽为 1000、中心块从 `left=512` 开始、`tile_size=512`、`tile_pad=10`：

```text
中心 tile：  [512, min(512 + 512, 1000)) = [512, 1000)
带上下文：   [max(512 - 10, 0), 1000)    = [502, 1000)
```

Python/NumPy 切片遵守 **左闭右开**：`image[:, 502:1000]` 包含下标 502 到 999，共 498 列，而不包含 1000。这个规则让长度可以直接用 `stop - start` 得到；项目中的 `(right - left) * 4` 正是据此计算核心 tile 的 4×输出宽度。

不要用 `if left + tile_size > width: ...` 在许多分支中手工修补边界。`min`/`max` 让同一套坐标公式同时处理图像中间和边缘，减少“最后一块少一列/多一列”的经典错误。

## NumPy：图像数组的 dtype、元素运算和索引

OpenCV 读入的普通彩色图片通常是 NumPy `ndarray`：shape 为 `[H,W,3]`，dtype 为 `uint8`，通道顺序为 BGR。一个 `uint8` 元素只能表示 0 到 255 的整数；它适合储存和显示像素，却不是模型最常见的浮点输入。

```python
import numpy as np

image_bgr = np.array([[[10, 20, 30]]], dtype=np.uint8)
print(image_bgr.shape, image_bgr.dtype)  # (1, 1, 3) uint8
print(image_bgr[0, 0])                   # [10 20 30]，语义是 B、G、R
```

### 列表的 `*` 与数组的 `*` 不同

Python 列表与 NumPy 数组外观相似，乘法语义却完全不同：

```python
print([1, 2, 3] * 2)                    # [1, 2, 3, 1, 2, 3]：重复列表
print(np.array([1, 2, 3]) * 2)          # [2, 4, 6]：逐元素乘法
print(np.array([1, 2, 3]) + 10)         # [11, 12, 13]：标量广播到每个元素
```

模型前后处理依赖的是后两种**逐元素运算**。例如 `array / 255.0` 会让每个像素值除以 255；`result_rgb * 255` 又把每个浮点像素放回显示量纲。数组的运算不是 Python `for` 循环逐像素解释执行，而是 NumPy 的底层向量化实现；这也是为什么应优先表达为整个数组的公式，而不是在 Python 层嵌套遍历百万像素。

### `astype(np.float32) / 255.0` 为什么不能随意换顺序

项目的 Real-ESRGAN 输入预处理是：

```python
rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB)
rgb = rgb.astype(np.float32) / 255.0
```

这两步分别解决颜色与数值问题：

- `image_bgr[:, :, :3]` 取全部行、全部列和前 3 个通道；若输入意外携带 alpha 或更多通道，不会把它们交给 RGB 网络；
- `cv2.cvtColor` 交换 BGR/RGB 的通道**语义**；只做 `transpose` 不会改变红蓝含义；
- `astype(np.float32)` 把每个整数像素转换为单精度浮点数；
- `/ 255.0` 将每个值从 `[0,255]` 线性映射为 `[0,1]`。

先 `astype(np.float32)` 的价值是明确控制结果 dtype。若直接让 `uint8` 数组与 Python 浮点数相除，NumPy 常会提升到 `float64`；数值未必立刻错误，却会让数组占用更多内存，并可能与后续期望 `float32` 的 Tensor 不一致。反过来，若在 `uint8` 上进行会截断的整数计算，再期待模型恢复小数精度，则只是把信息先扔掉再祈祷。

### shape、`np.newaxis`、`transpose`：移动维度不是改变颜色

图像的 HWC 与模型的 CHW 是维度顺序不同，不是颜色空间不同：

```python
rgb_hwc = np.zeros((4, 5, 3), dtype=np.float32)
rgb_chw = rgb_hwc.transpose(2, 0, 1)

print(rgb_hwc.shape)  # (4, 5, 3)：H, W, C
print(rgb_chw.shape)  # (3, 4, 5)：C, H, W
```

`transpose(2,0,1)` 的意思是“把原来的第 2 维放到第 0 位，原第 0 维放到第 1 位，原第 1 维放到第 2 位”。它通常只创建一个 view，改变的是索引步长解释，而不是把所有像素逐一重新计算。需要给单通道 mask 增加一个通道维时，项目写：

```python
padded_mask = np.zeros((728, 1288), dtype=np.uint8)
mask_chw = padded_mask[np.newaxis]

print(mask_chw.shape)  # (1, 728, 1288)
```

`np.newaxis` 等价于在当前位置插入长度为 1 的维度。它不增加像素、不把灰度变 RGB；它只把 `[H,W]` 表示为模型更容易理解的 `[C,H,W]`。随后 PyTorch 的 `unsqueeze(0)` 再增加 batch 维，最终 mask 才成为 `[1,1,H,W]`。

### 广播、布尔数组和 mask 外像素保护

比较运算会逐元素产生布尔数组：

```python
mask = np.array([[0, 255], [0, 255]], dtype=np.uint8)
outside = mask == 0

print(outside)
# [[ True, False],
#  [ True, False]]
```

在 LaMa 修复后，项目执行：

```python
result_bgr[binary_mask == 0] = image_bgr[:, :, :3][binary_mask == 0]
```

这不是逐个像素写出的循环，而是 NumPy 的布尔索引。左边和右边都先用同一个二维布尔 mask 选出若干个 `[B,G,R]` 三元组，再把原图这些位置赋回结果图。它实现了清晰的产品不变量：**mask 外部像素必须与输入完全相同。** 若布尔 mask 的高宽与图片不一致，NumPy 会报索引错误；这恰好比悄悄修改错误区域安全得多。

`&`、`|`、`~` 用于数组逐元素逻辑运算，不应替换为 Python 的 `and`、`or`、`not`。例如项目计算邻域采样环：

```python
ring = (dilated > 0) & ~binary_mask.astype(bool)
```

括号是必要的：先得到两个布尔数组，再逐元素“且”；`~` 将遮罩取反。写成 `dilated > 0 and ...` 会要求 Python 把整张数组判断为单个真/假值，通常直接抛出“数组真值不明确”的异常。

### `np.zeros`、`np.pad`、`np.clip` 与 copy/view 边界

项目会用 `np.zeros(image_bgr.shape[:2], dtype=np.uint8)` 创建全零 mask；`shape[:2]` 只取高度和宽度，所以结果是 `[H,W]` 而非误用彩色图的 `[H,W,3]`。`np.pad` 用于 LaMa 的倍数补齐：图像采用 `symmetric` 边界扩展，mask 使用 `constant` 的零填充。前者让边缘像素以对称方式延续，减少网络看到突兀黑框的机会；后者把新增 mask 区域明确设为“不可修复”，避免 padding 被误当成用户选择的区域。

模型输出转回图片时：

```python
image_uint8 = np.clip(result_rgb * 255, 0, 255).astype(np.uint8)
```

`np.clip` 对每个元素做 $min(\max(x,0),255)$。它必须出现在转 `uint8` 前：若模型给出 `-0.1` 或 `1.1`，直接转换可能产生溢出或不符合预期的颜色；先 clip 才将结果限制为显示格式能表示的范围。

切片和 `transpose` 经常返回原数组的 view，修改它可能反过来修改源图；`array.copy()` 则明确生成独立数据。项目在需要保护原始输入、又要继续修改结果时使用 `result_bgr.copy()`。对图像代码而言，是否共享内存不是微不足道的性能细节，它决定一条后处理语句会不会意外污染“用于恢复 mask 外像素”的原图。

## PyTorch：从 NumPy 数值到可执行的模型 Tensor

PyTorch Tensor 的数据本身与 NumPy 数组都可理解为多维数表，但 Tensor 还可位于 CUDA 上、可被网络 Module 使用，并能在训练时参与 autograd。项目的推理路径不需要梯度，却仍需要严格匹配模型的 shape、dtype 和 device。

### `from_numpy`、`float`、`unsqueeze` 与 `to` 的连续含义

Real-ESRGAN 的 `_infer()` 中最关键的一行是：

```python
tensor = torch.from_numpy(image.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)
```

把它拆开才知道每一步没有替你做什么：

```python
chw_array = image.transpose(2, 0, 1)      # NumPy：[H,W,3] -> [3,H,W]
tensor = torch.from_numpy(chw_array)      # CPU Tensor；通常与 NumPy 共享底层内存
tensor = tensor.float()                   # 请求转换为 torch.float32
batch = tensor.unsqueeze(0)               # [3,H,W] -> [1,3,H,W]
batch = batch.to(self.device)             # 迁移到模型所在 CPU 或 CUDA
```

- `torch.from_numpy` 不是图像解码函数；它只把已有的 CPU NumPy 内存包装为 Tensor。只要仍共享内存，修改数组也可能影响 Tensor；如果要独立数据，应在 NumPy 端 `.copy()` 或在 Tensor 端 `.clone()`。
- `.float()` 等价于请求 `torch.float32`。当前输入在 NumPy 阶段已是 `float32` 时，它不必一定复制；写出它的目的，是让 `_infer()` 的输入契约自包含。
- `unsqueeze(0)` 只插入 batch 维，不复制图像，也不改变像素数值。没有它，`Conv2d` 会把 3 当作 batch 或因维度不足报错。
- `.to(self.device)` 才将 CPU 数据复制到 GPU（若目标是 CUDA）。模型权重和输入若不在同一 device，卷积无法计算；这是“Expected all tensors to be on the same device”错误的直接原因。

CUDA 路径还会执行 `.half()`，让输入变为 `torch.float16`，以匹配已经 `.half()` 的模型权重。半精度不是一个自动的加速开关：权重是 `float16`、输入却仍 `float32` 时，许多算子会报 dtype 不匹配；CPU 路径保持 `float32` 更稳妥。

### `squeeze`、`permute`、`cpu`、`numpy` 与 `clamp` 的返回方向

模型返回后，`enhance()` 走反向路径：

```python
result_rgb = (
    output.squeeze(0)
    .float()
    .cpu()
    .clamp(0, 1)
    .numpy()
    .transpose(1, 2, 0)
)
```

它不是一串可任意调换顺序的链式写法：

| 操作 | 输入与输出 | 必要原因 |
| ---- | ---------- | -------- |
| `squeeze(0)` | `[1,3,4H,4W] → [3,4H,4W]` | 只移除已知的单图片 batch 维；无参数 `squeeze()` 可能误删其他长度为 1 的维 |
| `.float()` | FP16/FP32 → FP32 | 后处理和转 NumPy 前统一精度，避免半精度在 CPU 端继续传播 |
| `.cpu()` | CUDA Tensor → CPU Tensor | NumPy 只能直接查看 CPU 内存 |
| `.clamp(0,1)` | 逐元素限制值域 | 防止模型输出越过图像浮点约定 |
| `.numpy()` | CPU Tensor → NumPy 数组 | 把数据交回 OpenCV/NumPy 生态 |
| `.transpose(1,2,0)` | `[3,H,W] → [H,W,3]` | 恢复 OpenCV 所需 HWC 布局 |

这里的 `.numpy()` 只能对 CPU Tensor 使用；训练代码还通常需要先 `.detach()` 切断 autograd 图。LaMa 路径显式写成 `result[0].permute(1,2,0).detach().cpu().numpy()`，因为它的输出对象来自 TorchScript 模型。Real-ESRGAN 整段在 `torch.inference_mode()` 中运行，不建立反向图，但仍保留“先 CPU、再 NumPy”的边界。

`clamp` 是 PyTorch Tensor 方法；`np.clip` 是 NumPy 函数。它们都表达限制区间的数学动作，但前者在模型当前 device 上处理 Tensor，后者在 CPU 数组上处理 ndarray。不要为了名字相似而把 CUDA Tensor 传给 `np.clip`，也不要把 ndarray 当作 Tensor 调用 `.clamp()`。

## 将三层操作放回 CleanCanvas 的真实数据流

下面用一张 `720×1280` 的 BGR 图、用户请求 `1.5×` 为例，完整列出 Real-ESRGAN 的数值状态。假设使用 Anime/General 任一 4×模型，模型输出值域暂按通常的 `[0,1]` 约定理解：

| 阶段 | Python/NumPy/PyTorch 表示 | shape | dtype / device | 值域或副作用 |
| ---- | ------------------------- | ----- | -------------- | ------------ |
| OpenCV 输入 | `image_bgr` ndarray | `[720,1280,3]` | `uint8` / CPU | BGR，0–255 |
| 颜色与缩放 | `rgb` ndarray | `[720,1280,3]` | `float32` / CPU | RGB，0–1 |
| 模型输入 | `tensor` | `[1,3,720,1280]` | `float32` CPU 或 `float16` CUDA | RGB，0–1 |
| 原生模型输出 | `output` | `[1,3,2880,5120]` | 与模型相同 | 浮点 RGB，可能存在轻微越界 |
| 后处理数组 | `result_rgb` ndarray | `[2880,5120,3]` | `float32` / CPU | RGB，clip 后 0–1 |
| 最终返回 | `result_bgr` ndarray | `[1080,1920,3]` | `uint8` / CPU | 4×结果再 Lanczos 缩至 1.5×，BGR 0–255 |

这里最值得记住的是：用户请求的 1.5×不会把网络变成“1.5×模型”。网络仍先产生 `720×4=2880`、`1280×4=5120` 的原生输出，之后普通插值才把它缩到 `round(720×1.5)=1080`、`round(1280×1.5)=1920`。如果只看最终尺寸而忽略中间的 4× Tensor，就会错误估计显存和耗时。

### mask 路径：同一套数组知识怎样避免误修复

LaMa 路径中的 mask 初始是二维 `uint8 [H,W]`：0 表示保持原图，非零表示允许模型修复。它先用：

```python
binary_mask = (mask > 0).astype(np.uint8)
padded_mask = _pad_to_modulo(binary_mask, 8, constant=True)[:, :, 0]
mask_tensor = torch.from_numpy(padded_mask[np.newaxis].astype(np.float32))
batch_mask = mask_tensor.unsqueeze(0).to(device)
```

若原 mask 是 `[721,1282]`，补齐 8 的倍数后是 `[728,1288]`。`_pad_to_modulo` 会临时把二维数组视为 `[H,W,1]`，以便 `np.pad` 对高、宽和通道使用统一的三维 padding 参数；紧接的 `[:, :, 0]` 再取回二维 mask。`np.newaxis` 形成 `[1,728,1288]`，`unsqueeze(0)` 形成模型需要的 `[1,1,728,1288]`。

图像使用对称 padding，mask 使用全零 constant padding，并非随意风格差异：图像边缘要保留可供卷积参考的视觉上下文；新增 padding 区域却不应被 mask 标记为“用户要删除的内容”。当图像与 mask 的补齐尺寸不同，双输入模型会在空间维度上直接不匹配。

### tile 路径：标量坐标怎样控制数组和 Tensor 切片

`_infer_tiled()` 将 Python 标量 `left`、`top`、`right`、`bottom` 用于 NumPy 切片：

```python
tile = image[pad_top:pad_bottom, pad_left:pad_right]
tile_output = self._infer(tile)
```

第一行仍是 NumPy HWC 数组；第二行才将它变为 PyTorch NCHW Tensor 并执行网络。模型的原生倍率是 4，所以输入坐标与输出坐标必须同时乘 4：

```python
crop_left = (left - pad_left) * 4
output[:, :, top * 4:bottom * 4, left * 4:right * 4] = \
    tile_output[:, :, crop_top:crop_bottom, crop_left:crop_right]
```

例如中心区域横向是 `[512,1000)`，左侧上下文 pad 使实际输入为 `[502,1000)`。中心左边界在该 tile 内的偏移是 `512-502=10`，4×输出中的偏移就是 40。因此必须从 `tile_output` 的 40 开始取，而不能把带 pad 的结果整块写进总输出。这里左侧是 PyTorch Tensor 切片赋值：会原地改变预先由 `torch.zeros` 分配的完整输出画布；每个核心像素只写一次，不需要把重叠区域平均。

## 用检查函数把“感觉不对”变成可定位的事实

阅读或修改数值代码时，不要只打印整个数组——图片 Tensor 会输出海量数字，反而看不出错误。应固定检查 shape、dtype、device、值域和是否连续：

```python
import numpy as np
import torch

def describe_array(name: str, array: np.ndarray) -> None:
    print(
        name,
        'shape=', array.shape,
        'dtype=', array.dtype,
        'range=', (float(array.min()), float(array.max())),
        'contiguous=', array.flags['C_CONTIGUOUS'],
    )

def describe_tensor(name: str, tensor: torch.Tensor) -> None:
    print(
        name,
        'shape=', tuple(tensor.shape),
        'dtype=', tensor.dtype,
        'device=', tensor.device,
        'range=', (float(tensor.min()), float(tensor.max())),
        'contiguous=', tensor.is_contiguous(),
    )
```

在 `enhance()` 的关键边界分别检查 `image_bgr`、`rgb`、`tensor`、`output`、`result_rgb`，至少能迅速区分以下问题：

| 现象 | 优先检查 | 常见根因 |
| ---- | -------- | -------- |
| 颜色明显偏蓝/偏红 | 通道语义 | 忘记 BGR↔RGB，而不是 `transpose` 写错 |
| 模型报四维输入错误 | `shape` | 少了 batch 维，或 HWC 没有变为 CHW |
| `Half` 与 `Float` 类型错误 | `dtype` | CUDA 模型 `.half()` 了，输入仍为 `float32` |
| CPU/CUDA 不在同一设备 | `device` | Tensor 没有 `.to(self.device)` |
| 输出全黑、发白或色彩怪异 | 值域 | 漏除 255、重复除 255，或没有在转 `uint8` 前 clip |
| tile 接缝或 shape 不匹配 | 坐标与切片长度 | 忘乘 4、pad 输出未裁掉、右边界理解错误 |

这些检查不是要永久塞进热路径。它们用于开发、单元测试和出现异常时的最小复现；确认契约后再移除高频日志。真正值得保留的是对输入尺寸、请求倍率、输出尺寸和 mask 外像素不变等业务不变量的断言。

## 小结

- Python `//`、`ceil`、`min`、`max`、`round` 和左闭右开切片，控制 padding、tile 边界与最终尺寸；它们决定“取哪一块”，并不直接计算卷积。
- NumPy 负责 CPU 图像数组。`astype(float32)/255`、`transpose`、`np.newaxis`、布尔索引、`np.pad` 和 `np.clip` 分别改变 dtype、维度、选择区域、边界和显示值域；必须分清 view 与 copy。
- PyTorch 负责 Tensor、device 和网络计算。`from_numpy → float → unsqueeze → to(device)` 建立模型输入；`squeeze → cpu → clamp → numpy → transpose` 把结果安全交回 OpenCV。
- 同一个“4×模型”可以最终返回 1×到4×图像，因为项目先做原生 4×推理、再按请求倍率缩放；中间 4× Tensor 才是显存估计的关键。
- 读数值密集代码时，优先追踪每一步的 shape、dtype、device、值域与副作用。只要这五项可说明，绝大多数图像推理代码就不再只是成串的符号。
