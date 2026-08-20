+++
date = '2025-10-07T18:42:03+08:00'
draft = false
title = 'Canal'
+++

### Canal 是什么

**Canal** 是阿里巴巴开源的 **基于数据库 binlog 的增量订阅 & 消费组件**。

最早是为了解决 **MySQL 和 HBase/ES 的数据同步**问题。

它会监听 MySQL 的 **binlog** 日志，把数据库的增删改操作实时解析出来，推送给其他系统。

### Canal 的工作原理

**模拟 MySQL 从库（Slave）**

>  MySQL 主从复制的原理：主库写 binlog，从库通过 **dump 协议** 拉取 binlog。

Canal 伪装成 MySQL 的一个从库，**订阅 binlog**。拿到 binlog 日志后，**解析**出行级别的变更信息（insert/update/delete）。

然后，Canal 把解析后的数据以事件（event）的形式**投递到下游系统**：

- Kafka / RocketMQ
- ElasticSearch
- HBase / ClickHouse
- 业务自定义消费者

### Canal 的应用场景

1. **数据库同步**
   - MySQL 到 MySQL（跨机房、跨库实时同步）
   - MySQL 到 Oracle / PostgreSQL / ClickHouse
2. **数据库与搜索引擎同步**
   - MySQL 到 ElasticSearch（做搜索系统时，数据实时更新到 ES）
3. **数据库与缓存同步**
   - MySQL 到 Redis（缓存预热、更新保持实时一致）
4. **审计与监控**
   - 监听敏感表的变更，实时触发告警。

### Canal 的架构

```markdown
          ┌─────────────┐
          │   MySQL主库  │
          └──────┬──────┘
                 │ binlog
                 ▼
          ┌─────────────┐
          │   Canal     │  (伪装成Slave)
          ├─────────────┤
          │ binlog解析器 │
          │ 数据存储队列 │
          │ 消费者适配器 │
          └──────┬──────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  ElasticSearch  Kafka     Redis/HBase
```

组件说明：

- **Canal Server**：核心服务，负责连接 MySQL、拉取并解析 binlog。
- **Canal Instance**：一个数据订阅通道（对应一个数据库实例）。
- **Canal Client**：消费 Canal 解析后的数据。

### Canal 的部署和使用

#### 部署

下载 canal，解压后修改配置：

```properties
# conf/example/instance.properties
canal.instance.master.address=127.0.0.1:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal
```

需要在 MySQL 中创建一个账号，授予 **REPLICATION SLAVE** 权限：

```sql
CREATE USER 'canal'@'%' IDENTIFIED BY 'canal';
GRANT SELECT, REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'canal'@'%';
```

#### 启动

```bash
sh bin/startup.sh
```

#### 消费数据

- 方式1：Java 客户端 API（直接拉取 binlog 事件）。
- 方式2：Kafka/RocketMQ 适配器（自动把数据投递到消息队列）。
- 方式3：Elasticsearch 适配器（直接同步到 ES）。

### 典型实战案例

1. **MySQL -> Elasticsearch**

   业务数据库写入/更新商品信息

   Canal 监听 binlog，把变化推送到 ES

   搜索引擎里的商品数据保持实时一致

2. **MySQL -> Redis 缓存**

   用户修改资料 -> 写入数据库

   Canal 捕获 binlog -> 更新 Redis 中的缓存

   避免出现缓存与数据库不一致问题

3. **MySQL -> Kafka -> Flink -> 数据仓库**

   电商订单表的 binlog 通过 Canal 投递到 Kafka

   Flink 做实时计算（GMV、UV）

   汇总写入 HDFS/ClickHouse

