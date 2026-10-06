+++
date = '2026-10-06T20:00:00+08:00'
draft = false
title = '无重复最长子串：C++ string、char 与 unordered_set 滑动窗口'
math = true
+++

LeetCode 的“无重复字符的最长子串”很适合把算法思路和 C++ 标准库一起练清楚。题目要找的是一个**连续子串**，并且子串中的字符不能重复；例如 `"abcabcbb"` 的答案是 `3`，对应 `"abc"`。

题目中的滑动窗口思路没有问题：右边界不断扩张，遇到重复字符时移动左边界并删除窗口左侧字符，直到窗口重新满足“没有重复字符”。

## 一、代码

```cpp
#include <algorithm>
#include <cstddef>
#include <string>
#include <unordered_set>

class Solution {
public:
    int lengthOfLongestSubstring(const std::string& s) {
        std::unordered_set<char> window;
        std::size_t left = 0;
        std::size_t best = 0;

        for (std::size_t right = 0; right < s.size(); ++right) {
            const char current = s[right];

            // 重复字符尚未移出窗口时，持续收缩左边界。
            while (window.contains(current)) {
                window.erase(s[left]);
                ++left;
            }

            window.insert(current);
            best = std::max(best, right - left + 1);
        }

        return static_cast<int>(best);
    }
};
```

`const std::string& s` 的含义是“只读地引用传入字符串”：不会复制整份字符串，也不会修改调用方的内容。题目通常保证返回值落在 `int` 范围内；本地工程中若输入可能极长，函数返回类型也应改为 `std::size_t`，而不该只在最后做转换来假装问题不存在。

若编译选项是 C++17 或更早版本，`unordered_set` 没有 `contains`。只需把条件改成下面的形式，算法不变：

```cpp
while (window.find(current) != window.end()) {
    window.erase(s[left]);
    ++left;
}
```

`find` 找到元素时返回该元素的迭代器；找不到时返回 `end()`。`end()` 是尾后位置，只用于比较，不能解引用。

## 二、滑动窗口为什么正确

把当前窗口看成下标范围 `[left, right]`，即左右端点都包含。循环每轮结束时应维持两个不变条件：

- `window` 恰好保存 `s[left]` 到 `s[right]` 中出现的字符；
- 该范围内没有重复字符。

当读取 `current = s[right]` 时，若 `window` 已经有它，说明把当前字符直接放入窗口会破坏第二个条件。于是不断删除 `s[left]` 并递增 `left`；旧的同字符终会被移出，窗口才能安全加入 `current`。此时 `[left, right]` 是一个合法窗口，所以用 `right - left + 1` 更新最长长度。

以 `"abba"` 为例：

```text
right = 0: "a"       合法，答案 1
right = 1: "ab"      合法，答案 2
right = 2: 加入 'b' 前重复
           删除 'a'，窗口 "b" 仍有重复
           删除旧 'b'，窗口为空
           加入新 'b'，窗口 "b"，答案仍为 2
right = 3: "ba"      合法，答案仍为 2
```

这里不能在发现重复时只让 `left` 加一，却不删除对应字符；那样集合与真实窗口就不一致，后续判断会失去依据。

虽然 `left` 写在 `for` 循环外、`right` 写在循环控制部分，它们都是函数的局部变量。二者分别只向右移动，且每个字符最多被插入一次、删除一次，因此总时间复杂度是平均 $O(n)$，空间复杂度是 $O(k)$，其中 $k$ 是窗口内不同 `char` 的数量。`unordered_set` 的单次查找、插入和擦除是**平均** $O(1)$；在哈希冲突被刻意构造等极端情况下，标准并不承诺始终是常数时间。

## 三、`std::string` 与 `char` 到底是什么关系

### 1. `char` 是一个字符代码单元，不等于“一个可见文字”

`char` 是 C++ 的基本整型字符类型，通常占 1 个字节。一个 `char` 变量保存一个**代码单元**，例如：

```cpp
char letter = 'A';
char newline = '\n';
```

单引号表示单个字符字面量；双引号表示字符串字面量。因此 `'A'` 的类型是 `char`，而 `"A"` 是包含字符和结尾空字符的字符串字面量，二者绝不能因为看起来只差一对引号就混为一谈。

`char` 是否默认带符号由实现决定。把原始字节拿来做数值计算、数组下标或分类时，若可能出现非 ASCII 数据，应明确转换成 `unsigned char`，不要依赖它恰好是正数。

