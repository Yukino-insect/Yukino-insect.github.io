+++
date = '2026-10-02T14:30:00+08:00'
draft = false
title = 'Docker 网络、端口与数据持久化：从容器互联到安全备份'
+++

容器能启动，只是 Docker 入门的开场白；服务能被正确访问、重建后数据仍在、故障时知道从哪里查，才算真正可用。本篇把网络和存储放在同一张地图中讲清楚：**网络决定谁能与谁通信，端口决定外部入口，挂载决定哪些状态能跨容器存活。**

先记住三个结论。

- 同一 Docker 网络中的服务应通过**服务名和容器端口**互访，而不是通过宿主机 IP 或映射端口。
- `ports` 只是在宿主机与容器之间建立入口；它不是容器之间通信所必需的配置，也不是安全策略本身。
- 容器可写层会随容器删除而消失。数据库、上传文件、索引等状态必须有明确的 volume、bind mount 或外部存储方案，并有与数据类型相匹配的备份流程。

## 一、先建立一张通信地图

以一个常见的 Web 系统为例：浏览器访问 `web`，`web` 调用 `api`，`api` 再连接 PostgreSQL 与 Redis。正确的数据流通常是：

```text
浏览器
  │  http://宿主机:8080
  ▼
宿主机发布端口 8080:80
  ▼
web 容器 ── http://api:8080 ──> api 容器
                                      ├── postgres:5432
                                      └── redis:6379
```

`web` 访问 `api:8080` 时，`8080` 是 **api 容器内**监听的端口；即使 Compose 把它发布为 `18080:8080`，同网络容器也不该改去访问 `api:18080`。发布端口是给宿主机或网络外客户端使用的另一条路径。

### 容器网络的底层轮廓

Linux 上，Docker 通常为每个使用 bridge 网络的容器创建独立的 network namespace：它有自己的网卡、路由表、iptables/nftables 相关规则和回环接口。容器中的 `eth0` 通过一对 veth 与宿主机的 Linux bridge 相连；容器访问外网时，Docker 通常再做源地址转换（NAT）。因此容器看似拥有一台小机器的网络视图，却仍由宿主机内核转发数据包。

这解释了几件初学者容易困惑的事：

- 容器内的 `127.0.0.1` 是**该容器自己**，不是宿主机，也不是另一个容器。
- 容器 IP 不是稳定接口。重建、扩缩容或重新接网后都可能改变；应使用 DNS 名称。
- `EXPOSE 8080` 只是镜像元数据和文档提示，不会打开宿主机端口；真正发布端口的是 `docker run -p` 或 Compose 的 `ports`。

Docker Desktop（Windows/macOS）会把 Linux 容器运行在一个 Linux VM 中，路径映射、宿主网络和性能行为会与原生 Linux 有差异。概念相同，但不要把 Linux 上看到的网卡名、IP 或 `--network host` 行为机械搬过去。

## 二、网络驱动与隔离边界

### bridge：单机服务的默认选择

`bridge` 是单机 Docker 最常用的网络。Compose 会自动创建一个项目默认网络；同一 Compose 文件中的服务默认接入它，并可按服务名解析彼此。更推荐显式定义**用户自定义 bridge 网络**，而非依赖 Docker 自带的 `bridge`：前者提供更好的内置 DNS 和隔离边界。

```yaml
services:
  api:
    image: example/api:1.0
    networks:
      - app

  postgres:
    image: postgres:17
    networks:
      - app

networks:
  app:
    driver: bridge
```

此时 `api` 可连接 `postgres:5432`，但 PostgreSQL 不必发布端口。把不同职责拆到多个网络，能让“能否连接”成为默认拒绝，而不是事后祈祷。

```text
internet → web ── public
                  └─ private ── api ── data
                                      └─ postgres
```

`web` 同时接入 `public` 与 `private`，`api` 接入 `private` 与 `data`，数据库只接入 `data`。网络不是完整的应用层零信任方案，但它是非常有效的第一道可见边界。

