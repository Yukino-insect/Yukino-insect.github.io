+++
date = '2026-10-02T10:00:00+08:00'
draft = false
title = '文本排序的评测与运行：质量、延迟、容量与回滚'
math = true
+++

排序服务有两类不能互相替代的验收：**质量**回答“前几名是否更符合用户意图”，**性能**回答“在目标并发下是否足够快且不失控”。只压测接口，可能高效地返回一堆不相关结果；只看 nDCG，可能得到一个无法承受流量的模型。

## 建立一份可回归的标注集

先固定一小份代表性 query，每个 query 配若干 candidate，并由了解业务规则的人给出相关等级。等级可用 `0`（无关）、`1`（有帮助）、`2`（高度相关）。测试集必须与训练样本分开，并保留查询类型、语言、长度和数据版本，才能在模型或 tokenizer 更新后追踪变化原因。

```json
{
  "query": "静音 键盘",
  "candidates": ["静音机械键盘", "无线鼠标", "薄膜键盘"],
  "relevances": [2, 0, 1]
}
```

预期不是某个固定分数，而是每次模型变更前后都对**同一份冻结数据**运行。对新增业务类型另建集合，不能悄悄替换旧集合来掩盖退化。

## 计算 nDCG 与 MRR

nDCG 关注前 K 位的整体质量；越相关、越靠前，贡献越大。MRR 只看第一个正确结果，对 FAQ、工单路由等“尽快找到一个正确项”的任务有用。

```python
import math

def ndcg_at_k(rels: list[int], k: int) -> float:
    def dcg(xs: list[int]) -> float:
        return sum((2 ** rel - 1) / math.log2(i + 2)
                   for i, rel in enumerate(xs[:k]))
    ideal = dcg(sorted(rels, reverse=True))
    return dcg(rels) / ideal if ideal else 0.0

def reciprocal_rank(rels: list[int]) -> float:
    for position, rel in enumerate(rels, start=1):
        if rel > 0:
            return 1.0 / position
    return 0.0

rels = [2, 0, 1]
print(round(ndcg_at_k(rels, 3), 4), reciprocal_rank(rels))
```

预期输出约为 `0.9639 1.0`。注意函数输入是**模型已经排好序后的相关等级**，不是原候选顺序。真实评测程序需先按 API 返回的 `index` 重排标注。

除均值外还应查看分组结果：短 query 与长 query、不同语言、不同领域、含错别字的 query 是否都没有明显退化。少数类别被平均数掩盖，是排序迭代中最常见的错觉之一。

## 从调用方视角测延迟

单次耗时可分为排队时间、tokenize 时间、模型前向时间、序列化和网络时间。调用方看见的是总时间，所以 SLO（服务目标）也应从调用方测量。P50 表示中位数，P95 表示 95% 请求不超过的时间，P99 则暴露少量极慢请求；平均值常会掩盖排队造成的长尾。

```python
import statistics

latencies_ms = [18, 19, 20, 20, 21, 22, 26, 34, 90]
ordered = sorted(latencies_ms)
def percentile(p: float) -> float:
    i = min(len(ordered) - 1, int((len(ordered) - 1) * p))
    return ordered[i]

print("p50", percentile(0.50), "p95", percentile(0.95), "mean", statistics.mean(ordered))
```

预期输出显示 P95 接近最大值而平均值低得多，说明单看平均值会误判体验。严谨的压测工具应采用更准确的分位算法；本例仅用来建立直觉。

## 阶梯压测：一次只改变一个变量

压测前固定模型 revision、硬件、最大 token 长度和候选数。先用低并发验证正确响应，再以 1、2、4、8……逐级增加并发；每一级持续足够时间，记录吞吐（请求/秒）、P50/P95/P99、错误率、GPU/CPU 利用率、显存、队列长度和截断比例。不要同时改 batch、并发和模型，否则看到变化也无法归因。

```python
# 仅示意：在真实评测中加入超时、错误记录和并发控制
import time
import httpx

payload = {"query": "静音 键盘", "candidates": ["静音机械键盘"] * 10, "top_n": 5}
start = time.perf_counter()
response = httpx.post("http://127.0.0.1:8000/rerank", json=payload, timeout=10)
elapsed_ms = (time.perf_counter() - start) * 1000
print(response.status_code, round(elapsed_ms, 1))
```

预期状态码为 `200`，后面是一个非负毫秒数。该代码并不等于压测器；真正阶梯负载需要多个并发请求、预热、固定持续时间和完整指标采集。

## 用实验做取舍

若质量不足，先检查召回候选池是否包含正确项、输入字段是否完整、截断是否过多、标注是否一致；不要立刻换更大的模型。若 P95 过高，按顺序检查队列、候选数、长度分布、batch、模型设备和多实例分流。降低候选数通常会降低延迟，但可能降低质量，必须在同一评测集上比较。

容量结论应写成可验证句子，例如：“在最大 30 个候选、256 token、并发 4 的条件下，P95 小于 200 ms，错误率小于 0.1%。”脱离输入规模的“QPS=100”没有可迁移意义。

## 灰度、降级与回滚

发布新模型前，保存旧模型的 revision、tokenizer、依赖锁文件、评测报告和服务镜像标识。先让少量流量使用新版本，比较同一时段的质量代理指标、延迟、错误率和截断率；出现明显退化时切回旧版本。不要在故障发生后才尝试“重新下载之前的权重”。

可接受的降级顺序通常是：减少精排候选数 → 暂时使用更轻的模型 → 仅返回召回排序。降级前必须确认确定性权限/合规过滤仍会执行；为了快而跳过安全规则，称不上降级，只是制造事故。

## 常见错误与排查

- 离线指标上涨、线上反馈变差：检查测试集是否过时、线上 query 分布是否不同、业务过滤是否改变了候选池；不要仅凭一个均值决定发布。
- 压测比实际快得多：常见原因是数据过短、没有模拟并发、模型已热而生产会冷启动，或只测了 localhost 网络。
- P99 偶发尖峰：关联队列长度、GC、模型首次加载、GPU 利用率和长文本请求，而不是只重启进程。
- 回滚后仍异常：确认调用方真正切换了版本和缓存键，检查是否有残留实例继续接流量。

## 小结

- 排序质量要在冻结标注集上用 nDCG/MRR 等指标回归，性能要看 P95/P99 和错误率。
- 压测必须写清输入规模、并发、硬件和时长；单一 QPS 数字没有解释力。
- 灰度、可观察指标和可立即切换的旧版本，是模型服务上线的基本安全网。
