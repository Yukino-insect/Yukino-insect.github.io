+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '项目实战总览：从机器学习到 CleanCanvas Studio 的预训练模型推理'
+++

前半部分我们训练过一个很小的分类器。现在换一个更接近真实工作的场景：用户上传一张图片，框选一段文字，程序调用已经训练好的模型完成修复，再把结果交给界面或视频编码器。读这类代码时，最容易犯的错误是直接钻进某个网络类，结果看见几十个卷积层，却不知道它在整条链路中解决什么问题。

本章先建立通用地图，再把地图映射到 [CleanCanvas Studio GitHub 仓库](https://github.com/Yukino-insect/clean-canvas-studio)。仓库地址比作者电脑上的目录更重要：读者可以克隆、查看提交和对照版本；本文只把仓库中的接口作为案例，不要求读者拥有相同的本地路径。

## 先把三个容易混淆的词分开

**机器学习**是一个问题范式：程序通过数据和目标改进预测，而不是把每条规则都写死。**深度学习**是机器学习的一类，使用许多层可学习变换来表示复杂函数。**神经网络**是深度学习中最常见的模型家族，由线性层、卷积、注意力、归一化、激活函数和残差连接等模块组合而成。

因此它们不是三个并列框架：神经网络通常属于深度学习，深度学习属于机器学习；但机器学习还包括决策树、线性回归等非神经网络方法。CleanCanvas Studio 中的 LaMa 和 Real-ESRGAN 是深度学习模型，OpenCV Telea 是传统图像算法，PaddleOCR 使用的是 PaddlePaddle。一个项目可以同时包含三类技术。

## 训练、加载和推理是三段不同的工作

训练阶段有数据和标签，执行“前向计算 → loss → `backward()` → `optimizer.step()`”，参数会改变。发布阶段把训练好的参数保存成 TorchScript 或 `state_dict`。推理阶段只有新输入，执行前向函数并返回结果，参数不改变：

```text
训练：样本 + 标签 → 预测 → loss → 梯度 → 更新参数
发布：网络结构 + 参数 → 模型文件
推理：图片/掩膜 → 预处理 → model(x) → 后处理 → 图片
```

推理仍然使用前面学过的 `Tensor`、`nn.Module` 和设备，但不计算损失，也不需要反向传播。`model.eval()` 负责 Dropout、BatchNorm 等层的行为；`torch.inference_mode()` 负责不建立 autograd 图。它们解决不同问题，不能互相替代。

## 先用一个与项目无关的最小预训练模型

下面的例子用公开的 torchvision 权重说明“下载—加载—预处理—推理”闭环。它不需要理解 CleanCanvas 的任何代码；先运行它，读者就能知道预训练模型的本质是一个固定参数的函数。

```python
import torch
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
weights = ResNet18_Weights.DEFAULT
model = resnet18(weights=weights).to(device).eval()
preprocess = weights.transforms()

image = Image.open('cat.jpg').convert('RGB')
batch = preprocess(image).unsqueeze(0).to(device)  # [1, 3, H, W]

with torch.inference_mode():
    logits = model(batch)                       # [1, 1000]
    probability = logits.softmax(dim=1)
    class_id = probability.argmax(dim=1).item()

print(weights.meta['categories'][class_id], probability[0, class_id].item())
```

`weights` 包含网络参数和与训练一致的预处理规则；`preprocess` 将 PIL 的 HWC 图像变为模型约定的 NCHW 浮点张量；`unsqueeze(0)` 增加 batch 维；`eval()` 和 `inference_mode()` 分别固定层行为、关闭梯度记录。这里没有 `loss`，因为用户没有提供“这张图片正确类别”的标签。换用一个修复模型时，类别输出会变成图像输出，但这条边界仍然成立。

## CleanCanvas 的实际数据流

仓库中的业务层、模型层和媒体层可以按下图阅读：

```text
图片/视频帧（OpenCV BGR uint8）
        ↓
masking.py：矩形、涂鸦、OCR 多边形 → [H, W] 二值 mask
        ↓
main.py：任务调度与惰性加载
        ↓
create_inpaint_engine(mode, device, model_dir)
  ├─ opencv       → cv2.inpaint（传统算法）
  ├─ lama/anime   → TorchScriptLaMaEngine
  └─ manga        → MangaEngine
        ↓
RGB/CHW/float32 张量 → 预训练网络前向推理 → BGR uint8
        ↓
恢复 mask 外原像素 → 返回界面或视频编码器
```

`main.py` 不应该知道 LaMa 的 padding 规则，`realesrgan.py` 也不应该负责视频音频回封装。这种分层让模型可以替换，让同一个引擎既服务图片也服务视频。

| 组件 | 学习重点 | 与基础课程的对应 |
| ---- | -------- | ---------------- |
| `masking.py` | 如何把用户意图变成 0/1 区域 | 标签/输入契约、数组 shape |
| `backend/main.py` | 任务、缓存、没有 mask 时的短路 | 函数调用与副作用 |
| `backend/inpaint/engine.py` | TorchScript、padding、设备、后处理 | `nn.Module` 前向、`eval()`、推理模式 |
| `backend/enhance/realesrgan.py` | RRDB/SRVGG、超分和 tile | `Conv2d`、激活、残差、NCHW |
| `media_enhancer.py` | 逐帧调度与输出 | 模型之外的工程边界 |

## 为什么模型要惰性加载

第一次真正需要修复时才创建引擎，之后复用同一实例，这叫惰性加载。权重下载、反序列化和显存分配都很昂贵；用户只使用 OpenCV 或只打开应用时，不应承担这些成本。视频逐帧处理尤其不能每帧重新加载模型，否则时间和显存都会被浪费。

同时，`auto` 设备策略应当完成真实初始化，而不是只检查 `torch.cuda.is_available()`：CUDA 驱动、算子或显存仍可能在加载/首次推理时失败。显式 `cuda` 失败应报错，`auto` 才适合尝试 CUDA 后从干净对象回退 CPU。

## 阅读顺序与迁移能力

建议按以下顺序继续：

1. [PyTorch 预训练模型推理详解](04a-pretrained-model-inference-tutorial.md)：先用分类器、`state_dict`、TorchScript 和真实图像模型完整走一遍推理。
2. [图像张量基础](04b-image-arrays-numpy-pytorch.md)：补齐 NumPy/PyTorch 数组、颜色、通道、mask 和内存知识。
3. [图像如何变成张量](05-image-tensor-preprocessing-and-inpainting.md)：核对 BGR/RGB、HWC/CHW、值域和 mask，并解释矩形 mask 去水印的原因。
4. [加载权重与推理模式](06-model-loading-device-and-inference-mode.md)：对照 TorchScript 与 `state_dict`，理解训练模式和推理模式。
5. [Real-ESRGAN 与分块推理](07-realesrgan-network-and-tiled-inference.md)：把卷积、残差、上采样与显存问题联系起来。
6. [项目排错与扩展](08-project-interview-and-debugging.md)：用输入契约、数据流和不变量定位错误，而不是盲目添加 `.squeeze()`。

读完这组文章，应该能把同样的方法迁移到任意视觉项目：先找输入输出，再找模型格式和设备，最后检查后处理与业务不变量。项目名称会变，`shape`、`dtype`、`device` 和“参数是否改变”这些问题不会变。
