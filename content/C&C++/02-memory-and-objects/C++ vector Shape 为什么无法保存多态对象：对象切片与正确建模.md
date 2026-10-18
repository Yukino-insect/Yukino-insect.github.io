+++
date = '2026-08-26T21:00:00+08:00'
draft = false
title = 'C++ vector Shape 为什么无法保存多态对象：对象切片与正确建模'
+++

下面这段代码看起来很合理：有基类 `Shape`，有重写了虚函数的派生类 `Circle`，然后把圆形放进“形状列表”。但运行结果却不是预期的圆形绘制信息。

```cpp
#include <iostream>
#include <vector>

class Shape {
public:
    virtual ~Shape() = default;

    virtual void draw() const {
        std::cout << "Draw a generic shape\n";
    }
};

class Circle : public Shape {
    double radius = 5.0;

public:
    void draw() const override {
        std::cout << "Draw a circle with radius " << radius << "\n";
    }
};

int main() {
    std::vector<Shape> shapes;
    Circle c;

    shapes.push_back(c);
    shapes[0].draw();
}
```

输出是：

```text
Draw a generic shape
```

原因不是虚函数失效，也不是 `override` 写错，更不是 `std::vector` 不支持多态。真正发生的是 **对象切片（object slicing）**：`Circle` 被按值复制为一个独立的 `Shape` 对象，派生类新增的那一部分状态和类型信息都没有进入容器。

所以更准确的结论是：**`std::vector<Shape>` 可以保存 `Shape` 对象，但不能按值保存不同派生类对象并保留其运行时多态。** 这两个说法只差几个字，含义却并不相同。下面把这件事讲清楚。

## 一、先看问题发生在哪一步

代码的关键行是：

```cpp
shapes.push_back(c);
```

`shapes` 的元素类型是 `Shape`：

```cpp
std::vector<Shape> shapes;
```

因此 `push_back` 需要在容器内部构造一个 **`Shape` 类型的新元素**。可以把这次调用近似理解为：

```cpp
Shape copied = c;
shapes.push_back(copied);
```

这里发生的是从 `Circle` 到 `Shape` 的按值转换。C++ 会调用 `Shape` 的拷贝构造函数，只复制 `c` 中属于 `Shape` 基类子对象的部分。

原始对象和存入容器后的对象可以粗略表示为：

```text
c：Circle 对象
┌──────────────────────────────┐
│ Shape 基类子对象             │
│  - 虚函数分派所需的实现信息  │
├──────────────────────────────┤
│ Circle 自己的成员            │
│  - radius = 5.0              │
└──────────────────────────────┘

shapes[0]：Shape 对象
┌──────────────────────────────┐
│ Shape 基类对象               │
│  - 没有 Circle::radius       │
└──────────────────────────────┘
```

`shapes[0]` 已经不是 `Circle`，而是一个完整、独立的 `Shape` 对象。对它调用虚函数时，动态类型就是 `Shape`，所以输出基类版本完全符合规则。

## 二、什么是对象切片

### 1. 派生对象按值转换为基类对象时发生切片

对象切片的典型形式是：

```cpp
Circle circle;
Shape shape = circle;

shape.draw();  // Draw a generic shape
```

`shape` 的静态类型和实际对象类型都是 `Shape`。尽管它由 `circle` 初始化，`shape` 也不会“记得自己原本来自圆形”。这是一次创建新对象的按值复制，不是给原对象起了一个基类别名。

与之对比，引用和指针不会复制对象：

```cpp
Circle circle;

Shape& shape_ref = circle;
Shape* shape_ptr = &circle;

shape_ref.draw();   // Draw a circle with radius 5
shape_ptr->draw();  // Draw a circle with radius 5
```

`shape_ref` 和 `shape_ptr` 的**静态类型**是 `Shape` 的引用或指针，但它们指向的实际对象仍是 `Circle`。因此虚函数调用能根据对象的**动态类型**分派到 `Circle::draw()`。

