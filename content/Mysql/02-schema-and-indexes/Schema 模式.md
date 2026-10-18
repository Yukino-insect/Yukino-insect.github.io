+++
date = '2026-02-17T23:06:17+08:00'
draft = false
title = 'Schema 模式'
+++

我第一次在实习项目里接触 PostgreSQL 时，最容易混淆的概念就是 schema。MySQL 中也能看到 `schema` 这个词，但它和 PostgreSQL 的 schema 不是同一层级的东西。

简单说：**PostgreSQL 的 schema 是 database 内部的命名空间；MySQL 里 schema 基本可以理解为 database 的同义词。**

## 一、PostgreSQL 的 schema

PostgreSQL 的层级大致是：

```text
server
  └── database
        └── schema
              ├── table
              ├── view
              ├── function
              ├── sequence
              └── type
```

例如：

```text
public.user
auth.user
```

这里 `public` 和 `auth` 是两个 schema。它们下面都可以有一张叫 `user` 的表，因为完整对象名不同。

## 二、schema 的作用

### 1. 解决重名

不同模块可以有同名对象：

```text
auth.user
report.user
```

只要 schema 不同，就不会冲突。

### 2. 模块化组织

可以像包结构一样管理数据库对象：

```text
auth.users
auth.roles
order.orders
order.order_items
```

大型系统里，这比把所有表都丢进一个公共命名空间更清楚。

### 3. 权限隔离

可以按 schema 授权：

```sql
grant usage on schema auth to app_user;
grant select on all tables in schema auth to app_user;
```

这样权限边界可以按模块组织。

### 4. 多租户隔离

一种多租户设计是每个租户一个 schema：

```text
tenant_a.user
tenant_b.user
```

这种方式逻辑隔离较清晰，但租户数量太多时，迁移、DDL、连接配置和权限管理都会变复杂。

## 三、search_path

PostgreSQL 用 `search_path` 决定未指定 schema 时从哪里找对象：

```sql
show search_path;
```

常见默认值类似：

```text
"$user", public
```

如果设置：

```sql
set search_path to auth, public;
```

执行：

```sql
select *
from user;
```

会优先查找：

```text
auth.user
```

找不到才继续查 `public.user`。

生产 SQL 中，如果对象归属很重要，可以显式写 schema，避免被 `search_path` 影响。

## 四、MySQL 中的 schema

MySQL 中：

```text
schema ≈ database
```

例如：

```sql
create database blog;
use blog;
```

在很多 MySQL 工具里，`schema` 和 `database` 基本指同一个东西。MySQL 没有 PostgreSQL 那种 database 内再分多个 schema 的层级。

对比：

```text
PostgreSQL:
database -> schema -> table

MySQL:
database/schema -> table
```

## 五、schema 和数据源

schema 是命名空间，不天然等于数据源。

如果同一个 PostgreSQL database 里有多个 schema，只要使用同一个连接，就可以在一个本地事务中访问它们：

```sql
begin;
insert into schema_a.t1 values (...);
insert into schema_b.t2 values (...);
commit;
```

但如果应用层给每个 schema 都配置一个独立 `DataSource`，那就变成了多个连接。一个本地事务不再天然覆盖全部操作。

这类设计会让事务边界变复杂。除非有明确隔离需求，否则不要把“命名空间隔离”误建模成“数据源隔离”。

## 六、底层理解

在 PostgreSQL 内部，schema 信息存放在系统目录中。对象会通过 namespace 和 name 共同确定身份。

这也是为什么同名表可以存在于不同 schema 中：

```text
namespace = auth, name = user
namespace = report, name = user
```

它们不是同一个对象。

## 七、总结

PostgreSQL schema 是 database 内部的命名空间，适合做模块化、权限隔离和有限的租户隔离。MySQL 里的 schema 基本等同于 database。

理解这个差异很重要。否则在设计多数据源、事务边界和对象命名时，很容易把“逻辑命名空间”误认为“物理数据源”。
