+++
date = '2026-09-28T17:00:00+08:00'
draft = false
title = 'GitHub Actions 与 GitLab CI/CD：架构、运行原理与流水线设计'
+++

很多人第一次接触 CI/CD 时，看到的往往是一份 YAML：里面有 `build`、`test`、`deploy`，再配几条 shell 命令。于是很自然地把它理解成“云端帮我执行脚本”。这个理解不算错，但还不够。

GitHub Actions 和 GitLab CI/CD 的核心工作，是把一次 Git 事件和某个确定的提交版本绑定起来，解析版本库中的流水线配置，生成一张任务依赖图，然后把任务安全地调度到合适的执行机器上。构建日志、测试报告、制品、部署记录和权限边界，也都由这一过程统一管理。

换句话说，YAML 只是声明“应该做什么”；真正让流程跑起来的是事件系统、调度器、Runner、隔离环境、制品存储和权限系统。只盯着 `script`，就像只看到了剧本，却忽略了舞台、演员、排练和场务。这样理解 CI/CD，遇到问题时难免会有些无从下手。

本文会先建立 CI/CD 的共同模型，再分别说明 GitHub Actions 与 GitLab CI/CD 的架构和执行原理，最后给出一条可用于实际项目的流水线设计方法。

如果你要了解 Hugo 博客如何通过 GitHub Actions 发布到 GitHub Pages，可以继续阅读本站的[GitHub Actions、GitHub Pages 和 Hugo 静态博客部署流程](./GitHub%20Actions、GitHub%20Pages%20和%20Hugo%20静态博客部署流程.md)。本文不重复讲静态博客的具体部署配置，而是讨论更一般的 CI/CD 机制。

## 一、先区分 CI、持续交付和持续部署

CI/CD 中的 `CI` 和 `CD` 不是两个模糊的口号，而是三种不同程度的自动化能力。

| 概念 | 英文全称 | 要解决的问题 |
| --- | --- | --- |
| CI | Continuous Integration，持续集成 | 每次提交能否与主干稳定集成 |
| 持续交付 | Continuous Delivery | 软件是否随时具备可发布状态 |
| 持续部署 | Continuous Deployment | 已验证的改动能否自动进入生产环境 |

### 1. 持续集成：尽早发现“不该合进去”的代码

持续集成要求开发者频繁把改动合入共享分支，并在每次提交或 Pull Request、Merge Request 中自动完成构建和验证。

一个典型的 CI 流程是：

```text
开发者提交代码
    -> 拉取本次提交对应的源码
    -> 安装依赖
    -> 静态检查和编译
    -> 单元测试
    -> 回写成功或失败状态到 PR / MR
```

它的目标不是“自动上线”，而是尽可能早地发现：代码是否无法编译、测试是否失败、格式是否不合规范、依赖是否存在已知漏洞。越晚发现问题，修复成本通常越高；这一点不需要多么深奥的理论，经历过一次上线前才发现主干不能构建的人大概都会同意。

### 2. 持续交付：始终保留一个可发布版本

持续交付在 CI 之上继续前进：当代码通过验证后，自动构建可部署的制品，并将其部署到测试或预发环境。生产环境的最后一步常常需要人工批准。

```text
测试通过
    -> 生成 JAR、前端 dist、Docker 镜像等制品
    -> 部署测试或预发环境
    -> 自动验收
    -> 等待生产发布审批
```

这里的关键是：**任意一个通过质量门禁的版本，都应当是可发布的**。人工审批并不意味着流程不自动化；它只是把生产风险的最终决定留给具备业务上下文的人。

### 3. 持续部署：通过门禁后自动进入生产

持续部署则不再等待人工确认：只要自动化测试、质量门禁和安全策略全部通过，系统就自动部署生产环境。

```text
代码合并
    -> CI 通过
    -> 构建制品
    -> 测试环境验证
    -> 自动部署生产
    -> 线上健康检查和监控
```

持续部署适合测试充分、监控完善、回滚可靠，且业务能够接受快速变更的场景。支付、医疗、金融核心链路等高风险系统常会采用持续交付加人工审批；内容站、内部工具或成熟的云服务，则可能更接近持续部署。没有哪一种天然更高级，和风险模型匹配才有意义。

## 二、所有 CI/CD 平台共享的架构

GitHub Actions 与 GitLab CI/CD 在产品名称和 YAML 写法上不同，但核心架构高度相似。最重要的划分是：**控制平面**和**执行平面**。

