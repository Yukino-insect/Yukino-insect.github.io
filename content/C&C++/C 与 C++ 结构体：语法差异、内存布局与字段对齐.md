+++
date = '2026-08-22T20:44:55+08:00'
draft = false
title = 'C 与 C++ 结构体：语法差异、内存布局与字段对齐'
+++

结构体是 C 和 C++ 里都非常基础、也非常容易被低估的东西。

它看起来只是“把几个字段放在一起”，但实际牵涉到类型系统、对象模型、内存布局、字段对齐、ABI、序列化、网络协议、二进制文件格式等一串问题。若只是记住“结构体里可以放变量”，未免太粗糙了。

这篇文章系统整理三件事：

- C 和 C++ 结构体有什么相同点。
- C 和 C++ 结构体有什么不同点。
- 结构体在内存中怎么布局，为什么会出现字段对齐和填充字节。

## 一、结构体解决了什么问题

结构体的核心作用是：**把多个相关的数据组合成一个新的复合类型**。

例如，一个学生有学号、年龄、成绩：

```c
struct Student {
    int id;
    int age;
    double score;
};
```

相比单独维护多个变量：

```c
int id;
int age;
double score;
```

结构体的意义在于：

- 把相关字段组织在同一个对象里。
- 让函数参数更清晰。
- 可以创建数组、指针、链表、树等复杂数据结构。
- 可以表达二进制数据格式或硬件寄存器布局。

例如：

```c
struct Student students[100];
```

这表示有 100 个 `Student` 对象，每个对象内部都有 `id`、`age`、`score` 三个字段。

## 二、C 和 C++ 结构体的相同点

先说共同点。因为 C++ 继承了大量 C 的语法，所以简单结构体在两门语言中看起来很像。

### 1. 都可以定义一组成员字段

C：

```c
struct Point {
    int x;
    int y;
};
```

C++：

```cpp
struct Point {
    int x;
    int y;
};
```

这两个例子在语法上几乎一样，都表示 `Point` 由两个 `int` 成员组成。

### 2. 都可以创建结构体变量

C 中通常这样写：

```c
struct Point p;
p.x = 10;
p.y = 20;
```

C++ 中也可以这样写：

```cpp
Point p;
p.x = 10;
p.y = 20;
```

注意这里已经出现了一个小差异：C 里通常要写 `struct Point`，而 C++ 里可以直接写 `Point`。这个差异后面会展开。

### 3. 都可以通过 `.` 和 `->` 访问成员

当变量本身是结构体对象时，用 `.`：

```c
struct Point p;
p.x = 10;
```

当变量是结构体指针时，用 `->`：

```c
struct Point *ptr = &p;
ptr->x = 20;
```

`ptr->x` 本质上等价于：

```c
(*ptr).x
```

因为 `.` 的优先级比 `*` 高，所以必须写成 `(*ptr).x`，不能写成 `*ptr.x`。

### 4. 都会受到内存布局和对齐规则影响

无论是 C 还是 C++，结构体对象最终都要放在内存里。字段不是简单无缝拼接，编译器经常会在字段之间插入填充字节。

例如：

```c
struct Example {
    char c;
    int i;
};
```

很多平台上 `sizeof(struct Example)` 不是 `1 + 4 = 5`，而是 `8`。

原因不是编译器闲得无聊，而是为了让 `int` 放在适合它访问的地址上。这个问题后文会详细讲。

## 三、C 结构体的特点

C 的结构体主要是纯数据聚合。它偏向“数据组织”，不提供完整的面向对象能力。

### 1. C 中类型名通常要带 `struct`

在 C 里：

```c
struct Student {
    int id;
    int age;
};

struct Student s;
```

这里的完整类型名是 `struct Student`，不能直接写：

```c
Student s; // C 中不合法，除非做了 typedef
```

如果想直接使用 `Student`，通常会配合 `typedef`：

```c
typedef struct Student {
    int id;
    int age;
} Student;

Student s;
```

