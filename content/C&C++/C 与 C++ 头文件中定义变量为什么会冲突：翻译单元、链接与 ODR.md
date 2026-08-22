+++
date = '2026-08-23T01:35:00+08:00'
draft = false
title = 'C 与 C++ 头文件中定义变量为什么会冲突：翻译单元、链接与 ODR'
+++

刚开始写 C/C++ 多文件项目时，很容易写出这样的代码：

```cpp
// config.hpp

#ifndef CONFIG_HPP
#define CONFIG_HPP

int global_count = 0;

#endif
```

然后在多个 `.cpp` 文件中包含它：

```cpp
// main.cpp

#include "config.hpp"

int main() {
    ++global_count;
    return 0;
}
```

```cpp
// worker.cpp

#include "config.hpp"

void work() {
    ++global_count;
}
```

编译链接时可能会报错：

```text
multiple definition of `global_count'
```

很多人第一次看到这个错误时会觉得奇怪：

**这个变量不是在各自的 `.cpp` 文件里各有一份吗？既然各自唯一，为什么会冲突？**

这个问题问得很好。只是答案稍微冷淡一点：你以为它们“各自唯一”，但链接器看到的是多个具有外部链接性的同名定义。C/C++ 不会因为你觉得它们应该和平相处，就替你重新解释规则。

这篇文章专门把这个问题讲清楚。

## 一、先给结论

头文件里写：

```cpp
int global_count = 0;
```

这不是声明，而是 **定义**。

如果这个头文件被多个 `.cpp` 包含，那么每个 `.cpp` 在预处理后都会得到一份：

```cpp
int global_count = 0;
```

于是整个程序中会出现多个 `global_count` 的定义。

而普通全局变量默认具有 **外部链接性**，也就是它会导出一个能被其他翻译单元链接到的符号。多个 `.cpp` 都导出了同名的 `global_count`，链接器就会发现：

```text
main.o   里有一个 global_count 定义
worker.o 里也有一个 global_count 定义
```

它无法接受同一个程序里有多个外部定义，于是报 `multiple definition`。

核心知识点是：

- `#include` 是文本包含
- 每个 `.c` / `.cpp` 会形成一个翻译单元
- 声明和定义不是一回事
- 全局变量默认具有外部链接性
- 链接器会合并多个目标文件
- C++ 有 ODR，也就是 One Definition Rule
- `extern`、`static`、`inline` 变量会改变问题的性质

一个问题能牵出这么多概念，也算它相当会给初学者添麻烦了。

## 二、include 不是模块导入

在 C/C++ 中：

```cpp
#include "config.hpp"
```

不是“导入一个模块”，而是把 `config.hpp` 的内容复制到当前位置。

也就是说：

```cpp
// main.cpp

#include "config.hpp"

int main() {
    ++global_count;
    return 0;
}
```

预处理后大致会变成：

```cpp
// main.cpp 预处理后，简化理解

int global_count = 0;

int main() {
    ++global_count;
    return 0;
}
```

另一个文件：

```cpp
// worker.cpp

#include "config.hpp"

void work() {
    ++global_count;
}
```

预处理后大致会变成：

```cpp
// worker.cpp 预处理后，简化理解

int global_count = 0;

void work() {
    ++global_count;
}
```

所以问题不是“头文件被共享了一次”，而是“头文件内容被复制进了每一个包含它的源文件”。

## 三、翻译单元是什么

C/C++ 的编译不是把所有 `.cpp` 一起揉成一个大文件处理。

通常每个 `.cpp` 会单独经过：

```text
预处理
编译
汇编
```

生成自己的目标文件：

```text
main.cpp   -> main.o
worker.cpp -> worker.o
```

每个源文件经过预处理后形成的完整输入，叫做 **翻译单元**。

可以粗略理解成：

```text
一个 .cpp + 它包含进来的所有头文件内容 = 一个翻译单元
```

例如：

```text
main.cpp + config.hpp   -> main 翻译单元 -> main.o
worker.cpp + config.hpp -> worker 翻译单元 -> worker.o
```

