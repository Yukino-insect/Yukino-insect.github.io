+++
date = '2025-11-27T18:18:33+08:00'
draft = false
title = '快速排序 找到第 k 大的数字'
+++

在使用快速排序时，一般都是求升序序列。如果有求降序值的化可以通过等价的索引位置来求得正确答案。

下面这部分代码为什么要使用 `do {} while ()` 呢。是因为当出现

```java
int x = nums[l], i = l - 1, j = r + 1;
// 如果左指针小于右指针
while (i < j) {
    // 如果左值小于分界值 i++
    do {
        i++;
    } while (nums[i] < x);
    // 如果右值小于分界值 j--
    do {
        j--;
    } while (nums[j] > x);
    // 交换大小不符的元素位置
    if (i < j) {
        int temp = nums[i];
        nums[i] = nums[j];
        nums[j] = temp;
    }
}
```

```java
class Solution {

    private int quickselect(int[] nums, int l, int r, int k) {
        // 如果左右指针重合，结束递归
        if (l == r) {
            // 返回排序后数组的第 k 值
            return nums[k];
        }
        // x 为分界值 i 为左扫描指针 j 为右扫描指针
        int x = nums[l], i = l - 1, j = r + 1;
        // 如果左指针小于右指针
        while (i < j) {
            // 如果左值小于分界值 i++
            do {
                i++;
            } while (nums[i] < x);
            // 如果右值小于分界值 j--
            do {
                j--;
            } while (nums[j] > x);
            // 交换大小不符的元素位置
            if (i < j) {
                int temp = nums[i];
                nums[i] = nums[j];
                nums[j] = temp;
            }
        }
        // 结束该轮分治之后，判断第 k 个值落在哪个区间
        if (k <= j) {
            return quickselect(nums, l, j, k);
        } else {
            return quickselect(nums, j + 1, r, k);
        }
    }
    public int findKthLargest(int[] nums, int k) {
        int n = nums.length;
        return quickselect(nums, 0, n - 1, n - k);
    }
}
```
