+++
date = '2026-10-04T21:09:00+08:00'
draft = false
title = 'Qt 桌面应用的测试、资源与交付：从离屏验证到可发布软件'
+++
桌面应用在开发机上能点开，并不等于它可测试、可交付。真实用户会有不同 DPI、路径、权限、显卡、媒体文件和安装环境；而 Qt 应用还会同时包含 Python 依赖、原生 Qt 库、图片图标、FFmpeg、模型、许可证与配置文件。

本篇讨论最后一段工程能力：怎样测试 Qt UI，怎样处理资源和路径，以及怎样把“能运行的源码”变成一个可负责的发行物。

## 一、测试不应只依赖人工点击

人工测试仍然必要，尤其是视觉效果和交互手感。但基础行为应有自动化验证：

- 界面能否创建；
- 长路径是否换行撑破布局；
- 按钮状态是否与任务状态一致；
- 完成后预览是否切换输出；
- 任务参数是否正确传入后端；
- 关闭窗口时是否请求清理任务。

Qt 在没有真实显示器的环境中也可测试。常用方式：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s test -p "test_*.py" -v
```

`offscreen` 让 Qt 使用离屏平台插件。它不能替代真实视觉验收，但很适合验证窗口构造、控件属性、信号槽和基本状态变化。

## 二、一个最小的离屏 UI 测试

```python
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from ui.enhance_interface import EnhanceInterface


class EnhanceInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_long_path_is_elided(self):
        widget = EnhanceInterface()
        widget.resize(900, 560)
        widget.show()
        self.app.processEvents()

        path = "C:/" + "very-long-name/" * 30 + "image.png"
        widget._set_file_label(path)

        self.assertFalse(widget.file_label.wordWrap())
        self.assertEqual(widget.file_label.toolTip(), path)
        self.assertNotIn("\n", widget.file_label.text())
        widget.close()
```

测试这里验证的不是字体像素是否绝对一致，而是布局规则：长路径不换行、完整路径可访问、显示文本保持单行。

## 三、分层测试比只测 UI 更有效

推荐按层次安排：

| 层次 | 测什么 | 例子 |
| --- | --- | --- |
| 纯函数单元测试 | 无 Qt、无网络逻辑 | 多边形 mask 面积、坐标裁剪、输出命名。 |
| 服务测试 | 文件/任务行为 | `MaskPlan` 序列化、取消逻辑、输出存在性。 |
| UI 冒烟测试 | 构造和状态映射 | 页面可创建、按钮状态、标签省略。 |
| 集成测试 | 真实模型/FFmpeg | 小图修复、小视频编码、模型推理。 |
| 人工验收 | 视觉与体验 | 不同 DPI、长路径、深浅主题、真实媒体。 |

默认测试不应偷偷下载数百 MB 模型或依赖网络；真实 AI 推理测试可以通过环境变量显式开启。这样 CI 稳定，维护者也能在有 GPU/缓存时运行完整验证。

## 四、资源路径：开发环境和打包环境不同

开发时可以写：

```python
QtGui.QIcon("design/icon.ico")
```

但打包后当前工作目录不一定是源码根目录。更稳妥的做法是统一封装资源路径：

```python
from pathlib import Path
import sys


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[1]
    return base / relative
