+++
date = '2026-11-27T20:00:00+08:00'
draft = false
title = '8086 汇编语言系统教程：分段、指令、寻址与 DOS 中断'
+++

8086 汇编的关键不是死记缩写，而是让每一步都可追踪：数据在哪个段，偏移如何取得，指令读写什么，哪些标志位改变，以及下一条指令到哪里。本篇以 **8086 实模式、MASM/TASM 语法和 DOS 程序** 为范围，建立读题、写程序和调试所需的完整基础。

本文中的 `DATA`、`CODE` 是程序员定义的段名；段使用 `SEGMENT` 和 `ENDS` 显式定义。`@DATA` 是 MASM 简化内存模型生成的预定义符号，不是定义段的语法，因此本文不依赖它。

## 一、8086 的机器模型

8086 是 16 位处理器：通用寄存器和多数算术操作数宽度为 16 位，数据总线为 16 位；地址总线却有 20 位，因此可访问 1 MiB（`2^20` 字节）物理内存。为了用 16 位寄存器表达 20 位地址，8086 采用分段机制：

```text
物理地址 = 段地址 × 10H + 偏移地址
```

例如：

```text
DS = 2000H，SI = 0030H
逻辑地址 = 2000H:0030H
物理地址 = 20000H + 0030H = 20030H
```

段地址左移四位后再加偏移，所以不同的“段:偏移”组合可能映射到同一物理地址。程序取指使用 `CS:IP`；普通数据通常位于 `DS`；栈在 `SS`；字符串目的区默认在 `ES`。读取内存时先判断默认段寄存器，再计算有效地址，不能只盯着方括号。

### 1. 从取指到执行：CPU 实际在循环什么

把一条汇编指令写在源文件中，并不等于 CPU 已经能执行它。汇编器先把助记符翻译成机器码；程序装入内存后，8086 不断重复下面的过程：

1. 用 `CS:IP` 取出下一条机器指令。
2. 对指令译码，确定操作码、操作数宽度、寻址方式和是否需要访问内存。
3. 读取寄存器或内存操作数，交给执行部件完成加法、逻辑、地址计算或转移判断。
4. 将结果写回寄存器或内存，并按指令规则更新 FLAGS。
5. 若不是转移、调用、中断或返回，`IP` 自动指向顺序的下一条指令；否则由控制流指令给出新的位置。

因此，阅读汇编时最可靠的记录方式不是给一段代码笼统贴上“初始化”标签，而是每条指令都写出：**读什么、写什么、FLAGS 怎样变、下一条在何处**。例如：

```asm
ADD AX, [SI]
```

需要先把 `DS:SI` 指向的一个字读入执行单元，和旧 `AX` 相加，将低 16 位写回 `AX`，并更新 `CF`、`OF`、`SF`、`ZF`、`AF`、`PF`。这比“AX 加数组元素”多出来的细节，正是条件转移、进位扩展和调试时真正需要的部分。

### 2. 段寄存器不是内存保护机制

实模式的段只是地址计算的一部分。任何段寄存器都可以装入许多值，CPU 不会检查 `DS` 是不是“数据段”、`SS` 是不是“栈段”。`ASSUME` 也不改变这个事实：它只影响汇编器如何生成和检查地址表达式。

例如 `DS=1000H`、`ES=1001H` 时，两个段的物理基址只相差 16 字节。它们可以重叠；这正是段地址左移四位带来的结果。实模式没有现代操作系统那样按进程隔离的页表权限，错误的段值或偏移可能覆盖任意可访问内存。后续 80286 的保护模式和 80386 的分页改变了保护模型，但不改变本文讨论的 8086 指令基本语义。

### 3. 字节编址、字访问与小端序

内存按字节编号。`MOV AL, [SI]` 只访问一个字节；`MOV AX, [SI]` 连续访问 `SI` 和 `SI+1` 两个字节。8086 使用小端序，故：

```text
地址       2000H   2001H
内容       34H     12H
MOV AX,[SI]（SI=2000H）后：AX = 1234H
```

数组步长由元素类型决定，而不是由寄存器名字决定。`DB` 数组的下一个元素是 `SI+1`；`DW` 数组的下一个元素是 `SI+2`。这也是“10 个 16 位数求最小值”中每轮要 `ADD SI, 2` 的原因。

## 二、寄存器与 FLAGS

### 1. 通用、指针和段寄存器

| 寄存器 | 可拆分 | 常见用途 |
| --- | --- | --- |
| `AX` | `AH:AL` | 累加器；乘除法、DOS 功能号常隐含使用 |
| `BX` | `BH:BL` | 基址寄存器，可参与地址计算 |
| `CX` | `CH:CL` | 循环计数；`CL` 可提供移位次数 |
| `DX` | `DH:DL` | 乘除法高半部分、端口号、DOS 参数 |
| `SP` | — | 栈顶偏移，配合 `SS` |
| `BP` | — | 栈帧基址；寻址默认使用 `SS` |
| `SI` | — | 源变址；字符串源为 `DS:SI` |
| `DI` | — | 目的变址；字符串目标为 `ES:DI` |
| `CS`、`DS`、`SS`、`ES` | — | 代码、数据、栈、附加段 |
| `IP` | — | 下一条指令在代码段内的偏移 |

