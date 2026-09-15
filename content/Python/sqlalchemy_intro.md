+++
date = '2026-09-13T2:00:00+08:00'
draft = false
title = 'SQLAlchemy 是什么：从零理解 Python ORM 与 SQLAlchemy 2.x 入门'
+++

Python 程序需要访问关系型数据库时，你当然可以直接调用数据库驱动、手写每一条 SQL。这样做并不错误；错误的是以为“手写 SQL”和“使用 ORM”之间只能二选一。现实没有这么戏剧化，工具也不该逼迫人站队。

**SQLAlchemy 是 Python 生态中成熟的 SQL 工具包与 ORM（对象关系映射）框架。**它一方面提供接近 SQL 的表达式构造、连接管理和事务能力，另一方面提供把 Python 类映射到数据表的 ORM。你可以只使用前者，也可以两者组合使用。

## 先给结论

如果只想先记住最重要的内容，可以记下面几条：

- SQLAlchemy **不是数据库**，它不会替你存数据；SQLite、MySQL、PostgreSQL 才是数据库。
- SQLAlchemy **也不是数据库驱动**。连接 PostgreSQL、MySQL 等数据库时，仍需安装相应的 DBAPI 驱动，例如 `psycopg`、`PyMySQL`。
- 它分为两层：**Core** 负责 SQL、连接、事务和表结构；**ORM** 在 Core 之上，把表记录映射为 Python 对象。
- 现代 SQLAlchemy 2.x 的 ORM 查询以 `select()` 为中心，通过 `Session` 执行；不要把旧教程中的 `session.query(...)` 当作首选写法。
- `Engine` 负责“如何连接数据库”，`Session` 负责“一次业务工作中的对象状态与事务”。二者职责不同，混为一谈只会制造额外困惑。
- `Base.metadata.create_all()` 适合演示或原型；生产项目中的表结构演进通常应使用 **Alembic** 管理迁移。

## 一、SQLAlchemy 到底解决了什么问题

假设有一张用户表：

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    is_active BOOLEAN NOT NULL
);
```

如果使用数据库驱动直接操作，你通常需要自己维护连接、拼接或绑定 SQL 参数、执行语句、处理事务，并把查询结果转换成应用需要的数据结构。对于小脚本，这很直接；对于持续演进的项目，重复劳动会迅速变多。

SQLAlchemy 给出的抽象层大致如下：

```text
Python 业务代码
       │
       ├── SQLAlchemy ORM：Python 类 / 对象 / 关系
       │        │
       └── SQLAlchemy Core：SQL 表达式 / 事务 / 连接池
                │
             DBAPI 驱动（pysqlite、psycopg、PyMySQL……）
                │
       SQLite / PostgreSQL / MySQL / 其他关系型数据库
```

这里最值得建立的认识是：**ORM 并没有消灭 SQL。**它只是把常见的数据读写和对象关系管理抽象起来；最终仍会生成并执行 SQL。理解表、索引、事务、隔离级别和查询计划，依然是必要的。只不过你不必为每一次简单的增删改查都从零处理那些细枝末节。

### Core：更接近 SQL 的工具层

SQLAlchemy Core 提供：

- `Engine`：数据库方言、连接池和连接配置的入口。
- `Connection`：一次底层连接的使用接口。
- `Table`、`Column`、`MetaData`：用 Python 描述表结构。
- `select()`、`insert()`、`update()`、`delete()`：以 Python 对象构造 SQL。
- 参数绑定、事务控制和执行结果处理。

Core 很适合下面的场景：复杂报表、批量更新、需要精确控制 SQL 结构的代码，或你本来就偏好 SQL，只是不想手写字符串拼接。

### ORM：把“表”映射成“类”

ORM（Object Relational Mapping，对象关系映射）会建立这样的对应关系：

| 关系型数据库概念 | ORM 中的概念 |
| --- | --- |
| 表 `users` | 类 `User` |
| 一行记录 | 一个 `User` 实例 |
| 列 `name` | 属性 `User.name` |
| 主键 | 对象身份 |
| 外键 | 类之间的关联 |
| 事务 | `Session` 的工作单元 |

这让业务代码能以对象形式表达常见操作，例如“创建一个用户”“修改用户邮箱”“获取某个用户的文章”。但请保持一点冷静：对象模型和关系模型并不完全相同。多表关联、聚合、窗口函数和大批量操作有时用 SQL/Core 表达反而更清楚。ORM 是工具，不是信仰。

## 二、安装：SQLAlchemy 与数据库驱动

先创建并激活虚拟环境，然后安装 SQLAlchemy：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install SQLAlchemy
```

