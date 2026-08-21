+++
date = '2026-08-21T16:24:00+08:00'
draft = false
title = 'JavaScript Symbol 详解：唯一标识、对象 key 与内置协议'
+++

`Symbol` 是 JavaScript 的一种基础类型。它经常出现在对象属性、库源码、迭代器、`typeof` 判断和一些看起来很神秘的写法里。

比如：

```js
const idKey = Symbol('id')

const user = {
  name: 'Yuki',
  [idKey]: 1
}

console.log(user[idKey]) // 1
```

如果你只看表面，会觉得 `Symbol('id')` 像是创建了一个字符串 `'id'`。但它不是字符串。`Symbol` 的核心价值是：**创建一个唯一的标识值**。

先给结论：

- `Symbol` 是 JavaScript 的基础类型之一，`typeof Symbol()` 的结果是 `'symbol'`。
- 每次调用 `Symbol()` 都会创建一个全新的、唯一的值。
- `Symbol` 可以作为对象属性 key，避免和普通字符串 key 冲突。
- `Symbol` 属性不会被 `Object.keys()`、`for...in`、`JSON.stringify()` 常规枚举出来。
- `Symbol.for()` 可以从全局注册表中创建或复用 Symbol。
- JavaScript 内置了一批 well-known symbols，用来定制语言内部行为，例如 `Symbol.iterator`、`Symbol.toPrimitive`、`Symbol.toStringTag`。

一句话：

> `Symbol` 不是“特殊字符串”，而是“唯一标识”；它既能当对象属性 key，也能参与 JavaScript 的一些内置协议。

## 一、Symbol 是什么

`Symbol` 是 JavaScript 的原始类型之一。

JavaScript 常见原始类型包括：

| 类型 | 示例 |
| ---- | ---- |
| `string` | `'hello'` |
| `number` | `123` |
| `boolean` | `true` |
| `undefined` | `undefined` |
| `bigint` | `123n` |
| `symbol` | `Symbol('id')` |
| `null` | `null` |

注意，`null` 用 `typeof` 判断会得到 `'object'`，这是历史遗留问题，不代表它真的是普通对象。

创建 Symbol：

```js
const key = Symbol()

console.log(typeof key) // symbol
```

可以传入描述：

```js
const key = Symbol('id')

console.log(key) // Symbol(id)
```

这里的 `'id'` 只是描述，方便调试。它不是这个 Symbol 的实际值，也不会让两个 Symbol 相等。

```js
const a = Symbol('id')
const b = Symbol('id')

console.log(a === b) // false
```

哪怕描述一样，`a` 和 `b` 也是两个不同的 Symbol。

这就是 Symbol 最重要的特性：

```text
每次调用 Symbol()，都会得到一个唯一的新值。
```

## 二、Symbol 不是字符串

很多初学者会把：

```js
Symbol('id')
```

理解成某种特殊字符串。这个理解不对。

看下面的比较：

```js
const key = Symbol('id')

console.log(key === 'id') // false
console.log(typeof key) // symbol
console.log(typeof 'id') // string
```

Symbol 不能和字符串直接拼接：

```js
const key = Symbol('id')

console.log('key is ' + key) // TypeError
```

如果确实要转成字符串，需要显式转换：

```js
const key = Symbol('id')

console.log(String(key)) // Symbol(id)
console.log(key.toString()) // Symbol(id)
```

为什么不允许隐式拼接？因为 Symbol 的定位是唯一标识，不是展示文本。语言在这里表现得很强硬，倒也不是坏事。要是所有东西都能悄悄变成字符串，错误就会变得格外会隐藏自己。

## 三、Symbol 的描述 description

创建 Symbol 时传入的参数叫描述。

```js
const key = Symbol('user id')

console.log(key.description) // user id
```

描述只用于调试和展示，不参与唯一性判断。

```js
const a = Symbol('same')
const b = Symbol('same')

console.log(a.description) // same
console.log(b.description) // same
console.log(a === b) // false
```

可以把描述理解成标签纸，不是身份证号。两张标签纸都写着 `same`，也不代表贴着它们的东西是同一个。

如果不传描述：

```js
const key = Symbol()

console.log(key.description) // undefined
```

## 四、Symbol 可以作为对象属性 key

