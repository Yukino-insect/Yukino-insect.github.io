+++
date = '2026-08-22T00:30:00+08:00'
draft = false
slug = 'sentinel-flow-rule'
title = 'Sentinel 流控规则'
+++

流控规则解决的问题是：**某个资源当前流量太大时，应该允许多少请求通过，超出的请求怎么处理**。

Sentinel 的流控不是简单的“加一个限流器”。它至少包含三个维度：

- 限什么：QPS 还是并发线程数。
- 按什么策略限：直接、关联、链路。
- 超过阈值后怎么处理：快速失败、Warm Up、匀速排队。

对应的规则模型是 `FlowRule`。

## 一、FlowRule 核心字段

简化后的 `FlowRule` 可以理解为：

```java
public class FlowRule extends AbstractRule {
    private int grade;
    private double count;
    private int strategy;
    private String refResource;
    private int controlBehavior;
    private int warmUpPeriodSec;
    private int maxQueueingTimeMs;
    private boolean clusterMode;
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `resource` | 规则作用的资源名，继承自 `AbstractRule` |
| `grade` | 限流指标，QPS 或并发线程数 |
| `count` | 阈值 |
| `strategy` | 流控模式，直接、关联、链路 |
| `refResource` | 关联资源或入口资源 |
| `controlBehavior` | 流控效果 |
| `warmUpPeriodSec` | Warm Up 预热时长 |
| `maxQueueingTimeMs` | 匀速排队最大等待时间 |
| `clusterMode` | 是否启用集群限流 |

`FlowRule` 只是规则数据模型，真正执行判断的是 Sentinel Slot 链中的 `FlowSlot`。

执行过程：

```text
请求进入资源
  ↓
StatisticSlot 统计实时指标
  ↓
FlowSlot 读取 FlowRule
  ↓
判断是否超过阈值
  ↓
通过：继续执行
拒绝：抛出 FlowException
```

## 二、grade：限流指标

`grade` 决定 Sentinel 用什么指标限流。

| 值 | 常量 | 含义 |
| --- | --- | --- |
| `0` | `RuleConstant.FLOW_GRADE_THREAD` | 并发线程数 |
| `1` | `RuleConstant.FLOW_GRADE_QPS` | 每秒请求数 |

### 1. QPS 限流

QPS 是最常用的限流方式。

```java
FlowRule rule = new FlowRule();
rule.setResource("order.query");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(100);
```

语义：

```text
order.query 每秒最多允许 100 个请求通过
```

适合：

- 查询接口。
- 秒杀入口。
- 第三方接口调用。
- 数据库重查询。

### 2. 并发线程数限流

并发线程数限流控制的是当前同时执行该资源的线程数量。

```java
FlowRule rule = new FlowRule();
rule.setResource("report.export");
rule.setGrade(RuleConstant.FLOW_GRADE_THREAD);
rule.setCount(10);
```

语义：

```text
report.export 同时最多 10 个线程执行
```

适合：

- 慢接口。
- 导出任务。
- 需要占用连接或线程较久的资源。
- 下游并发承载能力有限的调用。

QPS 控制入口速度，并发线程数控制占用规模。一个接口如果响应时间很长，即使 QPS 不高，也可能占满线程池；这时并发线程数限流更有效。

## 三、strategy：流控模式

`strategy` 决定按什么关系限流。

| 值 | 常量 | 含义 |
| --- | --- | --- |
| `0` | `RuleConstant.STRATEGY_DIRECT` | 直接流控 |
| `1` | `RuleConstant.STRATEGY_RELATE` | 关联流控 |
| `2` | `RuleConstant.STRATEGY_CHAIN` | 链路流控 |

### 1. 直接流控

直接流控最常用：当前资源超过阈值，就限制当前资源。

```java
FlowRule rule = new FlowRule("order.query");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(100);
rule.setStrategy(RuleConstant.STRATEGY_DIRECT);
```

语义：

```text
order.query 自己超过 100 QPS，就限制 order.query
```

适合绝大多数接口级限流。

### 2. 关联流控

关联流控的语义是：**当关联资源压力过高时，限制当前资源**。

例如写操作优先级高，读操作可以牺牲：

```java
FlowRule rule = new FlowRule("order.query");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(50);
rule.setStrategy(RuleConstant.STRATEGY_RELATE);
rule.setRefResource("order.create");
```

语义：

```text
当 order.create 超过 50 QPS 时，限制 order.query
```

注意被限制的是 `resource`，被观察的是 `refResource`。

典型场景：

- 写库压力高时限制读接口。
- 支付链路压力高时限制非核心查询。
- 核心业务资源繁忙时限制辅助资源。

### 3. 链路流控

链路流控按调用入口限制资源。

例如同一个 Service 方法被两个入口调用：

```text
/api/order/detail
  ↓
