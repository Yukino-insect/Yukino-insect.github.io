+++
date = '2026-10-02T09:30:00+08:00'
draft = false
title = '文档预处理：PDF、Office、页图与可追溯结果'
+++

OCR 的输入不是“一个文件路径”这么简单。用户上传的文件可能是带文字层的 PDF、扫描 PDF、DOCX、XLSX、PPTX，甚至是扩展名伪装过的二进制。若每种格式都直接交给同一个 OCR 函数，结果往往是空白、顺序混乱、页码错位或无法复现。本章建立一条通用输入管道：验证文件，尽量提取原生文字，需要时转 PDF、渲染页面，再把每一次转换留下的证据组织起来。

## 为什么要把格式归一化为 PDF

PDF 并不总是最佳存储格式，却是文档处理中的良好中间层：它有稳定页面边界，可以保留部分文字层，能渲染为页图，也便于让人工核验。DOCX 的浮动元素、Excel 的打印区域和 PPT 的画布，在不同软件版本上渲染可能不同；转换为 PDF 后，至少可以固定“本次处理看到的页面”。

归一化不等于丢弃原件。原始 Office 文件可能有可编辑表格和元数据，PDF 是处理派生物。两者都要保存并关联。

```text
原始上传文件
  -> 类型验证、SHA-256、反病毒/大小限制
  -> 原生文本提取（若存在文字层）
  -> Office 转 PDF（若需要）
  -> PDF 按页渲染为图片（若需 OCR）
  -> 页级 OCR / 版面结果
  -> manifest：把所有文件和处理版本串起来
```

## 第一步：不要相信扩展名

上传名 `report.pdf` 只能用于展示，不应决定解析器。至少检查 MIME 类型、文件头（magic bytes）和大小；还要限制解压缩炸弹、嵌套压缩包和异常页数。

Python 的 `mimetypes` 只根据扩展名猜测，不能单独作为安全判断。下面示例演示最小的 PDF 头检查：

```python
from pathlib import Path

def is_probably_pdf(path: Path) -> bool:
    return path.read_bytes()[:5] == b"%PDF-"

path = Path("uploads/example.pdf")
if not is_probably_pdf(path):
    raise ValueError("文件名为 PDF，但文件头不是 PDF")
```

预期：真实 PDF 通过，改名后的普通文本失败。生产环境还应使用成熟的内容检测和恶意文件扫描；示例的作用是说明扩展名不能被当作事实。

## 第二步：优先利用 PDF 已有文字层

使用命令行可快速诊断：

```powershell
pdfinfo .\samples\report.pdf
pdftotext .\samples\report.pdf - | Select-Object -First 20
```

若能得到连贯文本，先保留它。文字层提取速度快，字符错误少，并且可能保留字体和坐标。若输出为空、只有零星字符或阅读顺序异常，再考虑渲染页图并 OCR。现实中常见混合 PDF：正文有文字层，扫描附件没有；判断应按页做，而非整个文件只选一条路径。

用 PyMuPDF 查看每页是否有可提取文本：

```python
import fitz  # pymupdf

doc = fitz.open("samples/report.pdf")
for index, page in enumerate(doc):
    text = page.get_text("text").strip()
    print(f"page={index + 1}, chars={len(text)}")
```

预期每页输出字符数。字符数为零不必然说明是扫描件，但它是需要进一步检查的信号。将页数、字符数和选择的处理路径写入 manifest，后续才能解释为什么第 7 页走了 OCR。

## 第三步：Office 转 PDF

在 Linux 服务器或自动化环境中，LibreOffice 的无头模式是常见选择：

```bash
mkdir -p work/pdf
libreoffice --headless --convert-to pdf --outdir work/pdf uploads/sample.docx
```

预期在 `work/pdf` 出现同名 PDF。转换命令返回成功并不保证版式完全正确，因此下一步必须检查页数并抽看渲染图。对于 Excel，还应明确打印区域、分页、缩放和隐藏工作表；“屏幕上看起来有十列”不表示转换后的 PDF 仍有十列。

转换在隔离的临时目录内进行，设置时间、内存和文件数上限。Office 文档不是可信代码，宏、嵌入对象和畸形文件都可能使转换器挂起或消耗异常资源。转换失败应返回清晰状态，而不是将空 PDF 当成功结果。

