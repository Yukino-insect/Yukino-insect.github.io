+++
date = '2025-10-22T18:16:04+08:00'
draft = false
title = 'CyclicBarrier'
+++

`CyclicBarrier` 是一个可复用的线程屏障。它让一组线程互相等待，直到所有参与线程都到达屏障点，然后一起继续执行。

## 一、核心方法

| 方法 | 作用 |
| --- | --- |
| `CyclicBarrier(int parties)` | 创建屏障，指定参与线程数 |
| `CyclicBarrier(int parties, Runnable action)` | 所有线程到达后先执行 `action` |
| `await()` | 表示当前线程到达屏障并等待其他线程 |
| `await(timeout, unit)` | 等待指定时间，超时则屏障破坏 |
| `reset()` | 重置屏障 |
| `getNumberWaiting()` | 获取正在等待的线程数 |
| `isBroken()` | 判断屏障是否已被破坏 |

`CyclicBarrier` 的重点是 `cyclic`：屏障打开后会自动重置，可以继续用于下一轮等待。

## 二、使用示例

```java
int parties = 3;
CyclicBarrier barrier = new CyclicBarrier(parties, () -> {
    System.out.println("all ready");
});

ExecutorService executor = Executors.newFixedThreadPool(parties);
for (int i = 0; i < parties; i++) {
    int workerId = i;
    executor.execute(() -> {
        try {
            System.out.println("worker " + workerId + " arrive");
            barrier.await();
            System.out.println("worker " + workerId + " start");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (BrokenBarrierException e) {
            System.err.println("barrier broken");
        }
    });
}

executor.shutdown();
```

只有所有线程都执行到 `await()`，屏障才会打开。可选的 `barrierAction` 由最后一个到达屏障的线程执行。

## 三、屏障破坏

如果等待中的线程被中断、等待超时，或者屏障被 `reset()`，当前这一代屏障会被破坏，其他等待线程会收到 `BrokenBarrierException`。

这意味着使用 `CyclicBarrier` 时要认真处理异常。某个线程出了问题，不是它一个线程停下，而是整组协作都会受影响。

## 四、和 CountDownLatch 的区别

| 对比项 | `CountDownLatch` | `CyclicBarrier` |
| --- | --- | --- |
| 核心语义 | 等待计数归零 | 等待所有参与线程到达屏障 |
| 是否可复用 | 不可复用 | 可复用 |
| 谁在等待 | 通常是一个或多个外部线程等待任务完成 | 参与线程互相等待 |
| 触发方式 | `countDown()` 递减到 0 | `await()` 到达数量达到 parties |
| 可选动作 | 不支持 | 支持 `barrierAction` |
| 底层实现 | AQS | `ReentrantLock` + `Condition` |

## 五、适用场景

`CyclicBarrier` 适合多阶段并行任务，例如：

- 多个线程完成本轮计算后再进入下一轮。
- 多个服务或模块准备完成后统一开始。
- 并发测试中让一组线程在同一时刻发起请求。

如果只是主线程等待子线程完成，`CountDownLatch` 更简单。

## 六、总结

`CyclicBarrier` 的关键不是“阻塞线程”，而是“让一组线程在阶段边界对齐”。它适合可重复的多阶段协作，不适合简单的一次性等待。
