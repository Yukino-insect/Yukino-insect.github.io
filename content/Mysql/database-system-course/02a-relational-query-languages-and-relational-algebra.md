+++
date = '2026-11-21T20:00:00+08:00'
draft = false
title = '关系查询语言：从关系代数到 SQL 声明式查询'
math = true
+++

关系数据库中的查询不是“从表里拿数据”这么含糊的动作，而是把已有关系按规则转换为新关系。关系查询语言规定了这些规则的表达方式；关系代数则把复杂查询拆成一系列可组合的表运算。理解它以后，`WHERE`、`SELECT`、`JOIN`、`UNION` 不再只是 SQL 关键字，而是有明确输入、输出和数学语义的操作。

本篇先说明过程式与声明式查询语言的差别，再以教师、授课和开课数据为统一案例，逐步推导选择、投影、笛卡尔积、连接、集合运算、重命名和查询等价改写。文中的关系代数采用集合语义；相同查询的 SQL 示例以 MySQL 8 为参照，并特别指出与 SQL 默认多重集语义的差异。

## 一、关系查询语言在解决什么问题

关系模型将数据表示为一组关系（relation），可近似理解为一张张表。关系查询语言的目标是从一个或多个输入关系得到结果关系：

```text
输入关系 → 按规则运算 → 输出关系
```

例如，给定教师关系 `instructor` 与授课关系 `teaches`，可以查询物理系教师、讲授过课程的教师，或在指定学期都开设过的课程。无论查询多复杂，结果仍可看作一张具有模式和元组的关系，因此还能继续参与下一步运算。

这种“输入是关系，输出还是关系”的闭包性质，使查询能够组合、验证和优化。它也是关系代数成为 SQL 理论基础的原因。

### 1. 过程式与声明式

过程式（procedural）查询语言既描述想要的结果，也显式给出得到结果的运算过程。关系代数正是这种形式：找出物理系教师姓名，需要先筛选行，再保留姓名列：

$$
\pi_{\text{name}}
\left(
  \sigma_{\text{dept\_name} = \text{'Physics'}}(\text{instructor})
\right)
$$

声明式（declarative）或非过程式（non-procedural）语言主要描述结果应满足的条件，而不要求用户指定完整执行策略。相同查询的 SQL 是：

```sql
SELECT name
FROM instructor
WHERE dept_name = 'Physics';
```

SQL 使用者通常不必决定是否先过滤、使用哪个索引、按何种顺序连接数据；数据库优化器会选择执行计划。因此可以这样区分：

| 类型 | 使用者主要描述什么 | 执行策略主要由谁决定 |
| ---- | ------------------ | -------------------- |
| 关系代数 | 结果及其运算步骤 | 编写表达式的人 |
| SQL 查询 | 所需结果及约束条件 | 数据库优化器 |

这并不表示 SQL 完全没有过程性。`ORDER BY`、窗口函数、递归 CTE 和存储过程都能表达顺序或过程；不过普通 SQL 查询的主要风格仍是声明式。

### 2. 三种纯关系查询语言

理论上常见三种纯关系查询语言：

- 关系代数（relational algebra）；
- 元组关系演算（tuple relational calculus，TRC）；
- 域关系演算（domain relational calculus，DRC）。

在安全查询的通常范围内，它们具有相同的表达能力：某个查询能用一种语言表达，就也能用其他两种表达。差异在于表达视角。

- 关系代数将查询写成运算流水线；
- 元组关系演算用“哪些行应属于结果”的逻辑谓词描述查询；
- 域关系演算用属性值而非整行作为变量。

例如，找物理系教师的关系演算思想可写为：

$$
\{t \mid t \in \text{instructor} \land t.\text{dept\_name} = \text{'Physics'}\}
$$

它表示所有属于 `instructor` 且院系为 `Physics` 的元组 $t$。工程上的 SQL 同时吸收了关系代数和关系演算的思想，并增加了聚合、排序、空值、事务等实用能力。

### 3. 为什么经典关系代数不是图灵完备

经典关系代数不能自然表达任意次数的循环或递归。例如，仅依靠固定数量的连接，无法表示“找出社交图中任意层级的间接好友”这种需要不断扩展结果直到稳定的可达性问题。

SQL 的递归 CTE 可以扩展这项能力：

```sql
WITH RECURSIVE reachable AS (
  SELECT source_id, target_id
  FROM edge

  UNION

  SELECT r.source_id, e.target_id
  FROM reachable AS r
  JOIN edge AS e
    ON r.target_id = e.source_id
)
SELECT *
FROM reachable;
```

