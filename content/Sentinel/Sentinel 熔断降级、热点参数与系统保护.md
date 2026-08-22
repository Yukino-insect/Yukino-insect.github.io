+++
date = '2026-08-22T00:40:00+08:00'
draft = false
slug = 'sentinel-degrade-param-system'
title = 'Sentinel 熔断降级、热点参数与系统保护'
+++

流控解决“请求太多”的问题，熔断解决“依赖不健康”的问题，热点参数解决“某些值太热”的问题，系统保护解决“整个 JVM 快撑不住”的问题。

它们都属于 Sentinel 的保护能力，但触发原因和设计思路不同。混在一起理解，结果通常是规则配了一堆，真正出事时不知道谁在起作用。

## 一、BlockException 体系

Sentinel 命中保护规则后会抛出 `BlockException` 子类。

常见类型：

```text
BlockException
  ├─ FlowException
  ├─ DegradeException
  ├─ ParamFlowException
  ├─ SystemBlockException
  └─ AuthorityException
```

对应关系：

| 异常 | 规则 | 含义 |
| --- | --- | --- |
| `FlowException` | 流控规则 | QPS、并发、排队、Warm Up 等触发 |
| `DegradeException` | 熔断规则 | 慢调用、异常比例、异常数触发 |
| `ParamFlowException` | 热点参数规则 | 某个参数值访问过热 |
| `SystemBlockException` | 系统规则 | CPU、Load、入口 QPS、线程数等触发 |
| `AuthorityException` | 授权规则 | 来源不符合黑白名单 |

统一异常处理示例：

```java
@ExceptionHandler(BlockException.class)
public ResponseEntity<String> handleBlock(BlockException ex) {
    if (ex instanceof FlowException) {
        return ResponseEntity.status(429).body("请求过多，请稍后再试");
    }
    if (ex instanceof DegradeException) {
        return ResponseEntity.status(503).body("依赖暂时不可用，请稍后再试");
    }
    if (ex instanceof ParamFlowException) {
        return ResponseEntity.status(429).body("热点访问过于频繁，请稍后再试");
    }
    if (ex instanceof SystemBlockException) {
        return ResponseEntity.status(503).body("系统压力过高，请稍后再试");
    }
    if (ex instanceof AuthorityException) {
        return ResponseEntity.status(403).body("当前来源无权访问");
    }
    return ResponseEntity.status(429).body("请求被 Sentinel 拦截");
}
```

`BlockException` 是可预期的治理结果，不是程序 bug。日志级别、告警策略和返回码都应该按这个前提设计。

## 二、熔断降级

Sentinel 的熔断规则模型是 `DegradeRule`。

简化字段：

```java
public class DegradeRule extends AbstractRule {
    private int grade;
    private double count;
    private int timeWindow;
    private int minRequestAmount;
    private double slowRatioThreshold;
    private int statIntervalMs;
}
```

核心字段：

| 字段 | 含义 |
| --- | --- |
| `grade` | 熔断策略 |
| `count` | 阈值，含义随策略变化 |
| `timeWindow` | 熔断持续时间，单位秒 |
| `minRequestAmount` | 最小请求数 |
| `slowRatioThreshold` | 慢调用比例阈值 |
| `statIntervalMs` | 统计窗口，单位毫秒 |

熔断的基本过程：

```text
统计窗口内资源变慢或异常
  ↓
达到触发条件
  ↓
熔断打开
  ↓
timeWindow 内请求直接拒绝
  ↓
进入半开探测
  ↓
探测成功：关闭熔断
探测失败：重新打开熔断
```

### 1. 慢调用比例

慢调用比例是 Sentinel 1.8.x 以后更推荐的熔断策略。

示例：

```java
DegradeRule rule = new DegradeRule("payment.prepay");
rule.setGrade(RuleConstant.DEGRADE_GRADE_RT);
rule.setCount(500);
rule.setSlowRatioThreshold(0.5);
rule.setMinRequestAmount(20);
rule.setStatIntervalMs(1000);
rule.setTimeWindow(10);
```

语义：

```text
1 秒统计窗口内，请求数至少 20
其中响应时间超过 500ms 的请求比例达到 50%
则 payment.prepay 熔断 10 秒
```

适合：

- RPC 调用变慢。
- 数据库查询变慢。
- 第三方接口响应抖动。
- 下游还没完全失败，但已经开始拖慢上游。

慢调用比例比异常比例更早发现问题。很多故障不是一下子报错，而是先变慢；线程池往往就是在“还没报错”的阶段被耗尽的。

