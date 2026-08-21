+++
date = '2026-08-21T16:13:00+08:00'
draft = false
title = 'JavaScript 原型与 class-only 模型：为什么 class 只是入口，不是底层'
+++

在 JavaScript 里，你会同时看到这些说法：

- JavaScript 有对象。
- JavaScript 有 `class`。
- JavaScript 可以 `new User()`。
- JavaScript 的底层是原型。
- JavaScript 不是传统 class-only 模型。

这些话单独看都不难，放在一起就容易让人怀疑：既然已经有 `class` 了，为什么还要讲原型？既然原型才是底层，那 `class` 是不是假的？如果你有这种疑问，倒也正常。语言模型不一致时，人类感到别扭，不是什么罪过。

先给结论：

- **传统 class-only 模型**：先有类，类定义结构和行为，实例必须从类创建，继承主要发生在类和类之间。
- **JavaScript 原型模型**：对象可以直接关联另一个对象；访问属性时，自己没有就沿着原型链向上找。
- **JavaScript 的 `class`**：是建立在原型机制之上的现代语法，让你用类似类的方式组织代码，但底层仍然是原型链。

所以不要把问题理解成：

```text
JavaScript 到底是 class 还是 prototype？
```

更准确的理解是：

```text
JavaScript 底层是 prototype，现代写法可以用 class 表达。
```

## 一、传统 class-only 模型是什么

很多语言采用以类为中心的对象模型，比如 Java、C#。为了方便理解，可以先看一个简化版 Java 风格：

```java
class User {
  private String name;

  public User(String name) {
    this.name = name;
  }

  public String greet() {
    return "Hello, " + this.name;
  }
}

User user = new User("Yuki");
```

在这种模型里，通常是：

```text
class 定义对象应该有什么字段和方法
 -> new class 创建实例
 -> 实例按照 class 的定义工作
```

也就是说，类是对象的模板。你不能随便让一个普通对象临时成为另一个对象的“父对象”。对象和对象之间不会像 JavaScript 那样直接通过原型链互相查找属性。

当然，不同语言的细节并不完全一样。这里说的 class-only 模型，是为了帮助你建立对比：它强调“类定义实例”，而不是“对象委托给对象”。

## 二、JavaScript 的对象不是从 class 开始的

JavaScript 一开始就可以直接创建对象：

```js
const user = {
  name: 'Yuki',
  greet() {
    return `Hello, ${this.name}`
  }
}

console.log(user.greet()) // Hello, Yuki
```

这里没有 `class`，也没有 `new`。对象就是对象，它可以直接拥有属性和方法。

这和很多 class-only 语言的直觉不同。在 JavaScript 中，普通对象不是“缺少类的残次品”。它就是语言的一等公民。接口响应、配置对象、组件状态、表单数据，很多时候都适合用这种普通对象表达。

但问题来了：如果很多对象都需要共享同一个方法，难道每个对象都复制一份吗？

```js
const user1 = {
  name: 'Yuki',
  greet() {
    return `Hello, ${this.name}`
  }
}

const user2 = {
  name: 'Hachiman',
  greet() {
    return `Hello, ${this.name}`
  }
}
```

这样当然能运行，但方法重复了。语言总得有一种共享行为的机制。JavaScript 的答案就是：原型。

## 三、原型的核心：对象委托给对象

每个普通对象都可以有一个原型。原型本质上也是对象。

```js
const userMethods = {
  greet() {
    return `Hello, ${this.name}`
  }
}

const user = Object.create(userMethods)
user.name = 'Yuki'

console.log(user.greet()) // Hello, Yuki
```

这段代码里：

```text
user
 -> userMethods
 -> Object.prototype
 -> null
```

当执行：

```js
user.greet()
```

JavaScript 会这样找：

```text
1. user 自己有没有 greet？
2. 没有，就去 user 的原型 userMethods 上找。
3. 找到了，就调用它。
```

这就是原型链查找。

