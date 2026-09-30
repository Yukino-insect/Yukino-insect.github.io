+++
date = '2026-09-30T20:10:00+08:00'
draft = false
title = 'Java 多模块项目中的包名、源码根目录与 classpath'
+++
多模块 Java 项目常让人产生一个直觉冲突：代码明明位于 `rag/`、`agent/`、`framework/` 等不同目录，为什么它们的 `package` 却都以同一段前缀开头？又为什么主模块只依赖其他模块的 JAR，就能在运行时使用其中的类？

这是因为 **Maven 模块、Java 包和 classpath 属于三个不同层次**。它们彼此有关联，却不能互相替代：模块规定构建和依赖，包规定类的逻辑名字，classpath 规定编译器与 JVM 实际可查找哪些类和资源。

## 一、用一个多模块项目观察三个层次

设想一个仓库：

```text
ragent/
├─ bootstrap/
│  └─ src/main/java/com/example/ragent/RagentApplication.java
├─ framework/
│  └─ src/main/java/com/example/ragent/framework/web/GlobalExceptionHandler.java
├─ rag/
│  └─ src/main/java/com/example/ragent/rag/controller/RAGChatController.java
└─ agent/
   └─ src/main/java/com/example/ragent/agent/controller/AgentChatController.java
```

三个层次分别回答不同问题：

| 层次 | 代表物 | 回答的问题 |
| --- | --- | --- |
| 构建层 | `bootstrap`、`rag`、`agent` 模块及 POM | 谁依赖谁、怎样编译和打包？ |
| 语言层 | `com.example.ragent.rag.controller` | 这个类的完整名字是什么、同包访问规则如何？ |
| 运行层 | classpath | 编译器、JVM、框架能从哪里加载类与资源？ |

如果把这三者混在一起，就会出现“Spring 是不是遍历了所有模块目录”的误解。Spring 不遍历仓库；它通过类加载器查看 classpath 上的已编译类。Maven 模块目录在源码阶段很重要，但并不等于 Java 包，也不等于运行时 classpath。

## 二、Java 包名相对于源码根目录，而不是仓库根目录

以 `rag` 模块为例：

```text
rag/
└─ src/main/java/
   └─ com/example/ragent/rag/controller/RAGChatController.java
```

文件开头应写为：

```java
package com.example.ragent.rag.controller;
```

因为 `rag/src/main/java` 是 Maven 约定的**源码根目录**。从这个根目录向下的相对路径：

```text
com/example/ragent/rag/controller/RAGChatController.java
```

恰好对应 package 路径和类名。`rag/src/main/java` 是构建工具识别源码的路径，不属于包名。因此下面的写法是错误的：

```java
// 错误：把模块目录和源码约定目录误当成 Java 包的一部分
package rag.src.main.java.com.example.ragent.rag.controller;
```

编译后，Java 编译器会输出：

```text
rag/target/classes/com/example/ragent/rag/controller/RAGChatController.class
```

`.java` 变成 `.class` 后，`target/classes` 就是该模块在开发期可提供给其他模块的一个 classpath 位置。

## 三、共享根包不等于完整包名相同

下列类并不在同一个 Java 包中：

```java
package com.example.ragent.framework.web;
package com.example.ragent.rag.controller;
package com.example.ragent.agent.controller;
```

它们仅共享根包前缀 `com.example.ragent`。这种安排有三个明显收益：

1. **命名空间清楚。** `rag`、`agent`、`framework` 都是同一产品的一部分，包前缀能体现这一点。
2. **类名不会轻易冲突。** Java 真正区分类的是完全限定类名，例如 `com.example.ragent.rag.config.Config` 与 `com.example.ragent.agent.config.Config` 可以同时存在。
3. **适配 Spring 默认扫描。** 启动类位于 `com.example.ragent` 时，可以覆盖上述所有子包。

不过，Java 不会因为两个类在不同 JAR 里就允许完全相同的完全限定类名。若两个依赖都包含：

```text
com/example/ragent/common/Config.class
```

便产生了类路径冲突。类加载器通常按搜索顺序找到其中一个，另一个被遮蔽，行为可能随构建或运行环境改变。不同模块使用清晰的子包不仅是为了扫描便利，也是为了避免这种冲突。

## 四、classpath 到底是什么

classpath 是**类与资源的可搜索位置集合**。其中每一个位置可以是目录、普通 JAR，或由特定类加载器识别的其他位置。

当 JVM 需要加载下面的类：

```text
com.example.ragent.rag.controller.RAGChatController
```

它会把完整类名转换为资源路径：

```text
com/example/ragent/rag/controller/RAGChatController.class
```

然后尝试从 classpath 的各个条目中查找它。开发期的逻辑 classpath 可以理解为：

```text
bootstrap/target/classes
rag/target/classes
agent/target/classes
framework/target/classes
~/.m2/.../spring-context-*.jar
~/.m2/.../spring-webmvc-*.jar
...
```

