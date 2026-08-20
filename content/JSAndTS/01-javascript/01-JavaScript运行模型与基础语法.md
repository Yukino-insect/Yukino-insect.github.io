+++
date = '2026-08-19T18:29:00+08:00'
draft = false
title = 'JavaScript 运行模型与基础语法：变量、类型和控制流'
+++

JavaScript 是前端的基础语言。它既可以运行在浏览器中，也可以运行在 Node.js 中。浏览器负责页面、DOM、网络和用户交互；Node.js 负责本地脚本、构建工具和服务端能力。语言本身则提供变量、类型、函数、对象、异步等机制。

这一篇先解决最基础的问题：代码怎么执行，变量怎么存，类型怎么判断，流程怎么控制。

## 一、代码在哪里运行

JavaScript 常见运行环境有两个：

- 浏览器：执行页面脚本，操作 DOM，发起请求，响应用户点击。
- Node.js：执行本地脚本、构建命令、工具链代码。

同样是 JavaScript，不同环境提供的全局对象不同。

| 环境 | 常见全局能力 |
| ---- | ------------ |
| 浏览器 | `window`、`document`、`fetch`、`localStorage` |
| Node.js | `process`、`Buffer`、`fs`、`path` |

所以你在浏览器里能写 `document.querySelector`，在普通 Node 脚本里就不能直接写。不要把语言能力和环境能力混为一谈。

## 二、变量声明

现代 JavaScript 主要使用 `const` 和 `let`。

```js
const appName = 'blog'
let count = 0

count = count + 1
```

基本规则：

- 默认使用 `const`。
- 需要重新赋值时使用 `let`。
- 不建议使用 `var`，它有函数作用域和变量提升，容易制造误会。

`const` 限制的是变量绑定，不是对象内容。

```js
const user = {
  name: 'Yuki',
  age: 18
}

user.age = 19
```

上面代码可以执行，因为 `user` 仍然指向同一个对象。不能做的是重新赋值：

```js
user = {}
```

## 三、基础类型

JavaScript 有几类常见基础类型：

| 类型 | 示例 | 说明 |
| ---- | ---- | ---- |
| `string` | `'hello'` | 字符串 |
| `number` | `18`、`3.14` | 整数和小数都属于 number |
| `boolean` | `true`、`false` | 布尔值 |
| `undefined` | `undefined` | 声明了但没有值 |
| `null` | `null` | 主动表示空 |
| `bigint` | `1n` | 大整数 |
| `symbol` | `Symbol()` | 唯一标识 |

用 `typeof` 可以查看类型：

```js
typeof 'hello' // 'string'
typeof 18 // 'number'
typeof true // 'boolean'
typeof undefined // 'undefined'
typeof null // 'object'
```

`typeof null` 返回 `'object'` 是历史遗留问题。记住即可，不必试图从设计美学上原谅它。

## 四、真假值

JavaScript 在条件判断中会把值转换成布尔值。下面这些是假值：

```text
false
0
''
null
undefined
NaN
```

其他大多数值都是真值，包括空数组和空对象。

```js
if ([]) {
  console.log('空数组也是真值')
}

if ({}) {
  console.log('空对象也是真值')
}
```

这在业务判断中很重要。判断列表有没有数据，不能写：

```js
if (list) {
  // 空数组也会进入
}
```

应该写：

```js
if (list.length > 0) {
  // 有数据
}
```

## 五、相等比较

推荐默认使用 `===` 和 `!==`。

```js
0 == false // true
0 === false // false
```

`==` 会做隐式转换，初学阶段只会增加不确定性。工程代码中，如果你需要转换，就显式转换。

```js
const page = Number(route.query.page ?? 1)
```

这样读代码的人能知道你确实想把字符串变成数字。

## 六、条件判断

常见写法：

```js
if (score >= 90) {
  level = 'A'
} else if (score >= 60) {
  level = 'B'
} else {
  level = 'C'
}
```

当判断基于固定枚举值时，可以使用 `switch`：

```js
switch (status) {
  case 'loading':
    text = '加载中'
    break
  case 'success':
    text = '加载完成'
    break
  case 'error':
    text = '加载失败'
    break
  default:
    text = '未知状态'
}
```

状态值越固定，越适合后续用 TypeScript 联合类型约束。

## 七、循环

遍历数组最常用的是 `for...of`：

```js
const names = ['A', 'B', 'C']

for (const name of names) {
  console.log(name)
}
```

需要下标时：

```js
for (let i = 0; i < names.length; i++) {
  console.log(i, names[i])
}
```

遍历对象可以使用 `Object.entries`：

```js
const user = {
  name: 'Yuki',
  age: 18
}

for (const [key, value] of Object.entries(user)) {
  console.log(key, value)
}
```

## 八、可选链与空值合并

真实接口数据经常有空值。可选链可以避免读取深层属性时报错。

```js
const avatar = user.profile?.avatarUrl
```

如果 `profile` 是 `null` 或 `undefined`，表达式会返回 `undefined`，不会继续访问 `avatarUrl`。

空值合并运算符 `??` 只在左侧是 `null` 或 `undefined` 时使用默认值。

```js
const pageSize = query.pageSize ?? 10
```

它和 `||` 不同：

```js
0 || 10 // 10
0 ?? 10 // 0
```

当 `0` 是合法值时，应该使用 `??`。

## 九、异常处理

用 `try...catch` 捕获可能失败的代码。

```js
try {
  const data = JSON.parse(text)
  console.log(data)
} catch (error) {
  console.error('JSON 解析失败', error)
}
```

在前端中，常见失败来源包括：

- JSON 解析失败。
- 网络请求失败。
- 接口返回业务错误。
- 本地存储数据格式不符合预期。
- 访问空对象属性。

异常处理不是为了把错误吞掉，而是为了让错误变成可展示、可恢复、可定位的状态。

## 十、练习

完成一个用户列表处理函数：

```js
function normalizeUsers(users) {
  // 过滤掉 disabled 为 true 的用户
  // 如果 nickname 为空，就使用 username
  // 返回 { label, value } 结构
}
```

参考实现：

```js
function normalizeUsers(users) {
  return users
    .filter(user => !user.disabled)
    .map(user => ({
      label: user.nickname ?? user.username,
      value: user.id
    }))
}
```

这段代码虽然短，但覆盖了数组、对象、布尔判断、空值合并和箭头函数。基础能力就是这样一点点叠起来的，并没有什么神秘仪式。
