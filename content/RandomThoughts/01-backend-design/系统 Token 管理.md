+++
date = '2026-02-19T15:46:38+08:00'
draft = false
title = '系统 Token 管理'
+++

实习时看到项目同时把 Token 存在 Redis 和 MySQL 里。乍看像重复存储，其实更像两套职责：**Redis 管在线态，MySQL 管长期态和审计**。

如果只问“Token 放哪儿”，答案很容易流于表面。更好的问题是：系统希望 Token 支持哪些能力？

## Redis 和 MySQL 的职责

| 存储 | 适合职责 | 原因 |
| --- | --- | --- |
| Redis | 高频鉴权、过期控制、踢人下线、黑名单 | 读写快，天然支持 TTL |
| MySQL | 登录记录、Refresh Token、多端管理、审计追溯 | 持久化强，方便查询和统计 |

Redis 面向在线请求，MySQL 面向管理和追溯。把这两个目标混成一个设计，后面不是性能难受，就是审计难受。

## 只用 JWT 可以吗

可以，但要接受它的取舍。

纯 JWT 的特点是服务端不保存登录态。后端只校验签名和过期时间，不需要每次查 Redis。

优点：

- 鉴权简单。
- 服务端压力小。
- 适合无状态横向扩展。

缺点：

- Token 未过期前难以及时失效。
- 强制下线、封号、修改密码后踢出旧登录比较麻烦。
- 多端登录管理和审计能力弱。

所以，纯 JWT 更适合安全要求不高、会话控制不复杂的系统。一旦系统需要“立刻失效”和“登录可追溯”，就需要引入服务端状态。

## Access Token 和 Refresh Token

常见方案会拆成两种 Token。

| 类型 | 有效期 | 用途 | 存储建议 |
| --- | --- | --- | --- |
| Access Token | 短，例如 15 分钟到 2 小时 | 访问接口 | 前端保存，后端可用 Redis 校验状态 |
| Refresh Token | 长，例如 7 天到 30 天 | 换取新的 Access Token | MySQL 持久化，必要时 Redis 加速 |

Access Token 泄露后危害时间短，Refresh Token 泄露后危害更大，所以 Refresh Token 更应该支持服务端吊销、轮换和审计。

## 登录时写什么

登录成功后可以做这些事：

```text
1. 校验账号密码、短信验证码或第三方身份。
2. 生成 accessToken 和 refreshToken。
3. 将在线态写入 Redis，设置 TTL。
4. 将登录记录或 refreshToken 记录写入 MySQL。
5. 返回 accessToken，必要时返回 refreshToken。
```

Redis 示例：

```text
login:access:{jti} -> userId, deviceId, roles
TTL = accessToken 剩余有效期
```

MySQL 示例字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 记录 ID |
| `user_id` | 用户 ID |
| `refresh_token_hash` | Refresh Token 摘要，不建议存明文 |
| `device_id` | 设备标识 |
| `login_ip` | 登录 IP |
| `user_agent` | 客户端信息 |
| `expires_at` | 过期时间 |
| `revoked_at` | 吊销时间 |

Refresh Token 最好存摘要而不是明文。数据库泄露时，摘要至少还能增加一层防线；明文 Token 泄露就等于把门票摆在桌上。

## 请求鉴权时查什么

如果系统要求 Token 可立即失效，可以在每次请求时查 Redis：

```text
1. 从 Authorization 请求头解析 accessToken。
2. 校验签名、过期时间、格式。
3. 读取 jti。
4. 查询 Redis 中的在线态或黑名单。
5. 构建 Authentication，放入 SecurityContext。
```

查不到 Redis 记录时通常返回 401。不要自动去 MySQL 恢复 Access Token，除非这是明确设计好的容灾策略，否则会削弱“踢人下线”和“封禁”的即时性。

## 什么时候需要双存储

满足这些需求时，Redis + MySQL 的组合更合理：

- 支持多端登录管理。
- 支持管理员强制下线。
- 支持用户修改密码后旧 Token 失效。
- 支持登录历史、设备列表、异常登录审计。
- 支持 Refresh Token 轮换。
- 有安全合规或风控要求。

如果只是个人项目、后台管理系统或低风险应用，只保存短期 JWT 也可以。设计不是越复杂越高级，不合需求的复杂度只是换了衣服的麻烦。

## 小结

Redis 存 Token 解决的是“当前还能不能访问”，MySQL 存 Token 解决的是“谁在什么时候以什么设备登录过，以及能不能长期管理”。一个偏实时，一个偏追溯。理解这点，就不会再把双写 Token 当成单纯的重复劳动。
