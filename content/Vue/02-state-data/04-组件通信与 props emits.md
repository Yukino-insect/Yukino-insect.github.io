+++
date = '2026-08-21T21:30:00+08:00'
draft = false
title = '组件通信与 props emits：父组件怎样把数据交给子组件'
+++

前面讲单文件组件时，已经知道一个 `.vue` 文件可以包含 `<script setup>`、`<template>` 和 `<style scoped>`。但只知道这些还不够，因为真实页面不会永远只有一个组件。

一旦把页面拆成组件，就会遇到两个问题：

- 父组件的数据，怎么传给子组件？
- 子组件里的按钮被点击后，怎么通知父组件修改数据？

这篇可以作为《组件通信、插槽与组合函数：把复杂页面拆得有秩序》中 `props` 和 `emits` 部分的细化补充。那篇更关心组件通信方式如何选择，这篇则专门把父子组件通信的基础语法讲透。

在 Vue 中，最基础、最重要的答案就是：

```text
父组件通过 props 向子组件传数据
子组件通过 emits 向父组件发事件
```

也就是常说的：

```text
props down, events up
```

数据从父组件往下传，事件从子组件往上传。这个方向最好一开始就记清楚，否则后面组件一多，状态会乱得很有层次感，当然，是不值得欣赏的那种层次感。

## 一、先看父组件使用子组件

在父组件 `App.vue` 中，可以这样使用文章卡片组件：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import PostCard from './components/PostCard.vue'

const post = ref({
  title: '单文件组件不是把代码随便塞进一个文件',
  summary: '',
  author: 'Yuki',
  likes: 7,
  liked: false
})

function handleLike() {
  post.value.liked = !post.value.liked
  post.value.likes += post.value.liked ? 1 : -1
}
</script>

<template>
  <PostCard
    :title="post.title"
    :summary="post.summary"
    :author="post.author"
    :likes="post.likes"
    :liked="post.liked"
    @like="handleLike"
  />
</template>
```

这段代码的核心是：

```vue
<PostCard
  :title="post.title"
  :summary="post.summary"
  :author="post.author"
  :likes="post.likes"
  :liked="post.liked"
  @like="handleLike"
/>
```

它不是普通 HTML 标签，而是一个组件标签。`PostCard` 来自这行导入：

```ts
import PostCard from './components/PostCard.vue'
```

在 `<script setup>` 中，导入的组件可以直接在模板里使用，不需要再写 `components: { PostCard }`。这是 Vue 3 `<script setup>` 帮你省掉的样板代码。

## 二、这些冒号绑定是什么意思

来看这一组：

```vue
:title="post.title"
:summary="post.summary"
:author="post.author"
:likes="post.likes"
:liked="post.liked"
```

冒号 `:` 是 `v-bind` 的简写，表示右边是 JavaScript 表达式，不是普通字符串。

也就是说：

```vue
:title="post.title"
```

含义是：

```text
把父组件中 post.title 的值，作为 title 这个 prop 传给 PostCard
```

其他几个也是一样：

| 父组件写法 | 传给子组件的 prop | 值来自哪里 |
| ---------- | ----------------- | ---------- |
| `:title="post.title"` | `title` | `post.title` |
| `:summary="post.summary"` | `summary` | `post.summary` |
| `:author="post.author"` | `author` | `post.author` |
| `:likes="post.likes"` | `likes` | `post.likes` |
| `:liked="post.liked"` | `liked` | `post.liked` |

所以这段代码可以理解成：父组件把一篇文章的数据拆成几个属性，交给 `PostCard` 展示。

如果不写冒号：

```vue
<PostCard likes="7" />
```

这里传过去的是字符串 `"7"`，不是数字 `7`。

如果写冒号：

```vue
<PostCard :likes="7" />
```

这里传过去的才是数字 `7`。

同理，布尔值也应该用动态绑定：

```vue
<PostCard :liked="false" />
```

不要写成：

```vue
<PostCard liked="false" />
```

后者传过去的是字符串 `"false"`。字符串只要不是空字符串，在很多判断里都会被当成真值。这个问题不难，但足够让人浪费一个下午，实在朴素得令人不快。

## 三、@like 是什么意思

这一行：

```vue
@like="handleLike"
```

表示父组件监听子组件发出的 `like` 事件。

它的含义是：

```text
当 PostCard 触发 like 事件时，父组件执行 handleLike
```

注意，这里的 `like` 不是浏览器原生事件。浏览器原生事件有 `click`、`input`、`submit` 这些。`like` 是我们给组件自定义的事件名。

父组件这样写：

```vue
@like="handleLike"
```

子组件内部就需要这样触发：

```vue
@click="emit('like')"
```

完整关系是：

```text
用户点击子组件按钮
 -> 子组件 emit('like')
 -> 父组件监听到 @like
 -> 父组件执行 handleLike
 -> 父组件修改 post
 -> 新的 props 再传给子组件
 -> 子组件重新渲染
