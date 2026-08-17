+++
date = '2025-12-31T20:44:11+08:00'
draft = false
title = 'Java 的基本类型和包装类型'
+++

Java 有八种基本类型，也为每种基本类型提供了对应的包装类型。基本类型直接保存值，包装类型是对象。

## 一、基本类型和包装类型

对应关系如下：

| 基本类型 | 包装类型 |
| --- | --- |
| `byte` | `Byte` |
| `short` | `Short` |
| `int` | `Integer` |
| `long` | `Long` |
| `float` | `Float` |
| `double` | `Double` |
| `char` | `Character` |
| `boolean` | `Boolean` |

基本类型不能为 `null`，包装类型可以为 `null`。因此数据库字段、接口参数和 DTO 中如果需要表达“未传”或“未知”，通常应使用包装类型。

## 二、为什么需要包装类型

包装类型常用于：

1. 泛型，例如 `List<Integer>`。
2. 需要表示 `null` 的场景。
3. 反射和框架绑定。
4. 集合类存储。

Java 泛型不能直接使用基本类型，所以集合中必须使用包装类型。

## 三、自动装箱和拆箱

Java 会在基本类型和包装类型之间自动转换：

```java
Integer a = 1; // 装箱
int b = a;     // 拆箱
```

自动拆箱时要注意空指针：

```java
Integer value = null;
int result = value; // NullPointerException
```

## 四、包装类型缓存

部分包装类型有缓存机制。默认情况下：

1. `Byte`、`Short`、`Integer`、`Long` 通常缓存 `-128` 到 `127`。
2. `Character` 通常缓存 `0` 到 `127`。
3. `Boolean` 使用 `TRUE` 和 `FALSE`。
4. `Float` 和 `Double` 没有类似整数缓存。

因此比较包装类型数值时，不要使用 `==`，应使用 `equals`，或先拆箱后比较。

## 五、String 常量池

`String` 不是基本类型，也不是基本类型包装类。它有字符串常量池机制，用来复用字面量字符串。

```java
String a = "abc";
String b = "abc";
```

这里 `a` 和 `b` 可能指向常量池中的同一个对象。但通过 `new String("abc")` 创建时，会显式创建新对象。

## 六、总结

基本类型适合局部计算和性能敏感场景。包装类型适合集合、泛型、框架绑定和需要表示空值的场景。比较包装类型时要避免依赖缓存行为。