注意，这不是“`user` 复制了 `userMethods.greet`”。更准确地说，是 `user` 找不到属性时，把查找委托给自己的原型。

```js
console.log(user.hasOwnProperty('name')) // true
console.log(user.hasOwnProperty('greet')) // false
```

`name` 是 `user` 自己的属性，`greet` 来自原型。

这就是 JavaScript 原型模型最关键的地方：

```text
对象自己没有某个属性时，可以沿着原型链向别的对象查找。
```

## 四、构造函数只是自动设置原型的工具

早期 JavaScript 没有 `class`，常用构造函数创建一批类似对象：

```js
function User(name) {
  this.name = name
}

User.prototype.greet = function () {
  return `Hello, ${this.name}`
}

const user = new User('Yuki')

console.log(user.greet()) // Hello, Yuki
```

这里有两个容易混淆的点：

- `User` 是函数。
- `User.prototype` 是一个对象。

当执行：

```js
const user = new User('Yuki')
```

`new` 大致做了这些事：

```text
1. 创建一个新对象。
2. 把新对象的原型设置为 User.prototype。
3. 用 this 指向这个新对象，执行 User 函数。
4. 如果构造函数没有显式返回对象，就返回这个新对象。
```

所以这个判断成立：

```js
console.log(Object.getPrototypeOf(user) === User.prototype) // true
```

也就是说，构造函数不是“类系统本身”。它更像一个创建对象并连接原型的工具。

如果把它画出来，是这样：

```text
user
 -> User.prototype
 -> Object.prototype
 -> null
```

`user.greet()` 能调用成功，不是因为 `greet` 被复制到了 `user` 上，而是因为 `user` 的原型链上有它。

## 五、class 语法做了什么

现代 JavaScript 可以写：

```js
class User {
  constructor(name) {
    this.name = name
  }

  greet() {
    return `Hello, ${this.name}`
  }
}

const user = new User('Yuki')

console.log(user.greet()) // Hello, Yuki
```

这看起来很像 Java 或 C# 的类。它也确实让代码更容易组织。可是底层依然是原型：

```js
console.log(Object.getPrototypeOf(user) === User.prototype) // true
console.log(user.greet === User.prototype.greet) // true
```

类方法会放在 `User.prototype` 上，而不是每个实例单独复制一份。

所以这两段在概念上接近。

构造函数写法：

```js
function User(name) {
  this.name = name
}

User.prototype.greet = function () {
  return `Hello, ${this.name}`
}
```

`class` 写法：

```js
class User {
  constructor(name) {
    this.name = name
  }

  greet() {
    return `Hello, ${this.name}`
  }
}
```

但“接近”不等于“完全一样”。`class` 有更严格、更规范的语义：

- 类必须用 `new` 调用。
- 类内部默认是严格模式。
- 类方法默认不可枚举。
- `extends` 和 `super` 提供标准继承写法。
- 可以使用 `#privateField` 声明私有字段。

因此，比较准确的说法是：

```text
class 是基于原型的现代类语法，不是脱离原型的新对象模型。
```

把 `class` 说成“假的类”也不太公平。它是真的语法，也是现代工程里推荐的组织方式。只是它没有把 JavaScript 变成 Java。

## 六、class-only 与原型模型的关键区别

可以用一张表来压住这个概念：

| 对比 | 传统 class-only 模型 | JavaScript 原型模型 |
| ---- | -------------------- | ------------------- |
| 核心关系 | 类定义实例 | 对象委托给对象 |
| 行为共享 | 方法定义在类上 | 方法通常在原型对象上 |
| 创建实例 | 通常必须通过类 | 可以用 `{}`、`Object.create`、构造函数、`class` |
| 继承理解 | 类继承类 | 原型链查找属性 |
| 运行时灵活性 | 相对固定 | 对象和原型关系更动态 |
| 现代写法 | 类语法就是主要模型 | `class` 是原型机制之上的语法 |

如果你从 Java 或 C# 转过来，最容易误解的是这一点：