```

这就是父子组件通信的基本闭环。

## 四、子组件声明 props

在 `PostCard.vue` 中，子组件需要声明自己要接收哪些数据：

```vue
<script setup lang="ts">
type Props = {
  title: string
  summary?: string
  author: string
  likes: number
  liked: boolean
}

withDefaults(defineProps<Props>(), {
  summary: ''
})
</script>
```

这里先定义了一个 TypeScript 类型：

```ts
type Props = {
  title: string
  summary?: string
  author: string
  likes: number
  liked: boolean
}
```

它表示这个组件允许接收这些 props：

| prop | 类型 | 是否必传 | 含义 |
| ---- | ---- | -------- | ---- |
| `title` | `string` | 是 | 文章标题 |
| `summary` | `string` | 否 | 文章摘要 |
| `author` | `string` | 是 | 作者 |
| `likes` | `number` | 是 | 点赞数 |
| `liked` | `boolean` | 是 | 当前用户是否已点赞 |

其中：

```ts
summary?: string
```

问号 `?` 表示这个 prop 可选。也就是说，父组件可以传 `summary`，也可以不传。

## 五、defineProps 是什么

这一段：

```ts
defineProps<Props>()
```

表示声明当前组件接收的 props，并且使用 `Props` 这个 TypeScript 类型进行约束。

也就是说：

```ts
defineProps<Props>()
```

告诉 Vue 和 TypeScript：

```text
这个组件接收 title、summary、author、likes、liked 这些 props
它们的类型必须符合 Props 的定义
```

如果父组件传错类型，比如：

```vue
<PostCard :likes="'7'" />
```

TypeScript 就有机会提示你：`likes` 应该是 `number`，不是 `string`。

这里要注意：`defineProps` 是 Vue 在 `<script setup>` 中提供的**编译宏**。它看起来像普通函数，但不需要从 `vue` 中导入。

不需要这样写：

```ts
import { defineProps } from 'vue'
```

在 `<script setup>` 中直接用就可以。

## 六、withDefaults 是什么

这一段是很多初学者会卡住的地方：

```ts
withDefaults(defineProps<Props>(), {
  summary: ''
})
```

可以拆成两层看。

第一层：

```ts
defineProps<Props>()
```

声明组件接收哪些 props。

第二层：

```ts
withDefaults(..., {
  summary: ''
})
```

给可选 prop 设置默认值。

合起来就是：

```text
PostCard 接收 Props 中声明的那些 props
如果父组件没有传 summary，就让 summary 默认等于空字符串
```

所以父组件这样写也可以：

```vue
<PostCard
  :title="post.title"
  :author="post.author"
  :likes="post.likes"
  :liked="post.liked"