在编译阶段，编译器一次通常只看一个翻译单元。

所以从 `main.cpp` 的编译视角看：

```cpp
int global_count = 0;
```

确实只有一个。

从 `worker.cpp` 的编译视角看：

```cpp
int global_count = 0;
```

也确实只有一个。

问题出在后面的链接阶段。

## 四、链接器看到的不是一个 cpp

编译完成后，链接器会把多个目标文件合成一个可执行文件：

```text
main.o + worker.o + 标准库 -> app
```

这时它会看到：

```text
main.o:
  定义了 global_count
  定义了 main

worker.o:
  定义了 global_count
  定义了 work
```

`main` 和 `work` 名字不同，没问题。

但 `global_count` 出现了两次，而且都是外部可见的定义。于是链接器就会报错。

这就是“各自 `.cpp` 中唯一”和“整个程序中冲突”的区别：

| 视角 | 看到什么 |
| ---- | -------- |
| 编译器处理 `main.cpp` | 一个 `global_count` |
| 编译器处理 `worker.cpp` | 一个 `global_count` |
| 链接器处理整个程序 | 两个外部定义的 `global_count` |

编译器觉得每个房间都只坐了一个人，链接器进大厅一看，两个人拿着同一张身份证。问题当然就出现了。

## 五、声明和定义

要理解这个问题，必须区分声明和定义。

声明告诉编译器：这个名字存在。

定义不仅告诉编译器名字存在，还真正创建实体。

变量声明：

```cpp
extern int global_count;
```

含义是：

```text
有一个 int 类型的 global_count，它的定义在别处。
```

变量定义：

```cpp
int global_count = 0;
```

含义是：

```text
创建一个 int 类型的 global_count，并初始化为 0。
```

即使不写初始化：

```cpp
int global_count;
```

在命名空间作用域或文件作用域下，它通常也是定义。不要因为它没有 `= 0` 就以为它只是声明。C/C++ 在这种地方并不会因为你少写几个字符就变得温柔。

函数也类似：

```cpp
int add(int a, int b);
```

这是函数声明。

```cpp
int add(int a, int b) {
    return a + b;
}
```

这是函数定义。

头文件中最适合放的是声明，而不是普通全局变量定义。

## 六、正确写法：头文件 extern，源文件定义

如果你想让整个程序共享同一个全局变量，推荐写法是：

```cpp
// config.hpp

#ifndef CONFIG_HPP
#define CONFIG_HPP

extern int global_count;

#endif
```

然后在一个 `.cpp` 文件中提供唯一的定义：

```cpp
// config.cpp

#include "config.hpp"

int global_count = 0;
```

其他 `.cpp` 只需要包含头文件：

```cpp
// main.cpp

#include "config.hpp"

int main() {
    ++global_count;
    return 0;
}
```

```cpp
// worker.cpp

#include "config.hpp"

void work() {
    ++global_count;
}
```

这样整个程序中只有一个定义：

```text
config.o:
  定义 global_count

main.o:
  引用 global_count

worker.o:
  引用 global_count
```

链接器会把 `main.o` 和 `worker.o` 中对 `global_count` 的引用，解析到 `config.o` 中的那一个定义。

这才是“整个程序共享一个变量”的典型写法。

## 七、extern 不是定义吗

这一点很容易混：

```cpp
extern int global_count;
```

是声明，不是定义。

但下面这个通常是定义：

```cpp
extern int global_count = 0;
```

因为它带了初始化。

可以这样理解：

| 写法 | 含义 |
| ---- | ---- |
| `extern int x;` | 声明，定义在别处 |
| `int x;` | 定义 |
| `int x = 0;` | 定义 |
| `extern int x = 0;` | 定义，而且显式外部链接 |

所以不要在头文件里写：

```cpp
extern int global_count = 0;
```

它并不会因为有 `extern` 就变得安全。初始化已经把它变成定义了。

## 八、头文件保护宏为什么没用

很多人会问：

