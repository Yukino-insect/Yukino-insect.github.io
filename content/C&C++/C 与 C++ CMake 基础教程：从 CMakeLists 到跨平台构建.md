+++
date = '2026-08-23T01:20:00+08:00'
draft = false
title = 'C 与 C++ CMake 基础教程：从 CMakeLists 到跨平台构建'
+++

C/C++ 项目一旦稍微复杂，就会遇到构建问题：

```text
project/
  include/
    math_utils.h
  src/
    main.cpp
    math_utils.cpp
```

你可以手写命令：

```bash
g++ -Iinclude src/main.cpp src/math_utils.cpp -o app
```

也可以写 Makefile：

```makefile
app: src/main.cpp src/math_utils.cpp
	g++ -Iinclude src/main.cpp src/math_utils.cpp -o app
```

但如果你希望同一个项目能在不同平台、不同 IDE、不同构建工具里使用，就会发现手写 Makefile 不够方便。

例如：

- Linux 上想用 Make
- Windows 上想用 Visual Studio
- macOS 上想用 Xcode
- CI 里想用 Ninja
- 项目里还有静态库、动态库、测试、安装规则

这时 CMake 就登场了。

CMake 不是编译器，也不是 Make 的简单替代品。它更准确的身份是：**构建系统生成器**。

你写：

```text
CMakeLists.txt
```

CMake 生成：

```text
Makefile
Ninja build files
Visual Studio solution
Xcode project
```

然后真正执行构建的是 Make、Ninja、MSBuild 这些后端工具。CMake 负责把项目结构、编译选项、依赖关系翻译成对应平台能理解的构建文件。

这篇文章讲 C/C++ 项目最基础、最实用的 CMake 用法。

## 一、先准备一个最小项目

目录结构：

```text
hello-cmake/
  CMakeLists.txt
  main.cpp
```

`main.cpp`：

```cpp
#include <iostream>

int main() {
    std::cout << "hello cmake\n";
    return 0;
}
```

`CMakeLists.txt`：

```cmake
cmake_minimum_required(VERSION 3.16)

project(HelloCMake LANGUAGES CXX)

add_executable(app main.cpp)
```

这就是最小可用的 CMake 项目。

各行含义如下：

```cmake
cmake_minimum_required(VERSION 3.16)
```

声明项目需要的最低 CMake 版本。它不仅是版本检查，也会影响 CMake 策略行为。新项目应该明确写这一行，不要让 CMake 猜你的意图。猜测这种事，在构建系统里通常没有好结果。

```cmake
project(HelloCMake LANGUAGES CXX)
```

声明项目名，并启用 C++ 语言。

```cmake
add_executable(app main.cpp)
```

声明生成一个可执行文件 `app`，它由 `main.cpp` 编译链接得到。

## 二、配置、构建、运行

CMake 通常采用 out-of-source build，也就是把构建产物放到源码目录之外的 `build` 目录。

在项目根目录执行：

```bash
cmake -S . -B build
```

含义是：

| 参数 | 含义 |
| ---- | ---- |
| `-S .` | 源码目录是当前目录 |
| `-B build` | 构建目录是 `build` |

然后构建：

```bash
cmake --build build
```

运行程序：

```bash
./build/app
```

在 Windows 的 Visual Studio 生成器下，可执行文件可能在配置子目录里，例如：

```text
build/Debug/app.exe
build/Release/app.exe
```

这不是 CMake 出错，而是不同生成器的目录习惯不同。

推荐记住这两条命令：

```bash
cmake -S . -B build
cmake --build build
```

它们比进入 `build` 目录再运行一堆命令更清楚，也更适合脚本和 CI。

## 三、CMake 的两个阶段

CMake 使用时通常分成两个阶段：

```text
配置阶段 configure
  读取 CMakeLists.txt
  检测编译器
  生成构建系统

构建阶段 build
  调用 Make / Ninja / MSBuild 等工具
  真正编译和链接
```

对应命令：

```bash
cmake -S . -B build
cmake --build build
```

第一次运行 `cmake -S . -B build` 时，CMake 会在 `build` 目录里生成缓存文件：