```text
在 JavaScript 中，class 不是对象存在的前提。
```

普通对象不需要类也能存在；类实例也只是某个原型链结构下的对象。

## 七、实例属性和原型方法要分开看

来看这段代码：

```js
class User {
  constructor(name) {
    this.name = name
  }

  greet() {
    return `Hello, ${this.name}`
  }
}

const user1 = new User('Yuki')
const user2 = new User('Hachiman')
```

`name` 是实例属性：

```js
console.log(user1.name) // Yuki
console.log(user2.name) // Hachiman
console.log(user1.hasOwnProperty('name')) // true
```

每个实例都有自己的 `name`。

`greet` 是原型方法：

```js
console.log(user1.hasOwnProperty('greet')) // false
console.log(user1.greet === user2.greet) // true
```

两个实例共享同一个方法。

可以把它理解成：

```text
user1
  自己的属性：name = 'Yuki'
  原型上的方法：greet

user2
  自己的属性：name = 'Hachiman'
  原型上的方法：greet
```

这种设计既能让每个对象保存自己的状态，又能让多个对象共享行为。

## 八、属性查找不是类型判断

原型链负责属性查找，但它不是 TypeScript 那种静态类型系统。

```js
const user = {
  name: 'Yuki'
}

console.log(user.toString) // 来自 Object.prototype
```

`user` 自己没有 `toString`，但它的原型链上有。

这不代表 `user` 在编译前被某个类严格声明过。JavaScript 运行时只是按照规则找属性：

```text
自己有 -> 用自己的
自己没有 -> 去原型找
原型还没有 -> 继续往上找
找到 null -> 返回 undefined
```

例如：

```js
const base = {
  role: 'guest'
}

const user = Object.create(base)
user.name = 'Yuki'

console.log(user.role) // guest
console.log(user.age) // undefined
```

`role` 来自原型，`age` 整条原型链都没有，所以是 `undefined`。

## 九、原型链和继承

`class extends` 也会建立原型链。

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

console.log(dog.speak()) // Mochi barks
console.log(dog instanceof Dog) // true
console.log(dog instanceof Animal) // true
```

这里有两条相关的链。

实例属性查找链：

```text
dog
 -> Dog.prototype
 -> Animal.prototype
 -> Object.prototype
 -> null
```

构造函数之间也有关联：

```text
Dog
 -> Animal
 -> Function.prototype
 -> Object.prototype
 -> null
```

日常学习阶段，你最需要先掌握第一条：实例访问方法时，会沿着 `Dog.prototype`、`Animal.prototype` 往上找。

当 `Dog.prototype` 上有自己的 `speak` 时，会优先用子类的方法：

```js
dog.speak()
```

如果子类没有定义 `speak`，才会去 `Animal.prototype` 找。

这和很多 class-only 语言里的“子类继承父类方法”表面上很像，但 JavaScript 的运行时解释仍然是原型链查找。

## 十、为什么不建议随便改原型

既然原型这么重要，能不能给内置对象加方法？

```js
Array.prototype.first = function () {
  return this[0]
}

console.log([1, 2, 3].first()) // 1
```

能。问题是，不建议。

原因很现实：

- 可能和未来标准方法重名。
- 可能和第三方库扩展冲突。
- 会影响所有数组实例。
- 团队成员读代码时很难知道这个方法从哪里来。

特别是修改 `Object.prototype`，影响范围更大：

```js
Object.prototype.extra = 'bad idea'

const user = { name: 'Yuki' }

console.log(user.extra) // bad idea
```

这种写法会让几乎所有普通对象都能访问到 `extra`。一个工具影响全局对象链，结果通常不是“优雅扩展”，而是“优雅地制造事故”。程度不同，结局相近。

现代业务代码里，除非你在写 polyfill，并且非常清楚兼容性和规范边界，否则不要修改内置原型。

## 十一、`__proto__`、`prototype` 和 `[[Prototype]]`

这几个名字容易混：

| 名称 | 是什么 | 常见用途 |
| ---- | ------ | -------- |
| `[[Prototype]]` | 规范里的内部原型槽 | 表示对象真正关联的原型 |
| `__proto__` | 访问内部原型的历史属性 | 学习和调试时可能见到，不推荐业务代码使用 |
| `prototype` | 函数对象上的普通属性 | 被 `new` 用来设置实例原型 |

先看 `prototype`：

```js
function User(name) {
  this.name = name
}

