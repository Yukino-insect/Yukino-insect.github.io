+++
date = '2026-09-28T00:00:00+08:00'
draft = false
title = 'Python 类注解、描述符与元类：ORM 声明式映射为何能工作'
+++

在 Java 中，框架常读取注解，再借助反射、动态代理或字节码增强，把一个看似普通的类接入 IoC、AOP、ORM 等机制。看到 Python 的 ORM 模型时，人们也常自然地提出同一个问题：`id: Mapped[int] = mapped_column(...)` 里的注解是否就是 Java 注解？字段是不是被某种对象“包装”了？

答案是：**Python 当然可以把类声明转化为框架元信息，但它的主要工具并不是 Java 那种注解系统。**类型注解通常只是可读取的声明；真正接管属性读写、校验、查询表达式和变更跟踪的，往往是**描述符**。框架再通过**元类、`__init_subclass__` 或类装饰器**，在类创建时收集这些声明并建立映射。

以 SQLAlchemy 2.x 为例，模型类同时包含两层含义：对人和类型检查器来说，它是带类型的 Python 类；对 ORM 来说，它是表、列、关系和映射规则的声明。表面上是一行字段定义，背后却是一次精心安排的类创建过程。没有什么魔法，只是把 Python 对象模型用得相当彻底而已。

## 一、先纠正一个容易混淆的词：Python 的“注解”不是 Java Annotation

在 Python 语境中，至少有两种经常被统称为“注解”的东西，然而它们不是同一种机制。

| 写法 | 正确名称 | 主要作用 |
| --- | --- | --- |
| `name: str` | 类型注解（type annotation） | 为工具和框架提供类型元信息 |
| `@decorator` | 装饰器（decorator） | 用一个可调用对象改造函数或类 |
| `@Entity`、`@Transactional` | Java 注解（annotation） | 由 Java 反射 API 读取的结构化元信息 |

Python 没有与 Java Annotation 完全对应的一套内建声明与反射 API。`name: str` 的核心行为是把信息放进类或函数的 `__annotations__`，而不是自动产生运行时逻辑：

```python
class User:
    name: str
    age: int = 18


print(User.__annotations__)
# {'name': <class 'str'>, 'age': <class 'int'>}

print(User.__dict__.get("name"))
# None：只有注解，没有给类属性赋值

print(User.__dict__["age"])
# 18：age 既有注解，也有一个普通类属性默认值
```

仅写 `name: str` 时，Python 不会检查你后来是否真的赋了字符串，也不会拦截 `user.name` 的读写。它甚至不会自动创建 `name` 这个类属性。静态类型检查器（mypy、pyright）、IDE、Pydantic、dataclasses、SQLAlchemy 等工具可以读取这份元信息并赋予它意义；**意义来自工具或框架，而不是注解语法本身。**

这和 Java 中“框架扫描某个注解”的直觉有一点相似，但要避免把两者等同。Python 的类型注解更接近一份可由运行时读取的类型声明，框架可以用，也可以完全不用。

### 延迟求值与 `get_type_hints()`

现代 Python 项目还经常使用：

```python
from __future__ import annotations


class Article:
    author: User
```

这能方便前向引用，但 `__annotations__` 中的值可能是字符串或延迟求值形式。框架或自己的工具若需要拿到已经解析的真实类型，通常应使用 `typing.get_type_hints()`，并在需要时提供正确的全局与局部命名空间：

```python
from typing import get_type_hints

hints = get_type_hints(Article)
print(hints["author"])
```

因此，若你在写一个通用框架，直接假设 `cls.__annotations__["author"] is User` 并不稳妥。类型提示的求值时机、前向引用和导入循环都需要被纳入设计；框架代码本来就不该靠侥幸运行。

## 二、关键机制一：描述符让“属性”不再只是字典中的一个值

普通实例属性通常保存在实例的 `__dict__` 中：

```python
class PlainUser:
    pass


user = PlainUser()
user.name = "Yukino"

print(user.__dict__)
# {'name': 'Yukino'}
```

但只要类属性实现了 `__get__`、`__set__` 或 `__delete__` 中的任意方法，它就是**描述符（descriptor）**。访问 `user.name` 时，Python 不再只是查找字典；它会按属性访问协议调用描述符的方法。

下面是一个最小的字符串字段描述符：

