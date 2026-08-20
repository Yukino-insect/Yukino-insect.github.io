+++
date = '2026-08-20T19:14:00+08:00'
draft = false
title = 'JavaScript 对象、类、new 与集合容器：从 {} 到 Map 和 Set'
+++

JavaScript 可以使用 `new`，也可以直接用 `{}` 创建对象。它也有 `Array`、`Map`、`Set` 这样的集合容器。

这几个事实放在一起，很容易让人困惑：JavaScript 到底能不能面向对象？`{}` 是不是类似 Java 里的 `Map`？数组是不是类似 `List`？什么时候该用普通对象，什么时候该用 `Map` 和 `Set`？

先给结论：

- JavaScript 可以面向对象，但它的底层模型是**原型**，不是传统 class-only 模型。
- `{}` 是对象字面量，常用来描述业务实体或记录键值，但它不完全等同于 `Map`。
- JavaScript 没有内置叫 `List` 的容器，通常用 `Array` 表示有序列表。
- 现代 JavaScript 有 `Array`、普通对象、`Map`、`Set`、`WeakMap`、`WeakSet` 等常用容器。

如果你从 Java、C#、Python 这类语言转过来，最好先把“对象”和“Map”分开理解。不然你会把 `{}` 用得太宽，然后在某天遇到奇怪 key、原型属性或遍历顺序时，收到语言温柔但坚定的提醒。

## 一、JavaScript 可以面向对象吗

可以。

JavaScript 支持面向对象编程，常见能力包括：

- 对象。
- 构造函数。
- `new`。
- 原型。
- `class`。
- 继承。
- 方法。
- 封装。
- 多态风格的调用。

例如用 `class` 定义一个用户类：

```js
class User {
  constructor(id, name) {
    this.id = id
    this.name = name
  }

  greet() {
    return `你好，我是 ${this.name}`
  }
}

const user = new User(1, 'Yuki')

console.log(user.greet())
```

输出：

```text
你好，我是 Yuki
```

这看起来很像其他语言里的类。但要注意：JavaScript 的 `class` 本质上是基于原型机制的语法。它让代码更像传统类语法，但底层仍然离不开原型链。

## 二、对象字面量 `{}`

最常见的对象创建方式是对象字面量：

```js
const user = {
  id: 1,
  name: 'Yuki',
  active: true
}
```

对象通常用来描述一组相关属性。

```js
const post = {
  id: 100,
  title: 'JavaScript 对象',
  author: {
    id: 1,
    name: 'Yuki'
  },
  tags: ['js', 'frontend']
}
```

读取属性：

```js
console.log(post.title)
console.log(post['title'])
```

修改属性：

```js
post.title = '新的标题'
post.likeCount = 10
```

删除属性：

```js
delete post.likeCount
```

对象字面量适合表达业务实体：

```text
用户
文章
评论
订单
配置项
接口响应
```

它的核心不是“容器”，而是“结构化数据”。

## 三、`{}` 像不像 Map

普通对象确实可以当键值表使用。

```js
const countMap = {}

countMap.apple = 2
countMap.orange = 3

console.log(countMap.apple) // 2
```

也可以用动态 key：

```js
const key = 'apple'

countMap[key] = 2
```

从这个角度看，`{}` 有点像 Map。

但它不是专门的 `Map` 容器。普通对象和 `Map` 有几个关键差异：

| 对比 | 普通对象 `{}` | `Map` |
| ---- | ------------- | ----- |
| 主要用途 | 表示结构化对象、记录 | 专门的键值集合 |
| key 类型 | 字符串或 Symbol | 任意值都可以作为 key |
| 原型 | 默认有原型链 | 没有对象原型属性干扰 |
| 大小 | 需要 `Object.keys(obj).length` | 直接用 `map.size` |
| 遍历 | `Object.keys`、`Object.entries` | `map.keys()`、`map.values()`、`map.entries()` |
| JSON | 天然适合 JSON | 需要转换 |

对象的 key 会被转换成字符串或 Symbol。

```js
const obj = {}

obj[1] = 'number key'
obj['1'] = 'string key'

console.log(obj)
```

结果里只有一个 key：

```js
{
  '1': 'string key'
}
```

因为数字 `1` 作为对象属性名时会变成字符串 `'1'`。

`Map` 不会这样：

