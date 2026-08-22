+++
date = '2026-08-22T00:20:00+08:00'
draft = false
slug = 'sentinel-resource-and-exception'
title = 'Sentinel 资源埋点与异常处理'
+++

Sentinel 的第一步不是配置规则，而是定义资源。没有资源，规则就没有作用对象；没有规则，资源只是一个被统计的名字。

资源埋点有两种常见方式：

- 用 `SphU.entry()` 手动埋点。
- 用 `@SentinelResource` 注解埋点。

在 Spring Cloud Alibaba Web 项目里，HTTP 入口通常已经由 Web 适配层自动埋点；`@SentinelResource` 更适合保护 Service、RPC、DB、缓存、消息消费等内部关键逻辑。

## 一、什么是资源

资源是 Sentinel 统计和保护的基本单位。

资源名应该稳定、清晰、有业务含义。推荐格式：

```text
模块.动作
```

例如：

```text
order.create
order.query
inventory.deduct
payment.prepay
coupon.receive
```

不建议把资源名写成：

```text
test
aaa
method1
com.demo.service.impl.OrderServiceImpl.createOrder
```

资源名不是越技术化越好。它最终会出现在控制台、日志、监控和告警里，最好让排查的人一眼知道它保护的是哪段业务。

## 二、手动埋点

最直接的方式是 `SphU.entry()`：

```java
public OrderDTO getOrder(Long orderId) {
    try (Entry entry = SphU.entry("order.query")) {
        return orderClient.getOrder(orderId);
    } catch (BlockException ex) {
        return OrderDTO.empty(orderId);
    }
}
```

含义是：

1. 进入 `order.query` 资源。
2. Sentinel 根据规则判断是否允许通过。
3. 允许通过时执行业务逻辑。
4. 命中规则时抛出 `BlockException`。
5. `try-with-resources` 结束时自动退出资源并记录统计。

手动埋点的优点是边界精确、无框架依赖。缺点也明显：代码侵入较高，业务逻辑里会混入 Sentinel API。

更完整的写法会区分被 Sentinel 拦截和业务异常：

```java
public OrderDTO getOrder(Long orderId) {
    Entry entry = null;
    try {
        entry = SphU.entry("order.query");
        return orderClient.getOrder(orderId);
    } catch (BlockException ex) {
        return OrderDTO.empty(orderId);
    } catch (Throwable ex) {
        Tracer.trace(ex);
        throw ex;
    } finally {
        if (entry != null) {
            entry.exit();
        }
    }
}
```

`Tracer.trace(ex)` 用来向 Sentinel 记录业务异常，便于熔断规则基于异常比例、异常数进行统计。使用 `@SentinelResource` 时，框架会帮你处理大部分统计逻辑；手动埋点时要更小心。

## 三、注解埋点

`@SentinelResource` 是 Spring 项目里最常用的埋点方式。

示例：

```java
@Service
public class OrderService {

    @SentinelResource(
            value = "order.query",
            blockHandler = "queryBlockHandler",
            fallback = "queryFallback"
    )
    public OrderDTO query(Long orderId) {
        return remoteOrderClient.query(orderId);
    }

    public OrderDTO queryBlockHandler(Long orderId, BlockException ex) {
        return OrderDTO.empty(orderId);
    }

    public OrderDTO queryFallback(Long orderId, Throwable ex) {
        return OrderDTO.fromCache(orderId);
    }
}
```

这里分成两类异常：

- `blockHandler`：处理 Sentinel 规则命中后的 `BlockException`。
- `fallback`：处理业务代码抛出的非 `BlockException` 异常。

这两个概念必须分清。限流不是业务异常，业务异常也不等于限流。

## 四、注解常用属性

`@SentinelResource` 常见属性如下：

| 属性 | 作用 |
| --- | --- |
| `value` | 资源名 |
| `entryType` | 入口类型，默认 `EntryType.OUT` |
| `blockHandler` | Sentinel 阻断后的处理方法 |
| `blockHandlerClass` | `blockHandler` 所在类 |
| `fallback` | 业务异常 fallback 方法 |
| `fallbackClass` | `fallback` 所在类 |
| `defaultFallback` | 默认 fallback 方法 |
| `exceptionsToTrace` | 哪些异常计入异常统计并触发 fallback |
| `exceptionsToIgnore` | 哪些异常忽略，不触发 fallback |

