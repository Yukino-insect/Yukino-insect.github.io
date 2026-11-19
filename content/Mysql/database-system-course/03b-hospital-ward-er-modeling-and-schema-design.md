+++
date = '2026-11-19T09:00:00+08:00'
draft = false
title = '医院病房管理系统 ER 图：从需求到关系模式与 MySQL 约束'
+++

医院病房管理题的难点不在于写出几条 `CREATE TABLE`，而在于分清每一项信息究竟描述谁：医生属于科室，病床属于病房，而入院时间、主治医生、床位和诊断结论描述的是患者的**某一次住院**。若把后者直接写进患者表，患者第二次住院时第一次记录就只能被覆盖。

本文以一个小型医院病房管理需求为例，完整演示从自然语言规则、Chen E-R 图，到关系模式和 MySQL 约束的推导过程。重点是建立可复核的设计理由：为什么要引入住院记录，哪些联系是 `1:N`，哪些参与必须是完全参与，以及哪些规则不能只靠外键解决。

## 一、先把需求改写成可建模的业务规则

设系统要管理科室、病房、病床、医生、患者和住院信息。为了避免“有多个”“属于”等自然语言造成歧义，先明确以下规则：

- 一个科室可以管理零个或多个病房；每个病房必须属于一个科室。
- 一个科室可以有零名或多名医生；每位医生必须属于一个科室。
- 一个病房可以包含零张或多张病床；每张病床必须属于一个病房。
- 患者可以尚未住院，也可以有多次住院记录；每次住院只属于一位患者。
- 每次住院必须指定一位主治医生和一张病床；一位医生、一张病床可以在不同时间服务多次住院。
- 患者可以登记多个联系电话。
- 住院天数由入院时间和出院时间计算，不作为可随意修改的基础事实保存。

最后两条很重要：它们分别对应多值属性和派生属性。至于“同一床位在同一时间不能安排两位患者”，它跨越多条住院记录，后文会单独处理，不能假装一条普通外键就能解决。

## 二、识别实体：谁有独立身份，谁描述一次事件

能依靠自身标识独立存在的对象，建模为强实体集。这里有五个：

| 强实体集 | 主键 | 主要属性 |
| --- | --- | --- |
| `DEPARTMENT` | `department_id` | `department_name`、`office_room`、`department_phone` |
| `SICKROOM` | `sickroom_id` | `bed_capacity`、`room_location` |
| `BED` | `bed_id` | `bed_type` |
| `DOCTOR` | `doctor_id` | `doctor_name`、`birth_date`、`professional_title`、`education` |
| `PATIENT` | `patient_id` | `patient_name`、`gender`、`birth_date` |

它们在 Chen E-R 图中画成单矩形，键属性名画实线下划线。 `phone_number` 不是第六个强实体：题目只要求保存号码值，并未赋予号码独立生命周期，因此它是患者的多值属性。

### 为什么“住院记录”不能放在患者实体中

下面的设计看似直观，实际会破坏历史：

```text
PATIENT(
  patient_id,
  patient_name,
  attending_doctor_id,
  bed_id,
  admission_time,
  discharge_time,
  diagnosis_conclusion
)
```

它隐含“一个患者只能住院一次”。患者再次入院时，新的床位、医生和时间会覆盖旧值；若重复增加 `bed_1`、`bed_2`、`admission_time_1` 等列，则只是把可重复的业务事实伪装成固定数量的字段。

因此应增加 `HOSPITALIZATION`（住院记录）。本例不额外虚构全局住院 ID，而是在每位患者内部用 `admission_no` 区分第几次住院：

```text
PATIENT 的键：             patient_id
HOSPITALIZATION 的部分键： admission_no
完整标识：                 (patient_id, admission_no)
```

`HOSPITALIZATION` 依赖患者才能被完整识别，因此可在 Chen 图中建模为弱实体：画双矩形；`HAS_ADMISSION` 画双菱形；弱实体一侧连接标识联系时画双线。 `admission_no` 是部分键，不是可以全局唯一识别住院记录的独立主键。

## 三、确定联系、基数与参与约束

下面的表把每一条业务规则翻译为 E-R 联系。 `1:N` 表示最大基数；“完全参与”表示最小参与次数至少为 1。两者必须同时判断。

