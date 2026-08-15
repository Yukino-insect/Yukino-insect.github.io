+++
date = '2025-10-03T23:18:08+08:00'
draft = false
title = 'Nacos'
+++

在单体应用里，所有模块都在一个进程中，方法调用是本地调用，直接通过方法名就能找到目标。但是在微服务架构中，每个模块都是独立的进程，运行在不同的机器或容器上，它们的 IP 和端口可能经常变化。

那么，**问题来了**

如果 A 服务要调用 B 服务，如何知道 B 服务地址？

B 服务实例可能有堕多台，怎么实现负载均衡？

某个 B 服务实例挂了怎么剔除它？

这就是**服务注册与发现**需要解决的问题

#### 服务注册

每个服务启动时，把自己的信息注册到一个**注册中心**。这样，其他服务就可以通过这个注册中心知道这个服务的位置和状态

#### 服务发现

其他服务就是通过服务发现机制，向注册中心申请到需要的服务

> **心跳机制**
>
> 每一个正常的服务都会定期向注册中心发送心跳，证明自己健康存活，如果心跳超时，注册中心就会把这个服务实例剔除

架构示意图

```bash
[服务提供者] ── 注册 ──> [注册中心] <── 发现 ── [服务消费者]
```

接下来我们只学习当前主流的 **Nacos** 作为服务注册与发现方案

### Nacos

整体架构

```markdown
                  ┌──────────────────────────────────┐
                  │              Nacos               │
                  │   ┌────────────┐   ┌──────────┐  │
     注册发现 <──> │   │ Naming服务 │   │ Config服务│  │ <──> 配置管理
                  │   └────────────┘   └──────────┘  │
                  │        │   ▲            │  ▲     │
                  │        ▼   │            ▼  │     │
                  │   ┌────────────┐   ┌──────────┐  │
                  │   │ 元数据存储 │   │ 配置存储 │  │
                  │   └────────────┘   └──────────┘  │
                  └──────────────────────────────────┘
                                │
                        ┌──────────────┐
                        │  MySQL/Derby │   （持久化层）
                        └──────────────┘
```

从上图我们可以分析到，nacos 主要有以下核心模块

**Naming Service（服务发现模块）**

提供服务注册、注销、心跳检测。

服务消费者可从 Nacos 获取服务列表，并做负载均衡。

支持：

- **AP 模式**（可用性优先，服务不会轻易下线，适合电商、业务高可用场景）
- **CP 模式**（一致性优先，适合金融、强一致业务场景）

**Config Service（配置管理模块）**

支持集中式配置管理。

开发者可以把应用配置（数据库连接、功能开关、限流阈值等）放在 Nacos，而不是本地 yml。

客户端可以：启动时拉取配置，监听配置变化，动态刷新（无需重启应用）

支持：

- 配置分组（Group）
- 命名空间隔离（Namespace）
- 配置版本回滚
- 灰度发布

**控制台（Console）**

提供可视化 Web 界面：

- 查看服务列表、健康状态
- 管理配置（新增、修改、发布、回滚）
- 管理命名空间 / 分组
- 用户与权限管理

**存储层**

它默认使用 **嵌入式 Derby** 这样只适合单机/测试。

在生产环境需切换为 **MySQL 持久化存储**。

存储内容：

- 服务实例信息（服务名、IP、端口、健康状态、权重）
- 配置内容（DataId、Group、Namespace、内容）
- 权限、用户、角色等管理数据

**集群架构**

nacos 支持集群

通常部署 **多节点 Nacos 集群**（推荐奇数台：3/5/7）。

节点间通过 **Raft 协议** 或 **Distro 协议** 同步数据。

对外通过 **负载均衡/SLB/Nginx VIP** 提供统一访问入口。

