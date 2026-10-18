+++
date = '2026-08-22T21:50:24+08:00'
draft = false
title = 'C 与 C++ 文件后缀和工程组织：h、hpp、c、cpp 到底怎么分'
+++

C/C++ 项目里常见这些文件：

```text
main.c
main.cpp
student.h
student.hpp
math_utils.cc
vector.hxx
```

刚开始看时很容易困惑：

- `.h` 和 `.hpp` 有什么区别？
- `.c` 和 `.cpp` 是不是只是名字不同？
- C++ 能不能包含 `.h`？
- C 能不能包含 `.hpp`？
- 头文件是不是一定只放声明？
- 为什么有些库只有头文件，没有 `.cpp`？

这些问题没有一个简单到可以只用一句“约定而已”打发。说它们只是约定，没错；但说完就结束，也太不负责任。现实是：**后缀既是工程约定，也会影响编译器和构建系统如何处理文件。**

这篇文章专门梳理 C/C++ 文件后缀和工程组织方式。

## 一、先看常见后缀

常见后缀可以粗略分为两类：

| 后缀 | 常见含义 |
| ---- | -------- |
| `.c` | C 源文件 |
| `.cpp` | C++ 源文件 |
| `.cc` | C++ 源文件 |
| `.cxx` | C++ 源文件 |
| `.C` | C++ 源文件，部分 Unix 系统区分大小写 |
| `.h` | C 或 C++ 头文件 |
| `.hpp` | C++ 头文件 |
| `.hh` | C++ 头文件 |
| `.hxx` | C++ 头文件 |
| `.ipp` | C++ 模板或 inline 实现片段 |
| `.inl` | inline 实现片段 |

其中最常见的是：

```text
C:
  .h
  .c

C++:
  .hpp
  .cpp
```

但很多老项目、跨语言项目、系统库仍然大量使用 `.h` 作为 C++ 头文件。不要看到 `.h` 就立刻断定它只能给 C 用。它只是一个后缀，不是血统证明。

## 二、后缀是强制标准吗

C/C++ 标准并不强制规定源文件必须叫 `.c`、`.cpp`，头文件必须叫 `.h`、`.hpp`。

理论上，你可以把 C++ 代码放在一个叫 `hello.txt` 的文件里，然后告诉编译器按 C++ 编译：

```bash
g++ -x c++ hello.txt -o hello
```

`-x c++` 明确指定输入语言是 C++。

也可以把 C 代码放在奇怪后缀里：

```bash
gcc -x c source.weird -o app
```

但是正常工程不会这么做。后缀虽然不是语言标准强制，但它是编译器、构建系统、编辑器、IDE、语法高亮、静态分析工具共同依赖的约定。

如果你把 C++ 文件命名成 `.c`，构建系统可能按 C 编译它。然后你写：

```cpp
#include <iostream>

int main() {
    std::cout << "hello\n";
}
```

编译器按 C 语言处理，自然会报一堆错误。不是它不懂你，只是你没有告诉它正确语言。

## 三、.c 和 .cpp 的区别

`.c` 通常表示 C 源文件，使用 C 编译器或按 C 语言模式编译：

```bash
gcc main.c -o app
```

`.cpp` 通常表示 C++ 源文件，使用 C++ 编译器或按 C++ 语言模式编译：

```bash
g++ main.cpp -o app
```

区别不只是后缀，而是语言规则不同。

例如同样的代码：

```c
int main(void) {
    int class = 1;
    return class;
}
```

在 C 中，`class` 不是关键字，可能能通过。

在 C++ 中，`class` 是关键字，不能作为变量名。

再比如：

```c
void *p = malloc(100);
```

C 中 `void *` 可以隐式转换成其他对象指针：

```c
int *arr = malloc(sizeof(int) * 10);
```

C++ 中不允许这种隐式转换：

```cpp
int *arr = malloc(sizeof(int) * 10); // C++ 不合法
```

需要强转，但 C++ 更推荐使用 `new`、智能指针或标准容器：

```cpp
auto arr = std::vector<int>(10);
```

所以 `.c` 和 `.cpp` 真正代表的是：这个文件应该用哪套语言规则编译。

## 四、gcc 和 g++ 的区别

很多人以为：

```bash
gcc
g++
```

只是命令名字不同。并不是。

粗略理解：

- `gcc` 默认把 `.c` 当 C 编译，把 `.cpp/.cc/.cxx` 当 C++ 编译，但链接时不一定自动链接 C++ 标准库。
- `g++` 默认按 C++ 编译和链接，并会自动链接 C++ 标准库。

