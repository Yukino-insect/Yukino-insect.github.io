+++
date = '2026-08-25T20:00:00+08:00'
draft = false
title = 'C 与 C++ 如何表示一个函数：函数指针、Lambda 与 std::function'
+++

在 C 和 C++ 里，“函数”并不只有一种表示方式。

你可能会看到 C 代码：

```c
int add(int a, int b);

int (*fp)(int, int) = add;
```

也可能会看到 C++ 代码：

```cpp
auto f = [](int a, int b) {
    return a + b;
};

std::function<int(int, int)> g = f;
```

如果继续读系统代码，还会遇到这种声明：

```c
static uint64 (*syscalls[])(void) = {
    [SYS_fork] sys_fork,
    [SYS_exit] sys_exit,
};
```

它们看起来不像同一种东西，但都在回答同一个问题：

```text
如何把“可以被调用的一段行为”表示出来？
```

C 的答案很朴素：普通函数、函数名、函数指针、函数指针数组。

C++ 的答案更丰富：普通函数、函数指针、成员函数指针、函数对象、Lambda、`std::function`，以及更泛化的“可调用对象”概念。

这些东西不是为了让语法显得高深。虽然它们偶尔确实会这么做，而且毫无悔意。真正的核心是：代码有时不只需要立即调用一个函数，还需要保存它、传递它、组合它，或者在运行时决定调用哪一个函数。

## 一、普通函数

最普通的函数声明是这样：

```c
int add(int a, int b);
```

它的类型可以理解为：

```text
接收两个 int，返回 int 的函数。
```

定义如下：

```c
int add(int a, int b) {
    return a + b;
}
```

调用时写：

```c
int result = add(3, 4);
```

这里 `add` 是函数名。函数名代表一段可以被调用的代码。

在大多数表达式场景中，函数名会转换成“指向该函数的指针”。所以你可以写：

```c
int (*fp)(int, int) = add;
```

也可以写：

```c
int (*fp)(int, int) = &add;
```

两种写法通常都成立。实际工程里更常见的是 `fp = add`，因为函数名本来就会转换成函数指针。

## 二、函数指针

函数指针是一个指针变量。

它保存的不是普通数据地址，而是函数入口地址。

```c
int add(int a, int b) {
    return a + b;
}

int (*fp)(int, int) = add;

int result = fp(3, 4);
```

这里：

| 名称 | 含义 |
| --- | --- |
| `add` | 普通函数 |
| `fp` | 函数指针 |
| `fp(3, 4)` | 通过函数指针调用函数 |

`fp` 的类型是：

```c
int (*)(int, int)
```

意思是：

```text
指向某个函数的指针；
这个函数接收两个 int；
返回 int。
```

变量声明则是：

```c
int (*fp)(int, int);
```

这对括号不能省。少了括号，类型就变了。

## 三、函数指针和指针函数

中文里的“函数指针”和“指针函数”只差两个字的位置，含义却完全不同。

| 名称 | 英文习惯说法 | 核心含义 | 例子 |
| --- | --- | --- | --- |
| 函数指针 | function pointer | 指向函数的指针 | `int (*fp)(int, int)` |
| 指针函数 | function returning pointer | 返回指针的函数 | `int *f(int, int)` |

看两个声明：

```c
int *f(int);
int (*f)(int);
```

它们只差一对括号。C 语法就是这么节俭，节俭到近乎没有同情心。

### 1. `int *f(int)`

```c
int *f(int);
```

这是一个函数声明。

读法是：

```text
f 是一个函数；
它接收一个 int；
它返回 int *。
```

所以它是指针函数，也就是返回指针的函数。

例子：

```c
int global_value = 10;

int *get_value(void) {
    return &global_value;
}

int *p = get_value();
```

`get_value` 是函数，不是指针。只是它的返回值类型是 `int *`。

### 2. `int (*f)(int)`

```c
int (*f)(int);
```

这是函数指针声明。

读法是：

