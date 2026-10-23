+++
date = '2026-10-20T15:50:00+08:00'
draft = false
title = 'Python Protocol 如何工作：结构化子类型、鸭子类型与可替换接口'
+++

下面这段代码定义的不是一个具体的图像修复引擎，而是一个**类型协议**（protocol）：

```python
from typing import Protocol

import numpy as np


class InpaintEngine(Protocol):
    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
```

它表达的契约是：**任何对象只要能以兼容的签名提供 `inpaint(image_bgr, mask)`，并返回 `np.ndarray`，就可以在静态类型检查中被当作 `InpaintEngine` 使用**。实现类不必显式写 `class SomeEngine(InpaintEngine)`。

这是 Python 类型提示中的**结构化子类型**（structural subtyping）：看对象“具有什么形状和能力”，而不是只看它是否声明继承了某个名字。它将 Python 传统的鸭子类型——“像鸭子一样走和叫，就把它当作鸭子”——以可检查、可导航的接口形式写进类型系统。

## 一、逐行解释这段声明

```python
class InpaintEngine(Protocol):
    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
```

每个部分的职责不同：

| 部分 | 含义 |
| ---- | ---- |
| `Protocol` | 来自 `typing` 的协议基类，声明结构化接口 |
| `InpaintEngine` | 协议名称，供参数、返回值和变量注解使用 |
| `inpaint(...)` | 调用方依赖的实例方法名称与调用形式 |
| `image_bgr: np.ndarray` | 第一个输入应是 NumPy 数组，语义上为 BGR 图像 |
| `mask: np.ndarray` | 第二个输入应是 NumPy 数组，语义上为修复遮罩 |
| `-> np.ndarray` | 方法应返回 NumPy 数组 |
| `...` | `Ellipsis` 占位方法体，表示此处只声明契约，不提供实现 |

这里的类型注解主要服务于 Pyright、mypy、IDE 和其他静态分析工具。Python 解释器默认不会在调用 `inpaint` 时检查数组类型、维度、颜色通道或 `mask` 是否二值；这些仍应由边界校验、测试和实际实现保证。

`...` 在这个位置是简洁的声明体写法。它不是“这个方法会自动由 Python 实现”，也不是把图像修复延后执行的特殊语法。协议类本身只描述能力，不能拿来当作可工作的引擎实例。

## 二、无需显式继承，也能满足协议

假设项目已有一个具体实现：

```python
class LamaEngine:
    def inpaint(
        self,
        image_bgr: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        # 这里省略模型推理、预处理和后处理。
        return image_bgr
```

它没有继承 `InpaintEngine`，仍可传给依赖协议的函数：

```python
def run_inpaint(
    engine: InpaintEngine,
    image_bgr: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    return engine.inpaint(image_bgr, mask)


result = run_inpaint(LamaEngine(), image_bgr, mask)
```

静态检查器会查看 `LamaEngine` 的公开成员。只要 `inpaint` 的参数和返回类型与协议兼容，就接受这次传入；若方法名拼错、漏掉 `mask`、返回不兼容的类型，检查器会在运行前指出问题。

```text
调用方依赖 InpaintEngine 协议
        │
        ├── LamaEngine.inpaint(...)       满足结构，允许传入
        ├── OpenCvTeleaEngine.inpaint(...) 满足结构，允许传入
        └── FakeEngine.inpaint(...)       测试替身也满足结构，允许传入
```

这使高层代码依赖“能修复图像”这一能力，而非依赖某个特定模型类、权重加载方式或 GPU 实现。替换实现时，不必让每一个候选引擎进入同一条继承树。

## 三、这与普通鸭子类型有什么不同

没有 `Protocol` 时，Python 本来就允许直接调用：

```python
def run_inpaint(engine, image_bgr, mask):
    return engine.inpaint(image_bgr, mask)
```

若传入对象没有 `inpaint`，运行到这一行才会得到 `AttributeError`。这就是动态鸭子类型：代码按行为调用，错误在运行时暴露。

使用协议后，运行时调用方式没有改变；改变的是**静态工具能够提前理解并检查依赖**：

```python
def run_inpaint(
    engine: InpaintEngine,
    image_bgr: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    return engine.inpaint(image_bgr, mask)
```

