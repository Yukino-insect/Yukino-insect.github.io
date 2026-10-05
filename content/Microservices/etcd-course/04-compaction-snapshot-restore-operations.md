+++
date = '2026-10-02T13:40:00+08:00'
draft = false
title = 'etcd 运维入门：压缩、快照、恢复与集群边界'
+++

etcd 可靠并不等于“容器有一个数据卷”。KV 的历史会增长，watch 客户端会落后，磁盘会产生碎片；真正的备份也必须能恢复并读取。这里先在单节点实验中学习工具的行为，再说明这些操作在集群中的边界。执行前请重新启动[上一章](02-etcd-dockerctlkv-practice.md)的 `etcd-learning` 容器。

## 为什么需要压缩

etcd 使用 MVCC 保留旧 revision，方便历史读取和断线 watch 追赶。历史无限增长会占满 backend，因此需要 **compaction（压缩）**：告诉服务器“这个 revision 之前的历史不再提供”。压缩不会删除当前 key，只会让很老的版本和从太早 revision 开始的 watch 不可用。

先制造历史。读取 JSON 响应并记下 `header.revision` 的实际数值，例如 `R`：

```powershell
1..12 | ForEach-Object {
  docker exec etcd-learning etcdctl put /learn/history/item "value-$_"
}
docker exec etcd-learning etcdctl get /learn/history/item -w json
```

把 `R` 替换为一个已经产生的 revision 后执行压缩：

```powershell
docker exec etcd-learning etcdctl compact R
```

再从明显早于 `R` 的 revision 开始 watch：

```powershell
docker exec -it etcd-learning etcdctl watch /learn/history/item --rev 1
```

预期会出现类似 `required revision has been compacted` 的错误。正确处理不是猜一个 revision 重试，而是 range 当前状态、记录响应 revision，然后从下一 revision 建立新 watch。这就是第二章反复强调快照加增量的原因。

压缩只删除逻辑历史；底层数据库文件的空洞不一定立即归还操作系统。**defrag（碎片整理）**会重写数据文件以回收空间。单节点执行期间会影响服务；多节点也必须一次只维护一个成员，并在每步确认多数派仍在线。

```powershell
docker exec etcd-learning etcdctl endpoint status -w table
docker exec etcd-learning etcdctl defrag
docker exec etcd-learning etcdctl endpoint health
```

不要把 `defrag` 当作固定频率的清洁仪式。先根据监控确认已用空间和文件大小存在明显差距，再挑维护窗口处理。

## 快照：创建、校验与保存

**snapshot（快照）**是某一一致状态的备份文件。先写一条容易辨认的数据：

```powershell
docker exec etcd-learning etcdctl put /learn/backup/checkpoint ready
docker exec etcd-learning etcdctl snapshot save /tmp/etcd-learning.db
docker cp etcd-learning:/tmp/etcd-learning.db .\etcd-learning.db
```

用 `etcdutl` 检查快照。下面的容器只读取当前实验目录中的文件：

```powershell
docker run --rm -v "${PWD}:/backup" quay.io/coreos/etcd:v3.5.18 `
  etcdutl snapshot status /backup/etcd-learning.db -w table
```

状态表应给出 hash、revision、key 数量和大小。这个检查只能说明文件结构可读，不代表恢复后的应用一定正确；后者必须通过隔离恢复验证。生产备份还需要加密、访问控制、异地副本、保留策略以及定期恢复演练。

## 隔离恢复：绝不覆盖正在运行的数据目录

恢复会生成一个新的数据目录和新的集群身份。以下实验故意使用不同的容器名和端口，不会覆盖 `data`，也不能将恢复实例接回原实例。

```powershell
docker run --rm -v "${PWD}:/backup" quay.io/coreos/etcd:v3.5.18 `
  etcdutl snapshot restore /backup/etcd-learning.db `
  --name restore-1 `
  --data-dir /backup/restored-data `
  --initial-cluster restore-1=http://127.0.0.1:32480 `
  --initial-advertise-peer-urls http://127.0.0.1:32480

docker run -d --name etcd-restore-check --rm `
  -p 32479:2379 -p 32480:2380 `
  -v "${PWD}\restored-data:/etcd-data" `
  quay.io/coreos/etcd:v3.5.18 `
  etcd --name restore-1 --data-dir /etcd-data `
  --listen-client-urls http://0.0.0.0:2379 `
  --advertise-client-urls http://127.0.0.1:32479 `
  --listen-peer-urls http://0.0.0.0:2380 `
  --initial-advertise-peer-urls http://127.0.0.1:32480 `
  --initial-cluster restore-1=http://127.0.0.1:32480

docker exec etcd-restore-check etcdctl get /learn/backup/checkpoint
```

最后一条预期输出 key 和 `ready`。完成后停止隔离容器：`docker stop etcd-restore-check`。恢复后的 revision 时间线是新的；依赖旧 revision 的 watch 客户端必须重新做完整快照同步。

## 配额、告警与故障排查顺序

backend quota 是 etcd 数据库允许增长的上限。接近上限或触发 `NOSPACE` 告警时，写入会被拒绝。先诊断，再处置：

```powershell
docker exec etcd-learning etcdctl endpoint status -w table
docker exec etcd-learning etcdctl alarm list
docker exec etcd-learning etcdctl endpoint health
```

处理通常是确认可丢弃的历史后压缩，必要时 defrag，确认空间已释放后再解除告警。随意删除 key 或直接解除 alarm 只会掩盖问题。延迟突然升高时，优先检查磁盘 fsync 延迟、磁盘空间、CPU 争用和网络抖动；etcd 很依赖稳定的持久化延迟。

## 从单节点走向生产集群

生产环境通常使用 3 或 5 个 voting member，部署到独立故障域，并启用 TLS、认证与 RBAC。成员加入、移除和替换是 Raft 成员变更：每一步都应先检查 `member list`、endpoint health 和多数派，再按当前版本官方流程继续。不要手写猜测的初始集群字符串，也不要同时重启多数成员。

如果失去 quorum，首要动作是停止写入并保存现有数据目录、日志和快照证据；不要让残存成员各自强制组成“新集群”。恢复需要基于可信快照和清晰的集群重建计划。谨慎不是多余的仪式，而是避免把短暂故障变成永久数据分叉的最低成本。

本课程至此形成一条完整主线：KV 保存小状态，Raft 让多数成员对写入排序，revision 与 watch 让客户端同步变化，lease 让临时资格自动失效，事务解决竞争，而压缩和快照让这套系统可以长期运行与恢复。
