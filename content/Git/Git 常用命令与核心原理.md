+++
date = '2026-03-17T21:42:58+08:00'
draft = false
title = 'Git 常用命令与核心原理'
+++

这篇文章整理 Git 的常用命令、典型工作流，以及一些必须知道的底层概念。Git 的命令并不难，真正容易让人混乱的是：同一个命令在修改 **工作区**、**暂存区**、**本地仓库** 还是 **远程分支**。

先记住一句话：Git 不是简单地保存“文件变化”，而是在本地维护一套由提交对象串起来的历史。你平时执行的 `add`、`commit`、`merge`、`rebase`、`reset`，本质都是在移动指针、生成对象、更新索引或修改工作区。

## 一、先建立整体认知

### 1. Git 管理的三个区域

日常使用 Git 时，最重要的是分清下面三个区域：

| 区域 | 英文 | 作用 |
| --- | --- | --- |
| 工作区 | Working Tree | 你正在编辑的项目文件 |
| 暂存区 | Index / Staging Area | 下一次提交准备包含的内容 |
| 本地仓库 | Repository | 已经提交的历史记录 |

常见流程如下：

```text
修改文件
 -> git add
 -> 暂存区
 -> git commit
 -> 本地仓库
 -> git push
 -> 远程仓库
```

所以，`git add` 不是“保存到仓库”，而是把改动放进暂存区；`git commit` 才是生成一次本地提交。

### 2. Git 的底层对象

Git 的底层可以理解为一个 **内容寻址的对象数据库**。对象通常保存在 `.git/objects` 中，并用内容哈希作为地址。

Git 主要有四类对象：

| 对象 | 作用 |
| --- | --- |
| `blob` | 保存文件内容，不保存文件名 |
| `tree` | 保存目录结构、文件名、权限，并指向 `blob` 或子 `tree` |
| `commit` | 保存一次提交的信息，指向一个 `tree`，并记录父提交 |
| `tag` | 给某个提交或对象起一个固定名字 |

一次 `commit` 里通常记录这些信息：

- 当前项目快照对应的 `tree`
- 父提交的哈希
- 作者、提交者、时间
- 提交说明

Git 把文件内容和目录结构分开存储，带来了两个好处：

- 相同内容只需要保存一份 `blob`，天然去重。
- 文件重命名时，如果内容没变，底层主要只是 `tree` 里的路径映射变了。

### 3. 分支和 HEAD

分支并不是一份完整代码。分支本质上只是一个指向某次提交的引用。

```text
main    -> A
dev     -> C
HEAD    -> dev
```

可以把它理解为：

- `main` 指向某个提交。
- `dev` 指向另一个提交。
- `HEAD` 表示你当前站在哪里，通常指向当前分支。

当你在 `dev` 分支执行一次新的提交后：

```text
提交前：dev -> C
提交后：dev -> D
HEAD 仍然指向 dev
```

也就是说，提交会让当前分支向前移动。

刚 `git init` 的仓库没有任何提交，此时分支可能处于 `unborn branch` 状态。这个时候 `HEAD` 只是记录“当前准备叫哪个分支”，但还没有真正的提交可指向，所以 `git branch` 可能什么都不显示。等第一次 `commit` 完成后，分支引用才真正落到一个提交上。

## 二、初始化与配置

### 1. 初始化仓库

在项目根目录执行：

```bash
git init
```

执行后会生成 `.git` 目录。这个目录保存了 Git 的对象、引用、配置、索引等信息。平时不要手动改 `.git`，除非你很清楚自己在做什么。

### 2. 配置用户名和邮箱

第一次使用 Git 时，建议先配置：

```bash
git config --global user.name "your-name"
git config --global user.email "your-email@example.com"
```

查看当前配置：

```bash
git config --list
```

如果只想给当前仓库配置用户名或邮箱，就去掉 `--global`：

```bash
git config user.name "work-name"
git config user.email "work-email@example.com"
```

### 3. 设置默认分支名

现在很多仓库使用 `main` 作为默认分支。如果希望以后新建仓库默认使用 `main`：

```bash
git config --global init.defaultBranch main
```

## 三、查看状态与差异

### 1. 查看仓库状态

```bash
git status
```

这个命令会告诉你：