```

无论使用 PyInstaller、Nuitka 还是其他工具，都要实际验证图标、翻译文件、模型目录、FFmpeg 二进制和配置文件是否被包含。

## 五、配置、缓存与用户数据要分开

不要把所有可写内容放在程序安装目录。一个健康的目录规划应区分：

```text
应用资源       只读：图标、翻译、内置程序文件
用户配置       可写：窗口位置、语言、默认参数
模型缓存       可写且大：按需下载权重
任务输出       用户选择：修复结果、增强结果
临时文件       可清理：视频编码中间文件
```

这会直接影响权限、卸载、磁盘空间、备份和故障恢复。净绘工坊的模型缓存可在设置中改目录，输出文件不覆盖原文件，都是这一原则的实际应用。

## 六、发布前必须处理的许可证和第三方文件

桌面应用的发行物常含：

- 自己的 Python 源码或编译产物；
- Qt/PySide6 运行库；
- FFmpeg；
- OpenCV、PaddleOCR、PyTorch wheels；
- 模型包装代码；
- 可选模型权重；
- 图标、字体、测试素材。

这些不是一个 `LICENSE` 能全部覆盖的。应在发布物中保留：

```text
LICENSE
NOTICE
THIRD_PARTY_NOTICES.md
THIRD_PARTY_LICENSES/
MODIFICATIONS.md
```

并根据最终安装包中实际包含的版本补齐对应许可证。尤其是模型权重：代码开源许可不自动授予权重再分发权。

## 七、版本与更新检查

独立衍生项目必须有自己的版本序列、Issues、Release 页面和更新 API。不要把上游仓库 Release 当成当前项目最新版本。

合理流程：

```text
0.1.0  初次独立预发布
0.2.0  新功能、兼容性改进
0.2.1  Bug 修复
1.0.0  稳定发布承诺
```

版本检查应只请求当前项目自己的 GitHub Release API；尚未建立独立 Release 时，默认关闭启动检查，避免 404 和错误的版本比较。

## 八、净绘工坊的交付检查清单

- [ ] 普通启动不输出第三方库推广信息。
- [ ] 非全屏窗口下内容修复页和增强页不被长文本撑坏。
- [ ] 图片增强完成后预览输出图，视频增强完成后预览输出首帧。
- [ ] OpenCV 图片/视频回归测试通过。
- [ ] 默认测试不联网下载模型。
- [ ] AI 模型集成测试需要显式开启。
- [ ] 项目主页、Issues、Release 和更新 API 指向自己的仓库。
- [ ] LICENSE、NOTICE、第三方声明和模型边界随发行物发布。
- [ ] 临时视频文件失败或取消后被清理。
- [ ] 用户原始媒体不会被覆盖。

## 九、实战补充：测试状态机和真实事件循环

不要只断言“某个方法被调用过”。任务状态机是纯业务规则，可以不启动 Qt 就测试；而信号到 UI 的投递必须让 Qt 事件循环至少处理一次。

```python
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

from app.task_store import TaskState, TaskStore


class TaskStoreTests(unittest.TestCase):
    def test_task_must_run_before_completion(self):
        store = TaskStore()
        store.add("job-1")
        with self.assertRaises(ValueError):
            store.transition("job-1", TaskState.COMPLETED)

        store.transition("job-1", TaskState.RUNNING)
        store.set_progress("job-1", 63)
        store.transition("job-1", TaskState.COMPLETED)
        self.assertEqual(store._records["job-1"].progress, 100)

    def test_queued_callback_needs_event_processing(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        received = []
        # 在真实测试中，从 worker 发射 queued signal 后再调用这一行。
        app.processEvents()
        self.assertEqual(received, [])
```

第二个测试片段的目的不是制造一个无意义的空列表，而是强调：如果测试对象依赖 queued signal、`QTimer` 或 `deleteLater()`，仅调用槽函数并不能覆盖运行时行为，必须让事件循环处理事件。使用 `pytest-qt` 时可用 `qtbot.waitSignal()` 等待完成信号；使用标准库 `unittest` 时，可在有超时的循环中调用 `app.processEvents()`，避免 CI 无限等待。

建议把第 7 篇的 `TaskStore`、第 4 篇的 `TaskTableModel` 和第 5 篇 worker 分别放在 `tests/test_store.py`、`tests/test_model.py`、`tests/test_worker.py`。前两者应完全离屏且快速；后者只用短小、可控的假任务，不要在单元测试中加载真实模型。

## 十、C++ 底层视角：打包的不只是 Python 文件

PyInstaller 的 `--collect-all PySide6` 或类似参数会收集 Python 包中携带的 Qt 动态库、平台插件和部分资源，但是否完整必须通过一台**没有开发环境**的干净虚拟机验证。Qt C++ 应用也面对相同问题：`windeployqt` 会部署 Qt DLL 与 plugins；Python 打包器只是把这一层也纳入了 Python 发行物。

在 Windows 上，平台插件通常位于 `platforms/qwindows.dll`。缺失或与 Qt 主 DLL 版本不匹配时，应用常报“无法初始化 Qt platform plugin”，这不是窗口代码的逻辑错误。发布排查可临时设置 `QT_DEBUG_PLUGINS=1` 观察 Qt 的插件搜索过程；排查完成后不要把它作为常态环境变量写进产品。

## 总结

- UI 测试可以离屏运行，但仍需真实视觉验收。
- 将纯逻辑、服务、UI 冒烟、真实模型集成测试分层，速度和可信度更平衡。
- 资源路径、可写目录和打包环境必须在发布前验证。
- 桌面发行物的许可证范围比源码仓库更广，应基于实际打包内容核查。
- 一个可发布 Qt 应用的标准不是“开发者机器能启动”，而是能在陌生环境中被安装、理解、排错和维护。
- 自动化测试也要运行事件循环；否则 queued signal、timer 与延迟销毁路径并没有真正被验证。