普通对象的属性 key 主要是两类：

- 字符串。
- Symbol。

例如：

```js
const idKey = Symbol('id')

const user = {
  name: 'Yuki',
  [idKey]: 1
}

console.log(user.name) // Yuki
console.log(user[idKey]) // 1
```

注意这里必须使用计算属性名：

```js
const user = {
  [idKey]: 1
}
```

如果写成：

```js
const user = {
  idKey: 1
}
```

那属性名就是字符串 `'idKey'`，不是变量 `idKey` 对应的 Symbol。

读取 Symbol 属性时，也要用方括号：

```js
console.log(user[idKey])
```

不能写：

```js
console.log(user.idKey)
```

点语法里的 `idKey` 会被当作字符串属性名，而不是 Symbol 变量。

## 五、Symbol key 的意义：避免命名冲突

假设你在给一个对象追加内部状态：

```js
const user = {
  id: 1,
  name: 'Yuki'
}

user.id = 'internal-id'
```

这很危险，因为你覆盖了业务字段 `id`。

可以用 Symbol 创建一个不会和字符串 key 冲突的属性：

```js
const internalIdKey = Symbol('internal id')

const user = {
  id: 1,
  name: 'Yuki'
}

user[internalIdKey] = 'internal-id'

console.log(user.id) // 1
console.log(user[internalIdKey]) // internal-id
```

即使描述也是 `'id'`，它也不会和字符串属性 `'id'` 冲突：

```js
const idKey = Symbol('id')

const user = {
  id: 1,
  [idKey]: 'symbol id'
}

console.log(user.id) // 1
console.log(user[idKey]) // symbol id
```

这就是 Symbol 常见用途之一：

```text
给对象挂载不容易和外部字段冲突的属性。
```

但不要误会：Symbol 属性不是绝对私有。别人如果拿到了这个 Symbol，也能访问对应属性。

```js
const secretKey = Symbol('secret')

const user = {
  [secretKey]: 'hidden value'
}

console.log(user[secretKey]) // hidden value
```

它是“难以意外冲突”，不是“绝对不可访问”。要真正私有字段，现代 JavaScript 有 `#privateField`。

## 六、Symbol 属性不会被常规枚举拿到

看这个对象：

```js
const idKey = Symbol('id')

const user = {
  id: 1,
  name: 'Yuki',
  [idKey]: 'symbol id'
}
```

`Object.keys()` 只返回字符串 key：

```js
console.log(Object.keys(user)) // ['id', 'name']
```

`Object.entries()` 也是：

```js
console.log(Object.entries(user))
```

结果：

```text
[['id', 1], ['name', 'Yuki']]
```

`for...in` 也不会遍历 Symbol key：

```js
for (const key in user) {
  console.log(key)
}
```

输出：

```text
id
name
```

如果要拿到 Symbol 属性，需要用：

```js
console.log(Object.getOwnPropertySymbols(user)) // [Symbol(id)]
```

如果想同时拿到字符串 key 和 Symbol key，可以用：

```js
console.log(Reflect.ownKeys(user)) // ['id', 'name', Symbol(id)]
```

所以：

| 方法 | 是否包含字符串 key | 是否包含 Symbol key |
| ---- | ------------------ | ------------------- |
| `Object.keys(obj)` | 是 | 否 |
| `Object.values(obj)` | 是 | 否 |
| `Object.entries(obj)` | 是 | 否 |
| `for...in` | 是，且会遍历可枚举原型属性 | 否 |
| `Object.getOwnPropertyNames(obj)` | 是 | 否 |
| `Object.getOwnPropertySymbols(obj)` | 否 | 是 |
| `Reflect.ownKeys(obj)` | 是 | 是 |

这也是为什么 Symbol 适合放一些内部扩展信息。它不会轻易出现在普通枚举逻辑里。轻易这两个字很重要，因为不是拿不到，只是不在默认路径里。

## 七、JSON.stringify 会忽略 Symbol

`JSON.stringify()` 会忽略 Symbol key。

```js
const idKey = Symbol('id')

const user = {
  id: 1,
  name: 'Yuki',
  [idKey]: 'symbol id'
}

console.log(JSON.stringify(user))
```

输出：

```json
{"id":1,"name":"Yuki"}
```

