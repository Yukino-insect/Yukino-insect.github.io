+++
date = '2025-12-11T20:52:05+08:00'
draft = false
title = 'Java 接口的演变'
+++

## JDK 7 之前

接口只能包含：

- `public abstract` 方法
- `public static fianl` 常量

不能有**方法实现**和**实例字段**

```java
interface A {
    int NUM = 10;
    void f(); // abstract
}
```

接口的主要作用是**抽象行为**、**实现多继承**。

> **接口中的字段只能是 `public static final`，我们在接口中写任何接口字段，Java 编译器会自动将修饰符补全。**
>
> 接口字段是：
>
> - 共有的，所有实现类都可以使用
> - 静态的，属于接口不属于任何实现类
> - 被 **final** 修饰，防止被修改
>
> 只有这样才能满足接口的作用：**定义行为契约**。

## JDK 8

到 JDK 8 时，Java 引入了：

- 默认方法，方法可以带有实现类。

  ```java
  default void print() {
      System.out.println("hello");
  }
  ```

- 静态方法，可以充当静态工具类

  ```java
  static void say() {
      System.out.println("Hi");
  }
  ```

**Java 8 中的 default 方法是一个兼容性设计。一般来说，实现接口的类需要将接口中声明的方法全部重写，如果这时给接口中添加了新方法的话，下面的所有旧实现类需要该方法重写。这在大系统中是灾难。但是新增 default 之后，在接口中新定义一个 default 方法，旧类不需要修改也能继续使用。**

## JDK 9

这时 Java 引入了，**私有方法**，接口可以写私有方法，用于 default 方法之间复用。

```java
private void helper() {
    System.out.println("help");
}
```

> 我们可以看到，开篇接口中的方法并没有写修饰符，这是因为没有任何修饰符的接口方法，编译器会自动加上 `public abstract`。如果我们要使用默认方法、私有方法和静态方法等等，都需要手动加上相应的关键字 `default`、`private` 和 `static`。
>
> 接口的主要作用是表示行为契约，因此：
>
> -  **public：**表示所有实现类都可以看到
> - **abstract：**要求实现类必须实现

## JDK 16+

接口可以被**密封**，这样就可以限制无关类实现该接口，增强类型系统的安全性。

```java
public sealed interface Shape permits Circle, Rectangle {}
```

**可以发现，这和类内部接口的作用很像，都是限制接口的实现者，规定作用范围。最大的区别就是 sealed 接口时编译器强制规范的，内部类是编写程序时的一种语义。**

典型的像 **Map.Entry**，它就是 JDK 单独为 Map 类型设计的接口。

我们可以单独设计一个类，内部定义一个策略接口

```java
class Sorter {
    interface Strategy {
        boolean compare(int a, int b);
    }

    private Strategy strategy;

    public void setStrategy(Strategy s) {
        this.strategy = s;
    }
}
```

通过外部为这个类提供不同的策略，实现不同的功能

```java
Sorter sorter = new Sorter();
sorter.setStrategy(new Sorter.Strategy() {
    public boolean compare(int a, int b) { return a < b; }
});
```

> 这里我们的接口并没有用修饰符，那么编译器认为它的作用域是什么呢？
>
> **内部接口不写修饰符默认是 `package-private`（包级可见）**
>
> ```java
> class Outer {
>     interface Inner {
>         void f();
>     }
> }
> 
> class Test implements Outer.Inner {  // 只要在同包就能实现
>     public void f() {}
> }
> ```
>
> ```java
> package other;
> 
> class Test implements Outer.Inner {} // 无法访问 Inner
> 
> ```
>
> 这就一般的类修饰符规则一样。
>
> - 顶层类和接口的修饰符只有两种，`public`、`package-private`。
> - 而类中字段属性的修饰规则是
>   - `public` 对所有代码可见
>   - `protected` 子类、同包可见
>   - `(default) package-private` 同包可见
>   - `private` 只有当前类可见
>   - `static` 被它修饰的话表示当前属性属于类，不属于实例

## 接口和抽象类有什么关系

在讨论二者的关系时，我们先了解一下什么是抽象类：

**抽象类是一种不能被创建对象的类，其中可以包含抽象方法（没有方法体的方法），用于强制子类实现某些行为。**

**抽象类常作为基类，内部定义子类必须重写的抽象方法，实现代码的复用。**

```java
abstract class Animal {
    protected String name;

    public Animal(String name) {
        this.name = name;
    }

    abstract void sound();  // 抽象方法

    void sleep() {          // 普通方法
        System.out.println("zzz...");
    }
}

class Dog extends Animal {

    public Dog(String name) {
        super(name);
    }

    void sound() {
        System.out.println(name + " barks");
    }
}

public class Test {
    public static void main(String[] args) {
        Animal a = new Dog("Buddy");
        a.sound();
        a.sleep();
    }
}
```

**抽象类允许包含变量、构造方法、普通方法等，但是它不能被 final 修饰，因为抽象类就是用来被继承的。它和接口相比起来的话，接口实际上是一种对类行为的规范，让不同的类实现同一套方法。**
