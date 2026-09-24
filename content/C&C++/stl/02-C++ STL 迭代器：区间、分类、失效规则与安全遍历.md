+++
date = '2026-09-24T19:00:00+08:00'
draft = false
title = 'C++ STL 迭代器：区间、分类、失效规则与安全遍历'
+++

初学 STL 时，`vector` 用下标访问，`map` 用 `find`，`list` 又没有下标；不同容器的操作方式看似各自为政。**迭代器（iterator）提供了一层统一的“位置”抽象：容器负责存储，迭代器负责指向元素位置，算法则接收一段由迭代器界定的区间。**

因此，迭代器并不只是“更复杂的指针”。它让 `std::find` 能用于 `vector`、`list` 和 `set`，也解释了为什么 `std::sort` 能排序 `vector` 却不能直接排序 `list`。掌握它的关键，不是记住 `begin()` 和 `end()`，而是理解区间、能力分类、常量性以及失效规则。

## 一、迭代器表示什么

可以先把迭代器理解成“指向容器中某个位置的对象”。对多数顺序容器，它的使用形态很像指针：

```cpp
#include <iostream>
#include <vector>

int main() {
    std::vector<int> values{10, 20, 30};

    auto it = values.begin();
    std::cout << *it << '\n';  // 10

    ++it;
    *it = 99;                  // 修改第二个元素
    std::cout << values[1] << '\n';  // 99
}
```

这里，`values.begin()` 返回指向第一个元素的迭代器，`*it` 访问当前位置的元素，`++it` 让位置前进到下一个元素。`it` 本身不是元素，也不保证真的是裸指针；不要依赖其内部表示。`std::vector<int>::iterator` 在很多实现中接近 `int*`，但 `std::map`、调试模式容器和自定义容器的迭代器可能是更复杂的类型。程序只应使用标准保证的操作，而不是把迭代器强行转换成地址。

## 二、STL 算法的共同语言：半开区间

几乎所有 STL 算法都用两个迭代器表示一个范围：

```text
[first, last)
```

它包含 `first` 指向的元素，**不包含** `last` 指向的位置。因此，遍历容器的基本形式是：

```cpp
for (auto it = values.begin(); it != values.end(); ++it) {
    std::cout << *it << ' ';
}
```

`end()` 返回的是最后一个元素之后的位置，也叫尾后迭代器。它只负责界定范围，不能解引用：

```cpp
auto last = values.end();
// *last;  // 错误：不能访问尾后位置
```

半开区间很实用：

- 空区间可以自然写成 `[it, it)`，例如空容器的 `begin() == end()`；
- `[a, b)` 与 `[b, c)` 可以无缝相接；
- 对随机访问迭代器，元素数量可用 `last - first` 表示；
- 整个容器恰好是 `[container.begin(), container.end())`。

例如，只对 `vector` 中下标 1 到 3 的元素求和时，右边界要写到 `begin() + 4`：

```cpp
#include <numeric>
#include <vector>

std::vector<int> values{3, 5, 7, 11, 13};
int sum = std::accumulate(values.begin() + 1, values.begin() + 4, 0);
// 求的是 5 + 7 + 11，sum 为 23
```

`begin() + 4` 之所以能写，是因为 `vector` 的迭代器支持随机访问；这不是所有迭代器都拥有的能力。

## 三、容器和算法为什么分离

算法只要求“给我一个满足某种能力的区间”，不需要知道数据来自哪种容器。例如查找第一个偶数：

```cpp
#include <algorithm>
#include <list>
#include <vector>

auto isEven = [](int value) {
    return value % 2 == 0;
};

std::vector<int> numbers{3, 5, 8, 13};
std::list<int> linked{3, 5, 8, 13};

auto vectorIt = std::find_if(numbers.begin(), numbers.end(), isEven);
auto listIt = std::find_if(linked.begin(), linked.end(), isEven);
```

同一个 `std::find_if` 同时适用于 `vector` 与 `list`。它只需要读取元素、比较、再前进，因此要求很低。

相反，排序需要在任意两个位置之间迅速跳转、交换和比较。`std::sort` 要求随机访问迭代器：

```cpp
#include <algorithm>
#include <list>
#include <vector>

std::vector<int> values{4, 1, 3, 2};
std::sort(values.begin(), values.end());
```

```cpp
std::list<int> linked{4, 1, 3, 2};
// std::sort(linked.begin(), linked.end());  // 不满足要求
linked.sort();  // list 自己提供的排序成员函数
```

这不是 `list` 少实现了功能，而是链表无法像连续数组那样在常数时间跳到任意位置。算法对迭代器能力提出要求，容器的物理结构决定它能提供什么能力。

## 四、迭代器分类与算法要求

| 类别 | 核心能力 | 常见来源 | 算法示例 |
| ---- | -------- | -------- | -------- |
| 输入迭代器 | 读取并单向前进；可能只能单遍扫描 | 输入流 | `std::find` |
| 输出迭代器 | 写入并单向前进 | `std::back_inserter` | `std::copy` 的输出端 |
| 前向迭代器 | 可多次、单向遍历 | `forward_list`、无序关联容器 | `std::find` |
| 双向迭代器 | 可前进和后退 | `list`、`map`、`set` | `std::reverse` |
| 随机访问迭代器 | 可跳转、相减和比较位置 | `vector`、`deque`、`array` | `std::sort` |
| 连续迭代器 | 元素还保证连续存放 | `vector`、`array`、`string` | 与数组互操作 |