## 第四步：用合适 DPI 渲染页面

**DPI（dots per inch）**决定渲染页面的像素密度。DPI 太低，细字没有足够像素可识别；太高，图片、内存和处理时间急剧膨胀。先从 200 或 300 DPI 开始，用你的样本测试，而不是相信一个放之四海皆准的数字。

```python
from pathlib import Path
import fitz

pdf = fitz.open("work/pdf/sample.pdf")
out_dir = Path("work/pages")
out_dir.mkdir(parents=True, exist_ok=True)

dpi = 200
scale = dpi / 72  # PDF 默认坐标单位对应 72 DPI
matrix = fitz.Matrix(scale, scale)

for page_no, page in enumerate(pdf, start=1):
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    target = out_dir / f"page-{page_no:04d}.png"
    pix.save(target)
    print(target, pix.width, pix.height)
```

预期生成 `page-0001.png` 这类有固定零填充编号的文件。固定命名不是洁癖：它使页顺序在文件系统、对象存储和批处理里保持稳定。若一页 A4 在 300 DPI 下约为 2480×3508 像素，RGB 未压缩图约占 25 MiB；并发处理十页时，内存预算必须包含这些中间对象。

## 把结果设计成可追溯资产

“最终文本.txt”无法回答很多关键问题：第一个字段来自第几页？原件后来是否被替换？这次为何比上次少了一页？建议为一次上传建立独立目录：

```text
jobs/<job-id>/
  original/source.docx
  normalized/source.pdf
  pages/page-0001.png
  pages/page-0002.png
  results/page-0001.json
  results/page-0002.json
  manifest.json
```

`manifest.json` 记录处理事实，而非业务猜测：

```json
{
  "job_id": "8f4b2e91",
  "source_name": "sample.docx",
  "source_sha256": "<64-hex-digest>",
  "created_at": "2026-10-02T01:30:00Z",
  "pipeline": {"converter": "libreoffice", "renderer_dpi": 200, "ocr_model": "chosen-model@version"},
  "pages": [
    {"number": 1, "image": "pages/page-0001.png", "result": "results/page-0001.json", "mode": "ocr"}
  ]
}
```

哈希应由流式读取计算，避免大文件一次占满内存：

```python
import hashlib

def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()
```

预期：同一字节内容总是得到同一哈希；内容改动一字节，哈希完全变化。它可用于去重和审计，但不是访问控制机制。

## 处理路径如何选择

| 页面条件 | 首选路径 | 为什么 |
| --- | --- | --- |
| 文字层完整 | 提取文字与坐标 | 快、准确、成本低 |
| 无文字层的扫描页 | 渲染后 OCR | 像素中才有内容 |
| 文本层乱码或顺序错 | OCR 或混合策略 | 视觉顺序可能更可信 |
| Word/Excel/PPT | 转 PDF 后按页检查 | 固化输出页面 |
| 表格、图文混排 | OCR + 版面/表格管线 | 仅文本不足以恢复结构 |

不要因为“统一”而强迫所有 PDF OCR。正确的统一是统一输出契约和来源记录，不是统一把所有内容重新识别一遍。

## 常见故障与排查

### 页面是空白或裁切不全

先打开渲染后的 PNG，而非先怀疑 OCR。检查 PDF 是否加密、转换是否成功、DPI 是否合理、Excel 打印区域是否设置。原始页图错误时，后续模型不可能产生正确结果。

### 页码错位

通常来自从 0 开始的程序索引与面向用户的 1 开始页码混用。内部可以使用零基索引，但输出和 manifest 必须明确 `number: 1` 对应用户看到的第一页。

### 临时目录不断增长

成功与失败任务都要有清理策略。不要在任务结束立刻删除用户需要核验的证据；应区分短期工作目录、受保留策略控制的结果目录和长期归档原件。

## 小结

- 先检测输入真实类型，并优先提取已有文字层。
- Office 转 PDF 的意义是固定页面，不是替代原件。
- DPI 是准确率、耗时和内存的共同杠杆，应通过样本验证。
- 原件、派生 PDF、页图、页级结果和 manifest 共同构成可追溯结果；只有最终文本远远不够。
