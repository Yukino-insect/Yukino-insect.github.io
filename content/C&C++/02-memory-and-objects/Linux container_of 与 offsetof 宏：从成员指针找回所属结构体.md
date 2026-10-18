+++
date = '2026-09-08T19:02:00+08:00'
draft = false
title = 'Linux container_of 与 offsetof 宏：从成员指针找回所属结构体'
+++

## 一、代码

看一段代码：

```c
#ifndef offsetof
#define offsetof(TYPE, MEMBER) ((size_t)&((TYPE *)0)->MEMBER)
#endif

#define container_of(ptr, type, member) ({                         \
    const typeof(((type *)0)->member) *__mptr = (ptr);             \
    (type *)((char *)__mptr - offsetof(type, member));             \
})
```
是 Linux 内核里极有代表性的一组宏：`offsetof` 计算成员相对结构体开头的偏移，`container_of` 则根据“某个成员的地址”，反推出“包着这个成员的整个结构体的地址”。

它初看相当不像正经 C：把 `0` 转成指针、访问空指针成员、把指针转成 `char *` 再相减，最后还塞进了 `typeof` 与一对花括号。实际上，它背后只有一条朴素的地址关系：**成员地址 = 结构体首地址 + 成员偏移**。既然如此，反过来就是：**结构体首地址 = 成员地址 - 成员偏移**。

不过，“公式正确”不等于“可以在任意 C/C++ 代码里照抄”。图片中的 `container_of` 使用了 GNU C 扩展，服务的是内核这种明确控制编译器、内存布局和对象生命周期的环境。本文会解释每个 token 在做什么，也会划清它在标准 C、GNU C 与 C++ 中的边界。毕竟，底层技巧最容易造成的误解，就是把依赖前提的技巧当成不需要前提的魔法。

不同版本的 Linux 内核会使用更复杂的变体，加入编译期类型检查、`const` 限定传播和更好的诊断；但核心计算就是最后一行。下面先把它的目标说清楚。

## 二、它究竟要解决什么问题

假设一个结构体中嵌入了一个链表节点：

```c
struct list_node {
    struct list_node *prev;
    struct list_node *next;
};

struct task {
    int pid;
    const char *name;
    struct list_node run_queue;
};
```

内核的通用链表只需要操作 `struct list_node`，因此在遍历时拿到的通常是：

```c
struct list_node *node;
```

但业务代码真正关心的是这条节点所属的任务：

```c
struct task *task;
```

如果已知 `node` 实际就是某个 `struct task` 对象里的 `run_queue` 成员，就可以写：

```c
struct task *task = container_of(node, struct task, run_queue);
```

这行不是搜索链表，也没有保存一个隐藏的“父对象指针”；它只是利用结构体的连续布局算回起始地址。

```text
一个真实的 struct task 对象

起始地址 p
┌─────────────────────────────────────────────┐
│ pid │ name │ 对齐填充 │ run_queue            │
└─────────────────────────────────────────────┘
                     ↑                         ↑
                成员偏移 offset              成员地址 m

m = p + offset
p = m - offset
```

例如，在某个具体平台上 `run_queue` 的偏移可能是 `16` 字节。若一个真实 `task` 对象从 `0x1000` 开始，而已知 `node == 0x1010`，那么：

```text
task 起始地址 = 0x1010 - 16 = 0x1000
```

这里的 `16` 不是手写常量，而应由 `offsetof(struct task, run_queue)` 得到；因为字段顺序、指针宽度和对齐规则变化后，手写数字会立刻变成维护事故。

## 三、先理解 `offsetof`：成员离开头有多远

### 1. 标准接口与返回值

`offsetof` 是 C 标准库 `<stddef.h>` 中定义的宏，C++ 的 `<cstddef>` 也提供相应名字。其形式是：

```c
offsetof(type, member)
```

它返回类型 `type` 的成员 `member` 从该对象起始处开始计算的**字节偏移**，结果类型为 `size_t`。

```c
#include <stddef.h>

size_t offset = offsetof(struct task, run_queue);
```

注意，偏移不一定等于前面字段 `sizeof` 的简单相加。编译器可能在成员之间插入填充字节，以满足各成员的对齐要求。让 `offsetof` 询问编译器的实际布局，远比自己心算可靠。

### 2. 图片中的旧式实现如何得到偏移

图片先在 `offsetof` 尚未定义时给出一个回退实现：

```c
#define offsetof(TYPE, MEMBER) ((size_t)&((TYPE *)0)->MEMBER)
```

把它从内到外拆开：

