+++
date = '2026-10-02T14:50:00+08:00'
draft = false
title = 'Docker 容器底层原理与工程化运维：从隔离机制到故障排查'
+++

前面的 Dockerfile、镜像、网络和 Compose 解决了“怎样把服务跑起来”。但一旦服务开始承载真实流量，问题很快会变成：为什么容器里的进程看不到宿主机进程？为什么明明限制了内存，进程还是被杀掉？为什么删掉容器数据仍在，或者反过来数据丢了？出了故障该先看哪里？

这一篇把这些问题串成一个完整模型。核心结论并不复杂：**容器不是轻量虚拟机，更不是某种特殊的应用格式；它本质上是宿主机 Linux 内核上的普通进程，配合隔离、资源控制和受管理的文件系统。** Docker 将这些能力组织成易用的镜像、网络、卷和命令。理解这条边界，许多看似神秘的现象就不再神秘了。

## 一、先建立一幅正确的运行全景图

在 Linux 上执行下面的命令时，真正运行的是宿主机内核调度的进程：

```bash
docker run --rm nginx:1.27-alpine
```

可以把调用链理解为：

```text
docker CLI
  -> Docker Engine API / dockerd
    -> containerd
      -> containerd-shim
        -> runc
          -> Linux kernel（namespaces、cgroups、VFS、网络）
            -> nginx 进程
```

这张图描述的是常见的 Docker Engine 实现路径；它的价值在于理解职责，并不要求日常开发者手动操作每一层。

| 组件 | 主要职责 | 初学者应记住什么 |
| ---- | -------- | ---------------- |
| `docker` CLI / API | 接收 `build`、`pull`、`run` 等请求 | CLI 只是客户端；本机或远程都可以有 Docker daemon |
| `dockerd` | Docker 的长驻服务，管理镜像、网络、卷、容器生命周期 | `docker ps`、`docker logs` 等通常都在和它通信 |
| `containerd` | 更底层的容器生命周期与镜像分发运行时 | Docker 通过它管理实际的容器任务 |
| `containerd-shim` | 在 daemon 重启时维持容器的标准输入输出与父子关系 | 不要手动杀掉它，否则容器可能异常退出 |
| `runc` | 按 OCI Runtime Specification 创建容器进程 | 它配置隔离与资源限制，然后启动目标进程并退出 |
| Linux 内核 | 提供进程、文件系统、网络、隔离与调度能力 | 容器最终依赖的不是 Docker，而是内核能力 |

### 1. 镜像、容器与进程不是同一个东西

- **镜像（image）**：不可变的文件系统层、启动配置和元数据模板。它没有“运行中”的状态。
- **容器（container）**：从镜像创建出的运行实例，附带一个可写层、网络命名空间、资源限制和生命周期配置。
- **容器主进程（PID 1）**：容器启动命令所对应的第一个进程。它退出，容器通常就退出；即使镜像和可写层仍然存在。

例如 `nginx:1.27-alpine` 是镜像，`docker run --name web ...` 创建的是容器，容器内的 `nginx -g 'daemon off;'` 是决定容器存活的主进程。把容器当作“永远在线的小服务器”，是后续运维误解的起点。

### 2. OCI 标准为什么重要

OCI（Open Container Initiative）定义了镜像格式和运行时配置等开放规范。因而一个符合 OCI 规范的镜像，通常可以由 Docker、containerd、CRI-O、Podman 或 Kubernetes 生态中的运行时使用；它不等于只能由 Docker 使用。

这也解释了工程上的分层：Docker 适合本地构建与开发体验，Kubernetes 负责集群编排，而 containerd、runc 等组件仍可在更底层承担运行工作。选择工具时看职责，不要把“Docker”误当作整个容器技术的同义词。

## 二、隔离的核心：Linux namespaces

`namespace` 会让一组进程看到一套“自己的”系统视图。同一个宿主机上可以存在多个容器：每个容器都以为自己有独立的进程列表、网卡、主机名和挂载点，实际上它们仍共享同一个 Linux 内核。

### 1. 常见命名空间及其效果