> **CAP** 定理
>
> 它是分布式系统中的一个核心理论，用来描述在分布式架构下，系统在 **一致性**、**可用性**、**分区容错性** 三者之间的取舍
>
> 在一个分布式系统中，已被证明，**C（一致性）、A（可用性）、P（分区容错性）三者不能同时完全满足，只能最多同时满足其中的两个**
>
> C – 一致性 (Consistency)
>
> 所有节点在同一时间看到的数据是一致的。
> 换句话说，**对某个数据的更新，所有节点要么都看到新值，要么都看到旧值，不允许有差异**。
>
> A – 可用性 (Availability)
>
> 系统在任何时候都能返回一个 **非错误响应**（即服务总是可用）。
> 即使部分节点故障，系统仍然能在合理时间内响应用户请求。
>
> P – 分区容错性 (Partition Tolerance)
>
> 当网络分区（节点之间通信中断或延迟）时，系统仍能继续工作。
> 因为分布式系统必然跨多台机器/机房，网络分区一定可能发生，所以 **P 在分布式系统里是必选项**。
>
> #### CAP 定理的三种取舍
>
> 因为 **P 必须保证**（分布式系统无法避免网络分区），所以只能在 **C 和 A 之间二选一**。
>
> **CP 系统**（一致性 + 分区容错性）
>
> 它是强一致性，牺牲部分可用性。如果节点之间网络分区，就暂停服务或拒绝请求，直到数据同步完成。
>
> 典型场景：金融转账、支付系统（宁可暂时不可用，也不能出现错账）。
>
> **AP 系统**（可用性 + 分区容错性）
>
> 保证系统始终可用，允许节点之间数据短时间不一致。系统会返回“尽力而为”的结果，后续通过同步机制实现最终一致性。
>
> 典型场景：电商、社交、缓存（只要不挂，哪怕看到旧数据也行）。
>
> Nacos 默认选择此模式
>
> **CA 系统**（一致性 + 可用性）
>
> 不考虑分区容错性（只能在单机或强可靠网络里成立）。一旦发生网络分区，整个系统不可用，所以 **在分布式环境几乎不存在**。

使用 nacos 主要分为两部分，启动 nacos-server，搭建 nacos-client

#### nacos-server

下载好 Nacos 软件包，在服务器上启动 nacos 注册中心

单例模式

```bash
// 只启动单个节点
startup -m standalone
```

集群模式

```bash
// 搭建好多节点集群
startup
```

#### 如何搭建一个 nacos 集群

nacos 默认数据存储在内嵌数据库 Derby 中，并不适合用于生产环境，官方推荐的最佳实践是使用带有主从的高可用 MySQL 数据库集群存储持久化数据

部署架构

```markdown
                                    nacos client
                                         |
                                        \|/
                                       nginx
                  ______________________|____________________
                  |                      |                    |
                 \|/                    \|/                  \|/ 
            nacos server1           nacos server2        nacos server3
                                         |
                                         |
                                    高可用 MySQL
```

创建集群的步骤：

1. 创建一个数据库 nacos_config，导入 nacos 包下的 sql 脚本，用于存储相关数据
2. 修改 `application.properties` 文件，将数据存储位置改为 mysql
3. 创建一个 cluster 目录，在下面复制三个 nacos 包，分别将位置改为不同的端口
4. 然后再每个 nacos 下创建一个 `cluster.conf` 文件
5. 最后配置 nginx，启动项目

> 不同nacos节点如何是实现数据共享：
>
> - 配置管理的数据保存在mysql中，确保多节点共享和持久化
>
> - 服务注册的数据：
>   - 临时实例主要依赖Raft协议+内存复制在内存中保存一致，不会全部写入mysl
>   - 非临时实例会写入mysql从而实现跨节点共享

#### nacos-client

nacos-client 的搭建，只是在普通 spring-boot 项目中引入客户端依赖，添加配置即可。注意 nacos-server 需要保持启动状态，否则客户端会因为连接不上而导致注册失败

```xml
<!--nacos的管理依赖-->
<dependencyManagement>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-alibaba-dependencies</artifactId>
    <version>2.2.5.RELEASE</version>
    <type>pom</type>
    <scope>import</scope>
</dependencyManagement>

<!-- nacos客户端依赖包 -->
<!-- 服务发现，这样就可以向注册中心注册该服务 -->
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
</dependency>
```

`application.yml` 配置文件

```yaml
server:
  port: 8081
spring:
  application:
    name: orderservice #设置当前应用名称
  cloud:
    nacos:
      server-addr: http://localhost:8848 # nacos服务地址
```

配置完成启动项目后，可以在 nacos 的控制台服务列表中看到该服务已经注册成功

#### 临时实例和持久实例

nacos 在注册实例时分临时实例和持久实例，这在服务注册发现中是非常重要的概念，直接影响服务的下线方式和容灾策略

##### 临时实例

服务实例和 Nacos 之间通过 **心跳机制 **维持。

如果实例超过心跳超时时间没有上报心跳，Nacos 会认为它失效并**自动删除**。

**特点**：

实例生命周期就是应用进程生命周期。如果发生了进程宕机 / 网络中断，实例就会自动下线。无需人工干预。

**适用场景**：大多数微服务（电商、业务应用），要求自动摘除故障实例，保证可用性。

##### 持久实例

注册时声明为持久实例，Nacos 不依赖心跳来判断存活。实例信息会一直保存在注册中心，**除非手动删除**。