| 片段 | 表面类型/含义 | 它在计算中扮演的角色 |
| --- | --- | --- |
| `0` | 整数常量 | 作为假想的起始地址 |
| `(TYPE *)0` | `TYPE *` 空指针 | “假装有一个从地址 0 开始的 `TYPE`” |
| `((TYPE *)0)->MEMBER` | `TYPE` 的成员表达式 | 描述该成员位于布局中的哪里 |
| `&((TYPE *)0)->MEMBER` | 指向该成员的指针 | 数值上对应成员相对开头的位置 |
| `(size_t)...` | 无符号整数 | 将地址形式的结果保存为字节偏移 |

若 `MEMBER` 在布局中离开头 16 字节，编译器会将这整个表达式视为常量形式的偏移值 `16`。这里的“地址 0”并不表示程序真的创建了一个位于 0 地址的结构体；它只是古老而常见的宏写法，用来让编译器按类型布局计算成员位置。

### 3. 不要把空指针成员访问当成普通运行时操作

下面的普通代码是错误的：

```c
struct task *task = NULL;
int pid = task->pid; // 未定义行为：运行时解引用空指针
```

所以你会自然追问：`&((TYPE *)0)->MEMBER` 难道不也是解引用空指针吗？从抽象语言规则看，手工定义这种宏存在微妙的可移植性问题；许多编译器会把它识别为 `offsetof` 习惯用法或用内建能力实现，但它不应被理解成“访问空指针是安全的”。

实际项目应优先使用标准头文件提供的：

```c
#include <stddef.h>

size_t offset = offsetof(struct task, run_queue);
```

现代 GCC/Clang 通常会把标准 `offsetof` 映射到编译器内建（常见形式为 `__builtin_offsetof`），而不是在运行时生成一次对 0 地址的访问。**`offsetof` 是受支持的布局查询接口；任意空指针解引用不是。** 两者长得相似，语义边界却不能混为一谈。

### 4. `offsetof` 的适用范围

在 C 中，`offsetof` 用于结构体或联合体的成员。不要把它用于位域、不能静态确定位置的概念，或并不存在的成员。

在 C++ 中限制更强：标准 `offsetof` 只对**标准布局（standard-layout）类型**有定义良好的保证。具有虚函数、虚继承、复杂多重继承等的类，不应拿来套这个思路。C++ 对象模型并不是“任何 class 都是一段随你倒推的 C 结构体字节”；在这里保持克制，比写出一个看似聪明的宏更重要。

## 四、`container_of` 的数学核心只有一行

先忽略类型检查与宏语法，`container_of` 的本体是：

```c
(type *)((char *)ptr - offsetof(type, member))
```

设：

```text
base   = 容器结构体起始地址
member = 成员相对起始地址的字节偏移
ptr    = 该成员在一个真实对象中的地址
```

那么：

```text
ptr = base + member
base = ptr - member
```

代码严格对应第二条式子。最终将算出的起始地址转换为 `type *`，调用者便重新得到容器结构体指针。

### 为什么必须先转成 `char *`

指针加减的单位由指向的类型决定。假如：

```c
struct list_node *node;
```

那么：

```c
node - 1
```

表示向前移动 `sizeof(struct list_node)` 个字节，而不是向前移动 1 个字节。`offsetof` 的单位却是字节；这两个单位必须对齐。

`char` 的大小在 C 中恰好定义为一个字节（`sizeof(char) == 1`），所以：

```c
(char *)ptr - 16
```

就是将地址向前移动 16 个字节。再转回 `type *` 后，编译器才知道这个地址应当按完整的 `type` 结构体解释。

```text
错误： (struct list_node *)ptr - 16
      按 16 个 list_node 的大小后退

正确： (char *)ptr - 16
      按 16 个字节后退
```

这就是 `(char *)__mptr` 的必要性，不是无意义的强制类型转换。

## 五、逐行拆解图片中的 `container_of`

再次看完整宏：

```c
#define container_of(ptr, type, member) ({                         \
    const typeof(((type *)0)->member) *__mptr = (ptr);             \
    (type *)((char *)__mptr - offsetof(type, member));             \
})
```

### 1. `#define container_of(ptr, type, member)`

三个参数分别是：

| 参数 | 应传入什么 | 示例 |
| --- | --- | --- |
| `ptr` | 指向某个真实成员对象的指针 | `node` |
| `type` | 外层容器的完整类型名 | `struct task` |
| `member` | 该成员在容器中的成员名 | `run_queue` |

调用：

