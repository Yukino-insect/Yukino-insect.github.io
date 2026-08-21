+++
date = '2025-10-03T00:46:36+08:00'
draft = false
title = 'OpenFeign 服务调用'
+++

在单体应用中，模块之间通常是本地方法调用。拆成微服务后，订单、库存、用户、支付这些模块可能运行在不同进程、不同机器甚至不同网络里，调用方式就变成了远程调用。

OpenFeign 的价值在于：**把 HTTP 调用声明成 Java 接口，让调用方像调用本地方法一样调用远程服务**。它并没有消除网络调用的成本，只是把 URL 拼接、请求编码、响应解码、负载均衡、拦截器等细节交给框架统一处理。

## 服务调用方式

微服务之间常见调用方式有三类。

### HTTP REST

HTTP REST 最通用，调试简单，适合大多数业务系统。Spring Cloud OpenFeign 就是声明式 HTTP 客户端。

### RPC

Dubbo、gRPC 这类 RPC 框架通常使用更紧凑的协议和更明确的接口契约，性能和类型约束更强，但技术栈绑定也更明显。

### 消息队列

Kafka、RabbitMQ、RocketMQ 用于异步解耦。它适合事件通知、削峰、最终一致性，不适合要求调用方立刻拿到结果的查询链路。

## OpenFeign 是什么

几个名字容易混在一起：

- Feign：Netflix 的声明式 HTTP 客户端项目。
- OpenFeign：社区延续维护的 Feign。
- Spring Cloud OpenFeign：Spring Cloud 对 OpenFeign 的集成，支持 Spring MVC 注解、自动装配、服务发现和负载均衡。

在 Spring Cloud 项目里，日常说“Feign”通常就是指 Spring Cloud OpenFeign。

## 基本使用

调用方先启用 Feign 扫描：

```java
@EnableFeignClients
@SpringBootApplication
public class OrderApplication {
}
```

然后声明远程接口：

```java
@FeignClient(name = "user-service", path = "/api/users")
public interface UserClient {

    @GetMapping("/{id}")
    UserDTO getUser(@PathVariable("id") Long id);
}
```

业务代码中直接注入：

```java
@Service
public class OrderService {

    private final UserClient userClient;

    public OrderService(UserClient userClient) {
        this.userClient = userClient;
    }

    public OrderDetail getOrderDetail(Long orderId) {
        Order order = findOrder(orderId);
        UserDTO user = userClient.getUser(order.getUserId());
        return OrderDetail.of(order, user);
    }
}
```

这里的 `name = "user-service"` 通常对应注册中心里的服务名。调用时，Spring Cloud LoadBalancer 会根据服务名获取实例列表并选择一个实例。

## 与 RestTemplate 的区别

`RestTemplate` 是命令式 HTTP 客户端，需要手写 URL、参数、响应类型和错误处理。

```java
UserDTO user = restTemplate.getForObject(
    "http://user-service/api/users/{id}",
    UserDTO.class,
    userId
);
```

OpenFeign 则把这些信息收敛到接口声明上。

```java
@GetMapping("/{id}")
UserDTO getUser(@PathVariable("id") Long id);
```

如果只是少量内部调用，`RestTemplate` 或 `RestClient` 也可以工作；如果服务之间有大量稳定接口，OpenFeign 更利于统一管理调用契约、拦截器、超时、日志和降级。

## 负载均衡

OpenFeign 通常配合注册中心和 Spring Cloud LoadBalancer 使用。调用 `http://user-service` 这类服务名时，负载均衡器会从可用实例中选择一个。

常见策略：

- 轮询：按顺序把请求分配给实例，简单稳定。
- 随机：随机选择实例，实现简单。
- 权重：根据实例配置的权重分配流量。
- 一致性哈希：根据用户 ID、租户 ID 等 key 固定路由到特定实例。

默认策略适合实例能力接近、请求耗时接近的服务。若实例规格不同，或者存在灰度版本、租户隔离、粘性路由，就需要定制负载均衡策略。

## 超时与重试

远程调用一定要设置超时。没有超时的调用会拖垮线程池，进而把一个下游故障扩散成上游故障。

```yaml
spring:
  cloud:
    openfeign:
      client:
        config:
          default:
            connectTimeout: 2000
            readTimeout: 5000
```

重试要谨慎。查询类接口通常可以重试，创建订单、扣款、发券这类写接口必须先确认幂等能力，否则重试可能造成重复写入。

## 日志配置

Feign 内置四种日志级别：

| 级别 | 含义 |
| --- | --- |
| `NONE` | 不打印日志 |
| `BASIC` | 记录请求方法、URL、响应状态和耗时 |
| `HEADERS` | 在 `BASIC` 基础上记录请求头和响应头 |
| `FULL` | 记录请求和响应的完整内容 |

生产环境建议默认使用 `BASIC`，排障时再临时打开 `FULL`。全量日志可能输出请求体、响应体和敏感字段，不能长期无差别开启。

```yaml
logging:
  level:
    com.example.client: DEBUG

spring:
  cloud:
    openfeign:
      client:
        config:
          default:
            loggerLevel: basic
```

## 拦截器

Feign 拦截器常用于透传鉴权信息、租户信息和链路追踪 ID。

```java
@Bean
public RequestInterceptor requestInterceptor() {
    return template -> {
        ServletRequestAttributes attrs =
            (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();

        if (attrs == null) {
            return;
        }

        HttpServletRequest request = attrs.getRequest();
        copyHeader(request, template, "Authorization");
        copyHeader(request, template, "X-Trace-Id");
        copyHeader(request, template, "X-Tenant-Id");
    };
}

private void copyHeader(HttpServletRequest request, RequestTemplate template, String name) {
    String value = request.getHeader(name);
    if (value != null && !value.isBlank()) {
        template.header(name, value);
    }
}
```

注意不要无脑透传所有 Header。`Host`、`Content-Length`、内部网关标识、用户可伪造的灰度 Header，都应该由网关或服务端可信组件控制。

## 常见误区

1. 把 Feign 当成本地方法调用。远程调用会失败、超时、抖动，必须有超时、错误处理和观测。
2. Controller 直接调用 Feign。更推荐封装一层 Facade 或 Domain Service，统一处理异常和返回语义。
3. 写接口没有幂等设计。尤其是重试、熔断恢复、消息补偿都会放大这个问题。
4. 日志开到 `FULL` 后忘记关闭。排查结束就收回，否则成本和安全风险都会上来。
5. Provider 和 Consumer 各写一份接口。大型项目更适合抽出 `xxx-api` 契约模块。

## 总结

OpenFeign 解决的是“如何更规范地发起 HTTP 服务调用”，不是“远程调用就此变得可靠”。真正可靠的微服务调用，还需要服务发现、负载均衡、超时、熔断、降级、幂等、日志和链路追踪一起配合。

接口声明只是开始，工程约束才是重点。
