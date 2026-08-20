+++
date = '2026-08-20T19:15:00+08:00'
draft = false
title = 'typeof 类型判断详解：为什么 typeof null 是 object'
+++

`typeof` 是 JavaScript 中最常见的类型判断工具之一。

你看到的：

```js
typeof value === 'object'
```

意思是：判断 `value` 的 `typeof` 结果是否为字符串 `'object'`。

但这句话不能简单理解成“判断 value 是对象”。因为在 JavaScript 里：

```js
typeof null // 'object'
typeof [] // 'object'
typeof {} // 'object'
```

也就是说，`typeof value === 'object'` 会同时命中普通对象、数组、`null`、日期对象、正则对象等很多值。它只是一个入口判断，不是精确对象判断。

如果要判断“普通非空对象”，通常要写：

```js
typeof value === 'object' && value !== null && !Array.isArray(value)
```

这就没那么优雅了。可惜，现实中的正确判断经常比想象中的漂亮答案长一点。

## 一、typeof 是什么

`typeof` 是一个一元运算符，用来返回一个值的类型描述字符串。

```js
typeof 'hello'
typeof 123
typeof true
```

它的结果是字符串：

```js
console.log(typeof 'hello') // 'string'
console.log(typeof 123) // 'number'
console.log(typeof true) // 'boolean'
```

因为返回的是字符串，所以经常这样写：

```js
if (typeof value === 'string') {
  console.log(value.trim())
}
```

注意：

```js
typeof value === 'string'
```

不是把 `value` 和 `'string'` 比较，而是先计算：

```js
typeof value
```

得到一个字符串，再和 `'string'` 比较。

## 二、typeof 的返回值

常见返回值如下：

| 表达式 | 返回值 |
| ------ | ------ |
| `typeof 'hello'` | `'string'` |
| `typeof 123` | `'number'` |
| `typeof true` | `'boolean'` |
| `typeof undefined` | `'undefined'` |
| `typeof null` | `'object'` |
| `typeof 1n` | `'bigint'` |
| `typeof Symbol()` | `'symbol'` |
| `typeof {}` | `'object'` |
| `typeof []` | `'object'` |
| `typeof function () {}` | `'function'` |

示例：

```js
console.log(typeof 'hello') // string
console.log(typeof 18) // number
console.log(typeof true) // boolean
console.log(typeof undefined) // undefined
console.log(typeof null) // object
console.log(typeof 1n) // bigint
console.log(typeof Symbol('id')) // symbol
console.log(typeof {}) // object
console.log(typeof []) // object
console.log(typeof (() => {})) // function
```

`typeof` 的返回值不是任意类型名，而是固定的一组字符串。比如数组不会返回 `'array'`。

```js
typeof [] // 'object'
```

判断数组要用：

```js
Array.isArray(value)
```

## 三、为什么 typeof null 是 object

这是 JavaScript 早期的历史遗留问题。

```js
typeof null // 'object'
```

从语义上说，`null` 表示空值，不是对象。可是 `typeof null` 返回了 `'object'`。

这也是为什么下面的判断不够安全：

```js
function isObject(value) {
  return typeof value === 'object'
}

console.log(isObject(null)) // true
```

如果你真的要判断对象，必须排除 `null`：

```js
function isObject(value) {
  return typeof value === 'object' && value !== null
}
```

这样：

```js
console.log(isObject(null)) // false
console.log(isObject({})) // true
console.log(isObject([])) // true
```

注意，数组仍然会返回 `true`，因为数组也是对象。

所以更准确地说：

```js
typeof value === 'object' && value !== null
```

判断的是“非 null 的对象类型值”，包括数组、日期、正则、普通对象等。

## 四、typeof value === 'object' 是什么

这句代码由三部分组成：

```js
typeof value === 'object'
```

拆开看：

```js
typeof value
```

得到 `value` 的类型字符串。

```js
=== 'object'
```

判断这个类型字符串是否等于 `'object'`。

