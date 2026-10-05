+++
date = '2026-10-02T14:40:00+08:00'
draft = false
title = 'Docker Compose 从零到实战：把多容器应用变成可复现的开发环境'
+++

单独运行一个 Nginx 或 Redis 容器时，`docker run` 已经足够；但一个真实应用往往同时需要应用进程、数据库、缓存、消息队列、对象存储，以及它们各自的数据目录和启动条件。把这些命令手工记在终端历史里，环境很快就变得不可复现：某台机器忘了挂卷，另一台机器端口冲突，第三台机器又在服务尚未就绪时启动了应用。

**Docker Compose 的价值是把这份“多容器环境的期望状态”声明为一个 YAML 文件。**开发者执行同一条命令，Compose 据此创建网络、数据卷和容器，并以服务名组织它们。它适合本地开发、集成测试、演示环境和单机部署；它并不是跨多台主机的集群调度器，生产环境还需要考虑镜像供应链、密钥、监控、备份、扩缩容和高可用。

本文使用两个真实配置作为贯穿案例：`D:\Project\git\me\ragent\resources\docker\local-dev-stack.compose.yaml` 的本地中间件栈，以及 `D:\Project\git\me\ragent\resources\docker\graphrag\lightrag-neo4j-stack.compose.yaml` 的 Neo4j + LightRAG 栈。示例只解释配置机制和本机开发适用范围，**不会展示或要求粘贴任何 API Key**。

## 先建立正确的心智模型

Compose 文件描述的不是“按顺序执行的一串 Docker 命令”，而是一个**项目（project）**。项目由服务、网络、卷、配置和密钥等资源构成。最常用的三类是：

| 对象 | 解决的问题 | 典型 Compose 字段 |
| ---- | ---------- | ---------------- |
| 服务（service） | 一个可运行的容器实例应长什么样 | `image`、`build`、`environment`、`ports` |
| 网络（network） | 哪些容器能互相发现、如何隔离 | `networks`、服务名 DNS |
| 卷（volume） | 容器销毁后哪些数据仍要保留 | 顶层 `volumes`、服务的 `volumes` |

可以把它想成下面的关系：

```text
Compose project
├─ services
│  ├─ postgres / redis / 应用容器
│  └─ 每个服务连接一个或多个网络、挂载零个或多个卷
├─ networks
│  └─ 默认网络与按用途拆分的隔离网络
└─ volumes
   └─ 数据库数据、对象存储数据、应用工作目录
```

服务名同时是 Compose 网络中的 DNS 名。例如 `rmqbroker` 可以通过 `rmqnamesrv:9876` 找 NameServer；LightRAG 可以通过 `neo4j:7687` 找 Neo4j。这里的 `rmqnamesrv` 与 `neo4j` 是**容器网络内的地址**，不是宿主机地址，更不是 `localhost`。

### Compose、镜像和容器分别负责什么

- **Dockerfile** 定义如何构建镜像。例如 GraphRAG 栈中的 `neo4j-gds.Dockerfile` 把经过验证的 GDS 插件固化进 `ragent/neo4j-gds:5.26-2.13.11` 镜像。
- **镜像** 是只读模板，包含程序与运行环境。
- **容器** 是镜像的一次运行实例，具有自己的进程、可写层、网络命名空间和挂载点。
- **Compose** 把多个容器及其连接关系编排在一起；`build` 指向 Dockerfile，`image` 则指定运行或构建后使用的镜像名。

因此，改 Dockerfile 后通常要 `docker compose build` 或 `docker compose up --build`；只改运行时环境变量、端口或卷，Compose 会在 `up` 时判断并按需重建受影响的容器。

### YAML 是声明，不是配置模板语言

缩进决定 YAML 结构，列表项的 `-` 和映射的 `:` 都不能随意省略。Docker Compose v2 使用 Compose Specification，现代文件通常不再需要顶层 `version`。一个最小但完整的示例是：

```yaml
name: demo

services:
  web:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"
```

它声明项目名为 `demo`，并希望有一个名为 `web` 的服务。执行 `docker compose up -d` 后，Compose 会创建默认网络并运行 Nginx。`8080:80` 的左侧是宿主机端口，右侧是容器端口；浏览器访问的是 `http://localhost:8080`。

