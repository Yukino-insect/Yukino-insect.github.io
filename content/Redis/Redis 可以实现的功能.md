+++
date = '2025-09-20T20:34:39+08:00'
draft = false
title = 'Redis 可以实现的功能'
+++

Redis 常被称为缓存，但它能做的事远不止缓存。只要问题可以抽象成“快速读写某种数据结构”，Redis 往往都能提供一个轻量而高效的方案。

不过，Redis 不是万能后端。它适合解决高频、低延迟、状态较轻的问题；不适合承载复杂事务、强一致关系模型和长期海量冷数据。

## 一、缓存

缓存是 Redis 最常见的用途。典型读取流程是：

```text
读取请求
  -> 查询 Redis
  -> 命中：直接返回
  -> 未命中：查询数据库
  -> 回写 Redis，并设置 TTL
```

适合缓存的数据：

1. 热点数据。
2. 读多写少的数据。
3. 可以接受短暂不一致的数据。
4. 计算成本高、结果可复用的数据。

不适合缓存的数据：

1. 强一致实时数据。
2. 体积很大的对象。
3. 命中率很低的冷数据。
4. 没有过期策略、会无限增长的数据。

## 二、缓存一致性

Redis 作为缓存时，数据库通常仍然是最终的数据源。更新数据时，最常见的策略是：

```text
先更新数据库，再删除缓存
```

这样做的原因是：缓存可以在下次读取时重新加载，不必强行和数据库同时更新。

但在高并发下仍可能出现旧数据回写：

```text
线程 A 读缓存未命中
线程 A 查数据库，得到旧值
线程 B 更新数据库
线程 B 删除缓存
线程 A 把旧值写回缓存
```

常见缓解方案：

1. 延迟双删：更新数据库后删除缓存，隔一小段时间再删一次。
2. 给缓存设置较短 TTL，让错误数据有自然过期窗口。
3. 使用互斥锁或 singleflight，控制同一 key 的并发回源。
4. 通过 MQ 或订阅数据库 Binlog 异步删除/更新缓存。
5. 对强一致要求高的场景，直接读数据库或使用专门的一致性设计。

没有一种缓存一致性方案能免费解决所有问题。工程上要明确业务能接受的延迟窗口，再选择成本合适的方案。

## 三、缓存穿透、击穿、雪崩、污染

### 1. 缓存穿透

缓存和数据库中都不存在的数据被大量请求，导致请求直接打到数据库。

解决方案：

1. 参数校验，拦截明显非法请求。
2. 缓存空值，并设置较短 TTL。
3. 使用 Bloom Filter 判断数据是否可能存在。
4. 对异常来源做限流和风控。

### 2. 缓存击穿

某个热点 key 过期后，大量请求同时回源数据库。

解决方案：

1. 热点 key 不设置固定过期时间，由后台异步刷新。
2. 使用互斥锁，只允许一个线程回源。
3. 使用逻辑过期，先返回旧值，再异步刷新。
4. 提前预热热点数据。

### 3. 缓存雪崩

大量 key 在同一时间过期，或者 Redis 整体不可用，导致数据库压力暴涨。

解决方案：

1. TTL 增加随机抖动。
2. 热点数据分散到不同实例或不同过期时间。
3. Redis 做高可用部署。
4. 服务侧限流、降级、熔断。
5. 核心接口保留兜底数据或静态降级结果。

### 4. 缓存污染

大量低价值数据进入缓存，占用内存，挤出真正的热点数据。

解决方案：

1. 只缓存高命中率数据。
2. 设置合理 TTL。
3. 选择合适的内存淘汰策略，例如 `allkeys-lfu`。
4. 监控命中率、内存占用和 key 分布。

## 四、内存淘汰策略

Redis 达到 `maxmemory` 后，会根据 `maxmemory-policy` 决定如何处理新写入。

```conf
maxmemory 512mb
maxmemory-policy allkeys-lfu
```

常见策略：

| 策略 | 含义 | 适合场景 |
| --- | --- | --- |
| `noeviction` | 不淘汰，写入时报错 | 不能丢数据的场景 |
| `allkeys-lru` | 从所有 key 中淘汰最近最少使用的数据 | 通用缓存 |
| `allkeys-lfu` | 从所有 key 中淘汰使用频率最低的数据 | 热点相对稳定的缓存 |
| `volatile-lru` | 只淘汰设置了 TTL 的 key | Redis 中混有缓存和非缓存数据 |
| `volatile-ttl` | 优先淘汰 TTL 更短的 key | 临时数据 |
| `allkeys-random` | 从所有 key 中随机淘汰 | 要求不高的缓存 |

