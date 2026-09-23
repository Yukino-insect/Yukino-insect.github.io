+++
date = '2026-09-23T20:00:59+08:00'
draft = false
title = 'Git Merge 与 Rebase 冲突：如何判断代码来源'
+++

Git 冲突标记看起来很简单，但最容易被误读的恰恰是 `HEAD`：它并不天然代表“我的代码”，只代表**冲突发生时 Git 当前检出的那一侧**。在 `merge` 中，它通常是当前分支；在 `rebase` 中，它通常是作为新基底的上游分支。因此，同一份冲突标记，必须结合正在执行的 Git 操作来判断来源。

本文以最常见的两类情形为主：合并分支时的 `merge` 冲突，以及执行 `git pull origin main --rebase` 时的 `rebase` 冲突。读完后，应该能够回答三个问题：哪一段来自当前分支，哪一段来自被整合的一侧，以及遇到冲突时应如何确认而不是凭印象猜测。

## 一、先读懂冲突标记的结构

Git 无法自动决定同一位置该保留哪种改动时，会把文件改写为类似下面的形式：

```text
<<<<<<< HEAD
冲突上半部分
=======
冲突下半部分
>>>>>>> 来源标识
```

各标记的含义如下：

| 标记 | 含义 |
| --- | --- |
| `<<<<<<< HEAD` | 当前 `HEAD` 一侧的内容开始处 |
| `=======` | 两侧内容的分界线 |
| `>>>>>>> 来源标识` | 另一侧内容结束处；来源标识可能是分支名、远程分支名或提交 SHA |

这套格式描述的是**两侧在当前操作中的角色**，并不直接描述作者，也不直接描述“新”与“旧”。例如，`HEAD` 可以是你的本地功能分支，也可以是远程 `main`；下半部分也可能是同事的提交，也可能正是你自己正在重放的提交。

所以第一条原则是：**不要只看 `HEAD`，先确认当前正在进行 `merge` 还是 `rebase`。**

## 二、用提交图建立正确直觉

假设共同历史为 `A`，`main` 与 `feature` 之后各自都有新提交：

```text
      C -> D  feature
     /
A -> B -> E  main
```

其中：

- `C`、`D` 是功能分支的提交。
- `E` 是 `main` 在分叉后新增的提交。
- 两边都改了同一文件的同一段内容时，整合操作就可能发生冲突。

`merge` 的目标是把两条历史接在一起；`rebase` 的目标则是把 `feature` 的提交复制为新的提交，接到 `main` 最新位置后面。两者的目标不同，导致冲突时 `HEAD` 的含义也不同。

## 三、Merge 冲突：HEAD 是当前检出的分支

### 1. 典型操作与来源判断

先切换到功能分支，再把远程主分支合进来：

```bash
git switch feature
git fetch origin
git merge origin/main
```

冲突文件可能显示：

```text
<<<<<<< HEAD
功能分支 feature 的实现
=======
远程主分支 origin/main 的实现
>>>>>>> origin/main
```

这时的判断很直接：

- `<<<<<<< HEAD` 到 `=======`：来自**当前检出的 `feature` 分支**。
- `=======` 到 `>>>>>>> origin/main`：来自**正在合入的 `origin/main`**。

因为开始执行 `merge` 时，`HEAD` 指向 `feature`。如果角色调换，在 `main` 上执行 `git merge feature`，含义也会随之调换：上半部分是 `main`，下半部分是 `feature`。

### 2. `git pull` 默认 merge 时也是同一规则

不带 `--rebase` 的 `git pull`，可近似理解为先获取远程更新，再将其合并到当前分支：

```bash
git pull origin main
```

若它进入合并冲突，`HEAD` 依然是执行命令前的当前本地分支；下半部分则来自这次拉取后试图合并进来的 `main`。不过，分支名只是线索，真正可靠的是操作状态与提交图。

### 3. merge 的示意图

在 `feature` 分支合并 `main` 时，冲突发生前的逻辑关系是：

```text
HEAD -> feature -> D
                 \
                  merge origin/main 的 E
```

因此 Git 把当前 `HEAD` 所见的内容放在冲突上半部分，把待合入一侧的内容放在下半部分。可以记为：**merge 中，HEAD 是“我当前站着的分支”。**

## 四、Rebase 冲突：HEAD 是新的基底，而非原功能分支

