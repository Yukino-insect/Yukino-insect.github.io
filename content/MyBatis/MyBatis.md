+++
date = '2025-09-20T18:25:57+08:00'
draft = false
title = 'MyBatis'
+++

MyBatis 是一个**优秀的持久层框架**，主要用于**简化 JDBC 操作**和 **SQL 映射**。它的定位是**半自动 ORM（对象关系映射，Object Relational Mapping）框架**

#### MyBatis 的核心特点

1. **SQL 映射（SQL Mapping）**
   - 开发者自己写 SQL 语句，MyBatis 负责将 **SQL 与 Java 对象字段映射**。
   - 保证了 SQL 的灵活性，不像 Hibernate 那样完全自动生成 SQL。
2. **避免 JDBC 繁琐代码**
   - 传统 JDBC 需要写很多模板代码（连接、PreparedStatement、ResultSet 映射等）。
   - MyBatis 通过**配置文件（XML）或注解**，自动完成参数设置与结果映射。
3. **灵活的配置方式**
   - 可以在 **XML 文件**里写 SQL，也可以直接在 **Mapper 接口**里用注解写 SQL。
4. **支持动态 SQL**
   - 通过 `&lt;if&gt;`、`&lt;choose&gt;`、`&lt;foreach&gt;` 等标签，可以根据条件拼接 SQL。
5. **集成方便**
   - 常与 Spring / Spring Boot 配合使用，整合简单。

这里，我们先只讲纯 Mybatis 项目

创建一个 maven 项目，引入依赖

```xml
    <dependency>
        <groupId>org.mybatis</groupId>
        <artifactId>mybatis</artifactId>
        <version>3.5.19</version>
    </dependency>
```

使用 Mybatis 时，需要一个全局配置文件`mybatis-config.xml`，这里面要配置很多全局变量，Mybatis 也靠它来启动和加载 Mapper

`mybatis-config.xml` 里配置：

- 数据源
- 事务
- 别名
- 插件
- `&lt;mappers&gt;`（告诉 MyBatis 去哪里加载 SQL 映射文件）。

在 resources 目录下配置`mybatis-config.xml`

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE configuration
        PUBLIC "-//mybatis.org//DTD Config 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-config.dtd">
<!-- 根标签 -->
<configuration>
    <properties>
        <property name="driver" value="com.mysql.jdbc.Driver"/>
        <property name="url" value="jdbc:mysql://127.0.0.1:3306/mybatis-110?useUnicode=true&amp;characterEncoding=utf-8&amp;allowMultiQueries=true"/>
        <property name="username" value="root"/>
        <property name="password" value="123456"/>
    </properties>

    <!-- 环境，可以配置多个，default：指定采用哪个环境 -->
    <environments default="test">
        <!-- id：唯一标识 -->
        <environment id="test">
            <!-- 事务管理器，JDBC类型的事务管理器 -->
            <transactionManager type="JDBC" />
            <!-- 数据源，池类型的数据源 -->
            <dataSource type="POOLED">
                <property name="driver" value="com.mysql.jdbc.Driver" />
                <property name="url" value="jdbc:mysql://127.0.0.1:3306/mybatis-110" />
                <property name="username" value="root" />
                <property name="password" value="123456" />
            </dataSource>
        </environment>
        <environment id="development">
            <!-- 事务管理器，JDBC类型的事务管理器 -->
            <transactionManager type="JDBC" />
            <!-- 数据源，池类型的数据源 -->
            <dataSource type="POOLED">
                <property name="driver" value="${driver}" /> <!-- 配置了properties，所以可以直接引用 -->
                <property name="url" value="${url}" />
                <property name="username" value="${username}" />
                <property name="password" value="${password}" />
            </dataSource>
        </environment>
    </environments>
</configuration>
```

配置中可以设置 properties 引用值

`&lt;environments&gt;`中可以配置不同生产环境下的配置，通过`default`用来指定使用哪个。

`&lt;environment&gt;`下是来配置 mybatis 的全局变量的。

接下来创建一个实体类

```java
public class User {

    private int id;

    private String userName;

    private int age;

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getUserName() {
        return userName;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }

    public int getAge() {
        return age;
    }

    public void setAge(int age) {
        this.age = age;
    }

    @Override
    public String toString() {
        return "User{" +
                "id=" + id +
                ", userName='" + userName + '\'' +
                ", age=" + age +
                '}';
    }
}
```

接着，创建它的 dao

```java
public interface UserDao {

    List<User> findAll();

    User findById(int id);

    void save(User user);

    void delete(int id);

    void update(User user);
}
```

daoimpl

```java
public class UserDaoImpl implements UserDao {

    private SqlSession sqlSession;

    public UserDaoImpl() {

    }

    public UserDaoImpl(SqlSession sqlSession) {
        this.sqlSession = sqlSession;
    }

    @Override
    public List<User> findAll() {
        return sqlSession.selectList("UserMapper.findAll");
    }

    @Override
    public User findById(int id) {
        return sqlSession.selectOne("UserMapper.findById", id);
    }

    @Override
    public void save(User user) {
        sqlSession.insert("UserMapper.save", user);
    }

    @Override
    public void delete(int id) {
        sqlSession.delete("UserMapper.delete", id);
    }

    @Override
    public void update(User user) {
        sqlSession.update("UserMapper.update", user);
    }
}
```

在 resource/mapper 目录下创建一个`UserMapper.xml`的 sql 映射文件

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper
        PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<!-- mapper:根标签，namespace：命名空间，随便写，一般保证命名空间唯一 -->
<mapper namespace="UserMapper">
    <!-- statement，内容：sql语句。id：唯一标识，随便写，在同一个命名空间下保持唯一
       resultType：sql语句查询结果集的封装类型,tb_user即为数据库中的表
     -->
    <select id="findById" resultType="com.jh.entity.User">
        select * from user where id = #{id}
    </select>

    <select id="findAll" resultType="com.jh.entity.User">
        select * from user
    </select>

    <insert id="save">
        insert into user (user_name, age) VALUE (#{userName}, #{age})
    </insert>

    <delete id="delete">
        delete from user where id = #{id}
    </delete>

    <update id="update" parameterType="int">
        update user set user_name = #{UserName}, age = #{age} where id = #{id}
    </update>
</mapper>
```

在 mybatis-config.xml 中添加该文件，使 myabtis 能够加载它

```java
<mappers>
    <mapper resource="mapper/UserMapper.xml"/>
</mappers>
```

做测试

```java
public class Main {

    public static void main(String[] args) throws IOException {
        String resource = "mybatis-config.xml";
        try (InputStream inputStream = Resources.getResourceAsStream(resource)) {
            SqlSessionFactory sqlSessionFactory = new SqlSessionFactoryBuilder().build(inputStream);
            try (SqlSession sqlSession = sqlSessionFactory.openSession()) {
                UserDaoImpl userDao = new UserDaoImpl(sqlSession);
                User user1 = new User();
                user1.setUserName("雪之下雪乃");
                user1.setAge(18);
                User user2 = new User();
                user2.setUserName("牧濑红莉栖");
                user2.setAge(18);
                userDao.save(user1);
                userDao.save(user2);
                sqlSession.commit();
                List<User> users = userDao.findAll();
                for (User user : users) {
                    System.out.println(user);
                }
                System.out.println(userDao.findById(1));
            }
        }
    }
}
```

现在现总结一下 mybatis 的使用步骤：
mybatis 通过加载配置文件来获取一个 SqlSessionFactory，再由它获取一个 SqlSession。最后由 SqlSession 操作数据库。

**SqlSessionFactoryBuilder**

