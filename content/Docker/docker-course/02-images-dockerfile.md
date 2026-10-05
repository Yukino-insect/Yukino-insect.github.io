+++
date = '2026-10-02T14:20:00+08:00'
draft = false
title = 'Docker 镜像与 Dockerfile：从构建原理到可维护镜像'
+++

上一节认识了容器的用途后，下一步就是理解它从哪里来。容器并不是凭空出现的运行环境；它由**镜像**启动，而镜像通常由 `Dockerfile` 按固定步骤构建。掌握这一层，才能避免“镜像能跑但又大、又慢、又不安全”的常见结局——那种把问题推给运气的做法，显然不值得依赖。

本文会建立一条完整链路：构建上下文进入构建器，Dockerfile 生成分层镜像，镜像再以可写容器层运行。随后会结合项目中的 Neo4j GDS Dockerfile，解释缓存、参数、校验和调试等工程细节。

## 一、镜像、层与容器：先建立正确模型

**镜像（image）**是可复用、不可变的文件系统快照及其运行配置。它包含应用文件、运行时、依赖库、默认命令、环境变量等；它不等同于一个已经启动的系统。

**容器（container）**是镜像在某次运行时创建的实例。Docker 在只读镜像层上加一个很薄的可写容器层：程序写入的新文件、日志或临时修改优先落在这个可写层。删除容器时，这一层通常也随之消失；需要保留的数据应使用 volume 或 bind mount，而不是寄望于容器层。

```text
Dockerfile + 构建上下文
          │ docker build
          ▼
  多个只读镜像层 + 镜像配置
          │ docker run
          ▼
  容器：镜像只读层 + 单个可写容器层 + 运行中的进程
```

### 1. 为什么镜像是“分层”的

Dockerfile 中大多数会改变文件系统的指令，例如 `RUN`、`COPY`、`ADD`，都会产生一个新层。后面的层覆盖前面同一路径的文件，但不会从旧层中真正抹去它。

例如下面的写法看似最终没有 `/tmp/build.log`，它仍可能存在于较早的层中：

```dockerfile
RUN curl -o /tmp/build.log https://example.invalid/tool.tar.gz
RUN rm /tmp/build.log
```

第二条指令只在新层记录“删除”，旧层仍保存下载结果。因此，同一逻辑步骤中应一起创建并清理临时文件：

```dockerfile
RUN curl -fsSLo /tmp/tool.tar.gz https://example.invalid/tool.tar.gz \
    && install -m 0755 /tmp/tool.tar.gz /usr/local/bin/tool \
    && rm -f /tmp/tool.tar.gz
```

分层带来两项收益：相同层可被多个镜像共享，未变化的层可命中构建缓存。代价是层的顺序、上下文内容和每一步输入都会影响构建速度与最终体积。

### 2. 镜像名称与不可变性边界

`repository:tag` 只是一个便于人阅读的引用，例如 `neo4j:5.26-community`。标签可以被仓库重新指向另一个镜像，因此“同一个 tag 永远是同一份字节”并不成立。

更严格的发布或生产构建可使用 digest 固定基镜像：

```dockerfile
FROM neo4j:5.26-community@sha256:<已验证的镜像摘要>
```

摘要应从受信任的镜像仓库或你们的制品记录取得，不能凭空填写。开发阶段用 tag 更方便；需要可复现构建、审计或长期维护时，应锁定 digest，并建立更新基镜像的流程。

## 二、`docker build` 到底发送了什么

最容易被忽略的概念是**构建上下文（build context）**。命令最后的路径就是发送给构建器的上下文，不是 Dockerfile 所在目录的装饰品。

```bash
docker build -t demo-web:1.0 .
```

这里的 `.` 中、且未被 `.dockerignore` 排除的文件，才可以被 `COPY` 或 `ADD` 引用。Dockerfile 无法随意读取上下文之外的本机文件；这是构建隔离，也是安全边界。