在 Windows 命令行中，多个传统 classpath 条目通常使用分号分隔；在类 Unix 系统中常使用冒号。IDE、Maven 和 Spring Boot 插件会替我们组装这串路径，因此日常通常不必手工设置环境变量 `CLASSPATH`。更准确的说法是：**每次编译或启动都有一个实际的类路径**，它不等同于某个全局环境变量。

除了类，资源也会随之可见。例如 `src/main/resources/application.yml` 编译/打包后通常位于 classpath 根部，Spring 才能使用 `classpath:application.yml` 这样的资源定位方式。有关配置文件的加载优先级，可进一步阅读[Spring 配置文件加载](Spring 配置文件加载.md)。

## 五、Maven 如何把模块放进 classpath

假设启动模块声明：

```xml
<dependencies>
    <dependency>
        <groupId>com.example</groupId>
        <artifactId>rag</artifactId>
        <version>${project.version}</version>
    </dependency>
    <dependency>
        <groupId>com.example</groupId>
        <artifactId>agent</artifactId>
        <version>${project.version}</version>
    </dependency>
</dependencies>
```

而 `agent` 又依赖 `rag`，`rag` 又依赖 `framework`。Maven 会解析这张依赖图：

```text
bootstrap
├─ rag
│  └─ framework
└─ agent
   └─ rag
```

在编译 `bootstrap` 时，Maven 会把它直接和传递依赖的编译产物加入编译 classpath；在运行时，也会组装相应的运行 classpath。因此 `bootstrap` 能引用并运行 `rag` 和 `agent` 提供的类。

这不是 Maven 替 Spring “自动装配 Bean”。Maven 的职责只是依赖解析、编译和打包；Spring 的职责才是基于扫描、配置和自动配置，把某些 class 注册为 Bean。两者之间的连接点正是 classpath：Maven 让类可见，Spring 才有机会处理它们。

## 六、从源码到 Spring 容器的一条完整链路

将上述概念串在一起，某个跨模块 Controller 的出现过程如下：

```text
rag/src/main/java/
└─ com/example/ragent/rag/controller/RAGChatController.java
        ↓ javac
rag/target/classes/.../RAGChatController.class
        ↓ Maven 依赖解析
进入 bootstrap 的运行时 classpath
        ↓ Spring 组件扫描 com.example.ragent.**
读取 @RestController 元数据并注册 BeanDefinition
        ↓ Spring MVC 自动配置已生效
能够映射并处理 HTTP 请求
```

其中每个箭头都是独立环节。比如：

- POM 没有依赖 `rag`，则 Controller 根本不在运行时 classpath；
- Controller 的包改为 `org.other.rag`，默认扫描范围就无法覆盖它；
- 忘记 `@RestController`，类虽在 classpath 上也不会作为普通组件注册；
- 没有 Web MVC 环境，Controller 即使注册了也无法形成预期的 Servlet MVC 请求处理。

将失败精确归因到某一环，比把一切称为“Spring 没自动装配”有效得多。

## 七、Spring Boot 可执行 JAR 中的 classpath

开发期可以直接从多个 `target/classes` 目录和 JAR 中加载类。打成 Spring Boot 可执行 JAR 后，物理布局通常类似：

```text
bootstrap.jar
├─ BOOT-INF/classes/
│  └─ com/example/ragent/RagentApplication.class
└─ BOOT-INF/lib/
   ├─ rag-1.0.0.jar
   ├─ agent-1.0.0.jar
   ├─ framework-1.0.0.jar
   ├─ spring-context-*.jar
   └─ spring-webmvc-*.jar
```

普通 JVM 并不会天然把嵌套在 JAR 内的 JAR 当作标准 classpath 条目。Spring Boot 通过自己的启动器和类加载器处理 `BOOT-INF/classes`、`BOOT-INF/lib` 中的内容。因此它的物理实现比传统 `java -cp a.jar;b.jar` 更特别，但逻辑含义不变：应用和依赖模块的类对运行时可见。

## 八、总结

阅读多模块项目时，可以牢牢记住下面的分工：

- **模块目录和 POM**：定义构建单元与依赖关系；
- **`src/main/java`**：源码根目录，决定包路径从哪里开始计算；
- **Java package**：定义逻辑命名空间与完全限定类名；
- **classpath**：决定编译器、JVM 和 Spring 运行时能找到哪些类与资源；
- **Spring 扫描**：从 classpath 上、且处于扫描范围内的类中发现候选 Bean。

不同模块共享产品根包，是为了逻辑统一和扫描便利；不同模块的 JAR 出现在 classpath 中，是 Maven 依赖解析的结果。二者各自解决不同问题，少了任何一方，都不会自然得到“多个目录中的 Bean 被一个启动类管理”的效果。
