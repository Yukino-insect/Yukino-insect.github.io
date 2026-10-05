+++
date = '2026-10-01T21:00:00+08:00'
draft = false
title = 'React 前端框架：从声明式 UI 到状态、渲染与工程实践'
math = true
+++

React 是一个用于构建用户界面的 JavaScript 库。更准确地说，它提供了一种组织复杂界面的模型：把页面拆成组件，用数据描述界面，在数据变化时让框架计算并提交必要的 DOM 更新。

初学时很容易把 React 误解为“会写 JSX、会用 `useState` 就够了”。这种理解只能让页面暂时显示出来；当页面出现筛选、表单、接口请求、共享状态和性能问题时，代码很快就会失去秩序。React 真正要求掌握的不是某几个 Hook 的拼写，而是**用状态推导 UI、让数据单向流动、把渲染保持为纯计算**。API 会增加，原则不会替你变简单。

本文以一个“文章列表”页面为例，从浏览器直接操作 DOM 的方式开始，逐步解释组件、JSX、状态、事件、数据流、渲染与副作用，并给出进入工程实践前应建立的判断标准。阅读它需要具备 HTML、CSS 与现代 JavaScript 的基础；如果使用 TypeScript，阅读体验会更好，但不是前提。

## 一、React 到底解决了什么问题

一个普通的网页刚开始往往很简单：找到元素，监听事件，修改文本或样式。页面只有一个按钮时，这种方式没有问题。

```js
const button = document.querySelector('#like-button')
const count = document.querySelector('#like-count')

let likes = 0

button.addEventListener('click', () => {
  likes += 1
  count.textContent = String(likes)
})
```

问题在于真实页面并不只有一个文本节点。一次“点赞”可能同时影响按钮文字、列表排序、顶部统计、登录提示和接口请求状态。若每个事件处理函数都直接修改 DOM，代码会逐渐变成下面这种关系：

```text
用户事件
 -> 修改若干变量
   -> 找到并修改多个 DOM 节点
     -> 处理加载、失败、空数据、权限等分支
       -> 另一个事件再次修改同一批节点
```

困难不在于 DOM API 难用，而在于**同一份业务事实被分散地写进了许多 DOM 操作中**。页面变大后，没有人能轻易回答：“现在这个界面为什么会是这个样子？”

React 反过来组织这件事：先保存页面的状态，再把 UI 写成状态的函数。

$$
UI = f(state, props)
$$

其中，`state` 是组件自己会变化的记忆，`props` 是父组件传入的输入。状态变了，不需要你逐个寻找节点并修补；React 会重新计算当前 UI 应是什么样，再把新旧结果比较后，只提交必要的 DOM 修改。

```text
用户事件 / 接口结果
 -> 更新 state
   -> 重新执行组件函数，得到新的 UI 描述
     -> React 比较前后结果
       -> 最小化更新真实 DOM
```

这叫做**声明式 UI**：你声明“数据处于这个状态时页面长什么样”，而不是命令浏览器“把第 17 个节点的文字改成什么”。它不是不再使用 DOM，而是把易错的 DOM 协调工作集中交给框架。

## 二、组件：把界面按职责拆开

React 应用由组件组成。现代 React 中，组件通常就是一个返回 JSX 的 JavaScript 函数。

```tsx
type ArticleCardProps = {
  title: string
  summary: string
}

export function ArticleCard({ title, summary }: ArticleCardProps) {
  return (
    <article className="article-card">
      <h2>{title}</h2>
      <p>{summary}</p>
    </article>
  )
}
```

`ArticleCard` 同时定义了这一小块 UI 的结构、输入和局部行为。它不是浏览器原生标签，所以必须以大写字母开头；小写的 `<article>`、`<h2>` 才会被 React 识别为 HTML 元素。

### 1. JSX 不是字符串，也不是 HTML

JSX 是 JavaScript 的一种语法扩展。构建工具会把它转换成 React 创建 UI 描述的代码，因此它看起来像 HTML，却遵守 JavaScript 的规则。

