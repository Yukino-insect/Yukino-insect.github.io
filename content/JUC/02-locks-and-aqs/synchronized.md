+++
date = '2025-12-12T19:09:22+08:00'
draft = false
title = 'synchronized'
+++

`synchronized` 是 Java 语言层面的内置锁，用于保证临界区代码的互斥、可见性和有序性。它不需要手动释放锁，线程退出同步块或同步方法时，JVM 会自动释放对应的监视器锁。

## 一、三种用法

### 1. 修饰代码块

```java
private final Object lock = new Object();

public void update() {
    synchronized (lock) {
        doUpdate();
    }
}
```

锁对象是括号中的 `lock`。不同锁对象之间互不影响。

### 2. 修饰实例方法

```java
public synchronized void update() {
    doUpdate();
}
```

实例同步方法锁住的是当前对象，也就是 `this`。

### 3. 修饰静态方法

```java
public static synchronized void updateGlobal() {
    doUpdate();
}
```

静态同步方法锁住的是当前类的 `Class` 对象，例如 `Demo.class`。

## 二、能保证什么

`synchronized` 主要保证三件事：

- 原子性：同一把锁保护的代码，同一时间只能有一个线程执行。
- 可见性：释放锁前的修改，对后续获取同一把锁的线程可见。
- 有序性：同步块内外的指令重排会受到锁语义约束。

注意，必须是**同一把锁**才有这些保证。一个方法锁 `this`，另一个方法锁 `new Object()`，它们之间没有互斥关系。

## 三、字节码层面的实现

同步代码块会编译成 `monitorenter` 和 `monitorexit` 指令：

```text
monitorenter
  执行同步代码
monitorexit
```

如果同步块内抛出异常，编译器也会生成异常路径上的 `monitorexit`，确保锁能释放。

同步方法则不会直接在方法体里生成这两个指令，而是在方法访问标志中带上 `ACC_SYNCHRONIZED`，由 JVM 在方法调用和返回时隐式完成加锁和解锁。

## 四、对象头和 Monitor

Java 对象头中的 Mark Word 会记录锁相关信息，例如锁标志位、线程 ID、hashCode、GC 年龄等。

当线程进入同步块时，JVM 会根据对象头中的锁状态选择不同策略。竞争较轻时，可以使用轻量级锁和 CAS；竞争严重时，会膨胀为重量级锁，由 `ObjectMonitor` 管理等待队列和阻塞唤醒。

可以简化理解为：

```text
对象
 └─ 对象头 Mark Word
      -> 无锁
      -> 轻量级锁
      -> 重量级锁 Monitor
```

## 五、锁升级

现代 JVM 中，`synchronized` 会根据竞争情况优化锁实现。常见状态包括：

| 锁状态 | 特点 |
| --- | --- |
| 无锁 | 没有线程进入同步区域 |
| 轻量级锁 | 通过 CAS 和栈帧中的锁记录尝试获取锁 |
| 重量级锁 | 竞争激烈时膨胀为 Monitor，线程阻塞等待 |

早期 HotSpot 还包含偏向锁优化，但根据 OpenJDK JEP 374，从 JDK 15 开始偏向锁默认禁用，并废弃相关 JVM 参数。因此现在学习 `synchronized` 时，更应该关注轻量级锁、重量级锁和 Monitor，而不是把偏向锁当成永远存在的主线。

## 六、Monitor 内部结构

重量级锁依赖 JVM 内部的 `ObjectMonitor`。可以简化成：

```text
ObjectMonitor
 ├─ Owner：当前持有锁的线程
 ├─ EntryList：等待进入同步块的线程
 ├─ WaitSet：调用 wait 后等待唤醒的线程
 └─ Recursions：重入次数
```

`EntryList` 和 `WaitSet` 容易混淆：

- 获取锁失败进入的是 `EntryList`。
- 已经持有锁并调用 `wait()` 后进入的是 `WaitSet`。

调用 `notify` 或 `notifyAll` 唤醒的是 `WaitSet` 中的线程，被唤醒后它们仍然要重新竞争锁。

## 七、可重入性

`synchronized` 是可重入锁。同一个线程已经持有某把锁时，可以再次进入由同一把锁保护的同步代码。

```java
public synchronized void outer() {
    inner();
}

public synchronized void inner() {
    doSomething();
}
```

如果不可重入，`outer` 调用 `inner` 时会把自己堵住。幸好 JVM 没有设计成那样，不然很多代码会显得过于悲惨。

## 八、和 ReentrantLock 的区别

| 对比项 | `synchronized` | `ReentrantLock` |
| --- | --- | --- |
| 实现层级 | JVM 内置 | JUC 类库，基于 AQS |
| 释放方式 | 自动释放 | 必须手动 `unlock` |
| 可中断获取 | 不支持 | 支持 `lockInterruptibly` |
| 超时获取 | 不支持 | 支持 `tryLock(timeout)` |
| 公平锁 | 不支持显式配置 | 可配置公平或非公平 |
| 条件队列 | 一个对象对应一个 WaitSet | 可创建多个 `Condition` |

普通同步场景优先考虑 `synchronized`，代码更简洁，也不容易忘记释放锁。需要超时、可中断、公平锁、多条件队列时，再使用 `ReentrantLock`。

## 九、总结

`synchronized` 的表层语义很简单：进入时加锁，退出时解锁。底层则由对象头、CAS、锁升级和 Monitor 协作完成。使用时最重要的是确认锁对象是否正确、锁范围是否足够小，以及不要在锁内执行不必要的耗时操作。