- **作用**：用来解析 MyBatis 配置文件（`mybatis-config.xml`），创建 `SqlSessionFactory`。
- **特点**：
  - 一次性使用，不需要保留。
  - 线程不安全。

 **SqlSessionFactory**

- **作用**：是一个“工厂”，用来生产 `SqlSession` 对象。
- **特点**：
  - 全局唯一，一般应用启动时创建一次，整个项目复用。
  - 线程安全，可以在多个线程中共享。

 **SqlSession**

- **作用**：真正的数据库操作对象，包含执行 SQL 的所有方法。
- **常见方法**：
  - `selectOne()`、`selectList()` -> 查询
  - `insert()`、`update()`、`delete()` -> 写操作
  - `commit()`、`rollback()` -> 事务控制
  - `getMapper()` -> 获取 Mapper 接口代理对象
- **特点**：
  - 线程不安全。
  - 一般是 **方法内获取，用完立即关闭**，不要长时间保存。

在 mybatis 中，事务默认是手动提交的，不会自动提交

当我们通过 `sqlSessionFactory.openSession()` 获取一个 `SqlSession` 时：

- 默认情况下：**`openSession(false)`** -> 事务关闭自动提交，需要手动 `commit()`。

- 如果希望自动提交，可以将 false 改为 true：

  ```
  SqlSession session = sqlSessionFactory.openSession(true);
  ```

  这样每次 `insert`、`update`、`delete` 执行后都会自动提交。

在 mybatis 中有两种方式执行数据库操作，上写的一种是不使用 Mapper 代理的方式，直接调用`selectOne`等方法的方式

```java
try (SqlSession sqlSession = sqlSessionFactory.openSession()) {
    User user = sqlSession.selectOne("UserMapper.findById", 1);
}
```

这种方式的原理是往`selectOne`中传入的是映射文件 mapper 中的 namespace 和 sql 的 id。

mybatis 会根据这个 id 在 **Configuration** 里找到对应的 **MappedStatement**（存放 SQL、参数、返回类型等信息的对象）。

然后执行 JDBC 操作：

- 解析 SQL
- 绑定参数
- 执行 SQL
- 映射结果集到对象

Configuration 和 MappedStatement 类是 MyBatis 的底层对象

**Configuration**

包所在位置：`org.apache.ibatis.session.Configuration`

作用

- 是 MyBatis 的 **全局配置对象**，在加载 `mybatis-config.xml` 和 `mapper.xml` 时创建并填充。
- 里面保存了所有运行所需的信息：
  - 数据源、事务管理器
  - 类型别名、类型处理器（TypeHandler）
  - Mapper 映射关系
  - 所有 SQL 的定义（以 `MappedStatement` 形式存放）

**MappedStatement**

包所在位置：`org.apache.ibatis.mapping.MappedStatement`

作用

- 表示**一个具体的 SQL 配置项**（对应 `&lt;select&gt; / &lt;insert&gt; / &lt;update&gt; / &lt;delete&gt;` 标签）。
- 里面封装了执行 SQL 所需的全部信息：
  - SQL 的 ID（namespace + id）
  - SQL 文本（可以是动态 SQL）
  - 输入参数类型（parameterType）
  - 输出结果映射（resultType / resultMap）
  - SQL 的命令类型（SELECT / UPDATE / INSERT / DELETE）
  - 缓存设置、超时时间等

总结来说

`SqlSessionFactory` 在初始化时，会读取`mybatis-config.xml`生成一个 `Configuration`，其中会加载全局配置和，文件中所涉及的所有 mapper 的映射信息，mapper 信息会映射成一个`MappedStatement`保存。执行 SQL 时就是从 `Configuration` 里取 `MappedStatement` 拿到 SQL 模板和参数映射信息。交给 `Executor` 执行，最终返回结果。

我们在 selectOne 中传入的参数，是如何正确匹配到 sql 中的呢

```bash
SQL: SELECT * FROM user WHERE id = #{id}
            │
            ▼
ParameterMapping("id")   ← 描述占位符
            │
            ▼
ParameterHandler.getParameterValue()
            │
            ▼
Java 值 (123)
            │
            ▼
TypeHandler.setParameter(preparedStatement, index, 123, JDBC_TYPE)
            │
            ▼
PreparedStatement.execute()
```

MyBatis 会解析 SQL 文本，找到所有`#{xxx}`占位符。接着会将每个占位符封装成一个 **`ParameterMapping`** 对象，并将 SQL 中的占位符被替换成 `?`，形成最终可执行的 SQL（`BoundSql.sql`）。

然后`ParameterHandler`会获取 `selectOne` / `update` 等方法的参数，将参数封装成 `ParamMap` 对象，它是一个 map，就是通过其中的 key 和 占位符匹配的。正确匹配获得参数后由`TypeHandler` 根据 Java 类型与 JDBC 类型，将值绑定到 `PreparedStatement` 对应占位符最后调用 `preparedStatement.setXXX(index, value)` 执行 SQL

下面是具体的参数绑定细节

**单参数**（基本类型 / 包装类 / String）

- MyBatis 会自动封装成 `ParamMap`：

  ```
  {"param1": param, "value": param}
  ```

- SQL 中占位符：

  ```
  SELECT * FROM user WHERE id = #{param1}  或 #{value}
  ```

  paramMap 中的 param1 会匹配 sql 中的 param1

- **宽容机制**：

  - 如果你写 `#{任意名字}`，单值参数会直接绑定到占位符上。

**多参数**（Object[] / List / 多个参数）

- MyBatis 自动封装成 `ParamMap`：

  ```
  param1 -&gt; 第一个参数
  param2 -&gt; 第二个参数
  ...
  ```

- 和 SQL 中 `#{param1}`、`#{param2}` 对应

- 不加 `@Param` 的话，不能直接用自定义名字

如果是**对象参数**（JavaBean）

- mybatis 会直接通过反射获取属性值，将属性名和占位符匹配：
  - `#{name}` -> `user.getName()`
  - `#{age}` -> `user.getAge()`

如果是**Map 参数**

- 直接按 key 查找：
  - `#{name}` -> `map.get("name")`
  - `#{age}` -> `map.get("age")`

可以看到，可以传入的参数类型是很多的

上面讲了非代理方法，下面说一下常用的代理方法

当我们执行完上面的代码，看到查询结果时会发现

```bash
User{id=1, userName='null', age=18}
```

名字的值为空，但是数据库中的值确实是存在的。这就要说到**结果集映射机制**

整体流程如下

```bash
SQL 执行 -> JDBC ResultSet -> ResultSetHandler -> TypeHandler -> Java 对象 -> 返回给调用者
```

JDBC PreparedStatement 执行完 SQL后返回 `ResultSet`，**ResultSetHandler** 类会获取结果，读取 ResultSet 的每一行并对其执行**行到对象的映射**

我们在 Mapper XML 中声明了返回对象的类型`&lt;resultType="User"&gt;`，MyBatis 会实例化该对象。然后根据 **ResultMapping** 找到对应的 Java 属性，调用对应的 **TypeHandler** 将列值转换为 Java 类型并将其填充到实例化的对象中。

如果有嵌套对象 (`&lt;association&gt;` / `&lt;collection&gt;`)

MyBatis 会递归调用 ResultSetHandler

如果有 Map 返回类型，会把列名当 key，值填充到 Map 中

最后返回结果

- 如果是 `selectOne()`
  - 返回单个对象
- 如果是 `selectList()`
  - 返回 List&lt;JavaObject&gt;
- 如果是 Map
  - 返回 Map&lt;key, value&gt;

执行流程图：

