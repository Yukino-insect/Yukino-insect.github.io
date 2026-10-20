+++
date = '2026-10-07T19:00:00+08:00'
draft = false
title = '零基础 PyTorch 课程导读：从 Python 程序到第一个会学习的模型'
+++

你不需要先学完高等数学、线性代数或深度学习，才能开始这门课。对零基础读者而言，眼下最重要的目标只有一个：**看懂并亲手运行一个很小的 PyTorch 训练程序，知道它为什么会从数据中改进。**

网络上常见的 PyTorch 示例把数据、模型、损失、梯度和优化器压缩到十几行。代码短并不等于概念少；如果每个词都陌生，照抄之后得到的往往只是一次成功运行，而不是可以迁移的理解。本课程会先用生活化的问题建立直觉，再逐步给出术语和代码。公式会出现，但只用来确认已经理解的过程，不把它当作入场券。

## 这门课会带你做到什么

完成基础理论部分和后续项目实践文章后，你应当能够：

- 说清楚“让程序预测一个答案”与“让程序从例子中学习”的区别；
- 看懂一条样本、一个 batch（小批量）、训练集、验证集各自是什么；
- 读懂常见的 `torch.tensor`、`nn.Linear`、`loss.backward()` 和 `optimizer.step()`；
- 说明 `nn.Module`、`forward()`、激活函数、logit、损失函数和反向传播分别解决什么问题；
- 根据回归、二分类或多分类任务，匹配模型输出、标签的形状/类型和合适的损失函数；
- 运行一个二分类示例，并根据 loss、准确率和报错的形状信息做最初步的排查；
- 知道一个模型在训练集表现好，并不自动表示它对新数据有用。
- 沿着 CleanCanvas Studio 的真实调用链，读懂模型为何延迟加载、图像为何需要转成 `[1, C, H, W]`、权重如何加载到 CPU/GPU，以及为什么大图需要分块推理。
- 在面试中清楚地区分训练与推理、OpenCV 与 PyTorch、TorchScript 与 `state_dict`、`eval()` 与 `inference_mode()`、GPU 可见与模型实际可用。

本课程不会带你从零训练 LaMa 或 Real-ESRGAN；这需要大规模数据、昂贵算力与另一个完整专题。后半段讲的是工程中更常见的任务：**可靠地使用已经训练好的模型进行图像推理**。GPU、精度、模型格式和部署并不“不重要”，只是必须建立在前四篇的基础之上；否则它们只会变成一串更长的配置项。

## 开始前需要准备什么

唯一的前置要求是能读懂最基础的 Python：变量、列表、函数、`for` 循环和 `print`。例如，下面的代码不必逐字符背诵，但你应知道它会逐个打印列表里的数字：

```python
numbers = [2, 4, 6]

for number in numbers:
    print(number)
```

没有 NVIDIA 显卡也没有关系。所有示例故意使用极小的数据和模型，普通 CPU 完全够用。先在一个空目录创建 Python 虚拟环境；它相当于给本课程单独准备一个工具箱，不会弄乱电脑上其他项目的依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch
python -c "import torch; print(torch.__version__)"
```

最后一条命令打印出版本号，说明安装成功。若 PowerShell 因执行策略拒绝激活脚本，可以临时在当前窗口执行 `Set-ExecutionPolicy -Scope Process Bypass` 后再激活，或改用你已熟悉的终端。以后需要 CUDA 时，请到 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 选择与你的系统和驱动相符的命令；旧教程里的安装命令没有替你的电脑承担兼容性责任。

## 先建立一幅全景图

假设要写一个程序，根据“是否下雨、气温是否低”预测明天是否需要带伞。你先准备许多过去的例子：每条例子都有输入和正确答案。程序从这些例子中猜一个答案，拿猜测与正确答案比较，再稍微调整内部数值，使下次猜测更接近答案。重复很多次后，它可能学到有用的规律。

```text
带答案的历史例子
        ↓
模型根据输入做一次猜测
        ↓
损失告诉它“猜错了多少”
        ↓
梯度指出内部数值该往哪个方向调整
        ↓
优化器真的修改这些数值
        ↓
