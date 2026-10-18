+++
date = '2026-10-05T20:10:00+08:00'
draft = false
title = 'OpenCV 图像本质与常见操作：从像素、掩膜到修复和超分'
math = true
+++

图片去文字、去水印、制作掩膜、局部修复和超分辨率，看上去像是不同功能；从程序角度看，它们都在处理同一件事：一个带有空间坐标、通道和数据类型的数值数组。

如果不了解图像数组，常见问题会显得像“模型不稳定”：颜色发蓝、掩膜位置偏移、边缘出现锯齿、透明背景变黑、修复区域过大、保存后颜色变化。事实上，其中大部分问题在模型推理之前就已经产生。

本文从 OpenCV 的图像表示出发，逐步说明常用操作的数学和工程含义，并把它们连接到去水印、掩膜、局部修复和超分辨率任务。目标不是记住 API，而是能判断某个操作改变了什么、为什么要这样做、何时不该这样做。

## 一、先把图像看成数组，而不是“照片文件”

一张常见彩色图在 OpenCV 中通常是一个三维 NumPy 数组：

```python
import cv2

image = cv2.imread("input.png", cv2.IMREAD_COLOR)
print(image.shape)
print(image.dtype)
```

典型输出如下：

```text
(1080, 1920, 3)
uint8
```

它表示：

- 高度为 `1080` 个像素；
- 宽度为 `1920` 个像素；
- 每个像素有 3 个通道；
- 每个通道使用 `uint8` 保存，范围是 `0` 到 `255`。

在 OpenCV 的默认约定中，三个通道顺序是 **BGR**：蓝、绿、红，而不是常见的 RGB。

```text
image[y, x] = [B, G, R]
```

这里有两个必须建立的习惯：

1. 数组索引顺序是 `y, x`，即先行后列；
2. OpenCV 默认是 BGR，Pillow、Matplotlib 和多数深度学习示例常使用 RGB。

### 1. 像素、通道和文件体积不是一回事

一张 `4000×3000`、三通道、`uint8` 的未压缩彩色图需要的原始内存大约是：

$$
4000 \times 3000 \times 3 = 36{,}000{,}000\ \text{bytes}
$$

约为 34.3 MiB。它保存为 JPEG 后可能只有几 MB，也可能保存为 PNG 后有十几 MB。磁盘文件体积受压缩、纹理和格式影响；模型推理、缩放和逐像素操作主要受**像素数量**影响。

因此，对于修复或超分任务，更应关注：

```python
height, width = image.shape[:2]
pixel_count = height * width
print(width, height, pixel_count)
```

宽高各翻倍时，总像素数变为四倍；如果超分到 4×，输出总像素通常变为输入的 16 倍。

### 2. `uint8` 的便利与陷阱

`uint8` 很适合保存图像，但不适合直接做可能越界的算术。

```python
import numpy as np

pixel = np.array([250], dtype=np.uint8)
print(pixel + 20)  # 结果会回绕，不是 270
```

图像亮度、融合和归一化等操作应先转为浮点数，再裁剪回合法范围：

```python
result = image.astype(np.float32) * 1.15
result = np.clip(result, 0, 255).astype(np.uint8)
```

这也是为什么很多深度学习模型会把输入转换为 `float32` 并归一化到 `[0, 1]` 或 `[-1, 1]`：模型需要连续数值计算，而不是 8 位整数的截断和回绕。

## 二、坐标、切片与 ROI：图像处理最常见的偏移来源

图像界面常用 `(x, y)` 表示坐标，数组使用 `[y, x]` 索引。两者混淆后，处理区域会发生转置或偏移。

假设一个矩形区域用 `(xmin, xmax, ymin, ymax)` 表示，正确的 NumPy 切片是：

```python
roi = image[ymin:ymax, xmin:xmax]
```

其中：

- `x` 对应列，即宽度方向；
- `y` 对应行，即高度方向；
- Python 切片右边界不包含在内，因此 ROI 的宽高分别为 `xmax - xmin` 与 `ymax - ymin`。