```bash
SQL 执行 -> JDBC ResultSet
         │
         ▼
ResultSetHandler.handleResultSets()
         │
         ▼
遍历 ResultSet 每行 -> 创建 Java 对象
         │
         ▼
遍历每列 -> TypeHandler 转换值
         │
         ▼
列值设置到对象属性 -> 完成一行映射
         │
         ▼
集合封装 -> 返回给调用者
```

**ResultMapping** 如何处理类和数据库列的匹配

如果 Mapper XML 只写了 `resultType="User"`，MyBatis 会将数据库**列名和属性名做匹配**：

如果是**驼峰映射**

- 数据库列名 `user_name` -> Java 属性 `userName`
- 数据库列名 `id` -> Java 属性 `id`

但是它默认不开启，需要自己手动配置，这就是为什么我们的 userName 属性拿不到值的原因

```xml
<configuration>
  <settings>
    <setting name="mapUnderscoreToCamelCase" value="true"/>
  </settings>
</configuration>
```

我们也可以给查询的数据做别名，这样也能正确的匹配

```xml
<select id="findById" resultType="com.jh.entity.User">
    select id, user_name userName, age from user where id = #{id}
</select>
```

当列名和属性名不一致，或者有嵌套对象时，也可以用 `&lt;resultMap&gt;` 明确映射

```xml
<resultMap id="userMap" type="User">
    <id column="user_id" property="id"/>
    <result column="user_name" property="userName"/>
    <result column="age" property="age"/>
</resultMap>

<select id="findUser" resultMap="userMap">
    SELECT user_id, user_name, age FROM user
</select>
```

接下来我们将 demo 修改成动态代理 Mapper 的模式

非动态代理模式，每个 Mapper 都要手动实现

```java
public interface UserMapper {
    User findById(int id);
}

public class UserMapperImpl implements UserMapper {
    private SqlSession sqlSession;
    public UserMapperImpl(SqlSession sqlSession) {
        this.sqlSession = sqlSession;
    }
    @Override
    public User findById(int id) {
        return sqlSession.selectOne("UserMapper.findById", id);
    }
}
```

而动态代理 Mapper 接口，只需要调用`getMapper()`返回**动态生成的代理对象**无需实现类即可直接执行 SQL，并统一处理参数、结果、缓存和事务，极大简化开发和维护成本。

```java
UserMapper mapper = sqlSession.getMapper(UserMapper.class);
User user = mapper.findById(1);
```

如果希望使用 mybatis 通过的动态代理的接口，就需要 namespace 中的值和需要对应的 Mapper 接口的全路径一致。Mapper中namespace 的定义本身是没有限制的，只要不重复即可，但如果使用 mybatis 的动态代理，则 namespace 必须为 mapper 接口的全路径

```xml
<mapper namespace="com.jh.mapper.UserMapper">
</mapper>
```

mapper 类

```java
public interface UserMapper {

    List<User> findAll();

    User findById(int id);

    void save(User user);

    void delete(int id);

    void update(User user);
}
```

使用

```java
public class Main {

    public static void main(String[] args) throws IOException {
        String resource = "mybatis-config.xml";
        try (InputStream inputStream = Resources.getResourceAsStream(resource)) {
            SqlSessionFactory sqlSessionFactory = new SqlSessionFactoryBuilder().build(inputStream);
            try (SqlSession sqlSession = sqlSessionFactory.openSession()) {
                UserMapper userMapper = sqlSession.getMapper(UserMapper.class);
                List<User> users = userMapper.findAll();
                for (User user : users) {
                    System.out.println(user);
                }
            }
        }
    }
}
```

生成 Mapper 类的代理过程是怎样的

```bash
Mapper 接口方法调用
          │
          ▼
MapperProxy.invoke()
          │
          ▼
MappedStatement ← Mapper XML / 注解
          │
          ▼
SqlSession 执行 SQL
          │
          ▼
Executor -> StatementHandler -> JDBC PreparedStatement
          │
          ▼
ParameterHandler 绑定参数 -> ? 占位符
          │
          ▼
SQL 执行 -> ResultSet
          │
          ▼
ResultSetHandler -> TypeHandler -> Java对象
          │
          ▼
MapperProxy 返回结果 -> 业务层
```

当调用该方法时

```
UserMapper mapper = sqlSession.getMapper(UserMapper.class);
```

`sqlSession.getMapper(Class&lt;T&gt; type)` 内部其实执行的是这样的程序

```
MapperProxyFactory<T> factory = new MapperProxyFactory<>(type);
return factory.newInstance(sqlSession);
```

通过 **MapperProxyFactory** 创建代理对象 `MapperProxy` 接着调用时

```
User user = mapper.findById(123);
```

MapperProxy 的 `invoke()` 方法会被触发。该程序会获取`findById`**方法对应的 MappedStatement**，然后执行和非代理方法`selectOne()`的流程

**`MapperProxyFactory`**

- 负责为 Mapper 接口生成 **动态代理对象**。
- 不需要手写实现类，就可以让接口方法直接执行 SQL。

**`MapperProxy`**

实际创建代理对象使用的是 **JDK 动态代理**：

```
Proxy.newProxyInstance(
    type.getClassLoader(),
    new Class[]{type},
    new MapperProxy<>(sqlSession, type, methodCache)
)
```

- 代理对象类型是 **MapperProxy**，实现了 Mapper 接口
- 拦截所有接口方法调用

 当调用`MapperProxy.invoke()`时，所有 Mapper 方法调用都会被代理对象的 `invoke()` 方法拦截，接着将接口方法调用转化为 MyBatis SQL 执行流程

**我们再看一下`MappedStatement`的生成和使用**

作用

- 核心对象，记录每个 Mapper 方法对应的 SQL 与映射规则
- 包含信息：
  - SQL 语句或 SQL ID（namespace + id）
  - SQL 类型（SELECT / INSERT / UPDATE / DELETE）
  - 返回类型（resultType / resultMap）
  - 参数类型（parameterType）
  - 缓存策略 / KeyGenerator / fetchSize / timeout 等

生成流程

1. **全局配置加载时**：
   - `SqlSessionFactory` 解析 Mapper XML
   - 每个 `&lt;select&gt;` / `&lt;insert&gt;` / `&lt;update&gt;` / `&lt;delete&gt;` -> 封装为 `MappedStatement`
   - 存储在 `Configuration.mappedStatements` Map 中
2. **使用阶段**：
   - **MapperProxy.invoke()** 调用方法时：
     - 根据方法 ID 从 Configuration 获取 `MappedStatement`
   - **Executor** 执行 SQL 时：
     - 从 `MappedStatement` 获取 SQL 文本 / 参数映射 / ResultMap
   - **ParameterHandler**：
     - 读取 MappedStatement 的参数信息，绑定方法参数到 SQL 占位符
   - **ResultSetHandler**：
     - 读取 MappedStatement 的返回类型 / ResultMap，将 JDBC ResultSet 转 Java对象

**讲一下 Executor** 执行器

MyBatis 把 SQL 解析、参数绑定、结果映射的职责拆分到不同类，最后由Executor 统一调度。

```bash
Executor
   │
   ├─ StatementHandler.prepare() -> 生成 JDBC PreparedStatement
   │
   ├─ ParameterHandler.setParameters() -> 将方法参数绑定到 ? 占位符
   │
   ├─ StatementHandler.execute() -> 执行 SQL
   │
   └─ ResultSetHandler.handleResultSets() -> 将 ResultSet 映射成 Java 对象
```

现在来描述一下 Executor 调用 ParameterHandler、StatementHandler、ResultSetHandler 等组件完成 SQL 执行和结果映射的过程：