### 1. `value`

`value` 是资源名，也是规则匹配的关键。

```java
@SentinelResource("payment.prepay")
public PayResult prepay(PayCommand command) {
    return paymentClient.prepay(command);
}
```

控制台或动态数据源里的规则资源名必须和 `payment.prepay` 一致，否则规则不会命中。

### 2. `entryType`

`entryType` 用来标记资源在调用链里的语义：

| 类型 | 含义 | 常见位置 |
| --- | --- | --- |
| `EntryType.IN` | 系统入口流量 | HTTP、RPC Provider、消息入口 |
| `EntryType.OUT` | 内部调用资源 | Service、RPC Client、DB、缓存 |

`@SentinelResource` 默认是 `EntryType.OUT`。这并不是疏忽，而是因为注解更多用于保护任意代码段，而大多数代码段都不是系统入口。

一条健康的调用链可以理解为：

```text
HTTP 入口资源（IN）
  ↓
Controller
  ↓
order.create（OUT）
  ↓
inventory.deduct（OUT）
  ↓
payment.prepay（OUT）
```

系统规则主要统计入口流量。如果把大量内部方法都标成 `IN`，入口统计口径会被污染，链路规则也会变得难以理解。

在 Spring Cloud Alibaba Web 项目里，HTTP 请求一般已由 Sentinel Web Filter 作为入口处理。因此 Controller 方法上不必为了“入口”而强行写 `entryType = EntryType.IN`。除非你清楚自己在调整调用链语义，否则保持默认更稳妥。

### 3. `blockHandler`

`blockHandler` 处理的是 Sentinel 阻断。

方法签名要求：

- 方法名与 `blockHandler` 属性一致。
- 返回值与原方法一致。
- 参数与原方法一致，并在最后追加 `BlockException`。

示例：

```java
@SentinelResource(value = "coupon.receive", blockHandler = "receiveBlocked")
public CouponResult receive(Long userId, Long couponId) {
    return couponClient.receive(userId, couponId);
}

public CouponResult receiveBlocked(Long userId, Long couponId, BlockException ex) {
    return CouponResult.busy();
}
```

如果处理方法放在单独类中，需要配合 `blockHandlerClass`，且方法通常要声明为 `static`：

```java
public final class SentinelBlockHandlers {

    private SentinelBlockHandlers() {
    }

    public static CouponResult receiveBlocked(
            Long userId,
            Long couponId,
            BlockException ex
    ) {
        return CouponResult.busy();
    }
}
```

使用方式：

```java
@SentinelResource(
        value = "coupon.receive",
        blockHandler = "receiveBlocked",
        blockHandlerClass = SentinelBlockHandlers.class
)
public CouponResult receive(Long userId, Long couponId) {
    return couponClient.receive(userId, couponId);
}
```

### 4. `fallback`

`fallback` 处理业务异常，例如：

- `TimeoutException`
- `IllegalStateException`
- `RuntimeException`
- 下游 SDK 抛出的业务异常

示例：

```java
@SentinelResource(value = "recommend.list", fallback = "recommendFallback")
public List<ProductDTO> recommend(Long userId) {
    return recommendClient.list(userId);
}

public List<ProductDTO> recommendFallback(Long userId, Throwable ex) {
    return productCache.getDefaultRecommendations();
}
```

`fallback` 可以返回缓存、默认值、空列表或更保守的业务结果。但它不能随便伪造成功。

例如扣款接口不应该这样写：

```java
public PayResult payFallback(PayCommand command, Throwable ex) {
    return PayResult.success();
}
```

这不是降级，是制造账务事故。系统不会因为返回了 `success` 就真的扣款成功，这种显而易见的事情，最好不要让生产环境亲自提醒我们。

### 5. `defaultFallback`

