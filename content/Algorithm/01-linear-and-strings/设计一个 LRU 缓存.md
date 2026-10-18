+++
date = '2025-11-23T17:30:41+08:00'
draft = false
title = '设计一个 LRU 缓存'
+++

该缓存需要满足：

- 获取元素的时间复杂度为 O(1)
- 当缓存容量已满，插入新元素时需要淘汰最久未被访问的元素

根据上述两条要求就可以看出：

`HashMap` 数据结构可以满足 O(1) 时间复杂度的获取操作

而 `LinkedList` 链表又可以满足 O(1) 时间复杂度的插入删除操作

这样将 hash 映射到链表中的元素，并且维护链表的一个头指针和尾指针用来快速插入最近访问的和最久未被访问的元素。这样就实现了该数据结构

```java
class LRUCache {

    // 自定义一个节点，该节点包含指向前一个节点和后一个节点的指针
    class DLinkedNode {
        int key;
        int value;
        DLinkedNode prev;
        DLinkedNode next;
        
        public DLinkedNode() {}

        public DLinkedNode(int key, int value) {
            this.key = key;
            this.value = value;
        }
    }

    // 通过哈希表快速查找值
    private Map<Integer, DLinkedNode> cache = new HashMap<Integer, DLinkedNode>();

    // 缓存当前的元素值
    private int size;
    // 缓存的容量大小
    private int capacity;
    // 链表的头节点和尾节点，用来快速插入
    private DLinkedNode head, tail;

    public LRUCache(int capacity) {
        this.size = 0;
        this.capacity = capacity;
        head = new DLinkedNode();
        tail = new DLinkedNode();
        head.next = tail;
        tail.prev = head;
    }
    
    public int get(int key) {
        DLinkedNode node = cache.get(key);
        if (node == null) {
            return -1;
        }
        // 移到头节点，表示最新访问过的
        moveToHead(node);
        // 返回值
        return node.value;
    }
    
    public void put(int key, int value) {
        DLinkedNode node = cache.get(key);
        if (node == null) {
            DLinkedNode newNode = new DLinkedNode(key, value);
            cache.put(key, newNode);
            addToHead(newNode);
            // 更新缓存数量
            size++;
            if (size > capacity) {
                DLinkedNode tail = removeTail();
                cache.remove(tail.key);
                size--;
            }
        } else {
            node.value = value;
            moveToHead(node);
        }
    }

    private void addToHead(DLinkedNode node) {
        node.prev = head;
        node.next = head.next;
        head.next.prev = node;
        head.next = node;
    }

    private void removeNode(DLinkedNode node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }

    private void moveToHead(DLinkedNode node) {
        removeNode(node);
        addToHead(node);
    }

    private DLinkedNode removeTail() {
        DLinkedNode res = tail.prev;
        removeNode(res);
        return res;
    }
}
```
