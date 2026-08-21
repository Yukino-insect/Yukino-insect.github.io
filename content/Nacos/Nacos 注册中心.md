+++
date = '2026-08-21T20:10:00+08:00'
draft = false
title = 'Nacos 注册中心'
+++

Nacos 注册中心负责服务注册、服务发现、健康检查和实例元数据管理。它解决的不是“怎么调用 HTTP 接口”本身，而是“调用前怎么找到一个当前可用的服务实例”。

在微服务架构中，服务实例可能随时扩容、缩容、重启或迁移。如果消费者把提供者的 IP 和端口写死，就会导致服务变更成本很高。注册中心把这些动态地址集中管理起来，让消费者按服务名发现实例。

## 一、基本调用链路

一个典型服务调用过程如下：

```text
服务提供者启动
  -> 注册 order-service 实例到 Nacos
  -> 定期维持心跳或连接状态

服务消费者启动
  -> 从 Nacos 订阅 order-service
  -> 在本地缓存实例列表
  -> 调用时由负载均衡器选择一个实例
```

消费者通常不会每次请求都实时访问 Nacos。更常见的方式是客户端维护本地服务列表，Nacos 在实例变化时通知或让客户端刷新列表。这样可以减少注册中心压力，也能在 Nacos 短暂抖动时提升服务调用稳定性。

## 二、核心模型

Nacos 服务发现中的主要对象如下：

| 概念 | 说明 |
| ---- | ---- |
| Namespace | 顶层隔离单位，常用于环境或租户隔离 |
| Group | 服务分组，默认 `DEFAULT_GROUP` |
| Service | 服务名，例如 `order-service` |
| Cluster | 服务下的实例分组，常表示机房、区域、可用区 |
| Instance | 具体实例，包含 IP、端口、健康状态、权重等 |
| Metadata | 实例元数据，用于自定义路由或治理 |

示例结构：

```text
public
  -> DEFAULT_GROUP
    -> order-service
      -> shanghai-idc
        -> 10.0.0.11:8080 metadata={version=v1}
        -> 10.0.0.12:8080 metadata={version=v2}
```

消费者发现服务时，至少需要保证 **Namespace、Group、Service** 能对上。否则服务已经注册成功，消费者也可能完全发现不到。

## 三、接入 Spring Cloud Alibaba

服务发现依赖：

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
</dependency>
```

常见配置如下：

```yaml
server:
  port: 8081

spring:
  application:
    name: order-service
  cloud:
    nacos:
      discovery:
        server-addr: 127.0.0.1:8848
        namespace: public
        group: DEFAULT_GROUP
        cluster-name: shanghai-idc
        weight: 1
        metadata:
          version: v1
          tag: prod
```

配置完成并启动应用后，可以在 Nacos 控制台的服务列表中看到 `order-service`。

如果是 Spring Cloud 早期版本，可能还会看到 `@EnableDiscoveryClient`。在较新的 Spring Boot 自动装配场景中，只引入 starter 和配置通常就够了；是否显式加注解，要看项目版本和团队规范。

## 四、临时服务和持久服务

Nacos 中服务有临时服务和持久服务之分。这个差异会影响实例状态维护方式，也会影响一致性路径。

| 类型 | 状态维护 | 失效处理 | 适用场景 |
| ---- | -------- | -------- | -------- |
| 临时服务 | 依赖客户端连接、心跳或租约状态 | 实例失效后自动摘除 | 大多数业务微服务 |
| 持久服务 | 作为持久化资源管理 | 不应轻易自动删除，需要明确上下线 | 固定地址服务、基础设施或特殊治理场景 |

多数 Spring Cloud 微服务都使用临时服务：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        ephemeral: true
```

临时服务的好处是简单直接：应用挂了，实例会自动从可用列表中消失。这样消费者不容易继续请求一个已经不存在的节点。

持久服务更适合不希望因为短暂连接异常就被注册中心删除的场景。但使用持久服务时，运维侧必须有明确的上下线流程，否则消费者可能拿到已经不可用的地址。

## 五、健康检查

服务发现必须处理“实例是否可用”的问题。Nacos 会根据服务类型和客户端能力维护实例健康状态。

