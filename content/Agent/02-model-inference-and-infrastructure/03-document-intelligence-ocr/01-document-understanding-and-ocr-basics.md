+++
date = '2026-10-02T09:10:00+08:00'
draft = false
title = '从一张图片开始理解 OCR：检测、识别、方向与错误'
+++

先不要急着搭服务。OCR 的第一个实验应该小到可以肉眼判断对错：给程序一张清晰、正向、包含几行文字的本地图片，拿回每一行的文本和位置。只有亲手看过“框在哪里、字读成了什么”，后面讨论表格、异步、GPU 才不会沦为术语陈列。

## 本章目标与样本

准备一张名为 `samples/hello.png` 的图片。可以用截图、自己打印后扫描的文字，内容最好含中文、英文和数字，例如：

```text
订单编号: A-20261002
合计: 128.00 元
```

它不需要来自某个业务系统。清晰度比“看起来真实”更重要。运行后你应看到类似输出：

```text
订单编号: A-20261002    score=0.98    box=[[42, 30], [364, 30], [364, 70], [42, 70]]
合计: 128.00 元        score=0.96    box=[[42, 98], [292, 98], [292, 138], [42, 138]]
```

坐标会因图片不同而变化；验收的重点是：每行都有文字、分数和四个顶点，不是逐字符完全一致。

## OCR 不是一个黑盒动作

### 图像如何变成数字

彩色图片由像素组成。一个像素通常有红、绿、蓝三个数值，范围是 0 到 255；灰度图则只保留亮度。OCR 模型并不“看见”汉字，它接收的是一个数值张量，例如宽 1280、高 720 的 RGB 图片可以表示为 `[720, 1280, 3]`。

低分辨率、运动模糊、反光和阴影都会让像素模式变得含糊。人眼能依据上下文猜出“8”，模型却可能在相似像素中选成 `B`。所以 OCR 的上限首先受输入质量限制，而不是某个 API 参数。

### 检测：先找到字在哪里

**文本检测（text detection）**在整张图中寻找文字区域，常以四边形表示：

```json
{
  "polygon": [[42, 30], [364, 30], [364, 70], [42, 70]]
}
```

四边形而非简单矩形，是因为手机拍摄的文字可能倾斜或透视变形。检测失败的现象是整行没有框、两个词粘在同一框，或表格线被误框为文字。

### 识别：再读取框里的内容

**文本识别（text recognition）**将检测框裁切、拉正，输出字符序列及一个置信度。现代识别器会把图像特征映射到字符概率序列，再通过解码得到文本；你不必先懂网络结构，但要记住置信度通常是模型内部概率的汇总，不是“96% 的字符一定正确”。

### 方向与阅读顺序

页面旋转 90 度时，即便检测器找到文字，识别器也可能读出乱码。**方向分类**先判断页面或文字块应旋转多少度。多栏论文还存在阅读顺序问题：视觉上左栏从上到下，再读右栏；简单按 `y` 坐标排序可能把两栏混在一起。它们是文档理解问题，不只是 OCR 问题。

## 跑通最小实验

PaddleOCR 的 API 在大版本间会有少量差异。下面使用常见的 `PaddleOCR` 调用形式；如果你的安装版本提示参数不兼容，先执行 `pip show paddleocr`，再按该版本的官方示例调整，而不要胡乱同时安装多个版本。

创建 `ocr_one_image.py`：

```python
from pathlib import Path

from paddleocr import PaddleOCR

image_path = Path("samples/hello.png")
if not image_path.is_file():
    raise FileNotFoundError(f"找不到样本：{image_path.resolve()}")

ocr = PaddleOCR(lang="ch", use_doc_orientation_classify=True)
result = ocr.predict(str(image_path))

for page in result:
    data = page.json["res"]
    for text, score, box in zip(
        data["rec_texts"], data["rec_scores"], data["rec_polys"]
    ):
        print(f"{text}\tscore={score:.2f}\tbox={box}")
```

运行：

```powershell
python .\ocr_one_image.py
```

