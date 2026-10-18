+++
date = '2026-09-27T20:00:00+08:00'
draft = false
title = 'Codex Skill 实战：从团队 Git 规范制作并使用可复用技能'
+++
上一节“Skill 是什么”解释了 Skill 的定位、目录结构与触发机制；但只知道这些还不够。真正开始制作时，最容易犯的错误是把一份长文档原封不动塞进 `SKILL.md`，然后期待 Agent 自行领悟哪些命令可以执行、哪些事情需要停下确认。它通常不会如你想象得那样可靠。

本文以一个真实目标为例：将团队的 Git 分支与提交规范沉淀为 `git-branch-and-commit` Skill。读完后，你应当能够从已有团队规范中提炼出一个可发现、可执行、可验证，并且不会擅自推送代码的 Skill。

> 本文示例面向安装了 Codex 的 Windows 环境，命令使用 PowerShell。路径和系统目录可能因安装方式不同而变化；先用实际环境为准，不必对示例路径产生宗教般的执着。

## 一、先定义工作边界，而不是急着写 Markdown

团队 Git 规范通常会同时包含分支模型、提交消息、PR、CI、仓库结构等内容。它们不是一个单一操作。若把“建分支、提交、推送、开 PR、合并、清理分支”统统放进一个 Skill，触发范围和权限范围都会变得模糊。

本例只负责两项可组合的本地工作：

- 从受保护的 `main` 创建一个合规的短期分支；
- 审查选定改动、生成规范提交信息并创建**本地** commit。

它刻意不做推送、开 PR、合并、rebase 已发布分支、删除分支或绕过 hook。这不是功能残缺，而是把高风险的外部影响留给用户明确授权。尤其是 AI 协作的提交，在 push 或合入前仍然必须由人审查。

```text
团队 Git 规范
   │
   ├── 分支命名、main 同步、短分支原则
   ├── Conventional Commits、中文标题、trailer
   ├── PR review、CI、合入策略
   └── 密钥、hook、force push 等安全约束
            │
            ▼
git-branch-and-commit Skill
   ├── 检查工作树与暂存区
   ├── 创建本地工作分支
   ├── 选择性暂存、验证、创建本地 commit
   └── 报告 SHA、验证结果和剩余工作
            │
            └── 不推送 / 不开 PR / 不合并
```

这一步会直接决定 Skill 是否值得维护。一个好 Skill 不是“让 Agent 记住更多事情”，而是把一个高频、稳定、边界清楚的任务固定下来。

## 二、先把规范拆成“主流程”和“按需参考”

`SKILL.md` 会在 Skill 触发后读入上下文，因此它应当是一份可执行的操作说明，而不是规范文档的备份。通常保留下面几类信息：

| 放在 `SKILL.md` | 放在 `references/` |
| --- | --- |
| 操作顺序、检查命令、停止条件 | 分支类型完整定义与命名示例 |
| 哪些操作需要显式授权 | commit type、scope 与 footer 细则 |
| 哪些行为禁止执行 | PR、CI、仓库结构等扩展规范 |
| 最小可用的命令模板 | 具体团队政策的来源与解释 |

本例将团队 `DevSpecDoc/workflow` 下的分支、commit、PR、仓库与工具链要求浓缩到 `references/devspec-git-policy.md`。这让主流程保持短小，而 Agent 在需要判断 `hotfix/` 与 `fix/`、破坏性变更 footer、锁文件拆分等细节时仍有可追溯的依据。

不要把资料复制得比源文件还长。参考资料的目的，是保存执行时不可缺少的团队专有规则；通用 Git 常识和大段背景解释会稀释真正的约束。

## 三、用 `description` 写出触发条件和反向边界

Skill 目录中的必需文件是 `SKILL.md`。文件开头的 YAML front matter 至少包含 `name` 和 `description`：

```markdown
---
name: git-branch-and-commit
description: Create a compliant local Git branch and/or local commit under the team's simplified GitHub Flow and Conventional Commits policy. Use when asked to start a feature, fix, documentation, refactor, hotfix, release, or spike branch; prepare staged changes; draft or create a Chinese Conventional Commit; or verify branch and commit safety before a PR. Do not use for pushing, merging, rebasing published branches, or bypassing hooks unless the user explicitly requests those separate actions.
---
```

这里有三层信息：

- `name` 是显式调用名，因此必须简短、稳定，使用小写字母、数字和连字符；用户可以写 `$git-branch-and-commit`。
- `description` 说明“做什么”和“什么时候用”。Codex 会先依据它决定是否加载完整正文，所以不能只写“Git 工具”。
- 结尾的反向边界同样重要。它告诉 Agent：即使任务涉及 Git，也不要顺手 push、合并或绕过质量门禁。

描述过宽会误触发，例如“帮助处理任何 Git 问题”；描述过窄则用户每次都要记住显式调用。实用的写法是列出用户的自然表达：新功能分支、修复分支、暂存改动、写中文 commit、提交前检查。