```c
container_of(node, struct task, run_queue)
```

展开后，最后一行近似为：

```c
(struct task *)((char *)__mptr - offsetof(struct task, run_queue))
```

### 2. `({ ... })`：GNU C 的语句表达式

外层：

```c
({
    /* 语句 */
    /* 最后一个表达式 */
})
```

是 GNU C 扩展，称为**语句表达式**（statement expression）。它允许在一个表达式内部写局部变量与多条语句，并让最后一个表达式成为整体结果。

因此：

```c
struct task *task = container_of(node, struct task, run_queue);
```

中的 `container_of(...)` 最终是一个 `struct task *` 值，而 `__mptr` 只在宏内部可见。若没有 `({ ... })`，宏无法既声明临时变量，又像普通表达式一样产生返回值。

这不是 ISO C 标准语法。GCC 与 Clang 在 GNU C 模式下支持它，Linux 内核也明确以这些工具链为目标；严格 ISO C 项目或 MSVC C 编译环境不能假定它可用。

### 3. `typeof(((type *)0)->member)`：从成员声明推导类型

这一段也是 GNU 扩展：

```c
typeof(((type *)0)->member)
```

它让编译器根据表达式推导出 `member` 的类型。假设：

```c
struct task {
    int pid;
    const char *name;
    struct list_node run_queue;
};
```

那么：

```c
typeof(((struct task *)0)->run_queue)
```

推导为：

```c
struct list_node
```

请注意：这里的表达式是提供给 `typeof` 做**类型推导**的，不会作为普通语句在运行时解引用空指针。它也正是 GNU C 版本能够不手写成员类型的原因。

### 4. `const ... *__mptr = (ptr)`：保存指针并检查类型

替换具体类型后，这一行大致是：

```c
const struct list_node *__mptr = node;
```

它有两个作用。

第一，临时保存 `ptr`，以后地址计算只使用 `__mptr`。因此 `ptr` 在宏中只出现一次，像下面这种带副作用的实参不会被重复求值：

```c
container_of(next_node(), struct task, run_queue);
```

`next_node()` 只会调用一次。尽管如此，可读性与调试性考虑下，仍不建议把有副作用的复杂表达式塞进底层宏调用；先存入局部变量通常更清楚。

第二，它利用赋值的类型规则帮助发现错误。如果 `run_queue` 的类型是 `struct list_node`，你却传进一个 `struct other_node *`，编译器通常会对不兼容指针赋值发出诊断。它不是绝对的安全屏障：显式强制转换仍可绕过检查，某些类型组合也可能需要更严格的内核版本宏来诊断；但至少把明显错误尽早暴露出来。

`const` 让 `__mptr` 指向只读成员视图。这里它主要用于保留输入指针可能携带的只读属性并避免无意经此临时指针修改成员；早期版本的宏对最终容器指针的 `const` 传播并不完美，后文会说明这个限制。

### 5. 最后一行：字节地址减偏移，再转回容器类型

```c
(type *)((char *)__mptr - offsetof(type, member));
```

按执行逻辑可分为四步：

1. `__mptr` 指向真实对象中的 `member`；
2. `(char *)__mptr` 将它视作字节地址；
3. 减去 `offsetof(type, member)`，回到该对象的开头；
4. `(type *)` 将这块起始地址解释成容器结构体指针。

宏的最后一行没有分号，因为它必须作为 `({ ... })` 的最终表达式，把计算出的指针值交给调用处。

## 六、完整示例：侵入式链表为什么需要它

“侵入式”表示通用节点直接嵌入业务对象，而不是额外分配一个节点并在节点里存 `void *data`。下面用一个极简的单链表演示：

```c
#include <stddef.h>
#include <stdio.h>

struct list_node {
    struct list_node *next;
};

struct task {
    int pid;
    const char *name;
    struct list_node run_queue;
};

#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

int main(void) {
    struct task first = { .pid = 101, .name = "compile", .run_queue = {0} };
    struct task second = { .pid = 202, .name = "write", .run_queue = {0} };

    first.run_queue.next = &second.run_queue;

    for (struct list_node *node = &first.run_queue;
         node != NULL;
         node = node->next) {
        struct task *task = container_of(node, struct task, run_queue);
        printf("pid=%d, name=%s\\n", task->pid, task->name);
    }
}
```

输出为：

```text
pid=101, name=compile
pid=202, name=write
```