- 当前所在分支。
- 哪些文件被修改了。
- 哪些文件已经暂存。
- 哪些文件还没有被 Git 跟踪。
- 当前分支和远程分支是否有领先或落后的提交。

如果想看更简洁的输出：

```bash
git status -sb
```

### 2. 查看工作区差异

查看工作区中尚未暂存的改动：

```bash
git diff
```

查看已经暂存、准备提交的改动：

```bash
git diff --staged
```

查看两个提交之间的差异：

```bash
git diff <commit-a> <commit-b>
```

查看某个文件在两个提交之间的差异：

```bash
git diff <commit-a> <commit-b> -- path/to/file
```

`git diff` 是非常值得经常用的命令。提交之前看一眼差异，比提交之后再后悔要体面得多。

## 四、添加与提交

### 1. 添加到暂存区

添加某个文件：

```bash
git add path/to/file
```

添加某个目录：

```bash
git add path/to/directory
```

添加当前目录下所有变化：

```bash
git add .
```

`git add .` 很方便，但也很容易把调试文件、临时文件一起加进去。提交前建议执行：

```bash
git status
git diff --staged
```

如果想交互式地选择部分改动：

```bash
git add -p
```

`git add -p` 很适合把一个文件里的多处修改拆成多次提交。

### 2. 提交修改

```bash
git commit -m "提交说明"
```

提交说明应该写清楚“这次提交做了什么”，例如：

```bash
git commit -m "fix login redirect after session expired"
```

不太推荐这种说明：

```bash
git commit -m "update"
git commit -m "fix"
git commit -m "改一下"
```

不是因为它们不合法，而是三天之后你自己看了也未必知道当初改了什么。人的记忆力没那么可靠，没必要为难未来的自己。

### 3. 修改最近一次提交

如果刚提交完发现漏了一个文件，可以先补充暂存：

```bash
git add path/to/file
```

然后修改最近一次提交：

```bash
git commit --amend
```

如果只想修改提交说明：

```bash
git commit --amend -m "新的提交说明"
```

注意：如果这次提交已经推送到公共远程分支，使用 `--amend` 会改写提交历史，需要谨慎。

## 五、查看提交历史

### 1. 基础查看

查看完整提交历史：

```bash
git log
```

查看简洁历史：

```bash
git log --oneline
```

查看带分支图的历史：

```bash
git log --oneline --graph --decorate --all
```

### 2. 查看某个提交

```bash
git show <commit-hash>
```

这个命令会显示某次提交的说明、作者、时间和具体改动。

### 3. 查看分支之间的差异

查看 `dev-han` 比 `origin/main` 多了哪些提交：

```bash
git log origin/main..dev-han --oneline
```

查看当前分支还没有推送到远程的提交：

```bash
git log @{u}..HEAD --oneline
```

这里的 `@{u}` 表示当前分支的上游分支，也就是 upstream。

## 六、分支操作

### 1. 查看分支

查看本地分支：

```bash
git branch
```

查看当前分支名：

```bash
git branch --show-current
```

查看本地和远程分支：

```bash
git branch -a
```

### 2. 创建和切换分支

创建分支但不切换：

```bash
git branch dev-han
```

切换到已有分支：

```bash
git switch dev-han
```

创建并切换到新分支：

```bash
git switch -c dev-han
```

旧命令也可以这样写：

```bash
git checkout -b dev-han
```

现在更推荐使用 `git switch` 处理分支切换，因为它的语义更清楚。

### 3. 删除分支

删除已经合并过的本地分支：

```bash
git branch -d dev-han
```

强制删除本地分支：

```bash
git branch -D dev-han
```

删除远程分支：

```bash
git push origin --delete dev-han
```

`-D` 会忽略“是否已合并”的保护，请确认分支上的提交不再需要。

## 七、撤销与恢复

Git 的撤销命令最容易误用。先问自己一个问题：你要撤销的是 **工作区**、**暂存区**，还是 **提交历史**？

### 1. 取消暂存

文件已经 `git add`，但还没 `commit`，想从暂存区拿出来：

```bash
git restore --staged path/to/file
```

这只会取消暂存，不会删除工作区里的修改。

### 2. 丢弃工作区修改

丢弃某个文件尚未暂存的修改：

```bash
git restore path/to/file
```

这会让文件恢复到当前 `HEAD` 或暂存区记录的状态。工作区修改会丢失，请确认你真的不要了。

