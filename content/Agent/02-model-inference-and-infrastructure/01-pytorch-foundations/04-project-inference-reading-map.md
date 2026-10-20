+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '项目实战总览：从机器学习到 CleanCanvas Studio 的预训练模型推理'
+++

前半部分我们训练过一个很小的分类器。现在换一个更接近真实工作的场景：用户上传一张图片，框选一段文字，程序调用已经训练好的模型完成修复，再把结果交给界面或视频编码器。读这类代码时，最容易犯的错误是直接钻进某个网络类，结果看见几十个卷积层，却不知道它在整条链路中解决什么问题。

本节涉及到的 github 仓库为 [CleanCanvas Studio GitHub](https://github.com/Yukino-insect/clean-canvas-studio)。

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

## CleanCanvas 的实际数据流：先找编排器，再找模型

不要从 `RRDBNet` 或 LaMa 权重文件开始读。真实项目的第一层并不是网络，而是两个“把输入交给模型”的编排器：内容修复使用 `backend/main.py` 中的 `ContentRepairProcessor`，画质增强使用 `backend/enhance/media_enhancer.py` 中的 `MediaEnhancer`。前者统一编排图片和视频的手工框选、涂鸦、颜色筛选及 OCR 文字区域修复。

内容修复的一次实际调用链如下。箭头两侧的函数名可以直接作为读源码时的搜索关键词：

```text
GUI 任务快照，或 backend/main.py 的 CLI 参数
        ↓
ContentRepairProcessor.run()
  ├─ 图片：repair_image()
  └─ 视频：repair_video()，逐帧读取/编码
        ↓
_repair(frame, polygons=None)
  ├─ _mask() → build_mask(...) / polygon_mask(...)
  ├─ mask 全为 0：直接 return 原 frame，不创建模型
  └─ _engine().inpaint(frame, mask)
        ↓
create_inpaint_engine(mode, device, model_dir)
  ├─ opencv     → OpenCVEngine → cv2.inpaint
  ├─ lama/anime → TorchScriptLaMaEngine → torch.jit.load(...)
  └─ manga      → MangaEngine → 两个 torch.jit.load(...) 模型
        ↓
引擎返回 BGR uint8 [H, W, 3] → UI 预览、图片编码或视频写入/音频回封装
```

这里的 `frame` 是 OpenCV 读取的 `numpy.ndarray`，通常为 BGR、`uint8`、形状 `[H, W, 3]`；`mask` 是 `[H, W]` 的 `uint8` 数组，0 表示不修复，非 0 表示可修改。`_repair()` 的返回值仍是与输入同尺寸、同颜色布局的 BGR 图像。这个稳定的业务接口很重要：`ContentRepairProcessor` 不需要知道 LaMa 的 Tensor 是 RGB/CHW，也不需要为 Manga 的五个模型输入写分支。

### `Protocol`、工厂和缓存：项目如何抽象“可修复”

`backend/inpaint/engine.py` 声明了下面这个类型协议：

```python
class InpaintEngine(Protocol):
    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
```

它不是一个装着共享代码的“模型父类”，而是 Python 类型提示里的**结构性接口**：只要对象有同样签名的 `inpaint()`，就可被 `ContentRepairProcessor` 当作修复引擎使用。`OpenCVEngine`、`TorchScriptLaMaEngine`、`MangaEngine` 不必继承同一个运行时基类。这正是 Python 的鸭子类型在工程中的克制用法：调用方只依赖输入、返回值和副作用的契约，不依赖具体算法。

真正决定实现的是工厂函数 `create_inpaint_engine(mode, *, device="auto", model_dir=None)`。它把字符串模式转换为 `InpaintMode` 枚举，返回上述三个实现之一；`opencv` 路径完全不导入 PyTorch。`ContentRepairProcessor._engine()` 又把这个结果保存在 `self._inpaint_engine`：第一个有非空 mask 的图片/视频帧才会调用工厂，后续帧复用同一个对象。因此“惰性加载”包含两个条件：任务要真的进入修复，且 mask 不能为空。

`ModelStore.ensure(asset)` 是权重取得的另一层边界。它先检查模型缓存和 MD5，再下载到临时文件，校验通过后才移动到正式位置；断网或下载到一半不会被当成可加载权重。`model_dir` 参数优先于环境变量 `CLEAN_CANVAS_MODEL_DIR`，否则落到项目默认模型目录。模型缓存解决的是文件和完整性问题；`_inpaint_engine`/`RealESRGANEnhancer` 的实例缓存解决的是反序列化和显存重复占用问题，二者不可混为一谈。

### 修复、增强与媒体层各自应知道什么

| 组件 | 真实职责与关键入口 | 不应承担的职责 | 与基础课程的对应 |
| ---- | ---------------- | -------------- | ---------------- |
| `backend/masking.py` | `MaskPlan` 冻结矩形、涂鸦、颜色筛选；`build_mask()` 产出 `[H,W]` `uint8` mask | 不加载权重，不做神经网络前向 | 输入契约、NumPy shape、可序列化状态 |
| `backend/main.py` | `ContentRepairProcessor._repair()` 短路空 mask，调用统一 `inpaint()`；图片/视频调度 | 不知道 LaMa 的 padding、Tensor 值域或 checkpoint 键 | 函数调用、缓存、副作用与边界 |
| `backend/inpaint/engine.py` | 工厂、权重缓存、设备回退、OpenCV/LaMa/Manga 的模型适配 | 不负责 GUI 交互、视频容器与音频 | `nn.Module` 前向、`eval()`、推理模式 |
| `backend/enhance/realesrgan.py` | 构造匹配网络、加载 checkpoint、tile 推理、BGR↔RGB/Tensor 转换 | 不负责逐帧读写、取消按钮或音频 | `Conv2d`、激活、残差、NCHW、`state_dict` |
| `backend/enhance/media_enhancer.py` | `MediaEnhancer.run()` 创建增强器，处理图片或逐帧视频，写文件/回封装音频 | 不定义 Real-ESRGAN 网络或解释权重键 | 模型之外的任务生命周期与 I/O |

### 画质增强不是修复链路的一个分支

容易被名称误导，不过“去除文字”和“画质增强”在当前仓库中是两条独立任务链。`MediaEnhancer.run()` 才是增强的入口；它通过 `_enhancer()` 调用 `create_enhancer(...)`，得到 `RealESRGANEnhancer`。对图片，`_run_image()` 读取一次 BGR 图并调用 `enhancer.enhance(image, scale)`；对视频，`_run_video()` 每帧调用同一实例的 `enhance()`，用 `FFmpegVideoWriter` 写临时视频，最后 `_merge_audio()` 尝试流复制原始音频。

这意味着 `RealESRGANEnhancer` 的职责严格是：

```text
BGR uint8 [H,W,3]
  → RGB float32 [H,W,3]，值域 [0,1]
  → NCHW Tensor [1,3,H,W]，CPU 或 CUDA
  → 原生 4× NCHW 输出
  → RGB/BGR uint8，再按请求倍率缩放
```

它不认识视频帧号、输出路径或音频。反过来，`MediaEnhancer` 也不该偷偷改 Tensor 的 dtype 或网络结构。如此划分以后，即使把 Real-ESRGAN 换成另一种超分模型，媒体读写层也能保持不变。

## 为什么模型要惰性加载

第一次真正需要修复时才创建引擎，之后复用同一实例，这叫惰性加载。权重下载、反序列化和显存分配都很昂贵；用户只使用 OpenCV、只打开应用，或当前帧 mask 为空时，不应承担这些成本。视频逐帧处理尤其不能每帧重新加载模型，否则时间和显存都会被浪费。

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
