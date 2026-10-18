+++
date = '2026-01-02T20:20:26+08:00'
draft = false
title = 'Java 集合'
+++

Java 集合的重点不是背实现类名字，而是理解每个接口表达的语义。接口选对了，代码暴露的能力就刚好够用；接口选大了，调用方就能做不该做的事。

集合体系可以先分成两大类：

1. `Collection`：单个元素的集合，例如 `List`、`Set`、`Queue`。
2. `Map`：键值对集合，例如 `HashMap`、`TreeMap`、`ConcurrentHashMap`。

## 一、Collection 体系

`Collection` 体系的核心结构如下：

```text
Iterable
  └── Collection
       ├── List
       ├── Set
       │    └── SortedSet
       │         └── NavigableSet
       └── Queue
            └── Deque
```

`Iterable<E>` 是可迭代接口，提供遍历能力：

```java
Iterator<E> iterator();
void forEach(Consumer<? super E> action);
Spliterator<E> spliterator();
```

`Collection<E>` 提供最基础的增删查能力：

```java
boolean add(E e);
boolean addAll(Collection<? extends E> c);

boolean remove(Object o);
boolean removeAll(Collection<?> c);
boolean retainAll(Collection<?> c);
void clear();

boolean contains(Object o);
boolean containsAll(Collection<?> c);
boolean isEmpty();
int size();

Object[] toArray();
<T> T[] toArray(T[] a);

Stream<E> stream();
Stream<E> parallelStream();
```

实际写代码时，引用类型应该尽量使用能表达需求的最小接口：

```java
List<String> names = new ArrayList<>();
Set<Long> userIds = new HashSet<>();
Queue<Task> tasks = new ArrayDeque<>();
```

这不是形式主义。接口越准确，后续维护者越容易看出这段代码真正需要什么能力。

## 二、List

`List` 表示有序、可重复、可按下标访问的集合。

常用方法：

```java
E get(int index);
E set(int index, E element);
void add(int index, E element);
E remove(int index);
int indexOf(Object o);
int lastIndexOf(Object o);
List<E> subList(int fromIndex, int toIndex);
```

常见实现类：

```text
List
  ├── ArrayList
  ├── LinkedList
  └── CopyOnWriteArrayList
```

`ArrayList` 底层是数组，适合随机访问和尾部追加。扩容时会创建更大的数组并复制旧元素。

`LinkedList` 底层是双向链表，理论上适合已定位节点后的插入删除，但随机访问很慢，并且每个元素都需要额外的节点对象。实际业务中，`ArrayList` 往往比 `LinkedList` 更常用。

`CopyOnWriteArrayList` 适合读多写少的并发场景。写入时复制数组，读操作无需加锁，但写成本很高。

## 三、Set

`Set` 表示不允许重复元素的集合。

核心方法其实就三个：

| API | 说明 |
| --- | --- |
| `add(e)` | 添加元素，已存在则添加失败 |
| `contains(e)` | 判断元素是否存在 |
| `remove(e)` | 删除元素 |

常见实现类：

```text
Set
  ├── HashSet
  ├── LinkedHashSet
  ├── TreeSet
  ├── ConcurrentSkipListSet
  └── CopyOnWriteArraySet
```

`HashSet` 基于 `HashMap` 实现，不保证遍历顺序，适合普通去重。

`LinkedHashSet` 在哈希表基础上维护插入顺序，适合既要去重又要保留顺序的场景。

`TreeSet` 基于红黑树，元素按自然顺序或比较器排序，适合范围查询。

`ConcurrentSkipListSet` 是线程安全的有序集合，底层是跳表。

`CopyOnWriteArraySet` 适合元素少、读多写少的并发场景。

## 四、Queue 和 Deque

`Queue` 表示队列，通常是先进先出。

它有三组核心 API，每组都有“抛异常版本”和“返回特殊值版本”：

| 操作 | 抛异常版本 | 返回特殊值版本 | 说明 |
| --- | --- | --- | --- |
| 入队 | `add(e)` | `offer(e)` | 添加元素 |
| 出队 | `remove()` | `poll()` | 删除并返回队头 |
| 查看队头 | `element()` | `peek()` | 查看但不删除 |

