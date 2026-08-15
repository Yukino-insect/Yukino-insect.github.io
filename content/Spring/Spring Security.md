+++
date = '2026-02-17T13:04:35+08:00'
draft = false
title = 'Spring Security'
+++

Spring Security 是基于 Spring 生态的用于保护 Java 应用程序的框架。它提供了身份验证、授权和防护机制等功能

Spring Security 中重要的设计思想是 **责任链模式**，它将网络请求通过 Filter 链逐步处理。每个 Filter 可以决定请求是否继续传递给下一个 Filter，或者直接返回响应（如认证失败、权限不足）。

Spring Security 默认链中主要 Filter 按顺序如下：

| Filter                                 | 作用                                                         |
| -------------------------------------- | ------------------------------------------------------------ |
| `SecurityContextPersistenceFilter`     | 从 Session 或其他存储加载 `SecurityContext`（包含 `Authentication`）到线程上下文，保证请求内可访问 `SecurityContextHolder` |
| `UsernamePasswordAuthenticationFilter` | 处理表单登录认证，解析用户名/密码，调用 `AuthenticationManager` 进行身份验证 |
| `BasicAuthenticationFilter`            | 处理 HTTP Basic 认证                                         |
| `BearerTokenAuthenticationFilter`      | 处理 OAuth2 / JWT Token                                      |
| `CsrfFilter`                           | 处理 CSRF 校验                                               |
| `LogoutFilter`                         | 处理登出请求                                                 |
| `SessionManagementFilter`              | 管理 Session（并发控制、Session Fixation 防护）              |
| `ExceptionTranslationFilter`           | 捕获安全异常（如 AuthenticationException / AccessDeniedException）并生成 HTTP 响应 |
| `FilterSecurityInterceptor`            | 最终权限校验，调用 `AccessDecisionManager` 判断是否允许访问资源 |

**请求处理流程的主要流程**

1. **客户端请求** -> 进入 Servlet Filter
2. **DelegatingFilterProxy** -> 委托给 `FilterChainProxy`
3. **SecurityContextPersistenceFilter** -> 从 Session/Token 加载 `SecurityContext`
4. **UsernamePasswordAuthenticationFilter / BasicAuthenticationFilter** -> 认证处理
   - 调用 `AuthenticationManager.authenticate()`
   - 返回认证成功的 `Authentication`，存入 `SecurityContext`
5. **SessionManagementFilter / CsrfFilter / LogoutFilter / RememberMeFilter** -> 执行安全功能
6. **FilterSecurityInterceptor** -> 权限判断，调用 `AccessDecisionManager`
7. **DispatcherServlet -> Controller** -> 业务处理
8. **响应返回** -> Filter 链逆序执行后处理（如清理 SecurityContext）

其中重要的 Filter 有

- `UsernamePasswordAuthenticationFilter`：认证操作全靠这个过滤器
- `ExceptionTranslationFilter`：异常转换过滤器位于整个 SpringSecurityFilterChain 的后方，用来转换整个链路中出现的异常
- `FilterSecurityInterceptor`：获取所配置资源访问的授权信息，根据 SecurityContextHolder 中存储的用户信息来决定其是否有权限

**接下来我们着重看一下身份认证**

`UsernamePasswordAuthenticationFilter` 是身份认证过滤器，`AuthenticationManager` 类是过滤器中用于认证过程总入口。它可以理解为一个认证调度中心，所有的登录认证请求都会经过它来处理。

主要的认证流程是

```bash
接收一个 Authentication 请求对象 -> 找到合适的认证器 -> 调用认证逻辑 -> 返回一个认证成功的 Authentication 对象（带上用户权限信息等
```

Spring Secturity 在基于内存中的用户认证过程中，是通过 `loadUserByUserName` 获取的账号和密码并存入内存中的。之后会再调用其他方法来判断客户端输入的账号密码是否和内存中的数据匹配。

这个 `loadUserByUserName` 方法是通过 `UserDetailsService` 获取的，它是一个抽象接口，内部的实现可以自由配置。

