+++
date = '2025-09-03T19:32:53+08:00'
draft = false
title = 'Java CAS 原理'
+++

CAS 是 Compare And Swap 的缩写，中文通常叫“比较并交换”。它是一种乐观并发控制方式：先判断内存中的值是否仍然等于预期值，如果相等就更新；如果不相等，说明期间被其他线程修改过，本次更新失败。

## 一、为什么需要 CAS

多线程更新共享变量时，常见问题有三个：

- 原子性：`count++` 不是一个不可分割的操作。
- 可见性：一个线程修改后的值，其他线程不一定立刻可见。
- 有序性：编译器和 CPU 可能在不改变单线程语义的前提下重排指令。

`volatile` 能保证可见性，并通过内存屏障约束部分重排，但它不能保证复合操作的原子性。

```java
private volatile int count = 0;

public void increment() {
    count++;
}
```

上面的 `count++` 仍然包含读取、加一、写回三个步骤。多个线程同时执行时，更新可能丢失。

## 二、CAS 的基本过程

CAS 操作包含三个值：

- 内存位置中的当前值。
- 线程期望看到的旧值。
- 准备写入的新值。

流程可以表示为：

```text
读取当前值 current
 -> current == expected ?
      -> 是：写入 newValue，更新成功
      -> 否：不写入，更新失败
```

CAS 通常由 CPU 原子指令支持。Java 中的原子类会借助底层原子操作完成更新。

## 三、AtomicInteger 示例

`AtomicInteger` 使用 CAS 和 `volatile` 实现线程安全的整数更新。

```java
AtomicInteger count = new AtomicInteger(0);

int next = count.incrementAndGet();
boolean success = count.compareAndSet(next, 100);
```

常见方法：

| 方法 | 作用 |
| --- | --- |
| `get()` | 获取当前值 |
| `set(value)` | 设置新值 |
| `incrementAndGet()` | 先加一，再返回新值 |
| `getAndIncrement()` | 先返回旧值，再加一 |
| `addAndGet(delta)` | 增加指定值并返回新值 |
| `compareAndSet(expect, update)` | 当前值等于期望值时更新 |

原子类适合计数、状态标记、轻量级并发更新等场景。

## 四、自旋重试

CAS 更新失败时，常见做法是重新读取最新值，再次尝试更新：

```java
public int increment(AtomicInteger value) {
    for (;;) {
        int current = value.get();
        int next = current + 1;
        if (value.compareAndSet(current, next)) {
            return next;
        }
    }
}
```

这种循环称为自旋。竞争不激烈时，自旋 CAS 很轻量；竞争激烈时，大量线程反复失败，会浪费 CPU。

## 五、ABA 问题

CAS 只比较“值是否等于预期值”。如果一个值从 A 变成 B，又变回 A，CAS 会认为它没有变过。

```text
线程 1 读取到 A
线程 2 把 A 改成 B
线程 2 又把 B 改回 A
线程 1 比较发现仍然是 A，于是更新成功
```

如果业务只关心当前值，ABA 可能不是问题；如果业务关心中间是否发生过变化，ABA 就会造成误判。

## 六、解决 ABA

常见解决方式是增加版本号。Java 提供了 `AtomicStampedReference`：

```java
AtomicStampedReference<String> ref =
        new AtomicStampedReference<>("A", 1);

int[] stampHolder = new int[1];
String value = ref.get(stampHolder);
int stamp = stampHolder[0];

boolean success = ref.compareAndSet(
        value,
        "B",
        stamp,
        stamp + 1
);
```

它不仅比较引用值，还比较版本号。只要中间发生过更新，版本号就会变化，从而避免把“变回来了”误判成“没变过”。

## 七、CAS 的优缺点

优点：

- 不需要阻塞线程，避免一部分上下文切换成本。
- 适合低到中等竞争下的轻量级状态更新。
- 是很多 JUC 组件和原子类的基础。

缺点：

- 高竞争下可能长时间自旋，浪费 CPU。
- 单个 CAS 通常只能保证一个变量的原子更新。
- 可能遇到 ABA 问题，需要版本号或其他机制处理。

## 八、总结

CAS 的核心是“先比较，再交换”。它不是锁的完全替代品，而是一种适合特定场景的乐观更新方式。竞争轻、操作短、状态简单时，CAS 很优雅；竞争重、逻辑复杂时，强行自旋只会把问题变成 CPU 热点。