```tsx
const author = {
  name: '雪乃',
  avatarUrl: '/avatar.png'
}

export function Author() {
  return (
    <div className="author">
      <img src={author.avatarUrl} alt={`${author.name} 的头像`} />
      <span>{author.name}</span>
    </div>
  )
}
```

需要特别注意三点：

- 花括号 `{}` 表示“回到 JavaScript 表达式”。变量、函数调用、三元表达式都放在这里。
- 属性名大多采用 JavaScript 风格，例如 CSS 类使用 `className`，点击事件使用 `onClick`。
- 标签必须闭合；一个组件需要返回一个根结构。没有额外语义节点时可以使用片段 `<>...</>`。

JSX 的价值不是让 HTML 混进 JavaScript，而是让“数据如何成为界面”留在同一个可阅读的上下文里。模板、条件和列表离业务数据越近，越容易看出页面的真实规则。

### 2. 怎样划分组件才不至于过度拆分

假设产品设计给出一个可搜索文章列表，可以先画出层级：

```text
ArticlePage
├─ SearchBar
├─ ArticleStats
└─ ArticleList
   └─ ArticleCard
```

组件边界并不是“每一个 `div` 都单独写一个文件”。更实用的判断是：它是否有独立职责、是否会复用、是否包含自己的状态或行为、是否已经让父组件难以阅读。一个只出现一次且只有两行标记的小片段，留在父组件通常更直接；一个同时管理搜索输入和提交逻辑的区域，则很适合成为 `SearchBar`。

组件应围绕**数据和行为的边界**拆分，而不是围绕视觉盒子机械拆分。把每根线都做成组件，看似精致，实际上只是把理解成本分散到更多文件里而已。

## 三、props：组件之间的输入契约

父组件通过 props 向子组件传数据和回调函数。子组件应把 props 看作只读输入，不能直接修改它。

```tsx
type LikeButtonProps = {
  liked: boolean
  likes: number
  onToggle: () => void
}

function LikeButton({ liked, likes, onToggle }: LikeButtonProps) {
  return (
    <button type="button" onClick={onToggle}>
      {liked ? '取消点赞' : '点赞'} · {likes}
    </button>
  )
}
```

父组件这样使用它：

```tsx
<LikeButton liked={article.liked} likes={article.likes} onToggle={handleToggleLike} />
```

这段代码暗含一个重要方向：**数据向下，事件向上**。

```text
父组件 state
   │  通过 props 向下传递数据
   ▼
子组件显示 UI
   │  用户操作时调用回调
   ▼
父组件更新 state
```

子组件不需要知道文章存在哪里、接口怎样调用；它只负责展示收到的数据，并在点击时通知拥有数据的人。这种单向数据流会让状态变化有来源、有路径，也让组件更容易测试和复用。

## 四、state：组件跨渲染保存的记忆

普通局部变量不能保存用户交互后的数据。组件函数每次渲染都会重新执行，下面的 `count` 既不会保留，也不会通知 React 更新页面。

```tsx
function BrokenCounter() {
  let count = 0

  function handleClick() {
    count += 1
  }

  return <button onClick={handleClick}>点赞 {count}</button>
}
```

应使用 `useState` 声明状态：

```tsx
import { useState } from 'react'

function LikeCounter() {
  const [count, setCount] = useState(0)

  function handleClick() {
    setCount((current) => current + 1)
  }

  return <button onClick={handleClick}>点赞 {count}</button>
}
```

`useState(0)` 返回一对值：当前状态 `count` 与更新函数 `setCount`。调用更新函数不是立刻改写当前这行代码中的变量，而是向 React 请求下一次渲染使用新状态。因此，应把当前渲染中的 state 当作一个**快照**来读取。

### 1. 为什么推荐函数式更新

一次事件中可能基于前一次结果连续更新。若直接写 `setCount(count + 1)` 三次，每次读取的都是同一个旧快照，最终未必得到加三的结果。依赖旧值时，传入更新函数更稳妥：

```tsx
function addThreeLikes() {
  setCount((current) => current + 1)
  setCount((current) => current + 1)
  setCount((current) => current + 1)
}
```

