+++
date = '2026-02-19T21:34:14+08:00'
draft = false
title = 'nacos的tag的作用是什么'
+++

在 **Nacos** 里，**Tag（标签）本质是服务实例的分组标识**，用于做流量隔离 / 灰度发布 / 分环境路由。Tag = 给服务实例打一个标记，然后让流量按规则只访问某些标记的实例。

### 一、Tag 解决什么问题？

假设有一个服务 `order-service`

现在部署了：

- 3 台正式版本
- 1 台灰度版本

如果没有 tag：

所有流量都会随机打到 4 台机器。

但如果加 tag：

| 实例 | tag  |
| ---- | ---- |
| A    | prod |
| B    | prod |
| C    | prod |
| D    | gray |

就可以做到：

- 普通用户 -> 只访问 prod
- 内测用户 -> 访问 gray

### 二、Tag 在 Nacos 中怎么体现？

在 Nacos 里：

Tag 实际上是服务实例的 metadata（元数据）。

注册服务时：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        metadata:
          tag: gray
```

注册后：

Nacos 控制台 -> 服务列表 -> 实例详情

可以看到：

```yaml
metadata:
  tag=gray
```

### 三、Tag 怎么被使用？

光打 tag 没用。

必须配合：

- Ribbon
- Spring Cloud LoadBalancer
- 或服务网关

通过负载均衡规则读取 metadata。

例如：

```java
if (instance.getMetadata().get("tag").equals("gray")) {
    // 只选灰度实例
}
```

### 四、常见使用场景

#### 灰度发布

只让某些请求访问新版本。

#### 多环境隔离

同一个 Nacos 注册中心里：

- dev
- test
- prod

通过 tag 控制访问。

#### 多机房流量控制

例如：

| 实例     | tag  |
| -------- | ---- |
| 北京机房 | bj   |
| 上海机房 | sh   |

可以做就近访问。

### 五、Tag vs Group 区别

很多人会混淆。

| 概念      | 作用                 |
| --------- | -------------------- |
| Group     | 服务分组（逻辑隔离） |
| Namespace | 环境隔离（物理隔离） |
| Tag       | 实例级别流量控制     |

简单理解：

Namespace > Group > Service > Instance > Tag

Tag 是最细粒度。

### 六、底层本质

在 Nacos 中，Tag 只是 `Instance.metadata 中的一个 key` 没有特殊结构。它不自动生效。必须由：

- 客户端负载均衡器
- 网关
- 或自定义规则

去解析。