例子：

```js
const value = {
  id: 1,
  name: 'Yuki'
}

if (typeof value === 'object') {
  console.log('这是 object 类型')
}
```

但下面也会进入：

```js
const value = null

if (typeof value === 'object') {
  console.log('这里也会执行')
}
```

因为：

```js
typeof null // 'object'
```

所以真实项目里，几乎总是要写：

```js
if (typeof value === 'object' && value !== null) {
  console.log('这是非 null 的 object 类型')
}
```

如果还要排除数组：

```js
if (
  typeof value === 'object' &&
  value !== null &&
  !Array.isArray(value)
) {
  console.log('更接近普通对象')
}
```

不过这仍然不能排除 `Date`、`RegExp`、`Map`、`Set` 等对象。

```js
console.log(typeof new Date()) // object
console.log(typeof /abc/) // object
console.log(typeof new Map()) // object
console.log(typeof new Set()) // object
```

`typeof` 适合做粗粒度判断，不适合做所有精确分类。工具有边界，不能因为它短就让它包办一切。

## 五、判断基础类型

`typeof` 最适合判断基础类型。

### 字符串

```js
function isString(value) {
  return typeof value === 'string'
}
```

使用：

```js
if (typeof name === 'string') {
  console.log(name.trim())
}
```

### 数字

```js
function isNumber(value) {
  return typeof value === 'number'
}
```

但要注意 `NaN`：

```js
typeof NaN // 'number'
```

如果你要判断一个有效数字：

```js
function isValidNumber(value) {
  return typeof value === 'number' && !Number.isNaN(value)
}
```

如果还要排除 `Infinity`：

```js
function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}
```

### 布尔值

```js
function isBoolean(value) {
  return typeof value === 'boolean'
}
```

这和真假值判断不同。

```js
if (value) {
  // 判断 value 转成布尔后是否为 true
}

if (typeof value === 'boolean') {
  // 判断 value 本身是不是 boolean 类型
}
```

`0`、`''`、`null` 在条件中是假值，但它们都不是 boolean。

### undefined

```js
if (typeof value === 'undefined') {
  console.log('没有值')
}
```

也可以直接：

```js
if (value === undefined) {
  console.log('没有值')
}
```

现代代码中，这两种都常见。

## 六、typeof 和未声明变量

`typeof` 有一个特殊点：对未声明变量使用时，不会报错。

```js
typeof notDeclared
```

结果是：

```text
undefined
```

但如果直接访问：

```js
notDeclared
```

会报错：

```text
ReferenceError: notDeclared is not defined
```

因此过去常见写法：

```js
if (typeof window !== 'undefined') {
  console.log('当前可能在浏览器环境')
}
```

这在同时支持浏览器和 Node.js 的代码中很常见。

例如：

```js
const isBrowser = typeof window !== 'undefined'
```

因为在 Node.js 中，`window` 可能根本没有声明。直接写：

```js
window !== undefined
```

可能会报错。

## 七、typeof 判断函数

函数的 `typeof` 结果是 `'function'`。

```js
function fn() {}

console.log(typeof fn) // function
```

箭头函数也是：

```js
const fn = () => {}

console.log(typeof fn) // function
```

常见用途是判断可选回调：

```js
function submit(input, options = {}) {
  const result = save(input)

  if (typeof options.onSuccess === 'function') {
    options.onSuccess(result)
  }

  return result
}
```

现代代码也可以使用可选链：

```js
options.onSuccess?.(result)
```

但这有一个区别：如果 `onSuccess` 存在但不是函数，`?.()` 仍然会报错。

```js
const options = {
  onSuccess: 'not function'
}

options.onSuccess?.() // TypeError
```

如果数据来源不可信，`typeof === 'function'` 更稳。

```js
if (typeof options.onSuccess === 'function') {
  options.onSuccess(result)
}
```

## 八、typeof 不能精确判断数组

数组的结果是：

