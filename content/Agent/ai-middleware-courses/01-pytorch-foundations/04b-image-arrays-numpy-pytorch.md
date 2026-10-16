+++
date = '2026-10-16T20:00:00+08:00'
draft = false
title = '图像张量基础：NumPy 与 PyTorch 的数组、通道、mask 和内存'
math = true
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

## 像素值 0–255 如何变成颜色

普通 PNG/JPEG 图片最常见的每通道深度是 8 bit。8 个二进制位能表示 $2^8=256$ 个整数，因此每个通道可取 `0` 到 `255`。RGB 三个通道并不表示“一个颜色值被拆成三部分”，而是三束光的相对强度：

| RGB 值 | 视觉结果 | 含义 |
| ------ | -------- | ---- |
| `[0, 0, 0]` | 黑色 | 三个通道都没有光强度 |
| `[255, 255, 255]` | 白色 | 三个通道都达到最大 |
| `[255, 0, 0]` | 红色 | 红通道最强 |
| `[0, 255, 0]` | 绿色 | 绿通道最强 |
| `[0, 0, 255]` | 蓝色 | 蓝通道最强 |
| `[255, 255, 0]` | 黄色 | 红、绿叠加，蓝为零 |
| `[128, 128, 128]` | 中灰 | 三通道相等的中等亮度 |

RGB 是**加色模型**：屏幕发出的红、绿、蓝光叠加越多，越接近白色。颜料/印刷的 CMYK 则属于减色模型，不能把两者混为一谈。OpenCV 用 BGR 存储，因此一个像素 `[0, 0, 255]` 在 OpenCV 数组里视觉上是红色，在 RGB 数组里却是蓝色；这正是转换不可省略的原因。

```python
pixel_bgr = image[100, 200]       # 读取第 100 行、第 200 列，结果为 [B,G,R]
blue, green, red = pixel_bgr
print(int(red), int(green), int(blue))
```

模型通常把 `uint8` 除以 `255.0` 变为 `float32` 的 `0..1`。例如 RGB `[255,128,0]` 变为 `[1.0, 0.502, 0.0]`。是否还要减均值、除标准差，取决于权重训练时使用的预处理；没有一种归一化规则能自动适合所有模型。

## 颜色空间、透明度与“颜色相同”的边界

RGB 适合显示和大多数神经网络输入，但不总适合人按颜色筛选。HSV/HSL 将颜色拆为色相、饱和度和明度/亮度，常更接近“找偏红文字”或“排除低饱和背景”的需求；Lab 尝试让距离更接近人眼感知，OpenCV 的颜色筛选和背景亮度判断会用到这类空间。转换不是无损的业务语义升级，只是换一种坐标表示。

PNG 还可能有第四个 alpha 通道，常写为 RGBA/BGRA：

```text
[R, G, B, A]
A=0   完全透明
A=255 完全不透明（8-bit PNG）
```

LaMa 和 Real-ESRGAN 的常见权重只接受三通道图片，因此项目会取前三个颜色通道。若输入带透明背景，必须明确选择怎样把它合成到实际背景上；直接丢掉 alpha 并不总能保留用户看到的视觉效果。

## 分辨率、像素数量与缩放

分辨率 `1920×1080` 表示宽 1920、高 1080，总像素数为：

$$
1920\times1080=2,073,600
$$

RGB `uint8` 原始数组约占 $1920\times1080\times3\approx5.9$ MiB；同样图像转为 `float32` 后，每个数 4 字节，约为四倍。模型内部并不只保存输入，还会产生多个特征图和反向传播中间结果，因此训练显存远大于“图片文件大小”；图像文件经过 JPEG 压缩后的磁盘大小不能用来估算显存。

把图片从 1000×1000 放大为 4×，会得到 4000×4000，像素数从 100 万变为 1600 万，是 16 倍而非 4 倍。这就是 Real-ESRGAN 4×输出和大图 tile 推理特别消耗内存与时间的直接原因。

## 图像文件、数组和 Tensor 不是同一种东西

