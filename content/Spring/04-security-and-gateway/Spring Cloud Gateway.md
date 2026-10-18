+++
date = '2026-03-21T20:20:07+08:00'
draft = false
title = 'Spring Cloud Gateway'
+++

Spring Cloud Gateway

路由转发是最基本的能力，路由由这基本分组成

- `id`
- `uri`
- 一组 `predicates`
- 一组 `filters`

只有当这组断言匹配成功时，请求才会命中这条路由

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user-service
          uri: lb://user-service
          predicates:
            - Path=/user/**
```

这表示：只要请求路径匹配 `/user/**`，就把它转发给 `user-service`。

Predicate 断言

Gateway 用 **Route Predicate Factory** 来判断某个请求是否匹配路由。官方说明它是建立在 Spring WebFlux 的 `HandlerMapping` 基础设施之上的，支持很多内置断言工厂，并且可以用逻辑 `and` 组合。断言的输入是 `ServerWebExchange`，所以它可以根据请求的各种属性匹配，比如请求头、参数、路径、来源地址等

内置的常见断言包括：

- `Path`
- `Host`
- `Method`
- `Header`
- `Cookie`
- `Query`
- `RemoteAddr`
- `After` / `Before` / `Between`

例如 `RemoteAddr` 可用于基于客户端地址做匹配；如果网关在代理层后面，还可以用 `X-Forwarded-For` 的解析方式自定义远端地址解析。

Filter 过滤器

过滤器是 Gateway 最核心、最强大的部分之一。
 官方定义里，**Filter** 是由 `GatewayFilterFactory` 构建出来的 `GatewayFilter` 实例，可以在**下游代理请求前后**修改请求和响应。

Gateway 不只是能转发到固定 URL，还能配合注册中心和负载均衡使用。
 当路由的 URI 是 `lb://service` 这种格式时，`ReactiveLoadBalancerClientFilter` 会使用 Spring Cloud 的 Reactor LoadBalancer，把服务名解析成具体的主机和端口，并替换请求 URL。默认找不到实例时返回 503，也可配置成 404

Spring Cloud Gateway 是 Spring Cloud 体系中的 API Gateway，建立在 Spring Boot、Spring WebFlux、Project Reactor 之上，并依赖 Netty runtime。它的核心目标是把请求统一接入后，根据路由规则转发到下游服务，同时在网关层统一处理鉴权、限流、熔断、监控、Header 改写等横切逻辑。

它的核心模型是 Route、Predicate 和 Filter。Route 描述目标 URI、断言和过滤器；Predicate 负责判断当前请求是否命中某条路由；Filter 分为 GatewayFilter 和 GlobalFilter，可以在代理请求前后对请求和响应做统一处理。匹配流程上，请求先通过 Gateway Handler Mapping 匹配路由，命中后交给 Gateway Web Handler 组装过滤器链，先执行 pre 过滤逻辑，再通过 NettyRoutingFilter 或负载均衡过滤器发起下游请求，最后执行 post 过滤逻辑，并由 NettyWriteResponseFilter 将响应写回客户端。

Spring Cloud Gateway 的路由本质上来源于 `RouteDefinitionLocator`，默认从配置文件加载。要实现动态发布路由规则，一般会把路由定义放到数据库、Nacos 或 Redis 这类外部存储中，然后通过自定义 `RouteDefinitionLocator` 或官方 actuator 接口动态增删路由，再通过 `/actuator/gateway/refresh` 刷新路由缓存，使变更不重启即可生效。官方还支持通过 `RedisRouteDefinitionRepository` 在多个 Gateway 实例之间共享路由定义。

灰度发布的本质是让部分流量先进入新版本。最简单的方式是使用 Gateway 内置的 `Weight` 路由断言按比例放量；更稳定的方式是根据 Header、Cookie、Query、用户 ID 等特征做精确灰度，把测试用户或白名单用户路由到新版本。生产环境里还常结合注册中心实例 metadata，比如 `version=v1/v2`，再配合自定义负载均衡逻辑，把标记过的请求转发到对应版本实例。
