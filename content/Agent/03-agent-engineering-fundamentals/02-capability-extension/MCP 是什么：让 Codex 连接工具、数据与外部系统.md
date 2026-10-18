+++
date = '2026-08-28T17:40:00+08:00'
draft = false
title = 'MCP 是什么：让 Codex 连接工具、数据与外部系统'
+++
MCP 是 **Model Context Protocol**，即模型上下文协议。它让 ChatGPT 或 Codex 能以统一方式连接外部工具和上下文：例如浏览器、设计工具、内部文档、GitHub、数据库或工单系统。它不是模型、不是 Prompt、也不是某个 Agent 框架；它解决的是 Agent 与外部能力之间的连接问题。

按照 [OpenAI 的 MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)，Codex 可连接本地或远程 MCP Server；桌面应用、Codex CLI 与 IDE 扩展共享同一 Codex host 的 MCP 配置。

## 一、MCP 解决了什么问题

没有统一协议时，每个 Agent 客户端都要分别适配内部 API、日志平台、知识库和开发工具。工具提供者不断重复开发连接层，使用者也不断重复配置。MCP 将这种关系拆成标准角色：

```text
Codex / ChatGPT（Host）
          │ MCP
          ▼
MCP Server
├── Tools：可调用的动作
├── Resources：可读取的上下文或数据
└── Instructions：服务级约束与使用说明
```

例如，一个 GitHub MCP Server 可以提供“读取 Pull Request”“列出 Issue”“创建评论”等工具；Codex 仍负责理解用户目标、选择何时调用和怎样解释结果。协议负责连接，不负责替人制定业务流程。

## 二、Codex 中常见的两种连接方式

| 类型 | 工作方式 | 适合场景 |
| --- | --- | --- |
| STDIO | Codex 启动本地命令，并通过标准输入输出通信 | 本地开发工具、文件系统、个人脚本 |
| Streamable HTTP | Codex 通过服务地址访问远程 Server | 团队共享服务、云端工具、需要 OAuth 的系统 |

官方文档列出了 Streamable HTTP 可使用的 Bearer Token、OAuth 等认证方式。无论本地还是远程，都要把 Server 当作能够读写系统的真实集成来审查；“它叫协议”并不会使权限问题自动消失。

## 三、如何在 Codex 中配置

MCP Server 的配置默认位于 `~/.codex/config.toml`，也可以放在受信任项目的 `.codex/config.toml` 中。CLI 的典型操作是：

```bash
codex mcp add context7 -- npx -y @upstash/context7-mcp
codex mcp list
codex mcp login <server-name>
```

在桌面应用或 IDE 扩展中，可以从 MCP Servers 设置页添加 Server，选择 STDIO 或 Streamable HTTP，填写命令或地址后重启。运行中的 Codex TUI 可用 `/mcp` 查看已连接的 Server。

手工配置 STDIO Server 时，核心字段通常包括启动命令、参数、工作目录及允许传递的环境变量：

```toml
[mcp_servers.example]
command = "node"
args = ["./dist/server.js"]
cwd = "/path/to/project"
env_vars = ["EXAMPLE_API_TOKEN"]
```

配置中的令牌、环境变量和启动命令都应经过审查。不要为了图省事把整个环境变量集合或高权限凭据无差别暴露给一个来源不明的 Server。

## 四、MCP 与 Skill 如何协作

Skill 规定“**怎样完成**一项工作”；MCP 提供“**能调用什么**外部能力”。二者组合后，才是比较完整的自动化。

```text
“排查线上告警”的 Skill
        │ 指导收集证据、判断优先级、输出报告
        ▼
日志 / 监控 / 工单 MCP Server
        │ 提供查询日志、读取指标、创建草稿的工具
        ▼
Codex 依据权限与用户指令执行
```

如果只是调用一个项目内的纯函数，不必为了形式感搭建 MCP；普通代码调用可能更简单。如果某项能力要被多个 Agent 客户端、语言或团队复用，并且需要独立鉴权、审计和生命周期，MCP 的价值就会出现。

## 五、使用边界与安全要点

1. 只连接可信来源，审查其工具清单、文档和实际网络行为。
2. 为每个 Server 分配最小权限；读操作和写操作尽量分开。
3. 对创建、删除、部署、发消息等外部副作用保留用户确认。
4. 使用明确的认证与令牌管理，不在配置和日志中泄露密钥。
5. 为失败、超时、限流和不可用服务设计降级路径。

MCP 能减少集成的重复劳动，但不能免除集成责任。把外部系统的钥匙交给 Agent 前，先确认门后究竟是什么，这并不算多疑。
