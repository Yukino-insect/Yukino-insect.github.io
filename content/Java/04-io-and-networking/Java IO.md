+++
date = '2025-09-13T18:56:18+08:00'
draft = false
title = 'Java IO 与同步阻塞模型'
+++

Java IO 主要指 `java.io` 包里的输入输出 API。它的核心模型很朴素：以程序内存为中心，从外部读入内存叫输入，把内存写到外部叫输出。

- `InputStream` / `OutputStream`：字节流，处理原始二进制数据。
- `Reader` / `Writer`：字符流，处理文本数据，会涉及字符编码。
- `File`：表示文件或目录路径，本身不等于文件内容。
- `Serializable` / `ObjectInputStream` / `ObjectOutputStream`：Java 原生对象序列化机制。

传统 `java.io` 整体属于**同步阻塞 IO**。调用 `read()` 时，如果数据还没准备好，当前线程通常会阻塞；调用 `write()` 时，如果底层暂时写不出去，也可能阻塞。它写起来直观，但面对大量连接时，需要谨慎处理线程数量。

## 一、字节流和字符流

字节流直接处理 `byte`，适合图片、压缩包、音视频、网络协议、未知编码文件等二进制内容。

字符流处理 `char`，适合文本内容。它会在字节和字符之间做编码转换，所以必须考虑 `UTF-8`、`GBK` 这类字符集。

| 类型 | 输入 | 输出 | 适合场景 |
| --- | --- | --- | --- |
| 字节流 | `InputStream` | `OutputStream` | 二进制数据、网络数据、文件复制 |
| 字符流 | `Reader` | `Writer` | 文本读取、文本写入 |

一句话：不知道是不是文本，就先按字节流处理。随便把二进制数据当字符读，结果通常不会有礼貌。

## 二、File 和 Path

`File` 表示文件或目录的路径。创建一个 `File` 对象不会立刻访问磁盘，只有调用 `exists()`、`isFile()`、`listFiles()`、`delete()` 等方法时，才会真正和文件系统交互。

```java
File file = new File("data/app.log");

System.out.println(file.exists());
System.out.println(file.isFile());
System.out.println(file.getAbsolutePath());
```

`File` 是较早的 API。现在写新代码时，更推荐使用 `java.nio.file.Path` 和 `Files`：

```java
Path path = Path.of("data", "app.log");

if (Files.exists(path)) {
    String text = Files.readString(path, StandardCharsets.UTF_8);
    System.out.println(text);
}
```

`Path` 更适合表达路径，`Files` 更适合执行文件操作。`File` 还能用，但新代码不必对它太执着。

## 三、InputStream

`InputStream` 是所有字节输入流的父类，最基础的方法是：

```java
int read() throws IOException
```

它一次读取一个字节，返回 `0` 到 `255` 之间的整数；如果读到末尾，返回 `-1`。

实际开发中更常用带缓冲区的读取方式：

```java
Path path = Path.of("data.bin");

try (InputStream in = Files.newInputStream(path)) {
    byte[] buffer = new byte[8192];
    int len;

    while ((len = in.read(buffer)) != -1) {
        // buffer 中只有 [0, len) 这一段是本次读到的数据
        System.out.println("read bytes: " + len);
    }
}
```

这里有两个细节：

- `read(byte[])` 返回的是本次实际读到的字节数，不一定等于数组长度。
- 只有返回 `-1` 才表示结束，返回 `0` 在某些流实现中也可能出现。

因此不要直接使用整个 `buffer`。有效数据只在 `[0, len)` 范围内。

## 四、OutputStream

`OutputStream` 是所有字节输出流的父类，最基础的方法是：

```java
void write(int b) throws IOException
```

它只会写入 `int` 的低 8 位。实际开发中通常写入 `byte[]`：

```java
Path path = Path.of("data.bin");
byte[] data = "hello".getBytes(StandardCharsets.UTF_8);

try (OutputStream out = Files.newOutputStream(path)) {
    out.write(data);
}
```

`flush()` 用来把缓冲区里的数据尽快推到底层目标：

```java
try (OutputStream out = new BufferedOutputStream(Files.newOutputStream(path))) {
    out.write(data);
    out.flush();
}
```

文件流在 `close()` 时会自动刷新。网络流、包装流、交互式协议中，什么时候 `flush()` 就要认真考虑。比如服务端写完一行响应却不刷新，客户端可能一直等着，以为世界停止了。

## 五、try-with-resources