`AX`、`BX`、`CX`、`DX` 都是 16 位寄存器。执行 `MOV AX, 1234H` 后，`AH=12H`、`AL=34H`。8 位和 16 位操作数不能直接混用，例如 `MOV AX, BL` 非法；需要时应显式扩展。

### 2. 重要标志位

| 标志 | 含义 | 用途 |
| --- | --- | --- |
| `CF` | 无符号进位或借位 | `ADC`、`SBB`、`JC`、无符号比较 |
| `ZF` | 结果为 0 | `JE/JZ`、`JNE/JNZ` |
| `SF` | 结果最高位 | 有符号结果的符号线索 |
| `OF` | 有符号溢出 | `JG/JL` 等有符号转移 |
| `PF` | 低字节中 1 的数量为偶数 | `JP/JNP` |
| `AF` | 低半字节进位 | BCD 调整相关 |
| `DF` | 字符串方向 | `CLD` 递增、`STD` 递减 |
| `IF` | 可屏蔽中断允许 | `STI`、`CLI` |

`CF` 面向无符号解释，`OF` 面向补码有符号解释。寄存器中只有位模式，不会自动带上“有符号”标签；条件转移选错才是常见错误。

### 3. 不要把寄存器职责误认为硬件限制

`AX` 被称为累加器，`BX` 被称为基址寄存器，`CX` 被称为计数寄存器，这些名称首先是历史用法和部分指令的隐含约定，并不意味着它们在所有指令中只能做一种事。`MOV AX, BX`、`ADD BX, CX` 都合法。真正的限制来自具体指令：例如 8 位 `MUL` 固定以 `AL` 为被乘数并把结果放入 `AX`；`LOOP` 固定使用 `CX`；DOS 02H 固定从 `DL` 取字符。

这一区别能避免一个常见误解：寄存器的“常见职责”有助于读程序，**隐含操作数**才是不能随意改动的机器规则。写代码前先问“这条指令规定了什么”，不要只凭寄存器名称猜测。

`BP` 是另一个容易出错的寄存器。它参与地址计算时默认段为 `SS`：

```asm
MOV AX, [BP+4]     ; 默认读 SS:[BP+4]
MOV AX, [BX+4]     ; 默认读 DS:[BX+4]
```

这让 `BP` 很适合访问栈上的参数。若要用 `BP` 访问数据段中的数组，需要显式写段超越，例如 `MOV AX, DS:[BP+4]`。

### 4. FLAGS 必须结合一次具体运算理解

以 8 位加法为例：

```text
FFH + 01H = 100H
写回 AL 的结果为 00H，CF=1，ZF=1
```

按无符号解释，255 加 1 超过了 8 位最大值 255，所以 `CF=1`。但按有符号补码解释，`FFH` 是 -1，`01H` 是 1，结果 0 完全可表示，所以 `OF=0`。

再看：

```text
7FH + 01H = 80H
```

这里没有第 9 位进位，所以 `CF=0`；但 8 位有符号数的最大值是 127，127 加 1 应为 128，已经无法用 8 位补码表示，故 `OF=1`。结果 `80H` 在补码解释下是 -128，`SF=1`。这说明：**CF 不等于 OF，SF 也不能单独判断有符号比较结果。**

减法同样要分解释。`CMP A,B` 与 `SUB A,B` 使用相同的比较性标志规则，只是 `CMP` 不写回差值。对无符号数，`A<B` 时减法需要借位，`CF=1`；对有符号数，是否越界由 `OF` 表示。条件转移正是把这些标志组合成“相等、大于、小于”等结论。

## 三、显式段、伪指令与最小程序

伪指令由汇编器处理，用来定义数据、段和符号，不是 CPU 在运行时执行的指令。以下是 DOS EXE 程序的显式分段骨架：

```asm
STACK SEGMENT PARA STACK 'STACK'
    DW 128 DUP(?)
STACK ENDS

DATA SEGMENT
    MESSAGE DB 'Hello, 8086!', 0DH, 0AH, '$'
DATA ENDS

CODE SEGMENT
    ASSUME CS:CODE, DS:DATA, SS:STACK

START:
    MOV AX, SEG DATA
    MOV DS, AX

    MOV DX, OFFSET MESSAGE
    MOV AH, 09H
    INT 21H

    MOV AX, 4C00H
    INT 21H

CODE ENDS
END START
```

`ASSUME CS:CODE, DS:DATA` 只告诉汇编器“应当如何解释段寄存器”，不会在运行时修改任何寄存器。访问数据前仍必须执行：

```asm
MOV AX, SEG DATA
MOV DS, AX
```

8086 不允许 `MOV DS, 立即数`，所以段值先进入通用寄存器。常规 DOS EXE 的栈由装载器依照 `STACK` 类段建立；不要在不了解中断窗口和栈状态时随意改写 `SS`。

### 1. 常用伪指令和汇编器运算符

