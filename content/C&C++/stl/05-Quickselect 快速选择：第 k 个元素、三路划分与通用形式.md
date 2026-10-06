+++
date = '2026-10-06T20:30:00+08:00'
draft = false
title = 'Quickselect 快速选择：第 k 个元素、三路划分与通用形式'
+++

“数组中第 `k` 大元素”不一定要先把整个数组排好序。下面这种写法使用随机枢轴（pivot）把元素分为“大于、等于、小于”三组，只向真正包含目标的一组继续递归。它是 **Quickselect（快速选择）** 的一种三路划分变体。

```cpp
class Solution {
public:
    int findKthLargest(std::vector<int>& nums, int k) {
        return quickSelect(nums, k);
    }

private:
    int quickSelect(std::vector<int>& nums, int k) {
        int pivot = nums[rand() % nums.size()];
        std::vector<int> big, equal, small;
        for (int num : nums) {
            if (num > pivot) big.push_back(num);
            else if (num < pivot) small.push_back(num);
            else equal.push_back(num);
        }

        if (k <= big.size()) return quickSelect(big, k);
        if (nums.size() - small.size() < k) {
            return quickSelect(small, k - nums.size() + small.size());
        }
        return pivot;
    }
};
```

这段代码的核心逻辑正确：`big` 放比枢轴大的元素，`equal` 放等于枢轴的元素，`small` 放比枢轴小的元素；第 `k` 大元素只会落在其中一个区域。真正需要理解的并不是那三个 `if`，而是**秩（rank）如何在划分后换算**。一旦这个关系弄清楚，“第 k 小”“第 k 大”“按对象字段选择第 k 名”只是比较方向不同，而不是三种互不相干的题。

## 一、Quickselect 与快速排序有什么不同

快速排序也会选枢轴并分区，但它必须递归处理枢轴两边，最终让整个数组有序：

```text
快速排序：处理左区间 + 处理右区间
Quickselect：只处理包含目标秩的一个区间
```

因此，在随机枢轴或足够均衡划分的前提下：

| 算法 | 目标 | 平均时间复杂度 | 最坏时间复杂度 |
| ---- | ---- | -------------- | -------------- |
| 快速排序 | 所有元素有序 | `O(n log n)` | `O(n^2)` |
| Quickselect | 一个指定秩的元素 | `O(n)` | `O(n^2)` |
| 完整排序再取第 k 个 | 一个指定秩的元素 | `O(n log n)` | 取决于排序算法保证 |

Quickselect 并不会排序完整数组。它只反复做一件事：找到一个枢轴，把不可能成为答案的那一侧丢弃。若只需要一个第 `k` 大元素，再把其余元素排得井井有条，通常只是额外工作。

## 二、三路划分的通用形式

先不讨论“大”还是“小”。设有一个元素集合 `S`、一个枢轴 `p`，以及一个比较关系 `before(a, b)`，它表示“`a` 在目标顺序中应该排在 `b` 前面”。例如：

- 求第 `k` 小：`before(a, b)` 是 `a < b`。
- 求第 `k` 大：`before(a, b)` 是 `a > b`。
- 按学生分数从高到低选第 `k` 名：`before(a, b)` 是 `a.score > b.score`。

按 `p` 将元素分成三组：

```text
Before = { x | before(x, p) }
Equal  = { x | !before(x, p) && !before(p, x) }
After  = { x | before(p, x) }
```

令：

```text
b = |Before|
e = |Equal|
```

若 `rank` 从 `1` 开始编号，则通用选择规则是：

```text
rank <= b             -> 在 Before 中找第 rank 个
b < rank <= b + e     -> 答案属于 Equal，返回 pivot
rank > b + e          -> 在 After 中找第 rank - b - e 个
```

这就是三路 Quickselect 的一般形式。它只依赖“排在前面”的比较规则，因此不用为第 k 小和第 k 大各背一套看起来相似、下标却容易错一位的代码。

给出的代码中：

```text
Before = big
Equal  = equal
After  = small
```

所以第三个判断本质是：

```text
k > big.size() + equal.size()
```

原代码写成：

```cpp
nums.size() - small.size() < k
```

因为 `nums.size() - small.size()` 恰好等于 `big.size() + equal.size()`，二者等价。进入 `small` 后的新秩为：

```text
k - big.size() - equal.size()
```

原代码的：

```cpp
k - nums.size() + small.size()
```

同样是这一公式的等价变形。虽然它数学上没有错，但直接写成“减去前两个组的大小”更接近通用规则，也更容易在考场或代码审查中验证。

## 三、为什么必须保留 `equal` 分区

若只做两路划分，所有等于枢轴的元素常会被塞入同一边。对大量重复值，例如：

```text
[5, 5, 5, 5, 5, 5]
```

每轮都可能只排除一个枢轴，问题规模从 `n` 缓慢降到 `n - 1`、`n - 2`，性能退化明显。

三路划分把全部相等元素放到中间。若目标秩落在该段，立即返回；即使不立即返回，也不会把与枢轴相等的元素带进下一轮。这和荷兰国旗问题中的三路划分思想一致：

