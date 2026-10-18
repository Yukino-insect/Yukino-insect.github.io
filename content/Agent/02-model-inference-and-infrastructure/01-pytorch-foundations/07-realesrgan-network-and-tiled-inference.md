+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '读懂 Real-ESRGAN：网络、输入输出契约与带重叠边缘的分块推理'
math = true
+++
上一章说明了模型如何加载。本章沿着 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 的 `backend/enhance/realesrgan.py` 继续追踪：一张 OpenCV 的 BGR `uint8` 图像怎样成为网络输入、Anime/General 为什么不能共用权重、显存不足时 tile 怎样裁剪和拼回去。目标不是记住类名，而是能够从函数签名、shape、dtype、device 和副作用读懂一条真实推理链。

## 超分辨率学习什么，又不能证明什么

低分辨率图像 $x$ 经模型参数 $\theta$ 变为预测结果：

$$
\hat y=f_\theta(x)
$$

训练时用成对的低/高分辨率图像调整 $\theta$；推理时只有 $x$，所以 $\hat y$ 是符合训练分布的合理细节，不是对丢失真实像素的取证。项目也明确区分 Anime 与 General：前者优先二次元线条，后者面向普通图像，但文字和关键线条仍须人工复核。

当前两个网络的原生倍率都是 4：`[1,3,H,W] → [1,3,4H,4W]`。界面虽然可请求 1×至4×，但非 4×的实现并不是换一个相应倍率模型，而是先产生 4×结果，再以 Lanczos 插值缩到请求尺寸。

## 工程入口：`enhance()` 的参数、返回值与数据流

`RealESRGANEnhancer.enhance(image_bgr, scale=2.0)` 是推理的公开边界：

| 项目 | 约定 | 实际处理 |
| --- | --- | --- |
| `image_bgr` | NumPy `[H,W,>=3]`，通常 `uint8` BGR | 拒绝非彩色输入，只取前三通道 |
| `scale` | 1 到 4 的浮点数 | 超范围抛 `InpaintError` |
| 内部数组 | `[H,W,3]` / `float32` / RGB / `[0,1]` | BGR→RGB，除 255 |
| 模型 Tensor | `[1,3,H,W]`，CUDA 时可能 FP16 | HWC→CHW、加 batch、迁移设备 |
| 返回值 | `[round(H*scale),round(W*scale),3]` / `uint8` BGR | 截断值域、转回 BGR，必要时再缩放 |

预处理的这行包含多个不能互换的语义：

```python
rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
```

- `[:, :, :3]` 不把 alpha 或额外通道混入卷积输入；
- `cvtColor` 改变通道含义。OpenCV 默认 BGR，而发布权重按 RGB 训练，`astype` 不会交换红蓝；
- `float32` 与 `/255.0` 将 `uint8` 的 `[0,255]` 映射到模型约定的 `[0,1]`。

输出采取反向数据流：去掉 batch 维、转 float32、复制到 CPU、非原地 `clamp(0,1)`、CHW→HWC、乘255、四舍五入、转 `uint8`、RGB→BGR。最后的 `clamp` 是生成模型的防线：最后一层输出不必天然在图像值域中，直接转 `uint8` 会让越界值造成错误颜色。

## 模式、网络结构与 checkpoint 必须三者配对

项目没有根据文件名猜结构，而是在 `_asset_and_model()` 中显式映射：

```python
if self.mode is EnhanceMode.REAL_ESRGAN_ANIME:
    return ANIME_ASSET, _build_rrdb_net(num_block=6)
return GENERAL_ASSET, _build_srvgg_net()
```

| 模式 | 下载文件 | 代码创建的 `nn.Module` | 原生输出 |
| --- | --- | --- | --- |
| `realesrgan_anime` | `RealESRGAN_x4plus_anime_6B.pth` | 6 个 RRDB 的 `RRDBNet` | RGB，4× |
| `realesrgan_general` | `realesr-general-x4v3.pth` | `SRVGGNetCompact` | RGB，4× |

随后 `_load_model()` 才以 `strict=True` 将 checkpoint 载入此结构。`.pth` 本身不足以让程序猜出要创建哪一个类；真正可执行的兼容性检查是参数键、数量和 shape。

## Anime 网络：从 `forward()` 跟踪每一层的 shape

`RRDBNet` 的主干可读为：

```text
RGB [N,3,H,W]
  → conv_first: [N,64,H,W]
  → 6 个 RRDB + conv_body，并与浅层特征相加
  → 最近邻上采样 ×2 + conv_up1
  → 最近邻上采样 ×2 + conv_up2
  → conv_hr + conv_last
  → RGB [N,3,4H,4W]
```