```text
开发者 push / 创建 PR 或 MR / 打 Tag / 手动触发
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│ 控制平面：GitHub Actions 或 GitLab CI/CD             │
│                                                    │
│ 接收事件 -> 解析 YAML -> 创建任务图 -> 调度 Job      │
│ 保存状态、日志索引、制品元数据、环境和审批记录       │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│ 执行平面：Runner                                    │
│                                                    │
│ 虚拟机、Docker 容器、Kubernetes Pod 或自建服务器      │
│ checkout -> install -> build -> test -> package     │
└────────────────────────────────────────────────────┘
             │                         │
             ▼                         ▼
      缓存、构建制品               镜像仓库、云服务、
      测试报告、日志               Kubernetes、目标服务器
```

### 1. 控制平面：决定做什么、何时做、由谁做

控制平面通常由 GitHub 或 GitLab 服务端提供，负责下面这些事情：

- 接收 `push`、PR、MR、Tag、定时和手动等事件。
- 找到事件关联的提交 SHA，并读取该版本的流水线 YAML。
- 判断分支、路径、标签、条件表达式和权限策略是否满足。
- 将矩阵任务展开，建立 Job 之间的依赖关系。
- 根据标签、容量、环境权限和并发限制选择 Runner。
- 持久化 Job 状态、日志索引、测试报告、制品信息和部署记录。

它不一定亲自执行 `npm test` 或 `mvn package`，但它决定这些命令是否应当运行、应该在哪里运行，以及失败后谁不能继续。把这种工作放在中心化控制平面中，才能让团队看到一致的结果和审计记录。

### 2. 执行平面：在隔离环境里真正运行命令

执行平面是 Runner 所在的机器或容器环境。Runner 领取 Job 后，才会实际完成：

1. 准备工作目录、虚拟机、容器或 Pod。
2. 注入临时变量、Token 和经过授权的密钥。
3. 拉取指定提交的源码。
4. 恢复依赖缓存，下载上游 Job 的构建制品。
5. 执行脚本或可复用步骤。
6. 上传日志、测试报告、构建制品和退出状态。
7. 清理临时环境，或在自建 Runner 中等待下一项任务。

所以，平台页面显示“Job 正在运行”时，真正忙碌的通常是一台临时虚拟机、一个容器或一个 Kubernetes Pod，而不是 GitHub 或 GitLab 的网页本身。

### 3. YAML 会被解析成 DAG

CI/CD 的任务不必是一条从左到右的串行队列。更准确地说，平台会将它解析为 **DAG**，即有向无环图。

```text
lint ──────┐
           ├─> build ─> deploy-staging
unit-test ─┘
```

图中的箭头表示依赖：

- `lint` 和 `unit-test` 互不依赖，因此可以并行。
- `build` 依赖它们二者，只有都成功才执行。
- `deploy-staging` 依赖构建结果。

这种安排比“无论是否有关联都全部串行”更快，也比“所有任务同时乱跑”更可靠。GitHub 主要用 Job 的 `needs` 表达依赖；GitLab 既有默认的 `stages` 阶段顺序，也可以用 `needs` 精确表达 DAG。

## 三、GitHub Actions 的架构和运行模型

GitHub 的 CI/CD 产品是 GitHub Actions。它的核心关系可以概括为：

```text
Event -> Workflow -> Job -> Step -> Runner
```

