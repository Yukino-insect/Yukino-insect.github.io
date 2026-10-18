+++
date = '2026-08-31T16:30:00+08:00'
draft = false
title = 'C 与 C++ 线程模型与并发控制：内存模型、同步原语和设计选择'
+++

线程并不是“让函数同时跑起来”的魔法按钮。它让多个执行流共享同一进程的地址空间，因此也让它们能够在没有约定的情况下同时碰到同一份数据。真正需要解决的问题始终是三件事：**谁可以访问数据、访问的先后关系是什么、另一个线程何时能看见结果**。

C11 和 C++11 都为此定义了语言级内存模型：数据竞争是未定义行为；同步操作会建立线程间的顺序关系；原子操作既能保证单个对象的无竞争访问，也能在合适的内存序下发布其他数据。操作系统线程、POSIX Threads 和 Windows 线程仍然是常见实现基础，但程序的正确性应先以语言规则来判断。

## 一、先分清并发、并行和线程

**并发（concurrency）**表示多个任务的生命周期相互重叠；它们可以在一个 CPU 核上交替推进。**并行（parallelism）**表示多个任务在不同 CPU 核上同一时刻执行。线程是操作系统调度的执行单元之一；多线程可以并发，也可能真正并行。

```text
进程
├─ 线程 A：寄存器、栈、程序计数器独立
├─ 线程 B：寄存器、栈、程序计数器独立
└─ 共享：堆、全局/静态对象、打开的文件描述符等进程资源
```

共享内存使线程间传递数据很方便，也使下面的代码危险：

```cpp
int counter = 0;

void increment() {
    ++counter;
}
```

`++counter` 不是一个不可分割的“加一”：概念上包含读、计算、写。两个线程交错执行时可能丢失更新；更严肃的是，C/C++ 中两个线程对同一内存位置并发访问，至少一个是写，且没有原子性或同步关系时，就是**数据竞争（data race）**，行为未定义。它不只是“最终数字可能不对”，编译器也可以基于“程序不存在数据竞争”的前提进行优化。

## 二、C/C++ 内存模型：正确性判断的中心

### 1. 冲突访问与数据竞争

两个操作满足以下条件时互相冲突：它们访问同一**内存位置**，并且至少一个是写或对象生命周期的开始/结束。数组的不同元素通常是不同内存位置；位域和相邻对象则应避免凭直觉猜测。

下列任一条件成立，冲突访问才不会形成数据竞争：

- 两个访问都是原子操作；
- 一个访问通过同步关系**先发生于**（happens-before）另一个访问；
- 访问发生在同一线程，或程序另有语言规定的顺序。

`volatile` 不属于这个清单。它主要约束编译器不能随意省略或合并对该对象的可观察访问，适合内存映射 I/O 等场景；它不提供互斥、原子读改写、跨线程可见性或顺序保证。用 `volatile bool done` 做线程通知，是一个看上去很勤奋、结果却不合格的答案。

### 2. `happens-before`：让“看见”有依据

同一线程内，语句的求值顺序会形成 **sequenced-before**；一个线程解锁互斥量，另一个线程随后锁定同一个互斥量，解锁与成功加锁之间会形成同步关系。把这些边连起来，得到的传递闭包就是 `happens-before`。

```text
线程 A                         线程 B
写入订单字段
mutex.unlock()  ─同步→          mutex.lock()
                                读取订单字段

写入字段 happens-before 读取字段
```

因此，锁不仅保证“同一时间最多一人进入临界区”，还保证临界区内较早的写入会在后来持有同一把锁的线程看来是可见的。线程创建与 `join` 也提供重要边界：启动线程前完成的操作先发生于新线程中的操作；被 `join` 的线程完成前的操作先发生于 `join` 返回后的操作。

### 3. 不要把硬件直觉当成语言保证

在某台 x86 机器上“反复测试都正常”，不能证明代码正确。编译器可以重排普通读写，CPU 也可能以与源码不同的可观察顺序传播写入。C/C++ 的同步原语和原子内存序描述的是跨平台契约；应以它们建立顺序，而不是依赖当前处理器“似乎比较强的内存模型”。

## 三、线程的创建、所有权与结束

### 1. C++：`std::thread` 与 `std::jthread`

