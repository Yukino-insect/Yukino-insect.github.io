+++
date = '2026-08-19T18:23:00+08:00'
draft = false
title = 'Node 与前端工程化学习路线：从运行项目到维护项目'
+++

很多初学者第一次接触前端工程时，最困惑的不是 Vue 语法，而是项目怎么启动：为什么要安装 Node，为什么要执行 npm，为什么有锁文件，为什么本地运行和构建不是一回事，为什么明明页面能打开，提交到 CI 却失败。

这些问题不属于“杂项”。它们就是现代前端工程的底座。工程化不是为了显得专业，而是为了让项目可以被多人协作、重复安装、稳定构建、持续交付。

这篇文章先给出学习路线。你不需要一开始掌握所有工具的底层实现，但至少要知道每个工具站在哪个位置、负责哪段链路、出问题时应该先看哪里。

## 一、现代前端项目的基本链路

一个常见 Vue / React 项目从下载安装到上线，大致会经过这条链路：

```text
Node.js
 -> package.json
 -> 包管理器安装依赖
 -> node_modules
 -> 开发服务器
 -> 类型检查 / lint / format / test
 -> 生产构建
 -> dist
 -> 部署到静态服务器或平台
```

如果只会执行命令，却不知道命令之间的关系，遇到错误时就只能重装依赖、清缓存、换电脑。偶尔能解决问题，但那不叫工程能力，叫运气比较活跃。

常见启动流程：

```bash
pnpm install
pnpm dev
```

背后实际发生的是：

```text
pnpm 读取 package.json
 -> 根据 pnpm-lock.yaml 解析依赖版本
 -> 把依赖安装到 node_modules
 -> 执行 scripts.dev
 -> 启动 Vite 开发服务器
 -> 浏览器访问本地地址
```

构建流程则不同：

```bash
pnpm build
```

背后可能是：

```text
执行类型检查
 -> 执行 ESLint
 -> Vite 生产构建
 -> 压缩和拆分资源
 -> 输出 dist
```

所以“能启动”和“能构建”不是同一个能力。开发服务器为了效率会容忍一些问题，生产构建则会更严格。

## 二、Node.js 在前端中的角色

Node.js 不是浏览器，也不是 Vue 或 React 的一部分。它在前端工程中主要承担三件事：

- 运行开发工具，例如 Vite、ESLint、Prettier、TypeScript 编译器、Vitest。
- 执行项目脚本，例如启动、构建、检查、格式化、测试、生成代码。
- 提供本地脚本能力，例如读取文件、处理路径、加载配置、执行构建插件。

浏览器负责运行最终交给用户的页面。Node.js 负责在开发和构建阶段把源码变成可交付产物。

可以把它们分清楚：

| 环境 | 负责内容 | 常见对象 |
| ---- | -------- | -------- |
| 浏览器 | 运行页面、渲染 DOM、发送网络请求 | `window`、`document`、`fetch` |
| Node.js | 运行工具、读写文件、执行脚本 | `process`、`fs`、`path` |
| 构建工具 | 转换源码、处理资源、生成产物 | Vite、Rollup、esbuild |

因此，下面这种代码只适合 Node 侧：

```js
import fs from 'node:fs'

const text = fs.readFileSync('README.md', 'utf-8')
```

而下面这种代码只适合浏览器侧：

```js
const button = document.querySelector('button')
button?.addEventListener('click', () => {
  console.log('clicked')
})
```

混淆运行环境，是很多前端工程错误的根源。比如在浏览器业务代码里访问 `process.env`，或者在 Node 脚本里直接访问 `document`，都会出问题。

## 三、package.json 是项目入口

`package.json` 是前端项目的说明书，也是包管理器和脚本系统的入口。

一个简化示例：

```json
{
  "name": "frontend-app",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@12.0.0",
  "engines": {
    "node": ">=20.0.0"
  },
  "scripts": {
    "dev": "vite",
    "type-check": "vue-tsc --noEmit",
    "lint": "eslint .",
    "format": "prettier --write .",
    "test": "vitest",
    "build": "pnpm type-check && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.0",
    "pinia": "^3.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^6.0.0",
    "typescript": "^7.0.0",
    "vite": "^8.0.0",
    "vue-tsc": "^3.3.0"
  }
}
```

示例中的版本号只用于说明字段结构。真实项目应以官方模板、当前生态版本和团队约束为准，不要机械复制。

