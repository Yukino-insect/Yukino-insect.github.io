+++
date = '2026-10-19T20:00:00+08:00'
draft = false
title = 'SQL 定义数据与完整性约束：把业务规则写进数据库'
+++
前文已经从 ER 模型和关系模式讨论了实体、键与联系；现在要把那些设计变成数据库真正能够执行的规则。数据定义语言（Data Definition Language，DDL）负责创建、修改和删除数据库对象。若只靠应用程序“记得检查”，任何绕过应用的脚本、后台任务或另一套服务都可能写入脏数据。把稳定的规则放入模式，才有一条可信的底线。

本章实践方言是 **MySQL 8**，存储引擎使用 InnoDB。主键、外键、检查约束等概念来自标准 SQL，但具体类型名称、`ALTER TABLE` 能力和 DDL 是否可回滚会随产品不同而变化。所谓“通用 SQL”在细节处往往并不通用，最好不要把一份语法记忆当作定律。后续查询会使用本章建立的在线书店模型；读完可继续进入 [单表查询、聚合与分组](05-sql-query-and-aggregation.md)。

## 类型应表达业务语义

列类型不是为了凑出一张能建成功的表，而是声明值域。在线书店中，技术主键可用无符号大整数；ISBN 和订单号看起来由数字组成，却是标识符，必须保留前导零且不参与加减；价格则必须精确到分。

| 业务值 | MySQL 8 常用类型 | 选择理由 |
| --- | --- | --- |
| 技术标识 | `BIGINT UNSIGNED` | 容量大，适合 `AUTO_INCREMENT` |
| ISBN、订单号 | `CHAR` / `VARCHAR` | 是字符标识而非算术数值 |
| 名称、状态 | `VARCHAR(n)` | 长度上限清晰，便于校验 |
| 书籍简介 | `TEXT` | 允许较长文本，但不应作随意索引键 |
| 金额 | `DECIMAL(10,2)` | 定点十进制，适合结算 |
| 日期与时刻 | `DATE`、`DATETIME` | 分别表达日期和本地业务时刻 |
| 真/假 | `BOOLEAN` | MySQL 中是 `TINYINT(1)` 的别名 |

不要用 `FLOAT` 或 `DOUBLE` 储存钱。二进制浮点无法准确表达大多数十进制小数，`0.1 + 0.2` 可能产生看似荒谬的尾差；`DECIMAL` 才是可预期的十进制算术。`VARCHAR(255)` 也不是全能答案：长度只限制尺寸，不能替代邮箱格式、状态枚举或业务流程校验。

## 建立一套可运行的书店模式

下面可在空的 MySQL 8 实例执行。`utf8mb4` 支持中文和 emoji，所有表都明确使用 InnoDB，从而支持事务和外键。

```sql
CREATE DATABASE IF NOT EXISTS bookstore
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE bookstore;

CREATE TABLE customers (
  customer_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(254) NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  phone VARCHAR(32) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (customer_id),
  UNIQUE KEY uk_customers_email (email)
) ENGINE = InnoDB;

CREATE TABLE books (
  book_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  isbn CHAR(13) NOT NULL,
  title VARCHAR(200) NOT NULL,
  list_price DECIMAL(10, 2) NOT NULL,
  stock_qty INT UNSIGNED NOT NULL DEFAULT 0,
  published_on DATE NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ON_SALE',
  PRIMARY KEY (book_id),
  UNIQUE KEY uk_books_isbn (isbn),
  CONSTRAINT ck_books_price CHECK (list_price >= 0),
  CONSTRAINT ck_books_stock CHECK (stock_qty >= 0),
  CONSTRAINT ck_books_status CHECK (status IN ('DRAFT', 'ON_SALE', 'OFF_SALE'))
) ENGINE = InnoDB;

CREATE TABLE orders (
  order_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_no CHAR(20) NOT NULL,
  customer_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  ordered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  shipping_fee DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
  PRIMARY KEY (order_id),
  UNIQUE KEY uk_orders_order_no (order_no),
  KEY idx_orders_customer_time (customer_id, ordered_at),
  CONSTRAINT ck_orders_status
    CHECK (status IN ('PENDING', 'PAID', 'SHIPPED', 'CANCELLED')),
  CONSTRAINT ck_orders_shipping_fee CHECK (shipping_fee >= 0),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
    REFERENCES customers (customer_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE order_items (
  order_id BIGINT UNSIGNED NOT NULL,
  line_no SMALLINT UNSIGNED NOT NULL,
  book_id BIGINT UNSIGNED NOT NULL,
  quantity INT UNSIGNED NOT NULL,
  unit_price DECIMAL(10, 2) NOT NULL,
  PRIMARY KEY (order_id, line_no),
  UNIQUE KEY uk_items_order_book (order_id, book_id),
  KEY idx_items_book (book_id),
  CONSTRAINT ck_items_quantity CHECK (quantity > 0),
  CONSTRAINT ck_items_unit_price CHECK (unit_price >= 0),
  CONSTRAINT fk_items_order FOREIGN KEY (order_id)
    REFERENCES orders (order_id)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT fk_items_book FOREIGN KEY (book_id)
    REFERENCES books (book_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;
```

