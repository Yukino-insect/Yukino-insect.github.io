+++
date = '2026-08-24T20:00:00+08:00'
draft = false
title = 'C 与 C++ 函数指针、指针函数与位运算：从语法到 xv6 读码'
+++

读 xv6 这类 C 代码时，有几类语法很容易让人停下来：

```c
static uint64 (*syscalls[])(void) = {
    [SYS_fork] sys_fork,
    [SYS_exit] sys_exit,
};

#define PTE_V (1L << 0)
#define PTE_R (1L << 1)
#define PTE_W (1L << 2)

flags |= PTE_W;
flags &= ~PTE_U;
```

如果只从表面看，它们确实不太像平时写业务代码时会频繁接触的东西。尤其是 `(*syscalls[])(void)` 这种声明，括号、星号、数组、函数返回值混在一起，看起来像是在故意刁难读者。

但它们并不神秘。函数指针本质上是“保存函数入口地址的变量”，指针函数本质上是“返回指针的函数”，位运算本质上是“把整数的每一位当作开关使用”。说得稍微刻薄一点：难点往往不在概念，而在声明语法过于节俭，节俭到近乎没有同情心。

这篇文章整理三件事：

- 什么是函数指针，怎么读函数指针声明。
- 什么是指针函数，它和函数指针到底差在哪里。
- C 的位运算怎么用于权限、标志位、页表和系统代码。

## 一、先区分两个名字

先把最容易混淆的两个概念摆清楚：

| 名称 | 英文习惯说法 | 核心含义 | 例子 |
| --- | --- | --- | --- |
| 函数指针 | function pointer | 指向函数的指针 | `int (*fp)(int, int)` |
| 指针函数 | function returning pointer | 返回指针的函数 | `int *f(int, int)` |

中文里的“函数指针”和“指针函数”只差两个字的位置，含义却完全不同。

### 1. 函数指针

函数指针是一个指针变量。它保存的不是普通数据地址，而是某个函数的入口地址。

```c
int add(int a, int b) {
    return a + b;
}

int (*fp)(int, int) = add;

int result = fp(3, 4);
```

这里：

- `add` 是函数。
- `fp` 是指向函数的指针。
- `fp(3, 4)` 通过函数指针调用 `add`。

`fp` 的类型可以读成：

```text
fp 是一个指针
它指向一个函数
这个函数接收两个 int 参数
这个函数返回 int
```

### 2. 指针函数

指针函数不是指针变量，而是一个函数。只是这个函数的返回值是指针。

```c
int global_value = 10;

int *get_value(void) {
    return &global_value;
}

int *p = get_value();
```

这里：

- `get_value` 是函数。
- 它没有参数。
- 它返回 `int *`。

`int *get_value(void)` 可以读成：

```text
get_value 是一个函数
它不接收参数
它返回 int *
```

这就叫指针函数。更准确地说，是“返回指针的函数”。

## 二、为什么 `*` 的位置会让人困惑

C 声明的麻烦之处在于：同一个 `*`，放在不同位置，含义就不同。

先看两个声明：

```c
int *f(int);
int (*f)(int);
```

它们只差一对括号，但含义完全不同。

### 1. `int *f(int)`

```c
int *f(int);
```

这是一个函数声明。

读法是：

```text
f 是一个函数
参数是 int
返回值是 int *
```

所以它是指针函数。

### 2. `int (*f)(int)`

```c
int (*f)(int);
```

这是一个函数指针声明。

读法是：

```text
f 是一个指针
指向一个函数
这个函数参数是 int
返回值是 int
```

为什么括号这么关键？因为在 C 里，函数调用运算符 `()` 的优先级高于一元 `*`。

如果没有括号：

```c
int *f(int);
```

编译器会先把 `f` 和 `(int)` 结合，于是 `f` 先成为函数，返回值再是 `int *`。

如果有括号：

```c
int (*f)(int);
```

`*f` 被括号包起来，说明 `f` 先是指针，然后这个指针指向函数。

这对括号不是装饰。它是分界线。少了它，类型就换了。

## 三、声明阅读规则

读复杂声明时，可以使用一个非常实用的原则：

**从标识符开始，优先向右看，再向左看；遇到括号先处理括号。**

比如：

```c
int (*fp)(int, int);
```

从 `fp` 开始：

```text
fp
(*fp)       fp 是一个指针
(*fp)(...) 这个指针指向函数
int        函数返回 int
```

所以：

```text
fp 是一个指向函数的指针，该函数接收两个 int，返回 int。
```

