+++
date = '2025-11-15T20:13:01+08:00'
draft = false
title = 'SkyWalking'
+++

**APM** 应用程序管理系统

**分布式调用链标准：OpenTracing**[](https://blog.csdn.net/wuzhiwei549/article/details/108856398)

[](https://blog.csdn.net/weixin_39603265/article/details/111581334?spm=1001.2101.3001.6661.1&utm_medium=distribute.pc_relevant_t0.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7EPaidSort-1-111581334-blog-108856398.235%5Ev43%5Epc_blog_bottom_relevance_base8&depth_1-utm_source=distribute.pc_relevant_t0.none-task-blog-2%7Edefault%7EBlogCommendFromBaidu%7EPaidSort-1-111581334-blog-108856398.235%5Ev43%5Epc_blog_bottom_relevance_base8&utm_relevant_index=1)

## 概念

skywalking分为服务端和客户端，服务端负责收集日志数据并且展示

![](https://img-blog.csdnimg.cn/18613f4fdee0487caf0b3f01ed728209.png)

上述架构图中主要分为四个部分，如下：

- 最上面的 `Tracing`：负责从应用中，收集链路信息，发送给 `SkyWalking OAP` 服务器，目前支持 `SkyWalking、Zikpin、Jaeger` 等提供的 Tracing 数据信息。一般采用的是 `SkyWalking Agent` 收集 `SkyWalking Tracing` 数据，传递给 `SkyWalking OAP` 服务器。
- 中间的`OAP`：负责接收 `Agent` 发送的 `Tracing` 和 `Metric` 的数据信息，然后进行分析(`Analysis Core`) ，存储到外部存储器( `Storage` )，最终提供查询( `Query` )功能。
- 左面的`UI`：负责提供`web`控制台，查看链路，查看各种指标，性能等等。
- 右面`Storage`：负责数据的存储，支持多种存储类型。目前支持 ES、MySQL、Sharding Sphere、TiDB、H2 多种存储器。

看了架构图之后，思路很清晰了，`Agent`负责收集日志传输数据，通过`GRPC`的方式传递给`OAP`进行分析并且存储到数据库中，最终通过UI界面将分析的统计报表、服务依赖、拓扑关系图展示出来。

从逻辑上看，skywalking分为四个部分：探针，平台后端，存储和UI。

探针：收集数据并重新格式化以符合SkyWalking的要求（不同的探针支持不同的来源）。
平台后端：支持数据聚合，分析和流处理，涵盖跟踪，指标和日志。
存储：设备通过开放/可插入的界面存储SkyWalking数据。您可以选择现有的实现，例如ElasticSearch，H2，MySQL，TiDB，InfluxDB，或者实现自己的实现。
UI：是一个高度可定制的基于Web的界面，允许SkyWalking最终用户可视化和管理SkyWalking数据。
以此实现了收集，分析，聚合和可视化来自本地或者云服务中的数据

## 使用

### skywalking服务端

启动oap服务和UI服务

### 客户端

客户端也就是单个微服务，由于`Skywalking`采用字节码增强技术，因此对于微服务无代码侵入，只要是普通的微服务即可，不需要引入什么依赖。

想要传输数据必须借助`skywalking`提供的`agent`，只需要在启动参数指定即可，命令如下：

```bashell
-javaagent:D:\SoftWare\Tools\SkyWalking\skywalking-agent\skywalking-agent.jar
-Dskywalking.agent.service_name=skywalking-product-service
-Dskywalking.collector.backend_service=127.0.0.1:11800
```

上述命令解析如下：

- `-javaagent`：指定`skywalking`中的`agent`中的`skywalking-agent.jar`的路径
- `-Dskywalking.agent.service_name`：指定在`skywalking`中的服务名称，一般是微服务的`spring.application.name`
- `-Dskywalking.collector.backend_service`：指定`oap`服务绑定的地址，如果是本地，由于`oap`服务默认的端口是`11800`，因此只需要配置为`127.0.0.1:11800`

**注意**：`agent`的`jar`包路径不能包含中文，不能有空格，否则运行不成功。

### 日志监控

### 数据持久化