还有一种常见写法是匿名结构体配合 `typedef`：

```c
typedef struct {
    int id;
    int age;
} Student;
```

这种写法可以直接使用 `Student`，但因为没有结构体标签名，不适合直接写自引用结构体。

比如链表节点更常见的写法是：

```c
typedef struct Node {
    int value;
    struct Node *next;
} Node;
```

在结构体内部，`Node` 这个 typedef 名还没有完全建立，所以自引用指针要写 `struct Node *next`。

### 2. C 结构体不能定义成员函数

C 中结构体内部只能声明数据成员，不能写成员函数：

```c
struct Counter {
    int value;

    void add() { // C 中不合法
        value++;
    }
};
```

C 通常把“数据”和“操作数据的函数”分开写：

```c
struct Counter {
    int value;
};

void counter_add(struct Counter *counter) {
    counter->value++;
}
```

这种风格非常清晰，也很直接。代价是调用者需要显式把对象指针传进去。

### 3. C 结构体没有构造函数和析构函数

C 中创建结构体对象时，不会自动调用构造函数：

```c
struct Student s;
```

如果这是局部变量，里面的字段默认是未初始化的。也就是说，字段值可能是任意内容。

可以手动初始化：

```c
struct Student s = {1, 18};
```

也可以写初始化函数：

```c
void student_init(struct Student *student, int id, int age) {
    student->id = id;
    student->age = age;
}
```

C 也没有析构函数。如果结构体内部持有动态内存、文件句柄、socket 等资源，需要手动释放：

```c
struct Buffer {
    char *data;
    int size;
};

void buffer_destroy(struct Buffer *buffer) {
    free(buffer->data);
    buffer->data = NULL;
    buffer->size = 0;
}
```

这就是 C 的风格：权力交给你，责任也交给你。听起来很公平，实际写错时也很公平。

### 4. C 支持位域和柔性数组成员

C 结构体可以使用位域：

```c
struct Flags {
    unsigned int readable : 1;
    unsigned int writable : 1;
    unsigned int executable : 1;
};
```

位域常用于压缩标志位、描述硬件寄存器等场景。

C99 还支持柔性数组成员：

```c
struct Packet {
    int length;
    char data[];
};
```

`data` 不占固定大小，通常配合一次性动态分配使用：

```c
struct Packet *packet = malloc(sizeof(struct Packet) + 100);
packet->length = 100;
```

柔性数组成员必须放在结构体最后。C++ 标准中没有 C 风格柔性数组成员，虽然有些编译器会作为扩展支持。写跨语言、跨编译器代码时，不应该依赖它。

## 四、C++ 结构体的特点

C++ 中的 `struct` 已经不只是“数据包”。它本质上和 `class` 很接近，只是默认访问权限不同。

### 1. C++ 中可以直接使用结构体类型名

C++：

```cpp
struct Student {
    int id;
    int age;
};

Student s;
```

在 C++ 中，`Student` 可以直接作为类型名使用，不需要写成 `struct Student`。

当然，写成下面这样也可以：

```cpp
struct Student s;
```

只是 C++ 程序通常不会这么写。

### 2. C++ 结构体可以有成员函数

```cpp
struct Counter {
    int value;

    void add() {
        value++;
    }
};

Counter counter{0};
counter.add();
```

成员函数内部可以直接访问成员字段，因为它隐式接收一个 `this` 指针。

概念上可以粗略理解为：

```cpp
void Counter::add(Counter *this) {
    this->value++;
}
```

这只是帮助理解，真实语法并不是这样写。

### 3. C++ 结构体可以有构造函数和析构函数

```cpp
struct Student {
    int id;
    int age;

    Student(int id, int age) : id(id), age(age) {
    }
};

Student s(1, 18);
```

如果结构体管理资源，还可以写析构函数：

```cpp
struct FileHolder {
    FILE *file;

    explicit FileHolder(FILE *file) : file(file) {
    }

    ~FileHolder() {
        if (file != nullptr) {
            fclose(file);
        }
    }
};
```