再看：

```c
int *func(int, int);
```

从 `func` 开始：

```text
func(...)  func 是函数
int *      函数返回 int *
```

所以：

```text
func 是一个函数，接收两个 int，返回 int *。
```

### 1. 对照表

| 声明 | 含义 |
| --- | --- |
| `int *p` | `p` 是指向 `int` 的指针 |
| `int f(int)` | `f` 是函数，接收 `int`，返回 `int` |
| `int *f(int)` | `f` 是函数，接收 `int`，返回 `int *` |
| `int (*fp)(int)` | `fp` 是函数指针，指向接收 `int`、返回 `int` 的函数 |
| `int (*arr[4])(int)` | `arr` 是数组，数组元素是函数指针 |
| `int *(*fp)(int)` | `fp` 是函数指针，指向接收 `int`、返回 `int *` 的函数 |

最后两个看起来稍微不友好，但读法依然一样。

```c
int (*arr[4])(int);
```

从 `arr` 开始：

```text
arr[4]       arr 是长度为 4 的数组
*arr[4]      数组元素是指针
(*arr[4])()  指针指向函数
int          函数返回 int
```

所以 `arr` 是函数指针数组。

## 四、函数名和函数地址

在表达式中，函数名通常会转换成指向该函数的指针。

```c
int add(int a, int b) {
    return a + b;
}

int (*fp)(int, int);

fp = add;
fp = &add;
```

上面两种赋值在 C 里通常都可以。

调用时也有两种写法：

```c
int a = fp(1, 2);
int b = (*fp)(1, 2);
```

这两种写法也都可以。

不过实际工程中更常见的是：

```c
fp(1, 2);
```

因为它更简洁，也更像普通函数调用。

### 1. 函数指针不是 `void *`

普通对象指针可以和 `void *` 互相转换：

```c
int x = 10;
void *p = &x;
```

但函数指针和对象指针不是一类东西。标准 C 不保证函数指针能安全转换成 `void *` 再转回来。

在很多平台上，这样做可能“看起来能运行”，但底层代码不应该把这种事当成理所当然。尤其是读操作系统代码时，看到函数指针就把它当成独立的函数地址类型，不要随手塞进 `void *` 里。

### 2. 函数指针类型必须匹配

函数指针不只记录“这是个函数地址”，还记录函数签名：

```c
int (*fp1)(int, int);
void (*fp2)(void);
char *(*fp3)(const char *);
```

这些是不同类型。

如果把签名不匹配的函数塞给函数指针，再通过它调用，结果可能是未定义行为。因为调用约定依赖参数和返回值类型。调用者和被调用者如果对参数数量、参数类型、返回值类型理解不一致，运行时就可能乱掉。

这不是编译器小题大做。机器代码层面没有那么多温柔的保护。

## 五、函数指针的基本用法

函数指针常见用途有三类：

- 回调函数。
- 分发表。
- 抽象接口。

### 1. 回调函数

回调就是：把函数作为参数传给另一个函数，由后者在合适的时候调用。

```c
int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

int apply(int x, int y, int (*op)(int, int)) {
    return op(x, y);
}

int main(void) {
    int a = apply(3, 4, add);
    int b = apply(3, 4, multiply);

    return 0;
}
```

这里 `apply` 不关心具体做加法还是乘法。它只要求传进来的函数满足这个签名：

```c
int (*op)(int, int)
```

也就是：

```text
接收两个 int，返回 int。
```

这就是 C 里常见的“把行为参数化”。

### 2. 标准库里的例子：`qsort`

C 标准库里的 `qsort` 就使用了函数指针。

典型声明类似：

```c
void qsort(
    void *base,
    size_t nmemb,
    size_t size,
    int (*compar)(const void *, const void *)
);
```

最后一个参数 `compar` 是比较函数指针。

例如排序 `int` 数组：

```c
#include <stdlib.h>

int cmp_int(const void *a, const void *b) {
    const int *pa = a;
    const int *pb = b;

    if (*pa < *pb) {
        return -1;
    }
    if (*pa > *pb) {
        return 1;
    }
    return 0;
}

int main(void) {
    int arr[] = { 4, 1, 3, 2 };

    qsort(arr, 4, sizeof(arr[0]), cmp_int);

    return 0;
}
```

`qsort` 不知道你要排序什么类型，也不知道你的比较规则。它只知道一件事：需要比较两个元素时，调用你给它的 `compar`。

