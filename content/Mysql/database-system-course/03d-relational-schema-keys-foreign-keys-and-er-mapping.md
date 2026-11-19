+++
date = '2026-11-19T11:00:00+08:00'
draft = false
title = '从 E-R 图到关系模型：关系模式、主键、外键与弱实体映射'
+++

E-R 图回答“系统中有哪些对象、它们如何关联”；关系模型回答“这些事实最终怎样用关系、键和约束保存”。两者描述同一业务世界，却处在不同抽象层次。把 ER 图里的每根连线机械抄成一个字段，或把 SQL 外键当作概念 ER 图中的普通属性，都会造成重复或丢失语义。

本文先解释关系模式和关系实例，再区分超键、候选键、主键与外键，最后给出常见 E-R 结构的转换规则。重点包含两个容易混淆的问题：外键应在哪个层次显示，以及弱实体如何在关系模型中获得完整主键。

## 一、关系模式不是表中的当前数据

数据库模式（database schema）是数据库的逻辑设计；数据库实例（database instance）则是某个时刻实际保存的数据快照。

例如：

```text
DEPARTMENT(dept_name, building, budget)
```

描述的是一个**关系模式（relation schema）**：关系名为 `DEPARTMENT`，它有 `dept_name`、`building`、`budget` 三个属性。严格说，每个属性还应有域（domain），即允许取值的集合，例如文本、日期、金额、状态代码及其范围。

某个时刻的**关系实例（relation instance）**可能是：

| dept_name | building | budget |
| --- | --- | ---: |
| Comp. Sci. | Taylor | 100000.00 |
| Finance | Painter | 120000.00 |

其中每一行叫元组（tuple）。关系模型从数学上把关系实例看作 n 元组的集合：

```text
r ⊆ D1 × D2 × ... × Dn
```

`D1` 到 `Dn` 是各属性的域。集合语义意味着元组不重复、没有天然顺序；SQL 表在工程上还涉及 `NULL`、重复查询结果、存储顺序等实现细节，但并不改变“模式定义结构、实例保存当前数据”这一核心区分。

## 二、键：如何从属性值唯一确定一行

设有关系模式：

```text
DOCTOR(doctor_id, doctor_name, department_id, birth_date)
```

键讨论的不是“当前恰好没有重名”，而是业务规则是否保证在**所有合法实例**中能够唯一标识元组。

| 概念 | 定义 | 示例 |
| --- | --- | --- |
| 超键（superkey） | 能唯一确定一条元组的属性集合 | `{doctor_id}`、`{doctor_id, doctor_name}` |
| 候选键（candidate key） | 最小超键；去掉任意属性就不再唯一 | `{doctor_id}` |
| 主键（primary key） | 从候选键中选作主要标识的一组 | `doctor_id` |

若 `doctor_id` 唯一，则 `{doctor_id}` 已是候选键。再加上 `doctor_name` 后仍能唯一定位一行，所以是超键；但姓名是冗余属性，因此不是候选键。

“姓名加科室”是否能成为候选键，不能由字段名想当然地决定。只有业务规则明确保证“同一科室不可能有两位同名医生”时，`{doctor_name, department_id}` 才是候选键。实际系统通常不应依赖这种脆弱假设。

主键应稳定、唯一、非空。它被其他表引用后，频繁修改会迫使所有引用值同步变化。自然编号、工号和代理键都可以使用，关键在于唯一性和稳定性。

### 联合主键

主键可以由多个属性组成。例如：

```text
TAKES(student_id, section_id, grade)
PK: (student_id, section_id)
```

`student_id` 不能单独标识选课记录，一名学生可以选多门课；`section_id` 也不能单独标识，一门课有多个学生。二者组合才是最小标识。

## 三、外键：保证引用的对象真实存在

外键约束（foreign-key constraint）表示：一个关系中的属性值必须引用另一关系中已有的键值。

```text
DEPARTMENT(department_id, department_name)
DOCTOR(doctor_id, department_id, doctor_name)

DOCTOR.department_id → DEPARTMENT.department_id
```

`DOCTOR` 是**引用关系**，`DEPARTMENT` 是**被引用关系**。任何医生记录中填写的部门编号，都必须在 `DEPARTMENT` 中找到对应部门。

在 SQL 中：

