+++
date = '2026-08-26T20:00:00+08:00'
draft = false
title = 'Python 类与方法：理解 self、cls、实例方法、类方法和静态方法'
+++

刚开始接触 Python 的类时，很多人会把 `self`、`cls`、`@classmethod` 和 `@staticmethod` 当成需要背诵的语法。这样的学习方式并不可靠：一旦遇到继承、工厂方法或属性查找，记住的几条口诀通常就不够用了。

更稳妥的理解是：**类是创建对象的模板；方法本质上仍是定义在类中的函数；通过对象或类访问方法时，Python 会根据访问方式自动绑定第一个参数。** `self` 和 `cls` 只是这两个“被自动绑定的对象”的惯例名称。

本文从一次普通的方法调用开始，逐步解释实例属性、类属性、实例方法、类方法、静态方法，以及它们在继承中的行为。看完后，至少不必再把“能运行”误认为“理解了”。

## 一、类、对象与属性

**类（class）** 用来描述一类对象共同的数据和行为；按照类创建出的具体对象叫作 **实例（instance）**。

例如，用 `Student` 描述学生：每个学生都有姓名和年龄，也都可以介绍自己。

```python
class Student:
    school = "No. 1 High School"  # 类属性

    def __init__(self, name: str, age: int) -> None:
        self.name = name  # 实例属性
        self.age = age

    def introduce(self) -> str:
        return f"我是 {self.name}，今年 {self.age} 岁。"


alice = Student("Alice", 18)
bob = Student("Bob", 17)

print(alice.introduce())
print(bob.school)
```

这里有三个层次：

- `Student` 是类对象，不是某个具体学生。
- `alice` 和 `bob` 是两个不同的实例。
- `name`、`age` 保存在各自实例上；`school` 定义在类上，默认由所有实例共享。

可以把它们粗略画成下面这样：

```text
Student（类）
├── school = "No. 1 High School"
├── __init__
└── introduce

alice（实例）                 bob（实例）
├── name = "Alice"            ├── name = "Bob"
└── age = 18                  └── age = 17
```

“共享”并不表示类属性被复制到每个实例里。实例访问 `school` 时，如果自身没有同名属性，Python 才会到类上查找它。

## 二、`self` 到底是什么

### 1. `self` 是当前实例的引用

在实例方法中，第一个参数通常命名为 `self`。它指向**调用该方法的那个实例**，因此方法可以读取或修改这个实例自己的状态。

```python
class Counter:
    def __init__(self, value: int = 0) -> None:
        self.value = value

    def increment(self, step: int = 1) -> None:
        self.value += step


counter = Counter()
counter.increment(2)
print(counter.value)  # 2
```

在 `increment` 内部，`self` 就是 `counter`。`self.value += step` 修改的是这个对象的 `value`，而不是某个神秘的全局变量。

`self` 并不是 Python 关键字。下面的代码语法上没有问题：

```python
class Example:
    def show(current_instance) -> None:
        print(current_instance)
```

但几乎所有 Python 代码都使用 `self`。坚持这个约定可以让读代码的人立刻知道第一个参数代表实例，没必要为了所谓“个性”制造阅读障碍。

### 2. `obj.method(x)` 等价于什么

关键点在这里。下面两种调用效果相同：

```python
counter.increment(2)
Counter.increment(counter, 2)
```

当你写：

```python
counter.increment(2)
```

Python 会先从 `counter`（再到它的类）找到 `increment`，然后把 `counter` 自动作为第一个实参传入。概念上相当于：

```python
Counter.increment(counter, 2)
```

因此，方法定义必须显式写出第一个形参：

```python
class Counter:
    def increment(self, step: int = 1) -> None:
        self.value += step
```

不是 Python “凭空认识 `self`”，而是调用表达式提供了第一个参数。若漏写 `self`，调用时就会收到参数数量错误：

```python
class BrokenCounter:
    def increment(step: int = 1) -> None:
        pass


item = BrokenCounter()
item.increment(2)  # TypeError：实际传入了 item 和 2 两个参数
```

### 3. `self` 用于访问同一个对象的状态与行为

实例方法里应当通过 `self` 访问实例属性，也应当优先通过 `self` 调用其他可被子类重写的方法。

```python
class Account:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def deposit(self, amount: int) -> None:
        self._validate_amount(amount)
        self.balance += amount

    def _validate_amount(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
```

