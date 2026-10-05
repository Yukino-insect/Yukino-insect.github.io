+++
date = '2026-10-02T13:30:00+08:00'
draft = false
title = 'etcd 协调实战：事务、分布式锁、选主与隔离令牌'
+++

上一章的 `get` 和 `put` 足以保存配置，却不足以处理竞争。两个程序若各自执行“先读取锁不存在，再写入锁”，它们都可能在同一时刻读到不存在。正确的协调需要把判断和动作放进同一个原子操作。etcd 的 **transaction（事务）** 就是这把工具：它在一个 revision 中执行比较条件，再只执行成功分支或失败分支。

本章假设 `etcd-learning` 容器仍在运行；若已停止，请重新执行[上一章的启动命令](02-etcd-dockerctlkv-practice.md)。

## Compare-and-swap：把“如果”交给服务端

**CAS（compare-and-swap，比较并交换）**指“只有条件仍成立才写入”。先创建一个值：

```powershell
docker exec etcd-learning etcdctl put /learn/release/color blue
docker exec etcd-learning etcdctl get /learn/release/color -w json
```

从 JSON 中找到 `mod_revision`，将下面的 `R` 替换为实际数字。事务文本分为三段：第一段比较；第一个空行后的命令在条件成立时执行；第二个空行后的命令在不成立时执行。

```powershell
@'
mod("/learn/release/color") = "R"

put /learn/release/color green

get /learn/release/color
'@ | docker exec -i etcd-learning etcdctl txn
```

输出中 `SUCCESS` 表示比较通过。现在先运行一次 `put /learn/release/color red`，再不改 `R` 重复事务；这次会进入失败分支并读出当前值。`version("/learn/locks/report") = "0"` 则表示 key 不存在，适合“只创建一次”。将读取和写入拆成两个独立请求，正是在自己制造竞态条件。

## 最小分布式锁：存在性检查加 Lease

锁的作用是限制同一段临界工作同一时刻只由一个参与者执行，例如只允许一个任务生成日报。锁 key 必须绑定 lease：持有者崩溃后，lease 到期会自动删锁，别人才能继续。

```powershell
$lease = docker exec etcd-learning etcdctl lease grant 30 |
  Select-String -Pattern 'lease ' |
  ForEach-Object { ($_ -split ' ')[1] }

@"
version(\"/learn/locks/report\") = \"0\"

put /learn/locks/report worker-a --lease=$lease

get /learn/locks/report
"@ | docker exec -i etcd-learning etcdctl txn
```

只有看到 `SUCCESS` 才能进入临界区。以另一个 lease、另一个值再次运行同一事务，应得到 `FAILURE`。真实客户端需要在持锁期间 keep-alive，并在结束时撤销 lease 或删除锁；不能只依赖“我觉得任务会很快完成”。

不过锁并不能阻止一个已经失去网络的旧持有者继续写外部数据库：它可能不知道 lease 已过期，仍在慢吞吞地执行。这就是为什么关键副作用还需要隔离令牌。

## Fencing token：拒绝迟到的旧持有者

**Fencing token（隔离令牌）**是单调递增的任期编号。把获得锁时的 `mod_revision` 或独立的递增号作为 token，随每次对受保护资源的写入一同提交；资源服务记录已接受的最大 token，并拒绝比它小的 token。

```text
worker-a 获得 token 101，随后网络暂停
lease 到期，worker-b 获得 token 102 并成功写资源
worker-a 恢复，携带 token 101 的迟到写入被资源服务拒绝
```

令牌的检查必须在真正执行副作用的系统里完成，例如数据库更新条件、文件写入服务或支付网关适配层。只在 etcd 中“看见锁还在”并不能替资源服务撤销旧客户端的权限。这个边界很重要：etcd 协调资格，业务系统负责拒绝过期资格。

## 选主：长期职责的可观察版本

**选主（leader election）**是锁的常见变体：多个副本争取成为某项长期职责的 leader，例如定期调度器。leader 用 lease 注册一个带序号的候选 key；最早的候选成为 leader，其他候选 watch 它，删除后再竞争。官方客户端库已经提供 election 原语，应用通常应该使用库而不是手搓复杂的 watch 顺序。

即使使用库，也要设计三个问题：

- leader 失去 lease 后必须停止新工作；
- 工作最好可重试、可幂等，避免交接时重复执行造成伤害；
- 对不可重复的外部写入使用 fencing token 或业务幂等键。

简化的状态流如下：

```text
候选者创建 lease 绑定的候选 key
        │
        ├─ 排名最前：成为 leader，持续 keep-alive 并工作
        └─ 不是最前：watch 前一个候选 key，删除后重新判断
```

## Watch 的正确姿势

watch 适合观察锁释放、成员下线和配置变更，但每个消费者都要处理三件事：连接断开、事件重复处理，以及历史被压缩。最稳妥的算法仍是先 range 拿到状态和 revision，再从下一 revision watch；收到 compaction 错误后重新全量同步。

不要用 etcd 锁包住长时间的网络调用或人工操作。TTL 设得过短会误释放，设得过长会让故障恢复拖延；更根本的办法是缩短临界区、让操作幂等、为外部副作用加隔离令牌。协调不是魔法，它只是把竞争的规则明确到足以验证。
