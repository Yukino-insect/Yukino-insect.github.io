+++
date = '2025-10-02T22:02:47+08:00'
draft = false
title = 'ID 生成方案'
+++

单机生成唯一 id，实现简单，生成 id 的性能高。但是当需要在多台机器上生成唯一 id，单机生成 id 的算法可能就不能保证 id 的唯一性。这时就需要其他的算法，以满足对 id 的需求。

分布式 id 生成算法一般需要满足多节点并发生成算法时，id **不会重复**。要有**高可用性**，不能只依赖多节点，否则如果生成 id 的服务挂掉了，整个分布式系统就瘫痪了。**生成 Id 的速度要快**，不能让其成为系统的瓶颈。一般来说，希望 **id 大体上是递增的**，因为，有序的 id 可以提高 MySQL 的索引效率。

现在介绍一下常见的 id 生成算法的使用

### UUID

它会随机生成一个 128 位字符串，通常表示为 32 个十六进制字符 + 4 个 `-`，一共 36 个字符。理论上保证全局唯一。

它有多个版本。主流是使用 v1、v3、v4 和 v5

**v1**：基于时间戳 + MAC，唯一性好，但可能泄露信息

**v3/v5**：基于 namespace + hash，确定性 UUID（相同输入必然相同输出）

**v4**：基于随机数，最常用，Java 默认实现

```java
String uuid = UUID.randomUUID().toString();
System.out.println(uuid); 
// e.g. "550e8400-e29b-41d4-a716-446655440000"
```

它生成的 id 长度长且无序，这样会致使数据库索引性能变差

### Redis 自增

利用 Redis 的原子自增操作，保证分布式唯一

```bash
INCR order_id
```

```java
Jedis jedis = new Jedis("localhost", 6379);
long id = jedis.incr("order_id");
System.out.println(id); // 1, 2, 3...
```

它的实现简单，但是严重依赖 Redis 的高可用

### Snowflake 雪花算法

它是一个 64 位 long 数，拼接时间戳、机器号、序列号，保证趋势递增

```bash
# 结构
0 | timestamp(41) | machineId(10) | sequence(12)
```

第一部分是符号位，一般来说是 0，因为 id 是正数。第二部分是时间戳，第三部分是机器号，第四部分是序列号

简单实现

```java
/**
 * 雪花算法（Snowflake）实现类
 *
 * 生成 64 位全局唯一 ID，结构如下：
 * 0 | 时间戳（41位） | 数据中心ID（5位） | 机器ID（5位） | 序列号（12位）
 *
 * 特点：
 * 1. 高性能（本地生成，无需依赖数据库）
 * 2. 按时间大体有序
 * 3. 保证分布式环境下的唯一性
 *
 * 存在的问题：
 * - 时钟回拨会导致生成重复ID
 * - 同一毫秒内超过4096个请求会阻塞等待下一毫秒
 */
public class SnowflakeIdWorker {
    /** 机器ID（0~31） */
    private long workerId;

    /** 数据中心ID（0~31） */
    private long datacenterId;

    /** 当前毫秒内的序列号（0~4095） */
    private long sequence = 0L;

    /** 起始时间戳（可自定义，用于缩小时间戳占用空间，Twitter默认2010-11-04） */
    private long twepoch = 1288834974657L;

    /** 机器ID所占位数 */
    private long workerIdBits = 5L;

    /** 数据中心ID所占位数 */
    private long datacenterIdBits = 5L;

    /** 序列号占用位数 */
    private long sequenceBits = 12L;

    /** 最大机器ID值（31） */
    private long maxWorkerId = -1L ^ (-1L << workerIdBits);

    /** 最大数据中心ID值（31） */
    private long maxDatacenterId = -1L ^ (-1L << datacenterIdBits);

    /** 机器ID向左偏移量（12位） */
    private long workerIdShift = sequenceBits;

    /** 数据中心ID向左偏移量（12+5=17位） */
    private long datacenterIdShift = sequenceBits + workerIdBits;

    /** 时间戳向左偏移量（12+5+5=22位） */
    private long timestampLeftShift = sequenceBits + workerIdBits + datacenterIdBits;

    /** 序列号掩码（4095），用于与运算取余 */
    private long sequenceMask = -1L ^ (-1L << sequenceBits);

    /** 上次生成ID的时间戳 */
    private long lastTimestamp = -1L;

    /**
     * 构造函数
     * @param workerId     机器ID（0~31）
     * @param datacenterId 数据中心ID（0~31）
     */
    public SnowflakeIdWorker(long workerId, long datacenterId) {
        this.workerId = workerId;
        this.datacenterId = datacenterId;
    }

    /**
     * 生成下一个唯一ID（线程安全）
     *
     * @return 唯一的 64 位 ID
     */
    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();

        // 1. 如果当前时间小于上一次ID生成的时间，说明发生了时钟回拨
        if (timestamp < lastTimestamp) {
            throw new RuntimeException("Clock moved backwards.");
        }

        // 2. 如果在同一毫秒内，则对序列号自增
        if (lastTimestamp == timestamp) {
            sequence = (sequence + 1) & sequenceMask;
            // 序列号溢出，阻塞到下一毫秒
            if (sequence == 0) {
                while ((timestamp = System.currentTimeMillis()) <= lastTimestamp) {
                }
            }
        } else {
            // 3. 时间戳改变，序列号重置为0
            sequence = 0L;
        }

        // 记录上一次的时间戳
        lastTimestamp = timestamp;

        // 4. 组装ID
        return ((timestamp - twepoch) << timestampLeftShift)   // 时间戳部分
                | (datacenterId << datacenterIdShift)          // 数据中心部分
                | (workerId << workerIdShift)                  // 机器部分
                | sequence;                                    // 序列号部分
    }
}

```

