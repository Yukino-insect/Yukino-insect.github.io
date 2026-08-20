+++
date = '2026-08-19T18:22:00+08:00'
draft = false
title = 'Node、npm、pnpm 与依赖管理：现代前端项目的运行底座'
+++

前端工程依赖大量工具和库。Vue、Vite、TypeScript、Pinia、ESLint、组件库、请求库、测试框架都通过包管理器安装。依赖管理不稳，项目就会出现本地正常、别人异常、CI 失败、线上构建失败这种熟悉而讨厌的局面。

依赖管理看起来像安装命令，实际是在维护项目的运行底座。底座歪了，页面写得再漂亮也只是暂时还没倒。

## 一、Node.js 与 npm

安装 Node.js 时通常会获得 `node` 和 `npm` 两个命令。

查看版本：

```bash
node -v
npm -v
```

Node.js 负责运行前端工具链。Vite、TypeScript、ESLint、Prettier、Vitest 等工具本质上都是在 Node 环境里执行的程序。

Node 版本会影响工具能否运行。很多现代前端工具要求较新的 Node 版本。如果团队没有约束 Node 版本，就很容易出现某个人能跑、另一个人装依赖失败。

常见约束方式：

```json
{
  "engines": {
    "node": ">=20.0.0"
  }
}
```

也可以使用 `.nvmrc` 或 `.node-version` 标记项目推荐版本：

```text
20
```

建议团队至少明确三件事：

- 使用哪个 Node 主版本。
- 使用哪个包管理器。
- CI 是否使用同样的 Node 和包管理器版本。

“我电脑上是好的”不是结论，只是事故调查的开场白。

## 二、package.json 的定位

`package.json` 是项目清单。它描述项目是什么、怎么运行、依赖什么、用什么工具检查和构建。

一个现代前端应用的示例：

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
    "format:check": "prettier --check .",
    "test": "vitest",
    "build": "pnpm type-check && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.7.0",
    "pinia": "^3.0.0",
    "vue": "^3.5.0",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^6.0.0",
    "eslint": "^9.0.0",
    "prettier": "^3.0.0",
    "typescript": "^7.0.0",
    "vite": "^8.0.0",
    "vitest": "^4.1.0",
    "vue-tsc": "^3.3.0"
  }
}
```

示例中的版本号只用于说明字段结构。真实项目应以官方模板、当前生态版本和团队约束为准，不要机械复制。

重点字段：

| 字段 | 说明 |
| ---- | ---- |
| `name` | 包名或项目名 |
| `version` | 项目版本 |
| `private` | 防止应用项目被误发布到 npm 仓库 |
| `type` | 决定 Node 如何处理 `.js` 文件的模块格式 |
| `scripts` | 项目命令入口 |
| `dependencies` | 生产运行依赖 |
| `devDependencies` | 开发、检查、构建依赖 |
| `engines` | 声明运行环境要求 |
| `packageManager` | 声明推荐包管理器和版本 |

`package.json` 必须是合法 JSON。不能写注释，不能用单引号，不能多一个尾随逗号。它并不会因为你觉得“差不多”就通过解析，机器没有这种体贴。

## 三、scripts：命令别名

`scripts` 是项目命令别名。

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "type-check": "vue-tsc --noEmit",
    "build": "pnpm type-check && vite build"
  }
}
```

执行：

```bash
pnpm build
```

等价于执行：

```bash
pnpm type-check && vite build
```

`&&` 表示前一步成功后才执行下一步。因此如果类型检查失败，`vite build` 不会继续执行。

常见脚本可以这样设计：

| 脚本 | 职责 |
| ---- | ---- |
| `dev` | 启动开发服务器 |
| `type-check` | 独立类型检查 |
| `lint` | 检查代码问题 |
| `lint:fix` | 自动修复可修复 lint 问题 |
| `format` | 格式化代码 |
| `format:check` | 只检查格式，不修改文件 |
| `test` | 运行测试 |
| `build` | 生产构建 |
| `preview` | 本地预览构建产物 |

