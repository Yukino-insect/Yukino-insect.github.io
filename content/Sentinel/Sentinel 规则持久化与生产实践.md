+++
date = '2026-08-22T00:50:00+08:00'
draft = false
slug = 'sentinel-rule-persistence'
title = 'Sentinel 规则持久化与生产实践'
+++

Sentinel 规则最终是在客户端本地内存中生效的。无论规则来自硬编码、Dashboard，还是 Nacos、Apollo、ZooKeeper 等动态数据源，最后都要加载进对应的 `RuleManager`。

这一点非常重要：

```text
规则数据
  ↓
动态数据源 / 控制台推送 / 硬编码
  ↓
RuleManager.loadRules(...)
  ↓
客户端本地内存
  ↓
Slot 链运行期判断
```

控制台只是规则管理入口之一，不等于规则持久化中心。生产环境如果只依赖 Dashboard 内存规则，应用重启、控制台重启、实例扩缩容时就可能出现规则丢失或不一致。

## 一、规则为什么要持久化

不持久化会遇到这些问题：

- 应用重启后规则恢复不稳定。
- 新扩容实例拿不到已有规则。
- Dashboard 重启后看不到历史配置。
- 多环境规则容易混乱。
- 缺少变更审计和回滚。
- 事故期间临时规则无法可靠保留。

生产环境的规则应该像配置一样管理：

- 有来源。
- 有版本。
- 有审核。
- 可回滚。
- 可观察。
- 可自动加载。

如果规则只能靠人在控制台页面点出来，那它更像临时操作，而不是治理能力。

## 二、规则加载方式

Sentinel 常见规则加载方式：

| 方式 | 适合场景 | 问题 |
| --- | --- | --- |
| 硬编码 | Demo、单测、本地验证 | 修改要发版 |
| Dashboard 推送 | 学习、临时调试、小规模运维 | 默认不适合作为唯一持久化来源 |
| 本地文件 | 简单部署、离线环境 | 多实例同步麻烦 |
| Nacos / Apollo | Spring Cloud 微服务 | 适合生产动态配置 |
| ZooKeeper / Redis | 已有基础设施复用 | 运维复杂度取决于团队 |
| 自定义数据源 | 内部治理平台 | 需要开发和维护 |

Spring Cloud Alibaba 项目里，最常见的是 Nacos 动态数据源。

## 三、RuleManager 与规则生效

不同规则由不同管理器维护：

| 规则 | 管理器 |
| --- | --- |
| `FlowRule` | `FlowRuleManager` |
| `DegradeRule` | `DegradeRuleManager` |
| `ParamFlowRule` | `ParamFlowRuleManager` |
| `SystemRule` | `SystemRuleManager` |
| `AuthorityRule` | `AuthorityRuleManager` |

硬编码示例：

```java
@PostConstruct
public void initRules() {
    FlowRule flowRule = new FlowRule("order.query");
    flowRule.setGrade(RuleConstant.FLOW_GRADE_QPS);
    flowRule.setCount(100);

    DegradeRule degradeRule = new DegradeRule("payment.prepay");
    degradeRule.setGrade(RuleConstant.DEGRADE_GRADE_RT);
    degradeRule.setCount(500);
    degradeRule.setSlowRatioThreshold(0.5);
    degradeRule.setMinRequestAmount(20);
    degradeRule.setStatIntervalMs(1000);
    degradeRule.setTimeWindow(10);

    FlowRuleManager.loadRules(Collections.singletonList(flowRule));
    DegradeRuleManager.loadRules(Collections.singletonList(degradeRule));
}
```

规则加载后立即对后续请求生效，不需要重启应用。

但要注意：`loadRules()` 通常是覆盖式加载。也就是说，后一次加载的规则集合会替换该类型已有规则集合。多数据源、多处硬编码混用时，最容易出现“我明明配了规则，怎么没了”的问题。

## 四、接入 Nacos 动态数据源

### 1. 添加依赖

Spring Cloud Alibaba Sentinel Nacos 数据源通常需要额外引入：

```xml
<dependency>
    <groupId>com.alibaba.csp</groupId>
    <artifactId>sentinel-datasource-nacos</artifactId>
</dependency>
```

