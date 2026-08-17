+++
date = '2025-12-18T18:33:55+08:00'
draft = false
title = 'Comparable 和 Comparator'
+++

## Comparable 

它是用来定义每个类的自然排序规则。当类自生实现了该接口，在一些集合中排序时会默认使用这个规则。

```java
class Person implements Comparable<Person> {
    int age;

    @Override
    public int compareTo(Person o) {
        return this.age - o.age;
    }
}
```

## Comparator

是外部定义的规则，在调用排序方法时。传入一个 `Comparator` 的实现类作为该排序方法中元素的排序规则。

```java
class AgeComparator implements Comparator<Person> {
    @Override
    public int compare(Person a, Person b) {
        return Integer.compare(a.age, b.age);
    }
}
```

> `Comparator` 的优先级高于 `Comparable`。只要显式传入了 `Comparator`，程序就会完全忽略 `Comparable`