```js
typeof [] // 'object'
```

所以不要写：

```js
if (typeof value === 'array') {
  // 永远不会成立
}
```

正确写法：

```js
if (Array.isArray(value)) {
  console.log('这是数组')
}
```

示例：

```js
function normalizeList(value) {
  if (Array.isArray(value)) {
    return value
  }

  return []
}
```

接口数据处理中很常见：

```js
const list = Array.isArray(response.data?.items)
  ? response.data.items
  : []
```

如果后端返回了错误结构，前端至少不会在 `.map()` 时直接崩掉。

## 九、typeof 不能区分各种对象

下面这些都是 `'object'`：

```js
typeof {} // 'object'
typeof [] // 'object'
typeof null // 'object'
typeof new Date() // 'object'
typeof /abc/ // 'object'
typeof new Map() // 'object'
typeof new Set() // 'object'
```

所以，如果你需要更精确的判断，要使用其他方法。

判断数组：

```js
Array.isArray(value)
```

判断日期：

```js
value instanceof Date
```

判断 Map：

```js
value instanceof Map
```

判断 Set：

```js
value instanceof Set
```

判断普通对象可以写一个辅助函数：

```js
function isPlainObject(value) {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const prototype = Object.getPrototypeOf(value)

  return prototype === Object.prototype || prototype === null
}
```

测试：

```js
console.log(isPlainObject({})) // true
console.log(isPlainObject(Object.create(null))) // true
console.log(isPlainObject([])) // false
console.log(isPlainObject(null)) // false
console.log(isPlainObject(new Date())) // false
```

这种判断适合“我要确认它是普通配置对象或普通 JSON 对象”的场景。

## 十、typeof 和 instanceof 的区别

`typeof` 判断的是粗粒度类型标签。

```js
typeof value === 'object'
typeof value === 'string'
typeof value === 'function'
```

`instanceof` 判断一个对象是否出现在某个构造函数的原型链上。

```js
const date = new Date()

console.log(date instanceof Date) // true
console.log(date instanceof Object) // true
```

数组：

```js
const list = []

console.log(list instanceof Array) // true
console.log(list instanceof Object) // true
```

但判断数组更推荐：

```js
Array.isArray(list)
```

因为它语义更明确，也能处理一些跨执行环境的边界问题。

简单对比：

| 工具 | 适合判断 |
| ---- | -------- |
| `typeof` | 基础类型、函数、环境变量是否存在 |
| `Array.isArray` | 数组 |
| `instanceof` | 类实例、内置对象实例 |
| `Object.getPrototypeOf` | 更精确的普通对象判断 |

## 十一、typeof 和 TypeScript 的类型收窄

如果你使用 TypeScript，`typeof` 还是一种类型收窄工具。

```ts
function format(value: string | number) {
  if (typeof value === 'string') {
    return value.trim()
  }

  return value.toFixed(2)
}
```

在：

```ts
if (typeof value === 'string')
```

这个分支里，TypeScript 知道 `value` 是 `string`。

另一个分支里，TypeScript 可以推断它是 `number`。

判断对象时也一样要排除 `null`：

```ts
function getName(value: unknown) {
  if (typeof value === 'object' && value !== null && 'name' in value) {
    return value.name
  }

  return '匿名用户'
}
```

不过上面这段在严格类型下还需要更细的类型处理。这里先理解原则：

```text
typeof object 分支里仍然可能有 null
所以要先 value !== null
```

## 十二、接口数据校验中的 typeof

接口返回的数据在运行时不可信。`typeof` 常用于做轻量校验。

```js
function normalizeUser(raw) {
  if (typeof raw !== 'object' || raw === null) {
    return null
  }

  return {
    id: typeof raw.id === 'number' ? raw.id : 0,
    name: typeof raw.name === 'string' ? raw.name : '匿名用户',
    active: typeof raw.active === 'boolean' ? raw.active : false
  }
}
```

