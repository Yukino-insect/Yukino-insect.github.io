+++
date = '2026-10-04T21:06:00+08:00'
draft = false
title = 'Qt 与 Python 多进程 IPC：模型任务、Queue 与安全回到 GUI'
+++
当桌面应用开始加载 OCR、深度学习模型、GPU 运行时和 FFmpeg 时，“放进线程”可能仍然不够。模型占用的内存如何释放？CUDA OOM 后 GUI 是否还活着？用户点击停止如何真正结束任务？Windows 的 `spawn` 会不会重新导入整个应用？这些问题通常需要进程隔离。

Qt 不负责 Python 多进程；它负责 GUI 事件和线程边界。工程上常见的组合是：**子进程做重活，Queue 传跨进程消息，Qt Signal 把消息安全送回 UI。**

## 一、线程和进程的边界

| 对比项 | 线程 | 进程 |
| --- | --- | --- |
| 地址空间 | 共享 | 隔离 |
| 传递对象 | 可直接共享引用，但需同步 | 必须序列化或 IPC |
| 崩溃影响 | 可能拖垮整个 GUI | 通常可局部失败/终止 |
| 模型/GPU 隔离 | 较弱 | 较强 |
| 创建开销 | 较低 | 较高 |
| 适合 | I/O、轻量任务、UI 协作 | 模型推理、CPU 密集、可终止的外部任务 |

进程不是越多越好。它的价值是明确资源与故障边界。

## 二、Windows 的 `spawn` 模式

Windows 常用 `spawn`：启动子进程时会重新启动 Python 解释器并导入模块，而不是复制父进程内存。因此必须：

```python
if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    main()
```

还要避免：

- 在模块顶层启动子进程；
- 将不可 pickle 的 Qt widget、lambda、打开的文件句柄传给子进程；
- 在 GUI 进程预先加载大模型后期待子进程自动复用。

正确做法是向子进程传路径、字典、列表、数值等可序列化数据，并在子进程中惰性加载模型。

## 三、消息协议比“随便 put 一个对象”更重要

跨进程 Queue 适合传递小型消息：

```python
from enum import Enum

class Command(Enum):
    PROGRESS = 1
    LOG = 2
    PREVIEW = 3
    ERROR = 4
    FINISH = 5

queue.put((Command.PROGRESS, (42, False)))
```

优点：

- 消息类型明确；
- UI 层只需按 command 分发；
- 日志、进度、错误和完成状态不会混在一个不透明对象中；
- 日后可以增加任务 ID、时间戳和协议版本。

不建议频繁通过 Queue 传送超大图片数组。高分辨率帧会增加 pickle、复制和内存压力。可以采样预览、缩小后发送，或限制更新频率。

## 四、Queue 与 Qt Signal 的桥接

子进程发给 Queue 的消息仍不能直接改 UI。父进程可以有一个后台监听线程：

```text
child process
    -> multiprocessing.Queue
listener thread
    -> Qt Signal
GUI thread slot
    -> update widgets
```

这是一种桥接模式：

- Queue 解决跨进程传输；
- Qt Signal 解决跨线程回到 GUI 事件循环；
- View 只接触 UI 安全的槽函数。

## 五、进度、错误和退出的可靠性

一个任务协议至少应考虑：

- `PROGRESS`：当前进度与是否完成；
- `LOG`：用户可见日志；
- `ERROR`：可读异常和任务上下文；
- `FINISH`：子进程自然结束；
- `CANCELLED`：用户取消而非算法失败；
- 子进程 `exitcode`：即使没发 finish，也可判断异常退出。

父进程不能只相信“收到了 100%”。例如子进程可能在写文件后崩溃；也不能只看 `exitcode == 0`，因为业务可能把错误吞掉。应综合输出文件存在性、消息、异常和 exit code。

## 六、净绘工坊的 IPC 实战

内容修复页中：

1. GUI 将已确认的 `MaskPlan`、修复模式、设备、输出路径、A/B 区间等序列化为 task options；
2. `multiprocessing.Process` 创建子进程；
3. 子进程创建 `SubtitleRemover`，在进程内加载 OCR/Torch 模型；
4. 子进程通过 Queue 发送进度、日志、错误与原/修复预览；
5. 父进程的远程调用分发器将消息转换成 Qt Signal；
6. GUI 槽函数更新进度条、任务状态和预览。

这里 `MaskPlan` 的可序列化设计非常关键。子进程不需要知道黄色 ROI 控件、表格行对象或窗口比例；它只需要知道最终 OCR 多边形、手工区域、模式和参数。

## 七、何时不需要进程

