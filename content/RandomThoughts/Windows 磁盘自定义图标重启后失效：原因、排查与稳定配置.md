+++
date = '2026-09-21T20:15:00+08:00'
draft = false
title = 'Windows 磁盘自定义图标重启后失效：原因、排查与稳定配置'
+++

给 C、D、E 盘换上图标后，资源管理器左侧导航栏似乎一切正常；但重启电脑再打开“此电脑”，主区域里的驱动器却变成了白色通用图标。这不是磁盘出故障，也不意味着图标一定被删除了。更准确地说，是资源管理器没有在需要的时机、从需要的位置，成功解析到驱动器图标，于是回退到了默认图标。

本文说明这一现象为什么会发生，并给出一种在 Windows 10、Windows 11 上更稳定的配置方法。核心结论先写在前面：**驱动器图标应使用 `DriveIcons` 注册表项配置为绝对路径；图标文件应当是可在启动后立即访问的具体 `.ico` 文件，而不是一个装图标的目录。** 完成配置后再重启资源管理器或刷新图标缓存，才能让当前窗口立即显示新结果。

## 一、先理解：资源管理器并不只在一个地方显示磁盘

同一个 C 盘，至少会在下面两个界面出现：

- 左侧导航窗格，例如“此电脑”展开后的 `OS (C:)`；
- “此电脑”主区域的设备和驱动器卡片。

它们最终都会由 Windows Shell 绘制，但读取图标的时间、缓存和上下文并不完全相同。因此，左侧仍显示自定义小图标，并不能证明主区域使用的驱动器图标配置仍然有效。

可以把过程简化为下面这样：

```text
资源管理器需要显示 C: / D: / E:
        -> 查询驱动器图标的注册表配置
        -> 解析“图标文件完整路径,图标索引”
        -> 从 .ico / .exe / .dll 中提取图标
        -> 命中图标缓存，或生成新的缓存
        -> 显示自定义图标；失败时显示通用白色图标
```

其中任一环节失败，都可能出现“名称和容量条正常，但图标是白纸”的结果。图标只是外观资源，Windows 不会因为它解析失败就阻止磁盘被使用；这也是为什么问题看起来很别扭，却不影响文件读写。

## 二、正确的驱动器图标配置位置

Windows 为驱动器图标提供了专门的注册表位置：

```text
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons
```

每个盘符各有一个子项。例如 D 盘的配置结构是：

```text
DriveIcons
└── D
    └── DefaultIcon
        └── (默认) = C:\ProgramData\DriveIcons\D.ico,0
```

这里有两个经常被忽略的细节：

1. 子项名只写盘符，例如 `D`，**不要写成 `D:`**。
2. `DefaultIcon` 的默认值不是目录，而是 `完整文件路径,图标索引`。对于普通 `.ico` 文件，索引通常是 `0`。

微软的 Shell 文档将该位置列为 Windows 2000 之后版本设置自定义驱动器图标的方式，并要求值包含图标文件的完整路径及索引。[如何为驱动器盘符设置自定义图标和标签](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-assign-a-custom-icon-and-label-to-a-drive-letter)

## 三、为什么 `ico` 目录会成为问题

很多人会在每个盘符根目录创建一个 `ico` 文件夹，例如：

```text
C:\ico\
D:\ico\
E:\ico\
```

这个组织方式本身没有问题；问题在于 **`C:\ico` 是目录，不是图标文件**。下列写法无效：

```text
DefaultIcon = C:\ico,0
```

资源管理器不能从目录本身提取图标。它必须指向一个文件，例如：

```text
DefaultIcon = C:\ico\system-drive.ico,0
```

或：

```text
DefaultIcon = D:\ico\data-drive.ico,0
```

### 图标的“多尺寸”到底应该在哪里

Windows 会在侧栏、小图标、列表、磁盘卡片等不同场景请求不同尺寸的图标。理想情况是**一份 `.ico` 文件内部包含多种尺寸**，常见的是 `16×16`、`24×24`、`32×32`、`48×48`、`64×64` 和 `256×256`。

如果 `ico` 目录里放的是多份彼此独立的文件，例如 `16.ico`、`32.ico`、`48.ico`，注册表仍然只能指定其中的某一个文件；它不会根据窗口大小自动在一个目录中挑选另一个文件。此时应优先使用一份内含多种尺寸的 ICO，或明确选择希望使用的那一份。

还要特别避免把 PNG、JPG 直接改名为 `.ico`。扩展名改变不会把图像编码变成 ICO 格式。这样的文件可能在某些软件中看似可预览，但 Shell 提取图标时失败，最终只会得到通用图标。

## 四、重启后为什么才失效

“刚设置时可见，重启后无效”并不神秘，通常来自以下几种情况。

### 1. 图标文件路径在启动时不可用

