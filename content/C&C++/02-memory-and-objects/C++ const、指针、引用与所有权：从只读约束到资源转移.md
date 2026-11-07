+++
date = '2026-11-07T15:30:00+08:00'
draft = false
title = 'C++ const、指针、引用与所有权：从只读约束到资源转移'
+++

在 C++ 中，`const`、指针、引用和 `std::move` 往往同时出现在一个函数签名里：

```cpp
void set_config(const Config* source, std::unique_ptr<Logger> logger);
```

如果只把它们逐个背成语法，读到这里仍然容易失去判断：`source` 能不能为空？能不能修改它？谁负责销毁 `Logger`？调用结束后还能不能用它？真正需要读懂的是接口的**访问权限、可空性和所有权**。

本文建立一套由浅入深的判断方式：先分清 `const` 限制的对象，再理解值、指针与引用如何传递，最后用 RAII 和智能指针表达资源由谁管理。结论先说在前面：**`const` 解决“能否通过这个名字修改”，引用和指针表达“如何访问对象”，所有权则必须由值语义、智能指针或明确的接口约定表达；它们不是同一件事。**

## 一、先分开三个问题

面对一个变量或参数，依次回答下面三个问题，通常就不会把概念混在一起：

1. 这里保存的是对象本身，还是对象的地址？
2. 能否通过这个名字修改对象，或者改变它指向的位置？
3. 这个对象或资源最终由谁负责销毁？

例如：

```cpp
const Widget* view = find_widget();
```

- `view` 是一个保存地址的**指针变量**，不是 `Widget` 对象本身。
- 不能通过 `view` 修改它所指向的 `Widget`，但可以让 `view` 指向另一个 `Widget`，也可以设为 `nullptr`。
- 这行代码没有说明谁拥有 `Widget`。它多半只是一个只读的借用视图，生命周期必须由其他对象保证。

不要因为代码里出现了 `const` 就假定没有人能修改对象，也不要因为拿到了指针就假定自己应该 `delete` 它。这样的推断缺少最关键的所有权信息。

## 二、`const` 限制的是“通过谁修改”

`const` 表示某个对象不能通过当前声明的访问路径被修改。它不等价于“内存中的值永远不会变化”。

```cpp
int score = 80;
const int& read_only_score = score;

// read_only_score = 90;  // 错误：不能经由 const 引用修改
score = 90;               // 合法：原对象本身并不是 const
```

`read_only_score` 给出的是只读视角；如果同时存在可写的 `score`，后者仍可以改变同一个对象。对并发共享数据而言，`const` 也不会自动提供线程安全，仍需要锁、原子操作或其他同步方案。

### `const` 与编译期常量不是一回事

下面两种变量都不能在初始化后被赋值，但只有第二种必然要求在编译期就能求值：

```cpp
int read_port();

const int port = read_port();       // 运行时才得到值
constexpr int retry_limit = 3 + 2;  // 编译期常量表达式
```

`const` 主要是只读约束；`constexpr` 表示该声明可用于要求常量表达式的上下文。很多基本类型的 `const` 对象在满足条件时也可能参与常量表达式，但不要把“写了 `const`”机械理解成“必然在编译期计算”。

### 顶层 `const` 与底层 `const`

概念上可以这样区分：

- **顶层 `const`**：限制变量自身，例如 `int* const p` 中的 `p` 不能改指向。
- **底层 `const`**：限制通过间接访问得到的对象，例如 `const int* p` 中的 `*p` 不能被修改。

这个区分在指针、模板推导和赋值检查中很有用。最直观的地方，还是指针声明。

## 三、常量指针与指针常量：不要猜中文名称

“常量指针”和“指针常量”的中文叫法很像，甚至不同资料对名称的使用并不总是一致。因此最可靠的方法是看 `const` 修饰谁，或采用从标识符向外阅读的方式。

设 `value` 是可修改的 `int`：

```cpp
int value = 10;
int other = 20;
```

| 声明 | `const` 修饰谁 | 能否 `*p = ...` | 能否 `p = ...` | 常见含义 |
| ---- | --------------- | --------------- | -------------- | -------- |
| `const int* p` | 指向的 `int` | 不能 | 能 | 指向常量的指针、只读借用 |
| `int* const p` | 指针变量 `p` | 能 | 不能 | 常量指针、固定指向 |
| `const int* const p` | 指针和指向的 `int` | 不能 | 不能 | 固定的只读访问 |

### 指向常量的指针：`const int* p`

```cpp
const int* p = &value;

// *p = 11;  // 错误：不能通过 p 修改 value
p = &other;  // 合法：p 自身不是 const
```

`int const* p` 与 `const int* p` 完全等价。标准库和多数项目更常使用前一种写法以外的 `const int*`，关键是团队内保持一致。

它适合表达“函数只读取对象，而且参数可以为空”：

```cpp
void print_if_present(const std::string* text) {
    if (text != nullptr) {
        std::cout << *text << '\n';
    }
}
```