| 写法 | 作用 | 示例 |
| --- | --- | --- |
| `name SEGMENT ... name ENDS` | 定义段 | `DATA SEGMENT` |
| `ASSUME` | 声明段寄存器假设 | `ASSUME DS:DATA` |
| `END label` | 源文件结束并指定入口 | `END START` |
| `DB/DW/DD` | 定义字节、字、双字 | `COUNT DW 100` |
| `DUP` | 重复初始化或保留空间 | `BUF DB 80 DUP(?)` |
| `EQU` | 定义不可改的汇编期常量 | `CR EQU 0DH` |
| `=` | 定义可重新赋值的汇编期符号 | `N = 1` |
| `OFFSET` | 取得段内偏移 | `MOV DX, OFFSET MESSAGE` |
| `SEG` | 取得段地址 | `MOV AX, SEG DATA` |
| `PTR` | 指定内存操作数大小 | `MOV BYTE PTR [SI], 0` |
| `LABEL` | 为当前位置定义类型别名 | `NEXT LABEL WORD` |
| `PROC/ENDP` | 标记过程边界 | `P PROC ... P ENDP` |
| `PUBLIC/EXTRN` | 多模块导出/外部声明 | `EXTRN F:FAR` |
| `ORG` | 调整汇编期位置计数器 | COM 程序常用 `ORG 100H` |

`DB`、`DW`、`DD` 分别定义 8、16、32 位数据。8086 采用小端序：`DW 1234H` 的低地址字节是 `34H`，高地址字节是 `12H`。`?` 只保留空间；`$` 是当前汇编位置：

```asm
MESSAGE DB 'ABC'
LENGTH  EQU $ - MESSAGE      ; LENGTH = 3
```

`OFFSET` 是段内偏移，不是变量内容；`SEG` 是段值。`LEA SI, ARRAY` 装入有效地址，在简单直接寻址时可视为 `MOV SI, OFFSET ARRAY`。

### 2. 把伪指令按“定义什么”来掌握

`DB`、`DW`、`DD` 的职责是把初值或保留空间写入目标文件。它们不是变量类型系统：`DW` 只是告诉汇编器分配两个连续字节，程序员仍要决定读它时使用有符号还是无符号指令。`DUP` 只在汇编阶段展开，因此：

```asm
ARRAY  DW 10 DUP(0)     ; 十个初值为 0 的字
BUFFER DB 100 DUP(?)    ; 保留一百个字节，初值未指定
```

`EQU` 是文本级常量定义，适合功能号、缓冲区大小和控制字符；它不会占用内存。`=` 与 `EQU` 的差异在于前者可在汇编过程中再次赋值，但两者都不是运行时变量。

```asm
CR      EQU 0DH
LF      EQU 0AH
MAXLEN  EQU 80
```

`OFFSET`、`SEG`、`PTR` 解决的分别是“偏移是多少”“段是多少”“这块内存按多大宽度解释”。它们经常同时出现，但不能相互替代：

```asm
MOV AX, SEG DATA              ; AX = DATA 的段值
MOV SI, OFFSET ARRAY          ; SI = ARRAY 的段内偏移
MOV BYTE PTR [SI], 0          ; 指定写一个字节
MOV WORD PTR [SI], 0          ; 指定写一个字
```

`ORG` 改变的是汇编时的位置计数器，最典型的用途是 COM 程序以偏移 `0100H` 为入口。它不是“申请一块内存”，也不是运行时跳转。`PUBLIC` 与 `EXTRN` 则服务于多个目标模块的链接：前者导出名称，后者声明名称由其他模块提供。单源文件的作业程序无需它们，但理解它们能区分“汇编完成”和“链接成可执行文件”这两个阶段。

## 四、操作数规则与寻址方式

多数双操作数指令的格式是：

```text
指令  目的操作数, 源操作数
```

例如 `ADD AX, BX` 表示 `AX ← AX + BX`；目的操作数通常既是输入也是输出。需要记住四条规则：

- 普通 `MOV`、`ADD` 等不能让两个操作数同时为内存，`MOV [DI], [SI]` 非法，必须经过寄存器。
- 两个操作数宽度必须一致；内存立即数宽度不明确时使用 `BYTE PTR` 或 `WORD PTR`。
- `CS` 不能通过 `MOV` 直接写入；切换代码段需要远转移、远调用或中断返回。
- 有 `BP` 的地址表达式默认取 `SS`，其他常见数据地址默认取 `DS`；可用 `ES:[DI]` 进行段超越。

| 方式 | 格式 | 示例 | 默认段 |
| --- | --- | --- | --- |
| 立即寻址 | `op reg, imm` | `MOV AX, 1234H` | 无 |
| 寄存器寻址 | `op reg, reg` | `MOV AX, BX` | 无 |
| 直接寻址 | `op reg, label` | `MOV AX, COUNT` | DS |
| 寄存器间接 | `[BX] [BP] [SI] [DI]` | `MOV AL, [SI]` | BP 为 SS，其余为 DS |
| 带位移 | `[BX+disp]`、`[SI+disp]` | `MOV AX, [BP+4]` | 由 BP 决定 |
| 基址加变址 | `[BX+SI]` 等 | `MOV AL, [BX+DI]` | 有 BP 则 SS |
| 加位移的组合 | `[BX+SI+disp]` | `MOV AX, [BP+DI+6]` | 有 BP 则 SS |

8086 合法的基址和变址组合只有：

```text
BX + SI    BX + DI    BP + SI    BP + DI
```

所以 `[SI+DI]`、`[BX+BP]` 都非法。跳转使用相对寻址，`JNZ LOOP_BODY` 的位移由汇编器根据标号计算。