```python
class StringField:
    def __set_name__(self, owner, name):
        self.name = name
        self.storage_name = f"_{name}"

    def __get__(self, instance, owner=None):
        if instance is None:
            # 通过类访问时返回字段对象本身，供框架读取元信息或构造表达式。
            return self
        return instance.__dict__.get(self.storage_name)

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise TypeError(f"{self.name} 必须是 str")
        instance.__dict__[self.storage_name] = value


class User:
    name: str = StringField()


user = User()
user.name = "Yukino"          # 实际调用 StringField.__set__
print(user.name)              # 实际调用 StringField.__get__
print(user.__dict__)          # {'_name': 'Yukino'}
print(User.name.name)         # 'name'
```

`User.name` 并不是字符串默认值，而是一个 `StringField` 对象；`user.name` 的读写被它接管。这正是“字段被包装了吗”这个问题的核心答案：**在很多 Python ORM 中，是的，但更精确地说，是类属性被替换或装配为描述符/受控属性对象。**实例中的真实数据仍可能放在 `__dict__`、`__slots__` 或 ORM 自己的状态容器中，取决于框架的实现。

### 数据描述符为什么能优先于实例字典

上例的 `StringField` 同时实现了 `__get__` 与 `__set__`，它是**数据描述符（data descriptor）**。数据描述符的优先级高于 `instance.__dict__`：即使你手动写入 `user.__dict__["name"] = "绕过值"`，读取 `user.name` 时仍会执行描述符逻辑。

```text
读取 instance.attr 时，重要的查找顺序可概括为：

类上的数据描述符
    -> 实例 __dict__
    -> 类上的普通属性或非数据描述符
    -> __getattr__（若定义）
```

这条规则使字段对象可以可靠地实现类型校验、延迟加载、缓存失效、脏数据标记、审计日志等功能。`property` 也是描述符；方法在通过实例访问时会自动绑定 `self`，同样依赖描述符协议。你每天都在使用它，只是通常没有必要特意注意到。

### 类访问与实例访问可以拥有不同语义

ORM 尤其需要区分两种访问方式：

```python
User.name                 # 类访问：表示“users.name 这一列”
user.name                 # 实例访问：表示“这一行记录的 name 值”
User.name == "Yukino"    # 类访问：构造 WHERE 条件，而不是比较两个字符串
```

这并不违反 Python 的直觉，只是描述符可以根据 `instance is None` 分支返回不同对象。类访问返回列或查询表达式对象，实例访问返回真实值；同一份写法得以同时服务查询构造和对象状态访问。

## 三、关键机制二：类体执行后，框架有机会把声明“收编”为元数据

理解 ORM 前，先把 `class` 看成一段会执行的代码，而不是某种静态结构声明。简化后的类创建过程如下：

```text
1. 选择元类；默认元类是 type
2. 元类的 __prepare__ 创建类命名空间（通常是一个字典）
3. 执行 class 代码块，把 name、__annotations__、StringField() 等放入命名空间
4. 调用元类创建类对象；通常最终会调用 type.__new__
5. type.__new__ 调用描述符的 __set_name__(owner, name)
6. 依次触发基类的 __init_subclass__ 等类创建钩子
7. 对新类应用类装饰器（若有）
```

例如执行下面这段代码时，右侧的 `StringField()` 先创建一个普通对象，随后它才在类创建阶段知道自己被绑定为 `User.name`：

```python
class User:
    name: str = StringField()
```

`__set_name__` 正是描述符获得属性名的标准入口。早期框架常在元类中遍历属性并手动设置名称；现在如果只是让描述符知道自己绑定到哪里，优先实现 `__set_name__` 更自然。

### 元类、`__init_subclass__` 和类装饰器如何选择

它们都能在“一个类刚刚定义完成”的附近介入，但能力和复杂度不同。

| 机制 | 典型使用方式 | 适合做什么 | 代价 |
| --- | --- | --- | --- |
| 类装饰器 | `@register_model` | 为已创建的类登记元信息 | 简单，但不能控制类命名空间和创建过程 |
| `__init_subclass__` | 定义在基类中 | 约束和注册子类 | 大多数轻量框架已经足够 |
| 元类 | `class Model(metaclass=ModelMeta)` | 收集字段、替换类属性、处理继承、定制类创建 | 最强，也最容易制造继承/元类冲突 |

Python 框架并不一定非得使用元类。`dataclasses.dataclass` 就是类装饰器；不少注册型基类可以只用 `__init_subclass__`。而 Django ORM、SQLAlchemy 等需要深入处理字段声明、继承、映射与类级查询表达式的框架，通常会在类创建路径中使用元类或等价的声明式构造机制。