如果 D 盘的图标放在 D 盘自身、网络位置、同步盘或临时目录，资源管理器启动时可能比目标位置更早尝试读取它。图标解析失败后，当前会话就可能缓存通用图标。

将所有驱动器图标统一放在系统盘的固定目录，例如 `C:\ProgramData\DriveIcons\`，最容易避免这个时序问题。该目录不依赖 D、E 盘是否已完成挂载，也不适合被随手清理或同步客户端改成“仅云端”。

若确实希望各个盘符保留自己的 `ico` 目录，配置也能工作；前提是其中的图标文件在登录时可访问，并且注册表指向的是明确的文件路径。

### 2. 只设置了 `desktop.ini`

`desktop.ini` 是 Windows 用来定制**文件夹**外观和行为的机制。它适合给普通文件夹设置图标；要让设置生效，文件夹还需要具备相应的系统文件夹属性。微软在 [使用 desktop.ini 自定义文件夹](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-customize-folders-with-desktop-ini) 的文档中也将它定义为文件夹自定义机制。

驱动器不是普通文件夹。虽然在部分显示场景下，根目录的 `desktop.ini` 可能看起来有效，但对于“此电脑”里的驱动器图标，应该优先使用 `DriveIcons`。两种机制混用时，左侧导航栏和主区域也可能分别命中不同的缓存或来源，于是出现一边正常、一边白色的现象。

### 3. 图标缓存保留了旧结果

为了避免每次打开窗口都从磁盘逐个解析图标，资源管理器维护了图标缓存。改完注册表或替换同名 ICO 后，缓存不一定立刻失效。

这解释了两类看似矛盾的现象：

- 文件和注册表已经正确，但当前窗口仍显示旧图标；
- 某个位置显示新图标，另一个位置还显示旧图标或通用图标。

缓存需要在**配置正确之后**刷新。反复清理缓存却不修正路径，只是在反复让 Windows 重新读取同一个错误配置，结果自然不会因为次数足够多而突然变得正确。

### 4. ICO 文件只含小尺寸或内容损坏

侧栏需要的图标尺寸较小，主区域需要的尺寸较大。若 ICO 缺少合适的图层、格式不规范或文件受损，可能会在小尺寸场景中勉强显示，在“此电脑”卡片中回退为空白。

最直接的检查方法是：在任意普通文件夹中打开“属性 → 自定义 → 更改图标”，选择该 ICO。若预览框也为空白或报错，应更换为真正的多尺寸 ICO 文件，而不是继续修改注册表。

## 五、用 PowerShell 建立稳定配置

在本文对应的电脑上，实际检查结果如下：

- C、D、E 根目录分别有 `C:\p.ico`、`D:\p.ico`、`E:\p.ico`；
- 三份文件都是有效 ICO，均内含 `16×16` 至 `256×256` 的八个尺寸图层；
- 三个根目录都有隐藏的 `autorun.inf`，内容是 `[autorun]` 和 `ICON=p.ico`；
- `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons` 下不存在 C、D、E 的 `DefaultIcon`。

因此，图标文件本身无需移动或重做。`autorun.inf` 的 `icon` 条目确实能够为 Windows UI 中的驱动器指定图标，但它属于 AutoRun 机制；而针对固定盘符配置图标，`DriveIcons` 是更直接、稳定的 Shell 配置位置。[Microsoft Learn：Autorun.inf 的 icon 条目](https://learn.microsoft.com/zh-cn/windows/win32/shell/autorun-cmds)

下面脚本会直接使用这三份已经验证过的图标文件，为 C、D、E 写入 `DriveIcons`。它不会删除 `autorun.inf`，也不会重启资源管理器或清除图标缓存；它只完成刷新前必要的配置和验证。

请在 **以管理员身份运行的 PowerShell** 中执行：

```powershell
#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$registryRoot = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons'
$icons = [ordered]@{
    C = 'C:\p.ico'
    D = 'D:\p.ico'
    E = 'E:\p.ico'
}

foreach ($driveLetter in $icons.Keys) {
    $iconPath = $icons[$driveLetter]

    if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
        throw "找不到 $driveLetter 盘的图标文件：$iconPath"
    }

    $iconValue = "$iconPath,0"
    $driveRegistryKey = "$registryRoot\$driveLetter"
    $registryKey = "$driveRegistryKey\DefaultIcon"

    New-Item -Path $registryRoot -Force | Out-Null
    New-Item -Path $driveRegistryKey -Force | Out-Null
    New-Item -Path $registryKey -Force | Out-Null
    Set-Item -LiteralPath $registryKey -Value $iconValue

    $actualValue = (Get-Item -LiteralPath $registryKey).GetValue('')
    Write-Host "已设置 $driveLetter 盘：$actualValue" -ForegroundColor Green
}

