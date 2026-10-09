+++
date = '2026-10-09T20:02:00+08:00'
draft = false
title = '分治算法：用归并过程统计逆序对，并推导 O(n log n)'
+++
**分治**把一个大问题拆成若干个同类型的小问题，递归求解后再合并结果。它不是“见到递归就分治”：子问题必须足够独立，合并步骤也必须比直接暴力求解更划算。

逆序对是很好的例子。对数组 `a`，若 `i < j` 且 `a[i] > a[j]`，二元组 `(i, j)` 是一个逆序对。暴力枚举所有下标对要 `O(n^2)`；借助归并排序，可在排序的同时完成统计。

## 一、跨越中点的逆序对如何一次数完

递归把区间分成左右两半后，左半和右半内部的逆序对已由子问题统计完成。剩下的只可能是“左元素在前、右元素在后”的**跨区间逆序对**。

归并时，左右两段已经分别有序。若 `left[i] <= right[j]`，取左元素不会产生新的跨区间逆序对；若 `left[i] > right[j]`，由于左段从 `i` 到末尾都不小于 `left[i]`，它们都大于 `right[j]`，于是一次增加 `mid - i + 1` 个逆序对。这个批量计数正是从二次复杂度降下来的关键。

## 二、完整 C++17 程序

输入格式：第一行 `n`，第二行 `n` 个整数。输出逆序对数量。计数最大可达 $n(n-1)/2$，所以使用 `long long`。

```cpp
#include <iostream>
#include <vector>
using namespace std;

long long mergeAndCount(vector<int>& a, vector<int>& temp, int left, int mid, int right) {
    int i = left, j = mid + 1, k = left;
    long long count = 0;

    while (i <= mid && j <= right) {
        if (a[i] <= a[j]) {
            temp[k++] = a[i++];
        } else {
            count += mid - i + 1;
            temp[k++] = a[j++];
        }
    }
    while (i <= mid) temp[k++] = a[i++];
    while (j <= right) temp[k++] = a[j++];
    for (int p = left; p <= right; ++p) a[p] = temp[p];
    return count;
}

long long countInversions(vector<int>& a, vector<int>& temp, int left, int right) {
    if (left >= right) return 0;
    int mid = left + (right - left) / 2;
    long long count = 0;
    count += countInversions(a, temp, left, mid);
    count += countInversions(a, temp, mid + 1, right);
    count += mergeAndCount(a, temp, left, mid, right);
    return count;
}

int main() {
    int n;
    cin >> n;
    vector<int> a(n), temp(n);
    for (int& x : a) cin >> x;
    cout << countInversions(a, temp, 0, n - 1) << '\n';
}
```

例如输入 `5` 与 `7 5 6 4 1`，输出为 `9`。空数组时调用区间为 `[0, -1]`，终止条件仍成立，因此不需要特别分支。

## 三、正确性：归纳地覆盖三类逆序对

对任一区间 `[left, right]`，逆序对只有三类：完全在左半、完全在右半、跨越中点。递归调用分别正确统计前两类；合并时，每次从右段取出更小的元素，恰好计入所有尚未合并且位于左段的较大元素，既不遗漏也不重复。因此三部分之和就是整个区间的逆序对数。

这类论证也是考研算法题可复用的写法：先将答案按结构互斥分类，再说明每一类由哪个步骤负责。

## 四、时间与空间复杂度怎样得出

递推式为：

$$
T(n)=2T(n/2)+O(n)
$$

递归树有 `log n` 层，而同一层的合并长度总和为 `n`，故时间复杂度为 `O(n log n)`。`temp` 只分配一次，长度为 `n`；递归栈深度为 `O(log n)`，总辅助空间由临时数组主导，为 `O(n)`。

若在每次 `merge` 内都新建临时数组，渐近空间仍可为 `O(n)`，但频繁分配会增加常数和实现风险。把工作区作为参数传入，职责更清楚。

## 五、与排序和考研的连接

归并排序稳定、时间复杂度稳定为 `O(n log n)`，但需要 `O(n)` 辅助空间。逆序对题说明“排序过程”不仅能输出有序数组，还能在合并边界上统计很多关系：小和、区间交叉数、二维偏序的简化版本都沿用这一观察。不要只背归并的代码；看清“两个有序区间相遇时，哪些信息可以批量结算”才是分治的收获。
