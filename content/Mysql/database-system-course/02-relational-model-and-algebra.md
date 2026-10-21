+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = '关系模型与关系代数：理解 SQL 查询的计算骨架'
math = true
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

## 关系操作全景：基本运算与派生运算

关系代数把查询看成“关系输入、关系输出”的组合。每一步输入和输出都是关系，因此一个操作的结果还能继续作为下一个操作的输入；这正是复杂查询仍可被拆解、验证和优化的原因。教材中常将选择、投影、并、差、笛卡尔积和重命名视为一组基础操作，连接、交、除则可以由它们组合而来。

| 类别 | 运算与记号 | 作用 | 常见 SQL 对应 |
| ---- | ---------- | ---- | ------------- |
| 单关系 | 选择 `σ` | 按谓词保留元组 | `WHERE` |
| 单关系 | 投影 `π` | 保留所需属性 | `SELECT DISTINCT` |
| 单关系 | 重命名 `ρ` | 重命名关系或属性 | `AS` 别名 |
| 二元集合 | 并 `∪`、差 `−` | 合并兼容关系，或排除已有事实 | `UNION`、`EXCEPT` / `NOT EXISTS` |
| 二元组合 | 笛卡尔积 `×` | 每一行与另一关系的每一行配对 | `CROSS JOIN` |
| 派生组合 | 交 `∩`、连接 `⋈`、除 `÷` | 找共同元组、匹配事实、满足“全部条件”的对象 | `INTERSECT`、`JOIN`、双重 `NOT EXISTS` |

关系代数默认采用集合语义：同一元组不会重复出现。SQL 默认通常采用多重集（bag）语义，因此要注意 `UNION ALL`、重复连接行与 `DISTINCT` 的差异。两者并不矛盾；SQL 是面向实际系统的语言，需要保留重复来表达计数和明细，但把它与关系代数对照时必须先问清楚是否去重。

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

### 差集运算的并兼容要求：以教师关系为说明

关系代数不是把符号随意排在一起；它有递归的表达式语法。先把 `R`、`S` 看成关系名，`E` 看成任意一个已经合法的关系代数表达式，常见骨架可以写为：

```text
E ::= R
   |  σ_条件(E)
   |  Π_属性列表(E)
   |  ρ_新名称(E)
   |  (E ∪ E) | (E − E) | (E × E) | (E ⋈条件 E)
```

这段写法读作“一个合法表达式 `E`，要么是一个关系名；要么是在一个合法表达式外套一个单目运算；要么是把两个合法表达式用二元运算连接起来”。所有这些运算的结果仍然是关系，所以才可以继续嵌套。例如选择的结果能再投影，投影的结果又能作为差集的左操作数。

符号的语法位置也有固定含义：

- `instructor` 是**操作数**，即输入关系名；可以理解为教师表。
- `Π`、`σ` 写在操作数前，是**前缀单目运算符**；圆括号中必须放一个关系或另一个合法表达式。
- 下标是运算符的参数：`Π` 的下标是属性列表，`σ` 的下标是布尔条件。它们不是结果列名的随意注释。
- `−` 写在两个完整关系表达式中间，是**中缀二元运算符**；左右两边都必须先各自产生一个关系。
- 括号决定嵌套边界。`Π_{ID,name}(instructor)` 的意思是“把投影应用到 `instructor`”；并不是“把 `ID,name` 当作一张关系”。

从“表达式树”看，下面的式子有三个中间结果：

```text
E0 = instructor
E1 = Π_ID,name(E0)                    -- 只留下编号、姓名
E2 = σ_dept_name='Physics'(E0)        -- 只留下 Physics 系教师
E3 = E1 − E2                          -- 对两个结果做差
```

差集的两个操作数必须具有相同的关系模式。下面以常见的 `instructor` 教师关系说明这一要求：

$$
\Pi_{ID,\;name}(instructor) - \sigma_{dept\_name = \text{Physics}}(instructor)
$$

这个表达式的业务意图是“找出不属于 Physics 系的教师的 `ID` 与 `name`”，但严格来说**不能直接相减**。左侧投影后的模式是 `(ID, name)`，右侧选择后的模式却仍是完整的 `instructor(ID, name, dept_name, salary, ...)`。列数和属性都不同，因而两个关系不并兼容，这个差集表达式不合法。

要使差集合法，必须先把右侧也投影到同一模式：

$$
\Pi_{ID,\;name}(instructor)
-
\Pi_{ID,\;name}
\bigl(
  \sigma_{dept\_name = \text{Physics}}(instructor)
\bigr)
$$

计算顺序是：先取所有教师的 `ID`、`name`；再取 Physics 系教师的 `ID`、`name`；最后做差，留下不在 Physics 系的教师。它也可以读成：