`orders` 是订单头，`order_items` 是订单内的行。复合主键 `(order_id, line_no)` 表达“某订单的第几行”；`(order_id, book_id)` 的唯一键表达当前规则“不允许同一种书分为两行”。明细中的 `unit_price` 是成交时的价格快照，不能要求它等于 `books.list_price`：图书调价后，已成交订单的历史意义不应被改写。

## 约束各自在保护什么

`PRIMARY KEY` 意味着唯一且非空，一个表只能有一个主键。它可使用代理 `id`，但代理键不会取消业务键：订单号和 ISBN 仍须用 `UNIQUE` 保护。`UNIQUE` 保护其他候选键；在 MySQL 中唯一索引通常容许多个 `NULL`，因为未知值之间不相等。因此“邮箱必须存在且不重复”必须同时使用 `NOT NULL` 与 `UNIQUE`。

`NOT NULL` 防止必填事实缺失。`DEFAULT` 只在插入语句遗漏该列时提供值，显式插入 `NULL` 不会自动变成默认值。`CHECK` 适合单行可判断的范围，例如价格非负、状态只能取给定集合。MySQL 8 会执行 `CHECK`；旧版 MySQL 曾只解析而不强制它，维护遗留实例前应先查版本。

外键保证引用完整性：每个 `orders.customer_id` 都必须存在于 `customers`。父、子列的类型及无符号属性应兼容，父列应是有索引的键，InnoDB 才会真正实施。外键不是“自动优化一切查询”的按钮；查询所需的复合索引仍要依据访问模式设计。

## 删除、更新规则体现生命周期

外键的动作不是语法装饰，而是业务决策。

- `RESTRICT` 或 `NO ACTION`：存在子行便拒绝父行变更。InnoDB 中两者实践效果接近；标准 SQL 对检查时机有更细区分。
- `CASCADE`：删除订单时删除其明细，适合明细离开订单没有独立意义的组合关系。
- `SET NULL`：清空可选引用，要求子列可为 `NULL`，可用于“负责人离职后工单暂未分配”。

示例拒绝删除已有订单记录引用的图书，以保护审计历史；删除草稿订单时则可级联删除其行。实际商城更常采用状态和归档，而非物理删除已支付订单。稳定的代理主键通常也没有更新必要，选择 `ON UPDATE RESTRICT` 能避免一次错误更新扩散。

## ALTER TABLE 与可控演进

模式会演进，不代表应该在生产库随手改列：

```sql
ALTER TABLE customers
  ADD COLUMN loyalty_level VARCHAR(16) NOT NULL DEFAULT 'STANDARD',
  ADD CONSTRAINT ck_customers_loyalty
    CHECK (loyalty_level IN ('STANDARD', 'SILVER', 'GOLD'));

ALTER TABLE books
  MODIFY COLUMN title VARCHAR(300) NOT NULL;

ALTER TABLE orders
  ADD COLUMN paid_at DATETIME NULL,
  ADD KEY idx_orders_status_time (status, ordered_at);
```

某些 MySQL 8 变更可使用 `INSTANT` 或 `INPLACE` 算法，另一些会重建表或等待元数据锁，具体取决于版本和操作。增加非空列、缩短字符串、删除列之前，应先回填和验证旧数据；生产迁移应在接近真实的数据量上演练，安排兼容期和回滚方案。

## DDL 不是普通事务的一部分

InnoDB 的 `INSERT`、`UPDATE`、`DELETE` 可包在 `START TRANSACTION`、`COMMIT`、`ROLLBACK` 中。MySQL 的大量 DDL，如 `CREATE TABLE`、`ALTER TABLE`、`DROP TABLE`，会发生隐式提交，不能期待一次 `ROLLBACK` 恢复表结构；其他数据库的事务性 DDL 支持各不相同。

创建订单并扣库存则应是 DML 事务：

```sql
START TRANSACTION;
INSERT INTO orders (order_no, customer_id) VALUES ('SO202610200001', 1);
INSERT INTO order_items (order_id, line_no, book_id, quantity, unit_price)
VALUES (LAST_INSERT_ID(), 1, 10, 2, 88.00);
UPDATE books SET stock_qty = stock_qty - 2
WHERE book_id = 10 AND stock_qty >= 2;
-- 应用确认受影响行数为 1；否则执行 ROLLBACK。
COMMIT;
```

条件更新避免了“先查库存、再无条件扣减”之间的并发窗口。约束守住局部不变量，事务和后续的并发控制章节守住跨行、跨表的业务动作。

## 小结

- 类型、键、默认值和检查约束共同描述值的含义，而不是仅仅让建表成功。
- 主键不是业务唯一性的替身；外键动作必须按实体生命周期选择。
- MySQL 8 的 DDL 细节与标准及其他产品有差异，生产变更要演练并保留回退路径。

有了能够自我保护的数据结构，下一章 [单表查询、聚合与分组](05-sql-query-and-aggregation.md) 将学习如何准确地取回数据。
