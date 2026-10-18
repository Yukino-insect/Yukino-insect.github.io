+++
date = '2026-09-13T00:00:00+08:00'
draft = false
title = 'RISC-V 的 CSR 与页表：相关指令、寄存器和同步机制'
+++

在 RISC-V 内核代码中，`csrr`、`csrw satp`、`sfence.vma` 往往各只占一行，却分别跨越了三种完全不同的状态：**处理器控制状态、普通内存中的页表、以及 hart 内部缓存的地址翻译结果。**如果把它们都看成“读写寄存器”或“刷新缓存”，页表代码迟早会在切换地址空间、缺页处理或多核回收页面时出错。

本文以支持 M/S/U 特权级的 RV64 实现和 Sv39 分页为主线，独立说明与 CSR、trap、页表最相关的指令和寄存器。它不依赖某个内核的宏名：示例中的位移与位域来自 RISC-V 架构；何时写这些寄存器、怎样分配页面、怎样向其他 hart 发 IPI，则是操作系统必须设计的协议。

## 一、先看全景：四类对象和四类操作

```text
C 变量 / 普通内存
  └─ store PTE ──────────────> 页表页（物理内存中的普通数据）

通用寄存器 x0-x31
  └─ csrr / csrw ────────────> CSR（每个 hart 的控制和状态）

虚拟地址 VA
  └─ satp + 页表遍历 ────────> 物理地址 PA
                              └─ TLB 缓存翻译结果

页表更新后
  └─ sfence.vma ─────────────> 令执行该指令的 hart 不再按旧翻译继续访问
```

| 对象 | 例子 | 谁能访问/修改 | 关键误解 |
| --- | --- | --- | --- |
| 通用寄存器 | `a0`、`sp`、`ra` | 当前 hart 上的普通指令 | 不是 CSR；ABI 名称不是硬件类型 |
| CSR | `sstatus`、`stvec`、`satp` | 取决于特权级、CSR 属性和扩展 | 不是可由指针解引用的内存地址 |
| 页表 | 根表、PTE | 软件以普通 load/store 读写 | 改 PTE 不会自动清除 TLB |
| TLB | VPN→PPN 与权限的缓存 | 硬件填充；软件通过同步指令约束使用 | 不是“所有 CPU 共用的一张缓存” |

从这一刻开始，读代码时应持续追问：它是在改**页表内存**、**CSR**，还是在让**当前 hart 的翻译缓存**与前两者同步？问题对象不同，正确指令也不同。

## 二、CSR 是什么：每个 hart 的独立控制状态