SQLite 是 Python 标准库自带的数据库，通常不需要额外安装驱动。其他数据库则需要对应驱动：

| 数据库 | 同步连接 URL 示例 | 常用驱动安装命令 |
| --- | --- | --- |
| SQLite | `sqlite+pysqlite:///app.db` | 通常无需额外安装 |
| PostgreSQL | `postgresql+psycopg://user:password@localhost/app` | `py -m pip install "psycopg[binary]"` |
| MySQL / MariaDB | `mysql+pymysql://user:password@localhost/app` | `py -m pip install PyMySQL` |

URL 中的 `方言+驱动` 并不是装饰。例如 `postgresql+psycopg` 明确表示“使用 PostgreSQL 方言和 psycopg 驱动”。实际密码中若含有 `@`、`:`、`/` 等 URL 保留字符，应进行 URL 编码；更稳妥的是通过配置读取后用 `URL.create()` 构造连接 URL，别把密码直接写进源码和 Git 历史里。

## 三、第一个完整 ORM 示例

下面的程序使用 SQLite，在当前目录创建 `sqlalchemy_intro.db`，定义 `users` 表、插入两条数据并查询它们。

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r})"


# echo=True 会把执行的 SQL 输出到控制台；学习时有用，生产环境通常关闭。
engine = create_engine("sqlite+pysqlite:///sqlalchemy_intro.db", echo=True)

# 根据已声明的模型创建尚不存在的表。它不会处理复杂的表结构升级。
Base.metadata.create_all(engine)

# 插入数据。with session.begin() 成功时提交，抛出异常时回滚。
with Session(engine) as session:
    with session.begin():
        session.add_all(
            [
                User(name="Yukino", email="yukino@example.com"),
                User(name="Hachiman", email=None),
            ]
        )

# 查询数据。
with Session(engine) as session:
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.id)
    users = session.scalars(stmt).all()

    for user in users:
        print(user, user.email)
```

运行：

```powershell
py app.py
```

输出 SQL 时，你会看到 `CREATE TABLE`、`INSERT INTO`、`SELECT` 等语句。请偶尔看一眼这些日志。ORM 写起来很优雅是一回事，实际发出了多少 SQL、是否命中索引，则是另一回事。前者不能替后者免责。

### 模型声明逐行理解

`class Base(DeclarativeBase)` 创建声明式模型的基类。继承它的 `User` 同时携带两类信息：它是一个普通 Python 类，也是 `users` 表的映射描述。

```python
id: Mapped[int] = mapped_column(primary_key=True)
```

这一行说明：

- `id` 是 Python 属性。
- `Mapped[int]` 告诉类型检查器和 SQLAlchemy：这个属性映射到一列整数数据。
- `mapped_column(primary_key=True)` 进一步说明它是主键。

在 SQLAlchemy 2.x 中，`Mapped[...]` 加 `mapped_column()` 是带类型标注的声明式写法。`str | None` 或 `Optional[str]` 表明字段可以为空；即使 SQLAlchemy 能从类型标注推断许多默认配置，重要约束仍建议显式写出，尤其是长度、索引、唯一性和外键。

## 四、四个必须分清的对象

SQLAlchemy 初学者最容易被名词绊倒。把下面四个角色理清，许多问题就不再显得神秘。

| 对象 | 职责 | 常见生命周期 |
| --- | --- | --- |
| `Engine` | 保存数据库 URL、方言和连接池配置；按需提供连接 | 应用启动时创建，通常全局复用一个 |
| `Connection` | Core 模式下执行 SQL 的底层连接接口 | 一小段数据库操作期间 |
| `Session` | ORM 的工作单元：追踪对象、执行 ORM 查询、管理事务 | 一次 Web 请求、命令任务或业务单元 |
| `Base.metadata` | 收集模型对应的表结构元数据 | 随模型定义长期存在 |

### `Engine` 不是一条已经打开的连接

`create_engine()` 返回的是 `Engine`。它通常管理连接池，并在真正需要数据库操作时才取得连接。Web 服务中，`Engine` 常在应用初始化时创建一次并复用；不要每个请求都新建一个 `Engine`，那是在主动放弃连接池的意义。

### `Session` 也不是“全局数据库对象”

`Session` 是 ORM 的工作单元（unit of work）。它维护对象身份映射、记录变更，并在适当的时候发出 `INSERT`、`UPDATE`、`DELETE`。它可以在内部使用数据库连接，但它本身不是连接池。

更重要的是：**同一个 `Session` 不应被多个线程或并发任务共享。**常见实践是“一次 Web 请求一个 Session”“一次后台任务一个 Session”，在任务结束后关闭它。把它做成永不关闭的全局变量，迟早会得到难以复现的事务与并发问题；这并不神秘，只是资源生命周期被忽略了。

## 五、CRUD：增、查、改、删的现代写法

以下代码延续前面的 `User` 模型和 `engine`。

### 新增：`add()` 与 `add_all()`

```python
with Session(engine) as session:
    with session.begin():
        user = User(name="Yui", email="yui@example.com")
        session.add(user)

    # 离开事务块后已提交；Session 仍在当前 with 块内，主键可安全读取。
    print(user.id)
