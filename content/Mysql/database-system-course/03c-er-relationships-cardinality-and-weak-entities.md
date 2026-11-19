+++
date = '2026-11-19T10:00:00+08:00'
draft = false
title = 'E-R 模型中的联系、关系属性、基数约束与参与约束'
+++

E-R 图不只是把表画成矩形、再连几根线。它要说明业务事实：哪些对象发生关联、关联本身有没有信息、每一端最多能关联多少对象，以及对象是否必须参加这项关联。若只写“教师—学生”，却没有说明学生是否必须有导师、导师能否指导多人，这张图几乎没有约束力。

本文使用 Chen E-R 图的概念和符号，解释联系集、联系属性、递归联系、箭头、单线、双线和最小—最大基数。弱实体的完整键和关系模式映射会在后续关系模式教程中统一讨论；这里先把“关系到底表达什么”读准确。

## 一、实体、实体集、联系与联系集

**实体（entity）**是一个可区分的具体对象，例如编号为 `44553` 的学生 Peltier。**实体集（entity set）**是同类实体的集合，例如 `student` 表示所有学生，`instructor` 表示所有教师。Chen 图中的矩形表示实体集，不是某一行具体记录。

一条具体的**联系（relationship）**是若干实体之间的一次关联：

```text
student(44553, Peltier) ── advisor ── instructor(22222, Einstein)
```

所有同类联系构成一个**联系集（relationship set）**。因此 `advisor` 表示所有学生和教师之间的指导关联，而不是某个单独学生、某位教师，或将来 SQL 中必然存在的一张表。

| 层次 | 含义 | 示例 |
| --- | --- | --- |
| 实体 | 一个具体对象 | 学生 `44553` |
| 实体集 | 同类对象的集合 | `student` |
| 联系 | 一次具体关联 | Peltier 由 Einstein 指导 |
| 联系集 | 同一类关联的集合 | `advisor` |

二元联系集可写成：

```text
advisor ⊆ student × instructor
```

其中 `(44553, 22222) ∈ advisor` 表示学生 `44553` 与教师 `22222` 之间存在指导联系。一般的 n 元联系集是多个实体集笛卡尔积的子集：

```text
R ⊆ E1 × E2 × ... × En
```

图上实体摆在左边还是右边不决定元组的语义；参与位置和角色才决定每个值的含义。

## 二、联系可以拥有属性

实体属性描述对象自身，例如 `instructor.name`、`instructor.salary`、`student.name`。但有些值描述的是实体之间发生的事，这时它应属于联系集。

教师与学生的 `advisor` 联系可拥有 `date`：

```text
instructor ── advisor(date) ── student
```

它表示“某教师从某日期开始担任某学生的导师”。`date` 不应直接属于 `instructor`，因为同一教师指导不同学生的开始日期可以不同；通常也不应直接属于 `student`，因为学生可能更换导师。它依赖“教师 + 学生”的组合。

同理，成绩 `grade` 属于学生选修教学班的联系：

```text
student ── takes(grade) ── section
```

它既不是 `student.grade`，因为一名学生有多门课；也不是 `section.grade`，因为同一班中不同学生的成绩不同。

判断属性归属时，可以问：

> 确定这个值时，是否必须同时知道联系两端或多端的参与对象？

若答案是“必须”，它通常是联系属性。

### 联系属性与外键列的区别

在概念 E-R 图中，`advisor` 是菱形，`date` 连到菱形。若业务规则是“一位教师可指导多名学生，而学生至多一位当前导师”，在 SQL 中可能实现为：

```sql
CREATE TABLE student (
  id BIGINT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  advisor_id BIGINT,
  advisor_date DATE,
  FOREIGN KEY (advisor_id) REFERENCES instructor(id)
);
```

`advisor_id` 是实现联系的外键，`advisor_date` 是被放到多端表中的联系属性；它们并不因此变成学生天生固有的事实。**概念归属**与**物理存储位置**不是同一个问题。

## 三、角色与递归联系

同一个实体集可以以不同角色参加同一个联系，这称为**递归联系（recursive relationship）**或自关联。课程先修关系是典型例子：

```text
course ── prerequisite ── course
```

两端都是 `course`，但角色不同：

- `course_id`：当前课程，即需要先修知识的课程。
- `prereq_id`：先修课程，即应先学习的课程。

`(CS201, CS101)` 表示“`CS201` 的先修课程是 `CS101`”，不表示反过来。转换为关系模式时，应使用两个语义清楚、都引用 `course` 的外键：

```sql
CREATE TABLE prerequisite (
  course_id VARCHAR(20) NOT NULL,
  prereq_id VARCHAR(20) NOT NULL,
  PRIMARY KEY (course_id, prereq_id),
  FOREIGN KEY (course_id) REFERENCES course(course_id),
  FOREIGN KEY (prereq_id) REFERENCES course(course_id),
  CHECK (course_id <> prereq_id)
);
```

角色名不是注释，而是防止语义倒置的模型组成部分。

## 四、箭头表示最大基数

在本教材的 Chen 记法中，从联系菱形指向实体集的**箭头**表示该端“至多一个”；普通无箭头线表示该端可以是“多个”。正确的阅读规则是：

