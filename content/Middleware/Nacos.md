+++
date = '2026-08-21T20:30:00+08:00'
draft = false
title = 'Nacos'
+++

Nacos 是一个用于服务发现、配置管理和服务治理的平台。它在 Spring Cloud Alibaba 体系中很常见，通常同时承担注册中心和配置中心两个角色。

在微服务系统里，Nacos 解决两类核心问题：

- 服务实例在哪里，调用方如何发现它。
- 配置如何集中管理，并在运行时动态更新。

## 核心能力

Nacos 常用能力：

| 能力 | 说明 |
| --- | --- |
| 服务注册 | 服务启动后把自身地址注册到 Nacos |
| 服务发现 | 调用方从 Nacos 获取目标服务实例列表 |
| 健康检查 | 判断服务实例是否可用 |
| 配置管理 | 集中存储应用配置 |
| 动态刷新 | 配置变更后推送给客户端 |
| 命名空间 | 按环境或租户隔离资源 |
| 分组 | 在同一命名空间内进一步区分配置或服务 |

Nacos 不是业务网关，也不是负载均衡器本身。它提供服务实例信息，真正的请求转发通常由客户端负载均衡、网关或服务框架完成。

## 注册中心

服务启动时把自身注册到 Nacos：

```text
用户服务 user-service
  -> 注册 192.168.1.10:8080
订单服务 order-service
  -> 从 Nacos 查询 user-service 实例列表
  -> 选择一个实例发起调用
```

注册中心关心的是服务实例元数据：

- 服务名
- IP
- 端口
- 分组
- 命名空间
- 权重
- 健康状态
- 临时实例或持久实例

## 临时实例与持久实例

Nacos 服务实例通常分为临时实例和持久实例。

临时实例依赖客户端心跳。客户端下线或心跳超时后，Nacos 会自动摘除实例。

```text
服务实例 -> 定期心跳 -> Nacos
心跳停止 -> Nacos 标记不健康或删除实例
```

持久实例更适合需要人工维护、不会因为心跳停止立即删除的场景。

多数微服务应用使用临时实例即可。应用挂了就应该从可调用列表里消失，这一点不需要太复杂。

## 配置中心

Nacos 配置中心用来集中管理应用配置：

```text
应用启动
  -> 从 Nacos 拉取配置
  -> 合并本地配置
  -> 初始化 Spring Environment
  -> 监听配置变化
```

常见配置内容：

- 数据库连接参数
- Redis 地址
- MQ topic
- 业务开关
- 限流阈值
- 日志级别

不建议放入：

- 大文件
- 高频变化数据
- 用户业务数据
- 未加密的敏感密钥

配置中心不是数据库。把所有可变数据都塞进去，只会得到一个难以审计的数据库替代品，而且还没有数据库好用。

## Data ID、Group、Namespace

Nacos 通过三个维度定位配置：

```text
Namespace + Group + Data ID
```

### Namespace

Namespace 用于环境或租户隔离。常见用法：

| Namespace | 说明 |
| --- | --- |
| `dev` | 开发环境 |
| `test` | 测试环境 |
| `prod` | 生产环境 |

不同 Namespace 下可以存在相同的 Group 和 Data ID。

### Group

Group 用于在同一命名空间内进一步分组。默认值通常是 `DEFAULT_GROUP`。

常见用法：

- 按业务线分组。
- 按应用类型分组。
- 按公共配置和应用配置分组。

不要滥用 Group。环境隔离应该优先用 Namespace，而不是把 `DEV_GROUP`、`TEST_GROUP`、`PROD_GROUP` 全堆在同一个 Namespace 里。

### Data ID

Data ID 是配置集标识。Spring Boot 项目里常见命名：

```text
user-service.yaml
order-service.yaml
common.yaml
```

配置格式可以是：

- `yaml`
- `properties`
- `json`
- `text`

一个实用约定：

```text
应用配置：应用名.yaml
公共配置：common.yaml
环境隔离：Namespace
业务分组：Group
```

## Spring Boot 接入配置中心

示例配置：

```yaml
spring:
  application:
    name: user-service
  cloud:
    nacos:
      server-addr: 127.0.0.1:8848
      config:
        namespace: dev
        group: DEFAULT_GROUP
        file-extension: yaml
```

常见 Data ID 推导：

```text
${spring.application.name}.${file-extension}
```

如果应用名是 `user-service`，配置扩展名是 `yaml`，则默认会读取：

```text
user-service.yaml
```

也可以配置扩展配置：

```yaml
spring:
  cloud:
    nacos:
      config:
        extension-configs:
          - data-id: common.yaml
            group: DEFAULT_GROUP
            refresh: true
          - data-id: datasource.yaml
            group: DEFAULT_GROUP
            refresh: true
```

公共配置要控制粒度。公共配置越大，改一次影响的应用越多。

## 动态刷新

Nacos 支持配置变更后推送到客户端。Spring Cloud Alibaba 中常见做法是配合 `@RefreshScope`：

```java
@RefreshScope
@RestController
public class ConfigController {

    @Value("${feature.demo-enabled:false}")
    private Boolean demoEnabled;

    @GetMapping("/config/demo-enabled")
    public Boolean demoEnabled() {
        return demoEnabled;
    }
}
```

更推荐使用 `@ConfigurationProperties` 管理一组配置：

```java
@Data
@RefreshScope
@ConfigurationProperties(prefix = "feature")
@Component
public class FeatureProperties {

    private Boolean demoEnabled = false;
}
```