GitHub 官方将 Workflow 定义为仓库中可配置的自动化过程：一个 Workflow 包含一个或多个 Job；每个 Job 由多个 Step 组成；Job 被 Runner 执行。Workflow 可由仓库事件、定时任务、手动操作或 API 调用触发。[GitHub Actions 官方概念文档](https://docs.github.com/en/actions/get-started/understand-github-actions)

### 1. Workflow：一份自动化流程的声明

GitHub Actions 的配置文件位于：

```text
.github/workflows/<workflow-name>.yml
```

一个仓库可以拆分出多份 Workflow：

```text
.github/workflows/
  ci.yml          # 代码检查、测试和构建
  release.yml     # 打 Tag 后发布包或镜像
  deploy.yml      # 部署环境
```

最小示例如下：

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test
```

其中：

- `on` 指定触发事件。
- `jobs` 定义本次 Workflow 中的任务。
- `runs-on` 指定运行 Job 的 Runner 类型或标签。
- `steps` 是同一个 Job 内依次执行的操作。
- `uses` 调用一个可复用的 Action。
- `run` 直接执行 shell 命令。

### 2. Job 与 Step：隔离边界和顺序边界

一个 Job 中的 Step 默认运行在同一个 Runner 上，并按顺序执行。因此，前一个 Step 生成的文件可以被后一个 Step 使用：

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build
      - run: ls dist
```

这里的 `npm run build` 与 `ls dist` 在同一工作目录中，所以后者能看到前者生成的 `dist/`。

不同 Job 则不能假定共享本地文件系统，因为它们可能被分配给不同 Runner，甚至在不同虚拟机中执行。需要跨 Job 传递文件时，应上传和下载 Artifact：

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: web-dist
    path: dist/
```

下游 Job 再下载名为 `web-dist` 的制品。这个边界很重要：同一 Job 共享工作区，不同 Job 通过显式机制交换结果。依赖“另一台机器上也许还留着文件”的做法，不是工程设计，只是把故障延后了一点。

### 3. Action 与 Reusable Workflow：两种复用粒度

GitHub 中的 **Action** 是可复用的自动化组件，常见例子有：

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-node@v4
- uses: docker/login-action@v3
```

Action 可由 JavaScript、Docker 容器或多个普通步骤组合实现。它适合封装“拉取代码”“安装 Node.js”“登录镜像仓库”这类明确的小职责。

如果需要复用一整套 Job，例如“构建镜像、扫描镜像、推送镜像”，则更适合使用 **Reusable Workflow**。可以把它理解为 Workflow 级复用：调用方传入参数和密钥，被调用方运行预定义的多个 Job。

### 4. Runner：托管执行器与自托管执行器

GitHub 提供两类 Runner：

| 类型 | 特点 | 适用场景 |
| --- | --- | --- |
| GitHub-hosted Runner | GitHub 托管，Job 通常运行在新创建的虚拟机中 | 标准 Linux、Windows、macOS 构建和测试 |
| Self-hosted Runner | 由团队自己部署和维护 | 内网资源、专用硬件、私有网络、GPU 或定制工具链 |

GitHub-hosted Runner 的优势是免维护与较好的任务隔离。自托管 Runner 可以是物理机、虚拟机、容器、本地数据中心或云中的资源，但操作系统更新、工作目录清理、网络隔离和安全策略都需要自行承担。[GitHub 自托管 Runner 文档](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)

在自托管 Runner 上尤其要防止“污染”：一个 Job 留下的文件、进程、Docker 镜像或凭据，有可能影响后续 Job。处理方式包括使用临时容器或临时虚拟机、限制可执行任务来源、在 Job 后清理目录，并将生产部署 Runner 与普通 PR 构建 Runner 分开。

### 5. 并行、依赖与矩阵

GitHub 中没有 `needs` 依赖的 Job 默认可并行：

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest

  test:
    runs-on: ubuntu-latest

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]
```

如果同一测试要覆盖多个系统或运行时版本，可使用矩阵：

```yaml
strategy:
  matrix:
    node: [20, 22]
```

平台会将一个逻辑 Job 展开为多个独立 Job：

```text
test(Node 20) ─┐
               ├─> build
test(Node 22) ─┘
```

矩阵适合验证兼容性，但不应无节制扩大组合数量。每多一个维度，执行时间、Runner 消耗和排查复杂度都会增加。测试矩阵的目标是覆盖真实支持范围，不是把排队时间做成一种行为艺术。

## 四、GitLab CI/CD 的架构和运行模型

GitLab CI/CD 通常使用下面的层级表达流程：

```text
Pipeline -> Stage -> Job -> Script
```

配置文件通常位于仓库根目录：

```text
.gitlab-ci.yml
```

一个基础 Pipeline 如下：

```yaml
stages:
  - test
  - build
  - deploy

unit_test:
  stage: test
  script:
    - npm ci
    - npm test

build:
  stage: build
  script:
    - npm run build
```

GitLab 在触发 Pipeline 后，会依据 `.gitlab-ci.yml` 创建 Job、将 Job 放入队列，并匹配具备正确标签、能力和可用容量的 Runner。Runner 获取任务、准备执行环境、运行脚本并实时上报结果。[GitLab Runner 官方说明](https://docs.gitlab.com/ci/runners/)

### 1. Pipeline：一次完整的执行实例

一次 `push`、Merge Request、Tag 或手动操作，可以产生一次 Pipeline。Pipeline 会记录：

- 触发来源和关联提交。
- 生成了哪些 Job。
- 每个 Job 的日志、耗时和状态。
- 构建产物和测试报告。
- 部署到哪个 Environment。
- 失败发生在哪个步骤，以及是否允许重试。

因此 Pipeline 是可追溯的发布记录，而不仅是一段临时执行日志。

### 2. Stage：默认的阶段屏障

`stages` 定义逻辑阶段的顺序：

```yaml
stages:
  - verify
  - test
  - build
  - deploy
