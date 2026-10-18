+++
date = '2025-10-22T19:44:07+08:00'
draft = false
title = 'Semaphore'
+++

`Semaphore` 是信号量，用来控制同一时间访问某个资源的线程数量。它维护一组许可，线程执行前先获取许可，执行完再释放许可。

## 一、核心方法

| 方法 | 作用 |
| --- | --- |
| `acquire()` | 获取一个许可，没有许可时阻塞等待 |
| `acquire(int permits)` | 一次获取多个许可 |
| `tryAcquire()` | 尝试获取许可，失败立即返回 `false` |
| `tryAcquire(timeout, unit)` | 在指定时间内尝试获取许可 |
| `release()` | 释放一个许可 |
| `availablePermits()` | 查看当前可用许可数 |
| `drainPermits()` | 一次性取走所有可用许可 |

许可数量可以理解为并发上限。创建 `new Semaphore(3)`，就表示最多允许 3 个线程同时进入被保护的区域。

## 二、限制并发数

```java
Semaphore semaphore = new Semaphore(3);
ExecutorService executor = Executors.newFixedThreadPool(10);

for (int i = 0; i < 10; i++) {
    int taskId = i;
    executor.execute(() -> {
        boolean acquired = false;
        try {
            semaphore.acquire();
            acquired = true;
            System.out.println("task " + taskId + " running");
            Thread.sleep(1000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            if (acquired) {
                semaphore.release();
            }
        }
    });
}

executor.shutdown();
```

`release()` 应该放在 `finally` 中。否则任务异常退出后许可不归还，后续线程可能一直等待。

## 三、尝试获取许可

如果不想一直阻塞，可以使用 `tryAcquire`：

```java
if (semaphore.tryAcquire()) {
    try {
        doBusiness();
    } finally {
        semaphore.release();
    }
} else {
    System.out.println("too many requests");
}
```

也可以设置等待时间：

```java
if (semaphore.tryAcquire(2, TimeUnit.SECONDS)) {
    try {
        doBusiness();
    } finally {
        semaphore.release();
    }
} else {
    System.out.println("timeout");
}
```

这种方式适合做本地并发保护：拿不到许可就快速失败、降级或稍后重试。

## 四、公平和非公平

`Semaphore` 默认是非公平的：

```java
Semaphore semaphore = new Semaphore(3);
```

也可以创建公平信号量：

```java
Semaphore semaphore = new Semaphore(3, true);
```

公平模式会尽量按线程等待顺序发放许可，避免后来线程插队；非公平模式吞吐量通常更高。普通业务更常用非公平模式，除非确实需要严格排队。

## 五、和限流的区别

`Semaphore` 限制的是**同时运行的并发数**，不是单位时间内的请求数。

| 工具 | 控制目标 | 是否分布式 |
| --- | --- | --- |
| `Semaphore` | 本 JVM 内同时执行的任务数 | 否 |
| Guava `RateLimiter` | 本 JVM 内每秒通过的请求速率 | 否 |
| Redis / Sentinel | 多实例间的全局流量或并发 | 可以 |
| 网关限流 | 入口请求速率 | 可以 |

如果要保护本地资源，例如文件句柄、第三方 SDK、单机连接池，`Semaphore` 很合适。如果要做多实例全局限流，它就不够了。

## 六、总结

`Semaphore` 适合控制并发访问数量。它不关心线程是谁，也不关心任务顺序，只关心还有没有许可。使用时记住一件事：获取许可和释放许可必须成对出现，否则问题迟早会来，而且多半挑你最忙的时候来。
