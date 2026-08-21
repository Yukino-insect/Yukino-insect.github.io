+++
date = '2025-09-11T21:12:53+08:00'
draft = false
title = 'SQL 的执行顺序'
+++

SQL 的书写顺序和逻辑执行顺序并不完全一样。理解这件事，对 `JOIN`、`WHERE`、`GROUP BY`、`HAVING`、`ORDER BY` 的使用很有帮助。

## 一、SELECT 的书写顺序

常见写法：

```sql
select distinct ...
from ...
join ... on ...
where ...
group by ...
having ...
order by ...
limit ...
```

这是写给人和 SQL 解析器看的顺序。

## 二、SELECT 的逻辑执行顺序

逻辑上可以这样理解：

1. `FROM`：确定数据来源。
2. `JOIN`：执行表连接。
3. `ON`：应用连接条件。
4. `WHERE`：过滤连接后的行。
5. `GROUP BY`：分组。
6. 聚合函数：计算每组聚合值。
7. `HAVING`：过滤分组后的结果。
8. `SELECT`：计算返回列和表达式。
9. `DISTINCT`：去重。
10. `ORDER BY`：排序。
11. `LIMIT` / `OFFSET`：截取结果。

这只是逻辑顺序，不代表数据库物理执行时一定按这个顺序一步一步做。优化器会在保证语义一致的前提下重排执行计划。

## 三、为什么 WHERE 不能直接用 SELECT 别名

例如：

```sql
select amount * 100 as amount_cent
from orders
where amount_cent > 1000;
```

`WHERE` 逻辑上早于 `SELECT`，所以此时 `amount_cent` 还没生成。通常要写成：

```sql
select amount * 100 as amount_cent
from orders
where amount * 100 > 1000;
```

或者使用子查询：

```sql
select *
from (
  select amount * 100 as amount_cent
  from orders
) t
where amount_cent > 1000;
```

## 四、WHERE 和 HAVING

`WHERE` 过滤分组前的行：

```sql
select user_id, count(*) as total
from orders
where status = 'PAID'
group by user_id;
```

`HAVING` 过滤分组后的结果：

```sql
select user_id, count(*) as total
from orders
group by user_id
having count(*) > 10;
```

能写在 `WHERE` 的条件，不要为了省事写到 `HAVING`。先过滤掉无关行，再分组，通常更高效。

## 五、ON 和 WHERE

`ON` 用于连接匹配，`WHERE` 用于结果过滤。

在 `LEFT JOIN` 中尤其要注意：

```sql
select d.id, s.name
from dept d
left join station s
  on s.dept_id = d.id
 and s.status = 1;
```

这会保留全部 `dept`，只匹配状态为 1 的 `station`。

如果写成：

```sql
select d.id, s.name
from dept d
left join station s on s.dept_id = d.id
where s.status = 1;
```

右表匹配不到的行会被 `WHERE` 过滤掉，`LEFT JOIN` 可能退化成类似 `INNER JOIN` 的效果。

更完整的说明可以看 [SQL JOIN 与 ON、WHERE 的区别](./SQL%20JOIN%20与%20ON、WHERE%20的区别.md)。

## 六、MySQL 的架构分层

MySQL 大致可以分成：

```text
客户端
  |
连接层
  |
Server 层
  |
存储引擎层
```

Server 层负责 SQL 解析、优化、执行调度、内置函数、权限等。存储引擎层负责真正的数据读写，例如 InnoDB 的索引、事务、锁、redo log、undo log、buffer pool。

一条 SQL 的大致过程：

1. 客户端通过驱动连接 MySQL。
2. MySQL 校验权限和语法。
3. 解析器生成语法结构。
4. 优化器选择执行计划。
5. 执行器调用存储引擎接口。
6. 存储引擎读取或修改数据。
7. 返回结果给客户端。

## 七、连接池的作用

Java 应用访问 MySQL 通常通过 JDBC 驱动建立 TCP 连接。每次请求都新建和销毁连接会很浪费，所以应用一般使用连接池。

连接池负责维护一批可复用连接：

```text
应用线程 -> 连接池借连接 -> 执行 SQL -> 归还连接
```

常见连接池有 HikariCP、Druid、DBCP、C3P0。现在 Spring Boot 默认常用 HikariCP。

事务和连接池关系很密切：事务期间连接不能随意换，否则同一业务方法里的 SQL 就可能不在同一个事务里。

## 八、InnoDB 更新的大致过程

一次更新大致涉及：

1. 从 buffer pool 查找数据页，找不到就从磁盘加载。
2. 生成 undo log，用于回滚和 MVCC。
3. 在内存页中修改数据。
4. 写 redo log buffer。
5. 提交时按配置刷 redo log，保证崩溃恢复。
6. 后续由后台线程把脏页刷回磁盘。

简化理解：

```text
undo log 保证能回滚
redo log 保证提交后能恢复
buffer pool 减少磁盘读写
```

数据页不是每次提交都立刻完整刷盘。MySQL 依赖 redo log 在崩溃后恢复已提交事务。

## 九、总结

SQL 逻辑顺序帮助我们理解语义，MySQL 执行链路帮助我们理解性能。

写 SQL 时先保证语义正确：`ON`、`WHERE`、`HAVING` 各在其位。排查性能时再看执行计划：优化器到底用了哪个索引、扫描了多少行、是否排序、是否临时表。