### 固定指向的指针：`int* const p`

```cpp
int* const p = &value;
*p = 11;       // 合法：可以改 value
// p = &other; // 错误：p 不能改指向
```

这里的“固定”只约束本地变量 `p`。它不意味着 `value` 的地址在程序中永远不能被其他指针保存或修改，也不表达所有权。作为函数按值参数时，顶层 `const` 对调用者几乎没有可观察差别：指针值本来就是复制进函数的。它更常用于函数内部确保某个指针不会被意外重新赋值。

### 两者都不能改：`const int* const p`

```cpp
const int* const p = &value;
// *p = 11;       // 错误
// p = &other;    // 错误
```

记忆口诀可以有，但别让口诀替代阅读：**`*` 左侧的 `const` 约束对象，`*` 右侧的 `const` 约束指针。**

## 四、值、指针与引用：三种访问和传参方式

```cpp
Widget original;

Widget copy = original;     // 值：创建独立对象
Widget* pointer = &original; // 指针：保存地址
Widget& reference = original; // 引用：original 的别名
```

它们在函数参数中通常表达不同契约：

| 参数形式 | 是否复制对象 | 是否可为空 | 是否可修改调用方对象 | 典型语义 |
| -------- | ------------ | ---------- | -------------------- | -------- |
| `T value` | 是，或由右值移动构造 | 否 | 否 | 函数取得一份独立值 |
| `T& value` | 否 | 否 | 是 | 可写借用、输出参数 |
| `const T& value` | 否 | 否 | 否 | 只读借用 |
| `T* value` | 复制的是地址 | 是 | 是 | 可空的可写借用 |
| `const T* value` | 复制的是地址 | 是 | 否 | 可空的只读借用 |

这里的“否”是通常 API 语义：引用应当绑定有效对象。语言层面仍可能通过悬垂引用制造未定义行为，所以引用不是生命周期保险。

### 何时按值传递

当函数需要自己的值，或参数很小且复制成本低时，按值最自然：

```cpp
class User {
public:
    explicit User(std::string name) : name_(std::move(name)) {}

private:
    std::string name_;
};
```

调用者给左值时会复制；给临时值或 `std::move(name)` 时可以移动。构造函数拿到的 `name` 明确由自己拥有，再移动进成员。这通常比为左值和右值各写一个重载更简洁。

### 何时使用引用

```cpp
void normalize(std::string& text);          // 要修改调用者的对象
void log(const std::string& text);          // 只读且避免复制大字符串
```

`T&` 与 `const T&` 都应表达借用，而不是所有权转交。特别是从函数返回引用或保存引用成员时，必须确信被借用对象比引用活得更久：

```cpp
const std::string& broken() {
    std::string local = "temporary";
    return local;  // 错误：返回后 local 已销毁
}
```

需要创建结果时按值返回即可；现代 C++ 通常会执行复制省略，必要时还会移动。

### 右值引用不是所有权类型

`T&&` 能绑定到右值，常用于移动构造、移动赋值和转发，但它本身不表示“唯一所有者”：

```cpp
void consume(std::string&& text) {
    std::string stored = std::move(text);
}
```

具名变量 `text` 在函数体内仍是左值；`std::move(text)` 只是把它转换为可被移动的表达式。是否真正发生资源转移取决于目标类型是否支持移动。`T&&` 同样可能引用一个不由当前函数拥有的对象，所以不能只见到 `&&` 就推断析构责任。

## 五、所有权：谁负责释放资源

所有权是“资源生命周期由谁负责结束”的问题。资源不限于堆内存，还包括文件描述符、互斥锁、数据库连接和 socket。C++ 推荐用 **RAII**（资源获取即初始化）：让拥有资源的对象在构造时取得资源、在析构时自动释放资源。

```cpp
{
    std::ofstream output("report.txt");
    output << "done\n";
} // 离开作用域，ofstream 析构并关闭文件
```

使用者不必在每条可能的返回路径上手工关闭文件；作用域结束就是统一的释放边界。

### 裸指针通常只表示借用

现代 C++ 中，`T*` 最好默认理解为“可能为空的非拥有访问”，`T&` 是“不可为空的非拥有访问”。它们不自动销毁所指对象：

```cpp
void render(const Image* image); // 读取借用，image 可以为 nullptr
void resize(Image& image);       // 可写借用，image 必须存在
```

除非接口文档明确写出“调用者负责 `delete`”或“函数接管释放责任”，不要对一个拿到的裸指针执行 `delete`。裸指针既无法让编译器阻止重复释放，也无法说明它来自 `new`、数组、栈对象还是其他所有者。

### `std::unique_ptr`：独占所有权和显式转移

堆上唯一拥有的对象，应优先使用 `std::unique_ptr`：

