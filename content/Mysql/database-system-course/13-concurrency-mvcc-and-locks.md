+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = '并发控制、MVCC 与锁'
+++

促销开始的瞬间，许多用户可能同时购买最后几本书。把所有事务完全串行化当然容易正确，却会牺牲吞吐；让所有请求随意交错，则可能读取未提交数据或相互覆盖结果。并发控制解决的并非“如何永不等待”，而是如何在正确性、并行度和可恢复失败之间建立清楚的契约。

本篇延续[事务、ACID 与故障恢复](12-transactions-and-acid.md)，从异常、隔离级别到 MySQL 8/InnoDB 中常见的 MVCC 与锁定读取。MVCC 是一类实现并发读的思想，不是“无需锁”的同义词；锁的实际范围还依赖索引与语句谓词，必须以测试和执行计划验证。

## 一、并发会带来的四种问题

设 `book(id=101, stock=5)`，两个事务交错时容易出现下列现象：

| 名称 | 过程 | 风险 |
| ---- | ---- | ---- |
| 脏读 | T1 读到 T2 未提交、后来回滚的 `stock=0` | T1 的判断建立在从未正式存在的数据上 |
| 不可重复读 | T1 两次读取同一行，T2 在中间提交更新 | 同一业务步骤得到相反的行值 |
| 幻读 | T1 两次按条件查询，T2 插入符合条件的新订单 | 被条件选中的“行集合”改变 |
| 丢失更新 | 两人基于旧值写回，后写覆盖先写 | 一次有效修改悄悄消失 |

幻读强调的是谓词结果集合。例如运营人员两次查询 `WHERE status='PENDING_PAYMENT'`，中间来了新订单，第二次多出一行。它不同于同一行的价格被改掉。还要注意：一个异常是否可观察到，既取决于隔离级别，也取决于查询是普通读还是加锁当前读。

## 二、四种隔离级别是可见性契约

| 隔离级别 | 典型语义 | 选择提示 |
| -------- | -------- | -------- |
| `READ UNCOMMITTED` | 可能读到未提交值 | 几乎不用于可信业务数据 |
| `READ COMMITTED` | 只读已提交值；同一事务两读可不同 | 常见 OLTP 选择 |
| `REPEATABLE READ` | 同一事务普通读通常使用稳定视图 | MySQL/InnoDB 常见默认值 |
| `SERIALIZABLE` | 效果接近逐事务串行 | 只在能接受更强冲突时使用 |

这些名称来自 SQL 标准，描述的是结果语义而不是统一算法。MySQL 中可检查、设定会话级别：

```sql
SELECT @@transaction_isolation;

SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
-- 下面的 SQL 使用本会话设定；结束后 COMMIT 或 ROLLBACK。
COMMIT;
```

把级别一路调高不是万能药。更强隔离会增大等待或重试，而“请求重复扣款”“库存更新不检查条件”本来就是业务建模错误，不能靠隔离级别修正。

## 三、快照读和当前读

多版本并发控制的直觉是：更新一行时，普通读者不必都等待写者完成；数据库可以让读者看到对自己一致的已提交版本。在 InnoDB 中，行版本与撤销信息支撑这种读法；具体物理结构属于实现细节，写 SQL 时应把握的是可见性语义。

在 InnoDB 常见情形下，普通 `SELECT` 是一致性读（也常称快照读），按事务读取视图返回可见版本。`UPDATE`、`DELETE` 和 `SELECT ... FOR UPDATE` 则需处理最新可操作的数据，属于当前读，并会配合锁来协调冲突：

```sql
START TRANSACTION;

-- 适用于展示；通常不为这行取得排他锁。
SELECT stock FROM book WHERE id = 101;

-- 若随后必须依据它修改，读取当前值并协调写竞争。
SELECT stock FROM book WHERE id = 101 FOR UPDATE;
UPDATE book
SET stock = stock - 1
WHERE id = 101 AND stock >= 1;
COMMIT;
```

不应把这段话过度简化为“普通读绝不阻塞、`FOR UPDATE` 永远只锁一行”。缺少可用索引的范围条件会扫描更多记录，锁定影响也可能扩大；DDL 或资源限制也会产生等待。良好的索引与精确谓词，本来就是并发设计的一部分。

## 四、用两个会话亲手观察

先将库存重置为 5：

```sql
UPDATE book SET stock = 5 WHERE id = 101;
```