### 2. “切片”切掉的是什么

从概念上说，被切掉的是派生类相对于基类额外拥有的那一部分：

- 派生类新增的数据成员，例如 `Circle::radius`。
- 派生类新增的成员函数所依赖的状态。
- “这个对象是 `Circle`”这一动态类型事实。

严格地说，C++ 标准并不要求对象必须以某种固定内存布局实现；不要把上面的示意图当作 ABI 保证。但“目标对象只有 `Shape` 类型可容纳的状态”这一语义是确定的。

`Circle::draw()` 需要读取 `radius`，而切片后的 `Shape` 对象根本没有 `radius` 成员。让它还去调用 `Circle::draw()` 才是不合理的：函数需要的数据已经不在那个对象里了。

### 3. 容器并不是罪魁祸首

下面所有写法都会产生同一种问题：

```cpp
void draw_by_value(Shape shape) {
    shape.draw();
}

Shape make_shape() {
    Circle circle;
    return circle;
}

int main() {
    Circle circle;

    Shape assigned;
    assigned = circle;

    draw_by_value(circle);
    Shape returned = make_shape();
}
```

它们分别对应：

- 把派生对象按值传给基类形参；
- 从函数按 `Shape` 值返回派生对象；
- 将派生对象赋值给一个已存在的基类对象。

共同点不是“使用了 `vector`”，而是目标位置的类型是 `Shape`，并且发生了按值复制或按值移动。`std::vector<Shape>` 只是最常见、也最容易让人误以为是容器问题的一种场景。

## 三、虚函数为什么没有挽救这段代码

虚函数负责的是**对一个仍然存在的多态对象进行动态分派**。它不会阻止 C++ 在需要 `Shape` 值的地方创建一个 `Shape` 对象。

在原始代码中，可以把时间线理解为：

```text
1. 创建 Circle c
2. 把 c 的 Shape 基类部分复制到 vector 的一个新 Shape 元素中
3. vector 中只剩一个 Shape 对象
4. 对这个 Shape 对象调用 draw()
5. 动态分派到 Shape::draw()
```

关键不是“虚函数失去了作用”，而是在第 2 步后，供虚函数分派的实际对象已经变成 `Shape` 了。

### 1. 静态类型与动态类型

理解多态时，最好区分两个概念：

- **静态类型**：编译器从声明看到的类型，例如 `Shape&`、`Shape*`。
- **动态类型**：运行时对象实际的类型，例如一个 `Shape&` 绑定的对象可能是 `Circle`。

看下面的对照：

```cpp
Circle circle;

Shape& reference = circle;
Shape* pointer = &circle;
Shape value = circle;
```

| 变量 | 静态类型 | 所代表对象的动态类型 | `draw()` 结果 |
| ---- | -------- | -------------------- | ------------- |
| `reference` | `Shape&` | `Circle` | `Circle::draw()` |
| `pointer` | `Shape*` | `Circle` | `Circle::draw()` |
| `value` | `Shape` | `Shape` | `Shape::draw()` |

虚函数需要“静态类型是多态基类的引用或指针，同时实际对象仍是派生对象”这一条件。按值的 `Shape value` 不满足后一半条件。

### 2. 虚析构函数解决的是另一件事

原始代码中有：

```cpp
virtual ~Shape() = default;
```

这是正确且重要的设计，但它不能避免对象切片。虚析构函数解决的是经由基类指针删除派生对象时，能正确调用完整析构链的问题：

```cpp
Shape* shape = new Circle();
delete shape;  // 因为 ~Shape 是 virtual，会先析构 Circle，再析构 Shape
```

在现代 C++ 中，更推荐由智能指针管理这个对象：

```cpp
std::unique_ptr<Shape> shape = std::make_unique<Circle>();
```

可以这样记忆两者的边界：

- `virtual void draw()`：决定通过基类接口调用时，执行哪个派生类实现。
- `virtual ~Shape()`：决定通过基类指针销毁对象时，执行哪些析构函数。
- 两者都不会让 `Shape` 值自动变成能容纳 `Circle` 完整状态的对象。

