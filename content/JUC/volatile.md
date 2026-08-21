+++
date = '2026-08-21T20:00:00+08:00'
draft = false
title = 'volatile'
+++

`volatile` 是 Java 提供的轻量级同步机制。它主要解决共享变量的**可见性**和部分**有序性**问题，但不能保证复合操作的原子性。

## 一、可见性问题

多线程环境下，每个线程可能会把共享变量缓存到自己的工作内存中。一个线程修改变量后，其他线程不一定立刻读到最新值。

使用 `volatile` 修饰变量后，线程写入该变量会把新值刷新到主内存，其他线程读取时会尽量从主内存获取最新值。

```java
private volatile boolean running = true;

public void stop() {
    running = false;
}

public void run() {
    while (running) {
        doWork();
    }
}
```

这里 `running` 适合使用 `volatile`，因为它只是一个状态标记，写入和读取都是单次操作。

## 二、有序性

`volatile` 还会通过内存屏障约束指令重排。

对 `volatile` 变量的写入，具有释放语义：写入前的普通变量修改，对之后读取该 `volatile` 变量的线程可见。

对 `volatile` 变量的读取，具有获取语义：读取后能看到写入线程在写 `volatile` 前完成的修改。

常见例子是双重检查锁单例：

```java
public class Singleton {
    private static volatile Singleton instance;

    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

这里 `volatile` 的作用不是让 `new Singleton()` 原子化，而是防止对象引用赋值和对象初始化之间发生危险重排。

## 三、不能保证原子性

`volatile` 不能保证复合操作原子性：

```java
private volatile int count = 0;

public void increment() {
    count++;
}
```

`count++` 包含读取、加一、写回三个步骤。多个线程同时执行时，仍然可能丢失更新。

如果要保证计数原子性，应使用 `AtomicInteger` 或锁：

```java
private final AtomicInteger count = new AtomicInteger();

public void increment() {
    count.incrementAndGet();
}
```

## 四、适用场景

`volatile` 适合这些场景：

- 状态标记，例如 `running`、`closed`、`initialized`。
- 一个线程写，多个线程读。
- 写入不依赖当前值。
- 配合锁实现安全发布或双重检查。

不适合这些场景：

- 自增、自减等复合操作。
- 多个变量之间需要保持一致。
- 读改写逻辑依赖旧值。
- 临界区中有复杂业务逻辑。

## 五、和 synchronized 的区别

| 对比项 | `volatile` | `synchronized` |
| --- | --- | --- |
| 可见性 | 支持 | 支持 |
| 有序性 | 支持部分重排约束 | 支持 |
| 原子性 | 只保证单次读写 | 保证临界区原子执行 |
| 阻塞 | 不会阻塞线程 | 竞争时可能阻塞 |
| 使用场景 | 状态标记、轻量可见性 | 复合操作、临界区保护 |

## 六、总结

`volatile` 不是轻量版锁。它适合表达“这个变量的最新值要被其他线程看到”，不适合保护一段复杂逻辑。判断能不能用它时，只需要问一句：这次更新是否依赖旧值，并且是否需要和其他变量一起保持一致？如果答案是肯定的，那就别勉强它了。
