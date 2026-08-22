+++
date = '2026-08-22T00:10:00+08:00'
draft = false
slug = 'sentinel-dashboard-spring-boot'
title = 'Sentinel 控制台与 Spring Boot 接入'
+++

Sentinel 控制台用于查看客户端机器、资源实时指标，并在运行期下发规则。它不是业务服务的必需组件：客户端没有控制台也能通过本地代码或动态数据源加载规则。但在学习和排查阶段，控制台非常直观。

这篇只讲一件事：如何把一个 Spring Boot / Spring Cloud Alibaba 应用接入 Sentinel Dashboard，并确认它真的工作了。

## 一、启动 Dashboard

Sentinel Dashboard 是一个标准 Spring Boot 应用，可以直接运行官方发布的 jar 包。

示例命令：

```powershell
java -Xms512m -Xmx512m -XX:+UseG1GC `
  -Dserver.port=8858 `
  -Dcsp.sentinel.dashboard.server=localhost:8858 `
  -Dproject.name=sentinel-dashboard `
  -jar sentinel-dashboard-1.8.6.jar
```

Linux / macOS 可以写成：

```bash
java -Xms512m -Xmx512m -XX:+UseG1GC \
  -Dserver.port=8858 \
  -Dcsp.sentinel.dashboard.server=localhost:8858 \
  -Dproject.name=sentinel-dashboard \
  -jar sentinel-dashboard-1.8.6.jar
```

参数含义：

| 参数 | 含义 |
| --- | --- |
| `-Dserver.port` | Dashboard Web 端口 |
| `-Dcsp.sentinel.dashboard.server` | Dashboard 自身上报地址 |
| `-Dproject.name` | Dashboard 进程显示名称 |
| `-Xms` / `-Xmx` | JVM 堆内存 |

访问地址：

```text
http://localhost:8858
```

默认账号密码通常是：

```text
sentinel / sentinel
```

> 如果端口冲突，改 `-Dserver.port` 即可。原文里常见的 `-Sproject.name` 是笔误，正确参数是 `-Dproject.name`。

## 二、接入客户端依赖

Spring Cloud Alibaba 项目通常引入：

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-sentinel</artifactId>
</dependency>
```

版本建议交给 Spring Cloud Alibaba BOM 管理，不要在业务模块里随手写一个孤立版本。Sentinel 与 Spring Boot、Spring Cloud、Spring Cloud Alibaba 之间有版本适配关系，硬凑版本很容易出现自动配置不生效、Endpoint 不存在或依赖冲突。

一个简化的 Maven 结构如下：

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-alibaba-dependencies</artifactId>
            <version>${spring-cloud-alibaba.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

业务模块再引入 starter：

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-sentinel</artifactId>
</dependency>
```

## 三、配置客户端上报

在应用配置文件中增加：

```yaml
spring:
  application:
    name: order-service
  cloud:
    sentinel:
      transport:
        dashboard: localhost:8858
        port: 8719
```

两个配置不要混淆：

- `dashboard`：Sentinel Dashboard 地址，客户端会向它发送心跳。
- `port`：客户端本机启动的通信端口，Dashboard 下发规则时会访问这个端口。

也就是说，控制台并不是主动扫描全网机器。客户端启动后会向 Dashboard 上报心跳，Dashboard 才能在机器列表看到它。

通信关系如下：

```text
业务应用
  ├─ 主服务端口：8080
  └─ Sentinel transport port：8719
          ↑
          │ Dashboard 推送规则、查询客户端信息
          │
Sentinel Dashboard：8858
```

## 四、准备一个测试接口

示例 Controller：

```java
@RestController
@RequestMapping("/orders")
public class OrderController {

    @GetMapping("/{id}")
    public String getOrder(@PathVariable Long id) {
        return "order:" + id;
    }
}
```

启动应用后，先访问一次接口：

```http
GET http://localhost:8080/orders/1
```

Sentinel 的很多资源统计是懒加载的。也就是说，不访问接口时，控制台可能看不到对应资源；先有请求，才有资源统计。

## 五、在控制台确认接入

打开 Dashboard 后检查：

1. 左侧应用列表是否出现 `order-service`。
2. 机器列表是否有当前应用 IP 和端口。
3. 实时监控里是否能看到请求 QPS 和响应时间。
4. 簇点链路里是否出现 `/orders/{id}` 或实际 URL 资源。

如果应用列表为空，优先排查：

- 客户端是否真正引入了 `spring-cloud-starter-alibaba-sentinel`。
- `spring.application.name` 是否存在。
- `spring.cloud.sentinel.transport.dashboard` 地址是否正确。
- 应用是否访问过受保护资源。
- Dashboard 所在机器能否访问客户端的 `transport.port`。
- 防火墙、容器端口映射、安全组是否放行。