```text
f 是一个指针；
它指向一个函数；
这个函数接收一个 int；
返回 int。
```

为什么括号这么关键？因为函数调用运算符 `()` 的优先级高于一元 `*`。

如果没有括号：

```c
int *f(int);
```

`f` 会先和 `(int)` 结合，于是 `f` 先成为函数，返回值再是 `int *`。

如果有括号：

```c
int (*f)(int);
```

`*f` 被括号包起来，说明 `f` 先是指针，然后这个指针指向函数。

括号不是装饰。它是类型的分界线。

## 四、复杂声明怎么读

读 C 声明时，可以使用一个实用规则：

```text
从标识符开始，优先向右看，再向左看；遇到括号先处理括号。
```

比如：

```c
int (*fp)(int, int);
```

从 `fp` 开始：

```text
fp
(*fp)          fp 是一个指针
(*fp)(...)    这个指针指向函数
int           函数返回 int
```

所以：

```text
fp 是一个指向函数的指针，该函数接收两个 int，返回 int。
```

再看函数指针数组：

```c
int (*ops[4])(int, int);
```

从 `ops` 开始：

```text
ops[4]          ops 是长度为 4 的数组
*ops[4]         数组元素是指针
(*ops[4])(...)  指针指向函数
int             函数返回 int
```

所以：

```text
ops 是一个数组，数组元素是函数指针；
这些函数都接收两个 int，返回 int。
```

常见声明可以放在一张表里：

| 声明 | 含义 |
| --- | --- |
| `int f(int)` | `f` 是函数，接收 `int`，返回 `int` |
| `int *f(int)` | `f` 是函数，接收 `int`，返回 `int *` |
| `int (*fp)(int)` | `fp` 是函数指针，指向接收 `int`、返回 `int` 的函数 |
| `int (*arr[4])(int)` | `arr` 是数组，数组元素是函数指针 |
| `int *(*fp)(int)` | `fp` 是函数指针，指向接收 `int`、返回 `int *` 的函数 |

## 五、函数指针的赋值和调用

定义两个函数：

```c
int add(int a, int b) {
    return a + b;
}

int sub(int a, int b) {
    return a - b;
}
```

声明一个函数指针：

```c
int (*op)(int, int);
```

赋值：

```c
op = add;
```

调用：

```c
int x = op(3, 4);
```

也可以写成：

```c
int y = (*op)(3, 4);
```

这两种调用都成立。工程里更常见的是：

```c
op(3, 4);
```

因为它更简洁，也更像普通函数调用。

函数指针可以重新指向另一个同类型函数：

```c
op = sub;
int z = op(3, 4);
```

这正是函数指针有用的地方：调用位置不变，具体行为可以改变。

## 六、函数指针类型必须匹配

函数指针保存的不只是“一个函数地址”，还带着函数签名。

```c
int (*fp1)(int, int);
void (*fp2)(void);
char *(*fp3)(const char *);
```

这些是不同类型。

如果把签名不匹配的函数塞进函数指针，再通过它调用，可能产生未定义行为。

例如：

```c
int add(int a, int b) {
    return a + b;
}

void (*bad)(void);

/* 不要这样做 */
bad = (void (*)(void))add;
bad();
```

调用约定依赖参数和返回值类型。调用者以为没有参数，被调用者却按两个 `int` 去取参数，机器不会替你补一份体面。结果能运行只是偶然，不是契约。

还要注意：函数指针不是普通对象指针。

```c
int x = 10;
void *p = &x;
```

对象指针和 `void *` 的互转是 C 里常见用法。但标准 C 不保证函数指针可以安全转换成 `void *` 再转回来。

很多平台上看起来可以，但底层代码不应该把它当成理所当然。函数指针就按函数指针处理，不要随手塞进 `void *`。

## 七、用 `typedef` 简化函数指针

函数指针声明写多了会变得很不友好。

```c
int (*op)(int, int);
int (*ops[4])(int, int);
int apply(int x, int y, int (*op)(int, int));
```

可以用 `typedef` 简化：

