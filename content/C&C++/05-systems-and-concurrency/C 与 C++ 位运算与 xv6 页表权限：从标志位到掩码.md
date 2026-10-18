+++
date = '2026-08-25T20:10:00+08:00'
draft = false
title = 'C 与 C++ 位运算与 xv6 页表权限：从标志位到掩码'
+++

读 C 系统代码时，位运算几乎绕不开。

在 xv6 里，你会看到类似代码：

```c
#define PTE_V (1L << 0)
#define PTE_R (1L << 1)
#define PTE_W (1L << 2)
#define PTE_X (1L << 3)
#define PTE_U (1L << 4)

flags |= PTE_W;
flags &= ~PTE_U;

if ((*pte & PTE_V) == 0) {
    return 0;
}
```

如果只从表面看，`|`、`&`、`~`、`<<` 这些符号确实显得冷淡。它们不解释自己，也不会给初学者一点情绪价值。

但位运算并不神秘。它的核心只有一句话：

```text
把一个整数的每一位当作独立开关，用掩码进行设置、清除、检查和组合。
```

操作系统、文件格式、网络协议、硬件寄存器和权限系统喜欢位运算，是因为它紧凑、稳定、低开销，并且和机器表示方式非常接近。

## 一、整数也是一串 bit

C 和 C++ 里的整数可以从两个角度看。

平时我们把它看成数值：

```c
unsigned x = 5;
```

`5` 是一个数。

但从二进制角度看，它也是一串 bit：

```text
0101
```

如果用 4 位演示：

| 十进制 | 二进制 |
| --- | --- |
| `0` | `0000` |
| `1` | `0001` |
| `2` | `0010` |
| `3` | `0011` |
| `4` | `0100` |
| `5` | `0101` |
| `8` | `1000` |

真实的 `unsigned int` 通常不止 4 位。这里用 4 位，只是为了让每一位都看得清楚。

位运算就是直接操作这些 bit。

## 二、常用位运算符

常用运算符如下：

| 运算符 | 名称 | 含义 |
| --- | --- | --- |
| `&` | 按位与 | 两位都为 1，结果才为 1 |
| `|` | 按位或 | 两位至少一个为 1，结果就是 1 |
| `^` | 按位异或 | 两位不同，结果为 1 |
| `~` | 按位取反 | 0 变 1，1 变 0 |
| `<<` | 左移 | 二进制位整体向左移动 |
| `>>` | 右移 | 二进制位整体向右移动 |

先看 4 位例子：

```text
  0101
& 0011
= 0001

  0101
| 0011
= 0111

  0101
^ 0011
= 0110

~ 0101
= 1010
```

`&` 像筛子，用来选中某些位。

`|` 像开关合并，用来打开某些位。

`~` 用来制造“除了这些位之外”的掩码。

`<<` 常用来构造某一个 bit。

## 三、用左移构造标志位

如果要让每个标志占一个独立 bit，可以这样写：

```c
#define FLAG_A (1U << 0)
#define FLAG_B (1U << 1)
#define FLAG_C (1U << 2)
```

展开后大致是：

```text
FLAG_A = 0001
FLAG_B = 0010
FLAG_C = 0100
```

`1U << 0` 表示把 `1` 放在第 0 位。

`1U << 1` 表示把 `1` 放在第 1 位。

`1U << 2` 表示把 `1` 放在第 2 位。

这样每个宏都占据一个不同的位置。

在 xv6 中，页表权限位常见写法类似：

```c
#define PTE_V (1L << 0)
#define PTE_R (1L << 1)
#define PTE_W (1L << 2)
#define PTE_X (1L << 3)
#define PTE_U (1L << 4)
```

它们分别表示页表项里的不同 bit。

| 宏 | 含义 |
| --- | --- |
| `PTE_V` | valid，有效 |
| `PTE_R` | readable，可读 |
| `PTE_W` | writable，可写 |
| `PTE_X` | executable，可执行 |
| `PTE_U` | user，用户态可访问 |

所以：

```c
PTE_V | PTE_R | PTE_W
```

可以理解成：

```text
有效 + 可读 + 可写。
```

## 四、按位或：设置某个标志位

设置标志位通常用 `|=`：

```c
flags |= FLAG_A;
```

它等价于：

```c
flags = flags | FLAG_A;
```

如果原来是：

```text
flags  = 0000
FLAG_A = 0001
```

