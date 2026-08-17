+++
date = '2026-01-02T20:20:26+08:00'
draft = false
title = 'Java 集合'
+++

**在 Java 21 之前，Java 集合一共有两个体系，顶层接口的架构分别为**：

```textt
Iterable
    └── Collection
            ├── List
            ├── Set
            │   └── SortedSet
            │       └── NavigableSet
            └── Queue
                └── Deque
```

****

```textt
Map
 └── SortedMap
       └── NavigableMap
```

这些接口为他们的实现类提供了基本的操作方法。在使用的时候可以用接口引用实现类，统一操作不同的集合。

**Iterable&lt;E&gt;** 是最顶层迭代接口，它提供了基本的遍历方法。所有集合类都可以通过迭代器遍历集合：

```java
Iterator<E> iterator() // 获取迭代器
void forEach(Consumer<? super T> action)
Spliterator<E> spliterator()
```

**Collection&lt;E&gt;** 接口为集合提供了基本增删查统的能力

新增

```java
boolean add(E e)
boolean addAll(Collection<? extends E> c)
```

删除

```java
boolean remove(Object o)
boolean removeAll(Collection<?> c)
boolean retainAll(Collection<?> c) // 删除其他元素，只保留指定元素
void clear()
```

查询

```java
boolean contains(Object o)
boolean containsAll(Collection<?> c)
boolean isEmpty()
int size()
```

遍历

```java
Iterator<E> iterator()
```

数组转换

```java
Object[] toArray()
<T> T[] toArray(T[] a)
```

&gt; 可以看到，如果要将集合转化为一维数组时直接调用 `toArray()`。但是如果要转化成二维数组，需要使用 `toArray(new int[][])`

```java
boolean removeIf(Predicate filter)
Stream<E> stream()
Stream<E> parallelStream()
void forEach(Consumer action)
```

&gt; 在实际的应用中，我们应该使用符合语义的顶层接口来引用实现类。

**List&lt;E&gt;** 接口

```java
E get(int index)	// 按位置取元素
E set(int index, E element) 	// 修改元素 
void add(int index, E element) 	// 指定位置插入
E remove(int index)		// 指定位置删除 
int indexOf(Object o)	// 查找首次     
int lastIndexOf(Object o)	// 查找末次     
List<E> subList(int fromIndex, int toIndex)	 // 子列表视图 
```

**Set&lt;E&gt;** 接口最重要的是这 3 个核心方法

| API           | 说明                         |
| ------------- | ---------------------------- |
| `add(e)`      | 添加去重的关键方法           |
| `contains(e)` | 基于 equals 检查元素是否存在 |
| `remove(e)`   | 删除元素                     |

**Queue&lt;E&gt;** 接口有 6 个核心 API

| 操作                   | 抛异常版本  | 返回特殊值版本 | 说明             |
| ---------------------- | ----------- | -------------- | ---------------- |
| **入队（添加元素）**   | `add(e)`    | `offer(e)`     | 把元素插入队尾   |
| **出队（移除头元素）** | `remove()`  | `poll()`       | 移除队头         |
| **取队头（不移除）**   | `element()` | `peek()`       | 查看队头但不删除 |

**Deque&lt;E&gt;** 是双端队列的接口，提供 12 个核心 API

头部操作

| 操作                   | 抛异常版本      | 返回特殊值版本  | 说明           |
| ---------------------- | --------------- | --------------- | -------------- |
| **头部插入**           | `addFirst(e)`   | `offerFirst(e)` | 在队头加入元素 |
| **头部删除**           | `removeFirst()` | `pollFirst()`   | 删除并返回队头 |
| **获取头部（不删除）** | `getFirst()`    | `peekFirst()`   | 查看队头       |

尾部操作

| 操作                   | 抛异常版本     | 返回特殊值版本 | 说明           |
| ---------------------- | -------------- | -------------- | -------------- |
| **尾部插入**           | `addLast(e)`   | `offerLast(e)` | 在队尾加入元素 |
| **尾部删除**           | `removeLast()` | `pollLast()`   | 删除并返回队尾 |
| **获取尾部（不删除）** | `getLast()`    | `peekLast()`   | 查看队尾       |

**Queue** 是 Java 提供的单向队列，先进先出。从队尾进队头出。

```text
队头---队尾
```

**Deque** 是 Java 提供的双端队列。可以对队头和队尾同时操作。

```text
队头---队尾
```