但这里有一个实际问题：当 `raw` 的类型是 `object` 时，JavaScript 能访问 `raw.id`；TypeScript 中如果 `raw` 是 `unknown`，则还要做更严格的类型收窄。

纯 JavaScript 里，这种写法可以避免很多运行时错误。

数组字段也要单独判断：

```js
function normalizePost(raw) {
  if (typeof raw !== 'object' || raw === null) {
    return null
  }

  return {
    id: typeof raw.id === 'number' ? raw.id : 0,
    title: typeof raw.title === 'string' ? raw.title : '未命名文章',
    tags: Array.isArray(raw.tags) ? raw.tags : []
  }
}
```

如果校验规则复杂，应该使用 schema 校验库，而不是手写一大堆 `typeof`。工具要用在适合的位置，不要把小刀当施工队。

## 十三、常见判断函数

可以封装一些简单工具。

```js
function isString(value) {
  return typeof value === 'string'
}

function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function isBoolean(value) {
  return typeof value === 'boolean'
}

function isFunction(value) {
  return typeof value === 'function'
}

function isObjectLike(value) {
  return typeof value === 'object' && value !== null
}

function isPlainObject(value) {
  if (!isObjectLike(value)) {
    return false
  }

  const prototype = Object.getPrototypeOf(value)

  return prototype === Object.prototype || prototype === null
}
```

使用：

```js
if (isPlainObject(config)) {
  console.log(config)
}
```

函数名要准确。不要把：

```js
typeof value === 'object' && value !== null
```

封装成：

```js
isObject(value)
```

然后在团队里默认它排不排除数组、日期、Map，全靠大家心照不宣。心照不宣在代码里通常意味着将来会有人照不见。

更好的命名：

```js
isObjectLike(value)
isPlainObject(value)
```

## 十四、常见误区

### 1. 忘记 null

错误：

```js
if (typeof value === 'object') {
  console.log(value.name)
}
```

如果 `value` 是 `null`，会报错。

更稳：

```js
if (typeof value === 'object' && value !== null) {
  console.log(value.name)
}
```

### 2. 用 typeof 判断数组

错误：

```js
typeof list === 'array'
```

正确：

```js
Array.isArray(list)
```

### 3. 以为 typeof NaN 不是 number

```js
typeof NaN // 'number'
```

有效数字判断：

```js
typeof value === 'number' && Number.isFinite(value)
```

### 4. 把真假值判断当类型判断

```js
if (value) {
  // 这里只能说明 value 转成布尔后是真
}
```

这不能说明 `value` 是什么类型。

```js
if (typeof value === 'string') {
  // 这里才能说明它是 string
}
```

### 5. 忘记函数是 function

```js
typeof function () {} // 'function'
```

虽然函数也是对象，但 `typeof` 对函数返回的是 `'function'`，不是 `'object'`。

## 十五、练习

判断下面输出：

```js
console.log(typeof 'hello')
console.log(typeof 123)
console.log(typeof NaN)
console.log(typeof true)
console.log(typeof undefined)
console.log(typeof null)
console.log(typeof {})
console.log(typeof [])
console.log(typeof (() => {}))
```

答案：

```text
string
number
number
boolean
undefined
object
object
object
function
```

实现一个 `getValueKind`：

```js
function getValueKind(value) {
  if (value === null) {
    return 'null'
  }

  if (Array.isArray(value)) {
    return 'array'
  }

  return typeof value
}
```

测试：

```js
console.log(getValueKind(null)) // null
console.log(getValueKind([])) // array
console.log(getValueKind({})) // object
console.log(getValueKind('hello')) // string
console.log(getValueKind(() => {})) // function
```

最后记住一句话：

> `typeof` 很适合判断基础类型和函数，但判断对象时必须小心：`null`、数组、日期、Map、Set 的 `typeof` 都可能是 `'object'`。真正需要精确分类时，要配合 `value !== null`、`Array.isArray`、`instanceof` 或更明确的工具函数。
