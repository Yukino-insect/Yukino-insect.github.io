+++
date = '2025-09-07T15:07:56+08:00'
draft = false
title = 'Redis 高可用'
+++

Redis 高可用的目标不是“永远不出问题”，而是在节点故障、进程重启、网络抖动时，尽量减少不可用时间和数据丢失窗口。

要理解 Redis 高可用，需要把四件事分开看：

1. 持久化：进程重启后能否恢复数据。
2. 主从复制：数据能否有副本。
3. Sentinel：主节点故障后能否自动切换。
4. Cluster：数据能否分片扩展，并具备分片级故障转移。

## 一、持久化

Redis 数据主要在内存中。如果没有持久化，进程退出后数据就会丢失。

Redis 常见持久化方式有三种。

### 1. RDB

RDB 是快照持久化，会在某个时间点把内存数据保存成紧凑的二进制文件。

优点：

1. 文件紧凑，适合备份。
2. 恢复速度通常较快。
3. 对主进程运行时性能影响相对较小。

缺点：

1. 两次快照之间的数据可能丢失。
2. 数据量大时，`fork` 和写快照会带来 CPU、内存和磁盘压力。

示例配置：

```conf
save 900 1
save 300 10
save 60 10000
dbfilename dump.rdb
dir /data/redis
```

### 2. AOF

AOF 会记录 Redis 接收到的写命令，重启时通过重放命令恢复数据。

常见刷盘策略：

```conf
appendonly yes
appendfsync everysec
```

`appendfsync` 常见值：

1. `always`：每次写命令都刷盘，数据更安全，但性能成本高。
2. `everysec`：每秒刷盘一次，通常是性能和安全性的折中。
3. `no`：交给操作系统决定刷盘时机，性能好但数据丢失窗口更大。

优点：

1. 数据丢失窗口通常小于 RDB。
2. 文件记录的是命令，便于理解恢复过程。

缺点：

1. 文件通常比 RDB 大。
2. 重写和恢复可能消耗更多时间。
3. 写入路径上有额外 I/O 成本。

### 3. RDB + AOF 混合持久化

Redis 4.0 之后支持混合持久化。AOF 重写后的文件前半部分是 RDB 格式，后半部分追加增量 AOF 命令。

```conf
appendonly yes
aof-use-rdb-preamble yes
```

它兼顾了 RDB 恢复速度和 AOF 较小数据丢失窗口，是生产环境常见选择。

## 二、单节点、主从、Sentinel、Cluster 怎么选

| 模式 | 能力 | 风险 | 适合场景 |
| --- | --- | --- | --- |
| 单节点 | 部署简单，读写都在一个实例 | 单点故障，容量受限 | 本地开发、小型非核心缓存 |
| 主从复制 | 有副本，可读扩展 | 主节点故障需要人工处理或额外机制 | 读多写少、需要副本 |
| Sentinel | 主从基础上自动故障转移 | 不分片，容量仍受单主限制 | 中小规模生产高可用 |
| Cluster | 分片、自动故障转移、水平扩展 | 运维和客户端复杂度更高 | 大规模缓存或高吞吐场景 |

简单判断：

1. 只是开发测试，用单节点。
2. 需要读扩展但能接受人工切换，用主从。
3. 需要自动故障转移但数据量不大，用 Sentinel。
4. 需要水平扩展和分片，用 Cluster。

## 三、主从复制

Redis 主从复制用于把主节点的数据同步到从节点。它的目标是提供读扩展、数据副本和故障切换基础，而不是提供严格强一致。

### 1. 基本配置

主节点：

```conf
port 6379
appendonly yes
aof-use-rdb-preamble yes
```

从节点：

```conf
port 6380
replicaof 127.0.0.1 6379

# 如果主节点设置了密码
masterauth yourpassword
```

也可以运行时执行：

```bash
REPLICAOF 127.0.0.1 6379
```

让从节点脱离主节点，提升为主节点：

```bash
REPLICAOF NO ONE
```

从节点默认只读，由 `replica-read-only yes` 控制。生产环境不要随意开启从节点写入，否则容易造成数据不一致。

### 2. 全量同步

全量同步通常发生在：

1. 从节点第一次连接主节点。
2. 从节点断线太久，无法继续增量同步。
3. 主节点复制积压缓冲区中缺失的历史命令已被覆盖。

过程大致是：

