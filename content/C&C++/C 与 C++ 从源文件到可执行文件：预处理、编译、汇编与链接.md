+++
date = '2026-08-22T21:50:10+08:00'
draft = false
title = 'C 与 C++ 从源文件到可执行文件：预处理、编译、汇编与链接'
+++

写 C/C++ 时，经常会遇到这种情况：

```c
#include "student.h"

int main(void) {
    print_student();
    return 0;
}
```

头文件明明包含了，编译时却还是报错：

```text
undefined reference to `print_student'
```

这时候如果只盯着 `#include`，就会越看越困惑。因为 `#include` 解决的是“声明可见”的问题，而 `undefined reference` 通常是链接阶段找不到定义。

C/C++ 的构建过程不是一步完成的。一个程序从源码到可执行文件，大致会经历：

```text
源文件
  -> 预处理
  -> 编译
  -> 汇编
  -> 链接
  -> 可执行文件
```

这篇文章把这条链路系统讲清楚。否则头文件、源文件、库文件、链接错误会混在一起，像一堆看似熟悉但互相指责的概念。那当然不会让人变强，只会让人变沉默。

## 一、整体流程

假设有一个最简单的 C 项目：

```text
project/
  main.c
  math_utils.c
  math_utils.h
```

头文件：

```c
// math_utils.h

#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);

#endif
```

实现文件：

```c
// math_utils.c

#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}
```

入口文件：

```c
// main.c

#include "math_utils.h"
#include <stdio.h>

int main(void) {
    printf("%d\n", add(1, 2));
    return 0;
}
```

可以这样直接构建：

```bash
gcc main.c math_utils.c -o app
```

这条命令看似一步完成，其实编译器驱动程序在背后做了多步：

```text
main.c       -> main.o
math_utils.c -> math_utils.o
main.o + math_utils.o + C 标准库 -> app
```

更细地看：

```text
main.c
  -> 预处理得到 main.i
  -> 编译得到 main.s
  -> 汇编得到 main.o

math_utils.c
  -> 预处理得到 math_utils.i
  -> 编译得到 math_utils.s
  -> 汇编得到 math_utils.o

main.o + math_utils.o + 运行时库和标准库
  -> 链接得到 app
```

实际构建工具可能不会真的把 `.i`、`.s` 文件保存下来，但概念上就是这些阶段。

## 二、预处理阶段

预处理阶段处理的是以 `#` 开头的预处理指令，例如：

- `#include`
- `#define`
- `#ifdef`
- `#ifndef`
- `#if`
- `#pragma`

例如：

```c
#include <stdio.h>
#define MAX_SIZE 100

int buffer[MAX_SIZE];
```

预处理之后，`stdio.h` 的相关声明会被展开进来，`MAX_SIZE` 会被替换。

可以只运行预处理：

```bash
gcc -E main.c -o main.i
```

C++：

```bash
g++ -E main.cpp -o main.ii
```

预处理阶段的结果是一个完整的 **翻译单元**。

### 预处理阶段常见错误

头文件找不到：

```text
fatal error: math_utils.h: No such file or directory
```

这通常是 include 路径没有配好。例如头文件在 `include` 目录：

```bash
gcc -Iinclude src/main.c
```

宏拼写错误、条件编译不符合预期，也属于预处理相关问题。

## 三、编译阶段

编译阶段把预处理后的 C/C++ 代码转换成汇编代码。

可以只编译到汇编：

```bash
gcc -S main.c -o main.s
```

C++：

```bash
g++ -S main.cpp -o main.s
```

编译器在这一阶段会做：

- 词法分析。
- 语法分析。
- 类型检查。
- 语义分析。
- 优化。
- 生成汇编代码。

例如：

```c
int add(int a, int b);

int main(void) {
    return add(1, 2);
}
```

只要编译器看到了 `add` 的声明，它就知道 `add(1, 2)` 这种调用是否合法。

但它不需要在编译阶段看到 `add` 的函数体。函数体可以在另一个 `.c` 文件里，稍后由链接器处理。

这就是声明和定义分离的基础。

### 编译阶段常见错误

语法错误：

```text
error: expected ';' before '}'
```

类型错误：

```text
error: incompatible pointer types
```

C 中没有函数声明时，可能出现：