### 2. `std::string` 是按顺序保存 `char` 的字符串类型

`std::string` 位于 `<string>` 中，本质上是 `char` 序列的标准库类型。它提供长度、下标访问、拼接和查找等操作：

```cpp
#include <string>

std::string name = "Yukino";
std::size_t count = name.size();  // 6
char first = name[0];             // 'Y'

name += " Yukinoshita";
```

对 `std::string` 而言，`size()` 与 `length()` 返回相同结果；日常代码通常统一使用 `size()`，因为这也和多数 STL 容器一致。返回值类型是 `std::string::size_type`，通常等价于 `std::size_t`，它是无符号类型。

`operator[]` 按下标访问字符代码单元，通常是常数时间，但**不会做范围检查**。边界不确定时可用 `s.at(index)`；越界会抛出 `std::out_of_range`。算法中 `right < s.size()` 已保证 `s[right]` 有效，而 `left` 只会在已有窗口元素时推进，因而 `s[left]` 也在有效范围内。

### 3. 这道题按字节处理 UTF-8 字符串

在常见环境中，`std::string` 保存的是 UTF-8 文本的字节序列。英文 ASCII 字符通常占一个字节，所以一个 `char` 看起来就是一个字符；但中文、emoji 等常常占多个字节：

```cpp
std::string text = "你好";
// text.size() 通常是 6，而不是 2（UTF-8 环境）
```

因此，本题的 `unordered_set<char>` 解法严格说计算的是“无重复**字节**的最长连续片段”，并非按用户看到的 Unicode 字符计数。若题目输入限定为英文字母或 ASCII，这完全正确；若必须按 Unicode 码点、甚至用户感知字符（grapheme cluster）处理，需要先正确解码 UTF-8，再用适合的 Unicode 库和数据类型。`std::string` 不会神奇地替你完成这一步。

## 四、`std::unordered_set`：本题真正使用的容器

`std::unordered_set<T>` 位于 `<unordered_set>`，保存一组不重复的键。它基于哈希表组织元素，不保证遍历顺序，也不支持下标访问。本题只关心“当前字符在不在窗口中”，它正合适。

```cpp
#include <unordered_set>

std::unordered_set<char> window;

window.insert('a');                 // 插入；已有相同键时不会重复保存
bool hasA = window.contains('a');   // C++20：是否存在
std::size_t removed = window.erase('a');  // 按键删除，返回删除数量（0 或 1）
```

对 `unordered_set`，最常见的操作和含义如下：

| 操作 | 含义 | 平均复杂度 |
| ---- | ---- | ---------- |
| `insert(value)` | 插入键，返回“迭代器 + 是否新插入”的结果 | $O(1)$ |
| `contains(key)` | 判断键是否存在，C++20 起可用 | $O(1)$ |
| `find(key)` | 查找键；找不到时返回 `end()` | $O(1)$ |
| `erase(key)` | 按键删除，返回删除的元素数量 | $O(1)$ |
| `size()` | 当前键数量 | $O(1)$ |
| `clear()` | 清空容器 | $O(n)$ |

不要把它与 `std::set` 混淆：`set` 通常基于平衡树，键会有序，常见操作为 $O(\log n)$；`unordered_set` 不排序，换来平均 $O(1)$ 的按键查询。若你需要按字典序遍历、查询最小/最大元素或范围查询，`set` 才是合理选择；若只做存在性判断，哈希集合往往更贴切。

## 五、与 `unordered_map`、数组方案的取舍

集合只记录“有没有出现”，所以发现重复时必须一个个移动 `left`。另一种常见写法用 `std::unordered_map<char, std::size_t>` 记录每个字符最近出现的位置，可以直接跳过重复区间：

```cpp
#include <algorithm>
#include <cstddef>
#include <string>
#include <unordered_map>

int lengthOfLongestSubstring(const std::string& s) {
    std::unordered_map<char, std::size_t> lastIndex;
    std::size_t left = 0;
    std::size_t best = 0;

    for (std::size_t right = 0; right < s.size(); ++right) {
        const char current = s[right];
        const auto found = lastIndex.find(current);

        if (found != lastIndex.end() && found->second >= left) {
            left = found->second + 1;
        }

        lastIndex[current] = right;
        best = std::max(best, right - left + 1);
    }

    return static_cast<int>(best);
}
```