如果使用 Spring Cloud Alibaba 的自动配置，也要确保已经引入：

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-sentinel</artifactId>
</dependency>
```

版本仍建议交给 BOM 管理。

### 2. 配置数据源

示例：

```yaml
spring:
  application:
    name: order-service
  cloud:
    sentinel:
      transport:
        dashboard: localhost:8858
        port: 8719
      datasource:
        flow-rules:
          nacos:
            server-addr: localhost:8848
            namespace: public
            group-id: SENTINEL_GROUP
            data-id: order-service-flow-rules
            data-type: json
            rule-type: flow
        degrade-rules:
          nacos:
            server-addr: localhost:8848
            namespace: public
            group-id: SENTINEL_GROUP
            data-id: order-service-degrade-rules
            data-type: json
            rule-type: degrade
        param-flow-rules:
          nacos:
            server-addr: localhost:8848
            namespace: public
            group-id: SENTINEL_GROUP
            data-id: order-service-param-flow-rules
            data-type: json
            rule-type: param-flow
```

关键字段：

| 字段 | 含义 |
| --- | --- |
| `server-addr` | Nacos 地址 |
| `namespace` | 命名空间 |
| `group-id` | 配置分组 |
| `data-id` | 配置 ID |
| `data-type` | 数据格式，常用 `json` |
| `rule-type` | 规则类型 |

常见 `rule-type`：

```text
flow
degrade
authority
system
param-flow
gw-flow
gw-api-group
```

不同 Spring Cloud Alibaba 版本的配置项细节可能略有差异，实际项目应以当前版本官方文档为准。版本不一致时，不要靠猜；猜配置项这种事，通常只会让日志替你冷笑。

## 五、Nacos 规则内容

### 1. 流控规则

`Data ID`：

```text
order-service-flow-rules
```

配置内容：

```json
[
  {
    "resource": "order.query",
    "grade": 1,
    "count": 100,
    "strategy": 0,
    "controlBehavior": 0
  }
]
```

### 2. 熔断规则

`Data ID`：

```text
order-service-degrade-rules
```

配置内容：

```json
[
  {
    "resource": "payment.prepay",
    "grade": 0,
    "count": 500,
    "slowRatioThreshold": 0.5,
    "minRequestAmount": 20,
    "statIntervalMs": 1000,
    "timeWindow": 10
  }
]
```

语义：

```text
1 秒内至少 20 个请求
响应时间超过 500ms 的请求比例达到 50%
则熔断 10 秒
```

### 3. 热点参数规则

`Data ID`：

```text
order-service-param-flow-rules
```

配置内容：

```json
[
  {
    "resource": "product.detail",
    "grade": 1,
    "paramIdx": 0,
    "count": 20,
    "durationInSec": 1,
    "controlBehavior": 0,
    "paramFlowItemList": [
      {
        "object": "1001",
        "classType": "java.lang.Long",
        "count": 100
      }
    ]
  }
]
```

语义：

```text
product.detail 的第 0 个参数默认每秒最多 20 次
参数值 1001 每秒最多 100 次
```

### 4. 系统规则

`Data ID`：

```text
order-service-system-rules
```

配置内容：

```json
[
  {
    "highestCpuUsage": 0.8,
    "qps": 2000,
    "avgRt": 1000,
    "maxThread": 300
  }
]
```

系统规则作用于整个应用实例，不针对某个资源。配置时要更谨慎。

## 六、Dashboard 与 Nacos 的关系

常见误解是：

```text
在 Dashboard 点保存
  ↓
规则自动永久保存到 Nacos
```

开源 Sentinel Dashboard 默认并不天然等于一个完整的生产规则中心。常见生产模型有两种：

### 1. 客户端直接从 Nacos 拉规则

```text
Nacos 配置
  ↓
Sentinel 客户端动态数据源
  ↓
本地 RuleManager
  ↓
规则生效
```

这种方式简单可靠。规则编辑可以通过 Nacos 控制台、配置发布系统或内部治理平台完成。

### 2. 改造 Dashboard，让它写入 Nacos

```text
Dashboard 页面编辑规则
  ↓
Dashboard 写入 Nacos
  ↓
客户端监听 Nacos 变更
  ↓
