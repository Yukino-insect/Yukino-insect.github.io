+++
date = '2025-09-02T22:33:38+08:00'
draft = false
title = 'Java 锁的作用'
+++

Java 中的锁用于协调多个线程对共享资源的访问。它不只是“防止同时进入一段代码”，还承担着可见性、原子性和执行顺序控制的职责。

## 一、锁解决什么问题

锁主要解决四类并发问题：

- 互斥访问：同一时间只允许一个线程进入临界区。
- 原子性：让一组操作作为整体执行，避免中间状态被其他线程观察或修改。
- 可见性：释放锁前的修改，对后续获取同一把锁的线程可见。
- 协作顺序：配合条件队列或等待通知机制，让线程按业务条件协作。

所谓“同一把锁”很重要。如果两个线程锁的不是同一个对象，就不存在互斥和可见性保证。

## 二、synchronized

`synchronized` 是 JVM 内置锁，使用简单，退出同步块时会自动释放。

```java
private final Object lock = new Object();

public void update() {
    synchronized (lock) {
        doUpdate();
    }
}
```

它适合大多数普通互斥场景。优点是语法简单、不容易忘记释放；缺点是不支持超时获取、可中断获取和公平锁配置。

## 三、ReentrantLock

`ReentrantLock` 是 JUC 提供的可重入锁，基于 AQS 实现。

```java
private final ReentrantLock lock = new ReentrantLock();

public void update() {
    lock.lock();
    try {
        doUpdate();
    } finally {
        lock.unlock();
    }
}
```

相比 `synchronized`，它提供了更多能力：

- `tryLock()`：尝试获取锁，失败立即返回。
- `tryLock(timeout, unit)`：在指定时间内尝试获取锁。
- `lockInterruptibly()`：等待锁时可以响应中断。
- 公平锁：构造时传入 `true` 可以按等待顺序获取锁。
- 多个 `Condition`：可以为一把锁创建多个等待队列。

它的代价是必须手动释放锁，因此一定要在 `finally` 中调用 `unlock()`。

## 四、ReadWriteLock

`ReadWriteLock` 把锁拆成读锁和写锁，适合读多写少的场景。

```java
private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
private final Lock readLock = rwLock.readLock();
private final Lock writeLock = rwLock.writeLock();

public String read() {
    readLock.lock();
    try {
        return value;
    } finally {
        readLock.unlock();
    }
}

public void write(String newValue) {
    writeLock.lock();
    try {
        value = newValue;
    } finally {
        writeLock.unlock();
    }
}
```

读写规则是：

- 读锁和读锁可以共存。
- 读锁和写锁互斥。
- 写锁和写锁互斥。

如果写操作很多，读写锁的收益会下降，甚至不如普通互斥锁简单稳定。

## 五、StampedLock

`StampedLock` 提供写锁、悲观读锁和乐观读。乐观读不会阻塞写线程，但读取后必须校验戳是否仍然有效。

```java
class Point {
    private final StampedLock lock = new StampedLock();
    private double x;
    private double y;

    public void move(double deltaX, double deltaY) {
        long stamp = lock.writeLock();
        try {
            x += deltaX;
            y += deltaY;
        } finally {
            lock.unlockWrite(stamp);
        }
    }

    public double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead();
        double currentX = x;
        double currentY = y;

        if (!lock.validate(stamp)) {
            stamp = lock.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }

        return Math.sqrt(currentX * currentX + currentY * currentY);
    }
}
```

`StampedLock` 性能潜力更高，但使用复杂度也更高。它不可重入，使用时要非常谨慎。

## 六、如何选择

| 场景 | 建议 |
| --- | --- |
| 普通互斥同步 | 优先使用 `synchronized` |
| 需要超时、可中断、公平锁 | 使用 `ReentrantLock` |
| 读多写少 | 使用 `ReadWriteLock` |
| 读很多、写很少且能接受复杂度 | 考虑 `StampedLock` |
| 简单计数或状态更新 | 优先考虑原子类 |
| 线程协作 | 优先考虑 JUC 工具类，而不是手写多锁 |

## 七、总结

锁的作用不是让代码看起来“线程安全”，而是明确地保护共享状态。选择锁时先问三个问题：共享资源是什么、竞争是否激烈、是否需要超时或条件队列。问题问清楚了，工具通常也就不难选。
