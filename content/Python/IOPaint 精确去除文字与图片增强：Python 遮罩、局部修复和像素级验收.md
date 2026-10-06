+++
date = '2026-10-03T22:25:00+08:00'
draft = false
title = 'IOPaint 精确去除文字与图片增强：Python 遮罩、局部修复和像素级验收'
+++

图片上的文字、页码、日期标记或自己后期添加的说明，往往只占很小一块区域。真正容易出问题的并不是“能否让模型运行”，而是遮罩稍大一点便会碰到发丝、衣服描边或阴影；稍小一点又会留下残笔。对于动漫插画和留白较多的海报，这类误差尤其显眼。

本文以当前的 [IOPaint](https://github.com/Sanster/IOPaint) 项目为基础，整理一套可复现的工作流：**先分析像素位置，再由 Python 精确生成遮罩，调用 IOPaint 的修复或超分能力，最后用程序验证修改范围**。它适用于你有权编辑的图片；应尊重作者署名、授权协议和平台规则，不要把技术手段当成绕过权利边界的借口。

核心结论很简单：AI 负责推断遮罩内应该长什么样，Python 负责严格规定“它只能改哪里”。两者各做自己擅长的部分，结果才可靠。

## 一、先理解任务：修复、遮罩与增强并不是一回事

在开始写脚本前，先把几个概念分开。它们经常被混为一谈，随后就有人把整张图交给模型，希望它“顺便”保持细节不变——这显然不现实。

| 目标 | 输入 | 输出 | 关键风险 |
| --- | --- | --- | --- |
| 局部去文字 | 原图 + 遮罩 | 同尺寸修复图 | 遮罩碰到主体、文字漏选 |
| 命令行批处理 | 图片目录 + 同名遮罩目录 | 每张图的修复结果 | 文件对应关系、遮罩尺寸 |
| 图片增强 | 原图 | 更大尺寸的超分图 | 细节是模型推断，不是原始像素复原 |
| WebUI 手工修复 | 原图 + 鼠标涂抹 | 交互式结果 | 细小文字的涂抹边界不稳定 |

这里的“遮罩”是一张与原图**宽高完全相同**的单通道图：白色（像素值 `255`）表示允许修复的区域，黑色（`0`）表示必须保留的区域。可以把它理解为一份修改权限清单。

```text
原始图像 ─┐
          ├─> IOPaint 修复模型 ─> 候选修复结果
精确遮罩 ─┘                         │
                                    ├─> 只取遮罩内像素
原始图像 ────────────────────────────┘
                                             │
                                             ▼
                                      最终输出 + 像素级验收
```

最后“只取遮罩内像素”这一步很重要。某些模型或图像处理链路可能对整幅图重新编码或产生极小差异；把候选结果仅合并到遮罩区域，就可以保证遮罩外的解码后像素不变。

## 二、准备当前项目环境

以下命令以 Windows PowerShell、项目位于 [IOPaint](https://github.com/Sanster/IOPaint)。CPU 可以完成小面积修复，只是速度较慢；如果已经安装适配的 CUDA 版 PyTorch，可将 `cpu` 换成 `cuda`。

```powershell
cd D:\IOPaint
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

想先通过界面验证模型和手工遮罩，可以启动 WebUI：

```powershell
iopaint start --model=anime-lama --device=cpu --port=8080 --inbrowser
```

浏览器会打开 `http://127.0.0.1:8080/`。对动漫插画，`anime-lama` 是很合适的起点；照片或一般场景则可先尝试 `lama`。首次使用某个模型时，IOPaint 会下载权重。若模型已经缓存在本机，可加 `--local-files-only` 防止运行时意外联网。

不过，细小数字和边缘文字往往不适合完全依赖鼠标涂抹。手工界面适合探索，**确定坐标后的可重复任务更适合脚本**。

## 三、标准工作流：从观察到验收

推荐把一次处理拆为六步。

1. **保留原文件**：输出使用新文件名，例如追加 `_text_removed.png`；不要覆盖输入图。
2. **确定坐标**：用图像查看器、OpenCV 或 Pillow 找出文字的像素范围，不要凭缩略图猜。
3. **先做最小遮罩**：优先覆盖文字笔画本身以及很窄的边缘余量。
4. **调用修复模型**：对动漫图可使用 `AnimeLaMa`，对一般图可改为 `LaMa`。
5. **只合并遮罩内部的生成像素**：用原图保留遮罩外区域。
6. **做两类验收**：放大检查视觉效果，并在程序中断言遮罩外像素逐字节一致。

遮罩不应该默认画成一个大矩形。矩形当然很快，但当数字靠近鞋边、发梢或边框时，它会把不该修的内容一起交给模型。一个实用的准则是：**文字位于纯色留白时，可用小矩形；文字紧贴主体时，应选择文字的连通区域或手工多边形。**

## 四、先用 Python 定位文字，不要猜坐标

Pillow 很适合读取图像尺寸。下面脚本只做检查，不会写文件：

```python
from pathlib import Path

from PIL import Image


image_path = Path(r"C:\Users\hanjie\Pictures\source.png")
with Image.open(image_path) as image:
    print(f"size: {image.width} x {image.height}")
    print(f"mode: {image.mode}")
```

如果文字是深色、背景足够浅，可以在一个已知的小窗口内用阈值找候选区域。下面示例打印深色像素的包围盒；坐标的格式是 `(left, top, right, bottom)`，右边和下边采用 Python 切片的开区间习惯。

```python
from pathlib import Path

import numpy as np
from PIL import Image


image_path = Path(r"C:\Users\hanjie\Pictures\source.png")
left, top, right, bottom = (80, 2600, 180, 2690)

rgb = np.asarray(Image.open(image_path).convert("RGB"))
window = rgb[top:bottom, left:right]
dark = np.any(window < 245, axis=2)

ys, xs = np.where(dark)
if len(xs) == 0:
    raise RuntimeError("窗口内没有检测到深色像素，请检查坐标或阈值。")

print(
    "candidate bbox:",
    (left + xs.min(), top + ys.min(), left + xs.max() + 1, top + ys.max() + 1),
)
```

这里的阈值 `245` 并不是通用真理。JPEG 压缩、纸张纹理、渐变背景都会影响它。正确做法是先截取小窗口，再通过打印结果或保存放大预览来调整阈值和坐标，而不是对整幅图盲目二值化。

## 五、用 IOPaint 的 Anime LaMa 做精确局部修复

下面是一份可以直接放在项目根目录运行的脚本。它使用当前项目中已经安装的依赖：`opencv-python`、`numpy` 和 IOPaint。脚本会：

- 读取输入图；
- 构造一个小矩形遮罩；
- 调用 `AnimeLaMa`；
- 仅把遮罩内的修复像素写回原图副本；
- 导出新的 PNG，不修改原图。

文件名可以命名为 `remove_text_rect.py`：

```python
from __future__ import annotations

import sys
import types
from pathlib import Path

import cv2
import numpy as np


ROOT_DIR = Path(__file__).resolve().parent
SOURCE = Path(r"C:\Users\hanjie\Pictures\source.png")
DESTINATION = ROOT_DIR / "output" / "source_text_removed.png"


def load_anime_lama():
    """只导入修复模型，避免启动 WebUI。"""
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    # 当前源码包的 model/__init__.py 会加载许多可选模型。
    # 对于独立脚本，只暴露 model 子包路径即可按需导入 AnimeLaMa。
    model_dir = ROOT_DIR / "iopaint" / "model"
    package = types.ModuleType("iopaint.model")
    package.__path__ = [str(model_dir)]
    sys.modules["iopaint.model"] = package

    from iopaint.model.lama import AnimeLaMa

    return AnimeLaMa


def read_image(path: Path) -> np.ndarray:
    """用 imdecode 读取，兼容 Windows 非 ASCII 路径。"""
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"无法读取图片：{path}")
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"无法编码 PNG：{path}")
    encoded.tofile(str(path))


def main() -> None:
    image_bgr = read_image(SOURCE)
    height, width = image_bgr.shape[:2]

    # 替换为实际文字区域。例：右上角的窄竖排说明。
    left, top, right, bottom = (1584, 0, 1670, 1056)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("遮罩坐标超出图片边界。")

    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.rectangle(mask, (left, top), (right - 1, bottom - 1), 255, thickness=-1)

    AnimeLaMa = load_anime_lama()
    from iopaint.schema import InpaintRequest

    model = AnimeLaMa("cpu")
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    generated_bgr = model(image_rgb, mask, InpaintRequest())

    # 只采用遮罩内生成的内容，遮罩外严格保留原图解码后的像素。
    output_bgr = image_bgr.copy()
    output_bgr[mask > 0] = generated_bgr[mask > 0]
    write_png(DESTINATION, output_bgr)
    print(f"created: {DESTINATION}")


if __name__ == "__main__":
    main()
```

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe .\remove_text_rect.py
```

### 为什么要特别处理 BGR 与 RGB

OpenCV 默认数组通道顺序是 BGR；Pillow 和 IOPaint 的 `AnimeLaMa` 输入约定是 RGB；`AnimeLaMa` 的输出则是 BGR。忽略这一点通常不会让程序报错，却会造成红蓝通道颠倒——这是最不值得保留的那类“成功运行”。

因此，上例中有两次明确转换：

```python
image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
generated_bgr = model(image_rgb, mask, InpaintRequest())
```

第二行没有再做颜色转换，是因为当前 IOPaint 的 LaMa/Anime LaMa 实现返回 BGR 数组。若改用不同模型或不同版本，应先查看该模型的输入输出约定，不要机械复制。

## 六、紧贴主体的文字：用连通域代替大矩形

假设左下角的 “13” 靠近鞋的黑色描边。矩形遮罩很容易覆盖到鞋边；即使模型修得不坏，仍没有必要让它碰到本来正确的内容。

若数字与主体在一个小观察窗口里是分离的深色连通域，可以通过 `connectedComponentsWithStats` 选出数字本身。下面代码延续上一节的读取方式，重点在生成不规则遮罩：

```python
gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

# 只在文字附近的小窗口检测，避免主体其它暗色区域参与判断。
left, top, right, bottom = (80, 2600, 180, 2690)
local_dark = (gray[top:bottom, left:right] < 245).astype(np.uint8)
count, labels, stats, _ = cv2.connectedComponentsWithStats(local_dark, 8)

mask = np.zeros(gray.shape, dtype=np.uint8)
for label in range(1, count):
    x, y, component_width, component_height, area = stats[label]
    absolute_x = x + left
    absolute_y = y + top

    # 以下范围需根据本图实际测得的连通域包围盒调整。
    # 这里挑出数字“1”和“3”，而不是右下方的鞋子轮廓。
    is_target_digit = (
        95 <= absolute_x <= 120
        and 2615 <= absolute_y <= 2625
        and component_height <= 30
        and area > 0
    )
    if is_target_digit:
        mask[top:bottom, left:right][labels == label] = 255
```

接着将这个 `mask` 传给上一节的模型调用代码即可。连通域筛选不是识别文字的万能方案：文字与背景同色、笔画和人物线条相连、背景存在复杂纹理时，自动阈值反而会误选。此时应改为：

- 在 WebUI 用细笔刷手工涂出遮罩；
- 用图像编辑器导出黑白蒙版，再通过 `iopaint run` 批处理；
- 或用 OpenCV 的多边形工具 `cv2.fillPoly()` 按已知轮廓构造遮罩。

所谓“精确”不是一定要自动识别，而是遮罩边界有依据、可检查、可重复。

## 七、批量任务：遮罩图与 `iopaint run`

如果一批图片的文字位置规律一致，最稳妥的方式是为每张图生成同名遮罩，再使用项目命令行批处理。目录结构例如：

```text
D:\images\
  image-001.png
  image-002.png

D:\masks\
  image-001.png
  image-002.png
```

遮罩和图片必须同名且尺寸一致。随后执行：

```powershell
iopaint run --model=anime-lama --device=cpu `
  --image=D:\images `
  --mask=D:\masks `
  --output=D:\outputs
```

调试阶段建议加上 `--concat`：

```powershell
iopaint run --model=anime-lama --device=cpu `
  --image=D:\images `
  --mask=D:\masks `
  --output=D:\outputs `
  --concat
```

它会把原图、遮罩和结果拼在一起，方便快速发现“遮罩错位”“遮罩过大”等问题。批处理并不会自动保证每张图都正确；先用两三张具有代表性的图片验证，再扩展到整个目录，这比批量返工要理性得多。

## 八、图片画质增强：使用 RealESRGAN 插件

去文字是局部替换，超分增强则是整体生成更高分辨率的细节。当前项目内置 `RealESRGAN` 插件；对于动漫插画，可以选 `RealESRGAN_x4plus_anime_6B`。下面的示例将输入放大两倍并导出 PNG：

```python
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from iopaint.plugins.realesrgan import RealESRGANUpscaler
from iopaint.schema import RealESRGANModel, RunPluginRequest


SOURCE = Path(r"C:\Users\hanjie\Pictures\source.png")
DESTINATION = Path(r"D:\IOPaint\output\source_enhanced_2x.png")


def main() -> None:
    image_bgr = cv2.imdecode(np.fromfile(str(SOURCE), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise RuntimeError(f"无法读取图片：{SOURCE}")

    upscaler = RealESRGANUpscaler(
        RealESRGANModel.RealESRGAN_x4plus_anime_6B,
        "cpu",
    )
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    enhanced_rgb = upscaler.gen_image(
        image_rgb,
        RunPluginRequest(name="RealESRGAN", image="unused", scale=2.0),
    )
    enhanced_bgr = cv2.cvtColor(enhanced_rgb, cv2.COLOR_RGB2BGR)

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", enhanced_bgr)
    if not ok:
        raise RuntimeError(f"无法编码 PNG：{DESTINATION}")
    encoded.tofile(str(DESTINATION))
    print(f"created: {DESTINATION}")


if __name__ == "__main__":
    main()
```

超分后的细节应被理解为模型的合理推断，而非恢复出了原图中不存在的真实信息。尤其要检查：

- 人物五官和手部；
- 线稿边缘、格纹、蕾丝等高频图案；
- 原图里本来就有的文字；
- 大面积纯色与渐变是否产生不自然的颗粒。

如果目标只是清除一个角落文字，不要顺手对整图超分。先做局部修复，再按实际用途决定是否增强；两件事的风险和验收标准不同。

## 九、验收不是肉眼扫一眼：做像素级边界检查

修复完成后，至少应验证三件事：输出尺寸正确、遮罩外没有改变、遮罩内部不再包含目标文字。下面的脚本验证前两项，并统计遮罩区域的颜色范围：

```python
from pathlib import Path

import cv2
import numpy as np


before_path = Path(r"D:\IOPaint\output\source_before.png")
after_path = Path(r"D:\IOPaint\output\source_text_removed.png")
left, top, right, bottom = (1584, 0, 1670, 1056)

before = cv2.imdecode(np.fromfile(str(before_path), dtype=np.uint8), cv2.IMREAD_COLOR)
after = cv2.imdecode(np.fromfile(str(after_path), dtype=np.uint8), cv2.IMREAD_COLOR)
if before is None or after is None:
    raise RuntimeError("无法读取待校验图片。")
if before.shape != after.shape:
    raise RuntimeError(f"尺寸不一致：{before.shape} != {after.shape}")

mask = np.zeros(before.shape[:2], dtype=np.uint8)
mask[top:bottom, left:right] = 1

outside_is_identical = np.array_equal(before[mask == 0], after[mask == 0])
if not outside_is_identical:
    raise AssertionError("遮罩外存在像素变化，请检查处理流程。")

patch = after[top:bottom, left:right]
print("outside mask byte-identical:", outside_is_identical)
print("patch min BGR:", patch.min(axis=(0, 1)).tolist())
print("patch mean BGR:", patch.mean(axis=(0, 1)).round(2).tolist())
```

这里的“逐字节一致”比较的是 OpenCV 解码后的像素数组，而不是 PNG 文件的二进制文件是否相同。文件的元数据、压缩方式都可能不同，真正应关心的是画面像素是否被意外改动。

对于深色小数字，还可在遮罩区域做阈值检测并观察连通域数量。但它只能作为辅助：一段原本就应该存在的深色线条也会被统计为“深色像素”。最终仍要把目标区域放大到 200% 或 400%，检查边缘是否自然、有无残笔。

## 十、常见问题与排查顺序

### 1. 模型下载或加载失败

先确认当前 Python 环境而不是系统 Python：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
.\.venv\Scripts\python.exe -c "import iopaint; print(iopaint.__file__)"
```

首次启动需要下载权重；离线环境应先准备模型缓存，或使用项目的 `--model-dir` 指定模型目录。若只是运行脚本，确保 `ROOT_DIR` 指向 IOPaint 仓库根目录。

### 2. 输出颜色不对

先检查 BGR/RGB 转换。用 OpenCV 读取后传给模型之前需要 `BGR2RGB`；只有确认模型输出为 RGB 时才执行 `RGB2BGR`。不同插件的返回约定并不完全相同。

### 3. 文字去掉了，但附近主体坏了

这是遮罩问题，不是“模型不够聪明”。缩小遮罩、使用连通域或多边形遮罩，并从原图重新运行。不要在已经被错误修复的输出上反复修补；误差会累积，且很难追溯源头。

### 4. 文字仍有残留

先放大原图确认残笔到底在不在遮罩里。若不在，微调遮罩边缘后从原图重跑；若已经在遮罩内但模型没有补干净，可以把遮罩向纯背景方向扩大 1 至 3 个像素。扩大前必须确认不会触及主体。

### 5. 超分后的图片“更锐”，但不像原图

这通常不是程序错误。降低放大倍率、换更保守的模型，或仅将增强结果用于展示尺寸较小的场景。任何超分模型都在生成细节，不能替代高分辨率原始素材。

## 十一、把流程固化成可复用的工具

一次性处理可以写几行脚本；重复任务则应把路径、遮罩坐标、模型和输出命名做成参数或配置。最低限度也应保存下面这些信息：

- 输入文件的绝对路径和尺寸；
- 遮罩的构造方式与坐标；
- 使用的模型、设备和 IOPaint 版本；
- 输出文件路径；
- 验收结果，例如“遮罩外像素一致”。

这样下次遇到相同版式时，不需要重新凭记忆涂遮罩；遇到结果异常时，也能确定问题来自输入、遮罩、模型还是保存流程。

## 十二、总结

使用 IOPaint 处理文字和增强图片时，最可靠的顺序是：

- 用 WebUI 快速探索模型和遮罩范围；
- 用 Python 精确、可重复地生成小范围遮罩；
- 对动漫图优先尝试 `AnimeLaMa`，对超分使用适合图像类型的 RealESRGAN 模型；
- 把模型结果只合并回遮罩区域，保护其余像素；
- 用放大预览加像素级断言验收，而不是只看缩略图；
- 全程输出新文件，保留原图和每个可追溯版本。

工具并不会自动让修图变得精确。精确来自明确的修改边界、谨慎的模型调用，以及最后那一步看似多余、实际上最能避免返工的验证。
