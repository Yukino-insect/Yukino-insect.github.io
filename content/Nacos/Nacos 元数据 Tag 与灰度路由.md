+++
date = '2026-08-21T20:20:00+08:00'
draft = false
title = 'Nacos 元数据 Tag 与灰度路由'
+++

Nacos 中常说的 `tag`，本质上不是一个特殊协议能力，而是服务实例 `metadata` 里的一个普通字段。它常用于灰度发布、环境标记、版本路由和定向流量。

这件事最容易被误解成“前端拿到 Nacos 的 tag，就能直接访问我的后端实例”。严格说，这不对。前端通常只是把某个路由意图传给网关或后端；真正根据 `tag` 筛选服务实例的，是后端负载均衡器、网关或服务治理组件。

## 一、Tag 是什么

假设 `order-service` 有三个实例：

```text
order-service
  -> 10.0.0.11:8080 metadata={tag=prod, version=v1}
  -> 10.0.0.12:8080 metadata={tag=prod, version=v1}
  -> 10.0.0.13:8080 metadata={tag=gray, version=v2}
```

这里的 `tag=gray` 只是实例元数据中的一项。它本身不会自动改变流量，必须有调用侧规则去读取它。

服务提供者可以这样注册元数据：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        metadata:
          tag: gray
          version: v2
```

注册后，在 Nacos 控制台的实例详情里可以看到 metadata。

## 二、Tag 能做什么

`tag` 常见用途包括：

- **灰度发布**：让一部分用户访问新版本实例。
- **定向联调**：让测试流量访问某个开发实例。
- **多版本路由**：按 `version=v1`、`version=v2` 选择实例。
- **区域路由**：配合 `region`、`az`、`cluster-name` 做就近访问。

例如灰度发布：

| 用户类型 | 路由目标 |
| -------- | -------- |
| 普通用户 | `tag=prod` |
| 内测用户 | `tag=gray` |
| 指定测试账号 | `tag=dev-user-a` |

但这些规则必须由网关、后端或负载均衡组件执行。Nacos 只负责保存实例及其 metadata，并把服务实例列表提供给客户端。

## 三、真实调用链路

如果前端请求里带了一个 tag，真实链路通常是：

```text
1. 前端请求固定入口
   GET /api/orders
   X-Env-Tag: gray

2. 网关或后端读取 Header
   tag = gray

3. 服务消费者查询 order-service 实例列表
   从 Nacos 获取多个实例

4. 负载均衡规则过滤实例
   只保留 metadata.tag = gray 的实例

5. 请求转发到被选中的后端实例
```

也就是说：

```text
前端
  -> 网关 / 后端入口
    -> 负载均衡器按 tag 筛选实例
      -> 目标服务实例
```

前端并没有直接访问 Nacos，也没有直接选择 IP。它最多只是提供了一个参与路由计算的条件。

## 四、为什么看起来像前端精确访问了实例

如果系统中只有一个实例满足 `tag=gray`，那么每次携带 `X-Env-Tag: gray` 的请求都会落到这个实例上。

这会造成一种错觉：

```text
前端拿到 tag -> 精确访问我的服务
```

更准确的表述应该是：

```text
前端携带 tag -> 后端按 tag 过滤实例 -> 过滤后只剩我的服务 -> 请求落到我的服务
```

“精确”的来源不是前端能力，而是后端路由规则足够确定。

## 五、后端如何筛选实例

伪代码如下：

```java
String tag = request.getHeader("X-Env-Tag");

List<ServiceInstance> matched = instances.stream()
        .filter(instance -> tag.equals(instance.getMetadata().get("tag")))
        .toList();
```

实际项目里还要考虑兜底逻辑：

```java
if (matched.isEmpty()) {
    return chooseFromProdInstances(instances);
}

return chooseByWeight(matched);
```

否则一旦前端传了不存在的 tag，请求就可能直接失败。

## 六、不要让前端决定生产路由

让前端传 tag 在联调时很方便，但长期用于生产灰度通常不合适。

原因有三个。

### 1. Tag 不是安全边界

Header 和参数都可以被用户修改：

```http
GET /api/orders
X-Env-Tag: internal
```

如果后端完全信任前端传入的 tag，用户就可能绕过灰度规则，甚至访问本不该访问的内部实例。

### 2. 会破坏流量治理

灰度发布通常需要控制比例：

```text
95% -> prod
5%  -> gray
```

如果前端可以直接指定 `gray`，比例控制就失效了。配置中心里的灰度比例、用户白名单、权重策略都会被绕开。

### 3. 泄露部署细节

前端不应该知道：

- 有哪些部署环境。
- 有哪些实例标签。
- 哪些服务正在灰度。
- 哪些版本正在联调。

这些信息属于后端治理细节。前端知道得越多，耦合越深，也越难改。

## 七、推荐做法

生产环境更推荐由网关或后端计算路由标签。

常见决策来源如下：

| 决策来源 | 示例 |
| -------- | ---- |
| 用户 ID | 对用户 ID 做 Hash，命中固定灰度比例 |
| 用户白名单 | 内部员工、测试账号、指定租户 |
| Token 信息 | JWT claim 中的租户、角色、渠道 |
| 配置中心 | 动态调整灰度比例和开关 |
| 请求来源 | 内网 IP、办公网、特定渠道 |

网关自动打标签：

```java
if (grayRule.matches(user)) {
    request.addHeader("X-Route-Tag", "gray");
} else {
    request.addHeader("X-Route-Tag", "prod");
}
```

然后服务调用侧只信任网关生成的内部 Header，而不是直接信任浏览器传来的 Header。

更稳妥的做法是：外部请求进网关后，先清理用户可伪造的路由 Header，再由网关根据规则重新写入内部 Header。

## 八、Tag、Group、Namespace 的区别

这几个概念不要混用。

| 概念 | 粒度 | 推荐用途 |
| ---- | ---- | -------- |
| Namespace | 最大 | 环境、租户隔离 |
| Group | 中等 | 业务线、系统分组 |
| Cluster | 中等 | 机房、区域、可用区 |
| Metadata / Tag | 最细 | 实例级路由、灰度、版本 |

推荐关系：

```text
Namespace 用来隔离环境
Group 用来组织业务
Cluster 用来表达部署位置
Metadata 用来承载路由属性
```

不要用 `tag=prod` 代替生产 Namespace。Tag 只是路由属性，不是环境隔离，也不是权限模型。

## 九、灰度发布是不是这个原理

是，但还不完整。

灰度发布的底层通常包含：

- 新旧版本实例同时注册。
- 实例用 metadata 标记版本或灰度状态。
- 网关或负载均衡器根据规则筛选实例。
- 配置中心动态调整灰度开关、比例或白名单。
- 监控和告警观察新版本表现。
- 出问题时快速回滚流量。

Nacos 的 metadata 只是其中一环。真正的灰度发布还需要规则管理、流量控制、监控、回滚和权限治理。

## 十、总结

`tag` 的本质是实例元数据。它可以帮助实现灰度路由，但不会自动生效。

准确表述应该是：

> 前端携带的 tag 不会直接访问 Nacos，也不会直接选择服务实例。它只是一个路由条件。后端、网关或负载均衡组件根据这个条件，从 Nacos 返回的实例列表中筛选符合 metadata 的实例，最终完成定向路由。

联调用前端传 tag 可以，生产环境把路由决策交给前端就不太体面了。系统设计不是考试抢答，谁先说了算并不重要，谁有资格做这个决策才重要。