## 四、用 Skill Creator 初始化目录

Codex 内置的 `skill-creator` 会创建符合约定的骨架，并提供基础校验。先在 Codex 对话中调用它：

```text
$skill-creator
```

在 Windows 的本地用户级安装中，默认的可发现目录通常是：

```text
%USERPROFILE%\.codex\skills\
```

本例的目标目录为：

```text
C:\Users\<用户名>\.codex\skills\git-branch-and-commit\
```

初始化器的典型命令如下。系统内置 Skill 的实际安装路径可能不同，因此先确认 `init_skill.py` 所在位置再执行。

```powershell
python <skill-creator路径>\scripts\init_skill.py `
  git-branch-and-commit `
  --path "$env:USERPROFILE\.codex\skills" `
  --resources references `
  --interface "display_name=Git 分支与提交" `
  --interface "short_description=按团队规范安全创建 Git 分支并生成中文提交记录" `
  --interface "default_prompt=Use $git-branch-and-commit to create a compliant branch and commit the current change."
```

几个容易被忽略的约束：

- 目录名必须与 `name` 对应，使用小写连字符形式；
- `short_description` 是 UI 摘要，创建器会校验其长度，不能随意写成两三个字；
- `default_prompt` 要明确提到 `$git-branch-and-commit`，这样 UI 插入的示例才真能调用对应 Skill；
- 只在确实需要时创建 `scripts/`、`references/` 或 `assets/`。本例只有政策资料，因此只需要 `references/`。

完成后，目录应接近下面的结构：

```text
git-branch-and-commit/
├── SKILL.md
├── references/
│   └── devspec-git-policy.md
└── agents/
    └── openai.yaml
```

`agents/openai.yaml` 是可选的界面元数据，不承载核心流程。即使它缺失，只要 `SKILL.md` 合格，Skill 本身仍可以工作。

## 五、把“先检查，再改动”写成不可跳过的流程

Git Skill 最危险的错误不是分支名不漂亮，而是它在错误仓库、混杂工作树或含密钥的暂存区直接执行了写操作。因此流程必须先收集证据：

```powershell
git rev-parse --show-toplevel
git status --short --branch
git branch --show-current
git remote -v
git diff --stat
git diff --cached --stat
git diff --cached --name-only
```

这些命令分别回答：当前目录是不是仓库、工作树是否干净、在哪个分支、有没有远程、未暂存和已暂存的改动各是什么。注意，`git diff --cached --stat` 只说明规模，不说明语义；真正准备提交前仍必须查看 `git diff --cached`。

Skill 的停止条件也必须明确。以下情况不应由 Agent “自作聪明”地修复：

- 当前目录不是 Git 工作树，或者没有 `main`；
- 切换到 `main` 会与未提交改动冲突；
- 工作区有多项无关修改，用户没有说哪些要提交；
- 暂存文件包含 `.env`、私钥、证书、构建产物或不明二进制；
- 变更无法归入一个可审查的 type、scope 和标题。

面对这些情况，正确行为是报告事实并请求方向；不是 `git stash`、`git reset --hard`、`git clean` 或 `git add .`。后几种命令的确很快，快到足以让你在几秒钟内失去本不该失去的工作成果。

## 六、将分支规则和 commit 规则变成可执行判断

建分支时，Skill 先安全地同步 `main`，再创建短分支：

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/device-register-api
```

`--ff-only` 的意义是拒绝本地意外产生的 merge commit。若没有 `origin/main`、工作树无法安全切换，或项目根本不使用 `main`，Skill 应停下报告，而不是猜测远程或偷偷换基线。

提交时，Skill 要引导 Agent 只暂存确认过的路径或 hunk：

```powershell
git add -- src/device/DeviceController.java src/device/DeviceControllerTest.java
git diff --cached --check
git diff --cached
```

然后根据团队的 Conventional Commits 规则写消息：

```text
feat(device): 新增设备注册接口骨架

补充注册流程的请求校验与最小控制器实现。
验证：mvn test 通过。

Co-Authored-By: Codex <noreply@openai.com>
```

其中 `feat` 表示新增能力，`device` 是业务 scope，标题使用中文祈使句。实现和对应测试属于同一个逻辑改动，应一起提交；依赖锁文件的独立变化、无关重构和另一个模块的修复则应该拆开。若接口存在不兼容变更，写成 `feat(device)!:`，并添加 `BREAKING CHANGE:` footer 说明影响与迁移方式。

最后创建 commit 时，不允许用 `--no-verify` 绕过 hook：

```powershell
git commit -m "feat(device): 新增设备注册接口骨架" `
  -m "补充注册流程的请求校验与最小控制器实现。" `
  -m "验证：mvn test 通过。" `
  -m "Co-Authored-By: Codex <noreply@openai.com>"
```