那么：

```text
0000 | 0001 = 0001
```

再设置 `FLAG_C`：

```c
flags |= FLAG_C;
```

结果：

```text
flags  = 0001
FLAG_C = 0100
result = 0101
```

`FLAG_A` 和 `FLAG_C` 都被打开了。

注意不要写成：

```c
flags = FLAG_C;
```

这会把原来的其他标志全部覆盖掉。

在页表代码里：

```c
*pte |= PTE_W;
```

意思是：

```text
给这个页表项增加写权限，同时保留其他权限位。
```

如果写成：

```c
*pte = PTE_W;
```

那就不是“增加写权限”，而是把整个页表项改成只剩 `PTE_W`。原来的有效位、读权限、地址部分都可能被破坏。底层代码对这种错误通常没有耐心，当然它也没有义务有。

## 五、按位与：检查某个标志位

检查标志位通常用 `&`：

```c
if (flags & FLAG_A) {
    /* FLAG_A is set */
}
```

如果：

```text
flags  = 0101
FLAG_A = 0001
```

那么：

```text
0101 & 0001 = 0001
```

结果非零，说明 `FLAG_A` 存在。

如果检查 `FLAG_B`：

```text
flags  = 0101
FLAG_B = 0010
result = 0000
```

结果为 0，说明 `FLAG_B` 不存在。

更明确的写法是：

```c
if ((flags & FLAG_A) != 0) {
    /* FLAG_A is set */
}
```

这对初学者更友好，也能减少优先级误读。

在 xv6 页表代码里：

```c
if ((*pte & PTE_V) == 0) {
    return 0;
}
```

可以翻译成：

```text
如果页表项没有有效位，就返回失败。
```

## 六、取反再按位与：清除某个标志位

清除标志位通常用：

```c
flags &= ~FLAG_A;
```

它等价于：

```c
flags = flags & ~FLAG_A;
```

如果只看 4 位：

```text
FLAG_A  = 0001
~FLAG_A = 1110
flags   = 0101
result  = 0100
```

`FLAG_A` 那一位被清掉，其他位保持不变。

所以：

```c
flags &= ~FLAG_A;
```

意思是：

```text
关闭 FLAG_A，保留其他标志位。
```

在页表代码里：

```c
*pte &= ~PTE_U;
```

可以翻译成：

```text
清除用户态可访问权限，其他位保持不变。
```

不要写成：

```c
flags &= FLAG_A;
```

这不是清除 `FLAG_A`，而是只保留 `FLAG_A` 这一位，其他位全部清掉。

## 七、异或：翻转某个标志位

异或 `^` 可以翻转 bit。

```c
flags ^= FLAG_A;
```

如果 `FLAG_A` 原来是 1，异或后变成 0。

如果 `FLAG_A` 原来是 0，异或后变成 1。

示意：

```text
1 ^ 1 = 0
0 ^ 1 = 1
```

所以异或常用于“切换状态”：

```c
flags ^= FLAG_A;
```

但在权限代码里，异或要谨慎使用。

权限通常需要明确设置或清除：

```c
flags |= PERM_WRITE;
flags &= ~PERM_WRITE;
```

而不是：

```c
flags ^= PERM_WRITE;
```

因为“原来有就去掉，原来没有就加上”这种语义太暧昧。权限检查里暧昧不是一种美德。

## 八、标志位的增删查改

可以把标志位操作记成四个动作：

| 操作 | 写法 | 含义 |
| --- | --- | --- |
| 设置某位 | `flags |= FLAG_A` | 打开 `FLAG_A` |
| 清除某位 | `flags &= ~FLAG_A` | 关闭 `FLAG_A` |
| 检查某位 | `flags & FLAG_A` | 判断 `FLAG_A` 是否存在 |
| 翻转某位 | `flags ^= FLAG_A` | 有则去掉，无则加上 |

完整例子：

```c
#include <stdio.h>

#define PERM_READ  (1U << 0)
#define PERM_WRITE (1U << 1)
#define PERM_EXEC  (1U << 2)

int main(void) {
    unsigned perm = 0;

    perm |= PERM_READ;
    perm |= PERM_WRITE;

    if ((perm & PERM_READ) != 0) {
        printf("readable\n");
    }

    perm &= ~PERM_WRITE;

    if ((perm & PERM_WRITE) == 0) {
        printf("not writable\n");
    }

    return 0;
}
```

