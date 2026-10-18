+++
date = '2025-09-24T22:28:00+08:00'
draft = false
title = 'JWT 登录逻辑'
+++

JWT 登录的核心并不复杂：**登录接口完成身份校验并签发 Token，后续请求携带 Token，过滤器解析 Token 并把认证信息放进 SecurityContext**。

真正容易出错的地方，是把 Spring Security 默认表单登录、JSON 登录、短信登录、JWT 鉴权混在一起讲。它们确实都叫“登录”，但所处位置并不一样。

## 表单登录和 JSON 登录

Spring Security 默认的 `UsernamePasswordAuthenticationFilter` 适合处理表单提交：

- `application/x-www-form-urlencoded`
- `multipart/form-data`

也就是前端提交：

```http
POST /login
Content-Type: application/x-www-form-urlencoded

username=tom&password=123456
```

如果前后端分离项目提交的是 JSON：

```http
POST /login
Content-Type: application/json

{
  "username": "tom",
  "password": "123456"
}
```

默认过滤器不会自动从 JSON 请求体中解析账号密码。常见做法有两种：

- 自定义登录过滤器，读取 JSON 后交给 `AuthenticationManager`。
- 在 Controller 中提供登录接口，手动调用 `AuthenticationManager`。

Controller 写法大致如下：

```java
@PostMapping("/auth/login")
public LoginResponse login(@RequestBody LoginRequest request) {
    Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(
                    request.getUsername(),
                    request.getPassword()
            )
    );

    SecurityContextHolder.getContext().setAuthentication(authentication);

    String token = jwtTokenProvider.createToken(authentication);
    return new LoginResponse(token, "Bearer");
}
```

这里 `AuthenticationManager` 负责校验身份，JWT 工具只负责签发令牌。把职责分开，代码会少很多自作聪明的混乱。

## 短信登录流程

短信登录可以看成另一种身份校验方式。密码登录校验密码，短信登录校验验证码。

典型流程：

```text
1. 前端请求 /auth/sms/send，提交手机号。
2. 后端校验手机号格式和发送频率。
3. 后端生成验证码，写入 Redis，并设置 TTL。
4. 后端调用短信平台发送验证码。
5. 前端请求 /auth/sms/login，提交手机号和验证码。
6. 后端校验验证码，删除验证码。
7. 后端查询或创建用户，签发 JWT。
8. 前端保存 JWT，后续请求放到 Authorization 请求头。
```

验证码存 Redis 比较合适，因为它天然需要过期时间，也属于短期临时状态。

```java
private static final String CODE_KEY = "sms:code:";
private static final String LIMIT_KEY = "sms:limit:";

public void sendCode(String phone) {
    Boolean limited = redis.opsForValue()
            .setIfAbsent(LIMIT_KEY + phone, "1", Duration.ofSeconds(60));

    if (Boolean.FALSE.equals(limited)) {
        throw new BizException("发送过于频繁，请稍后重试");
    }

    String code = String.format("%06d", secureRandom.nextInt(1_000_000));
    redis.opsForValue().set(CODE_KEY + phone, code, Duration.ofMinutes(5));

    smsService.send(phone, code);
}
```

验证码校验成功后要删除，避免同一个验证码重复使用：

```java
public String loginBySms(String phone, String code) {
    String key = CODE_KEY + phone;
    String cachedCode = redis.opsForValue().get(key);

    if (cachedCode == null) {
        throw new BizException("验证码已过期");
    }
    if (!cachedCode.equals(code)) {
        throw new BizException("验证码不正确");
    }

    redis.delete(key);

    User user = userService.findOrCreateByPhone(phone);
    return jwtTokenProvider.createToken(user.getId(), user.getRoles());
}
```

## JWT 签发

JWT 通常包含三部分：

- Header：令牌类型和签名算法。
- Payload：用户标识、角色、过期时间等声明。
- Signature：用密钥对前两部分签名，防止篡改。

签发时一般放这些信息：

| 字段 | 含义 |
| --- | --- |
| `sub` | 用户唯一标识，通常是 userId |
| `iat` | 签发时间 |
| `exp` | 过期时间 |
| `roles` | 角色或权限摘要 |
| `jti` | Token 唯一 ID，可用于黑名单或审计 |

不要把手机号、身份证、密码、密钥等敏感信息放进 JWT。JWT 的 Payload 只是 Base64URL 编码，不是加密。能被前端拿到的东西，就别假装它看不见。

## JWT 鉴权过滤器

登录成功之后，请求一般这样携带 Token：

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

后端通过过滤器解析请求头。如果 Token 有效，就构造认证对象放入 `SecurityContextHolder`。

```java
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider jwtTokenProvider;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain)
            throws ServletException, IOException {

        String authorization = request.getHeader(HttpHeaders.AUTHORIZATION);

        if (StringUtils.hasText(authorization) && authorization.startsWith("Bearer ")) {
            String token = authorization.substring(7);

            try {
                Authentication authentication = jwtTokenProvider.parseAuthentication(token);
                SecurityContextHolder.getContext().setAuthentication(authentication);
            } catch (JwtException e) {
                SecurityContextHolder.clearContext();
            }
        }

        filterChain.doFilter(request, response);
    }
}
```

Spring Security 判断“当前用户是否已登录”，本质就是看当前线程的 `SecurityContext` 中有没有有效的 `Authentication`。

## Security 配置

JWT 项目通常是无状态会话：

```java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session -> session
                    .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            .authorizeHttpRequests(auth -> auth
                    .requestMatchers("/auth/login", "/auth/sms/send", "/auth/sms/login").permitAll()
                    .anyRequest().authenticated()
            )
            .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
            .build();
}
```

如果 JWT 放在 `Authorization` 请求头里，并且后端不依赖 Cookie 维持会话，CSRF 风险会低很多，所以常见配置会关闭 CSRF。但如果 Token 放在 Cookie 里，就不能简单照抄关闭配置。

## 小结

JWT 登录可以拆成两段：登录接口负责“证明你是谁并发令牌”，鉴权过滤器负责“之后每次请求识别你是谁”。短信、密码、第三方登录只是不同的身份校验方式；只要校验成功，后面的 JWT 签发和过滤器鉴权逻辑基本一致。