### 2. 异常比例

异常比例按异常请求占比触发熔断。

```java
DegradeRule rule = new DegradeRule("coupon.receive");
rule.setGrade(RuleConstant.DEGRADE_GRADE_EXCEPTION_RATIO);
rule.setCount(0.3);
rule.setMinRequestAmount(20);
rule.setStatIntervalMs(1000);
rule.setTimeWindow(10);
```

语义：

```text
1 秒内请求数至少 20
异常比例达到 30%
则 coupon.receive 熔断 10 秒
```

适合异常语义比较明确的接口。前提是你要区分业务异常和系统异常，例如“优惠券不存在”不应该和“数据库连接失败”混在一起统计。

### 3. 异常数

异常数按统计窗口内的异常绝对数量触发。

```java
DegradeRule rule = new DegradeRule("sms.send");
rule.setGrade(RuleConstant.DEGRADE_GRADE_EXCEPTION_COUNT);
rule.setCount(10);
rule.setStatIntervalMs(1000);
rule.setTimeWindow(30);
```

语义：

```text
1 秒内异常数达到 10
则 sms.send 熔断 30 秒
```

异常数策略简单直接，但在低流量和高流量场景下都需要谨慎。流量很小时偶发异常可能误判，流量很大时绝对异常数很容易被击穿。

## 三、熔断和降级不是一回事

熔断回答：

```text
还要不要继续调用这个资源？
```

降级回答：

```text
不调用以后返回什么？
```

示例：

```java
@SentinelResource(value = "recommend.list", fallback = "recommendFallback")
public List<ProductDTO> recommend(Long userId) {
    return recommendClient.list(userId);
}

public List<ProductDTO> recommendFallback(Long userId, Throwable ex) {
    return Collections.emptyList();
}
```

推荐服务不可用时返回空列表，通常是可以接受的。

但扣款、扣库存、发券等接口不能简单降级成功：

```text
扣款失败 -> 返回成功
库存扣减失败 -> 返回成功
风控失败 -> 默认放行
```

这些做法不是稳定性设计，是把事故藏到更晚的时候爆发。系统不会因为响应报文好看就变得正确。

## 四、热点参数限流

热点参数规则模型是 `ParamFlowRule`。

它解决的问题是：整体 QPS 不一定高，但某个参数值特别热。

典型场景：

- 某个热门商品被抢购。
- 某个热门文章被大量访问。
- 某个明星用户主页被集中访问。
- 某个租户突然流量异常。

普通资源限流只能限制整体：

```text
product.detail 总 QPS <= 1000
```

热点参数限流可以限制具体参数：

```text
product.detail 中 productId = 1001 的 QPS <= 100
其他 productId 的 QPS <= 20
```

### 1. 代码埋点

热点参数限流通常需要资源方法参数明确：

```java
@SentinelResource(value = "product.detail", blockHandler = "detailBlocked")
public ProductDTO detail(Long productId) {
    return productClient.detail(productId);
}

public ProductDTO detailBlocked(Long productId, BlockException ex) {
    return ProductDTO.busy(productId);
}
```

`ParamFlowRule` 通过 `paramIdx` 指定参数位置，索引从 `0` 开始。

### 2. 规则示例

```java
ParamFlowRule rule = new ParamFlowRule("product.detail");
rule.setParamIdx(0);
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(20);
rule.setDurationInSec(1);
```

语义：

```text
对 product.detail 的第 0 个参数限流
每个参数值默认每秒最多 20 次
```

为特定热点值配置单独阈值：

```java
ParamFlowItem item = new ParamFlowItem()
        .setObject(String.valueOf(1001L))
        .setClassType(Long.class.getName())
        .setCount(100);

ParamFlowRule rule = new ParamFlowRule("product.detail");
rule.setParamIdx(0);
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(20);
rule.setParamFlowItemList(Collections.singletonList(item));
```

语义：

```text
productId = 1001 时 QPS <= 100
其他 productId 时 QPS <= 20
```

热点参数规则常见字段：

| 字段 | 含义 |
| --- | --- |
| `paramIdx` | 参数索引，从 0 开始 |
| `count` | 默认阈值 |
| `durationInSec` | 统计窗口，单位秒 |
| `controlBehavior` | 快速失败或匀速排队 |
| `burstCount` | 突发流量容忍 |
| `paramFlowItemList` | 特定参数值的例外配置 |

### 3. 使用建议

热点参数限流适合保护数据倾斜，不适合替代业务风控。

推荐用于：

- 商品详情。
- 用户主页。
- 评论列表。
- 搜索建议。
- 多租户接口。