## 从 Compose 文件到运行中的栈

以下命令以 Compose v2 插件为准，因此写作 `docker compose`（中间有空格），而不是旧的独立程序 `docker-compose`。先进入 Compose 文件所在目录，避免 `.env` 和相对路径被错误解析：

```bash
cd D:\Project\git\me\ragent\resources\docker
docker compose -f local-dev-stack.compose.yaml config
docker compose -f local-dev-stack.compose.yaml up -d
docker compose -f local-dev-stack.compose.yaml ps
```

`config` 极其重要：它会解析变量替换、合并文件和默认值，输出 Compose 实际看到的配置。分享日志或贴到工单前要审查输出，因为解析后的环境变量可能包含敏感值；可用 `--no-interpolate` 辅助检查变量占位符。`up -d` 在后台创建并启动资源，`ps` 显示服务状态与健康状态。

常用的日常工作流如下：

```bash
# 持续查看某个服务的日志；-f 表示跟随输出
docker compose -f local-dev-stack.compose.yaml logs -f postgres

# 在已运行容器中执行诊断命令，而不是猜测容器名
docker compose -f local-dev-stack.compose.yaml exec postgres psql -U postgres -d ragent

# 查看最终展开的服务名、端口与健康状态
docker compose -f local-dev-stack.compose.yaml ps

# 停止并删除容器与项目网络，保留命名卷中的数据
docker compose -f local-dev-stack.compose.yaml down

# 连同命名卷一起删除；数据库、队列或索引数据会不可恢复地丢失
docker compose -f local-dev-stack.compose.yaml down -v
```

不要把 `down -v` 当作普通“重启”命令。对于 PostgreSQL、Neo4j、Milvus 一类有状态服务，它相当于删除本地实验数据。遇到问题的排查顺序通常是：`config` 确认声明、`ps` 看状态、`logs` 看失败原因、`exec` 在容器内验证连接，再决定是否重建或清卷。

## 服务：一个容器运行说明书

服务定义位于 `services:` 下。以本地开发栈中的 PostgreSQL 为例，它有镜像、环境变量、端口、卷、健康检查和重启策略等组成部分：

```yaml
services:
  postgres:
    image: pgvector/pgvector:0.8.5-pg17-trixie
    environment:
      POSTGRES_DB: ragent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set it in .env}
    ports:
      - "5432:5432"
    volumes:
      - ragent-postgres-data:/var/lib/postgresql/data
      - ../database/schema_pg.sql:/docker-entrypoint-initdb.d/01-schema_pg.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ragent"]
```

上面是为了讲解变量管理而做的等价教学写法；实际案例当前将本机开发参数直接写入 Compose 文件，并额外挂载初始化脚本与初始化数据脚本。不要把这种开发便捷性照搬到生产。特别是数据库密码、Redis `requirepass`、对象存储访问凭据都应在生产改为受管密钥，而不是提交到仓库或命令历史。

### `image` 与 `build`

`image` 从镜像仓库获取或使用本地已有镜像，最好固定到已验证的版本标签，甚至 digest。`latest` 只是一个会移动的标签，不能代表可复现版本。

GraphRAG 的 Neo4j 服务同时写了：

```yaml
image: ragent/neo4j-gds:5.26-2.13.11
build:
  context: .
  dockerfile: neo4j-gds.Dockerfile
```

这表示构建上下文是当前目录、构建规则在指定 Dockerfile 中、产物使用指定镜像名。首次使用 `docker compose up --build` 或 `docker compose build neo4j` 时会构建本地镜像；后续若 Dockerfile 和上下文未变，可以复用缓存。构建上下文过大既慢又可能把不应进入镜像的文件发送给 Docker daemon，所以应使用 `.dockerignore`，并让 `context` 尽可能小。

### `command`、`entrypoint` 与运行时覆盖

镜像的 Dockerfile 可定义默认 `ENTRYPOINT` 和 `CMD`。Compose 中：

- `command` 通常覆盖默认 CMD，适合传业务启动参数；本地 Redis 服务以数组形式传入 `redis-server`、持久化和认证参数。
- `entrypoint` 覆盖镜像入口程序，影响更大，适合确实需要接管启动流程的场景。

