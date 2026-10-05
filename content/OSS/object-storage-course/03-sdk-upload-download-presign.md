+++
date = '2026-10-02T18:30:00+08:00'
draft = false
title = 'Python 操作对象存储：可靠上传、分片传输与预签名 URL'
+++

CLI 适合学习和排障，应用不能靠人工敲命令。本章用 Python `boto3` 把上一章的对象操作封装为程序，并解释“上传成功”为什么仍需校验、“重试”为什么不能无条件进行，以及浏览器直传为何需要预签名 URL。

## 1. 创建明确的 client

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install boto3
```

不要把 endpoint、密钥散落在函数中。下面的代码从环境读取实验配置，并设置连接与读取超时。生产环境应从工作负载身份或密钥管理系统获得短期凭据。

```python
import os
import boto3
from botocore.config import Config

client = boto3.client(
    's3',
    endpoint_url=os.environ['OS_LAB_ENDPOINT'],
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
    config=Config(
        connect_timeout=3,
        read_timeout=60,
        retries={'mode': 'standard', 'max_attempts': 4},
        s3={'addressing_style': 'path'},
    ),
)
```

`addressing_style='path'` 让请求形如 `endpoint/bucket/key`，对本地服务和不支持 wildcard DNS 的环境更稳定。云端或目标服务若要求 virtual-host-style，应遵从其文档，而不是把这个设置当万能答案。

## 2. 小对象：写入、读取并校验字节

以下函数不把 ETag 当 checksum。它将 SHA-256 写入 metadata，下载到临时文件后校验，再原子替换目标文件，避免调用者读取到半个文件。

```python
from hashlib import sha256
from pathlib import Path
import os

def digest(path: Path) -> str:
    h = sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def upload_checked(bucket: str, key: str, source: Path) -> str:
    checksum = digest(source)
    with source.open('rb') as body:
        client.put_object(
            Bucket=bucket, Key=key, Body=body,
            ContentType='application/octet-stream',
            Metadata={'sha256': checksum},
        )
    head = client.head_object(Bucket=bucket, Key=key)
    if head['ContentLength'] != source.stat().st_size:
        raise RuntimeError('uploaded size differs from source')
    if head.get('Metadata', {}).get('sha256') != checksum:
        raise RuntimeError('checksum metadata missing or changed')
    return checksum

def download_checked(bucket: str, key: str, target: Path) -> None:
    expected = client.head_object(Bucket=bucket, Key=key).get('Metadata', {}).get('sha256')
    temporary = target.with_suffix(target.suffix + '.part')
    client.download_file(bucket, key, str(temporary))
    if expected and digest(temporary) != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError('download checksum mismatch')
    os.replace(temporary, target)
```

运行时使用上一章设置的环境变量：

```python
from pathlib import Path

bucket = 'os-lab-alice-2026'
Path('note.txt').write_text('durable bytes\n', encoding='utf-8')
print(upload_checked(bucket, 'uploads/note.txt', Path('note.txt')))
download_checked(bucket, 'uploads/note.txt', Path('note-copy.txt'))
print(Path('note-copy.txt').read_text(encoding='utf-8'))
```

预期先打印 64 位 SHA-256，随后打印 `durable bytes`。如果进程在下载中断，留下的只会是 `.part` 文件，不会伪装成完整的 `note-copy.txt`。

## 3. 大文件：何时交给 multipart transfer manager

`put_object` 适合明确的小对象。大文件或网络波动场景应使用 `upload_file`；它会按阈值启动 multipart upload、并发传 part、失败重试。不要自己随意并行切文件后再 `PUT`，那不会自动组成一个对象。

```python
from boto3.s3.transfer import TransferConfig

transfer = TransferConfig(
    multipart_threshold=16 * 1024 * 1024,
    multipart_chunksize=16 * 1024 * 1024,
    max_concurrency=4,
    use_threads=True,
)
client.upload_file(
    'archive.zip', bucket, 'archives/archive.zip',
    ExtraArgs={'Metadata': {'sha256': digest(Path('archive.zip'))}},
    Config=transfer,
)
```

16 MiB 和 4 并发只是实验起点。增大 part 会减少请求数但增加失败重传量；增加并发会提高吞吐也会占用网络、磁盘和内存。用真实文件和网络测量吞吐、错误率、服务端 5xx 与未完成分片数量，再定参数。

如果你直接调用 `create_multipart_upload`，必须在异常路径执行 `abort_multipart_upload`。否则无主 part 会持续计费或占空间。完成 multipart 后还要执行 `head_object` 和 checksum 核对，不能仅依据 `complete` 返回成功。

## 4. 预签名 URL：让浏览器直传但不交出密钥

典型流程是：应用认证用户，生成不可猜的对象 key，签一个短期 PUT URL；浏览器将文件直接传到对象存储；应用收到完成通知后用 `HEAD` 验证对象。

```python
from uuid import uuid4

key = f'incoming/user-42/{uuid4()}.png'
put_url = client.generate_presigned_url(
    'put_object',
    Params={'Bucket': bucket, 'Key': key, 'ContentType': 'image/png'},
    ExpiresIn=300,
    HttpMethod='PUT',
)
print(key)       # 可保存为业务记录
# put_url 是临时凭据：不要打印到长期日志或返回给无关用户
```

客户端必须使用签名时承诺的 HTTP 方法和 `Content-Type`：

```powershell
$headers = @{ 'Content-Type' = 'image/png' }
Invoke-WebRequest -Method Put -Uri $putUrl -Headers $headers -InFile .\avatar.png
```

URL 过期、上传失败或客户端篡改 header 都可能导致 403。更关键的是，预签名 URL 本身不能取代业务校验：签发前限制用户可写的 prefix、类型和期望大小；上传后 `head_object` 检查 size 与 metadata，必要时做病毒扫描或文件格式解析后才把 key 关联到正式业务记录。

## 5. 重试与错误：只重试你理解的失败

连接超时、读超时、部分 5xx 常可重试；`AccessDenied`、`NoSuchBucket`、参数错误和 checksum 不一致通常不能靠重试解决。覆盖固定 key 的 `PUT` 在超时后存在“服务已写入但客户端没收到响应”的不确定性；使用唯一 key 或版本/条件写入策略能降低重复执行风险。

记录错误时保留 operation、bucket、key 的安全摘要、HTTP status、request id 和耗时，不要记录 secret 或完整预签名 URL。下一章会继续处理权限、版本、生命周期和灾难恢复；可靠代码只是可靠对象存储的一半。
