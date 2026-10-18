+++
date = '2026-09-24T20:10:00+08:00'
draft = false
title = 'C++ 引用与 const：参数传递、范围 for 和生命周期'
+++

在 `groupAnagrams` 的函数签名和循环中，`&` 出现了不止一次：

```cpp
vector<vector<string>> groupAnagrams(vector<string>& strs);

for (const string& str : strs) {
    // ...
}
```

它们都表示**引用**，却承担着不同的职责：前者让函数接收调用方的容器本体，后者让循环变量别名化当前元素。引用不是“更安全的指针”这样一句话就能结束的概念；它牵涉是否复制、能否修改、对象寿命以及 API 的所有权边界。

本文先建立值、指针、引用的基本模型，再说明 `const T&` 为什么常见，以及范围 `for` 中到底该写 `auto`、`auto&` 还是 `const auto&`。

## 一、引用是对象的别名

引用在初始化时绑定到一个对象，此后通过引用访问就是访问该对象本身：

```cpp
int score = 80;
int& alias = score;

alias = 95;
// score 现在也是 95
```

与普通变量不同，`alias` 并没有创建第二个 `int`。也不能把它“改绑”到另一个对象：

```cpp
int other = 100;
alias = other;  // 这是把 other 的值赋给 score，不是重新绑定
```

可把三种常见写法先区分开：

```cpp
int value = 10;

int copy = value;   // 新对象，复制值
int& ref = value;   // 引用，value 的别名
int* ptr = &value;  // 指针，保存 value 的地址
```

| 形式 | 是否可为空 | 是否可重新指向 | 访问对象的写法 |
| ---- | ---------- | -------------- | -------------- |
| 值 `T` | 不适用 | 不适用 | `copy` |
| 引用 `T&` | 语言语义中应始终绑定有效对象 | 不能 | `ref` |
| 指针 `T*` | 可以为 `nullptr` | 可以 | `*ptr` |

引用不等于“永远安全”。如果它绑定到寿命已结束的对象，引用仍会悬垂；如果调用者传入不该修改的对象，非 `const` 引用仍可能破坏状态。它表达的是“这里借用一个已有对象”，并不替代生命周期设计。

## 二、函数参数：值、`T&` 和 `const T&`

以字符串为例，三种参数形式代表不同契约：

```cpp
void by_value(std::string name);
void modify(std::string& name);
void inspect(const std::string& name);
```

| 参数形式 | 调用时发生什么 | 函数能否改调用方对象 | 适用场景 |
| -------- | -------------- | -------------------- | -------- |
| `T value` | 构造一个参数对象，通常复制或移动 | 不能 | 函数需要独立拥有值、对象很小 |
| `T& value` | 绑定到调用方对象 | 能 | 输出参数、原地修改 |
| `const T& value` | 只读绑定到调用方对象 | 不能 | 只读的大对象、避免复制 |

分组函数要读取输入，又不应改动输入，因此更准确的签名是：

```cpp
std::vector<std::vector<std::string>> groupAnagrams(
    const std::vector<std::string>& strs
);
```

题目平台常把签名固定成 `vector<string>& strs`，在那种情况下不必为了风格强行改掉接口；但函数体应当像只读函数一样对待 `strs`。在自主设计 API 时，`const T&` 是“借用但不修改”的清楚声明，也让编译器拦住意外写入：

```cpp
void inspect(const std::vector<std::string>& names) {
    // names.push_back("Yukino");  // 错误
}
```

## 三、`const` 修饰谁：从右向左读

引用本身在初始化后不能改绑，所以常见的是“常量对象的引用”：

```cpp
std::string name = "Yukino";
const std::string& view = name;

// view += "!";  // 错误：不能经 view 修改 name
name += "!";     // 合法：name 本身不是 const
```

`const std::string&` 与 `std::string const&` 完全等价。前一种在标准库代码中更常见；选择一种团队约定后保持一致即可。

与指针对照能更好地理解 `const` 的位置：

```cpp
const int* pointer_to_const = &value;  // 不能通过指针改 value
int* const const_pointer = &value;     // 指针不能改指向，仍能改 value
```

引用没有“空引用”和“改指向”的正常语义，所以 `const T&` 只需要关心被引用的对象是否可改。

## 四、范围 `for`：`&` 决定遍历的是元素还是副本

范围 `for` 会依次取出容器元素。循环变量如何声明，决定每轮是否复制，以及能否改写容器：

