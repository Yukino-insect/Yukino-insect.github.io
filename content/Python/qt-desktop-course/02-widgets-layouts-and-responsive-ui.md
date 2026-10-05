+++
date = '2026-10-04T21:02:00+08:00'
draft = false
title = 'PySide6 Widgets、布局与响应式桌面界面：不要用坐标堆窗口'
+++
桌面界面最常见的早期写法是：给每个控件设置 `move(x, y)` 和固定宽高。它在自己的显示器、自己的字体大小、自己的语言文本下似乎能工作；一旦窗口缩放、DPI 改变、路径变长、切换语言或用户改变系统字体，界面就会立刻失去秩序。

Qt 的布局系统不是“自动排版的便利工具”，而是一套尺寸协商机制。要写出在非全屏、不同分辨率下仍合理的页面，必须理解控件、layout、size hint、minimum size、size policy 与 splitter 分别在做什么。

## 一、`QWidget`、控件和组合

Qt Widgets 的基本单位是 `QWidget`。常见控件包括：

| 控件 | 职责 |
| --- | --- |
| `QLabel` | 显示文本或图片。 |
| `QPushButton` | 触发一次操作。 |
| `QLineEdit` | 单行文本输入。 |
| `QTextEdit` | 多行富文本或日志显示。 |
| `QComboBox` | 在有限选项中选择。 |
| `QSlider` / `QProgressBar` | 连续值、进度。 |
| `QTableView` / `QListView` | 基于模型展示大量数据。 |
| `QScrollArea` | 当内容高度超出可用空间时提供滚动。 |

页面本身通常也是 `QWidget`，通过组合子控件形成结构。Qt 的设计强调组合：先把一个区域封装成 widget，再将它加入更大的布局，而不是为每种页面形状写一套复杂继承树。

### Qt Widgets 与 QML / Qt Quick

Qt 并不只有 Widgets。它大致提供两种常见 UI 路线：

| 路线 | 特点 | 适合场景 |
| --- | --- | --- |
| Qt Widgets | 命令式创建控件、成熟的布局和传统桌面控件生态 | 工具软件、表格/表单、桌面管理软件、既有 Widgets 项目。 |
| QML / Qt Quick | 声明式描述界面，属性绑定和动画能力更强 | 触控界面、动态视觉效果、嵌入式和现代定制 UI。 |

PySide6 同时支持它们。净绘工坊选择 Widgets，是因为它有大量设置卡、文件选择、表格、日志、复杂预览和成熟的 `qfluentwidgets` 组件；这不是说 QML 较差，而是当前桌面工具的交互结构更适合 Widgets。若项目未来需要高度定制动画、触屏工作流或设计师参与声明式 UI，QML 可以成为独立的展示层选择。

## 二、布局不是坐标：它在协商空间

最常用布局：

```text
QVBoxLayout  垂直排列
QHBoxLayout  水平排列
QGridLayout  网格排列
QFormLayout  标签/字段表单
QStackedLayout / QStackedWidget  多页面切换
```

示例：

```python
layout = QVBoxLayout(self)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(10)

layout.addWidget(title)
layout.addWidget(preview, 1)
layout.addLayout(button_row)
```

`addWidget(preview, 1)` 中的 stretch 表示在额外空间存在时，预览更愿意获得空间。布局会综合：

- 控件的 `sizeHint()`；
- `minimumSize` / `maximumSize`；
- `QSizePolicy`；
- stretch 因子；
- 父容器可用空间；
- 间距和外边距。

## 三、`QSizePolicy`：控件希望怎样长大或缩小

常见策略：

| 策略 | 含义 |
| --- | --- |
| `Fixed` | 尽量保持固定尺寸。 |
| `Minimum` | 不低于 `sizeHint`，可以变大。 |
| `Maximum` | 不超过 `sizeHint`，可以变小。 |
| `Preferred` | 理想大小是 `sizeHint`，可缩可扩。 |
| `Expanding` | 愿意尽量吃掉额外空间。 |
| `Ignored` | 布局可忽略 size hint，按空间强制压缩或拉伸。 |

长路径标签通常适合：单行、不换行、水平 `Ignored`，并使用中间省略。这样路径不会把整个设置卡纵向撑开。

```python
label.setWordWrap(False)
label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
label.setToolTip(full_path)
```

然后根据当前可用宽度用 `QFontMetrics.elidedText(..., Qt.ElideMiddle, width)` 生成展示文本。完整路径仍在 tooltip 中，界面只展示可读的关键前缀和后缀。

## 四、何时使用 `QSplitter`

左右都有重要内容时，固定比例布局并不总是合适。`QSplitter` 允许用户拖动分隔线：

```python
splitter = QSplitter(Qt.Horizontal)
splitter.addWidget(preview_card)
splitter.addWidget(option_card)
splitter.setStretchFactor(0, 3)
splitter.setStretchFactor(1, 2)
```

它适合：

- 左边预览、右边参数；
- 文件树、编辑器、属性面板；
- 日志、任务队列、详情区；
- 用户对空间偏好差异较大的工具型软件。

净绘工坊的画质增强页使用 splitter，将预览卡和参数卡拆开。预览区不再强制 `640×420` 的最小尺寸，路径也不再自动换行，因此窗口不是全屏时仍能保持稳定比例。

## 五、图片预览为什么要保存原始 `QPixmap`

