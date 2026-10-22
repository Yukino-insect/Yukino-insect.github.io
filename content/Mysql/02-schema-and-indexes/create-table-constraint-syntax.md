+++
date = '2026-10-22T19:50:00+08:00'
draft = false
title = 'CREATE TABLE 的语法层级：列级约束、表级约束与主外键'
+++
读 `CREATE TABLE` 时，最容易产生的误会是把逗号前后的内容都当成“字段”。其实表定义的括号内混合了两种不同层级的声明：**列定义**（column definition）和**表约束**（table constraint）。前者描述一列的类型、是否允许空值和默认值；后者描述一列或多列之间必须同时成立的规则。

下面以订单明细表为例，系统说明这些位置能写什么、相同约束写在不同位置有什么差别，以及哪些写法在 MySQL 8 中更清晰、更稳妥。

```sql
CREATE TABLE order_item (
    order_id BIGINT NOT NULL,
    line_no INT NOT NULL,
    book_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, line_no),
    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id) REFERENCES book_order(order_id),
    CONSTRAINT fk_item_book
        FOREIGN KEY (book_id) REFERENCES book(book_id)
);
```

示例采用 MySQL 8 和 InnoDB 作为具体参照。`PRIMARY KEY`、`FOREIGN KEY`、`CHECK` 等概念来自标准 SQL，但各数据库对类型、列级外键简写、约束名和 `ALTER TABLE` 的细节并不完全相同。建表语句不是跨产品的咒语；迁移数据库时必须核对目标方言。

## 先看整体语法骨架

可以先忽略具体字段名，将常见形状理解为下面的伪语法：

```text
CREATE TABLE 表名 (
    列名 数据类型 [列级属性或约束]...,
    列名 数据类型 [列级属性或约束]...,
    [CONSTRAINT 约束名] 表级约束,
    [CONSTRAINT 约束名] 表级约束
) [表选项];
```

更形式化一点：

```text
表元素 ::= 列定义 | 表约束

列定义 ::= 列名 数据类型 [列级属性或约束]...

表约束 ::= [CONSTRAINT 约束名] PRIMARY KEY (列列表)
          | [CONSTRAINT 约束名] UNIQUE (列列表)
          | [CONSTRAINT 约束名] FOREIGN KEY (列列表)
                REFERENCES 父表 (父列列表) [引用动作]
          | [CONSTRAINT 约束名] CHECK (条件)
```

方括号表示可选，省略号表示可重复；它们只是解释语法的记号，**不是**你要原样输入 SQL 的字符。

以 `order_item` 为例，前五项都是列定义：它们以列名开头，例如 `order_id BIGINT NOT NULL`。而从 `PRIMARY KEY (order_id, line_no)` 开始，后面的三项不创建列；它们是在给已定义的列组合补充规则。

```text
order_id BIGINT NOT NULL
└─────┬──── └─┬─── └───┬───
      列名    类型       列级非空规则

PRIMARY KEY (order_id, line_no)
└───────┬────────────────────────┘
      表级规则：引用两列的组合
```

## 列定义里通常能写什么

一列首先必须有**名称**和**数据类型**，其后才能跟该列自己的属性或约束。常见形式如下：

```sql
quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0)
```

它从左到右表达四件事：

1. `quantity` 是列名；
2. `INT` 是整数类型；
3. `NOT NULL` 表示每一行都必须有数量；
4. `DEFAULT 1` 表示插入时省略该列可取 1；
5. `CHECK (quantity > 0)` 表示实际值必须为正数。

常用项目的职责和位置如下。

| 写法 | 典型位置 | 保护或描述什么 | 备注 |
| ---- | -------- | -------------- | ---- |
| `NOT NULL` / `NULL` | 列级 | 该列是否允许未知值 | `NOT NULL` 不是表级约束 |
| `DEFAULT ...` | 列级 | 插入时遗漏该列的取值 | 显式插入 `NULL` 不等于使用默认值 |
| `CHECK (...)` | 列级或表级 | 一条记录必须满足的条件 | 单列范围常写列级；跨列规则写表级 |
| `UNIQUE` | 列级或表级 | 值或列组合不重复 | 多列唯一只能写表级 |
| `PRIMARY KEY` | 列级或表级 | 行的唯一、非空标识 | 复合主键只能写表级 |
| `AUTO_INCREMENT` | MySQL 列属性 | 自动生成递增值 | 它不是标准 SQL 的完整通用写法 |
| `COMMENT`、字符集、可见性等 | MySQL 列属性 | 元数据或产品特性 | 它们通常不是完整性约束 |

