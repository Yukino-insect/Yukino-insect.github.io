+++
date = '2026-11-07T15:31:00+08:00'
draft = false
title = 'Java switch 报错 constant expression required：case 标签为何必须是编译期常量'
+++

在 Java 中写 `switch` 时，下面这种代码很容易得到 `constant expression required`（需要常量表达式）报错：

```java
int status = loadStatusFromDatabase();

switch (input) {
    case status: // 编译错误：constant expression required
        System.out.println("matched");
        break;
    default:
        break;
}
```

直觉上的疑问很合理：`status` 明明也是 `int`，运行时比较一次不就行了吗？问题在于，传统 `switch` 的 `case` 不是任意条件，而是**编译器需要预先确定的标签**。它必须在编译阶段就能确定每个标签的值、检查有没有重复，并据此生成分支结构；数据库、方法调用和普通变量的值只能等程序运行后才知道。

本文解释这个报错的准确原因，区分“不能再赋值的变量”和“编译期常量”，并给出面对动态条件时应该使用的结构。先记住核心结论：**普通 `case` 标签只能写与选择器类型兼容的编译期常量表达式，不能写运行时变量、方法调用或对象属性。**

## 一、`case` 标签不是 `if` 条件

先看两段形式相似、语义却不同的代码：

```java
int expected = loadStatusFromDatabase();

if (input == expected) {
    System.out.println("matched");
}
```

```java
switch (input) {
    case expected: // 编译错误
        System.out.println("matched");
        break;
}
```

`if` 的条件本来就在运行时求值，因此 `expected` 完全合法。传统 `switch` 的每个 `case` 则像一个预先写好的“入口标签”：编译器需要在编译时知道它代表哪个固定值。

这带来两个直接结果：

- 每个普通 `case` 必须是常量表达式。
- 两个 `case` 不能计算出相同的值，否则编译器会报告重复标签。

```java
switch (day) {
    case 1 + 1: // 合法，编译期可计算为 2
        break;
    // case 2:  // 错误：与上面的标签重复
    //     break;
    default:
        break;
}
```

如果允许标签依赖数据库或某次方法调用，编译器不仅无法提前完成这些检查，运行一次与下一次运行得到的分支集合也可能不同。这已经不是 `switch` 设计的使用模型。

## 二、什么是 Java 的常量表达式

不要把“值暂时没改”或“变量写了 `final`”直接等同于编译期常量。`case` 所需的是**常量表达式**：编译器无需执行程序，就能按照语言规则求出结果的表达式。

常见的合法写法包括：

```java
switch (code) {
    case 200:
    case 'A':
    case 100 + 20:
    case (int) 3L:
        System.out.println("fixed label");
        break;
    default:
        break;
}
```

字符串选择器同样可以使用字符串字面量：

```java
switch (command) {
    case "start":
        start();
        break;
    case "stop":
        stop();
        break;
    default:
        throw new IllegalArgumentException("unknown command: " + command);
}
```

可把它理解为：标签是源代码中可被编译器折叠为固定结果的内容，不是“每次运行前刚好有一个值”的内容。

## 三、为什么 `final` 有时可以，有时仍然报错

`final` 的含义是变量只能赋值一次；它并不保证初始化表达式在编译期可求值。

### `final` + 常量表达式：可以作为标签

```java
class HttpCode {
    static final int OK = 200;
    static final String START = "start";
}

switch (code) {
    case HttpCode.OK:
        System.out.println("success");
        break;
    default:
        break;
}

switch (command) {
    case HttpCode.START:
        start();
        break;
    default:
        break;
}
```

`OK` 和 `START` 都是 `final`，类型分别为基本类型和 `String`，初始化值也是字面量；它们满足常量变量的条件，因此可被内联为固定标签。

局部变量也一样：

```java
final int retryCode = 429;

switch (code) {
    case retryCode:
        retryLater();
        break;
    default:
        break;
}
```

这里并不因为它不是 `static final` 就失败。`static` 常用于类级常量的组织，但真正关键的是 `final`、类型和初始化值是否满足常量变量的规则。

### `final` + 运行时计算：仍然不可以

```java
final int configuredCode = Integer.parseInt(System.getProperty("retry.code", "429"));

switch (code) {
    case configuredCode: // 编译错误：constant expression required
        retryLater();
        break;
    default:
        break;
}
```

即使 `configuredCode` 以后绝不会改变，`System.getProperty` 和 `Integer.parseInt` 也必须运行程序后才能执行。编译器不能把它当作固定标签。

下面几类同样不行：

```java
static final int FROM_METHOD = readCode();
static final int FROM_ARRAY = CODES[0];
static final Integer BOXED = 200;
final String fromRequest = request.getCommand();
```

原因分别是方法调用、数组访问、包装类型和运行时方法调用。尤其要注意：`Integer` 虽然装着 `200`，但它不是 `int`；`case` 所需的“常量变量”只适用于基本类型或 `String` 这类符合规则的变量，而不是任意 `final` 对象。

## 四、`static final`、`final` 与枚举的选择

下面的对照足以覆盖大部分实际代码：