这里的 `_validate_amount` 只是“内部使用”的命名约定，并不是真正的私有方法。使用 `self._validate_amount(...)` 的另一个好处是：子类可以按需重写验证规则，`deposit` 会自然调用重写后的版本。

## 三、构造实例：`__init__` 不是构造器本身

创建实例时常会写：

```python
user = User("Alice")
```

这会触发类的实例化过程。简化地说，Python 先创建对象，再调用 `__init__` 对对象进行初始化。

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name
```

`__init__` 接收已创建的实例 `self`，负责给它设置初始状态；它**必须返回 `None`**。所以更准确的说法是：`__init__` 是初始化方法，而不是负责创建对象的底层构造方法。对象的创建通常由 `__new__` 参与，普通业务类很少需要直接重写它。

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_active = True
```

不要把可变默认值直接写在参数中。它会在函数定义时只创建一次，随后被所有未传参的实例共享：

```python
class WrongTodoList:
    def __init__(self, items: list[str] = []) -> None:
        self.items = items
```

推荐使用 `None` 作为哨兵值：

```python
class TodoList:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = [] if items is None else list(items)
```

这里 `list(items)` 还会复制传入的列表，避免调用方之后修改原列表时，悄悄改变对象内部状态。边界清楚一点，后面的麻烦就会少一点。

## 四、实例属性与类属性

### 1. 实例属性：每个对象各自拥有

一般在 `__init__` 中通过 `self.属性名 = 值` 创建实例属性：

```python
class Dog:
    def __init__(self, name: str) -> None:
        self.name = name


first = Dog("Mochi")
second = Dog("Cocoa")

first.name = "Momo"
print(first.name)   # Momo
print(second.name)  # Cocoa
```

修改 `first.name` 只影响 `first`。对于普通实例属性，可以用 `vars(first)` 或 `first.__dict__` 观察它们：

```python
print(vars(first))  # {'name': 'Momo'}
```

并不是每一个类都一定有 `__dict__`；例如使用 `__slots__` 的类就是例外。不过在理解普通类时，这个观察方式很直观。

### 2. 类属性：定义在类体中，默认共享

类体顶层定义的属性属于类：

```python
class Connection:
    timeout = 10


first = Connection()
second = Connection()

print(first.timeout)   # 10
print(second.timeout)  # 10
print(Connection.timeout)  # 10
```

读取 `first.timeout` 时，Python 大致按下面顺序查找：

```text
first 的实例属性
 -> Connection 的类属性
   -> 父类的类属性（按 MRO 顺序）
```

其中 MRO（Method Resolution Order）是方法解析顺序，决定继承体系中属性的查找路径。现在不必急着背完整规则，只要先知道：实例没有找到时才会继续到类和父类查找。

### 3. 通过实例给类属性赋值，会发生遮蔽

读取和赋值不是同一回事。下面的代码很容易造成误解：

```python
class Connection:
    timeout = 10


first = Connection()
second = Connection()

first.timeout = 30

print(first.timeout)       # 30
print(second.timeout)      # 10
print(Connection.timeout)  # 10
print(vars(first))         # {'timeout': 30}
```

`first.timeout = 30` 创建了 `first` 自己的实例属性，它遮蔽了读取时本应找到的 `Connection.timeout`，并没有修改类属性。

若要修改所有尚未被实例属性遮蔽的对象所看到的默认值，应通过类赋值：

```python
Connection.timeout = 20
print(second.timeout)  # 20
```

类属性很适合放常量、默认配置、统计计数器等“确实属于整个类”的数据；不适合放每个实例各自会变动的状态。

### 4. 可变类属性是一个常见陷阱

下面的 `members` 只有一份：

```python
class WrongTeam:
    members: list[str] = []


first = WrongTeam()
second = WrongTeam()
first.members.append("Alice")

print(second.members)  # ['Alice']
```

如果你本来希望每个实例拥有独立列表，应该把它放入 `__init__`：

```python
class Team:
    def __init__(self) -> None:
        self.members: list[str] = []
```

反过来，如果业务上真的需要一份由所有实例共享的注册表，可变类属性完全可以使用，只是应当明确通过类来操作它，别让读者猜测它的归属。

## 五、实例方法：处理单个对象的行为

**实例方法（instance method）** 是最常见的方法类型。它的第一个参数是实例，按惯例写作 `self`；它通过实例调用，也可以读取实例和类上的内容。

