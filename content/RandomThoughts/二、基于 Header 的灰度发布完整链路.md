+++
date = '2026-02-19T21:51:11+08:00'
draft = false
title = '二、基于 Header 的灰度发布完整链路'
+++

## 一、灰度发布的核心逻辑

灰度发布的本质是：让部分流量进入新版本实例，其余流量继续访问旧版本。

关键点：

- 不重启服务
- 不影响线上流量
- 可随时回滚
- 用户无感知

# 二、基于 Header 的灰度发布完整链路

完整流程如下：

```
用户请求
    ↓
网关（判断用户特征）
    ↓
网关注入 Header: X-Gray-Version=gray
    ↓
路由断言匹配
    ↓
转发到 gray 实例
```

# 三、Header 是谁设置的？

不是用户手动设置；是网关自动注入

生产环境流程：

```java
@Component
public class GrayHeaderFilter implements GlobalFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {

        String userId = exchange.getRequest().getHeaders().getFirst("X-User-Id");

        // 示例：按用户ID做灰度
        if (userId != null && userId.hashCode() % 10 == 0) {
            ServerHttpRequest newRequest = exchange.getRequest()
                .mutate()
                .header("X-Gray-Version", "gray")
                .build();

            return chain.filter(exchange.mutate().request(newRequest).build());
        }

        return chain.filter(exchange);
    }
}
```

# 四、网关路由如何匹配灰度？

在路由中增加断言：

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: order-gray
          uri: lb://order-service
          predicates:
            - Header=X-Gray-Version, gray
```

或者 Java 代码方式：

```java
.route("gray-route", r -> r
    .header("X-Gray-Version", "gray")
    .uri("lb://order-service"))
```

# 五、灰度策略可以有哪些？

企业级一般是多策略组合：

| 策略     | 说明           |
| -------- | -------------- |
| 白名单   | 指定用户ID     |
| IP 匹配  | 指定测试人员IP |
| 权重控制 | 10% / 30% 流量 |
| Cookie   | 内测标识       |
| AB 实验  | 分组实验       |

# 六、为什么用 Header？

相比其他方式：

| 方案    | 问题             |
| ------- | ---------------- |
| 修改URL | 侵入业务         |
| 改接口  | 破坏API规范      |
| 改参数  | 业务耦合         |
| Header  | 标准、解耦、透明 |

Header 优势：

- HTTP 标准机制
- 网关层可拦截
- 后端无需改代码
- 易于调试（抓包即可看到）

# 七、灰度实例如何区分？

一般通过：

- 不同 Nacos metadata
- 不同服务版本
- 不同部署标签

例如在 **Nacos** 中：

```yaml
metadata:
  version: gray
```

然后负载均衡器根据 metadata 筛选实例。

# 八、生产环境推荐架构

企业级推荐三阶段灰度：

### 第一阶段：白名单测试

```
指定内部员工ID
```

### 第二阶段：权重放量

```
10% -> 30% -> 50%
```

### 第三阶段：全量切换

```
100% 切换
```

# 九、回滚如何实现？

只需要：

- 删除灰度路由
- 或关闭灰度开关

无需重启服务。

这就是灰度发布的价值：

> 秒级回滚

# 十、用户是否有感知？

完全无感知

- 不需要登录不同地址
- 不需要切换环境
- 不知道自己是否进入灰度

整个过程发生在网关层。

------

# 十一、最终企业级最佳实践

推荐模式：

```
网关自动注入 Header
      +
服务注册中心 metadata 版本控制
      +
负载均衡实例筛选
      +
动态配置中心控制开关
```
