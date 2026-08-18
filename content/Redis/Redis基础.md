+++
date = '2025-09-06T20:47:53+08:00'
draft = false
title = 'Redis 基础'
+++

Redis 是一款基于内存的高性能键值数据库。它不仅可以作为缓存使用，也提供了丰富的数据结构、持久化、复制、Lua 脚本、发布订阅、Stream 等能力。

理解 Redis 时，不要只把它看成一个“更快的 Map”。更准确的说法是：Redis 是一个以内存为主要工作介质、以数据结构命令为核心接口的存储系统。

## 一、Redis 的基本特征

Redis 的核心特点包括：

1. 数据主要存储在内存中，读写延迟低。
2. 单线程执行命令，避免了大量锁竞争；网络 I/O 等部分在新版本中可以使用多线程辅助。
3. 支持 String、Hash、List、Set、ZSet、Bitmap、HyperLogLog、Geo、Stream 等数据结构。
4. 支持 RDB、AOF、RDB + AOF 混合持久化。
5. 支持主从复制、Sentinel、Cluster 等高可用和扩展方案。

需要注意的是，Redis 快并不意味着可以无节制地存放所有数据。Redis 的成本主要来自内存，适合放热点数据、短期状态、计数、索引、轻量消息等。

## 二、Key 的设计原则

Redis 中所有 key 都是字符串。好的 key 设计会直接影响可读性、维护成本和集群扩展。

常见命名方式：

```text
业务:对象:标识:属性
```

例如：

```text
user:1001:profile
user:1001:following
article:9527:likes
cache:product:20001
```

实践建议：

1. key 名要稳定、清晰，不要把无意义的随机字符串作为业务 key。
2. 避免超长 key，key 本身也会占内存。
3. 给缓存类 key 设置 TTL，避免长期堆积。
4. 避免大 key，例如一个包含几百万成员的 Set、Hash 或 List。
5. Cluster 场景下，跨 key 操作要注意 hash slot；必要时使用 hash tag，例如 `order:{1001}:items` 和 `order:{1001}:status`。

## 三、String

String 是 Redis 最基础的数据类型，值可以是普通字符串、数字、JSON、序列化字节等。它是二进制安全的，因此也可以保存图片、压缩数据等二进制内容，只是实际业务中通常不建议把大文件放进 Redis。

常用命令：

```bash
SET user:1001:name "Tom"
GET user:1001:name
DEL user:1001:name

INCR article:9527:view_count
INCRBY article:9527:view_count 10
DECR stock:sku:20001

SET cache:product:20001 "{...}" EX 300
SET lock:order:1001 "request-id" NX PX 30000
```

适合场景：

1. 缓存对象。
2. 计数器。
3. 分布式锁的基础实现。
4. 短期状态标记。

## 四、Hash

Hash 是字段和值的映射，适合存储对象的多个属性。和把整个对象序列化成一个 String 相比，Hash 可以单独读取或修改某个字段。

```bash
HSET user:1001 name "Tom" age 18 city "Hangzhou"
HGET user:1001 name
HMGET user:1001 name city
HINCRBY user:1001 login_count 1
HGETALL user:1001
HDEL user:1001 city
```

适合场景：

1. 用户资料、商品信息等对象缓存。
2. 多字段计数。
3. 局部更新频繁的对象。

注意：当对象字段很多或者单个字段值很大时，Hash 也会变成大 key。不要因为 Hash 看起来像对象，就把一个业务域的所有数据都塞进去。

## 五、List

List 是有序列表，可以从两端插入和弹出。它适合实现简单队列、最新列表、任务缓冲等。

```bash
LPUSH timeline:1001 "post-1"
LPUSH timeline:1001 "post-2"
LRANGE timeline:1001 0 9

RPUSH queue:email "task-1"
BLPOP queue:email 0
```

适合场景：

1. 简单先进先出或后进先出队列。
2. 最近 N 条记录。
3. 轻量任务缓冲。

限制也很清楚：List 没有完善的消费者组、消息确认、重试和死信机制。如果要做更可靠的消息队列，优先考虑 Redis Stream，或者使用专业 MQ。

## 六、Set

Set 是无序且元素唯一的集合，适合去重、成员判断和集合运算。

```bash
SADD article:9527:tags redis cache database
SISMEMBER article:9527:tags redis
SCARD article:9527:tags
SMEMBERS article:9527:tags

SINTER user:1001:following user:1002:following
SUNION role:admin:users role:editor:users
SDIFF user:1001:following user:1002:following
```

适合场景：

1. 标签。
2. 用户关系。
3. 去重集合。
4. 共同好友、共同关注等集合运算。

Set 的查询和成员判断很快，但成员数量过大时会形成大 key。关于大规模 Set 的建模，可以参考单独的《Redis Set》文章。

## 七、ZSet

ZSet 是有序集合。每个成员都有一个 score，Redis 会根据 score 排序。成员唯一，但 score 可以相同。

```bash
ZADD rank:article 100 "article-1"
ZADD rank:article 230 "article-2"
ZINCRBY rank:article 10 "article-1"

ZREVRANGE rank:article 0 9 WITHSCORES
ZRANK rank:article "article-1"
ZREVRANK rank:article "article-1"
ZSCORE rank:article "article-1"
```

