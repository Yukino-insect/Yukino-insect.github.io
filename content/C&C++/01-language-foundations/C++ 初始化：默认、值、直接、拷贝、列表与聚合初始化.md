+++
date = '2026-10-13T10:00:00+08:00'
draft = false
title = 'C++ 初始化：默认、值、直接、拷贝、列表与聚合初始化'
+++
在下面的层序遍历代码中：

```cpp
res.push_back(std::vector<int>());
```

`std::vector<int>()` 的作用不是“调用了一个神秘的空构造器”，而是构造一个**空的 `std::vector<int>` 对象**，再将它作为参数传给 `push_back`。同一意图在现代 C++ 中更常写成：

```cpp
res.emplace_back();
```

或者：

```cpp
res.push_back({});
```

这几个写法引出了一个很容易被零碎规则淹没的主题：C++ 的“初始化”并不只有一种语法，`=`, `()`, `{}` 也不总是可互换。理解它们时，先区分三件事：对象是否刚刚诞生、初始值来自哪里、类型的构造规则允许哪种形式。否则只背“优先用大括号”之类的口诀，迟早会在 `initializer_list`、窄化转换或默认初始化上踩到边界。

## 一、初始化与赋值不是同一件事

初始化发生在对象创建时；赋值发生在对象已经存在之后。

```cpp
int first = 10;  // 初始化：first 此刻诞生，初始值为 10
first = 20;      // 赋值：给已存在的 first 写入新值
```

对简单的 `int`，效果看起来很像；对不可赋值、只有构造函数的类型，差别就不再能忽略：

```cpp
class Token {
public:
    explicit Token(int value) : value_(value) {}

private:
    int value_;
};

Token token(42);  // 直接初始化，调用构造函数
```

构造函数负责建立对象的初始状态，赋值运算符负责修改一个已经完整存在的对象。尤其在类的成员初始化列表、`const` 成员、引用成员中，初始化是不可替代的；先默认构造再赋值常常更慢，也可能根本无法通过编译。

## 二、内置类型：默认初始化与值初始化的差别

最危险的一组差异来自局部的内置类型：

```cpp
void demo() {
    int uninitialized;  // 默认初始化：值不确定
    int zero{};         // 值初始化：0
    int also_zero = {}; // 列表初始化：0
}
```

`uninitialized` 是自动存储期的局部变量，声明后其值不确定；读取它会导致未定义行为。`int{}` 则进行值初始化，得到 `0`。因此，对没有明确初值的局部标量，写 `int count{};` 是清晰且安全的。

对象的存储期也会影响默认状态：

```cpp
int global_count;  // 静态存储期，零初始化为 0

void demo() {
    static int cached_count;  // 静态存储期，零初始化为 0
    int local_count;          // 自动存储期，不确定
}
```

不要把“全局变量通常是 0”错误推广成“所有未写初值的变量都是 0”。代码是否能侥幸运行不构成语言保证。

## 三、常见初始化语法

### 1. 拷贝初始化：`T value = expression;`

```cpp
int count = 3;
std::string name = "Yukino";
```

这里的“拷贝”是语法分类，不意味着现代编译器一定先创建临时对象再物理复制。编译器可以省略不必要的拷贝或移动；读代码时应关注的是这种形式允许哪些转换和构造函数。

对于 `explicit` 构造函数，拷贝初始化通常不能隐式调用：

```cpp
class UserId {
public:
    explicit UserId(int value) : value_(value) {}

private:
    int value_;
};

UserId first(7);   // 可以：直接初始化
// UserId second = 7;  // 错误：不能使用 explicit 构造函数做隐式转换
UserId third = UserId(7);  // 可以：右侧已显式构造对象
```

`explicit` 的目的正是阻止“任意一个 `int` 都悄悄变成 `UserId`”。当单参数构造代表明确的领域转换时，这个限制通常是有益的。

### 2. 直接初始化：`T value(expression);`

```cpp
std::string name("Yukino");
std::vector<int> values(3, 7);  // 三个值为 7 的元素
```

它直接选择构造函数，可使用 `explicit` 构造函数。`std::vector<int>(3, 7)` 调用的是“数量、元素值”构造函数，结果为 `{7, 7, 7}`。

不过，空的 `T()` 需要小心一个历史语法陷阱：

```cpp
Widget object();  // 这不是对象定义，而是名为 object 的函数声明
```

这被称为 **most vexing parse（最令人烦恼的解析）**。编译器在语法允许时会把它尽量解释为函数声明。若要构造空对象，使用：

