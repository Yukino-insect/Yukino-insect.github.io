+++
date = '2026-08-20T19:13:00+08:00'
draft = false
title = 'Python 模块与导入：import、包、局部导入与可选依赖'
+++

Python 的 `import` 看起来很简单：

```python
import math
```

但真实项目里，你很快会遇到更多问题：为什么可以在函数里面导入？为什么 `import` 可以放进 `try`？为什么有时相对导入失败？为什么两个模块互相导入会出错？为什么导入一个模块竟然会执行代码？

这些问题并不偏门。只要项目从一个文件变成多个文件，它们就会出现。模块系统不是装饰，它决定代码如何组织、依赖如何表达、初始化何时发生。

## 一、模块是什么

Python 中，一个 `.py` 文件通常就是一个模块。

例如：

```text
project/
  math_utils.py
  main.py
```

`math_utils.py`：

```python
def add(a, b):
    return a + b
```

`main.py`：

```python
import math_utils

print(math_utils.add(1, 2))
```

导入模块后，通过模块名访问里面的函数：

```python
math_utils.add(1, 2)
```

这种写法的好处是来源清楚。看到 `math_utils.add`，就知道 `add` 来自哪个模块。

## 二、import 做了什么

执行：

```python
import math_utils
```

大致会发生：

```text
查找 math_utils 模块
 -> 如果还没加载，执行 math_utils.py
 -> 创建模块对象
 -> 把模块对象缓存到 sys.modules
 -> 在当前作用域绑定名字 math_utils
```

也就是说，导入模块时会执行模块顶层代码。

```python
# config.py
print("config loaded")

DEBUG = True
```

导入：

```python
import config
```

会输出：

```text
config loaded
```

所以模块顶层不要随便写有副作用的业务逻辑。定义函数、类、常量可以；直接连接数据库、启动任务、发请求，就要谨慎。

## 三、模块缓存 sys.modules

Python 不会每次 `import` 都重新执行模块。

```python
import sys
import math_utils

print(sys.modules["math_utils"])
```

第一次导入时，模块会被加载并执行。之后再次导入，通常直接从 `sys.modules` 里取缓存。

示例：

```python
import config
import config
import config
```

`config.py` 顶层代码通常只执行一次。

这个缓存机制能避免重复初始化，也解释了为什么模块级单例、配置对象、日志对象经常放在模块顶层。

但它也带来一个边界：如果你修改了模块文件，正在运行的 Python 进程不会自动重新加载它。开发服务器热重载、Notebook 重新执行单元格、`importlib.reload()` 都是在处理这个问题。

## 四、from import

可以从模块中导入指定名字：

```python
from math_utils import add

print(add(1, 2))
```

这会把 `add` 绑定到当前作用域。

对比：

```python
import math_utils

math_utils.add(1, 2)
```

两种写法都可以。

建议：

- 模块名能提供上下文时，用 `import module`。
- 导入少量清晰函数或类时，可以用 `from module import name`。
- 避免过度导入导致当前文件名字来源混乱。

例如：

```python
from pathlib import Path
from datetime import datetime
```

这种很常见，也很清楚。

## 五、as 重命名

可以用 `as` 给模块或对象起别名。

```python
import numpy as np
import pandas as pd
```

也可以：

```python
from datetime import datetime as DateTime
```

别名应该服务于清晰，而不是制造个人暗号。

常见约定：

| 导入 | 约定别名 |
| ---- | -------- |
| `numpy` | `np` |
| `pandas` | `pd` |
| `matplotlib.pyplot` | `plt` |

如果没有社区约定，不要随便把模块名缩成看不懂的两个字母。代码不是密码本。

## 六、不要滥用 import *

Python 支持：

```python
from math_utils import *
```

这会把模块中可导出的名字导入当前作用域。

问题是：

- 看不出名字来自哪里。
- 容易覆盖当前已有名字。
- 静态分析和重构更困难。
- 阅读代码时需要猜。

不推荐在普通业务代码中使用。

更清楚：

```python
from math_utils import add, multiply
```

或：

```python
import math_utils
```

`import *` 在交互式探索、某些框架约定或包入口控制得很严格时可能出现，但它不应该成为日常习惯。

## 七、包是什么

包是包含多个模块的目录。

```text
project/
  app/
    __init__.py
    services/
      __init__.py
      user_service.py
    repositories/
      __init__.py
      user_repository.py
```

