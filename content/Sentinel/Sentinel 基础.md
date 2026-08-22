+++
date = '2026-03-22T15:55:41+08:00'
draft = false
title = 'Sentinel 基础'
+++

Sentinel 是 Alibaba 开源的流量治理组件，核心目标不是“让服务永远不失败”，而是让失败发生时有边界、有速度、有替代方案。

在微服务系统里，一个接口可能依赖数据库、缓存、RPC、第三方 HTTP、消息队列。任何一个依赖变慢或异常，都可能占满上游线程、连接池和队列。Sentinel 解决的正是这种问题：**在请求进入资源之前，先判断当前系统和资源是否还能承受它**。

这组文章按下面的顺序阅读会比较顺：

- [Sentinel 控制台与 Spring Boot 接入](/sentinel/sentinel-dashboard-spring-boot/)
- [Sentinel 资源埋点与异常处理](/sentinel/sentinel-resource-and-exception/)
- [Sentinel 流控规则](/sentinel/sentinel-flow-rule/)
- [Sentinel 熔断降级、热点参数与系统保护](/sentinel/sentinel-degrade-param-system/)
- [Sentinel 规则持久化与生产实践](/sentinel/sentinel-rule-persistence/)

## 一、Sentinel 解决什么问题

Sentinel 主要围绕“资源”做保护。

所谓资源，可以是：

- 一个 HTTP 接口。
- 一个 Service 方法。
- 一次 OpenFeign 调用。
- 一次 RestTemplate 调用。
- 一个数据库查询。
- 一个定时任务。
- 一个消息消费逻辑。

只要这段逻辑可能被高并发、慢调用、异常或热点参数拖垮，就可以被当成 Sentinel 资源。

Sentinel 常见能力包括：

| 能力 | 解决的问题 | 典型场景 |
| --- | --- | --- |
| 流量控制 | 请求太多，系统来不及处理 | 秒杀、查询接口、写入保护 |
| 流量整形 | 请求突增，需要平滑通过 | Warm Up、匀速排队 |
| 熔断降级 | 下游变慢或异常，继续调用只会扩大故障 | RPC、数据库、第三方接口 |
| 热点参数限流 | 某个参数值访问过热 | 热门商品、热门用户、热点文章 |
| 系统自适应保护 | 整个 JVM 已经接近极限 | CPU 高、入口 QPS 高、线程数过多 |
| 授权规则 | 按调用来源做简单访问控制 | 服务间白名单、黑名单 |
| 实时监控 | 观察资源通过量、拒绝量、响应时间 | 控制台机器列表和实时监控 |

Sentinel 并不替代业务异常处理，也不替代权限系统，更不替代容量规划。它是在运行时对流量进行治理的组件。

## 二、核心模型

理解 Sentinel，只需要先抓住三个词：

- **资源**：要保护的代码段。
- **规则**：什么时候放行，什么时候拒绝。
- **处理结果**：被拒绝后如何返回，业务异常后如何兜底。

执行链路可以简化成：

```text
请求进入
  ↓
识别资源
  ↓
读取规则
  ↓
统计实时指标
  ↓
判断是否放行
  ↓
放行：执行业务逻辑
拒绝：抛出 BlockException
```

如果业务代码本身抛出异常，Sentinel 也可以统计异常并触发熔断；但这并不意味着所有业务异常都应该被 Sentinel 吃掉。限流、熔断、业务异常处理的边界要清楚，否则最后只会得到一个“看起来没报错、实际上没人知道发生了什么”的系统。

## 三、资源与规则的关系

一个资源可以配置多种规则。

例如 `order.create` 这个资源可以同时拥有：

- QPS 每秒最多 100。
- 慢调用比例超过 50% 时熔断 10 秒。
- `userId` 参数为某几个热点用户时单独限流。
- 只允许来自某些服务的调用。

规则不是写在资源本身上的。资源只是一个名字和一段埋点逻辑，规则由对应的 `RuleManager` 加载到内存中：

| 规则类型 | 管理器 | 命中后异常 |
| --- | --- | --- |
| `FlowRule` | `FlowRuleManager` | `FlowException` |
| `DegradeRule` | `DegradeRuleManager` | `DegradeException` |
| `ParamFlowRule` | `ParamFlowRuleManager` | `ParamFlowException` |
| `SystemRule` | `SystemRuleManager` | `SystemBlockException` |
| `AuthorityRule` | `AuthorityRuleManager` | `AuthorityException` |