文件句柄、Socket、流对象都属于需要关闭的资源。资源不关闭，轻则文件占用，重则连接泄漏。

推荐使用 `try-with-resources`：

```java
try (InputStream in = Files.newInputStream(Path.of("in.txt"));
     OutputStream out = Files.newOutputStream(Path.of("out.txt"))) {
    in.transferTo(out);
}
```

只要对象实现了 `AutoCloseable`，就可以放在 `try (...)` 中。无论正常结束还是抛异常，都会自动调用 `close()`。

传统 `try-finally` 当然也能做，但代码更啰嗦，异常覆盖也更容易处理错。既然语言已经替你扫地，就不必抢扫帚。

## 六、缓冲流

直接读写文件时，每次调用都可能触发系统调用。系统调用比普通方法调用重得多，所以 Java 提供了缓冲流：

- `BufferedInputStream`
- `BufferedOutputStream`
- `BufferedReader`
- `BufferedWriter`

缓冲流的作用是把多次小读写合并成较少的大读写。

```java
Path source = Path.of("source.log");
Path target = Path.of("target.log");

try (InputStream in = new BufferedInputStream(Files.newInputStream(source));
     OutputStream out = new BufferedOutputStream(Files.newOutputStream(target))) {
    byte[] buffer = new byte[8192];
    int len;

    while ((len = in.read(buffer)) != -1) {
        out.write(buffer, 0, len);
    }
}
```

很多高级 API 内部已经做了缓冲，但理解缓冲流仍然重要。看到一段代码每次只读一个字节还没有缓冲，就应该稍微皱一下眉。不是所有慢代码都值得同情。

## 七、Reader 和 Writer

`Reader` / `Writer` 处理字符，适合文本文件。

```java
Path path = Path.of("app.log");

try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
    String line;

    while ((line = reader.readLine()) != null) {
        System.out.println(line);
    }
}
```

写文本：

```java
Path path = Path.of("result.txt");

try (BufferedWriter writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
    writer.write("hello");
    writer.newLine();
    writer.write("world");
}
```

注意：`readLine()` 会去掉行尾换行符。如果业务需要保留原始换行，就不能只依赖 `readLine()` 的返回值。

## 八、编码转换

`InputStreamReader` 可以把字节输入流转换成字符输入流；`OutputStreamWriter` 可以把字符输出流转换成字节输出流。

```java
try (Reader reader = new InputStreamReader(
        Files.newInputStream(Path.of("app.log")),
        StandardCharsets.UTF_8)) {
    char[] buffer = new char[1024];
    int len;

    while ((len = reader.read(buffer)) != -1) {
        System.out.println(new String(buffer, 0, len));
    }
}
```

不要依赖系统默认编码。默认编码会随操作系统、JDK 版本、启动参数变化。文本文件如果明确是 `UTF-8`，代码里就写 `StandardCharsets.UTF_8`。

乱码问题通常不是玄学，而是写入时用一种编码，读取时换了另一种编码。玄学只是人类给自己没查清楚的问题起的名字。

## 九、内存流

`ByteArrayInputStream` 和 `ByteArrayOutputStream` 可以在内存中模拟输入输出。

```java
ByteArrayOutputStream out = new ByteArrayOutputStream();
out.write("hello".getBytes(StandardCharsets.UTF_8));
out.write(" java".getBytes(StandardCharsets.UTF_8));

byte[] data = out.toByteArray();

try (InputStream in = new ByteArrayInputStream(data)) {
    System.out.println(new String(in.readAllBytes(), StandardCharsets.UTF_8));
}
```

它们常用于测试、协议组包、临时生成字节数组等场景。数据量很大时不要无脑塞进内存，否则问题就从 IO 变成内存压力。

## 十、classpath 资源

配置文件经常放在 classpath 下，例如 `src/main/resources/default.properties`。读取时可以使用类加载器：

```java
try (InputStream in = Thread.currentThread()
        .getContextClassLoader()
        .getResourceAsStream("default.properties")) {
    if (in == null) {
        throw new FileNotFoundException("default.properties");
    }

    Properties properties = new Properties();
    properties.load(new InputStreamReader(in, StandardCharsets.UTF_8));
    System.out.println(properties.getProperty("app.name"));
}
```

`getResourceAsStream()` 找不到资源时会返回 `null`，不会自动抛异常。这里如果不判断，后面很可能得到一个不太友善的 `NullPointerException`。

## 十一、打印流

