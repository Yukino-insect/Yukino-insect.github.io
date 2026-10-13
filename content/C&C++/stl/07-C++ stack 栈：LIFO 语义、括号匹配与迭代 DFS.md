+++
date = '2026-10-13T09:10:00+08:00'
draft = false
title = 'C++ stack 栈：LIFO 语义、括号匹配与迭代 DFS'
+++
`std::stack` 表示后进先出（LIFO，Last In, First Out）的栈。最后压入的元素，必须最先取出；这正好对应函数调用、撤销操作、括号嵌套和深度优先搜索中“先把当前分支走到底，再回退”的过程。

```cpp
#include <stack>

std::stack<int> values;
values.push(10);
values.push(20);

int top = values.top();  // 20
values.pop();            // 删除 20，不返回它
```

它和 `queue` 一样是容器适配器：它故意不给你任意访问中间元素的接口。若你总要访问第 3 个、第 10 个元素，说明问题本身也许不是“栈”，硬用 `stack` 只是在掩盖模型不对。

## 一、栈的操作与复杂度

`std::stack` 定义在 `<stack>` 中，默认使用 `std::deque` 作为底层容器。最常用成员如下：

| 目的 | 成员函数 | 说明 |
| ---- | -------- | ---- |
| 压入栈顶 | `push(value)` | 在顶部放入已有值 |
| 原地构造 | `emplace(args...)` | 在顶部直接构造元素 |
| 查看栈顶 | `top()` | 返回引用，不删除 |
| 弹出栈顶 | `pop()` | 删除，不返回元素 |
| 判空 | `empty()` | 空栈时为 `true` |
| 获得数量 | `size()` | 返回 `std::size_t` |

这些操作通常为 `O(1)`。栈顶在代码中的一端，但具体对应底层容器的哪一端是适配器实现细节；使用者只需理解 `top`、`push`、`pop` 的逻辑关系。

和 `queue` 相同，`pop()` 不返回值。若需要取得再删除：

```cpp
int value = values.top();
values.pop();
```

并且 `top()`、`pop()` 的前提都是栈非空。

## 二、括号匹配：最典型的嵌套问题

给定一个只含 `()[]{}` 的字符串，判断每个右括号能否与最近尚未匹配的左括号配对。最近打开的括号必须最先关闭，这正是 LIFO，而不是某种偶然的技巧。

```cpp
#include <stack>
#include <string>

bool isValidBrackets(const std::string& text) {
    std::stack<char> opened;

    for (const char ch : text) {
        if (ch == '(' || ch == '[' || ch == '{') {
            opened.push(ch);
            continue;
        }

        if (ch != ')' && ch != ']' && ch != '}') {
            return false;
        }
        if (opened.empty()) {
            return false;
        }

        const char left = opened.top();
        opened.pop();

        const bool matched =
            (left == '(' && ch == ')') ||
            (left == '[' && ch == ']') ||
            (left == '{' && ch == '}');
        if (!matched) {
            return false;
        }
    }

    return opened.empty();
}
```

### 1. 为什么只保存左括号

读到左括号时，它在等待未来某个右括号，因此压栈。读到右括号时，它必须匹配“最后一个仍未匹配的左括号”，所以检查并弹出栈顶。

以 `([])` 为例：

```text
读 ( ：栈 [(]
读 [ ：栈 [(, []
读 ] ：弹出 [，匹配
读 ) ：弹出 (，匹配
结束 ：栈为空，合法
```

`([)]` 会在读到 `)` 时发现栈顶是 `[`，立即失败。`())` 则会在最后一个 `)` 到来时发现栈为空。遍历结束仍不为空，例如 `(()`，表示还有未关闭的左括号。

每个字符最多进栈和出栈一次，时间复杂度为 `O(n)`，最坏额外空间为 `O(n)`。

### 2. 更紧凑的“期待右括号”写法

也可以在读到左括号时直接压入它所期待的右括号：

```cpp
bool isValidBracketsCompact(const std::string& text) {
    std::stack<char> expected;

    for (const char ch : text) {
        if (ch == '(') expected.push(')');
        else if (ch == '[') expected.push(']');
        else if (ch == '{') expected.push('}');
        else if (ch == ')' || ch == ']' || ch == '}') {
            if (expected.empty() || expected.top() != ch) {
                return false;
            }
            expected.pop();
        } else {
            return false;
        }
    }

    return expected.empty();
}
```

这种版本避免了配对表，但只适用于规则简单的场景。选择哪一种应以可读性为准，没必要为了少写两行条件把错误处理藏起来。

## 三、用栈改写递归 DFS

