+++
date = '2025-10-22T21:25:50+08:00'
draft = false
title = 'AQS'
+++

AQS 是 `AbstractQueuedSynchronizer` 的缩写，位于 `java.util.concurrent.locks` 中。

它是 Java 并发锁于同步器的基础框架，用于实现各种同步状态管理与线程等待队列机制

#### AQS 的设计思想

AQS 维护一个关键的整数变量

```java
private volatile int state;
```

`state` 表示同步状态，AQS 通过一套 `acquire/release` 模板方法操作这个 `state`，管理内部线程排队、挂起、唤醒等逻辑
##### AQS 的两种模式

- 独占模式：同一时间只能由一个线程占有资源
- 共享：多个线程可以共享资源

##### AQS 的核心组成

- 同步状态（state）：表示资源是否可用，如锁是否被持有
- 等待队列（CLH 双向队列）：当线程获取资源失败时，会进入 FIFO 等待队列
- 模板方法（模板设计模式）：子类只需实现下面几个核心方法
  - `tryAcquire(int arg)`：尝试独占式获取资源
  - `tryRelease(int arg)`：尝试独占式释放资源
  - `tryAcquireShared(int arg)`：尝试共享式获取资源
  - `tryReleaseShared(int arg)`：尝试共享式释放资源
  - `isHeldExclusicely()`：当前线程是否独占资源

> AQS 主要负责实现了线程排队、阻塞唤醒、状态维护；实现 AQS 的子类负责定义 state 的意义与修改逻辑

##### 线程获取锁的流程（独占模式）

以 `ReentrantLock` 为例

它实现的 `lock()` 方法会调用 `acquire(1)`

底层流程

```markdown
Thread-1 调用 acquire(1)
 ├─ tryAcquire(1) -> 成功？（CAS修改state=1）
 │     ├─ 成功：拿到锁，继续执行
 │     └─ 失败：进入等待队列
 │
 ├─ park() 挂起等待前驱节点唤醒
 └─ 被唤醒后重新尝试获取锁
```

当锁被释放时

```markdown
unlock() -> release(1)
 ├─ tryRelease(1) -> state=0？
 ├─ 成功则唤醒队列中下一个等待线程（LockSupport.unpark）
```

##### AQS 内部维护了一个 CLH 变体队列

它可以被视为时一个 FIFO 双向队列
```markdown
head -> [Node-1] -> [Node-2] -> [Node-3] -> tail
```

每个节点 Node 存储等待线程 `Thread`、等待状态 `waitStatus`、前后指针 `prev/next`

等待机制：

1. 线程获取锁失败 -> 进入队列尾部；
2. 前一个节点释放资源 -> 唤醒下一个节点；
3. 被唤醒的线程重新竞争锁。

##### 共享模式下的流程

```markdown
acquireShared(n)
 ├─ tryAcquireShared(n)
 │     ├─ 返回负数 -> 获取失败，入队
 │     ├─ 返回0 -> 成功但不再共享
 │     └─ 返回正数 -> 成功且可继续共享
 ├─ 等待队列中线程逐个唤醒（releaseShared）
```

##### 核心 API 指向流程图

```markdown
acquire(arg)
 ├─ if tryAcquire(arg) -> 成功
 └─ 否则：
     ├─ addWaiter(Node.EXCLUSIVE)
     ├─ acquireQueued(node, arg)
         ├─ park()
         ├─ 被唤醒后重新尝试 tryAcquire(arg)
release(arg)
 ├─ if tryRelease(arg) 成功
 └─ unparkSuccessor(head)
```

AQS 底层使用了  `LockSupport.park()` / `unpark()` 来挂起或唤醒线程，而不是传统的 `wait()/notify()`

**AQS 用“用户态的智能调度”替代了“内核态的被动调度”。**
 它通过：

- CAS 原子更新（无锁抢占）
- CLH 队列排队（顺序化竞争）
- 精准唤醒（LockSupport）
   **最大限度地减少了线程上下文切换开销。**

> **线程从用户态（User Mode）切到内核态（Kernel Mode）是非常昂贵的！**
>  每一次切换都意味着：
>
> - CPU 寄存器上下文切换
> - 内核调度
> - 缓存失效
> - TLB flush（页表缓存清空）

这些代价在高并发场景下会被无限放大。
 AQS 的设计哲学就是：**尽可能“用户态解决战斗”**。