这就是函数指针的价值。C 没有模板和泛型函数的那套语法，但它可以用 `void *` 搭配函数指针实现相当朴素的通用算法。

### 3. 分发表

分发表就是把一组操作放进数组，通过下标选择要调用的函数。

```c
int add(int a, int b) {
    return a + b;
}

int sub(int a, int b) {
    return a - b;
}

int mul(int a, int b) {
    return a * b;
}

int (*ops[])(int, int) = {
    add,
    sub,
    mul,
};

int main(void) {
    int op = 2;
    int result = ops[op](3, 4);

    return 0;
}
```

这里：

```c
ops[op](3, 4)
```

等价于：

```text
取出 ops[op] 这个函数指针
调用它
传入 3 和 4
```

这类写法在解释器、虚拟机、驱动、系统调用、中断处理里很常见。不是因为作者喜欢炫技，而是因为它确实适合把“编号”映射到“行为”。

## 六、xv6 的系统调用表

xv6 中的系统调用表就是函数指针数组的典型例子。

代码形式类似：

```c
static uint64 (*syscalls[])(void) = {
    [SYS_fork]    sys_fork,
    [SYS_exit]    sys_exit,
    [SYS_wait]    sys_wait,
    [SYS_pipe]    sys_pipe,
    [SYS_read]    sys_read,
    [SYS_kill]    sys_kill,
    [SYS_exec]    sys_exec,
    [SYS_fstat]   sys_fstat,
    [SYS_chdir]   sys_chdir,
    [SYS_dup]     sys_dup,
    [SYS_getpid]  sys_getpid,
    [SYS_sbrk]    sys_sbrk,
    [SYS_sleep]   sys_sleep,
    [SYS_uptime]  sys_uptime,
    [SYS_open]    sys_open,
    [SYS_write]   sys_write,
    [SYS_mknod]   sys_mknod,
    [SYS_unlink]  sys_unlink,
    [SYS_link]    sys_link,
    [SYS_mkdir]   sys_mkdir,
    [SYS_close]   sys_close,
};
```

先读声明：

```c
static uint64 (*syscalls[])(void)
```

从 `syscalls` 开始：

```text
syscalls[]          syscalls 是数组
*syscalls[]         数组元素是指针
(*syscalls[])(void) 指针指向函数，该函数无参数
uint64              函数返回 uint64
static              这个数组只在当前源文件内部可见
```

所以它的完整含义是：

```text
syscalls 是一个静态数组，数组元素是函数指针；
每个函数指针指向一个无参数、返回 uint64 的函数。
```

### 1. 为什么系统调用适合用函数指针数组

用户程序执行系统调用时，最终会把一个系统调用号传给内核。内核要做的事情是：

```text
系统调用号 -> 对应的内核处理函数
```

比如：

| 系统调用号 | 处理函数 |
| --- | --- |
| `SYS_fork` | `sys_fork` |
| `SYS_exit` | `sys_exit` |
| `SYS_read` | `sys_read` |
| `SYS_write` | `sys_write` |

如果不用函数指针数组，可以写成一长串 `switch`：

```c
switch (num) {
case SYS_fork:
    return sys_fork();
case SYS_exit:
    return sys_exit();
case SYS_read:
    return sys_read();
case SYS_write:
    return sys_write();
default:
    return -1;
}
```

这样当然可以。但系统调用很多时，分发表更简洁：

```c
if (num > 0 && num < NELEM(syscalls) && syscalls[num]) {
    p->trapframe->a0 = syscalls[num]();
} else {
    p->trapframe->a0 = -1;
}
```

这段逻辑的核心是：

```text
检查系统调用号是否合法
检查表里有没有对应函数
调用 syscalls[num]()
把返回值放回用户寄存器保存区
```

### 2. `[SYS_fork] sys_fork` 是什么

数组初始化里这种写法：

```c
[SYS_fork] sys_fork
```

是指定初始化器的写法。它表示把 `sys_fork` 放到数组下标 `SYS_fork` 的位置。

需要稍微留意一点：标准 C99 的指定初始化器通常写成带 `=` 的形式：

```c
[SYS_fork] = sys_fork
```

xv6 源码里常见的：

```c
[SYS_fork] sys_fork
```

是 GCC 支持的旧式 GNU 写法。读 xv6 时按源码理解即可；自己写可移植 C 代码时，优先写标准 C99 形式。语法这种东西，偶尔也会留下历史包袱，当然它不会主动向你道歉。

普通数组初始化是按顺序放：

```c
int a[] = { 10, 20, 30 };
```

等价于：

