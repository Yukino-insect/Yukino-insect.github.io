+++
date = '2026-10-15T21:00:00+08:00'
draft = false
title = 'PyTorch 视觉预训练模型推理详解：torchvision、Pillow、权重与 CleanCanvas 图像模型'
math = true
+++

前一篇建立了 CleanCanvas Studio 的项目地图，但地图不能代替走一遍道路。本篇专门回答一个更具体的问题：**拿到一个已经训练好的 PyTorch 模型后，程序究竟怎样完成一次推理？**

我们会从最容易观察的分类模型开始，逐步进入图像到图像模型，最后对照 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 中的 LaMa 和 Real-ESRGAN。每一步都记录输入的 `shape`、`dtype`、设备和值域，因为模型推理失败或结果异常，通常不是“网络不够聪明”，而是这几个契约没有对齐。

## 推理不是一个函数调用，而是一条边界协议

可以把推理拆成六个阶段：

```text
加载结构与权重
    ↓
读取原始数据
    ↓
预处理：颜色、尺寸、shape、dtype、值域
    ↓
前向计算：model(input)
    ↓
解释输出：概率、类别、图像或分数
    ↓
后处理：恢复尺寸、颜色、格式并保存
```

训练时我们还要准备标签并计算 `loss`；推理时没有标签，也不执行 `backward()` 或 `optimizer.step()`。推理阶段的模型参数应保持不变，程序只是在调用一个已经确定的函数 $f_\theta$：

$$
\hat{y}=f_\theta(x)
$$

`θ` 是加载的权重，`x` 是经过预处理的输入，`ŷ` 是模型输出。模型的任务决定 `ŷ` 的含义：分类器输出类别分数，修复模型输出图像，超分模型输出更大尺寸的图像。

## 先分清 PyTorch、torchvision、Pillow 和模型权重

示例里的四个名字经常一起出现，但它们并不是同一个东西，更不存在“安装 Pillow 就拥有了模型”这种关系。它们在视觉推理链中处于不同层次：

```text
cat.jpg / PNG / WebP 文件
        │
        │ Pillow：解码文件，得到带颜色模式和尺寸的 PIL.Image
        ▼
PIL.Image（例如 RGB，宽×高）
        │
        │ torchvision：按模型训练时的规则 resize、裁剪、缩放、归一化
        ▼
torch.Tensor（例如 float32 [3, 224, 224]）
        │
        │ PyTorch：将 Tensor 与参数在 CPU/GPU 上执行前向计算
        ▼
logits / 特征 / 输出图像 Tensor
```

| 名称 | 在本课中的职责 | 它不负责什么 |
| ---- | -------------- | ------------ |
| `torch` / PyTorch | Tensor、自动求导、`nn.Module`、CPU/GPU 运算、保存/加载参数 | 不能仅凭一个 JPEG 文件猜出正确的图像预处理规则 |
| `torchvision` | PyTorch 的计算机视觉扩展：视觉模型、数据集、图像变换和部分读写工具 | 不是所有 PyTorch 模型的必需依赖，也不替第三方项目决定网络结构 |
| Pillow（安装名 `Pillow`，导入名 `PIL`） | 解码/编码常见图像文件，创建、转换和保存 `Image` 对象 | 不执行神经网络，不保存或训练模型权重 |
| 模型权重 | 训练得到的数值参数，例如卷积核、线性层的 `weight` 与 `bias` | 不是图像文件，也不能脱离匹配的网络结构独立预测 |

因此，`from PIL import Image` 只是得到一个适合检查和处理的图片对象；`from torchvision.models import resnet18` 是取得 ResNet-18 的**网络定义**；`resnet18(weights=...)` 才会把一组训练完成的参数装入这张网络。最终真正执行乘法、卷积和激活函数的是 PyTorch。

### Pillow 为什么出现在模型代码前面

磁盘上的 `cat.jpg` 是经过 JPEG 编码的字节序列，既不是 NumPy 数组，也不是 PyTorch Tensor。Pillow 的 `Image.open()` 负责识别和解码它，返回 `PIL.Image.Image`。`Image.open()` 是惰性打开：文件会在真正处理像素时读取；因此用 `with` 管理文件句柄更稳妥。

```python
from PIL import Image

with Image.open('cat.jpg') as source:
    print(source.format)  # 例如 JPEG：文件编码格式
    print(source.mode)    # 例如 RGB、RGBA、L（灰度）
    print(source.size)    # (宽, 高)，注意顺序不是 (高, 宽)
    image = source.convert('RGB')

print(type(image))        # PIL.Image.Image
print(image.mode, image.size)
```

