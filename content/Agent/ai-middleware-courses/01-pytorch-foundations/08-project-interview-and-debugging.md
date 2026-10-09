+++
date = '2026-10-09T20:00:00+08:00'
draft = false
title = '项目实战：PyTorch 与深度学习面试问答、排错清单与学习路线'
+++

学完本课程后，最有价值的不是能背出 `torch.Tensor` 的定义，而是能面对一段项目代码，说明它的输入输出、模型格式、设备策略、推理状态和失败边界。CleanCanvas Studio 提供了一个完整的图像推理案例：图像修复使用 LaMa、Anime-LaMa、Manga，画质增强使用 Real-ESRGAN；但模型选择、mask、视频调度、模型缓存和输出保护同样是深度学习工程的一部分。

本篇将知识收束成可以练习的面试回答和现场排障顺序。请不要逐字背答案；应先用自己的话回答，再回到对应源码验证。面试官追问时，只有理解因果关系的人能自然往下说。

## 一分钟项目介绍模板

> CleanCanvas Studio 是本地图片/视频文字去除与画质增强工具。它将传统 OpenCV 修复与预训练 PyTorch 模型分层：业务层先从矩形、涂鸦、颜色筛选或 OCR 结果生成与原图同尺寸的二值 mask；LaMa/Anime-LaMa/Manga 在整图上下文和 mask 条件下做推理；Real-ESRGAN 对完整图像或视频帧做 4×超分。模型按需加载，`auto` 真实尝试 CUDA 后可回退 CPU，推理使用 `eval()` 与 `inference_mode()`，并在后处理强制恢复 mask 外的原图像素，避免生成模型越界修改。

这段话涵盖了任务、数据流、模型、资源管理和质量约束。不要声称“模型能还原被遮挡的真实像素”或“所有 AI 都由 PyTorch 实现”：LaMa 和 Real-ESRGAN 是推测性生成/增强，OCR 则运行在 PaddlePaddle。

## 高频基础问答

### 1. 什么是 tensor？项目中有哪些形状？

Tensor 是能位于 CPU/GPU、带 dtype 和可选梯度信息的多维数值容器。图像在 OpenCV 中是 NumPy BGR `uint8 [H, W, 3]`；送入 LaMa 前变成 RGB `float32 [1, 3, H, W]`；mask 变为 `[1, 1, H, W]`。第一维是 batch，第二维是通道。Real-ESRGAN 的 4×网络输入 `[1, 3, H, W]`，输出 `[1, 3, 4H, 4W]`。

### 2. 训练与推理差异是什么？

训练有标签、损失、反向传播和优化器更新；推理使用已经固定的权重，只做前向计算。本项目是推理工程，因此没有 `loss.backward()` 或 `optimizer.step()`；使用 `.eval()` 固定推理行为，使用 `inference_mode()` 不建立梯度图以减少开销。

### 3. 为什么不能只写 `model(image)`？

因为模型有严格输入契约。必须匹配颜色顺序（BGR/RGB）、shape（NCHW）、dtype（通常 `float32` 或 CUDA 上 `float16`）、值域（例如 0–1 或 -1–1）和设备。缺少任何转换都可能报错，或更糟地，静默地产生低质量输出。

### 4. `eval()` 和 `inference_mode()` 能互相替代吗？

不能。`eval()` 改变 Dropout、BatchNorm 等模块的行为；`inference_mode()` 关闭 autograd 记录。项目二者都用：加载后 `.eval()`，前向调用时进入 `torch.inference_mode()`。

### 5. 什么是 TorchScript？为何本项目使用它？

TorchScript 是可序列化运行的 PyTorch 图/模块格式，使用 `torch.jit.load()` 可加载执行，无需在运行项目中重写原训练时所有 Python 模型类。LaMa/Manga 使用 TorchScript；Real-ESRGAN 权重是 state dict，所以项目必须先构建 RRDBNet/SRVGGNetCompact 再 `load_state_dict()`。

## 高频工程问答

### 6. 模型放到 GPU 后，为什么输入也要放 GPU？

一次张量运算要求参与者位于兼容设备。CUDA 权重和 CPU 输入不能直接卷积。项目将模型 `model.to(device)`，并在调用前让 `image_tensor`、`mask_tensor` 都 `.to(self.device)`；后处理转 NumPy 前再 `.cpu()`。

### 7. 为什么 `auto` 不只检查 `torch.cuda.is_available()`？

它只是初步可见性检查。模型加载、TorchScript 算子、显存分配和首次真实推理仍可能失败。项目的 `auto` 按 CUDA、CPU 顺序真实初始化，失败后从干净模型对象回退；显式 `cuda` 则不静默回退，便于发现配置问题。

### 8. 为什么加载权重先 `map_location='cpu'`？

避免 checkpoint 绑定保存时的 GPU，并控制加载阶段显存。文件先在 CPU 反序列化，网络结构匹配后再迁移到最终设备；这也让同一权重可在 CPU-only 环境运行。

