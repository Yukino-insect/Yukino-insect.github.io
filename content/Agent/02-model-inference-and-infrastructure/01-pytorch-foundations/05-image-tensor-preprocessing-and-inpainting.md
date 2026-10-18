+++
date = '2026-10-09T20:00:00+08:00'
draft = false
title = '项目实战：图像如何变成 PyTorch 张量——预处理、mask 与 LaMa 修复'
math = true
+++

深度学习图像代码最容易让初学者困惑的部分，往往不是网络，而是网络前后的十几行转换。它们看似只是 `transpose`、`astype`、`unsqueeze`，却决定模型看到的是正确颜色、正确范围、正确形状，还是一张被悄悄打乱的数据。以 `TorchScriptLaMaEngine.inpaint()` 为例，我们把这条链路完整拆开。

## 先认识三个实际模型

本组实战文章会遇到三个模型，它们的任务不同，输入输出也不同：

- **ResNet**：分类模型，把一张图片映射为类别 logits；它回答“这张图片更像哪一类”。
- **LaMa**：图像修复（inpainting）模型，把完整图片和一个待填补区域映射为完整图片；它回答“被遮住的区域根据周围上下文可能是什么样子”。LaMa 的名称来自 *Resolution-robust Large Mask Inpainting*，核心思想是让网络利用较大范围的图像上下文，而不是只做局部像素涂抹。
- **Real-ESRGAN**：超分辨率模型，把低分辨率图片映射为更大尺寸的图片；它回答“怎样生成视觉上更自然的高分辨率细节”。

LaMa 和 Real-ESRGAN 都是生成式/重建式推理：输出是模型根据训练分布作出的合理猜测，不是被遮挡像素或真实高频细节的历史记录。理解这个边界，才能正确解释“效果很好”到底意味着什么。

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

### 先把真实调用链定位出来

这个项目的模型代码并不是由页面层直接调用。单图和视频帧最终都会在 `backend/main.py` 进入 `_repair(frame)`：

```python
mask = self._mask(frame, polygons)
if not np.any(mask):
    return frame
repaired = self._engine().inpaint(frame, mask)
```

这四行分别意味着：

1. `_mask` 根据静态 `MaskPlan`、OCR 多边形或颜色筛选，返回与 `frame` 同高宽的 `uint8 [H,W]`；
2. `np.any(mask)` 检查是否至少有一个非零像素。没有修复区域时，直接返回原数组，既不运行模型，也不触发模型加载；
3. `_engine()` 按当前模式懒加载并缓存引擎。一个视频任务不会每帧重新读权重；
4. `inpaint(frame, mask)` 是所有修复引擎共同的输入/输出契约：输入 BGR 数组和二维 mask，返回 BGR 数组。

因此，后文的 `TorchScriptLaMaEngine.inpaint()` 不是一个孤立示例，而是这个统一契约中 LaMa/Anime-LaMa 的具体实现。它接收到的 `frame` 已经是 OpenCV/NumPy 的 `[H,W,3] uint8 BGR`，`mask` 已经是 `[H,W] uint8`，而不是文件路径、PIL 图片或 GUI 坐标。

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

项目的 `_pad_to_modulo` 可以压缩为如下逻辑：

```python
padded_height = (height + modulo - 1) // modulo * modulo
padded_width = (width + modulo - 1) // modulo * modulo
padding = ((0, padded_height - height), (0, padded_width - width), (0, 0))
return np.pad(image, padding, mode="constant" if constant else "symmetric")
```

假设输入高宽为 `721×1283`，LaMa 的 `modulo=8` 会得到 `H_pad=728`、`W_pad=1288`，因此只在**下边**补 7 行、在**右边**补 5 列。`padding` 的三组数分别对应 H、W、C 的“前、后”补齐量，所以颜色通道的 `(0, 0)` 绝不能漏掉。

调用图像时 `constant=False`，`symmetric` 会镜像边界值；调用 mask 时 `constant=True`，补出的像素必为 0。这里的参数差异是语义，而不仅是图像处理技巧：镜像图像可给卷积边缘一个较自然的上下文，而扩张 mask 到虚拟 padding 区会改变模型的修复条件。二维 mask 进入该函数时会先临时扩成 `[H,W,1]`，所以之后的 `[:, :, 0]` 正是去掉这个辅助通道，不是随意索引。

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

## 为什么矩形 mask 去水印反而可能效果很好

这是使用 CleanCanvas 时非常自然的疑问。答案是：**LaMa 并不是在 mask 内寻找一个“水印对象”然后删除；它把整个 mask 区域当作洞（hole），再依据洞外和洞内未遮挡的统计线索生成一块新的内容。** 水印覆盖的背景确实被一起遮住了，但这并不等于模型失去了所有信息。