```text
从节点请求同步
  -> 主节点生成 RDB 快照
  -> 主节点把 RDB 发送给从节点
  -> 从节点加载 RDB
  -> 主节点继续发送快照期间产生的写命令
```

全量同步会消耗磁盘、网络、CPU 和内存，生产环境要关注它发生的频率。

### 3. 增量同步

增量同步发生在从节点短暂断线后重新连接，并且主节点仍保留它缺失的那部分复制日志时。

它依赖三个概念：

1. 复制 ID：标识一段复制历史。
2. 复制偏移量：记录主从同步进度。
3. 复制积压缓冲区：主节点保存最近写命令的环形缓冲区。

如果从节点带来的复制 ID 能匹配，并且缺失的 offset 仍在 backlog 中，就可以只补缺失命令；否则只能全量同步。

### 4. 主从复制不是强一致

Redis 主从复制默认是异步的。主节点写入成功后，不会等待所有从节点确认才返回客户端。

因此可能出现：

```text
客户端写入 master 成功
  -> replica 还没同步完成
  -> 客户端读 replica
  -> 读到旧值
```

如果业务不能接受旧数据：

1. 强一致读走主节点。
2. 从节点只承载允许短暂延迟的查询。
3. 监控主从延迟，延迟过大时摘除从库读流量。
4. 写入后使用 `WAIT` 提高写命令被副本确认的概率。

示例：

```bash
SET order:1001 paid
WAIT 1 1000
```

`WAIT 1 1000` 表示等待至少 1 个从节点在 1000 毫秒内确认之前的写命令。它能提高数据安全性，但不等于把 Redis 变成强一致分布式数据库。

## 四、Sentinel

Sentinel 用来解决普通主从模式下“主节点故障需要人工切换”的问题。

Sentinel 的职责包括：

1. 监控主节点和从节点。
2. 判断主节点是否下线。
3. 在主节点故障时选举新的主节点。
4. 通知客户端新的主节点地址。

### 1. 基本拓扑

典型结构：

```text
Redis master:  127.0.0.1:6379
Redis replica: 127.0.0.1:6380
Redis replica: 127.0.0.1:6381

Sentinel: 26379
Sentinel: 26380
Sentinel: 26381
```

Sentinel 本身也要部署多个实例。只部署一个 Sentinel，仍然会有单点问题。

### 2. Sentinel 配置

```conf
port 26379

sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1

# 如果主节点有密码
# sentinel auth-pass mymaster yourpassword
```

启动：

```bash
redis-sentinel sentinel-26379.conf
redis-sentinel sentinel-26380.conf
redis-sentinel sentinel-26381.conf
```

查看：

```bash
redis-cli -p 26379 INFO sentinel
```

### 3. 主观下线和客观下线

Sentinel 判断故障分两步：

1. 主观下线：某个 Sentinel 认为 master 不可达。
2. 客观下线：达到 quorum 数量的 Sentinel 都认为 master 不可达。

达到客观下线后，Sentinel 才会发起故障转移，选出一个从节点提升为新的主节点。

### 4. Sentinel 的一致性风险

Sentinel 能提高可用性，但它不能消除异步复制带来的数据丢失窗口。

可能发生：

```text
master 写入成功
  -> 写命令尚未复制到 replica
  -> master 宕机
  -> replica 被提升为新 master
  -> 刚才的写入丢失
```

因此 Sentinel 解决的是自动故障转移，不是强一致复制。

## 五、Redis Cluster

Redis Cluster 是 Redis 的分片集群方案。它把数据分布到多个主节点上，每个主节点可以有自己的从节点。

Cluster 的核心概念是 hash slot。Redis Cluster 一共有 16384 个 slot，每个 key 根据哈希结果映射到某个 slot，slot 再归属到具体节点。

### 1. 本机模拟 3 主 3 从

端口：

```text
7000 7001 7002 7003 7004 7005
```

单个节点配置示例：

```conf
port 7000
cluster-enabled yes
cluster-config-file nodes-7000.conf
cluster-node-timeout 5000
appendonly yes
daemonize yes
bind 127.0.0.1
```

启动 6 个实例后创建集群：

```bash
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1
```

连接：

```bash
redis-cli -c -p 7000
```

查看：

```bash
CLUSTER NODES
CLUSTER INFO
```

### 2. Cluster 的限制

