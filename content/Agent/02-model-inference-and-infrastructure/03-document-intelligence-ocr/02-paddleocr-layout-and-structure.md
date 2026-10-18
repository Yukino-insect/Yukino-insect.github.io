+++
date = '2026-10-02T09:20:00+08:00'
draft = false
title = 'PaddleOCR 实战：从文字行到版面、表格与复杂文档'
+++

上一章得到的是一组“文字框 + 文本”。对收据或截图，这通常足够；面对双栏报告、表格、页眉页脚和插图时，把所有文字按坐标拼起来会得到语义混乱的结果。本章从这个真实限制出发，介绍 PaddleOCR 的能力层次：先用普通 OCR 获得可靠文字行，再按需要引入方向、版面和表格解析。模型越复杂，并不代表每个文件都该走最重的路径。

## 先区分三个层次

### 文字行 OCR

输入一张图，输出文字行、多边形和置信度。它适合票据、屏幕截图、标签、单栏通知等结构简单的页面。你已经在上一章做过这个实验。

### 版面分析

**版面分析（layout analysis）**把页面划分为标题、正文、表格、图片、页眉、页脚、公式等区域。它解决的是“这块是什么、先读哪块”，而不是把字符读得更清楚。对于双栏文档，它会先识别两个正文区域，再分别排序。

### 表格结构识别

表格 OCR 至少有两件事：认出每个单元格的文字，以及恢复行列关系。单纯识别到 `名称`、`数量`、`金额` 并不能说明哪一个值属于哪一列。带边框表格较容易；无线表、合并单元格、跨页表和手写表格都更难，必须保留人工复核出口。

## 安装与版本检查

本章默认已完成上一章环境准备。先检查实际安装版本：

```powershell
python -m pip show paddleocr paddlepaddle
python -c "from paddleocr import PaddleOCR; print('import ok')"
```

PaddleOCR 的大版本在管线对象、参数名和结果结构上存在变化。下面的原则比死记某一行 API 更可靠：**用官方示例创建管线，打印一页原始结果，适配后再定义自己的稳定 JSON 契约**。不要将第三方博客中旧版 `ocr.ocr(...)` 的输出结构直接假定为新版接口的结构。

## 实验一：只做文本识别，并可视化结果

在 `samples/receipt.png` 准备一张清晰票据或自制表格截图。执行上一章的最小脚本后，为每个多边形画线。这样你能直接看出是“没有框”还是“框内文字不对”。

```python
import json
from pathlib import Path

import cv2
import numpy as np

items = json.loads(Path("out/receipt.ocr.json").read_text(encoding="utf-8"))
canvas = cv2.imread("samples/receipt.png")

for item in items:
    points = np.array(item["polygon"], dtype=np.int32)
    cv2.polylines(canvas, [points], True, (0, 180, 0), 2)
    x, y = points[0]
    cv2.putText(canvas, f'{item["score"]:.2f}', (int(x), int(y) - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

Path("out").mkdir(exist_ok=True)
cv2.imwrite("out/receipt-boxes.png", canvas)
```

预期生成 `out/receipt-boxes.png`：每一行文字周围有绿色框。中文在 OpenCV 默认字体中可能显示成方块，这不影响检查框的位置。若框覆盖了表格线或漏掉细字，先回到图像质量、DPI 和方向，而不是立刻上视觉语言模型。

## 实验二：让页面具有阅读顺序

一份可消费的页面结果不应只是 `items` 数组。定义一个通用、与厂商无关的中间结构：

```json
{
  "page": 1,
  "width": 1654,
  "height": 2339,
  "blocks": [
    {
      "type": "paragraph",
      "bbox": [80, 120, 760, 420],
      "order": 3,
      "text": "第一段内容……",
      "lines": []
    }
  ]
}
```

`bbox` 用 `[left, top, right, bottom]` 表示坐标；`order` 是阅读顺序；`type` 是 `title`、`paragraph`、`table`、`figure` 等类别。即使第一版没有版面模型，也可以先将同一 `y` 区间内、水平相邻的行合并为段落。重要的是明确这只是启发式规则，在双栏和浮动元素前会失败。

一个可解释的简化排序函数如下：

```python
def reading_order(lines):
    """仅适用于单栏页面；多栏应先由版面模型分区。"""
    return sorted(lines, key=lambda line: (min(p[1] for p in line["polygon"]),
                                           min(p[0] for p in line["polygon"])))
```

