+++
date = '2026-09-01T17:00:00+08:00'
draft = false
title = 'C 与 C++ 中的 char 数组、字节数组与 string：关系、转换和边界'
+++

`char` 数组、字节数组和 `std::string` 常常装着同样的一串数据，于是很容易被当成同一种东西。这个印象只对了一半：它们都能承载若干个字节，但**是否有长度、能否包含 `\0`、是否拥有数据、每个元素表达什么含义**，并不相同。把这些边界省略，得到的通常不是简洁代码，而是某次恰好没有暴露的越界读取。

先给结论：

- `char[]` 是固定长度的数组；只有包含结束零字节的那一种用法，才是 **C 字符串**。
- 字节数组通常用 `unsigned char[]`、`std::byte[]` 或 `std::vector<std::byte>` 表达；它表达的是原始数据，不自动带“文本”的含义。
- `std::string` 是 C++ 的**拥有型、带长度、连续存储**的 `char` 序列。它可以保存文本，也可以保存任意字节，包括中间的 `\0`。
- 在“二进制数据”场景中，转换时必须同时传递**指针和显式长度**；只传 `const char*` 就是在要求代码碰运气地寻找第一个零字节。

```text
char[] / unsigned char[] / std::byte[]  -> 原始连续存储，长度由数组边界或外部变量决定
以 '\0' 结束的 char[] / const char*   -> C 字符串，长度由第一个 '\0' 决定
std::string                             -> 自己保存长度的连续 char 序列，可含 '\0'
```

## 一、先区分四个容易混在一起的概念

### 1. `char`、字符与字节不是同义词

在 C 和 C++ 中，一个 `char` 对象恰好占一个语言定义的**字节**；`sizeof(char)` 永远是 `1`。但这不保证一个字节一定是 8 位。其位数由 `CHAR_BIT` 给出，在绝大多数现代平台上是 `8`，而语言层面不应把它当成无条件事实。

`char` 既是一种小整数类型，也常用于保存字符和文本编码单元。它是否默认有符号由实现决定：同一份 `char` 代码在不同编译器或目标平台上，`char` 的取值范围可能不同。因此，当数据的含义是 `0` 到 `255` 的原始数值时，`char` 并不是最清楚的选择。

```cpp
#include <climits>

static_assert(sizeof(char) == 1);
// CHAR_BIT 在常见平台为 8，但标准并未要求它只能是 8。
```

“字符”则是更上层的概念。`'A'` 这样的字符字面量、UTF-8 中的一个编码单元、用户看见的一个汉字或 emoji，并不必然是一一对应的关系。尤其是 UTF-8 中，一个可见字符常由多个 `char` 组成。请不要把“数组长度”草率地解释成“字符个数”。

### 2. `char[]`：数组，不天然是字符串

下面两个数组的元素数都为 `5`，但只有第一个能作为 C 字符串使用：

```cpp
char name[] = "yuki";                    // {'y', 'u', 'k', 'i', '\0'}
char raw[5] = {'y', 'u', 'k', 'i', '!'}; // 没有 '\0'
```

`name` 的初始化器来自字符串字面量，编译器自动补上结束零字节 `\0`；`raw` 则是五个普通字节。对 `raw` 调用 `std::strlen(raw)`、`std::cout << raw` 或 `std::string(raw)` 都会继续向数组边界外寻找 `\0`，行为未定义。代码没有因为元素类型都是 `char` 就获得任何额外保护，遗憾但合理。

若缓冲区预留给 C 字符串，常见且可靠的起点是零初始化：

```cpp
char buffer[64]{}; // 全部置零，当前是空 C 字符串，可容纳至多 63 个非零字符
```

之后写入时仍须留下一个位置给结束符，并确保调用的 C API 实际写入它。很多“缓冲区大小够了”的 bug，遗漏的恰好就是这一格。

### 3. C 字符串：一种约定，而不是一种容器

**C 字符串**（C string）是以第一个 `\0` 为结束标记的 `char` 序列，通常经由 `char*` 或 `const char*` 传递。它没有独立保存长度：`strlen`、`strcpy`、`printf("%s", p)` 等函数只能从起始地址逐字节扫描，直到发现零字节。

