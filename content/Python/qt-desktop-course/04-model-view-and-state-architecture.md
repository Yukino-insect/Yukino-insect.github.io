+++
date = '2026-10-04T21:04:00+08:00'
draft = false
title = 'Qt Model/View 与状态架构：让列表、表格和业务数据各司其职'
+++
如果列表只有三行，直接往 `QTableWidget` 塞单元格很方便。但当数据需要排序、筛选、分页、后台更新、复用到多个视图，或者每一行都有状态和操作时，把业务数据直接塞进控件会迅速变得难以维护。

Qt 的 Model/View 设计把“数据是什么”和“如何显示”分开。它不是为了让代码更抽象而抽象，而是为了让数据变化能够有明确、可增量更新的传播路径。

## 一、三类角色

```text
Model      数据、角色、增删改通知
View       QListView / QTableView / QTreeView，负责展示和选择
Delegate   负责单元格绘制与编辑体验
```

一个 model 可以被多个 view 共享；一个 view 可以替换 model；delegate 可以让同一份数据以不同方式绘制。这是典型的“数据与表现分离”。

## 二、`QModelIndex` 与角色（Role）

Qt 不要求 model 把一行数据直接暴露成 Python 对象。view 会通过 `QModelIndex(row, column)` 和 role 查询数据：

```python
def data(self, index, role):
    task = self._tasks[index.row()]
    if role == Qt.DisplayRole:
        return task.name
    if role == Qt.ToolTipRole:
        return task.full_path
    if role == Qt.ForegroundRole and task.failed:
        return QColor("#e74c3c")
```

常见 role：

| Role | 作用 |
| --- | --- |
| `DisplayRole` | 显示文字。 |
| `DecorationRole` | 图标。 |
| `ToolTipRole` | 悬停提示。 |
| `EditRole` | 编辑值。 |
| `ForegroundRole` / `BackgroundRole` | 颜色。 |
| `UserRole` 及以上 | 自定义业务数据。 |

这让同一个任务既能显示短文件名，又能通过 tooltip 保留完整路径；不需要在业务对象中混入 QLabel 的细节。

## 三、为什么 model 必须发出正确通知

view 不会轮询数据。model 修改后要调用正确的 begin/end 方法或发出 `dataChanged`：

```python
def update_progress(self, row, progress):
    self._tasks[row].progress = progress
    index = self.index(row, self.PROGRESS_COLUMN)
    self.dataChanged.emit(index, index, [Qt.DisplayRole])
```

插入/删除行时使用：

```python
self.beginInsertRows(QModelIndex(), row, row)
self._tasks.insert(row, task)
self.endInsertRows()
```

如果直接修改列表却不通知 model，view 的行号、选择状态和缓存可能失效。Model/View 的纪律在于：**数据变更必须伴随结构或数据变更通知。**

## 四、`QTableWidget` 与 `QTableView` 如何选择

| 场景 | 更适合 |
| --- | --- |
| 小型、静态、快速原型表格 | `QTableWidget`。 |
| 任务队列、文件列表、复杂状态 | `QTableView + QAbstractTableModel`。 |
| 大量数据、排序/过滤/分页 | Model/View + proxy model。 |
| 自定义单元格、进度条、按钮 | delegate 或自定义 view。 |

净绘工坊当前任务列表使用 `TableWidget` 管理有限任务，开发速度较快；若以后需要持久化队列、批量筛选、上千个媒体文件、可排序列或后台增量刷新，升级为 `QAbstractTableModel` 会更合适。

## 五、MVC、MVVM 与 Qt 的实际落地

不要把 MVC/MVVM 当成必须严格命名的教条。更重要的是控制依赖方向：

```text
Domain / Task 数据
       ↓
Model 或 ViewModel
       ↓
Widget / View
       ↑
用户意图（按钮、菜单、快捷键）
```

在 Qt Widgets 中，一个实用分层是：

- **Domain/Service**：媒体任务、OCR 计划、修复引擎、输出路径；
- **Model/Controller**：任务状态、页面协调、后台回调；
- **View**：按钮、标签、表格、预览；
- **Worker**：OCR、模型、编码等耗时实现。

View 不应直接启动 `ffmpeg`、加载 AI 权重或修改全局配置；它只收集输入并发出意图。这样同一业务可被 GUI、CLI 或测试重复使用。

## 六、状态所有权：一个重要但常被忽略的设计思想

每一份状态都应能回答“谁拥有它、谁可以修改它、谁观察它”。例如：

