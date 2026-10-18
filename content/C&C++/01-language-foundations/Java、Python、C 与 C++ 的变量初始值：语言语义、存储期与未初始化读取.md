+++
date = '2026-08-27T11:30:00+08:00'
draft = false
title = 'Java、Python、C 与 C++ 的变量初始值：语言语义、存储期与未初始化读取'
+++

不同语言里，“变量不写初始值会怎样”确实表现得很不一样：Java 的字段会有默认值，Python 往往报名称或属性不存在，C/C++ 的局部标量则可能带着不确定的内容。

这些现象很容易让人得出一个解释：Java、Python、C/C++ 的内存布局不同，所以变量初始值行为不同。

这个解释抓住了一部分实现背景，却把因果关系倒了过来。更准确的结论是：**变量是否默认初始化、何时允许读取、失败时是编译错误、运行时异常还是未定义行为，首先由语言规范定义；运行时、编译器和内存布局必须实现这些语义。**

内存模型会影响实现成本和设计取舍，但不能反过来替语言规则作担保。即使某次 C++ 调试运行时恰好读到 `0`，也不代表变量被初始化；即使 JVM 常会先把对象内存清零，Java 字段默认值也不是“碰巧清零”的副作用，而是语言保证。

本文比较 Java、Python、C 与 C++ 的相关规则，并澄清几个特别常见的误解。

## 一、先给结论：不要把几种“未赋值”混为一谈

下表中的“未赋值”看起来像同一件事，实际对应不同语言机制。

| 场景 | 不显式初始化时的结果 | 能否直接读取 |
| ---- | -------------------- | ------------ |
| Java 实例字段 | 有默认值 | 可以；基本类型为零值，引用为 `null` |
| Java 静态字段 | 有默认值 | 可以；基本类型为零值，引用为 `null` |
| Java 局部变量 | 没有可用默认值 | 不可以；编译器报“可能尚未初始化” |
| Python 局部名称 | 未绑定 | 不可以；通常抛 `UnboundLocalError` |
| Python 模块名称 | 未绑定 | 不可以；抛 `NameError` |
| Python 对象属性 | 属性不存在 | 不可以；抛 `AttributeError` |
| C 自动存储期标量 | 不确定值（indeterminate value） | 不应读取；可能导致未定义行为 |
| C 静态存储期对象 | 零初始化 | 可以读取 |
| C++ 自动存储期标量 | 不确定值 | 不应读取；常见标准语义下会导致未定义行为或错误行为 |
| C++ 具有构造/成员默认初始化的对象 | 由类型规则决定 | 通常可安全使用，但要看构造函数定义 |

这里已经能看出第一条重要边界：**“字段”“局部变量”“名字”“对象属性”“原始存储”并不是同一个概念。**即使在同一门语言中，它们的初始化规则也可能完全不同。

## 二、Java：字段有默认值，局部变量必须经过确定赋值

关于 Java，最需要修正的一点是：**引用类型字段不赋值并不是未定义行为，它有确定的默认值 `null`。**

```java
class User {
    int age;        // 0
    boolean active; // false
    double score;   // 0.0
    char grade;     // '\u0000'
    String name;    // null
}
```

```java
User user = new User();

System.out.println(user.age);    // 0
System.out.println(user.active); // false
System.out.println(user.name);   // null
```

Java 字段的默认值如下：

| 字段类型 | 默认值 |
| -------- | ------ |
| `byte`、`short`、`int`、`long` | `0` |
| `float`、`double` | `0.0`、`0.0d` |
| `char` | `\u0000` |
| `boolean` | `false` |
| 任意引用类型 | `null` |

### 1. `null` 是确定状态，不是未定义状态

下面的代码可以运行：

```java
class Profile {
    String nickname;
}

Profile profile = new Profile();
System.out.println(profile.nickname == null); // true
```

但如果把 `null` 当成对象去调用方法，会得到明确、可诊断的运行时异常：

```java
System.out.println(profile.nickname.length());
// NullPointerException
```

这与 C/C++ 的野指针完全不同。Java 在这里的语义是“引用没有指向任何对象”；它不是一段随机比特，也不能偶然指向某个旧地址。

给引用赋值也并不只限于 `new` 或 `null`：方法返回值、数组元素、其他变量、依赖注入框架提供的对象都可以赋给引用。