```cpp
#ifndef CONFIG_HPP
#define CONFIG_HPP

int global_count = 0;

#endif
```

不是已经有头文件保护宏了吗？为什么还会多重定义？

原因是：**头文件保护宏只能防止同一个翻译单元内重复包含，不能防止多个翻译单元分别包含。**

例如一个文件里这样写：

```cpp
#include "config.hpp"
#include "config.hpp"
```

头文件保护宏可以保证 `config.hpp` 的内容只在当前 `.cpp` 中出现一次。

但如果有两个源文件：

```text
main.cpp   include config.hpp
worker.cpp include config.hpp
```

它们是两个不同的翻译单元。每个翻译单元都会各自处理一遍头文件保护宏。

可以粗略理解成：

```text
main.cpp:
  CONFIG_HPP 没定义 -> 放入 int global_count = 0 -> 定义 CONFIG_HPP

worker.cpp:
  CONFIG_HPP 没定义 -> 放入 int global_count = 0 -> 定义 CONFIG_HPP
```

宏的状态不会跨 `.cpp` 文件共享。

所以头文件保护宏解决的是：

```text
同一个 .cpp 中重复 include
```

解决不了：

```text
多个 .cpp 都 include 同一个头文件
```

## 九、外部链接性是什么

文件作用域或命名空间作用域下的普通全局变量通常具有 **外部链接性**。

例如：

```cpp
int global_count = 0;
```

这个名字不只在当前 `.cpp` 内部可见。它会成为一个外部符号，可以被其他目标文件引用。

这意味着整个程序层面通常只能有一个这样的定义。

如果多个翻译单元都定义了同名外部符号：

```text
main.o:
  global_count

worker.o:
  global_count
```

链接器就会冲突。

这和局部变量完全不同。

例如：

```cpp
void f() {
    int count = 0;
}
```

这个 `count` 是局部变量，没有外部链接性。另一个函数里也可以有自己的 `count`：

```cpp
void g() {
    int count = 0;
}
```

它们不会冲突，因为它们不是外部符号，也不需要在链接阶段被当成同一个全局名字处理。

## 十、static：每个翻译单元一份

如果你真的希望每个 `.cpp` 都有自己独立的一份变量，可以在头文件里写 `static`：

```cpp
// config.hpp

#ifndef CONFIG_HPP
#define CONFIG_HPP

static int global_count = 0;

#endif
```

`static` 修饰文件作用域变量时，表示 **内部链接性**。

含义是：

```text
这个变量只属于当前翻译单元，不导出为外部符号。
```

于是：

```text
main.cpp   包含 config.hpp -> main.o   有自己的 global_count
worker.cpp 包含 config.hpp -> worker.o 有自己的 global_count
```

它们名字相同，但都只在各自翻译单元内部可见，链接器不会把它们当成同一个外部符号。

这时不会多重定义，但要注意：这已经不是“全程序共享一个变量”了，而是“每个 `.cpp` 各有一份变量”。

例如：

```cpp
// config.hpp

static int global_count = 0;
```

```cpp
// main.cpp

#include "config.hpp"

void inc_main() {
    ++global_count;
}
```

```cpp
// worker.cpp

#include "config.hpp"

void inc_worker() {
    ++global_count;
}
```

`inc_main` 改的是 `main.cpp` 那一份。

`inc_worker` 改的是 `worker.cpp` 那一份。

如果你以为它们共享同一个变量，那程序行为就会变得很难看懂。不是它复杂，是你给了它两种身份。

## 十一、C++17 inline 变量

C++17 引入了 **inline 变量**，可以安全地在头文件中定义全局变量：

```cpp
// config.hpp

#ifndef CONFIG_HPP
#define CONFIG_HPP

inline int global_count = 0;

#endif
```

这表示允许这个变量定义出现在多个翻译单元中，但它们在整个程序里表示同一个实体。

也就是说：

```text
main.cpp   包含 inline int global_count = 0;
worker.cpp 包含 inline int global_count = 0;
```

链接器会把这些 inline 变量定义合并成一个变量。

