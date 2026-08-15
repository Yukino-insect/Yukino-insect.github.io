+++
date = '2025-09-20T20:34:39+08:00'
draft = false
title = 'Redis 可以实现的功能'
+++

redis 是一款开源的基于内存的数据结构存储系统，它可以实现很多功能

## Redis 缓存

由于 redis 优异的读写性能，redis 缓存常被作为解决高并发的基本工具，将热点数据存储在 redis 中，可以提高读写性能和响应速度，减少对后端数据存储的压力。但这也存在一些问题，如：数据一致性、缓存穿透和雪崩、高可用集群等等。

#### 缓存

缓存分为本地缓存和分布式缓存。

本地缓存主要的特点是轻量和快速，其生命周期会随着 JVM 的销毁而结束，在分布式多实例的情况下，本地缓存不具有一致性。

使用 redis 等实现的缓存称为分布式缓存，在分布式多实例的情况下，所有节点公用一份缓存数据，具有一致性。由于数据存储在内存中，所以不可能存放大量数据，因此常把热点数据、读多写少的数据放入缓存。

**使用 Java 实现 Redis 缓存的方式有**：

- 自己通过 spring-data-redis 等客户端封装

- 通过集成 Spring Cache 来实现缓存。

> 具体之后再详写

**保证数据一致性**

redis 作为第三方缓存层，它和存储数据的数据库必然存在数据一致性问题。

读取缓存的步骤一般没有什么问题，但是一旦涉及到了更新数据就容易出现缓存数据和数据库数据的一致性问题，因此可以采用以下模式：

- 先更新数据库，再删除缓存。

  >  在高并发环境下可能出现脏数据回写
  >
  > 比如，一个是读操作，但是没有命中缓存，然后就到数据库中取数据，此时来了一个写操作，写完数据库后，让缓存失效，然后，之前的那个读操作再把老的数据放进去，所以，会造成脏数据。

- 延迟双删策略

  > 第二次删除能覆盖并发下的缓存回写问题

-  消息队列异步更新缓存

  > 写数据库成功后，发送一个 MQ 消息
  >
  > 消费者收到后去删除/更新缓存

- 订阅数据库 Binlog

  > 在 redis 的热数据中读取，增删改都是操作MySQL，然后通过 canal 对mysql 的 binlog 进行监听，然后向 redis 推送修改的数据

在高并发业务场景下，数据库大多数情况下都是用户并发访问最薄弱的环节，使用 redis 做一个缓冲操作，让请求现访问 redis，而不是直接访问 MySQL 数据库。这样可以大大缓解数据库压力。但是，这样仍会出现一些问题：

- 缓存穿透：指缓存和数据库中都没有的数据，被用户不断请求，请求直接打到数据库。

  > 原因：可能是由于攻击者发送大量恶意请求，故意查询不存在的数据。也有可能是正常业务中大量并发请求查询不存在的数据
  >
  > 解决方案：
  >
  > - 可以设置布隆过滤器，快速判断查询的数据是否存在于缓存或数据库中，不存在就直接返回
  > - 可以将查询数据库中返回空的结果缓存起来，这样在下次查询的时候直接返回缓存中的空值，避免频繁查询数据库的操作
  > - 可以通过校验手段，限制恶意请求

- 缓存击穿：指缓存中没有但数据库中有的数据（一般是缓存过期），由于这时并发用户特别多，同时读缓存没读到，又同时去数据库读数据，造成数据库压力瞬间增大。即，并发查询同一条数据。

  > 原因：可能是在高并发情况下，大量请求同时访问同一个缓存中不存在的热点数据
  >
  > 解决方案：
  >
  > - 设置热点数据永不过期
  > - 做好接口的限流
  > - 通过加互斥锁

- 缓存雪崩：指缓存数据大批量过期，而查询数据量巨大，引起数据库压力过大。即，很多数据过期，很多都要查询数据库。

  > 原因：可能是大量缓存设置了相同的过期时间，导致某一时刻缓存同时失效。也可能是缓存服务器宕机
  >
  > 解决方案：
  >
  > - 设置热点数据永不过期
  > - 设置缓存数据的过期时间为随机值
  > - 如果缓存数据库是分布式部署，将热点数据均匀分布在不同的缓存数据库中

- 缓存污染：指缓存中存在大量永不会被访问的数据，占用有限的缓存空间。导致增加了 redis 淘汰策略的开销。

**redis 内存淘汰策略：**

redis 是内存型数据库，数据存储在内存中，如果内存满了，就需要触发内存淘汰策略。

在配置文件中设置：

```conf
maxmemory 512mb   # 限制最大内存
maxmemory-policy allkeys-lru   # 设置淘汰策略
```

redis 的内存淘汰策略有：

1. 不淘汰

   - `noeviction`（默认）：内存满了直接报错，不会删除任何数据

     >  一般用于持久化场景（保证数据不会丢）

