+++
date = '2025-09-20T21:43:00+08:00'
draft = false
title = 'Spring Boot 日志'
+++

Java 中的日志框架主要分两大类：**日志门面**和**日志实现**

日志门面定义了一组日志的接口规范，它并不提供底层具体的实现逻辑。`Apache Commons Logging` 和 `Slf4j` 就属于这一类

日志实现则是日志具体的实现，包括日志级别控制、日志打印格式、日志输出形式（输出到数据库、输出到文件、输出到控制台等）。`Log4j`、`Log4j2`、`Logback` 以及 `Java Util Logging` 则属于这一类

将日志门面和日志实现分离其实是一种典型的门面模式，这种方式可以让具体业务在不同的日志实现框架之间自由切换，而不需要改动任何代码，开发者只需要掌握日志门面的 API 即可。

日志门面一般是不单独使用的，它必须和一种具体的日志实现框架相结合使用。

### 日志级别

使用日志级别的好处在于可以通过调整级别来屏蔽掉很多调试相关的日志输出。不同的日志实现定义的日志级别有些不一样

**Java Util Logging**

`Java Util Logging` 定义了 7 个日志级别，从严重到普通依次是：

- SEVERE
- WARNING
- INFO
- CONFIG
- FINE
- FINER
- FINEST

因为默认级别是 INFO，因此 INFO 级别以下的日志，不会被打印出来。

**Log4j**

`Log4j` 定义了 8 个日志级别（除去 OFF 和 ALL，可以说分为 6 个级别），从严重到普通依次是：

- OFF：最高等级的，用于关闭所有日志记录。
- FATAL：重大错误，这种级别可以直接停止程序了。
- ERROR：打印错误和异常信息，如果不想输出太多的日志，可以使用这个级别。
- WARN：警告提示。
- INFO：用于生产环境中输出程序运行的一些重要信息，不能滥用。
- DEBUG：用于开发过程中打印一些运行信息。
- TRACE
- ALL 最低等级的，用于打开所有日志记录。

**Logback**

`Logback` 日志级别比较简单，从严重到普通依次是：

- ERROR
- WARN
- INFO
- DEBUG
- TRACE

在这里介绍一下 **classpath**

在 Java中，**classpath** 是一个非常核心的概念，它决定了 **Java 程序运行时如何找到类文件、资源文件和配置文件**

**什么是 classpath**

**classpath** 是指向 **Java 虚拟机（JVM）搜索类和资源文件的路径集合**。

它可以包含：

1. **目录**：存放 `.class` 文件或资源文件
2. **JAR 包**：存放编译后的类和资源

当程序运行时，JVM 会在 classpath 指定的路径中查找需要加载的类或资源。

**classpath 的作用**

1. **加载类**
   - JVM 会根据 classpath 查找 `.class` 文件。例如 `java.lang.String` 会从 JDK 自带的 rt.jar（或 JDK 模块）加载
2. **加载资源文件**
   - 例如 Spring Boot 的 `application.properties`、`application.yml`
   - `ClassLoader.getResource("application.properties")` 会从 classpath 查找
3. **决定依赖搜索**
   - 第三方库的 JAR 包也需要放到 classpath 中

**Spring Boot 中的 classpath**

项目中的`src/main/resources` 下的文件会被打包到 JAR 中，并放到 **classpath 根路径**

例如：

```bash
src/main/resources/application.yml
```

在程序中可以这样加载：

```java
Resource resource = new ClassPathResource("application.yml");
InputStream in = resource.getInputStream();
```

Spring Boot 会自动从 **classpath 根路径**加载 `application.properties` 或 `application.yml`

### Spring Boot 日志系统

Spring Boot 的日志系统是它的一个核心特性。默认情况下，Spring Boot 内置了 **Commons Logging** 作为桥接层，底层默认使用 **Logback** 作为实现，但可以自由切换成 Log4j2 或 Java Util Logging。

**配置日志级别**

可以在配置文件里修改日志级别：

application.properties

```
# 全局日志级别
logging.level.root=INFO

# 单个包
logging.level.com.example.demo=DEBUG

# 单个类
logging.level.com.example.demo.service.UserService=TRACE
```

配置日志输出文件

```
# 单个日志文件（默认放在项目根目录）
logging.file.name=app.log

# 或者指定目录（日志名为 spring.log）
logging.file.path=/var/logs
```

效果：

- 如果配置 `logging.file.name`，日志输出到该文件。
- 如果配置 `logging.file.path`，会在目录下生成 `spring.log`。

使用自定义日志配置文件

Spring Boot 会在 **classpath 根目录** 查找以下日志配置文件：

- **Logback**（默认优先级最高）
  - `logback-spring.xml`（推荐，可以使用 Spring 的扩展）
  - `logback.xml`
- **Log4j2**
  - `log4j2-spring.xml`
  - `log4j2.xml`
- **JUL**
  - `logging.properties`

Spring Boot 默认使用 **Logback**，所以最常见的就是写一个 `logback-spring.xml` 或 `logback.xml`。在这个文件里，可以配置：