> **多实例配置**
>
> Canal 中的 **一个 Instance 就是一个独立的数据订阅通道**，对应一个数据库的 binlog 拉取配置。一个 Canal Server 可以管理多个 Instance。每个 Instance 有独立的配置文件（`instance.properties`），互不干扰。
>
> 可以理解为 **一个数据库 = 一个 instance**。
>
> ##### 多实例的配置方式
>
> 实例目录结构
>
> 在 `canal/conf/` 目录下，默认有一个示例 instance：
>
> ```markdown
> conf/
>  ├── canal.properties        # 全局配置
>  └── example/                # 默认的 instance
>       └── instance.properties
> ```
>
> 如果要添加多个实例，就新增多个目录：
>
> ```markdown
> conf/
>  ├── canal.properties
>  ├── example/
>  │    └── instance.properties
>  ├── userdb/
>  │    └── instance.properties
>  └── orderdb/
>       └── instance.properties
> ```
>
> 以 `userdb/instance.properties` 为例：
>
> ```properties
> # 指定要监听的MySQL
> canal.instance.master.address=127.0.0.1:3306
> canal.instance.dbUsername=canal
> canal.instance.dbPassword=canal
> 
> # 指定要监听的数据库/表
> canal.instance.filter.regex=userdb\\..*
> ```
>
> 再比如 `orderdb/instance.properties`：
>
> ```properties
> canal.instance.master.address=192.168.10.21:3306
> canal.instance.dbUsername=canal
> canal.instance.dbPassword=canal
> 
> # 只监听订单表
> canal.instance.filter.regex=orderdb\\.t_order
> ```
>
> 启动多实例
>
> 在 `canal.properties` 中配置要加载的实例：
>
> ```
> canal.destinations=example,userdb,orderdb
> ```
>
> 启动 Canal 后，它会同时运行这些实例，每个实例独立去拉取对应 MySQL 的 binlog。

### 在 Spring 中集成 Canal

#### 引入依赖

```xml
<dependency>
    <groupId>com.alibaba.otter</groupId>
    <artifactId>canal.client</artifactId>
    <version>1.1.7</version> <!-- 与Canal服务端版本匹配 -->
</dependency>
```

>  Canal 服务端和客户端的版本必须兼容
>
> 一定要启动 Canal 服务器

Java 实现

```java
/**
 * Canal 客户端示例
 * 作用：连接 Canal Server，实时拉取 MySQL binlog 并处理数据
 */
@Component
public class CanalClient implements InitializingBean, DisposableBean {

    /** Canal 连接器，用于与 Canal Server 建立连接 */
    private CanalConnector connector;

    /**
     * Bean 初始化时执行，相当于 @PostConstruct
     * 用于初始化 Canal 连接器，并开启监听线程
     */
    @Override
    public void afterPropertiesSet() {
        // 1. 创建连接器，连接到 Canal Server
        connector = CanalConnectors.newSingleConnector(
                new InetSocketAddress("127.0.0.1", 11111), // Canal Server 地址和端口
                "example", // instance 名称，对应 canal/conf/example
                "canal",   // 用户名（默认空）
                "canal");  // 密码（默认空）

        // 2. 启动独立线程持续监听 Binlog 事件
        new Thread(this::listen).start();
    }

    /**
     * 持续监听 MySQL Binlog 数据
     */
    private void listen() {
        connector.connect(); // 建立连接
        connector.subscribe("mydb\\..*"); // 订阅 mydb 库下的所有表（正则匹配）
        connector.rollback(); // 回滚到未确认的地方，避免丢失

        // 无限循环监听
        while (true) {
            // 批量获取数据，每次最多 100 条
            Message message = connector.getWithoutAck(100);
            long batchId = message.getId();

            if (batchId != -1 && !message.getEntries().isEmpty()) {
                // 有数据才处理
                handleMessage(message);
            }

            // 确认消息，告诉 Canal Server 已经成功消费
            connector.ack(batchId);
        }
    }

    /**
     * 处理一批 Binlog 事件
     */
    private void handleMessage(Message message) {
        for (CanalEntry.Entry entry : message.getEntries()) {
            // 只解析 RowData 类型的事件（即真正的数据变更）
            if (entry.getEntryType() == CanalEntry.EntryType.ROWDATA) {
                try {
                    // 解析变更数据
                    CanalEntry.RowChange rowChange = CanalEntry.RowChange.parseFrom(entry.getStoreValue());
                    CanalEntry.EventType eventType = rowChange.getEventType();
                    System.out.println("====> Binlog事件类型: " + eventType);

                    // 遍历每一行数据的变更
                    for (CanalEntry.RowData rowData : rowChange.getRowDatasList()) {
                        if (eventType == CanalEntry.EventType.INSERT) {
                            // 插入：打印 After 值
                            rowData.getAfterColumnsList()
                                   .forEach(c -> System.out.println(c.getName() + "=" + c.getValue()));
                        } else if (eventType == CanalEntry.EventType.UPDATE) {
                            // 更新：打印更新后的值
                            rowData.getAfterColumnsList()
                                   .forEach(c -> System.out.println(c.getName() + "=" + c.getValue()));
                        } else if (eventType == CanalEntry.EventType.DELETE) {
                            // 删除：打印 Before 值
                            rowData.getBeforeColumnsList()
                                   .forEach(c -> System.out.println(c.getName() + "=" + c.getValue()));
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    }

    /**
     * Bean 销毁时执行，关闭 Canal 连接
     */
    @Override
    public void destroy() {
        if (connector != null) {
            connector.disconnect();
        }
    }
}
```

