+++
date = '2026-08-21T20:10:00+08:00'
draft = false
title = 'BlockingQueue'
+++

`BlockingQueue` 是 JUC 中的阻塞队列接口，常用于生产者消费者模型和线程池任务队列。它的核心能力是：**队列为空时获取阻塞，队列满时插入阻塞**。

## 一、核心方法

`BlockingQueue` 对插入和获取提供了四组方法：

| 操作 | 抛异常 | 返回特殊值 | 阻塞等待 | 超时等待 |
| --- | --- | --- | --- | --- |
| 插入 | `add(e)` | `offer(e)` | `put(e)` | `offer(e, timeout, unit)` |
| 获取 | `remove()` | `poll()` | `take()` | `poll(timeout, unit)` |
| 查看队头 | `element()` | `peek()` | 不支持 | 不支持 |

实际业务中最常用的是：

- `put`：队列满时等待。
- `take`：队列空时等待。
- `offer(timeout)`：最多等待一段时间，避免无限阻塞。
- `poll(timeout)`：最多等待一段时间，避免空转。

## 二、生产者消费者模型

```java
BlockingQueue<String> queue = new ArrayBlockingQueue<>(100);

Thread producer = new Thread(() -> {
    try {
        queue.put("task");
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    }
});

Thread consumer = new Thread(() -> {
    try {
        String task = queue.take();
        System.out.println(task);
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    }
});

producer.start();
consumer.start();
```

使用阻塞队列后，生产者和消费者不需要自己写 `wait/notify`。队列内部已经处理了加锁、等待和唤醒。

## 三、常见实现

| 实现类 | 特点 |
| --- | --- |
| `ArrayBlockingQueue` | 基于数组，有界队列，适合固定容量 |
| `LinkedBlockingQueue` | 基于链表，可有界也可无界 |
| `PriorityBlockingQueue` | 按优先级排序，无界队列 |
| `DelayQueue` | 元素到期后才能被取出 |
| `SynchronousQueue` | 不存储元素，生产者和消费者直接移交 |
| `LinkedTransferQueue` | 支持更灵活的直接移交和队列缓存 |

线程池中常见的 `workQueue` 就是 `BlockingQueue<Runnable>`。

## 四、在线程池中的影响

线程池使用不同队列，行为会明显不同：

- `ArrayBlockingQueue`：容量明确，队列满后线程池才会继续扩容或拒绝。
- 无界 `LinkedBlockingQueue`：任务可能长期堆积，`maximumPoolSize` 很难发挥作用。
- `SynchronousQueue`：任务不排队，必须直接交给线程，更容易触发线程扩容。
- `PriorityBlockingQueue`：可以按优先级执行任务，但要注意任务饥饿和无界堆积。

这也是为什么配置线程池时，队列不能随手一填。队列选择会直接改变线程池的吞吐、延迟和过载表现。

## 五、容量要有边界

业务系统中不建议轻易使用无界队列。无界队列不会真的无界，它的边界最终是内存。

更稳妥的方式是使用有界队列，并明确满队列时的策略：

- 阻塞提交方。
- 快速失败。
- 降级处理。
- 记录告警。
- 交给调用方执行形成反压。

把过载暴露出来并不丢人。真正麻烦的是过载被队列藏起来，等内存撑不住时才一起爆出来。

## 六、总结

`BlockingQueue` 把“等待条件满足”封装成了队列操作，是生产者消费者模型的基础。它既是一个容器，也是线程协作工具。使用时最重要的是选对实现类，并给容量和过载策略一个明确答案。
