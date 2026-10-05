+++
date = '2026-10-02T14:10:00+08:00'
draft = false
title = 'Docker 入门：从第一个容器到日常排错'
+++
Docker 解决的并不是“如何在另一台机器上安装软件”这个小问题，而是“如何把应用及其运行条件一起交付，并在不同环境中稳定运行”这个工程问题。学习 Docker 的第一步，不是背命令，而是分清镜像、容器、仓库、端口和数据各自负责什么。

完成本文后，你应当能够安全地安装并验证 Docker，运行和删除第一个 Web 容器，解释常用命令在改变什么状态，并在容器启动失败时按一条可靠的路径定位问题。后续阅读本项目的 Compose YAML 与 Dockerfile 时，也不会再把它们当成神秘配置。

## 一、Docker 到底解决了什么

传统部署常见的过程是：在服务器上安装运行时、数据库客户端和系统依赖，再复制程序、配置环境变量、开放端口并启动服务。步骤写下来并不复杂，真正麻烦的是每台机器的操作系统、依赖版本、环境变量和文件权限都可能不同。“在我电脑上能运行”通常不能推出“在测试或生产环境也能运行”。

Docker 将应用运行所需的文件和默认启动方式打成**镜像**，再据此创建一个或多个**容器**。容器是主机上的隔离进程，不是完整虚拟机；它通常与主机共享 Linux 内核，因此启动快、占用相对少。容器的隔离主要来自 Linux 的 namespace（看见各自的进程、网络、挂载点等）和 cgroup（限制和统计 CPU、内存等资源）。

这带来三个直接收益：

- 环境可复现：同一镜像在开发、CI 和服务器上有相同的应用文件与启动命令。
- 依赖隔离：不同项目可以使用不同版本的运行时或中间件，互不覆盖。
- 交付一致：镜像是可版本化、可推送、可拉取的交付物，部署不再依赖一长串人工安装步骤。

它也没有消灭所有问题。容器不会自动让程序无状态、不会自动保存数据、更不会替你处理镜像漏洞、账号密钥和网络暴露。尤其应记住：容器隔离不是绝对的安全边界，把 Docker socket、宿主机敏感目录或 `--privileged` 随意挂进去，等于显著扩大了容器对宿主机的控制范围。

### 容器与虚拟机的区别

| 维度 | 容器 | 虚拟机 |
| ---- | ---- | ------ |
| 运行单位 | 隔离的应用进程及其文件系统视图 | 带有客户操作系统的虚拟硬件环境 |
| 内核 | 通常共享宿主机 Linux 内核 | 每台虚拟机运行自己的客户内核 |
| 启动与资源 | 通常秒级或更快，额外开销较小 | 通常需要启动客户 OS，开销较大 |
| 隔离强度 | 依赖内核隔离与运行时配置 | 硬件虚拟化边界通常更强 |
| 适合场景 | 应用交付、开发环境、服务编排 | 不同 OS、强隔离、传统基础设施 |

在 Windows 与 macOS 上运行 Linux 容器时，Docker Desktop 会在后台使用一个轻量 Linux 虚拟化环境，因为 Linux 容器仍需要 Linux 内核。这并不矛盾：你日常操作的是 Docker 容器，但底层会借助一个 Linux VM 提供内核。

## 二、先建立五个核心概念

### 1. Docker Client、Daemon 与 CLI

你输入的 `docker run` 是 Docker CLI 命令。CLI 会向 Docker daemon（通常名为 `dockerd`）发请求；daemon 负责拉取镜像、创建网络和卷、调用容器运行时启动进程。Docker Desktop 则是面向桌面系统的一套产品，包含 GUI、CLI 与运行 Linux 容器所需的后端环境。

可以把调用链理解为：

```text
PowerShell / Terminal
        │ docker run
        ▼
Docker CLI ── API ──> Docker daemon
                         │
                         ├─ 镜像仓库：拉取镜像
                         ├─ 本地镜像存储：解包镜像层
                         └─ container runtime：启动隔离进程
```

因此，`docker` 命令存在不代表 Docker 服务一定可用；反之，Docker Desktop 没启动、Linux 上 daemon 未运行、当前用户没有访问 daemon 的权限，都会让命令失败。

### 2. 镜像（image）是只读模板

