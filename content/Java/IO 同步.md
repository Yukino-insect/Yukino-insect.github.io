+++
date = '2025-09-13T18:56:18+08:00'
draft = false
title = 'IO 同步'
+++

IO 是指 Input/Output，即输入输出流。以内存为中心：

- Input指从外部读入数据到内存，例如，把文件从磁盘读取到内存，从网络读取数据到内存等等。
- Output指把数据从内存输出到外部，例如，把数据从内存写入到文件，把数据从内存输出到网络等等。

IO 流是一种顺序读写数据的模式，特点是单向流动。

在 Java 中 IO 流分为输入流和输出流，根据数据的处理方式又分为字节流和字符流。

它的所有类都是从如下四个抽象基类派生的

- `InputStream`/`Reader`: 所有的输入流的基类，前者是字节输入流，后者是字符输入流。
- `OutputStream`/`Writer`: 所有输出流的基类，前者是字节输出流，后者是字符输出流。

以上所说的类都是 Java 标准库的包`java.io`提供的同步 IO，而`java.nio`则是异步 IO。

### File

文件在计算机系统中是重要的存储方式。`java.io`中提供了`File`对象来操作文件和目录

构造一个`File`对象只需传入文件路径，就算传入不存在的路径也不会报错，因为构造一个`File`对象并不会导致任何磁盘操作，只有当真正调用`File`的某些方法时，才会真正执行磁盘操作。

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        File file = new File("../log/test.txt");
        if (file.createNewFile()) { // 创建文件
            System.out.println(file.isFile()); // 判断是否文件
            System.out.println(file.isDirectory()); // 判断是否是目录
            if (file.delete()) { // 删除文件
                System.out.println("删除成功");
            }
        }
    }
}
```

当`File`表示一个目录时，可以列出目录下的文件和子目录

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        File file = new File("../log");
        if (file.isDirectory()) {
            File[] files = file.listFiles();
            for (File temp : files) {
                System.out.println(temp.getPath());
            }
        }
    }
}
```

### InputStream

是所有输入流的超类。这个超类定义的一个最重要的方法就是`int read()`。用于读取输入流的下一个字符并返回字节表示的`int`值，如果读到末尾就返回`-1`，表示不能继续读取。

同时，它还有两个重载方法，利用缓存区一次读取多个数据来提高效率

- `int read(byte[] b)`：读取若干字节并填充到`byte[]`数组，返回读取的字节数
- `int read(byte[] b, int off, int len)`：指定`byte[]`数组的偏移量和最大填充数

