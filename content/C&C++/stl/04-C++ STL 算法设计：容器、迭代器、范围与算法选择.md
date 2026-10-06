+++
date = '2026-10-06T20:20:00+08:00'
draft = false
title = 'C++ STL 算法设计：容器、迭代器、范围与算法选择'
+++

下面这段“数组中的第 k 大元素”代码很短，却已经体现了 C++ 标准库最重要的一层设计：`vector` 保存数据，`sort` 处理数据，二者通过迭代器连接。

```cpp
class Solution {
public:
    int findKthLargest(std::vector<int>& nums, int k) {
        std::sort(nums.begin(), nums.end());
        return nums[nums.size() - k];
    }
};
```

更准确地说，**容器负责拥有元素和提供访问能力，算法负责在一段元素范围上完成通用操作。**这不是为了把一个简单调用拆得煞有介事，而是为了让排序、查找、复制、变换和聚合等能力不必绑死在某一种容器上。

本文从这道题出发，说明 C++ STL 中容器、迭代器、范围、算法与比较器分别做什么，并给出日常写题和工程代码中常用的算法选择原则。

## 一、先读懂第 k 大元素代码

`std::sort(nums.begin(), nums.end())` 按升序排列整个 `nums`。若数组长度为 `n`，第 `1` 大元素的下标是 `n - 1`，第 `k` 大元素的下标就是 `n - k`：

```text
排序前：3, 2, 1, 5, 6, 4
排序后：1, 2, 3, 4, 5, 6

k = 1 -> 下标 5 -> 6
k = 2 -> 下标 4 -> 5
k = 3 -> 下标 3 -> 4
```

算法思路没有问题，前提是 `1 <= k <= nums.size()`。在线题通常已经给出这个约束；若写成独立函数，还应处理非法输入，并明确排序会改变传入容器的顺序。

下面是一个可直接用 C++17 编译运行的完整示例。函数按值接收 `nums`，意在保留调用方原数组；若允许修改原数据，可以改回 `std::vector<int>&`，避免一次复制。

```cpp
#include <algorithm>
#include <cstddef>
#include <iostream>
#include <stdexcept>
#include <vector>

int kthLargestBySort(std::vector<int> nums, int k) {
    if (k <= 0 || static_cast<std::size_t>(k) > nums.size()) {
        throw std::out_of_range("k is out of range");
    }

    std::sort(nums.begin(), nums.end());
    return nums[nums.size() - static_cast<std::size_t>(k)];
}

int main() {
    const std::vector<int> values{3, 2, 1, 5, 6, 4};
    std::cout << kthLargestBySort(values, 2) << '\n';
}
```

这里有几个 C++ 细节不能略过：

- `std::sort` 定义在 `<algorithm>` 中，`std::vector` 定义在 `<vector>` 中。
- `size()` 返回无符号的 `std::size_t`，而 `k` 常写为有符号 `int`；先验证 `k > 0`，再转换为 `std::size_t`，可避免无符号减法把负数或越界值变成巨大的数。
- `std::sort` 是原地算法。若参数为引用，函数返回后 `nums` 已排序；这不是副作用被藏起来，而是调用者必须明确接受的操作语义。
- 完整排序的时间复杂度为 `O(n log n)`。它适合最终确实需要完整有序数组的场景，但只求第 `k` 大时并非唯一选择。

## 二、STL 的分工：容器、迭代器、范围与算法

把 STL 看作四层协作，比把它背成一长串 API 可靠得多：

```text
容器 / 数据源
    保存元素，决定存储结构
        ↓ 提供 begin()、end()
迭代器与范围 [first, last)
    描述一段可操作元素
        ↓ 传给算法
算法
    查找、排序、复制、变换、聚合、划分……
        ↓ 按需接收
比较器、谓词、投影、输出迭代器
    定义排序规则、筛选条件和结果去向
```

### 1. 容器负责数据与局部结构操作

容器决定元素如何存放，也提供那些必须依赖自身内部结构的操作：

```cpp
std::vector<int> values{4, 1, 7, 3};
values.push_back(9);
values.erase(values.begin());
```

