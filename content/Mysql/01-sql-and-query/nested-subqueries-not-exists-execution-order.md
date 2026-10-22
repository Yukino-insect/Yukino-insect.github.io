+++
date = '2026-10-22T19:50:00+08:00'
draft = false
title = '相关子查询与双重 NOT EXISTS：从逻辑执行到“全部满足”查询'
math = true
+++
一条嵌套 SQL 难读，通常不是因为括号太多，而是因为把两件不同的事混在了一起：**SQL 的逻辑语义**，以及数据库真正采用的**物理执行计划**。前者告诉我们结果为何正确；后者决定数据库怎样利用索引、连接和临时结构把结果算出来。先把逻辑语义读清楚，才有资格讨论快不快。否则只是把困惑交给优化器，颇为不负责任。

本文围绕下面这条查询，说明外层与内层怎样关联、双重 `NOT EXISTS` 到底否定了什么，以及“SQL 执行顺序”应当怎样理解。

```sql
SELECT DISTINCT p.customer_id
FROM purchase AS p
WHERE NOT EXISTS (
    SELECT 1
    FROM required_book AS r
    WHERE NOT EXISTS (
        SELECT 1
        FROM purchase AS bought
        WHERE bought.customer_id = p.customer_id
          AND bought.book_id = r.book_id
    )
);
```

这里假定：

- `purchase(customer_id, book_id, ...)` 记录顾客买过什么书；
- `required_book(book_id)` 列出一份必读书单；
- 目标是找出**买齐了必读书单中所有书**的顾客。

## 先读结果，而不是先背执行口诀

最外层的骨架是：

```sql
SELECT DISTINCT p.customer_id
FROM purchase AS p
WHERE ...;
```

它的候选行来自 `purchase p`。每一条购买记录都暂时对应一个候选行，`WHERE` 决定这条记录是否留下，最后 `DISTINCT` 把同一顾客因买过多本书而产生的重复 `customer_id` 去掉。

所以它**不是**逐行输出“购买记录”，而是最终输出顾客编号。`DISTINCT` 放在最后这件事很重要：同一名合格顾客若有十条购买记录，外层条件会对这十条记录分别成立，但最终只显示一次。

`WHERE` 中的整个条件可以先译成一句人话：

> 不存在一本必读书，是这位顾客没有买过的。

这句人话比连续读两个 `NOT EXISTS` 可靠得多。再把它拆开，括号就不再像某种恶意的俄罗斯套娃了。

## 认识相关子查询：内层并不总能独立运行

子查询有两类。**非相关子查询**不引用外层查询的列，可以独立理解。例如：

```sql
SELECT title
FROM book
WHERE book_id IN (
    SELECT book_id
    FROM required_book
);
```

内层只依赖 `required_book`，它的结果可以被看作一个书籍编号集合。

而原查询的子查询引用了外层的 `p.customer_id`：

```sql
SELECT 1
FROM purchase AS bought
WHERE bought.customer_id = p.customer_id
  AND bought.book_id = r.book_id;
```

其中 `p` 来自最外层，`r` 来自中间层；只有当前已经确定“正在检查哪位顾客、哪本必读书”后，最内层条件才完整。这就是**相关子查询**（correlated subquery）。别名的可见范围可以这样看：

```text
最外层：p 可见
  中间层：p、r 可见
    最内层：p、r、bought 都可见
```

内层能引用外层，外层却不能引用尚未定义的内层别名。这与程序中的局部作用域相似：变量不是凭心情出现的。

## 从最内层向外翻译

理解嵌套查询时，最稳妥的方法不是机械地问“谁先执行”，而是从最内层开始给每层写一个明确命题。

### 最内层：这位顾客买过这本必读书吗

固定一位顾客 `p.customer_id` 和一本必读书 `r.book_id` 后，最内层是：

```sql
SELECT 1
FROM purchase AS bought
WHERE bought.customer_id = p.customer_id
  AND bought.book_id = r.book_id;
```

`SELECT 1` 并不表示要取数字 1 作为业务结果；`EXISTS` 只关心“结果集中是否至少有一行”，选 `1`、`*` 或某个列在存在性上没有差别。写 `1` 是为了明确表达：**我不需要这些行的内容，只需要它们是否存在。**

因此，最内层 `EXISTS (...)` 的命题是：

```text
存在一条 purchase 记录，表示当前顾客买过当前这本必读书。
```

最内层外面紧接一个 `NOT EXISTS`，于是中间 `WHERE` 的条件变成：