如果属性值本身是 Symbol，也会被忽略或变成 `null`，取决于它所在的位置。

对象属性值是 Symbol：

```js
const obj = {
  id: Symbol('id')
}

console.log(JSON.stringify(obj))
```

输出：

```json
{}
```

数组元素是 Symbol：

```js
const list = [Symbol('id')]

console.log(JSON.stringify(list))
```

输出：

```json
[null]
```

这说明 Symbol 不适合作为需要传输或持久化的数据值。接口数据、数据库数据、本地存储数据，最好使用字符串、数字、布尔值、对象、数组这些 JSON 能表达的结构。

Symbol 更适合运行时内部标识，不适合跨网络传递。让它去做 JSON 的工作，就像让校服去参加晚宴，倒不是不能出现，只是场合不对。

## 八、Symbol 不能用 new 创建

`Symbol` 是函数，但不能作为构造函数使用。

```js
const key = Symbol('id')
```

不能写：

```js
const key = new Symbol('id') // TypeError
```

因为 Symbol 是原始值，不是普通对象实例。

不过可以用 `Object()` 把 Symbol 包装成对象：

```js
const key = Symbol('id')
const boxed = Object(key)

console.log(typeof key) // symbol
console.log(typeof boxed) // object
```

日常代码里几乎不需要这么做。知道有这回事即可，不要为了显得高级而包装它。代码不是展示柜。

## 九、Symbol.for 和全局注册表

普通 `Symbol()` 每次都会创建新值：

```js
const a = Symbol('id')
const b = Symbol('id')

console.log(a === b) // false
```

如果你希望根据同一个字符串拿到同一个 Symbol，可以用 `Symbol.for()`：

```js
const a = Symbol.for('app.user.id')
const b = Symbol.for('app.user.id')

console.log(a === b) // true
```

`Symbol.for(key)` 会先查全局 Symbol 注册表：

```text
如果 key 已存在 -> 返回已有 Symbol
如果 key 不存在 -> 创建一个新的 Symbol 并登记
```

可以用 `Symbol.keyFor()` 反查注册表中的 key：

```js
const key = Symbol.for('app.user.id')

console.log(Symbol.keyFor(key)) // app.user.id
```

但普通 `Symbol()` 创建的值不在全局注册表里：

```js
const localKey = Symbol('app.user.id')

console.log(Symbol.keyFor(localKey)) // undefined
```

使用建议：

| 场景 | 推荐 |
| ---- | ---- |
| 只在当前模块内部使用 | `Symbol()` |
| 多个模块需要共享同一个 Symbol | `Symbol.for()` |
| 需要避免全局命名污染 | 优先 `Symbol()` |
| 需要跨模块约定协议 key | 可以考虑 `Symbol.for()` |

不要随便把所有 Symbol 都写成 `Symbol.for()`。全局注册表是全局的，既然是全局，就要承担命名冲突和长期占用的责任。随手往全局扔东西，通常不是成熟，是懒。

## 十、Symbol 和常量

有时会用 Symbol 表示唯一常量：

```js
const STATUS_LOADING = Symbol('loading')
const STATUS_SUCCESS = Symbol('success')
const STATUS_ERROR = Symbol('error')

let status = STATUS_LOADING

if (status === STATUS_LOADING) {
  console.log('加载中')
}
```

这样做的好处是不会和普通字符串混淆：

```js
status = 'loading'

console.log(status === STATUS_LOADING) // false
```

但在业务代码中，字符串常量也很常见：

```js
const STATUS_LOADING = 'loading'
const STATUS_SUCCESS = 'success'
const STATUS_ERROR = 'error'
```

两种方式怎么选？

| 需求 | 推荐 |
| ---- | ---- |
| 需要序列化、传接口、存本地 | 字符串 |
| 需要展示、日志、调试清晰 | 字符串 |
| 只在运行时内部比较 | Symbol 可以考虑 |
| 担心和外部字符串混用 | Symbol 可以考虑 |

前端业务状态通常更适合字符串，因为它要和接口、路由、缓存、调试工具一起工作。Symbol 可以用，但不要为了“唯一”牺牲可读性和可传输性。

## 十一、Symbol 和 Map 的区别

`Symbol` 是一个值，可以作为对象 key。

