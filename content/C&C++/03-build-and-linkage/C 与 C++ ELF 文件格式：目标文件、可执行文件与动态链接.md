+++
date = '2026-08-23T21:00:00+08:00'
draft = false
title = 'C 与 C++ ELF 文件格式：目标文件、可执行文件与动态链接'
+++

写 C/C++ 时，我们经常会看到这些文件：

```text
main.o
app
libmath.a
libmath.so
```

表面上它们只是“编译出来的文件”。但在 Linux 这类 Unix-like 系统上，目标文件、可执行文件、共享库、core dump，很多都遵循同一种二进制格式：**ELF**。

ELF 是 **Executable and Linkable Format** 的缩写。名字已经说得很清楚了：它既要服务“可执行”，也要服务“可链接”。

如果你只把 ELF 理解成“Linux 上的 exe”，那就太窄了。`.o` 目标文件通常也是 ELF，共享库 `.so` 通常也是 ELF，最终可执行程序通常也是 ELF。只是它们处在构建和运行链路的不同位置，承担的任务不同。

这篇文章从 C/C++ 工程视角理解 ELF：它里面有什么，链接器看什么，加载器看什么，为什么 `undefined reference`、`cannot open shared object file`、`not found` 这类问题经常和它有关。

先把结论放在前面：

**ELF 是 C/C++ 程序在 Linux 上从“编译产物”走向“可运行程序”的二进制容器。编译器、汇编器、链接器、操作系统内核和动态链接器都会在不同阶段读取它。**

## 一、ELF 解决什么问题

一个 C 程序很简单：

```c
#include <stdio.h>

int global_count = 10;

int add(int a, int b) {
    return a + b;
}

int main(void) {
    printf("%d\n", add(global_count, 20));
    return 0;
}
```

编译：

```bash
gcc -c main.c -o main.o
gcc main.o -o app
```

这里会出现两个重要文件：

```text
main.o  目标文件
app     可执行文件
```

它们都可能是 ELF：

```bash
file main.o
file app
```

可能看到类似输出：

```text
main.o: ELF 64-bit LSB relocatable, x86-64
app:    ELF 64-bit LSB pie executable, x86-64
```

这说明 ELF 不是单指最终程序。它是一种通用二进制格式，可以表达：

- 机器码放在哪里
- 全局变量初值放在哪里
- 哪些符号已经定义
- 哪些符号还没解析
- 哪些位置以后需要重定位
- 程序运行时需要哪些共享库
- 操作系统应该把哪些内容映射到内存
- 动态链接器应该如何修补地址

源码里写的是函数和变量。ELF 里保存的是更接近机器视角的信息。它不关心你写代码时的心情，甚至不太关心你的缩进，它只关心字节、地址、符号、权限和重定位。

这当然很冷淡，但很可靠。

## 二、ELF 常见文件类型

ELF 头里有一个字段叫 `e_type`，用来说明这个 ELF 文件是什么类型。

常见类型如下：

| 类型 | 含义 | 常见文件 |
| --- | --- | --- |
| `ET_REL` | 可重定位目标文件 | `.o` |
| `ET_EXEC` | 传统可执行文件 | 非 PIE 可执行程序 |
| `ET_DYN` | 共享对象 | `.so`、PIE 可执行程序 |
| `ET_CORE` | core dump | 程序崩溃后的 core 文件 |

可以用 `readelf` 查看：

```bash
readelf -h app
```

输出里会有类似字段：

```text
Type:                              DYN (Position-Independent Executable file)
Machine:                           Advanced Micro Devices X86-64
Entry point address:               0x1050
```

这里有一个容易误会的地方：现代 Linux 发行版默认常常生成 PIE，也就是 Position Independent Executable。PIE 可执行文件在 ELF 类型上通常是 `ET_DYN`，和共享库同类。

这不是说它“不是可执行文件”。它仍然可以运行，只是它被设计成可以加载到随机地址，配合 ASLR 提高安全性。

所以判断一个文件能不能执行，不能只粗暴地看 `ET_EXEC`。这类草率判断，适合制造困惑，不适合解决问题。

## 三、从源码到 ELF

