+++
date = '2026-08-27T11:00:00+08:00'
draft = false
title = 'Python logging 日志库：从 basicConfig 到模块化、异常与文件轮转'
+++

程序输出一行 `print()` 很容易；让线上发生的问题能够被定位、被关联、又不把密码和令牌顺手泄露出去，则是另一回事。Python 标准库的 `logging` 正是为后一件事准备的。

它不要求先引入第三方框架，适合命令行工具、Web 服务、后台任务和自动化脚本。本文从最小可用配置开始，逐步说明日志级别、logger、handler、formatter、异常堆栈、文件轮转、配置边界与常见错误。

## 一、日志不是 `print()` 的复杂替身

`print()` 在临时调试时没有问题：

```python
print(f"request finished: status={status_code}")
```

但它很快会遇到边界：

- 无法按严重程度过滤输出。
- 不方便同时写到终端和文件。
- 输出格式、时间、模块名与请求上下文难以统一。
- 不能自然记录异常 Traceback。
- 测试和部署环境很难各自调整输出策略。
- 一旦把调试输出散落在业务代码中，之后很难有秩序地收回。

日志应记录系统运行过程中的事件和诊断信息。它通常服务于三个目的：

```text
运行观察：系统做了什么、速度如何、当前处于什么状态
故障排查：失败发生在哪里、输入与上下文是什么、原始异常是什么
审计追踪：关键动作何时发生、由哪个主体触发、作用于哪个对象
```

这不意味着什么都该写入日志。每个循环、每个对象、每个完整请求体都写一遍，只会让真正的异常被噪声埋掉。日志应当是证据，不是程序的自言自语。

## 二、五个最常用的日志级别

Python 默认常用的级别从低到高为：

| 级别 | 含义 | 典型用途 |
| ---- | ---- | -------- |
| `DEBUG` | 开发和深度排查细节 | 分支判断、缓存命中、耗时、输入摘要 |
| `INFO` | 正常运行中的重要事件 | 服务启动、任务完成、配置加载成功 |
| `WARNING` | 尚可继续，但值得关注的异常情况 | 使用降级配置、重试、接口返回非预期字段 |
| `ERROR` | 当前操作失败，需要调查 | 请求失败、任务失败、无法写入文件 |
| `CRITICAL` | 系统或关键功能无法继续 | 配置致命错误、关键依赖不可用、数据损坏 |

级别是一个阈值，不是五条完全独立的开关。若 logger 的有效级别是 `INFO`，它会处理 `INFO`、`WARNING`、`ERROR`、`CRITICAL`，忽略 `DEBUG`。

```python
import logging


logging.debug("读取到 %d 条缓存记录", 3)      # 默认看不到
logging.info("应用启动完成")                  # 默认也通常看不到
logging.warning("配置未设置 timeout，使用默认值")
logging.error("保存任务结果失败")
logging.critical("数据库连接池无法初始化")
```

模块级的 `logging.warning()` 等便利函数使用根 logger（root logger）。小脚本可以这样写；项目代码更推荐创建自己模块的 logger，后面会说明原因。

## 三、最小可用配置：`basicConfig`

在应用启动入口调用一次 `logging.basicConfig()`，就能把日志输出到标准错误流：

```python
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logging.info("application started")
```

输出类似：

```text
2026-08-27 11:00:00,123 INFO [root] application started
```

常用格式字段包括：

| 字段 | 含义 |
| ---- | ---- |
| `%(asctime)s` | 记录创建时间 |
| `%(levelname)s` | 级别名，如 `INFO` |
| `%(name)s` | logger 名称 |
| `%(message)s` | 最终格式化后的消息 |
| `%(filename)s`、`%(lineno)d` | 源文件名与行号 |
| `%(process)d`、`%(threadName)s` | 进程 ID 与线程名 |

可以通过 `datefmt` 控制时间格式：

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

`%(levelname)-8s` 让级别名称左对齐为固定宽度，主要是为了让终端输出更整齐。它不是必须项；可读性比格式技巧重要得多。

### 1. `basicConfig` 的调用位置

它应位于应用入口，而不是普通业务模块的导入阶段：