```js
const map = new Map()

map.set(1, 'number key')
map.set('1', 'string key')

console.log(map.get(1)) // number key
console.log(map.get('1')) // string key
```

所以：`{}` 可以做简单字典，但当你需要真正的键值集合时，`Map` 更合适。

## 四、对象属性 key 的类型

普通对象的属性 key 主要有两类：

- 字符串。
- Symbol。

```js
const idKey = Symbol('id')

const user = {
  name: 'Yuki',
  [idKey]: 1
}

console.log(user.name)
console.log(user[idKey])
```

即使你写数字 key：

```js
const obj = {
  1: 'one'
}
```

它实际也会作为字符串属性名处理：

```js
console.log(obj['1']) // one
console.log(obj[1]) // one
```

数组索引看起来像数字，但属性名层面也和字符串属性有关。只是数组对非负整数索引做了特殊处理，并维护 `length`。

这就是为什么普通对象适合描述字段名固定或大致固定的数据，而不是任意 key 的映射关系。

## 五、Object.create(null)

如果你确实想用对象做纯字典，可以使用：

```js
const dict = Object.create(null)

dict.apple = 2
dict.orange = 3
```

这个对象没有默认原型。

```js
console.log(Object.getPrototypeOf(dict)) // null
```

它可以避免一些原型属性干扰。

但这类写法不如 `Map` 常见。现代代码里，如果你明确需要键值集合，优先考虑 `Map`。`Object.create(null)` 更像是低层技巧，不是日常首选。

## 六、`new` 做了什么

`new` 用来基于构造函数或类创建对象。

先看构造函数写法：

```js
function User(id, name) {
  this.id = id
  this.name = name
}

User.prototype.greet = function () {
  return `你好，我是 ${this.name}`
}

const user = new User(1, 'Yuki')

console.log(user.greet())
```

执行：

```js
new User(1, 'Yuki')
```

大致会发生：

```text
创建一个新对象
 -> 把新对象的原型指向 User.prototype
 -> 用 this 指向这个新对象，执行 User 函数
 -> 如果构造函数没有显式返回对象，就返回这个新对象
```

所以构造函数里的：

```js
this.id = id
this.name = name
```

是在给新对象添加属性。

如果忘记 `new`：

```js
const user = User(1, 'Yuki')
```

在严格模式下，`this` 是 `undefined`，通常会报错。非严格模式下可能污染全局对象，更糟。糟糕不是因为报错，而是因为它有时不报错。

## 七、class 语法

现代 JavaScript 更常用 `class` 写面向对象结构。

```js
class User {
  constructor(id, name) {
    this.id = id
    this.name = name
  }

  greet() {
    return `你好，我是 ${this.name}`
  }
}

const user = new User(1, 'Yuki')
```

`constructor` 是构造方法。使用 `new` 时会执行它。

```js
const user = new User(1, 'Yuki')
```

类方法会放在原型上，而不是每个实例单独复制一份。

```js
console.log(user.greet === User.prototype.greet) // true
```

这有利于节省内存，也让所有实例共享同一套方法。

## 八、class 也是对象模型的语法糖吗

可以这么理解：`class` 是建立在原型机制之上的语法。

下面两种写法在概念上接近。

构造函数：

```js
function User(id, name) {
  this.id = id
  this.name = name
}

User.prototype.greet = function () {
  return `你好，我是 ${this.name}`
}
```

类：

```js
class User {
  constructor(id, name) {
    this.id = id
    this.name = name
  }

  greet() {
    return `你好，我是 ${this.name}`
  }
}
```

但它们不完全等价。`class` 有自己的语法限制和行为，例如：

- 类必须用 `new` 调用。
- 类声明内部默认是严格模式。
- 类方法默认不可枚举。
- `extends` 和 `super` 提供标准继承语法。

所以不要简单说 `class` 只是“换皮”。它确实基于原型，但语义更规范，适合现代工程代码。

## 九、原型和原型链

JavaScript 对象可以通过原型共享属性和方法。

```js
const user = {
  name: 'Yuki'
}

console.log(Object.getPrototypeOf(user))
```

普通对象默认有一个原型，通常是 `Object.prototype`。

当访问属性时：

```js
user.toString
```

如果 `user` 自己没有 `toString`，JavaScript 会沿着原型链向上找。

