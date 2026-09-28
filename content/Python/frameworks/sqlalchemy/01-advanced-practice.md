+++
date = '2026-09-26T20:05:00+08:00'
draft = false
title = 'SQLAlchemy ORM 进阶实践：查询、事务、并发与迁移'
aliases = [
  '/python/sqlalchemy_orm_advanced_practice/',
]
+++
ORM 的作用不是让 SQL 消失，而是把实体映射、连接管理、事务和查询组合成更安全的 Python 抽象。真正的难点也不在“会不会 `session.add()`”，而在于：会话应活多久？事务边界由谁决定？怎样防止列表页 N+1 查询？并发请求如何保证唯一性？模型声明改变后怎样安全升级线上表？

本文以 SQLAlchemy 2.x 的类型化同步 ORM 为主线，适用于 FastAPI、命令行任务和普通 Python 服务。基础建模与 CRUD 可先阅读 [SQLAlchemy 2.0 ORM 入门](00-introduction.md)；本文会在此基础上讨论更接近实际项目的查询、事务、并发与迁移问题。

## 一、建立正确的心智模型：Engine、Connection、Session

先区分三个对象：

| 对象 | 职责 | 通常生命周期 |
| --- | --- | --- |
| `Engine` | 保存数据库 URL、方言和连接池，按需提供连接 | 应用进程级，通常一个 |
| `Connection` | 执行 Core SQL 的底层连接 | 一段数据库操作期间 |
| `Session` | ORM 工作单元，追踪对象、发出 SQL、管理事务 | 一次请求或一次后台任务 |

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine = create_engine(
    "postgresql+psycopg://app:password@localhost/app",
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
```

`Engine` 不是一条已经永久占用的数据库连接，而是连接池与方言配置中心。`pool_pre_ping=True` 会在借出连接时检测连接是否仍有效；`pool_recycle` 可避免某些数据库回收长期闲置连接后，业务请求才发现断开。具体值应结合数据库的超时配置决定。

`Session` 也不是全局数据库对象。它维护对象身份映射和变更追踪，并在需要时从 Engine 的池中借连接。一个 `Session` 不应跨线程或并发任务共享；一次 HTTP 请求、一次 worker 领任务或一次 CLI 命令，应各自创建和关闭会话。

```python
from collections.abc import Generator
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`close()` 归还资源，但不会替你提交事务。只有 `commit()` 才会让当前事务的变更永久生效；发生异常后若还要继续使用同一个会话，应先 `rollback()`。这两个动作看起来琐碎，却是大量线上数据问题的分界线。

## 二、类型化模型：把不变量写进数据库映射

SQLAlchemy 2.x 推荐用 `Mapped[...]` 与 `mapped_column()` 声明模型：

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(SqlEnum(OrderStatus),
                                                  default=OrderStatus.PENDING)
    payment_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
```

| 声明 | 作用 |
| --- | --- |
| `Mapped[str]` | 说明 Python 属性是 ORM 映射字段 |
| `String(255)` | 限制数据库列类型与长度 |
| `primary_key=True` | 定义行身份 |
| `ForeignKey(...)` | 维护表间引用完整性 |
| `index=True` | 为常用筛选/连接路径建立索引 |
| `unique=True` | 让数据库拒绝重复业务键 |
| `SqlEnum(...)` | 将有限状态限制为枚举集合 |

金额建议存为最小货币单位的整数，例如 `amount_cents`，而不是 `float`。时间建议统一存储带时区的 UTC 时间，在展示层转换时区。UUID 适合分布式生成 ID，但它不是自动的性能优化；索引类型、插入局部性和数据库方言仍需按实际负载评估。

### 外键与 `relationship()` 各做什么

`ForeignKey("users.id")` 是数据库层的引用约束；`relationship()` 则是在 ORM 层提供对象导航。两者不是互相替代。

```python
from sqlalchemy.orm import relationship


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    articles: Mapped[list[Article]] = relationship(back_populates="author")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), index=True)
    author: Mapped[Author] = relationship(back_populates="articles")