GraphRAG 的 LightRAG 服务使用 `/bin/sh -ec` 作为 `entrypoint`：先循环确认 `neo4j:7687` 的 Bolt 端口可连接，再 `exec python -m lightrag.api.lightrag_server`。这里的 `exec` 很关键：它让应用进程成为 PID 1，从而能正确接收停止信号。这个等待门闩是对 Compose 启动依赖的补强，不应被误解为所有服务都必须复制的一段 shell 脚本；优先使用服务自身的重试和健康接口。

### 为什么不要轻率使用 `container_name`

案例中使用了 `container_name: ragent-postgres` 等固定名称，方便本机用 `docker logs` 查找。但 Compose 原本会基于“项目名-服务名-序号”生成容器名。固定 `container_name` 有两个代价：不同项目容易撞名，并且该服务无法用 `docker compose up --scale 服务名=2` 扩容。教程和生产模板一般建议让 Compose 自动命名，日常操作用 `docker compose logs 服务名` 与 `docker compose exec 服务名` 代替依赖容器名。

## 网络、服务发现与端口：最常见的混淆点

Compose 会为项目创建默认 bridge 网络；所有未显式指定网络的服务都加入它，并可直接以服务名互访。**容器间通信不需要也不应该为了内部访问而发布端口。**

| 访问方向 | 正确写法 | 原因 |
| -------- | -------- | ---- |
| 浏览器访问 Nginx | `localhost:8080` | 走宿主机已发布的端口 |
| 应用容器访问 PostgreSQL | `postgres:5432` | 走项目内部 DNS 和容器端口 |
| LightRAG 容器访问 Neo4j | `neo4j:7687` | 两者在默认 Compose 网络中 |
| 容器访问宿主机 PostgreSQL | `host.docker.internal:5432` | 需要显式解决宿主机网关解析问题 |

`local-dev-stack.compose.yaml` 为 RocketMQ 专门声明了 `rocketmq` bridge 网络，`rmqnamesrv` 和 `rmqbroker` 都连接其中，因此 Broker 的 `NAMESRV_ADDR` 可以是 `rmqnamesrv:9876`。这是一种按子系统隔离的方式：不在该网络的服务不能直接通过该网络访问 RocketMQ。需要一个服务同时接入两个边界时，可给它声明多个网络，并谨慎区分对外、数据和管理面网络。

### `ports`、`expose` 与 `network_mode`

- `ports: ["宿主机端口:容器端口"]` 把端口发布给宿主机。默认绑定所有接口；只希望本机访问时可写 `127.0.0.1:5432:5432`，避免意外暴露到局域网或公网。
- `expose` 只声明容器间可用端口，不做宿主机发布；在同一 Compose 网络中，即使不写 `expose`，服务通常仍能访问目标端口，它更多是文档化意图。
- `network_mode: "service:rmqbroker"` 让一个服务共享另一个服务的网络命名空间。案例中的 `rocketmq-dashboard` 共享 Broker 网络，因此它不独自声明 `ports`，而是使用 Broker 已发布的端口。此模式耦合很强、端口也会共享；只在确有必要时采用。

GraphRAG 栈的 LightRAG 默认使用 `POSTGRES_HOST=host.docker.internal`，并通过 `extra_hosts: ["host.docker.internal:host-gateway"]` 让 Linux Docker 也能解析宿主机网关。它的用途是**复用宿主机上已经运行的 PostgreSQL**，而非在两个 Compose 栈之间建立自动网络。若 PostgreSQL 实际部署在另一台机器、容器或托管服务中，应改用那一端明确的地址、TLS 与访问控制；不要把 `host.docker.internal` 当成通用生产域名。

## 卷与持久化：容器可删，数据不能随意删

容器可写层会随容器删除而消失。数据库、对象存储和索引的数据必须放在挂载中。Compose 常见的挂载有三种：

| 类型 | 写法示例 | 适合什么 | 生命周期 |
| ---- | -------- | -------- | -------- |
| 命名卷 | `pg-data:/var/lib/postgresql/data` | 数据库和长期状态 | 独立于容器，`down` 默认保留 |
| bind mount | `./config:/app/config:ro` | 本机源码、配置、初始化 SQL | 直接使用宿主机路径 |
| tmpfs | `type: tmpfs` | 临时且不落盘的数据 | 随容器停止消失 |

