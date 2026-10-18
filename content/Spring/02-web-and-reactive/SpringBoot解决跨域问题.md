+++
date = '2025-08-04T20:36:03+08:00'
draft = false
title = 'Spring Boot 跨域配置'
+++

跨域问题的本质不是后端“接口不能访问”，而是浏览器的同源策略限制了前端脚本读取响应。请求可能已经到达服务端，甚至服务端也返回了数据，但浏览器发现响应里缺少合适的 CORS 头，就会把结果拦下来。

所以 CORS 配置要解决的是：**服务端明确告诉浏览器，哪些来源、方法、请求头和凭证可以访问当前资源**。

## 一、什么是同源

浏览器判断同源时看三个部分：

- 协议：`http`、`https`
- 域名：`example.com`、`api.example.com`
- 端口：`8080`、`3000`

只要其中一个不同，就是跨域。

例如：

| 前端页面 | 接口地址 | 是否跨域 |
| --- | --- | --- |
| `http://localhost:3000` | `http://localhost:8080` | 是，端口不同 |
| `https://www.example.com` | `https://api.example.com` | 是，域名不同 |
| `https://example.com` | `http://example.com` | 是，协议不同 |
| `https://example.com` | `https://example.com` | 否 |

跨域限制发生在浏览器环境。Postman、curl、后端服务之间调用通常不受同源策略限制。

## 二、CORS 常见响应头

服务端常见响应头如下：

| 响应头 | 作用 |
| --- | --- |
| `Access-Control-Allow-Origin` | 允许访问的来源 |
| `Access-Control-Allow-Methods` | 允许的 HTTP 方法 |
| `Access-Control-Allow-Headers` | 允许携带的请求头 |
| `Access-Control-Allow-Credentials` | 是否允许携带 Cookie、Authorization 等凭证 |
| `Access-Control-Max-Age` | 预检请求结果缓存时间 |

如果请求带了自定义请求头、非简单方法，或者 `Content-Type` 不是简单类型，浏览器通常会先发起 `OPTIONS` 预检请求。

```text
OPTIONS /api/users
Origin: http://localhost:3000
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type, authorization
```

只有预检通过后，浏览器才会继续发送真实请求。

## 三、全局配置：`WebMvcConfigurer`

Spring MVC 项目中最常用的方式是实现 `WebMvcConfigurer#addCorsMappings`：

```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("http://localhost:3000", "https://www.example.com")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
```

几个配置含义：

- `addMapping`：哪些接口路径启用 CORS。
- `allowedOrigins`：允许哪些前端来源访问。
- `allowedMethods`：允许哪些请求方法。
- `allowedHeaders`：允许前端携带哪些请求头。
- `allowCredentials`：是否允许携带 Cookie、Authorization 等凭证。
- `maxAge`：预检请求缓存秒数。

如果允许携带凭证，`allowedOrigins("*")` 不应该和 `allowCredentials(true)` 一起使用。浏览器也不会接受这种组合。要允许多个来源，就显式列出来源，或者使用 `allowedOriginPatterns`。

```java
registry.addMapping("/api/**")
        .allowedOriginPatterns("https://*.example.com")
        .allowedMethods("*")
        .allowedHeaders("*")
        .allowCredentials(true);
```

## 四、全局配置：`CorsFilter`

如果希望 CORS 在更靠前的 Filter 层处理，可以注册 `CorsFilter`：

```java
@Configuration
public class CorsFilterConfig {

    @Bean
    public CorsFilter corsFilter() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(List.of("http://localhost:3000"));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(true);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", configuration);
        return new CorsFilter(source);
    }
}
```

`WebMvcConfigurer` 作用在 Spring MVC 层，`CorsFilter` 作用在 Servlet Filter 层。普通 MVC 项目用前者通常足够；如果涉及 Spring Security，过滤器顺序就需要额外注意。

## 五、局部配置：`@CrossOrigin`

如果只有少数接口需要跨域，可以在 Controller 或方法上使用 `@CrossOrigin`：

```java
@RestController
@RequestMapping("/api/users")
@CrossOrigin(
        origins = "http://localhost:3000",
        methods = {RequestMethod.GET, RequestMethod.POST},
        allowCredentials = "true"
)
public class UserController {

    @GetMapping
    public List<UserVO> list() {
        return userService.list();
    }
}
```

方法级配置会比类级配置更具体：

```java
@PostMapping
@CrossOrigin(origins = "https://admin.example.com")
public void create(@RequestBody UserCreateRequest request) {
}
```

`@CrossOrigin` 适合局部例外，不适合大型项目到处散落配置。跨域策略本身属于安全边界，最好集中管理。

## 六、和 Spring Security 一起使用

如果项目引入了 Spring Security，要在安全配置中启用 CORS：

```java
@Bean
SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http
            .cors(Customizer.withDefaults())
            .csrf(AbstractHttpConfigurer::disable)
            .authorizeHttpRequests(registry -> registry
                    .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                    .anyRequest().authenticated()
            )
            .build();
}
```

然后提供 `CorsConfigurationSource`：

```java
@Bean
CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration configuration = new CorsConfiguration();
    configuration.setAllowedOrigins(List.of("http://localhost:3000"));
    configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
    configuration.setAllowedHeaders(List.of("*"));
    configuration.setAllowCredentials(true);

    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/api/**", configuration);
    return source;
}
```

如果 Security 没启用 CORS，预检请求可能在进入 Controller 前就被安全过滤器拦截。然后你会去改 Controller，当然没有效果，因为请求根本没走到那里。

## 七、生产环境建议

生产环境不要使用过宽配置：

```java
allowedOrigins("*")
allowedMethods("*")
allowedHeaders("*")
```

更稳妥的做法是：

- 明确列出允许的域名。
- 只开放需要的 HTTP 方法。
- 只开放必要请求头。
- 需要 Cookie 或 Authorization 时才启用 `allowCredentials(true)`。
- 前后端域名固定后，把本地开发域名和生产域名分开配置。

可以用配置文件管理来源：

```yaml
app:
  cors:
    allowed-origins:
      - http://localhost:3000
      - https://www.example.com
```

再绑定成配置类，避免把环境差异写死在 Java 代码里。

## 八、排查清单

遇到跨域报错时，按顺序检查：

1. 浏览器控制台是否显示 CORS 错误，而不是接口 500 或网络错误。
2. 预检 `OPTIONS` 请求是否成功。
3. 响应里是否有 `Access-Control-Allow-Origin`。
4. 前端是否携带了 `Authorization` 或 Cookie。
5. 携带凭证时，后端是否设置了具体来源而不是 `*`。
6. Spring Security 是否拦截了 `OPTIONS`。
7. Nginx、网关、后端是否重复设置了冲突的 CORS 头。

跨域配置最好只在一层完成。Nginx、Gateway、后端 Controller 都配置一遍，看似保险，实际更像制造谜题。

## 九、总结

Spring Boot 中处理跨域常用三种方式：

- 全局 MVC 配置：实现 `WebMvcConfigurer#addCorsMappings`。
- Filter 层配置：注册 `CorsFilter` 或 `CorsConfigurationSource`。
- 局部配置：在 Controller 或方法上使用 `@CrossOrigin`。

普通项目优先使用全局 MVC 配置；引入 Spring Security 后，要确保 Security 过滤器链也启用了 CORS；生产环境要明确来源，不要用过宽策略蒙混过关。浏览器已经替你守门了，后端就不要再把钥匙挂门口。
