+++
date = '2025-12-22T22:02:38+08:00'
draft = false
title = 'Spring'
+++

Spring Framework 的核心价值不是“提供很多注解”，而是把 Java 应用里最容易重复、最容易失控的基础能力收进框架：对象创建、依赖管理、横切逻辑、事务边界、事件通知、Web 请求处理和资源整合。

可以把 Spring 看成三层：

- **容器层**：IoC 容器负责创建 Bean、注入依赖、管理生命周期。
- **增强层**：AOP 在方法调用前后织入事务、日志、权限、监控等横切逻辑。
- **应用层**：MVC、事务、缓存、事件、安全、集成等模块都建立在容器和 AOP 之上。

所以学习 Spring 时，不必一开始就记住所有注解。先看清楚“谁创建对象、谁调用方法、谁接管请求、谁决定事务提交或回滚”，后面的知识才会各归其位。很遗憾，框架不会因为注解长得亲切就变简单，最多只是把复杂性包装得体面一些。

## 一、Spring 解决了什么问题

传统 Java 应用通常会遇到几类重复问题：

| 问题 | 传统写法 | Spring 的处理方式 |
| --- | --- | --- |
| 对象创建分散 | 到处 `new` 对象 | 由 IoC 容器统一创建和装配 |
| 依赖关系混乱 | 构造顺序和依赖链手动维护 | 通过依赖注入声明关系 |
| 横切逻辑重复 | 每个方法里写日志、事务、权限 | 通过 AOP 统一织入 |
| 事务边界不清 | 手动获取连接、提交、回滚 | 通过 `@Transactional` 声明事务 |
| Web 流程重复 | 手动解析请求和响应 | 由 Spring MVC 统一分发和转换 |
| 扩展点零散 | 各模块自己定义生命周期 | 通过 Bean 生命周期和后置处理器扩展 |

Spring 的基本思路是：**业务代码只表达业务依赖和业务动作，通用基础设施交给框架接管**。

## 二、IoC：对象由容器管理

IoC 是 Inversion of Control，控制反转。它反转的是对象创建和依赖组装的控制权。

没有 IoC 时，业务类通常自己创建依赖：

```java
public class OrderService {
    private final UserService userService = new UserService();
}
```

使用 Spring 后，业务类只声明自己需要什么：

```java
@Service
public class OrderService {
    private final UserService userService;

    public OrderService(UserService userService) {
        this.userService = userService;
    }
}
```

`OrderService` 不再关心 `UserService` 怎样创建、什么时候创建、是否需要代理、是否还有别的依赖。这些问题都交给容器。

### 1. 常见 Bean 来源

Spring 可以从多种入口注册 Bean：

- `@Component`、`@Service`、`@Repository`、`@Controller`
- `@Configuration` + `@Bean`
- `@Import`
- `FactoryBean`
- 自动配置类
- XML 配置

它们最终都会变成容器中的 `BeanDefinition`。`BeanDefinition` 描述的是“这个 Bean 应该怎样创建”，真正的对象实例会在后续生命周期中被创建出来。

### 2. 推荐注入方式

业务代码优先使用构造器注入：

```java
@Service
public class PaymentService {
    private final OrderRepository orderRepository;
    private final PayClient payClient;

    public PaymentService(OrderRepository orderRepository, PayClient payClient) {
        this.orderRepository = orderRepository;
        this.payClient = payClient;
    }
}
```

构造器注入的好处很直接：

- 依赖在对象创建时就完整，不容易出现半初始化状态。
- 字段可以声明为 `final`，语义更清楚。
- 单元测试时可以直接传入 mock 对象。
- 循环依赖更容易暴露，而不是被字段注入暂时掩盖。

字段注入虽然写起来短，但依赖关系隐藏在类内部，不利于测试和重构。它不是不能用，只是别把“少写几行”误认成“设计更好”。

## 三、AOP：在方法调用外层织入能力

AOP 是 Aspect-Oriented Programming，面向切面编程。它解决的是横切关注点重复散落的问题。

例如事务管理。如果不用 AOP，业务方法里会混入大量事务代码：

```java
public void createOrder() {
    transaction.begin();
    try {
        saveOrder();
        transaction.commit();
    } catch (Exception ex) {
        transaction.rollback();
        throw ex;
    }
}
```

使用 Spring 后，业务方法只声明事务边界：

```java
@Transactional
public void createOrder() {
    saveOrder();
}
```

Spring 会为 Bean 创建代理对象。外部调用代理方法时，代理在目标方法前后执行事务拦截器，决定创建事务、提交、回滚和清理资源。

### 1. Spring AOP 的核心限制

Spring AOP 基于代理，所以它主要有几个边界：