`PrintStream` 和 `PrintWriter` 提供了 `print()`、`println()` 这类方便方法。

```java
try (PrintWriter writer = new PrintWriter(
        Files.newBufferedWriter(Path.of("result.txt"), StandardCharsets.UTF_8))) {
    writer.println("hello");
    writer.printf("count=%d%n", 10);
}
```

`System.out` 就是一个 `PrintStream`。

需要注意的是，`PrintStream` / `PrintWriter` 的很多写入方法不会直接向外抛出 `IOException`，而是记录错误状态。必要时可以调用 `checkError()` 检查。

## 十二、对象序列化

Java 原生序列化可以把对象写成字节流：

```java
class User implements Serializable {
    private static final long serialVersionUID = 1L;

    private String name;
    private int age;

    User(String name, int age) {
        this.name = name;
        this.age = age;
    }
}
```

写出对象：

```java
Path path = Path.of("user.bin");

try (ObjectOutputStream out = new ObjectOutputStream(Files.newOutputStream(path))) {
    out.writeObject(new User("Tom", 18));
}
```

读回对象：

```java
try (ObjectInputStream in = new ObjectInputStream(Files.newInputStream(path))) {
    User user = (User) in.readObject();
}
```

几个重要点：

- `Serializable` 是标记接口。
- `serialVersionUID` 用来标识序列化版本。
- `transient` 修饰的字段不会被默认序列化。
- 反序列化不会调用普通构造方法。

但原生序列化不适合作为通用数据交换格式。它和 Java 类结构绑定太紧，跨语言不友好，还存在反序列化安全风险。实际项目里，更常见的是 JSON、Protocol Buffers、Avro 等格式。

如果输入来自不可信来源，不要随便用 `ObjectInputStream` 反序列化。它的问题不是“不优雅”，而是可能真的危险。

## 十三、Files 常用方法

`Files` 提供了很多更方便的文件操作：

```java
Path path = Path.of("app.log");

String text = Files.readString(path, StandardCharsets.UTF_8);
List<String> lines = Files.readAllLines(path, StandardCharsets.UTF_8);
byte[] bytes = Files.readAllBytes(path);

Files.writeString(path, "hello", StandardCharsets.UTF_8);
Files.copy(Path.of("source.txt"), Path.of("target.txt"), StandardCopyOption.REPLACE_EXISTING);
Files.deleteIfExists(Path.of("old.txt"));
```

这些方法适合中小文件和简单场景。大文件不要轻易 `readAllBytes()` 或 `readAllLines()`，因为它们会把内容一次性读进内存。

## 十四、同步阻塞 IO 模型

一次 IO 通常可以拆成两个阶段：

1. 等待数据准备好。
2. 把数据从内核空间拷贝到用户空间，或者反过来写出。

阻塞 IO 的特点是：调用线程会在这些阶段等待。

```text
应用线程调用 read()
        |
        v
内核等待数据准备
        |
        v
数据从内核空间拷贝到用户空间
        |
        v
read() 返回
```

这种模型简单可靠，很适合文件操作、低并发网络通信、命令行工具、后台批处理等场景。

但在高并发网络服务里，如果每个连接都占用一个阻塞线程，线程数量、上下文切换和内存占用都会变成压力。这时通常会考虑：

- `java.nio` 的非阻塞 IO 和 `Selector`。
- Netty 这类网络框架。
- Java 7 之后的异步通道 API。
- 虚拟线程。对于大量阻塞 IO，虚拟线程能显著降低线程成本，但 IO 调用本身仍然是同步写法。

## 十五、怎么选择

| 场景 | 推荐 |
| --- | --- |
| 简单读写文本 | `Files.readString`、`Files.writeString` |
| 按行读大文本 | `BufferedReader` |
| 复制二进制文件 | `Files.copy` 或缓冲字节流 |
| 处理网络协议 | 字节流，明确消息边界 |
| 读 classpath 配置 | `ClassLoader.getResourceAsStream` |
| Java 内部临时对象持久化 | 谨慎使用原生序列化 |
| 跨系统数据交换 | JSON、Protobuf 等格式 |

总结一下：

- 字节流处理原始数据，字符流处理文本。
- 文本读写必须明确字符编码。
- 流资源要用 `try-with-resources` 关闭。
- 缓冲流减少频繁系统调用。
- 原生序列化能用，但不要滥用。
- `java.io` 是同步阻塞模型，简单直观，但高并发网络场景要考虑线程成本。