/>
```

即使没有传 `summary`，子组件里拿到的 `summary` 也会是 `''`。

这就是下面这段代码的作用：

```ts
withDefaults(defineProps<Props>(), {
  summary: ''
})
```

更直白地说，它做了两件事：

- 用 `defineProps<Props>()` 声明组件入参。
- 用 `withDefaults` 给可选入参设置默认值。

## 七、为什么明明定义了 props，模板里却直接写 title

子组件模板里是这样写的：

```vue
<h2>{{ title }}</h2>
<p>{{ summary || '这篇文章还没有摘要。作者很可能以为标题已经足够说明一切。' }}</p>
<span>作者：{{ author }}</span>
```

你可能会问：不是写了 `const props = ...` 吗？为什么这里不是：

```vue
<h2>{{ props.title }}</h2>
```

原因是：在 Vue 的 `<script setup>` 中，`defineProps` 声明的 props 会暴露给模板，模板里可以直接使用 prop 名称。

所以在模板中：

```vue
{{ title }}
```

等价于在使用当前组件接收到的 `title` prop。

这些写法都来自父组件传进来的值：

```vue
<h2>{{ title }}</h2>
<p>{{ summary }}</p>
<span>{{ author }}</span>
<button>{{ likes }}</button>
```

对应关系是：

| 子组件模板使用 | 来自父组件 |
| -------------- | ---------- |
| `title` | `:title="post.title"` |
| `summary` | `:summary="post.summary"` |
| `author` | `:author="post.author"` |
| `likes` | `:likes="post.likes"` |
| `liked` | `:liked="post.liked"` |

不过，在 `<script setup>` 的 JavaScript 代码里，如果你要读取 prop，通常要通过 `props`：

```ts
console.log(props.title)
```

模板里可以直接写 `title`，脚本里更常见的是写 `props.title`。这不是玄学，只是 `<script setup>` 的编译规则。

## 八、props 变量没有用，可以不写吗

上面的代码写了：

```ts
const props = withDefaults(defineProps<Props>(), {
  summary: ''
})
```

但模板里没有写 `props.title`，脚本里也没有读取 `props`。这时很多编辑器可能会提示：

```text
props is assigned a value but never used
```

如果你确实不需要在 `<script setup>` 的 JavaScript 部分访问 props，可以写成：

```ts
withDefaults(defineProps<Props>(), {
  summary: ''
})
```

这样仍然会声明 props，也仍然会设置默认值。

但如果脚本里需要使用 props，比如根据标题计算一个值：

```vue
<script setup lang="ts">
import { computed } from 'vue'

type Props = {
  title: string
  summary?: string
}

const props = withDefaults(defineProps<Props>(), {
  summary: ''
})

const titleLength = computed(() => props.title.length)
</script>
```

这时就应该保留 `const props = ...`。

## 九、defineEmits 是什么

子组件里还有这一段：

```ts
const emit = defineEmits<{
  like: []
}>()
```

它表示当前组件会向外触发一个名为 `like` 的事件，并且这个事件不携带参数。

也就是说，子组件允许这样写：

```ts
emit('like')
```

如果你写错事件名：

```ts
emit('liked')
```

TypeScript 就会提示：没有声明过 `liked` 这个事件。

这里的类型：

```ts
{
  like: []
}
```

可以理解成：

```text
事件名是 like
参数列表是空数组
```

所以 `like: []` 表示：

```text
触发 like 事件时，不需要传任何参数
```

如果事件要传参数，可以这样写：

```ts
const emit = defineEmits<{
  remove: [id: number]
}>()
```

触发时：

```ts
emit('remove', 1)
```

父组件监听：

```vue
<PostCard @remove="handleRemove" />
```

父组件方法：

```ts
function handleRemove(id: number) {
  console.log(id)
}
```

这就是带参数的自定义事件。

## 十、为什么子组件不直接修改 liked 和 likes

你可能会想：`PostCard` 里已经拿到了 `liked` 和 `likes`，为什么不直接在子组件里修改？

比如这样：

```ts
liked = !liked
likes += liked ? 1 : -1
```

这不是推荐做法。原因是：`liked` 和 `likes` 是父组件传下来的 props。Vue 中 props 应该被看作只读数据。

父组件拥有这份状态：

```ts
const post = ref({
  likes: 7,
  liked: false
})
```

子组件只是负责展示它：

```vue
<button :class="{ active: liked }">
  {{ liked ? '已点赞' : '点赞' }} · {{ likes }}
</button>
```

当用户点击按钮时，子组件不直接修改 props，而是通知父组件：

```vue
@click="emit('like')"
```

父组件收到事件后再修改自己的数据：

```ts
function handleLike() {
  post.value.liked = !post.value.liked
  post.value.likes += post.value.liked ? 1 : -1
}
```

这样数据来源非常清楚：

```text
post 数据属于父组件
PostCard 只负责展示和发出用户意图
```

如果子组件随便修改父组件传下来的数据，数据流就会变成：

```text
父组件能改
子组件也能改
其他子组件可能也能改
```

到那时你看到页面状态不对，就很难判断到底是谁改的。程序当然不会替你感到愧疚，它只会照常运行。

## 十一、完整拆解 PostCard.vue

下面重新看子组件代码：

```vue
<script setup lang="ts">
type Props = {
  title: string
  summary?: string
  author: string
  likes: number
  liked: boolean
}

withDefaults(defineProps<Props>(), {
  summary: ''
})

