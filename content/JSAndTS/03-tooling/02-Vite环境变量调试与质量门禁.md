+++
date = '2026-08-19T18:21:00+08:00'
draft = false
title = 'Vite、环境变量、调试与质量门禁：把代码交付得更可靠'
+++

能写代码只是第一步。能稳定启动、构建、检查、调试、交付，才算进入工程阶段。Vite 是现代前端常用构建工具，它把开发服务器、模块转换、资源处理、生产构建串起来。

## 一、Vite 负责什么

Vite 的核心职责：

- 启动开发服务器。
- 处理 ES Module。
- 编译 TypeScript、Vue、CSS。
- 处理静态资源。
- 注入环境变量。
- 生产构建。

常见脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview"
  }
}
```

`dev` 面向开发，`build` 面向生产产物，`preview` 用来本地预览构建结果。

## 二、路径别名

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

如果使用 TypeScript，还要保证 `tsconfig.json` 的 `paths` 同步配置。

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

构建工具和类型系统都要认识别名，否则编辑器不报错，构建却失败，或者反过来。

## 三、环境变量

Vite 会按模式读取环境文件：

```text
.env
.env.development
.env.production
```

暴露给客户端的变量需要以 `VITE_` 开头：

```bash
VITE_API_BASE_URL=https://api.example.com
```

读取：

```ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
```

注意：

- 前端环境变量不是秘密。
- 不要放数据库密码、服务端密钥。
- 生产环境变量要和部署平台保持一致。

## 四、开发代理

本地开发常用代理解决跨域和接口地址问题。

```ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  }
})
```

这只影响开发服务器。生产环境通常由 Nginx、网关或后端服务处理转发。不要把开发代理误认为线上配置。

## 五、调试方法

前端调试不要只靠 `console.log`，虽然它很朴素，也确实有用。

常见工具：

- 浏览器 Elements：检查 DOM 和样式。
- Console：查看日志和错误。
- Network：检查请求、响应、状态码和耗时。
- Sources：断点调试。
- Application：检查本地存储。
- Vue Devtools：检查组件树和状态。

排查接口问题时，优先看 Network：

```text
请求是否发出
 -> URL 是否正确
 -> Method 是否正确
 -> 状态码是什么
 -> 请求头是否带 token
 -> 响应体是什么
```

这比凭感觉改代码可靠。

## 六、类型检查

TypeScript 项目应该有独立类型检查。

```bash
vue-tsc --noEmit
```

`noEmit` 表示只检查类型，不输出文件。很多模板语法和组件 props 问题，需要 `vue-tsc` 才能发现。

建议构建脚本包含类型检查：

```json
{
  "scripts": {
    "type-check": "vue-tsc --noEmit",
    "build": "npm run type-check && vite build"
  }
}
```

## 七、代码风格与格式化

ESLint 负责发现潜在问题，Prettier 负责统一格式。

```json
{
  "scripts": {
    "lint": "eslint .",
    "format": "prettier --write ."
  }
}
```

团队里代码风格不应该靠口头提醒。能交给工具的事，就不要交给脾气。

## 八、测试

前端测试可以分层：

| 类型 | 关注点 |
| ---- | ------ |
| 单元测试 | 函数、组合函数、状态逻辑 |
| 组件测试 | 组件输入输出和交互 |
| 端到端测试 | 用户完整流程 |

不必一开始追求覆盖所有页面。先给复杂数据处理、权限判断、状态转换、关键组件补测试，收益更高。

## 九、构建产物

生产构建通常输出到 `dist`：

```bash
npm run build
```

检查内容：

- 入口 HTML 是否生成。
- JS 和 CSS 是否拆分。
- 图片路径是否正确。
- 环境变量是否使用生产值。
- 路由模式是否和服务器配置匹配。

## 十、质量门禁

推荐提交前至少通过：

```bash
npm run type-check
npm run lint
npm run build
```

如果项目有测试：

```bash
npm run test
```

质量门禁不是形式主义。它的意义是把错误拦在提交前，而不是让用户或同事帮你发现。

## 十一、练习

给一个 Vue 项目补齐下面脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "type-check": "vue-tsc --noEmit",
    "lint": "eslint .",
    "build": "npm run type-check && vite build",
    "preview": "vite preview"
  }
}
```

然后故意制造一个类型错误，观察 `type-check` 和 `build` 的表现。能亲眼看到工具如何拦住错误，比单纯听别人说“要工程化”有用得多。