**FileInputStream**是它的一个子类，用来从文件中读取数据

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (FileInputStream fis1 = new FileInputStream("../test/test.txt");) {
            int n = fis1.read();
            while (n != -1) {
                System.out.println(n);
                n = fis1.read();
            }
        }
		// fis1 读取完数据之后，流中就不存在数据了
        try (FileInputStream fis2 = new FileInputStream("../test/test.txt");) {
            byte[] b = new byte[100];
            int n = fis2.read(b);
            if (n != -1) {
                System.out.println("byte number: " + n);
            }
        }

    }
}
```

在计算机中，类似文件、网络端口这些资源，都是由操作系统统一管理。应用程序在运行过程中，如果打开了一个文件进行读写，操作完成后要及时关闭，以便让操作系统把资源释放掉。

`InputStream`和`OutputStream`都是通过`close()`方法来关闭流。其对应着底层资源的释放。

如果在读取或写入 IO 流的过程中发生底层错误，Java 虚拟机会自动封装成`IOException`异常并抛出，因此，所有与IO操作相关的代码都必须正确处理`IOException`。

否则的话，资源可能无法正确关闭。

```java
InputStream input = new FileInputStream("/path/...");
byte[] b = new byte[100];
System.out.print(read(b));
throw new IOException(); // 发生异常
input.close();
```

可以使用`try ... finally`或`try (resource)`来保证即使程序发生错误，接下来的也能正确完成关闭资源的操作。

**ByteArrayInputStream**可以将一个`byte[]`数组在内存中变成一个`InputStream`

### OutputStream

是所有输出流的超类，它定义的一个最重要的方法就是`void write(int b)`。这个方法会写入一个字节到输出流。它虽然传入的是`int`参数，但只会写入`int`最低 8 位部分表示的字节。

它也同样提供了`close()`方法来关闭输出流。同时它也提供了一个`flush()`方法，用来强制将缓冲区的内容真正输出到目的地。

输出流在磁盘、网络写入数据的时候出于效率，不是输出一个字节就会立刻写入文件或发送到网络，而是把字节先存到缓冲区中，等缓冲区写满了再一次性完成写入。这样会减少 IO 次数，从而减少执行时间。

在某些场景下，等不到缓存写满才真正写入到文件或者网络，所以需要手动调用`flush()`方法，强制将缓冲区的内容输出。

`InputStream`的缓冲区也有缓冲区，它会存放操作系统一次性读取的多个字节，并通过维护的指针指向未读的缓冲区，每次调用`read()`移动指针返回数据。避免每次读一个字节都导致IO操作。当缓冲区全部读完后继续调用`read()`，则会触发操作系统的下一次读取并再次填满缓冲区。

**FileOutputStream**

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (OutputStream outputStream = new FileOutputStream("../test/test.txt")) {
            outputStream.write("凤凰院凶真".getBytes("UTF-8")); // 直接写入一个 byte[]
        }
    }
}
```

**ByteArrayOutputStream**将一个`byte[]`变成`OutputStream`

### Filter 模式

如果直接使用继承为`InputStream`和`OutputStream`附加更多的功能，会产生大量的子类，最终导致失控。

因此使用了 Filter 模式为`InputStream`和`OutputStream`增加功能。

通过把一个`InputStream`和任意个`FilterInputStream`组合；一个`OutputStream`和任意个`FilterOutputStream`组合来实现功能的增加。Filter 模式又称 Decorator 模式。

常见的`Filter`实现类有：

**BufferedInputStream**、**BufferedOutputStream**、**BufferedReader**和**BufferedWriter**

以上四个包装类在输入输出流上都维护了一个缓冲区，用来减少频繁的 IO 操作

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (BufferedOutputStream outputStream =
             new BufferedOutputStream(new FileOutputStream("../test/test.txt"))) {
            outputStream.write("xuezhixia".getBytes());
            outputStream.flush(); // 强制把缓冲区内容写到文件（不写也行，close() 会自动 flush）
        }
    }
}
```

工作原理

- **不加缓冲**：`FileOutputStream` 每次 `write()` 调用都会触发系统 I/O 操作。
- **加了 `BufferedOutputStream`**：数据先写到内存缓冲区，缓冲区满了或调用 `flush()` / `close()` 时，才一次性写到文件/网络，效率更高。

**从 classPath 读取资源文件**

```java
try (InputStream input = getClass().getResourceAsStream("/default.properties")) {
    // TODO:
}
```

### 序列化

**序列化**是指把一个 Java 对象变成二进制内容，本质上就是一个`byte[]`数组。这样就可以把序列化后的`byte[]`保存到文件中，或者通过网络传输到远程。

一个类如果要想序列化就要实现`java.io.Serializable`接口。这个接口是一个空接口，仅仅是一个标记，没有任何方法

一个可以序列化的类

```java
public class Person implements Serializable {

    public static final long serialVersionUID = 1L;
    public String name;
    public int age;
}
```

要把一个 Java 对象变为`byte[]`数组，需要使用`ObjectOutputStream`。它负责把一个 Java 对象写入一个字节流

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        Person p = new Person();
        p.name = "hj";
        p.age = 20;
        OutputStream outputStream = new FileOutputStream("../test/object.txt");
        try (ObjectOutputStream objectOutputStream = new ObjectOutputStream(outputStream)) {
            objectOutputStream.writeObject(p);
        }
    }
}
```

