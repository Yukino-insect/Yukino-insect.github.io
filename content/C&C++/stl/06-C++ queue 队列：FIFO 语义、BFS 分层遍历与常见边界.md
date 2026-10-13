+++
date = '2026-10-13T09:00:00+08:00'
draft = false
title = 'C++ queue 队列：FIFO 语义、BFS 分层遍历与常见边界'
+++
二叉树层序遍历中的这几行代码，已经把 `std::queue` 最重要的用途说得很清楚：先进入队列的节点，先被处理。

```cpp
std::queue<TreeNode*> nodes;
nodes.push(root);

while (!nodes.empty()) {
    TreeNode* node = nodes.front();
    nodes.pop();
    // 处理 node，再把它的孩子放到队尾
}
```

`std::queue` 是一个遵循 **FIFO（First In, First Out，先进先出）** 规则的容器适配器。它不让调用方按下标任意访问中间元素，也不让调用方从队尾取出元素；这不是功能缺失，而是在接口上明确限制操作，避免“队列”被误用成普通数组。处理排队任务、广度优先搜索（BFS）、生产者—消费者缓冲区时，这种限制恰好就是需要的约束。

本文以二叉树层序遍历为主线，解释 `queue` 的创建、入队、出队、分层技巧、复杂度和常见错误。文中的 `vector<int>()` 初始化问题，则在 [C++ 初始化方式](<../C++ 初始化：默认、值、直接、拷贝、列表与聚合初始化.md>) 中单独展开；把不同层次的概念混在一篇文章里，只会让本来简单的代码显得神秘。

## 一、队列到底保证了什么

可以把队列想成只有两个可操作端的排队通道：

```text
队头                                      队尾
front  <-  [A] [B] [C]  <-  back
          最先进入             最后进入

取元素：只能从队头取出 A
放元素：只能追加到队尾
```

因此，队列的基本规则是：

- `push(x)`：将 `x` 放到队尾。
- `front()`：查看当前队头元素，不删除它。
- `back()`：查看当前队尾元素，不删除它。
- `pop()`：删除当前队头元素，**不返回被删除的值**。
- `empty()`：判断是否为空。
- `size()`：获得当前元素数量。

对于典型实现，以上操作都是常数时间 `O(1)`。这也是队列适合任务调度与 BFS 的原因：每个元素入队一次、出队一次，总开销随元素数线性增长。

`std::queue` 位于 `<queue>` 头文件，并在 `std` 命名空间中：

```cpp
#include <queue>

std::queue<int> waiting;
waiting.push(10);
waiting.push(20);

int first = waiting.front();  // 10，只查看
waiting.pop();                // 删除 10
int last = waiting.back();    // 20
```

### 1. `queue` 是容器适配器，不是独立的底层容器

`vector`、`deque`、`list` 自己拥有元素并定义存储结构；`queue` 则在一个满足要求的底层容器之上，收窄出“先进先出”接口。默认底层容器是 `std::deque<T>`：它能高效地在两端插入和删除，正好能支撑“尾部入队、头部出队”。

```cpp
std::queue<int> first;                   // 默认使用 std::deque<int>
std::queue<int, std::list<int>> second;  // 显式使用 std::list<int>
```

日常代码几乎不需要指定第二个模板参数。重点应是你是否需要 FIFO 语义，而不是为了炫耀模板参数去替换一个已经合适的默认值。

## 二、逐行理解二叉树层序遍历

设二叉树为：

```text
        3
       / \
      9  20
        /  \
       15   7
```

层序遍历的结果应为：

```text
[[3], [9, 20], [15, 7]]
```

下面是完整实现。为简洁起见，假设题目已提供 `TreeNode` 定义。

```cpp
#include <queue>
#include <vector>

class Solution {
public:
    std::vector<std::vector<int>> levelOrder(TreeNode* root) {
        std::vector<std::vector<int>> result;
        if (root == nullptr) {
            return result;
        }

        std::queue<TreeNode*> nodes;
        nodes.push(root);

        while (!nodes.empty()) {
            const int level_size = static_cast<int>(nodes.size());
            result.emplace_back();

            for (int i = 0; i < level_size; ++i) {
                TreeNode* node = nodes.front();
                nodes.pop();

                result.back().push_back(node->val);

                if (node->left != nullptr) {
                    nodes.push(node->left);
                }
                if (node->right != nullptr) {
                    nodes.push(node->right);
                }
            }
        }

        return result;
    }
};
```