这里一个整数 `perm` 同时保存多个权限：

```text
bit 0: read
bit 1: write
bit 2: exec
```

这比使用多个变量更紧凑：

```c
int readable;
int writable;
int executable;
```

在普通业务代码里，三个变量也许更清晰。但在页表、协议头、文件权限、硬件寄存器里，位标志的紧凑性和可组合性非常重要。

## 九、掩码

掩码就是专门用来选择、保留、清除某些 bit 的数。

例如：

```text
value = 1011 0110
mask  = 0000 1111
```

取低 4 位：

```text
value & mask = 0000 0110
```

清低 4 位：

```text
value & ~mask = 1011 0000
```

设置低 4 位：

```text
value | mask = 1011 1111
```

掩码的常见用途：

- 取出某几位。
- 清除某几位。
- 设置某几位。
- 判断某几位是否符合条件。

一句话概括：

```text
mask 为 1 的位会被选中；
mask 为 0 的位会被忽略或清除，取决于你使用的运算。
```

## 十、判断多个标志位

判断某一位是否存在：

```c
if ((perm & PERM_READ) != 0) {
}
```

判断读或写至少一个存在：

```c
if ((perm & (PERM_READ | PERM_WRITE)) != 0) {
}
```

判断读和写都存在：

```c
if ((perm & (PERM_READ | PERM_WRITE)) == (PERM_READ | PERM_WRITE)) {
}
```

两者区别很重要：

| 写法 | 含义 |
| --- | --- |
| `(perm & (R | W)) != 0` | `R` 或 `W` 至少一个存在 |
| `(perm & (R | W)) == (R | W)` | `R` 和 `W` 都存在 |

判断某几位全都不存在：

```c
if ((perm & (PERM_WRITE | PERM_EXEC)) == 0) {
    /* neither write nor exec is set */
}
```

权限检查这种东西，差一个 bit 就不是“差不多”的问题。它只会安静地变成漏洞或错误。

## 十一、替换一组位

有时某几位不是独立开关，而是共同表示一个模式。

例如低两位表示模式：

```c
#define MODE_MASK 0x3
#define MODE_A    0x0
#define MODE_B    0x1
#define MODE_C    0x2
```

设置模式时应该先清掉旧模式，再放入新模式：

```c
flags = (flags & ~MODE_MASK) | MODE_B;
```

拆开看：

```c
flags = flags & ~MODE_MASK;
flags = flags | MODE_B;
```

先清空低两位，再设置成 `MODE_B`。

如果直接写：

```c
flags |= MODE_B;
```

旧模式位可能残留，最后得到不合法或意外的组合。

独立标志位可以叠加：

```c
PERM_READ | PERM_WRITE
```

互斥模式位则通常要先清再设：

```c
(flags & ~MODE_MASK) | MODE_B
```

这两个模型要分清。否则代码看起来很短，问题也会很短地出现。

## 十二、xv6 页表项里的地址和标志位

页表项通常不只保存权限位，还保存物理页地址的一部分。

可以粗略理解为：

```text
高位：物理地址相关信息
低位：权限和状态标志
```

xv6 中常见的页表标志位类似：

```c
#define PTE_V (1L << 0)
#define PTE_R (1L << 1)
#define PTE_W (1L << 2)
#define PTE_X (1L << 3)
#define PTE_U (1L << 4)
```

如果一个页表项同时有效、可读、可写：

```c
PTE_V | PTE_R | PTE_W
```

从二进制看：

```text
PTE_V = 00001
PTE_R = 00010
PTE_W = 00100

PTE_V | PTE_R | PTE_W = 00111
```

一个整数里同时表达了三个权限。

提取标志位时，常见写法是使用掩码：

```c
#define PTE_FLAGS(pte) ((pte) & 0x3FF)
```

这表示取出页表项低 10 位作为标志位。

如果想清掉低位，只保留高位地址部分，可以看到类似写法：

```c
uint64 addr_part = pte & ~0x3FF;
```

这里：

```text
0x3FF = 二进制低 10 位全为 1
~0x3FF = 低 10 位为 0，其余位为 1
```

所以：

```text
pte & 0x3FF
```

表示取低 10 位。

```text
pte & ~0x3FF
```

表示清低 10 位，保留高位。

不要被十六进制吓到。`0x3FF` 只是比写一长串二进制更体面一点。

