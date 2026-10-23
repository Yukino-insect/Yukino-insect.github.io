+++
date = '2026-10-13T09:30:00+08:00'
draft = false
title = 'C++ priority_queue 优先队列：堆、比较器与 Top K 问题'
+++
当“下一个处理谁”不再由到达顺序决定，而由数值、截止时间或距离决定时，普通 `queue` 已经不合适。`std::priority_queue` 会始终把优先级最高的元素放在 `top()`，插入和取出都保持这种顺序，典型底层结构是二叉堆。

```cpp
#include <queue>

std::priority_queue<int> largest_first;
largest_first.push(3);
largest_first.push(1);
largest_first.push(5);

int value = largest_first.top();  // 5
largest_first.pop();
```

默认情况下它是**大顶堆**：数值最大的元素优先。许多错误并非不会写 `push` 和 `pop`，而是没有先问清楚：这里的“优先”究竟意味着最大值先出，还是最小值先出？Top K、合并多路有序数据、定时任务、Dijkstra 算法对此答案各不相同。

## 一、堆提供什么保证

优先队列不是完整排序的容器。它只保证 `top()` 是按比较规则最优的元素；除顶部外，其他元素的相对顺序不对外承诺。

| 操作 | 复杂度 | 说明 |
| ---- | ------ | ---- |
| `top()` | `O(1)` | 查看当前最高优先级元素 |
| `push(x)` / `emplace(...)` | `O(log n)` | 插入并恢复堆性质 |
| `pop()` | `O(log n)` | 删除顶部并恢复堆性质 |
| `empty()` / `size()` | `O(1)` | 状态查询 |

它定义在 `<queue>` 中，是容器适配器，默认使用 `std::vector<T>` 保存堆元素。与 `queue`、`stack` 一样，`pop()` 不返回元素：

```cpp
const int best = heap.top();
heap.pop();
```

不要把优先队列遍历后期待得到排序序列。若不断执行“读取 `top` 后 `pop`”，得到的序列会按优先级排列，但原优先队列也被清空；若要保留原对象，先复制一份。

## 二、最大堆、最小堆与比较器的读法

默认声明：

```cpp
std::priority_queue<int> max_heap;
```

等价于：

```cpp
std::priority_queue<int, std::vector<int>, std::less<int>> max_heap;
```

`std::less<int>` 使较大的元素拥有更高优先级，所以 `top()` 是最大值。最小堆可写为：

```cpp
#include <functional>
#include <queue>
#include <vector>

std::priority_queue<int, std::vector<int>, std::greater<int>> min_heap;
```

记忆方式不必绕进“比较器返回 true 到底代表什么”的内部细节：**写 `std::greater<T>` 时，`top()` 是最小元素；写 `std::less<T>` 或省略比较器时，`top()` 是最大元素**。每次写完可用两个值心算验证一下：若放入 `2` 和 `5`，你期待 `top()` 返回哪个？

对自定义对象，更推荐把比较逻辑写成独立的可命名类型：

```cpp
#include <queue>
#include <string>
#include <vector>

struct Task {
    int deadline;
    std::string name;
};

struct EarlierDeadlineFirst {
    bool operator()(const Task& left, const Task& right) const {
        return left.deadline > right.deadline;
    }
};

std::priority_queue<Task, std::vector<Task>, EarlierDeadlineFirst> tasks;
```

这里 `left.deadline > right.deadline` 看似“反着写”，但结果是截止时间更小的任务位于 `top()`。可把它理解为：当 `left` 的截止时间更晚时，比较器说它的优先级更低，应排在 `right` 后面。比较器要形成严格弱序；不要写 `>=`，相等元素之间不应被宣称“彼此都排在对方后面”。

## 三、Top K：为什么保留大小为 K 的最小堆

给定大量整数，求最大的 `k` 个元素。最直接的方法是完整排序，复杂度为 `O(n log n)`；若只需 `k` 个最大值，保留一个大小不超过 `k` 的**最小堆**通常更合适。

思路如下：

1. 堆中只保留目前见过的最大的 `k` 个数。
2. 堆顶是这 `k` 个数中最小的，也就是“进入前 K 的门槛”。
3. 新值不超过门槛，忽略；新值超过门槛，弹出旧门槛，再加入新值。

```cpp
#include <functional>
#include <queue>
#include <stdexcept>
#include <vector>

std::vector<int> largestK(const std::vector<int>& values, int k) {
    if (k < 0 || static_cast<std::size_t>(k) > values.size()) {
        throw std::invalid_argument("k is out of range");
    }

    std::priority_queue<int, std::vector<int>, std::greater<int>> smallest_of_top_k;

    for (const int value : values) {
        if (static_cast<int>(smallest_of_top_k.size()) < k) {
            smallest_of_top_k.push(value);
        } else if (k > 0 && value > smallest_of_top_k.top()) {
            smallest_of_top_k.pop();
            smallest_of_top_k.push(value);
        }
    }

    std::vector<int> result;
    result.reserve(static_cast<std::size_t>(k));
    while (!smallest_of_top_k.empty()) {
        result.push_back(smallest_of_top_k.top());
        smallest_of_top_k.pop();
    }
    return result;  // 从小到大；若需要降序，再 reverse。
}
```

