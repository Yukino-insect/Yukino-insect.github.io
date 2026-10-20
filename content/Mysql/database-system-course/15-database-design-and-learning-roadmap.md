+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = '数据库设计与课程学习路线'
+++

学完关系模型、SQL、索引、事务和运维后，真正应该带走的不是一套“建表口诀”，而是一条从需求到可靠运行的工作链。在线书店并不是先有一张 `customer_order` 表，再往上堆字段；它从用户要购买什么、库存如何扣减、支付如何确认、运营怎样查询，一步步推导出模式、约束、访问路径和运行指标。

本篇收束课程：用一次“创建订单并扣库存”的完整案例复盘设计方法，说明如何看 `EXPLAIN` 和关键监控指标，并划清 MySQL、Redis、Elasticsearch、ClickHouse 的职责边界。它们可以协作，但不应因为“看起来更快”而随便取代关系数据库中的交易事实。

## 一、从需求到模式：先写事实，再写表

先用自然语言列出不变量，而非直接挑数据类型：一本书有稳定标识、售价和可售库存；一个订单属于一个用户，包含一到多个订单项；订单项在下单时保存成交单价，不能随着图书现价变化；已支付订单不能随意回到待支付；库存不能小于零。将这些事实映射到关系、主键与约束：

```text
book(id, title, sale_price, stock)
customer_order(id, customer_id, status, total_amount, request_no, created_at)
order_item(order_id, book_id, quantity, unit_price)

book 1 --- n order_item n --- 1 customer_order
```

订单项保存 `unit_price` 是有意识的反规范化：它记录交易当时的事实，不能在查询历史订单时再 join 当前图书价格。反之，用户昵称等可变展示信息通常不应复制进每一张订单表，除非业务明确需要快照。设计的关键不是教条地“范式越高越好”，而是分辨哪些是同一事实、哪些是历史快照、哪些为读性能而冗余并需要维护规则。

## 二、约束、状态机与索引是不同层的工具

| 目标 | 首选机制 | 示例 |
| ---- | -------- | ---- |
| 行具有唯一身份 | 主键 | `book.id`、`customer_order.id` |
| 请求不可重复创建订单 | 唯一键 | `request_no` |
| 明细不能指向不存在订单 | 外键或受控应用写入 | `order_item.order_id` |
| 库存不能为负 | 条件更新、检查约束 | `stock >= 0` |
| 订单不能倒退状态 | 条件更新/状态机 | 仅 `PENDING_PAYMENT -> PAID` |
| 用户查最近订单 | 复合索引 | `(customer_id, created_at)` |

索引不是“把常用字段都建上”。它服务具体访问路径。若页面总是按用户查询最近订单，下面索引使筛选前缀与排序方向相匹配：

```sql
CREATE INDEX idx_order_customer_created
ON customer_order (customer_id, created_at DESC);

SELECT id, status, total_amount, created_at
FROM customer_order
WHERE customer_id = 7
ORDER BY created_at DESC
LIMIT 20;
```

而订单创建后的精确查询需要幂等键索引：

```sql
ALTER TABLE customer_order
ADD UNIQUE KEY uk_order_request_no (request_no);
```

唯一键既是查询优化，也把“同一请求只能生成一个订单”写进数据库。对交易正确性，约束比“先查询确认不存在，再插入”的应用约定可靠得多。

## 三、订单创建的安全最小闭环

订单创建应把不可分割的本地事实放入一个短事务：幂等请求只创建一次，库存只在充足时扣减，订单与明细一起写入。下列 SQL 是流程示意；生产代码还应将受影响行数、异常分类和事务边界处理清楚。

```sql
START TRANSACTION;

INSERT INTO customer_order
    (id, customer_id, request_no, status, total_amount, created_at)
VALUES
    (90011, 7, 'req-20261020-0001', 'PENDING_PAYMENT', 79.00, NOW());

UPDATE book
SET stock = stock - 1
WHERE id = 101 AND stock >= 1;

-- 若更新的行数不是 1，应 ROLLBACK；订单不能留下。
INSERT INTO order_item (order_id, book_id, quantity, unit_price)
VALUES (90011, 101, 1, 79.00);

COMMIT;
```

实际实现中，常先尝试按 `request_no` 建单；若唯一键冲突，则查询已有订单并返回，避免重复扣货。付款平台调用不应长时间包在本地锁事务内：先记录待支付订单，本地提交后发起外部支付；回调再以状态条件更新确认付款。若需要可靠通知下游，可采用事务内写出站事件、由独立投递器发送的模式，而非指望数据库事务跨越远程 HTTP。

支付确认也应有状态前置条件：

```sql
UPDATE customer_order
SET status = 'PAID', paid_at = NOW()
WHERE id = 90011
  AND status = 'PENDING_PAYMENT';
```

影响 1 行代表本次状态转换成功；影响 0 行则可能是重复回调、订单已取消或状态异常，应按当前订单状态做幂等响应或人工告警，不能盲目再次执行库存逻辑。

