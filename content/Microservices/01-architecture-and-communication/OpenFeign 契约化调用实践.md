+++
date = '2026-01-26T20:03:05+08:00'
draft = false
title = 'OpenFeign 契约化调用实践'
+++

微服务之间用 OpenFeign 调用时，最容易出现的问题不是“调不通”，而是 Provider 和 Consumer 对接口的理解慢慢漂移：路径改了、参数名改了、DTO 字段改了，一边能编译，另一边上线后才炸。

比较稳的做法是把接口契约下沉到独立的 `xxx-api` 模块：DTO、请求对象、响应对象、Feign 接口都放在这里。Provider 实现这个接口，Consumer 也依赖同一个接口。这样接口变化会在编译期暴露，而不是交给联调阶段碰运气。

## 推荐模块结构

以 `infra-service` 被 `system-service` 调用为例：

```text
iwater-module-infra-api
  └── InfraUserApi.java
  └── UserRespDTO.java

iwater-module-infra-biz
  └── InfraUserApiImpl.java
  └── InfraUserService.java

iwater-module-system-biz
  └── UserFacade.java
  └── DemoController.java
```

`infra-api` 是契约模块，Provider 和 Consumer 都可以依赖它。`infra-biz` 提供真实 HTTP 实现，`system-biz` 通过 Feign 调用。

## API 模块

契约接口上声明服务名、路径和方法签名：

```java
@FeignClient(
    name = "iwater-module-infra",
    path = "/admin-api/infra/user",
    contextId = "infraUserApi"
)
public interface InfraUserApi {

    @GetMapping("/{id}")
    CommonResult<UserRespDTO> getUser(@PathVariable("id") Long id);
}
```

DTO 只表达跨服务调用需要的数据，不要直接暴露数据库实体：

```java
public class UserRespDTO {

    private Long id;
    private String username;
    private String nickname;

    // getter/setter
}
```

契约模块应尽量轻。不要把 Mapper、Entity、复杂业务 Service 放进去，否则 Consumer 会被 Provider 的内部实现污染。

## Provider 实现

Provider 端实现同一个接口：

```java
@RestController
@Validated
public class InfraUserApiImpl implements InfraUserApi {

    private final InfraUserService infraUserService;

    public InfraUserApiImpl(InfraUserService infraUserService) {
        this.infraUserService = infraUserService;
    }

    @Override
    public CommonResult<UserRespDTO> getUser(Long id) {
        return CommonResult.success(infraUserService.getUser(id));
    }
}
```

`Impl` 不应该承载复杂业务逻辑。它只负责 HTTP 入口、参数校验、调用应用服务并转换返回结果。业务规则放在 Service 层，测试和复用都会清楚得多。

## Consumer 调用

Consumer 端启用 Feign 扫描：

```java
@EnableFeignClients(basePackages = "cn.iwater.module.infra.api")
@SpringBootApplication
public class SystemApplication {
}
```

业务代码中建议封装一层 Facade，不要在 Controller 里直接调远程服务：

```java
@Service
public class UserFacade {

    private final InfraUserApi infraUserApi;

    public UserFacade(InfraUserApi infraUserApi) {
        this.infraUserApi = infraUserApi;
    }

    public UserRespDTO getUserOrThrow(Long id) {
        CommonResult<UserRespDTO> result = infraUserApi.getUser(id);

        if (result == null || !result.isSuccess()) {
            String message = result == null ? "empty response" : result.getMsg();
            throw new RemoteServiceException("调用 infra 用户接口失败：" + message);
        }

        return result.getData();
    }
}
```

Facade 的价值是把远程调用异常、空响应、业务错误码、降级语义统一封装。Controller 只关心当前接口要返回什么。

## Header 透传

常见需要透传的 Header：

- `Authorization`：用户身份或访问令牌。
- `X-Trace-Id`：链路追踪 ID。
- `X-Tenant-Id`：租户 ID。
- `X-Request-Id`：请求唯一标识。

```java
@Configuration
public class FeignCommonConfig {

    @Bean
    public RequestInterceptor requestInterceptor() {
        return template -> {
            ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();

            if (attrs == null) {
                return;
            }

            HttpServletRequest request = attrs.getRequest();
            copy(request, template, "Authorization");
            copy(request, template, "X-Trace-Id");
            copy(request, template, "X-Tenant-Id");
        };
    }

    private void copy(HttpServletRequest request, RequestTemplate template, String name) {
        String value = request.getHeader(name);
        if (value != null && !value.isBlank()) {
            template.header(name, value);
        }
    }
}
```

灰度、内部权限、路由标签这类 Header 要特别小心。它们最好由网关或可信服务写入，不要直接信任客户端传来的值。

## 超时与日志

```yaml
spring:
  cloud:
    openfeign:
      client:
        config:
          default:
            connectTimeout: 2000
            readTimeout: 5000
            loggerLevel: basic
```

生产环境必须配超时。`connectTimeout` 控制建立连接的等待时间，`readTimeout` 控制等待响应的时间。

日志建议默认 `basic`，需要排查参数和响应体时再临时打开 `full`。涉及 token、手机号、身份证号、密钥的字段必须脱敏。

## 异常转换

Feign 默认遇到 4xx、5xx 会抛出 `FeignException`。大型项目里最好统一转换成业务侧能识别的异常。

```java
@Bean
public ErrorDecoder errorDecoder() {
    return (methodKey, response) -> new RemoteServiceException(
        "Feign 调用失败: " + methodKey + ", http=" + response.status()
    );
}
```

这样上层可以按异常类型做告警、降级或错误码映射，而不是到处捕获框架异常。

## 降级与熔断

如果调用的是非核心依赖，可以使用 `fallbackFactory` 返回可接受的降级结果：

```java
@Component
public class InfraUserApiFallbackFactory implements FallbackFactory<InfraUserApi> {

    @Override
    public InfraUserApi create(Throwable cause) {
        return id -> CommonResult.error(503, "用户服务暂时不可用");
    }
}
```

降级要符合业务语义。比如“推荐列表为空”通常可以接受，但“余额服务不可用时默认余额充足”就很荒唐。可靠性不是假装成功。

## 契约接口的取舍

把 Mapping 注解放在接口上，Provider 实现接口，是很多团队喜欢的做法。优点是契约集中、Consumer 复用方便、路径和参数不容易写散。

它也有边界：

- 契约模块只放跨服务公开模型，不放内部领域对象。
- 接口不要膨胀成万能入口，应按业务能力拆分。
- 返回值不要泄露 Provider 内部错误细节。
- 版本升级要兼容老 Consumer，避免一次改动要求所有服务同时上线。

## 总结

`PermissionApiImpl implements PermissionApi` 这类写法的本质不是为了让 Feign 能调用，而是为了让 Provider 和 Consumer 共享同一份接口契约。

契约模块、Facade 封装、Header 透传、超时日志、异常转换、降级熔断，这些配套放在一起，OpenFeign 调用才算从“能用”走到“适合长期维护”。