```text
build/CMakeCache.txt
```

这个文件记录了编译器、构建类型、选项等配置。之后再次配置时，CMake 会复用缓存。

如果你更换了编译器、生成器，或者配置变得很混乱，最简单的处理方式是删除 `build` 目录后重新配置：

```bash
rm -rf build
cmake -S . -B build
```

在 PowerShell 中可以使用：

```powershell
Remove-Item -Recurse -Force build
cmake -S . -B build
```

构建目录本来就是可再生的产物，不应该提交到 Git。

## 四、添加多个源文件

现在把项目改成：

```text
hello-cmake/
  CMakeLists.txt
  include/
    math_utils.hpp
  src/
    main.cpp
    math_utils.cpp
```

`include/math_utils.hpp`：

```cpp
#ifndef MATH_UTILS_HPP
#define MATH_UTILS_HPP

int add(int a, int b);

#endif
```

`src/math_utils.cpp`：

```cpp
#include "math_utils.hpp"

int add(int a, int b) {
    return a + b;
}
```

`src/main.cpp`：

```cpp
#include "math_utils.hpp"

#include <iostream>

int main() {
    std::cout << add(1, 2) << '\n';
    return 0;
}
```

`CMakeLists.txt`：

```cmake
cmake_minimum_required(VERSION 3.16)

project(HelloCMake LANGUAGES CXX)

add_executable(app
    src/main.cpp
    src/math_utils.cpp
)

target_include_directories(app PRIVATE include)
```

新增的关键行是：

```cmake
target_include_directories(app PRIVATE include)
```

它等价于告诉编译器添加头文件搜索路径：

```bash
-Iinclude
```

但在 CMake 中，我们不直接把 `-Iinclude` 塞进全局变量，而是把它绑定到目标 `app` 上。

这就是现代 CMake 的重要习惯：**围绕 target 组织项目。**

## 五、target 是现代 CMake 的核心

在 CMake 里，`target` 可以是：

- 可执行文件
- 静态库
- 动态库
- 只提供接口的头文件库

例如：

```cmake
add_executable(app src/main.cpp)
```

创建了一个名为 `app` 的可执行目标。

```cmake
add_library(math_utils src/math_utils.cpp)
```

创建了一个名为 `math_utils` 的库目标。

现代 CMake 推荐使用一系列 `target_*` 命令：

| 命令 | 作用 |
| ---- | ---- |
| `target_sources` | 给目标添加源文件 |
| `target_include_directories` | 给目标添加头文件搜索路径 |
| `target_compile_features` | 给目标声明语言特性 |
| `target_compile_options` | 给目标添加编译选项 |
| `target_compile_definitions` | 给目标添加宏定义 |
| `target_link_libraries` | 给目标链接库 |

不要一开始就依赖大量全局命令，例如：

```cmake
include_directories(include)
add_definitions(-DDEBUG)
```

它们会影响当前目录及子目录中的许多目标，项目大了以后很难判断某个选项到底从哪里来的。全局状态这种东西，用起来很方便，查起来很狼狈。

## 六、拆出一个库

更合理的项目结构通常是：

```text
hello-cmake/
  CMakeLists.txt
  include/
    math_utils.hpp
  src/
    main.cpp
    math_utils.cpp
```

我们可以把 `math_utils.cpp` 编译成库，再让 `app` 链接它：

```cmake
cmake_minimum_required(VERSION 3.16)

project(HelloCMake LANGUAGES CXX)

add_library(math_utils
    src/math_utils.cpp
)

target_include_directories(math_utils
    PUBLIC
        include
)

add_executable(app
    src/main.cpp
)

target_link_libraries(app
    PRIVATE
        math_utils
)
```

这里出现了两个目标：

- `math_utils`：库
- `app`：可执行文件

关系是：

```text
app -> math_utils
```

也就是 `app` 链接 `math_utils`。

## 七、PUBLIC、PRIVATE、INTERFACE

CMake 中最容易让初学者皱眉的关键字之一就是：

```cmake
PUBLIC
PRIVATE
INTERFACE
```

