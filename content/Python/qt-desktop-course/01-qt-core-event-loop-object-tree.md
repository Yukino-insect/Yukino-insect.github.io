+++
date = '2026-10-04T21:01:00+08:00'
draft = false
title = 'Qt 的核心心智模型：事件循环、事件分发与 QObject 对象树'
+++
很多 GUI 初学者的第一个困惑是：代码明明从上到下执行，为什么按钮点击、窗口重绘和定时器回调能在“以后”发生？答案是 Qt 不是在普通顺序代码之外施展魔法，而是启动了一个持续运行的**事件循环**。

理解事件循环和对象树，是学习 Qt 最值得先投入时间的两件事。它们分别回答：程序如何持续响应外界，以及对象何时应该被销毁。

## 一、`QApplication` 不只是一个初始化对象

Qt Widgets 应用通常从下面的结构开始：

```python
import sys
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication(sys.argv)
button = QPushButton("点击我")
button.show()
sys.exit(app.exec())
```

`QApplication` 管理应用级资源：

- 与操作系统窗口系统交互；
- 字体、剪贴板、主题、输入法等共享服务；
- GUI 事件分发；
- 主事件循环。

一个进程通常只能有一个 `QApplication`。在测试中也要先确保已有实例不存在，再创建新的实例。

## 二、事件循环如何工作

可以将事件循环想象为一个不断重复的调度器：

```text
while application_is_running:
    event = wait_for_next_event()
    target = decide_who_should_receive(event)
    target.event(event)
    run_pending_queued_callbacks()
    repaint_if_needed()
```

真实实现更复杂，但核心不变。事件可能来自：

- 鼠标按下、移动、释放；
- 键盘输入；
- 窗口大小变化、最小化、关闭；
- 操作系统要求重绘；
- 定时器到期；
- 跨线程排队的信号；
- 网络、进程或自定义事件。

`app.exec()` 会进入循环，直到调用 `quit()`、关闭最后一个窗口或发生其他退出条件。若不调用它，窗口可能一闪而过，定时器和点击也不会有机会发生。

## 三、为什么阻塞主线程会让窗口“未响应”

假设按钮槽函数里直接执行十秒计算：

```python
def on_clicked():
    run_model_for_ten_seconds()
```

调用该函数时，主线程无法回到事件循环，因此无法处理：

- 窗口重绘；
- 拖动、缩放、关闭；
- 点击停止按钮；
- 进度条更新；
- 系统的“是否仍在响应”检查。

这就是 GUI 卡顿的本质：不是窗口不想更新，而是负责分发更新事件的线程被占住了。不要用 `time.sleep()` 或长循环占据 UI 线程；后续并发章节会讨论正确的任务边界。

## 四、`QObject`：Qt 对象系统的基础

几乎所有 Qt 核心对象都继承 `QObject`，包括控件、定时器、模型、网络对象和自定义服务。它提供：

- 信号槽机制；
- 对象名称和动态属性；
- 父子对象树；
- 线程归属（thread affinity）；
- 事件处理能力。

`QWidget` 又继承 `QObject`，因此一个按钮既是可显示的视觉对象，也是可以发送信号、拥有父对象、接收事件的 Qt 对象。

## 五、对象树：Qt 的生命周期管理

Qt 的父子关系并不只是界面嵌套。若一个 `QObject` 有 parent，当 parent 销毁时，Qt 会销毁它的子对象。

```python
from PySide6.QtWidgets import QWidget, QPushButton

panel = QWidget()
button = QPushButton("保存", panel)
```

这里 `panel` 是 `button` 的父对象。关闭并销毁 `panel` 时，按钮会随之清理。布局也会管理所加入控件的可视层级与几何关系。

需要区分两套概念：

| 机制 | 谁负责 | 典型问题 |
| --- | --- | --- |
| Python 引用计数/GC | Python 运行时 | Python 变量是否还持有引用？ |
| Qt 父子对象树 | Qt | parent 销毁时 child 是否应随之销毁？ |

它们会相互影响，但不是同一个系统。把一个 Qt 控件创建在局部变量中却不保存引用，有时 Python 可能先回收包装对象；反之，Qt parent 也可能仍持有底层对象。因此 GUI 中通常应让窗口或控制器持有长期对象的 Python 引用，同时正确设置 Qt parent。

## 六、事件、`event()` 与专用处理函数

Qt 先把事件送到对象的 `event()`，再由它分派到更专门的方法：

```text
QMouseEvent    -> mousePressEvent / mouseMoveEvent / mouseReleaseEvent
QKeyEvent      -> keyPressEvent / keyReleaseEvent
QPaintEvent    -> paintEvent
QResizeEvent   -> resizeEvent
QCloseEvent    -> closeEvent
```

例如需要自定义绘制时重写 `paintEvent`；需要处理窗口关闭并清理资源时重写 `closeEvent`。