```python
# main.py
import logging

from app.service import run


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

原因是日志策略属于应用组合层：命令行、测试、Web 服务和任务进程可能需要不同的级别、输出位置和格式。库模块若在导入时自行配置根 logger，就会擅自改变整个进程的日志行为，像是不请自来的装修队。

另外，`basicConfig()` 默认只会在根 logger **尚未有 handler** 时生效。若测试框架、Web 框架或其他库已经配置过日志，后面的普通调用可能看似“没有效果”。Python 3.8+ 可以使用 `force=True` 重置根 logger：

```python
logging.basicConfig(level=logging.DEBUG, force=True)
```

这适合由程序入口明确接管日志配置的场景；在共享进程、Notebook 或库代码中要非常谨慎，因为它会移除既有根 handler。

## 四、项目中应使用 `logging.getLogger(__name__)`

在每个业务模块顶部创建命名 logger：

```python
import logging


logger = logging.getLogger(__name__)


def load_user(user_id: str) -> dict[str, object]:
    logger.info("loading user: user_id=%s", user_id)
    return {"id": user_id}
```

`__name__` 在模块被导入时通常是完整模块路径，例如 `app.services.user_service`。这样日志会自然携带来源：

```text
INFO [app.services.user_service] loading user: user_id=u-123
```

`getLogger()` 不会每次都随便新建一个不相干对象；同名 logger 在进程中表示同一个命名日志通道。名称可按点号形成层次：

```text
root
├── app
│   ├── app.api
│   └── app.services
│       └── app.services.user_service
└── urllib3
```

因此可以按模块或包名精细控制级别：

```python
logging.getLogger("app.services").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.WARNING)
```

前者只打开本项目服务层的调试信息，后者压低 HTTP 客户端的冗长输出。比起把全世界都调成 `DEBUG`，这显然更接近理性。

### 1. 库代码不要配置全局日志

可复用库一般只做：

```python
logger = logging.getLogger(__name__)
```

然后调用 `logger.debug()`、`logger.info()` 等，不调用 `basicConfig()`，通常也不自行添加输出 handler。由使用该库的应用决定日志最终去哪儿。

如果库在没有任何 handler 的环境下会直接使用根 logger 输出 `WARNING` 以上日志，且确实希望避免“找不到 handler”类提示，可以给库顶层 logger 添加 `NullHandler`：

```python
import logging


logging.getLogger(__name__).addHandler(logging.NullHandler())
```

这是一种面向库发布的惯例；普通单体应用一般不必为了它额外增加复杂度。

## 五、logger、handler、formatter 和 filter 的关系

`logging` 的组件可按这条路径理解：

```text
业务代码调用 logger.info(...)
  -> Logger 判断记录级别是否需要处理
  -> LogRecord 保存消息、时间、模块名、异常等信息
  -> Handler 决定输出到哪里，并可再次按级别过滤
  -> Formatter 决定记录显示成什么文本
  -> Filter 可补充或拒绝记录
```

其中最常用的三个角色是：

| 组件 | 负责什么 | 常见对象 |
| ---- | -------- | -------- |
| `Logger` | 接收记录、按名称组织、控制最低级别 | `logging.getLogger(__name__)` |
| `Handler` | 将记录发送到目标 | `StreamHandler`、`FileHandler`、轮转文件 handler |
| `Formatter` | 定义文本格式 | `logging.Formatter(...)` |

下面是同时输出到终端和文件的显式配置：

```python
import logging
from pathlib import Path


def configure_logging(log_path: Path) -> None:
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
```

这里根 logger 允许 `DEBUG` 及以上记录；终端 handler 从 `INFO` 开始显示；文件 handler 则保留更详细的 `DEBUG` 记录。一个日志事件可以被多个 handler 分别消费，所以同一条记录同时出现在两个位置是设计目标，不是重复。

但如果每次启动都重复执行 `configure_logging()`，handler 会不断累加，同一条日志也会重复打印。配置函数应只在明确的入口调用一次，或在重复配置前先设计清晰的清理策略。不要用“如果有 handler 就什么也不做”这种条件修补所有情况；测试、重载和多入口应用的需求并不完全相同。

## 六、延迟格式化：不要先写 f-string

推荐：

```python
logger.debug("parsed %d selectors for device=%s", len(selectors), device_id)
```

不推荐作为常规日志写法：

```python
logger.debug(f"parsed {len(selectors)} selectors for device={device_id}")
```

第一种写法将格式字符串和参数交给 `logging`。当 `DEBUG` 被当前级别过滤掉时，消息的 `%` 格式化通常不会发生；第二种 f-string 在调用 `logger.debug()` 前就会先求值。

对于简单值，性能差异往往不值得焦虑；但当参数包含昂贵计算、序列化或数据库查询时，延迟格式化能避免无意义的工作：

```python
logger.debug("payload=%r", build_debug_payload())  # 仍会先调用函数

