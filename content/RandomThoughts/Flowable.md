+++
date = '2026-02-26T18:07:55+08:00'
draft = false
title = 'Flowable'
+++

## 一、Flowable 整体可以分为哪几部分？

从工程角度看，**一个完整的 Flowable 系统分为 5 个层次**

```
用户
 ↓
流程设计层（怎么画流程）
 ↓
流程引擎层（Flowable Engine）
 ↓
业务系统代码（你写的 Java）
 ↓
数据库（MySQL）
```

## 二、怎么设置流程？

可以通过编写 XML 文件定义业务流程。但是在**真实项目里，我感觉 99% 的人不手写 BPMN XML**

下面介绍一些常用的流程设计方式

### 方式一：流程设计器

- Flowable Modeler（官方）
- Camunda Modeler（也能画 Flowable BPMN）
- Web 流程设计器（很多公司自己做）

用户看到的是：

- 拖拽开始节点
- 拖拽审批节点
- 拖拽条件分支
- 选“谁审批”“什么条件”

**最终保存的仍然是 BPMN XML，只是用户看不到**

### 方式二：管理员配置流程（配置型系统）

比如：

- 审批人 = 部门负责人
- 审批条件 = 金额 > 10000
- 抄送人 = HR

这些配置：

- 存数据库
- 在发布流程时 -> 注入到 BPMN 模型

### 方式三：手写 XML

很少使用

## 三、那 BPMN XML 在系统里到底干嘛？

一句话：

> **BPMN XML 是流程的“可执行源码”**

Flowable 引擎只认这个。

### 生命周期：

```
流程设计器
  ↓
生成 BPMN XML
  ↓
RepositoryService 部署
  ↓
Flowable 引擎解析并存库
```

## 四、后端代码在 Flowable 里充当什么角色？

这是最关键的一层。

> **后端代码充当流程引擎和真实业务系统的桥梁**

后端主要干 6 件事

#### 部署流程

```java
repositoryService.createDeployment()
    .addClasspathResource("leave.bpmn20.xml")
    .deploy();
```

#### 启动流程

```java
runtimeService.startProcessInstanceByKey(
    "leaveProcess", businessKey, variables);
```

通常在：

- 提交表单
- 创建业务单据时

#### 处理用户任务

```java
taskService.complete(taskId, variables);
```

比如：

- 审批通过
- 审批驳回
- 填写审批意见

#### 绑定业务数据

```
businessKey = "leave:12345";
```

把流程实例和你的 **业务表主键** 关联起来

#### 查询流程进度

```java
taskService.createTaskQuery()
    .processInstanceId(pid)
    .list();
```

#### 权限 & 用户体系对接

Flowable 本身不管怎么登录，不管用什么用户表

后端要做的事是：

- 把系统里的 userId -> Flowable 的 assignee
- 把部门 / 角色 -> candidateGroup

## 五、MySQL 数据库存的到底是什么？

## Flowable 会建一整套表

### 流程定义 & 部署

| 表                | 说明     |
| ----------------- | -------- |
| ACT_RE_DEPLOYMENT | 流程部署 |
| ACT_RE_PROCDEF    | 流程定义 |
| ACT_RE_MODEL      | 流程模型 |

用来记录 **流程长什么样**

### 正在运行的流程

| 表               | 说明         |
| ---------------- | ------------ |
| ACT_RU_EXECUTION | 流程执行节点 |
| ACT_RU_TASK      | 当前待办任务 |
| ACT_RU_VARIABLE  | 流程变量     |

用于记录 **流程现在跑到哪**

### 已完成的流程

| 表              | 说明         |
| --------------- | ------------ |
| ACT_HI_PROCINST | 历史流程实例 |
| ACT_HI_TASKINST | 历史任务     |
| ACT_HI_ACTINST  | 历史节点     |

用于记录 **流程跑过什么**。

> Flowable 数据库不存业务数据，只存流程状态、节点、变量、轨迹。

## Flowable 是如何和用户访问的业务系统关联的？

这是靠 **3 个关键机制**：

#### businessKey

```java
runtimeService.startProcessInstanceByKey(
    "leaveProcess", "leave:12345"
);
```

