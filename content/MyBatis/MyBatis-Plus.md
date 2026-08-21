+++
date = '2026-01-30T19:18:59+08:00'
draft = false
title = 'MyBatis-Plus'
+++

MyBatis-Plus 是 MyBatis 的增强工具。它不替代 MyBatis，而是在 MyBatis 之上提供通用 CRUD、条件构造器、分页插件、逻辑删除、自动填充、乐观锁等能力。

它适合解决重复性很高的单表操作和常规列表查询；遇到复杂 JOIN、窗口函数、数据库特性明显的 SQL 时，仍然应该回到 XML 或手写 SQL。工具有边界，假装没有边界，只会让边界在生产环境里亲自提醒你。

## 依赖与配置

Spring Boot 项目中常见依赖如下：

```xml
<dependency>
    <groupId>com.baomidou</groupId>
    <artifactId>mybatis-plus-boot-starter</artifactId>
    <version>3.5.12</version>
</dependency>
<dependency>
    <groupId>com.mysql</groupId>
    <artifactId>mysql-connector-j</artifactId>
    <version>9.1.0</version>
</dependency>
```

配置示例：

```yaml
spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://127.0.0.1:3306/demo
    username: root
    password: 123456

mybatis-plus:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.example.domain
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      id-type: assign_id
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0
```

`mybatis-plus-boot-starter` 会自动集成 MyBatis、MyBatis-Spring、MyBatis-Plus 扩展能力。你仍然可以写 XML，也仍然可以使用原生 MyBatis 的能力。

## 实体映射

MyBatis-Plus 通过注解描述表和字段的映射关系：

```java
@TableName("sys_user")
public class User {

    @TableId(value = "id", type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("user_name")
    private String userName;

    private Integer age;

    @TableLogic
    private Integer deleted;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField(exist = false)
    private String displayName;
}
```

常用注解：

| 注解 | 作用 |
| --- | --- |
| `@TableName` | 指定数据库表名 |
| `@TableId` | 指定主键列和主键策略 |
| `@TableField` | 指定字段映射、自动填充、是否存在 |
| `@TableLogic` | 标记逻辑删除字段 |
| `@Version` | 标记乐观锁版本字段 |

如果表字段遵循下划线命名，Java 属性遵循驼峰命名，开启 `map-underscore-to-camel-case` 后通常不需要给每个字段都写 `@TableField`。

## BaseMapper

Mapper 继承 `BaseMapper<T>` 后，可以直接获得常见 CRUD 方法：

```java
@Mapper
public interface UserMapper extends BaseMapper<User> {
}
```

常用方法：

| 方法 | 说明 |
| --- | --- |
| `insert(entity)` | 插入一条记录 |
| `deleteById(id)` | 按主键删除 |
| `delete(wrapper)` | 按条件删除 |
| `updateById(entity)` | 按主键更新 |
| `update(entity, wrapper)` | 按条件更新 |
| `selectById(id)` | 按主键查询 |
| `selectList(wrapper)` | 按条件查询列表 |
| `selectPage(page, wrapper)` | 分页查询 |

`BaseMapper` 适合单表常规操作。复杂 SQL 不必强行塞进 Wrapper，可以直接在 Mapper XML 中写自定义方法。

## Service 层

MyBatis-Plus 也提供了 `IService` 和 `ServiceImpl`：

```java
public interface UserService extends IService<User> {
}
```

```java
@Service
public class UserServiceImpl
        extends ServiceImpl<UserMapper, User>
        implements UserService {
}
```

这样可以直接使用 `save`、`removeById`、`list`、`page`、`saveBatch` 等方法。

是否使用 `IService` 取决于团队习惯。它能减少样板代码，但也可能让 Service 方法过于“万能”。如果业务边界明确，自己定义 Service 接口会更清晰。

## Wrapper 条件构造器

Wrapper 是 MyBatis-Plus 最常用也最容易误用的能力。