| 状态 | 合理拥有者 |
| --- | --- |
| 当前媒体路径 | 页面/任务对象。 |
| 已确认的 OCR 掩膜计划 | Task 或独立 `MaskPlan`。 |
| 进度与状态 | 任务模型。 |
| 模型缓存路径 | 应用配置。 |
| 某个按钮是否禁用 | View，根据任务状态派生。 |

当按钮自己保存业务状态、后台线程直接改表格、配置和任务都保存同一字段时，系统会出现多个“真相来源”。这种 bug 往往不是立即崩溃，而是偶发地显示旧状态，最难排查。

## 七、与当前项目的联系

净绘工坊的 `Task` 保存路径、进度、状态和选项；`TaskOptions` 记录掩膜计划、模式、设备和 A/B 区间。这个方向是正确的：修复子进程只接收任务数据，而不是接收 GUI 控件。

下一步若继续演进，可将 `TaskListComponent` 从 `QTableWidget` 迁移到自定义 `QAbstractTableModel`，让任务状态的改变通过 model 信号驱动表格刷新，而不是手动找每个 `QTableWidgetItem` 修改文本。

## 八、可运行练习：实现一个真正会增量刷新的任务模型

下面的模型只实现三个显示列，却覆盖了 `QAbstractTableModel` 最重要的约定：先通知再改变结构；只改变一个单元格时只发射那个单元格的 `dataChanged`；状态不是散落在 table item 中，而是放在纯数据对象里。

```python
from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


@dataclass
class Task:
    name: str
    source_path: str
    progress: int = 0
    state: str = "等待中"


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
            return (task.name, f"{task.progress}%", task.state)[index.column()]
        if role == Qt.ToolTipRole and index.column() == self.NAME:
            return task.source_path
        if role == Qt.ForegroundRole and task.state == "失败":
            return QColor("#c0392b")
        if role == Qt.TextAlignmentRole and index.column() == self.PROGRESS:
            return Qt.AlignCenter
        return None

    def append_task(self, task: Task):
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()

    def update_progress(self, row: int, progress: int):
        task = self._tasks[row]
        progress = max(0, min(100, progress))
        if task.progress == progress:
            return
        task.progress = progress
        index = self.index(row, self.PROGRESS)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def finish(self, row: int, state: str):
        self._tasks[row].state = state
        index = self.index(row, self.STATE)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ForegroundRole])
```

把它接到界面只需要三行：`view = QTableView()`、`model = TaskTableModel(view)`、`view.setModel(model)`。例如 `model.append_task(Task("示例.png", "/tmp/示例.png"))` 后，view 会收到插入通知并创建新行；`model.update_progress(0, 42)` 则只请求重绘进度单元格。没有 `view.repaint()`，也没有遍历控件树去找某个文本框——这才是 Model/View 的价值。

注意后台 worker 不能直接调用这些 model 方法。model 通常属于 GUI 线程，应让 worker 发射 `(task_id, progress)`，由 GUI 线程中的协调器定位 `row` 后调用 `update_progress`。第 5 篇会把这条边界落到完整代码中。

## 九、C++ 底层视角：model 通知是视图一致性的事务边界

`beginInsertRows()` / `endInsertRows()` 不是装饰性的仪式。Qt C++ view、selection model、proxy model 和 persistent index 会在 begin/end 之间更新内部行映射；如果先改 Python 列表再通知，观察者看到的数据范围已经不一致，排序、选中项和代理模型就可能发生难以复现的错误。

Qt C++ 的典型实现与上面的 Python 结构一一对应：

```cpp
beginInsertRows(QModelIndex(), row, row);
tasks_.push_back(task);
endInsertRows();
```

`QModelIndex` 本身是轻量的定位句柄，不应长期当作稳定 ID 保存：排序、筛选、插入行后它的位置可能变化。业务层应保存自己的 `task_id`；需要在模型变化后追踪某个可见位置时，才考虑 `QPersistentModelIndex`。

## 总结

- Model/View 分离数据、展示与绘制，适合复杂列表和表格。
- `QModelIndex` + role 是 Qt 查询数据的通用协议。
- 数据修改必须通知 view，不能偷偷改底层列表。
- MVC/MVVM 的重点是依赖方向和状态所有权，而不是目录名。
- 小项目可以从 item widget 起步，但应知道何时需要迁移到 model。
- `begin...` / `end...` 与 `dataChanged` 是模型和 view 保持一致的协议，不是可省略的样板代码。
