+++
date = '2026-09-23T20:00:00+08:00'
draft = false
title = '从两数之和入门 C++ STL：vector、unordered_map 与常用用法'
math = true
+++
LeetCode 的“两数之和”很适合用来认识 C++ STL。题目要求在整数数组中找到两个不同下标，使对应元素之和等于目标值。下面这段代码能够正确完成任务：它使用 `std::vector` 保存输入和返回结果，用两层循环枚举所有可能的下标对。

```cpp
class Solution {
public:
    std::vector<int> twoSum(std::vector<int>& nums, int target) {
        for (int i = 0; i < nums.size(); i++) {
            for (int j = i + 1; j < nums.size(); j++) {
                if (nums[j] == target - nums[i]) {
                    return {i, j};
                }
            }
        }
        return {};
    }
};
```

这不是错误答案；在数组较短时，它甚至足够直接、容易验证。不过，它也暴露出几个值得学习的 STL 知识点：`vector` 是什么、`return {i, j}` 为什么成立、如何用 `unordered_map` 将重复查找变成一次查表，以及哪些场景不该为了“优雅”而盲目换容器。

本文只介绍日常编码最常用的 STL 容器和算法用法。STL 的迭代器分类、分配器、复杂度证明等更深内容可以以后再展开；一开始把所有抽象都背下来，并不会让代码突然变得更好。

## 一、先读懂原始解法

### 1. `std::vector<int>`：可变长的整数序列

`std::vector<T>` 是 STL 中最常用的顺序容器。它保存同一种类型的元素，并支持按下标快速访问：

```cpp
#include <vector>

std::vector<int> nums{2, 7, 11, 15};

int first = nums[0];     // 2
std::size_t count = nums.size();  // 4
```

在题目函数中：

```cpp
std::vector<int> twoSum(std::vector<int>& nums, int target)
```

- 返回类型 `std::vector<int>`：函数最终返回两个下标组成的动态数组。
- 参数 `std::vector<int>& nums`：`&` 表示引用，函数直接读取调用方的容器，而不复制整份数组。
- `nums.size()`：返回元素个数。
- `nums[i]`：按下标访问第 `i` 个元素，时间复杂度为 $O(1)$。

`vector` 的底层通常是一段连续存储空间。因此它擅长“按下标读取”和“在尾部追加”，但不擅长在中间插入或删除元素：后者往往需要移动后续元素。

| 操作 | 常见写法 | 典型复杂度 |
| ---- | -------- | ---------- |
| 按下标读取 | `nums[i]` | $O(1)$ |
| 尾部追加 | `nums.push_back(x)` | 均摊 $O(1)$ |
| 获得长度 | `nums.size()` | $O(1)$ |
| 中间插入或删除 | `nums.insert(...)`、`nums.erase(...)` | $O(n)$ |

`operator[]` 不会检查下标范围；下标无效时行为未定义。调试或边界不确定的代码可以使用会做范围检查的 `at`：

```cpp
int value = nums.at(0);
```

如果下标越界，`at` 会抛出 `std::out_of_range`。而在已能证明下标合法的算法主路径中，`[]` 更常见。

### 2. 两层循环枚举了哪些组合

外层的 `i` 从 `0` 开始，内层的 `j` 从 `i + 1` 开始：

```cpp
for (int i = 0; i < nums.size(); i++) {
    for (int j = i + 1; j < nums.size(); j++) {
        // 检查 nums[i] 与 nums[j]
    }
}
```

这样有两个好处：

- `j > i`，所以永远不会拿同一个元素和自己相加。
- 组合 `(i, j)` 只检查一次，不会再反过来检查 `(j, i)`。

对每一对下标，代码判断：

```cpp
nums[j] == target - nums[i]
```

这与 `nums[i] + nums[j] == target` 等价，只是把“另一个数应是多少”写得更明确。最坏情况下需要检查大约 $n(n - 1) / 2$ 对元素，所以时间复杂度是 $O(n^2)$；除输入数组外不额外分配容器，额外空间复杂度是 $O(1)$。

### 3. 为什么可以写 `return {i, j}`

这行使用了 C++ 的**列表初始化**：

```cpp
return {i, j};
```

函数的返回类型已经确定为 `std::vector<int>`，编译器会据此构造一个包含 `i`、`j` 的 `vector`。下面写法等价，只是更冗长：

```cpp
return std::vector<int>{i, j};
```

同理，找不到答案时：

```cpp
return {};
```