| 联系 | 基数 | 必须参与的一端 | 业务含义 |
| --- | --- | --- | --- |
| `HAS_SICKROOM`：科室—病房 | `DEPARTMENT 1:N SICKROOM` | `SICKROOM` | 每个病房恰好属于一个科室 |
| `EMPLOYS`：科室—医生 | `DEPARTMENT 1:N DOCTOR` | `DOCTOR` | 每位医生恰好属于一个科室；联系属性为 `joined_department_on` |
| `CONTAINS_BED`：病房—病床 | `SICKROOM 1:N BED` | `BED` | 每张病床恰好属于一个病房 |
| `HAS_ADMISSION`：患者—住院 | `PATIENT 1:N HOSPITALIZATION` | `HOSPITALIZATION` | 每条住院记录恰好属于一位患者 |
| `ATTENDS`：医生—住院 | `DOCTOR 1:N HOSPITALIZATION` | `HOSPITALIZATION` | 每次住院恰好有一位主治医生 |
| `ASSIGNED_TO`：病床—住院 | `BED 1:N HOSPITALIZATION` | `HOSPITALIZATION` | 每次住院恰好使用一张病床 |

例如，`ATTENDS` 不是“医生和患者”的直接联系，而是“医生负责哪次住院”的联系。这样同一患者不同次住院可由不同医生负责，模型不会把一次就诊的事实误认为患者永久属性。

### Chen 图的文字复原版

纸面实际作图时，应使用矩形、菱形、椭圆、双线和下划线；下面只是把结构写成可核对的文字版：

```text
[DEPARTMENT] 1 ── HAS_SICKROOM ─═ N [SICKROOM]
[DEPARTMENT] 1 ── EMPLOYS ───────═ N [DOCTOR]
[SICKROOM]   1 ── CONTAINS_BED ──═ N [BED]

[PATIENT]    1 ── HAS_ADMISSION ══ N [[HOSPITALIZATION]]
[DOCTOR]     1 ── ATTENDS ───────═ N [[HOSPITALIZATION]]
[BED]        1 ── ASSIGNED_TO ───═ N [[HOSPITALIZATION]]
```

约定如下：

- `[ENTITY]` 表示强实体的单矩形；`[[ENTITY]]` 表示弱实体的双矩形。
- `HAS_ADMISSION` 在实际图中是双菱形，其他联系是单菱形。
- `═` 表示双线，即该实体对该联系完全参与；普通横线表示部分参与。
- `PATIENT`、`DOCTOR`、`BED` 可以暂时没有住院记录，所以它们在后三个联系中使用单线。

`PATIENT` 还应连接双线椭圆 `phone_number`；`HOSPITALIZATION` 连接虚线椭圆 `stay_days`。后者由时间计算，属于派生属性。

## 四、给实体和弱实体安排属性

在 Chen 图中，强实体的键属性为实线下划线；弱实体的部分键用虚线下划线。可以按以下清单作图：

```text
DEPARTMENT
  _department_id_, department_name, office_room, department_phone

SICKROOM
  _sickroom_id_, bed_capacity, room_location

BED
  _bed_id_, bed_type

DOCTOR
  _doctor_id_, doctor_name, birth_date, professional_title,
  education

PATIENT
  _patient_id_, patient_name, gender, birth_date, ((phone_number))

HOSPITALIZATION（弱实体）
  admission_no（部分键）, admission_time, admission_reason,
  admission_diagnosis, diagnosis_conclusion, discharge_time,
  stay_days（派生属性）
```

`joined_department_on` 应作为 `EMPLOYS` 的联系属性，表达“医生在某日加入某个科室”，而不是医生脱离科室后仍成立的固有属性。由于本例的 `EMPLOYS` 是当前状态的一对多联系，转换到关系模式后，它可随 `department_id` 一起存进 `DOCTOR`。如果医院要保存历次科室调动，应把它改成独立的任职记录，而不是继续覆盖 `DOCTOR.department_id` 与该日期。

## 五、从 E-R 图转换为关系模式

转换规则并不复杂：

1. 每个强实体变成一张关系，实体键成为主键。
2. 对没有自身属性的 `1:N` 联系，把 `1` 端主键放入 `N` 端作为外键。
3. 多值属性单独成为关系，其主键通常为“拥有者主键 + 属性值”。
4. 弱实体关系包含拥有者主键和部分键；两者合成完整主键。
5. 派生属性通常不作为可编辑列存储，而是在查询或视图中计算。

