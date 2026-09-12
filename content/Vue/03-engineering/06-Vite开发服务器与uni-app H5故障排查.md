+++
date = '2026-09-12T21:00:00+08:00'
draft = false
title = 'Vite 是什么：从 localhost 连接被拒绝到 uni-app H5 404 的排查'
+++

在前端项目里访问 `http://localhost:5173/` 失败时，很多人会立刻怀疑 Vue 代码、接口跨域、后端服务，甚至怀疑浏览器“抽风”。这些方向偶尔会命中，但顺序不对。浏览器地址栏中的一次访问，至少跨越了地址解析、TCP 连接、HTTP 响应、HTML 入口、JavaScript 模块加载和应用渲染几个层级。前一层没有成功，后一层根本没有出场机会。

本文以一个 uni-app 项目的实际现象为线索，解释 Vite 是什么、它在开发阶段做了什么，以及两个很相像但根因完全不同的问题：

- 浏览器提示 `ERR_CONNECTION_REFUSED`，无法连接 `localhost:5173`；
- 连接恢复后，浏览器提示 `HTTP ERROR 404`，找不到 `/` 页面。

结论先写在前面：前者是**网络监听地址与本机连接**的问题，后者是**H5 入口文件缺失**的问题。它们都不是微信小程序页面自身的编译故障。

## 一、Vite 到底是什么

Vite 是现代前端项目常用的构建工具和开发服务器。它主要承担两类工作：

1. **开发阶段**：启动本地 HTTP 服务，按需转换并返回 HTML、TypeScript、Vue 单文件组件、CSS 和静态资源，同时提供热更新。
2. **生产构建阶段**：把应用打包、压缩、拆分为可部署的静态资源。

它不是业务后端，也不负责你的用户、订单或 API 数据。开发时它更像一个专门服务前端源代码的本地服务器和即时翻译器。

运行下面的命令后：

```bash
npm run dev
```

通常会发生这样的过程：

```text
终端执行 npm 脚本
  -> Vite 读取 vite.config.ts
    -> 启动本地 HTTP 开发服务器
      -> 浏览器访问 localhost:端口
        -> Vite 返回 index.html
          -> 浏览器请求 main.ts、.vue、.css 等模块
            -> Vite 按需转换模块并返回
              -> Vue 应用挂载并渲染页面
```

这里最重要的一点是：**浏览器不是直接执行 `.ts` 和 `.vue` 文件的**。浏览器先拿到 HTML，再根据 HTML 中的模块脚本请求 `main.ts`；Vite 在中间把 TypeScript、Vue SFC 和样式处理为浏览器可理解的资源。

### 1. 为什么它启动得快

传统的开发服务器往往先把整套应用打成一个或多个 bundle，再交给浏览器。项目变大后，每次启动和重建都可能变慢。

Vite 在开发时主要使用浏览器原生 ES Module 能力。浏览器请求到哪个模块，Vite 就转换哪个模块；修改一个 Vue 组件时，也尽量只更新受影响的模块。这就是常说的“按需编译”和 HMR（Hot Module Replacement，热模块替换）。

```text
浏览器请求 /src/main.ts
  -> Vite 转换 TypeScript 并返回 JavaScript

main.ts 导入 ./App.vue
  -> 浏览器继续请求 App.vue
  -> Vite 编译该 Vue 组件并返回模块

开发者修改 pages/market/index.vue
  -> Vite 通知浏览器这个模块已变化
  -> 浏览器只更新相关模块，而非重新加载整个应用
```

速度并不意味着 Vite 可以猜测项目结构。它仍然需要明确的入口、正确的配置和可访问的监听地址。工具负责高效执行规则，不负责替工程补齐缺失的规则；这一点有时不够浪漫，但很可靠。

### 2. `vite.config.ts` 的职责

`vite.config.ts` 是 Vite 的配置文件。它常用于定义：

