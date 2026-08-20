+++
date = '2026-08-19T18:21:00+08:00'
draft = false
title = 'Vite、环境变量、调试、质量工具与构建部署：把代码交付得更可靠'
+++

能写代码只是第一步。能稳定启动、构建、检查、调试、交付，才算进入工程阶段。Vite 是现代前端常用构建工具，它把开发服务器、模块转换、资源处理、生产构建串起来。

这篇文章不只讲“怎么配置 Vite”，还会把环境变量、调试、TypeScript、ESLint、Prettier、测试、构建部署放在同一条交付链路里理解。工具不是摆设，质量也不是上线前临时祈祷。

## 一、Vite 负责什么

Vite 是前端构建工具。它主要由两部分组成：

- 开发服务器：基于原生 ES Module 提供快速启动和热更新。
- 生产构建：把源码打包、压缩、拆分，生成可部署产物。

常见脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

三条命令不要混淆：

| 命令 | 作用 | 使用场景 |
| ---- | ---- | -------- |
| `vite` | 启动开发服务器 | 本地开发 |
| `vite build` | 构建生产产物 | 打包上线 |
| `vite preview` | 本地预览生产产物 | 检查 `dist` |

`dev` 能跑，不代表 `build` 一定成功。开发阶段为了速度，很多转换是按需发生的；生产构建会完整扫描依赖图，处理压缩、拆包、资源路径和环境变量替换。

## 二、开发服务器与 HMR

Vite 开发服务器负责：

- 提供本地访问地址。
- 按需转换模块。
- 处理 Vue、React、TypeScript、CSS 等文件。
- 提供热更新。
- 提供开发代理。

启动：

```bash
pnpm dev
```

如果需要让局域网其他设备访问：

```bash
vite --host 0.0.0.0
```

可以写进脚本：

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0"
  }
}
```

HMR 是 Hot Module Replacement，热模块替换。它的目标是在不完整刷新页面的情况下更新改动模块，尽量保留页面状态。

HMR 失效时常见原因：

- 文件路径大小写不一致。
- 模块存在循环依赖。
- 插件处理异常。
- 框架状态超出 HMR 能保持的范围。
- 代码改动触发了整页刷新。

遇到 HMR 问题，先看终端和浏览器 Console。不要一上来就怪框架，框架已经背了很多锅，没必要什么都给它。

## 三、vite.config.ts

Vite 配置通常写在 `vite.config.ts`：

```ts
import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    open: true
  },
  build: {
    outDir: 'dist',
    sourcemap: false
  }
})
```

常见配置项：

| 配置 | 作用 |
| ---- | ---- |
| `plugins` | 接入框架和构建插件 |
| `resolve.alias` | 路径别名 |
| `server.port` | 开发服务器端口 |
| `server.proxy` | 开发代理 |
| `base` | 部署基础路径 |
| `build.outDir` | 构建输出目录 |
| `build.sourcemap` | 是否生成 source map |
| `define` | 编译期常量替换 |

`vite.config.ts` 是 Node 侧配置文件，不是浏览器业务代码。里面可以使用 Node API，比如 `node:url`。但 `src` 里的浏览器代码不能随便使用 Node 内置模块。

## 四、路径别名

前端项目中常用 `@` 指向 `src`：

```ts
import { request } from '@/utils/request'
```

Vite 配置：

```ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
```

如果使用 TypeScript，还要保证 `tsconfig.json` 的 `paths` 同步配置：

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

构建工具和类型系统都要认识别名，否则会出现：

- 编辑器找得到，构建失败。
- 构建能过，类型检查失败。
- 测试环境找不到模块。

如果项目还使用 Vitest，也要确认测试配置继承或同步了别名。路径别名不是写一次就自动感动所有工具。

## 五、静态资源处理

Vite 常见资源处理方式有两种。

### 从源码中导入资源

适合组件内使用的图片、字体、样式资源：

```ts
import logoUrl from '@/assets/logo.png'
```

模板中使用：

```vue
<template>
  <img :src="logoUrl" alt="Logo" />
</template>

