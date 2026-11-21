+++
date = '2026-11-21T20:00:00+08:00'
draft = false
title = '数据库系统核心概念综合复习：关系模型、规范化、SQL 与 E-R 设计'
math = true
+++

数据库原理中的术语往往成对出现：数据库与数据库系统、模式与实例、超键与候选键、无损分解与依赖保持。若只靠逐项背诵，很容易在题目换一种英文表述时失去方向。本篇以“数据如何被描述、约束、查询和设计”为主线，串起数据库基础、关系模型、关系代数、规范化、SQL 与 E-R 设计。

核心结论是：**数据库设计先表达业务事实，再用键和约束保证事实，最后用查询与物理结构高效地访问事实**。范式、外键和索引各自解决的问题不同，不能相互替代。

## 一、数据库、DBMS 与数据库系统

### 1. 基本概念

- **数据（data）**：对客观事物的记录，例如学生姓名、学号和成绩。
- **数据库（database，DB）**：有组织、可共享、长期存储的相关数据集合。
- **数据库管理系统（Database Management System，DBMS）**：管理数据库的软件，例如 MySQL、Oracle、SQL Server 和 PostgreSQL。
- **数据库系统（Database System，DBS）**：由数据库、DBMS、应用程序、用户或管理员，以及相关硬件和规则共同构成的整体。

可以把数据库系统理解为：

```text
Database System
= Database + DBMS + Applications + Users/Administration
```

因此，题目询问 database system 包含什么时，答案不能只停在“数据库”。数据库只是被管理的数据集合；DBS 才是让数据能够被安全、共享且持续使用的完整系统。

### 2. 数据库方式的优势

DBMS 统一管理数据，通常带来下列能力：

- 数据共享（data sharing）；
- **受控制的数据冗余**（controlled redundancy）；
- 数据一致性（data consistency）与完整性（data integrity）；
- 数据安全（data security）与权限控制；
- 并发访问控制（concurrent access control）；
- 备份与恢复（backup and recovery）；
- 数据独立性（data independence）。

“减少冗余”不等于“绝对没有重复数据”。为了查询性能、历史快照或容灾，系统可以保留冗余；关键是明确冗余的来源、维护规则和一致性责任。盲目复制字段才是问题，不是冗余这个词本身。

### 3. DBA 与应用程序员的边界

**数据库管理员（Database Administrator，DBA）**通常负责：

- 定义数据库模式、存储结构和访问方法；
- 授权用户并维护安全性、完整性约束；
- 备份、恢复和性能调优；
- 管理并发控制与日常运行。

编写下单、支付、查询等业务功能，或开发用户界面，通常属于**应用程序员（application programmer）**或软件开发人员的职责。两者需要协作，但“creating application programs”一般不是 DBA 的核心工作。

## 二、三级模式与数据独立性

### 1. 三层模式分别描述什么

数据库的 three-schema architecture 可概括为三层：

| 层次 | 英文 | 关注的问题 |
| ---- | ---- | ---------- |
| 外模式 | external schema / view level | 某个用户或用户组能看到什么 |
| 概念模式 | conceptual schema / logical level | 整个数据库在逻辑上有哪些实体、关系和约束 |
| 内模式 | internal schema / physical level | 数据如何在存储介质上组织和访问 |

三层关系可记为：

```text
User-specific views
        ↓
External level
        ↓
Conceptual level
        ↓
Internal level
        ↓
Physical storage
```

外模式描述用户视图。例如学生只能查看自己的成绩，教师可查看所授课程的学生名单，管理员可查看完整数据。概念模式描述全局逻辑结构，例如：

```text
Student(student_id, name, major)
Course(course_id, title, credits)
Enrollment(student_id, course_id, grade)
```

内模式则关心数据文件、索引、数据页、分区和实际存储位置；它回答的是“怎样存”，而不是“业务上有什么”。

### 2. 物理与逻辑数据独立性

数据独立性指底层变化时，上层模式和应用程序不必大面积修改。

