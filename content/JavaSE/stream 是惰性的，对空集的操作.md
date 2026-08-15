+++
date = '2026-02-17T23:51:31+08:00'
draft = false
title = 'stream 是惰性的，对空集的操作'
+++

今天我们来看一下 Java `Stream` 的懒操作

### 一、Stream 的懒操作到底是什么？

**Stream 的中间操作（`map / filter / flatMap / sorted` 等）本身不会立即执行，只有遇到终止操作（`forEach / collect / findFirst / anyMatch` 等）时，整个流水线才会一次性执行。**

这就是所谓的 **惰性**。

```java
Stream<Integer> s = list.stream()
    .filter(x -> {
        System.out.println("filter " + x);
        return x > 10;
    })
    .map(x -> {
        System.out.println("map " + x);
        return x * 2;
    });

// 到这里为止，一行都不会打印
```

只有当我们写：

```java
s.forEach(System.out::println);
```

**整条链才开始真正跑。**

### 二、懒操作是如何体现的？

#### Stream 不是存数据，而是存规则

传统写法：

```java
List<Integer> tmp = new ArrayList<>();
for (Integer x : list) {
    if (x > 10) {
        tmp.add(x * 2);
    }
}
```

Stream 写法：

```java
list.stream()
    .filter(x -> x > 10)
    .map(x -> x * 2)
    .collect(toList());
```

**本质区别：**

| 写法     | 本质                       |
| -------- | -------------------------- |
| for 循环 | 立即计算 + 中间结果落地    |
| Stream   | **构建一条操作描述流水线** |

Stream 在中间阶段只做这件事：如果将来有人要结果，那么：先 filter -> 再 map -> 再……

#### 真正执行时是「元素驱动」而不是「操作驱动」

**这是懒加载提升性能的核心点之一。**

Stream 实际执行模型是：

> **一个元素，从头跑到尾**

而不是：

> 先对所有元素 filter
>  再对所有元素 map

举个直观例子：

```java
list.stream()
    .filter(x -> x > 10)
    .map(x -> x * 2)
    .findFirst();
```

执行流程是：

```text
第1个元素 -> filter -> 不通过 -> 丢弃
第2个元素 -> filter -> 不通过 -> 丢弃
第3个元素 -> filter -> 通过 -> map -> 直接返回
```

**后面的元素完全不会执行**

### 三、为什么懒操作能提高性能？

#### 避免无用计算（短路能力）

```java
list.stream()
    .filter(x -> x > 1000)
    .findFirst();
```

如果第 3 个元素就满足条件：后面 **999,997 个元素完全不碰**

Stream 自带：

- `findFirst`
- `anyMatch`
- `allMatch`
- `noneMatch`
- `limit`

**天然是短路操作**

#### 没有中间集合，减少内存和 GC

传统写法：

```java
List<A> l1 = ...
List<B> l2 = l1.stream().map(...).toList();
List<C> l3 = l2.stream().filter(...).toList();
```

Stream 懒执行写法：

```java
l1.stream()
  .map(...)
  .filter(...)
  .collect(toList());
```

**区别：**

| 项        | 传统 | Stream |
| --------- | ---- | ------ |
| 中间 List | 多个 | 0      |
| 对象分配  | 多   | 少     |
| GC 压力   | 高   | 低     |

在 **大列表 / 高并发服务** 中，GC 压力差距非常明显。

#### 操作融合

```
.filter(...)
.map(...)
.map(...)
.filter(...)
```

**不会产生 5 次遍历**

JVM 会把它们**融合成一次遍历**。等价于：

```java
for (T t : source) {
    if (...) {
        R r1 = ...
        R r2 = ...
        if (...) {
            // terminal
        }
    }
}
```

#### 为并行流打基础

懒执行 + 无状态操作：

```java
list.parallelStream()
    .filter(...)
    .map(...)
    .collect(...)
```

JDK 才能安全地：

- 拆分数据
- 多线程并行跑流水线
- 合并结果

如果是立即执行、到处落中间结果，**并行几乎不可能**。