## 四、自己实现一个极简“声明式 ORM”

下面的例子并不会连接数据库。它只实现最核心的两件事：字段对象接管属性读写，元类在类创建时收集字段并根据类型注解生成一份表元数据。先把这层看清楚，再看成熟 ORM 时就不会觉得它凭空变出了数据库。

```python
from __future__ import annotations

from typing import Any, get_type_hints


class Field:
    def __init__(self, *, primary_key: bool = False, nullable: bool = True):
        self.primary_key = primary_key
        self.nullable = nullable
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.storage_name = f"_{name}"

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.storage_name)

    def __set__(self, instance: object, value: Any) -> None:
        if value is None and not self.nullable:
            raise ValueError(f"{self.name} 不能为空")
        instance.__dict__[self.storage_name] = value


class String(Field):
    def __set__(self, instance: object, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{self.name} 必须是 str")
        super().__set__(instance, value)


class Integer(Field):
    def __set__(self, instance: object, value: int | None) -> None:
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError(f"{self.name} 必须是 int")
        super().__set__(instance, value)


class ModelMeta(type):
    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> type:
        # 先继承父类字段；子类同名字段可以覆盖它。
        fields: dict[str, Field] = {}
        for base in bases:
            fields.update(getattr(base, "__fields__", {}))

        # 类体中的 Field 实例是声明；它们将在 type.__new__ 中获得 __set_name__ 回调。
        fields.update(
            {
                attr_name: value
                for attr_name, value in namespace.items()
                if isinstance(value, Field)
            }
        )

        cls = super().__new__(mcls, name, bases, namespace)
        cls.__fields__ = fields
        cls.__field_types__ = get_type_hints(cls)
        cls.__table_name__ = namespace.get("__table_name__", name.lower())
        return cls


class Model(metaclass=ModelMeta):
    def __init__(self, **values: Any) -> None:
        unknown = values.keys() - self.__fields__.keys()
        if unknown:
            raise TypeError(f"未知字段：{', '.join(sorted(unknown))}")
        for name, value in values.items():
            setattr(self, name, value)


class User(Model):
    __table_name__ = "users"

    id: int = Integer(primary_key=True, nullable=False)
    name: str = String(nullable=False)
    email: str | None = String()


user = User(id=1, name="Yukino", email=None)

print(User.__table_name__)       # users
print(User.__fields__)           # {'id': <Integer ...>, 'name': <String ...>, ...}
print(User.__field_types__)      # {'id': int, 'name': str, 'email': str | None}
print(user.__dict__)             # {'_id': 1, '_name': 'Yukino', '_email': None}
```

这个例子揭示了声明式框架的一般形状：

```text
class User(Model):
    name: str = String(nullable=False)
       │              │
       │              └─ 运行时字段对象：校验并拦截读写
       └─ 类型元信息：工具、框架和 IDE 可以读取

ModelMeta
    └─ 在 User 创建时收集字段和注解，生成模型级元数据
```

成熟 ORM 只是在此基础上增加了很多不能省略的细节：字段到数据库类型的映射、主键与外键、关系加载、SQL 方言、连接池、事务、对象身份映射、延迟加载、变更检测、缓存失效、并发控制等。概念上并没有突然跳跃；代码量会跳跃，毕竟数据库不接受“原理我懂了”作为提交结果。

### 为何示例同时保留类型注解和字段对象

只写下面这一行：

```python
name: str
```

框架可以知道它大概是一个字符串字段，却没有任何对象接管 `user.name`。反过来，只写 `name = String()`，运行时行为已经可以实现，但类型检查器不知道 `user.name` 的精确类型，框架也少了一份通用、可声明的类型信息。

因此现代 Python 库常把两者并列：**注解负责“它是什么”，字段对象负责“访问它时做什么”。**这也解释了为什么 ORM 模型看起来比普通数据类更“厚”：它不只描述数据形状，还声明了持久化和状态管理行为。

## 五、SQLAlchemy 2.x 中真实发生了什么

上一篇 [SQLAlchemy 2.x 入门](frameworks/sqlalchemy/00-introduction.md) 已介绍过基础模型、`Engine` 与 `Session`。现在回到其中最典型的字段声明：

```python
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
```

可以把它理解为下面的分工，而不是把它看成一条不透明的专用语法：

