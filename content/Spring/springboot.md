+++
date = '2025-09-20T20:32:27+08:00'
draft = false
title = 'Spring Boot'
+++

SpringFramework 的组件代码是轻量级的，但它的配置却是重量级的。它的痛点也不止于此

| 痛点             | 说明                                                         |
| ---------------- | ------------------------------------------------------------ |
| **繁琐的配置**   | XML 配置文件（`applicationContext.xml`、`springmvc.xml`）非常多，尤其是大型项目，扫描包、数据源、事务管理都需要手动配置。 |
| **依赖管理复杂** | Spring 各模块（Spring MVC、Spring JDBC、Spring Data 等）版本需要手动协调，容易出现依赖冲突。 |
| **启动部署繁琐** | 传统 Web 项目需要打成 WAR 包，部署到外部容器（Tomcat、Jetty）上。 |
| **自动化程度低** | 各模块集成需要手动配置，例如 Spring MVC + JPA + Redis。      |
| **测试困难**     | 单元测试和集成测试需要手动初始化 Spring 容器。               |
| **约定不统一**   | 不同团队可能会有不同的配置方式和包结构，学习成本高。         |

而 Spring Boot 是**Spring 生态下的一个开箱即用框架**，核心目标是**简化 Spring 应用的开发和部署**，尤其是企业级 Web 应用和微服务。它主要解决了传统 Spring 项目中繁琐的配置问题

| Spring Boot 特性                                  | 对应痛点解决方案                                             |
| ------------------------------------------------- | ------------------------------------------------------------ |
| **自动配置（Auto-Configuration）**                | 根据 classpath 的依赖自动配置 Bean，省去了大量 XML 配置。例如引入 `spring-boot-starter-web` 自动配置 DispatcherServlet、Tomcat、Spring MVC。 |
| **起步依赖（Starter POM）**                       | 一个依赖包搞定整个模块所需的依赖，解决版本管理和依赖冲突问题。例如 `spring-boot-starter-data-jpa`。 |
| **嵌入式服务器**                                  | 默认内置 Tomcat/Jetty，无需部署 WAR，可以直接运行 JAR 包。   |
| **约定优于配置（Convention over Configuration）** | 约定默认目录结构（`src/main/java`、`resources`），默认端口 8080，默认日志配置等，大大减少配置量。 |
| **简化测试**                                      | 提供 `@SpringBootTest` 注解，可以方便地启动整个容器进行集成测试。 |
| **现代微服务支持**                                | 内置 Actuator、REST API 支持、Spring Cloud 兼容，便于快速开发微服务。 |

在介绍 spring boot 的核心特点之前，先介绍一下 

#### `@SpringBootApplication` 注解

```java
@SpringBootApplication
public class App {
    public static void main(String[] args) {
        SpringApplication.run(App.class, args);
    }
}
```

`@SpringBootApplication` 是 Spring Boot 应用的核心入口注解，它本身是一个**组合注解**，把多个常用注解整合在一起，使应用可以“一步启动”。下面按组成注解说明它的作用：

**注解定义**

```java
@Target({ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
@Inherited
@SpringBootConfiguration
@EnableAutoConfiguration
@ComponentScan(
    excludeFilters = {@Filter(
    type = FilterType.CUSTOM,
    classes = {TypeExcludeFilter.class}
), @Filter(
    type = FilterType.CUSTOM,
    classes = {AutoConfigurationExcludeFilter.class}
)}
)
public @interface SpringBootApplication {
}
```

可以看到，`@SpringBootApplication` **包含三个核心注解**：

`@SpringBootConfiguration`

- **作用**：标记当前类是 Spring Boot 的配置类，相当于 `@Configuration` 的特化版本。
- 功能：
  - 告诉 Spring Boot 这是一个配置类
  - 可以定义 `@Bean` 方法
- 本质上是：

```java
@Configuration
public @interface SpringBootConfiguration {}
```

 `@EnableAutoConfiguration`

- **作用**：开启 Spring Boot **自动配置**功能。
- 功能：
  - 根据 classpath 中的依赖和条件注解（`@ConditionalOnClass`、`@ConditionalOnMissingBean` 等），自动配置 Bean。
  - 减少开发者手动配置。

`@ComponentScan`

- **作用**：启用组件扫描，将标注了 `@Component`、`@Service`、`@Repository`、`@Controller` 的类注册为 Spring Bean。
- 功能：
  - 默认扫描当前类所在包及子包
  - 支持排除过滤器（`excludeFilters`）排除不需要的组件

> 默认情况下，`@SpringBootApplication` 会扫描启动类所在包及其子包，所以推荐把启动类放在根包下。

可以看到 `SpringBootApplication` 就是作为 spring boot 的启动注解，用来开启 spring boot 项目

```java
ApplicationContext context = SpringApplication.run(App.class, args);
```

也可以拿到 spring 容器

#### 自动配置（Auto-Configuration）

Spring Boot 的**自动配置（Auto-Configuration）** 是它最核心的特性之一，它的实现机制主要依赖**条件注解（Condition）+ `spring.factories` / `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` + Spring 注解驱动**。