这和 `static` 不一样：

| 写法 | 是否冲突 | 是否共享同一份 |
| ---- | -------- | -------------- |
| `int x = 0;` 放头文件 | 冲突 | 不合法 |
| `extern int x;` 头文件 + 一个 `.cpp` 定义 | 不冲突 | 是 |
| `static int x = 0;` 放头文件 | 不冲突 | 否，每个翻译单元一份 |
| `inline int x = 0;` 放头文件 | 不冲突 | 是，C++17 起 |

`inline` 变量很适合头文件库、全局配置对象、常量对象等场景。

但前提是你使用的是 C++17 或更高版本。

## 十二、inline 变量和 inline 函数的关系

很多人听到 `inline` 会想到“建议编译器内联展开函数”。但在 C++ 中，`inline` 还有一个非常重要的含义：

**允许同一个定义出现在多个翻译单元中，只要这些定义完全一致。**

例如头文件里常见的 inline 函数：

```cpp
// math_utils.hpp

inline int add(int a, int b) {
    return a + b;
}
```

这个头文件被多个 `.cpp` 包含不会多重定义，因为 `inline` 函数允许多处定义。

C++17 的 inline 变量把类似能力扩展到了变量：

```cpp
inline int global_count = 0;
```

所以这里的 `inline` 不应该只理解成性能优化提示。它更重要的是链接规则。

## 十三、const 的特殊情况

`const` 变量在 C 和 C++ 中有一个很容易踩的差异。

在 C++ 中，命名空间作用域下的非 `extern` `const` 变量默认具有内部链接性：

```cpp
// constants.hpp

const int max_size = 100;
```

如果这个头文件被多个 `.cpp` 包含，通常不会产生多重定义。因为每个翻译单元都有自己的一份 `max_size`，它不是外部符号。

但这也意味着它不一定是全程序共享的同一个对象。

如果你只是把它当编译期常量使用，这通常没问题：

```cpp
int buffer[max_size];
```

如果你在意它的地址是否全程序唯一，那就要小心。

C++17 之后，更推荐写：

```cpp
inline constexpr int max_size = 100;
```

这样它可以放在头文件里，并且作为 inline 变量遵守相应规则。

在 C 中，文件作用域 `const` 默认仍然具有外部链接性：

```c
// constants.h

const int max_size = 100;
```

如果被多个 `.c` 包含，可能导致多重定义。

C 中更稳妥的写法是：

```c
// constants.h

extern const int max_size;
```

然后在一个 `.c` 文件中定义：

```c
// constants.c

#include "constants.h"

const int max_size = 100;
```

如果只是整数常量，C 中也常见使用宏或枚举：

```c
#define MAX_SIZE 100
```

或者：

```c
enum {
    MAX_SIZE = 100
};
```

宏没有类型，枚举常量只能表达整数值。选择哪种方式，要看场景。总之，不要以为 C 和 C++ 的 `const` 行为完全一样。它们只是长得像，并不保证性格一致。

## 十四、C 语言里的 tentative definition

C 语言中还有一个概念叫 **tentative definition**，也就是暂定定义。

例如文件作用域：

```c
int global_count;
```

在 C 里是暂定定义。如果同一个翻译单元后面没有真正的定义，它会被当作：

```c
int global_count = 0;
```

如果你把它放进头文件：

```c
// config.h

int global_count;
```

再被多个 `.c` 包含，就会在多个翻译单元中都产生外部定义。

旧工具链有时会因为 common symbol 机制让这种写法侥幸链接通过。但这不是值得依赖的好习惯。现代 GCC 默认使用 `-fno-common` 后，这类代码更容易直接报多重定义。

正确写法仍然是：

```c
// config.h

extern int global_count;
```

```c
// config.c

#include "config.h"

int global_count;
```

这才清楚。

## 十五、namespace 不能解决这个问题

C++ 里有人会这样写：

```cpp
// config.hpp

namespace config {
    int global_count = 0;
}
```

这依然是定义。

如果多个 `.cpp` 包含这个头文件，就会产生多个：

