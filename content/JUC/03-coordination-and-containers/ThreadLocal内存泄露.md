+++
date = '2026-02-26T15:05:26+08:00'
draft = false
title = 'ThreadLocal 为什么会引起内存泄露'
+++

`ThreadLocal` 用于为每个线程保存一份独立变量。它常用于保存用户上下文、traceId、数据库连接上下文等线程级数据。

## 一、ThreadLocal 的存储位置

`ThreadLocal` 本身不直接保存业务值。真正的数据保存在当前线程对象内部的 `ThreadLocalMap` 中。

可以简化理解为：

```text
Thread -> ThreadLocalMap -> Entry(ThreadLocal, value)
```

每个线程都有自己的 `ThreadLocalMap`，因此不同线程访问同一个 `ThreadLocal` 时，拿到的是各自线程内部的值。

## 二、弱引用和强引用

`ThreadLocalMap.Entry` 的 key 是对 `ThreadLocal` 的弱引用，value 是普通强引用。

这意味着：如果外部没有强引用指向某个 `ThreadLocal`，它可能被 GC 回收。此时 Entry 的 key 变成 `null`，但 value 仍然可能被线程强引用着。

如果线程很快结束，问题不大。线程结束后，整个 `ThreadLocalMap` 都会被回收。

真正危险的是线程池。线程池中的线程会长期存活，value 可能长期滞留在线程对象中。

## 三、泄露和脏数据

`ThreadLocal` 使用不当有两个问题：

1. 内存泄露：value 长期无法释放。
2. 数据串扰：线程复用后，上一个任务留下的数据被下一个任务读到。

数据串扰在 Web 应用中尤其危险。例如用户 A 的上下文没有清理，线程复用后处理用户 B 的请求，可能读到错误用户信息。

## 四、正确写法

使用 `ThreadLocal` 后应在 `finally` 中清理：

```java
try {
    USER_CONTEXT.set(user);
    doBusiness();
} finally {
    USER_CONTEXT.remove();
}
```

这样无论业务是否抛异常，都能清理当前线程中的数据。

## 五、总结

`ThreadLocal` 不是不能用，而是必须明确生命周期。在线程池和 Web 容器中，使用完后调用 `remove` 是基本要求。