这就是 C++ 常说的 RAII：对象创建时获取资源，对象销毁时释放资源。

### 4. C++ 结构体可以有访问控制

C++ 的结构体可以写 `public`、`private`、`protected`：

```cpp
struct User {
public:
    int id;

private:
    int passwordHash;
};
```

`struct` 的默认访问权限是 `public`：

```cpp
struct A {
    int x; // public
};
```

而 `class` 的默认访问权限是 `private`：

```cpp
class B {
    int x; // private
};
```

所以在 C++ 中，`struct` 和 `class` 的主要语法差别是：

| 关键字 | 默认成员访问权限 | 默认继承访问权限 |
| ------ | ---------------- | ---------------- |
| `struct` | `public` | `public` |
| `class` | `private` | `private` |

除此之外，二者都可以有构造函数、析构函数、成员函数、静态成员、继承、虚函数、模板等能力。

### 5. C++ 结构体可以继承

```cpp
struct Shape {
    virtual double area() const = 0;
    virtual ~Shape() = default;
};

struct Circle : Shape {
    double radius;

    explicit Circle(double radius) : radius(radius) {
    }

    double area() const override {
        return 3.1415926 * radius * radius;
    }
};
```

这已经是完整的面向对象写法了。换句话说，C++ 的 `struct` 不是“低配 class”，而是默认公开的 `class`。

## 五、C 和 C++ 结构体差异总结

可以用一张表收束一下：

| 对比项 | C 结构体 | C++ 结构体 |
| ------ | -------- | ---------- |
| 类型名使用 | 通常要写 `struct Student`，除非 `typedef` | 可以直接写 `Student` |
| 成员函数 | 不支持 | 支持 |
| 构造函数 / 析构函数 | 不支持 | 支持 |
| 访问控制 | 不支持 `public/private/protected` | 支持，默认 `public` |
| 继承 | 不支持 | 支持，默认 `public` 继承 |
| 虚函数 | 不支持 | 支持 |
| 运算符重载 | 不支持 | 支持 |
| 模板 | 不支持 | 支持 |
| 默认成员初始化 | 不支持 | 支持 |
| 柔性数组成员 | C99 支持 | 标准 C++ 不支持 |
| 空结构体 | 标准 C 不允许空结构体 | C++ 允许，大小至少为 1 |

例如 C++ 中可以写：

```cpp
struct Config {
    int port = 8080;
    bool debug = false;
};

Config config;
```

而 C 中不能这样给成员写默认值。

## 六、结构体的内存布局

结构体对象在内存中通常按成员声明顺序排列。编译器会为每个成员选择一个合适的偏移量，让它满足对齐要求。

先看一个简单例子：

```c
struct A {
    int x;
    int y;
};
```

假设 `int` 占 4 字节，并要求按 4 字节对齐，那么布局通常是：

```text
偏移量:  0   1   2   3   4   5   6   7
内容:   x   x   x   x   y   y   y   y
```

所以：

```c
sizeof(struct A) == 8
```

这个例子没有填充字节，因为两个 `int` 都自然满足 4 字节对齐。

### 1. 成员偏移量

结构体中每个成员都有一个相对于结构体起始地址的偏移量。

例如：

```c
struct Point {
    int x;
    int y;
};
```

如果 `Point` 对象的起始地址是 `1000`，并且 `int` 占 4 字节，那么：

```text
p.x 地址 = 1000 + 0
p.y 地址 = 1000 + 4
```

可以用 `offsetof` 查看成员偏移量：

```c
#include <stddef.h>
#include <stdio.h>

struct Point {
    int x;
    int y;
};

int main(void) {
    printf("%zu\n", offsetof(struct Point, x));
    printf("%zu\n", offsetof(struct Point, y));
    printf("%zu\n", sizeof(struct Point));
    return 0;
}
```

