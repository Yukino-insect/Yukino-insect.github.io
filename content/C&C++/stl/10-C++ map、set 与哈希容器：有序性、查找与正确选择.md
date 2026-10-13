+++
date = '2026-10-13T09:40:00+08:00'
draft = false
title = 'C++ map、set 与哈希容器：有序性、查找与正确选择'
+++
`map`、`set`、`unordered_map` 和 `unordered_set` 都能“按键查东西”或“判断元素是否存在”，却不应该被视为同一种容器的四个拼写。最关键的区别是：你需要的是平均常数时间的精确查找，还是按键有序的遍历、边界和范围查询？

```cpp
#include <map>
#include <unordered_map>

std::map<std::string, int> scores;              // 键始终有序
std::unordered_map<std::string, int> counters;  // 平均更快，但无顺序
```

如果只是统计单词次数，`unordered_map` 往往合理；如果需要“所有键不小于 `from` 且小于 `to` 的记录”，`map` 的顺序和 `lower_bound` 才是题目的直接表达。先确定查询语义，再讨论复杂度，顺序不能倒过来。

## 一、四种容器的角色

| 容器 | 保存内容 | 键是否唯一 | 键是否有序 | 常见查找复杂度 |
| ---- | -------- | ---------- | ---------- | -------------- |
| `std::map<K, V>` | 键值对 | 是 | 是 | `O(log n)` |
| `std::set<T>` | 键 | 是 | 是 | `O(log n)` |
| `std::unordered_map<K, V>` | 键值对 | 是 | 否 | 平均 `O(1)` |
| `std::unordered_set<T>` | 键 | 是 | 否 | 平均 `O(1)` |

有序关联容器通常以平衡二叉搜索树实现，因此操作的最坏复杂度为 `O(log n)`，并能提供范围查询。无序关联容器通常以哈希表实现，平均查找和插入为 `O(1)`，但最坏情况可能退化，而且迭代顺序不稳定，不能当作排序结果使用。

若要保留重复键，还有 `multimap`、`multiset`、`unordered_multimap`、`unordered_multiset`。不过应先确认重复值是否真的需要以多条元素存在；许多“统计次数”的问题应存成 `map<Key, int>`，而不是把同一个键插入多次。

## 二、`map`：有序键值映射与范围查询

`std::map` 中每一项的类型近似为 `std::pair<const Key, T>`。键不可通过迭代器修改，因为改键会破坏树的有序性；值可以修改。

```cpp
#include <map>
#include <string>

std::map<std::string, int> score_by_name{
    {"Alice", 90},
    {"Carol", 88},
    {"Bob", 95},
};

for (const auto& [name, score] : score_by_name) {
    // 按 Alice、Bob、Carol 的字典序遍历
}
```

### 1. `find` 与 `operator[]` 的根本区别

只想查询键是否存在时，用 `find`：

```cpp
auto it = score_by_name.find("Alice");
if (it != score_by_name.end()) {
    int score = it->second;
}
```

不要把下面写法当作纯查询：

```cpp
int score = score_by_name["Alice"];
```

当键不存在时，`operator[]` 会插入一个值初始化的 `int`，即 `0`。这对计数很方便：

```cpp
++score_by_name["Alice"];
```

但对“查不到就不改容器”的逻辑是副作用。若键不存在属于异常，也可使用：

```cpp
int score = score_by_name.at("Alice");
```

`at` 不插入元素，找不到时抛出 `std::out_of_range`。选择 `find`、`at` 还是 `[]`，取决于缺失键应当如何处理：静默判断、显式报错，还是创建默认值。

### 2. `lower_bound` 与半开区间

有序性使 `map` 可以高效查找边界。`lower_bound(key)` 返回第一个“不小于 `key`”的迭代器，`upper_bound(key)` 返回第一个“大于 `key`”的迭代器。

```cpp
std::map<int, std::string> events{
    {10, "login"},
    {20, "upload"},
    {30, "logout"},
    {40, "archive"},
};

const auto first = events.lower_bound(20);  // 键为 20
const auto last = events.lower_bound(40);   // 键为 40，不包含它

for (auto it = first; it != last; ++it) {
    // 处理键在 [20, 40) 的 20 与 30
}
```

这就是 STL 常见的半开区间 `[first, last)`：起点包含，终点不包含。哈希容器没有全局键顺序，因而不能提供这种按键范围的查询。

## 三、`set`：只关心是否存在且希望有序

`std::set<T>` 相当于只有键、没有关联值的有序集合：

```cpp
#include <set>

std::set<int> ids;
ids.insert(42);
ids.insert(7);
ids.insert(42);  // 重复插入不会产生第二个 42
```

插入结果可用于判断本次是否为首次出现：