```java
String name = loadName();
Object value = cache.get("key");
```

关键不是赋值来源，而是**在局部变量被读取前，编译器必须能证明它已被赋值**。

### 2. Java 局部变量没有字段那样的默认值

```java
void printAge() {
    int age;
    System.out.println(age); // 编译错误
}
```

引用局部变量也一样：

```java
void printName() {
    String name;
    System.out.println(name); // 编译错误
}
```

Java 编译器会执行**确定赋值（definite assignment）**分析。它不允许程序读取一个尚未被证明已经赋值的局部变量：

```java
int score;
if (enabled) {
    score = 100;
}
System.out.println(score); // 编译错误：enabled 为 false 时 score 没有值
```

补上完整分支即可：

```java
int score;
if (enabled) {
    score = 100;
} else {
    score = 0;
}
System.out.println(score); // 合法
```

所以 Java 不是“所有变量都会由 JVM 自动赋值”。准确说法是：**实例字段和类字段有语言规定的默认值；局部变量必须在编译期通过确定赋值检查。**

### 3. 默认值发生在什么阶段

“JVM 加载类时给变量赋值”也需要拆开。

- 类的静态字段在类加载后的链接/准备阶段会获得默认值；之后类初始化会按程序顺序执行静态字段显式初始化和静态初始化块。
- 创建对象时，实例字段先处于默认值状态；随后执行实例字段初始化器、实例初始化块和构造函数体。
- 局部变量不属于对象字段或类字段，不走这套默认初始化规则。

例如：

```java
class Counter {
    static int total = 10;
    int step = 1;

    Counter() {
        System.out.println(step); // 1
    }
}
```

在 `total = 10`、`step = 1` 的显式初始化执行之前，相应字段先有语言规定的默认值 `0`；最终可观察到的值再由初始化器和构造过程决定。通常不需要为了日常业务代码追踪 JVM 每一步，只要别把“字段默认值”错误推广到局部变量即可。

## 三、Python：没有“未初始化变量”，只有尚未绑定的名字或不存在的属性

Python 的“变量”更准确地说是**名字到对象的绑定**。赋值不是往一个已分配的固定类型槽位里写值，而是把名字绑定到对象：

```python
age = 18
name = "Yukino"
```

这里 `age` 绑定到整数对象，`name` 绑定到字符串对象。没有一条“先声明一个 `int`，以后再决定里面是什么”的普通 Python 语法。因此 Python 不存在 C/C++ 那种“局部 `int` 未初始化，读取到栈上残留字节”的语言层面现象。

### 1. 名字未绑定时是确定的异常

在模块或交互式环境中读取尚未定义的名字：

```python
print(token)
```

会抛出：

```text
NameError: name 'token' is not defined
```

函数中则有一个更细的规则：只要函数体里出现对名字的赋值，Python 通常会将它视为整个函数的局部名字。

```python
setting = "production"


def show_setting() -> None:
    print(setting)
    setting = "development"
```

调用 `show_setting()` 会抛出：

```text
UnboundLocalError: cannot access local variable 'setting' where it is not associated with a value
```

这不是未定义行为。解释器明确知道此处读取了一个尚未绑定的局部名称，因此以异常终止当前路径。

### 2. 条件分支没有执行，也会留下未绑定的名字

```python
def get_value(enabled: bool) -> int:
    if enabled:
        value = 42
    return value
```

当 `enabled` 为 `False` 时，赋值语句没有执行，`return value` 会抛出 `UnboundLocalError`。

正确的处理方式是让所有分支赋值，或使用明确默认值：

```python
def get_value(enabled: bool) -> int:
    value = 0
    if enabled:
        value = 42
    return value
```

### 3. 对象属性不存在时抛 `AttributeError`

Python 类的实例属性也不会因类型注解而自动获得值：

```python
class User:
    name: str


user = User()
print(user.name)  # AttributeError
```

上面的 `name: str` 主要是注解信息，它没有执行 `self.name = ...`。应在构造函数中明确赋值：

```python
class User:
    def __init__(self, name: str | None = None) -> None:
        self.name = name


user = User()
print(user.name)  # None
```

若业务上“没有名字”是合法状态，可以使用 `None`；若不合法，就应让构造函数要求调用方传入非空字符串。Python 的自由并不意味着状态可以不定义，只是把定义状态的责任更明确地交给了代码。