```python
def closeEvent(self, event):
    self.stop_running_task()
    self.save_window_geometry()
    event.accept()
```

不要为了监听一个普通按钮点击而重写 `mousePressEvent`。优先使用控件已有信号；只有事件语义本身需要改变时，才走事件重写。

## 七、事件过滤器：横切观察而非强行继承

如果想在不修改目标类的情况下观察或拦截事件，可以安装 event filter：

```python
class EscapeFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            watched.clearFocus()
            return True
        return False

line_edit.installEventFilter(EscapeFilter(line_edit))
```

返回 `True` 表示事件已处理，不再继续传递；返回 `False` 表示让原对象继续处理。过滤器适合快捷键、输入限制、全局交互策略等横切需求；过度使用会让控制流隐蔽，简单需求仍应优先连接信号。

## 八、与净绘工坊的联系

净绘工坊中：

- `QApplication.exec()` 保持主窗口和两个功能页面持续响应；
- `FluentWindow`、各页面和控件通过 parent/布局建立对象树；
- 窗口关闭事件负责终止正在执行的子进程；
- 视频预览、滑块、OCR 结果和进度更新都依赖主事件循环；
- 后台任务绝不能直接阻塞点击“停止”后的响应。

如果忽略事件循环，后面所有“线程、进度条、Signal”的讨论都失去基础。

## 九、可运行练习：用零延迟定时器分片，而不是假装异步

下面程序计算较大的累加任务，但每次只处理一小段；处理完一段后把控制权还给事件循环。因此窗口仍可以拖动、重绘和响应“取消”。它适合很短且可拆分的纯 UI 协作工作，不适合模型推理或文件编码。

```python
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class ChunkedCounter(QWidget):
    def __init__(self):
        super().__init__()
        self._next = 0
        self._total = 20_000_000
        self._sum = 0

        self.status = QLabel("尚未开始")
        self.start_button = QPushButton("开始")
        self.cancel_button = QPushButton("取消")
        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.start_button)
        layout.addWidget(self.cancel_button)

    def start(self):
        self._next, self._sum = 0, 0
        self.start_button.setEnabled(False)
        QTimer.singleShot(0, self.process_one_chunk)

    def process_one_chunk(self):
        chunk_end = min(self._next + 100_000, self._total)
        self._sum += sum(range(self._next, chunk_end))
        self._next = chunk_end
        self.status.setText(f"{self._next:,} / {self._total:,}")

        if self._next < self._total:
            QTimer.singleShot(0, self.process_one_chunk)
        else:
            self.status.setText(f"完成，结果为 {self._sum}")
            self.start_button.setEnabled(True)

    def cancel(self):
        self._total = self._next


app = QApplication(sys.argv)
window = ChunkedCounter()
window.show()
sys.exit(app.exec())
```

关键不在 `singleShot(0, ...)` 这个写法本身，而在 `process_one_chunk()` 能很快返回。调用 `QTimer.singleShot` 只是向事件队列追加一个后续回调；它**没有创建线程**。若把 `100_000` 改成几亿，窗口仍然会卡住。真正耗时或不可自然拆分的工作，应该使用第五篇的 worker 线程或第六篇的进程。

## 十、C++ 底层视角：事件队列、元对象与延迟删除

Qt C++ 的事件循环通过平台事件分发器等待操作系统消息，再把它们封装为 `QEvent` 并投递给目标 `QObject`。跨线程 queued signal、`QTimer` 超时和 `deleteLater()` 也都会变成待处理事件。可以把其中的关系概括为：

```text
Windows/macOS/Linux 平台消息
        -> QAbstractEventDispatcher
        -> QObject::event(QEvent*)
        -> 专用处理函数或 Qt 元对象调用槽
```

`deleteLater()` 之所以比立刻释放更安全，是因为它把销毁操作排到对象所属线程的事件循环中，避开“当前还在处理该对象的事件/槽”这一危险时刻。C++ 中常见形式是：

```cpp
connect(worker, &Worker::finished, worker, &QObject::deleteLater);
```

PySide6 调用的是同一个原生 `QObject::deleteLater()`。不过不要把它误解成 Python `del worker`：前者安排 Qt 原生对象的安全销毁，后者只减少一个 Python 引用。两者针对的生命周期层次不同。

## 总结

- `QApplication` 是应用级事件与资源管理器。
- `exec()` 启动事件循环，GUI 才能持续处理输入、重绘和异步回调。
- 主线程被同步耗时任务占住时，窗口必然失去响应。
- `QObject` 提供信号槽、对象树、线程归属和事件能力。
- 父子对象树解决 Qt 生命周期，但仍要理解 Python 引用的作用。
- `QTimer.singleShot(0, ...)` 只是在同一事件循环中分片调度；它不是后台线程。
- PySide6 的事件、定时器和 `deleteLater()` 仍由 Qt C++ 事件队列执行。
