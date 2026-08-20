+++
date = '2026-08-19T18:26:00+08:00'
draft = false
title = 'TypeScript 学习路线：从类型标注到工程契约'
+++

TypeScript 的价值不在于“给每个变量写类型”，而在于把隐含规则显式表达出来。一个接口返回什么、组件需要什么参数、状态有哪几种可能、函数允许什么输入，这些都应该变成代码里能检查的契约。

如果说 JavaScript 负责表达逻辑，那么 TypeScript 负责约束逻辑的边界。

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

类型系统的本质是把“不确定”摆到台面上。只要你愿意正视它，代码就会少很多意外。

## 二、学习路线

推荐按下面顺序学习：

```text
基础类型
 -> 对象类型
 -> 联合类型
 -> 类型收窄
 -> 泛型
 -> 工具类型
 -> 工程建模
```

不要一开始就钻条件类型、递归类型、复杂类型体操。那些能力有用，但不是入门阶段的主菜。

## 三、类型和运行时的边界

TypeScript 类型只在编译期存在，运行后会被擦除。

```ts
type User = {
  id: number
  name: string
}
```

编译成 JavaScript 后，`User` 不存在。也就是说，TypeScript 不能替你检查真实接口数据一定可靠。

你仍然需要处理运行时校验：

```ts
function isUser(value: unknown): value is User {
  return typeof value === 'object'
    && value !== null
    && typeof (value as User).id === 'number'
    && typeof (value as User).name === 'string'
}
```

类型是开发期契约，运行时校验是现实世界的门卫。两者各司其职。

## 四、前端常见建模对象

前端项目中最常建模的对象包括：

| 对象 | 示例 |
| ---- | ---- |
| 接口响应 | `ApiResponse<T>` |
| 分页数据 | `PageResult<T>` |
| 用户信息 | `UserProfile` |
| 表单模型 | `LoginForm`、`PostForm` |
| 页面状态 | `LoadingState` |
| 组件参数 | `ButtonProps` |
| 枚举值 | `PostStatus`、`ThemeMode` |

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

但要注意：TypeScript 不是 Java。它的类型系统更偏结构化。只要对象结构匹配，类型通常就兼容，不要求来自同一个类。

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
```

精通不是写出谁都看不懂的类型，而是用类型减少沟通成本、减少错误、提升重构信心。

## 七、练习路线

按顺序练习：

1. 给用户对象、文章对象、评论对象定义类型。
2. 给登录表单和发布表单定义类型。
3. 定义统一接口响应 `ApiResponse<T>`。
4. 定义分页响应 `PageResult<T>`。
5. 用联合类型定义请求状态。
6. 写一个泛型函数，从数组中按 `id` 查找元素。
7. 写一个工具类型，把表单字段都变成可选。

当你能把真实业务数据自然地翻译成类型，TypeScript 才算真正学进去了。
