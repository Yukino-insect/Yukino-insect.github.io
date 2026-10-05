+++
date = '2026-10-04T21:08:00+08:00'
draft = false
title = '净绘工坊中的 Qt 工程实践：从多页面导航到 OCR、模型与预览回写'
+++
前面几篇建立了 Qt 的通用概念。本篇把这些概念落到净绘工坊：一个 PySide6 桌面应用如何组织内容修复、画质增强、OCR 精确掩膜、模型任务和视频输出。

重点不是逐行解释源码，而是识别每段代码在解决什么问题、位于什么边界，以及今后如何继续改进。

## 一、应用外壳：主窗口只负责装配

`gui.py` 中的 `SubtitleExtractorGUI` 继承 FluentWindow，负责：

- 创建内容修复页、画质增强页和高级设置页；
- 注册导航项；
- 保存窗口位置；
- 关闭时通知 `ProcessManager` 清理子进程；
- 在导入第三方 UI 库时抑制无关推广输出。

它不应负责 OCR、视频帧处理或模型推理。主窗口是 composition root：把对象装配起来，但不承担业务实现。

```text
FluentWindow
├─ HomeInterface          内容修复
├─ EnhanceInterface       画质增强
└─ AdvancedSettingInterface 配置、模型缓存、关于
```

## 二、内容修复页：交互与业务数据分开

`HomeInterface` 负责用户交互：打开媒体、预览帧、画候选 ROI、发起 OCR、确认掩膜、运行/停止任务。

但用户画出的框并不直接等于修复区域。当前链路是：

```text
黄色候选 ROI
    -> 限制 OCR 搜索范围
青色 OcrPolygon
    -> PaddleOCR dt_polys
红色最终 mask
    -> MaskPlan（确认后冻结）
修复引擎
    -> OpenCV / LaMa / Anime-LaMa / Manga
```

这就是“状态分层”的实际例子。若把黄色框直接传给模型，用户无法知道背景会不会被误擦；`MaskPlan` 将 OCR 多边形、手工矩形、扩张像素、细化阈值等变成可序列化业务数据。

## 三、预览坐标与原始媒体坐标

预览画面为了适配窗口会缩放并加黑边。用户鼠标得到的是预览比例坐标，而修复引擎需要原始帧像素坐标。

```text
原图 1920×1080
   -> 等比缩放到预览区域
   -> 记录缩放比例和黑边
   -> 用户拖出预览 ROI
   -> 反向映射为原图 (xmin, xmax, ymin, ymax)
```

如果忽略黑边和缩放比例，框选区域在不同窗口尺寸下会偏移。这说明 UI 几何数据不能直接当业务数据使用，必须经过坐标转换边界。

## 四、OCR 回显为什么使用 Signal

OCR 检测是耗时操作。页面在后台线程获取 `OcrPolygon`，然后发射：

```text
ocr_detection_finished_signal(task_index, polygons, error)
```

主线程槽函数负责：

- 把多边形外接框转为可编辑候选 ROI；
- 将多边形序列化存进任务；
- 根据模式建立精确 mask；
- 在预览上显示黄色框、青色轮廓与红色 mask。

后台只返回数据，不认识任何 QLabel、QPixmap 或表格。这是跨线程 GUI 的正确职责划分。

## 五、修复任务为什么走子进程

`SubtitleRemover` 可能加载 PaddleOCR、PyTorch、CUDA、FFmpeg，并逐帧处理视频。它在 `multiprocessing.Process` 中运行：

```text
HomeInterface 工作线程
    -> 启动修复子进程
    -> 子进程构建 SubtitleRemover
    -> Queue 回传消息
    -> Qt Signal 刷新 GUI
```

这样做的收益：

- OCR/模型异常不直接杀死 GUI；
- 停止时可终止任务进程；
- Windows spawn 下模型在子进程惰性加载；
- GUI 不需要持有 GPU 模型状态。

## 六、增强页的响应式修复案例

增强页曾出现三个典型 UI 问题：长路径撑高设置卡、窗口非全屏比例失衡、完成后仍显示输入图。最终解决方案不是继续增加单文件页面的局部控件，而是复用内容修复页的桌面工具结构：

- 左侧使用 `MediaPreviewComponent`，提供黑底 16:9 输入、输出和输入/当前输出对比预览；
- 左下使用日志卡，记录模型加载、任务开始、编码、输出、失败和停止；
- 右侧使用 `ComboBoxSettingCard`，使增强模型、倍率和设备与内容修复页采用同一视觉语言；
- 右侧任务表保存多个媒体的名称、进度、状态、模型、倍率、设备和输出路径；
- 队列线程顺序调度任务，视频预览按固定帧间隔回传，并将预览最长边限制为 960px；
- 完成后重新读取输出图片或输出视频首帧，任务选择决定预览媒体。

这正是“视图状态与数据状态分离”的具体体现。

## 七、配置与独立项目身份

`backend/config.py` 集中保存：

