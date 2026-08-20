+++
date = '2026-08-19T18:25:00+08:00'
draft = false
title = 'TypeScript 类型系统基础：类型推断、对象类型、联合类型和收窄'
+++

TypeScript 入门的关键不是记住所有语法，而是理解它如何推断、限制和收窄类型。类型系统越早介入，错误越早暴露；错误越早暴露，修复成本越低。

这一篇先讲最常用的基础能力：类型推断、函数边界、对象类型、可选字段、字面量类型、联合类型、类型收窄、`any`、`unknown` 和 `never`。

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

这不是错，只是没有必要。真正需要标注的是函数参数、公共函数返回值、复杂对象、接口响应和空数组。

空数组尤其要注意：

```ts
const users = []
```

在不同配置下，空数组可能被推断成 `any[]` 或 `never[]`。业务代码里更稳的写法是：

```ts
type User = {
  id: number
  name: string
}

const users: User[] = []
```

## 二、字面量类型

`let` 和 `const` 的推断不同。

```ts
let status = 'loading'
const mode = 'dark'
```

通常可以理解为：

```text
status: string
mode: 'dark'
```

因为 `let` 后续可以重新赋值，所以被放宽成 `string`；`const` 不能重新赋值，所以可以推断成更具体的字面量类型。

字面量类型可以限制取值：

```ts
type ThemeMode = 'light' | 'dark' | 'system'

let mode: ThemeMode = 'dark'
mode = 'blue'
```

`'blue'` 会报错，因为它不是合法主题。

## 三、基础类型

常见基础类型：

| 类型 | 示例 |
| ---- | ---- |
| `string` | `'hello'` |
| `number` | `18`、`3.14` |
| `boolean` | `true` |
| `null` | `null` |
| `undefined` | `undefined` |
| `bigint` | `1n` |
| `symbol` | `Symbol()` |

数组类型：

```ts
const ids: number[] = [1, 2, 3]
const names: Array<string> = ['A', 'B']
```

两种写法都可以。业务代码里 `number[]` 更常见，泛型嵌套复杂时 `Array<T>` 有时更清楚。

元组类型表示固定长度和固定位置含义：

```ts
type Point = [number, number]

const point: Point = [100, 200]
```

元组适合表示坐标、范围、键值对等结构。普通列表不要强行写成元组。

## 四、函数参数和返回值

函数参数应该显式标注。

```ts
function formatCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}w`
  }
  return String(count)
}
```

返回值可以让 TypeScript 推断，但公共函数建议写出来。它会成为调用者的阅读入口，也能防止函数内部改着改着返回值变形。

回调函数也可以建模：

```ts
type Listener<T> = (value: T) => void

function onChange(listener: Listener<string>) {
  listener('new value')
}
```

可选参数要放在必填参数后面：

```ts
function search(keyword: string, page?: number) {
  return {
    keyword,
    page: page ?? 1
  }
}
```

默认参数通常不需要再写成可选：

```ts
function search(keyword: string, page = 1) {
  return {
    keyword,
    page
  }
}
```

## 五、对象类型

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

如果开启 `exactOptionalPropertyTypes`，`name?: string` 和 `name: string | undefined` 的差异会更明显。前者强调“字段可以不存在”，后者强调“字段存在但值可以是 undefined”。

## 六、只读字段

`readonly` 表示字段不能被重新赋值。

```ts
type User = {
  readonly id: number
  name: string
}

const user: User = {
  id: 1,
  name: 'Yuki'
}

user.name = 'New Name'
user.id = 2
```

`user.id = 2` 会报错。

注意：`readonly` 默认只是限制这一层属性。

```ts
type Post = {
  readonly author: {
    name: string
  }
}

const post: Post = {
  author: {
    name: 'Yuki'
  }
}

