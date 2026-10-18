+++
date = '2026-10-02T09:40:00+08:00'
draft = false
title = '把 OCR 脚本做成通用异步服务：任务、状态、幂等与回调'
+++

单机脚本适合学习和离线批处理，HTTP 接口适合让其他程序提交文件。两者之间最容易犯的错误，是在一次 HTTP 请求中上传大文件、同步转 PDF、渲染几十页、跑模型，然后等待十分钟才返回。代理可能超时，客户端断开后服务仍在跑，重试又会产生重复任务。**异步任务服务**的目标不是故作复杂，而是把“提交工作”和“取得结果”分开。

本章构建一个通用模型：客户端提交文件后立刻得到任务 ID；后台 worker 执行解析；客户端轮询状态或接收经签名的回调；所有结果都能以任务 ID 和输入哈希追溯。它不依赖某个项目、固定端口或默认密钥。

## 同步接口何时足够，何时不够

对一张小图片、耗时在几秒内且调用方能接受等待的情况，同步 `POST /ocr` 完全合理。下面任一条件出现时，更适合异步：

- 文件可能有数百页，耗时难预测；
- 要执行 Office 转换、GPU 推理或多个模型步骤；
- 调用方可能断线、刷新页面或重试；
- 需要排队限制并发，保护内存和 GPU；
- 结果需要被保存、下载或人工复核。

异步不是“返回 202 就完成了”。它要求清晰的状态机、可靠保存、幂等规则、失败语义和可观测性。

## 先设计任务状态机

状态必须是有限集合，而非任意字符串。一个足够小的模型是：

```text
accepted -> queued -> running -> succeeded
                    \-> failed
accepted -> cancelled
queued   -> cancelled
```

`accepted` 表示服务已接收并持久化请求；`queued` 表示等待 worker；`running` 表示正在处理；`succeeded` 和 `failed` 是终态。终态不应再回到 `running`。重试应创建新的尝试记录，或明确增加 `attempt`，不要悄悄覆盖上次失败的证据。

推荐任务记录包含：

```json
{
  "id": "job_01J...",
  "status": "queued",
  "created_at": "2026-10-02T01:40:00Z",
  "input": {"sha256": "...", "filename": "report.pdf", "bytes": 1830042},
  "options": {"language": "ch", "enable_table": false},
  "attempt": 1,
  "result_url": null,
  "error": null
}
```

注意：文件名不可信，`result_url` 在未完成前必须为 `null`，错误信息应给调用方可行动的代码（如 `unsupported_format`），详细堆栈只写受保护日志。

## API 契约先于框架

一个简单契约可以是：

```http
POST /v1/jobs
Idempotency-Key: 5b3e...
Content-Type: multipart/form-data

file=@report.pdf
options={"language":"ch","enable_table":false}
```

成功立即返回：

```json
{
  "id": "job_01J...",
  "status": "queued",
  "status_url": "/v1/jobs/job_01J..."
}
```

查询接口：

```http
GET /v1/jobs/job_01J...
```

完成后返回：

```json
{
  "id": "job_01J...",
  "status": "succeeded",
  "result": {"manifest_url": "/v1/jobs/job_01J.../manifest", "page_count": 12}
}
```

预期行为是客户端可以在任何时刻根据 `status` 做决定：继续等、展示进度、读取结果或提示失败。不要让客户端通过猜测“HTTP 200 是不是已经处理完”来推断状态。

## 一个最小 FastAPI 骨架

下面骨架只演示边界。生产中任务记录应放在数据库，文件放对象存储或受管卷，队列使用可恢复的消息系统；不能靠进程内字典承诺可靠性。

```python
from uuid import uuid4
from fastapi import FastAPI, File, Header, HTTPException, UploadFile

app = FastAPI()
jobs: dict[str, dict] = {}
idempotency: dict[str, str] = {}

@app.post("/v1/jobs", status_code=202)
async def create_job(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None),
):
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key is required")
    if idempotency_key in idempotency:
        return jobs[idempotency[idempotency_key]]
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise HTTPException(415, "unsupported media type")

    job_id = f"job_{uuid4().hex}"
    job = {"id": job_id, "status": "queued", "filename": file.filename}
    jobs[job_id] = job
    idempotency[idempotency_key] = job_id
    # 真实服务：流式写入受控存储，事务提交任务记录，再发送队列消息。
    return job

@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "job not found")
    return jobs[job_id]
```

