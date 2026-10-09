+++
date = '2026-10-09T20:00:00+08:00'
draft = false
title = '项目实战：沿着 CleanCanvas Studio 读懂 PyTorch 图像推理调用链'
+++

前几篇讨论了“怎样训练一个小模型”。真实业务代码却经常是另一种形态：模型已经由别人训练好，应用负责把图片变成正确的张量、加载权重、调用模型，再把结果安全地还给用户。`D:\Project\python\clean-canvas-studio\backend` 正是这样的项目。它不是一个训练平台；它使用 LaMa、Anime-LaMa、Manga 和 Real-ESRGAN 完成图片修复与超分推理。

这一点在面试中值得先说清楚：**这个项目的深度学习核心是预训练模型推理（inference），不是训练（training）。** 因而读代码的重点应从“loss 如何下降”转为“输入约定是否正确、权重是否匹配、设备是否可用、输出是否被可靠地处理”。把两种工作混为一谈，便会得到一种听起来很努力、内容却并不准确的回答。

## 先画出项目中的实际职责边界

项目并非所有图像功能都使用 PyTorch。下图是从用户任务到结果的实际分层：

```text
图片或视频帧（OpenCV，BGR uint8）
        ↓
掩膜构建：矩形、涂鸦、颜色筛选或 OCR 多边形
        ↓
main.py 的 SubtitleRemover._repair()
        ↓
create_inpaint_engine(mode, device, model_dir)
        ├─ opencv  → OpenCV Telea：传统算法，不需要 PyTorch
        ├─ lama / anime_lama → TorchScriptLaMaEngine：PyTorch 推理
        └─ manga → MangaEngine：两份 TorchScript 模型推理
        ↓
完整修复结果，并强制恢复 mask 外的原图像素

另一条独立路径：
图片或视频帧 → MediaEnhancer → RealESRGANEnhancer → PyTorch 超分推理 → 输出
```

关键文件与职责如下：

| 文件 | 应先读什么 | 深度学习相关职责 |
| ---- | ---------- | ---------------- |
| `backend/main.py` | `_engine()`、`_repair()` | 懒加载引擎；为当前帧生成 mask，调用统一 `inpaint()` 接口 |
| `backend/inpaint/engine.py` | `create_inpaint_engine()` | 模式选择、模型缓存、设备回退、LaMa/Manga 推理与后处理 |
| `backend/enhance/realesrgan.py` | `RealESRGANEnhancer` | Real-ESRGAN 网络定义、权重加载、FP16、分块超分 |
| `backend/enhance/media_enhancer.py` | `MediaEnhancer.run()` | 图片/视频读取、逐帧调度、预览、编码与音频回封装 |
| `backend/masking.py` | `build_mask()` | 生成和原图同尺寸的单通道 0/255 mask；它不是 PyTorch 网络 |

`PaddleOCR` 也会参与定位文字，但它使用的是 PaddlePaddle，和 PyTorch 的设备设置、模型对象和运行时相互独立。不要因为它也使用 GPU，就在面试中说“项目的 OCR 是用 PyTorch 跑的”；这正是需要避免的技术误会。

## 从一张图片开始追踪

在 `backend/main.py` 中，修复一帧的核心流程可概括为：

```python
mask = self._mask(frame, polygons)
if not np.any(mask):
    return frame

repaired = self._engine().inpaint(frame, mask)
return repaired
```

这里的 `frame` 是 OpenCV 读取的 NumPy 数组，常见形状为 `[H, W, 3]`，颜色顺序为 BGR，数据类型是 `uint8`，每个像素值在 0 到 255。`mask` 形状为 `[H, W]`，白色/非零区域代表“允许修改的位置”。没有 mask 时直接返回原图，是很重要的短路：不用下载模型、不占显存，也不会凭空改动图像。

`self._engine()` 只有第一次被调用时才会创建引擎，然后缓存在 `self._inpaint_engine` 中。同一图片任务或视频任务的所有帧复用同一个模型实例。这样做有两个工程原因：

- 模型权重加载和 GPU 显存分配都昂贵，不能每帧重新执行；
- 模型的模式、设备与缓存目录在一次任务内保持一致，结果和日志更可解释。

这种“第一次真正需要时才创建，之后复用”的模式称为**惰性加载（lazy loading）**。它不是为了让代码看起来机灵，而是避免用户只打开应用、只使用 OpenCV 模式时，也被迫导入 PyTorch、下载权重或占用 GPU。

## 工厂函数如何屏蔽模型差异

`create_inpaint_engine()` 接受模式字符串、设备偏好和模型目录，返回一个都拥有 `inpaint(image_bgr, mask)` 方法的对象。这个设计使用了一个很朴素但很实用的原则：**调用方依赖统一行为，不依赖某个具体模型的类名。**