## 四、正确方案一：`std::vector<std::unique_ptr<Shape>>`

如果容器需要拥有不同派生类对象，并且每个对象只有一个所有者，最常用的选择是：

```cpp
#include <iostream>
#include <memory>
#include <vector>

class Shape {
public:
    virtual ~Shape() = default;

    virtual void draw() const {
        std::cout << "Draw a generic shape\n";
    }
};

class Circle : public Shape {
    double radius = 5.0;

public:
    void draw() const override {
        std::cout << "Draw a circle with radius " << radius << "\n";
    }
};

class Rectangle : public Shape {
    double width = 4.0;
    double height = 3.0;

public:
    void draw() const override {
        std::cout << "Draw a rectangle " << width << " x " << height << "\n";
    }
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;

    shapes.push_back(std::make_unique<Circle>());
    shapes.push_back(std::make_unique<Rectangle>());

    for (const auto& shape : shapes) {
        shape->draw();
    }
}
```

输出：

```text
Draw a circle with radius 5
Draw a rectangle 4 x 3
```

现在 `vector` 里按值保存的是 `std::unique_ptr<Shape>`，而不是 `Shape`。每个智能指针指向一个独立分配的完整派生对象，所以 `Circle` 的 `radius`、`Rectangle` 的 `width` 和 `height` 都仍然存在。

### 1. 为什么 `unique_ptr` 很适合这里

`std::unique_ptr<T>` 表达**独占所有权**：一个对象在同一时间只有一个所有者。容器销毁时，其中的智能指针会自动销毁，进而通过虚析构函数正确销毁它们管理的派生对象。

它还有几个实际优点：

- 不需要手写 `delete`，异常安全。
- `vector` 扩容时只移动智能指针，不复制庞大的派生对象。
- 所有权关系在类型中可见，不必猜测谁负责释放内存。

要注意，`unique_ptr` 不可复制，只可移动。因此以下写法不成立：

```cpp
std::unique_ptr<Shape> first = std::make_unique<Circle>();
std::unique_ptr<Shape> second = first;  // 错误：unique_ptr 不可复制
```

这是设计使然：若两个对象都以为自己独占同一个资源，最终只会出现重复释放之类毫无美感的事故。

需要转移所有权时使用 `std::move`：

```cpp
std::unique_ptr<Shape> first = std::make_unique<Circle>();
std::unique_ptr<Shape> second = std::move(first);
```

移动后 `first` 为空，`second` 接管对象所有权。

### 2. `emplace_back` 不是消除切片的魔法

有时会有人把原代码改成：

```cpp
std::vector<Shape> shapes;
shapes.emplace_back(Circle{});
```

这依然会切片。`emplace_back` 的作用是直接在容器元素的存储位置构造元素，**元素类型仍然是 `Shape`**。它不能让 `vector<Shape>` 的一个槽位忽然装下大小和布局都可能不同的 `Circle`、`Rectangle` 等对象。

正确的 `emplace_back` 用法是构造智能指针元素：

```cpp
std::vector<std::unique_ptr<Shape>> shapes;
shapes.emplace_back(std::make_unique<Circle>());
```

这里使用 `push_back` 或 `emplace_back` 通常都可以；重点在元素类型已经变成 `std::unique_ptr<Shape>`，而不在选择哪个插入成员函数。

## 五、其他方案：引用、原始指针与 `shared_ptr`

`unique_ptr` 不是唯一方案。该选择取决于容器是否拥有对象、对象是否共享，以及对象的寿命由谁管理。

### 1. `std::reference_wrapper<Shape>`：容器只借用对象

若 `Circle`、`Rectangle` 已经在别处创建并由别处负责其生命周期，容器只需要引用它们，可以使用 `std::reference_wrapper`：