规则生效
```

这种方式体验更好，但需要改造 Dashboard 或使用具备规则中心能力的平台。否则 Dashboard 保存的规则可能只是推送到了客户端内存。

判断一个系统是否真正持久化规则，只问一个问题：

```text
所有应用实例和 Dashboard 全部重启以后，规则还能自动恢复吗？
```

如果答案是否定的，那就还不算生产级持久化。

## 七、生产规则命名建议

推荐按应用和规则类型拆分：

```text
${spring.application.name}-flow-rules
${spring.application.name}-degrade-rules
${spring.application.name}-param-flow-rules
${spring.application.name}-system-rules
${spring.application.name}-authority-rules
```

例如：

```text
order-service-flow-rules
order-service-degrade-rules
order-service-param-flow-rules
```

也可以带环境：

```text
order-service-prod-flow-rules
order-service-test-flow-rules
```

更推荐用 Nacos namespace 区分环境，用 group 区分业务域或规则域，避免 `data-id` 过长。

## 八、发布流程建议

生产规则变更至少应包含：

1. 变更原因。
2. 影响资源。
3. 当前指标。
4. 新阈值。
5. 预期效果。
6. 回滚方案。
7. 观察窗口。

一个更稳妥的发布流程：

```text
测试环境验证
  ↓
预发环境压测或回放
  ↓
生产小流量实例验证
  ↓
全量发布规则
  ↓
观察通过 QPS、拒绝 QPS、RT、异常率
  ↓
确认无异常后结束变更
```

规则变更虽然不像代码发版那样重，但它直接改变运行时行为。越是能快速生效的东西，越需要清楚的边界和回滚手段。

## 九、监控与告警

Sentinel 规则上线后，应至少关注：

- 资源通过 QPS。
- 资源拒绝 QPS。
- 平均 RT、P95、P99。
- 异常比例和异常数。
- 熔断打开次数。
- 热点参数拒绝次数。
- 系统规则触发次数。
- 业务 fallback 次数。

日志建议记录：

```text
traceId
resource
ruleType
exceptionType
origin
fallbackResult
costMs
```

示例：

```java
@ExceptionHandler(BlockException.class)
public ResponseEntity<ApiResult<Void>> handleBlock(BlockException ex) {
    log.warn("sentinel block, resource={}, type={}",
            ex.getRule() == null ? "unknown" : ex.getRule().getResource(),
            ex.getClass().getSimpleName());
    return ResponseEntity.status(429)
            .body(ApiResult.fail("系统繁忙，请稍后再试"));
}
```

降级不能悄悄发生。悄悄发生的降级，本质上只是把故障从用户眼前移到了排查人员的深夜里。

## 十、规则设计清单

上线前检查：

- 资源名是否稳定且可读。
- 规则资源名是否与埋点一致。
- 阈值是否来自压测或历史指标。
- 是否有明确 fallback。
- 写操作是否具备幂等。
- 熔断统计是否排除了正常业务异常。
- 热点参数 `paramIdx` 是否和方法签名一致。
- 系统规则是否过于激进。
- 规则是否持久化。
- 规则变更是否可回滚。
- 告警是否覆盖拒绝量和熔断事件。

## 十一、常见误区

1. 把 Dashboard 当成生产规则数据库。
2. 多个数据源同时加载同一类规则，互相覆盖。
3. 应用扩容后新实例没有规则。
4. 规则没有版本和审计，无法知道是谁改的。
5. 限流触发后没有业务提示和日志。
6. 熔断触发后没有监控，降级结果掩盖故障。
7. 直接复制测试环境阈值到生产环境。
8. 只看平均 RT，不看 P95 / P99。

## 十二、总结

Sentinel 规则的生产化重点不是“能不能配”，而是“能不能可靠地恢复、变更、观察和回滚”。

推荐做法是：

- 客户端接入动态数据源。
- 规则存放在 Nacos、Apollo 等可靠配置中心。
- Dashboard 只作为观察和管理入口，必要时改造成规则写入端。
- 规则变更走流程，有审计和回滚。
- 限流、熔断、热点、系统保护都接入监控告警。

当规则变成可管理的配置，而不是某次页面点击留下的临时状态，Sentinel 才真正进入生产可用的阶段。

## 参考资料

- [Spring Cloud Alibaba Sentinel 高级指南](https://sca.aliyun.com/en/docs/2023/user-guide/sentinel/advanced-guide/)
- [Sentinel 动态规则扩展文档](https://github.com/alibaba/Sentinel/wiki/动态规则扩展)
- [Sentinel Dashboard 文档](https://github.com/alibaba/Sentinel/wiki/Dashboard)