表示返回一个空的 `std::vector<int>`。这种写法简洁，但前提是上下文能唯一确定目标类型；如果读者一眼看不出返回类型，明确写出 `std::vector<int>{}` 也完全合理。

### 4. 循环下标的类型

`vector::size()` 的返回类型是 `std::size_t`，通常是无符号整数；原始代码的 `i`、`j` 则是 `int`。因此表达式 `i < nums.size()` 会发生有符号与无符号整数的比较，编译器常会给出警告。

本题返回下标的类型是 `int`，保留 `int` 下标会更贴合题目接口。可以在确认数组长度可表示为 `int` 的前提下，显式转换一次：

```cpp
const int n = static_cast<int>(nums.size());

for (int i = 0; i < n; ++i) {
    // ...
}
```

在通用库代码中，如果下标不需要 `int`，也可以统一使用 `std::size_t`。关键不在于迷信某一种类型，而在于不要无意中混用有符号和无符号值，更不要把一个可能很大的长度悄悄截断。

## 二、用 `unordered_map` 改写为线性查找

暴力解法的重复工作在于：对每个 `nums[i]`，它都再次扫描后面的元素寻找 `target - nums[i]`。如果能把“某个数字是否已经出现、出现在哪个下标”存入一个可快速查找的表，就不需要反复扫描。

`std::unordered_map<Key, Value>` 正好用于保存“键 → 值”的映射。本题中：

- 键 `Key`：数组中的数值。
- 值 `Value`：该数值已出现的位置。

```cpp
#include <unordered_map>
#include <vector>

class Solution {
public:
    std::vector<int> twoSum(const std::vector<int>& nums, int target) {
        std::unordered_map<int, int> index_by_value;
        index_by_value.reserve(nums.size());

        const int n = static_cast<int>(nums.size());
        for (int i = 0; i < n; ++i) {
            const int complement = target - nums[i];

            auto it = index_by_value.find(complement);
            if (it != index_by_value.end()) {
                return {it->second, i};
            }

            index_by_value.emplace(nums[i], i);
        }

        return {};
    }
};
```

这版函数不会修改 `nums`，所以把参数写成 `const std::vector<int>&` 更准确：它仍然避免复制数组，同时用 `const` 让编译器帮助我们阻止意外修改。

### 1. 查找与插入的顺序不能颠倒

每次遍历 `nums[i]` 时，代码先查找“补数” `target - nums[i]`，再把当前值写入哈希表：

```cpp
auto it = index_by_value.find(complement);
if (it != index_by_value.end()) {
    return {it->second, i};
}

index_by_value.emplace(nums[i], i);
```

这保证表中只存放**当前下标之前**的元素，因而答案中的两个下标一定不同。以 `nums = {3, 3}`、`target = 6` 为例：

```text
i = 0：查找 3，表为空；插入 3 -> 0
i = 1：查找 3，命中 3 -> 0；返回 {0, 1}
```

若先插入当前元素再查找，那么当 `target` 恰好等于 `2 * nums[i]` 时，很容易错误地用同一个下标凑出答案。

### 2. `find`、`end` 与 `emplace`

`unordered_map` 最常见的三个成员函数是：

| 目的 | 写法 | 结果 |
| ---- | ---- | ---- |
| 查找键 | `map.find(key)` | 找到时返回该元素的迭代器；找不到时返回 `map.end()` |
| 判断是否找到 | `it != map.end()` | `true` 表示 `it` 指向有效元素 |
| 原地插入键值 | `map.emplace(key, value)` | 键不存在时插入一项 |

`find` 的返回值是**迭代器**，可以把它理解为容器中某个元素的位置。对于 `unordered_map<int, int>`，元素类型近似于 `std::pair<const int, int>`：

```cpp
auto it = index_by_value.find(complement);
int found_index = it->second;
```

- `it->first` 是键，也就是数值。
- `it->second` 是值，也就是下标。

这里不要为了判断键是否存在而写 `index_by_value[complement]`。`operator[]` 在键不存在时会**自动插入**一个默认值，这会改变哈希表内容，也会把“未找到”和“找到的下标恰好为 0”混在一起。只查找时，`find` 更合适。

`emplace(nums[i], i)` 只在键不存在时插入。对于“两数之和”只需任意一组答案，保留数值第一次出现的下标已经足够；重复元素不会破坏前面 `{3, 3}` 的处理过程。

### 3. 为什么平均复杂度是 $O(n)$

哈希表将键分布到不同的桶中。`unordered_map` 的 `find` 和插入在平均情况下都是 $O(1)$，遍历数组 $n$ 次后，总时间通常是 $O(n)$，额外空间是 $O(n)$。