这段代码实现了 Spring 项目启动时自动连接 Canal Server，订阅数据库 binlog 事件

> 其中使用了两个 Spring 框架中提供的生命周期接口 **`InitializingBean`** 和 **`DisposableBean`**
>
> `InitializingBean`
>
> ```java
> public interface InitializingBean {
>     void afterPropertiesSet() throws Exception;
> }
> ```
>
> 用于在 **Spring Bean 初始化完成后** 执行自定义逻辑。
>
> 使用场景
>
> - 建立连接（数据库、MQ、Canal 这种就是典型用法）。
> - 校验配置参数是否正确。
> - 启动异步任务。
>
> `DisposableBean`
>
> ```java
> public interface DisposableBean {
>     void destroy() throws Exception;
> }
> ```
>
> 用于在 **Spring 容器销毁 Bean 时** 执行收尾逻辑。
>
> 使用场景
>
> - 释放资源（关闭数据库连接、线程池、消息队列连接、文件句柄）。
> - 停止后台线程，避免内存泄漏。
>
> 在现代 Spring 项目中，更多的是使用注解 `@PostConstruct` 和 `PreDestory` 来实现初始化和销毁的作用
>
> ```java
> @Component
> public class MyBean {
> 
>     @PostConstruct
>     public void init() {
>         System.out.println("Bean 初始化完成");
>     }
> 
>     @PreDestroy
>     public void cleanup() {
>         System.out.println("Bean 即将销毁");
>     }
> }
> ```

#### 过滤表

默认情况下，Canal 会订阅 MySQL 实例下所有数据库、所有表的 binlog。有时候这是不可接受的（数据量过大、性能消耗大），所以必须通过 **正则表达式**来指定要监听的表。 

所以可以添加 `canal.instance.filter.regex` 配置，来实现表的过滤

语法规则

- 格式：`库名.表名`
- 支持正则表达式 (`.*`) 和多个表（用逗号分隔）

示例：

```properties
# 监听 userdb 库的所有表
canal.instance.filter.regex=userdb\\..*

# 监听 userdb.t_user 和 orderdb.t_order 两张表
canal.instance.filter.regex=userdb\\.t_user,orderdb\\.t_order

# 监听所有库下以 t_ 开头的表
canal.instance.filter.regex=.*\\.t_.*
```

注意：

- 点号 `.` 在正则里有特殊意义，必须写成 `\\.`
- 通配所有表时必须双反斜杠：`userdb\\..*`

配置排除表

- 使用 `canal.instance.filter.black.regex` 来排除某些表。

示例：

```properties
# 订阅所有表，但排除 binlog 记录表和日志表
canal.instance.filter.regex=.*\\..*
canal.instance.filter.black.regex=.*\\.(binlog_backup|sys_log)
```

#### Canal 与消息中间件结合使用

架构

```markdown
 MySQL (binlog)
       │
       ▼
  Canal Server (解析 binlog -> 事件)
       │
       ▼
  Canal Adapter (kafka/rocketmq/rabbitmq)
       │
       ▼
  消息中间件 (Kafka / RocketMQ / RabbitMQ)
       │
 ┌─────┴────────────┐
 ▼                  ▼
ES/Redis          业务微服务
```

在生产环境中，Canal 一般不会让业务系统直接连它，而是 **把数据写入消息队列/ES**，由下游异步消费。

##### Canal -> Kafka

使用 Canal Kafka Adapter

配置文件：`conf/application.yml`