Java 最早提供的 Stack 栈类型已被废弃，现代 Java 所有的栈操作可以通过封住 Deque 一端实现，达到先进后出的效果。

**Deque 中内置了带有 Stack 语义的 API，在实际使用中，我们也应该使用这些 API 在进行栈的操作**

```java 
void push(E e);     // 从双端队列的队头入栈
E pop();            // 从双端队列的队头出栈
E peek();           // 从队头查看栈顶，不删除
```

这几个操作总是作用于队列的头部

**Map&lt;K, V&gt;** 的核心方法

查找

| 方法                                  | 说明                                   |
| ------------------------------------- | -------------------------------------- |
| `V get(Object key)`                   | 根据 key 获取 value（不存在返回 null） |
| `boolean containsKey(Object key)`     | 判断是否存在该 key                     |
| `boolean containsValue(Object value)` | 判断是否存在该 value                   |

添加 & 修改

| 方法                    | 说明                        |
| ----------------------- | --------------------------- |
| `V put(K key, V value)` | 添加或覆盖 key 对应的 value |
| `void putAll(Map m)`    | 批量添加（相同 key 会覆盖） |

删除

| 方法                   | 说明                               |
| ---------------------- | ---------------------------------- |
| `V remove(Object key)` | 删除指定 key（返回被删除的 value） |
| `void clear()`         | 清空所有键值对                     |

遍历 Map 的核心方法

| 方法                             | 返回内容   | 作用         |
| -------------------------------- | ---------- | ------------ |
| `Set&lt;K&gt; keySet()`                | 所有 key   | 遍历 key     |
| `Collection&lt;V&gt; values()`         | 所有 value | 遍历 value   |
| `Set&lt;Map.Entry&lt;K,V&gt;&gt; entrySet()` | 所有键值对 | 遍历整个 Map |

其中 `Map.Entry&lt;K,V&gt;` 是 Map 遍历的核心结构

```java
for (Map.Entry<K, V> entry : map.entrySet()) {
    System.out.println(entry.getKey() + "=" + entry.getValue());
}
```

&gt; 在编写代码是，如果要使用 KV 型的类，可以选择 Java 提供的
&gt;
&gt; **AbstractMap.SimpleEntry&lt;K,V&gt;**
&gt;
&gt; ```java
&gt; AbstractMap.SimpleEntry&lt;String, Integer&gt; kv = new AbstractMap.SimpleEntry&lt;&gt;("age", 20);
&gt; ```
&gt;
&gt; 这是可变 KV，如果要使用不可变 KV，可以使用
&gt;
&gt; **AbstractMap.SimpleImmutableEntry&lt;K,V&gt;**
&gt;
&gt; ```java
&gt; AbstractMap.SimpleImmutableEntry&lt;String, Integer&gt; kv =
&gt;         new AbstractMap.SimpleImmutableEntry&lt;&gt;("age", 20);
&gt; 
&gt; ```

**在 Java 21 之前，有序集合并没有一个统一的顶层接口，只有上图中提供的 SortedSet/SortedMap 和 NavigableSet/NavigableMap** 接口，而后者是前者的增强类

**SortedSet/SortedMap** 提供的核心方法有

| 方法                                 | 作用                                      |
| ------------------------------------ | ----------------------------------------- |
| `Comparator&lt;? super E&gt; comparator()` | 返回排序使用的比较器（null 表示自然排序） |
| `SortedSet&lt;E&gt; subSet(E from, E to)`  | 返回指定范围的子集（[from, to)）          |
| `SortedSet&lt;E&gt; headSet(E to)`         | 返回所有小于 to 的元素                    |
| `SortedSet&lt;E&gt; tailSet(E from)`       | 返回所有大于等于 from 的元素              |
| `E first()`                          | 返回第一个（最小）元素                    |
| `E last()`                           | 返回最后一个（最大）元素                  |

| 方法                                  | 作用                         |
| ------------------------------------- | ---------------------------- |
| `Comparator&lt;? super K&gt; comparator()`  | key 的排序比较器             |
| `SortedMap&lt;K,V&gt; subMap(K from, K to)` | 返回 key 在区间内的子 Map    |
| `SortedMap&lt;K,V&gt; headMap(K to)`        | 返回所有 key &lt; to 的键值对   |
| `SortedMap&lt;K,V&gt; tailMap(K from)`      | 返回所有 key ≥ from 的键值对 |
| `K firstKey()`                        | 最小 key                     |
| `K lastKey()`                         | 最大 key                     |

这些方法都围绕 **排序 + 范围查询** 展开

