+++
date = '2026-08-28T10:05:00+08:00'
draft = false
title = 'C 与 C++ 的 extern：声明、定义、链接与跨语言接口'
+++

`extern` 最常被解释为“在别处定义”。这句话方向没错，却不足以指导实际工程：什么叫“别处”？为什么有的 `extern` 只是声明，有的却仍然是定义？为什么 C++ 的 `const`、头文件变量和 `extern "C"` 又让问题复杂起来？

核心只有一句：`extern` 通常用于声明一个具有**外部链接**的实体，使多个翻译单元能引用同一份定义。它不负责创建存储，更不负责替你组织接口；声明、定义、预处理和链接器各有各的工作，混在一起只会制造重复定义或未定义引用。

```text
头文件：声明“有这样一个实体，类型和名字是这个”
源文件：定义“实体就在这里，程序中应有这一份”
链接器：把所有翻译单元对该外部实体的引用接到同一份定义
```

## 一、先建立翻译单元与链接属性的概念

一个 `.c`/`.cpp` 文件在 `#include` 和宏展开后的结果，称为**翻译单元**（translation unit）。各翻译单元先独立编译，再由链接器组合为可执行文件或库。

因此，声明某个名字时至少应区分：

| 概念 | 问题 | 示例 |
| --- | --- | --- |
| 声明（declaration） | 编译器是否已知实体的名字和类型？ | `extern int timeout;` |
| 定义（definition） | 是否真正提供实体，或函数实现？ | `int timeout = 30;` |
| 链接属性（linkage） | 其他翻译单元的同名声明能否指向它？ | 外部链接、内部链接、无链接 |
| 作用域（scope） | 名字能在当前源码的何处直接使用？ | 块、文件、命名空间、类 |

`extern` 主要涉及“声明”和“外部链接”，不是存储期关键字。一个文件作用域变量即使不写 `extern` 也可具有静态存储期；反过来，写了 `extern` 也不意味着它在此处得到存储。

## 二、最常见的组织方式：头文件声明，单个源文件定义

```cpp
// config.h
#pragma once

extern int global_timeout;

// config.cpp
#include "config.h"

int global_timeout = 30;

// main.cpp
#include "config.h"

void run() {
    global_timeout = 10;
}
```

`config.h` 的 `extern int global_timeout;` 通常只是声明：它告诉每个包含者“存在一个这种类型、这种名字的对象”。`config.cpp` 中带初始化器的 `int global_timeout = 30;` 提供定义和存储。链接器将 `main.cpp` 中对该名字的使用解析到这个定义。

```text
config.h    -> 可重复包含的接口声明
config.cpp  -> 程序中唯一的对象定义
main.cpp    -> 包含接口后使用同一个对象
```

源文件中的定义也应包含自己的头文件。如此一来，若头文件将 `int` 改成 `long`、移入命名空间或添加限定符，定义文件会立即接受同一份声明检查，而不是悄悄和接口分叉。

## 三、声明与定义：四种写法必须分清

```cpp
extern int count;      // 声明；定义应在其他某处出现
int count;             // 定义；零初始化
int count = 0;         // 定义；显式初始化
extern int count = 0;  // 仍是定义：初始化器使它定义对象
```

最后一行最容易制造事故。下面的头文件并非“带默认值的声明”：

```cpp
// bad_config.h
extern int global_timeout = 30; // 定义，不只是声明
```

每个包含它的翻译单元都会产生一个外部定义，最终通常导致多重定义链接错误。在 C++ 中，这也会违反单一定义规则（ODR）。正确的传统布局仍然是：

```cpp
// config.h
extern int global_timeout;

// config.cpp
int global_timeout = 30;
```

### 1. “暂定定义”不是可依赖的头文件技巧

在 C 中，文件作用域的 `int count;` 涉及历史上的暂定定义（tentative definition）规则；不同编译器和构建选项也曾对多个此类定义的合并方式有所差异。无论这些细节如何，头文件中放置非 `extern` 的全局变量定义都不是可靠的接口设计。

若它应被共享：头文件写 `extern` 声明，恰好一个 `.c` 定义。若它不应被共享：放入一个源文件，并用文件作用域 `static` 隐藏。别把链接器曾经宽容的行为当成语言接口。

### 2. 函数的情形

普通文件/命名空间作用域函数默认通常具有外部链接：

```cpp
int add(int left, int right) {
    return left + right;
}
```

这类函数声明前写 `extern` 合法，却通常没有额外意义：

```cpp
extern int add(int left, int right);
```

项目代码一般直接把函数声明放在头文件即可。若函数只服务于当前 `.c/.cpp`，C 使用文件作用域 `static`，C++ 可使用 `static` 或匿名命名空间，而不是期待 `extern` 提供某种访问控制。

## 四、常量、`inline` 变量与头文件：C++ 的额外规则

### 1. `const` 的默认链接属性

在 C++ 中，命名空间作用域的非 `volatile` `const` 对象默认具有内部链接，除非已有外部链接声明或另有规则：

```cpp
// constants.cpp
const int default_timeout = 30; // 默认内部链接
```

若它需要被多个翻译单元共享，应在头文件作外部声明：

```cpp
// constants.h
extern const int default_timeout;

// constants.cpp
#include "constants.h"
const int default_timeout = 30;
```

前面的声明使定义具有外部链接。定义处也可以写 `extern const int default_timeout = 30;`，但将声明放进头、定义放进源文件通常更清晰。

