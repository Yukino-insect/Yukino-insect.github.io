+++
date = '2025-10-22T17:54:13+08:00'
draft = false
title = 'CountDownLatch'
+++

`CountDownLatch` 是 JUC 中的同步辅助工具，用于让一个或多个线程等待其他线程完成操作。它的核心语义是：**倒计时归零之前等待，归零之后放行**。

## 一、核心方法

| 方法 | 作用 |
| --- | --- |
| `CountDownLatch(int count)` | 创建指定计数的倒计时器 |
| `await()` | 当前线程等待，直到计数归零 |
| `await(timeout, unit)` | 最多等待指定时间 |
| `countDown()` | 计数减一 |
| `getCount()` | 获取当前计数 |

`CountDownLatch` 是一次性的。计数归零后不能重置，如果需要重复使用屏障，应考虑 `CyclicBarrier`。

## 二、等待多个任务完成

最常见场景是主线程等待多个子任务结束：

```java
int taskCount = 5;
CountDownLatch latch = new CountDownLatch(taskCount);
ExecutorService executor = Executors.newFixedThreadPool(taskCount);

for (int i = 0; i < taskCount; i++) {
    int taskId = i;
    executor.execute(() -> {
        try {
            System.out.println("task " + taskId + " running");
        } finally {
            latch.countDown();
        }
    });
}

latch.await();
System.out.println("all tasks finished");
executor.shutdown();
```

`countDown()` 应该放在 `finally` 中。否则任务抛异常后没有倒数，等待线程可能永远阻塞。

## 三、等待统一开始信号

也可以让多个线程等待同一个开始信号：

```java
CountDownLatch startSignal = new CountDownLatch(1);
ExecutorService executor = Executors.newFixedThreadPool(3);

for (int i = 0; i < 3; i++) {
    executor.execute(() -> {
        try {
            startSignal.await();
            System.out.println(Thread.currentThread().getName() + " start");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    });
}

System.out.println("ready");
startSignal.countDown();
executor.shutdown();
```

这种写法常用于压测、并发测试或等待初始化完成。

## 四、和 wait 的区别

`CountDownLatch.await()` 是同步工具的等待方法，不需要调用方持有对象锁。

`Object.wait()` 必须在 `synchronized` 块中调用，并且需要其他线程通过 `notify` 或 `notifyAll` 唤醒。

业务代码中，`CountDownLatch` 比手写 `wait/notify` 更清楚，也更不容易出错。

## 五、总结

`CountDownLatch` 适合“一批任务完成后再继续”或“多个线程等待同一信号”的场景。它只负责等待计数归零，不保证任务执行顺序，也不能重复使用。