```java
LambdaQueryWrapper<User> wrapper = Wrappers.lambdaQuery(User.class)
        .eq(name != null && !name.isBlank(), User::getUserName, name)
        .ge(minAge != null, User::getAge, minAge)
        .orderByDesc(User::getCreatedAt);

List<User> users = userMapper.selectList(wrapper);
```

这里每个条件方法的第一个参数是 `condition`：

```java
.eq(condition, column, value)
```

只有 `condition == true` 时，MP 才会把该条件加入 SQL。这个写法比在外层堆很多 `if` 更紧凑，也能避免把无效条件拼进 SQL。

## Lambda Wrapper

优先使用 `LambdaQueryWrapper` 和 `LambdaUpdateWrapper`：

```java
LambdaUpdateWrapper<User> wrapper = Wrappers.lambdaUpdate(User.class)
        .set(User::getUserName, "Alice")
        .eq(User::getId, 1L);

userMapper.update(null, wrapper);
```

Lambda 写法通过方法引用定位字段：

```java
User::getUserName
```

它比字符串字段更适合重构。字段改名后，编译器会提醒你，而不是等到运行时 SQL 报错。

## 自定义 SQL 中使用 Wrapper

有时 SQL 主体需要自己写，但条件希望交给 Wrapper：

```java
@Select("""
        select id, user_name, age
        from sys_user
        ${ew.customSqlSegment}
        """)
List<User> selectByWrapper(@Param(Constants.WRAPPER) Wrapper<User> wrapper);
```

`Constants.WRAPPER` 的值是 `ew`，所以等价于：

```java
@Param("ew") Wrapper<User> wrapper
```

`ew.customSqlSegment` 是 MP 根据 Wrapper 生成的 SQL 片段，可能包含 `where`、`and`、`order by` 等结构。

注意这里必须使用 `${}`，因为它拼的是 SQL 片段，不是单个参数：

```sql
select * from sys_user ${ew.customSqlSegment}
```

这并不等于鼓励手写字符串拼接。Wrapper 内部会对值进行参数化处理，但 SQL 片段的结构仍要由开发者控制，不能把用户输入直接拼成列名、排序字段或表名。

## 分页插件

MyBatis-Plus 3.4 以后推荐使用 `MybatisPlusInterceptor`：

```java
@Configuration
public class MyBatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        PaginationInnerInterceptor pagination =
                new PaginationInnerInterceptor(DbType.MYSQL);
        pagination.setMaxLimit(500L);
        interceptor.addInnerInterceptor(pagination);
        return interceptor;
    }
}
```

分页查询：

```java
Page<User> page = Page.of(current, size);
LambdaQueryWrapper<User> wrapper = Wrappers.lambdaQuery(User.class)
        .eq(status != null, User::getStatus, status)
        .orderByDesc(User::getCreatedAt);

IPage<User> result = userMapper.selectPage(page, wrapper);
```

分页参数说明：

| 字段 | 说明 |
| --- | --- |
| `current` | 当前页，从 1 开始 |
| `size` | 每页数量 |
| `records` | 当前页数据 |
| `total` | 总记录数 |
| `pages` | 总页数 |

生产环境建议设置 `maxLimit`，避免调用方传入过大的 `size`。

## JOIN 分页的 count 问题

MyBatis-Plus 分页插件会尝试优化 count SQL。普通单表查询通常没问题，但复杂 JOIN 可能出错。

例如原 SQL：

```sql
select a.id, a.name, b.tag_name
from product a
left join product_tag b on a.id = b.product_id
where b.tag_name = #{tagName}
```

分页插件可能认为某些 JOIN 对 count 没影响，于是改写成只统计主表。只要 `where`、`group by`、`distinct` 或一对多 JOIN 影响结果行数，自动优化就可能导致 `total` 不准。

局部关闭优化：

```java
Page<ProductVO> page = Page.of(current, size);
page.setOptimizeCountSql(false);
page.setOptimizeJoinOfCountSql(false);
```

更可控的做法是关闭自动 count，自己写 count SQL：

