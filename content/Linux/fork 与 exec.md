+++
date = '2026-08-18T00:00:00+08:00'
draft = false
title = 'fork 与 exec'
+++

在 Linux 里谈进程创建时，经常会听到两个词：`fork` 和 `exec`。

很多初学者会把它们理解成“两个命令”，但严格来说：

- `fork()` 是一个系统调用，用来创建子进程
- `exec` 是一族系统调用，用来把当前进程替换成另一个程序

它们不是普通意义上的 shell 命令。我们平时在命令行里输入：

```bash
ls
```

背后其实大致就是 shell 先 `fork()` 出一个子进程，然后在子进程里用 `exec()` 加载 `ls` 这个程序。

这篇文章就围绕几个问题展开：

- `fork()` 到底做了什么？
- `fork()` 只能在 Linux 上用吗？
- 为什么 `fork()` 之后父子进程要靠返回值区分身份？
- 把父进程和子进程逻辑写在一起会不会很冗余？
- `exec()` 和 `fork()` 是什么关系？

------

## 一、初识 fork

`fork` 是操作系统提供给程序使用的系统调用。

在 C 语言里，它的函数原型大致是：

```c
#include <unistd.h>

pid_t fork(void);
```

调用它之后，操作系统会创建一个新的进程。这个新进程叫做**子进程**，原来的进程叫做**父进程**。

最让人感到别扭的地方是：

**`fork()` 调用一次，却会返回两次。**

这句话不是修辞，而是事实。

一次 `fork()` 之后，会出现两个几乎一模一样的进程：

- 父进程从 `fork()` 返回
- 子进程也从 `fork()` 返回

它们都会继续执行 `fork()` 之后的代码。

所以程序必须通过 `fork()` 的返回值判断：

```text
我现在到底是父进程，还是子进程？
```

------

## 二、fork 的返回值

`fork()` 的返回值有三种情况：

| 返回值 | 所在进程 | 含义 |
| --- | --- | --- |
| `> 0` | 父进程 | 返回的是子进程的 PID |
| `== 0` | 子进程 | 表示当前正在子进程中 |
| `< 0` | 父进程 | 创建子进程失败 |

也就是说：

**返回 `0` 的是子进程，返回子进程 PID 的是父进程。**

这点不能写反。写反之后程序还是可能运行，但逻辑会像扣错第一颗扣子一样，一路错得很自然。

来看一个最小例子。

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>

int main(void) {
    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        printf("child: pid=%d, parent pid=%d\n", getpid(), getppid());
    } else {
        printf("parent: pid=%d, child pid=%d\n", getpid(), pid);
    }

    return 0;
}
```

编译运行：

```bash
gcc fork-basic.c -o fork-basic
./fork-basic
```

可能输出：

```text
parent: pid=12001, child pid=12002
child: pid=12002, parent pid=12001
```

也可能先输出子进程，再输出父进程。这取决于操作系统调度，不能假设父进程一定先执行。

------

## 三、fork 创建的是“程序副本”吗？

可以这么理解，但要稍微精确一点。

`fork()` 创建子进程时，子进程会获得父进程的许多资源副本，包括：

- 当前代码执行位置
- 变量值
- 打开的文件描述符
- 环境变量
- 当前工作目录
- 信号处理设置
- 用户 ID、组 ID 等进程属性

从程序视角看，子进程像是父进程在 `fork()` 那一刻的复制品。

不过现代 Linux 并不会真的立刻把父进程的所有内存完整复制一份。那样太浪费。

Linux 通常使用 **写时复制**，也就是 Copy-On-Write，简称 COW。

它的大致意思是：

- `fork()` 刚发生时，父子进程可以共享同一批物理内存页
- 只要双方都只是读取，就不复制
- 一旦某个进程要修改某页内存，内核才真正复制那一页

所以 `fork()` 在现代系统上并不像“立刻完整拷贝一个大程序”那么笨重。操作系统毕竟不至于这么勤劳地浪费力气。

看一个变量复制的例子。

```c
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main(void) {
    int value = 100;

    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        value = 200;
        printf("child: value=%d, address=%p\n", value, (void *)&value);
    } else {
        wait(NULL);
        printf("parent: value=%d, address=%p\n", value, (void *)&value);
    }

    return 0;
}
```

编译运行：

```bash
gcc fork-variable.c -o fork-variable
./fork-variable
```

可能输出：

```text
child: value=200, address=0x7ffd6e63b2ac
parent: value=100, address=0x7ffd6e63b2ac
```

这里有个现象很有意思：

- 父子进程里变量地址看起来可能一样
- 但子进程修改 `value` 不会影响父进程

原因是这个地址是**虚拟地址**。父子进程有各自独立的虚拟地址空间，即使虚拟地址数值相同，最终映射到的物理内存也可以不同。

------

## 四、fork 只能在 Linux 上执行吗？

不是只有 Linux 才有 `fork()`。

更准确地说：

**`fork()` 是 Unix / POSIX 系统里的经典进程创建接口。**

常见支持或接近支持 `fork()` 的系统包括：

- Linux
- macOS
- BSD 系列系统
- 其他 Unix / 类 Unix 系统

但 Windows 原生 API 里没有完全等价的 `fork()`。

Windows 创建进程常用的是 `CreateProcess()`。它的模型更接近：

```text
直接创建一个新进程，并指定它要运行哪个程序
```

而不是：

```text
先复制当前进程，再在子进程里替换程序
```

当然，在 Windows 上也可能通过一些兼容层或环境间接使用类似 `fork()` 的能力，比如：

- WSL，也就是 Windows Subsystem for Linux
- Cygwin
- MSYS2

但那不是普通 Win32 程序天然拥有的 `fork()` 语义。

所以简单总结：

```text
Linux 支持 fork()
Unix / POSIX 系统通常支持 fork()
Windows 原生不提供真正同语义的 fork()
```

------

## 五、父子进程逻辑写在一起，会不会很冗余？

这是一个很自然的问题。

`fork()` 之后，父子进程从同一个代码位置继续执行，因此代码常常会写成这样：

```c
pid_t pid = fork();