1. **日志级别**

   - 指定不同包/类的日志级别（TRACE / DEBUG / INFO / WARN / ERROR）。

   ```xml
   <logger name="com.example.demo" level="DEBUG"/>
   ```

2. **日志输出位置**

   - 控制台、文件、远程 Socket 等。

   ```xml
   <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender"/>
   ```

3. **日志文件策略**

   - 滚动策略（按大小、按日期）、保留历史日志天数。

   ```xml
   <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
       <fileNamePattern>logs/app-%d{yyyy-MM-dd}.log</fileNamePattern>
       <maxHistory>7</maxHistory>
   </rollingPolicy>
   ```

4. **日志格式**

   - 自定义日志输出 pattern，比如：

   ```xml
   %d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n
   ```

5. **环境隔离**

   - `logback-spring.xml` 支持 `<springProfile>`，可以按环境加载不同的配置。

Spring Boot 的日志配置体系是这样的：

1. **application.yml / application.properties** 是提供简单的、开箱即用的日志配置，比如：

   ```
   logging:
     level:
       root: INFO
       com.example.demo: DEBUG
     file:
       name: /var/logs/app.log
   ```

   适合 **小规模配置**。

2. **logback-spring.xml / logback.xml** 用于**复杂、细粒度配置**，比如：

   - 多个 appender（控制台 + 文件 + Kafka）
   - 滚动策略
   - 不同环境的日志差异

**如果 classpath 中没有提供 logback 配置文件**，Spring Boot 会读取 `application.yml` 里的 `logging.*` 配置，自动生成默认的 Logback 配置。

**如果提供了 logback.xml**，Spring Boot 会 **完全忽略 `application.yml` 的 logging 配置**。因为 Logback 已经接管了日志系统。

**如果提供了 logback-spring.xml**，Spring Boot 会先解析 `application.yml`，然后把里面的属性注入到 `logback-spring.xml` 中。
这样就可以在 XML 里写：

```xml
<springProperty scope="context" name="LOG_PATH" source="logging.file.path"/>
<file>${LOG_PATH}/app.log</file>
```

配合 `application.yml`：

```yaml
logging:
  file:
    path: /var/logs
```

示例（logback-spring.xml）：

```xml
<configuration>
    <springProperty scope="context" name="LOG_PATH" source="logging.file.path"/>
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>
    <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_PATH}/app.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>${LOG_PATH}/app-%d{yyyy-MM-dd}.log</fileNamePattern>
            <maxHistory>7</maxHistory>
        </rollingPolicy>
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="STDOUT"/>
        <appender-ref ref="FILE"/>
    </root>
</configuration>
```

#### Spring Boot 中如何使用日志

Spring Boot 推荐使用 **SLF4J 接口** 来写日志（即便底层默认是 Logback）

```java
@Controller
public class HelloController {

    private static final Logger log = LoggerFactory.getLogger(HelloController.class); // SLF4J 

    @GetMapping("/hello")
    public String hello() {
        log.trace("This is a TRACE log");
        log.debug("This is a DEBUG log");
        log.info("This is an INFO log");
        log.warn("This is a WARN log");
        log.error("This is an ERROR log");
        return "Hello, Spring Boot Logging!";
    }
}
```

推荐使用 `@Slf4j` 注解，它由 Lombok 提供

```java
@Slf4j
public class MyService {
    public void doSomething() {
        log.info("Task running...");
    }
}
```

上面说的 spring boot 的桥接接口不是 Commons Logging 吗，为什么这里说的是 SLF4J 接口
在早期的 spring framework（没有 spring boot） 中使用的是 **Apache Commons Logging (JCL)** 作为日志门面。
 所以在 Spring 里常见这样的用法：

```java
private static final Log log = LogFactory.getLog(MyClass.class); // Commons Logging 
```

**Spring Boot 出来之后**，为了统一生态，内部还是保留 Commons Logging 作为“最上层门面”，但是底层用 **SLF4J + Logback** 实现。
 也就是说：

- **Spring Boot 自身**用 Commons Logging 来写日志（兼容老项目）
- **推荐开发者使用 SLF4J** 来写日志（面向未来、标准统一）

为什么推荐使用 SLF4J

1. **Spring Boot 已经自动桥接了**

   - Spring Boot 引入了 `spring-boot-starter-logging`
   - 里面包含：
     - `slf4j-api`（接口）
     - `logback-classic`（默认实现）
     - `jul-to-slf4j`、`jcl-over-slf4j`（桥接包）
   - 结果是无论是 Commons Logging、JUL、Log4j1 都会被桥接到 **SLF4J -> Logback**。

   所以即使用 `Commons Logging` 写日志，最终也会走到 Logback。

2. **SLF4J 是事实标准**

   - 几乎所有新框架（如 MyBatis、Hibernate、Spring Cloud 组件）都用 SLF4J。
   - SLF4J API 更简洁、生态更广。

3. **代码迁移方便**

   - 如果以后你不想用 Logback，可以很轻松切换到 Log4j2，只需要换一个实现依赖，不改业务代码
