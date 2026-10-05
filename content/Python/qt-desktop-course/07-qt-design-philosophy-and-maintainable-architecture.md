+++
date = '2026-10-04T21:07:00+08:00'
draft = false
title = 'Qt 的设计思想与可维护桌面架构：对象、消息、状态和边界'
+++
Qt 的 API 很大，但其设计思想并不杂乱。很多类名背后反复出现同几条原则：对象拥有明确生命周期；界面由组合形成；变化通过消息传播；数据与呈现分离；耗时工作离开 UI；平台差异藏在抽象之后。

理解这些原则，比记住某个控件的构造函数更能帮助你面对陌生需求。

## 一、组合优于继承

Qt 当然有继承：`QWidget`、`QMainWindow`、`QDialog`、自定义 model、delegate 都常需要继承。但页面组织不应靠不停制造“更复杂的窗口子类”。

更常见的健康结构是：

```text
MainWindow
├─ Navigation / Stack
│  ├─ ContentRepairPage
│  │  ├─ PreviewPanel
│  │  ├─ SettingsPanel
│  │  └─ TaskListPanel
│  └─ EnhancePage
│     ├─ PreviewPanel
│     └─ EnhanceOptionsPanel
└─ Application services
```

每个组件只负责一个区域，组合到上层。继承用于“是一个什么”，组合用于“由什么构成”。当一个页面同时管理 OCR、视频解码、模型下载、按钮状态和布局时，通常说明它需要拆服务或子组件，而不是再多继承一个类。

## 二、对象树表达所有权

Qt parent/child 不只是方便释放内存，也是一种所有权语言：

```text
窗口拥有页面
页面拥有控件
控件生命周期随页面结束
```

当一个对象不应随页面销毁，例如应用级配置、模型缓存服务、全局任务管理器，就不应随便设置为页面 child。把所有对象都挂到主窗口下面虽然省事，却会模糊谁该在何时释放。

## 三、消息驱动而非相互调用

信号槽体现的是发布—订阅思想：

```text
页面发起意图
    -> 服务处理
    -> 服务发布状态变化
    -> 多个视图各自响应
```

例如“任务进度变化”不属于某个按钮；任务列表、进度条、日志和预览都可能关心它。由任务服务发出 progress，由多个视图订阅，比让 worker 挨个持有这些控件引用更可扩展。

## 四、单一事实来源与状态机

一个任务最好具有显式状态：

```text
PENDING
  -> DETECTING
  -> WAITING_FOR_REVIEW
  -> PROCESSING
  -> COMPLETED / FAILED / CANCELLED
```

如果只靠“运行按钮是否禁用”“进度是否为 100”“某变量是不是 None”来推断状态，边界条件会不断增加。显式状态机的优点：

- UI 能从状态派生可用按钮；
- 日志和测试能验证合法迁移；
- 取消、重试、恢复更容易定义；
- 不会把业务流程埋在 if/else 的偶然组合里。

净绘工坊目前已有待处理、处理中、完成、失败等任务状态；下一步可将 OCR 确认也建模为更正式的状态迁移，而不是只依赖布尔字段。

## 五、命令与查询分离

一个实用习惯：

- **查询**：读取状态，不产生副作用；
- **命令**：改变状态，明确命名和输入。

```python
task = task_store.get_task(task_id)       # 查询
task_store.confirm_mask(task_id, plan)    # 命令
task_store.cancel(task_id)                # 命令
```

这让按钮槽函数变得很薄：读取用户意图，调用命令；而不是在槽函数中同时做校验、文件 I/O、模型加载、表格更新和异常处理。

## 六、依赖倒置：UI 不应认识模型细节

内容修复页真正需要的是“给图像和 mask，得到修复结果”的能力，不需要知道 LaMa 怎样加载 TorchScript。可以用协议表达：

```python
class InpaintEngine(Protocol):
    def inpaint(self, image_bgr, mask):
        ...
```

UI 选择模式，工厂创建引擎，业务层调用统一接口。这样新增模型不会迫使所有页面出现 `if mode == ...`。

同样，增强页只依赖 `enhance(image, scale)`，不应自己了解 RRDB、tile pad 或 checkpoint 键名。

## 七、错误是状态，不只是打印

桌面应用的错误至少有三个受众：

- 用户：需要简洁、可行动的信息；
- 开发者：需要异常栈、设备、输入、模式和上下文；
- 任务系统：需要将状态更新为 failed/cancelled，并清理资源。

因此不要只写：

```python
except Exception as exc:
    print(exc)
```

更好的流程：捕获异常 → 转换为领域错误 → 发送 IPC/Signal → 更新任务状态 → 提示用户 → 保留开发日志。