```text
a[0] = 10
a[1] = 20
a[2] = 30
```

指定初始化器可以直接指定下标：

```c
int a[] = {
    [3] = 10,
    [7] = 20,
};
```

表示：

```text
a[3] = 10
a[7] = 20
```

xv6 的系统调用表用这种写法，是因为系统调用号本身就是固定编号。把函数放到对应编号的位置，比依赖初始化顺序更清楚，也更不容易因为插入新系统调用而错位。

### 3. 为什么所有 `sys_xxx` 都是同一类签名

系统调用函数通常长得像这样：

```c
uint64 sys_write(void);
uint64 sys_read(void);
uint64 sys_fork(void);
```

它们都不直接在 C 函数参数里接收用户传来的参数，而是从当前进程的 trapframe 或系统调用参数读取逻辑里取参数。

所以系统调用表可以统一写成：

```c
uint64 (*)(void)
```

也就是“无参数、返回 `uint64` 的函数指针”。

这种统一签名很重要。因为一个数组里的所有元素必须是同一种类型。假如 `sys_read` 是 `uint64 (*)(int, void *, int)`，而 `sys_fork` 是 `uint64 (*)(void)`，它们就不能自然放进同一个函数指针数组里。

## 七、用 `typedef` 简化函数指针

函数指针声明写多了，确实难看。C 里常用 `typedef` 简化。

```c
typedef int (*binary_op)(int, int);
```

这表示：

```text
binary_op 是一个类型别名
它代表：指向函数的指针，该函数接收两个 int，返回 int
```

于是可以写：

```c
int add(int a, int b) {
    return a + b;
}

int sub(int a, int b) {
    return a - b;
}

binary_op op = add;
binary_op ops[] = { add, sub };
```

对系统调用表也可以写成类似形式：

```c
typedef uint64 (*syscall_fn)(void);

static syscall_fn syscalls[] = {
    [SYS_fork] sys_fork,
    [SYS_exit] sys_exit,
};
```

这样可读性会好一些。

不过 xv6 原代码常常选择直接写类型。这也并不奇怪：教学代码倾向于把底层事实摊开。它并不总是追求最舒适的包装。

### 1. `typedef` 到底给谁起别名

这一点很容易误读。

```c
typedef int (*binary_op)(int, int);
```

不是给 `int` 起别名，也不是给函数起别名，而是给整个函数指针类型起别名。

可以把普通变量声明和 `typedef` 对照：

```c
int (*fp)(int, int);
```

这里 `fp` 是变量名。

改成：

```c
typedef int (*binary_op)(int, int);
```

这里 `binary_op` 就变成类型名。

C 的 `typedef` 语法就是这样：先写一个“变量声明的样子”，再把里面的名字变成类型别名。它很强大，也很容易让第一次见的人怀疑自己是不是看错了。遗憾的是，通常不是你看错了，是语法本来就这样。

## 八、C++ 里的函数指针

C++ 也支持 C 风格函数指针：

```cpp
int add(int a, int b) {
    return a + b;
}

int (*fp)(int, int) = add;
int result = fp(3, 4);
```

但 C++ 还多了几类容易混淆的东西：

- 普通函数指针。
- 成员函数指针。
- 函数对象。
- Lambda。
- `std::function`。

这篇文章重点是 C 和 xv6 读码，所以这里只做必要区分。

### 1. 普通函数指针

普通函数指针只能指向普通函数或不捕获变量的 lambda。

```cpp
int (*fp)(int, int) = add;
```

不捕获变量的 lambda 可以转换成函数指针：

```cpp
int (*fp)(int, int) = [](int a, int b) {
    return a + b;
};
```

捕获变量的 lambda 不行：

```cpp
int base = 10;

// 不能转换成普通函数指针
// int (*fp)(int) = [base](int x) { return x + base; };
```

因为捕获变量的 lambda 内部需要保存状态，而普通函数指针只是一个函数入口地址，不携带对象状态。

### 2. 成员函数指针不是普通函数指针

C++ 成员函数有隐含的 `this` 对象，所以成员函数指针和普通函数指针不是一回事。

```cpp
struct Counter {
    int value;

    int add(int x) {
        return value + x;
    }
};

int (Counter::*fp)(int) = &Counter::add;
```

调用时必须绑定对象：

```cpp
Counter c{10};
int result = (c.*fp)(5);
```

如果是对象指针：

```cpp
Counter *p = &c;
int result2 = (p->*fp)(5);
```

