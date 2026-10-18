+++
date = '2026-01-11T20:50:49+08:00'
draft = false
title = 'token认证'

+++

问题是：

> 后端返回给前端的 token 如果被拦截，拿到 token 的人可以直接访问服务吗？

答案是：**可以。在有效期内，拿到 Bearer Token 的人通常就可以以该用户身份访问对应资源。**

但前提是“真的拿到了完整可用的 token”。在 HTTPS 正常配置的情况下，网络窃听者通常拿不到 HTTP 请求头里的 token。

## 一、Token 是什么

Token 是服务端签发给客户端的一段访问凭证。

常见请求方式：

```http
GET /api/user/info HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

这里的：

```text
Authorization: Bearer <token>
```

表示客户端用 token 证明自己的登录状态。

Bearer Token 的意思就是：

> 持有者即授权者。

谁持有这个 token，谁就能在它有效期和权限范围内访问资源。

## 二、拿到 token 能不能直接调用接口

通常可以。

例如你从浏览器 DevTools 里复制了前端正在使用的 token，然后用 Postman 调接口：

```http
GET /api/user/info
Authorization: Bearer <copied-token>
```

只要 token 没过期、没被撤销、签名有效、权限满足，后端就会认为这是合法请求。

这不是 bug，而是 token 认证的设计前提。

真正需要关注的是：

1. token 是否容易泄露。
2. token 泄露后能用多久。
3. token 权限是否过大。
4. token 是否可以撤销。
5. 是否有风控和审计。

## 三、HTTPS 下 token 会不会被网络拦截

在 HTTPS 正常配置且客户端没有被安装恶意根证书的情况下，网络窃听者通常看不到 token。

因为 token 在 HTTP 请求头里，而 HTTPS 会把 HTTP 层内容加密。

网络中间人通常只能看到：

1. 目标 IP。
2. 连接端口。
3. 数据大小。
4. 连接时间。
5. 部分 TLS 握手元数据。

看不到：

1. 请求路径的完整敏感内容。
2. HTTP header。
3. `Authorization`。
4. Cookie。
5. 请求体。
6. 响应体。

更准确的说法不是：

```text
拦截者拿到了 token 但解不开。
```

而是：

```text
拦截者通常只能拿到 TLS 加密后的数据流，拿不到完整 token 字符串。
```

## 四、HTTP 明文传输为什么危险

如果系统使用 HTTP：

```http
GET /api/user/info HTTP/1.1
Host: api.example.com
Authorization: Bearer abc.def.ghi
```

同一网络中的攻击者、恶意代理或被入侵的网络设备都可能直接看到 token。

一旦 token 被复制，攻击者就可以在有效期内伪装成用户访问接口。

所以生产系统必须使用 HTTPS。对 token 认证来说，这是基本要求，不是什么锦上添花。

## 五、Token 常见泄露方式

HTTPS 只能保护传输过程，不能保证 token 在客户端和服务端内部永远安全。

常见泄露方式包括：

### 1. XSS 窃取

如果 token 存在 `localStorage`：

```js
localStorage.setItem("token", token);
```

一旦页面存在 XSS，恶意脚本可以读取：

```js
localStorage.getItem("token");
```

然后把 token 发走。

### 2. 日志泄露

常见危险写法：

```java
log.info("Authorization = {}", authorizationHeader);
```

或者：

```js
console.log(token);
```

日志系统、浏览器控制台截图、异常平台都可能导致 token 扩散。

### 3. 浏览器插件或被控终端

恶意浏览器插件、木马、远控软件可以从页面、内存、剪贴板或本地存储中读取 token。

### 4. 复制调试

实习或联调时，从前端复制 token 到 Postman 调接口很常见。

这不是网络拦截，而是合法用户把凭证复制出来。它说明 token 在有效期内确实可以代表用户身份。

### 5. 企业 HTTPS 代理

某些企业安全设备会进行 HTTPS 检查。

链路类似：

```text
浏览器
  -> 企业代理
  -> 目标服务器