这里最容易漏掉 `found->second >= left`。同一个字符可能在当前窗口左侧很早就出现过；那次记录不能再推动当前的 `left` 回退。代码更短不等于前提更少，反而需要更严谨地维护下标关系。

如果题目明确只处理单字节 `char`，键空间至多 256 个值，用定长数组通常更直接、性能也更稳定：

```cpp
#include <algorithm>
#include <array>
#include <cstddef>
#include <string>

int lengthOfLongestSubstring(const std::string& s) {
    std::array<int, 256> lastIndex;
    lastIndex.fill(-1);

    int left = 0;
    int best = 0;

    for (int right = 0; right < static_cast<int>(s.size()); ++right) {
        const auto byte = static_cast<unsigned char>(s[right]);
        left = std::max(left, lastIndex[byte] + 1);
        lastIndex[byte] = right;
        best = std::max(best, right - left + 1);
    }

    return best;
}
```

将 `s[right]` 转成 `unsigned char` 是必要的防御：若 `char` 为有符号类型，非 ASCII 字节可能是负数，直接作为数组下标会越界。数组方案依然是按 UTF-8 字节而非按 Unicode 字符处理，只是把哈希表换成了固定索引表。

## 六、与本题相关的 STL 小结

STL 常被宽泛地用来指 C++ 标准库中的容器、迭代器、算法和相关工具。本题不需要把所有成员函数背下来，但要先分清常用容器的职责。

| 类型 | 主要用途 | 是否有序 | 按键查找/访问特点 |
| ---- | -------- | -------- | ----------------- |
| `std::vector<T>` | 可变长顺序数组 | 保持插入顺序 | 按下标 $O(1)$，尾部追加均摊 $O(1)$ |
| `std::string` | `char` 的可变长序列 | 保持字符顺序 | 按下标访问通常 $O(1)$ |
| `std::array<T, N>` | 编译期固定长度数组 | 保持下标顺序 | 按下标 $O(1)$ |
| `std::set<Key>` | 不重复且有序的键 | 有序 | 查找、插入、删除通常 $O(\log n)$ |
| `std::unordered_set<Key>` | 不重复键的存在性判断 | 无序 | 查找、插入、删除平均 $O(1)$ |
| `std::map<Key, Value>` | 有序键值映射 | 按键有序 | 按键操作通常 $O(\log n)$ |
| `std::unordered_map<Key, Value>` | 哈希键值映射 | 无序 | 按键操作平均 $O(1)$ |
| `std::queue<T>` / `std::stack<T>` | FIFO / LIFO 的受限访问 | 不适用 | 只从规定端部取放元素 |

还有三条非常实用的规则：

- **先选语义，再看复杂度。** “是否出现过”选 `unordered_set`；“键对应的位置”选 `unordered_map`；“按下标连续访问”选 `vector` 或 `string`。不要为了看起来高级而把所有数据塞进同一种容器。
- **查找结果先判断。** `find` 的返回值可能等于 `end()`；无论容器是 `vector`、`set` 还是 `unordered_map`，都不能解引用 `end()`。
- **修改容器后留意迭代器失效。** `unordered_set` 和 `unordered_map` 发生 rehash 时迭代器会失效；`erase` 会使被删元素的迭代器失效。当前题解没有保存集合迭代器，所以不会踩到这个问题，但换题时不能遗忘。

## 七、总结

- 原代码的滑动窗口算法正确，但 C++ 中应使用 `std::unordered_set<char>`、`insert`、`erase`、`size()` 和 `std::max`；`remove`、`add` 不是 C++ 容器 API。
- `std::string` 是 `char` 代码单元的序列，`s[i]` 得到的是一个 `char`；单引号的字符和双引号的字符串是不同类型。
- `unordered_set` 适合维护当前窗口中的不重复元素，`contains` 需要 C++20；旧标准使用 `find(...) != end()`。
- 双指针都只会向右移动，每个字符最多进出窗口一次，所以该解法平均时间复杂度为 $O(n)$。
- 普通 `std::string` 加 `char` 的写法按字节工作。题目若包含中文或 emoji 并要求按可见字符计数，必须先处理 Unicode，而不是假装一个 `char` 总是一整个字符。

掌握这些边界后，“无重复最长子串”就不只是一个模板题：它也是一次容器语义、索引类型、字符编码和循环不变式的集中练习。比起记住一段能过题的代码，知道它为什么能过、又在什么条件下不再代表你以为的“字符”，才更值得留下来。