### 1. 用同一数组看懂各种地址表达式

假设 `ARRAY` 的首偏移为 0100H，`BX=0100H`，`SI=0006H`。下面几种写法的含义不同：

```asm
MOV AL, ARRAY        ; 读 DS:0100H 的一个字节
MOV AL, [BX]         ; 读 DS:0100H 的一个字节
MOV AL, [BX+2]       ; 读 DS:0102H 的一个字节
MOV AL, [BX+SI]      ; 读 DS:0106H 的一个字节
MOV AL, [BX+SI+2]    ; 读 DS:0108H 的一个字节
```

变量名直接作为内存操作数时，汇编器把它翻译为该变量的偏移；加方括号则明确表示“把寄存器内容当作地址”。相反：

```asm
MOV SI, OFFSET ARRAY  ; SI 得到 0100H，不读取 ARRAY 的内容
MOV SI, ARRAY         ; SI 读取 ARRAY 开始处的一个字
```

这两句初学者很容易混淆。判断方法很简单：`OFFSET` 产生地址常量；没有 `OFFSET` 的变量名在 `MOV` 的源操作数位置通常表示内存内容。

### 2. 数组、结构和栈参数分别适合什么寻址

一维字节数组通常用 `SI` 或 `DI` 顺序扫描；一维字数组每步加 2。二维数组或记录数组可将 `BX/BP` 作为记录基址，将 `SI/DI` 作为行内偏移。例如结构体某字段位于记录开头后 6 字节：

```asm
MOV AX, [BX+SI+6]
```

这个写法只负责地址计算，不会自动乘以元素大小。若 `SI` 代表“第几个字元素”，程序员必须先将它换算成字节偏移。8086 没有后来的比例变址语法，不能写“`SI×2`”作为地址成分。

栈参数则常用 `BP`。过程建立栈帧后，`[BP]` 是保存的旧 `BP`，`[BP+2]` 通常是近调用的返回地址，后面才是调用者压入的参数。这里默认使用 `SS` 正好符合栈数据的位置。

## 五、数据传送、栈与字符串指令

| 指令格式 | 作用 |
| --- | --- |
| `MOV dest, src` | 传送数据，不修改标志位 |
| `XCHG op1, op2` | 交换寄存器或寄存器与内存 |
| `PUSH src` | `SP←SP-2`，写入 `SS:SP` |
| `POP dest` | 读 `SS:SP`，再 `SP←SP+2` |
| `LEA reg, mem` | 取得有效地址，不读取该地址的数据 |
| `LDS/LES reg, mem` | 从内存远指针装入偏移和 DS/ES |

`PUSH` 与 `POP` 在 8086 上处理一个字。`CALL` 将返回地址压栈，`RET` 将它弹回 `IP`；过程若要保护调用者寄存器，必须自行压栈和恢复。

字符串指令把 `SI`、`DI`、`CX` 作为隐含操作数：

| 指令 | 单次语义 |
| --- | --- |
| `MOVSB/MOVSW` | `ES:[DI] ← DS:[SI]` |
| `LODSB/LODSW` | `AL/AX ← DS:[SI]` |
| `STOSB/STOSW` | `ES:[DI] ← AL/AX` |
| `CMPSB/CMPSW` | 比较 `DS:[SI]` 和 `ES:[DI]` |
| `SCASB/SCASW` | 比较 `AL/AX` 和 `ES:[DI]` |

`CLD` 清除 `DF`，使地址递增；`STD` 置位 `DF`，使地址递减。`REP MOVSB` 会在 `CX` 次数内连续复制字节；`REPE`、`REPNE` 则可配合比较和扫描。正向处理字符串前应明确 `CLD`，否则先前代码遗留的 `DF` 可能让程序反向遍历内存。

### 1. 用栈帧理解 CALL、RET 与 BP

`CALL` 并不是“跳过去执行”这么简单。近调用会先把返回后的 `IP` 压入 `SS:SP`，再跳到目标标号；`RET` 从栈顶取回该偏移，继续执行调用点之后的指令。因此，只要子程序私自多 `POP` 一次或少 `POP` 一次，返回地址就可能被破坏。

一个典型的近过程框架如下：

```asm
ADD_TWO PROC
    PUSH BP
    MOV  BP, SP
    PUSH BX

    MOV  AX, [BP+4]    ; 第一个参数
    ADD  AX, [BP+6]    ; 第二个参数

    POP  BX
    POP  BP
    RET
ADD_TWO ENDP
```

调用者若按从右到左的顺序压入参数：

```asm
PUSH NUM2
PUSH NUM1
CALL ADD_TWO
ADD SP, 4
```

进入 `ADD_TWO` 后的栈从低地址到高地址可理解为“当前局部空间、保存的寄存器、旧 BP、返回地址、NUM1、NUM2”。上例没有分配局部变量，因此 `[BP+4]` 和 `[BP+6]` 分别读取两个参数。参数的压栈顺序、近/远调用和由谁回收参数必须由调用约定统一；不要机械地把偏移量照搬到另一种过程类型。

### 2. 字符串指令为何需要 DS:SI、ES:DI 与 DF

普通 `MOV` 每次都要明确写出地址；字符串指令把源地址固定为 `DS:SI`、目标地址固定为 `ES:DI`，并在每次操作后自动移动地址。下面复制 16 个字节：

