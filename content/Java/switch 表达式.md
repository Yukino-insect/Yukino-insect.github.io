+++
date = '2026-03-04T19:04:03+08:00'
draft = false
title = 'switch 表达式'
+++

老版本 Java 7/8 的 switch 不能直接返回值，我们只能先定义变量，再在 case 里赋值：

```java
int code;
switch (status) {
  case 1:
    code = 200;
    break;
  case 2:
    code = 400;
    break;
  default:
    code = 500;
}
```

老版本的 switch 必须 `break`，否则会把所有分支都执行一遍。并且 case 只能写常量（编译期常量），比如 `int/char/enum/String`，但不能是范围、不能是条件表达式。

而到了 Java 17+ 的版本。

switch 可以使用 `->` 箭头 case，这时就可以不写 `break`

```java
switch (op) {
  case ADD -> add();
  case DEL -> del();
  default -> throw new IllegalArgumentException();
}
```

> 注意，如果不写 `->` 的话，是需要写 break 的。

switch 在 Java 17+ 支持产出一个值。

```java
int score = switch (level) {
  case HIGH -> 3;
  case MID  -> 2;
  case LOW  -> 1;
};
```

`case HIGH -> 3` 这种写法的意思就是，当 level 是 HIGH 时，这个 switch 表达式的值就是 3。

> 如果我们单独这样写 
>
> ```java
> switch (level) {
>   case HIGH -> 3;
>   case MID  -> 2;
>   case LOW  -> 1;
> };
> ```
>
>  **Java 里通常是不合法/没意义的**。因为它既没有被赋值，也没有被 return

支持多个 case 合并

```java
String type = switch (c) {
  case 'a', 'e', 'i', 'o', 'u' -> "vowel";
  default -> "other";
};
```

如果 case 里面要写多行逻辑，可以使用 `{}` + `yield`

`yield` 表示这个 case 块最终产出什么值

```java
String msg = switch (status) {
  case 1 -> {
    log.info("ok");
    yield "SUCCESS";
  }
  case 2 -> {
    log.warn("bad");
    yield "FAIL";
  }
  default -> "UNKNOWN";
};
```

当 switch 的对象是 enum，并且把所有枚举值都写全，很多时候可以不写 default。这样以后 enum 新增值时，编译器会提醒补齐分支，从而避免漏处理。

```java
enum Level { HIGH, MID, LOW }

int score = switch (level) {
  case HIGH -> 3;
  case MID  -> 2;
  case LOW  -> 1;
};
```

如果写了 default，编译器就不一定提醒新增枚举值没处理，安全性会差一点。