得到的关系模式如下。这里使用 `PK`、`FK` 直接标记键；既是主键又是外键的 `patient_id` 必须同时标出。

```text
DEPARTMENT(
  department_id PK,
  department_name,
  office_room,
  department_phone
)

SICKROOM(
  sickroom_id PK,
  department_id FK → DEPARTMENT(department_id),
  bed_capacity,
  room_location
)

BED(
  bed_id PK,
  sickroom_id FK → SICKROOM(sickroom_id),
  bed_type
)

DOCTOR(
  doctor_id PK,
  department_id FK → DEPARTMENT(department_id),
  doctor_name,
  birth_date,
  professional_title,
  education,
  joined_department_on
)

PATIENT(
  patient_id PK,
  patient_name,
  gender,
  birth_date
)

PATIENT_PHONE(
  patient_id PK, FK → PATIENT(patient_id),
  phone_number PK
)

HOSPITALIZATION(
  patient_id PK, FK → PATIENT(patient_id),
  admission_no PK,
  attending_doctor_id FK → DOCTOR(doctor_id),
  bed_id FK → BED(bed_id),
  admission_time,
  admission_reason,
  admission_diagnosis,
  diagnosis_conclusion,
  discharge_time
)
```

概念 E-R 图中不要把 `department_id` 作为 `DOCTOR` 的普通属性重复画一遍；它是从 `EMPLOYS` 联系映射出来的实现字段。相反，在关系模式和 SQL 表结构图中，应明确显示它是外键。

## 六、将模型落实为 MySQL 8 约束

下面的 DDL 保留了模型中的主键、外键、值域约束和常用查询索引。为了让“每次住院必须有患者、医生和病床”在数据库中成立，相应外键列使用 `NOT NULL`。

```sql
CREATE TABLE department (
  department_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  department_name VARCHAR(100) NOT NULL,
  office_room VARCHAR(100) NOT NULL,
  department_phone VARCHAR(32) NOT NULL,
  PRIMARY KEY (department_id)
) ENGINE = InnoDB;

CREATE TABLE sickroom (
  sickroom_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  department_id BIGINT UNSIGNED NOT NULL,
  bed_capacity SMALLINT UNSIGNED NOT NULL,
  room_location VARCHAR(100) NOT NULL,
  PRIMARY KEY (sickroom_id),
  UNIQUE KEY uk_sickroom_department_room (department_id, room_location),
  CONSTRAINT ck_sickroom_bed_capacity CHECK (bed_capacity > 0),
  CONSTRAINT fk_sickroom_department
    FOREIGN KEY (department_id) REFERENCES department (department_id)
) ENGINE = InnoDB;

CREATE TABLE bed (
  bed_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sickroom_id BIGINT UNSIGNED NOT NULL,
  bed_type VARCHAR(30) NOT NULL,
  PRIMARY KEY (bed_id),
  KEY idx_bed_sickroom (sickroom_id),
  CONSTRAINT fk_bed_sickroom
    FOREIGN KEY (sickroom_id) REFERENCES sickroom (sickroom_id)
) ENGINE = InnoDB;

CREATE TABLE doctor (
  doctor_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  department_id BIGINT UNSIGNED NOT NULL,
  doctor_name VARCHAR(100) NOT NULL,
  birth_date DATE NOT NULL,
  professional_title VARCHAR(60) NOT NULL,
  education VARCHAR(60) NOT NULL,
  joined_department_on DATE NOT NULL,
  PRIMARY KEY (doctor_id),
  KEY idx_doctor_department (department_id),
  CONSTRAINT fk_doctor_department
    FOREIGN KEY (department_id) REFERENCES department (department_id)
) ENGINE = InnoDB;

CREATE TABLE patient (
  patient_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  patient_name VARCHAR(100) NOT NULL,
  gender CHAR(1) NOT NULL,
  birth_date DATE NOT NULL,
  PRIMARY KEY (patient_id),
  CONSTRAINT ck_patient_gender CHECK (gender IN ('M', 'F', 'U'))
) ENGINE = InnoDB;

CREATE TABLE patient_phone (
  patient_id BIGINT UNSIGNED NOT NULL,
  phone_number VARCHAR(32) NOT NULL,
  PRIMARY KEY (patient_id, phone_number),
  CONSTRAINT fk_patient_phone_patient
    FOREIGN KEY (patient_id) REFERENCES patient (patient_id)
    ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE hospitalization (
  patient_id BIGINT UNSIGNED NOT NULL,
  admission_no SMALLINT UNSIGNED NOT NULL,
  attending_doctor_id BIGINT UNSIGNED NOT NULL,
  bed_id BIGINT UNSIGNED NOT NULL,
  admission_time DATETIME NOT NULL,
  admission_reason VARCHAR(500) NOT NULL,
  admission_diagnosis VARCHAR(500),
  diagnosis_conclusion TEXT,
  discharge_time DATETIME,
  PRIMARY KEY (patient_id, admission_no),
  KEY idx_hospitalization_doctor_time (attending_doctor_id, admission_time),
  KEY idx_hospitalization_bed_time (bed_id, admission_time),
  CONSTRAINT ck_hospitalization_time
    CHECK (discharge_time IS NULL OR discharge_time >= admission_time),
  CONSTRAINT fk_hospitalization_patient
    FOREIGN KEY (patient_id) REFERENCES patient (patient_id),
  CONSTRAINT fk_hospitalization_doctor
    FOREIGN KEY (attending_doctor_id) REFERENCES doctor (doctor_id),
  CONSTRAINT fk_hospitalization_bed
    FOREIGN KEY (bed_id) REFERENCES bed (bed_id)
) ENGINE = InnoDB;
```

