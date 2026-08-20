+++
date = '2026-08-19T18:22:00+08:00'
draft = false
title = 'Node、npm、pnpm 与依赖管理：现代前端项目的运行底座'
+++

前端工程依赖大量工具和库。Vue、Vite、TypeScript、Pinia、ESLint、组件库、请求库都通过包管理器安装。依赖管理不稳，项目就会出现本地正常、别人异常、CI 失败这种熟悉而讨厌的局面。

## 一、Node.js 与 npm

安装 Node.js 时通常会附带 npm。

查看版本：

```bash
node -v
npm -v
```

Node 版本影响工具能否运行。很多现代前端工具要求较新的 Node 版本。如果团队没有约束 Node 版本，就很容易出现某个人能跑、另一个人装依赖失败。

常见约束方式：

```json
{
  "engines": {
    "node": ">=20.0.0"
  }
}
```

也可以使用 `.nvmrc` 或 `.node-version` 标记项目推荐版本。

## 二、package.json

`package.json` 是项目说明书。

```json
{
  "name": "frontend-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build"
  },
  "dependencies": {
    "vue": "^3.5.0",
    "pinia": "^3.0.0"
  },
  "devDependencies": {
    "typescript": "^5.8.0",
    "vite": "^7.0.0"
  }
}
```

重点字段：

- `scripts`：项目命令。
- `dependencies`：生产运行需要的依赖。
- `devDependencies`：开发和构建需要的依赖。
- `private`：防止误发布到 npm 仓库。

## 三、安装依赖

npm：

```bash
npm install
```

pnpm：

```bash
pnpm install
```

安装指定依赖：

```bash
npm install axios
npm install -D eslint
```

`-D` 表示安装到 `devDependencies`。

判断一个依赖放哪里：

- 页面运行时需要：`dependencies`。
- 只在开发、检查、构建时需要：`devDependencies`。

## 四、语义化版本

常见版本写法：

| 写法 | 含义 |
| ---- | ---- |
| `1.2.3` | 固定版本 |
| `^1.2.3` | 允许升级 minor 和 patch |
| `~1.2.3` | 允许升级 patch |
| `latest` | 最新版本，不推荐写进项目依赖 |

版本号通常表示：

```text
主版本.次版本.修订版本
major.minor.patch
```

主版本变化可能包含破坏性变更。升级前应该看 changelog，不要凭勇气更新依赖。勇气很好，但不该用在这种地方。

## 五、锁文件

锁文件记录实际安装出来的依赖树。

不要同时提交多个包管理器的锁文件。比如项目使用 pnpm，就保留 `pnpm-lock.yaml`，不要又提交 `package-lock.json`。

团队协作建议：

- 统一包管理器。
- 提交锁文件。
- CI 使用锁文件安装。
- 避免手动编辑锁文件。

npm CI 安装：

```bash
npm ci
```

pnpm CI 安装：

```bash
pnpm install --frozen-lockfile
```

## 六、pnpm 的特点

pnpm 相比 npm，常见优势是安装快、磁盘占用低、依赖结构更严格。

启用 Corepack：

```bash
corepack enable
```

指定包管理器：

```json
{
  "packageManager": "pnpm@10.0.0"
}
```

这能让团队成员使用相同版本的 pnpm。

## 七、常用命令

```bash
npm run dev
npm run build
npm run preview
npm outdated
npm update
npm uninstall axios
```

pnpm 对应：

```bash
pnpm dev
pnpm build
pnpm preview
pnpm outdated
pnpm update
pnpm remove axios
```

## 八、依赖安全

依赖越多，风险越大。常见风险包括：

- 包维护停止。
- 新版本破坏兼容。
- 间接依赖漏洞。
- 安装脚本执行恶意代码。

基本做法：

- 不随意安装小而冷门的包。
- 安装前看下载量、维护状态、仓库 issue。
- 定期执行审计命令。
- 关键依赖升级后跑完整构建。

npm 审计：

```bash
npm audit
```

## 九、排错顺序

依赖问题可以按这个顺序查：

```text
Node 版本
 -> 包管理器版本
 -> 锁文件是否匹配
 -> node_modules 是否损坏
 -> 依赖版本是否冲突
 -> 安装脚本是否失败
```

不要一出问题就删除所有文件。先看错误信息。工具其实已经把大部分线索打印出来了，只是人类常常不愿意读。

## 十、练习

打开一个前端项目的 `package.json`：

- 解释每个 `scripts`。
- 找出生产依赖和开发依赖。
- 判断是否有锁文件。
- 判断是否声明 Node 版本。
- 判断包管理器是否统一。

这不是杂活，而是工程能力的一部分。