```

`session.add()` 的含义不是“此刻立刻执行 INSERT”，而是把对象纳入 Session 管理。SQLAlchemy 会在需要时执行 **flush**，把内存中的变更同步为 SQL。提交事务前一定会发生必要的 flush。

### 查询：从 `select()` 开始

查询一个 ORM 实体时，推荐组合 `select()` 与 `Session.scalars()`：

```python
with Session(engine) as session:
    # 查询多个对象
    stmt = (
        select(User)
        .where(User.name.like("Y%"), User.is_active.is_(True))
        .order_by(User.created_at.desc())
    )
    users = session.scalars(stmt).all()

    # 按主键查询一个对象；找不到时返回 None。
    user = session.get(User, 1)

    # 确认恰好有一条；没有或多于一条都会抛异常。
    yukino = session.scalars(
        select(User).where(User.name == "Yukino")
    ).one()
```

常用的结果方法如下：

| 方法 | 适用情况 | 结果 |
| --- | --- | --- |
| `session.get(User, 1)` | 按主键获取 | 对象或 `None` |
| `session.scalars(stmt).all()` | 获取多个实体或单列值 | `list` |
| `session.scalars(stmt).first()` | 最多取第一个 | 对象或 `None` |
| `session.scalars(stmt).one()` | 业务上必须恰好一条 | 对象；数量不对会抛异常 |
| `session.scalar(stmt)` | 只要第一行第一列 | 标量或 `None` |

如果选择的是多个字段而不是完整实体，应使用 `execute()`，它返回行对象：

```python
with Session(engine) as session:
    stmt = select(User.id, User.name).where(User.is_active.is_(True))
    for user_id, name in session.execute(stmt):
        print(user_id, name)
```

### 修改：加载对象，修改属性，提交事务

```python
with Session(engine) as session:
    with session.begin():
        user = session.get(User, 1)
        if user is None:
            raise LookupError("用户不存在")

        user.email = "new-address@example.com"
        user.is_active = False
```

这里没有显式调用 `session.update(user)`。被当前 Session 加载的对象会被追踪；属性改变后，SQLAlchemy 会在 flush 时生成相应的 `UPDATE`。这称为 **Unit of Work** 模式。

### 删除：`delete()` 后仍要提交

```python
with Session(engine) as session:
    with session.begin():
        user = session.get(User, 2)
        if user is not None:
            session.delete(user)
```

`delete()` 同样只是登记删除意图。只有事务成功提交，数据库中的记录才真正被删除。

## 六、事务：`flush`、`commit` 与 `rollback` 的区别

这三个词经常被混用，然而它们做的事并不一样。

| 操作 | 做什么 | 数据是否永久写入 |
| --- | --- | --- |
| `flush()` | 把 Session 中待处理的变更发送为 SQL | 否，仍在当前事务中 |
| `commit()` | 提交当前事务 | 是，正常情况下其他事务可见 |
| `rollback()` | 撤销当前事务中尚未提交的变更 | 否 |

例如数据库生成主键后，你可能希望在提交前就拿到 `user.id`：

```python
with Session(engine) as session:
    with session.begin():
        user = User(name="Komachi")
        session.add(user)
        session.flush()

        # INSERT 已发出，主键已经可用；但事务尚未提交。
        print(user.id)

        # 可以继续用这个 id 创建依赖它的其他记录。