雪花算法常见的问题就是时钟回拨，**Leaf** 提供了一种雪花算法的实现，解决了时钟回拨的问题

### Leaf-snowflake

 和原版 Snowflake 类似，Leaf-snowflake 也是 64 位 ID：

```bash
0 | timestamp(41位) | machineId(10位) | sequence(12位)
```

- **0**：最高位始终为 0，保证正数
- **timestamp**：当前时间戳（毫秒），减去一个固定的开始时间（epoch）
- **machineId**：机器号（Leaf 用 ZooKeeper 来分配，保证全局唯一）
- **sequence**：同一毫秒内的自增序列（0~4095）

##### 和原始 Snowflake 的区别

1. **机器 ID 分配**
   - 原版 Snowflake 要手动配置 workerId/datacenterId，很容易冲突
   - Leaf-snowflake 用 **ZooKeeper 持久顺序节点** 来动态分配机器 ID，避免了人工分配冲突问题
2. **时钟回拨问题处理**
   - 原版 Snowflake 一旦时钟回拨，ID 就可能重复
   - Leaf-snowflake 会检测回拨，如果回拨时间很短（比如 < 5ms），会进行等待；
   - 如果回拨时间较长，会直接抛异常或报警，避免生成错误 ID
3. **高可用**
   - Leaf-snowflake 支持 **多节点部署**，机器 ID 由 ZK 管理，挂掉一个节点不会影响整体服务

使用场景

- 和 **Leaf-segment（号段模式）** 相比，Snowflake 更适合 **实时性要求高** 的业务：
  - 比如日志 ID、链路追踪 ID、消息队列的消息 ID
- 但是由于依赖系统时钟，**对时间敏感**，在运维环境中要格外注意 **NTP 时间同步**。

### Leaf-segment（号段模式）

它的核心思想是每次会把一大段 ID 提前申请下来，缓存到内存里，本地自增使用。当用完之后会申请下一段。这样就不需要每次生成 ID 都访问数据库，缓解了数据库的压力，同时，ID 在本地的自增效率又很快。支持分布式

Leaf 使用一张 `leaf_alloc` 表来管理不同业务的 ID 号段

```sql
CREATE TABLE leaf_alloc (
  biz_tag     VARCHAR(128) NOT NULL PRIMARY KEY COMMENT '业务 key，如订单、用户',
  max_id      BIGINT NOT NULL COMMENT '当前最大 id',
  step        INT NOT NULL COMMENT '号段长度，每次申请多少个 id',
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
```

如 

```bash
biz_tag | max_id | step | update_time
--------|--------|------|-----------------
order   | 10000  | 1000 | 2025-10-02 12:00:00
user    | 5000   | 500  | 2025-10-02 12:00:00
```

现在以 `order` 业务为例，介绍一下 ID 生成流程，step=1000：

1. **应用请求一个号段**
   - 更新表里的 `max_id = max_id + step`
   - 返回 `[old_max_id+1, new_max_id]` 这一段给应用
   - 比如之前 max_id=10000，更新后=11000，返回 [10001,11000]
2. **应用在本地缓存号段**
   - 内存里保存当前号段范围和游标
   - 每次请求 ID，就从内存里 `+1`
3. **号段快用完时异步申请**
   - 当本地号段消耗到 90%（阈值可调），提前去 DB 申请新的号段
   - 确保切换号段时不会中断
4. **新旧号段平滑切换**
   - 旧号段用完后，直接切到新号段继续用

id 申请下来之后，进行本地自增操作，单机 QPS 可达 5w+，远高于每次访问数据库的自增模式。只有每次申请新号段时才会访问数据库，减小了数据库的压力。容灾性也不错，即使数据库挂掉了，也可以继续使用内存中当前号段的 ID。通过数据库控制号段不重叠，保证分布式唯一。