学习 `package.json` 时，不要只记命令。要理解字段的职责：

| 字段 | 作用 |
| ---- | ---- |
| `scripts` | 定义项目命令 |
| `dependencies` | 运行时依赖 |
| `devDependencies` | 开发、检查、构建依赖 |
| `engines` | 声明 Node 等运行环境要求 |
| `packageManager` | 声明推荐包管理器及版本 |
| `type` | 影响 Node 如何理解 `.js` 模块 |
| `private` | 防止应用项目被误发布 |

项目的很多行为不是藏在某个神秘角落里，而是明明白白写在 `package.json`。只是它不负责主动解释自己，人也就经常假装没看见。

## 四、包管理器负责什么

包管理器负责把依赖声明变成真实可用的文件结构。

常见包管理器：

| 工具 | 常见锁文件 | 常见命令 |
| ---- | ---------- | -------- |
| npm | `package-lock.json` | `npm install`、`npm run build` |
| pnpm | `pnpm-lock.yaml` | `pnpm install`、`pnpm build` |
| yarn | `yarn.lock` | `yarn install`、`yarn build` |

包管理器主要做这些事：

- 读取 `package.json` 中的依赖声明。
- 解析版本范围。
- 下载依赖包。
- 生成或更新锁文件。
- 创建 `node_modules`。
- 执行依赖包的生命周期脚本。
- 把项目脚本和本地命令连接起来。

包管理器不是“下载器”这么简单。它实际在管理一棵依赖树。一个直接依赖还会带来很多间接依赖，版本之间可能互相约束，也可能互相冲突。

## 五、版本与锁文件

`package.json` 中写的是依赖范围，锁文件记录的是实际解析结果。

例如：

```json
{
  "dependencies": {
    "vue": "^3.5.0"
  }
}
```

`^3.5.0` 表示允许安装兼容范围内的新版本。到底安装了 `3.5.0`、`3.5.13` 还是更高的兼容版本，要看解析结果。

锁文件会记录完整结果：

```text
vue: 3.5.13
@vue/compiler-dom: 3.5.13
@vue/runtime-core: 3.5.13
...
```

这就是为什么团队项目必须提交锁文件。否则同一个 `package.json` 在不同时间、不同机器上可能安装出不同结果。嘴上说“代码一样”，依赖树却不一样，当然会出现各种不一致。

要记住两个层次：

| 文件 | 记录内容 |
| ---- | -------- |
| `package.json` | 项目想要什么依赖 |
| 锁文件 | 实际安装成什么依赖树 |

这两个文件需要一起维护。

## 六、Vite 负责什么

Vite 是现代前端常用构建工具。它主要包含两部分：

- 开发服务器：快速启动、本地模块加载、热更新。
- 生产构建：把源码打包、压缩、拆分并输出到 `dist`。

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

三条命令的含义不同：

| 命令 | 作用 |
| ---- | ---- |
| `vite` | 启动开发服务器 |
| `vite build` | 生成生产产物 |
| `vite preview` | 本地预览生产产物 |

`preview` 不是开发服务器。它用于检查 `dist` 是否能被正常服务。如果 `dev` 正常但 `preview` 异常，问题往往在构建产物、路径、环境变量或路由服务器配置上。

## 七、环境变量和模式

现代前端项目通常会区分开发、测试、生产环境。

Vite 常见环境文件：

```text
.env
.env.local
.env.development
.env.development.local
.env.production
.env.production.local
```

暴露给客户端代码的变量默认需要以 `VITE_` 开头：

```bash
VITE_API_BASE_URL=https://api.example.com
```

代码中读取：

```ts
const baseUrl = import.meta.env.VITE_API_BASE_URL
```

重点不是“会写变量”，而是知道它什么时候生效：

- `dev` 默认使用 development 模式。
- `build` 默认使用 production 模式。
- 可以通过 `--mode` 指定模式。
- 客户端环境变量会进入前端产物，不是秘密。

所以不要把数据库密码、云服务密钥、后端私钥放进前端环境变量。只要进入前端包，就等于交给用户。把秘密写在公开代码里，还期待它保持秘密，这种信念未免太浪漫了。

## 八、质量工具负责什么

质量工具不是“上线前跑一下求安心”。它们分别检查不同问题。