简化理解：

```text
user
 -> Object.prototype
 -> null
```

类实例也是这样：

```js
class User {
  greet() {
    return 'hello'
  }
}

const user = new User()

console.log(Object.getPrototypeOf(user) === User.prototype) // true
```

访问：

```js
user.greet()
```

会先看 `user` 自己有没有 `greet`，没有就去 `User.prototype` 上找。

原型链是 JavaScript 面向对象的底层基础。理解这一点后，`new`、`class`、方法共享、继承都会清楚许多。

## 十、继承

`class` 可以用 `extends` 继承。

```js
class Animal {
  constructor(name) {
    this.name = name
  }

  speak() {
    return `${this.name} makes a sound`
  }
}

class Dog extends Animal {
  speak() {
    return `${this.name} barks`
  }
}

const dog = new Dog('Mochi')

console.log(dog.speak())
```

输出：

```text
Mochi barks
```

如果子类要调用父类构造方法：

```js
class AdminUser extends User {
  constructor(id, name, role) {
    super(id, name)
    this.role = role
  }
}
```

`super(...)` 会调用父类构造方法。

继承能用，但不要滥用。前端业务代码里，很多时候对象组合比复杂继承更清楚。

```js
const user = {
  profile,
  permissions,
  settings
}
```

比设计一长串父类子类更容易维护。代码不是家谱，没必要每个东西都认祖归宗。

## 十一、封装和私有字段

现代 JavaScript 支持私有字段，使用 `#`。

```js
class Counter {
  #value = 0

  increase() {
    this.#value++
  }

  getValue() {
    return this.#value
  }
}

const counter = new Counter()

counter.increase()
console.log(counter.getValue()) // 1
```

外部不能直接访问：

```js
counter.#value // 语法错误
```

私有字段适合隐藏内部状态。

但在前端业务中，不是所有数据都要包装成类。很多接口数据、表单数据、页面状态，用普通对象就很好。

判断是否需要类，可以看：

- 是否需要创建多个相同行为的实例。
- 是否有稳定的方法和内部状态。
- 是否需要封装复杂行为。
- 是否比普通对象加函数更清楚。

如果只是保存接口返回数据，普通对象通常足够。

## 十二、Array：JavaScript 的列表

JavaScript 没有内置叫 `List` 的类。通常用 `Array` 表示有序列表。

```js
const users = [
  { id: 1, name: 'Yuki' },
  { id: 2, name: 'Hachiman' }
]
```

常见操作：

```js
users.push({ id: 3, name: 'Iroha' })

const first = users[0]
const names = users.map(user => user.name)
const activeUsers = users.filter(user => user.active)
const current = users.find(user => user.id === 1)
```

数组是有序集合，适合：

- 列表渲染。
- 有顺序的数据。
- 需要按索引访问。
- 需要 `map`、`filter`、`reduce` 等批量处理。

数组可以包含任意类型：

```js
const mixed = [1, 'text', true, { id: 1 }]
```

但业务代码里最好保持数组元素结构一致，否则后续处理会很麻烦。

```js
const users = [
  { id: 1, name: 'Yuki' },
  { id: 2, title: 'Post' }
]
```

这种数组不是不能存在，但它会让每次读取都变成猜谜。猜谜可以是娱乐，不该是日常开发流程。

## 十三、数组也是对象

数组在 JavaScript 中也是对象。

```js
const list = [10, 20, 30]

console.log(typeof list) // object
console.log(Array.isArray(list)) // true
```

判断数组不要用：

```js
typeof list === 'array'
```

因为结果不会是 `'array'`。

应该用：

```js
Array.isArray(list)
```

数组有特殊的 `length` 和索引行为。

```js
const list = []

list[0] = 'A'
list[2] = 'C'

console.log(list.length) // 3
console.log(list[1]) // undefined
```

中间空出来的位置叫稀疏数组。业务代码里不建议故意制造稀疏数组，因为很多数组方法处理它时会有细节差异。

## 十四、Map：真正的键值集合

`Map` 是专门的键值集合。

```js
const map = new Map()

map.set('name', 'Yuki')
map.set('age', 18)

console.log(map.get('name')) // Yuki
console.log(map.has('age')) // true
console.log(map.size) // 2
```

删除：