2. 只淘汰设置过过期时间的键

   - `volatile-lru`：从设置了过期时间的键里，挑选最久没用的淘汰（LRU）

   - `volatile-lfu`：从设置了过期时间的键里，挑选使用次数最少的淘汰（LFU）

   - `volatile-ttl`：从设置了过期时间的键里，优先淘汰 TTL（剩余生存时间）最短的

   - `volatile-random`：从设置了过期时间的键里，随机淘汰

     >  适用于做缓存场景（缓存本来就是短期的，没过期时间的数据一般不删）。
     >
     > LRU 是淘汰最近最少使用的缓存（时间维度）
     >
     > LFU 是淘汰访问次数最少的缓存（频率维度）
     >
     > 选择使用哪种策略取决于具体的应用场景和访问模式。如果应用对最近访问的数据比较敏感，LRU 可能更适合；如果应用对访问频率较低的数据更感兴趣，LFU 可能更合适。有些缓存系统也采用 LRU 和 LFU 的结合策略，根据具体情况灵活选择淘汰键。

3. 所有键都可能被淘汰

   - `allkeys-lru`：所有键中挑选最久没用的淘汰（最常用 ）

   - `allkeys-lfu`：所有键中挑选使用次数最少的淘汰（Redis 4.0+ 推荐）

   - `allkeys-random`：所有键中随机淘汰

     >  适用于做纯缓存（所有数据都可以被淘汰，保证热点数据常驻）。

## Redis 实现消息队列

### 基于 List 实现消息队列

redis 的 List 数据结构可以实现消息队列的入队和出队操作。生产者将消息队列插到 List 的尾部，消费者从 List 的头部获取消息，实现先进先出的消息处理。

生产者：

```bash
# 把消息 "task1" 放到队列 "queue" 右边
rpush queue "task1"
rpush queue "task2"
rpush queue "task3"
```

消费者

```bash
# 取出队列最左边的消息
lpop queue

# 如果队列为空，阻塞等待。0 表示一直阻塞直到有消息
brpop queue 0 
```

> 使用 List 实现的消息队列没有 ACK 机制，消费者一旦 POP 出来，消息就从队列里移除，如果消费者挂了，消息就丢失了

### 使用 Redis 的发布订阅模式

redis 的发布订阅模式是一种通信模式，发送者发送消息，订阅者接收消息。以此来实现消息队列。

该模式有两种

- 基于频道(Channel)的发布/订阅
- 基于模式(pattern)的发布/订阅

### 使用 Stream

## 实现计数器和排行榜

redis 的一些数据很合适实现计数器和排行榜

- 使用 String 数据结构 + 自增命令实现计数器

  ```bash
  INCR key           # 计数 +1
  INCRBY key 10      # 计数 +10
  DECR key           # 计数 -1
  GET key            # 获取计数值
  ```

- 使用 Zset 有序列表实现排行榜

  ```bash
  ZADD rank 100 user1      # 添加用户 user1，分数 100
  ZADD rank 200 user2      # 添加用户 user2，分数 200
  ZINCRBY rank 10 user1    # 给 user1 的分数 +10
  ZRANGE rank 0 -1 WITHSCORES     # 按升序取所有
  ZREVRANGE rank 0 9 WITHSCORES   # 按降序取前10名
  ZRANK rank user1         # 查看 user1 排名（从 0 开始）
  ZREVRANK rank user1      # 查看 user1 排名（倒序）
  ZSCORE rank user1        # 查看 user1 的分数
  ```

## 实现分布式锁

在分布式环境中，多个服务实例同时操作共享资源时可能会出现并发冲突。分布式锁可以保证同一时间只有一个节点能操作资源。

**实现方式**

1. 使用 redis 提供的`SET key value NX PX ttl`

   ```bash
   # 获取锁
   SET lock:order:123 "UUID" NX PX 30000
   
   # NX -> 只有 key 不存在时才设置
   # PX 30000 -> 过期时间 30 秒
   # UUID -> 锁的持有者标识，用于解锁时校验
   ```

   ```lua
   -- 直接 DEL lock:order:123 会有风险（可能锁过期被别人拿到）
   -- 安全做法：用 Lua 脚本保证 先检查是否是自己再删除
   if redis.call("get", KEYS[1]) == ARGV[1] then
       return redis.call("del", KEYS[1])
   else
       return 0
   end
   ```

   Java实现

   ```java
   public boolean tryLock(String key, String value, long expireMillis) {
       return redisTemplate.opsForVal ue().setIfAbsent(key, value, Duration.ofMillis(expireMillis));
   }
   
   public void unlock(String key, String value) {
       String script = "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                       "return redis.call('del', KEYS[1]) else return 0 end";
       redisTemplate.execute(new DefaultRedisScript<>(script, Long.class),
                             Collections.singletonList(key), value);
   }
   ```

2. 使用 Redission 实现

   Redisson 是开源的 Redis Java 客户端，提供分布式锁、读写锁、信号量等功能

   使用简单，自动处理锁超时、重入、自动续期

   ```java
   RLock lock = redisson.getLock("order:123");
   lock.lock(30, TimeUnit.SECONDS);  // 自动释放锁
   try {
       // 业务逻辑
   } finally {
       lock.unlock();
   }
   ```

