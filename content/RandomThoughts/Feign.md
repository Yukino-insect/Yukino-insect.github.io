+++
date = '2025-10-03T00:46:36+08:00'
draft = false
title = 'Feign'
+++

在传统的**单体应用**中，所有模块在同一个项目中，方法调用就是本地方法调用，速度快，但耦合度高。

而**微服务**将每个模块拆分成独立的服务，部署在不同的服务器上，模块之间的调用不再是方法调用，而是远程调用。所以必须有一套**服务发现**和**调用机制**

### 微服务之间的调用方式

#### HTTP REST 调用

最常见的方式，提供 REST API，服务之间通过 `HTTP` 调用

#### RPC 调用

常见的实现有 **gRPC/Dubbo**

服务之间基于二进制协议进行调用，效率比 HTTP 高

#### 消息队列异步调用

通过消息中间件（Kafka/RabbitMQ、RocketMQ），服务之间实现异步解耦

> 例如 ：
>
> OrderService 下单 -> 发送 `order_created` 消息
>
> InventoryService 订阅消息 -> 扣减库存

### 微服务调用的关键组件

在 Spring Cloud 微服务体系中，除了服务调用组件，还有以下关键的组件，一起实现微服务的核心功能

**注册中心（Eureka、Nacos、Consul）**

- 每个服务启动时注册到注册中心
- 其他服务通过服务名去注册中心获取实例地址

**服务调用（RestTemplate / Feign / gRPC）**

- 客户端调用另一个服务时，不需要写死 IP，而是用服务名
- 负载均衡器（Ribbon / Spring Cloud LoadBalancer）会选择一台实例

**配置中心（Nacos / Apollo / Spring Cloud Config）**

- 服务调用时可能依赖一些公共配置（比如超时时间、服务地址），统一管理

**网关（Spring Cloud Gateway / Nginx）**

- 对外统一入口
- 内部调用可以绕过网关直连，也可以统一走网关

> 假设有 **订单服务 (OrderService)** 和 **用户服务 (UserService)**：
>
> 1. UserService 启动 -> 注册到 **Nacos**，服务名 `user-service`
> 2. OrderService 需要调用 `user-service` -> 向 Nacos 请求 `user-service` 的实例列表
> 3. Ribbon / LoadBalancer 挑选一台 `user-service` 实例
> 4. 通过 HTTP/Feign 调用 `http://user-service/users/{id}`
> 5. UserService 返回数据 -> OrderService 处理

这里，我们只详细介绍一下**服务调用功能**

常用的服务调用客户端有 **RestTemplate、Feign、OpenFeign**

- **RestTemplate**：Spring 提供的 **命令式 HTTP 客户端**（自己写 URL、自己发请求、自己解析响应）。
- **Feign**：Netflix 开源的 **声明式 HTTP 客户端**（用接口+注解声明 HTTP 调用）。
- **OpenFeign**：社区维护的 Feign 分支；
- **Spring Cloud OpenFeign**：把 **OpenFeign 深度集成到 Spring 生态**（支持 Spring MVC 注解、自动装配、与 Spring Cloud 组件协同）。

> 从 Spring 6 开始，官方推荐新项目使用 **RestClient**（取代 RestTemplate 的新 API）。RestTemplate 仍可用，但基本进入维护模式。

#### RestTemplate（命令式客户端）

基本使用

```java
@Bean
@LoadBalanced  // 可选：让它支持服务名 + 负载均衡
public RestTemplate restTemplate() {
  return new RestTemplate();
}

// 使用
UserDTO dto = restTemplate.getForObject("http://user-service/api/users/{id}", UserDTO.class, 1001L);
```

#### Feign / OpenFeign（声明式客户端）

Feign vs OpenFeign vs Spring Cloud OpenFeign

