+++
date = '2026-03-22T15:55:41+08:00'
draft = false
title = 'Sentinel 基础'
+++

Sentinel 是 Alibaba 开源的流量控制组件。

它的使用可以分为两部分：

- 控制台
- 核心库

## 控制台

通过一系列手段搞到 jar 包，启动的控制台。启动命令如下：

```bash
java -Xms512m -Xmx512m -XX:+UseG1GC -Dserver.port=8858 -Dcsp.sentinel.dashboard.server=localhost:8858 -Dproject.name=sentinel-dashboard -jar sentinel-dashboard-1.8.6.jar
```

- `-X` 用于指定虚拟机参数
- `-Dserver.port` 用于指定控制台端口
- `-Dcsp.sentinel.dashboard.server` 用于指定自身标识
- `-Sproject.name` 用于指定应用名

控制台启动后在浏览器中访问

```http
http://localhost:8858
```

输入账号和密码

```text
sentinel / sentinel
```

Sentinel 控制台并不会主动连接 Sentinel 客户端，需要客户端主动上报。我们需要在 Spring Boot 客户端配置一下。

```yaml
spring:
  cloud:
    sentinel:
      transport:
        dashboard: localhost:8858
        port: 8719
```

- `dashboard` 是控制台地址
- `port` 是客户端和控制台通信的地址

成功启动后可以在机器列表中查看是否注册到控制台。

## 核心库

Sentinel 是本地流控组件。实现流控只需要两步：

1. 定义资源。
2. 定义规则。

### 定义资源

Sentinel 提供了大致两种方式定义资源，一种是硬编码，另一种是使用注解。

#### SphU#entry()

我们可以使用 `SphU#entry()` 定义资源并埋点

```java
try (Entry entry = SphU.entry(UserService.USERS_RESOURCE)) {
    return userService.getUsers();
} catch (BlockException e) {
    System.out.println("limited");
}
```

该方法如果触发规则了会抛出 `BlockException`。当然还有一种返回 `boolean` 值类型的，就不了解了。

#### @SentinelResource

硬编码方式对代码侵入高，不优雅，可以使用注解形式。下面给出该注解的定义。

```java
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Inherited
public @interface SentinelResource {
    String value() default "";

    EntryType entryType() default EntryType.OUT;

    int resourceType() default 0;

    String blockHandler() default "";

    Class<?>[] blockHandlerClass() default {};

    String fallback() default "";

    String defaultFallback() default "";

    Class<?>[] fallbackClass() default {};

    Class<? extends Throwable>[] exceptionsToTrace() default {Throwable.class};

    Class<? extends Throwable>[] exceptionsToIgnore() default {};
}
```

该注解的作用是定义一个受 Sentinel 保护的资源，并指定当触发规则或业务异常时如何兜底。

它本质上是声明一个埋点，并定义一套异常限流处理策略。下面来详细了解一下各个参数的作用。

##### value 用于定义资源名，是 Sentinel 识别和匹配规则的唯一标识

定义资源名称时，我们要有一个良好的命名规范。这里推荐使用如下形式：

```markdown
模块.动作
```

例如：`user.get`、`user.update` 等。

##### entryType 用于标记该资源是入口还是内部调用

一共有如下两种类型：

- `EntryType.IN` 对外入口，如 HTTP、RPC
- `EntryType.OUT` 内部下游调用

如果接口是 Controller 外部调用接口，应该使用 `IN`；如果是 Service / DB / RPC / OpenFeigon 的内部调用，应该使用 `OUT`。

##### resourceType 用于资源分类标记，可以直接忽略

##### blockHandler 用于指定规则触发兜底的方法

如果该接口触发 Sentinel 规则时，比如，限流、熔断、系统保护、热点参数等。就会触发该参数指定的方法。该方法的定义需要满足：

- 方法名要与原埋点接口一致
- 参数列表在原接口的基础上添加一个 `BlockException` 参数
- 返回值要与埋点处一致

该方法只处理 Sentinel 规则抛出的 `BlockException` 异常，并不会处理业务异常。

##### blockHandlerClass 用于指定 blockHandler 方法所在的类

如果 `blockHandler` 方法没有与 `@SentinelResource` 定义的资源在一个类中，那么它在别的类中的定义时需要用 `static` 修饰

##### fallback 业务异常兜底

如果业务代码抛出

- `NullPointerException`

- `IllegalArgumentException`

