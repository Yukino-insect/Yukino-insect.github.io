+++
date = '2026-08-20T18:23:00+08:00'
draft = false
title = 'ES Module 导入导出详解：命名导出、默认导出与模块组织'
+++

模块化的目标很朴素：把代码拆成清楚的文件，让每个文件只暴露必要能力。现代前端使用 ES Module，也就是 `import` 和 `export`。

如果模块拆得好，项目会像一组边界清晰的小房间；如果拆得不好，就会变成到处都是门但没有一扇通向出口。后者很有文学性，但不适合维护。

## 一、为什么需要模块

没有模块时，代码容易出现三个问题：

- 全局变量污染。
- 文件之间依赖关系不清楚。
- 工具函数、请求函数、状态逻辑混在一起。

模块让一个文件可以明确导出能力，另一个文件明确导入能力。

```text
date.js 导出 formatDate
postApi.js 导出 fetchPosts
PostList.js 导入并使用它们
```

这种依赖关系能被编辑器、构建工具和人类一起读懂。

## 二、命名导出

命名导出可以在一个模块里导出多个成员。

```js
export function formatDate(value) {
  return new Date(value).toLocaleDateString()
}

export function formatDateTime(value) {
  return new Date(value).toLocaleString()
}

export const defaultDateText = '-'
```

导入时使用花括号：

```js
import { formatDate, formatDateTime, defaultDateText } from './date.js'
```

命名导出的名字必须匹配导出名。

适合命名导出的内容：

- 工具函数。
- 常量。
- 多个同类 API。
- 多个组件。
- 类型定义。

工程中更推荐命名导出，因为它便于搜索、重构和自动补全。

## 三、统一放在底部导出

也可以先声明，再统一导出。

```js
function formatDate(value) {
  return new Date(value).toLocaleDateString()
}

function formatDateTime(value) {
  return new Date(value).toLocaleString()
}

const defaultDateText = '-'

export {
  formatDate,
  formatDateTime,
  defaultDateText
}
```

这种写法适合文件较长时集中查看导出列表。

如果函数本身就是这个文件的主要内容，直接在声明处 `export` 也很清楚。两种写法没有绝对高下，保持团队一致更重要。

## 四、导入时重命名

如果名字冲突，可以使用 `as` 重命名。

```js
import { formatDate as formatPostDate } from './date.js'
```

导出时也可以重命名：

```js
function format(value) {
  return new Date(value).toLocaleDateString()
}

export {
  format as formatDate
}
```

重命名不是为了炫技，而是为了让调用处语义更明确。

## 五、默认导出

一个模块只能有一个默认导出。

```js
export default function request(url, options) {
  return fetch(url, options)
}
```

导入默认导出时不需要花括号：

```js
import request from './request.js'
```

默认导入的名字可以随便取：

```js
import http from './request.js'
import apiClient from './request.js'
```

这既是便利，也是风险。名字过于自由，项目大了之后可能出现同一个东西在不同文件里叫不同名字的情况。

## 六、默认导出对象

有些代码会默认导出一个对象。

```js
function getPosts() {
  return fetch('/api/posts')
}

function getPostDetail(id) {
  return fetch(`/api/posts/${id}`)
}

export default {
  getPosts,
  getPostDetail
}
```

导入：

```js
import postApi from './postApi.js'

postApi.getPosts()
```

这种写法能把一组方法挂在同一个命名空间下，但也会削弱静态分析和按需导入的清晰度。

更推荐命名导出：

```js
export function getPosts() {
  return fetch('/api/posts')
}

export function getPostDetail(id) {
  return fetch(`/api/posts/${id}`)
}
```

导入：

```js
import { getPosts, getPostDetail } from './postApi.js'
```

如果项目规范已经选择默认导出对象，就遵守现有规范。工程不是写诗，风格统一比个人偏好更重要。

## 七、同时导入默认与命名成员

一个模块可以同时有默认导出和命名导出。

```js
export const timeout = 10000

export default function request(url, options) {
  return fetch(url, options)
}
```

导入：

```js
import request, { timeout } from './request.js'
```

可以这样写，但不要让一个模块承担太多角色。默认导出和命名导出同时存在时，要保证语义清楚。

## 八、命名空间导入

可以把模块所有命名导出收集到一个对象上。

```js
import * as postApi from './postApi.js'

postApi.getPosts()
postApi.getPostDetail(1)
```

适合场景：

- API 模块方法较多。
- 调用处希望保留模块名作为上下文。
- 避免多个模块导出同名函数造成混淆。

不要为了省事到处 `import * as utils`。如果一个 `utils` 里什么都有，最后它就什么边界都没有。

## 九、重新导出

重新导出常用于模块入口文件。

目录结构：

```text
api/
  post.js
  user.js
  index.js
```

`post.js`：

```js
export function getPosts() {
  return fetch('/api/posts')
}
```

`user.js`：

```js
export function getProfile() {
  return fetch('/api/profile')
}
```

`index.js`：

```js
export { getPosts } from './post.js'
export { getProfile } from './user.js'
```

调用处：

```js
import { getPosts, getProfile } from './api/index.js'
```

这种入口文件常被称为 barrel file。

它的好处是导入路径更统一；风险是入口文件过度聚合后，依赖关系可能变得不够直观。小项目问题不大，大项目要谨慎。

