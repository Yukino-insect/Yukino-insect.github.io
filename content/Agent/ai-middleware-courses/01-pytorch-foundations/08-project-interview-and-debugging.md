+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '项目实战收束：用数据流和最小实验排查 PyTorch 推理问题'
+++

项目实战的目标不是背出十个面试答案，而是能把一个陌生模型还原成可验证的数据流。本章以 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 为例，先给出通用排查方法，再把它应用到图像修复和超分场景。

## 先写输入契约，再读实现

任何模型边界都可以先写成一张小表：

| 项目 | 需要明确的问题 | LaMa/Real-ESRGAN 常见值 |
| ---- | -------------- | ---------------------- |
| shape | 每一维代表什么？ | `[N,C,H,W]` |
| dtype | 整数还是浮点？精度多少？ | `float32`，CUDA 可选 `float16` |
| device | 参数和输入在哪里？ | CPU 或同一块 CUDA |
| value range | 数值范围是什么？ | `0..1` 或模型约定的 `-1..1` |
| color | 通道顺序是什么？ | OpenCV BGR，模型通常 RGB |
| state | 是否训练行为？ | `eval()` + `inference_mode()` |

如果这张表还填不出来，不要先改网络。大多数“模型很玄学”的问题其实是边界契约没有被写清楚。

## 用最小张量实验隔离问题

遇到真实图片很难复现时，先用四行 NumPy 数组验证转换：

```python
import numpy as np
import torch

bgr = np.zeros((4, 6, 3), dtype=np.uint8)
bgr[:, :, 2] = 255                    # BGR 中的红色
rgb = torch.from_numpy(bgr[:, :, ::-1].copy())
x = rgb.permute(2, 0, 1).float().div(255).unsqueeze(0)

print(x.shape, x.dtype, x.min().item(), x.max().item())
# torch.Size([1, 3, 4, 6]) torch.float32 0.0 1.0
```

这个实验不依赖任何权重，却能验证颜色、shape、dtype 和值域。若它都不正确，继续调学习率或更换 GPU 没有意义。

## 训练与推理排错不能混用

训练问题首先看：是否真的执行了 `zero_grad → forward → loss → backward → step`，loss 是否是有限标量，标签 shape/dtype 是否匹配，训练/验证是否泄漏。推理问题则看：权重是否完整、结构是否匹配、模型是否 `eval()`、输入是否同设备、输出是否正确后处理。推理阶段不应临时添加 `loss.backward()`；它没有标签，也不需要改变参数。

## CleanCanvas 的典型故障如何定位

| 现象 | 最小验证 | 常见根因 |
| ---- | -------- | -------- |
| `Expected all tensors to be on the same device` | 打印模型参数、图像、mask 的 `.device` | 只迁移了模型或只迁移了输入 |
| `Expected scalar type Half but found Float` | 打印 `.dtype` | FP16 模型与 FP32 输入混用 |
| 颜色明显偏蓝/偏红 | 构造上面的纯红实验 | BGR/RGB 转换方向错误 |
| 输出尺寸错位 | 在 padding 前后打印 `H,W`，核对 `scale` | 裁剪或 tile 坐标未乘放大倍数 |
| mask 外也改变 | 比较 `result[mask==0]` 与原图 | 缺少最终像素保护 |
| `CUDA out of memory` | 先固定一张小图，逐步降低 tile | 输入太大、tile 太大、并发模型过多 |
| 运行很慢且每帧重复下载 | 记录引擎构造次数 | 没有惰性加载后的实例缓存 |

不要为了消除 shape 报错随手加 `.squeeze()`：它可能在 batch size 为 1 时删除本应保留的维度。先写出每一维的含义，再使用 `unsqueeze`、`permute` 或 `reshape`。

## 一个可测试的业务不变量

生成模型允许 mask 内有合理差异，但产品常要求 mask 外像素完全不变。可以把它写成测试：

```python
outside = mask == 0
assert np.array_equal(result[outside], original[outside])
```

这条断言比“肉眼看起来没有改动”可靠，也把神经网络的概率性输出限制在业务允许的区域。类似的不变量还包括：输出尺寸等于输入尺寸乘 scale、视频帧数不变、模型只初始化一次。

## 把项目讲清楚的五句话

面试或代码评审时可以按固定顺序说明，而不是被问题牵着跳跃：

1. 任务是什么：LaMa 做带 mask 的图像修复，Real-ESRGAN 做超分，项目主要执行预训练模型推理。
2. 输入是什么：OpenCV BGR `uint8` 图像和单通道 mask，边界处转换为模型约定的 NCHW 浮点张量。
3. 模型如何运行：按需加载权重，CPU/GPU 真实初始化，`eval()` 固定层行为，`inference_mode()` 关闭梯度图。
4. 输出如何保证可靠：裁回原尺寸，转换回 BGR/`uint8`，恢复 mask 外原像素，必要时用 tile 控制显存。
5. 失败如何定位：按 shape、dtype、device、值域、颜色和权重格式逐项验证，并用最小实验复现。

这五句话覆盖了概念、代码和工程边界，比背“什么是 tensor”的一句定义更能迁移到别的视觉项目。

## 课程到这里应掌握什么

- 能区分机器学习、深度学习、神经网络、训练、验证和推理。
- 能把线性层、激活、卷积、注意力理解为可组合的函数，而不是神秘的固定层次。
- 能解释 loss、梯度、`backward()`、优化器、`eval()` 与 `inference_mode()` 各自负责什么。
- 能从一个公开权重开始完成下载、预处理、前向推理和后处理。
- 能沿着一个真实项目的数据流读代码，并用最小例子验证而不是凭经验猜测。

后续学习 Transformer、embedding、RAG 或重排序模型时，仍然回到同一组问题：输入契约是什么，模型组合了哪些函数，训练时谁更新参数，推理时如何保证输出可靠。