镜像包含应用文件、依赖、默认工作目录、环境变量、默认启动命令等元数据。它通常由多层只读文件系统层组成；相同基础层可以被多个镜像复用，所以“镜像大”不总是等于磁盘实际新增同样多的空间。

镜像名称一般写作：

```text
[registry-host[:port]/]namespace/repository[:tag][@digest]
```

例如 `nginx:1.27-alpine`：`nginx` 是仓库名，`1.27-alpine` 是 tag。未写 registry 时通常从 Docker Hub 获取；未写 tag 时 Docker 默认使用 `latest`，但 `latest` 只是一个普通、可移动的标签，**并不保证是最新版本，更不保证可重复构建**。

生产环境应优先选择明确版本标签；需要最高可重复性时，使用不可变的内容摘要（digest），例如 `nginx@sha256:...`。tag 像会被重新贴上的书签，digest 才是对具体内容的校验值。

### 3. 容器（container）是镜像的一次运行实例

从同一个 `nginx:alpine` 镜像可以创建多个容器，它们有不同的名称、可写层、网络地址和生命周期。容器创建后，Docker 在镜像只读层之上增加一个**可写容器层**；应用写入容器文件系统的内容会落在这里。

可写层属于容器，不属于镜像。删除容器后，该层及其中没有挂载出去的数据通常也会消失。这就是数据库、上传文件和重要配置不能只写在容器内的根本原因；持久化数据应使用后文会深入介绍的 volume 或 bind mount。

### 4. 仓库与注册表（repository / registry）

这两个词很容易混淆：

- **repository**：某个镜像的版本集合，例如 Docker Hub 上的 `library/nginx`。
- **registry**：保存并分发多个 repository 的服务，例如 Docker Hub、私有 Harbor、云厂商镜像仓库。

`docker pull` 从 registry 下载镜像，`docker push` 将本地镜像推送到有权限的 registry。镜像仓库既是依赖来源，也是供应链入口：不要把未知来源、永远不更新或来历不明的镜像直接用于生产。

### 5. Dockerfile、Compose 与 Docker 的关系

- `Dockerfile` 是**构建镜像的配方**，常见指令有 `FROM`、`RUN`、`COPY`、`CMD` 和 `ENTRYPOINT`。
- Docker 镜像是按 Dockerfile 构建出来的产物。
- Compose YAML 是**定义一组相关容器**的声明文件，可同时描述服务、网络、卷、端口和依赖关系。

所以，Dockerfile 不等于容器，Compose 也不等于镜像。可以用一句话概括：Dockerfile 负责“做出一个运行包”，`docker run` 负责“启动一个实例”，Compose 负责“把一组实例和它们的关系一起启动”。

## 三、安装 Docker 与验证运行环境