但是它**不保证 id 连续**，有时候可能有跳号，比如一个节点申请了号段，但没用完就挂了 -> 剩余 ID 会浪费。但大多数业务（订单号、用户ID）能接受。

**依赖数据库**，需要一个高可用数据库来做号段分配。

简单实现

```java
public class Segment {
    private long currentId;   // 当前 ID
    private long maxId;       // 当前号段最大值
    private int step;         // 步长

    public Segment(long currentId, long maxId, int step) {
        this.currentId = currentId;
        this.maxId = maxId;
        this.step = step;
    }

    public synchronized long nextId() {
        if (currentId < maxId) {
            return ++currentId;
        } else {
            throw new RuntimeException("号段已用完，需要申请新的");
        }
    }
}
```

### 在 Spring Boot 项目中集成 Leaf

### 引入依赖

```xml
<dependency>
    <groupId>com.sankuai.inf.leaf</groupId>
    <artifactId>leaf-server</artifactId>
    <version>1.0.0</version>
</dependency>
<dependency>
    <groupId>com.sankuai.inf.leaf</groupId>
    <artifactId>leaf-core</artifactId>
    <version>1.0.0</version>
</dependency>
```

### 选择模式

#### 号段模式

在数据库创建 `leaf_alloc` 表

```sql
CREATE TABLE leaf_alloc (
  biz_tag     VARCHAR(128) NOT NULL PRIMARY KEY COMMENT '业务key，如order、user',
  max_id      BIGINT NOT NULL COMMENT '当前最大id',
  step        INT NOT NULL COMMENT '号段步长',
  update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

在资源目录下配置 `leaf.properties`

```properties
leaf.segment.enable=true
leaf.jdbc.url=jdbc:mysql://127.0.0.1:3306/leaf?useSSL=false
leaf.jdbc.username=root
leaf.jdbc.password=123456
```

#### 雪花模式

依赖 ZooKeeper

配置 `leaf.properties`

```properties
leaf.snowflake.enable=true
leaf.snowflake.zk.address=127.0.0.1:2181
leaf.snowflake.port=8080   # 当前服务端口
```

Leaf 会在 ZK 上注册临时顺序节点，用于 workerId 分配。

### 启动 Leaf 服务

```java
@SpringBootApplication
public class LeafApplication {
    public static void main(String[] args) {
        SpringApplication.run(LeafApplication.class, args);
    }
}
```

当启动 程序后，Leaf 本身会启动一个 **HTTP 接口**，可以通过 HTTP 请求获取 ID

#### 号段模式

```
http://localhost:8080/api/segment/get/ORDER
```

返回：

```
{"status":"SUCCESS","id":10001,"bizTag":"ORDER"}
```

#### 雪花模式

```
http://localhost:8080/api/snowflake/get/test
```

返回：

```
{"status":"SUCCESS","id":657933783557709824}
```

**但一般会选择在项目中直接调用**

在项目中注入 `IDGen`

```java
@Autowired
@Qualifier("segmentIDGen")  // 或者 "snowflakeIDGen"
private IDGen idGen;

// 使用
public Long getOrderId() {
    Result result = idGen.get("ORDER");
    if (result.getStatus() == Status.SUCCESS) {
        return result.getId();
    }
    throw new RuntimeException("获取ID失败");
}
```

- `IDGen` 是 **Leaf 提供的 ID 生成接口**

- Leaf 有两种实现：

  - `SegmentIDGen` -> 号段模式（基于数据库号段表）
  - `SnowflakeIDGen` -> 雪花模式（基于 ZooKeeper 分配 workerId）

- 在 Spring Boot 项目中，通过 `@Autowired` 注入其中之一：

  ```java
  @Autowired
  @Qualifier("segmentIDGen")  // 或 "snowflakeIDGen"
  private IDGen idGen;
  ```

 `idGen.get("ORDER")`  会调用 Leaf 生成一个唯一 ID，`"ORDER"` 是业务标识（bizTag）

- 号段模式下，它对应 `leaf_alloc` 表的 `biz_tag` 字段
- 雪花模式下，它主要用作区分不同业务请求

比如你在数据库表里有这样一行数据：

```bash
biz_tag = "ORDER", max_id = 10000, step = 1000
```

那么：

- 第一次调用会返回 ID = 10001
- 下一次调用 = 10002
- 一直自增，直到号段用完，才去数据库申请新的号段

Leaf 的 `Result` 对象通常包含：

```java
public class Result {
    private long id;        // 生成的ID
    private Status status;  // 生成状态（SUCCESS、EXCEPTION等）
    private String msg;     // 错误信息（如果有的话）
}
```

使用时要判断状态：

```java
Result result = idGen.get("ORDER");
if (result.getStatus() == Status.SUCCESS) {
    Long orderId = result.getId();
    System.out.println("生成订单号: " + orderId);
} else {
    throw new RuntimeException("获取ID失败: " + result.getMsg());
}
```
