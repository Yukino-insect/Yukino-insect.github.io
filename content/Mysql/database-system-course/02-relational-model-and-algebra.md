+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = '关系模型与关系代数：理解 SQL 查询的计算骨架'
+++

关系模型之所以经久不衰，不是因为它把数据排成了网格，而是因为它用有限而严谨的结构描述事实，并用一组可组合的运算表达查询。SQL 的写法看似繁多，背后常可还原为“先筛选哪些行、再保留哪些列、再按什么条件关联”。一旦掌握这个过程，面对多表查询时便不必靠猜。

本篇继续使用在线书店。为突出原理，下表故意简化字段；真实 schema 会在下一篇补上约束和中间表。关系代数使用集合语义，而 MySQL 的普通 SQL 往往保留重复行（bag/multiset 语义），这是理解二者时必须记住的一处差异。

## 关系的基本术语

在关系模型中，**关系**（relation）近似于一张表，但它首先是一个有名字、按属性组织的元组集合。关系中的一行叫**元组**（tuple），对应日常所说的记录；一列叫**属性**（attribute）；属性允许取值的集合叫**域**（domain），如“非负整数”“合法日期”“订单状态枚举”。关系模式可写成 `Book(book_id, title, price, stock)`，它描述结构；某一时刻表中实际行构成关系实例。

`book_id`、`title` 等并不是“第 1 列、第 2 列”，而是有名字的属性。因此，概念上的关系没有行序和列序；没有 `ORDER BY` 的 SQL 查询也不承诺返回顺序。把当前结果看起来的第一行当作“最新图书”，是一个危险的偶然现象。

| Book 关系 | | | |
| --------- | - | ---------------- | ----- |
| `book_id` | `title` | `price` | `stock` |
| 101 | 数据库系统概念 | 128.00 | 8 |
| 102 | SQL 实战 | 69.00 | 0 |
| 103 | 分布式系统导论 | 88.00 | 15 |

| OrderItem 关系 | | | |
| -------------- | - | --------- | ---------- |
| `order_id` | `book_id` | `quantity` | `unit_price` |
| 9001 | 101 | 2 | 120.00 |
| 9001 | 103 | 1 | 88.00 |
| 9002 | 101 | 1 | 128.00 |

### 域、空值与键

域不只是数据库字段类型。`price DECIMAL(10,2)` 说明数值精度，却不能单独说明价格是否允许为负；`status VARCHAR(20)` 允许任意字符串，却未表达它只能是 `PENDING`、`PAID` 或 `CANCELLED`。严谨的模式应使用 `NOT NULL`、`CHECK`、外键和适当的枚举/参照表，把业务规则尽量交给数据库验证。

能唯一标识一个元组的一组属性称为**超键**（superkey）。若从中去掉任何属性便不能唯一标识，则是**候选键**（candidate key）；从候选键中选作主要标识的一组是**主键**（primary key）。例如 ISBN 可以是图书的候选键，内部 `book_id` 也可以是候选键；若选 `book_id` 作为主键，ISBN 仍应由 `UNIQUE` 约束保护。订单项通常由 `(order_id, book_id)` 联合唯一标识，或使用独立 `order_item_id` 并额外限制同一订单不重复购买同一本书。

空值 `NULL` 表示未知、尚未提供或不适用，绝不是空字符串和数字 0。SQL 的空值还会带来三值逻辑：`NULL = NULL` 的结果是未知而非真，所以必须用 `IS NULL` 判断。不要用 `0` 或 `'未知'` 冒充缺失值，那会混淆真正的业务值与未提供值。

## 选择与投影：先决定行，再决定列

关系代数的**选择**（selection）用 σ 表示，按照谓词过滤元组；它对应 SQL 的 `WHERE`。要找库存大于零的图书：

```text
σ stock > 0 (Book)

book_id  title             price   stock
101      数据库系统概念     128.00  8
103      分布式系统导论     88.00   15
```

SQL 直觉如下。虽然 `SELECT *` 为便于展示可用，生产查询通常应只取需要的列，减少网络和后续处理成本。

```sql
SELECT book_id, title, price, stock
FROM book
WHERE stock > 0;
```

**投影**（projection）用 π 表示，保留指定属性。例如 π `title, price(Book)` 只保留书名和定价。集合关系中的投影会去重；SQL 若需要同样效果必须显式写 `DISTINCT`。这是初学者常误解的点：SQL 的 `SELECT title FROM book` 不保证消除同名图书。

```sql
-- 关系代数的投影语义：只返回不同的价格
SELECT DISTINCT price
FROM book;
```

选择与投影可组合：`π title(σ stock > 0(Book))` 的含义是“先挑有库存的书，再显示书名”。SQL 的书写顺序是 `SELECT` 在前、`WHERE` 在后，但思考时仍应把 `WHERE` 当作确定结果行范围的重要步骤。优化器也可能改变实际执行次序，只要结果符合声明的语义。