| 容器 | 结构特征 | 常见优势 |
| ---- | -------- | -------- |
| `std::vector<T>` | 连续动态数组 | 下标访问、尾部追加、缓存友好 |
| `std::array<T, N>` | 固定长度连续数组 | 编译期固定容量、零额外分配 |
| `std::string` | `char` 的连续序列 | 字符串存储与按下标访问 |
| `std::list<T>` | 双向链表 | 已知位置插删、其他结点迭代器通常稳定 |
| `std::set<Key>` | 有序平衡树 | 有序去重、范围查询 |
| `std::unordered_set<Key>` | 哈希表 | 平均 `O(1)` 的存在性判断 |
| `std::map<Key, Value>` | 有序键值映射 | 按键有序访问 |
| `std::unordered_map<Key, Value>` | 哈希键值映射 | 平均 `O(1)` 的按键查找 |

容器不会，也不应该，把所有可能的算法都做成成员函数。若 `vector` 自己承担排序、二分、累加、排列、集合运算、堆操作和字符串匹配等全部职责，同一套逻辑会在不同容器中重复实现，类型也会很快失去边界。

### 2. 迭代器是泛化的指针

迭代器表示容器中的位置，行为类似指针，但不要求内部一定真是裸指针：

```cpp
std::vector<int> values{10, 20, 30};

auto it = values.begin();
std::cout << *it << '\n';
++it;
std::cout << *it << '\n';
```

算法不问“你是不是 `vector`”，而问“你的迭代器能做到什么”。例如 `std::find` 只需从前向后读取，所以可用于许多容器；`std::sort` 需要在任意位置间高效跳转，因此需要随机访问迭代器。

| 迭代器能力 | 可做的事 | 常见来源 |
| ---------- | -------- | -------- |
| 输入 | 读取、单向前进 | 输入流 |
| 前向 | 可重复单向遍历 | `forward_list`、无序关联容器 |
| 双向 | 前进与后退 | `list`、`set`、`map` |
| 随机访问 | 跳转、相减、位置比较 | `vector`、`deque`、`array` |
| 连续 | 元素还保证连续存放 | `vector`、`array`、`string` |

能力是递进的。连续迭代器具有随机访问能力，随机访问迭代器又具有双向、前向和输入迭代器能力。因此下面代码有效：

```cpp
std::vector<int> values{4, 1, 3, 2};
std::sort(values.begin(), values.end());
```

而下面代码不能使用同一个 `std::sort`：

```cpp
std::list<int> linked{4, 1, 3, 2};
// std::sort(linked.begin(), linked.end());  // 错误：list 不是随机访问迭代器
linked.sort();
```

这不是 `list` 少了功能，而是链表不能在常数时间跳到任意逻辑位置。对其强行套用依赖随机访问的算法，才是真正不讲道理的要求。

### 3. 范围通常是半开区间 `[first, last)`

绝大多数传统 STL 算法使用两个迭代器表示范围：

```cpp
std::sort(values.begin() + 1, values.begin() + 3);
```

这只排序下标 `1` 和 `2` 的元素；左边界包含，右边界不包含。半开区间有三个重要好处：

- 空区间自然写成 `[it, it)`；空容器满足 `begin() == end()`。
- 相邻区间可以无缝拼接：`[a, b)` 与 `[b, c)`。
- 对随机访问迭代器，长度可写为 `last - first`。

`end()` 是尾后位置，用于比较和表示边界，绝不能解引用。

## 三、`std::sort`：排序规则、能力要求与比较器契约

`std::sort` 的传统接口是：

```cpp
std::sort(first, last);
std::sort(first, last, comp);
```

它对 `[first, last)` 原地排序，要求随机访问迭代器。标准承诺其比较次数为 `O(N log N)`，但**不规定必须使用某一种具体排序算法**。因此，了解快速排序、堆排序和归并排序对分析很有价值，但不要把任一实现细节误认为所有 C++ 实现都必须如此。

默认排序使用从小到大的比较规则：

```cpp
std::sort(values.begin(), values.end());
```

降序可以写成：

```cpp
#include <functional>

std::sort(values.begin(), values.end(), std::greater<int>{});
```