```c
typedef int (*binary_op)(int, int);
```

这表示：

```text
binary_op 是一个类型别名；
它代表“指向函数的指针，该函数接收两个 int，返回 int”。
```

于是可以写：

```c
binary_op op;
binary_op ops[4];
int apply(int x, int y, binary_op op);
```

完整例子：

```c
typedef int (*binary_op)(int, int);

int add(int a, int b) {
    return a + b;
}

int sub(int a, int b) {
    return a - b;
}

int apply(int x, int y, binary_op op) {
    return op(x, y);
}

int main(void) {
    int a = apply(3, 4, add);
    int b = apply(3, 4, sub);

    return 0;
}
```

`typedef` 的写法容易让人误会：

```c
typedef int (*binary_op)(int, int);
```

它不是给 `int` 起别名，也不是给某个函数起别名，而是给整个函数指针类型起别名。

可以把它和变量声明对照：

```c
int (*fp)(int, int);
typedef int (*binary_op)(int, int);
```

第一行里 `fp` 是变量名。

第二行里 `binary_op` 是类型名。

C 的 `typedef` 语法就是这样：先写出一个变量声明的形状，再把里面的名字变成类型别名。它不难，只是第一次见时显得很有距离感。

## 八、函数指针作为参数：回调

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

`apply` 不关心具体是加法还是乘法。它只要求传进来的函数满足这个类型：

```c
int (*)(int, int)
```

也就是：

```text
接收两个 int，返回 int。
```

这就是 C 里常见的“把行为参数化”。

### 1. 标准库例子：`qsort`

C 标准库里的 `qsort` 就使用函数指针：

```c
void qsort(
    void *base,
    size_t nmemb,
    size_t size,
    int (*compar)(const void *, const void *)
);
```

最后一个参数 `compar` 是比较函数指针。

排序 `int` 数组可以这样写：

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

`qsort` 不知道数组元素的真实类型，也不知道排序规则。它只知道：需要比较两个元素时，调用你传进来的 `compar`。

这是 C 的典型组合方式：`void *` 表示通用数据地址，函数指针表示通用行为。

## 九、函数指针数组：分发表

函数指针数组适合表示：

```text
编号 -> 对应行为
```

比如一个简单计算器：

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

`ops[op](3, 4)` 的意思是：

```text
取出 ops[op] 这个函数指针；
调用它；
传入 3 和 4。
```

这类写法常见于解释器、虚拟机、驱动、中断处理和系统调用分发。不是因为作者想把读者拒之门外，主要是因为它确实适合把编号映射到行为。

## 十、xv6 的系统调用表