if logger.isEnabledFor(logging.DEBUG):
    logger.debug("payload=%r", build_debug_payload())
```

要注意第一行仍会执行 `build_debug_payload()`，因为函数参数必须先被计算。延迟的是日志消息拼接，不是任意表达式。只有在确实昂贵时再加 `isEnabledFor`；每一行都套一层条件，只会让普通日志变得不必要地难读。

`%s` 使用 `str()` 风格，适合普通展示；`%r` 使用 `repr()`，对字符串里的换行、空格、不可见字符或对象表示更有帮助。日志格式化这里用的是 logging 的 `%` 风格占位，而不是 f-string 或 `.format()`；不要把三者混在一条消息里。

## 七、记录异常：`logger.exception`、`exc_info` 与 `stack_info`

发生异常时，只记录 `str(error)` 往往不够：

```python
try:
    config = load_config(path)
except ConfigError as error:
    logger.error("load config failed: %s", error)
```

这会留下错误消息，却没有发生错误的调用栈。更适合当前正处在 `except` 块内的写法是：

```python
try:
    config = load_config(path)
except ConfigError:
    logger.exception("load config failed")
    raise
```

`logger.exception()` 等价于以 `ERROR` 级别记录，并自动附带当前正在处理异常的 Traceback。它应在 `except` 块中使用；离开异常处理上下文再调用它，得到的并不是你想要的有效堆栈。

也可以显式写：

```python
logger.error("load config failed", exc_info=True)
```

`exc_info=True` 同样会附带当前异常信息，适合级别不想固定为 `ERROR` 的情况：

```python
except TemporaryNetworkError:
    logger.warning("request failed; retrying", exc_info=True)
```

而 `stack_info=True` 记录的是**当前调用位置的栈**，即使并没有异常：

```python
logger.warning("unexpected retry path", stack_info=True)
```

它适合追踪“为什么会执行到这里”；不要把它和 `exc_info` 混淆。`exc_info` 说明异常在哪里抛出，`stack_info` 说明日志调用发生在什么调用链中。

### 1. 在哪一层记录完整 Traceback

异常可能逐层向上传播。如果每一层都这样写：

```python
except Exception:
    logger.exception("failed")
    raise
```

同一异常会被打印多份完整堆栈，结果只是消耗存储并污染告警。通常应选择一个边界记录完整异常：例如命令行 `main()`、HTTP 请求的统一异常处理器，或任务消费者入口。

中间层若需要补充语义，通常只转换异常并保留原因：

```python
try:
    payload = response.json()
except ValueError as error:
    raise UpstreamResponseError("接口响应不是合法 JSON") from error
```

上层最终记录时，异常链会给出完整原因。异常是要传播的信息，日志是一次有选择的落笔；两者无需在每一层重复做同一件事。

## 八、写入文件与轮转：不要让一个日志文件无限长

最直接的文件日志可以用 `FileHandler`：

```python
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
```

它会持续向同一个文件追加内容。对于短命令行脚本足够，但常驻服务需要控制文件大小和数量。标准库 `logging.handlers` 提供了轮转 handler。

### 1. 按文件大小轮转

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def build_file_handler(log_dir: Path) -> RotatingFileHandler:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
    )
    return handler
```

当 `app.log` 即将超过 10 MiB 时，handler 会轮转旧文件，保留最多五个备份。实际文件名通常形如：

```text
app.log
app.log.1
app.log.2
...
```

`backupCount` 不是装饰：它决定旧日志何时被删除。大小阈值和保留份数应根据写入量、排障窗口、磁盘预算和合规要求决定，而不是因为 10 和 5 看起来恰好顺眼。

### 2. 按时间轮转

若运维习惯按天查看日志，可以使用 `TimedRotatingFileHandler`：

```python
from logging.handlers import TimedRotatingFileHandler


handler = TimedRotatingFileHandler(
    "logs/app.log",
    when="midnight",
    interval=1,
    backupCount=14,
    encoding="utf-8",
    utc=True,
)
```

这会按 UTC 的午夜轮转并保留 14 个旧文件。是否使用 UTC 是一个系统级决定：分布式服务、跨时区排障时 UTC 更容易关联；面向单一地区人工查看的程序也可能选择本地时间。关键是团队统一，别让同一事故的两份日志各自活在不同的时间宇宙里。