```js
map.delete('age')
```

清空：

```js
map.clear()
```

遍历：

```js
for (const [key, value] of map) {
  console.log(key, value)
}
```

`Map` 的 key 可以是任意值。

```js
const user = { id: 1 }
const map = new Map()

map.set(user, 'selected')

console.log(map.get(user)) // selected
```

这点是普通对象做不到的。对象属性 key 不能直接保留对象身份。

```js
const obj = {}
const user = { id: 1 }

obj[user] = 'selected'

console.log(Object.keys(obj)) // ['[object Object]']
```

对象 key 被转成字符串了。

## 十五、什么时候用 Object，什么时候用 Map

一个实用判断：

| 场景 | 推荐 |
| ---- | ---- |
| 表示用户、文章、订单等业务实体 | 普通对象 |
| 表示接口 JSON 数据 | 普通对象 |
| 表示配置项 | 普通对象 |
| key 固定且有语义 | 普通对象 |
| key 是动态生成的集合 | `Map` |
| key 可能是对象、函数、数字等任意值 | `Map` |
| 频繁增删键值 | `Map` |
| 需要直接获取数量 | `Map` |

普通对象示例：

```js
const user = {
  id: 1,
  name: 'Yuki',
  role: 'admin'
}
```

`Map` 示例：

```js
const selectedMap = new Map()

selectedMap.set(user.id, true)
selectedMap.set(anotherUser.id, false)
```

也可以用 `Map` 做缓存：

```js
const cache = new Map()

async function getUser(id) {
  if (cache.has(id)) {
    return cache.get(id)
  }

  const user = await fetchUser(id)
  cache.set(id, user)
  return user
}
```

如果你只是要描述一个用户，不要用 `Map`：

```js
const user = new Map()
user.set('id', 1)
user.set('name', 'Yuki')
```

这当然能工作，但读起来不如对象自然，也不利于 JSON 序列化。能用普通对象清楚表达的数据，就别把它装进 `Map` 里让读者绕路。

## 十六、Map 和 JSON

普通对象可以直接转 JSON：

```js
const user = {
  id: 1,
  name: 'Yuki'
}

console.log(JSON.stringify(user))
```

输出：

```json
{"id":1,"name":"Yuki"}
```

`Map` 不能直接得到你想要的 JSON：

```js
const map = new Map()
map.set('id', 1)
map.set('name', 'Yuki')

console.log(JSON.stringify(map))
```

输出：

```json
{}
```

需要转换：

```js
const obj = Object.fromEntries(map)

console.log(JSON.stringify(obj))
```

或：

```js
const entries = Array.from(map.entries())

console.log(JSON.stringify(entries))
```

所以接口数据和持久化数据更常使用普通对象。`Map` 更适合运行时内存中的动态映射。

## 十七、Set：唯一值集合

`Set` 用来保存不重复的值。

```js
const set = new Set()

set.add('js')
set.add('vue')
set.add('js')

console.log(set.size) // 2
```

判断是否存在：

```js
set.has('js')
```

删除：

```js
set.delete('vue')
```

遍历：

```js
for (const value of set) {
  console.log(value)
}
```

数组去重：

```js
const tags = ['js', 'vue', 'js', 'react']
const uniqueTags = [...new Set(tags)]

console.log(uniqueTags) // ['js', 'vue', 'react']
```

`Set` 适合：

- 去重。
- 判断某个值是否存在。
- 保存选中 id 集合。
- 保存权限码集合。
- 保存已经处理过的 key。

示例：

```js
const selectedIds = new Set()

selectedIds.add(1)
selectedIds.add(2)

if (selectedIds.has(1)) {
  console.log('已选中')
}
```

比数组查找更表达意图：

```js
selectedIds.includes(1)
```

数组当然也能做，但 `Set` 更明确地表示“这是唯一集合”。

## 十八、Set 判断对象唯一性

`Set` 判断对象是否重复，看的是对象引用，不是对象内容。

```js
const set = new Set()

set.add({ id: 1 })
set.add({ id: 1 })

console.log(set.size) // 2
```

虽然两个对象内容一样，但它们是两个不同对象。

```js
const user = { id: 1 }

set.add(user)
set.add(user)

console.log(set.size) // 1
```

如果要按 `id` 去重，应该存 `id`，或自己写去重逻辑。

