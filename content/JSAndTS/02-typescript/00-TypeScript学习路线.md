+++
date = '2026-08-19T18:26:00+08:00'
draft = false
title = 'TypeScript 学习路线：从类型标注到工程契约'
+++

TypeScript 的价值不在于“给每个变量写类型”，而在于把隐含规则显式表达出来。接口返回什么、组件需要什么参数、状态有哪几种可能、函数允许什么输入、错误应该如何处理，这些都应该变成代码里能检查的契约。

如果说 JavaScript 负责表达运行时逻辑，那么 TypeScript 负责约束这些逻辑的边界。边界越清楚，重构时越不需要靠记忆和运气。

## 一、TypeScript 解决什么问题

JavaScript 很灵活，但灵活也意味着错误可能到运行时才暴露。

```js
function getUserName(user) {
  return user.profile.name
}
```

如果 `profile` 是 `null`，这段代码运行时才会报错。TypeScript 可以提前提醒你：

```ts
type User = {
  profile?: {
    name: string
  }
}

function getUserName(user: User) {
  return user.profile?.name ?? '匿名用户'
}
```

类型系统的本质是把“不确定”摆到台面上。只要你愿意正视它，代码就会少很多意外。嗯，逃避当然也可以，只是错误不会因此变得懂事。

## 二、学习路线

推荐按下面顺序学习：

```text
基础类型和类型推断
 -> 对象类型、可选字段和只读字段
 -> 字面量类型、联合类型和类型收窄
 -> interface、type 和结构化类型系统
 -> 函数类型、回调类型和 this 类型
 -> 泛型和泛型约束
 -> keyof、typeof、索引访问类型
 -> 映射类型、条件类型和 infer
 -> 内置工具类型
 -> 接口响应、表单、组件 Props 和状态建模
 -> tsconfig、模块解析和运行时边界
```

不要一开始就钻递归类型和复杂类型体操。那些能力有用，但不是入门阶段的主菜。能把真实业务数据建模清楚，比写出让同事沉默的类型谜题更有价值。

## 三、类型和运行时的边界

TypeScript 类型只在编译期存在，运行后会被擦除。

```ts
type User = {
  id: number
  name: string
}
```

编译成 JavaScript 后，`User` 不存在。也就是说，TypeScript 不能替你证明真实接口数据一定可靠。

你仍然需要处理运行时校验：

```ts
function isUser(value: unknown): value is User {
  return typeof value === 'object'
    && value !== null
    && typeof (value as User).id === 'number'
    && typeof (value as User).name === 'string'
}
```

类型是开发期契约，运行时校验是现实世界的门卫。两者各司其职，别让其中一个假装自己能包办全部工作。

## 四、前端常见建模对象

前端项目中最常建模的对象包括：

| 对象 | 示例 |
| ---- | ---- |
| 接口响应 | `ApiResponse<T>` |
| 分页数据 | `PageResult<T>` |
| 用户信息 | `UserProfile` |
| 表单模型 | `LoginForm`、`PostForm` |
| 提交参数 | `CreatePostRequest`、`UpdateUserRequest` |
| 页面状态 | `LoadState<T>` |
| 组件参数 | `ButtonProps`、`TableColumn<T>` |
| 枚举值 | `PostStatus`、`ThemeMode` |
| 配置映射 | `Record<PostStatus, StatusConfig>` |

这些类型不只是为了 IDE 提示，它们也是团队协作的边界。

## 五、后端学生的迁移理解

可以这样类比：

| 后端概念 | TypeScript / 前端概念 |
| -------- | --------------------- |
| DTO | 接口请求和响应类型 |
| VO | 页面展示模型 |
| Enum | 字面量联合类型 |
| Service 方法签名 | 函数参数与返回值类型 |
| Controller 入参校验 | 表单类型与运行时校验 |
| 泛型响应对象 | `ApiResponse<T>` |
| 状态机 | 判别联合类型 |

但要注意：TypeScript 不是 Java。它的类型系统更偏结构化。只要对象结构匹配，类型通常就兼容，不要求来自同一个类。

```ts
type User = {
  id: number
  name: string
}

type Member = {
  id: number
  name: string
}

const user: User = {
  id: 1,
  name: 'Yuki'
}

const member: Member = user
```

这段代码成立，因为 `User` 和 `Member` 的结构兼容。理解结构化类型，是理解 TypeScript 的一条主线。

## 六、精通 TypeScript 的标志

初级使用者会写：

```ts
const list: any[] = []
```

成熟使用者会写：

```ts
type PostCard = {
  id: number
  title: string
  summary: string
  liked: boolean
}

const list = ref<PostCard[]>([])
```

更进一步，会把通用契约抽出来：

```ts
type PageResult<T> = {
  records: T[]
  total: number
  page: number
  pageSize: number
}

type PostListState = LoadState<PageResult<PostCard>>
```

精通不是写出谁都看不懂的类型，而是用类型减少沟通成本、减少错误、提升重构信心。

## 七、练习路线

按顺序练习：

1. 给用户对象、文章对象、评论对象定义类型。
2. 区分接口响应模型、页面展示模型和表单模型。
3. 定义统一接口响应 `ApiResponse<T>`。
4. 定义分页响应 `PageResult<T>`。
5. 用判别联合定义请求状态 `LoadState<T>`。
6. 写一个泛型函数，从数组中按 `id` 查找元素。
7. 用 `Pick`、`Omit`、`Partial` 推导提交参数类型。
8. 用 `Record` 约束状态到文案、颜色、按钮行为的映射。
9. 写一个类型守卫，把 `unknown` 接口数据收窄成业务类型。
10. 打开 `strict`，修复项目里暴露出来的真实问题。

当你能把真实业务数据自然地翻译成类型，TypeScript 才算真正学进去了。类型不是装饰，它应该参与设计。