通过在流程实例中保存业务主键，在需要时通过业务主键迅速关联所需数据

#### assignee / candidateGroup

```java
taskService.createTaskQuery()
    .taskAssignee(userId)
    .list();
```

把流程任务映射到真实用户

#### 流程变量

```java
variables.put("amount", 12000);
variables.put("deptId", 10);
```

流程根据业务数据走不同分支

## 怎么查询流程走到哪一步了？

#### 当前在哪个节点？

```java
taskService.createTaskQuery()
    .processInstanceId(pid)
    .list();
```

#### 走过哪些步骤？

```java
historyService.createHistoricActivityInstanceQuery()
    .processInstanceId(pid)
    .orderByHistoricActivityInstanceStartTime()
    .asc()
    .list();
```

## 一个支持自定义流程的后台系统，整体是怎么分层的？

真实系统基本是这样

```text
【流程管理员 / 业务管理员】
        ↓
前端流程设计器（拖拽）
        ↓
后端流程管理 API
        ↓
Flowable RepositoryService（部署流程）
        ↓
流程定义（可启动）

---------------------------------

【普通用户】
        ↓
业务页面（发起流程）
        ↓
后端业务 API
        ↓
Flowable RuntimeService（启动流程）
```

**设计流程和发起流程是两个完全不同的阶段和角色**

## 流程什么时候变成可启动的？

### 关键动作：**部署**

```java
repositoryService.createDeployment()
    .addString("leave.bpmn20.xml", bpmnXml)
    .deploy();
```

部署完成后：

- Flowable 生成 **流程定义**
- 有 `processDefinitionId`
- 状态 = active

**此时流程才真正上线**

## 那普通用户是如何发起流程的？

#### 用户看到什么？

比如：

- 请假申请
- 费用报销
- 采购申请

本质是 **一个业务表单**

#### 用户点提交时，后端做了什么？

```java
runtimeService.startProcessInstanceByKey(
    "leaveProcess",
    "leave:12345",   // businessKey
    variables
);
```

这一刻发生了什么？

- 创建一个流程实例
- 绑定业务数据
- 流程走到第一个节点
- 生成第一条待办任务

所以你要记住这个关系

```text
流程定义（模板） —— 可复用
流程实例（一次申请） —— 每次创建
```

## 为什么要区分流程定义和流程实例？

这是审批系统能跑起来的核心原因。

- 流程定义：
  - 管理员配置
  - 版本化
  - 可升级
- 流程实例：
  - 普通用户发起
  - 一次一条
  - 走完就结束

**这和类 vs 对象是一个关系**

### 前端通常需要哪些流程相关 API？

#### 流程管理

```http
POST   /process/model/save
POST   /process/deploy
GET    /process/list
GET    /process/xml
```

#### 发起流程

```http
POST   /process/start
```

#### 我的待办 / 已办

```http
GET    /task/todo
GET    /task/done
```

#### 流程进度

```http
GET    /process/trace/{businessKey}
```

## 为什么企业一定要有流程分类表？

因为 **流程在企业里不是技术对象，而是管理对象**。如果没有流程分类

- 流程越来越多（几十 / 上百）
- 用户不知道该从哪里发起
- 权限不好控
- 运营人员无法管理

Flowable 原生的 `ACT_RE_PROCDEF` **完全不够用**

## 企业级流程管理的典型分层设计

一个成熟的流程系统，**至少分 4 层**：

```text
【流程运营层】  ← 你看到的流程分类表就在这
【流程定义层】
【流程运行层】
【流程引擎层（Flowable）】
```

### 流程运营层

#### 流程分类表

这是 **企业几乎必定存在的一张表**。

```sql
process_category
-----------------------------
id
category_code
category_name
parent_id
sort
status
remark
```

它解决了

- 流程分组（如：人事 / 财务 / 行政 / IT）
- 前端发起页分栏目展示
- 权限隔离（部门只能看到自己的流程）
- 运营统计（哪个分类流程用得最多）

**这张表是给人看的，不是给引擎看的**

#### 流程定义管理表

```sql
process_definition_ext
-----------------------------
id
process_key
process_name
category_id
version
status
icon
form_id
deploy_id
remark
```

注意：

