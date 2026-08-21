+++
date = '2025-09-20T18:25:57+08:00'
draft = false
title = 'MyBatis'
+++

MyBatis 是一个半自动 ORM 持久层框架。它不会替开发者生成所有 SQL，而是让开发者自己控制 SQL，再负责完成参数绑定、SQL 执行、结果映射和 Mapper 代理。

如果一句话概括它的价值：**把 JDBC 的模板代码收起来，把 SQL 的控制权留给开发者**。

## 核心定位

MyBatis 主要解决四件事：

- 用 Mapper 接口和 XML 或注解管理 SQL。
- 用 `#{}` 把 Java 参数安全绑定到 SQL 占位符。
- 用 `resultType` 或 `resultMap` 把查询结果映射成 Java 对象。
- 用动态 SQL 标签处理可选查询条件、批量操作和复杂拼接。

它和 Hibernate 这类全自动 ORM 不同。MyBatis 更适合 SQL 比较重要、查询需要精细控制、团队希望直接审查 SQL 的项目。

## 基础依赖

纯 MyBatis 项目至少需要引入 MyBatis 本体和数据库驱动：

```xml
<dependencies>
    <dependency>
        <groupId>org.mybatis</groupId>
        <artifactId>mybatis</artifactId>
        <version>3.5.19</version>
    </dependency>
    <dependency>
        <groupId>com.mysql</groupId>
        <artifactId>mysql-connector-j</artifactId>
        <version>9.1.0</version>
    </dependency>
</dependencies>
```

版本号只是示例，真实项目里应统一交给父工程或 BOM 管理。

## 全局配置

MyBatis 通过 `mybatis-config.xml` 启动。这个文件负责描述运行环境、数据源、事务管理器、类型别名、插件和 Mapper 加载位置。

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE configuration
        PUBLIC "-//mybatis.org//DTD Config 3.0//EN"
        "https://mybatis.org/dtd/mybatis-3-config.dtd">
<configuration>
    <properties>
        <property name="driver" value="com.mysql.cj.jdbc.Driver"/>
        <property name="url" value="jdbc:mysql://127.0.0.1:3306/demo"/>
        <property name="username" value="root"/>
        <property name="password" value="123456"/>
    </properties>

    <settings>
        <setting name="mapUnderscoreToCamelCase" value="true"/>
    </settings>

    <typeAliases>
        <package name="com.example.domain"/>
    </typeAliases>

    <environments default="development">
        <environment id="development">
            <transactionManager type="JDBC"/>
            <dataSource type="POOLED">
                <property name="driver" value="${driver}"/>
                <property name="url" value="${url}"/>
                <property name="username" value="${username}"/>
                <property name="password" value="${password}"/>
            </dataSource>
        </environment>
    </environments>

    <mappers>
        <package name="com.example.mapper"/>
    </mappers>
</configuration>
```

几个常见配置项：

| 配置 | 作用 |
| --- | --- |
| `properties` | 抽取可复用配置，支持外部属性文件 |
| `settings` | 控制 MyBatis 行为，例如驼峰映射、缓存、懒加载 |
| `typeAliases` | 给实体类设置短别名，减少 XML 里的全限定类名 |
| `environments` | 配置数据源和事务管理器 |
| `mappers` | 告诉 MyBatis 到哪里加载 Mapper |

在 Spring Boot 项目中，这些配置大多会被 starter 自动装配取代，但理解原生配置有助于判断问题到底发生在哪一层。连这个都不看，排查时就只能祈祷，祈祷通常不属于可靠工程实践。

## Mapper 接口

Mapper 接口用于描述数据访问方法：

```java
package com.example.mapper;

import com.example.domain.User;
import org.apache.ibatis.annotations.Param;

import java.util.List;

public interface UserMapper {

    User selectById(Long id);

    List<User> selectByName(@Param("name") String name);

    int insert(User user);

    int update(User user);