```cpp
const auto [it, inserted] = ids.insert(42);
if (!inserted) {
    // 42 原本就在集合中
}
```

对于 C++17，`insert` 的返回值是一个包含迭代器与布尔值的 `pair`，结构化绑定让意图更清楚。迭代器 `it` 指向集合中的元素；集合元素同样不允许通过迭代器修改，因为值本身就是排序键。

## 四、哈希容器：快的是平均精确查找，不是所有操作

`unordered_map`、`unordered_set` 依赖哈希函数把键分配到桶中。对于支持 `std::hash` 的常见类型，可直接使用：

```cpp
#include <string>
#include <unordered_map>

std::unordered_map<std::string, int> word_count;

for (const std::string& word : words) {
    ++word_count[word];
}
```

这个场景中 `operator[]` 正确而自然：缺失单词应从默认值 `0` 开始计数。若只是判断元素是否出现过：

```cpp
#include <unordered_set>

std::unordered_set<int> seen;
if (seen.insert(value).second) {
    // value 第一次出现
}
```

### 1. `reserve` 与 `rehash`

若预先知道大概会插入多少元素，可以：

```cpp
std::unordered_set<int> seen;
seen.reserve(expected_count);
```

这会预留足以容纳预计元素数量的桶，从而减少扩容和重新散列。它不改变集合中实际元素数，也不保证精确分配多少桶；真正的桶数还会受最大装载因子影响。

哈希表发生 rehash 后，迭代器通常失效。因此不要在循环中一边保存哈希容器迭代器、一边进行可能触发 rehash 的大量插入。若确实需要，先 `reserve`，或改用不会依赖旧迭代器的写法。

### 2. 自定义键必须满足相等与哈希一致

自定义结构作为 `unordered_set` 的键，需要提供相等判断和哈希函数，并保证：若两个键相等，它们的哈希值也必须相同。

```cpp
#include <cstddef>
#include <functional>
#include <string>
#include <unordered_set>

struct UserKey {
    int tenant_id;
    std::string user_id;

    bool operator==(const UserKey& other) const {
        return tenant_id == other.tenant_id && user_id == other.user_id;
    }
};

struct UserKeyHash {
    std::size_t operator()(const UserKey& key) const {
        const std::size_t first = std::hash<int>{}(key.tenant_id);
        const std::size_t second = std::hash<std::string>{}(key.user_id);
        return first ^ (second << 1);
    }
};

std::unordered_set<UserKey, UserKeyHash> users;
```

上例的哈希组合方式适合说明接口，并不保证面对所有分布都最优。重要的是语义一致：不能让 `operator==` 认为两个键相等，却给出不相等时才相同的任意规则；哈希值碰撞是允许的，相等对象哈希不一致则会破坏容器正确性。

## 五、`map` 与 `unordered_map` 如何选择

| 需求 | 推荐 | 理由 |
| ---- | ---- | ---- |
| 高频精确查找、计数、去重 | `unordered_map` / `unordered_set` | 平均 `O(1)` |
| 按键有序遍历 | `map` / `set` | 迭代顺序就是键顺序 |
| 范围查询、找前驱后继 | `map` / `set` | 有 `lower_bound`、`upper_bound` |
| 需要稳定的最坏复杂度 | `map` / `set` | 操作通常为 `O(log n)` |
| 键没有自然哈希或需要自定义哈希成本很高 | `map` / `set` | 只需定义严格弱序 |
| 输出必须按排序键呈现 | `map` / `set` | 避免额外排序 |

“哈希表永远更快”并不成立。小数据量下常数、内存局部性和哈希计算成本都可能改变结果；更重要的是，无序容器根本无法替代范围查询的语义。反过来，若你只需按键精确查找，却每次都接受对数复杂度并不需要排序，`map` 也未必是最匹配的选择。

## 六、总结

- `map`/`set` 的核心价值是有序键：支持有序遍历、`lower_bound`、`upper_bound` 和范围查询，常见复杂度为 `O(log n)`。
- `unordered_map`/`unordered_set` 的核心价值是平均 `O(1)` 精确查找；它们没有排序语义，最坏复杂度也不能忽略。
- `operator[]` 会在 `map` 或 `unordered_map` 缺失键时插入默认值；只查询时使用 `find`，需要缺失即报错时使用 `at`。
- `set::insert` 和 `unordered_set::insert` 返回的布尔值可判断某元素是否首次插入。
- 已知规模时，哈希容器可以 `reserve` 减少 rehash；重散列会影响迭代器有效性。
- 自定义哈希键必须让“相等对象具有相同哈希值”，并保证相等判断符合键语义。

把“要不要排序”理解为需求，而非性能装饰，关联容器就不再难选。你不是在四个名字中抽签，而是在选择数据是否应当以某种键顺序存在。