实践上，最好不要在同一个 Redis 实例中混放“可淘汰缓存”和“不可丢状态”。如果必须混放，就要非常谨慎地设置 TTL 和淘汰策略。

## 五、消息队列

Redis 可以实现轻量消息队列，但不同结构的可靠性差异很大。

### 1. 基于 List

生产者：

```bash
RPUSH queue:email "task-1"
RPUSH queue:email "task-2"
```

消费者：

```bash
BLPOP queue:email 0
```

优点是简单。缺点是消息一旦被 `POP` 出来就从队列删除，如果消费者处理时宕机，消息可能丢失。

### 2. 发布订阅

```bash
PUBLISH channel:notice "hello"
SUBSCRIBE channel:notice
```

发布订阅适合实时广播，不适合可靠队列。订阅者离线期间的消息不会自动补偿。

### 3. Stream

Stream 更适合做队列，因为它支持消费者组、ACK 和 Pending List。

```bash
XADD stream:order * orderId 1001 status created
XGROUP CREATE stream:order group:order 0 MKSTREAM
XREADGROUP GROUP group:order consumer-1 COUNT 1 STREAMS stream:order >
XACK stream:order group:order 1750000000000-0
```

如果只是系统内部的轻量异步任务，Stream 可以胜任。若需要大规模堆积、复杂重试、死信、严格顺序、多集群容灾，应该选择专业 MQ。

## 六、计数器

Redis 的 `INCR` 系列命令天然适合计数。

```bash
INCR article:9527:view_count
INCRBY article:9527:view_count 10
DECR stock:sku:20001
```

适合场景：

1. 浏览量。
2. 点赞数。
3. 库存扣减的前置校验。
4. 短期限额统计。

如果计数结果最终要落库，可以用定时任务或消息队列异步汇总。但要注意崩溃恢复、重复消费和最终一致性。

## 七、排行榜

ZSet 非常适合排行榜。

```bash
ZADD rank:article 100 article:1
ZADD rank:article 200 article:2
ZINCRBY rank:article 10 article:1

ZREVRANGE rank:article 0 9 WITHSCORES
ZREVRANK rank:article article:1
ZSCORE rank:article article:1
```

常见设计：

1. 日榜：`rank:article:day:2025-09-20`
2. 周榜：`rank:article:week:2025-W38`
3. 总榜：`rank:article:total`

日榜、周榜可以设置 TTL，避免历史榜单无限堆积。

## 八、分布式锁

Redis 可以用 `SET key value NX PX ttl` 实现基础分布式锁。

```bash
SET lock:order:1001 "request-id" NX PX 30000
```

含义：

1. `NX`：key 不存在时才设置。
2. `PX 30000`：锁 30 秒后自动过期。
3. `request-id`：锁持有者标识，释放锁时要校验。

释放锁要用 Lua 脚本保证“判断持有者”和“删除锁”是原子操作：

```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

Java 示例：

```java
public boolean tryLock(String key, String value, long expireMillis) {
    return Boolean.TRUE.equals(
        redisTemplate.opsForValue()
            .setIfAbsent(key, value, Duration.ofMillis(expireMillis))
    );
}