案例的顶层：

```yaml
volumes:
  ragent-postgres-data:
  ragent-redis-data:
  rustfs-data:
  etcd-data:
  milvus-data:
```

并在各服务中把它们挂到对应数据目录。这使得 `postgres` 容器被重建后数据库文件仍然存在。PostgreSQL 还把 schema 与初始数据 SQL 只读挂到 `/docker-entrypoint-initdb.d/`：这类官方镜像初始化脚本通常只在**数据目录首次为空**时执行。因此修改 SQL 后，已初始化的命名卷不会自动重新执行脚本；应通过迁移工具、显式 SQL 或在确认可丢数据的开发环境清空相应卷来处理。

卷不是备份。命名卷能避免“删容器就丢数据”，却不能替代数据库逻辑备份、异机备份、恢复演练和版本迁移。需要查找实际卷名时使用 `docker volume ls`；Compose 会按项目名加前缀，除非特别声明外部卷名。

## 环境变量与 `.env`：插值和注入是两回事

这两个概念常被混在一起：

1. **Compose 插值**：Compose 在读取 YAML 时把 `${VAR}` 替换为值。来源可包括当前 shell、同目录 `.env` 或 `--env-file` 指定文件。
2. **容器环境变量**：`environment:` 或 `env_file:` 把变量传入容器进程。它们未必等同于 Compose 自己用于插值的变量来源。

GraphRAG 配置使用了三种安全且可读的插值形式：

```yaml
environment:
  LLM_BINDING: "${LLM_BINDING:-openai}"
  NEO4J_PASSWORD: "${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"
  POSTGRES_HOST: "${POSTGRES_HOST:-host.docker.internal}"
```

- `${VAR:-default}`：未设置或为空时使用默认值，适合非敏感、可预测的开发参数。
- `${VAR:?message}`：变量不存在或为空时直接报错，适合密码、令牌等绝不能静默回退的必填项。
- `${VAR}`：直接替换；如果未设置，容易得到空值或警告，必须结合应用含义审查。

该目录的 `.env.example` 是变量清单和模板；开发者应复制为未提交的 `.env`，填入本机真实值，再启动 Compose。`.env` 不是安全保险箱：它是明文文件，可能被备份、日志或 `docker inspect` 暴露。生产环境优先使用云密钥管理、CI/CD 的受保护变量或 Compose `secrets`，并限制谁能读取运行时配置。无论哪种方式，都不要把 API Key、真实密码写入 Markdown、Git 提交、截图或 `docker compose config` 的公开输出。

`environment` 可写成映射或列表。映射更容易审查：

```yaml
environment:
  APP_ENV: production
  LOG_LEVEL: info
```

本地开发栈中的部分固定账号、密码和映射端口是为了快速拉起依赖服务的**开发便利配置**。它不具备生产所需的账号轮换、最小权限、网络边界和 TLS，切勿把其值或端口暴露策略直接复制到公网环境。

## 启动顺序、就绪状态与健康检查

`depends_on` 表达服务依赖关系，但“容器已启动”“端口可连接”“应用真正可用”是三个不同状态。

```text
容器 created → 进程 started → 端口 listening → 依赖初始化完成 → healthy
```

短列表写法：

```yaml
depends_on:
  - postgres
```

它只保证 Compose 按依赖顺序创建/启动，并不保证 PostgreSQL 已能接受查询。长写法能将依赖条件说明得更准确：

```yaml
depends_on:
  neo4j:
    condition: service_healthy
```

GraphRAG 的 LightRAG 就这样依赖 Neo4j；本地开发栈的 RocketMQ Broker 同样等待 NameServer `service_healthy`。前提是被依赖服务定义了真正有意义的 `healthcheck`。例如 PostgreSQL 使用 `pg_isready`，Redis 使用认证后的 `redis-cli ... PING`，Neo4j 使用认证后的 `cypher-shell` 查询。这些探针检查的是服务最基本的可用能力，而不只是“进程还活着”。