| 命名空间 | 隔离的对象 | 直观结果 | 常见风险或例外 |
| -------- | ---------- | -------- | -------------- |
| PID | 进程编号与进程树 | 容器内通常只能看到自己的进程，主进程为 PID 1 | `--pid=host` 会取消这层进程视图隔离 |
| NET | 网卡、IP、路由、端口、防火墙规则 | 默认容器有独立网络栈 | `--network host` 直接共用宿主网络 |
| MNT | 挂载点与文件系统视图 | 容器可看到自己的根文件系统和挂载卷 | 错误的 bind mount 会暴露宿主文件 |
| UTS | 主机名和域名 | `hostname` 在容器内可不同 | `--uts=host` 会共用宿主主机名 |
| IPC | 共享内存、消息队列、信号量 | 多容器默认不共享 IPC 对象 | `--ipc=host` 会扩大可见范围 |
| USER | 用户和组 ID 映射 | 容器内 UID 0 可映射为宿主非特权 UID | 并非所有环境默认启用；卷权限需额外设计 |
| Cgroup | cgroup 路径视图 | 容器不必看见宿主完整的 cgroup 层级 | 它不是资源限制本身，限制由 cgroups 控制器完成 |

可以用一个不严格但有用的类比记忆：namespace 决定“你**看见**什么”，cgroups 决定“你**最多用**多少”。前者偏隔离视图，后者偏资源治理；两者一起使用才形成可管理的容器。

### 2. 容器内的 root 不等于宿主机 root

默认 Docker 容器内的 UID 0 往往仍对应宿主机 UID 0，因此“容器内 root”绝不能被当作无害身份。它会受到 capabilities、seccomp、AppArmor/SELinux、namespace 等限制，但配置不当、内核漏洞或高权限挂载仍可能造成逃逸或宿主破坏。

用户命名空间和 rootless Docker 则可把容器内的 UID 0 映射为宿主机的非特权 UID。它能显著缩小意外提权的后果，但也会带来端口、存储驱动、设备访问及某些网络能力的限制。对不需要特权的开发环境和构建节点，rootless 是很好的默认选择；对特殊硬件、复杂网络场景，应先验证兼容性。

### 3. PID 1 的两个容易踩坑的细节

PID 1 对信号和子进程回收有特殊语义。应用若只会启动子进程却不 `wait`，可能留下僵尸进程；若它没有正确处理 `SIGTERM`，`docker stop` 会在宽限期后使用 `SIGKILL` 强制结束，造成请求中断或数据未落盘。

建议让应用本身前台运行并处理优雅退出信号；如果应用不擅长回收子进程，可使用 Docker 的轻量初始化进程：

```bash
docker run --init --name report-worker example/report-worker:1.4.0
```

不要用 `tail -f /dev/null` 或无限 `sleep` 来“保活”一个已经退出的服务。它只是在掩盖启动命令、依赖连接或应用进程设计的问题。

## 三、资源控制：cgroups 与内核调度

cgroups（control groups）将进程归入层级组，并通过控制器记录或限制 CPU、内存、I/O、进程数等资源。Docker 把这些内核接口包装成 `--memory`、`--cpus` 等参数。较新的 Linux 发行版常使用 cgroup v2；Docker 的具体配置文件路径与部分细节会随 v1/v2 变化，但运维目标相同。

### 1. CPU 限制不是“永远占一颗核”

`--cpus 1.5` 通常以 CFS 配额（quota）约束平均可使用的 CPU 时间。例如在一个常见的 100 ms 周期里，容器可运行约 150 ms 的 CPU 时间（分布到多个核上亦可）。达到配额后会被节流，直到下一周期。

```bash
docker run -d --name api \
  --cpus="1.5" \
  --memory="768m" \
  --memory-reservation="512m" \
  --pids-limit=256 \
  example/api:2.3.0
```

- `--cpus`：限制可用 CPU 时间；CPU 密集型任务达到上限后，延迟可能上升。
- `--memory`：硬内存上限。进程超限时可能触发容器内或宿主机的 OOM killer。
- `--memory-reservation`：较软的内存压力提示，不可替代硬上限。
- `--pids-limit`：限制进程/线程总数，防止 fork bomb 或线程泄漏拖垮宿主机。