xv6 里的系统调用表就是函数指针数组的典型例子：

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
syscalls[]            syscalls 是数组
*syscalls[]           数组元素是指针
(*syscalls[])(void)   指针指向无参数函数
uint64                函数返回 uint64
static                这个数组只在当前源文件内部可见
```

所以完整含义是：

```text
syscalls 是当前源文件内部使用的一张表；
表里的每一项都是函数指针；
这些函数都没有参数，返回 uint64。
```

系统调用号本质上是编号。内核要做的是：

```text
系统调用号 -> 系统调用处理函数
```

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

函数指针数组能把它压成一张表：

```c
if (num > 0 && num < NELEM(syscalls) && syscalls[num]) {
    p->trapframe->a0 = syscalls[num]();
} else {
    p->trapframe->a0 = -1;
}
```

这段逻辑可以翻译成：

```text
检查系统调用号是否合法；
检查表里有没有对应函数；
调用 syscalls[num]()；
把返回值写回用户寄存器保存区。
```

### 1. 指定初始化器

数组初始化里的写法：

```c
[SYS_fork] sys_fork
```

表示把 `sys_fork` 放到数组下标 `SYS_fork` 的位置。

标准 C99 的指定初始化器通常写成：

```c
[SYS_fork] = sys_fork
```

xv6 源码里常见的：

```c
[SYS_fork] sys_fork
```

是 GCC 支持的旧式 GNU 写法。读 xv6 时按源码理解即可；自己写可移植 C 代码时，优先使用带 `=` 的 C99 写法。

### 2. 为什么所有 `sys_xxx` 都是同一签名

xv6 的系统调用函数通常长得像这样：

```c
uint64 sys_write(void);
uint64 sys_read(void);
uint64 sys_fork(void);
```

它们并不直接通过 C 函数参数接收用户传来的参数，而是从当前进程的 trapframe 或参数读取逻辑里取参数。

所以系统调用表可以统一写成：

```c
uint64 (*)(void)
```

一个数组里的所有元素必须是同一种类型。统一签名之后，`sys_read`、`sys_write`、`sys_fork` 才能自然放进同一张表里。

## 十一、C++ 的可调用对象

C++ 保留了 C 风格函数指针，但又扩展出一组更大的概念：可调用对象。

能写成 `obj(args...)` 或能通过调用语义执行的东西，通常都可以放进这个范畴：

| 形式 | 例子 | 是否能保存状态 |
| --- | --- | --- |
| 普通函数 | `int add(int, int)` | 否 |
| 函数指针 | `int (*)(int, int)` | 否 |
| 成员函数指针 | `int (T::*)(int)` | 依赖对象 |
| 函数对象 | 重载 `operator()` 的对象 | 是 |
| Lambda | `[](int x) { return x + 1; }` | 捕获时可以 |
| `std::function` | `std::function<int(int)>` | 可以，类型擦除 |

C++ 的问题不再只是“这是不是函数指针”，而是：

```text
这个东西能不能被调用？
调用时需要什么参数？
返回什么？
是否携带状态？
是否需要类型擦除？
```

这几个问题比死背语法更有用。语法只是外壳，行为才是本体。

## 十二、普通函数指针在 C++ 中仍然可用

C++ 可以直接写 C 风格函数指针：

```cpp
int add(int a, int b) {
    return a + b;
}

int (*fp)(int, int) = add;

int result = fp(3, 4);
```

也可以用 `using` 起别名：

```cpp
using BinaryOp = int (*)(int, int);

BinaryOp op = add;
```

`using` 往往比 C 风格 `typedef` 更直观：

```cpp
typedef int (*BinaryOp1)(int, int);
using BinaryOp2 = int (*)(int, int);
```

两者表达的类型相同。只是 `using` 把“别名 = 原类型”写得更接近人的阅读顺序。

普通函数指针的优点是：

- 很轻量，通常就是一个代码地址。
- 没有动态分配。
- 可以和 C 接口自然交互。
- 适合回调、分发表、底层接口。

缺点也明确：

- 不能直接保存捕获状态。
- 不能指向普通成员函数。
- 类型必须精确匹配。

## 十三、成员函数指针

C++ 的非静态成员函数有一个隐含的 `this` 对象，所以成员函数指针不是普通函数指针。

```cpp
struct Counter {
    int value;

    int add(int x) {
        return value + x;
    }
};

int (Counter::*fp)(int) = &Counter::add;
```

这里 `fp` 的类型是：

```cpp
int (Counter::*)(int)
```

意思是：

```text
指向 Counter 的某个成员函数；
该成员函数接收一个 int；
返回 int。
```

调用时必须绑定对象：

```cpp
Counter c{10};

int result = (c.*fp)(5);
```

如果手里是对象指针：

```cpp
Counter *p = &c;

int result = (p->*fp)(5);
```

静态成员函数没有隐含 `this`，所以可以转成普通函数指针：

```cpp
struct Math {
    static int add(int a, int b) {
        return a + b;
    }
};

int (*fp)(int, int) = &Math::add;
```

非静态成员函数不行，因为它需要对象。

## 十四、函数对象

函数对象，也叫 functor，是重载了 `operator()` 的对象。

```cpp
struct Add {
    int operator()(int a, int b) const {
        return a + b;
    }
};