用没有参与调整的新例子检查效果
```

这里的“内部数值”稍后会叫作**参数**。你暂时可以把模型看成一台有许多可调旋钮的计算器：数据告诉它题目与答案，训练就是不断把旋钮拧得更合适。它不是理解语言或拥有常识；它只是根据数据调整计算规则。这个界限越早分清，越不容易被看似神奇的演示误导。

## 推荐阅读与动手顺序

1. [任务、数据与泛化](01-machine-learning-data-and-generalization.md)：从一条带答案的样本开始，理解训练、验证和测试为什么不能混用。
2. [张量、形状与自动求导](02-tensor-linear-algebra-and-gradients.md)：认识 PyTorch 存放数据的方式，并亲眼看一次导数如何给出调整方向。
3. [自动求导与模型参数](02-0-autograd-computation-graph-and-model-state.md)：从计算图、`nn.Parameter`、优化器状态到 `state_dict`、checkpoint 和 TorchScript，回答参数和梯度究竟存在哪里。
4. [神经网络、前向传播与激活函数](02-1-neural-networks-forward-and-activation.md)：从单个线性层进入 `nn.Module`，理解多层网络为何需要非线性。
5. [损失函数、反向传播与梯度下降](02-2-loss-functions-and-backpropagation.md)：建立“任务、输出、标签、损失、梯度”的完整对应关系。
6. [第一个训练循环](03-neural-network-training-loop.md)：把前面的部件连起来，完成一次真正的训练、验证和排错。
7. [优化器、批训练、正则化与训练稳定性](03a-optimizers-regularization-and-training-stability.md)：理解全量/小批量梯度的统计意义、SGD、Momentum、AdamW、正则化、梯度裁剪与最佳 checkpoint。
8. [评估指标与分类阈值](03b-evaluation-metrics-and-thresholds.md)：用混淆矩阵、Precision、Recall、F1 与错误代价评价模型。
9. [网络架构与迁移学习](03c-network-architectures-and-transfer-learning.md)：分清 MLP、CNN、RNN、Transformer 的归纳偏置、计算结构与预训练策略。
10. [训练实验与诊断](03d-training-experiments-and-diagnostics.md)：建立可追溯实验，并按固定顺序定位 loss、数值与泛化问题。
11. [项目实战总览：从机器学习到预训练模型推理](04-project-inference-reading-map.md)：先用可运行的预训练模型例子，再以 CleanCanvas Studio 为例建立“媒体任务、mask、模型引擎、输出”的调用全景。
12. [PyTorch 视觉预训练模型推理详解](04a-pretrained-model-inference-tutorial.md)：先分清 PyTorch、`torchvision`、Pillow 与模型权重的职责，再从分类器、`state_dict`、TorchScript 到 LaMa 和 Real-ESRGAN，完整走一遍模型输入、前向计算与输出后处理。
13. [图像张量基础：NumPy 与 PyTorch 的数组、通道、mask 和内存](04b-image-arrays-numpy-pytorch.md)：补齐图像 shape、dtype、颜色顺序、切片、设备和 mask 的基础。
14. [图像如何变成模型张量](05-image-tensor-preprocessing-and-inpainting.md)：逐步读懂 BGR/RGB、`uint8`/`float32`、NCHW、padding、mask 与后处理。
15. [读懂图像推理中的数值计算](05a-numerical-operations-python-numpy-pytorch.md)：从 Python 标量、NumPy 数组到 PyTorch Tensor，逐行解释 padding、mask、tile、dtype、shape、device 与值域操作。
16. [加载权重、选择设备与推理模式](06-model-loading-device-and-inference-mode.md)：解释 TorchScript、checkpoint、`state_dict`、CUDA 回退、`eval()`、FP16 与 `inference_mode()`。
17. [从 PyTorch 基础读懂 Real-ESRGAN](07-realesrgan-network-and-tiled-inference.md)：从网络类、卷积、残差、稠密连接到 4×超分、`PixelShuffle`、tile 与显存控制。
18. [项目面试题与代码阅读清单](08-project-interview-and-debugging.md)：把前文汇总为可以用自己的话回答的项目问题、排障路径与边界。

建议采用“读一小节、运行一段、故意改坏一次、再改回来”的节奏。比如把 `batch_size=32` 改成 `16`，观察输出是否仍合理；或删掉 `optimizer.step()`，观察模型为何不再进步。对初学者来说，能解释一次失败，常常比顺利运行十次更有价值。

## 读代码时的四个固定问题

后面每次碰到不熟悉的代码，都先问这四件事，而不是急着记 API：

1. **输入是什么？** 它是几个数字、一批图片，还是文本转换出的编号？
2. **输出是什么？** 是一个预测分数、一个类别，还是新的数字矩阵？
3. **这一步是否改变模型？** `model(...)` 通常只计算；`optimizer.step()` 才会改参数。
4. **如何知道它做得好不好？** 看的是训练损失、验证指标，还是一批具体错误样本？

这四个问题会贯穿所有机器学习框架。框架的名字和 API 会迭代，输入、输出、更新与评价这条因果链不会。

后半段阅读已有模型的工程代码时，再额外问两个问题：**模型权重从哪里来、模型是否真的处于可推理状态？** 前者涉及模型格式和完整性校验，后者涉及设备、`eval()`、无梯度上下文与数据预处理。能够回答它们，才不是只会复制一个“可运行”的推理片段。

## 小结

- 学 PyTorch 的第一步不是背接口，而是理解“例子、猜测、误差、调整、验证”的闭环。
- 课程只要求基础 Python；没有 GPU 也能完成全部示例。
- 遇到陌生代码，先确认输入、输出、是否更新参数以及评价方式。把这些边界弄清后，术语自然会各归其位。
- 后续会用 CleanCanvas Studio 的图像修复和超分代码落地这些概念；重点是理解推理工程，而不是假装已经训练过这些大型模型。