```

默认语义是：前一个 Stage 中的 Job 全部满足继续条件，后一个 Stage 才开始。

```text
verify 阶段全部完成
        ↓
test 阶段全部完成
        ↓
build 阶段开始
        ↓
deploy 阶段开始
```

同一个 Stage 内的多个 Job 可以并行。Stage 适合表达粗粒度阶段，例如检查、测试、构建、部署；它让 Pipeline 的可视化阅读很直观。

### 3. `needs`：从阶段顺序升级到依赖图

真实项目常常不需要等待上一个 Stage 的全部 Job 完成。此时可使用 `needs`：

```yaml
build_web:
  stage: build
  needs:
    - lint
    - unit_test
  script:
    - npm run build
```

这表示 `build_web` 只依赖 `lint` 与 `unit_test`，而不是笼统地依赖前一个 Stage 中全部任务。GitLab 的 `needs` 还能明确下游是否需要下载上游 Artifact：

```yaml
deploy_staging:
  stage: deploy
  needs:
    - job: build_web
      artifacts: true
  script:
    - ./scripts/deploy-staging.sh
```

所以，Stage 是好读的默认结构，`needs` 是更准确的执行依赖。二者不是互相排斥，而是先后两个层次的工具。

### 4. GitLab Runner 与 Executor

GitLab Runner 是运行 CI/CD Job 的代理程序。它可以使用不同 Executor 来真正执行任务：

| Executor | 执行方式 | 典型用途 |
| --- | --- | --- |
| Shell | 直接在 Runner 主机上执行命令 | 已有专用构建机、内网运维任务 |
| Docker | 为 Job 创建 Docker 容器 | 常规构建，依赖环境可声明化 |
| Kubernetes | 为 Job 创建 Kubernetes Pod | 云原生构建、大规模弹性任务 |
| 托管虚拟机 | 在 GitLab 托管环境中运行 | 希望减少 Runner 运维 |

GitLab Runner 可以作为项目、群组或实例范围的 Runner 使用。GitLab-hosted Runner 由平台管理，通常以新虚拟机执行每个 Job 并根据需求扩缩容；Self-managed Runner 则由团队部署和维护，并支持 Shell、Docker、Kubernetes 等 Executor。[GitLab Runner 类型与执行器说明](https://docs.gitlab.com/ci/runners/)

这让 GitLab 在私有化部署、内网构建或 Kubernetes 集群场景中很常见：GitLab 负责控制和展示，Runner 可以靠近私有 Maven 仓库、数据库测试环境、Kubernetes API 或生产网络。

### 5. YAML 复用：`include`、`extends` 和变量

大型项目不应把所有逻辑堆在一个越来越长的 `.gitlab-ci.yml` 中。GitLab 支持用 `include` 引入其他 YAML：

```yaml
include:
  - local: '.gitlab/ci/test.yml'
  - local: '.gitlab/ci/build.yml'
  - local: '.gitlab/ci/deploy.yml'
```

还可以通过隐藏 Job 和 `extends` 复用公共环境：

```yaml
.node_job:
  image: node:22
  before_script:
    - npm ci

unit_test:
  extends: .node_job
  script:
    - npm test