```cpp
const char* title = "C string"; // 指向只读字符串字面量
char editable[] = "C string";   // 另建可修改的数组副本
```

在 C++ 中，字符串字面量不可修改；不要把它转为 `char*` 再写入。`const char*` 也不表示“必然以 `\0` 结束”，它只表示“指向 const char 的地址”。是否是 C 字符串完全取决于调用方的协议。

### 4. 字节数组：强调原始数据而非文本

“字节数组”不是 C++ 的一个固定语法，常见表示有：

```cpp
#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

unsigned char legacy_packet[] = {0x01, 0x00, 0xFF};
std::array<std::byte, 3> packet = {
    std::byte{0x01}, std::byte{0x00}, std::byte{0xFF}
};
std::vector<std::byte> dynamic_packet;
```

- `unsigned char` 是传统 C/C++ 处理原始字节时最常见的类型；它的数值范围至少能覆盖一个字节的所有位模式。
- C++17 的 `std::byte` 专门表示原始字节，不支持普通整数算术，因而更能提醒读者“这不是拿来做字符或数值运算的”。位运算可用，转换数值时使用 `std::to_integer`。
- `std::uint8_t` 很常见，但它是可选类型：只有平台存在恰好 8 位、无填充位的无符号整数类型时才提供。它在常见平台往往是 `unsigned char` 的别名，却不应把“存在且等同”当作跨平台语言保证。

字节数据可以包含 `0x00`，而且 `0x00` 往往非常普通，例如整数的高位、二进制协议字段或压缩数据的一部分。因此它不应交给只认结束零字节的 C 字符串函数处理。

## 二、`std::string` 究竟保存了什么

`std::string` 是 `std::basic_string<char>` 的别名。它管理自己的动态存储，保存元素数 `size()`，支持追加、替换、查找等操作；其字符序列连续存储，可通过 `data()` 取得首元素地址。

```cpp
#include <string>

std::string text = "hello";
std::string payload{"A\0B", 3};

// text.size() == 5
// payload.size() == 3，而不是 1
```

第二个构造函数明确传入长度，所以三个元素 `A`、`\0`、`B` 都属于字符串。也就是说，`std::string` **并不因为名为 string 就拒绝二进制数据**。从存储角度，它完全能承载任意 `char` 位模式；从接口设计角度，若变量表示网络包、哈希摘要或文件块，使用 `std::vector<std::byte>` 往往更诚实，也更不易被后来的人误传给文本 API。

标准库保证 `std::string` 的字符序列连续，并提供一个以零字符结尾的 C 风格视图：

```cpp
const char* c_text = text.c_str();
// c_text[0..text.size()-1] 是字符串内容；c_text[text.size()] 为 '\0'。
```

这个额外的 `\0` 用来和 C 接口互操作，**不是** `size()` 的一部分。对含内嵌零字节的 `payload` 调用 `payload.c_str()` 后，C API 仍通常只会看见 `A`；它不知道 `std::string::size()`，自然也无法猜到后面还有数据。

`c_str()`、`data()` 或迭代器取得的指针/引用在字符串被修改、重分配、销毁，或调用某些非 `const` 成员函数后都可能失效。若 C API 保存了该指针供稍后使用，不能把临时字符串的 `c_str()` 交给它；必须让 `std::string` 在整个使用期内保持存活且不发生导致失效的修改。

从 C++17 起，非 `const std::string` 的 `data()` 返回 `char*`，可修改 `[0, size())` 中的现有元素：

```cpp
std::string word = "cat";
word.data()[0] = 'C'; // 合法，word 变为 "Cat"
```

这不授权你写入 `data()[size()]` 的结束零字节，也不意味着可以越过 `size()` 当作任意容量的缓冲区使用。需要让 C API 填充数据时，应先 `resize` 到明确长度，再根据 API 实际写入量缩回大小；不要把 `capacity()` 当成可随意写入的元素数量。

## 三、三者的关系速查

