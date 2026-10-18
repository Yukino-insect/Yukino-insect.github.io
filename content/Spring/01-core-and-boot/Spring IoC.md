+++
date = '2025-09-17T20:47:04+08:00'
draft = false
title = 'Spring IoC'
+++

IoC 即控制反转。它将控制权从应用代码反转给容器

>  它不是什么技术，而是一种设计思想。在 Java 开发中，IoC 意味着将设计好的对象交给容器控制，而不是传统的在程序中直接`new`。

传统应用程序需要我们自己在程序中主动控制获取和管理依赖对象，这叫正转；而反转是由容器来帮忙创建对象并且注入依赖。

```java
// 传统
UserService service = new UserService(new UserRepository());
// IoC
// 交给容器来管理对象
UserService service = applicationContext.getBean(UserService.class);
```

### IoC 容器是什么

Java 程序将创建好的组件注册到 IoC 容器，然后应用程序需要什么外部资源就通过依赖注入 DI 从 IoC 容器中获取。

> “控制反转是通过依赖注入实现的”----从中可以看出**IoC是设计思想，DI是实现方式**

IoC 容器本质上是一个管理**Bean**及其依赖关系的容器。

在 Spring 中提供了两大核心 IoC 容器接口：

**BeanFactory**

- 最基础的 IoC 容器，只提供 Bean 的创建与依赖注入功能。
- **懒加载**（用到的时候才创建对象）。

**ApplicationContext**

- 是 BeanFactory 的子接口，功能更强大。
- 除了 IoC，还支持 **AoP、事件发布、国际化、自动装配** 等功能。
- **预加载**（启动时就把单例 Bean 全部实例化）。

> 什么是一个 Bean：它是一个被 IoC 容器管理的对象。任何一个交给 Spring 管理、在容器中被实例化、组装、管理的对象，都叫 **Bean**

这里只介绍`ApplicationContext`容器，也是最常用的

### 如何注册一个 Bean

这里只介绍使用注解的方法注册一个 Bean

#### 核心注解

Spring 提供了一组注解，用于标记类，使其自动被 **IoC 容器**扫描并注册为 Bean：

| 注解              | 作用            | 适用场景              |
| ----------------- | --------------- | --------------------- |
| `@Component`      | 通用组件        | 任意可管理的 Bean     |
| `@Service`        | 业务逻辑层      | Service 类            |
| `@Repository`     | 数据访问层      | DAO / Repository 类   |
| `@Controller`     | 控制器          | Web 层，处理请求      |
| `@RestController` | REST 风格控制器 | Web 层，返回 JSON/XML |

这些注解本质上都是 `@Component` 的派生，作用是告诉容器“这是一个 Bean”

Spring 想要找到这些注解并且注册为 Bean 需要扫描包

```java
@Configuration
@ComponentScan(basePackages = "com.example") // 扫描指定包及子包
public class AppConfig {}
```

**Spring Boot** 会自动扫描启动类所在包及其子包，因此只要类在启动类包下，用注解就会自动注册

**注册实例**

```java
@Component
public class MyComponent {
    public void doSomething() {
        System.out.println("执行 MyComponent 方法");
    }
}

@Service
public class UserService {
    public void registerUser(String name) {
        System.out.println("注册用户: " + name);
    }
}

@Repository
public class UserRepository {
    public void saveUser(String name) {
        System.out.println("保存用户: " + name);
    }
}

@Controller
public class UserController {
    @Autowired
    private UserService userService;

    public void createUser(String name) {
        userService.registerUser(name);
    }
}
```

> 这些注解在作用上并没有什么多大的区别，类名不同只是为了在不同业务语境下区别

#### @Configuration 和 @Bean 同样也可以注册 Bean

**@Bean**

是方法级注解，用来告诉容器这个方法返回的对象要注册为 Bean

它的每个 `@Bean` 方法就是一个 **Bean 的定义**，返回对象就是容器中的 Bean

**@Configuration**

是用来标记一个类为配置类，告诉 Spring 这是一个用来定义 Bean 的类，容器会扫描它的`@Bean`方法注册的 Bean。

```java
@Configuration
public class AppConfig {
    @Bean
    public UserService userService() {
        return new UserService(userRepository());
    }

    @Bean
    public UserRepository userRepository() {
        return new UserRepository();
    }
}
```

#### 获取 Bean

我们可以直接从`ApplicationContext`容器中获取 Bean

```java
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
UserService userService = context.getBean(UserService.class);
userService.registerUser("Tom");
```

`AnnotationConfigApplicationContext`是基于注解的配置类中获取 Bean 的实现。还有其他不同的实现获取 Bean

**通过依赖注入**

在 Spring 容器管理的类中，可以直接使用注解注入

**@Autowired** 

它是默认按类型自动注入 Bean

可与`@Qualifier` 配合按名称注入

该注解可以标注在字段、构造方法、Setter 方法上

```java
@Component
class UserService {
    public void hello() {
        System.out.println("Hello UserService");
    }
}

@Component
class UserController {
    @Autowired
    private UserService userService; // 按类型注入

    public void test() {
        userService.hello();
    }
}
```

当创建了多个相同类型的 Bean，这时就需要`@Qualifier`来通过名称指定使用哪个 Bean。

可以使用 `@Primary` 标记首选 Bean

```java
@Component("userServiceA")
class UserService {}

@Component("userServiceB")
class UserService {}

@Component
class UserController {
    @Autowired
    @Qualifier("userServiceB") // 按名称注入
    private UserService userService;
}
```

**@Resource**

Resource 是 JDK 提供的注解，而 Autowired 是 Spring 提供的注解

默认按名称注入，找不到再按类型注入

```java
@Resource(name="userServiceA") // 用 name 指定 Bean 名称
private UserService userService;
```

**@Inject**

按类型注入

```java
@Inject
private UserService userService;
```

> 在 Spring IoC 容器中，**同一个 Bean 默认是单例的（Singleton）**
>
> 但是可以通过控制 Spring 用于控制作用域的注解 `@Scope` 来改变它的生命周期
>
> ```java
> @Bean
> @Scopee("prototype")
> public UserService userService() {
>     return new UserService();
> }
> ```
>
> 相关作用域
>
> | Scope 名称    | 说明                                    |
> | ------------- | --------------------------------------- |
> | `request`     | 每个 HTTP 请求创建一个 Bean             |
> | `session`     | 每个 HTTP 会话创建一个 Bean             |
> | `application` | ServletContext 范围内单例，所有请求共享 |
> | `websocket`   | 每个 WebSocket 会话创建一个 Bean        |
