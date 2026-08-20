+++
date = '2026-08-20T18:34:00+08:00'
draft = false
title = '接口响应、表单和组件 Props 建模：让 TypeScript 进入真实业务'
+++

TypeScript 学到最后，一定要回到业务。会写 `Partial`、`infer`、`keyof` 只是工具，真正的问题是：接口返回的数据、页面展示的数据、表单编辑的数据和组件接收的数据，它们是不是同一个东西？

很多项目类型混乱，不是因为语法不熟，而是因为这些边界没有分开。

## 一、先区分四类模型

前端常见模型可以分成四类：

| 模型 | 说明 |
| ---- | ---- |
| 接口响应模型 | 后端实际返回的数据 |
| 页面展示模型 | 页面渲染需要的数据 |
| 表单模型 | 用户正在编辑的数据 |
| 提交参数模型 | 最终发给后端的数据 |

它们有时长得很像，但不应该默认等同。

例如文章详情：

```ts
type PostResponse = {
  id: number
  title: string
  content: string | null
  author: {
    id: number
    name: string | null
  } | null
  like_count: number | null
  created_at: string
}
```

页面展示模型可以更干净：

```ts
type PostDetail = {
  id: number
  title: string
  content: string
  authorName: string
  likeCount: number
  createdAtText: string
}
```

中间需要映射函数。

## 二、接口响应泛型

统一响应结构：

```ts
type ApiResponse<T> = {
  code: number
  message: string
  data: T
}
```

分页结构：

```ts
type PageResult<T> = {
  records: T[]
  total: number
  page: number
  pageSize: number
}
```

组合：

```ts
type PostPageResponse = ApiResponse<PageResult<PostResponse>>
```

请求函数：

```ts
async function fetchPostPage(): Promise<PageResult<PostResponse>> {
  const response = await fetch('/api/posts')
  const result = await response.json() as ApiResponse<PageResult<PostResponse>>
  return result.data
}
```

这里的 `as` 只是告诉 TypeScript 你期望的结构，不会校验真实响应。生产项目里如果接口不可信，需要运行时校验。

## 三、响应模型到展示模型

不要把字段兜底散落在模板里。推荐写 mapper。

```ts
function toPostDetail(response: PostResponse): PostDetail {
  return {
    id: response.id,
    title: response.title.trim() || '未命名文章',
    content: response.content ?? '',
    authorName: response.author?.name ?? '匿名用户',
    likeCount: response.like_count ?? 0,
    createdAtText: formatDate(response.created_at)
  }
}
```

好处：

- 接口字段风格可以和页面字段风格分开。
- 空值兜底集中处理。
- 模板更干净。
- 后端字段调整时有明确修改位置。

这一步很朴素，却能让页面代码少很多噪音。

## 四、列表项和详情不一定同型

列表通常不需要详情全部字段。

```ts
type PostListItemResponse = {
  id: number
  title: string
  summary: string | null
  like_count: number
}

type PostCard = {
  id: number
  title: string
  summary: string
  likeCountText: string
}
```

不要为了省事让列表使用 `PostDetail`。字段越多，依赖越重，后续越不敢改。

## 五、表单模型

表单模型描述用户正在编辑的数据。

```ts
type PostForm = {
  title: string
  content: string
  tagIds: number[]
  publishNow: boolean
}
```

提交参数可能不同：

```ts
type CreatePostRequest = {
  title: string
  content: string
  tagIds: number[]
  status: 'draft' | 'published'
}
```

转换函数：

```ts
function toCreatePostRequest(form: PostForm): CreatePostRequest {
  return {
    title: form.title.trim(),
    content: form.content,
    tagIds: form.tagIds,
    status: form.publishNow ? 'published' : 'draft'
  }
}
```

表单里的 `publishNow` 是 UI 字段，不一定应该原样提交给后端。

## 六、新增和编辑表单

新增和编辑可以共享一部分字段。

```ts
type PostEditableFields = {
  title: string
  content: string
  tagIds: number[]
}

type CreatePostRequest = PostEditableFields & {
  status: 'draft' | 'published'
}

type UpdatePostRequest = Partial<PostEditableFields>
```

编辑时常用局部更新，但不代表所有字段都可以随便缺失。是否使用 `Partial`，取决于后端接口语义。

如果后端要求 PUT 全量更新，就不要用 `Partial`：

```ts
type ReplacePostRequest = PostEditableFields
```

## 七、请求状态建模

页面请求不要只写一个 `loading`。

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'empty' }
  | { status: 'error'; message: string }