int main() {
    Add add;
    int result = add(3, 4);
}
```

`add(3, 4)` 看起来像函数调用，但 `add` 是对象。

函数对象的优势是可以保存状态：

```cpp
struct AddBase {
    int base;

    int operator()(int x) const {
        return x + base;
    }
};

int main() {
    AddBase f{10};
    int result = f(5); // 15
}
```

这件事是普通函数指针做不到的。函数指针只有函数入口地址，不携带 `base` 这种运行时状态。

在泛型代码里，函数对象非常常见：

```cpp
template <typename F>
int apply(int x, int y, F f) {
    return f(x, y);
}
```

这里 `F` 可以是普通函数指针，也可以是函数对象，也可以是 Lambda。

## 十五、Lambda

Lambda 是 C++ 里就地定义可调用对象的语法。

```cpp
auto add = [](int a, int b) {
    return a + b;
};

int result = add(3, 4);
```

这段代码定义了一个匿名函数对象。`add` 不是函数指针，而是一个对象。它的类型由编译器生成，名字无法直接写出来，所以通常用 `auto` 接收。

Lambda 的基本结构是：

```cpp
[capture](parameters) -> return_type {
    body
}
```

例如：

```cpp
auto f = [](int x) -> int {
    return x + 1;
};
```

返回类型经常可以省略：

```cpp
auto f = [](int x) {
    return x + 1;
};
```

### 1. 不捕获 Lambda

不捕获外部变量的 Lambda：

```cpp
auto add = [](int a, int b) {
    return a + b;
};
```

它没有额外状态。

不捕获 Lambda 可以转换成普通函数指针：

```cpp
int (*fp)(int, int) = [](int a, int b) {
    return a + b;
};

int result = fp(3, 4);
```

因为它不需要保存任何上下文，编译器可以生成一个普通函数入口。

### 2. 捕获 Lambda

捕获 Lambda 会保存外部状态：

```cpp
int base = 10;

auto add_base = [base](int x) {
    return x + base;
};
```

这个 Lambda 内部保存了一份 `base`。

因此它不能转换成普通函数指针：

```cpp
int base = 10;

/* 错误：捕获 Lambda 不能转换成普通函数指针 */
/* int (*fp)(int) = [base](int x) { return x + base; }; */
```

原因很简单：

```text
函数指针只能保存函数入口地址；
捕获 Lambda 还需要保存状态。
```

一个地址装不下对象状态。语法再怎么努力，也不能违反这个事实。

### 3. 值捕获和引用捕获

值捕获：

```cpp
int base = 10;

auto f = [base](int x) {
    return x + base;
};

base = 20;

int result = f(5); // 15
```

`f` 保存的是创建 Lambda 时的 `base` 值。

引用捕获：

```cpp
int base = 10;

auto f = [&base](int x) {
    return x + base;
};

base = 20;

int result = f(5); // 25
```

`f` 保存的是对 `base` 的引用，所以后续变化会影响调用结果。

引用捕获要注意生命周期：

```cpp
auto make_bad() {
    int base = 10;

    return [&base](int x) {
        return x + base;
    };
}
```

`base` 是局部变量，函数返回后已经失效。返回的 Lambda 里还引用它，就会留下悬垂引用。

正确做法通常是值捕获：

```cpp
auto make_ok() {
    int base = 10;

    return [base](int x) {
        return x + base;
    };
}
```

## 十六、`std::function`

`std::function` 是 C++ 标准库提供的通用可调用对象包装器。

需要头文件：

```cpp
#include <functional>
```

声明方式：

```cpp
std::function<int(int, int)> op;
```

意思是：

```text
op 可以保存任何“接收两个 int，返回 int”的可调用对象。
```

它可以保存普通函数：

```cpp
int add(int a, int b) {
    return a + b;
}

std::function<int(int, int)> op = add;
```

可以保存不捕获 Lambda：

```cpp
std::function<int(int, int)> op = [](int a, int b) {
    return a + b;
};
```

也可以保存捕获 Lambda：

```cpp
int base = 10;