如果每次窗口 resize 都从文件重新读取图片，既浪费 I/O，也可能因为路径不存在或输出尚未写完造成闪烁。更合理的是：

1. 读取 OpenCV BGR 图像；
2. 转成 RGB `QImage`；
3. 保存原始 `QPixmap`；
4. 每次预览区变化时，只按当前 label 尺寸重新缩放。

```python
self._preview_source_pixmap = QPixmap.fromImage(qimage)
self.preview.setPixmap(
    self._preview_source_pixmap.scaled(
        self.preview.size(),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
)
```

这体现了一个 UI 原则：**展示尺寸是视图状态，原始内容是数据状态。不要因为视图变了就重新获取数据。**

## 六、`QScrollArea` 与内容高度

当设置页有大量参数时，应让内容在可滚动区域内显示，而不是把窗口最小高度无限增大：

```python
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll.setWidget(content_widget)
```

但不要把所有页面都塞进滚动区。一个只有少量控件的固定页面，过度滚动反而增加操作成本。判断标准是：内容是否天然可能超过窗口可用高度，而不是“加滚动条看起来更安全”。

## 七、布局常见失败模式

### 1. 长文本自动换行撑高页面

修复：路径、ID、哈希等机器文本用单行省略和 tooltip；说明性文字才允许换行。

### 2. 为了好看设置过大最小尺寸

修复：最小尺寸只保证基本可用，不要把开发机器的舒适尺寸当作所有用户的最小尺寸。

### 3. 在 `resizeEvent` 中做重计算

修复：resize 中只重排、重缩放；模型推理、文件读取和网络请求必须离开 UI 线程。

### 4. 将每一个区域都写成绝对坐标

修复：使用 layout、stretch、size policy 和 splitter。绝对坐标只适合特殊画布、图形编辑器或自定义绘制区域。

## 八、与净绘工坊的联系

增强页的修复说明了布局不是“锦上添花”：长文件名曾经让右侧卡片变成数行高度，完成后预览仍保留输入图。现在通过单行中间省略、splitter、保存原始 pixmap、完成后读取输出媒体，界面表现与实际任务状态保持一致。

## 九、可运行练习：一个会正确省略路径的预览面板

下面组件把“原图缓存”和“当前显示尺寸”分开保存。拖动窗口时只重新缩放已经在内存中的 pixmap；改变路径时只更新显示文本，不让长路径破坏布局。

```python
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class MediaPreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_pixmap = QPixmap()
        self._full_path = ""

        self.path_label = QLabel("尚未选择文件")
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.path_label.setWordWrap(False)

        self.preview = QLabel("预览区")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet("background: #202124; color: #d9d9d9;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.path_label)
        layout.addWidget(self.preview, 1)

    def set_media(self, path: str):
        self._full_path = path
        self._source_pixmap = QPixmap(path)
        self.path_label.setToolTip(path)
        self._refresh_path_text()
        self._refresh_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_path_text()
        self._refresh_preview()

    def _refresh_path_text(self):
        if not self._full_path:
            return
        metrics = QFontMetrics(self.path_label.font())
        text = metrics.elidedText(
            self._full_path, Qt.ElideMiddle, self.path_label.width()
        )
        self.path_label.setText(text)

    def _refresh_preview(self):
        if self._source_pixmap.isNull() or self.preview.size().isEmpty():
            return
        self.preview.setPixmap(
            self._source_pixmap.scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
```

`QSizePolicy.Ignored` 是这里的关键之一：它允许布局在水平方向压缩标签，即使标签的 `sizeHint()` 偏大。`QFontMetrics.elidedText()` 根据当前字体和可用像素宽度计算省略文本，不能用 `text[:30]` 代替——中文、英文字母和不同 DPI 下的实际宽度并不相同。`Path` 可用于把显示名与完整路径拆开；本例直接保留完整字符串，以便 tooltip 能准确展示用户选择的路径。

## 十、C++ 底层视角：尺寸协商与隐式共享图像

Widgets 的布局计算在 C++ Qt 内部进行。布局收集子项的 `sizeHint`、最小/最大尺寸、stretch 和 `QSizePolicy`，递归分配父容器给出的几何区域；Python 只是调用这套 C++ API，并不在 Python 层进行逐像素排版。

`QImage` 与 `QPixmap` 还使用了 Qt 的**隐式共享**（copy-on-write）策略：复制包装对象通常先共享底层数据，直到某一方真的修改数据才分离。它能减少一般 UI 传递中的复制，但有两条边界：

- `QPixmap` 绑定窗口系统资源，应只在 GUI 主线程创建和使用；后台解码更适合生成 `QImage` 或纯字节数据，再用信号交给主线程转换为 `QPixmap`；
- 隐式共享不等于跨线程随意读写安全。多个线程若能修改同一份对象，仍须建立明确的所有权和同步。

## 总结

- 用 layout 表达结构，用 size policy 表达伸缩意愿。
- 长路径应省略并保留 tooltip，不应随意换行撑高页面。
- `QSplitter` 适合两个重要区域的可调空间分配。
- 预览应缓存原始 pixmap，resize 时只缩放，不重新读文件。
- `QFontMetrics` 应按当前可用像素宽度省略文本；字符数量不是可靠的界面宽度。
- 响应式桌面界面不是网页专属问题；字体、语言、DPI 和窗口大小同样会改变桌面布局。
