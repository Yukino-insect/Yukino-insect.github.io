+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '第三讲：Python 与 OpenTelemetry 埋点，从同步调用到跨服务 Trace'
+++
第二讲让平台接收事件，本讲回到应用代码。目标不是给每一行都套一个 span，而是在边界上留下足够的事实：请求从哪里来、调用了什么、花了多久、是否失败、消耗了多少资源。OpenTelemetry（OTel）提供了与后端无关的 trace 标准；Langfuse 可以接收其 LLM 语义相关数据，但你的代码不应因此失去可迁移性。

## 前置与实验目标

需要 Python 环境。完成后，程序应在终端输出一个根 span 和两个子 span，异常会被记录为 `ERROR`，并且 HTTP 出站请求可以携带 W3C `traceparent` 头。先用控制台 exporter 验证，再把 exporter 换成真实后端；这样排错路径最短。

## 初始化 SDK：API、SDK 与 exporter 的区别

`opentelemetry-api` 提供应用代码调用的接口；`opentelemetry-sdk` 负责采样、处理和导出；exporter 才知道怎样发送数据。业务库一般只依赖 API，应用入口再安装 SDK，避免一个库擅自覆盖全局 provider。

```powershell
python -m pip install opentelemetry-api opentelemetry-sdk
```

保存为 `otel_demo.py`：

```python
import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("copy.demo")

def model_call(text: str) -> str:
    with tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("gen_ai.request.model", "demo-model")
        span.set_attribute("app.input.length", len(text))
        time.sleep(0.02)
        return "欢迎使用"

with tracer.start_as_current_span("http.request") as root:
    root.set_attribute("http.request.method", "POST")
    try:
        with tracer.start_as_current_span("validate"):
            prompt = "写一句欢迎语"
        result = model_call(prompt)
        root.set_attribute("app.output.length", len(result))
    except Exception as exc:
        root.record_exception(exc)
        root.set_status(Status(StatusCode.ERROR, str(exc)))
        raise
finally:
    provider.shutdown()
```

运行 `python otel_demo.py`，预期输出多个 JSON span，其中 `llm.generate` 的 `parent_id` 对应 `http.request` 的 span ID，并出现 `gen_ai.request.model` 属性。若只有一条或没有输出，通常是忘了添加 `BatchSpanProcessor`，或程序过早退出而未调用 `shutdown()`。

## 什么该成为 span，什么只该成为属性

一个 span 表示可独立计时、可失败、需要排查的操作：HTTP 入站/出站、模型调用、数据库查询、工具执行、队列消费适合成为 span。模型名称、提示词版本、输入长度、重试次数适合作为属性。

不要为循环内每个 token 创建 span；高频小事件会带来昂贵的采集与查询负担。对流式生成记录一个 generation span，再记录 TTFT、总输出 token、终止原因即可。原文输入输出默认不传，只有经过权限设计、脱敏和保留期评审的字段才可采样保存。

## 为模型调用补齐业务语义

OTel 本身记录“调用发生了”，但平台无法从任意 HTTP span 猜出模型、用量和结束原因。一个通用 generation span 至少应该记录：

```text
模型请求：model、provider、temperature、input_token_count
模型结果：output_token_count、finish_reason、ttft_ms、cost.amount
运行结果：retry_count、outcome、error.type
关联版本：prompt_version、application_release、price_table_version
```

这些是建议字段，不要求照搬某家 SDK 的拼写。最重要的约束是：字段要有稳定含义、版本值可回溯、用户内容与秘密不能混入其中。

## 跨 HTTP 服务传播上下文

如果服务 A 调用服务 B，而 B 新建了不相关的 trace，就无法从一个用户请求看到完整路径。W3C Trace Context 使用 `traceparent` 等 HTTP 头传播当前上下文。实际 Web 框架优先使用经过验证的自动埋点；下面的最小例子帮助理解边界：

```python
from opentelemetry.propagate import inject

headers = {}
inject(headers)
print(headers)  # 含 traceparent；值每次不同
# 将 headers 作为 HTTP 客户端请求头发送给下游
```

下游在创建根处理 span 前提取这些头，新的 span 就成为同一 trace 的子节点。队列则不能只传业务消息；应同时传受控的 trace context。多条消息汇聚为一个批任务时，不存在唯一父节点，应使用 span link 或在应用层记录关联，而不是武断地选一个父 span。

## 线程、协程与重试的陷阱

Python 的 `asyncio` 通常能传播上下文，但自己创建线程池、回调或后台任务时可能丢失当前 context。先用控制台 exporter 检查 parent ID；若断链，在线程提交前复制并在工作线程 attach context，或使用框架/库的官方 instrumentation。重试也不应悄悄覆盖第一次失败：每次尝试可以是子 span，带 `retry.attempt`；根请求只在最终结果确定后标记状态。

## 导出到后端前的安全策略

先在应用边界做字段白名单，而不是希望查询界面“别显示”。一个简单原则：允许模型、版本、长度、耗时、状态、哈希和分类；默认拒绝 prompt、completion、Authorization、Cookie、邮箱、手机号和文件正文。对错误信息也要截断或清洗，因为异常文本可能包含请求内容。

采样同样是设计的一部分：错误 trace 可以较高比例保留，常规成功 trace 可按固定概率或按业务风险抽样；被抽样的事件必须带上采样策略版本，避免以为它代表全部流量。

## 常见错误与排查顺序

1. **span 没有父子关系**：确认使用 `start_as_current_span`，而非只 `start_span`；检查异步/线程边界是否复制了上下文。
2. **导出让接口变慢**：使用 `BatchSpanProcessor` 和有界队列；观测失败应降级记录并暴露自身指标，不应无限阻塞关键请求。
3. **错误没有显示**：捕获异常后同时 `record_exception` 与设置 `StatusCode.ERROR`，最后仍按业务语义抛出或返回。
4. **属性太多或泄密**：在 exporter 之前执行白名单和脱敏；不要依靠人为“以后不看这些字段”。

## 小结

- OTel 将埋点 API 与后端解耦，先用控制台 exporter 验证关系最容易学习。
- span 代表可计时的操作，属性补充稳定的上下文；两者都必须控制体积与隐私。
- HTTP、队列和并发边界是 trace 最容易断开的地方，应主动验证 parent ID 与链接关系。
