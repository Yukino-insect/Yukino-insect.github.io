+++
date = '2025-10-02T22:02:47+08:00'
draft = false
title = 'ID 生成方案'
+++

单机生成唯一 ID 很简单，AtomicLong、数据库自增、UUID 都能做到。问题出现在分布式环境：多个节点同时生成 ID，既要唯一，又要高性能，还最好对数据库索引友好。

一个工程上可用的 ID 方案，通常要考虑这些指标：

- 全局唯一。
- 高可用，不因为单点故障拖垮主流程。
- 性能足够高，不能成为写入瓶颈。
- 趋势递增，减少 B+Tree 索引页分裂。
- 长度可接受，便于存储、传输和排查。
- 不泄露过多业务信息。

没有一种方案在所有指标上都完美。选型时先问业务需要什么，而不是先背名词。名词不会替你扛故障。

## UUID

UUID 是 128 位标识，常见字符串形式是 36 个字符：

```java
String id = UUID.randomUUID().toString();
```

优点：

- 本地生成，不依赖中心服务。
- 全局唯一概率极高。
- 使用简单。

缺点：

- 字符串较长，占用空间大。
- 随机无序，对数据库聚簇索引不友好。
- 可读性差，不适合直接作为订单号展示。

UUID 适合日志追踪、外部请求 ID、幂等号等场景。作为 MySQL 主键也不是不能用，但高写入表要谨慎，尤其是 InnoDB 聚簇索引。

## 数据库自增

数据库自增 ID 是最传统的方案。

优点：

- 简单。
- 趋势递增。
- 数据库保证唯一。

缺点：

- 强依赖单库。
- 分库分表后不方便。
- 容易暴露业务规模。
- 高并发下可能成为瓶颈。

如果是单体应用、数据量不大、没有分库分表，自增主键依然是很稳的选择。别为了“分布式”三个字把系统改复杂，系统不会因此变得高贵。

## Redis 自增

Redis 的 `INCR` 是原子操作，可以生成全局递增 ID：

```bash
INCR order:id
```

优点：

- 性能高。
- 实现简单。
- ID 递增。

缺点：

- 依赖 Redis 高可用。
- Redis 数据持久化和故障恢复要处理好。
- 多业务要设计好 key，避免混用。

Redis 自增适合对 ID 连续性要求不高、已有 Redis 高可用架构的系统。为了降低单 key 热点，也可以按业务和日期分段：

```text
order:id:20261002 -> 1, 2, 3...
```

最终订单号可以拼成：

```text
20261002 + sequence
```

## Snowflake

Snowflake 是经典的 64 位趋势递增 ID。常见结构：

```text
0 | timestamp(41) | workerId(10) | sequence(12)
```

含义：

- 最高位固定为 0，保证正数。
- 时间戳部分保证趋势递增。
- 机器号保证不同节点不冲突。
- 序列号保证同一毫秒内可生成多个 ID。

优点：

- 本地生成，性能高。
- 64 位整数，存储友好。
- 趋势递增，适合作为数据库主键。

缺点：

- 依赖机器时钟。
- workerId 分配不能冲突。
- 时钟回拨处理不好会重复。

简单生成逻辑：

```java
public synchronized long nextId() {
    long timestamp = System.currentTimeMillis();

    if (timestamp < lastTimestamp) {
        throw new IllegalStateException("Clock moved backwards");
    }

    if (timestamp == lastTimestamp) {
        sequence = (sequence + 1) & sequenceMask;
        if (sequence == 0) {
            timestamp = waitNextMillis(lastTimestamp);
        }
    } else {
        sequence = 0L;
    }

    lastTimestamp = timestamp;

    return ((timestamp - epoch) << timestampShift)
            | (workerId << workerIdShift)
            | sequence;
}
```

生产环境使用 Snowflake 时，要重点处理：

- workerId 自动分配。
- NTP 时间同步。
- 小幅时钟回拨等待。
- 大幅时钟回拨告警并拒绝生成。
- 容器重启后 workerId 不重复。

## Leaf-snowflake

美团 Leaf 的 Snowflake 模式用 ZooKeeper 分配 workerId，减少人工配置冲突。

它相比手写 Snowflake 的优势：

- workerId 由 ZooKeeper 管理。
- 多节点部署时更容易保证机器号唯一。
- 对时钟回拨有检测和保护。
- 服务化后接入成本更统一。

适合场景：

- 日志 ID。
- 消息 ID。
- 链路追踪 ID。
- 对实时生成要求高的业务主键。

它仍然依赖时钟，所以不能忽视服务器时间同步。分布式系统里，时间这种东西看起来温顺，闹起来很不讲理。

## 号段模式

号段模式的思路是：服务一次从数据库申请一段 ID，缓存在本地内存中慢慢用。

表结构示例：

```sql
CREATE TABLE leaf_alloc (
  biz_tag VARCHAR(128) NOT NULL PRIMARY KEY,
  max_id BIGINT NOT NULL,
  step INT NOT NULL,
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

生成流程：

```text
1. 应用按 biz_tag 申请号段。
2. 数据库把 max_id 增加 step。
3. 应用拿到 [old_max_id + 1, new_max_id]。
4. 应用在内存中自增发号。
5. 号段快用完时提前申请下一段。
```

例如：

```text
biz_tag = order
old max_id = 10000
step = 1000
new max_id = 11000
可用 ID = 10001 到 11000
```

优点：

- 本地发号性能高。
- ID 递增。
- 数据库压力低，只有申请号段时访问数据库。
- 数据库短暂不可用时，当前号段还能继续使用。

缺点：

- 可能跳号。
- 依赖数据库分配号段。
- 多业务需要维护不同 `biz_tag`。

号段模式适合订单 ID、用户 ID、商品 ID 等业务主键。跳号通常不是问题，要求绝对连续才是问题。现实里绝对连续往往意味着你牺牲了并发和可用性，代价不小。

## 方案对比

| 方案 | 性能 | 趋势递增 | 依赖 | 适合场景 |
| --- | --- | --- | --- | --- |
| UUID | 高 | 否 | 无 | 请求 ID、幂等号、日志追踪 |
| 数据库自增 | 中 | 是 | 数据库 | 单体、小规模系统 |
| Redis 自增 | 高 | 是 | Redis | 简单分布式发号 |
| Snowflake | 很高 | 是 | 时钟、workerId | 高并发业务主键 |
| 号段模式 | 很高 | 是 | 数据库 | 订单、用户、商品等主键 |

## 选择建议

如果是单体应用，优先数据库自增。

如果需要全局唯一但不进数据库主键，可以用 UUID 或更短的随机 ID。

如果是高并发业务主键，优先 Snowflake 或号段模式。

如果团队已经有 Leaf、UidGenerator 这类统一发号服务，就接统一服务，不要每个业务自己手写一套。ID 重复这种故障，发生一次就足够让人记很久，甚至不需要第二次来巩固记忆。

## 小结

ID 生成方案没有绝对最优，只有适合当前系统的取舍。小系统用自增，简单可靠；分布式高并发用 Snowflake 或号段模式；日志追踪用 UUID。真正需要警惕的是在不理解约束的情况下复制一段发号代码，然后把唯一性寄托给运气。
