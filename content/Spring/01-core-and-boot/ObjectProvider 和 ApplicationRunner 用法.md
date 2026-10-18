+++
date = '2026-08-25T20:00:00+08:00'
draft = false
title = 'ObjectProvider 和 ApplicationRunner 用法'
+++

`ObjectProvider` 和 `ApplicationRunner` 都是 Spring 开发中很实用，但容易被低估的工具。

`ObjectProvider` 解决的是 Bean 依赖获取问题：依赖可能不存在、可能有多个、可能不想立刻创建。`ApplicationRunner` 解决的是应用启动后执行初始化逻辑的问题：容器已经准备好，此时可以做数据预热、配置检查、任务注册等动作。

## 一、ObjectProvider 是什么

`ObjectProvider<T>` 是 Spring 提供的依赖查找工具，它继承自 `ObjectFactory<T>`，主要用于在注入点上进行更灵活的 Bean 获取。

普通构造方法注入要求目标 Bean 必须存在：

```java
@Service
public class OrderService {

    private final PayService payService;

    public OrderService(PayService payService) {
        this.payService = payService;
    }
}
```

如果容器里没有 `PayService`，应用启动时就会失败。

而 `ObjectProvider` 可以把“是否真的需要这个 Bean”的决定推迟到运行时：

```java
@Service
public class OrderService {

    private final ObjectProvider<PayService> payServiceProvider;

    public OrderService(ObjectProvider<PayService> payServiceProvider) {
        this.payServiceProvider = payServiceProvider;
    }

    public void pay(Long orderId) {
        PayService payService = payServiceProvider.getIfAvailable();
        if (payService == null) {
            return;
        }

        payService.pay(orderId);
    }
}
```

这不是让依赖关系变得随便，而是让依赖关系变得可控。毕竟，连对象是否存在都没想清楚就强行注入，最后只会把启动异常写成谜语。

## 二、常用方法

### getObject

`getObject()` 会从容器中获取 Bean。如果没有找到，或者找到多个但无法确定唯一候选 Bean，通常会抛出异常。

```java
PayService payService = payServiceProvider.getObject();
payService.pay(orderId);
```

它适合用于“这个依赖必须存在”的场景。此时使用 `ObjectProvider` 的价值主要是**延迟获取**，而不是可选依赖。

### getIfAvailable

`getIfAvailable()` 表示：如果容器里有可用 Bean，就返回；如果没有，就返回 `null`。

```java
PayService payService = payServiceProvider.getIfAvailable();
if (payService != null) {
    payService.pay(orderId);
}
```

也可以传入默认对象：

```java
PayService payService = payServiceProvider.getIfAvailable(NoopPayService::new);
payService.pay(orderId);
```

如果只是想在存在时执行一段逻辑，可以使用 `ifAvailable`：

```java
payServiceProvider.ifAvailable(payService -> payService.pay(orderId));
```

### getIfUnique

`getIfUnique()` 表示：只有在能确定唯一 Bean 时才返回。

```java
PayService payService = payServiceProvider.getIfUnique();
if (payService != null) {
    payService.pay(orderId);
}
```

当同一类型存在多个 Bean，且没有 `@Primary` 或更明确的限定条件时，它会返回 `null`，不会像普通注入那样直接因为歧义而失败。

示例：

```java
@Service
public class AliPayService implements PayService {
}

@Service
public class WechatPayService implements PayService {
}
```

此时：

```java
PayService payService = payServiceProvider.getIfUnique();
```

无法确定唯一候选对象，结果就是 `null`。

如果其中一个 Bean 被标记为 `@Primary`：

```java
@Primary
@Service
public class AliPayService implements PayService {
}
```

`getIfUnique()` 就可以返回这个主要候选 Bean。

### stream

`ObjectProvider` 还可以拿到当前类型下的所有 Bean。

```java
payServiceProvider.stream()
        .forEach(payService -> payService.pay(orderId));
```

这适合插件式处理器、策略集合、扩展点等场景。

如果希望按 Spring 的排序规则执行，可以结合 `@Order`：