```java
Page<ProductVO> page = Page.of(current, size);
page.setSearchCount(false);

List<ProductVO> records = productMapper.selectProductPage(page, query);
Long total = productMapper.countProductPage(query);

page.setRecords(records);
page.setTotal(total);
```

复杂 JOIN 场景里，手写 count 往往比“相信插件理解业务语义”更稳。插件没有读心术，这一点倒是比人类诚实。

## 逻辑删除

逻辑删除不是物理删除，而是把记录标记为已删除：

```sql
alter table sys_user add column deleted tinyint default 0 not null;
```

实体字段：

```java
@TableLogic
private Integer deleted;
```

配置：

```yaml
mybatis-plus:
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0
```

使用 Wrapper 或 `BaseMapper` 查询时，MP 会自动追加：

```sql
deleted = 0
```

删除时则会改写为：

```sql
update sys_user set deleted = 1 where id = ?
```

需要注意：

- 手写 XML SQL 不一定自动追加逻辑删除条件，应自行检查。
- 恢复已删除数据时，Wrapper 默认会过滤 `deleted = 1` 的记录。
- 唯一索引需要考虑逻辑删除字段，否则删除后再次插入同业务键可能冲突。

常见唯一索引设计：

```sql
create unique index uk_user_name_deleted on sys_user(user_name, deleted);
```

如果同一个 `user_name` 允许删除后重新创建，还需要结合业务约束、历史保留策略或非业务主键设计，不要只靠逻辑删除字段侥幸通过。

## 自动填充

创建时间、更新时间、创建人、更新人可以用自动填充处理：

```java
@Component
public class AuditMetaObjectHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        strictInsertFill(metaObject, "createdAt", LocalDateTime.class, now);
        strictInsertFill(metaObject, "updatedAt", LocalDateTime.class, now);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        strictUpdateFill(metaObject, "updatedAt", LocalDateTime.class, LocalDateTime.now());
    }
}
```

实体字段：

```java
@TableField(fill = FieldFill.INSERT)
private LocalDateTime createdAt;

@TableField(fill = FieldFill.INSERT_UPDATE)
private LocalDateTime updatedAt;
```

自动填充只在 MP 参与的 insert、update 流程中生效。手写 SQL 不会自动经过这些字段填充逻辑。

## 乐观锁

乐观锁用于防止并发更新覆盖：

```java
@Version
private Integer version;
```

配置插件：

```java
@Bean
public MybatisPlusInterceptor mybatisPlusInterceptor() {
    MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
    interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
    interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
    return interceptor;
}
```

更新时 MP 会附加版本条件：

```sql
update sys_user
set user_name = ?, version = version + 1
where id = ? and version = ?
```

如果返回更新行数为 0，说明数据已被其他事务修改，应提示用户重试或重新加载数据。

## 安全注意事项

Wrapper 能减少字符串拼接，但不代表所有写法都安全。

谨慎使用这些方法：

- `last("limit 1")`
- `apply("date_format(create_time,'%Y-%m') = {0}", month)`
- `inSql(User::getId, "select user_id from ...")`
- `orderBy(true, true, rawColumn)`

凡是接收 SQL 片段的方法，都应避免直接使用用户输入。排序字段、查询列名、动态表名要做白名单映射：

```java
Map<String, SFunction<User, ?>> sortMapping = Map.of(
        "createdAt", User::getCreatedAt,
        "age", User::getAge
);
```

## 使用建议

- 单表 CRUD、简单列表查询优先用 `BaseMapper` 和 Lambda Wrapper。
- 复杂 JOIN、复杂聚合、报表 SQL 优先写 XML。
- Wrapper 条件尽量补全 `condition` 参数，避免拼出无意义条件。
- 分页接口必须限制 `size` 上限。
- 逻辑删除表的唯一索引要提前设计。
- 插件顺序要明确，分页、多租户、数据权限、乐观锁同时存在时尤其要测试。

MyBatis-Plus 的价值是“减少重复”，不是“消灭 SQL”。真正稳定的用法，是让它处理适合自动化的部分，把复杂业务 SQL 留在能被人直接审查的位置。