临时实例通常由客户端维持心跳或连接状态。如果实例长时间没有续约、连接断开或心跳超时，Nacos 会把它标记为不健康，进一步从可用列表中移除。

持久实例更偏管理型资源，可以使用服务端探测等方式维护健康状态。它不应该像普通临时微服务那样被轻易删除。

对业务调用来说，关键点是：消费者不应该只看实例是否存在，还应该尊重健康状态和权重。否则注册中心已经知道某个实例不健康，调用端却仍然把请求发过去，那就是调用端自己的问题了。

## 六、负载均衡

Nacos 返回的是服务实例列表，不等于替业务完成了所有负载均衡策略。真正选择哪一个实例，通常由消费者侧负载均衡组件完成，例如 Spring Cloud LoadBalancer、OpenFeign 集成的负载均衡能力，或网关中的服务发现组件。

常见策略有：

| 策略 | 说明 |
| ---- | ---- |
| 轮询 | 按顺序分配请求，适合实例能力接近的服务 |
| 随机 | 随机选择实例，简单直接 |
| 权重 | 按实例权重分配流量，适合灰度或机器规格不同的场景 |
| 同集群优先 | 优先调用相同 `cluster-name` 下的实例 |
| 元数据路由 | 根据 `metadata` 中的字段过滤实例 |

服务提供者可以配置权重：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        weight: 2
```

也可以配置集群名：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        cluster-name: shanghai-idc
```

如果消费者和提供者都配置了同一个 `cluster-name`，就可以配合同集群优先策略做就近调用。

## 七、Namespace、Group 和 Cluster 怎么选

常见实践如下：

| 维度 | 推荐用途 |
| ---- | -------- |
| Namespace | 区分环境，例如 dev、test、prod |
| Group | 区分业务线或系统，例如 ORDER_GROUP、PAY_GROUP |
| Cluster | 区分机房、区域、可用区 |
| Metadata | 区分版本、标签、灰度状态等实例属性 |

不要为了省事把所有环境都塞进同一个 Namespace，再靠 `tag=dev`、`tag=prod` 来隔离。`tag` 只是实例元数据，适合路由和灰度，不适合作为环境安全边界。

更稳妥的结构是：

```text
dev namespace
  -> DEFAULT_GROUP
    -> order-service

prod namespace
  -> DEFAULT_GROUP
    -> order-service
```

这样开发环境的消费者默认就发现不到生产环境的服务。

## 八、常见问题

### 1. 服务注册成功，但消费者发现不到

优先检查：

- `spring.application.name` 是否等于消费者要调用的服务名。
- Namespace 是否一致。
- Group 是否一致。
- Nacos 地址是否指向同一个集群。
- 服务实例是否健康。

### 2. 控制台能看到服务，但调用失败

注册成功只说明实例信息写进了 Nacos，不代表网络一定通。

还要检查：

- 消费者能否访问提供者注册的 IP。
- 容器部署时注册的是容器 IP 还是宿主机可达 IP。
- 防火墙、安全组、Kubernetes Service 是否放行。
- 提供者端口是否真实监听。

### 3. 实例下线后仍然被调用

可能原因包括：

- 客户端本地缓存尚未刷新。
- 负载均衡器没有过滤不健康实例。
- 使用了持久服务但没有正确下线实例。
- 服务进程没有正常注销，且健康检查配置不合理。

### 4. 前端能不能直接拿 Nacos 实例地址

一般不应该。前端应该访问网关或后端入口。服务发现、鉴权、灰度、限流和实例选择都应该放在后端治理层完成。让前端直接选择实例，会泄露部署细节，也会破坏流量治理。

## 九、总结

Nacos 注册中心的重点不是“把服务名和 IP 存起来”这么简单，而是围绕服务实例生命周期做管理：

- 服务启动时注册。
- 服务运行时维持健康状态。
- 服务变更时通知消费者。
- 消费者调用时按规则选择实例。
- 服务下线或故障时及时摘除。

把 Namespace、Group、Service、Cluster、Instance、Metadata 的边界分清，后面再看灰度发布、同机房优先和多环境隔离，就不会混成一团。混成一团当然也能跑，只是迟早会用生产事故来交学费，价格通常不太友好。