**一般，账号密码都是存入数据库的，所以如果我们需要基于数据库来实现用的认证**，我们可以通过继承 `UserDetailsService` 接口重写 `loadUserByUserName` 中的获取账号密码的逻辑即可。

查看该接口

```java 
public interface UserDetailsService {
    UserDetails loadUserByUsername(String username) throws UsernameNotFoundException;
}
```

发现该接口返回的是 `UserDetails`，查看该类

```java
public interface UserDetails extends Serializable {
    Collection<? extends GrantedAuthority> getAuthorities();

    String getPassword();

    String getUsername();

    default boolean isAccountNonExpired() {
        return true;
    }

    default boolean isAccountNonLocked() {
        return true;
    }

    default boolean isCredentialsNonExpired() {
        return true;
    }

    default boolean isEnabled() {
        return true;
    }
}
```

可以看到这是一个接口，是用来获取我们储存的用户信息。我们需要实现该接口，可以使其能够正确返回正确的信息。从数据库查询到的用户信息肯定是会被存入实体类中的 `User`，我们可以在 `UserDetails` 的实现类中保存该类的一个引用从而获取信息

```java
@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserDetailsImpl implements UserDetails {

    private User user;

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of();
    }

    @Override
    public String getPassword() {
        return user.getPassword();
    }

    @Override
    public String getUsername() {
        return user.getUsername();
    }

    @Override
    public boolean isAccountNonExpired() {
        return UserDetails.super.isAccountNonExpired();
    }

    @Override
    public boolean isAccountNonLocked() {
        return UserDetails.super.isAccountNonLocked();
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return UserDetails.super.isCredentialsNonExpired();
    }

    @Override
    public boolean isEnabled() {
        return UserDetails.super.isEnabled();
    }
}
```

> **`UserDetails`**  是描述用户核心信息的接口
>
> **`UserDetailsService`** 是专门用来加载 `UserDetails` 的核心接口

现在我们总结一下认证的大概流程：

用户在前端提交登录表单：`username=alice, password=123456`

`UsernamePasswordAuthenticationFilter` 会拦截请求并构造认证请求对象

> 

然后 `AuthenticationManager` 会调用 `UserDetailsService.loadUserByUsername("alice")` 从数据库查出 `UserDetails`：

- username = `"alice"`
- password = `"$2a$10$...哈希值..."`

`DaoAuthenticationProvider` 用 `PasswordEncoder.matches()` 比较前端密码和数据库哈希密码

如果正确返回认证成功的 `Authentication`

```java
// 根据用户名和密码创建认证令牌
Authentication authToken = new UsernamePasswordAuthenticationToken(username, password);
// 调用认证处理对象的 authenticate 方法进行认证
Authentication authenticate = authenticationManager.authenticate(authToken);

// 认证令牌中的 isAuthenticated() 返回 false 代表未认证
// 返回的认证对象 isAuthenticated() 返回 true 代表已认证
```

来看一下这个过程中涉及的核心类

**`AuthenticationManager`**

- 核心接口，用于执行身份验证：

```java
Authentication authenticate(Authentication authentication) throws AuthenticationException;
```

- 常用实现：
  - `ProviderManager`：维护一个 `AuthenticationProvider` 列表，逐个尝试认证。

**`AuthenticationProvider`**

- 具体认证逻辑实现：
  - `DaoAuthenticationProvider`：基于数据库用户名/密码认证
  - `JwtAuthenticationProvider`：基于 JWT Token 认证
- 判断 `Authentication` 是否有效，生成认证后的 `Authentication` 对象。

**`Authentication`**

- 身份认证令牌，封装认证信息：
  - `principal`：用户身份（UserDetails）
  - `credentials`：凭证（密码、Token）
  - `authorities`：角色或权限列表
  - `authenticated`：是否认证成功

**`SecurityContext` & `SecurityContextHolder`**

- **SecurityContext**：保存当前请求的 `Authentication` 对象
- **SecurityContextHolder**：提供访问当前线程上下文 `SecurityContext` 的入口