**特点**：实例不会因为心跳丢失而自动下线。即使服务宕机，Nacos 依旧返回该实例。需要 **人工管理** 实例的上下线。

**适用场景**：数据库、中间件、MQ 等基础设施服务，这些通常稳定，且不希望因为短暂的网络抖动被错误摘除。

`application.yml` 的配置如下

```yaml
spring:
  cloud:
    nacos:
      discovery:
        ephemeral: true   # 默认 true = 临时实例
```

#### 负载均衡

如果存在多个实例，客户端请求发送时就需要关注负载均衡策略。

如何在 nacos 中配置常见的负载均衡策略？

Spring Cloud 2020+ 默认使用 **Spring Cloud LoadBalancer**，不再支持 Ribbon。

##### 全局默认策略配置

```yaml
spring:
  cloud:
    loadbalancer:
      strategy: random  # 全局使用随机策略
```

可选值：`random`、`round_robin`

##### 针对某个服务配置策略

新版本推荐用 **Java 配置类**：

```java
@Configuration
@LoadBalancerClient(name = "user-service", configuration = UserServiceLoadBalancerConfig.class)
public class UserServiceLoadBalancerConfiguration {
}

class UserServiceLoadBalancerConfig {
    @Bean
    ReactorServiceInstanceLoadBalancer userServiceLoadBalancer(
            Environment environment,
            ServiceInstanceListSupplier supplier) {
        String serviceId = environment.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);
        // 使用轮询策略
        return new RoundRobinLoadBalancer(supplier, serviceId);
    }
}
```

##### 权重策略 / 元数据路由（Nacos 特有）

Nacos 提供了**权重 (weight)** 和 **metadata**，可配合负载均衡实现更复杂的路由。

服务提供者配置权重

```yaml
spring:
  cloud:
    nacos:
      discovery:
        weight: 2   # 权重，默认 1
        metadata:
          version: v2   # 元数据，用于灰度发布
```

消费者端基于 metadata 自定义路由

```java
@Bean
public ReactorServiceInstanceLoadBalancer versionAwareLoadBalancer(
        Environment env,
        ServiceInstanceListSupplier supplier) {
    String serviceId = env.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);
    return (request) -> supplier.get().next()
        .map(instances -> {
            // 只选 version=v2 的实例
            List<ServiceInstance> filtered = instances.stream()
                .filter(i -> "v2".equals(i.getMetadata().get("version")))
                .toList();
            return new DefaultResponse(filtered.get(0));
        });
}
```

这样就能实现 **灰度发布** 或 **蓝绿部署**。

生产环境常用策略

| 策略       | 特点                      | 适用场景           |
| ---------- | ------------------------- | ------------------ |
| 随机       | 简单、均匀                | 普通业务           |
| 轮询       | 顺序分配                  | 服务性能接近       |
| 权重       | 根据机器性能/版本比例分配 | 灰度发布、异构集群 |
| 最少连接   | 给空闲实例更多请求        | 处理耗时差异大     |
| 元数据路由 | 按版本、标签分流          | 蓝绿发布、多机房   |

一般情况下，不同服务应该就近调用，本地服务优先

这样，请求的延迟会更低，吞吐量会更高，请求丢包/抖动的概率会更低

nacos 的就近访问会通过负载均衡实现

服务提供者配置

```yaml
# application.yml (Provider)
spring:
  application:
    name: order-service
  cloud:
    nacos:
      discovery:
        cluster-name: shanghai-idc   # 机房/集群名
        weight: 2                    # 本地权重更高（可选）
        metadata:
          region: cn-sh
          az: sh-a
```

消费者配置

```yaml
# application.yml (Consumer)
spring:
  application:
    name: web-frontend
  cloud:
    nacos:
      discovery:
        server-addr: 127.0.0.1:8848
        cluster-name: shanghai-idc    # 本地优先
```

二者配置了相同的 `cluster-name`，这样负载均衡会认为它们在同一个机房，优先挑选同 `cluster-name` 的服务

还有其他方法，用到再学

#### Nacos 命名空间

**Namespace** 是 Nacos 的**最顶级隔离单位**。每个 **Namespace** 下可以有独立的 **配置管理** 和 **服务注册信息**。它们之间 **互相隔离**，不同 Namespace 下的服务和配置，默认互相不可见

在 Nacos 配置中心里，配置的层级结构是：

```markdown
Namespace -> Group -> DataId
```

- **Namespace**：最顶层隔离
- **Group**：命名空间内部的二级分类（默认 DEFAULT_GROUP）
- **DataId**：具体的配置项名称（比如 application.yaml）