| 表示 | 长度从哪里来 | 可否含中间 `\0` | 是否自动以 `\0` 结束 | 典型用途 |
| --- | --- | --- | --- | --- |
| `char[N]` | 编译期数组边界 | 可以 | 不保证 | 固定缓冲区、C API 缓冲区 |
| `char*` / `const char*` | 指针本身没有长度 | 指向的数据可以 | 不保证 | 借用一段字符存储 |
| C 字符串 | 扫描到首个 `\0` | 不能表达其后的内容 | 是，按约定 | C 文本 API |
| `unsigned char[N]` | 编译期数组边界 | 可以 | 不适用 | C 风格原始字节 |
| `std::byte` 序列 | `size()` 或容器边界 | 可以 | 不适用 | 二进制协议、内存表示 |
| `std::string` | `size()` | 可以 | 为 C 互操作提供末尾 `\0` | 文本；必要时的字节载体 |

表中的“可含中间 `\0`”是存储能力，不是每个相关函数都能正确处理它。`std::string` 可以保存，`std::string::size()` 也能报告真实长度；但把它交给 `strlen` 就重新回到了 C 字符串规则。

## 四、`char` 数组与 `std::string` 的相互转换

### 1. 已确认是 C 字符串的 `char[]` 或 `const char*`

若数据保证有结束符、并且其中不含需要保留的中间零字节，直接构造即可：

```cpp
#include <string>

char name[] = "yukino";
std::string first(name);

const char* label = "service";
std::string second(label);
```

这两个构造都等价于先按 C 字符串规则求长度，再复制该长度的元素；结束符不进入 `std::string` 的逻辑内容。前提是指针非空且指向一个有效的、以 `\0` 结束的序列。对 `nullptr` 构造 `std::string` 不是“得到空字符串”，而是违反前提。

### 2. 数组或缓冲区有明确长度

这才是处理通用数据的默认方式：使用“指针 + 长度”的构造函数。

```cpp
#include <string>

char raw[] = {'A', '\0', 'B', '!'};
std::string payload(raw, sizeof raw);

// payload.size() == 4，内嵌 '\0' 被保留
```

如果数组确实由字符串字面量初始化，却希望把数组末尾的结束符也作为普通数据复制，可以同样使用 `sizeof`；通常文本并不需要这样做：

```cpp
char greeting[] = "hi"; // {'h', 'i', '\0'}

std::string text(greeting);                  // "hi"，大小为 2
std::string including_nul(greeting, sizeof greeting); // 大小为 3
```

后一种字符串最后一个元素是零字节。除非目标协议明确要求，保留它只会制造多余数据，别为了“数组本来就有”而复制它。

### 3. `std::string` 转为 `char*` / C 字符串视图

当 C API 只读取以零结束的文本时，传 `c_str()`：

```cpp
#include <cstdio>
#include <string>

std::string path = "config.ini";
std::FILE* file = std::fopen(path.c_str(), "r");
```

若 API 只读“地址和长度”，传 `data()` 与 `size()`，它适用于内嵌零字节：

```cpp
void send_bytes(const void* data, std::size_t length);

std::string packet{"A\0B", 3};
send_bytes(packet.data(), packet.size());
```

若旧 C API 的参数是 `char*` 且它会修改内容，不要对 `c_str()` 使用 `const_cast`。应确认 API 的实际协议：若它只是在缺少 `const` 的旧声明下读取，优先修正接口；若它确实要写入，则创建可写数组或在 C++17 及以后对已 `resize` 的 `string::data()` 提供可写区域。

```cpp
#include <algorithm>
#include <string>
#include <vector>

std::string name = "yukino";
std::vector<char> writable(name.begin(), name.end());
writable.push_back('\0'); // 供需要可写 C 字符串的 API 使用

// legacy_mutate(writable.data());
name.assign(writable.data()); // 前提：API 仍保证结果是有效 C 字符串
```

这里使用 `std::vector<char>` 的原因是其存储连续、大小可控，并且可明确补上结束符。若 API 返回实际写入长度，应该用该长度构造或 `assign`，而不是再次依赖 `\0`。

## 五、`std::string` 与字节数组的转换

### 1. 用 `unsigned char` 表达字节

在 C 或需兼容 C 的代码中，`unsigned char` 是实用的字节载体。将 `std::string` 的内容复制到字节容器时，应显式按无符号字节解释，避免 `char` 为有符号类型时出现负数：