`DEFAULT` 与 `NOT NULL` 常被混为一谈。它们独立工作：`NOT NULL` 禁止存储空值；`DEFAULT` 只在 `INSERT` 没有提供该列时补值。下面两条语句的意义不同：

```sql
INSERT INTO order_item (order_id, line_no, book_id, unit_price)
VALUES (1, 1, 10, 88.00); -- quantity 可使用 DEFAULT 1

INSERT INTO order_item (order_id, line_no, book_id, quantity, unit_price)
VALUES (1, 2, 10, NULL, 88.00); -- quantity 为 NOT NULL 时应报错
```

默认值不是数据校验的替身。若“数量必须大于零”，就应同时有正确的类型、`NOT NULL` 和 `CHECK`（或相应业务规则），而不是期待缺失输入会神奇地变得正确。

## 为什么 `PRIMARY KEY (order_id, line_no)` 必须写在字段之后

该定义的主键是两列的**组合**：

```sql
PRIMARY KEY (order_id, line_no)
```

它的意思不是“`order_id` 单独唯一，同时 `line_no` 单独唯一”，而是：在同一个订单内，行号不能重复。以下数据合法：

| `order_id` | `line_no` |
| ---------- | --------- |
| 1001       | 1         |
| 1001       | 2         |
| 1002       | 1         |

相同的 `(1001, 1)` 再出现一次则非法。

因为这条规则需要同时看两列，所以必须写成表级约束。一个表只能有一个主键，但该主键可由一列或多列组成；主键列不能为 `NULL`。因此原 DDL 中 `order_id BIGINT NOT NULL` 与 `line_no INT NOT NULL` 在主键最终建立后，从约束效果上看有些重复。保留 `NOT NULL` 也并非错误，它能在读到列定义时提前说明字段意图；只是不能误以为它们产生了第二层独立的主键规则。

若主键只有一列，列级和表级写法在语义上通常等价：

```sql
-- 列级：id 本身就是主键
CREATE TABLE book_a (
    book_id BIGINT PRIMARY KEY,
    title VARCHAR(200) NOT NULL
);

-- 表级：同样是一列主键
CREATE TABLE book_b (
    book_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    PRIMARY KEY (book_id)
);
```

对于单列主键，选哪一种主要是风格问题；对于复合主键，第二种是唯一自然的写法。团队项目中常将所有键统一写成表级，以便名字、列顺序和引用动作集中显示，阅读更稳定。

## `UNIQUE` 与 `CHECK`：相同规则的两种位置

### 单列 `UNIQUE`

图书 ISBN 应存在且不可重复，可以写成列级：

```sql
CREATE TABLE book (
    book_id BIGINT PRIMARY KEY,
    isbn CHAR(13) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL
);
```

也可写成表级，并给出稳定的约束名：

```sql
CREATE TABLE book (
    book_id BIGINT PRIMARY KEY,
    isbn CHAR(13) NOT NULL,
    title VARCHAR(200) NOT NULL,
    CONSTRAINT uk_book_isbn UNIQUE (isbn)
);
```

两种写法都表达“非空 ISBN 不重复”。不过在 MySQL 中，`UNIQUE` 通常通过唯一索引实施；未加 `NOT NULL` 的唯一列可出现多个 `NULL`，因为 `NULL` 表示未知而非一个普通相等值。因此业务要求“必须填写且唯一”时，`NOT NULL` 与 `UNIQUE` 缺一不可。

多列唯一只能写表级：

```sql
CONSTRAINT uk_item_order_book UNIQUE (order_id, book_id)
```

它表示同一订单中同一本书最多一条明细；它并不禁止不同订单购买同一本书。

### `CHECK` 的列级与表级

只检查一个列时，列级写法很自然：

```sql
quantity INT NOT NULL CHECK (quantity > 0),
unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0)
```

