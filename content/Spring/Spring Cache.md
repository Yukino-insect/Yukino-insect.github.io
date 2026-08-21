+++
date = '2025-09-18T22:09:15+08:00'
draft = false
title = 'Spring Cache'
+++

Spring Cache 是 Spring 提供的一套缓存抽象。它本身不负责存储数据，而是把缓存的常见操作抽象成统一 API 和注解，再交给具体缓存实现，例如 ConcurrentMap、Caffeine、Redis、Ehcache。

一句话概括：**Spring Cache 负责“什么时候读写缓存”，缓存中间件负责“数据存在哪里”**。

## 一、为什么需要缓存抽象

如果项目直接操作 Redis，业务代码很容易变成这样：

```java
public UserVO getUser(Long id) {
    String key = "user:" + id;
    UserVO cached = redisTemplate.opsForValue().get(key);
    if (cached != null) {
        return cached;
    }

    User user = userRepository.findById(id);
    UserVO result = convert(user);
    redisTemplate.opsForValue().set(key, result, Duration.ofMinutes(10));
    return result;
}
```

这段代码不复杂，但会在很多查询方法里重复出现。Spring Cache 把这种模式改成声明式：

```java
@Cacheable(cacheNames = "user", key = "#id")
public UserVO getUser(Long id) {
    User user = userRepository.findById(id);
    return convert(user);
}
```

方法第一次执行时查数据库，并把返回值写入缓存；之后相同 Key 命中缓存时，方法体不会执行。

## 二、启用缓存

使用缓存注解前，需要启用缓存能力：

```java
@Configuration
@EnableCaching
public class CacheConfig {
}
```

Spring Boot 会根据依赖自动选择 `CacheManager`。例如引入 Redis 相关依赖并配置连接信息后，通常会自动使用 `RedisCacheManager`。

```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 10m
      cache-null-values: false
```

如果没有引入外部缓存，Boot 可能退回到简单的本地缓存实现。开发环境看似正常，生产环境却没有共享缓存，这种差异要提前确认。

## 三、核心接口

Spring Cache 的几个核心接口如下：

| 接口 | 作用 |
| --- | --- |
| `Cache` | 表示一个具体缓存区域，提供 `get`、`put`、`evict` 等操作 |
| `CacheManager` | 管理多个 `Cache` |
| `CacheResolver` | 动态决定使用哪些缓存 |
| `KeyGenerator` | 根据方法和参数生成缓存 Key |
| `CacheErrorHandler` | 处理缓存读写异常 |

常见关系：

```text
@Cacheable
 -> CacheInterceptor
 -> CacheResolver / CacheManager
 -> Cache
 -> Redis / Caffeine / ConcurrentMap
```

缓存注解本质上也是通过 AOP 拦截方法调用实现的，所以同类内部自调用同样可能导致缓存注解不生效。

## 四、常用注解

### 1. `@Cacheable`

`@Cacheable` 表示先查缓存，命中则直接返回；未命中才执行方法，并把返回值写入缓存。

```java
@Cacheable(cacheNames = "user", key = "#id")
public UserVO getUser(Long id) {
    return userRepository.findVOById(id);
}
```

常用属性：

| 属性 | 作用 |
| --- | --- |
| `cacheNames` / `value` | 缓存名称 |
| `key` | SpEL 表达式生成 Key |
| `keyGenerator` | 指定 Key 生成器 |
| `condition` | 满足条件才使用缓存 |
| `unless` | 方法执行后满足条件则不写缓存 |
| `sync` | 同一 Key 缓存加载时尝试同步 |

例如不缓存空结果：

```java
@Cacheable(cacheNames = "user", key = "#id", unless = "#result == null")
public UserVO getUser(Long id) {
    return userRepository.findVOById(id);
}
```

### 2. `@CachePut`

`@CachePut` 总会执行方法，并把返回值写入缓存。它适合更新后刷新缓存：

```java
@CachePut(cacheNames = "user", key = "#result.id")
public UserVO updateUser(UserUpdateRequest request) {
    User user = userRepository.update(request);
    return convert(user);
}
```

注意：如果更新方法返回值不是完整缓存对象，就不要用它刷新查询缓存，否则缓存里会写入残缺数据。

### 3. `@CacheEvict`

`@CacheEvict` 用于删除缓存：

```java
@CacheEvict(cacheNames = "user", key = "#id")
public void deleteUser(Long id) {
    userRepository.deleteById(id);
}
```

删除整个缓存区域：

```java
@CacheEvict(cacheNames = "user", allEntries = true)
public void refreshUserCache() {
}
```

`allEntries = true` 影响范围很大，生产环境慎用。

### 4. `@Caching`

当一个方法需要组合多个缓存操作时，可以使用 `@Caching`：

```java
@Caching(evict = {
        @CacheEvict(cacheNames = "user", key = "#id"),
        @CacheEvict(cacheNames = "userList", allEntries = true)
})
public void disableUser(Long id) {
    userRepository.disable(id);
}
```

这种场景常见于更新单个对象后，还要清理列表缓存。

## 五、Key 设计

缓存 Key 设计直接决定缓存是否可靠。

推荐显式声明 Key：

```java
@Cacheable(cacheNames = "order", key = "#userId + ':' + #status")
public List<OrderVO> listOrders(Long userId, Integer status) {
}
```