CPU 限制会造成 **throttling（节流）**，不是异常；内存限制却可能造成 **OOM kill**，常表现为容器退出码 `137`（128 + SIGKILL 9）。因此排查“偶尔重启”的 Java、Node.js 或向量数据库容器时，应同时查看容器事件、内核 OOM 记录和应用自身内存上限，而不是只盯着应用日志。

### 2. 内存限制与运行时参数必须协同

容器限制只是外层预算，语言运行时还会有自己的堆、缓存、线程栈和本地内存。比如 Java 的 `-Xmx` 不应直接等于 `--memory`，必须为 Metaspace、Direct Buffer、线程栈、JIT 和系统库预留空间；Node.js、Python 科学计算库和数据库也有类似的额外内存。

一个保守的起点是：先根据压测观测到的峰值，再给应用堆设置小于容器上限的预算，并留出明显余量。这里没有放之四海皆准的百分比，原因很简单：运行时、负载形态和内存映射文件都不同。用监控校正预算，远比机械套数字可靠。

### 3. I/O、ulimit 与共享宿主机的现实

磁盘 I/O 限制依赖块设备与存储驱动，命令如 `--device-read-bps`、`--device-write-bps` 适用于明确的设备路径，但在 Docker Desktop 或网络存储上效果可能与 Linux 裸机不同。先用压测确认，不能只凭参数名字相信它必然生效。

文件描述符上限也常被遗漏。高并发 Web 服务可显式设置：

```bash
docker run -d --name gateway \
  --ulimit nofile=65535:65535 \
  --pids-limit=512 \
  example/gateway:3.1.0
```

不要无条件把所有限制调到极大。限制是为了让一个故障服务不能侵蚀整台机器；正确做法是根据应用容量模型、压测结果和节点总预算设置值。

## 四、镜像分层、UnionFS 与 OverlayFS

镜像不是一个巨大的单文件压缩包。Docker 镜像由配置对象、清单（manifest）及多个以内容摘要标识的只读层组成。每条会改变文件系统的 Dockerfile 指令，通常会形成新的层；多个镜像可以共享相同的基础层，因此拉取与存储不必重复。

### 1. OverlayFS 如何把多层变成一个目录

Linux 上常见的存储驱动是 `overlay2`，底层使用 OverlayFS。可把它想成下列结构：

```text
lowerdir：镜像的多层只读目录（base OS、运行时、应用层）
upperdir：当前容器专属的可写目录
workdir ：OverlayFS 内部工作目录
merged  ：容器实际看到的统一根文件系统
```

当进程读取一个只存在于 `lowerdir` 的文件时，内核直接读取只读层；当它首次修改该文件时，OverlayFS 会将文件复制到 `upperdir` 再修改，这就是 **copy-on-write，写时复制**。新增文件也进入 `upperdir`。删除下层文件通常以 whiteout（白障）标记遮蔽，而不是改写原始只读层。

这个机制解释了三件事：

1. 同一镜像启动十个容器，不会复制十份基础系统。
2. 容器可写层适合短暂运行状态，不适合唯一业务数据。
3. 修改一个很大的镜像内文件可能触发复制并放大磁盘和 I/O 开销。

### 2. Dockerfile 的层缓存为什么有时失效

