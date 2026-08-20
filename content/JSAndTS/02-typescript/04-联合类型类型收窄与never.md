+++
date = '2026-08-20T18:31:00+08:00'
draft = false
title = '联合类型、类型收窄与 never：把不确定状态说清楚'
+++

TypeScript 最有工程价值的能力之一，是用联合类型描述“不确定”。一个请求可能未开始、加载中、成功、失败；一个弹窗可能是新增、编辑、只读；一个接口字段可能是字符串、数字或空值。

如果这些状态只靠布尔值和可选字段堆出来，代码迟早会出现一些“理论上不该发生但确实发生了”的组合。联合类型的作用，就是提前把可能性列清楚。

## 一、联合类型是什么

联合类型表示一个值可以是多个类型之一。

```ts
type Id = string | number

function printId(id: Id) {
  console.log(id)
}
```

更常见的是字面量联合：

```ts
type Status = 'idle' | 'loading' | 'success' | 'error'
```

这比普通字符串更安全：

```ts
let status: Status = 'loading'
status = 'done'
```

`'done'` 会报错。

## 二、为什么不用多个 boolean

很多页面状态会这样写：

```ts
type State<T> = {
  loading: boolean
  data?: T
  error?: string
}
```

它能表达很多状态，但也能表达不合理状态：

```ts
const state: State<string[]> = {
  loading: true,
  data: ['A'],
  error: '失败'
}
```

加载中、已有数据、同时失败。也许某些业务允许，但大多数时候这是状态混乱。

用判别联合更清楚：

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }
```

每个状态只能带自己应该有的字段。

## 三、判别字段

判别字段是联合类型里用于区分分支的固定字段。

```ts
type DialogState =
  | { mode: 'create' }
  | { mode: 'edit'; id: number }
  | { mode: 'readonly'; id: number }
```

使用时：

```ts
function getDialogTitle(state: DialogState): string {
  switch (state.mode) {
    case 'create':
      return '新增'
    case 'edit':
      return `编辑 ${state.id}`
    case 'readonly':
      return `查看 ${state.id}`
  }
}
```

在 `edit` 和 `readonly` 分支里，TypeScript 知道 `id` 存在；在 `create` 分支里，`id` 不存在。

## 四、typeof 收窄

基础类型用 `typeof` 收窄。

```ts
function formatValue(value: string | number) {
  if (typeof value === 'number') {
    return value.toFixed(2)
  }

  return value.trim()
}
```

`typeof` 常见结果：

```text
string
number
boolean
undefined
bigint
symbol
function
object
```

注意 `typeof null` 是 `'object'`，这是 JavaScript 历史问题。判断对象时要排除 `null`。

```ts
function isObject(value: unknown) {
  return typeof value === 'object' && value !== null
}
```

## 五、instanceof 收窄

`instanceof` 适合类实例和内置对象。

```ts
function formatDate(value: string | Date) {
  if (value instanceof Date) {
    return value.toLocaleDateString()
  }

  return new Date(value).toLocaleDateString()
}
```

错误处理里也常见：

```ts
function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }

  return '未知错误'
}
```

不要假设 `catch (error)` 一定是 `Error`。真实世界总有人 `throw 'fail'`，虽然这并不值得赞赏。

## 六、in 操作符收窄

判断对象是否拥有某字段，可以用 `in`。

```ts
type Cat = {
  meow: () => void
}

type Dog = {
  bark: () => void
}

function speak(animal: Cat | Dog) {
  if ('meow' in animal) {
    animal.meow()
  } else {
    animal.bark()
  }
}
```

前端接口兼容老字段时也会遇到：

```ts
type OldUser = {
  name: string
}

type NewUser = {
  profile: {
    name: string
  }
}

function getUserName(user: OldUser | NewUser) {
  if ('profile' in user) {
    return user.profile.name
  }

  return user.name
}
```

## 七、自定义类型守卫

类型守卫函数返回 `value is Type`。

```ts
type User = {
  id: number
  name: string
}

