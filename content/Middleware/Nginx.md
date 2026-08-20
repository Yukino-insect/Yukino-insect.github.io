+++
date = '2025-08-17T11:58:44+08:00'
draft = false
title = 'Nginx'
+++

## 概念

**Nginx**是高性能的HTTP和反向代理的web服务器。它不仅可以做反向代理，实现负载均衡。还能用作正向代理来进行上网等功能。

- 正向代理：使局域网中的客户端访问到外网。即通过代理服务器来访问服务器的过程
- 反向代理：客户端对代理是无感的。客户端将请求发送到反向代理服务器，再由反向代理服务器去选择目标服务器获取数据返回给客户端。暴露的是代理服务器的地址，隐藏了真实服务器地址
- 负载均衡：

## 配置

```properties

#user  nobody;
# 定义 nginx 工作进程（worker process） 的数量
worker_processes  1;

# 每个 worker 进程 最大能同时建立的连接数
events {
    worker_connections  1024;
}

# HTTP 模块配置，管理 web 服务
http {
    include       mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                     '$status $body_bytes_sent "$http_referer" '
                     '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  logs/access.log  main;
    error_log   logs/error.log   warn;

    sendfile        on;

    keepalive_timeout  65;
    
    # 虚拟主机就是在同一台服务器上，通过域名 / IP / 端口的不同配置，运行多个网站。
	# nginx 的 server{} 配置块就是一个虚拟主机的定义
    server {
   		# 表示监听本机 80 端口
        listen       80;
        # 匹配请求头（HTTP Host）中的域名或 IP 地址，用于区分不同的虚拟主机
        server_name  208.208.128.122;
        
        # 访问静态资源
        # 请求路径中的资源会从root目录下寻找，index是默认返回值
        # location / {
        #     root   /usr/share/nginx/html;
        #     index  index.html index.htm;
        # }

		# location /：表示匹配所有路径。
		# root html;：表示静态资源的根目录在 nginx安装目录/html/ 下。
		# proxy_pass http://127.0.0.1:8080;：把请求反向代理到本地 8080 端口
        location / {
            root   html;
            proxy_pass http://127.0.0.1:8080;
            index  index.html index.htm;
        }
        
		# 当出现 500/502/503/504 错误时，统一跳转到 /50x.html 页面。
		# location = /50x.html 表示精确匹配 /50x.html 路径，从 html 目录下取这个文件
        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }

    }

}
```

****

负载均衡

```properties

#user  nobody;
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                     '$status $body_bytes_sent "$http_referer" '
                     '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  logs/access.log  main;
    error_log   logs/error.log   warn;

    sendfile        on;

    keepalive_timeout  65;

    # 定义后端服务器池
    # 默认轮询
    # 权重 server 127.0.0.1:8080 weight=3;
    # 哈希 加上 ip_hash属性
    #最少链接 加上 least_conn
    upstream backend_servers {
        server 127.0.0.1:8080;
        server 127.0.0.1:8081;
    }

    server {
        listen       80;
        server_name  208.208.128.122;

        location / {
            root   html;
            proxy_pass http://127.0.0.1:8080;
            index  index.html index.htm;
        }

		# 负载均衡
        location /redis {
            proxy_pass         http://backend_servers;  # 注意这里的 / 很关键
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }

    }

}
```