核心原理

Spring Boot 自动配置的基本思想是：

> 如果类路径中存在某些类，或者 Spring 容器中没有配置某个 Bean，就自动配置默认 Bean

**自动配置执行流程**

**Spring Boot 启动**，扫描 `@SpringBootApplication` 注解。注解内的`@EnableAutoConfiguration` 会触发 `AutoConfigurationImportSelector`。然后它会读取 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` 中的自动配置类列表。

遍历每个自动配置类，检查条件注解：`@ConditionalOnClass` / `@ConditionalOnMissingBean` / `@ConditionalOnProperty` 等。将符合条件的配置类注入到 Spring 容器，创建默认 Bean。

>  用户自己定义的 Bean 会覆盖自动配置的 Bean。

实现机制主要依赖以下三部分：

- `@EnableAutoConfiguration`，它其实就是`@Import(AutoConfigurationImportSelector.class)` 通过它触发**自动配置类的导入**。

- 自动配置类列表，Spring Boot 在 JAR 包 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` 文件里列出所有自动配置类。由 AutoConfigurationImportSelector 读取。再根据条件选择需要导入的配置类。

- 条件注解（Condition）
  - 自动配置类上通常有条件注解，如：
  - `@ConditionalOnClass`：当某个类在 classpath 中存在时生效
  - `@ConditionalOnMissingBean`：当容器中不存在某个 Bean 时生效
  - `@ConditionalOnProperty`：当某个配置属性存在或符合条件时生效

#### 起步依赖（Starter）

spring boot 提供了一组**起步依赖**，例如：

- `spring-boot-starter-web` 用于 Web 开发
- `spring-boot-starter-data-jpa` 用于 JPA 数据访问
- `spring-boot-starter-security` 用于 安全

在 Spring Boot 中，**Starter 依赖（starter dependency）** 是一个非常重要的概念，它的核心作用是**简化依赖管理和快速集成常用功能**。它本质上是一个**Maven 依赖包**，内部已经集成了某个功能模块所需的常用依赖。引入 starter 后，就无需手动去添加每个具体依赖，就能快速使用该模块功能。

**示例：**

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

这个 starter 包含了：

- Spring MVC (`spring-webmvc`)
- 内嵌 Tomcat (`tomcat-embed-core`)
- Jackson JSON 解析 (`jackson-databind`)
- Spring Boot 自动配置相关模块

能极大减少依赖导入和版本控制问题

```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.0</version>
</parent>
```

这段配置是 Spring Boot 项目中非常常见的**父 POM 声明**。声明当前项目继承自 `spring-boot-starter-parent`。

作用主要有三个：

1. **版本管理**：统一管理 Spring Boot 及其依赖的版本。
2. **默认插件配置**：Maven 编译、打包插件有默认配置。
3. **继承 `spring-boot-dependencies` 的依赖管理**。

统一版本管理（Dependency Management）

- 父 POM 内部引用了 `spring-boot-dependencies`。
- 子项目引入 Spring Boot starter 依赖时，不需要指定版本号，版本由父 POM 管理。

**示例：**

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

> 不需要写 `<version>`，版本由 `spring-boot-starter-parent` 提供。

默认 Maven 插件配置

- 父 POM 提供了 Maven 编译插件、打包插件、资源插件等的默认配置，不需要开发者在项目里手动配置这些插件。
- 例如：
  - Java 编译版本默认 17（对应 Spring Boot 3.x）
  - 打包为可执行 JAR
  - Spring Boot Maven 插件默认配置

继承 BOM（Bill of Materials）