项目的真实 `forward()`：

```python
feat = self.conv_first(x)
feat = feat + self.conv_body(self.body(feat))
feat = self.lrelu(self.conv_up1(functional.interpolate(feat, scale_factor=2, mode='nearest')))
feat = self.lrelu(self.conv_up2(functional.interpolate(feat, scale_factor=2, mode='nearest')))
return self.conv_last(self.lrelu(self.conv_hr(feat)))
```

若 `x` 是 `[1,3,16,20]`，`Conv2d(3,64,3,1,1)` 输出 `[1,64,16,20]`。卷积高的计算式为：

$$
H_{out}=\left\lfloor\frac{H+2P-K}{S}\right\rfloor+1
$$

其中 $H$ 是输入高，$P$ 是 padding，$K$ 是卷积核尺寸，$S$ 是 stride。代入 $H=16,P=1,K=3,S=1$ 得 16；两次 2×上采样后尺寸依次为 `32×40`、`64×80`，所以最终是 `[1,3,64,80]`。

`feat + ...` 是残差连接，左右 shape 必须完全相同；因此 `conv_body` 仍保持 64 通道与原高宽。它让深层分支学习“相对已有特征要补什么”，也提供较短的信息路径。

### RRDB 的稠密连接：`torch.cat(..., 1)` 为什么沿通道拼接

一个 `ResidualDenseBlock` 的关键部分如下：

```python
x1 = lrelu(conv1(x))
x2 = lrelu(conv2(torch.cat((x, x1), 1)))
x3 = lrelu(conv3(torch.cat((x, x1, x2), 1)))
x4 = lrelu(conv4(torch.cat((x, x1, x2, x3), 1)))
return conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x
```

`dim=1` 是图像 Tensor `[N,C,H,W]` 的通道维，不是在高宽方向拼图。默认 `num_feat=64`、`num_grow_ch=32`：

- `x` 为64通道，`x1` 为32通道，故 `conv2` 输入是 `64+32=96`；
- `x2` 仍是32通道，`conv3` 输入变为128；
- `conv5` 接收 `64+4×32=192` 通道，再压回64，才可与原始 `x` 相加。

这正是稠密连接：后面层能直接取得较早的特征。`*0.2+x` 是缩放残差，减小新分支幅度以帮助深层网络稳定；三个此类块再组成一个 `RRDB`，六个 RRDB 由 `nn.Sequential` 注册到网络。

`LeakyReLU(negative_slope=0.2, inplace=True)` 为卷积间加入非线性，并尽量原地改写中间激活以节省内存。这个 `inplace=True` 是网络层的局部内存选择，和 `torch.inference_mode()` 的 autograd 状态并不是同一概念，不能据此随意将所有操作改为原地。

## General 网络：`PixelShuffle(4)` 如何得到四倍图像

`SRVGGNetCompact` 用卷积/PReLU 把 3 通道特征变为 `3*4*4=48` 通道，之后执行：

```python
self.upsampler = nn.PixelShuffle(4)
return self.upsampler(output) + functional.interpolate(x, scale_factor=4, mode='nearest')
```

`PixelShuffle(4)` 将 `[N,48,H,W]` 重排为 `[N,3,4H,4W]`。它不生成新元素：`48=3×4²`，每个输出通道的 4×4 子像素来自输入的不同通道。视觉细节来自前面卷积学习出的数值；PixelShuffle 只负责把数值放到空间位置。加号右边是固定最近邻 4×基线，网络学习对这个基线的修正。

## `_infer()`：device、dtype、`eval()` 与 `inference_mode()` 的最小闭环

`_infer(image)` 接收预处理后的 RGB `float32 [H,W,3]`：

```python
tensor = torch.from_numpy(image.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)
if self.use_half:
    tensor = tensor.half()
with torch.inference_mode():
    return self.model(tensor)
```

1. `from_numpy` 在 CPU 与 NumPy 共享内存，并未复制到 GPU。
2. `transpose(2,0,1)` 与 `unsqueeze(0)` 得到模型需要的 `[1,3,H,W]`。
3. `.to(self.device)` 才可能复制到 CUDA；输入必须和模型权重同 device。
4. `self.use_half` 仅当实际加载到 CUDA 时为真。模型在加载时已经 `.half()`，因此输入也必须 `.half()`；CPU 路径保持 float32。
5. `.eval()` 在加载模型时已执行，控制层的推理行为；`inference_mode()` 控制本次前向不记录 autograd 图。两者缺一不可。