不是所有配置都适合动态刷新。数据库连接池、线程池大小、MQ 消费并发这类配置，即使能刷新，也要确认组件是否真的会重建或重新应用。

## Spring Boot 接入注册中心

示例配置：

```yaml
spring:
  application:
    name: user-service
  cloud:
    nacos:
      server-addr: 127.0.0.1:8848
      discovery:
        namespace: dev
        group: DEFAULT_GROUP
        cluster-name: SHANGHAI
```

服务启动后会注册到 Nacos。其他服务可以通过服务名发现实例：

```java
@RestController
public class OrderController {

    private final RestTemplate restTemplate;

    public OrderController(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @GetMapping("/orders/{id}/user")
    public String user(@PathVariable Long id) {
        return restTemplate.getForObject(
                "http://user-service/users/" + id,
                String.class
        );
    }
}
```

如果使用 Spring Cloud LoadBalancer，需要给 `RestTemplate` 加上 `@LoadBalanced`：

```java
@Bean
@LoadBalanced
public RestTemplate restTemplate() {
    return new RestTemplate();
}
```

真实项目里也常使用 OpenFeign：

```java
@FeignClient(name = "user-service")
public interface UserClient {

    @GetMapping("/users/{id}")
    UserDTO getById(@PathVariable("id") Long id);
}
```

## 权重和集群

Nacos 服务实例可以配置权重。权重越高，被客户端选中的概率越高。

常见用途：

- 灰度发布。
- 同机房优先。
- 临时降低某个实例流量。
- 下线前把权重调低。

集群名可用于同区域或同机房优先调用：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        cluster-name: HANGZHOU
```

服务治理要和部署拓扑一致。配置里写了集群名，但实际机器乱放，那就只是给混乱起了个名字。

## Nacos 服务端部署

开发环境可以单机启动，生产环境建议集群部署，并使用外部数据库存储元数据。

常见生产形态：

```text
客户端
  -> SLB / Nginx TCP 转发
  -> Nacos 集群
  -> 外部 MySQL
```

需要关注：

- Nacos 节点数。
- 外部数据库可用性。
- 服务端 JVM 参数。
- 端口映射。
- 控制台访问权限。
- 配置备份。
- 监控和告警。

## 端口注意事项

常见端口：

| 端口 | 说明 |
| --- | --- |
| `8080` | 控制台端口，部分新版本部署文档中作为默认控制台入口 |
| `8848` | Nacos 主服务端口，Spring Cloud Alibaba 客户端常见连接端口 |
| `9848` | Nacos 2.x 客户端 gRPC 通信端口，通常是主端口 + 1000 |
| `9849` | Nacos 2.x 服务端 gRPC 通信端口，通常是主端口 + 1001 |
| `7848` | 集群间通信相关端口 |

不同 Nacos 版本和部署方式的默认端口可能不同，应以当前服务端配置和官方部署文档为准。如果通过 Docker、Kubernetes、SLB、Nginx 或安全组暴露 Nacos，需要特别确认 `9848` 是否正确转发。很多客户端连接失败，并不是账号密码错，而是 gRPC 端口没有通。

生产环境不要把所有端口直接暴露到公网。控制台和服务端口都应放在内网或受控网络中。

## 配置管理建议

配置中心最怕“谁都能改，改了没人知道”。

建议：

- 按环境使用不同 Namespace。
- 生产配置开启权限控制。
- 敏感信息加密或放入专门的密钥系统。
- 重要配置变更走审批。
- 配置命名保持统一。
- 公共配置控制影响范围。
- 对关键配置增加默认值和校验。

应用启动时应校验关键配置：

```java
@PostConstruct
public void validate() {
    Assert.hasText(payUrl, "pay.url must not be blank");
}
```

配置缺失时快速失败，比带着错误配置运行更可靠。

## 常见问题

### 服务注册了但调用不到

检查：

- 服务名是否一致。
- Namespace 是否一致。
- Group 是否一致。
- 客户端是否启用负载均衡。
- 实例 IP 是否是可访问地址。
- 健康状态是否正常。

容器环境里尤其要注意注册 IP。应用如果把容器内网地址注册出去，其他服务可能根本访问不到。

### 配置不生效

检查：

- Data ID 是否正确。
- Namespace 是否填的是 ID，不只是名称。
- Group 是否一致。
- 文件扩展名是否一致。
- 是否使用了 bootstrap 阶段配置。
- 是否开启动态刷新。

### 配置刷新了但 Bean 没变化

可能原因：

- Bean 没有加 `@RefreshScope`。
- 使用了不可刷新的静态变量。
- 配置被读取后缓存到了其他对象里。
- 组件本身不支持运行时更新。

### 客户端连接 Nacos 失败

检查：

- `8848` 是否可访问。
- Nacos 2.x 所需的 `9848` 是否可访问。
- 服务端和客户端版本是否兼容。
- 网络代理或负载均衡是否支持对应协议。

## 使用建议

- 环境隔离用 Namespace，业务分组用 Group。
- Data ID 命名和应用名保持一致。
- 配置中心只放配置，不放业务数据。
- 生产环境开启鉴权和访问控制。
- Nacos 集群部署时使用外部数据库。
- 端口映射要同时关注 HTTP 端口和 gRPC 端口。
- 动态刷新只用于确实支持运行时变更的配置。

Nacos 的价值在于统一管理服务发现和配置。它让系统更灵活，也让错误配置的影响范围更大。用它时最重要的不是“能注册、能读取”，而是把隔离、权限、命名和变更流程设计清楚。