`Map` 是一种键值集合。

这两个概念不要混。

```js
const key = Symbol('id')

const obj = {
  [key]: 1
}

console.log(obj[key]) // 1
```

这是用 Symbol 作为对象属性 key。

而 `Map` 是容器：

```js
const key = Symbol('id')
const map = new Map()

map.set(key, 1)

console.log(map.get(key)) // 1
```

`Map` 的 key 可以是任意值，包括 Symbol、对象、函数、数字、字符串。

```js
const map = new Map()

map.set(Symbol('id'), 'symbol key')
map.set({ id: 1 }, 'object key')
map.set(1, 'number key')
```

如果你只是需要一个不会冲突的对象属性名，可以用 Symbol。如果你需要维护一组动态键值关系，更应该考虑 `Map`。

## 十二、内置 Symbol：well-known symbols

JavaScript 内置了一批特殊 Symbol，称为 well-known symbols。它们不是普通业务常量，而是语言用来开放内部协议的钩子。

常见的有：

| Symbol | 作用 |
| ------ | ---- |
| `Symbol.iterator` | 定义对象如何被迭代 |
| `Symbol.asyncIterator` | 定义对象如何被异步迭代 |
| `Symbol.toPrimitive` | 定义对象如何转换为原始值 |
| `Symbol.toStringTag` | 自定义 `Object.prototype.toString` 的标签 |
| `Symbol.hasInstance` | 自定义 `instanceof` 行为 |
| `Symbol.match` | 定义对象如何参与 `String.prototype.match` |
| `Symbol.replace` | 定义对象如何参与 `String.prototype.replace` |
| `Symbol.search` | 定义对象如何参与 `String.prototype.search` |
| `Symbol.split` | 定义对象如何参与 `String.prototype.split` |
| `Symbol.isConcatSpreadable` | 定义对象被 `Array.prototype.concat` 时是否展开 |
| `Symbol.species` | 定义派生对象构造器 |

初学阶段不用把它们全背下来。先重点理解三个：

```text
Symbol.iterator
Symbol.toPrimitive
Symbol.toStringTag
```

它们最能体现 Symbol 和语言协议之间的关系。

## 十三、Symbol.iterator：让对象可以被遍历

数组可以被 `for...of` 遍历：

```js
const list = ['a', 'b', 'c']

for (const item of list) {
  console.log(item)
}
```

因为数组内部有 `Symbol.iterator` 方法：

```js
const list = ['a', 'b', 'c']

console.log(typeof list[Symbol.iterator]) // function
```

普通对象默认不能被 `for...of` 遍历：

```js
const user = {
  id: 1,
  name: 'Yuki'
}

for (const item of user) {
  console.log(item)
}
```

这会报错，因为普通对象默认没有迭代器。

你可以给对象定义 `Symbol.iterator`：

```js
const range = {
  start: 1,
  end: 3,
  [Symbol.iterator]() {
    let current = this.start
    const end = this.end

    return {
      next() {
        if (current <= end) {
          return {
            value: current++,
            done: false
          }
        }

        return {
          value: undefined,
          done: true
        }
      }
    }
  }
}

for (const value of range) {
  console.log(value)
}
```

输出：

```text
1
2
3
```

这说明 `for...of` 不是随便遍历对象属性。它会寻找对象上的 `Symbol.iterator` 方法，并按照迭代器协议取值。

也可以用生成器函数简化：

```js
const range = {
  start: 1,
  end: 3,
  *[Symbol.iterator]() {
    for (let value = this.start; value <= this.end; value++) {
      yield value
    }
  }
}

console.log([...range]) // [1, 2, 3]
```

`Symbol.iterator` 是理解展开语法、`for...of`、数组解构、`Map`、`Set` 的关键之一。

```js
const set = new Set(['js', 'vue'])

console.log([...set]) // ['js', 'vue']
```

`Set` 能被展开，是因为它是可迭代对象。

## 十四、Symbol.toPrimitive：自定义原始值转换

对象在某些场景下会被转换成原始值，比如参与加法或字符串转换。

```js
const user = {
  name: 'Yuki'
}

console.log(String(user)) // [object Object]
```

可以用 `Symbol.toPrimitive` 自定义转换行为：