```text
所有教师的姓名与编号
减去
Physics 系教师的姓名与编号
```

若数据库支持集合差集，SQL 可以直观地写为：

```sql
SELECT instructor_id, name
FROM instructor

EXCEPT

SELECT instructor_id, name
FROM instructor
WHERE dept_name = 'Physics';
```

许多 MySQL 项目会更常用 `NOT EXISTS` 来表达同一含义，并避免不同版本的集合运算支持差异：

```sql
SELECT i.instructor_id, i.name
FROM instructor AS i
WHERE NOT EXISTS (
    SELECT 1
    FROM instructor AS physics_instructor
    WHERE physics_instructor.instructor_id = i.instructor_id
      AND physics_instructor.dept_name = 'Physics'
);
```

这里假定 `instructor_id` 是教师主键。一名教师只有一条教师记录时，较简单的 `WHERE dept_name <> 'Physics'` 也能工作；但若 `dept_name` 可能为 `NULL`，它会因 SQL 三值逻辑把 `NULL` 一并过滤。关系代数的经典模型不含 `NULL`，实际 SQL 写法却必须明确“部门未知的教师是否也应保留”这一业务规则。

### 重命名与交：避免歧义，找出共同事实

**重命名**（rename）用 `ρ` 表示，可以修改关系名、属性名或两者。它在自连接中不可省略：若要找出购买过同一本书的两位不同客户，必须把“订单项”视为两个不同角色的关系，概念上可写成 `ρA(OrderItem)` 与 `ρB(OrderItem)`。SQL 中的 `AS a`、`AS b` 就承担这个职责。

```sql
SELECT DISTINCT a.order_id AS first_order_id,
       b.order_id AS second_order_id,
       a.book_id
FROM order_item AS a
JOIN order_item AS b
  ON a.book_id = b.book_id
 AND a.order_id < b.order_id;
```

这里的 `a`、`b` 不是给表起一个好看的短名字，而是在同一个关系的两次出现之间建立可区分的身份。没有重命名，`order_item.book_id = order_item.book_id` 只是在比较同一列，无法表达两个角色的匹配。

**交集** `R ∩ S` 返回同时属于 R 和 S 的元组，也要求两侧并兼容。它可由差集推导：`R ∩ S = R − (R − S)`。例如找出既在“新书推荐”又在“编辑精选”清单中的 `book_id`。较新的 MySQL 支持 `INTERSECT`，但为了兼容更多版本，也可以用 `EXISTS`：

```sql
SELECT n.book_id
FROM new_book AS n
WHERE EXISTS (
    SELECT 1
    FROM featured_book AS f
    WHERE f.book_id = n.book_id
);
```

`EXISTS` 表达的是集合意义的“存在一个相同键”，不会因为右表有两条相同记录而把左表行放大；若业务允许清单重复，则应先决定重复本身是否有意义，再选择是否 `DISTINCT`。

### 除法：把“全部满足”翻译为查询

**除法**是关系代数中很有辨识度、却经常被遗漏的派生运算。若 `Purchase(customer_id, book_id)` 表示客户购买过某书，`RequiredBook(book_id)` 表示一组指定图书，那么：

```text
Purchase ÷ RequiredBook
```

返回“买过 `RequiredBook` 中**所有**图书的客户”。它不是“买过其中任意一本”，所以一个普通 `JOIN` 不够。用基本操作表示时，其逻辑是：先列出所有客户与必读书的应有组合，减去实际购买过的组合，再从全部客户中排除仍有缺项的人。

```text
π customer_id(Purchase)
− π customer_id(
    (π customer_id(Purchase) × RequiredBook)
    − Purchase
  )
```

SQL 常使用双重 `NOT EXISTS`，直译为“并不存在某一本必读书，是该客户没有买过的”：

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

若 `required_book` 为空，经典关系代数的结果会包含所有出现在 `Purchase` 中的客户；产品需求可能反而希望返回空结果。因此“全部”查询还应明确空集合时的业务语义，而不能只复制模板。除法的价值不在于背出符号，而在于识别“对每一个条件都满足”的量词结构；权限齐全、完成所有课程、覆盖全部地区等问题都属于这一类。

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
- 选择、投影、重命名、并、差和笛卡尔积构成可组合的基本运算；连接、交和除法是常用派生运算。
- 笛卡尔积解释了漏掉连接条件的危险；集合运算则要求参与关系语义兼容。除法对应“满足全部条件”，SQL 中常写成双重 `NOT EXISTS`。

下一篇[ER 建模到关系模式](03-er-modeling-and-schema-design.md)将从书店需求出发，决定哪些概念应该成为实体、联系和最终的表。