`__init__.py` 表示这个目录是一个普通包。现代 Python 也支持没有 `__init__.py` 的命名空间包，但初学和业务项目里，保留 `__init__.py` 通常更直观。

导入：

```python
from app.services.user_service import get_user
```

包的作用是组织命名空间：

```text
services.user_service
repositories.user_repository
```

这样项目变大后，不同模块不至于都挤在根目录下。

## 八、__init__.py 的作用

`__init__.py` 会在导入包时执行。

```python
# app/__init__.py
print("app package loaded")
```

导入：

```python
import app
```

会执行 `app/__init__.py`。

它常见用途：

- 标记普通包。
- 暴露包级 API。
- 定义包版本。
- 做少量轻量初始化。

例如：

```python
# app/services/__init__.py
from .user_service import get_user
from .post_service import get_post

__all__ = [
    "get_user",
    "get_post",
]
```

调用：

```python
from app.services import get_user
```

注意：`__init__.py` 不应该塞太多重逻辑。导入包就执行复杂初始化，会让依赖关系变得很沉。

## 九、绝对导入

绝对导入从项目包名或顶层模块开始写。

```python
from app.services.user_service import get_user
from app.repositories.user_repository import UserRepository
```

优点：

- 路径清楚。
- 移动文件时更容易发现影响。
- 不依赖当前文件所在层级。

业务项目里，绝对导入通常更推荐。

前提是项目以包的方式运行，且项目根目录在 `sys.path` 或安装环境中。

## 十、相对导入

相对导入使用点号表示当前位置。

```python
from .user_repository import UserRepository
from ..core.config import settings
```

含义：

```text
.   当前包
..  上一级包
```

相对导入只能在包内部使用。直接运行某个包内文件时，经常会失败。

例如：

```bash
python app/services/user_service.py
```

如果文件内部有：

```python
from .user_repository import UserRepository
```

可能报错：

```text
ImportError: attempted relative import with no known parent package
```

更稳的运行方式是从项目根目录以模块方式运行：

```bash
python -m app.services.user_service
```

`-m` 会让 Python 按模块路径运行，包上下文更完整。

## 十一、Python 去哪里找模块

Python 导入模块时会沿着搜索路径查找。

可以查看：

```python
import sys

for path in sys.path:
    print(path)
```

常见来源：

- 当前脚本所在目录。
- 环境变量 `PYTHONPATH`。
- 虚拟环境的 site-packages。
- 标准库路径。
- 已安装包路径。

如果出现：

```text
ModuleNotFoundError: No module named 'app'
```

常见原因：

- 当前工作目录不对。
- 项目没有作为包安装。
- 没有激活虚拟环境。
- 包名写错。
- 同名文件遮蔽了真实包。

不要第一反应就往 `sys.path` 里硬塞路径。能通过正确运行方式、虚拟环境和包安装解决的问题，就不要用临时补丁把项目结构弄得更暧昧。

## 十二、局部导入

`import` 可以写在函数内部。

```python
def load_json(text: str):
    import json

    return json.loads(text)
```

这叫局部导入。它是合法的。

局部导入常见用途：

- 延迟导入重依赖，减少启动成本。
- 避免可选依赖在不使用时强制安装。
- 暂时缓解循环导入。
- 只在某个平台或某个分支中需要模块。

例如：

```python
def read_excel(path):
    import pandas as pd

    return pd.read_excel(path)
```

如果项目大多数功能不需要 pandas，就可以把导入放到真正使用时。

但不要滥用局部导入。过多局部导入会让文件依赖关系不直观，也会让错误更晚暴露。

一般建议：

- 标准库和核心依赖放在文件顶部导入。
- 重依赖、可选依赖、特定分支依赖可以局部导入。
- 如果只是为了逃避循环导入，最好最终还是重构依赖关系。

## 十三、try import

导入可以放进 `try`。

常见用途是处理可选依赖：

```python
try:
    import orjson as json_impl
except ImportError:
    import json as json_impl
```

如果安装了 `orjson`，就使用更快的实现；否则退回标准库 `json`。

也可以给出更明确错误：

```python
try:
    import pandas as pd
except ImportError as exc:
    raise RuntimeError(
        "read_excel() requires pandas. Install it with: pip install pandas"
    ) from exc
```