这些约束检查的是每行自己的 `quantity` 和 `unit_price`。为了便于错误定位和后续维护，实际项目常为它们命名：

```sql
quantity INT NOT NULL
    CONSTRAINT ck_item_quantity CHECK (quantity > 0),
unit_price DECIMAL(10, 2) NOT NULL
    CONSTRAINT ck_item_unit_price CHECK (unit_price >= 0),
```

当表达式同时依赖多列时，应写表级。比如订单的支付时间必须与支付状态一致：

```sql
CREATE TABLE book_order (
    order_id BIGINT NOT NULL,
    status VARCHAR(16) NOT NULL,
    paid_at DATETIME NULL,
    PRIMARY KEY (order_id),
    CONSTRAINT ck_order_paid_time
        CHECK (
            (status = 'PAID' AND paid_at IS NOT NULL)
            OR (status <> 'PAID' AND paid_at IS NULL)
        )
);
```

把它强行挂在 `status` 或 `paid_at` 后面并不会让规则更“属于”某列；它本质上是两列关系，所以表级更诚实。`CHECK` 只能可靠表达当前行可判断的条件，不能用来验证“库存总量不为负”“订单至少一条明细”这类跨行或跨表不变量；后者需要事务中的条件更新、触发器或业务流程控制。

MySQL 8 会强制执行 `CHECK`；维护旧版 MySQL 时则必须先确认版本，因为早期版本曾接受该语法却不实施检查。不要仅因建表成功，就假定规则真的被执行。

## 外键：单列也常写成表级

原 DDL 中有两条外键：

```sql
CONSTRAINT fk_item_order
    FOREIGN KEY (order_id) REFERENCES book_order(order_id),
CONSTRAINT fk_item_book
    FOREIGN KEY (book_id) REFERENCES book(book_id)
```

它们分别保证：每条明细归属的订单必须存在，每条明细引用的图书必须存在。`CONSTRAINT fk_item_order` 中的 `fk_item_order` 是这条规则的名字，不是字段名，也不是索引名的随意别称；它会在报错、迁移和删除约束时帮助定位对象。

有些数据库允许单列外键写成接近列级的简写，例如：

```sql
book_id BIGINT REFERENCES book(book_id)
```

但不同产品的支持细节和引用动作写法存在差异。在 MySQL/InnoDB 项目中，更建议使用明确的表级 `FOREIGN KEY (...) REFERENCES ...` 形式，尤其当你需要约束名、复合外键或删除/更新动作时：

```sql
CONSTRAINT fk_item_order
    FOREIGN KEY (order_id)
    REFERENCES book_order(order_id)
    ON UPDATE RESTRICT
    ON DELETE CASCADE
```

`ON DELETE CASCADE` 的意思是删除订单时一并删除它的订单项；是否正确完全取决于生命周期。对“订单—订单项”这类离开父对象没有独立意义的明细通常合理；对“图书—历史订单项”通常不应级联删除，否则历史记录会消失。数据库只能严格执行你写下的规则，无法替你判断业务语义。

复合外键同样只能用表级列表表达。例如子表的 `(tenant_id, order_id)` 必须引用父表相同的键组合：

```sql
CONSTRAINT fk_item_tenant_order
    FOREIGN KEY (tenant_id, order_id)
    REFERENCES book_order(tenant_id, order_id)
```

外键两侧列的类型和符号属性应兼容，父表被引用列必须是有索引的键。InnoDB 会为子表外键列需要的索引提供或创建支持，但查询所需的复合索引仍应基于真实访问模式设计，不能把外键当作“性能已经自动解决”的承诺。

## `CONSTRAINT 名称` 放在哪里，名称又有什么用

`CONSTRAINT <name>` 是给规则命名的前缀，最常见于表级约束：

```sql
CONSTRAINT pk_order_item PRIMARY KEY (order_id, line_no),
CONSTRAINT ck_item_quantity CHECK (quantity > 0),
CONSTRAINT fk_item_order FOREIGN KEY (order_id)
    REFERENCES book_order(order_id)
```

对支持该写法的约束种类，列级 `CHECK` 也可命名，如前文的 `CONSTRAINT ck_item_quantity CHECK (...)`。而 `NOT NULL`、`DEFAULT` 主要是列属性，实际项目通常不为它们额外命名；精确可用的命名位置仍应以目标数据库文档为准。