### 1. 切片通常是视图，不是副本

下面的 `roi` 通常与原图共享内存：

```python
roi = image[100:200, 300:500]
roi[:, :] = 0
```

这会直接把原图对应区域改黑。若要在局部试验而不修改原图，需要显式复制：

```python
roi = image[100:200, 300:500].copy()
```

在去水印和手工调试掩膜时，这一点尤其重要。一个临时 ROI 预处理若意外改写原图，后续得到的结果就无法判断到底来自模型还是来自前处理副作用。

### 2. 显示坐标不一定等于原图坐标

桌面程序通常会把原图等比缩放到预览框，并在四周添加黑边。用户在预览框上画出的坐标属于“显示坐标”，不能直接传给原图。

如果原图缩放比例为 $s$，预览左上角相对原图有偏移 $(l, t)$，则预览坐标 $(x_p, y_p)$ 应转换为：

$$
x = \frac{x_p - l}{s}, \qquad y = \frac{y_p - t}{s}
$$

这就是视频/图片修复工具需要保存缩放比例、黑边和实际显示矩形的原因。它不是 GUI 细节，而是 mask 是否落在正确像素上的前提。

## 三、BGR、RGB、灰度、HSV 和 Lab：颜色空间改变的是“表达方式”

颜色空间不是给图像换滤镜，而是用不同坐标系描述同一个颜色。

| 空间 | OpenCV 常见用途 | 适合解决的问题 |
| --- | --- | --- |
| BGR | 默认读写、显示前处理 | 与 OpenCV API 直接配合 |
| RGB | Pillow、Matplotlib、深度学习模型 | 与模型或其他库交换数据 |
| Gray | 阈值、边缘、连通域 | 只关心明暗结构 |
| HSV | 颜色范围筛选 | 按色相、饱和度、亮度提取目标 |
| Lab | 感知颜色差异 | 局部颜色相近性、轮廓细化 |

### 1. BGR 与 RGB：最隐蔽的颜色错误

OpenCV 读取的是 BGR：

```python
bgr = cv2.imread("input.png")
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
```

若直接把 BGR 数组交给期待 RGB 的模型或 Matplotlib，红蓝通道会交换。程序不会报错，但天空可能偏红、皮肤可能偏蓝，属于“结果看起来奇怪但难定位”的典型问题。

返回 OpenCV 保存或继续处理前，应转回 BGR：

```python
bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
```

### 2. 灰度图不是“黑白图片”，而是明暗单通道

```python
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
```

灰度图形状通常为 `(height, width)`。每个值描述亮度，不再保留颜色信息。阈值、连通域和很多边缘操作基于灰度，是因为它们关心“哪里亮、哪里暗”，不关心原本是红还是蓝。

但灰度转换会丢失颜色信息。若要从红色印章中提取文字，直接灰度化可能不如 HSV 或 Lab 有效。

### 3. HSV：按颜色取范围

HSV 将颜色拆成：

- H：色相；
- S：饱和度；
- V：明度。

提取一类明显颜色时，HSV 往往比直接比较 BGR 稳定：

```python
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
lower_red = np.array([0, 80, 80])
upper_red = np.array([10, 255, 255])
mask = cv2.inRange(hsv, lower_red, upper_red)
```

注意红色跨越 HSV 的色相边界，通常需要两个区间再取并集。HSV 适合颜色清晰的图标、印章和标记，不适合颜色与背景接近的半透明水印。

### 4. Lab：更适合讨论“颜色差异”

Lab 将颜色表示为亮度 $L$ 与两个颜色对立轴 $a、b$。在局部区域中，比较 Lab 距离通常比直接比较 BGR 差更接近人眼感受。

这对文字轮廓细化很有用：先由 OCR 给出候选多边形，再在多边形内部寻找与局部背景颜色差异较明显的像素，可减少外接矩形误伤背景的面积。

## 四、缩放与插值：每一次 resize 都在生成新像素

缩放不是简单复制数组。目标图像中的一个像素通常需要从源图多个像素估计得到，这个估计方法就是插值。