例如：

```bash
gcc main.cpp -o app
```

可能在链接时报 C++ 标准库符号找不到。

更常见写法是：

```bash
g++ main.cpp -o app
```

如果分步编译：

```bash
gcc -c main.cpp -o main.o
g++ main.o -o app
```

最后链接 C++ 程序时，通常用 `g++` 更省心，因为它会带上 C++ 运行时和标准库。

当然，严格说这些行为也和具体工具链有关。工程里更重要的是：**C++ 程序的最终链接应该使用 C++ 链接方式。**

## 五、.h 和 .hpp 的区别

`.h` 和 `.hpp` 都是头文件后缀。区别主要是工程约定：

| 后缀 | 常见含义 |
| ---- | -------- |
| `.h` | C 头文件，或 C/C++ 兼容头文件，或历史 C++ 头文件 |
| `.hpp` | C++ 头文件 |

如果头文件要同时给 C 和 C++ 使用，通常使用 `.h`：

```c
// student.h

#ifndef STUDENT_H
#define STUDENT_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Student {
    int id;
    int age;
} Student;

void print_student(const Student *student);

#ifdef __cplusplus
}
#endif

#endif
```

这个头文件里不能使用 C++ 专有语法，比如：

```cpp
class User {
};
```

因为 C 编译器看不懂 `class`。

如果头文件只给 C++ 用，通常可以用 `.hpp`：

```cpp
// user.hpp

#pragma once

#include <string>

class User {
public:
    User(std::string name, int age);

private:
    std::string name_;
    int age_;
};
```

这里使用了 `class`、`std::string`、访问控制等 C++ 特性，所以它不是 C 头文件。

## 六、C++ 能不能 include .h

当然可以。

很多 C++ 标准库和系统库也使用 `.h` 风格头文件，尤其是 C 标准库兼容头：

```cpp
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
```

C++ 也提供了对应的 C++ 风格头：

```cpp
#include <cstdio>
#include <cstdlib>
#include <cstring>
```

区别大致是：

- `<stdio.h>` 是 C 风格头文件名。
- `<cstdio>` 是 C++ 风格包装头，通常把名字放进 `std` 命名空间。

例如：

```cpp
#include <cstdio>

int main() {
    std::printf("hello\n");
}
```

实际实现中，某些名字也可能同时出现在全局命名空间和 `std` 中，但写 C++ 时更推荐使用 `<cstdio>` 和 `std::printf` 这种风格。

项目自己的 C++ 头文件也可以叫 `.h`。比如很多著名 C++ 项目都这样做。关键不是后缀，而是项目内部是否有统一规范。

## 七、C 能不能 include .hpp

从预处理器角度说，`#include` 只是找文件并展开文本，所以 C 当然“可以尝试”包含 `.hpp`：

```c
#include "user.hpp"
```

但如果 `.hpp` 里有 C++ 语法：

```cpp
class User {
public:
    User();
};
```

C 编译器会直接报错，因为它看不懂。

所以实际结论是：

- 如果 `.hpp` 里只写 C 兼容内容，C 编译器可以处理。
- 但按照工程约定，`.hpp` 通常表示 C++ 专用头文件，C 不应该包含它。

写出“C 可以 include `.hpp`”这种代码，不一定错，但很容易让维护者困惑。代码让人困惑时，它离错误通常也不远。

## 八、头文件和源文件如何配对

常见组织方式：

```text
student.h
student.c

user.hpp
user.cpp
```

头文件放对外接口：

```c
// student.h

#ifndef STUDENT_H
#define STUDENT_H

typedef struct Student {
    int id;
    int age;
} Student;

void student_print(const Student *student);

#endif
```

源文件放具体实现：

```c
// student.c

#include "student.h"
#include <stdio.h>

void student_print(const Student *student) {
    printf("id=%d, age=%d\n", student->id, student->age);
}
```

这种“头源分离”的好处：

- 调用者只需要包含头文件。
- 实现可以单独编译成目标文件。
- 修改 `.c/.cpp` 实现时，不一定导致所有调用者重新编译。
- 接口和实现边界更清楚。

但它也有代价：

- 需要维护声明和定义一致。
- C++ 类的私有成员往往仍要暴露在头文件中。
- 模板和 `inline` 经常不能简单放到 `.cpp`。

## 九、为什么头文件里不能随便写实现

假设有：