```text
[Before | Equal | After]
```

对重复键很多的数据，三路划分不是可有可无的装饰，而是避免无意义递归的关键。

## 四、可运行的通用 C++17 版本

下面实现将“顺序方向”作为比较器参数。`compare(a, b)` 返回 `true` 表示 `a` 应排在 `b` 前；传 `std::less<int>{}` 得到第 k 小，传 `std::greater<int>{}` 得到第 k 大。

它采用迭代而非递归，并按值接收容器以保留调用方数据。为了可重复测试，随机引擎由调用方传入；这比在算法中反复调用全局 `rand()` 更容易控制和验证。

```cpp
#include <cstddef>
#include <functional>
#include <iostream>
#include <random>
#include <stdexcept>
#include <utility>
#include <vector>

template <typename T, typename Compare, typename URBG>
T randomizedSelect(std::vector<T> values, std::size_t rank,
                   Compare compare, URBG& engine) {
    if (rank == 0 || rank > values.size()) {
        throw std::out_of_range("rank is out of range");
    }

    while (true) {
        std::uniform_int_distribution<std::size_t> pick(0, values.size() - 1);
        const T pivot = values[pick(engine)];

        std::vector<T> before;
        std::vector<T> equal;
        std::vector<T> after;
        before.reserve(values.size());
        equal.reserve(values.size());
        after.reserve(values.size());

        for (const T& value : values) {
            if (compare(value, pivot)) {
                before.push_back(value);
            } else if (compare(pivot, value)) {
                after.push_back(value);
            } else {
                equal.push_back(value);
            }
        }

        if (rank <= before.size()) {
            values = std::move(before);
        } else if (rank <= before.size() + equal.size()) {
            return pivot;
        } else {
            rank -= before.size() + equal.size();
            values = std::move(after);
        }
    }
}

int main() {
    const std::vector<int> values{3, 2, 1, 5, 6, 4, 5, 5};
    std::mt19937 engine(20261006);  // 固定种子，便于复现示例

    const int thirdLargest = randomizedSelect(
        values, 3, std::greater<int>{}, engine);
    const int fourthSmallest = randomizedSelect(
        values, 4, std::less<int>{}, engine);

    std::cout << "third largest: " << thirdLargest << '\n';
    std::cout << "fourth smallest: " << fourthSmallest << '\n';
}
```

运行结果为：

```text
third largest: 5
fourth smallest: 4
```

这里按值传入的 `values` 只是一种教学上清楚的接口设计。若元素很大、复制昂贵且允许修改原数组，应改为引用传参并采用原地分区；下一节会给出这种版本。

## 五、原地三路 Quickselect：减少额外分配

分组版代码每轮都创建 `before`、`equal`、`after` 三个 `vector`，阅读直观，却会复制元素和分配内存。原地版本在同一数组内维护三个区域：

```text
[left, greater)   : 比 pivot 大
[greater, scan)   : 等于 pivot
[scan, less]      : 尚未检查
(less, right]     : 比 pivot 小
```

下列实现求第 `k` 大元素。它使用 `int` 下标以便清楚表达 `right = greater - 1`；接口先检查数组规模能否安全转换为 `int`。在通常的在线题约束中这个限制并不构成问题，但独立代码不应悄悄假设它永远成立。

```cpp
#include <cstddef>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <utility>
#include <vector>

int kthLargestInPlace(std::vector<int>& values, int k, std::mt19937& engine) {
    if (k <= 0 || static_cast<std::size_t>(k) > values.size()) {
        throw std::out_of_range("k is out of range");
    }
    if (values.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        throw std::length_error("input is too large for int indices");
    }

    const int target = k - 1;  // 在降序排列中的 0-based 下标
    int left = 0;
    int right = static_cast<int>(values.size()) - 1;

    while (left <= right) {
        std::uniform_int_distribution<int> pick(left, right);
        const int pivot = values[pick(engine)];

        int greater = left;
        int scan = left;
        int less = right;

        while (scan <= less) {
            if (values[scan] > pivot) {
                std::swap(values[greater++], values[scan++]);
            } else if (values[scan] < pivot) {
                std::swap(values[scan], values[less--]);
            } else {
                ++scan;
            }
        }

        // [left, greater) 大于 pivot；[greater, scan) 等于 pivot。
        if (target < greater) {
            right = greater - 1;
        } else if (target >= scan) {
            left = scan;
        } else {
            return pivot;
        }
    }

    throw std::logic_error("unreachable: valid rank must be selected");
}

int main() {
    std::vector<int> values{3, 2, 1, 5, 6, 4, 5, 5};
    std::mt19937 engine(20261006);

    std::cout << kthLargestInPlace(values, 3, engine) << '\n';  // 5
}
```

每轮分区都用线性时间扫描当前区间。随机枢轴使下一轮的期望规模大幅缩小，因此总期望时间为 `O(n)`；迭代原地版本除随机引擎外只使用常数额外空间。请注意“期望”二字：若每一次枢轴都极端不平衡，仍可能退化到 `O(n^2)`。