std::function<int(int)> f = [base](int x) {
    return x + base;
};
```

这就是它和普通函数指针的重要区别。

| 形式 | 能否保存捕获状态 | 典型成本 |
| --- | --- | --- |
| 函数指针 | 不能 | 很低 |
| Lambda 对象 | 可以 | 通常很低，可被内联 |
| `std::function` | 可以 | 类型擦除，可能有间接调用和分配 |

`std::function` 的代价来自类型擦除。

它不关心内部保存的具体类型是什么，只保留统一的调用接口：

```cpp
std::function<int(int)> f;
```

这个 `f` 可能保存普通函数，可能保存函数对象，也可能保存捕获 Lambda。调用者不用知道细节。

代价是：编译器更难内联，调用通常多一层间接性；如果保存的对象较大，还可能发生动态内存分配。

所以：

- 需要固定、轻量、C 兼容的回调时，用函数指针。
- 在模板中接收任意可调用对象时，用模板参数。
- 需要把不同类型的可调用对象放进同一种变量、容器或接口里时，用 `std::function`。

## 十七、模板参数接收可调用对象

很多时候，C++ 并不需要 `std::function`。

如果只是在函数内部调用一次或少数几次，可以用模板：

```cpp
template <typename F>
int apply(int x, int y, F f) {
    return f(x, y);
}

int main() {
    int base = 10;

    int result = apply(3, 4, [base](int a, int b) {
        return a + b + base;
    });
}
```

这里 `F` 会被推导为 Lambda 的真实类型。

优点：

- 不需要类型擦除。
- 通常更容易被内联。
- 可以接收函数指针、函数对象、Lambda。

缺点：

- 模板实现通常要放在头文件里。
- 每种不同可调用对象类型都会实例化一份代码。
- 不能直接作为运行时统一类型放进普通容器。

`std::function` 和模板不是谁取代谁，而是解决不同问题。

## 十八、什么时候用哪一种

可以按需求选择：

| 需求 | 推荐表示 |
| --- | --- |
| C 接口回调 | 函数指针 |
| 操作系统分发表 | 函数指针数组 |
| C++ 临时传入一段行为 | Lambda |
| C++ 需要保存状态 | 捕获 Lambda 或函数对象 |
| C++ 泛型算法参数 | 模板参数 |
| C++ 需要统一保存不同 callable | `std::function` |
| 类的非静态成员函数 | 成员函数指针，或 Lambda 绑定对象 |

### 1. C 风格 API

```c
void set_callback(void (*cb)(int));
```

传普通函数：

```c
void on_event(int code) {
}

set_callback(on_event);
```

这种接口简单、稳定、低开销，但没有直接携带上下文的能力。

很多 C API 会额外传一个 `void *userdata`：

```c
typedef void (*callback)(int code, void *userdata);

void set_callback(callback cb, void *userdata);
```

这样函数指针负责行为，`userdata` 负责状态。

### 2. C++ 即用即走

```cpp
std::vector<int> xs = { 3, 1, 4, 2 };

std::sort(xs.begin(), xs.end(), [](int a, int b) {
    return a < b;
});
```

这里 Lambda 最自然。它贴近调用点，读者不用跳到别处找比较函数。

### 3. C++ 保存回调

```cpp
class Button {
public:
    void set_on_click(std::function<void()> cb) {
        on_click_ = std::move(cb);
    }

    void click() {
        if (on_click_) {
            on_click_();
        }
    }

private:
    std::function<void()> on_click_;
};
```

使用：

```cpp
int count = 0;

Button button;

button.set_on_click([&count] {
    ++count;
});
```

这里 `std::function` 的价值是：`Button` 不需要知道回调的具体类型。

## 十九、几种形式的本质差异

### 1. 普通函数

普通函数是编译期存在的命名代码块。

```cpp
int add(int a, int b) {
    return a + b;
}
```

它适合直接调用，也适合被函数指针引用。

### 2. 函数指针

函数指针是运行时变量，保存函数入口地址。

```cpp
int (*fp)(int, int) = add;
```

它适合底层回调和分发表。

### 3. 函数对象和 Lambda

函数对象和捕获 Lambda 可以保存状态。

```cpp
int base = 10;