if (pid == 0) {
    // child task
} else {
    // parent task
}
```

看起来确实像把两个程序的任务塞进了一个文件里。

但这不一定是冗余，要看场景。

如果父子进程做的是同一个程序内部的不同分工，比如：

- 父进程继续监听请求
- 子进程处理某个连接
- 父进程负责调度任务
- 子进程负责执行任务

那么写在同一个程序里是合理的。

例如一个非常简化的并发处理模型：

```c
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

void handle_job(int job_id) {
    printf("child %d handling job %d\n", getpid(), job_id);
    sleep(1);
    printf("child %d finished job %d\n", getpid(), job_id);
}

int main(void) {
    for (int i = 1; i <= 3; i++) {
        pid_t pid = fork();

        if (pid < 0) {
            perror("fork");
            return 1;
        }

        if (pid == 0) {
            handle_job(i);
            return 0;
        }
    }

    while (wait(NULL) > 0) {
        // wait for all child processes
    }

    printf("parent %d: all jobs finished\n", getpid());
    return 0;
}
```

编译运行：

```bash
gcc fork-jobs.c -o fork-jobs
./fork-jobs
```

这个程序里，父进程负责创建子进程并等待它们结束，子进程负责处理具体任务。逻辑虽然在一个程序中，但职责并不混乱。

不过，如果子进程要执行的是完全不同的程序，比如：

- 运行 `ls`
- 执行 `python script.py`
- 调用 `grep`
- 启动另一个服务程序

那就没有必要把另一个程序的全部逻辑写进当前程序。

这时就该轮到 `exec()` 了。

------

## 六、exec 的作用：替换当前进程的程序

`exec` 不是单独一个函数，而是一族函数。

常见的有：

- `execl()`
- `execlp()`
- `execv()`
- `execvp()`
- `execve()`

它们细节不同，但核心作用一样：

**把当前进程的程序镜像替换成另一个程序。**

注意这个说法：

```text
替换当前进程
```

不是：

```text
创建一个新进程
```

`exec()` 本身不会创建新进程。它只是在当前进程里加载另一个程序，把原来的代码、数据、堆、栈等内容替换掉。

如果 `exec()` 成功，它后面的代码不会继续执行。

看一个例子：

```c
#include <stdio.h>
#include <unistd.h>