```text
项目根目录
├─ Dockerfile
├─ package.json
├─ package-lock.json
├─ src/
└─ .dockerignore

docker build .
       └─ 上述未忽略的内容成为构建上下文
          COPY src/ /app/src/   # 合法
          COPY ../secret /app/  # 不合法：在上下文之外
```

### 1. Dockerfile 路径与上下文路径可以不同

`-f` 指定 Dockerfile，最后一个参数仍指定上下文。例如项目外部示例位于 `resources/docker/graphrag/neo4j-gds.Dockerfile`，若当前目录是 `resources/docker`，可写为：

```bash
docker build \
  -f graphrag/neo4j-gds.Dockerfile \
  -t ragent-neo4j-gds:5.26-gds2.13.11 \
  graphrag
```

这个选择意味着 `COPY` 的源路径应相对 `graphrag` 解析。如果 Dockerfile 需要项目根目录内的文件，则应把根目录设为上下文，并相应调整 `COPY` 源路径。盲目把上下文设为很大的仓库根目录，会拖慢构建，也会把不必要甚至敏感的文件暴露给构建器。

### 2. `.dockerignore` 不是可有可无的装饰

`.dockerignore` 在发送上下文前排除文件。它能减少传输量、避免缓存被无关文件频繁打破，也能降低把密钥、构建产物放入镜像的风险；但它不是秘密管理系统，已经进入镜像层或构建日志的敏感数据仍需要按泄露处理。

一个 JavaScript 服务的起点可以是：

```text
.git
.gitignore
node_modules
dist
coverage
*.log
.env
.env.*
!example.env
*.pem
*.key
Dockerfile*
docker-compose*.yml
```

最后两行是否忽略取决于构建是否需要它们；规则要服务于项目，不是照搬模板。修改 `.dockerignore` 也会影响 `COPY` 的输入和缓存结果，构建失败时不要只盯着 Dockerfile。

## 三、Dockerfile 的最小骨架

Dockerfile 是顺序执行的构建说明。指令本身通常大写，参数区分具体工具的规则。下面是一个小型 Node.js 服务的示例：

```dockerfile
FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

ENV NODE_ENV=production
EXPOSE 3000
USER node
CMD ["node", "server.js"]
```

它不是任何服务都可以直接使用的万能答案，但体现了可靠顺序：选择明确基镜像，设定工作目录，先复制依赖清单并安装依赖，再复制经常变化的源码，最后声明运行配置和默认启动命令。

### 1. `FROM`：选择运行世界的起点

`FROM` 指定基础镜像；一个 Dockerfile 至少要有一个 `FROM`。基础镜像决定系统发行版、libc 实现、预装工具和安全更新节奏，因此不要只根据“体积小”选择。

- `alpine` 很小，但使用 musl libc；含原生扩展的程序可能需要额外适配。
- `slim` 通常在兼容性和体积之间较平衡。
- distroless 镜像运行面小，却几乎没有 shell，调试要采用专门方法。
- 官方镜像也需要核验维护者、版本和更新策略，不能因为“官方”便停止审查。

### 2. `RUN`：构建时执行命令

`RUN` 在构建阶段执行命令并写入镜像层。常见的 shell 形式为：

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

这里把 `update`、安装和清理放到同一条 `RUN`，可以避免过期索引和无效层。应让命令在任何一步失败时停止；下载文件时建议使用 `curl -f` 或下载后检查退出码、文件大小/校验和。不要使用 `RUN some-command || true` 把真实失败伪装成成功，除非失败确实是经过设计且已被后续验证的可选分支。

### 3. `COPY` 与 `ADD`：默认选 `COPY`

两者都把构建上下文的内容加入镜像，但行为边界不同：

| 指令 | 主要行为 | 适用建议 |
| ---- | -------- | -------- |
| `COPY` | 复制本地上下文文件 | 常规首选，语义直接 |
| `ADD` | 除复制外，还可能自动解压本地 tar，或从 URL 下载 | 仅在确实需要这些额外行为时使用 |

```dockerfile
COPY --chown=app:app ./app/ /srv/app/
```

