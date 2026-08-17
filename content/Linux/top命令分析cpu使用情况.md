+++
date = '2026-03-23T20:45:00+08:00'
draft = false
title = 'top 命令分析 CPU 使用情况'
+++

今天面试的时候，被面试官问到如何分析服务器 CPU 使用情况。回答得并不理想，所以重新梳理一下 `top` 命令中最常用的几个指标。

在 Linux 中，我们可以使用 `top` 命令查看当前服务器的 CPU 使用情况，以下是示例输出：

```text
top - 19:46:52 up  1:44,  2 users,  load average: 0.00, 0.00, 0.00
Tasks:  32 total,   1 running,  31 sleeping,   0 stopped,   0 zombie
%Cpu(s):  0.0 us,  0.0 sy,  0.0 ni,100.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   7746.1 total,   5931.0 free,    803.6 used,   1011.5 buff/cache
MiB Swap:   2048.0 total,   2048.0 free,      0.0 used.   6777.0 avail Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
     65 root      19  -1   72328  12412  11644 S   0.7   0.2   0:19.93 systemd-journal
```

## 一、看整体 CPU 使用率

```text
%Cpu(s):  0.0 us,  0.0 sy,  0.0 ni,100.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
```

这一行最关键，各字段含义如下：

- **us**：用户态占用 CPU 的百分比

- **sy**：内核态占用 CPU 的百分比

- **ni**：被调整过优先级的进程占用 CPU 的百分比

- **id**：空闲 CPU 的百分比

- **wa**：等待 I/O 的时间百分比

- **hi**：硬中断占用 CPU 的百分比

- **si**：软中断占用 CPU 的百分比

- **st**：被虚拟机偷走的 CPU 时间百分比

## 二、单个进程的 CPU 占用

关键列是：

```text
%CPU
```

## 三、load average

```text
load average: 0.00, 0.00, 0.00
```

表示最近 1 分钟、5 分钟、15 分钟的平均负载都几乎为 0。

`load average` 不是 CPU 使用率百分比，而是系统平均负载。它大致反映一段时间内处于可运行状态或不可中断睡眠状态的任务数量。分析时通常要结合 CPU 核心数一起看：如果 4 核机器的 1 分钟负载长期接近或超过 4，就说明系统可能已经比较繁忙。

**因此，我们可以通过 `%Cpu(s)` 查看整体 CPU 使用率；通过 `%CPU` 查看单个进程的 CPU 占用；通过 `load average` 查看最近 1 分钟、5 分钟、15 分钟的系统平均负载。**

使用 `htop` 可以获得交互体验更好的实时监控面板，界面如下：

![top命令显示](/images/posts/Linux/top命令显示.png)

上面的 `0[...]`、`1[...]` 这类条目表示每个 CPU 核心的使用情况。