`stay_days` 可以按查询口径计算，而不放入 `hospitalization`：

```sql
SELECT
  patient_id,
  admission_no,
  admission_time,
  discharge_time,
  CASE
    WHEN discharge_time IS NULL THEN NULL
    ELSE DATEDIFF(discharge_time, admission_time)
  END AS stay_days
FROM hospitalization;
```

若业务要求“入院日和出院日都算一天”，则应在明确口径后把计算式调整为 `DATEDIFF(...) + 1`。模型只能说明它是派生值，不能替业务方决定计费规则。

## 七、外键无法独立保证的规则

下面几条规则跨越多行数据或多个关系，不能只靠 `PRIMARY KEY`、`FOREIGN KEY` 和单行 `CHECK` 完成：

- 同一张床的两个住院时间区间不能重叠。
- 某病房实际登记的病床数不能超过 `bed_capacity`。
- 若规定主治医生必须与病床所属科室相同，需要跨 `DOCTOR`、`BED`、`SICKROOM`、`HOSPITALIZATION` 比较。
- 若规定一位患者不能同时拥有两条未出院住院记录，需要检查同一患者的其他行。

这些规则通常要在事务中锁定相关记录后检查，或由触发器、专门的占床状态表、统一服务入口实施。把它们遗漏并不会使 E-R 图失效，但会使“设计已经保证业务正确”的结论变得不诚实。

## 八、常见错误与检查清单

### 把联系实现字段提前画成实体属性

在概念 E-R 图中，`DEPARTMENT` 与 `DOCTOR` 的归属应由 `EMPLOYS` 联系表达。 `DOCTOR.department_id` 是转换到关系模型后才出现的外键，不是概念图中需要重复画出的普通椭圆。

### 把多值电话拆成固定列

`phone_1`、`phone_2`、`phone_3` 会人为限制号码数量。正确的 E-R 表达是多值属性，正确的关系模型表达是 `PATIENT_PHONE(patient_id, phone_number)`。

### 把弱实体误认为“任何复合主键表”

`HOSPITALIZATION` 是弱实体，是因为它的身份在语义上依赖患者及标识联系；不是仅仅因为它的主键恰好有两列。反过来，联合主键关系表也不一定是弱实体。

### 只写 `1:N`，漏掉最低参与次数

`1:N` 只说明最多多少。 `HOSPITALIZATION` 到患者、医生和病床的双线表达“至少一个”；两类信息合起来才得到“恰好一个”。

## 小结

- 医院案例应将科室、病房、病床、医生和患者建模为强实体，将一次住院建模为带部分键的弱实体。
- 床位、主治医生、入出院时间和诊断结论属于住院记录，不属于患者的永久属性。
- `1:N` 联系通常把 `1` 端主键作为 `N` 端外键；多值电话需要独立关系；弱实体的拥有者键同时是外键和联合主键的一部分。
- `NOT NULL`、主键、外键和 `CHECK` 能落实许多图中规则，但时间区间不重叠等跨行约束仍需额外机制。