这里的“平均”不能省略：如果哈希冲突极端严重，单次查找可能退化，最坏情况可到 $O(n)$。对普通整数键和常规题目输入，这个方案通常就是正确且实用的选择。若需要按键排序、范围查询或更稳定的对数复杂度，再考虑 `std::map`。

`reserve(nums.size())` 是一个可选的小优化。它提前为预计数量的元素预留桶空间，减少扩容和重新散列的次数；它不改变算法的正确性。不要把这种微调误认为算法本身，先消除二重扫描才是关键。

## 三、`vector` 的日常操作

掌握 `vector` 的以下用法，已经能处理大多数“数组、结果列表、批量数据”的场景。

```cpp
#include <vector>

std::vector<int> values{3, 1, 4};

values.push_back(1);        // 尾部追加：{3, 1, 4, 1}
values.emplace_back(5);     // 尾部原地构造一个元素
values.pop_back();          // 删除最后一个元素

int first = values.front(); // 第一个元素
int last = values.back();   // 最后一个元素

values.reserve(100);        // 预留容量，不改变 size()
values.clear();             // 删除所有元素，size() 变为 0
```

### 1. `size` 与 `capacity` 不是一回事

- `size()`：容器中当前实际有多少元素。
- `capacity()`：目前已分配的存储空间最多可容纳多少元素而不重新分配。
- `reserve(n)`：确保容量至少为 `n`，但不会创建 `n` 个可访问元素。
- `resize(n)`：将实际元素数量变为 `n`；变大时会补默认构造的元素。

```cpp
std::vector<int> values;
values.reserve(10);

// values.size() == 0，不能访问 values[0]

values.resize(10);
// values.size() == 10，此时可访问 values[0] 到 values[9]
```

把 `reserve` 当作 `resize` 使用是常见错误：前者只安排座位，后者才真的让元素入座。

### 2. `push_back` 与 `emplace_back`

对于 `int`、`std::string` 这样的简单场景，两者的可读性差异通常比性能差异更重要：

```cpp
std::vector<std::string> names;

names.push_back("Yukino");
names.emplace_back("Yui");
```

`push_back` 接受一个已经存在的元素（或可转换成元素的值）；`emplace_back` 接受构造函数参数，直接在容器末尾构造元素。只有当构造对象本身有意义时，`emplace_back` 才更能表达意图：

```cpp
struct Point {
    Point(int x, int y) : x(x), y(y) {}
    int x;
    int y;
};

std::vector<Point> points;
points.emplace_back(10, 20);
```

不必把所有 `push_back` 机械替换成 `emplace_back`。代码首先应当说明“放入一个值”还是“用这些参数构造一个值”。

## 四、关联容器怎么选：`unordered_map`、`map`、`set`

STL 中的关联容器用于按“键”组织数据。选择时先问需求：需要快速精确查找，还是需要有序遍历和范围查询？

| 容器 | 保存内容 | 键是否有序 | 常见查找复杂度 | 常见用途 |
| ---- | -------- | ---------- | -------------- | -------- |
| `std::unordered_map<K, V>` | 键值映射 | 否 | 平均 $O(1)$ | 缓存、计数、索引表 |
| `std::map<K, V>` | 键值映射 | 是 | $O(\log n)$ | 按键排序、范围查询 |
| `std::unordered_set<T>` | 不重复的键 | 否 | 平均 $O(1)$ | 快速判断是否出现过 |
| `std::set<T>` | 不重复的键 | 是 | $O(\log n)$ | 去重且维持有序 |

下面是一个统计词频的 `unordered_map` 示例：

```cpp
#include <string>
#include <unordered_map>
#include <vector>

std::unordered_map<std::string, int> count_words(
    const std::vector<std::string>& words
) {
    std::unordered_map<std::string, int> counts;

    for (const std::string& word : words) {
        ++counts[word];
    }

    return counts;
}
```

这里允许使用 `counts[word]`，因为目标正是“若不存在则从 0 开始计数”。这和两数之和中“只查询、不应插入”的场景不同；同一个接口是否合适，取决于代码意图，而不是某条脱离上下文的禁令。

## 五、迭代器、范围 `for` 与常用算法

STL 将“存数据的容器”和“处理数据的算法”分开设计。`vector`、`map` 负责保存元素；`std::sort`、`std::find` 等算法通过**迭代器**描述要处理的区间。

### 1. 迭代器表示半开区间

每个标准容器通常提供：