### 3. 从某个提交恢复文件

把某个文件恢复到指定提交时的版本：

```bash
git restore --source=<commit-hash> -- path/to/file
```

旧写法是：

```bash
git checkout <commit-hash> -- path/to/file
```

### 4. reset 的三种模式

假设当前历史是：

```text
A -> B -> C
```

现在当前分支指向 `C`，如果执行：

```bash
git reset --soft B
```

效果是：

- 分支指针回到 `B`。
- 暂存区保留 `C` 相对于 `B` 的改动。
- 工作区保留当前文件内容。

如果执行：

```bash
git reset --mixed B
```

效果是：

- 分支指针回到 `B`。
- 暂存区回到 `B`。
- 工作区保留当前文件内容。

`--mixed` 是默认模式，所以 `git reset B` 等价于 `git reset --mixed B`。

如果执行：

```bash
git reset --hard B
```

效果是：

- 分支指针回到 `B`。
- 暂存区回到 `B`。
- 工作区也回到 `B`。

`--hard` 会丢弃工作区和暂存区中的修改。除非你确定这些改动不需要，否则不要随手执行。

### 5. revert：生成反向提交

如果某个错误提交已经推送到共享分支，更推荐使用 `git revert`：

```bash
git revert <commit-hash>
```

`revert` 不会删除历史，而是生成一个新的提交，用来抵消指定提交的修改。公共分支上更适合这种方式，因为它不会改写别人已经基于它开发的历史。

### 6. reflog：找回刚刚丢掉的提交

如果你不小心 `reset --hard` 到了错误位置，可以先看：

```bash
git reflog
```

`reflog` 会记录 `HEAD` 和分支指针最近移动过的位置。找到需要恢复的提交后，可以执行：

```bash
git reset --hard <commit-hash>
```

`reflog` 是本地记录，不会同步到远程。它经常能救急，但别把“能救急”理解成“可以随便乱来”，这两件事的逻辑关系并不存在。

## 八、临时保存现场：stash

如果当前分支有未提交修改，但你需要临时切换分支、拉取代码或处理紧急问题，可以使用 `stash`。

### 1. 保存当前修改

保存已跟踪文件的修改：

```bash
git stash push -m "work in progress"
```

简写也可以：

```bash
git stash -m "work in progress"
```

保存未跟踪文件：

```bash
git stash push -u -m "include untracked files"
```

默认情况下，`stash` 不会保存未跟踪文件。新增文件如果还没有被 Git 跟踪，记得加 `-u`。

### 2. 查看和恢复 stash

查看所有 stash：

```bash
git stash list
```

查看某个 stash 的内容：

```bash
git stash show -p stash@{0}
```

应用某个 stash，但保留记录：

```bash
git stash apply stash@{0}
```

应用并删除某个 stash：

```bash
git stash pop stash@{0}
```

删除某个 stash：

```bash
git stash drop stash@{0}
```

清空所有 stash：

```bash
git stash clear
```

`stash` 可以理解成一个栈，新的记录会放在 `stash@{0}`。但恢复时仍然可能发生冲突，因为你保存时的文件状态和当前分支的文件状态可能已经不同。

## 九、远程仓库与 GitHub

Git 可以只在本地使用，但团队协作通常会配合 GitHub、GitLab、Gitee 等远程平台。

### 1. 添加远程仓库

使用 HTTPS：

```bash
git remote add origin https://github.com/<user>/<repo>.git
```

使用 SSH：

```bash
git remote add origin git@github.com:<user>/<repo>.git
```

查看远程仓库：

```bash
git remote -v
```

修改远程地址：

```bash
git remote set-url origin git@github.com:<user>/<repo>.git
```

### 2. 推送代码

第一次推送并建立上游关系：

```bash
git push -u origin main
```

之后在当前分支推送：

```bash
git push
```

`-u` 的意思是设置 upstream。设置后，Git 就知道当前本地分支对应哪个远程分支。

### 3. 拉取代码

常见写法：

```bash
git pull origin main
```

如果当前分支已经设置 upstream，可以直接：

```bash
git pull
```

需要注意：`git pull` 不是一个单纯的“下载”命令，它大致等于：

```text
git fetch
git merge
```

也就是说，`pull` 会拉取远程更新，并尝试合并到当前分支。

