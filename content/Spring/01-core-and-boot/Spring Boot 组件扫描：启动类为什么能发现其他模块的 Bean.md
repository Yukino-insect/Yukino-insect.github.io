+++
date = '2026-09-30T20:00:00+08:00'
draft = false
title = 'Spring Boot 组件扫描：启动类为什么能发现其他模块的 Bean'
+++
在多模块项目中，经常会看到一个看似反直觉的现象：`bootstrap` 模块只有一个 `Application` 启动类，`controller`、`service`、`configuration` 却分散在多个 Maven 模块中；应用一启动，它们竟然都进入了同一个 Spring 容器。

这不是启动类逐个“启动”了其他模块，也不是每个模块都必须有自己的 `main` 方法。更准确地说，启动模块把依赖模块带入运行时 classpath，Spring 再从其中扫描符合规则的类并注册 Bean。**模块目录决定构建边界，包名决定默认扫描范围，classpath 决定运行时能否看见这些类。**

本文只讨论这条链路中的“组件扫描”一环：Spring 为什么能发现跨模块的业务 Bean，以及 Bean 没有被扫描到时应如何定位。

## 一、先建立正确的模型：一个应用上下文，而不是多个应用

假设项目具有如下结构：

```text
project/
├─ bootstrap/       启动模块
├─ framework/       公共 Web、异常处理等基础能力
├─ system/          用户、权限等业务能力
├─ rag/             检索增强生成业务
└─ agent/           Agent 业务
```

`bootstrap` 中的启动类如下：

```java
package com.example.ragent;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class RagentApplication {
    public static void main(String[] args) {
        SpringApplication.run(RagentApplication.class, args);
    }
}
```

其他模块可以各自提供业务类：

```java
package com.example.ragent.rag.controller;

import org.springframework.web.bind.annotation.RestController;

@RestController
public class RAGChatController {
}
```

```java
package com.example.ragent.agent.service;

import org.springframework.stereotype.Service;

@Service
public class AgentService {
}
```

应用运行后，通常只有一个由 `SpringApplication.run` 创建的 `ApplicationContext`。`RAGChatController`、`AgentService` 和启动模块中的 Bean 都注册在这个上下文里，并非 `rag`、`agent` 模块各启动了一个独立的 Spring Boot 服务。

这种形态称为**模块化单体**很合适：源码和构建上分模块，部署和进程上仍是一个应用。它与微服务不同；微服务通常有各自独立的启动入口、进程、端口和部署单元。

## 二、`@SpringBootApplication` 中真正负责业务扫描的部分

`@SpringBootApplication` 是一个组合注解。理解它时，应当把下面三项职责分开：

| 组成 | 主要职责 | 典型对象 |
| --- | --- | --- |
| `@SpringBootConfiguration` | 表明这是 Boot 配置入口 | 启动配置类 |
| `@ComponentScan` | 发现项目定义的组件 | Controller、Service、Configuration |
| `@EnableAutoConfiguration` | 按条件导入框架自动配置 | MVC、数据源、Redis 等基础设施 |

其中，**决定项目业务 Bean 扫描范围的是 `@ComponentScan`**。若没有显式配置 `scanBasePackages`，它会以启动类所在包作为基准，扫描该包及其子包。

因此上例中启动类位于 `com.example.ragent`，默认范围就是：

```text
com.example.ragent
├─ framework.**
├─ user.**
├─ rag.**
└─ agent.**
```

只要类在这个包前缀下，并且带有可识别的组件标记，Spring 就有机会发现它。模块位于 `rag/` 目录还是 `agent/` 目录，并不直接决定扫描结果。

### 1. 哪些注解会让类成为候选组件

最常见的候选组件注解如下：

| 注解 | 常见用途 | 与 `@Component` 的关系 |
| --- | --- | --- |
| `@Component` | 通用组件 | 基础标记 |
| `@Service` | 业务服务 | `@Component` 的派生注解 |
| `@Repository` | 数据访问组件 | `@Component` 的派生注解 |
| `@Controller` | MVC 控制器 | `@Component` 的派生注解 |
| `@RestController` | REST 控制器 | 间接带有组件标记 |
| `@Configuration` | Java 配置类 | 可作为配置候选项被处理 |
| `@RestControllerAdvice` | 全局 REST 异常处理 | 由 MVC 机制识别并注册 |

例如，下面的配置类会在扫描时被发现；随后其中 `@Bean` 方法返回的对象也会成为 Bean：

```java
package com.example.ragent.rag.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RagConfiguration {
    @Bean
    public DocumentSplitter documentSplitter() {
        return new DocumentSplitter();
    }
}
```

请留意因果顺序：组件扫描首先找到 `RagConfiguration`，配置类解析过程再执行 `@Bean` 方法的定义逻辑。不是扫描器直接“扫到了”`DocumentSplitter` 类。

### 2. 扫描的是已编译类，不是源码目录

初学者很容易把这一过程想成：Spring 从 Git 仓库根目录递归查找 `Controller.java`。实际情况并非如此。

启动阶段，Spring 面对的是类加载器可见的类和资源。它会在 classpath 中按包路径寻找类似以下资源：

```text
com/example/ragent/rag/controller/RAGChatController.class
com/example/ragent/agent/service/AgentService.class
```

然后读取类元数据，判断是否有合适的注解，最后生成 BeanDefinition。也就是说，一个组件能够被发现，至少要同时满足三个条件：

