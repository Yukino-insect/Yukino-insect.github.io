+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = 'SQL 单表查询、聚合与分组：从行筛选到统计结论'
+++
表已由 [SQL 定义数据与完整性约束](04-sql-ddl-constraints.md) 守住基本正确性，查询的难题随即变成另一件事：如何用准确的条件表达问题，而不让 `NULL`、分组粒度或排序细节悄悄改变答案。本章以 MySQL 8 的在线书店 `books`、`orders` 表为例，讲单表 `SELECT`、筛选、表达式、聚合和分组。SQL 的逻辑处理顺序比书写顺序更重要：`FROM` 产生候选行，`WHERE` 筛行，`GROUP BY` 形成组，`HAVING` 筛组，`SELECT` 计算投影，最后 `ORDER BY` 与 `LIMIT` 排列和截取。

为了便于复现，先插入少量图书；真实项目当然不应每次查询都写这些样本。

```sql
INSERT INTO books (isbn, title, list_price, stock_qty, status, published_on)
VALUES
  ('9787300000001', '数据库系统概念', 88.00, 12, 'ON_SALE', '2025-03-01'),
  ('9787300000002', 'SQL 实战', 59.90, 0, 'ON_SALE', '2025-06-12'),
  ('9787300000003', '旧版算法笔记', 35.00, 3, 'OFF_SALE', NULL);
```

## SELECT：先说明需要哪些列

最基本的查询明确列出结果字段，而不是习惯性使用 `SELECT *`：

```sql
SELECT book_id, isbn, title, list_price, stock_qty
FROM books;
```

显式列有三个好处：减少无关数据传输；避免新加的列意外进入接口；同名列连接时更容易辨认。可以使用别名让结果更接近读者语言：

```sql
SELECT title AS 书名,
       list_price AS 标价,
       stock_qty * list_price AS 库存标价金额
FROM books;
```

`AS` 对列别名是清晰的写法。别名通常可在 `ORDER BY` 使用，但不能假设可在同层 `WHERE` 使用，因为 `WHERE` 的逻辑处理发生在 `SELECT` 之前；要筛选计算值，重复表达式或使用子查询/CTE。

`DISTINCT` 删除**结果行**完全相同的重复项，不是“按第一列去重”：

```sql
SELECT DISTINCT status FROM books;
SELECT DISTINCT status, stock_qty FROM books;
```

第二条按两个字段的组合去重。若需求是“每位顾客最近一笔订单”，`DISTINCT` 并不能正确选出“最近”，需使用窗口函数或先求最大时间，这将留给后续进阶主题。

## WHERE 与 NULL：三值逻辑的陷阱

`WHERE` 只保留条件结果为 `TRUE` 的行；`FALSE` 和 `UNKNOWN` 都会被排除。普通比较包括 `=`, `<>`, `>`, `>=`, `<`, `<=`，可由 `AND`、`OR`、`NOT` 组合。括号能让意图一目了然：

```sql
SELECT title, list_price, stock_qty
FROM books
WHERE status = 'ON_SALE'
  AND list_price BETWEEN 50.00 AND 100.00
  AND stock_qty > 0;
```

`BETWEEN 50 AND 100` 两端都包含。`IN ('ON_SALE', 'DRAFT')` 是同一列多值匹配的简洁写法；`LIKE 'SQL%'` 按模式匹配，`%` 匹配任意长度、`_` 匹配一个字符。对于前缀匹配，合适索引可能仍有帮助；`LIKE '%SQL%'` 的前导通配符通常难以使用普通 B-tree 索引。

最容易被忽略的是 `NULL` 不等于任何值，甚至不等于自己。`published_on = NULL` 的结果是 `UNKNOWN`，不会返回空日期图书；应写：

```sql
SELECT title FROM books WHERE published_on IS NULL;
SELECT title FROM books WHERE published_on IS NOT NULL;
```

同理，`NOT IN` 的候选集合若包含 `NULL`，比较可能都变为 `UNKNOWN`。涉及可空数据时，优先明确排除空值，或在跨表场景采用 `NOT EXISTS`。这是逻辑规则，不是 MySQL 的小怪癖。

## 表达式与 CASE：在查询中计算和分类

SQL 表达式可以进行算术、字符串和日期计算。`COALESCE(a, b, c)` 返回第一个非空值，很适合把展示用的缺失值替换为默认文本；它不应被用于掩盖本不应为空的建模错误。

```sql
SELECT title,
       list_price,
       COALESCE(published_on, DATE('1900-01-01')) AS published_on_for_export,
       CASE
         WHEN stock_qty = 0 THEN '缺货'
         WHEN stock_qty < 5 THEN '库存紧张'
         ELSE '可售'
       END AS stock_label
FROM books;
```