auto f = [base](int x) {
    return x + base;
};
```

捕获列表决定 Lambda 是否携带状态，也决定它能不能转换成普通函数指针。

### 4. `std::function`

`std::function` 是类型擦除包装器。

```cpp
std::function<int(int)> f = [base](int x) {
    return x + base;
};
```

它牺牲一部分性能和可见性，换来统一存储和接口稳定。

## 二十、常见错误

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

### 2. 用错函数指针签名

错误：

```c
int f(int);
int (*fp)(int, int) = (int (*)(int, int))f;
```

这不是“让类型适配”，只是把编译器的提醒堵住了。通过错误签名调用函数可能产生未定义行为。

### 3. 以为捕获 Lambda 是函数指针

错误：

```cpp
int base = 10;

int (*fp)(int) = [base](int x) {
    return x + base;
};
```

捕获 Lambda 有状态，不能转换成普通函数指针。

### 4. 返回引用捕获了局部变量的 Lambda

错误：

```cpp
auto make_adder() {
    int base = 10;

    return [&base](int x) {
        return x + base;
    };
}
```

`base` 生命周期结束后，Lambda 里的引用就悬空了。

### 5. 不必要地使用 `std::function`

如果只是模板算法里的参数：

```cpp
template <typename F>
void visit(F f) {
    f();
}
```

通常不需要改成：

```cpp
void visit(std::function<void()> f);
```

后者更统一，但也更重。抽象不是越厚越高级。它只是在合适的时候有用，不合适的时候就只是负担。

## 二十一、一页速查

### 1. C 函数指针

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

### 2. 函数指针数组

```c
int (*ops[])(int, int) = {
    add,
    sub,
    mul,
};
```

调用：

```c
int result = ops[index](3, 4);
```

### 3. 指针函数

```c
int *f(int);
```

含义：

```text
f 是函数，接收 int，返回 int *。
```

### 4. C++ Lambda

```cpp
auto f = [base](int x) {
    return x + base;
};
```

含义：

```text
f 是一个可调用对象，它保存了 base 的值。
```

### 5. `std::function`

```cpp
std::function<int(int)> f;
```

含义：

```text
f 可以保存任何接收 int、返回 int 的可调用对象。
```

## 二十二、总结

C 里表示函数，重点是函数名和函数指针。

```c
int (*fp)(int, int);
```

这表示：

```text
一个变量，保存“接收两个 int，返回 int”的函数地址。
```

C++ 里表示函数，范围更大。普通函数、函数指针、成员函数指针、函数对象、Lambda、`std::function` 都可以参与“调用”这件事。

可以用一句话区分它们：

```text
函数指针保存入口地址；
函数对象和捕获 Lambda 可以保存状态；
std::function 用统一类型包装不同的可调用对象。
```

读 C 系统代码时，看到：

```c
static uint64 (*syscalls[])(void)
```

就把它翻译成：

```text
syscalls 是一张系统调用处理函数表。
```

写 C++ 代码时，看到：

```cpp
auto f = [state](int x) { return x + state; };
```

就把它理解成：

```text
编译器生成了一个能被调用的对象，这个对象内部保存了 state。
```

再看到：

```cpp
std::function<int(int)> f;
```

就知道它是在说：

```text
我不关心具体是哪种 callable，只要求它能用 int 调用并返回 int。
```

把这些表示方式分清楚以后，函数就不只是“写在那里然后调用”的语法单位了。它可以被保存、传递、选择、包装，也可以变成对象的一部分。C 和 C++ 在这里的风格差异很明显：C 直接、克制，几乎贴着机器；C++ 丰富、灵活，但也要求你知道自己究竟在买哪一种抽象。否则语法不会拦着你，它只会在事后安静地把账单递过来。
