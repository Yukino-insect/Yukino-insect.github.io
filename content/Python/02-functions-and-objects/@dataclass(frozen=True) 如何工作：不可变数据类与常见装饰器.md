+++
date = '2026-10-20T14:30:00+08:00'
draft = false
title = '@dataclass(frozen=True) 如何工作：不可变数据类与常见装饰器'
+++

下面的类看起来只声明了三个字段，却比普通类多做了不少工作：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class EnhanceModeInfo:
    mode: EnhanceMode
    title: str
    description: str
```

`@dataclass` 会读取类注解并为这类主要用于承载数据的类生成方法；`frozen=True` 则禁止实例字段在构造后被重新赋值或删除。它适合表达“模式说明一旦创建就不应改写”的值对象，但不等于递归地冻结内部所有对象，更不能替业务系统自动保证线程安全或持久化不可变。

本文先将这段代码展开，再把 `@dataclass` 放回 Python 装饰器体系中，区分属性、方法、缓存、抽象和资源管理等常见装饰器各自的职责。若想深入理解自定义函数装饰器的闭包、`functools.wraps`、同步/异步包装和多层应用顺序，请继续阅读[Python 装饰器：从闭包到同步与异步的可复用横切逻辑](Python 装饰器：从闭包到同步与异步的可复用横切逻辑.md)。

## 一、`@dataclass` 做了什么

装饰器语法先定义类，再把类对象交给装饰器处理。概念上：

```python
@dataclass(frozen=True)
class EnhanceModeInfo:
    ...


# 近似于：
EnhanceModeInfo = dataclass(frozen=True)(EnhanceModeInfo)
```

`dataclass` 使用类上的类型注解识别字段，并按配置生成若干特殊方法。对给定示例，它至少提供了接近下面效果的构造、显示和相等性比较：

```python
info = EnhanceModeInfo(
    mode=EnhanceMode.REAL_ESRGAN_ANIME,
    title="动漫增强",
    description="适合动漫、插画和线稿。",
)

print(info.title)
print(info)
# EnhanceModeInfo(mode=<EnhanceMode...>, title='动漫增强', ...)
```

默认配置下，数据类主要会生成：

| 能力 | 对应方法 | 作用 |
| ---- | -------- | ---- |
| 构造参数 | `__init__` | 按字段顺序/默认值初始化实例 |
| 可读表示 | `__repr__` | 便于日志、调试和测试失败信息 |
| 值相等性 | `__eq__` | 同类实例按字段值比较 |
| 模式匹配位置参数 | `__match_args__` | 支持部分结构化模式匹配写法 |

它并不进行运行时类型校验。`title: str` 是字段声明和类型工具可读取的元数据，不会阻止你在纯 Python 运行时传入整数。若需要输入验证、解析或序列化策略，应选择显式校验、Pydantic 等合适工具；不要期望 `dataclass` 悄悄兼任所有框架职责。

## 二、`frozen=True` 限制了什么

普通数据类实例的字段可以被重新绑定：

```python
@dataclass
class MutableInfo:
    title: str


info = MutableInfo("初版")
info.title = "修订版"
```

加入 `frozen=True` 后，这类赋值会抛出 `FrozenInstanceError`：

```python
info = EnhanceModeInfo(
    mode=EnhanceMode.REAL_ESRGAN_ANIME,
    title="动漫增强",
    description="适合动漫、插画和线稿。",
)

info.title = "通用增强"  # FrozenInstanceError
```

装饰器会生成限制属性设置和删除的逻辑。初始化仍然可以完成：生成的 `__init__` 会用适当方式写入字段；这并不意味着所有后续修改都被容忍。

### 1. 冻结是浅层的，不是递归不可变

以下定义虽然冻结了字段绑定，仍然允许修改字段所引用的列表：

```python
@dataclass(frozen=True)
class Preset:
    tags: list[str]


preset = Preset(tags=["anime"])
preset.tags.append("line-art")  # 可以，列表本身仍可变
```

这里没有给 `preset.tags` 重新赋值，改变的是原列表对象。若值对象需要可靠不可变，应优先使用 `tuple`、`frozenset`、不可变嵌套数据类或在构造时复制可变输入：

```python
@dataclass(frozen=True)
class SafePreset:
    tags: tuple[str, ...]