```yaml
canal:
  server:
    mode: kafka
  kafka:
    bootstrap.servers: localhost:9092
    topic: canal-topic
    partition: 0
```

启动后，Canal 会自动把解析好的数据推送到 `canal-topic`。

Spring Boot 作为 Kafka 消费者即可：

```java
@Component
public class CanalKafkaConsumer {

    @KafkaListener(topics = "canal-topic", groupId = "test-group")
    public void listen(String message) {
        System.out.println("收到Canal消息：" + message);
    }
}
```

##### Canal -> RocketMQ

```yaml
canal:
  server:
    mode: rocketmq
  rocketmq:
    nameServer: 127.0.0.1:9876
    topic: canal-topic
```

Spring Boot 使用 RocketMQ Starter 消费：

```java
@Component
@RocketMQMessageListener(topic = "canal-topic", consumerGroup = "canal-consumer")
public class CanalRocketMqConsumer implements RocketMQListener<String> {
    @Override
    public void onMessage(String message) {
        System.out.println("收到Canal消息：" + message);
    }
}
```

##### Canal -> Elasticsearch

使用 Canal 提供的 **ElasticSearch Adapter**

配置 `es7/mytest_user.yml`

```yaml
dataSourceKey: defaultDS
destination: example
esMapping:
  _index: user_index
  _id: _id
  sql: "select id as _id, name, age from user"
```

启动 adapter 后，Canal 会自动把 MySQL 的数据写入 ES 索引。

**Canal + 消息中间件（Kafka / RocketMQ / RabbitMQ）** 的默认模式只是把 MySQL 的 binlog 事件变更丢到 MQ 里。
这些原始消息大多是 **RowChange 结构 / JSON 格式**，下游要真正能用，还需要 **进一步处理、转换和消费**。

Canal Server 解析 binlog 后，会输出类似的 JSON 消息到 Kafka/RocketMQ：

```json
{
  "database": "mydb",
  "table": "user",
  "pkNames": ["id"],
  "isDdl": false,
  "type": "UPDATE",
  "ts": 1695012345678,
  "sql": "",
  "before": {
    "id": "1001",
    "name": "Alice",
    "age": "20"
  },
  "after": {
    "id": "1001",
    "name": "Alice",
    "age": "21"
  }
}
```

字段含义：

- **database/table** -> 来自哪个库、哪个表
- **type** -> 事件类型（INSERT/UPDATE/DELETE/DDL）
- **before/after** -> 修改前/修改后的行数据
- **ts** -> 事件时间戳

它本质上就是一个 **通用的数据库行级别变更事件**。

为什么还需要进一步处理？

1. **数据结构差异**
   - MQ 消息是通用 JSON，业务系统需要转换成内部的 DTO/实体。
2. **业务逻辑需求**
   - 例如：
     - 下游 **缓存系统**（Redis）需要 key/value 形式
     - 下游 **搜索引擎**（ES）需要文档结构
     - 下游 **数据仓库**（ClickHouse/Flink）需要事实表/维度表
3. **幂等和顺序**
   - 下游消费时必须保证重复消费/乱序不会导致数据错误。

> 我们要知道，Canal **默认**传输的其实是它内部的 **Entry 对象（Protobuf 二进制序列化）**，而不是 JSON。
>
> **Canal 内部数据结构**是 `CanalEntry.Entry`（Google Protobuf 定义的）。
>
> 如果在 `canal.properties` 或 MQ 配置中 **没有配置** `canal.mq.flatMessage=true`，Canal 会直接把 **Protobuf 二进制消息**推送到 Kafka / RocketMQ。
>
> 下游消费者拿到的就是字节数组，需要自己用 Protobuf 反序列化，代码大概是：
>
> ```java
> CanalEntry.Entry entry = CanalEntry.Entry.parseFrom(messageBytes);
> ```
>
> 为了让下游业务更容易消费（特别是 Kafka、RocketMQ 这种场景），Canal 提供了一个“扁平化消息格式”：
>
> ```properties
> # canal.properties
> canal.mq.flatMessage = true
> ```
>
> 这样，Canal 会把解析出来的 binlog 事件，转换成 **FlatMessage 对象**，再序列化为 JSON 字符串，推送到 MQ。
>
> 下游就能直接消费 JSON，比如：
>
> ```json
> {
>   "database": "mydb",
>   "table": "user",
>   "type": "UPDATE",
>   "data": [{"id":"1001","name":"Alice","age":"22"}],
>   "old": [{"age":"21"}]
> }
> ```