`convert('RGB')` 的意义不是“让图片更好看”，而是消除输入通道的歧义。PNG 可能是 `RGBA`（四个通道，最后一个是透明度），灰度图可能是 `L`（一个通道）；而本例的 ResNet 权重训练时接收三通道 RGB。若不统一，后续可能直接因通道数不符报错，也可能把透明度或颜色以错误方式带入模型。Pillow 不知道某个模型需要 RGB；这项约定来自模型的训练过程。

Pillow 也能完成裁剪、缩放和保存，但本例不应该随意用它先做一套预处理，再让 `weights.transforms()` 做第二套。预处理的目标不是把图像“修饰得漂亮”，而是把输入变成**与该权重训练时相同的数值分布**。这件事必须由对应权重的说明来决定。

### torchvision 和 PyTorch 是怎样配合的

`torchvision` 是构建在 PyTorch 之上的视觉扩展库。它既可以提供 `resnet18` 这类已经写好的 `nn.Module`，也可以提供把 PIL 图像或图像 Tensor 转为模型输入的变换。它的结果仍然是 PyTorch Tensor，所以随后仍用 `.to(device)`、`model(batch)`、`torch.inference_mode()` 等 PyTorch API。

注意两个边界：

- `torchvision` 的模型只是许多 PyTorch 模型来源之一。你完全可以用纯 `torch.nn` 写模型，或加载 Hugging Face、OpenMMLab、Real-ESRGAN 等项目提供的网络与 checkpoint；那些权重并不会因为没有 `torchvision` 而失效。
- `torchvision.transforms.v2` 可用于自己训练的视觉数据管线，但**调用公开预训练权重推理时，优先使用 `weights.transforms()`**。后者与该权重版本绑定，避免你复制了一套看似相同、实际不完全一致的规则。