- 使用哪些插件，例如 Vue、uni-app 或 React 插件；
- 路径别名，例如把 `@/components` 映射为 `src/components`；
- 本地服务器的地址、端口、代理和 HTTPS；
- 打包输出、静态资源路径和环境行为。

一个简单的 Vue 配置可能是：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
```

uni-app 项目使用的插件不同，但原则相同：Vite 本身提供开发服务器和构建管线，`@dcloudio/vite-plugin-uni` 让它理解 uni-app 的页面配置、跨端 API 和不同编译目标。

```ts
import { defineConfig } from 'vite'
import uniPlugin from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uniPlugin()],
})
```

## 二、一次访问实际上经过哪些层级

访问 `http://localhost:5173/` 时，不能只把它理解成“打开一个网页”。更准确的顺序如下：

```text
1. 解析 localhost
2. 建立到 IP:5173 的 TCP 连接
3. 发送 HTTP GET / 请求
4. Vite 根据路径查找或生成资源
5. 浏览器接收 index.html
6. 浏览器加载 /src/main.ts 与其依赖
7. Vue / uni-app 创建应用并渲染首个页面
```

每一步都可能失败，报错含义也不同。

| 现象 | 失败层级 | 应优先检查的对象 |
| ---- | -------- | ---------------- |
| `ERR_CONNECTION_REFUSED` | TCP 连接 | 进程、端口、监听地址、防火墙或安全软件 |
| `ERR_CONNECTION_TIMED_OUT` | 网络传输 | 网络路径、远端服务、防火墙规则 |
| `HTTP 404` | HTTP 资源路由 | 请求路径、`index.html`、静态资源或服务端路由 |
| 空白页、控制台报错 | JavaScript 运行时 | `main.ts`、Vue 组件、依赖、运行时异常 |
| 接口 `401`、`403`、`500` | 业务 API | 鉴权、参数、后端业务逻辑、服务端日志 |

这种分层非常实用。例如出现连接被拒绝时，先去检查 `App.vue` 或 CORS 配置没有意义：HTTP 请求都还没有发出去。相反，已经得到 HTTP 404 时，再去改端口监听往往也是徒劳的，因为网络层已经成功了。

## 三、问题一：为什么会出现 `ERR_CONNECTION_REFUSED`

### 1. 报错真正表示什么

浏览器中的 `ERR_CONNECTION_REFUSED` 表示目标地址拒绝了 TCP 连接。常见原因有：

- 对应端口没有进程在监听；
- 服务启动后异常退出；
- 服务监听在另一个端口；
- 服务只监听 IPv6 或 IPv4，而浏览器尝试了另一种地址；
- 本机安全软件、代理、VPN 或防火墙拦截了连接；
- 访问地址不是服务实际监听的地址。

它**不表示** Vue 页面返回了错误，也不表示 API 跨域。此时浏览器连开发服务器都没有连上，自然不可能得到 Vue 或后端的业务响应。

### 2. `localhost` 不只有一个地址

`localhost` 是本机回环主机名，常见的解析结果包括：

```text
IPv4: 127.0.0.1
IPv6: ::1
```

二者都表示“当前机器”，但它们属于不同的 IP 协议族。服务监听在 `::1:5173`，并不必然等于它也监听在 `127.0.0.1:5173`。

可以在 PowerShell 中查看端口状态：

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen |
  Format-Table LocalAddress, LocalPort, State, OwningProcess
```

典型输出及含义：

| `LocalAddress` | 说明 |
| -------------- | ---- |
| `127.0.0.1` | 只接受本机 IPv4 访问 |
| `::1` | 只接受本机 IPv6 访问 |
| `0.0.0.0` | 接受所有 IPv4 网卡上的访问 |
| `::` | 接受所有 IPv6 网卡上的访问，是否同时接收 IPv4 取决于系统和程序设置 |

在这次场景中，Vite/uni 开发进程最初只监听在：

```text
::1:5173
```

而本机访问结果是：

```text
127.0.0.1:5173  -> ECONNREFUSED
::1:5173        -> EACCES
```

第一条说明 IPv4 没有服务监听；第二条说明 IPv6 地址的连接被系统以“访问不允许”的方式拒绝。浏览器最终表现为连接失败。这种情况常见于 IPv4/IPv6 偏好不同，或企业安全客户端、VPN、代理与本机网络策略对 IPv6 loopback 存在干预。

### 3. 为什么“进程还在”仍然打不开

仅仅看到 `node.exe` 进程存在，不能证明浏览器能访问页面。至少还要确认三件事：

```text
进程存在
  != 端口在监听
  != 监听在浏览器访问的地址
  != HTTP 首页能够正确返回