C/C++ 构建链路可以这样看：

```text
main.c
  -> 预处理
  -> 编译
  -> 汇编
  -> main.o
  -> 链接
  -> app
```

其中：

- 编译器把 C/C++ 代码翻译成汇编或中间机器表示。
- 汇编器把汇编变成目标文件 `.o`。
- 链接器把多个 `.o` 和库组合成可执行文件或共享库。

目标文件 `.o` 还不能直接运行，因为它通常还有很多事情没完成：

- 函数调用目标地址可能还不知道。
- 外部变量地址可能还不知道。
- 引用的库函数可能还没解析。
- 某些代码和数据还需要被合并、排列、重定位。

例如：

```c
// main.c

int add(int a, int b);

int main(void) {
    return add(1, 2);
}
```

```c
// math.c

int add(int a, int b) {
    return a + b;
}
```

分别编译：

```bash
gcc -c main.c -o main.o
gcc -c math.c -o math.o
```

此时 `main.o` 里会记录：我需要一个叫 `add` 的符号，但它不在我这里。

链接：

```bash
gcc main.o math.o -o app
```

链接器找到 `math.o` 中的 `add` 定义，然后把 `main.o` 中对 `add` 的引用解析过去。

如果漏掉 `math.o`：

```bash
gcc main.o -o app
```

就可能报：

```text
undefined reference to `add'
```

这不是 ELF 坏了，也不是编译器突然失忆。只是目标文件里留下的“待解析符号”，在链接时没有找到对应定义。

## 四、ELF 的整体结构

一个 ELF 文件大致由这些部分组成：

```text
ELF Header
Program Header Table
Sections
Section Header Table
```

可以粗略画成这样：

```text
+------------------------+
| ELF Header             |
+------------------------+
| Program Header Table   |
+------------------------+
| .text                  |
| .rodata                |
| .data                  |
| .bss                   |
| .symtab                |
| .strtab                |
| .rela.text             |
| ...                    |
+------------------------+
| Section Header Table   |
+------------------------+
```

注意，这只是示意。真实 ELF 中各部分的顺序可以变化，某些表也可以不存在。

核心结构有三类：

- **ELF Header**：说明这个文件的基本身份。
- **Section Header Table**：描述节，主要服务链接器和分析工具。
- **Program Header Table**：描述段，主要服务操作系统加载器。

这里最容易混的是 section 和 segment。中文里常常都翻成“段”，于是读起来像一群概念在互相冒充亲戚。

为了避免混乱，本文统一这样叫：

- **section**：节。
- **segment**：段。

链接器主要看节。操作系统加载程序主要看段。

这一句很重要：

**节是链接视角，段是加载视角。**

## 五、ELF Header

ELF Header 在文件最开头，用来描述整个 ELF 文件。

可以查看：

```bash
readelf -h app
```

常见字段包括：

| 字段 | 含义 |
| --- | --- |
| `Magic` | ELF 魔数，通常以 `7f 45 4c 46` 开头 |
| `Class` | 32 位还是 64 位 |
| `Data` | 大端还是小端 |
| `Type` | ELF 文件类型 |
| `Machine` | 目标架构，例如 x86-64、AArch64 |
| `Entry point address` | 程序入口地址 |
| `Start of program headers` | Program Header Table 在文件中的偏移 |
| `Start of section headers` | Section Header Table 在文件中的偏移 |

ELF 魔数中的 `45 4c 46` 对应 ASCII：

```text
E L F
```

所以一个 ELF 文件开头通常是：

```text
7f 45 4c 46
```

可以用 `xxd` 看：

```bash
xxd -l 16 app
```

如果一个文件不是 ELF，Linux 内核当然不会按 ELF 的规则去加载它。操作系统没有义务理解你想让它理解的东西，它只理解格式。

## 六、section：链接器眼中的文件

section 是 ELF 中按功能划分的节。

查看节表：

```bash
readelf -S app
```

常见节如下：

| 节 | 作用 |
| --- | --- |
| `.text` | 机器指令 |
| `.rodata` | 只读数据，例如字符串字面量 |
| `.data` | 已初始化的全局变量和静态变量 |
| `.bss` | 未初始化或零初始化的全局变量和静态变量 |
| `.symtab` | 完整符号表，常用于链接和调试分析 |
| `.strtab` | `.symtab` 使用的字符串表 |
| `.dynsym` | 动态链接需要的符号表 |
| `.dynstr` | `.dynsym` 使用的字符串表 |
| `.rela.text` | 针对 `.text` 的重定位信息 |
| `.plt` | Procedure Linkage Table，过程链接表 |
| `.got` | Global Offset Table，全局偏移表 |
| `.dynamic` | 动态链接信息 |
| `.init_array` | 程序初始化函数数组 |
| `.fini_array` | 程序结束时调用的函数数组 |
| `.eh_frame` | 异常处理和栈展开信息 |

用一个小例子看这些节从哪里来：

```c
#include <stdio.h>

