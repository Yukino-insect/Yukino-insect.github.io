+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '第二讲：自托管 Langfuse 的最小实验与数据流'
+++
第一讲在终端中看到了请求事实；本讲把事实送到一个可搜索、可查看时间线的后端。Langfuse 是面向 LLM 应用的观测平台：它提供 trace、generation、评分、数据集和提示词管理等能力。它不是模型网关，不负责替你的应用执行模型请求；应用仍须负责超时、鉴权、重试和业务正确性。

## 前置与实验目标

需要 Docker Desktop、Git 和第一讲的 Python 环境。完成后，浏览器能打开本机 Langfuse，Docker 状态中核心服务为 `running`，并能解释一条事件从 SDK 到页面前经过了哪些阶段。Docker Compose 适合本地学习和单机试验；它本身不提供高可用、横向扩容或成熟备份方案。

## 先理解：为什么不是“一个 Web 容器”

观测写入往往不立即完成，因为业务请求不应等着分析库写盘。典型数据流如下：

```text
应用 SDK / OTLP
  -> 接入 API：认证、校验、接收
  -> 队列：缓冲突发流量
  -> Worker：异步转换、聚合、写入
  -> 事务存储：用户、项目、配置
  -> 分析存储：高频 trace 与聚合查询
  -> 对象存储：较大附件或导出物
  -> Web / API：查询与展示
```

队列的价值是削峰和失败重试，不是无限的“防丢失黑洞”。Worker 停止时，接入端可能仍然成功返回；因此除了 HTTP 成功率，还必须观察队列深度、最老任务等待时间和写入错误数。

## 启动官方最小环境

最稳妥的起点是下载 Langfuse 官方仓库提供的 Compose 文件，而不是从博客复制一个可能过时、带默认口令的片段。打开 [官方 Docker Compose 部署说明](https://langfuse.com/self-hosting/deployment/docker-compose)，按当日版本执行其中的 clone 与启动步骤。下面命令只展示通用工作流；以该仓库当前文档中的配置项为准。

```powershell
git clone https://github.com/langfuse/langfuse.git
Set-Location langfuse
Copy-Item .env.example .env
# 用随机值替换 .env 中所有示例 secret；不要提交 .env
docker compose config --quiet
docker compose up -d
docker compose ps
```

`config --quiet` 会在启动前检查 YAML 和环境变量展开。`ps` 的预期是 Web、Worker、数据库、队列和对象存储相关服务逐步进入运行状态；首次拉取镜像和初始化会花几分钟。然后访问官方 Compose 文档所列的本机地址，创建第一个用户、组织和项目。界面生成的公钥/私钥属于运行期凭据，只应放在本地 `.env`、密钥服务或 CI 的 secret 中。

## 用健康检查代替“页面能打开”

页面能打开只证明反向代理或 Web 进程还活着。应同时检查每一段：

```powershell
docker compose ps
docker compose logs --tail 80 langfuse-web
docker compose logs --tail 80 langfuse-worker
docker compose logs --tail 80 redis
```

预期是没有连续重启、认证失败或连接拒绝；服务名可能随官方 Compose 演进，先以 `docker compose config --services` 列出的名称替换示例。不要为了“清空错误”先执行 `docker compose down -v`：`-v` 会删除命名卷，很可能把数据库与对象数据一并删除。

## 创建一条最小 trace

安装当前 Python SDK。SDK 与服务端版本有兼容要求，因此安装后先查看版本，并在部署时固定已验证的版本范围：

```powershell
python -m pip install langfuse
python -m pip show langfuse
$env:LANGFUSE_PUBLIC_KEY = '<项目公钥>'
$env:LANGFUSE_SECRET_KEY = '<项目私钥>'
$env:LANGFUSE_BASE_URL = 'http://localhost:3000'
```

下面示例故意只记录合成输入。SDK API 可能随大版本演进，若方法名不一致，应按 [Python SDK 文档](https://langfuse.com/docs/observability/sdk/overview) 调整，而不要降级整套服务来迁就旧代码。

```python
from langfuse import get_client

langfuse = get_client()

with langfuse.start_as_current_observation(name="demo.request") as trace:
    trace.update(input={"task_type": "short_copy", "input_length": 12})
    with langfuse.start_as_current_generation(
        name="demo.model",
        model="demo-model",
        input={"prompt_template": "welcome-v1"},
    ) as generation:
        generation.update(output={"text_length": 5}, usage_details={"input": 8, "output": 5})

langfuse.flush()
print("event submitted; open the project traces page")
```

预期终端打印 `event submitted`，随后在项目的 trace 列表看到 `demo.request` 和其下的 `demo.model`。事件可能异步处理，短暂延迟是正常的；超过几分钟仍不可见，则从环境变量、Web/Worker 日志、队列和系统时间依次查起。不要通过把私钥打印到终端来验证环境变量。

## 数据为什么会“过一会儿才出现”

异步平台通常有至少三个成功状态：接入端已接受、Worker 已处理、查询库已可见。把第一个状态误当成“永久保存成功”是常见误判。对关键审计或计费事实，应有独立的业务数据账本；观测平台可帮助诊断和分析，但不是自动获得法律审计语义的系统。

## 常见问题

1. **容器反复重启**：先看最早的错误而非最后一行。最常见是 `.env` 中必填 secret 缺失、端口已被占用、Docker 分配内存不足或旧数据卷不兼容。
2. **SDK 成功、页面无数据**：确认 `LANGFUSE_BASE_URL` 指向目标实例，公钥和私钥属于同一项目；再检查 Worker 是否运行。不要混用 Cloud 与本机项目的凭据。
3. **页面慢或查询超时**：区分写入积压和分析查询慢；前者看 Worker/队列，后者看分析数据库资源、时间范围和属性过滤。
4. **误以为 Compose 就是生产部署**：单机可能有单点、没有跨主机备份。生产选型须另行设计网络、TLS、身份、备份、容量和升级。

## 小结

- Langfuse 将 LLM 观测事件异步接入、处理并展示；Web 页面只是最后一层。
- 在本地跑通官方 Compose 的目标是理解数据流，不是复制一份生产架构。
- “SDK 没报错”与“数据已经可查询、且可恢复”是三种不同的结论。