**Executor** 是 MyBatis 执行 SQL 的顶层入口，它会接收 MappedStatement、参数、ResultHandler 等信息，调用 StatementHandler 完成 SQL 执行。

**StatementHandler** 在执行时会准备 SQL 语句，即准备 PreparedStatement 或 CallableStatement 执行类，然后 **ParameterHandler**

会将方法参数集 **ParaMap** 映射到 SQL 占位符 `?`，会使用 TypeHandler 处理类型转换，最终的效果会是：

```
preparedStatement.setInt(1, 123);
preparedStatement.setString(2, "abc");
```

执行**PreparedStatement.execute()**，JDBC 执行 SQL -> 返回 ResultSet

**ResultSetHandler**，会将 JDBC ResultSet 转换成 Java 对象

最终返回结果

##### 使用 `@Param` 注解优化参数映射

在使用 mapper 动态代理的时候可以使用`@Param("xxx")` 为参数指定名字，这时SQL 中可以直接使用名字，增强可读性

```java
public interface UserMapper {
    User findByIdAndName(@Param("id") int id, @Param("name") String name);
}
```

XML:

```xml
<select id="findByIdAndName" resultType="User">
    SELECT * FROM user WHERE id = #{id} AND name = #{name}
</select>
```

MyBatis 会将方法参数包装成 `ParamMap`：

```
{id=1, name="Tom"}
```

占位符 `#{id}` 和 `#{name}` 就可以正确匹配

&gt; 拦截器：
&gt;
&gt; MyBatis 允许在已映射语句执行过程中的某一点进行拦截调用。默认情况下，MyBatis 允许使用插件来拦截的方法调用包括：
&gt;
&gt; ```
&gt; Executor (update, query, flushStatements, commit, rollback, getTransaction, close, isClosed)
&gt; ParameterHandler (getParameterObject, setParameters)
&gt; ResultSetHandler (handleResultSets, handleOutputParameters)
&gt; StatementHandler (prepare, parameterize, batch, update, query)
&gt; ```
&gt;
&gt; 现在一些MyBatis 插件比如PageHelper都是基于这个原理，有时为了监控sql执行效率，也可以使用插件机制

`#{}`是占位符（PreparedStatement 参数绑定），会被替换为 `?`，通过 **PreparedStatement.setXXX()** 绑定参数

特点：

1. **防止 SQL 注入**
2. 与参数名 **可对应**（当有 `@Param` 时使用名字匹配）
3. 单参数方法时，**自动对应参数值**

`${}`本质是**字符串拼接**，不是占位符，它会直接把参数值拼到 SQL 中。常用于 **动态表名、列名**，不做类型转换，也不防 sql 注入

#### MyBatis 支持动态 sql

**if** 条件如果成立，则把 sql 字符串拼接上

```xml
<select id="queryUserList" resultType="com.zpc.mybatis.pojo.User">
    select * from tb_user WHERE sex=1
    <if test="name!=null and name.trim()!=''">
      and name like '%${name}%'
    </if>
</select>
```

**choose when otherwise** 相当于 Java 的 switch

```xml
<select id="queryUserListByNameOrAge" resultType="com.zpc.mybatis.pojo.User">
    select * from tb_user WHERE sex=1
    <!--
    1.一旦有条件成立的when，后续的when则不会执行
    2.当所有的when都不执行时,才会执行otherwise
    -->
    <choose>
        <when test="name!=null and name.trim()!=''">
            and name like '%${name}%'
        </when>
        <when test="age!=null">
            and age = #{age}
        </when>
        <otherwise>
            and name='鹏程'
        </otherwise>
    </choose>
</select>
```

**where** 多条件查询

```xml
<select id="queryUserListByNameAndAge" resultType="com.zpc.mybatis.pojo.User">
    select * from tb_user
    <!--如果多出一个and，会自动去除，如果缺少and或者多出多个and则会报错-->
    <where>
        <if test="name!=null and name.trim()!=''">
            and name like '%${name}%'
        </if>
        <if test="age!=null">
            and age = #{age}
        </if>
    </where>
</select>
```

**foreach** 遍历

```xml
<!-- 将传入的 String[] 遍历，然后拼接到了 sql 上 -->
<select id="queryUserListByIds" resultType="com.zpc.mybatis.pojo.User">
    select * from tb_user where id in
    <foreach collection="ids" item="id" open="(" close=")" separator=",">
        #{id}
    </foreach>
</select>
```

**如果存在对象嵌套**，结果集的映射该如何处理

```java
class User {
    private String name;
    private Account account;
}
```

使用`&lt;resultMap&gt;`来映射字段

#### MyBatis 的缓存

MyBatis 有 **两级缓存**：

- 一级缓存
  - MyBatis 一级缓存的生命周期和 SqlSession 一致。
  - MyBatis 一级缓存内部设计简单，只是一个没有容量限定的 HashMap，在缓存的功能性上有所欠缺。
  - MyBatis的一级缓存最大范围是 SqlSession 内部，有多个 SqlSession 或者分布式的环境下，数据库写操作会引起脏数据，建议设定缓存级别为Statement。
- 二级缓存
  - MyBatis 的二级缓存相对于一级缓存来说，实现了`SqlSession`之间缓存数据的共享，同时粒度更加的细，能够`namespace`级别，通过 Cache 接口实现类不同的组合，对 Cache 的可控性也更强。
  - MyBatis 在多表查询时，极大可能会出现脏数据，有设计上的缺陷，安全使用二级缓存的条件比较苛刻。
  - 在分布式环境下，由于默认的 MyBatis Cache 实现都是基于本地的，分布式环境下必然会出现读取到脏数据，需要使用集中式缓存将 MyBatis 的 Cache 接口实现，有一定的开发成本，直接使用Redis、Memcached 等分布式缓存可能成本更低，安全

使用二级缓存

配置缓存 在Mapper XML 中开启

```
<mapper namespace="com.example.UserMapper">
    <cache
        eviction="LRU"      <!-- 缓存回收策略（LRU、FIFO、Soft、Weak） -->
        flushInterval="60000" <!-- 自动刷新间隔，单位毫秒 -->
        size="512"           <!-- 缓存对象数量上限 -->
        readOnly="false"/>   <!-- 是否只读 -->
</mapper>
```

配置说明

| 属性          | 说明                                         |
| ------------- | -------------------------------------------- |
| eviction      | 缓存回收策略                                 |
| flushInterval | 自动刷新间隔                                 |
| size          | 缓存条目上限                                 |
| readOnly      | 是否只读（只读可直接返回对象，否则需要拷贝） |

Mapper 查询方法自动使用二级缓存，更新方法默认会清空当前 namespace 的缓存

```
List<User> users = userMapper.findAll(); // 查询结果放入二级缓存
```

**mybatis 缓存**只**适合**：

- 读多写少的表
- 查询结果复用率高

**不适合**：

- 高并发频繁更新表
- 对实时性要求非常高的场景

接下来，我们使用 Spring 来简化使用 MyBatis 时需要的配置

## 在纯 Spring 中配置 MyBatis

Maven 依赖

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-context</artifactId>
        <version>6.2.7</version>
    </dependency>
    <dependency>
        <groupId>org.mybatis</groupId>
        <artifactId>mybatis</artifactId>
        <version>3.5.19</version>
    </dependency>
    <dependency>
        <groupId>org.mybatis</groupId>
        <artifactId>mybatis-spring</artifactId>
        <version>3.0.5</version>
    </dependency>
    <dependency>
        <groupId>com.mysql</groupId>
        <artifactId>mysql-connector-j</artifactId>
        <version>9.1.0</version>
    </dependency>
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-jdbc</artifactId>
        <version>6.2.7</version>
    </dependency>
    <dependency>
        <groupId>com.alibaba</groupId>
        <artifactId>druid</artifactId>
        <version>1.2.24</version>
    </dependency>