const char *message = "hello";
int global_value = 42;
static int zero_value;

void print_message(void) {
    printf("%s %d %d\n", message, global_value, zero_value);
}
```

大致对应关系：

| 源码内容 | 可能进入的 ELF 节 |
| --- | --- |
| `print_message` 的机器码 | `.text` |
| 字符串字面量 `"hello"` | `.rodata` |
| `global_value = 42` | `.data` |
| `zero_value` | `.bss` |
| `printf` 的外部引用 | 符号表和重定位节 |

这里的“可能”不是客气话。具体放在哪里会受编译器、优化级别、目标平台、链接参数影响。

例如字符串字面量一般放在只读区域，但优化后是否合并、是否出现独立符号，就不该用单一例子当作宇宙真理。

## 七、`.bss` 为什么不占文件空间

`.bss` 用来表示未初始化或零初始化的静态存储期对象：

```c
int global_a;
static int global_b;
int global_c = 0;
```

它们运行时应该是 0，但 ELF 文件里没必要真的存一大堆 0。

例如：

```c
char buffer[1024 * 1024 * 100];
```

如果把 100MB 的 0 都写进可执行文件，那就很可笑。程序还没运行，磁盘先开始替你的偷懒付账。

ELF 可以只记录：

```text
这里需要一块大小为 100MB 的零初始化内存
```

加载时由操作系统把对应内存清零即可。

这也是为什么 `size` 命令会把程序分成：

```bash
size app
```

类似输出：

```text
   text    data     bss     dec     hex filename
   1400     584 1048576 1050560  100780 app
```

其中：

- `text`：代码和只读数据等。
- `data`：已初始化数据。
- `bss`：运行时需要的零初始化数据。

`.bss` 会影响程序运行时内存占用，但通常不会等量增加 ELF 文件大小。

## 八、symbol：链接器如何认识名字

C/C++ 源码里有函数名、变量名。编译成目标文件后，这些名字会变成符号。

查看符号：

```bash
nm main.o
```

或者：

```bash
readelf -s main.o
```

可能看到：

```text
0000000000000000 T main
                 U add
```

含义是：

- `T main`：`main` 定义在代码节中。
- `U add`：`add` 是未定义符号，需要链接时从别处找。

`nm` 常见符号类型：

| 标记 | 含义 |
| --- | --- |
| `T/t` | 代码节中的符号 |
| `D/d` | 已初始化数据符号 |
| `B/b` | BSS 符号 |
| `R/r` | 只读数据符号 |
| `U` | 未定义符号 |

大小写通常和符号可见性有关。大写一般表示外部可见，小写一般表示局部符号。具体细节要看平台和工具输出说明，但作为排查直觉已经够用。

例如：

```c
int public_value = 1;
static int private_value = 2;

void public_func(void) {}
static void private_func(void) {}
```

编译后：

```bash
gcc -c demo.c -o demo.o
nm demo.o
```

可能看到：

```text
0000000000000000 T public_func
0000000000000000 D public_value
0000000000000007 t private_func
0000000000000004 d private_value
```

`static` 修饰的文件作用域函数和变量具有内部链接性，所以通常表现为局部符号。

C++ 还会有名字改编，也就是 name mangling：

```cpp
void print(int) {}
void print(double) {}
```

因为 C++ 支持函数重载，二进制符号名不能都叫 `print`。可以用：

```bash
nm demo.o
nm -C demo.o
```

`-C` 会尝试把 C++ 改编后的符号名还原成人类比较能读的形式。

这也是 C 和 C++ 混合编程时经常需要 `extern "C"` 的原因：它告诉 C++ 编译器对指定接口使用 C 风格链接名，避免链接器找不到名字。

## 九、relocation：为什么目标文件还要重定位

目标文件 `.o` 通常不知道自己最终会被放到哪里。

比如 `main.o` 中调用 `add`：

```c
int add(int a, int b);