如果任务只是读取一个小 JSON、计算文本长度、加载缩略图或做短时间 I/O，进程会带来额外复杂度。先问：

- 是否会长时间占用 CPU/GPU？
- 是否需要能强制终止？
- 是否加载容易污染全局状态的第三方运行时？
- 崩溃是否不能影响 GUI？
- 传输的数据是否比计算本身还重？

不是每个后台任务都值得开一个进程。

## 八、可运行练习：一个有协议、可取消的进程消息桥

以下代码刻意只传递字符串、整数和字典；GUI 对象、`QPixmap`、打开的文件和模型实例都不会越过进程边界。`QueueBridge` 在普通 Python 监听线程中阻塞读取 Queue，再通过 Qt signal 把消息交给 GUI 线程。

```python
import multiprocessing as mp
import queue
import threading
import time

from PySide6.QtCore import QObject, Signal


def child_main(job: dict, messages: mp.Queue, cancel: mp.Event):
    """必须定义在模块顶层，Windows spawn 才能 pickle 到子进程。"""
    try:
        for step in range(1, 101):
            if cancel.is_set():
                messages.put(("cancelled", {"job_id": job["id"]}))
                return
            time.sleep(0.02)  # 替换为模型推理、转码或 CPU 计算
            if step % 5 == 0:
                messages.put(("progress", {"job_id": job["id"], "value": step}))
        messages.put(("finished", {"job_id": job["id"], "output": job["output"]}))
    except Exception as exc:
        messages.put(("error", {"job_id": job["id"], "message": repr(exc)}))


class QueueBridge(QObject):
    message_received = Signal(str, object)

    def __init__(self, messages: mp.Queue):
        super().__init__()
        self._messages = messages
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stopping.set()
        self._thread.join(timeout=1)

    def _listen(self):
        while not self._stopping.is_set():
            try:
                kind, payload = self._messages.get(timeout=0.2)
            except queue.Empty:
                continue
            self.message_received.emit(kind, payload)


if __name__ == "__main__":
    mp.freeze_support()  # 打包成 Windows 可执行文件时尤其需要
    ctx = mp.get_context("spawn")
    messages, cancel = ctx.Queue(), ctx.Event()
    job = {"id": "task-7", "input": "input.mp4", "output": "output.mp4"}
    process = ctx.Process(target=child_main, args=(job, messages, cancel))
    process.start()
```

在窗口中创建 `bridge = QueueBridge(messages)` 后，连接 `bridge.message_received.connect(self.on_process_message)`；`on_process_message` 运行在 GUI 线程，可以安全更新表格和进度条。窗口关闭时的顺序应是：设置 `cancel` → 等待一段合理时间 → 仍未退出时 `process.terminate()` → `process.join()` → `bridge.stop()` → 关闭 Queue。这样“正常取消”和“不得已终止”会有不同的日志和状态，不会被混为失败。

不要使用 `Queue.empty()` 作为控制逻辑：它是瞬时观察，在多进程下会竞态。阻塞 `get(timeout=...)` 才能让监听线程既不忙等，又能及时响应关闭请求。

## 九、C++/Qt 底层视角：何时使用 `QProcess`

Python `multiprocessing` 与 Qt C++ 的 `QProcess` 解决的边界并不完全相同。若工作单元本来就是外部可执行程序（例如 `ffmpeg`、命令行 OCR、独立 Rust/C++ 工具），优先考虑 `QProcess`：它把标准输出、标准错误、启动失败和进程结束事件纳入 Qt 事件循环，避免手写 Queue 协议。

```cpp
auto *process = new QProcess(this);
connect(process, &QProcess::readyReadStandardError, this, [process] {
    appendLog(process->readAllStandardError());
});
connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
        this, &Window::onEncoderFinished);
process->start("ffmpeg", {"-i", input, output});
```

PySide6 同样可使用 `QProcess`。而需要把 Python 函数、PyTorch 模型或 Python-only 对象隔离出去时，`multiprocessing` 更合适。不要为“看起来更 Qt”而强行用 `QProcess` 启动另一个 Python 解释器；选择依据是任务的天然边界与可观测性。

## 总结

- 进程提供内存、故障和资源隔离。
- Windows `spawn` 要求入口保护和可序列化参数。
- Queue 应传小而明确的协议消息，不应滥传大数组。
- Qt Signal 是将 IPC 结果安全带回 GUI 主线程的最后一段桥梁。
- `MaskPlan` 这类纯数据对象使 GUI 与子进程真正解耦。
- 外部命令行工具适合 `QProcess`；Python 模型和 Python CPU 任务通常更适合 `multiprocessing`。
