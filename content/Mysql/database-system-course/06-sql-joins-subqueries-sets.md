+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = 'SQL 连接、子查询、集合与 CTE：正确组合分散的事实'
+++
规范化把顾客、订单、图书和订单项分别保存，避免更新异常；代价是查询时必须把事实重新组合。若连接条件写漏一项，结果不会报错，而会膨胀成一张看似合理的错误报表。因而本章的重点并非背语法，而是先问清楚：结果的一行代表什么？一位顾客、一张订单、一条订单项，还是一个存在性判断？前置的 [单表查询、聚合与分组](05-sql-query-and-aggregation.md) 已给出 `SELECT` 基础，以下继续使用 MySQL 8 的书店模式。

## INNER JOIN：只留下匹配的两端

订单和顾客是一对多。下列查询的一行代表“一张订单”，所以从 `orders` 出发，按外键连接 `customers`：

```sql
SELECT o.order_no,
       o.ordered_at,
       o.status,
       c.display_name,
       c.email
FROM orders AS o
JOIN customers AS c
  ON c.customer_id = o.customer_id
WHERE o.status IN ('PAID', 'SHIPPED')
ORDER BY o.ordered_at DESC, o.order_id DESC;
```

未写连接类型的 `JOIN` 即 `INNER JOIN`，只返回满足 `ON` 条件的组合。别名不仅缩短文字，更明确了每列来源；多个表都可能有 `status`、`id` 时应始终带上别名。将连接条件放在 `ON`、业务筛选放在 `WHERE`，也更容易检查遗漏。

要展示订单内购买的图书，粒度改为“订单项”：

```sql
SELECT o.order_no, oi.line_no, b.title,
       oi.quantity, oi.unit_price,
       oi.quantity * oi.unit_price AS line_amount
FROM order_items AS oi
JOIN orders AS o ON o.order_id = oi.order_id
JOIN books AS b ON b.book_id = oi.book_id
WHERE o.order_no = 'SO202610200001'
ORDER BY oi.line_no;
```

不要看到多行就慌忙加 `DISTINCT`。一张订单有三项商品，本来就应产生三行；`DISTINCT` 可能掩盖连接错误并悄悄丢掉合法的重复值。

## OUTER JOIN：保留“没有匹配”的一端

`LEFT JOIN` 保留左表全部行，右侧没有匹配时右列补 `NULL`。例如查找从未下过订单的顾客：

```sql
SELECT c.customer_id, c.display_name
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;
```

这是一种反连接写法。关键点是对右表的主键判空；不要判可空业务列。`RIGHT JOIN` 可读性通常不如交换两表后写 `LEFT JOIN`，实际项目常少用。`FULL OUTER JOIN` 是标准 SQL 中有的概念，但 MySQL 8 **不原生支持**；需要时可在确认语义后用两个方向的 `LEFT JOIN` 加 `UNION` 模拟，或换用支持它的数据库。

外连接最大的陷阱是把右表过滤条件写进 `WHERE`：

```sql
-- 错误：WHERE 会排除右侧为 NULL 的行，LEFT JOIN 退化为 INNER JOIN
SELECT c.display_name, o.order_no
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.customer_id
WHERE o.status = 'PAID';

-- 正确：仍保留没有已支付订单的顾客
SELECT c.display_name, o.order_no
FROM customers AS c
LEFT JOIN orders AS o
  ON o.customer_id = c.customer_id AND o.status = 'PAID';
```

第二条中每位顾客仍出现，未匹配者订单号为 `NULL`。若需求只要“至少有已支付订单的顾客”，则改回 `INNER JOIN` 或 `EXISTS`，不要为了形式使用外连接。

## SELF JOIN 与 CROSS JOIN 的边界

自连接表示表中的关系指向同一张表。假设 `customers` 增加了可空的 `referrer_id`（推荐人）：

```sql
SELECT child.display_name AS customer_name,
       parent.display_name AS referrer_name
FROM customers AS child
LEFT JOIN customers AS parent
  ON parent.customer_id = child.referrer_id;
```

同一张表必须使用两个别名，才能区分角色。`CROSS JOIN` 则不使用匹配条件，产生笛卡尔积：1000 位顾客与 500 本书将产生 50 万行。它在生成“日期 × 门店”等完整矩阵时有用途，却绝不能用来“先连接再想想条件”。意外漏写 `ON` 是 SQL 中代价很高的错误；先检查预期行数，再运行大连接。

## 子查询：按问题选择形状

子查询既可出现在条件中，也可作为一个派生表。`EXISTS` 只关心是否至少存在一行，十分适合存在性问题：