int main(void) {
    return add(1, 2);
}
```

编译 `main.c` 时，编译器只知道：

```text
这里要调用 add
```

但 `add` 最终地址是多少，要等链接器把多个目标文件组合之后才知道。

于是 ELF 目标文件里会留下重定位信息：

```bash
readelf -r main.o
```

可能看到类似：

```text
Relocation section '.rela.text' contains entries:
  Offset          Info           Type              Sym. Name
  00000000000a    ...            R_X86_64_PLT32    add
```

这表示：

- 在 `.text` 的某个偏移处，有一段机器码需要修补。
- 修补方式是某种 x86-64 重定位类型。
- 它关联的符号是 `add`。

链接器最终会根据符号地址，把这些待修补位置改成正确的值。

常见 x86-64 重定位类型包括：

| 类型 | 大致含义 |
| --- | --- |
| `R_X86_64_PC32` | 基于程序计数器的 32 位相对寻址 |
| `R_X86_64_PLT32` | 通过 PLT 调用函数 |
| `R_X86_64_GLOB_DAT` | 为全局数据符号设置 GOT 项 |
| `R_X86_64_JUMP_SLOT` | 为动态函数调用修补 GOT/PLT |
| `R_X86_64_RELATIVE` | 按加载基址调整地址 |

不需要一开始背完这些名字。先理解一件事就够了：

**重定位就是把编译时还不能确定的地址，在链接或加载时补上。**

有些重定位发生在静态链接阶段，有些发生在程序加载阶段。不要把“链接器做的事”和“动态链接器做的事”混成一团，否则问题会变成一团，最后你也会变成一团。那并不优雅。

## 十、segment：操作系统如何加载程序

section 是链接视角，segment 是加载视角。

查看 program header：

```bash
readelf -l app
```

可能看到：

```text
Program Headers:
  Type           Offset   VirtAddr           FileSiz  MemSiz   Flags
  PHDR           0x000040 0x0000000000000040 0x0002d8 0x0002d8 R
  INTERP         0x000318 0x0000000000000318 0x00001c 0x00001c R
  LOAD           0x000000 0x0000000000000000 0x000650 0x000650 R
  LOAD           0x001000 0x0000000000001000 0x0001dd 0x0001dd R E
  LOAD           0x002000 0x0000000000002000 0x000124 0x000124 R
  LOAD           0x002dd0 0x0000000000003dd0 0x000248 0x000250 RW
  DYNAMIC        0x002de0 0x0000000000003de0 0x0001e0 0x0001e0 RW
```

重点看 `LOAD`。它表示需要映射进进程虚拟地址空间的内容。

一个可执行文件里可能有多个 `LOAD` segment，权限不同：

| 权限 | 常见内容 |
| --- | --- |
| `R` | 只读元数据、只读数据 |
| `R E` | 可读可执行代码 |
| `RW` | 可读可写数据 |

操作系统加载 ELF 时，不会逐个 section 思考人生。它主要看 program header，把 `PT_LOAD` 描述的文件区域映射到内存，并设置对应权限。

这也是 section 和 segment 的关键区别：

| 视角 | 主要使用者 | 作用 |
| --- | --- | --- |
| section | 链接器、调试器、分析工具 | 组织代码、数据、符号、重定位信息 |
| segment | 操作系统内核、动态链接器 | 描述运行时如何映射到内存 |

很多 section 会被合并进同一个 segment。

例如：

```text
.text + .plt
  -> R E LOAD segment

.rodata
  -> R LOAD segment

.data + .got
  -> RW LOAD segment