int main(void) {
    printf("before exec\n");

    execlp("ls", "ls", "-l", NULL);

    perror("execlp");
    return 1;
}
```

编译运行：

```bash
gcc exec-basic.c -o exec-basic
./exec-basic
```

你会看到它输出 `before exec`，然后执行 `ls -l`。

如果 `execlp("ls", "ls", "-l", NULL)` 成功，那么下面这两行不会执行：

```c
perror("execlp");
return 1;
```

只有当 `exec()` 失败时，比如找不到程序、没有执行权限，才会返回到原程序继续执行错误处理代码。

------

## 七、fork + exec：Unix 创建新程序的经典组合

现在问题来了：

- `fork()` 会创建子进程，但子进程还是当前程序的副本
- `exec()` 能加载新程序，但它不会创建新进程

那么如果我想“启动另一个程序，同时父进程继续运行”，该怎么办？

答案就是：

```text
fork() + exec()
```

典型流程是：

1. 父进程调用 `fork()` 创建子进程
2. 子进程调用 `exec()` 替换成另一个程序
3. 父进程继续执行自己的逻辑，必要时调用 `wait()` 等待子进程结束

示例：

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main(void) {
    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        printf("child: about to run ls\n");
        execlp("ls", "ls", "-l", NULL);

        perror("execlp");
        _exit(127);
    }

    printf("parent: created child process %d\n", pid);

    int status;
    if (waitpid(pid, &status, 0) < 0) {
        perror("waitpid");
        return 1;
    }

    if (WIFEXITED(status)) {
        printf("parent: child exited with code %d\n", WEXITSTATUS(status));
    } else if (WIFSIGNALED(status)) {
        printf("parent: child killed by signal %d\n", WTERMSIG(status));
    }

    return 0;
}
```

编译运行：

```bash
gcc fork-exec.c -o fork-exec
./fork-exec
```

这里子进程原本是当前程序的副本，但它马上调用：

```c
execlp("ls", "ls", "-l", NULL);
```

于是子进程被替换成了 `ls` 程序。

父进程不会被替换，它仍然是原来的程序，可以继续等待子进程结束，并检查退出状态。

这正是 shell 执行外部命令时常用的基本模型。

------

## 八、为什么 exec 的参数里有两个 ls？

很多人第一次看到这句会疑惑：

```c
execlp("ls", "ls", "-l", NULL);
```

为什么有两个 `"ls"`？

第一个 `"ls"`：

```c
execlp("ls", ...)
```

表示要查找并执行的程序名。因为用的是 `execlp()`，所以它会根据 `PATH` 环境变量搜索 `ls`。

第二个 `"ls"`：

```c
..., "ls", "-l", NULL
```

是传给新程序的 `argv[0]`。

也就是说，新程序看到的参数大致是：

```c
argv[0] = "ls";
argv[1] = "-l";
argv[2] = NULL;
```

最后的 `NULL` 表示参数列表结束，不能省略。

所以这句完整含义是：

```text
在 PATH 里查找 ls 程序，并用 argv = ["ls", "-l"] 启动它
```

------

## 九、exec 成功后为什么要用 _exit？

在 `fork + exec` 的子进程里，经常会看到这种写法：

```c
if (pid == 0) {
    execlp("ls", "ls", "-l", NULL);
    perror("execlp");
    _exit(127);
}
```

这里的 `_exit(127)` 只会在 `execlp()` 失败时执行。

为什么不用 `return 1` 或 `exit(1)`？

原因是：子进程是从父进程 `fork()` 出来的，它继承了父进程的一些 C 标准库状态，比如缓冲区。直接调用 `exit()` 可能触发标准库清理逻辑，导致某些缓冲内容被重复刷新。

而 `_exit()` 会更直接地结束当前进程，不做那些用户态标准库清理工作。在 `fork()` 后、`exec()` 前的子进程错误分支里，用 `_exit()` 通常更稳妥。

退出码 `127` 也不是随便写的。在 shell 语义里，`127` 常用来表示命令未找到或无法执行。

------

## 十、父进程为什么要 wait？

如果父进程创建了子进程，却不等待它结束，就可能产生僵尸进程。

当子进程结束时，内核还会暂时保存它的一些退出信息，比如：

- 退出码
- 被哪个信号终止
- 资源使用情况

父进程需要通过 `wait()` 或 `waitpid()` 读取这些信息。读取之后，内核才能彻底回收子进程残留的进程表项。

一个最简单的等待写法：

```c
wait(NULL);
```

更推荐在知道子进程 PID 时使用：

```c
waitpid(pid, &status, 0);
```

这样可以明确等待某一个子进程，而不是随便等任意一个子进程。

------

## 十一、fork 和 exec 的分工

可以把两者关系总结成一句话：

**`fork()` 负责复制出一个新进程，`exec()` 负责把这个进程换成新程序。**

更具体一点：