```

有些服务选择不定义大量 `relationship()`，而在读取接口中显式 `join()`；有些服务大量使用关系和预加载。两种风格都可以，但都必须理解最终 SQL、关联基数和加载策略。不能因为对象导航方便，就忘记它可能触发额外查询。

## 三、现代 CRUD：`select()`、对象状态与结果 API

SQLAlchemy 2.x 的查询以 `select()` 为中心：

```python
from sqlalchemy import select
from sqlalchemy.orm import Session


def find_order(db: Session, order_id: str) -> Order | None:
    return db.get(Order, order_id)


def find_pending_order(db: Session, payment_no: str) -> Order | None:
    return db.scalar(
        select(Order).where(
            Order.payment_no == payment_no,
            Order.status == OrderStatus.PENDING,
        )
    )


def list_orders(db: Session, buyer_id: str) -> list[Order]:
    stmt = select(Order).where(Order.buyer_id == buyer_id).order_by(Order.created_at.desc())
    return list(db.scalars(stmt))
```

| API | 合适场景 | 返回 |
| --- | --- | --- |
| `db.get(Model, pk)` | 已知主键 | 实体或 `None` |
| `db.scalar(stmt)` | 第一行第一列，常用于最多一条实体/聚合值 | 值或 `None` |
| `db.scalars(stmt)` | 多个实体或单列 | 标量结果序列 |
| `db.execute(stmt)` | 多列投影、多个实体、join 行 | `Row` 结果 |
| `.one()` | 业务上必须恰好一条 | 数量不对时抛异常 |

写入的核心链路如下：

```python
def create_order(db: Session, buyer_id: str, amount_cents: int) -> Order:
    order = Order(buyer_id=buyer_id, amount_cents=amount_cents,
                  payment_no=generate_payment_no())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