<script setup lang="ts">
import logoUrl from '@/assets/logo.png'
</script>
```

这类资源会进入构建处理流程，文件名可能带 hash，便于缓存。

### public 目录

`public` 下的文件会原样复制到构建产物根目录。

```text
public/favicon.ico
public/robots.txt
```

访问路径：

```text
/favicon.ico
/robots.txt
```

适合：

- `favicon.ico`
- `robots.txt`
- 不需要被打包处理的静态文件
- 必须保持固定路径的资源

不适合：

- 需要 hash 缓存的业务图片。
- 需要被压缩或转换的资源。
- 组件内部频繁引用的图片。

资源路径问题在线上很常见。尤其是部署到子路径时，`base` 配置、路由模式、资源引用方式需要一起检查。

## 六、环境变量与模式

Vite 会按模式读取环境文件。

常见文件：

```text
.env
.env.local
.env.development
.env.development.local
.env.production
.env.production.local
```

默认模式：

| 命令 | 默认模式 |
| ---- | -------- |
| `vite` | `development` |
| `vite build` | `production` |

也可以指定模式：

```bash
vite build --mode staging
```

对应文件：

```text
.env.staging
.env.staging.local
```

暴露给客户端的变量默认需要以 `VITE_` 开头：

```bash
VITE_API_BASE_URL=https://api.example.com
VITE_APP_TITLE=Admin
```

代码中读取：

```ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
export const APP_TITLE = import.meta.env.VITE_APP_TITLE
```

Vite 还提供内置变量：

```ts
if (import.meta.env.DEV) {
  console.log('development only')
}

if (import.meta.env.PROD) {
  console.log('production only')
}
```

构建时这些值会被静态替换，有利于删除无用分支。

## 七、环境变量不是秘密

前端环境变量会进入客户端产物。只要用户能访问页面，就有机会在打包后的 JS 中看到这些值。

不要放：

- 数据库密码。
- 服务端私钥。
- 云服务 Secret Key。
- 支付密钥。
- 后端内部 token。

可以放：

- 公开 API base URL。
- 应用名称。
- 当前构建模式。
- 公开的统计服务 ID。
- 前端功能开关。

如果某个值不能被用户知道，就不要进入前端构建。把秘密交给浏览器再要求它保密，和把答案写在试卷背面再要求别人不要看，性质差不多。

## 八、环境变量类型声明

TypeScript 默认不知道你的自定义环境变量。可以在 `src/vite-env.d.ts` 中声明：

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

这样可以减少拼错变量名的问题。

但是类型声明不等于运行时校验。如果 `.env.production` 缺少变量，TypeScript 不会自动替你发现。更稳的做法是在应用启动时集中读取和检查：

```ts
const requiredEnv = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  appTitle: import.meta.env.VITE_APP_TITLE
}

for (const [key, value] of Object.entries(requiredEnv)) {
  if (!value) {
    throw new Error(`Missing env: ${key}`)
  }
}

export const appEnv = requiredEnv
```

不要在业务代码各处散落 `import.meta.env`。集中管理更容易检查、测试和替换。

## 九、开发代理

本地开发常用代理解决跨域和接口地址问题。

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, '')
      }
    }
  }
})
```

请求：

```ts
fetch('/api/users')
```

开发时实际转发到：

```text
http://localhost:8080/users
```

注意：

- `server.proxy` 只影响 Vite 开发服务器。
- 生产环境通常由 Nginx、网关、后端服务或部署平台配置转发。
- 不要把开发代理误认为线上配置。
- 如果生产接口地址不同，要用环境变量或部署配置处理。

排查代理问题：

```text
浏览器 Network 是否发出请求
 -> 请求路径是否以 /api 开头
 -> Vite 终端是否有代理错误
 -> target 后端是否可访问
 -> rewrite 后路径是否正确
 -> 后端是否需要 cookie / token / header
```

## 十、CSS 与 PostCSS

Vite 默认支持 CSS 导入：

```ts
import './style.css'
```

组件中：

```vue
<style scoped>
.title {
  color: #1f2937;
}
</style>
```

也可以使用 CSS Modules：

```ts
import styles from './button.module.css'

console.log(styles.primary)
```

PostCSS 配置可以写在 `postcss.config.js`：

```js
export default {
  plugins: {
    autoprefixer: {}
  }
}
```

如果使用 Sass、Less 等预处理器，需要安装对应依赖：

```bash
pnpm add -D sass
```

然后使用：

```vue
<style lang="scss" scoped>
.panel {
  &:hover {
    color: #2563eb;
  }
}
</style>
```

样式问题不一定是 CSS 写错，也可能是作用域、构建顺序、浏览器兼容、资源路径或组件库样式覆盖问题。

## 十一、调试方法

前端调试不要只靠 `console.log`，虽然它朴素、有用，而且常常比某些花哨方法诚实。

常见工具：

| 工具 | 关注点 |
| ---- | ------ |
| Elements | DOM 结构、样式、布局 |
| Console | JS 错误、日志、运行表达式 |
| Network | 请求、响应、状态码、耗时 |
| Sources | 断点调试、source map |
| Application | localStorage、sessionStorage、cookie |
| Performance | 性能录制 |
| Vue Devtools | 组件树、props、状态、事件 |

