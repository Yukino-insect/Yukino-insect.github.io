+++
date = '2026-10-04T21:03:00+08:00'
draft = false
title = 'Qt 信号槽、属性与事件：用观察者模式组织交互，而不是让控件互相纠缠'
+++
一个 GUI 程序里最容易失控的不是控件数量，而是控件之间“谁调用谁”。按钮直接操作表格，表格直接改配置，后台任务直接改标签，页面又回头读取按钮状态——很快就形成循环依赖。

Qt 的 Signal/Slot 机制提供了更清晰的通信方式：对象发布“发生了什么”，其他对象决定“要不要响应、如何响应”。这本质上是观察者模式在事件驱动框架中的工程化实现。

## 一、信号槽的基本写法

```python
button.clicked.connect(self.save)

def save(self):
    print("save")
```

`clicked` 是信号，`save` 是槽。用户点击按钮时，Qt 发射信号；连接到它的槽会被调用。

自定义信号：

```python
from PySide6.QtCore import QObject, Signal


class DownloadTask(QObject):
    progress_changed = Signal(int)
    finished = Signal(str)
    failed = Signal(Exception)
```

信号的参数类型是通信契约。`progress_changed` 表示发送整数进度，`finished` 表示发送输出路径。不要用一个无结构的全局字典承担所有状态；清晰的信号让调用关系可读、可测试。

## 二、为什么不直接调用方法

直接调用当然不是错误：同一对象内部的小操作完全可以直接调。但在对象边界之间，信号槽有几个优势：

- 发送者不必知道接收者是谁；
- 可连接多个接收者；
- 接收者销毁后 Qt 会清理相关连接；
- 跨线程时可由 Qt 排队投递；
- 可以替换、断开或测试某个响应。

```text
直接调用：按钮 -> 任务 -> 表格 -> 日志
信号槽：按钮发起请求；任务发射进度；表格/日志/预览各自订阅
```

后者并不意味着“所有东西都要发信号”。原则是：**跨对象、跨层、跨线程的状态变化适合信号；纯内部算法调用适合普通方法。**

## 三、连接类型与跨线程语义

Qt 连接大致有：

- `DirectConnection`：发射信号时立即在当前线程调用槽；
- `QueuedConnection`：将调用投递到接收者所属线程的事件循环；
- `AutoConnection`：同线程时直接调用，跨线程时自动排队。

默认的 `AutoConnection` 很方便，但前提是你理解对象的线程归属。UI 控件属于 GUI 主线程，后台工作者发出的信号应通过排队方式回到主线程，再更新控件。

**不要从普通 Python 后台线程直接调用 `label.setText()`。** 即使偶尔看似能工作，也属于线程不安全行为，可能在某台机器、某次压力下随机崩溃。

## 四、事件与信号如何分工

| 需求 | 优先方案 |
| --- | --- |
| 按钮被点击 | `clicked` 信号。 |
| 文本变化 | `textChanged` 信号。 |
| 滑块值变化 | `valueChanged` 信号。 |
| 需要自定义鼠标拖拽画框 | 重写 `mousePressEvent/mouseMoveEvent/mouseReleaseEvent`。 |
| 需要统一拦截某类输入 | event filter。 |
| 需要绘制自定义画布 | `paintEvent`。 |

信号表达高层语义，例如“用户请求运行”；事件表达底层输入，例如“鼠标在 (x, y) 位置按下”。不要因为能拿到鼠标事件，就用它实现本已有 `clicked` 信号的按钮逻辑。

## 五、属性、状态与避免反馈循环

GUI 常有双向同步问题：配置变化更新下拉框；用户选择下拉框又写回配置。若没有约束，很容易出现循环触发。

一种简单处理是临时阻塞信号：

```python
combo.blockSignals(True)
combo.setCurrentIndex(index)
combo.blockSignals(False)
```

更好的长期设计是明确状态来源：

```text
配置对象是单一事实来源
    -> 配置变更信号
    -> 视图刷新

用户操作
    -> 意图/命令
    -> 更新配置对象
```

不要让两个控件互相直接更新对方。它们应该都从同一个状态读取，并把修改写回同一个状态。

## 六、生命周期与连接

Qt 在 `QObject` 销毁时会断开与它有关的信号连接，但 Python 闭包、lambda 和外部线程仍可能持有对象引用。因此：

