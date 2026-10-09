+++
date = '2026-10-09T20:05:00+08:00'
draft = false
title = '回溯算法：N 皇后、状态剪枝与搜索树复杂度'
+++
回溯法按深度优先顺序构造候选解；一旦发现当前部分解不可能扩展为合法完整解，就撤销最后一步选择，返回上层尝试其他分支。它适合组合、排列、棋盘放置和约束满足问题。回溯不是动态规划：前者在搜索解空间树，后者通常合并等价子问题的最优值。

N 皇后要求在 `n × n` 棋盘放置 `n` 个皇后，使任意两个不同行、不同列、不同对角线。若按行递归，每行只放一个皇后，行冲突已天然消除；需要维护的约束只剩列与两类对角线。

## 一、状态如何表示

第 `row` 行尝试第 `col` 列时：

- 列编号为 `col`；
- 主对角线可由 `row - col` 唯一表示，范围可能为负，代码加上 `n - 1` 偏移；
- 副对角线可由 `row + col` 唯一表示。

三个布尔数组保存哪些列、主对角线、副对角线已被占用。判断合法性和撤销选择都为 `O(1)`，这比每次扫描已放置的皇后更清楚也更快。

## 二、完整 C++17 程序

输入 `n`，输出解的总数；`n = 8` 时答案为 `92`。程序使用 `long long`，避免中等规模的解数量过早溢出。

```cpp
#include <iostream>
#include <vector>
using namespace std;

long long dfs(int row, int n, vector<bool>& usedCol,
              vector<bool>& usedMainDiag, vector<bool>& usedAntiDiag) {
    if (row == n) return 1;

    long long ways = 0;
    for (int col = 0; col < n; ++col) {
        int mainDiag = row - col + n - 1;
        int antiDiag = row + col;
        if (usedCol[col] || usedMainDiag[mainDiag] || usedAntiDiag[antiDiag]) {
            continue;
        }

        usedCol[col] = usedMainDiag[mainDiag] = usedAntiDiag[antiDiag] = true;
        ways += dfs(row + 1, n, usedCol, usedMainDiag, usedAntiDiag);
        usedCol[col] = usedMainDiag[mainDiag] = usedAntiDiag[antiDiag] = false;
    }
    return ways;
}

int main() {
    int n;
    cin >> n;
    if (n < 1) {
        cout << 0 << '\n';
        return 0;
    }
    vector<bool> usedCol(n, false);
    vector<bool> usedMainDiag(2 * n - 1, false);
    vector<bool> usedAntiDiag(2 * n - 1, false);
    cout << dfs(0, n, usedCol, usedMainDiag, usedAntiDiag) << '\n';
}
```

递归调用前的三次标记叫作“做选择”，调用后的三次恢复叫作“撤销选择”。后者绝不能遗漏；若状态未恢复，其他分支会错误地把不存在的皇后当作障碍。共享状态下的恢复，是回溯代码最核心的纪律。

## 三、正确性：搜索树没有漏也没有重

递归层 `row` 恰好表示前 `row` 行已经各放一个合法皇后。对当前行，程序枚举所有列：冲突列不可能产生合法解，被安全剪去；每个合法列都递归尝试，因此没有遗漏。每条从根到第 `n` 层叶子的路径对应一个不同的列序列，也就是一个不同棋盘，所以没有重复计数。到达 `row == n` 时，所有行都合法放置，返回 `1` 正确。

## 四、复杂度不要被“每层 n 个循环”骗过

不剪枝时，第 1 行有最多 `n` 种选择，第 2 行最多 `n - 1` 种……，叶子规模上界为 `n!`。每次尝试和状态修改是 `O(1)`，总时间上界常写作 `O(n!)`（更精细的结点数分析并不改变其指数级本质）。对角线剪枝会大幅减少实际搜索量，但不能把最坏情况变成多项式。

三个标记数组为 `O(n)`，递归栈深度为 `O(n)`，因此辅助空间为 `O(n)`；若还要保存并输出每一个棋盘，需要再加上答案输出本身的空间。输出规模很大时，不能假装它不存在。

## 五、回溯、剪枝与分支限界

回溯通常以“是否满足约束”剪枝，常用于找全部解或任意可行解。分支限界也搜索状态空间，但会用目标函数的上界/下界淘汰“不可能优于当前最优解”的分支，常用于最优化问题。两者都会回退，却不能因此混为同一个概念。

面对考研中的排列、子集或路径题，先明确一层递归代表什么，再列出选择、约束、终止条件和恢复动作。递归函数若无法用一句话说明它维护的部分解，代码多半也没有真正被你控制。