```cpp
#include <string>
#include <vector>

std::vector<unsigned char> to_unsigned_bytes(const std::string& value) {
    std::vector<unsigned char> bytes;
    bytes.reserve(value.size());

    for (unsigned char ch : value) {
        bytes.push_back(ch);
    }
    return bytes;
}

std::string from_unsigned_bytes(const unsigned char* data, std::size_t length) {
    return std::string(reinterpret_cast<const char*>(data), length);
}
```

范围 `for` 中的 `unsigned char ch : value` 进行的是按元素的数值转换；它适合将每个 `char` 的底层字节值送入无符号容器。反向构造明确传入 `length`，故 `0x00` 不会截断数据。`data` 只能在 `length > 0` 时为空吗？不可以：只要长度非零，调用者必须提供指向至少该长度有效元素的指针；最稳妥的接口是直接接收 `std::span<const unsigned char>`（C++20）或容器引用。

对任意对象的内存表示进行检查或复制时，C++ 允许通过 `char`、`unsigned char` 或 `std::byte` 访问其对象表示；这是一条底层规则，不是把任意 `char*` 转成任意对象指针并解引用的许可证。尤其要避免把 C++ 的规则与 C 混用：C 中 `signed char` 也有更宽松的字符类型别名地位，而 C++ 中用于该目的应优先使用 `char`、`unsigned char` 或 `std::byte`。

### 2. 用 `std::byte` 表达字节

`std::byte` 不会隐式当成整数或字符，转换代码稍长，但意图更准确：

```cpp
#include <cstddef>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

std::vector<std::byte> to_bytes(std::string_view value) {
    std::vector<std::byte> bytes;
    bytes.reserve(value.size());

    for (unsigned char ch : value) {
        bytes.push_back(static_cast<std::byte>(ch));
    }
    return bytes;
}

std::string from_bytes(const std::vector<std::byte>& bytes) {
    std::string value(bytes.size(), '\0');
    if (!bytes.empty()) {
        std::memcpy(value.data(), bytes.data(), bytes.size());
    }
    return value;
}
```

这段 `from_bytes` 要求 C++17，因为非 `const string::data()` 从该版本起返回可写指针。`std::memcpy` 是这里合适的选择：它复制每个字节的对象表示，不会寻找 `\0`，也不需要逐个把可能超过有符号 `char` 范围的数值转换回来。

只是查看字符串的字节视图而不想复制时，C++20 的 `std::span` 和 `std::as_bytes` 更直接：

```cpp
#include <cstddef>
#include <span>
#include <string>

std::string message{"A\0B", 3};
std::span<const char> chars(message.data(), message.size());
std::span<const std::byte> bytes = std::as_bytes(chars);

// bytes.size() == message.size()，没有分配，也不会在 '\0' 处停止
```

这是**非拥有视图**。只要 `message` 被销毁、重分配或发生可能使指针失效的修改，`chars` 和 `bytes` 都不能再使用。视图省去了复制，也把生命周期责任留给了调用方；这不是缺点，只是它没有替你做决定。

### 3. 不要把十六进制文本当成原始字节

下面两者看上去相近，长度却完全不同：

```cpp
std::string hex_text = "4A"; // 两个文本字符：'4'、'A'，大小为 2
unsigned char value = 0x4A;  // 一个数值字节，十进制为 74
```

将字节显示为十六进制、或把十六进制字符串解码成字节，是另一层**编码/解码**工作，不是 `char[]` 与 `string` 的普通复制。网络抓包、哈希摘要和密钥材料中常发生这类混淆；长度从 16 变为 8 并不是转换“自动完成”的事。

## 六、`std::string_view`：带长度的借用视图，不是 C 字符串

`std::string_view`（C++17）通常只保存“起始地址 + 长度”，不复制也不拥有字符。它很适合在 C++ 函数之间只读传递一段文本或 `char` 数据，但它与 `const char*` 的语义完全不同：`data()` **不保证**指向一个以 `\0` 结束的序列。

```cpp
#include <string_view>

void c_api(const char* text); // 只接受 C 字符串

std::string_view part = "hello world";
part.remove_suffix(6);        // 逻辑内容现在是 "hello"，长度为 5

// c_api(part.data());
// 错误：data() 仍指向 "hello world" 的开头，C API 可能读到完整的 "hello world"。
```