```cpp
Widget object{};
Widget object;    // 对类类型：默认初始化
```

### 3. 列表初始化：`T value{...};`

```cpp
int count{3};
std::vector<int> values{3, 7};  // 两个元素：3、7
std::vector<int> empty{};       // 空 vector
```

列表初始化的优势有两个：它避免 most vexing parse，并禁止许多可能丢失信息的窄化转换：

```cpp
int exact{3.14};  // 错误：double 到 int 可能丢失小数部分
int loose = 3.14; // 可以，但值变为 3
```

这种限制并不是为了让代码更难写，而是让风险在编译时暴露。若你确实要截断，应显式说明意图：

```cpp
int truncated = static_cast<int>(3.14);
```

### 4. `auto` 与花括号

`auto` 的推导规则不应只凭直觉猜测：

```cpp
auto first = 1;    // int
auto second{1};    // C++17 起为 int
auto list = {1};   // std::initializer_list<int>
```

尤其 `auto list = {1, 2, 3};` 推导的是 `std::initializer_list<int>`，并不是 `std::vector<int>`。当类型对接口重要时，宁可明确写 `std::vector<int>`；类型推导应减少重复，而不是隐藏容器语义。

## 四、`vector` 的圆括号与花括号为什么结果不同

容器初始化中最常见的误解就是把 `()` 与 `{}` 当作样式选择。它们可能选择完全不同的构造函数：

```cpp
#include <vector>

std::vector<int> a(3, 7);  // {7, 7, 7}：数量为 3，每项为 7
std::vector<int> b{3, 7};  // {3, 7}：initializer_list 中的两个元素
std::vector<int> c(3);     // {0, 0, 0}：三个值初始化的 int
std::vector<int> d{};      // {}：空 vector
```

为什么 `b` 优先得到元素列表？因为标准容器提供接收 `std::initializer_list<T>` 的构造函数，列表初始化会优先考虑这类构造。于是：

```cpp
std::vector<std::string> names{"Alice", "Bob"};
```

自然地表示两个字符串；但 `std::vector<int>{3, 7}` 不能被理解成“3 个 7”，因为它同样完全符合“两个 `int` 元素”的列表构造。

选用规则并不复杂：

- 想按数量构造，写 `vector<T>(count)` 或 `vector<T>(count, value)`。
- 想列出具体元素，写 `vector<T>{first, second, ...}`。
- 想构造空容器，写 `vector<T>{}` 或直接默认构造。

## 五、回到 `vector<int>()`、`push_back` 与 `emplace_back`

考察二维数组：

```cpp
std::vector<std::vector<int>> result;
```

下面三种写法都会在 `result` 的末尾增加一个空的内层 `vector<int>`：

```cpp
result.push_back(std::vector<int>());
result.push_back(std::vector<int>{});
result.emplace_back();
```

它们的语义分别是：

1. 构造一个空临时对象，再传给 `push_back`。
2. 用列表初始化构造一个空临时对象，再传给 `push_back`。
3. 将“没有构造参数”直接交给 `vector<int>` 的构造函数，在目标位置构造元素。

在 C++17 及以后，前两种临时对象通常不会导致额外的实际复制；因此不能把 `emplace_back` 当作不经思考的性能替代。此处推荐它，是因为 `emplace_back()` 最简洁地表达“我要创建一个空的内层容器”。

对于已有对象，`push_back` 更直接：

```cpp
std::vector<std::string> names;
std::string name = "Yukino";
names.push_back(name);  // 放入已有对象
```

对于需要用构造参数新建对象，`emplace_back` 更贴切：

```cpp
struct Point {
    Point(int x, int y) : x(x), y(y) {}
    int x;
    int y;
};

std::vector<Point> points;
points.emplace_back(3, 4);
```

不要机械地把每个 `push_back` 都改成 `emplace_back`。可读性优先：是“添加一个已经有的值”，还是“依据参数原地构造一个值”，两者应由代码意图决定。

## 六、聚合初始化与成员默认初始值

没有用户声明构造函数等条件下，简单结构体可作为聚合类型，用花括号按成员顺序初始化：

```cpp
struct Point {
    int x;
    int y;
};

Point origin{0, 0};
Point right{1, 0};
```

若成员有默认初始值，未在列表中提供的成员会使用它：

```cpp
struct ServerOptions {
    int port = 8080;
    bool enable_tls = false;
};

ServerOptions defaults{};        // port = 8080, enable_tls = false
ServerOptions secure{443, true};
```