```text
当前必读书是“当前顾客没有买过”的书。
```

### 中间层：找出顾客漏掉的必读书

中间层完整写法为：

```sql
SELECT 1
FROM required_book AS r
WHERE NOT EXISTS (
    SELECT 1
    FROM purchase AS bought
    WHERE bought.customer_id = p.customer_id
      AND bought.book_id = r.book_id
);
```

它会从必读书单中找出所有“该顾客没有买过”的书。因此，中间层结果的含义是：

```text
当前顾客缺少的必读书列表。
```

如果该列表至少有一行，说明顾客漏读了至少一本；如果它为空，说明书单里没有任何一本被漏掉。

### 最外层：没有漏书，才保留顾客

最外层再次套上 `NOT EXISTS`：

```sql
WHERE NOT EXISTS (
    -- 当前顾客缺少的必读书列表
)
```

因此其含义是：

```text
不存在任何一本顾客漏买的必读书。
```

也就是：这位顾客买齐了书单。最后的 `DISTINCT` 再把同一顾客的多条购买记录合并为一个编号。

用逻辑符号表达，原条件是：

$$
\neg \exists r \in RequiredBook,\; \neg \exists b \in Purchase:
(b.customer\_id = p.customer\_id \land b.book\_id = r.book\_id)
$$

它等价于：

$$
\forall r \in RequiredBook,\; \exists b \in Purchase:
(b.customer\_id = p.customer\_id \land b.book\_id = r.book\_id)
$$

也就是说：**对每一本必读书，都存在一条属于该顾客的购买记录。** SQL 没有直接写“对所有”的 `FOR ALL`，于是常用“没有反例”来表达全称条件。这种模式在关系数据库里称为**关系除法**（relational division）。

## 用一组小数据手工代入

假设必读书只有两本：

| `required_book.book_id` |
| ----------------------- |
| 101                     |
| 102                     |

购买记录如下：

| 顾客 | 买过的书 |
| ---- | -------- |
| A    | 101、102、103 |
| B    | 101      |
| C    | 101、102、102 |

检查顾客 A 时：

1. 中间层检查必读书 101；最内层能找到 A 买过 101，因此“未买过 101”为假。
2. 中间层检查必读书 102；最内层也能找到 A 买过 102，因此“未买过 102”为假。
3. 没有任何必读书通过中间层的 `WHERE`，所以中间层是空集。
4. 外层 `NOT EXISTS (空集)` 为真，A 的每条 `purchase p` 候选行都会保留。
5. `DISTINCT` 将这些候选行收敛为一行：A。

检查顾客 B 时：

1. 对 101，能找到购买记录，中间层不返回这一行。
2. 对 102，找不到购买记录，最内层 `NOT EXISTS` 为真；中间层返回 102 这一行。
3. 中间层非空，因此最外层 `NOT EXISTS` 为假；B 的候选行全部被过滤掉。

顾客 C 虽然把 102 买了两次，仍然合格。`EXISTS` 只要一条匹配记录就为真；“买齐”不是“每本刚好买一次”。若业务还要求每本只买一次，应另加唯一约束或专门的重复数据检查，不能把一个问题暗中塞给另一个问题。

## 所谓“执行顺序”：逻辑顺序和物理顺序必须分开

### 逻辑上，可以按“候选顾客—必读书—购买记录”理解

若把数据库当作一个用于理解语义的解释器，可以想象如下过程：

```text
对 purchase p 的每个候选行：
  令 c = p.customer_id
  在 required_book 中寻找任意一本 r：
    若不存在购买记录 bought，使其属于 c 且购买了 r：
      找到了漏书，淘汰当前 p 行
  若所有 r 都没有成为漏书：
    保留当前 p 行
最后对保留行的 customer_id 做 DISTINCT
```

这个过程解释了**相关性**：内层条件要拿到外层的 `p.customer_id`，中间层又为每本 `r.book_id` 提供条件值。它也解释了 `EXISTS` 的一个直觉：一旦找到能证明“存在”的行，逻辑上就够了；不必关心还有多少条相同匹配行。

但请不要把上面的伪代码误认为数据库承诺的逐行调用顺序。SQL 是**声明式语言**：你声明要什么结果，而不是命令数据库必须怎样循环。

### 物理上，优化器可以改写为反连接、半连接或集合运算

MySQL 等数据库的优化器可能：

- 使用 `(customer_id, book_id)` 索引快速验证最内层是否存在；
- 把 `EXISTS` 改写成半连接（semi-join），把 `NOT EXISTS` 改写成反连接（anti-join）；
- 先物化必读书集合，或调整表的访问顺序；
- 在确认等价的前提下提前过滤、合并子查询，避免真的对每条外层记录重复扫描。