```js
const users = [
  { id: 1, name: 'A' },
  { id: 1, name: 'A2' },
  { id: 2, name: 'B' }
]

const seen = new Set()

const uniqueUsers = users.filter(user => {
  if (seen.has(user.id)) {
    return false
  }

  seen.add(user.id)
  return true
})
```

不要期待 `Set` 自动深度比较对象。它没那么热心，也不该那么热心，因为深度比较本身就有很多业务边界。

## 十九、WeakMap 和 WeakSet

`WeakMap` 和 `WeakSet` 是弱引用集合。

`WeakMap` 的 key 必须是对象。

```js
const metaMap = new WeakMap()

const element = document.querySelector('#app')

metaMap.set(element, {
  mounted: true
})
```

如果 `element` 不再被其他地方引用，垃圾回收可以回收它，对应的 `WeakMap` 记录也不会阻止回收。

`WeakMap` 常用于：

- 给对象关联额外元数据。
- 缓存对象计算结果。
- 框架内部管理 DOM 或实例状态。
- 避免因为缓存导致对象无法被回收。

`WeakSet` 保存对象集合：

```js
const visited = new WeakSet()

function markVisited(obj) {
  visited.add(obj)
}
```

限制：

- 不能遍历。
- 没有 `size`。
- key / value 必须是对象。

因为弱引用集合不暴露里面到底有什么。否则垃圾回收行为就会被程序观察和依赖，事情会变得很麻烦。

日常业务代码中，`WeakMap` / `WeakSet` 用得比 `Map` / `Set` 少。先掌握 `Map` 和 `Set` 更重要。

## 二十、常见容器对比

| 容器 | 适合表达 | 是否有序 | key / value 特点 |
| ---- | -------- | -------- | ---------------- |
| 普通对象 `{}` | 业务实体、配置、JSON 结构 | 属性有规定顺序，但不要过度依赖 | key 主要是字符串 / Symbol |
| `Array` | 有序列表 | 是 | 按索引访问 |
| `Map` | 动态键值集合 | 按插入顺序遍历 | key 可以是任意值 |
| `Set` | 唯一值集合 | 按插入顺序遍历 | value 唯一 |
| `WeakMap` | 对象到元数据的弱映射 | 不可遍历 | key 必须是对象 |
| `WeakSet` | 对象弱集合 | 不可遍历 | value 必须是对象 |

如果只记使用建议：

```text
结构化数据 -> Object
有序列表   -> Array
动态映射   -> Map
唯一集合   -> Set
对象元数据 -> WeakMap
```

## 二十一、类实例和普通对象的区别

普通对象：

```js
const user = {
  id: 1,
  name: 'Yuki'
}
```

类实例：

```js
class User {
  constructor(id, name) {
    this.id = id
    this.name = name
  }

  greet() {
    return `你好，我是 ${this.name}`
  }
}

const user = new User(1, 'Yuki')
```

主要区别：

| 对比 | 普通对象 | 类实例 |
| ---- | -------- | ------ |
| 创建方式 | `{}` | `new Class()` |
| 方法 | 通常直接放函数或外部函数处理 | 方法放在原型上 |
| 适合 | 数据记录、接口响应、配置 | 有行为和状态的对象 |
| JSON | 天然适合 | 方法不会进入 JSON |
| 类型判断 | 看结构 | 可以用 `instanceof` |

示例：

```js
console.log(user instanceof User)
```

如果数据主要来自接口，通常是普通对象：

```js
const response = await fetch('/api/user/1')
const user = await response.json()
```

这个 `user` 不是 `User` 类实例，它只是普通对象。即使字段长得一样，也没有 `User.prototype` 上的方法。

```js
user.greet() // 如果接口没返回 greet 字段，这里会报错
```

如果需要把接口数据转成类实例，要显式创建：

```js
const rawUser = await response.json()
const user = new User(rawUser.id, rawUser.name)
```

不过前端业务里不一定需要这么做。很多时候，用普通对象加独立函数更轻：

```js
function getDisplayName(user) {
  return user.name?.trim() || '匿名用户'
}
```

## 二十二、函数也是对象

JavaScript 里函数也是对象。

```js
function fn() {}

console.log(typeof fn) // function
console.log(fn instanceof Object) // true
```

函数可以有属性：