</dependencies>
```

`mybatis-spring`是 spring 集成 myabtis 需要的依赖

`mysql-connector-j`是 MySQL JDBC 驱动，提供数据库连接

`spring-jdbc` 在这里的作用主要是 **提供 Spring 对 JDBC 的支持和封装**，可以更方便地管理数据库连接、事务，以及避免手动编写大量 JDBC 样板代码。

`spring-jdbc` 提供了：

1. **DataSource 管理**
   - Spring 可以创建和管理数据库连接池（如 HikariCP、DBCP）
2. **JdbcTemplate**
   - 封装了 JDBC 的查询、更新、批量操作
   - 自动管理连接、PreparedStatement、ResultSet 的关闭
   - 异常统一转换为 Spring DataAccessException 系列
3. **事务支持**
   - Spring 的声明式事务（`@Transactional`）依赖于 JDBC 事务管理器
   - `spring-jdbc` 提供了 `DataSourceTransactionManager`事务管理器
4. **异常处理**
   - JDBC 异常被转换成 Spring 的统一异常体系，不用手动 try-catch SQLExceptions

虽然 MyBatis 本身可以直接操作 JDBC，但在 **Spring 集成 MyBatis** 时，`spring-jdbc` 主要作用是：

1. **提供数据源和事务管理**

```java
@Bean
public DataSourceTransactionManager transactionManager(DataSource dataSource) {
    return new DataSourceTransactionManager(dataSource);
}
```

- `DataSourceTransactionManager` 来自 `spring-jdbc`
- 支持 Spring 的声明式事务 (`@Transactional`)

2. **封装 JDBC 资源管理**

- MyBatis 的 `SqlSessionFactoryBean` 内部会依赖 Spring 的 `DataSource`
- Spring 自动管理连接释放、事务提交/回滚

使用 spring 注解的方式配置 MyBatis

`mybatis-config.xml`配置类由**`@Configuration` 配置类**代替

```java
@Configuration
@MapperScan("com.jh.mapper")
public class MybatisConfig {

    @Bean
    public DataSource getDataSource() {
        DruidDataSource ds = new DruidDataSource();
        ds.setDriverClassName("com.mysql.cj.jdbc.Driver");
        ds.setUrl("jdbc:mysql://127.0.0.1:3306/db");
        ds.setUsername("root");
        ds.setPassword("Hanjie1012");
        return ds;
    }

    @Bean
    public SqlSessionFactory sqlSessionFactory(DataSource dataSource) throws Exception {
        SqlSessionFactoryBean factoryBean = new SqlSessionFactoryBean();
        factoryBean.setDataSource(dataSource);
        return factoryBean.getObject();
    }

    @Bean
    public DataSourceTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}
```

基础的 mybatis 是在`myabtis-config.xml`配置数据源和事务。在 spring 项目中，数据源、事务和`SqlSession`都交由 spring 容器管理，极大简化了配置方式和代码耦合度

Mapper 接口使用注解

```java
@Mapper
public interface UserMapper {

    @Select("select id, user_name userName, age from user")
    List<User> findAll();

    @Select("select id, user_name userName, age from user where id = #{id}")
    User findById(int id);
}
```

**Spring 是如何判断一个接口是不是 mapper 接口，并生成代理对象的**

两个核心注解：

**`@MaperScan`** 用于扫描指定包下的接口，并对标记了 `@Mapper` 或者没有标记的接口生成 **MapperFactoryBean**，然后注册到 Spring 容器

它内部用到的核心类是：

- **`ClassPathMapperScanner`**（继承 `ClassPathBeanDefinitionScanner`）
- 这个类会扫描指定包下的所有类，会进行以下逻辑：
  1. 判断这个类是不是接口。
  2. 判断是否有 `@Mapper` 注解，或者（根据配置）无条件当作 Mapper 接口处理。
  3. 把这个接口注册成一个 `BeanDefinition`，Bean 类型不是接口本身，而是 **`MapperFactoryBean`**

`@Mapper` 是 MyBatis 提供的注解，用于标记一个接口是 Mapper 接口

要知道`@Mapper`只是一个 **标记注解**，用来帮助 `MapperScanner` 判断哪些接口是 Mapper。在**默认配置下**，`@MapperScan` 会把所有接口都当成 Mapper 处理，所以 `@Mapper` **可加可不加**。

但是在 spring 环境中，`MapperScan`是必须的，它会触发 **包扫描**，找到所有符合条件的接口，并为它们注册一个 **`MapperFactoryBean`**。没有 `@MapperScan`，Spring 容器里根本不会有 Mapper 的 Bean，自然也就无法注入

**具体过程**：Spring 扫描指定包下的接口，为每个接口生成一个 **`MapperFactoryBean&lt;T&gt;`**，并将其注册到 Spring 容器中。当我们注入 Mapper 的时候，`MapperFactoryBean`会在内部调用 MyBatis 的 `SqlSession.getMapper(MapperInterface.class)` 方法，生成接口的代理对象（`MapperProxy`）并返回 `MapperProxy`。所以从容器中拿到的 Mapper 实际上是一个 JDK 动态代理对象。

在 spring 中，我们无需显示的调用管理 SqlSessin，在执行 SQL 时由 MyBatis-Spring 自动获取、关闭 SqlSession

综上所述：**Spring 容器里注册的是 `MapperFactoryBean`，真正代理逻辑是 MyBatis 的 `MapperProxy`**

`@Select()`是使用注解的方式来实现简单的 sql 查询，之前的`mapper.xml`方式仍保留，且不做变化，适用于复杂 sql

Service 层调用

```java
@Service
public class UserService {

    @Autowired
    private UserMapper userMapper;

    @Transactional
    public List<User> findAll() {
        return userMapper.findAll();
    }
}
```

`@Transactional` 注解

**声明式事务**

- 概念：通过**配置或注解**来声明哪些方法需要事务管理，由 Spring 框架在运行时自动控制事务的开启、提交和回滚。

- **特点**：
  1. **无需手动编写 commit/rollback**
  2. **业务代码和事务逻辑分离**
  3. 可针对类、方法级别控制事务

原理

Spring 的声明式事务底层依赖 **AOP（代理）机制**：

1. 给目标方法使用事务注解
2. Spring 为目标对象生成代理（JDK 动态代理或 CGLIB）
3. 调用方法时：
   - 代理先开启事务（TransactionManager）
   - 执行业务方法
   - 方法正常返回 -> 提交事务
   - 方法抛异常 -> 回滚事务

最后调用

```java
@Configuration
@ComponentScan("com.jh")
@Import(MybatisConfig.class)
public class App {
    public static void main(String[] args) {
        ApplicationContext context = new AnnotationConfigApplicationContext(App.class);
        UserService userService = (UserService) context.getBean("userService");
        List<User> users = userService.findAll();
        for (User user : users) {
            System.out.println(user);
        }
    }
}
```

我们的`App`类导入了`MyBatisConfig`配置，所以也加上`@Configuration`，表示这是一个配置类入口。但是也可以不加。`@Configuration` 的作用是：告诉 Spring 这是一个 **配置类**，里面可能会有 `@Bean`、`@ComponentScan`、`@Import` 等注解。并没有其他作用。

`AnnotationConfigApplicationContext` 是 Spring 提供的一个容器实现，它主要用来加载 **基于注解的配置类**，区别于：

- `ClassPathXmlApplicationContext` -> 加载 XML 配置
- `FileSystemXmlApplicationContext` -> 加载磁盘路径下的 XML
- `AnnotationConfigApplicationContext` -> 加载 `@Configuration`、`@ComponentScan`、`@Import` 等注解驱动的配置

当执行以下代码时

```java
ApplicationContext context = new AnnotationConfigApplicationContext(App.class);
```

它会做几件事：

1. 把 `App.class` 当作一个配置类解析。
2. 因为 `App` 上有 `@Import(MybatisConfig.class)`，所以会再加载 `MybatisConfig`。
3. `MybatisConfig` 里定义了 DataSource、SqlSessionFactory、事务管理器。
4. `@MapperScan("com.jh.mapper")` 会扫描 Mapper 接口并注册到 Spring 容器。
5. 最终容器里会有一个 `UserMapper` 代理对象，所以 `context.getBean(UserMapper.class)` 可以成功。

所以该类的作用是加载一个配置类，将该类所配置的 Bean 都注册到 Spring IoC 容器中。

## Spring Boot 项目中配置 MyBatis

接下来我们在spring boot 中配置以下 MyBatis

首先看一下 Maven 依赖

```xml
<dependencies>
    <dependency>
        <groupId>org.mybatis.spring.boot</groupId>
        <artifactId>mybatis-spring-boot-starter</artifactId>
        <version>3.0.5</version>
    </dependency>
    <dependency>
        <groupId>com.mysql</groupId>
        <artifactId>mysql-connector-j</artifactId>
        <version>9.1.0</version>
    </dependency>
    <dependency>
        <groupId>com.alibaba</groupId>
        <artifactId>druid</artifactId>
        <version>1.2.24</version>
    </dependency>
    <dependency>
        <groupId>org.slf4j</groupId>
        <artifactId>slf4j-api</artifactId>
        <version>2.0.17</version>
    </dependency>