一般更推荐 `offer`、`poll`、`peek`，因为空队列或容量限制时不会直接抛异常。

`Deque` 是双端队列，可以同时操作队头和队尾：

| 操作 | 抛异常版本 | 返回特殊值版本 |
| --- | --- | --- |
| 头部插入 | `addFirst(e)` | `offerFirst(e)` |
| 头部删除 | `removeFirst()` | `pollFirst()` |
| 查看头部 | `getFirst()` | `peekFirst()` |
| 尾部插入 | `addLast(e)` | `offerLast(e)` |
| 尾部删除 | `removeLast()` | `pollLast()` |
| 查看尾部 | `getLast()` | `peekLast()` |

现代 Java 中，不建议继续使用旧的 `Stack` 类。栈语义可以用 `Deque` 表达：

```java
Deque<Integer> stack = new ArrayDeque<>();
stack.push(1); // 等价于 addFirst
stack.push(2);
stack.pop();   // 返回 2
stack.peek();  // 查看栈顶
```

队列语义也可以用 `Deque` 表达：

```java
Deque<Integer> queue = new ArrayDeque<>();
queue.offer(1); // 入队尾
queue.offer(2);
queue.poll();   // 出队头，返回 1
```

常见实现类：

```text
Queue
  ├── Deque
  │    ├── ArrayDeque
  │    ├── LinkedList
  │    └── ConcurrentLinkedDeque
  ├── PriorityQueue
  └── BlockingQueue
       ├── ArrayBlockingQueue
       ├── LinkedBlockingQueue
       ├── PriorityBlockingQueue
       ├── SynchronousQueue
       ├── LinkedTransferQueue
       └── DelayQueue
```

`ArrayDeque` 底层是循环数组，通常比 `LinkedList` 更适合作为栈和队列。它数组连续、对象更少，缓存局部性也更好。

`PriorityQueue` 是优先级队列，默认小顶堆，只保证队头是当前最小元素。

`BlockingQueue` 是阻塞队列，常用于生产者消费者模型。

## 五、Map 体系

`Map` 存储键值对，不属于 `Collection` 体系。

```text
Map
  ├── HashMap
  ├── LinkedHashMap
  ├── TreeMap
  ├── ConcurrentHashMap
  └── ConcurrentSkipListMap
```

核心方法：

```java
V get(Object key);
V put(K key, V value);
V remove(Object key);
boolean containsKey(Object key);
boolean containsValue(Object value);
int size();
boolean isEmpty();
void clear();
```

遍历 Map 时，最常用的是 `entrySet()`：

```java
for (Map.Entry<K, V> entry : map.entrySet()) {
    System.out.println(entry.getKey() + "=" + entry.getValue());
}
```

如果只需要 key，可以用 `keySet()`；只需要 value，可以用 `values()`。

常见实现类的语义：

| 实现类 | 特点 |
| --- | --- |
| `HashMap` | 最常用的哈希表，不保证顺序 |
| `LinkedHashMap` | 维护插入顺序或访问顺序 |
| `TreeMap` | 按 key 排序，支持范围查询 |
| `ConcurrentHashMap` | 高并发场景下的线程安全 Map |
| `ConcurrentSkipListMap` | 线程安全且按 key 排序 |

如果需要临时表达一个键值对，可以使用：

```java
Map.Entry<String, Integer> entry =
        new AbstractMap.SimpleEntry<>("age", 20);
```

如果希望键值对不可变，可以使用：

```java
Map.Entry<String, Integer> entry =
        new AbstractMap.SimpleImmutableEntry<>("age", 20);
```

## 六、排序和导航接口

`SortedSet`、`SortedMap` 表示按顺序排列的集合或映射。

`SortedSet` 常用方法：

| 方法 | 说明 |
| --- | --- |
| `comparator()` | 返回排序比较器，`null` 表示自然排序 |
| `subSet(from, to)` | 返回 `[from, to)` 范围内的子集 |
| `headSet(to)` | 返回小于 `to` 的元素 |
| `tailSet(from)` | 返回大于等于 `from` 的元素 |
| `first()` | 返回第一个元素 |
| `last()` | 返回最后一个元素 |