```python
class Temperature:
    def __init__(self, celsius: float) -> None:
        self.celsius = celsius

    def to_fahrenheit(self) -> float:
        return self.celsius * 9 / 5 + 32


temperature = Temperature(25)
print(temperature.to_fahrenheit())  # 77.0
```

此时：

```python
temperature.to_fahrenheit()
```

概念上等价于：

```python
Temperature.to_fahrenheit(temperature)
```

实例方法适用于以下情况：

- 逻辑依赖某个对象的实例属性。
- 逻辑需要更新某个对象的状态。
- 逻辑需要利用多态，让子类覆盖某项行为。

例如，购物车的 `add_item`、账户的 `withdraw`、文件对象的 `read` 都天然属于实例方法：它们必须知道“操作的是哪个对象”。

## 六、类方法：`cls` 指向调用它的类

### 1. `@classmethod` 改变了第一个参数的绑定对象

在方法前加上 `@classmethod`，第一个参数将不再是实例，而是类对象。这个参数按惯例命名为 `cls`。

```python
class User:
    default_role = "member"

    @classmethod
    def describe_default_role(cls) -> str:
        return f"默认角色是：{cls.default_role}"


print(User.describe_default_role())
```

上面的调用概念上等价于：

```python
User.describe_default_role.__func__(User)
```

`__func__` 是绑定方法背后保存的原始函数。它适合帮助理解绑定机制，生产代码通常不需要这样调用。

类方法既可通过类调用，也可通过实例调用：

```python
user = User()

print(User.describe_default_role())
print(user.describe_default_role())
```

两次调用传入的 `cls` 都是 `User`，不是 `user`。不过既然方法表达的是“类级别的行为”，推荐直接使用 `User.describe_default_role()`，意图更清晰。

### 2. `cls` 不是类名的固定替代品

以下两段代码在最简单的情况下看起来相似：

```python
class Account:
    @classmethod
    def create(cls, name: str):
        return cls(name)
```

```python
class Account:
    @classmethod
    def create(cls, name: str):
        return Account(name)
```

区别会在继承中出现。`cls` 代表**实际调用方法的类**，而 `Account` 永远指向写死的基类。

```python
class Account:
    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def guest(cls):
        return cls("guest")


class AdminAccount(Account):
    pass


admin = AdminAccount.guest()
print(type(admin).__name__)  # AdminAccount
```

若 `guest` 里返回的是 `Account("guest")`，`AdminAccount.guest()` 反而会创建基类对象，扩展性会被悄悄损失。也不是什么戏剧性的错误，只是以后会让人不太愉快。

### 3. 类方法最常见的用途：替代构造器

类方法经常用作**替代构造器（alternative constructor）**：以不同来源的数据创建对象。

```python
from datetime import date


class Event:
    def __init__(self, name: str, event_date: date) -> None:
        self.name = name
        self.event_date = event_date

    @classmethod
    def from_iso_date(cls, name: str, value: str) -> "Event":
        return cls(name, date.fromisoformat(value))


conference = Event.from_iso_date("Python Conference", "2026-10-01")
print(conference.event_date)  # 2026-10-01
```

常见场景包括：

- `from_dict()`：从字典创建对象。
- `from_json()`：从 JSON 文本创建对象。
- `from_env()`：从环境变量读取配置。
- `from_timestamp()`：从时间戳创建时间对象。

类方法也适合维护类级别的统计或配置：

```python
class Order:
    created_count = 0

    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        type(self).created_count += 1

    @classmethod
    def total_created(cls) -> int:
        return cls.created_count
```

这里 `type(self)` 和 `cls` 都有利于让子类拥有正确的行为。是否要让计数器在父子类之间共享，则是业务设计问题，不是装饰器替你决定的事情。

## 七、静态方法：放在类命名空间中的普通函数

在方法前加 `@staticmethod` 后，Python 不会自动传入实例或类。因此静态方法没有 `self`，也没有 `cls`。

```python
class Password:
    @staticmethod
    def is_valid(value: str) -> bool:
        return len(value) >= 8 and any(char.isdigit() for char in value)


print(Password.is_valid("abc12345"))  # True
```

从调用参数的角度看，这近似于一个放进类命名空间的普通函数：