或者使用 lambda：

```cpp
std::sort(values.begin(), values.end(), [](int left, int right) {
    return left > right;
});
```

对自定义类型，比较器表达的是业务上的排序规则：

```cpp
#include <algorithm>
#include <string>
#include <vector>

struct Student {
    std::string name;
    int score;
};

int main() {
    std::vector<Student> students{
        {"Yukino", 95},
        {"Yui", 88},
        {"Hachiman", 90}
    };

    std::sort(students.begin(), students.end(),
              [](const Student& left, const Student& right) {
                  return left.score > right.score;
              });
}
```

比较器必须构成**严格弱序**。最直观的规则是：

- `comp(x, x)` 必须为 `false`。
- 若 `comp(a, b)` 为真，就不能同时 `comp(b, a)` 也为真。
- 比较关系与“等价关系”应满足传递性。

因此下面写法错误：

```cpp
std::sort(values.begin(), values.end(), [](int left, int right) {
    return left >= right;  // 错误：left == right 时仍返回 true
});
```

它让元素“比自己小”，不满足排序算法的契约，结果不能依赖。`std::sort`、堆算法和有序查找使用的比较规则也应保持一致；先按一种规则排序、再按另一种规则二分查找，得到的结论自然没有保证。

## 四、只求第 k 大：为什么 `nth_element` 更贴切

若只需要第 `k` 大元素，完整排序做了许多并不必要的工作。`std::nth_element` 只保证目标位置正确，并把元素划分到目标两侧：

```cpp
#include <algorithm>
#include <cstddef>
#include <iostream>
#include <stdexcept>
#include <vector>

int kthLargestByNthElement(std::vector<int> nums, int k) {
    if (k <= 0 || static_cast<std::size_t>(k) > nums.size()) {
        throw std::out_of_range("k is out of range");
    }

    const std::size_t index = nums.size() - static_cast<std::size_t>(k);
    std::nth_element(nums.begin(), nums.begin() + index, nums.end());
    return nums[index];
}

int main() {
    const std::vector<int> values{3, 2, 1, 5, 6, 4};
    std::cout << kthLargestByNthElement(values, 2) << '\n';
}
```

调用后：

- `nums[index]` 等于完整排序后该下标上的元素。
- `index` 左侧元素都不大于它。
- `index` 右侧元素都不小于它。
- 左右两侧内部都**不保证有序**。

非并行版本的 `nth_element` 平均复杂度为 `O(n)`，很适合第 `k` 小/大的选择问题。它同样会重排元素；若需要保留输入顺序，应像示例一样传副本，或由调用方先复制。

根据最终需求选择算法：

| 需求 | 推荐算法 | 典型复杂度 | 是否完整排序 |
| ---- | -------- | ---------- | ------------ |
| 所有元素有序 | `std::sort` | `O(n log n)` | 是 |
| 第 `k` 小或第 `k` 大 | `std::nth_element` | 平均 `O(n)` | 否 |
| 最小/最大的 `k` 个元素且这 `k` 个有序 | `std::partial_sort` | 约 `O(n log k)` | 仅目标部分 |
| 动态维护 Top K | `std::priority_queue` | 单次更新常为 `O(log k)` | 否 |
| 相等元素仍保持原相对次序 | `std::stable_sort` | 通常 `O(n log n)` | 是，且稳定 |

算法选择的标准不是“哪一个名字更熟”，而是：**你究竟需要完整顺序、一个秩位置、前 k 个，还是持续维护的候选集合。**把不需要的部分也整理得井井有条，通常只是额外消耗，并不是什么值得赞美的勤奋。

## 五、常用算法按问题分类

