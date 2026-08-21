+++
date = '2025-12-18T18:33:55+08:00'
draft = false
title = 'Comparable 和 Comparator：自然排序与外部排序规则'
+++

Java 中对象排序主要依赖两个接口：

- `Comparable<T>`：对象自己的自然排序规则。
- `Comparator<T>`：外部传入的排序规则。

它们都用于比较两个对象的大小，但职责不同。

## 一、Comparable

`Comparable` 表示“这个类自己知道如何排序”。

```java
class Person implements Comparable<Person> {
    private final String name;
    private final int age;

    Person(String name, int age) {
        this.name = name;
        this.age = age;
    }

    @Override
    public int compareTo(Person other) {
        return Integer.compare(this.age, other.age);
    }
}
```

排序：

```java
List<Person> people = new ArrayList<>();
Collections.sort(people);
```

或：

```java
people.sort(null);
```

当没有额外传入 `Comparator` 时，集合排序会使用元素自己的 `compareTo`。

`Comparable` 适合定义**自然排序**，例如：

- 数字按大小排序。
- 字符串按字典序排序。
- 日期按时间先后排序。
- 业务对象按唯一、稳定、最常用的字段排序。

## 二、compareTo 的返回值

`compareTo` 返回一个整数：

```text
小于 0：当前对象排在前面
等于 0：认为两者排序相等
大于 0：当前对象排在后面
```

不要写：

```java
return this.age - other.age;
```

因为整数相减可能溢出。

更推荐：

```java
return Integer.compare(this.age, other.age);
```

字符串：

```java
return this.name.compareTo(other.name);
```

多字段排序：

```java
@Override
public int compareTo(Person other) {
    int ageResult = Integer.compare(this.age, other.age);
    if (ageResult != 0) {
        return ageResult;
    }

    return this.name.compareTo(other.name);
}
```

## 三、Comparator

`Comparator` 表示“排序规则由外部提供”。

```java
Comparator<Person> byAge = new Comparator<Person>() {
    @Override
    public int compare(Person a, Person b) {
        return Integer.compare(a.getAge(), b.getAge());
    }
};
```

现代写法通常使用 lambda：

```java
Comparator<Person> byAge = (a, b) -> Integer.compare(a.getAge(), b.getAge());
```

更推荐使用工具方法：

```java
Comparator<Person> byAge = Comparator.comparingInt(Person::getAge);
```

排序：

```java
people.sort(byAge);
```

`Comparator` 适合：

- 同一个类有多种排序方式。
- 不能修改目标类源码。
- 排序规则只在当前场景使用。
- 组合多个字段排序。

## 四、组合排序

按年龄升序，再按姓名升序：

```java
Comparator<Person> comparator = Comparator
    .comparingInt(Person::getAge)
    .thenComparing(Person::getName);

people.sort(comparator);
```

倒序：

```java
people.sort(Comparator.comparingInt(Person::getAge).reversed());
```

处理 `null`：

```java
Comparator<Person> comparator = Comparator.comparing(
    Person::getName,
    Comparator.nullsLast(String::compareTo)
);
```

按对象本身可能为 `null`：

```java
people.sort(Comparator.nullsLast(Comparator.comparingInt(Person::getAge)));
```

## 五、Comparator 和 Comparable 的优先级

如果显式传入了 `Comparator`，排序会使用这个外部规则，而不是元素自己的 `Comparable`。

```java
people.sort(Comparator.comparing(Person::getName));
```

即使 `Person` 实现了 `Comparable<Person>`，这里也会按姓名排序。

可以理解为：

```text
没有外部 Comparator -> 使用 Comparable 自然排序
传入 Comparator      -> 使用 Comparator 指定排序
```

## 六、TreeSet 和 TreeMap 中的影响

`TreeSet` 和 `TreeMap` 使用排序规则判断元素或 key 的顺序。

```java
Set<Person> set = new TreeSet<>(Comparator.comparingInt(Person::getAge));
```

注意：对于 `TreeSet`，如果比较结果为 `0`，集合会认为两个元素重复。

```java
Set<Person> set = new TreeSet<>(Comparator.comparingInt(Person::getAge));

set.add(new Person("Alice", 18));
set.add(new Person("Bob", 18));
```

第二个元素可能无法加入，因为比较器认为它们排序相等。

所以排序规则要和“唯一性语义”保持一致。不要只按年龄比较，却期待同年龄不同人都能进入 `TreeSet`。集合不会替你理解人际关系，它只看比较器。

更稳：

```java
Set<Person> set = new TreeSet<>(
    Comparator.comparingInt(Person::getAge)
        .thenComparing(Person::getName)
);
```

## 七、总结

可以这样记：

| 接口 | 规则来源 | 适合场景 |
| ---- | -------- | -------- |
| `Comparable` | 类内部 | 一个稳定的自然排序 |
| `Comparator` | 类外部 | 多种排序规则、临时排序、无法修改类 |

实际开发中，`Comparator` 更常用，也更灵活。`Comparable` 适合那些确实存在自然排序的类。