### 4. `None` 也不是未定义行为

`None` 是一个正常的 Python 单例对象，类似 Java 的 `null`，表示“没有值”或“缺失”。错误通常发生在把它当作其他类型使用时：

```python
name: str | None = None
print(name.upper())  # AttributeError: 'NoneType' object has no attribute 'upper'
```

这种失败同样是有定义的运行时异常，而不是 C/C++ 式的任意内存访问。静态类型检查器可以根据 `str | None` 提前提示这个风险，但 Python 运行时本身不会因为注解而自动初始化或拦截所有类型问题。

## 四、C：先按存储期分类，再谈初始值

C 中，“没赋值”最容易被误称为“有野值”。更精确的术语是：对于许多未初始化对象，其值是**不确定值**（indeterminate value）。能否默认得到零，首先取决于对象的**存储期**。

### 1. 自动存储期：局部标量不会自动初始化

```c
void example(void) {
    int count;
    int *pointer;

    printf("%d\n", count);  /* 错误：不要读取 */
    printf("%p\n", (void *)pointer); /* 同样错误：不要读取 */
}
```

这类局部变量通常具有自动存储期。没有初始化器时，`count` 和 `pointer` 的对象表示不保证是任何可用值。它们可能看似保留了调用栈上先前内容，也可能在不同优化级别、不同调用路径下呈现不同结果。

读取这样的不确定值本身就可能触发未定义行为；把未初始化指针解引用则更危险：

```c
int *pointer;
*pointer = 42;  /* 未定义行为：不能指望它“刚好指向某处” */
```

这里应使用明确初始化：

```c
int count = 0;
int *pointer = NULL;
```

`NULL` 表示空指针常量；它不是一个可解引用的有效对象地址。把指针初始化为 `NULL` 的价值是表达“目前没有指向对象”，后续可先检查再使用，而不是让程序携带不确定的比特。

### 2. 静态存储期：默认进行零初始化

文件作用域变量和 `static` 局部变量具有静态存储期；未显式初始化时会被初始化为零值：

```c
int global_count;          /* 0 */
static int cached_count;   /* 0 */

void example(void) {
    static int call_count; /* 0，仅在程序启动时初始化一次 */
    call_count++;
}
```

对指针而言，静态存储期的零初始化会产生空指针值：

```c
static int *cached_pointer; /* 空指针 */
```

这和自动局部变量不同，不能因为两者都写作 `int value;` 就把规则混在一起。

### 3. 动态分配：`malloc` 与 `calloc` 也不相同

`malloc` 只分配原始存储，不初始化：

```c
int *numbers = malloc(10 * sizeof *numbers);
if (numbers == NULL) {
    /* 分配失败 */
}

/* numbers[0] 在写入前不可读取 */
```

`calloc` 会将分配区域的每个字节置零：

```c
int *numbers = calloc(10, sizeof *numbers);
```

对于普通整数数组，这通常得到可用的零元素；但写可移植代码时，不要把“全零字节”泛化为所有类型的语言零值，例如某些平台的浮点数或指针表示不必等于全零比特。若对象语义重要，最清晰的做法仍是按类型显式初始化。

无论使用哪种分配函数，完成后都要匹配 `free()`；初始化并不会接管资源生命周期。

## 五、C++：标量与对象的初始化规则更细

C++ 继承了 C 中“局部基本类型不会自动变成零”的直觉，但它有构造函数、默认成员初始化、不同初始化形式与 RAII，因此不能只按 C 的习惯套用。

### 1. 自动存储期的基本类型和指针

```cpp
void example() {
    int count;       // 未初始化：不应读取
    double ratio;    // 未初始化：不应读取
    int* pointer;    // 未初始化：不应读取或解引用
}
```

在大多数 C++ 版本和常见语境下，读取这种不确定标量值属于未定义行为。较新的 C++ 标准对部分“错误值”情况作了更细的区分，但这不会让下面代码变得可依赖：

```cpp
int count;
std::cout << count;  // 错误写法
```

无论编译器、调试器或某次运行恰好输出什么，都不是程序可以依赖的结果。优化器会假定程序没有执行未定义行为，并可能据此重排或删除看起来“理所当然”的分支。

正确写法是选择合适的初始化形式：