对 ResNet-18 的公开 ImageNet 权重而言，`weights.transforms()` 会将较短边 resize 到 256、中心裁剪为 `224×224`，把像素缩放到 `[0, 1]`，再按 RGB 三个通道使用均值 `[0.485, 0.456, 0.406]` 和标准差 `[0.229, 0.224, 0.225]` 归一化。它接收 PIL 图像或形状为 `[C,H,W]` / `[B,C,H,W]` 的图像 Tensor。[TorchVision 的 ResNet-18 权重文档](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet18.html)列出了这份输入契约；[模型与权重总览](https://docs.pytorch.org/vision/stable/models.html)也明确说明预处理会随模型和权重版本变化。

归一化对单个通道的计算是：

$$
x_{norm}=\frac{x-\mu}{\sigma}
$$

其中 $x$ 是已经缩放到 `[0, 1]` 的像素值，$\mu$ 是该通道的训练集均值，$\sigma$ 是标准差。比如一个纯红像素的原始 RGB 值为 `[255, 0, 0]`，缩放后为 `[1, 0, 0]`；红通道变成 $(1 - 0.485) / 0.229 \approx 2.25$。这并不表示像素“超过了最大亮度”，而是表示它相对于训练数据的平均红色强度偏高。模型的第一层就是在这样的数值尺度上训练出来的；直接喂入 `0` 到 `255` 的数会把输入放大约 255 倍，预测自然没有理由可靠。

### 权重为什么和 torchvision、Pillow 同时出现

权重文件只保存模型参数，不能规定“如何从一张 JPEG 得到输入张量”。可是在训练时，参数看到的是经过特定颜色处理、尺寸处理和归一化后的数据。因此一个可复用的预训练模型实际包含三份契约：

```text
网络结构：参数该放进哪些层，输入和输出的 shape 是什么
权重参数：这些层中 weight、bias 等张量的具体数值
输入/输出约定：颜色、尺寸、dtype、值域、类别标签和后处理方式
```

`torchvision` 的 `ResNet18_Weights` 恰好把最后两类信息放在一个权重枚举对象上：调用模型构造函数时它能定位并下载参数；`weights.transforms()` 给出匹配的输入变换；`weights.meta['categories']` 给出 1000 个输出下标对应的类别名。Pillow 只是将图片送到这套变换前的入口。换言之，Pillow 与权重之间没有直接的文件格式依赖；两者之所以在同一段代码中出现，是因为一个负责取得像素，另一个规定这些像素应怎样进入训练好的网络。

不要把 `ResNet18_Weights.DEFAULT` 当成永恒不变的实验名称。`DEFAULT` 表示当前库版本推荐的权重，未来可能指向更新版本；需要严格复现实验时，应记录并显式写出具体枚举值（例如 `ResNet18_Weights.IMAGENET1K_V1`）、`torch`/`torchvision` 版本及预处理方式。相同的道理也适用于第三方 `.pth`、`.pt` 和 checkpoint：先找出它匹配的网络和输入契约，再谈加载，不能把任何“权重文件”都塞进任何模型里。

### 运行本节最小示例前的安装与检查

本节的 ResNet 例子需要 `torch`、与其版本匹配的 `torchvision`，以及 Pillow。请优先按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 为你的 CPU/CUDA 环境选择 `torch` 和 `torchvision` 的配套命令；然后安装 Pillow：

```powershell
python -m pip install Pillow
python -c "import torch, torchvision; from PIL import Image; print(torch.__version__, torchvision.__version__, Image.__version__)"
```

下载公开权重的第一次运行需要网络，之后会从本机缓存读取。若导入 `torchvision` 时出现诸如“operator ... does not exist”的错误，通常是 `torch` 与 `torchvision` 安装来源或版本不匹配；不要只反复重装 Pillow，因为它并不包含 PyTorch 的算子。

## 案例一：ResNet 分类推理

### 先认识 ResNet-18：这段代码的模型意图

`resnet18` 是 torchvision 提供的 **ResNet-18 残差卷积网络**。它的原始任务是 ImageNet 的单标签 1,000 类图像分类：一张 RGB 图像经过卷积特征提取后，得到 1,000 个类别的原始分数。因此本节的 `softmax`、`topk` 和类别名称查询，是在回答“这张图最像 ImageNet 标签中的哪几类”，并不是通用的物体检测、图像修复或用户自定义分类器。

`ResNet` 的核心是残差连接。一个残差块不只计算 $F(x)$，还把输入直接加回去：

$$
y=F(x)+x
$$

这样网络学习的是“在已有特征上补充什么”。信息和梯度都有一条较直接的 shortcut 路径，深层网络因而更容易训练；当通道数或空间尺寸发生变化时，shortcut 会用投影把 shape 对齐。名称中的 `18` 是这套变体按惯例计数的 18 个带权重层（17 个卷积层加末端全连接层），不是 18 个类别，也不是 18 个独立模型。

对权重推荐的 `224×224` 输入，可将 `print(model)` 看到的结构先压缩为：

```text
[B, 3, 224, 224]
  → stem：7×7 卷积、归一化、激活、最大池化        [B, 64, 56, 56]
  → layer1 / layer2 / layer3 / layer4：残差 stage   [B, 64/128/256/512, 56/28/14/7, 56/28/14/7]
  → avgpool：每通道做全局平均                       [B, 512, 1, 1]
  → fc：Linear(512, 1000)                           [B, 1000] logits
```

前面的卷积和残差 stage 是通用视觉 **backbone（主干）**：从像素提取边缘、纹理、部件和更抽象的特征；最后 `fc` 是 ImageNet 的 **分类 head（任务头）**。本节只使用现成权重推理，不训练或重写这些层。后续迁移学习把 `fc` 替换为新的 `Linear(512, 类别数)`，正是“保留主干、替换任务头”，而非随意改一个层名。

### 下载模型并查看结构

```python
import torch
from torchvision.models import resnet18, ResNet18_Weights

weights = ResNet18_Weights.DEFAULT
model = resnet18(weights=weights)

print(model)
print('参数数量：', sum(p.numel() for p in model.parameters()))
```

`resnet18(weights=weights)` 做了两件事：创建 ResNet-18 的网络结构，并从官方权重地址下载参数。下载得到的不是“一个神奇的预测器”，而是许多层的 `weight` 和 `bias` 张量；结构决定这些张量如何组合，权重决定组合中的具体数值。

### 一张图片如何进入网络

```python
from PIL import Image

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = model.to(device).eval()
preprocess = weights.transforms()

image = Image.open('cat.jpg').convert('RGB')
input_tensor = preprocess(image)
batch = input_tensor.unsqueeze(0).to(device)

print(input_tensor.shape)  # [3, 224, 224]
print(batch.shape)         # [1, 3, 224, 224]
print(batch.dtype, batch.device)
```

这里发生了四次有明确含义的转换：

1. `convert('RGB')` 保证通道顺序与训练时一致；
2. `weights.transforms()` 按权重发布者规定的尺寸、裁剪和归一化处理图像；
3. `unsqueeze(0)` 增加 batch 维，单张图也要满足 `[N,C,H,W]` 接口；
4. `.to(device)` 让输入和模型参数位于同一设备。

### 前向计算和输出解释

```python
with torch.inference_mode():
    logits = model(batch)

print(logits.shape)  # [1, 1000]
probabilities = logits.softmax(dim=1)
top_prob, top_id = probabilities.topk(5, dim=1)

for probability, class_id in zip(top_prob[0], top_id[0]):
    name = weights.meta['categories'][class_id]
    print(name, float(probability))
```

`logits` 是 1000 个类别的原始分数，不是概率；`softmax(dim=1)` 才把同一张图的分数转换为总和为 1 的概率。`argmax` 或 `topk` 只是在解释输出，不会改变模型参数。注意这里没有 `sigmoid`：单标签多分类使用 softmax；二分类和多标签分类才通常对每个 logit 使用 sigmoid。这正是“输出层、损失函数和推理解释必须配套”的具体体现。

## 案例二：从零构造一个可保存和加载的模型

为了看清 `state_dict`，用课程前面的小分类器做一次完整闭环：

```python
import torch
from torch import nn

class TinyClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(2, 8), nn.ReLU(), nn.Linear(8, 1))

    def forward(self, x):
        return self.net(x).squeeze(1)

model = TinyClassifier()
torch.save(model.state_dict(), 'tiny-classifier.pth')

restored = TinyClassifier()
state = torch.load('tiny-classifier.pth', map_location='cpu', weights_only=True)
restored.load_state_dict(state, strict=True)
restored.eval()

with torch.inference_mode():
    logits = restored(torch.tensor([[89.0, 5.0]], dtype=torch.float32))
    probability = torch.sigmoid(logits)
print(probability)
```

这里必须再次写出 `TinyClassifier()`，因为 `state_dict` 只保存“参数名 → 参数张量”，不保存 `forward()` 的代码。`strict=True` 确保结构没有悄悄错配。输出层只有一个 logit，因此推理时使用 sigmoid；训练时则应把原始 logit 直接交给 `BCEWithLogitsLoss`，不要在训练和推理之间混淆这两个阶段。

## 案例三：TorchScript 图像修复模型

CleanCanvas 的 LaMa 路径使用 TorchScript。与 ResNet 分类不同，它需要两个输入：完整图像和 mask。模型不是只看被框选的小矩形，而是看完整图像，同时根据 mask 决定哪些位置允许生成补全。

**TorchScript 是什么？** 可以把它理解成将一个 PyTorch `nn.Module` 的可执行计算和参数导出为可加载工件的方式。训练/导出端通常通过 `torch.jit.script`（分析可脚本化代码）或 `torch.jit.trace`（记录示例输入走过的算子路径）生成它；部署端用 `torch.jit.load()` 恢复一个可调用的 ScriptModule，因此当前项目不必重新写出 LaMa 的 Python 网络类再注入参数。它仍依赖 PyTorch 运行时，也不会自动知道图片应为 RGB、mask 怎样二值化或尺寸如何补齐；这些输入/输出契约仍由模型发布者和引擎代码共同负责。`.pt`、`.pth` 这样的后缀本身不能区分 TorchScript 与普通权重文件，下一案例正好展示另一种格式。

LaMa（*Resolution-robust Large Mask Inpainting*）的任务是 **mask 引导的整图修复**：`完整图像 + 待修复 mask → 完整图像`。所以代码把整张图和同尺寸 mask 一起送入网络，而不是只裁出白色区域再放大；框外真实内容为模型补全洞内区域提供上下文。最终业务代码又强制恢复 mask 外像素，确保“网络能看全图”和“产品只允许改选区”这两件事并不冲突。

### 从 OpenCV 图像建立模型输入

```python
import cv2
import numpy as np
import torch

image_bgr = cv2.imread('input.png')          # [H, W, 3], uint8, BGR
mask = cv2.imread('mask.png', cv2.IMREAD_GRAYSCALE)  # [H, W], uint8

height, width = image_bgr.shape[:2]
image_rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB)
binary_mask = (mask > 0).astype(np.float32)

image_tensor = torch.from_numpy(
    image_rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
).unsqueeze(0)                              # [1, 3, H, W]
mask_tensor = torch.from_numpy(binary_mask).unsqueeze(0).unsqueeze(0)  # [1, 1, H, W]

print(image_tensor.shape, image_tensor.dtype, image_tensor.min().item(), image_tensor.max().item())
print(mask_tensor.shape, mask_tensor.unique())
```

这段代码与分类预处理有三个重要区别：图像从 HWC 变为 CHW；mask 需要额外的通道维；图像和 mask 共同构成模型输入。mask 的 `0/1` 不是概率，也不是灰度亮度，而是一个空间条件：`1` 表示允许模型修改，`0` 表示尽量保持原状。

### 加载 TorchScript 并执行前向推理

```python
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = torch.jit.load('big-lama.pt', map_location='cpu').to(device).eval()

with torch.inference_mode():
    repaired = model(image_tensor.to(device), mask_tensor.to(device))

print(repaired.shape)  # 常见为 [1, 3, H, W]
```

`torch.jit.load()` 恢复的是已经序列化的可执行模块；但它不会替你检查输入是否为 RGB、是否补齐到网络支持的尺寸，也不会替你把输出变回 OpenCV 图像。模型输出仍是张量，通常需要裁回 padding 尺寸、转回 CPU、CHW 变 HWC、乘回 255、裁剪到合法范围并转换回 BGR。

### 把案例三逐行对照到项目的 LaMa 引擎

上面的代码是最小版，而当前项目把它封装在 `backend/inpaint/engine.py` 的 `TorchScriptLaMaEngine`。它的公开业务接口不是 `model(...)`，而是：

```python
def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    ...
```

这行类型标注就是调用者必须满足的契约：传入 OpenCV BGR 的 `uint8 [H,W,3]` 图和 `uint8 [H,W]` mask；返回同尺寸的 BGR `uint8 [H,W,3]` 图。`ContentRepairProcessor` 因此不用导入 `torch`。在 `__init__()` 中，项目先用 `ModelStore.ensure()` 获取并校验 `big-lama.pt` 或 `anime-manga-big-lama.pt`，再执行等价于下面的加载流程：

```python
self.model = torch.jit.load(str(path), map_location="cpu").to(self.device).eval()
```

先 `map_location="cpu"` 的目的，是避免 checkpoint 强迫当前机器拥有它保存时的 CUDA 设备；`.to(self.device)` 才是项目根据用户设置迁移到 CPU 或 CUDA 的一步；`.eval()` 选择推理时层行为。它们都不关闭 autograd，所以真正调用处仍需要 `torch.inference_mode()`。

`inpaint()` 的关键数据流可压缩为如下代码。变量名和顺序与项目保持一致，但省略了错误包装：

```python
height, width = image_bgr.shape[:2]
rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB)
binary_mask = (mask > 0).astype(np.uint8)

padded_image = _pad_to_modulo(rgb, 8)
padded_mask = _pad_to_modulo(binary_mask, 8, constant=True)[:, :, 0]

image_tensor = torch.from_numpy(
    padded_image.transpose(2, 0, 1).astype(np.float32) / 255.0
)                                      # float32 [3, Hp, Wp]
mask_tensor = torch.from_numpy(
    padded_mask[np.newaxis].astype(np.float32)
)                                      # float32 [1, Hp, Wp]

with torch.inference_mode():
    result = self.model(
        image_tensor.unsqueeze(0).to(self.device),  # [1, 3, Hp, Wp]
        mask_tensor.unsqueeze(0).to(self.device),   # [1, 1, Hp, Wp]
    )
```

其中 `Hp`、`Wp` 是向上补齐到 8 的倍数后的尺寸。例如原图为 `721×1280`，则 `Hp=728`、`Wp=1280`。图像使用对称 padding，mask 使用常量 0 padding；后者的含义是“补出来的边缘绝不请求模型修复”。这不是为了凑整齐的形式主义，而是该 TorchScript 网络在当前实现中要求该空间尺度。`image_tensor` 的第一处 `unsqueeze(0)` 与 `mask_tensor` 的第二处 `unsqueeze(0)` 都是在增加 batch 维，不是在增加颜色通道。

下表把最容易混淆的每一行展开。这里的 `device` 是 Tensor 的存放/执行位置，而不是 NumPy 数组的属性；NumPy 数据始终先在 CPU 内存中。

| 阶段 | 值的类型和 shape | dtype / 值域 | 作用与副作用 |
| ---- | ---------------- | ----------- | ------------ |
| 调用入口 | `image_bgr [H,W,3]`、`mask [H,W]` | 通常 `uint8`，BGR 为 `0..255`，mask 非 0 即选区 | 外部调用者持有的数据；项目不在这里改原图 |
| 颜色/二值化 | `rgb [H,W,3]`、`binary_mask [H,W]` | `uint8` | 将 OpenCV 的 BGR 边界转成模型约定的 RGB；把任意灰度 mask 规整成 0/1 |
| padding | `padded_image [Hp,Wp,3]`、`padded_mask [Hp,Wp]` | 仍为 `uint8` | 仅创建新数组；记录原 `height,width` 以便输出裁回 |
| Torch 输入 | `[1,3,Hp,Wp]` 与 `[1,1,Hp,Wp]` | `float32`；图像为 `0..1`，mask 为 `0.0/1.0` | `.to(self.device)` 创建/迁移设备张量；必须与模型参数在同一设备 |
| 前向输出 | 通常 `[1,3,Hp,Wp]` | Tensor，通常是 `float32`、RGB 值域约 `0..1` | 只在 `inference_mode()` 内计算，不建立反向传播图，不更新权重 |

真实后处理同样是模型协议的一部分。项目对 `result[0]` 去掉 batch 维，用 `permute(1, 2, 0)` 把 CHW 变回 HWC，移至 CPU、裁回 `[:height, :width]`、乘以 255 并转为 `uint8`，最后 RGB→BGR。接着它执行两项明确的业务保护：`_finish_ink_on_flat_background()` 只在“平坦底色、原字明显更暗”等保守条件下清理残笔；更关键的是 `result_bgr[binary_mask == 0] = image_bgr[..., :3][binary_mask == 0]`，强制恢复 mask 外的原像素。网络可以生成整幅输出，但产品不允许它在选区外留下细微色偏。

### 输出后处理和业务保护

```python
result_rgb = repaired[0].permute(1, 2, 0).cpu().numpy()
result_rgb = np.clip(result_rgb[:height, :width] * 255, 0, 255).astype(np.uint8)
result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)

# 业务不变量：mask 外不允许被生成模型修改。
outside = binary_mask == 0
result_bgr[outside] = image_bgr[:, :, :3][outside]
cv2.imwrite('repaired.png', result_bgr)
```

最后三行不是“可有可无的美化”：生成模型可能对整张图产生轻微变化，业务代码必须把不允许变化的区域恢复为原图。这样，神经网络负责 mask 内的概率性补全，确定性代码负责产品边界。

## 案例四：Real-ESRGAN 的 `state_dict` 推理

Real-ESRGAN 与 LaMa 的区别在于：项目保存的是 checkpoint，而不是完整 TorchScript 模块。因此加载顺序是：**构造正确网络 → 在 CPU 读取 checkpoint → 取出参数字典 → 严格加载 → 迁移设备 → 推理**。

**checkpoint（检查点）** 是“某个训练或发布时刻保存下来的状态包”的泛称，不是单一的文件格式。一个用于断点续训的完整 checkpoint 可能包括模型参数、优化器状态、epoch、学习率调度器、随机数状态和配置；而本例为了部署推理，只从 checkpoint 中取 `params_ema` 或 `params` 这一组模型参数。`state_dict` 是“名称到 Tensor”的状态映射，常是 checkpoint 的全部或其中一个字段；二者不能机械地视为同义词。

Real-ESRGAN 是**单图像超分辨率**模型：输入一张低分辨率 RGB 图，输出一张更大的 RGB 图；它不接收修复 mask，也不保证找回真实历史细节。项目的 Anime 权重配 `RRDBNet`（Residual-in-Residual Dense Block 网络：密集连接复用中间特征，残差连接让深层特征变换更稳定），General 权重配 `SRVGGNetCompact`（紧凑的 VGG 风格卷积/激活网络）。这两种网络结构和权重必须成对：前者不能因为文件也叫 `.pth` 就装进后者。

例如 `RealESRGAN_x4plus_anime_6B` 中，`x4` 表示网络原生生成 4 倍宽高的输出，`6B` 对应本项目 Anime 构造器使用的 6 个 RRDB；它不表示用户可将同一权重任意改成 6 倍。若调用者请求 2 倍，项目仍先由 x4 网络生成原生结果，再在后处理阶段缩放到 2 倍。

```python
checkpoint = torch.load('RealESRGAN_x4plus_anime_6B.pth', map_location='cpu', weights_only=True)
state = checkpoint.get('params_ema', checkpoint.get('params', checkpoint))

model = build_rrdb_net(num_block=6)       # 必须与权重对应
model.load_state_dict(state, strict=True)
model = model.to(device).eval()

rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
x = torch.from_numpy(rgb.transpose(2, 0, 1)).unsqueeze(0).to(device)

with torch.inference_mode():
    if device.type == 'cuda':
        model = model.half()
        x = x.half()
    output = model(x)

result = output[0].float().cpu().clamp(0, 1).numpy().transpose(1, 2, 0)
result_bgr = cv2.cvtColor((result * 255).round().astype(np.uint8), cv2.COLOR_RGB2BGR)
```

示例中的 `build_rrdb_net()` 代表项目里的 `_build_rrdb_net()`；必须使用与 checkpoint 一致的通道数、块数和放大倍数。`half()` 只在 CUDA 路径使用，CPU 上保持 `float32` 更稳妥。输出是原生 4×图像，若用户请求 2×，项目是在模型输出之后再做 Lanczos 缩放，而不是假装网络本身产生了 2×权重。

### Real-ESRGAN：模型结构不是权重文件名的附属品

当前项目的 `RealESRGANEnhancer._asset_and_model()` 体现了 `state_dict` 推理最关键的一点：权重没有自描述到足以替你创建任意网络。Anime 模式把 `RealESRGAN_x4plus_anime_6B.pth` 配对给 `_build_rrdb_net(num_block=6)`；General 模式把 `realesr-general-x4v3.pth` 配对给 `_build_srvgg_net()`。两个 `.pth` 都不是“只要 `torch.load` 成功就能调用”的通用模型。

`_load_model(model, path, device)` 的实际核心是：

```python
checkpoint = torch.load(str(path), map_location="cpu", weights_only=True)
state = checkpoint.get("params_ema", checkpoint.get("params", checkpoint))
model.load_state_dict(state, strict=True)
loaded = model.to(device).eval()
if device == "cuda":
    loaded = loaded.half()
```

这里 `params_ema` 是一些训练流程保存的指数滑动平均参数，项目优先使用它；若不存在才退到 `params` 或 checkpoint 本身。`weights_only=True` 限定加载预期的权重数据，`strict=True` 则要求每一个参数键和 shape 都与刚构造的网络匹配。前者缩小不必要的反序列化风险，后者把“下载了 Anime 权重却构造了 General 网络”等错误提前暴露，而不是让结果悄悄变差。

模型调用发生在 `_infer()`：它把已经是 RGB、`float32 [H,W,3]`、值域 `[0,1]` 的 NumPy 数组转成 `[1,3,H,W]` Tensor；CUDA 路径再转成 `float16`。`torch.inference_mode()` 中的 `self.model(tensor)` 返回 `[1,3,4H,4W]`。这组输入/输出的 4 倍关系由网络决定，不由 `enhance(scale=2)` 的 `scale` 参数决定。

大图会进入 `_infer_tiled()`。假设原图为 `H×W`、`tile_size=512`、`tile_pad=10`：代码先为每个核心 tile 向四周多取最多 10 个输入像素，再把该扩展 tile 的 4×输出裁回核心区域，写入一个预先分配的 `[1,3,4H,4W]` 输出 Tensor。`tile_pad` 给卷积的感受野留下邻域，避免独立分块在边缘产生接缝；它并不是把不同 tile 的结果平均融合。最后 `enhance()` 在同一 `inference_mode()` 块中依次 `squeeze(0) → float() → cpu() → clamp(0,1) → numpy() → transpose(1,2,0)`，转回 BGR `uint8`。若用户请求 1×、1.5×、2×或 3×，才使用 Lanczos 把原生 4×结果缩到目标尺寸。

这也解释了 `MediaEnhancer` 与模型类的分工：`MediaEnhancer._run_video()` 在循环外只创建一次 `enhancer`，循环内每帧调用 `enhancer.enhance(frame, self.scale)`，负责进度、取消检查、输出尺寸为偶数以及音频回封装；它不应每帧重新读取 checkpoint，更不应把视频逻辑塞进 `RealESRGANEnhancer`。

## 四种模型调用方式的对照

| 模型 | 输入 | 输出 | 加载方式 | 推理后处理 |
| ---- | ---- | ---- | -------- | ---------- |
| ResNet 分类 | `[1,3,H,W]` RGB | `[1,C]` logits | torchvision weights | softmax、top-k、类别名 |
| TinyClassifier | `[B,2]` 特征 | `[B,1]` logit | `state_dict` | sigmoid、阈值 |
| LaMa | 图像 `[1,3,H,W]` + mask `[1,1,H,W]` | 图像张量 | TorchScript | CHW→HWC、RGB→BGR、恢复 mask 外像素 |
| Real-ESRGAN | `[1,3,H,W]` RGB | `[1,3,4H,4W]` | 网络 + checkpoint | clamp、缩放、RGB→BGR、tile 拼接 |

表格中最值得记住的是：**模型类别不同，输出语义不同；但推理边界的检查方法相同。** 先确认输入契约，再调用模型，最后按输出语义解释和保存。

## 从最小例子回到 CleanCanvas

回到仓库代码时，可以这样对应：

- `ContentRepairProcessor._repair()` 对应“先建 mask；空 mask 直接返回原帧；否则调用统一 `inpaint()`”；
- `TorchScriptLaMaEngine.__init__()` 对应“校验/取得 TorchScript 权重 + `torch.jit.load(...).to(device).eval()`”；
- `TorchScriptLaMaEngine.inpaint()` 对应“OpenCV BGR → RGB/CHW/float32 → 8 的倍数 padding → 两个输入前向 → 裁回、恢复 mask 外像素”；
- `MangaEngine.inpaint()` 说明一个项目可能串联两个模型，先得到线稿先验，再将归一化灰度、线稿、mask、噪声和全 1 条件交给修复模型；
- `RealESRGANEnhancer._load_model()` 对应“由模式构造匹配网络 + checkpoint 的 `params_ema/params` + `strict=True`”；
- `_infer_tiled()` 对应“输入分块、带上下文 pad 推理、按 4 倍坐标裁剪和写回”；
- `MediaEnhancer.run()` 对应“增强器只创建一次，图片或逐帧视频复用它，媒体层处理输出与音频”。

这就是“深入实际模型”的正确入口：不是先记住整个项目的类层次，而是先用小例子掌握推理协议，再逐个验证真实模型在哪些地方增加了输入、状态和后处理复杂度。

如果你对 `HWC`、`CHW`、mask、NumPy 切片或 CPU/GPU Tensor 还不熟，请先阅读[图像张量基础：NumPy 与 PyTorch 的数组、通道、mask 和内存](04b-image-arrays-numpy-pytorch.md)，再继续看 LaMa 的预处理代码。

## 把模型推理真正跑在 CleanCanvas 上

前面的最小代码帮助你理解模型边界；接下来可以在 [CleanCanvas Studio 仓库](https://github.com/Yukino-insect/clean-canvas-studio) 实际运行同一条推理链。以下命令以 Windows PowerShell、CPython 3.12 和 CPU 为例；GPU wheel、PaddleOCR 与模型缓存的具体要求应以仓库当前 README 为准。

```powershell
git clone https://github.com/Yukino-insect/clean-canvas-studio.git
Set-Location clean-canvas-studio

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
.\scripts\install-runtime.ps1 -TorchBackend cpu -Python .\.venv\Scripts\python.exe
```

先不依赖 OCR，也不依赖 GUI。准备一张 `input.png`，选择一个明确包含水印的区域，执行：

```powershell
python backend/main.py `
  -i .\input.png `
  -o .\output.png `
  --mode anime_lama --device cpu `
  --manual-area 120 620 560 710
```

当前 CLI 没有 `--no-ocr` 参数；上述命令不启用 `--dynamic-ocr`，并显式提供 `--manual-area`，所以会走静态最终 mask 路径。四个数字的顺序必须是 `XMIN XMAX YMIN YMAX`，因此例子表示横向 `[120,620)`、纵向 `[560,710)` 的矩形，而不是常见但错误的“先 y 后 x”顺序。项目将 OpenCV BGR `uint8` 图像和该 mask 传给 `TorchScriptLaMaEngine.inpaint()`。首次选择 AI 模式时，仓库会按自己的模型缓存策略校验或下载所需权重；之后才进入本篇案例三讲解的 TorchScript 前向推理。命令完成后应检查三件事，而不是只看“没有报错”：

1. `output.png` 的尺寸应与输入相同；
2. mask 外像素应保持原图不变；
3. mask 内是否既清除了水印，也没有重建明显错误的线条、文字或人物细节。

要验证 Real-ESRGAN，应在 GUI 的“画质增强”页面选择 Anime 或 General 模式，或跟随仓库当前 README 的增强命令。它的输出原生为 4×，请求 1×、1.5×、2×或 3×时会先进行 4×网络推理，再缩放到目标大小；因此“输出不是精确 4×”不表示模型没有运行。

这个步骤的价值在于把抽象知识落到可观察现象：断网会停在权重获取，颜色异常通常出在 BGR/RGB 边界，设备错误出在 `.to(device)`，显存不足通常和输入尺寸/tile 有关，而不是被一个笼统的“AI 模型坏了”掩盖。

## 小结

- PyTorch 推理是一条包含加载、预处理、前向计算、输出解释和后处理的完整链路。
- 分类模型、图像修复模型和超分模型的输入输出语义不同，不能只把它们都简化成 `model(x)`。
- TorchScript 可以直接恢复可执行模块；`state_dict` 必须先构造相同网络结构。
- CleanCanvas 的 LaMa 和 Real-ESRGAN 分别代表双输入 TorchScript 推理与 checkpoint 网络推理。
- 真正可迁移的能力是：看到一个新模型时，能写出它的输入契约、输出语义和后处理边界。
