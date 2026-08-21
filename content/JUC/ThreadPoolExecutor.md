+++
date = '2025-10-23T19:05:53+08:00'
draft = false
title = 'ThreadPoolExecutor'
+++

`ThreadPoolExecutor` 是 Java 线程池的核心实现。它把任务队列、工作线程集合、线程池状态和拒绝策略组合在一起，提供了一套可控的并发执行框架。

如果说“线程池”文章适合回答怎么配置，那么这篇更适合回答：**线程池内部到底怎么接收任务、创建线程、复用线程和结束线程**。

## 一、核心结构

`ThreadPoolExecutor` 可以简化成四个部分：

```text
ThreadPoolExecutor
 ├─ ctl：线程池运行状态 + 工作线程数量
 ├─ workQueue：等待执行的任务队列
 ├─ workers：工作线程集合
 └─ handler：拒绝策略
```

其中最关键的是 `ctl`、`workQueue` 和 `Worker`。

## 二、ctl：状态和线程数

`ctl` 是一个 `AtomicInteger`，同时保存两类信息：

- 高 3 位表示线程池状态。
- 低 29 位表示当前工作线程数量。

线程池状态包括：

| 状态 | 含义 |
| --- | --- |
| `RUNNING` | 接收新任务，也处理队列中的任务 |
| `SHUTDOWN` | 不接收新任务，但继续处理队列中的任务 |
| `STOP` | 不接收新任务，不处理队列任务，并中断正在执行的任务 |
| `TIDYING` | 所有任务结束，工作线程数为 0，准备执行终止钩子 |
| `TERMINATED` | 线程池完全终止 |

把状态和线程数量放进同一个原子变量，是为了在并发环境下用一次 CAS 同时保证状态判断和线程数变更的正确性。

## 三、Worker：工作线程

线程池中的每个工作线程都会被包装成 `Worker`。它主要做三件事：

- 保存真正执行任务的 `Thread`。
- 保存启动时携带的第一个任务 `firstTask`。
- 作为一个简化锁，控制线程中断和执行状态。

工作线程启动后，会进入 `runWorker` 循环：

```java
final void runWorker(Worker worker) {
    Runnable task = worker.firstTask;
    worker.firstTask = null;

    try {
        while (task != null || (task = getTask()) != null) {
            try {
                task.run();
            } finally {
                task = null;
            }
        }
    } finally {
        processWorkerExit(worker, false);
    }
}
```

真实源码比这复杂得多，但主干逻辑就是：先执行初始任务，然后不断从队列里取任务，直到取不到任务或线程池需要退出。

## 四、execute 的执行流程

调用 `execute(Runnable command)` 后，线程池大致按下面流程处理：

```text
execute(command)
 -> 如果工作线程数 < corePoolSize
      -> 创建核心线程执行 command
 -> 否则尝试把 command 放入 workQueue
      -> 入队成功后再次检查线程池状态
      -> 如果线程池已关闭，则移除任务并执行拒绝策略
      -> 如果没有工作线程，则补一个空任务线程
 -> 如果入队失败
      -> 尝试创建非核心线程执行 command
 -> 如果创建失败
      -> 执行拒绝策略
```

这里有两个容易被忽略的点。

第一，任务入队成功后还会再次检查线程池状态。因为入队前线程池可能还在运行，入队后可能已经被关闭。

第二，如果任务已经入队，但工作线程数是 0，线程池会补充一个不带初始任务的 Worker，让它去队列中取任务执行。

## 五、getTask 如何取任务

`getTask()` 负责从队列中取任务，并决定当前 Worker 是否应该退出。

核心判断包括：

- 线程池是否已经进入 `STOP`。
- 线程池是否是 `SHUTDOWN` 且队列已经为空。
- 当前线程数是否超过 `maximumPoolSize`。
- 当前线程是否允许超时退出。

对于核心线程，默认会一直阻塞等待任务。对于超过核心线程数的非核心线程，如果空闲时间超过 `keepAliveTime`，就会退出。

如果调用了 `allowCoreThreadTimeOut(true)`，核心线程空闲超时后也可以退出。

## 六、任务队列的影响

不同队列会改变线程池行为：

- 使用无界队列时，任务通常会一直入队，线程数很难超过 `corePoolSize`。
- 使用有界队列时，队列满后线程池才会继续扩容到 `maximumPoolSize`。
- 使用 `SynchronousQueue` 时，任务不能排队，必须直接交给工作线程，因此更容易创建新线程。

这就是为什么线程池参数不能孤立理解。`maximumPoolSize` 是否生效，很大程度取决于 `workQueue`。

## 七、关闭流程

`shutdown()` 和 `shutdownNow()` 的差异在于是否继续处理队列任务：

| 方法 | 行为 |
| --- | --- |
| `shutdown()` | 不再接收新任务，继续执行已提交和队列中的任务 |
| `shutdownNow()` | 不再接收新任务，尝试中断正在执行的任务，并返回队列中尚未执行的任务 |
| `awaitTermination()` | 等待线程池进入终止状态 |

线程池不会粗暴杀死线程。`shutdownNow()` 也只是调用中断，任务是否能停下来，取决于任务本身是否响应中断。

## 八、钩子方法

`ThreadPoolExecutor` 提供了几个扩展点：

```java
protected void beforeExecute(Thread t, Runnable r) {
}

protected void afterExecute(Runnable r, Throwable t) {
}

protected void terminated() {
}
```

它们常用于统计耗时、记录异常、清理上下文等工作。需要注意的是，如果任务通过 `submit` 提交，异常会被封装进 `Future`，`afterExecute` 的 `Throwable` 参数可能是 `null`，需要额外从 `Future` 中取出异常。

## 九、总结

`ThreadPoolExecutor` 的本质是：

- 用 `ctl` 原子维护线程池状态和线程数量。
- 用 `workQueue` 缓冲等待执行的任务。
- 用 `Worker` 循环执行任务并复用线程。
- 用拒绝策略处理超过承载能力的任务。

理解这几件事以后，线程池的很多行为就不再神秘。所谓源码，拆开以后也只是几个边界条件被小心地放在一起。只是小心这种东西，恰好最不应该省。