**Canal 如何和 Elasticsearch 对接** 的呢

Canal 自身只做 **binlog 捕获和解析**，真正和 ES 交互，需要依赖 **canal.adapter**。

`canal.adapter` 是 Canal 官方提供的一个 **数据同步插件系统**。

它内置了一些 **转换器（Adapter/Plugin）**，能把 binlog 事件转成特定系统能接受的数据格式。

对于 ES，Canal 提供了 **ES Adapter**，会把数据库的行数据转成 ES 的文档。

Canal 提供的 ES 转换器在 `canal.adapter` 包里，主要有以下两类适配器：

1. **ES Adapter（es7 / es6）**
   - 直接将 MySQL 表的数据映射到 Elasticsearch 索引。
   - 自动处理 **INSERT/UPDATE/DELETE** -> ES 的 **index/update/delete**。
   - 支持 SQL 映射配置，可以灵活选择表字段与 ES 文档的对应关系。
2. **通用 RDB -> ES 映射器**
   - 使用配置文件 `yml` 定义 MySQL -> ES 的映射规则。
   - 支持多表映射、字段重命名、函数计算。

配置示例（MySQL -> ES）

在 `canal.adapter/conf/es7/` 下新建配置文件，比如 `user.yml`：

```yaml
dataSourceKey: defaultDS  # 数据源
destination: example      # 对应 canal.instance 名称
groupId: g1

esMapping:
  _index: user_index       # ES 索引名
  _id: _id                 # ES 主键
  sql: "select id as _id, name, age, email from user"  # SQL 定义映射
  etlCondition: "where id > 0"
  commitBatch: 3000
```

- `dataSourceKey`：数据源配置，定义在 `application.yml`
- `destination`：对应 canal.instance 名称
- `sql`：决定同步哪些字段、如何映射到 ES
- `etlCondition`：ETL 初始条件（全量同步时使用）

运行机制

1. **Canal Server** 采集 MySQL binlog -> 生成 Entry/FlatMessage。
2. **Canal Adapter (ES)** 订阅 Canal Server 的数据。
3. 按照 `esMapping` 配置，把数据转成 **Elasticsearch JSON 文档**：
   - INSERT -> `index`
   - UPDATE -> `update`
   - DELETE -> `delete`

```markdown
MySQL -> Canal Server -> Canal Adapter(ES) -> Elasticsearch
```

##### 既然 canal 提供了直接将增量消息传递给 elasticsearch 的 adapter，那为什么再一些项目中还需要引入 mq 插件来做中转站。

接下来我们以一个电商项目为例

**电商项目中，不直接用 Canal -> Elasticsearch，而是用 Canal -> MQ -> 消费端 -> Elasticsearch**。原因并不是 Elasticsearch 消息适配器本身有致命问题，而是涉及到 **可靠性、解耦、伸缩性和容错**

##### 直接 Canal -> Elasticsearch 的问题

Canal 有官方的 Adapter 可以把 binlog 增量同步到 Elasticsearch，例如 canal-adapter 提供了 ES Sink。

但是 **缺点** 比较明显：

1. **可靠性差**
   - Canal Adapter 是单机或单点执行的，如果同步失败（ES 临时不可用、网络异常），消息可能丢失。
   - ES Sink 不是事务型的，没办法保证数据库提交成功的同时 ES 也成功。
   - 如果直接写 ES，失败重试逻辑较复杂，需要自己管理批量重试、死信队列等。
2. **扩展性受限**
   - Canal-adapter 内部是单线程或者线程池模式，写 ES 高峰可能导致阻塞。
   - 对于电商项目，SKU、订单、商品库数据量巨大，直接 Canal -> ES 很难做横向扩展。
   - MQ 作为中间件可以天然做流量削峰、分组订阅、多消费者并行处理。
3. **解耦性差**
   - 如果 Canal Adapter 直接写 ES，那么 Adapter 就必须知道业务 ES 结构（索引、mapping、BO 映射规则），耦合度高。
   - 如果业务逻辑需要修改索引结构、增加字段、修改转换规则，直接 Adapter 改动很麻烦。
