+++
date = '2026-08-21T00:00:00+08:00'
draft = false
title = 'JVM 故障排查'
+++

JVM 故障排查的重点不是马上知道答案，而是快速拿到能缩小范围的证据。线上问题里，最危险的不是“不知道”，而是没有证据却装作知道。那通常会把一个问题变成两个问题。

这篇文章按常见现象整理排查路径：

- OOM。
- CPU 高。
- GC 频繁或停顿过长。
- 线程阻塞、死锁。
- 内存持续上涨。
- 应用无响应。

## 一、排查前先保留现场

线上故障发生时，先尽量保留证据，再考虑重启。

优先收集：

- JVM 参数。
- GC 日志。
- 线程栈。
- 堆信息。
- 堆转储。
- 操作系统 CPU、内存、磁盘、网络指标。
- 容器资源限制和 OOM Kill 记录。

常用命令：

```bash
jcmd <pid> VM.version
jcmd <pid> VM.flags
jcmd <pid> VM.command_line
jcmd <pid> GC.heap_info
jcmd <pid> Thread.print > thread.txt
```

如果怀疑内存泄漏，导出堆转储：

```bash
jcmd <pid> GC.heap_dump /tmp/heap.hprof
```

注意：生成 heap dump 可能导致进程暂停，并占用大量磁盘空间。生产环境操作前要确认磁盘余量和业务影响。

## 二、OOM 排查

OOM 不等于堆不够。先看错误类型。

| 错误信息 | 常见原因 | 重点证据 |
| -------- | -------- | -------- |
| `Java heap space` | 堆对象过多、内存泄漏、缓存无边界 | heap dump、GC 日志 |
| `GC overhead limit exceeded` | GC 花大量时间但回收很少 | GC 日志、老年代趋势 |
| `Metaspace` | 动态类过多、类加载器泄漏 | class histogram、类加载器引用 |
| `Direct buffer memory` | 直接内存不足、Netty/NIO 泄漏 | NMT、直接内存配置 |
| `unable to create native thread` | 线程过多、系统线程限制、内存不足 | 线程数、`ulimit`、线程栈 |

### 1. 堆 OOM

典型现象：

- `OutOfMemoryError: Java heap space`。
- Full GC 频繁。
- Full GC 后堆占用下降很少。

排查步骤：

1. 确认是否有 heap dump。
2. 用 MAT、VisualVM、JProfiler 等工具查看大对象。
3. 看 dominator tree，找保留内存最大的对象。
4. 检查对象到 GC Roots 的引用链。
5. 判断是正常业务峰值、缓存过大，还是真正泄漏。

常见泄漏点：

- 静态集合持续增长。
- 本地缓存没有容量和过期策略。
- `ThreadLocal` 未清理。
- 监听器、回调、定时任务注册后未注销。
- 批处理一次性把大量数据加载到内存。
- WebSocket、Session、连接对象未释放。

### 2. 元空间 OOM

典型现象：

```text
java.lang.OutOfMemoryError: Metaspace
```

常见原因：

- CGLIB、Byte Buddy、Javassist 等动态生成类过多。
- 脚本引擎、规则引擎反复生成新类。
- 热部署后旧 `ClassLoader` 无法释放。
- 线程上下文类加载器引用住旧应用。

排查命令：

```bash
jcmd <pid> VM.classloader_stats
jcmd <pid> GC.class_histogram
```

如果只是上限太低，可以调整：

```bash
-XX:MaxMetaspaceSize=512m
```

但如果类数量持续增长，调大上限只是延后失败时间。问题还在原地，只是换了个更晚的闹钟。

### 3. 直接内存 OOM

典型现象：

```text
java.lang.OutOfMemoryError: Direct buffer memory
```

常见来源：

- NIO `ByteBuffer.allocateDirect`。
- Netty 堆外内存。
- 文件映射。
- 本地库分配。

可配置上限：

```bash
-XX:MaxDirectMemorySize=512m
```

排查时可以开启 Native Memory Tracking：

```bash
-XX:NativeMemoryTracking=summary
```

运行时查看：

```bash
jcmd <pid> VM.native_memory summary
```

NMT 有额外开销，生产环境是否开启要结合性能要求决定。

