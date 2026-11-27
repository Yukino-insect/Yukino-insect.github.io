+++
date = '2026-11-26T20:00:00+08:00'
draft = false
title = '汽车销售 E-R 图转换为关系模式：一道设计题的完整推导'
+++

E-R 图到关系模式的题目，考查的并不是把图上的文字机械地抄成字段。真正的工作是先读出实体、属性和基数约束，再决定哪些事实应保存在同一张表中。否则，即使表名写对了，也可能把多值属性塞进一个单元格，或把本应只出现一次的事实重复保存。

本文通过一道汽车销售数据库设计题，说明强实体、多值属性和 `N:1` 联系应如何转换为关系模式，并给出能够落地为 SQL 的主键与外键约束。

## 题目

给定一个汽车销售系统的 E-R 图，包含以下对象：

- 实体集 `cars`，属性为 `VIN`、`brand`、`{option}`、`prod_date`；其中 `VIN` 是车辆识别号，`{option}` 表示多值属性。
- 实体集 `customers`，属性为 `cust_id`、`name`、`address`；其中 `cust_id` 是客户编号。
- `cars` 与 `customers` 之间存在 `order` 联系，联系属性为 `order_date` 和 `sale_price`。
- 一辆车最多卖给一名客户；一名客户可以购买多辆车。

要求：将该 E-R 图转换为关系模式，并说明为什么多值属性和 `N:1` 联系应当这样处理。若选择题给出的正确选项是下列结构，则应选择它：

```text
cars(VIN, brand, prod_date, cust_id, order_date, sale_price)
customers(cust_id, name, address)
car_option(VIN, option)
```

## 先读业务规则，而不是急着建表

关系模式来自业务事实。题目中的事实可分为三类：一辆车自身的事实、一个客户自身的事实，以及“某辆车卖给某位客户”这一联系的事实。

| 对象 | 能唯一标识它的属性 | 其他事实 |
| ---- | ------------------ | -------- |
| 汽车 | `VIN` | `brand`、`prod_date`、多个 `option` |
| 客户 | `cust_id` | `name`、`address` |
| 订购关系 | 由一辆具体汽车确定 | `cust_id`、`order_date`、`sale_price` |

“一辆车最多卖给一名客户”决定了联系的方向。用车和客户的对应数量表示，关系是：

```text
customers  1  <----  N  cars
```

这里的 `N` 不表示每辆车有多个客户，恰好相反：它表示一个客户可以出现在多辆车的销售记录中。每辆车至多出现一次销售关系，因此 `VIN` 能唯一确定这条联系上的客户、销售日期和售价。

题目说的是“至多一名”，而不是“恰好一名”。尚未售出的库存车也是合法状态，所以与销售联系对应的 `cust_id`、`order_date`、`sale_price` 可以暂时为 `NULL`；这不是设计疏漏，而是可选参与约束的直接结果。

## E-R 图转换的基础规则

### 强实体集转换为关系

每个强实体集通常先转换为一张关系。实体的键属性成为主键，普通单值属性成为普通列：

```text
customers(cust_id, name, address)
cars(VIN, brand, prod_date)
```

对应的键约束为：

```text
customers: PRIMARY KEY (cust_id)
cars:      PRIMARY KEY (VIN)
```

这一步只解决“客户是什么”和“车辆是什么”。联系和特殊属性仍要单独分析；把图中所有文字一股脑放进实体表，当然省事，却不是关系模型的转换规则。

### 多值属性必须成为独立关系

`{option}` 的花括号表示一辆车可以有零个或多个配置，例如天窗、导航、真皮座椅。关系模型要求字段值是原子的：一格应保存一个配置，而不是保存“天窗, 导航, 真皮座椅”这种待解析的文本。

多值属性的一般转换规则是：以所属实体的主键和该属性共同建立新关系。于是得到：

```text
car_option(VIN, option)
```

其中：

- `(VIN, option)` 是主键，用于防止同一辆车重复登记同一项配置；
- `VIN` 还是引用 `cars(VIN)` 的外键；
- 同一个 `VIN` 可以对应多行，正好表达多值性。

例如，车辆 `V001` 具有三个配置时，数据应写成三行：