### 矩形 mask 实际做了什么

假设原图是 $I$，二值 mask 是 $M$，其中 $M=1$ 表示允许修改。模型接收的是完整的 $(I,M)$，输出的是修复图像：

$$
\hat I = f_\theta(I,M)
$$

它通常会重点生成 $M=1$ 的区域；CleanCanvas 最后又把 $M=0$ 的像素强制替换回原图。因此矩形内部的背景并没有“被保留”，而是被重新预测；只是矩形外的背景、线条、颜色和纹理为预测提供了上下文。

### 水印为什么适合这种补全

很多水印具有以下特点：

1. **占图面积小**：矩形内部仍包含大量背景统计规律，模型容易判断这是天空、墙面、纸张、渐变或重复纹理。
2. **背景具有连续性**：水印左右、上下的颜色和纹理可以延伸进被遮挡区域。即使中间一整块不可见，模型仍可根据边界推断合理的延续。
3. **水印往往是稀疏叠加层**：文字、半透明 logo 和细线并不是原始场景的主体结构。把它们连同周围少量背景一起交给模型，比只抠文字笔画更容易避免残留边缘和“灰色幽灵”。
4. **训练时见过大区域缺失**：LaMa 的设计目标本来就包含较大 mask 和分辨率变化；它不是只针对一两个像素的修补器。较大的感受野/傅里叶卷积让网络能利用更远处的结构线索。

因此，矩形 mask 有时比沿着文字轮廓勾画的精确 mask 更好：它把抗锯齿边缘、半透明阴影和水印残留一起覆盖，给模型一个边界更明确的“待重建区域”。这不是因为矩形包含了某种水印识别能力，而是因为它更符合修复任务的输入语义。

### 为什么背景明明被遮住，模型仍能补得自然

可以把它和拼图联系起来：中间一块拼图被拿走，不代表周围的颜色、方向、重复纹理和结构全部消失。卷积层从局部邻域提取边缘和纹理，较大感受野或 Fourier 分支则帮助模型观察更远的周期结构。对均匀墙面、天空、纸张、渐变背景，可能的补全方案本来就很多，但视觉上都相近，所以模型看起来“恢复得很好”。

对人脸、文字、建筑细节或复杂重复图案，情况不同：模型可能生成一个合理但不真实的结果。LaMa 的成功应理解为“视觉连续性较好”，而不是“找回了被遮挡的原始像素”。

### 矩形 mask 也不是越大越好

矩形扩大后，模型获得了更大的自由度，但同时失去的真实背景也更多。实践中可以按下面顺序调整：

1. 先让 mask 完整覆盖水印、半透明边缘和阴影；
2. 在文字边缘外留少量余量，避免残留；
3. 不要无意义地覆盖相邻的重要物体、脸部或结构线；
4. 如果背景是规则纹理，尝试让矩形边缘落在纹理较平稳的位置；
5. 对复杂场景比较多个 mask，保留视觉连续且未改变非目标内容的结果。

CleanCanvas 的最终像素保护只保证矩形外不被修改，不能保证矩形内部一定符合事实。mask 越大，内部被重新生成的像素越多，潜在幻觉也越大。

### 矩形 mask 与精确 mask 的取舍

| mask 方式 | 优点 | 风险 |
| --------- | ---- | ---- |
| 紧贴文字轮廓 | 修改区域小 | 容易留下抗锯齿边缘、阴影和残留笔画 |
| 稍大矩形 | 输入稳定、边界简单、容易覆盖完整水印 | 可能重建过多真实背景 |
| 多边形/涂抹 | 能贴合不规则区域 | 边界复杂，局部缺口和细小孤岛更难处理 |

正确标准不是“mask 越精确越专业”，而是：水印是否完全覆盖、非目标区域是否保持、重建区域是否符合场景连续性。实际项目通常允许用户通过扩大或缩小 mask 反复比较，这比假设存在一个永远正确的轮廓更可靠。

## 第四步：迁移设备并仅做前向推理

### 权重怎样成为可调用模型

在第一次真正修复时，`create_inpaint_engine` 根据模式创建 `TorchScriptLaMaEngine`。其初始化的关键代码是：

```python
path = ModelStore(model_dir).ensure(asset, allow_bundled_fallback=asset is LAMA_ASSET)
self.model = torch.jit.load(str(path), map_location="cpu").to(self.device).eval()
```

`asset` 描述权重文件名、下载地址和 MD5；`ensure` 会先检查缓存哈希，缺失时下载到临时文件，校验通过后才移动到正式位置。这样取消下载不会留下一个被误认为有效的半截权重文件。