```asm
MOV AX, SEG DEST
MOV ES, AX
LEA SI, SOURCE
LEA DI, DEST
MOV CX, 16
CLD
REP MOVSB
```

`REP MOVSB` 等价于循环执行 16 次 `MOVSB`：复制 `DS:[SI]` 到 `ES:[DI]`，在 `DF=0` 时 `SI` 与 `DI` 各加 1，并让 `CX` 减 1。若源与目的区重叠，方向选择会影响结果；类似 `memmove` 的“从后向前复制”需要 `STD` 并让指针先指向末尾。字符串指令不会替你检查缓冲区边界，也不会自动设置 `ES`，这两件事必须由程序准备。

## 六、算术、逻辑和位操作

### 1. 常用算术指令

| 指令格式 | 结果/用途 | CF |
| --- | --- | --- |
| `ADD dest, src` | `dest ← dest + src` | 更新 |
| `ADC dest, src` | 加上 `CF`，用于多字加法 | 更新 |
| `SUB dest, src` | `dest ← dest - src` | 更新 |
| `SBB dest, src` | 再减 `CF`，用于多字减法 | 更新 |
| `INC/DEC dest` | 加一/减一 | **不更新** |
| `CMP op1, op2` | 按 `op1-op2` 设置标志，不保存结果 | 更新 |
| `NEG dest` | `dest ← 0-dest` | 更新 |
| `CBW` / `CWD` | `AL→AX`、`AX→DX:AX` 的符号扩展 | — |

双字无符号加法的标准模式：

```asm
ADD AX, BX        ; 低字
ADC DX, CX        ; 高字并吸收低字进位
```

不能用 `INC` 代替需要传递进位的 `ADD reg, 1`，因为 `INC` 不修改 `CF`。

### 2. 乘法和除法的隐含操作数

| 指令 | 被乘数/被除数 | 结果 |
| --- | --- | --- |
| `MUL r/m8` | `AL` | `AX = AL × operand` |
| `MUL r/m16` | `AX` | `DX:AX = AX × operand` |
| `IMUL r/m8/r/m16` | 与 `MUL` 相同 | 按有符号数解释 |
| `DIV r/m8` | `AX` | `AL=商`，`AH=余数` |
| `DIV r/m16` | `DX:AX` | `AX=商`，`DX=余数` |
| `IDIV` | 与 `DIV` 相同 | 按有符号数解释 |

若无符号 16 位被除数只在 `AX` 中，除法前应清零 `DX`：

```asm
XOR DX, DX
DIV BX
```

有符号除法通常先执行 `CWD`。除数为零或商装不下会触发除法错误中断。

### 3. 逻辑与移位

| 指令 | 用途 |
| --- | --- |
| `AND` | 掩码、清零某些位 |
| `OR` | 置位、组合位 |
| `XOR` | 异或；`XOR AX, AX` 常用于清零 |
| `NOT` | 逐位取反 |
| `TEST` | 与运算但不保存结果，只更新标志 |
| `SHL/SAL` | 左移；通常对应乘 2 的位级操作 |
| `SHR` | 逻辑右移，高位补 0 |
| `SAR` | 算术右移，高位复制符号位 |
| `ROL/ROR/RCL/RCR` | 循环移位，后两者经过 `CF` |

8086 的移位计数只能是 `1` 或 `CL`，不能写 `SHR AL, 4`。判断奇偶数的典型代码如下：

```asm
TEST AL, 01H
JZ EVEN
; 最低位为 1，AL 是奇数
```

如果用 `LOOP` 管理 `CX`，不要为了移位而改写 `CL`，否则循环次数也被改掉。

### 4. ADD、ADC、SUB、SBB 如何串成多精度运算

8086 一次只能直接加减一个字或一个字节。若一个无符号整数占两个字，必须从低字开始：低字产生的进位通过 `CF` 传给高字。不能反过来，因为高字加法无法预知低字会不会溢出。

```asm
; DX:AX = DX:AX + CX:BX
ADD AX, BX
ADC DX, CX
```

减法完全平行：

```asm
; DX:AX = DX:AX - CX:BX
SUB AX, BX
SBB DX, CX
```

`SBB` 的含义是“目的 - 源 - CF”。在无符号减法中，`CF=1` 表示前一个低字需要借位，因此高字还要再减 1。`NEG` 计算补码相反数；`INC` 和 `DEC` 只适合单独加减一，因为它们故意保留 `CF`，以便不破坏外层的进位链。

### 5. 乘除法的寄存器约定不能省略

`MUL` 和 `DIV` 不是普通的双操作数格式。它们把一部分寄存器固定为隐含输入或输出，因此调用前要先安排数据，调用后要立即保存仍需要的结果。

例如计算 200 × 3：

```asm
MOV AL, 200
MOV BL, 3
MUL BL              ; AX = 600 = 0258H
```

8 位无符号乘法的完整结果可能有 16 位，所以必须放在 `AX`。16 位 `MUL BX` 的完整结果可能有 32 位，于是低字放 `AX`、高字放 `DX`。若把 `DX` 当作普通临时寄存器而忘记它会被乘法覆盖，错误往往很隐蔽。