```cpp
int count = 0;
int total{0};
double ratio{};      // 0.0
int* pointer = nullptr;
```

`{}` 的值初始化常常是现代 C++ 很好的默认选择：

```cpp
int value{};         // 0
bool enabled{};      // false
int* pointer{};      // nullptr
```

它还会禁止某些可能丢失精度的窄化转换：

```cpp
int value{3.14};     // 编译错误，避免悄悄得到 3
```

### 2. `new int` 与 `new int{}` 不同

下面两种动态分配并不等价：

```cpp
int* first = new int;    // 默认初始化：int 未初始化
int* second = new int{}; // 值初始化：*second 为 0
```

因此，看到 `new` 不应自动推断“对象已经有合理初始值”。基本类型与类类型的行为不同，初始化语法也会影响结果。

现代 C++ 更推荐让资源所有权由 RAII 类型表达：

```cpp
#include <memory>

auto value = std::make_unique<int>(0);
```

这样既明确把值初始化为 `0`，也不必手写 `delete`。当然，智能指针解决的是所有权；里面的对象要取什么初始值，仍应由构造参数明确表达。

### 3. 类类型可能由构造函数初始化

```cpp
#include <string>

std::string title;  // 默认构造为空字符串，可安全使用
```

`std::string` 不是“碰巧内存为零才安全”，而是它的默认构造函数建立了有效的空字符串状态。

自定义类也应让构造后的对象保持有效不变式：

```cpp
class ConnectionConfig {
public:
    std::string host{"localhost"};
    int port{5432};
    bool use_tls{true};
};

ConnectionConfig config;
```

这里的成员默认初始化器确保默认构造的 `config` 有可预测状态。若类没有用户提供的构造函数和成员初始化器，则成员初始化情况又会随 `Config config;`、`Config config{};` 等写法变化；对外暴露的类型不应要求调用者记住这种细枝末节来避免非法状态。

### 4. 静态存储期对象同样先零初始化

C++ 的静态存储期对象也会在动态初始化前经历零初始化：

```cpp
int global_count;          // 0
static int cached_count;   // 0
static int* cached_pointer; // nullptr
```

对类对象而言，随后还会执行构造函数或动态初始化。它与“函数里的 `int count;`”是不同的存储期和初始化过程。

## 六、为什么不能只用“内存布局不同”解释

内存布局和运行时实现当然重要，但它们不能单独推出语言层面的初始化规则。至少有四个原因。

### 1. 同一门语言内部也有不同规则

Java 的字段和局部变量不同；C/C++ 的自动、静态、动态存储对象不同；Python 的模块名、局部名和实例属性不同。若只用“Java 的内存布局”或“C++ 的栈”来解释，连同一种语言内部的差别都解释不完整。

### 2. “栈”和“堆”不是最先该问的问题

人们常说：

```text
C/C++ 局部变量在栈上，所以是野值。
Java 对象在堆上，所以字段是零。
```

这只是一种不完整的实现直觉。

- C/C++ 标准用的是自动、静态、线程、动态等**存储期**概念，并不要求某个对象必须放在名为“栈”的硬件区域。
- Java 规范也不是通过“堆上对象天然为零”来定义字段语义；虚拟机实现必须让程序观察到规定默认值。
- 优化器可以把变量放在寄存器、消除对象、重排存储，实际物理布局甚至可能与源码直觉不同。

对业务代码而言，最可靠的问题是：**语言在这个位置保证了什么？**而不是“我猜此刻内存里大概是什么”。

### 3. Java 的安全保证是语言和虚拟机协作的结果

Java 要保证引用字段初始为 `null`，并在空引用解引用时给出 `NullPointerException`，这要求 JVM、字节码验证、对象模型与垃圾回收等机制共同配合。对象内存清零是常见且高效的实现方式之一，但应用程序依赖的是 Java 语言语义，不是某款 JVM 的某个内存清零细节。

同样，Java 局部变量的确定赋值检查主要是编译语言规则；即使底层某个栈槽位恰好有零，也不允许源码读取它。

### 4. C/C++ 把更多责任交给程序员和工具链

C/C++ 不自动初始化多数局部标量，减少了一部分初始化开销，也保留了与底层系统紧密协作的自由。但代价是程序员必须在使用前写入合法值，并借助编译器警告、静态分析、Sanitizer 和测试发现遗漏。

