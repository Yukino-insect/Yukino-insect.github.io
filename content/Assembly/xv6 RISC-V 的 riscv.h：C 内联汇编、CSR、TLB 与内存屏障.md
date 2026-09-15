+++
date = '2026-09-13T00:00:00+08:00'
draft = false
title = 'xv6 RISC-V 的 riscv.h：C 内联汇编、CSR、TLB 与内存屏障'
+++
`kernel/riscv.h` 看起来像一大串很短的 C 函数：`r_sstatus()`、`w_satp()`、`sfence_vma()`……如果只把它当成“寄存器工具类”，很容易在真正需要修改内核时踩坑。它实际是一层**极薄但权限极高的硬件接口**：C 代码通过 GCC 风格的内联汇编，在调用点直接发出 RISC-V 的 CSR、地址翻译同步和内存顺序指令。

本文以 xv6 RISC-V 版本的 `kernel/riscv.h` 为例。目标不是背完所有 CSR 编号，而是能独立回答：这一行 `asm volatile` 最终告诉 CPU 做什么？`%0`、`"=r"`、`"rK"` 和 `"memory"` 分别约束谁？为什么写 `satp` 后还需要 `sfence.vma`？为什么关闭中断既不是锁，也不能只看一个普通 C 变量？

先给全局结论：

- `riscv.h` 中大多数 `r_xxx()`/`w_xxx()` 是 `static inline` 封装，通常不会形成一次普通函数调用；编译器把其中汇编嵌入调用点。
- 源码中出现的 `csrr`、`csrw`、`csrs`、`csrc` 和 `mv` 都是汇编器提供的友好写法；真正的机器编码分别落到 `CSRRS`、`CSRRW`、`CSRRS/CSRRSI`、`CSRRC/CSRRCI` 与 `ADDI`（或可选压缩编码）等指令上。
- `csrrc`、`sfence.vma`、`fence`、`fence.i` 则对应有明确 ISA 语义的真实指令；其中后面三者解决的是不同层次的“看见新内容”，不能互相替代。
- CSR 不是内存变量，`csrw satp, x` 也不是向某个地址写一个 `uint64`。它访问的是 CPU 的独立控制状态空间，并受特权级和实现支持情况限制。

## 阅读前的前置知识

下面几项并非 xv6 独有；它们是阅读任何 RISC-V 内核、固件、运行时或驱动的类似封装时都会遇到的边界。若尚不能明确区分这些概念，建议先读配套前置文章，再回到本篇对照具体代码。否则很容易把编译器约束、硬件屏障和多核协议说成同一件事——这种简化很诱人，但并不正确。

| 前置知识 | 在本文中的用途 | 建议阅读 |
| --- | --- | --- |
| 通用寄存器、内存、CSR、hart 与特权级 | 区分 `mv`、`csrr/csrw` 和普通 load/store；判断一条指令影响哪个执行者 | [RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序](RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序.md) 的第二、四、七节 |
| GCC 风格扩展内联汇编 | 理解模板、`%0`、`"=r"`、`"rK"`、`volatile` 与 `"memory"` 是怎样约束编译器的 | [RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序](RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序.md) 的第三节 |
| 虚拟地址、页表、TLB 与多 hart 同步 | 理解为什么改写 PTE 或 `satp` 后不能只看普通内存中的新值 | [RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序](RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序.md) 的第五节，以及 [RISC-V 页表：Sv39、PTE、TLB 与 xv6 地址空间](08-RISC-V 页表：Sv39、PTE、TLB 与 xv6 地址空间.md) |
| 普通内存顺序、MMIO、DMA 与取指同步 | 区分 `fence`、`fence.i`、`sfence.vma`，避免把其中任意一个叫作“万能清缓存” | [RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序](RISC-V 底层编程前置知识：内联汇编、CSR、TLB 与内存顺序.md) 的第六节 |

前置文章刻意不绑定某个内核；本篇才讨论 xv6 将这些机制封装成哪些函数、又在何处调用它们。两者分别处理“机制为何成立”和“这一份代码怎样使用机制”，不要颠倒阅读顺序。

## 一、先分清：这是 C 头文件，不是 `.S` 汇编文件

`riscv.h` 的主体被包在：

```c
#ifndef __ASSEMBLER__
// C 类型、static inline 函数、asm volatile
#endif
```

