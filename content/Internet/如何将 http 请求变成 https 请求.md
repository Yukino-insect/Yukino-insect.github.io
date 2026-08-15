+++
date = '2026-02-19T18:10:00+08:00'
draft = false
title = '如何将 http 请求变成 https 请求'
+++

把 HTTP 变成 HTTPS，本质是：**让客户端只用 TLS 通道访问**，并且 **把所有 HTTP 流量重定向到 HTTPS**。实际落地一般分三层：证书、入口（网关/反代/负载均衡）、应用（Spring Boot）。

#### 1）最推荐的架构：在网关/Nginx 做 HTTPS 终止 + HTTP->HTTPS 重定向

##### 1. 申请/配置证书

拿到：

- 证书文件（`.crt/.pem`）
- 私钥（`.key`）
- （可选）中间证书链（chain）

##### 2.Nginx 配置：80 强制跳 443

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # 反向代理到你的 Spring Boot
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

这样外部访问全是 `https://`，内部应用仍可跑 `http://localhost:8080`。

#### 2）Spring Boot 里如何强制 HTTPS

如果你已经在 Nginx/网关终止 TLS，Spring Boot 需要做两件事：

##### 1.正确识别 X-Forwarded-*（否则会误以为自己是 http）

Spring Boot 3 推荐：

```yaml
server:
  forward-headers-strategy: framework
```

##### 2.强制安全

让应用层也拒绝非 https：

**Spring Security 配置：**

```java
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
      .requiresChannel(channel -> channel
          .anyRequest().requiresSecure()
      );
    return http.build();
}
```

> 注意：如果你是网关终止 TLS，一定要配好 `forward-headers-strategy`，否则 `requiresSecure()` 可能判断失误。

##### 3）如果你要让 Spring Boot 自己直接提供 HTTPS

你需要给应用配置 keystore：

##### 生成/导入证书到 PKCS12

你已有 `fullchain.pem + privkey.pem`：

```bash
openssl pkcs12 -export \
  -in fullchain.pem \
  -inkey privkey.pem \
  -out server.p12 \
  -name tomcat \
  -passout pass:changeit
```

##### Spring Boot 配置

```yaml
server:
  port: 8443
  ssl:
    enabled: true
    key-store: classpath:server.p12
    key-store-password: changeit
    key-store-type: PKCS12
    key-alias: tomcat
```

然后再单独开一个 8080 的 HTTP 端口做 301 跳转（Spring Boot 里实现会稍微麻烦些，通常还是交给 Nginx/网关做更简单稳）。

#### 4）安全性真正关键的加固项

- **HSTS**：告诉浏览器以后只能走 HTTPS

  - Nginx：

    ```nginx
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    ```

- **禁用旧 TLS/弱加密套件**（TLS1.0/1.1）

- **只开放 443，对外关闭 8080**（或仅内网可访问）

- **后端服务间用 mTLS**（如果你是微服务、内部也要强安全）

#### 把 HTTP 变成 HTTPS到底在改什么？

主要改的是 **服务端是否提供 HTTPS**，以及 **客户端是否只能用 HTTPS**：

- 服务端：需要证书 + 监听 443（或其它端口）提供 TLS
- 客户端：请求地址改成 `https://...`，并正确校验证书
- 入口层：把 `http://` 的 80 端口请求 301/302 重定向到 `https://...`

> 如果服务端没开 HTTPS，客户端就算想发 `https://` 也连不上（握手失败/连接失败）。

参考：

https://juejin.cn/post/7361358666212212745
