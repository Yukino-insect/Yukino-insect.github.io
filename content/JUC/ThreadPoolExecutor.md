+++
date = '2025-10-23T19:05:53+08:00'
draft = false
title = 'ThreadPoolExecutor'
+++

> **线程池中的任务队列是怎么实现的？线程是怎么被管理的？线程池如何协调两者？**

------

##  一、核心类：`ThreadPoolExecutor`

Java 的线程池核心实现类是：

```
java.util.concurrent.ThreadPoolExecutor
```

它实现了线程池中所有的核心机制：

- **任务提交与缓存（BlockingQueue）**
- **线程创建与复用（Worker）**
- **线程状态与生命周期管理（ctl）**

------

##  二、线程池的核心结构

简化理解，线程池里有三样东西

```
+------------------------------------------------------+
| ThreadPoolExecutor                                   |
|------------------------------------------------------|
| - BlockingQueue<Runnable> workQueue   —— 任务队列     |
| - HashSet<Worker> workers             —— 线程集合     |
| - ctl (AtomicInteger)                 —— 状态 + 数量控制 |
| - RejectedExecutionHandler            —— 拒绝策略     |
+------------------------------------------------------+
```

### 1. 任务队列：阻塞队列

用来保存**等待执行**的任务。
 常见实现：

| 队列类型     | 类名                    | 特点                     |
| ------------ | ----------------------- | ------------------------ |
| 有界队列     | `ArrayBlockingQueue`    | 固定长度，防止任务堆积   |
| 无界队列     | `LinkedBlockingQueue`   | 可无限增长，容易 OOM     |
| 同步移交队列 | `SynchronousQueue`      | 不缓存任务，直接交给线程 |
| 优先队列     | `PriorityBlockingQueue` | 按优先级排序执行         |

> 线程池会先尝试让空闲线程执行任务；
>  如果没有空闲线程，就把任务放入队列中等待。

------

### 2. 线程集合：`HashSet<Worker>`

线程池中的每个线程都被包装成一个内部类：

```
private final class Worker extends AbstractQueuedSynchronizer implements Runnable
```

它同时扮演：

- **线程的封装器**（保存 Thread 对象）；
- **AQS 锁的实现**（用于控制中断、安全退出）；
- **任务执行循环的载体**（执行 `runWorker` 方法）。

每个 Worker 都会不断从队列中取任务执行：

```
while ((task = getTask()) != null) {
    task.run();
}
```

------

### 3. 线程控制器：`ctl`

`ctl` 是一个 `AtomicInteger`，用来同时保存：

- **线程池状态（高 3 位）**
- **当前线程数量（低 29 位）**

内部通过位运算区分：

```
// ctl 的结构: [ 高3位: 运行状态 | 低29位: 工作线程数 ]
RUNNING = -1 << COUNT_BITS
```

状态包括：

| 状态名     | 说明                           |
| ---------- | ------------------------------ |
| RUNNING    | 正常运行，接受新任务           |
| SHUTDOWN   | 不接受新任务，但执行队列中任务 |
| STOP       | 立即停止所有任务               |
| TIDYING    | 正在清理资源                   |
| TERMINATED | 已完全结束                     |

------

##  三、线程池工作流程

### 当调用 `execute(Runnable task)` 时：

```
           +-------------------------------+
           | execute(task)                 |
           +---------------+---------------+
                           |
              ┌────────────┴────────────┐
              │                         │
        1. 若当前线程数 < corePoolSize  │
              │                         │
          创建新线程执行任务            │
              │                         │
              ▼                         │
        2. 否则任务放入队列(workQueue) │
              │                         │
              ▼                         │
        3. 若队列满且线程数 < maxPoolSize│
              │                         │
          再创建新线程执行任务           │
              │                         │
              ▼                         │
        4. 否则执行拒绝策略（饱和处理） │
              │                         │
              ▼                         ▼
           END
```

------

##  四、线程管理的关键方法

| 方法                  | 作用                           |
| --------------------- | ------------------------------ |
| `addWorker()`         | 创建并启动一个 Worker 线程     |
| `getTask()`           | 从队列中取任务（阻塞等待）     |
| `runWorker()`         | Worker 主循环执行任务          |
| `processWorkerExit()` | 线程退出后的回收与计数更新     |
| `tryTerminate()`      | 检查是否所有线程都结束，关闭池 |

这些方法共同维持线程池的生命周期。

------

##  五、任务执行的核心循环（源码简化版）

```
final void runWorker(Worker w) {
    Runnable task = w.firstTask;
    try {
        while (task != null || (task = getTask()) != null) {
            w.lock(); // 防止并发中断
            try {
                task.run(); // 执行任务
            } finally {
                w.unlock();
            }
            task = null;
        }
    } finally {
        processWorkerExit(w, false);
    }
}
```

当线程执行完任务后，会去队列中取下一个任务；
 如果等待超时且线程数超过核心数，就销毁线程。

------

##  六、线程池的生命周期管理

| 方法                 | 作用                                     |
| -------------------- | ---------------------------------------- |
| `shutdown()`         | 不再接收新任务，执行完队列中的任务后关闭 |
| `shutdownNow()`      | 尝试中断正在执行的任务                   |
| `awaitTermination()` | 阻塞等待线程池关闭完成                   |

------

##  七、可视化总结图

```
                ┌──────────────┐
  execute() --> │ workQueue    │
                └────┬─────────┘
                     │ poll()
                     ▼
                ┌──────────────┐
                │ Worker(Thread)│
                └────┬─────────┘
                     │ run()
                     ▼
             [ task.run() ]
                     │
                     ▼
                ┌──────────────┐
                │ processWorkerExit()│
                └──────────────┘
```

------

##  总结一句话

> **线程池 = 阻塞队列 + 线程集合 + 状态控制器**
>
> - 阻塞队列负责任务的“排队与缓存”；
> - Worker 线程负责“执行与复用”；
> - ctl 负责“生命周期与状态同步”；
>
> 三者配合，实现了一个高性能、可伸缩的并发执行框架。
