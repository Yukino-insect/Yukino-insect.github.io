+++
date = '2026-10-02T13:20:00+08:00'
draft = false
title = 'etcd 入门实战：启动单节点、KV、Watch 与 Lease'
+++

这一章只启动一个单节点。目的不是搭建高可用环境，而是把前一章的 key、revision、watch 和 lease 变成亲手可验证的现象。请先完成[课程导读](00-overview.md)中的实验目录准备；下面的 `data` 子目录只保存本章的实验状态。

## 启动一个独立节点

在 PowerShell 中执行以下命令。`2379` 是容器内部给客户端访问的端口，`2380` 是成员复制用的端口；前者映射到宿主机 `32379`，后者映射到 `32380`。即使现在只有一个成员，也保留 peer 地址配置，是为了让“客户端地址”和“成员地址”的区别清楚可见。

```powershell
docker run -d --name etcd-learning --rm `
  -p 32379:2379 -p 32380:2380 `
  -v "${PWD}\data:/etcd-data" `
  quay.io/coreos/etcd:v3.5.18 `
  etcd --name learning-1 --data-dir /etcd-data `
  --listen-client-urls http://0.0.0.0:2379 `
  --advertise-client-urls http://127.0.0.1:32379 `
  --listen-peer-urls http://0.0.0.0:2380 `
  --initial-advertise-peer-urls http://127.0.0.1:32380 `
  --initial-cluster learning-1=http://127.0.0.1:32380 `
  --initial-cluster-state new

docker exec etcd-learning etcdctl endpoint health
docker exec etcd-learning etcdctl endpoint status -w table
```

第一条检查应包含 `is healthy`；状态表通常显示一个 member、一个 leader 和数据库大小。若容器未运行，先执行 `docker logs etcd-learning`。若提示端口被占用，请换一个未被使用的本机端口，并同步修改 `--advertise-client-urls` 与课程导读中的环境变量。

## 第一次写入：观察 KV 元数据

写入一个配置值，再以 JSON 形式读取它：

```powershell
docker exec etcd-learning etcdctl put /learn/config/theme dark
docker exec etcd-learning etcdctl get /learn/config/theme -w json
```

`put` 输出 `OK`。JSON 中 key/value 是 Base64 编码，这是字节串通用表示方式；`header.revision` 是本次读取看到的全局版本。初次写入时，`create_revision` 和 `mod_revision` 相同。再次写入另一值：

```powershell
docker exec etcd-learning etcdctl put /learn/config/theme light
docker exec etcd-learning etcdctl get /learn/config/theme -w json
```

现在 `create_revision` 保持不变，`mod_revision` 变大，`version` 增加。不要把 `version` 当作全局顺序；跨 key 排序应看 revision。

接着写入两个 key 并做前缀查询：

```powershell
docker exec etcd-learning etcdctl put /learn/config/page-size 50
docker exec etcd-learning etcdctl put /learn/config/language zh-CN
docker exec etcd-learning etcdctl get /learn/config/ --prefix
```

预期会列出三个 key。`--prefix` 的含义是字节前缀，不是文件夹权限；所有约定都依赖命名规范。

## Watch：让两个终端合作

打开终端 A，保持命令运行：

```powershell
docker exec -it etcd-learning etcdctl watch /learn/config/ --prefix
```

再打开终端 B，执行：

```powershell
docker exec etcd-learning etcdctl put /learn/config/theme blue
docker exec etcd-learning etcdctl del /learn/config/page-size
```

终端 A 应先显示 `PUT` 与 key/value，再显示 `DELETE` 和被删除的 key。按 `Ctrl+C` 关闭 watch，再写一次值，关闭期间的输出不会跑进已停止的终端。这正是程序需要“range 快照 + 指定 revision 的 watch”恢复策略的原因，而不是一个 bug。

## Lease：让注册记录自动删除

创建一个 15 秒租约。lease ID 由 etcd 返回，因此必须从输出中取自己的值：

```powershell
$lease = docker exec etcd-learning etcdctl lease grant 15 |
  Select-String -Pattern 'lease ' |
  ForEach-Object { ($_ -split ' ')[1] }

docker exec etcd-learning etcdctl put /learn/members/worker-a '{"address":"127.0.0.1:8080"}' --lease=$lease
docker exec etcd-learning etcdctl lease timetolive $lease --keys
```

输出应该显示剩余 TTL 和 `/learn/members/worker-a`。在终端 A watch 这个 key：

```powershell
docker exec -it etcd-learning etcdctl watch /learn/members/worker-a
```

终端 B 用以下命令保持它活着，观察 TTL 被反复刷新：

```powershell
docker exec -it etcd-learning etcdctl lease keep-alive $lease
```

十几秒后按 `Ctrl+C` 停止续约。等 TTL 用尽，终端 A 会看到 `DELETE`；随后执行 `get` 不再有结果。若没有删除，先查 `lease timetolive $lease --keys`：常见原因是 key 没有绑到同一个租约，或另一个 keep-alive 进程仍在运行。

## 清理与本章结论

结束实验时只停止这个明确命名的容器：

```powershell
docker stop etcd-learning
```

若要重新开始，先确认当前目录确实是实验目录，再删除其中的 `data`。单节点停机期间没有替代者，因此它不能代表生产可用性；但它已经足够让你验证四个基本事实：KV 有版本，前缀是命名约定，watch 只传递在线期间的变化，lease 会让临时 key 自动过期。