`std::thread` 表示一个可执行线程。对象析构前必须 `join()` 或 `detach()`；否则仍为可结合（joinable）的 `std::thread` 析构会调用 `std::terminate()`。`detach()` 会放弃会合能力，后台线程又可能访问已经销毁的对象，因此它不应作为“我不想处理生命周期”的借口。

```cpp
#include <iostream>
#include <thread>

void work(int value) {
    std::cout << value * 2 << '\n';
}

int main() {
    std::thread worker(work, 21);
    worker.join();
}
```

在 C++20 中，优先考虑 `std::jthread`。它在析构时会请求停止并自动 `join()`，让线程所有权与作用域绑定；线程函数可选择接收 `std::stop_token`，以协作方式响应取消。

```cpp
#include <chrono>
#include <stop_token>
#include <thread>

void poll(std::stop_token stop) {
    while (!stop.stop_requested()) {
        // 做一小段可中断的工作，而不是无限阻塞
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}

int main() {
    std::jthread worker(poll);
    // 离开作用域时：request_stop()，然后 join()
}
```

停止请求不是强行杀死线程；它只是一个可观察的标志。工作函数必须在合适的边界检查它，并保证资源仍能正常释放。

### 2. C：C11 `<threads.h>` 或平台线程库

C11 提供了 `<threads.h>`：`thrd_create`、`thrd_join`、`mtx_t`、`cnd_t` 和 `_Atomic` 等；不过线程库在历史上是可选能力，实际工程要确认编译器与目标平台支持情况。POSIX 平台广泛使用 pthread，Windows 则常用 Win32 线程或其更高层封装。它们的 API 不同，但锁、条件变量、原子与生命周期的基本模型相同。

```c
#include <stdio.h>
#include <threads.h>

static mtx_t counter_mutex;
static int counter = 0;

static int increment(void *unused) {
    (void)unused;
    mtx_lock(&counter_mutex);
    ++counter;
    mtx_unlock(&counter_mutex);
    return 0;
}

int main(void) {
    thrd_t first, second;
    mtx_init(&counter_mutex, mtx_plain);

    thrd_create(&first, increment, NULL);
    thrd_create(&second, increment, NULL);
    thrd_join(first, NULL);
    thrd_join(second, NULL);

    printf("counter = %d\n", counter);
    mtx_destroy(&counter_mutex);
}
```

这个例子中，`counter` 的所有访问都由同一把互斥量保护；两个 `join` 返回后再读取它，因此没有数据竞争。生产代码仍应检查每个 API 的错误码；示例省略它只是为了突出并发结构。

## 四、互斥：最可靠的默认选择

### 1. 用 RAII 管住锁的生命周期

临界区应尽量短，只覆盖维护共享不变量所需的代码；更重要的是，C++ 中不要手写一串 `lock()` / `unlock()` 后期待所有分支都记得解锁。异常、提前返回和新增代码会让这种期待很脆弱。

```cpp
#include <mutex>
#include <vector>

class SafeQueue {
public:
    void push(int value) {
        std::lock_guard<std::mutex> lock(mutex_);
        values_.push_back(value);
    }

private:
    std::mutex mutex_;
    std::vector<int> values_;
};
```

`std::lock_guard` 在构造时加锁、离开作用域时解锁。需要先解锁再做耗时工作，或需要与条件变量配合等待时，使用可显式 `unlock()` 的 `std::unique_lock`。需要一次锁住多把锁时，用 `std::scoped_lock`（C++17）或 `std::lock` 配合多个 `unique_lock`，避免固定顺序不一致造成死锁。

```cpp
std::scoped_lock lock(account_a.mutex, account_b.mutex);
// 在两把锁都持有时转账、同时维护两个账户的不变量
```

### 2. 选择 `mutex`、读写锁还是递归锁

| 工具 | 适用对象 | 要点 |
| ---- | -------- | ---- |
| `std::mutex` / `mtx_t` | 大多数共享可变状态 | 默认首选，语义直白 |
| `std::shared_mutex` | 读远多于写、读操作足够长 | 多读者可并行，但写入、饥饿和开销需评估 |
| `std::recursive_mutex` | 旧接口必须重入同一把锁 | 尽量避免；常暴露不清晰的调用结构 |
| `std::timed_mutex` | 必须响应超时的边界 | 超时不是解决死锁的主要手段 |