- 其编译产物或 JAR 已处于运行时 classpath；
- 它的完整包名落在组件扫描范围内；
- 它带有可识别的组件标记，或者通过其他配置方式被注册。

任意一个条件不成立，类都不会因“它在某个模块目录中”而自动成为 Bean。目录名称只是在源码阶段帮助 Maven 和开发者组织项目。

## 三、为什么统一根包在多模块单体中很常见

一个合理的多模块项目可能在物理上拆成多个模块，却共享一个产品根包：

```text
framework/src/main/java/com/example/ragent/framework/web/GlobalExceptionHandler.java
rag/src/main/java/com/example/ragent/rag/controller/RAGChatController.java
agent/src/main/java/com/example/ragent/agent/controller/AgentChatController.java
```

它们的完整包名并不相同：

```java
package com.example.ragent.framework.web;
package com.example.ragent.rag.controller;
package com.example.ragent.agent.controller;
```

相同的是共同前缀 `com.example.ragent`。将启动类放在这个根包下，能用一条默认规则覆盖所有模块的业务子包。这既减少扫描配置，也表达“它们属于同一个产品”的架构事实。

当然，这不是 Java 语言的强制要求。若包名不在同一根下，可以显式扩大范围：

```java
@SpringBootApplication(scanBasePackages = {
        "com.example.ragent",
        "org.example.shared"
})
public class RagentApplication {
}
```

这样做适用于接入外部公司库或历史模块。不过把无关包大面积加入扫描范围，会让启动边界逐渐模糊，甚至引入意外的同名 Bean。能通过稳定的根包约定解决的问题，通常没有必要用越来越长的 `scanBasePackages` 掩盖。

## 四、普通组件扫描并不覆盖所有类型

“带注解就能被扫描”只是常见情况，不是万能规律。有些对象需要专门的注册机制。

### 1. MyBatis Mapper：接口需要生成代理

MyBatis 的 Mapper 通常是接口：

```java
package com.example.ragent.rag.dao.mapper;

public interface KnowledgeMapper {
    KnowledgeEntity findById(Long id);
}
```

接口不能像普通 `@Service` 那样直接实例化。因此 MyBatis 需要扫描 Mapper 接口并为其生成代理对象，常见做法是：

```java
@SpringBootApplication
@MapperScan({
        "com.example.ragent.rag.dao.mapper",
        "com.example.ragent.user.dao.mapper"
})
public class RagentApplication {
}
```

`@MapperScan` 和 `@ComponentScan` 都含有“扫描”一词，但处理逻辑不同：前者注册的是 MyBatis Mapper 代理定义，后者寻找的是 Spring 组件候选项。不要因为二者名字相似就把它们视为同一机制。

### 2. 显式 `@Bean`、`@Import` 与第三方对象

无法修改源码的第三方类，通常不适合给它硬塞 `@Component`。应在配置类中显式注册：

```java
@Configuration
public class ClientConfiguration {
    @Bean
    public ExternalAiClient externalAiClient(AiProperties properties) {
        return new ExternalAiClient(properties.getApiKey());
    }
}
```

也可以通过 `@Import` 导入另一个配置类。它们在容器中同样会形成 Bean，但入口不是普通组件扫描。

## 五、Bean 没有被发现时的排查顺序

出现 `NoSuchBeanDefinitionException`、构造器注入失败，或 Controller 返回 404 时，按以下顺序检查会比盯着注解猜测可靠得多：

1. **检查运行时依赖。** 启动模块的 POM 是否依赖了目标模块？依赖作用域是否是运行时可用的 `compile` 或 `runtime`，而不是 `test`、`provided`？
2. **检查完整包名。** 目标类是否真在启动类所在包的子包下？IDE 的目录视图有时会隐藏真实包结构。
3. **检查注册方式。** 普通类是否使用了 `@Component`、`@Service` 等？Mapper、Servlet Filter、第三方客户端是否应使用各自的专用注册方式？
4. **检查条件。** 即使组件扫描到 `@Configuration`，其中的 `@Bean` 也可能受 `@Profile`、`@ConditionalOnProperty` 等条件限制而不生效。
5. **查看诊断信息。** 开启 Spring 的条件评估报告或 Actuator 的 `/actuator/beans`，确认 Bean 是否根本没有注册、注册后被条件排除，还是发生了注入歧义。

尤其不要忽略第一步：包名正确而 JAR 不在 classpath 时，扫描器没有任何对象可扫描。这部分与 Maven 依赖和 classpath 的关系，会在[Java 多模块项目中的包名、源码根目录与 classpath](/spring/java-多模块项目中的包名源码根目录与-classpath/)中展开。

## 六、总结

一个启动类能管理多个 Maven 模块中的 Controller 和 Service，靠的不是“跨模块启动”，而是一套连续条件：

- Maven 依赖把模块产物放入启动应用的运行时 classpath；
- `@SpringBootApplication` 默认从启动类包扫描其子包；
- `@Component`、`@Service`、`@RestController`、`@Configuration` 等标记让类成为候选组件；
- 所有发现并注册的 Bean 最终属于同一个 `ApplicationContext`。

因此，将启动类置于产品统一根包下、让各模块使用互不冲突的子包，是模块化单体中简单而有效的约定。至于 MVC、数据源等基础设施为什么会凭依赖出现，则属于自动配置而不是组件扫描，下一篇会把这两件常被混淆的事分开说明。