```python
smaller = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
larger = cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_CUBIC)
```

常用插值及含义：

| 插值 | 本质 | 常见场景 |
| --- | --- | --- |
| `INTER_NEAREST` | 复制最近像素 | 标签图、像素风、离散 mask |
| `INTER_LINEAR` | 邻近像素线性加权 | 一般预览与普通缩放 |
| `INTER_CUBIC` | 使用更大邻域的三次插值 | 放大照片，速度较慢 |
| `INTER_AREA` | 面积关系重采样 | 缩小照片，减少锯齿和摩尔纹 |
| `INTER_LANCZOS4` | 较大邻域的 sinc 类核 | 高质量缩放，计算成本较高 |

### 一个必须区分的事实：图像与 mask 的插值不能混用

照片缩放时使用线性、三次或 Lanczos 可以让画面更平滑；二值 mask 缩放时使用这些插值会生成 `1` 到 `254` 的灰色边缘，使“是否修复”的边界变得不明确。

```python
resized_image = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
resized_mask = cv2.resize(mask, (640, 360), interpolation=cv2.INTER_NEAREST)
```

如果 mask 必须缩放，优先使用 `INTER_NEAREST`，随后再显式二值化：

```python
_, resized_mask = cv2.threshold(resized_mask, 127, 255, cv2.THRESH_BINARY)
```

超分辨率模型与传统插值的区别也在这里：插值只根据邻近已知像素平滑估计；Real-ESRGAN 等模型会根据训练得到的先验生成更锐利的纹理和边缘，但这些细节是推测，不是从原图中无损找回的事实。

## 五、阈值、掩膜和按位运算：规定“哪里允许改变”

掩膜通常是一张与原图同宽高的单通道数组：

```text
0   黑色  保留原图
255 白色 允许处理或选中区域
```

创建矩形 mask：

```python
mask = np.zeros(image.shape[:2], dtype=np.uint8)
cv2.rectangle(mask, (xmin, ymin), (xmax, ymax), 255, thickness=-1)
```

### 1. 二值阈值的意义

```python
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
_, mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
```

它不是“识别文字”，而是按亮度把像素分成两类。阈值 `180` 的意思是亮度大于 180 的像素写为 255，其余写为 0。适合背景和前景亮度差异明显的场景。

当光照或背景不均匀时，可用自适应阈值：

```python
mask = cv2.adaptiveThreshold(
    gray,
    255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    31,
    5,
)
```

它会为每个局部窗口计算阈值，但并不保证更好：纹理背景会被当成前景。阈值方法适合已知局部区域，不应在复杂整图上盲目替代 OCR。

### 2. `bitwise_and` 与掩膜合成

```python
selected = cv2.bitwise_and(image, image, mask=mask)
```

结果只保留 mask 为非零的位置。更常见的工程需求是“只用处理结果替换 mask 内像素”：

```python
output = image.copy()
output[mask > 0] = repaired[mask > 0]
```

这条赋值是局部修复最重要的保护措施之一。无论模型、编码器或后处理怎样变化，mask 外的已解码像素都保持来自原图。

### 3. Alpha 通道与二值 mask 不相同

PNG 可能有第四个 alpha 通道，形状是 `(H, W, 4)`：

```text
[B, G, R, A]
```

alpha 表示透明度，可以有 0 到 255 的连续值；二值 mask 表示处理权限，通常只使用 0 和 255。两者都叫“蒙版”时很容易混淆，但语义不同。

将带透明背景的 PNG 保存为 JPEG 时，JPEG 无法保存 alpha，必须选择背景色：

```python
from PIL import Image

rgba = Image.open("input.png").convert("RGBA")
background = Image.new("RGB", rgba.size, "white")
background.paste(rgba, mask=rgba.getchannel("A"))
background.save("output.jpg", quality=95)
```

## 六、形态学与连通域：修整 mask，而不是替代语义理解

形态学操作用一个小核在局部邻域内改变 mask：

```python
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
dilated = cv2.dilate(mask, kernel, iterations=1)
eroded = cv2.erode(mask, kernel, iterations=1)
```