健康检查可调参数为：

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -fsS http://localhost:8080/health || exit 1"]
  interval: 20s
  timeout: 5s
  retries: 5
  start_period: 40s
```

- `interval` 是检查间隔，`timeout` 是单次最大等待时间。
- `retries` 是连续失败多少次才标记 `unhealthy`。
- `start_period` 给予冷启动宽限期，其间失败不会立刻计数，适合 Java、数据库、模型服务等启动慢的进程。
- `CMD` 直接执行数组命令；`CMD-SHELL` 允许 `&&`、重定向和变量展开，但也引入 shell 解析复杂度。

请注意：Docker 将容器标成 `unhealthy`，默认**不会自动重启它**。`restart` 是基于容器退出的重启策略，而不是基于健康检查失败的修复器。应用仍应实现连接重试、超时与优雅降级；依赖在运行期重启、网络短暂中断和数据库故障都会发生，不能只靠启动时的 `depends_on`。

## 重启策略、Profile 与可选服务

案例普遍使用：

```yaml
restart: unless-stopped
```

它表示容器异常退出或 Docker daemon 重启后会重启，除非操作者明确停止过它。常见策略的边界如下：

| 策略 | 行为 | 常见用途 |
| ---- | ---- | -------- |
| `no` | 不自动重启 | 一次性任务、调试容器 |
| `on-failure[:N]` | 非零退出码时有限/无限重试 | 可重试的批处理任务 |
| `always` | 无论退出原因都倾向于重启 | 必须常驻的单机服务 |
| `unless-stopped` | 类似 `always`，但尊重人工停止 | 本机长期开发依赖 |

重启策略可能把“启动即退出”的配置错误变成刷屏的重启循环，所以第一步永远是 `logs` 找根因，而非盲目重启。

本地开发栈将 `etcd`、`milvus-standalone` 和 `milvus-attu` 放进 `milvus` profile：

```yaml
services:
  milvus-standalone:
    profiles: ["milvus"]
```

默认 `up` 不启动 profile 服务；需要向量数据库时才执行：

```bash
docker compose -f local-dev-stack.compose.yaml --profile milvus up -d
```

这让“常用的 PostgreSQL、Redis、对象存储、RocketMQ”与“体积和资源都更重的 Milvus 组件”可以按需启动。Profile 是同一份开发环境中的功能开关，不是权限隔离，也不会替代不同环境的配置管理。

## 多文件覆盖：从基础栈派生本地与生产差异

不要通过复制一整份 Compose 文件维护 dev、test、prod 三个版本。Compose 可以按顺序合并多个文件，后面的文件覆盖或补充前面的字段：

```bash
docker compose \
  -f compose.yaml \
  -f compose.dev.yaml \
  up -d
```

一个合理的基本文件只保留稳定声明：服务镜像、内部网络、数据卷、健康检查；开发覆盖文件再加入源码 bind mount、调试端口、热更新命令和较宽松的日志。示意：

```yaml
# compose.yaml
services:
  api:
    image: example/api:1.4.2
    environment:
      APP_ENV: production