`COPY` 不会越过上下文边界。`ADD` 的“魔法”会使来源、解压和缓存行为更难一眼看懂；远程下载也不利于校验和可复现性。通常应以 `RUN curl ...` 显式下载、验证摘要、再安装。

注意尾部斜杠：`COPY src/ /app/src/` 复制目录内容；路径错误经常造成多套一层目录。构建后可用临时容器检查目标路径，而不是凭感觉修改。

## 四、缓存：如何快而不失控

构建器会尝试复用以前生成的层。一个 `RUN` 能否命中缓存，取决于它的指令内容、前序层以及它读取的构建输入；`COPY` 或 `ADD` 还取决于被复制文件的变化。当某一步未命中缓存，它之后的依赖层通常也要重新构建。

因此，变化频率低的步骤应放前面，变化频率高的步骤放后面。对于依赖型项目，错误与正确的差异很明显：

```dockerfile
# 不利于缓存：任意源码变化都会重装依赖
COPY . .
RUN npm ci
```

```dockerfile
# 利于缓存：只有依赖清单变化时才重装依赖
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
```

缓存不是正确性的替代品。依赖仓库内容、系统安全更新和远程下载可能改变，而 Dockerfile 文本不变；需要最新依赖时，应明确设计版本锁定和更新策略。排查缓存问题可以用：

```bash
docker build --no-cache -t demo-web:debug .
docker build --progress=plain -t demo-web:debug .
```

`--no-cache` 适合诊断或强制重建，日常每次使用只会浪费时间。现代 Docker 默认使用 BuildKit；若启用相应 Dockerfile 语法，也可为包管理器使用缓存挂载，例如：

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt
```

这类缓存只加速构建，不应被误认为最终运行镜像中的应用依赖。不同包管理器的缓存目录、权限和锁文件策略不同，应按实际生态调整。

## 五、运行配置：`ARG`、`ENV`、目录、端口与用户

### 1. `ARG` 与 `ENV` 的边界

`ARG` 是**构建期参数**。可以有默认值，并由 `--build-arg` 覆盖；它适合版本号、构建开关等不敏感输入。`ARG` 不会自动成为容器运行时环境变量。

```dockerfile
ARG APP_VERSION=1.0.0
RUN printf '%s\n' "$APP_VERSION" > /app/version.txt
```

```bash
docker build --build-arg APP_VERSION=1.2.0 -t demo-web:1.2.0 .
```

`ENV` 将变量写入镜像配置，默认会在容器运行时存在：

```dockerfile
ENV APP_HOME=/srv/app \
    NODE_ENV=production
WORKDIR $APP_HOME
```

两者的核心区别如下：

| 对比项 | `ARG` | `ENV` |
| ------ | ----- | ----- |
| 主要阶段 | 构建期 | 构建期和运行期 |
| 可由命令覆盖 | `--build-arg` | `docker run -e` |
| 是否默认留在容器环境 | 否 | 是 |
| 典型用途 | 版本、构建选项 | 运行时路径、模式、语言设置 |

**不要**通过 `ARG`、`ENV`、`COPY` 或命令行把密码、访问令牌、私钥写进镜像：构建历史、镜像配置、层或日志都可能暴露它们。构建时确实需要私有凭据时，使用 BuildKit secret mount、受限的凭据代理或 CI 的秘密注入，并确保秘密不被复制到最终层：

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=package_token \
    some-private-install-command
```

对应的命令由 CI 或本机安全地提供 secret；秘密名称和文件路径也应按实际平台配置。运行时秘密则优先由编排平台、密钥管理服务或受控挂载提供。

### 2. `WORKDIR`、`USER` 与文件权限

`WORKDIR /app` 设置后续 `RUN`、`COPY`、`CMD` 等相对路径的工作目录；若目录不存在会创建。显式写出它，比依赖基础镜像的默认目录更可读也更可移植。

```dockerfile
WORKDIR /srv/service
COPY --chown=app:app . .
USER app
```