`NavigableSet` 在排序基础上提供“向前/向后找”的能力：

| 方法 | 说明 |
| --- | --- |
| `lower(e)` | 严格小于 `e` 的最大元素 |
| `floor(e)` | 小于等于 `e` 的最大元素 |
| `ceiling(e)` | 大于等于 `e` 的最小元素 |
| `higher(e)` | 严格大于 `e` 的最小元素 |
| `pollFirst()` | 删除并返回最小元素 |
| `pollLast()` | 删除并返回最大元素 |
| `descendingSet()` | 返回降序视图 |

`TreeSet` 和 `TreeMap` 是最典型的导航集合实现。

## 七、Java 21 的 Sequenced 接口

Java 21 引入了 Sequenced Collections，用来统一表达“有明确首尾顺序”的集合。

在 Java 21 之前，`List`、`Deque`、`LinkedHashSet`、`LinkedHashMap` 都有顺序，但缺少一个统一接口来表达“获取第一个元素、获取最后一个元素、反转视图”这些操作。

Java 21 补上了这组接口：

```text
Collection
  └── SequencedCollection
       ├── List
       ├── Deque
       └── SequencedSet
            └── SortedSet

Map
  └── SequencedMap
       └── SortedMap
```

`SequencedCollection` 的核心方法：

```java
E getFirst();
E getLast();
void addFirst(E e);
void addLast(E e);
E removeFirst();
E removeLast();
SequencedCollection<E> reversed();
```

`SequencedMap` 的核心方法：

```java
Map.Entry<K, V> firstEntry();
Map.Entry<K, V> lastEntry();
Map.Entry<K, V> pollFirstEntry();
Map.Entry<K, V> pollLastEntry();
K firstKey();
K lastKey();
V putFirst(K key, V value);
V putLast(K key, V value);
SequencedMap<K, V> reversed();
```

`Sequenced` 系列不会取代 `Sorted` 和 `Navigable` 系列。它们表达的语义不同：

| 接口 | 关注点 |
| --- | --- |
| `Sequenced` | 首尾顺序、反转视图 |
| `Sorted` | 排序规则、范围视图 |
| `Navigable` | 按顺序查找相邻元素 |

简单说，`Sequenced` 解决“谁在前、谁在后”；`Sorted` 解决“按什么排序”；`Navigable` 解决“比某个值大一点或小一点的是谁”。

## 八、实现类怎么选

常见选择可以按需求判断：

| 需求 | 推荐 |
| --- | --- |
| 普通可变列表 | `ArrayList` |
| 去重，不关心顺序 | `HashSet` |
| 去重，保留插入顺序 | `LinkedHashSet` |
| 排序集合、范围查询 | `TreeSet` |
| 栈或普通队列 | `ArrayDeque` |
| 每次取最小/最大元素 | `PriorityQueue` |
| 普通键值对 | `HashMap` |
| 保留插入顺序的 Map | `LinkedHashMap` |
| 按 key 排序的 Map | `TreeMap` |
| 并发 Map | `ConcurrentHashMap` |
| 生产者消费者队列 | `BlockingQueue` |

接口引用也要跟需求匹配：

```java
Queue<Task> queue = new ArrayDeque<>();
Deque<Integer> stack = new ArrayDeque<>();
Map<Long, User> users = new HashMap<>();
NavigableMap<Integer, String> ranges = new TreeMap<>();
```

如果你只需要队列操作，就用 `Queue`；如果需要双端操作，就用 `Deque`；如果需要范围查找，就用 `NavigableMap`。把类型写准确，代码会少很多解释成本。

## 九、总结

Java 集合可以按语义理解：

1. `List`：有序、可重复、可按下标访问。
2. `Set`：去重。
3. `Queue`：队列。
4. `Deque`：双端队列，也可当栈。
5. `Map`：键值对。
6. `Sorted`：排序。
7. `Navigable`：排序基础上的相邻查找。
8. `Sequenced`：Java 21 引入的首尾顺序接口。

集合选型不是背答案，而是先问一句：这段代码到底需要什么语义？能回答这个问题，剩下的实现类通常就自己浮出来了。虽然说得像理所当然，但很多 bug 正是从“随便用个差不多的集合”开始的。