构建时，Docker/BuildKit 会尽量复用已经存在的层。若先复制全部源码，再执行依赖安装，任何一行源码变化都会使依赖安装层失效。更合理的顺序是先复制依赖清单、安装依赖，再复制业务源码：

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
```

缓存优化的本质是让“变化最少、最昂贵”的步骤位于变化较多步骤之前。它是开发效率优化，不应为了缓存把密钥、构建产物或无关文件放进镜像；`.dockerignore` 仍然不可缺少。

### 3. 容器可写层、卷和 bind mount 的选择

| 存储位置 | 生命周期 | 典型用途 | 主要注意点 |
| -------- | -------- | -------- | ---------- |
| 容器可写层 | 删除容器后通常随之消失 | 临时缓存、运行中生成的小文件 | 不用于唯一持久数据 |
| named volume | 独立于容器，可显式备份和迁移 | PostgreSQL、Redis 持久化目录 | 必须制定备份、恢复和清理策略 |
| bind mount | 直接映射宿主指定路径 | 本地源码热更新、受控宿主数据目录 | 权限、路径可移植性和宿主暴露风险更高 |
| `tmpfs` mount | 内存中的临时挂载，停止后消失 | 敏感临时文件、高速临时目录 | 占用内存，不能当持久化存储 |

例如本项目的本地开发栈将 PostgreSQL 的 `/var/lib/postgresql/data` 放入命名卷，将初始化 SQL 只读挂载到 `/docker-entrypoint-initdb.d/`。这是一个合理的职责划分：数据卷负责数据生命周期，初始化脚本是可审查的只读输入。反过来，把数据库目录放在容器根文件系统中，删除并重建容器时便很容易误删数据。

### 4. 镜像层不能保存运行时数据

`docker commit` 可以把某个容器当前可写层制作成新镜像，但它会把不可见的手工操作固化下来，不可审计、不可稳定复现，也无法取代数据库备份。除了紧急取证外，应使用 Dockerfile、配置管理、迁移脚本与数据备份来描述系统状态。可复现性不是仪式感，是故障恢复时真正能救命的东西。

## 五、为什么 Linux、macOS 和 Windows 的体验不同

Linux 容器需要 Linux 内核能力。在 Linux 主机上，Docker Engine 可直接利用宿主内核，因此容器进程与宿主进程属于同一个内核，只是隔离视图不同。

macOS 和 Windows 的普通桌面内核不能原生提供完整 Linux 容器运行环境。Docker Desktop 因此在轻量 Linux 虚拟机中运行 Linux Docker Engine；Windows 上通常借助 WSL 2 或 Hyper-V。于是路径共享、文件事件、网络地址、磁盘性能和内存统计都会比 Linux 裸机多一层边界。

| 场景 | 实际运行内核 | 需要特别注意 |
| ---- | ------------ | ------------ |
| Linux 主机上的 Linux containers | 宿主 Linux 内核 | 与宿主同内核，内核版本和安全配置直接相关 |
| macOS Docker Desktop | Linux VM 中的 Linux 内核 | bind mount I/O、大小写、文件监听与 VM 资源上限 |
| Windows + WSL 2 Docker Desktop | WSL 2 Linux VM 内核 | 建议把源码放在 Linux 文件系统中以获得更好的开发 I/O |
| Windows containers | Windows 内核 | 基础镜像版本必须与宿主 Windows 版本/隔离模式兼容 |

因此，“镜像能在我电脑上运行”不自动意味着它能在任何系统上运行。还要核对 CPU 架构（如 `linux/amd64` 与 `linux/arm64`）、操作系统类型、内核能力和宿主挂载路径。使用多架构镜像时，清单会为不同平台指向相应的镜像层；必要时可在构建或运行时明确指定 `--platform`。

## 六、日志、健康检查与可观测性：让容器不是黑箱

### 1. 日志必须输出到标准输出和标准错误

Docker 最自然的日志入口是容器主进程的 stdout/stderr：

```bash
docker logs --tail 200 --timestamps -f api
```

`docker logs` 能否读取历史日志取决于日志驱动。常见的 `json-file` 在宿主机保存 JSON 日志，默认不限制大小，长期运行容易撑满磁盘；`local` 驱动有更适合本地轮转的存储格式；生产环境还可发送到 journald、Fluentd、GELF、云日志服务等集中系统。

本地可明确设置轮转，避免“日志写满磁盘导致全机故障”这种相当遗憾的事故：

```bash
docker run -d --name api \
  --log-driver local \
  --log-opt max-size=20m \
  --log-opt max-file=5 \
  example/api:2.3.0
```

应用不应只把日志写入容器内部某个文件。那样既不方便收集，容器重建后也可能丢失；若必须生成审计文件，应通过卷或日志代理规划其保留和轮转。

### 2. 健康检查回答的是“服务可用吗”

进程还活着不代表服务可用：它可能死锁、无法连数据库、线程池耗尽，或尚未完成启动。`HEALTHCHECK` 会周期性执行一个命令，并将容器状态标记为 `starting`、`healthy` 或 `unhealthy`。

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1
```

健康检查端点应轻量、确定，并能反映真正需要的依赖程度。启动慢的服务应设置合适的 `start-period`；否则正常冷启动会被误判。读取业务数据、执行大查询或访问不稳定的第三方 API，都不适合作为高频健康检查。

