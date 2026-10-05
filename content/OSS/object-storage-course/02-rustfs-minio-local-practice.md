+++
date = '2026-10-02T18:20:00+08:00'
draft = false
title = '对象存储动手实验：启动 S3 兼容服务并用 CLI 管理对象'
+++

这一章的目标很小也很重要：在自己的电脑上把一个文件上传为对象，再用不同方式证明它确实存在、内容正确、可被范围读取，最后安全地删掉实验数据。先把手工链路跑通，再写 SDK；否则报错时你无法判断是程序、网络、签名还是服务的问题。

## 1. 启动一个只用于实验的服务

RustFS 与 MinIO 都提供 S3 兼容 API。以下以 MinIO 为例，因为它便于本地快速验证；若你使用 RustFS，只需采用其官方 Docker 启动方式，并将 endpoint 改为实际端口。不同实现支持的扩展能力不完全相同，后面用到的操作应在你的目标版本上再次验证。

创建一个独立 volume，并启动容器。下面的用户名和密码仅用于本机实验，至少 8 位，绝不能复制到任何共享或生产环境。

```powershell
docker volume create os-lab-data
docker run --rm --name os-lab -p 9000:9000 -p 9001:9001 `
  -e MINIO_ROOT_USER=labadmin `
  -e MINIO_ROOT_PASSWORD='LabOnly-ChangeMe-2026' `
  -v os-lab-data:/data `
  minio/minio server /data --console-address ':9001'
```

保持这个窗口运行。另开 PowerShell，确认服务可达：

```powershell
Invoke-WebRequest http://127.0.0.1:9000/minio/health/live | Select-Object StatusCode
docker ps --filter name=os-lab
```

预期第一个命令显示 `200`，第二个命令状态为 `Up`。若端口被占用，改成 `-p 19000:9000 -p 19001:9001`，并在所有客户端中使用 `http://127.0.0.1:19000`。不要通过“能打开 9001 控制台”推断 S3 API 一定可用，health 检查和实际 CLI 请求才是验证。

设置仅对当前终端生效的凭据：

```powershell
$env:AWS_ACCESS_KEY_ID = 'labadmin'
$env:AWS_SECRET_ACCESS_KEY = 'LabOnly-ChangeMe-2026'
$env:AWS_DEFAULT_REGION = 'us-east-1'
$env:OS_LAB_ENDPOINT = 'http://127.0.0.1:9000'
$bucket = 'os-lab-alice-2026'   # 换成你自己的小写名称
```

## 2. 使用 AWS CLI 完成对象生命周期

创建 bucket，并准备一个可校验的小文件：

```powershell
aws --endpoint-url $env:OS_LAB_ENDPOINT s3 mb "s3://$bucket"
Set-Content -NoNewline -Path .\hello.txt -Value 'hello object storage'
$before = (Get-FileHash .\hello.txt -Algorithm SHA256).Hash
aws --endpoint-url $env:OS_LAB_ENDPOINT s3 cp .\hello.txt "s3://$bucket/notes/hello.txt"
aws --endpoint-url $env:OS_LAB_ENDPOINT s3api head-object --bucket $bucket --key notes/hello.txt
```

预期看到 `make_bucket`、上传进度，以及 JSON 中的 `ContentLength` 为 20（ASCII 内容）和 `ETag`。`head-object` 没有返回正文，这正是它适合先确认对象是否存在、大小是否合理的原因。

列举与下载：

```powershell
aws --endpoint-url $env:OS_LAB_ENDPOINT s3 ls "s3://$bucket/notes/"
aws --endpoint-url $env:OS_LAB_ENDPOINT s3api get-object --bucket $bucket --key notes/hello.txt .\downloaded.txt
$after = (Get-FileHash .\downloaded.txt -Algorithm SHA256).Hash
if ($before -eq $after) { 'SHA-256 verified' } else { throw 'content mismatch' }
```

预期列举到一个约 20 B 对象，并输出 `SHA-256 verified`。范围读取用 `get-object` 的 `--range`：

```powershell
aws --endpoint-url $env:OS_LAB_ENDPOINT s3api get-object `
  --bucket $bucket --key notes/hello.txt --range bytes=0-4 .\first-five.txt
Get-Content .\first-five.txt
```

预期内容为 `hello`。这证明服务返回一段字节，不意味着对象可以随机写入。

## 3. 用 mc 观察同一批对象

`mc` 是面向 S3 兼容服务的交互客户端。它和 AWS CLI 不共享配置，所以要单独建立 alias：

```powershell
mc alias set lab $env:OS_LAB_ENDPOINT labadmin 'LabOnly-ChangeMe-2026'
mc ls lab
mc ls "lab/$bucket/notes"
mc stat "lab/$bucket/notes/hello.txt"
```

预期 `mc stat` 显示 size、ETag、modified time 等信息。此处 ETag 只用于观察服务返回的对象标识；完整性仍以上一步的 SHA-256 对比为准。

## 4. 删除不是“按一下就不存在”

先删除对象并验证：

```powershell
aws --endpoint-url $env:OS_LAB_ENDPOINT s3api delete-object --bucket $bucket --key notes/hello.txt
aws --endpoint-url $env:OS_LAB_ENDPOINT s3api head-object --bucket $bucket --key notes/hello.txt
```

预期第二个命令失败并返回 `404`。这是未开启版本控制时的行为；启用版本后，DeleteObject 通常新增删除标记，旧版本仍可能恢复。不要在陌生 bucket 直接试验版本与生命周期，下一章会解释如何为业务数据设计它们。

实验结束后，先列举确认 bucket 内没有对象，再删除 bucket：

```powershell
aws --endpoint-url $env:OS_LAB_ENDPOINT s3 rb "s3://$bucket"
```

若要保留实验数据，按 `Ctrl+C` 停掉容器即可，volume 仍在；以后用同名 volume 重启可以继续使用。若确实要永久清掉**这个实验 volume**，先确认名称，再执行 `docker volume rm os-lab-data`。这一步不可恢复。

## 5. 失败时不要盲猜

| 现象 | 优先检查 |
| --- | --- |
| connection refused | 容器是否 `Up`、端口映射、endpoint 是否包含正确端口 |
| `AccessDenied` | access key/secret、bucket 策略、对象 key 前缀 |
| `SignatureDoesNotMatch` | 系统时间、endpoint、region、代理是否改写 Host |
| `NoSuchBucket` | bucket 名、endpoint 是否指到同一实例 |
| 上传成功但读不到 | key 是否完全一致，特别是大小写、空格、prefix |

你现在已经手工验证了 bucket、key、HEAD、GET、Range GET 和 DELETE。下一章把同一套动作写成应用代码，并为网络故障和大文件补上可靠性措施。
