+++
date = '2025-12-11T20:52:05+08:00'
draft = false
title = 'Java 接口的演变：从抽象契约到 default、static、private 和 sealed'
+++

Java 接口最初只负责定义行为契约。随着 JDK 演进，接口逐渐支持默认方法、静态方法、私有方法和密封接口。它仍然不是普通类，但表达能力比早期强了很多。

理解接口演变，不只是背版本特性。更重要的是看清：Java 为什么要给接口增加方法实现，以及这些能力分别解决什么问题。

## 一、JDK 7 之前

早期接口只能包含：

- `public abstract` 方法。
- `public static final` 常量。

示例：

```java
interface Printer {
    int DEFAULT_COPIES = 1;

    void print(String text);
}
```

即使不写修饰符，编译器也会补全：

```java
public static final int DEFAULT_COPIES = 1;

public abstract void print(String text);
```

接口字段必须是常量，因为接口的核心是定义行为契约，而不是保存实例状态。

```java
interface BadExample {
    int count = 0;
}
```

这里的 `count` 不是实例字段，而是：

```java
public static final int count = 0;
```

实现类不能拥有各自独立的接口字段副本。

## 二、JDK 8：default 方法

JDK 8 引入了默认方法。

```java
interface Printer {
    void print(String text);

    default void printTwice(String text) {
        print(text);
        print(text);
    }
}
```

`default` 方法有方法体，实现类可以不重写。

它最大的意义是**接口兼容性演进**。

假设一个接口已经有很多实现类：

```java
interface CollectionLike {
    int size();
}
```

如果后来想加一个新方法：

```java
boolean isEmpty();
```

在早期 Java 中，所有实现类都必须修改，否则编译失败。JDK 8 之后可以写：

```java
default boolean isEmpty() {
    return size() == 0;
}
```

旧实现类不用修改也能继续工作。

这就是 `default` 方法的主要设计动机：让已有接口能平滑增加能力。

## 三、JDK 8：static 方法

JDK 8 也允许接口定义静态方法。

```java
interface Strings {
    static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
```

调用：

```java
boolean blank = Strings.isBlank(" ");
```

接口静态方法适合放和接口强相关的工具方法。

注意，接口静态方法不会被实现类继承。

```java
class MyStrings implements Strings {
}

MyStrings.isBlank(" ") // 不推荐，也通常不能这样调用
```

应该通过接口名调用：

```java
Strings.isBlank(" ");
```

## 四、JDK 9：private 方法

JDK 9 允许接口定义私有方法，用来复用多个 `default` 方法或 `static` 方法中的内部逻辑。

```java
interface Logger {
    default void info(String message) {
        log("INFO", message);
    }

    default void warn(String message) {
        log("WARN", message);
    }

    private void log(String level, String message) {
        System.out.println("[" + level + "] " + message);
    }
}
```

私有方法不能被实现类调用，也不是接口契约的一部分。

它只是接口内部复用代码的工具。

这让接口里的默认方法可以保持简洁，不必复制粘贴同样逻辑。复制粘贴当然也能工作，只是会在未来用更隐蔽的方式讨债。

## 五、JDK 15/17：sealed 接口

密封类和密封接口在后续 JDK 中逐步预览并正式稳定。现在可以使用 `sealed interface` 限制接口的实现者。

```java
public sealed interface Shape permits Circle, Rectangle {
}

public final class Circle implements Shape {
}

public final class Rectangle implements Shape {
}
```

`sealed` 的作用是限制扩展范围。

适合场景：

- 领域模型封闭。
- 编译器需要知道所有子类型。
- 配合 `switch` 做穷尽检查。
- 不希望任意外部类实现接口。

例如：

```java
sealed interface Result permits Success, Failure {
}

record Success(String data) implements Result {
}

record Failure(String message) implements Result {
}
```

这种结构比随意开放接口更安全，因为类型边界被写进了语言规则里。

## 六、内部接口

接口也可以定义在类或接口内部。

```java
class Sorter {
    interface Strategy {
        boolean compare(int a, int b);
    }

    private Strategy strategy;

    public void setStrategy(Strategy strategy) {
        this.strategy = strategy;
    }
}
```

内部接口常用于表达“这个接口只服务于外部类型”的关系。

典型例子是：

```java
Map.Entry<K, V>
```

它表示 `Map` 中的键值对条目，语义上依附于 `Map`。

内部接口不写访问修饰符时，遵循成员访问规则。普通类内部的成员接口可以使用 `public`、`protected`、包级、`private` 等访问控制。

```java
class Outer {
    interface Inner {
        void run();
    }
}
```

这里 `Inner` 是包级可见。同包代码可以访问，不同包不能直接访问。

## 七、接口和抽象类

接口和抽象类都可以表达抽象，但侧重点不同。

| 对比 | 接口 | 抽象类 |
| ---- | ---- | ------ |
| 主要语义 | 行为契约 | 共同基类 |
| 实例字段 | 不能有普通实例字段 | 可以有实例字段 |
| 构造方法 | 没有构造方法 | 可以有构造方法 |
| 多继承 | 一个类可以实现多个接口 | 一个类只能继承一个类 |
| 代码复用 | default/private 方法有限复用 | 更适合共享状态和模板逻辑 |

抽象类示例：

```java
abstract class Animal {
    protected final String name;

    protected Animal(String name) {
        this.name = name;
    }

    abstract void sound();

    void sleep() {
        System.out.println(name + " sleeps");
    }
}
```

接口示例：

```java
interface Flyable {
    void fly();
}
```

选择建议：

- 只表达能力，用接口。
- 需要共享状态和构造逻辑，用抽象类。
- 需要多种能力组合，用接口。
- 需要限制一组子类型，可以考虑 sealed interface 或 sealed abstract class。

## 八、总结

接口演变可以这样记：

```text
JDK 7 之前：抽象方法 + 常量
JDK 8：default 方法 + static 方法
JDK 9：private 方法
JDK 17：sealed 接口稳定可用
```

接口的核心仍然是行为契约。`default`、`static`、`private` 和 `sealed` 只是让接口在兼容性、工具方法、内部复用和类型封闭方面更有表达力。