## 四、用 EXPLAIN 验证假设，而不是猜索引

给索引命名后不等于查询一定使用它。用 `EXPLAIN` 查看优化器计划，先关注访问方式、估算扫描行数、候选与实际键、排序和临时表等线索：

```sql
EXPLAIN
SELECT id, status, total_amount, created_at
FROM customer_order
WHERE customer_id = 7
ORDER BY created_at DESC
LIMIT 20;
```

理想计划常会使用 `idx_order_customer_created`，扫描较少的行并避免额外排序；但“出现 `key` 就一定好”也不成立。若某客户有绝大多数订单，选择性低；若查询返回很多列，回表成本仍可能高；统计信息过旧，估算也会偏差。优化流程应是：获得真实慢 SQL 与参数分布，读计划，确认索引和谓词，再修改并回归压测，而不是看到 `ALL` 就机械加索引。

可用 `EXPLAIN ANALYZE`（在支持的 MySQL 版本中）比较估算与实际执行时间、行数，但它会实际执行语句；对写语句或生产敏感查询要格外谨慎。性能问题有时根本不在 SQL：连接池耗尽、锁等待、磁盘饱和和网络抖动都可能使接口变慢。

## 五、监控把“数据库很慢”变成可回答的问题

至少把指标分为四类：

- **请求视角**：订单创建成功率、P50/P95/P99 延迟、错误码、重复请求比例。
- **SQL 与连接**：慢查询数量、QPS、活跃连接、连接池等待、扫描行数突增。
- **事务与锁**：事务持续时间、锁等待、死锁、回滚率、长事务。
- **实例与复制**：CPU、内存、磁盘延迟/空间、缓存命中、日志压力、副本延迟与复制错误。

告警应可行动。例如“订单 P99 升高且锁等待增长”提示先找热点行和长事务；“副本延迟过阈值”提示把一致性敏感读取切回主库；“备份连续失败”提示恢复能力正在退化。没有基线和关联 ID 的孤立仪表盘，只会让事故现场多几张好看的图。

## 六、何时引入 Redis、Elasticsearch、ClickHouse

MySQL/InnoDB 仍应保存订单、付款、库存等需要约束和事务保护的**权威交易事实**。其他系统是针对特定访问模式的投影或加速层：

| 需求 | 可考虑的系统 | 仍需注意 |
| ---- | ------------ | -------- |
| 热门图书详情、限频、短期会话 | Redis | 缓存失效、穿透、热点与源库一致性 |
| 图书全文检索、联想和复杂相关性排序 | Elasticsearch | 索引异步更新，不作为订单真相源 |
| 海量订单分析、报表聚合 | ClickHouse | 与 OLTP 分离，处理导入延迟与口径 |

Redis 不是库存扣减绕过数据库约束的理由；若采用缓存预扣，仍须设计与权威库存的对账、失败补偿和防超卖协议。全文搜索的资料可从站内 Elasticsearch 课程继续；分析型数据仓库可从[ClickHouse 课程导读](../../ClickHouse/clickhouse-course/00-overview.md)开始。Redis 的高可用与基础使用可参考[Redis 基础](../../Redis/Redis基础.md)和[Redis 高可用](../../Redis/Redis%20高可用.md)。这些链接是延伸路径，不重复本课程的事务和建模内容。

同样，已有的 MySQL 实践文章可作为专题查阅：[索引](../02-schema-and-indexes/索引.md)、[数据库事务的边界](../03-transactions-and-locks/数据库事务的边界.md)、[FOR UPDATE](../03-transactions-and-locks/FOR%20UPDATE.md)。当前课程的目的，是让你知道何时需要回到这些细节，而非把所有中间件堆进一个下单接口。

## 七、一条可复用的工作流

```mermaid
flowchart LR
    R[澄清需求与不变量] --> M[关系模型与约束]
    M --> I[按访问路径设计索引]
    I --> S[编写并验证 SQL]
    S --> T[设计事务、幂等与并发控制]
    T --> O[监控、备份、复制与演练]
    O --> R
```

这是一条循环，不是一次性交付。线上慢查询可能暴露新的访问路径；运营报表可能促使建立异步分析投影；事故演练可能发现 RTO 不达标。每一次调整都应回到不变量：优化不能破坏订单的唯一性、库存不能因为缓存或副本延迟而变成负数、可观测性不能依赖不可验证的猜测。

## 八、小结

- 先从业务事实和不变量建模，再决定表、字段、约束与历史快照，避免从“有哪些字段”反推业务。
- 主键、唯一键、外键、状态条件和索引解决不同问题，不能互相替代。
- 下单需要短事务、条件扣库存、幂等请求号与状态机；外部支付通过可靠异步流程衔接。
- `EXPLAIN` 与真实指标共同验证性能，锁等待、连接池和磁盘也可能是“慢 SQL”的根因。
- Redis、Elasticsearch、ClickHouse 是为缓存、搜索、分析而设的协作组件；权威交易事实仍应由关系数据库约束和事务保护。