### 4. 无法创建线程

典型现象：

```text
java.lang.OutOfMemoryError: unable to create native thread
```

它通常不是 Java 堆满了，而是系统无法再创建新线程。

检查方向：

- 线程池是否无界增长。
- 是否每个请求创建线程。
- `-Xss` 是否过大。
- 操作系统线程数限制。
- 容器 PID 限制。
- 进程可用内存是否不足。

常用命令：

```bash
jcmd <pid> Thread.print > thread.txt
ps -eLf | grep <pid> | wc -l
ulimit -u
```

## 三、CPU 高排查

CPU 高要先区分是业务线程高，还是 GC 线程高。

### 1. 定位高 CPU 线程

Linux 常用流程：

```bash
top -H -p <pid>
printf "%x\n" <tid>
jcmd <pid> Thread.print > thread.txt
```

`top -H` 看到的是线程 ID，把它转成十六进制后，在 `thread.txt` 里搜索 `nid=0x...`。

### 2. 常见原因

业务线程 CPU 高：

- 死循环。
- 大集合遍历。
- 正则表达式灾难性回溯。
- JSON 序列化或反序列化过重。
- 加解密或压缩消耗 CPU。
- 日志格式化过多。
- 热点锁自旋。

GC 线程 CPU 高：

- 对象分配速率过高。
- 堆太小导致 GC 频繁。
- 大量对象存活，回收成本高。
- 内存泄漏导致 GC 反复尝试回收但效果很差。

如果线程栈里大量出现 GC 线程，同时 GC 日志显示 GC 时间占比很高，就应转向 GC 排查。

## 四、GC 频繁排查

GC 频繁不一定是坏事。Young GC 高频但停顿极短，业务没有抖动，未必需要处理。真正要关注的是 GC 是否影响吞吐、延迟和稳定性。

### 1. Young GC 频繁

看这些指标：

- 每秒分配多少内存。
- Young GC 每次回收后 Eden 是否明显下降。
- Survivor 是否放不下幸存对象。
- 是否有大量对象提前晋升老年代。

常见原因：

- 热点接口创建大量临时对象。
- 日志、字符串拼接、JSON 转换过多。
- 批量任务没有分批处理。
- 新生代偏小。

处理方向：

- 先减少热点路径不必要对象创建。
- 控制批量大小。
- 减少中间集合复制。
- 再考虑调整堆大小或收集器参数。

### 2. Full GC 频繁

Full GC 更需要警惕。

看这些问题：

- Full GC 后老年代是否明显下降。
- 是否存在大对象分配。
- 是否有元空间触发。
- 是否有显式 `System.gc()`。
- 是否有 promotion failed、to-space exhausted 等退化信号。

排查命令：

```bash
jcmd <pid> GC.heap_info
jcmd <pid> GC.class_histogram
```

如果 Full GC 后内存下降很少，要导出 heap dump 分析引用链。

### 3. GC 停顿过长

常见原因：

- 存活对象太多。
- 堆设置过大。
- 老年代对象图复杂。
- 大对象或数组过多。
- CPU limit 太低，GC 线程无法及时运行。
- 收集器不适合业务延迟目标。

处理方向：

- 分析 GC 日志中的阶段耗时。
- 降低对象存活率。
- 缩短缓存生命周期或限制容量。
- 给容器足够 CPU。
- 评估 G1、ZGC、Shenandoah 等收集器选择。

## 五、线程阻塞和死锁

接口无响应但 CPU 不高时，很可能是线程阻塞、锁等待、连接池耗尽或外部依赖慢。

### 1. 看线程状态

线程栈中常见状态：

| 状态 | 含义 |
| ---- | ---- |
| `RUNNABLE` | 正在运行或等待 CPU，也可能在 native IO |
| `BLOCKED` | 等待进入 `synchronized` 锁 |
| `WAITING` | 无限期等待，例如 `Object.wait()` |
| `TIMED_WAITING` | 限时等待，例如 `sleep`、带超时的 `park` |

导出线程栈：

```bash
jcmd <pid> Thread.print > thread.txt
```

重点观察：