而后者 **NavigableSet/NavigableMap** 提供了更强的导航能力

| 方法                              | 说明                  |
| --------------------------------- | --------------------- |
| `E lower(E e)`                    | 严格小于 e 的最大元素 |
| `E floor(E e)`                    | 小于等于 e 的最大元素 |
| `E ceiling(E e)`                  | 大于等于 e 的最小元素 |
| `E higher(E e)`                   | 严格大于 e 的最小元素 |
| `E pollFirst()`                   | 取出并删除最小值      |
| `E pollLast()`                    | 取出并删除最大值      |
| `NavigableSet&lt;E&gt; descendingSet()` | 降序视图              |

| 方法                                 | 说明                     |
| ------------------------------------ | ------------------------ |
| `Map.Entry&lt;K,V&gt; lowerEntry(K key)`   | key 前一个 Entry         |
| `Map.Entry&lt;K,V&gt; floorEntry(K key)`   | ≤ key 的最大 Entry       |
| `Map.Entry&lt;K,V&gt; ceilingEntry(K key)` | ≥ key 的最小 Entry       |
| `Map.Entry&lt;K,V&gt; higherEntry(K key)`  | &gt; key 的最小 Entry       |
| `K lowerKey(K key)`                  | lowerEntry 的 key 版本   |
| `K floorKey(K key)`                  | floorEntry 的 key 版本   |
| `K ceilingKey(K key)`                | ceilingEntry 的 key 版本 |
| `K higherKey(K key)`                 | higherEntry 的 key 版本  |
| `Map.Entry&lt;K,V&gt; pollFirstEntry()`    | 删除并取最小键值对       |
| `Map.Entry&lt;K,V&gt; pollLastEntry()`     | 删除并取最大键值对       |
| `NavigableMap&lt;K,V&gt; descendingMap()`  | 降序视图                 |

提供了 **向前、向后找的功能**

**而在 Java 21 后，补全了有序集的体系。提供了 SequencedCollection、SequencedSet 和 SequencedMap 接口**

&gt; 在 Java 21 之前存在很多有序集合，像 List、ArrayDeque等。它们不在之前的顺序接口体系中。Java 整体缺乏一个通用接口来表示共同的顺序操作。所有在 Java 21 引入了 **Sequenced** 系列接口，作为统一的、有序集合的顶层接口。

```textt
Collection
   └── SequencedCollection
          ├── List
          ├── Deque
          └── SequencedSet
```

```textt
Map
  └── SequencedMap
```

**SequencedCollection** 提供了以下核心方法

| 方法                                | 作用                             |
| ----------------------------------- | -------------------------------- |
| `E getFirst()`                      | 获取第一个元素                   |
| `E getLast()`                       | 获取最后一个元素                 |
| `void addFirst(E e)`                | 在头部添加                       |
| `void addLast(E e)`                 | 在尾部添加                       |
| `E removeFirst()`                   | 删除并返回第一个                 |
| `E removeLast()`                    | 删除并返回最后一个               |
| `SequencedCollection&lt;E&gt; reversed()` | 返回一个“反转视图”（不复制数据） |

统一了 List 和 Deque 的有序操作

**SequencedSet** 实现了 SequencedCollection 提供的所有有序操作

**SequencedMap** 提供的核心方法

| 方法                            | 作用                |
| ------------------------------- | ------------------- |
| `K firstKey()`                  | 第一个 key          |
| `K lastKey()`                   | 最后一个 key        |
| `Map.Entry&lt;K,V&gt; firstEntry()`   | 第一个 entry        |
| `Map.Entry&lt;K,V&gt; lastEntry()`    | 最后一个 entry      |
| `void putFirst(K key, V value)` | 把 entry 插入最前面 |
| `void putLast(K key, V value)`  | 把 entry 插入最后面 |
| `SequencedMap&lt;K,V&gt; reversed()`  | 反转视图            |

&gt; **Sequenced 系列接口的出现，是否会代替原本 SortedSet/SortedMap 和 NavigableSet/NavigableMap 接口**？
&gt;
&gt; **答案是否定的**
&gt;
&gt; **Sequenced 的出现补充的是顺序语义，它解决了顺序访问问题。而 SortedSet/SortedMap 和 NavigableSet/NavigableMap 排序语义和导航语义。**

**在使用集合的实现类时，引用类型应该选择能准确表达实际使用的操作语义接口，用最小必要语义的接口来约束使用，避免暴露不应该用的方法。**

