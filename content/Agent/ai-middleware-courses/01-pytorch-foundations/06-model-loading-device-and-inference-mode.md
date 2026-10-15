+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '预训练模型如何下载和使用：权重格式、CPU/GPU 与推理模式'
+++

“下载一个 `.pt` 文件然后 `model(x)`”省略了太多前提。本章先用一个可复制的 torchvision 例子说明完整流程，再解释 CleanCanvas Studio 为什么同时使用 TorchScript 和 `state_dict`。你需要记住的不是某个文件名，而是：**结构、权重、输入契约和运行状态必须彼此匹配。**

## 一个真正可运行的下载—使用例子

安装 `torch`、`torchvision` 和 `pillow` 后，下面代码第一次运行会从 torchvision 的官方权重地址下载 ResNet-18；之后从本地缓存读取。没有 GPU 也能运行，只是速度较慢。

```python
import torch
from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
weights = ResNet18_Weights.DEFAULT
model = resnet18(weights=weights).to(device)
model.eval()

image = Image.open('cat.jpg').convert('RGB')
inputs = weights.transforms()(image).unsqueeze(0).to(device)

with torch.inference_mode():
    logits = model(inputs)
    probs = logits.softmax(dim=1)
    top_prob, top_id = probs.topk(3, dim=1)

for probability, class_id in zip(top_prob[0], top_id[0]):
    print(weights.meta['categories'][class_id], float(probability))
```

这里的“预训练模型”具体就是 `resnet18` 的网络结构加上一组已经训练好的权重张量。`weights.transforms()` 不是可有可无的便利函数：它保存了训练时的 resize、crop、归一化规则。换成随意的 `/255` 或 BGR 顺序，程序可能不报错，却已经偏离训练分布。

## `state_dict`：只有参数，没有网络结构

训练代码通常这样保存：

```python
torch.save(model.state_dict(), 'classifier.pth')
```

加载时必须先用**相同的 Python 类和构造参数**重建结构：

```python
model = MyClassifier(in_features=2, hidden=8)
state = torch.load('classifier.pth', map_location='cpu', weights_only=True)
model.load_state_dict(state, strict=True)
model.eval()
```

`state_dict` 是“参数名 → 张量”的字典，例如 `layers.0.weight`；它不告诉你层的顺序、激活函数或 `forward()` 如何组合。`strict=True` 在键不匹配时立即失败，避免把错误模型伪装成可用结果。生产环境还应记录 PyTorch 版本、模型配置、权重来源和哈希。

## TorchScript：把结构和参数一起序列化

TorchScript 模型可以由 `torch.jit.load()` 直接恢复可执行模块：

```python
model = torch.jit.load('big-lama.pt', map_location='cpu')
model = model.to(device).eval()
```

这适合发布推理模型，因为运行程序不必重新定义训练时的 Python 类。它仍然有输入契约：LaMa 可能需要图像和 mask 两个 `[N, C, H, W]` 张量，输入顺序、dtype、值域必须查模型或项目文档确认。TorchScript 并不意味着“任何张量都能喂”。

## 为什么先在 CPU 加载

先 `map_location='cpu'` 再 `.to(device)` 有三个好处：不依赖保存权重时的 GPU 编号；控制加载阶段显存峰值；让 CPU-only 机器也能读取文件。模型、输入和中间张量参与同一次算子计算时必须位于兼容设备：

```python
model = model.to(device)
inputs = inputs.to(device)
```

只迁移模型或只迁移输入都会得到 `Expected all tensors to be on the same device`。从 CUDA 张量转 NumPy 前还必须 `.cpu()`。

## `train()`、`eval()`、`no_grad()` 和 `inference_mode()`

它们分别控制两个维度，不能混为一个“推理开关”：

| API | 控制对象 | 是否改变参数 |
| ---- | -------- | -------- |
| `model.train()` | Dropout、BatchNorm 的训练行为 | 否 |
| `model.eval()` | Dropout、BatchNorm 的推理行为 | 否 |
| `torch.no_grad()` | 不记录 autograd 图 | 否 |
| `torch.inference_mode()` | 更严格的推理上下文，减少额外开销 | 否 |

训练循环应显式 `model.train()`；验证和线上推理应显式 `model.eval()`，并在前向调用外层使用 `inference_mode()`。只写 `inference_mode()`，Dropout 仍可能随机丢弃；只写 `eval()`，复杂模型仍会记录无用的梯度历史。

## CleanCanvas 的两种加载路径

在 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 中，LaMa/Manga 使用 TorchScript：

```python
model = torch.jit.load(path, map_location='cpu').to(device).eval()
```

Real-ESRGAN 使用 checkpoint：先构造 `RRDBNet` 或 `SRVGGNetCompact`，从 checkpoint 中取出 `params_ema`/`params`，再 `load_state_dict(strict=True)`。这里的顺序不能反过来，因为 `.pth` 文件没有告诉程序应当创建哪一种网络。

`params_ema` 是训练时参数的指数滑动平均，推理常比最后一步瞬时参数稳定；但是否存在该键必须以实际 checkpoint 为准，不能盲目 `checkpoint['params_ema']`。

## 下载、完整性与缓存

模型下载器应使用临时文件，成功后再原子替换目标文件；网络中断时不能留下一个名字正确但内容不完整的权重。项目的 MD5 校验主要用于发现缓存损坏，不等价于供应链签名验证。对不可信来源，优先使用项目发布页、官方 release 和 HTTPS，并记录来源与哈希。

## 小结

- 模型可运行的最小条件是：结构与权重匹配，输入满足 shape/dtype/值域，模型与输入在兼容设备，且状态切到推理行为。
- `state_dict` 只保存参数；TorchScript 通常保存可执行模块，二者加载 API 不同。
- `eval()` 控制层行为，`inference_mode()` 控制 autograd；推理代码应同时使用。
- CleanCanvas 的 LaMa 与 Real-ESRGAN 代表两种真实发布方式，读懂它们就能迁移到更多预训练视觉模型。