JPEG、PNG、WebP 是**文件编码格式**：它们描述如何在磁盘上压缩和保存像素，JPEG 通常有损压缩，PNG 常无损并可含 alpha。`cv2.imread()` 会解码文件成为 NumPy 数组；`torch.from_numpy()` 再将 CPU 数组包装成 Tensor。模型看到的不是 `.png` 文件，而是某种 dtype、shape、颜色空间和值域的数值张量。

这也解释了两个常见误会：

- 文件后缀改成 `.png` 不会自动把 BGR 转 RGB，也不会产生模型需要的 float32；
- Tensor 保存为 `.pt` 也不是图片格式，它只是张量/对象序列化，除非你同时记录颜色、尺寸和值域，否则其他程序不知道怎样显示它。

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

## 视频就是有时间顺序的许多帧，但不止如此

最朴素的理解没有错：视频由连续图像帧组成。若每秒显示 30 帧（30 FPS），10 秒视频约有 300 帧；每帧 `1920×1080` 的 RGB 原始像素若完全展开，数据量约为 `300 × 5.9 MiB`，接近 1.7 GiB。这正是视频文件必须使用 H.264/H.265 等编解码器压缩、而视频 AI 往往必须逐帧或分段处理的原因。

但视频不等于“把很多 PNG 直接拼起来”：

- **帧率（FPS）** 决定每秒显示多少帧，影响运动流畅度和总帧数；
- **时间戳（PTS）** 决定每帧的显示时刻，变帧率视频不能只靠 `frame_index / fps` 推断时间；
- **编解码器** 决定怎样压缩帧，有些帧依赖邻近帧重建，读取某一帧可能需要先解码前面的关键帧；
- **颜色采样和色彩范围** 影响视频像素如何表示，常见 yuv420p 与内存里的 BGR/RGB 三通道数组不是同一个格式；
- **音频流** 与视频帧是独立轨道，图像模型只处理视频帧，输出时还要考虑重新编码和音频回封装。

OpenCV 读视频时，通常每次给出一帧 BGR `uint8 [H,W,3]`：

```python
import cv2

capture = cv2.VideoCapture('input.mp4')
fps = capture.get(cv2.CAP_PROP_FPS)
index = 0

while True:
    ok, frame_bgr = capture.read()
    if not ok:
        break
    print(index, frame_bgr.shape, frame_bgr.dtype)
    index += 1

capture.release()
```

CleanCanvas 正是把每一帧送进与单图相同的 LaMa/Real-ESRGAN 推理边界，再将结果交给视频编码器。模型通常不了解“前一帧”和“后一帧”，所以逐帧修复可能发生**时间闪烁**：每帧都合理，但相邻帧生成的纹理细节并不完全相同。解决闪烁需要时序模型、光流约束或后处理，不是简单把 batch size 改大就能解决。

## 缩放与插值：尺寸变大不等于细节真的回来

普通 resize 必须为新像素赋值。最近邻复制最近像素，边缘容易呈块状；双线性根据周围四个像素插值，较平滑但可能模糊；Lanczos 使用更大邻域，常用于高质量重采样。它们都是固定数学规则，不会从训练数据中学习纹理。

Real-ESRGAN 的前半段同样会处理数组和插值，但卷积网络还会根据训练中学到的图像规律生成高频细节。因此它的结果可能更自然，也可能产生并不存在的纹理。无论使用哪种缩放，输出的像素数量增加了，原始信息本身却不会凭空变成可验证的历史事实。

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
- RGB 的 0–255 是三束颜色通道的 8-bit 强度；文件编码、内存数组、颜色空间和模型 Tensor 是不同层次的表示。
- `transpose`/`permute` 改变维度顺序，`unsqueeze` 增加维度，`squeeze` 可能删除重要维度；不要混用它们的语义。
- NumPy 切片、`torch.from_numpy` 可能共享内存，修改前要明确自己是否需要副本。
- 视频由时间有序的图像帧构成，但还包含帧率、时间戳、编解码、色彩格式和音频；逐帧图像推理可能产生时间闪烁。
- mask 是模型的空间条件，不是简单的裁剪框；LaMa 是否能修好水印，和 mask 语义、上下文及模型训练分布密切相关。