```

对大多数业务代码，推荐把事务边界写得清楚：

```python
try:
    with Session(engine) as session:
        with session.begin():
            # 多个读写操作组成一个原子业务动作
            ...
except Exception:
    # session.begin() 已经在异常时回滚；这里记录日志或转换业务异常。
    raise
```

不要在深层工具函数中随意 `commit()`。更好的边界通常在服务层、请求处理层或任务入口：由调用方决定“一组操作是否必须同时成功”。否则一次下单、扣库存、写流水这种本应原子的动作，可能被中途提交切成无法补救的碎片。

## 七、表关系：外键和 `relationship()`

数据库用外键连接表，ORM 用 `relationship()` 提供对象导航。下面定义“一个用户拥有多篇文章”的一对多关系：

```python
from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    articles: Mapped[list[Article]] = relationship(back_populates="author")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))

    author: Mapped[Author] = relationship(back_populates="articles")
```

这里有两个层面，缺一不可：

- `ForeignKey("authors.id")` 是**数据库约束与连接条件**的基础；它最终体现在表结构中。
- `relationship(...)` 是 ORM 层的对象关系；它让你可以访问 `article.author` 或 `author.articles`。

创建关联对象时可以直接操作对象属性：

```python
with Session(engine) as session:
    with session.begin():
        author = Author(name="Haruno")
        author.articles = [
            Article(title="SQL 并不会因为 ORM 而消失"),
            Article(title="事务边界比缩进更重要"),
        ]
        session.add(author)
```

### 警惕 N+1 查询

假如先查询 N 位作者，再在循环里访问每位作者的 `articles`，默认的延迟加载可能发出额外 N 条 SQL：

```python
with Session(engine) as session:
    authors = session.scalars(select(Author)).all()

    for author in authors:
        print(author.name, len(author.articles))
```

小数据量时它安静得像什么都没发生，所以尤其容易被忽略。需要列表展示关联数据时，可以显式使用 `selectinload()`：

```python
from sqlalchemy.orm import selectinload

with Session(engine) as session:
    stmt = select(Author).options(selectinload(Author.articles))
    authors = session.scalars(stmt).all()

    for author in authors:
        print(author.name, len(author.articles))
```

`selectinload()` 通常会用一条额外的 `IN (...)` 查询批量加载关联集合，从而避免逐个查询。对于不同基数和访问模式，`joinedload()`、`selectinload()`、显式 `join()` 的选择不同；先观察生成的 SQL 和数据规模，再做决定。性能优化不能靠咒语。

## 八、何时使用 Core，何时使用 ORM

它们不是互斥关系。一个项目可以对业务实体使用 ORM，对报表、聚合或批量更新使用 Core。

### 用 Core 执行参数化 SQL

以下示例使用 `text()` 执行文本 SQL。` :name` 是绑定参数，不是字符串拼接：

```python
from sqlalchemy import text

with engine.begin() as connection:
    result = connection.execute(
        text(
            """
            SELECT id, name
            FROM users
            WHERE name = :name
            """
        ),
        {"name": "Yukino"},
    )
    row = result.mappings().first()
    print(row)