这种写法适合可选功能：

```python
def read_excel(path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Excel support requires pandas. Install it with: pip install pandas"
        ) from exc

    return pd.read_excel(path)
```

注意，不要用宽泛的 `except Exception` 包住导入。

不推荐：

```python
try:
    import my_plugin
except Exception:
    my_plugin = None
```

如果 `my_plugin` 自己内部有 bug，也会被吞掉。结果你以为是“没安装”，实际是“安装了但执行崩了”。这种误导很讨厌，当然，错误本来也没义务照顾人的心情。

更推荐只捕获：

```python
except ImportError:
```

或在复杂场景里检查异常的模块名。

例如：

```python
try:
    import optional_plugin
except ModuleNotFoundError as exc:
    if exc.name != "optional_plugin":
        raise

    optional_plugin = None
```

这段代码只把 `optional_plugin` 本身不存在当作“可选依赖未安装”。如果 `optional_plugin` 内部又导入别的包失败，就继续抛出异常。这样更容易暴露真实问题。

## 十四、导入模块和导入名字的区别

看两种写法：

```python
import config
```

使用：

```python
print(config.DEBUG)
```

另一种：

```python
from config import DEBUG
```

使用：

```python
print(DEBUG)
```

如果 `config.DEBUG` 之后被修改，两者表现可能不同。

```python
# config.py
DEBUG = False
```

```python
# main.py
from config import DEBUG
import config

config.DEBUG = True

print(config.DEBUG) # True
print(DEBUG) # False
```

`from config import DEBUG` 把当时的对象绑定到了当前模块的 `DEBUG` 名字。后面 `config.DEBUG` 被重新赋值，不会自动改当前模块里的 `DEBUG` 绑定。

所以可变配置更适合通过模块对象访问：

```python
import config

if config.DEBUG:
    ...
```

## 十五、导入副作用

导入模块会执行模块顶层代码，因此导入可能有副作用。

```python
# tasks.py
print("register task")
register_task("send_email")
```

只要执行：

```python
import tasks
```

就会注册任务。

有些框架会利用这种机制，例如插件注册、路由注册、模型发现。但业务代码里要谨慎，因为副作用导入会让依赖关系变隐蔽。

如果只是为了副作用导入，最好写得明确：

```python
import app.tasks  # register scheduled tasks
```

不要让读者猜为什么导入一个看似没用的模块。

## 十六、if __name__ == "__main__"

模块可以被导入，也可以被直接运行。

```python
print(__name__)
```

直接运行：

```bash
python script.py
```

`__name__` 是：

```text
__main__
```

被导入时：

```python
import script
```

`__name__` 是：

```text
script
```

所以常见写法：

```python
def main():
    print("run script")


if __name__ == "__main__":
    main()
```

这样模块被导入时不会自动执行 `main()`，只有直接运行时才执行。

这是避免导入副作用的基本习惯。

## 十七、循环导入

循环导入是两个模块互相导入。

```text
user_service.py -> user_repository.py
user_repository.py -> user_service.py
```

示例：

```python
# a.py
from b import b_func

def a_func():
    return "a"
```

```python
# b.py
from a import a_func

def b_func():
    return "b"
```

循环导入可能导致：

```text
ImportError: cannot import name ...
```

原因是模块导入过程中会先创建模块对象，再执行模块代码。如果 A 导入 B，B 又导入尚未执行完的 A，就可能拿到一个“半初始化”的模块。

解决方向：

- 抽出共同依赖到第三个模块。
- 让底层模块不要导入上层业务模块。
- 把导入移动到函数内部作为临时缓解。
- 使用依赖注入，把对象从外部传进去。
- 拆分类型定义和运行时逻辑。

局部导入可以缓解：

```python
def create_user(data):
    from app.repositories.user_repository import UserRepository

    repo = UserRepository()
    return repo.create(data)
```

但这只是移动导入时机。真正的问题通常是模块边界不清楚。循环依赖不是命运，是结构在提醒你它不太舒服。

## 十八、类型检查中的导入

类型注解有时会引入循环导入。

```python
from app.models.user import User

def send_email(user: User) -> None:
    ...
```

如果只是给类型检查器使用，可以用 `TYPE_CHECKING`：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


def send_email(user: "User") -> None:
    ...
