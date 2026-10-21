+++
date = '2026-10-20T20:00:00+08:00'
draft = false
title = '函数依赖、关系规范化与模式分解：让重复数据有据可查'
+++

ER 图回答“有哪些实体和联系”，但还没有完全回答“字段应当放在哪一张表”。如果把客户姓名、图书标题、当前定价、订单成交价都塞进订单项，一开始写查询很省事；之后改一次客户名、调一次书价，或删除最后一条订单项，就可能让同一个事实在不同位置互相矛盾。**关系规范化**研究的正是这种问题：根据数据之间稳定的决定关系，把一个混杂的关系模式拆成更可靠的模式。

这不是“表拆得越多越专业”的竞赛。规范化要求消除的是**同一事实的无约束重复**；为了保存历史而出现的订单成交价、收货地址快照，仍然是不同时间点的不同事实，不能被错误地合并掉。本篇继续使用在线书店，建立从函数依赖到 1NF、2NF、3NF、BCNF，以及无损分解和受控反规范化的完整链路。

## 函数依赖：哪些属性能确定哪些属性

在同一个关系中，若属性集 `X` 的值一旦确定，属性集 `Y` 的值也只能有一个确定结果，就说存在函数依赖：`X → Y`。读作“X 函数决定 Y”。例如在当前图书目录中：

```text
book_id → isbn, title, current_price
isbn    → book_id, title, current_price
```

`book_id` 唯一标识一本图书，所以同一个 `book_id` 不能对应两个标题；`isbn` 若被业务规则声明为唯一，也可以决定该图书的其他属性。函数依赖表达的是**业务语义和约束**，并不只是某一小批测试数据“碰巧没有重复”。

例如下面这张临时导入表里，今天每个 `customer_name` 恰好只出现一次，并不能推出 `customer_name → customer_id`：同名客户完全可能在明天注册。相反，若系统规定邮箱唯一，并且数据库建立了唯一约束，`email → customer_id` 才是可依赖的规则。

| 关系 | 可以成立的依赖 | 不应凭样本假设的依赖 |
| ---- | -------------- | -------------------- |
| `customer` | `customer_id → name, email`；`email → customer_id` | `name → customer_id` |
| `book` | `book_id → title, current_price`；`isbn → book_id` | `title → book_id` |
| `order_item` | `(order_id, line_no) → book_id, quantity, unit_price` | `book_id → unit_price` |

最后一行特别重要。`book_id → current_price` 说的是当前目录价；`order_item.unit_price` 是该订单行的成交价。同一图书可能参加满减或在不同日期售卖，因此 `book_id` 无法决定成交价。把这两种价格混为一谈，才是设计错误。

### 候选键与属性闭包

若一组属性能决定关系中的全部属性，称它是一个**超键**；其中再删去任何属性就不再能决定全部属性的超键，称为**候选键**。选其中一个作为主键，是命名和实现上的选择，不会让其他候选键失去唯一性要求。

判断一组属性能推出什么，可使用**属性闭包**。设关系：

```text
Enrollment(student_id, course_id, student_name, course_name, grade)

student_id → student_name
course_id  → course_name
(student_id, course_id) → grade
```

从 `{student_id, course_id}` 开始：由第一条推出 `student_name`，由第二条推出 `course_name`，由第三条推出 `grade`，得到所有属性。因此 `{student_id, course_id}` 是超键；去掉任一列都不能确定 `grade`，它也是候选键。这个推导说明复合键为何不是两个“随便拼在一起的字段”，而是共同描述一条选课事实。

```text
{student_id, course_id}+
  = {student_id, course_id}
  ∪ {student_name}
  ∪ {course_name}
  ∪ {grade}
```

候选键、唯一键与函数依赖各有分工：候选键是设计推导，`PRIMARY KEY` / `UNIQUE` 是数据库执行的约束，函数依赖是二者背后的业务陈述。不能只靠应用层“插入前先查一下”来代替唯一约束；并发写入时，这种检查没有原子性。

## 为什么混合关系会产生异常

考虑一个为了方便导出而设计的宽表：

```text
order_line_raw(
  order_id, line_no,
  customer_id, customer_name, customer_email,
  book_id, book_title, current_price,
  quantity, unit_price
)
```

它隐含了下列依赖：

```text
customer_id → customer_name, customer_email
book_id → book_title, current_price
(order_id, line_no) → customer_id, book_id, quantity, unit_price
```