```

GitLab 官方 YAML 参考中，将 `stages`、`variables`、`workflow`、`include` 列为全局配置；将 `script`、`rules`、`needs`、`artifacts`、`environment`、`tags` 等列为 Job 配置。[GitLab CI/CD YAML 官方参考](https://docs.gitlab.com/ci/yaml/)

## 五、GitHub Actions 与 GitLab CI/CD 如何对应

两者不是谁能做、谁不能做的关系，而是相似能力使用了不同术语和默认组织方式。

| 关注点 | GitHub Actions | GitLab CI/CD |
| --- | --- | --- |
| 配置文件 | `.github/workflows/*.yml` | `.gitlab-ci.yml` |
| 一次完整执行 | Workflow run | Pipeline |
| 顶层组织 | 一个 Workflow 包含多个 Job | 一个 Pipeline 包含多个 Stage 和 Job |
| 默认依赖模型 | Job 默认并行，使用 `needs` 声明依赖 | Stage 默认有序，使用 `needs` 建 DAG |
| 最小执行内容 | Step 中的 `uses` 或 `run` | Job 中的 `script`、`before_script` 等 |
| 复用方式 | Action、Reusable Workflow | `include`、`extends`、组件、下游 Pipeline |
| Runner 选择 | `runs-on` 与 label | `tags`、Runner 范围与能力 |
| 环境部署 | Environment、Protection rule、Deployment | Environment、Protected environment、Deployment |
| 代码评审反馈 | Pull Request Checks | Merge Request Pipeline |

可以做一个不那么严格、但有助于初学的记忆：

```text
GitHub Actions：事件驱动 + Job 依赖图 + Action 生态

GitLab CI/CD：Pipeline/Stage 模型 + Runner/Executor 架构 + 一体化 DevSecOps 能力
```

实际选择时，更应考虑已有代码托管平台、企业是否需要私有化部署、Runner 是否要访问内网、镜像和包仓库是否已整合、团队是否已有对应运维经验。为了“语法看起来顺眼”而迁移整个代码平台，通常不会是一个成熟的决策理由。

## 六、一次流水线从触发到结束的底层过程

无论平台差异如何，一次典型流水线大致都会经历下面八步。

```text
1. Git 事件产生
2. 平台确定提交 SHA 和配置版本
3. 解析条件、变量、矩阵和依赖
4. 创建 Pipeline / Workflow 与 Job
5. 调度器匹配 Runner
6. Runner 创建环境并执行
7. 回传日志、报告、制品和状态
8. 继续下游、等待审批或终止
```

### 1. Git 事件与不可变提交

常见触发源包括：

- 代码推送。
- 创建、更新或合并 PR/MR。
- 创建 Release 或 Tag。
- 定时触发。
- 手动触发。
- API、上游 Pipeline 或其他自动化系统触发。

平台应将运行与明确的 commit SHA 绑定，例如：

```text
commit: a1b2c3d
branch: main
pipeline: #842
artifact: app-1.8.0-a1b2c3d.jar
```

这条追溯链能回答生产事故中最重要的问题：当前线上运行的制品来自哪次提交？如果不能回答，所谓“自动化发布”仍然缺少基本的可控性。

### 2. 条件判断与任务图生成

平台读取 YAML 后，会依次判断：

- 本次事件是否匹配触发器？
- 分支、Tag、路径是否满足规则？
- 条件表达式是否为真？
- Job 是否需要手动启动或环境审批？
- 矩阵是否需要展开为多个任务？
- 下游 Job 依赖哪些上游结果？

例如 Node.js 兼容性测试可能从一个定义展开为两个实际 Job：

```text
test(node=20)
test(node=22)
```

控制平面最终得到的是一张图和一批待调度 Job，而不是直接把整个 YAML 原封不动交给一台机器执行。

### 3. 调度与 Runner 匹配

调度器会根据下面的信息匹配 Runner：

- Runner 是否在线。
- 当前是否还有并发容量。
- 操作系统、CPU 架构、GPU 等能力是否匹配。
- `runs-on`、label 或 Runner tag 是否匹配。
- Runner 是否被授权执行受保护分支或生产环境任务。
- Runner 是否能访问所需的内网、集群或密钥服务。

例如：

```yaml
runs-on: [self-hosted, linux, internal-network]
```

或：

```yaml
tags:
  - kubernetes
  - production
```

表达的都不是“随便找台机器跑”，而是“只允许具备特定能力和权限的 Runner 领取”。

### 4. 环境准备、脚本执行与退出码

Runner 拿到 Job 后，通常会拉取基础镜像或准备虚拟机，创建工作目录，再执行类似下面的流程：

```text
准备临时环境
    -> checkout 源码
    -> 恢复 cache
    -> 下载依赖 Job 的 artifact
    -> 执行 before script
    -> 执行 build / test / deploy script
    -> 上传 artifact 和报告
    -> 清理环境
```

绝大多数 Job 成败最终都由进程退出码决定：退出码为 `0` 表示成功，非 `0` 通常表示失败。平台会将失败状态传播给依赖该 Job 的下游任务，并将结果回写到 PR/MR、Commit 或部署页面。

### 5. 日志、测试报告与部署记录

Runner 产生的标准输出、错误输出、测试 XML、覆盖率、制品清单和部署元数据，会被回传到控制平面。这样 PR/MR 页面中的绿色勾选并不是一句模糊的“成功了”，而是关联到：

```text
某个提交
    -> 某次 Workflow / Pipeline
    -> 若干 Job
    -> 每个 Job 的日志、执行环境、制品与退出状态
```

这就是 CI/CD 的审计与可追溯能力所在。

## 七、Artifact 和 Cache：不要让它们互相冒充

构建制品和缓存经常被误认为同一种东西，其实职责完全不同。

| 对比项 | Artifact，构建制品 | Cache，缓存 |
| --- | --- | --- |
| 目的 | 传递和保存本次构建结果 | 缩短后续运行时间 |
| 常见内容 | JAR、`dist/`、测试报告、安装包 | Maven、npm、pnpm、pip 依赖 |
| 是否与某次构建严格对应 | 是 | 不一定，允许失效和重建 |
| 是否可作为发布输入 | 应当可以 | 不应当 |
| 生命周期 | 通常绑定一次 Workflow/Pipeline 或制品仓库 | 通常跨多次运行复用 |

例如：

```text
~/.m2/repository     -> Maven 依赖缓存
target/app.jar       -> Java 构建制品

pnpm store           -> 依赖缓存
dist/                -> 前端构建制品
```

一个安全的原则是：**缓存只负责加速，制品才负责交付。**

生产部署应使用明确、不可变、可追溯的 Artifact 或镜像 digest。不要因为某台 Runner 恰好保留了一个 `dist/` 目录，就让它承担发布职责；那不是优化，而是把部署正确性寄托在运气上。

## 八、一份可靠 CI/CD 脚本应有哪些流程

并非每个项目都需要全部阶段。一个 Hugo 静态博客不需要数据库迁移和金丝雀发布，支付系统也不能只跑一次 `npm test` 就心安理得地上线。应当按风险和项目类型选择流程。

一条较完整的通用流水线通常长这样：

```text
触发与预检
    -> 环境准备和依赖恢复
    -> 格式化、静态检查、类型检查
    -> 单元测试和覆盖率
    -> 构建、打包和版本注入
    -> 安全与供应链检查
    -> 集成测试、端到端测试
    -> 保存和发布制品
    -> 部署测试或预发环境
    -> 冒烟测试和验收
    -> 生产审批、灰度或正式部署
    -> 线上监控、验证和回滚
```

### 1. 触发与预检

首先应决定本次变更应该跑什么：

- PR/MR：代码检查、测试和快速构建。
- 合并到主干：构建正式制品，部署测试或预发环境。
- 打 Tag：发布版本、推送正式镜像、准备生产部署。
- 文档或特定目录变更：只运行相关任务。
- 手动触发：执行回滚、重部署或专项任务。

合理的规则能避免无关变更触发昂贵的全量测试，也能确保真正的发布路径没有被遗漏。

### 2. 环境准备与依赖恢复

流水线要明确声明工具版本，而不是依赖 Runner 上“可能已经安装”的环境：

```text
JDK 21
Node.js 22
Maven 3.9
Python 3.12
指定版本的 Docker Buildx
```

这一阶段通常包括：checkout 固定 SHA、安装工具链、恢复依赖缓存、配置私有包仓库、启动测试服务。显式声明环境会让构建更可复现，也会让“本地能跑、CI 失败”的问题少一些。

### 3. 静态检查与质量门禁

速度快的检查应尽量前置：

- 代码格式检查。
- Lint。
- 类型检查。
- 编译告警检查。
- Markdown、链接和拼写检查。
- 提交消息、分支命名或版本号检查。

这些任务可以迅速反馈低成本问题，让代码评审更多关注设计、边界和业务行为，而不是反复讨论缩进和未使用变量。

### 4. 测试：从单元到端到端

测试通常分层进行：

| 测试类型 | 验证对象 | 特点 |
| --- | --- | --- |
| 单元测试 | 函数、类、模块 | 快、定位准确，应频繁运行 |
| 集成测试 | 服务与数据库、消息队列等依赖 | 更接近真实环境，成本更高 |
| 契约测试 | 服务间接口约定 | 降低联调和版本升级风险 |
| 端到端测试 | 用户完整操作路径 | 最真实，但慢且容易受环境影响 |
| 冒烟测试 | 部署后核心功能是否可用 | 快速验证环境和版本健康 |

单元测试通过不等于部署成功，部署成功也不等于用户真的能使用核心功能。不同层级各自回答不同问题，不应互相替代。

### 5. 构建、打包与版本信息

构建阶段把源码变为可交付物：

- Java 项目的 JAR、WAR。
- 前端项目的 `dist/`。
- Go 或 C/C++ 的二进制文件。
- Python 的 wheel 包。
- Docker 镜像。
- Hugo 的静态站点目录。

制品中最好记录版本、提交 SHA、构建时间和流水线编号：

```text
version: 1.8.0
commit: a1b2c3d
pipeline: 842
built-at: 2026-09-28T20:00:00+08:00
```

这样线上发生问题时，才能快速从运行版本反查源码和构建记录。

### 6. 安全与软件供应链检查

安全检查应在流水线中持续进行，而不是发布前临时补一份报告：

- SAST：扫描源码中的安全风险。
- SCA：扫描第三方依赖及其漏洞。
- Secret Scan：扫描是否提交了 Token、密码和私钥。
- 镜像扫描：检查基础镜像与应用镜像漏洞。
- IaC Scan：检查 Terraform、Kubernetes YAML 等基础设施配置。
- SBOM：生成软件物料清单。
- 制品签名与来源证明。

高危漏洞和明文密钥泄露通常应阻断发布；中低风险项可以告警并进入治理计划。所有告警都一视同仁地阻断，会让团队只想关闭工具；所有告警都不阻断，则工具又只剩下仪式感。安全门禁也需要分级。

### 7. 制品发布：构建一次，多环境提升

推荐的发布链路是：

```text
源码 commit a1b2c3d
    -> 构建一次
    -> artifact / image digest
    -> 测试环境
    -> 预发环境
    -> 生产环境
```

也就是说，测试、预发和生产应使用同一个构建制品，而不是每个环境重新从源码构建一次。否则测试环境验证的是 A，生产上线的是 B；即使两次构建看似相同，依赖下载、时间戳、构建环境差异也会使它们不再是同一个对象。

### 8. 环境部署、审批和并发控制

部署 Job 常常需要额外控制：

- 只允许主干或受保护 Tag 触发生产部署。
- 生产环境要求特定角色批准。
- 限制同一环境的部署并发，避免两个版本相互覆盖。
- 保存部署人、部署版本和目标环境记录。
- 部署失败后保留可诊断日志。

发布策略可以按风险选择：

| 策略 | 做法 | 优点 | 主要前提 |
| --- | --- | --- | --- |
| 滚动发布 | 分批替换旧实例 | 资源开销较小 | 新旧版本兼容 |
| 蓝绿发布 | 新旧环境并存后切流 | 回滚快 | 有足够资源和切流能力 |
| 金丝雀发布 | 少量用户先使用新版本 | 风险暴露更小 | 有流量治理和监控能力 |
| 全量发布 | 一次替换全部实例 | 流程简单 | 能接受集中风险 |

### 9. 上线后的验证与回滚

部署命令返回成功，只表示命令执行成功，并不等于服务真实健康。生产部署后至少应检查：

- 存活和就绪探针。
- 核心 API 或页面的冒烟测试。
- 错误率、延迟、吞吐量等监控指标。
- 关键日志与告警。
- 业务侧核心指标。
- 明确的回滚版本和回滚命令。

完整的判断应当是：

```text
构建成功
  != 部署命令成功
  != 服务进程存活
  != 用户请求正常
  != 业务指标正常
```

最后一层才是发布真正完成的标志。

## 九、GitHub Actions 的通用流水线示例

下面以 Node.js Web 项目为例，展示检查、测试、构建、制品传递和测试环境部署之间的关系。

```yaml
name: CI and Deploy

on:
  pull_request:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run lint

  test:
    name: Unit Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm test

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: web-dist
          path: dist/

  deploy-staging:
    name: Deploy Staging
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: staging
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: web-dist
          path: dist/
      - run: ./scripts/deploy-staging.sh
```

它的依赖图是：

```text
lint ─┐
      ├─> build ─> deploy-staging
test ─┘
```

这份配置体现了几个原则：PR 会运行检查、测试和构建，但不会部署；只有 `main` 分支上的构建才会继续部署测试环境；部署 Job 下载构建 Job 生成的 Artifact，而不是重新构建。

## 十、GitLab CI/CD 的通用流水线示例

同样的逻辑，在 GitLab 中可以写成：

```yaml
stages:
  - verify
  - test
  - build
  - deploy

default:
  image: node:22

cache:
  key:
    files:
      - package-lock.json
  paths:
    - .npm/

before_script:
  - npm ci --cache .npm --prefer-offline

lint:
  stage: verify
  script:
    - npm run lint

unit_test:
  stage: test
  script:
    - npm test

build:
  stage: build
  needs:
    - lint
    - unit_test
  script:
    - npm run build
  artifacts:
    name: "web-dist-$CI_COMMIT_SHA"
    paths:
      - dist/
    expire_in: 7 days

deploy_staging:
  stage: deploy
  needs:
    - job: build
      artifacts: true
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
  environment:
    name: staging
  script:
    - ./scripts/deploy-staging.sh
```

这里：

- `stages` 提供默认的可视化阶段顺序。
- `needs` 明确构建依赖检查和测试。
- `artifacts` 保存 `dist/`。
- `deploy_staging` 使用上游的 Artifact。
- `rules` 限制只有默认分支才会部署测试环境。
- `environment` 让 GitLab 将这次 Job 记录为一次 staging 部署。

## 十一、CI/CD 的安全边界

CI/CD 系统天然拥有较高权限：它能读源码、访问依赖仓库、推送镜像、调用云 API，甚至部署生产环境。因此安全不是最后加上的一个 Job，而是架构的一部分。

### 1. 最小权限与短期凭据

应当按 Job 赋予最小权限：

- 测试 Job 只需要读取源码和依赖。
- 发布 Job 才需要推送包或镜像的权限。
- 部署 Job 才需要访问目标环境。
- 生产部署权限不应出现在每个 PR Job 中。

对于云平台，优先采用 OIDC 等身份联邦机制换取短期凭据，而不是长期把云密钥写入平台 Secret。Secret 可以减少明文暴露，但长期静态密钥本身仍然有泄露和轮换成本。

### 2. 不能信任所有 PR/MR 代码

来自 Fork 或不受信任分支的 PR/MR，可能修改 CI 配置并试图打印密钥、访问内网或执行恶意命令。应当做到：

- 不向不受信任的代码注入生产 Secret。
- 不让外部 PR 随意使用内网和生产 Runner。
- 对部署 Workflow 使用受保护分支、Tag 和 Environment。
- 对第三方 Action 使用可信来源并固定到可靠版本或提交。
- 将普通构建 Runner 与生产部署 Runner 分隔。

安全模型的底线是：**执行不受信任代码的环境，不能顺手拥有高价值凭据。**

### 3. Runner 隔离与制品可信度

尤其在自建 Runner 中，应关注：

- 前一个 Job 是否会留下工作目录、容器、进程或密钥。
- 不同项目和不同信任级别的任务是否共享同一台机器。
- 构建镜像是否固定版本或 digest。
- 发布的 Artifact 是否来自通过门禁的 Pipeline。
- 生产是否部署了经过签名或可追溯的制品。

CI/CD 的权限链条越长，越需要把隔离、审计与可追溯性当作基础能力，而不是出了问题后的补救措施。

## 十二、总结

GitHub Actions 与 GitLab CI/CD 的 YAML 语法不同，但底层思想相同：由平台控制平面接收 Git 事件、解析配置和任务依赖，再由 Runner 在可控环境中执行 Job，最后把状态、日志、制品和部署记录回传。

理解 CI/CD 时，应当记住下面几点：

- CI 是自动构建和验证；持续交付强调随时可发布；持续部署则自动进入生产。
- GitHub Actions 的核心模型是 `Event -> Workflow -> Job -> Step -> Runner`。
- GitLab CI/CD 的常见模型是 `Pipeline -> Stage -> Job -> Script`，并可用 `needs` 建立 DAG。
- 控制平面负责解析、调度、状态和审计；Runner 才负责真正执行命令。
- 同一 Job 内的 Step 可以共享工作目录；跨 Job 应通过 Artifact 显式传递结果。
- Cache 用来加速，Artifact 用来交付，二者不应混用。
- 可靠流水线应覆盖预检、检查、测试、构建、制品、安全、部署、验证与回滚，但具体阶段必须与项目风险相匹配。
- CI/CD 拥有接近生产的权限，最小权限、Runner 隔离、受保护环境和可信制品不是可选装饰。

当你把流水线看成“围绕一次确定提交构建出的、可调度且可审计的任务图”，许多看似零散的问题——为什么 Job 不共享文件、为什么要上传 Artifact、为什么自建 Runner 有风险、为什么部署需要环境审批——都会有同一个清晰的答案。至于 YAML 的缩进为什么总在最不该出错的时候出错，那属于另一种更古老的工程学问题。
