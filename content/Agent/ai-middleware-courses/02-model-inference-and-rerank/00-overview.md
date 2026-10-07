+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '课程导读：从搜索排序到可运行的文本模型服务'
+++

输入一句搜索词后，为什么有的结果排在前面？答案不是“模型觉得它更像”，而是一个可以拆开学习的问题：系统先拿到一个 **query（查询）**，收集一批 **candidate（候选）**，再为每个候选计算一个 **score（分数）**，最后按分数排序。文本重排序模型只负责其中的“打分”环节；库存、权限、地域、内容合规等确定性规则应在模型前后单独处理。

本课程不假设读者会深度学习，也不假设读者正在维护某个 AI 项目。目标是从一个极小的 PyTorch 程序开始，逐步理解文本如何变成数字、模型如何计算分数、怎样将模型安全地做成 HTTP 服务，以及如何用数据判断服务是否真的有用。

如果你是第一次接触 `tensor`、loss、梯度或训练集划分，建议先完成[PyTorch 前置理论：从机器学习到训练循环](../01-pytorch-foundations/00-overview.md)。本课程会直接把这些概念放进 token、embedding 和 Transformer 的语境中；先看懂训练循环，再看模型如何用于排序，阅读会更顺畅。

## 先认识本课程的四个词

以“机械键盘”为例，用户输入的文字是 query；商品、文档或工单标题是 candidate；模型输出的实数是 score。score 只表示**同一次查询中的相对相关性**，例如 `0.81` 比 `0.35` 更适合排在前面；它通常不能解释为 81% 的概率，更不能拿去和另一个 query 的分数直接比较。

模型不能直接处理汉字或英文单词。tokenizer 会把文本切成 token，并给每个 token 一个整数 ID；若句子长度不同，再补齐到相同长度。多个数字组成 **tensor（张量）**，可以把它理解为带形状的多维数组。模型是含有可学习参数的函数，训练会修改参数；**inference（推理）** 则固定参数，只计算输出。

```text
query:      "机械键盘"
candidates: ["茶轴键盘", "蓝牙鼠标", "键帽收纳盒"]
                  ↓ 模型分别计算
scores:     [0.91, 0.14, 0.32]
                  ↓ 降序排列
result:     茶轴键盘 → 键帽收纳盒 → 蓝牙鼠标
```

## 阅读顺序

1. [从张量到 Transformer](01-deep-learning-transformer-foundations.md)：用最小可运行程序建立 token、张量、参数、训练和推理的直觉。
2. [召回与文本重排序](02-retrieval-and-cross-encoder-rerank.md)：理解为何先找候选、再精排，以及 bi-encoder 和 cross-encoder 的取舍。
3. [PyTorch 推理环境与资源](03-pytorch-loading-device-and-precision.md)：让模型在 CPU 或 GPU 上稳定运行，并理解显存、batch、精度和 OOM。
4. [FastAPI 文本排序服务](04-fastapi-rerank-service.md)：将一个加载一次的模型包成有输入边界、健康检查和明确错误语义的 API。
5. [质量评测、压测与上线](05-performance-evaluation-and-production.md)：同时测量排序质量和运行性能，避免“接口能返回”被误当成“服务可用”。
6. [模型文件、PaddleOCR 与重排序部署](06-模型文件、PaddleOCR与重排序部署.md)：弄清下载的模型是什么，以及它如何从本地文件变成后端服务。
7. [Python 图像修复与指定区域 Inpainting](07-Python图像修复与指定区域Inpainting.md)：从前端选区产生 mask，到本地模型补全自有图片的最小可运行实践。

## 环境准备

以下命令创建独立实验环境。PyTorch 的 CPU/GPU 安装命令会随平台变化；第一次使用 GPU 时，应以 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 给出的当前组合为准，而不是盲目复制旧教程。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch transformers fastapi "uvicorn[standard]" httpx pydantic
```

预期输出是最后一行没有报错，并且随后执行 `python -c "import torch; print(torch.__version__)"` 能打印版本号。没有 GPU 也完全可以完成前两篇和 API 实验；GPU 只会改变速度，不改变概念。

## 常见问题与排查

- `python` 找不到：确认 Python 已加入 PATH，或以 `py -3.11 -m venv .venv` 创建环境。
- PowerShell 禁止激活脚本：仅对当前窗口执行 `Set-ExecutionPolicy -Scope Process Bypass`，不要为此关闭整台机器的安全策略。
- 安装到全局环境：激活后执行 `python -c "import sys; print(sys.executable)"`，路径应包含 `.venv`。
- 下载模型失败：先确认网络、证书与磁盘空间；课程中的最小实验并不依赖下载预训练权重。

## 小结

- 排序问题由 query、candidate 和 score 构成；模型只是计算 score 的一种方法。
- token 是文本的编码单位，tensor 是模型实际读取的数值容器，推理不会修改模型参数。
- 先运行最小实验，再接触预训练模型和 GPU，学习路径才不会倒置。