## 六、如何看待给出的递归分组实现

给出的实现没有悬垂引用问题。`big`、`equal`、`small` 是当前函数栈帧中的局部变量，调用 `quickSelect(big, k)` 时，`big` 在递归调用返回前仍然存活；引用本身是安全的。

但它有几个应当明确的边界：

| 方面 | 当前写法 | 更稳妥的处理 |
| ---- | -------- | ------------ |
| 输入合法性 | 默认 `nums` 非空且 `k` 有效 | 入口检查 `1 <= k <= nums.size()` |
| 随机数 | `rand() % nums.size()` | 使用 `<random>` 的 `std::mt19937` 与均匀分布 |
| 取模偏差 | `rand() % n` 可能非均匀 | `std::uniform_int_distribution` |
| 内存 | 每轮建立三个新数组 | 大数据用原地三路分区 |
| 秩换算 | 用 `nums.size() - small.size()` 间接表达 | 直接写 `big.size() + equal.size()` |
| 递归深度 | 极端枢轴时可能很深 | 用循环缩小当前区间 |

`rand()` 并不会使算法逻辑错误，随机枢轴的正确性也不依赖“真正不可预测”。但 `rand` 是全局状态，质量和可复现性较差，`rand() % n` 还会在 `RAND_MAX + 1` 不能整除 `n` 时产生取模偏差。现代 C++ 中，用局部随机引擎加 `std::uniform_int_distribution` 表达“在当前下标区间均匀取一个枢轴”更符合意图。

分组递归版本的空间也不能只写成一句 `O(n)` 就结束。若随机划分足够均衡，沿递归路径保存的各轮分组规模形成几何级数，期望额外空间为 `O(n)`；若连续选到极端枢轴，上一层局部数组在下一层返回前不会释放，最坏情况下累计空间可能达到 `O(n^2)`。原地迭代版正是为避免这种额外复制和递归栈而存在。

## 七、随机化、最坏情况与确定性线性选择

随机 Quickselect 的“随机”只用于降低持续选到坏枢轴的概率。给定有效的 `k`，无论枢轴如何选，三路划分的秩判断都仍然正确；变化的是运行时间，而不是答案。

若题目要求最坏情况下也必须线性时间，可以使用 **Median of Medians（中位数的中位数）** 选择枢轴。其一般过程是：

1. 将元素分成每组至多 5 个的小组。
2. 分别找出每组中位数。
3. 递归寻找这些中位数的中位数，作为枢轴。
4. 以该枢轴三路划分，再仅递归目标所在分区。

这个枢轴保证能丢弃足够多元素，递推关系可写为：

```text
T(n) <= T(n / 5) + T(7n / 10 + O(1)) + O(n)
```

因此最坏复杂度为 `O(n)`。不过常数较大，普通工程和绝大多数在线题中，随机 Quickselect 或标准库 `std::nth_element` 通常更实用。算法题不能因为理论最优就无视常数与实现复杂度；这和为了一个第 k 大元素强行把全数组排序一样，都是把手段误当成目的。

## 八、标准库替代：`std::nth_element`

若不要求手写 Quickselect，C++ 标准库提供了更直接的选择算法：

```cpp
#include <algorithm>
#include <cstddef>
#include <functional>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> values{3, 2, 1, 5, 6, 4};
    const std::size_t index = 2 - 1;  // 降序下，第 2 大的 0-based 下标

    std::nth_element(values.begin(), values.begin() + index, values.end(),
                     std::greater<int>{});
    std::cout << values[index] << '\n';  // 5
}
```

`nth_element` 的语义正好对应选择问题：目标位置上的元素等于完整排序后该位置的元素，目标前后的区域只满足分区关系，不保证各自有序。非并行版本平均为线性复杂度。关于它与 `sort`、`partial_sort`、堆之间的详细取舍，可参见[STL 算法设计：容器、迭代器、范围与算法选择](04-C++ STL 算法设计：容器、迭代器、范围与算法选择.md)。

## 九、总结

- Quickselect 使用分区消除不可能包含目标秩的一侧，只递归或迭代处理一个分区，因此平均可在 `O(n)` 时间找到第 `k` 个元素。
- 三路划分的一般规则是：目标在 `Before` 则秩不变；目标在 `Equal` 则直接返回；目标在 `After` 则减去 `Before` 与 `Equal` 的大小。
- 第 k 小和第 k 大的差别只在比较器方向：`std::less` 表示从小到大，`std::greater` 表示从大到小。
- `equal` 分区能正确处理重复值，并避免大量相等键导致问题规模几乎不缩小。
- 分组版直观但会复制元素；原地三路版更节省内存，并可用循环避免深递归。
- 随机化改善的是期望性能，不改变正确性；若追求最坏线性时间，可使用 median of medians。
- 在生产代码中，若没有练习算法本身的要求，优先考虑 `std::nth_element`。标准库已经把“找指定秩”这个意图表达得足够清楚，没有必要把每个选择问题都重新手搓一遍。