Redis Cluster 不是“单机 Redis 自动变无限大”。它有一些必须理解的限制：

1. 多 key 操作要求 key 在同一个 slot，否则会报跨 slot 错误。
2. 可以使用 hash tag 控制多个 key 落到同一 slot，例如 `order:{1001}:items`。
3. Cluster 只支持数据库 0，不支持 `SELECT` 切换多个数据库。
4. 主从复制仍然是异步的，故障时仍可能丢失少量已确认写入。
5. 客户端必须支持 Cluster 协议和 MOVED/ASK 重定向。

## 六、客户端配置示例

下面示例以 Spring Boot 为主。不同 Spring Boot 版本中配置前缀可能是 `spring.redis` 或 `spring.data.redis`，实际项目应以当前版本文档和 IDE 配置提示为准。

### 1. 单节点

```yaml
spring:
  data:
    redis:
      host: 127.0.0.1
      port: 6379
      password: yourpassword
```

### 2. Sentinel

```yaml
spring:
  data:
    redis:
      sentinel:
        master: mymaster
        nodes:
          - 127.0.0.1:26379
          - 127.0.0.1:26380
          - 127.0.0.1:26381
      password: yourpassword
```

### 3. Cluster

```yaml
spring:
  data:
    redis:
      cluster:
        nodes:
          - 127.0.0.1:7000
          - 127.0.0.1:7001
          - 127.0.0.1:7002
        max-redirects: 3
      password: yourpassword
```

Jedis Cluster 示例：

```java
Set<HostAndPort> nodes = new HashSet<>();
nodes.add(new HostAndPort("127.0.0.1", 7000));
nodes.add(new HostAndPort("127.0.0.1", 7001));
nodes.add(new HostAndPort("127.0.0.1", 7002));

try (JedisCluster cluster = new JedisCluster(nodes)) {
    cluster.set("key", "value");
    String value = cluster.get("key");
}
```

Lettuce Cluster 示例：

```java
RedisClusterClient client = RedisClusterClient.create(List.of(
    RedisURI.create("redis://127.0.0.1:7000"),
    RedisURI.create("redis://127.0.0.1:7001"),
    RedisURI.create("redis://127.0.0.1:7002")
));

try (StatefulRedisClusterConnection<String, String> connection = client.connect()) {
    connection.sync().set("key", "value");
    String value = connection.sync().get("key");
}
```

## 七、读写实时性

如果业务要求“刚写完立刻必须读到最新值”，不同模式的表现如下：

| 模式 | 实时性风险 | 建议 |
| --- | --- | --- |
| 单节点 | 读写同实例，通常没有复制延迟 | 风险主要是单点故障 |
| 主从 | 读从节点可能读到旧值 | 强一致读走主节点 |
| Sentinel | failover 期间可能读旧值或丢少量写入 | 客户端正确感知 master，关键读走主 |
| Cluster | 从节点读可能旧，跨 slot 操作受限 | 默认读 master，谨慎开启读从 |

读写分离不是免费的。它提升读能力的同时，也引入复制延迟。对订单状态、支付状态、库存结果这类敏感数据，应谨慎读从节点。

## 八、生产环境检查清单

上线前至少检查：

1. 是否设置 `maxmemory` 和合理淘汰策略。
2. 是否开启合适的持久化策略。
3. 是否监控主从复制延迟。
4. 是否监控全量同步次数。
5. 是否避免大 key 和热 key。
6. 是否配置认证、网络隔离和最小权限。
7. Sentinel 或 Cluster 是否至少具备多数派可用性。
8. 客户端是否配置连接池、超时、重试和故障切换。
9. 是否有备份和恢复演练。
10. 是否明确哪些数据允许丢失，哪些数据必须落数据库。

总结来说，Redis 高可用不是某一个配置项，而是一组取舍：持久化降低重启丢失，复制提供副本，Sentinel 提供自动切换，Cluster 提供分片扩展。真正稳妥的设计，是先承认 Redis 的异步复制边界，再把业务一致性要求放到合适的位置。

## 参考资料

- Redis 持久化官方文档：<https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/>
- Redis 主从复制官方文档：<https://redis.io/docs/latest/operate/oss_and_stack/management/replication/>
- Redis Sentinel 官方文档：<https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/>
- Redis Cluster 规范：<https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/>
- Redis WAIT 命令：<https://redis.io/docs/latest/commands/wait/>
