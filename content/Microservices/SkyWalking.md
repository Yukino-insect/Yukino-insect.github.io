+++
date = '2025-11-15T20:13:01+08:00'
draft = false
title = 'SkyWalking 链路追踪'
+++

SkyWalking 是 APM 和分布式链路追踪系统，用来观察微服务调用链、服务拓扑、接口耗时、错误率、实例状态和日志关联。它适合用在服务数量较多、调用链较长、仅靠单机日志已经难以排障的系统里。

它的核心价值是回答几个问题：

- 一次请求经过了哪些服务。
- 哪个服务或接口最慢。
- 错误发生在哪一跳。
- 服务之间的依赖关系是什么。
- 日志、指标和 Trace 能不能通过 traceId 关联起来。

## 核心组件

SkyWalking 通常由四部分组成：

| 组件 | 作用 |
| --- | --- |
| Agent | 部署在应用侧，采集调用链、指标和日志上下文 |
| OAP | 后端分析服务，接收、聚合、分析和查询遥测数据 |
| Storage | 存储数据，例如 Elasticsearch、H2、MySQL、TiDB 等 |
| UI | Web 控制台，用于查看拓扑、Trace、指标和告警 |

常见链路如下：

```text
Java 服务
  -> SkyWalking Agent
  -> OAP Server
  -> Storage
  -> SkyWalking UI
```

Agent 通过字节码增强采集数据，对业务代码侵入较低。OAP 接收数据后进行分析、聚合和存储，UI 负责展示查询结果。

## Agent 接入

Java 服务通常通过 `-javaagent` 参数接入：

```bash
java \
  -javaagent:D:\SoftWare\Tools\SkyWalking\skywalking-agent\skywalking-agent.jar \
  -Dskywalking.agent.service_name=order-service \
  -Dskywalking.collector.backend_service=127.0.0.1:11800 \
  -jar order-service.jar
```

参数说明：

- `-javaagent`：指定 SkyWalking Agent 的 jar 路径。
- `skywalking.agent.service_name`：服务在 SkyWalking 中显示的名称，通常使用 `spring.application.name`。
- `skywalking.collector.backend_service`：OAP gRPC 地址，默认端口常见为 `11800`。

Windows 本地路径中尽量不要包含中文和空格。部署到 Linux 或容器时，建议把 Agent 放在固定目录，例如 `/opt/skywalking/agent/`。

## Spring Boot 接入建议

本地开发可以直接在启动参数里添加 `-javaagent`。生产环境更常见的做法是通过启动脚本、Docker 镜像或 Kubernetes 注入 Agent。

Docker 示例：

```dockerfile
FROM eclipse-temurin:17-jre

COPY app.jar /app/app.jar
COPY skywalking-agent /opt/skywalking-agent

ENTRYPOINT ["java", \
  "-javaagent:/opt/skywalking-agent/skywalking-agent.jar", \
  "-Dskywalking.agent.service_name=order-service", \
  "-Dskywalking.collector.backend_service=skywalking-oap:11800", \
  "-jar", "/app/app.jar"]
```

Kubernetes 环境中，也可以通过 init container 或统一基础镜像注入 Agent，避免每个业务服务重复维护同样的接入逻辑。

## Trace、Metric 与 Log

SkyWalking 不只看 Trace。

### Trace

Trace 表示一次请求的完整调用路径。例如：

```text
gateway -> order-service -> inventory-service -> mysql
```

每一段调用是一个 span，span 上会记录耗时、状态、组件类型和异常信息。

### Metric

Metric 用于聚合观察，例如服务吞吐、响应时间、错误率、实例健康状态。它适合看趋势，而不是单次请求细节。

### Log

日志可以通过 traceId 和链路关联。排查问题时，先从 Trace 找到异常 span，再跳到对应服务日志，会比全局搜索关键词可靠得多。

## 日志关联

应用日志需要输出 traceId。常见做法是把 traceId 放进 MDC，然后在日志格式中打印。

Logback 示例：

```xml
<pattern>
  %d{yyyy-MM-dd HH:mm:ss.SSS} %-5level [%thread] [%X{traceId}] %logger{36} - %msg%n
</pattern>
```

实际字段名要和项目使用的链路追踪组件保持一致。SkyWalking Agent 会在支持的框架中注入上下文，但日志框架配置仍需要自己确认。

## 存储选择

开发和演示环境可以使用 H2，但生产环境不能依赖它。生产更常见的是 Elasticsearch、OpenSearch、MySQL、TiDB 或其他受支持存储。

选择存储时要考虑：

- Trace 保留周期。
- 每日请求量和 span 数量。
- 查询性能。
- 磁盘成本。
- 索引或表清理策略。
- 高可用部署。

链路数据量会随服务调用层级快速增长。不要等磁盘满了才讨论保留周期，那时通常已经不怎么体面了。

## 常见排障路径

一次接口变慢时，可以按这个顺序看：

1. 在 UI 中按接口名或 traceId 查询 Trace。
2. 找到耗时最长的 span。
3. 判断慢在应用逻辑、HTTP 调用、数据库还是消息中间件。
4. 跳转到对应实例日志查看异常和关键参数。
5. 对比同一时间段的服务指标，例如错误率、P95、线程池和连接池。

如果是灰度发布期间的问题，应同时按版本、实例 metadata 或 Header 标记过滤，否则新旧版本数据混在一起会误导判断。

## 使用注意

1. 服务名要稳定。频繁变化会导致拓扑和历史数据割裂。
2. Agent 版本要统一管理，避免不同服务采集行为不一致。
3. 采样率要按流量调整，高流量系统全量采样成本很高。
4. traceId 要进入日志，否则 Trace 和 Log 很难串起来。
5. 不要把 APM 当成业务审计系统，它关注调用链，不负责保存完整业务证据。

## 总结

SkyWalking 的核心是把分散在各服务里的调用、耗时、错误和日志关联起来。它不能替你修复慢 SQL、超时和异常，但能让你更快找到它们。对微服务来说，这已经是很大的帮助了。