`torch.jit.load` 读取的是已经导出的 **TorchScript** 图，而不是在本项目中重新定义一个 Python `nn.Module` 再 `load_state_dict`。返回对象仍像函数一样可调用，即后文的 `self.model(image_tensor, mask_tensor)`；但模型内部结构及其双输入签名封装在 `.pt` 文件中。`map_location="cpu"` 先保证权重可在 CPU 内存中安全反序列化，随后 `.to(self.device)` 才把模型参数迁往实际推理设备，`.eval()` 则切换 Dropout、BatchNorm 等会区分训练/推理状态的层。

`device="auto"` 也不是只看一次 `torch.cuda.is_available()` 就宣称成功：工厂会实际尝试 CUDA 初始化/加载，失败后再尝试 CPU；用户显式指定 `cuda` 或 `cpu` 时则不静默改选另一个设备。这样“能检测到 GPU”和“这份权重能在当前 GPU 上真正运行”被区分开来。

模型调用前，两个张量都执行 `.to(self.device)`：

```python
with torch.inference_mode():
    result = self.model(
        image_tensor.unsqueeze(0).to(self.device),
        mask_tensor.unsqueeze(0).to(self.device),
    )
```

模型的参数在 CPU 还是 CUDA，输入张量就必须在同一设备；CPU 模型和 CUDA 输入相加/卷积会报设备不一致错误。`inference_mode()` 表示不记录自动求导历史，推理阶段通常更省内存、开销更低。它不等于 `eval()`，模型加载时调用的 `.eval()` 已经负责切换某些层的推理行为；第六篇会把二者精确区分。

这个调用的返回 `result` 仍是 GPU 或 CPU Tensor；在 LaMa 当前权重契约下，成功时它应有 `[1,3,H_pad,W_pad]`。如果 CUDA 阶段报显存不足，项目会把底层 `RuntimeError` 转为提示用户切换 CPU、缩小选区或降低分辨率的 `InpaintError`。错误包装不会修复输入契约，但能把“模型调用失败”转换为用户可以操作的边界条件。

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

需要补充一个项目中的细节：这条赋值之前，LaMa 路径会调用 `_finish_ink_on_flat_background(...)`。它只在 mask 内连通域的周围采样环在 Lab 空间中足够一致、且原始区域像稀疏深色笔画时，才用该环的真实背景中位数处理残留的灰色文字笔画。条件不满足时保持网络输出不变；无论条件是否满足，最后的布尔索引赋值都会恢复 mask 外的原图。换言之，后处理有两层不同职责：前者是针对平坦底色的保守质量修正，后者是不容破坏的像素边界。

### 用真实断言检查一次接口，而不是凭肉眼猜

将下列检查临时放在 `inpaint` 的模型调用前后，能比“结果看着不对”更快判断是哪一层违约：

```python
assert image_bgr.dtype == np.uint8 and image_bgr.ndim == 3
assert mask.dtype == np.uint8 and mask.shape == image_bgr.shape[:2]
assert image_tensor.shape == (3, padded_image.shape[0], padded_image.shape[1])
assert mask_tensor.shape == (1, padded_mask.shape[0], padded_mask.shape[1])

with torch.inference_mode():
    result = self.model(
        image_tensor.unsqueeze(0).to(self.device),
        mask_tensor.unsqueeze(0).to(self.device),
    )

assert result.shape[0] == 1 and result.shape[1] == 3
assert result.device.type == self.device
```

前四个断言检查的是 NumPy → Tensor 的输入契约；后两个检查的是模型返回的 batch/通道和设备。它们是调试期的防线，不建议在性能敏感的逐帧生产循环中无条件保留大量检查；不过任何一次改模型、权重或预处理时，都值得重新运行。

## Manga 路径为何不同

`MangaEngine` 先执行 `BGR → GRAY`，构造 `[1, 1, H, W]` 灰度张量；除主修复网络外还调用一份线稿模型，生成 `lines`。灰度和线稿归一化到 `[-1, 1]` 后，与二值 mask、随机噪声和全 1 张量一起喂给漫画修复网络。

因此彩色画面不适合 Manga：mask 内输出来自灰度模型，最终再 `GRAY → BGR` 后三个通道相同，色相和饱和度无法凭配置找回来。这不是“GPU 算得不够好”，而是输入信息在最开始就被丢弃了。

## 小结

- 图像推理要同时核对颜色顺序、数值范围、dtype、shape、设备和模型输入契约；任一项错了都可能静默降低质量。
- CleanCanvas Studio 的 LaMa 输入是 RGB `[1, 3, H, W]`、0–1 的 `float32`；mask 是 `[1, 1, H, W]` 的 0/1 浮点张量。
- padding 是为网络的下采样结构服务，结果必须裁回原尺寸。
- mask 决定可修改区域而非模型可见区域；最后恢复 mask 外原像素是一项明确的工程安全约束。
