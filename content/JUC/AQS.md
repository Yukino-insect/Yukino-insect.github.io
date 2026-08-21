+++
date = '2025-10-22T21:25:50+08:00'
draft = false
title = 'AQS'
+++

`AQS` 是 `AbstractQueuedSynchronizer` 的缩写，位于 `java.util.concurrent.locks` 包中。它是 Java 并发包里很多同步组件的基础，例如 `ReentrantLock`、`Semaphore`、`CountDownLatch`、`ReentrantReadWriteLock`。

一句话概括：**AQS 负责排队、阻塞、唤醒和同步状态管理；具体同步器负责定义 state 的含义**。

## 一、核心思想

AQS 内部维护一个 `volatile int state`：

```java
private volatile int state;
```

`state` 是同步状态。不同组件对它的解释不同：

| 组件 | state 的含义 |
| --- | --- |
| `ReentrantLock` | 锁重入次数，0 表示未被持有 |
| `Semaphore` | 剩余许可数量 |
| `CountDownLatch` | 还需要倒数的次数 |
| `ReentrantReadWriteLock` | 同时编码读锁和写锁状态 |

AQS 提供模板方法处理排队和阻塞，子类只需要实现尝试获取、释放同步状态的逻辑。

## 二、两种模式

AQS 支持两种获取模式：

- 独占模式：同一时间只能有一个线程获取资源，例如 `ReentrantLock`。
- 共享模式：同一时间允许多个线程获取资源，例如 `Semaphore`、`CountDownLatch`。

独占模式关注“锁是不是被某个线程独占”。共享模式关注“资源是否还能被多个线程共同获取”。

## 三、等待队列

当线程获取同步状态失败时，会被包装成节点加入 AQS 的 CLH 变体队列。

```text
head -> node1 -> node2 -> node3 -> tail
```

每个节点保存线程、等待状态、前驱节点和后继节点。队列的基本原则是 FIFO：前面的线程先获得重新竞争资源的机会。

AQS 并不会让所有等待线程同时醒来争抢锁，而是尽量唤醒合适的后继节点。这样可以减少无意义竞争。

## 四、独占模式流程

以 `ReentrantLock.lock()` 为例，底层会调用 AQS 的 `acquire(1)`：

```text
acquire(1)
 -> tryAcquire(1)
      -> 成功：直接获得锁
      -> 失败：加入等待队列
 -> 在队列中判断前驱节点是否为 head
 -> 条件满足则再次尝试获取锁
 -> 仍失败则 LockSupport.park() 挂起
 -> 被唤醒后继续重试
```

释放锁时调用 `release(1)`：

```text
release(1)
 -> tryRelease(1)
 -> 如果释放成功，唤醒后继节点
```

AQS 使用 `LockSupport.park()` 和 `unpark()` 挂起、唤醒线程，而不是使用 `wait` 和 `notify`。

## 五、共享模式流程

共享模式的入口是 `acquireShared`：

```text
acquireShared(arg)
 -> tryAcquireShared(arg)
      -> 返回负数：获取失败，进入队列等待
      -> 返回 0：获取成功，但不继续传播唤醒
      -> 返回正数：获取成功，并可能继续唤醒后继节点
```

`Semaphore` 就是典型共享模式。只要许可数量足够，多个线程都可以成功获取；许可不足时，后来的线程才进入队列等待。

`CountDownLatch` 也是共享模式，只是它的含义反过来：当 `state` 还不为 0 时，等待线程获取失败；当 `state` 减到 0 后，等待线程会被批量唤醒。

## 六、模板方法

自定义同步器通常需要实现这些方法：

| 方法 | 作用 |
| --- | --- |
| `tryAcquire(int arg)` | 尝试独占获取 |
| `tryRelease(int arg)` | 尝试独占释放 |
| `tryAcquireShared(int arg)` | 尝试共享获取 |
| `tryReleaseShared(int arg)` | 尝试共享释放 |
| `isHeldExclusively()` | 当前线程是否独占同步状态 |

这些方法只负责状态判断和修改。线程入队、挂起、唤醒、取消等待等复杂流程由 AQS 统一处理。

## 七、AQS 解决了什么问题

如果没有 AQS，每个同步组件都要自己处理这些细节：

- 如何用 CAS 修改同步状态。
- 获取失败后如何排队。
- 线程什么时候应该阻塞。
- 释放资源后应该唤醒谁。
- 中断、超时、取消等待如何处理。

AQS 把这些通用逻辑抽出来，让并发工具只需要关心自己的同步语义。这就是它在 JUC 中重要的原因。

## 八、总结

AQS 的核心是 `state + CLH 队列 + LockSupport`。`state` 表达资源状态，队列表达等待顺序，`park/unpark` 负责阻塞和唤醒。理解 AQS 以后，再看 `ReentrantLock`、`Semaphore`、`CountDownLatch` 这些工具，就不会只是背 API，而是能看见它们共享的骨架。
