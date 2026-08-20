+++
date = '2026-08-20T18:32:00+08:00'
draft = false
title = '泛型约束、keyof 与 typeof：在类型之间建立关系'
+++

泛型的重点不是“类型参数看起来高级”，而是让输入和输出之间的类型关系被保留下来。`keyof`、`typeof`、索引访问类型和 `as const` 则让你能从已有值或类型中推导出新的类型。

这些能力在工程里非常常见：表格列配置、表单字段、接口响应、状态映射、组件 Props，都离不开它们。

## 一、泛型保留类型关系

没有泛型时，函数容易丢失信息。

```ts
function first(list: unknown[]): unknown {
  return list[0]
}

const value = first(['A', 'B'])
```

`value` 是 `unknown`，后续使用前还要判断。

泛型版本：

```ts
function first<T>(list: T[]): T | undefined {
  return list[0]
}

const value = first(['A', 'B'])
```

`value` 是 `string | undefined`。这就是泛型的价值：函数复用了，类型信息也没有丢。

## 二、什么时候需要显式传泛型

很多时候 TypeScript 能推断泛型。

```ts
const name = first(['A', 'B'])
```

不需要写：

```ts
const name = first<string>(['A', 'B'])
```

需要显式传泛型的场景通常是：

- 参数本身不足以推断类型。
- 初始值为空数组或 `null`。
- 调用第三方库 API 时希望指定返回类型。

例如 Vue：

```ts
const posts = ref<PostCard[]>([])
```

空数组本身推不出 `PostCard`，所以要告诉类型系统。

## 三、泛型约束 extends

泛型可以加约束。

```ts
function getId<T extends { id: number }>(item: T): number {
  return item.id
}
```

`T` 可以是任意对象，但必须有 `id: number`。

```ts
type User = {
  id: number
  name: string
}

type Post = {
  id: number
  title: string
}

getId<User>({ id: 1, name: 'Yuki' })
getId<Post>({ id: 2, title: '文章' })
```

约束不是把类型写死，而是规定最小能力。

## 四、keyof 获取键名联合

`keyof` 可以获取对象类型的键名联合。

```ts
type User = {
  id: number
  name: string
  age: number
}

type UserKey = keyof User
```

`UserKey` 等价于：

```ts
type UserKey = 'id' | 'name' | 'age'
```

这在字段选择、表格列、表单字段中很有用。

```ts
function getValue<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]
}

const user = {
  id: 1,
  name: 'Yuki',
  age: 18
}

const name = getValue(user, 'name')
```

`name` 会被推断成 `string`。

## 五、索引访问类型

`T[K]` 表示从类型 `T` 中取出键 `K` 对应的值类型。

```ts
type User = {
  id: number
  name: string
}

type UserName = User['name']
```

`UserName` 是 `string`。

配合 `keyof`：

```ts
function pluck<T, K extends keyof T>(list: T[], key: K): Array<T[K]> {
  return list.map(item => item[key])
}
```

使用：

```ts
const users = [
  { id: 1, name: 'A' },
  { id: 2, name: 'B' }
]

const ids = pluck(users, 'id')
const names = pluck(users, 'name')
```

`ids` 是 `number[]`，`names` 是 `string[]`。

## 六、typeof 从值推导类型

`typeof` 在类型位置可以从变量推导类型。

```ts
const defaultConfig = {
  pageSize: 20,
  theme: 'light'
}

type Config = typeof defaultConfig
```

`Config` 会根据 `defaultConfig` 推导。

常见用途是从配置对象生成类型：

```ts
const statusConfig = {
  draft: {
    text: '草稿',
    color: 'gray'
  },
  published: {
    text: '已发布',
    color: 'green'
  }
}

type StatusConfig = typeof statusConfig
type Status = keyof typeof statusConfig
```

`Status` 是 `'draft' | 'published'`。

## 七、as const 保留字面量

默认情况下，对象属性会被放宽。

```ts
const config = {
  mode: 'dark'
}
```