```c
// add.h

#ifndef ADD_H
#define ADD_H

int add(int a, int b) {
    return a + b;
}

#endif
```

然后：

```c
// a.c
#include "add.h"
```

```c
// b.c
#include "add.h"
```

预处理后，`a.c` 和 `b.c` 都有一份 `add` 函数定义。分别编译成 `a.o` 和 `b.o` 后，链接器会看到两个 `add`，于是报重复定义。

解决方式之一是把定义放到 `.c`：

```c
// add.h

#ifndef ADD_H
#define ADD_H

int add(int a, int b);

#endif
```

```c
// add.c

#include "add.h"

int add(int a, int b) {
    return a + b;
}
```

如果确实要把小函数放在头文件里，C 中可以使用 `static inline`：

```c
// add.h

#ifndef ADD_H
#define ADD_H

static inline int add(int a, int b) {
    return a + b;
}

#endif
```

`static` 让每个翻译单元拥有内部链接的独立副本，`inline` 表达内联意图并配合语言规则使用。

C++ 中可以使用 `inline`：

```cpp
// add.hpp

#pragma once

inline int add(int a, int b) {
    return a + b;
}
```

C++ 的 `inline` 不只是“建议编译器内联”，它还允许函数定义出现在多个翻译单元中，只要定义一致。

## 十、为什么模板通常放在头文件

C++ 模板是一个特别重要的例外。

例如：

```cpp
// max_value.hpp

#pragma once

template <typename T>
T max_value(T a, T b) {
    return a > b ? a : b;
}
```

使用：

```cpp
#include "max_value.hpp"

int main() {
    return max_value(1, 2);
}
```

编译器看到 `max_value(1, 2)` 时，需要根据 `T=int` 生成一个具体函数：

```cpp
int max_value<int>(int a, int b) {
    return a > b ? a : b;
}
```

因此，编译器必须在使用模板的翻译单元里看到模板定义。

如果你只在头文件里写声明：

```cpp
// max_value.hpp

#pragma once

template <typename T>
T max_value(T a, T b);
```

把定义放到 `.cpp`：

```cpp
// max_value.cpp

#include "max_value.hpp"

template <typename T>
T max_value(T a, T b) {
    return a > b ? a : b;
}
```

其他 `.cpp` 使用 `max_value<int>` 时，可能链接失败，因为模板实例没有在那个翻译单元中生成。

当然，可以显式实例化：

```cpp
template int max_value<int>(int, int);
```

但普通工程里，模板定义放头文件更常见。

这也是 C++ 很多库只有 `.hpp` 的原因之一。

## 十一、header-only 库

有些 C++ 库是 header-only，也就是只有头文件，没有需要单独编译的 `.cpp`。

常见原因：

- 大量使用模板。
- 大量使用 `inline`。
- 希望使用者只 include 就能用。
- 简化分发和构建。

例如：

```cpp
// small_math.hpp

#pragma once

template <typename T>
T square(T x) {
    return x * x;
}

inline int add(int a, int b) {
    return a + b;
}
```

使用者：

```cpp
#include "small_math.hpp"

int main() {
    return square(3) + add(1, 2);
}
```

header-only 的优点：

- 使用简单。
- 模板定义天然可见。
- 不需要链接单独库。

缺点：

- 编译时间可能增加。
- 修改头文件会导致所有包含它的源文件重新编译。
- 实现细节暴露更多。
- 二进制边界不清晰。

所以 header-only 不是“更高级”，只是适合某些场景。

## 十二、.ipp 和 .inl 是什么

在一些 C++ 项目里，会看到：

```text
vector.hpp
vector.ipp
math.inl
```

这类文件通常不是单独编译的源文件，而是被头文件包含的实现片段。

例如：

```cpp
// vector.hpp

#pragma once

template <typename T>
class Vector {
public:
    void push_back(const T &value);
};

#include "vector.ipp"
```

```cpp
// vector.ipp

template <typename T>
void Vector<T>::push_back(const T &value) {
    // ...
}
```

这样做的目的是：

- 让头文件主体更清晰。
- 模板定义仍然对使用者可见。
- 避免把大量实现全堆在 `.hpp` 里。

`.ipp`、`.inl` 没有统一强制标准，只是工程习惯。它们通常不应该被构建系统当作普通 `.cpp` 单独编译。

## 十三、C 和 C++ 混合工程

很多工程里既有 C，又有 C++：