在 C++ 中，`offsetof` 主要适用于标准布局类型。如果一个类型有复杂继承、虚函数、不同访问控制区混排等情况，就不要轻率拿它当普通 C 结构体看待。

### 2. 字段并不总是紧挨着

看这个例子：

```c
struct B {
    char c;
    int i;
    short s;
};
```

假设：

- `char` 大小为 1 字节，对齐要求为 1。
- `short` 大小为 2 字节，对齐要求为 2。
- `int` 大小为 4 字节，对齐要求为 4。
- 整个结构体的对齐要求取成员中最大的对齐要求，也就是 4。

布局通常是：

```text
偏移量:  0   1   2   3   4   5   6   7   8   9   10  11
内容:   c   pad pad pad i   i   i   i   s   s   pad pad
```

于是：

```c
sizeof(struct B) == 12
```

为什么不是 `1 + 4 + 2 = 7`？

因为 `i` 是 `int`，通常要求从 4 的倍数地址开始。`c` 占了偏移量 `0`，下一个可用位置是 `1`，但 `1` 不是 4 的倍数，所以编译器在 `c` 后面插入 3 个填充字节，让 `i` 从偏移量 `4` 开始。

`s` 放在偏移量 `8`，满足 2 字节对齐。`s` 占两个字节后到偏移量 `10`。但整个结构体大小还要是结构体对齐要求的整数倍，也就是 4 的整数倍，所以末尾再补 2 个填充字节，最终大小为 12。

### 3. 结构体末尾为什么也要填充

末尾填充常常被忽略，但它很重要。

考虑数组：

```c
struct B arr[2];
```

数组元素必须连续存放：

```text
arr[0] 起始地址
arr[1] 起始地址 = arr[0] 起始地址 + sizeof(struct B)
```

如果 `sizeof(struct B)` 是 10，那么 `arr[1]` 的起始地址可能不是 4 的倍数。这样 `arr[1].i` 就可能无法满足 `int` 的对齐要求。

所以编译器会把结构体总大小补齐到结构体对齐要求的整数倍。这样数组中的每一个元素都能保持正确对齐。

这一点非常关键：**结构体末尾的填充，是为了保证结构体数组里的下一个元素也能正确对齐。**

## 七、什么是字段对齐

字段对齐指的是：某种类型的对象通常需要放在特定倍数的地址上。

常见情况可以粗略理解为：

| 类型 | 常见大小 | 常见对齐要求 |
| ---- | -------- | ------------ |
| `char` | 1 | 1 |
| `short` | 2 | 2 |
| `int` | 4 | 4 |
| `float` | 4 | 4 |
| `double` | 8 | 8 或 4 |
| 指针 | 4 或 8 | 4 或 8 |

这张表只是常见平台上的情况，不是所有平台的绝对真理。具体大小和对齐要求会受到 CPU 架构、操作系统、编译器、ABI、编译选项影响。

可以用下面方式查看：

```c
#include <stdio.h>
#include <stdalign.h>

int main(void) {
    printf("sizeof(int) = %zu\n", sizeof(int));
    printf("alignof(int) = %zu\n", alignof(int));
    printf("sizeof(double) = %zu\n", sizeof(double));
    printf("alignof(double) = %zu\n", alignof(double));
    return 0;
}
```

C++ 中可以使用：

```cpp
#include <iostream>

int main() {
    std::cout << "sizeof(int) = " << sizeof(int) << '\n';
    std::cout << "alignof(int) = " << alignof(int) << '\n';
    std::cout << "sizeof(double) = " << sizeof(double) << '\n';
    std::cout << "alignof(double) = " << alignof(double) << '\n';
}
```

## 八、为什么需要字段对齐

字段对齐不是语法洁癖，而是底层硬件和 ABI 共同塑造出来的规则。

### 1. CPU 访问对齐数据更高效

CPU 从内存读取数据时，通常不是一个字节一个字节随意读取，而是按一定宽度读取。

如果一个 4 字节整数放在 4 字节边界上：

```text
地址:   0   1   2   3   4   5   6   7
内容:   .   .   .   .   i   i   i   i
```