锁保护的是**不变量**，不是某一个看上去可疑的变量。若 `balance` 与 `history` 必须同步更新，它们应在同一同步协议下读取和修改；只给其中一个加锁并不能保存业务状态的一致性。

### 3. 死锁、活锁与饥饿

死锁往往需要四个条件同时成立：互斥、持有并等待、不可抢占、循环等待。实践上最有效的预防方式是减少多锁设计；确需多锁时，统一全局加锁顺序或使用一次锁定多个锁的工具。

```text
线程 A：持有 mutex_a，等待 mutex_b
线程 B：持有 mutex_b，等待 mutex_a
                    ↓
                  死锁
```

活锁是线程都在“礼貌地重试”却没有任何进展；饥饿是某个线程长期得不到资源。它们不等于数据竞争，因此通过原子变量也不会自动消失。把锁内 I/O、网络调用和用户回调移到锁外，往往比给锁叠加更多技巧更有价值。

## 五、条件变量：等待条件，而不是等待一次通知

条件变量适合“队列非空”“状态已完成”一类条件：等待者先在锁保护下检查条件，不满足时原子地释放锁并等待；通知者修改条件后通知等待者。关键规则是：**条件由共享状态表示，等待必须放在谓词循环中**。通知不会永久保存，等待也可能无缘无故返回（伪唤醒）。

```cpp
#include <condition_variable>
#include <mutex>
#include <queue>

std::mutex mutex;
std::condition_variable not_empty;
std::queue<int> jobs;
bool closed = false;

bool pop(int& job) {
    std::unique_lock<std::mutex> lock(mutex);
    not_empty.wait(lock, [] { return closed || !jobs.empty(); });

    if (jobs.empty()) {
        return false; // 已关闭且没有剩余任务
    }
    job = jobs.front();
    jobs.pop();
    return true;
}

void push(int job) {
    {
        std::lock_guard<std::mutex> lock(mutex);
        jobs.push(job);
    }
    not_empty.notify_one();
}
```

调用 `notify_one()` / `notify_all()` 的时机通常是修改共享状态之后；通知本身不是状态。C11 使用 `cnd_wait` 与 `cnd_signal` / `cnd_broadcast`，其正确用法同样是“持锁检查条件 → 循环等待 → 被唤醒后重新检查”。

## 六、原子操作：小状态的无锁协调

`std::atomic<T>`（C++）和 `_Atomic T` / `atomic_*`（C）让对一个对象的读、写或读改写以原子方式发生，从而避免该对象自身的数据竞争。原子不等于“整个算法线程安全”：多个变量之间的不变量、检查后再执行（check-then-act）和容器操作，仍常常需要锁。

```cpp
#include <atomic>

std::atomic<unsigned long> request_count{0};

void record_request() {
    request_count.fetch_add(1, std::memory_order_relaxed);
}
```

这个计数器只需要正确计数，不借它发布其他数据，因此 `memory_order_relaxed` 足够。它只保证该原子变量的修改顺序和原子性，不建立其他内存位置的可见性。

### 1. 发布数据：release 与 acquire

当一个原子标志承载“前面的普通写入已经准备好”的含义时，需要发布/获取语义：

```cpp
#include <atomic>

struct Config {
    int port;
};

Config config;
std::atomic<bool> ready{false};

void producer() {
    config.port = 8080;
    ready.store(true, std::memory_order_release);
}

void consumer() {
    while (!ready.load(std::memory_order_acquire)) {
        // 实际程序应避免无限空转，可用等待、退避或条件变量
    }
    use(config.port); // 能看见 producer 在 release 前完成的写入
}
```

当 acquire 读取到对应 release 写入的值时，`producer` 中 release 之前的写入先发生于 `consumer` 中 acquire 之后的读取。C 的 `atomic_store_explicit` / `atomic_load_explicit` 与 `memory_order_release` / `memory_order_acquire` 表达同一模型。

### 2. `seq_cst`、`acq_rel` 与默认策略

| 内存序 | 含义 | 常见用途 |
| ------ | ---- | -------- |
| `relaxed` | 只保证该原子的原子性与修改顺序 | 独立统计计数器 |
| `release` / `acquire` | 发布写入 / 获取已发布数据 | 初始化完成标志、单向交接 |
| `acq_rel` | 同一读改写同时获取与发布 | 无锁状态机的 RMW 操作 |
| `seq_cst` | 额外提供全局单一顺序 | 首先保证正确性、调试复杂协议 |

