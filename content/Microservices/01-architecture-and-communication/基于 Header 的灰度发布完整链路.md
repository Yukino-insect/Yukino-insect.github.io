+++
date = '2026-02-19T21:51:11+08:00'
draft = false
title = '基于 Header 的灰度发布完整链路'
+++

灰度发布的本质是让一部分流量先进入新版本实例，其余流量继续访问旧版本。基于 Header 的灰度方案，是把“谁进入灰度”这个决策写入请求头，再由网关、负载均衡器和注册中心协同完成路由。

这类方案适合需要精确控制用户、租户、版本或实验分组的微服务系统。

## 核心链路

完整链路如下：

```text
用户请求
  -> 网关识别用户、租户、Cookie 或白名单
  -> 网关注入 X-Gray-Version: gray
  -> 网关路由或负载均衡读取 Header
  -> 选择 metadata=gray 的服务实例
  -> 下游服务继续透传灰度 Header
```

关键点不是“客户端带了一个 Header”，而是这个 Header 必须由可信入口生成，并在服务间调用时继续传递。

## Header 谁来设置

生产环境里，灰度 Header 通常由网关设置，而不是让用户手动设置。用户请求里即使带了 `X-Gray-Version`，网关也应该先清理，再按内部规则重新注入。

```java
@Component
public class GrayHeaderFilter implements GlobalFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest originalRequest = exchange.getRequest();
        String userId = originalRequest.getHeaders().getFirst("X-User-Id");

        ServerHttpRequest.Builder builder = originalRequest.mutate();
        builder.headers(headers -> headers.remove("X-Gray-Version"));

        if (hitGrayRule(userId)) {
            builder.header("X-Gray-Version", "gray");
        }

        return chain.filter(exchange.mutate().request(builder.build()).build());
    }

    private boolean hitGrayRule(String userId) {
        return userId != null && Math.floorMod(userId.hashCode(), 100) < 10;
    }
}
```

这里的 `10` 表示 10% 用户命中灰度。真实项目里一般从配置中心读取规则，而不是写死在代码里。

## 网关路由匹配

如果灰度版本有独立路由，可以直接在 Spring Cloud Gateway 中按 Header 匹配：

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: order-gray
          uri: lb://order-service
          predicates:
            - Header=X-Gray-Version, gray
          filters:
            - AddRequestHeader=X-Route-Stage, gray

        - id: order-stable
          uri: lb://order-service
          predicates:
            - Path=/order/**
```

仅靠 Gateway 路由还不够。`lb://order-service` 最终仍然会进入服务发现和负载均衡。如果新旧版本注册在同一个服务名下，就需要负载均衡根据实例 metadata 筛选。

## 服务实例标记

灰度实例通常通过注册中心 metadata 标记：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        metadata:
          version: gray
```

稳定版本：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        metadata:
          version: stable
```

负载均衡器读取请求 Header，再筛选匹配 metadata 的实例：

```text
X-Gray-Version=gray -> 只选择 version=gray 的实例
没有灰度 Header -> 选择 version=stable 的实例
```

如果没有匹配实例，应该有明确策略：回退稳定版本、直接失败，或按配置决定。多数业务更适合回退稳定版本，但涉及数据结构不兼容时不能盲目回退。

## 服务间透传

灰度请求进入第一个服务后，后续 Feign、RestTemplate、WebClient 调用也要继续透传 `X-Gray-Version`。否则只会第一跳命中灰度，第二跳又回到稳定版本，链路就裂开了。

Feign 拦截器示例：

```java
@Bean
public RequestInterceptor grayRequestInterceptor() {
    return template -> {
        ServletRequestAttributes attrs =
            (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();

        if (attrs == null) {
            return;
        }

        String grayVersion = attrs.getRequest().getHeader("X-Gray-Version");
        if (grayVersion != null && !grayVersion.isBlank()) {
            template.header("X-Gray-Version", grayVersion);
        }
    };
}
```

如果使用异步线程、消息队列或 Reactor，需要额外处理上下文传播，不能指望 ThreadLocal 自动生效。

## 常见灰度策略

| 策略 | 说明 | 适用场景 |
| --- | --- | --- |
| 白名单 | 指定用户、员工、租户进入灰度 | 内测、验收 |
| 百分比 | 按用户 ID 哈希后命中比例 | 稳定放量 |
| Cookie | 浏览器用户绑定灰度组 | 前后端联调、A/B |
| 地域 | 按地区或机房灰度 | 区域发布 |
| 版本 | App 版本、客户端类型 | 移动端兼容 |
| 租户 | 指定租户或企业客户 | SaaS 系统 |

百分比灰度要使用稳定 key，例如用户 ID 或租户 ID。不要用每次变化的随机数，否则同一个用户会在新旧版本之间来回跳。

## 发布阶段

比较稳的流程：

1. 部署灰度实例，注册为 `version=gray`，但默认不接流量。
2. 内部白名单验证核心链路。
3. 小比例放量，例如 1%、5%、10%。
4. 观察错误率、延迟、业务指标、日志和链路追踪。
5. 扩大比例到 30%、50%、100%。
6. 确认稳定后，把灰度版本提升为稳定版本。

## 回滚策略

灰度发布必须先设计回滚：

- 关闭灰度开关。
- 把比例调回 0。
- 删除或降低灰度实例权重。
- 回退服务版本。
- 回滚不兼容的配置。

真正麻烦的是数据兼容。如果新版本写入了旧版本不认识的数据结构，关闭路由也未必能安全回滚。因此数据库变更应尽量遵循“先兼容、再切流、最后清理”的节奏。

## 观测指标

灰度期间至少要按版本维度观察：

- 请求量。
- 错误率。
- P95 / P99 延迟。
- 核心业务转化率。
- 下游依赖失败率。
- JVM、线程池、连接池、数据库慢 SQL。
- 日志中的 traceId 和 gray 标记。

如果没有按版本拆分指标，灰度流量的问题会被总体指标稀释，等发现时可能已经扩大了影响面。

## 总结

基于 Header 的灰度不是单独一个网关规则，而是一条完整链路：网关注入、注册中心标记、负载均衡筛选、服务间透传、配置中心开关、指标观测和快速回滚。

只要其中一环断掉，所谓灰度就会变成“看起来分流了，实际上没有完全控制住”。这种事并不稀奇，只是上线前最好别假装它不会发生。