CPU 可能一次内存访问就能读到完整的 `int`。

如果这个 `int` 从偏移量 `3` 开始：

```text
地址:   0   1   2   3   4   5   6   7
内容:   .   .   .   i   i   i   i   .
```

它可能跨过了硬件读取边界，需要两次读取再拼接，性能会变差。

### 2. 某些架构不允许未对齐访问

有些 CPU 架构允许未对齐访问，只是慢一点；有些架构可能直接触发硬件异常。

因此，编译器默认会尽量让成员自然对齐，以保证程序在目标平台上能正确、高效地运行。

### 3. ABI 需要统一布局规则

ABI 可以理解为二进制层面的约定，包括：

- 函数参数如何传递。
- 返回值如何放置。
- 结构体成员如何排列和对齐。
- 不同编译单元之间如何链接。

如果一个库和另一个程序对同一个结构体的布局理解不同，传参和读写字段就会全部错位。那种错误通常不喧哗，只会安静地制造灾难。

所以结构体布局必须遵守目标平台 ABI 的规则。

### 4. 数组元素也要保持对齐

前面已经说过，结构体末尾填充是为了保证数组里的每个元素都对齐。

```c
struct B arr[10];
```

如果 `arr[0]` 对齐了，而 `sizeof(struct B)` 没有按结构体对齐要求补齐，那么 `arr[1]`、`arr[2]` 后续元素就可能逐渐错位。

所以 `sizeof(struct)` 经常比所有成员大小之和更大。

## 九、字段顺序会影响结构体大小

字段顺序不同，结构体大小可能不同。

例如：

```c
struct Bad {
    char c;
    int i;
    short s;
};
```

常见布局：

```text
偏移量:  0   1   2   3   4   5   6   7   8   9   10  11
内容:   c   pad pad pad i   i   i   i   s   s   pad pad
大小:   12 字节
```

如果调整字段顺序：

```c
struct Good {
    int i;
    short s;
    char c;
};
```

常见布局：

```text
偏移量:  0   1   2   3   4   5   6   7
内容:   i   i   i   i   s   s   c   pad
大小:   8 字节
```

只是调整顺序，就可能从 12 字节变成 8 字节。

一般经验是：**把对齐要求大的字段放前面，对齐要求小的字段放后面，通常可以减少填充。**

例如：

```c
struct Better {
    double d;
    int i;
    short s;
    char c;
};
```

不过也不要机械排序。真实工程里还要考虑：

- 字段的逻辑分组。
- ABI 兼容性。
- 是否已经被外部二进制协议使用。
- 是否需要保持和旧版本结构体布局一致。
- CPU 缓存局部性和热点字段位置。

如果一个结构体已经是公开接口的一部分，随便调整字段顺序就是在改二进制契约。这种事最好三思，最好再三思。

## 十、结构体嵌套时如何对齐

结构体里面可以嵌套另一个结构体：

```c
struct Inner {
    char c;
    int i;
};

struct Outer {
    char tag;
    struct Inner inner;
    short s;
};
```

假设 `Inner` 的大小是 8，对齐要求是 4：

```text
struct Inner:

偏移量:  0   1   2   3   4   5   6   7
内容:   c   pad pad pad i   i   i   i
大小:   8 字节，对齐要求 4
```

那么 `Outer` 中的 `inner` 也要从满足 4 字节对齐的位置开始：

```text
struct Outer:

偏移量:  0   1   2   3   4 ... 11  12  13  14  15
内容:   tag pad pad pad inner   s   s   pad pad
大小:   16 字节，对齐要求 4
```

也就是说，嵌套结构体作为成员时，它整体像一个普通字段一样参与对齐。它的对齐要求通常就是它内部成员对齐要求的最大值。

## 十一、位域的内存布局要谨慎

位域可以节省空间：

```c
struct Permission {
    unsigned int read : 1;
    unsigned int write : 1;
    unsigned int exec : 1;
};
```