除法前更要明确被除数宽度。`DIV BL` 用整个 `AX` 除以 `BL`；`DIV BX` 用 `DX:AX` 除以 `BX`。例如要计算无符号 `AX / BX`，若 `AX` 只是 16 位被除数，就必须先令 `DX=0`。有符号除法则不能清零高字，而应使用 `CBW` 或 `CWD` 把符号位扩展过去。

### 6. 位操作不是“算术的简写”

`AND`、`OR`、`XOR`、`TEST` 按每一位独立运算，适合处理标志位、设备寄存器、BCD 半字节和掩码。`TEST AL,01H` 只为判断最低位而存在：它保留 `AL`，只更新 FLAGS。若改写为 `AND AL,01H`，数值本身被破坏，除非你本来就只需要判断结果。

移位也要区分数值解释。`SHL` 左移会把低位补 0，常可用于无符号乘 2；`SHR` 高位补 0，适合无符号除 2；`SAR` 复制原符号位，才接近有符号除 2。对于负奇数，算术右移向负无穷方向舍入，未必等于高级语言规定的“向零截断”除法，不能不加思考地替代 `IDIV`。

## 七、转移、条件判断与过程

`CMP A, B` 执行逻辑上的 `A-B`，只设置标志。后续跳转必须按数据的解释选择：

| 比较关系 | 无符号跳转 | 有符号跳转 |
| --- | --- | --- |
| 相等/不等 | `JE/JZ`、`JNE/JNZ` | 相同 |
| 大于/大于等于 | `JA`、`JAE` | `JG`、`JGE` |
| 小于/小于等于 | `JB`、`JBE` | `JL`、`JLE` |

`FFH` 作为无符号数是 255，作为 8 位补码数是 -1；比较它与 `01H` 时，无符号应跳 `JA`，有符号应跳 `JL`。

| 格式 | 功能 |
| --- | --- |
| `JMP label` | 无条件跳转 |
| `Jcc label` | 条件满足时跳转 |
| `JC/JNC`、`JO/JNO`、`JS/JNS` | 直接测试 CF、OF、SF |
| `LOOP label` | `CX←CX-1`，非零则跳转 |
| `JCXZ label` | `CX=0` 时跳转 |
| `CALL label` / `RET` | 过程调用与返回 |
| `INT n` / `IRET` | 软件中断与中断返回 |

`LOOP` 不检查 `ZF`，只检查 `CX`。固定次数循环很合适；复杂条件循环通常写成 `DEC CX` 加 `JNZ` 更清晰。

### 1. 把高级语言条件翻译成标号和跳转

汇编没有内建的 `if`、`while` 或 `for`；它们都是“比较/测试 + 条件跳转 + 标号”的组织方式。例如无符号代码：

```text
if (ax > bx) {
    ax = bx;
}
```

可写成：

```asm
CMP AX, BX
JBE KEEP_AX
MOV AX, BX
KEEP_AX:
```

条件跳转的目标应当表达“条件为真时跳去哪里”。这段程序选择了“若不需要更新则跳过赋值”，因此使用 `JBE`。也可以反转条件，先跳到赋值块再用 `JMP` 越过它；两种写法都正确，关键是每个路径都能到达同一个后继位置。

一个显式循环通常更容易调试：

```asm
MOV CX, COUNT
JCXZ DONE

LOOP_BODY:
    ; 循环体
    DEC CX
    JNZ LOOP_BODY
DONE:
```

当 `COUNT=0` 时，若直接从 `LOOP_BODY` 进入，`DEC CX` 会使 `CX` 从 0000H 变为 FFFFH，造成极长循环。因此未知次数的循环在入口处检查 `CX` 是严谨的做法。

## 八、字符、ASCII 与组合 BCD

ASCII 数字连续编码：

```text
'0' = 30H，'1' = 31H，…，'9' = 39H
```

合法数值 `0..9` 转 ASCII：

```asm
ADD AL, '0'       ; 或 OR AL, 30H
```

ASCII 数字转数值：

```asm
SUB AL, '0'
```

组合 BCD 的一个字节保存两个十进制数字；例如 `45H` 表示 4 和 5，而不是二进制数 69。转换低半字节：

```asm
AND AL, 0FH
OR  AL, 30H
```

高半字节需先右移四位。此过程假定半字节是合法 BCD，即值在 0 到 9；`AH` 到 `FH` 应视为非法输入并另行校验。

### 1. BCD 转换要先明确输出顺序

组合 BCD 的“组合”指两个十进制数字压在一个字节的两个半字节中：

```text
字节 45H = 0100 0101B
高半字节 0100B -> 十进制数字 4
低半字节 0101B -> 十进制数字 5
```

它不是二进制整数 45，也不是字符 `'E'`。将低半字节与 `0FH` 相与后得到 0 到 9 的数值，再与 `30H` 组合即可获得 ASCII。高半字节必须先屏蔽低位，再移到低四位。若题目要求高位数字的 ASCII 放到更高地址，处理次序可先低后高：

```asm
MOV AL, [SI]
MOV AH, AL

AND AL, 0FH
OR  AL, 30H
MOV [DI], AL

MOV AL, AH
AND AL, 0F0H
SHR AL, 1
SHR AL, 1
SHR AL, 1
SHR AL, 1
OR  AL, 30H
MOV [DI+1], AL
```