```python
class Password:
    def is_valid(value: str) -> bool:
        return len(value) >= 8 and any(char.isdigit() for char in value)


Password.is_valid("abc12345")
```

但实际代码中应使用 `@staticmethod` 明确表达“这个方法不依赖自动绑定的实例或类”。它可以通过类或实例访问：

```python
password = Password()

print(Password.is_valid("abc12345"))
print(password.is_valid("abc12345"))
```

通常仍建议通过类调用，因为它不需要实例状态。

### 1. 不要为了“归类”滥用静态方法

如果函数只是在概念上与类有关、但既不访问实例也不访问类，`@staticmethod` 可以作为一种组织方式。不过，如果它独立到完全不依赖该类，放在模块级函数中往往更简单，也更容易测试和复用。

```python
def normalize_email(value: str) -> str:
    return value.strip().lower()
```

不必因为系统里存在 `User` 类，就把所有和用户沾边的小函数都塞进 `User`。类不是抽屉，什么都往里面放只会变得难找。

## 八、三种方法的对比

| 类型 | 装饰器 | 第一个自动传入的对象 | 适合处理什么 | 推荐调用方式 |
| ---- | ------ | -------------------- | ------------ | ------------ |
| 实例方法 | 无 | 实例 `self` | 单个对象的状态和行为 | `obj.method()` |
| 类方法 | `@classmethod` | 类 `cls` | 类级配置、替代构造器、继承友好的工厂 | `Class.method()` |
| 静态方法 | `@staticmethod` | 不自动传入 | 与类相关但不依赖对象状态的工具逻辑 | `Class.method()` |

可以用同一个类直观看到差异：

```python
class MethodDemo:
    label = "demo"

    def instance_method(self) -> tuple[object, str]:
        return self, self.label

    @classmethod
    def class_method(cls) -> tuple[type["MethodDemo"], str]:
        return cls, cls.label

    @staticmethod
    def static_method(value: int) -> int:
        return value * 2


demo = MethodDemo()

print(demo.instance_method())     # (demo 实例, 'demo')
print(MethodDemo.class_method())  # (MethodDemo 类, 'demo')
print(MethodDemo.static_method(3))  # 6
```

选择时可以连续问自己三个问题：

1. 逻辑是否需要读取或修改某个实例？需要则使用实例方法。
2. 逻辑是否需要知道“当前是哪一个类”，尤其要支持继承？需要则使用类方法。
3. 逻辑是否两者都不需要？再考虑静态方法，或者更干脆地使用模块级函数。

## 九、方法为什么能自动绑定：描述符的简化理解

普通函数定义在类体中时，会成为类属性。通过类访问它与通过实例访问它，得到的东西不完全相同：

```python
class Greeting:
    def say(self, name: str) -> str:
        return f"Hello, {name}!"


greeting = Greeting()

print(Greeting.say)   # 函数对象
print(greeting.say)   # 绑定到 greeting 的方法对象
```

因此下面的调用才会成立：

```python
Greeting.say(greeting, "Alice")
greeting.say("Alice")
```

第二种写法中，`greeting.say` 是一个已经绑定 `greeting` 的方法。函数能够在“作为类属性被实例访问”时形成绑定方法，是 Python **描述符（descriptor）** 协议的一部分。

不需要为了写日常业务代码手写描述符，但理解这一点可以解释许多表面上奇怪的现象：

- 实例方法调用时为何不必手动传 `self`。
- 类方法调用时为何收到的是 `cls`。
- `property` 为什么看起来像属性，访问时却会执行代码。

`@classmethod` 和 `@staticmethod` 本质上也是不同的描述符包装器：前者绑定类，后者不做实例/类绑定。

## 十、`property`：用属性形式保护状态

并非所有属性都适合任意修改。`property` 可以把一个方法包装成像属性一样访问的接口，在读取或赋值时执行校验逻辑。

```python
class Product:
    def __init__(self, price: float) -> None:
        self.price = price

    @property
    def price(self) -> float:
        return self._price

    @price.setter
    def price(self, value: float) -> None:
        if value < 0:
            raise ValueError("price cannot be negative")
        self._price = value


product = Product(99.0)
product.price = 120.0
print(product.price)  # 120.0
```

注意调用时没有括号：`product.price` 看起来是属性访问，却会调用 `price()` 的 getter；赋值 `product.price = 120.0` 会调用 setter。这使得调用方可以使用稳定的属性接口，而类内部仍有机会验证或调整存储方式。