脚本命名要稳定。团队成员和 CI 都依赖这些入口，今天叫 `check`，明天叫 `verify`，后天又叫 `quality`，除了制造记忆负担，没有太多美德。

## 四、dependencies 与 devDependencies

依赖应该放在哪里，取决于它是否参与生产运行。

`dependencies`：用户访问页面时仍然需要的依赖。

```json
{
  "dependencies": {
    "vue": "^3.5.0",
    "pinia": "^3.0.0",
    "axios": "^1.7.0"
  }
}
```

`devDependencies`：开发、检查、构建阶段需要，最终业务运行不直接依赖。

```json
{
  "devDependencies": {
    "vite": "^8.0.0",
    "typescript": "^7.0.0",
    "eslint": "^9.0.0",
    "prettier": "^3.0.0",
    "vitest": "^4.1.0"
  }
}
```

判断方式：

| 问题 | 放置位置 |
| ---- | -------- |
| 浏览器运行页面时要用吗？ | `dependencies` |
| 只在本地开发、类型检查、构建、测试时用吗？ | `devDependencies` |
| 是 CLI、插件、编译器、测试工具吗？ | 通常是 `devDependencies` |
| 是 UI 框架、状态库、请求库、运行时工具库吗？ | 通常是 `dependencies` |

安装运行依赖：

```bash
pnpm add axios
```

安装开发依赖：

```bash
pnpm add -D eslint
```

npm 对应：

```bash
npm install axios
npm install -D eslint
```

注意：前端应用最终会被打包，`devDependencies` 里的构建工具不会直接进入浏览器。但如果你把生产运行需要的库错放到 `devDependencies`，在某些只安装生产依赖的环境中可能出问题。

## 五、其他依赖字段

除了 `dependencies` 和 `devDependencies`，还可能看到这些字段。

### peerDependencies

`peerDependencies` 表示“我需要宿主项目提供这个依赖”。

组件库、插件、框架扩展经常使用它：

```json
{
  "peerDependencies": {
    "vue": "^3.5.0"
  }
}
```

意思是：这个包可以配合 Vue 使用，但 Vue 本身应该由使用者项目安装。

典型场景：

- Vue 插件要求宿主项目安装 Vue。
- ESLint 插件要求宿主项目安装 ESLint。
- Vite 插件要求宿主项目安装 Vite。

如果 peer 依赖版本不匹配，包管理器可能警告甚至安装失败。不要无视这类警告。它们通常说明工具之间的版本契约已经开始松动。

### optionalDependencies

`optionalDependencies` 表示可选依赖。安装失败时，项目不一定整体失败。

它常见于跨平台包。例如某些平台才需要的原生二进制依赖。

业务项目里不常手写这个字段，遇到时知道它不是普通依赖即可。

### overrides

`overrides` 可以强制覆盖间接依赖版本。npm 和 pnpm 都支持类似能力，但具体写法和行为要看包管理器文档。

示例：

```json
{
  "overrides": {
    "some-nested-package": "1.2.3"
  }
}
```

它适合临时处理安全漏洞或兼容问题，但不应该被滥用。强行覆盖间接依赖，等于你接管了上游维护者的一部分版本判断。做得到当然很好，做不到就会显得很自信。

## 六、包管理器怎么选

常见选择：

| 包管理器 | 特点 |
| -------- | ---- |
| npm | Node 自带，通用性好，学习成本低 |
| pnpm | 安装快、磁盘占用低、依赖结构更严格，monorepo 友好 |
| yarn | 生态成熟，不同大版本之间行为差异较大 |

对于现代前端应用，npm 和 pnpm 都很常见。pnpm 的优势主要体现在：

- 依赖安装速度快。
- 全局内容寻址存储减少重复占用。
- 依赖访问更严格，不容易误用未声明依赖。
- workspace 支持成熟。

但选择不是重点，统一才是重点。一个项目应该明确使用一种包管理器，并提交对应锁文件。

不要同时提交：

```text
package-lock.json
pnpm-lock.yaml
yarn.lock
```

如果项目使用 pnpm，就保留：