### 9. FP16 有什么收益和风险？

半精度将每个浮点数从约 4 字节降为 2 字节，通常可降低 GPU 显存并提高受支持 GPU 的吞吐。风险是精度和可表示范围下降、CPU 支持通常不理想、模型与输入 dtype 必须一致。项目只在 CUDA 上 `half()`，CPU 保持 `float32`。

### 10. 大图为什么要分块，为什么还要 overlap？

4×超分后像素面积是原图 16 倍，中间特征耗显存更多。分块降低单次峰值显存；overlap 提供块边缘附近的上下文，推理后裁掉重叠区域再拼接，避免卷积边缘缺上下文产生接缝。

## 从现象反推问题的排错表

| 现象 | 优先检查 | 原因与处理 |
| ---- | -------- | ---------- |
| `Expected all tensors to be on the same device` | 模型、图像张量、mask、输出缓冲区的 `.device` | 统一迁移到 CPU 或 CUDA；转 NumPy 前 `.cpu()` |
| `expected scalar type Half but found Float` | 模型和输入的 `.dtype` | CUDA FP16 路径中，模型、输入和输出缓冲区统一 half；CPU 默认 float32 |
| 模型能运行但颜色明显怪异 | BGR/RGB 与归一化 | 检查 `cv2.cvtColor`、`/255.0`、输出转回 BGR 的顺序 |
| shape 报错或结果错位 | `[N,C,H,W]`、mask 通道、padding、裁回尺寸 | 在每个边界打印 `.shape`；不要只看元素总数 |
| `CUDA out of memory` | 输入大小、tile、并发模型、dtype | 降低 tile、缩小输入、释放其他 GPU 任务或切 CPU；不要盲目重装 torch |
| 结果出现 tile 接缝 | `tile_pad`、输出坐标裁剪 | 确认每块有重叠输入，写回时只取中心有效区；检查坐标是否乘 4 |
| mask 外内容也变了 | 最后像素保护逻辑 | 将 `mask == 0` 的输出强制覆盖为原图；这应有自动化测试 |
| GPU 可见却加载失败 | 完整加载日志而非只看 `is_available` | 区分驱动/wheel、权重、显存、TorchScript 算子和设备迁移问题 |

排错时建议打印最少但关键的信息：`shape`、`dtype`、`device`、值域的 `min/max`，以及模型实际选择的设备。切勿为了“让异常消失”随手加 `.squeeze()`、`.half()` 或转置；先写清楚每一维的含义，再做转换。

## 你应该能亲自完成的阅读练习

不需要下载大模型，也可以完成以下练习：

1. 打开 `backend/main.py`，解释 `_repair()` 在没有任何 mask 时为何不初始化模型。
2. 在 `engine.py` 找出 LaMa 图像和 mask 具体在哪一步变成 `[1, 3, H, W]`、`[1, 1, H, W]`。
3. 解释 `torch.jit.load(..., map_location='cpu').to(device).eval()` 四段分别解决什么问题。
4. 在 `realesrgan.py` 找出用户选择 `2×` 时为何仍产生 4×网络输出。
5. 画出 `_infer_tiled()` 的一个 tile：输入边界、重叠边界、4×输出坐标和裁剪坐标分别是什么。
6. 找出项目在哪里区分 OpenCV、PaddleOCR 与 PyTorch；说出它们各自负责的任务。

完成后尝试脱离源码口述，而非把函数名串起来。能用变量与形状讲清数据如何流动，才算真正读懂。

## 继续学习的方向

本课程已经够你开始维护这部分代码，但不意味着深度学习知识到此为止。下一步按实际目标选择：

- 想改网络：学习 `nn.Module`、卷积感受野、归一化、残差网络、上采样与图像损失；
- 想训练/微调：学习数据集、数据增强、损失函数、优化器、验证集、指标与实验复现；
- 想优化推理：学习 profiling、batch、显存生命周期、混合精度、ONNX/TensorRT 与模型量化；
- 想做视频质量：学习时序一致性、光流、视频超分与回归测试集，而不是只逐帧处理；
- 想面试算法岗：补齐线性代数、概率统计、反向传播推导、CNN/Transformer 原理及论文复现。

你不需要等“全部学完”才开始。以当前项目为锚点，每学一个概念就在对应代码里找到它的输入、输出和取舍；这种往返比孤立背诵名词更能建立稳定理解。

## 小结

- 解释项目时先界定：它使用预训练模型推理，不是在线训练模型。
- 面试回答必须覆盖张量契约、模型格式、设备、推理模式、资源控制与质量边界。
- 对图像模型，BGR/RGB、NCHW、值域、dtype、device 是五项基本检查。
- 好的工程不是只让模型“跑起来”，还要能回退、能诊断、能保护非目标区域，并明确模型无法保证什么。