这和 C 的函数指针不是同一种东西。读 C 代码时不用把它们混在一起。

### 3. C++ 中更常见的封装

C++ 里经常会用 `using` 简化类型：

```cpp
using BinaryOp = int (*)(int, int);
```

也会用 `std::function` 保存更通用的可调用对象：

```cpp
#include <functional>

std::function<int(int, int)> op;
```

`std::function` 可以保存普通函数、函数对象、捕获 lambda 等可调用对象。代价是它比裸函数指针更重。系统底层 C 代码一般不会使用这类抽象，xv6 也不需要。

## 九、指针函数的常见用途

指针函数，也就是返回指针的函数，在系统代码里非常常见。

```c
struct proc *myproc(void);
char *sbrk(int n);
void *memmove(void *dst, const void *src, uint n);
```

它的意义是：函数执行后，给调用者一个对象地址。

### 1. 返回全局对象地址

```c
struct cpu cpus[NCPU];

struct cpu *mycpu(void) {
    int id = cpuid();
    return &cpus[id];
}
```

这里 `mycpu` 是指针函数：

```text
mycpu 是函数
返回 struct cpu *
```

调用者拿到当前 CPU 对应的结构体指针：

```c
struct cpu *c = mycpu();
```

### 2. 返回结构体字段地址

```c
struct proc {
    char name[16];
    int pid;
};

char *proc_name(struct proc *p) {
    return p->name;
}
```

数组名 `p->name` 在表达式里会转换成指向首元素的指针，所以返回类型是 `char *`。

### 3. 返回动态分配的内存

```c
#include <stdlib.h>

int *make_int(int value) {
    int *p = malloc(sizeof(*p));
    if (p == NULL) {
        return NULL;
    }

    *p = value;
    return p;
}
```

这种写法要格外注意所有权：

```c
int *p = make_int(10);
free(p);
```

谁负责释放？什么时候释放？能不能返回 `NULL`？这些都应该在接口约定里说清楚。否则返回指针这件事本身很简单，麻烦的是生命周期。

### 4. 不要返回局部变量地址

这是指针函数最常见的错误：

```c
int *bad(void) {
    int x = 10;
    return &x;
}
```

`x` 是局部变量，函数返回后它的生命周期结束。返回它的地址会得到悬空指针。

正确方式取决于你的目标：

```c
static int x = 10;

int *ok_static(void) {
    return &x;
}
```

或者：

```c
#include <stdlib.h>

int *ok_heap(void) {
    int *p = malloc(sizeof(*p));
    if (p == NULL) {
        return NULL;
    }

    *p = 10;
    return p;
}
```

`static` 对象的生命周期贯穿整个程序。堆对象则需要调用者或某个明确的拥有者释放。

## 十、位运算的基本模型

C 的位运算把整数当作二进制位序列处理。

常用运算符有：

| 运算符 | 名称 | 含义 |
| --- | --- | --- |
| `&` | 按位与 | 两位都为 1，结果才为 1 |
| `|` | 按位或 | 两位有一个为 1，结果就是 1 |
| `^` | 按位异或 | 两位不同，结果为 1 |
| `~` | 按位取反 | 0 变 1，1 变 0 |
| `<<` | 左移 | 二进制位整体向左移动 |
| `>>` | 右移 | 二进制位整体向右移动 |

先用 4 位二进制看：

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

实际 C 里的 `int`、`long`、`uint64` 当然不止 4 位，这里只是为了看清楚。

### 1. 左移：构造某一位

```c
1 << 0  // 0001
1 << 1  // 0010
1 << 2  // 0100
1 << 3  // 1000
```

因此常见宏会这样写：

```c
#define FLAG_A (1U << 0)
#define FLAG_B (1U << 1)
#define FLAG_C (1U << 2)
```

每个宏占据一个不同的 bit。

### 2. 按位或：打开开关

```c
unsigned flags = 0;

flags |= FLAG_A;
flags |= FLAG_C;
```

`|=` 表示：

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

再加 `FLAG_C`：

```text
flags  = 0001
FLAG_C = 0100
result = 0101
```

所以按位或常用于**设置某个标志位**。

### 3. 按位与：检查开关

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

所以按位与常用于**测试某个标志位是否打开**。

### 4. 取反再按位与：关闭开关

```c
flags &= ~FLAG_A;
```

这表示：

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

常用于**清除某个标志位**。

### 5. 异或：翻转开关

```c
flags ^= FLAG_A;
```

如果 `FLAG_A` 原来是 1，异或后变成 0。  
如果 `FLAG_A` 原来是 0，异或后变成 1。