这里演示宏故意写成了去除 GNU 扩展的教学版本，直接接受 `struct list_node *`；它没有图片版本的 GNU 类型检查。`offsetof` 本身来自标准头文件，但这种“从成员字节地址倒推外层对象”的模式仍应仅用于对象关系与编译器行为都受控的底层 C 代码，不能因为宏写得短就当成任意 ISO C 语境下的通用指针转换。真正的 Linux 内核常把成员嵌入其通用 `struct list_head`，然后用 `container_of` 从链表节点还原宿主对象。这样一个链表算法就无需为每种业务对象重新写一遍，也不必为每个节点增加一个额外的“数据指针”。

### 地址过程再走一遍

以循环中的 `node` 为例：

```text
node
  -> &first.run_queue
  -> first 的起始地址 + offsetof(struct task, run_queue)

container_of(node, struct task, run_queue)
  -> (char *)node - offsetof(struct task, run_queue)
  -> &first
```

所以之后访问：

```c
task->pid
task->name
```

是合法的：`task` 已恢复成原先真实存在的 `struct task` 对象地址，而不是凭空把任意地址伪装成了 `struct task *`。

## 七、必须成立的前提：它不是通用的指针转换

`container_of` 的结果正确，依赖一个很强的事实：`ptr` 必须真的指向某个仍然存活的 `type` 对象中的那个 `member` 成员。换句话说，下面三项缺一不可。

| 前提 | 含义 | 不满足时的后果 |
| --- | --- | --- |
| 类型匹配 | `ptr` 的目标确实是 `type.member` 的类型 | 偏移也许能算，所得对象解释却不成立 |
| 对象归属匹配 | 该成员真的嵌在一个 `type` 对象里 | 会算到无关地址，后续访问是未定义行为 |
| 生命周期有效 | 外层对象尚未释放、离开作用域或复用 | 得到悬空容器指针，后续解引用无效 |

以下写法是错误的：

```c
struct list_node detached = {0};

/* detached 并不属于任何 struct task。 */
struct task *bad = container_of(&detached, struct task, run_queue);
```

宏当然可以做出一个数值地址；但地址算术不会创造一个真实的 `struct task` 对象。对 `bad->pid` 的访问没有合法基础。这一点与把任意整数转换成指针再解引用没有本质区别：语法上能写，语义上不成立。

同样，不能从一个结构体的成员指针，拿另一个结构体类型和一个“碰巧偏移相同”的成员名去反推。当前平台上地址数值碰巧落对位置，不会使程序获得可移植性或正确性。

## 八、`const`、`volatile` 与类型安全的真实边界

### 1. 早期宏可能丢失 `const`

图片中的宏最终固定返回：

```c
(type *)...
```

所以即使输入是：

```c
const struct list_node *node;
```

结果仍是：

```c
struct task *task;
```

这在类型层面丢掉了 `const`。如果原始 `struct task` 对象本来就定义为 `const`，再通过结果写入会产生未定义行为。Linux 内核中常见的较新版本会用 `typeof`、`__same_type` 等机制改进诊断，并提供或建议能保留限定符的用法；无论使用何种宏，调用者都不该借 `container_of` 绕过对象的只读契约。

若接口只需读取，至少让结果也为 `const`：

```c
const struct task *task =
    container_of(node, struct task, run_queue);
```

这不会让错误用法自动消失，但会把“我只读该对象”的意图放回类型系统。

### 2. `volatile` 也不能随手抹去

若成员来自 MMIO 寄存器、原子相关对象或具有 `volatile` 限定的存储，简单的 `(char *)` 与 `(type *)` 转换可能丢失限定符。是否能从这样的成员反推外层对象、反推后能否普通访问，必须由具体 API、平台与内存模型决定。`container_of` 最常用的场景是普通内存中的嵌入节点，不应把它当成处理硬件寄存器或并发同步的工具。

### 3. 类型检查不是内存安全证明

`typeof` 使编译器知道“传入指针的静态类型是否像成员类型”，但它不能证明：

- 指针此刻确实来自某个 `type` 对象；
- 该对象尚未释放；
- 当前线程有同步地访问它；
- 链表节点没有被从一个容器移到另一个容器或遭到破坏。

静态类型是很好的第一道门，却无法替代对象所有权、生命周期和并发协议。内核能安全使用这个模式，不是因为宏无所不能，而是因为周围的数据结构和锁规则共同维持了这些不变量。

## 九、标准 C、GNU C 与 C++：不要混用边界