在服务注册发现里：

- 一个服务属于某个 **Namespace** 和某个 **Group**。
- 消费者只能发现同 Namespace 下的服务。

在 Spring Boot 配置中可以指定 Namespace

配置中心

```yaml
spring:
  cloud:
    nacos:
      config:
        server-addr: 127.0.0.1:8848
        namespace: 7e6c6d40-xxxx-xxxx-bf3b-8d64e39b4f12  # 指定命名空间ID
```

服务注册发现

```yaml
spring:
  cloud:
    nacos:
      discovery:
        server-addr: 127.0.0.1:8848
        namespace: 7e6c6d40-xxxx-xxxx-bf3b-8d64e39b4f12
```

这样该应用注册的服务、拉取的配置，就会在这个命名空间下。

接下来讲以下**配置中心**

#### 配置中心

在分布式微服务架构中，服务数量剧增，如果还像是对待单体应用配置一样手动去实现配置信息的修改或数据的迁移等，效率是很低的，而且手动操作配置也极有可能出现错误的情况。

复杂的业务对应大量的配置项，对集群部署的应用配置进行修改时需要修改每个节点上的应用配置，在这种背景下，中心化的配置服务即配置中心应运而生。配置中心就是一种统一管理各种应用配置的基础服务组件，配置中心可以把业务开发者从复杂以及繁琐的配置中解脱出来，只需专注于业务代码本身，从而能够显著提升开发以及运维效率。同时将配置和发布包解藕也进一步提升发布的成功率，并为运维的细力度管控、应急处理等提供强有力的支持。

一个服务如果启用了 nacos 配置中心，在项目启动时会先拉取 nacos 中管理的配置，然后与本地的配置文件 `application.yml` 中的配置合并，最后作为项目最终的运行配置

- 没有nacos管理配置文件的情况下的项目启动流程：

  ```bash
  启动项目 ---> 读取本地 aplication.yml ---> 创建 spring 容器 ---> 加载 Bean
  ```

- 使用nacos管理配置时项目的启动流程：

  ```bash
  启动项目 ---> 读取 nacos 中配置文件 ---> 读取本地 aplication.yml ---> 创建 spring 容器 ---> 加载 Bean
  ```

> 在Spring Cloud 2022.x之前项目启动的时候需要提前知道 nacos 的环境信息，而 `application.yml` 在读取 nacos 配置后才会读取，所以无法把 nacos 的相关信息配置在 `application.yml` 中，此时我们可以使用 `bootstrap.yml` 文件。`bootstrap.yml` 是一个引导文件，优先级高于 `application.yml`，它会在 `application.yml` 之前被读取
>
> 在Spring Cloud 2022.x之后，弃用 `bootstrap.yml`，直接将 nacos 相关配置写在 `application.yml` 中即可

想要服务能够拉取 nacos 配置中心的配置，需要引入 nacos 配置管理依赖

```xml
<!--nacos配置管理依赖-->
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
</dependency>
```

```yaml
spring:
  application:
    name: userservice # 服务名称
  profiles:
    active: dev #开发环境，这里是dev 
  cloud:
    nacos:
      server-addr: localhost:8848 # Nacos地址
      config:
        file-extension: yaml # 文件后缀名
```

##### 配置命名规则

在 Nacos 配置中心里，每个配置由 **三元组** 唯一标识：

```markdown
Namespace + Group + DataId
```

- **Namespace**：命名空间，用来区分环境（dev/test/prod）或租户
- **Group**：分组，用来区分业务线，默认 `DEFAULT_GROUP`
- **DataId**：配置文件名，最关键的部分

##### DataId 的命名规则

Spring Cloud Alibaba 默认规则：

```markdown
DataId = ${spring.application.name}-${spring.profiles.active}.${file-extension}
```

- `${spring.application.name}` -> 服务名
- `${spring.profiles.active}` -> 当前激活环境（dev/test/prod）
- `${file-extension}` -> 配置文件后缀（yaml / properties）

举个例子

服务 `userservice`，运行在 **dev** 环境，用 **yaml**：

```markdown
DataId = userservice-dev.yaml
```

服务 `orderservice`，运行在 **prod** 环境，用 **properties**：

```
DataId = orderservice-prod.properties
```

如果没有 `spring.profiles.active`，默认 DataId 就是：

```
userservice.yaml
```

##### Group 的命名规则

默认值：`DEFAULT_GROUP`

一般用于 **业务隔离**：

`USER_GROUP`、`ORDER_GROUP`、`PAY_GROUP`