排查接口问题时，优先看 Network：

```text
请求是否发出
 -> URL 是否正确
 -> Method 是否正确
 -> Query / Body 是否正确
 -> 状态码是什么
 -> 请求头是否带 token
 -> 响应体是什么
 -> 是否被 CORS 拦截
```

排查页面白屏：

```text
Console 是否有 JS 错误
 -> Network 是否有资源 404
 -> index.html 是否加载
 -> JS / CSS 路径是否正确
 -> 环境变量是否缺失
 -> 路由 base 是否正确
 -> 后端是否返回了 HTML fallback
```

排查样式异常：

```text
Elements 中样式是否存在
 -> 是否被覆盖
 -> scoped 属性是否生效
 -> CSS 变量是否有值
 -> 媒体查询是否命中
 -> 组件库样式加载顺序是否正确
```

调试不是试错速度比赛。先定位问题所在层，再修改对应代码。

## 十二、source map

source map 用来把构建后的代码映射回源码，方便调试。

Vite 构建配置：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    sourcemap: false
  }
})
```

常见策略：

| 环境 | 策略 |
| ---- | ---- |
| 本地开发 | 默认支持调试 |
| 测试环境 | 可以开启 source map |
| 生产环境 | 谨慎开启，避免源码泄露 |

如果生产需要错误定位，可以将 source map 上传到监控平台，而不是直接公开给所有用户访问。

## 十三、TypeScript 类型检查

Vite 可以处理 TypeScript 语法，但它本身不等价于完整类型检查。Vue 项目通常需要 `vue-tsc`。

安装：

```bash
pnpm add -D typescript vue-tsc
```

脚本：

```json
{
  "scripts": {
    "type-check": "vue-tsc --noEmit"
  }
}
```

`noEmit` 表示只检查类型，不输出文件。

推荐构建前执行类型检查：

```json
{
  "scripts": {
    "build": "pnpm type-check && vite build"
  }
}
```

类型检查能发现：

- props 类型不匹配。
- 组件事件参数错误。
- 接口响应使用不安全。
- `ref`、`computed`、组合函数类型错误。
- 模板中访问不存在的字段。

不要以为页面能打开就说明类型没问题。运行到某条路径之前，错误可以安静地躲着。类型检查的意义就是把一部分错误提前拖出来。

## 十四、ESLint

ESLint 负责发现代码中的潜在问题和不一致写法。

脚本：

```json
{
  "scripts": {
    "lint": "eslint .",
    "lint:fix": "eslint . --fix"
  }
}
```

现代 ESLint 常见 flat config 文件：

```js
import js from '@eslint/js'