该算法的堆大小至多为 `k`，每次调整成本为 `O(log k)`，总时间为 `O(n log k)`，额外空间为 `O(k)`。当 `k` 远小于 `n` 时，这比完整排序更划算。

### 1. 求最小的 K 个元素时为什么反过来

若要保留最小的 `k` 个元素，应使用**大顶堆**。堆顶成为当前保留集合中最大的元素，也就是最容易被更小的新值替换的门槛。

```text
保留最大 K 个：用最小堆，堆顶是最小的保留值。
保留最小 K 个：用最大堆，堆顶是最大的保留值。
```

这比死记“Top K 要小根堆”准确得多。关键并不是题目里出现了 Top K，而是你想快速淘汰保留集合里的哪一个元素。

### 2. `k == 0` 不是普通分支

`k == 0` 时，堆永远不应有元素，当然也不能调用 `top()`。上例专门以 `k > 0` 保护了 `top()`。若业务语义不允许 `k == 0`，更简单的做法是在入口直接抛出异常；边界策略取决于函数的约定，不能事后让空堆操作“碰运气”。

## 四、合并 K 个有序链表：堆中放什么

合并多个升序链表时，每次应取所有当前链表头中最小的节点。这里的优先队列元素不是数值本身，而是节点指针；比较器按节点值排序。

```cpp
#include <queue>
#include <vector>

struct ListNode {
    int val;
    ListNode* next;
};

struct SmallerNodeFirst {
    bool operator()(const ListNode* left, const ListNode* right) const {
        return left->val > right->val;
    }
};

ListNode* mergeKLists(std::vector<ListNode*>& lists) {
    std::priority_queue<ListNode*, std::vector<ListNode*>, SmallerNodeFirst> pending;

    for (ListNode* head : lists) {
        if (head != nullptr) {
            pending.push(head);
        }
    }

    ListNode dummy{0, nullptr};
    ListNode* tail = &dummy;

    while (!pending.empty()) {
        ListNode* node = pending.top();
        pending.pop();

        tail->next = node;
        tail = node;

        if (node->next != nullptr) {
            pending.push(node->next);
        }
    }

    return dummy.next;
}
```

任何时刻，堆里至多保存每条链表的一个当前候选节点，因此堆大小不超过链表数量 `k`。若总节点数为 `N`，时间复杂度为 `O(N log k)`，额外空间为 `O(k)`。注意函数只是重新连接已有节点，没有新建每个结果节点；原链表结构会被改变，接口使用者应知晓这一点。

## 五、它不是“带 decrease-key 的通用优先队列”

在 Dijkstra 算法中，一个顶点的暂定距离可能被更新。标准 `std::priority_queue` 不支持在堆中定位某个既有元素并降低其键值，也没有 `decrease_key` 操作。常用做法是把更新后的新条目再次 `push`，弹出时丢弃过期条目：

```cpp
if (known_distance != distance[node]) {
    continue;  // 堆中的旧记录，跳过
}
```

这不是 bug，而是一种“惰性删除”策略。它会让堆中存在重复记录，但实现简单、复杂度仍可接受。若问题必须高效删除任意元素或修改任意优先级，可能需要额外的索引结构，或者选择其他专用数据结构；不要假设所有名为 priority queue 的接口都相同。

## 六、与 `sort`、`nth_element` 的选择

| 需求 | 更合适的工具 | 原因 |
| ---- | ------------ | ---- |
| 所有元素最终有序 | `std::sort` | 得到完整排序序列 |
| 只找第 k 个秩位置 | `std::nth_element` | 平均线性选择，避免维护堆 |
| 一次性取 Top K，`k` 很小 | 大小为 `k` 的 `priority_queue` | `O(n log k)` |
| 数据持续到来，随时查询当前 Top K | 大小为 `k` 的 `priority_queue` | 可增量维护 |
| 不断取全局最优待办项 | `priority_queue` | 每次 `top` 即当前最优 |

容器和算法的选择取决于结果何时需要、需要多完整，而不取决于哪个名字听起来更高级。

## 七、总结

- `std::priority_queue` 默认是大顶堆，`top()` 是最大元素；传入 `std::greater<T>` 可得到最小堆。
- 它只保证堆顶最优，不保证其余元素有序；`push`、`pop` 为 `O(log n)`，`top` 为 `O(1)`。
- `pop()` 不返回值，且 `top()`、`pop()` 都要求非空。
- 求最大的 K 个元素时维护大小为 `k` 的最小堆；求最小的 K 个元素时维护大小为 `k` 的最大堆。
- 自定义比较器应表达“谁的优先级更低”，并满足严格弱序；相等时不能用 `>=` 破坏比较规则。
- `std::priority_queue` 不支持就地修改任意元素的优先级；Dijkstra 中通常以重复入堆和惰性跳过旧记录处理更新。

堆的价值不在于把数据“差不多排个序”，而在于以较低成本持续回答：此刻最应该处理的是谁。只要这个问题的规则明确，最小堆和最大堆也就不再容易写反。