```js
function request() {}

request.timeout = 3000

console.log(request.timeout)
```

普通函数还可以作为构造函数使用：

```js
function User(name) {
  this.name = name
}

const user = new User('Yuki')
```

但箭头函数不能作为构造函数：

```js
const User = name => {
  this.name = name
}

new User('Yuki') // TypeError
```

因为箭头函数没有自己的 `this`，也没有作为构造函数所需的行为。

现代代码里，如果要表达构造能力，优先使用 `class`，不要让普通函数同时承担太多角色。

## 二十三、常见误区

### 1. 以为 `{}` 就是 Map

`{}` 可以做简单键值记录，但它不是专门的 `Map`。当 key 是动态集合、对象、函数，或者需要频繁增删和获取数量时，用 `Map` 更合适。

### 2. 以为 JS 不能面向对象

JavaScript 可以面向对象，只是它的对象系统基于原型。`class` 是现代语法，但底层仍然和原型链有关。

### 3. 以为 `new` 只能创建 class 实例

`new` 也可以调用普通构造函数。

```js
function User(name) {
  this.name = name
}

const user = new User('Yuki')
```

只是现代代码更推荐用 `class` 表达这种意图。

### 4. 以为数组就是普通对象，没有特殊规则

数组确实是对象，但它有索引、`length` 和一组数组方法。判断数组要用 `Array.isArray`。

### 5. 以为 Set 会按内容去重对象

```js
new Set([{ id: 1 }, { id: 1 }]).size // 2
```

对象按引用比较，不按内容比较。

### 6. 以为 class 实例适合所有数据

接口响应、表单状态、组件 props、配置对象，很多时候用普通对象更自然。类适合“状态 + 行为”稳定绑定的场景。

## 二十四、练习

### 1. 选择容器

下面场景应该选什么？

| 场景 | 推荐 |
| ---- | ---- |
| 接口返回的用户信息 | 普通对象 |
| 页面文章列表 | `Array` |
| 记录选中的文章 id | `Set` |
| 根据用户 id 缓存用户详情 | `Map` |
| 给 DOM 节点关联内部状态 | `WeakMap` |
| 表单配置项 | 普通对象 |

### 2. 用 Map 做缓存

实现一个简单缓存：

```js
const userCache = new Map()

async function getUser(id) {
  if (userCache.has(id)) {
    return userCache.get(id)
  }

  const response = await fetch(`/api/users/${id}`)
  const user = await response.json()

  userCache.set(id, user)

  return user
}
```

### 3. 用 Set 做去重

按标签去重：

```js
function uniqueTags(posts) {
  const tags = posts.flatMap(post => post.tags ?? [])
  return [...new Set(tags)]
}
```

按用户 id 去重：

```js
function uniqueUsers(users) {
  const seen = new Set()

  return users.filter(user => {
    if (seen.has(user.id)) {
      return false
    }

    seen.add(user.id)
    return true
  })
}
```

### 4. 判断输出

```js
const obj = {}

obj[1] = 'number'
obj['1'] = 'string'

console.log(obj[1])
console.log(Object.keys(obj))
```

结果：

```text
string
['1']
```

再看：

```js
const map = new Map()

map.set(1, 'number')
map.set('1', 'string')

console.log(map.get(1))
console.log(map.get('1'))
console.log(map.size)
```

结果：

```text
number
string
2
```

## 二十五、总结

JavaScript 的对象和容器可以这样记：

```text
{}       -> 对象字面量，适合业务实体、配置、JSON 数据
new      -> 调用构造函数或类，创建实例
class    -> 基于原型机制的现代类语法
Array    -> 有序列表，类似很多语言里的 List
Map      -> 真正的键值集合，key 可以是任意值
Set      -> 唯一值集合
WeakMap  -> 对象弱映射，适合关联元数据
WeakSet  -> 对象弱集合
```

如果只写一句话：

> JavaScript 可以面向对象，但它的对象系统以原型为基础；`{}` 是结构化对象，不完全等于 `Map`；列表用 `Array`，动态键值集合用 `Map`，唯一集合用 `Set`。

理解这些边界后，你就不会把所有数据都塞进 `{}`，也不会把所有结构都设计成类。能分清工具用途，才算真正开始掌握这门语言，而不是只是在和语法和平共处。