| 改动 | 对应概念 | 典型例子 |
| ---- | -------- | -------- |
| 改变索引、文件组织、页大小或磁盘位置 | 物理数据独立性 | B+ 树改为哈希索引、增加辅助索引 |
| 改变逻辑属性、实体关系或表的逻辑拆分 | 逻辑数据独立性 | 为 `Student` 增加 `email`，拆分逻辑关系 |
| 改变某类用户看到的字段 | 外模式变更 | 为财务人员创建专用视图 |

**物理数据独立性**表示内部模式变化不影响概念模式和应用程序；**逻辑数据独立性**表示概念模式变化尽量不影响外模式和应用程序。后者更难，因为它更接近业务代码依赖的数据结构。

一句话区分：物理独立性处理“怎么存”，逻辑独立性处理“存什么、逻辑上怎样组织”。

## 三、数据模型与关系模型

### 1. 数据模型的组成

数据模型（data model）是一组描述数据、数据关系、约束和操作的概念工具。一个完整的数据模型通常包括：

- 数据结构（data structure）；
- 数据操作（data operations）；
- 完整性约束（integrity constraints）。

关系模型（relational model）、层次模型（hierarchical model）、网状模型（network model）和面向对象数据模型都是数据模型。题干出现 relation、attribute、tuple 时，通常在考关系模型。

### 2. 表、行、列与实例

设有关系模式：

```text
Student(student_id, name, major, age)
```

其中某行数据为：

```text
S001 | Alice | Computer Science | 20
```

| 中文 | 英文 | 在表中的对应物 |
| ---- | ---- | -------------- |
| 关系 | relation | 一张表 |
| 关系模式 | relation schema | `Student(student_id, name, major, age)` |
| 关系实例 | relation instance | 某一时刻表中的全部数据 |
| 元组 | tuple | 一行（row） |
| 属性 | attribute | 一列（column） |
| 属性值 | attribute value | 单元格中的具体值 |
| 域 | domain | 属性可取值的范围 |
| 度 | degree / arity | 列数 |
| 基数 | cardinality | 行数 |

特别注意：`degree` 是属性或列的数量，`cardinality` 是元组或行的数量。关系模式相对稳定，关系实例则会随着插入、删除和更新不断变化。

### 3. 关系模型的基本性质

在严格的关系模型中：

- 一张关系可视为集合，元组没有本质顺序；
- 属性也没有本质顺序；
- 单元格应保存原子值（atomic value）；
- 不应把可重复的一串值随意塞进同一个字段。

例如下面的 `courses` 同时保存多门课程，不利于查询、约束和更新：

```text
Student(student_id, name, courses)
S001, Alice, "Database, Java, English"
```

更合适的做法是用独立关系表达选课事实：

```text
Enrollment(student_id, course_id)
```

这也是第一范式（1NF）要求原子值的直接应用。

## 四、键与完整性约束

### 1. 超键、候选键与主键

假设：

```text
Student(student_id, email, name)
```

且 `student_id`、`email` 都唯一。

- **超键（superkey）**：能唯一标识一个元组的属性集合。`{student_id}`、`{student_id, name}` 都是超键；超键可以包含冗余属性。
- **候选键（candidate key）**：最小超键。它既要唯一，又不能删除任意属性后仍唯一。因此 `{student_id}` 和 `{email}` 是候选键，`{student_id, email}` 虽是超键却不是候选键。
- **主键（primary key）**：从候选键中选择一个作为主要标识，例如选择 `student_id`。未被选作主键的其他候选键称为 alternate keys。

“最小”指属性集合不可再删，不是数值更小或字符串更短。这样的措辞陷阱并不高明，却颇受试题喜爱。

### 2. 复合键与外键

在多对多选课中：

```text
Enrollment(student_id, course_id, grade)
```

`(student_id, course_id)` 共同唯一标识一条选课记录，是**复合键（composite key）**。

若关系定义为：

```text
Student(student_id, name)
Course(course_id, title)
Enrollment(student_id, course_id, grade)
```

那么 `Enrollment.student_id` 引用 `Student.student_id`，`Enrollment.course_id` 引用 `Course.course_id`。它们是外键（foreign key），用于保证选课记录不会凭空指向不存在的学生或课程。

### 3. 三类完整性约束

