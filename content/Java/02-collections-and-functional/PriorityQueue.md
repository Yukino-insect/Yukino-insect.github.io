+++
date = '2026-03-02T08:47:23+08:00'
draft = false
title = 'PriorityQueue'
+++

今天写力扣题 [合并 K 个排序链表](https://leetcode.cn/problems/merge-k-sorted-lists) 时用到了 `java.util.PriorityQueue`。它是 Java 标准库里的优先级队列，常用于“每次取当前最小/最大元素”的场景。

`PriorityQueue` 实现了 `Queue` 接口，但它不是普通的 FIFO 队列。它的出队顺序由元素优先级决定：

```text
Collection
  └── Queue
       └── PriorityQueue
```

默认情况下，`PriorityQueue` 使用元素的自然顺序，也就是一个小顶堆：最小元素会排在队头。

## 一、基本用法

常用 API 和普通队列相同：

```java
PriorityQueue<Integer> pq = new PriorityQueue<>();

pq.offer(3);   // 入队
pq.offer(1);
pq.offer(2);

pq.peek();     // 查看队头：1，不删除
pq.poll();     // 删除并返回队头：1
pq.size();     // 当前元素数量
pq.isEmpty();  // 是否为空
```

需要注意，`PriorityQueue` 只保证队头元素是当前最小值，并不保证内部数组整体有序。因此不要用遍历结果判断排序顺序。

```java
PriorityQueue<Integer> pq = new PriorityQueue<>(List.of(3, 1, 2));
System.out.println(pq); // 可能不是 [1, 2, 3]
```

如果需要完整排序，应持续 `poll()`，或者直接使用排序 API。

## 二、自定义比较器

如果想要大顶堆，可以传入比较器：

```java
PriorityQueue<Integer> maxHeap =
        new PriorityQueue<>((a, b) -> Integer.compare(b, a));
```

不要写成：

```java
new PriorityQueue<>((a, b) -> b - a);
```

`b - a` 在整数极值下可能溢出，导致比较结果错误。使用 `Integer.compare` 更稳妥。

对象排序也一样：

```java
PriorityQueue<ListNode> pq =
        new PriorityQueue<>(Comparator.comparingInt(node -> node.val));
```

在“合并 K 个排序链表”里，可以把每条链表的头节点放入小顶堆，每次取出当前最小节点，再把它的下一个节点放回堆中。这样每个节点入堆、出堆各一次，复杂度为 `O(N log K)`。

## 三、构造方式

可以只创建空队列：

```java
PriorityQueue<Integer> pq = new PriorityQueue<>();
```

可以指定初始容量：

```java
PriorityQueue<Integer> pq = new PriorityQueue<>(16);
```

也可以从已有集合建堆：

```java
List<Integer> list = List.of(5, 1, 3);
PriorityQueue<Integer> pq = new PriorityQueue<>(list);
```

从集合构造时，`PriorityQueue` 会执行堆化，不是逐个排序。

## 四、使用限制

`PriorityQueue` 有几个容易踩的点：

1. 它不是线程安全容器。多线程共享时应自行加锁，或使用 `PriorityBlockingQueue`。
2. 它不允许插入 `null`，因为 `null` 无法参与优先级比较。
3. 它不支持按索引随机访问，也不保证遍历顺序。
4. 修改已经入堆对象的排序字段，不会触发自动重排。

第四点尤其常见：

```java
PriorityQueue<Node> pq = new PriorityQueue<>(Comparator.comparingInt(n -> n.val));
Node node = new Node(10);
pq.offer(node);

node.val = 1; // 堆结构不会因为字段变化而自动调整
```

如果元素的优先级变了，通常要先删除旧元素，再重新入队；或者在设计上避免修改堆内元素的排序字段。

## 五、复杂度

常见操作复杂度如下：

| 操作 | 复杂度 | 说明 |
| --- | --- | --- |
| `offer` | `O(log n)` | 插入后向上调整堆 |
| `poll` | `O(log n)` | 删除堆顶后向下调整堆 |
| `peek` | `O(1)` | 直接读取堆顶 |
| `remove(Object)` | `O(n)` | 需要先线性查找元素 |
| `contains(Object)` | `O(n)` | 内部不是哈希结构 |

所以，`PriorityQueue` 适合“反复取最值”，不适合“频繁查找某个元素是否存在”。

## 六、总结

`PriorityQueue` 的核心可以概括为三句话：

1. 它是基于堆的优先级队列，默认小顶堆。
2. 它只保证队头元素优先级最高，不保证整体遍历有序。
3. 比较器决定优先级，比较器写错，堆的行为也会跟着错。

写算法题时，它通常出现在 Top K、合并有序序列、Dijkstra、任务调度这类问题里。只要记住“我每次只关心当前最小或最大元素”，就该想到它。若连这个都想不到，那也不是什么灾难，只是说明题目还没把你逼到合适的位置而已。
