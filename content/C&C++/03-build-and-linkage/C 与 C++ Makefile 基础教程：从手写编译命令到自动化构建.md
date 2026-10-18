+++
date = '2026-08-23T01:10:00+08:00'
draft = false
title = 'C 与 C++ Makefile 基础教程：从手写编译命令到自动化构建'
+++

写 C/C++ 时，一开始我们通常会这样编译：

```bash
gcc main.c math_utils.c -o app
```

或者 C++：

```bash
g++ main.cpp math_utils.cpp -o app
```

文件少的时候，这当然没什么问题。可是一旦项目变成这样：

```text
project/
  include/
    math_utils.h
    student.h
  src/
    main.c
    math_utils.c
    student.c
```

你就会开始反复写很长的命令：

```bash
gcc -Iinclude src/main.c src/math_utils.c src/student.c -o app
```

如果再加上：

- 调试参数 `-g`
- 警告参数 `-Wall -Wextra`
- 优化参数 `-O2`
- 多个 `.o` 目标文件
- 只重新编译改过的源文件
- 清理构建产物

手写命令就会变得很烦。Makefile 的作用就是把这些重复、机械、容易写错的构建命令记录下来，然后交给 `make` 自动执行。

一句话概括：

**Makefile 描述“什么文件依赖什么文件，以及如何从依赖生成目标”。**

它不是 C/C++ 专属工具，但它非常适合解释 C/C++ 构建过程。因为 C/C++ 本来就是由源文件、目标文件、头文件、库文件和可执行文件共同组成的。

## 一、Makefile 解决什么问题

假设有三个文件：

```text
main.c
math_utils.c
math_utils.h
```

代码如下：

```c
// math_utils.h

#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);

#endif
```

```c
// math_utils.c

#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}
```

```c
// main.c

#include "math_utils.h"
#include <stdio.h>

int main(void) {
    printf("%d\n", add(1, 2));
    return 0;
}
```

直接编译可以这样写：

```bash
gcc main.c math_utils.c -o app
```

这条命令背后做的事情可以拆成：

```text
main.c       -> main.o
math_utils.c -> math_utils.o
main.o + math_utils.o -> app
```

手动拆开就是：

```bash
gcc -c main.c -o main.o
gcc -c math_utils.c -o math_utils.o
gcc main.o math_utils.o -o app
```

这样做有一个好处：如果只修改了 `main.c`，理论上只需要重新生成 `main.o`，然后重新链接：

```bash
gcc -c main.c -o main.o
gcc main.o math_utils.o -o app
```

`math_utils.c` 没变，就没必要重新编译。Makefile 正是把这种依赖关系写清楚，让 `make` 自己判断哪些命令需要重新执行。

## 二、最小 Makefile

在项目根目录创建一个名为 `Makefile` 的文件：

```makefile
app: main.c math_utils.c
	gcc main.c math_utils.c -o app
```

然后运行：

```bash
make
```

`make` 默认会读取当前目录下的 `Makefile`，并执行第一个目标。这里第一个目标是 `app`。

Makefile 规则的基本格式是：

```makefile
目标: 依赖
	命令
```

对应到上面的例子：

```makefile
app: main.c math_utils.c
	gcc main.c math_utils.c -o app
```

含义是：

```text
如果 app 不存在，或者 main.c / math_utils.c 比 app 更新，
就执行 gcc main.c math_utils.c -o app。
```

注意，命令行前面必须是 **Tab 字符**，不是普通空格。这是 Makefile 最容易让初学者困惑的地方之一。看起来只是缩进，实际上语法要求很严格。它冷淡得像一位不愿解释第二遍的考官。

## 三、目标、依赖和命令

Makefile 的核心就是三件事：

| 名称 | 含义 |
| ---- | ---- |
| 目标 | 要生成的文件，或者要执行的任务 |
| 依赖 | 生成目标之前需要检查的文件或目标 |
| 命令 | 生成目标时真正执行的 shell 命令 |

例如：

```makefile
app: main.o math_utils.o
	gcc main.o math_utils.o -o app

main.o: main.c math_utils.h
	gcc -c main.c -o main.o

math_utils.o: math_utils.c math_utils.h
	gcc -c math_utils.c -o math_utils.o
```

这份 Makefile 写清楚了：

- `app` 依赖 `main.o` 和 `math_utils.o`
- `main.o` 依赖 `main.c` 和 `math_utils.h`
- `math_utils.o` 依赖 `math_utils.c` 和 `math_utils.h`

