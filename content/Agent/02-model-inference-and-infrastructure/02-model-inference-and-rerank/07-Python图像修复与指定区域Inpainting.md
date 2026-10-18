+++
date = '2026-10-02T22:45:00+08:00'
draft = false
title = 'Python 图像修复教程：用 Inpainting 补全指定区域'
+++

当你要处理**自己拥有或已获得编辑授权的图片**时，指定一个区域让模型补全，使用的技术叫作 **inpainting（图像修复）**。它适合清理自己导出的测试文字、日期戳、临时标记，或修复画面中的小瑕疵；但它不是“找回被遮挡的真实像素”的魔法。模型会参考周围画面生成一个看起来连贯的结果，因此原始文字、证据或关键业务字段被覆盖后，修复图不能替代原件。

本文只讨论授权素材的图像修复。对于他人作品上的版权水印、署名或来源标记，应取得无标记原件或授权版本，而不是尝试消除它们。规则并不妨碍学习技术，反而能避免把一个可控的图像编辑问题变成不必要的版权问题。

## 想解决的问题：不是识别文字，而是补全像素

OCR 的问题是“图片上的文字是什么”；inpainting 的问题则是“指定区域被遮住后，怎样根据周围画面补出一块看起来合理的内容”。两者的输入输出完全不同：

```text
OCR
  图片 -> 文字、位置、置信度

Inpainting
  原图 + 遮罩图（mask）+ 可选文字提示 -> 修复后的新图片
```

若你的目标是裁掉固定底部的自有字幕，而且丢失那一条画面也无妨，直接裁切通常更快、更可靠。只有在必须保留尺寸、且被处理区域周围有足够背景可供参考时，inpainting 才值得使用。

## mask：把“指定区域”交给模型的办法

mask 是一张与原图宽高一致的灰度图。最简单的约定是：

| mask 像素 | 含义 |
| --------- | ---- |
| 黑色，值为 `0` | 保留原图，不让模型改动 |
| 白色，值为 `255` | 需要修复，交给模型补全 |

例如要补全坐标 `(80, 400)` 到 `(720, 475)` 的底部横条，后端只需创建一张全黑 mask，再把这个矩形涂白：

```text
原图                         mask
+------------------+        +------------------+
|                  |        |                  |
|     保留画面     |        |    黑色：保留     |
|                  |        |                  |
| [指定修复区域]   |        | [白色：交给模型] |
+------------------+        +------------------+
```