除此之外，`ObjectOutputStream`还可以写入基本类型，如`int`、`boolean`等。

**反序列化**是负责把一个字节流变成 Java 对象。在读取的过程中可能抛出：

- `ClassNotFoundException`：没有找到对应的Class；
- `InvalidClassException`：Class不匹配。

发生`ClassNotFoundException`常见于反序列化本地不存在的类

发生`InvalidClassException`可能是因为原类的内容被修改，导致序列化后的类与此不兼容。

为了避免这种 class 定义变动导致的不兼容，Java的序列化允许class定义一个特殊的`serialVersionUID`静态变量，用于标识Java类的序列化“版本”，通常可以由IDE自动生成。如果增加或修改了字段，可以改变`serialVersionUID`的值，这样就能自动阻止不匹配的class版本。反序列化时，由JVM直接构造出Java对象，不调用构造方法，构造方法内部的代码，在反序列化时根本不可能执行

`ObjectInputStream`用来实现序列化

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        InputStream inputStream = new FileInputStream("../test/object.txt");
        try (ObjectInputStream objectInputStream = new ObjectInputStream(inputStream)) {
            Person p = (Person) objectInputStream.readObject();
            System.out.println("name: " + p.name + "\n" + "age: " + p.age);
        }
    }
}
```

如果改变`serialVersionUID = 1L`的值，就会报错

```bash
PS D:\Project\IdeaProjects\java\src> java Demo      
Exception in thread "main" java.io.InvalidClassException: Person; local class incompatible: stream classdesc serialVersionUID = 1, local class serialVersionUID = 0
        at java.base/java.io.ObjectStreamClass.initNonProxy(ObjectStreamClass.java:597)
        at java.base/java.io.ObjectInputStream.readNonProxyDesc(ObjectInputStream.java:2051)
        at java.base/java.io.ObjectInputStream.readClassDesc(ObjectInputStream.java:1898)
        at java.base/java.io.ObjectInputStream.readOrdinaryObject(ObjectInputStream.java:2224)
        at java.base/java.io.ObjectInputStream.readObject0(ObjectInputStream.java:1733)
        at java.base/java.io.ObjectInputStream.readObject(ObjectInputStream.java:509)
        at java.base/java.io.ObjectInputStream.readObject(ObjectInputStream.java:467)
        at Demo.main(Demo.java:13)
```

如果不想序列化某些类，可以使用**`transient`** 修饰的字段

反序列化时，这些字段会被还原为默认值：

- 对象引用 = `null`
- 数值 = `0`
- boolean = `false`

除了 `transient`，还可以通过 **自定义序列化** 控制更精细的逻辑：

```
private void writeObject(ObjectOutputStream oos) throws IOException {
    oos.defaultWriteObject(); // 序列化非 transient 字段
    // 自己控制要不要写某个字段
}

private void readObject(ObjectInputStream ois) throws IOException, ClassNotFoundException {
    ois.defaultReadObject(); 
    // 自己控制要不要读某个字段
}
```

这两个方法是序列化机制允许类定义特定签名的私有方法来控制序列化行为。

实现 `Externalizable` 接口也可以实现序列化，它适用于完全自定义序列化方式。

```java
@Override
public void writeExternal(ObjectOutput out) throws IOException {
    out.writeObject(name);      // 只序列化 name
    // password 不写出 => 等于保护了敏感信息
}

@Override
public void readExternal(ObjectInput in) throws IOException, ClassNotFoundException {
    this.name = (String) in.readObject();
}
// 通过这两方式实现自定义序列化
```

### Reader

所有字符输入流的超类，它的主要方法是`int read()`。这个方法会读取字符流的下一个字符，并返回字符表示的`int`，如果读到末尾返回`-1`

和`InputStream`类似，`Reader`也是一种资源，需要保证出错也能正确的释放资源

**FileReader**

是`Reader`的一个子类，可以使用它来打开文件并获取`Reader`

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (Reader reader = new FileReader("../test/test.txt", StandardCharsets.UTF_8)) {
            char[] c = new char[100];
            while (reader.read(c) != -1) {
                System.out.println(c);
            }
        }
    }
}
```