```js
const score = {
  value: 100,
  [Symbol.toPrimitive](hint) {
    if (hint === 'number') {
      return this.value
    }

    if (hint === 'string') {
      return `Score(${this.value})`
    }

    return this.value
  }
}

console.log(Number(score)) // 100
console.log(String(score)) // Score(100)
console.log(score + 1) // 101
```

`hint` 表示转换倾向，常见值是：

| hint | 含义 |
| ---- | ---- |
| `'number'` | 倾向转成数字 |
| `'string'` | 倾向转成字符串 |
| `'default'` | 默认转换倾向 |

这个能力很强，但业务代码里要谨慎使用。因为它会让对象在不同表达式里表现得像不同类型。写得漂亮时像魔法，调试时也会像魔法。区别只在于你当时是不是清醒。

普通业务对象不建议随便定义 `Symbol.toPrimitive`。库、框架、日期/金额/数学对象这类封装场景更适合它。

## 十五、Symbol.toStringTag：自定义类型标签

你可能见过这种判断：

```js
Object.prototype.toString.call([])
```

输出：

```text
[object Array]
```

对象可以用 `Symbol.toStringTag` 自定义这个标签：

```js
const user = {
  [Symbol.toStringTag]: 'User'
}

console.log(Object.prototype.toString.call(user))
```

输出：

```text
[object User]
```

很多内置对象也有自己的标签：

```js
console.log(Object.prototype.toString.call(new Map())) // [object Map]
console.log(Object.prototype.toString.call(new Set())) // [object Set]
```

`Symbol.toStringTag` 可以改善调试和类型展示，但它不应该被过度当作安全可靠的类型判断。

因为别人也可以伪造：

```js
const fakeMap = {
  [Symbol.toStringTag]: 'Map'
}

console.log(Object.prototype.toString.call(fakeMap)) // [object Map]
console.log(fakeMap instanceof Map) // false
```

所以它更像“标签”，不是身份证明。标签这种东西，最大的风险就是有人以为贴上去就是真的。

## 十六、Symbol.hasInstance：自定义 instanceof

`instanceof` 默认会检查构造函数的 `prototype` 是否出现在对象的原型链上。

```js
class User {}

const user = new User()

console.log(user instanceof User) // true
```

可以通过 `Symbol.hasInstance` 自定义判断逻辑：

```js
class EvenNumber {
  static [Symbol.hasInstance](value) {
    return typeof value === 'number' && value % 2 === 0
  }
}

console.log(2 instanceof EvenNumber) // true
console.log(3 instanceof EvenNumber) // false
```

这段代码很有趣，但在业务代码里通常不建议这么写。因为大多数人看到 `instanceof`，会自然以为它在判断原型链。你突然改变规则，就等于让熟悉的语法变得不熟悉。

可以了解它，但不要轻易把它作为日常建模方式。

## 十七、Symbol.isConcatSpreadable

`Array.prototype.concat()` 默认会展开数组：

```js
const result = [1, 2].concat([3, 4])

console.log(result) // [1, 2, 3, 4]
```

可以用 `Symbol.isConcatSpreadable` 控制是否展开。

让数组不展开：

```js
const list = [3, 4]

list[Symbol.isConcatSpreadable] = false

console.log([1, 2].concat(list)) // [1, 2, [3, 4]]
```

让类数组对象展开：

```js
const arrayLike = {
  0: 'a',
  1: 'b',
  length: 2,
  [Symbol.isConcatSpreadable]: true
}

console.log(['start'].concat(arrayLike)) // ['start', 'a', 'b']
```

这种能力在库源码里更常见。业务代码里如果只是想合并数组，用展开语法通常更清楚：

```js
const result = [1, 2, ...[3, 4]]
```

## 十八、Symbol.match 等字符串协议

一些字符串方法会读取对象上的特殊 Symbol。

例如 `String.prototype.match()` 会看对象是否实现了 `Symbol.match`：

```js
const matcher = {
  [Symbol.match](text) {
    return text.includes('js') ? ['js'] : null
  }
}

console.log('learn js'.match(matcher)) // ['js']
console.log('learn css'.match(matcher)) // null
```

类似的还有：

- `Symbol.replace` 对应 `replace`。
- `Symbol.search` 对应 `search`。
- `Symbol.split` 对应 `split`。

