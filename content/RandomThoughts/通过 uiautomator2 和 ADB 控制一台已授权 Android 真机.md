+++
date = '2026-08-26T21:20:00+08:00'
draft = false
title = '通过 uiautomator2 和 ADB 控制一台已授权 Android 真机'
+++

如果一台 Android 真机已经由设备所有者明确授权，并开启了 USB 调试，那么可以通过 ADB 建立电脑与手机之间的调试通道，再用 `uiautomator2` 以 Python 控制界面。这很适合做回归测试、重复性验收、企业自有设备巡检，或复现某个稳定的操作流程。

先说清楚边界：下文只讨论**自己拥有或已获明确授权的设备、应用和测试数据**。不要把 USB 调试授权、调试接口或自动化脚本用于绕过锁屏、窃取数据、操控他人设备或规避应用限制。能做某件事与有权做某件事是两回事；脚本不会替人承担后果，这一点倒是相当诚实。

## 一、ADB 与 uiautomator2 各自做什么

**ADB（Android Debug Bridge）** 是 Android SDK Platform-Tools 中的调试工具。它在电脑上的客户端通过 USB 或已配对的网络调试通道，与设备上的 `adbd` 通信；常用于查看设备、执行 shell 命令、安装测试包、读取日志和转发端口。

**uiautomator2** 是面向 Python 的 Android UI 自动化库。它会在设备端运行基于 Android UiAutomator 的 HTTP 服务，Python 客户端通过该服务查找控件、点击、输入、滑动、截图和读取界面层级。初始化与连接设备时，它通常借助 ADB 完成设备端组件的部署和通信建立。

可以把职责理解为：

```text
Python 测试脚本
 -> uiautomator2 Python 客户端
   -> ADB：识别设备、部署组件、执行调试命令
     -> 手机上的 UiAutomator 服务
       -> Android 界面与目标应用
```

二者不是互相替代的关系：ADB 更接近设备调试与系统命令通道，`uiautomator2` 更适合按控件语义操作用户界面。一个可维护的自动化项目通常会同时使用它们。

## 二、开始前：授权、环境与最小原则

开始前应满足以下条件：

- 手机已由所有者允许用于调试，且已经开启“开发者选项”和“USB 调试”。
- 手机通过可信 USB 数据线连接电脑，并在手机弹出的 RSA 调试授权提示中确认这台电脑。
- 电脑已安装 Android SDK Platform-Tools，终端可以执行 `adb`。
- 已安装 Python 3.8 或更高版本，以及 `uiautomator2`。
- 自动化目标、测试账号和测试数据属于你的授权范围。

安装 Python 库：

```bash
python -m pip install --upgrade uiautomator2
python -m uiautomator2 version
```

如果 `adb` 提示找不到命令，可以直接使用 Platform-Tools 目录中的可执行文件，或把该目录加入系统的 `PATH`。不要从来历不明的网站下载一个叫 `adb.exe` 的文件就直接运行；调试工具拥有相当高的设备权限，谨慎一点并不多余。

### 1. 用 ADB 确认设备状态

连接手机后，先执行：

```bash
adb devices -l
```

正常情况下会看到类似结果：

```text
List of devices attached
R58N12345AB            device product:example model:Example_Phone device:example
```

第二列的状态尤其重要：

| 状态 | 含义 | 应对方式 |
| ---- | ---- | -------- |
| `device` | 已连接且已授权 | 可以继续操作 |
| `unauthorized` | 手机尚未授权当前电脑 | 解锁手机，确认 RSA 调试授权提示 |
| `offline` | 设备存在但调试连接不可用 | 重新插拔、重启 ADB 服务或检查线缆 |
| 无设备 | 电脑没有发现可用设备 | 检查 USB 调试、线缆、驱动和连接模式 |

只看到序列号并不等于已经可控；必须看到 `device`。如果有多台设备，后续每条 ADB 命令都应指定序列号，避免把测试动作发给错误的手机：

```bash
adb -s R58N12345AB shell getprop ro.product.model
adb -s R58N12345AB shell wm size
```

在 Windows 上，可以使用 `where adb` 确认实际执行的是哪个 `adb.exe`。多套 Android SDK 同时存在时，版本不一致导致的“看起来连上了，实际很奇怪”并不罕见。

### 2. 只在必要时重启 ADB 服务