### 1. `git pull origin main --rebase` 到底做了什么

假设你当前在 `feature` 分支，执行：

```bash
git pull origin main --rebase
```

Git 会先取得远程 `main` 的最新提交，然后以该提交为新的基底，把当前 `feature` 中独有的提交依次重放上去。可将其理解为：

```text
rebase 前：

      C -> D  feature
     /
A -> B -> E  origin/main

rebase 后：

A -> B -> E -> C' -> D'  feature
```

`C'`、`D'` 是把原提交 `C`、`D` 重新应用后的新提交，所以它们的提交 SHA 会变化。重放到某一个提交时，若该补丁无法干净地应用，就会暂停并产生冲突。

### 2. 冲突标记的两侧分别是谁

重放 `C` 时，冲突文件可能是：

```text
<<<<<<< HEAD
main 中已有的实现
=======
feature 的提交 C 想要应用的实现
>>>>>>> 7bc57d3 (feat: 优化模型上传展示与个人中心流程)
```

在这个场景中：

- `HEAD` 上半部分来自**当前 rebase 基底一侧**，即远程 `main` 的结果。
- 下半部分来自**正在被重放的那个原功能分支提交**，这里是 `7bc57d3`。

如果 `C` 已经解决并成功重放，接着重放 `D` 又发生冲突，含义会略有变化：

```text
<<<<<<< HEAD
origin/main 的内容，加上已经成功重放的 C'
=======
feature 的提交 D 想要应用的内容
>>>>>>> 84e8039 (fix: ...)
```

此时 `HEAD` 不再是“纯粹的 `origin/main`”，而是**新基底加上此前已成功重放的提交结果**；下半部分仍然只是当前正在重放的那一个旧提交 `D`。这正是连续解决 rebase 冲突时最容易遗漏的细节。

### 3. 为什么会和 merge 的直觉相反

rebase 在冲突期间通常处于临时的 detached `HEAD` 状态。Git 先把 `HEAD` 放到上游分支（这里是最新 `main`）的位置，再尝试把你的某个旧提交应用为一个补丁。

```text
HEAD -> E（上游 main 的最新结果）
          \
           正在应用 C 的补丁
```

因此，冲突上半部分是“补丁要落脚的地方”，下半部分是“当前补丁带来的改动”。可以记成一句话：**rebase 中，HEAD 是“我要落脚的基底”，`>>>>>>> <commit>` 是“我要搬上去的提交”。**

## 五、不要机械套用 ours 与 theirs

Git 还把冲突两侧称作 `ours` 和 `theirs`，但这两个词更容易引起误会。

| 操作 | `ours` / 上半部分 | `theirs` / 下半部分 |
| --- | --- | --- |
| 在 `feature` 执行 `git merge origin/main` | 当前 `feature` | `origin/main` |
| 在 `feature` 执行 `git rebase origin/main` | `origin/main` 及此前已重放的结果 | 当前正在重放的 `feature` 提交 |

也就是说，在 rebase 里，下面的命令语义与不少人的直觉正好相反：

```bash
git checkout --ours -- path/to/file
git checkout --theirs -- path/to/file
```

- `--ours` 取的是当前 `HEAD` 一侧；rebase 时通常就是上游 `main` 的版本。
- `--theirs` 取的是正在重放的本地提交一侧；rebase 时通常才是你原功能分支的改动。

较新的 Git 也可以使用更语义化的 `git restore`：

```bash
git restore --ours -- path/to/file
git restore --theirs -- path/to/file
```

这些命令只适合明确要完整保留某一侧文件时。多数真实冲突需要逐行整合，直接二选一往往会把另一侧有价值的改动一起丢掉。Git 的术语并没有背叛你；只是它从当前操作的视角命名，而不是从你的心理归属感命名。遗憾的是，机器对此从不负责安抚。

## 六、冲突时怎样确认来源，而不是猜

### 1. 先看 Git 当前状态

```bash
git status
```

输出通常会明确显示当前操作，例如：

```text
You are currently merging ...
```

或：

```text
You are currently rebasing branch 'feature' on '...'
```

看到 `merging`，按 merge 的规则理解；看到 `rebasing`，按 rebase 的规则理解。不要在两种语境之间混用结论。

### 2. rebase 时查看正在重放的提交

