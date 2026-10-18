+++
date = '2025-09-20T20:32:27+08:00'
draft = false
title = 'Spring Boot'
+++

Spring Boot 是 Spring 生态的工程化框架。它并没有替代 Spring Framework，而是把 Spring 应用常见的依赖管理、自动配置、内嵌服务器、配置加载、监控和测试支持整理成一套默认方案。

一句话概括：**Spring Framework 提供能力，Spring Boot 负责把这些能力按约定组装成可启动的应用**。

## 一、Spring Boot 解决的问题

传统 Spring 项目常见问题如下：

| 问题 | 典型表现 | Spring Boot 的处理方式 |
| --- | --- | --- |
| 依赖版本难统一 | Spring MVC、Jackson、Tomcat、Validation 版本互相牵制 | 通过 Boot BOM 统一依赖版本 |
| 配置样板太多 | XML 或 Java Config 注册大量基础 Bean | 通过自动配置按条件创建默认 Bean |
| Web 部署繁琐 | 打 WAR 包部署到外部 Tomcat | 默认内嵌 Tomcat、Jetty 或 Undertow |
| 配置入口分散 | 不同模块各有配置方式 | 使用 `application.yml` / `application.properties` |
| 运维观测不足 | 健康检查、指标、环境信息要自己做 | 通过 Actuator 暴露运维端点 |
| 测试启动麻烦 | 手动准备容器和依赖 | 提供 `@SpringBootTest`、切片测试等工具 |

这些问题不是业务问题，却会持续消耗项目精力。Boot 的价值就在这里：把重复工程问题做成默认方案。

## 二、启动入口

一个最小 Spring Boot 应用通常长这样：

```java
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

`@SpringBootApplication` 是组合注解，核心包含三部分：

| 注解 | 作用 |
| --- | --- |
| `@SpringBootConfiguration` | 标记当前类是 Boot 配置类，本质是 `@Configuration` |
| `@EnableAutoConfiguration` | 开启自动配置，导入符合条件的自动配置类 |
| `@ComponentScan` | 默认扫描启动类所在包及其子包 |

因此启动类通常应该放在项目根包下。否则组件扫描范围变小，某些 `@Controller`、`@Service` 找不到，表面像框架失灵，实际只是包结构把自己绊倒了。

## 三、`SpringApplication.run` 做了什么

`SpringApplication.run` 不是单纯创建一个对象。它会完成应用启动的主流程：

```text
创建 SpringApplication
 -> 推断应用类型
 -> 准备 Environment
 -> 加载配置文件
 -> 创建 ApplicationContext
 -> 执行上下文初始化器
 -> 刷新容器 refresh()
 -> 创建 Bean
 -> 启动内嵌 Web 服务器
 -> 发布启动事件
 -> 执行 ApplicationRunner / CommandLineRunner
```

其中最关键的是两件事：

- **准备环境**：加载命令行参数、系统环境变量、配置文件、Profile 等配置源。
- **刷新容器**：执行 Spring Framework 的 `ApplicationContext#refresh()`，完成 BeanFactory 准备、BeanDefinition 加载、BeanPostProcessor 注册、单例 Bean 创建等工作。

Boot 的启动最终还是回到 Spring 容器生命周期。它只是把入口整理得更顺手。

## 四、自动配置

自动配置是 Spring Boot 最重要的机制。

它的基本思想是：

> 如果 classpath 中存在某类依赖，并且用户没有自己定义对应 Bean，Boot 就提供一套合理默认配置。

例如引入 `spring-boot-starter-web` 后，Boot 会根据条件自动配置：

- `DispatcherServlet`
- Spring MVC 基础组件
- Jackson JSON 转换器
- Bean Validation 集成
- 内嵌 Tomcat
- 静态资源映射
- 默认错误处理

### 1. 自动配置导入方式

Spring Boot 2.7 和 3.x 主要通过下面的文件声明自动配置类：