在多进程、高并发写入同一个本地文件的场景下，标准轮转 handler 并不是通用的跨进程协调方案。生产服务往往将日志写到标准输出，由容器平台、系统日志服务或专业采集器负责汇总与轮转；或者使用专门支持并发轮转的方案。不要因为它“能写文件”就默认它能解决所有部署模型。

## 九、给日志补充上下文

一条没有上下文的日志：

```text
ERROR request failed
```

通常几乎没有诊断价值。更好的日志至少带上排查需要的标识：请求 ID、任务 ID、用户 ID 的安全标识、设备序列号、目标资源和耗时。

最简单的方式是在消息参数中传递：

```python
logger.info(
    "task completed: task_id=%s device_id=%s duration_ms=%d",
    task_id,
    device_id,
    duration_ms,
)
```

若同一个上下文会在一段调用链中反复使用，可以用 `LoggerAdapter`：

```python
import logging


base_logger = logging.getLogger(__name__)
task_logger = logging.LoggerAdapter(base_logger, {"task_id": "task-42"})

task_logger.info("started")
task_logger.info("finished")
```

此时 formatter 需要引用附加字段：

```python
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s [task_id=%(task_id)s] %(message)s"
)
```

但有一个陷阱：如果同一个 handler 也处理没有 `task_id` 的普通记录，格式化时会因为缺少该字段失败。可为所有记录提供默认值、为特定 logger 使用独立 handler，或在 `Filter` 中统一注入上下文。项目规模较小时，直接在消息中写关键 ID 往往更稳；当请求/任务上下文需要跨多层传递时，再引入 `LoggerAdapter`、`Filter` 或基于 `contextvars` 的方案。

`extra` 也可为单条记录添加字段：

```python
logger.info(
    "task completed",
    extra={"task_id": task_id, "duration_ms": duration_ms},
)
```

不要用 `extra` 覆盖 `LogRecord` 已有属性，例如 `name`、`message`、`levelname`；这会抛出错误。并且同样要保证 formatter 所用的自定义字段在每条记录中都存在。

## 十、结构化日志与 JSON

纯文本日志适合人直接阅读：

```text
2026-08-27 11:00:00 INFO [app.tasks] task completed: task_id=t-42 duration_ms=318
```

若日志会被 ELK、Loki、Cloud Logging 等平台采集和查询，JSON 结构化日志往往更便于按字段过滤和聚合：

```json
{"time":"2026-08-27T03:00:00Z","level":"INFO","logger":"app.tasks","event":"task_completed","task_id":"t-42","duration_ms":318}
```

标准库没有内置 JSON formatter，但可以自定义：

```python
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
```

实际项目通常还会统一事件名、请求 ID、服务名、部署版本和字段命名规则。结构化日志不是把原来的整句话塞进 JSON 字符串就结束了；字段应有稳定语义，才能支持可靠查询。

是否需要 JSON 取决于日志消费者：若只是个人脚本的终端输出，整洁文本更轻；若会被机器查询、告警和统计，结构化形式更合适。先确定谁在读日志，再决定日志长什么样。

## 十一、日志与敏感信息

日志通常会被集中保存、被更多人读取、保留更久，因此其敏感性常被低估。以下信息默认不应完整写入日志：

- API token、密码、Cookie、会话 ID、Authorization 请求头。
- 身份证件、银行卡、手机号、邮箱等个人信息，除非确有合规依据且已做脱敏。
- 完整请求体、完整响应体、数据库连接串。
- 可能包含用户数据或内部实现细节的异常消息。

错误示例：

```python
logger.info("calling api with token=%s", config["api"]["token"])
```

可以记录安全摘要：

```python
token = config["api"]["token"]
logger.debug("API token configured: suffix=%s", token[-4:])
```

前提是令牌长度已被校验，或先安全处理长度不足的情况。更稳妥的选择是只记录“令牌已配置”，根本不展示任何片段。脱敏策略取决于数据分类和威胁模型；不要指望一个 `***` 代替真正的设计。

## 十二、常见错误与改进

### 1. 在库模块中调用 `basicConfig`

错误：

```python
# library_module.py
logging.basicConfig(level=logging.DEBUG)
```

它会影响所有导入这个模块的应用。库模块只获取命名 logger；由程序入口配置 handler、级别和格式。

### 2. 对同一 logger 重复添加 handler

错误：

```python
def get_logger():
    logger = logging.getLogger("app")
    logger.addHandler(logging.StreamHandler())
    return logger
```