### host、none、overlay 和共享网络栈

| 模式 | 含义 | 适用与边界 |
| ---- | ---- | ---------- |
| `bridge` | 容器有独立网络命名空间，通过 bridge 转发 | 单机默认选择，适合绝大多数 Compose 服务 |
| `host` | 直接使用宿主机网络命名空间 | Linux 上可减少 NAT，但隔离弱、端口会冲突；`ports` 无意义 |
| `none` | 除 loopback 外不配置网络 | 离线批处理、严格隔离任务；应用不能访问 DNS、数据库或外网 |
| `overlay` | 跨节点的虚拟网络 | Docker Swarm 服务使用；普通单机 Compose 不应把它当作默认方案 |
| `service:xxx` | 与另一个服务共享同一网络命名空间 | sidecar 等少数场景；二者共享 IP、端口和 `localhost` |

项目的 RocketMQ Compose 使用了 `network_mode: "service:rmqbroker"`：Dashboard 与 Broker 共用网络栈，因此 Dashboard 的 `8082` 需要从 **Broker 服务**的 `ports` 发布。这是一个有意的特殊设计，不表示普通业务服务都该这样写。共享网络栈会让端口冲突、可观测性和隔离边界更复杂；没有明确 sidecar 理由时，坚持 bridge 网络即可。

`host` 也不是“性能开关”。它会让进程直接占用宿主机端口，容器内 `localhost` 变成宿主机，安全边界明显缩小；Docker Desktop 上其实现还受 VM 限制。只有确实需要宿主网络、并已审查端口与权限时才使用。

## 三、端口发布：入口，而不是互联方式

Compose 最常见的短语法是：

```yaml
ports:
  - "127.0.0.1:15432:5432"
  - "8080:8080"
```

第一行表示仅在宿主机回环地址监听 `15432`，转发到容器的 `5432`；本机开发工具可连，局域网机器不能直接连。第二行未指定监听地址，通常会发布到宿主机所有地址（IPv4/IPv6 行为还受 Docker 和系统配置影响）。生产环境中，数据库、Redis、管理面板通常不应使用后一种写法。

| 写法 | 外部含义 | 容器间访问 |
| ---- | -------- | ---------- |
| `"8080:80"` | 宿主机 `8080` 转发到容器 `80` | 仍使用 `服务名:80` |
| `"127.0.0.1:8080:80"` | 仅本机可访问 | 仍使用 `服务名:80` |
| `expose: ["80"]` | 文档性声明，不发布到宿主机 | 同网络服务本来即可访问 `80` |
| 不写 `ports` | 没有宿主机入口 | 同网络服务仍可访问监听端口 |

可用以下命令确认事实，而不要凭 YAML 猜测：

```bash
docker compose ps
docker port <容器名>
docker inspect <容器名> --format '{{json .NetworkSettings.Ports}}'
```

如果 `-p 8080:80` 失败，先检查宿主机端口占用，而不是反复重启容器。若应用只绑定容器内 `127.0.0.1:8080`，即使发布端口也可能无法转发；服务一般需要监听 `0.0.0.0`，再由 Docker 网络边界控制可达性。

## 四、DNS、服务发现与 Compose 的正确用法

用户自定义网络中 Docker 内置 DNS 会把服务名解析为该网络上的容器地址。Compose 的服务名是最可靠的默认主机名；`container_name` 不该承担服务发现职责，因为它妨碍扩缩容，并容易跨项目重名。

```yaml
services:
  worker:
    image: example/worker:1.0
    environment:
      DATABASE_URL: postgresql://app:${POSTGRES_PASSWORD}@postgres:5432/app
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:17
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 12
```

`depends_on` 只控制 Compose 启动顺序；带 `service_healthy` 时会等待健康检查通过，却仍不能替代应用自身的重试、超时和幂等初始化。数据库刚刚能响应 TCP 或健康命令，不等于迁移、权限配置和业务数据都已就绪。

