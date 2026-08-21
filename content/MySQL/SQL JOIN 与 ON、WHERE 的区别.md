+++
date = '2026-03-01T15:43:14+08:00'
draft = false
title = 'SQL JOIN 与 ON、WHERE 的区别'
+++

写多表查询时，最容易混淆的是三件事：`FROM` 是数据来源，`JOIN` 是表之间的连接方式，`ON` 和 `WHERE` 分别控制连接匹配和最终过滤。

如果只记一句话：**`ON` 决定右表数据如何匹配到左表，`WHERE` 决定连接后的结果哪些行最终留下。**

## 一、FROM 和 JOIN

`FROM` 指定查询从哪里取数据。只有一张表时，写法很直接：

```sql
select *
from user_role;
```

多表查询时，推荐显式使用 `JOIN`，把连接关系写清楚：

```sql
select ur.*
from user_role ur
join sys_user u on u.id = ur.user_id;
```

早期也能看到逗号连接：

```sql
select *
from user_role ur, sys_user u
where u.id = ur.user_id;
```

这等价于内连接，但可读性差，也容易把连接条件和过滤条件混在一起。项目代码里更推荐显式 `JOIN ... ON ...`。

## 二、INNER JOIN 和 LEFT JOIN

`INNER JOIN` 只保留两边都匹配成功的行：

```sql
select a.id, b.name
from a
inner join b on b.a_id = a.id;
```

`LEFT JOIN` 会保留左表的全部行。右表匹配不到时，右表字段补 `NULL`：

```sql
select a.id, b.name
from a
left join b on b.a_id = a.id;
```

假设数据如下：

| a.id |
| ---- |
| 1    |
| 2    |

| b.a_id | b.name |
| ------ | ------ |
| 1      | Tom    |

`INNER JOIN` 结果只有 `a.id = 1`。`LEFT JOIN` 结果会保留 `a.id = 2`，只是 `b.name` 为 `NULL`。

## 三、ON 和 WHERE 的区别

`ON` 是连接条件，决定两张表如何匹配：

```sql
from dept d
left join station s on s.dept_id = d.id
```

`WHERE` 是结果过滤条件，在连接完成后过滤整行结果：

```sql
where d.status = 1
```

在 `INNER JOIN` 中，很多条件写在 `ON` 或 `WHERE` 里结果可能一样，优化器也常能改写。但在 `LEFT JOIN` 中，二者差异非常关键。

## 四、LEFT JOIN 下条件位置的影响

把右表条件写在 `ON` 中：

```sql
select d.id, s.name
from dept d
left join station s
  on s.dept_id = d.id
 and s.addvcd like concat('%', #{addvcd}, '%');
```

含义是：左表 `dept` 仍然全部保留，只是右表 `station` 只匹配满足行政区划条件的行。匹配不到时，`s.*` 为 `NULL`。

把同一个右表条件写在 `WHERE` 中：

```sql
select d.id, s.name
from dept d
left join station s on s.dept_id = d.id
where s.addvcd like concat('%', #{addvcd}, '%');
```

含义就变了：连接完成后，`s.addvcd` 为 `NULL` 的行会被过滤掉。这样左表中没有匹配右表的行也会消失，`LEFT JOIN` 实际上接近退化成 `INNER JOIN`。

所以判断条件放哪里，要先问业务要什么：

1. 想限制右表如何匹配，同时保留左表：写在 `ON`。
2. 想过滤最终结果，右表不满足就整行不要：写在 `WHERE`。
3. 左表自己的过滤条件通常写在 `WHERE`，例如 `d.status = 1`。

## 五、WHERE 为什么能写 JOIN 表字段

因为 SQL 的逻辑执行顺序里，`WHERE` 发生在 `FROM` 和 `JOIN` 之后。此时连接结果已经形成，结果集中已经有右表字段，所以当然可以写：

```sql
where s.addvcd like concat('%', #{addvcd}, '%')
```

问题不在于“能不能写”，而在于“写在这里会不会改变外连接语义”。

## 六、ON 里能不能写非等值条件

可以。`ON` 不限制只能写等值条件，也可以写范围、`LIKE`、多个条件组合：

```sql
left join station s
  on s.dept_id = d.id
 and s.name like concat('%', #{keyword}, '%')
```

只是要注意，`LIKE '%xxx%'` 这类前置模糊匹配通常很难利用普通 B+ 树索引，数据量大时要评估性能。

## 七、总结

`JOIN` 负责把表连接起来，`ON` 控制连接匹配，`WHERE` 控制最终过滤。

对 `LEFT JOIN` 来说，右表条件写在 `ON` 里通常表示“右表不匹配也保留左表”；写在 `WHERE` 里通常表示“右表不匹配就过滤整行”。这正是很多查询结果“莫名其妙少了”的原因。