    int deleteById(Long id);
}
```

MyBatis 会根据接口全限定名和方法名找到对应 SQL。一般推荐让 XML 的 `namespace` 等于 Mapper 接口全限定名，SQL 的 `id` 等于接口方法名。

## Mapper XML

一个典型 Mapper XML 如下：

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper
        PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "https://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.mapper.UserMapper">

    <resultMap id="UserResultMap" type="User">
        <id property="id" column="id"/>
        <result property="userName" column="user_name"/>
        <result property="age" column="age"/>
        <result property="createdAt" column="created_at"/>
    </resultMap>

    <select id="selectById" resultMap="UserResultMap">
        select id, user_name, age, created_at
        from user
        where id = #{id}
    </select>

    <select id="selectByName" resultMap="UserResultMap">
        select id, user_name, age, created_at
        from user
        where user_name = #{name}
    </select>

    <insert id="insert" useGeneratedKeys="true" keyProperty="id">
        insert into user(user_name, age, created_at)
        values(#{userName}, #{age}, #{createdAt})
    </insert>

    <update id="update">
        update user
        set user_name = #{userName},
            age = #{age}
        where id = #{id}
    </update>

    <delete id="deleteById">
        delete from user where id = #{id}
    </delete>
</mapper>
```

`resultType` 适合字段名和属性名能直接匹配的简单查询；`resultMap` 更适合复杂映射，例如字段名不一致、对象嵌套、一对多关系。

## SqlSession 执行流程

纯 MyBatis 的基本使用方式是通过 `SqlSessionFactory` 创建 `SqlSession`，再获取 Mapper 代理对象：

```java
try (InputStream inputStream = Resources.getResourceAsStream("mybatis-config.xml")) {
    SqlSessionFactory factory = new SqlSessionFactoryBuilder().build(inputStream);

    try (SqlSession sqlSession = factory.openSession(false)) {
        UserMapper mapper = sqlSession.getMapper(UserMapper.class);
        User user = mapper.selectById(1L);
        System.out.println(user);
        sqlSession.commit();
    }
}
```

`openSession(false)` 表示关闭自动提交，需要手动 `commit()`。如果发生异常，应执行 `rollback()`，否则可能留下未提交事务。

在 Spring 项目中通常不直接操作 `SqlSession`，而是由 `SqlSessionTemplate` 和 Spring 事务统一管理。

## 参数绑定

MyBatis 中最容易混淆的是 `#{}` 和 `${}`。

### `#{}`

`#{}` 是预编译参数绑定。MyBatis 会把它转换成 JDBC 的 `?` 占位符，再通过 `PreparedStatement` 设置参数：

```xml
select * from user where id = #{id}
```

大致等价于：

```java
preparedStatement.setLong(1, id);
```

它的优点是安全、支持类型转换、能避免大多数 SQL 注入问题。

### `${}`

`${}` 是字符串替换：

```xml
select * from ${tableName} where id = #{id}
```

它适合动态表名、动态字段名、排序字段这类无法用 `?` 占位的 SQL 结构，但必须严格白名单校验。用户输入不能直接进入 `${}`，否则就是把门打开请 SQL 注入进来坐下喝茶，倒也不必如此体贴。

### `@Param`

当 Mapper 方法有多个参数时，建议显式使用 `@Param`：

```java
User selectByIdAndName(@Param("id") Long id, @Param("name") String name);
```

XML 中即可直接使用：

```xml
<select id="selectByIdAndName" resultMap="UserResultMap">
    select id, user_name, age
    from user
    where id = #{id}
      and user_name = #{name}
</select>
```

如果不写 `@Param`，MyBatis 会使用 `param1`、`param2`、`arg0`、`arg1` 等默认名称，可读性和稳定性都差一些。

## 动态 SQL

动态 SQL 用于根据条件生成不同 SQL。常用标签包括 `if`、`choose`、`where`、`set`、`foreach`。

### `if`

```xml
<select id="selectByCondition" resultMap="UserResultMap">
    select id, user_name, age
    from user
    where 1 = 1
    <if test="name != null and name != ''">
        and user_name = #{name}
    </if>
    <if test="minAge != null">
        and age &gt;= #{minAge}
    </if>
</select>
```

### `where`

`where` 会在至少有一个条件成立时自动补上 `where`，并去掉开头多余的 `and` 或 `or`：

```xml
<select id="selectByCondition" resultMap="UserResultMap">
    select id, user_name, age
    from user
    <where>
        <if test="name != null and name != ''">
            and user_name = #{name}
        </if>
        <if test="minAge != null">
            and age &gt;= #{minAge}
        </if>
    </where>
</select>
```

### `set`