这一点不能不加区分地搬到 C：C 与 C++ 对文件作用域 `const` 的默认链接规则不同。编写同时被两种语言包含的头文件时，应有意设计声明和定义位置，而不是依赖读者对某个默认规则的记忆。

### 2. C++17 的内联变量

若确实希望在头文件中定义一个全程序共享的 C++ 变量，C++17 起可使用 `inline` 变量：

```cpp
// constants.h
inline constexpr int default_timeout = 30;

inline std::atomic<int> active_connections{0};
```

`inline` 在这里的含义不是“强制内联一段指令”，而是允许同一定义出现在多个翻译单元中，并使它们表示同一个实体。它适用于有意的头文件定义；不要把它和头文件 `static` 混为一谈——后者通常是每个翻译单元一份实体。

### 3. 模板与 `constexpr` 函数

C++ 模板的完整定义通常必须放在头文件，因为编译器需要在使用点实例化它。`constexpr` 函数和类内定义的成员函数也常放在头文件，并具有适合多翻译单元包含的规则。这些并不是“所有实现都可以塞进头文件”的通行证；普通非 `inline` 函数和变量仍应遵守相应的 ODR 与链接规则。

## 五、`extern "C"`：语言链接，不是“定义在别处”

C++ 中还常见：

```cpp
extern "C" int c_library_sum(int left, int right);
```

这里的 `"C"` 指定**语言链接**（language linkage）。它通常要求 C++ 编译器以与 C ABI 兼容的方式处理名称修饰和调用约定，从而让 C++ 调用 C 库，或让 C 调用某个 C++ 导出函数。

可供 C 和 C++ 共同包含的头文件常这样写：

```c
#ifdef __cplusplus
extern "C" {
#endif

int c_library_sum(int left, int right);

#ifdef __cplusplus
}
#endif
```

它和普通的 `extern int value;` 有关联，却不是同一个教学重点：

- 普通 `extern` 主要表达外部链接的声明。
- `extern "C"` 主要指定语言链接与 ABI 约定。

`extern "C"` 不会把 C++ 类、函数重载、异常或标准库类型自动变成 C 接口。跨语言 API 应使用稳定的 C 兼容类型、明确的所有权规则和错误处理约定；写上两个引号并不能让 ABI 兼容性从天而降。

## 六、常见链接错误，按症状定位

### 1. `undefined reference` / unresolved external

编译器接受了声明，但链接器找不到定义。常见原因是：

- 只写了 `extern` 声明，却从未提供定义；
- 定义所在 `.c/.cpp` 没有加入构建目标；
- C++ 名字修饰与 C 库符号不匹配，漏写或误写 `extern "C"`；
- 声明和定义的命名空间、签名、`const` 限定或导出属性不同。

检查顺序应是：先确认正式头文件中的声明，再确认唯一的定义实际参与构建，最后检查链接命令和符号名称。不要先在某个调用点随手再写一条 `extern`，那只会掩盖接口没有被正确包含的问题。

### 2. multiple definition / duplicate symbol

同一个外部实体在多个翻译单元被定义。典型原因：

```cpp
// bad.h
int global_timeout = 30;
```

每个包含 `bad.h` 的 `.cpp` 都生成定义。改成 `static int` 虽能消除多重定义，却会制造每个翻译单元独立的状态；这不是共享变量的修复方案。应根据真正意图选择：

```text
唯一共享对象 -> extern 声明 + 一个源文件定义
有意头文件共享对象（C++17+） -> inline 变量
每个翻译单元独立对象 -> static（并明确这是所需语义）
```

### 3. 手写 `extern` 代替正式头文件

在某个 `.cpp` 临时写：

```cpp
extern int global_timeout;
```

或许能通过当前构建，但它可能与真实接口的命名空间、类型、`const`、导出属性或初始化约束不一致。应包含声明该实体的正式头文件，让定义和所有使用者共享一份声明；这不是仪式感，而是让编译器替你持续检查接口一致性。

## 七、选择速查表

| 需求 | 合适的方式 | 不要误用 |
| --- | --- | --- |
| 多个翻译单元共享一个可变变量 | 头文件 `extern` 声明 + 一个源文件定义 | 头文件普通变量定义 |
| 多个翻译单元使用普通函数 | 头文件函数声明 + 一个源文件定义 | 在每个调用点手写声明 |
| 头文件定义一个全程序唯一的 C++17 变量 | `inline` 变量 | 以 `static` 冒充共享对象 |
| 只让当前源文件使用实体 | 文件作用域 `static`；C++ 匿名命名空间 | `extern` |
| 调用 C 库或导出 C ABI | `extern "C"` + C 兼容接口设计 | 以为它自动处理所有 ABI 问题 |

## 八、总结

`extern` 的边界其实很明确：

```text
extern 声明：此处知道实体存在，并引用外部链接的那一份
定义：此处真正提供对象存储或函数实现
链接：将各翻译单元的声明和引用解析到定义
```

记住三条即可避开大多数事故：

- 变量共享的传统结构是“头文件声明、一个源文件定义”；带初始化器的 `extern` 仍可能是定义。
- `extern` 不能替代头文件，也不能替代把定义文件加入构建系统。
- `extern "C"` 是语言链接/ABI 工具，不是普通外部变量声明的强化版。

当声明、定义和链接各自回到自己的位置，`extern` 就不再像链接器出错时临时念出的咒语；它只是跨翻译单元接口最朴素的一部分。