### 1. 为什么根节点先入队

遍历还未开始时，唯一已知且应处理的节点就是根。因此：

```cpp
nodes.push(root);
```

此时队列只有根节点。随后每处理一个节点，就把它的孩子按“左、右”顺序加入队尾；于是同一层的节点总会先于下一层的节点被取出。这正是 BFS 的核心不变量。

### 2. `level_size` 必须在本层开始时保存

下面这行是“按层分组”的关键：

```cpp
const int level_size = static_cast<int>(nodes.size());
```

它记录的是**本层开始前队列中已有的节点数**。在内层循环中，虽然会把孩子节点继续 `push` 进队列，但循环次数已固定为 `level_size`，因此本轮只会取出当前层的节点。

以示例树为例：

```text
开始处理第 2 层：队列 [9, 20]，level_size = 2

取出 9，加入 15：队列 [20, 15]
取出 20，加入 7 ：队列 [15, 7]

内层循环已执行 2 次，停止。
下一轮才处理 [15, 7]。
```

如果把循环条件写成 `i < nodes.size()`，`size()` 会随着孩子入队不断变化，当前层和下一层便会混在一起。循环条件在迭代期间改变，通常不是聪明，而是很难验证的错误来源。

### 3. 为什么先 `front()` 再 `pop()`

`queue::pop()` 的返回类型是 `void`。所以不能这样写：

```cpp
TreeNode* node = nodes.pop();  // 错误：pop 不返回节点
```

正确顺序是先查看队头，再删除队头：

```cpp
TreeNode* node = nodes.front();
nodes.pop();
```

从接口设计看，这要求调用方明确写出“读取”和“删除”两步。它和 C++ 中 `vector::pop_back()` 的规则相同，也能避免“返回引用后元素立刻失效”之类含混的语义。

### 4. `result.emplace_back()` 与 `result.push_back(std::vector<int>())`

原始写法可以是：

```cpp
result.push_back(std::vector<int>());
```

`std::vector<int>()` 会构造一个空的临时 `vector<int>`，随后将其放入 `result`。在现代 C++ 中，更直接的写法是：

```cpp
result.emplace_back();
```

它表示“在 `result` 尾部直接构造一个空的 `vector<int>`”。也可写成：

```cpp
result.push_back({});
```

三者在这里的结果一样，都会新增一个空的内层数组。选择 `emplace_back()` 的理由不是它有某种玄学般的性能魔法，而是它最准确地表达了“此处需要新建一个元素”。初始化的具体分类、`()` 与 `{}` 的差别、`push_back` 和 `emplace_back` 的边界，见前文链接的初始化文章。

## 三、BFS 的通用模板

队列不只遍历树。图的最短边数、迷宫最少步数、消息按到达顺序消费，都可归结为同一套骨架：从队头取出一个待处理对象，扩展其后继，再把未处理后继放到队尾。

```cpp
std::queue<State> pending;
pending.push(start);
markVisited(start);

while (!pending.empty()) {
    State current = pending.front();
    pending.pop();

    for (const State& next : expand(current)) {
        if (isVisited(next)) {
            continue;
        }

        markVisited(next);
        pending.push(next);
    }
}
```

这里有一条很重要的顺序：**先标记已访问，再入队**。若等到出队时才标记，同一个节点可能被多个前驱反复加入队列，既浪费空间，也可能破坏距离计算。

### 1. 无权图最短路径

在每条边代价相同的无权图中，BFS 首次到达一个节点时走过的边数就是最短距离。因为队列保证距离较小的节点总会先于距离较大的节点展开。

```cpp
#include <queue>
#include <vector>

std::vector<int> shortestDistance(
    const std::vector<std::vector<int>>& graph, int start
) {
    const int n = static_cast<int>(graph.size());
    std::vector<int> distance(n, -1);
    std::queue<int> pending;

    distance[start] = 0;
    pending.push(start);

    while (!pending.empty()) {
        const int current = pending.front();
        pending.pop();

        for (const int next : graph[current]) {
            if (distance[next] != -1) {
                continue;
            }

            distance[next] = distance[current] + 1;
            pending.push(next);
        }
    }

    return distance;
}
```