```cpp
config::global_count
```

链接时仍然可能多重定义。

命名空间只是改变名字所在的作用域，并不会自动让变量变成“每个 `.cpp` 私有”或“全程序唯一共享”。

正确写法之一：

```cpp
// config.hpp

namespace config {
    extern int global_count;
}
```

```cpp
// config.cpp

#include "config.hpp"

namespace config {
    int global_count = 0;
}
```

C++17 起也可以：

```cpp
// config.hpp

namespace config {
    inline int global_count = 0;
}
```

## 十六、类中的 static 成员变量

类里的 `static` 成员变量也有类似问题。

例如：

```cpp
// Counter.hpp

class Counter {
public:
    static int value;
};
```

这只是声明，不是定义。

在 C++17 之前，通常需要在一个 `.cpp` 中定义：

```cpp
// Counter.cpp

#include "Counter.hpp"

int Counter::value = 0;
```

如果你把定义写进头文件：

```cpp
// Counter.hpp

class Counter {
public:
    static int value;
};

int Counter::value = 0;
```

多个 `.cpp` 包含后，也会多重定义。

C++17 起可以写 inline static 成员：

```cpp
// Counter.hpp

class Counter {
public:
    inline static int value = 0;
};
```

这就可以放在头文件中。

## 十七、ODR 是什么

ODR 是 One Definition Rule，通常翻译为 **单一定义规则**。

C++ 中大致要求：

- 一个翻译单元内，任何变量、函数、类类型等不能有冲突的重复定义
- 整个程序中，具有外部链接性的普通变量和普通函数通常只能有一个定义
- 某些实体允许多个定义，例如类定义、模板定义、inline 函数、inline 变量，但这些定义必须一致

例如类定义通常放在头文件里：

```cpp
// Student.hpp

class Student {
public:
    int id;
    int age;
};
```

多个 `.cpp` 包含它不会出问题，因为类型定义允许在多个翻译单元中出现，只要内容一致。

函数声明也可以放头文件：

```cpp
void print_student(const Student& student);
```

因为它只是声明。

普通函数定义不加 `inline` 放头文件会出问题：

```cpp
// math_utils.hpp

int add(int a, int b) {
    return a + b;
}
```

多个 `.cpp` 包含后，会产生多个 `add` 定义。

正确方式之一是加 `inline`：

```cpp
// math_utils.hpp

inline int add(int a, int b) {
    return a + b;
}
```

变量也是同理。普通变量定义不能随便放头文件，C++17 起的 inline 变量除外。

## 十八、作用域、链接性、存储期不要混在一起

这个问题容易让人混淆三个概念：

| 概念 | 问的问题 |
| ---- | -------- |
| 作用域 | 这个名字在源码的哪里可见 |
| 链接性 | 这个名字在不同翻译单元之间是否表示同一个实体 |
| 存储期 | 这个对象什么时候创建、什么时候销毁 |

例如：

```cpp
int global_count = 0;
```

它在命名空间作用域：

```text
作用域：从声明点开始，在当前命名空间内可见
链接性：默认外部链接
存储期：静态存储期，程序启动前后创建，程序结束时销毁
```

而：

```cpp
static int global_count = 0;
```

它仍然有静态存储期，但链接性变成内部链接：

```text
作用域：当前文件中从声明点开始可见
链接性：内部链接
存储期：静态存储期
```

所以 `static` 并不是“让变量生命周期变长”这么简单。放在不同位置，它的含义不同。

局部静态变量：

```cpp
void f() {
    static int count = 0;
    ++count;
}
```

这里的 `count`：

```text
作用域：只在函数 f 内可见
链接性：无链接
存储期：静态存储期
```

它不会导致头文件全局变量那种链接冲突，因为它不是一个外部符号。

## 十九、应该如何选择写法

如果你想让全程序共享一个变量：

```cpp
// config.hpp
extern int global_count;
```

```cpp
// config.cpp
int global_count = 0;
```

这是最传统、最清楚的写法。