order.load

/api/admin/order/detail
  ↓
order.load
```

如果只想限制来自 `/api/admin/order/detail` 的 `order.load`，就需要链路流控。

示意规则：

```java
FlowRule rule = new FlowRule("order.load");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(20);
rule.setStrategy(RuleConstant.STRATEGY_CHAIN);
rule.setRefResource("/api/admin/order/detail");
```

链路流控依赖清晰的入口上下文。入口资源通常是 `EntryType.IN`，内部资源通常是 `EntryType.OUT`。如果入口和内部资源混乱，链路流控就很容易看起来“配置了但没生效”。

## 四、controlBehavior：流控效果

`controlBehavior` 决定超过阈值后怎么处理。

| 值 | 常量 | 含义 |
| --- | --- | --- |
| `0` | `RuleConstant.CONTROL_BEHAVIOR_DEFAULT` | 快速失败 |
| `1` | `RuleConstant.CONTROL_BEHAVIOR_WARM_UP` | Warm Up |
| `2` | `RuleConstant.CONTROL_BEHAVIOR_RATE_LIMITER` | 匀速排队 |
| `3` | `RuleConstant.CONTROL_BEHAVIOR_WARM_UP_RATE_LIMITER` | Warm Up + 匀速排队 |

### 1. 快速失败

快速失败是默认策略。

```java
FlowRule rule = new FlowRule("order.query");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(100);
rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_DEFAULT);
```

超过阈值直接抛出 `FlowException`。

适合：

- 在线接口。
- 用户请求。
- 对延迟敏感的业务。
- 宁可失败也不能排队拖慢的场景。

快速失败的优点是保护边界清楚。缺点是突发流量会直接被拒绝，需要业务返回友好的限流响应。

### 2. Warm Up

Warm Up 用于冷启动保护，让系统从较低阈值逐步升到目标阈值。

```java
FlowRule rule = new FlowRule("product.detail");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(1000);
rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_WARM_UP);
rule.setWarmUpPeriodSec(30);
```

语义：

```text
系统在 30 秒内逐步放量，最终达到 1000 QPS
```

适合：

- 应用刚启动。
- 缓存刚预热。
- JIT、连接池、线程池尚未进入稳定状态。
- 下游服务刚恢复。

Warm Up 的意义是避免流量突然打满一个还没准备好的系统。

### 3. 匀速排队

匀速排队会让请求按固定速率通过，超过最大等待时间才失败。

```java
FlowRule rule = new FlowRule("mq.consume");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(50);
rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_RATE_LIMITER);
rule.setMaxQueueingTimeMs(500);
```

语义：

```text
mq.consume 以每秒 50 个请求的速度匀速通过
等待超过 500ms 的请求会被拒绝
```

适合：

- MQ 消费。
- 后台任务。
- 批处理。
- 对瞬时延迟不敏感，但希望平滑流量的场景。

不适合：

- 用户实时请求。
- 已经有严格超时要求的接口。
- 上游线程资源有限的场景。

排队不是免费午餐。请求只要还在等，就会占用线程、内存和上下文。把在线接口大量改成排队，最后可能不是保护系统，而是换一种姿势把系统拖住。

## 五、硬编码加载规则

学习或单测时可以硬编码规则：

```java
@PostConstruct
public void initFlowRules() {
    FlowRule rule = new FlowRule();
    rule.setResource("order.query");
    rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
    rule.setCount(100);
    rule.setStrategy(RuleConstant.STRATEGY_DIRECT);
    rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_DEFAULT);

    FlowRuleManager.loadRules(Collections.singletonList(rule));
}
```

`FlowRuleManager.loadRules()` 会把规则加载到本地内存，随后请求立即按新规则判断。

但生产环境不建议靠硬编码维护规则，原因很简单：

- 修改规则需要发版。
- 无法按环境灵活调整。
- 多实例规则容易不一致。
- 缺少审计和回滚。

硬编码适合演示，不适合治理体系。

## 六、JSON 规则示例

动态数据源里常用 JSON 表达规则。

直接 QPS 限流：

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

关联流控：

```json
[
  {
    "resource": "order.query",
    "grade": 1,
    "count": 50,
    "strategy": 1,
    "refResource": "order.create",
    "controlBehavior": 0
  }
]
```

匀速排队：

```json
[
  {
    "resource": "mq.consume",
    "grade": 1,
    "count": 50,
    "strategy": 0,
    "controlBehavior": 2,
    "maxQueueingTimeMs": 500
  }
]
```

JSON 字段和 Java 规则模型基本对应。真正容易错的不是 JSON 格式，而是资源名、阈值单位和规则语义。

## 七、规则设计建议

### 1. 先按资源容量定阈值

不要凭感觉写：

```text
这个接口看起来重要，给 1000 QPS 吧。
```

更合理的方式是先知道：

- 单实例最大稳定 QPS。
- P95 / P99 响应时间。
- 下游数据库或 RPC 的承载能力。
- 线程池和连接池大小。
- 高峰流量和突发流量。

限流阈值应该来自容量评估，而不是来自心情。

### 2. 在线请求优先快速失败

在线接口通常更适合快速失败：

- 用户能尽快收到响应。
- 上游线程不会长期阻塞。
- 故障边界清楚。
- 告警和指标更明显。

排队只适合少数可等待场景。

### 3. 写接口要谨慎限流

写接口被限流后，前端或上游可能重试。重试如果没有幂等设计，会制造重复提交、重复扣减、重复发券等问题。

写接口限流要同时考虑：

- 幂等键。
- 去重。
- 业务事务。
- 用户提示。
- 重试策略。

### 4. 关联流控用于保护核心资源

关联流控不是为了炫技。它适合表达优先级：

```text
核心写链路忙时，牺牲非核心读链路
```

如果两个资源没有明确优先级关系，就不要硬关联。

### 5. 链路流控要先理清入口

链路流控依赖调用链。使用前先确认：

- 入口资源名是什么。
- 内部资源名是什么。
- 是否被 Web 适配层自动埋点。
- 是否手动创建了新的上下文。
- 控制台簇点链路是否符合预期。

链路乱了，规则再漂亮也只是摆设。

## 八、常见误区

1. 把 QPS 限流当成所有问题的答案。
2. 慢接口只限 QPS，不限制并发线程数。
3. 在线接口使用长时间排队，导致线程堆积。
4. 控制台资源名和代码资源名不一致。
5. 不压测就直接设置生产阈值。
6. 忽略下游容量，只保护当前服务。
7. 规则写在代码里，生产变更只能重新发版。

## 九、总结

`FlowRule` 由三个关键问题组成：

- `grade`：按 QPS 还是并发线程数限。
- `strategy`：直接限、关联限，还是按链路限。
- `controlBehavior`：快速失败、Warm Up，还是匀速排队。

流控规则的目标不是把请求挡在门外这么简单，而是在容量有限时保住核心资源、控制排队成本、让系统退化得可理解。限流本身不难，难的是知道该限谁、限多少、失败后怎么交代。

## 参考资料

- [Sentinel 流量控制文档](https://github.com/alibaba/Sentinel/wiki/流量控制)
- [Sentinel GitHub 仓库](https://github.com/alibaba/Sentinel)