这些 Symbol 允许对象参与字符串方法的内部流程。

不过平时你大概率会直接用正则：

```js
console.log('learn js'.match(/js/))
```

理解这些协议主要是为了读懂源码和规范行为，不是为了把每个字符串处理都写成自定义对象。能用直白写法解决的问题，就不要特意绕过人类阅读能力。

## 十九、Symbol.species

`Symbol.species` 用来指定派生对象使用哪个构造器。

看一个例子：

```js
class MyArray extends Array {
  static get [Symbol.species]() {
    return Array
  }
}

const list = new MyArray(1, 2, 3)
const mapped = list.map(item => item * 2)

console.log(mapped instanceof MyArray) // false
console.log(mapped instanceof Array) // true
```

如果不指定 `Symbol.species`，某些数组方法可能会返回子类实例。指定后，可以让派生结果回到普通 `Array`。

这个知识点偏底层，主要出现在继承内置类、库设计、框架源码中。普通业务代码很少需要它。知道它存在即可，不需要每天把它请出来证明自己懂 JavaScript。

## 二十、Symbol 和私有属性

Symbol 常被误认为可以实现真正私有属性。

例如：

```js
const passwordKey = Symbol('password')

class User {
  constructor(name, password) {
    this.name = name
    this[passwordKey] = password
  }

  checkPassword(password) {
    return this[passwordKey] === password
  }
}

const user = new User('Yuki', '123456')

console.log(user.name) // Yuki
console.log(user.password) // undefined
```

看起来 `password` 被隐藏了。

但它并不是真正私有：

```js
const symbols = Object.getOwnPropertySymbols(user)

console.log(user[symbols[0]]) // 123456
```

所以 Symbol 更适合表达：

```text
不希望和普通属性冲突
不希望被常规枚举扫出来
```

不适合表达：

```text
绝对禁止外部访问
```

真正的私有字段应该用：

```js
class User {
  #password

  constructor(name, password) {
    this.name = name
    this.#password = password
  }

  checkPassword(password) {
    return this.#password === password
  }
}
```

外部直接访问：

```js
user.#password
```

会产生语法错误。

当然，前端代码里也不要真的把敏感密码放在对象里长期保存。语法能隐藏字段，不代表安全问题就从现实世界里消失了。

## 二十一、Symbol 属性和展开语法

对象展开会复制可枚举的自有属性，包括可枚举的 Symbol 属性。

```js
const idKey = Symbol('id')

const user = {
  name: 'Yuki',
  [idKey]: 1
}

const copy = {
  ...user
}

console.log(copy.name) // Yuki
console.log(copy[idKey]) // 1
```

`Object.assign()` 也会复制可枚举的 Symbol 属性：

```js
const copy = Object.assign({}, user)

console.log(copy[idKey]) // 1
```

这点容易和 `Object.keys()` 混淆。

```js
console.log(Object.keys(user)) // ['name']
console.log(Reflect.ownKeys(user)) // ['name', Symbol(id)]
```

如果 Symbol 属性是不可枚举的，对象展开就不会复制它：

```js
const idKey = Symbol('id')
const user = {
  name: 'Yuki'
}

Object.defineProperty(user, idKey, {
  value: 1,
  enumerable: false
})

const copy = {
  ...user
}

console.log(copy[idKey]) // undefined
```

所以要分清两个问题：

```text
是不是 Symbol key？
是不是可枚举属性？
```

它们是不同维度。

## 二十二、什么时候应该使用 Symbol

适合使用 Symbol 的场景：

| 场景 | 示例 |
| ---- | ---- |
| 创建不会冲突的对象属性 key | 给对象挂内部元数据 |
| 定义模块内部唯一常量 | 内部状态标识 |
| 接入语言内置协议 | `Symbol.iterator` |
| 定制对象转换或调试标签 | `Symbol.toPrimitive`、`Symbol.toStringTag` |
| 编写库或框架内部机制 | 避免和用户字段冲突 |

不太适合使用 Symbol 的场景：

| 场景 | 更合适的选择 |
| ---- | ------------ |
| 接口字段 | 字符串 key |
| JSON 数据 | 字符串、数字、布尔、对象、数组 |
| 页面展示文本 | 字符串 |
| 需要长期持久化的状态 | 字符串或数字 |
| 团队成员都要直观看懂的业务枚举 | 字符串字面量 |