运行：

```bash
make
```

`make` 会先看第一个目标 `app`。它发现 `app` 需要 `main.o` 和 `math_utils.o`，于是继续检查这两个目标是否需要更新。

如果 `main.c` 改了，只重新编译 `main.o`。

如果 `math_utils.c` 改了，只重新编译 `math_utils.o`。

如果 `math_utils.h` 改了，`main.o` 和 `math_utils.o` 都会重新编译。因为它们都包含了这个头文件。

这就是 Makefile 的基本价值：**按依赖关系做增量构建。**

## 四、为什么头文件也要写进依赖

很多初学者会写成这样：

```makefile
main.o: main.c
	gcc -c main.c -o main.o
```

看起来没错，但它漏掉了 `math_utils.h`。

如果 `main.c` 内容没变，而 `math_utils.h` 改了，比如函数声明从：

```c
int add(int a, int b);
```

改成：

```c
long add(long a, long b);
```

那么 `main.o` 其实应该重新编译。因为 `main.c` 预处理时会把 `math_utils.h` 的内容包含进来。

也就是说，对编译器来说：

```c
#include "math_utils.h"
```

并不是一个轻飘飘的引用，而是文本包含。头文件变了，源文件的编译输入也变了。

所以更准确的依赖应该写成：

```makefile
main.o: main.c math_utils.h
	gcc -c main.c -o main.o
```

手写小项目时可以这么做。项目大了以后，手动维护头文件依赖会很累，后面会介绍自动生成依赖文件。

## 五、添加变量

重复写 `gcc` 和编译参数很麻烦。Makefile 支持变量：

```makefile
CC = gcc
CFLAGS = -Wall -Wextra -g

app: main.o math_utils.o
	$(CC) main.o math_utils.o -o app

main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c main.c -o main.o

math_utils.o: math_utils.c math_utils.h
	$(CC) $(CFLAGS) -c math_utils.c -o math_utils.o
```

变量使用 `$(变量名)` 引用。

常见变量如下：

| 变量 | 常见含义 |
| ---- | -------- |
| `CC` | C 编译器 |
| `CXX` | C++ 编译器 |
| `CFLAGS` | C 编译选项 |
| `CXXFLAGS` | C++ 编译选项 |
| `CPPFLAGS` | 预处理选项，例如 `-Iinclude`、`-DDEBUG` |
| `LDFLAGS` | 链接器选项，例如 `-Llib` |
| `LDLIBS` | 链接库，例如 `-lm`、`-lpthread` |

例如项目头文件放在 `include` 目录：

```makefile
CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -Wall -Wextra -g

app: main.o math_utils.o
	$(CC) main.o math_utils.o -o app

main.o: src/main.c include/math_utils.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -c src/main.c -o main.o

math_utils.o: src/math_utils.c include/math_utils.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -c src/math_utils.c -o math_utils.o
```

`CPPFLAGS` 这个名字容易误会。它不是 C++ flags，而是 C PreProcessor flags，也就是预处理器选项。C++ 编译选项通常叫 `CXXFLAGS`。名字取得有点历史包袱，但历史包袱这种东西，从来不会主动为后来者体贴。

## 六、伪目标

有些目标并不是真的要生成一个文件。例如我们希望运行：

```bash
make clean
```

来删除构建产物：

```makefile
clean:
	rm -f app main.o math_utils.o
```

这里的 `clean` 不是一个真正的文件，而是一个任务。

建议把它声明为伪目标：

```makefile
.PHONY: clean

clean:
	rm -f app main.o math_utils.o
```

为什么需要 `.PHONY`？

如果当前目录下刚好有一个名为 `clean` 的文件，`make clean` 会认为目标文件已经存在，而且可能不需要执行命令。声明 `.PHONY` 后，`make` 会知道 `clean` 是任务名，不是文件名。

常见伪目标包括：

```makefile
.PHONY: all clean run test
```

例如：

```makefile
.PHONY: all clean run

all: app

run: app
	./app

clean:
	rm -f app main.o math_utils.o
```

这样就可以运行：

```bash
make
make run
make clean
```

通常会把 `all` 放在第一个目标：

```makefile
all: app
```

这样默认执行 `make` 时，构建的就是完整项目。

## 七、自动变量

Makefile 提供了一些自动变量，可以减少重复。

