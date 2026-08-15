+++
date = '2025-09-10T21:23:12+08:00'
draft = false
title = 'JVM 调优'
+++

JVM 调优主要是通过调整虚拟机的配置参数、垃圾回收策略和内存分配手段，提升 Java 应用程序的性能、稳定性和可靠性。

但绝大部分情况下，并不需要特意去调优 JVM，只需要记录好日志，对程序做好性能监控，根据日志和性能监控数据修改程序，在业务层面进行优化就可以解决大多数问题。

但是通过 JVM 调优，仍可以带来一下好处：

- 性能层面：通过调整 JVM 参数和优化垃圾回收机制，能够提高 Java 应用程序的性能，减少延迟，提升系统响应速度、并发能力和吞吐量
- 资源层面：合理配置 JVM 资源，可以有效地利用硬件资源，提高系统的资源利用率，降低成本
- 稳定性：通过调优JVM，可减少内存泄漏、OOM（Out of Memory）等问题的发生，提高系统的稳定性和可靠性，降低系统崩溃的风险

JVM 调优关注两个核心指标：**吞吐量**、**停顿时间**和**堆内存占用量**；几个非核心指标：**垃圾回收次数**、**垃圾回收频率**

#### 吞吐量

程序运行过程中执行两种任务：执行业务代码的任务；进行垃圾回收的任务

吞吐量就指的是 CPU 执行业务代码任务的占用时间百分比

```bash
吞吐量 = CPU在用户应用程序运行的时间 / （CPU在用户应用程序运行的时间 + CPU垃圾回收的时间）
```

#### 停顿时间

是指一段时间内，执行 GC，而应用程序完全暂停

停顿时间越长就意味着 GC 场景下，用户线程平均等待时间越长，这回直接影响用户使用系统的体验。

#### 堆内存占用量

堆内存占用量直接影响着 GC 频率和效果：如果堆太小会导致 GC 频繁；堆太大会导致停顿时间长。

同时也是 **OOM（OutOfMemoryError）**的主要来源

#### 垃圾回收次数

是指从 JVM 启动到当前时间，GC发生的总次数

GC 非常占用 CPU 资源，如果 GC 占用的资源越多，其他程序占用的资源就会越少，影响系统吞吐量

#### 垃圾回收频率

是指单位时间内 GC 发生的次数。

频繁的进行垃圾回收可能会导致系统延迟，影响客户端系统的体验感。可以通过增大堆内存来减少垃圾回收的频率，但是这有可能会导致堆分配的内存过大，造成单次停顿时间的增加。

**目前 GC 优化方向主要是吞吐量和暂停时间**

吞吐量、暂停时间和堆内存占用量三个指标是不能同时达到。

高吞吐量会让业务程序暂有更高的 CPU 利用率，提升程序的运行速度。

而低暂停时间会让用户的系统体验感更好。

然而**高吞吐量**和**低暂停时间**是竞争关系，高吞吐量需要增大推内存，降低内存的回收的执行频率，这样势必会导致单次 GC 执行时间的延长；而为了实现低暂停时间，就需要减少堆内存，提高 GC 频率。

因此在选择 GC 算法时需要考虑应用场景：高吞吐量适用于 CPU 密集型服务、后台任务或批处理系统；低暂停时间更适合延迟敏感或实时性高的应用。

在选择垃圾回收器的时候就需要注意程序的应用场景

- Parallel以吞吐量优先
- cms以停顿时间优先
- 而G1则取折中方案: 在保证用户可接受的停顿时间的前提下,尽可能提高吞吐量

### JVM 日志

可以通过分析日志来查看 JVM 内存指标

在启动项目的时候，增加一下参数来收集 GC 日志，再通过第三方的日志分析工具来分析等到的数据

```bash
# jdk 8及以下使用
java  
-XX:+PrintGCDetails -XX:+PrintGCDateStamps 
-XX:+UseGCLogFileRotation 
-XX:+PrintHeapAtGC -XX:NumberOfGCLogFiles=5  
-XX:GCLogFileSize=20M    
-Xloggc:/opt/ard-user-gc-%t.log  
-jar abg-user-1.0-SNAPSHOT.jar 
# -Xloggc:/opt/app/ard-user/ard-user-gc-%t.log   设置日志目录和日志名称
# -XX:+UseGCLogFileRotation           开启滚动生成日志
# -XX:NumberOfGCLogFiles=5            滚动GC日志文件数，默认0，不滚动
# -XX:GCLogFileSize=20M               GC文件滚动大小，需开启UseGCLogFileRotation
# -XX:+PrintGCDetails                 开启记录GC日志详细信息（包括GC类型、各个操作使用的时间）,并且在程序运行结束打印出JVM的内存占用情况
# -XX:+ PrintGCDateStamps             记录系统的GC时间           
# -XX:+PrintGCCause                   产生GC的原因(默认开启)

# jdk 9+ 输出日志的参数
java -Xlog:gc*,gc+heap=debug:file=../log/ard-user-gc-%t.log:time,uptime,level,tags:filecount=5,filesize=20M Demo
# gc*,gc+heap=debug -> 输出 GC 事件和堆信息
# file=... -> 日志文件路径
# filecount=5,filesize=20M -> 日志轮转 5 个文件，每个 20MB
#time,uptime,level,tags -> 日志信息格式
```