| 问题类型 | 常用算法 | 作用 |
| -------- | -------- | ---- |
| 遍历执行 | `for_each` | 对每个元素执行操作 |
| 查找 | `find`、`find_if` | 查值或按条件查找 |
| 计数与判断 | `count`、`count_if`、`all_of`、`any_of`、`none_of` | 统计或判断条件 |
| 排序与选择 | `sort`、`stable_sort`、`nth_element`、`partial_sort` | 全排序、稳定排序、秩选择、Top K |
| 有序范围查询 | `lower_bound`、`upper_bound`、`equal_range`、`binary_search` | 二分查找及重复值边界 |
| 划分 | `partition`、`stable_partition` | 让满足条件的元素集中到一侧 |
| 复制与变换 | `copy`、`transform` | 复制数据或生成新数据 |
| 去重与逻辑删除 | `unique`、`remove`、`remove_if` | 重排有效元素，返回新逻辑尾部 |
| 数值操作 | `accumulate`、`iota`、`partial_sum` | 求和、填充递增序列、前缀和 |
| 堆 | `make_heap`、`push_heap`、`pop_heap` | 在普通区间上维护堆性质 |
| 排列 | `next_permutation` | 枚举下一个字典序排列 |

### 1. 查找：返回迭代器，而不是随意用特殊值

```cpp
#include <algorithm>
#include <vector>

std::vector<int> values{3, 5, 8, 13};

auto found = std::find_if(values.begin(), values.end(), [](int value) {
    return value % 2 == 0;
});

if (found != values.end()) {
    // *found == 8
}
```

找不到时，`find` 和 `find_if` 返回 `end()`。必须先比较再解引用；`end()` 不是一个可读取元素。算法返回迭代器，使它既能表示“找到了哪个位置”，也能自然表示“范围结束仍未找到”。

### 2. 变换：输入范围与输出位置分离

```cpp
#include <algorithm>
#include <iterator>
#include <vector>

std::vector<int> values{1, 2, 3};
std::vector<int> squares;

std::transform(values.begin(), values.end(),
               std::back_inserter(squares),
               [](int value) {
                   return value * value;
               });
// squares == {1, 4, 9}
```

`transform` 并不需要知道输出对象是 `vector`；`std::back_inserter` 将“在容器尾部追加”的行为包装为输出迭代器。算法只负责从输入读值、执行变换、写入输出位置，这种职责切分使其可以复用到更多容器和输出目标。

### 3. 二分：前提是范围已经按同一规则有序

```cpp
#include <algorithm>
#include <vector>

std::vector<int> values{1, 2, 2, 2, 5, 9};

auto firstTwo = std::lower_bound(values.begin(), values.end(), 2);
auto afterTwo = std::upper_bound(values.begin(), values.end(), 2);
// [firstTwo, afterTwo) 就是所有值为 2 的元素范围
```

`lower_bound` 返回第一个“不小于目标”的位置，`upper_bound` 返回第一个“大于目标”的位置。它们只在范围已按相同比较规则排序时成立。对 `std::list` 虽然也可能调用某些二分相关算法，但链表不能快速跳到中间位置，实际迭代移动代价会抵消二分的优势；数据结构与算法的能力匹配从来不是可选项。

## 六、`remove` 与 `erase`：一个整理范围，一个真正删容器元素

下面代码看似要删除所有 `2`：

```cpp
std::vector<int> values{1, 2, 3, 2, 4};
std::remove(values.begin(), values.end(), 2);
```

但调用后 `values.size()` 不会改变。`std::remove` 是通用算法，它不知道也不应该假设传入的是哪一种容器；它只将不应删除的元素向前移动，并返回新的逻辑尾部。真正改变 `vector` 长度的是容器成员函数 `erase`：

```cpp
#include <algorithm>
#include <vector>

std::vector<int> values{1, 2, 3, 2, 4};

values.erase(
    std::remove(values.begin(), values.end(), 2),
    values.end()
);
// values == {1, 3, 4}
```

这就是经典的 **erase-remove idiom**。从 C++20 起，对于常见容器还可以写：

```cpp
std::erase(values, 2);
```

这个例子恰好说明了 STL 的分层：`remove` 负责重排范围，`erase` 负责容器真实地析构并移除尾部元素。它们不是重复设计，而是分别完成不同层次的任务。

## 七、C++20 ranges：语法更直接，思想没有改变

传统 STL 风格需要显式写出迭代器对：

```cpp
std::sort(values.begin(), values.end());
```

C++20 ranges 支持直接传递整个范围：