```java
@Order(1)
@Component
public class RiskCheckHandler implements OrderHandler {
}

@Order(2)
@Component
public class CouponHandler implements OrderHandler {
}
```

使用时：

```java
handlerProvider.orderedStream()
        .forEach(handler -> handler.handle(order));
```

`orderedStream()` 会按照 `Ordered` 或 `@Order` 定义的顺序返回 Bean。

## 三、适合 ObjectProvider 的场景

### 可选依赖

有些功能依赖外部模块，但外部模块不是必选项。

例如审计功能只有在引入审计模块时才启用：

```java
@Service
public class UserService {

    private final ObjectProvider<AuditService> auditServiceProvider;

    public UserService(ObjectProvider<AuditService> auditServiceProvider) {
        this.auditServiceProvider = auditServiceProvider;
    }

    public void createUser(String username) {
        // 创建用户
        auditServiceProvider.ifAvailable(auditService ->
                auditService.record("create user: " + username));
    }
}
```

这种写法比到处判断配置项更干净。依赖存在就用，不存在就跳过。

### 延迟获取

有些 Bean 创建成本比较高，或者只有在特定方法执行时才需要，可以使用 `ObjectProvider` 延迟获取。

```java
@Service
public class ReportService {

    private final ObjectProvider<HeavyReportExporter> exporterProvider;

    public ReportService(ObjectProvider<HeavyReportExporter> exporterProvider) {
        this.exporterProvider = exporterProvider;
    }

    public void export(Long reportId) {
        HeavyReportExporter exporter = exporterProvider.getObject();
        exporter.export(reportId);
    }
}
```

需要注意，`ObjectProvider` 推迟的是获取时机，不代表 Bean 一定不会在启动阶段创建。对于普通单例 Bean，是否预实例化还要看 Bean 本身的作用域、懒加载配置和容器创建策略。

### 多实现策略

如果某个接口有多个实现，可以通过 `ObjectProvider` 获取所有实现，再按业务条件选择。

```java
public interface NotifySender {

    boolean supports(String channel);

    void send(String receiver, String content);
}
```

```java
@Service
public class NotifyService {

    private final ObjectProvider<NotifySender> senderProvider;

    public NotifyService(ObjectProvider<NotifySender> senderProvider) {
        this.senderProvider = senderProvider;
    }

    public void send(String channel, String receiver, String content) {
        NotifySender sender = senderProvider.stream()
                .filter(item -> item.supports(channel))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("unsupported channel: " + channel));

        sender.send(receiver, content);
    }
}
```

如果策略数量固定，直接注入 `List<NotifySender>` 也可以。`ObjectProvider` 更适合依赖可选、需要延迟解析、或者希望调用时再决定获取方式的情况。

## 四、和 @Autowired(required = false) 的区别

`@Autowired(required = false)` 也能处理可选依赖：

```java
@Autowired(required = false)
private PayService payService;
```

但这种方式有几个问题：

- 它通常和字段注入一起出现，不利于测试和构造方法约束。
- 可选语义藏在注解参数里，不如 `ObjectProvider` 明确。
- 它只能处理注入阶段的可选，不能表达运行时按需获取、遍历、排序等行为。

更推荐的写法是构造方法注入 `ObjectProvider`：

```java
@Service
public class OrderService {

    private final ObjectProvider<PayService> payServiceProvider;

    public OrderService(ObjectProvider<PayService> payServiceProvider) {
        this.payServiceProvider = payServiceProvider;
    }
}
```

或者使用 `Optional<T>`：

```java
public OrderService(Optional<PayService> payService) {
    this.payService = payService;
}
```

如果只是表达“这个依赖可能不存在”，`Optional<T>` 很直观。如果还需要延迟获取、多 Bean 遍历、默认对象、唯一性判断，`ObjectProvider` 更合适。

## 五、ApplicationRunner 是什么

`ApplicationRunner` 是 Spring Boot 提供的启动回调接口。只要它本身是一个 Spring Bean，Spring Boot 就会在应用启动过程中调用它的 `run` 方法。

基本写法：