```sql
CREATE TABLE department (
  department_id BIGINT PRIMARY KEY,
  department_name VARCHAR(100) NOT NULL
);

CREATE TABLE doctor (
  doctor_id BIGINT PRIMARY KEY,
  department_id BIGINT NOT NULL,
  doctor_name VARCHAR(100) NOT NULL,
  FOREIGN KEY (department_id)
    REFERENCES department(department_id)
);
```

`FOREIGN KEY` 保证“引用的部门存在”；`NOT NULL` 额外保证“每位医生必须填写一个部门”。若去掉 `NOT NULL`，SQL 通常允许医生暂时没有部门，但非空部门编号仍必须有效。

外键可以引用复合键或其他具有唯一性的候选键；引用列数、顺序和对应域必须匹配。

## 四、纸面关系模式中怎样标记键

最简模式：

```text
DOCTOR(doctor_id, department_id, doctor_name, birth_date)
```

只列出了属性，不能让读者可靠地推断主键和外键。作业和设计文档应明确写出约束。下面两种写法都可使用，但一篇文档内应保持一致。

### 使用 `PK`、`FK` 标签

```text
DEPARTMENT(
  department_id PK,
  department_name
)

DOCTOR(
  doctor_id PK,
  department_id FK NOT NULL → DEPARTMENT(department_id),
  doctor_name,
  birth_date
)
```

这是最清楚的写法。既然已经标出 `PK`，就不必再给该属性画下划线；同一属性若既是主键又是外键，应同时标记。

### 使用下划线表示主键

传统教材常把主键属性加实线下划线：

```text
DEPARTMENT(
  _department_id_,
  department_name
)

DOCTOR(
  _doctor_id_,
  department_id,
  doctor_name,
  birth_date
)

DOCTOR.department_id → DEPARTMENT.department_id
```

这种写法中，外键约束应另行写出。外键不需要因其“外键身份”而加下划线；只有它同时参与本关系主键时才加主键下划线。

### 概念 ER 图与逻辑表结构图的差别

在 Chen 概念 ER 图中，应画：

```text
DEPARTMENT ── EMPLOYS ── DOCTOR
```

并标注基数和参与约束。此时通常**不**把 `department_id` 当作 `DOCTOR` 的普通属性画出来，因为该外键尚未出现；它是将联系映射到关系模型之后的实现结果。

在逻辑 ERD、物理数据库图或关系模式中，则应显示：

```text
DOCTOR.department_id FK → DEPARTMENT.department_id
```

概念图若同时画联系和同一个外键普通属性，会重复表达业务事实；表结构图若不显示外键，则丢失参照完整性规则。

## 五、从常见 E-R 联系映射为关系模式

### 强实体

每个强实体集通常转换为一个关系，实体键成为主键：

```text
DEPARTMENT(department_id PK, department_name)
DOCTOR(doctor_id PK, doctor_name)
```

### 一对多联系

对于：

```text
DEPARTMENT 1 ── EMPLOYS ── N DOCTOR
```

将 `DEPARTMENT` 的主键放进多端 `DOCTOR`：

```text
DOCTOR(
  doctor_id PK,
  department_id FK → DEPARTMENT(department_id),
  doctor_name
)
```

若医生必须属于科室，`department_id` 为 `NOT NULL`；若可暂时不分配科室，它可以为空。联系属性若只描述当前一对多联系，例如“加入当前科室的日期”，也可与外键一起放在多端。若需要科室调动历史，则应建立独立任职记录。

### 一对一联系

一对一联系可以选择任意一端保存外键，但必须增加唯一性：

```text
PASSPORT(
  passport_no PK,
  person_id FK UNIQUE → PERSON(person_id)
)
```

`UNIQUE` 不可省略。没有它，多本护照可引用同一个人，关系会退化为一对多。应优先把外键放在完全参与、空值更少或业务上更依赖另一方的一侧。

### 多对多联系

对于：

```text
STUDENT M ── TAKES(grade) ── N SECTION
```

建立独立关系：

```text
TAKES(
  student_id PK, FK → STUDENT(student_id),
  section_id PK, FK → SECTION(section_id),
  grade
)
```

两个外键共同组成主键；`grade` 是原来联系 `TAKES` 的属性。不要把它放到 `STUDENT` 或 `SECTION`。

### 多值属性

若 `PATIENT` 的 `phone_number` 是多值属性，应转换为：

```text
PATIENT_PHONE(
  patient_id PK, FK → PATIENT(patient_id),
  phone_number PK
)
```

这避免 `phone_1`、`phone_2`、`phone_3` 这种固定上限设计。电话号码应使用字符域，因为它可能含国家码、前导零、分隔符和分机号，不是要参与算术的数值。