## 十、副作用导入

有些模块不导出值，只在执行时产生副作用。

```js
import './global.css'
import './setupErrorHandler.js'
```

副作用包括：

- 注册全局样式。
- 初始化监控。
- 注册全局事件。
- 修改原型或全局对象。

副作用模块要少而明确。一个文件被导入后偷偷改了全局行为，会让调试变得很辛苦。

## 十一、导入是静态结构

ES Module 的 `import` 通常必须写在模块顶层。

```js
import { formatDate } from './date.js'
```

不能根据条件随便写：

```js
if (enabled) {
  import { formatDate } from './date.js'
}
```

这是错误写法。

如果确实需要按需加载，可以使用动态导入：

```js
async function loadEditor() {
  const module = await import('./editor.js')
  module.mountEditor()
}
```

动态导入返回 Promise，常用于：

- 路由懒加载。
- 大组件按需加载。
- 管理后台中低频功能延迟加载。

## 十二、导出是实时绑定

ES Module 导出的不是值的静态拷贝，而是绑定关系。

```js
// counter.js
export let count = 0

export function increase() {
  count++
}
```

导入：

```js
import { count, increase } from './counter.js'

console.log(count) // 0
increase()
console.log(count) // 1
```

但导入的绑定不能在导入方重新赋值。

```js
import { count } from './counter.js'

count = 10 // 错误
```

如果需要修改模块内部状态，应该通过模块导出的函数完成。

## 十三、循环依赖

两个模块互相导入，就是循环依赖。

```text
a.js -> b.js
b.js -> a.js
```

简单循环依赖不一定立刻报错，但会让初始化顺序变复杂。

```js
// a.js
import { b } from './b.js'

export const a = 'A'
console.log(b)
```

```js
// b.js
import { a } from './a.js'

export const b = 'B'
console.log(a)
```

真实项目里，循环依赖常见于：

- 工具函数互相引用。
- API 模块和状态模块互相引用。
- 组件互相导入。
- 入口文件重新导出太多内容。

解决方向：

- 抽出共同依赖到第三个模块。
- 让底层工具不要依赖上层业务。
- 减少 barrel file 的过度聚合。
- 把类型和运行时代码分开。

模块依赖应该尽量单向。代码结构和人际关系一样，互相拉扯太多，总会出问题。

## 十四、ES Module 与 CommonJS

现代浏览器和现代前端工程主要使用 ES Module。

Node.js 早期主要使用 CommonJS。

```js
const fs = require('fs')

module.exports = {
  readConfig
}
```

ES Module 写法：

```js
import fs from 'node:fs'

export {
  readConfig
}
```

前端学习阶段先掌握 ES Module。CommonJS 主要在 Node.js 老项目、构建配置、某些第三方包里遇到。

两者差异很多，先记住最实用的一点：不要在同一个普通业务文件里混着写 `require` 和 `import`，除非你清楚构建工具正在做什么。

## 十五、文件路径与扩展名

浏览器原生 ES Module 通常需要完整路径：

```js
import { formatDate } from './date.js'
```

在 Vite、Webpack 这类构建工具中，可能可以省略扩展名：

```js
import { formatDate } from './date'
```

项目里应该遵守已有风格，不要一会儿写 `.js`，一会儿省略。

路径建议：

- 同目录使用 `./xxx`。
- 上级目录使用 `../xxx`。
- 过深的 `../../../` 可以考虑配置路径别名。
- 公共模块放在稳定目录，不要随业务页面频繁移动。

## 十六、如何选择命名导出和默认导出

一个实用建议：

| 场景 | 建议 |
| ---- | ---- |
| 工具函数 | 命名导出 |
| 常量集合 | 命名导出 |
| API 方法 | 命名导出或命名空间导入 |
| 单个页面组件 | 可默认导出 |
| 单个类 | 可默认导出 |
| 多个相关函数 | 命名导出 |

如果你没有强烈理由，优先命名导出。

原因：

- 导入名固定。
- 更容易搜索引用。
- 重构工具更可靠。
- 不容易出现同物异名。

默认导出不是不能用，而是要用在“这个文件的主角只有一个”的场景。

## 十七、练习

把下面代码拆成模块。

原始代码：

```js
function formatCount(count) {
  return count >= 10000 ? `${(count / 10000).toFixed(1)}w` : String(count)
}

async function getPosts() {
  const response = await fetch('/api/posts')
  return response.json()
}

async function init() {
  const posts = await getPosts()
  console.log(posts.map(post => formatCount(post.likeCount)))
}
```

参考拆分：

```text
utils/format.js
api/post.js
pages/postList.js
```

`utils/format.js`：

```js
export function formatCount(count) {
  return count >= 10000 ? `${(count / 10000).toFixed(1)}w` : String(count)
}
```

`api/post.js`：

```js
export async function getPosts() {
  const response = await fetch('/api/posts')
  return response.json()
}
```

`pages/postList.js`：

```js
import { getPosts } from '../api/post.js'
import { formatCount } from '../utils/format.js'

export async function initPostList() {
  const posts = await getPosts()
  console.log(posts.map(post => formatCount(post.likeCount)))
}
```

模块化的核心不是“多拆文件”，而是让依赖关系变得诚实。谁需要谁，谁暴露什么，谁不该知道什么，都应该从 `import` 和 `export` 里看出来。
