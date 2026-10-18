+++
date = '2025-12-28T21:35:49+08:00'
draft = false
title = 'Fail-Fast 和 Fail-Safe'
+++

## Fail-Fast

当系统检测到**非法状态、并发修改或潜在错误**时，**立即抛出异常并终止当前操作**，以防止错误继续扩散。

Fail-Fast 行为示例：

执行以下代码会抛出 `ConcurrentModificationException` 异常

```java
List<String> list = new ArrayList<>();
list.add("A");
list.add("B");
list.add("C");

for (String s : list) {
    System.out.println(s);
    list.remove(s);
}
```

为什么会抛异常？

- `ArrayList` 的 `for-each` 底层使用的是 **Iterator**
- `Iterator` 是 **Fail-Fast 的**
- 当遍历过程中，集合结构被直接修改（`list.remove`）时
- 迭代器检测到 `modCount` 与预期不一致
- **立刻抛出 `ConcurrentModificationException`**

为什么需要 **Fail-Fast**？

- 防止数据被悄悄破坏
- 防止并发 Bug 难以排查
- 让问题尽早暴露（开发阶段非常重要）

> **Fail-Fast 是一种尽力而为的错误检测机制，用来提醒：这里的代码逻辑是错的。**

注意，“尽力而为”很重要。它不保证在所有并发修改场景下都一定抛异常，因此不能把 `ConcurrentModificationException` 当成线程安全控制手段。

如何在 Fail-Fast 场景下安全的修改集合

可以使用 `Iterator.remove()`

```java
Iterator<String> it = list.iterator();
while (it.hasNext()) {
    String s = it.next();
    System.out.println(s);
    it.remove(); 
}
```

`Iterator.remove()` 会同步更新 `expectedModCount`，不会触发 Fail-Fast 机制。

可以遍历完成后再修改
```java
List<String> toRemove = new ArrayList<>();

for (String s : list) {
    if ("A".equals(s)) {
        toRemove.add(s);
    }
}

list.removeAll(toRemove);
```

## Fail-Safe

Fail-Safe 通常指遍历时不直接基于原集合结构，而是基于快照、副本或弱一致视图，从而避免因为原集合被修改就立即抛出 `ConcurrentModificationException`。

它的核心不是“绝对安全”，而是“遍历过程尽量不被并发修改打断”。如果把它理解成不会有任何并发问题，那就太乐观了。乐观到几乎不像是在写 Java。

Java 中典型的例子就是 `CopyOnWriteArrayList`

```java
List<String> list = new CopyOnWriteArrayList<>();
list.add("A");
list.add("B");
list.add("C");

for (String s : list) {
    System.out.println(s);
    list.remove(s);
}
```

这段代码不会抛出 `ConcurrentModificationException` 

为什么 `CopyOnWriteArrayList` 是 Fail-Safe？

- 迭代时操作的是数组快照
- 修改发生在副本上
- 迭代器不感知修改
- 遍历的是旧数据
- 修改的是“新数据”
- 二者互不干扰

这也带来了代价：

- 迭代期间看不到最新修改。
- 每次写入都要复制数组，写多读少的场景很不合适。
- 它适合读多写少，例如监听器列表、配置快照等。

`ConcurrentHashMap` 的迭代器则是弱一致的：遍历过程中可能看到部分新数据，也可能看不到，但一般不会因为并发修改抛出 `ConcurrentModificationException`。

## 总结

| 类型 | 典型集合 | 遍历时修改集合 | 特点 |
| --- | --- | --- | --- |
| Fail-Fast | `ArrayList`、`HashMap` | 可能抛 `ConcurrentModificationException` | 尽早暴露错误，但不保证一定检测到 |
| Fail-Safe / 弱一致 | `CopyOnWriteArrayList`、`ConcurrentHashMap` | 通常不抛该异常 | 依赖快照或弱一致视图，有可见性和性能取舍 |

写普通集合时，遍历过程中需要删除元素，优先用 `Iterator.remove()` 或先收集再批量删除。写并发集合时，要先想清楚读写比例和一致性要求，再选择具体实现。