需要交给 C 字符串 API 时，创建一个拥有且零结束的副本：

```cpp
#include <string>
#include <string_view>

std::string_view part = "hello world";
part.remove_suffix(6);

std::string temporary(part);
c_api(temporary.c_str());
```

这份 `temporary` 必须在 `c_api` 使用指针的整个期间保持存活。若接口本来就能接收“地址 + 长度”，直接传 `part.data(), part.size()` 才不会多一次分配，也不会把带长度的数据退化回零结束字符串。

同样地，`string_view` 指向的原始 `std::string`、数组或其他存储一旦被销毁、重分配或发生使引用失效的修改，视图就失效。它解决的是不必要复制，不是生命周期问题；后者仍是调用方的责任。

## 七、传给 C API 时，先看它需要哪一种协议

同样是 `const char*`，函数含义可能截然不同。调用前要阅读参数是否伴随长度，而不是看见指针就写 `c_str()`。

| C 风格接口形式 | 它需要的东西 | `std::string` 的正确传法 |
| --- | --- | --- |
| `int open_text(const char* path)` | 以 `\0` 结束的文本 | `path.c_str()`，且路径不能含内嵌零字节 |
| `void hash(const void* p, size_t n)` | 任意 `n` 个字节 | `value.data(), value.size()` |
| `int parse(char* p)` | 可写且以 `\0` 结束的缓冲区 | 可写 `vector<char>` / 明确大小的 `string`，视 API 约定而定 |
| `ssize_t read(int fd, void* p, size_t n)` | 一段可写存储和容量 | 先 `resize(n)`，传 `data()`，再按返回值调整 `size()` |

以 POSIX `read` 一类“返回实际写入量”的接口为例，C++17 可这样组织：

```cpp
#include <string>

// 假设 read_some(fd, buffer, count) 返回写入字节数，失败时另行处理。
std::string receive_text_or_bytes(int fd, std::size_t capacity) {
    std::string result(capacity, '\0');
    std::size_t received = read_some(fd, result.data(), result.size());
    result.resize(received);
    return result;
}
```

真正代码还必须处理错误、短读、返回值类型和 `capacity` 是否超过接口可接受范围。更重要的是：返回的 `result` 可能含 `\0`，它是不是“文本”由协议决定，而不是由容器类型决定。

## 八、文本编码是另一条维度

`std::string` 的元素类型是 `char`，但它**不携带编码元数据**。同一个 `std::string` 既可以存 UTF-8，也可以存 GBK、系统本地编码、ASCII，或者根本不是文本的字节。下面的断言只有在 `utf8` 确实遵循 UTF-8 时才表达“编码单元数”，并不表示三个用户可见字符：

```cpp
std::string utf8 = "雪乃";
// utf8.size() 是 UTF-8 编码后的字节数，不是“汉字个数”。
```

从 C++20 起，UTF-8 字符串字面量 `u8"..."` 的类型涉及 `char8_t`，通常应使用 `std::u8string` 或 `std::u8string_view` 接收。它不能不经处理地当成 `std::string`；两者元素类型不同。若需要与以字节为单位的 API 对接，应根据 API 的契约进行明确的编码边界处理，而不是通过强制转换掩盖类型差异。

```cpp
#include <string>

std::u8string utf8 = u8"雪乃"; // C++20：元素是 char8_t
```

如果需求是“把 Unicode 文本转为某种编码再发送”，那是编码转换问题；如果需求是“原样复制已有 UTF-8 字节”，那才是本章讨论的字节复制问题。名字相似，不代表问题相同。

## 九、常见错误与修正

### 1. 对非 C 字符串调用 `strlen`

```cpp
char data[4] = {'A', '\0', 'B', 'C'};

std::size_t wrong = std::strlen(data); // 得到 1，不是 4
std::size_t right = sizeof data;       // 数组仍在当前作用域时可得 4
```

