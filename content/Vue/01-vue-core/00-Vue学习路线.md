+++
date = '2026-08-19T18:20:00+08:00'
draft = false
title = 'Vue 学习路线：从页面语法到前端工程能力'
+++

Vue 不是一组模板语法的集合，而是一套组织前端应用的方式。它把页面拆成组件，把状态变成响应式数据，把 DOM 更新交给框架，把业务逻辑放进组合函数和状态管理中。

如果你从零开始学 Vue，推荐按“能看懂 -> 能写页面 -> 能拆组件 -> 能管状态 -> 能做工程”的顺序推进。

## 一、Vue 要解决什么问题

没有框架时，前端代码通常会混在一起：

```text
获取 DOM
 -> 监听事件
 -> 修改变量
 -> 手动更新 DOM
 -> 发请求
 -> 再手动更新 DOM
```

Vue 的思路是：

```text
声明状态
 -> 根据状态渲染页面
 -> 状态变化后自动更新视图
```

你不再直接命令 DOM 怎么改，而是描述“当前状态下页面应该是什么样”。这就是声明式 UI。

## 二、学习阶段

### 1. 入门阶段

掌握：

- 单文件组件。
- 模板插值。
- 属性绑定。
- 事件绑定。
- 条件渲染。
- 列表渲染。
- `ref` 和 `reactive`。

这一阶段目标是能写一个页面。

### 2. 组件阶段

掌握：

- props。
- emits。
- slot。
- 组件拆分。
- 组合函数。
- 受控与非受控状态。

这一阶段目标是能把复杂页面拆成可维护组件。

### 3. 数据流阶段

掌握：

- 接口请求封装。
- loading、error、empty 状态。
- Pinia。
- 本地存储。
- token 和权限。
- 乐观更新。

这一阶段目标是能处理真实业务数据。

### 4. 工程阶段

掌握：

- 路由和页面结构。
- uni-app 页面配置。
- 目录分层。
- 性能优化。
- 类型检查。
- 测试。
- 构建和部署。

这一阶段目标是能维护中大型项目。

## 三、Vue 3 的核心思想

Vue 3 的核心可以概括为四句话：

- 组件是页面的基本组织单位。
- 响应式状态驱动视图更新。
- 组合式 API 负责复用逻辑。
- 工程化工具负责类型、构建和质量。

写 Vue 时，你真正要反复判断的是：

```text
这段代码属于页面、组件、状态、接口、工具函数，还是构建配置？
```

判断清楚位置，代码自然会变清楚。

## 四、推荐练习路径

从一个小应用开始：

```text
文章列表
 -> 文章详情
 -> 发布文章
 -> 登录状态
 -> 个人资料
```

每一步都对应 Vue 的一个能力点：

| 功能 | 训练点 |
| ---- | ------ |
| 文章列表 | 列表渲染、接口请求、加载状态 |
| 文章详情 | 路由参数、详情请求、空状态 |
| 发布文章 | 表单、校验、提交、错误提示 |
| 登录状态 | Pinia、本地存储、token |
| 个人资料 | 组件拆分、图片展示、权限 |

## 五、从后端视角理解 Vue

可以做一个不完全类比：

| 后端概念 | Vue 概念 |
| -------- | -------- |
| Controller | 页面组件 |
| Service | 组合函数或业务模块 |
| DTO | TypeScript 类型 |
| Mapper / Repository | API 请求模块 |
| 全局上下文 | Pinia store |
| 配置文件 | Vite、pages.json、环境变量 |

类比只是辅助，不要照搬。前端还有用户交互、浏览器状态、组件生命周期和渲染性能，这些是后端开发中不太常见的问题。

## 六、学习路线练习讲解：搭建第一个可运行 Vue 项目

这一节的练习不是写某个花哨页面，而是搭好一个以后所有练习都能复用的 Vue 3 + TypeScript 项目。基础工程不稳，后面写得再热闹也只是临时搭台。项目不会因为你一时兴起就保持整洁，真是毫不浪漫。

### 1. 实现目标