一个简单判断：

```text
需要跨系统传递 -> 不用 Symbol
只在运行时内部唯一识别 -> 可以考虑 Symbol
需要接入 JS 内置协议 -> 使用对应内置 Symbol
```

## 二十三、常见误区

### 1. 以为 Symbol('id') 等于 'id'

不等于。

```js
Symbol('id') === 'id' // false
```

`'id'` 只是描述，不是字符串值。

### 2. 以为描述相同的 Symbol 相等

不相等。

```js
Symbol('id') === Symbol('id') // false
```

每次调用 `Symbol()` 都是新值。

### 3. 以为 Symbol 属性绝对私有

不是。

```js
Object.getOwnPropertySymbols(obj)
```

可以拿到对象自己的 Symbol 属性。Symbol 只能降低意外访问和命名冲突，不提供绝对私有性。

### 4. 以为 Object.keys 能拿到所有 key

不能。

```js
Object.keys(obj)
```

只拿可枚举字符串 key。要拿 Symbol key，用：

```js
Object.getOwnPropertySymbols(obj)
```

要拿所有自有 key，用：

```js
Reflect.ownKeys(obj)
```

### 5. 以为 Symbol 能直接进 JSON

不能。

```js
JSON.stringify({ key: Symbol('id') }) // '{}'
```

Symbol 是运行时标识，不是 JSON 数据格式的一部分。

### 6. 滥用 well-known symbols

`Symbol.iterator`、`Symbol.toPrimitive` 这些能力很强，但不要把普通业务逻辑写得像语言扩展。可读性不是低级需求，它是维护代码时的最低保障。

## 二十四、练习

### 1. 判断相等

```js
const a = Symbol('id')
const b = Symbol('id')
const c = a

console.log(a === b)
console.log(a === c)
```

结果：

```text
false
true
```

### 2. 判断对象 key

```js
const idKey = Symbol('id')

const user = {
  id: 1,
  [idKey]: 2
}

console.log(user.id)
console.log(user[idKey])
console.log(Object.keys(user))
console.log(Object.getOwnPropertySymbols(user))
```

结果：

```text
1
2
['id']
[Symbol(id)]
```

### 3. 判断 JSON 结果

```js
const key = Symbol('id')

const user = {
  name: 'Yuki',
  [key]: 1,
  token: Symbol('token')
}

console.log(JSON.stringify(user))
```

结果：

```json
{"name":"Yuki"}
```

Symbol key 会被忽略，Symbol 值也不会进入对象 JSON。

### 4. 实现一个可迭代对象

```js
const todoList = {
  items: ['learn js', 'write code'],
  *[Symbol.iterator]() {
    for (const item of this.items) {
      yield item
    }
  }
}

console.log([...todoList])
```

结果：

```text
['learn js', 'write code']
```

## 二十五、总结

Symbol 可以这样记：

```text
Symbol()                  -> 创建一个唯一 Symbol
Symbol('id')              -> 创建带描述的唯一 Symbol
typeof Symbol()           -> 'symbol'
Symbol.for('key')         -> 从全局注册表创建或复用 Symbol
Symbol.keyFor(symbol)     -> 查询全局注册表中的 key
obj[symbolKey]            -> 用 Symbol 作为对象属性 key
Object.getOwnPropertySymbols(obj) -> 获取对象自己的 Symbol key
Reflect.ownKeys(obj)      -> 获取字符串 key 和 Symbol key
Symbol.iterator           -> 定义对象如何被迭代
Symbol.toPrimitive        -> 定义对象如何转原始值
Symbol.toStringTag        -> 定义对象的 toString 标签
```

最后用一句话收束：

> Symbol 是 JavaScript 中用于创建唯一标识的原始类型；它常用于避免对象属性名冲突，也通过 well-known symbols 暴露了迭代、类型标签、原始值转换等语言内部协议。

日常业务代码里，不要为了显得“底层”而滥用 Symbol。真正需要它时，它很好用；不需要它时，普通字符串和普通对象往往更清楚。工具本身没有虚荣心，虚荣的是使用工具的人。