| 自动变量 | 含义 |
| -------- | ---- |
| `$@` | 当前目标 |
| `$<` | 第一个依赖 |
| `$^` | 所有依赖，去重 |
| `$?` | 比目标更新的依赖 |

例如：

```makefile
main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c $< -o $@
```

这里：

- `$@` 是 `main.o`
- `$<` 是 `main.c`

链接规则也可以写成：

```makefile
app: main.o math_utils.o
	$(CC) $^ -o $@
```

这里：

- `$@` 是 `app`
- `$^` 是 `main.o math_utils.o`

于是 Makefile 可以变成：

```makefile
CC = gcc
CFLAGS = -Wall -Wextra -g

.PHONY: all clean run

all: app

app: main.o math_utils.o
	$(CC) $^ -o $@

main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c $< -o $@

math_utils.o: math_utils.c math_utils.h
	$(CC) $(CFLAGS) -c $< -o $@

run: app
	./app

clean:
	rm -f app main.o math_utils.o
```

这已经是一份可以用的小型 Makefile。

## 八、模式规则

如果源文件很多，每个 `.c` 到 `.o` 都手写一条规则还是重复：

```makefile
main.o: main.c
	$(CC) $(CFLAGS) -c main.c -o main.o

student.o: student.c
	$(CC) $(CFLAGS) -c student.c -o student.o

math_utils.o: math_utils.c
	$(CC) $(CFLAGS) -c math_utils.c -o math_utils.o
```

这时可以使用模式规则：

```makefile
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@
```

含义是：

```text
任何 .o 文件都可以由同名 .c 文件编译得到。
```

完整例子：

```makefile
CC = gcc
CFLAGS = -Wall -Wextra -g

TARGET = app
OBJS = main.o math_utils.o student.o

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $^ -o $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET) $(OBJS)
```

这比逐个文件写规则舒服得多。可惜，舒服不等于可以放松警惕。这个版本没有处理头文件依赖。如果头文件变了，相关 `.o` 可能不会自动重新编译。

## 九、目录结构稍微正规一点

现实项目往往不把所有文件都放在根目录，而是分成：

```text
project/
  Makefile
  include/
    math_utils.h
    student.h
  src/
    main.c
    math_utils.c
    student.c
  build/
```

希望构建产物放到 `build` 目录：

```text
build/
  main.o
  math_utils.o
  student.o
  app
```

可以这样写：

```makefile
CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -Wall -Wextra -g

TARGET = build/app
SRCS = src/main.c src/math_utils.c src/student.c
OBJS = $(SRCS:src/%.c=build/%.o)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $^ -o $@

build/%.o: src/%.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build
```

这一行比较关键：

```makefile
OBJS = $(SRCS:src/%.c=build/%.o)
```

它把：

```text
src/main.c
src/math_utils.c
src/student.c
```

转换成：

```text
build/main.o
build/math_utils.o
build/student.o
```

这种替换语法在 Makefile 中很常见。刚开始觉得别扭很正常。Makefile 的语法不像现代语言那样体贴，它更像一件经久耐用但说明书泛黄的工具。

## 十、自动生成头文件依赖

前面的 Makefile 还有一个问题：没有记录头文件依赖。

如果 `src/main.c` 包含了 `include/math_utils.h`，那么 `include/math_utils.h` 改动时，`build/main.o` 应该重新编译。

手写依赖可以，但大项目会很烦。GCC 和 Clang 支持用 `-MMD -MP` 自动生成依赖文件。

```makefile
CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -Wall -Wextra -g
DEPFLAGS = -MMD -MP

TARGET = build/app
SRCS = src/main.c src/math_utils.c src/student.c
OBJS = $(SRCS:src/%.c=build/%.o)
DEPS = $(OBJS:.o=.d)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $^ -o $@

build/%.o: src/%.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build

-include $(DEPS)
```

编译时会生成：

```text
build/main.o
build/main.d
build/math_utils.o
build/math_utils.d
```

`.d` 文件里记录了源文件依赖哪些头文件。`make` 下次运行时会读取这些依赖。

最后一行：

```makefile
-include $(DEPS)
```

表示包含依赖文件。前面的 `-` 表示如果文件不存在也不要报错。第一次构建时 `.d` 文件还没生成，所以这里必须允许它不存在。

`-MMD` 和 `-MP` 的大致作用：

| 参数 | 含义 |
| ---- | ---- |
| `-MMD` | 生成用户头文件依赖，通常不包含系统头文件 |
| `-MP` | 为头文件生成伪目标，避免删除头文件后 make 报错 |

