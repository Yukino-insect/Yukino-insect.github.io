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

如何在 Fail-Fast 场景下安全的修改集合

可以使用 `Interator.remove()`

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

即使在出现并发修改或异常情况下，系统也**不会抛出异常**，而是尽量保证当前操作能够继续完成。

**Fail-Safe** 的核心思想就是**系统不能因为一点问题就崩溃**。

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
