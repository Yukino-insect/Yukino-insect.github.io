+++
date = '2026-03-03T20:01:58+08:00'
draft = false
title = 'Java 异常捕获机制'
+++

Java 异常抛出后，会沿着当前线程的调用栈向上查找匹配的 `catch` 代码块。找到后，异常传播停止；一直找不到，当前线程终止，并由默认异常处理器打印堆栈。

这个过程可以理解成三件事：

1. 抛出异常对象。
2. 沿调用栈逐层回退。
3. 按异常类型匹配 `catch`。

## 一、异常如何向上传播

先看一个简单调用链：

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

如果 `c` 抛出异常，而 `c`、`b`、`a` 都没有捕获，那么异常会从 `c` 回到 `b`，再回到 `a`，最后交给更外层调用者。

如果外层存在匹配的 `catch`：

```java
try {
    a();
} catch (IllegalArgumentException e) {
    log.error("参数错误", e);
}
```

异常会在这里被捕获，后续代码从 `catch` 之后继续执行。

## 二、catch 如何匹配

`catch` 的匹配依据是异常类型。子类异常可以被父类异常捕获：

```java
try {
    parse(input);
} catch (RuntimeException e) {
    // 可以捕获 IllegalArgumentException、NullPointerException 等 RuntimeException 子类
}
```

多个 `catch` 同时存在时，必须把更具体的异常放在前面：

```java
try {
    parse(input);
} catch (NumberFormatException e) {
    log.warn("数字格式错误", e);
} catch (IllegalArgumentException e) {
    log.warn("参数不合法", e);
}
```

如果把 `IllegalArgumentException` 放在前面，`NumberFormatException` 分支就永远执行不到，编译器会直接报错。是的，编译器偶尔也会做些真正有用的事。

## 三、JVM 视角：异常表

编译后的字节码里，方法会带有异常表。异常表记录了某段指令范围内，如果抛出某类异常，应该跳转到哪个处理位置。

可以粗略理解为：

```text
try 起点 -> try 终点 -> catch 入口 -> 捕获的异常类型
```

运行时一旦抛出异常，JVM 会先在当前方法的异常表里查找匹配项。找不到，就弹出当前栈帧，回到调用者方法继续找。这个过程就是栈展开。

## 四、finally 什么时候执行

`finally` 通常用于释放资源。无论 `try` 正常结束，还是 `catch` 捕获异常，`finally` 都会执行：

```java
try {
    readFile();
} catch (IOException e) {
    log.error("读取失败", e);
} finally {
    closeQuietly();
}
```

但现代 Java 更推荐使用 `try-with-resources` 管理资源：

```java
try (InputStream in = Files.newInputStream(path)) {
    return in.readAllBytes();
}
```

资源会在代码块结束时自动关闭，比手写 `finally` 更不容易漏。

## 五、异常链

框架经常会包装底层异常。例如数据库唯一键冲突可能先由 JDBC 抛出，再被 Spring 包装成 `DataAccessException` 体系中的异常。

这就是异常链：

```java
throw new ServiceException("保存失败", cause);
```

外层异常描述业务语义，`cause` 保存底层原因。打印堆栈时，控制台会先显示外层异常，再显示 `Caused by` 后面的底层异常。

设计业务异常时，不要随手丢掉 `cause`：

```java
// 不推荐：根因丢失
throw new ServiceException("保存失败");

// 推荐：保留根因
throw new ServiceException("保存失败", e);
```

## 六、Suppressed 异常

`try-with-resources` 关闭资源时也可能抛异常。如果 `try` 代码块本身已经抛了一个异常，关闭资源时又抛了另一个异常，后者不会覆盖前者，而是会被记录为 suppressed exception。

可以通过下面的方法查看：

```java
Throwable[] suppressed = e.getSuppressed();
```

这类异常排查频率不高，但在文件、网络、数据库连接关闭失败时会出现。知道它存在就够了，没必要每天惦记它。

## 七、看堆栈的顺序

排查异常时，不要只看第一行。第一行通常是最外层异常，真正的根因往往在最底层 `Caused by` 附近。

建议顺序：

1. 先看最外层异常，判断当前业务动作是什么。
2. 再看最底层 `Caused by`，定位根本原因。
3. 最后看自己项目包名附近的调用栈，找到具体代码位置。

## 八、总结

Java 异常捕获依赖调用栈和类型匹配。异常抛出后，JVM 会在当前方法查找匹配的处理器；找不到就继续向调用者传播，直到被捕获或线程终止。

实践中要记住三点：

1. `catch` 从具体异常写到宽泛异常。
2. 包装异常时保留 `cause`。
3. 排查问题时顺着异常链看根因，不要只盯第一行。