```cpp
#include <functional>
#include <vector>

int main() {
    Circle circle;
    Rectangle rectangle;

    std::vector<std::reference_wrapper<Shape>> shapes;
    shapes.push_back(circle);
    shapes.push_back(rectangle);

    for (Shape& shape : shapes) {
        shape.draw();
    }
}
```

这种容器**不拥有**对象。`circle` 和 `rectangle` 必须在整个遍历和使用期间保持存活；如果引用已经悬空，后续访问就是未定义行为。引用容器适合生命周期明显由外部管理的场景，不适合用来逃避所有权设计。

### 2. `std::vector<Shape*>`：可以，但必须把所有权说清楚

原始指针同样可以保留多态：

```cpp
std::vector<Shape*> shapes;

Circle circle;
shapes.push_back(&circle);

shapes[0]->draw();
```

这里容器只保存地址，不复制 `Circle`，所以调用会分派到 `Circle::draw()`。但 `shapes` 不拥有 `circle`，而且 `circle` 必须活得比容器中的指针使用时间更久。

不要随手混用下面这种写法：

```cpp
std::vector<Shape*> shapes;
shapes.push_back(new Circle());
```

它要求你在所有路径上手动 `delete`，包括异常、提前返回、插入失败等路径。除非接口明确表示“非拥有的观察指针”，否则应优先使用 `unique_ptr` 或其他能表达所有权的类型。

### 3. `std::shared_ptr<Shape>`：仅在确实共享所有权时使用

当同一个形状必须由多个独立所有者共同延长生命周期时，可以使用：

```cpp
std::vector<std::shared_ptr<Shape>> shapes;
shapes.push_back(std::make_shared<Circle>());
```

`shared_ptr` 通过引用计数管理共享所有权。它并不比 `unique_ptr` “更高级”，只是在语义、性能和生命周期复杂度上更重。没有真实的共享所有权需求时，默认从 `unique_ptr` 开始通常更清楚。

如果 `shared_ptr` 形成环状引用，例如对象 A 和 B 互相持有对方的 `shared_ptr`，引用计数可能永远无法归零。需要从环的一侧改用 `std::weak_ptr`，但这是另一层生命周期问题。

## 六、若需要值语义，考虑 `std::variant` 而不是继承

有些设计确实希望容器**按值**保存形状：对象可以复制，容器也不需要动态分配；形状种类是有限且已知的。这时运行时继承多态未必是最合适的工具。

可以使用 `std::variant`：

```cpp
#include <iostream>
#include <type_traits>
#include <variant>
#include <vector>

struct Circle {
    double radius = 5.0;
};

struct Rectangle {
    double width = 4.0;
    double height = 3.0;
};

using Shape = std::variant<Circle, Rectangle>;

void draw(const Shape& shape) {
    std::visit([](const auto& item) {
        using T = std::decay_t<decltype(item)>;

        if constexpr (std::is_same_v<T, Circle>) {
            std::cout << "Draw a circle with radius " << item.radius << "\n";
        } else {
            std::cout << "Draw a rectangle "
                      << item.width << " x " << item.height << "\n";
        }
    }, shape);
}

int main() {
    std::vector<Shape> shapes;
    shapes.emplace_back(Circle{5.0});
    shapes.emplace_back(Rectangle{4.0, 3.0});

    for (const Shape& shape : shapes) {
        draw(shape);
    }
}
```

`std::variant<Circle, Rectangle>` 的每个元素都有足够空间保存其中任意一种备选类型，不会发生派生对象到基类对象的切片。它是**封闭集合**：可以表示的类型需要在 `variant` 定义时列出来。

两种设计的取舍可以这样看：

| 需求 | 更适合的方案 |
| ---- | ------------ |
| 类型可在以后通过派生类继续扩展 | 多态基类 + `unique_ptr` |
| 类型集合固定，容器要按值保存 | `std::variant` |
| 容器只临时观察外部对象 | 引用、`reference_wrapper` 或非拥有原始指针 |
| 多个组件确实共同决定对象寿命 | `shared_ptr` |