这也是前端选框与模型服务的连接点：前端返回矩形坐标或用户涂抹轨迹；后端把它转换为 mask；模型只接收图片和 mask。Hugging Face Diffusers 的 inpainting 管线明确采用这一语义：白色区域被编辑，黑色区域保留。[官方 inpainting 文档](https://huggingface.co/docs/diffusers/en/using-diffusers/inpaint)

### 不要把 mask 画得刚好贴住文字

文字边缘通常有抗锯齿、投影、描边或压缩伪影。若 mask 只覆盖字符内部，残留的边缘会像一圈脏影子；若 mask 扩得过大，模型又需要凭空生成更多内容，画面更容易失真。

一个实用起点是：在文字四周额外留出 8 到 24 像素边距，然后根据图片分辨率和结果逐步调整。遇到文字压在眼睛、手指、复杂花纹、表格数据或原有文字上时，应降低期望：模型只能推测，不知道那里原本究竟是什么。

## 模型、提示词与结果分别负责什么

常见的 inpainting 模型可粗略分为两类：

| 类型 | 更适合 | 局限 |
| ---- | ------ | ---- |
| 上下文修复模型，例如 LaMa 类方法 | 墙面、天空、地面、普通纹理和较小瑕疵 | 对复杂物体和语义细节的控制较弱 |
| 扩散式 inpainting 模型 | 需要结合文字描述重建背景或物体 | 显存/时间开销更大，也更可能生成不真实的细节 |

本文的最小实例使用 Diffusers 的 `AutoPipelineForInpainting`。它负责加载与所选 checkpoint 匹配的推理管线；第一次运行会下载模型配置和权重，之后命中本机缓存便无需再次下载。关于“下载的模型文件究竟是什么、为何应固定版本并在生产环境预置”，请先阅读上一篇[模型文件、PaddleOCR 与重排序部署](06-模型文件、PaddleOCR与重排序部署.md)。

提示词不是区域选择器。区域由 mask 决定；提示词只告诉生成模型“这一块应该像什么”。例如修复桌面上自己添加的测试标签时，`a clean wooden desktop with natural grain` 比“remove text”更有帮助，因为前者描述了要补出的背景，后者只描述了不想要什么。

## 运行前的环境准备

以下命令创建一个独立虚拟环境，并安装最小依赖。Python 3.10 及以上较合适；本机没有 GPU 也能运行，但扩散模型在 CPU 上会很慢。若使用 NVIDIA GPU，`torch` 的安装组合应以 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 显示的 CUDA 版本为准。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch diffusers transformers accelerate safetensors pillow
```

预期是最后一条命令成功结束。接着运行下面脚本的首次下载会占用明显的磁盘空间；网络受限环境应在可联网机器预下载并将模型目录作为制品交付，而不是让生产服务临时联网。

## 最小可运行 Python 实例

将以下内容保存为 `inpaint_demo.py`，然后在已激活的虚拟环境中执行 `python inpaint_demo.py`。

脚本**不需要任何外部图片**：它先生成一张带有 `DEMO TEXT` 的测试图，随后只把该测试文字所在的矩形区域涂白到 mask 中，最后调用模型生成 `output.png`。这只是验证“原图 + 指定区域 mask + 模型”的完整链路；请把自己的已授权图片接入后再评估真实效果。

```python
from pathlib import Path

import torch
from diffusers import AutoPipelineForInpainting
from PIL import Image, ImageDraw


MODEL_ID = "kandinsky-community/kandinsky-2-2-decoder-inpaint"
WORK_DIR = Path("inpaint-output")
IMAGE_SIZE = (512, 512)

# 左、上、右、下。这个矩形就是“指定区域”。
REGION = (72, 392, 440, 466)


def create_demo_image() -> Image.Image:
    """生成自有测试图，避免示例依赖或处理任何外部素材。"""
    image = Image.new("RGB", IMAGE_SIZE, "#d9edf7")
    draw = ImageDraw.Draw(image)

    # 画出一些简单背景纹理，让模型有可参考的上下文。
    for y in range(0, IMAGE_SIZE[1], 24):
        color = "#c5e1ef" if (y // 24) % 2 == 0 else "#d5ebf5"
        draw.rectangle((0, y, IMAGE_SIZE[0], y + 12), fill=color)

    draw.rounded_rectangle((48, 360, 464, 486), radius=18, fill="#87b9d1")
    draw.text((112, 414), "DEMO TEXT", fill="#17394d", stroke_width=1)
    return image


def create_rect_mask(size: tuple[int, int], region: tuple[int, int, int, int]) -> Image.Image:
    """黑色保留，白色交给模型修复。"""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle(region, fill=255)
    return mask


def main() -> None:
    WORK_DIR.mkdir(exist_ok=True)
    image = create_demo_image()
    mask = create_rect_mask(image.size, REGION)

    image.save(WORK_DIR / "input.png")
    mask.save(WORK_DIR / "mask.png")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"Loading {MODEL_ID} on {device} ({dtype}) ...")

    # 首次执行会下载 checkpoint；以后会从本机 Hugging Face 缓存读取。
    pipeline = AutoPipelineForInpainting.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
    ).to(device)

    generator = torch.Generator(device=device).manual_seed(42)
    result = pipeline(
        prompt="a clean pale blue panel with subtle horizontal texture",
        image=image,
        mask_image=mask,
        num_inference_steps=30,
        generator=generator,
    ).images[0]

    output_path = WORK_DIR / "output.png"
    result.save(output_path)
    print(f"Saved input : {WORK_DIR / 'input.png'}")
    print(f"Saved mask  : {WORK_DIR / 'mask.png'}")
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
```

正常情况下，终端最后会打印三条保存路径，目录结构如下：

```text
inpaint-output/
  input.png   # 带 DEMO TEXT 的测试图
  mask.png    # 只有指定矩形为白色的遮罩
  output.png  # 模型生成的修复结果