| 操作 | 是否创建新进程 | 是否替换当前程序 | 成功后是否返回 |
| --- | --- | --- | --- |
| `fork()` | 是 | 否 | 父子进程都会返回 |
| `exec()` | 否 | 是 | 成功后不返回 |
| `fork() + exec()` | 是 | 子进程被替换 | 父进程继续，子进程变成新程序 |

这也是为什么它们常常一起出现。

如果只是想让当前进程变成另一个程序，可以只用 `exec()`。

如果想创建一个子进程执行同一份代码，可以只用 `fork()`。

如果想启动另一个外部程序，同时原进程继续存在，就用 `fork() + exec()`。

------

## 十二、再看“冗余”的问题

把父子进程任务写在一起，确实可能让代码变得复杂。

但这不是 `fork()` 本身的问题，而是代码组织方式的问题。

如果父子进程只是同一个程序的不同分支，可以拆成函数：

```c
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

void run_child(void) {
    printf("child: do child work\n");
}

void run_parent(pid_t child_pid) {
    printf("parent: child pid is %d\n", child_pid);
    waitpid(child_pid, NULL, 0);
}

int main(void) {
    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        run_child();
        return 0;
    }

    run_parent(pid);
    return 0;
}
```

这样父子逻辑虽然还在同一个程序里，但结构已经清楚很多。

如果子进程要做的是另一个独立任务，就让它成为另一个可执行程序，然后使用 `exec()`：

```c
if (pid == 0) {
    execlp("python3", "python3", "worker.py", NULL);
    perror("execlp");
    _exit(127);
}
```

这时当前程序只负责调度，具体任务交给 `worker.py`。这就不是把两个程序硬塞在一起，而是父进程启动另一个程序。

所以结论是：

```text
fork 后用 if 区分父子进程，是进程模型要求的写法；
业务逻辑是否冗余，取决于你是否合理拆分函数、模块或外部程序。
```

------

## 十三、一个接近 shell 的小例子

最后写一个更接近 shell 执行命令的例子。它读取用户输入的命令，然后 `fork()` 子进程执行。

为了简单，只支持一个命令和一个参数。

```c
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main(void) {
    char command[64];
    char arg[64];

    printf("command: ");
    if (scanf("%63s", command) != 1) {
        return 1;
    }

    printf("arg: ");
    if (scanf("%63s", arg) != 1) {
        arg[0] = '\0';
    }

    pid_t pid = fork();

    if (pid < 0) {
        perror("fork");
        return 1;
    }

    if (pid == 0) {
        if (arg[0] == '\0') {
            execlp(command, command, NULL);
        } else {
            execlp(command, command, arg, NULL);
        }

        perror("execlp");
        _exit(127);
    }

    int status;
    waitpid(pid, &status, 0);

    if (WIFEXITED(status)) {
        printf("exit code: %d\n", WEXITSTATUS(status));
    }

    return 0;
}
```

编译：

```bash
gcc mini-shell.c -o mini-shell
```

运行：

```bash
./mini-shell
```

输入：

```text
command: ls
arg: -l
```

这个程序的结构就是：

```text
父进程：读取命令，fork 子进程，等待子进程
子进程：exec 外部命令
```

当然，真正的 shell 要复杂得多，还要处理：

- 多个参数
- 引号
- 管道
- 重定向
- 环境变量
- 后台任务
- 信号
- 作业控制

但最核心的骨架就是 `fork + exec + wait`。

------

## 十四、总结

`fork()` 和 `exec()` 是 Unix 进程模型里非常重要的一组机制。

`fork()` 的重点是创建子进程：

- 调用一次，返回两次
- 子进程返回 `0`
- 父进程返回子进程 PID
- 失败返回负数
- 父子进程拥有相互独立的地址空间
- 现代系统通常通过写时复制优化内存复制成本

`exec()` 的重点是替换当前程序：

- 不创建新进程
- 用另一个程序替换当前进程镜像
- 成功后不会返回
- 失败时才返回并设置错误

两者组合起来，就是经典模式：

```text
fork 创建子进程
exec 在子进程里加载新程序
wait 让父进程回收子进程状态
```

这也是 shell、服务管理器、许多并发程序和任务调度程序背后的基本机制。

所以，父子进程逻辑写在一起并不一定是冗余。对于同一程序内部的分工，可以用函数拆清楚；对于完全不同的任务，就用 `exec()` 加载外部程序。把边界放在正确的位置，代码自然就不会显得臃肿。
