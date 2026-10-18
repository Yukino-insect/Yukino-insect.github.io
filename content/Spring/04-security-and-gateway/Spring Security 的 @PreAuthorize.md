+++
date = '2026-01-10T20:22:20+08:00'
draft = false
title = 'Spring Security 的 @PreAuthorize'
+++

@PreAuthorize 是用于方法级别的权限控制，在方法执行之前，基于 SpEL 表达式判断当前用户是否有权限。

常用于：

- Controller 接口权限控制
- Service 层业务权限控制
- RBAC（角色 / 权限）模型

开启方法级权限控制

#### Spring Boot 2.x / Spring Security 5

```java
@EnableGlobalMethodSecurity(prePostEnabled = true)
@Configuration
public class SecurityConfig {
}
```

#### Spring Boot 3.x / Spring Security 6（推荐）

```java
@Configuration
@EnableMethodSecurity
public class SecurityConfig {
}
```

在方法上使用 `@PreAuthorize`

```java
@PreAuthorize("hasRole('ADMIN')")
@GetMapping("/admin")
public String admin() {
    return "admin";
}
```

## 三、最常用表达式（一定要会）

### 1. 角色判断

```
@PreAuthorize("hasRole('ADMIN')")
```

等价于：

```
@PreAuthorize("hasAuthority('ROLE_ADMIN')")
```

> 注意： `hasRole` **会自动加 `ROLE_` 前缀**

------

### 2. 多角色

```
@PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
```

------

### 3. 权限判断（推荐）

```
@PreAuthorize("hasAuthority('user:add')")
```

多权限：

```
@PreAuthorize("hasAnyAuthority('user:add','user:update')")
```

------

### 4. 登录状态判断

```
@PreAuthorize("isAuthenticated()")
```

匿名用户不可访问。

------

### 5. 允许匿名

```
@PreAuthorize("isAnonymous()")
```

------

## 四、结合方法参数（非常常用）

### 1. 参数级权限校验

```
@PreAuthorize("#userId == authentication.principal.id")
public void updateUser(Long userId) {
}
```

含义：

> 只能修改 **自己的数据**

------

### 2. 多条件组合

```java
@PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
```

## 五、调用自定义权限校验方法（进阶必会）

### 1. 定义权限校验 Bean

```
@Component("auth")
public class AuthService {

    public boolean canEdit(Long userId) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        User user = (User) auth.getPrincipal();
        return user.getId().equals(userId);
    }
}
```

------

### 2. 在 `@PreAuthorize` 中调用

```
@PreAuthorize("@auth.canEdit(#userId)")
public void edit(Long userId) {
}
```

>  **企业项目最推荐的写法**

------

## 六、Controller vs Service 放哪里更好？

| 层级       | 建议                 |
| ---------- | -------------------- |
| Controller |  不推荐（容易绕过） |
| Service    |  强烈推荐           |

```
@Service
public class UserService {

    @PreAuthorize("hasAuthority('user:update')")
    public void update(User user) {
    }
}
```

------

## 七、常见错误 & 排查清单

### 1. 不生效

原因 90% 是：

- 没加 `@EnableMethodSecurity`
- 方法是 `private`
- 同类内部调用（AOP 失效）

------

### 2. hasRole 判断失败

```
hasRole('ADMIN')
```

但数据库里是：

```
ADMIN
```

 错
  正确应为：

```
ROLE_ADMIN
```

或改用：

```
hasAuthority('ADMIN')
```

------

### 3. 获取不到参数

```
@PreAuthorize("#id == ...")
```

方法签名必须是：

```
public void test(Long id)
```

**参数名要开启编译参数保留：**