输入 `12H` 的输出是低地址 `'2'`、高地址 `'1'`。这个顺序与人书写十进制数的顺序相反，却符合“高位放高地址”的题设；程序设计时必须服从内存布局要求，而不是凭直觉交换两次存储。

## 九、DOS INT 21H：01H、02H、09H、0AH、4CH

`INT 21H` 是 DOS 的系统服务入口，不是 CPU 的普通输出指令。通常 `AH` 放功能号，其他寄存器放参数；它只能在 DOS 或兼容环境中使用。

| AH | 功能 | 调用前 | 返回/注意 |
| --- | --- | --- | --- |
| `01H` | 读一个字符并回显 | `AH=01H` | `AL` 返回 ASCII，阻塞等待 |
| `02H` | 输出一个字符 | `DL=字符` | 可输出 `$`、回车、换行 |
| `09H` | 输出字符串 | `DS:DX` 指向字符串 | 输出到 `$` 为止，`$` 不显示 |
| `0AH` | 缓冲区行输入 | `DS:DX` 指向输入缓冲区 | 回车结束，缓冲区格式固定 |
| `4CH` | 结束程序 | `AL=返回码` | 返回 DOS |

### 1. 01H 与 02H

```asm
MOV AH, 01H
INT 21H            ; AL = 输入字符，且已经回显

MOV DL, AL
MOV AH, 02H
INT 21H            ; 输出一个字符
```

换行必须输出回车和换行两个控制字符：

```asm
MOV AH, 02H
MOV DL, 0DH
INT 21H
MOV DL, 0AH
INT 21H
```

### 2. 09H 字符串输出

```asm
PROMPT DB 'Input: $'

MOV DX, OFFSET PROMPT
MOV AH, 09H
INT 21H
```

09H 按 `$` 找结束，不读取显式长度。字符串必须有 `$` 结尾；要显示单个 `$`，使用 02H。

### 3. 0AH 缓冲输入

```asm
INPUT_BUF DB 20           ; 最大可接收字符数
          DB ?            ; 实际读入字符数，不含回车
          DB 20 DUP(?)    ; 字符区域
```

```asm
MOV DX, OFFSET INPUT_BUF
MOV AH, 0AH
INT 21H
```

字符从 `INPUT_BUF+2` 开始，第二个字节保存长度。若要用 09H 回显，先在输入末尾写入 `$`：

```asm
XOR BX, BX
MOV BL, INPUT_BUF+1
MOV BYTE PTR INPUT_BUF[BX+2], '$'

MOV DX, OFFSET INPUT_BUF+2
MOV AH, 09H
INT 21H
```

### 4. 4CH 退出

```asm
MOV AX, 4C00H      ; AH=4CH，AL=00H
INT 21H
```

### 5. 调用 DOS 前后的寄存器语义

01H 是带回显的阻塞输入：程序停在 `INT 21H`，直到键盘给出一个字符；字符的 ASCII 码返回在 `AL`。它适合菜单和单字符确认，不适合读取整行。02H 只从 `DL` 输出一个字符，因此 `$`、回车 `0DH` 和换行 `0AH` 都能输出；09H 则要求 `DS:DX` 指向以 `$` 结尾的文本，它不认识长度，也不输出终止符本身。

0AH 的缓冲区不是普通 C 字符串，而是一个有控制头的 DOS 数据结构：

```text
偏移 +0：缓冲区允许的最大字节数
偏移 +1：本次实际输入的字符数，不含回车
偏移 +2：第一个输入字符
...
输入结束时：字符区尾部还会保留回车 0DH
```

因为 DOS 09H 以 `$` 结束而 0AH 不自动写 `$`，将同一缓冲区交给 09H 前必须利用“实际长度”定位尾部，再写入 `$`。若希望最多允许 N 个可见字符，缓冲区的实际保留空间还必须考虑最终的回车以及后续可能补写的 `$`；不要只按“看起来有 N 个字符位”定义。

4CH 不只是停止 CPU；它让 DOS 按正常程序结束路径回收资源并将 `AL` 返回给父进程。因此常规 DOS 程序应使用它结束，而不是跳进未知地址或无限循环。

## 十、三个典型题型

### 1. 10 个 16 位无符号数求最小值

```asm
    LEA SI, ARRAY
    MOV AX, [SI]
    ADD SI, 2
    MOV CX, 9

FIND_MIN:
    CMP AX, [SI]
    JBE KEEP_MIN       ; 无符号 AX <= [SI]
    MOV AX, [SI]

KEEP_MIN:
    ADD SI, 2          ; DW 元素占两个字节
    LOOP FIND_MIN

    MOV MIN, AX
```

题目指定无符号数，必须用 `JBE`，不是 `JLE`。

### 2. 100 个字节中统计奇数

```asm
    LEA SI, DAT
    XOR BX, BX         ; BL 计数
    MOV CX, 100

COUNT_ODD:
    MOV AL, [SI]
    TEST AL, 01H
    JZ NOT_ODD
    INC BL

NOT_ODD:
    INC SI
    LOOP COUNT_ODD

    MOV RESULT, BL
```

`TEST` 不会改变 `AL`，而 100 以内的计数放在 `BL` 即可。

### 3. 30 个组合 BCD 字节转 ASCII