遇到设备卡在 `offline` 时，可以尝试：

```bash
adb kill-server
adb start-server
adb devices -l
```

这会影响当前电脑上所有 ADB 连接，所以在共享测试机或多人使用的环境里应先确认影响范围。排障不等于向周围的一切发送重启请求；这两个概念的差别，通常在别人正在跑测试时才变得格外明显。

## 三、先用 ADB 做低层验证

在写 Python 自动化之前，先确认调试链路和设备基本信息。以下命令都是只读或低影响的检查：

```bash
adb -s R58N12345AB get-state
adb -s R58N12345AB shell getprop ro.build.version.release
adb -s R58N12345AB shell dumpsys window | findstr mCurrentFocus
```

最后一条能帮助观察当前前台窗口。在 macOS/Linux 中，过滤命令通常是 `grep`，而 Windows PowerShell 可使用：

```powershell
adb -s R58N12345AB shell dumpsys window | Select-String 'mCurrentFocus'
```

ADB 也能直接模拟一些基础输入，例如按返回键：

```bash
adb -s R58N12345AB shell input keyevent KEYCODE_BACK
```

它适合用在自动化恢复初始状态、唤起系统功能或辅助诊断中。不过，业务页面的点击和输入优先交给 `uiautomator2`，因为控件定位比绝对坐标可靠得多。

## 四、连接 `uiautomator2` 真机

建立最小项目：

```text
android-ui-test/
├── requirements.txt
└── smoke_test.py
```

`requirements.txt` 可以先只有一行：

```text
uiautomator2
```

创建 `smoke_test.py`：

```python
import uiautomator2 as u2

SERIAL = "R58N12345AB"  # 替换为 adb devices -l 中的真实序列号

d = u2.connect(SERIAL)

print("设备信息：", d.device_info)
print("当前前台应用：", d.app_current())
d.screenshot("artifacts/connected.png")
```

首次连接时，`uiautomator2` 可能通过 ADB 向设备安装或启动所需组件，耗时会比后续连接更长。运行前创建 `artifacts` 目录，并执行：

```bash
python smoke_test.py
```

如果机器只连接了一台已授权设备，也可以使用：

```python
d = u2.connect()
```

但在 CI、设备柜或有模拟器的开发机上，显式传入 `SERIAL` 更可靠。自动化最不应该依赖的东西之一，就是“它大概会选对”。

若连接或初始化异常，可先检查：

```bash
python -m uiautomator2 doctor
adb devices -l
```

检查时应记录设备序列号、Android 版本、`uiautomator2` 版本和完整错误信息；只记录“连不上”对于后来排查几乎没有帮助。

## 五、控件定位：优先语义，坐标只是最后手段

UI 自动化最常见的失败原因并非点击 API 不会用，而是定位方式太脆弱。屏幕分辨率、字体缩放、语言、刘海和页面布局变化都可能让坐标失效。

优先级通常如下：

1. 稳定的 `resourceId`。
2. `content-desc`，在 `uiautomator2` 中通常用 `description` 定位。
3. 明确且稳定的可见文本。
4. 类名与层级等组合条件。
5. 坐标点击，仅用于没有可定位语义的特殊区域。

假设自有测试应用中存在用户名输入框、密码输入框和登录按钮，可以这样写：

```python
PACKAGE = "com.example.demo"

d.app_start(PACKAGE)

username = d(resourceId=f"{PACKAGE}:id/username")
password = d(resourceId=f"{PACKAGE}:id/password")
login_button = d(resourceId=f"{PACKAGE}:id/login")

if not username.exists(timeout=10):
    raise RuntimeError("用户名输入框未出现，页面可能没有成功打开")

username.set_text("test_user")
password.set_text("only-for-test")
login_button.click()
```

如果应用能为自动化控件提供稳定的 `resource-id` 和无障碍描述，测试会省去大量不必要的猜测。应用开发者若只给视觉稿，不给可访问性语义，最终通常会由测试脚本用等待、坐标和运气来偿还这笔债。

### 1. 文本、描述与组合定位

常用选择器示例：

```python
# 文本完全匹配
d(text="设置").click()

# 无障碍描述（content-desc）
d(description="搜索").click()

# 文本包含某个片段
d(textContains="保存").click()

# 多个条件组合
d(className="android.widget.TextView", text="确定").click()
```