3. RedLock（多节点 Redis 分布式锁）

   RedLock 算法旨在解决单个 Redis 实例作为分布式锁时可能出现的单点故障问题，通过在多个独立运行的 Redis 实例上同时获取锁的方式来提高锁服务的可用性和安全性。RedLock 是对集群的每个节点进行加锁，如果大多数节点（N/2+1）加锁成功，则才会认为加锁成功。 这样即使集群中有某个节点挂掉了，因为大部分集群节点都加锁成功了，所以分布式锁还是可以继续使用的。

## 限流

限流是指在各种场景中，通过各种技术和策略手段对数据流量、请求频率或资源消耗进行有计划的限制，以避免系统负载过高、性能下降甚至崩溃的情况发生，维护系统的稳定性和可用性。

**限流常用的算法如下**

1. 计数器算法：将时间周期划分为固定大小的窗口（如每分钟、每小时），并在每个窗口内统计请求数量。当窗口内请求数量达到预设的阈值时，后续请求将被限制。时间窗口结束后计数器清零

   > 可能存在突刺流量问题，即在窗口结束时会有短暂的大量请求被允许通过

2. 滑动窗口算法：改进了计数器算法的突刺问题，将时间划分为多个小时间段，每个小时间段有自己的计数器。连续的小时间段组成一个时间窗口，最后计算所有小时间段的计数器之和不能超过规定的时间窗口设定的阈值。处理流量更平滑，避免了突刺问题

3. 漏桶算法：想象一个固定容量的桶，水（请求）以恒定速率流入桶中，同时桶底部有小孔让水以恒定速率流出。当桶满时，新来的水（请求）会被丢弃。此算法主要用来平滑网络流量，防止瞬时流量过大

   > 无法处理突发流量高峰，多余的请求会被直接丢弃

4. 令牌桶算法：有一个桶，里面的令牌以固定速率填充，令牌代表许可。当请求到达时，需要从桶中获取令牌，如果获取到则请求被通过，否则别拒绝。桶的容量是有限的，多余的令牌会被丢弃

   > 因为令牌可以积累，所以可以处理一定程度的突发流量

**使用 redis 实现限流**

常见限流方法有以下几种实现：

1. 基于计数器和过期时间实现的计数器算法：使用一个计数器存储当前请求量（每次使用 incr 方法相加），并设置一个过期时间，计数器在一定时间内自动清零。计数器未到达限流值就可以继续运行，反之则不能继续运行。
2. 基于有序集合（ZSet）实现的滑动窗口算法：将请求都存入到 ZSet 集合中，在分数（score）中存储当前请求时间。然后再使用 ZSet 提供的 range 方法轻易的获取到 2 个时间戳内的所有请求，通过获取的请求数和限流数进行比较并判断，从而实现限流。
3. 基于列表（List）实现的令牌桶算法：在程序中使用定时任务给 Redis 中的 List 添加令牌，程序通过 List 提供的 leftPop 来获取令牌，得到令牌继续执行，否则就是限流不能继续运行。

## 分布式会话管理

在单机应用中，HTTP Session 通常储存在服务器内存里。如果使用多节点部署，用户访问不同节点，不同节点内存中的 Session 是不会共享的。这样就导致了用户登录状态丢失。这时可以将 Session 集中存储到 redis 中，实现分布式会话管理，这样就解决了用户登录状态丢失的问题。

**实现方式**

- 手动实现

  将操作 Redis 校验 Session 的逻辑放在过滤器或拦截其中统一处理

  ```java
  @Component
  public class SessionInterceptor implements HandlerInterceptor {
  
      @Autowired
      private StringRedisTemplate redisTemplate;
  
      @Override
      public boolean preHandle(HttpServletRequest request,
                               HttpServletResponse response,
                               Object handler) throws Exception {
          String sessionId = request.getHeader("Session-Id");
          // 判断 sessionId 是否存在，即登录校验
          if (sessionId == null || !redisTemplate.hasKey("session:" + sessionId)) {
              response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
              response.getWriter().write("Session Invalid");
              return false;
          }
          // 刷新 TTL
          redisTemplate.expire("session:" + sessionId, Duration.ofMinutes(30));
          return true;
      }
  }
  ```

  Session（用户信息、登录状态、权限等）可以作为 redis 的值

- 通过 Spring Session + Redis。Spring 提供了 Spring Session 模块，可以直接替换默认 HttpSession，使用 Redis 存储。

  ```xml
  <-- 依赖 -->
  <dependency>
      <groupId>org.springframework.session</groupId>
      <artifactId>spring-session-data-redis</artifactId>
  </dependency>
  <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-redis</artifactId>
  </dependency>
  ```

  ```yaml
  # application.yml 配置
  spring:
    redis:
      host: 127.0.0.1
      port: 6379
  
  # Spring Session 默认配置
  spring:
    session:
      store-type: redis
      timeout: 1800s   # 会话过期时间
  ```

  ```java
  // 启动类
  @SpringBootApplication
  @EnableRedisHttpSession   // 开启 Redis 会话支持
  public class Application {
      public static void main(String[] args) {
          SpringApplication.run(Application.class, args);
      }
  }
  ```

  这样原本存在本地的 Session 就会保存到 redis 中