之内。它的意思是：当 C 编译器包含此文件时，可以看见 `uint64`、`static inline` 和内联汇编；当**经过 C 预处理的**汇编源（通常是大写后缀 `.S`）包含它，工具链约定定义 `__ASSEMBLER__`，这些 C 语法便会被排除，避免汇编器被 `uint64` 之类的东西绊倒。小写 `.s` 通常直接送入汇编器，未必经过预处理，不能仅凭“它也是汇编文件”假定此宏存在。页大小、PTE 标志、地址换算宏位于条件块外，因而两边都能使用。

换言之，下面的代码不是“运行时去调用一个叫 `r_sstatus` 的库函数”：

```c
static inline uint64
r_sstatus(void)
{
  uint64 x;
  asm volatile("csrr %0, sstatus" : "=r"(x));
  return x;
}
```

在合适的优化级别下，调用：

```c
uint64 status = r_sstatus();
```

通常直接变成类似：

```asm
csrr    a5, sstatus
```

其中 `a5` 只是编译器此刻挑选的一个通用寄存器。`static` 让函数只具有本翻译单元可见性，`inline` 允许内联；但不要把 `inline` 理解成绝对承诺。调试构建、未优化构建或特殊情形下，编译器仍可能不内联，正确性不能依赖“它一定没有调用开销”。

## 二、读懂 GCC 扩展内联汇编的四个位置

最常见的形式是：

```c
asm volatile("模板" : 输出 : 输入 : clobber);
```

以 `r_sstatus()` 为例：

```c
uint64 x;
asm volatile("csrr %0, sstatus" : "=r"(x));
return x;
```

可从右向左拆开理解：

| 片段 | 交给谁 | 含义 |
| --- | --- | --- |
| `"csrr %0, sstatus"` | 汇编器 | `%0` 是第 0 个操作数的占位符，最终替换为某个寄存器名 |
| `"=r"(x)` | 编译器寄存器分配器 | `=` 表示只输出；`r` 要求用一个通用整数寄存器；机器执行完后该寄存器的值写回 C 变量 `x` |
| `volatile` | 编译器优化器 | 该汇编具有必须保留的可观察副作用，不能因“结果似乎没用”而随意删去或合并 |
| 没有输入/没有 clobber | 编译器 | 这条封装只读取 CSR 并产出 `x`；它没有声称会读写普通 C 内存 |

写入函数换成输入约束：

```c
static inline void
w_satp(uint64 x)
{
  asm volatile("csrw satp, %0" : : "r"(x));
}
```

这里第一个冒号后留空，第二个冒号后的 `"r"(x)` 表示“把 C 表达式 `x` 放入一个通用寄存器，并把该寄存器名字替换到 `%0`”。它不是 `satp = x` 这样的普通 C 赋值，也没有内存地址操作数。

### 1. 为什么 `volatile` 还不够

`volatile asm` 主要告诉编译器“这条汇编不能被当成无副作用计算删除”。它**不自动**表示“所有普通内存读写都不能跨过这里重排”。对于必须建立 C 编译器层面内存边界的封装，文件还写了：

```c
asm volatile("sfence.vma zero, zero" ::: "memory");
```

末尾的 `"memory"` 是 clobber，表示这段汇编可能读写任意内存。编译器于是必须在此处把此前可能涉及内存的值处理妥当，且不能把普通内存访问任意移动到屏障另一侧。它是**编译器屏障**；硬件层面的地址翻译/内存访问顺序，则由字符串里的 `sfence.vma` 或 `fence` 指令本身提供。两者缺一不可，也不能混为同一种屏障。

### 2. `"rK"` 为什么比 `"r"` 多一个字母

`s_sstatus()` 和 `c_sstatus()` 使用：

```c
__asm__ __volatile__("csrs sstatus, %0" : : "rK"(x) : "memory");
```

`r` 允许通用寄存器；RISC-V GCC 约束中的 `K` 允许能编码为 CSR 立即数操作数的 5 位无符号常量。因此 `"rK"` 表示“若 `x` 是合适的编译期小常量，可以直接使用立即数形式；否则放进寄存器”。对于 `SSTATUS_SIE` 这类值很小的掩码，编译器有机会生成更短的 CSR 立即数形式；传入运行时变量时则使用寄存器形式。