| 约束 | 核心要求 | 示例 |
| ---- | -------- | ---- |
| 实体完整性（entity integrity） | 主键不能为 `NULL` | `student_id` 必须存在 |
| 参照完整性（referential integrity） | 外键必须引用已存在的键值，或按规则为 `NULL` | 选课记录中的学生必须存在 |
| 用户定义完整性（domain constraints / business rules） | 满足业务和值域规则 | 年龄大于 0、金额不为负 |

若 `Student` 中不存在 `S999`，则下面的选课记录违反参照完整性：

```text
Enrollment(student_id = 'S999', course_id = 'C001')
```

## 五、关系代数：SQL 的概念基础

设有：

```text
Student(sid, name, major)
Course(cid, title)
Enrollment(sid, cid, grade)
```

### 1. 选择与投影

选择（selection）从关系中筛选行，可用下式表示：

$$
\sigma_{\text{major} = \text{'CS'}}(\text{Student})
$$

对应 SQL：

```sql
SELECT *
FROM Student
WHERE major = 'CS';
```

投影（projection）从关系中保留指定列：

$$
\pi_{\text{name},\ \text{major}}(\text{Student})
$$

```sql
SELECT name, major
FROM Student;
```

选择影响行（rows / tuples），投影影响列（columns / attributes）。可以记为：selection 选哪些记录，projection 取哪些字段。

### 2. 集合、笛卡尔积与连接

若两个关系 union-compatible，即属性数量相同且对应属性域兼容，则可以做集合运算：

- 并：$R \cup S$，属于 $R$ 或 $S$ 的元组；
- 交：$R \cap S$，同时属于 $R$ 和 $S$ 的元组；
- 差：$R - S$，属于 $R$ 但不属于 $S$ 的元组。

关系代数使用集合语义，会消除重复元组；SQL 默认并不完全如此，通常需要 `DISTINCT` 或集合运算显式表达。

笛卡尔积 `Student × Course` 会产生每个学生与每门课程的全部组合。若前者有 100 行、后者有 20 行，结果有 $100 \times 20 = 2000$ 行。它通常只是连接的中间概念，直接使用往往会得到大量无意义组合。

连接（join）按照相关属性组合表。例如 `Student ⋈ Enrollment` 可以得到学生及其选课记录。常见类型包括 theta join、equijoin、natural join、inner join 和各类 outer join。

```sql
SELECT s.name, e.cid, e.grade
FROM Student AS s
JOIN Enrollment AS e
  ON s.sid = e.sid;
```

### 3. 除法与“全部满足”

除法（division）常用于“找出满足全部条件的对象”，例如“选修所有必修课程的学生”或“购买每一种指定商品的客户”。题干出现 all、every、each、所有或每一门时，应考虑关系除法的语义；在 SQL 中常用嵌套 `NOT EXISTS` 表达。

## 六、函数依赖与属性闭包

### 1. 函数依赖

在关系模式 $R$ 中，函数依赖：

$$
X \to Y
$$

表示任意两个元组只要在 $X$ 上取值相同，也必须在 $Y$ 上取值相同。比如：

$$
\text{student\_id} \to \{\text{name},\ \text{major}\}
$$

说明同一个学号只能对应同一个姓名和专业；反向的 `name → student_id` 未必成立，因为可能有重名。

如果 $Y \subseteq X$，则 $X \to Y$ 是平凡函数依赖，例如 $AB \to A$；它必然成立，通常不提供新的设计信息。若 $Y \nsubseteq X$，则是非平凡函数依赖，例如 `student_id → name`。

### 2. 属性闭包

属性集 $X$ 在函数依赖集 $F$ 下能推出的全部属性称为 $X$ 的闭包，记作 $X^+$。它是判断超键、寻找候选键和判断范式的基础。

设：

$$
R(A, B, C, D, E)
$$

函数依赖集为：

$$
F = \{A \to B,\ B \to C,\ AC \to D,\ D \to E\}
$$

求 $A^+$：

1. 初始时 $A^+ = \{A\}$。
2. 由 $A \to B$ 得到 $B$，再由 $B \to C$ 得到 $C$。
3. 此时已有 $A$、$C$，由 $AC \to D$ 得到 $D$。
4. 由 $D \to E$ 得到 $E$。

因此：

$$
A^+ = \{A, B, C, D, E\}
$$

