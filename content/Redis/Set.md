+++
date = '2025-12-31T21:50:44+08:00'
draft = false
title = 'Redis Set'
+++

Redis Set 是无序且元素唯一的集合结构，常用于去重、标签、权限、关注关系、抽奖、共同好友等场景。

它最值得记住的能力有两个：一是成员判断快，二是集合运算方便。至于它是不是适合承载某个业务模型，要看数据规模、访问模式和是否会形成大 key。

## 一、基本命令

```bash
SADD tag:redis article:1 article:2 article:3
SREM tag:redis article:2
SISMEMBER tag:redis article:1
SCARD tag:redis
SMEMBERS tag:redis
```

集合运算：

```bash
# 交集：共同关注、共同标签
SINTER user:1001:following user:1002:following

# 并集：多个角色的用户集合
SUNION role:admin:users role:editor:users

# 差集：我关注但你没关注的人
SDIFF user:1001:following user:1002:following
```

随机成员：

```bash
SRANDMEMBER lottery:2025 10
SPOP lottery:2025 1
```

`SRANDMEMBER` 只随机返回成员，不会删除；`SPOP` 会随机弹出并删除成员，适合抽奖后不允许重复中奖的场景。

## 二、底层结构

Redis Set 的底层编码会根据元素类型和数量变化。

在较早和常见的实现中，Set 主要有两类编码：

1. `intset`：元素都是整数且数量较少时使用，内存更紧凑。
2. `hashtable`：元素数量变多或出现普通字符串时使用，成员查询、插入、删除平均复杂度为 `O(1)`。

在 Redis 7.2 及之后的版本中，小 Set 还可以使用 listpack 相关编码来进一步节省内存，配置项包括 `set-max-listpack-entries` 和 `set-max-listpack-value`。

不管内部编码如何变化，对使用者来说，Set 的核心语义都是：无序、唯一、支持集合运算。

## 三、适合的业务场景

### 1. 去重

例如记录某篇文章被哪些用户阅读过：

```bash
SADD article:9527:read_users user:1001
SADD article:9527:read_users user:1002
SCARD article:9527:read_users
```

如果只需要估算 UV，而不要求精确值，可以考虑 HyperLogLog；如果需要精确用户列表，Set 更合适。

### 2. 标签系统

可以用一个 Set 表示某个标签下的对象：

```bash
SADD tag:redis article:1 article:2
SADD tag:cache article:2 article:3
SINTER tag:redis tag:cache
```

这类模型适合做简单筛选。若标签维度很多、查询条件复杂，应该考虑搜索引擎或倒排索引系统。

### 3. 关注关系

```text
following:{userId} -> 该用户关注的人
followers:{userId} -> 关注该用户的人
```

判断是否关注：

```bash
SISMEMBER following:1001 2002
```

求共同关注：

```bash
SINTER following:1001 following:1002
```

Set 很适合中小规模关系链，但不能把“能做”理解成“无限做”。如果某个用户有上千万甚至上亿粉丝，单个 Set 就会变成典型大 key。

## 四、大 Set 的问题

大 Set 常见问题包括：

1. 内存占用随成员数量线性增长。
2. rehash、迁移、删除、持久化可能带来明显开销。
3. `SMEMBERS`、`SINTER` 等命令在大集合上可能阻塞主线程。
4. Cluster 模式下，一个 key 只能落在一个 slot，单个大 key 难以水平拆分。
5. 热点 Set 容易集中打到单个 Redis 节点。

因此，生产环境应避免直接对大 Set 使用 `SMEMBERS`、`SUNION`、`SINTER` 这类可能返回大量数据的命令。需要遍历时优先使用 `SSCAN`。

```bash
SSCAN followers:1001 0 COUNT 100
```

`SSCAN` 是渐进式遍历，不能保证一次返回固定数量，也不能完全避免遍历期间的数据变化影响结果，但它比一次性拉完整集合更适合线上场景。

## 五、Set 与 Bitmap 的取舍

Bitmap 适合表示“某个整数偏移量是否存在”，例如签到、活跃状态、是否完成任务。

Set 适合表示“成员集合”，尤其是成员不是连续整数，或者需要取出成员列表、做集合运算的时候。

对比：

| 维度 | Set | Bitmap |
| --- | --- | --- |
| 数据语义 | 成员集合 | 二值状态 |
| 成员类型 | 字符串 | 整数 offset |
| 是否能列出成员 | 可以 | 不适合 |
| 稀疏数据 | 相对合适 | 可能浪费空间 |
| 成员判断 | 快 | 很快 |
| 集合运算 | 支持 | 支持位运算 |

关注关系通常是二维关系：用户 A 是否关注用户 B。直接用 Bitmap 表示所有关系，往往会遇到空间巨大、ID 稀疏、映射维护复杂等问题。除非业务 ID 已经过压缩映射，并且关系模型非常适合位图，否则不要轻易用 Bitmap 替代 Set。

## 六、实践建议

使用 Set 时可以按以下规则判断：

1. 中小规模集合可以直接使用 Set。
2. 成员判断、去重、简单集合运算优先考虑 Set。
3. 大规模关系链要考虑分片、冷热分离和数据库兜底。
4. 热点用户、热点标签不要只靠单个 Redis key 承载。
5. 精确关系保存在数据库中，Redis 缓存热点查询结果。
6. 计数类需求可以单独维护计数字段，不要每次都遍历集合计算。
7. 删除大 Set 时避免直接 `DEL`，可以使用 `UNLINK` 异步释放内存。

总结来说，Redis Set 是很好用的集合工具，但它不是关系数据库，也不是图数据库。规模小的时候命令很漂亮；规模上来以后，数据模型才是真正的主角。

## 参考资料

- Redis Set 官方文档：<https://redis.io/docs/latest/develop/data-types/sets/>
- Redis 内存优化：<https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/>