const emit = defineEmits<{
  like: []
}>()
</script>

<template>
  <article class="post-card">
    <div class="content">
      <h2>{{ title }}</h2>
      <p>{{ summary || '这篇文章还没有摘要。作者很可能以为标题已经足够说明一切。' }}</p>
      <span>作者：{{ author }}</span>
    </div>

    <button
      class="like-button"
      :class="{ active: liked }"
      :aria-pressed="liked"
      @click="emit('like')"
    >
      {{ liked ? '已点赞' : '点赞' }} · {{ likes }}
    </button>
  </article>
</template>
```

逐段解释：

- `type Props = ...`：定义这个组件需要哪些外部数据。
- `defineProps<Props>()`：声明组件接收这些 props。
- `withDefaults(..., { summary: '' })`：给可选的 `summary` 设置默认值。
- `defineEmits<{ like: [] }>()`：声明这个组件会发出 `like` 事件。
- `{{ title }}`：显示父组件传入的标题。
- `{{ summary || 默认文案 }}`：如果摘要为空，就显示默认文案。
- `{{ author }}`：显示父组件传入的作者。
- `:class="{ active: liked }"`：如果已经点赞，就给按钮加上 `active` 类。
- `:aria-pressed="liked"`：告诉辅助技术这个按钮是否处于按下状态。
- `@click="emit('like')"`：点击按钮时，向父组件发出 `like` 事件。
- `{{ likes }}`：显示父组件传入的点赞数。

这段代码的本质是：

```text
PostCard 不拥有文章数据
PostCard 接收文章数据
PostCard 展示文章数据
PostCard 把用户点击事件通知父组件
```

## 十二、父组件和子组件的职责

在这个例子中，父组件 `App.vue` 的职责是：

- 保存文章状态。
- 决定传哪些数据给 `PostCard`。
- 监听 `PostCard` 发出的事件。
- 修改点赞状态和点赞数。

子组件 `PostCard.vue` 的职责是：

- 声明自己需要哪些 props。
- 根据 props 渲染卡片内容。
- 根据 props 切换按钮样式。
- 在按钮点击时发出事件。

可以这样理解：

```text
父组件负责数据和决策
子组件负责展示和通知
```

这不是绝对规则，但对初学组件通信非常有用。

## 十三、为什么要把文章卡片拆成组件

如果页面只有一张卡片，拆不拆都可以。但如果有文章列表：

```vue
<PostCard
  v-for="post in posts"
  :key="post.id"
  :title="post.title"
  :summary="post.summary"
  :author="post.author"
  :likes="post.likes"
  :liked="post.liked"
  @like="handleLike(post)"
/>
```

拆成组件的价值就很明显：

- 卡片结构只写一次。
- 样式只维护一份。
- 父组件更关注列表数据。
- 子组件更关注单张卡片如何展示。

对于列表场景，父组件负责循环：

```vue
v-for="post in posts"
```

子组件负责单项展示：

```vue
<PostCard ... />
```

这就是组件拆分最常见的用法之一。

## 十四、一个更完整的列表例子

父组件可以这样管理多篇文章：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import PostCard from './components/PostCard.vue'

type Post = {
  id: number
  title: string
  summary: string
  author: string
  likes: number
  liked: boolean
}

const posts = ref<Post[]>([
  {
    id: 1,
    title: '单文件组件与模板语法',
    summary: '理解 Vue 页面由哪些部分组成。',
    author: 'Yuki',
    likes: 7,
    liked: false
  },
  {
    id: 2,
    title: '响应式原理与组合式 API',
    summary: '',
    author: 'Haruno',
    likes: 12,
    liked: true
  }
])

function handleLike(post: Post) {
  post.liked = !post.liked
  post.likes += post.liked ? 1 : -1
}
</script>

<template>
  <main class="page">
    <PostCard
      v-for="post in posts"
      :key="post.id"
      :title="post.title"
      :summary="post.summary"
      :author="post.author"
      :likes="post.likes"
      :liked="post.liked"
      @like="handleLike(post)"
    />
  </main>
</template>
```

这里有一个细节：

```vue
@like="handleLike(post)"
```

它表示每一张卡片触发 `like` 事件时，父组件都知道是哪一篇文章被点了赞。

也可以让子组件把 `id` 发上来：

```ts
const emit = defineEmits<{
  like: [id: number]
}>()
```