Write-Host "`n配置已完成。现在可在任务管理器中重新启动“Windows 资源管理器”。" -ForegroundColor Yellow
```

### 脚本做了什么

| 步骤 | 作用 |
| --- | --- |
| 验证 `C:\p.ico`、`D:\p.ico`、`E:\p.ico` | 防止把不存在的路径写入注册表 |
| 为每个盘符写入 `DefaultIcon` | 让“此电脑”按官方驱动器图标机制读取资源 |
| 回读注册表默认值 | 确认写入的实际路径与预期一致 |
| 暂不刷新资源管理器 | 让配置和显示刷新成为两个可验证的步骤 |

脚本写入的值形如：

```text
C:\p.ico,0
```

末尾的 `,0` 是图标索引。ICO 文件常见情况下只需选择第 `0` 个图标；若图标资源来自 EXE 或 DLL，才可能需要不同索引。`DefaultIcon` 的值采用“完整路径,资源索引”的形式。[Microsoft Learn：DefaultIcon](https://learn.microsoft.com/en-us/windows/win32/com/defaulticon)

## 六、配置完成后如何刷新显示

脚本结束后，先用最温和的方式刷新：

1. 按 `Ctrl + Shift + Esc` 打开任务管理器。
2. 找到“Windows 资源管理器”。
3. 右键选择“重新启动”。
4. 再打开“此电脑”，检查 C、D、E 的主区域图标。

如果仍显示旧图标，可在管理员 PowerShell 中执行：

```powershell
ie4uinit.exe -show
```

然后再次重启“Windows 资源管理器”。

仍未变化时，才考虑重建图标缓存。以下命令会关闭并重新启动资源管理器，删除的只是当前用户的图标缓存文件，不会删除个人数据：

```powershell
Stop-Process -Name explorer -Force
Remove-Item -LiteralPath "$env:LOCALAPPDATA\IconCache.db" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache*" -Force -ErrorAction SilentlyContinue
Start-Process explorer.exe
```

执行期间桌面和任务栏会短暂消失。这是因为它们都由 `explorer.exe` 承载；最后一行会重新启动它，并不是系统突然决定把桌面收走。

## 七、需要把图标放在哪里

将图标存放在每个磁盘自身的 `ico` 目录中，便于整理，也可正常工作。不过从启动可靠性来看，所有图标统一放到系统盘固定目录更稳妥：

```text
C:\ProgramData\DriveIcons\C.ico
C:\ProgramData\DriveIcons\D.ico
C:\ProgramData\DriveIcons\E.ico
```

这是因为系统盘通常最早可用，而 `ProgramData` 不属于个人桌面、下载目录或云同步目录。尤其不要让 D 盘图标指向会延迟挂载的网络路径，也不要把 D 盘的唯一图标放进一个可能被 BitLocker 锁定的盘符中。

无论选择哪一种目录结构，都应满足下面的条件：

- 注册表中记录的是**绝对路径**；
- 目标是**具体文件**，不是文件夹；
- 文件扩展名与实际格式一致，确实是 ICO；
- 文件不会被移动、重命名、清理或设为仅云端；
- 文件最好包含从小到大的多种尺寸。

## 八、如何撤销或恢复默认图标

如果不再需要自定义图标，打开管理员 PowerShell，执行：

```powershell
$root = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons'
'C', 'D', 'E' | ForEach-Object {
    Remove-Item -LiteralPath "$root\$_\DefaultIcon" -Force -ErrorAction SilentlyContinue
}
```

之后重新启动“Windows 资源管理器”，Windows 就会回到对应磁盘类型的默认图标。这里仅删除 `DefaultIcon`，不会顺带清除同一盘符可能存在的 `DefaultLabel` 等其他设置。执行删除注册表项前，如果还想保留原有设置，可以先在注册表编辑器中导出 `DriveIcons` 项作为备份。

## 九、总结

磁盘自定义图标重启后不生效，通常不是“Windows 忘记了设置”，而是以下任一问题导致 Shell 在启动时无法正确提取图标：目录被误当作图标文件、路径不可访问、`desktop.ini` 与驱动器机制混用、ICO 文件不规范，或正确配置尚未被图标缓存重新读取。

解决时可以按这个顺序处理：

1. 确认图标是可预览的、真正的多尺寸 `.ico` 文件。
2. 将 `DriveIcons\盘符\DefaultIcon` 指向该文件的绝对路径，并带上 `,0`。
3. 优先把图标保存到启动后稳定可访问的位置。
4. 最后再重启资源管理器；只有显示未更新时才重建图标缓存。

这样处理后，问题从“重启后又看运气”变成了一个明确、可验证、也可以随时撤销的系统配置。Windows 的图标缓存不会因此突然变得可爱，但至少不再有机会替错误路径背锅。