```text
src/
  c_api.h
  c_api.c
  wrapper.hpp
  wrapper.cpp
```

C 接口头文件：

```c
// c_api.h

#ifndef C_API_H
#define C_API_H

#ifdef __cplusplus
extern "C" {
#endif

void c_api_init(void);

#ifdef __cplusplus
}
#endif

#endif
```

C 实现：

```c
// c_api.c

#include "c_api.h"

void c_api_init(void) {
}
```

C++ 可以包含这个 C 头文件：

```cpp
// wrapper.cpp

#include "c_api.h"

int main() {
    c_api_init();
}
```

`extern "C"` 确保 C++ 编译器不会对 `c_api_init` 做 C++ 名字改编。

混合工程要注意：

- `.c` 文件用 C 编译器规则编译。
- `.cpp` 文件用 C++ 编译器规则编译。
- C 头文件要避免 C++ 专有语法。
- 暴露给 C 的 API 要用 C ABI。
- 最终链接如果包含 C++ 对象文件，通常用 C++ 编译器驱动链接。

例如：

```bash
gcc -c c_api.c -o c_api.o
g++ -c wrapper.cpp -o wrapper.o
g++ c_api.o wrapper.o -o app
```

最后一步用 `g++`，因为程序里有 C++ 代码，需要 C++ 运行时和标准库。

## 十四、C++ 头文件里的私有成员问题

C++ 类即使把字段写成 `private`，也常常必须放在头文件里：

```cpp
// user.hpp

#pragma once

#include <string>

class User {
public:
    User(std::string name);
    const std::string &name() const;

private:
    std::string name_;
};
```

使用者虽然不能直接访问 `name_`，但编译器必须知道 `User` 的大小和布局，才能创建对象：

```cpp
User user("yukino");
```

这会导致两个问题：

- 私有实现细节暴露在头文件中。
- 修改私有字段也可能导致所有包含该头文件的源文件重新编译。

一种缓解方式是 PImpl：

```cpp
// user.hpp

#pragma once

#include <memory>
#include <string>

class User {
public:
    explicit User(std::string name);
    ~User();

    const std::string &name() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
```

```cpp
// user.cpp

#include "user.hpp"

struct User::Impl {
    std::string name;
};

User::User(std::string name)
    : impl_(std::make_unique<Impl>(Impl{std::move(name)})) {
}

User::~User() = default;

const std::string &User::name() const {
    return impl_->name;
}
```

PImpl 可以减少头文件暴露的实现细节，也能降低重新编译范围。代价是多一次间接访问和动态分配，代码也更复杂。

不要为了展示技巧到处使用 PImpl。技巧这种东西，一旦离开问题本身，就只是装饰品。

## 十五、工程目录怎么组织

小项目可以这样：

```text
project/
  main.c
  student.c
  student.h
```

稍微规范一点：

```text
project/
  include/
    student.h
  src/
    student.c
    main.c
```

C++ 项目：

```text
project/
  include/
    user.hpp
    order.hpp
  src/
    user.cpp
    order.cpp
    main.cpp
```

如果是库项目，可以区分公开头文件和内部头文件：

```text
project/
  include/
    mylib/
      user.hpp        对外公开
      order.hpp       对外公开
  src/
    user.cpp
    order.cpp
    internal_cache.hpp  内部使用
```

公开头文件是别人会 include 的内容，要格外克制：

- 少包含不必要的头文件。
- 不污染命名空间。
- 不暴露无关实现细节。
- 保持 ABI/API 稳定。
- 文件名和命名空间尽量有项目前缀，避免冲突。

内部头文件只在项目内部使用，可以灵活一些，但也不应该混乱。混乱不会因为被藏在 `src` 目录里就变得无害。

## 十六、CMake 中如何表达这些关系

CMake 示例：

```cmake
add_library(student
    src/student.c
)

target_include_directories(student
    PUBLIC
        include
)

add_executable(app
    src/main.c
)

target_link_libraries(app
    PRIVATE
        student
)
```

这里的关系是：

- `student` 库由 `src/student.c` 编译出来。
- `include` 是 `student` 的公开头文件路径。
- `app` 链接 `student`。
- 因为 `include` 对 `student` 是 `PUBLIC`，所以链接 `student` 的目标也能继承这个 include 路径。

`target_include_directories` 解决的是头文件路径。

`target_link_libraries` 解决的是链接依赖。

二者不是一回事。写 CMake 时把这两个混淆，最后就会得到一些表情很冷淡的报错。

## 十七、命名建议