子组件触发：

```vue
<script setup lang="ts">
type Props = {
  id: number
  title: string
  summary?: string
  author: string
  likes: number
  liked: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  like: [id: number]
}>()
</script>

<template>
  <button @click="emit('like', id)">
    点赞
  </button>
</template>
```

父组件监听：

```vue
<PostCard
  :id="post.id"
  @like="handleLike"
/>
```

父组件处理：

```ts
function handleLike(id: number) {
  const post = posts.value.find((item) => item.id === id)
  if (!post) {
    return
  }

  post.liked = !post.liked
  post.likes += post.liked ? 1 : -1
}
```

两种写法都可以。初学时，用 `@like="handleLike(post)"` 更直观；业务更复杂时，让事件带上 `id` 会更清晰。

## 十五、props 命名：模板里可以用短横线

如果 prop 名是驼峰：

```ts
type Props = {
  likedByMe: boolean
}
```

父组件模板中推荐写成短横线：

```vue
<PostCard :liked-by-me="post.likedByMe" />
```

子组件中仍然用驼峰访问：

```vue
<button :class="{ active: likedByMe }">
  点赞
</button>
```

原因是 HTML 属性不区分大小写，模板里使用短横线更符合 HTML 习惯。对于 `title`、`summary`、`author` 这种单词 prop，就没有这个问题。

## 十六、常见错误

### 1. 把动态值写成静态字符串

不推荐：

```vue
<PostCard likes="post.likes" liked="post.liked" />
```

这样传过去的是字符串 `"post.likes"` 和 `"post.liked"`。

推荐：

```vue
<PostCard :likes="post.likes" :liked="post.liked" />
```

### 2. 在子组件里直接修改 props

不推荐：

```ts
props.likes++
```

推荐：

```ts
emit('like')
```

让父组件去修改真正的数据。

### 3. 子组件触发的事件名和父组件监听的不一致

子组件：

```ts
emit('like')
```

父组件必须监听：

```vue
@like="handleLike"
```

如果父组件写成：

```vue
@liked="handleLike"
```

那就监听不到。名字都对不上，程序当然也不会凭爱意理解你。

### 4. 可选 prop 没有默认值

如果 `summary` 可选：

```ts
summary?: string
```

模板里直接使用时，要么给默认值：

```ts
withDefaults(defineProps<Props>(), {
  summary: ''
})
```

要么在模板里处理空值：

```vue
{{ summary || '暂无摘要' }}
```

两者可以同时存在。`withDefaults` 保证 `summary` 至少是字符串，模板里的 `||` 则处理空字符串时的展示文案。

## 十七、总结

把这套组件知识压缩成几句话：

- `PostCard` 是子组件，父组件导入后可以像标签一样使用。
- `:title="post.title"` 表示把父组件的 `post.title` 动态传给子组件的 `title` prop。
- `@like="handleLike"` 表示监听子组件发出的 `like` 事件，并执行父组件方法。
- `defineProps<Props>()` 用来声明子组件接收哪些 props。
- `withDefaults` 用来给可选 props 设置默认值。
- `defineEmits` 用来声明子组件可以向外发出哪些事件。
- 模板中可以直接使用 `title`、`summary`、`author`、`likes`、`liked`，因为它们是当前组件接收到的 props。
- props 是父组件传下来的数据，子组件应当把它当作只读数据。
- 子组件想改变父组件的数据时，不直接改 props，而是 `emit` 一个事件通知父组件。

所以这段父组件代码：

```vue
<PostCard
  :title="post.title"
  :summary="post.summary"
  :author="post.author"
  :likes="post.likes"
  :liked="post.liked"
  @like="handleLike"
/>
```

表达的是：

```text
把 post 的数据交给 PostCard 展示
当 PostCard 说“用户点了赞”时，由父组件 handleLike 修改 post
```

而这段子组件代码：

```ts
withDefaults(defineProps<Props>(), {
  summary: ''
})

const emit = defineEmits<{
  like: []
}>()
```

表达的是：

```text
我这个组件需要接收哪些外部数据
哪些数据有默认值
我这个组件会向外通知哪些事件
```

组件通信并不神秘。它只是把页面拆开以后，给“数据从哪里来”和“操作通知谁”定了一条清楚的路线。路线清楚，组件就不会互相扯袖子；路线不清楚，代码就会开始用一种很安静的方式报复你。
