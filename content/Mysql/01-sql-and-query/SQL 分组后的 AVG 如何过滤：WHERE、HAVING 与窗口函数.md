+++
date = '2026-10-26T14:00:00+08:00'
draft = false
title = 'SQL 分组后的 AVG 如何过滤：WHERE、HAVING 与窗口函数'
+++

在 `SELECT` 中写出 `AVG(score)` 后，常见的疑问是：能否直接在 `WHERE` 中按这个平均分过滤？结论并不复杂：**若条件依赖某一组算出的 `AVG`，应使用 `HAVING`，或者先在子查询 / CTE 中算出平均值再用外层 `WHERE` 过滤**。`WHERE` 只能处理分组形成之前的一行行原始数据。

这一区别不只是语法记忆。把条件放错位置，可能得到报错，也可能得到一条能执行却改变统计口径的 SQL；后一种尤其麻烦，因为数据库并不会替你指出题目已经被悄悄换掉。

## 先分清：筛行、算组、筛组

设 `exam_scores` 保存一次考试的成绩：

```sql
CREATE TABLE exam_scores (
  id BIGINT PRIMARY KEY,
  class_id BIGINT NOT NULL,
  student_id BIGINT NOT NULL,
  subject VARCHAR(30) NOT NULL,
  score DECIMAL(5, 2) NOT NULL
);
```

按班级求平均分时，逻辑上经历下面的阶段：

```text
原始行
  -> WHERE 过滤单行
  -> GROUP BY 按 class_id 分组
  -> AVG(score) 为每一组计算平均值
  -> HAVING 过滤整组
  -> SELECT 输出结果
```

因此，查询平均分不低于 80 分的班级应写为：

```sql
SELECT class_id,
       AVG(score) AS avg_score
FROM exam_scores
GROUP BY class_id
HAVING AVG(score) >= 80;
```

`HAVING AVG(score) >= 80` 的判断对象是“一个班级形成的一组行”。只有这一组先存在，`AVG(score)` 才有定义。

下面的写法在标准 SQL 语义下不成立：

```sql
SELECT class_id,
       AVG(score) AS avg_score
FROM exam_scores
WHERE AVG(score) >= 80
GROUP BY class_id;
```

执行 `WHERE` 时尚未分组，当前只有某一条成绩记录，不能询问“这一组的平均值”。MySQL 会报 `Invalid use of group function` 一类错误；不同产品的报错文字可以不同，原因相同。

## WHERE 也能和 AVG 同时出现，但它过滤的是样本

`WHERE` 不能引用本层分组平均值，并不表示含有 `AVG` 的查询不能写 `WHERE`。它很适合先限定参与统计的原始行。例如，只统计数学科目的有效成绩，再保留平均分至少为 80 的班级：

```sql
SELECT class_id,
       AVG(score) AS avg_score
FROM exam_scores
WHERE subject = '数学'
  AND score IS NOT NULL
GROUP BY class_id
HAVING AVG(score) >= 80;
```

这里两种过滤回答的是不同问题：

| 子句 | 问题 | 示例条件 | 影响 |
| --- | --- | --- | --- |
| `WHERE` | 哪些成绩记录参与平均？ | `subject = '数学'` | 改变平均值的样本 |
| `HAVING` | 算完平均后保留哪些班级？ | `AVG(score) >= 80` | 不改变已算出的平均值，只筛结果组 |

尤其不要把“排除低分”误写成“筛选平均分高的班级”：

```sql
-- 统计所有学生后的班级平均分，再选出平均分至少 80 的班级。
HAVING AVG(score) >= 80

-- 先丢弃所有低于 80 分的个人成绩，再计算剩余样本的平均分。
WHERE score >= 80
```

第二种写法的平均值通常更高，但它已经是在回答另一个问题。统计口径应由业务含义决定，不能因为语句短就随意替换。

## 聚合别名：MySQL 能用，不等于通用写法

在 MySQL 中，下列写法通常可运行：

```sql
SELECT class_id,
       AVG(score) AS avg_score
FROM exam_scores
GROUP BY class_id
HAVING avg_score >= 80;
```