## 十三、移位的几个细节

移位常用，但边界上并不温柔。

### 1. 构造标志位时优先使用无符号类型

推荐：

```c
#define FLAG_A (1U << 0)
#define FLAG_B (1U << 1)
```

如果需要 64 位：

```c
#define FLAG64_A (1ULL << 40)
```

原因是有符号整数移位更容易踩到边界问题。

例如把 `1` 左移到有符号类型的符号位，可能产生未定义行为或实现相关行为。

xv6 里常见：

```c
#define PTE_V (1L << 0)
```

这是和它的目标平台、编译器和代码环境一起成立的写法。自己写通用 C/C++ 代码时，更推荐使用 `1U`、`1UL`、`1ULL`，或者明确的 `uint64_t` 相关类型。

### 2. 移位数量不能越界

如果类型宽度是 32 位：

```c
1U << 32
```

这是错误的。移位数量必须小于类型的位宽。

正确构造 64 位高位标志：

```c
1ULL << 32
```

因为 `1ULL` 至少提供 64 位无符号整数范围。

### 3. 有符号负数右移要谨慎

```c
int x = -8;
int y = x >> 1;
```

有符号负数右移的结果在 C 里是实现定义行为。很多机器上会做算术右移，也就是保留符号位，但不要把它当成跨平台保证。

处理位模式时，尽量使用无符号类型：

```c
unsigned x = 0x80000000U;
unsigned y = x >> 1;
```

底层代码喜欢无符号整数，并不是性格问题，而是位运算本来就更适合在无符号类型上表达。

## 十四、运算符优先级

位运算和比较、逻辑运算混用时，最容易出现优先级错误。

### 1. `&` 的优先级低于 `==`

这句有问题：

```c
if (flags & FLAG_A == 0) {
    /* wrong */
}
```

它会被理解成：

```c
if (flags & (FLAG_A == 0)) {
    /* wrong */
}
```

因为 `==` 的优先级高于按位与 `&`。

应该写：

```c
if ((flags & FLAG_A) == 0) {
    /* FLAG_A is not set */
}
```

或者：

```c
if (!(flags & FLAG_A)) {
    /* FLAG_A is not set */
}
```

括号不是多余的。它是在帮后来读代码的人省时间，也是在帮自己少犯错。

### 2. `&` 和 `&&` 不是一回事

```c
if (flags & FLAG_A) {
}

if (a && b) {
}
```

`&` 是按位与，会对整数的每一位进行运算。

`&&` 是逻辑与，只判断真假，并且有短路行为。

同样：

```c
flags | FLAG_A
```

和：

```c
a || b
```

也完全不同。

在标志位代码里，通常使用 `&`、`|`、`~`。

在条件组合里，通常使用 `&&`、`||`、`!`。

### 3. 宏里要加括号

推荐：

```c
#define BIT(n) (1ULL << (n))
#define HAS_FLAG(x, flag) (((x) & (flag)) != 0)
```

不要写成：

```c
#define BIT(n) 1ULL << n
#define HAS_FLAG(x, flag) x & flag != 0
```

宏展开只是文本替换。预处理器不会理解你的善意，也不会替你补括号。

## 十五、C++ 里的位标志

C++ 也可以直接使用 C 风格位标志：

```cpp
constexpr unsigned Read  = 1U << 0;
constexpr unsigned Write = 1U << 1;
constexpr unsigned Exec  = 1U << 2;

unsigned perm = Read | Write;
```

比宏更推荐 `constexpr`：

```cpp
constexpr unsigned bit(unsigned n) {
    return 1U << n;
}
```

如果使用枚举，可以写：

```cpp
enum Permission : unsigned {
    Read  = 1U << 0,
    Write = 1U << 1,
    Exec  = 1U << 2,
};

unsigned perm = Read | Write;
```

如果使用 `enum class`，类型更安全，但默认不能直接 `|`：

```cpp
enum class Permission : unsigned {
    Read  = 1U << 0,
    Write = 1U << 1,
    Exec  = 1U << 2,
};
```

需要自己定义运算符：

```cpp
constexpr Permission operator|(Permission a, Permission b) {
    return static_cast<Permission>(
        static_cast<unsigned>(a) | static_cast<unsigned>(b)
    );
}

constexpr bool has_permission(Permission value, Permission flag) {
    return (static_cast<unsigned>(value) & static_cast<unsigned>(flag)) != 0;
}
```