`set` 常用于动态更新，会自动处理末尾逗号：

```xml
<update id="updateSelective">
    update user
    <set>
        <if test="userName != null">
            user_name = #{userName},
        </if>
        <if test="age != null">
            age = #{age},
        </if>
    </set>
    where id = #{id}
</update>
```

### `foreach`

`foreach` 常用于批量查询或批量写入：

```xml
<select id="selectByIds" resultMap="UserResultMap">
    select id, user_name, age
    from user
    where id in
    <foreach collection="ids" item="id" open="(" close=")" separator=",">
        #{id}
    </foreach>
</select>
```

传入集合时，Mapper 方法可以写成：

```java
List<User> selectByIds(@Param("ids") List<Long> ids);
```

## 结果映射

字段名和属性名一致时，可以使用 `resultType`：

```xml
<select id="selectSimple" resultType="User">
    select id, user_name as userName, age
    from user
</select>
```

对象关系复杂时使用 `resultMap`。

### 一对一映射

```xml
<resultMap id="OrderResultMap" type="Order">
    <id property="id" column="order_id"/>
    <result property="orderNo" column="order_no"/>
    <association property="user" javaType="User">
        <id property="id" column="user_id"/>
        <result property="userName" column="user_name"/>
    </association>
</resultMap>
```

### 一对多映射

```xml
<resultMap id="UserWithOrdersMap" type="User">
    <id property="id" column="user_id"/>
    <result property="userName" column="user_name"/>
    <collection property="orders" ofType="Order">
        <id property="id" column="order_id"/>
        <result property="orderNo" column="order_no"/>
    </collection>
</resultMap>
```

一对多映射要注意结果集膨胀。用户有 10 个订单，SQL 返回 10 行，MyBatis 会把这些行合并成一个用户对象和 10 个订单对象。如果主键映射缺失，合并结果很容易异常。

## 缓存机制

MyBatis 有一级缓存和二级缓存。

### 一级缓存

一级缓存默认开启，作用域是 `SqlSession`。同一个 `SqlSession` 内执行相同查询，可能直接从缓存返回。

缓存会在以下情况清空：

- 执行 `insert`、`update`、`delete`。
- 手动调用 `clearCache()`。
- 提交或回滚事务。
- 关闭 `SqlSession`。

在 Spring 项目中，`SqlSession` 通常被框架托管，同一个事务内更容易观察到一级缓存效果。

### 二级缓存

二级缓存作用域是 Mapper 的 `namespace`，需要显式开启：

```xml
<mapper namespace="com.example.mapper.UserMapper">
    <cache eviction="LRU"
           flushInterval="60000"
           size="512"
           readOnly="false"/>
</mapper>
```

二级缓存适合读多写少、数据实时性要求不高的表。不适合频繁更新、多表强一致查询、分布式多实例共享缓存的场景。

在业务系统中，二级缓存要谨慎使用。很多时候直接使用 Redis 并在业务层设计缓存失效策略，会比依赖 Mapper 级缓存更清楚。

## 插件机制

MyBatis 插件基于拦截器机制，可以拦截四类核心对象：

```text
Executor
StatementHandler
ParameterHandler
ResultSetHandler
```

常见插件如 PageHelper、SQL 监控、慢 SQL 统计，都是在这些执行点上织入逻辑。

一个简化版插件如下：

```java
@Intercepts({
    @Signature(
        type = StatementHandler.class,
        method = "prepare",
        args = {Connection.class, Integer.class}
    )
})
public class SqlLogInterceptor implements Interceptor {

    @Override
    public Object intercept(Invocation invocation) throws Throwable {
        StatementHandler handler = (StatementHandler) invocation.getTarget();
        BoundSql boundSql = handler.getBoundSql();
        System.out.println(boundSql.getSql());
        return invocation.proceed();
    }
}
```

插件很强，但也很容易制造隐蔽问题。修改 SQL、分页、租户隔离、数据权限这类插件尤其要补足测试。

## Spring 集成

在传统 Spring 项目中，MyBatis 通常需要配置：

- `DataSource`
- `SqlSessionFactoryBean`
- `SqlSessionTemplate`
- `MapperScannerConfigurer`
- `DataSourceTransactionManager`

核心配置大致如下：