它们表示属性的传播范围。

先看这段：

```cmake
target_include_directories(math_utils
    PUBLIC
        include
)
```

`math_utils` 的头文件在 `include` 目录下。

而 `app` 的 `main.cpp` 也包含了：

```cpp
#include "math_utils.hpp"
```

所以 `app` 编译时也需要知道 `include` 路径。

使用 `PUBLIC` 表示：

```text
math_utils 自己需要 include
链接 math_utils 的目标也需要 include
```

如果写成：

```cmake
target_include_directories(math_utils
    PRIVATE
        include
)
```

含义就变成：

```text
只有 math_utils 自己需要 include
链接 math_utils 的目标不需要 include
```

这样 `app` 编译 `src/main.cpp` 时可能找不到 `math_utils.hpp`。

三个关键字可以这样理解：

| 关键字 | 当前目标使用 | 依赖它的目标使用 |
| ------ | ------------ | ---------------- |
| `PRIVATE` | 是 | 否 |
| `PUBLIC` | 是 | 是 |
| `INTERFACE` | 否 | 是 |

常见用法：

- 源文件自己的内部头文件路径，用 `PRIVATE`
- 库的公开头文件路径，用 `PUBLIC`
- 纯头文件库的使用要求，用 `INTERFACE`

这三个词不是装饰，它们决定了依赖关系是否能正确传播。

## 八、声明 C++ 标准

很多教程会这样写：

```cmake
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
```

这能用，但它是偏全局的写法。

现代 CMake 更推荐对目标声明需要的语言特性：

```cmake
target_compile_features(math_utils PUBLIC cxx_std_17)
target_compile_features(app PRIVATE cxx_std_17)
```

如果 `math_utils` 的公开头文件使用了 C++17 特性，那么应该写：

```cmake
target_compile_features(math_utils PUBLIC cxx_std_17)
```

因为使用 `math_utils` 的目标也需要按 C++17 或更高标准编译。

如果只有 `app` 自己的 `.cpp` 使用了 C++17，则可以写：

```cmake
target_compile_features(app PRIVATE cxx_std_17)
```

完整示例：

```cmake
cmake_minimum_required(VERSION 3.16)

project(HelloCMake LANGUAGES CXX)

add_library(math_utils
    src/math_utils.cpp
)

target_include_directories(math_utils
    PUBLIC
        include
)

target_compile_features(math_utils
    PUBLIC
        cxx_std_17
)

add_executable(app
    src/main.cpp
)

target_link_libraries(app
    PRIVATE
        math_utils
)
```

这样比单纯设置全局 `CMAKE_CXX_STANDARD` 更能表达依赖关系。

## 九、添加编译警告

可以给目标添加编译选项：

```cmake
target_compile_options(app
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
)
```

但这里有一个跨平台问题：GCC / Clang 和 MSVC 的参数不同。

GCC / Clang 常用：

```text
-Wall -Wextra -Wpedantic
```

MSVC 常用：

```text
/W4
```

可以用编译器 ID 判断：

```cmake
if(MSVC)
    target_compile_options(app PRIVATE /W4)
else()
    target_compile_options(app PRIVATE -Wall -Wextra -Wpedantic)
endif()
```

如果多个目标都需要相同警告选项，可以创建一个接口库：

```cmake
add_library(project_warnings INTERFACE)

if(MSVC)
    target_compile_options(project_warnings INTERFACE /W4)
else()
    target_compile_options(project_warnings INTERFACE -Wall -Wextra -Wpedantic)
endif()

target_link_libraries(math_utils PRIVATE project_warnings)
target_link_libraries(app PRIVATE project_warnings)
```

`project_warnings` 不会生成真实库文件，它只是携带使用要求。这个技巧在中型项目里很常见。

## 十、Debug 和 Release