```

所以 `.text` 是节，不是操作系统最终按名字加载的单位。真正用于加载的是 `PT_LOAD` segment。

概念差一个词，排查时可能差半天。很遗憾，计算机不会因为你只差一点点就自动给分。

## 十一、可执行文件启动时发生了什么

运行：

```bash
./app
```

背后大致发生这些事：

```text
shell
  -> 调用 execve
  -> Linux 内核读取 ELF Header
  -> 内核读取 Program Header Table
  -> 映射 PT_LOAD segments
  -> 如果有 PT_INTERP，启动动态链接器
  -> 动态链接器加载共享库
  -> 执行动态重定位
  -> 调用初始化函数
  -> 跳到程序入口
  -> 进入 C 运行时
  -> 调用 main
```

这里要注意，ELF Header 里的 entry point 通常不是你的 `main`。

C 程序真正开始执行前，还要经过运行时启动代码，例如 `_start`。它会完成一些初始化，然后调用 `__libc_start_main`，最后再调用你的 `main`。

可以查看入口：

```bash
readelf -h app | grep Entry
```

也可以找符号：

```bash
nm app | grep ' main\| _start'
```

可能看到：

```text
0000000000001050 T _start
0000000000001139 T main
```

所以当你说“程序从 main 开始执行”时，在 C 语言层面这样理解可以；在 ELF 和操作系统层面，它并不准确。

准确一点说：

**用户代码通常从 `main` 开始，但进程的机器码入口通常是 `_start`。**

## 十二、动态链接需要哪些信息

如果程序依赖共享库：

```bash
gcc main.c -lm -o app
```

或者依赖自己的库：

```bash
gcc main.c -L. -lmath_utils -o app
```

ELF 里会记录动态链接信息。

查看依赖：

```bash
readelf -d app
```

可能看到：

```text
Dynamic section contains entries:
  NEEDED               Shared library: [libc.so.6]
  NEEDED               Shared library: [libm.so.6]
```

也可以用：

```bash
ldd app
```

可能看到：

```text
linux-vdso.so.1
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6
/lib64/ld-linux-x86-64.so.2
```

`NEEDED` 表示这个程序运行时需要哪些共享库。

但注意，ELF 通常不会把完整路径写死进去。它多半记录的是库名，例如：

```text
libmath_utils.so
```

运行时动态链接器会按规则搜索它。

常见搜索来源包括：

- ELF 中的 `RPATH` 或 `RUNPATH`。
- 环境变量 `LD_LIBRARY_PATH`。
- 系统动态库缓存，例如 `/etc/ld.so.cache`。
- 系统默认库目录，例如 `/lib`、`/usr/lib` 及其架构子目录。

不同系统、不同 glibc 版本、不同链接参数会影响细节。实际排查时，不要靠想象，直接看：

```bash
readelf -d app
ldd app
```

如果运行时报：

```text
error while loading shared libraries: libfoo.so: cannot open shared object file: No such file or directory
```

说明程序启动时动态链接器找不到 `libfoo.so`。

这和编译时找不到头文件不是一回事。头文件在编译期使用，`.so` 在链接期和运行期参与。把它们混为一谈，只会让问题更有耐心地折磨你。

## 十三、PLT 和 GOT

动态链接里经常看到两个名字：

- `.plt`：Procedure Linkage Table
- `.got`：Global Offset Table

它们主要服务动态链接和位置无关代码。

假设程序调用 `printf`：

```c
#include <stdio.h>

int main(void) {
    printf("hello\n");
    return 0;
}
```

`printf` 在 `libc.so.6` 里。编译链接 `app` 时，链接器通常不知道 `libc.so.6` 运行时会被加载到哪个地址。即使知道某一次的地址，ASLR 也可能让下一次不同。

于是程序不能简单写死：

```text
call 0x某个固定printf地址
```

它需要一套间接机制。

大致可以这样理解：

```text
程序调用 printf
  -> 先跳到 PLT 中的入口
  -> PLT 通过 GOT 找到真实地址
  -> 如果还没解析，交给动态链接器解析
  -> GOT 被填上真实 printf 地址
  -> 后续调用可以更快跳过去