还有一个常见误解：**Docker 将容器标为 `unhealthy` 并不等于它会自动重启。** `restart` 策略主要针对进程退出。Compose 中可用 `depends_on.condition: service_healthy` 控制某项服务的启动等待，例如本地栈中 broker 等待 name server 的健康状态；但这也不是持续的故障编排。需要跨多副本自愈、流量摘除与滚动发布时，应使用 Kubernetes、Swarm 或云平台等编排层的就绪与存活探针。

### 3. 三类可观测性信号缺一不可

- **日志（logs）**：发生了什么。应带时间、级别、请求/追踪 ID、错误堆栈，避免打印密码、Token 和完整个人数据。
- **指标（metrics）**：系统是否正在变差。至少观测 CPU 使用与节流、内存工作集、OOM、网络错误、磁盘、请求量、错误率和延迟分位数。
- **链路追踪（traces）**：一次请求跨服务时慢在哪里、错在哪里。用 trace ID 将网关、应用、数据库和消息队列调用关联起来。

排障时，`docker stats` 是快速快照，不能替代长期监控：

```bash
docker stats --no-stream
docker top api
docker inspect -f '{{.State.Status}} {{.State.Health.Status}} {{.State.OOMKilled}}' api
docker events --since 30m
```

单机实验可用 cAdvisor 采集容器指标，再交给 Prometheus/Grafana；生产系统还应纳入宿主机、数据库、负载均衡和应用业务指标。只监测“容器在运行”是最低限度，不是可观测性。

## 七、安全基线：容器隔离不是免死金牌

容器共享内核，安全模型必须采用纵深防御：缩小镜像、缩小权限、缩小挂载、缩小网络暴露，并让依赖来源可验证。下面的做法通常值得成为默认值。

### 1. 运行时最小权限

```bash
docker run -d --name public-api \
  --user 10001:10001 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges:true \
  --pids-limit 256 \
  -p 127.0.0.1:8080:8080 \
  example/api:2.3.0
```

逐项理解比照抄更重要：

- `--user`：以非 root 用户运行。镜像中需要提前创建该用户并修正目录所有权。
- `--read-only`：根文件系统不可写；把确实需要写的缓存、临时目录显式放在卷或 `tmpfs`。
- `--cap-drop ALL`：移除 Linux capabilities，再按需加回最少能力。端口大于 1024 时通常连 `NET_BIND_SERVICE` 也不需要。
- `no-new-privileges`：阻止 `setuid` 程序等获得额外权限。
- `-p 127.0.0.1:...`：只对本机暴露端口；是否公开由反向代理或防火墙明确决定。

不要使用 `--privileged` 来“快速解决权限错误”。它会给予极广泛的宿主能力，常常把容器隔离变得形同虚设。也不要把 `/var/run/docker.sock` 挂进普通业务容器：拥有该 socket 通常等同于拥有宿主机的高权限 Docker 控制权。若确有构建或编排需求，应采用受隔离的构建器、最小权限代理或专用节点。

### 2. 默认安全机制与额外隔离

Docker 默认的 seccomp profile 会阻止一部分危险系统调用；Linux 上还可借助 AppArmor 或 SELinux 进行强制访问控制。不要为了某个功能报错就直接设置 `seccomp=unconfined`；先定位缺少的能力或系统调用，确认该服务是否真的需要它。

在多租户、高风险或需要更强隔离的场景，可考虑 rootless 模式、用户命名空间、gVisor、Kata Containers 或独立虚拟机。它们的安全、兼容性与性能取舍不同：没有一种“打开即绝对安全”的选项。风险越高，越应使用独立节点、网络隔离和完整的补丁策略。

### 3. 密钥和镜像供应链

环境变量很方便，但会出现在 `docker inspect`、进程环境或错误日志的可见范围中，不宜承载长期高价值密钥。开发环境可以从不提交 Git 的 `.env` 文件读取；生产环境应使用平台 Secret、外部密钥管理服务或受权限控制的只读 secret 文件，并做好轮换。

供应链的最小清单是：

