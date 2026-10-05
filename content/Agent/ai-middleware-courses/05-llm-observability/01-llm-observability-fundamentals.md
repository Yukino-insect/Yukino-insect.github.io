+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '第一讲：从一次请求理解日志、指标、Trace 与 LLM 指标'
math = true
+++
本讲只解决一个问题：当用户说“生成按钮转了十秒”时，你怎样从系统证据中找出是哪一步慢了。先不要安装任何平台。理解最小事实模型，比先学某个产品的界面更重要。

## 前置与实验目标

你需要导读中的 Python 环境。本讲结束时，运行一个脚本应打印两行结构化日志，并得到一次请求的耗时、首个输出到达时间和 token 估算值。这里的“模型”是本地函数，目的是隔离网络和计费变量。

## 从一条日志开始

最早的做法通常是：请求开始打印一行，结束打印一行。它对定位异常很有用，却不能回答“过去一小时 95% 的请求有多慢”，也无法可靠关联一次请求跨越的 HTTP、模型和数据库调用。

```python
import json
import time
import uuid

request_id = str(uuid.uuid4())
started = time.perf_counter()
print(json.dumps({"event": "request.started", "request_id": request_id}))
time.sleep(0.03)
elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
print(json.dumps({"event": "request.finished", "request_id": request_id, "elapsed_ms": elapsed_ms}))
```

预期输出中的两个 `request_id` 相同，而具体 UUID 与耗时不同：

```text
{"event": "request.started", "request_id": "..."}
{"event": "request.finished", "request_id": "...", "elapsed_ms": 30.1}
```

如果没有输出，先确认在激活虚拟环境后的终端执行了 `python 文件名.py`。如果 JSON 输出被混入普通 `print`，后续日志收集器可能无法解析；把诊断文本也写成结构化字段，或输出到 `stderr`。

## 三种信号，各回答不同问题

| 信号 | 记录形态 | 擅长回答的问题 | 常见误用 |
| --- | --- | --- | --- |
| 日志 | 一条离散事件 | 这次失败的异常是什么 | 把所有原文和密钥永久写入 |
| 指标 | 可聚合数值序列 | 错误率、p95 是否上升 | 用用户 ID 作为标签 |
| Trace | 一次工作的因果树 | 这次请求在哪一步耗时 | 把它当长期业务审计账本 |

**指标的标签必须低基数。**`model_family=small`、`outcome=success` 的可能取值有限；`trace_id`、手机号、订单号、完整 prompt 几乎每次都不同。后者如果成为指标标签，会持续创建新时间序列，反而让监控系统变慢。它们适合出现在经过脱敏的日志或 trace 属性中。

## Trace 与 span：一次请求的时间线

一个 **trace** 表示一次端到端工作，例如“生成一份邮件”。一个 **span** 表示其中一段有开始和结束的工作，例如“验证输入”“调用模型”“保存结果”。根 span 通常是 HTTP 请求，子 span 自动继承根的 trace ID。

```text
trace: generate-email
├─ span: validate-input       2 ms
├─ span: llm.generate       420 ms
│  └─ span: first-token      85 ms
└─ span: save-result          6 ms
```

这里的树不是调用栈的截图。并行任务可能有同一个父 span，也可能因队列而成为新的 trace；后者应通过链接或携带上下文表达“有关联”，不要伪造为同步父子关系。

## LLM 请求比普通 HTTP 多出的事实

一次生成至少应区分下面的字段。它们是数据模型，不绑定供应商：

- `model`、`model_version`、`prompt_version`：用于比较变更，不记录秘密提示词。
- `input_tokens`、`output_tokens`：优先使用供应商返回的 usage；没有时才标记为“估算”。
- `time_to_first_token_ms`（TTFT）：流式响应开始出现第一个 token 的等待时间。
- `duration_ms`：从请求开始到完整响应或失败的总时间。
- `outcome`：成功、调用方取消、可重试失败、不可重试失败；不要只有布尔值。

假设输入每百万 token 单价为 $I$、输出单价为 $O$，本次输入、输出 token 分别为 $t_i,t_o$，则成本为：

$$
cost = \frac{t_i}{10^6}I + \frac{t_o}{10^6}O
$$

价格会变，故成本记录还必须带上 `price_table_version` 和币种；不能把今天的价目表套到半年前的请求。

## 最小实验：观察流式首字节

保存为 `signals_demo.py` 后运行。它把“模型生成”模拟成先等待、再逐字产生字符：

```python
import time

def fake_stream():
    time.sleep(0.08)
    for token in ["你", "好", "，", "世", "界"]:
        time.sleep(0.01)
        yield token

started = time.perf_counter()
first_token_at = None
text = []
for token in fake_stream():
    if first_token_at is None:
        first_token_at = time.perf_counter()
    text.append(token)

finished = time.perf_counter()
print({
    "text": "".join(text),
    "ttft_ms": round((first_token_at - started) * 1000, 1),
    "duration_ms": round((finished - started) * 1000, 1),
    "output_tokens_estimated": len(text),
})
```

预期 `ttft_ms` 大约 90 ms，`duration_ms` 大约 130 ms。TTFT 很低而总耗时很高，常意味着输出很长或生成速度慢；TTFT 本身很高，才更可能是排队、建连、输入过长或模型首轮计算的问题。不要将两者混为“延迟”。

## 分位数比平均数更诚实

十次请求中九次为 100 ms、一次为 5 秒，平均值约 590 ms，却掩盖了大多数人的体验。将样本升序排列后，p95 表示约 95% 的样本不超过的值。样本很少时 p95 不稳定，不能只用三次请求就宣称性能达标；指标系统通常通过直方图近似计算并按固定窗口聚合。

## 常见错误与排查顺序

1. **没有关联 ID**：确认日志的开始和结束事件携带同一 `request_id`；后面用 trace ID 替代或补充它。
2. **TTFT 为负或大于总时长**：只使用同一个单调时钟 `time.perf_counter()` 计算单进程耗时，不要混用服务器时间戳。
3. **token 数量不可信**：先检查供应商响应的 `usage`；若使用字符数估算，字段名必须带 `estimated`，不可用于精确计费。
4. **日志泄露内容**：默认记录长度、哈希或分类，不记录原始输入输出；脱敏应在发送到观测后端之前完成。

## 小结

- 日志、指标、trace 分别服务于细节、趋势和因果路径。
- trace 是 span 的有向时间树；一次请求是学习它的最小单位。
- 对 LLM，TTFT、总耗时、用量、版本和结果状态比单一 `200` 更有解释力。
