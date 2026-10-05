+++
date = '2026-10-04T21:10:00+08:00'
draft = false
title = '实战：用 PySide6 构建可取消的批处理任务面板'
+++
前面的章节分别讨论事件循环、布局、信号槽、模型视图和并发。若它们始终各自独立，读者很容易以为“理解了概念”，却不知道一个真实页面应当如何拼起来。本篇用一个不依赖 AI 模型的批处理任务面板，把这些概念收束为一个可运行的小程序。

程序允许加入演示任务、顺序开始、取消当前任务，并在表格中实时显示进度。耗时工作只是 `sleep` 模拟，恰好能把焦点放在 Qt 的工程边界上；把它替换为缩略图生成、文件哈希、图片处理或调用服务时，结构不需要改变。

## 一、完成后的结构

```text
MainWindow（GUI 线程）
├─ TaskTableModel          任务数据到表格的适配器
├─ QTableView              仅负责展示、选择
├─ Start / Cancel 按钮     用户意图
└─ QThread + JobWorker     一次只运行一个后台任务
       └─ Signal           进度、完成、取消、错误回到 GUI 线程
```

这里刻意采用“一次一个 worker、按队列顺序执行”。批量并行当然可以做，但它需要额外定义并发数、资源争抢、完成顺序、取消语义和进度聚合。先让单任务生命周期没有漏洞，再扩展并发；这是比一上来堆线程池更可靠的顺序。

## 二、运行方式

在虚拟环境安装 PySide6，然后将下面完整代码保存为 `task_panel.py`：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install PySide6
python task_panel.py
```

## 三、完整代码

```python
import sys
import time
from dataclasses import dataclass
from itertools import count

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Task:
    task_id: str
    name: str
    progress: int = 0
    state: str = "等待中"
    error: str = ""


class TaskTableModel(QAbstractTableModel):
    NAME, PROGRESS, STATE = range(3)
    HEADERS = ("任务", "进度", "状态")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[Task] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._tasks)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        task = self._tasks[index.row()]
        if role == Qt.DisplayRole:
            values = (task.name, f"{task.progress}%", task.state)
            return values[index.column()]
        if role == Qt.ToolTipRole and task.error:
            return task.error
        if role == Qt.ForegroundRole and task.state == "失败":
            return QColor("#c0392b")
        if role == Qt.TextAlignmentRole and index.column() == self.PROGRESS:
            return Qt.AlignCenter
        return None

    def add(self, task: Task):
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()

    def next_pending(self) -> Task | None:
        return next((item for item in self._tasks if item.state == "等待中"), None)

    def _row_for(self, task_id: str) -> int:
        for row, task in enumerate(self._tasks):
            if task.task_id == task_id:
                return row
        raise KeyError(task_id)

    def set_progress(self, task_id: str, value: int):
        row = self._row_for(task_id)
        task = self._tasks[row]
        task.progress = max(0, min(100, value))
        index = self.index(row, self.PROGRESS)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def set_state(self, task_id: str, state: str, error: str = ""):
        row = self._row_for(task_id)
        task = self._tasks[row]
        task.state, task.error = state, error
        if state == "已完成":
            task.progress = 100
        left, right = self.index(row, self.PROGRESS), self.index(row, self.STATE)
        self.dataChanged.emit(left, right, [Qt.DisplayRole, Qt.ForegroundRole, Qt.ToolTipRole])


class JobWorker(QObject):
    progress = Signal(str, int)
    completed = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str, str)

    def __init__(self, task_id: str):
        super().__init__()
        self._task_id = task_id
        self._cancel_requested = False

    @Slot()
    def run(self):
        try:
            for value in range(1, 101):
                if self._cancel_requested:
                    self.cancelled.emit(self._task_id)
                    return
                time.sleep(0.025)  # 替换成单个可取消的处理步骤
                self.progress.emit(self._task_id, value)
            self.completed.emit(self._task_id)
        except Exception as exc:
            self.failed.emit(self._task_id, f"{type(exc).__name__}: {exc}")

    @Slot()
    def request_cancel(self):
        self._cancel_requested = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批处理任务面板")
        self.resize(720, 420)
        self._ids = count(1)
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._closing = False

        self.model = TaskTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.status = QLabel("加入任务后点击“顺序开始”。")
        self.add_button = QPushButton("加入演示任务")
        self.start_button = QPushButton("顺序开始")
        self.cancel_button = QPushButton("取消当前任务")
        self.add_button.clicked.connect(self.add_demo_task)
        self.start_button.clicked.connect(self.start_queue)
        self.cancel_button.clicked.connect(self.cancel_current)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self.status)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)
        self.setCentralWidget(root)

    def add_demo_task(self):
        number = next(self._ids)
        self.model.add(Task(f"job-{number}", f"示例文件 {number}.png"))
        self.status.setText("任务已加入队列。")

    def start_queue(self):
        if self._thread is not None:
            return
        self._start_next_task()

    def _start_next_task(self):
        task = self.model.next_pending()
        if task is None:
            self.status.setText("队列已完成。")
            return

        self.model.set_state(task.task_id, "运行中")
        self.status.setText(f"正在处理：{task.name}")
        self._thread = QThread(self)
        self._worker = JobWorker(task.task_id)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.on_progress)
        self._worker.completed.connect(self.on_completed)
        self._worker.cancelled.connect(self.on_cancelled)
        self._worker.failed.connect(self.on_failed)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    @Slot(str, int)
    def on_progress(self, task_id: str, value: int):
        self.model.set_progress(task_id, value)

    @Slot(str)
    def on_completed(self, task_id: str):
        self.model.set_state(task_id, "已完成")
        self.status.setText("一个任务已完成。")
        self._thread.quit()

    @Slot(str)
    def on_cancelled(self, task_id: str):
        self.model.set_state(task_id, "已取消")
        self.status.setText("当前任务已取消。")
        self._thread.quit()

    @Slot(str, str)
    def on_failed(self, task_id: str, message: str):
        self.model.set_state(task_id, "失败", message)
        self.status.setText(f"任务失败：{message}")
        self._thread.quit()

    def cancel_current(self):
        if self._worker is not None:
            # 这里只写一个布尔标记；复杂 QObject 清理应改为 queued slot。
            self._worker.request_cancel()

    @Slot()
    def _on_thread_finished(self):
        thread = self._thread
        self._thread, self._worker = None, None
        if thread is not None:
            thread.deleteLater()
        if self._closing:
            QTimer.singleShot(0, self.close)
        else:
            self._start_next_task()

    def closeEvent(self, event):
        if self._thread is None:
            event.accept()
            return
        self._closing = True
        self.cancel_current()
        self.status.setText("正在取消当前任务后关闭……")
        event.ignore()