```java
@Configuration
@MapperScan("com.example.mapper")
public class MyBatisConfig {

    @Bean
    public SqlSessionFactory sqlSessionFactory(DataSource dataSource) throws Exception {
        SqlSessionFactoryBean factoryBean = new SqlSessionFactoryBean();
        factoryBean.setDataSource(dataSource);
        factoryBean.setMapperLocations(
                new PathMatchingResourcePatternResolver()
                        .getResources("classpath*:mapper/**/*.xml")
        );
        return factoryBean.getObject();
    }

    @Bean
    public DataSourceTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}
```

配置完成后，Mapper 接口会被注册为 Spring Bean，可以直接注入 Service。

## Spring Boot 集成

Spring Boot 项目通常使用 starter：

```xml
<dependency>
    <groupId>org.mybatis.spring.boot</groupId>
    <artifactId>mybatis-spring-boot-starter</artifactId>
    <version>3.0.4</version>
</dependency>
```

配置文件示例：

```yaml
spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://127.0.0.1:3306/demo
    username: root
    password: 123456

mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.example.domain
  configuration:
    map-underscore-to-camel-case: true
```

启动类或配置类上添加：

```java
@SpringBootApplication
@MapperScan("com.example.mapper")
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

如果每个 Mapper 接口都标注了 `@Mapper`，也可以不写 `@MapperScan`。但在真实项目里，更推荐统一使用 `@MapperScan`，这样接口层更干净。

## 执行原理

MyBatis 的核心执行链路可以简化为：

```text
Mapper 接口方法
  -> MapperProxy
  -> MappedStatement
  -> Executor
  -> StatementHandler
  -> ParameterHandler
  -> JDBC PreparedStatement
  -> ResultSetHandler
  -> Java 对象
```

关键对象说明：

| 对象 | 职责 |
| --- | --- |
| `Configuration` | 保存全局配置、Mapper、MappedStatement、插件等信息 |
| `MappedStatement` | 一条 SQL 语句的完整元数据 |
| `BoundSql` | 最终 SQL 和参数映射 |
| `Executor` | SQL 执行入口，负责查询、更新、缓存协调 |
| `StatementHandler` | 创建并执行 JDBC Statement |
| `ParameterHandler` | 把 Java 参数绑定到 SQL 占位符 |
| `ResultSetHandler` | 把 ResultSet 映射成 Java 对象 |

理解这条链路后，很多问题会变得清楚：

- SQL 没加载，多半看 `mapper-locations`、`namespace`、`id`。
- 参数绑定失败，多半看 `@Param`、参数对象属性名、`#{}` 写法。
- 结果为空或字段为 null，多半看列名、驼峰映射、`resultMap`。
- 分页或数据权限异常，多半看插件顺序和插件改写后的 SQL。

## 常见坑

### XML 特殊字符

XML 中 `<`、`>`、`&` 需要转义：

```xml
where age &gt;= #{age}
```

也可以使用 CDATA：

```xml
<![CDATA[
    where age >= #{age}
]]>
```

### 模糊查询

不要这样写：

```xml
and name like '%${name}%'
```

推荐写法：

```xml
and name like concat('%', #{name}, '%')
```

### 空集合 `in`

`foreach` 遇到空集合时可能生成非法 SQL。应在业务层提前判断，或在 XML 中处理空集合。

```java
if (ids == null || ids.isEmpty()) {
    return Collections.emptyList();
}
```

### 更新条件缺失

动态更新一定要保证 `where` 条件存在。没有条件的 `update` 和 `delete` 属于事故，不属于“手滑”。

## 使用建议

- 简单 CRUD 可以用 MyBatis-Plus 或代码生成器减少重复。
- 复杂 SQL、报表、跨库差异明显的查询，原生 MyBatis XML 更可控。
- Mapper 方法参数超过两个时，优先使用 DTO 或 `@Param` 明确命名。
- 查询字段不要长期使用 `select *`，字段变化会影响映射和网络开销。
- 写复杂动态 SQL 时，优先保证生成 SQL 可读，再追求抽象复用。

MyBatis 的优势不在于“少写 SQL”，而在于**让 SQL 可控、让映射稳定、让 JDBC 细节退到幕后**。把这个边界把握住，它会是很可靠的工具；把所有逻辑都塞进 XML，它也会非常诚实地变成另一种形式的混乱。