Milvus 资源正是服务名互联的实例：`ETCD_ENDPOINTS=etcd:2379`、`MINIO_ADDRESS=rustfs:9000` 与 `MILVUS_URL=milvus-standalone:19530` 都指向容器内网络地址；它们和 `ports` 无关。把这些值改成 `localhost` 会失败，因为 `localhost` 指向调用方容器。

### 容器访问宿主机，别猜 IP

容器需要连接宿主机上未容器化的服务时，Docker Desktop 通常提供 `host.docker.internal`。原生 Linux 可明确添加：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

LightRAG 资源采用了这一模式，用 `POSTGRES_HOST=host.docker.internal` 连接宿主 PostgreSQL，并同时设置 `extra_hosts` 保证 Linux 可解析。它是“渐进迁移”的实用方案，但会跨过 Compose 内部网络边界：要限制宿主数据库监听地址、账户权限和防火墙，长期仍更建议把强耦合服务纳入同一受控网络。

### 两个网络之间不会自动相通

项目里 RocketMQ 显式使用 `rocketmq` 网络，而没有声明网络的 PostgreSQL、Redis、RustFS 则在 Compose 默认网络中。`rmqbroker` 不能天然解析或连接默认网络中的服务；这是隔离，不是 Docker 出错。若一个服务必须作为受控桥梁，应显式接入两个网络，而不是将所有服务塞进一个大网。

```yaml
services:
  api:
    networks: [backend, data]
  postgres:
    networks: [data]

networks:
  backend: {}
  data:
    internal: true
```

`internal: true` 会阻止该网络获得默认的外部访问路径，适合纯后端数据网；它不替代数据库鉴权、TLS 或最小权限账户。

## 五、三种挂载：持久化、开发映射与内存临时文件

镜像层是只读模板，容器自己的可写层只适合临时变更。删除容器时，它通常会消失。Docker 提供三类主要挂载：

| 类型 | 数据实际归属 | 最适合 | 主要注意点 |
| ---- | ------------ | ------ | ---------- |
| named volume | Docker 管理的宿主机存储区 | 数据库、队列、生产持久数据 | 不能因 `down -v` 误删；需要独立备份 |
| bind mount | 指定的宿主机路径 | 源码、配置、开发输入输出 | 宿主路径、UID/GID、权限和跨平台性能会影响容器 |
| `tmpfs` | 内存 | 密钥派生临时文件、缓存、敏感短暂数据 | 重启即丢，消耗内存，不可当持久化介质 |

### named volume：让数据随服务迁移，而不随容器消失

```yaml
services:
  postgres:
    image: postgres:17
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
```

Compose 实际会创建带项目名前缀的 volume。即使 `docker compose down` 删除容器与网络，默认也会保留 named volume；`docker compose down -v`、`docker volume rm` 和激进的 prune 才会删除它。删除之前务必确认目标：

```bash
docker volume ls
docker volume inspect <volume>
docker compose down          # 通常保留 volume
# docker compose down -v     # 会删除本项目声明的 volume，包含数据
```

项目的本地开发栈把 PostgreSQL、Redis、RustFS、etcd、Milvus 分别放进 named volume。这种“一项有状态服务对应一个明确卷”的设计使数据边界可审计。尤其 PostgreSQL 的初始化 SQL 被以 `:ro` bind mount 到 `/docker-entrypoint-initdb.d/`；官方镜像只会在**空的数据目录初始化时**执行这些脚本。已有 `ragent-postgres-data` 后，修改 SQL 再重启不会自动重放——开发重置需要先备份，再明确删除对应开发卷，而不是误以为 Compose 会迁移数据。

### bind mount：宿主机文件直接进入容器

```yaml
services:
  app:
    image: example/app:1.0
    volumes:
      - ./config/app.yaml:/app/config/app.yaml:ro
      - ./uploads:/app/uploads
```