- `RuntimeException`

等非 `BlockException` 异常时，可以由该方法处理。

##### defaultFallback 通用兜底

没有指定 `fallback` 时的通用兜底方法

##### fallbackCalss 用于指定 fallback 所在的类，与 blackHandlerClass 类似

##### exceptionsToTrace 用于指定哪些异常会触发 fallback

##### exceptionsToIgnore 用于指定哪些异常不触发 fallback

看完上面的内容，我们发现 Sentinel 提供了很多局部异常的处理方法。但是在 Spring 项目中我们通常会使用 Spring MVC 提供的统一异常处理器 `@RestControllerAdvice` 处理异常。 Sentinel 最终只负责判断是否拦截请求；Spring MVC 负责怎么返回给客户端。全局处理器定义如下：

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BlockException.class)
    public ResponseEntity<?> handle(BlockException ex) {
        return ResponseEntity
                .status(429)
                .body("系统繁忙，请稍后再试");
    }
}
```

整个的调用处理架构

```markdown
Sentinel
  └─ 负责拦截（抛 BlockException）

Spring MVC
  └─ 统一异常处理
      ├─ BlockException
      ├─ BusinessException
      └─ Exception
```

但是如果在非常局部、非常特殊的接口，返回给客户端的信息不一样、或者是在非 Web 场景，没有 Spring MVC的情况下。那么我们可以使用 `blockHandler` 做处理。

`blockHandler` 是用于处理 `BlockException` 的。而 `fallback` 对于处理 Service 层 / 非 Web 场景下的非 `BlockException` 异常时非常有价值 。它可以在这些场景中定义一些：

- 降级策略

- 业务兜底

- 默认值返回

我们发现 `@SentinelResource` 的 `entryType` 的默认类型为 `EntryType.OUT`，但是 Controller 层需要 `EntryType.IN` 类型。那为什么官方把 `@SentinelResource` 的默认值设置成 `EntryType.OUT` 呢？

`@SentinelResource` 在设计时是被设计成通用埋点注解，而不是入口注解。默认 `EntryType.OUT` 可以避免错误地把大量内部方法当成系统入口，从而污染调用链和系统设计。它的目的是让任何一段代码都可以被 Sentinel 保护。也就是说，它可能被用在：

- Controller 方法
- Service 方法
- RPC 客户端方法
- DB 操作方法
- 定时任务
- 工具类方法

等很多方法中。但是这些地方绝大多数都不应该是入口类型。因此 `@SentinelResource` 的默认值设置成了 `EntryType.OUT`。

一个合理的调用链路长应该长这样：

```markdown
HTTP(IN)
 └── Service(OUT)
      └── DB(OUT)
```

那我们在写 Controller 层时会不会很麻烦，需要在每个方法上指明类型？

其实 Sentinel 官方提供了 Web 适配模块，如果我们引入了 Spring Cloud Alibaba，Controller 层的方法根本不需要手动指明 `EntryType.IN`。

在 Spring Cloud Alibaba 中，HTTP 请求在进入 Controller 之前已经被 Sentinel 的 Web 适配层自动埋点了，并以 `ENtryType.IN` 标记为入口流量，Controller 方法本身处在这条入口的调用链之内，因此天然就是 IN。

Sentinel 的 Web 适配模块依赖是 `sentinel-web-servlet / sentinel-web-webflux`。

一次 HTTP 请求的生命周期如下：

```markdown
HTTP 请求
  ↓
Servlet Filter / WebFlux Filter
  ↓
Sentinel Web Filter
  ↓
DispatcherServlet
  ↓
Controller 方法
```

那 `@SentinelResource` 在 Controller 上到底扮演什么角色？

`@SentinelResource` 这时主要的职责并不是入口标记，而是资源声明。

当我们在 Controller 上写：

```java
@SentinelResource("order.create")
@PostMapping("/orders")
public Order create() { }
```

它并不会新建一个 IN 入口。而是在已有的 IN 上下文中，新增一个受保护资源节点。

为什么框架要在 HTTP 层而不是 Controller 层做 IN？因为 HTTP 才是真正的系统入口

- Controller 只是 MVC 的一个环节
- Filter 层才是：
  - 最外层
  - 最稳定
  - 不受开发者误用影响

那如果在 Controller 上手动写指明 `EntryType.IN` 会怎样？

可能会出现多个 IN 吧。（没试过）

##### EntryType 是什么？

> `EntryType` 是一个枚举类。`EntryType.IN` 用于定义调用链的起点，`EntryType.OUT` 用于定义调用链中的内部节点；
> IN 决定链路和系统级统计的边界，OUT 只参与局部统计与规则判断。

以 Spring Cloud Alibaba + HTTP 请求 为例，一条健康、标准的链路是这样：

```markdown
EntranceNode  (IN)
   │
   ├─ Controller / @SentinelResource (OUT 或默认)
   │     │
   │     ├─ Service (OUT)
   │     │     └─ DB / RPC (OUT)
   │     │
   │     └─ Cache / MQ (OUT)
