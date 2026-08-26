+++
date = '2026-08-26T21:00:00+08:00'
draft = false
title = 'SQLite：嵌入式数据库入门，从一个文件到可用应用'
+++

提到数据库，很多人首先想到的是安装一个服务、配置端口、创建账号，再让应用通过网络连接过去。SQLite 不走这条路。它把数据库引擎嵌入到应用程序中，数据通常保存在一个普通文件里；程序打开这个文件，就能执行 SQL。

这并不意味着它只是玩具。SQLite 支持事务、索引、约束、触发器以及相当完整的 SQL；手机应用、桌面软件、浏览器和大量嵌入式设备都在使用它。只是它解决的问题与 MySQL、PostgreSQL 这类数据库服务器不同。先分清边界，才能避免把合适的工具用得面目全非。

## 一、SQLite 是什么形式的数据库

SQLite 是一个**嵌入式、无服务器、关系型数据库管理系统**。它以 C 库的形式提供，应用通过语言绑定直接调用它，而不是先连接到一个长期运行的数据库服务进程。

它的名字可以拆成三个关键词来理解：

- **关系型**：数据按表、行、列组织，使用 SQL 查询和修改；表之间可以用外键表达关系。
- **嵌入式**：数据库引擎与应用处在同一个进程中，作为库被调用。
- **无服务器**：不需要单独启动、守护和运维一个 SQLite 数据库服务。这里的“无服务器”不是云计算中的 Serverless，而是没有独立的数据库服务端进程。

一次典型访问大致是这样：

```text
应用程序
 -> SQLite 库
   -> 数据库文件（例如 app.db）
     -> 操作系统文件系统
```

对比一下会更直观：

| 维度 | SQLite | MySQL / PostgreSQL |
| ---- | ------ | ------------------ |
| 运行形态 | 应用内的库 | 独立数据库服务进程 |
| 数据位置 | 通常是本地数据库文件 | 服务端管理的数据目录 |
| 连接方式 | 直接打开文件 | 通过网络协议连接 |
| 部署成本 | 很低，常常只需携带文件 | 需要安装、配置、监控服务 |
| 并发特点 | 多读很好，但同一时刻通常只有一个写入者 | 面向大量并发读写连接 |
| 典型场景 | 本地应用、缓存、配置、原型、小型服务 | 多用户在线业务、集中式数据服务 |

SQLite 的数据库通常是一个 `.db`、`.sqlite` 或 `.sqlite3` 文件，但后缀没有强制规定。不要因为它是文件就把它当成 JSON 文本：它是有明确页结构的二进制数据库文件，应当由 SQLite 或兼容工具读写。

### 1. “一个文件”并不等于永远只有一个文件

最简单的默认模式下，`app.db` 就是数据库主体。启用 WAL（Write-Ahead Logging，预写式日志）后，同一目录中还可能出现：

- `app.db-wal`：暂存已提交但尚未合并回主数据库的更改。
- `app.db-shm`：供同机多个连接协调 WAL 状态的共享内存文件。

这两个文件是正常现象。备份或复制一个正在使用 WAL 的数据库时，不能只随手复制主文件；应该先使用 SQLite 的备份能力，或者确保没有连接并让 WAL 检查点完成。数据库文件看起来朴素，不代表可以用朴素的方式破坏它。

### 2. SQLite 如何保证数据可靠

SQLite 支持 **ACID 事务**：

- **原子性（Atomicity）**：事务中的操作要么全部成功，要么全部撤销。
- **一致性（Consistency）**：数据要满足已定义的约束和业务规则。
- **隔离性（Isolation）**：并发事务不会随意看到彼此未完成的修改。
- **持久性（Durability）**：提交成功的数据会按配置尽力可靠地落盘。

为了在异常退出或断电后尽量保持一致，它使用回滚日志或 WAL 来记录变更过程。这里仍然要保持现实感：可靠性还依赖磁盘、文件系统、正确的同步配置，以及应用是否把异常当成空气。事务不是免罪符。