```cpp
#include <algorithm>
#include <ranges>

std::ranges::sort(values);
```

对于对象成员排序，还可以传递投影：

```cpp
#include <algorithm>
#include <ranges>

std::ranges::sort(students, std::ranges::greater{}, &Student::score);
```

这表示“按 `Student::score` 降序排序”。ranges 让接口更容易阅读，也通过 concepts 更明确地表达算法所需能力；但其底层思想并没有变：算法仍在范围上工作，仍要求迭代器和元素满足相应条件，容器仍负责自身数据。

## 八、与 Java 的关系：并非绝对不同，而是抽象重心不同

不能简单说“Java 把算法和数据结构绑在一起，C++ 完全分开”。Java 同样有独立工具，例如 `Arrays.sort`、`Collections.sort`、`Collections.binarySearch`，也有 `List.sort` 和 Stream API；C++ 的容器也有成员操作，例如 `vector::erase`、`list::sort`。

真正的差别更接近下面这样：

| 角度 | C++ STL | Java 集合体系 |
| ---- | ------- | ------------ |
| 核心抽象 | 迭代器、范围、模板、concepts | 数组、集合接口、泛型、Stream |
| 算法复用方式 | 按迭代器能力在编译期组合 | 静态工具、接口默认方法、对象/流 API 并存 |
| 性能表达 | 容器布局、值语义、移动、迭代器类别更显性 | 接口统一性、对象模型与运行时环境更突出 |
| 特殊结构算法 | 结构不满足通用前提时使用成员算法，如 `list::sort` | 也会在具体类或工具类中提供实现 |

C++ 更强调“算法只声明它需要的能力”。`find` 只需单向读取，`sort` 需要随机访问，`list::sort` 利用链表自己的节点结构。让所有容器暴露完全相同的操作，看起来统一，实际上往往会掩盖复杂度和底层条件的差异。

## 九、写 STL 算法时的检查顺序

遇到一个问题时，可以按以下顺序决策：

1. **需要保留输入顺序吗？** 若需要，不要直接对原容器使用 `sort`、`nth_element`、`partition`；先复制，或选择不修改输入的算法。
2. **结果真正需要什么？** 全部有序选 `sort`；一个第 k 名选 `nth_element`；Top K 选 `partial_sort` 或堆；只判断存在性选 `find`、哈希容器或二分。
3. **输入是否满足前提？** 二分要求有序；Dijkstra 要求非负权；`sort` 的比较器需要严格弱序；算法范围必须有效。
4. **当前容器的迭代器能力够吗？** `sort` 需要随机访问；链表有自己的 `sort`；保存迭代器后再插删时还要检查失效规则。
5. **算法是否真正改变容器大小？** `remove`、`unique`、`partition` 主要重排范围；需要缩小 `vector` 时，通常还要调用 `erase`。
6. **复杂度是否与数据规模匹配？** 不要为了一个秩位置做全排序，也不要在只需单次扫描时引入不必要的树或堆。

## 十、总结

- `std::vector` 等容器负责保存和管理数据；`std::sort`、`std::find`、`std::transform` 等算法负责处理一段范围。
- 迭代器是容器与算法的共同语言，算法根据迭代器能力决定能否使用以及复杂度边界。
- `[first, last)` 是 STL 的基本范围表示；`end()` 只能用于比较，不能解引用。
- `std::sort` 适合完整排序，要求随机访问迭代器和严格弱序比较器；它会原地重排元素。
- 第 `k` 大/小元素应优先考虑 `std::nth_element`；Top K 可考虑 `std::partial_sort` 或 `std::priority_queue`。
- `std::remove` 不会直接缩小容器，配合 `erase` 才是实际删除。
- C++20 ranges 改善了表达方式，但“容器提供范围、算法按能力工作”的设计没有改变。

理解 STL 的关键，不是背下所有函数名，而是每次先问：**数据由谁拥有？我操作的是哪一段范围？算法需要什么能力？它会不会改变原数据？真正需要的结果到底有多完整？**这些问题想清楚后，算法库就不再是一堆互不相干的工具，而是一套边界明确、可以组合的系统。
