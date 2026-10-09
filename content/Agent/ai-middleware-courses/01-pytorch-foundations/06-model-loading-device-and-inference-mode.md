+++
date = '2026-10-09T20:00:00+08:00'
draft = false
title = '项目实战：加载预训练权重、选择 CPU/GPU 与正确进入推理模式'
+++

“模型文件能下载下来”不等于“模型能正确推理”。在工程里，模型加载至少包含四件彼此独立的事：模型文件完整可信、Python 中的网络结构与权重匹配、模型/输入在同一可用设备上、模型处于正确的推理状态。CleanCanvas Studio 将这些步骤封装在 `ModelStore`、`TorchScriptLaMaEngine` 与 `RealESRGANEnhancer` 中，这正是一段很适合面试讲解的推理工程代码。

## 两种模型文件：TorchScript 与 state dict

项目使用两类文件，它们不能混用加载方式：

| 类型 | 项目例子 | 加载 API | 文件中包含什么 |
| ---- | -------- | -------- | -------------- |
| TorchScript | `big-lama.pt`、`anime-manga-big-lama.pt`、`manga_inpaintor.jit` | `torch.jit.load()` | 已序列化的可执行图/模块及参数，可在没有原始 Python 类定义时运行 |
| checkpoint / state dict | `RealESRGAN_x4plus_anime_6B.pth` | `torch.load()` + `load_state_dict()` | 参数字典或包含参数的 checkpoint；仍需先在 Python 中构建同结构网络 |

LaMa 的加载逻辑很直接：

```python
model = torch.jit.load(str(path), map_location='cpu').to(device).eval()
```

Real-ESRGAN 则必须先通过 `_build_rrdb_net()` 或 `_build_srvgg_net()` 构造网络，再读取 checkpoint：

```python
checkpoint = torch.load(str(path), map_location='cpu', weights_only=True)
state = checkpoint.get('params_ema', checkpoint.get('params', checkpoint))
model.load_state_dict(state, strict=True)
model = model.to(device).eval()
```

`state_dict` 可以理解为“参数名 → 张量值”的字典。它不包含“应当由哪些层组成网络”的完整语义，所以代码必须重建结构。`strict=True` 要求权重键与网络参数完全匹配；少一个或多一个键都报错。这是有意的安全检查：若把 General 模型权重灌进 Anime 网络，宁可在加载时明确失败，也不应带着错配参数悄悄输出错误图像。

`params_ema` 指指数滑动平均（EMA）后的参数。训练时它通常比瞬时参数更平滑，许多生成/超分模型会保存它并优先用于推理。项目回退到 `params`，最后才把整个 checkpoint 视为 state dict，从而兼容不同发布版本的保存结构。

## 为什么先在 CPU 加载，再迁移到目标设备

两个路径都使用 `map_location='cpu'`。这不是表示最终只使用 CPU，而是让文件反序列化阶段不依赖“保存它时的 GPU 编号”。随后再显式 `model.to(device)`。

好处包括：

- 模型即使由有 GPU 的机器保存，也能在只有 CPU 的机器读取；
- 避免在加载时突然把大权重直接塞进显存，便于控制显存峰值；
- 设备选择逻辑集中在 `.to(device)`，更容易实现 CUDA → CPU 回退。

必须记住一条不变式：**模型参数、输入张量和临时输出张量必须位于能共同计算的设备。** `model.to('cuda')` 后，输入也要 `tensor.to('cuda')`。项目的 LaMa 代码在模型调用前将图像张量和 mask 张量都迁移到 `self.device`，正是为此。

## `.eval()`、`no_grad()` 与 `inference_mode()` 的区别

三者常被一起写，却控制不同问题：

| 操作 | 控制的内容 | 典型影响 |
| ---- | ---------- | -------- |
| `model.eval()` | 模块的训练/推理行为 | Dropout 停止随机丢弃；BatchNorm 使用已保存统计量 |
| `torch.no_grad()` | 是否记录 autograd 计算图 | 减少梯度记录与内存；仍允许之后较灵活地恢复梯度相关操作 |
| `torch.inference_mode()` | 更严格的推理专用上下文 | 在许多场景比 `no_grad()` 更省开销；推理张量有更严格的原地修改限制 |

项目加载模型时调用 `.eval()`，调用模型时进入 `torch.inference_mode()`。这两个动作缺一不可：只有 `.eval()` 不会关闭 autograd；只有 `inference_mode()` 不会替 Dropout/BatchNorm 切到推理行为。对于当前有些 TorchScript 模型不一定含这些层，仍应保留这个正确习惯；接口的正确性不能依赖“这次模型正好没触发问题”。