IDE 可以补全 `engine.inpaint`，重构工具可追踪实现，类型检查器可验证调用者传入的对象。它不是强迫 Python 变成 Java，而是在保留鸭子类型灵活性的同时，给大型项目一份可机器检查的协作契约。

## 四、协议匹配检查什么

类型检查器关心的不只是“碰巧有一个同名方法”，还会检查类型兼容性。以 `InpaintEngine` 为例，实现至少应满足：

- 方法名为 `inpaint`；
- 调用方能传入两个位置参数 `image_bgr`、`mask`；
- 实现不能要求协议未要求的额外必填参数；
- 返回值必须能当作 `np.ndarray` 使用；
- 实例方法、类方法、属性与可调用对象等成员种类也应匹配协议声明。

参数遵循“实现应接受得更宽，返回应给得更窄”的替换原则。若协议允许调用方传任意 `np.ndarray`，实现却只接受一个更特殊、调用方无法证明的类型，就可能无法替换协议。返回值反过来：协议承诺 `np.ndarray`，实现返回其更具体的兼容类型通常没有问题。

类型注解并不能完整表达图像领域约束。例如 `np.ndarray` 没说明 `image_bgr` 必须是 `H×W×3` 的 `uint8`，也没说明 `mask` 与图像具有相同的宽高。可以使用 `numpy.typing.NDArray` 增加 dtype 信息、在文档中写明形状，最重要的仍是在服务/API 边界做运行时校验：

```python
def validate_inputs(image_bgr: np.ndarray, mask: np.ndarray) -> None:
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("image_bgr 必须是 H×W×3 的 BGR 图像")
    if mask.shape[:2] != image_bgr.shape[:2]:
        raise ValueError("mask 的宽高必须与图像一致")
```

类型系统减少接口错配，不会替图像处理程序猜出数据语义。

## 五、`Protocol`、ABC 与显式继承的区别

`Protocol` 经常被称为“Python 的接口”，但它与抽象基类（ABC）解决的问题并不相同。

| 对比项 | `Protocol` | `ABC` + `@abstractmethod` |
| ------ | ---------- | ------------------------- |
| 子类型关系 | 结构化：成员兼容即可 | 名义式：通常要求显式继承/注册 |
| 是否可复用默认实现 | 可以，但通常不作为主要用途 | 很适合共享默认方法和状态 |
| 主要检查时机 | 静态类型检查 | 运行时实例化时也可强制抽象方法 |
| 适合的边界 | 调用方只依赖少量能力 | 框架控制子类层级与生命周期 |
| 对第三方/旧类的适配 | 无需修改原类 | 往往需要继承、注册或适配器 |

若项目要规定所有引擎都有加载、关闭、状态管理和共享默认逻辑，ABC 可能更合适：

```python
from abc import ABC, abstractmethod


class BaseInpaintEngine(ABC):
    @abstractmethod
    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """执行图像修复。"""

    def close(self) -> None:
        """默认无需释放资源的实现。"""
```

若高层函数只需要一个 `inpaint` 方法，而具体实现来自不同库、不同团队或测试代码，协议通常更松耦合。两者也可以同时存在：基础框架的正式引擎继承 ABC，调用方参数仍标为一个更小的 `Protocol`，从而不把不必要的生命周期能力暴露为依赖。

## 六、显式继承 `Protocol` 有何意义

实现类**可以**显式写成：

```python
class TorchInpaintEngine(InpaintEngine):
    def inpaint(
        self,
        image_bgr: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        return image_bgr
```

这样做对读者有提示作用，也能让类型检查器检查该类是否完成了协议。但它不是结构化匹配所必需的条件。不要为了“让它看起来像接口实现”把所有第三方类都强行改成继承协议；那会失去 `Protocol` 最实际的优点。

协议也可继承其他协议，以组合更大的能力：

```python
class Closable(Protocol):
    def close(self) -> None: ...


class ManagedInpaintEngine(InpaintEngine, Closable, Protocol):
    pass
```

这里只有真正需要同时依赖 `inpaint` 和 `close` 的调用方才应标注 `ManagedInpaintEngine`。小接口比一个包罗万象的“万能引擎协议”更容易替换和测试。