这是一份小项目里比较实用的 Makefile。

## 十一、C++ 项目的 Makefile

C++ 项目只需要把编译器和后缀换掉：

```text
project/
  Makefile
  include/
    calculator.hpp
  src/
    main.cpp
    calculator.cpp
```

Makefile：

```makefile
CXX = g++
CPPFLAGS = -Iinclude
CXXFLAGS = -Wall -Wextra -g -std=c++17
DEPFLAGS = -MMD -MP

TARGET = build/app
SRCS = src/main.cpp src/calculator.cpp
OBJS = $(SRCS:src/%.cpp=build/%.o)
DEPS = $(OBJS:.o=.d)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $^ -o $@

build/%.o: src/%.cpp
	mkdir -p build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(DEPFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build

-include $(DEPS)
```

注意链接时也使用 `$(CXX)`，不要用 `$(CC)`：

```makefile
$(TARGET): $(OBJS)
	$(CXX) $^ -o $@
```

因为 C++ 程序通常需要链接 C++ 标准库。用 `g++` 或 `clang++` 作为编译器驱动程序时，它会自动处理这些默认链接项。

如果你用 `gcc` 去链接 C++ 目标文件，可能会看到类似错误：

```text
undefined reference to `std::cout'
```

这不是 `iostream` 坏了，也不是世界有意与你为难。只是链接命令选错了。

## 十二、链接第三方库

假设 C 程序使用数学库里的 `sqrt`：

```c
#include <math.h>
#include <stdio.h>

int main(void) {
    printf("%f\n", sqrt(9.0));
    return 0;
}
```

在一些系统上，需要链接 `libm`：

```bash
gcc main.c -lm -o app
```

Makefile 中可以写：

```makefile
CC = gcc
CFLAGS = -Wall -Wextra -g
LDLIBS = -lm

app: main.o
	$(CC) $^ $(LDLIBS) -o $@

main.o: main.c
	$(CC) $(CFLAGS) -c $< -o $@
```

库选项的位置也值得注意。对很多链接器来说，被依赖的库应该放在使用它的目标文件后面：

```bash
gcc main.o -lm -o app
```

而不是：

```bash
gcc -lm main.o -o app
```

现代工具链有时没那么严格，但最好从一开始就养成正确习惯。

## 十三、调试版和发布版

可以通过变量切换编译参数：

```makefile
CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -Wall -Wextra
DEPFLAGS = -MMD -MP

BUILD ?= debug

ifeq ($(BUILD),debug)
	CFLAGS += -g -O0
else ifeq ($(BUILD),release)
	CFLAGS += -O2 -DNDEBUG
else
	$(error Unknown BUILD mode: $(BUILD))
endif

TARGET = build/$(BUILD)/app
SRCS = src/main.c src/math_utils.c
OBJS = $(SRCS:src/%.c=build/$(BUILD)/%.o)
DEPS = $(OBJS:.o=.d)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $^ -o $@