const user = new User('Yuki')

console.log(Object.getPrototypeOf(user) === User.prototype) // true
```

`User.prototype` 是函数 `User` 上的一个属性。`new User()` 创建出来的实例，会把自己的内部原型指向它。

再看对象的内部原型：

```js
console.log(Object.getPrototypeOf(user))
```

现代代码里，如果需要读取原型，优先使用：

```js
Object.getPrototypeOf(user)
```

如果需要设置原型，优先在创建时决定：

```js
const user = Object.create(User.prototype)
```

尽量不要在业务代码中频繁使用：

```js
user.__proto__
```

它能帮助你理解调试输出，但不是日常建模的好工具。

## 十二、`instanceof` 判断的也是原型链

你可能写过：

```js
console.log(user instanceof User)
```

`instanceof` 的核心判断不是“这个对象长得像不像 User”，而是：

```text
User.prototype 是否出现在 user 的原型链上？
```

例如：

```js
function User(name) {
  this.name = name
}

const user = new User('Yuki')

console.log(user instanceof User) // true
```

因为：

```text
user
 -> User.prototype
 -> Object.prototype
 -> null
```

如果只是字段一样，不代表 `instanceof` 成立：

```js
function User(name) {
  this.name = name
}

const rawUser = {
  name: 'Yuki'
}

console.log(rawUser instanceof User) // false
```

`rawUser` 有 `name`，但它的原型链上没有 `User.prototype`。

这也是为什么接口返回的数据通常不是类实例：

```js
const rawUser = await response.json()

console.log(rawUser instanceof User) // false
```

JSON 只保存数据，不保存原型方法。它能告诉你字段，不会替你恢复类实例。指望网络响应顺手帮你维持对象血统，未免太乐观了。

## 十三、该怎么在现代代码中使用

实际写业务代码时，不需要每天手动操作原型。

通常可以这样选择：

| 场景 | 推荐写法 |
| ---- | -------- |
| 接口响应、页面状态、配置项 | 普通对象 `{}` |
| 有序列表 | `Array` |
| 动态键值缓存 | `Map` |
| 唯一值集合 | `Set` |
| 需要创建多个带相同行为的实例 | `class` |
| 学习底层、写框架、理解继承和 `this` | 理解原型链 |

换句话说：

```text
日常建模可以用 class。
底层理解必须懂 prototype。
简单数据不要勉强包装成 class。
```

例如，一个用户只是接口数据：

```js
const user = {
  id: 1,
  name: 'Yuki',
  role: 'admin'
}
```

这样就很好。

如果用户有稳定行为，并且你确实要创建很多实例：

```js
class User {
  constructor(id, name) {
    this.id = id
    this.name = name
  }

  getDisplayName() {
    return this.name.trim() || '匿名用户'
  }
}
```

这时用 `class` 更清楚。

但如果只是为了“看起来面向对象”，把所有数据都包进类里：

```js
class UserDto {
  constructor(data) {
    this.id = data.id
    this.name = data.name
    this.role = data.role
  }
}
```

不一定有价值。工程代码不是礼仪场，不需要每个对象都穿上类的外套。

## 十四、一个完整的对照例子

先用原型手写：

```js
const userMethods = {
  greet() {
    return `Hello, ${this.name}`
  }
}

const user = Object.create(userMethods)
user.name = 'Yuki'

console.log(user.greet()) // Hello, Yuki
console.log(Object.getPrototypeOf(user) === userMethods) // true
```

再用构造函数：

```js
function User(name) {
  this.name = name
}

