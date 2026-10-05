+++
date = '2026-10-04T21:05:00+08:00'
draft = false
title = 'Qt 并发：QThread、线程池与 UI 主线程边界'
+++
“把耗时任务放进线程”这句话只说对了一半。真正的问题是：任务对象属于哪个线程？槽函数在哪个线程执行？结果怎样安全回到 UI？取消时谁负责清理？如果这些问题没有答案，线程只会把卡顿变成随机崩溃。

## 一、先牢记唯一规则：UI 只在主线程更新

Qt Widgets 不是线程安全的。创建窗口和控件的线程通常是 GUI 主线程，`setText()`、`setPixmap()`、插入表格行等操作都应在那里完成。

正确模式：

```text
Worker thread
    -> emits progress/result signal
    -> queued delivery
GUI thread slot
    -> updates progress bar / label / preview
```

错误模式：

```python
def background_work():
    result = slow_job()
    self.label.setText(result)  # 不要这样做
```

## 二、三种常用执行方式

| 工具 | 适合什么 | 关键特点 |
| --- | --- | --- |
| `QTimer` | 小任务分片、延迟执行 | 仍在主线程，不能跑重计算。 |
| `QThread` + worker `QObject` | 长生命周期、可发多次进度的任务 | 有独立事件循环和明确 worker 生命周期。 |
| `QRunnable` + `QThreadPool` | 大量短任务 | 轻量、复用线程池，不适合依赖对象事件循环的复杂 worker。 |

Python 的 `threading.Thread` 也能用于纯 Python 后台工作，但与 Qt UI 交互时仍要通过 Qt Signal 或 `QMetaObject.invokeMethod` 回到主线程。

## 三、推荐的 `QThread + QObject worker` 模式

不要把所有逻辑都写进 `QThread.run()` 后就直接操作 UI。更推荐将 worker 移动到 thread：

```python
class Worker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    failed = Signal(Exception)

    @Slot()
    def run(self):
        try:
            for index in range(100):
                do_one_step(index)
                self.progress.emit(index + 1)
            self.finished.emit("output.mp4")
        except Exception as exc:
            self.failed.emit(exc)


thread = QThread()
worker = Worker()
worker.moveToThread(thread)
thread.started.connect(worker.run)
worker.progress.connect(progress_bar.setValue)
worker.finished.connect(thread.quit)
worker.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)
thread.start()
```

这个模式的价值不只是模板好看：

- worker 的耗时槽在工作线程执行；
- progress 信号排队到 GUI 线程；
- `finished` 同时负责业务完成与线程退出；
- `deleteLater()` 在对象所属事件循环中安全释放对象。

## 四、`QRunnable` 与线程池

对于短小、无状态、数量较多的任务，例如批量缩略图、元数据读取、哈希计算，可使用：

```python
class ThumbnailJob(QRunnable):
    def run(self):
        create_thumbnail()

QThreadPool.globalInstance().start(ThumbnailJob())
```

`QRunnable` 本身不继承 `QObject`，因此通常要配一个单独的 `QObject` signal holder 回传结果。它适合“投递一次、执行一次、结束”的任务；需要取消、状态、事件循环或长期连接时，`QThread + QObject` 往往更清楚。

## 五、取消不是强杀线程

Python 没有安全通用的“杀死一个任意线程”接口。强行终止可能留下：

- 文件只写了一半；
- FFmpeg stdin 管道未关闭；
- 锁未释放；
- GPU/模型状态异常；
- 临时文件未清理。

更可靠的做法是协作式取消：

```python
class Worker(QObject):
    def __init__(self):
        super().__init__()
        self._cancelled = False

    @Slot()
    def cancel(self):
        self._cancelled = True

    @Slot()
    def run(self):
        for item in items:
            if self._cancelled:
                return
            process(item)
```

取消响应点应放在安全边界，例如一帧视频处理结束后、一个文件写入前、一个网络请求返回后。

## 六、GIL 与 Qt 线程不是一回事

CPython 的 GIL 限制多个线程同时执行 Python 字节码，但：

- I/O 等待时线程仍有价值；
- NumPy、OpenCV、PyTorch 等原生代码可能释放 GIL；
- Qt 线程仍能让 UI 事件循环不被阻塞；
- 真正 CPU 密集纯 Python 计算可能更适合多进程。

所以“有 GIL 就不要线程”是错误结论。问题应是：任务是 I/O、原生计算、Python CPU 计算，还是 GPU/模型运行？它需要 UI 事件循环吗？能否被安全终止？

## 七、净绘工坊的选择

