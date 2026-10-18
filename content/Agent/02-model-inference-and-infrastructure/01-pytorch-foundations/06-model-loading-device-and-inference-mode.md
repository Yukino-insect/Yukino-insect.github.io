+++
date = '2026-10-15T20:00:00+08:00'
draft = false
title = '预训练模型如何下载和使用：权重格式、设备、dtype 与推理模式'
+++
“下载一个 `.pt` 文件，然后写 `model(x)`”省略了模型推理最容易出错的部分：文件里装的是什么？谁创建网络？图像数组如何变成 Tensor？模型与输入为什么必须匹配 device、dtype 和运行状态？本章以 [CleanCanvas Studio](https://github.com/Yukino-insect/clean-canvas-studio) 的真实后端为例回答这些问题。它同时使用 **TorchScript 推理包**（LaMa、Manga）和 **checkpoint 参数包**（Real-ESRGAN）；它们都可被称为“模型文件”，但加载方式不能混用。

## 先建立推理的四份契约

一次可靠推理要同时满足四份契约：

```text
模型结构 ── 参数名和张量 shape ── 权重文件
    │
    ├── 输入/输出契约：参数个数、shape、通道、值域、dtype
    │
    └── 运行契约：device、train/eval 状态、是否记录 autograd 图
```

模型结构是 `nn.Module` 的层与 `forward()` 的计算顺序；权重是其中 `nn.Parameter` 的数值；输入契约规定模型函数接收什么；运行契约规定这次计算在哪里、如何执行。文件能读入，不表示四份契约已经匹配。

例如 LaMa 的 `TorchScriptLaMaEngine.inpaint(image_bgr, mask)` 最后调用模型时有**两个**参数：图像 `[1, 3, H', W']` 和 mask `[1, 1, H', W']`。Real-ESRGAN 则接收一个 RGB 图像 Tensor，原生输出是高宽四倍的 RGB Tensor。它们即便文件扩展名相同，也不可互换。

## `state_dict` 与 TorchScript：扩展名不是格式

`.pt`、`.pth`、`.jit` 只是命名习惯。加载前要看发布方的序列化格式和输入说明，而不是根据后缀猜 API。

| 类型 | 文件包含什么 | 谁创建结构 | 加载 API | 项目实例 |
| --- | --- | --- | --- | --- |
| `state_dict` / checkpoint | 参数名到 Tensor 的映射，可能外包元数据字典 | 应用代码 | `torch.load()` + `load_state_dict()` | Real-ESRGAN `.pth` |
| TorchScript 模块 | 可执行的图及参数 | TorchScript 反序列化器 | `torch.jit.load()` | LaMa `.pt`、Manga `.jit` |
| Python 整对象 pickle | Python 对象及其引用 | 依赖原始 Python 类 | `torch.load()` | 本项目未使用；不应加载不可信来源 |

### `state_dict` 只保存参数，不会替你猜网络

训练端通常保存：

```python
torch.save(model.state_dict(), 'classifier.pth')
```

其中可能有 `conv_first.weight`、`body.0.rdb1.conv1.bias` 这样的键和 Tensor 值，但没有独立描述“按什么顺序走层、怎样上采样、`forward()` 怎样相加”。加载方必须先以相同类和构造参数创建结构：

```python
model = MyClassifier(in_features=2, hidden=8)
state = torch.load('classifier.pth', map_location='cpu', weights_only=True)
model.load_state_dict(state, strict=True)
model.eval()
```

`strict=True` 会在缺键、多键或张量 shape 不符时立刻失败。它阻止 Anime 权重被误装进 General 网络后，带着错误继续跑。

CleanCanvas 的 `backend/enhance/realesrgan.py` 在 `_load_model()` 中的真实逻辑是：

```python
checkpoint = torch.load(str(path), map_location='cpu', weights_only=True)
state = checkpoint.get('params_ema', checkpoint.get('params', checkpoint))
model.load_state_dict(state, strict=True)
loaded = model.to(device).eval()
```

- `weights_only=True` 限制反序列化为权重所需数据，降低任意 Python 对象被恢复的风险；它不等同于“文件可信”，来源与哈希仍要验证。
- checkpoint 可能直接是 state dict，也可能把参数放在 `params_ema` 或 `params`。这里优先指数滑动平均参数 `params_ema`，不存在才回退。
- `_asset_and_model()` 会按模式构建空网络：Anime 为 6 个 RRDB 的 `RRDBNet`，General 为 `SRVGGNetCompact`。先建结构、再按名字把参数拷入结构，才是 `load_state_dict()`。
- `.to(device)` 迁移已登记的参数和 buffer，`.eval()` 切换层行为；它们都还没有执行图像推理。

### TorchScript 恢复可调用模块，仍要遵守输入契约

LaMa、Anime-LaMa、Manga 使用：

```python
model = torch.jit.load('big-lama.pt', map_location='cpu')
model = model.to(device).eval()
```

这里无需在当前 Python 文件重新定义训练时的网络类；但不代表“任意 Tensor 都能喂”。LaMa 的图像与 mask、Manga 的灰度图与线稿等参数数目、shape、归一化范围，仍由导出的 `forward` 签名和项目预处理共同规定。不要靠不断尝试不同 API 猜陌生权重的格式。

## 模型资源：下载、校验和缓存的副作用边界

项目用不可变 `ModelAsset` 描述 `filename`、下载 `url` 和预期 `md5`；`ModelStore.ensure(asset)` 的行为是：

```text
正式缓存存在且 MD5 匹配 → 返回路径
              │否则
创建临时 .download 文件 → 下载 → 流式计算 MD5 → 移动为正式文件
```

下载中断或哈希不匹配时，正式文件名不会指向半个 checkpoint，`finally` 还会清掉临时文件。MD5 在这里用于发现缓存损坏或错误下载，**不是签名验证**，不能取代可信发布页、HTTPS 与版本记录。

Real-ESRGAN 在尝试 CUDA/CPU 前先执行 `ModelStore.ensure()`，所以下载失败不会触发“回退 CPU”；设备回退只处理后续真实的模型初始化失败。

## 为什么先在 CPU 加载，再迁移设备

两种格式都使用 `map_location='cpu'`：

```python
torch.load(path, map_location='cpu', weights_only=True)
torch.jit.load(path, map_location='cpu')
```

这指定反序列化出的 Tensor 先放 CPU，避免保存于 `cuda:1` 的权重无法在 CPU 或另一张 GPU 上读取，也避免加载阶段立刻占满目标显存。随后应用显式 `.to(self.device)`，设备控制权不再藏在旧 checkpoint 里。

一次卷积要求输入、权重和中间 Tensor 位于相容设备：

```python
model = model.to('cuda')
image = torch.zeros(1, 3, 64, 64)  # 仍在 CPU
model(image)                       # 设备不匹配
```

正确流程是把数据也迁往模型所在设备；从 CUDA Tensor 交给 NumPy 前必须 `.cpu()`：

```python
image = image.to('cuda')
with torch.inference_mode():
    output = model(image)
array = output.detach().cpu().numpy()
```

项目的 `auto` 也不是仅根据一次 `torch.cuda.is_available()` 作决定。`device_candidates('auto')` 给出 `('cuda', 'cpu')`，外层会先检查 CUDA 并**实际完成模型加载**；失败后才用一个新的模型实例尝试 CPU。显式选择 `cuda` 或 `cpu` 时不会静默降级。Real-ESRGAN 还把 CUDA 首次失败原因存到 `device_fallback_reason`，供 `MediaEnhancer` 写日志；LaMa/Manga 由 `create_inpaint_engine()` 执行同样的候选循环。驱动、显存、算子或权重迁移都可能在 `is_available()` 为真后失败，所以必须真实尝试。

## dtype 与 FP16：必须让模型和输入同步

`dtype` 是元素数值类型。CleanCanvas 的 Real-ESRGAN 只在实际选择 CUDA 时使用半精度：

```python
loaded = model.to(device).eval()
use_half = device == 'cuda'
if use_half:
    loaded = loaded.half()

tensor = torch.from_numpy(image.transpose(2, 0, 1)).float().unsqueeze(0).to(device)
if use_half:
    tensor = tensor.half()
```

模型已是 `float16` 时，输入也必须转为 `float16`；否则卷积通常会报 dtype 不匹配。输出仍可能为 FP16，项目再用 `.float().cpu().clamp(0, 1)` 先回到 float32，再交给 NumPy/OpenCV。CPU 路径保留 float32。这不是 `autocast` 的混合精度训练方案，而是 CUDA 推理中整体 half 的明确策略；是否安全仍取决于模型、算子与硬件，不能不加区分地套用。

## 从 OpenCV 图像到 LaMa 输入：逐行数据流

`TorchScriptLaMaEngine.inpaint()` 的边界是 BGR `uint8` 图像与 mask。其关键实现为：

```python
rgb = cv2.cvtColor(image_bgr[:, :, :3], cv2.COLOR_BGR2RGB)
binary_mask = (mask > 0).astype(np.uint8)
padded_image = _pad_to_modulo(rgb, 8)
padded_mask = _pad_to_modulo(binary_mask, 8, constant=True)[:, :, 0]

image_tensor = torch.from_numpy(
    padded_image.transpose(2, 0, 1).astype(np.float32) / 255.0
)
mask_tensor = torch.from_numpy(padded_mask[np.newaxis].astype(np.float32))
with torch.inference_mode():
    result = model(image_tensor.unsqueeze(0).to(device), mask_tensor.unsqueeze(0).to(device))
```

| 阶段 | shape / dtype | 含义 |
| --- | --- | --- |
| `image_bgr` | `[H,W,>=3]` / `uint8` | OpenCV 边界 |
| `rgb` | `[H,W,3]` / `uint8` | 改正 BGR 通道语义 |
| `padded_image` | `[H',W',3]` | 对齐模型要求的 8 的倍数 |
| `image_tensor` | `[3,H',W']` / `float32`，`[0,1]` | HWC 转 Conv2d 的 CHW |
| `mask_tensor` | `[1,H',W']` / `float32` | 单通道区域提示 |
| 两个调用参数 | `[1,3,H',W']`、`[1,1,H',W']` | `unsqueeze(0)` 添加 batch |

图像采取对称 padding，mask 使用常量零 padding；这使额外区域不会被标作待修复。输出则取第 0 个 batch、转 HWC、裁回原高宽、转换为 BGR `uint8`。最后项目会将 mask 外像素写回原图，因为生成模型可能轻微修改选区外区域；这是产品层的后处理保证，不是 TorchScript 本身承诺的行为。

## `eval()`、`no_grad()`、`inference_mode()` 不做同一件事

| API | 控制什么 | 修改参数吗 | 项目用途 |
| --- | --- | --- | --- |
| `model.train()` | Dropout、BatchNorm 等 Module 的训练行为 | 否 | 训练循环 |
| `model.eval()` | 同一批层的推理行为 | 否 | 所有加载后的视觉模型 |
| `torch.no_grad()` | 不记录反向传播图 | 否 | 一般验证/推理 |
| `torch.inference_mode()` | 更严格地关闭 autograd 与相关开销 | 否 | 三条推理路径 |

`eval()` 不会自动关闭梯度记录；`inference_mode()` 也不会自动把 Dropout 设为评估行为。线上推理应同时使用。Real-ESRGAN 的 `_infer()` 返回 inference tensor，`enhance()` 因而把 `.squeeze(0).float().cpu().clamp(0, 1)` 等后处理留在外层同一个 `inference_mode()` 中，并使用非原地 `clamp`。这避免在上下文外对 inference tensor 做不合适的原地更新，也让推理副作用边界更清晰。

## 小结

- checkpoint 保存参数而非网络；Real-ESRGAN 必须先按模式构造网络，再严格加载 `params_ema`、`params` 或直接 state dict。
- TorchScript 可直接恢复可执行 Module；LaMa/Manga 仍须匹配多输入、shape、通道和值域契约。
- 先在 CPU 反序列化、再显式迁移 device；`auto` 通过真实 CUDA→CPU 初始化尝试来回退。
- `eval()` 管层的行为，`inference_mode()` 管 autograd 和推理开销；dtype、device、shape 与颜色通道共同构成一条不可拆开的推理数据流。