export default [
  js.configs.recommended,
  {
    files: ['src/**/*.{js,ts,vue}'],
    rules: {
      'no-console': 'warn'
    }
  },
  {
    ignores: ['dist/**', 'coverage/**']
  }
]
```

ESLint 适合检查：

- 未使用变量。
- 可能的空引用。
- 不安全的异步写法。
- 不符合团队约定的导入顺序。
- 框架专属规则，例如 Vue 组件规则。

不要把 ESLint 当格式化工具。它可以修一些格式，但它的核心职责是代码质量和规则约束。

## 十五、Prettier

Prettier 负责统一格式。它不关心你的业务逻辑，只关心代码长什么样。

脚本：

```json
{
  "scripts": {
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

配置示例：

```json
{
  "singleQuote": true,
  "semi": false,
  "printWidth": 100,
  "trailingComma": "none"
}
```

`.prettierignore`：

```text
dist
coverage
node_modules
pnpm-lock.yaml
```

ESLint 和 Prettier 应该分工：

| 工具 | 职责 |
| ---- | ---- |
| ESLint | 代码问题、规则约束 |
| Prettier | 代码格式 |

如果两者规则冲突，应该使用对应的 Prettier 兼容配置关闭 ESLint 中和格式相关的规则。代码风格不应该靠人吵赢，机器很适合处理这种无聊但必要的事。

## 十六、测试

前端测试可以分层：

| 类型 | 工具 | 关注点 |
| ---- | ---- | ------ |
| 单元测试 | Vitest | 函数、组合函数、状态逻辑 |
| 组件测试 | Vitest + Testing Library | 组件输入输出和交互 |
| 端到端测试 | Playwright / Cypress | 用户完整流程 |

Vitest 脚本：

```json
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  }
}
```

示例测试：

```ts
import { describe, expect, it } from 'vitest'

function sum(a: number, b: number) {
  return a + b
}

describe('sum', () => {
  it('adds two numbers', () => {
    expect(sum(1, 2)).toBe(3)
  })
})
```

不必一开始追求覆盖所有页面。优先测试：

- 金额、权限、状态流转。
- 复杂数据转换。
- 公共组合函数。
- 表单校验。
- 关键业务组件。
- 曾经出过 bug 的逻辑。

覆盖率是指标，不是目标。高覆盖率的无效测试只是在认真制造幻觉。

## 十七、质量门禁

质量门禁是提交、合并、部署前必须通过的检查。

本地建议：

```bash
pnpm type-check
pnpm lint
pnpm format:check
pnpm test:run
pnpm build
```

可以组合成脚本：

```json
{
  "scripts": {
    "check": "pnpm type-check && pnpm lint && pnpm format:check && pnpm test:run",
    "verify": "pnpm check && pnpm build"
  }
}
```

CI 中执行：

```bash
pnpm install --frozen-lockfile
pnpm verify
```

质量门禁应该尽量快，但不能空。可以分层：

| 阶段 | 检查 |
| ---- | ---- |
| 提交前 | format、lint staged files |
| PR | type-check、lint、test、build |
| 部署前 | build、e2e、产物检查 |

## 十八、生产构建

生产构建：

```bash
pnpm build
```

默认输出：

```text
dist/
  index.html
  assets/
    index-xxxxx.js
    index-xxxxx.css
```

构建后检查：

- `dist/index.html` 是否存在。
- JS、CSS、图片是否生成。
- 资源路径是否正确。
- 环境变量是否是生产值。
- 包体积是否异常增大。
- sourcemap 是否符合策略。

本地预览：

```bash
pnpm preview
```

`preview` 用于检查生产产物，不是替代生产服务器。它能发现很多 `dev` 阶段看不到的问题。

## 十九、构建优化

构建优化不要一开始就追求复杂配置。先观察，再处理。

常见方向：

- 减少不必要依赖。
- 按路由懒加载页面。
- 避免把大型库打进首屏。
- 使用构建分析工具查看包体积。
- 合理配置浏览器兼容目标。
- 确认图片、字体等资源是否过大。

路由懒加载：

```ts
const routes = [
  {
    path: '/settings',
    component: () => import('@/pages/settings/SettingsPage.vue')
  }
]
```

手动分包要谨慎：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia']
        }
      }
    }
  }
})
```

不要为了“看起来优化过”随便拆包。拆得不好会增加请求数量、破坏缓存收益，甚至让首屏更慢。

## 二十、部署基础

Vite 构建产物通常是静态文件，可以部署到：

- Nginx。
- GitHub Pages。
- Netlify。
- Vercel。
- Cloudflare Pages。
- 对象存储加 CDN。
- 后端服务的静态目录。

核心是：服务器需要正确返回 `index.html`、JS、CSS、图片等静态文件。

如果使用前端路由 history 模式，还需要配置回退：

```text
/users/1
 -> 如果服务器没有真实 /users/1 文件
 -> 返回 index.html
 -> 前端路由接管
```

Nginx 示例：

```nginx
server {
    listen 80;
    server_name example.com;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

如果没有 fallback，刷新二级路由可能 404。

## 二十一、部署子路径与 base

如果项目部署在域名根路径：

```text
https://example.com/
```

通常不需要特殊 `base`。

如果部署在子路径：

```text
https://example.com/admin/
```

需要配置：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  base: '/admin/'
})
```

同时前端路由也要匹配：

```ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory('/admin/'),
  routes: []
})
```

常见线上白屏原因：

```text
index.html 加载成功
 -> JS 路径是 /assets/index.js
 -> 实际项目在 /admin/assets/index.js
 -> 资源 404
 -> 页面白屏
```

这种问题很普通，但很容易被误判成框架坏了。框架要是真能替你猜部署路径，那它也未免太辛苦。

## 二十二、环境差异与部署平台

本地 `.env.production` 不一定等于线上环境变量。很多部署平台会在平台后台配置环境变量。

要确认：

- 构建时使用哪个模式。
- 环境变量是在构建时注入，还是运行时读取。
- 平台是否区分 Preview、Staging、Production。
- 变量名是否以 `VITE_` 开头。
- 变量修改后是否重新构建。

Vite 前端变量通常是构建期注入。也就是说，修改部署平台环境变量后，需要重新构建才能进入产物。

如果你需要运行时配置，可以考虑：

- 由后端提供 `/config.json`。
- 部署时生成静态配置文件。
- 在 HTML 中注入全局配置对象。

但这些方案要控制缓存和安全边界，不要把密钥换个位置继续公开。

## 二十三、CI/CD 示例

GitHub Actions 示例：

```yaml
name: frontend-ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  verify:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - run: corepack enable

      - run: pnpm install --frozen-lockfile

      - run: pnpm type-check

      - run: pnpm lint

      - run: pnpm test:run

      - run: pnpm build
