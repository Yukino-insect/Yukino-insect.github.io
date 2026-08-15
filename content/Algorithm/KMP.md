+++
date = '2025-10-23T17:37:33+08:00'
draft = false
title = 'KMP'
+++

**KMP** 算法用来解决在一个主串中高效的查找一个模式串第一次出现的位置，它的核心思想是当匹配失败时利用已经匹配成功部分减少重复比较，避免从头重新匹配。

下面看一段 KMP 算法实现

```c++
vector<int> buildNext(const string& p) {
    int m = (int) p.size();
    vector<int> next(m, 0);
    int len = 0;
    int i = 1;

    while (i < m) {
        if (p[len] == p[i]) {
            len++;
            next[i] = len;
            i++;
        } else {
            if (len != 0) {
                len = next[len - 1];
            } else {
                next[i] = 0;
                i++;
            }

        }
    }

    return next;
}

int kmpSearch(string& pattern, string& text) {
    vector<int> next = buildNext(pattern);

    int p1 = 0, p2 = 0;
    int m = (int) text.size();
    int n = (int) pattern.size();
    while (p1 < m) {
        if (text[p1] == pattern[p2]) {
            p1++;
            p2++;

            if (p2 == n) {
                return p1 - n;
            }
        } else {
            if (p2 != 0) p2 = next[p2 - 1];
            else p1++;
        }
    }

    return -1;
}
```

整个算法的核心函数有两个：

1. 求 **next** 数组
2. 根据 next 数组进行模式匹配

下面简单描述一下搜索逻辑是怎么样的。

next 数组每个 [i] 位置上记录的是该字串中相同前后缀的最长长度，前后缀不能包含整个字串本身。这样当在匹配失败时，text 的指针不需要回退，只需要将 pattern 的指针回退到相应的前缀末尾即可。因为 text 中指针前面的字符串可以视为后缀，pattern 的前缀和这部分后缀相等，因此可以跳过不比较。

接下来我们来看一下 next 数组如何求。

我们以代码为例，pattern 中的 [0] 一定是 0，因此 i 从 1 开始。

len 可以视为当前字串的最长相同前后缀长度。