| VIN | option |
| --- | ------ |
| V001 | 天窗 |
| V001 | 导航 |
| V001 | 真皮座椅 |

不要通过重复整行 `cars` 数据来表示多个配置。那样会把 `brand`、`prod_date`，甚至销售事实重复多次，并让更新变得不可靠。

### `N:1` 联系的外键放在 N 方

对于二元 `N:1` 联系，通常不需要额外建立联系表。应把“一”方的主键复制到“多”方作为外键，并把联系自身的属性放在同一张“多”方表中。

本题中：

- 一方是 `customers`，其主键为 `cust_id`；
- 多方是 `cars`；
- 联系属性是 `order_date` 和 `sale_price`。

因此，转换后的 `cars` 为：

```text
cars(VIN, brand, prod_date, cust_id, order_date, sale_price)
```

从 E-R 图的角度看，`VIN` 最多对应一组客户、日期和售价信息，因为每辆车最多参与一条销售联系。这里不把它作为含 `NULL` 的 SQL 表上的严格函数依赖来论证；它只是说明了为什么这些联系属性能够随 `VIN` 安放在 `cars` 中。若业务改为“同一辆车可被反复出租或多次转售”，一辆车就可能对应多条交易，此时应建立独立的 `rental` 或 `sale` 关系，并使用订单号或时间段来标识每次联系。关系模式必须服从业务基数，不能反过来替业务作决定。

## 本题的最终关系模式

将三部分合并，得到：

```text
customers(cust_id, name, address)
cars(VIN, brand, prod_date, cust_id, order_date, sale_price)
car_option(VIN, option)
```

若把关系模式落实为 MySQL DDL，可以写成：

```sql
CREATE TABLE customers (
    cust_id VARCHAR(32) PRIMARY KEY,
    name    VARCHAR(100) NOT NULL,
    address VARCHAR(255)
);

CREATE TABLE cars (
    VIN        VARCHAR(32) PRIMARY KEY,
    brand      VARCHAR(100) NOT NULL,
    prod_date  DATE NOT NULL,
    cust_id    VARCHAR(32),
    order_date DATE,
    sale_price DECIMAL(12, 2),
    CONSTRAINT fk_cars_customer
        FOREIGN KEY (cust_id) REFERENCES customers(cust_id),
    CONSTRAINT ck_cars_sale_fields
        CHECK (
            (cust_id IS NULL AND order_date IS NULL AND sale_price IS NULL)
            OR
            (cust_id IS NOT NULL AND order_date IS NOT NULL AND sale_price IS NOT NULL)
        )
);

CREATE TABLE car_option (
    VIN    VARCHAR(32) NOT NULL,
    option VARCHAR(100) NOT NULL,
    PRIMARY KEY (VIN, option),
    CONSTRAINT fk_car_option_car
        FOREIGN KEY (VIN) REFERENCES cars(VIN)
);
```

这里刻意没有把 `cars.cust_id` 设为 `NOT NULL`，因为库存车尚未售出时不应被排除在数据库之外。示例中的 `CHECK` 约束使客户、日期和售价要么同时为空，要么同时出现，避免“没有客户却有售价”这样的半成品销售记录。反过来，如果业务要求“录入车辆即表示已售出”，才应把这几个销售相关字段设计为非空。

## 为什么答案中的其他常见写法不合适

### 将 `option` 留在 `cars` 中

```text
cars(VIN, brand, option, prod_date, ...)
```

若 `option` 是普通单列，它无法自然地保存多个独立配置。用逗号拼接多个值会破坏原子性；用多行车辆记录则会重复车辆信息。因此它不能正确表达 E-R 图中的多值属性。

### 为 `N:1` 联系建立单独的 `order` 表

```text
order(VIN, cust_id, order_date, sale_price)
```

这并非在所有系统中都错误。若订单本身拥有订单号、付款状态、物流状态或一张订单可包含多辆车，它很可能应成为独立实体。但是在本题给定的简单 `N:1` 联系里，订单事实最多对应一辆具体车，把它放在 `cars` 中更直接，也正是标准 E-R 映射规则所给出的结果。

### 在 `car_option` 中重复保存 `cust_id`

```text
car_option(VIN, cust_id, option)
```