这样调用：

```cpp
Permission perm = Permission::Read | Permission::Write;

if (has_permission(perm, Permission::Read)) {
}
```

底层仍然是位运算，只是类型系统更严格。

## 十六、读 xv6 时的翻译方法

读底层代码时，不要先被符号压住。先把表达式翻译成状态变化。

### 1. 权限组合

```c
PTE_V | PTE_R | PTE_W
```

翻译：

```text
有效、可读、可写这几个权限同时存在。
```

### 2. 检查权限

```c
if ((*pte & PTE_V) == 0) {
    return 0;
}
```

翻译：

```text
如果页表项没有有效位，就返回失败。
```

### 3. 增加权限

```c
*pte |= PTE_W;
```

翻译：

```text
打开写权限，其他位不动。
```

### 4. 清除权限

```c
*pte &= ~PTE_U;
```

翻译：

```text
清除用户态可访问位，其他位保持不变。
```

### 5. 提取标志位

```c
PTE_FLAGS(pte)
```

如果定义类似：

```c
#define PTE_FLAGS(pte) ((pte) & 0x3FF)
```

翻译：

```text
取出页表项低 10 位的标志部分。
```

这种翻译看起来朴素，但非常有效。底层代码的难点往往不是某个符号本身，而是你能不能把它还原成“哪些位被保留、哪些位被打开、哪些位被清除”。

## 十七、常见错误整理

### 1. 用 `=` 覆盖标志位

错误：

```c
flags = FLAG_A;
```

如果目标是添加 `FLAG_A`，应该写：

```c
flags |= FLAG_A;
```

`=` 是整体替换，`|=` 是设置某位并保留其他位。

### 2. 清除标志位时忘记取反

错误：

```c
flags &= FLAG_A;
```

这不是清除 `FLAG_A`，而是只保留 `FLAG_A`。

正确：

```c
flags &= ~FLAG_A;
```

### 3. 检查多个标志位时语义不清

```c
if (flags & (A | B)) {
}
```

这表示 `A` 或 `B` 至少一个存在。

如果要检查 `A` 和 `B` 都存在：

```c
if ((flags & (A | B)) == (A | B)) {
}
```

### 4. 忘记优先级

错误：

```c
if (flags & A == 0) {
}
```

正确：

```c
if ((flags & A) == 0) {
}
```

这种错误很隐蔽。编译器可能不报错，因为它在语法上成立。只是语义已经去了别处。

### 5. 移位类型太窄

错误：

```c
uint64_t x = 1U << 40;
```

`1U` 通常是 32 位，先在 32 位范围内移位，已经出问题了。

正确：

```c
uint64_t x = 1ULL << 40;
```

或者：

```c
uint64_t x = (uint64_t)1 << 40;
```

## 十八、一页速查

定义标志位：

```c
#define A (1U << 0)
#define B (1U << 1)
#define C (1U << 2)
```

设置：

```c
flags |= A;
```

清除：

```c
flags &= ~A;
```

检查：

```c
if ((flags & A) != 0) {
}
```

翻转：

```c
flags ^= A;
```

检查多个位至少一个存在：

```c
if ((flags & (A | B)) != 0) {
}
```

检查多个位全部存在：

```c
if ((flags & (A | B)) == (A | B)) {
}
```

替换一组模式位：

```c
flags = (flags & ~MODE_MASK) | MODE_B;
```

取低 10 位：

```c
low = value & 0x3FF;
```

清低 10 位：

```c
high = value & ~0x3FF;
```

## 十九、总结

位运算的核心不是符号，而是状态变化。

看到：

```c
flags |= A;
```

就翻译成：

```text
打开 A。
```

看到：

```c
flags &= ~A;
```

就翻译成：

```text
关闭 A。
```

看到：

```c
flags & A
```

就翻译成：

```text
检查 A 是否存在。
```

看到 xv6 里的：

```c
PTE_V | PTE_R | PTE_W
```

就翻译成：

```text
页表项有效、可读、可写。
```

看到：

```c
*pte &= ~PTE_U;
```

就翻译成：

```text
清除用户态可访问权限。
```

只要能完成这种翻译，位运算就不再是一堆冷冰冰的符号，而是一组明确的开关操作。它仍然不亲切，但至少诚实。而在系统代码里，诚实已经算是相当不错的品质了。