这属于实际 SQL 对经典关系代数的扩展。并非图灵完备不意味着关系代数无用；绝大多数表查询仍可由它的基本思想清晰解释。

## 二、六个基础运算与派生运算

教材通常把选择、投影、并、差、笛卡尔积和重命名视为六个基础运算：

| 运算 | 记号 | 作用 | 常见 SQL 对应 |
| ---- | ---- | ---- | ------------- |
| 选择 | $\sigma$ | 保留满足谓词的行 | `WHERE` |
| 投影 | $\pi$ | 保留指定列 | `SELECT DISTINCT` |
| 并 | $\cup$ | 合并两个兼容关系的元组 | `UNION` |
| 差 | $-$ | 保留左关系有、右关系没有的元组 | `EXCEPT` 或 `NOT EXISTS` |
| 笛卡尔积 | $\times$ | 将两关系的每对行组合 | `CROSS JOIN` |
| 重命名 | $\rho$ | 为关系或属性改名 | `AS` 别名 |

交、连接和自然连接十分常用，但可以由基础运算推导：

$$
r \cap s = r - (r - s)
$$

$$
r \bowtie_{\theta} s = \sigma_{\theta}(r \times s)
$$

第二个公式尤其重要：**连接本质上是笛卡尔积后按连接条件进行选择**。在实际查询中直接使用 `JOIN`，只是因为它比完整展开写法更清楚、更高效。

## 三、统一案例：教师、授课与开课

后续例子都使用以下简化数据。

### 1. 教师关系 `instructor`

| ID | name | dept_name | salary |
| -- | ---- | --------- | ------ |
| 10101 | 张敏 | Physics | 95000 |
| 12121 | 李雷 | Physics | 88000 |
| 15151 | 王芳 | Music | 72000 |
| 22222 | 陈晨 | Computer Science | 110000 |
| 33445 | 周宁 | Physics | 105000 |

关系模式为：

```text
instructor(ID, name, dept_name, salary)
```

### 2. 授课关系 `teaches`

| ID | course_id | sec_id | semester | year |
| -- | --------- | ------ | -------- | ---- |
| 10101 | PHY-101 | 1 | Fall | 2017 |
| 12121 | PHY-102 | 1 | Spring | 2018 |
| 33445 | PHY-101 | 2 | Spring | 2018 |
| 22222 | CS-101 | 1 | Fall | 2017 |
| 22222 | CS-101 | 2 | Spring | 2018 |

```text
teaches(ID, course_id, sec_id, semester, year)
```

### 3. 开课关系 `section`

| course_id | sec_id | semester | year |
| --------- | ------ | -------- | ---- |
| PHY-101 | 1 | Fall | 2017 |
| PHY-102 | 1 | Spring | 2018 |
| PHY-101 | 2 | Spring | 2018 |
| CS-101 | 1 | Fall | 2017 |
| CS-101 | 2 | Spring | 2018 |

```text
section(course_id, sec_id, semester, year)
```

### 4. 院系关系 `department`

| dept_name | building | budget |
| --------- | -------- | ------ |
| Physics | Physics | 800000 |
| Music | Arts | 300000 |
| Computer Science | Taylor | 1200000 |

```text
department(dept_name, building, budget)
```

关系代数把关系视为集合，结果不包含重复元组。SQL 普通 `SELECT` 则通常保留重复行，这种多重集（bag）语义是实际开发中必须留意的差异。

## 四、选择：用 $\sigma$ 筛选行

选择（select / selection）按照谓词筛选元组，记为：

$$
\sigma_p(r)
$$

其中 $r$ 是输入关系，$p$ 是选择谓词。形式化地说：

$$
\sigma_p(r) = \{t \mid t \in r \land p(t)\}
$$

含义是：从 $r$ 中保留所有属于该关系且满足 $p$ 的元组。选择改变的是行，不会删除列。

### 1. 使用常量条件筛选

查询物理系教师：

$$
\sigma_{\text{dept\_name} = \text{'Physics'}}(\text{instructor})
$$

结果为张敏、李雷和周宁所在的三行；全部字段仍然保留。对应 SQL：

```sql
SELECT *
FROM instructor
WHERE dept_name = 'Physics';
```

选择谓词可使用 $=, \ne, >, \ge, <, \le$，也可用 $\land$、$\lor$、$\neg$ 组合多个条件。

例如，找出工资超过 90,000 的物理系教师：

