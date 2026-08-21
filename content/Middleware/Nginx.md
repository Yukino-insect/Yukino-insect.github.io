+++
date = '2025-08-17T11:58:44+08:00'
draft = false
title = 'Nginx'
+++

Nginx 是高性能的 HTTP 服务器和反向代理服务器。它常用于静态资源托管、反向代理、负载均衡、HTTPS 终止、访问控制和请求转发。

在 Web 系统里，Nginx 通常站在应用服务前面：客户端先访问 Nginx，再由 Nginx 把请求转发到后端应用。这样可以隐藏真实服务地址，也能统一处理证书、日志、限流和负载均衡。

## 正向代理与反向代理

正向代理代理的是客户端。客户端知道代理存在，并通过代理访问目标服务器。

```text
客户端 -> 正向代理 -> 外部服务器
```

反向代理代理的是服务端。客户端通常不知道后端真实服务，只访问代理服务器。

```text
客户端 -> Nginx -> 后端应用
```

常见业务系统使用的是反向代理。

## 配置结构

Nginx 配置由几个核心块组成：

```nginx
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;
        server_name example.com;

        location / {
            root /usr/share/nginx/html;
            index index.html;
        }
    }
}
```

常见配置块：

| 配置块 | 作用 |
| --- | --- |
| `main` | 全局配置，例如 worker 进程数 |
| `events` | 网络连接模型和连接数 |
| `http` | HTTP 服务配置 |
| `server` | 一个虚拟主机 |
| `location` | 路径匹配和请求处理规则 |
| `upstream` | 后端服务池 |

## 静态资源

最简单的静态资源配置：

```nginx
server {
    listen 80;
    server_name static.example.com;

    location / {
        root /data/www;
        index index.html;
    }
}
```

如果请求 `/images/logo.png`，Nginx 会查找：

```text
/data/www/images/logo.png
```

`root` 会把请求路径追加到指定目录后面。

另一个常用指令是 `alias`：

```nginx
location /upload/ {
    alias /data/files/;
}
```

请求 `/upload/a.png` 时，Nginx 会查找：

```text
/data/files/a.png
```

`root` 和 `alias` 的路径拼接规则不同，配置文件里混用时要格外小心。它们都叫路径映射，但实际脾气完全不一样。

## 反向代理

把请求转发到本机 Java 应用：

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

常见代理头：

| 请求头 | 作用 |
| --- | --- |
| `Host` | 保留原始域名 |
| `X-Real-IP` | 传递客户端真实 IP |
| `X-Forwarded-For` | 记录代理链路上的 IP |
| `X-Forwarded-Proto` | 记录原始协议，例如 HTTP 或 HTTPS |

后端应用如果要获取真实客户端 IP，需要从这些代理头中读取，并且只信任来自 Nginx 的请求。

## `proxy_pass` 路径规则

`proxy_pass` 后面是否带 `/`，会影响转发路径。

```nginx
location /api/ {
    proxy_pass http://backend/;
}
```

请求：

```text
/api/users
```

转发到：

```text
http://backend/users
```

如果写成：

```nginx
location /api/ {
    proxy_pass http://backend;
}
```

转发到：

```text
http://backend/api/users
```

路径不符合预期时，先检查这里。很多 404 不是后端坏了，只是 Nginx 把路带歪了。

## 负载均衡

使用 `upstream` 定义后端服务池：

```nginx
http {
    upstream app_servers {
        server 127.0.0.1:8080 weight=3;
        server 127.0.0.1:8081 weight=1;
    }

    server {
        listen 80;
        server_name api.example.com;

        location / {
            proxy_pass http://app_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
```

常见策略：

| 策略 | 配置 | 说明 |
| --- | --- | --- |
| 轮询 | 默认 | 按顺序分发请求 |
| 权重 | `weight=3` | 权重越高，接收请求越多 |
| IP 哈希 | `ip_hash;` | 同一客户端尽量落到同一后端 |
| 最少连接 | `least_conn;` | 优先转发给连接数较少的后端 |

示例：

```nginx
upstream app_servers {
    least_conn;
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
}
```

## HTTPS 终止

Nginx 常用于统一处理 HTTPS：

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /etc/nginx/certs/api.example.com.pem;
    ssl_certificate_key /etc/nginx/certs/api.example.com.key;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}
```

这样后端应用可以只监听内网 HTTP，由 Nginx 负责外部 HTTPS。

## 常用命令

```bash
nginx -t
```

检查配置是否正确。

```bash
nginx -s reload
```

平滑重载配置。

```bash
systemctl restart nginx
```

重启 Nginx 服务。

修改配置后应先执行 `nginx -t`，确认没有语法错误再 reload。直接重启然后祈祷，是一种非常朴素但不值得推广的部署方法。

## 常见问题

### 413 Request Entity Too Large

上传文件超过限制：

```nginx
client_max_body_size 100m;
```

### 504 Gateway Timeout

后端响应慢或连接超时：

```nginx
proxy_connect_timeout 5s;
proxy_read_timeout 60s;
proxy_send_timeout 60s;
```

### 静态资源缓存

```nginx
location /assets/ {
    root /data/www;
    expires 30d;
    add_header Cache-Control "public";
}
```

### WebSocket 代理

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## 使用建议

- 每次修改配置后先执行 `nginx -t`。
- `server_name`、`location`、`proxy_pass` 三者一起检查，路径问题通常出在这里。
- 反向代理一定要设置必要的请求头。
- 对外只暴露需要的端口，后端应用尽量只监听内网。
- 访问日志和错误日志要按业务域名拆分，排查会轻松很多。

Nginx 的配置并不复杂，复杂的是路径匹配和转发语义。把这两点理解清楚，大多数代理问题都能靠读配置解决。