| 问题 | ISO C | GNU C（图片代码） | C++ |
| --- | --- | --- | --- |
| `offsetof` | `<stddef.h>` 提供的标准接口 | 同样可用，通常有编译器内建 | 仅标准布局类型有可靠保证 |
| `typeof` | 非标准 | GCC/Clang GNU 扩展 | `decltype` 类似但规则不同，不能直接替换 |
| `({ ... })` 语句表达式 | 非标准 | GNU C 扩展 | 不是标准 C++；部分编译器仅作扩展支持 |
| 图片宏能否原样移植 | 不保证 | 可在目标工具链与约定下使用 | 不应直接照搬 |

若你写的是一般 C 项目，优先使用 `<stddef.h>` 的 `offsetof`，并把“从成员找容器”封装在清楚的、受控的模块里。若项目必须以严格 C 标准编译，图片宏中的局部临时变量与类型检查不能原样保留；可以使用一个简单宏，或按具体类型写小函数，但应把前提写在接口文档中。

若你写的是现代 C++ 业务代码，通常更该重新审视设计：`std::list`、模板、回调对象、智能指针或明确的父指针往往比从子对象地址逆推父对象更直接、更可维护。只有在 ABI 兼容、操作系统/驱动、嵌入式或无额外分配的 intrusive container 等确实需要布局控制的场景，才应使用相应的低层模式，并限制在非常小的边界内。

## 十、常见误解与排查清单

### 1. “`container_of` 会遍历或查找容器”

不会。它是常数时间的地址计算，不读取链表内容，也不保存反向索引。前提正确时，计算只相当于一次减法和类型转换。

### 2. “它把任意成员指针都能变成父对象”

不能。只有“该指针确实指向某个真实 `type` 对象中的指定 `member`”时才成立。类型一样、偏移一样、地址看起来合理，都不足以替代对象归属这一事实。

### 3. “`offsetof` 说明可以访问空指针成员”

不说明。标准 `offsetof` 是布局查询；图片中的旧式宏是一种编译器广泛支持的实现习惯。普通运行时表达式中解引用空指针依旧是未定义行为。

### 4. “有 `typeof` 就绝对类型安全”

不绝对。它只能检查静态指针类型是否能赋给成员指针类型，不能证明动态对象身份和生命周期。显式强制类型转换仍能让错误代码通过编译。

### 5. “C++ 中也能用同一宏”

不要这样假设。C++ 的对象模型与标准布局限制更严格，图片宏还依赖 GNU C 扩展。需要侵入式容器时，应使用专为 C++ 设计、明确支持该场景的库或局部实现，并把类型约束写清楚。

## 十一、读到类似宏时的分析顺序

以后看到这类底层宏，不妨按以下顺序拆开：

1. **宏最后产出什么**：是地址、值，还是一条语句？
2. **每个参数的单位是什么**：字节偏移、元素下标，还是实际对象指针？
3. **地址算术在哪个指针类型上进行**：是否需要先转为 `char *`？
4. **类型推导或临时变量做了什么检查**：参数是否重复求值？
5. **对象关系的前提是什么**：指针来自哪个真实对象，生命周期是否仍有效？
6. **使用了哪些编译器扩展**：能否在当前语言模式、编译器与平台上成立？
7. **限定符和并发约束是否保留**：`const`、`volatile`、锁和所有权是否被意外绕过？

顺着这七步，图片中的宏便不再是“神来之笔”，而是一段地址关系十分明确、但使用条件也十分严格的系统代码。

## 总结

- `offsetof(type, member)` 给出成员相对结构体开头的**字节偏移**；应优先使用 `<stddef.h>` 提供的标准版本。
- `container_of(ptr, type, member)` 的核心是 `(char *)ptr - offsetof(type, member)`：由成员地址减去偏移，回到容器起始地址。
- 转为 `char *` 是为了按字节而不是按成员类型大小进行地址计算。
- 图片中的 `typeof` 与 `({ ... })` 分别用于推导成员类型、保存实参并让宏作为表达式返回；它们是 GNU C 扩展，不是 ISO C/C++ 通用语法。
- 该宏只对“真实、匹配、仍存活的容器对象中的指定成员”有效；它不检查对象归属、生命周期、并发安全，也不能把任意地址变成合法对象。
- 在普通应用或 C++ 代码中，应优先选择更直接的类型安全设计；若确需此模式，应把它封装在小范围、约束明确的底层模块中。

所谓 `container_of` 的巧妙，并不在于它违背了 C 的常识，而在于它把结构体布局这条常识倒过来使用：已知枝叶的位置，便能沿着固定偏移回到树干。只是前提是你拿到的确实是这棵树的枝叶；否则，再精确的减法也只会把你带到一块看起来很像地址的陌生地方。