文本定位对系统设置页或临时验证很方便，但会受到多语言和文案改动影响。业务自动化中，稳定的 `resourceId` 通常优于文本。

### 2. 等待条件，不要用无意义的固定睡眠

网络、动画、设备性能和首屏加载时间都不稳定。与其在每一步后写很长的 `sleep`，不如等待真正关心的界面状态：

```python
success = d(resourceId=f"{PACKAGE}:id/welcome_title")

if not success.exists(timeout=15):
    d.screenshot("artifacts/login-failed.png")
    raise AssertionError("登录后未进入预期页面")
```

短暂等待动画结束有时仍然合理，但它应是补充，不是同步策略。固定等待会让成功的测试变慢，让失败的测试也慢；它在公平地浪费每个人的时间。

### 3. 输入、滑动、按键和截图

```python
# 清空再输入。必要时使用 send_keys 处理更复杂的输入场景。
d(resourceId=f"{PACKAGE}:id/search").set_text("SQLite")

# 按返回键
d.press("back")

# 向上滑动，比例坐标比绝对像素稍耐分辨率变化
d.swipe(0.5, 0.8, 0.5, 0.2, duration=0.3)

# 根据可滚动容器滚动到目标文本
d(scrollable=True).scroll.to(text="关于我们")

# 保存当前屏幕，便于失败诊断
d.screenshot("artifacts/current-screen.png")
```

`set_text` 对一般输入框足够方便；如果遇到中文、特殊字符或输入法焦点问题，应先在目标设备上验证，再根据 `uiautomator2` 的输入法支持调整方案。不要因为一次输入失败就退回到模拟键盘逐字符敲击，那通常只会把偶发问题改造成稳定的慢问题。

## 六、读取 UI 层级，找到真正的定位信息

当元素“明明在屏幕上，却找不到”时，截图只能告诉你看到了什么；UI 层级才能告诉你自动化框架实际看到了什么。

```python
xml = d.dump_hierarchy()
with open("artifacts/window.xml", "w", encoding="utf-8") as file:
    file.write(xml)
```

在 XML 中重点寻找：

- `resource-id`
- `text`
- `content-desc`
- `class`
- `clickable`、`enabled`、`scrollable`
- 元素边界 `bounds`

也可以安装元素查看工具辅助检查：

```bash
python -m pip install uiautodev
uiautodev
```

如果层级里根本没有目标控件，常见原因包括：目标其实是 WebView、内容属于自绘 Canvas、页面还未加载完成，或应用刻意限制了无障碍层级暴露。此时应先判断测试对象的技术形态，再选择 WebView 调试、应用测试桩或与研发协作增加可测性；不要急着把所有问题都归结为“选择器写错”。

## 七、把一次操作写成可重复的冒烟测试

下面是一个自有应用登录冒烟测试的结构示例。它没有尝试替你处理验证码、风控或生产账号登录；这类流程应由系统提供测试环境、测试账号或明确的测试开关，而不是让自动化去对抗安全机制。

```python
from pathlib import Path
import time

import uiautomator2 as u2

SERIAL = "R58N12345AB"
PACKAGE = "com.example.demo"
ARTIFACTS = Path("artifacts")


def save_failure_artifacts(device: u2.Device, name: str) -> None:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    ARTIFACTS.mkdir(exist_ok=True)
    device.screenshot(str(ARTIFACTS / f"{name}-{timestamp}.png"))
    (ARTIFACTS / f"{name}-{timestamp}.xml").write_text(
        device.dump_hierarchy(),
        encoding="utf-8",
    )


def test_login_smoke() -> None:
    d = u2.connect(SERIAL)
    d.implicitly_wait(10)
    d.app_stop(PACKAGE)
    d.app_start(PACKAGE)

    try:
        d(resourceId=f"{PACKAGE}:id/username").set_text("test_user")
        d(resourceId=f"{PACKAGE}:id/password").set_text("only-for-test")
        d(resourceId=f"{PACKAGE}:id/login").click()

        welcome = d(resourceId=f"{PACKAGE}:id/welcome_title")
        if not welcome.exists(timeout=15):
            raise AssertionError("登录后未看到欢迎标题")
    except Exception:
        save_failure_artifacts(d, "login-failure")
        raise


if __name__ == "__main__":
    test_login_smoke()
```

