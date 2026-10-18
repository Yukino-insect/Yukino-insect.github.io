+++
date = '2025-11-26T21:00:05+08:00'
draft = false
title = '反转链表中长度为 k 的子链表'
+++

```java
class Solution {
    public ListNode reverseKGroup(ListNode head, int k) {
        // 用于返回
        ListNode hair = new ListNode();
        hair.next = head;
        // 用于遍历时的拼接位置
        ListNode pre = hair;
        while (head != null) {
            ListNode tail = pre;
            // 遍历需要反转的子链表
            for (int i = 0; i < k; i++) {
                tail = tail.next;
                // 如果该条件为真，说明剩下的元素不够 k 个，直接返回
                if (tail == null) {
                    return hair.next;
                }
            }
            // 记录尾部连接的位置
            ListNode next = tail.next;
            // 反转局部链表
            ListNode[] arr = reverseChildList(head, tail);
            // 记录反转后链表的首尾节点
            head = arr[0];
            tail = arr[1];
            // 拼接
            pre.next = head;
            tail.next = next;
            head = tail.next;
            pre = tail;
        }
        return hair.next;
    }

    private ListNode[] reverseChildList(ListNode head, ListNode tail) {
        ListNode pre = tail.next;
        // 不能直接使用 head，最后要返回该节点
        ListNode p = head;
        // 当最后一个节点遍历到第一个节点，终止遍历
        while (pre != tail) {
            ListNode next = p.next;
            p.next = pre;
            pre = p;
            p = next;
        }
        return new ListNode[] {tail, head};
    }
}
```