- 只拦截 Spring Bean 的方法调用。
- 默认只拦截外部通过代理对象发起的调用。
- 同类内部方法自调用不会经过代理。
- `final` 类或 `final` 方法不适合被 CGLIB 代理增强。
- JDK 动态代理基于接口，CGLIB 基于子类。

这也是很多 `@Transactional` 不生效问题的来源。不是注解突然心情不好，而是调用根本没有经过代理。

### 2. 常见 AOP 场景

Spring 生态中大量能力都依赖 AOP 或类似的拦截思想：

- 声明式事务：`@Transactional`
- 方法级权限：`@PreAuthorize`
- 缓存：`@Cacheable`、`@CacheEvict`
- 日志和审计
- 限流、幂等、分布式锁
- 参数校验和业务前置检查

其中事务、缓存、权限这类框架能力更适合使用声明式 AOP；高度业务化、分支很多的逻辑则不要强行塞进切面。

## 四、MVC：请求进入应用的主通道

Spring MVC 是 Spring 在 Servlet 体系上的 Web 框架。它的核心入口是 `DispatcherServlet`。

一次典型请求大致会经过下面的流程：

```text
HTTP request
 -> Servlet Filter
 -> DispatcherServlet
 -> HandlerMapping
 -> HandlerAdapter
 -> Controller method
 -> HandlerMethodReturnValueHandler
 -> HttpMessageConverter / ViewResolver
 -> HTTP response
```

其中几个组件最重要：

| 组件 | 作用 |
| --- | --- |
| `DispatcherServlet` | 前端控制器，统一接收请求并协调后续组件 |
| `HandlerMapping` | 根据请求路径、方法、条件找到处理器 |
| `HandlerAdapter` | 适配并调用 Controller 方法 |
| `HandlerMethodArgumentResolver` | 把请求数据解析成方法参数 |
| `HandlerMethodReturnValueHandler` | 处理 Controller 返回值 |
| `HttpMessageConverter` | 在 Java 对象和 HTTP body 之间转换 |
| `HandlerExceptionResolver` | 把异常转换成响应 |

理解这条链路后，`@RequestParam`、`@RequestBody`、`@ModelAttribute`、全局异常处理、自定义参数解析器都不再是孤立知识点。

## 五、事务：AOP 和资源管理的组合

Spring 事务的入口通常是 `@Transactional`，但真正执行事务的是事务拦截器和事务管理器。

一个声明式事务大致包含这些步骤：

1. AOP 代理拦截方法调用。
2. `TransactionInterceptor` 读取事务属性。
3. 选择合适的 `PlatformTransactionManager`。
4. 获取或创建事务资源，例如 JDBC `Connection`。
5. 执行业务方法。
6. 根据返回结果或异常决定提交还是回滚。
7. 清理线程绑定的事务上下文和数据库资源。

事务不是“给方法加个注解”这么轻。它牵涉代理、线程上下文、数据库连接、传播行为、隔离级别和异常规则。专题文章里再拆它，否则这篇总览会膨胀得很不体面。

## 六、Spring Boot 的位置

Spring Boot 不是 Spring 的替代品，而是 Spring 的工程化封装。

它主要做了几件事：

- 用起步依赖统一管理常用依赖组合。
- 用自动配置减少手动注册 Bean 的工作。
- 用内嵌服务器简化部署。
- 用 `application.yml` / `application.properties` 统一配置入口。
- 用 Actuator、测试支持、日志默认值提高工程可用性。

如果 Spring Framework 解决的是“框架能力如何工作”，Spring Boot 解决的就是“这些能力怎样被快速、稳定地组装成一个应用”。

## 七、模块之间的关系

可以用下面这张文字图理解 Spring 生态的层次：

```text
Spring Boot
  -> 自动配置、Starter、配置加载、内嵌容器

Spring Framework
  -> IoC 容器
  -> AOP 代理
  -> 事务、事件、缓存
  -> Spring MVC

扩展生态
  -> Spring Security
  -> Spring Cloud Gateway
  -> Spring Integration
  -> WebFlux / Reactor
```

Boot 负责装配，Framework 负责基础能力，扩展生态负责更具体的工程场景。

## 八、总结

学习 Spring 时，建议始终抓住四个问题：

- **对象从哪里来**：看 IoC、BeanDefinition、Bean 生命周期。
- **方法怎样被增强**：看 AOP、代理、拦截器链。
- **请求怎样被处理**：看 Spring MVC、参数解析、返回值处理、异常解析。
- **工程怎样启动和装配**：看 Spring Boot、自动配置、配置加载、Starter。

只要这四条线清楚，Spring 的大量注解就会从“需要背诵的符号”变成“挂在某条执行链路上的入口”。这才算真正理解它，而不是和注解进行一种礼貌但无效的寒暄。