- `begin()`：第一个元素的位置。
- `end()`：最后一个元素之后的位置，不可解引用。

因此 `[begin(), end())` 表示“从第一个元素开始，到末尾之前结束”的半开区间：

```cpp
std::vector<int> values{3, 1, 4};

for (auto it = values.begin(); it != values.end(); ++it) {
    // *it 依次是 3、1、4
}
```

遍历时更常用范围 `for`，更短也更不容易写错边界：

```cpp
for (const int value : values) {
    // 只读取 value
}

for (int& value : values) {
    value *= 2;  // 修改 vector 中的原元素
}
```

对于较大的对象，应写 `const auto& item`，避免每轮复制：

```cpp
for (const auto& name : names) {
    // 读取 name，不复制字符串
}
```

### 2. `std::sort`、`std::find` 与 `std::count`

常用算法位于 `<algorithm>`。它们不专属于 `vector`，只要容器提供相应能力，就能通过迭代器使用。

```cpp
#include <algorithm>
#include <vector>

std::vector<int> values{5, 2, 2, 9};

std::sort(values.begin(), values.end());
// values: {2, 2, 5, 9}

auto it = std::find(values.begin(), values.end(), 5);
if (it != values.end()) {
    // 找到了 5
}

int twos = static_cast<int>(
    std::count(values.begin(), values.end(), 2)
);
```

`std::sort` 会修改原容器，且要求迭代器支持随机访问，因此可以用于 `vector`，不能直接用于 `std::list`。`std::find` 依次扫描区间，时间复杂度为 $O(n)$；如果数据本来就需要按键快速定位，直接选 `unordered_map` 或 `unordered_set` 往往更合理，而不是把 `find` 套在错误的数据结构上。

自定义排序规则时传入比较函数：

```cpp
std::sort(values.begin(), values.end(), [](int left, int right) {
    return left > right;
});
// values: {9, 5, 2, 2}
```

比较函数应返回“`left` 是否应排在 `right` 前面”，不要误写成“是否小于等于”。使用 `<=` 会破坏排序算法所要求的严格弱序关系。

## 六、两数之和到底该选哪一版

两种实现都是正确的，区别在约束与取舍：

| 方案 | 时间复杂度 | 额外空间 | 优点 | 适合场景 |
| ---- | ---------- | -------- | ---- | -------- |
| 双重循环 | $O(n^2)$ | $O(1)$ | 不依赖额外容器，逻辑最直接 | 数据量很小、教学或空间受限 |
| `unordered_map` | 平均 $O(n)$ | $O(n)$ | 避免重复扫描，适合大输入 | 需要快速定位、允许额外空间 |

不要为了题目中出现了哈希表，就把原始双循环说成“不优雅”。如果输入最多只有十几个元素，双循环可能更直观，也完全够用。反过来，当数据规模大到二次扫描会成为瓶颈时，`unordered_map` 才是在用合适的数据结构表达“按值找下标”的需求。

还有一个容易误入的方向是“先排序，再用双指针”。它也可以把查找降到 $O(n \log n)$，但排序会破坏原下标；若题目要求返回原下标，还要额外保存“数值—原下标”对应关系。相比之下，哈希表解法直接保留原下标，通常更自然。

## 七、总结

从这道题中，应当掌握这些可迁移的结论：

- `std::vector` 适合顺序保存元素、按下标读取和尾部追加；`size`、`capacity`、`reserve`、`resize` 不能混为一谈。
- `std::vector<int>&` 避免复制；只读参数应优先写为 `const std::vector<int>&`。
- `return {i, j}` 和 `return {}` 是由返回类型推导出的列表初始化，分别构造两个元素和零个元素的 `vector`。
- `std::unordered_map` 适合“键到值”的快速索引；`find` 用于只查找，`operator[]` 适合确实需要在缺失时创建默认值的场景。
- `find` 返回迭代器，只有 `it != container.end()` 时才能访问 `it->first` 或 `it->second`。
- STL 算法通常处理 `[begin(), end())` 区间；范围 `for` 是日常遍历容器的首选写法。
- 两数之和的哈希表解法以 $O(n)$ 额外空间换取平均 $O(n)$ 时间；它更快，但不是每个小规模场景都必须使用的唯一写法。

STL 的价值不在于把代码堆满模板名，而在于让容器、算法和意图彼此匹配。能够先看出问题需要“顺序访问”“快速查找”还是“有序范围”，再选择 `vector`、`unordered_map` 或 `map`，就已经比背下一串成员函数可靠得多。