约定上，实际存储字段使用 `_price` 这样的单下划线名称，避免在 setter 中再次写 `self.price = value` 造成无限递归。

单下划线仍只是约定，表达“内部实现，外部请谨慎使用”。双下划线开头的名称会触发名称改写，例如 `__token` 会变成 `_Product__token`；它主要用于避免子类意外重名，不等于真正的访问控制。

## 十一、继承中 `self` 与 `cls` 的价值

继承让子类复用或修改父类行为：

```python
class Animal:
    def speak(self) -> str:
        return "..."


class Dog(Animal):
    def speak(self) -> str:
        return "Woof"


animals: list[Animal] = [Animal(), Dog()]
for animal in animals:
    print(animal.speak())
```

循环只调用 `animal.speak()`，Python 会根据实际对象类型选择对应实现。这就是多态。实例方法通过 `self` 表示实际对象，类方法通过 `cls` 表示实际调用的类，所以两者都能自然支持这种扩展。

子类若需要在保留父类初始化逻辑的基础上增加状态，应调用 `super()`：

```python
class Employee:
    def __init__(self, name: str) -> None:
        self.name = name


class Manager(Employee):
    def __init__(self, name: str, team_size: int) -> None:
        super().__init__(name)
        self.team_size = team_size
```

`super()` 不只是“调用父类”的简写；它会按照 MRO 找到下一个合适的实现，因此在多重继承的协作式初始化中尤其重要。普通单继承场景先掌握 `super().__init__(...)` 已经足够，别急着把所有问题都变成多重继承问题。

## 十二、常见错误与修正

### 1. 定义实例方法时漏写 `self`

错误：

```python
class User:
    def greet():
        print("Hello")
```

这段代码的问题是 `greet` 缺少 `self`。正确写法：

```python
class User:
    def greet(self) -> None:
        print("Hello")
```

如果方法不需要实例，也应明确说明它是静态方法：

```python
class User:
    @staticmethod
    def greet() -> None:
        print("Hello")
```

### 2. 在实例方法中直接使用实例属性名

错误：

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return f"Hello, {name}"
```

`name` 不是局部变量，也不是全局变量；它在这个实例上。正确写法是 `self.name`：

```python
def greet(self) -> str:
    return f"Hello, {self.name}"
```

### 3. 把类属性误当成每个实例独有的列表

错误：

```python
class Cart:
    items: list[str] = []
```

除非所有购物车真的应该共用一个列表，否则应改为：

```python
class Cart:
    def __init__(self) -> None:
        self.items: list[str] = []
```

### 4. 在类方法里写死基类名

不够灵活：

```python
class User:
    @classmethod
    def anonymous(cls):
        return User("anonymous")
```

更适合继承：

```python
class User:
    @classmethod
    def anonymous(cls):
        return cls("anonymous")
```

### 5. 用静态方法保存本应属于实例的状态

下面的代码无法访问具体账户的余额：

```python
class Account:
    @staticmethod
    def withdraw(amount: int) -> None:
        # 不知道该从哪个账户扣款
        pass
```

扣款明显依赖某个账户对象，应使用实例方法：

```python
class Account:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def withdraw(self, amount: int) -> None:
        if amount > self.balance:
            raise ValueError("insufficient balance")
        self.balance -= amount
```

## 十三、总结

Python 的类并不要求你立刻掌握所有面向对象术语，但下面几条必须分清：

- `self` 是实例方法接收的当前实例；`obj.method(x)` 概念上相当于 `Class.method(obj, x)`。
- `cls` 是类方法接收的当前类；使用 `cls(...)` 创建对象可以保留对子类的支持。
- 实例属性属于某个对象，适合保存对象自己的状态；类属性属于类，适合共享默认值、常量和类级别状态。
- 实例方法处理对象状态；类方法处理类级行为和替代构造；静态方法不接收自动绑定对象，只适合独立的辅助逻辑。
- `@property` 可以在不改变属性访问形式的前提下加入校验和封装。
- 遇到方法类型选择困难时，先问它依赖的是实例、类，还是两者都不依赖。答案通常已经足够明确了。

真正值得记住的不是某个装饰器的拼写，而是绑定关系：**通过实例访问普通方法会绑定实例；类方法绑定类；静态方法不绑定任何对象。** 其余差异，几乎都能从这里推导出来。