```

“冻结”保证的是对象字段的绑定关系，不是替你追踪对象图中所有后代的可变性。把这层边界说清楚，比把 `frozen` 想象成一层绝对护盾可靠得多。

### 2. 哈希、字典键与集合元素

可变对象通常不应按字段值生成哈希，因为放入 `set` 或作为 `dict` 键后若字段改变，哈希表会失去一致性。默认 `@dataclass(eq=True)` 会让普通可变数据类不可哈希。

当 `frozen=True` 且保留默认 `eq=True` 时，数据类通常会生成基于字段的 `__hash__`，使其可用于集合或字典键：

```python
known_modes = {
    EnhanceModeInfo(
        EnhanceMode.REAL_ESRGAN_GENERAL,
        "通用增强",
        "适合照片和一般图像。",
    )
}
```

但所有参与哈希的字段也必须可哈希。若字段中放入 `list` 或 `dict`，把实例放进集合时仍会得到 `TypeError`。不要用 `unsafe_hash=True` 逃避设计问题；除非你能严格证明对象在作为键期间不会改变，否则它只是把错误推迟到更难排查的位置。

## 三、默认值、`field` 与构造后校验

有默认值的字段必须位于无默认值字段之后，这是 Python 函数参数规则的自然延伸：

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnhanceModeInfo:
    mode: EnhanceMode
    title: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
```

对于 `list`、`dict`、`set` 等可变默认值，必须使用 `default_factory`，不能写 `tags: list[str] = []`。后者会让所有实例共享同一个列表；数据类不会替你消除这一经典陷阱。

还可定义 `__post_init__` 做构造后的交叉字段校验。冻结类中若确有必要规范化字段，需要使用 `object.__setattr__`，并把这种绕过限制控制在初始化阶段：

```python
@dataclass(frozen=True)
class NormalizedInfo:
    title: str

    def __post_init__(self) -> None:
        normalized = self.title.strip()
        if not normalized:
            raise ValueError("title 不能为空")
        object.__setattr__(self, "title", normalized)
```

这不是给业务代码留下“以后也能改”的后门；它只是让构造过程能完成最终规范化。构造完成后仍应保持不可变约定。

## 四、数据类什么时候合适，什么时候不合适

`EnhanceModeInfo` 是数据类的典型场景：它主要表达一组稳定字段，行为很少，按值比较和清晰显示都有意义。

| 场景 | 是否适合 `@dataclass` | 说明 |
| ---- | --------------------- | ---- |
| 配置、命令、DTO、值对象 | 很适合 | 字段是主体，样板方法重复 |
| 领域实体 | 视情况而定 | 若身份与生命周期比字段值更重要，需慎选 `eq` |
| ORM 模型 | 视框架而定 | 初始化、描述符和延迟加载可能有框架约束 |
| 大量业务状态机 | 通常不优先 | 行为、约束和状态转换应显式建模 |
| 需要运行时校验/解析 | 不单独足够 | 需校验逻辑或专门模型库 |

数据类不是“所有类都更短”的开关。它生成的方法应与你的领域语义一致：例如两个数据库实体即使字段内容相同，也未必应被视为相等；此时应重新考虑 `eq`、标识字段和建模边界。

## 五、常见装饰器按职责分类

所有 `@...` 写法都遵循“接收对象、返回对象或描述符、再绑定名称”的基本模型，但不同装饰器解决的问题差异很大。下表按最常用职责分类。

| 装饰器 | 装饰目标 | 主要作用 | 典型边界 |
| ------ | -------- | -------- | -------- |
| `@dataclass` | 类 | 根据字段生成数据模型方法 | 不负责深度冻结和运行时类型校验 |
| `@property` | 方法 | 以属性形式暴露受控读取 | 不应隐藏昂贵 I/O |
| `@staticmethod` | 方法 | 声明不依赖实例/类状态的命名空间函数 | 不能访问 `self` 或 `cls` |
| `@classmethod` | 方法 | 绑定类，常用于替代构造器 | 不代表一定是工厂模式 |
| `@abstractmethod` | 方法/属性 | 声明 ABC 子类必须实现的契约 | 需和 `ABC`/兼容元类配合 |
| `@cached_property` | 实例方法 | 首次计算后缓存为实例属性 | 适合稳定且计算较贵的值 |
| `@lru_cache` | 函数 | 缓存可哈希参数的调用结果 | 不适合带副作用或无界高基数输入 |
| `@contextmanager` | 生成器函数 | 定义 `with` 资源进入/退出协议 | 不能替代清晰的资源所有权 |
| `@wraps` | 包装函数 | 保留被装饰函数的元数据 | 常用于自定义函数装饰器内部 |