预期：单栏通知会按从上到下、从左到右排列。若把双栏论文拿来测试，中间会发生“左栏第一段、右栏第一段、左栏第二段”的交错，这正是该规则不适用的证据。

## 使用文档解析管线

PaddleOCR 生态中，文档解析管线会组合方向校正、文本识别、版面分析与表格能力。不同发布版本可能称为 PP-Structure、PP-StructureV3 或由 PaddleX 管线提供。选择时先问三个问题：

1. 页面是否真的有多栏、表格、公式或图文混排？
2. 输出需要的是可读文本，还是要恢复 HTML/Excel 单元格？
3. 允许的延迟、显存和人工复核成本是多少？

一个版本无关的调用框架可以写成：

```python
from pathlib import Path

# 根据你安装版本的官方示例导入并初始化 pipeline。
pipeline = create_document_pipeline(
    enable_orientation=True,
    enable_layout=True,
    enable_table=True,
)

for page_result in pipeline.predict("samples/report.pdf"):
    normalized = normalize_to_our_schema(page_result)
    save_page(normalized, Path("out"))
```

这里故意没有伪造一个所有版本都能复制运行的 `create_document_pipeline`。先复制**你安装版本官方文档中实际可运行的初始化代码**，再实现 `normalize_to_our_schema`。与其得到一段看似权威、运行即报错的神秘代码，不如掌握这条适配方法；这才是维护第三方模型依赖的基本功。

## 表格：先定义你要的正确结果

假设输入表格是：

| 商品 | 数量 | 金额 |
| --- | ---: | ---: |
| 铅笔 | 2 | 6.00 |
| 本子 | 1 | 8.00 |

你希望输出的不是一串 `铅笔 2 6.00 本子 1 8.00`，而是：

```json
{
  "headers": ["商品", "数量", "金额"],
  "rows": [["铅笔", "2", "6.00"], ["本子", "1", "8.00"]],
  "source": {"page": 1, "bbox": [70, 220, 880, 600]}
}
```

这使验证成为可能：每一行是否有三列、金额能否转为十进制、总金额是否等于明细和。结构模型输出 HTML 时，也应保存原始 HTML，再转换为上述内部格式；转换失败时保留原证据，而不是静默丢弃表格。

### 表格的高频失败

- **合并单元格**：`项目` 跨两列时，模型可能复制、漏掉或错归属标题。
- **无线表**：没有线不代表不是表，但行列边界更依赖对齐和语义。
- **跨页表**：第二页重复表头或没有表头；不要仅凭相邻页面自动拼接。
- **小数与日期**：`1,234.50`、`2026-01-02` 的格式必须按业务规则校验，OCR 不知道你的地区规则。

## 什么时候需要视觉语言模型

视觉语言模型（VLM）可根据页面图像和提示词生成描述或结构化结果，对复杂版面有帮助。但它可能编造未出现的内容，输出也更慢、更贵、难以逐字复现。将它用于“低置信度页面的候选解释”或人工辅助较合理；用它替代所有确定性表格解析，则是在用昂贵的不确定性掩盖数据质量问题。

如果使用 VLM，输入和输出仍应遵循同一证据契约：保存页面图、提示词版本、模型版本、原始响应、字段坐标（若支持）和人工确认状态。

## 排错清单

| 症状 | 先检查什么 | 不要急着做什么 |
| --- | --- | --- |
| 模型初始化很慢 | 首次权重下载、CPU/GPU、缓存目录 | 每次请求重新创建模型 |
| 双栏顺序错 | 是否启用版面分区、页眉页脚 | 仅把 `y` 排序写得更复杂 |
| 表格列数不对 | 表格截图、单元格框、合并单元格 | 直接把文本按空格 `split` |
| 公式被读成文字 | 是否需要公式能力、应用场景 | 把公式结果当数值计算依据 |
| 内存不断升高 | 图片尺寸、批量大小、对象释放 | 无限制提高并发 |

## 小结

- 普通 OCR、版面分析和表格结构识别解决不同层次的问题。
- 可视化检测框是定位问题最快的工具。
- 先设计可验证的表格输出，再选择模型；只有文字不等于恢复了表格。
- PaddleOCR 的具体 API 会演进，稳定的做法是适配到自己定义的页级 JSON，而不是绑死某个返回格式。
