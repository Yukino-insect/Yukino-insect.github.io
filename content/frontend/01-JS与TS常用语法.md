+++
date = '2026-08-19T16:01:00+08:00'
draft = false
title = 'JS 与 TS 常用语法：从语言基础到工程写法'
+++

JavaScript 是前端运行时语言，TypeScript 是在 JavaScript 上增加静态类型的工程化语言。真实项目里，两者不是二选一：你写的是 TypeScript，最终构建出来运行的是 JavaScript。

`D:\shenweikeji\HebustForumFrontEnd` 使用 TypeScript。它的 `.vue` 文件通常写成 `<script setup lang="ts">`，普通逻辑文件写成 `.ts`。这意味着你不仅要会 JS 的运行机制，还要理解 TS 如何约束数据结构。

## 一、变量与作用域

现代 JS 主要使用 `const` 和 `let`。

```ts
const HOME_PAGE_SIZE = 20
let loading = false
```

推荐规则：

- 默认使用 `const`。
- 变量需要重新赋值时才使用 `let`。
- 不要再使用 `var`。

`const` 约束的是变量绑定不能变，不代表对象内容不能变：

```ts
const user = { name: 'Alice' }
user.name = 'Bob'
```

这段代码合法，因为 `user` 仍然指向同一个对象。只是对象里的字段变了。

在 Vue 中，响应式状态常用 `ref` 包一层：

```ts
const active = ref<'rec' | 'new' | 'hot'>('rec')
active.value = 'new'
```

这里的 `active` 自身是 `const`，但 `active.value` 可以变。初学者常被这一点绊倒，倒也不必难过，Vue 的响应式系统确实有点像把变量放进了盒子里。

## 二、基础类型

JavaScript 的常见基础类型：

| 类型 | 示例 |
| ---- | ---- |
| string | `'hello'` |
| number | `1`、`3.14` |
| boolean | `true`、`false` |
| undefined | 声明了但没有值 |
| null | 主动表示空 |
| bigint | `10n` |
| symbol | 唯一标识 |

TypeScript 会在这些基础上增加类型标注：

```ts
const title: string = '河北科技大学微墙'
const pageSize: number = 20
const visible: boolean = true
```

多数情况下 TS 可以自动推导：

```ts
const pageSize = 20
```

这里 `pageSize` 会被推导为 `20` 这个字面量类型或 `number`，具体取决于上下文。写业务代码时，不必给每个变量都手动标注类型。真正需要标注的是函数参数、返回值、对象结构和复杂泛型。

## 三、对象与数组

前端接口数据大多是对象和数组。

```ts
const post = {
  id: '1001',
  title: '今天食堂怎么样',
  likes: 12,
  liked: false,
}

const posts = [post]
```

访问字段：

```ts
console.log(post.title)
console.log(post['title'])
```

数组常用方法：

```ts
const visiblePosts = posts.filter((p) => p.likes > 0)
const titles = posts.map((p) => p.title)
const first = posts.find((p) => p.id === '1001')
```

在 `src/stores/feed.ts` 中可以看到类似写法：

```ts
favorites: (state): Post[] => state.posts.filter((p) => p.fav)
```

这表示从全局帖子列表中过滤出已收藏的帖子。

## 四、解构与展开语法

解构用于从对象或数组中取值：

```ts
const { id, title } = post
const [firstPost] = posts
```

函数参数中也常用解构：

```ts
function createUser({ name, age }: { name: string; age: number }) {
  return `${name}-${age}`
}
```

展开语法用于复制和合并：

```ts
const nextPost = { ...post, liked: true }
const nextPosts = [...posts, nextPost]
```

在 Pinia store 中，更新用户资料时就使用了对象展开：

```ts
this.profile = { ...this.profile, ...patch }
```

它的含义是：保留旧对象字段，再用 `patch` 覆盖其中一部分字段。

这和后端常见的 DTO 局部更新很像，只不过前端更常在内存对象里直接完成。