- **Feign**：Netflix 原项目（后来停更）。
- **OpenFeign**：社区延续维护的 Feign。
- **Spring Cloud OpenFeign**：在 Spring 里“开箱即用”的集成包：
  - 让接口方法直接用 **Spring MVC 注解**（`@GetMapping` 等）；
  - 与 **Spring Cloud LoadBalancer**、**Nacos/Eureka**、**Resilience4j** 等无缝协同；
  - 支持 Bean 注入、拦截器、配置隔离等。

> 在 Spring Cloud 体系里，说“Feign”基本就是指 **Spring Cloud OpenFeign**。

基本用法

```java
@EnableFeignClients // 启用 Feign 扫描
@SpringBootApplication
public class App {
    
}

@FeignClient(name = "user-service") // 服务名，可自动负载均衡
public interface UserClient {
  @GetMapping("/api/users/{id}")
  UserDTO get(@PathVariable("id") Long id);
}

// 调用
@Autowired UserClient userClient;
UserDTO u = userClient.get(1001L);
```

> 在微服务里，一般会有两种角色：
>
> - **服务提供者（Provider）**：对外暴露 REST 接口。
> - **服务调用者（Consumer）**：通过 FeignClient 调用 Provider 的接口。
>
> 通常做法是：
>
> - Provider 写一个 `@RestController`，定义接口。
> - Consumer 写一个 `@FeignClient`，再定义一模一样的方法签名。
>
> 问题：接口定义重复了，既要写在 Controller，又要写在 Feign，维护起来容易出错。
>
> 为了解决这个问题，我们发现 Controller 可以继承 Feign 接口
>
> 比如这样：
>
> **公共接口定义（API 层）：**
>
> ```java
> @RequestMapping("/account")
> public interface AccountFeignClient {
> 
>     @GetMapping("/get/{id}")
>     AccountDTO getAccountById(@PathVariable("id") Long id);
> }
> ```
>
> **服务提供者（Provider）：**
>
> ```java
> @RestController
> public class AccountFeignController implements AccountFeignClient {
> 
>     @Override
>     public AccountDTO getAccountById(Long id) {
>         // 从数据库查数据返回
>         return accountService.findById(id);
>     }
> }
> ```
>
> **服务调用者（Consumer）：**
>
> ```java
> @FeignClient(name = "account-service")
> public interface AccountFeignClient {
>     @GetMapping("/account/get/{id}")
>     AccountDTO getAccountById(@PathVariable("id") Long id);
> }
> ```
>
> 这样做实现了
>
> **接口复用**
>
> - Provider 只需要实现 Feign 的接口，不用再写一份重复的 `@RequestMapping`。
> - Consumer 直接引用同一个接口，保证方法签名、路径、参数完全一致。
>
> **统一契约**
>
> - `AccountFeignClient` 就是“契约接口”（Contract）。
> - Provider 必须实现它，Consumer 调用它，避免接口不一致的问题。
>
> **减少重复代码**
>
> - 不用在 Controller 和 FeignClient 各写一份接口。
> - API 层抽取出来，Consumer 和 Provider 都用一份。
>
> **IDE/编译器检查**
>
> - 如果 Provider 的实现方法和接口不匹配，编译器会报错。
> - 保证接口规范强一致。
>
> #### 这种设计的典型场景
>
> - **大型微服务系统**：通常会单独建一个 `api` module，把 Feign 接口都放在里面。
>   - Provider 实现接口
>   - Consumer 引用接口
> - 避免接口的文档化问题，天然实现“接口即文档”。

**RestTemplate** 与 **OpenFeign** 都可以接入 **Spring Cloud LoadBalancer（SCLB）**，通过注册中心（Eureka/Nacos/Consul）按“服务名”调用，并在客户端完成 **轮询/自定义策略**

```java
// RestTemplate 方式
@Bean 
@LoadBalanced // 使用注解
public RestTemplate restTemplate(){ 
 return new RestTemplate();
}

// OpenFeign 方式（自动集成 SCLB）
// 只需 @EnableFeignClients + @FeignClient(name="xxx")
```

#### 轮询

**轮询**就是：把请求 **依次** 分配到可用的服务器/服务实例上，形成一种循环的调度方式。