项目在 Real-ESRGAN 的注释中还指出一个细节：由 `inference_mode()` 产生的 inference tensor 不应在该上下文外做 `clamp_()`、`copy_()` 这类原地修改。因此它将张量后处理保持在同一上下文，并使用非原地 `.clamp(0, 1)`。这不是 API 洁癖，而是在视频逐帧场景下会真实触发的约束。

## CUDA、CPU 与 `auto` 的生产级含义

`torch.cuda.is_available()` 是必要检查，但不是“CUDA 推理一定成功”的充分条件。项目把设备意图分为：

```text
cpu  ：只尝试 CPU；稳定但通常较慢
cuda ：只尝试 CUDA；若失败，明确报错
auto ：完整尝试 CUDA 初始化；失败后完整尝试 CPU 初始化
```

为什么 auto 要重新构建/重新加载模型，而不是同一对象失败后直接 `.to('cpu')`？因为失败可能发生在模型迁移、权重转换或某个 CUDA 初始化的中间状态。重新构造一个干净模型对象并从 CPU 权重开始加载，更容易避免部分状态残留，也让 CPU 回退逻辑可测试。

用户可以把“有 NVIDIA 显卡”与“当前 PyTorch CUDA 环境可用”分开验证：

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

最后一项为 `True` 才说明当前 Python 环境中的 PyTorch 能看见 CUDA。驱动、CUDA wheel、Python 版本和环境是否一致，都可能影响它；显卡名称出现在设备管理器里并不能替 PyTorch 做这项验证。

## FP16：为什么 Real-ESRGAN 只在 CUDA 上使用半精度

Real-ESRGAN 加载完成后，在 CUDA 时调用 `loaded.half()`，输入也调用 `tensor.half()`；在 CPU 上保持 `float32`。`float32` 的每个数通常占 4 字节，`float16` 占 2 字节，所以 FP16 常能降低显存占用、提升支持半精度 GPU 上的吞吐。

它并非无条件更好：

- CPU 对 FP16 的算子支持和性能通常不适合作为默认选择；
- FP16 可表示范围和精度更低，极端计算可能溢出或带来数值误差；
- 模型、权重、输入和中间计算必须兼容同一精度。

项目由 `use_half = device == 'cuda'` 集中管理模型、输入与输出缓冲区 dtype，避免常见的“模型是 half、输入还是 float”的类型错误。面试时不要笼统声称“FP16 一定更快”；正确说法是：它通常在受支持的 GPU 推理上换取更低显存与较高吞吐，但必须测试数值质量、硬件支持和实际瓶颈。

## 模型缓存为何需要原子下载与校验

`ModelStore.ensure()` 不是普通的“文件不存在就下载”。它会：

1. 将文件下载到目标目录的临时文件；
2. 计算 MD5 并与 `ModelAsset` 的预期值比较；
3. 只有校验成功才移动为正式模型文件；
4. 无论成功或失败，最终清理临时文件。

这样网络中断、用户取消或下载错误时，半个权重不会伪装成“文件存在的可用模型”。这不是完整的供应链安全方案——MD5 主要用于完整性识别，安全敏感场景还应使用更强哈希、可信发布渠道与签名——但对于本地缓存的损坏防护已经是必要基础。

## 面试速答

**问：`torch.jit.load` 和 `torch.load` 有何区别？**

答：前者加载 TorchScript 序列化模块，通常可直接调用；后者反序列化普通 checkpoint。若 checkpoint 是 state dict，必须先在代码中构建完全一致的模型，再 `load_state_dict`。项目的 LaMa/Manga 用 TorchScript，Real-ESRGAN 用 `.pth` 权重字典。

**问：为何模型推理仍要 `eval()` 和 `inference_mode()`？**

答：`eval()` 切换 Dropout/BatchNorm 等层的推理行为；`inference_mode()` 禁止构建反向传播图以减少资源。前者管模型行为，后者管 autograd，不能互相替代。

**问：`auto` 为什么不只判断 `cuda.is_available()`？**

答：CUDA 可见不代表特定模型能加载或执行，实际仍可能遭遇驱动、算子、显存和权重迁移失败。项目对 CUDA 完成真实初始化，失败后才从干净状态加载 CPU 模型。

## 小结

- TorchScript 是可运行模块，state dict 是参数字典；加载流程不同。
- CPU 加载、再迁移目标设备使模型文件不绑定保存时的设备，并有利于回退。
- `.eval()` 与 `inference_mode()` 分别控制层行为和梯度记录，两者都需要。
- FP16 是 GPU 推理的资源优化手段，不是跨设备的默认真理；模型和输入的 dtype 必须一致。