1. 基础镜像选官方或可信维护者，并固定到明确版本；关键生产部署最好固定到 digest，例如 `repo/app@sha256:...`。
2. 定期重建镜像以纳入基础镜像安全修复，而不是以为 `latest` 会自动更新已经运行的容器。
3. 在 CI 中生成 SBOM、扫描操作系统和语言依赖漏洞，并设定例外审批与修复时限。
4. 对发布镜像签名并在部署端验证来源，保存构建来源、版本、提交号和扫描结果。

以本地开发 Compose 为例，`POSTGRES_PASSWORD: postgres`、Redis 密码和对象存储凭据直接写入 YAML 只能作为本地示例；绝不能复制到仓库中的生产配置。即使是内网服务，泄露的凭据也不会因为“本来只给内部用”就突然变得无害。

## 八、系统化故障排查：先缩小范围，再改变状态

发生故障时，第一原则是先保存证据，避免一上来就 `docker rm -f`、反复重启或清日志。下面的顺序覆盖了大多数单机容器事故。

### 1. 第一步：容器是否活着，为什么退出

```bash
docker ps -a --no-trunc
docker inspect -f '{{json .State}}' api
docker logs --tail 300 --timestamps api
docker events --since 1h --filter container=api
```

重点看 `ExitCode`、`Error`、`FinishedAt`、`OOMKilled` 与健康状态。退出码不是充分证据，但能帮助分类：

| 现象 | 首先怀疑什么 | 下一步 |
| ---- | ------------ | ------ |
| 退出码 `0`，却不停重启 | 主命令正常结束，不该作为长期服务 | 检查 `CMD`/`ENTRYPOINT` 与前台进程 |
| 退出码 `1` | 应用启动或配置错误 | 看应用日志、环境变量、挂载文件和依赖连接 |
| 退出码 `126` / `127` | 命令不可执行 / 找不到命令 | 检查镜像路径、执行权限、shell 形式与架构 |
| 退出码 `137` 或 `OOMKilled=true` | 内存不足或被 SIGKILL | 核对 cgroup 限制、内核 OOM、应用内存设置 |
| `unhealthy` 但仍在运行 | 健康检查失败 | 在容器内手动执行检查命令，判断端点或依赖 |

### 2. 第二步：配置、挂载、网络与 DNS

```bash
docker inspect api
docker exec api sh
docker exec api env
docker exec api getent hosts postgres
docker network inspect ragent-local-dev_default
docker volume inspect ragent-postgres-data
```

`docker exec` 适合短暂检查，不适合把手工修改当作修复。进入容器后应验证：配置文件是否真正挂载、运行用户是否有读写权限、环境变量是否如预期、服务名能否解析、目标端口能否访问。对数据库连接问题，要分别检查 DNS、TCP 连通性、认证、数据库是否就绪与应用连接池，而不是简单地“端口通了就没问题”。

Compose 服务之间应使用服务名和容器端口，例如 `postgres:5432`，而不是宿主映射端口 `localhost:5432`。在容器中，`localhost` 指向的是**当前容器自身**；这是新手最常见的网络错误之一。

### 3. 第三步：资源与宿主机

```bash
docker stats --no-stream api
docker system df
docker info
```

再在 Linux 宿主机查看系统日志、磁盘空间、inode、内核 OOM 信息和文件权限。Docker Desktop 则还要检查 Desktop 分配给 Linux VM 的 CPU、内存、磁盘，以及 bind mount 位置。容器“能启动但很慢”经常不是镜像问题，而是 CPU 节流、内存换页、磁盘满、挂载 I/O 慢或依赖服务饱和。

若需要网络抓包、挂载检查或命名空间级诊断，优先在受控的诊断容器或宿主机上进行，并记录操作。生产环境中的 `--network container:...`、`nsenter`、`strace` 等工具很强大，也很容易影响性能和暴露敏感数据；它们应是有目的的升级手段，而非默认动作。

### 4. 一张实际可执行的排障路径

```text
请求失败 / 服务异常
  -> 容器存在且主进程仍在吗？
     -> 否：看 ExitCode、日志、OOM、启动命令
     -> 是：健康检查是否通过？
        -> 否：手动复现 healthcheck，检查依赖与启动时间
        -> 是：检查端口、反向代理、DNS、网络策略
  -> 资源是否异常？CPU 节流 / 内存上涨 / 磁盘或 inode 满
  -> 配置、镜像版本、挂载和最近变更是否一致？
  -> 修复后以新镜像或声明式配置重建，并验证指标与业务请求
```