这个示例刻意包含几个工程习惯：

- 显式指定设备序列号，避免误操作其他设备。
- 每次启动前停止目标应用，使初始状态尽量一致。
- 使用控件标识而非点击固定像素。
- 在失败时保存截图和页面层级，留下可诊断证据。
- 使用专门的测试账号，绝不在代码中写入真实用户凭据。

对于会产生业务副作用的动作，如提交订单、发送消息、删除记录，应在测试环境执行，并增加明确的环境检查、测试数据前缀和人工确认点。自动化不是让危险操作变得无声无息，而是让可预期的操作变得可重复、可追踪。

## 八、常见问题与排查顺序

### 1. `adb devices` 显示 `unauthorized`

解锁手机，查看是否有 RSA 指纹授权弹窗。确认连接的是自己的可信电脑；若设备曾错误记住授权，可在手机开发者选项中撤销 USB 调试授权后重新连接。不要试图绕过授权弹窗——它存在的理由正是阻止未获许可的控制。

### 2. ADB 找不到设备

按下面顺序排查：

1. 确认线缆支持数据传输，而不仅仅是充电。
2. 确认手机已开启 USB 调试，并已解锁。
3. 更换 USB 端口或线缆。
4. 在 Windows 上检查对应厂商 USB 驱动。
5. 执行 `adb kill-server`、`adb start-server` 后再次查看设备。

### 3. `uiautomator2` 无法连接或初始化

先确认 `adb -s <serial> get-state` 返回 `device`，再运行：

```bash
python -m uiautomator2 doctor
```

随后检查 Python 环境是否就是安装库的环境，并保留命令输出。若公司设备管理策略禁止安装辅助组件，应与设备管理员或测试环境负责人确认，不应绕过管理策略。

### 4. 元素找不到或点击无效

依次检查：

1. 当前前台应用和页面是否正确，可用 `d.app_current()` 确认。
2. 目标元素是否已经出现，而不是仍在加载或被弹窗覆盖。
3. `dump_hierarchy()` 中是否存在目标的 `resource-id`、文本或描述。
4. 是否因为语言、深色模式、字体缩放或版本升级导致文本/布局变化。
5. 是否属于 WebView、自绘控件或系统受限界面。

不要把“增加三秒 `sleep`”作为第一反应。它偶尔能掩盖时序问题，却很少解决定位问题。

### 5. 出现 `device offline`、端口占用或偶发连接中断

优先收集 `adb devices -l`、脚本日志、设备日志和失败截图。重连前确认没有另一套脚本在占用同一台设备；设备控制应有排他调度，尤其在共享真机池中。同一台手机被两个测试同时操作时，得到的往往不是并发，而是一场很难复盘的互相干扰。

## 九、安全与稳定性清单

将下面几条作为每个真机自动化项目的基础约束：

- 只登记并连接有明确授权的设备序列号。
- 不在仓库、日志或截图中保存真实密码、令牌、手机号及其他敏感信息。
- 使用独立测试账号与可清理的测试数据。
- 对清除应用数据、卸载应用、删除内容、发消息和付款等动作加环境保护与显式确认。
- 每次失败保存截图、UI XML、设备序列号、应用版本和错误堆栈。
- 为每台共享设备设置占用锁或调度队列，禁止并发脚本互相操作。
- 在完成测试后关闭 USB 调试，或至少撤销不再信任电脑的调试授权。

## 十、总结

通过 ADB 确认连接与授权，通过 `uiautomator2` 按界面语义执行操作，是控制已授权 Android 真机的一条清晰路径。真正决定脚本质量的，不是能否点到一个按钮，而是能否做到：设备选对、状态可控、元素定位稳定、失败留有证据、业务副作用被限制在授权的测试范围内。

从一个“连接成功并截一张图”的脚本开始，再逐步加入页面对象、测试数据管理、失败归档和设备调度，会比一开始堆砌几百行坐标点击可靠得多。界面会变化，等待会波动，设备也会偶尔闹脾气；只有让脚本依赖语义和证据，自动化才不至于像一次侥幸成功的魔术。

## 参考资料

- [Android Debug Bridge（ADB）官方文档](https://developer.android.com/tools/adb)
- [uiautomator2 官方项目与使用说明](https://github.com/openatx/uiautomator2)