这不是 C 语言标准的语法，而是 GCC/Clang 兼容的扩展约束。约束写错可能导致汇编器无法编码、编译器选择了不正确的操作数形式，或优化后出现难以定位的问题。GCC 将 RISC-V 的 `K` 定义为 CSR 访问可用的 5 位无符号立即数。[GCC RISC-V machine constraints](https://gcc.gnu.org/onlinedocs/gcc/Machine-Constraints.html)

## 三、先分类：源码助记符不总等于一条硬件指令

`riscv.h` 中真正出现的汇编字符串可归为下表。术语上必须严格：**伪指令/别名并不表示它“没有效果”，只表示 ISA 没有以该名字定义独立编码；汇编器会将其转换为一条或多条真实编码。**

| 源码写法 | 分类 | 典型真实形式或语义 | 本文件中的用途 |
| --- | --- | --- | --- |
| `csrr rd, csr` | 汇编器伪指令 | `csrrs rd, csr, x0`，读取 CSR 且不改写 | 所有 `r_xxx()` |
| `csrw csr, rs` | 汇编器伪指令 | `csrrw x0, csr, rs`，写 CSR，丢弃旧值 | 所有 `w_xxx()` |
| `csrs csr, src` | 汇编器伪指令 | `csrrs x0, csr, src` 或立即数形式，只置位掩码为 1 的位 | 打开 `sstatus.SIE` |
| `csrc csr, src` | 汇编器伪指令 | `csrrc x0, csr, src` 或立即数形式，只清除掩码为 1 的位 | 关闭 `sstatus.SIE` |
| `csrrc rd, csr, src` | 真实 CSR 指令 | 读旧值到 `rd`，再按掩码清 CSR 位 | 原子地读取并关中断 |
| `mv rd, rs` | 汇编器伪指令 | 通常为 `addi rd, rs, 0`；可用压缩扩展时编码可能不同 | 读/写 `sp`、`tp`、`ra` |
| `sfence.vma rs1, rs2` | 真实特权指令 | 同步地址翻译缓存与页表修改 | 切换/修改页表 |
| `fence pred, succ` | 真实内存顺序指令 | 约束指定类别的访存/IO 在硬件中可见的顺序 | VirtIO 的 DMA/MMIO 交互 |
| `fence.i` | Zifencei 扩展指令 | 同步本 hart 的指令取指与此前代码写入 | 自修改代码/JIT 场景 |

RISC-V 的 CSR 规范明确将 `CSRR rd, csr` 定义为 `CSRRS rd, csr, x0` 的汇编器伪指令，并将 `CSRW csr, rs1` 定义为 `CSRRW x0, csr, rs1`。[Zicsr 规范](https://docs.riscv.org/reference/isa/v20260120/unpriv/zicsr.html)

本文件**没有**执行 `mret`、`sret` 或 `wfi`。这些名字可能出现在启动/陷阱路径的其他源文件或注释里，但不能因为它们都和 RISC-V 内核有关，就硬塞进对 `riscv.h` 的“涉及指令”讲解中。源码是什么，结论就应是什么。

## 四、CSR 指令：读取、覆盖写、按位修改

CSR（Control and Status Register，控制和状态寄存器）和 `a0`、`sp` 这类通用寄存器属于不同空间。CSR 的编号编码在指令内，硬件会依当前特权级、CSR 的只读/可写属性和已实现扩展决定访问是否合法。用一个 `volatile uint64 *` 去解引用某个“CSR 地址”不能替代 `csrr/csrw`。

### 1. `csrr`：读，不是内存加载

```c
static inline uint64
r_scause(void)
{
  uint64 x;
  asm volatile("csrr %0, scause" : "=r"(x));
  return x;
}
```

语义可写为：

```text
x = CSR[scause]
```

实际展开为 `csrrs rd, scause, x0`。`x0` 恒为零，故 CSRRS 的“置位掩码”为空，不会修改 `scause`；读出的旧值进入 `rd`。`r_mhartid()`、`r_sstatus()`、`r_satp()`、`r_time()` 等全部属于这一模式，差异只在访问的 CSR 名称和调用者如何解释结果。

### 2. `csrw`：覆盖写，需由调用者保留无意修改的位

```c
static inline void
w_sstatus(uint64 x)
{
  asm volatile("csrw sstatus, %0" : : "r"(x));
}
```

可概念化为：

```text
CSR[sstatus] = x
```

这不是说所有位一定可写。对已实现 CSR 的保留字段、只读字段和 WARL 字段如何处理，必须以该 CSR 的规范为准；而访问未实现 CSR、无权访问的 CSR 或以错误方式写只读 CSR，通常会触发 illegal-instruction 异常，不能笼统理解为“硬件忽略”。但对可写字段而言，这是覆盖式写入。因此要只改一位时，调用者通常应：

1. 先 `r_sstatus()` 读取快照；
2. 在 C 中修改所需掩码；
3. 用 `w_sstatus()` 写回。

否则一个只想修改 `SIE` 的调用，可能意外丢掉原本需要保留的其他可写控制位。

### 3. `csrs` 与 `csrc`：只改掩码指定的位

```c
s_sstatus(SSTATUS_SIE); // csrs sstatus, ...
c_sstatus(SSTATUS_SIE); // csrc sstatus, ...
```

其效果分别是：

```text
CSR[sstatus] = CSR[sstatus] | mask
CSR[sstatus] = CSR[sstatus] & ~mask
```

所以 `intr_on()`、`intr_off()` 不必先读完整的 `sstatus` 再写回；它们只改变 `SIE` 位，其他位保持不变。需要谨慎的一点是：这类“原子 read-modify-write”说的是单条指令对**该 CSR**的读改写不可被拆为两条普通指令，并不等价于获得了多核互斥锁，也不自动同步普通内存数据。

### 4. `csrrc`：为何 `push_off()` 需要“读旧值并清位”

文件中的：

```c
static inline uint64
rc_sstatus(uint64 x)
{
  __asm__ __volatile__("csrrc %0, sstatus, %1"
                       : "=r"(x) : "rK"(x) : "memory");
  return x;
}
```

对应的真实指令先把旧 `sstatus` 读到输出寄存器，再清除输入掩码为 1 的位。它在 `spinlock.c:push_off()` 中的关键使用是：

```c
uint64 flags = rc_sstatus(SSTATUS_SIE);
int old = !!(flags & SSTATUS_SIE);
```

这同时完成两件事：拿到“进入临界区前中断是否开启”的事实，并立刻禁止当前 hart 的 S 模式可屏蔽中断。若先用 `r_sstatus()` 读取、再隔一条或多条指令调用 `c_sstatus()`，中间可能已发生不希望的中断。后续嵌套的 `push_off()` 记录层数，最外层退出时才依据最初的 `old` 恢复中断状态；它比“无条件 `intr_on()`”正确得多。

## 五、这些 CSR 在 xv6 中分别服务什么

`riscv.h` 定义了很多读写包装，但它们不是同一类“系统寄存器”。按内核职责分组会更清楚。

| 分组 | 本文件涉及的 CSR | 主要问题 |
| --- | --- | --- |
| M 模式启动与委托 | `mhartid`、`mstatus`、`mepc`、`medeleg`、`mideleg`、`menvcfg`、`pmpcfg0`、`pmpaddr0`、`mcounteren` | 谁是当前 hart？`mret` 将去哪里、降到哪个模式？哪些事件交给 S 模式？ |
| S 模式中断与 trap | `sstatus`、`sie`、`sip`、`stvec`、`sepc`、`scause`、`stval` | 哪类中断可接收？trap 从哪进入？为何陷入？返回到哪？ |
| 地址翻译 | `satp` | 当前 hart 使用什么分页模式、ASID 与根页表 PPN？ |
| 定时器 | `time`、`stimecmp` | 当前计数器值是多少？下一次 S 模式定时器中断的绝对比较阈值何时到期？ |

这里最需要避免的误解有四个：

- `sstatus.SIE` 是当前 hart 的 S 模式**总开关**，`sie` 是按类别的许可位，`sip` 是已挂起的类别；三者都满足也不代表设备处理程序必然没有其他前提。
- `mstatus.MPP` 不是“当前模式变量”。启动代码设置它和 `mepc` 后，真正执行 `mret` 才根据这些状态改变特权级和 PC。
- `scause` 的最高位区分异步中断与同步异常；`stval` 的含义依赖 `scause`，对许多缺页情况它是相关虚拟地址，但不能永远不加判断地叫作“错误地址”。
- `satp` 的低位内容不是 C 指针。`MAKE_SATP(pagetable)` 会把页对齐根页表物理地址右移 12 位后放入 PPN 字段，并结合 `SATP_SV39` 选择 Sv39；读取 `satp` 得到的是 CSR 编码值。

`stimecmp` 使用数字 `0x14d`，`menvcfg` 使用 `0x30a`，是因为此仓库选择兼容未识别这些 CSR 助记名的汇编器。它们是**CSR 编号**，既不是 MMIO 地址，也不是十六进制指针。无论写助记名还是编号，访问路径仍是 CSR 指令。还应注意，`stimecmp` 属于可选的 Sstc 扩展，`time` 的 S 模式读取权限也可受更高特权级的计数器访问控制影响；它们不是每个 RISC-V S 模式环境必然提供的接口。

## 六、`mv`：读写 `sp`、`tp`、`ra` 的普通寄存器搬运

与 CSR 封装不同，下面几组操作的是通用寄存器：

```c
asm volatile("mv %0, sp" : "=r"(x));
asm volatile("mv %0, tp" : "=r"(x));
asm volatile("mv tp, %0" : : "r"(x));
asm volatile("mv %0, ra" : "=r"(x));
```

`mv` 是汇编器伪指令，通常等价于：

```asm
addi    rd, rs, 0
```

它不访问内存、不读取 CSR，只复制寄存器位模式。名称来自 ABI 约定：

| ABI 名 | 硬件寄存器 | 在此仓库中的角色 |
| --- | --- | --- |
| `sp` | `x2` | 当前执行上下文的栈指针 |
| `tp` | `x4` | xv6 在内核态缓存当前 hart ID；`cpuid()` 读取它索引 `cpus[]` |
| `ra` | `x1` | 普通函数调用的返回地址 |

特别是 `tp`：RISC-V ABI 通常把它称作 thread pointer，但 xv6 选择在内核执行上下文中保存 hart ID。这是内核约定，不是硬件保证“`tp` 永远等于 hart ID”。切入用户态后，trampoline 会恢复用户寄存器状态；内核不能从用户态 `tp` 推导 CPU 编号。

`ra` 也不能与 `sepc` 混淆。`ra` 服务普通 `call`/`ret`；`sepc` 是 S 模式 trap 保存与 `sret` 恢复的 PC，两者属于完全不同的控制流机制。

## 七、页表更新或切换时为何需要 `sfence.vma`，而不是普通 `fence`

页表是普通内存中的 PTE 数组，但 CPU 会把地址翻译结果缓存在 TLB 等地址翻译缓存中。即使 C 代码已经改写某个 PTE，或已经执行：

```c
w_satp(MAKE_SATP(kernel_pagetable));
```

CPU 仍可能根据此前缓存的翻译继续访问。xv6 的 `vm.c:kvminithart()` 因而采用：

```c
sfence_vma();
w_satp(MAKE_SATP(kernel_pagetable));
sfence_vma();
```

这是该内核针对其启动/切换路径选择的协议，不应背成所有场景都必须在写 `satp` 前后各放一条的万能配方。更一般地说，软件必须依据“改了什么映射、谁可能保留旧翻译、何时继续访问或回收旧页”来安排地址翻译同步。其封装为：

```c
asm volatile("sfence.vma zero, zero" ::: "memory");
```

`sfence.vma` 是专门服务地址翻译同步的特权指令。两个寄存器操作数分别用于限制虚拟地址和 ASID；使用 `zero, zero` 表示不按某个单独虚拟页或 ASID 缩小范围，要求本 hart 不再使用旧的相关翻译缓存。它不是“刷新所有 CPU 的全部缓存”，也不是通用 MMIO 顺序栅栏。

还有两个边界必须记住：

1. `sfence.vma` 只约束**执行它的 hart**。若其他 hart 也可能缓存同一地址空间的旧翻译，内核还需通过跨 hart 的同步机制让它们各自执行适当的同步；单靠本 hart 一条指令不能隔空清空别人的 TLB。
2. `"memory"` 只约束编译器对 C 内存操作的重排，`sfence.vma` 才约束硬件的地址翻译可见性。删掉任一层都可能在某些优化级别或微架构上留下错误窗口。

Supervisor ISA 对 `satp`、地址翻译缓存以及 `SFENCE.VMA` 的同步范围有正式定义；它也是判断页表代码是否正确的最终依据。[RISC-V Supervisor-Level ISA](https://docs.riscv.org/reference/isa/v20260120/priv/supervisor.html)

## 八、`fence iorw, iorw`：DMA/MMIO 的顺序，不是“清缓存”

本文件定义：

```c
static inline void
io_fence(void)
{
  asm volatile("fence iorw, iorw" ::: "memory");
}
```

`fence` 的前驱集合和后继集合都写为 `iorw`，表示对 I/O 与普通内存的读/写类别建立硬件顺序约束。在 xv6 的 VirtIO 路径中，典型意图是：

```text
先写描述符与 avail 环的内存
  -> fence iorw, iorw
  -> 写 MMIO 通知寄存器
  -> 设备看到“有新请求”时，也应看到完整描述符
```

反方向上，设备更新 used 环后，CPU 在确认/读取这些结果前也需要相应顺序保证。它防止的是“通知已经被设备观察到，描述符内容却尚未以所需顺序对设备可见”这种跨 CPU/设备观察顺序问题。

它**不是**：

- 互斥锁：不会排他地阻止其他 hart 修改共享数据；
- TLB 刷新：不能替代 `sfence.vma`；
- 将所有缓存逐字节写回内存的万能“flush cache”；
- 让每个 C 数据竞争自动正确的魔法。

设备一致性、DMA 映射和平台 I/O 内存模型仍是内核需要明确处理的边界。xv6 教学环境简化了许多硬件差异，不能把这一条屏障的使用方式机械搬到任意驱动。

## 九、`fence.i`：让后续取指看见新写入的代码

```c
static inline void
icache_fence(void)
{
  asm volatile("fence.i" ::: "memory");
}
```

普通数据写入与指令取指可能经过不同的微架构路径。若软件刚把机器码写入一段未来将执行的内存，例如 JIT 生成代码、打补丁或自修改代码，仅仅完成普通 store 并不足以保证后续取指看到新字节。`fence.i` 为**当前 hart**建立数据存储与之后指令取指之间的同步。

它和前两种屏障的职责不同：

| 指令 | 解决的问题 | 不能替代 |
| --- | --- | --- |
| `sfence.vma` | 页表更新/切换后，地址翻译缓存不能继续使用旧结果 | DMA/MMIO 顺序、指令缓存同步 |
| `fence iorw, iorw` | 普通内存与设备 I/O 的观察顺序 | TLB 同步、代码取指同步 |
| `fence.i` | 当前 hart 后续取指必须观察到此前写入的指令内容 | 页表/TLB 同步、跨 hart I-cache 同步 |

xv6 的常规内核路径通常不动态生成机器码，因此这只是通用接口，不是每次修改页表后应该调用的东西。并且 Zifencei 规范将 `FENCE.I` 的同步范围限定在执行该指令的 hart；若其他 hart 也要执行新代码，软件仍需要跨 hart 协调。[Zifencei 规范](https://docs.riscv.org/reference/isa/v20260120/unpriv/zifencei.html)

## 十、一个真实调用链：从 C 到硬件状态再回到 C

以“为临界区关闭当前 hart 中断”为例，路径是：

```text
spinlock.c: push_off()
  -> rc_sstatus(SSTATUS_SIE)
      -> 内联汇编 csrrc rd, sstatus, mask
          -> rd 得到旧 sstatus，硬件清除 SIE
  -> old = 旧值中是否包含 SIE
  -> 记录嵌套层数；最外层 pop_off() 才可能恢复中断
```

这里不存在对某个 `bool interrupts_enabled` 的普通内存读写。中断使能是当前 hart 的处理器状态；如果它被当成共享 C 变量处理，不但读写方式错误，还会遗漏“中断可能在两条普通指令之间到来”的事实。

再看页表启用：

```text
vm.c: kvminithart()
  -> sfence_vma()        # 将此前页表写入与后续翻译同步
  -> w_satp(MAKE_SATP(kernel_pagetable))
  -> sfence_vma()        # 不再使用旧翻译缓存
```

以及定时器重约：

```text
start.c / trap.c
  -> r_time()            # 读取单调递增的平台时间计数 CSR
  -> 当前值 + 间隔
  -> w_stimecmp(...)     # 写绝对比较阈值，预约下一次 timer interrupt
```

这些路径的共同点是：C 代码负责计算策略和维护内核数据结构，`riscv.h` 用极少量汇编负责触达 C 无法表达的硬件状态。它不应自行掩盖策略，也不应扩张成“所有硬件逻辑都写在头文件里”。

## 十一、如何验证：不要猜某条内联汇编最后长什么样

在 xv6 目录中可先构建内核，再对最终 ELF 反汇编。交叉工具链前缀随安装方式不同而变，下面仅示意：

```bash
make kernel/kernel
riscv64-unknown-elf-objdump -d -M no-aliases kernel/kernel | less
```

`-M no-aliases` 尽量让反汇编器显示真实编码而非友好别名。你可以搜索：

```bash
riscv64-unknown-elf-objdump -d -M no-aliases kernel/kernel \
  | rg "csrrs|csrrw|csrrc|sfence\.vma|fence\.i|fence"
```

预期观察点如下：

- `r_sstatus()` 等读包装会显示为 `csrrs ..., sstatus, zero` 一类真实形式；
- `w_satp()` 会显示为目的寄存器为 `zero` 的 `csrrw`；
- `rc_sstatus()` 应保留单条 `csrrc` 或对应立即数形式，而非被拆成“先读再写”；
- `sfence.vma`、`fence`、`fence.i` 是需要保留的屏障指令；
- `mv` 是否显示为 `addi` 或压缩指令，取决于目标 ISA 与反汇编选项。

若想检查 C 到汇编的边界，可让编译器保留汇编输出：

```bash
riscv64-unknown-elf-gcc -S -O2 -march=rv64gc -mabi=lp64 \
  -I kernel -o example.s example.c
```

不过不要只凭某一次 `-O0` 的输出给所有情况定论。寄存器分配、内联与是否采用立即数形式都会随优化级别、编译器版本、`-march` 和调用点常量传播改变；不变的应该是本文解释的接口语义与硬件约束。

## 十二、修改这类封装时最危险的错误

| 错误做法 | 为什么错 | 更合适的原则 |
| --- | --- | --- |
| 用普通指针解引用“CSR 地址” | CSR 不在普通虚拟内存空间，且访问有特权规则 | 使用对应 CSR 指令封装 |
| 将 `csrr` 当成独立机器编码 | 它是 `csrrs ..., x0` 的别名 | 讨论性能、反汇编或副作用时看真实形式 |
| 用 `r_sstatus()` + `w_sstatus()` 替代 `csrrc` | 在读和写之间留下中断/状态变化窗口，且可能覆盖其他位 | 需要读旧值并按位改时用恰当 CSR RMW 指令 |
| 写 `satp` 后省略 `sfence.vma` | 当前 hart 仍可能命中旧 TLB 翻译 | 依据地址空间和修改范围执行正确同步 |
| 把 `fence` 当 cache flush 或锁 | 它只建立规定访问类别的顺序 | 分别处理互斥、DMA 一致性和翻译同步 |
| 只有 `volatile`，却遗漏 `"memory"` | 编译器仍可能移动普通内存访问 | 对确实需要的内存边界显式声明 clobber |
| 无条件相信 `tp` 一直是 hart ID | 这是 xv6 内核上下文约定，不是硬件永久属性 | 只在约定成立的内核上下文使用 |
| 把 `0x14d`、`0x30a` 当地址 | 它们是指令内的 CSR 编号 | 依据 CSR 编码与扩展规范解释 |

## 总结

`riscv.h` 的价值不在于“把汇编藏起来”，而在于把一组必须精确处理的硬件动作收束为可审计的 C 接口：

- `csrr/csrw/csrs/csrc/csrrc` 管理特权 CPU 状态；前四个是汇编器友好别名，`csrrc` 是真实的 CSR 读改写指令。
- `mv` 只在通用寄存器间复制位模式；`sp`、`tp`、`ra` 的特殊含义来自 ABI 和 xv6 约定。
- `sfence.vma` 管页表与 TLB 的同步；它只作用于执行它的 hart。
- `fence iorw, iorw` 管设备 I/O 与普通内存的硬件观察顺序；它不是锁，也不是 TLB 刷新。
- `fence.i` 管当前 hart 的后续指令取指；它不是页表同步工具。
- `asm volatile`、操作数约束和 `"memory"` clobber 负责让编译器与硬件遵守同一份边界契约。

读这类代码时，最可靠的方法不是看到 `r_`、`w_` 就把它们当作普通 getter/setter，而是连续追问：**它访问的是普通内存、通用寄存器还是 CSR？该助记符是否为别名？CPU 的真实状态变化是什么？编译器能否跨越它重排内存访问？这条同步只影响本 hart，还是还需要其他 hart/设备的配合？**如此一来，这个头文件便不再是一片密集的咒语，而是 xv6 与 RISC-V 硬件之间一份边界清晰的契约。