`config.mode` 通常是 `string`，不是 `'dark'`。

使用 `as const`：

```ts
const config = {
  mode: 'dark'
} as const
```

这会让对象属性变成只读，并保留字面量类型。

数组也一样：

```ts
const statuses = ['draft', 'published', 'archived'] as const

type PostStatus = typeof statuses[number]
```

`PostStatus` 等价于：

```ts
type PostStatus = 'draft' | 'published' | 'archived'
```

这在维护枚举值列表时很实用。

## 八、satisfies 检查结构但保留推断

`satisfies` 用来检查一个值是否满足某个类型，同时尽量保留值自身更精确的推断。

```ts
type StatusConfig = {
  text: string
  color: 'gray' | 'green' | 'red'
}

const config = {
  draft: {
    text: '草稿',
    color: 'gray'
  },
  published: {
    text: '已发布',
    color: 'green'
  }
} satisfies Record<string, StatusConfig>
```

它比直接类型标注更适合配置对象：

```ts
const config: Record<string, StatusConfig> = {
  draft: {
    text: '草稿',
    color: 'gray'
  }
}
```

直接标注后，键名可能被放宽成 `string`。`satisfies` 能检查结构，同时保留 `draft` 这类具体键名。

## 九、表格列建模

表格列是 `keyof` 的典型场景。

```ts
type TableColumn<T> = {
  key: keyof T
  title: string
}

type Post = {
  id: number
  title: string
  likeCount: number
}

const columns: TableColumn<Post>[] = [
  { key: 'title', title: '标题' },
  { key: 'likeCount', title: '点赞数' }
]
```

如果写错字段：

```ts
const columns: TableColumn<Post>[] = [
  { key: 'likes', title: '点赞数' }
]
```

`likes` 会报错，因为它不是 `Post` 的键。

## 十、更新字段函数

再看一个常见函数：更新对象某个字段。

```ts
function updateField<T, K extends keyof T>(target: T, key: K, value: T[K]): T {
  return {
    ...target,
    [key]: value
  }
}
```

使用：

```ts
const user = {
  id: 1,
  name: 'Yuki',
  age: 18
}

const nextUser = updateField(user, 'age', 19)
```

如果值类型不匹配：

```ts
updateField(user, 'age', '19')
```

会报错，因为 `age` 对应的是 `number`。

## 十一、常见误区

### 1. 泛型没有建立关系

```ts
function parse<T>(value: string): T {
  return JSON.parse(value)
}
```

这看起来很灵活，但其实只是把断言包装起来。`T` 和参数没有真实关系，调用者写什么都能相信。

```ts
const user = parse<User>(text)
```

这不代表运行时数据一定是 `User`。外部输入仍然需要校验。

### 2. key 写成 string

```ts
function getValue<T>(obj: T, key: string) {
  return obj[key]
}
```

`string` 太宽，不能保证它是对象的合法键。应该用：

```ts
function getValue<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]
}
```

### 3. 滥用 as const

`as const` 会让属性只读。配置对象适合，普通可变业务数据不一定适合。

```ts
const form = {
  title: ''
} as const
```

这会导致 `form.title` 不能改，表单场景通常不是你想要的结果。

## 十二、练习

实现一个 `createOptions`：

- 输入对象数组。
- 指定 label 字段和 value 字段。
- 返回 `{ label, value }[]`。
- label 和 value 必须来自对象已有字段。

参考：

```ts
function createOptions<T, L extends keyof T, V extends keyof T>(
  list: T[],
  labelKey: L,
  valueKey: V
): Array<{ label: T[L]; value: T[V] }> {
  return list.map(item => ({
    label: item[labelKey],
    value: item[valueKey]
  }))
}
```

使用：

```ts
const users = [
  { id: 1, name: 'A' },
  { id: 2, name: 'B' }
]

const options = createOptions(users, 'name', 'id')
```

这就是泛型、`keyof` 和索引访问类型共同完成的事：让函数足够通用，同时让调用方不能乱传字段。