第一次运行通常较慢，因为模型权重需要下载并初始化。预期是终端打印若干行文本、分数和坐标。若版本返回的是列表而非 `page.json`，不要为了“让代码过”直接丢弃坐标；打印 `type(result)` 与一条原始结果，确认字段名称后再改取值逻辑。

### 把结果存成可复查文件

控制台输出很快会丢失。保存 JSON，才可以在后续比较不同预处理方案：

```python
import json

output = []
for page in result:
    data = page.json["res"]
    for text, score, box in zip(data["rec_texts"], data["rec_scores"], data["rec_polys"]):
        output.append({"text": text, "score": float(score), "polygon": box})

Path("out").mkdir(exist_ok=True)
Path("out/hello.ocr.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
)
```

预期文件中的每条记录都有 `text`、`score` 和 `polygon`。以后无论做搜索、高亮还是字段提取，都应从这类有来源的记录派生，而不是仅保存拼接后的长字符串。

## 用小实验理解方向和输入质量

将样本复制并旋转 90 度：

```python
from PIL import Image

source = Image.open("samples/hello.png")
source.rotate(90, expand=True).save("samples/hello-rotated.png")
```

分别识别正向和旋转图片。关闭方向分类时，旋转图的漏字或乱码通常增多；打开它，结果应该改善，但耗时也会略增加。**预期不是所有图片都 100% 恢复**：极短文字、印章、竖排和低清照片仍可能判断错误。

再用手机拍一张带阴影的同样文字。你会发现“模型相同，结果却不同”。这正是为什么生产系统要记录输入分辨率、渲染 DPI 和预处理版本。

## 先从简单预处理开始

预处理的目的不是把图“修得好看”，而是让文字笔画与背景更容易区分。最常见的安全尝试是灰度化、轻微降噪和对比度增强：

```python
import cv2

image = cv2.imread("samples/hello-rotated.png")
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
cv2.imwrite("samples/hello-enhanced.png", enhanced)
```

对原图和增强图各运行一次 OCR，并保留两份 JSON。若增强后细小笔画被抹掉、数字反而更差，就回退。自适应二值化、锐化、去噪都不是越重越好；它们会同时放大噪声或删除细节。

## 怎样初步判断错误来自哪里

| 观察到的现象 | 更可能的环节 | 第一项检查 |
| --- | --- | --- |
| 一整行完全没有结果 | 检测 | 图片边缘、分辨率、文字与背景对比 |
| 两列文字合成一条 | 检测或排序 | 检测框可视化、列间距 |
| 框对了但 `0/O`、`8/B` 混淆 | 识别 | 裁切图、语言模型、原图清晰度 |
| 整页乱码 | 方向或语言 | 旋转角度、`lang`、竖排文本 |
| 文本都对但段落顺序乱 | 版面 | 多栏、页眉页脚、坐标排序规则 |

不要根据一个低分就自动删除结果。正确做法是为不同字段定义复核策略：订单号可用正则检查，金额可检查小数格式和合计关系，姓名等开放文本则适合进入人工队列。

## 常见排错

### 模型下载失败或导入失败

先确认网络、磁盘和虚拟环境：

```powershell
python -c "import paddle, paddleocr; print(paddle.__version__)"
python -m pip show paddleocr paddlepaddle
```

公司网络下无法下载模型时，应通过受控制品仓库或预置模型目录解决，不要把下载地址和凭据硬编码进脚本。

### 结果为空

先用一张清晰的 PNG 测试，排除 HEIC、损坏文件和路径编码问题；再检查图片宽高。把只有几十像素高的截图放大并不一定增加信息，但可能使检测器能接受它。

### 结果看似正确却无法追溯

这是设计错误，不是模型错误。至少保存原始文件哈希、页码、坐标、模型版本、处理时间和原始输出；没有这些信息，之后无法重跑或解释差异。

## 小结

- 一次 OCR 包含检测、裁切拉正、识别、方向和排序等多个步骤。
- 文本、坐标、置信度与来源必须一起保存。
- 用正向、旋转和低质量三类小样本做实验，能最快理解模型边界。
- 先定位错误在检测、识别还是版面，再调整输入或参数；盲目换模型通常只会制造新的不确定性。