bind mount 会遮住镜像中同一路径原有文件；若把空宿主目录挂到镜像预置的 `/app`，镜像里的应用文件“消失”并不是镜像坏了。配置、证书和初始化 SQL 应尽量加 `:ro`，减少容器反向修改宿主机的机会。它不是 secret 管理方案：宿主机上的文件仍需以文件权限、部署平台 secret 机制或专用密钥服务保护。

Windows/macOS 的 bind mount 还要格外留心共享路径权限和大量小文件的性能。数据库数据目录优先使用 named volume，不要为了“看得见文件”随意 bind 到桌面同步目录；文件锁、换行符、权限和 I/O 语义都可能成为隐蔽故障源。

### tmpfs：明确声明“此处不能保留数据”

```yaml
services:
  app:
    image: example/app:1.0
    tmpfs:
      - /run/app-cache:rw,noexec,nosuid,size=64m
```

它适合可再生缓存或短期敏感中间文件。不要把数据库目录放入 `tmpfs`，除非你明确接受容器停止即数据全失，并已验证内存上限与 OOM 风险。

## 六、权限、数据生命周期与备份

### 所有权不是小问题

容器中的进程以某个 UID/GID 写入挂载目录；在 Linux bind mount 上，这个数字会映射为宿主文件所有者。镜像里以 `root` 运行，往往会让宿主目录出现 root 所有文件；反过来，宿主目录权限不足会导致数据库启动时报 `permission denied`。

解决顺序应当是：查镜像文档确认运行 UID/GID；为目录授予最小所需所有权；在镜像支持时使用 `user: "1000:1000"`；再考虑 rootless Docker 或平台专有的权限映射。不要用 `chmod -R 777` 草率“修复”，那只是把证据与边界一起抹掉。SELinux 主机还可能需要 Docker 支持的挂载标签（如 `:Z`/`:z`）；这是主机安全策略，不应在不了解影响时到处添加。

同样重要的是不要把 `/var/run/docker.sock` 随手挂入业务容器。能控制 Docker socket 的进程通常几乎等同于拥有宿主机高权限；它不是普通“让容器管理容器”的配置项。

### 备份要备“可恢复的数据”，不是随便复制目录

对运行中的数据库直接打包 volume 底层目录，可能得到逻辑不一致的数据。优先使用数据库自身的一致性工具：PostgreSQL 使用 `pg_dump`/`pg_dumpall` 或物理备份；Redis 依据 RDB/AOF 策略做可恢复备份；对象存储用其对象级复制或导出；Milvus、etcd、Neo4j 则遵循各自的快照/备份机制。备份还必须定期恢复演练，否则它只是安慰剂。

下面以 PostgreSQL 逻辑备份为例；重定向由宿主 shell 执行，所以备份文件会落在当前宿主目录：

```bash
docker compose exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > postgres-2026-10-02.dump

docker compose exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d restore_check --clean --if-exists \
  < postgres-2026-10-02.dump
```

真实命令中的用户、数据库名、认证方式须与镜像配置一致；不要把示例开发密码复制到生产 Compose。生产备份还应包含加密、异地副本、保留策略、访问审计和恢复时间目标（RTO/RPO）。卷备份可用于**已停止服务**或已协调一致性快照的场景，例如临时容器把一个 named volume 以只读方式挂入后归档；它不是在线数据库通用替代品。

## 七、排障：按路径而非直觉检查

“连接失败”至少可能是名称、网络归属、监听地址、端口发布、应用就绪、认证或防火墙中的任一环节。按下面顺序检查，效率会高得多。