- `spring-boot-starter-parent` 内部继承了：

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-dependencies</artifactId>
            <version>${spring-boot.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

作用：统一管理 Spring Boot 以及常用第三方库版本。保证所有依赖版本兼容，不用手动维护。

#### 内嵌服务器

Spring Boot 的 **内嵌服务器（Embedded Server）** 是它最核心的特性之一，它让 Spring Boot Web 应用**无需单独部署到外部 Tomcat/Jetty/Undertow**，直接运行 JAR 就能启动 Web 服务

我们只需要**引入依赖** `spring-boot-starter-web`，它内部已经引入了 **Tomcat** 依赖。

当启动配置时，Spring Boot 的自动配置类 `TomcatServletWebServerFactory` / `JettyServletWebServerFactory` / `UndertowServletWebServerFactory` 就会创建内嵌服务器 Bean。

**启动流程**

```
SpringApplication.run() ->
创建 ApplicationContext ->
自动配置 WebServerFactory Bean ->
启动内嵌服务器 (Tomcat/Jetty/Undertow) ->
部署 DispatcherServlet ->
应用就绪，监听端口
```

**运行 JAR** 时，直接执行 `java -jar app.jar`，内嵌服务器启动，Web 应用即可访问。

如果要使用其他服务器只需要将配置改为

```xml
<!-- 排除默认 Tomcat -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <exclusions>
        <exclusion>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-tomcat</artifactId>
        </exclusion>
    </exclusions>
</dependency>

<!-- 引入 Jetty -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-jetty</artifactId>
</dependency>
```

#### 配置文件支持

Spring Boot 支持以下配置文件类型：

| 文件类型  | 扩展名                   | 说明                         |
| --------- | ------------------------ | ---------------------------- |
| 属性文件  | `application.properties` | key-value 格式，经典配置方式 |
| YAML 文件 | `application.yml`        | 支持层级结构，适合复杂配置   |

默认情况下，Spring Boot 会自动加载 `classpath:/application.properties` 或 `classpath:/application.yml`。

**Spring Boot 提供 `@ConfigurationProperties` 注解，可以把配置文件内容绑定到 Java Bean 中，支持类型安全和嵌套属性。**

```yaml
app:
  name: MyApp
  version: 1.0
  datasource:
    url: jdbc:mysql://localhost:3306/test
    username: root
    password: 123456
```

```java
@Component
@ConfigurationProperties(prefix = "app")
public class AppConfig {
    private String name;
    private String version;
    private DataSourceConfig datasource;

    // getters and setters

    public static class DataSourceConfig {
        private String url;
        private String username;
        private String password;
        // getters and setters
    }
}
```

spring boot 自动将配置文件中 `app.*` 属性映射到 `AppConfig` 对象。

**配置不同环境文件**

Spring Boot 支持 **Profile（环境）** 概念，可以创建多个配置文件，命名方式

在 Spring Boot 中，按环境配置不同的配置文件是非常常见的做法，用于区分 **开发环境（dev）/测试环境（test）/生产环境（prod）** 的配置。命名方式

```bash
application-{profile}.properties
application-{profile}.yml
```

启动时如何选择配置文件

假设有如下配置文件

```bash
application.yml           # 默认配置，所有环境通用
application-dev.yml       # 开发环境配置
application-test.yml      # 测试环境配置
application-prod.yml      # 生产环境配置
```

在通用配置文件 application.yml  中指定

```yaml
spring:
  profiles:
    active: dev   # 激活开发环境
```

在启动时会自动加载 `application-dev.yml`，不同环境可以通过修改此字段切换

也可以通过命令行选择

```bash
java -jar app.jar --spring.profiles.active=prod
```

命令行参数优先级高于 application.yml 中配置

#### Actuator（监控）

Spring Boot 的 **Actuator** 是一个非常强大的模块，用于**监控和管理 Spring Boot 应用**，它可以帮助开发者快速获取应用健康状况、性能指标、日志信息等

使用 Actuator 时**引入依赖**

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

**配置端点暴露**

默认情况下，Actuator **只暴露少量端点**（`/actuator/health`、`/actuator/info`）。
 通过配置文件可以指定要暴露的端点：

```yaml
management:
  endpoints:
    web:
      exposure:
        include: "*"         # 开启所有端点
        # include: "health,info,metrics" # 仅开启指定端点
        # exclude: "beans"    # 排除某些端点
```

- `include`：允许访问的端点列表，`*` 表示全部
- `exclude`：排除端点

**配置端点路径**

默认端点路径是 `/actuator`，可以自定义：

```yaml
management:
  server:
    port: 8081                  # Actuator 端口，默认与应用端口相同
  endpoints:
    web:
      base-path: /manage        # 改变端点前缀，访问变为 /manage/health
```

**配置健康端点**

- 健康端点可以显示更多信息：

```yaml
management:
  endpoint:
    health:
      show-details: always       # always / when-authorized / never
```

- 健康状态中可以包含数据库、消息队列、磁盘空间等详细信息
- 与 `show-details` 配合安全策略可避免泄露敏感信息

**配置应用信息**

可以通过 `info` 端点显示应用版本、构建信息等：

```yaml
spring:
  application:
    name: myapp

info:
  app:
    version: 1.0.0
    description: "Spring Boot Actuator Demo"
```

通过访问 `/actuator/info`网络路劲，浏览器将返回

```json
{
  "app": {
    "version": "1.0.0",
    "description": "Spring Boot Actuator Demo"
  }
}
```

**配置安全访问**

如果项目使用了 **Spring Security**，可以控制端点访问：

```yaml
management:
  endpoints:
    web:
      exposure:
        include: "*" 
  endpoint:
    health:
      show-details: when-authorized
```

- 只有经过认证的用户才能看到详细信息
- 可以结合角色进行权限控制

访问示例：

- 健康状态：`http://localhost:8081/manage/health`
- 应用信息：`http://localhost:8081/manage/info`

#### 日志管理

- 默认集成 `Logback`。
- 支持通过配置文件统一管理日志级别和格式。
- 开发环境和生产环境可灵活切换日志配置。

#### 安全集成

spring boot 可快速集成 **Spring Security**。支持 **OAuth2**、**JWT** 等认证机制。

#### 测试支持

- 集成 Spring Test、JUnit 5、Mockito 等，方便单元测试和集成测试。
- 提供注解如：
  - `@SpringBootTest` -> 启动完整 Spring Boot 上下文
  - `@WebMvcTest` -> Web 层测试

#### DevTools & 热部署

- 内置热部署工具，可在开发时自动刷新应用。
- 提高开发效率，无需每次修改都手动重启。