```text
pnpm-lock.yaml
```

如果项目使用 npm，就保留：

```text
package-lock.json
```

多个锁文件并存会让开发者和部署平台都困惑。工具还没开始工作，人类先贡献了混乱，实在没有必要。

## 七、packageManager 与 Corepack

`packageManager` 字段用于声明项目推荐包管理器及版本。

```json
{
  "packageManager": "pnpm@12.0.0"
}
```

它的作用是让团队和自动化环境知道：这个项目应该用 pnpm，而且期望的 pnpm 版本是什么。

如果团队使用 Corepack，可以启用对应包管理器：

```bash
corepack enable
```

然后进入项目执行：

```bash
pnpm install
```

实际项目中要注意：不同 Node 发行方式、不同团队环境对 Corepack 的预装和启用状态可能不同。可靠做法是把 Node 版本、包管理器版本和安装命令写进项目 README 或贡献指南。

## 八、语义化版本

常见版本写法：

| 写法 | 含义 |
| ---- | ---- |
| `1.2.3` | 固定版本 |
| `^1.2.3` | 通常允许升级 minor 和 patch |
| `~1.2.3` | 通常允许升级 patch |
| `>=1.2.3` | 大于等于某版本 |
| `latest` | npm dist-tag，不推荐写进业务项目依赖 |

版本号通常表示：

```text
主版本.次版本.修订版本
major.minor.patch
```

常规语义：

- major：可能包含破坏性变更。
- minor：新增能力，通常保持兼容。
- patch：修复问题，通常保持兼容。

但这只是约定，不是宇宙法则。现实里也会有 patch 版本引入回归，minor 版本改变边界行为，major 版本迁移成本超出预期。所以升级依赖前应该看 changelog、release notes，并跑完整检查。

`^` 和 `~` 的行为还要注意 `0.x` 版本。很多 `0.x` 包仍处于不稳定阶段，兼容规则可能比 `1.x` 更保守。看到 `^0.3.2` 时，不要想当然地套用成熟包的升级预期。

## 九、锁文件的作用

锁文件记录实际安装出来的依赖树。

| 包管理器 | 锁文件 |
| -------- | ------ |
| npm | `package-lock.json` |
| pnpm | `pnpm-lock.yaml` |
| yarn | `yarn.lock` |

锁文件解决的是“同一份依赖声明，安装结果尽量一致”的问题。

`package.json` 中可能写：

```json
{
  "dependencies": {
    "axios": "^1.7.0"
  }
}
```

锁文件会记录实际版本和间接依赖版本：

```text
axios 1.7.9
follow-redirects 1.15.9
form-data 4.0.0
...
```

团队协作建议：

- 应用项目提交锁文件。
- 不手动编辑锁文件。
- 升级依赖后提交锁文件变化。
- CI 使用锁文件进行冻结安装。
- 一个项目只保留一种锁文件。

锁文件变化本身不是坏事。可疑的是你不知道它为什么变化。

## 十、install 与 ci / frozen-lockfile

本地开发常用：

```bash
npm install
pnpm install
```

它们可能根据 `package.json` 更新锁文件。

CI 更应该使用可复现安装：

```bash
npm ci
```

或：

```bash
pnpm install --frozen-lockfile
```

它们的目标是：如果锁文件和 `package.json` 不匹配，就失败，而不是悄悄更新锁文件。

对比：

| 场景 | 推荐命令 |
| ---- | -------- |
| 本地首次安装 | `pnpm install` / `npm install` |
| 本地添加依赖 | `pnpm add xxx` / `npm install xxx` |
| CI 安装 npm 项目 | `npm ci` |
| CI 安装 pnpm 项目 | `pnpm install --frozen-lockfile` |

CI 不应该替你“顺手修好”锁文件。CI 的职责是验证仓库当前状态是否可构建，不是帮你补交作业。

## 十一、node_modules 不只是一个目录

`node_modules` 是包管理器安装依赖后的结果。它通常不提交到 Git。

原因：