聚合初始化很适合简单数据承载对象；若类需要维护不变量、验证输入或隐藏内部表示，应该用构造函数，而不是让调用方按成员位置猜参数。C++20 支持指定初始化器，例如 `Point{.x = 1, .y = 2}`，但它要求编译器标准与项目配置支持，且通常需按成员声明顺序书写；跨版本代码不应不加确认地依赖它。

## 七、类成员必须在成员初始化列表中正确初始化

构造函数体执行前，成员已经先被初始化。下面写法先默认构造 `name_`，再在函数体内赋值：

```cpp
class User {
public:
    User(const std::string& name) {
        name_ = name;
    }

private:
    std::string name_;
};
```

更自然的写法是成员初始化列表：

```cpp
class User {
public:
    explicit User(std::string name) : name_(std::move(name)) {}

private:
    std::string name_;
};
```

这不仅避免一次“默认构造再赋值”，也能初始化 `const` 成员和引用成员：

```cpp
class ConfigView {
public:
    explicit ConfigView(const std::string& name) : name_(name) {}

private:
    const std::string& name_;  // 必须在初始化列表中绑定
};
```

不过，保存引用意味着被引用对象必须活得足够久；构造一个指向临时 `std::string` 的 `ConfigView` 会留下悬空引用。初始化正确不等于生命周期自动正确，二者要分别验证。

成员实际初始化顺序由**成员声明顺序**决定，而不是初始化列表中书写的顺序：

```cpp
class Range {
public:
    Range(int begin, int end) : end_(end), begin_(begin) {}

private:
    int begin_;
    int end_;
};
```

上例实际仍先初始化 `begin_`，再初始化 `end_`。通常应按成员声明顺序编写初始化列表，让代码阅读顺序与实际执行顺序一致，并避免一个成员错误依赖另一个尚未初始化的成员。

## 八、实用选择表

| 目标 | 推荐写法 | 说明 |
| ---- | -------- | ---- |
| 局部标量明确置零 | `int count{};` | 避免未初始化读取 |
| 构造空容器 | `std::vector<int> values{};` | 清晰且无 vexing parse |
| 按数量构造 vector | `std::vector<int> values(n, 0);` | 使用圆括号的数量构造函数 |
| 列出容器元素 | `std::vector<int> values{1, 2, 3};` | 使用 initializer list |
| 调用 `explicit` 构造函数 | `Type value(args);` 或 `Type value{args};` | 不依赖隐式转换 |
| 追加已有对象 | `items.push_back(value);` | 意图是加入一个值 |
| 依据参数追加新对象 | `items.emplace_back(args...);` | 在末尾构造元素 |
| 初始化类成员 | 构造函数成员初始化列表 | 避免先构造再赋值 |

没有一条规则能把所有场景压成“永远用 `{}`”。花括号会阻止窄化，也避免空对象被解析为函数声明，但当类型有 `initializer_list` 构造函数时，它会改变重载选择；`vector<int>(n, value)` 就是最常见的反例。

## 九、总结

- 初始化创建对象的初始状态，赋值修改已经存在的对象；两者不能因为写法相似就混为一谈。
- 自动存储期的内置局部变量默认初始化后值不确定；`T{}` 对标量进行值初始化，通常得到零值。
- `T x = value` 是拷贝初始化，`T x(value)` 是直接初始化，`T x{value}` 是列表初始化；`explicit` 构造函数不能用于隐式的拷贝初始化。
- `{}` 会拒绝许多窄化转换，并避免 `Widget object()` 被解析成函数声明，但也可能优先选择 `initializer_list` 构造函数。
- `vector<int>(3, 7)` 表示三个 7，`vector<int>{3, 7}` 表示元素 3 和 7；圆括号和花括号在容器上绝非单纯风格差异。
- `res.push_back(vector<int>())` 会添加空内层数组，现代 C++ 中 `res.emplace_back()` 更直接地表达原地构造空元素。
- 类成员应优先在成员初始化列表中构造；实际初始化顺序遵循成员声明顺序，引用成员还必须保证被引用对象的生命周期。

初始化语法的意义，是让对象从诞生起就处在明确、合法的状态。只要先想清楚“我要构造几个什么值、是否允许隐式转换、这个类型是否有列表构造函数”，`=`, `()` 和 `{}` 便不再是一堆需要死记的符号，而是不同意图的精确表达。
