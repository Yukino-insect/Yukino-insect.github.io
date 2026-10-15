+++
date = '2026-10-16T20:00:00+08:00'
draft = false
title = '图像张量基础：NumPy 与 PyTorch 的数组、通道、mask 和内存'
+++

在真正调用 LaMa 或 Real-ESRGAN 之前，必须先看懂图像在程序中的几种形态。很多所谓“模型效果不好”的问题，根源只是把 `[H, W, C]` 当成了 `[C, H, W]`，或者把 OpenCV 的 BGR 当成了模型训练时的 RGB。

本篇只讨论图像数组和张量，不讨论复杂网络。读完后，你应该能够看到一段 `transpose`、`permute`、`unsqueeze` 或布尔索引代码时，说明每一维代表什么、数据是否被复制、结果是否仍在 GPU 上。

## 一张彩色图像究竟是什么

从数学上看，一张灰度图像是二维函数 $I(y,x)$，每个坐标对应一个亮度值；彩色图像多了一个通道维，可以写成 $I(y,x,c)$。在代码里，常见表示如下：

| 表示 | shape | 含义 |
| ---- | ----- | ---- |
| NumPy/OpenCV | `[H, W, C]` | 高、宽、颜色通道 |
| PyTorch 单张图 | `[C, H, W]` | 通道、高、宽 |
| PyTorch batch | `[N, C, H, W]` | 图片数量、通道、高、宽 |
| 灰度 mask | `[H, W]` | 每个像素是否属于待处理区域 |
| 模型 mask | `[N, 1, H, W]` | batch 和单通道维都显式存在 |

`H` 是行数，`W` 是列数，`C=3` 通常表示 RGB/BGR，`N` 是一次并行处理的图片数。`shape` 不是装饰性信息；卷积层会按照固定维度寻找通道，维度顺序错了，轻则报错，重则得到颜色和空间都错误的结果。

## NumPy：CPU 上的多维数组

OpenCV 的 `cv2.imread()` 返回 NumPy 数组：

```python
import cv2

image = cv2.imread('input.png')
print(image.shape)  # 例如 (720, 1280, 3)
print(image.dtype)  # uint8
print(image.min(), image.max())  # 通常是 0 到 255
```

`uint8` 表示每个元素占 8 位，适合保存普通图片；它不是神经网络最常用的计算类型。模型通常需要 `float32`，并且把 0 到 255 缩放到 0 到 1：

```python
image_float = image.astype('float32') / 255.0
```

不要写成整数除法后再期待模型自动修复类型。显式调用 `astype` 能让值域和 dtype 都可检查。

## 切片不是复制：先理解视图和副本

NumPy 切片经常返回原数组的 view：

```python
crop = image[100:200, 300:500]
crop[:, :] = 0
```

上面的赋值会同时修改 `image`，因为 `crop` 与原数组共享内存。如果只想得到独立图片，应显式复制：

```python
crop = image[100:200, 300:500].copy()
```

这解释了为什么颜色翻转示例常写成 `image[:, :, ::-1].copy()`：反向步长产生的数组可能不是连续内存，`.copy()` 既断开共享，也得到 PyTorch 更容易接受的布局。`torch.from_numpy()` 通常也与 NumPy 共享内存，所以创建张量后不要再无意修改原数组。

## 通道顺序：BGR、RGB 和维度顺序是两件事

OpenCV 默认是 BGR；PIL、torchvision 和大多数视觉模型文档默认是 RGB。通道顺序错误时，shape 仍然完全正确，因此这是很危险的静默错误：

```python
rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
```

通道顺序与维度顺序不要混淆：

- BGR → RGB 是交换通道语义；
- HWC → CHW 是重新排列维度位置。

它们通常都需要做，但解决的是不同问题。

## `transpose` 和 `permute`：重新排列维度

NumPy 使用 `transpose`：

```python
chw = rgb.transpose(2, 0, 1)  # [H, W, C] -> [C, H, W]
```

PyTorch 使用 `permute`：

```python
import torch

torch_tensor = torch.from_numpy(rgb)
chw = torch_tensor.permute(2, 0, 1)
```

这两个操作通常只改变“如何解释步长”，不一定立即复制所有数据。若后续算子要求连续内存，可以使用：

```python
chw = chw.contiguous()
```