```

使用：

```ts
type PostPageState = LoadState<PageResult<PostCard>>
```

渲染：

```ts
function getPageText(state: PostPageState): string {
  switch (state.status) {
    case 'idle':
      return '尚未加载'
    case 'loading':
      return '加载中'
    case 'success':
      return `共 ${state.data.total} 条`
    case 'empty':
      return '暂无文章'
    case 'error':
      return state.message
  }
}
```

状态建模越清楚，页面条件判断越少互相打架。

## 八、组件 Props

组件 Props 应该表达组件真正依赖什么。

```ts
type UserCardProps = {
  user: {
    id: number
    name: string
    avatarUrl?: string
  }
  size?: 'small' | 'medium' | 'large'
  showActions?: boolean
}
```

如果多个组件使用同一展示模型，可以抽类型：

```ts
type UserCardModel = {
  id: number
  name: string
  avatarUrl?: string
}

type UserCardProps = {
  user: UserCardModel
  size?: 'small' | 'medium' | 'large'
  showActions?: boolean
}
```

不要让组件直接依赖庞大的后端响应模型。组件需要什么，就给什么。

## 九、Vue defineProps

Vue 组合式写法：

```ts
type ButtonProps = {
  type?: 'primary' | 'default' | 'danger'
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<ButtonProps>(), {
  type: 'default',
  loading: false,
  disabled: false
})
```

事件也可以建模：

```ts
const emit = defineEmits<{
  submit: [id: number]
  cancel: []
}>()

emit('submit', 1)
emit('cancel')
```

事件名和参数都能被检查。

## 十、表格列配置

表格列可以用泛型约束字段名。

```ts
type TableColumn<T> = {
  key: keyof T
  title: string
  width?: number
  render?: (row: T) => string
}

type PostCard = {
  id: number
  title: string
  likeCount: number
}

const columns: TableColumn<PostCard>[] = [
  {
    key: 'title',
    title: '标题'
  },
  {
    key: 'likeCount',
    title: '点赞数',
    render: row => `${row.likeCount} 个赞`
  }
]
```

字段名写错时会报错。这种类型约束很适合重复出现的组件配置。

## 十一、错误模型

错误也应该建模。

```ts
type ApiError =
  | { type: 'unauthorized'; message: string }
  | { type: 'forbidden'; message: string }
  | { type: 'validation'; fields: Record<string, string> }
  | { type: 'network'; message: string }
```

处理：

```ts
function getErrorText(error: ApiError): string {
  switch (error.type) {
    case 'unauthorized':
      return '登录已过期'
    case 'forbidden':
      return '没有权限'
    case 'validation':
      return Object.values(error.fields).join('，')
    case 'network':
      return error.message
  }
}
```

把错误分清楚，页面才能做正确响应。所有错误都叫 `Error`，最后就只能统一弹一个“系统异常”，也算一种放弃思考。

## 十二、目录组织

按领域组织类型：

```text
src/
  domains/
    post/
      post.model.ts
      post.api.ts
      post.mapper.ts
      post.state.ts
      components/
        PostCard.vue
```

`post.model.ts`：

```ts
export type PostResponse = {
  id: number
  title: string
}

export type PostCard = {
  id: number
  title: string
}
```

`post.mapper.ts`：

```ts
import type { PostCard, PostResponse } from './post.model'

export function toPostCard(response: PostResponse): PostCard {
  return {
    id: response.id,
    title: response.title.trim() || '未命名文章'
  }
}
```

注意 `import type` 表示只导入类型，构建后不会产生运行时代码依赖。

## 十三、建模检查清单

- 这是后端响应、页面展示、表单编辑，还是提交参数？
- 字段名是否需要从下划线转换成驼峰？
- 空值是否已经集中兜底？
- 后端枚举值是否用字面量联合约束？
- 页面状态是否能用判别联合表达？
- 组件 Props 是否只包含组件真正需要的数据？
- 是否把一个大类型传得到处都是？
- 是否需要 mapper 把外部数据变成内部模型？

## 十四、练习

给文章列表页建模：

- 后端返回 `PostListItemResponse`，字段包括 `id`、`title`、`summary`、`like_count`、`created_at`。
- 页面使用 `PostCard`，字段包括 `id`、`title`、`summary`、`likeCountText`、`createdAtText`。
- 定义 `PageResult<T>`。
- 定义 `LoadState<T>`。
- 写 `toPostCard(response)`。

参考：

```ts
type PostListItemResponse = {
  id: number
  title: string
  summary: string | null
  like_count: number
  created_at: string
}

type PostCard = {
  id: number
  title: string
  summary: string
  likeCountText: string
  createdAtText: string
}

function toPostCard(response: PostListItemResponse): PostCard {
  return {
    id: response.id,
    title: response.title.trim() || '未命名文章',
    summary: response.summary ?? '暂无摘要',
    likeCountText: `${response.like_count} 个赞`,
    createdAtText: formatDate(response.created_at)
  }
}
```

真正的 TypeScript 工程能力，就是让类型贴着业务边界生长。类型不应该只证明“这段代码能编译”，还应该帮助你看清数据从哪里来、到哪里去、中间发生了什么变化。