若图有 `V` 个顶点、`E` 条边，邻接表表示下的时间复杂度是 `O(V + E)`：每个顶点至多入队一次，每条边至多检查一次或两次。额外空间为 `O(V)`，来自距离数组和最坏情况下的队列。

## 四、空队列、引用失效与类型细节

### 1. 不能对空队列调用 `front()`、`back()` 或 `pop()`

下面的代码具有未定义行为：

```cpp
std::queue<int> values;
int value = values.front();  // 错误：队列为空
```

标准库并不会为每次访问自动抛出异常。调用前由程序保证非空：

```cpp
if (!values.empty()) {
    int value = values.front();
    values.pop();
}
```

在上面的遍历模板中，`while (!nodes.empty())` 保证了每次内层取队头时至少有一个元素；不要在看似“更安全”的包装代码里把这种基本前提丢掉。

### 2. `front()` 返回的是引用

对 `std::queue<T>`，`front()` 返回 `T&`，常量队列上返回 `const T&`。因此下面的引用在 `pop()` 后悬空：

```cpp
const std::string& name = names.front();
names.pop();
use(name);  // 错误：name 已不再引用有效队头元素
```

如果删除后还要使用值，应先复制或移动到局部变量：

```cpp
std::string name = std::move(names.front());
names.pop();
use(name);
```

对树节点指针而言，`TreeNode* node = nodes.front()` 复制的是指针值；`pop()` 删除的是队列里的指针，不会删除指针指向的树节点。因此只要树本身仍存活，`node` 可以继续使用。不要把“队列元素被删掉”误解为“节点对象被释放”。

### 3. `size()` 返回 `std::size_t`

`queue::size()` 的类型是无符号的 `std::size_t`。在线题中常用 `int i`，可在确认容器大小不超过 `int` 表示范围时转换一次：

```cpp
const int level_size = static_cast<int>(nodes.size());
```

或者让循环变量使用 `std::size_t`：

```cpp
const std::size_t level_size = nodes.size();
for (std::size_t i = 0; i < level_size; ++i) {
    // ...
}
```

二者都可以。应避免无意地混合有符号和无符号比较，尤其不要把可能为负的数直接转换为 `size_t` 后再参与边界计算。

## 五、`queue`、`deque`、`stack` 与 `priority_queue` 怎么区分

这些名字都和“在端点取放元素”有关，但取元素的规则不同：

| 类型 | 取出规则 | 常见操作 | 典型场景 |
| ---- | -------- | -------- | -------- |
| `queue` | 先进先出 | `front`、`push`、`pop` | BFS、排队任务 |
| `stack` | 后进先出 | `top`、`push`、`pop` | 括号匹配、回溯、DFS |
| `deque` | 两端都可操作 | `push_front`、`push_back` | 单调队列、滑动窗口 |
| `priority_queue` | 优先级最高者先出 | `top`、`push`、`pop` | Top K、Dijkstra、调度 |

若题意是“按到达顺序处理”，选 `queue`；若题意是“最近放入的先处理”，选 `stack`；若题意是“当前最小/最大优先”，选 `priority_queue`。不要只因为它们都有 `push` 与 `pop` 就随便替换，取出顺序才是数据结构的灵魂。

## 六、总结

- `std::queue` 表示 FIFO 队列：尾部 `push`，队头 `front` 后 `pop`。
- 它位于 `<queue>`，是限制接口的容器适配器，默认以 `std::deque` 为底层容器。
- 层序遍历在每层开始时保存 `queue.size()`，才能把当前层与新加入的下一层节点隔开。
- `pop()` 不返回元素；正确顺序是先取 `front()`，再 `pop()`。
- `front()`、`back()`、`pop()` 的前提都是队列非空；`front()` 得到的引用不能在 `pop()` 后继续使用。
- BFS 的关键不变量是：节点按发现顺序入队，按入队顺序出队；无权图中首次发现节点即可确定最短边数。
- `result.emplace_back()` 可直接在外层 `vector` 末尾构造一个空内层 `vector`，是 `push_back(vector<int>())` 的更直接表达。

当你需要的是“公平地按先后顺序处理工作”，`queue` 不只是一个可选容器，而是让代码结构和问题规则一致的工具。至于要不要用它之外的结构，先问自己：下一个该处理的元素，究竟由什么规则决定。这个问题的答案比容器名字更可靠。