| 工具 | 关注点 |
| ---- | ------ |
| TypeScript / `vue-tsc` | 类型是否成立 |
| ESLint | 代码是否有潜在问题 |
| Prettier | 格式是否统一 |
| Vitest | 函数、组合逻辑、组件行为是否符合预期 |
| Playwright / Cypress | 用户关键流程是否真的可用 |

一个常见脚本组合：

```json
{
  "scripts": {
    "type-check": "vue-tsc --noEmit",
    "lint": "eslint .",
    "format": "prettier --write .",
    "test": "vitest",
    "build": "pnpm type-check && vite build"
  }
}
```

不要把所有检查都叫“构建失败”。构建失败只是一种结果，原因可能不同：

```text
类型错误
 -> lint 错误
 -> 测试失败
 -> Vite 打包失败
 -> 部署平台配置失败
```

判断问题发生在哪一层，才有资格谈修复。

## 九、构建部署要看什么

生产构建通常输出到 `dist`：

```bash
pnpm build
```

部署时交付的不是 `src`，而是构建后的静态产物：

```text
dist/
  index.html
  assets/
    index-xxxxx.js
    index-xxxxx.css
```

上线前至少确认：

- 构建命令能在干净环境中通过。
- 构建产物目录正确。
- 接口地址使用生产环境配置。
- 路由模式和服务器回退规则匹配。
- 静态资源路径和部署子路径匹配。
- 不把 `.env.local`、密钥、源码映射错误公开。

如果项目部署在子路径，例如：

```text
https://example.com/admin/
```

通常需要配置 Vite 的 `base`：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  base: '/admin/'
})
```

否则资源可能会从根路径加载，导致线上页面白屏。

## 十、从会运行到会维护

会运行项目：

- 能安装依赖。
- 能启动开发服务器。
- 能打开页面。

会维护项目：

- 能解释每个脚本做什么。
- 能判断依赖是运行依赖还是开发依赖。
- 能看懂版本范围和锁文件变化。
- 能处理 Node 版本和包管理器版本不一致。
- 能配置 Vite 的别名、环境变量、代理和构建选项。
- 能区分开发服务器问题、类型问题、构建问题、部署问题。
- 能在提交和上线前运行质量检查。

两者不是同一件事。前者像会按电梯按钮，后者才知道停电时该看配电箱。虽然听起来不够温柔，但项目并不会因为你委屈就自动恢复。

## 十一、学习顺序

建议按下面顺序学习：

```text
Node.js 基础
 -> package.json
 -> npm / pnpm 常用命令
 -> 依赖版本与锁文件
 -> Vite 开发服务器
 -> 环境变量与路径别名
 -> TypeScript 类型检查
 -> ESLint / Prettier
 -> 测试
 -> 构建与部署
 -> CI 质量门禁
```

对应实践：

1. 找一个真实项目，先读 `package.json`。
2. 确认使用 npm、pnpm 还是 yarn。
3. 删除 `node_modules` 后重新安装依赖。
4. 分别执行 `dev`、`type-check`、`lint`、`test`、`build`。
5. 观察每一步失败时的错误信息。
6. 执行 `preview` 检查生产产物。
7. 查一次锁文件变化，理解为什么会变化。

工程化最好的学习方式不是背工具名，而是把一个项目从干净目录跑到可部署状态。工具链本来就是链路，拆开背当然会显得零碎。

## 十二、练习

打开一个前端项目，回答下面问题：

- 使用哪个包管理器？
- `package.json` 中有哪些脚本？
- 启动命令是什么？
- 构建命令是什么？
- 是否有类型检查？
- 是否有 ESLint、Prettier、测试？
- 是否有环境变量文件？
- 构建产物输出到哪里？
- Node 版本是否有约束？
- 包管理器版本是否有约束？
- 锁文件是否和包管理器匹配？
- 部署路径是否需要配置 `base`？

如果这些问题你都能回答，说明你已经开始从“运行项目的人”变成“理解项目的人”。

## 十三、延伸阅读

- npm `package.json` 文档：https://docs.npmjs.com/cli/v12/configuring-npm/package-json/
- npm `npm ci` 文档：https://docs.npmjs.com/cli/v11/commands/npm-ci/
- pnpm `install` 文档：https://pnpm.io/cli/install
- Vite 官方指南：https://vite.dev/guide/
- Vite 环境变量与模式：https://vite.dev/guide/env-and-mode
- Vite 生产构建：https://vite.dev/guide/build