```text
warning: implicit declaration of function 'add'
```

现代 C 标准已经不再允许随便隐式声明函数。不要依赖“反正能编过去”的旧习惯。它不是宽容，只是历史遗留。

C++ 中如果函数没有声明，一般会直接报错：

```text
error: 'add' was not declared in this scope
```

这些错误发生在编译阶段，还没有进入链接。

## 四、汇编阶段

汇编阶段把汇编代码转换成目标文件。

可以只生成目标文件，不链接：

```bash
gcc -c main.c -o main.o
gcc -c math_utils.c -o math_utils.o
```

目标文件通常是：

- Linux / Unix-like：`.o`
- Windows MSVC：`.obj`

目标文件里包含：

- 机器指令。
- 符号表。
- 重定位信息。
- 常量数据。
- 调试信息。

一个目标文件还不是完整程序。它可能引用了其他目标文件或库里的函数。

例如 `main.o` 里可能有：

```text
定义的符号:
  main

未解析的符号:
  add
  printf
```

`math_utils.o` 里可能有：

```text
定义的符号:
  add
```

链接器后面要把这些符号对上。

## 五、链接阶段

链接阶段把多个目标文件和库合成最终产物：

```bash
gcc main.o math_utils.o -o app
```

链接器要做的事情包括：

- 合并多个目标文件。
- 解析符号引用。
- 处理重定位。
- 合并相同或相关段。
- 引入运行时启动代码。
- 链接静态库或记录动态库依赖。
- 生成可执行文件或共享库。

最关键的是：**链接器负责把“调用某个函数”的地方，和“这个函数真正定义在哪里”对应起来。**

例如：

```c
// main.c

int add(int a, int b);

int main(void) {
    return add(1, 2);
}
```

`main.c` 编译时只需要知道 `add` 的声明。编译器会在 `main.o` 中留下一个对 `add` 的引用。

```c
// math_utils.c

int add(int a, int b) {
    return a + b;
}
```

`math_utils.c` 编译成 `math_utils.o`，里面定义了 `add`。

链接时：

```bash
gcc main.o math_utils.o -o app
```

链接器发现 `main.o` 需要 `add`，而 `math_utils.o` 提供 `add`，于是把它们连接起来。

如果漏掉 `math_utils.o`：

```bash
gcc main.o -o app
```

就会报：

```text
undefined reference to `add'
```

这不是头文件问题。头文件只是让编译器“知道有这个函数”，并不提供函数实现。

## 六、声明、定义和链接错误

下面这个例子很典型。

头文件：

```c
// logger.h

#ifndef LOGGER_H
#define LOGGER_H

void log_message(const char *message);

#endif
```

入口文件：

```c
// main.c

#include "logger.h"

int main(void) {
    log_message("hello");
    return 0;
}
```

如果没有 `logger.c` 实现：

```c
// logger.c

#include "logger.h"
#include <stdio.h>

void log_message(const char *message) {
    puts(message);
}
```

或者编译时没有把 `logger.c` 加进去：

```bash
gcc main.c -o app
```

都会在链接阶段失败。

正确编译：

```bash
gcc main.c logger.c -o app
```

或者分步：

```bash
gcc -c main.c -o main.o
gcc -c logger.c -o logger.o
gcc main.o logger.o -o app
```

可以总结成：

```text
头文件提供声明
源文件提供定义
目标文件保存编译结果
链接器把目标文件和库拼成最终程序
```

## 七、重复定义错误

另一个常见链接错误是重复定义。

错误示例：

```c
// config.h

#ifndef CONFIG_H
#define CONFIG_H

int global_port = 8080;

#endif
```

如果 `main.c` 和 `server.c` 都包含了 `config.h`：

```c
#include "config.h"
```

那么预处理后，两个翻译单元里都会有一份：

```c
int global_port = 8080;
```

于是链接器会看到两个 `global_port` 定义，可能报：

```text
multiple definition of `global_port'
```

正确做法：

```c
// config.h

#ifndef CONFIG_H
#define CONFIG_H

extern int global_port;

#endif
```

```c
// config.c

#include "config.h"

int global_port = 8080;
```

头文件里放声明，某一个源文件里放唯一的定义。

### C++17 的 inline 变量

C++17 以后可以用 `inline` 变量：