User.prototype.greet = function () {
  return `Hello, ${this.name}`
}

const user = new User('Yuki')

console.log(user.greet()) // Hello, Yuki
console.log(Object.getPrototypeOf(user) === User.prototype) // true
```

最后用 `class`：

```js
class User {
  constructor(name) {
    this.name = name
  }

  greet() {
    return `Hello, ${this.name}`
  }
}

const user = new User('Yuki')

console.log(user.greet()) // Hello, Yuki
console.log(Object.getPrototypeOf(user) === User.prototype) // true
```

三者写法不同，但都能形成类似的原型链关系：

```text
user
 -> 某个保存 greet 的原型对象
 -> Object.prototype
 -> null
```

区别在于：

- `Object.create` 直接指定原型。
- 构造函数配合 `new` 自动指定原型并初始化属性。
- `class` 用更现代、更清晰的语法包装构造函数和原型方法。

## 十五、常见误区

### 1. 以为有 class 就不需要理解原型

不行。`class` 方法仍然在原型上，`extends` 仍然建立原型链，`instanceof` 仍然检查原型链。不了解原型，很多现象只能死记。

### 2. 以为 class 只是“假的”

也不准确。`class` 是正式语法，有自己的规则和限制。它基于原型，但不是毫无意义的伪装。现代代码中，需要类时优先用 `class`，比手写构造函数更清楚。

### 3. 以为对象必须来自 class

普通对象完全可以独立存在。JavaScript 里大量业务数据都只是对象字面量，不需要类。

### 4. 以为原型方法会复制到每个实例上

不会。原型方法是共享的。实例访问不到自己的属性时，才沿原型链查找。

### 5. 以为字段一样就是同一个类型

运行时不是这样。`instanceof` 看原型链，不看字段结构。TypeScript 的结构类型又是另一套编译期规则，不要混在一起。

## 十六、练习

### 1. 判断属性来自哪里

```js
class User {
  constructor(name) {
    this.name = name
  }

  greet() {
    return `Hello, ${this.name}`
  }
}

const user = new User('Yuki')

console.log(user.hasOwnProperty('name'))
console.log(user.hasOwnProperty('greet'))
console.log(user.greet === User.prototype.greet)
```

结果：

```text
true
false
true
```

### 2. 判断 instanceof

```js
function User(name) {
  this.name = name
}

const a = new User('Yuki')
const b = { name: 'Yuki' }

console.log(a instanceof User)
console.log(b instanceof User)
```

结果：

```text
true
false
```

`a` 的原型链上有 `User.prototype`。`b` 只是字段相同，原型链不同。

### 3. 手写一个原型委托

```js
const methods = {
  getLabel() {
    return `${this.id}: ${this.name}`
  }
}

const item = Object.create(methods)
item.id = 1
item.name = 'JavaScript'

console.log(item.getLabel()) // 1: JavaScript
console.log(item.hasOwnProperty('getLabel')) // false
```

这段代码能帮助你看清：方法不在 `item` 自己身上，而在它的原型对象上。

## 十七、总结

把这几个概念分开，就不容易乱：

```text
对象            -> 属性和方法的集合
原型            -> 对象背后委托查找的另一个对象
原型链          -> 多层原型形成的查找链
构造函数        -> 配合 new 创建对象并连接 prototype
prototype       -> 构造函数上用于实例原型的对象
class           -> 基于原型机制的现代类语法
class-only 模型 -> 以类为核心模板的对象模型
```

最后用一句话收束：

> JavaScript 不是没有类，而是类语法建立在原型系统之上；传统 class-only 模型强调“类生成实例”，JavaScript 原型模型强调“对象通过原型链委托查找属性”。

学到这里，你不需要把所有原型细节背成法律条文。先记住一件事：`class` 是你日常写代码的好入口，原型链是它背后的运行机制。知道入口，也知道地基，才不会在代码表现得和想象不一致时，只能盯着屏幕沉默。