有意识地命名主键、唯一键、检查约束和外键有三个好处：

- 报错信息更可读，例如能直接看到 `ck_item_quantity`；
- 迁移时可以准确 `DROP CONSTRAINT` 或修改指定规则；
- 多环境、自动迁移工具和团队协作中不必依赖数据库生成的随机或截断名称。

常见命名约定可使用 `pk_表名`、`uk_表名_业务列`、`ck_表名_规则`、`fk_子表_父表`。名称本身不改变约束语义，却能决定日后排错时你是否还要考古。这个差别并不诗意，但足够实际。

## 将示例整理成一份更完整的 MySQL 8 DDL

下面把原示例补足常见的索引和引用动作。它不是唯一正确设计，而是展示各类元素应在什么位置出现：

```sql
CREATE TABLE order_item (
    order_id BIGINT NOT NULL,
    line_no INT NOT NULL,
    book_id BIGINT NOT NULL,
    quantity INT NOT NULL
        CONSTRAINT ck_item_quantity CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL
        CONSTRAINT ck_item_unit_price CHECK (unit_price >= 0),

    CONSTRAINT pk_order_item PRIMARY KEY (order_id, line_no),
    CONSTRAINT uk_item_order_book UNIQUE (order_id, book_id),
    KEY idx_item_book (book_id),

    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id)
        REFERENCES book_order(order_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT fk_item_book
        FOREIGN KEY (book_id)
        REFERENCES book(book_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
) ENGINE = InnoDB;
```

这里的 `KEY idx_item_book (book_id)` 是 MySQL 的普通索引声明，用于按图书查询订单项；它**不是**完整性约束，因为它允许重复、空值和任何业务上无效的值。不要把所有出现在 `CREATE TABLE` 中的关键字都统称为约束：列、约束、索引、存储引擎和表选项分别承担不同责任。

## 列级还是表级：一张决策表

| 需求 | 推荐位置 | 原因 |
| ---- | -------- | ---- |
| 某列必须填写 | 列级 `NOT NULL` | 只涉及一列 |
| 某列缺省值 | 列级 `DEFAULT` | 只涉及一列 |
| 单列正数、范围、枚举检查 | 列级或命名 `CHECK` | 列旁边可读性好 |
| 两列日期、状态之间的关系 | 表级 `CHECK` | 规则依赖多列 |
| 单列业务唯一性 | 列级或表级 `UNIQUE` | 二者语义相同，团队统一风格即可 |
| 多列组合唯一性 | 表级 `UNIQUE (a, b)` | 必须引用列组合 |
| 单列主键 | 列级或表级 `PRIMARY KEY` | 二者语义相同 |
| 复合主键 | 表级 `PRIMARY KEY (a, b)` | 必须引用列组合 |
| 单列/复合外键及引用动作 | 表级 `FOREIGN KEY` | 名称、动作和跨产品可读性更好 |

一个简单原则足够应对大多数建表语句：**规则只描述一列时可写在列后；规则要同时谈到多列、另一张表或需要明确命名与动作时，写成表级。**

## 小结

- `CREATE TABLE (...)` 内既有列定义，也有表约束；后者不会创建新字段。
- 列级常写类型、`NOT NULL`、`DEFAULT`，以及单列 `CHECK`、单列键；表级适合复合主键、复合唯一键、外键和跨列检查。
- `PRIMARY KEY (order_id, line_no)` 的唯一性针对二元组合，且主键天然非空；它不意味着每一列各自唯一。
- `CONSTRAINT 名称` 为规则提供可维护的身份。外键的 `ON DELETE` / `ON UPDATE` 是业务生命周期决策，不是可随手复制的装饰。
- `KEY`/`INDEX` 主要服务查询性能，与主键、唯一键、外键、检查约束守护数据正确性并非同一职责。

如果对嵌套查询中“外层、内层究竟如何关联”仍感到模糊，可结合 [相关子查询与双重 NOT EXISTS：从逻辑执行到“全部满足”查询](../01-sql-and-query/nested-subqueries-not-exists-execution-order.md) 阅读：查询的逻辑层次与 DDL 的声明层次，都是把复杂 SQL 拆成可验证规则的基本方法。