| 声明部分 | 主要含义 |
| --- | --- |
| `Base(DeclarativeBase)` | 建立 SQLAlchemy 的声明式映射基类与元数据收集入口 |
| `__tablename__` | 指定对应的数据表名 |
| `Mapped[int]` | 标明这是一个由 ORM 管理的、Python 侧类型为 `int` 的映射属性 |
| `mapped_column(...)` | 声明列的数据库配置，如主键、长度、是否可空、默认值等 |

在 `User` 类创建时，SQLAlchemy 会扫描这些声明，创建或补充 `Table`、`Column`、Mapper 等映射对象，并把模型属性安装成受 ORM 管理的属性。之后的属性访问语义大致是：

```python
user = User(name="Yukino")

user.name                # 实例层：读取该对象当前的 name 值，ORM 能追踪其变化
user.name = "雪之下"     # 实例层：写入值并标记对象状态可能发生变化

User.name                # 类层：代表可用于 SQL 表达式的映射属性
User.name == "Yukino"   # 类层：得到 SQL 条件表达式，不会直接比较字符串
```

例如：

```python
from sqlalchemy import select

stmt = select(User).where(User.name == "Yukino")
print(stmt)
```

这里 `User.name == "Yukino"` 不是普通的 `str.__eq__` 比较，而是 ORM 属性对象重载比较运算符后构造出的条件。`Session` 在适当时机把 `stmt` 编译为目标数据库方言的 SQL，再以绑定参数执行。类属性能够用于写查询，实例属性能够用于取值和脏检查，正是描述符和 ORM 属性代理共同带来的两套语义。

### `mapped_column()` 返回的对象会永远原封不动地留在类上吗

不必把它理解成“右侧对象从此就是左侧属性的最终形态”。声明式映射期间，SQLAlchemy 会对类字典中的声明进行解释和**instrumentation（属性装配）**。最终通过 `User.name` 访问到的是 ORM 管理的映射属性；通过 `user.name` 访问到的是实例状态中的值。具体内部对象和实现细节会随 SQLAlchemy 版本演进，但对应用代码而言，上面两种访问语义才是稳定的契约。

所以更准确的回答是：**字段声明起初确实是类命名空间中的对象；框架在建类时收集、转换或装配它们，最后以描述符式的受控属性暴露给类和实例。**不是给每个字段值简单套上一层包装盒，而是让属性查找本身进入框架的控制路径。

### `relationship()` 与延迟加载：描述符还能替你“晚一点再查”

关联关系也遵循类似规则：

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped[User] = relationship()
```

当 `article.author` 尚未加载且当前对象仍关联着可用的 `Session` 时，ORM 可能在属性被访问的一刻再发送 SQL 查询。这叫**延迟加载（lazy loading）**。它很方便，但在循环中逐个访问关联对象时可能造成 N+1 查询；相关的加载策略和处理方式可参见前文的 SQLAlchemy 入门文章。

也要注意边界：一个已经脱离或关闭会话的对象未必还能延迟加载关联属性，届时可能抛出异常。属性访问看起来像内存读取，不代表它不可能触发网络 I/O。把这点忘掉，性能和事务边界就会提醒你，只是提醒方式往往不太温柔。

## 六、不同 Python 框架分别怎样利用这些机制

“类继承 + 字段声明”不是 ORM 专属模式。不同框架选择的机制略有不同，目的都是把开发者写下的声明转为可执行规则。

| 框架或工具 | 常见声明形式 | 类创建时的主要动作 | 属性访问时的主要动作 |
| --- | --- | --- | --- |
| `dataclasses` | `name: str`、`field(...)` | 类装饰器读取注解，生成 `__init__`、`__repr__` 等方法 | 多数情况下是普通属性 |
| Pydantic | `name: str`、`Field(...)` | 元类收集类型与字段配置，生成校验模型信息 | 初始化/赋值时按配置校验与转换 |
| Django ORM | `name = models.CharField(...)` | 模型元类收集 `Field` 并建立数据库模型元数据 | 通过 ORM 属性和描述符管理字段/关联访问 |
| SQLAlchemy ORM | `name: Mapped[str] = mapped_column(...)` | 声明式映射构造表、列和 Mapper，并装配属性 | 追踪状态、构造 SQL 表达式、支持关系加载 |

不要据此认为“只要继承基类，字段就一定被包装”。继承基类本身不会自动产生任何特殊能力；能力取决于基类的钩子、元类、装饰器以及类属性对象的实现。一个普通基类也可以什么都不做：

```python
class Base:
    pass


class User(Base):
    name: str