```

这就是常说的 lazy binding，也就是延迟绑定。第一次调用某个外部函数时再解析，后续直接使用已修补的 GOT 项。

也可以通过链接或运行参数关闭延迟绑定，让程序启动时就解析更多符号。比如：

```bash
LD_BIND_NOW=1 ./app
```

或者链接时使用：

```bash
gcc main.c -Wl,-z,now -o app
```

不必一开始把 PLT/GOT 的每条指令都背下来。先理解它们解决的问题：

**动态库地址运行时才确定，PLT/GOT 提供了一层可被动态链接器修补的间接跳转和寻址机制。**

这比背名字可靠。名字会骗人，问题不会。

## 十四、静态链接和动态链接

静态链接：

```bash
gcc main.o libmath.a -o app
```

动态链接：

```bash
gcc main.o -L. -lmath -o app
```

如果同时有：

```text
libmath.a
libmath.so
```

链接器默认可能优先选择共享库，具体取决于命令、平台和链接器配置。

### 静态链接

静态链接会把需要的目标代码从静态库复制进最终可执行文件。

优点：

- 部署时对外部共享库依赖较少。
- 某些场景下运行环境更可控。

缺点：

- 可执行文件通常更大。
- 多个程序难以共享同一份库代码。
- 库更新后通常需要重新链接程序。

### 动态链接

动态链接不会把共享库完整复制进可执行文件，而是在 ELF 中记录运行时依赖。

优点：

- 可执行文件较小。
- 多个进程可以共享同一份库代码页。
- 库可以独立更新。

缺点：

- 运行时必须能找到兼容的 `.so`。
- 版本和搜索路径问题更复杂。
- 启动时需要动态链接器参与。

查看程序是否动态依赖某个库：

```bash
readelf -d app | grep NEEDED
```

如果没有动态段，可能看到：

```text
There is no dynamic section in this file.
```

这通常说明它不是动态链接 ELF，或者至少不包含动态链接信息。

## 十五、strip 后发生了什么

有时发布程序前会执行：

```bash
strip app
```

`strip` 会移除符号表、调试信息等不影响运行的内容，从而减小文件体积。

例如：

```bash
gcc -g main.c -o app
ls -lh app

strip app
ls -lh app
```

strip 后：

- `.symtab` 可能被移除。
- `.strtab` 可能被移除。
- 调试信息节可能被移除。
- `.dynsym` 通常仍需保留，因为动态链接需要它。

这就是为什么 strip 后程序仍然能运行，但调试和分析会困难很多。

如果你用 `nm app` 看到：

```text
nm: app: no symbols
```

不代表程序没有函数，也不代表二进制里没有机器码。它只是没有保留普通符号表。工具看不到名字，不等于代码不存在。

这个区别很重要。否则你会把“我看不见”误判成“它没有”。人类在很多地方都会犯这个错误，程序分析里也一样。

## 十六、调试信息在哪里

使用 `-g` 编译：

```bash
gcc -g main.c -o app
```

ELF 中会包含调试相关信息。常见节名可能包括：

```text
.debug_info
.debug_abbrev
.debug_line
.debug_str
.debug_frame
```

这些通常属于 DWARF 调试信息，用来帮助调试器完成：

- 地址到源码行号的映射。
- 局部变量位置追踪。
- 类型信息查询。
- 函数调用栈还原。

查看节：

```bash
readelf -S app | grep debug
```

发布程序时常常会把调试信息拆出去：

```bash
objcopy --only-keep-debug app app.debug
strip --strip-debug app
objcopy --add-gnu-debuglink=app.debug app
```

这样线上程序体积更小，同时保留单独的调试符号文件。崩溃后拿 core dump 和 debug file 还能做比较完整的分析。

当然，如果 debug file 丢了，排查体验就会朴素很多。所谓朴素，就是你和地址数字面面相觑。

## 十七、常用 ELF 分析命令

日常排查里，下面这些命令很常用。

### 1. 判断文件类型

```bash
file app
```

看它是不是 ELF、多少位、什么架构、是否 stripped、是否 PIE。

### 2. 看 ELF 头

```bash
readelf -h app
```

适合查看：

- 文件类型。
- 目标架构。
- 入口地址。
- program header 和 section header 的位置。

### 3. 看节表

```bash
readelf -S app
```

适合查看：

- `.text`
- `.data`
- `.bss`
- `.rodata`
- `.symtab`
- `.dynsym`
- `.debug_*`

### 4. 看加载段

```bash
readelf -l app
```

适合查看：

- 哪些内容会被映射到内存。
- 每个 `LOAD` segment 的权限。
- 是否有解释器 `INTERP`。
- section 到 segment 的映射关系。

### 5. 看符号

```bash
nm app
nm -C app
readelf -s app
```

适合排查：

- 某个函数是否被定义。
- 某个符号是否未解析。
- C++ 符号名是否被改编。
- 静态符号和外部符号的大致区别。

### 6. 看动态依赖

```bash
readelf -d app
ldd app
```

适合排查：

- 程序依赖哪些 `.so`。
- 哪个库找不到。
- 实际加载的是哪个路径下的库。

需要提醒一句：`ldd` 对不可信二进制要谨慎使用。日常开发排查自己的程序没问题，但分析来源不明的文件时，优先用 `readelf -d` 这种不会运行目标程序的方式。

### 7. 反汇编

```bash
objdump -d app
objdump -d -C app
```

适合查看机器指令、函数边界、调用位置。

也可以看节内容：

```bash
objdump -s -j .rodata app
```

### 8. 看重定位

```bash
readelf -r app
readelf -r main.o
```

适合观察哪些地址还需要在链接或加载时修补。

## 十八、常见问题排查

### 1. `undefined reference`

典型错误：

```text
undefined reference to `add'
```