```cpp
// config.hpp

#pragma once

inline int global_port = 8080;
```

这允许变量定义出现在多个翻译单元中，由链接器合并。但这属于 C++ 的特性，不是传统 C 的写法。

不要把 C++17 的规则拿去解释 C。语言之间虽然长得像，但并不总是亲戚般可靠。

## 八、静态库和动态库

实际工程里，函数实现不一定来自自己项目的 `.o` 文件，也可能来自库。

库主要分两类：

- 静态库。
- 动态库。

### 1. 静态库

静态库可以理解为一组目标文件打包在一起。

常见后缀：

- Linux / Unix-like：`.a`
- Windows MSVC：`.lib`

例如：

```bash
gcc -c math_utils.c -o math_utils.o
ar rcs libmathutils.a math_utils.o
```

使用静态库：

```bash
gcc main.c -L. -lmathutils -o app
```

其中：

- `-L.` 表示在当前目录查找库。
- `-lmathutils` 表示链接 `libmathutils.a` 或对应动态库。

静态链接时，链接器会把需要的目标代码复制进最终可执行文件。

优点：

- 部署简单，依赖少。
- 程序运行时不需要额外找这个库文件。

缺点：

- 可执行文件可能更大。
- 多个程序使用同一个库时，代码不能共享。
- 库更新后通常需要重新链接程序。

### 2. 动态库

动态库在程序运行或加载时由操作系统动态加载。

常见后缀：

- Linux：`.so`
- macOS：`.dylib`
- Windows：`.dll`

构建动态库：

```bash
gcc -fPIC -shared math_utils.c -o libmathutils.so
```

链接使用：

```bash
gcc main.c -L. -lmathutils -o app
```

动态链接时，可执行文件里通常不会复制库的全部代码，而是记录对动态库的依赖和符号引用。程序启动时，动态链接器会加载所需动态库并解析符号。

优点：

- 多个程序可以共享同一份库代码。
- 可执行文件较小。
- 库可以独立更新，但要保持 ABI 兼容。

缺点：

- 运行时必须能找到动态库。
- 版本冲突和部署问题更复杂。
- ABI 不兼容时可能出现运行时错误。

## 九、头文件和库文件的关系

使用一个库通常需要两类东西：

```text
头文件：告诉编译器怎么调用
库文件：提供真正实现，让链接器或运行时找到代码
```

例如使用第三方库 `foo`：

```c
#include <foo/foo.h>

int main(void) {
    foo_init();
    return 0;
}
```

编译时可能需要：

```bash
gcc main.c -I/path/to/foo/include -L/path/to/foo/lib -lfoo -o app
```

这里：

- `-I/path/to/foo/include` 是给预处理器和编译器找头文件用的。
- `-L/path/to/foo/lib` 是给链接器找库文件用的。
- `-lfoo` 是告诉链接器链接 `foo` 库。

不要把 `-I` 和 `-L` 混在一起：

| 选项 | 作用 | 面向谁 |
| ---- | ---- | ------ |
| `-I` | 添加头文件搜索路径 | 预处理器 / 编译器 |
| `-L` | 添加库文件搜索路径 | 链接器 |
| `-l` | 指定要链接的库 | 链接器 |

这也是为什么“头文件能找到，但链接失败”很常见：你只告诉了编译器接口在哪里，却没有告诉链接器实现在哪里。

## 十、动态链接和程序运行

用户提到“程序运行的时候好像还有链接什么的事情”，这个感觉是对的。

链接可以分成：

- 构建时链接。
- 加载时动态链接。
- 运行时显式加载。

### 1. 构建时链接

构建可执行文件时：

```bash
gcc main.o math_utils.o -o app
```

链接器会生成最终的 `app`。如果是静态链接，所需代码可能已经被复制进可执行文件。

### 2. 加载时动态链接

如果程序依赖动态库，例如 `libfoo.so`，可执行文件里会记录这个依赖。

运行程序时，操作系统加载器和动态链接器会：

- 读取可执行文件。
- 找到它依赖的动态库。
- 把动态库加载到进程地址空间。
- 解析需要的符号。
- 做必要的重定位。
- 然后开始执行程序入口。

所以动态库确实可能在程序启动时参与链接过程。

如果找不到动态库，可能出现：

