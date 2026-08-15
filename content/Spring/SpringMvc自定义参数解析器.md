+++
date = '2025-08-04T21:09:13+08:00'
draft = false
title = 'Spring MVC 自定义参数解析器'
+++

Spring MVC 的参数解析器用于把 HTTP 请求中的信息转换成 Controller 方法参数。常见的 `@RequestParam`、`@PathVariable`、`@RequestBody` 等能力，背后都依赖参数解析机制。

## 一、核心接口

自定义参数解析器需要实现 `HandlerMethodArgumentResolver`：

```java
public interface HandlerMethodArgumentResolver {
    boolean supportsParameter(MethodParameter parameter);

    Object resolveArgument(
        MethodParameter parameter,
        ModelAndViewContainer mavContainer,
        NativeWebRequest webRequest,
        WebDataBinderFactory binderFactory
    ) throws Exception;
}
```

`supportsParameter` 用来判断当前解析器是否支持某个方法参数。`resolveArgument` 用来真正解析参数值。

## 二、典型场景

自定义参数解析器常用于：

1. 自动注入当前登录用户。
2. 从请求头中解析租户 ID。
3. 注入当前门店、组织、数据权限上下文。
4. 统一解析自定义注解标记的参数。

例如 Controller 中希望直接写：

```java
public Result<?> detail(@CurrentUser LoginUser user) {
    return Result.ok(user);
}
```

就可以通过自定义解析器读取 token 或上下文，并把 `LoginUser` 注入到方法参数中。

## 三、实现思路

先定义注解：

```java
@Target(ElementType.PARAMETER)
@Retention(RetentionPolicy.RUNTIME)
public @interface CurrentUser {
}
```

再实现解析器：

```java
public class CurrentUserArgumentResolver implements HandlerMethodArgumentResolver {
    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return parameter.hasParameterAnnotation(CurrentUser.class)
            && parameter.getParameterType().equals(LoginUser.class);
    }

    @Override
    public Object resolveArgument(
            MethodParameter parameter,
            ModelAndViewContainer mavContainer,
            NativeWebRequest webRequest,
            WebDataBinderFactory binderFactory) {
        return UserContext.getCurrentUser();
    }
}
```

最后注册到 Spring MVC：

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(new CurrentUserArgumentResolver());
    }
}
```

## 四、注意点

参数解析器只负责参数解析，不应承载复杂业务逻辑。鉴权、权限校验、数据权限过滤等逻辑应放在过滤器、拦截器或业务服务中。

另外，解析器中依赖的上下文要注意线程安全。如果上下文基于 `ThreadLocal`，请求结束后必须清理。