`Reader`提供了一次性读取若干字符并填充到`char[]`数组的方法，它实际返回读入的字符个数，最大不超过`char[]`数组的长度。返回`-1`表示流结束。

`FileReader`默认编码与系统有关，如果文件于系统的编码不同就可能出现乱码，因此可以指定编码

```java
Reader reader = new FileReader("../test/test.txt", StandardCharsets.UTF_8)
```

**CharArrayReader**和**StringReader**可以分别把一个`char[]`和`String`变成一个`Reader`

```java
Reader reader = new CharArrayReader("Hello".toCharArray())
Reader reader = new StringReader("Hello")
```

`Reader`是基于`InputStream`实现的，因此可以通过`InputStreamReader`将一个`InputStream`转换为`Reader`

```java
Reader reader = new InputStreamReader(new FileInputStream("src/readme.txt"), "UTF-8")
```

### Writer

`Reader`是带编码转换器的`InputStream`，它把`byte`转换为`char`，而`Writer`就是带编码转换器的`OutputStream`，它把`char`转换为`byte`并输出。

`Writer`是所有字符输出流的超类，它主要提供的方法有：

- 写入一个字符（0~65535）：`void write(int c)`
- 写入字符数组的所有字符：`void write(char[] c)`
- 写入String表示的所有字符：`void write(String s)`

### FileWriter

向文件中写入字符

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (Writer writer = new FileWriter("test.txt", StandardCharsets.UTF_8)) {
            writer.write("我永远喜欢雪之下雪乃");
        }
    }
}
```

**CharArrayWriter**和**StringWriter**

**OutputStreamWirter**可以将任意的`OutputStream`转换为`Writer`的转换器

```java
Writer writer = new OutputStreamWriter(new FileOutputStream("readme.txt"), "UTF-8")
```

**PrintStream**

是一种`FilterOutputStream`，它在`OutputStream`的接口上提供了一些额外写入各种数据类型的方法：

- 写入`int`：`print(int)`
- 写入`boolean`：`print(boolean)`
- 写入`String`：`print(String)`
- 写入`Object`：`print(Object)`，实际上相当于`print(object.toString())`

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        try (PrintStream printStream = new PrintStream("../test/test.txt");) {
            printStream.println("雪之下雪乃");
        }
    }
}
```

`println()`会自动加上换行符

经常使用的`System.out.println()`实际上就是使用`PrintStream`打印各种数据。其中，`System.out`是系统默认提供的`PrintStream`，表示标准输出。

它不会抛出`IOException`

**PrintWriter**

`PrintStream`最终输出的总是byte数据，而`PrintWriter`则是扩展了`Writer`接口，它的`print()`/`println()`方法最终输出的是`char`数据

用法和上类似

**Files**封装了很多读写文件的简单方法

```java
public class Demo {
    public static void main(String[] args) throws Exception {
        String str = Files.readString(Path.of("../test/test.txt"));;
        System.out.println(str);
        Files.writeString(Path.of("../test/test.txt"), "fenghuangyuanxiongzhen", StandardCharsets.UTF_8);
        System.out.println(Files.readString(Path.of("../test/test.txt")));
    }
}
```

### IO 模型

为了保证操作系统的稳定和安全，一个进程的地址空间划分为**用户空间**和**内核空间**。

平常运行的应用程序就是运行在用户空间，只有内核空间才能进行系统态级别的资源有关的操作，比如文件管理、进程通信、内存管理等等。