`defaultFallback` 是通用兜底方法。它适合多个方法返回值一致、兜底逻辑一致的场景。

示例：

```java
@SentinelResource(value = "tag.query", defaultFallback = "defaultFallback")
public List<TagDTO> queryTags(Long itemId) {
    return tagClient.queryTags(itemId);
}

public List<TagDTO> defaultFallback(Throwable ex) {
    return Collections.emptyList();
}
```

不要滥用全局默认兜底。不同业务的失败语义不同，过度统一会让系统表面整齐，实际含义混乱。

### 6. `exceptionsToTrace` 与 `exceptionsToIgnore`

`exceptionsToTrace` 指定哪些异常会被 Sentinel 记录并触发 fallback。

`exceptionsToIgnore` 指定哪些异常忽略，不进入 fallback，也不计入 Sentinel 异常统计。

示例：

```java
@SentinelResource(
        value = "order.detail",
        fallback = "detailFallback",
        exceptionsToIgnore = {BusinessException.class}
)
public OrderDetail detail(Long orderId) {
    return orderClient.detail(orderId);
}
```

如果 `BusinessException` 是可预期的业务失败，例如“订单不存在”，就不应该用 Sentinel fallback 处理。否则监控里会把正常业务分支误判成系统不健康。

## 五、统一异常处理还是局部处理

两种方式都可以用，关键是分工清楚。

### 1. 统一异常处理

适合 Web 接口统一返回格式：

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BlockException.class)
    public ResponseEntity<ApiResult<Void>> handleBlock(BlockException ex) {
        ApiResult<Void> body = ApiResult.fail("系统繁忙，请稍后再试");
        return ResponseEntity.status(429).body(body);
    }
}
```

优点：

- 返回结构统一。
- Controller 和 Service 代码干净。
- 便于记录日志和指标。

### 2. 局部 `blockHandler`

适合资源需要特殊返回：

```java
@SentinelResource(value = "search.suggest", blockHandler = "suggestBlocked")
public List<String> suggest(String keyword) {
    return searchClient.suggest(keyword);
}

public List<String> suggestBlocked(String keyword, BlockException ex) {
    return Collections.emptyList();
}
```

适合场景：

- 非 Web 场景。
- 某个资源需要特殊降级结果。
- 同一接口内部不同步骤有不同保护策略。

## 六、资源命名建议

推荐：

```text
order.create
order.cancel
order.detail
inventory.deduct
payment.prepay
search.suggest
recommend.list
```

不推荐：

```text
get
query
test-resource
demo
/api/v1/order/create/detail/query
```

命名原则：

- 稳定，不随 Java 类名频繁变化。
- 简短，但能看出业务含义。
- 用点号分层，不要混用太多风格。
- 入口 URL 资源和内部业务资源要区分。
- 告警里出现资源名时，值班同学能判断影响范围。

## 七、常见误区

1. 以为引入 Sentinel 后所有方法都自动受保护。
2. 规则资源名和埋点资源名不一致。
3. 把所有 `@SentinelResource` 都标成 `EntryType.IN`。
4. 用 `fallback` 处理本该由业务异常处理器处理的异常。
5. 对写操作返回“默认成功”。
6. `blockHandler` 方法签名不匹配，导致启动或运行时报错。
7. 在局部 fallback 中吞掉异常，却不记录日志和指标。

## 八、总结

资源埋点负责告诉 Sentinel：“这里值得保护。”

`blockHandler` 处理 Sentinel 规则命中，`fallback` 处理业务异常。`EntryType.IN` 表示入口语义，`EntryType.OUT` 表示内部资源。Web 项目里入口通常已经由适配层处理，内部关键逻辑再用 `@SentinelResource` 做细粒度保护。

把这些边界分清，后面配置限流、熔断、热点参数和系统规则才不会乱。

## 参考资料

- [Sentinel 注解支持文档](https://github.com/alibaba/Sentinel/wiki/注解支持)
- [Spring Cloud Alibaba Sentinel Wiki](https://github.com/alibaba/spring-cloud-alibaba/wiki/Sentinel-en)