- 当前版本和项目 GitHub URL；
- AI 模式、设备、模型缓存目录；
- OCR 阈值、精确掩膜模式、视频策略；
- 用户窗口尺寸、语言和输出目录。

当前项目已经不再比较上游项目 Release。更新 API、Issues、Release 和项目主页都指向净绘工坊自己的 GitHub 仓库。上游来源只保留在 `NOTICE`、`THIRD_PARTY_NOTICES.md` 和 `MODIFICATIONS.md` 等合规文件中。

## 八、可以继续演进的部分

| 当前实现 | 后续方向 |
| --- | --- |
| `QTableWidget` 管理任务 | 自定义 `QAbstractTableModel`，支持排序、筛选、持久化。 |
| 手工矩形与 OCR 多边形 | 加入笔刷/橡皮擦像素级 mask。 |
| 图片模型逐帧修复视频 | 接入时序模型或光流传播，降低闪烁。 |
| Queue 传预览帧 | 预览采样、缩放、节流，降低 IPC 压力。 |
| 字符串状态 | 显式任务状态机和可恢复任务记录。 |

## 九、把坐标转换写成可测试函数

这一类功能最常见的缺陷是“开发者窗口大小下正确，用户缩放窗口后偏移”。将预览坐标转换从控件事件中抽成纯函数，才能用不同宽高和黑边组合覆盖它。

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewTransform:
    image_width: int
    image_height: int
    draw_x: int       # 图像在预览控件中的左边界
    draw_y: int       # 图像在预览控件中的上边界
    draw_width: int   # 等比缩放后的绘制宽度
    draw_height: int

    def to_image_rect(self, x1: int, y1: int, x2: int, y2: int):
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        scale_x = self.image_width / self.draw_width
        scale_y = self.image_height / self.draw_height
        left = round((left - self.draw_x) * scale_x)
        right = round((right - self.draw_x) * scale_x)
        top = round((top - self.draw_y) * scale_y)
        bottom = round((bottom - self.draw_y) * scale_y)
        return (
            max(0, min(self.image_width, left)),
            max(0, min(self.image_height, top)),
            max(0, min(self.image_width, right)),
            max(0, min(self.image_height, bottom)),
        )
```

假设原图是 `1920×1080`，在 `1000×800` 的预览区域按比例绘制为 `1000×562`，上下各有 `119` 像素黑边，则 `draw_y=119`。用户在预览的 `(100, 219)` 到 `(900, 581)` 拖拽时，函数得到的才是原图坐标；若直接把鼠标坐标交给 OpenCV，y 轴会整体偏移 119 个预览像素。实际实现还应在鼠标按下时拒绝落在 `draw_x/draw_y` 黑边外的起点，避免用户看见一个不可解释的边界裁剪。

## 十、从页面到子进程的最小数据契约

页面不要把 widget 或临时绘制对象传给 worker。确认后的数据应冻结成能够打印、保存、重放的载荷：

```python
payload = {
    "task_id": task.task_id,
    "input_path": str(task.input_path),
    "output_path": str(task.output_path),
    "mask_plan": {
        "manual_rects": [(120, 800, 1860, 960)],
        "ocr_polygons": [[[130, 805], [1850, 805], [1850, 950], [130, 950]]],
        "dilate_pixels": 4,
    },
    "engine": {"name": "lama", "device": "cuda"},
}
```

这个 payload 有意只包含 JSON 友好数据。worker 把它转换为 `MaskPlan`、加载模型、产生输出；UI 收到的回调则只包含任务 ID、进度、日志和尺寸受限的预览。这样即使将来从 `multiprocessing` 换成远程 worker、`QProcess` 或 C++ 加速模块，页面契约也无需变化。

## 十一、C++ 底层视角：图像帧与 GUI 资源不要混用

OpenCV 的 `cv::Mat` 和 Qt 的 `QImage`/`QPixmap` 具有不同的数据布局、生命周期和线程要求。常见的 C++ 桥接会先用 `QImage` 包装 RGB 缓冲区，再调用 `.copy()` 取得独立所有权；否则 `cv::Mat` 释放或复用缓冲区后，预览可能显示花屏或访问无效内存。Python 与 NumPy/OpenCV 间也存在同样的问题：是否 copy、数组是否连续、BGR/RGB 是否已转换，都应由一个明确的转换边界负责。

`QPixmap` 则更接近 GUI/窗口系统资源，不能作为跨进程或跨线程的数据载体。传输预览时使用缩小后的 RGB bytes、PNG/JPEG bytes 或临时文件路径；在 GUI 线程构造 `QImage/QPixmap` 并显示。所谓“偶尔能直接传”并不会让这种所有权和线程边界突然合理。

## 总结

净绘工坊不是把 Qt 当作“显示几个按钮”的工具，而是将它用作桌面工程协调层：页面收集意图，任务数据冻结状态，子进程执行重任务，Queue 传输跨进程消息，Qt Signal 安全地更新 UI。理解这一链路后，增加新模型或新页面不会立刻演变成所有模块互相调用的混乱。