React 会按顺序将这些更新应用到待处理的状态上。这个写法不是仪式感；它明确表达了“新值依赖旧值”，也减少批处理更新带来的误解。

### 2. 对象和数组状态必须按不可变方式更新

状态中的对象、数组不要原地修改后再交回 React。原地修改会让旧快照被污染，也会让比较、调试和 memo 优化失去可靠依据。

```tsx
type Article = {
  id: string
  title: string
  liked: boolean
  likes: number
}

// 不要这样做：直接改动已有对象
// article.liked = true

// 应当创建新的对象
setArticle((current) => ({
  ...current,
  liked: !current.liked,
  likes: current.liked ? current.likes - 1 : current.likes + 1
}))
```

更新数组同样使用 `map`、`filter`、展开语法等返回新数组：

```tsx
setArticles((current) =>
  current.map((article) =>
    article.id === articleId
      ? { ...article, liked: !article.liked }
      : article
  )
)
```

这里的“不可变”不是说 JavaScript 对象真的永远不能改，而是说**已经放入 React state 的值，应当作为本次渲染的只读快照**。需要变更时，以新值替代旧值。

### 3. 哪些数据该放进 state

一个数据适合 state，通常要同时满足：它会随时间或交互变化；它不能完全由现有 props 或 state 计算出来；页面需要用它重新渲染。例如输入框内容、当前页码、接口加载状态、可编辑表单草稿都很合适。

反过来，若一个值可以由已有数据直接推导，就不要复制一份到 state：

```tsx
const [keyword, setKeyword] = useState('')
const [articles] = useState(initialArticles)

// 派生数据：每次渲染时直接计算
const visibleArticles = articles.filter((article) =>
  article.title.toLowerCase().includes(keyword.trim().toLowerCase())
)
```

不要为 `visibleArticles` 再设置 state，也不要用 `useEffect` 在关键字变化后同步它。两份状态终会不一致，并且平白增加一次渲染。只有计算确实昂贵且性能测量证明需要时，再用 `useMemo` 缓存计算结果。

## 五、条件、列表与 key：把数据稳定映射到 UI

React 不发明另一套条件语法。条件渲染直接使用 JavaScript：

```tsx
function ArticlePanel({ loading, error, articles }: ArticlePanelProps) {
  if (loading) {
    return <p>正在加载文章……</p>
  }

  if (error) {
    return <p role="alert">加载失败：{error.message}</p>
  }

  if (articles.length === 0) {
    return <p>没有符合条件的文章。</p>
  }

  return <ArticleList articles={articles} />
}
```

列表通常由 `map` 生成，每个同级项目必须有稳定的 `key`：

```tsx
function ArticleList({ articles }: { articles: Article[] }) {
  return (
    <ul>
      {articles.map((article) => (
        <li key={article.id}>
          <ArticleCard article={article} />
        </li>
      ))}
    </ul>
  )
}
```

`key` 不是传给 `ArticleCard` 的普通 prop，也不是为了消除控制台警告的装饰。它是 React 判断列表项身份的依据。当列表插入、删除、排序时，稳定的 `article.id` 能让 React 把“同一篇文章”的 DOM 与局部状态对应起来。

不要在可变列表中随手使用数组下标作为 `key`。如果在顶部插入新项，后续所有下标都会改变，输入框内容、展开状态等局部状态可能错误地迁移到另一项。仅当列表永不重排、永不插入删除，且没有更稳定的身份标识时，下标才勉强可用。

## 六、完整示例：一个可交互的文章列表

下面的单文件组件使用 TypeScript 实现搜索、分类筛选、点赞和空状态。它没有接入后端，目的是先把 React 最重要的数据关系看清楚；接口、路由与全局状态应该建立在这层清晰关系之上，而不是反过来把它淹没。

