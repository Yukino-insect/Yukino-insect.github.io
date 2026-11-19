+++
date = '2026-11-19T12:00:00+08:00'
draft = false
title = '医院住院模型的设计验证：函数依赖、范式与无损分解'
+++

完成医院病房管理系统的 E-R 图和关系模式后，仍要回答一个更严格的问题：这些表为什么应当这样拆？如果把患者、医生、病床和住院信息塞进一张大表，会发生什么；拆开后又如何证明不会丢失事实或凭空制造事实？

本文只围绕医院住院案例，使用函数依赖、属性闭包、范式、无损连接与依赖保持验证关系模式。目标不是把范式当作孤立术语背诵，而是学会为“这列该放在哪张表”给出可检验的理由。

## 一、函数依赖来自业务规则

若属性集 `X` 的值能唯一确定属性集 `Y` 的值，记作：

```text
X → Y
```

它表示一种业务语义约束，不是观察到几行样本数据后得到的巧合。例如，患者编号唯一，因此：

```text
patient_id → patient_name, gender, birth_date
```

但通常不能反过来写：

```text
patient_name → patient_id
```

因为允许存在同名患者。

医院模型中的主要函数依赖可整理为：

```text
department_id → department_name, office_room, department_phone
sickroom_id   → department_id, bed_capacity, room_location
bed_id        → sickroom_id, bed_type
doctor_id     → department_id, doctor_name, birth_date,
                 professional_title, education, joined_department_on
patient_id    → patient_name, gender, birth_date

(patient_id, admission_no) → attending_doctor_id, bed_id,
  admission_time, admission_reason, admission_diagnosis,
  diagnosis_conclusion, discharge_time
```

最后一条尤其重要：床位和主治医生由“某患者的某次住院”决定，不是患者一生不变的属性。

## 二、用属性闭包证明住院记录的主键

属性集 `X` 能在函数依赖集合下推出的所有属性，称为 `X` 的属性闭包，记为 `X+`。计算时先放入 `X` 本身，再反复应用左部已经满足的函数依赖，直到无法加入新属性。

对于：

```text
HOSPITALIZATION(
  patient_id,
  admission_no,
  attending_doctor_id,
  bed_id,
  admission_time,
  admission_reason,
  admission_diagnosis,
  diagnosis_conclusion,
  discharge_time
)
```

由前节依赖可得：

```text
(patient_id, admission_no)+
  = HOSPITALIZATION 的全部属性
```

所以 `(patient_id, admission_no)` 是超键。去掉 `patient_id` 后，`admission_no` 只在单个患者内部有意义；去掉 `admission_no` 后，一名患者可有多次住院。因此它还是最小超键，即候选键，可选择为主键。

这说明弱实体的联合主键不是“看上去应该这么写”，而是由其识别语义证明出来的。

## 三、把所有信息放进一张表为什么错误

假设设计了下列大表：

```text
BAD_STAY(
  patient_id, admission_no, patient_name, patient_birth_date,
  attending_doctor_id, doctor_name, doctor_title,
  bed_id, sickroom_id, room_location,
  admission_time, discharge_time
)
```

其键为 `(patient_id, admission_no)`。患者、医生和病房属性会随着每一次住院不断重复，由此出现三类异常。

### 更新异常

医生职称变更时，必须修改该医生所有历史住院行。只要漏改一行，数据库就同时保存两种职称。

### 插入异常

医院想先登记一张空病床时，如果大表要求填写患者和住院编号，便无法保存这张尚未使用的病床。

### 删除异常

删除某患者最后一条住院记录时，患者姓名和出生日期等本应继续保留的建档事实也可能消失。

问题不在于列数多，而在于不同粒度的事实被混在一起：患者事实、医生事实、病房事实和一次住院事件事实不应由同一主键统一决定。

## 四、用范式定位冗余来源

### 第一范式：多值电话不能塞进重复列

下列设计人为限制了电话号码数量：

```text
PATIENT(patient_id, phone_1, phone_2, phone_3)
```

用逗号把多个号码放进一个字符串同样不利于查询和约束。更合适的结构是：

```text
PATIENT(patient_id, ...)
PATIENT_PHONE(patient_id, phone_number)
```

这满足 1NF 的要求：每个属性位置保存当前语义下的单一值。电话号码本身应仍使用字符类型；“原子”不意味着要把号码拆成每一位数字。

### 第二范式：移除对复合键一部分的依赖

若把 `patient_name` 放进住院表，就有：

```text
(patient_id, admission_no) → patient_name
patient_id → patient_name
```

`patient_name` 只依赖复合主键的一部分 `patient_id`，这就是部分函数依赖。应将它留在：

```text
PATIENT(patient_id, patient_name, gender, birth_date)
```