闭包覆盖了关系 $R$ 的全部属性，所以 $A$ 是超键；并且 $A$ 无法再删属性，它也是候选键。

### 3. 寻找候选键的实用步骤

对给定关系和依赖集，可以按下列顺序思考：

1. 找出从未出现在任一依赖右侧的属性；它们通常必须出现在每个候选键中。
2. 以这些属性为起点求闭包。
3. 若闭包未覆盖全部属性，逐步补充必要属性。
4. 闭包覆盖整个关系时，得到超键；再尝试删去属性，以检验最小性。

主属性（prime attribute）至少属于一个候选键；非主属性（non-prime attribute）不属于任何候选键。

## 七、规范化：减少异常，而不是机械拆表

规范化（normalization）旨在减少不合理冗余与异常，不是“表越碎越好”。常见异常包括：

- 插入异常（insertion anomaly）：保存一类信息时被迫同时插入无关信息；
- 删除异常（deletion anomaly）：删除一条记录时意外失去另一项事实；
- 更新异常（update anomaly）：同一事实被重复存储，修改时容易漏改。

例如下面的选课关系重复保存了学生、课程与教师信息：

```text
Enrollment(
  student_id,
  student_name,
  course_id,
  course_name,
  instructor,
  grade
)
```

### 1. 第一范式、第二范式与第三范式

| 范式 | 主要要求 | 要消除的问题 |
| ---- | -------- | ------------ |
| 1NF | 每个属性值原子化，不是重复组或多值集合 | 非原子值 |
| 2NF | 在 1NF 基础上，非主属性完全依赖整个候选键 | 对复合键的部分依赖 |
| 3NF | 对每个非平凡依赖，决定因素是超键，或右侧是主属性 | 不恰当的传递依赖 |

不符合 1NF 的例子：

```text
Student(sid, name, phones)
S001, Alice, "138..., 139..."
```

可以拆为：

```text
Student(sid, name)
StudentPhone(sid, phone)
```

对于：

```text
Enrollment(sid, cid, student_name, course_name, grade)
```

若候选键是 `(sid, cid)`，且有 `sid → student_name`、`cid → course_name`，则 `student_name` 和 `course_name` 只依赖复合键的一部分，违反 2NF。可拆为：

```text
Student(sid, student_name)
Course(cid, course_name)
Enrollment(sid, cid, grade)
```

再看：

```text
Employee(emp_id, dept_id, dept_name)
```

若 `emp_id → dept_id` 且 `dept_id → dept_name`，则 `dept_name` 通过 `dept_id` 间接依赖 `emp_id`，形成传递依赖。常见拆分是：

```text
Employee(emp_id, dept_id)
Department(dept_id, dept_name)
```

### 2. BCNF 与 3NF 的区别

Boyce-Codd Normal Form（BCNF）比 3NF 更严格：对每个非平凡函数依赖 $X \to Y$，决定因素 $X$ 必须是超键。

| 比较项 | 3NF | BCNF |
| ------ | --- | ---- |
| 决定因素必须是超键吗 | 不一定 | 必须 |
| 右侧属性为主属性时是否有例外 | 可以 | 不可以 |
| 严格程度 | 较宽松 | 更严格 |
| 保持所有函数依赖 | 较容易做到 | 不一定 |

范式的包含关系是：

$$
\text{BCNF} \subseteq \text{3NF} \subseteq \text{2NF} \subseteq \text{1NF}
$$

满足 BCNF 一定满足 3NF，反过来则不一定。工程上通常还要在规范化、依赖保持、查询性能和历史快照需求之间权衡。

## 八、分解：无损连接与依赖保持

### 1. 无损连接分解

分解后重新自然连接，应能准确恢复原关系，既不丢失元组，也不产生伪元组（spurious tuples）。这称为无损连接分解（lossless-join decomposition）。

对于二元分解 $R \to R_1, R_2$，无损的充分必要判断为下列任一依赖在 $F^+$ 中成立：

$$
(R_1 \cap R_2) \to R_1
$$

或：

$$
(R_1 \cap R_2) \to R_2
$$

也就是说，两个子关系的公共属性必须能函数决定其中一个子关系的全部属性。仅仅“有一个共同字段”远远不够。

例如：

$$
R(A, B, C),\quad F = \{A \to B\}
$$