## 五、函数与箭头函数

普通函数：

```ts
function add(a: number, b: number): number {
  return a + b
}
```

箭头函数：

```ts
const add = (a: number, b: number): number => a + b
```

回调函数常用箭头函数：

```ts
posts.map((post) => post.title)
```

箭头函数不会绑定自己的 `this`。在 Vue 组合式 API 中，我们一般很少直接使用 `this`，所以箭头函数很自然。但在 Pinia 的 `actions` 中，项目使用对象方法写法：

```ts
async reload() {
  this.posts = []
}
```

这里需要 `this` 指向当前 store，因此不要随便改成箭头函数。

## 六、条件判断与可选链

常见条件判断：

```ts
if (!token) return
```

可选链用于安全访问可能为空的对象：

```ts
const school = profile.value?.school?.trim() || '河北科技大学'
```

这段逻辑来自首页思路：如果用户资料里有学校名，就展示学校名；否则展示默认值。

空值合并运算符 `??` 只在左侧为 `null` 或 `undefined` 时使用右侧值：

```ts
const pageSize = opts.batchSize ?? this.pageSize ?? 10
```

它和 `||` 的区别很重要：

```ts
0 || 10
0 ?? 10
```

第一行结果是 `10`，第二行结果是 `0`。如果 `0` 是合法业务值，就应该用 `??`。

## 七、模块化

现代前端使用 ES Module。

导出：

```ts
export function request<T>() {}
export const USE_MOCK = false
```

导入：

```ts
import { request } from '@/api/http'
import type { Post } from '@/models/post'
```

`import type` 只导入类型，构建后不会出现在运行时代码中。TypeScript 项目推荐对纯类型使用 `import type`，这样更清楚，也减少构建工具误判。

`@` 是路径别名。项目在 `vite.config.ts` 中配置：

```ts
resolve: {
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url)),
  },
}
```

所以：

```ts
import { useFeedStore } from '@/stores/feed'
```

等价于从 `src/stores/feed` 导入。

## 八、Promise 与 async/await

前端大量操作是异步的：

- 请求接口
- 读取本地缓存
- 图片上传
- 页面刷新
- 用户点击后的确认流程

`Promise` 表示未来才会完成的结果：

```ts
function delay(ms = 120): Promise<void> {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}
```

`async/await` 用同步风格写异步代码：

```ts
async function reloadFeed() {
  const posts = await fetchHomePosts()
  return posts
}
```

项目首页刷新时使用了并行请求：

```ts
await Promise.all([
  loadFeedIfNeeded(force),
  loadHotTodayIfNeeded(force),
  loadTopicsIfNeeded(force && includeTopics),
])
```

这表示三个请求没有依赖关系，可以一起发起。后端同学可以把它理解成多个异步任务并行执行，全部完成后再继续。

## 九、异常处理

JS 使用 `try/catch` 捕获异常：

```ts
try {
  await feed.loadMore()
} catch (e) {
  ui.showToast(e instanceof ApiError ? e.message : '加载失败')
}
```

项目中自定义了 `ApiError`：

```ts
export class ApiError extends Error {
  code: number
  constructor(code: number, msg: string) {
    super(msg || `HTTP code ${code}`)
    this.code = code
  }
}
```

这样页面可以根据错误类型判断是否展示后端错误信息。

需要注意，Promise 中的异常不会自动被外层同步 `try/catch` 捕获，必须 `await` 或 `.catch()`：

```ts
void useNotifyStore().refresh().catch(() => {})
```

这里的 `void` 表示调用者故意不等待这个 Promise。它不是装饰，而是在告诉 TypeScript 和读代码的人：这个异步任务是后台刷新，失败时不阻塞主流程。

## 十、TypeScript 接口与类型别名

接口用于描述对象结构：

```ts
interface RequestOptions {
  method?: HttpMethod
  data?: unknown
  noAuth?: boolean
}
```

`?` 表示可选字段。

类型别名可以描述联合类型：

