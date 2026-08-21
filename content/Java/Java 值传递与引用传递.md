+++
date = '2026-03-09T08:49:42+08:00'
draft = false
title = 'Java 值传递与引用传递：为什么对象参数也不是引用传递'
+++

Java 方法参数只有一种传递方式：**值传递**。

这句话容易让人困惑，因为对象作为参数传入方法后，方法内部确实可以修改对象字段。于是很多人会说“对象是引用传递”。这个说法不准确。

更精确地说：

> Java 对基本类型传递的是值的副本；对引用类型传递的是引用值的副本。

引用值可以理解为“指向对象的地址信息”。方法拿到的是这个地址信息的副本，所以它可以通过副本找到同一个对象并修改对象内部状态，但不能让外部变量改指向另一个对象。

## 一、基本类型是值副本

```java
public class Demo {
    public static void change(int x) {
        x = 100;
    }

    public static void main(String[] args) {
        int a = 10;
        change(a);
        System.out.println(a);
    }
}
```

输出：

```text
10
```

`change(a)` 时，方法参数 `x` 得到的是 `a` 的值副本。方法内部改 `x`，不会影响外面的 `a`。

## 二、对象参数为什么能修改字段

看对象例子：

```java
public class Demo {
    static class Person {
        String name;

        Person(String name) {
            this.name = name;
        }
    }

    public static void rename(Person p) {
        p.name = "Bob";
    }

    public static void main(String[] args) {
        Person person = new Person("Alice");
        rename(person);
        System.out.println(person.name);
    }
}
```

输出：

```text
Bob
```

这不是引用传递，而是因为：

```text
外部变量 person 保存一个引用值
 -> 调用 rename(person)
 -> 形参 p 得到引用值的副本
 -> person 和 p 都指向同一个 Person 对象
 -> p.name 修改的是同一个对象内部字段
```

可以画成：

```text
person ─┐
        ├──> Person{name="Alice"}
p      ─┘
```

`p.name = "Bob"` 改的是对象本身，不是外部变量 `person`。

## 三、最能证明 Java 不是引用传递的例子

如果 Java 是引用传递，那么方法内部把参数重新赋值为新对象，外部变量也应该跟着改变。

但事实不会。

```java
public class Demo {
    static class Person {
        String name;

        Person(String name) {
            this.name = name;
        }
    }

    public static void change(Person p) {
        p = new Person("Bob");
    }

    public static void main(String[] args) {
        Person person = new Person("Alice");
        change(person);
        System.out.println(person.name);
    }
}
```

输出：

```text
Alice
```

方法内部：

```java
p = new Person("Bob");
```

只是让形参 `p` 这个副本指向了新对象。

调用前：

```text
person ─┐
        ├──> Person{name="Alice"}
p      ─┘
```

重新赋值后：

```text
person ───> Person{name="Alice"}

p      ───> Person{name="Bob"}
```

外面的 `person` 没有变。

这说明 Java 传进去的是引用值的副本，而不是外部引用变量本身。

## 四、C++ 的引用传递是什么

C++ 支持真正的引用传递：

```cpp
#include <iostream>
using namespace std;

void change(int& x) {
    x = 100;
}

int main() {
    int a = 10;
    change(a);
    cout << a << endl;
}
```

输出：

```text
100
```

这里：

```cpp
int& x
```

表示 `x` 是 `a` 的别名。修改 `x`，就是修改 `a`。

这和 Java 参数完全不同。Java 没有这种“形参成为外部变量别名”的机制。

## 五、C++ 指针传递和 Java 更像

C++ 传指针时，本质上也是把指针值复制一份。

```cpp
void change(Person* p) {
    p = new Person("Bob");
}
```

如果只是改变 `p` 指向的新对象，外面的指针变量也不会自动改。

想修改外部指针本身，需要传指针引用或二级指针：

```cpp
void change(Person*& p) {
    p = new Person("Bob");
}
```

这一点和 Java 的对象参数很像：Java 传的是引用值副本，而不是引用变量本身。

## 六、常见误区

### 1. 能修改对象字段就是引用传递

不对。

能修改对象字段，只说明形参和实参引用值指向了同一个对象。

```java
p.name = "Bob";
```

改的是对象内部状态。

### 2. 重新给参数赋值会影响外部变量

不对。

```java
p = new Person("Bob");
```

只会改变形参 `p` 的指向，不会改变外部变量。

### 3. String 传参改不了，所以 String 特殊

`String` 确实不可变，但参数传递规则没有变。

```java
public static void change(String s) {
    s = "new";
}
```

这里也是让形参 `s` 指向新字符串，不会改变外部变量。

### 4. Integer 传参改不了，所以包装类型是值传递

所有类型都是值传递。`Integer` 改不了通常和不可变对象、装箱拆箱有关，不是另一套参数规则。

## 七、总结

Java 参数传递可以这样记：

```text
基本类型：复制具体值
引用类型：复制引用值
```

复制引用值后：

- 可以通过副本修改同一个对象的内部字段。
- 不能通过副本改变外部引用变量指向谁。

如果只写一句话：

> Java 永远是值传递；对象参数传递的是引用值的副本，所以能改对象内容，不能改外部变量本身的指向。
