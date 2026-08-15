+++
date = '2026-01-30T19:18:59+08:00'
draft = false
title = 'MyBatis-Plus'
+++

在实习过程中，使用 MyBatis-Plus 遇到很多小问题，在这里记录一下。

我们在处理 SQL 时可能会需要使用一些标签，通过 `<if></if>` 等的一些标签来实现动态的逻辑，其实 MyBatis-Plus 提供了一种更加优雅的方式。使用 Wrappers

## 动态 SQL

好，这一段**正是 MyBatis-Plus 里“Wrapper 动态 SQL”的精髓**，但如果没人把**每一层发生了什么**拆开讲，其实非常容易“会用但不懂”。

我按 **4 个层次**来讲清楚：

1. 这行 `@Select` 到底在干嘛
2. `Wrapper` / `ew` 是什么机制
3. `LambdaQueryWrapper` 是如何“动态拼 SQL”的
4. 为什么它 **比注解里的 `<if>` 更推荐**

------

## 一、先看这行核心 SQL（非常关键）

```
@Select("select * from user ${ew.customSqlSegment}")
List<User> selectByWrapper(@Param(Constants.WRAPPER) Wrapper<User> wrapper);
```

### 你必须先明确一件事：

> **这条 SQL 本身是“静态注册”的，但 SQL 的 WHERE 部分是“运行时生成”的**

------

### 1. `${ew.customSqlSegment}` 是什么？

这是 **MyBatis-Plus 约定的占位符**：

- `ew`：`Wrapper` 的别名（**固定名字**）
- `customSqlSegment`：MP 在 Wrapper 里**动态生成的 SQL 片段**

 本质是：

```
-- 运行前
select * from user ${ew.customSqlSegment}

-- 运行时（举例）
select * from user WHERE name = ? AND age >= ?
```

注意： 注意：

- 这是 **SQL 片段拼接**
- 不是 MyBatis 的 `<if>` 动态标签
- 是 **MP 自己拼好的结果**

------

### 2. 为什么是 `${}` 而不是 `#{}`？

这是很多人第一次看到会疑惑的点。

- `#{}` -> 预编译参数，占位符 `?`
- `${}` -> **直接 SQL 片段拼接**

而 `customSqlSegment`：

- 已经是 **完整 SQL 结构**
- 包含 `WHERE / AND / ORDER BY`
- 里面的值 **已经被参数化处理过**

 **MP 内部保证安全性**
 你不用自己拼字符串（这是关键优势）

------

## 二、`@Param(Constants.WRAPPER)` 到底在干嘛？

```
@Param(Constants.WRAPPER)
Wrapper<User> wrapper
```

### `Constants.WRAPPER` 是什么？

```
public static final String WRAPPER = "ew";
```

也就是说：

```
@Param("ew")
Wrapper<User> wrapper
```

这一步的意义只有一个：

> **把 Wrapper 参数，绑定成 SQL 里能识别的 `ew`**

否则 `${ew.customSqlSegment}` 根本找不到对象。

------

## 三、`LambdaQueryWrapper` 是如何“动态生成 SQL”的？

现在来看你调用的这段代码：

```
LambdaQueryWrapper<User> qw = new LambdaQueryWrapper<>();

qw.eq(name != null, User::getName, name)
  .ge(age != null, User::getAge, age);

mapper.selectByWrapper(qw);
```

### 1. 每一行 `eq / ge` 实际在干什么？

以这一行为例：

```
qw.eq(name != null, User::getName, name);
```

MP 内部做的是：

```
if (condition) {
    conditions.add("name = ?");
    params.add(name);
}
```

如果 `name == null`：

- **这一行什么都不会发生**
- SQL 里根本不会出现 `name = ?`

注意： **这就是 MP Wrapper 动态性的核心：**

> 条件在 Java 层判断，而不是 SQL 层判断

------

### 2. SQL 是什么时候真正生成的？

不是在你 `eq()` 的时候
 而是在 **Mapper 方法被调用时**：

```
mapper.selectByWrapper(qw);
```

执行流程是：

1. MyBatis 拿到 `MappedStatement`
2. MP 读取 `Wrapper`
3. 调用 `wrapper.getCustomSqlSegment()`
4. 拼出最终 SQL
5. 绑定参数
6. 执行

 **SQL 的最终形态，是在“执行时”才确定的**

------

## 四、为什么 MP 明确“更推荐 Wrapper，而不是 `<if>`”？

这是你这个问题真正的重点。

------

### 1. 对比一眼就懂

####  注解 + `<if>`（不推荐）

```
@Select({
  "<script>",
  "select * from user",
  "<where>",
    "<if test='name != null'>",
      "and name = #{name}",
    "</if>",
    "<if test='age != null'>",
      "and age &gt;= #{age}",
    "</if>",
  "</where>",
  "</script>"
})
```

问题：

- SQL 和业务条件 **强耦合**
- XML/注解可读性极差
- 条件多了以后像“屎山”

------

####  Wrapper（MP 推荐）

```
qw.eq(name != null, User::getName, name)
  .ge(age != null, User::getAge, age);
```

优点非常明显：

| 维度          | Wrapper     |
| ------------- | ----------- |
| 可读性        |        |
| 动态性        |        |
| Java IDE 支持 |            |
| 重构安全      | （Lambda） |
| SQL 可控性    |            |
| 维护成本      | 极低        |

------

### 2. Wrapper 把“动态逻辑”放在了**正确的层**

这是设计上的关键点：

| 逻辑类型   | 应该在哪 |
| ---------- | -------- |
| 是否拼条件 | Java     |
| SQL 结构   | Mapper   |
| 参数安全   | MP 内部  |

 `<if>` 把 **业务判断写进 SQL**
  Wrapper 把 **业务判断留在 Java**

**这是分层设计的正确姿势**

------

## 五、一个你一定要记住的工程级结论

> **`${ew.customSqlSegment}` 不是“黑魔法”**
>  它只是：
>
> - Mapper 保持 SQL 骨架
> - Wrapper 负责动态条件
> - MyBatis-Plus 做中间人

------

## 六、什么时候用这种写法？什么时候不用？

###  非常适合：

- 条件可选
- 查询组合多
- CRUD / 列表 / 统计
- 后期需求一定会变的接口

###  不适合：

- SQL 结构本身就非常复杂
- 多表 JOIN + 子查询 + 窗口函数
- 强数据库特性（Oracle / MySQL 差异）

这种情况：
  XML / 注解 + 明确 SQL 反而更好

## 逻辑删除

使用 MyBatis-Plus 的逻辑删除功能需要注意。

它会在你使用 Wrapper 条件构造器的时候自动为你拼接 `deleted = 0`。虽然很方便，但有些地方也不方便。比如恢复原来已经被逻辑删除的数据的时候，直接执行 `INSERT` 又可能会直接抛异常。因此我们需要做额外的判断，这个判断是不能用 Wrapper 构造器判断的。因为它构造的每一条 SQL 都会有 `deleted = 0` 这个条件。因此需要手写 SQL，在 XML 文件，或者 `@Select` 注解中的 SQL 在执行时是不会被自动加上 `deleted = 0` 这种的条件判断的。

这个问题已解决，那就是使用非业务主键，我们可以给每一调数据设置一个无意义的主键，这样在插入数据的时候就不会造成主键冲突，但是唯一索引还是会冲突。

### 条件构造器

使用 MP 的条件构造器时，一定要加 condition 条件。因为在拼接 sql 时，条件过滤器是根据 condition 的真值判断是否拼接的，如果不加条件，WHERE 中出现 WHERE id=null 这种场景的话，会导致什么数据都查不出来