递归调用本身依赖调用栈。把“下一步要访问的节点”显式保存到 `std::stack` 中，就能写出迭代版深度优先搜索，避免极深递归导致调用栈溢出。

```cpp
#include <stack>
#include <vector>

std::vector<int> depthFirstOrder(
    const std::vector<std::vector<int>>& graph, int start
) {
    const int n = static_cast<int>(graph.size());
    std::vector<bool> visited(n, false);
    std::vector<int> order;
    std::stack<int> pending;

    pending.push(start);

    while (!pending.empty()) {
        const int current = pending.top();
        pending.pop();

        if (visited[current]) {
            continue;
        }
        visited[current] = true;
        order.push_back(current);

        for (auto it = graph[current].rbegin(); it != graph[current].rend(); ++it) {
            if (!visited[*it]) {
                pending.push(*it);
            }
        }
    }

    return order;
}
```

### 1. 为什么邻居要倒序压栈

若希望访问顺序尽量与递归版的“从左到右遍历邻居”一致，就必须从右到左压栈。因为最后压入的左侧邻居位于栈顶，会最先处理。

```text
邻居顺序：A, B, C
压栈顺序：C, B, A
出栈顺序：A, B, C
```

图的 DFS 并不存在唯一正确的输出顺序；访问顺序由邻接表顺序与压栈顺序共同决定。算法正确性通常只要求每个可达节点被访问，不要求恰好输出某一串节点。

### 2. 入栈时标记还是出栈时标记

上例在出栈时才设 `visited[current] = true`，所以同一节点可能被多个前驱压入多次，但只会真正处理一次。它写起来直观，也便于模拟递归。

若要避免重复压栈，可以在入栈时标记：

```cpp
visited[start] = true;
pending.push(start);

while (!pending.empty()) {
    const int current = pending.top();
    pending.pop();

    for (const int next : graph[current]) {
        if (!visited[next]) {
            visited[next] = true;
            pending.push(next);
        }
    }
}
```

两种做法都可以，但同一个函数里要保持一致。不要在循环开始处又跳过已访问节点、在压栈处又无条件标记，却没有想清楚哪个时刻代表“发现”、哪个时刻代表“完成”。

## 四、表达式求值中的两个角色

栈还常用于表达式解析。这里至少要区分两个问题：

- **操作数栈**：保存尚未参与计算的数值。
- **运算符栈**：保存尚未执行的运算符，用于处理优先级和括号。

例如逆波兰表达式 `2 3 4 * +` 的求值只需一个操作数栈：

```text
读 2：栈 [2]
读 3：栈 [2, 3]
读 4：栈 [2, 3, 4]
读 *：弹出 4、3，压入 3 * 4 = 12 -> [2, 12]
读 +：弹出 12、2，压入 2 + 12 = 14 -> [14]
```

从栈中取二元运算的右操作数时，先得到的是右边的值，顺序不能颠倒：

```cpp
const int right = values.top();
values.pop();
const int left = values.top();
values.pop();
values.push(left - right);
```

对加法、乘法写反仍会得到相同结果，恰好会掩盖 bug；减法和除法才会让问题暴露。测试表达式时不要只用交换律成立的运算符。

## 五、`stack` 的限制与替代选择

`std::stack` 不提供迭代器，不能写范围 `for`，也不能清空之外地访问中间元素。若你需要：

- 两端都访问或维护单调序列，使用 `std::deque`。
- 按到达先后处理，使用 `std::queue`。
- 总是取最小值或最大值，使用 `std::priority_queue`。
- 对整个序列随机访问、排序、遍历，使用 `std::vector`。

例如“撤销最近操作”是栈；“按提交顺序执行任务”是队列；“总选截止时间最近的任务”是优先队列。容器选择不应只根据 API 是否能凑合实现，而应根据下一项由什么规则决定。

## 六、总结

- `std::stack` 是 LIFO 栈，包含在 `<stack>` 中，常用 `push`、`top`、`pop`、`empty`。
- `top()` 只查看栈顶，`pop()` 只删除栈顶；两者都不能用于空栈。
- 括号匹配依赖“最近未匹配的左括号先关闭”，因此天然适合栈，时间复杂度为 `O(n)`。
- 迭代 DFS 把递归调用栈显式化；为了得到从左到右的访问效果，邻居通常要倒序压栈。
- `top()` 返回引用，元素弹出后不能继续持有该引用；需在 `pop()` 前取值。
- 当题目需要任意访问或不同的取出规则时，不要勉强使用 `stack`。数据结构表达的是约束，而不是一组可以随便拼接的方法名。