```text
error while loading shared libraries: libfoo.so: cannot open shared object file
```

Windows 上可能是：

```text
The code execution cannot proceed because foo.dll was not found
```

这类错误不是编译错误，也不是普通链接错误，而是运行时加载动态库失败。

### 3. 运行时显式加载

程序也可以自己在运行时加载动态库。

Linux / Unix-like：

```c
#include <dlfcn.h>

void *handle = dlopen("./plugin.so", RTLD_NOW);
```

Windows：

```c
HMODULE module = LoadLibraryA("plugin.dll");
```

这常见于插件系统。程序启动时不一定知道所有插件，运行过程中再按需加载。

## 十一、符号是什么

链接器处理的核心对象之一叫 **符号（symbol）**。

函数名、全局变量名通常都会成为符号：

```c
int add(int a, int b) {
    return a + b;
}

int global_count = 0;
```

目标文件里会记录：

```text
add            定义在当前目标文件
global_count   定义在当前目标文件
printf         当前目标文件引用了它，但没有定义
```

可以用工具查看符号。

Linux / Unix-like：

```bash
nm main.o
```

Windows MSVC：

```bat
dumpbin /symbols main.obj
```

当链接器看到某个目标文件引用了 `add`，它就要在其他目标文件或库中找到 `add` 的定义。

找不到，就是 undefined reference。

找到多个强定义，就是 multiple definition。

## 十二、C++ 名字改编

C++ 支持函数重载：

```cpp
void print(int value);
void print(double value);
```

两个函数都叫 `print`，但参数不同。为了让链接器区分它们，C++ 编译器会对函数名做 **名字改编（name mangling）**。

例如源代码里的：

```cpp
void print(int value);
```

在目标文件符号表里可能变成类似：

```text
_Z5printi
```

不同编译器的改编规则不一定相同。

这会影响 C 和 C++ 混合编程。

假设 C 里有函数：

```c
// c_api.c

void hello(void) {
}
```

C++ 想调用它：

```cpp
// main.cpp

void hello();

int main() {
    hello();
}
```

C++ 编译器可能会把 `hello` 当成 C++ 函数，生成改编后的符号名，结果链接器找不到 C 文件里的 `hello`。

应该写：

```cpp
extern "C" void hello();
```

常见头文件写法：

```c
#ifdef __cplusplus
extern "C" {
#endif

void hello(void);

#ifdef __cplusplus
}
#endif
```

`extern "C"` 的作用是告诉 C++ 编译器：这些函数按照 C 的符号规则处理，不要做 C++ 名字改编。

它不会让 C 支持 C++ 类，也不会让对象模型突然统一。它只处理链接符号名的问题。

## 十三、链接顺序问题

在 GCC / Clang 使用静态库时，链接顺序有时会影响结果。

例如：

```bash
gcc -lmathutils main.o -o app
```

可能失败。

更常见的正确写法是：

```bash
gcc main.o -lmathutils -o app
```

因为传统链接器通常从左到右扫描输入文件。扫描到库时，只会从库中取出当前已经需要的符号。如果库出现在使用它的目标文件之前，链接器当时还不知道需要库里的哪些符号，就可能没有取出对应目标。

当然，现代构建系统和链接器有各种选项能处理复杂情况，但理解这个规则有助于看懂一些令人恼火的链接错误。

## 十四、静态链接和动态链接的选择

选择静态库还是动态库，没有绝对答案。

静态链接适合：

- 部署环境简单。
- 想减少运行时依赖。
- 小工具、单文件分发。
- 对库版本稳定性要求高。

动态链接适合：

- 多个程序共享库。
- 希望库独立升级。
- 插件系统。
- 系统级公共库。

但动态库升级必须注意 ABI 兼容。

例如 C 接口：

```c
typedef struct User {
    int id;
    int age;
} User;
```

如果动态库新版本把结构体改成：

```c
typedef struct User {
    int id;
    double score;
    int age;
} User;
```

旧程序如果仍按旧布局使用，就可能发生二进制不兼容。

所以库的头文件和实际二进制库必须匹配。头文件描述的是接口，库文件提供的是实现。两者版本错位时，程序不会因为你的诚意而自动正常。

## 十五、构建系统在做什么

手写命令：