1. 确认服务状态与端口：`docker compose ps`、`docker compose logs <服务>`。
2. 确认网络成员：`docker network ls`，然后 `docker network inspect <网络名>`。
3. 从**调用方容器**验证 DNS 和 TCP，而不是只在宿主机测试：`docker compose exec <服务> sh -c 'cat /etc/resolv.conf; getent hosts postgres'`。精简镜像可能没有 `getent`、`ping` 或 `curl`，这是镜像裁剪，不代表网络异常。
4. 用业务协议做最终验证，例如 `pg_isready -h postgres -p 5432`、应用健康检查或一次受控 API 请求。
5. 若必须做网络抓包或 DNS 调试，临时启动专用诊断容器并接入目标网络；不要为了调试把工具永久塞进生产镜像。

```bash
docker run --rm -it --network <项目网络> nicolaka/netshoot
```

还要区分两种常见现象：宿主机 `curl localhost:8080` 成功，不能证明另一个容器能访问服务；容器内 `curl localhost:8080` 成功，也只证明它访问到了自己。测试必须站在真实调用方的网络位置上进行。

## 八、一个更安全的 Compose 组合示例

下面的模板保留必要入口：Web 对外、数据库只在内部网络。密码通过环境变量或部署平台 secret 注入，示例没有写入真实值。

```yaml
services:
  web:
    image: example/web:1.0
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      API_BASE_URL: http://api:8080
    networks: [edge, backend]

  api:
    image: example/api:1.0
    environment:
      DATABASE_HOST: postgres
      DATABASE_PORT: "5432"
      DATABASE_PASSWORD: ${DATABASE_PASSWORD:?set DATABASE_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
    networks: [backend, data]

  postgres:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:?set DATABASE_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 12
    networks: [data]

volumes:
  postgres-data: {}

networks:
  edge: {}
  backend: {}
  data:
    internal: true
```

它展示的是原则，而非可以直接上线的万能文件：`127.0.0.1:8080` 适合由同机反向代理接管入口；若要让局域网或公网访问，应由防火墙、反向代理、TLS、认证和访问控制共同决定暴露范围。数据网络的 `internal` 也不能抵消弱密码或应用注入漏洞。

## 九、回到项目资源：哪些配置值得保留，哪些只限开发

项目的 Compose 资源已经体现了不少正确实践：服务间使用 `etcd`、`rustfs`、`neo4j` 等名称；状态服务有独立 named volume；健康检查用于降低启动竞态；LightRAG 的 `extra_hosts: host-gateway` 解决了 Linux 上访问宿主 PostgreSQL 的兼容性问题。这些都是理解 Docker 网络与存储的好样本。

不过它们是本地开发资源，不能原样视为生产安全基线。文件中出现的固定容器名、示例账号口令、数据库和管理 UI 的公开 `ports`，在共享机器、CI 或生产环境中都应收紧：删除不必要端口，敏感配置移出版本库，使用最小权限账户，固定并审查镜像版本，并为每个有状态组件制定独立的备份与恢复计划。RocketMQ 配置里的 `brokerIP1 = 127.0.0.1` 也提醒我们：分布式中间件除了“端口能通”，还会向客户端通告地址；通告地址必须是客户端实际可达的地址，不能想当然地写回环地址。

## 十、本文检查清单

- 容器之间使用 `服务名:容器端口`，从不依赖容器 IP 或宿主映射端口。
- `ports` 只发布必须的入口；数据库和内部管理端口默认不暴露，开发需要时优先绑定 `127.0.0.1`。
- 用多个 bridge 网络表达访问边界；只有确有理由才使用 `host`、`none`、`overlay` 或共享网络栈。
- 每一项状态数据都有明确的 named volume 或外部存储；明白 `down -v` 会删除什么。
- bind mount 对配置优先 `:ro`，并按 UID/GID 处理权限；不把 Docker socket 暴露给普通业务容器。
- 备份使用应用一致性工具，包含恢复演练，而不是在运行中盲目复制数据目录。
- 发生连接故障时，从调用方容器验证 DNS、网络成员、端口监听、健康状态与认证，逐层缩小范围。

掌握这些边界后，你便不会把 Docker 当成一串神秘命令：网络是明确的可达性设计，端口是谨慎暴露的入口，volume 是需要被认真管理的数据资产。