</dependencies>
```

`mybatis-spring-boot-starter` 是 **MyBatis 官方提供的 Spring Boot Starter**，核心作用是：

1. **自动配置 MyBatis**
   - 自动创建 `SqlSessionFactory`
   - 自动创建 `SqlSessionTemplate`（线程安全的 SqlSession）
   - 自动扫描 Mapper 接口并生成 MapperProxy
2. **整合 Spring Boot 特性**
   - 可以直接使用 Spring Boot 的 **数据源配置**（`spring.datasource.*`）
   - 支持 Spring 的 **声明式事务**（`@Transactional`），并且也是自动创建配置

Spring Boot 推荐使用 **application.properties** 或 **application.yml**：

```yaml
spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://localhost:3306/db
    username: root
    password: Hanjie1012
    type: com.alibaba.druid.pool.DruidDataSource
    
mybatis:
  type-aliases-package: com.example.entity
```

上面配置了数据库连接池的参数

mybatis 的一些参数

Mapper 接口仍然使用 @Mapper 注解方式

Spring Boot 与纯 Spring 项目相比，简化点主要有：

| 功能              | 纯 Spring 配置                        | Spring Boot 配置                     |
| ----------------- | ------------------------------------- | ------------------------------------ |
| SqlSessionFactory | 手动配置 Bean                         | 自动配置，无需手动定义               |
| SqlSession        | 手动获取                              | 自动注入 Mapper 接口，代理对象已管理 |
| 数据源            | 手动配置 DataSource Bean              | 配置 application.yml 即可            |
| 事务管理          | 手动配置 DataSourceTransactionManager | 自动配置，可用 `@Transactional`      |

启动一个 Spring Boot 项目

```java
@SpringBootApplication
public class App {

    public static void main(String[] args) {
        ApplicationContext context = SpringApplication.run(App.class, args);
        UserService userService = context.getBean(UserService.class);
        userService.findAll().forEach(System.out::println);
    }
}
```

我们可以看到，项目中并没有显示的注明`@MapperScan`，只是给 Mapper 接口标注上了`@Mapper`注解，spring boot 却成功的注册了 Mapper，这是因为**`mybatis-spring-boot-starter` 做了自动配置**。

`mybatis-spring-boot-starter`内部带了一个**自动配置类**：`org.mybatis.spring.boot.autoconfigure.MybatisAutoConfiguration`

它的作用是：

检测工程里有 **`@Mapper` 接口**，就会自动注册`MapperScannerConfigurer`类，然后扫描并注册这些接口

所以即使没写 `@MapperScan`，Spring Boot 也能识别 `Mapper`。

`MapperScannerConfigurer` 是 **MyBatis-Spring 提供的一个 BeanDefinition 注册器**。
 类全名：

```java
org.mybatis.spring.mapper.MapperScannerConfigurer
```

它的核心任务就是：

- 扫描指定包路径下的接口
- 识别出 **Mapper 接口**
- 为这些接口生成对应的 **MapperFactoryBean**
- 注册到 Spring 容器里，这样就能通过 `@Autowired` 或 `getBean()` 拿到 Mapper 代理对象了

**@MapperScan** 就是自动注册该类

## MyBatis-Plus

MyBatis-Plus 是基于 MyBatis 框架的一个增强工具，主要目的是简化 MyBatis 的开发过程，提供更加简洁、方便的 CRUD 操作。它是在保留 MyBatis 强大功能的基础上，通过封装和优化一些常见操作来提高开发效率。

MyBatis-Plus 提供了许多开箱即用的功能，包括自动 CRUD 代码生成、分页查询、性能优化、以及支持多种数据库。与 MyBatis 相比，MyBatis-Plus 的 部分 核心特性包括：

1. **无侵入设计**：不会改变 MyBatis 原有的 API 和使用方式，可以自由选择 MyBatis 和 MyBatis-Plus 的功能。
2. **自动 CRUD**：通过 `BaseMapper` 和 `ServiceImpl` 接口，MyBatis-Plus 提供了一系列 CRUD 操作的方法，如 `insert`、`delete`、`update` 和 `select`，减少了重复的 SQL 编写工作。
3. **条件构造器**：MyBatis-Plus 提供了条件构造器（如 `QueryWrapper`），可以通过链式编程方式轻松构建复杂的查询条件。

现在我们来通过一个小 demo 来学习一下

创建一个 maven 项目

```xml
<dependencies>
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
    <dependency>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok</artifactId>
        <version>1.18.34</version>
    </dependency>