`enhance()` 的外层也用了 `inference_mode()`，所以 `_infer_tiled()` 与输出 `clamp` 处于嵌套推理上下文。内层保证 `_infer()` 单独调用也安全，外层保证 inference tensor 的后处理保持在相同语义边界内，并用非原地 `clamp` 避免修改模型输出。

## tile 降低的是什么内存，不能降低什么内存

4×放大使像素数变为 $4^2=16$ 倍，深层卷积又会产生特征图。tile 一次只运行一个输入块，使一次前向的**中间激活**随 tile 面积而非整图面积增长。

但它不让内存归零：当前代码会先在目标 device 分配完整输出 `torch.zeros((1,3,4H,4W))`。所以 tile 显著降低的是中间激活峰值，不会消除最终输出自身的显存；超大图仍可能在输出分配或结果转换时 OOM。

`tile_size` 是输入中心区域的最大边长：当其为 0，或图像最大边不超过它，代码直接整图推理；否则才分块。构造器将负值归零。`MediaEnhancer` 公开传入 `tile_size`，而 `tile_pad` 当前通过 `create_enhancer()` 使用默认值 10；若要改重叠量，需要直接构造 `RealESRGANEnhancer` 或扩展工厂接口。

## 逐行推导：带重叠边缘的切分、裁剪与写回

真实实现的核心是：

```python
left, top = tile_x * tile_size, tile_y * tile_size
right, bottom = min(left + tile_size, width), min(top + tile_size, height)
pad_left, pad_top = max(left - tile_pad, 0), max(top - tile_pad, 0)
pad_right, pad_bottom = min(right + tile_pad, width), min(bottom + tile_pad, height)

tile_output = infer(image[pad_top:pad_bottom, pad_left:pad_right])
crop_left, crop_top = (left - pad_left) * 4, (top - pad_top) * 4
crop_right = crop_left + (right - left) * 4
crop_bottom = crop_top + (bottom - top) * 4
output[:, :, top*4:bottom*4, left*4:right*4] = \
    tile_output[:, :, crop_top:crop_bottom, crop_left:crop_right]
```

Python 切片右边界排他，故 `left:right` 精确表示中心 tile。`min`/`max` 使图像边缘的 pad 自动缩短且不越界。

例如输入宽 1000，`tile_size=512`、`tile_pad=10`。第二列 tile 中心横向为 `[512,1000)`，送入模型的实际范围扩为 `[502,1000)`。模型输出宽 `498×4=1992`；其中开头 `10×4=40` 个像素对应左侧重叠 pad，不能写作本 tile 的中心。因此代码从 `tile_output` 取 `[40,40+488×4)`，写到完整输出 `[512×4,1000×4)`。

重叠不是重复计算的浪费。卷积靠邻居像素获得上下文；每块若只有中心，边界会缺真实上下文并产生网格接缝。项目让每块带 `tile_pad` 推理，再丢弃该块的 pad 输出，只写回自己的中心。每个中心像素只写一次，因此不需要平均融合。

## 模型复用与异常边界

`MediaEnhancer.run()` 一次创建 `enhancer = self._enhancer()`；图片调用一次 `enhance()`，视频循环则对每帧复用同一个 `enhancer.enhance(frame, self.scale)`。因此不会逐帧下载权重、重建网络或迁移参数。

- 初始化阶段会暴露模式错误、PyTorch 缺失、下载/MD5 失败、权重不匹配和两个设备都无法加载等问题；
- `auto` 真实尝试 CUDA 后才回退 CPU，并将失败原因写入任务日志；显式 `cuda`/`cpu` 不会偷偷换设备；
- 推理中的 CUDA OOM 被翻译为可执行建议：降低 tile、缩小图像或切换 CPU；其他 `RuntimeError` 也会保留为明确的推理失败；
- 输出转换不会修改输入数组；请求非4×时 `cv2.resize` 产生一张最终尺寸的新图。

tile 不能解决权重结构不匹配、BGR/RGB 混用或 FP16 dtype 不匹配；它只在输入契约正确时降低单次网络前向的激活内存。

## 小结

- CleanCanvas 将 OpenCV BGR `uint8` 明确转为 RGB `[0,1]` Tensor，并在同一 device/dtype 下以 `eval()` + `inference_mode()` 推理，最后还原 BGR `uint8`。
- Anime 的 RRDBNet 与 General 的 SRVGGNetCompact 是不同 `nn.Module`，必须与各自 checkpoint 严格配对。
- RRDB 的 `cat` 沿通道汇集历史特征，残差要求 shape 对齐；PixelShuffle 重排48通道为3通道的4×空间输出。
- tile 用重叠输入保留卷积边界上下文，裁掉 pad 输出后写回中心；它降低中间激活峰值，而非神奇地消除完整输出的显存成本。