```cpp
#include <memory>

auto logger = std::make_unique<Logger>("app.log");
// auto second = logger;            // 错误：不能复制两个所有者
auto next_owner = std::move(logger); // 所有权转给 next_owner
```

移动后，`logger` 不再拥有对象，通常为空；`next_owner` 析构时负责销毁 `Logger`。把 `unique_ptr` 按值传参，是一种很清晰的“调用后由被调方拥有资源”的接口：

```cpp
class Service {
public:
    void set_logger(std::unique_ptr<Logger> logger) {
        logger_ = std::move(logger);
    }

private:
    std::unique_ptr<Logger> logger_;
};

Service service;
service.set_logger(std::make_unique<Logger>("app.log"));
```

调用者若持有具名的 `unique_ptr`，必须明确写出 `std::move`：

```cpp
auto logger = std::make_unique<Logger>("app.log");
service.set_logger(std::move(logger));
// 此后 logger 不再是可用的所有者
```

这不是烦琐，而是让所有权边界在调用点可见。相反，对裸指针写 `std::move(ptr)` 只会移动一个地址数值，**不会**让源指针变空，也不会建立独占所有权。

### `std::shared_ptr` 与 `std::weak_ptr`：确有共享才使用

当多个对象确实需要共同延长同一资源的寿命时，可使用 `std::shared_ptr`：

```cpp
auto document = std::make_shared<Document>();
auto preview = document; // 共享所有权
```

资源会在最后一个 `shared_ptr` 离开时释放。但它有引用计数成本，也容易因循环引用导致对象永远不析构。树中的父子双向关系、观察者关系等“只想看看、并不负责存活”的一侧，通常使用 `std::weak_ptr`：

```cpp
class Child;

class Parent {
    std::shared_ptr<Child> child_;
};

class Child {
    std::weak_ptr<Parent> parent_;
};
```

不要为了“看起来安全”把每个对象都包成 `shared_ptr`。若所有权并不共享，`unique_ptr`、值成员或普通借用参数更准确，也更容易推理。

## 六、把声明读成接口契约

回到开头的例子：

```cpp
void set_config(const Config* source, std::unique_ptr<Logger> logger);
```

现在可以完整解读：

- `source` 是可空的只读借用；函数不应通过它修改 `Config`，也不拥有它，调用期间它必须保持有效。
- `logger` 是按值接收的独占所有权参数；调用者传入临时 `unique_ptr`，或对现有 `unique_ptr` 使用 `std::move`，函数就接管其管理的 `Logger`。
- 函数内部若只想临时使用 `logger`，仍应把它放入成员或让局部 `unique_ptr` 在结束时析构；否则接管资源却不保存它，当然没有意义。

如果 `source` 不允许缺失，应把它改为 `const Config&`；如果函数只观察 logger、不接管它，应写 `const Logger&` 或 `Logger*`，而不是 `unique_ptr`。类型应准确匹配资源关系，而不是作为“高级 C++ 写法”的装饰。

## 七、常见误区

### 1. `const` 对象永远不会变

`const` 只限制当前访问路径。对象若还有其他非常量别名，仍可能被修改；并发场景下也不会因此安全。

### 2. `const T*` 就拥有对象

它只说明不能通过该指针修改 `T`。是否拥有、何时失效完全没有被表达；绝大多数情况下它只是借用。

### 3. 引用一定安全，指针一定危险

引用避免了显式空值检查，但仍可能悬垂。选择指针还是引用应由“是否允许没有对象”决定，不是按危险程度排座次。

### 4. `std::move` 会立即移动一切

`std::move` 本质是值类别转换。目标操作支持移动时，资源才可能被转交；对 `const` 对象通常会退回复制，对裸指针也不会自动处理所有权。

### 5. 用 `shared_ptr` 消除全部生命周期问题

共享所有权只能管理引用计数，不能自动解决循环引用、线程协作语义或业务上的所有者不清。能用值成员或 `unique_ptr` 时，通常不该先选 `shared_ptr`。

## 八、总结

- `const` 表示不能通过当前声明修改对象；它不等于全局不变、线程安全或必然编译期常量。
- `const T*` 是“可改指针指向、不可经指针改对象”；`T* const` 是“不可改指针指向、可改对象”；两者都加 `const` 则两边都不能改。
- 按值传递表达独立值；`T&` 与 `const T&` 表达不可空的可写/只读借用；指针适合表达可空借用。
- 引用、普通指针和右值引用本身不表达所有权。资源由谁销毁，必须从 RAII、值成员、`unique_ptr`、`shared_ptr` 或明确契约中判断。
- 优先用 `std::make_unique` 和 `std::unique_ptr` 管理独占资源；只有真实共享生命周期时再使用 `shared_ptr`，并留意用 `weak_ptr` 打破循环。

当声明既回答了“能否修改”、又回答了“能否为空”、还回答了“谁负责释放”，调用者就不必靠猜测使用接口。C++ 的语法已经足够复杂了，接口契约至少不该再故意含糊。