`CASE` 是标准 SQL 的条件表达式，适合报表标签、条件汇总和有限映射。它返回一个值，不能替代用 `WHERE` 排除行。更重要的是，若在索引列上随意套函数，如 `WHERE DATE(ordered_at) = '2026-10-20'`，常会使索引难以按范围访问；对于时间点，写半开区间通常更稳妥：

```sql
SELECT order_no, ordered_at
FROM orders
WHERE ordered_at >= '2026-10-20 00:00:00'
  AND ordered_at <  '2026-10-21 00:00:00';
```

## 排序与分页：没有 ORDER BY 就没有顺序承诺

关系和 SQL 结果集都不天然有顺序。即使某次恰好按主键返回，也不能依赖。要稳定排序，使用 `ORDER BY`，并在可能并列的列后补唯一的决定项：

```sql
SELECT book_id, title, list_price
FROM books
WHERE status = 'ON_SALE'
ORDER BY list_price DESC, book_id ASC
LIMIT 10 OFFSET 20;
```

这表示取第 21 至 30 条。数据频繁插入时，偏移分页可能出现重复或遗漏，且大 `OFFSET` 需要跳过很多行。连续翻页接口常以最后看到的 `(list_price, book_id)` 作游标（keyset pagination），用范围条件取下一页。`LIMIT` 是 MySQL 常用语法，标准 SQL 还定义 `FETCH FIRST` 等形式，跨产品时应检查方言。

## 聚合函数：从多行得到一个值

`COUNT(*)` 数行，`COUNT(column)` 数该列非空值；`SUM`、`AVG`、`MIN`、`MAX` 通常忽略 `NULL`。空输入上的 `COUNT(*)` 为 0，而 `SUM`、`AVG` 通常为 `NULL`：

```sql
SELECT COUNT(*) AS book_count,
       COUNT(published_on) AS dated_book_count,
       MIN(list_price) AS min_price,
       MAX(list_price) AS max_price,
       AVG(list_price) AS avg_price
FROM books
WHERE status = 'ON_SALE';
```

若“没有销售额应显示 0”，应明确表达展示规则：`COALESCE(SUM(amount), 0)`。千万别将 `COUNT(*)` 和 `COUNT(nullable_column)` 混用；前者回答“有多少行”，后者回答“有多少已填写该字段的行”。

订单表的按状态统计展示了分组的基础：

```sql
SELECT status,
       COUNT(*) AS order_count,
       SUM(shipping_fee) AS total_shipping_fee,
       AVG(shipping_fee) AS avg_shipping_fee
FROM orders
GROUP BY status
ORDER BY order_count DESC, status;
```

`GROUP BY status` 把状态相同的行压成一组，每组选出一行结果。`SELECT` 中非聚合列必须能由分组列唯一决定；MySQL 8 默认启用 `ONLY_FULL_GROUP_BY`，会拒绝含糊的写法。不要为了让语句通过而关闭它：含糊结果本就没有确定含义。

## WHERE 与 HAVING 分别过滤行和组

`WHERE` 在分组前过滤单行，`HAVING` 在分组后过滤聚合结果。查询“已支付或已发货状态中，订单数至少 10 的状态”应写：

```sql
SELECT status, COUNT(*) AS order_count
FROM orders
WHERE status IN ('PAID', 'SHIPPED')
GROUP BY status
HAVING COUNT(*) >= 10
ORDER BY order_count DESC;
```

把 `status IN (...)` 写进 `HAVING` 在某些情况下也能运行，却混淆层次并可能少了优化机会。相反，`WHERE COUNT(*) >= 10` 是非法的，因为那个阶段组尚不存在。记住一句即可：**行条件用 WHERE，聚合后的组条件用 HAVING**。

## 条件聚合与常见误差

一张报表可用 `CASE` 在一次扫描中统计多个类别：

```sql
SELECT
  COUNT(*) AS all_orders,
  SUM(CASE WHEN status = 'PAID' THEN 1 ELSE 0 END) AS paid_orders,
  SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_orders,
  COALESCE(SUM(CASE WHEN status IN ('PAID', 'SHIPPED')
                    THEN shipping_fee ELSE 0 END), 0) AS realized_shipping
FROM orders;
```

这比分别发出多条查询更易保证同一快照下的口径，但前提是状态定义清楚。报表最常见的错误不是函数拼错，而是把订单数、订单项数和图书种类数混为一谈；在多表连接后还会出现“连接放大”，下一章会专门处理。

## 小结

- `WHERE` 只保留真值；对 `NULL` 必须用 `IS NULL`，并理解三值逻辑。
- `ORDER BY` 才提供顺序，稳定分页应有确定的并列规则。
- 聚合的粒度由 `GROUP BY` 决定；`WHERE` 筛行、`HAVING` 筛组。
- 聚合前先用简单样本核对“数的是行、非空值还是不同值”。

单表查询能够回答局部问题，但书店事实分布在多张表。下一章 [SQL 连接、子查询、集合与 CTE](06-sql-joins-subqueries-sets.md) 将把这些关系正确地组合起来。
