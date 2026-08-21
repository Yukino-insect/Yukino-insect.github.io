+++
date = '2025-12-31T20:44:11+08:00'
draft = false
title = 'Java 基本类型与包装类型：装箱、拆箱、缓存与空指针'
+++

Java 有八种基本类型，也为每种基本类型提供了对应的包装类型。

基本类型直接保存值，包装类型是对象。

这看起来只是语法差异，但在集合、泛型、数据库字段、接口 DTO、性能和空指针问题中都会产生影响。

## 一、八种基本类型

| 基本类型 | 包装类型 | 说明 |
| -------- | -------- | ---- |
| `byte` | `Byte` | 8 位整数 |
| `short` | `Short` | 16 位整数 |
| `int` | `Integer` | 32 位整数 |
| `long` | `Long` | 64 位整数 |
| `float` | `Float` | 单精度浮点数 |
| `double` | `Double` | 双精度浮点数 |
| `char` | `Character` | 字符 |
| `boolean` | `Boolean` | 布尔值 |

基本类型不能为 `null`。

```java
int count = 0;
```

包装类型可以为 `null`。

```java
Integer count = null;
```

这就是很多 DTO、数据库映射对象使用包装类型的原因：它可以表达“未传”“未知”“数据库为 null”。

## 二、为什么需要包装类型

包装类型常见用途：

- 泛型。
- 集合。
- 反射。
- 框架绑定。
- 表达 `null`。
- 作为对象参与统一 API。

Java 泛型不能直接使用基本类型。

错误：

```java
List<int> numbers;
```

正确：

```java
List<Integer> numbers;
```

集合中只能放对象，所以必须使用包装类型。

## 三、自动装箱和拆箱

自动装箱：基本类型自动转换为包装类型。

```java
Integer value = 1;
```

大致等价于：

```java
Integer value = Integer.valueOf(1);
```

自动拆箱：包装类型自动转换为基本类型。

```java
Integer value = 1;
int number = value;
```

大致等价于：

```java
int number = value.intValue();
```

自动转换让代码更简洁，但也隐藏了空指针和性能成本。

## 四、自动拆箱的空指针

最常见问题：

```java
Integer value = null;
int number = value;
```

运行时会抛出：

```text
NullPointerException
```

因为拆箱时实际调用：

```java
value.intValue();
```

`value` 是 `null`，当然会报错。

类似问题也会出现在比较中：

```java
Integer count = null;

if (count > 0) {
    System.out.println("positive");
}
```

这里 `count > 0` 会触发自动拆箱。

更稳：

```java
if (count != null && count > 0) {
    System.out.println("positive");
}
```

或先给默认值：

```java
int safeCount = count == null ? 0 : count;
```

## 五、包装类型缓存

部分包装类型有缓存机制。

常见规则：

- `Byte` 全部缓存。
- `Short`、`Integer`、`Long` 默认缓存 `-128` 到 `127`。
- `Character` 通常缓存 `0` 到 `127`。
- `Boolean` 使用 `TRUE` 和 `FALSE`。
- `Float`、`Double` 没有整数那样的缓存。

示例：

```java
Integer a = 100;
Integer b = 100;

System.out.println(a == b); // true
```

```java
Integer c = 1000;
Integer d = 1000;

System.out.println(c == d); // false
```

原因是 `100` 命中缓存，`1000` 默认不命中缓存。

但不要依赖这种行为判断数值相等。

应该写：

```java
Objects.equals(a, b);
```

或：

```java
a.intValue() == b.intValue()
```

如果可能为 `null`，优先：

```java
Objects.equals(a, b)
```

## 六、包装类型比较

不推荐：

```java
Integer a = 1000;
Integer b = 1000;

System.out.println(a == b);
```

`==` 比较的是对象引用是否相同。

推荐：

```java
System.out.println(Objects.equals(a, b));
```

或明确拆箱：

```java
if (a != null && b != null && a.intValue() == b.intValue()) {
    ...
}
```

对于常量在左侧的场景，可以：

```java
if (Integer.valueOf(1).equals(status)) {
    ...
}
```

但更常见的是：

```java
if (Objects.equals(status, 1)) {
    ...
}
```

## 七、性能影响

基本类型直接存值，包装类型是对象。大量包装类型会增加：

- 对象分配。
- 间接访问。
- GC 压力。
- 缓存局部性损失。

例如：

```java
int[] values = new int[1_000_000];
```

和：

```java
Integer[] values = new Integer[1_000_000];
```

差异很大。

`int[]` 里是连续的基本类型值。`Integer[]` 里是连续的引用，每个非缓存 `Integer` 对象还在堆上单独存在。

所以数值密集计算、数组、大批量处理时，基本类型通常更合适。

业务 DTO、集合、泛型和需要 `null` 的地方，再使用包装类型。

## 八、String 不是包装类型

`String` 不是基本类型，也不是包装类型。

```java
String text = "hello";
```

它是普通引用类型，只是 Java 对字符串字面量有常量池机制。

```java
String a = "abc";
String b = "abc";

System.out.println(a == b); // 通常为 true
```

通过 `new` 创建：

```java
String c = new String("abc");

System.out.println(a == c); // false
```

字符串内容比较应该使用：

```java
a.equals(c)
```

不要把 `String` 的常量池和包装类型缓存混为一谈。它们都像“复用对象”，但机制和适用场景不同。

## 九、使用建议

| 场景 | 建议 |
| ---- | ---- |
| 局部计算 | 基本类型 |
| 循环计数 | 基本类型 |
| 大数组数值计算 | 基本类型数组 |
| 集合元素 | 包装类型 |
| 泛型参数 | 包装类型 |
| DTO 需要表达未传 | 包装类型 |
| 数据库字段允许 null | 包装类型 |
| 布尔配置有三态 | `Boolean` |

所谓三态是：

```text
true
false
null 表示未配置或未知
```

如果业务只有两态，不要随便用 `Boolean`，否则你迟早要处理第三种状态。它不会因为你没想过就不存在。

## 十、总结

可以这样记：

```text
基本类型：值，不能 null，性能好
包装类型：对象，可以 null，适合泛型、集合、框架和 DTO
装箱：基本类型 -> 包装类型
拆箱：包装类型 -> 基本类型
```

最重要的两个提醒：

- 包装类型比较不要依赖 `==`。
- 自动拆箱前要小心 `null`。