然后在两个独立客户端按顺序执行。下面演示 `READ COMMITTED` 的不可重复读：

| 步骤 | 会话 A | 会话 B |
| ---- | ------ | ------ |
| 1 | `SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED; START TRANSACTION;` | |
| 2 | `SELECT stock FROM book WHERE id=101;`，得到 5 | |
| 3 | | `START TRANSACTION; UPDATE book SET stock=4 WHERE id=101; COMMIT;` |
| 4 | 再执行同一 `SELECT`，得到 4 | |
| 5 | `COMMIT;` | |

换成 `REPEATABLE READ` 后，若会话 A 两次都为普通一致性读，第二次通常仍可见到首次视图中的 5；若改为 `SELECT ... FOR UPDATE` 或 `UPDATE`，它面对的是当前数据，行为自然不同。隔离级别并没有让所有 SQL 都在时光中冻结。

对于最后一本书的争抢，不必先锁再读，条件更新本身就是清晰的并发控制：

```sql
START TRANSACTION;

UPDATE book
SET stock = stock - 1
WHERE id = 101
  AND stock >= 1;

SELECT ROW_COUNT();
COMMIT;
```

应用仅在 `ROW_COUNT()` 为 1 时创建订单。两个会话同时执行时，至多一个把库存从 1 改为 0；另一个在必要等待后会看到条件不再成立，影响 0 行。这比“两个请求都读到 1，随后无条件写 0”可靠得多。

## 五、悲观锁、乐观锁与索引

锁不是性能敌人，而是表达互斥需求的工具。多个仓储 worker 领取待发货订单时，确实需要避免拿到同一行，可以在极短事务中锁定并改状态：

```sql
START TRANSACTION;

SELECT id
FROM customer_order
WHERE status = 'PENDING_FULFILLMENT'
ORDER BY id
LIMIT 1
FOR UPDATE SKIP LOCKED;

UPDATE customer_order
SET status = 'FULFILLING'
WHERE id = 90001;
COMMIT;
```

`SKIP LOCKED` 适合 worker 分摊不同任务；它会跳过本应符合条件但被锁住的行，因此不适合作为用户列表或严格公平队列的通用“优化”。领取后不要在事务里调用快递接口，应先提交领取状态，再由后续流程处理外部动作。

另一种办法是版本列的乐观控制，适合冲突较少、用户编辑周期较长的订单操作：

```sql
UPDATE customer_order
SET status = 'CANCELLED', version = version + 1
WHERE id = 90001
  AND version = 12
  AND status = 'PENDING_PAYMENT';
```

影响 0 行说明订单已被他人改变或当前状态不允许取消；应重新读取并给出业务反馈，而非无条件重试。无论悲观还是乐观，都需要索引支持 `WHERE` 条件。扫描很宽的范围不只慢，也可能扩大冲突范围。

## 六、死锁不是灾难，缺少重试才是

若事务 A 先锁书 101 再锁 102，而事务 B 先锁 102 再锁 101，双方会形成等待环：

```mermaid
flowchart LR
    A[事务 A 持有书 101] --> AW[等待书 102]
    B[事务 B 持有书 102] --> BW[等待书 101]
    AW --> B
    BW --> A
```

InnoDB 可以检测许多死锁并回滚其中一个事务，释放资源给另一个继续。因此死锁错误是可预期的并发失败，应用要在**完整事务**边界做有限次数、带退避的重试。重试前提是请求有幂等键，或插入受唯一约束保护；否则重试可能创造第二张订单。

减少死锁和锁等待的可靠手段很朴素：全系统按相同顺序更新多行；让查询使用索引；批处理拆小；事务内不做慢 RPC 或用户交互；及时提交；记录等待 SQL 和耗时。单纯把超时时间调大，只是把队列拉得更长。

## 七、小结

- 脏读、不可重复读、幻读和丢失更新不是同一问题，分别需要正确的可见性与写入策略。
- 隔离级别是结果契约；在 InnoDB 中还应区分普通一致性读和当前读。
- MVCC 减少读写等待，却不能消灭写写冲突；条件 `UPDATE` 是库存扣减的优先方案。
- `FOR UPDATE`、`SKIP LOCKED` 与版本列各有适用业务，不应为了“更安全”而滥用。
- 死锁必须被当作可重试的正常结果；统一顺序、短事务、索引和幂等性共同决定系统的可用性。