PowerShell 的反引号表示续行；若终端或 shell 不支持这种写法，使用 Git 编辑器录入同样的标题、正文和 trailer 即可。关键不在于一行命令多么炫，而在于消息结构、实际验证和 hook 都没有被伪造。

## 七、怎样使用这个 Skill

对有明确影响的 Git 操作，推荐显式调用。它能避免相似的“看看 Git 状态”请求误进入创建分支和 commit 流程。

```text
使用 $git-branch-and-commit：
从 main 创建 feature/auth-token-refresh 分支；
只提交 src/auth 和对应测试，提交前运行 npm test。
不要 push，也不要创建 PR。
```

当用户自然地说“按团队规范为当前改动创建一个 fix 分支并提交”时，只要 `description` 覆盖了该表达，Codex 也可以自动选择这个 Skill。不过关键操作仍要在对话中写清范围，特别是：

- 分支类型与业务模块；
- 哪些文件或改动属于本次提交；
- 应运行哪些验证命令；
- 是否只创建本地 commit；
- 是否有 issue 编号、破坏性影响或既有分支。

| 目标 | 推荐提示 |
| --- | --- |
| 只要建议 | `使用 $git-branch-and-commit 审查当前暂存区，并给出合规分支名和 commit 文案；不要执行 Git 写操作。` |
| 创建本地提交 | `使用 $git-branch-and-commit 为登录超时修复创建 fix/auth-token-expiry 分支，暂存指定文件并创建本地 commit；运行现有测试，不要 push。` |
| 提交前检查 | `使用 $git-branch-and-commit 检查 HEAD 前的暂存改动是否含敏感文件、是否符合提交粒度，并列出需要我确认的项。` |

Skill 完成后应报告分支名、commit SHA、提交摘要、实际运行的检查、未提交文件以及风险。它不会把“没跑测试”写成“测试通过”，也不会把本地 commit 描述成已经上线。

## 八、验证 Skill 本身，而不是只验证它能生成文件

创建完成后，先运行 Skill Creator 提供的基础校验：

```powershell
python <skill-creator路径>\scripts\quick_validate.py `
  "$env:USERPROFILE\.codex\skills\git-branch-and-commit"
```

这能检查 front matter、必填字段和命名规则，却不能证明流程真的安全。还应使用至少三类真实提示做前向测试：

1. **应触发**：请求创建 `feature/device-register-api` 分支并提交已选定的代码和测试。
2. **不应执行写操作**：只要求解释 `git status` 或起草 commit 文案。
3. **应停止并提问**：工作树包含无关改动、`main` 不存在、暂存区含 `.env`，或用户要求 `--no-verify`。

测试时检查的不是答案是否“好看”，而是 Agent 是否读取政策资料、是否没有擅自 stage/push、是否真正执行了它声称的检查、是否在危险场景停下来。这些边界若在测试里守不住，生产任务里只会更糟。

## 九、什么时候修改、禁用或拆分 Skill

团队规范改变时，应先更新 `references/` 中的政策，再审查 `SKILL.md` 是否有冲突；例如默认分支从 `main` 改为 `trunk`、允许的 commit type 调整、AI trailer 规则变化，都会影响核心流程。修改后重新运行校验和前向测试。

若 Skill 暂时不适用于某项目，可以在 Codex 配置中禁用它，而不是直接删除。若团队希望分发给其他人、同时捆绑多项工作流或 MCP 工具，再考虑将它升级为 Plugin。不要为了看起来“工程化”而过早打包；一个经过验证的用户级 Skill 已经能解决绝大多数重复工作。

也应在任务边界变大时拆分。`git-branch-and-commit` 不应悄悄演化成“发布、部署、通知群组”的万能按钮。前者的输入是本地改动和团队 Git 规范，后者还涉及权限、环境、外部服务和不可逆影响，应该有各自独立的确认与审查流程。

## 十、总结

本例将抽象的团队 Git 规范转换成了一个可复用的本地工作流，核心并不在 `git switch -c` 或 `git commit` 这两条命令，而在于把判断与边界写清楚：

- 先定义一个小而稳定的任务：建本地分支与创建本地 commit；
- 用 `description` 写清触发场景和不做什么；
- 将核心流程留在 `SKILL.md`，把团队细则放进按需读取的 `references/`；
- 在任何写操作前检查仓库、工作树、暂存内容和敏感文件；
- 使用选择性暂存、中文 Conventional Commit、实际验证与提交后复核；
- 将 push、PR 和合并作为需要单独授权的后续动作；
- 用格式校验和危险场景测试验证 Skill，而非只看目录是否存在。

当一项流程已经反复发生、能说清输入输出和停止条件，并且有人愿意持续维护它时，它就值得成为 Skill。否则先写一个好 Prompt 或项目 `AGENTS.md` 就够了；不是每段经验都需要立刻被封装成一个目录。
