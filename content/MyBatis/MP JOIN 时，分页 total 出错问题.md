+++
date = '2026-02-19T12:07:35+08:00'
draft = false
title = 'MP JOIN 时，分页 total 出错问题'
+++

MyBatis-Plus 分页插件会自动生成 `count` SQL，用于计算分页总数。普通单表查询通常没有问题，但 JOIN 查询、分组查询、去重查询里，自动优化可能让 `total` 失真。

这类问题的本质不是分页插件“坏了”，而是插件无法准确理解业务 SQL 的语义。它能做语法层面的优化，却不能替你判断 JOIN 是否影响结果行数。

## 问题现象

原始查询 SQL：

```sql
SELECT
    a.id,
    a.model_code,
    a.model_name,
    a.model_type,
    b.id AS roam_path_id,
    b.name AS roam_path_name
FROM hbsw.iwater_v242.system_model_config a
LEFT JOIN hbsw.iwater_v242.system_model_camera_path b
    ON a.model_code = b.model_code
WHERE a.model_code IN (
    SELECT model_code
    FROM hbsw.iwater_v242.system_model_camera_path
    GROUP BY model_code
);
```

期望分页总数和 JOIN 后的数据语义一致。但分页插件可能优化出类似 SQL：

```sql
SELECT COUNT(*) AS total
FROM hbsw.iwater_v242.system_model_config a
WHERE a.model_code IN (
    SELECT model_code
    FROM hbsw.iwater_v242.system_model_camera_path
    GROUP BY model_code
);
```

它把 `LEFT JOIN b` 移除了，只统计主表 `a`。如果 JOIN 后存在一对多行扩展，或者查询条件依赖 JOIN 表，`total` 就可能与真实分页数据不一致。

## 为什么会这样

分页插件为了减少 count 成本，会尝试删除它认为“不影响 count 结果”的 JOIN。

例如：

```sql
SELECT a.*
FROM a
LEFT JOIN b ON a.id = b.a_id
WHERE a.status = 1
```

如果只从主表字段看，插件可能认为 `b` 表没有参与过滤，于是移除 JOIN。但真实业务里，JOIN 可能带来这些影响：

- 一对多关系导致结果行数增加。
- `WHERE` 条件引用了 JOIN 表字段。
- `ORDER BY`、`GROUP BY`、`DISTINCT` 改变了结果语义。
- 查询返回的是 VO，不是主表实体。

所以，只要 SQL 不是简单单表查询，就不能无条件相信自动 count 优化。

## 方案一：关闭当前分页的 count 优化

对单次查询关闭优化：

```java
Page<ModelRespVO> page = Page.of(current, size);
page.setOptimizeCountSql(false);
page.setOptimizeJoinOfCountSql(false);

IPage<ModelRespVO> result = mapper.selectModelPage(page, query);
```

不同 MyBatis-Plus 版本的方法可能略有差异，常见方法是：

- `setOptimizeCountSql(false)`
- `setOptimizeJoinOfCountSql(false)`

这个方案改动最小，适合快速修复某个复杂分页接口。

## 方案二：全局关闭 JOIN count 优化

如果项目里复杂 JOIN 分页较多，可以在分页插件配置中关闭 JOIN 优化：

```java
@Bean
public MybatisPlusInterceptor mybatisPlusInterceptor() {
    MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();

    PaginationInnerInterceptor pagination = new PaginationInnerInterceptor(DbType.MYSQL);
    pagination.setOptimizeJoin(false);

    interceptor.addInnerInterceptor(pagination);
    return interceptor;
}
```

这个方案更保守，但会牺牲一部分简单查询的 count 性能。不要因为一个接口出错就立刻全局关闭，除非项目 SQL 风格确实以复杂 JOIN 为主。

## 方案三：手写 count SQL

最可控的方案是关闭自动 count，自己写 count 查询：

```java
Page<ModelRespVO> page = Page.of(current, size);
page.setSearchCount(false);

List<ModelRespVO> records = mapper.selectModelPage(page, query);
Long total = mapper.countModelPage(query);

page.setRecords(records);
page.setTotal(total);
```

XML：

```xml
<select id="countModelPage" resultType="long">
    SELECT COUNT(*)
    FROM hbsw.iwater_v242.system_model_config a
    LEFT JOIN hbsw.iwater_v242.system_model_camera_path b
        ON a.model_code = b.model_code
    WHERE a.model_code IN (
        SELECT model_code
        FROM hbsw.iwater_v242.system_model_camera_path
        GROUP BY model_code
    )
</select>
```

如果原 SQL 使用了 `GROUP BY` 或 `DISTINCT`，count 可能需要包一层子查询：

```sql
SELECT COUNT(*)
FROM (
    SELECT a.model_code
    FROM system_model_config a
    LEFT JOIN system_model_camera_path b
        ON a.model_code = b.model_code
    GROUP BY a.model_code
) t
```

这看起来麻烦，但它至少明确。复杂 SQL 的正确性本来就不该交给“猜测”。

## 排查建议

遇到分页 `total` 不对时，按这个顺序查：

1. 打开 SQL 日志，确认插件生成的 count SQL。
2. 把原查询 SQL 和 count SQL 分别拿到数据库里执行。
3. 检查是否存在 JOIN、一对多、`GROUP BY`、`DISTINCT`、子查询。
4. 如果 count SQL 语义不一致，优先局部关闭优化。
5. 对核心接口手写 count，补上回归测试。

## 结论

MyBatis-Plus 的自动 count 优化适合简单查询。只要分页 SQL 里出现复杂 JOIN、分组、去重或 VO 聚合，就要把 `total` 当成需要验证的结果，而不是默认正确。

工程里真正可靠的规则是：**简单查询交给插件，复杂查询自己定义 count**。