```

> **一条调用链只能有一个入口语义这个入口由第一个 EntryType.IN 决定。所有 OUT 都是挂在这个 IN 之下的子节点**

IN / OUT 类型对 Sentinel 行为有什么具体影响吗？

1. 对调用链构建的影响。**链路限流、链路统计，必须从 IN 开始**。
2. 对系统规则（System Rule）的影响。系统规则（CPU、Load、系统 QPS）**只统计入口流量**。这就是**为什么内部调用默认要用 OUT 避免把内部流量算成系统入口**。
3. 对普通限流 / 熔断规则的影响。**无**。
4. 对链路限流（按来源限）的影响。链路限流的语义是**从哪个入口（IN）进来，调用了哪个资源（OUT）**。如果把内部方法也标成  IN。会导致链路被打断、来源关系丢失、链路规则失效等。**IN 只能出现在真正的入口**。

它们之间的关系应该是：

1. **先有 IN，才有完整调用链**
2. **OUT 必须依附于某个 IN**
3. **IN 的数量决定系统统计口径**
4. **OUT 的数量决定链路细粒度**

如果两个 IN 嵌套的话会导致：

- 系统 QPS 被放大
- System Rule 频繁触发
- 链路限流语义混乱

因此，我们在使用时因该注意。调用链以 `EntryType.IN` 作为唯一入口节点，定义系统级统计边界；所有 `EntryType.OUT` 资源作为内部节点参与限流与熔断判断，但不影响入口统计，从而实现既有全局保护又有局部隔离的 Sentinel 调用链结构。

> 在同一条调用链中，`EntryType.IN` 和 `EntryType.OUT` 埋点出的资源可以完全不同。

### 定义规则

如何配置 Sentinel 限流规则？

1. 可以通过在本地硬编码配置规则。
2. 可以在 Sentinel DashBoard 编辑规则，然后推送到客户端。
3. 可以让客户端主动从数据源拉取规则数据。最常用使用的是 Nacos。我们可以使用 DashBoard 将编辑好的规则推送到 Nacos 持久化起来，然后在客户端配置好 Nacos 数据源，主动向 Nacos 拉取数据。 

> Sentinel 的规则并没有优先级，而是遵从规则覆盖机制，后加载的规则会覆盖原有的规则。

规则如何生效的呢？

Sentinel 通过在资源入口处埋点 `SphU#entry()` 触发 `Slot` 调用链，在业务执行前基于实时统计数据执行限流和熔断判断，一旦规则命中即抛出 `BlockException`，从而以极低成本实现对资源的本地保护。

#### BlockException

`BlockException` 是触发规则时抛出的异常的父类。它的多个实现是分别对应具体规则触发时抛出的异常。整个体系如下：

```markdown
BlockException
     ├── FlowException
     ├── DegradeException
     ├── SystemBlockException
     ├── AuthorityException
     └── ParamFlowException
```

##### FlowException

触发规则

- QPS 限流
- 并发线程数限流
- 匀速排队
- Warm Up

对应 Slot

- `FlowSlot`

##### DegradeException

触发规则

- 异常比例
- 异常数
- 慢调用比例

对应 Slot

- `DegradeSlot`

##### SystemBlockException

触发规则

- CPU 使用率
- Load
- 系统总 QPS
- 系统线程数

对应 Slot

- `SystemSlot`

##### AuthorityException

触发规则

- 授权规则（白名单 / 黑名单）

对应 Slot

- `AuthoritySlot`

##### ParamFlowException

触发规则

- 热点参数（如 userId、商品 ID）

对应 Slot

- `ParamFlowSlot`