可以采用这样的习惯：

### C 项目

```text
foo.h
foo.c
```

头文件写 C 兼容声明：

```c
#ifndef FOO_H
#define FOO_H

void foo_run(void);

#endif
```

源文件写实现：

```c
#include "foo.h"

void foo_run(void) {
}
```

### C++ 项目

```text
foo.hpp
foo.cpp
```

头文件写 C++ 接口：

```cpp
#pragma once

class Foo {
public:
    void run();
};
```

源文件写实现：

```cpp
#include "foo.hpp"

void Foo::run() {
}
```

### C/C++ 兼容 API

```text
foo.h
foo.c
```

或：

```text
foo.h
foo.cpp
```

如果实现用 C++ 写，但对外暴露 C API，也可以这样：

```c
// foo.h

#ifndef FOO_H
#define FOO_H

#ifdef __cplusplus
extern "C" {
#endif

void foo_run(void);

#ifdef __cplusplus
}
#endif

#endif
```

```cpp
// foo.cpp

#include "foo.h"

void foo_run(void) {
    // 内部可以使用 C++ 实现
}
```

外部 C 程序看到的仍然是 C 风格函数接口。

## 十八、常见误解

### 1. `.h` 一定是 C 头文件

不一定。很多 C++ 项目也使用 `.h`。

更准确的判断方式是看文件内容和项目约定。

### 2. `.hpp` 一定不能被 C 包含

预处理器并不关心后缀。但按照约定，`.hpp` 通常包含 C++ 语法，C 编译器大概率看不懂。

### 3. include 了头文件就不用编译源文件

错。

```c
#include "student.h"
```

只让编译器看到声明。`student.c` 仍然要参与编译和链接。

### 4. 头文件保护宏能解决重复定义函数

不完全对。

include guard 只能防止同一个翻译单元内重复包含同一个头文件。它不能阻止多个 `.c/.cpp` 文件各自包含同一个头文件后，生成多个函数定义。

例如：

```c
// bad.h

#ifndef BAD_H
#define BAD_H

void bad(void) {
}

#endif
```

`a.c` 和 `b.c` 都包含它，仍然可能链接重复定义。

### 5. 所有函数实现都应该放 `.cpp`

也不一定。

模板、`inline` 函数、`constexpr` 函数、header-only 库，经常需要或适合放在头文件中。

### 6. 后缀无所谓

也不对。

语言标准不强制，但工具链、构建系统、团队约定都依赖它。后缀写错，构建系统可能按错误语言编译。你可以说它“理论上无所谓”，但工程不是用理论上的侥幸构建出来的。

## 十九、实践建议

比较稳妥的习惯是：

- C 源文件使用 `.c`。
- C 头文件使用 `.h`。
- C++ 源文件使用 `.cpp`、`.cc` 或 `.cxx`，团队统一即可。
- C++ 专用头文件使用 `.hpp`、`.hh` 或 `.hxx`，团队统一即可。
- C/C++ 兼容头文件优先使用 `.h`。
- 头文件放接口，源文件放实现。
- 模板和 `inline` 可以放头文件。
- 不在头文件里写普通全局变量定义。
- 不在头文件里写 `using namespace std;`。
- 每个头文件都写 include guard 或 `#pragma once`。
- 构建系统里明确配置 include 路径和链接目标。

如果是个人项目，可以简单些；如果是团队项目，重要的是统一。统一不代表完美，但至少能减少没必要的猜测。

## 二十、总结

`.h`、`.hpp`、`.c`、`.cpp` 的关系可以这样理解：

- `.c` 通常是 C 源文件，按 C 语言规则编译。
- `.cpp`、`.cc`、`.cxx` 通常是 C++ 源文件，按 C++ 语言规则编译。
- `.h` 通常是 C 头文件，也常被 C++ 项目使用。
- `.hpp`、`.hh`、`.hxx` 通常表示 C++ 头文件。
- 后缀不是 C/C++ 标准强制规定，但会影响工具链和工程约定。
- 头文件不是单独编译的模块，而是被源文件 `#include` 后参与该翻译单元的编译。
- 源文件通常会被单独编译成目标文件，再由链接器组合。
- 头源分离、header-only、模板、C/C++ 混编都是围绕这套编译模型展开的工程选择。

一句话概括：**文件后缀本身只是名字，但它表达了这个文件应当被哪种语言规则处理、承担接口还是实现角色，以及在构建系统中应该如何参与编译和链接。**