public void unlock(String key, String value) {
    String script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """;
    redisTemplate.execute(
        new DefaultRedisScript<>(script, Long.class),
        Collections.singletonList(key),
        value
    );
}
```

实际项目中更推荐使用 Redisson。它提供了可重入锁、自动续期、读写锁、信号量等能力。

```java
RLock lock = redissonClient.getLock("lock:order:1001");

if (lock.tryLock(3, 30, TimeUnit.SECONDS)) {
    try {
        // 业务逻辑
    } finally {
        lock.unlock();
    }
}
```

分布式锁尤其要注意：

1. 锁必须有过期时间。
2. 解锁必须校验持有者。
3. 业务执行时间可能超过锁过期时间。
4. Redis 主从切换时，极端情况下可能出现锁安全问题。
5. 对强一致锁语义要求很高时，应评估 ZooKeeper、etcd 或数据库锁。

## 九、限流

Redis 适合做分布式限流，因为多个应用实例可以共享同一份计数状态。

### 1. 固定窗口计数器

```bash
INCR rate:user:1001:202509202030
EXPIRE rate:user:1001:202509202030 60
```

简单，但窗口边界可能产生突刺流量。

### 2. 滑动窗口

使用 ZSet 保存请求时间戳：

```bash
ZADD rate:user:1001 1758361800000 "request-1"
ZREMRANGEBYSCORE rate:user:1001 0 1758361740000
ZCARD rate:user:1001
EXPIRE rate:user:1001 120
```

实际使用时应放进 Lua 脚本，保证删除旧请求、添加新请求、统计数量这一组操作原子执行。

### 3. 令牌桶

可以用 Redis 存储令牌数量和上次补充时间，也可以使用 Redisson 的 `RRateLimiter`。

令牌桶允许一定突发流量，比固定窗口更平滑。

## 十、分布式会话

单机应用可以把 Session 放在本地内存中；多实例部署后，请求可能打到不同节点，本地 Session 就会失效。

Redis 可以集中存储 Session：

```text
session:{sessionId} -> 用户信息、权限、登录状态
```

手动方式可以在拦截器中校验：

```java
public boolean preHandle(HttpServletRequest request,
                         HttpServletResponse response,
                         Object handler) throws Exception {
    String sessionId = request.getHeader("Session-Id");
    if (sessionId == null) {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        return false;
    }

    String key = "session:" + sessionId;
    if (Boolean.FALSE.equals(redisTemplate.hasKey(key))) {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        return false;
    }

    redisTemplate.expire(key, Duration.ofMinutes(30));
    return true;
}
```

Spring 项目也可以使用 Spring Session + Redis 接管 HttpSession。

```xml
<dependency>
    <groupId>org.springframework.session</groupId>
    <artifactId>spring-session-data-redis</artifactId>
</dependency>
```

## 十一、签到、活跃和状态标记

Bitmap 适合记录大量二值状态。

```bash
SETBIT signin:2025:user:1001 0 1
GETBIT signin:2025:user:1001 0
BITCOUNT signin:2025:user:1001
```

例如：

1. 用户是否签到。
2. 某天是否活跃。
3. 某个任务是否完成。
4. 某个权限位是否开启。

Bitmap 的前提是 offset 模型合理。如果 ID 稀疏，要小心空间浪费。

## 十二、去重和存在性判断

如果需要精确去重，可以使用 Set：

```bash
SADD uv:article:9527 user:1001
SISMEMBER uv:article:9527 user:1001
SCARD uv:article:9527
```

如果只需要估算不重复数量，可以使用 HyperLogLog：

```bash
PFADD uv:site:2025-09-20 user:1001 user:1002
PFCOUNT uv:site:2025-09-20
```

如果需要用较小空间判断元素是否可能存在，可以使用 Bloom Filter：

```bash
BF.ADD bf:product product:1001
BF.EXISTS bf:product product:1001
```

选择方式：

| 需求 | 推荐结构 |
| --- | --- |
| 精确成员判断和取成员列表 | Set |
| 精确二值状态 | Bitmap |
| 估算 UV | HyperLogLog |
| 允许误判的存在性判断 | Bloom Filter |

## 十三、Redis 适合与不适合

适合使用 Redis：

1. 高频读写。
2. 数据结构简单。
3. 数据量可控。
4. 可接受最终一致性。
5. 对低延迟要求高。

不适合使用 Redis：

1. 复杂事务。
2. 强一致核心账务。
3. 长期海量冷数据。
4. 多维复杂查询。
5. 无法接受内存成本的场景。

总结来说，Redis 的价值不只是“快”，而是把常见高并发问题抽象成一组简单、稳定、低延迟的数据结构操作。只要边界划得清楚，它会非常可靠；边界一旦模糊，它也会很诚实地把问题还给你。

## 参考资料

- Redis 数据类型官方文档：<https://redis.io/docs/latest/develop/data-types/>
- Redis Stream 官方文档：<https://redis.io/docs/latest/develop/data-types/streams/>
- Redis 分布式锁模式：<https://redis.io/docs/latest/develop/use/patterns/distributed-locks/>