```ts
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'
```

这比直接写 `string` 更安全，因为调用方不能传 `'PATCHH'` 这种错误值。

也可以组合使用：

```ts
interface FeedState {
  posts: Post[]
  loaded: boolean
  pageSize: number
  hasMore: boolean
}
```

这和后端实体类、DTO 的作用类似，只是 TS 类型只在编译期存在，运行时不会保留。

## 十一、泛型

泛型用于让函数在保持类型安全的同时支持多种数据。

项目中的请求函数是典型例子：

```ts
export function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  // ...
}
```

调用时可以指定返回值类型：

```ts
const profile = await request<MeProfile>('/api/v1/users/me')
```

这样 `profile` 会被 TypeScript 识别成 `MeProfile`。后续访问 `profile.nickname`、`profile.avatar` 等字段时，IDE 能提示，也能检查错误字段。

泛型的核心价值不是“高级”，而是把接口返回值和调用方代码连起来。

## 十二、unknown、any 与类型收窄

`any` 表示放弃类型检查，`unknown` 表示现在还不知道类型，但使用前必须判断。

```ts
function handle(value: unknown) {
  if (typeof value === 'string') {
    return value.trim()
  }
  return ''
}
```

项目中请求体使用：

```ts
data?: unknown
```

这是合理的，因为 HTTP 请求体可以是任意结构，基础请求函数不应该假装知道业务字段。

相比之下，滥用 `any` 会让 TypeScript 退化成 JavaScript。偶尔用可以，长期用就像给所有后端接口都返回 `Map<String, Object>`，确实方便，也确实危险。

## 十三、字面量类型与枚举思维

前端常用字符串字面量表示有限选项：

```ts
type PostListSort = 'rec' | 'new' | 'hot'
```

首页 tab 使用：

```ts
interface SortTab {
  k: PostListSort
  n: string
}

const SORT_TABS: readonly SortTab[] = [
  { k: 'rec', n: '推荐' },
  { k: 'new', n: '最新' },
  { k: 'hot', n: '最热' },
]
```

这样模板里切换排序时，`active` 只能是合法值。

```ts
const active = ref<PostListSort>('rec')
```

如果误写成：

```ts
active.value = 'recommend'
```

TypeScript 会直接报错。

## 十四、数组不可变更新与原地更新

Vue 3 能追踪大多数数组变更，但工程上仍要区分不可变更新和原地更新。

不可变更新：

```ts
this.posts = this.posts.filter((post) => post.id !== postId)
```

原地更新：

```ts
Object.assign(post, patch)
```

项目的 `feed` store 两种方式都用了：

- 删除帖子时重新生成数组。
- 局部更新帖子字段时直接修改对象。

判断标准是：如果要改变集合结构，生成新数组更清晰；如果只是修改已存在对象的几个字段，原地更新更直接。

## 十五、常见工程建议

写 JS/TS 时，建议遵守这些规则：

- 不要在页面里散落重复接口请求逻辑。
- 不要用 `any` 掩盖类型问题。
- 后端可能返回空值的字段，前端类型也要体现出来。
- 接口响应类型放到 `models` 或 API 模块附近。
- 字符串状态值尽量用联合类型约束。
- 异步函数要处理失败路径。
- 对用户可见操作，先考虑 loading、失败、重试和空状态。

## 十六、小结

JS/TS 的学习重点不只是语法本身，而是语法如何服务工程结构：

- 解构和展开用于组织对象更新。
- 箭头函数用于回调和数组处理。
- `async/await` 用于接口、缓存和异步交互。
- 模块化用于拆分页面、API、store、工具函数。
- TypeScript 用接口、联合类型、泛型建立约束。
- Vue 响应式状态会让变量多一层 `.value`，这是需要习惯的地方。

把这些掌握之后，再读 `HebustForumFrontEnd` 的 Vue 文件就不会像看一团陌生符号。至少，它会变成一团有秩序的陌生符号。已经不错了。