$$
\sigma_{
  \text{dept\_name} = \text{'Physics'}
  \land
  \text{salary} > 90000
}(\text{instructor})
$$

```sql
SELECT *
FROM instructor
WHERE dept_name = 'Physics'
  AND salary > 90000;
```

### 2. 比较同一行中的两个属性

选择条件也可以比较属性和属性。找出院系名与所在建筑名相同的院系：

$$
\sigma_{\text{dept\_name} = \text{building}}(\text{department})
$$

结果为 `Physics`，因为它的 `dept_name` 与 `building` 都是 `Physics`。

```sql
SELECT *
FROM department
WHERE dept_name = building;
```

## 五、投影：用 $\pi$ 保留列

投影（project / projection）只保留列出的属性，记为：

$$
\pi_{A_1, A_2, \ldots, A_k}(r)
$$

### 1. 选择所需输出字段

查询教师的 ID、姓名和工资：

$$
\pi_{\text{ID},\ \text{name},\ \text{salary}}(\text{instructor})
$$

```sql
SELECT DISTINCT ID, name, salary
FROM instructor;
```

在经典关系代数中，投影后的重复行会消除。例如：

$$
\pi_{\text{dept\_name}}(\text{instructor})
$$

即使 `Physics` 有三位教师，结果中也只会有一行 `Physics`。SQL 若要保持相同语义，必须使用 `DISTINCT`：

```sql
SELECT DISTINCT dept_name
FROM instructor;
```

只写 `SELECT dept_name` 会保留重复行，因而并不严格等价。

### 2. 广义投影

基础投影只列属性名；广义投影允许在输出列表中使用表达式。例如计算月薪：

$$
\pi_{\text{ID},\ \text{name},\ \text{salary} / 12}(\text{instructor})
$$

```sql
SELECT
  ID,
  name,
  salary / 12 AS monthly_salary
FROM instructor;
```

## 六、组合：先筛选，再投影

关系代数的每一步输出都是关系，因此可以嵌套。查询物理系教师的姓名，应先选择物理系行，再投影姓名列：

$$
\pi_{\text{name}}
\left(
  \sigma_{\text{dept\_name} = \text{'Physics'}}(\text{instructor})
\right)
$$

结果只有一列：张敏、李雷、周宁。

```sql
SELECT DISTINCT name
FROM instructor
WHERE dept_name = 'Physics';
```

可以把它读成一条稳定的查询思路：先决定需要哪些行，再决定最终展示哪些列。SQL 的书写顺序以 `SELECT` 开头，但逻辑上并不是“先选择列再决定行”。若不区分书写顺序与逻辑处理过程，很容易误解聚合、别名和 `HAVING` 等后续问题。

## 七、笛卡尔积与连接：从任意组合到有意义匹配

### 1. 笛卡尔积产生所有配对

笛卡尔积：

$$
\text{instructor} \times \text{teaches}
$$

会将 `instructor` 的每一行与 `teaches` 的每一行组合。案例中两表各有五行，结果共有：

$$
5 \times 5 = 25
$$

行。绝大多数行没有业务意义，例如教师张敏会与陈晨教授的 `CS-101` 被配对。

两张表都拥有 `ID` 属性时，必须加关系名前缀以消除歧义：`instructor.ID` 与 `teaches.ID`。SQL 中的对应写法是：

```sql
SELECT *
FROM instructor
CROSS JOIN teaches;
```

笛卡尔积很少是最终目标；它主要用于理解连接的定义。

### 2. theta 连接保留匹配组合

要得到教师实际讲授的课程，只保留两侧 ID 相同的组合：

$$
\sigma_{\text{instructor.ID} = \text{teaches.ID}}
(\text{instructor} \times \text{teaches})
$$

这可缩写为 theta 连接：

$$
\text{instructor}
\bowtie_{\text{instructor.ID} = \text{teaches.ID}}
\text{teaches}
$$

```sql
SELECT
  i.ID,
  i.name,
  i.dept_name,
  t.course_id,
  t.sec_id,
  t.semester,
  t.year
FROM instructor AS i
JOIN teaches AS t
  ON i.ID = t.ID;
```

连接反映了关系数据库的建模原则：教师事实、课程事实、授课事实各存一处，需要组合时再通过键关联。表被拆开不意味着事实无法查询；恰恰相反，正确的连接让事实既可独立维护又能按需组合。

### 3. 自然连接的便利与风险

自然连接（natural join）会把两张关系的所有同名属性都作为相等条件，并在结果中仅保留一份同名属性。本例中 `instructor` 与 `teaches` 都有 `ID`，可写：