- `process_key` 对应 Flowable
- `category_id` 对应你说的分类表
- `deploy_id` 对应 Flowable 的 deployment

**Flowable 只存流程能不能跑，企业表存“流程怎么管**

## 流程定义层（设计 & 发布）

这一层解决的问题是：**流程是谁设计的、怎么设计的、是否发布**

典型能力：

- 流程建模（前端拖拽）
- 保存草稿
- 发布流程
- 版本升级 / 回滚
- 禁用流程

发布时调用：

```java
repositoryService.createDeployment()
    .addString("xxx.bpmn20.xml", xml)
    .deploy();
```

## 流程运行层

这是普通用户感知到的部分：

- 发起流程
- 审批流程
- 查看进度
- 查看历史

> **流程实例 ≠ 业务数据**

所以一定会有：

业务表

```sql
leave_request
-----------------
id
user_id
days
status
```

流程绑定

```java
businessKey = "leave:" + leaveId;
```

通过 `businessKey` 把 **流程实例** 和 **业务数据** 绑定

## 流程引擎层

Flowable 在企业里只负责三件事：

| 能力     | 说明         |
| -------- | ------------ |
| 流程执行 | 节点流转     |
| 任务管理 | 待办 / 已办  |
| 轨迹记录 | 走过哪些节点 |

### Flowable 数据库里存什么？

- 流程跑到哪一步
- 当前任务是谁
- 流程变量
- 历史轨迹

**不存业务含义、不存分类、不存权限**

## Flowable 的核心类总览

Flowable 的 API 设计非常清晰：**所有能力都通过 Service 暴露**。

### RepositoryService（流程定义 / 模型 / 部署）

**管流程长什么样**

常用场景

- 部署流程
- 查询流程定义
- 管理模型（Model）

核心方法

```java
// 部署流程（BPMN XML -> 可执行流程）
repositoryService.createDeployment()
    .addClasspathResource("processes/leave.bpmn20.xml")
    .deploy();
// 查询流程定义
repositoryService.createProcessDefinitionQuery()
    .processDefinitionKey("leave")
    .latestVersion()
    .singleResult();
// 查询模型（流程草稿）
repositoryService.createModelQuery().list();
```

### RuntimeService（流程实例）

常用场景

- 启动流程
- 查询流程实例
- 操作流程变量

核心方法

```java
// 启动流程
runtimeService.startProcessInstanceByKey(
    "leaveProcess",
    "leave:1001",   // businessKey
    variables
);
// 查询运行中的流程
runtimeService.createProcessInstanceQuery()
    .processInstanceBusinessKey("leave:1001")
    .singleResult();
```

> 在这里可以通过业务 ID 快速查到相应的流程实例。

### TaskService（用户任务）

**管人怎么审批**

常用场景

- 查询我的待办
- 认领任务
- 完成任务

核心方法

```java
// 我的待办
taskService.createTaskQuery()
    .taskAssignee(userId)
    .list();
// 组任务（候选组）
taskService.createTaskQuery()
    .taskCandidateGroup("finance")
    .list();
// 认领任务
taskService.claim(taskId, userId);
// 完成任务
taskService.complete(taskId, variables);
```

> 在 **Flowable** 里，一个任务是怎么变成某个用户的代办的？

代办任务 = Flowable 在数据库里生成了一条任务记录，并把它关联到某个用户或候选人。

##### 任务是怎么产生的？

当流程执行到一个：

```java
UserTask（用户任务节点）
```

Flowable 会做 3 件事：

1. 在运行时任务表插入一条记录
2. 计算该任务的办理人
3. 记录任务与用户的关系

##### 核心表结构

Flowable 的运行时表：

| 表名                | 作用              |
| ------------------- | ----------------- |
| ACT_RU_TASK         | 运行时任务表      |
| ACT_RU_EXECUTION    | 执行实例          |
| ACT_RU_IDENTITYLINK | 任务与用户/组关系 |
| ACT_RU_VARIABLE     | 变量表            |

##### 任务如何和用户关联？

关键在：

```sql
ACT_RU_TASK
ACT_RU_IDENTITYLINK
```

###### 情况 1：指定办理人（assignee）

比如流程定义里写：