```bash
gcc -Iinclude src/main.c src/math_utils.c -o app
```

项目小的时候还可以。项目变大后，需要构建系统管理：

- 哪些源文件参与编译。
- include 路径有哪些。
- 要链接哪些库。
- 编译选项是什么。
- 目标之间的依赖关系。
- 哪些文件变了需要重新编译。

Makefile 示例：

```makefile
app: main.o math_utils.o
	gcc main.o math_utils.o -o app

main.o: main.c math_utils.h
	gcc -c main.c -o main.o

math_utils.o: math_utils.c math_utils.h
	gcc -c math_utils.c -o math_utils.o
```

CMake 示例：

```cmake
add_executable(app
    src/main.c
    src/math_utils.c
)

target_include_directories(app PRIVATE include)
```

构建系统不是编译器本身，它只是把编译器、汇编器、链接器按正确方式组织起来。

## 十六、常见错误分类

### 1. 找不到头文件

```text
fatal error: foo.h: No such file or directory
```

原因通常是：

- 头文件路径写错。
- 没有配置 `-I`。
- 构建系统 include 路径没加。
- 使用了错误的双引号或尖括号查找方式。

### 2. 找不到函数声明

C++：

```text
error: 'foo' was not declared in this scope
```

原因通常是：

- 没有包含对应头文件。
- 函数声明在命名空间里，调用时没有写命名空间。
- 条件编译把声明排除了。
- C/C++ 混合头文件没有处理好。

### 3. 找不到函数定义

GCC / Clang：

```text
undefined reference to `foo'
```

MSVC：

```text
unresolved external symbol foo
```

原因通常是：

- 只包含了头文件，没有编译对应 `.c/.cpp`。
- 没有链接对应库。
- 库路径 `-L` 没配。
- 库名 `-l` 写错。
- C++ 名字改编导致符号名不匹配。
- 静态库链接顺序不对。

### 4. 重复定义

```text
multiple definition of `foo'
```

原因通常是：

- 在头文件里定义了普通全局变量。
- 在头文件里定义了非 `inline` 普通函数。
- 同一个源文件被重复加入构建目标。
- C++ ODR 被违反。

ODR 是 One Definition Rule，也就是一个定义规则。C++ 中很多链接问题最终都能追到这里。名字很端正，报错时一点也不温柔。

## 十七、如何排查编译链接问题

可以按阶段排查：

### 1. 头文件是否能找到

看 include 路径：

```bash
gcc -Iinclude -E src/main.c
```

如果预处理都失败，就先别看链接。

### 2. 函数声明是否可见

确认源文件包含了正确头文件：

```c
#include "math_utils.h"
```

确认函数声明存在：

```c
int add(int a, int b);
```

### 3. 实现文件是否参与编译

检查命令中有没有对应源文件：

```bash
gcc src/main.c src/math_utils.c -o app
```

或者目标文件：

```bash
gcc main.o math_utils.o -o app
```

### 4. 库是否参与链接

检查：

```bash
gcc main.o -L/path/to/lib -lfoo -o app
```

### 5. 符号是否真的存在

可以用 `nm`：

```bash
nm math_utils.o
nm libmathutils.a
```

如果库里根本没有你要的符号，那链接命令再虔诚也没有用。

## 十八、总结

C/C++ 程序从源码到可执行文件，不是简单把所有代码放在一起运行，而是经历多个阶段：

- **预处理**：处理 `#include`、宏、条件编译，生成翻译单元。
- **编译**：做语法和类型检查，把高级语言转成汇编。
- **汇编**：把汇编转成目标文件。
- **链接**：解析符号，把多个目标文件和库合成可执行文件或共享库。

头文件和链接的关系可以这样记：

- 头文件提供声明，解决编译器“看不看得懂调用”的问题。
- 源文件或库提供定义，解决链接器“找不找得到实现”的问题。
- `#include` 不会自动把 `.c/.cpp` 文件编译进来。
- `#include` 也不会自动链接某个 `.a/.so/.lib/.dll`。
- 动态库可能在程序加载或运行时参与符号解析。

一句话概括：**C/C++ 的构建模型是“各源文件分别编译，最后由链接器拼合”。头文件只是让每个源文件在编译时看见接口，真正把代码连成程序的是链接。**