$$
\text{instructor} \bowtie \text{teaches}
$$

```sql
SELECT *
FROM instructor
NATURAL JOIN teaches;
```

它在教材中很简洁，在工程中却应谨慎使用。假如两表日后又都出现 `created_at`，自然连接会额外要求它相等，查询语义可能在不报错的情况下改变。生产代码通常应写出明确条件：

```sql
SELECT *
FROM instructor AS i
JOIN teaches AS t
  ON i.ID = t.ID;
```

## 八、集合运算：并、交与差

并、交和差的输入必须并兼容（union-compatible）：属性数量相同，且对应属性的类型或域兼容。先定义两个结果集。

2017 年秋季开设的课程：

$$
F =
\pi_{\text{course\_id}}
\left(
  \sigma_{
    \text{semester} = \text{'Fall'}
    \land
    \text{year} = 2017
  }(\text{section})
\right)
$$

2018 年春季开设的课程：

$$
S =
\pi_{\text{course\_id}}
\left(
  \sigma_{
    \text{semester} = \text{'Spring'}
    \land
    \text{year} = 2018
  }(\text{section})
\right)
$$

### 1. 并集：至少在一个学期开设

$$
F \cup S
$$

结果为 `PHY-101`、`PHY-102`、`CS-101`。其中 `PHY-101` 与 `CS-101` 即使两个学期都出现，在集合结果中也各只保留一次。

```sql
SELECT course_id
FROM section
WHERE semester = 'Fall'
  AND year = 2017

UNION

SELECT course_id
FROM section
WHERE semester = 'Spring'
  AND year = 2018;
```

`UNION` 去重；`UNION ALL` 保留重复，后者不等价于经典关系代数的并。

### 2. 交集：两个学期都开设

$$
F \cap S
$$

结果为 `PHY-101` 和 `CS-101`。

```sql
SELECT course_id
FROM section
WHERE semester = 'Fall'
  AND year = 2017

INTERSECT

SELECT course_id
FROM section
WHERE semester = 'Spring'
  AND year = 2018;
```

若所用数据库不支持 `INTERSECT`，可以用 `EXISTS` 或连接重写；表达式变长，但语义不变。

### 3. 差集：只在一侧出现

$$
F - S
$$

表示 2017 年秋季开设、但 2018 年春季未开设的课程。在当前案例中结果为空。标准 SQL 可写为：

```sql
SELECT course_id
FROM section
WHERE semester = 'Fall'
  AND year = 2017

EXCEPT

SELECT course_id
FROM section
WHERE semester = 'Spring'
  AND year = 2018;
```

没有 `EXCEPT` 的 MySQL 版本可以使用 `NOT EXISTS` 改写：

```sql
SELECT DISTINCT f.course_id
FROM section AS f
WHERE f.semester = 'Fall'
  AND f.year = 2017
  AND NOT EXISTS (
    SELECT 1
    FROM section AS s
    WHERE s.course_id = f.course_id
      AND s.semester = 'Spring'
      AND s.year = 2018
  );
```

## 九、赋值与重命名：让复杂查询可读且无歧义

### 1. 赋值保存中间结果

赋值操作以 $\leftarrow$ 表示，像程序中的临时变量。查询物理系或音乐系教师可分步写为：

$$
\text{Physics} \leftarrow
\sigma_{\text{dept\_name} = \text{'Physics'}}(\text{instructor})
$$

$$
\text{Music} \leftarrow
\sigma_{\text{dept\_name} = \text{'Music'}}(\text{instructor})
$$

最后计算：

$$
\text{Physics} \cup \text{Music}
$$

赋值不是六个基础运算之一，却能让长表达式更容易验证。SQL 中可以用 CTE 表示类似结构：

```sql
WITH physics AS (
  SELECT *
  FROM instructor
  WHERE dept_name = 'Physics'
),
music AS (
  SELECT *
  FROM instructor
  WHERE dept_name = 'Music'
)
SELECT * FROM physics
UNION
SELECT * FROM music;
```

### 2. 重命名解决自连接

同一关系在一个查询中扮演两个角色时，需要重命名。问题是：找出工资高于 ID 为 `12121` 的教师。

- $i$ 代表所有待比较教师；
- $w$ 代表 ID 为 `12121` 的工资参照教师。

关系代数表达式为：