我们在统一处理 `BlockException` 时可以细分处理
```java
@ExceptionHandler(BlockException.class)
public ResponseEntity<?> handle(BlockException ex) {

    if (ex instanceof FlowException) {
        return ResponseEntity.status(429).body("请求过多");
    }
    if (ex instanceof DegradeException) {
        return ResponseEntity.status(503).body("服务降级中");
    }
    if (ex instanceof SystemBlockException) {
        return ResponseEntity.status(503).body("系统压力过大");
    }

    return ResponseEntity.status(429).body("请求被拦截");
}
```

Sentinel 通过 `BlockException` 及其子类精确表达不同类型的保护规则命中结果，开发者应将其视为一种可预期的流量控制信号，并在统一异常处理层进行规范化处理，而不是当作系统错误对待。

#### AbstractRule 

该类是 Sentinel 中所有规则的基类，它本身不包含任何限流算法或判断逻辑，它只是一个规则数据模型的公共父类。整个继承体系如下：

```markdown
AbstractRule
  ├── AuthorityRule
  ├── DegradeRule
  ├── FlowRule
  ├── ParamFlowRule
  └── SystemRule
```

`AbstractRule` 包含的字段如下：

```java
public abstract class AbstractRule implements Rule {
    private Long id;
    private String resource;
    private String limitApp;
    private boolean regex;
}
```

- `id` 是规则的唯一标识，主要给控制台、持久化用。
- `resource` 是规则作用的资源名。
- `limitApp` 是调用来源限制。
- `regex` 用来规定 `limitApp` 是普通字符串还是正则表达式。

我们可以看到它还继承了一个 `Rule` 接口。这个接口只定义了一个获取资源的方法。

```java
public interface Rule {
    String getResource();
}
```

##### FlowRule

该类代表的是对某个资源，在什么维度（QPS / 并发）、以什么策略（直接 / 关联 / 链路）、用什么整形方式（快速失败 / WarmUp / 排队），允许多少流量通过。

```java
public class FlowRule extends AbstractRule {
    private int grade = 1;
    private double count;
    private int strategy = 0;
    private String refResource;
    private int controlBehavior = 0;
    private int warmUpPeriodSec = 10;
    private int maxQueueingTimeMs = 500;
    private boolean clusterMode;
    private ClusterFlowConfig clusterConfig;
    private TrafficShapingController controller;
}
```

下面看一下各个参数的含义：

##### grade 限流指标类型

- `0` 代表并发线程数。统计**同时执行的线程数**
- `1` 代表 QPS（默认）。统计**单位时间通过的请求数**

##### count 阈值

它定义了**允许的最大值**

- QPS 模式：`count = 100`。代表每秒最多 100 次
- 并发模式：`count = 10`。代表同时最多 10 个线程

##### strategy 流控策略

- `0`。代表直接策略，只看当前资源（默认）
- `1`。代表关联策略，关联另一个资源
- `2`。代表链路策略，按入口来源限流

最常用的就是直接策略。

```java
strategy = 0;
```

**如果当前资源超了就限流**。

关联策略需要指定 refResource

```java
strategy = 1;
refResource = "db.order.insert";
```

语义：

> **当 A 资源压力大时，限 B 资源**

典型场景是当写 DB 压力大时，限读接口。

链路策略

```java
strategy = 2;
```

语义：

> **只限制从某个入口进来的请求**

必须有 `EntryType.IN` 的入口。

##### refResource 关联资源名

含义

- **仅在 `strategy = 1`（关联）时生效**
- 表示**被观察的资源**

##### controlBehavior 流量整形方式

当超出阈值时怎么处理请求

- `0`。快速失败，直接抛 `FlowException`
- `1`。Warm Up，冷启动
- `2`。排队等待，匀速排队

Sentinel 默认选择快速失败。

Warm Up代表冷启动保护。

```java
controlBehavior = 1;
warmUpPeriodSec = 10;
```

语义：

> **系统刚启动时，慢慢放量**

典型场景：

- 缓存刚启动
- 数据未预热

 排队等待

```java
controlBehavior = 2;
maxQueueingTimeMs = 500;
```

语义：

> **请求排队，匀速放行**。适合后台任务 / MQ 消费。

##### warmUpPeriodSec 预热时长

仅在 `controlBehavior = 1` 时生效，单位为秒。

##### maxQueueingTimeMs 最大排队时间

仅在 `controlBehavior = 2` 时生效，如果等待事件超过这个值，会直接拒绝请求。

##### clusterMode 是否集群限流

可选值：