这是 MySQL 对 `HAVING` 中选择列表别名的支持。为了明确表达依赖关系，也为了在其他数据库中更可移植，教学和通用 SQL 常直接重写聚合表达式：

```sql
HAVING AVG(score) >= 80
```

无论采用哪一种，`WHERE avg_score >= 80` 都不能工作：`WHERE` 既早于分组，也早于本层 `SELECT` 别名的产生。

## 想用 WHERE 筛平均值：先让平均值成为一列

有时后续还要连接、分页、按平均分区间筛选，或者希望在外层统一处理多个派生指标。这时可以在子查询或 CTE 中先完成分组；外层面对的是已经有 `avg_score` 列的结果表，因此自然可以使用 `WHERE`。

```sql
WITH class_averages AS (
  SELECT class_id,
         AVG(score) AS avg_score,
         COUNT(*) AS student_count
  FROM exam_scores
  WHERE subject = '数学'
  GROUP BY class_id
)
SELECT class_id,
       avg_score,
       student_count
FROM class_averages
WHERE avg_score >= 80
  AND student_count >= 20
ORDER BY avg_score DESC, class_id;
```

这并不是“绕过了 `HAVING`”。内层仍在分组后生成指标；只是外层不再处理原始成绩，而是在处理“一班一行”的派生结果。用派生表也可以得到相同语义：

```sql
SELECT *
FROM (
  SELECT class_id, AVG(score) AS avg_score
  FROM exam_scores
  GROUP BY class_id
) AS class_averages
WHERE avg_score >= 80;
```

当筛选条件只涉及本层聚合时，直接用 `HAVING` 往往更简洁；当要复用、组合或继续处理聚合结果时，CTE / 子查询的层次更清楚。

## 要保留每个学生明细：窗口函数不是 HAVING 的替代品

`GROUP BY` 会把多条学生记录压缩成一条班级记录。如果需求是“保留每位学生的成绩，并标出其班级平均分，只看班均分至少 80 的学生”，可用窗口函数：

```sql
SELECT class_id,
       student_id,
       score,
       avg_score
FROM (
  SELECT class_id,
         student_id,
         score,
         AVG(score) OVER (PARTITION BY class_id) AS avg_score
  FROM exam_scores
  WHERE subject = '数学'
) AS scored
WHERE avg_score >= 80
ORDER BY class_id, student_id;
```

窗口函数在不合并行的前提下计算分区统计值，但在同一查询层中它同样不能直接放进 `WHERE`。原因依旧是逻辑阶段：外层查询让窗口结果先成为普通列，再用 `WHERE` 筛选。某些数据库提供 `QUALIFY` 子句，MySQL 8 没有这一语法；不要把其他方言的示例直接复制过来。

## 性能与正确性的共同原则

能在 `WHERE` 中表达的**行级条件**，应尽量放在 `WHERE` 中。例如日期范围、状态、租户和学科等，越早缩小输入行，后续分组通常越轻。反过来，依赖 `COUNT`、`SUM`、`AVG`、`MIN`、`MAX` 的**组级条件**必须留给 `HAVING`。

不过“尽量早过滤”不能凌驾于业务语义。`WHERE score >= 60` 会改变平均分的分母和分子；若报表定义要求所有已录入成绩都参与平均，它就不应存在。先写清指标口径，再决定条件位置，这比背诵执行顺序可靠得多。

## 小结

- `WHERE` 在分组前筛选原始行，不能直接使用 `AVG()` 等分组聚合结果。
- `HAVING` 在分组后筛选组；“平均值达到阈值”的条件应写为 `HAVING AVG(...) ...`。
- 同一查询可以同时使用二者：`WHERE` 确定统计样本，`HAVING` 确定保留哪些统计结果。
- 若要在 `WHERE` 中筛平均值，先在子查询或 CTE 中把平均值计算成列。
- 若需保留明细行，使用窗口函数，并在外层筛选窗口计算结果。

有关聚合函数、`NULL` 与逻辑执行顺序的基础，可继续阅读 [SQL 的执行顺序](./SQL%20的执行顺序.md) 与 [SQL 单表查询、聚合与分组：从行筛选到统计结论](../database-system-course/05-sql-query-and-aggregation.md)。