```

`TYPE_CHECKING` 在类型检查时被视为 `True`，运行时是 `False`。这样类型工具能看到导入，运行时不会真的导入。

在现代 Python 中，也可以使用延迟注解：

```python
from __future__ import annotations
```

这样很多注解不会立刻求值，能减少运行时导入问题。

## 十九、动态导入 importlib

如果模块名运行时才确定，可以用 `importlib`。

```python
import importlib

module_name = "json"
json_module = importlib.import_module(module_name)

print(json_module.dumps({"ok": True}))
```

常见场景：

- 插件系统。
- 按配置加载处理器。
- 命令行工具按名称加载命令。
- 框架自动发现模块。

示例：

```python
def load_handler(name: str):
    module = importlib.import_module(f"app.handlers.{name}")
    return module.Handler()
```

动态导入要控制输入来源。不要把用户输入直接拼进模块路径后导入，否则可能加载到不该加载的模块。

## 二十、重新加载模块

可以使用：

```python
import importlib
import config

importlib.reload(config)
```

这会重新执行模块代码。

它常见于交互式调试、Notebook、开发工具。普通业务代码中很少需要手动 reload。

原因：

- 已经从模块导入的名字不会自动全部更新。
- 模块内部状态可能被重置。
- 其他模块持有的旧对象引用仍然存在。
- 行为容易变复杂。

如果你发现业务代码需要频繁 reload 模块，通常说明配置加载或对象生命周期设计需要重新考虑。

## 二十一、导入顺序

常见导入顺序：

```python
import os
import sys
from pathlib import Path

import requests

from app.services.user_service import get_user
```

分组：

```text
标准库
第三方库
本项目模块
```

组之间空一行。

这不是形式主义。导入顺序清楚后，依赖来源更容易判断，合并冲突也更少。

可以使用工具自动整理：

- `ruff`
- `isort`

## 二十二、常见错误

### 1. 文件名遮蔽标准库

如果你创建了：

```text
json.py
```

然后写：

```python
import json
```

可能导入的是你自己的 `json.py`，不是标准库 `json`。

避免用标准库或第三方库同名文件：

```text
random.py
typing.py
requests.py
asyncio.py
```

这些名字都不适合作为普通业务文件名。

### 2. 直接运行包内文件导致相对导入失败

错误方式：

```bash
python app/services/user_service.py
```

更稳：

```bash
python -m app.services.user_service
```

或提供项目入口脚本。

### 3. 在模块顶层做重初始化

```python
db = connect_database()
```

如果导入模块就连接数据库，测试、脚本、命令行工具都可能受到影响。

更稳：

```python
def get_db():
    return connect_database()
```

或者由应用启动入口统一初始化。

### 4. 用 try import 吞掉真实错误

不推荐：

```python
try:
    import plugin
except Exception:
    plugin = None
```

推荐：

```python
try:
    import plugin
except ImportError:
    plugin = None
```

如果插件内部执行时报错，应该暴露出来，而不是伪装成“没安装”。

### 5. 过度局部导入

```python
def f1():
    import os
    ...

def f2():
    import os
    ...
```

标准库和普通依赖放文件顶部更清楚。局部导入应该有理由。

## 二十三、推荐实践

- 普通依赖放在文件顶部导入。
- 标准库、第三方库、本项目模块分组。
- 业务项目优先使用清楚的绝对导入。
- 包内少量近邻模块可以使用相对导入。
- 不滥用 `import *`。
- 模块顶层少放副作用逻辑。
- 可选依赖用 `try import`，并给出明确错误。
- 重依赖或少用功能可以局部导入。
- 循环导入优先通过重构依赖方向解决。
- 直接运行包内模块时优先使用 `python -m package.module`。

## 二十四、总结

Python 导入系统可以这样理解：

```text
模块是 .py 文件
包是组织模块的目录
import 会查找、执行并缓存模块
sys.modules 保存已加载模块
sys.path 决定搜索路径
局部导入可以延迟依赖
try import 可以处理可选依赖
相对导入依赖包上下文
循环导入通常说明模块边界需要调整
```

如果只记一句话：

> `import` 不是简单复制代码，而是加载模块对象、执行顶层代码、缓存结果，并在当前作用域绑定名字。

理解这一点后，局部导入、`try import`、`__init__.py`、循环导入和 `python -m` 就不再是零散技巧，而是一套可以推理的规则。