```xml
<userTask id="approve" flowable:assignee="zhangsan" />
```

Flowable 会：

- 在 ACT_RU_TASK 表中：
  - ASSIGNEE_ = zhangsan

此时：

> 这条任务直接属于 zhangsan

查询代办时：

```sql
SELECT * FROM ACT_RU_TASK WHERE ASSIGNEE_ = 'zhangsan';
```

###### 情况 2：候选人（candidateUser）

```xml
flowable:candidateUsers="zhangsan,lisi"
```

Flowable 会：

- 在 ACT_RU_IDENTITYLINK 表插入记录

类似：

| TASK_ID_ | USER_ID_ | TYPE_     |
| -------- | -------- | --------- |
| 123      | zhangsan | candidate |
| 123      | lisi     | candidate |

此时任务是：

> 共享任务

谁领取（claim）了，ASSIGNEE_ 才会被填上。

###### 情况 3：候选组（candidateGroup）

```xml
flowable:candidateGroups="manager"
```

插入：

| TASK_ID_ | GROUP_ID_ | TYPE_     |
| -------- | --------- | --------- |
| 123      | manager   | candidate |

然后：

查询时：

```sql
SELECT * FROM ACT_RU_TASK t
JOIN ACT_RU_IDENTITYLINK i
ON t.ID_ = i.TASK_ID_
WHERE i.GROUP_ID_ IN (当前用户所属组)
```

##### 为什么发布后就成代办？

其实没有发布这个动作。

真正发生的是：

流程执行到 UserTask 节点时：

```text
流程引擎自动创建任务
↓
根据表达式解析办理人
↓
写入数据库
```

你的系统里的代办列表：

本质就是：

```text
查询 ACT_RU_TASK
```

完整链路：

```text
启动流程
   ↓
执行到 UserTask
   ↓
生成 ACT_RU_TASK 记录
   ↓
生成 ACT_RU_IDENTITYLINK 关联
   ↓
前端查询当前用户相关任务
   ↓
显示为“代办”
```

### HistoryService（历史数据）

常用场景

- 查看审批记录
- 查看流程轨迹
- 已办列表

核心方法

```java
// 流程历史
historyService.createHistoricProcessInstanceQuery()
    .processInstanceId(pid)
    .singleResult();
// 节点轨迹
historyService.createHistoricActivityInstanceQuery()
    .processInstanceId(pid)
    .orderByHistoricActivityInstanceStartTime()
    .asc()
    .list();
```

## Flowable 里有哪些核心数据承载对象

从 **流程设计 -> 运行 -> 结束** 的生命周期看，Flowable 主要靠 **9 类核心对象** 来承载中间数据。

### 一、设计与部署阶段（Repository 层）

#### Model

**类：**

```java
org.flowable.engine.repository.Model
```

**承载内容：**

- 流程模型
- 模型的 `metaInfo`
- `key / name / category / version`

**数据库表：**

- `ACT_RE_MODEL`

**流程设计阶段的载体**

#### Deployment

**类：**

```java
org.flowable.engine.repository.Deployment
```

**承载内容**

- 一次部署的元信息
- 部署时间
- 部署名

**数据库表：**

- `ACT_RE_DEPLOYMENT`

**发布动作的载体**

#### ProcessDefinition

**类：**

```java
org.flowable.engine.repository.ProcessDefinition
```

**承载内容：**

- 一个可执行流程模板
- `processDefinitionKey`
- 版本号
- category

**数据库表：**

- `ACT_RE_PROCDEF`

**流程模板**

### 运行阶段（Runtime 层）

 #### ProcessInstance

**类：**

```java
org.flowable.engine.runtime.ProcessInstance
```

**承载内容：**

- 一次流程运行实例
- 当前执行状态
- `businessKey`

**数据库表：**

- `ACT_RU_EXECUTION`

**流程对象**

#### Execution

**类：**

```java
org.flowable.engine.runtime.Execution
```

**承载内容：**

- 流程内部执行路径
- 并行/分支执行指针

**数据库表：**

- `ACT_RU_EXECUTION`

**流程内部指针**

#### Task

**类：**

```java
org.flowable.engine.task.Task
```

**承载内容：**

- 用户任务
- assignee / candidateUsers / candidateGroups
- 所属流程实例