## 笛卡尔积与连接：多表查询的关键

两个关系的**笛卡尔积** `R × S` 将 R 的每一行与 S 的每一行配对。如果 `Book` 有 3 行、`OrderItem` 有 3 行，乘积有 9 行。它很少是业务真正要的结果，却是理解连接的中间概念：连接等于先组合，再依据关联条件过滤不匹配的组合。

```text
Book × OrderItem（仅展示部分）
Book.book_id  Book.title          Item.order_id  Item.book_id
101           数据库系统概念      9001           101   ← 匹配
101           数据库系统概念      9001           103   ← 不匹配
101           数据库系统概念      9002           101   ← 匹配
```

**θ 连接**（theta join）可写为 `R ⋈条件 S`，即 `σ 条件(R × S)`。最常见的是等值连接。如下查询把订单项中的图书编号与图书表匹配，以取得人能读懂的书名。给列加表别名不仅简洁，也避免两个表同名字段造成歧义。

```sql
SELECT oi.order_id, b.title, oi.quantity, oi.unit_price
FROM order_item AS oi
JOIN book AS b
  ON b.book_id = oi.book_id
WHERE oi.order_id = 9001;
```

结果为两行：订单 9001 的《数据库系统概念》数量为 2、成交价为 120；《分布式系统导论》数量为 1、成交价为 88。若漏写 `ON b.book_id = oi.book_id`，多数数据库会得到笛卡尔积，行数突然膨胀并产生错误金额。**连接条件不是装饰，它表达了两个事实之间的对应规则。**

内连接只留下匹配行。若还要列出从未售出的图书，应使用左外连接：保留左表 `book` 的所有行，右表无匹配时用 `NULL` 补齐。注意条件放在 `ON` 与放在 `WHERE` 的效果可能不同；若在 `WHERE` 中写 `oi.order_id = 9001`，无订单项的图书因 `NULL` 不满足条件会被过滤，左连接会退化成内连接。

```sql
SELECT b.title, oi.order_id
FROM book AS b
LEFT JOIN order_item AS oi
  ON oi.book_id = b.book_id
 AND oi.order_id = 9001;
```

## 并、差与集合兼容

关系代数还提供并集 `R ∪ S`、交集 `R ∩ S` 和差集 `R − S`。参与集合运算的关系应**并兼容**：属性数量相同，对应域可比较、语义也应一致。不能把“图书价格”与“客户电话”直接并起来，即使它们碰巧都是字符串。

例如，`featured_book` 和 `new_book` 都只含 `book_id` 时，`featured_book ∪ new_book` 表示出现在任一清单的图书。SQL 的 `UNION` 默认去重；想保留来自两份清单的重复出现次数才用 `UNION ALL`。差集可找出“有库存但尚未售出”的图书，不过 SQL 常用 `NOT EXISTS` 表达，因为它对空值更直观。

```sql
-- 有库存且从未出现在订单项中的图书
SELECT b.book_id, b.title
FROM book AS b
WHERE b.stock > 0
  AND NOT EXISTS (
    SELECT 1
    FROM order_item AS oi
    WHERE oi.book_id = b.book_id
  );
```

不要轻易改用 `NOT IN (SELECT oi.book_id ...)`。若子查询意外产生 `NULL`，三值逻辑可能让 `NOT IN` 没有返回任何行。`NOT EXISTS` 直接问“是否不存在一条匹配记录”，语义通常更贴合业务。

## 从关系代数到 SQL 的阅读框架

面对一条 SQL，可按下面顺序还原它的逻辑，而不是死记关键字位置：

```text
FROM / JOIN：候选行来自哪些关系，如何匹配？
WHERE：哪些候选行被选择保留？
GROUP BY / HAVING：如何把行分组与过滤组？
SELECT：最终投影哪些值或聚合结果？
ORDER BY / LIMIT：如何呈现结果，不改变关系事实本身？
```

例如“计算订单 9001 总金额”先选择该订单的项，再以 `quantity * unit_price` 派生金额并求和。它使用的是历史成交价，而非 `book.price`，正是为了保证关系中保存的业务事实不被当前图书定价污染。

```sql
SELECT oi.order_id,
       SUM(oi.quantity * oi.unit_price) AS total_amount
FROM order_item AS oi
WHERE oi.order_id = 9001
GROUP BY oi.order_id;
```

## 本篇小结

- 关系由属性组织元组；关系没有天然行序，域与约束共同定义合法取值。
- 主键标识元组，候选键与唯一约束保护其他业务上的唯一性；`NULL` 需按三值逻辑谨慎处理。
- 选择对应筛行，投影对应取列，连接以明确条件将相关事实配对。
- 笛卡尔积解释了漏掉连接条件的危险；集合运算则要求参与关系语义兼容。

下一篇[ER 建模到关系模式](03-er-modeling-and-schema-design.md)将从书店需求出发，决定哪些概念应该成为实体、联系和最终的表。
