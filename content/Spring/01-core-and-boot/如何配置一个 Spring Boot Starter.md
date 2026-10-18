+++
date = '2025-09-26T19:06:54+08:00'
draft = false
title = '如何配置一个 Spring Boot Starter'
+++

配置一个 starter 需要引入一些依赖

```java
<dependencies>
<!-- 核心依赖：Spring Boot 自动配置 -->
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-autoconfigure</artifactId>
</dependency>

<!-- 让 @ConfigurationProperties 生效 -->
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-configuration-processor</artifactId>
  <optional>true</optional> <!-- 只在编译时处理，不打包 -->
</dependency>
```

然后定义配置类

```java
@ConfigurationProperties(prefix = "my.logger")
public class MyLoggerProperties {
    private String level = "INFO"; // 默认 INFO
    // getter / setter
}
```

`@ConfigurationProperties` 会读取配置类中以 `my.logger` 为前缀的配置文件

如果类上标注 `@Component` 注解，则它交给 spring 容器管理，可以直接使用

定义业务类

```java
public class MyLoggerService {
    private final String level;
    public MyLoggerService(String level) { this.level = level; }

    public void log(String msg) {
        System.out.println("[" + level + "] " + msg);
    }
}
```

它就是这个 starter 中实现功能的类

定义自动配置类

```java
@Configuration // Boot 2.x 用
@EnableConfigurationProperties(MyLoggerProperties.class)
@ConditionalOnProperty(prefix = "my.logger", name = "enabled", havingValue = "true", matchIfMissing = true)
public class MyLoggerAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public MyLoggerService myLoggerService(MyLoggerProperties properties) {
        return new MyLoggerService(properties.getLevel());
    }
}
```

`@EnableConfigurationProperties` 会让 `@ConfigurationProperties` 注解的类生效并将 `aplication.yml` 中的参数映射到类上，注册 `MyLoggerProperties` 为 bean。这种 bean 需要使用构造方法注入或者写在 `@Bean` 标注的方法参数上注入

> @EnableConfigurationProperties管理的 bean 只有在自动配置类真正加载时，Properties 才会被注册，避免无用的 Bean

**`@ConditionalOnProperty`** -> 只有在 `my.logger.enabled=true` 或没写时才生效

**`@ConditionalOnMissingBean`** -> 如果用户没有自定义 `MyLoggerService`，才注入默认的

注册自动配置类

spring boot 3 以前版本，在 `resources/META-INF/spring.factories` 中写

```properties
org.springframework.boot.autoconfigure.EnableAutoConfiguration=\
com.example.mylogger.MyLoggerAutoConfiguration
```

spring boot 2.7 往后也可以在 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` 中写

```java
com.example.mylogger.MyLoggerAutoConfiguration
```