例如使用 **Deque** 却用 **Queue** 接收，这样就限制了 **Deque** 双端操作的功能；如果使用 **BlockingQueue** 却用 **Queue** 接收，这样就不能调用阻塞方法。

## 实现类

### List

```textt
List
  ├── ArrayList
  ├── LinkedList
  └── CopyOnWriteArrayList
```

- `ArrayList` 是以数组为底层实现的可变数组。
- `LinkedList` 是以链表尾底层实现的。

二者的区别就来源于底层实现。包括插入删除性能、查询性能。

### Set

```textt
Set
 ├── HashSet
 ├── LinkedHashSet
 ├── SortedSet
 │    └── NavigableSet
 │          ├── TreeSet
 │          └── ConcurrentSkipListSet
 ├── SequencedSet
 │    ├── LinkedHashSet
 │    └── TreeSet
 └── CopyOnWriteArraySet
```

- `HashSet` 是不能包含重复元素的无序集合。它的底层使用 `HashMap` 实现的。
- `LinkedHashSet` 底层因为引入了链表，因此它是有序的 `Set`

### Queue

```textt
Queue
   ├── Deque
   │     ├── ArrayDeque
   │     ├── LinkedList
   │     ├── ConcurrentLinkedDeque
   │     └── BlockingDeque
   │           └── LinkedBlockingDeque
   │
   ├── PriorityQueue
   └── BlockingQueue
         ├── ArrayBlockingQueue
         ├── LinkedBlockingQueue
         ├── PriorityBlockingQueue
         ├── SynchronousQueue
         ├── LinkedTransferQueue
         └── DelayQueue
```

- `ArrayDeque` 底层是环形数组
- `LinkedList` 底层是双向链表

JDK 官方明确建议使用 `ArrayDeque` 代替 `Stack` 和 `LinkedList` 作为栈和队列使用

#### ArrayDeque

`ArrayDeque` 底层是数组，内存连续，通常比 `LinkedList` 快。

- 数组连续存储，遍历访问时 CPU cache 命中率高；而链表节点分散，指针跳转慢。
- `LinkedList` 每个元素都要包一层 `Node(prev, nex, item)`，对象多、GC 压力大；`ArrayDeque` 直接将元素放在数组槽位里。

`ArrayDeque` 内部核心是：

- `Object[] elements`：存放元素的数组

- `int head`：队头索引（指向队头元素位置）

- `int tail`：队尾索引（指向下一次插入尾部的位置）

为什么说他是环形的呢，因为数组末尾再往后走会绕回到 0（取模操作）

**入队/出队不移动元素，只移动 head/tail，并在数组里写入/清空槽位**。

下面使用伪代码简单表示一下从尾部入队时 `offerLast` / `addLast` 发生了什么。

```java
elements[tail] = x;
tail = (tail + 1) & (len - 1);
if (tail == head) grow(); // 满了（尾追上头）
```

`tail` 永远指向下一个可查位置。当 `tail == head` 时，代表数组满了，JDK 会自动扩容处理。

扩容步骤一般是：

1. 创建更大的数组，通常是原来的 2 倍
2. 把旧数组中的元素按逻辑顺序拷贝到新数组
3. 重置 `head = 0`、`tail = size`

`Deque` 给出的三套语义接口

当队列
```java
Deque<Integer> q = new ArrayDeque<>();
q.offer(1);  // 入队尾
q.offer(2);
q.poll();    // 出队头 -> 1
q.peek();    // 看队头
```

当栈

```java
Deque<Integer> st = new ArrayDeque<>();
st.push(1);  // 等价 addFirst
st.push(2);
st.pop();    // 等价 removeFirst -> 2
st.peek();   // 等价 peekFirst
```

当双端队列

```java
dq.offerFirst(1);
dq.offerLast(2);
dq.pollFirst(); // 1
dq.pollLast();  // 2
```

我们经常在层序遍历数、用两个队列实现栈、实现滑动窗口时使用它。

### Map

```textt
Map
 ├── HashMap
 ├── LinkedHashMap
 │
 ├── SequencedMap
 │      └── LinkedHashMap
 │
 ├── SortedMap
 │     └── NavigableMap
 │            └── TreeMap
 │
 └── ConcurrentMap
        ├── ConcurrentHashMap
        └── ConcurrentNavigableMap
               └── ConcurrentSkipListMap
```

- `HashMap` 是我们最常用的 KV 型数据结构了
- `ConcurrentHashMap` 是线程安全的 `HashMap`