这不是“C/C++ 不知道变量里有什么”，而是语言不替程序员建立一个可读取的默认状态。对性能敏感代码，可以明确选择何处初始化；对普通业务代码，明确初始化通常更值得。

## 七、同一段意图，用四种语言分别写

假设需求是“有一个可选的当前用户；尚未登录时表示为空”。不同语言应使用各自的明确状态表达。

### Java

```java
class Session {
    private User currentUser; // 默认 null

    boolean isLoggedIn() {
        return currentUser != null;
    }
}
```

更严格的 API 也可以使用 `Optional<User>` 作为返回类型，但不应把它当作实体字段中 `null` 的机械替代；关键是清楚定义缺失状态。

### Python

```python
class Session:
    def __init__(self) -> None:
        self.current_user: User | None = None

    def is_logged_in(self) -> bool:
        return self.current_user is not None
```

### C

```c
struct Session {
    struct User *current_user;
};

struct Session session = {0};
/* current_user 被初始化为 NULL */
```

也可显式写得更有语义：

```c
struct Session session = {
    .current_user = NULL,
};
```

### C++

```cpp
struct Session {
    User* current_user{nullptr};

    [[nodiscard]] bool is_logged_in() const {
        return current_user != nullptr;
    }
};
```

若 `Session` 拥有用户对象，则不应仅用裸指针表示所有权，应根据语义选择 `std::unique_ptr<User>`、值成员或其他合适模型。初始化为 `nullptr` 能避免野指针，但不能替你决定生命周期和所有权。

## 八、实践建议

### Java

- 区分字段默认值与局部变量确定赋值规则。
- 引用字段默认是 `null`；访问前应根据业务规则检查、保证非空，或采用合适的非空约束工具。
- 不要把 `NullPointerException` 描述成未定义行为；它是确定的运行时异常。
- 不要依赖“类加载时的某个中间值”设计业务逻辑，应以最终初始化顺序和构造不变式为准。

### Python

- 在所有可能执行路径上绑定局部名称，或直接赋一个清晰默认值。
- 在 `__init__` 中建立实例属性；单独的类型注解不等于赋值。
- 用 `None` 表示缺失状态时，将类型标注为 `T | None`，并在使用前判断。
- 把 `NameError`、`UnboundLocalError`、`AttributeError` 当作逻辑遗漏处理，不要把它们误称为未定义行为。

### C 与 C++

- 默认初始化局部标量和指针：C 用 `= 0`、`= NULL`，C++ 优先用 `{}`、`nullptr`。
- 不要通过打印、比较或条件判断“试探”未初始化值；读取本身就不可靠。
- 对 C++ 类类型，使用构造函数和成员默认初始化器建立有效默认状态。
- 区分 `malloc` 与 `calloc`、`new int` 与 `new int{}`、自动存储期与静态存储期。
- 启用编译器警告，例如 GCC/Clang 的 `-Wall -Wextra -Wuninitialized`；在可用场景下使用 AddressSanitizer、MemorySanitizer 或静态分析工具。工具能帮助发现遗漏，但不能替代初始化语义。

## 九、总结

对“变量没有显式赋值”这件事，Java、Python、C/C++ 的回答并不相同：

```text
Java 字段：有确定的默认零值，引用为 null
Java 局部变量：编译器禁止读取未确定赋值的变量
Python：名字或属性尚不存在时抛出明确异常
C/C++ 自动局部标量：不确定值，读取不可依赖，可能触发未定义行为
C/C++ 静态对象：零初始化
```

因此，下面几句话应当分别改正：

- Java 引用字段不赋值不是未定义行为，而是默认 `null`。
- Java 局部引用也不是默认 `null`，而是必须先经过确定赋值，否则无法编译。
- Python 没有 C/C++ 式的未初始化变量读取；它会因名字未绑定或属性不存在而抛出异常。
- C/C++ 局部指针和普通标量的未初始化问题不应简单叫“野值”；它们具有不确定值，读取或解引用会落入语言不保证的区域。

内存布局能帮助理解为何某些保证有成本、为何 C/C++ 提供更接近底层的控制，但不能替代规范。写代码时，最可靠的原则依然朴素：**先根据语言和业务语义建立明确有效的状态，再读取或使用它。**一段内存偶然看起来像零，并没有承诺过要继续替你保守秘密。