净绘工坊中有两层并发：

```text
GUI 主线程
    -> Python 工作线程：顺序调度队列中的任务
    -> multiprocessing 子进程：加载 OCR / Torch / FFmpeg 并执行修复
```

使用子进程是因为 AI 模型、CUDA、PaddleOCR、视频编码和强制终止的边界比普通线程更复杂。工作线程只负责不阻塞 GUI 地等待和调度；真正的模型任务隔离到进程中。

增强页的图片/视频处理目前以 Python 线程运行，并通过 Qt Signal 更新进度；安全停止采用 `threading.Event`，在当前帧处理结束后退出。后续若增强模型的进程隔离、显存回收或强制终止需求提高，也可统一迁移到进程任务执行器。

## 八、可运行练习：带取消、错误和清理的 `QThread` 任务

下面示例比“在线程里跑一个函数”多出三个不可省略的部分：取消请求走 worker 的槽；异常转换为文本信号；线程结束后在正确时机清理对象。运行时可连续点击“开始”，第二次会被禁用，避免同一个窗口重复启动任务。

```python
import sys
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class CountingWorker(QObject):
    progress = Signal(int)
    finished = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._cancel_requested = False

    @Slot()
    def run(self):
        try:
            for value in range(101):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                time.sleep(0.03)  # 用 I/O 或计算替换；绝不能放在 GUI 线程
                self.progress.emit(value)
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    @Slot()
    def request_cancel(self):
        self._cancel_requested = True


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.label = QLabel("就绪")
        self.start_button = QPushButton("开始")
        self.cancel_button = QPushButton("取消")
        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.cancel_button)

    def start(self):
        self.start_button.setEnabled(False)
        self.thread = QThread(self)
        self.worker = CountingWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(lambda value: self.label.setText(f"{value}%"))
        self.worker.finished.connect(lambda: self._stop_thread("完成"))
        self.worker.cancelled.connect(lambda: self._stop_thread("已取消"))
        self.worker.failed.connect(self._stop_thread)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._clear_references)
        self.thread.start()

    def cancel(self):
        if self.worker is not None:
            self.worker.request_cancel()

    def _stop_thread(self, message: str):
        self.label.setText(message)
        self.thread.quit()

    def _clear_references(self):
        self.start_button.setEnabled(True)
        self.thread.deleteLater()
        self.thread = None
        self.worker = None


app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec())
```

这段代码还有一个值得辨析的细节：`cancel()` 直接调用 `worker.request_cancel()` 时，该槽实际运行在 GUI 线程；它只写入一个 Python 布尔值，足够简单，但它并不是“把取消任务投递到 worker 线程”。如果取消逻辑需要关闭 worker 所在线程中的 `QNetworkReply`、timer 或其他 QObject，应定义一个 controller signal，并使用 `Qt.QueuedConnection` 连接到 worker 槽，确保该操作在 worker thread 执行。无论采用哪种方式，worker 都必须在安全检查点主动退出。

## 九、C++ 底层视角：`moveToThread` 只移动 QObject，不移动代码

`QThread` 在 C++ 中容易产生一个误解：`QThread` 对象本身通常仍属于创建它的 GUI 线程；它代表并管理的操作系统线程才是工作线程。`worker.moveToThread(thread)` 改变的是 worker 的 **thread affinity**，使得投递给 worker 的 queued slot 在该工作线程事件循环中执行。

因此，`thread.started.connect(worker.run)` 的 `run()` 在新线程中执行，而 `Window._stop_thread()` 因为属于 GUI `Window`，会在 GUI 线程处理 worker 发出的信号。`AutoConnection` 根据发射时与接收者归属线程选择直接或排队调用。PySide6 没有绕过这套 C++ 规则；它只是让槽体使用 Python 编写。

另外，示例用 `time.sleep` 模拟耗时工作只是为了看见进度。真正纯 Python CPU 密集循环即使放入 `QThread` 也会受 GIL 限制；但 UI 事件循环已经不被它占据，界面仍能响应。若需要多个 CPU 核并行计算，应转到第 6 篇的进程模型。

## 总结

- UI 控件只由 GUI 主线程更新。
- `QThread + QObject` 是带进度、状态和生命周期任务的推荐模式。
- `QThreadPool` 适合大量短任务。
- 取消应是协作式安全停止，不是随意强杀线程。
- GIL 不等于 Qt 线程没有价值；要按工作负载和资源边界选择线程或进程。
- `moveToThread` 改变对象的线程归属，不会把 `QThread` 对象或任意 Python 函数“自动搬到后台”。