含义可以直接理解为：

- 膨胀 `dilate`：白色区域向外扩张，适合覆盖文字边缘、抗锯齿和描边；
- 腐蚀 `erode`：白色区域向内收缩，适合减小误选范围；
- 开运算：先腐蚀再膨胀，常用于去掉小白噪点；
- 闭运算：先膨胀再腐蚀，常用于填补小黑洞和断裂笔画。

```python
opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
```

核的尺寸以像素为单位。`3×3` 和 `15×15` 的实际效果差异很大，不能脱离图像分辨率讨论。对高分辨率原图，先在预览图上确认边界，再换算到原图像素更可靠。

连通域分析能把二值 mask 中相互连接的区域分开：

```python
count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, connectivity=8)

for label in range(1, count):
    x, y, width, height, area = stats[label]
    if area < 12:
        mask[labels == label] = 0
```

这适合删除细小孤立噪点，或在局部 ROI 中保留面积、位置符合预期的文字笔画。它不能知道“这是否是一个字”，所以仍需结合 OCR、颜色、位置或人工确认。

## 七、局部修复：传统 inpaint 与 AI inpainting 的边界

OpenCV 的 Telea 修复可直接使用：

```python
repaired = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
```

它依据边界附近像素向修复区域传播颜色和结构，适合小字幕、平滑背景、连续纹理。它不理解人物、物体或复杂线稿，因此大面积遮挡或动漫人物边缘常需要 AI 修复模型。

AI inpainting 的输入同样是图像和 mask，但模型会利用训练得到的上下文先验补全区域。它能给出更合理的结构，却也可能生成原图中从未存在过的细节。工程上应遵循：

```text
先缩小 mask 到必要范围
→ 生成候选修复结果
→ 仅把 mask 内像素合回原图
→ 放大检查边缘、线稿和残留文字
```

不要把“模型能修复”理解为“mask 可以随意画大”。mask 是模型的修改权限，边界越宽，允许被改写的真实内容越多。

## 八、超分辨率：分辨率、显示大小和真实信息

把图片显示得更大有三种完全不同的情况：

1. GUI 预览缩放：只改变显示尺寸，不改变文件；
2. `cv2.resize()`：插值生成新像素，不使用学习到的先验；
3. 超分模型：根据训练数据生成更可能的边缘和纹理。

Real-ESRGAN 等模型常以原生 4×网络推理，再根据用户选择输出 1×、1.5×、2×、3×或 4×。这解释了两个现象：

- 1× 输出仍可能经过模型，画面并非简单复制；
- 4× 输出的宽和高各为原图约 4 倍，总像素约为原图 16 倍。

大图通常采用分块推理：

```text
原图
 ├─ 带少量重叠边缘的 tile 1 → 模型推理
 ├─ 带少量重叠边缘的 tile 2 → 模型推理
 └─ 拼接为完整输出
```

重叠边缘用于减轻 tile 接缝；分块降低单次显存峰值，但不会让总计算量消失。图像越大、倍率越高，编码、内存复制、推理和输出写盘都会变慢。

## 九、读写文件：格式、颜色和元数据

`cv2.imread()` 和 `cv2.imwrite()` 对常见格式方便，但在 Windows 非 ASCII 路径上可能受环境影响。使用字节读写可以提高兼容性：

```python
from pathlib import Path

import cv2
import numpy as np


path = Path("含中文目录/输入.png")
data = np.fromfile(path, dtype=np.uint8)
image = cv2.imdecode(data, cv2.IMREAD_COLOR)

ok, encoded = cv2.imencode(".png", image)
if not ok:
    raise RuntimeError("PNG 编码失败")
encoded.tofile("含中文目录/输出.png")
```

文件格式还会影响处理结果：

- JPEG 有损压缩，不支持 alpha；
- PNG 支持无损压缩和 alpha，适合 mask、图标和中间结果；
- WebP 可在较小体积下保存较好质量，也可支持透明；
- TIFF 常用于保留高位深或专业图像数据；
- ICO 是容器格式，一个文件可含 16、32、48、64、128、256 等多个尺寸。