不要仅因为“它们都叫形状”就强行使用继承。建模方式应该服从对象所有权、扩展方式和复制语义，而不是服从一个听起来很像面向对象的名词。

## 七、多态对象为什么通常不应随意复制

即使把容器改成 `std::vector<std::unique_ptr<Shape>>`，仍有一个值得明确的设计问题：如果要复制整个容器，应该怎样复制其中的派生对象？

`unique_ptr` 不可复制，所以这个问题不会被悄悄掩盖。你需要定义多态复制接口，通常命名为 `clone()`：

```cpp
#include <memory>
#include <vector>

class Shape {
public:
    virtual ~Shape() = default;
    virtual void draw() const = 0;
    virtual std::unique_ptr<Shape> clone() const = 0;
};

class Circle : public Shape {
    double radius;

public:
    explicit Circle(double value) : radius(value) {}

    void draw() const override {
        std::cout << "Draw a circle with radius " << radius << "\n";
    }

    std::unique_ptr<Shape> clone() const override {
        return std::make_unique<Circle>(*this);
    }
};
```

随后可以显式深拷贝：

```cpp
std::vector<std::unique_ptr<Shape>> copy_shapes(
    const std::vector<std::unique_ptr<Shape>>& source
) {
    std::vector<std::unique_ptr<Shape>> result;
    result.reserve(source.size());

    for (const auto& shape : source) {
        result.push_back(shape->clone());
    }

    return result;
}
```

这正好说明了对象切片背后的设计事实：基类不知道每个未知派生类要复制多少额外状态，也不知道该构造哪个具体类型。若这些信息很重要，就必须由动态类型自己的 `clone()` 实现负责。

## 八、原始代码的最小改法

如果目标只是让原示例保留多态，最小且现代的改法如下：

```cpp
#include <iostream>
#include <memory>
#include <vector>

class Shape {
public:
    virtual ~Shape() = default;

    virtual void draw() const {
        std::cout << "Draw a generic shape\n";
    }
};

class Circle : public Shape {
    double radius = 5.0;

public:
    void draw() const override {
        std::cout << "Draw a circle with radius " << radius << "\n";
    }
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;

    shapes.push_back(std::make_unique<Circle>());
    shapes[0]->draw();
}
```

输出：

```text
Draw a circle with radius 5
```

变化只有两处：

1. 容器元素从 `Shape` 改为 `std::unique_ptr<Shape>`。
2. 插入完整的 `Circle` 对象并保存其所有权，访问时通过 `->` 调用。

这样 `vector` 里的每一项都指向真实的派生对象，虚函数才有实际的动态类型可以分派。容器负责形状对象的生命周期，代码也不需要手动释放内存。

## 九、总结

原代码的问题可以浓缩成一句话：

> `std::vector<Shape>` 保存的是一个个完整的 `Shape` 值；把 `Circle` 放进去时会发生对象切片，因此容器元素不再是 `Circle`。

需要记住的结论如下：

- `std::vector<Shape>` 并非不能使用虚函数；它只是只能保存 `Shape` 对象，调用时自然执行 `Shape` 的实现。
- 派生对象赋值给基类对象、按值传递给基类参数、按 `Shape` 值返回，都会产生对象切片。
- 基类引用和指针不会复制对象，仍能保留动态类型，因此可以进行运行时多态。
- `virtual ~Shape()` 对多态基类是必要设计，但它解决的是销毁问题，不解决切片问题。
- 需要“容器拥有异构多态对象”时，优先选择 `std::vector<std::unique_ptr<Shape>>`。
- 需要纯值语义且类型集合固定时，`std::variant` 往往比继承层次更合适。

所以，不该简单地说“`vector<Shape>` 不能使用多态”。更严谨的说法是：**异构的运行时多态对象不能以基类值的方式存进 `vector<Shape>` 而不丢失派生部分；应当存指针、智能指针、引用包装器，或者改用适合值语义的 `variant`。** 概念多一些，但至少不再含糊。