4. **监控和补偿复杂**
   - MQ 可以天然保存消息（支持延迟、重试、死信队列），方便统计消费情况和补偿策略。
   - 直接 Adapter 写 ES，失败后只能依靠日志或人工修复，不方便做全量补偿。
5. **顺序与幂等处理复杂**
   - ES 更新是幂等操作（upsert）更安全。如果直接 Adapter 写 ES，需要自己保证顺序，否则可能覆盖旧数据。
   - MQ + 消费端可以控制分区、消费顺序、批量更新，保证幂等和顺序。

使用 mq 之后

1. **解耦 Canal 与业务**
   - Canal 只负责把数据库增量消息发布到 MQ，不需要关心 ES 索引结构和业务逻辑。
   - 消费端根据业务需要去处理消息，比如不同的 Processor 处理 brand/spu/sku 等。
2. **高可用与可靠性**
   - MQ 提供消息持久化、重试、死信队列，避免消息丢失。
   - 消费端可以并发处理、批量写 ES，提高吞吐。
3. **削峰与弹性伸缩**
   - 高峰期数据库产生大量变更，MQ 可以做缓冲，消费者按自身消费能力处理。
   - 可以增加消费者实例，提高消费能力，而不影响 Canal 端。
4. **支持多业务订阅**
   - 同一条增量消息，可以被多个消费者处理，支持不同业务场景（搜索、推荐、缓存更新等）。

Elasticsearch Adapter 本身的局限性

- Canal-adapter 的 ES Sink 本质上是一个**轻量级插件**，不是专门为高并发、高可用、幂等处理设计。
- 对于生产级电商：
  - 大量 SKU/订单数据，高峰期可能直接 Adapter 写 ES 失败；
  - Adapter 没有天然消息重试机制，失败后可能丢消息；
  - Adapter 和业务逻辑耦合高，维护成本大。
- 因此实际生产中，大多改成 **Canal -> MQ -> Spring Boot 消费 -> ES**。

接下来大致实现一下这个方案

```markdown
MySQL (启用 binlog)
    ↓ (binlog)
Canal Server (解析 binlog)
    ↓ (Canal-Adapter 推送消息)
RocketMQ Broker (topic: canal_topic)
    ↓ (消费者)
Spring Boot 应用 (RocketMQ listener)
    - CanalGlue 解析 JSON -> 找到对应 Processor
    - Processor 将变化映射为业务 BO（BrandBO/SpuBO/...）
    - ProductUpdateManager 使用 RestHighLevelClient 批量 update / upsert ES index
Elasticsearch (存储搜索索引)
```

消息体（CanalAdapter 推送到 RocketMQ）示例 JSON

```json
{
  "database": "mall_product",
  "table": "brand",
  "type": "UPDATE", // INSERT|UPDATE|DELETE
  "isDdl": false,
  "data": [ { "brand_id": 1, "name": "new", "img_url":"..." } ],
  "old": [ { "name": "old" } ],
  "pkNames": ["brand_id"],
  "sql": "update brand set name=... where brand_id=1"
}
```

跳过 canal 配置文件，直接进入 Spring Boot

```xml
<dependencies>
  <!-- Spring Boot -->
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter</artifactId></dependency>

  <!-- RocketMQ Spring Boot -->
  <dependency>
    <groupId>org.apache.rocketmq</groupId>
    <artifactId>rocketmq-spring-boot-starter</artifactId>
    <version>2.2.0</version>
  </dependency>

  <!-- Elasticsearch Rest High Level Client -->
  <dependency>
    <groupId>org.elasticsearch.client</groupId>
    <artifactId>elasticsearch-rest-high-level-client</artifactId>
    <version>7.17.0</version>
  </dependency>

  <!-- Fastjson (json parse) -->
  <dependency><groupId>com.alibaba</groupId><artifactId>fastjson</artifactId><version>1.2.83</version></dependency>

  <!-- lombok -->
  <dependency><groupId>org.projectlombok</groupId><artifactId>lombok</artifactId><optional>true</optional></dependency>
</dependencies>
```

application.yml

```yaml
spring:
  application:
    name: canal-consumer
rocketmq:
  name-server: 127.0.0.1:9876
  consumer:
    message-model: BROADCASTING

es:
  host: localhost
  port: 9200
  index: product_index
```