如果你使用 C++17 或更高，并且希望变量直接定义在头文件中：

```cpp
// config.hpp
inline int global_count = 0;
```

这是现代 C++ 可用的写法。

如果你希望每个 `.cpp` 都有独立的一份：

```cpp
// config.hpp
static int global_count = 0;
```

可以这么写，但要明确它们不是同一个变量。

如果只是常量：

```cpp
// C++17+
inline constexpr int max_size = 100;
```

通常很适合放在头文件里。

如果是 C 项目中的共享全局变量：

```c
// config.h
extern int global_count;
```

```c
// config.c
int global_count = 0;
```

不要把普通变量定义直接写进头文件。

## 二十、一个完整示例

推荐目录结构：

```text
project/
  include/
    config.hpp
  src/
    config.cpp
    main.cpp
    worker.cpp
```

`include/config.hpp`：

```cpp
#ifndef CONFIG_HPP
#define CONFIG_HPP

extern int global_count;

#endif
```

`src/config.cpp`：

```cpp
#include "config.hpp"

int global_count = 0;
```

`src/worker.cpp`：

```cpp
#include "config.hpp"

void work() {
    ++global_count;
}
```

`src/main.cpp`：

```cpp
#include "config.hpp"

void work();

int main() {
    ++global_count;
    work();
    return global_count;
}
```

编译：

```bash
g++ -Iinclude src/main.cpp src/worker.cpp src/config.cpp -o app
```

这里必须把 `src/config.cpp` 也参与编译链接。否则会变成另一种错误：

```text
undefined reference to `global_count'
```

因为头文件里的 `extern int global_count;` 只是声明，它承诺“别处有定义”。如果你没有把真正定义所在的 `.cpp` 链接进来，链接器当然找不到。

## 二十一、常见错误对照

### multiple definition

头文件中写了变量定义：

```cpp
// config.hpp
int global_count = 0;
```

多个 `.cpp` 包含后报：

```text
multiple definition of `global_count'
```

解决：

```cpp
// config.hpp
extern int global_count;
```

```cpp
// config.cpp
int global_count = 0;
```

或者 C++17：

```cpp
// config.hpp
inline int global_count = 0;
```

### undefined reference

头文件中只有声明：

```cpp
// config.hpp
extern int global_count;
```

但没有任何 `.cpp` 定义它，或者定义所在 `.cpp` 没参与链接，就会报：

```text
undefined reference to `global_count'
```

解决：提供一个定义，并参与构建。

### 每个文件都有一份，结果状态不共享

头文件中写：

```cpp
static int global_count = 0;
```

不会多重定义，但每个翻译单元都有一份。

如果你希望所有 `.cpp` 共享同一个计数器，这不是正确写法。

## 二十二、总结

头文件中定义普通全局变量会冲突，是因为 `#include` 会把定义复制进每个包含它的 `.cpp`。每个 `.cpp` 单独编译时确实各自只有一个变量定义，但链接器最终要把所有目标文件合成一个程序。

如果这个变量具有外部链接性，那么多个目标文件中出现同名定义，就违反了整个程序层面的规则。

最重要的判断方式是：

```text
头文件里的是声明，还是定义？
这个名字有没有外部链接性？
我想要全程序共享一份，还是每个翻译单元一份？
```

对应选择：

| 需求 | 推荐写法 |
| ---- | -------- |
| 全程序共享一个变量，C/C++ 通用 | 头文件 `extern` 声明，一个源文件定义 |
| C++17 起头文件中定义共享变量 | `inline` 变量 |
| 每个 `.cpp` 独立一份 | `static` 变量或内部链接 |
| C++17 起头文件常量 | `inline constexpr` |

所以，那个变量并不是“在各自 `.cpp` 中唯一就没事”。它在编译阶段看起来各自唯一，在链接阶段却都以同一个外部名字出现。链接器不负责理解你的心理预期，它只负责执行规则。

而这正是 C/C++ 多文件工程必须掌握的知识点：**翻译单元、链接性、声明与定义、以及 ODR。**