## 八、平台抽象与资源路径

Qt 本身跨平台，但应用仍会遇到：路径编码、系统代理、GPU、FFmpeg 二进制、字体和窗口行为差异。设计上应：

- 用 `pathlib.Path` 或 Qt 路径 API；
- 不把 Windows 绝对路径写进业务逻辑；
- 将平台特定实现放在边界层；
- 将资源、模型、配置和输出目录明确分开；
- 在打包前测试真实目标平台。

## 九、与净绘工坊的架构映射

```text
View: HomeInterface / EnhanceInterface / AdvancedSettingInterface
State: Task、TaskOptions、MaskPlan、Config
Services: SubtitleRemover、MediaEnhancer、ModelStore、VersionService
Engines: OpenCV / LaMa / Anime-LaMa / Manga / Real-ESRGAN
Boundary: Queue、Qt Signal、FFmpeg、PaddleOCR、PyTorch
```

这张映射图比“项目里有多少个 `.py` 文件”更能说明设计。它让你在新增功能时先问：这是页面、状态、服务、引擎还是外部边界？答案不同，文件位置和依赖方向也不同。

## 十、实战模板：让任务状态转换集中发生

下面的 store 不处理图像、不操作控件，也不启动线程；它只保存状态并拒绝非法迁移。worker 或进程回调把事件交给 controller，controller 再调用 store。这样“运行中还能否再次开始”“取消后能否标为完成”不再隐含在几个按钮的 enabled 状态里。

```python
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class TaskState(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class TaskRecord:
    task_id: str
    state: TaskState = TaskState.PENDING
    progress: int = 0
    error: str | None = None


class TaskStore(QObject):
    changed = Signal(str, object)  # task_id, TaskRecord
    _ALLOWED = {
        TaskState.PENDING: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.RUNNING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.COMPLETED: set(),
        TaskState.FAILED: set(),
        TaskState.CANCELLED: set(),
    }

    def __init__(self):
        super().__init__()
        self._records: dict[str, TaskRecord] = {}

    def add(self, task_id: str):
        if task_id in self._records:
            raise ValueError(f"重复任务：{task_id}")
        self._records[task_id] = TaskRecord(task_id)
        self.changed.emit(task_id, self._records[task_id])

    def transition(self, task_id: str, target: TaskState, error: str | None = None):
        record = self._records[task_id]
        if target not in self._ALLOWED[record.state]:
            raise ValueError(f"非法状态迁移：{record.state.name} -> {target.name}")
        record.state, record.error = target, error
        record.progress = 100 if target is TaskState.COMPLETED else record.progress
        self.changed.emit(task_id, record)

    def set_progress(self, task_id: str, value: int):
        record = self._records[task_id]
        if record.state is not TaskState.RUNNING:
            return
        record.progress = max(record.progress, min(value, 99))
        self.changed.emit(task_id, record)
```

`TaskStore.changed` 可以连接到 `TaskTableModel.update...`、进度条、日志面板和“开始/取消”按钮状态刷新。它不持有任一 `QLabel`，因而也可以在不启动 `QApplication` 的单元测试中检查状态迁移。产品代码需要增加“重试”时，只要显式加入 `FAILED -> PENDING` 的规则，而不是在四个页面各写一份例外判断。

## 十一、C++ 底层视角：所有权与 ABI 边界

在 C++ Qt 中，parent/child 是非拥有型原始指针形式的对象树；parent 析构时会删除 child。C++ 业务对象若同时被 `std::unique_ptr` 和 Qt parent 当作“唯一拥有者”，就可能双重释放。PySide6 虽然避免了你直接写 `delete`，仍要避免两套所有权同时接管同一个对象：长期服务要么明确由 Python 应用对象持有，要么明确成为某个 Qt parent 的 child，不要让页面、全局单例和后台回调都声称拥有它。

另一个容易被忽略的边界是 ABI。PySide6 wheel 已经带有与其绑定版本匹配的 Qt 运行库；不要在同一进程中随意加载另一个不兼容版本的 Qt C++ 插件或 DLL。插件、图像格式、平台插件的版本错配，往往表现为启动时找不到平台插件或在创建窗口后崩溃，而不是优雅的 Python 异常。

## 总结

- 用组合构建页面，用继承扩展 Qt 抽象。
- 用对象树表达生命周期，用状态机表达业务流程。
- 用信号表达变化，用服务承载业务，用协议隔离模型细节。
- UI 不应持有外部运行时细节；外部运行时也不应直接操作 UI。
- 架构不是为了画图，而是为了让新需求不会迫使旧页面全面失控。
- 用显式状态迁移收敛业务规则；按钮是否可用应是状态的结果，而不是状态的来源。