### 4. fetch 和 pull 的区别

只下载远程更新，不自动合并：

```bash
git fetch origin
```

下载后可以查看远程分支：

```bash
git branch -r
```

也可以比较本地分支和远程分支：

```bash
git log HEAD..origin/main --oneline
git diff HEAD origin/main
```

`fetch` 更稳，因为它只更新远程跟踪分支，不会直接动你的当前工作分支。想看清楚远程发生了什么时，先 `fetch`，再决定 `merge` 或 `rebase`。

### 5. 克隆仓库

```bash
git clone git@github.com:<user>/<repo>.git
```

克隆指定分支：

```bash
git clone -b main git@github.com:<user>/<repo>.git
```

## 十、合并、冲突与 rebase

### 1. merge 合并分支

如果你在 `main` 分支，想把 `dev-han` 合并进来：

```bash
git switch main
git merge dev-han
```

如果两个分支修改了同一文件的同一区域，就可能产生冲突。

冲突文件中通常会出现下面这种结构。示例里用方括号包了一层，真实文件里没有这层方括号：

```text
[<<<<<<< HEAD]
当前分支的内容
[=======]
被合并分支的内容
[>>>>>>> dev-han]
```

解决冲突时，需要手动保留正确内容，并删除这些冲突标记。然后执行：

```bash
git add .
git commit
```

如果想中止本次 merge：

```bash
git merge --abort
```

### 2. rebase 变基

假设当前在 `feature` 分支，想把它的提交挪到 `main` 最新提交之后：

```bash
git switch feature
git rebase main
```

直观理解：

```text
rebase 前：

      C -> D  feature
     /
A -> B        main

rebase 后：

A -> B        main
     \
      C' -> D' feature
```

`rebase` 会重放提交，因此会生成新的提交哈希。

发生冲突后，解决文件冲突，再执行：

```bash
git add .
git rebase --continue
```

如果想中止本次 rebase：

```bash
git rebase --abort
```

### 3. merge 和 rebase 怎么选

| 场景 | 推荐 |
| --- | --- |
| 合并公共分支、保留真实分支历史 | `merge` |
| 整理自己本地尚未共享的提交 | `rebase` |
| 已经推送给别人基于它开发的分支 | 不要随意 `rebase` |
| 想让提交历史更线性 | 可以考虑 `rebase` |

一句朴素的规则：自己的本地提交可以整理，大家共享的历史不要随便改写。

### 4. pull 时使用 rebase

默认 `git pull` 通常会用 merge 方式整合远程更新。如果想用 rebase：

```bash
git pull --rebase
```

也可以设置当前仓库默认 pull 时使用 rebase：

```bash
git config pull.rebase true
```

是否设置为默认，看团队规范。团队已有约定时，先遵守约定。

## 十一、远程跟踪分支

远程跟踪分支是本地用来记录远程分支状态的引用，例如：

```text
origin/main
origin/dev-han
```

它们不是远程仓库里的真实分支，而是你本地对远程状态的一份记录。执行 `git fetch` 后，这些引用会更新。

本地分支和远程跟踪分支可以建立 upstream 关系：

```bash
git branch --set-upstream-to=origin/main main
```

查看每个本地分支对应的 upstream：

```bash
git branch -vv
```

如果你在当前分支设置过 upstream，那么很多命令可以省略远程名和分支名：

```bash
git pull
git push
git log @{u}..HEAD --oneline
```

## 十二、标签 tag

标签通常用来标记版本，例如 `v1.0.0`。

创建轻量标签：

```bash
git tag v1.0.0
```

创建带说明的标签：

```bash
git tag -a v1.0.0 -m "release v1.0.0"
```

查看标签：

```bash
git tag
```

推送某个标签：

```bash
git push origin v1.0.0
```

推送所有标签：

```bash
git push origin --tags
```

删除本地标签：

```bash
git tag -d v1.0.0
```

删除远程标签：

```bash
git push origin --delete v1.0.0
```

项目发布版本时，标签比“记住某个 commit hash”更适合长期使用。

## 十三、忽略文件

不希望被 Git 跟踪的文件，可以写到 `.gitignore`：

```text
node_modules/
dist/
.env
*.log
```

注意：`.gitignore` 只对 **尚未被 Git 跟踪** 的文件生效。