做一个文章列表小页面，覆盖最基础的 Vue 能力：

- 使用 Vite 创建 Vue 3 项目。
- 使用 `ref` 管理文章列表和搜索关键字。
- 使用 `computed` 计算搜索结果。
- 使用 `v-model`、`v-for`、`:key`、`@click` 完成页面交互。
- 点赞后更新当前文章的点赞数。

### 2. 创建项目并运行

```bash
npm create vite@latest vue-course-demo -- --template vue-ts
cd vue-course-demo
npm install
npm run dev
```

浏览器访问终端提示的地址，通常是：

```text
http://localhost:5173
```

### 3. 替换 `src/App.vue`

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'

type Post = {
  id: number
  title: string
  summary: string
  author: string
  likes: number
  liked: boolean
}

const keyword = ref('')

const posts = ref<Post[]>([
  {
    id: 1,
    title: 'Vue 响应式到底解决了什么',
    summary: '用状态描述页面，让视图跟随数据变化。',
    author: 'Yuki',
    likes: 12,
    liked: false
  },
  {
    id: 2,
    title: '组合式 API 如何组织业务逻辑',
    summary: '把可复用的状态和行为提取成组合函数。',
    author: 'Haruno',
    likes: 8,
    liked: false
  },
  {
    id: 3,
    title: 'Pinia 适合存放哪些状态',
    summary: '全局状态应该有边界，不是所有数据都该塞进去。',
    author: 'Hikigaya',
    likes: 21,
    liked: true
  }
])

const filteredPosts = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) {
    return posts.value
  }
  return posts.value.filter((post) => {
    return post.title.toLowerCase().includes(text)
      || post.summary.toLowerCase().includes(text)
      || post.author.toLowerCase().includes(text)
  })
})

function toggleLike(post: Post) {
  post.liked = !post.liked
  post.likes += post.liked ? 1 : -1
}
</script>

<template>
  <main class="page">
    <header class="header">
      <h1>Vue 文章练习</h1>
      <input v-model="keyword" placeholder="搜索标题、摘要或作者" />
    </header>

    <p v-if="filteredPosts.length === 0" class="empty">
      没有搜索结果。不是页面坏了，只是条件太苛刻。
    </p>

    <section v-else class="list">
      <article v-for="post in filteredPosts" :key="post.id" class="card">
        <div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.summary }}</p>
          <span>作者：{{ post.author }}</span>
        </div>
        <button :class="{ liked: post.liked }" @click="toggleLike(post)">
          {{ post.liked ? '已赞' : '点赞' }} · {{ post.likes }}
        </button>
      </article>
    </section>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 20px;
  color: #1f2937;
}

.header {
  display: grid;
  gap: 16px;
  margin-bottom: 24px;
}

h1 {
  margin: 0;
  font-size: 28px;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 16px;
}

.list {
  display: grid;
  gap: 14px;
}

.card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

p {
  margin: 0 0 8px;
  color: #475569;
}

span {
  color: #64748b;
  font-size: 14px;
}

button {
  flex: 0 0 auto;
  padding: 8px 12px;
  border: 1px solid #94a3b8;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

button.liked {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.empty {
  padding: 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
}
</style>
```

### 4. 检查结果

运行后应该能看到三篇文章。输入关键字时列表会过滤，点击点赞按钮会切换状态并修改点赞数。这里已经包含后续 Vue 页面最常见的骨架：源数据、派生数据、用户输入、列表渲染和事件处理。

## 七、精通 Vue 的标志

不是会背所有 API，而是能做到：

- 能判断状态应该放组件内、父组件、Pinia，还是 URL。
- 能拆出职责清晰的组件。
- 能封装请求并统一处理错误。
- 能解释响应式数据为什么更新或不更新。
- 能处理表单、列表、权限、加载、空态和失败态。
- 能定位构建、类型和跨端问题。
- 能让代码在需求变化时仍然可维护。

Vue 不难入门，但想写得稳，需要你保持一点结构感。随便能跑的代码很多，能长期维护的代码并不多。