```

永远不要这样拼接用户输入：

```python
# 错误示例：存在 SQL 注入风险。
sql = f"SELECT * FROM users WHERE name = '{user_input}'"
```

参数绑定既能避免把值误当成 SQL 语法，也能让数据库正确处理数据类型。它不是可有可无的编码洁癖，而是数据库访问的基本安全要求。

### 一个实用判断表

| 需求 | 更自然的选择 |
| --- | --- |
| 常规业务实体的创建、读取、关联维护 | ORM |
| 复杂统计、窗口函数、数据库特定语法 | Core 或参数化文本 SQL |
| 批量导入、批量更新、批量删除 | Core 或 ORM 的批量 DML，注意同步策略 |
| 只按主键取一个对象并修改 | ORM 的 `Session.get()` |
| 需要精确审查最终 SQL | Core，或开启 ORM 的 SQL 日志 |

## 九、`create_all()` 不是迁移系统

下面这行只会根据当前模型创建不存在的表：

```python
Base.metadata.create_all(engine)
```

它**不会**可靠地把已存在的表从旧结构升级到新结构。例如你为 `users` 新增一列、修改列类型、建立索引或重命名字段，`create_all()` 不是用来处理这些变化的。

实际项目通常使用 Alembic：

```powershell
py -m pip install alembic
alembic init migrations
```

之后通过迁移脚本将“模型和数据库结构的变化”作为可审查、可回放的版本历史管理。即使是单人项目也很值得做；毕竟数据库并不会因为你说“只是改了一列”就自动理解你的意图。

## 十、异步 ORM：只有确实需要时再使用

SQLAlchemy 同时支持同步和异步 API。异步常见于 ASGI Web 服务等本身采用 `asyncio` 的应用；它有助于在等待 I/O 时让出事件循环，但**不会让一条慢 SQL 神奇地变快**。数据库索引和查询设计仍然要自己负责。

以 SQLite 的异步驱动为例：

```powershell
py -m pip install "SQLAlchemy" aiosqlite
```

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

engine = create_async_engine("sqlite+aiosqlite:///async_demo.db")
SessionLocal = async_sessionmaker(engine, class_=AsyncSession)

async def find_active_users() -> list[User]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(User).where(User.is_active.is_(True))
        )
        return result.all()
```

异步模式需要从 URL、驱动到 `await` 都保持一致。不要把同步 `Session` 和 `AsyncSession` 随意混在同一条调用链中；它们看起来相似，资源模型却不同。

## 十一、初学者常见误区

### 1. 以为 ORM 不需要懂 SQL

ORM 的查询、加载策略和关联最终都会生成 SQL。不会看 SQL 时，你很难排查慢查询、重复查询、锁等待和索引失效。建议在学习阶段打开 `echo=True`，并用数据库的查询分析工具检查关键路径。

### 2. 每个函数都自己提交事务

业务操作被拆到多个函数后，随意提交会破坏原子性。让更高一层定义事务边界，底层函数只完成本职读写，代码会更可预测。

### 3. 关闭 Session 后再访问未加载的关系

下列写法可能失败，因为 `author.articles` 需要延迟加载，而 Session 已关闭：

```python
with Session(engine) as session:
    author = session.get(Author, 1)

print(author.articles)  # 可能抛出 DetachedInstanceError
```

在 Session 仍有效时访问需要的数据，或提前使用 `selectinload()` 预加载。不要把数据库访问悄悄留到资源已关闭之后。

### 4. 把所有数据一次性 `.all()` 到内存

`all()` 适合有限结果集。导出大量记录时，应分页、分批处理，或使用流式结果；否则内存会先替你表达反对意见。

### 5. 把 `echo=True` 长期开在生产环境

SQL 日志可能包含表结构、参数甚至敏感业务信息，并带来额外噪声。开发环境可开，生产环境应使用经过脱敏和分级的日志配置。

## 十二、建议的学习顺序

不要急着把所有概念一次学完。按这个顺序会更稳妥：

1. 用 SQLite 完成本文的建表、增删改查。
2. 理解 `Engine`、`Session`、事务与 `select()` 的职责。
3. 学习一对多关系和 `selectinload()`，观察生成的 SQL。
4. 换成 PostgreSQL 或 MySQL，正确配置驱动与连接 URL。
5. 用 Alembic 管理迁移。
6. 再根据项目架构学习 FastAPI、Flask、Django 等框架如何管理 Session。
7. 只有项目已经采用异步调用链且确有并发 I/O 需求时，再学习 `AsyncSession`。

## 总结

SQLAlchemy 的价值不在于“让你再也看不见 SQL”，而在于为 Python 提供一套可组合的数据库抽象：需要对象模型时使用 ORM，需要贴近 SQL 时使用 Core，二者共享同一套连接、事务和方言能力。

入门阶段请先掌握这条主线：

```text
定义模型 → 创建 Engine → 创建/迁移表结构 → 创建 Session
     → 在明确事务中读写 → 用 select() 查询 → 关闭 Session
```

当你能解释 `Engine` 与 `Session` 的区别，知道为什么事务不该散落在每个函数里，并会检查 ORM 实际生成的 SQL 时，SQLAlchemy 就不再只是几段“看起来能运行”的模板了。

## 参考资料

- [SQLAlchemy Unified Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)
- [SQLAlchemy ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