### 1. `@property`：把方法变成受控属性

```python
class ImageSize:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    @property
    def pixels(self) -> int:
        return self.width * self.height
```

调用方使用 `size.pixels`，却仍由方法控制计算逻辑。适合派生值和校验后的访问；若一次读取会发网络请求、访问数据库或耗时很长，就不应伪装成普通属性。

### 2. `@classmethod` 和 `@staticmethod`：先问是否需要类/实例

```python
class ImageFormat:
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    @classmethod
    def from_filename(cls, filename: str) -> "ImageFormat":
        return cls(filename.rsplit(".", maxsplit=1)[-1].lower())

    @staticmethod
    def is_supported(suffix: str) -> bool:
        return suffix.lower() in {"png", "jpg", "webp"}
```

类方法收到 `cls`，因此子类调用时能构造相应子类；静态方法不自动收到 `self` 或 `cls`，只是把概念相关的纯函数放进类命名空间。若函数与类没有足够强的概念关系，放在模块级往往更简单。

### 3. `@abstractmethod`：让继承契约可执行

```python
from abc import ABC, abstractmethod


class Enhancer(ABC):
    @abstractmethod
    def enhance(self, image: bytes) -> bytes:
        """处理图像。"""
```

含未实现抽象方法的类不能直接实例化。它适合插件边界和稳定接口；不要为了让每个类“看起来规范”都堆一层抽象基类。

### 4. `@cached_property` 和 `@lru_cache`：缓存计算，不缓存真相

`@cached_property` 将第一次结果保存在实例上，适合配置加载后不会变化的派生值。`@lru_cache` 按函数参数缓存结果，适合纯函数或能明确失效的查询。两者都要求先想清楚缓存失效、内存增长和参数可哈希性；缓存不是性能护符，只是以空间换时间的状态管理。

### 5. 路由、测试和注册装饰器：多半在定义阶段登记信息

框架里的 `@router.get(...)`、测试框架的 `@pytest.mark...`、单分派函数的 `@singledispatch.register` 常不在每次调用时简单包一层函数。它们通常在模块导入、函数定义完成时把目标登记到路由表、测试元数据或分派表中。因此这类装饰器的导入时机和副作用要特别谨慎。具体的路由行为可参阅现有 FastAPI 文章；不要把所有带 `@` 的语法都想象成相同的闭包包装器。

## 六、多个装饰器的顺序

装饰器从离类或函数最近的一行开始应用：

```python
@outer
@inner
def task():
    pass


# 等价于：
task = outer(inner(task))
```

因此顺序是语义的一部分。以 `@property` 和 `@abstractmethod` 为例，通常写成：

```python
class Enhancer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...
```

先由 `@abstractmethod` 标记函数，再由 `@property` 把它包装成属性描述符；该描述符会保留抽象标记。遇到多个装饰器时，最稳妥的办法不是背口诀，而是把它展开成函数调用，检查每一步接收与返回的对象类型。

## 七、总结

- `@dataclass` 根据带注解的字段生成 `__init__`、`__repr__`、`__eq__` 等数据模型方法；它不自动做运行时类型检查。
- `frozen=True` 阻止字段重新绑定和删除，适合配置与值对象；它只提供浅层不可变，内部的列表、字典仍可能被修改。
- 冻结数据类通常可按字段哈希，但字段自身也必须可哈希；不要用 `unsafe_hash=True` 回避可变键问题。
- `field(default_factory=...)` 用于可变默认值，`__post_init__` 可完成构造期校验与规范化。
- 常见装饰器的职责各不相同：`property` 管访问，`classmethod`/`staticmethod` 管绑定方式，`abstractmethod` 管契约，缓存装饰器管结果复用，`contextmanager` 管资源生命周期。
- 看到 `@` 时，先问它装饰的是函数、方法还是类，以及它在定义阶段做登记、生成方法，还是在调用阶段包裹行为。这样比把所有装饰器当作同一种魔法要可靠得多。

对 `EnhanceModeInfo` 而言，`@dataclass(frozen=True)` 恰好表达了它的真实角色：它是一份初始化后稳定的模式说明，而不是负责加载模型、执行推理或维护可变流程的服务对象。让类的装饰器与类的职责相称，代码才不会因省下几行样板而欠下更多解释成本。