所以“内层一定先执行一次，得到结果，再执行外层”只适用于**不相关子查询的粗略教学图像**，而且也不保证物理实现。对本例这种相关子查询，更准确的说法是：**内层的逻辑条件依赖当前外层绑定值；物理上优化器会选择任意保持同一结果的执行计划。**

要看某个 MySQL 实例实际怎么做，应使用：

```sql
EXPLAIN ANALYZE
SELECT DISTINCT p.customer_id
FROM purchase AS p
WHERE NOT EXISTS (
    SELECT 1
    FROM required_book AS r
    WHERE NOT EXISTS (
        SELECT 1
        FROM purchase AS bought
        WHERE bought.customer_id = p.customer_id
          AND bought.book_id = r.book_id
    )
);
```

`EXPLAIN ANALYZE` 展示的是该版本、该统计信息、该数据量下的实际执行信息，不是 SQL 语义本身。读语义用逻辑层，调性能看执行计划；两者各司其职，混在一起只会让结论失去可验证性。

## 一个更贴近需求的等价写法

原 SQL 以 `purchase p` 为外层来源，因此每位候选顾客会重复出现，最后才用 `DISTINCT` 去重。可以先构造“买过书的顾客集合”，使意图更直接：

```sql
SELECT c.customer_id
FROM (
    SELECT DISTINCT customer_id
    FROM purchase
) AS c
WHERE NOT EXISTS (
    SELECT 1
    FROM required_book AS r
    WHERE NOT EXISTS (
        SELECT 1
        FROM purchase AS bought
        WHERE bought.customer_id = c.customer_id
          AND bought.book_id = r.book_id
    )
);
```

它仍然是同一套“找不到漏书”的逻辑，但候选行的粒度一开始就是“每位顾客一行”。是否更快不能靠外观判断，仍要看 `EXPLAIN ANALYZE`；它首先带来的价值是降低阅读时的认知噪声。

若 `purchase` 是经常访问的大表，常见索引是：

```sql
CREATE INDEX idx_purchase_customer_book
ON purchase (customer_id, book_id);
```

这个索引与最内层的两个等值条件一致。`required_book.book_id` 也应有主键或唯一键。索引要由访问模式和实际计划验证，不是见到列名就条件反射地创建；索引同样需要写入维护成本。

## 两个边界条件

### 必读书单为空

当 `required_book` 没有任何行时，中间层对每位候选顾客都为空，外层 `NOT EXISTS` 都为真。因此原查询会返回**所有至少有一条购买记录的顾客**。逻辑上这是“空集合的所有元素都已满足”的真值，称为空真（vacuous truth）。

若业务要求“书单为空时不返回任何人”，应把这个业务规则明确写出来，例如额外要求书单存在：

```sql
WHERE EXISTS (SELECT 1 FROM required_book)
  AND NOT EXISTS (...原来的漏书检查...)
```

### `NULL` 与重复记录

本例使用 `NOT EXISTS`，不像 `NOT IN` 那样会因为子查询中出现 `NULL` 而轻易得到 `UNKNOWN`。不过 `customer_id`、`book_id` 本身仍应在合理模式中设为 `NOT NULL`，并分别用主键、外键等约束表达身份和引用关系。购买记录是否允许重复，也应由业务规则决定；`EXISTS` 会自然忽略“同一匹配出现几次”的差异。

## 小结

- 从内向外读这条 SQL：先判断“买过某本书”，再找“没买过的必读书”，最后要求“没有漏掉的书”。
- 双重 `NOT EXISTS` 表达的是“对所有必读书都满足”的关系除法，不是某种特殊的循环语法。
- 相关子查询的内层引用外层别名，因此需要当前外层行提供参数；但优化器不必真的按嵌套循环逐行执行。
- `DISTINCT` 是因为外层从购买记录出发，会让同一顾客多次成为候选；先得到顾客集合可使 SQL 更易读。
- 查询语义、索引与性能是三个不同层次的问题。语义先正确，执行计划再回答性能。

理解“查询怎样描述事实”之后，表结构中的 `NOT NULL`、`CHECK`、主键和外键又该怎样写，正是另一层同样不能靠直觉蒙混过去的规则。可继续阅读 [CREATE TABLE 的语法层级：列级约束、表级约束与主外键](../02-schema-and-indexes/create-table-constraint-syntax.md)。