容器中的 root 并不等于宿主机 root，但仍拥有较高权限，且错误配置可能放大风险。应用没有必须使用特权端口、安装软件或管理系统文件时，应创建或使用非 root 用户。切换 `USER` 前要确保应用文件、缓存目录和需要写入的目录属于该用户；否则容器会在启动后才以权限错误失败。

### 3. `EXPOSE` 只是文档和元数据

```dockerfile
EXPOSE 8080
```

这表示应用预期监听容器内的 `8080` 端口；它**不会**自动把端口发布到宿主机。对外访问仍要显式映射：

```bash
docker run --rm -p 8080:8080 demo-web:1.0
```

左边是宿主机端口，右边是容器端口。应用还必须监听 `0.0.0.0`（或适当地址）；如果只监听容器内的 `127.0.0.1`，即使端口映射正确，外部连接也可能失败。

## 六、容器启动：`CMD`、`ENTRYPOINT` 与 PID 1

`CMD` 提供默认命令或默认参数，`docker run IMAGE 其他命令` 可以替换它：

```dockerfile
CMD ["python", "app.py"]
```

`ENTRYPOINT` 则定义容器的固定可执行程序，运行命令通常作为它的附加参数：

```dockerfile
ENTRYPOINT ["/usr/local/bin/mytool"]
CMD ["serve", "--port", "8080"]
```

默认启动结果为 `mytool serve --port 8080`；执行 `docker run image status` 时，结果通常是 `mytool status`。两者组合适合“镜像就是某一个命令行工具”的场景。普通 Web 应用往往只需 `CMD`，保留替换命令的灵活性。

优先使用 JSON 数组形式（exec form）：

```dockerfile
CMD ["node", "server.js"]
```

而非 shell form：

```dockerfile
CMD node server.js
```

exec form 不经过 `/bin/sh -c`，参数边界更明确，也让应用更直接成为 PID 1。PID 1 负责接收 `SIGTERM` 等终止信号；如果用 shell 脚本包一层启动器，必须用 `exec "$@"` 把进程替换过去，并正确转发信号、回收子进程。否则 `docker stop` 时应用可能不能优雅退出，只能在超时后被强制终止。

## 七、案例：拆解 Neo4j GDS 的预构建镜像

项目外部目录中的 `graphrag/neo4j-gds.Dockerfile` 内容很短，但每一行都有工程意图：

```dockerfile
FROM neo4j:5.26-community

ARG GDS_VERSION=2.13.11
RUN wget -q --timeout=300 --tries=5 \
      --output-document=/var/lib/neo4j/plugins/graph-data-science.jar \
      "https://graphdatascience.ninja/neo4j-graph-data-science-${GDS_VERSION}.jar" \
    && test -s /var/lib/neo4j/plugins/graph-data-science.jar \
    && chmod 0644 /var/lib/neo4j/plugins/graph-data-science.jar
```

### 1. 逐步理解它在解决什么问题

| 片段 | 作用 | 工程意义 |
| ---- | ---- | -------- |
| `FROM neo4j:5.26-community` | 继承 Neo4j 社区版运行环境 | 复用官方启动逻辑、目录和 Java 环境 |
| `ARG GDS_VERSION=2.13.11` | 把 GDS 版本参数化 | 构建时可调整版本，Dockerfile 不必复制多份 |
| `wget --timeout=300 --tries=5` | 下载时设置超时和重试 | 降低短暂网络波动导致的构建失败 |
| `--output-document=...jar` | 写入 Neo4j 插件目录和固定文件名 | 使 Neo4j 按预期位置发现插件 |
| `test -s` | 检查目标文件非空 | 下载异常不会悄悄生成一个空 JAR |
| `chmod 0644` | 设置所有者可读写、其他用户可读 | 避免过宽权限，满足常规读取需求 |

这份 Dockerfile 的关键目标，是在**镜像构建期**下载已选定版本的图数据科学插件。相较于每次容器启动时再下载，代价被移到构建阶段：启动更快、更稳定，同一镜像实例使用同一份已准备好的插件。这也意味着升级插件时应显式改变 `GDS_VERSION`、重新构建并测试兼容性，而不是期待运行中的容器自行变化。