build/$(BUILD)/%.o: src/%.c
	mkdir -p build/$(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build

-include $(DEPS)
```

默认构建调试版：

```bash
make
```

构建发布版：

```bash
make BUILD=release
```

`?=` 表示如果外部没有设置 `BUILD`，才使用默认值：

```makefile
BUILD ?= debug
```

这能让命令行参数覆盖 Makefile 中的默认值。

## 十四、Windows 上的注意点

Makefile 常见于 Linux、macOS 和类 Unix 环境。在 Windows 上也能使用，但要注意你使用的是哪套工具链和 shell。

常见组合包括：

| 环境 | 编译器 | make 工具 |
| ---- | ------ | --------- |
| MSYS2 / MinGW | `gcc`、`g++` | `make` 或 `mingw32-make` |
| WSL | `gcc`、`g++` | `make` |
| Visual Studio | `cl` | 通常使用 MSBuild 或 CMake |

如果你使用 MinGW，清理命令可以写：

```makefile
clean:
	rm -rf build
```

但如果在纯 Windows `cmd` 环境里，`rm` 不一定存在。此时就要改成 Windows 命令，或者使用 CMake、MSBuild 等更适合该环境的构建方式。

Makefile 本身不负责提供跨平台 shell。它只是执行命令。命令能不能运行，取决于当前环境。

## 十五、常见错误

### missing separator

错误类似：

```text
Makefile:5: *** missing separator.  Stop.
```

常见原因是命令前面用了空格，而不是 Tab：

```makefile
app: main.c
    gcc main.c -o app
```

应该写成：

```makefile
app: main.c
	gcc main.c -o app
```

Markdown 里不容易看出 Tab 和空格的区别，所以实际编辑时建议打开编辑器的空白字符显示。

### undefined reference

例如：

```text
undefined reference to `add'
```

这通常是链接阶段找不到函数定义。可能原因包括：

- 少编译了某个 `.c` 或 `.cpp`
- 生成了 `.o`，但链接时没有把它传进去
- 静态库或动态库没有链接
- C 和 C++ 混合时缺少 `extern "C"`

Makefile 层面重点检查：

```makefile
OBJS = main.o math_utils.o
```

是否漏掉了实现文件对应的目标文件。

### No rule to make target

错误类似：

```text
make: *** No rule to make target 'build/main.o', needed by 'build/app'.  Stop.
```

意思是 `make` 需要生成 `build/main.o`，但找不到对应规则。

常见原因包括：

- 源文件路径写错
- 模式规则不匹配
- 后缀写错，例如实际是 `.cpp`，规则却写 `%.c`
- 变量替换结果不符合预期

可以用下面命令观察变量展开：

```bash
make -n
```

`-n` 表示只打印将要执行的命令，不真正执行。它适合检查 Makefile 到底准备做什么。

### 头文件修改后没有重新编译

如果改了 `.h` 或 `.hpp`，但 `.o` 没有重新生成，通常是头文件依赖没有写进去。

解决方式：

- 小项目手写头文件依赖
- 稍大项目使用 `-MMD -MP` 生成 `.d` 文件

## 十六、一份推荐模板

C 项目可以从这份模板开始：

```makefile
CC = gcc
CPPFLAGS = -Iinclude
CFLAGS = -Wall -Wextra -g
DEPFLAGS = -MMD -MP

TARGET = build/app
SRCS = src/main.c src/math_utils.c src/student.c
OBJS = $(SRCS:src/%.c=build/%.o)
DEPS = $(OBJS:.o=.d)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $^ -o $@

build/%.o: src/%.c
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build

-include $(DEPS)
```

C++ 项目可以从这份模板开始：

```makefile
CXX = g++
CPPFLAGS = -Iinclude
CXXFLAGS = -Wall -Wextra -g -std=c++17
DEPFLAGS = -MMD -MP

TARGET = build/app
SRCS = src/main.cpp src/calculator.cpp
OBJS = $(SRCS:src/%.cpp=build/%.o)
DEPS = $(OBJS:.o=.d)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $^ -o $@

build/%.o: src/%.cpp
	mkdir -p build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(DEPFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf build

-include $(DEPS)
```

这不是唯一正确答案，但它覆盖了初学阶段最重要的能力：

- 源文件编译成目标文件
- 目标文件链接成可执行文件
- 使用变量管理参数
- 支持头文件搜索路径
- 支持增量构建
- 支持自动头文件依赖
- 支持清理和运行

## 十七、Makefile 和 CMake 的关系

Makefile 是构建脚本。你直接写规则，告诉 `make` 如何构建。

CMake 则更像构建系统生成器。你写 `CMakeLists.txt`，然后 CMake 根据平台和生成器生成实际构建文件：

```text
CMakeLists.txt
  -> Unix Makefiles
  -> Ninja
  -> Visual Studio solution
  -> Xcode project
```

所以二者不是简单的替代关系：

| 工具 | 角色 |
| ---- | ---- |
| Makefile | 直接描述构建规则 |
| Make | 执行 Makefile |
| CMake | 生成构建系统 |
| Ninja | 执行 Ninja 构建文件 |

小项目手写 Makefile 很好，能帮助你理解编译和链接。跨平台项目、多人协作项目、依赖复杂的项目，通常更适合使用 CMake。

## 十八、总结

Makefile 的核心并不复杂：

```makefile
目标: 依赖
	命令
```

真正需要理解的是它背后的构建模型：

```text
.c / .cpp
  -> .o
  -> 可执行文件
```

以及依赖关系：

```text
源文件依赖头文件
可执行文件依赖目标文件
```

只要把这两件事想清楚，Makefile 就不再是一堆神秘符号，而是一张构建流程图。它确实古老，语法也不算亲切，但在理解 C/C++ 工程构建这件事上，它仍然是很好的入门工具。