若分解为 $R_1(A, B)$ 与 $R_2(A, C)$，交集为 $\{A\}$，且 $A \to AB$，因此公共属性 $A$ 能决定 $R_1$，该分解无损。

### 2. 依赖保持

依赖保持（dependency preservation）指分解后无须把子表连接起来，就能检查和维护原有函数依赖。若原依赖集 $F$ 能由各子关系上的投影依赖联合推出，则分解保持依赖。

| 性质 | 关注点 |
| ---- | ------ |
| 无损连接 | 是否能通过连接恢复原始数据且不产生伪元组 |
| 依赖保持 | 是否能不连接表就检查原函数依赖 |

一个分解可能无损但不保持依赖，也可能保持依赖却有损。BCNF 分解通常优先保证无损，3NF 合成常用于同时争取无损和依赖保持。

## 九、SQL：分类与逻辑执行顺序

### 1. SQL 分类

| 类别 | 英文 | 常见命令 |
| ---- | ---- | -------- |
| 数据定义语言 | DDL | `CREATE`、`ALTER`、`DROP` |
| 数据操纵语言 | DML | `SELECT`、`INSERT`、`UPDATE`、`DELETE` |
| 数据控制语言 | DCL | `GRANT`、`REVOKE` |
| 事务控制语言 | TCL | `COMMIT`、`ROLLBACK`、`SAVEPOINT` |

### 2. `SELECT` 的逻辑处理顺序

书写时通常是 `SELECT`、`FROM`、`WHERE`、`GROUP BY`、`HAVING`、`ORDER BY`；逻辑处理过程更接近：

```text
FROM
→ JOIN / ON
→ WHERE
→ GROUP BY
→ HAVING
→ SELECT
→ DISTINCT
→ ORDER BY
→ LIMIT
```

因此，`WHERE` 在分组前过滤普通行，`HAVING` 在分组后过滤分组结果；聚合函数通常不能直接放在 `WHERE` 中。

```sql
SELECT dept_id, COUNT(*) AS employee_count
FROM Employee
WHERE salary >= 5000
GROUP BY dept_id
HAVING COUNT(*) >= 10;
```

这条查询先排除工资低于 5000 的员工，再按部门分组，最后保留员工数至少为 10 的部门。记忆句是：`WHERE filters rows; HAVING filters groups.`

### 3. 聚合函数、`NULL` 与连接

- `COUNT(*)` 统计所有行；`COUNT(column)` 只统计该列非 `NULL` 的值。
- `SUM`、`AVG`、`MAX`、`MIN` 分别用于求和、平均、最大和最小值。
- `NULL` 表示未知、不适用或尚未提供；它不是 `0`、空字符串或 `false`。
- 判断空值必须写 `column IS NULL`，而不是 `column = NULL`，因为 `NULL` 遵循真、假、未知的三值逻辑。

连接示例：

```sql
SELECT s.name, c.title, e.grade
FROM Student AS s
JOIN Enrollment AS e
  ON s.sid = e.sid
JOIN Course AS c
  ON e.cid = c.cid;
```

常见错误包括漏写连接条件而形成笛卡尔积，把外连接的过滤条件放在 `WHERE` 中而意外收窄为近似内连接，以及误以为 SQL 会自动识别主外键关系。

### 4. 子查询与“全部”条件

`IN` 判断值是否属于子查询结果；`EXISTS` 判断子查询是否至少返回一行；`NOT EXISTS` 判断是否没有返回行；`ALL`、`ANY`（或 `SOME`）用于与子查询结果比较。

```sql
SELECT name
FROM Student
WHERE sid IN (
  SELECT sid
  FROM Enrollment
  WHERE cid = 'DB101'
);
```

当题目表达“选修所有课程”或“购买每一种商品”时，可用双重 `NOT EXISTS` 表达“找不到任何一个未满足条件的对象”，这正对应关系除法的语义。

## 十、E-R 模型与关系模式映射

### 1. 实体、属性、联系与约束

实体（entity）是现实世界中可区分的对象，如 `Student`、`Customer`、`Car`、`Course`。同型实体构成实体集（entity set）。属性（attribute）是实体的特征，可分为简单、复合、单值、多值、派生和键属性。