适合场景：

1. 排行榜。
2. 延迟队列。
3. 根据时间戳排序的事件列表。
4. 带权重的 Top N 查询。

## 八、Bitmap

Bitmap 不是独立的数据类型，而是基于 String 的位操作能力。它适合表示大量二值状态。

```bash
SETBIT user:1001:signin:2025 0 1
SETBIT user:1001:signin:2025 1 1
GETBIT user:1001:signin:2025 1
BITCOUNT user:1001:signin:2025
```

适合场景：

1. 用户签到。
2. 是否活跃。
3. 是否完成某个动作。
4. 权限或状态标记。

Bitmap 的优势是省内存，但前提是偏移量不能过于稀疏。如果最大 offset 极大而实际数据很少，就会浪费空间。

## 九、HyperLogLog

HyperLogLog 用于基数统计，也就是估算不重复元素数量。它不是精确计数，但占用空间很小。

```bash
PFADD uv:2025-09-06 user1 user2 user3
PFCOUNT uv:2025-09-06

PFADD uv:2025-09-07 user2 user4
PFMERGE uv:2025-09 uv:2025-09-06 uv:2025-09-07
PFCOUNT uv:2025-09
```

适合场景：

1. 网站 UV。
2. 活跃用户估算。
3. 大规模去重计数。

如果业务要求精确值，就不要使用 HyperLogLog。

## 十、Geo

Geo 用于存储经纬度并进行距离计算和范围查询。底层基于 ZSet 实现。

```bash
GEOADD city:china 114.0579 22.5431 shenzhen
GEOADD city:china 120.1551 30.2741 hangzhou

GEOPOS city:china shenzhen hangzhou
GEODIST city:china shenzhen hangzhou km

GEOSEARCH city:china FROMLONLAT 120.1551 30.2741 BYRADIUS 300 km ASC
```

适合场景：

1. 附近的人。
2. 附近门店。
3. 地理围栏的粗略查询。

Geo 适合做初筛。如果要做复杂地理空间计算，仍然应该使用专业的地理空间数据库或搜索引擎能力。

## 十一、Stream

Stream 是 Redis 提供的追加型消息数据结构，支持消息 ID、消费者组、Pending List、ACK 等机制。它比 List 更适合实现可靠一些的队列。

写入和读取：

```bash
XADD stream:order * orderId 1001 status created
XLEN stream:order
XRANGE stream:order - +

XREAD COUNT 2 STREAMS stream:order 0-0
XREAD BLOCK 0 COUNT 1 STREAMS stream:order $
```

消费者组：

```bash
XGROUP CREATE stream:order group:order 0 MKSTREAM

XREADGROUP GROUP group:order consumer-1 COUNT 1 STREAMS stream:order >
XPENDING stream:order group:order
XACK stream:order group:order 1750000000000-0
```

Stream 适合：

1. 异步任务。
2. 事件流。
3. 需要消费者组的轻量消息队列。

但它仍然不是 Kafka、RocketMQ、RabbitMQ 的完全替代品。对于跨服务大规模消息系统，要根据吞吐、堆积、重试、顺序性、运维成本等因素选择。

## 十二、过期和淘汰

Redis 可以给 key 设置过期时间：

```bash
EXPIRE cache:product:20001 300
TTL cache:product:20001
SET cache:product:20001 "{...}" EX 300
```

过期不等于立刻删除。Redis 会结合惰性删除和定期删除来清理过期 key。

当内存达到 `maxmemory` 限制时，会根据 `maxmemory-policy` 执行淘汰策略。常见策略包括：

1. `noeviction`：不淘汰，写入时报错。
2. `allkeys-lru`：从所有 key 中淘汰最近最少使用的数据。
3. `allkeys-lfu`：从所有 key 中淘汰使用频率最低的数据。
4. `volatile-lru`：只从设置了过期时间的 key 中按 LRU 淘汰。
5. `volatile-ttl`：优先淘汰 TTL 更短的 key。
6. `allkeys-random` / `volatile-random`：随机淘汰。

缓存场景通常会选择 `allkeys-lru` 或 `allkeys-lfu`。如果 Redis 中混放了不能丢的数据，就需要更谨慎地规划实例，不要让缓存淘汰策略误伤核心数据。

## 十三、学习 Redis 的主线

学习 Redis 可以按这条线推进：

1. 先掌握 key 设计、TTL、内存淘汰和常用数据类型。
2. 再理解缓存一致性、穿透、击穿、雪崩、大 key、热 key。
3. 然后学习持久化、主从复制、Sentinel、Cluster。
4. 最后再根据业务需要深入 Stream、Lua、分布式锁、Bitmap、Bloom Filter 等专题。

Redis 的难点不在命令本身，而在什么时候该用、什么时候不该用，以及规模上来后如何控制内存、延迟和一致性风险。

## 参考资料

- Redis 官方文档：<https://redis.io/docs/latest/develop/data-types/>
- Redis 内存优化：<https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/>