但是位域布局有不少实现相关细节，例如：

- 位域从低位还是高位开始分配。
- 跨存储单元时如何处理。
- 不同基础类型的位域是否共用同一存储单元。
- 位域整体对齐方式。

所以位域适合在同一编译器、同一平台、同一 ABI 下做内部压缩。若要描述跨平台网络协议或文件格式，直接依赖 C/C++ 位域布局就不太稳妥。

更稳妥的做法是手动使用掩码：

```c
#define PERM_READ  0x01
#define PERM_WRITE 0x02
#define PERM_EXEC  0x04

unsigned char flags = 0;
flags |= PERM_READ;
```

这样二进制含义更明确。

## 十二、结构体和二进制数据

很多人会想把结构体直接写入文件：

```c
fwrite(&student, sizeof student, 1, file);
```

或者从网络接收一段字节后强转成结构体：

```c
struct Header *header = (struct Header *)buffer;
```

这种做法在受控场景里可能能跑，但必须知道它的风险：

- 结构体中可能有填充字节。
- 填充字节的值不一定稳定。
- 不同平台的字节序可能不同。
- 不同编译器的对齐规则可能不同。
- `int`、`long`、指针等类型大小可能不同。
- 强转后的地址可能不满足结构体对齐要求。
- C++ 中复杂对象不能当普通字节块随便读写。

如果是网络协议、磁盘文件格式、跨语言通信，通常应该显式序列化字段，而不是直接依赖结构体内存布局。

例如：

```c
buffer[0] = (unsigned char)(length >> 8);
buffer[1] = (unsigned char)(length & 0xff);
```

或者使用成熟的序列化格式，例如 Protocol Buffers、FlatBuffers、MessagePack、JSON 等。选择哪一种，要看性能、可读性、兼容性和生态，而不是一时兴起。

## 十三、填充字节带来的常见问题

### 1. `memcmp` 比较结构体可能出错

看似可以这样比较两个结构体：

```c
if (memcmp(&a, &b, sizeof a) == 0) {
    // equal
}
```

但如果结构体里有填充字节，填充字节的内容可能不同，即使所有有效字段都相等，`memcmp` 也可能认为不同。

更可靠的方式是逐字段比较：

```c
if (a.id == b.id && a.age == b.age) {
    // equal
}
```

在 C++ 中则可以定义 `operator==`：

```cpp
struct Student {
    int id;
    int age;

    bool operator==(const Student &other) const {
        return id == other.id && age == other.age;
    }
};
```

C++20 以后，很多简单结构体还可以使用默认比较：

```cpp
struct Student {
    int id;
    int age;

    bool operator==(const Student &) const = default;
};
```

### 2. 结构体清零不等于语义初始化

C 中经常看到：

```c
memset(&obj, 0, sizeof obj);
```

对于只包含整数、字符数组等简单字段的结构体，这通常可行。但如果结构体里有指针、浮点数、平台相关句柄，或者在 C++ 中包含非平凡对象，就不能想当然。

C++ 中尤其要谨慎：

```cpp
struct User {
    std::string name;
    int age;
};

User user;
std::memset(&user, 0, sizeof user); // 错误
```

`std::string` 是有内部状态的对象，不能用 `memset` 粗暴清零。C++ 应该依靠构造函数、默认成员初始化或标准库容器自己的初始化规则。

### 3. 直接发送结构体可能破坏兼容性

如果把结构体直接作为网络消息：

```c
send(fd, &message, sizeof message, 0);
```

那么只要结构体字段顺序、编译器、编译选项、平台字节序变化，就可能导致接收端解析错误。

这类问题在“本机测试一切正常，换环境就失效”的场景里很常见。它不神秘，只是你把编译器内部布局当成了公开协议。

## 十四、强制改变对齐：pack 和 alignas

有时确实需要控制结构体布局，例如：

- 解析硬件寄存器。
- 映射某个固定二进制文件头。
- 与已有 C ABI 对接。
- 节省大量结构体数组的内存。

