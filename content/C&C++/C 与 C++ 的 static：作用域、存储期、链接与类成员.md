+++
date = '2026-08-28T10:00:00+08:00'
draft = false
title = 'C 与 C++ 的 static：作用域、存储期、链接与类成员'
+++

`static` 是 C 与 C++ 中最容易被误记成“让变量一直存在”的关键字。这个说法只碰到了它的一部分效果，而且在文件作用域下甚至会把重点带偏。

要理解 `static`，先不要问“它是什么”；先问它**出现在哪里**。它在函数内、文件/命名空间作用域、C++ 类定义中承担的是不同职责。共同点不是某个神秘的“静态属性”，而是声明所处上下文决定了它影响的是存储期、链接属性，还是类成员归属。

```text
块作用域 static          -> 名字局部，对象跨调用保留
文件/命名空间作用域 static -> 当前翻译单元私有（内部链接）
C++ 类成员 static         -> 成员属于类，而不属于每个对象
```

## 一、先分清四个概念

一条声明可能同时涉及多个维度。它们并不是同义词：

| 概念 | 要回答的问题 | 例子 |
| --- | --- | --- |
| 作用域（scope） | 这个名字能在源码的哪些位置直接使用？ | 函数局部、文件、命名空间、类 |
| 存储期（storage duration） | 对象的存储何时取得、何时结束？ | 自动、静态、线程、动态 |
| 链接属性（linkage） | 不同翻译单元中的同名声明能否指向同一实体？ | 无、内部、外部链接 |
| 生命周期/初始化 | 构造或初始化何时发生，销毁何时发生？ | 首次执行、程序启动、线程启动 |

例如：

```cpp
static int cache_count = 0;
```

若它位于 `.cpp` 的命名空间作用域，`cache_count` 有**静态存储期**与**内部链接**：程序期间只有这份对象，但其他翻译单元不能通过同名外部声明链接到它。

而下面的 `call_count` 名字只在函数内可用，也有静态存储期：

```cpp
void record_call() {
    static int call_count = 0;
    ++call_count;
}
```

所以“作用域小”与“对象活得短”没有必然关系。把这两个概念混成一个，接下来的判断几乎必然出错。

## 二、函数内的 `static`：局部名字，长期对象

最常见的局部静态变量如下：

```cpp
int next_id() {
    static int current = 0;
    return ++current;
}

// 依次返回 1、2、3……
```

`current` 的作用域仍是 `next_id()` 函数体；函数外不能直接写它：

```cpp
// current = 10; // 错误：名字不在此处作用域内
```

但它不是自动局部变量。后者每次进入块都会重新创建并初始化：

```cpp
void ordinary() {
    int value = 0; // 每次调用都从 0 开始
    ++value;
}
```

局部 `static` 对象在整个程序生命周期内只存在一份，初始化只发生一次。C++ 中：

```cpp
void initialize_once() {
    static const std::string version = load_version();
    use(version);
}
```

第一次实际执行到声明处时会调用 `load_version()`；后续调用直接复用已初始化的 `version`。这很适合惰性缓存、按需初始化的查找表，以及函数内单例。

### 1. C++11 起的线程安全初始化，只保护初始化

C++11 及以后，多个线程同时首次到达同一个函数局部静态对象的初始化点时，语言保证初始化只会成功完成一次；其他线程不会观察到半初始化的对象。

这条保证不等于“局部静态变量从此线程安全”：

```cpp
int next_id_unsafe() {
    static int current = 0;
    return ++current; // 初始化安全，但并发递增仍有数据竞争
}
```

若初始化后对象仍会被多个线程修改，应使用 `std::atomic`、互斥锁或其他同步机制。C 语言没有 C++11 这项函数局部静态初始化的并发保证；多线程 C 代码应使用平台或库提供的 `once`/锁原语。

### 2. 初始化与销毁顺序

函数局部静态对象的延迟初始化常能避开一部分“全局对象初始化顺序”问题：它在首次真正需要时才构造，而非在 `main()` 前和其他翻译单元的全局对象竞争初始化先后。

不过，它的析构通常发生在程序退出阶段。析构函数再访问其他静态对象时，仍可能遇到销毁先后难以推断的问题。对生命周期必须延续到进程结束的服务对象，工程上有时会有意让它不析构；那是经过权衡的设计选择，不是 `static` 自动替你解决的事。

## 三、文件/命名空间作用域的 `static`：内部链接

在 C 文件的文件作用域，或 C++ 源文件的命名空间作用域，`static` 给对象或函数**内部链接**（internal linkage）：实体只属于当前翻译单元。

```c
/* metrics.c */

static int error_count = 0;

static void record_error(void) {
    ++error_count;
}

void process_request(void) {
    record_error();
}
```

其他 `.c` 或 `.cpp` 文件即使写出：

```c
extern int error_count;
```

也无法链接到 `metrics.c` 的 `error_count`，因为该名字没有对外导出。这里的 `static` 表达的是“实现细节只留在本文件”，而不只是“变量活得更久”。

### 1. 它通常不改变文件作用域对象的寿命

这一点格外容易误解：命名空间/文件作用域对象即使没有写 `static`，本来就具有静态存储期。

```cpp
int public_count = 0;         // 静态存储期，通常为外部链接
static int private_count = 0; // 静态存储期，内部链接
```

两者都在程序期间存在；主要差异是链接可见性。故而，把文件作用域的 `static` 解释为“让变量活得久一些”并不准确。

### 2. C++ 的匿名命名空间