- `false`（默认）：**单机限流**
- `true`：**集群限流**

##### clusterConfig 集群限流配置

只在 `clusterMode = true` 时生效

##### controller 流控算法执行器

Sentinel 内部生成的**策略执行器**

根据 grade、controlBehavior、count 等参数动态创建**不需要、也不应该手动配置**。

执行该规则的 Slot 是 `FlowSlot`

触发异常 是 `FlowException`

`FlowRule` 是 Sentinel 流量控制的规则模型，用于定义限流指标、阈值、关联策略以及流量整形方式，其本身不执行算法，而由 FlowSlot 在运行期结合统计数据与 TrafficShapingController 实现限流决策。

##### DegradeRule

在统计窗口内，当资源足够繁忙且足够不健康时，触发熔断，并在一段时间内直接拒绝请求

```java
public class DegradeRule extends AbstractRule {
    private int grade = 0;
    private double count;
    private int timeWindow;
    private int minRequestAmount = 5;
    private double slowRatioThreshold = (double)1.0F;
    private int statIntervalMs = 1000;
}
```

##### grade 熔断策略类型

表示用什么维度判断不健康

- `0`。慢调用比列，RT 慢的比例
- `1`。异常比例，异常 / 总请求
- `2`。异常数，异常的绝对数量

> Sentinel 1.8.x 以后：**慢调用比例是首推**

##### count 触发阈值

含义随 `grade` 改变：

- `grade = 0`（慢调用比例）
  - `count` = **RT 阈值（毫秒）**
- `grade = 1`（异常比例）
  - `count` = **比例阈值**（0~1）
- `grade = 2`（异常数）
  - `count` = **异常次数阈值**

##### timeWindow 熔断持续时间

熔断后，**多长时间内直接拒绝请求**。单位为秒。

整个运行过程是：

```markdown
触发熔断
  ↓
timeWindow 秒内：全部拒绝
  ↓
进入半开（尝试放行）
```

> **过短会抖动，过长影响可用性**

##### minRequestAmount 最小请求数门槛

> **统计窗口内，请求数 ≥ 这个值，才会触发熔断判断**

作用：

- 防止低流量下误触发
- 防止偶发异常导致熔断

这是一个**防抖阈值**

##### slowRatioThreshold 慢调用比例阈值

仅在 `grade = 0`（慢调用比例）时生效。**慢调用占比大于等于这个值就会触发熔断**。

示例：

设置 `slowRatioThreshold = 0.5`。10 个请求中，5 个 RT 大于 count（RT 阈值）就会触发熔断。

##### statIntervalMs 统计窗口长度

统计请求 / 异常 / RT 的时间窗口。单位毫秒。默认值是 1 秒。

**它和 timeWindow 是两个完全不同的概念：**

- `statIntervalMs` 代表一个小窗口的限制流量
- `timeWindow` 代表熔断时长

三种熔断策略的完整语义对照：

最推荐慢调用比例

```java
grade = 0;
count = 2000;              // RT 阈值
slowRatioThreshold = 0.5;  // 慢调用比例
timeWindow = 10;
```

语义：

> **1 秒内，请求 ≥ minRequestAmount，其中 ≥ 50% 的请求 RT > 2s -> 熔断 10 秒**

适合：

- DB
- RPC
- 第三方 HTTP

异常比例

```java
grade = 1;
count = 0.3; 
timeWindow = 10;
```

语义：

> **异常比例 ≥ 30% -> 熔断**

适合：

- 稳定接口
- 明确异常语义

异常数

```java
grade = 2;
count = 5;     // 5 次异常
timeWindow = 10;
```

语义：

> **1 秒内异常 ≥ 5 次 -> 熔断**

执行该规则的 Slot 是 `DegradeSlot`

触发的异常是 `DegradeException`

`DegradeRule` 用于描述资源的熔断条件，通过在统计窗口内评估请求量与异常/慢调用情况，在资源不健康时触发熔断并在指定时间内快速失败，以防止故障扩散。

##### AuthorityRule

授权规则（黑白名单）

用于做访问来源控制，决定哪些调用方能访问某个资源，而 `strategy` 决定这是白名单还是黑名单规则。

```java
public class AuthorityRule extends AbstractRule {
    private int strategy = 0;
}
```

这个类看起来只有一个字段，但它**强烈依赖 `AbstractRule` 里的字段**：