| 声明或标签 | 能否用于普通 `case` | 原因 |
| ---------- | ------------------ | ---- |
| `case 404:` | 可以 | 整数字面量 |
| `case 400 + 4:` | 可以 | 编译期常量表达式 |
| `final int NOT_FOUND = 404;` | 可以 | 基本类型、`final`、常量初始化 |
| `static final String GET = "GET";` | 可以 | `String` 常量变量 |
| `static final int TIMEOUT = readTimeout();` | 不可以 | 方法调用只能运行时执行 |
| `static final Integer OK = 200;` | 不可以 | 包装类型不是可用的常量变量 |
| `String name = "GET";` | 不可以 | 没有 `final`，只是普通变量 |
| `final String name = new String("GET");` | 不可以 | `new` 不是常量表达式 |

当一组固定状态本身就是领域概念时，`enum` 通常比魔法数字或字符串更可靠：

```java
enum OrderState {
    CREATED,
    PAID,
    CANCELLED
}

switch (state) {
    case CREATED:
        createShipment();
        break;
    case PAID:
        requestPaymentConfirmation();
        break;
    case CANCELLED:
        releaseReservation();
        break;
}
```

枚举的 `case` 应写未限定的枚举常量名，如 `case PAID:`，而不是 `case OrderState.PAID:`。它们由枚举类型固定定义，既没有拼写字符串的风险，也能得到更好的编译期检查。

## 五、遇到运行时值，应该怎么写

### 动态比较少：使用 `if / else if`

如果比较对象来自配置、数据库或请求，最直接的表达方式就是普通条件：

```java
int retryCode = config.getRetryCode();
int blockedCode = config.getBlockedCode();

if (code == retryCode) {
    retryLater();
} else if (code == blockedCode) {
    blockRequest();
} else {
    handleDefault();
}
```

这不是退而求其次。这里的分支本来就依赖运行时配置，`if` 正是在表达这种动态判断。

### 动态映射多：使用 `Map`

如果“运行时键 → 行为”的映射很多，连续的 `if` 会逐渐难以维护。可以构造一个由配置或注册逻辑填充的表：

```java
Map<Integer, Runnable> handlers = new HashMap<>();
handlers.put(config.getRetryCode(), this::retryLater);
handlers.put(config.getBlockedCode(), this::blockRequest);

Runnable handler = handlers.get(code);
if (handler != null) {
    handler.run();
} else {
    handleDefault();
}
```

这里 `Map` 中的键可以在运行时产生，正好与 `switch` 的固定标签形成分工。实际项目还应处理重复配置、缺省行为，以及 `Runnable` 无法携带复杂上下文时的策略接口设计。

### 条件是范围或组合：使用 `if`，不要伪装成 `switch`

`switch` 擅长“一个值等于哪个离散标签”，不擅长范围判断：

```java
if (score >= 90) {
    return "A";
}
if (score >= 60) {
    return "B";
}
return "C";
```

以下写法不能成立：

```java
// case score >= 90: // case 不是布尔条件
```

把范围、正则、对象属性或数据库结果硬塞进 `switch`，只会让代码试图表达语言本来没有承诺的语义。

## 六、现代 `switch` 没有取消这条规则

Java 14 起正式支持 `switch` 表达式和箭头标签，写法可以更紧凑：

```java
String category = switch (code) {
    case 200, 201 -> "success";
    case 400, 404 -> "client error";
    default -> "other";
};
```

这里的 `200`、`201`、`400`、`404` 仍然必须是固定标签；把其中任意一个换成普通变量，错误依旧存在。箭头语法解决的是穿透、返回值和分支结构问题，并没有把 `case` 改造成任意运行时条件。

较新的 Java 版本还支持模式匹配的 `switch`，可以按类型等模式分支。那是另一类由语言专门定义的标签规则，不应据此认为普通的整数或字符串 `case` 可以写数据库值、方法调用或关系表达式。

## 七、排查 `constant expression required` 的步骤

看到这个错误时，可以按以下顺序检查：

1. `case` 中是否写了普通变量、字段访问、方法调用、数组元素或 `new` 表达式？若是，它通常是运行时值。
2. 变量是否为 `final`，类型是否为基本类型或 `String`，初始化值是否本身是常量表达式？三个条件缺一不可。
3. 如果值本来就应该固定，能否改成字面量、合适的 `static final` 常量或 `enum`？
4. 如果值必须来自配置、数据库或请求，改用 `if / else` 或 `Map`，不要试图绕过编译器。
5. 再检查是否有两个标签最终得到相同常量值；修完前一个错误后，这类重复标签错误才可能显现。

## 八、总结

- `constant expression required` 的根本原因是：普通 `case` 标签需要在编译期确定，运行时变量不能充当标签。
- `final` 只保证变量不再被重新赋值；只有基本类型或 `String` 的 `final` 变量，且初始化值也是常量表达式时，才可作为普通 `case` 标签。
- `static final` 是组织类级常量的常见形式，但不是唯一条件；`static final Integer` 或调用方法得到的 `static final int` 仍然不符合要求。
- 固定的领域状态适合 `enum`；运行时的少量比较适合 `if / else`；大量动态映射适合 `Map` 或策略表。
- 新式箭头 `switch` 改善了分支写法，却没有放宽普通 `case` 的编译期常量要求。

因此，看到报错时不必急着给变量补一个 `final`。先问它的值究竟来自源码中的固定规则，还是来自程序运行后的世界；前者交给 `case`，后者就该由 `if` 或映射表来处理。编译器不是在故意为难你，它只是拒绝把一张运行时才出现的地图，伪装成早已印好的路标。