# compose.dev.yaml
services:
  api:
    environment:
      APP_ENV: development
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - ./:/workspace
```

合并规则并非所有字段都只是“后者完全替换前者”：映射往往按键合并，列表字段的行为则依字段而定，路径还会相对**第一份 Compose 文件**解析。每次调整覆盖文件后都要执行同一组 `-f` 参数的 `docker compose config`，以最终展开结果为准。若只是切换变量，优先 `--env-file .env.dev`；若要切换端口、挂载、服务拓扑，才使用覆盖文件。

## 真实案例拆解：本地中间件栈

`local-dev-stack.compose.yaml` 是一个面向单机开发的依赖集合，项目名为 `ragent-local-dev`。它包含：

- PostgreSQL（带 pgvector）、Redis、RustFS：均有命名卷和健康检查，适合让本地数据跨容器重建保存。
- RocketMQ NameServer、Broker 与 Dashboard：NameServer 和 Broker 加入独立 `rocketmq` 网络，Broker 等待 NameServer 健康；Dashboard 通过 `network_mode: service:rmqbroker` 共享 Broker 网络。
- 可选的 etcd、Milvus Standalone、Attu：由 `milvus` profile 控制，只有需要向量检索时才启动。

此配置很好地展示了“一个 Compose 文件可同时描述核心依赖、服务发现、数据卷和可选重型组件”。但它的绑定端口较多，部分账号或认证参数是本机开发默认值，RocketMQ Broker 还包含面向本机连通性的地址设置。因此它的适用范围是**受信任开发机上的本地依赖栈**，不应直接作为服务器或公网部署清单。

启动前也要检查端口占用，尤其是数据库与中间件默认端口：

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in 5432, 6379, 9000, 9001, 9876, 19530 } |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

如果端口已被本机服务占用，优先决定“复用已有服务”还是“修改宿主机左侧端口”。不要修改容器右侧端口后却忘记同步服务内部地址；容器间仍应访问它的服务名和容器端口。

## 真实案例拆解：Neo4j + LightRAG GraphRAG 栈

`graphrag/lightrag-neo4j-stack.compose.yaml` 只增加 Neo4j 与 LightRAG 两个容器：图数据由 Neo4j 保存，LightRAG 的 KV、向量和文档状态复用宿主机已存在、并安装了 pgvector 的 PostgreSQL。顶层 `networks.default.name: lightrag-net` 给默认网络固定名字，便于识别；三个命名卷分别保存 Neo4j 数据、Neo4j 日志与 LightRAG 工作目录。

启动该栈的安全流程是：

```bash
cd D:\Project\git\me\ragent\resources\docker\graphrag
# 复制模板为本机未提交的 .env，并在本机填写必填密钥和密码
docker compose -f lightrag-neo4j-stack.compose.yaml config --no-interpolate
docker compose -f lightrag-neo4j-stack.compose.yaml up -d --build
docker compose -f lightrag-neo4j-stack.compose.yaml ps
docker compose -f lightrag-neo4j-stack.compose.yaml logs -f neo4j lightrag
```

其中 `--build` 确保首次构建本地 Neo4j GDS 镜像；之后仅在 Dockerfile 或构建上下文变化时需要。`ps` 中两个服务达到 `healthy` 才表示这份 Compose 定义的就绪条件已满足。该栈设置了 LightRAG 的 Web/API 和 Neo4j Browser/Bolt 端口，目的是本机开发与验证；服务器部署时应通过反向代理、访问控制、TLS 和最小开放端口来替代直接暴露。

这个案例还展示了几个值得复用的原则：

1. 必填秘密使用 `${VAR:?错误提示}`，错误应该在启动时明确失败，而不是带着空密码运行。
2. Neo4j 用 `service_healthy`，LightRAG 又在入口脚本中检查 Bolt 端口，降低独立容器重启绕过启动顺序时的竞态概率。
3. 容器访问宿主 PostgreSQL 使用 `host.docker.internal` 与 `host-gateway` 映射；这明确表明 PostgreSQL 不属于本 Compose 项目，应单独验证网络、账号权限与 pgvector 扩展。
4. LightRAG 镜像的标签通过变量提供默认值。开发试验可用默认标签，但生产应固定到经过验证的具体 tag 或 digest，并建立升级验证流程。

## 常见故障的定位方法

### `docker compose up` 报变量未设置

先确认当前目录、Compose 文件位置和 `.env` 位置。`.env` 自动加载通常以 Compose 项目目录为准，不是任意 shell 当前目录都一定相同。用 `--env-file` 可以消除歧义：

```bash
docker compose \
  --env-file D:\Project\git\me\ragent\resources\docker\graphrag\.env \
  -f D:\Project\git\me\ragent\resources\docker\graphrag\lightrag-neo4j-stack.compose.yaml \
  config --no-interpolate