```cpp
std::vector<std::string> names{"Yukino", "Yui"};

for (std::string name : names) {
    name += "!";  // 改副本，names 不变
}

for (std::string& name : names) {
    name += "!";  // 改原元素
}

for (const std::string& name : names) {
    // 只读取，不复制
}
```

实践中常写为：

```cpp
for (const auto& str : strs) {
    // 只读元素
}

for (auto& value : values) {
    value *= 2;  // 修改元素
}
```

不要因为元素类型小就忽略语义差异。`for (auto item : container)` 明确表示“我需要一份局部副本”；`for (auto& item : container)` 明确表示“我会操作原元素”；`const auto&` 则表示“我只借来看看”。性能只是这种语义选择经常带来的结果，不是唯一理由。

## 五、临时对象为什么能绑定到 `const&`

常量左值引用可以绑定到临时对象，并把这个临时对象的寿命延长到引用所在作用域结束：

```cpp
const std::string& message = std::string("hello");
// 这个临时 string 到 message 离开作用域前都有效
```

这使得 `const T&` 能接收左值和右值：

```cpp
void print(const std::string& text);

std::string name = "Yukino";
print(name);              // 左值
print("Yukino");         // 字符串字面量可构造成临时 std::string
print(name + " Yukino"); // 表达式产生临时对象
```

但“生命周期延长”有明确边界：只对**直接初始化的局部引用**可靠，不能把临时对象的引用从函数中带出去。

```cpp
const std::string& broken() {
    return std::string("temporary");  // 错误：返回后临时对象已销毁
}
```

函数若要生成一个新字符串，应按值返回：

```cpp
std::string make_name() {
    return "Yukino";
}
```

现代 C++ 通常会执行返回值优化或移动构造，不需要为“避免复制”而返回悬垂引用。为了省一次并不一定存在的复制而制造未定义行为，这种交换并不划算。

## 六、不能把引用绑定到会失效的元素

引用、指针和迭代器都可能因为容器操作而失效。`vector` 扩容尤其常见：

```cpp
std::vector<std::string> names{"Yukino"};
std::string& first = names[0];

names.push_back("Yui");  // 若触发扩容，first 可能悬垂
// std::cout << first;    // 未定义行为
```

`reserve` 可以在已知规模时减少重分配机会，但它不是让所有引用永久有效的许诺。若容器可能增长、插入或删除，保存元素下标、重新查找元素，或使用迭代器失效规则更合适的容器，通常比赌引用仍有效可靠。

## 七、回到 `groupAnagrams`

下面这几个 `&` 不应混为一谈：

```cpp
std::vector<std::vector<std::string>> groupAnagrams(
    const std::vector<std::string>& strs
) {
    std::unordered_map<std::string, std::vector<std::string>> groups;

    for (const std::string& str : strs) {
        std::string key = str;
        std::sort(key.begin(), key.end());
        groups[key].push_back(str);
    }
    // ...
}
```

- 参数 `const vector<string>& strs`：借用整个输入序列，不复制，也不修改。
- 循环变量 `const string& str`：借用当前字符串元素，不复制。
- `key` 没有 `&`：它必须是可修改副本，因为 `sort` 会原地重排字符。
- `key.begin()` 和 `key.end()` 返回的是迭代器，不是引用；它们共同描述排序的半开区间。

当你看见 `&` 时，先问“它是声明引用、取地址，还是位与运算符？”在类型声明 `T& x` 中它是引用；在表达式 `&x` 中它才是取地址。仅凭一个符号猜语义，当然会混乱，毕竟 C++ 从不吝于让同一个符号承担几份工作。

## 八、总结

- 引用 `T&` 是对象别名，不会复制对象；修改引用通常就是修改原对象。
- 按值、非常量引用、常量引用分别表达“拥有副本”“原地修改”“只读借用”。
- 只读的大对象参数和遍历元素，通常优先 `const T&` 或 `const auto&`。
- 范围 `for` 中无 `&` 会复制，`&` 才会遍历原元素；是否复制首先是语义选择，其次才是性能选择。
- 引用不会自动解决生命周期问题。不要返回局部对象引用，也不要在会使其失效的容器操作后继续使用元素引用。

引用的作用不是把每个函数签名都压缩得更“高效”。它是在接口上明确对象由谁拥有、函数是否修改它、借用能持续多久。先把这三件事说清楚，`&` 才不是一枚容易误读的装饰符号。