```

可以继续查看 PID 对应的命令行：

```powershell
$listener = Get-NetTCPConnection -LocalPort 5173 -State Listen
Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" |
  Select-Object ProcessId, Name, CommandLine
```

这一步可以排除“5173 被另一个项目、Mock 服务或代理程序占用”的情况。排错时不要只相信端口号；确认端口的拥有者才是有效证据。

### 4. 为何固定到 `127.0.0.1` 能解决问题

如果只是本机浏览器调试，可以显式指定 Vite 的监听地址：

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import uniPlugin from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uniPlugin()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
})
```

这样做的效果是：

```text
Vite 固定监听 127.0.0.1:5173
  -> 浏览器访问 http://127.0.0.1:5173/
  -> 不再依赖 localhost 在 IPv4 与 IPv6 间的解析、优先级和兼容行为
```

`strictPort: true` 同样值得保留。端口 `5173` 被占用时，Vite 默认可能改用 `5174`、`5175` 等端口；终端会打印新地址，但浏览器若仍访问旧地址，就会出现“服务明明启动了却打不开”的错觉。开启严格端口后，它会直接报错，迫使问题在启动阶段暴露。

如果要从手机或局域网其他设备访问开发服务，才考虑：

```ts
server: {
  host: '0.0.0.0',
  port: 5173,
  strictPort: true,
}
```

`0.0.0.0` 会暴露到局域网网卡，方便真机调试，但也扩大了访问范围。仅在本机调试时，`127.0.0.1` 是更小、更明确的边界。

## 四、问题二：为什么连接成功后又变成 HTTP 404

修复监听地址后，浏览器不再提示连接被拒绝，而是提示：

```text
HTTP ERROR 404
```

这不是同一个错误换了文案，而是排错进入了下一层。

```text
第一次：浏览器到 Vite 的 TCP 连接没有建立
第二次：TCP 连接已建立，Vite 已收到 GET /，但找不到可返回的首页资源
```

可以用 PowerShell 直接验证：

```powershell
Invoke-WebRequest http://127.0.0.1:5173/ -SkipHttpErrorCheck
Invoke-WebRequest http://127.0.0.1:5173/@vite/client
Invoke-WebRequest http://127.0.0.1:5173/src/main.ts
```

若结果是：

```text
/                 -> 404
/@vite/client     -> 200
/src/main.ts      -> 200
```

则说明 Vite 服务、模块转换能力和源文件访问都正常；缺失的是根路径对应的 H5 HTML 入口。

### 1. 为什么 Vite 项目的根路径依赖 `index.html`

在 Vite 项目中，项目根目录的 `index.html` 不只是传统意义上的静态首页，它还是浏览器启动前端模块图的入口。一个最小的入口通常类似：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>示例应用</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

其中最关键的是：

```html
<script type="module" src="/src/main.ts"></script>
```

它告诉浏览器从 `main.ts` 开始加载应用。Vite 拦截后续的模块请求，转换 TypeScript 与 Vue 单文件组件，最后让 Vue 挂载到 `#app`。

如果根目录没有 `index.html`，访问 `/` 时 Vite 没有默认网页可返回：

```text
GET /
  -> 需要首页入口
  -> 根目录没有 index.html
  -> 404
```

即使 `src/main.ts`、`src/App.vue` 都存在，浏览器也不会自行猜测应该从哪个文件启动。它不能也不该这么做；工程入口应该是明确可读的，而不是由工具进行猜谜。