## 二、SQLite 适合与不适合什么

SQLite 很适合这些场景：

- 桌面应用、移动应用和浏览器中的本地数据。
- 命令行工具、开发工具的配置、历史记录和缓存。
- 单机部署的小型应用，或读多写少的内部工具。
- 测试、演示和原型：无需准备独立数据库服务。
- 设备端、边缘端等资源有限或网络不稳定的环境。

它也有明确的边界：

- 多台机器需要同时通过网络共享并写入同一份数据。
- 高峰期存在大量并发写事务。
- 需要数据库服务器级的用户、角色、网络鉴权、读写分离或复杂运维能力。
- 数据库文件需要放在不可靠的网络文件系统上供多个主机直接访问。

SQLite 可以有多个读连接，也支持事务；真正需要注意的是**单个数据库文件在同一时刻只有一个写入者**。WAL 模式可以让读操作与写操作更好地并行，但不会把单写者模型变成无限写并发。若业务的核心需求是多节点高并发写入，应当选择服务端数据库，而不是要求 SQLite 扮演它不擅长的角色。

## 三、五分钟开始使用 `sqlite3`

`sqlite3` 是 SQLite 官方提供的命令行客户端。安装 SQLite 后，在目标目录执行下面的命令即可创建或打开数据库：

```bash
sqlite3 demo.db
```

第一次执行时 `demo.db` 不存在，SQLite 会在当前目录创建它。进入交互界面后，点号开头的是客户端命令，不是 SQL：

```text
.help
.databases
.tables
.quit
```

为了让结果更易读，可以先设置输出格式：

```sql
.headers on
.mode column
```

然后创建一张保存文章的表。SQL 语句要以分号结束；不结束，客户端会认为你还没有写完，这种沉默通常不是它在思考人生。

```sql
CREATE TABLE article (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

这里几个字段值得认识：

- `INTEGER PRIMARY KEY`：在普通表中会成为行标识的别名；未显式指定 `id` 时，SQLite 可以自动分配一个整数值。
- `TEXT`：文本类型。
- `NOT NULL`：该列不能为 `NULL`。
- `DEFAULT`：插入时未提供该列时使用的默认值。
- `CHECK`：限制 `status` 只能取列出的两个值。

插入几行数据：

```sql
INSERT INTO article (title, content, status)
VALUES
    ('SQLite 是什么', '一个嵌入式关系型数据库。', 'published'),
    ('事务的意义', '要么全部成功，要么全部回滚。', 'draft');
```

查询数据：

```sql
SELECT id, title, status, created_at
FROM article
ORDER BY id;
```

更新和删除的写法与其他关系型数据库很接近：

```sql
UPDATE article
SET status = 'published'
WHERE id = 2;

DELETE FROM article
WHERE id = 2;
```

`UPDATE` 和 `DELETE` 若漏掉 `WHERE`，影响的是整张表。数据库会忠实执行语句，不会替你猜测“你大概不是这个意思”。动手前先写 `SELECT` 确认目标范围，是一个相当便宜的习惯。

## 四、用事务保证一组操作的一致性

假设发布文章时，既要更新文章状态，也要写一条操作日志；两步应当作为一个整体成功或失败。这时使用事务：

```sql
CREATE TABLE operation_log (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES article(id)
);

PRAGMA foreign_keys = ON;

BEGIN;

UPDATE article
SET status = 'published'
WHERE id = 1;

INSERT INTO operation_log (article_id, action)
VALUES (1, 'publish');

COMMIT;
```

若中间发现条件不成立或应用捕获到异常，应执行：

```sql
ROLLBACK;
```

`PRAGMA foreign_keys = ON` 很重要。SQLite 的外键约束需要对**每个数据库连接**显式开启；不要以为写了 `FOREIGN KEY` 就自然会生效。不同语言驱动创建的新连接也需要相应配置。

## 五、用 Python 操作 SQLite

Python 标准库自带 `sqlite3` 模块，因此不需要额外安装驱动。下面的例子创建表、以参数化方式插入数据，并查询已发布文章：

```python
import sqlite3