这些异常都继承自 `BlockException`。所以工程里通常会先统一处理 `BlockException`，再按子类细分返回语义。

## 四、Sentinel 的执行位置

在 Spring Cloud Alibaba 项目中，HTTP 请求通常会先经过 Sentinel 的 Web 适配层。

大致流程如下：

```text
HTTP 请求
  ↓
Servlet Filter / WebFlux Filter
  ↓
Sentinel Web 适配层
  ↓
DispatcherServlet / WebFlux Handler
  ↓
Controller
  ↓
Service
  ↓
RPC / DB / Cache
```

这意味着很多场景下不需要在每个 Controller 方法上手写 `@SentinelResource`。Web 适配层已经可以把 URL 识别为资源。

但 `@SentinelResource` 仍然有价值，尤其适合保护更细粒度的内部逻辑：

- 某个 Service 方法。
- 某个第三方接口调用。
- 某个数据库重查询。
- 某个消息消费处理。
- 某个需要单独 fallback 的业务步骤。

换句话说，Web 适配层保护“入口”，`@SentinelResource` 保护“你真正关心的内部资源”。把两者混为一谈，排查问题时会相当狼狈。

## 五、Sentinel 与降级的边界

Sentinel 做的是判断：

```text
这个请求现在还能不能进来？
这个下游现在还该不该继续调用？
这个参数值是不是过热？
这个 JVM 是不是已经快顶不住了？
```

业务代码要回答的是：

```text
被限流时返回什么？
熔断时返回什么？
下游异常时返回什么？
哪些接口可以降级？
哪些接口必须失败关闭？
```

例如商品推荐服务可以降级为空列表，评论服务可以返回缓存，扣款接口却不能随便返回“成功”。稳定性设计不是“出事时糊弄一下用户”，而是在故障发生前就定义清楚业务允许的替代结果。

## 六、控制台不是规则持久化中心

Sentinel Dashboard 用来做机器发现、实时监控和规则管理。它能把规则推送给客户端，让客户端在本地内存中生效。

但要注意：**开源 Dashboard 默认更偏演示和运维管理，不应被当作生产环境唯一的规则存储中心**。

生产环境通常需要动态数据源，例如 Nacos、Apollo、ZooKeeper、Redis、文件等。客户端从数据源读取规则，规则变更后自动刷新到本地内存。这样应用重启、扩缩容、控制台重启时，规则不会凭空消失。

推荐模型是：

```text
配置中心 / 规则中心
  ↓
Sentinel 客户端动态数据源
  ↓
RuleManager
  ↓
Slot 判断规则
```

Dashboard 可以参与规则编辑，但规则最终必须进入一个可靠的数据源。否则生产事故来临时，靠一台控制台撑住治理体系，未免过于天真。

## 七、学习路线

学习 Sentinel 建议按这个顺序：

1. 先接入控制台，确认机器能被发现。
2. 理解资源、规则、`BlockException`。
3. 学会用 `@SentinelResource` 保护 Service 方法。
4. 配置基础 QPS 限流，观察 `FlowException`。
5. 配置慢调用比例熔断，理解熔断和降级的区别。
6. 配置热点参数限流，处理热门数据访问。
7. 配置系统保护规则，理解入口流量统计。
8. 接入 Nacos 等动态数据源，实现规则持久化。
9. 建立告警、日志、指标和变更流程。

## 八、总结

Sentinel 的主线并不复杂：

- 用资源描述保护对象。
- 用规则描述保护条件。
- 用实时统计判断是否放行。
- 用 `BlockException` 表达流控、熔断、系统保护等阻断结果。
- 用业务 fallback 或统一异常处理返回合理结果。
- 用动态数据源让规则在生产环境可恢复、可审计、可持续变更。

学 Sentinel 最容易犯的错，是一开始就陷进控制台页面和规则字段。先把“资源、规则、异常、降级、持久化”这条线理顺，再看具体参数，事情会清楚许多。

## 参考资料

- [Sentinel 官方网站](https://sentinelguard.io/)
- [Sentinel GitHub 仓库](https://github.com/alibaba/Sentinel)
- [Spring Cloud Alibaba Sentinel 高级指南](https://sca.aliyun.com/en/docs/2023/user-guide/sentinel/advanced-guide/)
- [Spring Cloud Alibaba Sentinel Wiki](https://github.com/alibaba/spring-cloud-alibaba/wiki/Sentinel-en)
