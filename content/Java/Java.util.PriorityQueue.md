+++
date = '2026-03-02T08:47:23+08:00'
draft = false
title = 'Java.util.PriorityQueue'
+++

今天在写力扣算法题，[合并K个排序链表](https://leetcode.cn/problems/merge-k-sorted-lists)的使用用到了 `Java.util.PriorityQueue`。

`PriorityQueue` 是一个 `Queue` 的实现类，它不是普通的 FIFO 队列，而是优先级队列。继承体系为：

```markdown
Collection
   └── Queue
         └── PriorityQueue
```

它本质上是基于二叉堆实现的最小堆。默认是小堆顶，最小值优先。由于它实现了 `Queue`，因此常用方法为 

```java
pq.offer(x);   // 入堆
pq.poll();     // 取出最小值
pq.peek();     // 查看最小值
pq.isEmpty();
pq.size();
```

需要注意的是：

1. 它不是并发容器，不是线程安全的。
2. 由于是通过最小堆实现的，所以它不支持随机访问，只保证堆顶是最小的。
3. 如果我们 `PriorityQueue#peek` 出堆顶元素，然后改变该节点的值，堆不会自动重排的，必须显示的调用 `PriorityQueue#poll` 或者 `PriorityQueue#offer`

对于 `PriorityQueue` 的构造器

1. 我们可以指定比较器，改变最小堆顶的默认行为

```java
new PriorityQueue<>((a, b) -> a - b);
```

2. 可以指定容量

```java
new PriorityQueue<>(16);
```

3. 可以堆化一个集合

```java
List<Integer> list = new ArrayList<>();
PriorityQueue<Integer> pq = new PriorityQueue<>(list);
```