没有明确证明需要更弱内存序时，使用默认的顺序一致 `seq_cst`，或直接使用互斥量。无锁代码并不天然更快；缓存竞争、重试、可维护性与平台差异都可能让它更慢、更难验证。

### 3. 自旋与 `atomic::wait`

短暂等待的情况下可以自旋，但无限循环会浪费 CPU。C++20 的 `atomic::wait` / `notify_one` / `notify_all` 能把“值未改变时等待”表达得更清楚：

```cpp
std::atomic<bool> finished{false};

void wait_until_finished() {
    finished.wait(false);
}

void finish() {
    finished.store(true, std::memory_order_release);
    finished.notify_all();
}
```

调用方仍应按 API 规则重新检查期望值；等待可能因为值改变、通知或实现允许的伪唤醒而返回。

## 七、并发控制的常见模型

### 1. 共享状态 + 锁

所有访问都在同一锁协议下进行。它最直接，适合一组必须保持一致的数据结构；代价是竞争会降低可扩展性。优先把锁粒度设计为清晰的所有权边界，而不是过早拆成许多细锁。

### 2. 消息传递与生产者—消费者

让工作线程拥有自己的状态，通过线程安全队列传递任务和结果。这样共享状态变少，锁集中在队列边界，关闭语义也更容易定义。上面的“队列非空”条件变量示例就是其基础形式。

### 3. 不可变快照与 copy-on-write

配置、路由表或只读索引更新较少、读取很多时，可构造新快照，再原子地发布指针或在短锁内替换。读者只读自己的快照，不与写者共同修改同一对象。对象回收、指针生命周期与 ABA 问题会使实现复杂；C++ 可借助 `shared_ptr` 的原子操作或成熟并发容器，C 中则更应谨慎。

### 4. 任务并行

把大计算分成独立任务，汇合结果时再同步。C++ 标准库提供 `std::async`、并行算法及执行策略，但它们的调度策略和线程数量不应凭想象假定；需要稳定线程池、队列上限和取消策略时，通常选择成熟库或项目自己的执行器。

## 八、一个实用的选择顺序

面对并发需求，可以按下面的顺序作决定：

1. 能否把可变状态限制在一个线程或一个任务中？能，就用消息传递。
2. 共享状态是否由多个字段共同构成不变量？是，就从互斥量开始。
3. 是否只是独立标志、计数或单向发布？是，才评估原子变量。
4. 是否需要等待“状态成立”而不是轮询？使用条件变量、信号量或 C++20 原子等待。
5. 是否需要停止、超时、背压和异常传播？先把生命周期与关闭协议写清楚，再创建线程。

## 九、代码审查清单

- 每一份共享可变数据是否有唯一、明确的同步协议？
- 每一次读是否也受同一协议保护，而不只是在写入处加锁？
- 条件变量是否使用谓词/循环检查，而不是单独等待通知？
- 线程是否总会 `join`，后台线程是否可能访问已销毁对象？
- 锁内是否执行了 I/O、阻塞等待、未知回调或长计算？
- 多把锁是否有一致顺序，或使用了死锁避免工具？
- 原子内存序是否说明了发布什么数据；若没有，是否应改回锁？
- 是否定义了任务队列关闭、异常、取消和超时后的行为？

## 十、总结

C/C++ 并发控制不是从 `std::thread` 或 `thrd_create` 开始，而是从**数据所有权与同步关系**开始。

- 普通共享读写若没有同步，就是数据竞争和未定义行为。
- 互斥量是维护多字段不变量的默认工具；RAII 能让加锁与解锁可靠地跟随作用域。
- 条件变量等待的是共享状态表达的条件，必须在谓词循环中使用。
- 原子操作适合小而明确的协议；`relaxed` 不发布数据，release/acquire 才能建立可见性边。
- 线程的创建只是开始，`join`、停止、关闭和资源生命周期才决定一个并发设计是否完整。

若一个方案无法用一句话说明“哪份状态归谁所有、谁在何处修改、另一个执行流靠什么看见它”，那么先补上这个设计，再写代码。并发问题并不会因为沉默而自行消失。