```

已经由当前会话加载的对象称为持久态对象。修改它的属性后无需调用不存在的 `db.update()`：Session 的 Unit of Work 会在 flush 时检测脏数据并生成 `UPDATE`。

```python
def cancel_order(db: Session, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise LookupError("订单不存在")
    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    return order
```

## 四、事务边界：`add`、`flush`、`commit` 与 `rollback`

这四个操作做的事不同：

| 操作 | 行为 | 是否永久写入 |
| --- | --- | --- |
| `add()` | 将新对象纳入会话追踪 | 否 |
| `flush()` | 发出待处理 SQL，仍属于当前事务 | 否 |
| `commit()` | 提交当前事务 | 是 |
| `rollback()` | 撤销未提交事务，恢复会话可用状态 | 否 |

在一个业务动作内需要多个对象的 ID 时，使用 `flush()` 而不是提前提交：

```python
def create_order_and_audit(db: Session, buyer_id: str, amount_cents: int) -> Order:
    try:
        order = Order(buyer_id=buyer_id, amount_cents=amount_cents,
                      payment_no=generate_payment_no())
        db.add(order)
        db.flush()

        audit = AuditLog(entity_type="order", entity_id=order.id, action="created")
        db.add(audit)
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise
```

`flush()` 使 INSERT 已发送，主键和数据库约束检查可以在提交前生效；但如果随后创建审计日志失败，`rollback()` 仍能让订单和审计日志一起不生效。若在深层帮助函数里过早 `commit()`，原本原子的业务动作就会被切成无法恢复的碎片。

也可以让服务层明确使用事务上下文：

```python
with SessionLocal() as db:
    with db.begin():
        # 成功时自动提交；异常时自动回滚。
        ...
```

选择哪种写法不是宗教问题，关键是让事务边界清楚且一致：由能看见完整业务不变量的调用层决定提交，而不是每个工具函数各自提交。

## 五、关联加载与 N+1 查询

下面的代码看起来很自然，却可能产生 N+1 查询：

```python
authors = db.scalars(select(Author)).all()
for author in authors:
    print(author.name, len(author.articles))
```

先查作者一次，然后每个作者第一次访问 `articles` 时各查一次。N 很小时问题不明显，到了列表页就会把数据库往返数放大。集合关系通常可使用 `selectinload()`：

```python
from sqlalchemy.orm import selectinload

stmt = select(Author).options(selectinload(Author.articles))
authors = db.scalars(stmt).all()
```

`selectinload()` 通常发出“作者一条查询 + 文章按作者 ID 的一条 IN 查询”。一对一或多对一关系有时适合 `joinedload()`，但 join 会扩张行数；列表卡片若只需要作者昵称、评论数等少量字段，显式投影和聚合往往更直观：

```python
from sqlalchemy import func, select

comment_count = (
    select(Comment.article_id, func.count().label("comment_count"))
    .group_by(Comment.article_id)
    .subquery()
)

stmt = (
    select(Article, Author.display_name, func.coalesce(comment_count.c.comment_count, 0))
    .join(Author, Author.id == Article.author_id)
    .outerjoin(comment_count, comment_count.c.article_id == Article.id)
)
rows = db.execute(stmt).all()
```

没有哪种加载策略永远最好。请先确认接口需要的字段、关联基数和数据量，再打开 SQL 日志或执行计划检查实际查询；优化不应靠背诵一个“永远用 joinedload”的口诀。

## 六、分页：从 offset 到 keyset cursor

小型后台列表可使用 offset：

```python
stmt = select(Order).order_by(Order.created_at.desc()).offset(40).limit(20)
```

它支持“第 N 页”，但深页需要数据库扫描并跳过大量行，且新记录插入时可能产生重复或漏项。无限滚动、活动流、下载记录等按时间读取的集合，更适合 keyset pagination：

```python
from sqlalchemy import and_, or_, select


def next_page(db: Session, cursor_time: datetime | None, cursor_id: str | None) -> list[Order]:
    stmt = select(Order)
    if cursor_time is not None and cursor_id is not None:
        stmt = stmt.where(
            or_(
                Order.created_at < cursor_time,
                and_(Order.created_at == cursor_time, Order.id < cursor_id),
            )
        )
    return list(db.scalars(stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(21)))
```

实际 API 应只返回不透明游标，例如将 `(created_at, id)` 编码为 URL-safe base64 JSON，并严格校验解码结果。每页取 `limit + 1` 条，超过 `limit` 才说明有下一页；返回当前页最后一条生成的游标。排序列、游标比较符与索引顺序必须一致，例如常见的复合索引为 `(buyer_id, created_at DESC, id DESC)`，具体仍需按数据库和查询条件验证。

## 七、并发、唯一约束与幂等性

考虑“一个用户只能点赞一篇文章一次”。仅写代码预检查并不可靠：

```python
existing = db.scalar(select(Like).where(Like.user_id == user_id, Like.article_id == article_id))
if existing is None:
    db.add(Like(user_id=user_id, article_id=article_id))
```

两个并发请求都可能在查询时看见“没有记录”，随后都试图插入。真正的最终防线必须是数据库约束：

```python
class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_like_user_article"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
```

捕获 `IntegrityError` 后必须回滚会话，然后才可继续查询或返回友好错误：

```python
from sqlalchemy.exc import IntegrityError


def like_article(db: Session, user_id: int, article_id: int) -> None:
    try:
        db.add(Like(user_id=user_id, article_id=article_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        # 可选择将重复点赞视为幂等成功，也可返回 409。
```

对于“尝试插入唯一浏览记录，失败也不应影响详情查询”之类的局部操作，使用 savepoint 缩小回滚范围：

```python
def record_once(db: Session, user_id: int, article_id: int) -> bool:
    try:
        with db.begin_nested():
            db.add(ArticleView(user_id=user_id, article_id=article_id))
            db.flush()
        return True
    except IntegrityError:
        return False
```

业务幂等性还要看语义。支付回调可用第三方交易号的唯一约束，并检查金额、订单状态和同一流水号是否重复通知；创建任务可持久化 `Idempotency-Key` 并建立唯一键；文件上传可用内容摘要去重。不要只在内存里 `if exists`，然后宣称接口已经幂等。

多 worker 抢占队列任务时，可在支持的数据库中使用行锁：

```python
task = db.scalar(
    select(Task)
    .where(Task.status == TaskStatus.PENDING)
    .order_by(Task.created_at)
    .with_for_update(skip_locked=True)
    .limit(1)
)
if task is not None:
    task.status = TaskStatus.PROCESSING
    db.commit()
```

重点是只在很短的事务中领取并标记任务，再释放锁执行耗时工作。`SKIP LOCKED` 的语义与可用性取决于数据库和隔离级别；还应设计租约、心跳或超时回收机制，否则 worker 在标记 `PROCESSING` 后崩溃，任务可能永久停在处理中。

## 八、迁移：`create_all()` 为什么不够

`Base.metadata.create_all(engine)` 可以为全新数据库创建缺失表，适合教程或临时测试。但它不会可靠处理已部署表的以下变化：新增非空列、回填历史数据、修改列类型、重命名、建立唯一约束、创建复杂索引、拆分表或删除列。

生产数据库需要版本化迁移工具，例如 Alembic、yoyo-migrations、Flyway 或团队统一工具。无论工具如何选择，核心流程一致：

```text
模型和业务需求变化
  -> 新建不可变的迁移脚本
  -> 在空库与历史数据副本验证升级
  -> 审查索引、锁影响、数据回填和回滚策略
  -> 受控环境按版本顺序执行
  -> 应用在兼容的表结构上运行
```

以新增唯一键为例，迁移前应先查重、处理历史重复数据，再创建唯一索引；直接执行 `ALTER TABLE` 常会因历史脏数据失败。迁移脚本一旦进入共享环境，就不应被修改或重排，而应通过新的向前迁移修正。回滚脚本也不必然无损：删除列、数据转换和合并记录可能本身不可逆，必须在发布计划中说明。

## 九、同步 ORM 与异步 Web 框架如何配合

标准 `Session` 是同步 API。它适合普通 Python 程序和 FastAPI 的同步 `def` 路由：框架会在线程池中执行阻塞端点。若你在 `async def` 里直接运行大量同步 SQL，事件循环会被阻塞；应将同步工作转交线程池，或从驱动、Engine、Session 到每次调用完整迁移为 `AsyncSession`。

不要为了追求“全 async”而把两套会话混在同一个业务函数中。异步不会让慢 SQL 自动变快；索引、查询投影、锁范围与事务设计仍然决定数据库性能。先把同步架构的事务和查询写正确，再根据真实并发 I/O 需求评估异步迁移，通常更稳妥。

## 十、调试与测试清单

开发阶段可以开启 SQL 日志：

```python
engine = create_engine(database_url, echo=True)
```

它能帮助你检查是否出现意外的 N+1 查询、错误的 join 或遗漏的条件；生产环境应使用可脱敏、可分级的日志方案，避免暴露参数和敏感数据。

对每个关键写入用例，至少验证：

- 正常提交后，数据库中的行、状态与关联记录是否全部符合预期。
- 中间步骤失败时，事务是否整体回滚，还是有意留下可恢复状态。
- 重复请求、重复回调和并发请求是否满足预期幂等语义。
- 唯一键、外键、非空约束是否能拦住绕过应用层的错误写入。
- 列表查询是否有稳定排序、合理分页和与查询匹配的索引。
- 迁移能否在空库和已有历史数据的副本上完成。

测试数据库必须与开发、生产隔离。最危险的测试失败并不是断言失败，而是测试清理逻辑指向了不该删除的数据。

## 总结

SQLAlchemy ORM 的主线并不复杂：

```text
定义类型化模型
  -> 创建可复用 Engine
  -> 为每次工作创建独立 Session
  -> 使用 select() 查询、用 Unit of Work 追踪修改
  -> 在完整业务边界 commit 或 rollback
  -> 用数据库约束守住并发事实
  -> 用版本化迁移演进表结构
```

- `Engine` 管连接池，`Session` 管对象和事务；二者生命周期不同。
- `flush` 让 SQL 在事务内提前执行，`commit` 才是最终提交。
- ORM 查询仍是 SQL，需主动设计 join、预加载、分页与索引。
- 业务预检查提升体验，唯一约束和事务才是并发下的最终裁判。
- `create_all()` 不能代替生产迁移；表结构演进必须版本化、可验证、可审查。

结合 [FastAPI 教程：从第一个接口到工程化服务](../fastapi/00-fastapi-from-basics-to-engineering.md) 阅读，就能把“请求进入服务”与“数据可靠落库”两部分拼成完整的 Python 后端基础。