本项目面向 Windows 开发环境时，建议优先安装 Docker Desktop，并启用 WSL 2 后端。macOS 同样优先使用 Docker Desktop。原生 Linux 服务器通常安装 Docker Engine；请根据发行版选择官方安装步骤，而不是复制来源不明的一键脚本。官方入口见 [Docker 安装文档](https://docs.docker.com/get-started/get-docker/)；Windows 用户还应阅读 [Docker Desktop 的 Windows 安装要求](https://docs.docker.com/desktop/setup/install/windows-install/)。

### Windows：安装前与安装后的检查

Windows 10/11 的 Linux 容器通常依赖 WSL 2。以管理员 PowerShell 执行下列命令可确认 WSL 状态：

```powershell
wsl --status
wsl --version
```

若系统提示未安装 WSL，可按系统提示或执行 `wsl --install`，重启后再安装 Docker Desktop。安装时选择 WSL 2 后端，并确认 Docker Desktop 已启动。不要把 Hyper-V、BIOS 虚拟化、公司设备策略导致的报错，误认为是某条 Docker 命令写错了。

安装完成后，在新的 PowerShell 窗口执行：

```powershell
docker version
docker info
docker context ls
docker compose version
```

`docker version` 应同时显示 Client 与 Server 两部分；只有 Client 说明 CLI 找到了，但尚未连接到 daemon。`docker info` 能显示存储驱动、容器数量、CPU 与内存等运行信息。`docker context ls` 应有一个带 `*` 的当前 context，桌面环境常为 `desktop-linux`；`docker compose version` 确认使用的是 Docker Compose V2 的 `docker compose` 子命令。

### Linux：权限与服务状态

在 Linux 上安装 Docker Engine 后，先检查服务：

```bash
sudo systemctl status docker
docker version
docker info
```

如果普通用户执行 Docker 时出现访问 `/var/run/docker.sock` 的权限错误，可以按官方文档将该用户加入 `docker` 组，然后重新登录：

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker run --rm hello-world
```

`docker` 组通常等价于对宿主机拥有很高的管理权限，不应为了省事把不可信用户加入其中。对共享主机或更严格的隔离要求，应评估 rootless mode 与最小权限方案，而不是盲目放宽权限。

### 最小健康检查：hello-world

无论使用哪种系统，运行下面的命令：

```bash
docker run --rm hello-world
```

这条命令完成了一次很有代表性的完整链路：本地没有 `hello-world` 镜像时，daemon 会从默认 registry 拉取；随后根据镜像创建并启动一个容器；容器输出说明文字后立即退出；`--rm` 则自动删除这个短生命周期容器。

如果拉取失败，优先检查网络、代理、公司镜像源和 Docker Desktop 的网络设置；如果显示“Cannot connect to the Docker daemon”，优先检查 Docker Desktop 或 daemon 是否在运行；如果提示权限拒绝，检查 Linux 用户组或当前 context。先读完整错误信息，再决定动作，不要一上来就重装。

## 四、第一次实战：运行一个 Nginx Web 容器

`hello-world` 证明 Docker 可用，但它运行后立刻结束。下面启动一个持续提供 HTTP 服务的 Nginx 容器。为避免把服务暴露到所有网卡，本机练习显式绑定到回环地址：

```bash
docker run -d \
  --name demo-nginx \
  --publish 127.0.0.1:8080:80 \
  nginx:1.27-alpine
```

在 PowerShell 中，反斜杠不是续行符。请使用单行，或者用反引号续行：

```powershell
docker run -d `
  --name demo-nginx `
  --publish 127.0.0.1:8080:80 `
  nginx:1.27-alpine
```

参数逐项解释如下：

| 参数 | 作用 |
| ---- | ---- |
| `-d` | 以 detached 模式在后台运行，终端立即返回容器 ID。 |
| `--name demo-nginx` | 指定稳定、易读的容器名，后续不必复制长 ID。 |
| `--publish 127.0.0.1:8080:80` | 将宿主机 `127.0.0.1:8080` 映射到容器 `80/tcp`。 |
| `nginx:1.27-alpine` | 要运行的镜像及固定版本标签。 |

浏览器访问 `http://localhost:8080`，或在终端验证：

```bash
curl http://localhost:8080
docker ps
```

`docker ps` 只显示运行中的容器。输出中的 `PORTS` 如 `127.0.0.1:8080->80/tcp` 表明映射生效。请特别注意端口顺序是**宿主机端口在前，容器端口在后**。`-p 8080:80` 没有指定 IP 时，Docker 通常会绑定 `0.0.0.0`，也就是可能被局域网或外网访问；开发机上应按实际需要决定是否暴露。

### 进入容器看一看

容器仍在运行时，可以执行一个额外命令：

```bash
docker exec -it demo-nginx sh
```

现在出现的是容器中的 shell；可执行：

```sh
id
hostname
ps
ls -la /usr/share/nginx/html
exit
```

`exec` 是在**已经运行的容器**中启动一个新进程，不会重启容器。镜像使用 Alpine Linux，常只有 `sh`，未必存在 `bash`；“`bash` 找不到”通常不是 Docker 损坏，而是镜像刻意保持精简。

### 清理本次练习

先停止，再删除容器：

```bash
docker stop demo-nginx
docker rm demo-nginx
```

此操作只删除名为 `demo-nginx` 的容器，不会删除 `nginx:1.27-alpine` 镜像。下一次运行相同镜像时，若本地仍有该镜像，通常不会再次下载。

## 五、读懂 `docker run`：创建、启动和主进程

`docker run` 可以理解为 `docker create` 加 `docker start` 的组合：创建容器的配置和可写层，然后启动它的主进程。它每执行一次都会尝试创建**新容器**；即使镜像相同，也不是“再次进入原容器”。

一个容器的生命取决于它的主进程（PID 1）。主进程正常退出，容器就变为 `exited`；主进程崩溃，容器也会停止。后台模式 `-d` 仅仅是不把日志占住当前终端，绝不会让已退出的主进程变成持续运行的服务。

例如下面的容器会完成输出后退出，这是正确行为：

```bash
docker run --name one-shot alpine:3.20 echo "任务完成"
docker ps -a
```

而下面的容器会保持一段时间运行：

```bash
docker run -d --name sleep-demo alpine:3.20 sleep 300
docker ps
```

不要用 `service nginx start` 一类会立即返回的后台启动脚本作为容器主命令。正确的容器化服务通常以前台方式运行，让真正的服务进程成为 PID 1；这样 Docker 才能观察进程状态、收集日志并在停止时发送信号。

### 生命周期状态与对应命令

```text
镜像
  │ docker create / docker run
  ▼
created ── docker start ──> running ── 主进程结束 ──> exited
  ▲                             │                         │
  └──────── docker start ───────┘                         │
                                                        docker rm
                                                           ▼
                                                        removed
```

常用动作如下：

| 目标 | 命令 | 要点 |
| ---- | ---- | ---- |
| 仅看运行中容器 | `docker ps` | 容器“消失”时先用下一条确认是否已退出。 |
| 看全部容器 | `docker ps -a` | 包括 `created`、`exited` 等状态。 |
| 优雅停止 | `docker stop <容器>` | 先发停止信号，超时后才强制结束。 |
| 强制终止 | `docker kill <容器>` | 直接终止，可能来不及清理或落盘。 |
| 启动旧容器 | `docker start <容器>` | 保留该容器原有配置和可写层。 |
| 重启容器 | `docker restart <容器>` | 相当于停止后再启动。 |
| 删除已停止容器 | `docker rm <容器>` | 运行中的容器需先停止或明确使用 `-f`。 |
| 前台附着启动 | `docker start -a <容器>` | 将启动输出附着到当前终端。 |

练习结束即应删除临时容器，或在本来就无需保留状态的一次性命令中使用 `--rm`。但不要给数据库等需要人工排查的服务盲目加 `--rm`；它退出后容器记录和匿名卷可能被清理，反而不利于排错。

## 六、日常命令地图：先观察，再操作

Docker 命令可以按对象分组。较长的形式如 `docker container ls` 与常见短形式 `docker ps` 等价；初学者可以先使用短形式，理解对象后再阅读长形式帮助。

### 镜像：查看、拉取与删除

```bash
docker image ls
docker pull redis:7.4-alpine
docker image inspect redis:7.4-alpine
docker image rm redis:7.4-alpine
```

- `docker image ls` 只列本地镜像，不代表远程仓库的全部版本。
- `docker pull` 可以预先下载，也可以让 `docker run` 在本地缺失时自动拉取。
- `docker image inspect` 能查看镜像 ID、入口命令、环境变量和架构等详细元数据。
- 正被容器引用的镜像通常不能直接删除；这是保护措施，而不是错误。

### 容器：查看、日志、执行命令与拷贝文件

```bash
docker ps
docker ps -a
docker logs demo-nginx
docker logs --tail 100 -f demo-nginx
docker exec -it demo-nginx sh
docker cp demo-nginx:/etc/nginx/nginx.conf ./nginx.conf
docker inspect demo-nginx
```

`docker logs` 读取的是容器主进程写到标准输出和标准错误的日志；应用若只把日志写进容器内部某个文件，`docker logs` 不会自动显示。`-f` 会持续跟随输出，排查启动失败时常与 `docker ps -a` 配合使用。

`docker cp` 可在宿主机与容器之间复制文件，适合临时取证或调试；它不是生产环境配置和数据持久化方案。`docker inspect` 输出 JSON，信息很多，建议先用格式化查询取得一个字段：

```bash
docker inspect --format '{{.State.Status}}' demo-nginx
docker inspect --format '{{.State.ExitCode}}' demo-nginx
docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' demo-nginx
```

PowerShell 也能执行上述命令；单引号会将 Go 模板原样传给 Docker。若看到空 IP，不一定是网络故障：某些平台或网络模式下容器 IP 并不适合作为从宿主机访问服务的地址，优先通过已发布的宿主机端口访问。

### 系统：磁盘、资源和事件

```bash
docker system df
docker stats
docker stats --no-stream
docker events
```

`docker system df` 用于观察镜像、容器、本地卷和构建缓存的空间占用；`docker stats` 实时查看运行容器的 CPU、内存、网络和块 I/O；`docker events` 适合观察 `create`、`start`、`die`、`destroy` 等生命周期事件。遇到反复重启的容器时，事件流和日志能比“不断重启试试”更快地给出线索。

清理命令一定要先了解范围：

```bash
docker container prune
docker image prune
docker system prune
```

它们会删除未被使用的资源，其中 `docker system prune` 覆盖范围更大。不要为了释放几 GB 空间就在重要开发环境中带额外参数随手执行；尤其 `--volumes` 会影响未使用的卷。先用 `docker system df` 确认，再明确对象和范围后清理。

## 七、一个稳定的排错顺序

容器不能访问、刚启动就退出、端口打不开，表面现象不同，但排查应从事实而不是猜测开始。建议固定使用下面这条链路。

### 1. 确认 Docker 本身可连接

```bash
docker version
docker info
```

若没有 Server 信息，问题还在 Docker Desktop、daemon、context 或权限层，尚未进入应用问题。不要对一个根本没被创建的容器反复执行 `docker logs`。

### 2. 确认容器究竟是否运行

```bash
docker ps -a --filter name=demo-nginx
```

- `Up`：容器仍在运行，继续检查端口、网络、应用监听地址与健康状态。
- `Exited (0)`：主进程正常结束，需判断它是否本就应该是一次性任务。
- `Exited (非 0)`：应用或启动命令失败，先看日志和退出码。
- `Restarting`：程序持续失败且受重启策略影响，不要只盯着 `docker ps` 的刷新结果。

### 3. 看日志与退出信息

```bash
docker logs --tail 200 <容器名>
docker inspect --format 'status={{.State.Status}} exit={{.State.ExitCode}} error={{.State.Error}}' <容器名>
```

常见线索包括：环境变量缺失、配置文件路径错误、端口已被占用、连接依赖服务失败、镜像架构不匹配、应用自身异常。日志最后几行很重要，但不要忽略最早出现的第一条错误；后面的堆栈往往只是连锁反应。

### 4. 核对启动配置，而不是凭记忆改命令

```bash
docker inspect <容器名>
```

重点检查 `.Config.Cmd`、`.Config.Env`、`.HostConfig.PortBindings`、`.Mounts`、`.NetworkSettings.Networks` 与 `.State`。也可以先看简洁摘要：

```bash
docker port <容器名>
docker inspect --format '{{json .Mounts}}' <容器名>
```

这一步经常发现“宿主机端口和容器端口写反”“变量名拼错”“挂载路径覆盖了镜像内文件”“命令参数没有被正确传入”等问题。

### 5. 从宿主机和容器内分别验证网络

先确认宿主机端口是否真的发布：

```bash
docker port <容器名>
curl -v http://127.0.0.1:<宿主机端口>
```

再进入容器，检查应用实际监听的位置和端口。不同镜像工具不同，以下命令并非所有极简镜像都自带：

```bash
docker exec <容器名> sh
ss -lnt
```

应用若只监听 `127.0.0.1`，它监听的是**容器自己的回环地址**，通过端口发布后仍可能无法被 Docker 转发访问；服务通常应监听容器内的 `0.0.0.0`，再由 Docker 的端口映射控制宿主机暴露范围。

### 6. 用最小复现替代原地修补

当容器配置已变得难以判断，可保留现有容器用于取证，然后用一个新名字和最少参数重建：

```bash
docker run --rm --name minimal-test alpine:3.20 echo ok
```

最小命令成功说明 Docker 基础可用；随后一次只增加端口、挂载、环境变量或网络中的一个因素。一次改十个参数，得到的只会是更难解释的结果。

## 八、最常见的误解

### 1. “镜像就是正在运行的程序”

不对。镜像是只读模板，容器才是该模板的运行实例。同一个镜像可对应零个、一个或多个容器；删除容器也不等于删除镜像。

### 2. “容器停了就是 Docker 挂了”

不对。容器停止通常只表示其 PID 1 已结束。命令行任务完成后退出是正常现象；Web 服务立即退出，则要检查启动命令是否把服务放到了后台、应用是否崩溃或依赖是否不可用。

### 3. “`EXPOSE 8080` 或 Compose 的 `expose` 会让外部能访问”

不一定。`EXPOSE` 是镜像声明的元数据，`expose` 主要表达容器间可用端口；它们都不等于把端口绑定到宿主机。需要宿主机访问时，使用 `docker run -p` 或 Compose 的 `ports`。

### 4. “删容器就会删掉所有相关数据”

不完全对。容器可写层会消失；但命名 volume 默认不会因为 `docker rm` 被删除，bind mount 指向的宿主机文件更不会消失。相反，匿名卷与 `--rm`、`docker rm -v` 的组合行为需要特别留意。不要仅凭“我删过容器”判断数据一定不存在，也不要凭“我用了卷”判断数据一定安全——备份仍不可省略。

### 5. “`localhost` 在容器里就是宿主机”

不对。容器内的 `localhost` 指向该容器自身。容器要访问另一个容器，通常通过同一 Docker 网络中的服务名；要访问宿主机，则需使用符合当前平台和网络模式的方式。后续网络章节会详细说明。

### 6. “用 `latest` 很方便，所以生产也应该用”

方便不等于可靠。可变标签会让同一部署命令在不同日期获得不同内容，排障和回滚都会失去确定性。开发试验可以使用它，正式环境应固定版本并建立升级流程。

### 7. “容器天生安全，可以直接以 root 运行”

不对。容器中的 root 与宿主机权限映射、内核漏洞、挂载、Linux capabilities 和运行时配置有关。实际服务应尽量使用非 root 用户、只读文件系统、最小镜像和最小权限；绝不要把 `--privileged` 当作通用的“权限不够”解决方案。

## 九、阅读本项目 Docker 资源时的切入点

本项目的 Docker 资源目录含有若干 `*.compose.yaml` 文件与 Dockerfile。暂时不必逐行记住 YAML 语法，先用本文的概念标注它们：

- `image: redis:7-alpine` 表示服务使用的镜像；`container_name` 是实例名称。
- `ports: - "6379:6379"` 是宿主机到容器的端口映射，顺序仍是“宿主机：容器”。
- `environment` 为容器进程提供环境变量，密钥不应直接提交到公开仓库。
- `volumes` 将命名卷或主机路径挂载到容器，决定哪些数据在容器删除后仍保留。
- `depends_on`、`healthcheck`、`networks` 和 `restart` 分别描述启动依赖、就绪探测、容器互联与重启策略。
- Dockerfile 中的 `FROM` 指定基础镜像，`RUN` 在构建时执行并形成镜像层，`CMD` 或 `ENTRYPOINT` 决定容器默认启动什么主进程。

下面的课程将依次解释镜像构建、数据卷与网络、Compose 多服务编排、镜像优化与安全，以及如何将这些概念落到本项目的实际资源文件中。现在最重要的是能回答每次运行的五个问题：使用哪个镜像？创建了哪个容器？主进程是什么？端口如何映射？哪些数据会保留？

## 十、本文小结与自检

Docker 的关键不是把命令背熟，而是形成可验证的状态模型：镜像是模板，容器是实例，registry 负责分发，主进程决定容器是否存活，可写容器层不等于持久化存储。

完成本文后，建议自行验证下面的练习：

1. 运行 `docker run --rm hello-world`，并解释为什么运行结束后 `docker ps -a` 中看不到它。
2. 运行 `demo-nginx`，用 `docker ps`、`docker logs`、`docker port` 和浏览器分别验证它的状态、日志和端口映射。
3. 停止 `demo-nginx` 后使用 `docker ps -a` 找到它，再用 `docker start` 恢复，而不是再执行一次 `docker run`。
4. 最后使用 `docker rm` 删除该容器，确认镜像仍在 `docker image ls` 中。
5. 故意把端口写成已被占用的值或将镜像名拼错，按“连接 Docker → 看状态 → 查日志 → 核对配置 → 验证网络”的顺序记录错误原因。

当这些动作不再靠猜测时，Docker 已从一堆陌生命令变成了一个清晰的应用运行与交付系统。余下的内容只是在这个模型之上增加构建、存储、网络和编排的细节而已。
