+++
date = '2026-08-20T18:35:00+08:00'
draft = false
title = 'tsconfig、模块解析与运行时边界：TypeScript 工程配置入门'
+++

很多人学 TypeScript 时只看类型语法，却忽略 `tsconfig.json`。这很危险。`tsconfig` 决定 TypeScript 如何检查代码、如何理解模块、是否启用严格模式、能不能使用 DOM 类型、路径别名怎么解析。

换句话说，类型系统不是孤零零漂在空中的。配置决定它能管多宽、管多严。放任配置不管，就像请了门卫却不给名单，场面会很客气，也很没用。

## 一、tsconfig 是什么

`tsconfig.json` 是 TypeScript 项目的配置文件。

一个简化配置：

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"],
  "exclude": ["node_modules", "dist"]
}
```

前端项目通常由 Vite、Vue、React 等工具完成最终构建，TypeScript 主要负责类型检查和部分语法转换。

## 二、target

`target` 决定输出 JavaScript 的语法版本。

```json
{
  "compilerOptions": {
    "target": "ES2020"
  }
}
```

如果目标环境较新，可以使用较新的 target。构建工具和浏览器兼容策略也会影响最终产物。

常见取值：

| 值 | 含义 |
| ---- | ---- |
| `ES2017` | 支持 async/await 的基础现代版本 |
| `ES2020` | 支持可选链、空值合并等现代特性 |
| `ESNext` | 尽量使用最新语法 |

业务项目中不要只凭感觉改 `target`。它和浏览器兼容、构建工具、polyfill 策略相关。

## 三、module 与 moduleResolution

`module` 决定模块输出形式。

```json
{
  "compilerOptions": {
    "module": "ESNext"
  }
}
```

现代前端项目通常使用 ES Module。

`moduleResolution` 决定 TypeScript 如何查找模块。

```json
{
  "compilerOptions": {
    "moduleResolution": "Bundler"
  }
}
```

Vite 等现代构建工具项目常用 `Bundler`。Node 项目可能使用 `NodeNext` 或 `Node16`。

如果模块解析配置不对，常见问题包括：

- 编辑器找不到模块。
- 类型检查通过但构建失败。
- 构建通过但测试环境找不到路径。
- 默认导入和命名导入行为不一致。

## 四、strict

`strict` 是一组严格检查的总开关。

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

它会启用多项检查，例如：

- `noImplicitAny`
- `strictNullChecks`
- `strictFunctionTypes`
- `strictBindCallApply`
- `strictPropertyInitialization`
- `noImplicitThis`

新项目建议开启 `strict`。旧项目如果问题太多，可以分阶段开启，但最终应该向严格模式靠拢。

不开严格模式的 TypeScript，仍然有价值，但会漏掉很多真实问题。

## 五、strictNullChecks

`strictNullChecks` 开启后，`null` 和 `undefined` 不会被随便赋给其他类型。

```ts
let name: string = null
```

会报错。

你需要显式表达空值：

```ts
let name: string | null = null
```

这让代码必须面对空值。

```ts
function getName(user?: { name: string }) {
  return user?.name ?? '匿名用户'
}
```

前端接口和 DOM 操作里空值非常常见，`strictNullChecks` 很值得开启。

## 六、noImplicitAny

`noImplicitAny` 禁止隐式 `any`。

```ts
function format(value) {
  return String(value)
}
```

参数 `value` 没有类型，会报错。

应该写：

```ts
function format(value: unknown): string {
  return String(value)
}
```

或者更具体：

```ts
function formatCount(value: number): string {
  return String(value)
}
```

`any` 不是绝对不能用，但应该显式写出来。显式写 `any` 至少说明你知道自己正在放弃类型检查。

## 七、noUncheckedIndexedAccess

这个配置会让索引访问结果包含 `undefined`。

```json
{
  "compilerOptions": {
    "noUncheckedIndexedAccess": true
  }
}
```

例如：

```ts
const list = ['A', 'B']
const first = list[0]
```

开启后，`first` 是 `string | undefined`。

对象索引也一样：

```ts
const map: Record<string, string> = {}
const value = map['key']
```

`value` 是 `string | undefined`。

这更贴近运行时真实情况。数组第一个元素不一定存在，对象键也不一定有值。类型系统只是把这个事实说出来，虽然有时听起来不够温柔。

## 八、exactOptionalPropertyTypes

开启后，可选属性会更精确。

```json
{
  "compilerOptions": {
    "exactOptionalPropertyTypes": true
  }
}
```

区别：

```ts
type User = {
  name?: string
}
```

`name?: string` 表示字段可以不存在。它不完全等同于：

```ts
type User = {
  name: string | undefined
}
```

这对 PATCH 请求、表单字段、配置覆盖很有意义。

```ts
type PatchUserRequest = {
  nickname?: string
}
```

字段不存在，可能表示“不更新”；字段存在但值为 `undefined`，语义就不一定清楚。配置越严格，语义越需要你认真对待。

## 九、lib

`lib` 决定项目能使用哪些环境类型。

```json
{
  "compilerOptions": {
    "lib": ["ES2020", "DOM", "DOM.Iterable"]
  }
}
```

浏览器项目需要 `DOM`，否则 `document`、`window`、`HTMLElement` 等类型不可用。

Node 项目不应该随便依赖 DOM 类型。不同运行环境的全局能力不同，TypeScript 的配置也应该区分。

## 十、types

`types` 用来指定自动引入哪些类型包。

```json
{
  "compilerOptions": {
    "types": ["vite/client"]
  }
}
```

Vite 项目常见 `vite/client`，它提供 `import.meta.env` 等类型。

测试项目可能有：

```json
{
  "compilerOptions": {
    "types": ["vitest/globals"]
  }
}
```

不要无意识把所有全局类型都塞进来。全局类型越多，名字冲突和环境混淆的概率越高。

## 十一、baseUrl 与 paths

路径别名可以减少很深的相对路径。

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

使用：

```ts
import { getPosts } from '@/domains/post/post.api'
```

注意：`tsconfig` 的 `paths` 只告诉 TypeScript 如何理解路径。构建工具也要配置对应别名。

Vite 示例：

```ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
```

只配一边，另一边可能会报错。

## 十二、include 与 exclude

`include` 决定哪些文件参与类型检查。

```json
{
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

`exclude` 排除文件：

```json
{
  "exclude": ["node_modules", "dist"]
}
```

如果某个文件明明有错误但类型检查没发现，先确认它是否被 `include` 覆盖。

## 十三、import type

TypeScript 类型会被擦除，但导入语句可能产生运行时代码。使用 `import type` 可以明确只导入类型。

```ts
import type { User } from './user.model'

export function printUser(user: User) {
  console.log(user)
}
```

如果导入的是运行时值，就不能用 `import type`。

```ts
import { formatDate } from './format'
```

建议：

- 纯类型导入使用 `import type`。
- 类型和值混用时拆开写。
- 公共类型文件不要包含运行时副作用。

## 十四、类型擦除

TypeScript 类型不会出现在运行时代码里。

```ts
type User = {
  id: number
  name: string
}

function printUser(user: User) {
  console.log(user.name)
}
```

编译后，`User` 会消失。

所以不能这样判断：

```ts
if (value instanceof User) {
  console.log(value.name)
}
```

`User` 是类型，不是运行时构造函数。

应该使用类型守卫：

```ts
function isUser(value: unknown): value is User {
  return typeof value === 'object'
    && value !== null
    && typeof (value as User).id === 'number'
    && typeof (value as User).name === 'string'
}
```

## 十五、接口数据不可信

下面写法很常见：

```ts
const result = await response.json() as ApiResponse<User>
```

这只是类型断言，不是校验。

如果后端返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": null
}
```

TypeScript 不会在运行时阻止你访问 `result.data.name`。

更稳的方式：

- 后端接口契约稳定时，用类型声明配合测试。
- 外部来源不可信时，做运行时校验。
- 对关键数据使用 schema 校验库。
- 在 mapper 层集中兜底和转换。

类型系统不是边境海关，它不会检查每个进入运行时的数据包。它只检查你的代码如何使用这些数据。

## 十六、skipLibCheck

很多项目会配置：

```json
{
  "compilerOptions": {
    "skipLibCheck": true
  }
}
```

它会跳过依赖包声明文件的类型检查，能减少第三方类型问题带来的构建噪音，也能加快检查速度。

代价是：某些依赖类型问题可能被隐藏。

业务项目中常见做法是开启它；库项目或类型要求很高的项目，可以更谨慎。

## 十七、推荐配置方向

新前端项目可以参考：

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "types": ["vite/client"],
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"]
}
```

这不是所有项目的标准答案。配置要结合框架、构建工具、运行环境和团队迁移成本。

## 十八、练习

检查一个项目的 `tsconfig.json`：

- 是否开启 `strict`？
- 是否包含项目实际源码文件？
- 浏览器项目是否包含 `DOM` lib？
- 是否配置了路径别名？
- Vite 或构建工具是否同步配置了别名？
- 是否使用 `import type` 区分纯类型导入？
- 是否把接口响应断言误认为运行时校验？

TypeScript 工程化的核心是：类型语法、编译配置、构建工具和运行时边界要互相对齐。只学语法不看配置，就像只学法律条文不看法院在哪里，多少有点自信过头。
