+++
date = '2026-03-10T19:35:33+08:00'
draft = false
title = 'java.util.concurrent.DelayQueue'
+++

`DelayQueue` 是 Java 并发包中的无界阻塞队列。队列中的元素必须实现 `Delayed` 接口，只有元素到期后，才能被消费者取出。

## 一、适用场景

`DelayQueue` 适合处理延迟执行类任务，例如：

1. 订单超时关闭。
2. 缓存过期清理。
3. 任务延迟重试。
4. 会话超时检测。
5. 若干秒后执行某个动作。

它不适合要求严格持久化和分布式可靠调度的场景。如果任务不能丢失，应使用 MQ 延迟消息、数据库任务表或专业调度系统。

## 二、底层结构

`DelayQueue` 底层使用优先队列，队头永远是最早到期的元素。

即使队列中已经有元素，只要队头元素还没有到期，调用 `take` 的线程也会阻塞等待。只有队头元素到期后，消费者才能取到它。

## 三、Delayed 接口

队列元素必须实现 `Delayed`：

```java
class DelayTask implements Delayed {
    private final long executeAt;

    DelayTask(long delayMillis) {
        this.executeAt = System.currentTimeMillis() + delayMillis;
    }

    @Override
    public long getDelay(TimeUnit unit) {
        long delay = executeAt - System.currentTimeMillis();
        return unit.convert(delay, TimeUnit.MILLISECONDS);
    }

    @Override
    public int compareTo(Delayed other) {
        return Long.compare(this.getDelay(TimeUnit.MILLISECONDS),
            other.getDelay(TimeUnit.MILLISECONDS));
    }
}
```

`getDelay` 用来判断元素是否到期，`compareTo` 用来决定多个元素的先后顺序。

## 四、注意点

`DelayQueue` 是内存队列，应用重启后任务会丢失。它也不是分布式队列，多实例部署时每个实例都有自己的队列。

因此，它更适合单 JVM 内的延迟任务。如果业务要求任务可靠执行、可追踪、可补偿，就应该选择持久化方案。