```

打开 `input.png` 与 `mask.png` 对照，能确认问题是否出在“区域选择”；再打开 `output.png`，才是在观察模型补全质量。这三个文件必须分开保存，否则出了问题时，人们往往会毫无根据地责怪模型——这实在有些不讲道理。

### 改成自己的授权图片

确认最小实例能运行后，只需把 `create_demo_image()` 的返回值替换为本地文件，并保留生成 mask 的逻辑：

```python
image = Image.open("my-authorized-image.png").convert("RGB")
REGION = (80, 400, 720, 475)
mask = create_rect_mask(image.size, REGION)
```

矩形坐标必须落在图片范围内，且 `mask.size` 必须与 `image.size` 完全一致。若前端上传的是矩形 `(x, y, width, height)`，先转换为 `(x, y, x + width, y + height)`；这类坐标格式混淆比模型本身更常见，也更无聊。

## 如何把这个脚本接到前后端

最小脚本只负责验证模型。变成服务时，不要把 `from_pretrained()` 放进每次请求：模型应在进程启动阶段加载一次，之后每个请求只传图片、坐标和提示词。

```text
前端
  -> 上传自有/已授权图片，并框选矩形
  -> 后端校验文件类型、像素数、权限和坐标范围
  -> 后端生成与原图同尺寸的 mask
  -> 已常驻内存的 inpainting pipeline 推理
  -> 保存原图、mask、输出图和模型版本
  -> 返回处理结果或异步任务状态
```

对于单张小图，同步返回即可；对于高分辨率图片、批量任务或视频，应创建异步任务，并限制并发和总像素数。模型推理是资源密集操作，不能因为接口收到了一个矩形就无限制地接收 8K 图片。模型加载、缓存和服务进程职责的边界可参见[模型文件、PaddleOCR 与重排序部署](06-模型文件、PaddleOCR与重排序部署.md)。

## 常见问题与排查

| 现象 | 常见原因 | 先做什么 |
| ---- | -------- | -------- |
| 第一次运行很久 | 正在下载并加载模型，或 CPU 推理 | 查看网络、磁盘空间和 `device` 输出；GPU 更适合此类模型 |
| `CUDA out of memory` | 图片、模型或推理步数超过显存预算 | 降低分辨率和步数；不要盲目提高并发 |
| 字边缘仍然残留 | mask 太贴着字符，没覆盖描边/阴影 | 给矩形扩大少量边距，再重新生成 mask |
| 补全区域很假 | 背景复杂、mask 太大或提示词不描述背景 | 缩小 mask，写明背景内容；必要时改用原工程重导出 |
| 关键细节被改坏 | 模型只能生成近似内容 | 不用修复图替代原始证据，保留原图和 mask |
| 每次启动都下载 | 缓存目录没有保留，或模型版本不固定 | 在受控环境预下载模型，并挂载/交付本地模型目录 |

## 小结

- 指定区域修复的关键不是“让模型知道哪里有文字”，而是用与原图同尺寸的 mask 明确告诉模型哪里可以改；黑色保留，白色修复。
- Inpainting 生成的是合理的画面近似，不会恢复被覆盖区域的真实历史像素；对关键数据、复杂人物和原始文字必须谨慎。
- 最小 Python 实例已经涵盖模型下载、原图生成、矩形 mask、GPU/CPU 选择、推理和输出保存。跑通它后，再把输入图片和矩形坐标替换为前端传来的已授权素材即可。
