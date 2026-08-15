+++
date = '2026-02-19T12:33:48+08:00'
draft = false
title = 'mysql 视图'
+++

## 一、什么是 MySQL 视图？

**视图是一个保存好的 SQL 查询，本身不存数据，每次访问时动态执行底层 SQL。**

```sql
CREATE VIEW v_user_order AS
SELECT u.id, u.name, o.amount
FROM user u
JOIN orders o ON u.id = o.user_id;
```

之后就可以像查表一样：

```java
SELECT * FROM v_user_order;
```

## 二、视图 ≠ 表

| 对比项     | 表   | 视图     |
| ---------- | ---- | -------- |
| 是否存数据 | 是   | 否       |
| 是否占空间 | 是   | 几乎不占 |
| 是否实时   | 否   | 是       |
| 是否可更新 | 是   | 有条件   |
| 本质       | 数据 | SQL 封装 |

**视图 = SQL 的别名 + 封装**

## 三、为什么要用视图？

### 简化复杂 SQL

可能写过这种 SQL：

```sql
SELECT year, xzcd, SUM(amount)
FROM vt_dr_szyfq_jslcg_b
WHERE year BETWEEN 2015 AND 2020
GROUP BY year, xzcd;
```

如果被 **N 个接口 / 报表复用**：

```sql
CREATE VIEW v_water_year_xzcd AS
SELECT year, xzcd, SUM(amount) total_amount
FROM vt_dr_szyfq_jslcg_b
GROUP BY year, xzcd;
```

以后只查视图：

```sql
SELECT * FROM v_water_year_xzcd WHERE year >= 2018;
```

少写 SQL；少出错；逻辑集中

### 权限隔离

**不给用户表权限，只给视图权限**

```sql
GRANT SELECT ON v_water_year_xzcd TO 'report_user';
```

用户：

- 看不到原始表
- 看不到敏感字段
- 只能查你允许的结果

**这是视图的一个官方用途**

### 统一字段口径

后端经常遇到：

- 表字段名乱
- 多表 join 规则复杂

用视图统一：

```sql
CREATE VIEW v_order_simple AS
SELECT
  o.id AS orderId,
  u.name AS userName,
  o.amount,
  o.create_time
FROM orders o
JOIN user u ON o.user_id = u.id;
```

## 四、视图能不能 UPDATE / INSERT？

**有条件可以，大多数复杂视图不行**

## 五、视图性能如何？会不会慢？

MySQL 的视图：

- 不缓存结果
- 每次查询 -> 展开成原 SQL

```sql
SELECT * FROM v_xxx;
```

等价于：

```sql
SELECT ... FROM ... JOIN ...;
```

### 性能结论：

| 场景        | 性能          |
| ----------- | ------------- |
| 简单封装    | 几乎无损      |
| 多表 + 聚合 | 和原 SQL 一样 |
| 大表高频    | 要谨慎        |

**视图不是性能优化工具，是结构优化工具**

**MySQL 视图本质是 SQL 的封装，用来简化复杂查询、隔离权限、统一数据口径，不存数据、不提升性能，大多数情况下是只读的。**
