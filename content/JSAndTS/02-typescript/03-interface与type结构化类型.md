+++
date = '2026-08-20T18:30:00+08:00'
draft = false
title = 'interface 与 type：结构化类型、声明合并和对象建模'
+++

TypeScript 里最常见的问题之一是：到底用 `interface` 还是 `type`？

这个问题如果只回答“都可以”，虽然不算错，但等于没有回答。更重要的是理解 TypeScript 的结构化类型系统：类型是否兼容，主要看结构是否匹配，而不是看名字是否相同。

## 一、type 和 interface 都能描述对象

`interface` 写法：

```ts
interface User {
  id: number
  name: string
}
```

`type` 写法：

```ts
type User = {
  id: number
  name: string
}
```

在普通对象建模中，两者都能用。

```ts
const user: User = {
  id: 1,
  name: 'Yuki'
}
```

如果你的团队已经有统一规范，先遵守规范。没有规范时，可以用一个简单原则：业务数据模型优先 `type`，需要被外部扩展的公共对象优先 `interface`。

## 二、结构化类型系统

TypeScript 是结构化类型系统。只要结构匹配，类型就兼容。

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

这段代码成立，因为 `User` 和 `Member` 都有 `id: number` 和 `name: string`。

这和 Java 这类名义类型系统不同。TypeScript 不关心对象“出生在哪个类型名下”，它更关心对象现在长什么样。现实一点说，它看脸，或者更准确地说，看结构。

## 三、额外字段兼容

结构兼容不是要求两个对象完全一样。源对象可以有更多字段。

```ts
type User = {
  id: number
  name: string
}

const admin = {
  id: 1,
  name: 'Yuki',
  role: 'admin'
}

const user: User = admin
```

这段代码可以通过，因为 `admin` 至少满足 `User` 需要的字段。

函数参数也是一样：

```ts
function printUser(user: User) {
  console.log(user.name)
}

printUser(admin)
```

调用方给得更多，函数只用自己需要的部分。

## 四、多余属性检查

直接传对象字面量时，TypeScript 会做多余属性检查。

```ts
type User = {
  id: number
  name: string
}

function printUser(user: User) {
  console.log(user.name)
}

printUser({
  id: 1,
  name: 'Yuki',
  role: 'admin'
})
```

这里 `role` 会报错。

但如果先赋值给变量：

```ts
const admin = {
  id: 1,
  name: 'Yuki',
  role: 'admin'
}

printUser(admin)
```

通常可以通过。

原因是对象字面量直接传参时，TypeScript 会更严格地检查“你是不是写错字段了”。这不是前后矛盾，而是为了捕获常见拼写错误。

## 五、interface 的继承

`interface` 可以使用 `extends` 扩展。

```ts
interface Entity {
  id: number
}

interface User extends Entity {
  name: string
}

const user: User = {
  id: 1,
  name: 'Yuki'
}
```

多个接口也可以继承：

```ts
interface Timestamped {
  createdAt: string
  updatedAt: string
}

interface Post extends Entity, Timestamped {
  title: string
}
```

这适合表达“某个对象具备一组公共能力或公共字段”。

## 六、type 的交叉类型

`type` 可以使用交叉类型组合对象。

```ts
type Entity = {
  id: number
}

type Timestamped = {
  createdAt: string
  updatedAt: string
}

type Post = Entity & Timestamped & {
  title: string
}
```

`&` 表示同时满足多个类型。

交叉类型适合组合字段，但要小心冲突字段。

```ts
type A = {
  id: number
}

type B = {
  id: string
}

type C = A & B
```

`C['id']` 会变成 `never`，因为一个字段不可能既是 `number` 又是 `string`。

## 七、interface 的声明合并

`interface` 可以声明合并。

```ts
interface User {
  id: number
}

interface User {
  name: string
}

const user: User = {
  id: 1,
  name: 'Yuki'
}
```

两个 `User` 会合并成一个。

声明合并常用于扩展第三方库类型或全局类型：

```ts
declare global {
  interface Window {
    appVersion: string
  }
}
```

业务代码里不要随意依赖声明合并。它很方便，也容易让类型来源变得不透明。

## 八、type 能表达更多类型

`type` 不只能描述对象，还能表达联合类型、元组、函数类型等。

```ts
type Status = 'idle' | 'loading' | 'success' | 'error'

type Point = [number, number]

type Formatter = (value: number) => string
```

`interface` 主要描述对象形状。虽然它也能描述函数对象，但普通函数类型用 `type` 更直观。

```ts
type ClickHandler = (event: MouseEvent) => void
```

## 九、函数类型

函数类型可以这样定义：

```ts
type RequestFn = (url: string, options?: RequestInit) => Promise<unknown>
```

也可以用 interface：

```ts
interface RequestFn {
  (url: string, options?: RequestInit): Promise<unknown>
}
```

如果只是表达一个函数签名，`type` 更简洁。

如果函数本身还带属性，可以使用 interface：

```ts
interface CacheFn {
  (key: string): string | undefined
  clear(): void
}
```

## 十、索引签名

当对象有动态键时，可以使用索引签名。

```ts
type StringMap = {
  [key: string]: string
}

const messages: StringMap = {
  success: '成功',
  error: '失败'
}
```

但索引签名会让类型变宽。能用固定联合键时，更推荐 `Record`：

```ts
type Status = 'success' | 'error'

const messages: Record<Status, string> = {
  success: '成功',
  error: '失败'
}
```

这样漏字段或多字段都会被检查。

## 十一、如何选择

一个实用选择表：

| 场景 | 建议 |
| ---- | ---- |
| 普通业务对象 | `type` 或团队统一规范 |
| 联合类型 | `type` |
| 元组类型 | `type` |
| 函数类型 | `type` |
| 需要声明合并 | `interface` |
| 设计给外部扩展的库类型 | `interface` |
| 组合多个对象结构 | `type` 的交叉类型或 `interface extends` |

不要把 `interface` 和 `type` 的选择变成审美战争。项目可维护性来自一致性、边界清晰和命名准确，不来自某个关键字的胜利。

## 十二、练习

定义以下类型：

- `Entity`：包含 `id`。
- `Timestamped`：包含 `createdAt` 和 `updatedAt`。
- `Post`：包含 `Entity`、`Timestamped` 和 `title`。
- `PostStatus`：只能是 `draft`、`published`、`archived`。
- `StatusTextMap`：要求每个 `PostStatus` 都有对应文案。

参考：

```ts
type Entity = {
  id: number
}

type Timestamped = {
  createdAt: string
  updatedAt: string
}

type Post = Entity & Timestamped & {
  title: string
}

type PostStatus = 'draft' | 'published' | 'archived'

type StatusTextMap = Record<PostStatus, string>
```

这几个类型覆盖了对象组合、字面量联合和映射约束，是业务建模中很常见的一组基本功。