```tsx
import { useState } from 'react'

type Article = {
  id: string
  title: string
  category: 'React' | 'TypeScript' | '工程化'
  summary: string
  likes: number
  liked: boolean
}

const initialArticles: Article[] = [
  {
    id: 'react-state',
    title: 'React 状态为什么是快照',
    category: 'React',
    summary: '理解 setState 后为什么不能立即读取新值。',
    likes: 24,
    liked: false
  },
  {
    id: 'ts-contract',
    title: 'TypeScript 如何描述组件契约',
    category: 'TypeScript',
    summary: '让 props、接口数据与组件边界可检查。',
    likes: 18,
    liked: true
  },
  {
    id: 'vite-build',
    title: 'Vite 开发与构建的边界',
    category: '工程化',
    summary: '开发服务器快，不意味着生产构建不需要检查。',
    likes: 12,
    liked: false
  }
]

const categories = ['全部', 'React', 'TypeScript', '工程化'] as const
type CategoryFilter = (typeof categories)[number]

export default function ArticlePage() {
  const [articles, setArticles] = useState(initialArticles)
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState<CategoryFilter>('全部')

  const normalizedKeyword = keyword.trim().toLowerCase()
  const visibleArticles = articles.filter((article) => {
    const matchesKeyword = article.title.toLowerCase().includes(normalizedKeyword)
      || article.summary.toLowerCase().includes(normalizedKeyword)
    const matchesCategory = category === '全部' || article.category === category
    return matchesKeyword && matchesCategory
  })

  function toggleLike(articleId: string) {
    setArticles((currentArticles) =>
      currentArticles.map((article) => {
        if (article.id !== articleId) {
          return article
        }

        const liked = !article.liked
        return {
          ...article,
          liked,
          likes: article.likes + (liked ? 1 : -1)
        }
      })
    )
  }

  return (
    <main>
      <h1>文章列表</h1>

      <label>
        搜索文章
        <input
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="按标题或摘要搜索"
        />
      </label>

      <fieldset>
        <legend>分类</legend>
        {categories.map((item) => (
          <label key={item}>
            <input
              type="radio"
              name="category"
              value={item}
              checked={category === item}
              onChange={() => setCategory(item)}
            />
            {item}
          </label>
        ))}
      </fieldset>

      <p>当前找到 {visibleArticles.length} 篇文章</p>

      {visibleArticles.length === 0 ? (
        <p>没有搜索结果。条件准确固然重要，条件过于苛刻也会得到空白。</p>
      ) : (
        <ul>
          {visibleArticles.map((article) => (
            <li key={article.id}>
              <article>
                <span>{article.category}</span>
                <h2>{article.title}</h2>
                <p>{article.summary}</p>
                <button type="button" onClick={() => toggleLike(article.id)}>
                  {article.liked ? '取消点赞' : '点赞'} · {article.likes}
                </button>
              </article>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
```

这段代码的状态只有三份：原始文章列表、搜索关键字、分类筛选。`normalizedKeyword`、`visibleArticles` 和文章数量都由它们计算得出，因此不是 state。

当用户输入关键字时，`onChange` 调用 `setKeyword`；React 以新的 `keyword` 再次执行 `ArticlePage`；`visibleArticles` 被重新计算；最后 React 仅把列表中真正变化的部分提交到 DOM。点击点赞时也是同一条链路。只要沿着“事件 → 状态 → 渲染结果”的方向排查，绝大多数初学问题都不会显得神秘。

## 七、渲染的本质：计算与提交是两件事

“组件重新渲染”常被误解成“整个页面 DOM 被重建”。这两件事并不相同。一次更新可分为三个阶段：

```text
触发（trigger）
  初次挂载，或 state 更新
       ↓
渲染（render）
  React 调用组件函数，计算新的 JSX/UI 描述
       ↓
提交（commit）
  比较前后结果，把必要的差异写入真实 DOM
```

因此，组件函数在渲染期间应当是纯的：给定相同的 props 与 state，应返回相同的 JSX；不应在函数体中发请求、修改外部变量、启动定时器或直接操作 DOM。

```tsx
// 错误：渲染可能被重复执行，副作用就会重复发生
function BadProfile({ userId }: { userId: string }) {
  fetch(`/api/users/${userId}`)
  return <p>正在加载</p>
}
```