- 在大公司里，Group 会和业务线、部门对应。

##### Namespace 的命名规则

默认值：`public`

常用来 **区分环境**：

- `dev` -> 开发环境
- `test` -> 测试环境
- `prod` -> 生产环境

这样可以避免不同环境的配置相互影响。

##### 配置更新与拉取方式

Nacos 的配置加载和更新分 **启动时拉取** 和 **运行时监听更新** 两部分。

##### 启动时拉取

服务启动时会根据配置去 Nacos 拉取 DataId 对应的文件，流程：

```markdown
启动 -> 读取 application.yml/bootstrap.yml -> 获取 Nacos 地址 -> 拉取对应 DataId 配置 -> 合并到本地配置 -> Spring 容器启动
```

示例配置：

```yaml
spring:
  application:
    name: userservice
  profiles:
    active: dev
  cloud:
    nacos:
      config:
        server-addr: 127.0.0.1:8848
        file-extension: yaml
```

启动后，会去 Nacos 拉取：

```markdown
DataId = userservice-dev.yaml
```

#### 运行时配置热更新

默认情况下，修改了 nacos 配置中心的配置，微服务的配置不会随之更新的，需要重启微服务才能读到新配置。

我们通过 @Value 和 @ConfigurationProperties 来读取配置时，实现热更新的方式不同。

- 如果通过 @Value 来读取配置，此时需要在使用 @Value 注入的变量所在类上添加 @RefreshScope

  - @RefreshScope 会让该 Bean 重新注入最新配置，没加它的话就需要重启服务

- 通过 @ConfigurationProperties 来读取配置时，无需其他操作，会自动绑定相关配置

  ```java
  @Component
  @ConfigurationProperties(prefix = "app")
  public class AppProperties {
   private String name;
   private String version;
   private String author;
  
   // 一定要有 getter/setter，才能完成绑定
   // Lombok 的 @Data/@Getter/@Setter 也可以
  }
  ```

  ```yaml
  app:
  name: engineer-system
  version: 1.0.0
  author: hj
  ```

  > @ConfrgurationProperties注解的作用是将配置文件里的属性批量注入到一个javabean中

##### 接下来看一下配置中心常见的更新策略，以及 nacos 实际使用的策略

在分布式配置中心的实现中，常见的更新策略主要有三类：

**定时轮询（Polling）**

- 客户端每隔固定时间（比如 30s/60s）去配置中心拉取一次配置。
- **优点**：实现简单，容错性高。
- **缺点**：实时性差，频繁请求会增加服务器压力。

早期的配置管理工具或简单脚本常用这种方式。

**服务端推送（Push）**

- 配置中心主动把变更推送给客户端（通常基于长连接、WebSocket、Server-Sent Events）。
- **优点**：实时性强（配置一变更立即推送）。
- **缺点**：实现复杂，需要维持大量长连接，服务端压力大。

常见于消息中间件、事件通知系统。

**长轮询（Long Polling）**

- 客户端发起一个 HTTP 请求到服务端，如果配置没有变化，服务端会 hold 住连接（比如 30s）。
- 如果配置变化，立即返回结果；如果 30s 到期还没变化，就返回空，客户端立刻再发起下一次请求。
- **优点**：兼顾实时性和实现成本；服务端不需要维持大量长连接（复用 HTTP 请求）。
- **缺点**：会有少量的请求空转，但总体性能可控。

这是 **大多数配置中心采用的主流方案**。

Nacos 使用的就是 **长轮询（Long Polling）策略**，具体流程如下：

1. **客户端发起长轮询请求**
   - 调用 Nacos 的 `/v1/cs/configs/listener` 接口，带上本地已知的配置 MD5。
2. **服务端比较 MD5**
   - 如果配置没变化 -> 服务端阻塞请求，最多等待 30s。
   - 如果配置有变化 -> 立即返回最新版本信息。
3. **客户端处理响应**
   - 如果检测到变化 -> 再调用 `/v1/cs/configs` 拉取最新配置。
   - 如果 30s 超时无变化 -> 客户端立即发起新的长轮询。
4. **Spring 环境刷新**
   - 最新配置加载到 **Spring Environment**，触发 `@RefreshScope` 或 `@ConfigurationProperties` 的 Bean 自动更新。

长轮询 **比轮询更实时**，不必等固定周期才能感知变化。**比推送更轻量**，不需要服务端维护海量长连接（WebSocket），只需处理短时挂起的 HTTP 请求。**兼顾扩展性和性能**，单机可支撑数十万客户端连接，延迟一般 <1 秒。