```sql
SELECT c.customer_id, c.display_name
FROM customers AS c
WHERE EXISTS (
  SELECT 1
  FROM orders AS o
  WHERE o.customer_id = c.customer_id
    AND o.status IN ('PAID', 'SHIPPED')
);
```

这是相关子查询：内层引用外层的 `c.customer_id`。语义是“对每位顾客测试是否存在合格订单”，不是把订单列取回来，因而也不会像 `JOIN` 一样因多笔订单复制顾客行。

`IN` 适合与一个单列集合比较：

```sql
SELECT title, list_price
FROM books
WHERE book_id IN (
  SELECT oi.book_id
  FROM order_items AS oi
);
```

当子查询列可能为 `NULL` 时，`NOT IN` 会受三值逻辑影响，常使结果意外为空；“没有被购买过的书”最好写成 `NOT EXISTS`：

```sql
SELECT b.book_id, b.title
FROM books AS b
WHERE NOT EXISTS (
  SELECT 1 FROM order_items AS oi WHERE oi.book_id = b.book_id
);
```

标量子查询必须至多返回一个值。下例比较每本书价格与全站平均价：

```sql
SELECT title, list_price
FROM books
WHERE list_price > (SELECT AVG(list_price) FROM books);
```

若子查询返回多行，使用 `=` 会报错；应根据语义选择聚合、`IN`、`EXISTS` 或连接。相关子查询写得清晰并不必然慢，优化器可能改写它；性能结论应以 `EXPLAIN` 和实际数据验证，不要凭“子查询一定慢”的旧说法判断。

## UNION、INTERSECT 与 EXCEPT

集合运算要求各分支列数一致、相应类型兼容。`UNION` 默认去重，`UNION ALL` 保留重复且通常更省成本：

```sql
SELECT customer_id, 'ORDER' AS source FROM orders
UNION ALL
SELECT customer_id, 'EMAIL' AS source FROM newsletter_subscriptions;
```

若业务确实只要集合成员，再写 `UNION`；不要为“保险”去重。标准 SQL 有 `INTERSECT`（交集）和 `EXCEPT`（差集），MySQL 8.0.31 起支持这些运算符；较旧的 MySQL 版本不支持，需用 `EXISTS`/`NOT EXISTS` 或连接改写。即使在支持的版本，也要核对 `NULL`、重复消除和排序需求，而非想当然地照搬其他产品教程。

## WITH：给复杂查询取名字

公共表表达式（CTE）用 `WITH` 为中间结果命名，让分步计算更可读。下面先算有效订单每张的商品额，再按顾客汇总：

```sql
WITH order_totals AS (
  SELECT oi.order_id,
         SUM(oi.quantity * oi.unit_price) AS merchandise_amount
  FROM order_items AS oi
  GROUP BY oi.order_id
)
SELECT c.display_name,
       COUNT(o.order_id) AS order_count,
       SUM(ot.merchandise_amount + o.shipping_fee) AS paid_amount
FROM customers AS c
JOIN orders AS o ON o.customer_id = c.customer_id
JOIN order_totals AS ot ON ot.order_id = o.order_id
WHERE o.status IN ('PAID', 'SHIPPED')
GROUP BY c.customer_id, c.display_name
ORDER BY paid_amount DESC;
```

CTE 是查询内的命名结果，不等于永久表；MySQL 优化器可能合并或物化它，不能仅凭语法假设性能。递归 CTE 适合层级数据，例如分类树。它必须有锚点部分和递归部分，并以 `WITH RECURSIVE` 开始：

```sql
WITH RECURSIVE category_path AS (
  SELECT category_id, parent_id, name, 0 AS depth
  FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.category_id, c.parent_id, c.name, p.depth + 1
  FROM categories AS c
  JOIN category_path AS p ON c.parent_id = p.category_id
)
SELECT * FROM category_path ORDER BY depth, category_id;
```

生产环境还要防止循环引用，并了解 MySQL 的递归深度限制；递归不是替代数据质量约束的魔法。

## 小结

- 连接前先定义结果粒度；多行有时正是正确结果，不能靠 `DISTINCT` 掩盖。
- 外连接的右表筛选通常属于 `ON`，否则会丢掉本应保留的行。
- 存在性优先考虑 `EXISTS`，可空集合的反查优先 `NOT EXISTS`。
- CTE 改善分步表达，集合运算和产品兼容性则必须按目标 MySQL 版本确认。

查询会持续演进为视图、存储程序和权限边界。下一章 [SQL 高级对象与安全](07-sql-advanced-objects-and-security.md) 将讨论这些对象应如何谨慎使用。