React 开发环境中的 Strict Mode 会额外调用或重新运行某些逻辑，以暴露不纯的渲染和不完整的清理。这不是 React “无缘无故执行两次”，而是你的渲染代码如果有副作用，本来就不应假定它只会被调用一次。

### 1. 组件何时保留 state

React 将 state 与组件在渲染树中的**位置和身份**关联。相同的组件类型在相同位置再次出现时，通常会保留 state；换了位置、换了类型或换了 `key`，React 会把它视为不同组件并重置 state。

```tsx
function UserProfile({ userId }: { userId: string }) {
  return <Profile key={userId} userId={userId} />
}
```

这个 `key` 表达了业务含义：不同用户的资料页是不同实体，切换用户时表单草稿等局部状态应重新开始。不要把 `key` 当作强制刷新的万能按钮；先判断状态是否应该被保留，才知道该不该改变组件身份。

## 八、Effect：只用于同步外部系统

`useEffect` 很重要，也最容易被滥用。它的职责是让 React 状态与**React 之外的系统**保持同步，例如浏览器订阅、计时器、WebSocket、第三方地图组件，或在纯客户端组件中请求数据。

```tsx
import { useEffect, useState } from 'react'

function Clock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setNow(new Date())
    }, 1000)

    return () => {
      window.clearInterval(timerId)
    }
  }, [])

  return <time>{now.toLocaleTimeString()}</time>
}
```

Effect 在渲染提交到页面之后运行；返回的清理函数会在下一次 Effect 重跑前或组件卸载时执行。上例中的清理并非可有可无，否则组件离开页面后计时器仍在工作。

### 1. 不该使用 Effect 的三类场景

- **响应用户操作**：点击购买、保存表单、弹出提示应写在对应事件处理函数中。那里最清楚发生了什么。
- **计算派生数据**：`fullName = firstName + ' ' + lastName`、筛选列表、统计数量应在渲染中计算，必要时再用 `useMemo` 优化。
- **同步一个 state 到另一个 state**：这通常制造重复数据、额外渲染和不同步风险。

如果 Effect 中主要是 `setSomething(...)`，先停下来问：这个值能否从现有 props/state 推导？这个动作是否其实由一次点击触发？多数情况下答案会替你删掉 Effect。保留更少的状态和副作用，调试时也就少一处可能背叛你的地方。

### 2. 请求数据时还要处理竞态与取消

在纯客户端组件中，Effect 可以随查询条件请求数据，但必须处理 loading、error 和过期请求：

```tsx
useEffect(() => {
  const controller = new AbortController()

  async function loadArticles() {
    try {
      setStatus('loading')
      const response = await fetch(`/api/articles?q=${encodeURIComponent(keyword)}`, {
        signal: controller.signal
      })

      if (!response.ok) {
        throw new Error('文章加载失败')
      }

      const data: Article[] = await response.json()
      setArticles(data)
      setStatus('success')
    } catch (error) {
      if ((error as DOMException).name !== 'AbortError') {
        setStatus('error')
      }
    }
  }

  loadArticles()
  return () => controller.abort()
}, [keyword])
```

依赖数组 `[keyword]` 表示：组件使用的外部同步条件是 `keyword`，它变化时需重新请求。不要为了消除依赖警告而随意删依赖，也不要把所有变量都包进 `useCallback`。先让依赖准确表达代码读取的响应式值，再根据实际性能和架构需求重构。

对于需要服务端渲染、缓存、路由级数据加载的大型应用，通常应选择合适的 React 框架或数据获取方案，而不是在每个组件里手写 Effect 请求。React 负责 UI 模型，不等于替你决定全部应用架构。

## 九、Hook 的规则与常用边界

Hook 是以 `use` 开头、接入 React 能力的函数，例如 `useState`、`useEffect`、`useMemo`、`useRef`。它们必须在组件函数或自定义 Hook 的顶层调用，不能放在条件、循环或嵌套函数中。