function isUser(value: unknown): value is User {
  return typeof value === 'object'
    && value !== null
    && typeof (value as User).id === 'number'
    && typeof (value as User).name === 'string'
}
```

使用：

```ts
const value: unknown = JSON.parse(text)

if (isUser(value)) {
  console.log(value.name)
}
```

类型守卫很适合处理外部输入：

- 接口响应。
- 本地存储。
- URL 参数。
- 第三方 SDK 数据。
- 用户导入的 JSON 文件。

## 八、数组过滤中的类型守卫

过滤空值时，普通 `filter(Boolean)` 不一定能得到理想类型。

```ts
const list: Array<string | null> = ['A', null, 'B']

const result = list.filter(Boolean)
```

`result` 的类型可能仍然不够精确。

可以写类型守卫：

```ts
function isNotNull<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

const result = list.filter(isNotNull)
```

这样 `result` 会被推断为 `string[]`。

## 九、never 和穷尽检查

`never` 表示不可能出现的值。它常用于检查联合类型是否处理完整。

```ts
function assertNever(value: never): never {
  throw new Error(`未处理的分支：${JSON.stringify(value)}`)
}
```

使用：

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }

function getStateText<T>(state: LoadState<T>): string {
  switch (state.status) {
    case 'idle':
      return '未开始'
    case 'loading':
      return '加载中'
    case 'success':
      return '加载成功'
    case 'error':
      return state.message
    default:
      return assertNever(state)
  }
}
```

如果将来新增状态：

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }
  | { status: 'empty' }
```

但 `switch` 没处理 `empty`，`assertNever(state)` 就会报错。这就是类型系统替你提醒“你改了一半”。

## 十、业务状态建模

以文章编辑页为例：

```ts
type EditorState =
  | { status: 'draft'; content: string }
  | { status: 'saving'; content: string }
  | { status: 'saved'; content: string; savedAt: string }
  | { status: 'failed'; content: string; message: string }
```

页面按钮逻辑：

```ts
function canSubmit(state: EditorState): boolean {
  return state.status === 'draft' || state.status === 'failed'
}
```

展示文案：

```ts
function getEditorText(state: EditorState): string {
  switch (state.status) {
    case 'draft':
      return '未保存'
    case 'saving':
      return '保存中'
    case 'saved':
      return `已保存于 ${state.savedAt}`
    case 'failed':
      return state.message
    default:
      return assertNever(state)
  }
}
```

这样比 `saving: boolean`、`saved: boolean`、`error?: string` 更不容易出现矛盾组合。

## 十一、常见误区

### 1. 联合类型太宽

```ts
type Value = string | number | boolean | object | null | undefined
```

如果几乎什么都允许，那后续使用前仍然要大量判断。应该先思考业务真正允许哪些值。

### 2. 用可选字段替代状态分支

```ts
type Result<T> = {
  data?: T
  error?: string
}
```

这无法表达成功和失败互斥。更好：

```ts
type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }
```

### 3. 忘记处理新增分支

联合类型一旦扩展，所有消费方都可能需要调整。用 `assertNever` 能让遗漏更早暴露。

## 十二、练习

定义一个文件上传状态：

- 未选择文件。
- 已选择文件，包含文件名和大小。
- 上传中，包含进度。
- 上传成功，包含文件 URL。
- 上传失败，包含错误信息。

参考：

```ts
type UploadState =
  | { status: 'idle' }
  | { status: 'selected'; name: string; size: number }
  | { status: 'uploading'; progress: number }
  | { status: 'success'; url: string }
  | { status: 'error'; message: string }
```

然后写一个 `getUploadText(state)`，用 `switch` 和 `assertNever` 返回文案。联合类型训练的是一件事：让不确定的业务状态变得明确。能做到这一点，很多页面逻辑会自己安静下来。