- 体积巨大。
- 和操作系统、包管理器实现、安装结果有关。
- 可以通过 `package.json` 和锁文件重新生成。

常见 `.gitignore`：

```text
node_modules
dist
.env.local
```

npm 和 pnpm 的 `node_modules` 结构不同。

npm 通常会做较多扁平化处理。pnpm 使用内容寻址存储和符号链接结构，并默认让包只能访问自己声明过的依赖。这就是为什么 pnpm 有时能暴露“在 npm 下碰巧能跑”的依赖问题。

例如你在代码里导入了一个没有写进 `package.json` 的包：

```ts
import leftPad from 'left-pad'
```

如果它只是某个间接依赖，npm 的扁平结构可能让你碰巧能访问到。pnpm 下则更可能直接失败。这不是 pnpm 刁难你，而是项目声明不诚实。

解决方式也很简单：

```bash
pnpm add left-pad
```

当然，真实项目里应该先判断这个包是否真的值得安装。为了三行代码引入一个不维护的小包，通常不是成熟的热爱复用，而是把风险外包。

## 十二、添加、更新和删除依赖

添加依赖：

```bash
pnpm add axios
pnpm add -D eslint
```

删除依赖：

```bash
pnpm remove axios
```

查看过期依赖：

```bash
pnpm outdated
```

按版本范围更新：

```bash
pnpm update
```

更新指定依赖：

```bash
pnpm update vite
```

npm 对应：

```bash
npm install axios
npm install -D eslint
npm uninstall axios
npm outdated
npm update
```

升级依赖建议：

1. 先看当前版本和目标版本。
2. 阅读 changelog 或 migration guide。
3. 小步升级，避免一次更新一大片。
4. 运行 `type-check`、`lint`、`test`、`build`。
5. 检查锁文件变化。

依赖升级不是抽卡。虽然有时体感很像，但我们最好不要主动把它玩成那样。

## 十三、全局安装与本地安装

全局安装：

```bash
pnpm add -g vite
```

本地安装：

```bash
pnpm add -D vite
```

项目工具优先使用本地安装。原因：

- 本地版本写进 `package.json`，团队可复现。
- CI 能安装同样版本。
- 不依赖某个人电脑上的全局工具。
- 不同项目可以使用不同工具版本。

推荐通过脚本调用本地工具：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  }
}
```

执行：

```bash
pnpm dev
```

包管理器会优先找到项目本地 `node_modules/.bin` 中的 `vite`。

如果只是临时运行一次工具，可以使用：

```bash
pnpm dlx create-vite
```

或 npm：

```bash
npm create vite@latest
```

## 十四、npx、npm create、pnpm dlx

这些命令经常用于创建项目或运行一次性 CLI。

| 命令 | 用途 |
| ---- | ---- |
| `npm create vite@latest` | 使用 npm 创建 Vite 项目 |
| `pnpm create vite` | 使用 pnpm 创建 Vite 项目 |
| `npx eslint .` | 临时或本地执行 npm 包命令 |
| `pnpm dlx some-cli` | pnpm 下临时执行 CLI |

创建项目时，官方文档通常会给出多种包管理器命令。选择和项目一致的即可，不要在一个项目里今天 npm、明天 pnpm、后天 yarn。工具链不是调味料，不需要每天换口味。

## 十五、依赖安全

依赖越多，风险越大。常见风险包括：

- 包维护停止。
- 新版本破坏兼容。
- 间接依赖漏洞。
- 安装脚本执行恶意代码。
- 包名相似导致误安装。
- 供应链攻击。

基本做法：

- 不随意安装小而冷门的包。
- 安装前看维护状态、仓库 issue、release 频率。
- 避免为了很小功能引入大依赖。
- 定期执行审计命令。
- 关键依赖升级后跑完整检查。
- 对锁文件变化保持敏感。

npm 审计：

```bash
npm audit
```

pnpm 审计：

```bash
pnpm audit
```

审计结果需要判断影响范围。不是所有漏洞都能影响你的项目，但也不能一看到 warning 就关掉终端假装世界和平。成熟做法是分级处理：可利用、可触达、影响生产路径的优先修。

## 十六、常见错误与排查

依赖问题可以按这个顺序查：

```text
Node 版本
 -> 包管理器版本
 -> 是否使用了正确锁文件
 -> package.json 和锁文件是否同步
 -> node_modules 是否损坏
 -> 是否缺少直接依赖
 -> peerDependencies 是否冲突
 -> 安装脚本是否失败
 -> 网络或 registry 是否异常