app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
```

## 四、代码如何对应前面的原则

| 代码位置 | 解决的问题 | 对应章节 |
| --- | --- | --- |
| `Task` | 用纯数据保存业务状态，不把状态塞进 cell widget。 | Model/View 与状态架构 |
| `beginInsertRows` / `endInsertRows` | 告知 view 结构发生了变化。 | Model/View 与状态架构 |
| `JobWorker.progress` | 后台只发布数据，UI 在槽中刷新。 | 信号槽与线程边界 |
| `moveToThread` | 让 `run` 在工作线程中执行，释放 GUI 事件循环。 | Qt 并发 |
| `_on_thread_finished` | 在上一个 worker 结束后才启动下一个，避免重复占用资源。 | 对象树与生命周期 |
| `closeEvent` | 先请求协作式取消，再在 worker 退出后真正关闭。 | 事件与资源清理 |

有两个看上去微小、却最容易写错的细节。

第一，`JobWorker` 不持有 `QLabel`、`QTableView` 或 `TaskTableModel`。它只携带任务 ID 并发射不可变的值。因而它将来可以被 `multiprocessing` 子进程、`QProcess` 或远程服务替换，GUI 层的更新接口不必重写。

第二，`closeEvent` 不能在 `QThread` 仍运行时直接销毁窗口。示例先设置 `_closing` 并发出取消意图，忽略当前 close event；`QThread.finished` 到来后才用 `QTimer.singleShot(0, self.close)` 重新请求关闭。真实的不可协作外部任务还需设置超时和升级策略，例如终止单独的子进程；不要对任意 Python 线程强杀。

## 五、练习：把模拟任务替换为真实工作

按下面顺序扩展，能避免一次修改太多层：

1. 在 `add_demo_task` 中使用 `QFileDialog.getOpenFileNames` 加入真实文件路径，并在 `Task` 中保存 `source_path` 和输出目录。
2. 将 `time.sleep` 替换为一个处理步骤，例如读取一张图片、生成缩略图、写入输出。每处理一个文件块或一帧就检查 `_cancel_requested`。
3. 增加 `output_path` 与 `error` 列；错误应显示简短消息，完整异常栈写入日志文件。
4. 当工作负载变成 CPU/GPU 模型、CUDA 或需要硬终止时，将 `JobWorker` 的内部实现替换为第 6 篇的进程协议，但保留 `on_progress/on_completed/on_failed` 这组 GUI 槽。
5. 对 `TaskTableModel` 的状态更新和“取消后不可能完成”编写测试，再为窗口写离屏冒烟测试。

## 六、C++ 底层映射：为什么这不是“Python 特有技巧”

这段 PySide6 程序与 C++ Qt 的结构几乎一一对应：`TaskTableModel` 覆盖 C++ `QAbstractTableModel::data` / `rowCount`；`JobWorker` 对应含 `Q_OBJECT`、`signals`、`public slots` 的 `QObject`；`QThread`、queued connection 和 `deleteLater()` 仍由 Qt 6 原生运行时执行。

Python 的类型标注 `QThread | None` 与 `list[Task]` 只帮助读者和静态分析器，不会改变 Qt 的线程模型。真正使进度更新安全的条件是：worker 发射 signal 后，接收者 `MainWindow` 属于 GUI 线程，Qt 把调用排进 GUI 事件循环。若绕过 signal 直接在 `run()` 中修改 table，哪怕 Python 代码没有报错，也是在破坏同一条 C++ Qt 线程规则。

## 总结

- 一个小型任务面板已经足以同时使用对象树、事件循环、Model/View、信号槽和线程边界。
- worker 应处理数据并发布结果，view 应呈现状态；两者不要互相持有引用。
- 取消是协议的一部分：要有检查点、最终状态和关闭时的等待策略。
- 把模拟任务替换为真实工作时，优先保持 GUI 回调接口不变，再替换底层执行器。