```

此处既没有字段描述符，也没有元类收集行为，`name: str` 只是注解。换言之，先看框架给 `Base`、字段工厂和模型元类赋予了什么行为，再推断模型有什么能力；只盯着冒号和继承关系，结论通常会过于草率。

## 七、Python 与 Java 的机制对照：相似的目标，不同的切入点

两种语言都能让框架从声明生成运行时行为，但常用的扩展点不同。

| 问题 | Java 中常见做法 | Python 中常见做法 |
| --- | --- | --- |
| 在源码中表达元信息 | 运行时注解，如 `@Entity`、`@Column` | 类型注解、字段对象、类属性约定 |
| 在类定义后读取结构 | 反射读取 `Class`、字段、方法、注解 | `__dict__`、`__annotations__`、`inspect`、`typing.get_type_hints()` |
| 拦截对象方法 | JDK 动态代理、CGLIB、字节码增强 | 装饰器、包装对象、`__getattribute__`、描述符 |
| 拦截字段/属性访问 | 常依赖字节码增强、getter/setter、代理 | 描述符、`property`、`__setattr__` |
| 在类定义阶段加工声明 | 注解处理器、框架启动扫描 | 元类、`__init_subclass__`、类装饰器 |

Java 的代理更常围绕接口和方法调用展开，例如事务 AOP 拦截 `service.save()`；Python 也能用装饰器实现相似拦截：

```python
from functools import wraps


def transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print("begin transaction")
        try:
            result = func(*args, **kwargs)
        except Exception:
            print("rollback")
            raise
        else:
            print("commit")
            return result

    return wrapper


class UserService:
    @transactional
    def create_user(self, name: str) -> None:
        print(f"create user: {name}")
```

`@transactional` 在这里是装饰器：类定义阶段，原方法被包装函数替换。它不是 Java 注解，也不需要运行时扫描。当然，真正的事务实现还要处理连接、嵌套事务、异常类型和上下文传播；这个例子仅说明拦截入口。把 `print` 换成事务系统不会自动使边界设计正确，这种童话通常只能存在于演示代码中。

## 八、阅读和调试声明式模型的实用方法

当模型行为不符合预期时，与其猜测“框架是不是偷偷做了什么”，不如直接查看类和实例上实际存在的对象。

```python
from typing import get_type_hints

print(User.__dict__.keys())
print(get_type_hints(User))
print(vars(user))
print(type(User.name))
```

对于 SQLAlchemy，还可以查看映射和生成的 SQL：

```python
from sqlalchemy import inspect, select

mapper = inspect(User)
print(mapper.local_table)
print(mapper.columns.keys())

stmt = select(User).where(User.name == "Yukino")
print(stmt)
```

调试时尤其值得检查以下问题：

- 这个字段只有类型注解，还是也有框架提供的字段对象？只有前者通常不会有运行时控制能力。
- `User.field` 与 `user.field` 分别返回什么？它们常常对应“查询表达式”和“实例值”两种完全不同的语义。
- 属性读取是否可能触发 SQL 或其他 I/O？关系字段、延迟加载字段尤其要小心。
- 框架是否使用了继承字段？自定义元类收集字段时要先合并父类，再允许子类覆盖同名字段。
- 前向引用是否导致类型提示没有正确解析？必要时用 `get_type_hints()`，而不是仅看原始 `__annotations__`。

## 九、总结

Python 的声明式 ORM 并不是把 Java 注解原封不动地搬了过来。它通常由几块相互配合的机制组成：

- **类型注解**保存“字段应当是什么类型”等声明性元信息；单独存在时通常不产生运行时校验或持久化行为。
- **字段对象与描述符**接管属性读写，因此能实现校验、脏检查、延迟加载和类级 SQL 表达式。
- **元类、`__init_subclass__` 或类装饰器**在类创建时收集声明、处理继承，并生成模型级元数据。
- 对 SQLAlchemy 而言，`Mapped[...]` 与 `mapped_column(...)` 共同声明映射属性；框架随后对这些声明进行属性装配，使 `User.name` 和 `user.name` 分别服务于查询与实例状态。
- 基类不是魔法来源。要判断一个模型的行为，应该检查基类、元类、字段对象和类创建钩子，而不是只看它“继承了谁”。

掌握这条链路后，再遇到 Pydantic、Django、SQLAlchemy 或自定义配置框架的模型声明，就可以沿着同一条线拆解：**元信息从哪里来？谁在建类时收集它？谁在属性访问时接管它？最终生成了什么运行时对象？**能回答这四个问题，所谓“框架魔法”大多就只剩下工程细节，而不再值得过分神秘化。
