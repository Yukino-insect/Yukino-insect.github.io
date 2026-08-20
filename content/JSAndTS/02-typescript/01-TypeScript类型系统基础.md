+++
date = '2026-08-19T18:25:00+08:00'
draft = false
title = 'TypeScript 类型系统基础：类型推断、联合类型和类型收窄'
+++

TypeScript 入门的关键不是记住所有语法，而是理解它如何推断、限制和收窄类型。类型系统越早介入，错误越早暴露；错误越早暴露，修复成本越低。

## 一、类型推断

很多时候不需要手动标注类型。

```ts
const name = 'Yuki'
const age = 18
const enabled = true
```

TypeScript 会推断：

```text
name: string
age: number
enabled: boolean
```

过度标注会让代码变啰嗦。

```ts
const count: number = 0
```

这不是错，只是没有必要。真正需要标注的是函数边界、复杂对象、接口响应和空数组。

## 二、函数参数和返回值

函数参数应该显式标注。

```ts
function formatCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}w`
  }
  return String(count)
}
```

返回值可以让 TypeScript 推断，但公共函数建议写出来。它会成为调用者的阅读入口。

## 三、对象类型

使用 `type` 定义对象结构：

```ts
type User = {
  id: number
  username: string
  nickname?: string
  avatarUrl?: string | null
}
```

`?` 表示字段可选。`string | null` 表示字段存在但可能为空。两者不是一回事：

```ts
type A = {
  name?: string
}

type B = {
  name: string | null
}
```

`A` 可以没有 `name` 字段，`B` 必须有 `name` 字段，只是值可能是 `null`。

## 四、interface 与 type

两者都能描述对象：

```ts
interface User {
  id: number
  name: string
}

type Post = {
  id: number
  title: string
}
```

常见选择：

- 业务对象、接口响应、联合类型：优先 `type`。
- 需要声明合并、面向库扩展：可以使用 `interface`。

团队内保持一致比争论二者高下更重要。

## 五、联合类型

联合类型表示一个值可能是多种类型之一。

```ts
type Id = number | string
```

更常见的是用来描述状态：

```ts
type RequestStatus = 'idle' | 'loading' | 'success' | 'error'
```

这样可以限制状态只能取这四个值。

```ts
let status: RequestStatus = 'loading'
status = 'done'
```

`'done'` 会报错，因为它不在联合类型里。

## 六、类型收窄

当一个值可能有多种类型时，需要先判断再使用。

```ts
function printId(id: number | string) {
  if (typeof id === 'number') {
    console.log(id.toFixed(0))
  } else {
    console.log(id.toUpperCase())
  }
}
```

判断后，TypeScript 能知道分支里的具体类型。

对象联合类型通常使用判别字段：

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }

function renderState(state: LoadState<string[]>) {
  if (state.status === 'success') {
    return state.data.join(',')
  }

  if (state.status === 'error') {
    return state.message
  }

  return ''
}
```

这比到处写 `data?: T`、`error?: string` 更清晰。

## 七、unknown 与 any

`any` 会关闭类型检查：

```ts
let value: any = 1
value.trim().toFixed().notExists()
```

TypeScript 不会拦你。它很礼貌，也很危险。

`unknown` 表示未知类型，使用前必须判断。

```ts
function handleError(error: unknown) {
  if (error instanceof Error) {
    console.log(error.message)
  } else {
    console.log('未知错误')
  }
}
```

公共边界上优先使用 `unknown`，不要随手写 `any`。

## 八、never

`never` 表示不可能出现的值。它常用于穷尽检查。

```ts
function assertNever(value: never): never {
  throw new Error(`未处理的状态：${value}`)
}

function getStatusText(status: RequestStatus) {
  switch (status) {
    case 'idle':
      return '未开始'
    case 'loading':
      return '加载中'
    case 'success':
      return '成功'
    case 'error':
      return '失败'
    default:
      return assertNever(status)
  }
}
```

如果以后给 `RequestStatus` 增加新状态，`switch` 没处理时就会报错。

## 九、类型建模建议

- 不要把接口响应写成 `any`。
- 不要把所有字段都写成可选。
- 状态值优先使用字面量联合类型。
- 表单类型和提交参数可以分开。
- 外部输入先用 `unknown` 接住，再做校验。

## 十、练习

定义一个文章加载状态：

- 未开始。
- 加载中。
- 加载成功，包含文章列表。
- 加载失败，包含错误信息。

然后写一个函数，根据状态返回展示文案。这个练习很小，但能训练你用类型表达业务状态，而不是把状态揉成一团。