现代 C++ 中，如果目的只是隐藏当前源文件的实现细节，匿名命名空间是同样常见的选择：

```cpp
namespace {

int error_count = 0;

void record_error() {
    ++error_count;
}

} // namespace
```

它也让名称具有内部链接，并能自然地用于变量、函数和类型。C 没有命名空间，所以文件作用域 `static` 仍是 C 中的标准做法。

无论使用哪一种，头文件中都不应随意暴露只服务于单个 `.cpp` 的内部声明。接口越小，依赖和命名冲突越少；这个道理并不需要靠链接器报错后才勉强承认。

## 四、头文件中的 `static`：每个翻译单元一份

下面的头文件看上去像在定义一个共享计数器：

```cpp
// counter.h
static int counter = 0;
```

实际情况恰好相反。每个包含它的翻译单元都会得到一个独立实体：

```text
first.cpp  包含 counter.h  -> first.cpp 自己的 counter
second.cpp 包含 counter.h  -> second.cpp 自己的 counter
```

原因有两层：预处理器先把头文件文本分别复制进各个翻译单元；随后内部链接使这些同名定义不需要也不能彼此合并。这有时是刻意需要的，例如无状态的 `static` 辅助函数，或每个翻译单元独立的常量；但若你期待“全程序唯一的可变状态”，它就是设计错误。

若要共享可变对象，传统方式是头文件 `extern` 声明、某一个源文件定义；C++17 起也可按设计使用 `inline` 变量。`static` 能消除多重定义链接错误，不等于它帮你建立了共享状态——它只是让每个翻译单元悄悄拥有一份状态而已。

## 五、C++ 类中的 `static`：成员属于类，而非对象

### 1. 静态数据成员

```cpp
class RequestStats {
public:
    static int total_requests;

    void record() {
        ++total_requests;
    }
};

int RequestStats::total_requests = 0;
```

`total_requests` 只有一份，所有 `RequestStats` 对象共享；它不在每个对象的内存布局中。

```cpp
RequestStats first;
RequestStats second;

first.record();
second.record();
// RequestStats::total_requests == 2
```

在 C++17 前，类内的 `static int total_requests;` 通常只是声明，仍应在一个 `.cpp` 文件提供定义。C++17 起可写为：

```cpp
class RequestStats {
public:
    inline static int total_requests = 0;
};
```

这里 `inline` 的重点不是请求编译器内联机器指令，而是允许同一个定义出现在多个翻译单元中，并保证它们表示同一个变量。这非常适合头文件中的类定义。

### 2. 静态成员函数没有 `this`

```cpp
class IdGenerator {
public:
    static int next() {
        return ++current;
    }

private:
    inline static int current = 0;
};
```

静态成员函数以 `IdGenerator::next()` 调用，不依赖某个特定对象，因此没有隐式 `this` 指针，不能直接访问非静态成员：

```cpp
class User {
public:
    std::string name;

    static void print_name() {
        // std::cout << name; // 错误：没有具体对象
    }
};
```

它可以访问静态成员、其他静态成员函数，或经由参数接收对象后访问其成员。将它理解为“放在类作用域中、没有对象状态的函数”通常是很好的起点。

## 六、一个仅属于 C 的用法：数组参数中的 `static`

C99 支持在数组参数中使用 `static`：

```c
void sum10(const int values[static 10]);
```

它表示调用者传入的 `values` 至少指向 10 个元素的有效数组区域。这不是创建静态数组，也不是让参数跨调用保存；它是函数参数的最小长度契约。C++ 不支持这种数组参数语法，因此不要把它误当成 C/C++ 共有写法。

## 七、常见误解与选择表

### 1. 局部 `static` 不自动使后续操作线程安全

```cpp
static int request_count = 0;
++request_count; // 多线程下仍有数据竞争
```

局部静态“初始化一次”的保证，和“每次读改写均原子”毫无关系。计数器应使用 `std::atomic<int>` 或锁。

### 2. 不要用头文件 `static` 伪装全局状态

```cpp
// bad_for_shared_state.h
static int global_timeout = 30;
```

它不会共享，反而会每个翻译单元各一份。若要全程序唯一，使用正式声明与定义；若要每个翻译单元独立，也请让命名和注释明确表达这个意图。

| 需求 | 合适的 `static` 用法 | 仍需注意 |
| --- | --- | --- |
| 函数调用间保留局部状态 | 块作用域 `static` | 并发写入仍需同步 |
| 隐藏当前 `.c/.cpp` 的函数或变量 | 文件/命名空间作用域 `static` | C++ 可考虑匿名命名空间 |
| 所有对象共享一份类级状态 | C++ 静态数据成员 | 定义位置、并发与生命周期 |
| 不依赖对象调用类内工具函数 | C++ 静态成员函数 | 没有 `this`，不能直接访问非静态成员 |
| 声明 C 数组参数的最小长度 | `T array[static N]` | 仅 C99+，不是 C++ |

## 八、总结

看到 `static` 时，先定位它的声明上下文：

```text
函数内               -> 名字局部，对象跨调用保存
文件/命名空间作用域   -> 静态存储期不变，链接改为内部链接
C++ 类内             -> 成员归类所有，而非某个实例
C 数组参数           -> 调用者提供最小数组长度的契约
```

这份关键字并不反复无常；是不同上下文向它提出了不同问题。把作用域、存储期、链接和对象归属分别看清之后，`static` 就只是一个边界明确的工具，而不是什么需要靠记忆口诀镇压的语言怪癖。