> 固定关系中其他参与实体后，箭头所指向的实体至多一个。

### 一对一：两边都有箭头

```text
[instructor] ← <advisor> → [student]
```

给定学生至多一位教师，给定教师也至多一名学生。因此是 `1:1`。注意“至多一个”不是“必须有一个”。

### 一对多：箭头指向“一”端

```text
[instructor] ← <advisor> ── [student]
```

箭头指向 `instructor`，表示给定学生至多一位教师；一位教师可关联多名学生。因此：

```text
instructor 1 : N student
```

箭头不是数据流向，也不是“教师主动指向学生”；它只表达联系结果的最大数量。

### 多对一：箭头指向另一端

```text
[instructor] ── <advisor> → [student]
```

这表示一位教师至多关联一名学生，而一名学生可关联多位教师，即 `N:1`。例子的业务名称不常见，但符号规则完全相同。

### 多对多：两端都没有箭头

```text
[instructor] ── <advisor> ── [student]
```

两侧都可关联多个对方实体，即 `M:N`。关系数据库中通常需要关联表：

```sql
CREATE TABLE advisor (
  instructor_id BIGINT NOT NULL,
  student_id BIGINT NOT NULL,
  date DATE,
  PRIMARY KEY (instructor_id, student_id),
  FOREIGN KEY (instructor_id) REFERENCES instructor(id),
  FOREIGN KEY (student_id) REFERENCES student(id)
);
```

## 五、单线和双线表示最小参与次数

箭头回答“至多几个”，而连接实体和联系的单线、双线回答“至少几个”。这是两个相互独立的维度。

| 线条 | 名称 | 语义 | 最小参与次数 |
| --- | --- | --- | --- |
| 单线 | 部分参与 | 允许该实体不参与联系 | `0` |
| 双线 | 完全参与 | 每个实体至少参加一次联系 | `1` |

若 `student` 到 `advisor` 为双线，`instructor` 到 `advisor` 是单线，且箭头指向 `instructor`：

```text
[instructor] ← <advisor> ══ [student]
```

应逐项读为：

- 箭头指向教师：每位学生最多一位导师。
- 学生侧双线：每位学生至少一位导师。
- 教师侧单线：教师可以暂时没有学生。
- 教师侧无箭头：一位教师可以指导多名学生。

四项合起来才是：

```text
一位教师可以指导 0 名或多名学生；
每位学生必须且只能有 1 位教师。
```

只写 `1:N` 只能说明最大数量，不能推出“每名学生一定已被分配导师”。

## 六、用 `l..h` 统一表示最小和最大基数

更精确的写法是在联系端标注 `l..h`：`l` 是最小参与次数，`h` 是最大参与次数。

| 标注 | 语义 |
| --- | --- |
| `0..1` | 可不参加，最多一次 |
| `1..1` | 必须参加，且只能一次 |
| `0..*` | 可不参加，次数不限 |
| `1..*` | 至少一次，次数不限 |
| `2..5` | 至少两次，最多五次 |

前面的导师规则可写成：

```text
instructor 0..* ── advisor ── 1..1 student
```

它与“教师侧单线且无箭头、学生侧双线且箭头指向教师”的语义相同。实际建模时应选择一种主要记法并保持一致；不要一部分联系只写 `1:N`，另一部分又只画箭头却遗漏参与约束。

## 七、何时应把联系升级为独立实体

普通 `advisor(date)` 默认适合表达当前或单一的导师关联。若要保存多次分配历史：

```text
学生 A：
  2024-09-01 起由教师 X 指导
  2025-07-01 起由教师 Y 指导
  2026-03-01 又由教师 X 指导
```

同一师生组合可能发生多次独立任命，单纯的 `advisor(instructor_id, student_id, date)` 不再足够。应将“导师任命”建模为独立事件实体：

```text
ADVISOR_ASSIGNMENT
  assignment_id
  start_date
  end_date
  status
```

它分别关联教师和学生。这样关联本身可以拥有状态、结束时间、审批信息和稳定身份，也能保存历史。判断标准不是属性数量，而是该关联是否可重复发生、是否有独立生命周期，或是否需要被其他事实引用。

## 八、常见误解

### 把箭头当作流程方向

Chen 图中箭头表达最大基数，不表达控制流、数据流或 UML 导航方向。

### 把双线理解为一对一

双线表示最小值为 1；一对一由两端箭头表示最大值均为 1。两种线解决的不是同一个问题。

### 把联系属性放进任意一端实体

`grade`、`advisor_date` 依赖参与实体组合。即使 SQL 实现时它们随着外键放到某一端，概念模型中仍应先识别其联系属性语义。

### 用当前状态覆盖历史事实

若关联会反复建立、结束并被审计，普通外键只能表示当前状态；应改为带独立键的事件或关联实体。

## 小结

- 联系集描述同类实体关联的集合；其中一条具体配对是联系实例。
- 必须同时知道多个参与实体才能确定的值，应属于联系。
- 箭头表示最大值为 1；无箭头表示允许多个。
- 单线表示最小值为 0；双线表示最小值为 1。
- `l..h` 能一次表达最小和最大参与次数。
- 可反复发生、需要保存状态或历史的关联，应考虑提升为独立实体。