```

### Cannot find module

常见原因：

- 依赖没有安装。
- 依赖没有写进 `package.json`。
- 使用了错误包管理器。
- 路径别名只配了 TypeScript，没配 Vite。
- 包的导出字段发生变化。

处理：

```bash
pnpm install
pnpm add missing-package
```

如果是路径别名问题，要同时检查 `vite.config.ts` 和 `tsconfig.json`。

### Lockfile is out of date

常见于 CI：

```text
Cannot install with frozen-lockfile because lockfile is not up to date
```

意思是 `package.json` 和锁文件不匹配。

处理方式：

```bash
pnpm install
```

然后提交更新后的 `pnpm-lock.yaml`。

不要在 CI 里关掉 frozen-lockfile 来逃避问题。那只是把不一致放进下一次失败里。

### Unsupported engine

意思是当前 Node 版本不满足依赖或项目要求。

处理：

```bash
node -v
```

然后切换到项目要求的 Node 版本。

### Peer dependency warning

意思是某个包希望宿主项目安装特定范围的依赖。

处理方式：

- 检查 warning 中提到的包。
- 确认宿主项目依赖版本。
- 升级插件或框架到兼容版本。
- 不要随手 `--force`，除非你知道后果。

`--force` 和 `--legacy-peer-deps` 不是治疗方案，只是麻醉剂。该醒的时候还是会醒，而且可能更疼。

## 十七、团队协作建议

一个前端项目建议明确这些规则：

```text
Node 版本：20.x 或 22.x
包管理器：pnpm
锁文件：pnpm-lock.yaml
安装命令：pnpm install
开发命令：pnpm dev
构建命令：pnpm build
CI 安装：pnpm install --frozen-lockfile
```

可以写进 README：

````markdown
## Development

Required:

- Node.js >= 20
- pnpm 12

Install dependencies:

```bash
pnpm install
```

Start dev server:

```bash
pnpm dev
```

Build:

```bash
pnpm build
```
````

也可以在 `package.json` 中声明：

```json
{
  "packageManager": "pnpm@12.0.0",
  "engines": {
    "node": ">=20.0.0"
  }
}
```

规则越明确，协作成本越低。不要指望每个人通过猜测获得同样答案，那是占卜，不是工程。

## 十八、练习

打开一个前端项目的 `package.json`，完成下面检查：

- 解释每个 `scripts`。
- 找出 `dependencies` 和 `devDependencies`。
- 判断是否有 `engines.node`。
- 判断是否有 `packageManager`。
- 判断项目使用 npm、pnpm 还是 yarn。
- 判断锁文件是否唯一。
- 找出最近一次锁文件变化。
- 判断是否存在没有使用的依赖。
- 判断是否存在代码使用但 `package.json` 没声明的依赖。
- 执行一次干净安装和构建。

如果这些都能做完，你已经不只是会安装依赖，而是在理解项目的运行底座。

## 十九、延伸阅读

- npm `package.json` 文档：https://docs.npmjs.com/cli/v12/configuring-npm/package-json/
- npm 语义化版本说明：https://docs.npmjs.com/about-semantic-versioning/
- npm `npm ci` 文档：https://docs.npmjs.com/cli/v11/commands/npm-ci/
- npm `package-lock.json` 文档：https://docs.npmjs.com/cli/v8/configuring-npm/package-lock-json/
- pnpm `package.json` 文档：https://pnpm.io/package_json
- pnpm `install` 文档：https://pnpm.io/cli/install
- pnpm `add` 文档：https://pnpm.io/cli/add
- pnpm `update` 文档：https://pnpm.io/cli/update