## 六、弱实体：完整主键必须包含拥有者键

弱实体不是“主键有好几列”的同义词。严格的 Chen 定义是：

> 弱实体无法仅用自身属性在全局范围内唯一标识，必须借用标识强实体的主键，并结合自己的部分键获得完整身份。

课程班次是常见例子：

```text
COURSE(course_id)
SECTION(sec_id, semester, year)
```

`(sec_id, semester, year)` 只能在同一门课程内部区分班次。不同课程都可能存在“2026 年秋季 1 班”，所以完整键为：

```text
(course_id, sec_id, semester, year)
```

在 Chen 图中：

- `SECTION` 画双矩形。
- `COURSE` 与 `SECTION` 之间的识别联系画双菱形。
- `SECTION` 到该联系画双线，表示每个班次必须有所属课程。
- `sec_id`、`semester`、`year` 用虚线下划线表示部分键。
- 标识联系指向 `COURSE`，表示每个 `SECTION` 至多属于一门 `COURSE`。

映射成关系模型后，没有“双矩形”的特殊语法，只有清晰的主键与外键：

```text
COURSE(
  course_id PK,
  title,
  credits
)

SECTION(
  course_id PK, FK → COURSE(course_id),
  sec_id PK,
  semester PK,
  year PK,
  building,
  room_number
)
```

`course_id` 同时是 `SECTION` 对 `COURSE` 的外键和 `SECTION` 联合主键的一部分。这不是重复保存；它同时表达“属于哪个课程”和“如何唯一标识该班次”。

### 弱实体可以有自己的主键吗

弱实体可以有自己的**部分键**，但不能有一个无需拥有者键就能全局唯一识别它的完整候选键。若为每个班次另发放全局唯一的 `section_id`，并以它作为候选键：

```text
SECTION(section_id PK, course_id FK, sec_id, semester, year)
```

那么按严格的身份识别依赖定义，`SECTION` 已是强实体；它仍可要求 `course_id NOT NULL`，即存在上依赖课程，但不再依靠课程主键来证明“自己是谁”。

工程中可以为依赖对象加入代理键以方便引用；这不妨碍业务上称它为从属对象。但讨论 Chen 弱实体时，应以“完整身份是否必须包含拥有者键”为判断标准。

## 七、联系属性、关系主键与历史事件

设 `ADVISOR(instructor_id, student_id, date)` 是普通导师联系。若模型允许每对教师和学生只存在一条当前指导关系，则 `(instructor_id, student_id)` 足以标识关系，`date` 是描述属性而非默认主键的一部分。

若系统需要记录同一师生多次建立、结束又建立指导关系，应该把“导师任命”升级为事件实体：

```text
ADVISOR_ASSIGNMENT(
  assignment_id PK,
  instructor_id FK → INSTRUCTOR(instructor_id),
  student_id FK → STUDENT(student_id),
  start_date,
  end_date,
  status
)
```

不要因为看到 `date` 就机械地把它塞进普通联系的主键。关键问题是：是否存在多个可独立存在、可被引用、具有历史状态的任命事件。

## 八、转换后的约束检查表

完成从 E-R 图到关系模式的转换后，至少逐项核对：

- 每个强实体是否有稳定的主键？
- 每个一对多联系是否在多端保存了一端键作为外键？
- 每个多对多联系是否建立了独立关联关系，并保存联系属性？
- 每个多值属性是否已拆为独立关系？
- 每个弱实体是否把拥有者键同时作为外键和联合主键的一部分？
- 必须参加联系的一端，是否通过 `NOT NULL` 或其他约束表达？
- 最大值为 1 的约束，是否在需要时使用 `UNIQUE` 或合适的主键表达？
- 是否存在时间重叠、数量上限等跨行规则，需要事务、触发器或服务层校验？

## 小结

- 关系模式定义属性和域，关系实例是某个时刻的元组集合。
- 超键能唯一标识元组；候选键是最小超键；主键是选定的候选键。
- 外键保证引用值存在；若关系必须存在，还需配合 `NOT NULL`。
- 概念 ER 图用联系表达关联；逻辑或物理关系模型应明确显示外键。
- 一对多关系通常在多端放外键，多对多关系使用关联表，多值属性使用独立关系。
- 弱实体的完整主键由拥有者主键和部分键组成；在关系模型中，拥有者键同时是外键和联合主键的一部分。