不要只通过扩展名判断内容。格式转换应由实际编码器完成；把 `file.png` 改名为 `file.jpg` 不会转换像素数据。

## 十、一个可运行的小实验：检查、制作 mask、修复和验收

下面脚本展示一条不依赖 AI 的最小链路。它会读取图片、创建一个矩形 mask、用 Telea 修复、保证 mask 外像素不变，并写出结果。

```python
from pathlib import Path

import cv2
import numpy as np


source = Path("input.png")
target = Path("output.png")

data = np.fromfile(source, dtype=np.uint8)
before = cv2.imdecode(data, cv2.IMREAD_COLOR)
if before is None:
    raise RuntimeError(f"无法读取：{source}")

height, width = before.shape[:2]
print(f"shape={before.shape}, dtype={before.dtype}")

# 替换为需要修复的真实坐标，右边界和下边界不包含在 ROI 中。
xmin, ymin, xmax, ymax = 20, 20, min(180, width), min(80, height)
mask = np.zeros((height, width), dtype=np.uint8)
mask[ymin:ymax, xmin:xmax] = 255

candidate = cv2.inpaint(before, mask, 3, cv2.INPAINT_TELEA)

# 显式合成，确保 mask 外的已解码像素来自原图。
after = before.copy()
after[mask > 0] = candidate[mask > 0]

assert np.array_equal(before[mask == 0], after[mask == 0])

ok, encoded = cv2.imencode(".png", after)
if not ok:
    raise RuntimeError("输出编码失败")
encoded.tofile(target)
print(f"已保存：{target}")
```

可以在此基础上逐步替换：

- 用 OCR 多边形替代矩形坐标；
- 用形态学微调 mask；
- 用 AI inpainting 替代 Telea；
- 用 Real-ESRGAN 在修复完成后增强输出；
- 增加处理前后并排预览和输出属性日志。

每次只替换一个环节，才能知道质量、速度或颜色变化究竟来自哪里。

## 十一、常见误区清单

| 现象 | 常见原因 | 优先检查 |
| --- | --- | --- |
| 红蓝颜色颠倒 | BGR/RGB 混用 | 模型、Pillow、Matplotlib 的通道约定 |
| mask 位置偏移 | `(x, y)` 与 `[y, x]` 混用，或忽略预览缩放/黑边 | 坐标映射与 ROI 切片 |
| mask 边缘灰蒙蒙 | 对 mask 使用线性/三次插值 | 改用最近邻并重新二值化 |
| 修复伤到主体 | mask 过大或把候选框当最终 mask | 红色最终掩膜预览、局部 ROI |
| 超分后细节失真 | 将模型推测当作真实恢复 | 缩小倍率、切换模型、人工复核 |
| PNG 转 JPEG 后透明变黑或变白 | JPEG 不支持 alpha | 明确选择合成背景色 |
| 大图处理很慢 | 像素数、倍率和模型计算量过大 | 分辨率、tile、设备与输出倍率 |

## 十二、总结：建立一条可解释的图像处理链

理解图像处理，不是背诵 `cv2` 函数名，而是始终回答四个问题：

1. 当前数组的形状、通道顺序和数据类型是什么？
2. 当前操作改变的是坐标、颜色表达、像素值，还是文件编码？
3. 哪些像素允许改变，哪些像素必须保持原样？
4. 输出结果如何验证，而不是只凭缩略图判断？

对于去水印、去字幕、局部修复和超分，最可靠的工程流程是：先在原图坐标系中确定区域，构造并检查 mask，再调用传统算法或模型，最后验证输出尺寸、颜色、mask 外像素和局部视觉效果。

在了解这些基础后，可以继续阅读 [IOPaint 精确去除文字与图片增强：Python 遮罩、局部修复和像素级验收](IOPaint 精确去除文字与图片增强：Python 遮罩、局部修复和像素级验收.md)，学习如何将 mask、AI 修复和像素级验收组合成可重复的实践流程。