```java
@Component
public class StartupCheckRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        System.out.println("application started");
    }
}
```

`run` 方法接收的是 `ApplicationArguments`，它对命令行参数做了封装。

例如启动参数：

```bash
java -jar app.jar --init-cache=true --tenant=demo file1 file2
```

读取参数：

```java
@Component
public class ArgsRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        boolean initCache = args.containsOption("init-cache");
        List<String> tenants = args.getOptionValues("tenant");
        List<String> files = args.getNonOptionArgs();

        System.out.println(initCache);
        System.out.println(tenants);
        System.out.println(files);
    }
}
```

其中：

- `containsOption` 判断是否存在某个 `--xxx` 参数。
- `getOptionValues` 获取 `--key=value` 形式的参数值。
- `getNonOptionArgs` 获取非 `--` 开头的普通参数。

## 六、ApplicationRunner 的执行时机

`ApplicationRunner` 的执行时机在 Spring Boot 应用上下文创建完成之后。

这意味着：

- Bean 已经完成注册和依赖注入。
- 可以注入 Service、Repository、配置属性等 Bean。
- 可以读取启动参数。
- 如果 `run` 方法抛出异常，应用启动会失败。

它适合处理启动阶段必须完成的轻量逻辑，例如：

- 检查关键配置是否存在。
- 预热本地缓存。
- 初始化默认数据。
- 注册本地任务。
- 输出启动诊断信息。

不适合在里面执行很重的耗时任务。如果启动任务耗时很长，应用会长时间处于启动过程中；如果任务失败，整个应用也可能直接启动失败。

## 七、多个 Runner 的执行顺序

一个应用中可以有多个 `ApplicationRunner`。

如果顺序不重要，直接定义多个 Bean 即可：

```java
@Component
public class CacheWarmupRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        // 预热缓存
    }
}
```

```java
@Component
public class DataInitRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        // 初始化数据
    }
}
```

如果顺序重要，可以使用 `@Order`：

```java
@Order(1)
@Component
public class DataInitRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        // 先初始化数据
    }
}
```

```java
@Order(2)
@Component
public class CacheWarmupRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        // 再预热缓存
    }
}
```

数值越小，优先级越高。

也可以实现 `Ordered` 接口：

```java
@Component
public class DataInitRunner implements ApplicationRunner, Ordered {

    @Override
    public void run(ApplicationArguments args) {
        // 初始化数据
    }

    @Override
    public int getOrder() {
        return 1;
    }
}
```

## 八、ApplicationRunner 和 CommandLineRunner

`ApplicationRunner` 和 `CommandLineRunner` 都用于应用启动后执行逻辑，区别主要在参数类型。

| 接口 | 参数 | 特点 |
| --- | --- | --- |
| `ApplicationRunner` | `ApplicationArguments` | 参数已经被 Spring Boot 解析，适合读取 `--key=value` 形式的启动参数 |
| `CommandLineRunner` | `String... args` | 直接拿到原始字符串数组，适合简单参数处理 |

`CommandLineRunner` 示例：

```java
@Component
public class SimpleRunner implements CommandLineRunner {

    @Override
    public void run(String... args) {
        for (String arg : args) {
            System.out.println(arg);
        }
    }
}
```

如果需要解析命令行选项，优先使用 `ApplicationRunner`。如果只是拿到原始参数做简单处理，`CommandLineRunner` 足够。

## 九、组合使用示例

`ObjectProvider` 和 `ApplicationRunner` 可以组合使用，用来实现“启动后执行可选初始化器”的机制。

先定义一个扩展点：

```java
public interface StartupInitializer {

    void initialize();
}
```

不同模块可以按需实现这个接口：

```java
@Order(1)
@Component
public class DictionaryInitializer implements StartupInitializer {

    @Override
    public void initialize() {
        // 初始化字典数据
    }
}
```

```java
@Order(2)
@Component
public class CacheInitializer implements StartupInitializer {

    @Override
    public void initialize() {
        // 预热缓存
    }
}
```

统一在 `ApplicationRunner` 中执行：