定义一个 Java Bean 用于反序列化消息

```java
@Data
public class CanalBinLogEvent {
    private String database;
    private String table;
    private String type; // INSERT|UPDATE|DELETE
    private Boolean isDdl;
    private List<Map<String,Object>> data;
    private List<Map<String,Object>> old;
    private List<String> pkNames;
    private String sql;
}
```

注册一个 RocketMQ Listener，接收 MQ 消息并交给 CanalGlue

```java
@Component
@RocketMQMessageListener(topic = "canal_topic", consumerGroup = "canal_consumer_group")
public class CanalListener implements RocketMQListener<String> {

    private static final Logger log = LoggerFactory.getLogger(CanalListener.class);

    @Autowired
    private CanalGlue canalGlue;

    @Override
    public void onMessage(String message) {
        log.info("received canal mq message: {}", message);
        try {
            canalGlue.process(message);
        } catch (Exception e) {
            log.error("process canal message error", e);
            // 生产环境中可视情况重试/记录死信队列
        }
    }
}
```

定义一个解析并分发给对应表的 processors

```java
@Component
public class CanalGlue {

    private final Map<String, BaseCanalBinlogEventProcessor<?>> processorMap = new ConcurrentHashMap<>();

    // 注册 processor，key 形如 database.table
    public void registerProcessor(String database, String table, BaseCanalBinlogEventProcessor<?> processor) {
        processorMap.put(database + "." + table, processor);
    }

    public void process(String message) {
        CanalBinLogEvent event = JSON.parseObject(message, CanalBinLogEvent.class);
        String key = event.getDatabase() + "." + event.getTable();
        BaseCanalBinlogEventProcessor<?> processor = processorMap.get(key);
        if (processor == null) {
            // 没有注册 processor，则忽略或记录
            return;
        }
        processor.process(event);
    }
}
```

抽象处理器 BaseCanalBinlogEventProcessor

```java
public abstract class BaseCanalBinlogEventProcessor<T> {

    protected final Logger log = LoggerFactory.getLogger(getClass());

    // 子类在构造后调用 init 注册（或使用@PostConstruct）
    public void process(CanalBinLogEvent event) {
        String type = event.getType(); // INSERT/UPDATE/DELETE
        if ("INSERT".equalsIgnoreCase(type)) {
            if (event.getData() != null) {
                for (Map<String,Object> row : event.getData()) {
                    T after = mapToEntity(row);
                    processInsert(after);
                }
            }
        } else if ("UPDATE".equalsIgnoreCase(type)) {
            int size = event.getData() == null ? 0 : event.getData().size();
            for (int i = 0; i < size; i++) {
                Map<String,Object> afterMap = event.getData().get(i);
                Map<String,Object> beforeMap = (event.getOld() != null && event.getOld().size() > i) ? event.getOld().get(i) : null;
                T after = mapToEntity(afterMap);
                T before = beforeMap == null ? null : mapToEntity(beforeMap);
                processUpdate(before, after);
            }
        } else if ("DELETE".equalsIgnoreCase(type)) {
            if (event.getData() != null) {
                for (Map<String,Object> row : event.getData()) {
                    T before = mapToEntity(row);
                    processDelete(before);
                }
            }
        }
    }

    protected abstract T mapToEntity(Map<String,Object> data);
    protected void processInsert(T after) {}
    protected void processUpdate(T before, T after) {}
    protected void processDelete(T before) {}
}
```

ProductUpdateManager 更新 ES 的实现

```java
@Component
public class ProductUpdateManager {

    private static final Logger log = LoggerFactory.getLogger(ProductUpdateManager.class);

    @Autowired
    private RestHighLevelClient restHighLevelClient;

    @Value("${es.index:product_index}")
    private String index;

    public void esUpdateSpuBySpuIds(List<Long> spuIds, Object esProductBO) {
        if (spuIds == null || spuIds.isEmpty()) return;

        try {
            BulkRequest bulk = new BulkRequest();
            String json = JSON.toJSONString(esProductBO);
            for (Long id : spuIds) {
                // upsert: 如果不存在则 create（通过 doc_as_upsert）
                UpdateRequest ur = new UpdateRequest(index, String.valueOf(id))
                        .doc(json, XContentType.JSON)
                        .docAsUpsert(true);
                bulk.add(ur);
            }
            BulkResponse resp = restHighLevelClient.bulk(bulk, RequestOptions.DEFAULT);
            if (resp.hasFailures()) {
                log.error("es bulk has failures: {}", resp.buildFailureMessage());
            }
        } catch (Exception e) {
            log.error("es update exception", e);
            throw new RuntimeException(e);
        }
    }
}

```