所以应用程序要进行 IO 操作，就一定要依赖内核空间的能力。但是用户空间不能直接访问内核空间，只能发起系统调用请求操作系统帮忙完成。因此，用户进程想要执行 IO 操作的话，必须通过**系统调用**来间接访问内核空间。然后具体的 IO 操作是由操作系统的内核来完成的。这个过程会经历两个步骤：

- 内核等待 IO 设备准备好数据
- 内核将数据从内核空间拷贝到用户空间

#### 常见的 IO 模型

Unix 系统下，IO 模型一共有五种：**同步阻塞 I/O**、**同步非阻塞 I/O**、**I/O 多路复用**、**信号驱动 I/O** 和**异步 I/O**。

**BIO（Blocking I/O）**同步阻塞 IO

当应用程序发起 read() 调用后，会一直阻塞，直到内核把数据拷贝到用户空间。

在阻塞 IO 模型中，每个连接都需要一个线程来处理。因此，对于大量高并发连接的场景，阻塞 IO 模型性能较差

**Non-blocking I/O ** 同步非阻塞 IO

应用程序会发起 read() 调用，如果数据未准备好时，IO 调用会立即返回。在数据准备的这段时期是不会阻塞线程的，但当等数据从内核空间拷贝到用户空间的这段时间里，线程依然是阻塞的，直到内核将数据拷贝到用户空间。

在轮询发起 read() 调用的空隙，应用程序可以切换去做一些小的任务。也就是说轮询不是持续不断发起的，会有间隙, 这个间隙的利用就是同步非阻塞 IO 比同步阻塞 IO 高效的地方。它允许单个线程同时处理多个连接。

但是这个不断轮询的过程十分消耗 CPU 资源。

**I/O 多路复用模型**

IO 多路复用模型使用操作系统提供的多路复用功能，如 select、poll、epoll 等，使得单个线程可以同时处理多个 IO 事件。当某个连接上的数据准备好时，操作系统会通知应用程序。这样，应用程序可以在一个线程中处理多个并发连接，而不需要为每个连接创建一个线程。

这样通过减少无效的系统调用，减少了对 CPU 资源的消耗。

- select 是 Unix 系统中最早的 IO 多路复用技术。它允许一个线程同时监视多个文件描述符，并等待某个文件描述符上的 I/O 事件（如可读、可写或异常）
- poll 是对 select 的改进。它使用一个文件描述符数组而不是位掩码来表示文件描述符集。这样可以避免 select 中的性能问题
- epoll 是 Linux 中的一种高性能 I/O 多路复用技术。它通过在内核中维护一个事件表来避免遍历文件描述符数组的性能问题。当某个文件描述符上的 I/O 事件发生时，内核会将该事件添加到事件表中。应用程序可以使用 epoll_wait 函数来获取已准备好的 I/O 事件，而无需遍历整个文件描述符集。这种方法大大提高了在大量并发连接下的性能。

**Signal-driven I/O** 信号驱动

应用程序可以向操作系统注册一个信号处理函数，当某个 I/O 事件发生时，操作系统会发送一个信号通知应用程序。应用程序在收到信号后处理相应的 I/O 事件。这种模型与非阻塞 I/O 类似，也需要在应用程序级别进行事件管理和调度

**AIO** 异步 IO 模型

与同步 I/O 模型的主要区别在于，异步 I/O 操作会在后台运行，当操作完成时，操作系统会通知应用程序。应用程序不需要等待 I/O 操作的完成，可以继续执行其他任务。这种模型适用于处理大量并发连接，且可以简化应用程序的设计和开发。

**Java IO 模型**可以分为两大类

一类是传统的 阻塞 IO

上文中介绍的传统 Java IO（`java.io.*`）就是阻塞式 IO，这些类在读写数据时会导致线程阻塞，直到操作完成。

一类是 NIO

Java NIO（java.nio.*）是 Java 1.4 版引入的，基于通道、缓冲区进行操作，采用非阻塞式 IO 操作，允许线程在等待 IO 时执行其他任务。

Java 7 加强了 NIO，增加了异步 IO。
