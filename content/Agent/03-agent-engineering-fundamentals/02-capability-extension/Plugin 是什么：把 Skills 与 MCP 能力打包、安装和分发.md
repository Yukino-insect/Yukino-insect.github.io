+++
date = '2026-08-28T17:45:00+08:00'
draft = false
title = 'Plugin 是什么：把 Skills 与 MCP 能力打包、安装和分发'
+++
Plugin 是可安装、可分发的能力包。它可以包含一个或多个 Skills、一个 MCP Server，或两者兼有；如果 MCP Server 支持，也可以附带界面能力。换言之，Skill 描述可复用工作流，MCP 连接外部工具，而 Plugin 解决“怎样把这些成熟能力交付给别人使用”。

OpenAI 官方的 [Build plugins 指南](https://learn.chatgpt.com/docs/build-plugins) 指出，ChatGPT 与 Codex 共用一个 Plugin 目录；公开发布一次后，可在两类产品的受支持入口中被发现。

## 一、为什么不能把 Plugin 当成 Skill 的同义词

它们关系紧密，却处在不同层：

```text
Plugin（安装与分发单位）
├── Skills（任务流程与领域知识）
├── MCP Server / MCP 配置（外部工具和数据连接）
└── 可选的界面与展示资源
```

一个人还在打磨“会议纪要转行动项”的个人流程时，直接维护一个 Skill 最轻量。等流程稳定、要分享给团队、要组合多个 Skills，或需要打包某个外部服务连接时，再构建 Plugin。过早封装只会让实验成本变高；成熟后仍靠手工复制文件，则会让版本和依赖逐渐失控。

## 二、Plugin 的核心作用

- **安装**：让用户通过统一入口启用能力，而非手动分发许多目录。
- **组合**：将相互配合的 Skills、MCP Server 和展示资源放进一个版本化包。
- **分发**：支持本地 Marketplace 测试，也支持面向更大范围的发布。
- **治理**：以清单形式描述包的名称、版本、内容与依赖，便于审查和维护。

Plugin 并不是新的权限边界。用户安装某个 Plugin 后，具体工具实际能够访问什么，仍由 MCP Server、认证、Codex 权限与工作区策略共同决定。

## 三、最小的 Skills-only Plugin

一个只包含 Skill 的 Plugin 至少需要清单和一项 Skill：

```text
meeting-follow-up/
├── .codex-plugin/
│   └── plugin.json
└── skills/
    └── meeting-follow-up/
        └── SKILL.md
```

`plugin.json` 负责声明包信息及 Skills 目录：

```json
{
  "name": "meeting-follow-up",
  "version": "1.0.0",
  "description": "Turn meeting notes into decisions and next steps",
  "skills": "./skills/"
}
```

对应的 `SKILL.md` 仍需有自己的 `name` 与 `description`。清单的职责是分发和版本标识，Skill 的职责是定义具体流程；两份描述不能互相代替。

## 四、如何创建和测试

在 Codex 中可调用内置创建器：

```text
$plugin-creator
```

创建器能够生成必需的 `.codex-plugin/plugin.json`、组织目录，并可添加本地 Marketplace 条目用于测试。官方建议完成后依次审查清单、检查每项内置 Skill、刷新并安装 Plugin，然后用具有代表性的请求在新对话中测试。

若 Plugin 包含 MCP Server，应先独立验证这个 Server 的工具、认证、部署和错误处理，再将连接信息交给 Plugin Creator。不要把“能打包”误解为“已经可安全上线”；包装纸从来不是质量保证。

## 五、选择 Skill、MCP 还是 Plugin

| 需求 | 首选 |
| --- | --- |
| 当前项目内的一项可复用流程 | 仓库级 Skill |
| 多个客户端需要访问同一外部系统 | MCP Server |
| 需要把多项流程或流程加连接器交给团队安装 | Plugin |
| 仍在探索的个人工作方法 | 先写 Skill，稳定后再 Plugin 化 |

真实项目常常是“Skill + MCP + Plugin”的组合：Skill 规范调查步骤和报告格式，MCP 提供工单与日志查询，Plugin 将这套能力安装给团队。先让每层只承担自己的职责，后续的审查、升级和故障定位才不会变成猜谜。

## 六、发布前检查

- 名称、版本和说明是否稳定且具体；
- 每个 Skill 是否有明确触发条件、输入输出与禁止动作；
- MCP 工具是否最小授权，认证和密钥是否隔离；
- 是否在本地 Marketplace 与新对话中做过代表性测试；
- 是否写清了安装、升级、禁用与回滚方式；
- 是否有人复核了所有脚本、网络访问和外部副作用。

Plugin 的价值是让经得起审查的能力被可靠复用，而不是把未经审查的自动化扩大传播范围。前者是工程资产，后者通常只是规模更大的麻烦。