### 2. uni-app H5 的入口为何略有不同

uni-app 同时面对 H5、小程序和 App 等目标。对 H5 来说，它仍要运行在浏览器内，因此同样需要 `index.html`。常见的 uni-app H5 入口会保留两个供编译器处理的注释：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"
    />
    <title>造物云印</title>
    <!--preload-links-->
  </head>
  <body>
    <div id="app"><!--app-html--></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- `<!--preload-links-->`：构建或服务阶段插入需要的预加载资源；
- `<!--app-html-->`：为 SSR 或相关运行时场景保留应用 HTML 注入位置；
- `/src/main.ts`：仍然是浏览器端模块图的起点。

在纯客户端开发场景中，上述注释未必都直接影响首次渲染，但保留标准入口结构能使开发、构建及后续升级更稳定。

### 3. 为什么小程序端不需要它

微信小程序不运行在浏览器 HTML 页面中。它的构建与启动流程是：

```text
npm run dev:mp-weixin
  -> uni-app 编译页面、样式、脚本和配置
    -> 生成 dist/dev/mp-weixin
      -> 微信开发者工具导入该目录
        -> 微信运行时根据 app/pages 配置启动页面
```

小程序依赖的是页面配置、编译后的 JS、WXML、WXSS 和 JSON，而不是根目录的 `index.html`。因此，缺失 H5 的 `index.html` 会让 `npm run dev:h5` 访问 `/` 得到 404，但通常不会阻止：

```bash
npm run dev:mp-weixin
```

这也是跨端项目中需要明确区分的平台边界：同一份 Vue/uni-app 源码可以服务多个端，但每个目标端都有自己的入口与产物形式。

| 内容 | H5 | 微信小程序 |
| ---- | -- | ---------- |
| 浏览器入口 | 根目录 `index.html` | 不使用 HTML 入口 |
| 本地启动方式 | `npm run dev:h5` | `npm run dev:mp-weixin` |
| 开发运行位置 | Chrome、Edge 等浏览器 | 微信开发者工具、微信客户端 |
| 典型开发产物 | 由 Vite HTTP 服务即时返回 | `dist/dev/mp-weixin` |
| 路由/页面依据 | HTML 入口 + uni-app 运行时 | `pages.json` 与小程序页面配置 |

这不表示 H5 调通就能替代小程序测试。文件选择、支付、登录态、微信域名校验、真机权限与 `uni.*` 平台能力，仍应在微信开发者工具和真机中验证。

## 五、一次完整的排查流程

面对“本地前端打不开”，推荐遵循由外到内的顺序。每一步都通过可观察的证据决定下一步，而不是同时改端口、改代理、重装依赖和改业务代码。

### 1. 确认启动命令与终端输出

先确认运行的是目标平台对应的脚本：

```bash
npm run dev:h5
```

不要把 `dev:mp-weixin` 的成功误认为 H5 服务也已启动。前者是小程序开发构建，后者才是要在浏览器中访问的 Vite 服务。

再检查终端最终打印的地址和端口。若启动提示实际使用 `5174`，浏览器继续访问 `5173` 当然会失败。

### 2. 确认端口、地址和进程

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen |
  Format-Table LocalAddress, LocalPort, OwningProcess
