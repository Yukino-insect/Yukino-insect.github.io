+++
date = '2025-09-27T10:27:15+08:00'
draft = false
title = '数据库'
+++

数据库用于持久化管理数据。按数据模型粗略划分，可以分为关系型数据库和非关系型数据库。

关系型数据库使用表、行、列组织数据，并通过 SQL 操作数据。常见产品包括 MySQL、PostgreSQL、Oracle、SQL Server。

非关系型数据库不一定使用表结构，常见模型包括键值、文档、列族、图。Redis 常被用作键值数据库或缓存，MongoDB 常被用作文档数据库。

这篇是数据库和 MySQL 的入口笔记，重点放在 SQL 基础、表设计和 MySQL 常见组件。更深入的索引、事务、复制、排序问题放在独立文章里。

## 一、关系型数据库的核心概念

关系型数据库最常见的对象有：

| 对象 | 说明 |
| ---- | ---- |
| database | 数据库，MySQL 中常作为逻辑命名空间 |
| table | 表，存储同一类数据 |
| row | 行，一条记录 |
| column | 列，一个字段 |
| primary key | 主键，唯一标识一行 |
| index | 索引，加速查询或保证唯一性 |
| constraint | 约束，保证数据规则 |
| transaction | 事务，保证一组操作的提交或回滚 |

关系型数据库适合结构明确、关系清晰、需要事务和强约束的数据。

## 二、数据库三范式

三范式用于减少冗余、提高一致性。它不是绝对命令，而是设计表结构时的基本约束思路。

## 三、第一范式

第一范式要求每一列都是不可再分的原子值。

不推荐：

```text
address = '中国北京'
```

如果业务经常按国家、城市查询，更适合拆成：

```text
country = '中国'
city = '北京'
```

是否拆分取决于业务是否需要独立查询和维护这些信息。范式不是为了让表看起来工整，而是为了让数据语义清楚。

## 四、第二范式

第二范式要求在满足第一范式的基础上，非主键字段必须完全依赖于整个主键，不能只依赖复合主键的一部分。

例如成绩表：

```text
主键：(student_id, course_id)
字段：score, student_name
```

`score` 依赖学生和课程的组合，但 `student_name` 只依赖 `student_id`，这就是部分依赖。更好的设计是把学生信息拆到学生表。

## 五、第三范式

第三范式要求非主键字段不能依赖其他非主键字段。

例如学生表：

```text
student_id, student_name, department_name, department_leader
```

`department_leader` 依赖 `department_name`，不是直接依赖学生主键。更好的设计是拆出部门表：

```text
department_id, department_name, department_leader
```

学生表只保存 `department_id`。

## 六、SQL 查询

基础查询：

```sql
select *
from user;
```

条件查询：

```sql
select *
from user
where status = 1
  and age >= 18;
```

投影查询：

```sql
select id, username, create_time
from user;
```

排序：

```sql
select id, username
from user
order by create_time desc;
```

分页：

```sql
select id, username
from user
order by id
limit 20 offset 40;
```

MySQL 也支持：

```sql
limit 40, 20;
```

注意：`limit offset, row_count` 中第一个数字是偏移量，不是页码。

## 七、聚合和分组

常见聚合函数：

| 函数 | 说明 |
| ---- | ---- |
| count | 统计行数 |
| sum | 求和 |
| avg | 平均值 |
| max | 最大值 |
| min | 最小值 |

示例：

```sql
select status, count(*) as total
from orders
group by status;
```

分组后过滤要用 `having`：

```sql
select user_id, count(*) as order_count
from orders
group by user_id
having count(*) > 10;
```

`where` 过滤分组前的行，`having` 过滤分组后的结果。

## 八、多表连接

内连接：

```sql
select o.id, u.username
from orders o
join user u on u.id = o.user_id;
```

左连接：

```sql
select u.id, o.id as order_id
from user u
left join orders o on o.user_id = u.id;
```

MySQL 不直接支持 `full outer join`。如果确实需要类似结果，通常用 `left join` 和 `right join` 再 `union`。

`JOIN` 的细节可以看 [SQL JOIN 与 ON、WHERE 的区别](./SQL%20JOIN%20与%20ON、WHERE%20的区别.md)。

## 九、修改数据

插入：

```sql
insert into user(username, age)
values ('Tom', 18);
```

批量插入：

```sql
insert into user(username, age)
values
  ('Tom', 18),
  ('Jerry', 20);
```

更新：

```sql
update user
set age = 19
where id = 1;
```

删除：

```sql
delete from user
where id = 1;
```

写 `update` 和 `delete` 时一定要确认 `where` 条件。生产里少一个 `where`，通常足够让人清醒一整天。

## 十、修改表结构

新增字段：

```sql
alter table user
add column email varchar(128);
```

修改字段类型：

```sql
alter table user
modify column email varchar(255);
```

删除字段：

```sql
alter table user
drop column email;
```

重命名表：

```sql
alter table user
rename to user_account;
```

大表执行 DDL 前要评估锁、耗时、磁盘空间、主从延迟和回滚方案。

## 十一、MySQL 存储引擎

MySQL 支持多种存储引擎。创建表时可以指定：

```sql
create table t (
  id bigint primary key
) engine = InnoDB;
```

查看支持的引擎：

```sql
show engines;
```

常见引擎：

| 引擎 | 特点 |
| ---- | ---- |
| InnoDB | 默认主流引擎，支持事务、行锁、外键、崩溃恢复 |
| MyISAM | 不支持事务和行锁，历史系统中可能见到 |
| MEMORY | 数据在内存中，服务重启后数据丢失 |

日常业务表优先使用 InnoDB。

## 十二、索引入口

索引用于减少扫描、优化排序、保证唯一性。常见创建方式：

```sql
create index idx_user_create_time
on user(create_time);

create unique index uk_user_mobile
on user(mobile);
```

联合索引：

```sql
create index idx_orders_user_status_time
on orders(user_id, status, create_time);
```

索引的底层结构、B+ 树、聚簇索引、回表、索引失效和深分页，可以看 [索引](./索引.md)。

## 十三、事务入口

手动事务：

```sql
begin;

update account
set balance = balance - 100
where id = 1;

update account
set balance = balance + 100
where id = 2;

commit;
```

失败时：

```sql
rollback;
```

事务隔离级别、快照读、当前读、锁和死锁，可以看 [MySQL 事务](./MySQL%20事务.md)。

## 十四、总结

学习 MySQL 可以按这个顺序：

1. 先掌握表、主键、约束、基本 SQL。
2. 再理解索引如何影响查询和写入。
3. 然后学习事务、锁和并发一致性。
4. 最后再看主从复制、多数据源、分库分表等架构问题。

数据库不是只会保存数据的文件柜。它同时负责约束、查询、并发、恢复和一致性。越早理解这些边界，后面写业务代码时越少踩坑。