同一客户买三本书，姓名和邮箱会复制三次；同一本书出现在一千条订单行中，书名与当前价格也会复制一千次。这会造成三类经典异常：

- **更新异常**：客户改邮箱时漏改一行，数据库里便同时存在新旧邮箱。
- **插入异常**：一本尚未售出的新书没有订单行，若系统只保存宽表，就无处保存它的标题和价格。
- **删除异常**：删除某客户最后一条订单行，可能顺手丢失客户本身的联系方式。

这些异常不是 SQL 写得不熟练，而是一个关系同时保存了客户、图书和订单项三种粒度的事实。规范化的目的，就是让每个事实有明确、可维护的归属。

## 从第一范式到 BCNF

范式是对关系模式及其函数依赖提出的渐进条件。现实设计不需要把每张表机械追到最高范式，但应该理解每一级究竟在排除什么问题。

### 第一范式：一个字段表示一个可操作的值

**第一范式（1NF）**要求属性值在关系模型中是原子的，不把一组可独立查询、约束和更新的值塞进逗号字符串、数组文本或重复列组。

不合适的设计：

```text
book(book_id, title, author_ids = '10,18,23')
```

它无法可靠声明外键，也难以查“作者 18 写过哪些书”。对于在线书店，应使用关联表：

```sql
CREATE TABLE book_author (
    book_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,
    author_order INT NOT NULL,
    PRIMARY KEY (book_id, author_id),
    UNIQUE KEY uk_book_author_order (book_id, author_order),
    FOREIGN KEY (book_id) REFERENCES book(book_id),
    FOREIGN KEY (author_id) REFERENCES author(author_id)
);
```

原子不等于“现实世界中不可再拆”。地址可以存为一段收货快照；如果业务必须按省、市做运费规则和统计，就应将其拆成可操作的属性。判断标准是业务操作，而不是某个字段看起来够不够长。

### 第二范式：非键属性不能只依赖复合键的一部分

**第二范式（2NF）**建立在 1NF 之上，要求每个非主属性完全依赖候选键，而不是只依赖复合候选键的一部分。它主要针对拥有复合键的关系。

前面的 `Enrollment` 以 `(student_id, course_id)` 为键。`grade` 依赖完整的“学生选了哪门课”；但 `student_name` 只依赖 `student_id`，`course_name` 只依赖 `course_id`。这就是部分依赖。

```text
Enrollment(student_id, course_id, student_name, course_name, grade)

拆分为：
Student(student_id, student_name)
Course(course_id, course_name)
Enrollment(student_id, course_id, grade)
```

这样改学生姓名只需更新 `Student` 的一行，课程尚无人选时也能先进入 `Course`。请不要把“复合主键”本身当作违规项；真正的问题是其他字段是否只依赖其中一部分。

### 第三范式：非键属性不应经由另一个非键属性传递决定

**第三范式（3NF）**进一步避免传递依赖。直观地说，非键属性应直接描述键标识的对象，而不是描述另一个非键属性。

例如：

```text
Book(book_id, title, publisher_id, publisher_name)

book_id      → publisher_id
publisher_id → publisher_name
```

`publisher_name` 实际由 `publisher_id` 决定，而不是由图书自身决定。将它重复放在每本书上，出版社改名又会产生更新异常。应拆为：

```text
Book(book_id, title, publisher_id)
Publisher(publisher_id, publisher_name)
```

更严谨地说，对每个非平凡依赖 `X → A`，3NF 要求 `X` 是超键，或者 `A` 是某个候选键中的主属性。这个定义解释了少数 3NF 但不满足 BCNF 的模式为何可能仍可接受：3NF 往往较容易保持依赖。

### BCNF：每个决定因素都应是超键

**Boyce-Codd 范式（BCNF）**比 3NF 更严格：对每一个非平凡函数依赖 `X → Y`，`X` 都必须是超键。它消除由“非键决定因素”造成的冗余。

例如教学安排关系：

```text
Teaching(student_id, course_id, instructor)

(student_id, course_id) → instructor
instructor → course_id
```

假设每位教师只教授一门课，但一门课可有多个教师。候选键可能是 `(student_id, course_id)` 和 `(student_id, instructor)`；`instructor → course_id` 的左侧不是超键，于是违反 BCNF。可拆为：