```

如果没有输出，说明没有服务监听；如果地址与访问目标不一致，说明存在 IPv4/IPv6 或监听范围问题；如果 PID 不属于当前项目，应先处理端口占用。

### 3. 用明确 IP 绕开 `localhost` 歧义

```powershell
Invoke-WebRequest http://127.0.0.1:5173/ -SkipHttpErrorCheck
Invoke-WebRequest http://[::1]:5173/ -SkipHttpErrorCheck
```

这一步有助于判断是地址族问题，还是服务本身无法提供页面。注意 IPv6 URL 必须用方括号包住 `::1`。

### 4. 区分“无法连接”和“已有 HTTP 响应”

- `ECONNREFUSED`、`ERR_CONNECTION_REFUSED`：回到端口与监听地址检查。
- `404`：服务已收到请求，检查路径、入口文件和静态资源。
- `500`：服务运行中出现异常，检查终端、插件日志或服务器端堆栈。
- 页面 200 但空白：打开 DevTools 的 Console，检查 JavaScript 运行时错误。

### 5. 核对 H5 入口与模块路径

对于 Vite H5 项目，检查根目录是否存在：

```text
index.html
```

并确认其引用的模块路径正确：

```html
<script type="module" src="/src/main.ts"></script>
```

若项目使用 `main.js`、`src/main.ts` 或其它约定，HTML 路径必须与真实文件一致。Windows 文件系统对大小写较宽容，但 CI、Linux 容器和生产服务器往往不宽容；不要把“本地能打开”误当作文件名没有问题。

## 六、容易混淆的几个概念

### 1. 404 不是跨域错误

404 表示服务器已经成功处理请求，并明确告诉客户端“这个路径对应的资源不存在”。跨域错误则通常发生在浏览器同源策略检查阶段，Console 会显示 CORS 相关信息。两者应使用完全不同的排查路径。

### 2. 能访问 `main.ts` 不代表应用能打开

`/src/main.ts` 返回 200，只能说明 Vite 能找到并转换这个模块。浏览器正常启动仍需要从 `/` 取得 HTML，HTML 再引用该模块。入口链路缺任何一环，页面都无法完整呈现。

### 3. H5 404 不代表小程序首页 404

小程序页面由 `pages.json`、编译产物与微信运行时管理；H5 根路径由 `index.html` 和 Vite 管理。两端可能共用 Vue 页面源码，却不共用浏览器入口。把 H5 的 404 直接归因到小程序路由，是把两个运行环境混在了一起。

### 4. `0.0.0.0` 不是浏览器访问地址

`0.0.0.0` 的含义是“服务器监听所有 IPv4 网卡”，不是一个应填进浏览器地址栏的实际目标。配置为 `host: '0.0.0.0'` 后，浏览器应使用：

```text
http://127.0.0.1:5173/
```

或电脑的实际局域网 IP，例如：

```text
http://192.168.1.20:5173/
```

## 七、可复用的最小检查清单

以后遇到 `localhost` 打不开时，可以按下面的顺序执行：

1. 看终端：目标脚本是否真的启动成功，最终端口是什么。
2. 看端口：`Get-NetTCPConnection` 是否存在监听，监听在哪个地址。
3. 看进程：监听 PID 是否属于当前项目。
4. 看地址族：分别测试 `127.0.0.1` 与 `::1`。
5. 看状态码：连接失败、404、500、页面白屏分别进入不同分支。
6. 看入口：H5 是否存在根目录 `index.html`，模块路径是否正确。
7. 看运行时：页面返回 200 后，再查 DevTools 的 Console、Network 与 Sources。
8. 看平台：H5 与微信小程序分别用对应的构建命令和运行环境验证。

## 八、总结

Vite 让前端开发更快，但它并没有改变 Web 应用的基本事实：浏览器要先连上一个 HTTP 服务，再取得 HTML 入口，最后加载模块并执行应用代码。

这次问题可以用一句流程图概括：

```text
只监听 ::1，且本机 IPv6 回环连接受限
  -> localhost:5173 连接被拒绝

改为监听 127.0.0.1
  -> 浏览器可以连上 Vite

根目录缺少 index.html
  -> GET / 返回 HTTP 404

补齐 H5 入口并重启服务
  -> 浏览器才能加载 main.ts、App.vue 与 uni-app 页面
```

记住两个判断就足够应对大多数类似场景：

- **连接被拒绝**：先看进程、端口、监听地址和本机网络策略。
- **HTTP 404**：先看请求路径、入口文件和服务实际返回的资源。

先确认问题位于哪一层，再修改那一层的配置或文件。这样比对着一个报错反复重启项目更可靠，也更节省时间。
