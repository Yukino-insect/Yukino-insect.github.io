+++
date = '2026-10-06T20:11:00+08:00'
draft = false
title = '考研数据结构：KMP 算法、前缀函数与模式匹配'
+++

KMP 是串匹配中最常考的算法之一。它要解决的问题很朴素：在主串 `text` 中寻找模式串 `pattern` 首次出现的位置。朴素算法在某次失配后会让模式串右移一位并重新比较，最坏可能进行 `O(nm)` 次比较；KMP 借助模式串自身的重复结构，保证主串指针不回退，使总复杂度降到 `O(n + m)`。

真正困难的地方并不是写出双循环，而是回答这个问题：已经匹配的一段字符为什么可以直接跳过？答案在于它既是已匹配文本的后缀，也是模式串的前缀；下一次尝试不必否认已经得到的这一部分信息。

## 一、前缀、后缀与 `lps` 数组

对长度为 `m` 的模式串，`lps[i]` 表示子串 `pattern[0..i]` 的**最长相等真前后缀长度**。所谓“真前缀/真后缀”，就是不能等于整个子串本身。

例如模式串为 `ababaca`：

| 下标 `i` | 子串 `pattern[0..i]` | 最长相等真前后缀 | `lps[i]` |
| -------- | --------------------- | ---------------- | -------- |
| 0 | `a` | 无 | 0 |
| 1 | `ab` | 无 | 0 |
| 2 | `aba` | `a` | 1 |
| 3 | `abab` | `ab` | 2 |
| 4 | `ababa` | `aba` | 3 |
| 5 | `ababac` | 无 | 0 |
| 6 | `ababaca` | `a` | 1 |

所以 `lps` 为 `[0, 0, 1, 2, 3, 0, 1]`。有的教材把它叫 `next` 数组，有的 `next` 采用从 `-1` 开始、整体错一位的定义。它们的跳转思想相同，但下标含义不同；答题和编码时必须先写清楚你使用的是哪一种定义，不能把两套公式拼起来。

## 二、失配时为什么模式串指针能跳转

假设已经匹配 `j` 个字符，即 `text` 的末尾部分等于 `pattern[0..j-1]`。当比较 `text[i]` 和 `pattern[j]` 失败时，`pattern[0..j-1]` 不需要全部作废：其中长度为 `lps[j - 1]` 的后缀，也正好是模式串的前缀。

因此令 `j = lps[j - 1]`，继续比较同一个 `text[i]` 与新的 `pattern[j]`。主串下标 `i` 不回退；若仍失配，再按同样规则缩短 `j`。只有当 `j` 退到 `0` 仍不匹配时，才让 `i` 向右移动。

```text
已匹配： pattern[0 ... j - 1]
失配：   text[i] != pattern[j]

保留：   已匹配部分的最长“前缀 = 后缀”
跳转：   j = lps[j - 1]
```

这正是 KMP 的核心不变量：`pattern[0..j-1]` 始终等于刚刚扫描过的文本后缀。只要这个不变量不被破坏，跳转就不是猜测。

## 三、可直接运行的 C++17 实现

下面代码使用 `lps` 定义，并把“找不到”表示为 `std::string::npos`。空模式串按标准库 `find` 的常见约定匹配在位置 `0`，避免访问不存在的 `pattern[0]`。

```cpp
#include <iostream>
#include <string>
#include <vector>

std::vector<std::size_t> buildLps(const std::string& pattern) {
    std::vector<std::size_t> lps(pattern.size(), 0);

    for (std::size_t i = 1, length = 0; i < pattern.size();) {
        if (pattern[i] == pattern[length]) {
            lps[i++] = ++length;
        } else if (length != 0) {
            length = lps[length - 1];
        } else {
            lps[i++] = 0;
        }
    }

    return lps;
}

std::size_t kmpFind(const std::string& text, const std::string& pattern) {
    if (pattern.empty()) {
        return 0;
    }

    const std::vector<std::size_t> lps = buildLps(pattern);

    for (std::size_t i = 0, j = 0; i < text.size();) {
        if (text[i] == pattern[j]) {
            ++i;
            ++j;
            if (j == pattern.size()) {
                return i - j;
            }
        } else if (j != 0) {
            j = lps[j - 1];  // i 不回退
        } else {
            ++i;
        }
    }

    return std::string::npos;
}

int main() {
    const std::string text = "ababcabcacbab";
    const std::string pattern = "abcac";

    const std::vector<std::size_t> lps = buildLps(pattern);
    std::cout << "lps: ";
    for (std::size_t value : lps) {
        std::cout << value << ' ';
    }
    std::cout << '\n';

    const std::size_t pos = kmpFind(text, pattern);
    if (pos == std::string::npos) {
        std::cout << "not found\n";
    } else {
        std::cout << "found at index " << pos << '\n';
    }
}
```

编译运行：

```bash
g++ -std=c++17 kmp.cpp -o kmp
./kmp
```

`buildLps` 也只需线性时间。变量 `i` 只向右移动，`length` 在失配时按已计算的 `lps` 回退；它不会为每个位置重新枚举所有前后缀，所以构造复杂度是 `O(m)`，而不是看起来可能误以为的 `O(m^2)`。

## 四、手算与代码最常见的错误

- **把整个串当作真前后缀。** `lps[i]` 最大只能是 `i`，不可能是 `i + 1`。
- **失配时让文本指针回退。** KMP 的价值正是 `i` 不回退；回退后便退回朴素匹配的思路。
- **使用 `lps[j]` 而不是 `lps[j - 1]`。** 已成功匹配的是前 `j` 个字符，对应末位下标为 `j - 1`。
- **忘记空模式串。** 若直接读取 `pattern[j]`，空串会越界。必须先约定语义并提前返回。
- **混用不同教材的 `next` 表。** 先确认首项是 `0` 还是 `-1`，再确定失配转移公式。

## 五、复杂度与适用边界

设主串长度为 `n`、模式串长度为 `m`。构造 `lps` 是 `O(m)`，匹配是 `O(n)`，总时间为 `O(n + m)`，额外空间为 `O(m)`。当模式串较长、文本很大或要解释“失配时为何不用重头比较”时，KMP 很有价值。

若只是一次短字符串查找，工程中直接使用 `std::string::find` 通常更清晰；它的具体内部算法由实现决定。考研题目若明确要求 KMP，则应写出辅助表的定义与失配跳转依据，不能只给一个库调用。掌握 `lps` 的语义后，KMP 不再是一串神秘下标，而是对已匹配信息的诚实复用。

我们以代码为例，pattern 中的 [0] 一定是 0，因此 i 从 1 开始。

len 可以视为当前字串的最长相同前后缀长度。
