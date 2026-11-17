+++
date = '2026-11-17T08:00:00+08:00'
draft = false
title = '医院病房管理系统 ER 图：按教材 Chen 记法完整设计与关系模式转换'
+++

这道题真正考查的不是“能不能写出几条 `CREATE TABLE`”，而是能否把题目中的自然语言，严格翻译成教材所说的**实体集、属性、联系集、基数约束和参与约束**。尤其是“患者每次住院只使用一个床位、每次住院有一个主治医生”这句话，说明床位、医生、入院时间和诊断结论属于**某一次住院**，而不是患者这个人永久不变的属性。

本文只采用你给出的 Silberschatz、Korth、Sudarshan《Database System Concepts》第 7 版中 E-R 模型和关系数据库设计的概念体系来组织答案。该版本目录将“Database Design Using the E-R Model”列为第 6 章、将“Relational Database Design”列为第 7 章，可由[出版社的教材目录](https://www.mheducation.com/highered/product/database-system-concepts-silberschatz.html)核对。重点不是给出一张看起来漂亮但无法复原的图片，而是把“纸上这张图应该怎样画”逐笔说明：哪个概念画成矩形，哪个概念画成菱形，哪个字段画成椭圆，哪一条连接线画双线，哪一端标 `1`、哪一端标 `N`。即使没有图片工具，读者也可以根据本文的文字和 ASCII 草图完整重画 E-R 图。

为保持教材语义的严谨性，本文将“一次住院”建模为依赖于患者的**弱实体集** `Hospitalization`。患者的联系电话画成多值属性，住院天数画成派生属性。最后再把这张 Chen E-R 图转换为关系模式，并给出 MySQL 8.0 的 DDL。项目中其他文章的案例和画法不作为本篇的设计依据。

## 一、教材规定的 Chen E-R 图怎么画

### 1. 图形与语义一一对应

在 Chen 表示法中，不同图形不是装饰，而是不同种类的数据库概念：

| 图形 | 教材语义 | 本题中的例子 |
| ---- | -------- | ------------ |
| 单线矩形 | 强实体集 | 科室、病房、病床、医生、患者 |
| 双线矩形 | 弱实体集 | 一次住院记录 |
| 单线菱形 | 普通联系集 | 属于、任职、包含、负责、分配 |
| 双线菱形 | 标识联系集 | 患者拥有住院记录 |
| 单线椭圆 | 普通属性 | 科室名称、床位类型、姓名 |
| 属性名下划线 | 键属性 | 科室 ID、病房 ID、医生 ID、患者 ID |
| 双线椭圆 | 多值属性 | 患者联系电话 |
| 虚线椭圆 | 派生属性 | 住院天数 |
| 从一个椭圆分出多个椭圆 | 复合属性 | 若把地址拆成楼栋、楼层、房间 |
| 双线连接 | 全参与约束 | 每个病房必须属于一个科室 |
| 单线连接 | 部分参与约束 | 患者可以尚未住院 |

实体集是同一类实体的集合，而不是某一条具体数据。例如矩形 `Department` 表示所有科室，某个“心内科”才是其中一个实体实例。联系集也一样，菱形 `belongs_to` 表示所有“病房属于科室”的联系实例。

### 2. 键属性的画法

每个强实体集至少有一个能唯一标识实体的键属性。以 `Department` 为例：

1. 画一个矩形，写 `DEPARTMENT`。
2. 画四个椭圆，并分别连接到矩形。
3. 在 `department_id` 这个椭圆内的文字下方画下划线。
4. `department_name`、`office_room`、`department_phone` 不加下划线。

纸面上可用下面的文字模拟属性椭圆：

```text
                 (department_name)
                        |
(_department_id_) -- [DEPARTMENT] -- (office_room)
                        |
                (department_phone)
```

下划线应画在**键属性名**下方，而不是把实体矩形的名称下划线。若一个实体使用复合键，就分别标出组成键的多个属性；若是弱实体，则由拥有者实体的主键和弱实体自己的部分键共同标识。

### 3. 基数约束与参与约束

教材中最常见的基数标记是 `1`、`N` 或 `M`。例如：

```text
[DEPARTMENT] 1 ----- <HAS_SICKROOM> ----- N [SICKROOM]
```

含义是：一个科室可以对应多个病房，而一个病房只对应一个科室。`1:N` 只说明最大基数，不等于“双方都必须存在”。是否必须参加联系，要看连接线：

- 双线：全参与，实体集中的每个实体都必须参加该联系；
- 单线：部分参与，实体可以暂时不参加该联系。

如果老师采用 min-max 写法，可以把两端补充成：

- `(1,1)`：必须且只能对应一个；
- `(0,1)`：可以没有，最多一个；
- `(0,N)`：可以没有，也可以有多个；
- `(1,N)`：至少一个，且可以有多个。

例如“病房只能属于一个科室”是病房端 `(1,1)`；“一个科室可以暂时没有登记病房”则科室端是 `(0,N)`。本文会同时写出 `1:N` 和中文含义，避免只看符号产生歧义。

### 4. 多值、派生、复合属性

一个实体可以有多个同类值时，属性画成双线椭圆。本题中患者可以预留多个联系电话，因此在 `PATIENT` 矩形旁边画双线椭圆 `phone_number`。不要画 `phone1`、`phone2`、`phone3`，也不要把号码拼成一个字符串。

一个属性可以由其他属性计算得到时，画成虚线椭圆。本题的 `stay_days` 由入院和出院时间计算，应画虚线椭圆，而不是普通实线椭圆。

一个属性还可以继续拆成若干有意义的部分时，画复合属性。例如可把 `office_address` 椭圆连接到 `building`、`floor`、`room` 三个子椭圆。本题只要求办公地址，因此把它作为一个简单属性即可。

## 二、E-R 模型必须掌握的基础概念

会画矩形和菱形还不够。E-R 图的价值在于让每一种图形都对业务事实作出可检验的声明：什么可以独立存在，什么必须依附别人，什么对象必须参加某个联系，什么对象可以暂时不参加。下面的概念是画本题，也是在考试中判断图是否正确的基础。

### 1. 实体、实体集与实体类型

一个**实体**是现实世界中可区分的对象，例如“编号为 D01 的心内科”或“工号为 1001 的医生”。同类实体的集合叫**实体集**（entity set），例如 `DEPARTMENT`、`DOCTOR`。在 E-R 图里画的是实体集，不是某条具体记录。

实体集通常应满足三个条件：

- 有稳定的身份：能用一个键区分同类实体；
- 可独立叙述：即使暂时没有发生某项业务，也有保存价值；
- 有自身属性或生命周期：例如科室可以先创建，医生可以先入职，患者可以先建档。

例如 `BedType` 在本题不是实体集，因为题目只要求记录床位的类型名称，没有给床位类型自己的编号、价格、护理规则或生命周期；它首先是 `BED` 的一个属性。将每个名词都画成矩形只会把概念模型画得支离破碎。

### 2. 强实体集与弱实体集

**强实体集**有自己的键属性，能够不依赖其他实体而在整个实体集中唯一标识。例如：

```text
DEPARTMENT: department_id
DOCTOR:     doctor_id
PATIENT:    patient_id
BED:        bed_id
```

所以它们画单线矩形，键属性名加实线下划线。

**弱实体集**没有足以全局唯一标识自己的完整键；它必须依靠一个拥有者实体的键，再加上自己的**部分键**（discriminator），才能被识别。弱实体集画双线矩形；拥有者与弱实体之间的标识联系画双线菱形；弱实体必须通过该标识联系参加到拥有者，所以弱实体到标识联系画双线。

本题中，若不额外发明一个全局的住院编号，`HOSPITALIZATION` 可以这样理解：`admission_no = 1` 只表示“某一位患者的第 1 次住院”，离开患者它没有唯一性。因此：

```text
PATIENT 的键：             patient_id
HOSPITALIZATION 的部分键： admission_no
住院记录的完整标识：        (patient_id, admission_no)
```

这正是弱实体的典型结构。请区分两个概念：

- **部分键不是主键。** `admission_no` 不能独立唯一标识一条住院记录。
- **弱实体不等于“表的主键是复合键”。** 有复合键的表不一定是弱实体；只有当身份依赖拥有者及标识联系时，才有弱实体语义。

若医院为每次住院分配全局唯一的 `admission_id`，`HOSPITALIZATION` 也可以建成强实体。这是另一种合理实现，但在题目没有提供住院 ID 的前提下，用弱实体和部分键更能展示教材要求的标识联系。

### 3. 联系集、联系属性和联系度

联系集（relationship set）描述实体集之间的关联，例如 `EMPLOYS` 表达科室与医生的归属，`ASSIGNED_TO` 表达住院记录与病床的分配。普通联系画单线菱形。

联系也可以有属性。若“医生负责某次住院”的联系还需要记录 `assigned_at`、`duty_role`，且这些属性只描述“这个医生负责这次住院”这一事实，就应把属性椭圆连接到 `ATTENDS` 菱形，而不是随便挂到医生或患者上。本题没有给出这类属性，因此六个联系菱形都不连接额外属性。

联系涉及多少个实体集称为**联系度**：

- 一元联系：同一实体集内部的联系，例如医生指导医生；
- 二元联系：两个实体集之间的联系。本题的大多数联系都是二元联系；
- 三元或更高元联系：三个或更多实体集共同决定一条事实。

不要把一个真正的三元联系随意拆成三条二元线。例如若业务事实是“某医生在某次住院中为某患者执行某种治疗”，能否拆开要看拆后能否保留原来的组合语义。本题将“患者、医生、病床、时间”收束到 `HOSPITALIZATION` 弱实体中，再分别与医生、病床关联，是因为“住院记录”本身就是有属性、可被识别的业务事件。

### 4. 映射基数约束：1:1、1:N、M:N

映射基数（mapping cardinality）描述一个实体**至多**可以在某联系里配对多少个对方实体：

| 类型 | 读法 | 例子 |
| ---- | ---- | ---- |
| 1:1 | 两端一个实体至多对应对方一个实体 | 若每个病房恰有一个专属护士长，可能是 1:1 |
| 1:N | 1 端一个实体可关联多个 N 端实体；N 端至多关联一个 1 端实体 | 一个科室有多个医生，一个医生只属于一个科室 |
| M:N | 两端实体都可以关联多个对方实体 | 若一位医生可参加多个医疗团队、一支团队也有多位医生 |

本题的 `Department—Doctor`、`Department—Sickroom`、`Sickroom—Bed`、`Patient—Hospitalization`、`Doctor—Hospitalization`、`Bed—Hospitalization` 均是 1:N。题目没有出现必须直接建成 M:N 联系的业务规则。

一个非常容易颠倒的判断方法是：先从一句话中找“一个 A 对应多个 B”，再把 `1` 写在 A 端、`N` 写在 B 端。比如“一个医生可负责多个患者的诊治”，在本文精确为“一个医生可负责多条住院记录”，所以 `DOCTOR` 是 1 端，`HOSPITALIZATION` 是 N 端。

### 5. 全参与约束和部分参与约束

参与约束（participation constraint）回答的不是“最多几个”，而是“是否至少要有一个”。两者绝不能混为一谈。

- **全参与**：实体集中的每个实体都必须至少参加一次联系，用实体与联系之间的双线表示。
- **部分参与**：实体集中的实体可以不参加联系，用单线表示。

本题可按下表判断：

| 实体集参与的联系 | 参与类型 | 理由 |
| ---------------- | -------- | ---- |
| `SICKROOM` 参与 `HAS_SICKROOM` | 全参与 | 每个病房只能属于一个科室，不能没有所属科室 |
| `DOCTOR` 参与 `EMPLOYS` | 全参与 | 一个医生只属于一个科室 |
| `BED` 参与 `CONTAINS_BED` | 全参与 | 每张病床只属于一个病房 |
| `HOSPITALIZATION` 参与 `HAS_ADMISSION` | 全参与 | 弱实体住院记录必须由患者拥有 |
| `HOSPITALIZATION` 参与 `ATTENDS` | 全参与 | 每次住院有一名主治医生 |
| `HOSPITALIZATION` 参与 `ASSIGNED_TO` | 全参与 | 每次住院使用一张床 |
| `PATIENT` 参与 `HAS_ADMISSION` | 部分参与 | 患者可以先建档、尚未住院 |
| `DOCTOR` 参与 `ATTENDS` | 部分参与 | 医生可以暂时没有负责的住院记录 |
| `BED` 参与 `ASSIGNED_TO` | 部分参与 | 空床是合法状态 |

对于 `DEPARTMENT` 是否全参与 `HAS_SICKROOM`、`EMPLOYS`，以及 `SICKROOM` 是否全参与 `CONTAINS_BED`，题干中的“有多个”可以有两种课堂解释：若解释为至少一个，画双线；若允许刚成立或暂未配置的对象为空，画单线。关键不是猜一个答案，而是在图下写清楚自己的业务假设。

### 6. 键、候选键、超键与外键

这些术语属于关系模型，但在从 E-R 图落表前必须分清：

- **超键**：能唯一标识一条元组的一组属性。`{patient_id, patient_name}` 当然能唯一标识患者，但它含有冗余属性。
- **候选键**：最小超键；删除其中任何一个属性就不再能唯一标识元组。`patient_id` 是 `PATIENT` 的候选键。
- **主键**：从候选键中选定、实际作为主标识使用的一个键。主键必须唯一且非空。
- **外键**：一个关系中的属性，其值必须引用另一关系的候选键或主键。`SICKROOM.department_id` 引用 `DEPARTMENT.department_id`。

在本题的弱实体方案中，`(patient_id, admission_no)` 是 `HOSPITALIZATION` 的候选键和主键；其中 `patient_id` 同时还是指向 `PATIENT` 的外键。这种“同一属性同时参与主键和外键”是弱实体转换后的正常结果，不是设计冲突。

## 三、从题目抽取实体集和属性

画联系之前，先把实体和属性分清楚。题目中的“所属科室”“所属病房”“主治医生”“床位”描述的是联系，不应直接当成孤立的普通属性画在任意实体旁边。

### 1. 五个强实体集

以下概念能独立存在，并且题目给出了明确 ID，应画成单线矩形：

1. `DEPARTMENT`（科室）
   - 键属性：`department_id`
   - 普通属性：`department_name`、`office_room`、`department_phone`
2. `SICKROOM`（病房）
   - 键属性：`sickroom_id`
   - 普通属性：`bed_capacity`、`room_location`
3. `BED`（病床）
   - 键属性：`bed_id`
   - 普通属性：`bed_type`
4. `DOCTOR`（医生）
   - 键属性：`doctor_id`
   - 普通属性：`doctor_name`、`birth_date`、`professional_title`、`education`、`joined_department_on`
5. `PATIENT`（患者）
   - 键属性：`patient_id`
   - 普通属性：`patient_name`、`gender`、`birth_date`

### 2. 为什么必须增加住院记录

题目把“床位、入院时间、入院原因、诊断结论、主治医生、出院时间、住院天数”列在患者信息中，但后面的业务规则又明确说的是“患者每次住院”。这两个描述合起来意味着：这些字段描述的是**患者的一次住院事件**，不是患者永久属性。

如果直接设计成：

```text
PATIENT(patient_id, patient_name, bed_id, doctor_id, admission_time, ...)
```

患者第二次住院时，第一次住院的数据就会被覆盖。因此，在 E-R 图中增加 `HOSPITALIZATION`（住院记录）是对题意的必要解释，不是随意扩展需求。

本文采用教材中的弱实体建模：

- `HOSPITALIZATION` 画双线矩形；
- 它由患者拥有，不能脱离患者独立确定身份；
- `admission_no` 是部分键，只在同一患者内部区分第几次住院；
- 入院时间、入院原因、诊断结论、出院时间等属于住院记录；
- 住院天数是虚线椭圆表示的派生属性。

如果老师允许增加全局 `admission_id`，也可以把住院记录画成强实体；但无论采用哪种键，都不能把一次住院错误地塞回 `PATIENT` 矩形。

## 四、逐步画出完整的 Chen E-R 图

下面的描述就是答题纸上的绘图施工说明。先放置实体和属性，再画联系；每画一条线，都同时标出基数和参与约束。

### 第一步：放置六个实体矩形

建议把五个强实体和一个弱实体摆成下面的布局：

```text
左上：DEPARTMENT          中上：SICKROOM          右上：BED
左下：DOCTOR              中下：PATIENT           右下：HOSPITALIZATION（双线矩形）
```

六个矩形中的键属性和普通属性如下。键属性名在实际图中要加下划线：

```text
DEPARTMENT
  _department_id_, department_name, office_room, department_phone

SICKROOM
  _sickroom_id_, bed_capacity, room_location

BED
  _bed_id_, bed_type

DOCTOR
  _doctor_id_, doctor_name, birth_date, professional_title,
  education, joined_department_on

PATIENT
  _patient_id_, patient_name, gender, birth_date

HOSPITALIZATION（双线矩形）
  _admission_no_, admission_time, admission_reason,
  admission_diagnosis, diagnosis_conclusion, discharge_time
```

`PATIENT` 还连接一个双线椭圆 `phone_number`；`HOSPITALIZATION` 还连接一个虚线椭圆 `stay_days`。

### 第二步：画科室与病房的联系

在 `DEPARTMENT` 和 `SICKROOM` 两个矩形之间画一个单线菱形，菱形中写 `HAS_SICKROOM`。两侧这样标记：

```text
[DEPARTMENT] 1 ----- <HAS_SICKROOM> ===== N [SICKROOM]
```

这里的 `=====` 仅用于文字模拟双线；实际图中是两条平行线。解释如下：

- 科室端标 `1`，病房端标 `N`。
- 一个科室可以有多个病房。
- 一个病房只能属于一个科室。
- `SICKROOM` 到菱形画双线，因为每个病房必须参加“属于某科室”的联系。
- 若把题目的“一个科室有多个病房”严格解释为至少一个，科室端也画双线；若允许新科室暂时没有病房，科室端画单线并理解为 `(0,N)`。

这条联系转换为关系模式后，才会在 `SICKROOM` 中出现 `department_id` 外键。概念图阶段不必把同一个 `department_id` 再作为普通椭圆重复画一遍。

### 第三步：画科室与医生的联系

在 `DEPARTMENT` 和 `DOCTOR` 之间画单线菱形 `EMPLOYS`：

```text
[DEPARTMENT] 1 ----- <EMPLOYS> ===== N [DOCTOR]
```

- 一个科室有多个医生，所以医生端是 `N`。
- 一个医生只属于一个科室，所以科室端是 `1`。
- `DOCTOR` 端画双线，因为每个医生必须参加“任职于某科室”的联系。
- 若要求每个科室至少有一个医生，科室端也画双线；若允许空科室，则画单线。

不要画 `DOCTOR` 直接属于 `SICKROOM` 的联系。题目只规定医生属于科室，没有规定医生属于某个具体病房。

### 第四步：画病房与病床的联系

在 `SICKROOM` 和 `BED` 之间画单线菱形 `CONTAINS_BED`：

```text
[SICKROOM] 1 ===== <CONTAINS_BED> ===== N [BED]
```

- 一个病房有多个病床，所以病床端标 `N`。
- 一个病床只能属于一个病房，所以病房是 `1` 端。
- 每张病床必须有所属病房，`BED` 到菱形画双线。
- 若每个病房必须至少登记一张床，`SICKROOM` 端也画双线；否则可用单线表示暂时为空。

### 第五步：给患者画联系电话多值属性

在 `PATIENT` 矩形旁画双线椭圆 `PHONE_NUMBER`：

```text
[PATIENT] ----- ((PHONE_NUMBER))
```

双线椭圆的含义是：一个患者对应零个、一个或多个电话号码；每个电话号码是患者这个实体的一个属性值。它不是一个新的强实体，也不是三个固定字段。关系转换时，才把它变为 `PATIENT_PHONE(patient_id, phone_number)`。

### 第六步：画患者与住院记录的弱实体联系

在 `PATIENT` 和 `HOSPITALIZATION` 之间画**双线菱形** `HAS_ADMISSION`，并把 `HOSPITALIZATION` 画成双线矩形：

```text
[PATIENT] 1 ===== <HAS_ADMISSION> ===== N [HOSPITALIZATION]
```

这一步是全图最重要的部分：

- 双线矩形表示 `HOSPITALIZATION` 是弱实体；
- 双线菱形表示 `HAS_ADMISSION` 是标识联系；
- 患者端标 `1`，住院记录端标 `N`；
- 一名患者可以有多次住院；
- 一条住院记录只属于一名患者；
- 住院记录到标识联系画双线，表示每条住院记录必须由一个患者拥有；
- `admission_no` 是部分键，只有和拥有者的 `patient_id` 合起来才唯一。

在弱实体矩形旁画椭圆 `admission_no`，并按照教材约定把它标记为部分键；纸面上可使用**虚线下划线**，或者在属性名旁明确写“partial key”，以区别于强实体的全局键。最终关系模式中的主键是 `(patient_id, admission_no)`。

### 第七步：画医生与住院记录的联系

在 `DOCTOR` 和 `HOSPITALIZATION` 之间画单线菱形 `ATTENDS`：

```text
[DOCTOR] 1 ----- <ATTENDS> ===== N [HOSPITALIZATION]
```

- 一个医生可以负责多条住院记录，因此住院记录端是 `N`。
- 一条住院记录有且只有一个主治医生，因此医生端是 `1`。
- `HOSPITALIZATION` 端画双线，表示每条住院记录必须有主治医生。

“负责多个患者”在加入住院记录实体后，准确地表达为“一个医生负责多条住院记录”；同一个患者的不同住院可以由不同医生负责，也可以由同一医生负责。

### 第八步：画病床与住院记录的联系

在 `BED` 和 `HOSPITALIZATION` 之间画单线菱形 `ASSIGNED_TO`：

```text
[BED] 1 ----- <ASSIGNED_TO> ===== N [HOSPITALIZATION]
```

- 一张病床可以在先后不同时间服务多条住院记录，所以病床端是 `1`，住院记录端是 `N`。
- 一条住院记录只使用一张病床，所以住院记录端画双线，且在该端标 `N`。
- `admission_time`、`discharge_time` 是住院记录的属性，因此这条 1:N 联系是“按时间先后复用”的 1:N，而不是允许同一时刻一床多人。

在图的旁边写附加语义约束：

```text
同一 bed_id 的住院时间区间不得重叠；
discharge_time 为空表示患者仍在院。
```

这个规则比较多条住院记录的时间区间，不能仅靠 `1:N` 标记或普通外键表达。

### 第九步：画住院记录属性

围绕双线矩形 `HOSPITALIZATION` 连接以下椭圆：

```text
(_admission_no_)          部分键
(admission_time)
(admission_reason)
(admission_diagnosis)
(diagnosis_conclusion)
(discharge_time)
 - - (stay_days) - -      虚线椭圆，派生属性
```

`stay_days` 的虚线表示它可由 `admission_time` 和 `discharge_time` 计算。若医院采用“出院日减入院日”的口径，公式是 `DATEDIFF(discharge_time, admission_time)`；若入院、出院当天都计入，则是该差值加 1。E-R 图只标出“派生”，具体计费口径应在业务规则中写明。

## 五、整张图的文字复原版

下面这份清单可以直接作为答题纸上的绘图检查表：

```text
实体集（矩形）：
  Department、Sickroom、Bed、Doctor、Patient
  Hospitalization（双线矩形，弱实体）

联系集（菱形）：
  Department 1:N Sickroom       HAS_SICKROOM
  Department 1:N Doctor         EMPLOYS
  Sickroom 1:N Bed              CONTAINS_BED
  Patient 1:N Hospitalization   HAS_ADMISSION（双线标识联系）
  Doctor 1:N Hospitalization    ATTENDS
  Bed 1:N Hospitalization       ASSIGNED_TO

属性：
  Department: _department_id_, department_name, office_room, department_phone
  Sickroom: _sickroom_id_, bed_capacity, room_location
  Bed: _bed_id_, bed_type
  Doctor: _doctor_id_, doctor_name, birth_date, professional_title,
          education, joined_department_on
  Patient: _patient_id_, patient_name, gender, birth_date,
           ((phone_number))
  Hospitalization: _admission_no_, admission_time, admission_reason,
                  admission_diagnosis, diagnosis_conclusion, discharge_time,
                  - - (stay_days) - -
```

实际画图时，`_name_` 表示在椭圆文字下方画下划线，`((name))` 表示双线椭圆，`- - (name) - -` 表示虚线椭圆。每个“从属实体”到其拥有者联系的连接线画双线：病房到科室、医生到科室、病床到病房、住院记录到患者/医生/病床。科室和病房是否也画双线，取决于是否把“有多个”解释成至少一个；答题时应在图下注明这个假设。

## 六、E-R 模型转换为关系模式

### 1. 本题使用的转换规则

1. 每个强实体集转换成一个关系，键属性成为主键。
2. 1:N 联系把 1 端主键放入 N 端作为外键；联系自身没有属性时不另建联系表。
3. 多值属性单独转换成一个关系，主键通常是“拥有者主键 + 属性值”。
4. 弱实体关系包含拥有者主键和部分键，两者共同构成主键。
5. 派生属性一般不作为普通存储列，而是在查询或视图中计算。

### 2. 关系模式

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

### 3. 主键和外键汇总

| 关系 | 主键 | 外键 |
| ---- | ---- | ---- |
| `department` | `department_id` | 无 |
| `sickroom` | `sickroom_id` | `department_id → department.department_id` |
| `bed` | `bed_id` | `sickroom_id → sickroom.sickroom_id` |
| `doctor` | `doctor_id` | `department_id → department.department_id` |
| `patient` | `patient_id` | 无 |
| `patient_phone` | `(patient_id, phone_number)` | `patient_id → patient.patient_id` |
| `hospitalization` | `(patient_id, admission_no)` | `patient_id → patient.patient_id`；`attending_doctor_id → doctor.doctor_id`；`bed_id → bed.bed_id` |

`attending_doctor_id` 和 `bed_id` 位于 `hospitalization`，而不是 `patient`。这是因为它们回答的是“这一次住院由谁负责、使用哪张床”，不是“这个患者永久属于谁、永久使用哪张床”。

## 七、关系数据库设计：函数依赖、范式与无损连接

E-R 图解决“有哪些实体和联系”，关系数据库设计继续解决“属性应该放在哪张关系中”。这是两层不同的问题：即使 E-R 图画对了，若在转换后的表里重复放置患者姓名、医生姓名、病房位置，更新异常仍然会出现。函数依赖、规范化和无损连接正是第 7 章要处理的主题。

### 1. 关系模式、关系实例与元组

一个关系模式是关系名及其属性集合，例如：

```text
PATIENT(patient_id, patient_name, gender, birth_date)
```

它规定表“可以有哪些列”；某一时刻表中实际保存的行构成一个关系实例；每一行称为元组（tuple）。关系模型使用集合语义：行没有天然顺序，列也不是靠显示位置而是靠属性名解释。因而“第一行患者”和“第 3 列床位”不是业务概念，`patient_id`、`bed_id` 才是。

关系模式设计的目标不是单纯把表拆得越多越好，而是在保留业务事实的前提下减少有害冗余，使插入、删除和更新不产生矛盾。

### 2. 函数依赖：由业务语义确定属性

在同一关系模式中，若属性集 `X` 的值确定后，属性集 `Y` 的值也只能有一个确定值，则称存在**函数依赖**：

```text
X -> Y
```

读作“X 函数决定 Y”。它不是数学函数调用，也不是“当前样本数据碰巧没有重复”；它是业务规则。例如患者 ID 是唯一标识，则：

```text
patient_id -> patient_name, gender, birth_date
```

医生 ID 唯一标识医生，则：

```text
doctor_id -> doctor_name, birth_date, professional_title,
             education, department_id, joined_department_on
```

病床 ID 唯一标识病床，则：

```text
bed_id -> sickroom_id, bed_type
```

反过来，`patient_name -> patient_id` 通常不成立，因为可能同名；`bed_id -> attending_doctor_id` 也不成立，因为同一床在不同住院记录中可由不同医生负责。判断函数依赖必须根据题目规定的唯一性和业务含义，而不是根据一小份测试数据推测。

#### 属性闭包与候选键

给定一组函数依赖，属性集 `X` 能推出的所有属性称为 `X` 的**属性闭包**，记为 `X+`。计算闭包的过程是：先把 `X` 放入结果；只要有一条依赖左部已包含在结果中，就把右部加入；直到不能再加入属性。

例如在住院关系中：

```text
H(patient_id, admission_no, attending_doctor_id, bed_id,
  admission_time, admission_reason, admission_diagnosis,
  diagnosis_conclusion, discharge_time)

(patient_id, admission_no) -> attending_doctor_id, bed_id,
  admission_time, admission_reason, admission_diagnosis,
  diagnosis_conclusion, discharge_time
```

因此 `(patient_id, admission_no)+` 包含 `H` 的全部属性，是超键；去掉 `patient_id` 后，`admission_no` 只是在单个患者内部编号，不能标识全表记录；去掉 `admission_no` 后，一个患者可能有多次住院。因此 `(patient_id, admission_no)` 是候选键，也被选为主键。

### 3. 完全函数依赖、部分函数依赖与传递函数依赖

这些概念通常以一个复合候选键为背景，是判断 2NF、3NF 的关键。

**完全函数依赖**：`Y` 依赖于复合键 `X`，且不能只依赖 `X` 的任何真子集。例如：

```text
(patient_id, admission_no) -> admission_time, bed_id,
                            attending_doctor_id, admission_reason
```

`admission_time`、本次床位和本次主治医生都必须知道“哪个患者的第几次住院”才能确定；只知道患者 ID 或只知道住院序号都不够，所以是对复合键的完全函数依赖。

**部分函数依赖**：非主属性只依赖复合候选键的一部分，而不依赖整个复合键。假设错误地把患者姓名放入上面的住院关系：

```text
(patient_id, admission_no) -> patient_name
patient_id -> patient_name
```

其中 `patient_name` 只依赖 `patient_id`，而 `patient_id` 是复合键的真子集，所以前一条表面上的依赖包含了部分函数依赖。这会使同一患者每住院一次就重复保存一次姓名；患者改名时，历史住院行可能出现不一致。

**传递函数依赖**：若 `X -> Y`、`Y -> Z`，且 `Y` 不是候选键中的属性，则 `X -> Z` 是经由 `Y` 的传递依赖。假设把医生姓名也塞进住院关系：

```text
(patient_id, admission_no) -> attending_doctor_id
attending_doctor_id -> doctor_name, professional_title
```

于是住院主键传递地决定医生姓名和职称。它们应留在 `DOCTOR`，住院表只保留 `attending_doctor_id`。同理，若把病房位置放到住院表中：

```text
bed_id -> sickroom_id
sickroom_id -> room_location
```

住院主键会通过 `bed_id`、`sickroom_id` 传递地决定 `room_location`。这也是不应复制病房位置的原因。

### 4. 更新、插入和删除异常为什么出现

设有一张错误的“大住院表”：

```text
BAD_STAY(
  patient_id, admission_no, patient_name, patient_birth_date,
  attending_doctor_id, doctor_name, doctor_title,
  bed_id, sickroom_id, room_location,
  admission_time, discharge_time
)
```

它的键为 `(patient_id, admission_no)`。其中患者、医生、病房事实随着每次住院重复。会出现三类经典异常：

- **更新异常**：医生职称改变时，必须修改该医生所有历史住院行；漏改一行，就出现两个职称。
- **插入异常**：医院想先登记一张新病床，但若表要求必须填写患者和住院序号，就无法插入尚未使用的病床。
- **删除异常**：删除某患者的最后一次住院记录时，可能连同患者姓名、出生日期等本应保留的建档事实一起丢失。

将它拆分为 `PATIENT`、`DOCTOR`、`SICKROOM`、`BED`、`HOSPITALIZATION` 等关系，正是在消除这些无约束重复。这里的拆分不是为了形式上的“表多”，而是让每个事实只在其权威关系中存一次。

### 5. 第一、第二、第三范式与 BCNF

范式不是孤立的名词清单，而是对函数依赖提出逐步更强的限制。

#### 第一范式：属性值应是原子的

1NF 要求每个属性值是不可再分的单一值，而不是重复组或列表。`PATIENT(phone1, phone2, phone3)` 不是理想设计；`PATIENT(phone_numbers = '138...,139...')` 也不是原子值。使用：

```text
PATIENT(patient_id, ...)
PATIENT_PHONE(patient_id, phone_number)
```

才使每个号码成为一个独立、可约束、可查询的值。注意，“原子”取决于应用语义；电话号码对本题无需拆成每一位数字，因此 `VARCHAR` 是原子的合适表示。

#### 第二范式：消除对候选键的部分依赖

2NF 要求关系先满足 1NF，并且每个非主属性都完全函数依赖于每个候选键。若 `HOSPITALIZATION` 含有 `patient_name`，键是 `(patient_id, admission_no)`，而 `patient_id -> patient_name`，则违反 2NF。把患者信息拆到 `PATIENT` 后，住院表剩下的住院属性依赖完整复合键，便消除了该部分依赖。

当关系的所有候选键都是单属性时，不会有“依赖于复合键真子集”的可能，2NF 通常自然满足；但仍可能存在传递依赖，不能因此跳过 3NF 检查。

#### 第三范式：消除非主属性之间的传递依赖

3NF 的直观目标是：非主属性不应通过另一个非主属性依赖于键。严格地说，对每个非平凡函数依赖 `X -> A`，至少应满足以下之一：

- `X` 是超键；
- `A` 是主属性，即它属于某个候选键。

例如在住院表中放 `doctor_name`，存在 `attending_doctor_id -> doctor_name`，而 `attending_doctor_id` 不是该表的超键，`doctor_name` 也不是主属性，便不符合 3NF。将医生描述属性放入 `DOCTOR`，住院表保留医生外键，能消除这种传递依赖。

#### BCNF：更严格的“决定因素必须是超键”

BCNF（Boyce-Codd Normal Form）要求每一个非平凡函数依赖 `X -> Y` 的决定因素 `X` 都是超键。它比 3NF 更严格，能消除更多异常；但某些分解可能无法同时保持全部函数依赖。教学与工程中常在“更强的去冗余”与“依赖保持、查询便利”之间权衡，而不是不加判断地追求最高范式。

本题的核心关系在清晰定义键和外键后可达到 3NF，通常也符合 BCNF：例如 `PATIENT` 中 `patient_id` 是决定其他属性的超键；`DOCTOR` 中 `doctor_id` 是决定其他属性的超键；`HOSPITALIZATION` 中复合主键决定本次住院属性。若再声明其他业务唯一性，例如“科室名称唯一”，必须把相应依赖 `department_name -> department_id` 一并纳入分析。

### 6. 分解的两个质量标准：无损连接与依赖保持

把大关系拆成小关系之前，至少要问两个问题：连接回去会不会凭空造出数据？原有依赖能否只检查各张子表就得到保证？

#### 无损连接分解

把关系 `R` 分解成 `R1`、`R2` 后，若对任意满足函数依赖集合 `F` 的合法实例，都有：

```text
R = πR1(R) ⋈ πR2(R)
```

则称该分解是**无损连接**（lossless join）。意思是先投影拆表，再自然连接回来，既不丢失原来的元组，也不产生虚假的元组。

对于二元分解，一个常用判定条件是：

```text
(R1 ∩ R2) -> R1    或    (R1 ∩ R2) -> R2
```

在依赖集合 `F` 下成立即可。也就是说，两张表的公共属性必须能函数决定其中至少一张表的全部属性。

以患者信息从住院大表中拆出为例：

```text
R(patient_id, admission_no, patient_name, admission_time, ...)

R1 = PATIENT(patient_id, patient_name, ...)
R2 = HOSPITALIZATION(patient_id, admission_no, admission_time, ...)
```

两表交集是 `patient_id`，而 `patient_id -> PATIENT` 的全部属性。因此 `patient_id` 能决定 `R1`，该二元分解无损。连接时，每条住院记录会准确找回所属患者，而不会制造不存在的住院。

反例更能说明问题。若把一个事实关系错误拆为：

```text
R(patient_id, doctor_id, bed_id)
R1(patient_id, doctor_id)
R2(doctor_id, bed_id)
```

原关系只有两行：

```text
(P1, D1, B1)
(P2, D1, B2)
```

投影并按 `doctor_id` 连接会额外得到 `(P1, D1, B2)` 和 `(P2, D1, B1)`。它们是**伪元组**，说明这不是无损分解。根本原因是公共属性 `doctor_id` 不能决定 `R1` 或 `R2`；一位医生可以负责多位患者，也可以在不同住院中对应不同床位。

#### 依赖保持

分解后，若原依赖集 `F` 中的约束能通过各子关系上的函数依赖联合推出，而不必把多张表连接起来检查，则称分解**保持依赖**（dependency preserving）。形式上，若：

```text
(F1 ∪ F2 ∪ ... ∪ Fn)+ = F+
```

其中 `Fi` 是投影到关系 `Ri` 上的依赖集，则分解保持依赖。

例如把 `patient_id -> patient_name, birth_date` 放在 `PATIENT`，把 `doctor_id -> doctor_name, professional_title` 放在 `DOCTOR`，每个依赖都可在自己的表内以主键/唯一约束检查，属于直观的依赖保持设计。

无损连接与依赖保持是不同目标：无损保证不造假数据，依赖保持保证约束检查不必做昂贵连接。3NF 综合算法常能得到同时无损且依赖保持的分解；BCNF 分解有时会为更强规范化而牺牲部分依赖保持。没有这种取舍意识的“拆表”，只是机械操作。

### 7. 回到医院案例：为什么当前关系划分合理

下面用函数依赖再检查一次本题设计：

```text
department_id -> department_name, office_room, department_phone
sickroom_id   -> department_id, bed_capacity, room_location
bed_id        -> sickroom_id, bed_type
doctor_id     -> department_id, doctor_name, birth_date,
                 professional_title, education, joined_department_on
patient_id    -> patient_name, gender, birth_date
(patient_id, admission_no) -> attending_doctor_id, bed_id,
  admission_time, admission_reason, admission_diagnosis,
  diagnosis_conclusion, discharge_time
```

这些决定关系的左部在相应关系中都是主键或超键。患者的基本事实只在 `PATIENT` 保存，医生的基本事实只在 `DOCTOR` 保存，病房位置只在 `SICKROOM` 保存，某次住院才发生的事实只在 `HOSPITALIZATION` 保存。连接查询可以组合它们，但组合查询的结果不代表应把这些列永久复制进一张大表。

从 E-R 图到关系模式再到函数依赖分析，三步分别回答：

```text
E-R 图：有哪些对象、对象如何联系？
关系模式：这些对象如何用键和外键落成表？
函数依赖与范式：属性是否放在了正确的表中，拆分能否无损且可维护？
```

## 八、完整性约束分析

### 1. 实体完整性

所有主键必须唯一且非空：五个强实体使用各自 ID，`PATIENT_PHONE` 使用 `(patient_id, phone_number)`，弱实体使用 `(patient_id, admission_no)`。

### 2. 参照完整性

外键必须引用已存在的主键：病房引用科室，医生引用科室，病床引用病房，电话引用患者，住院记录分别引用患者、医生和病床。

### 3. 值域和业务唯一性

床位数应大于 0；性别只能使用约定代码；出院时间为空或不早于入院时间；同一科室中房间位置可以设置唯一约束。电话号码使用字符类型，因为它是标识符，不参与算术，可能含国家码、前导零和分隔符。

### 4. 不能只靠普通外键表达的规则

以下规则涉及多行或多张表：

- 一个病房实际登记的床位数不得超过 `bed_capacity`；
- 同一张床的住院区间不得重叠；
- 若医院规定主治医生必须与病床所属科室一致，需要跨表比较；
- 患者是否允许同时存在多条未出院记录，需要检查其他住院行。

这些规则应在事务中锁定相关行后检查，或使用触发器、当前占床关系和统一服务入口实现。不要把跨行时间比较假装成一条普通 `CHECK` 约束。

## 九、MySQL 8.0 建表 SQL

下面使用弱实体方案，住院记录主键为 `(patient_id, admission_no)`。`M`、`F`、`U` 只是示例性别代码，实际医院可以替换为自己的字典表。

```sql
CREATE DATABASE IF NOT EXISTS hospital_management
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE hospital_management;

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
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE bed (
  bed_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sickroom_id BIGINT UNSIGNED NOT NULL,
  bed_type VARCHAR(30) NOT NULL,
  PRIMARY KEY (bed_id),
  KEY idx_bed_sickroom (sickroom_id),
  CONSTRAINT fk_bed_sickroom
    FOREIGN KEY (sickroom_id) REFERENCES sickroom (sickroom_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
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
    ON UPDATE RESTRICT ON DELETE RESTRICT
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
    ON UPDATE RESTRICT ON DELETE CASCADE
) ENGINE = InnoDB;

CREATE TABLE hospitalization (
  patient_id BIGINT UNSIGNED NOT NULL,
  admission_no SMALLINT UNSIGNED NOT NULL,
  attending_doctor_id BIGINT UNSIGNED NOT NULL,
  bed_id BIGINT UNSIGNED NOT NULL,
  admission_time DATETIME NOT NULL,
  admission_reason VARCHAR(500) NOT NULL,
  admission_diagnosis VARCHAR(500) NULL,
  diagnosis_conclusion TEXT NULL,
  discharge_time DATETIME NULL,
  PRIMARY KEY (patient_id, admission_no),
  KEY idx_hospitalization_doctor_time
    (attending_doctor_id, admission_time),
  KEY idx_hospitalization_bed_time (bed_id, admission_time),
  CONSTRAINT ck_hospitalization_time
    CHECK (discharge_time IS NULL OR discharge_time >= admission_time),
  CONSTRAINT fk_hospitalization_patient
    FOREIGN KEY (patient_id) REFERENCES patient (patient_id)
    ON UPDATE RESTRICT ON DELETE CASCADE,
  CONSTRAINT fk_hospitalization_doctor
    FOREIGN KEY (attending_doctor_id) REFERENCES doctor (doctor_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT,
  CONSTRAINT fk_hospitalization_bed
    FOREIGN KEY (bed_id) REFERENCES bed (bed_id)
    ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE = InnoDB;
```

住院天数不作为可手工修改的普通列保存。若采用“出院日减入院日”的口径，可以使用视图：

```sql
CREATE VIEW v_hospitalization_detail AS
SELECT
  h.patient_id,
  h.admission_no,
  p.patient_name,
  h.attending_doctor_id,
  d.doctor_name AS attending_doctor_name,
  h.bed_id,
  h.admission_time,
  h.discharge_time,
  CASE
    WHEN h.discharge_time IS NULL THEN NULL
    ELSE DATEDIFF(h.discharge_time, h.admission_time)
  END AS stay_days,
  h.admission_reason,
  h.admission_diagnosis,
  h.diagnosis_conclusion
FROM hospitalization AS h
JOIN patient AS p ON p.patient_id = h.patient_id
JOIN doctor AS d ON d.doctor_id = h.attending_doctor_id;
```

## 十、最容易失分的五个地方

### 1. 把住院信息全画到患者旁边

这样无法保存患者多次住院。正确做法是增加弱实体 `Hospitalization`，通过双线标识联系连接到 `Patient`。

### 2. 把外键当成概念图中的普通属性

在 Chen 图中先画“科室—病房”“科室—医生”“病房—病床”等联系；`department_id`、`sickroom_id` 是关系模式转换后落到 N 端的外键。

### 3. 把多值电话画成多个固定字段

电话是双线椭圆；转换后才是 `PATIENT_PHONE` 关系。

### 4. 把住院天数画成普通实线椭圆

它是由时间计算的派生属性，应该用虚线椭圆表示，并在关系模式中按需计算。

### 5. 只标 `1:N`，不画参与约束

`1:N` 说明最大对应数量，双线/单线才说明必须参加还是可以缺席。完整的 E-R 图不能省略这部分语义。

## 十一、按作业四问归纳

**（1）E-R 模型。** 画五个强实体 `Department`、`Sickroom`、`Bed`、`Doctor`、`Patient`，一个依赖患者的弱实体 `Hospitalization`；画 `HAS_SICKROOM`、`EMPLOYS`、`CONTAINS_BED`、`HAS_ADMISSION`、`ATTENDS`、`ASSIGNED_TO` 六个联系；给实体连接键属性和普通属性；把患者联系电话画成双线椭圆，把住院天数画成虚线椭圆；在联系两端标 `1:N`，在必需参与的一端画双线。

**（2）关系模式。** 转换得到 `DEPARTMENT`、`SICKROOM`、`BED`、`DOCTOR`、`PATIENT`、`PATIENT_PHONE`、`HOSPITALIZATION` 七个关系。

**（3）主码和外码。** 强实体使用各自 ID 为主码；`PATIENT_PHONE` 的主码为 `(patient_id, phone_number)`；弱实体 `HOSPITALIZATION` 的主码为 `(patient_id, admission_no)`。外码分别表达病房到科室、医生到科室、病床到病房、电话到患者，以及住院记录到患者、医生和病床的引用。

**（4）约束和 SQL。** 用 `PRIMARY KEY` 保证实体完整性，用 `FOREIGN KEY` 保证参照完整性，用 `NOT NULL` 表达必填参与，用 `CHECK` 表达值域和时间先后，用 `UNIQUE` 表达业务唯一性；床位时间区间不重叠、床位容量等跨行规则则需要事务、触发器或额外状态关系。

完整的教材式 E-R 设计，必须同时回答四个问题：**画了哪些实体、实体之间通过什么联系相连、每端的基数是多少、哪一端是全参与**。如果只列出表名和字段，却没有把矩形、菱形、椭圆、双线和基数的语义说清楚，严格来说还没有完成 E-R 图设计。
