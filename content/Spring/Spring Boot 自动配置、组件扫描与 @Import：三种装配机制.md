+++
date = '2026-09-30T20:05:00+08:00'
draft = false
title = 'Spring Boot 自动配置、组件扫描与 @Import：三种装配机制'
+++
“Spring 自动装配”常被用来统称一切自动发生的事情：`@RestController` 被发现、`DataSource` 出现、Mapper 可以注入、某个 Starter 一引入 Web 服务就能跑。这个说法方便，却会遮住不同机制的边界；一旦启动失败，也就很难判断该查包扫描、POM 还是配置文件。

本文把最容易混淆的三种注册路径拆开：**组件扫描**负责发现业务组件，**Spring Boot 自动配置**负责按条件提供基础设施，**显式导入**负责精确地组合配置。它们最终都会把 Bean 放进同一个容器，但“为什么出现”完全不同。

## 一、先区分两个相近但不同的词

中文语境里的“自动装配”至少可能指两件事：

- **Bean 注册**：容器中为什么会有这个 Bean；
- **依赖注入**：已有 Bean 为什么会被注入到另一个 Bean 的构造器、字段或方法参数中。

例如：

```java
@Service
public class ChatService {
    private final ChatRepository chatRepository;

    public ChatService(ChatRepository chatRepository) {
        this.chatRepository = chatRepository;
    }
}
```

要让这段代码成立，至少发生两步：先通过扫描或配置把 `ChatService`、`ChatRepository` 注册进容器，再根据构造器参数按类型解析并注入 `ChatRepository`。后一过程是依赖注入；前一过程才是本文的重点。

## 二、组件扫描：寻找应用自己声明的组件

组件扫描的输入是一个或多个包路径，输出是对应包中带有组件语义的类定义。典型场景是业务代码：

```java
package com.example.ragent.rag.service;

import org.springframework.stereotype.Service;

@Service
public class RetrievalService {
}
```

`@SpringBootApplication` 默认包含 `@ComponentScan`。启动类在 `com.example.ragent` 包中时，`com.example.ragent.rag.service.RetrievalService` 位于其子包，便会成为扫描候选项。

扫描机制本身并不知道“RAG”或“用户”这些业务概念；它只依据包范围和注解元数据工作。Controller、Service、Repository、Configuration 的区别主要体现在语义、异常转换或 MVC 处理等后续机制上，而不是“是否能被扫描”的基本资格上。

```text
classpath 上的 class
        +
@ComponentScan 的包范围
        +
组件注解或可识别的配置声明
        ↓
BeanDefinition
        ↓
ApplicationContext
```

如果自定义组件没有被注册，首先应怀疑扫描包路径、模块依赖和注解，而不是先去修改 `application.yml`。

## 三、自动配置：根据条件补齐基础设施

一个 `@RestController` 被扫描到，并不意味着 HTTP 请求已经能抵达它。请求分发还需要 `DispatcherServlet`、HandlerMapping、消息转换器、嵌入式 Web 服务器等基础设施。绝大多数项目不会手工逐个定义这些 Bean，而是由 Spring Boot 自动配置完成。

`@EnableAutoConfiguration` 会从约定的位置导入许多自动配置候选类；当前 Spring Boot 主要使用：

```text
META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

自动配置类不会简单地“见到就执行”。它们会根据 classpath、配置属性和现有容器状态做条件判断：

```java
@AutoConfiguration
@ConditionalOnClass(name = "org.springframework.web.servlet.DispatcherServlet")
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class ExampleWebAutoConfiguration {
    // 示例：真实实现比这更复杂
}
```

可将这种决策简化为：

```text
classpath 有 Web MVC 相关类？
        + 是
当前是否为 Servlet Web 应用？
        + 是
用户是否已有更高优先级的自定义 Bean？
        + 否
        ↓