```java
SecurityContextHolder.getContext().getAuthentication();
```

- **UserDetailsService**：用户信息查询服务，定义了 loadUserByUsername 方法查询用户信息
- **UserDetails**：封装了用户的详细信息，UserDetailsService 查询的用户信息都会封装到这个对象中

**`GrantedAuthority`**

- 表示用户的权限或角色
- 用于最终访问控制（如 `ROLE_ADMIN`、`ROLE_USER`）

**`AccessDecisionManager` & `AccessDecisionVoter`**

- 最终由 `FilterSecurityInterceptor` 调用
- 判断当前用户是否有访问某个 URL 或方法的权限

在解了如何获取用户信息之后，接下来看一下一个 spring security 的基本配置

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Autowired
    private JwtAuthenticationTokenFilter jwtAuthenticationTokenFilter;

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration authConfig)
            throws Exception {
        return authConfig.getAuthenticationManager();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // 开启授权保护
                .authorizeHttpRequests(authorize -> authorize
                        // 不需要认证的地址有哪些
                        .requestMatchers("").permitAll()	// ** 通配符
                        // 对所有请求开启授权保护
                        .anyRequest().
                        // 已认证的请求会被自动授权
                                authenticated()
                )
                // 使用默认的登陆登出页面进行授权登陆
                .formLogin(Customizer.withDefaults())
                // 启用“记住我”功能的。允许用户在关闭浏览器后，仍然保持登录状态，直到他们主动注销或超出设定的过期时间。
                .rememberMe(Customizer.withDefaults());
        // 关闭 csrf CSRF（跨站请求伪造）是一种网络攻击，攻击者通过欺骗已登录用户，诱使他们在不知情的情况下向受信任的网站发送请求。
        http.csrf(AbstractHttpConfigurer::disable);

        // 加入过滤器
        http.addFilterBefore(jwtAuthenticationTokenFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
```

在上述配置类中设置了一个 `PasswordEncoder` 类，这是 Spring Security 提供的加密类，是用于保护用户信息等内容的安全机制。

一般说，数据库存储的密码都是加密过的，当前端界面提交一份用户信息，后端程序需要使用 `PasswordEncoder` 对进行 `encode` 加密，然后再存入数据库。当用户登录时，可以使用其 `matches` 方法来判断是否与当前数据库存储的数据一致

#### Spring Security 的加密机制

**PasswordEncoder**接口

Spring Security 提供了 `PasswordEncoder` 接口，用于定义密码的加密和验证方法。主要有以下几种实现：

- **BCryptPasswordEncoder**：基于 BCrypt 算法，具有适应性和强大的加密强度。它可以根据需求自动调整加密的复杂性。
- **NoOpPasswordEncoder**：不执行加密，适用于开发和测试环境，不建议在生产环境中使用。
- **Pbkdf2PasswordEncoder**、**Argon2PasswordEncoder** 等：这些都是基于不同算法的实现，具有不同的安全特性。

**BCrypt** 算法

BCrypt 是一种安全的密码哈希算法，具有以下特点：

- **盐值（Salt）**：每次加密时都会生成一个随机盐值，确保相同的密码在每次加密时生成不同的哈希值。
- **适应性**：通过增加计算复杂性（如工作因子），可以提高密码的加密强度。

#### 用户状态存储方式

当 spring security 生成了验证信息后，它本身**不规定存储方式**。所以需要看一下常用的客户端和服务端一般有两种方式保存认证状态

基于 **Session**（状态性认证，Stateful）

- **存储位置**：服务器端存储用户认证信息在 **HttpSession** 中
- **流程**：
  1. 用户登录 -> Spring Security 校验用户名密码
  2. 生成 `Authentication` -> 保存到 `SecurityContext` -> 存入 Session
  3. 后续请求带上 Session ID -> 服务端读取 Session -> 获取用户信息
- **特点**：
  - 服务端维护状态
  - 容易实现登出（删除 Session）
  - 不适合分布式（除非用 Session 集群 / Redis）

**spring security 基于 session 的身份认证原理**

**核心思想**

- 认证信息保存在 **服务器端**（通常是 HttpSession）。
- 客户端通过 **Cookie（JSESSIONID）** 与服务器通信，每次请求带上 Session ID。
- Spring Security 会自动把认证信息存入 `SecurityContext`，并存入 Session。

**流程**

```bash
客户端登录请求
      ↓
UsernamePasswordAuthenticationFilter
      ↓
AuthenticationManager -> AuthenticationProvider
      ↓
生成 Authentication 对象
      ↓
SecurityContextPersistenceFilter
      ↓
将 Authentication 存入 SecurityContextHolder
      ↓
将 SecurityContext 存入 HttpSession
      ↓
响应客户端（返回 Cookie: JSESSIONID）
```

**后续请求**

1. 客户端带上 Cookie: JSESSIONID
2. `SecurityContextPersistenceFilter` 从 Session 加载 SecurityContext
3. 将 Authentication 放入 SecurityContextHolder
4. FilterSecurityInterceptor 校验权限
5. Controller 处理请求

基于 **Token**（无状态认证，Stateless）

- **存储位置**：客户端持有 Token（如 JWT），服务端不保存认证状态
- **流程**：
  1. 用户登录 -> Spring Security 验证用户名密码
  2. 生成 Token（JWT）返回给客户端
  3. 客户端每次请求带上 Token（Header/Query）
  4. 服务端通过 Token 验证用户身份（无需 Session）
- **特点**：
  - 无状态，不依赖服务器保存 Session
  - 支持分布式系统
  - Token 一旦生成，无法立即失效（除非做 Token 黑名单管理）

**基于 JWT 的身份验证（Stateless）**

**核心思想**

- 认证信息 **不保存在服务器端**，全部存储在客户端 Token（JWT）里。
- 服务端每次请求通过解析 JWT 来验证身份。
- 适合 **分布式和移动端应用**。

**流程**

**登录阶段**

```bash
客户端发送用户名/密码登录请求
      ↓
UsernamePasswordAuthenticationFilter
      ↓
AuthenticationManager -> AuthenticationProvider
      ↓
生成 Authentication 对象
      ↓
生成 JWT（包含 userId、roles 等）
      ↓
返回 JWT 给客户端
```

**请求阶段**

```bash
客户端请求 API，并在 Header 中带上 JWT（Authorization: Bearer <token>）
      ↓
JwtAuthenticationFilter（自定义 Filter）
      ↓
解析 JWT，验证签名和有效期
      ↓
生成 Authentication 对象
      ↓
SecurityContextHolder.setContext(authentication)
      ↓
FilterSecurityInterceptor 进行权限校验
      ↓
Controller 处理请求
```

> 这里我们强调一下 `UsernamePasswordAuthenticationFilter` 的执行逻辑只在首次提交登录表单时触发，那么程序是如何判断这个时机呢
>
> `UsernamePasswordAuthenticationFilter` 内部有两个关键属性：
>
> ```
> private String filterProcessesUrl = "/login"; // 默认登录 URL
> private boolean postOnly = true;             // 默认只处理 POST 请求
> ```
>
> - **filterProcessesUrl**：指定登录请求的 URL
> - **postOnly**：是否只处理 POST 方法
>
> 一个关键方法 `requiresAuthentication()` 内部就是根据这两个属性判断“是否需要触发登录认证”的
>
> **只要请求 URL 是登录 URL 且是 POST，就认为是首次提交表单**

要知道 **SecurityContextPersistenceFilter 会执行两次逻辑**：

1. **请求开始时**：读取 Session 恢复 `SecurityContext` 到 `SecurityContextHolder`
2. **请求结束时**：把 `SecurityContextHolder` 的内容保存回 Session

因此当第一次认证过后，基于 session 储存认证信息的方式可以再次拿到认证信息，但是基于 token 的认证方式一般会将 session 禁用，所以它不能从 session 中拿到，因此就需要自己通过继承 `OncePerRequestFilter` 来自定义一个 Filter 逻辑来获取认证信息

```java
@Component
public class JwtAuthenticationTokenFilter extends OncePerRequestFilter {
    @Autowired
    private UserMapper userMapper;

    @Override
    protected void doFilterInternal(HttpServletRequest request, @NotNull HttpServletResponse response, @NotNull FilterChain filterChain) throws ServletException, IOException {
        String token = request.getHeader("Authorization");

        if (!StringUtils.hasText(token) || !token.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        token = token.substring(7);

        String userid;
        try {
            Claims claims = JwtUtil.parseJWT(token);
            userid = claims.getSubject();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        User user = userMapper.selectById(Integer.parseInt(userid));

        if (user == null) {
            throw new RuntimeException("用户名未登录");
        }

        UserDetailsImpl loginUser = new UserDetailsImpl(user);
        UsernamePasswordAuthenticationToken authenticationToken =
                new UsernamePasswordAuthenticationToken(loginUser, null, null);

        // 如果是有效的jwt，那么设置该用户为认证后的用户
        SecurityContextHolder.getContext().setAuthentication(authenticationToken);

        filterChain.doFilter(request, response);
    }
}
```

### 权限校验

Spring Security 会在请求进入 `FilterSecurityInterceptor` 之前，从 `SecurityContextHolder` 获取 `Authentication` 对象。

`Authentication` 里有用户的权限信息（通常是 `GrantedAuthority`）。

然后会根据在配置中写的 **访问规则**（比如 `hasRole("ADMIN")`），来判断当前用户是否有权限访问。

有两种权限校验的方式

#### 基于 URL 的权限控制

配置 `SecurityFilterChain`，对不同 URL 设置访问规则：

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()   // 公开接口，无需认证
                .requestMatchers("/admin/**").hasRole("ADMIN") // 需要 ADMIN 角色
                .requestMatchers("/user/**").hasAnyRole("USER", "ADMIN") // USER 或 ADMIN 可访问
                .anyRequest().authenticated() // 其他请求必须登录
            )
            .formLogin(withDefaults()); // 开启表单登录
        return http.build();
    }
}
```

#### 基于方法的权限控制

在 Service 或 Controller 层面，通过注解做权限校验。

需要开启：

```java
@Configuration
@EnableMethodSecurity // Spring Boot 3.x / Spring Security 6.x
public class MethodSecurityConfig {
}
```

然后在方法上使用：

```java
@RestController
@RequestMapping("/api")
public class UserController {

    @GetMapping("/profile")
    @PreAuthorize("hasRole('USER')") // 只有 USER 角色能访问
    public String profile() {
        return "用户信息";
    }

    @GetMapping("/admin")
    @PreAuthorize("hasAuthority('sys:admin')") // 需要特定权限
    public String admin() {
        return "后台管理";
    }
}
```

#### 基于表达式的权限控制

Spring Security 提供 SpEL 表达式，可以写得更灵活：

- `@PreAuthorize("isAuthenticated()")` -> 必须登录
- `@PreAuthorize("hasRole('ADMIN') or hasRole('MANAGER')")` -> 多角色支持
- `@PreAuthorize("#id == authentication.principal.id")` -> 只能访问自己的数据

> 用户权限信息来自 **UserDetailsService.loadUserByUsername()** 里返回的 `UserDetails` 对象的 `getAuthorities()`。
>
> - 一般从数据库里查用户 -> 查询角色/权限 -> 封装成 `GrantedAuthority`。
>
> **FilterSecurityInterceptor** 是最终的拦截器，会根据配置的规则校验是否允许访问。
>
> 如果权限不足，Spring Security 默认会抛出 `AccessDeniedException`，触发 `AccessDeniedHandler`。

**自定义的权限校验暂空**

### JWT

`JWT`全称 `JSON Web Token`，实现过程简单的说就是用户登录成功之后，将用户的信息进行加密，然后生成一个 `token` 返回给客户端

因为 `token` 中存放了用户的基本信息，所以肯定不能存放敏感信息，并且要对信息做一些加密处理

JWT是由三段信息构成的，将这三段信息文本用`.`链接一起就构成了`JWT`字符串

```bash
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9.TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ
```

- 第一部分：我们称它为头部（header），用于存放token类型和加密协议，一般都是固定的；
- 第二部分：我们称其为载荷（payload），用户数据就存放在里面；
- 第三部分：是签证（signature），主要用于服务端的验证；

##### header

JWT的头部承载两部分信息：

- 声明类型，这里是JWT；
- 声明加密的算法，通常直接使用 HMAC SHA256；

完整的头部就像下面这样的JSON：

```java
{
  'typ': 'JWT',
  'alg': 'HS256'
}
```

使用 `base64` 加密，构成了第一部分。

##### playload

载荷就是存放有效信息的地方，这些有效信息包含三个部分：

- 标准中注册的声明；
- 公共的声明；
- 私有的声明；

**其中，标准中注册的声明包括如下几个部分** ：

- iss：jwt 签发者；
- sub：jwt 所面向的用户；
- aud：接收 jwt 的一方；
- exp：jwt 的过期时间，这个过期时间必须要大于签发时间；
- nbf：定义在什么时间之前，该jwt都是不可用的；
- iat：jwt 的签发时间；
- jti：jwt 唯一身份标识，主要用来作为一次性token,从而回避重放攻击；

**公共的声明部分**：
公共的声明可以添加任何的信息，一般添加用户的相关信息或其他业务需要的必要信息，但不建议添加敏感信息，因为该部分在客户端可解密。

**私有的声明部分**：
私有声明是提供者和消费者所共同定义的声明，一般不建议存放敏感信息，因为`base64`是对称解密的，意味着该部分信息可以归类为明文信息。

定义一个 payload 后，将其进行`base64`加密，得到`Jwt`的第二部分：

##### signature

jwt 的第三部分是一个签证信息，这个签证信息由三部分组成：

- header (base64后的)；
- payload (base64后的)；
- secret (密钥);

这个部分需要 `base64` 加密后的 `header` 和 `base64` 加密后的 `payload` 使用 `.` 连接组成的字符串，然后通过 `header` 中声明的加密方式进行加盐 `secret` 组合加密，然后就构成了 `jwt` 的第三部分。

> 在 Spring Security 中，使用 JWT 的方式进行身份认证时，会将**身份认证后的身份标识和权限信息加密成 JWT**，后续会从 JWT 中拿到相应信息

一个 JWT 工具类

```java
/**
 * JWT 工具类
 * 功能：
 *  - 生成 JWT
 *  - 解析 JWT
 *  - 校验 JWT 是否过期
 *  - 从 JWT 中获取信息
 */
public class JwtUtil {

    /** JWT 默认有效期：14天 */
    public static final long JWT_TTL = 1000L * 60 * 60 * 24 * 14;

    /** JWT 签发者 */
    private static final String ISSUER = "sg";

    /** 秘钥 */
    private static final String SECRET_KEY = "SDFGjhdsfalshdfHFdsjkdsfds121232131afasdfac";

    /**
     * 生成唯一标识（JWT ID）
     */
    public static String getUUID() {
        return UUID.randomUUID().toString().replaceAll("-", "");
    }

    /**
     * 生成 JWT
     * @param subject 主题（通常存放用户唯一标识，比如用户ID）
     * @return JWT 字符串
     */
    public static String createJWT(String subject) {
        return createJWT(subject, null);
    }

    /**
     * 生成 JWT（带自定义有效期）
     * @param subject 主题（通常是用户ID或用户名）
     * @param ttlMillis 自定义有效期（毫秒），如果为 null 则用默认值
     * @return JWT 字符串
     */
    public static String createJWT(String subject, Long ttlMillis) {
        if (ttlMillis == null) {
            ttlMillis = JWT_TTL;
        }

        long nowMillis = System.currentTimeMillis();
        Date now = new Date(nowMillis);

        long expMillis = nowMillis + ttlMillis;
        Date expDate = new Date(expMillis);

        SecretKey key = generalKey();

        return Jwts.builder()
                .id(getUUID())              // JWT 唯一ID
                .subject(subject)           // 主题（可以存放用户ID/用户名）
                .issuer(ISSUER)             // 签发者
                .issuedAt(now)              // 签发时间
                .expiration(expDate)        // 过期时间
                .signWith(key, SignatureAlgorithm.HS256) // 签名算法
                .compact();
    }

    /**
     * 生成密钥
     */
    private static SecretKey generalKey() {
        // JJWT 新版本推荐使用 Keys.hmacShaKeyFor
        return Keys.hmacShaKeyFor(SECRET_KEY.getBytes());
    }

    /**
     * 解析 JWT 并获取 Claims
     * @param jwt JWT 字符串
     * @return Claims 对象（包含 subject, exp 等）
     * @throws JwtException 如果 token 无效或过期
     */
    public static Claims parseJWT(String jwt) throws JwtException {
        SecretKey key = generalKey();
        return Jwts.parser()
                .verifyWith(key)   // 校验签名
                .build()
                .parseSignedClaims(jwt)
                .getPayload();
    }

    /**
     * 判断 Token 是否过期
     */
    public static boolean isTokenExpired(String jwt) {
        try {
            Claims claims = parseJWT(jwt);
            return claims.getExpiration().before(new Date());
        } catch (ExpiredJwtException e) {
            return true; // 已过期
        }
    }

    /**
     * 获取 Token 中的 subject（例如用户ID）
     */
    public static String getSubject(String jwt) {
        return parseJWT(jwt).getSubject();
    }
}
```

###  Servlet 的 Filter、Spring Security 的 FilterChain 和 Spring MVC 的 HandlerInterceptor 的执行顺序

web 服务中，一个请求的执行顺序是

```bash
客户端请求
   ↓
Servlet Filter（普通 Web Filter）
   ↓
DelegatingFilterProxy -> Spring Security FilterChain
   ↓
DispatcherServlet
   ↓
Spring MVC HandlerInterceptor.preHandle()
   ↓
Controller 方法
   ↓
Spring MVC HandlerInterceptor.postHandle()
   ↓
视图渲染 / 返回响应
   ↓
Spring MVC HandlerInterceptor.afterCompletion()
   ↓
Servlet Filter.doFilter() 的后续逻辑
   ↓
响应返回给客户端
```

结合上面的流程图分析

**Servlet Filter（Web Filter）**

- 属于 **Servlet 容器级别**（Tomcat/Jetty 等）的过滤器。
- 在 Spring 体系外就已经能生效。
- 对所有进入容器的请求先进行处理。

**Spring Security Filter Chain**

- 是 Spring Boot 在启动时通过 `DelegatingFilterProxy` 注册到 Servlet 容器中的一个特殊 Filter。
- 本质上也是 **Servlet Filter**，但它内部维护了一个 **FilterChainProxy**，包含十几个 Spring Security 的安全过滤器（如认证、授权、CSRF 等）。
- 所以它会在 **普通的 Spring MVC 拦截器执行之前**，完成认证和权限控制。

**Spring MVC HandlerInterceptor**

- 属于 Spring MVC 层面。
- 在请求被分派到 `Controller` 前后执行（`preHandle -> Controller -> postHandle -> afterCompletion`）。

所以可以看出

**最外层** 是Servlet 过滤器（Web Filter）

- 可以拦截所有请求（包括静态资源），最早介入。

**中间层** 是Spring Security 过滤链（本质还是 Filter，但优先级高于 MVC）

- 负责认证、授权、安全控制。
- 如果认证失败/无权限，直接返回 401/403，后续拦截器和 Controller 根本不会执行。

**最内层** 是Spring MVC 拦截器（HandlerInterceptor）

- 只有通过了 Security 校验的请求，才会到达拦截器和 Controller。
- 适合做业务相关的拦截，如日志、接口耗时统计、多租户上下文等。