在 rebase 暂停期间，可以执行：

```bash
git rebase --show-current-patch
git show REBASE_HEAD
```

前者展示当前尝试应用的补丁，后者展示正在重放的原提交。它们能直接验证冲突下半部分究竟要引入什么，而不必仅凭 `>>>>>>>` 后的简短 SHA 猜测。

### 3. 查看三方版本

冲突文件在 Git 的暂存区中通常保留三个阶段：共同祖先、`ours`、`theirs`。可先列出未合并条目：

```bash
git ls-files -u
```

再查看某个文件的三方内容：

```bash
git show :1:path/to/file
git show :2:path/to/file
git show :3:path/to/file
```

其中：

- `:1:` 是双方分叉前的共同祖先，用来判断各自到底改了什么。
- `:2:` 是 `ours`，也就是冲突标记上半部分。
- `:3:` 是 `theirs`，也就是冲突标记下半部分。

阶段编号稳定，但 `ours` 与 `theirs` 的业务来源会随着 merge 或 rebase 而改变。因此，阶段信息能帮助排查，却不能跳过“先确认操作类型”这一步。

### 4. 只查看有哪些文件冲突

```bash
git diff --name-only --diff-filter=U
```

这个命令只列出仍处于未合并状态的文件。先缩小检查范围，再逐个处理，比在一堆普通改动中寻找冲突标记更可靠。

## 七、正确解决冲突的流程

### 1. 处理 merge 冲突

```bash
# 先确认冲突文件和两侧含义
git status

# 手动编辑冲突文件：保留上半、下半、两者组合，或重写为正确结果
# 编辑完成后，删除 <<<<<<<、=======、>>>>>>> 标记

git add path/to/file
git commit
```

如果发现方向错了，或暂时不想继续合并：

```bash
git merge --abort
```

### 2. 处理 rebase 冲突

```bash
# 确认当前正重放哪一个提交
git status
git rebase --show-current-patch

# 手动编辑并删除所有冲突标记
git add path/to/file
git rebase --continue
```

若下一个提交仍有冲突，重复“确认当前提交—编辑—暂存—继续”的步骤。若决定放弃整次变基：

```bash
git rebase --abort
```

`git rebase --skip` 会跳过当前正在重放的提交。它不是“跳过冲突标记”，而是放弃整个提交带来的改动；除非确认该提交已经不需要，否则不应轻易使用。

### 3. 最终内容不等于简单选边

解决冲突的目标不是判断“谁赢”，而是恢复正确的业务行为。对于每个冲突块，通常有四种合法结果：

- 保留上半部分。
- 保留下半部分。
- 合并两边的修改。
- 两边都不保留，改写为新的正确实现。

完成后应至少检查：冲突标记是否全部删除、代码能否编译或通过测试、关键行为是否同时覆盖了两侧改动意图。只执行 `git add .` 然后继续，当然很省事；至于省下的是时间还是思考，结果往往要到之后才知道。

## 八、快速判断表

| 你执行的操作 | `<<<<<<< HEAD` 上半部分 | `=======` 以下部分 |
| --- | --- | --- |
| 当前在 `feature`，执行 `git merge origin/main` | `feature` 当前内容 | `origin/main` 内容 |
| 当前在 `main`，执行 `git merge feature` | `main` 当前内容 | `feature` 内容 |
| 当前在 `feature`，执行 `git rebase origin/main` | `origin/main` 加已成功重放的提交 | 当前正在重放的旧 `feature` 提交 |
| 当前在 `feature`，执行 `git pull origin main --rebase` | 拉取到的 `main` 基底，加已成功重放的提交 | 当前正在重放的旧 `feature` 提交 |

最后把规则压缩为两句即可：

- **merge 冲突中，HEAD 是当前分支；下半部分是被合并进来的那一侧。**
- **rebase 冲突中，HEAD 是新基底；下半部分是当前正在被重放的提交。**

如果仍然没有把握，执行 `git status` 确认操作类型；在 rebase 中再用 `git rebase --show-current-patch` 检查当前提交。比起记住一句可能被错误套用的口诀，理解 Git 此刻正试图完成什么，才是不会失效的判断方式。

有关分支、提交、`merge`、`rebase` 等基础概念，可继续阅读 [Git 常用命令与核心原理](Git 常用命令与核心原理.md)。