例如有 3 台服务器：

- 第 1 个请求 -> Server A
- 第 2 个请求 -> Server B
- 第 3 个请求 -> Server C
- 第 4 个请求 -> 再回到 Server A
   ... 以此类推。

为什么要用轮询

- **简单**：实现容易，不需要复杂计算。
- **均衡**：理论上每个实例分到的请求数相近。
- **适合场景**：实例性能差不多、请求处理时间差不多。

##### 实现方式

方式一：简单计数器取模

```java
AtomicInteger counter = new AtomicInteger(0);

public Server getServer(List<Server> servers) {
    int index = counter.getAndIncrement() % servers.size();
    return servers.get(index);
}
```

> 每次计数器 +1，对服务器数取模，得到要选的实例。

方式二：平滑加权轮询（Weighted Round Robin）

有时服务器性能不同，要按权重分配流量。
 例如：

- A 权重 5
- B 权重 3
- C 权重 2
   10. 个请求 -> A 处理 5 个，B 3 个，C 2 个。

这样可以避免“短时间内倾斜”，分布更均匀。

##### 轮询的优点

- 算法简单、性能开销小；
- 对实例数目变化（新增/下线）能快速适应；
- 默认策略，很多框架都支持（Nginx、Ribbon、Spring Cloud LoadBalancer）。

##### 缺点

- **不考虑实例性能差异**：慢的机器也会分到同样的请求量；
- **不考虑请求开销**：如果有些请求特别耗时，可能导致不均衡；
- **无状态假设**：假设每个请求独立、服务无状态，否则“粘性”需求难满足。

在微服务里的应用

- **Spring Cloud LoadBalancer** 默认就是 **轮询**；
- **Nginx upstream** 默认也是 **轮询**；
- 如果要定制，可以换成：
  - 随机（Random）
  - 最小连接数（Least Connections）
  - 一致性哈希（Consistent Hashing）
  - 加权轮询（Weighted Round Robin）

#### 日志处理

Feign 内置了 4 种日志级别（枚举 `feign.Logger.Level`）：

| 级别      | 说明                                                 |
| --------- | ---------------------------------------------------- |
| `NONE`    | 默认，不打印任何日志                                 |
| `BASIC`   | 只记录请求方法、URL、响应状态码、执行时间            |
| `HEADERS` | 在 BASIC 基础上，记录请求和响应头                    |
| `FULL`    | 打印所有请求细节，包括 URL、方法、头、请求体、响应体 |

Spring Cloud 会根据 **Spring Boot 的日志配置**（logback/log4j）+ `feign.Logger.Level` 来决定日志输出。

##### 全局配置

使用配置文件

```yaml
logging:
  level:
    # 你自己 Feign Client 的包路径
    com.example.client: DEBUG
```

使用 Java

```java
@Configuration
public class FeignLogConfig {
    @Bean
    Logger.Level feignLoggerLevel() {
        return Logger.Level.FULL; // 全量日志
    }
}
```

##### 针对单个 Feigin Client 配置日志级别

在配置文件中

```yaml
feign:
  client:
    config:
      user-service:    # FeignClient 的 name
        loggerLevel: FULL
```

这样只有 `user-service` 的日志会打印详细信息，其他的还是默认

Java 配置方式

先在配置文件中打开日志

```yaml
logging:
  level:
    com.example.client.UserFeignClient: DEBUG
```

然后

```java
@FeignClient(
    name = "user-service", 
    configuration = UserFeignConfig.class // 单独配置类
)
public interface UserFeignClient {
    @GetMapping("/api/users/{id}")
    UserDTO getUserById(@PathVariable("id") Long id);
}
```

```java
// 不需要写 @Configuration，否则就成了全局日志配置
public class UserFeignConfig {

    @Bean
    public Logger.Level feignLoggerLevel() {
        // 只针对 user-service 的 FeignClient 生效
        return Logger.Level.FULL; 
    }
}
```