`strlen` 的结果是“第一个零字节之前的长度”，不是缓冲区长度。数组一旦作为函数参数传递会退化为指针，`sizeof` 也随之不再能得到数组大小；此时应将长度作为独立参数传入，或使用 `std::array`、`std::span`、`std::vector` 等保留范围信息的类型。

### 2. 用只接收 `const char*` 的 `string` 构造函数复制二进制数据

```cpp
const char data[] = {'x', '\0', 'y'};

std::string truncated(data);    // 只有 "x"
std::string complete(data, 3);  // 三个字节都保留
```

当长度已知时，选择带长度的构造函数。这不是“更保险的写法”，而是两种不同的数据协议。

### 3. 认为 `std::string` 的 `size()` 包括结束符

```cpp
std::string value = "abc";
// value.size() == 3；C 互操作用的结束零字节不算作内容。
```

将 `size() + 1` 发送到按长度读取的网络或文件接口，往往会额外发送一个零字节。除非协议明确要求，发送内容就传 `data()` 和 `size()`。

### 4. 用 `reinterpret_cast` 假装完成了安全转换

```cpp
// 不要这样把任意内存当作某个结构体：
// auto* header = reinterpret_cast<const Header*>(bytes.data());
```

指针强制转换不会处理对齐、对象生命周期、字节序、填充字节和协议版本。对于网络或文件格式，应逐字段解码，或使用经过设计的序列化库；对于纯粹的字节复制，使用长度明确的构造、`std::copy` 或 `std::memcpy` 即可。类型转换写得很短，并不使数据格式突然有了定义。

### 5. 把 `char` 的符号性带进字节计算

```cpp
char ch = static_cast<char>(0xFF);
int maybe_negative = ch; // char 为有符号时，结果可能为负

unsigned char byte = static_cast<unsigned char>(ch);
int value = byte;        // 以 0..UCHAR_MAX 的无符号字节值参与计算
```

解析协议长度、校验和、位标志时，优先使用 `unsigned char`、`std::byte` 或更明确的无符号整数类型。文本中的普通 `char` 不应悄悄承担这些数值语义。

## 十、如何选择

可以按数据的真实约束选择，而不是按“哪个写起来更少”选择：

- 固定大小、与 C API 直接交互的文本缓冲区：`char[N]`，并显式维护结束符和容量。
- 固定大小的原始数据：`std::array<std::byte, N>`；若需兼容 C，使用 `unsigned char[N]` 或 `std::array<unsigned char, N>`。
- 长度会变化的原始数据：`std::vector<std::byte>`；兼容旧接口时可选 `std::vector<unsigned char>`。
- C++ 内部的普通文本：`std::string`；借用一段不拥有的文本可用 `std::string_view`，但需负责其指向数据的生命周期。
- UTF-8 编码单元在类型上必须被区分的 C++20 代码：考虑 `std::u8string` / `std::u8string_view`，并在接口边界明确转换策略。

还有一条很实用的判断：如果一个函数需要“地址 + 长度”，参数优先设计为 `std::span<const std::byte>`、`std::span<const char>` 或等价的指针加长度；如果它需要 C 字符串，参数才应是 `const char*`。类型把协议写出来，调用方就不必从函数名里猜测。

## 十一、总结

三者可以互相复制，却不能互相替代：

```text
char 数组       = 固定大小的 char 存储
C 字符串        = 以 '\0' 结束的 char 序列约定
字节数组        = 以原始数据为语义的字节存储
std::string     = 带长度、拥有连续 char 存储的 C++ 容器
```

最后记住四条规则就够了：

- `char[]` 不等于 C 字符串；没有 `\0` 时，不能交给字符串函数。
- `std::string` 能含 `\0`，但 `c_str()` 交给 C 字符串 API 后，后续字节仍会被忽略。
- 二进制转换一律使用“指针 + 长度”或带 `size()` 的范围；不要依赖 `strlen`、`strcpy` 或只收 `const char*` 的构造函数。
- `std::string` 是否是“文本”取决于编码和业务协议；容器不会替你判断，正如编译器也不会替你补上丢失的长度。

把零结束、显式长度和文本编码分成三件事考虑，`char`、字节和 `string` 的关系就不再神秘。它们从来没有复杂到需要猜测，只是不能偷懒地把三种约定叫成同一个名字。