```

企业代理在终端安装了受信任的内部根证书后，可以对 HTTPS 做中间人解密和审计。

这属于受控企业环境，不等同于普通公网窃听。

## 六、Access Token 和 Refresh Token

成熟系统通常不会只使用一个永不过期 token。

更常见的设计是：

| 类型 | 作用 | 有效期 |
| --- | --- | --- |
| Access Token | 调业务接口 | 短，一般分钟级到小时级 |
| Refresh Token | 换取新的 Access Token | 较长，但使用范围更窄 |

流程大致是：

```text
用户登录
  -> 服务端签发 access token + refresh token
  -> 前端用 access token 调接口
  -> access token 过期
  -> 前端用 refresh token 换新 access token
```

这样即使 access token 泄露，攻击窗口也比较短。

Refresh Token 权限更敏感，应当更谨慎存储、支持撤销，并在刷新时进行风控校验。

## 七、JWT 和普通 Token 的区别

JWT 是一种常见 token 格式，不是 token 认证的唯一形式。

JWT 通常由三部分组成：

```text
header.payload.signature
```

特点：

1. payload 可以携带用户 ID、过期时间、权限等声明。
2. 服务端可以通过签名验证 JWT 是否被篡改。
3. JWT 默认只是 Base64URL 编码，不是加密。

所以不要把敏感信息直接放进 JWT payload，例如密码、身份证号、银行卡号等。

普通随机 token 则可能只是一个不可猜测的字符串，服务端通过数据库或缓存查它对应的用户和权限。

## 八、前端应该把 token 放在哪里

常见方案有两类，各有风险。

### 1. localStorage / sessionStorage

优点：

1. 使用简单。
2. 不会自动随请求发送。
3. 适合前后端分离接口调用。

风险：

1. 容易被 XSS 读取。
2. 长期存储会扩大泄露影响。

### 2. HttpOnly Cookie

优点：

1. JavaScript 不能直接读取。
2. 能降低 XSS 直接偷 token 的风险。

风险：

1. Cookie 会自动随请求发送。
2. 需要防 CSRF。
3. 跨域 Cookie 配置更复杂。

没有绝对完美的存储方式。选择哪种方案，要结合业务场景、前端架构、CSRF 防护和 XSS 防护能力。

## 九、如何降低 token 泄露风险

成熟系统通常会组合使用下面这些措施：

1. 全站 HTTPS。
2. Access Token 短有效期。
3. Refresh Token 单独管理。
4. 支持 token 撤销和强制下线。
5. 权限最小化。
6. 管理员 token 更短、更严格。
7. 避免在日志中打印 token。
8. 防 XSS：输入输出转义、CSP、依赖安全治理。
9. 防 CSRF：SameSite、CSRF Token、Origin 校验。
10. 异常登录检测：IP、设备、地理位置、User-Agent 变化。

其中 IP、User-Agent、设备指纹绑定属于增强措施，不应作为唯一安全边界。因为移动网络、代理和浏览器升级都可能导致这些信息变化。

## 十、实习时拿前端 token 测接口是否合理

合理，而且很常见。

在联调或测试阶段，前端已经完成登录流程，后端同学直接复制 token 调接口，可以快速验证业务行为。

但要清楚边界：

1. 这是调试便利，不是安全漏洞本身。
2. token 在有效期内等同于用户权限。
3. 不要把 token 发到群里、写进文档或提交到仓库。
4. 测试环境 token 也应该有过期时间。
5. 生产环境排查问题时更应该注意脱敏。

## 十一、面试时怎么回答

可以这样说：

> Bearer Token 的特点是持有者即授权者。如果攻击者真的拿到了完整可用的 token，那么在 token 有效期和权限范围内就可以伪装成用户访问接口。这不是 bug，而是 token 认证的基本模型。安全性依赖 HTTPS 防止传输途中被窃听，依赖短有效期、刷新机制、权限控制、撤销机制和日志脱敏来降低泄露后的影响。需要注意的是，在 HTTPS 正常配置下，普通网络窃听者通常拿不到 HTTP header 里的 token；真正常见的泄露来源反而是 XSS、日志、浏览器插件、被控终端或人为复制。

## 十二、一句话总结

HTTPS 保护的是 token 不在传输途中被普通窃听者拿到；但 token 一旦以任何方式泄露，在有效期内通常就等同于用户本人。因此 token 认证必须同时依赖 HTTPS、短有效期、权限最小化、可撤销机制和日志脱敏。
