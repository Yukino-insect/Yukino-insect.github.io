+++
date = '2026-10-15T21:00:00+08:00'
draft = false
title = 'PyTorch 预训练模型推理详解：从分类器到 CleanCanvas 的图像模型'
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

## 案例一：ResNet 分类推理

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

- `TorchScriptLaMaEngine.__init__()` 对应“加载 TorchScript + `.to(device).eval()`”；
- `TorchScriptLaMaEngine.inpaint()` 对应“OpenCV BGR → RGB/CHW/float32 → 两个输入前向 → 输出后处理”；
- `MangaEngine.inpaint()` 说明一个项目可能串联两个模型，先得到线稿先验，再将灰度、线稿、mask 和噪声交给修复模型；
- `RealESRGANEnhancer._load_model()` 对应“网络结构 + checkpoint + `strict=True`”；
- `_infer_tiled()` 对应“输入分块、带 overlap 推理、按 4 倍坐标裁剪和写回”；
- `enhance()` 对应“输出 clamp、CPU、NumPy、颜色转换和非 4×倍率的最终缩放”。

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
  --mode anime_lama --device cpu --no-ocr `
  --manual-area 120 560 620 710
```

`--manual-area` 的四个数创建最终 mask；项目将 OpenCV BGR `uint8` 图像和该 mask 传给 `TorchScriptLaMaEngine.inpaint()`。首次选择 AI 模式时，仓库会按自己的模型缓存策略校验或下载所需权重；之后才进入本篇案例三讲解的 TorchScript 前向推理。命令完成后应检查三件事，而不是只看“没有报错”：

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