CSR（Control and Status Register，控制和状态寄存器）位于独立的 12 位 CSR 编号空间中，理论上可编码 4096 个编号。它们与 `x0`–`x31` 通用寄存器分离，也不经过虚拟地址翻译。RISC-V 的 Zicsr 扩展定义了访问 CSR 的指令；标准 CSR 编号高位还按约定编码只读/可写属性和最低可访问特权级。[RISC-V CSR 地址空间与访问约定](https://docs.riscv.org/reference/isa/priv/priv-csrs.html)

```asm
csrr    a0, sstatus   # a0 = 当前 hart 的 sstatus
csrw    satp, a0      # 当前 hart 的 satp = a0
```

它们与普通内存访问的区别是：

```asm
ld      a0, 0(a1)     # 用 a1 形成 VA，经过页表翻译后读普通内存
csrr    a0, sstatus   # 不形成内存地址，直接读当前 hart 的 CSR
```

无权限访问、访问未实现 CSR，或以不允许的方式写只读 CSR，通常会产生 illegal-instruction 异常。不要将 CSR 保留位或 WARL 字段的处理一概理解成“硬件会忽略”；每个 CSR 的字段行为应查对应规范。

### 1. CSR 指令的六种基础形式

所有 CSR 指令对**同一个 CSR**完成原子的读—改—写；“原子”只指这条 CSR 操作不会拆成普通读写两条指令，不代表获得多核共享内存锁。

| 指令 | 输入 | 输出 | 对 CSR 的效果 |
| --- | --- | --- | --- |
| `csrrw rd, csr, rs1` | `rs1` 新值 | `rd` 得到旧值 | 覆盖写 CSR |
| `csrrs rd, csr, rs1` | `rs1` 位掩码 | `rd` 得到旧值 | CSR 中掩码为 1 的位被置位 |
| `csrrc rd, csr, rs1` | `rs1` 位掩码 | `rd` 得到旧值 | CSR 中掩码为 1 的位被清零 |
| `csrrwi rd, csr, uimm` | 5 位无符号立即数 | `rd` 得到旧值 | 覆盖写 CSR |
| `csrrsi rd, csr, uimm` | 5 位无符号立即数 | `rd` 得到旧值 | 按立即数置位 |
| `csrrci rd, csr, uimm` | 5 位无符号立即数 | `rd` 得到旧值 | 按立即数清位 |

汇编器还提供更常用的别名：

| 源码写法 | 实际基础形式 | 语义 |
| --- | --- | --- |
| `csrr rd, csr` | `csrrs rd, csr, x0` | 只读 CSR；掩码为 0，不改写 |
| `csrw csr, rs` | `csrrw x0, csr, rs` | 覆盖写 CSR；丢弃旧值 |
| `csrs csr, rs` | `csrrs x0, csr, rs` | 仅置掩码指定的位 |
| `csrc csr, rs` | `csrrc x0, csr, rs` | 仅清掩码指定的位 |

例如，关闭 S 模式全局中断可以写成：

```asm
csrrc   t0, sstatus, t1
```

若 `t1` 中只有 `SIE` 对应的位为 1，则 `t0` 得到关闭前的完整 `sstatus`，而硬件在同一条指令中清除 `SIE`。这比“先读 `sstatus`，隔几条指令再写回”少了一个可被中断打断的窗口。

需要严谨地区分两件事：`csrrw x0, csr, rs1` 因 `rd=x0` 而不读取 CSR；而 `csrrs/csrrc` 即使目的寄存器为 `x0` 也会读取 CSR。对具有访问副作用的自定义 CSR，这种差异可能很重要。Zicsr 对六种形式、`x0` 和立即数为零时是否实际读/写 CSR 有精确定义。[RISC-V Zicsr 规范](https://docs.riscv.org/reference/isa/unpriv/zicsr.html)

### 2. CSR、trap 和中断最常用的寄存器

下表只列出页表和 trap 路径最常接触的 CSR；并不表示某颗 RISC-V 芯片必须全部实现。

| 类别 | M 模式 | S 模式 | 核心含义 |
| --- | --- | --- | --- |
| trap 向量 | `mtvec` | `stvec` | trap 第一条指令的地址及 direct/vectored 模式 |
| trap PC | `mepc` | `sepc` | 被中断/发生异常的指令地址；`mret/sret` 的返回目标 |
| trap 原因 | `mcause` | `scause` | 最高位区分 interrupt 和 exception，其余位为原因码 |
| trap 附加值 | `mtval` | `stval` | 如许多缺页中的相关 VA；含义依 cause 而定 |
| 返回/中断状态 | `mstatus` | `sstatus` | 保存先前特权级、全局中断使能等状态 |
| 中断许可和挂起 | `mie` / `mip` | `sie` / `sip` | 哪类中断可交付、哪类中断已挂起 |
| 委托 | `medeleg` / `mideleg` | — | M 模式决定较低级事件是否由 S 模式接收 |
| 地址翻译 | — | `satp` | 分页模式、ASID、根页表 PPN |
| scratch | `mscratch` | `sscratch` | 软件约定的每 hart 暂存槽；不是硬件自动 trapframe |

## 三、trap 相关 CSR：硬件保存最小现场，不会替你保存寄存器

### 1. `mtvec` / `stvec`：向量入口

`mtvec` 与 `stvec` 均由高位的 BASE 和低两位的 MODE 组成：

```text
XLEN-1                              2 1       0
+------------------------------------+-----------+
| BASE                               | MODE      |
+------------------------------------+-----------+
```

| MODE | 行为 |
| --- | --- |
| `0`，Direct | 所有异常和中断从 `BASE` 开始执行 |
| `1`，Vectored | 异常从 `BASE` 开始；中断从 `BASE + 4 × cause` 开始 |

向量 CSR 不是 C 函数指针调用机制。写 `stvec=entry` 后，下一次由 S 模式处理的 trap 会使 CPU 的 PC 指向入口汇编的第一条指令。该入口自己仍要解决：正在使用哪张页表、栈在哪里、怎样保存通用寄存器、怎样再进入 C 代码。

### 2. `xepc`、`xcause`、`xtval`：从哪里来、为何而来

以 S 模式 trap 为例，硬件会写：

```text
sepc   = 被中断或发生同步异常的指令地址
scause = interrupt 标志 + cause code
stval  = 与该类异常有关的附加值（若规范定义）
PC     = stvec 指定的入口
```

在 RV64 中，`scause` 的 bit 63 为 1 表示中断，为 0 表示同步异常；其余位保存原因码。常见同步异常码包括：

| cause | 含义 |
| ---: | --- |
| `2` | illegal instruction |
| `8` | environment call from U-mode |
| `9` | environment call from S-mode |
| `11` | environment call from M-mode |
| `12` | instruction page fault |
| `13` | load page fault |
| `15` | store/AMO page fault |

`ecall` 是 32 位 SYSTEM 指令。它触发 trap 后，`sepc`/`mepc` 通常仍指向这条 `ecall`；若内核决定正常返回，必须在软件中把对应 `xepc` 前移 4 字节，避免再次执行同一条系统调用。相反，缺页处理成功后一般希望重试原来的 load/store/取指，因此不应机械地推进 `xepc`。

`stval` 在 instruction/load/store page fault 中常包含相关 VA，但它不是普适“坏地址寄存器”：对其他 cause 可能为 0、指令位模式，或实现定义的值。处理程序必须先判定 `scause`，再解释 `stval`。

### 3. `mstatus` / `sstatus`：进入与返回的硬件状态机

trap 进入时，硬件会保存“之前的中断开关和之前的权限”，并关闭当前处理级的全局可屏蔽中断。与 M/S trap 最相关的字段为：

| 字段 | 位 | 含义 |
| --- | ---: | --- |
| `mstatus.MIE` / `sstatus.SIE` | 3 / 1 | 当前 M/S 模式的全局可屏蔽中断开关 |
| `mstatus.MPIE` / `sstatus.SPIE` | 7 / 5 | trap 前 MIE/SIE 的保存槽 |
| `mstatus.MPP` | 12:11 | M trap 前的权限，也是 `mret` 的目标权限；`00=U`、`01=S`、`11=M` |
| `sstatus.SPP` | 8 | S trap 前的权限；`0=U`、`1=S` |

核心状态转移如下：

```text
进入 S trap：SPIE = SIE；SIE = 0；SPP = 原 U/S 模式；PC = stvec
sret：         特权级 = SPP；SIE = SPIE；SPIE = 1；SPP = 0；PC = sepc

进入 M trap：MPIE = MIE；MIE = 0；MPP = 原权限；PC = mtvec
mret：         特权级 = MPP；MIE = MPIE；MPIE = 1；MPP = 最低支持级；PC = mepc
```

这解释了两个常见现象：`sret` 不从 `ra` 返回，而从 `sepc` 返回；`mret` 能从 M 模式进入 S 模式或 U 模式，因为它读取的是 `MPP`，而普通 `ret` 绝不改变特权级。

### 4. `mie/mip` 与 `sie/sip`：中断不是一个 bool

以 S 模式为例，某个可屏蔽中断要被交付，至少要同时满足：全局 `SIE=1`、相应 `sie` 分类许可位为 1、相应 `sip` 挂起位为 1，并且委托/当前特权级/平台中断控制器的条件允许在 S 模式处理。

| 类别 | S 模式许可/挂起 | M 模式许可/挂起 | 常见来源 |
| --- | --- | --- | --- |
| software | `SSIE` / `SSIP`，bit 1 | `MSIE` / `MSIP`，bit 3 | IPI 或平台软件中断机制 |
| timer | `STIE` / `STIP`，bit 5 | `MTIE` / `MTIP`，bit 7 | 比较器、定时器或平台转发 |
| external | `SEIE` / `SEIP`，bit 9 | `MEIE` / `MEIP`，bit 11 | PLIC 或其他中断控制器 |

`sie`/`mie` 是许可，`sip`/`mip` 是挂起状态。许多挂起位由硬件或中断控制器驱动，不能随意用 `csrw` 清除；正确的确认动作可能是读取/完成 PLIC、重新设置定时器比较值，或遵守平台定义的 IPI 协议。

### 5. `medeleg` / `mideleg`：谁处理 trap

`medeleg` 与 `mideleg` 的每一位以 cause code 为索引。某位为 1 时，符合条件且来自较低特权级的相应异常或中断可交给 S 模式；为 0 时由 M 模式处理。委托不会将 M 模式 CSR 的权限交给 S 模式，也不能把发生在 M 模式本身的 trap 继续委托到 S 模式。

```text
U/S 模式事件发生
  -> 对应 deleg 位为 0：M trap，使用 mtvec/mepc/mcause/mtval
  -> 对应 deleg 位为 1：S trap，使用 stvec/sepc/scause/stval

M 模式事件发生
  -> 总是 M trap
```

## 四、`satp`：当前 hart 的地址翻译根

`satp`（Supervisor Address Translation and Protection）是 S 模式的地址翻译 CSR。它同时选择分页模式、地址空间标识 ASID 和根页表物理页；它不是指向页表的普通虚拟指针。

RV64 下的字段为：

```text
63          60 59                  44 43                         0
+--------------+----------------------+-----------------------------+
| MODE (4 bit) | ASID (16 bit)        | PPN (44 bit)                |
+--------------+----------------------+-----------------------------+
```

| MODE | 名称 | 含义 |
| ---: | --- | --- |
| `0` | Bare | 不启用页表地址转换 |
| `8` | Sv39 | 39 位有效 VA、三级页表、4 KiB 基页 |

若根页表的物理基址是页对齐的 `root_pa`，当前地址空间的 ASID 是 `asid`，则概念性构造为：

```c
uint64_t make_satp_sv39(uint64_t root_pa, uint16_t asid)
{
    return (8ULL << 60) | ((uint64_t)asid << 44) | (root_pa >> 12);
}
```

`root_pa >> 12` 是根页表的 **PPN**。低 12 位为 0 是页对齐的结果，并不存入 `satp`。反过来，读取 `satp` 后应先提取 PPN 再左移 12 位，才能得到根页表物理基址；不能把整个 CSR 数值直接强转为 C 指针。

`satp` 是每 hart 的状态。两个 hart 想使用同一页表，也必须各自写自己的 `satp`；同一个 VA 在不同 hart/不同时间若 `satp` 指向不同根表，就可能翻译到不同 PA。实现支持的 ASID 位数可能少于字段宽度，操作系统应按架构规定探测可用位数，不应默认全部 16 位有效。

## 五、Sv39 页表：VPN、PPN、PTE 与硬件遍历

### 1. 页、offset、VPN 与 PPN

Sv39 的基页是 4 KiB，即 `2^12` 字节。任何地址低 12 位都是页内 offset：

```text
offset = VA[11:0] = PA[11:0]
```

虚拟页号 VPN 是 VA 去掉 offset 后的索引部分；物理页号 PPN 是 PA 去掉 offset 后的页号。若物理页基址为：

```text
PA = 0x0000000080234000
PPN = PA >> 12 = 0x80234
```

而某次访问的 offset 为 `0x456`，最终物理地址为：

```text
(PPN << 12) | offset = 0x0000000080234456
```

VPN 和 PPN 都是页号。它们不表达“该页属于谁”，也不带 C 类型；PTE 的权限位、物理页管理器和上层内存管理策略才共同决定是否允许映射、访问和复用。

### 2. Sv39 虚拟地址位域

Sv39 仅使用 39 位 VA 信息。RV64 的 VA 寄存器宽度仍是 64 位，因此 bit 63 到 bit 39 必须全为 bit 38 的符号扩展：

```text
63                    39 38       30 29       21 20       12 11       0
+-----------------------+-----------+-----------+-----------+----------+
| bit 38 的符号扩展       | VPN[2]    | VPN[1]    | VPN[0]    | offset   |
+-----------------------+-----------+-----------+-----------+----------+
                             9 bit      9 bit      9 bit      12 bit
```

地址不满足这一 canonical 形式时，不能指望硬件“自动截成低 39 位”；它会导致地址翻译失败。三个 VPN 各 9 位，故每层页表有 `2^9=512` 个条目；PTE 是 8 字节，所以一张页表正好占一个 4 KiB 页。

```c
vpn2   = (va >> 30) & 0x1ff;
vpn1   = (va >> 21) & 0x1ff;
vpn0   = (va >> 12) & 0x1ff;
offset =  va        & 0xfff;
```

例：`va = 0x0000000040123456` 时：

```text
VPN[2] = 0x001
VPN[1] = 0x000
VPN[0] = 0x123
offset = 0x456
```

### 3. Sv39 PTE 位域与叶子判断

Sv39 PTE 是 64 位：

```text
63              54 53                    10 9      8 7 6 5 4 3 2 1 0
+----------------+-------------------------+--------+---+---+---+---+---+---+
| reserved / ext |          PPN            | RSW    | D | A | G | U | X | W | R | V |
+----------------+-------------------------+--------+---+---+---+---+---+---+---+
```

| 位 | 字段 | 含义 |
| ---: | --- | --- |
| 0 | `V` | valid；为 0 时无效 |
| 1/2/3 | `R/W/X` | 读、写、取指权限；`W=1,R=0` 是保留组合 |
| 4 | `U` | U 模式是否可访问 |
| 5 | `G` | 全局映射提示；影响按 ASID 的 TLB 失效范围 |
| 6/7 | `A/D` | Accessed / Dirty 状态 |
| 8:9 | `RSW` | 保留给软件 |
| 10:53 | `PPN` | 下一层页表或最终物理页的 PPN |

判断 PTE 时，不要只看 `V`：

```text
V = 0                    -> 无效，产生 page fault
V = 1 且 R=W=X=0         -> 非叶子项，PPN 指向下一张页表
V = 1 且 R=1 或 X=1      -> 叶子项，PPN + offset 完成映射
```

`A/D` 的维护方式依实现和启用的扩展而异：硬件可能在首次访问/写入时更新它们，也可能要求软件通过 page fault 维护。写内核时不能只因某个模拟器“自动帮你置位”就假定所有实现的策略相同。

若要创建一项 4 KiB 可读、可写、可供 U 模式访问的叶子映射，概念公式是：

```c
pte = ((pa >> 12) << 10) | PTE_V | PTE_R | PTE_W | PTE_U;
```

它应读作“将 `pa` 转为 PPN，放到 PTE 的 bit 10 起始处，再放入权限位”；不要把 VA 误填入 PPN 字段。

### 4. 硬件页表遍历和 superpage

硬件从 `satp.PPN << 12` 得到根页表**物理地址**，并按顺序使用三个 VPN：

```text
根表[VPN[2]]
  -> 非叶子：其 PPN 给出 level-1 表物理地址
  -> 叶子：这是 1 GiB superpage

level-1 表[VPN[1]]
  -> 非叶子：其 PPN 给出 level-0 表物理地址
  -> 叶子：这是 2 MiB superpage

level-0 表[VPN[0]]
  -> 叶子：这是 4 KiB 页
```

普通 4 KiB 页的最终地址是：

```text
PA = (leaf_pte.PPN << 12) | VA[11:0]
```

若高层已经是叶子 PTE，硬件不再向下读表，而使用更多的 VA 低位作为页内偏移：level 1 的 2 MiB 页使用 VA[20:0]，level 2 的 1 GiB 页使用 VA[29:0]。这要求 PTE 对应的低位 PPN 字段为零，以保证物理地址按大页大小对齐；否则该 PTE 无效。

## 六、`sfence.vma`：页表内存与 TLB 之间的同步

### 1. 为什么写 PTE 或 `satp` 后仍可能出错

页表是普通内存，软件可以用普通 store 改 PTE；但硬件为了避免每次访问都走三级表，会把 VPN→PPN 与权限放进 TLB。于是：

```text
软件：PTE 已从 “VA -> 旧 PA” 改为 “VA -> 新 PA”
当前 hart：TLB 仍命中 “VA -> 旧 PA”
结果：下一次访问仍可能到旧 PA，根本不重新读取 PTE
```

写 `satp` 也不自动建立页表更新与后续翻译之间所需的顺序，更不能保证先前 TLB 项永远不会被使用。因此切换地址空间、修改映射或撤销映射时，软件必须在适当位置执行 `sfence.vma`。

### 2. 指令形式和作用范围

```asm
sfence.vma rs1, rs2
```

- `rs1`：限制虚拟地址范围；`x0` 表示不按某个 VA 缩小范围。
- `rs2`：限制 ASID；`x0` 表示不按某个 ASID 缩小范围。

最保守、最容易正确理解的形式是：

```asm
sfence.vma zero, zero
```

它在**执行该指令的当前 hart**上，对所有 VA、所有 ASID（含全局映射）执行地址翻译同步。若 `rs2` 为非零 ASID，全球映射不在这一 ASID 专属同步的范围内；这正是 `G` 位可能影响精细失效策略的原因。

`sfence.vma` 不是普通内存锁，不是 cache flush，不是对设备 DMA 的一致性操作，也不会在其他 hart 上自动执行。它的对象是当前 hart 的显式内存访问与隐式页表遍历/地址翻译之间的架构同步。其精确语义、ASID 重用规则与可选细粒度失效扩展应以 [Supervisor ISA 的 `satp` 与 `SFENCE.VMA` 定义](https://docs.riscv.org/reference/isa/priv/supervisor.html) 为准。

### 3. 多 hart TLB shootdown：何时可以回收旧页

若 hart 0 修改一个地址空间的 PTE，而 hart 1 仍可能运行该地址空间，hart 0 的 `sfence.vma` 不会清掉 hart 1 的旧 TLB。一个通用的撤销映射协议是：

```text
1. 在页表内存中撤销/替换 PTE，并按共享数据协议发布修改。
2. 找出可能缓存该地址空间的所有其他 hart。
3. 向目标 hart 发送 IPI 或等价请求。
4. 每个目标 hart 执行范围合适的 sfence.vma。
5. 每个目标 hart 确认完成。
6. 收到所有确认后，才能回收或复用旧物理页、旧页表页。
```

缺少第 5、6 步会形成危险窗口：远端 hart 的旧 VA 仍可到达一个已经重新分配给其他对象的 PA。`sfence.vma` 是每个 hart 上的必要动作，IPI、等待确认和页面生命周期管理则属于操作系统协议。

## 七、相关但不能替代它的指令

| 指令 | 主要对象 | 何时使用 | 不能替代 |
| --- | --- | --- | --- |
| `csrr*` / `csrw*` | CSR | 读写状态、向量、`satp`、状态位 | 页表内存同步、TLB 同步、锁 |
| `sfence.vma` | 地址翻译/TLB | 改 PTE、切换/复用地址空间 | DMA/MMIO 顺序、I-cache 同步、远端 hart 协调 |
| `fence pred,succ` | 普通内存/I/O 的观察顺序 | 发布设备描述符、严格的跨访问排序 | TLB 失效、互斥、缓存维护 |
| `fence.i` | 当前 hart 的后续指令取指 | JIT、动态代码生成、代码补丁 | PTE/TLB 同步、跨 hart 代码发布 |
| `mret` / `sret` | trap 返回状态 | 从 M/S trap 返回 | 切换 `satp`、恢复全部通用寄存器 |
| `ecall` | trap 进入 | 主动请求环境服务 | 普通函数调用 |
| `wfi` | 等待中断条件 | 空闲循环 | 内存屏障、锁、设备确认 |

例如，内核切换用户页表时，常将写 `satp`、保存/恢复寄存器、`sfence.vma`、最后 `sret` 放在邻近位置；但它们各自解决的状态不同：

```text
w_satp(new)     -> 当前 hart 选择新的根页表/ASID
sfence.vma ...  -> 当前 hart 不再依赖旧翻译
恢复通用寄存器    -> 由软件/trapframe 完成
sret            -> 由 sepc/sstatus 恢复 PC、权限和中断状态
```

其中任意一步都不能被另一步“顺便完成”。

## 八、三条完整路径：把寄存器和指令串起来

### 1. 启用一张已构造的 Sv39 根页表

前提：根表和所有必要下级表都已在物理内存中正确建立；切换后当前执行路径、栈和所需数据仍可映射。

```text
root_pa 已页对齐
  -> satp = MODE=Sv39 | ASID | (root_pa >> 12)
  -> 执行范围合适的 sfence.vma
  -> 后续取指/load/store 按新翻译进行
```

错误的思路是“把 `root_pa` 原样写入 `satp` 就完成”。`satp` 需要 PPN 和模式字段；页表本身也必须可遍历；同步后还要确保所有相关 hart 都遵守同一地址空间切换协议。

### 2. 处理用户态 `ecall`

```text
U 模式执行 ecall
  -> 委托条件满足时，硬件写 sepc/scause/stval、更新 sstatus，并跳到 stvec
  -> trap 入口汇编保存通用寄存器，建立内核上下文
  -> 内核根据 scause 识别 U-mode ecall，根据 ABI/trapframe 取调用号和参数
  -> 内核将 sepc 前移 4，避免返回后再次 ecall
  -> 准备 sstatus.SPP/SPIE、恢复寄存器，必要时切 satp 并同步
  -> sret：回到 sepc，权限按 SPP 恢复
```

其中 CPU 自动完成的是最小 trap CSR 状态；系统调用号、参数、通用寄存器保存、内核栈和页表选择均由软件完成。

### 3. 取消一个映射并回收物理页

```text
找到叶子 PTE
  -> 清除 V 或以新 PPN/权限重写 PTE
  -> 当前 hart 执行 sfence.vma（按 VA/ASID 缩小或全范围）
  -> 向仍可能缓存旧翻译的其他 hart 发 shootdown 请求
  -> 等待每个目标 hart 执行 sfence.vma 并确认
  -> 才把旧 PA 交还页分配器
```

这里最不应省略的是“等待确认”。没有它，旧 VA 可能在另一个 hart 上访问到已经被复用的物理页；这既是内存安全问题，也是进程隔离问题。

## 九、调试与审阅清单

遇到“写 `satp` 后死机”“缺页地址不对”“取消映射后随机内存损坏”时，按以下顺序排查：

1. **模式与权限**：当前真的在 S 模式吗？`satp.MODE` 是 Bare 还是 Sv39？CSR 访问是否有权限？
2. **根表**：`satp.PPN << 12` 是否是页对齐、可读取的根表物理地址？
3. **VA 格式**：Sv39 VA 的 bit 63:39 是否为 bit 38 的符号扩展？
4. **三级 PTE**：每一级 `V` 是否为 1？非叶子是否真的 `R=W=X=0`？叶子 PPN 和权限是否正确？
5. **访问类型**：取指要求 `X`，写要求 `W`，U 模式还要求 `U`；不要只检查 `V`。
6. **trap 记录**：`scause` 最高位是中断还是异常？原因码是什么？`stval` 是否应按该原因解释？
7. **TLB 同步**：改 PTE 或换根表后，当前 hart 和所有可能持有旧翻译的远端 hart 是否执行了正确范围的 `sfence.vma`？
8. **页面生命周期**：远端确认前是否已经复用旧 PA？
9. **不要错用屏障**：这里需要的是 `sfence.vma`、`fence`、`fence.i`、锁还是 DMA cache maintenance？它们不能相互替代。

## 总结

读 CSR 与页表代码时，最可靠的方式是把每一行归入正确层次：

- `csrr*`/`csrw*` 读写的是当前 hart 的 **CSR**；它们不是普通内存访问。
- `satp` 把 **模式、ASID、根页表 PPN** 交给地址翻译硬件；它不是 C 指针。
- Sv39 用 `VPN[2:0]` 三级索引 PTE，叶子 PTE 的 **PPN 与 offset** 组成 PA；PTE 的 `R/W/X/U` 决定访问许可。
- `stvec`、`sepc`、`scause`、`stval`、`sstatus` 组成 S trap 的最小硬件现场；通用寄存器与内核栈仍须由软件管理。
- `sfence.vma` 让**当前 hart**停止依赖旧地址翻译；跨 hart 的 TLB shootdown、确认与旧页回收是操作系统协议。
- `fence`、`fence.i`、`sret`、锁和 DMA 同步各有不同对象；名字里都带着某种“同步”的意味，恰恰更不能互相冒充。

一旦能明确回答“它改了哪个 CSR、哪块页表内存、哪个 hart 的 TLB、谁还可能看到旧状态”，CSR 与页表代码就不再是一串看似神秘的短指令，而是一份能够逐项验证的硬件—软件契约。