因此异或常用于**切换某个标志位**。

不过在权限代码里，异或要谨慎使用。权限通常需要明确设置或清除，而不是“原来有就去掉，原来没有就加上”。这种暧昧行为很容易制造安全问题。

## 十一、标志位的增删查改

可以把位运算记成四个动作：

| 操作 | 写法 | 含义 |
| --- | --- | --- |
| 设置某位 | `flags |= FLAG_A` | 打开 `FLAG_A` |
| 清除某位 | `flags &= ~FLAG_A` | 关闭 `FLAG_A` |
| 检查某位 | `flags & FLAG_A` | 判断 `FLAG_A` 是否存在 |
| 翻转某位 | `flags ^= FLAG_A` | 有则去掉，无则加上 |

再把它放进一个完整例子：

```c
#include <stdio.h>

#define PERM_READ  (1U << 0)
#define PERM_WRITE (1U << 1)
#define PERM_EXEC  (1U << 2)

int main(void) {
    unsigned perm = 0;

    perm |= PERM_READ;
    perm |= PERM_WRITE;

    if (perm & PERM_READ) {
        printf("readable\n");
    }

    perm &= ~PERM_WRITE;

    if ((perm & PERM_WRITE) == 0) {
        printf("not writable\n");
    }

    return 0;
}
```

这里一个整数 `perm` 同时保存了多个权限：

```text
bit 0: read
bit 1: write
bit 2: exec
```

这比用三个独立变量紧凑：

```c
int readable;
int writable;
int executable;
```

在操作系统、文件格式、网络协议、硬件寄存器里，这种紧凑性和可组合性很重要。

## 十二、xv6 页表权限位

xv6 的页表项权限位通常类似：

```c
#define PTE_V (1L << 0)
#define PTE_R (1L << 1)
#define PTE_W (1L << 2)
#define PTE_X (1L << 3)
#define PTE_U (1L << 4)
```

这些宏表示页表项里的不同 bit：

| 宏 | 含义 |
| --- | --- |
| `PTE_V` | valid，有效 |
| `PTE_R` | readable，可读 |
| `PTE_W` | writable，可写 |
| `PTE_X` | executable，可执行 |
| `PTE_U` | user，用户态可访问 |

如果一个页表项同时有读、写、有效权限，可以写：

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

### 1. 检查页表项是否有效

```c
if (*pte & PTE_V) {
    /* valid */
}
```

意思是：

```text
取出页表项的 PTE_V 那一位
如果结果非 0，说明有效位存在
```

更严格地写也可以：

```c
if ((*pte & PTE_V) != 0) {
    /* valid */
}
```

这两种写法都常见。后一种对初学者更直观。

### 2. 增加写权限

```c
*pte |= PTE_W;
```

这会设置 `PTE_W` 位，同时保留其他位。

不要写成：

```c
*pte = PTE_W;
```

这会把其他位全部覆盖掉。比如原来的 `PTE_V`、`PTE_R` 都会丢失。底层代码里，这种差别足够让系统表现得相当冷淡。

### 3. 清除用户态访问权限

```c
*pte &= ~PTE_U;
```

这会清掉 `PTE_U`，保留其他位。

如果原来：

```text
*pte  = PTE_V | PTE_R | PTE_W | PTE_U
```

清除后：

```text
*pte  = PTE_V | PTE_R | PTE_W
```

在页表代码里，`~` 经常和 `&` 配合使用。看见它时不要紧张，先翻译成：

```text
把某一位变成 0，其他位尽量不动
```

### 4. 提取地址和标志位

页表项通常不只保存权限位，还保存物理页地址的一部分。于是底层代码里经常会有“取出地址部分”和“取出标志位部分”的操作。

示意：

```c
#define PTE_FLAGS(pte) ((pte) & 0x3FF)
```

这表示取出页表项低 10 位作为标志位。

如果想清掉低位，只保留高位地址部分，可能会看到类似：

```c
uint64 addr_part = pte & ~0x3FF;
```

这类操作的核心仍然是掩码：

```text
mask 为 1 的位会被保留或选中
mask 为 0 的位会被清除或忽略
```

不要被十六进制吓到。`0x3FF` 只是二进制的低 10 位全为 1：

```text
0x3FF = 11 1111 1111
```

它适合拿来选中低 10 位。

## 十三、掩码是什么

掩码就是专门用来选择、保留、清除某些 bit 的数。

比如：

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

### 1. 判断多个权限是否同时存在