每调用一次就多一个 handler，日志会逐渐重复。应只在启动配置阶段添加一次，或由明确的配置生命周期负责移除和关闭旧 handler。

### 3. 忘记 logger 的传播（propagation）

命名 logger 默认会把记录向父 logger 一路传播到 root。若你同时给 `app` logger 添加 handler，又给 root 添加 handler，同一条记录可能出现两次。

```python
app_logger = logging.getLogger("app")
app_logger.propagate = False
```

只有当 `app` 自己的 handler 已完整负责输出、且你确定不希望继续交给父 logger 时，才设置 `propagate = False`。这不是“去重按钮”，而是改变日志路由的开关；先弄清 handler 装在何处，再决定是否关闭传播。

### 4. 捕获所有异常后只记录不处理

```python
try:
    run_task()
except Exception:
    logger.exception("task failed")
```

记录后如果什么也不做，程序会继续运行，调用方可能误以为任务成功。应明确决定恢复、重试、返回失败状态或重新抛出：

```python
try:
    run_task()
except TaskError:
    logger.exception("task failed")
    raise
```

入口处若要将错误转成退出码，也应清楚地 `return 1` 或 `raise SystemExit(1)`。日志不等于错误处理。

### 5. 用日志拼接处理用户输入

用户输入可能含有换行和控制字符，直接拼接会影响日志的可读性，甚至造成日志注入式的误导：

```python
logger.info("login failed for user=%r", user_name)
```

`%r` 会以对象表示形式记录字符串，使换行等字符可见。更重要的是，对来自外部的高敏感字段先做验证和脱敏；日志不是原始输入的备份仓库。

### 6. 只靠字符串做机器判断

```python
if "timeout" in log_line:
    retry()
```

日志面向人类与观测系统，文案会变、会本地化、会被截断。程序控制流应该依靠异常类型、返回值、状态码和明确事件字段；日志可以记录决策，不能替代决策协议。

## 十三、一个适合小型应用的起点

对于一个普通命令行或自动化程序，可以从下面的约定开始：

```python
# logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, *, verbose: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
```

入口调用：

```python
# main.py
import logging
from pathlib import Path

from app.logging_setup import configure_logging
from app.service import run


def main() -> int:
    configure_logging(Path("logs"), verbose=False)
    logger = logging.getLogger(__name__)

    try:
        run()
    except Exception:
        logger.exception("application terminated unexpectedly")
        return 1
    else:
        logger.info("application finished successfully")
        return 0
```

业务模块只需要：

```python
import logging


logger = logging.getLogger(__name__)
```

然后在合适的位置写有意义的记录。这个结构将“日志如何输出”的政策集中在入口，将“发生了什么”的事实留给业务模块，足以覆盖很多项目的第一阶段需求。

上例在 `configure_logging()` 中使用 `root.handlers.clear()`，是因为它明确承担“重新建立本应用根日志配置”的职责。若已有 handler 持有文件或网络等资源，重配前还应关闭它们；在复杂应用中也可交由 `logging.config.dictConfig()` 统一声明式管理。不要把这段重置逻辑复制到普通模块里。

## 十四、总结

Python 的 `logging` 可以用下面的关系串起来：

```text
模块使用 getLogger(__name__) 记录事件
  -> 应用入口配置级别、handler 和 formatter
  -> handler 决定输出到终端、文件或日志平台
  -> 异常边界用 logger.exception 保留 Traceback
  -> 关键上下文帮助关联问题，敏感信息必须脱敏
```

实践中最值得坚持的几条规则是：

- 在模块中使用 `logger = logging.getLogger(__name__)`，不要随意配置全局日志。
- 在应用入口集中配置 `basicConfig` 或 handlers。
- 用正确级别区分正常事件、可恢复异常和失败；不要把一切都记成 `INFO` 或 `ERROR`。
- 使用 `logger.info("value=%s", value)` 这类参数化格式，避免无谓的 f-string 计算。
- 在最终异常边界使用 `logger.exception()`，避免在每一层重复打印完整 Traceback。
- 为长运行程序配置轮转和保留策略，别让日志文件无止境生长。
- 将令牌、密码、Cookie 和个人数据视为默认禁止记录的信息。

日志设计得好，问题发生后就不必靠猜测去复原现场；日志设计得差，留下的只是一大堆时间戳和无辜的 `failed`。前者是工程，后者只是噪声。