</dependencies>
```

这里我们只和 spring boot 集成

我们引入的依赖有

**`mybatis-plus-boot-starter`**：是 **MyBatis-Plus 官方提供的 Spring Boot Starter**，用于**在 Spring Boot 中零配置集成 MyBatis-Plus**。

在 Maven 里，它本质上是一个聚合依赖，内部包含了几个核心包：

- `mybatis-plus-core`
   MP 的核心功能（CRUD 封装、Wrapper 条件构造器、分页插件等）
- `mybatis-plus-extension`
   MP 的增强功能（自动填充、乐观锁、多租户、代码生成器）
- `mybatis-spring-boot-starter`（MyBatis 官方的）
   负责 Spring Boot 和 MyBatis 的基础整合（数据源、事务、Mapper 扫描）

所以只要加上一个 `mybatis-plus-boot-starter`，MyBatis 和 MyBatis-Plus 都能用

我们在使用 **MyBatis**，需要自己配置这些东西：

- `DataSource`（数据源）
- `SqlSessionFactory`
- `SqlSessionTemplate`
- `MapperScan`

但是引入 **`mybatis-plus-boot-starter`** 后：

- Spring Boot 自动读取 `application.yml` 的数据源配置
- 自动创建 **Druid/Hikari 数据源**
- 自动生成 **SqlSessionFactory**
- 自动扫描 `Mapper` 接口（不用写 `@MapperScan` 也行）
- 自动装配 MyBatis-Plus 的增强功能（分页插件、逻辑删除、Wrapper 查询等）

**`lombok`** 是一个 **Java 编译时期的工具库**，通过注解（Annotation）来**自动生成样板代码**，比如 getter/setter、构造方法、toString、equals、hashCode、日志对象等。

它的目标就是**减少冗余代码，让类更简洁**。

**常见注解及作用**

数据类相关

- `@Getter` / `@Setter`
   自动生成 getter/setter 方法
- `@Data`
   相当于 `@Getter + @Setter + @ToString + @EqualsAndHashCode + @RequiredArgsConstructor`
- `@ToString`
   自动生成 `toString()` 方法
- `@EqualsAndHashCode`
   自动生成 `equals()` 和 `hashCode()`
- `@AllArgsConstructor` / `@NoArgsConstructor` / `@RequiredArgsConstructor`
   自动生成构造方法

 Builder 模式

- `@Builder`
   让对象可以用链式的 **Builder 模式** 构造

  ```java
  User user = User.builder()
                  .name("Alice")
                  .age(18)
                  .build();
  ```

日志

- `@Slf4j`
   会自动注入一个 `private static final Logger log = LoggerFactory.getLogger(类名.class)`

  ```java
  @Slf4j
  public class Test {
      public void run() {
          log.info("运行成功！");
      }
  }
  ```

了解完依赖后，简单配置一下数据源

```yaml
spring:
  datasource:
    type: com.zaxxer.hikari.HikariDataSource
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://localhost:3306/db
    username: root
    password: Hanjie1012
```

我们在上述依赖中并没有注入 `hikari`，为什么这里可以使用呢，因为 spring boot 内置默认的数据源就是它
接下来看一下 entity 实例

```java
@Data
@TableName("user")
public class User {

    @TableId
    private int id;

    @TableField("user_name")
    private String name;

    @TableField("age")
    private int age;
}
```

`@Data` 是 lombok 注解，不管，但是出现了一些其他注解，在原生的 mybatis 中可没有。

**这些注解是 mybatis-plus 定义的字段映射注解**，用来解决 mybatis-plus 的 **java 实例和数据库表的映射关系**

MyBatis-Plus 的映射关系依赖两个核心原则：

1. **表名与类名的映射**
   - 默认规则：`UserInfo` -> `user_info`（驼峰转下划线，全部小写）
   - 可通过注解 `@TableName` 显式指定表名
2. **字段与列名的映射**
   - 默认规则：Java 字段 `userName` -> 数据库列 `user_name`
   - 可通过注解 `@TableField("user_name")` 显式指定
   - 主键必须用 `@TableId` 注解

&gt; 注意：**驼峰映射需开启 `map-underscore-to-camel-case: true`**，否则默认不映射。

注解使用

表名映射

```java
@TableName("user_table")
public class User {
    ...
}
```

- 指定数据库表名为 `user_table`
- 如果类名和表名一致且遵循驼峰规则，可省略

主键映射

```java
@TableId(value = "id", type = IdType.AUTO)
private Long id;
```

- `value`：对应列名
- `type`：主键策略（AUTO、自增、UUID 等）
  - `IdType.AUTO`：数据库自动生成（通常是自增长 ID）。
  - `IdType.INPUT`：用户输入 ID（即需要手动设置）。
  - `IdType.ASSIGN_ID`：由 MyBatis-Plus 生成的 ID（通常是 UUID）。
  - `IdType.ASSIGN_UUID`：生成 UUID（字符串类型的唯一 ID）。

字段映射

```java
@TableField("user_name")
private String userName; // 对应列 user_name
```

忽略字段

```java
@TableField(exist = false)
private String temp; // 不对应数据库列
```

配置自动映射驼峰命名

配置方式：

```yaml
mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
```

效果：

- `user_name` -> `userName`
- `create_time` -> `createTime`
- **不需要显式 `@TableField` 注解**，除非列名特殊

数据类型映射

MP 会根据 **Java 类型 SQL 类型** 自动映射：

| Java 类型           | SQL 类型            |
| ------------------- | ------------------- |
| `String`            | VARCHAR, TEXT       |
| `Integer` / `int`   | INT                 |
| `Long` / `long`     | BIGINT              |
| `Double` / `double` | DOUBLE, DECIMAL     |
| `BigDecimal`        | DECIMAL             |
| `LocalDateTime`     | DATETIME, TIMESTAMP |
| `Date`              | DATE, DATETIME      |

&gt; MP 内部通过 TypeHandler 处理类型转换，如果类型特殊，可以自定义 TypeHandler。

高级特性

1. **逻辑删除**

```java
@TableLogic
private Integer deleted; // 对应数据库的 deleted 列
```

&gt; 逻辑删除并不是把数据库中的记录真正删除掉，而是**在数据库中增加一个标识字段**，记录该条数据是否被“删除”。
&gt;
&gt; - **物理删除（Physical Delete）**：`DELETE FROM user WHERE id=1;` -> 数据真正被删除
&gt; - **逻辑删除（Logical Delete）**：`UPDATE user SET deleted=1 WHERE id=1;` -> 数据仍存在，只是标记为已删除
&gt;
&gt; 逻辑删除的好处：
&gt;
&gt; - 保留历史数据
&gt; - 便于数据恢复
&gt; - 避免外键约束问题
&gt;
&gt; MP 提供 **`@TableLogic` 注解** 来实现逻辑删除。
&gt;
&gt; 数据库表设计
&gt;
&gt; ```sql
&gt; CREATE TABLE user (
&gt;     id BIGINT PRIMARY KEY AUTO_INCREMENT,
&gt;     name VARCHAR(50),
&gt;     age INT,
&gt;     deleted INT DEFAULT 0
&gt; );
&gt; ```
&gt;
&gt; - `deleted = 0` 表示未删除
&gt; - `deleted = 1` 表示已删除

2. **自动填充**

```java
@TableField(fill = FieldFill.INSERT)
private LocalDateTime createTime;

@TableField(fill = FieldFill.INSERT_UPDATE)
private LocalDateTime updateTime;
```

- 插入或更新时自动填充时间

3. **乐观锁**

```java
@Version
private Integer version;
```

- 更新时自动检查版本字段

再来看一下 mapper 接口

```java
@Mapper
public interface UserMapper extends BaseMapper<User> {
}
```

mapper 接口实现了一个`BaseMapper&lt;T&gt;`类，但是却没有实现一些基本的 CRUD 方法。查看这个类可以发现，这里面已经帮我们实现了很多基本的 CRUD 的操作，无需我们自己去写。

`BaseMapper` 是 MyBatis-Plus 提供的一个基础 Mapper 接口，它简化了数据访问层（Data Access Layer）的开发。`BaseMapper` 提供了一系列通用的数据库操作方法，这样就不必手动编写常见的 SQL 语句，从而提升了开发效率。

然后再看一下 service 层

```java
package com.jh.service;

public interface UserService extends IService<User> {
}

```

```java
package com.jh.service.impl;