如果要判断读写权限是否都存在：

```c
if ((perm & (PERM_READ | PERM_WRITE)) == (PERM_READ | PERM_WRITE)) {
    /* both read and write are set */
}
```

注意不是简单写：

```c
if (perm & (PERM_READ | PERM_WRITE)) {
    /* read or write is set */
}
```

这只能说明两个权限中至少有一个存在。

两者区别是：

| 写法 | 含义 |
| --- | --- |
| `perm & (R | W)` | `R` 或 `W` 至少一个存在 |
| `(perm & (R | W)) == (R | W)` | `R` 和 `W` 都存在 |

这类细节在权限判断里非常重要。权限检查这种东西，差一个 bit 就不再是“差不多”的问题了。

### 2. 判断某几位是否全都不存在

```c
if ((perm & (PERM_WRITE | PERM_EXEC)) == 0) {
    /* neither write nor exec is set */
}
```

这表示写权限和执行权限都没有。

### 3. 替换一组位

如果一个整数里某几位表示模式，例如低两位表示状态：

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

这句可以拆成两步：

```c
flags = flags & ~MODE_MASK;
flags = flags | MODE_B;
```

先清空低两位，再设置成 `MODE_B`。

如果直接：

```c
flags |= MODE_B;
```

旧模式位可能残留，最后得到一个不合法或意料之外的组合。

## 十四、移位的细节

移位很常用，但也有几个细节需要认真对待。

### 1. 使用无符号类型更稳妥

构造标志位时，更推荐使用无符号整数：

```c
#define FLAG_A (1U << 0)
#define FLAG_B (1U << 1)
```

如果需要 64 位：

```c
#define FLAG64_A (1ULL << 40)
```

原因是有符号整数移位更容易踩到边界问题。比如把 `1` 左移到符号位，可能产生未定义行为或实现相关行为。

xv6 里常见 `1L << n`，这是和它的目标平台、代码环境一起成立的写法。自己写通用 C/C++ 代码时，优先考虑 `1U`、`1UL`、`1ULL` 或明确的 `uint64_t`。

### 2. 移位数量不能越界

如果类型宽度是 32 位：

```c
1U << 32
```

这是错误的。移位数量必须小于类型的位宽。

正确构造 64 位高位标志时：

```c
1ULL << 32
```

因为 `1ULL` 至少是 64 位无符号整数。

### 3. 右移有符号负数要谨慎

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

底层代码看起来喜欢无符号整数，并不是性格问题，而是位运算本来就更适合在无符号类型上表达。

## 十五、运算符优先级

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

在标志位代码里，通常使用 `&`、`|`、`~`。在条件组合里，通常使用 `&&`、`||`、`!`。

### 3. 常见优先级建议

不需要死背完整优先级表。实际写代码时，记住几条就够用：

- 位运算和比较混用时，加括号。
- 位运算和逻辑运算混用时，加括号。
- 移位表达式作为宏时，加括号。
- 宏参数参与运算时，加括号。

例如：

```c
#define BIT(n) (1ULL << (n))
#define HAS_FLAG(x, flag) (((x) & (flag)) != 0)
```

不要写成：

```c
#define BIT(n) 1ULL << n
#define HAS_FLAG(x, flag) x & flag != 0
```

宏展开之后，优先级问题会变得更难看。C 预处理器不会替你理解语义，它只是文本替换。很冷静，也很无情。

## 十六、函数指针和位运算的共同点

函数指针和位运算看起来属于两个世界：

- 函数指针处理“代码地址”。
- 位运算处理“整数 bit”。

但在系统代码里，它们经常承担同一种职责：**用简单、稳定、低开销的表示方式，把复杂行为压缩进机器容易处理的形式里。**

函数指针数组把：

```text
系统调用号 -> 处理函数
```

变成：

```c
syscalls[num]()
```

位运算把：

```text
有效、可读、可写、可执行、用户可访问
```

变成：

```c
PTE_V | PTE_R | PTE_W | PTE_U
```

它们都不华丽，但都很直接。

操作系统代码尤其偏爱这种直接性。因为内核需要精确控制内存、权限、寄存器、页表、调度状态。抽象当然有价值，但在这些位置上，抽象必须足够贴近机器。

## 十七、读 xv6 时的翻译方法

遇到复杂 C 语法时，不妨先翻译成普通话。

### 1. 函数指针数组

```c
static uint64 (*syscalls[])(void)
```

翻译：