这时可能会看到 `#pragma pack`、`__attribute__((packed))`、`alignas` 等机制。

### 1. `#pragma pack`

在 MSVC 和不少编译器中，可以使用：

```c
#pragma pack(push, 1)

struct PackedHeader {
    char tag;
    int length;
};

#pragma pack(pop)
```

`pack(1)` 表示按 1 字节对齐，编译器会尽量减少填充。这样 `PackedHeader` 可能只占 5 字节。

但是代价也很明显：

- 成员可能未对齐，访问速度下降。
- 某些平台可能不支持未对齐访问。
- 对结构体指针强转后访问成员可能有风险。
- 代码可移植性下降。

所以 `pack` 应该用在边界很清楚的地方，并且范围要尽量小。写了 `push` 就要记得 `pop`，否则后面的结构体布局都会被影响。那就不是“优化”，而是给未来的人布置考试。

### 2. `alignas`

C++ 中可以用 `alignas` 增大对齐要求：

```cpp
struct alignas(64) CacheLineData {
    int value;
};
```

这表示 `CacheLineData` 对象至少按 64 字节对齐。

这种写法常见于性能敏感代码，例如避免多个线程频繁修改的数据落在同一个缓存行里，引发伪共享。

C11 也有 `_Alignas`，C23 中也引入了更接近 C++ 的 `alignas` 写法。不过实际工程中还要看编译器支持情况。

### 3. 不要滥用强制对齐

默认对齐规则已经是编译器和平台 ABI 给出的正常选择。强行压缩或扩大对齐都应该有明确理由。

可以这样判断：

- 如果只是普通业务结构体，不要手动 pack。
- 如果要跨进程、跨语言、跨网络传输，不要直接依赖结构体布局。
- 如果是硬件寄存器、文件头、协议头，先确认规范，再精确控制字段大小、字节序和对齐。
- 如果是性能优化，先测量，再决定是否调整布局。

## 十五、C++ 中的标准布局类型

如果希望 C++ 结构体尽量像 C 结构体一样可预测，应当关注 **standard-layout type**，也就是标准布局类型。

大致来说，一个简单的 C++ 结构体：

```cpp
struct Point {
    int x;
    int y;
};
```

通常是标准布局类型。

但如果加入虚函数、复杂继承、混合访问控制等，类型布局就不再适合按 C 结构体来理解：

```cpp
struct Base {
    virtual void f() {
    }
};

struct Derived : Base {
    int x;
};
```

带虚函数的对象通常会有额外的虚表指针，内存布局和普通结构体不同：

```text
Derived 对象可能类似：

偏移量 0: 虚表指针
偏移量 8: x
```

这只是常见实现上的示意，不是所有编译器都必须一模一样。但结论很明确：一旦进入 C++ 对象模型，结构体就不再只是字段拼接。

如果要把 C++ 类型传给 C 接口，通常应该使用简单的标准布局结构体，并用固定宽度整数类型：

```cpp
#include <cstdint>

struct Header {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t flags;
};
```

必要时还可以用 `static_assert` 检查大小和偏移量：

```cpp
#include <cstddef>
#include <cstdint>

struct Header {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t flags;
};

static_assert(sizeof(Header) == 8);
static_assert(offsetof(Header, magic) == 0);
static_assert(offsetof(Header, version) == 4);
static_assert(offsetof(Header, flags) == 6);
```

这种检查比“我感觉应该是 8 字节”可靠得多。感觉这种东西，在内存布局面前并没有什么尊严。

## 十六、如何估算结构体大小

估算结构体大小可以按这个步骤：

1. 找出每个成员的大小和对齐要求。
2. 从偏移量 0 开始放第一个成员。
3. 放下一个成员前，先看当前偏移量是否满足该成员对齐要求。
4. 如果不满足，就插入填充字节，直到满足。
5. 所有成员放完后，把结构体总大小补齐到结构体自身对齐要求的整数倍。

例如：