构建参数可这样覆盖：

```bash
docker build \
  -f graphrag/neo4j-gds.Dockerfile \
  --build-arg GDS_VERSION=<已验证的兼容版本> \
  -t ragent-neo4j-gds:local \
  graphrag
```

`GDS_VERSION` 是版本选择而非运行时 Neo4j 配置，不需要写成 `ENV`。示例刻意没有展示数据库密码、令牌或其他部署私密配置；这些内容应在受控的运行环境传入，而非固化在 Dockerfile。

### 2. 这份示例可以进一步加强什么

`test -s` 只能证明文件非空，不能证明下载内容没有被篡改或替换。更高要求的供应链控制应校验发布方提供的 SHA-256，并锁定可信的基础镜像 digest。概念上可写成：

```dockerfile
ARG GDS_VERSION=<已验证版本>
ARG GDS_SHA256=<来自可信发布渠道的摘要>
RUN wget -q --timeout=300 --tries=5 \
      --output-document=/var/lib/neo4j/plugins/graph-data-science.jar \
      "https://graphdatascience.ninja/neo4j-graph-data-science-${GDS_VERSION}.jar" \
    && echo "${GDS_SHA256}  /var/lib/neo4j/plugins/graph-data-science.jar" | sha256sum -c - \
    && chmod 0644 /var/lib/neo4j/plugins/graph-data-science.jar
```

尖括号只是教学占位符，不能直接投入构建。摘要和版本必须从 Neo4j/GDS 的可信兼容性资料、内部制品库或经过审核的发布记录取得。还应评估插件目录在基础镜像中是否由特定用户拥有；若运行用户无法读取，需在不放宽权限的前提下调整所有权或权限。

## 八、多阶段构建：把“构建工具”留在构建阶段

编译器、测试工具、源码和包管理器缓存往往只在构建时需要。**多阶段构建（multi-stage build）**允许在前一个阶段完成编译，只把最终产物复制到精简运行阶段。

```dockerfile
FROM golang:1.24-bookworm AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/server /server
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/server"]
```

最终镜像不会带上 Go 编译器、模块缓存和源码。这既减小体积，也缩小运行时攻击面；不过“更小”不能替代测试。若程序依赖动态库、CA 证书、时区数据或 shell 脚本，极简运行镜像可能不满足需求，应根据实际依赖选择运行阶段。

多阶段不仅适用于 Go：前端项目可在 Node 阶段打包静态文件，再复制给 Web 服务器；Java 可在 Maven/Gradle 阶段编译，再把 JAR 复制到 JRE 阶段。命名阶段（如 `AS builder`）比 `--from=0` 更清楚，也能避免阶段顺序调整引入错误。

## 九、镜像安全与供应链：从“能构建”到“可交付”

Dockerfile 是软件供应链的一部分。以下实践应成为默认检查项：

- 固定或定期审查基础镜像版本；生产环境优先记录 digest，并及时重建以获取安全修复。
- 使用可信来源，尽量让依赖版本可追溯；远程二进制或插件下载后校验摘要/签名。
- 不把秘密放在镜像、Dockerfile、构建参数、镜像标签或构建日志中；使用专门的 secret 机制。
- 以非 root 用户运行，并只授予应用所需的文件权限和 Linux capabilities。
- 用 `.dockerignore` 排除 `.git`、本地环境文件、私钥、依赖目录和测试产物；构建前仍应检查实际上下文。
- 在 CI 中扫描基础镜像和最终镜像的已知漏洞，并设置例外审查、修复优先级和重新构建机制。
- 区分构建期配置与运行期配置。数据库连接、密码、生产地址等环境相关值应由部署环境注入。

扫描结果并不是“发现漏洞就立刻删除镜像”那样简单。需要结合漏洞是否可达、基础镜像是否已有修复、业务暴露面和补丁影响来处理；但忽略扫描结果则只是把风险从可见变为不可见，没有任何技术含量。