```text
syscalls 是当前文件内部使用的一张表。
表里的每一项都是函数指针。
这些函数都没有参数，返回 uint64。
```

### 2. 系统调用分发

```c
p->trapframe->a0 = syscalls[num]();
```

翻译：

```text
根据系统调用号 num，从 syscalls 表里取出处理函数。
调用这个函数。
把返回值写入当前进程 trapframe 的 a0 寄存器位置。
```

### 3. 页表权限组合

```c
PTE_V | PTE_R | PTE_W
```

翻译：

```text
有效 + 可读 + 可写。
```

### 4. 检查权限

```c
if ((*pte & PTE_V) == 0) {
    return 0;
}
```

翻译：

```text
如果页表项没有有效位，就返回失败。
```

### 5. 清除权限

```c
*pte &= ~PTE_U;
```

翻译：

```text
清掉用户态可访问位，其他位保持不变。
```

这种翻译看起来朴素，但很有用。读底层代码时，能把表达式翻译成状态变化，就已经迈过了最重要的一步。

## 十八、常见错误整理

### 1. 把函数指针写成指针函数

错误：

```c
int *fp(int, int);
```

这声明的是函数，不是函数指针。

正确：

```c
int (*fp)(int, int);
```

记住：函数指针里的 `*fp` 通常需要括号包起来。

### 2. 返回局部变量地址

错误：

```c
int *f(void) {
    int x = 1;
    return &x;
}
```

函数返回后，`x` 已经失效。

### 3. 用 `=` 覆盖标志位

错误：

```c
flags = FLAG_A;
```

如果你的目标是“添加 `FLAG_A`”，应该写：

```c
flags |= FLAG_A;
```

`=` 是整体替换，`|=` 是设置某位并保留其他位。

### 4. 清除标志位时忘记取反

错误：

```c
flags &= FLAG_A;
```

这不是清除 `FLAG_A`，而是只保留 `FLAG_A` 这一位，其他位都会被清掉。

清除应该写：

```c
flags &= ~FLAG_A;
```

### 5. 检查多个标志位时语义不清

```c
if (flags & (A | B)) {
}
```

这表示 `A` 或 `B` 至少一个存在。

如果你要检查 `A` 和 `B` 都存在，应该写：

```c
if ((flags & (A | B)) == (A | B)) {
}
```

### 6. 忘记优先级

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

这种错误非常隐蔽。编译器可能不报错，因为它在语法上是成立的。只是语义已经偏到别处去了。

## 十九、一页速查

### 1. 函数指针

```c
int (*fp)(int, int);
```

含义：

```text
fp 是指向函数的指针，该函数接收两个 int，返回 int。
```

赋值和调用：

```c
fp = add;
result = fp(1, 2);
```

函数指针数组：

```c
int (*ops[])(int, int) = {
    add,
    sub,
    mul,
};
```

### 2. 指针函数

```c
int *f(int);
```

含义：

```text
f 是函数，接收 int，返回 int *。
```

注意：

```c
int *bad(void) {
    int x = 10;
    return &x;
}
```

不要返回局部变量地址。

### 3. 位运算

```c
#define A (1U << 0)
#define B (1U << 1)
#define C (1U << 2)
```

常用操作：

```c
flags |= A;          // 设置 A
flags &= ~A;         // 清除 A
if (flags & A) {}    // 检查 A
flags ^= A;          // 翻转 A
```

检查多个位：

```c
if ((flags & (A | B)) == (A | B)) {
    /* A and B are both set */
}
```

## 二十、总结

函数指针、指针函数和位运算，都是读 C 系统代码绕不开的基础。

函数指针要抓住一句话：

```text
它是指向函数的指针，保存函数入口地址，可以通过它调用函数。
```

指针函数要抓住一句话：

```text
它是返回指针的函数，重点在返回值类型。
```

位运算要抓住一句话：

```text
它把整数的每个 bit 当作独立开关，用掩码进行设置、清除、检查和组合。
```

读 xv6 时，看到：

```c
static uint64 (*syscalls[])(void)
```

就把它翻译成“系统调用处理函数表”。

看到：

```c
PTE_V | PTE_R | PTE_W
```

就把它翻译成“有效、可读、可写这几个权限同时存在”。

看到：

```c
flags &= ~PTE_U;
```

就把它翻译成“清除用户态可访问权限”。

只要能完成这种翻译，所谓复杂 C 语法就会从一团符号变成一组明确的状态变化。代码不会因此变得亲切，但至少会变得诚实。而对读系统代码来说，诚实已经是相当不错的品质了。