运行：

```powershell
uvicorn app:app --reload
```

用 PowerShell 提交时，请为每次逻辑请求生成稳定的 `Idempotency-Key`；网络超时后的重试必须复用同一个 key。预期第一次和第二次返回同一个任务 ID。这个最小例子重启会丢失数据，正好说明为什么它只适合学习。

## worker：模型应常驻，任务应隔离

worker 的基本循环如下：

```text
取一条 queued 消息
  -> 原子地改为 running 并记录 attempt
  -> 下载/读取输入，验证哈希和选项
  -> 转换、渲染、OCR、写页级产物
  -> 先写 manifest，再原子更新为 succeeded
失败
  -> 记录错误分类、可否重试、失败时间
  -> 重试或更新为 failed
```

模型初始化通常昂贵，应该在 worker 启动时加载并复用，而不是每个任务加载一次。反过来，单个任务的临时目录、文件句柄和 GPU 张量必须在完成后释放；不要让上一个任务的文件状态泄漏给下一个任务。

### 为什么要先持久化，再投递消息

若先向队列发送消息、再写任务记录，worker 可能先取到消息却找不到任务；若先写记录、进程在发送消息前崩溃，则记录永远停在 `queued`。生产系统通常使用 outbox、事务消息或定期扫描补偿来缩小这个间隙。这里不存在一句“保证不丢”的魔法配置，只有可被监控和恢复的失败窗口。

## 幂等、重复与重试

**幂等**表示同一个逻辑请求重复执行，最终可观察结果相同。它不等于“用文件名去重”：两个同名文件可不同，两个不同名文件也可同字节。

建议同时使用：

- 调用方给出的 `Idempotency-Key`：避免网络重试重复创建任务；
- 输入 SHA-256 + 规范化 options：用于发现相同处理请求并复用或关联缓存；
- `attempt` 记录：保留每次执行的结果和错误。

只对暂时性错误重试，例如对象存储短暂不可用。格式不支持、密码保护 PDF、页数超限、模型明确拒绝的输入，不应反复重试。指数退避并设置最大次数；无限重试只是把错误变成队列积压。

## 回调并不是免费可靠性

客户端不想轮询时，可以在创建任务时提供 HTTPS 回调地址。服务完成后发送事件：

```json
{
  "event_id": "evt_...",
  "job_id": "job_01J...",
  "status": "succeeded",
  "occurred_at": "2026-10-02T01:45:00Z",
  "result": {"manifest_url": "..."}
}
```

必须使用每个租户独立的 secret 对原始请求体计算 HMAC，例如 `X-Webhook-Signature: sha256=<hex>`。接收方要校验签名和时间戳，并按 `event_id` 去重；网络会重复投递，不能假设“只来一次”。

回调地址是 SSRF 风险入口。服务端应限制协议为 HTTPS、校验域名 allowlist、拒绝内网和链路本地地址，并设置短超时和响应大小限制。切勿让任意用户提交一个 URL，就替其访问公司内网。

## 失败时怎样让人能恢复

| 类别 | 例子 | 处理 |
| --- | --- | --- |
| 输入错误 | 文件损坏、密码 PDF、超出限制 | `failed`，返回明确错误，不重试 |
| 可重试依赖错误 | 临时存储、队列网络故障 | 有限重试、退避、告警 |
| 资源不足 | GPU OOM、磁盘满 | 降低并发/限额，通常人工介入 |
| 程序错误 | 未处理异常 | 保留任务和关联日志，修复后新尝试 |

维护者应能从任务 ID 查到输入哈希、worker 版本、模型版本、各阶段耗时和最终 manifest；调用方应看到足以采取行动的错误码。两种信息的受众不同，不能混为一段堆栈。

## 可选的项目对照

若你手头已有 OCR 服务，可用本章清单审视它：它是否有真实持久化状态，而不是只靠内存？提交重试会否创建重复任务？回调是否签名和限制地址？模型是否每请求重载？结果是否能回到原始页？这比记住某个现有服务的路由名称有用得多。

## 小结

- 长文档解析应将提交和执行分离，任务状态机是接口的核心。
- 任务 ID、输入哈希、幂等键、尝试次数和 manifest 共同保证可追溯与可恢复。
- 队列、重试和回调都会失败，必须明确失败分类、限额和安全边界。
- 先做小而明确的 API 契约，再选择数据库、对象存储和消息队列实现。