## 十、构建和运行失败时怎样调试

不要一上来反复修改 Dockerfile。先把问题归类，能省去许多徒劳的重建：

| 症状 | 优先检查 |
| ---- | -------- |
| `COPY` 找不到文件 | 构建上下文、`.dockerignore`、源路径相对位置 |
| 每次都重装依赖 | `COPY` 顺序、锁文件是否变化、缓存是否被禁用 |
| 容器一启动就退出 | `CMD`/`ENTRYPOINT`、主进程日志、退出码 |
| `-p` 后仍无法访问 | 应用监听地址、容器端口、宿主端口占用、防火墙 |
| 非 root 后权限失败 | `COPY --chown`、运行用户、需写目录的权限 |
| 下载偶发失败 | DNS/代理、超时和重试、远程制品可用性与校验 |

下面的命令覆盖了多数初步检查：

```bash
# 看构建的详细执行输出
docker build --progress=plain -t demo-web:debug .

# 查看镜像层与创建指令，不要在这里放秘密
docker image history demo-web:debug

# 查看镜像保存的配置：入口、命令、环境变量、工作目录等
docker image inspect demo-web:debug

# 前台运行以直接观察日志和退出码
docker run --rm --name demo-web-debug -p 8080:8080 demo-web:debug

# 另一个终端中查看容器状态和日志
docker ps -a
docker logs demo-web-debug
docker inspect demo-web-debug
```

若镜像内有 shell，可以临时覆盖入口进入排查：

```bash
docker run --rm -it --entrypoint /bin/sh demo-web:debug
```

distroless 等极简镜像通常没有 `/bin/sh`，这不是“镜像坏了”。更合适的做法是在构建阶段加入测试、运行临时 debug 变体，或使用与目标容器共享网络/进程命名空间的诊断容器。调试镜像不要误推送为生产镜像。

## 十一、提交前检查清单

写完 Dockerfile 后，在提交前逐项回答这些问题：

- 基础镜像的来源、版本和更新策略是否清楚？
- 构建上下文是否足够小，`.dockerignore` 是否排除了秘密和无关产物？
- `COPY` 是否按“依赖清单在前、易变源码在后”组织，以利用缓存？
- 下载的外部文件是否有失败检查，并在需要时校验摘要或签名？
- 构建期参数与运行期环境变量是否分工明确，是否完全没有秘密进入镜像？
- 最终阶段是否只包含运行真正需要的文件和库？
- 应用是否以合适的非 root 用户运行，并有正确的文件权限？
- `CMD`、`ENTRYPOINT`、端口监听和优雅终止行为是否经过实际运行验证？

## 十二、总结

镜像的核心不是“装好软件的压缩包”，而是一组按顺序叠加、可缓存、可追溯的文件系统层和运行配置。Dockerfile 的质量主要取决于是否控制了输入、顺序和边界。

- 构建上下文决定 Docker 能看到什么；`.dockerignore` 决定不该发送什么。
- 分层缓存依赖指令及其输入；先复制稳定的依赖清单，再复制频繁变化的源码。
- `COPY` 是常规文件加入镜像的首选；`ADD` 和远程下载应只在额外行为确有必要且可验证时使用。
- `ARG` 服务构建期，`ENV` 服务运行期；二者都不是存储秘密的地方。
- `CMD`/`ENTRYPOINT` 决定启动语义，`EXPOSE` 不会自动发布端口，`USER` 和权限直接影响安全与可运行性。
- 多阶段构建、摘要校验、非 root 运行与镜像扫描，构成从本地可跑到生产可交付的基本防线。

理解这些原则后，再看 Neo4j GDS 示例就不应只看到一条下载命令：它是在构建期固定已验证的插件版本，用镜像层换取更可预测的启动过程。至于是否还要增加摘要校验、digest 固定和 CI 扫描，则取决于你的交付环境和风险要求；工程判断从来不是照抄一段 Dockerfile 就能省略的。