post.author.name = 'New Name'
```

这段代码可以通过，因为 `author` 这个属性不能换，但 `author.name` 没有被声明为只读。

## 七、联合类型

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

联合类型不要写得过于宽泛：

```ts
type Value = string | number | boolean | object | null
```

如果一个类型什么都能装，那它基本上没什么约束力。类型不是收纳箱，别把所有东西都塞进去。

## 八、类型收窄

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

常见收窄方式：

| 写法 | 适合场景 |
| ---- | -------- |
| `typeof` | 基础类型 |
| `instanceof` | 类实例、错误对象、日期对象 |
| `'key' in value` | 判断对象是否有某字段 |
| 判别字段 | 对象联合类型 |
| 自定义类型守卫 | 外部输入、复杂判断 |

示例：

```ts
function handleError(error: unknown) {
  if (error instanceof Error) {
    console.log(error.message)
  } else {
    console.log('未知错误')
  }
}
```

## 九、判别联合

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

这比到处写 `data?: T`、`error?: string` 更清晰，因为不同状态下能访问什么字段，是由类型明确表达的。

> 在 TypeScript 中，在联合类型（Union Type）的最开头使用竖线 | 是一种可选的语法习惯，它的作用主要是为了提升代码的可读性和格式化排版的便利性。
>
> 具体原因如下：
>
> 多行格式化排版：当联合类型的成员较多、需要分多行书写时，如果在第一行也加上 |，可以让所有分支在视觉上完全对齐，整体结构更清晰美观。
>
> 便于修改和维护：在调整代码顺序（如用快捷键向上/向下移动某一行）或增删类型成员时，每行都保持统一的 | { ... } 格式，不需要额外处理第一行的竖线。
>
> 这种写法在 TypeScript 语法规范中是完全合法且等价的。写成以下形式效果完全相同：
>
> ```ts
> type PostLoadState = { status: 'idle' }
>   | { status: 'loading' }
>   | { status: 'success'; data: Post[] }
>   | { status: 'error'; message: string }
> ```



## 十、unknown 与 any

`any` 会关闭类型检查：

```ts
let value: any = 1
value.trim().toFixed().notExists()
```

TypeScript 不会拦你。它很礼貌，也很危险。

`unknown` 表示未知类型，使用前必须判断。

```ts
function parseJson(text: string): unknown {
  return JSON.parse(text)
}

const value = parseJson('{"id":1}')

if (typeof value === 'object' && value !== null) {
  console.log(value)
}
```

公共边界上优先使用 `unknown`，不要随手写 `any`。

适合用 `unknown` 的地方：

- `JSON.parse` 的结果。
- 外部接口返回值。
- `catch` 捕获的错误。
- 浏览器存储中读出的数据。
- 第三方 SDK 回调参数。

## 十一、never

`never` 表示不可能出现的值。它常用于穷尽检查。

```ts
function assertNever(value: never): never {
  throw new Error(`未处理的状态：${value}`)
}

type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

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

## 十二、类型断言

类型断言告诉 TypeScript：“我比你更清楚这个值是什么类型。”

```ts
const input = document.querySelector('#username') as HTMLInputElement

console.log(input.value)
```

断言不会做运行时检查。如果选不到元素，`input` 仍然可能是 `null`，只是你强行让 TypeScript 相信它不是。

更稳的写法：

```ts
const input = document.querySelector('#username')

if (input instanceof HTMLInputElement) {
  console.log(input.value)
}
```

断言要少用。每一次 `as` 都是在告诉类型系统“这里你先别管”。如果整篇代码都是 `as`，那 TypeScript 基本只是站在旁边看你表演。

## 十三、类型建模建议

- 不要把接口响应写成 `any`。
- 不要把所有字段都写成可选。
- 状态值优先使用字面量联合类型。
- 表单类型和提交参数可以分开。
- 外部输入先用 `unknown` 接住，再做校验或收窄。
- 函数参数要显式标注，公共返回值建议显式标注。
- 能让 TypeScript 推断的局部变量，不要重复标注。

## 十四、练习

定义一个文章加载状态：

- 未开始。
- 加载中。
- 加载成功，包含文章列表。
- 加载失败，包含错误信息。

然后写一个函数，根据状态返回展示文案。

参考结构：

```ts
type Post = {
  id: number
  title: string
}

type PostLoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: Post[] }
  | { status: 'error'; message: string }

function assertNever(value: never): never {
  throw new Error(`未处理的状态：${value}`)
}

function getPostStateText(state: PostLoadState): string {
  switch (state.status) {
    case 'idle':
      return '尚未加载'
    case 'loading':
      return '加载中'
    case 'success':
      return `共 ${state.data.length} 篇文章`
    case 'error':
      return state.message
    default:
      return assertNever(state)
  }
}
```

这个练习很小，但能训练你用类型表达业务状态，而不是把状态揉成一团。类型系统并不神秘，它只是要求你把话说清楚。