```text
调用方只知道：engine.inpaint(BGR 图像, mask) -> BGR 图像

OpenCVEngine          : 内部调用 cv2.inpaint
TorchScriptLaMaEngine : 内部调用 LaMa / Anime-LaMa TorchScript
MangaEngine           : 内部调用线稿模型 + 漫画修复模型
```

这使 `main.py` 无须知道 LaMa 需要 RGB、Manga 需要灰度，或 Real-ESRGAN 使用什么网络。扩展一个新修复模型时，只要实现同一输入输出契约，业务层几乎不需要改动。

需要同时看到它的边界：相同接口不代表模型能力相同。Manga 路径会先把彩色图变成灰度，mask 内结果必然没有原始色相；OpenCV Telea 没有语义理解；LaMa 输出是根据上下文生成的合理补全，不是被遮挡像素的证据级还原。统一接口解决的是调用复杂度，不会抹掉模型本身的统计假设。

## `auto` 设备选择为什么不只看 `torch.cuda.is_available()`

工程中设备配置有 `cpu`、`cuda`、`auto` 三种。`engine.py` 的 `device_candidates()` 为 `auto` 返回 `("cuda", "cpu")`：先**真的**加载模型到 CUDA 并尝试初始化，失败后才重建并加载 CPU 模型。

仅调用 `torch.cuda.is_available()` 不够。它只表示当前 PyTorch 大致检测到了一个 CUDA 环境；实际模型仍可能因为以下原因不能工作：

- 驱动、CUDA 运行时与当前 PyTorch wheel 不兼容；
- 加载特定 TorchScript/权重时发生设备或算子错误；
- 模型在首次迁移或推理时显存不足；
- 进程里已有其他任务占用了显存。

因此项目的 `auto` 是“按候选设备完成真实初始化的回退策略”，不是“看到显卡图标就确信 GPU 可用”。显式选择 `cuda` 时则不回退，以便尊重用户的明确选择并暴露错误；这是一种可预测性与可用性之间的合理区分。

## 训练链路和本项目推理链路的对照

| 训练小模型时 | CleanCanvas Studio 推理时 |
| ------------ | ------------------------- |
| 数据 + 标签 | 图片/视频帧 + mask，没有训练标签 |
| `model.train()` | `model.eval()` |
| 计算 `loss` | 不计算 loss |
| `loss.backward()` | 不计算梯度 |
| `optimizer.step()` 更新参数 | 参数固定，只读取权重 |
| 关注训练/验证泛化 | 关注输入约定、视觉质量、延迟、显存和稳定性 |

训练与推理共享张量、模型层和设备等基础设施，却不是同一段流程。项目中使用 `torch.inference_mode()` 正是为了明确：“这个阶段只做前向计算，不建立反向传播需要的计算图。”后面会详细解释它与 `eval()` 的区别。

## 如何开始阅读这个项目

对于初学者，建议不要从 RRDB 网络最深处开始。按下列顺序打开代码：

1. `backend/main.py` 的 `_repair()`：先确认输入 `frame` 和 `mask`，以及没有 mask 时为何不加载模型。
2. `backend/inpaint/engine.py` 的 `create_inpaint_engine()`：看字符串模式如何变成具体引擎。
3. `TorchScriptLaMaEngine.inpaint()`：下一篇会逐行拆开其预处理、推理与后处理。
4. `RealESRGANEnhancer.enhance()`：观察超分输入如何从 OpenCV 变成张量再变回来。
5. 最后回到 `_build_rrdb_net()`：此时再读卷积、残差与上采样，才不会被类嵌套淹没。

## 面试速答

**问：该项目中的深度学习模块做什么？**

答：项目不训练模型，而是将预训练的 LaMa/Anime-LaMa/Manga 模型用于带 mask 的图像修复，并将 Real-ESRGAN 用于超分辨率增强。业务层生成全尺寸 mask，推理引擎把图像预处理为模型约定的张量，在 CPU 或 CUDA 上执行前向推理，后处理后返回 OpenCV 可继续处理的 BGR 图像。

**问：为什么不直接在业务代码里 `torch.load` 后调用模型？**

答：模型加载、缓存校验、CPU/GPU 回退、输入输出格式与错误处理属于推理基础设施。用 `create_inpaint_engine()` 统一封装能让业务层只依赖 `inpaint(image, mask)` 契约，避免模型细节散落到视频、GUI 和任务调度代码中。

## 小结

- 这个项目的 PyTorch 代码是预训练模型推理，而不是模型训练。
- `main.py` 管任务与 mask，`engine.py` 管修复模型与设备，`realesrgan.py` 管超分模型，职责清晰。
- OpenCV、PaddleOCR 与 PyTorch 是协作组件，不应混为一个框架。
- 从输入输出和工厂接口开始读，随后再进入张量变化与网络结构，是更适合初学者的代码阅读路径。