- 长期任务完成前关闭页面时，应取消任务或忽略回调；
- lambda 捕获 `self` 时要清楚其生命周期；
- 不要把 UI 对象传给子进程；
- 对重复创建的工作者，避免重复连接同一槽造成一次事件执行多次。

## 七、净绘工坊中的信号槽链路

净绘工坊的典型链路是：

```text
用户点击“检测当前帧 OCR”
    -> 后台线程检测
    -> ocr_detection_finished_signal(task_index, polygons, error)
    -> GUI 主线程回显候选 ROI、OCR 多边形和最终 mask

子进程修复任务
    -> multiprocessing.Queue
    -> 远程调用分发器
    -> progress_signal / append_log_signal / preview_signal
    -> GUI 主线程更新进度、日志和预览
```

这里 Queue 负责跨进程传输，Qt Signal 负责让最终 UI 更新回到 GUI 线程。两个机制解决的不是同一件事，不能互相替代。

## 八、可运行练习：用 `QSignalBlocker` 实现单一状态来源

下面的控制器保存唯一的亮度值。滑块与输入框都只表达用户意图，刷新界面时用 `QSignalBlocker` 防止“程序设置值”再次被误认为“用户修改”。

```python
from PySide6.QtCore import QObject, QSignalBlocker, Signal
from PySide6.QtWidgets import QLineEdit, QSlider


class BrightnessState(QObject):
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self._value = 50

    def set_value(self, value: int):
        value = max(0, min(100, value))
        if value == self._value:
            return
        self._value = value
        self.changed.emit(value)


class BrightnessBinder(QObject):
    def __init__(self, state: BrightnessState, slider: QSlider, editor: QLineEdit):
        super().__init__()
        self.state, self.slider, self.editor = state, slider, editor
        slider.valueChanged.connect(state.set_value)
        editor.editingFinished.connect(self._commit_editor)
        state.changed.connect(self._render)
        self._render(state._value)

    def _commit_editor(self):
        try:
            self.state.set_value(int(self.editor.text()))
        except ValueError:
            self._render(self.state._value)

    def _render(self, value: int):
        slider_blocker = QSignalBlocker(self.slider)
        editor_blocker = QSignalBlocker(self.editor)
        try:
            self.slider.setValue(value)
            self.editor.setText(str(value))
        finally:
            slider_blocker.unblock()
            editor_blocker.unblock()
```

这里不直接让 `slider.valueChanged` 修改输入框、再让输入框的信号修改滑块。那样一旦多出默认值加载、撤销/重做或远程配置同步，循环关系会迅速失控。`BrightnessState` 是唯一真相；`_render` 只是它的投影。C++ 的 `QSignalBlocker` 是 RAII 风格的临时屏蔽器；在 Python 示例中显式以 `try/finally` 调用 `unblock()`，确保异常路径也能恢复信号状态。

## 九、C++ 底层视角：`moc` 生成的元对象与连接投递

在 C++ Qt 中，带 `Q_OBJECT` 的类经过 `moc` 处理后会拥有 `QMetaObject` 元数据、信号方法和可按名称/索引调用的槽。`emit progressChanged(42)` 不会神秘地“调用 Python 回调”；它会进入 Qt 的连接列表，根据连接类型直接调用或创建一个待投递的元调用事件。

```cpp
class Worker : public QObject {
    Q_OBJECT
signals:
    void progressChanged(int value);
};
```

PySide6 的 `Signal(int)` 对接的正是这套元对象系统。一个重要细节是连接类型由**发射信号时所在的线程**和**接收者 QObject 的 thread affinity**决定，而不是由“定义槽函数的 Python 文件”决定。只要接收者是 GUI 控件，跨线程更新就必须让调用排队进入 GUI 线程的事件循环。

## 总结

- 信号槽是 Qt 的观察者模式和跨线程通信基础。
- 跨对象边界用信号，内部算法用普通方法。
- GUI 控件只能在其所属 UI 线程更新。
- 事件用于底层输入/绘制，信号用于高层语义。
- 状态应有单一事实来源，避免控件之间相互直接同步。
- `QSignalBlocker` 适合刷新视图时抑制反馈；它不应替代清晰的状态所有权。