```java
@Component
public class StartupInitializerRunner implements ApplicationRunner {

    private final ObjectProvider<StartupInitializer> initializerProvider;

    public StartupInitializerRunner(ObjectProvider<StartupInitializer> initializerProvider) {
        this.initializerProvider = initializerProvider;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!args.containsOption("init")) {
            return;
        }

        initializerProvider.orderedStream()
                .forEach(StartupInitializer::initialize);
    }
}
```

启动时传入参数：

```bash
java -jar app.jar --init
```

这样做的好处是：

- 主启动逻辑只依赖扩展点接口。
- 没有任何 `StartupInitializer` 实现时，应用也可以正常启动。
- 新增初始化逻辑只需要新增实现类。
- 执行顺序可以通过 `@Order` 控制。

这种写法很适合 starter、插件化模块、可选功能模块。如果一个模块根本没被引入，它的初始化器自然也不会出现在容器里。

## 十、注意事项

### 不要隐藏必要依赖

如果某个依赖是业务必需的，不应该为了让应用能启动就改成 `ObjectProvider`。

不推荐：

```java
public OrderService(ObjectProvider<OrderRepository> repositoryProvider) {
    this.repositoryProvider = repositoryProvider;
}
```

如果 `OrderRepository` 缺失时业务根本无法工作，就应该直接构造方法注入，让应用尽早失败。

### 注意多 Bean 歧义

`ObjectProvider` 可以缓解多 Bean 歧义，但不能替你决定业务规则。

如果多个实现中必须选一个，应使用更明确的方式：

- 使用 `@Primary` 指定默认实现。
- 使用 `@Qualifier` 指定具体 Bean。
- 使用策略接口的 `supports` 方法按业务条件选择。
- 使用配置项决定使用哪一种实现。

### 控制启动任务耗时

`ApplicationRunner` 会影响应用启动过程。

如果里面执行了大量网络请求、全量数据扫描、远程服务调用，启动时间就会被拉长。更稳妥的做法是：

- 启动阶段只做必要检查。
- 大任务交给异步任务或调度任务。
- 对远程调用设置超时时间。
- 对失败场景有明确策略。

### 注意事务和代理

`ApplicationRunner` 本身是 Spring Bean，可以注入其他 Bean。

如果启动逻辑需要事务，不建议在同一个 Runner 类的内部方法上直接写 `@Transactional` 然后自调用：

```java
@Component
public class InitRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        initData();
    }

    @Transactional
    public void initData() {
        // 这里可能因为自调用导致事务不生效
    }
}
```

更清晰的方式是把事务逻辑放到独立 Service 中：

```java
@Service
public class InitService {

    @Transactional
    public void initData() {
        // 初始化数据
    }
}
```

```java
@Component
public class InitRunner implements ApplicationRunner {

    private final InitService initService;

    public InitRunner(InitService initService) {
        this.initService = initService;
    }

    @Override
    public void run(ApplicationArguments args) {
        initService.initData();
    }
}
```

## 十一、总结

`ObjectProvider` 适合处理可选依赖、延迟获取、多实现遍历和按需解析。它不是用来掩盖缺失依赖的工具，而是用来表达“这个依赖在当前场景下可能存在，也可能暂时不需要”的工具。

`ApplicationRunner` 适合在 Spring Boot 应用启动后执行初始化逻辑。它能拿到已经创建好的 Bean，也能读取启动参数，但它会影响启动过程，因此不适合承载过重的任务。

两者组合起来，可以优雅地实现可选初始化、插件式启动任务和 starter 扩展点。简单说，`ObjectProvider` 负责“有没有、何时取、取哪些”，`ApplicationRunner` 负责“应用启动后什么时候执行”。分工明确，代码自然就不会那么难看。

## 参考

- [Spring Framework ObjectProvider API](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/beans/factory/ObjectProvider.html)
- [Spring Boot ApplicationRunner API](https://docs.spring.io/spring-boot/api/java/org/springframework/boot/ApplicationRunner.html)
- [Spring Boot SpringApplication Reference](https://docs.spring.io/spring-boot/reference/features/spring-application.html)