配置属于车辆，不属于“车辆卖给谁”这件事。把 `cust_id` 加入配置表会让同一客户编号随每一项配置重复出现，也会让未售车辆的配置携带无意义的空值。能由 `VIN` 经 `cars` 关联得到的信息，不应无故复制到 `car_option`。

## 同类题的检查顺序

面对任意 E-R 图转换题，可以按下面的顺序推导：

1. 为每个强实体建立关系，并标出主键。
2. 拆分复合属性；为多值属性建立“实体主键 + 属性值”的独立关系。
3. 依据箭头、基数标记和题目文字判断 `1:1`、`1:N` 或 `M:N`。
4. 对 `1:N`，将一方主键及联系属性放在多方；对 `M:N`，建立包含两边主键的联系关系。
5. 检查每张表的主键、外键、可空性与重复信息是否符合题目约束。

弱实体、三元联系和泛化/特化还需要额外规则，但它们并不改变这套思考顺序。

## 从本题扩展到完整的二元联系映射

本题只需要处理多值属性和 `N:1` 联系，但理解其余映射规则，才能避免换一张 E-R 图就失去判断依据。

### `1:1` 联系：选择合适的一方承载外键

若两端最多各对应一个对象，可以把任一方的主键放到另一方作为外键，并对该外键加 `UNIQUE` 约束。实际选择时，通常优先放在：

- 全参与联系的一方，减少空值；
- 记录数较少或生命周期依附于另一方的一方；
- 更常需要沿该方向查询的一方。

例如，每位员工最多有一张工牌、每张工牌只属于一位员工，可以设计为：

```text
Employee(employee_id, name, badge_id)
Badge(badge_id, issued_at)
```

其中 `Employee.badge_id` 是引用 `Badge.badge_id` 的唯一外键。联系自身的属性也应与外键放在同一侧。若两侧都全参与，或联系具有大量独立属性，则建立独立联系表同样是合理选择。

### `M:N` 联系：必须建立独立关系

学生选课是典型的多对多联系：一个学生可选多门课，一门课也可被多个学生选择。将外键只放在任一实体表中都无法表达多个匹配对象，因此必须建立联系关系：

```text
Student(student_id, name)
Course(course_id, title)
Enrollment(student_id, course_id, enroll_date, grade)
```

`Enrollment` 的主键通常是 `(student_id, course_id)`；两个字段同时也是外键。`enroll_date` 与 `grade` 描述的是“某学生选了某课程”这一事实，不能误放到 `Student` 或 `Course` 中。

### 弱实体：主键必须包含拥有者的主键

弱实体自身的部分键不能独立标识对象，必须依靠拥有者实体。例如家属只能在某位员工范围内按姓名区分时：

```text
Employee(employee_id, name)
Dependent(employee_id, dependent_name, relationship)
```

`Dependent` 的主键为 `(employee_id, dependent_name)`，其中 `employee_id` 同时是外键。仅使用 `dependent_name` 作为键显然不可靠；世界上同名的人比初学者以为的多得多。

### 可选参与与外键可空性

联系的最小基数决定外键能否为空：

- 若每个多方对象都必须关联一方对象，外键应为 `NOT NULL`。
- 若多方对象可暂时不参与联系，外键可为空。
- 对多对多关系，是否允许联系表为空由“是否允许尚未发生联系”决定，而不是由外键本身决定。

因此，E-R 图中的双线、单线、`0..1`、`1..*` 等参与约束不是装饰。它们会直接影响 SQL 中的 `NOT NULL`、`UNIQUE`、`CHECK` 和外键策略。

## 总结

本题的正确模式为：

```text
cars(VIN, brand, prod_date, cust_id, order_date, sale_price)
customers(cust_id, name, address)
car_option(VIN, option)
```

- `cars` 和 `customers` 是强实体，因此各自成为一张关系。
- `{option}` 是多值属性，因此转换为 `car_option(VIN, option)`。
- 汽车到客户是 `N:1` 联系，因此将 `customers.cust_id` 和联系属性存入 `cars`。
- 未售出车辆允许销售相关字段为空，这是“至多一名客户”的自然含义。

只要始终把“一个属性描述谁”“一条联系能出现几次”问清楚，E-R 图转换题并不需要死记选项。毕竟，数据库不会替你修复含混的业务理解。
