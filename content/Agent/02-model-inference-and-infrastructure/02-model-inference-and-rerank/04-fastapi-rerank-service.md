+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = 'FastAPI 实战：把文本排序模型做成可靠的 HTTP 服务'
+++

脚本中的 `score(query, candidate)` 只能给 Python 调用者使用。服务化的目的，是让 Java、Web、任务程序等不同调用者通过稳定 HTTP 契约请求排序，同时把模型加载、输入限制、超时和故障隔离留在服务内部。一个排序 API 的第一原则不是“多快返回”，而是对错误输入和资源压力有明确行为。

## 先设计请求与响应

一个最小请求应包含 query、候选文本和要返回的数量。响应除了 score，还必须携带输入时的 `index`；否则调用方无法把排序结果映射回自己的商品 ID、文档 ID 或权限信息。

```json
{
  "query": "静音 键盘",
  "candidates": ["静音机械键盘", "无线鼠标"],
  "top_n": 1
}
```

```json
{
  "results": [
    {"index": 0, "score": 0.91}
  ]
}
```

注意：示例分数只是说明格式，不是任何具体模型必然输出。API 的可测试承诺应是长度、原下标、降序和输入校验，而不是固定某个浮点小数。

## 用一个可替换的 scorer 搭起服务

先使用确定性的词重叠 scorer，这样不依赖大模型下载也能完成接口实验。之后只需将 `score_pairs` 的实现换成 tokenizer + 预训练 cross-encoder 推理，Pydantic 契约、健康检查和错误边界不必重写。

```python
# app.py
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="text-reranker")

class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    candidates: list[str] = Field(min_length=1, max_length=100)
    top_n: int = Field(default=10, ge=1, le=100)

    @field_validator("candidates")
    @classmethod
    def no_blank_candidate(cls, values):
        if any(not item.strip() or len(item) > 5000 for item in values):
            raise ValueError("candidate must be non-blank and at most 5000 chars")
        return values

def tokens(text: str) -> set[str]:
    # 中文没有天然空格；这是仅用于接口练习的单字重叠规则。
    chinese = {ch for ch in text if '\u4e00' <= ch <= '\u9fff'}
    latin_words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return chinese | latin_words

def score_pair(query: str, candidate: str) -> float:
    q, d = tokens(query), tokens(candidate)
    return len(q & d) / max(len(q), 1)

@app.get("/health/live")
def live():
    return {"status": "ok"}

@app.post("/rerank")
def rerank(request: RerankRequest):
    if request.top_n > len(request.candidates):
        raise HTTPException(422, "top_n must not exceed candidates length")
    items = [
        {"index": i, "score": score_pair(request.query, text)}
        for i, text in enumerate(request.candidates)
    ]
    items.sort(key=lambda item: item["score"], reverse=True)
    return {"results": items[:request.top_n]}
```

启动并请求：

```powershell
uvicorn app:app --host 127.0.0.1 --port 8000
```

```powershell
$body = @{ query = '静音 键盘'; candidates = @('静音机械键盘', '无线鼠标'); top_n = 1 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/rerank -ContentType application/json -Body $body
```

预期响应的 `results` 只有一项，`index` 为 `0`。另开窗口请求 `http://127.0.0.1:8000/docs`，可看到 FastAPI 自动生成的交互文档。

## 将玩具 scorer 替换为模型时的边界

真正的模型应在进程启动时或受控的首次请求时加载一次，而不是每个请求重新下载或构造。加载成功后，`/health/ready` 才应返回成功；`/health/live` 只回答进程是否活着。这样编排器不会把“端口已打开、模型仍在加载”的实例错误分流量。

模型请求前应执行四个限制：候选数上限、每条文本 token 上限、请求总字节数上限、并发/排队上限。字符数只能拦截明显滥用，真正的序列长度必须由 tokenizer 统计。请求超过预算时返回 422 或 413；服务器繁忙时返回 429 或 503 并给出重试提示，不能让无限队列把显存和尾延迟一起拖垮。

```text
HTTP 请求
  → Pydantic 格式检查
  → 字符/候选数限制
  → tokenizer token 限制
  → 有界队列或信号量
  → 单例模型 inference_mode 推理
  → index + score 响应
```

## 微批与并发

GPU 更喜欢 batch，但网络请求独立到达。微批队列会在很短的窗口（例如数毫秒）收集多个请求后合并推理，再按请求拆回结果。它能提高吞吐，也会让低流量请求多等一会儿。实现前先测单请求的 P95；如果延迟预算只有几十毫秒，不能随意把等待窗口设得很长。

初学阶段可以先用一个进程、一个模型实例和受限并发获得正确行为。不要用多个 Web worker 试图提高 GPU 吞吐：每个 worker 很可能加载独立权重，结果是 OOM。扩容通常应以多个独立实例配合负载均衡实现。

## 常见错误与排查

- `422 Unprocessable Entity`：这通常是输入校验生效，不是服务崩溃；查看响应中的字段路径并修正 JSON 类型、空字符串或 `top_n`。
- `Connection refused`：确认 Uvicorn 仍在运行，端口一致；先访问 `/health/live` 区分网络问题和业务请求问题。
- 第一次请求特别慢：模型可能在首次请求下载或加载。将下载和预热放进部署流程，并用 ready 探针隔离加载期。
- 返回顺序和原候选对不上：检查响应是否保留 `index`，不要只返回重排后的文本数组。
- 并发后延迟飙升/OOM：统计队列长度、候选数与 token 长度；先设置并发上限和 503 降载，再讨论微批。

## 小结

- API 契约要保留原下标，并把输入限制写成可机器验证的规则。
- live 不等于 ready；模型加载、权重校验和预热完成后才应接流量。
- 先让单例模型在有界并发下正确服务，再以测量结果引入微批和横向扩容。