联系（relationship）表达实体集间的关联：

```text
Customer — places — Order
Student  — enrolls in — Course
Customer — buys — Car
```

联系自身也可以有属性，例如销售关系中的 `sale_date`、`sale_price` 和 `order_id`。

常见基数约束为 1:1、1:N、N:1 和 M:N。若一辆车最多卖给一个客户、一个客户可购买多辆车，则从 `Customer` 到 `Car` 可看作 1:N；从 `Car` 到 `Customer` 则是 N:1。参与约束中，total participation 表示每个实体都必须参与联系，partial participation 表示可以不参与。

### 2. 弱实体与识别联系

强实体拥有完整主键，可独立被唯一标识，例如：

```text
Employee(employee_id, name)
```

弱实体不能仅凭自身属性唯一标识，必须依赖拥有者实体（owner entity / identifying entity）。例如家属的姓名不足以全局唯一：

```text
Dependent(employee_id, dependent_name, birth_date)
```

`dependent_name` 是部分键（partial key / discriminator），它只能区分同一个员工名下的家属；与 `employee_id` 合并后才能构成弱实体的主键。

弱实体与拥有者之间的关系称为识别联系（identifying relationship）。弱实体对该联系是全参与的，并且从弱实体到拥有者通常是多对一：多个家属可以依赖同一员工，每个家属通常只依赖一个员工。

### 3. 从 E-R 模型映射到关系

| E-R 结构 | 常用关系映射 |
| -------- | ------------ |
| 强实体 | 每个实体集映射为一个关系，键属性成为主键 |
| 弱实体 | 包含自身属性、拥有者主键和部分键；通常以两者组成联合主键 |
| 1:1 联系 | 将一方主键作为外键放入另一方，优先放在全参与一侧；必要时单独建表 |
| 1:N 联系 | 把“一方”的主键作为外键放入“多方”关系 |
| M:N 联系 | 必须建立单独的联系表，双方键通常构成复合主键 |

例如部门与员工的 1:N 关系：

```text
Department(dept_id, dept_name)
Employee(emp_id, name, dept_id)
```

其中 `Employee.dept_id` 是指向 `Department` 的外键。学生与课程的 M:N 联系则可表示为：

```text
Student(sid, name)
Course(cid, title)
Enrollment(sid, cid, grade)
```

`Enrollment` 是联系表，`sid`、`cid` 是外键，`(sid, cid)` 通常是复合主键，`grade` 是联系的属性。

## 十一、数据库设计的三个阶段

| 阶段 | 关注点 | 常见产出 |
| ---- | ------ | -------- |
| 概念设计（conceptual design） | 业务世界中有什么实体、属性和规则 | E-R 图、业务规则、基数与参与约束 |
| 逻辑设计（logical design） | 如何映射到关系模型 | 表、主键、外键、约束和规范化模式 |
| 物理设计（physical design） | 如何高效存储和访问 | 索引、分区、文件组织、数据页和调优方案 |

“将高层概念模式映射到实现所用的数据模型”描述的是 logical design。不要在概念设计阶段急着写 SQL，也不要把索引当作逻辑设计中实体关系的一部分；它们关注的层次不同。

## 十二、考前速记与解题路径

遇到术语题时，与其在选项中猜测，不如先把题干归到正确层次：

- `uniquely identify`：先想键；出现 `minimal` 时重点检查候选键的最小性。
- `physical storage`：先想内模式与物理数据独立性。
- `all`、`every`：先想关系除法或双重 `NOT EXISTS`。
- `weak entity`：立即联想 partial key、total participation、identifying relationship，以及指向拥有者的多对一。
- `WHERE` 与 `HAVING`：分别过滤行与分组。
- 分解题：先问公共属性能否决定其中一个子关系，再问原函数依赖能否不连接表就维护。

最后应掌握的不是一串孤立结论，而是一条因果链：业务事实决定概念模型，概念模型映射为关系与键，函数依赖帮助发现冗余，分解与约束保证数据正确，SQL 负责表达查询，物理设计再为实际访问成本服务。数据库原理并没有因为公式和缩写变得神秘；它只是要求我们对“一个事实由什么决定、应当在哪里保存”保持足够严格而已。