```text
META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

早期版本常见的是 `spring.factories`。如果在维护旧项目，看到它也不用惊讶，只是时代留下的接口。框架史有时也像考古，遗憾的是灰尘还会进 CI。

### 2. 条件注解

自动配置类通常不会无条件生效，而是配合条件注解：

| 注解 | 含义 |
| --- | --- |
| `@ConditionalOnClass` | classpath 中存在指定类时生效 |
| `@ConditionalOnMissingClass` | classpath 中不存在指定类时生效 |
| `@ConditionalOnBean` | 容器中存在指定 Bean 时生效 |
| `@ConditionalOnMissingBean` | 容器中不存在指定 Bean 时生效 |
| `@ConditionalOnProperty` | 配置项满足条件时生效 |
| `@ConditionalOnWebApplication` | 当前是 Web 应用时生效 |

例如：

```java
@AutoConfiguration
@ConditionalOnClass(RedisTemplate.class)
public class RedisAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public RedisTemplate<Object, Object> redisTemplate(RedisConnectionFactory factory) {
        RedisTemplate<Object, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(factory);
        return template;
    }
}
```

这段配置表达的是：只有项目里有 Redis 相关类，并且用户没有自己定义 `RedisTemplate` 时，Boot 才创建默认 Bean。

## 五、起步依赖

Starter 本质上是一组依赖集合，目的是让开发者不用逐个挑选兼容版本。

常见 Starter：

| Starter | 提供能力 |
| --- | --- |
| `spring-boot-starter-web` | Spring MVC、Jackson、Validation 集成、内嵌 Tomcat |
| `spring-boot-starter-validation` | Bean Validation 和 Hibernate Validator |
| `spring-boot-starter-aop` | Spring AOP 和 AspectJ 注解支持 |
| `spring-boot-starter-data-redis` | Redis 客户端、连接工厂、Template 支持 |
| `spring-boot-starter-security` | Spring Security 过滤器链和安全配置 |
| `spring-boot-starter-test` | JUnit、AssertJ、Mockito、Spring Test |
| `spring-boot-starter-actuator` | 健康检查、指标、环境信息等端点 |

Starter 不等于自动配置类。Starter 负责把依赖引进来，自动配置负责根据依赖和条件创建 Bean。两者经常配套出现，但职责不同。

## 六、配置加载

Spring Boot 统一使用 `Environment` 管理配置。常见配置源包括：

- 命令行参数
- Java 系统属性
- 操作系统环境变量
- `application.yml`
- `application.properties`
- Profile 配置，例如 `application-prod.yml`
- `@PropertySource`
- 默认配置

应用中常用两种方式读取配置：

```java
@Value("${app.name}")
private String appName;
```

更推荐用于结构化配置的是 `@ConfigurationProperties`：

```java
@ConfigurationProperties(prefix = "storage")
public class StorageProperties {
    private String endpoint;
    private String bucket;

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getBucket() {
        return bucket;
    }

    public void setBucket(String bucket) {
        this.bucket = bucket;
    }
}
```

`@Value` 适合少量简单值，`@ConfigurationProperties` 更适合一组有层次的业务配置。

## 七、内嵌服务器

Boot Web 应用默认以 JAR 方式运行，并在应用内部启动 Web 服务器。

常见选择：

- Tomcat：默认选择，Servlet 栈最常见。
- Jetty：轻量，某些场景下资源占用更低。
- Undertow：基于 XNIO，性能和吞吐表现较好。
- Netty：WebFlux 响应式栈常用，不属于 Servlet 容器。

对 Spring MVC 应用来说，启动流程大致是：

```text
SpringApplication.run()
 -> 创建 ServletWebServerApplicationContext
 -> refresh()
 -> 创建 WebServer
 -> 启动 Tomcat
 -> 注册 DispatcherServlet
 -> 应用开始接收请求
```

所以内嵌 Tomcat 并不是“先启动一个外部容器再部署应用”，而是 Spring Boot 在应用进程里创建并启动服务器。

## 八、Actuator

Actuator 提供生产环境常用的观测端点，例如：

| 端点 | 作用 |
| --- | --- |
| `/actuator/health` | 健康检查 |
| `/actuator/info` | 应用信息 |
| `/actuator/metrics` | 指标 |
| `/actuator/env` | 环境配置 |
| `/actuator/beans` | Bean 列表 |
| `/actuator/loggers` | 日志级别查看和调整 |

生产环境不要随便暴露所有端点，尤其是 `env`、`beans`、`heapdump` 这类敏感端点。能被观测是好事，被过度观测就成了事故预告。

## 九、测试支持

Boot 为测试提供了多种层级：

| 注解 | 适用场景 |
| --- | --- |
| `@SpringBootTest` | 启动完整 Spring 容器，做集成测试 |
| `@WebMvcTest` | 只测试 MVC 层 |
| `@DataJpaTest` | 只测试 JPA 持久层 |
| `@JsonTest` | 测试 JSON 序列化和反序列化 |
| `@MockBean` | 用 mock Bean 替换容器中的真实 Bean |

能用单元测试解决的问题，不要急着启动完整 Spring 容器。完整容器更接近真实环境，但代价是慢、重、故障原因更复杂。

## 十、总结

Spring Boot 的核心可以归纳成五句话：

- `@SpringBootApplication` 是启动入口，负责配置、自动配置和组件扫描。
- Starter 解决依赖组合和版本协调问题。
- 自动配置根据 classpath、配置项和容器状态创建默认 Bean。
- 配置加载把不同来源的配置统一放进 `Environment`。
- 内嵌服务器让应用可以直接以可执行 JAR 的方式运行。

理解 Boot 时不要只看它“省了多少配置”。真正重要的是：它用一套稳定约定，把 Spring 应用从“能运行”推进到“可维护、可部署、可观测”。这才是 Boot 存在的理由。