并提供 `RestHighLevelClient` Bean：

```java
@Configuration
public class EsConfig {
    @Value("${es.host:localhost}")
    private String host;
    @Value("${es.port:9200}")
    private int port;

    @Bean(destroyMethod = "close")
    public RestHighLevelClient restHighLevelClient() {
        RestClientBuilder builder = RestClient.builder(new HttpHost(host, port, "http"));
        return new RestHighLevelClient(builder);
    }
}
```

示例 Processor：BrandProcessor 监听 brand 表

```java
@Component
public class BrandProcessor extends BaseCanalBinlogEventProcessor<BrandBO> {

    @Autowired
    private ProductUpdateManager productUpdateManager;
    @Autowired
    private ProductFeignClient productFeignClient; // 假设存在，查询 spuId 列表

    @PostConstruct
    public void init() {
        // 注册到 glue（database=mall_product, table=brand）
        // 通过构造注入 canalGlue 或从 SpringContextUtils 取得
    }

    @Override
    protected BrandBO mapToEntity(Map<String, Object> data) {
        BrandBO bo = new BrandBO();
        if (data.get("brand_id") != null) bo.setBrandId(Long.valueOf(data.get("brand_id").toString()));
        bo.setName((String) data.get("name"));
        bo.setImgUrl((String) data.get("img_url"));
        return bo;
    }

    @Override
    protected void processUpdate(BrandBO before, BrandBO after) {
        boolean needUpdate = false;
        EsProductBO esProductBO = new EsProductBO();
        if (before != null && !Objects.equals(before.getName(), after.getName())) {
            esProductBO.setBrandName(after.getName());
            needUpdate = true;
        }
        if (before != null && !Objects.equals(before.getImgUrl(), after.getImgUrl())) {
            esProductBO.setBrandImg(after.getImgUrl());
            needUpdate = true;
        }
        if (needUpdate) {
            List<Long> spuIds = productFeignClient.getSpuIdsByBrandId(after.getBrandId()).getData();
            productUpdateManager.esUpdateSpuBySpuIds(spuIds, esProductBO);
        }
    }
}
```

> 说明：`BrandBO` / `EsProductBO` / `ProductFeignClient` 是业务相关类，需按项目定义。`BrandProcessor` 在 `@PostConstruct` 或构造时把自己注册到 `CanalGlue.registerProcessor("mall_product","brand", this)`。

首先 canal 接收到的增量数据消息会被发送给 mq，mq 中会直接调用 CanalGlue 来处理增量数据

`CanalGlue` 是如何处理增量数据呢

我们看这个类可以发现，里面维护着一个 Map 数据结构，该数据结构是以 数据库 + 表名 作为 key，对应的 value 是处理相应表的处理器。这个类中有一个方法 `process` 方法，该方法首先将 mq 传来的 json 消息转换成自定义的 `CanalBinLogEvent` Java Bean，然后通过获取 数据库 + 表名 拼接成 key 得到相应的 处理器实例 来调用其 `process` 方法进行真正的数据解析处理

`BaseCanalBinlogEventProcessor` 是处理器的抽象类，它定义了一个处理器的骨架，我们只需要根据相应的数据库表结构定制对应的 处理器类就可以了

接着往下看的化，我们封装了一个 elasticsearch 的 CRUD 类 `ProductUpdateManager`，用来真正进行和 elasticsearch 的交互。

最终，我们自己继承 `BaseCanalBinlogEventProcessor` 抽象类，真正实现一个处理器类 `BrandProcessor`，该类的主要逻辑就是实现消息到 Java Bean 类的具体解析，然后调用相应的 elasticsearch CRUD 方法完成增量数据的更新。

将该类注册到 `CanalGlue` 中，当 mq 收到对应表的消息就会调用该类处理