**数据库表：**

- `ACT_RU_TASK`

**当前待办任务**

#### Variable

**类（接口）：**

```java
org.flowable.variable.api.persistence.entity.VariableInstance
```

**承载内容：**

- 流程变量（运行态）

**数据库表：**

- `ACT_RU_VARIABLE`

**流程运行上下文数据**

#### 历史阶段（History 层）

#### HistoricProcessInstance

**类：**

```java
org.flowable.engine.history.HistoricProcessInstance
```

**承载内容：**

- 已完成或已结束的流程实例信息
- 开始/结束时间

**数据库表：**

- `ACT_HI_PROCINST`

#### HistoricTaskInstance

**类：**

```
org.flowable.engine.history.HistoricTaskInstance
```

**承载内容：**

- 已完成任务记录
- 审批人、时间

**数据库表：**

- `ACT_HI_TASKINST`

#### HistoricActivityInstance

**类：**

```java
org.flowable.engine.history.HistoricActivityInstance
```

**承载内容：**

- 每一个 BPMN 节点的执行轨迹

**数据库表：**

- `ACT_HI_ACTINST`

```
Model
  ↓ deploy
Deployment
  ↓
ProcessDefinition
  ↓ start
ProcessInstance (Execution)
  ↓
Task
  ↓ complete
HistoricTaskInstance
  ↓
HistoricProcessInstance
```

在 flowable 框架中，xml 经过部署成为流程定义，然后从流程定义可以启动一个流程实例。一个流程实例中可以有很多任务节点，每一个任务节点都可以有相应的负责人

下面按 Flowable 的核心结构重新梳理。

------

#  一、整体关系结构

在 **Flowable** 中，核心结构是：

```
BPMN XML
   ↓ 部署（Deployment）
流程定义（Process Definition）
   ↓ 启动
流程实例（Process Instance）
   ↓ 运行过程中产生
任务（Task）
   ↓ 分配
负责人（Assignee / Candidate）
```

------

#  二、逐层解释

## 1. BPMN XML -> 流程定义（Process Definition）

- 你写的 `.bpmn20.xml`
- 描述流程图结构（节点、连线、条件、审批人等）
- 部署后生成流程定义
- 数据表：`act_re_procdef`

 流程定义 = 模板（蓝图）

------

## 2. 流程定义 -> 流程实例（Process Instance）

当你调用：

```
runtimeService.startProcessInstanceByKey("processKey");
```

就会生成一个：

- Process Instance
- 唯一 processInstanceId

数据表：

- 运行中：`act_ru_procinst`
- 历史：`act_hi_procinst`

 流程实例 = 模板的一次实际执行

比如：

- 一条审批单
- 一笔订单流程
- 一次请假申请

------

## 3. 流程实例 -> 任务（Task）

流程走到用户节点（UserTask）时：

Flowable 会创建 Task

数据表：

- 运行中任务：`act_ru_task`
- 历史任务：`act_hi_taskinst`

 一个流程实例会随着流转生成多个任务

- 可能串行
- 可能并行
- 可能多实例

------

## 4. 任务 -> 负责人

每个 Task 都可以配置：

### 单人负责

```
assignee = "user1"
```

### 候选人

```
candidateUsers = "user1,user2"
```

### 候选组

```
candidateGroups = "manager"
```

任务生成后：

- 指定人可直接处理
- 候选人需要 claim
- claim 后变成 assignee

------

#  三、核心关系总结

### 1. 一个流程定义 -> 可以启动多个流程实例

```
流程定义 A
  ├── 实例 1
  ├── 实例 2
  └── 实例 3
```

------

### 2. 一个流程实例 -> 可以产生多个任务

```
实例 1
  ├── 任务 A（部门审批）
  ├── 任务 B（财务审批）
  └── 任务 C（总经理审批）
```

------

### 3. 一个任务 -> 有一个最终负责人

即使是候选人机制：

- 最终执行时只有一个 Assignee
- 并行多实例除外

参考：

**https://www.cnblogs.com/jinyangjie/p/15779216.html**

**https://juejin.cn/post/6844904158231789582**

**https://cloud.tencent.com/developer/article/2210855**