要求“高位 BCD 转换后的 ASCII 放在更高地址”，所以 `12H` 必须输出 `'2'`、`'1'`，也就是低地址为 `32H`，高地址为 `31H`。

```asm
    LEA SI, BUF
    LEA DI, BUF2
    MOV CX, 30

CONVERT:
    MOV AL, [SI]
    MOV BL, AL

    ; 低半字节 -> 低地址
    AND AL, 0FH
    OR  AL, 30H
    MOV BYTE PTR [DI], AL

    ; 高半字节 -> 高地址
    MOV AL, BL
    AND AL, 0F0H
    SHR AL, 1
    SHR AL, 1
    SHR AL, 1
    SHR AL, 1
    OR  AL, 30H
    MOV BYTE PTR [DI+1], AL

    INC SI
    ADD DI, 2
    LOOP CONVERT
```

### 4. 可独立汇编的完整程序

前面的片段突出算法，而作业提交通常还需要数据段、代码段、`DS` 初始化和 DOS 返回。以下三个源文件应分别汇编、链接和运行；它们不在屏幕显示结果，而是把答案写入题目指定的内存单元。

#### 最小值：10 个 16 位无符号数

```asm
DATA SEGMENT
ARRAY DW 0034H, 0120H, 0007H, 00A5H, 0021H
      DW 0003H, 0100H, 0048H, 0009H, 0020H
MIN   DW ?
DATA ENDS

CODE SEGMENT
ASSUME CS:CODE, DS:DATA

START:
    MOV AX, SEG DATA
    MOV DS, AX

    LEA SI, ARRAY
    MOV AX, [SI]
    ADD SI, 2
    MOV CX, 9

FIND_MIN:
    CMP AX, [SI]
    JBE KEEP_MIN
    MOV AX, [SI]

KEEP_MIN:
    ADD SI, 2
    LOOP FIND_MIN

    MOV MIN, AX
    MOV AX, 4C00H
    INT 21H

CODE ENDS
END START
```

#### 奇数计数：100 个 8 位无符号数

```asm
DATA SEGMENT
DAT    DB 100 DUP(?)
RESULT DB ?
DATA ENDS

CODE SEGMENT
ASSUME CS:CODE, DS:DATA

START:
    MOV AX, SEG DATA
    MOV DS, AX

    LEA SI, DAT
    XOR BX, BX
    MOV CX, 100

COUNT_ODD:
    MOV AL, [SI]
    TEST AL, 01H
    JZ NOT_ODD
    INC BL

NOT_ODD:
    INC SI
    LOOP COUNT_ODD

    MOV RESULT, BL
    MOV AX, 4C00H
    INT 21H

CODE ENDS
END START
```

本题最大计数是 100，故 `RESULT DB ?` 足够。若统计对象可能超过 255 个，计数器应改为字，例如 `XOR BX,BX` 后用 `INC BX`，结果写入 `RESULT DW ?`。

#### BCD 转 ASCII：30 个组合 BCD 字节

```asm
DATA SEGMENT
BUF  DB 30 DUP(?)
BUF2 DB 60 DUP(?)
DATA ENDS

CODE SEGMENT
ASSUME CS:CODE, DS:DATA

START:
    MOV AX, SEG DATA
    MOV DS, AX

    LEA SI, BUF
    LEA DI, BUF2
    MOV CX, 30

CONVERT:
    MOV AL, [SI]
    MOV BL, AL

    AND AL, 0FH
    OR  AL, 30H
    MOV BYTE PTR [DI], AL

    MOV AL, BL
    AND AL, 0F0H
    SHR AL, 1
    SHR AL, 1
    SHR AL, 1
    SHR AL, 1
    OR  AL, 30H
    MOV BYTE PTR [DI+1], AL

    INC SI
    ADD DI, 2
    LOOP CONVERT

    MOV AX, 4C00H
    INT 21H

CODE ENDS
END START
```

输入区是 30 字节，输出区必须是 60 字节，因为每一个组合 BCD 字节都会拆成两个 ASCII 字节。若 `BUF` 与 `BUF2` 指向重叠区域，还必须重新设计遍历方向；本题把它们定义为独立缓冲区，故可以从低地址向高地址顺序转换。

## 十一、写完后按这份清单复核

- `DS` 是否真的初始化，而非只写了 `ASSUME`？
- 内存操作默认走 `DS` 还是 `SS`？地址式中出现 `BP` 就默认 `SS`。
- 数据定义是 `DB` 还是 `DW`？地址步长应为 1 还是 2？
- 比较对象是有符号还是无符号？是否选对 `JG/JL` 或 `JA/JB`？
- `CMP`、`TEST` 只更新标志；是否误以为它们保存了结果？
- `INC/DEC` 不更新 `CF`；多精度运算是否应使用 `ADC/SBB`？
- `MUL/DIV` 是否考虑 `AX`、`DX:AX` 等隐含操作数？
- `LOOP` 依赖 `CX`；循环体是否误改 `CL`？
- 09H 字符串是否有 `$`？0AH 缓冲区是否按“最大长度、实际长度、字符区”定义？

掌握这套检查顺序后，8086 代码就不再是难以记忆的缩写：段寄存器决定“从哪个区域取”，寻址方式决定“具体在哪”，指令修改寄存器、内存或标志位，转移指令决定控制流。
