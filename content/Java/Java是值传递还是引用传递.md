+++
date = '2025-12-22T15:13:48+08:00'
draft = false
title = 'Java是值传递还是引用传递'
+++

## C++

在 C++ 中，值传递会拷贝对象。引用传递不拷贝对象，直接操作原对象。

现在如果有一个 `CShap` 基类，`CCuboid` 子类继承该基类。如果进行如下操作

```c++
void Display(CShape s) {
    cout << s.Area();
}
```

那么将会发生对象切片。函数只会拷贝 `CShape` 部分的内容，`CCuboid` 的信息被切掉。因此，多态必须用引用传递，不能用值传递。

正确的写法为 
```c++
void Display(CShape& s); 
```

## Java

Java 是值传递，没有引用传递。

对于基本数据类型，直接传递值的副本；

对于对象类型，传递的是对象的引用地址副本；

示例代码：

```java
public class Demo {

    public static void main(String[] args) {
        Person p1 = new Person("Alice");
        change(p1);
        System.out.println(p1.name); // 输出 Bob
    }
    
    static void change(Person p) {
        p.name = "Bob";
    }
}

class Person {
    String name;
    Person(String name) { this.name = name; }
}
```

上述代码输出了 Bob，看似是引用传递但其实值传递。

证明值传递：

```java
public class Demo {

    public static void main(String[] args) {
        Person p1 = new Person("Alice");
        change(p1);
        System.out.println(p1.name); // 输出 Alice
    }
    
    static void change(Person p) {
        p = new Person("Bob")
    }
}

class Person {
    String name;
    Person(String name) { this.name = name; }
}
```

如果真是引用传递，p1 会被重定向到 "Bob"，但结果是 "Alice"，说明参数传递的是引用地址的副本。