如果某个文件已经被提交过，后来才加入 `.gitignore`，需要先从 Git 索引中移除：

```bash
git rm --cached path/to/file
```

如果是目录：

```bash
git rm -r --cached path/to/directory
```

这只会让 Git 不再跟踪它，不会删除你工作区里的实际文件。

## 十四、git worktree

默认情况下，同一个仓库只有一个工作区和一个暂存区。多个分支虽然历史不同，但你切换分支时，操作的仍然是同一个目录。

如果你想同时打开多个分支，可以使用 `git worktree`。

例如当前仓库在 `blog` 目录，想给 `fix-login` 分支创建一个独立工作区：

```bash
git worktree add ../blog-fix-login fix-login
```

如果分支还不存在，可以创建并挂载：

```bash
git worktree add -b fix-login ../blog-fix-login main
```

查看 worktree：

```bash
git worktree list
```

删除某个 worktree：

```bash
git worktree remove ../blog-fix-login
```

`worktree` 适合这些场景：

- 当前开发没做完，但需要紧急切到另一个分支修问题。
- 想同时跑两个分支做对比。
- 不想频繁 `stash` 和切换分支。

## 十五、常见工作流

### 1. 新功能开发

```bash
git switch main
git pull
git switch -c feature-login

# 修改代码
git status
git diff
git add .
git commit -m "add login page"

git push -u origin feature-login
```

然后在 GitHub 或 GitLab 上创建 Pull Request / Merge Request。

### 2. 修复线上问题

```bash
git switch main
git pull
git switch -c fix-login-redirect

# 修改代码
git add .
git commit -m "fix login redirect"

git push -u origin fix-login-redirect
```

如果当前分支有未完成内容，可以先：

```bash
git stash push -u -m "save current work"
```

修完问题后再回到原分支：

```bash
git switch original-branch
git stash pop
```

### 3. 同步 main 的最新代码

方式一，使用 merge：

```bash
git switch feature-login
git fetch origin
git merge origin/main
```

方式二，使用 rebase：

```bash
git switch feature-login
git fetch origin
git rebase origin/main
```

团队协作中选哪一种，最好跟团队规范保持一致。工具本身没有道德立场，人乱用才会出问题。

## 十六、命令速查表

| 目的 | 命令 |
| --- | --- |
| 查看状态 | `git status -sb` |
| 查看未暂存差异 | `git diff` |
| 查看已暂存差异 | `git diff --staged` |
| 添加全部改动 | `git add .` |
| 交互式添加 | `git add -p` |
| 提交 | `git commit -m "message"` |
| 修改最近一次提交 | `git commit --amend` |
| 查看简洁历史 | `git log --oneline --graph --decorate --all` |
| 创建并切换分支 | `git switch -c branch-name` |
| 切换分支 | `git switch branch-name` |
| 删除本地分支 | `git branch -d branch-name` |
| 保存现场 | `git stash push -u -m "message"` |
| 恢复现场 | `git stash pop` |
| 拉取远程更新 | `git pull` |
| 只获取远程更新 | `git fetch origin` |
| 推送当前分支 | `git push` |
| 合并分支 | `git merge branch-name` |
| 变基 | `git rebase branch-name` |
| 取消暂存 | `git restore --staged path/to/file` |
| 丢弃工作区修改 | `git restore path/to/file` |
| 查看引用移动记录 | `git reflog` |
| 创建标签 | `git tag -a v1.0.0 -m "release v1.0.0"` |

## 十七、一些使用建议

- 提交前先看 `git status` 和 `git diff --staged`。
- 一个提交尽量只做一件事，不要把格式化、重构、功能开发、修 bug 全塞进同一次提交。
- 公共分支上优先用 `revert` 撤销错误提交，不要随意 `reset --hard` 后强推。
- `rebase` 适合整理自己的本地提交，不适合随便改写别人已经依赖的历史。
- 遇到冲突不要慌，先看冲突文件，再决定保留哪一边或如何合并。
- 不确定命令会不会破坏工作区时，先执行 `git status`，必要时先 `git stash push -u -m "backup"`。
- 遇到“提交不见了”的情况，先看 `git reflog`。

Git 的核心其实很朴素：文件内容变成对象，提交串成历史，分支只是指针，`HEAD` 表示当前位置。把这几件事想明白，再看命令就不会觉得它是在随机发脾气了。
