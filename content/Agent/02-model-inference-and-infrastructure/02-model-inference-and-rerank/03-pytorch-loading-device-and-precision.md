+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'PyTorch 推理实践：设备、精度、批处理与显存'
+++

一段模型代码“能跑”只是开始。推理服务还必须回答：模型和输入在哪块设备上？一次放多少个文本对？使用什么浮点精度？模型权重从哪里来？这些问题决定了延迟、吞吐、成本和是否会突然 OOM（out of memory，内存不足）。

## 先辨认 CPU、GPU 与设备

CPU 擅长通用控制逻辑，GPU 擅长同时执行大量相同类型的矩阵运算。PyTorch 中 `device` 指明 tensor 和参数实际存放的位置；同一次运算的参与者必须在同一设备上。

```python
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("device:", device)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))

x = torch.randn(2, 3, device=device)
print(x.device, x.dtype, x.shape)
```

预期输出在没有 NVIDIA CUDA GPU 的机器上为 `device: cpu`，最后一行包含 `cpu torch.float32 torch.Size([2, 3])`；有可用 CUDA GPU 时会显示 `cuda` 和显卡名称。这不是失败检测：课程示例应在 CPU 上正确运行，只是耗时更长。

## 可复现环境和权重

模型服务由代码、Python 依赖、模型配置、tokenizer、权重文件和运行时共同组成。仅记录“用了某个模型名”不够，因为同名仓库的 revision 可能改变。实际项目应至少固定依赖版本和模型 revision，并将下载缓存放在可控目录，避免运行时临时下载使启动结果不可预测。

```powershell
pip freeze | Select-String "torch|transformers"
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```

预期输出会列出已安装版本；CPU wheel 的 `torch.version.cuda` 可以是 `None`。把这份输出写进部署记录，比口头说“我的电脑能跑”可复现得多。

## 正确的推理模式

下面用线性层模拟模型。`eval()` 是模块状态切换：它让 dropout、batch normalization 等层采用推理行为。`inference_mode()` 是上下文：它不构建反向传播所需的计算图。两者不是替代关系，生产推理应同时使用。

```python
import torch
from torch import nn

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = nn.Sequential(nn.Linear(8, 16), nn.ReLU(), nn.Linear(16, 1)).to(device)
batch = torch.randn(32, 8, device=device)

model.eval()
with torch.inference_mode():
    scores = model(batch).squeeze(1)

print(scores.shape)
print(scores.requires_grad)
```

预期输出是 `torch.Size([32])` 和 `False`。如果第二行是 `True`，通常意味着代码遗漏了推理上下文；短脚本未必马上出错，但持续服务会平白保留内存。

## batch 与长度：吞吐和延迟的拉锯

**batch** 是一次前向计算包含的文本对数量。合批常能提高 GPU 利用率和总体吞吐；但请求会等待凑批，单次计算也变久，所以尾延迟可能恶化。Transformer 还受序列长度影响。若 batch 内按最长样本补齐，少数超长文本会让整批做更多无效计算。

实践中的安全起点是：设置最大 token 长度，按长度相近的请求分批，并测量而非猜测。下面程序逐步加大 batch；它不是严格基准，只用于观察形状和容量边界。

```python
import torch
from torch import nn

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = nn.Linear(768, 1).to(device).eval()

for batch_size in [1, 8, 32, 128, 512]:
    try:
        x = torch.randn(batch_size, 128, 768, device=device)
        with torch.inference_mode():
            y = model(x)
        print(batch_size, tuple(y.shape))
        del x, y
    except torch.OutOfMemoryError:
        print(batch_size, "OOM: stop and lower the limit")
        break
```

预期 CPU 会打印全部 shape；显存较小的 GPU 可能在某一档打印 OOM，这正是实验要揭示的边界。不要在生产请求中依赖“试到 OOM 再说”。应在预发布压测中确定最大长度、最大候选数和服务端 batch 上限。

## FP32、FP16、BF16 分别是什么

浮点数用有限位数表示实数。FP32（32 位）通常最稳妥；FP16（16 位）占用更少内存，在兼容 GPU 上可能更快，但有效表示范围较小；BF16 同样是 16 位，却保留更大的指数范围，许多较新的 GPU 对它更友好。不能只因为“半精度省显存”就强制转换：模型、硬件和算子都需要实测。

```python
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
x = torch.randn(1024, 1024, device=device)
print("fp32 bytes:", x.numel() * x.element_size())
if device.type == "cuda":
    print("fp16 bytes:", x.half().numel() * x.half().element_size())
```

预期在 CUDA 上第二个数约为第一个的一半。它只证明张量存储缩小；模型总显存还包括权重、临时激活和框架缓存，速度和排序质量也必须单独测试。

## OOM 的正确排查顺序

1. 记录发生 OOM 时的 batch、token 长度、候选数、模型版本和并发数，先让问题可复现。
2. 先降低候选数或最大长度，再降低 batch；这两项直接缩小工作量。
3. 确认只有一个进程加载了 GPU 模型。多 worker 往往各自复制一份权重。
4. 检查是否漏掉 `inference_mode()`、是否保存了 GPU tensor 到全局列表、是否并发执行了过多请求。
5. 最后才考虑精度、模型尺寸或增加显存。`torch.cuda.empty_cache()` 不能修复真实的容量不足，只能释放未使用的缓存块。

常见的 `Expected all tensors to be on the same device` 表示模型在 GPU 而 token 在 CPU（或反之）；在调用前把 tokenizer 返回的每个 tensor 都 `.to(device)`。`CUDA out of memory` 则不要靠无限重试掩盖，应返回可读的限流/容量错误，并保护服务恢复。

## 小结

- 设备、dtype、权重版本都是推理契约的一部分，应被记录和验证。
- `eval()` 控制层行为，`inference_mode()` 关闭梯度追踪；二者都应使用。
- batch 和 token 长度共同决定吞吐、延迟和显存，安全上限必须通过测量得到。
- FP16/BF16 是可选优化，不是绕过容量规划的魔法。