$$
\pi_{i.\text{ID},\ i.\text{name}}
\left(
  \sigma_{i.\text{salary} > w.\text{salary}}
  \left(
    \rho_i(\text{instructor})
    \times
    \sigma_{w.\text{ID} = 12121}
    \left(\rho_w(\text{instructor})\right)
  \right)
\right)
$$

执行逻辑并不神秘：先取李雷的工资 88,000；将每位教师与李雷配对；保留工资更高者；最后只输出其 ID 和姓名。

SQL 的表别名正是重命名：

```sql
SELECT i.ID, i.name
FROM instructor AS i
CROSS JOIN instructor AS w
WHERE w.ID = 12121
  AND i.salary > w.salary;
```

也可以改用标量子查询：

```sql
SELECT ID, name
FROM instructor
WHERE salary > (
  SELECT salary
  FROM instructor
  WHERE ID = 12121
);
```

## 十、等价查询与选择下推

同一查询通常不只一种关系代数写法。问题：找出由物理系教师讲授的课程信息。

写法一，先连接再过滤：

$$
\sigma_{\text{dept\_name} = \text{'Physics'}}
\left(
  \text{instructor}
  \bowtie_{\text{instructor.ID} = \text{teaches.ID}}
  \text{teaches}
\right)
$$

写法二，先过滤教师再连接：

$$
\left(
  \sigma_{\text{dept\_name} = \text{'Physics'}}(\text{instructor})
\right)
\bowtie_{\text{instructor.ID} = \text{teaches.ID}}
\text{teaches}
$$

两者对任何合法数据库状态都返回相同结果，因此是等价查询。但第二种通常更高效：如果教师表有百万行、物理系只有几十人，先用选择缩小输入，再连接授课表，会减少中间结果及连接成本。

这条规则称为**选择下推（selection pushdown）**：在不改变结果的前提下，尽可能早地过滤行。SQL 只需写出声明式查询：

```sql
SELECT
  i.ID,
  i.name,
  t.course_id,
  t.semester,
  t.year
FROM instructor AS i
JOIN teaches AS t
  ON i.ID = t.ID
WHERE i.dept_name = 'Physics';
```

优化器会依据统计信息、索引和代价模型选择实际计划。理解等价改写的价值不在于手工代替优化器，而在于阅读 `EXPLAIN` 时能判断：过滤是否过晚、连接输入是否过大、查询结构是否阻碍了索引使用。

## 十一、从问题到表达式的解题路径

面对一个多表查询，可按以下顺序拆解：

```text
需要哪些关系？
    ↓
每个关系先过滤哪些行？
    ↓
关系间使用哪些属性匹配？
    ↓
最终输出哪些列？
    ↓
是否需要去重、集合比较或让同一关系扮演多个角色？
```

对应到关系代数和 SQL：

| 要回答的问题 | 关系代数 | SQL 常见位置 |
| ------------ | -------- | ------------ |
| 保留哪些记录 | $\sigma$ | `WHERE` |
| 输出哪些字段 | $\pi$ | `SELECT` |
| 表如何关联 | $\bowtie$ | `JOIN ... ON` |
| 集合如何比较 | $\cup$、$\cap$、$-$ | `UNION`、`INTERSECT`、`EXCEPT` |
| 同表有多个逻辑角色吗 | $\rho$ | `AS` 别名 |
| 是否需要明确中间结果 | $\leftarrow$ | CTE、子查询、临时表 |

## 十二、总结

关系查询语言的核心不是记住一组希腊字母，而是建立一套可推导的查询思维：

- 关系代数是过程式语言，用一系列关系运算描述查询步骤；SQL 主要是声明式语言，描述结果条件并将执行策略交给优化器。
- 选择 $\sigma$ 筛选行，投影 $\pi$ 保留列；两者组合就是大量 SQL 查询的骨架。
- 笛卡尔积产生所有组合，连接 $\bowtie$ 则在其中保留满足关联条件的组合。
- 集合运算要求输入兼容；经典关系代数使用集合语义，SQL 需要留意 `DISTINCT` 与 `UNION ALL` 的多重集差异。
- 重命名 $\rho$ 用于消除歧义，尤其是同一张表参与自连接时。
- 等价查询可以有不同的执行成本；尽早筛选，再进行连接，是关系优化最基础也最有价值的原则之一。

当你下次写出一条 SQL，不妨先把它还原成“选择什么行、投影什么列、按何条件连接、是否比较两个集合”。查询语句的表面语法会变化，底层的关系运算却相当稳定。至于把一段本可清晰表达的查询堆成难以验证的嵌套，那并不叫高级，只是把问题藏了起来而已。