```

CI 的价值是提供干净环境。它能发现：

- 本地依赖没声明。
- 锁文件没提交。
- Node 版本不一致。
- 环境变量缺失。
- 构建命令依赖本地状态。
- 测试只在某个人电脑上通过。

让 CI 失败不是丢脸。让同一个问题反复在 CI 失败，才比较值得反省。

## 二十四、上线前检查清单

上线前至少检查：

- `pnpm install --frozen-lockfile` 通过。
- `pnpm type-check` 通过。
- `pnpm lint` 通过。
- `pnpm test:run` 通过。
- `pnpm build` 通过。
- `pnpm preview` 本地预览正常。
- 生产接口地址正确。
- 部署路径和 `base` 正确。
- history 路由刷新不 404。
- 静态资源没有 404。
- sourcemap 策略符合安全要求。
- `.env.local` 没有提交。
- 密钥没有进入前端产物。

上线不是把文件丢到服务器就结束。上线是把构建产物、服务器配置、环境变量、缓存策略、路由回退一起交付。

## 二十五、常见问题排查

### 本地能跑，构建失败

检查：

```text
类型检查是否失败
 -> 是否使用了只在开发存在的变量
 -> 是否有大小写路径问题
 -> 是否导入了 Node 专属模块
 -> 是否有动态导入路径无法分析
 -> 是否缺少依赖声明
```

### 构建成功，线上白屏

检查：

```text
Console 错误
 -> JS / CSS 是否 404
 -> base 是否正确
 -> 路由 history fallback 是否配置
 -> 环境变量是否缺失
 -> API 地址是否错误
```

### 接口本地正常，线上失败

检查：

```text
本地是否依赖 Vite proxy
 -> 线上是否有网关或 Nginx 转发
 -> CORS 是否允许生产域名
 -> token / cookie 是否发送
 -> HTTPS 混合内容是否被拦截
```

### CI 能构建，本地失败

检查：

```text
Node 版本
 -> 包管理器版本
 -> 是否删除 node_modules 后重装
 -> 是否有本地环境变量
 -> 操作系统路径大小写差异
```

### 本地能构建，CI 失败

检查：

```text
锁文件是否提交
 -> CI 是否使用正确包管理器
 -> 环境变量是否配置
 -> 是否依赖未提交文件
 -> 是否存在大小写路径问题
 -> 是否使用了全局安装工具
```

## 二十六、练习

给一个 Vue + Vite 项目补齐下面脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "type-check": "vue-tsc --noEmit",
    "lint": "eslint .",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "test": "vitest",
    "test:run": "vitest run",
    "build": "pnpm type-check && vite build",
    "preview": "vite preview",
    "verify": "pnpm type-check && pnpm lint && pnpm test:run && pnpm build"
  }
}
```

然后完成这些实验：

- 故意制造一个类型错误，观察 `type-check` 和 `build`。
- 故意写一个 lint 问题，观察 `lint`。
- 故意改乱格式，观察 `format:check`。
- 修改 `.env.production`，观察构建产物变化。
- 设置错误 `base`，观察 `preview` 中资源路径。
- 用 history 路由刷新二级页面，观察服务器回退行为。

亲眼看到工具如何拦住错误，比背一句“要工程化”可靠得多。

## 二十七、总结

Vite、环境变量、调试、质量工具、构建部署不是分散的知识点，而是一条交付链路：

```text
源码
 -> Vite 开发服务器
 -> 调试
 -> 类型检查
 -> lint / format
 -> 测试
 -> 生产构建
 -> 本地预览
 -> 部署
 -> 线上排查
```

项目越复杂，越不能只靠“能跑”。真正可靠的工程实践，是让每一步都有明确职责、可重复命令和失败信号。

## 二十八、延伸阅读

- Vite 官方指南：https://vite.dev/guide/
- Vite 环境变量与模式：https://vite.dev/guide/env-and-mode
- Vite 生产构建：https://vite.dev/guide/build
- Vite 静态部署：https://vite.dev/guide/static-deploy
- ESLint 配置文档：https://eslint.org/docs/latest/use/configure/configuration-files
- ESLint 忽略文件文档：https://eslint.org/docs/latest/use/configure/ignore
- Prettier CLI 文档：https://prettier.io/docs/cli
- Prettier ignore 文档：https://prettier.io/docs/ignore
- Vitest 覆盖率文档：https://vitest.dev/guide/coverage