```c
struct Demo {
    char a;
    double b;
    int c;
    char d;
};
```

假设：

- `char` 大小 1，对齐 1。
- `int` 大小 4，对齐 4。
- `double` 大小 8，对齐 8。
- 结构体整体对齐要求为 8。

计算过程：

```text
偏移量 0: a，占 1 字节
偏移量 1-7: 填充 7 字节，让 b 从 8 开始
偏移量 8-15: b，占 8 字节
偏移量 16-19: c，占 4 字节
偏移量 20: d，占 1 字节
偏移量 21-23: 末尾填充 3 字节，让总大小成为 8 的倍数
```

所以：

```text
sizeof(struct Demo) == 24
```

如果调整顺序：

```c
struct Demo2 {
    double b;
    int c;
    char a;
    char d;
};
```

布局可能变成：

```text
偏移量 0-7: b，占 8 字节
偏移量 8-11: c，占 4 字节
偏移量 12: a，占 1 字节
偏移量 13: d，占 1 字节
偏移量 14-15: 末尾填充 2 字节
```

于是：

```text
sizeof(struct Demo2) == 16
```

同样的字段，只是顺序不同，大小就从 24 变成 16。

## 十七、结构体使用建议

### 1. 普通业务数据

普通业务数据结构体应该优先考虑可读性：

```cpp
struct UserProfile {
    int id;
    std::string name;
    int age;
};
```

不必为了节省几个字节，把字段顺序改到毫无语义。除非这个结构体会创建几百万个实例，否则可读性通常更重要。

### 2. 大量数组数据

如果结构体会出现在巨大数组里，就要关注大小：

```c
struct Record {
    char type;
    int id;
    short status;
};
```

假设每个对象浪费 4 字节，数组有一千万个元素，就会浪费约 40 MB。这个数量就值得认真调整字段顺序了。

### 3. 二进制接口

如果结构体用于 ABI、文件格式或网络协议，要明确：

- 使用固定宽度类型，例如 `uint32_t`、`uint16_t`。
- 明确字节序。
- 明确对齐和填充。
- 使用 `static_assert` 检查 `sizeof` 和 `offsetof`。
- 不要把含指针、虚函数、`std::string`、`std::vector` 的 C++ 类型直接当二进制格式。

### 4. C 和 C++ 混合编程

如果头文件要同时给 C 和 C++ 使用，常见写法是：

```c
#ifdef __cplusplus
extern "C" {
#endif

typedef struct Student {
    int id;
    int age;
} Student;

void student_print(const Student *student);

#ifdef __cplusplus
}
#endif
```

`extern "C"` 解决的是 C++ 函数名改编问题，不会自动让复杂 C++ 对象变成 C 对象。能暴露给 C 的类型，最好保持简单。

## 十八、总结

C 和 C++ 的结构体有共同基础：都能把多个字段组合成一个复合类型，都可以通过 `.` 和 `->` 访问成员，也都会受到内存布局和字段对齐影响。

但二者的定位不同：

- C 的 `struct` 主要是纯数据聚合。
- C++ 的 `struct` 本质上接近 `class`，只是默认成员和继承是 `public`。
- C++ 结构体可以有成员函数、构造函数、析构函数、访问控制、继承、虚函数、模板等能力。

内存布局方面，要记住几个核心规则：

- 成员通常按声明顺序放置。
- 每个成员要满足自己的对齐要求。
- 编译器可能在成员之间插入填充字节。
- 结构体末尾也可能有填充字节。
- 结构体总大小通常会补齐到结构体自身对齐要求的整数倍。
- 字段顺序会影响结构体大小。
- 二进制协议和文件格式不要轻率依赖结构体原始内存布局。

一句话概括：**结构体是语法上最朴素的复合类型之一，但它的真正边界在类型系统和内存模型里。理解字段对齐和填充之后，`sizeof` 变大就不再奇怪；真正奇怪的，反而是以前我们竟然期待它刚好等于所有字段大小之和。**
