+++
date = '2025-10-11T16:50:27+08:00'
draft = false
title = 'URL 设计'
+++

刚学后端时，接口路径很容易写成 `/getUser`、`/saveUser`、`/deleteOrder`。这种写法能跑，但它把“动作”塞进了 URL，后期接口一多，风格就会变得很散。

更稳妥的原则是：**URL 表达资源，HTTP 方法表达动作**。

```text
GET    /api/v1/users          查询用户列表
POST   /api/v1/users          创建用户
GET    /api/v1/users/{id}     查询用户详情
PATCH  /api/v1/users/{id}     部分更新用户
DELETE /api/v1/users/{id}     删除用户
```

## 命名规则

- 路径使用小写字母，不混用大小写。
- 多个单词使用 `-` 分隔，例如 `/alarm-records`。
- 资源名通常使用复数名词，例如 `/users`、`/orders`。
- 不在路径中写 `get`、`save`、`delete` 这类动作。
- 子资源通过路径层级表达从属关系。
- 公共 API 建议带版本号，例如 `/api/v1`。

一个常见结构可以写成：

```text
/{api-prefix}/{version}/{resource}/{resourceId}/{sub-resource}
```

例如：

```text
/api/v1/devices/{deviceId}/alarm-records
/api/v1/users/{userId}/login-logs
/api/v1/orders/{orderId}/items
```

## HTTP 方法语义

| 方法 | 语义 | 示例 |
| --- | --- | --- |
| `GET` | 获取资源 | `GET /api/v1/users` |
| `POST` | 创建资源，或提交复杂动作 | `POST /api/v1/users` |
| `PUT` | 整体替换资源 | `PUT /api/v1/users/{id}` |
| `PATCH` | 部分更新资源 | `PATCH /api/v1/users/{id}` |
| `DELETE` | 删除资源 | `DELETE /api/v1/users/{id}` |

`PUT` 和 `PATCH` 的区别经常被混用。简单理解：`PUT` 更像“用这个对象整体替换原对象”，`PATCH` 更像“只改其中几个字段”。实际项目中如果团队没有严格区分，也至少要在接口文档里保持一致。

## 动作类接口

不是所有接口都能优雅地抽象成 CRUD。比如激活、导出、测试连接、审核通过，这些更像业务动作，可以把动作放到资源后面，用 `POST` 提交。

| 场景 | URL | 方法 |
| --- | --- | --- |
| 激活设备 | `/api/v1/devices/{deviceId}/activate` | `POST` |
| 导出日志 | `/api/v1/logs/export` | `POST` |
| 测试连接 | `/api/v1/connections/test` | `POST` |
| 审核订单 | `/api/v1/orders/{orderId}/approve` | `POST` |

导出接口有时也会用 `GET`，但如果筛选条件很多，或者会触发生成文件、写导出记录，就更适合用 `POST`。

## 查询参数

简单筛选可以放在 query string：

```http
GET /api/v1/alarm-records?deviceId=1&level=high&page=1&pageSize=20
```

复杂查询建议使用 `POST /query`，把条件放进 JSON 请求体：

```http
POST /api/v1/alarm-records/query
Content-Type: application/json
```

```json
{
  "deviceIds": [1, 2, 3],
  "timeRange": {
    "start": "2025-10-01T00:00:00",
    "end": "2025-10-11T23:59:59"
  },
  "levels": ["high", "medium"],
  "sort": {
    "field": "timestamp",
    "order": "desc"
  },
  "page": 1,
  "pageSize": 20
}
```

这里不是说 `POST` 才能查询，而是当查询条件已经复杂到影响可读性、URL 长度、日志展示和网关限制时，用请求体会更清楚。

## API 前缀

实习时遇到过一次接口访问不到的问题。Controller 路径看起来没错，最后才发现网关只放行带指定前缀的请求。这个经验可以归到 URL 设计里：**接口路径不只由 Controller 决定，还可能叠加网关前缀、应用 context-path、MVC 全局前缀**。

常见前缀来源有三类。

### 网关前缀

微服务网关可能只允许 `/admin-api`、`/app-api` 之类的请求进入后端服务：

```java
@RequiredArgsConstructor
public abstract class ApiRequestFilter extends OncePerRequestFilter {

    protected final WebProperties webProperties;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String apiUri = request.getRequestURI()
                .substring(request.getContextPath().length());

        return !StrUtil.startWithAny(
                apiUri,
                webProperties.getAdminApi().getPrefix(),
                webProperties.getAppApi().getPrefix()
        );
    }
}
```

如果本地请求 `/users` 不通，而线上文档写的是 `/admin-api/users`，问题通常不在 Controller，而在入口层。

### Spring MVC 全局前缀

可以给所有 `@RestController` 统一加前缀：

```java
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void configurePathMatch(PathMatchConfigurer configurer) {
        configurer.addPathPrefix(
                "/api",
                clazz -> clazz.isAnnotationPresent(RestController.class)
        );
    }
}
```

### 应用 context-path

也可以通过配置给整个应用加 context-path：

```yaml
server:
  servlet:
    context-path: /api
```

这三种方式的层级不同。网关前缀属于入口路由，`context-path` 属于 Servlet 应用上下文，`addPathPrefix` 属于 Spring MVC 映射规则。排查接口路径时，要把它们叠加起来看。

## 小结

好的 URL 设计不是为了显得“RESTful”，而是为了让接口在数量变多后依旧可预测。看到路径就知道资源是什么，看到方法就知道动作是什么，看到前缀就知道入口边界在哪里。能做到这一点，接口已经比许多随缘作品体面得多。
