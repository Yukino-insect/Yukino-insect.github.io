+++
date = '2026-10-09T20:03:00+08:00'
draft = false
title = '贪心算法：活动选择、交换论证与局部最优的边界'
+++
贪心算法每一步都选择当前看来最好的方案，并且一旦选择便不回头。它的优势是实现简洁、通常很快；它的危险则同样明显：**局部最优并不会自动推出全局最优**。能否使用贪心，必须给出可验证的结构性理由。

活动选择问题的目标是：给定若干有开始、结束时间的活动，同一资源一次只能安排一个活动，选择数量最多的两两相容活动。这里采用半开区间 `[start, finish)`，因此前一个恰好在后一个开始时结束是相容的。

## 一、为何选择“最早结束”的活动

若每次选择结束时间最早、且与已选活动相容的活动，它会为后续活动留下最多时间。更正式地，用**交换论证**证明：设某个最优解的第一项不是最早结束的可选活动 `g`，而是 `o`。因为 `finish(g) <= finish(o)`，把 `o` 替换成 `g` 后，原来在 `o` 后安排的所有活动仍然都能安排；活动数量没有减少。于是总存在一个最优解以 `g` 开头。去掉 `g` 后，剩余问题形式相同，可以重复该论证。

这说明“最早结束”是安全选择；反之，“持续时间最短”或“开始最早”并没有这条交换保证，可能错过更优解。

## 二、完整 C++17 程序

输入第一行是活动数 `n`，之后每行 `start finish`。程序输出最多可选数量以及被选活动的原始编号。排序后只要维护最近一个被选活动的结束时间即可。

```cpp
#include <algorithm>
#include <iostream>
#include <limits>
#include <vector>
using namespace std;

struct Activity {
    int start;
    int finish;
    int id;
};

int main() {
    int n;
    cin >> n;
    vector<Activity> activities(n);
    for (int i = 0; i < n; ++i) {
        cin >> activities[i].start >> activities[i].finish;
        activities[i].id = i + 1;
    }

    sort(activities.begin(), activities.end(), [](const Activity& a, const Activity& b) {
        if (a.finish != b.finish) return a.finish < b.finish;
        return a.start < b.start;
    });

    vector<int> chosen;
    int lastFinish = numeric_limits<int>::min();
    for (const Activity& activity : activities) {
        if (activity.start >= lastFinish) {
            chosen.push_back(activity.id);
            lastFinish = activity.finish;
        }
    }

    cout << chosen.size() << '\n';
    for (int id : chosen) cout << id << ' ';
    cout << '\n';
}
```

输入 `4`、`1 4`、`3 5`、`0 6`、`5 7` 时，程序会选择编号 `1 4`，数量为 `2`。活动结束时刻相同的活动任取一个均不影响最大数量；代码用开始时刻作为稳定的次级排序规则。

## 三、复杂度分析

排序需要 `O(n log n)`，排序后的单次扫描需要 `O(n)`，因此总时间复杂度为 `O(n log n)`。存放输入和答案的向量合计 `O(n)`；若题目只要求输出数量而不要求记录所选编号，除输入外的辅助空间可降为 `O(1)`。

复杂度不能写成“两个步骤相加所以 `O(n log n + n)`”后就停止。根据高阶项主导原则，它最终化简为 `O(n log n)`。

## 四、何时不要强行贪心

活动选择每个活动价值都相同，目标是数量最大。若每个活动有收益，问题变成**带权区间调度**，选择最早结束的活动不一定收益最大，需要动态规划。0/1 背包也不能按价值密度贪心；只有允许拆分物品的分数背包才可以。

考研中遇到贪心题，先写出候选规则，再尝试把任意最优解的第一步交换为你的选择。若交换后不可行或价值会下降，就不应以“直觉上合理”为理由继续使用贪心。算法不接受这种含糊的自信，题目自然也不会。
