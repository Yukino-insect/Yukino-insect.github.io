+++
date = '2026-03-03T20:01:58+08:00'
draft = false
title = 'Java 异常抛出后是怎么被捕获的'
+++

Java 异常抛出后，会沿着当前调用栈向上查找匹配的 `catch` 代码块。只要某一层方法捕获了该异常，异常传播就会停止；如果一直没有被捕获，线程会终止并打印异常堆栈。

## 一、异常传播过程

示例：

```java
public void a() {
    b();
}

public void b() {
    c();
}

public void c() {
    throw new IllegalArgumentException("invalid argument");
}
```

如果 `c` 方法抛出异常，而 `c`、`b`、`a` 都没有捕获，那么异常会依次从 `c` 传播到 `b`，再传播到 `a`，最后交给更外层调用者。

如果外层存在匹配的 `catch`：

```java
try {
    a();
} catch (IllegalArgumentException e) {
    log.error("参数错误", e);
}
```

异常就会在这里被捕获。

## 二、catch 如何匹配

`catch` 的匹配依据是异常类型。子类异常可以被父类异常捕获：

```java
catch (RuntimeException e) {
    // 可以捕获 IllegalArgumentException
}
```

多个 `catch` 同时存在时，应把更具体的异常放在前面，把更宽泛的异常放在后面。否则具体异常分支可能永远无法执行。

## 三、异常链

Spring 或数据库框架经常会包装底层异常。例如数据库唯一键冲突可能先由 JDBC 抛出，再被 Spring 包装成 `DataAccessException` 体系中的异常。

这就是异常链：

```java
throw new ServiceException("保存失败", cause);
```

外层异常描述业务语义，`cause` 保存底层原因。打印堆栈时，控制台会显示外层异常，并继续显示 `Caused by` 后面的底层异常。

## 四、看堆栈的顺序

排查异常时不要只看第一行。第一行通常是最外层异常，真正的根因往往在最后几个 `Caused by` 中。

阅读顺序建议是：

1. 先看最外层异常，判断业务动作。
2. 再看最底层 `Caused by`，定位根本原因。
3. 最后看自己项目包名附近的调用栈，找到代码位置。

总结来说，Java 异常捕获依赖调用栈和类型匹配；框架包装异常时，要结合异常链一起看，不能只看最上层错误。