这一路径刻意把“先重启试试”放在后面。重启可缓解临时状态，却会销毁最有价值的证据，并可能让数据恢复、消息重复消费或级联重启变得更糟。

## 九、从本地 Compose 到可靠部署

Compose 非常适合开发、集成测试和单机部署。它把镜像、网络、卷、依赖关系和环境变量声明成版本化文件，比一串无法复现的 `docker run` 命令可靠得多。复杂的高可用、自动扩缩、跨节点调度、滚动升级和流量治理，则需要 Kubernetes 或对应的托管平台；不要期待单机 `restart: unless-stopped` 解决集群问题。

### 1. 一份更稳健的服务定义骨架

以下示例展示关键思路，具体镜像、路径、用户 ID 和资源值必须根据应用调整：

```yaml
services:
  api:
    image: registry.example.com/team/api@sha256:replace-with-approved-digest
    restart: unless-stopped
    init: true
    user: "10001:10001"
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      APP_ENV: production
    secrets:
      - db_password
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: "1.50"
          memory: 768M
    logging:
      driver: local
      options:
        max-size: "20m"
        max-file: "5"

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

注意 Compose 的 `deploy` 字段在不同实现与部署模式下支持程度不同；不能仅凭 YAML 写了资源限制就假定其在当前环境生效。部署后应以 `docker inspect`、`docker stats` 和压力测试验证实际限制。secret 的文件也必须从版本控制中排除并由安全的发布流程提供。

### 2. 发布、回滚、数据的三个原则

- **镜像不可变**：每次发布使用可追踪的版本或 digest，记录 Git 提交、构建时间和依赖版本；不要让生产依赖浮动标签。
- **配置可审计**：Compose、环境变量模板、网络与卷定义进入版本管理，密钥进入专用 Secret 管理；变更走评审和发布记录。
- **数据可恢复**：数据库和命名卷有定期备份、异机保存、恢复演练和明确的 RPO/RTO。仅有备份文件而未做恢复演练，通常不能称为可靠备份。

升级有状态服务前还应阅读镜像对应版本的迁移说明，先备份并在接近生产的数据副本上演练。直接 `docker compose pull && docker compose up -d` 对无状态小服务可能足够，对数据库、消息队列和索引服务则未必安全。

### 3. 容器上线前检查清单

- 镜像是否固定版本/digest，是否通过漏洞扫描、来源验证和架构测试？
- 应用是否以非 root 运行，是否避免了 `privileged`、Docker socket 和不必要的 capabilities？
- 根文件系统是否可只读，写入目录、数据卷、权限和备份策略是否明确？
- CPU、内存、PID、日志轮转和运行时堆内存是否经过压测验证？
- 健康检查是否真实反映可用性，优雅退出时间是否与网关/编排器协调？
- 日志、指标、追踪、告警和故障联系人是否已准备好？
- 回滚方式、数据库迁移方式、备份与恢复演练是否可执行？

## 十、总结：把 Docker 当作受约束的进程管理系统

理解 Docker 的关键不是背完所有子命令，而是把每个现象放回正确层次：

- namespace 给进程独立视图，cgroups 给它资源边界；容器仍共享宿主机内核。
- OverlayFS 用只读镜像层和容器可写层实现高效复用与写时复制；业务数据应进入经过管理的卷或外部存储。
- Linux 可直接运行 Linux 容器；macOS、Windows 上的 Docker Desktop 通常隔着 Linux VM，性能和路径行为需要额外验证。
- stdout/stderr、健康检查、指标与追踪共同让容器可观测；`unhealthy` 不等于自动修复。
- 最小权限、非 root、只读文件系统、受控挂载、秘密管理与可信镜像缺一不可。
- 排障从状态、日志、健康、配置网络、资源和宿主机逐层收敛，证据优先于盲目重启。

至此，你不必把容器当成黑盒魔法：它只是被精心限制、打包、观察并可重复创建的进程。正因为如此，工程质量取决于我们是否把资源、数据、安全和故障路径也一并设计进去。