```tsx
// 错误：两次渲染时 Hook 调用顺序可能不同
if (isLoggedIn) {
  const [profile, setProfile] = useState(null)
}

// 正确：始终先调用 Hook，再根据条件决定渲染什么
const [profile, setProfile] = useState<Profile | null>(null)
if (!isLoggedIn) {
  return <LoginPage />
}
```

这条规则不是任性。React 根据同一组件每次渲染中稳定的 Hook 调用顺序，找回对应 state；条件调用会让这个顺序错位。

常见 Hook 的职责可以简洁地区分：

| Hook | 适合解决的问题 | 不应被误解为 |
| ---- | -------------- | ------------ |
| `useState` | 组件需要记住且会影响 UI 的数据 | 普通变量的替代品 |
| `useEffect` | 与外部系统同步 | 每次数据变化后的通用回调 |
| `useMemo` | 经测量后需要缓存的纯计算 | 默认性能开关 |
| `useCallback` | 需要稳定函数引用的明确场景 | 所有事件函数都必须包一层 |
| `useRef` | 保存不触发渲染的值，或访问 DOM 节点 | 第二套 state |

当多个组件反复共享一套状态逻辑时，可以提取自定义 Hook：

```tsx
import { useState } from 'react'

export function useToggle(initialValue = false) {
  const [value, setValue] = useState(initialValue)

  function toggle() {
    setValue((current) => !current)
  }

  return { value, toggle, setValue }
}
```

自定义 Hook 复用的是**状态逻辑**，不是一份全局状态。每次调用 `useToggle()` 都会得到独立的 state；若需要真正共享数据，应把状态提升到共同父组件、通过 Context 提供，或在规模和需求明确时使用专门的状态管理方案。

## 十、状态应该放在哪里

React 项目复杂后的核心难题，很少是“能否再加一个 Hook”，而是状态所有权。可以按范围从小到大判断：

| 状态类型 | 推荐位置 | 例子 |
| -------- | -------- | ---- |
| 只影响一个组件 | 组件内部 state | 输入框文本、弹窗开关 |
| 多个兄弟组件共享 | 最近共同父组件 | 筛选条件、当前选中项 |
| 多层组件都需要 | Context | 主题、当前语言、已认证用户的基础信息 |
| 跨页面且业务复杂 | 专用状态管理或服务端缓存层 | 全局编辑器状态、复杂工作流 |
| 可分享、可刷新恢复的页面状态 | URL | 页码、搜索词、排序、筛选 |
| 来自服务端的数据 | 请求缓存/数据层 | 文章列表、用户资料、订单详情 |

“全局”不是更高级。把局部表单输入塞进全局 store，会让谁能修改它、何时失效、如何测试都变得含糊。反过来，已经由 URL 表达的筛选条件又只藏在组件 state 中，刷新和分享链接就会丢失状态。状态应尽量放在**刚好覆盖其消费者的最小范围**。

Context 适合减少跨层传递稳定的环境信息，但并不自动等于状态管理方案。若频繁变化的大对象直接放入 Context，所有读取它的消费者都可能重新渲染；先拆分 Context、明确边界，再谈优化。

## 十一、性能：先得到正确结果，再测量

React 的常见性能误区是：一看到组件重新渲染，就立刻给所有函数套 `useCallback`、给所有计算套 `useMemo`、给所有组件套 `memo`。这通常只会增加依赖关系和认知负担，甚至因为依赖写错造成旧数据问题。

更可靠的顺序是：

1. 保持 state 尽量局部，避免一次无关更新从很高的树根扩散。
2. 保持组件纯净，先修复无意的 Effect、重复 state 和原地修改。
3. 使用 React DevTools Profiler 或浏览器性能工具定位真实的慢交互。
4. 针对测到的瓶颈采用 `memo`、`useMemo`、`useCallback`、列表虚拟化或状态拆分。

`key` 稳定、state 位置合理、派生数据不重复保存，往往比记住一串性能 API 更能解决真实问题。优化不是“让组件永不渲染”，而是让用户感受到的交互足够快，同时不牺牲正确性。

## 十二、从组件到工程：React 之外仍有许多工作