排查思路：

1. `add` 是否只有声明，没有定义。
2. 定义所在 `.c/.cpp` 是否参与编译。
3. 生成的 `.o` 是否参与最终链接。
4. 如果定义在库里，链接命令是否带上了对应库。
5. C++ 是否因为 name mangling 导致符号名不一致。

看目标文件：

```bash
nm main.o
nm math.o
```

如果 `main.o` 里是：

```text
U add
```

而所有参与链接的目标文件和库里都没有：

```text
T add
```

那链接失败并不奇怪。

### 2. C++ 调 C 函数失败

C 头文件：

```c
// math.h

int add(int a, int b);
```

C 实现：

```c
// math.c

int add(int a, int b) {
    return a + b;
}
```

C++ 调用：

```cpp
#include "math.h"

int main() {
    return add(1, 2);
}
```

如果直接用 C++ 编译器处理头文件声明，C++ 可能会期待一个改编后的符号名，而 C 文件里导出的是 C 风格 `add`。

头文件应该写成：

```c
#ifndef MATH_H
#define MATH_H

#ifdef __cplusplus
extern "C" {
#endif

int add(int a, int b);

#ifdef __cplusplus
}
#endif

#endif
```

然后用：

```bash
nm math.o
nm -C main.o
```

对照符号名。链接器不会替你猜“这两个名字其实很像”。它没有这种体贴，也不该有。

### 3. 运行时找不到共享库

错误：

```text
error while loading shared libraries: libfoo.so: cannot open shared object file: No such file or directory
```

先看依赖：

```bash
readelf -d app | grep NEEDED
ldd app
```

如果看到：

```text
libfoo.so => not found
```

说明动态链接器搜索路径里没有找到它。

常见解决方式：

- 把库安装到系统库目录并更新缓存。
- 临时设置 `LD_LIBRARY_PATH`。
- 链接时写入合适的 `RUNPATH`。
- 部署时把可执行文件和 `.so` 的相对位置设计清楚。

例如写入相对路径：

```bash
gcc main.o -L./lib -lfoo -Wl,-rpath,'$ORIGIN/lib' -o app
```

`$ORIGIN` 表示可执行文件所在目录。这样部署结构可以是：

```text
deploy/
  app
  lib/
    libfoo.so
```

这比让用户自己配置一堆环境变量更稳定。把复杂性交给使用者，通常只是把问题延后，而且延后得并不高明。

### 4. 架构不匹配

错误可能类似：

```text
cannot execute binary file: Exec format error
```

或者链接时出现架构不兼容。