```

若报错来自 `${VAR:?message}`，不要为了让启动通过而填一个随意值；先确认该变量对应的外部服务、账号或密钥从何处获取，并仅在本机受保护的文件或密钥系统中配置。

### 服务一直 `unhealthy` 或反复重启

执行下面两步，把“容器没起”与“探针失败”分开：

```bash
docker compose -f local-dev-stack.compose.yaml ps
docker compose -f local-dev-stack.compose.yaml logs --tail=200 redis
```

然后检查：健康检查命令在镜像中是否存在；认证参数是否与服务一致；首次初始化是否需要更长 `start_period`；数据卷中的旧数据是否与新版本兼容；宿主机资源是否不足。对于一次性启动脚本，使用 `docker compose run --rm 服务名 命令` 可以创建临时容器进行复现；它和 `exec` 的区别是前者新建容器，后者进入已运行容器。

### 应用能在宿主机连通，容器里却连不上

最常见错误是在容器内填写 `localhost`。容器中的 `localhost` 指向该容器自己。若目标是同一 Compose 项目中的 PostgreSQL，应填写 `postgres:5432`；若目标确实运行在宿主机，才考虑 `host.docker.internal:5432`，并在 Linux 上验证 `extra_hosts` 或 Docker 版本支持。可在容器内执行 DNS 或端口测试：

```bash
docker compose -f lightrag-neo4j-stack.compose.yaml exec lightrag \
  python -c "import socket; print(socket.gethostbyname('neo4j'))"
```

### 端口映射失败或访问到了错误服务

先用 `docker compose ps` 看 Compose 实际发布的端口，再用系统工具查谁占用了宿主机端口。记住 `5432:5432` 不表示所有客户端都该访问 `localhost:5432`：容器内的客户端仍应访问 `postgres:5432`。如果仅供本机调试，显式绑定 `127.0.0.1` 能减少暴露面。

### 改了环境变量或镜像却没有生效

先查看展开配置和运行中的容器：

```bash
docker compose -f lightrag-neo4j-stack.compose.yaml config
docker compose -f lightrag-neo4j-stack.compose.yaml up -d --force-recreate lightrag
```

如果改的是 Dockerfile 或构建上下文，用 `up -d --build`。如果改的是初始化 SQL，请回到“初始化脚本只首次执行”的规则，选择迁移或仅在可丢弃开发数据时重建对应卷。不要用删除所有卷作为默认修复手段。

## Compose 的生产边界

Compose 可以用于单机生产部署，但文件“能启动”不等于“具备生产质量”。至少要补齐下列能力：

- **版本与供应链**：固定镜像 tag/digest，扫描漏洞，构建后签名或保存 SBOM，避免长期依赖 `latest`。
- **秘密管理**：使用密钥管理系统或受保护的部署变量；限制 `.env` 权限，日志与诊断输出脱敏，定期轮换密码和令牌。
- **网络暴露**：只发布必要端口，数据库、Redis、消息队列通常不直接暴露公网；通过防火墙、私有网络、反向代理和 TLS 控制入口。
- **数据可靠性**：命名卷不等于备份。制定数据库与对象存储的备份、保留、恢复演练和升级迁移方案。
- **资源与可观测性**：设置 CPU/内存约束或运行环境配额，收集日志、指标、健康状态和告警；观察重启循环而不是掩盖它。
- **高可用与扩缩容**：单机 Compose 不会跨主机故障转移。需要多副本、滚动发布、服务发现与跨节点调度时，应评估 Kubernetes、Nomad、云容器平台或受管数据库等方案。

尤其是案例中公开的开发端口、开发账号、单节点存储与 `unless-stopped`，仅解决“本机方便启动”。它们不是一套可直接复制到公网的安全基线。

## 本文要点

- Compose 以项目为单位声明服务、网络和卷；服务名就是内部 DNS 名，内部通信应使用服务名和容器端口。
- `ports` 负责宿主机入口，命名卷负责容器外持久化；发布端口与持久化数据都要按最小必要原则设计。
- `.env` 参与 Compose 插值，`environment` 把变量交给容器；必填秘密使用失败即报错的变量表达式，并避免将真实值提交或输出。
- `depends_on` 与 `healthcheck` 能改善启动编排，但不能替代应用运行期的重试、超时和容错；`unhealthy` 也不会天然触发重启。
- `profiles` 用于按需启动可选组件，多个 Compose 文件用于管理拓扑差异；每次合并后以 `docker compose config` 的最终结果为准。
- 本地中间件栈和 GraphRAG 栈都是很好的开发环境案例，但生产还必须补足密钥、网络、备份、监控、资源和高可用设计。