```java
private String resource;   // 管哪个资源
private String limitApp;   // 对哪些来源生效
private boolean regex;     // limitApp 是否正则
```

**AuthorityRule 的真正语义是 strategy + limitApp + regex**

##### strategy 授权策略类型

- `0`。白名单，只允许 limitApp 中的来源
- `1`。黑名单，拒绝 limitApp 中的来源

> 默认是白名单

AuthorityRule 的运行期逻辑是什么？

当请求访问某个资源时：

1. `AuthoritySlot` 被执行
2. 找到该资源对应的 `AuthorityRule`
3. 取出：
   - `strategy`
   - `limitApp`
   - `regex`
4. 判断**当前调用来源**
5. 如果不符合规则**抛 `AuthorityException`**

`limitApp` 才是 `AuthorityRule` 的关键，虽然 `strategy` 决定黑/白名单，但**真正决定谁能访问的，是 limitApp**。

常见 limitApp 值可以是：

- `"app-a"`，直接指定具体资源
- `"app-b,app-c"`，使用 `,` 分割资源名。可以直接指定多个资源
- `"*"`，代表所有资源
- 可以使用正则，按模式匹配

正则匹配

```java
rule.setLimitApp("test-.*");
rule.setRegex(true);
```

语义：

> **所有 test- 前缀的服务都受影响**

**AuthorityRule 的优先级非常靠前**。在 Slot 链中是这样的：

```markdown
AuthoritySlot
  ↓
SystemSlot
  ↓
FlowSlot
  ↓
DegradeSlot
```

如果**没权限，后面的限流/熔断根本不会执行**。

`AuthorityRule` 通过白名单或黑名单策略，对指定资源的访问来源进行控制，主要用于服务间调用的访问隔离，而非流量控制或业务鉴权，其执行由 AuthoritySlot 在请求进入早期完成。

##### ParamFlowRule 

热点参数规则，对某个资源的某个参数维度，在单位时间内允许多少请求通过，并可为特定热点值配置更高或更低的阈值。

```java
public class ParamFlowRule extends AbstractRule {
    private int grade = 1;
    private Integer paramIdx;
    private double count;
    private int controlBehavior = 0;
    private int maxQueueingTimeMs = 0;
    private int burstCount = 0;
    private long durationInSec = 1L;
    private List<ParamFlowItem> paramFlowItemList = new ArrayList();
    private Map<Object, Integer> hotItems = new HashMap();
    private boolean clusterMode = false;
    private ParamFlowClusterConfig clusterConfig;
}
```

##### grade 限流指标类型

含义与 `FlowRule` 类似，但**热点参数场景几乎只用 QPS**：

- `1`。OPS
- `0`。并发线程数

##### paramIdx 参数索引

> **要对方法的第几个参数做限流。索引从 0 开始**

示例：

```java
public Order getOrder(Long userId, Long orderId)
```

- `paramIdx = 0` 代表 `userId`
- `paramIdx = 1` 代表 `orderId`

> **这是热点规则能否生效的关键字段**

##### count 默认阈值

对所有参数值的默认限流阈值

- QPS 模式：每秒允许多少次
- 并发模式：最多多少线程

如果某个参数值**没有单独配置热点项**，就用这个值。

##### controlBehavior 流控行为

- `0`。快速失败，默认
- `2`。排队等待

> **热点参数不支持 WarmUp**

##### maxQueueingTimeMs 最大排队时间

仅在 `controlBehavior = 2` 时生效，超过该时间直接拒绝。

#####  burstCount 突发流量容忍值

允许在一个时间窗口内临时多放行的请求数

示例：

```java
count = 10;
burstCount = 5
```

瞬时最多允许 15 次，用于吸收瞬时尖峰。

##### durationInSec 统计窗口长度

统计参数访问次数的窗口。单位秒，默认 1 秒。

##### paramFlowItemList 热点参数配置列表

为特定参数值单独配置阈值，每个 `ParamFlowItem` 表示：

```markdown
参数值 = X
允许 QPS = Y
```

示例语义：

userId = 1001 允许的 QPS 为 100。其他 userId 的 QPS 为 10。

**这是热点参数规则的灵魂**。

##### hotItems 运行期加速结构

`paramFlowItemList` 的 Map 形态，用于运行期快速查找 `ParamFlowItem`，**不需要、也不应该手动配置**

##### clusterMode 是否集群模式

- `false`：默认单机热点限流
- `true`：集群热点限流