自动创建合理的默认基础设施 Bean
```

常见条件注解及其意义如下：

| 条件注解 | 判断内容 | 常见目的 |
| --- | --- | --- |
| `@ConditionalOnClass` | classpath 是否存在某个类 | 某技术依赖是否已引入 |
| `@ConditionalOnMissingBean` | 容器中是否缺少指定 Bean | 允许用户覆盖默认实现 |
| `@ConditionalOnProperty` | 某配置项是否满足条件 | 按开关启用功能 |
| `@ConditionalOnWebApplication` | 是否是指定类型的 Web 应用 | 区分 Servlet 与 Reactive 环境 |
| `@ConditionalOnBean` | 是否已有前置 Bean | 只在基础能力已就绪时扩展 |

所以，Web MVC Starter 的作用不是“给每个 Controller 自动添加注解”，而是把所需类和自动配置候选项带入项目，使 Boot 能建立 MVC 运行环境。业务 Controller 本身仍主要来自组件扫描。

## 四、Starter、自动配置和业务组件各做什么

下表适合用来厘清最常见的误解：

| 对象 | 主要职责 | 例子 |
| --- | --- | --- |
| Starter | 聚合并引入一组依赖 | `spring-boot-starter-web` |
| 自动配置 | 按条件注册默认基础设施 Bean | MVC、数据源、Jackson 配置 |
| 业务组件 | 承载项目业务逻辑 | `OrderService`、`RAGChatController` |
| 组件扫描 | 发现业务组件和项目配置类 | 扫描 `com.example.ragent.**` |

因此，下面两句话不能混为一谈：

- “引入 Web Starter 后，MVC 基础设施会被自动配置。”
- “把业务 Controller 放在启动类子包，并标记为 `@RestController` 后，它会被组件扫描发现。”

第一句说的是自动配置，第二句说的是组件扫描。两者缺任何一个，Web API 都可能无法正常工作。

更完整的 Spring Boot 基础介绍可参见[Spring Boot](/spring/springboot/)；如果要制作可复用的自定义自动配置，则应阅读[如何配置一个 Spring Boot Starter](/spring/如何配置一个-spring-boot-starter/)。

## 五、`@Import`：不依赖包扫描的显式组合

当你希望精确引入某个配置，而不是让它依靠包位置被“顺带扫到”时，可以使用 `@Import`：

```java
@Configuration
@Import({
        RagClientConfiguration.class,
        ObservabilityConfiguration.class
})
public class ApplicationConfiguration {
}
```

`@Import` 有几个适用场景：

- 引入另一个模块中明确的配置入口；
- 注册无法改动源码的第三方类型；
- 构建测试上下文，只加载少量目标配置；
- 编写库或 Starter，向使用方暴露受控的配置组合。

例如第三方 SDK 的客户端往往使用 `@Bean` 明确创建：

```java
@Configuration
public class AiClientConfiguration {
    @Bean
    public AiClient aiClient(AiClientProperties properties) {
        return AiClient.connect(properties.baseUrl(), properties.apiKey());
    }
}
```

这并不比组件扫描“低级”。组件扫描追求按约定批量发现，`@Import` 与 `@Bean` 追求明确的组合根。真实项目往往同时使用三种机制。

## 六、专用扫描与显式启用：不要都归到 `@ComponentScan`

一些框架提供的注解包含“扫描”或“启用”的名字，但它们并非普通的组件扫描。

### 1. `@MapperScan`

MyBatis Mapper 常是接口，需要运行时代理，因而需要 MyBatis 的注册器：

```java
@SpringBootApplication
@MapperScan("com.example.ragent.rag.dao.mapper")
public class RagentApplication {
}
```

### 2. `@EnableConfigurationProperties`

配置属性类通常不承载业务逻辑。通过它可显式启用绑定：

```java
@ConfigurationProperties(prefix = "ai.client")
public record AiClientProperties(String baseUrl, String apiKey) {
}

@Configuration
@EnableConfigurationProperties(AiClientProperties.class)
public class AiClientConfiguration {
}
```

### 3. `@EnableScheduling` 等功能开关

定时任务、异步执行、缓存、事务等能力往往有自己的启用入口。其含义是导入对应基础配置，并非在任意包中查找普通 `@Component`。

区分这些机制的好处很实际：Mapper 注入失败应检查 `@MapperScan` 和 MyBatis 配置；`@ConfigurationProperties` 未绑定应检查启用方式与属性前缀；它们都不应只靠增大 `scanBasePackages` 解决。

## 七、一个可复用的判断框架

当一个 Bean “为什么会出现”或“为什么没出现”时，可按以下问题判断：

```text
它是项目自己的带注解类？
  └─ 是：检查组件扫描范围、classpath 与条件注解

它是框架提供的默认基础设施？
  └─ 是：检查 Starter、自动配置条件、配置属性与用户自定义 Bean

它是第三方客户端或明确的模块配置？
  └─ 是：检查 @Bean、@Import、@Enable... 等显式入口

它是 Mapper 等代理接口？
  └─ 是：检查对应框架的专用扫描或注册机制
```

最后，所有这些路径汇聚到同一事实：BeanDefinition 被注册进 `ApplicationContext`，容器才可能解析依赖并创建实例。所谓“自动”，并不是没有规则；只是规则被框架组织在不同层次。把组件扫描、自动配置与显式组合分开理解，启动问题就不再是一团不透明的魔法。
