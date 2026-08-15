+++
date = '2025-10-22T19:19:22+08:00'
draft = false
title = 'ReadWriteLock'
+++

`ReadWriteLock` 是 Java 并发包中的读写锁接口。它把锁拆成读锁和写锁，用于读多写少的场景。

## 一、为什么需要读写锁

如果使用普通互斥锁，例如 `ReentrantLock`，无论读操作还是写操作，同一时间都只能有一个线程进入临界区。

但很多业务中读操作不会修改共享数据，多个读线程同时执行是安全的。读写锁允许多个线程同时持有读锁，从而提高读多写少场景的吞吐量。

## 二、互斥规则

读写锁的基本规则是：

1. 读锁和读锁可以共存。
2. 读锁和写锁互斥。
3. 写锁和写锁互斥。

也就是说，只要有线程持有写锁，其他线程不能读也不能写。只要有线程持有读锁，写线程也必须等待。

## 三、使用示例

```java
private final ReadWriteLock lock = new ReentrantReadWriteLock();
private final Lock readLock = lock.readLock();
private final Lock writeLock = lock.writeLock();

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

锁一定要在 `finally` 中释放，避免异常导致锁无法释放。

## 四、和 StampedLock 的区别

`StampedLock` 提供乐观读能力。乐观读期间不阻塞写线程，但读取后必须校验版本戳。如果校验失败，说明读取期间发生过写入，需要退化为悲观读或重新读取。

`ReadWriteLock` 更容易理解，也更适合大多数普通业务场景。`StampedLock` 性能潜力更高，但使用复杂度也更高。

## 五、适用边界

读写锁适合读多写少。如果写操作频繁，读线程和写线程会频繁互相等待，收益会明显下降。此时普通互斥锁可能更简单，也更稳定。