@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements UserService {
}
```

我们在 service 层下面实现了一个 Service 接口，又在 service.impl 下面继承了该接口，实现了一个 UserServiceImpl 类。

UserService 是实现了 `Iservice&lt;T&gt;`接口

UserService  的实现类 UserServiceImpl 实现了 `ServiceImpl` 类。

`ServiceImpl` 和 `IService` 是 MyBatis-Plus 中用于服务层（Service Layer）的两个重要接口和类，它们帮助简化和规范了与数据库交互的业务逻辑。下面是它们的详细介绍：

**IService 接口**

`IService` 是 MyBatis-Plus 提供的一个通用服务接口。它定义了一些常见的 CRUD（Create, Read, Update, Delete）操作，并将这些操作抽象成方法。这意味着，当你使用 `IService` 接口时，你无需自己手动编写这些常见的数据库操作方法。

IService 中的一些常用方法：

- `boolean save(T entity)`: 保存一个实体类对象到数据库。
- `boolean removeById(Serializable id)`: 根据 ID 删除数据。
- `boolean updateById(T entity)`: 根据 ID 更新数据。
- `T getById(Serializable id)`: 根据 ID 查询数据。
- `List&lt;T&gt; list()`: 查询所有数据。
- `Page&lt;T&gt; page(Page&lt;T&gt; page)`: 分页查询数据。

**ServiceImpl 类**

`ServiceImpl` 是 MyBatis-Plus 提供的一个基础实现类，它实现了 `IService` 接口中的方法。`ServiceImpl` 通常是被继承的，它提供了具体的数据库操作方法的实现。开发者只需在自己定义的服务实现类中继承 `ServiceImpl` 类，就可以获得默认的 CRUD 功能。

最后看一下效果

```java
@SpringBootApplication
public class App {
    public static void main(String[] args) {
        ConfigurableApplicationContext context = SpringApplication.run(App.class, args);
        UserService service = context.getBean(UserServiceImpl.class);
        List<User> users = service.list();
        for (User user : users) {
            System.out.println(user);
        }
    }
}
```

mybatis-plus 还提供了 **QueryWrapper** 条件构造器，用来提供条件查询

看一个例子

```java
public class UserService {
    private UserMapper userMapper; // 注入的 MyBatis-Plus Mapper

    public void example() {
        QueryWrapper<User> query = new QueryWrapper<>();
        query.eq("age", 20)          // age = 20
             .like("name", "张")     // name LIKE '%张%'
             .orderByDesc("id");    // 按 id 降序排序

        List<User> userList = userMapper.selectList(query);
        userList.forEach(System.out::println);
    }
}
```

可以看到 `QueryWrapper` 可以当作条件传入给 mapper 方法当参数

**mybatis 和 mybatis-plus 的分页插件**

**MyBatis 原生分页**

使用方式

MyBatis 本身并没有内置分页功能，需要手动写 SQL。典型做法是使用 **`LIMIT` + `OFFSET`（MySQL）** 或者数据库特有的分页语法：

```sql
<!-- Mapper XML -->
<select id="selectUserPage" resultType="User">
  SELECT id, name, age, email
  FROM user
  WHERE age &gt; #{minAge}
  ORDER BY id DESC
  LIMIT #{offset}, #{pageSize}
</select>
```

对应的 Java 调用：

```java
int page = 1;
int pageSize = 10;
int offset = (page - 1) * pageSize;

List<User> users = userMapper.selectUserPage(offset, pageSize, 20);
```

原理

- 分页逻辑 **完全靠 SQL** 来实现。
- 开发者必须手动计算 `offset` 和 `limit`。
- 如果想获取总条数，还需要额外写一个 `SELECT COUNT(*)` 的 SQL。
- 优点：灵活，任何数据库都可用。
- 缺点：重复工作多，SQL 可维护性差。

**MyBatis-Plus 分页**

MyBatis-Plus 内置了分页插件（`PaginationInterceptor` 或 `MybatisPlusInterceptor` + `PaginationInnerInterceptor`），分页更加自动化。

使用方式

Mapper 接口

```java
public void getUserPage() {
    // 创建分页对象：第1页，每页10条
    IPage<User> page = new Page<>(1, 10);

    // 执行分页查询
    IPage<User> userPage = userMapper.selectPage(page, null); // 第二个参数需要传 Wrapper 条件，这里为 null 表示不加条件

    // 获取当前页数据
    List<User> users = userPage.getRecords();
    System.out.println("当前页数据：" + users);

    // 获取总条数
    long total = userPage.getTotal();
    System.out.println("总条数：" + total);

    // 获取总页数
    long pages = userPage.getPages();
    System.out.println("总页数：" + pages);
}
```

原理

1. **分页插件拦截 SQL**：
   - MyBatis-Plus 的分页插件会在 SQL 执行前拦截查询。
   - 自动改写 SQL，加上数据库对应的分页语法（`LIMIT`/`OFFSET`、`ROWNUM` 等）。
2. **自动计算总条数**：
   - 插件会自动生成一个 `COUNT(*)` SQL 查询总条数。
3. **返回 IPage 对象**：
   - 包含分页信息：总条数、当前页数据、总页数、每页大小等。
4. **无需手动拼接 SQL**：
   - SQL 可以和普通查询一样写，插件负责分页。

优点

- 自动化，减少重复分页 SQL。
- 与数据库无关（插件内部支持多种数据库）。
- 支持动态条件（Wrapper）分页。
- 提供丰富的分页信息（总页数、总条数等）。

虽然 MyBatis 本身不自带分页功能，但可以通过**分页插件**（最常用的是 **PageHelper**）来实现分页。下面展示一下**配置和使用方式**。

**引入依赖**

以 Maven 为例，引入 PageHelper 插件：

```xml
<dependency>
    <groupId>com.github.pagehelper</groupId>
    <artifactId>pagehelper</artifactId>
    <version>5.4.2</version> <!-- 最新稳定版本 -->
</dependency>
```

**配置 MyBatis 插件**

Spring Boot 项目

在 Spring Boot 中，可以直接在 `application.properties` 或 `application.yml` 配置：

```properties
# PageHelper 配置
pagehelper.helperDialect=mysql
pagehelper.reasonable=true
pagehelper.supportMethodsArguments=true
pagehelper.params=count=countSql
```

或者在配置类中注册插件：

```java
@Configuration
public class MyBatisConfig {

    @Bean
    public PageInterceptor pageInterceptor() {
        PageInterceptor pageInterceptor = new PageInterceptor();
        Properties properties = new Properties();
        properties.setProperty("helperDialect", "mysql"); // 数据库方言
        properties.setProperty("reasonable", "true");      // 页码合理化
        properties.setProperty("supportMethodsArguments", "true"); // 支持方法参数
        pageInterceptor.setProperties(properties);
        return pageInterceptor;
    }

    @Bean
    public SqlSessionFactory sqlSessionFactory(DataSource dataSource, PageInterceptor pageInterceptor) throws Exception {
        SqlSessionFactoryBean sessionFactory = new SqlSessionFactoryBean();
        sessionFactory.setDataSource(dataSource);
        sessionFactory.setPlugins(pageInterceptor); // 注册分页插件
        return sessionFactory.getObject();
    }
}
```

原理

- PageHelper 是一个 **MyBatis 拦截器插件（Interceptor）**。
- 在执行 SQL 前，它会拦截查询，并修改 SQL，加上 `LIMIT` 或数据库对应的分页语法。
- 同时，它会自动执行 `SELECT COUNT(*)` 查询总条数。
- 拦截器通过 `Properties` 配置不同数据库方言、合理化页码等功能。

**使用方式**

```java
public List<User> getUserPage(int pageNum, int pageSize) {
    // 开始分页
    PageHelper.startPage(pageNum, pageSize);

    // 执行查询
    List<User> users = userMapper.selectAll();

    // 包装分页结果
    PageInfo<User> pageInfo = new PageInfo<>(users);
    System.out.println("总条数：" + pageInfo.getTotal());
    System.out.println("总页数：" + pageInfo.getPages());
    System.out.println("当前页数据：" + pageInfo.getList());
    
    return pageInfo.getList();
}
```

注意：`PageHelper.startPage()` 必须紧跟查询语句，否则分页无效。

mybatis-plus 还提供像代码生成器这样的功能，等用到再说
