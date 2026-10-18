+++
date = '2026-02-19T17:35:55+08:00'
draft = false
title = 'SQL 递归'
+++

MySQL 8.0 支持递归公共表表达式，也就是 `WITH RECURSIVE`。它常用于查询树形结构，例如部门、菜单、区域、评论楼层。

递归查询的核心是两部分：**起点查询 anchor** 和 **递归查询 recursive member**。

## 一、基础语法

```sql
with recursive cte as (
  -- 1. anchor：递归起点
  select ...
  from ...
  where ...

  union all

  -- 2. recursive member：基于上一轮结果继续查询
  select ...
  from ...
  join cte on ...
)
select *
from cte;
```

第一段 SQL 生成第一批数据。第二段 SQL 引用 `cte` 自己，根据上一轮结果继续找下一层。直到没有新行产生，递归结束。

## 二、查询部门树

假设部门表：

```sql
create table dept (
  id bigint primary key,
  parent_id bigint null,
  name varchar(64) not null
);
```

数据结构：

```text
100 总部
  110 研发
    111 后端
    112 前端
  120 财务
```

查询 `100` 下面的整棵树：

```sql
with recursive dept_tree as (
  select
    id,
    parent_id,
    name,
    0 as level,
    cast(id as char(200)) as path
  from dept
  where id = 100

  union all

  select
    d.id,
    d.parent_id,
    d.name,
    t.level + 1 as level,
    concat(t.path, ',', d.id) as path
  from dept d
  join dept_tree t on d.parent_id = t.id
)
select id, parent_id, name, level, path
from dept_tree
order by path;
```

结果可能是：

| id | parent_id | name | level | path |
| -- | --------- | ---- | ----- | ---- |
| 100 | NULL | 总部 | 0 | 100 |
| 110 | 100 | 研发 | 1 | 100,110 |
| 111 | 110 | 后端 | 2 | 100,110,111 |
| 112 | 110 | 前端 | 2 | 100,110,112 |
| 120 | 100 | 财务 | 1 | 100,120 |

递归查询返回的是一个结果集，不是一棵真正的对象树。每一行代表树上的一个节点。应用层如果需要嵌套 JSON，还要根据 `id` 和 `parent_id` 再组装。

## 三、向上查父级链路

如果要从某个部门向上查所有父级：

```sql
with recursive parent_tree as (
  select
    id,
    parent_id,
    name,
    0 as level
  from dept
  where id = 111

  union all

  select
    d.id,
    d.parent_id,
    d.name,
    t.level + 1
  from dept d
  join parent_tree t on d.id = t.parent_id
)
select *
from parent_tree
order by level desc;
```

结果会从根节点到当前节点排列，适合面包屑、权限继承、区域上级链路等场景。

## 四、防止死循环

递归查询最怕脏数据导致环：

```text
A 的 parent_id = B
B 的 parent_id = A
```

如果没有限制，就可能递归很深直到触发数据库递归上限。

常见防护：

1. 限制最大层级。
2. 维护 path，避免重复访问同一个节点。
3. 写入数据时就校验不能形成环。

限制层级：

```sql
with recursive dept_tree as (
  select id, parent_id, name, 0 as level
  from dept
  where id = 100

  union all

  select d.id, d.parent_id, d.name, t.level + 1
  from dept d
  join dept_tree t on d.parent_id = t.id
  where t.level < 10
)
select *
from dept_tree;
```

## 五、索引建议

递归查询通常需要这两个索引：

```sql
primary key (id)
key idx_dept_parent_id (parent_id)
```

向下查子节点时，要通过 `parent_id` 找下一层。没有 `parent_id` 索引，每一层都可能扫描整张表。

向上查父节点时，主键 `id` 足够关键。

## 六、总结

`WITH RECURSIVE` 适合处理层级数据。写递归 SQL 时，先明确方向：向下查子树，还是向上查父链。

然后关注三件事：起点是否正确，递归连接条件是否正确，是否有层级或环路保护。递归 SQL 写错时，数据库不会替你理解“树应该长什么样”，它只会忠实地一层层执行。