##### clusterConfig 集群热点配置

仅在 `clusterMode = true` 时生效

该规则运行期完整判断逻辑：

当请求进入资源时：

1. `ParamFlowSlot` 执行
2. 根据 `paramIdx` 取参数值
3. 查 `hotItems` 是否有单独配置
   - 有，用该值的阈值
   - 没有，用 `count`
4. 按 `durationInSec` 统计访问次数
5. 超限抛 `ParamFlowException`

`ParamFlowRule` 通过对资源方法参数的访问频率进行统计与控制，实现热点参数限流，既能限制整体参数访问，又支持对特定热点值进行精细化配置，从而在高并发场景下有效防止“热点击穿”。

##### SystemRule 

系统保护规则

```java
public class SystemRule extends AbstractRule {
    private double highestSystemLoad = (double)-1.0F;
    private double highestCpuUsage = (double)-1.0F;
    private double qps = (double)-1.0F;
    private long avgRt = -1L;
    private long maxThread = -1L;
}
```

虽然它 **继承了 `AbstractRule`**：

```java
public class SystemRule extends AbstractRule
```

但要记住：

- **几乎不使用 `resource`**
- 不关心具体接口 / 方法
- **作用于整个 JVM**
- **只统计入口流量（IN）**

> 继承 `AbstractRule` 更多是为了统一规则管理模型，而不是语义继承。

##### highestSystemLoad 系统 Load 保护

当**系统 load > 该值**时，触发系统保护。特点：

- 只在 **Linux** 生效
- 和 CPU 核数强相关

##### highestCpuUsage CPU 使用率保护

**CPU 使用率阈值**，取值范围：`0 ~ 1`。

示例：

```markdown
0.8 = 80% CPU
```

触发条件，**CPU 使用率 > highestCpuUsage**。

##### qps 系统总入口 QPS

**整个系统的入口 QPS 上限**，统计所有 `EntryType.IN`。特点是

- 不区分资源
- 不区分接口
- 所有入口共享

使用场景

- 抗突发流量
- 兜底保护

##### avgRt 系统平均 RT

**系统整体平均响应时间**，单位毫秒。

触发条件是**平均 RT > avgRt**

##### maxThread 系统并发线程数

**当前 JVM 正在处理请求的线程数**，超过即触发系统保护。使用场景：

- 防止线程池耗尽
- 防止 Full GC 前雪崩

你会看到所有字段默认是 `-1` 或 `-1.0`

这意味着：**该维度的系统规则未启用。**SystemRule 是多维 AND 结构，只配了哪个就只检查哪个，其他维度直接忽略。

SystemRule 的运行期当请求进入时：

1. **必须是 `EntryType.IN`**
2. 执行 `SystemSlot`
3. 检查：
   - CPU
   - Load
   - 系统 QPS
   - 平均 RT
   - 线程数
4. **任一条件触发**
5. **抛 `SystemBlockException`**
6. **入口请求直接失败**

**不会进入 Service / DB / OUT 节点**

`SystemRule` 用于对 JVM 级系统负载进行保护，通过 CPU 使用率、系统 QPS、平均 RT、并发线程数等维度，在系统接近极限时快速拒绝入口请求，从而防止雪崩扩散，其本质是全局兜底保护机制，而非资源级限流策略。

关联模式：

资源调用方和被调用方之间是通过 `EntryType` 来确定的吗？它们之间如何处理能提高整体性能。

`RuleConstant` 类的作用

- 预热模式
- 排队等待模式
- 

热点规则

定义规则后，如何让规则在内存中生效

Sentinel 的规则只有在被加载进对应的 `RuleManager` 并成功注册后，才会在内存中立即生效；
生效与否与控制台无关，只取决于本地内存中的规则数据。

```markdown
RuleManager.loadRules(rules)
        ↓
rules 存入内存
        ↓
Slot 在每次请求中读取
        ↓
规则即时生效（无需重启）
```

| 规则类型      | RuleManager          |
| ------------- | -------------------- |
| FlowRule      | FlowRuleManager      |
| DegradeRule   | DegradeRuleManager   |
| AuthorityRule | AuthorityRuleManager |
| ParamFlowRule | ParamFlowRuleManager |
| SystemRule    | SystemRuleManager    |

参考：

https://www.cnblogs.com/crazymakercircle/p/14285001.html

https://github.com/all4you/sentinel-tutorial?tab=readme-ov-file