## 六、配置一个限流规则

在控制台的簇点链路里找到接口资源，添加流控规则：

| 字段 | 示例值 |
| --- | --- |
| 资源名 | `/orders/{id}` 或实际显示资源 |
| 阈值类型 | QPS |
| 单机阈值 | `1` |
| 流控模式 | 直接 |
| 流控效果 | 快速失败 |

然后连续快速访问接口。

正常结果：

- 每秒允许少量请求通过。
- 超过阈值的请求被 Sentinel 拦截。
- 控制台实时监控中出现通过 QPS 和拒绝 QPS。

如果项目没有自定义异常处理，默认返回可能不够友好。生产项目通常会统一处理 `BlockException`，或者在局部资源上配置 `blockHandler`。

## 七、统一处理限流异常

Spring MVC 项目可以增加统一异常处理：

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BlockException.class)
    public ResponseEntity<String> handleBlockException(BlockException ex) {
        return ResponseEntity
                .status(429)
                .body("系统繁忙，请稍后再试");
    }
}
```

更细致一些，可以按子类区分：

```java
@ExceptionHandler(BlockException.class)
public ResponseEntity<String> handleBlockException(BlockException ex) {
    if (ex instanceof FlowException) {
        return ResponseEntity.status(429).body("请求过多，请稍后再试");
    }
    if (ex instanceof DegradeException) {
        return ResponseEntity.status(503).body("服务暂时不可用，请稍后再试");
    }
    if (ex instanceof SystemBlockException) {
        return ResponseEntity.status(503).body("系统压力过高，请稍后再试");
    }
    return ResponseEntity.status(429).body("请求被 Sentinel 拦截");
}
```

`BlockException` 不应该按系统错误处理。它是 Sentinel 明确发出的流量治理信号，状态码通常选择 `429` 或 `503`，具体取决于业务语义。

## 八、常见接入问题

### 1. 控制台看不到应用

常见原因：

- 应用没有访问任何资源。
- `spring.application.name` 为空。
- `dashboard` 地址写错。
- 客户端和 Dashboard 网络不通。
- 应用启动失败或 Sentinel 自动配置未生效。

排查顺序：

```text
确认依赖
  ↓
确认配置
  ↓
访问一次接口
  ↓
看应用日志
  ↓
检查 Dashboard 机器列表
  ↓
检查网络和端口
```

### 2. 机器出现了，但规则不生效

检查：

- 规则资源名是否和实际资源名完全一致。
- 是否配置到了错误应用。
- 是否使用了 URL 资源而代码里访问的是 `@SentinelResource` 资源。
- 是否后续又被动态数据源加载的规则覆盖。
- 是否应用重启导致内存规则丢失。

Sentinel 规则匹配资源名，资源名错一个字符，规则就不会命中。很朴素，也很残酷。

### 3. 控制台配置的规则重启后消失

这是正常现象。Dashboard 默认下发到客户端内存，生产环境应接入 Nacos、Apollo、ZooKeeper、Redis、文件等动态数据源。

控制台负责“看见和操作”，动态数据源负责“可靠保存和恢复”。把两者混在一起，是很多 Sentinel 初学事故的开始。

### 4. `transport.port` 端口冲突

`spring.cloud.sentinel.transport.port` 是客户端本机端口。如果一台机器部署多个应用实例，端口可能冲突。

可以为不同实例配置不同端口，或让 Sentinel 尝试自动寻找可用端口。生产环境更推荐显式配置和暴露端口，排查时比较省心。

## 九、最小接入清单

接入完成前，至少确认下面几点：

- Dashboard 能正常打开。
- 客户端引入 Sentinel starter。
- `spring.application.name` 已配置。
- `spring.cloud.sentinel.transport.dashboard` 指向 Dashboard。
- 客户端 `transport.port` 能被 Dashboard 访问。
- 至少访问过一次接口。
- 控制台机器列表能看到应用。
- 配置一条简单 QPS 规则后能触发 `FlowException`。

这些都通过以后，才算 Sentinel 接入基本完成。至于规则怎么设计、怎么持久化、怎么和业务降级配合，那是后面的事。一步一步来，系统不会因为我们着急就变得更可靠。

## 参考资料

- [Spring Cloud Alibaba Sentinel 高级指南](https://sca.aliyun.com/en/docs/2023/user-guide/sentinel/advanced-guide/)
- [Sentinel Dashboard 文档](https://github.com/alibaba/Sentinel/wiki/Dashboard)