不要用 `reshape` 代替所有 `permute`。`reshape` 只是在改变形状，不能表达“把通道维移动到最前面”的语义；维度数相同并不代表维度含义正确。

## `unsqueeze` 和 batch 维

模型通常要求 `[N, C, H, W]`，但读取一张图得到的是 `[H, W, C]`。完整转换可以写成：

```python
import torch

tensor = torch.from_numpy(rgb.transpose(2, 0, 1)).float() / 255.0
batch = tensor.unsqueeze(0)
print(tensor.shape)  # [3, H, W]
print(batch.shape)   # [1, 3, H, W]
```

`unsqueeze(0)` 在第 0 维插入长度为 1 的维度；它不复制图片，也不改变像素值。相反，`squeeze()` 会删除长度为 1 的维度，不能随意放在推理代码里：当 batch size 恰好为 1 时，它可能把模型需要的 batch 维删除。

## mask 是数组，不是“裁剪框”

mask 通常是 `[H, W]` 的数组，0 表示不处理，非零表示允许模型修改：

```python
mask = cv2.imread('mask.png', cv2.IMREAD_GRAYSCALE)
binary = (mask > 0).astype('float32')
mask_tensor = torch.from_numpy(binary).unsqueeze(0).unsqueeze(0)
print(mask_tensor.shape)  # [1, 1, H, W]
```

两个 `unsqueeze` 分别增加 batch 维和通道维。mask 并不是把图片裁成一个小矩形；模型仍然看到完整图像，只是得到一个“哪些位置需要生成”的条件。这个区别正是理解 LaMa 矩形水印 mask 的前提。

## `torch.Tensor` 与 NumPy 的边界

NumPy 数组主要在 CPU 上工作，PyTorch Tensor 可以在 CPU 或 GPU 上工作：

```python
tensor = tensor.to('cuda')
```

GPU Tensor 不能直接调用 `.numpy()`，必须先回到 CPU：

```python
array = tensor.detach().cpu().numpy()
```

`detach()` 表示结果不再参与梯度图；推理时已经在 `inference_mode()` 中，显式写出来仍能表达边界。反向转换则常用 `torch.from_numpy(array)`，它通常与数组共享内存；如果需要独立副本，可使用 `.clone()` 或在 NumPy 端 `.copy()`。

## 一个完整的图像张量检查函数

把检查写成函数，比在项目中到处临时打印更容易复用：

```python
def describe(name, value):
    if hasattr(value, 'shape'):
        print(name, 'shape=', tuple(value.shape), end=' ')
    if hasattr(value, 'dtype'):
        print('dtype=', value.dtype, end=' ')
    if hasattr(value, 'device'):
        print('device=', value.device, end=' ')
    if hasattr(value, 'min'):
        print('range=', float(value.min()), float(value.max()))
    else:
        print()
```

对每个模型边界至少检查一次 `shape`、`dtype`、`device` 和值域。图像模型的错误排查，往往从这四个数字就能缩小一半范围。

## 这些数组操作如何连接到 CleanCanvas

CleanCanvas 的 LaMa 入口大致执行：

```text
OpenCV BGR uint8 [H,W,3]
  → RGB [H,W,3]
  → padding 到网络要求的尺寸
  → float32 / 255
  → transpose 成 [3,H,W]
  → unsqueeze 成 [1,3,H,W]
  → 迁移到 CPU/CUDA
  → TorchScript 前向
  → [1,3,H,W] 还原为 [H,W,3]
  → RGB 转 BGR uint8
```

Real-ESRGAN 使用相同的图像边界，但输出空间尺寸是输入的 4 倍；Manga 则把图像先转为灰度，并额外生成线稿先验。因此，模型名称不同，数组基础并没有改变。

## 小结

- NumPy/OpenCV 常见格式是 HWC、BGR、`uint8`；PyTorch 视觉模型常见格式是 NCHW、RGB、`float32`。
- `transpose`/`permute` 改变维度顺序，`unsqueeze` 增加维度，`squeeze` 可能删除重要维度；不要混用它们的语义。
- NumPy 切片、`torch.from_numpy` 可能共享内存，修改前要明确自己是否需要副本。
- mask 是模型的空间条件，不是简单的裁剪框；LaMa 是否能修好水印，和 mask 语义、上下文及模型训练分布密切相关。
