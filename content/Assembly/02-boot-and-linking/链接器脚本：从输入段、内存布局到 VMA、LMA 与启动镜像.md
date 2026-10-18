+++
date = '2026-09-13T00:00:00+08:00'
draft = false
title = '链接器脚本：从输入段、内存布局到 VMA、LMA 与启动镜像'
+++

链接器脚本（linker script）不是“给 `.text` 写个起始地址的配置文件”。它是链接器的布局语言：把各个 `.o` 文件中的输入段收集为输出段，决定它们的运行地址、镜像装载地址、ELF program header、入口点和导出符号。裸机、内核、bootloader、嵌入式固件之所以离不开它，正是因为这些程序不能把“代码和数据放在哪里”交给宿主操作系统随意决定。

本文以 GNU `ld` 的脚本语法为主。`lld` 和其他链接器对常用 GNU 语法通常兼容，但扩展、默认脚本和诊断细节可能不同；涉及生产镜像时，应以目标链接器版本的文档和最终 ELF 为准。GNU `ld` 即使没有显式传入脚本，也始终会使用一个默认脚本；`--verbose` 可打印它，而 `-T script.ld` 会用自定义脚本替换默认布局。[GNU ld：Linker Scripts](https://sourceware.org/binutils/docs/ld/Scripts.html)

## 一、先分清四件事：输入段、输出段、加载段和地址

构建链路可以先画成：

```text
main.o、driver.o、libfoo.a
  └─ 各自包含 input sections：.text、.text.foo、.rodata、.data、.bss ...
       └─ 链接器脚本按规则收集
            └─ output sections：.text、.rodata、.data、.bss ...
                 └─ ELF program headers（常见 PT_LOAD）描述装载映像
                      └─ bootloader/OS loader 将映像放入内存并从入口执行
```

| 概念 | 属于谁 | 例子 | 容易混淆的对象 |
| --- | --- | --- | --- |
| 输入段（input section） | 单个 `.o` / 库成员 | `driver.o` 中的 `.text.uart_init` | 最终 ELF 的 `.text` |
| 输出段（output section） | 链接器输出文件 | 合并后的 `.text`、`.data`、`.bss` | ELF 的 program header |
| 段（segment / program header） | ELF 装载视角 | `PT_LOAD`、`PT_DYNAMIC` | section；加载器主要看 segment |
| VMA | 运行时地址 | 程序执行/访问 `.data` 使用的地址 | 镜像中保存初始字节的位置 |
| LMA | 装载地址 | 固件镜像中 `.data` 初值的存放位置 | VMA、文件偏移、物理地址 |

**section 是链接和调试的组织单位，segment 是装载器的组织单位。**一个 `PT_LOAD` 常包含连续的 `.text` 与 `.rodata`，也可能包含 `.data`；具体如何分组由默认规则、脚本和链接器决定。运行 ELF 时，操作系统通常依据 program headers 建立映射，不会逐个读取 section 名称。

## 二、为什么需要脚本：默认布局只适合默认运行环境

普通 Linux 用户程序通常由编译器驱动程序传给链接器默认脚本，动态链接器和内核负责装载、重定位、分配栈与堆。你很少关心 `.text` 的最终虚拟地址，因为 ASLR、共享库和装载器都在参与决定它。

以下场景则必须由软件自己明确布局：

- **裸机固件**：代码要放在 Flash，运行时可写数据要在 SRAM/DRAM。
- **bootloader**：CPU 复位后从固定地址取指，入口和镜像格式不能猜。
- **操作系统内核**：内核虚拟地址、物理加载地址、trampoline、初始页表和可回收启动段可能有特殊要求。
- **多块内存的 MCU/SoC**：片上 SRAM、外部 DRAM、多个 Flash bank、DMA 专用内存各有地址范围和权限。
- **特殊段约束**：中断向量必须在镜像开头；某段代码必须放入 TCM；某段数据必须不初始化或不能被垃圾回收。

链接器脚本并不让硬件“自动拥有这些内存”。它只生成一个声称各段位于某些地址的输出文件。地址是否真实存在、是否可取指、启动代码有没有把数据从 LMA 复制到 VMA，仍是硬件、bootloader 和运行时共同要兑现的约定。

## 三、最小脚本：`ENTRY`、`.` 与 `SECTIONS`

先看一个刻意简化的脚本：

```ld
ENTRY(_start)

SECTIONS
{
  . = 0x80000000;

  .text : {
    *(.text .text.*)
  }

  .rodata : {
    *(.rodata .rodata.*)
  }

  .data : {
    *(.data .data.*)
  }

  .bss : {
    *(.bss .bss.*)
    *(COMMON)
  }
}
```

### 1. `ENTRY(_start)` 只设置 ELF 入口字段

`ENTRY(symbol)` 让链接器把 ELF header 的 entry point 设为该符号最终地址。它不是 `call _start`，不会把 `_start` 放到 `.text` 的第一个字节，也不能改变 CPU 复位后从哪里取第一条指令。

最终谁使用这个入口字段，取决于环境：

- Linux 等 ELF 装载器通常使用它作为进程/解释器的初始控制流信息；
- bootloader 可能读取它，也可能按自己的镜像格式使用固定入口；
- 某些 MCU 复位逻辑固定读取向量表或固定地址，根本不看 ELF header。

GNU `ld` 设置入口点有优先级：命令行 `-e`、脚本 `ENTRY`、目标相关默认符号、代码段起始地址、地址 0 等依次尝试。因此 `ENTRY` 是“告诉链接结果入口是什么”，不是“让硬件寻找标签”的魔法。[GNU ld：Setting the Entry Point](https://sourceware.org/binutils/docs/ld.html)

### 2. `.` 是位置计数器，不是 C 的成员访问符

脚本中的 `.`（location counter）表示链接器当前正在放置内容的地址：

```ld
. = 0x80000000;       /* 后续输出段从这里开始安排 */
. = ALIGN(4096);      /* 向上移动到 4 KiB 边界 */
```

每放入一个非空输出段，`.` 通常向后推进该段大小；显式赋值可以移动它。向前移动常用于对齐或保留空洞；若把它向后设置到超出内存范围，脚本不会替你凭空创造 RAM，只会产生地址布局或溢出错误。

### 3. 输出段收集输入段

```ld
.text : {
  *(.text .text.*)
}
```

左边的 `.text` 是**输出段**；花括号中的 `*(...)` 是输入段选择器：

- 第一个 `*` 表示来自任意输入文件；
- `.text` 匹配正好叫 `.text` 的输入段；
- `.text.*` 匹配 `.text.init`、`.text.uart_init` 等子段。

若只写 `*(.text)`，启用 `-ffunction-sections` 后编译器产生的 `.text.foo` 往往不会被收集，可能留成意外输出段，或在严格脚本中丢失。对库还可用 `archive.a:member.o(.text*)` 等更精细选择；一般布局先用通配符覆盖完整段族，之后再按需求拆分。

`.bss` 中的 `*(COMMON)` 是为了处理旧式 common 符号。现代 C 编译器常使用 `-fno-common`，使未初始化全局变量直接形成 `.bss` 定义；保留 `*(COMMON)` 仍可让脚本兼容某些对象文件。

## 四、输出段的完整语法与最常用命令

GNU `ld` 的输出段描述可拥有地址、内容、VMA/LMA 所在内存区、program header 和填充值等属性。常见骨架如下：

```ld
section_name [VMA] : [AT(LMA)]
{
  /* 输入段选择、符号赋值、对齐、显式字节 */
} > VMA_MEMORY_REGION AT> LMA_MEMORY_REGION :phdr =fill
```

并非每段都需要所有属性。链接脚本最容易读懂的方式不是背整行语法，而是将每个部分回答成一个问题：

| 写法 | 回答的问题 |
| --- | --- |
| `.text` | 输出段叫什么？ |
| `0x80000000` 或 `ALIGN(4096)` | 它的 VMA 从哪里开始？ |
| `{ *(.text*) }` | 收集哪些输入段，内部顺序怎样？ |
| `> RAM` | 运行时占用哪块 `MEMORY` 区域？ |
| `AT> FLASH` 或 `AT(0x...)` | 初始字节在镜像/装载时位于哪里，即 LMA？ |
| `:text` | 归入哪个 `PHDRS` program header？ |
| `=0xff` | 段内空洞以什么字节填充？ |

### 1. `ALIGN`：对齐地址，而非“分配某个对象”

```ld
. = ALIGN(16);
.rodata : ALIGN(16) { *(.rodata*) }
```

`ALIGN(n)` 将位置向上取整到 `n` 的倍数。它常用于满足指令、DMA、页表或 ELF segment 的对齐要求。对齐会产生 padding，所以映像大小与运行时占用空间都可能变大；它不是给某个 C 变量添加语言级 alignment 属性。

### 2. `KEEP`：对抗 section garbage collection

链接时若使用 `--gc-sections`，链接器会从根符号开始删除不可达的输入段。中断向量、注册表、启动钩子或仅由硬件间接引用的代码，可能在 C 调用图中“无人引用”，却绝不能删除：

```ld
.isr_vector : {
  KEEP(*(.isr_vector))
} > FLASH
```

`KEEP` 保留匹配的输入段；它不保证段排在镜像第一个位置，因此仍要通过脚本的输出段顺序和 VMA 指定位置。

### 3. `/DISCARD/`：明确丢弃，而不是“忽略一下”

```ld
/DISCARD/ : {
  *(.comment)
  *(.note .note.*)
  *(.eh_frame)
}
```

这会从最终输出中移除匹配输入段。它适合无异常处理、无调试需求的极小固件，但很危险：丢弃 unwind 信息会影响异常、栈回溯或调试；丢弃某个目标专用段可能导致运行时或装载器不再工作。压缩镜像大小前先确认谁依赖该段。

### 4. `PROVIDE`、`ASSERT` 和脚本导出符号

链接器脚本可定义符号：

```ld
__bss_start = .;
/* ...放置 .bss 内容... */
__bss_end = .;

PROVIDE(__stack_size = 4096);
ASSERT(__bss_end <= ORIGIN(RAM) + LENGTH(RAM), "RAM overflow");
```

- 普通 `symbol = expression;` 总会定义/覆盖该链接符号。
- `PROVIDE(symbol = expression)` 只在其他输入文件尚未定义该符号时提供默认值，适合允许应用覆盖的钩子。
- `ASSERT(condition, "message")` 在链接期验证关键不变量；比运行到硬件后才发现栈压到 Flash 可靠得多。

脚本符号通常表达的是**地址边界**。在 C 中应把它声明为外部数组或字符对象并取地址：

```c
#include <stdint.h>

extern uint8_t __bss_start[];
extern uint8_t __bss_end[];

void zero_bss(void)
{
    for (uint8_t *p = __bss_start; p < __bss_end; ++p)
        *p = 0;
}
```

不要写成 `size_t n = __bss_end;` 并期望读到一个普通变量的值：符号本身没有链接脚本“存进内存的一份对象”，它的关键含义是它的**地址数值**。GNU `ld` 文档也建议在源码中使用链接器定义的符号时取其地址。[GNU ld：脚本表达式与地址符号](https://sourceware.org/binutils/docs/ld.html)

## 五、`MEMORY`：把芯片的可用地址范围告诉链接器

裸机系统常有多块真实内存：Flash 可取指且非易失，SRAM 可读写，外部 DRAM 容量大但较晚可用。`MEMORY` 让脚本为这些区域命名并规定范围：

```ld
MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
```

这些名字只在脚本中有效。`FLASH` 不是 C 宏，`RAM` 不是 CPU 识别的关键字；它们是链接器进行放置与容量检查的标签。

| 写法 | 含义 |
| --- | --- |
| `ORIGIN(FLASH)` | 该区域起始地址 |
| `LENGTH(RAM)` | 该区域长度 |
| `> FLASH` | 输出段的 VMA 放在 FLASH 区域 |
| `AT> FLASH` | 输出段的 LMA 放在 FLASH 区域 |

链接器会根据区域长度检查溢出，却不会自动“挪一挪其他段使它装下”。更不会初始化内存控制器、配置 MPU/MMU 或烧录 Flash；这些是启动代码和平台工具的职责。`MEMORY` 的正式语法与区域属性见 [GNU ld：MEMORY Command](https://sourceware.org/binutils/docs/ld.html)。

## 六、VMA 与 LMA：理解固件启动布局的关键

### 1. 两个地址回答两个不同问题

- **VMA（Virtual Memory Address）**：程序运行时 CPU 用什么地址访问这段内容。裸机中它常也是物理/总线地址；启用 MMU 后，它通常是虚拟地址。
- **LMA（Load Memory Address）**：这段内容的初始化字节在镜像中应从哪里加载/复制。它常位于 Flash，也可能是文件镜像布局中的某个地址。

最典型的例子是 `.data`：变量在运行时必须可写，所以 VMA 在 RAM；但其 C 源码初始值必须断电保存，所以镜像中的初始字节放在 Flash，即 LMA 在 Flash。

```text
Flash（LMA）                       RAM（VMA）
+----------------------+          +----------------------+
| .text / .rodata      |  可直接   | .data 的运行时副本   |
| .data 的初始字节     | ---复制-> | 可读写的全局变量     |
+----------------------+          +----------------------+
```

`.bss` 则只需要 RAM VMA：它在镜像中没有初始字节，启动代码把那段 RAM 清零即可。因此它常使用 `(NOLOAD)`，表达“占用运行时地址空间，但不为其放入可装载内容”。

### 2. 一个完整的 Flash + RAM 脚本

下面是通用教学模板；地址、向量格式、入口名称和段名必须替换为目标板实际值：

```ld
ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}

SECTIONS
{
  .isr_vector :
  {
    KEEP(*(.isr_vector))
  } > FLASH

  .text :
  {
    __text_start = .;
    *(.text .text.*)
    *(.init .fini)
    __text_end = .;
  } > FLASH

  .rodata :
  {
    *(.rodata .rodata.*)
  } > FLASH

  .data :
  {
    . = ALIGN(4);
    __data_start = .;
    *(.data .data.*)
    __data_end = .;
  } > RAM AT> FLASH

  __data_load_start = LOADADDR(.data);

  .bss (NOLOAD) :
  {
    . = ALIGN(4);
    __bss_start = .;
    *(.bss .bss.*)
    *(COMMON)
    __bss_end = .;
  } > RAM

  __stack_top = ORIGIN(RAM) + LENGTH(RAM);

  ASSERT(__bss_end <= __stack_top, "RAM overflow")
}
```

逐段看其结果：

| 输出段 | VMA | LMA | 为什么 |
| --- | --- | --- | --- |
| `.isr_vector` | Flash | Flash | 复位/异常入口或向量需要最早可读 |
| `.text`、`.rodata` | Flash | Flash | 常可 XIP；也可按平台选择复制到 RAM |
| `.data` | RAM | Flash | 初值持久化，运行时可写 |
| `.bss` | RAM | 无需初始字节 | 启动时清零 |
| 栈 | RAM 高地址附近 | 无 | 只是一段预留运行时空间/边界符号 |

`AT> FLASH` 是“LMA 从 Flash 区域分配”，而不是“把 `.data` 自动复制到 RAM”。链接器只把 `LOADADDR(.data)` 算好；复位入口必须在 C 运行时开始前完成复制与清零：

```c
#include <stdint.h>

extern uint8_t __data_load_start[];
extern uint8_t __data_start[];
extern uint8_t __data_end[];
extern uint8_t __bss_start[];
extern uint8_t __bss_end[];

void runtime_init(void)
{
    uint8_t *src = __data_load_start;
    uint8_t *dst = __data_start;

    while (dst < __data_end)
        *dst++ = *src++;

    for (dst = __bss_start; dst < __bss_end; ++dst)
        *dst = 0;
}
```

真实启动代码还要在调用这段 C 前先设置栈、避免编译器生成依赖未初始化 `.data/.bss` 的访问，并保证所用指令、Flash 和 RAM 在当前 CPU 状态可访问。初始 C 运行时不是自然出现的，它正是链接脚本和启动汇编配合的结果。

### 3. VMA/LMA 与 Linux 进程不是简单的一一对应

在带操作系统和 MMU 的用户进程中，ELF 文件中的 `PT_LOAD` segment、文件偏移、进程 VMA、物理页和页缓存之间由装载器与内核处理；链接器脚本里所谓 LMA 的固件复制模型不应机械套用。仍然通用的原则是：**运行地址与初始内容来源可以不同。**在裸机里常是 Flash→RAM 复制；在 Linux 中常是文件页按需映射到进程虚拟地址，再由页缓存和物理页面支撑。

GNU `ld` 将 VMA 作为输出段地址，并允许用 `AT`/`AT>` 指定 LMA；这正是 `.data` 在 RAM 运行、初值在 Flash 保存的脚本基础。[GNU ld：Output Section VMA/LMA](https://sourceware.org/binutils/docs/ld.html)

## 七、`PHDRS`：何时还要自己控制 ELF 加载段

`SECTIONS` 主要控制 section；若你要精确控制 ELF program headers，可定义 `PHDRS`：

```ld
PHDRS
{
  text PT_LOAD FLAGS(5);  /* PF_R | PF_X */
  data PT_LOAD FLAGS(6);  /* PF_R | PF_W */
}

SECTIONS
{
  .text : { *(.text*) *(.rodata*) } :text
  .data : { *(.data*) } :data
  .bss  : { *(.bss*) *(COMMON) } :data
}
```

这里 `:text`、`:data` 将输出段关联到命名的 program header。`FLAGS(5)`/`FLAGS(6)` 分别是 ELF 的 `PF_R|PF_X` 和 `PF_R|PF_W` 数值。内核、bootloader、自定义 ELF 装载器或需要严格 W^X 的系统可能需要这一层；普通裸机二进制若最终用 `objcopy -O binary` 烧录，program header 有时不是启动工具最关心的部分，但仍值得在 ELF 调试阶段看清楚。

不要把 `PHDRS` 与 `MEMORY` 混为一谈：前者描述输出 ELF 如何被装载器看见，后者约束链接器把 section 放入哪些目标地址范围。一个解决文件格式的加载视角，一个解决板级内存地图。

## 八、输入段顺序、初始化数组与垃圾回收

段的顺序经常就是语义的一部分。

### 1. 构造函数、析构函数和注册表

C++ 全局构造、某些运行时注册和 init hook 常放在 `.init_array.*`、`.fini_array.*` 等输入段。一个适合保留优先级顺序的模式是：

```ld
.init_array :
{
  __init_array_start = .;
  KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*)))
  KEEP(*(.init_array))
  __init_array_end = .;
} > RAM AT> FLASH
```

这里的 `SORT_BY_INIT_PRIORITY`、`KEEP` 和边界符号共同形成运行时合同：启动代码遍历 `[__init_array_start, __init_array_end)`；顺序由段名优先级决定；即使没有普通调用引用，也不允许 `--gc-sections` 删除。

若项目不用 C++，不应为了“模板完整”强加这一段；链接脚本应该反映运行时真实需求，不是关键字展览。

### 2. `-ffunction-sections`、`-fdata-sections` 与 `--gc-sections`

这组常见优化将每个函数/数据放入更细的输入段，再让链接器从可达根删除未使用部分。它能减小镜像，却会暴露脚本遗漏：

- 段选择器必须覆盖 `.text.*`、`.rodata.*`、`.data.*` 等；
- 硬件入口、中断向量、链接期注册表等隐式引用内容须使用 `KEEP`；
- 需要被外部固件、调试器或反射系统找到的符号/段，也应明确作为根或保留。

“代码明明编译进 `.o`，为什么最终 ELF 没有”时，先检查 map 文件和 `--gc-sections`，不要先怀疑 CPU。

## 九、怎样验证脚本真的产生了预期布局

链接器脚本的正确性不能只靠阅读。应同时检查链接命令、map 文件、section header、program header、符号表和反汇编：

```bash
# 将脚本交给编译器驱动，并输出 map 文件
riscv64-unknown-elf-gcc -nostdlib -Wl,-T,linker.ld,-Map,app.map \
  start.o main.o -o app.elf

# section 的地址、大小、标志
riscv64-unknown-elf-readelf -S -W app.elf
riscv64-unknown-elf-objdump -h app.elf

# PT_LOAD 等 program header；关注 VirtAddr、PhysAddr、FileSiz、MemSiz、Flags
riscv64-unknown-elf-readelf -l -W app.elf

# 链接器定义的符号和入口地址
riscv64-unknown-elf-readelf -h app.elf
riscv64-unknown-elf-nm -n app.elf | rg '__data|__bss|__stack|Reset_Handler'

# 机器码是否真的位于预期 .text 地址
riscv64-unknown-elf-objdump -d -M no-aliases app.elf
```

应逐项核对：

1. ELF entry point 是否等于 `Reset_Handler` 的地址；
2. `.isr_vector`、`.text` 的 VMA 是否真的落在 Flash；
3. `.data` 的 VMA 是否在 RAM，LMA/加载镜像是否在 Flash；
4. `.bss` 的 `NOBITS`/`MemSiz` 是否占 RAM 却不膨胀镜像；
5. `__data_load_start`、`__data_start/end`、`__bss_start/end` 是否围住正确范围；
6. `PT_LOAD` 权限是否意外让数据页可执行，或代码页可写；
7. map 文件是否显示未预期的大段、重复库、对齐空洞或被意外回收的输入段。

特别是 `readelf -S` 与 `readelf -l` 必须一起看：前者回答 section 怎么组织，后者回答装载器会怎样看这个 ELF。GNU `ld` 的 `SECTIONS`、`MEMORY`、`PHDRS` 和 `ADDR`/`LOADADDR` 等函数都以此为验证对象。[GNU ld 文档](https://sourceware.org/binutils/docs/ld.html)

## 十、最常见的错误

| 错误 | 表现 | 正确理解 |
| --- | --- | --- |
| 以为 `ENTRY()` 会让 CPU 从该符号复位 | ELF 入口对了，板子仍不启动 | 复位 PC/向量由 CPU 与平台决定；入口字段由谁消费必须确认 |
| 以为 `> RAM AT> FLASH` 会自动复制 `.data` | 已初始化全局变量值错误 | 复位代码必须从 `LOADADDR(.data)` 复制到 `.data` VMA |
| 把 VMA 当 LMA | `.data` 初值不在镜像或运行时写到 Flash | VMA 是运行地址，LMA 是初始字节来源 |
| 只收集 `*(.text)` | 某些函数消失或落入意外段 | 同时覆盖 `.text.*`，并检查 map 文件 |
| 忘记 `KEEP` | 启动/中断/注册表在 `--gc-sections` 后消失 | 隐式入口和表项必须显式保留 |
| 将脚本符号当普通变量取值 | 清 `.bss` 边界、栈顶等数值荒谬 | 链接脚本符号主要用其地址，C 中声明后取地址/当数组边界 |
| 只看 `.o` 不看最终 ELF | 以为 section 已在预期地址 | 地址、重定位、库成员选择和段合并都在最终链接后才确定 |
| 用 `/DISCARD/` 随手删段 | unwind、构造、调试或加载失败 | 先确认运行时和工具是否依赖该段 |
| 将一个脚本搬到另一块板 | 取指 fault、RAM overflow、烧录后死机 | `ORIGIN`、`LENGTH`、复位机制、Flash 映射和启动协议必须按平台重做 |

## 总结

链接器脚本本质上是一份“从目标文件到可运行映像”的空间合同：

- 输入段被收集为输出段；输出段再通过 program header 告诉 ELF 装载器如何看待映像。
- `ENTRY` 设置 ELF 入口字段，`.` 推进布局位置，`SECTIONS` 决定收集和顺序，`MEMORY` 限定真实目标内存范围。
- VMA 是运行时访问地址，LMA 是初始字节的装载来源；`> RAM AT> FLASH` 需要启动代码完成数据复制。
- `PROVIDE`、边界符号、`ASSERT`、`KEEP` 将启动代码、运行时和链接布局连成可检查的接口。
- 链接脚本是否正确，最终要用 map、`readelf -S/-l`、`nm` 和反汇编验证；不看最终 ELF 的脚本调试，很难称得上调试。

掌握这套模型之后，看到 `ENTRY(_start)`、`*(.text.*)`、`AT> FLASH`、`LOADADDR(.data)` 或 `__bss_end` 时，就不应只记住语法，而应能回答：**这段内容运行在哪？初始字节从哪来？谁把它搬过去？它是否被装载器映射？若链接器删除或放错它，最先坏的是哪一步启动流程？**