```text
InstructorCourse(instructor, course_id)
StudentInstructor(student_id, instructor)
```

BCNF 并非总是唯一答案。某些分解会使原本依赖无法只在单表约束中检查；工程上常取 3NF，或在关键路径上配合事务、触发器和测试。理论给出的是取舍语言，不是替你拒绝一切冗余的法令。

## 分解必须无损，并尽量保持依赖

把一个关系拆成多个表后，重新连接应能准确还原原先的合法事实，既不能丢行，也不能凭空制造组合。这叫**无损连接分解**。

对二元分解 `R` 拆为 `R1`、`R2`，一个实用判据是交集属性能函数决定其中一张表的全部属性：

```text
R1 ∩ R2 → R1
或
R1 ∩ R2 → R2
```

以 `Book(book_id, title, publisher_id, publisher_name)` 为例，拆为 `Book(book_id, title, publisher_id)` 与 `Publisher(publisher_id, publisher_name)`。交集是 `publisher_id`，并且 `publisher_id → Publisher` 的全部属性，所以连接不会制造额外的“图书—出版社”组合。

```sql
SELECT b.book_id, b.title, p.publisher_name
FROM book AS b
JOIN publisher AS p
  ON p.publisher_id = b.publisher_id;
```

**依赖保持**则问：原有的依赖能否分别在各个分解后的表内验证，而不用每次把表重新连接。它让约束检查更简单。无损连接比依赖保持更不能妥协；若分解有损，查询会产生数据库中从未发生过的事实。无法同时满足两者时，常优先保证无损，再评估通过数据库约束或应用事务维护剩余规则。

## 规范化不会禁止历史快照与性能优化

有人会说“订单项里存 `unit_price` 不符合第三范式”，这通常是把属性语义看丢了。`book.current_price` 与 `order_item.unit_price` 不表示同一个属性：一个是当前目录价，一个是订单在特定时刻的成交价。它们之间不存在 `book_id → unit_price`，所以没有要消除的传递或部分依赖。

同理，正常化后的表仍可在明确代价与维护责任的前提下做**受控反规范化**：

- 在 `book_order` 保存 `total_amount`，以减少订单详情页的重复聚合；
- 为搜索或报表构建可重建的宽表、物化视图或同步索引；
- 将频繁读取且变化很少的展示字段冗余到缓存中。

关键在于写下不变量和维护者。例如订单总额必须满足：

```text
book_order.total_amount
  = SUM(order_item.quantity × order_item.unit_price)
```

若保存这个冗余值，就应在同一事务中更新订单项与总额，或让它仅由可重建的投影产生；没有更新路径的冗余只是未来的不一致。

## 把理论落到 DDL 和日常评审

函数依赖不能全部由 SQL 的 `FOREIGN KEY` 自动表达，但它会指导具体约束：候选键对应 `PRIMARY KEY` / `UNIQUE`，必需联系对应 `NOT NULL` 外键，值域对应类型、`CHECK` 与受控状态机。数据库无法理解“`customer_name` 应只由 `customer_id` 决定”这种自然语言时，设计者要通过分表避免它被重复保存。

评审一个新表时，可以按以下顺序提问：

1. 这张表的一行到底描述什么事实？候选键是什么？
2. 是否有属性只依赖复合键的一部分，或依赖其他非键属性？
3. 一次修改、插入或删除是否会迫使同一事实在多处同步？
4. 若要拆表，连接能否无损还原原事实，关键依赖在哪里检查？
5. 若故意冗余，它保存的是历史快照、可重建投影，还是未经说明的重复？谁在事务中维护它？

## 本篇小结

- 函数依赖来自业务规则；属性闭包帮助识别超键和候选键，不能只凭样本数据猜测。
- 1NF 处理可独立操作的重复组，2NF 消除对复合键的部分依赖，3NF 和 BCNF 处理传递依赖与非键决定因素。
- 分解至少应保证无损连接，并尽可能保持依赖；拆表若产生伪造组合，就失去了意义。
- 订单成交价等历史快照不是错误冗余。冗余是否合理，取决于它是否表达不同事实，以及是否有明确的一致性维护路径。

下一篇[SQL 定义数据与完整性约束](04-sql-ddl-constraints.md)会把这里推导出的键、联系和值域落实为可执行的 MySQL DDL。理论若不能落到约束和事务边界，便只是一套很工整、却救不了数据的词汇。