也可以自定义 `KeyGenerator`：

```java
@Bean
public KeyGenerator keyGenerator() {
    return (target, method, params) -> {
        String joinedParams = Arrays.stream(params)
                .map(String::valueOf)
                .collect(Collectors.joining(":"));
        return target.getClass().getSimpleName() + ":" + method.getName() + ":" + joinedParams;
    };
}
```

Key 设计建议：

- 包含业务维度，例如用户 ID、租户 ID、查询条件。
- 避免只使用方法名。
- 多租户系统必须把租户隔离维度放进 Key。
- 列表查询缓存要谨慎，因为查询条件组合太多。
- Key 规则稳定后再上线，否则旧缓存很难清理。

## 六、过期时间

Spring Cache 注解本身没有统一的 TTL 属性。过期时间通常由具体 `CacheManager` 配置。

Redis 示例：

```java
@Bean
public RedisCacheManager redisCacheManager(RedisConnectionFactory connectionFactory) {
    RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(10))
            .disableCachingNullValues();

    Map<String, RedisCacheConfiguration> cacheConfigs = Map.of(
            "user", defaultConfig.entryTtl(Duration.ofMinutes(30)),
            "dict", defaultConfig.entryTtl(Duration.ofHours(6))
    );

    return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(defaultConfig)
            .withInitialCacheConfigurations(cacheConfigs)
            .build();
}
```

不同缓存区域应设置不同 TTL。字典、配置类数据可以长一些；用户状态、库存、权限这类变化频繁的数据要短一些，甚至不适合缓存。

## 七、事务与一致性

缓存和数据库更新放在一起时，要小心事务边界。

例如：

```java
@Transactional
@CacheEvict(cacheNames = "user", key = "#id")
public void updateUser(Long id, UserUpdateRequest request) {
    userRepository.update(id, request);
}
```

如果数据库事务最终回滚，但缓存已经被删除，通常问题不大，只是下一次重新加载。但如果使用 `@CachePut` 提前写入新值，事务回滚后缓存可能比数据库更新。

更稳妥的策略：

- 更新数据时优先删除缓存，而不是直接更新缓存。
- 删除缓存尽量放在事务成功之后。
- 对强一致要求高的数据，不要依赖普通缓存注解解决。
- 缓存只是性能手段，不应成为唯一事实来源。

需要事务提交后再清理缓存时，可以结合事务事件：

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handleUserChanged(UserChangedEvent event) {
    cacheManager.getCache("user").evict(event.userId());
}
```

这样可以避免事务回滚时提前改动缓存。

## 八、缓存穿透、击穿和雪崩

Spring Cache 只是抽象层，不会自动解决所有缓存问题。

### 1. 缓存穿透

请求查询不存在的数据，每次都打到数据库。

常见处理：

- 缓存空值，但设置较短 TTL。
- 对非法 ID 做参数校验。
- 使用布隆过滤器拦截明显不存在的 Key。

### 2. 缓存击穿

热点 Key 过期瞬间，大量请求同时查询数据库。

常见处理：

- 热点 Key 设置更长 TTL。
- 使用互斥锁或单飞加载。
- `@Cacheable(sync = true)` 可在单机内减少同 Key 并发加载，但分布式场景仍要依赖外部锁或缓存能力。

### 3. 缓存雪崩

大量 Key 同时过期，导致数据库压力陡增。

常见处理：

- TTL 增加随机抖动。
- 分批预热缓存。
- 限流和降级。
- 核心缓存使用多级缓存或高可用缓存集群。

这些问题属于缓存系统设计，不是加一个注解就会自动消失。注解很安静，但数据库会很诚实。

## 九、常见失效原因

### 1. 同类内部调用

```java
public UserVO outer(Long id) {
    return this.getUser(id);
}

@Cacheable(cacheNames = "user", key = "#id")
public UserVO getUser(Long id) {
    return userRepository.findVOById(id);
}
```

`this.getUser(id)` 没有经过 Spring 代理，缓存注解不会生效。解决方式是把缓存方法放到另一个 Bean，或者通过代理对象调用。

### 2. 方法不是 `public`

Spring AOP 对非 `public` 方法的代理行为容易受代理方式影响。缓存注解建议放在 `public` 方法上。

### 3. 返回对象不能序列化

使用 Redis 缓存时，返回值需要能被配置的序列化器处理。复杂对象、懒加载代理对象、循环引用都可能导致序列化失败。

### 4. Key 不稳定

使用对象作为 Key 时，如果 `toString`、`equals`、`hashCode` 不稳定，可能导致缓存命中异常。复杂查询条件建议显式拼接关键字段。

## 十、总结

Spring Cache 的使用重点不是记住注解，而是看清四件事：

- `@Cacheable`：读缓存，未命中后执行方法并写缓存。
- `@CachePut`：总是执行方法，并把结果写缓存。
- `@CacheEvict`：删除缓存。
- `CacheManager`：决定缓存真正存在哪里、如何过期、如何序列化。

简单查询可以直接使用缓存注解；复杂一致性、热点数据和分布式并发场景，要把缓存当成系统设计问题处理。否则缓存会从“性能优化”变成“问题加速器”，这并不是它的职业理想。