分类是能力递进，不是容器的等级榜。`std::advance(it, n)` 可以用于多种迭代器，但对 `vector` 常可常数时间跳转，对 `list` 则必须一步步移动；`std::distance(first, last)` 也有相同的复杂度差异。因此，不要只看 API 能否编译，也要知道它在当前容器上会付出什么代价。

## 五、常量性与安全遍历

容器通常提供 `iterator` 和 `const_iterator`。前者可以通过迭代器修改元素，后者只能读取：

```cpp
std::vector<int> values{1, 2, 3};

auto it = values.begin();
*it = 10;

auto cit = values.cbegin();
// *cit = 20;  // 错误：不能经 const_iterator 修改元素
```

`const auto it = values.begin()` 只意味着变量 `it` 不能改指向另一个位置，并不意味着 `*it` 不能修改。要保护元素，应使用 `cbegin()`、`cend()`，或让容器本身是 `const`。

只需遍历时，范围 `for` 最清楚：

```cpp
for (const auto& value : values) {
    std::cout << value << ' ';
}
```

需要保存位置、提前停止，或要在循环中删除元素时，再使用显式迭代器。算法返回的迭代器必须先判断是否找到：

```cpp
auto found = std::find(values.begin(), values.end(), 42);
if (found != values.end()) {
    std::cout << *found << '\n';
}
```

找不到时 `std::find` 返回尾后迭代器。直接解引用它是未定义行为；它不会因为程序暂时没有崩溃就变成合法操作。

## 六、插入、删除时最重要的问题：迭代器失效

迭代器记录的是容器在某一时刻的位置。容器扩容、搬移元素、擦除节点或重哈希后，这个位置可能不再有效。继续解引用或比较失效迭代器通常是未定义行为。

| 容器 | 典型操作后的规律 |
| ---- | ---------------- |
| `vector` / `string` | 扩容会使全部迭代器、指针和引用失效；中间插入或删除通常还会使操作点及其后的迭代器失效 |
| `deque` | 规则比 `vector` 更复杂；中间插入或删除会使迭代器失效，首尾操作也不应想当然地长期保存迭代器 |
| `list` / `forward_list` | 插入通常不影响其他元素的迭代器；删除只使被删元素的迭代器失效 |
| `map` / `set` | 插入通常不影响已有迭代器；擦除只使被擦除元素的迭代器失效 |
| `unordered_map` / `unordered_set` | 发生 rehash 时迭代器会失效；擦除使被删元素的迭代器失效 |

例如，下面代码有风险：

```cpp
std::vector<int> values{1, 2, 3};
auto first = values.begin();

values.push_back(4);  // 若触发扩容，first 已失效
// std::cout << *first;  // 未定义行为
```

若已知大致规模，可以调用 `reserve` 降低扩容概率，但它不是永久保证迭代器有效的承诺。

遍历时删除 `vector` 元素，必须接住 `erase` 的返回值：

```cpp
std::vector<int> values{1, 2, 3, 4, 5, 6};

for (auto it = values.begin(); it != values.end();) {
    if (*it % 2 == 0) {
        it = values.erase(it);
    } else {
        ++it;
    }
}
```

不能在 `erase(it)` 后无条件 `++it`，因为旧 `it` 已失效；也不能在范围 `for` 中直接擦除当前元素。C++20 起，若规则只是删除满足谓词的元素，`std::erase_if` 往往更简洁。

查找后插入也一样：

```cpp
auto pos = std::find(values.begin(), values.end(), 3);
if (pos != values.end()) {
    auto inserted = values.insert(pos, 99);
    // 之后使用 inserted；不要再使用旧 pos
}
```

`vector` 的 `insert` 后，原有 `pos` 可能已经失效。函数接受了这个迭代器，不代表调用结束后它仍然有效。

## 七、反向、插入迭代器与 ranges

`rbegin()`、`rend()` 提供反向迭代器，可从最后一个元素向前遍历；`rend()` 是第一个元素之前的边界，不能解引用。

`std::back_inserter` 则把写入位置包装成输出迭代器：

```cpp
#include <algorithm>
#include <iterator>

std::vector<int> source{1, 2, 3};
std::vector<int> target;

std::copy(source.begin(), source.end(), std::back_inserter(target));
```

`std::copy` 的第三个参数不是目标容器，而是目标的输出迭代器。若直接写 `target.begin()`，而 `target` 为空，就没有可写的位置。

C++20 的 ranges 可以少写一对边界：

```cpp
#include <algorithm>
#include <ranges>

std::ranges::sort(values);
```

但 ranges 没有让迭代器消失：范围内部仍依靠迭代器或哨兵定义边界，失效规则也不会因语法更短而变得宽容。

## 八、总结

- 把算法操作对象看成半开区间 `[first, last)`；`end()` 只用于比较，绝不解引用。
- 先确认算法所需的迭代器能力；`find` 和 `sort` 对迭代器的要求完全不同。
- 只读时优先 `cbegin()`、`cend()` 或 `const auto&`；`const auto it` 并不能阻止经由它修改元素。
- 算法返回迭代器后，先判断它是否等于 `end()`，再访问元素。
- 插入、删除、扩容、rehash 后，主动检查之前保存的迭代器、指针和引用是否已失效。

迭代器的价值，是让存什么和如何处理一段元素不再绑死在一起。掌握这层抽象之后，容器、算法和 ranges 就不再是一堆独立 API，而是一套围绕区间协作的规则。这样理解，比把 `begin()`、`end()` 当作必须背诵的咒语要可靠得多。