React 只解决 UI 的组件化与更新模型。一个可维护的应用还需要路由、样式策略、表单校验、接口层、缓存、测试、构建与部署。常见的 Vite + React + TypeScript 项目可以先按职责组织：

```text
src/
├─ app/             应用入口、路由、全局 Provider
├─ pages/           路由页面
├─ features/        按业务能力组织的组件、状态和请求
├─ components/      跨业务复用的通用 UI
├─ services/        HTTP 客户端与接口请求
├─ hooks/           可复用状态逻辑
├─ types/           跨模块共享类型
└─ styles/          全局样式和设计变量
```

不必在项目第一天就造出复杂的目录体系。目录的目的应是帮助回答“这段代码负责什么、由谁使用、应在哪里修改”，而不是展示某种架构名词。随着业务增长，把页面编排放在 `pages`，把业务能力聚在 `features`，通常比按 `components`、`utils`、`api` 无限制堆叠更容易维持边界。

开始一个练习项目可使用 Vite：

```bash
npm create vite@latest react-learning-demo -- --template react-ts
cd react-learning-demo
npm install
npm run dev
```

然后按小而完整的路径练习：文章列表 → 搜索和筛选 → 详情页路由 → 表单提交 → 接口 loading/error/empty 状态 → 登录权限。每一步都问三个问题：数据的唯一来源在哪里？哪些 UI 由它推导？这次副作用是在响应用户事件，还是在同步外部系统？

## 十三、初学 React 最常见的误区

### 1. 把 state 当作可立即修改的变量

调用 `setState` 后当前渲染中的变量不会立即改变。需要基于旧值计算新值时使用函数式更新；需要在界面上看到新值，就让下一次渲染完成。

### 2. 为每一个计算结果创建 state

筛选结果、总价、全名、是否为空等若可由已有数据计算，就在渲染时计算。重复 state 会增加同步任务，不会增加能力。

### 3. 用 Effect 处理所有变化

Effect 是连接外部世界的桥，不是组件内部流程控制器。用户点击后的业务动作放事件处理函数；纯计算留在渲染阶段。

### 4. 直接修改 state 中的对象或数组

必须创建新的对象或数组交给更新函数。不可变更新让快照、比较和调试都保持可预测。

### 5. 用数组下标充当动态列表的 key

使用数据本身稳定的 ID。否则排序和插入后，DOM 与局部状态可能认错对象。

### 6. 把所有数据塞进全局状态

先使用局部 state；需要共享时提升到最近共同父组件；确实跨层共享再使用 Context 或 store。范围越大，约束与维护成本越高。

### 7. 未测量就全面“性能优化”

`memo`、`useMemo`、`useCallback` 都是工具，不是护身符。先用 profiler 找出慢在哪里，再优化相应边界。

## 十四、总结：用数据推导界面，而不是追着 DOM 修补

React 的核心可以收束为下面几条：

- 组件是 UI 的职责单元，props 是父组件传给子组件的只读输入。
- state 是跨渲染保存的组件记忆；更新 state 会触发新的 UI 计算。
- UI 应由 props 与 state 推导，派生数据不要复制到 state。
- 数据向下流动，用户事件通过回调向上通知，状态放在最小的合理范围。
- 渲染是纯计算；`useEffect` 只负责和浏览器、网络、订阅等外部系统同步。
- React 重新执行组件函数不等于重建全部 DOM；提交阶段只应用必要差异。
- 性能优化必须建立在正确的数据流和实际测量之上。

当你不再从“我要怎样把这个 DOM 改掉”出发，而是能先写出“在这些状态下页面应该是什么样”，React 才真正开始变得简单。之后要学习路由、服务端数据、表单、测试和框架生态，但它们都应建立在这条主线之上；否则不过是在混乱的状态上叠加更多工具而已。

## 延伸阅读

- [React 官方快速入门](https://react.dev/learn)
- [React 官方教程：用 React 的方式思考](https://react.dev/learn/thinking-in-react)
- [React 官方文档：渲染与提交](https://react.dev/learn/render-and-commit)
- [React 官方文档：何时不需要 Effect](https://react.dev/learn/you-might-not-need-an-effect)