- 是否大量线程阻塞在同一把锁上。
- 是否大量线程等待数据库连接池。
- 是否大量线程卡在 HTTP、Redis、MQ 等外部调用。
- 是否有死锁检测信息。

### 2. 死锁

死锁通常会在线程栈底部直接提示：

```text
Found one Java-level deadlock
```

常见原因：

- 多把锁获取顺序不一致。
- 锁中调用外部接口。
- 事务和应用锁嵌套。
- 线程池任务互相等待。

解决思路：

- 固定多把锁的获取顺序。
- 缩小锁范围。
- 锁内不要做耗时 IO。
- 使用超时锁，例如 `tryLock(timeout)`。
- 拆掉线程池里的任务互相等待。

## 六、内存持续上涨

内存上涨要区分是正常缓存预热，还是泄漏。

判断方式：

- 看 Full GC 后堆是否回落。
- 看老年代是否阶梯式上升。
- 看对象数量是否持续增长。
- 看缓存命中率和容量是否符合预期。
- 看容器 RSS 是否明显高于 JVM 堆。

可能原因：

- 堆内对象泄漏。
- 元空间类加载器泄漏。
- 直接内存增长。
- 线程数量增长。
- 本地库内存增长。
- mmap 文件映射未释放。

如果 Java 堆不高但 RSS 很高，优先检查：

- 直接内存。
- Metaspace。
- 线程栈。
- Code Cache。
- Native Memory。
- 容器或系统层 page cache。

## 七、应用无响应

应用无响应时，不要只看 JVM。

排查顺序：

1. 进程是否还存在。
2. CPU 是否打满。
3. 内存是否被 OOM Kill。
4. 线程是否都阻塞。
5. GC 是否长时间停顿。
6. 数据库、Redis、MQ、下游 HTTP 是否超时。
7. 连接池是否耗尽。
8. 磁盘 IO 是否异常。

常用命令：

```bash
jcmd <pid> Thread.print
jcmd <pid> GC.heap_info
jstat -gcutil <pid> 1000 10
```

如果进程已经被系统杀掉，要看系统日志或容器事件，而不是继续在 JVM 里找一个已经不存在的现场。

## 八、常用工具

| 工具 | 用途 |
| ---- | ---- |
| `jcmd` | JVM 诊断入口，推荐优先使用 |
| `jstack` | 导出线程栈 |
| `jmap` | 堆信息、堆转储 |
| `jstat` | GC 和类加载统计 |
| `jconsole` | 基础图形化监控 |
| VisualVM | 本地分析、采样、堆查看 |
| MAT | heap dump 分析 |
| async-profiler | CPU、分配、锁等性能分析 |
| GCViewer / GCEasy | GC 日志分析 |

新版本 JDK 中，`jcmd` 覆盖了很多旧工具能力，排查时可以优先记它。

## 九、排查模板

遇到 JVM 问题，可以按这个模板整理。

```text
现象：
- 什么时候开始？
- 影响哪些接口或任务？
- CPU、内存、GC、线程数有什么变化？

环境：
- JDK 版本：
- JVM 参数：
- 容器 CPU / 内存限制：
- 最近是否发布：

证据：
- GC 日志：
- 线程栈：
- heap dump：
- 监控截图：
- 系统日志：

初步判断：
- 是 CPU、内存、GC、锁等待，还是外部依赖？

处理动作：
- 临时止血：
- 根因修复：
- 验证方式：
```

这个模板看起来朴素，但它能逼迫排查过程回到证据上。线上问题最讨厌的地方在于，它从不因为我们语气笃定就变简单。

## 十、总结

JVM 故障排查可以抓住几条主线：

- OOM 先看错误类型，再找对应证据。
- CPU 高先定位线程，再判断业务线程还是 GC 线程。
- GC 频繁要看回收效果和业务影响。
- Full GC 后内存不下降，优先怀疑对象仍被引用。
- 应用无响应不一定是 JVM，也可能是锁、连接池或外部依赖。
- 容器环境要同时看 JVM 内存和进程 RSS。
- 重启可以止血，但重启前尽量保留线程栈、GC 日志和堆信息。

故障排查的核心是：**先保存现场，再缩小范围，最后动手修复**。没有证据的“经验判断”当然也可能对，只是那更像运气，不像工程。