配置构建类型：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
```

或者：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

常见构建类型：

| 类型 | 常见含义 |
| ---- | -------- |
| `Debug` | 带调试信息，通常不开优化 |
| `Release` | 开启优化，通常不适合逐行调试 |
| `RelWithDebInfo` | 优化并保留调试信息 |
| `MinSizeRel` | 优化体积 |

不过要注意：`CMAKE_BUILD_TYPE` 主要用于单配置生成器，例如 Unix Makefiles、Ninja。

Visual Studio、Xcode 这类多配置生成器通常在构建时选择配置：

```bash
cmake -S . -B build
cmake --build build --config Debug
cmake --build build --config Release
```

所以跨平台脚本里经常会看到：

```bash
cmake --build build --config Release
```

即使在单配置生成器中这个参数未必必要。

## 十一、选择生成器

CMake 可以生成不同构建系统。查看当前机器支持哪些生成器：

```bash
cmake --help
```

配置时指定生成器：

```bash
cmake -S . -B build -G Ninja
```

或者：

```bash
cmake -S . -B build -G "Unix Makefiles"
```

Windows 上可能使用：

```bash
cmake -S . -B build -G "Visual Studio 17 2022"
```

构建时仍然可以使用统一命令：

```bash
cmake --build build
```

这就是 CMake 的一个实际价值：配置阶段可以选择生成器，构建阶段尽量使用统一入口。

## 十二、添加宏定义

假设代码中有：

```cpp
#ifdef DEBUG_LOG
std::cout << "debug log\n";
#endif
```

可以在 CMake 中添加宏定义：

```cmake
target_compile_definitions(app
    PRIVATE
        DEBUG_LOG
)
```

这相当于编译命令中的：

```bash
-DDEBUG_LOG
```

如果宏需要传值：

```cmake
target_compile_definitions(app
    PRIVATE
        APP_VERSION="1.0.0"
)
```

如果某个宏属于库的公开接口，需要传递给使用者，可以用 `PUBLIC` 或 `INTERFACE`。但这要谨慎。公开宏定义会影响依赖它的目标，滥用之后，问题会像墨水滴进水里一样扩散。

## 十三、静态库和动态库

创建库时可以写：

```cmake
add_library(math_utils STATIC
    src/math_utils.cpp
)
```

表示静态库。

也可以写：

```cmake
add_library(math_utils SHARED
    src/math_utils.cpp
)
```

表示动态库。

如果不写 `STATIC` 或 `SHARED`：

```cmake
add_library(math_utils
    src/math_utils.cpp
)
```

则会根据 `BUILD_SHARED_LIBS` 变量决定默认库类型。

配置动态库：

```bash
cmake -S . -B build -DBUILD_SHARED_LIBS=ON
```

配置静态库：

```bash
cmake -S . -B build -DBUILD_SHARED_LIBS=OFF
```

初学阶段如果没有明确需求，可以先不急着纠结静态库和动态库。更重要的是理解：

```text
库也是 target
可执行文件通过 target_link_libraries 依赖库
```

## 十四、C 项目的 CMake

C 项目写法也很相似：

```text
hello-cmake-c/
  CMakeLists.txt
  include/
    math_utils.h
  src/
    main.c
    math_utils.c
```

`CMakeLists.txt`：

```cmake
cmake_minimum_required(VERSION 3.16)

project(HelloCMakeC LANGUAGES C)

add_library(math_utils
    src/math_utils.c
)

target_include_directories(math_utils
    PUBLIC
        include
)

target_compile_features(math_utils
    PUBLIC
        c_std_11
)

add_executable(app
    src/main.c
)