直接查看得到的日志文档很不方便，将其交给日志分析工具。这里主要使用 **gceasy.io**，它是在线的，将本地日志直接上传即可。

### JVM 常用配置

**垃圾回收器的选择**

- 单核 CPU 常使用 Serial

- 多核 CPU 并且关注系统吞吐量可以选择 Parallel Scavenge（PS）加 Parallel Old（PO）的组合。这种组合利用了多核CPU的并行处理能力，通过并行处理新生代和老年代的垃圾收集，以提高系统的吞吐量和整体性能。

- 多核CPU，JDK版本1.6或1.7，并且更关注用户停顿时间，特别是在JDK版本为1.6或1.7的情况下，推荐选择Concurrent Mark-Sweep（CMS）垃圾收集器。

  CMS垃圾收集器以减少应用程序停顿时间为目标，通过与应用程序线程并发执行部分垃圾回收操作，从而降低了GC造成的停顿时间，提高了系统的响应速度和用户体验。

- 对于JDK版本为1.8及以上，并且系统具备充足的内存资源（6G及以上），且依然关注用户停顿时间的情况，推荐选择Garbage-First（G1）垃圾收集器。G1垃圾收集器是一种面向服务端应用的垃圾收集器，具有高效的垃圾回收、可预测的停顿时间和良好的内存整理能力，适用于对用户停顿时间有较高要求的应用场景。

Java 8 及以下

| GC 类型                        | 启动参数                                                    |
| ------------------------------ | ----------------------------------------------------------- |
| Serial GC                      | `-XX:+UseSerialGC`                                          |
| Parallel GC (Throughput GC)    | `-XX:+UseParallelGC`                                        |
| Parallel Old GC                | `-XX:+UseParallelOldGC`                                     |
| CMS GC (Concurrent Mark Sweep) | `-XX:+UseConcMarkSweepGC`                                   |
| G1 GC                          | `-XX:+UseG1GC`                                              |
| 输出 GC 日志                   | `-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:gc.log` |

| GC 类型       | 启动参数                                                     |
| ------------- | ------------------------------------------------------------ |
| Serial GC     | `-XX:+UseSerialGC`                                           |
| Parallel GC   | `-XX:+UseParallelGC`                                         |
| G1 GC         | `-XX:+UseG1GC` (默认)                                        |
| ZGC           | `-XX:+UseZGC`                                                |
| Shenandoah GC | `-XX:+UseShenandoahGC`                                       |
| 输出 GC 日志  | `-Xlog:gc*,gc+heap=debug:file=gc-%t.log:time,uptime,level,tags:filecount=5,filesize=20M` |

**JVM 参数配置**

Java 8 常用调优参数：

- 通常会使用`-Xms` / `-Xmx`来设置堆的最大值和最小值，将它们设置为相同的值可以防止垃圾收集器在堆大小之间进行收缩，从而减少额外的时间消耗
- 年轻代大小：`-Xmn`
- Eden/Survivor 比例：`-XX:SurvivorRatio=8`
- GC 目标停顿：`-XX:MaxGCPauseMillis=200`（对 G1 有效）

Java 9+ 常用调优参数：

- 堆大小：`-Xms` / `-Xmx`
- 年轻代大小：`-XX:InitialHeapSize` / `-XX:MaxHeapSize`
- G1 调优：
  - `-XX:MaxGCPauseMillis=200` -> 目标停顿
  - `-XX:ParallelGCThreads=8` -> 并行线程数
- ZGC / Shenandoah：
  - 自动调节大部分参数，主要调堆大小和停顿目标

### JVM 常见调优

1. 调整内存大小：频繁的垃圾回收可能是堆内存过小导致的。但是如果垃圾回收次数频繁，但是回收的对象很少，很可能是由于内存泄漏导致对象无法被正确回收，从而导致的垃圾回收频繁
2. 调整 GC 触发时机：在 CMS 和 G1 垃圾回收器下，频繁的发生 Full GC 导致程序严重卡顿。CMS 和 G1 的部分 GC 阶段是并发进行的，这意味着在垃圾收集的过程中业务线程会产生新的对象，而这些对象需要一定的内存来存储，如果不预留对应的空间，在内存不足的情况下就会引发 STW
3. 调整对象晋升到老年代的年龄阈值：老年代发生频繁的 GC，清理回收大量对象。这时提高对象晋升的年龄阈值，减少进入老年代的对象数量，缓解老年代的空间压力。但是这样会导致增加新生代内的对象数量，需要合考虑新生代和老年代的GC性能，以达到最优的系统性能平衡。
4. 调整大对象进入老年代的标准：大对象会进入直接进入老年代，如果大量大对象进入老年代，这样会迅速占用内存空间，导致频繁 GC，以此需要调整进入老年代的标准。
5. 调整内存区域比率大小：某一内存区域频繁发生GC，而其他区域的GC表现正常。可能是因为该区域内存过小。

因此，JVM 调优需要考虑一些核心的性能指标，关注实际d应用场景。通过选择正确的垃圾回收器和调整合适的参数来达到最终的预期效果。