谨慎用于：

- 支付。
- 下单。
- 权限校验。
- 强一致写入。

热点参数规则依赖参数类型和参数位置。方法签名变化后，`paramIdx` 可能失效，所以这类规则要和代码变更一起评审。

## 五、系统保护规则

系统保护规则模型是 `SystemRule`。

它不是保护某个资源，而是保护整个 JVM。

简化字段：

```java
public class SystemRule extends AbstractRule {
    private double highestSystemLoad;
    private double highestCpuUsage;
    private double qps;
    private long avgRt;
    private long maxThread;
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `highestSystemLoad` | 系统 Load 阈值，主要用于 Linux |
| `highestCpuUsage` | CPU 使用率阈值，取值 `0` 到 `1` |
| `qps` | 系统入口总 QPS |
| `avgRt` | 系统入口平均响应时间 |
| `maxThread` | 系统入口并发线程数 |

系统规则只对入口流量有意义，也就是 `EntryType.IN`。

执行过程：

```text
入口请求进入
  ↓
SystemSlot 检查系统指标
  ↓
任一指标超过阈值
  ↓
抛出 SystemBlockException
  ↓
请求不会继续进入业务逻辑
```

示例：

```java
SystemRule rule = new SystemRule();
rule.setHighestCpuUsage(0.8);
rule.setQps(2000);
rule.setMaxThread(300);

SystemRuleManager.loadRules(Collections.singletonList(rule));
```

语义：

```text
CPU 使用率超过 80%
或入口总 QPS 超过 2000
或入口并发线程数超过 300
则触发系统保护
```

系统规则适合做最后一道保护，不适合替代资源级规则。它的粒度粗，一旦触发，影响范围通常是整个应用实例。

## 六、授权规则

授权规则模型是 `AuthorityRule`。

它按调用来源做简单黑白名单控制：

```java
AuthorityRule rule = new AuthorityRule();
rule.setResource("order.create");
rule.setLimitApp("trade-service");
rule.setStrategy(RuleConstant.AUTHORITY_WHITE);
```

语义：

```text
order.create 只允许 trade-service 来源访问
```

黑名单示例：

```java
AuthorityRule rule = new AuthorityRule();
rule.setResource("order.create");
rule.setLimitApp("test-service");
rule.setStrategy(RuleConstant.AUTHORITY_BLACK);
```

授权规则适合服务间来源隔离，但不要把它当作完整的认证授权系统。真正的用户权限、租户权限、数据权限，仍然应该由业务安全体系负责。

## 七、如何选择规则

| 问题 | 优先考虑 |
| --- | --- |
| 接口请求太多 | 流控规则 |
| 接口响应变慢 | 慢调用比例熔断 |
| 下游异常增多 | 异常比例或异常数熔断 |
| 某个商品、用户、租户特别热 | 热点参数限流 |
| 整个 JVM 压力过高 | 系统保护 |
| 某些调用来源不应访问 | 授权规则 |

实际生产中经常组合使用：

```text
入口接口：QPS 流控
核心下游：慢调用比例熔断
热门商品：热点参数限流
整个应用：系统保护兜底
```

不要一上来把所有规则都配满。规则越多，系统行为越难解释。先保护最关键的资源，再逐步扩展。

## 八、常见误区

1. 把熔断当成降级，配置规则后不写 fallback。
2. 把业务异常全部计入熔断统计。
3. 熔断时间过长，恢复后仍长时间拒绝请求。
4. `minRequestAmount` 太低，低流量下频繁误熔断。
5. 热点参数的 `paramIdx` 写错。
6. 系统规则阈值过低，导致全站入口频繁被挡。
7. 授权规则被当作业务鉴权使用。

## 九、总结

Sentinel 的多种规则各有边界：

- 流控规则控制访问速度和并发规模。
- 熔断规则隔离慢调用和异常依赖。
- 热点参数规则处理局部数据过热。
- 系统规则保护整个 JVM 的入口流量。
- 授权规则做简单来源控制。

规则本身只负责“是否允许通过”。被拒绝以后如何返回，仍然是业务设计的一部分。没有降级语义的熔断，只是换了一个更快的失败方式而已。

## 参考资料

- [Sentinel 熔断降级文档](https://github.com/alibaba/Sentinel/wiki/熔断降级)
- [Sentinel 热点参数限流文档](https://github.com/alibaba/Sentinel/wiki/热点参数限流)
- [Sentinel 系统自适应保护文档](https://github.com/alibaba/Sentinel/wiki/系统自适应保护)