## 七、`@runtime_checkable` 不是运行时签名验证

默认情况下，不能安全地对协议直接做 `isinstance` 检查：

```python
isinstance(engine, InpaintEngine)  # 默认不支持这种运行时检查
```

若确实要做一个浅层运行时成员检查，可标记协议：

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class InpaintEngine(Protocol):
    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
```

此时 `isinstance(engine, InpaintEngine)` 可以检查对象是否具有所需成员。但它**不会**可靠验证参数类型、返回类型、数组形状，也不会实际调用方法确认行为正确。一个签名错误、总是抛异常或返回错误图像的对象，仍可能通过这种成员存在性检查。

因此，`@runtime_checkable` 适合非常有限的能力探测，不适合替代配置解析、工厂注册、输入校验或集成测试。真正的引擎选择应在构造边界明确完成，并通过测试验证结果质量和资源生命周期。

## 八、协议如何改善测试与依赖注入

高层逻辑只依赖协议后，测试无需加载数 GB 的模型权重：

```python
class FakeInpaintEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[np.ndarray, np.ndarray]] = []

    def inpaint(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        self.calls.append((image_bgr, mask))
        return image_bgr.copy()


def test_service_uses_engine() -> None:
    engine = FakeInpaintEngine()
    result = run_inpaint(engine, image_bgr, mask)

    assert result.shape == image_bgr.shape
    assert len(engine.calls) == 1
```

`FakeInpaintEngine` 不需要继承生产类、伪造 GPU 状态或实现无关的生命周期方法；它只实现服务实际依赖的契约。这正是依赖倒置在 Python 中一种朴素而有效的落地方式：高层策略依赖抽象能力，具体模型适配器在应用装配处被注入。

如果一个依赖只有单个简单函数，也可以用 `Callable`：

```python
from collections.abc import Callable

InpaintFunction = Callable[[np.ndarray, np.ndarray], np.ndarray]
```

当依赖需要带名称的方法、额外属性、多个相关方法，或希望未来扩展 `warmup`、`close` 等能力时，`Protocol` 的可读性通常更好。

## 九、常见误解与选择建议

| 误解 | 更准确的理解 |
| ---- | ------------ |
| `Protocol` 会在运行时自动校验参数 | 默认不会；它主要服务静态检查 |
| 实现类必须继承协议 | 不必，成员结构兼容即可 |
| 有同名方法就一定类型兼容 | 参数、返回值和成员种类仍要兼容 |
| `@runtime_checkable` 会检查完整签名 | 它只做浅层成员存在性检查 |
| `Protocol` 应替代所有 ABC | 协议与 ABC 分别服务松耦合结构匹配和受控继承框架 |
| 类型注解会验证图像 shape/dtype | 通常不会，需要领域校验和测试 |

选择时可以遵循这条简单规则：调用方只关心“对象能做什么”、实现来源多样且不应被强制纳入同一继承树时，用小而明确的 `Protocol`；需要共享实现、运行时管理子类或严格的框架生命周期时，用 ABC 或具体基类；只依赖一个函数时，先考虑 `Callable`。

## 十、总结

- `class InpaintEngine(Protocol)` 是 Python 类型提示的协议声明，体现了结构化子类型与可检查的鸭子类型。
- `inpaint(...) -> np.ndarray` 规定调用方所依赖的方法形状；`...` 只表示声明占位，不提供图像修复实现。
- 具体类无需显式继承协议，只要方法签名兼容，就能被静态类型检查器当作 `InpaintEngine` 使用。
- `Protocol` 不会自动进行运行时类型、数组形状或业务语义验证；`@runtime_checkable` 也只能做浅层成员检查。
- 它特别适合模型适配器、插件和测试替身，使高层服务依赖能力而不是依赖某个特定实现。
- 与 ABC、`Callable` 和具体类相比，关键不在于谁更“高级”，而在于调用方实际需要的是结构契约、受控继承，还是一个简单可调用对象。

所以，这段声明不是在实现一个修复引擎，而是在把“可用于图像修复的对象最低应具备什么能力”写成可检查的契约。让服务依赖这个契约，而把 LaMa、OpenCV 或未来的其他实现留在装配边界，结构才不会因为换一个模型而跟着四处变形。