住院表只保存 `patient_id` 外键。这样患者每次入院不会复制基本档案，也不会在改名时留下不一致记录。

### 第三范式：移除非主属性间的传递依赖

若住院表保存医生姓名：

```text
(patient_id, admission_no) → attending_doctor_id
attending_doctor_id → doctor_name, professional_title
```

住院主键会通过 `attending_doctor_id` 传递地决定医生姓名和职称。医生描述属性应放在 `DOCTOR`，住院表只保留医生外键。

病房位置也是相同的道理：

```text
bed_id → sickroom_id
sickroom_id → room_location
```

因此 `room_location` 不应复制到 `HOSPITALIZATION`。

3NF 的正式判定是：对每个非平凡依赖 `X → A`，`X` 必须是超键，或者 `A` 必须是某个候选键中的主属性。直观上，它要求非键属性直接依赖于键，而非依赖另一个非键属性。

### BCNF：决定因素必须是超键

BCNF 要求每个非平凡函数依赖的左部都是超键。当前模型的主要关系通常满足这一要求：

```text
PATIENT:          patient_id → 其他属性
DOCTOR:           doctor_id → 其他属性
HOSPITALIZATION:  (patient_id, admission_no) → 本次住院属性
```

若再声明“科室名称全局唯一”，则 `department_name → department_id` 也必须纳入设计，并用唯一约束实施。BCNF 比 3NF 更严格，但不应为了追求形式上的最高范式而忽略约束检查和查询的实际成本。

## 五、无损连接：分表后不能造出假事实

把关系 `R` 分解为 `R1`、`R2` 后，若始终成立：

```text
R = πR1(R) ⋈ πR2(R)
```

则称该分解无损。它保证先投影拆表、再自然连接，不会丢失元组，也不会产生原来不存在的元组。

从大住院表拆出患者信息时：

```text
R(patient_id, admission_no, patient_name, admission_time, ...)

R1 = PATIENT(patient_id, patient_name, ...)
R2 = HOSPITALIZATION(patient_id, admission_no, admission_time, ...)
```

公共属性是 `patient_id`，而 `patient_id` 能决定 `PATIENT` 的全部属性，所以这是一种无损分解。每条住院记录都能准确连接回所属患者。

反过来，不能把三元事实随意拆成两张二元表。若：

```text
R(patient_id, doctor_id, bed_id)
R1(patient_id, doctor_id)
R2(doctor_id, bed_id)
```

原数据只有：

```text
(P1, D1, B1)
(P2, D1, B2)
```

按 `doctor_id` 连接后还会得到 `(P1, D1, B2)` 与 `(P2, D1, B1)`，这是从未发生过的伪元组。因此，若一个事实同时依赖患者、医生和病床的特定组合，不能只因“都能两两关联”就丢掉它们的组合语义。

## 六、依赖保持：避免靠大连接才能检查规则

若分解后的各关系上的函数依赖能联合推出原依赖，而不必把多张表连接起来检查，就称分解保持依赖。

例如：

```text
PATIENT:
  patient_id → patient_name, birth_date

DOCTOR:
  doctor_id → doctor_name, professional_title
```

每条依赖可在自己的关系中由主键或唯一约束直接维护。无损连接与依赖保持的侧重点不同：

| 质量目标 | 需要避免的问题 |
| --- | --- |
| 无损连接 | 拆表后丢失事实或制造伪元组 |
| 依赖保持 | 验证一项依赖时必须执行昂贵的跨表连接 |

良好的设计通常尽量兼顾二者。3NF 分解常能同时达到无损和依赖保持；BCNF 分解有时则会以更严格的去冗余换取较弱的依赖保持。

## 七、范式无法代替所有业务约束

函数依赖和范式只能帮助确定事实的归属，不会自动表达所有医院规则。例如：

- 同一张床的住院时间区间不得重叠。
- 病房实际登记的床位数不得超过 `bed_capacity`。
- 若规定主治医生必须属于病床所在科室，需要比较多张表。
- 若规定患者不能同时存在两次未出院住院记录，需要比较同一患者的多行住院记录。

这些是跨行或跨表约束，通常要在事务内锁定有关记录后检查，或用触发器、专门的占床状态关系、统一服务入口实现。规范化不会替代这一步。

## 小结

- 函数依赖源于业务语义；属性闭包可以证明超键和候选键。
- 患者、医生、病床和一次住院属于不同粒度的事实，混入大表会造成更新、插入和删除异常。
- 1NF 处理重复组，2NF 处理对复合键部分的依赖，3NF 处理非主属性间的传递依赖。
- 无损连接保证拆表后不造假数据，依赖保持保证约束无需总靠跨表连接检查。
- 时间重叠、容量上限等跨行规则仍需由事务、触发器或服务层落实。
