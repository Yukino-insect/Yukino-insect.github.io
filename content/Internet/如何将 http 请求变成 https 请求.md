+++
date = '2026-02-19T18:10:00+08:00'
draft = false
title = '如何将 http 请求变成 https 请求'
+++

把 HTTP 请求变成 HTTPS 请求，本质上要做两件事：

1. 服务端提供 HTTPS 入口，也就是启用 TLS。
2. 把所有 HTTP 访问重定向到 HTTPS。

只把前端地址从 `http://` 改成 `https://` 是不够的。如果服务端没有监听 HTTPS 端口、没有配置证书，客户端会在 TLS 握手阶段失败。

## 一、推荐架构：在 Nginx 或网关终止 TLS

实际项目中，最常见的做法是：

```text
浏览器
  -> HTTPS 443
  -> Nginx / 网关 / 负载均衡
  -> HTTP 8080
  -> 后端应用
```

也就是说，对外是 HTTPS，对内可以继续使用 HTTP。

这样做的好处是：

1. 证书统一放在入口层管理。
2. 多个后端服务不用重复配置 TLS。
3. HTTP 到 HTTPS 的跳转也可以统一处理。
4. 后端应用只专注业务逻辑。

## 二、准备证书

要提供 HTTPS，服务端需要证书和私钥。

常见文件包括：

```text
fullchain.pem   证书链
privkey.pem     私钥
```

证书可以来自：

1. 免费 CA，例如 Let's Encrypt。
2. 云厂商证书服务。
3. 公司内部 CA。
4. 商业 CA。

正式公网服务应该使用受浏览器信任的 CA 证书。自签名证书适合内网测试，但公网用户访问时会看到安全警告。

## 三、Nginx 配置 HTTP 跳 HTTPS

一个典型配置如下：

```nginx
server {
    listen 80;
    server_name example.com;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name example.com;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

效果是：

```text
http://example.com/a
  -> 301
  -> https://example.com/a
```

浏览器后续真正访问的是 HTTPS 地址。

## 四、Spring Boot 如何识别原始协议

如果 TLS 在 Nginx 或网关终止，后端收到的请求可能是：

```text
http://127.0.0.1:8080
```

但用户真实访问的是：

```text
https://example.com
```

这时要让 Spring Boot 正确识别 `X-Forwarded-*` 请求头。

Spring Boot 3 推荐配置：

```yaml
server:
  forward-headers-strategy: framework
```

否则应用在生成重定向地址、判断是否安全请求时，可能误以为当前请求是 HTTP。

如果使用 Spring Security 强制 HTTPS，可以写：

```java
@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http.requiresChannel(channel -> channel
            .anyRequest().requiresSecure());
    return http.build();
}
```

前提是入口层正确传递并信任 `X-Forwarded-Proto`。如果代理链没有配置好，应用层强制 HTTPS 可能造成重复跳转。

## 五、让 Spring Boot 直接提供 HTTPS

也可以让 Spring Boot 自己监听 HTTPS 端口。这种方式适合简单服务、内网服务或没有统一网关的场景。

如果已有 `fullchain.pem` 和 `privkey.pem`，可以转换成 PKCS12：

```bash
openssl pkcs12 -export \
  -in fullchain.pem \
  -inkey privkey.pem \
  -out server.p12 \
  -name tomcat \
  -passout pass:changeit
```

Spring Boot 配置：

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

这样应用会直接提供：

```text
https://example.com:8443
```

如果还要把 `8080` 的 HTTP 请求跳转到 `8443`，Spring Boot 需要额外配置 HTTP Connector。实际生产中通常还是交给 Nginx 或网关处理更清晰。

## 六、HTTPS 加固项

### 1. 开启 HSTS

HSTS 会告诉浏览器：以后访问这个域名时强制使用 HTTPS。

Nginx 示例：

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

注意：开启 `includeSubDomains` 前，要确认所有子域名都已经支持 HTTPS。否则某些子域名可能被浏览器强制 HTTPS 后无法访问。

### 2. 禁用旧协议

不要再启用 TLS 1.0、TLS 1.1。生产环境应使用 TLS 1.2 或 TLS 1.3。

### 3. 不暴露后端 HTTP 端口

如果外部入口是 Nginx 的 443，后端 `8080` 应该只允许本机或内网访问。

### 4. 证书自动续期

证书过期会直接导致用户无法正常访问。使用 Let's Encrypt 时，通常需要配置自动续期任务。

## 七、常见误区

### 1. HTTP 不能自动变成 HTTPS

客户端访问 `https://` 时，会先进行 TLS 握手。服务端必须支持 TLS，否则连接会失败。

### 2. 重定向不是加密

HTTP 到 HTTPS 的 `301` 重定向本身仍然是明文响应。真正的加密发生在浏览器访问 HTTPS 地址之后。

### 3. HTTPS 不等于后端完全安全

HTTPS 保护传输过程，不能替代认证、权限控制、参数校验和日志脱敏。

## 八、一句话总结

把 HTTP 变成 HTTPS，不是改一个 URL 字符串，而是在服务入口配置证书和 TLS，并把 80 端口的明文请求重定向到 443 端口。实际项目里最推荐在 Nginx、网关或负载均衡层统一处理。