with sqlite3.connect("demo.db") as conn:
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS todo (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0
                CHECK (done IN (0, 1))
        )
    """)

    conn.execute(
        "INSERT INTO todo (title, done) VALUES (?, ?)",
        ("阅读 SQLite 文档", 0),
    )

    rows = conn.execute(
        "SELECT id, title, done FROM todo WHERE done = ? ORDER BY id",
        (0,),
    ).fetchall()

for todo_id, title, done in rows:
    print(todo_id, title, done)
```

`with sqlite3.connect(...) as conn` 在正常结束时会提交事务；代码块内抛出异常时会回滚。连接对象离开 `with` 后是否自动关闭取决于所用 Python 版本和写法，因此在长期运行的程序中，仍应明确管理连接的生命周期。

### 1. 为什么必须使用参数化查询

不要把用户输入直接拼接进 SQL：

```python
# 不要这样写
title = "用户输入"
sql = f"SELECT * FROM todo WHERE title = '{title}'"
```

正确方式是把 SQL 结构与数据参数分开：

```python
sql = "SELECT * FROM todo WHERE title = ?"
rows = conn.execute(sql, (title,)).fetchall()
```

`?` 是参数占位符。驱动会正确处理字符串中的引号等特殊字符，并避免这类值被解释成 SQL 语法。参数化查询既减少注入风险，也让代码更容易维护。

需要动态指定表名、列名或排序方向时，参数占位符并不适用，因为它们属于 SQL 结构而不是数据值。这些内容应当由程序用白名单映射生成，绝不能直接接受用户输入。

## 六、类型：灵活，但不能想当然

SQLite 使用的是**动态类型系统和类型亲和性（type affinity）**。一个值自身带有存储类型，主要包括：

- `NULL`
- `INTEGER`
- `REAL`
- `TEXT`
- `BLOB`

表声明中的 `VARCHAR(50)`、`BOOLEAN`、`DATETIME` 等类型名称更多是在表达意图，并会影响类型亲和性；它不像某些数据库那样严格按照列声明限制每个值的物理类型。例如，`BOOLEAN` 通常以 `0` 和 `1` 保存，日期时间常保存为 ISO 8601 文本、Unix 时间戳整数或 Julian day 数值。

这份灵活性对嵌入式使用很方便，但业务模型不应该因此变得含糊。建议：

- 布尔值统一存为 `0` / `1`，配合 `CHECK (done IN (0, 1))`。
- 时间统一选择一种格式；多数业务使用 UTC 的 ISO 8601 文本会更直观。
- 金额优先存“分”等最小货币单位的 `INTEGER`，避免浮点数精度问题。
- 对枚举值、范围值使用 `NOT NULL`、`CHECK`、外键等约束。

如果确实需要更严格的列类型约束，可以了解 SQLite 的 `STRICT` 表。但无论是否使用它，输入校验和业务约束都不该完全推给数据库。

## 七、索引与查询性能

索引不是越多越好。它能加快查询，却会增加写入成本和文件体积；每次插入、更新、删除都要同步维护相关索引。

对于下面的高频查询：

```sql
SELECT id, title, created_at
FROM article
WHERE status = 'published'
ORDER BY created_at DESC;
```

可以建立与筛选、排序顺序匹配的索引：

```sql
CREATE INDEX idx_article_status_created_at
ON article (status, created_at DESC);
```

SQLite 提供 `EXPLAIN QUERY PLAN` 来观察查询计划：

```sql
EXPLAIN QUERY PLAN
SELECT id, title, created_at
FROM article
WHERE status = 'published'
ORDER BY created_at DESC;
```

若输出中出现 `USING INDEX`，说明查询可能正在利用索引；若出现全表扫描，也不必立刻恐慌。表很小时全表扫描常常更便宜，性能优化应该以真实查询和数据量为依据，而不是以“索引数量看起来很努力”为依据。

## 八、并发、WAL 与几个实用设置

默认的回滚日志模式已经足够满足许多简单场景。对于读多写少、同时存在读写的本地应用，WAL 模式通常是一个值得评估的选择：

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
```

- `journal_mode = WAL`：开启 WAL 模式。读者通常不必等待写者完成，读写并发体验更好。
- `busy_timeout = 5000`：遇到数据库暂时被占用时，最多等待 5 秒，而不是立即返回“database is locked”。

这些设置没有普遍适用的神奇组合。尤其要注意：

- 写事务要短。不要在事务中等待网络请求、读取大文件或进行耗时计算。
- 同一个连接不要被多个线程随意并发使用；让每个线程或任务按驱动规则管理自己的连接。
- 不要通过多台机器共享目录来共同写一个 SQLite 文件。
- 当频繁出现锁竞争时，先检查是否有过长事务和并发写设计；单纯加大超时只是把问题排队。

## 九、备份、迁移与日常维护

数据库文件适合随应用携带，但仍然应该把它当作重要数据，而不是“反正能重新生成”的临时文件。

### 1. 用备份命令导出

`sqlite3` 客户端可以生成一个一致性备份：

```bash
sqlite3 demo.db ".backup 'demo-backup.db'"
```

也可以导出为可阅读的 SQL 文本：

```bash
sqlite3 demo.db ".dump" > demo.sql
```

恢复 SQL 导出文件：

```bash
sqlite3 restored.db < demo.sql
```

### 2. 用版本化迁移管理表结构

不要在生产环境中手工修改表结构，然后希望所有环境恰好同步。更稳妥的做法是为每次结构变更写一份有序迁移，例如：

```text
migrations/
├── 001_create_article.sql
├── 002_add_article_summary.sql
└── 003_create_operation_log.sql
```

应用启动或部署时记录已执行的版本，并按顺序执行未完成的迁移。即使项目很小，这也能回答一个极其实际的问题：某个环境的表结构为什么和另一个不一样？

### 3. 检查与优化文件

可以使用完整性检查：

```sql
PRAGMA integrity_check;
```

当经过大量删除或更新后需要回收文件尾部的空闲空间，可以评估：

```sql
VACUUM;
```

`VACUUM` 会重建数据库并可能占用额外磁盘空间，也会持有较重的锁；应避开业务高峰，并先备份。维护命令不是“输入后感觉安心”的装饰品，应当在理解成本后执行。

## 十、一个最小可用的使用清单

如果你刚开始在项目中使用 SQLite，可以先遵循下面几条：

- 用数据库文件的绝对路径或由应用配置确定的路径，避免工作目录变化导致创建出意外的新库。
- 建表时明确写 `PRIMARY KEY`、`NOT NULL`、`DEFAULT`、`CHECK` 和需要的外键。
- 每个连接都开启 `PRAGMA foreign_keys = ON`。
- 所有外部输入都使用参数化查询。
- 需要原子性的多步修改必须包在事务中。
- 根据真实查询建立索引，并用 `EXPLAIN QUERY PLAN` 验证。
- 读多写少时再评估 WAL；写事务尽量短。
- 用 `.backup` 或应用内备份接口做一致性备份，不要在 WAL 工作时只复制一个主文件。

## 十一、总结

SQLite 的核心价值不是“省掉安装步骤”，而是把可靠的关系型数据能力放进一个易分发、易部署的本地文件中。

当数据主要由单机应用使用、写入并发有限、希望减少基础设施时，SQLite 往往是非常成熟的选择。反过来，当需求已经变成多节点共享、大量并发写入和集中式权限治理时，迁移到数据库服务器并不是 SQLite 的失败，而是需求已经进入另一类问题。工具没有自尊心，只有使用它的人会把边界误解成缺陷。