target_link_libraries(app
    PRIVATE
        math_utils
)
```

C 标准可以使用：

```cmake
target_compile_features(math_utils PUBLIC c_std_11)
```

常见还有：

```cmake
c_std_99
c_std_11
c_std_17
```

如果目标使用 C++，则是：

```cmake
cxx_std_17
cxx_std_20
```

## 十五、源文件要不要用 glob

有些教程会写：

```cmake
file(GLOB SOURCES src/*.cpp)

add_executable(app ${SOURCES})
```

它能工作，但初学阶段更推荐显式列出源文件：

```cmake
add_executable(app
    src/main.cpp
    src/math_utils.cpp
)
```

原因是显式列表更清楚，也更容易让构建系统知道项目结构变了。

旧版本 CMake 中，新增源文件后 `GLOB` 不一定自动触发重新配置。新一些的 CMake 支持：

```cmake
file(GLOB CONFIGURE_DEPENDS SOURCES src/*.cpp)
```

但大型项目里仍然常见显式列源文件。构建配置是项目接口的一部分，清楚有时比省几行更有价值。

## 十六、子目录组织

项目大一点后，可以拆成多个 `CMakeLists.txt`。

目录结构：

```text
project/
  CMakeLists.txt
  src/
    CMakeLists.txt
    main.cpp
  math/
    CMakeLists.txt
    include/
      math_utils.hpp
    src/
      math_utils.cpp
```

根目录 `CMakeLists.txt`：

```cmake
cmake_minimum_required(VERSION 3.16)

project(DemoProject LANGUAGES CXX)

add_subdirectory(math)
add_subdirectory(src)
```

`math/CMakeLists.txt`：

```cmake
add_library(math_utils
    src/math_utils.cpp
)

target_include_directories(math_utils
    PUBLIC
        include
)

target_compile_features(math_utils
    PUBLIC
        cxx_std_17
)
```

`src/CMakeLists.txt`：

```cmake
add_executable(app
    main.cpp
)

target_link_libraries(app
    PRIVATE
        math_utils
)
```

`add_subdirectory` 会进入子目录读取那里的 `CMakeLists.txt`。这样每个模块可以管理自己的源文件、头文件路径和依赖关系。

不过不要为了拆而拆。两个源文件的小项目硬拆成十个目录，只会显得勤奋得很可疑。

## 十七、查找第三方库

CMake 常用 `find_package` 查找第三方库。

例如查找线程库：

```cmake
find_package(Threads REQUIRED)

add_executable(app src/main.cpp)

target_link_libraries(app
    PRIVATE
        Threads::Threads
)
```

这里的 `Threads::Threads` 是一个导入目标。它可能对应不同平台上的不同编译和链接参数。

再比如某些库安装后会提供 CMake 配置文件，可以这样查找：

```cmake
find_package(fmt REQUIRED)

target_link_libraries(app
    PRIVATE
        fmt::fmt
)
```

现代 CMake 中，优先链接这种 `命名空间::目标` 形式的库：

```text
fmt::fmt
Threads::Threads
OpenSSL::SSL
```

因为它们不仅包含库文件路径，还可能携带头文件路径、宏定义、编译选项等使用要求。也就是说，依赖不是一条孤零零的 `-lxxx`，而是一组完整的构建信息。

## 十八、安装规则入门

如果只是本地运行小程序，可以暂时不写安装规则。但库项目迟早会需要安装。

最简单的安装可执行文件：

```cmake
install(TARGETS app
    RUNTIME DESTINATION bin
)
```

安装库和头文件：

```cmake
install(TARGETS math_utils
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)
```

配置安装前缀：

```bash
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build
cmake --install build
```

Windows 上可以指定普通目录：

```powershell
cmake -S . -B build -DCMAKE_INSTALL_PREFIX=C:\tools\demo
cmake --build build --config Release
cmake --install build --config Release
```

安装规则是 CMake 的重要部分，但初学阶段先理解 `add_executable`、`add_library`、`target_link_libraries` 更实际。

## 十九、常见错误

### 找不到头文件

错误类似：

```text
fatal error: math_utils.hpp: No such file or directory
```

常见原因是没有添加头文件搜索路径：

```cmake
target_include_directories(app PRIVATE include)
```

如果头文件属于某个库的公开接口，更常见的是写在库目标上：

```cmake
target_include_directories(math_utils PUBLIC include)
```

然后让可执行文件链接库：

```cmake
target_link_libraries(app PRIVATE math_utils)
```

这样 `include` 路径会从 `math_utils` 传播到 `app`。

### undefined reference

错误类似：

```text
undefined reference to `add(int, int)'
```

常见原因是实现文件没有参与构建，或者库没有被链接。

错误写法：

```cmake
add_executable(app
    src/main.cpp
)
```

如果 `add` 定义在 `src/math_utils.cpp` 中，那就需要把它加入目标：

```cmake
add_executable(app
    src/main.cpp
    src/math_utils.cpp
)
```

或者拆成库：

```cmake
add_library(math_utils src/math_utils.cpp)
add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE math_utils)
```

### 改了 CMakeLists 但构建没变化

通常重新运行配置即可：

```bash
cmake -S . -B build
cmake --build build
```

多数情况下，`cmake --build build` 也会触发必要的重新配置。但当你更换生成器、编译器或缓存变量时，建议清理 `build` 后重新配置。

### 生成器和编译器混乱

例如第一次使用 Visual Studio 生成器配置了 `build`，后来又想用 Ninja 复用同一个 `build` 目录，可能会报错。

解决方式是换一个构建目录：

```bash
cmake -S . -B build-ninja -G Ninja
```

或者删除旧的 `build` 目录后重新配置。

一个构建目录通常只对应一种生成器。不要强迫它同时扮演几种身份，它会用报错表达拒绝。

## 二十、一份推荐模板

C++ 小项目可以从这份模板开始：

```cmake
cmake_minimum_required(VERSION 3.16)

project(DemoProject LANGUAGES CXX)

add_library(demo_lib
    src/demo.cpp
)

target_include_directories(demo_lib
    PUBLIC
        include
)

target_compile_features(demo_lib
    PUBLIC
        cxx_std_17
)

add_executable(app
    src/main.cpp
)

target_link_libraries(app
    PRIVATE
        demo_lib
)

if(MSVC)
    target_compile_options(demo_lib PRIVATE /W4)
    target_compile_options(app PRIVATE /W4)
else()
    target_compile_options(demo_lib PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(app PRIVATE -Wall -Wextra -Wpedantic)
endif()
```

如果暂时没有库，只是一个可执行文件，可以更简单：

```cmake
cmake_minimum_required(VERSION 3.16)

project(DemoProject LANGUAGES CXX)

add_executable(app
    src/main.cpp
    src/demo.cpp
)

target_include_directories(app
    PRIVATE
        include
)

target_compile_features(app
    PRIVATE
        cxx_std_17
)
```

构建命令：

```bash
cmake -S . -B build
cmake --build build
```

Release 构建：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

## 二十一、CMake 学习路线

初学 CMake 不需要一次掌握所有内容。比较合理的顺序是：

1. 会写 `cmake_minimum_required`、`project`
2. 会用 `add_executable` 构建可执行文件
3. 会用 `target_include_directories` 添加头文件路径
4. 会用 `add_library` 拆分库
5. 会用 `target_link_libraries` 表达依赖
6. 理解 `PUBLIC`、`PRIVATE`、`INTERFACE`
7. 会用 `target_compile_features` 声明 C/C++ 标准
8. 会区分配置阶段和构建阶段
9. 会使用 Debug / Release
10. 再学习 `find_package`、安装、测试、打包

前六项掌握之后，大多数小项目就已经够用了。

## 二十二、总结

CMake 的核心不是“把编译命令换一种写法”，而是围绕目标表达项目结构：

```cmake
add_library(math_utils src/math_utils.cpp)
target_include_directories(math_utils PUBLIC include)

add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE math_utils)
```

这几行背后表达的是：

```text
math_utils 是一个库
它的公开头文件在 include
app 是一个可执行文件
app 依赖 math_utils
依赖 math_utils 的目标也能获得必要的头文件路径和编译要求
```

这就是现代 CMake 的基本思想。

Makefile 更接近底层构建规则，适合理解编译和链接。CMake 更接近项目建模，适合跨平台和多人协作。二者都值得学，只是承担的角色不同。

如果你刚开始学习，先记住这一套命令：

```bash
cmake -S . -B build
cmake --build build
```

再记住这一套写法：

```cmake
add_library(...)
target_include_directories(...)
target_compile_features(...)
add_executable(...)
target_link_libraries(...)
```

够了。构建系统本来就不该抢走太多注意力。它最好的状态，是让源码安静、可靠地变成程序。