检查：

```bash
file app
readelf -h app
```

重点看：

- 32 位还是 64 位。
- x86-64 还是 AArch64。
- 目标系统是否支持这个 ABI。

比如在 x86-64 机器上直接运行 AArch64 ELF，自然不行。它不是不努力，它只是物理上做不到。

### 5. stripped 后看不到符号

如果：

```bash
nm app
```

显示：

```text
no symbols
```

先看：

```bash
file app
readelf -S app
```

如果程序被 strip 过，普通符号表可能已经没有了。可以尝试：

```bash
readelf -s app
readelf --dyn-syms app
```

动态符号表可能还在，但它只包含动态链接需要的符号，不等于完整源码级符号信息。

## 十九、把 ELF 和 C/C++ 概念连起来

很多 C/C++ 概念最终都会落到 ELF 里。

| C/C++ 概念 | ELF 中的体现 |
| --- | --- |
| 函数定义 | `.text` 中的机器码，符号表中的函数符号 |
| 全局变量初始化为非零值 | `.data` |
| 全局变量未初始化或初始化为 0 | `.bss` |
| 字符串字面量 | 常见于 `.rodata` |
| `static` 文件作用域函数 | 局部符号 |
| `extern` 声明 | 可能形成未定义符号引用 |
| 头文件声明 | 本身不直接进入 ELF，影响编译时符号引用 |
| 链接第三方库 | 解析符号，或写入 `NEEDED` 动态依赖 |
| `-g` | 添加 DWARF 调试信息节 |
| `strip` | 移除部分符号和调试信息 |
| PIE | ELF 类型常见为 `ET_DYN`，可随机加载 |

所以学习 ELF 不是为了把二进制格式背得像考试答案，而是为了理解：

- 为什么目标文件还不能运行。
- 为什么链接器能找到或找不到某个函数。
- 为什么共享库运行时可能找不到。
- 为什么 `main` 不是进程真正入口。
- 为什么 `.bss` 很大但文件不一定大。
- 为什么 strip 后程序能运行但不好调试。

这些问题都不是孤立的。它们只是 ELF 在不同阶段露出来的侧面。

## 二十、推荐观察顺序

真正排查一个 ELF 问题时，可以按这个顺序来：

1. 先用 `file app` 判断文件身份。
2. 用 `readelf -h app` 看类型、架构、入口。
3. 用 `readelf -l app` 看加载段和解释器。
4. 用 `readelf -d app` 看动态依赖。
5. 用 `ldd app` 看本机实际解析到哪些库。
6. 用 `nm -C` 或 `readelf -s` 看符号。
7. 用 `readelf -r` 看重定位。
8. 必要时用 `objdump -d -C` 看汇编。

如果是链接错误，优先看 `.o` 和 `.a` 里的符号。

如果是运行时加载错误，优先看可执行文件的动态段、解释器和共享库搜索路径。

如果是崩溃问题，可能还要结合：

```bash
gdb app core
addr2line -e app 0x地址
```

当然，前提是你还保留着调试符号。把符号删光之后再要求调试器温柔，多少有些不讲道理。

## 总结

ELF 是 Linux 上 C/C++ 程序非常核心的二进制格式。它不只是最终可执行文件的外壳，也承载目标文件、共享库、符号、重定位、动态链接和加载信息。

可以这样理解：

- `.o` 是还没完成链接的 ELF，里面有符号和重定位信息。
- `app` 是链接后的 ELF，里面有程序入口、加载段和运行时依赖。
- `.so` 是可被动态链接器加载的 ELF，共享给多个程序使用。
- section 面向链接和分析，segment 面向加载和运行。
- 符号表回答“名字在哪里”，重定位回答“哪些地址还要修补”。
- 动态段回答“运行时还需要哪些库和链接信息”。

最重要的一句话：

**ELF 把 C/C++ 程序从源码世界带到操作系统能执行的二进制世界。**

理解 ELF 后，再看编译、链接、共享库、运行时加载错误，就不会只剩下“怎么又报错了”这种朴素但无助的感想。报错依然可能出现，不过至少你知道应该从哪个表、哪个节、哪个段开始问它。
