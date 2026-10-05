+++
date = '2026-10-02T18:10:00+08:00'
draft = false
title = '对象存储基础：Bucket、Object、HTTP 请求与 S3 签名'
+++

先别急着安装客户端。对象存储最容易出错的地方并不是某个命令，而是把它当作远程磁盘：以为有真实目录、以为覆盖写一定安全、以为下载链接可以永久公开。本章先建立准确模型，后面的每个命令才知道自己在验证什么。

## 一个对象到底是什么

在 S3 风格服务中，对象由三部分定位：

```text
endpoint + bucket + key
http://127.0.0.1:9000 / os-lab-alice-2026 / raw/acme/readme.txt
```

- **Endpoint** 是服务入口，例如 AWS S3 或自建 S3 兼容服务。
- **Bucket** 是对象的顶层容器，也是策略、版本和生命周期的常见作用范围。
- **Key** 是对象名，长度和字符规则取决于服务；`images/2026/a.png` 是一个完整字符串，不是目录树。
- **Object** 包含数据字节、key、大小、内容类型、用户 metadata、标签、ETag 和可选 version id。

当你“创建目录”时，许多工具其实上传了一个以 `/` 结尾的零字节对象，或根本没有创建任何东西。列举 `photos/` 之所以像列目录，是 ListObjects 的 prefix 过滤在起作用。因此不要用“目录是否为空”作为业务正确性依据，也不要依赖目录级 rename：对象存储通常要复制新 key 后再删除旧 key。

## 元数据、ETag 与内容完整性：三个很像但不同的概念

`Content-Type: image/png` 告诉浏览器怎样解释内容；自定义 metadata（例如 `x-amz-meta-sha256`）保存应用说明；Tag 更适合策略或计费筛选。它们都不是文件本身。

ETag 是服务返回的对象版本标识。单段、未加密上传在很多实现中恰好是 MD5，但这不是跨服务的保证；multipart 上传的 ETag 往往形如 `xxx-7`，加密或网关也可能改变它。需要证明字节未损坏时，上传前计算 SHA-256，写入可信 metadata 或单独 manifest，下载后再次计算并比较。

```powershell
Get-FileHash .\sample.txt -Algorithm SHA256
```

预期输出中 `Hash` 是 64 位十六进制字符串。同一份未改动文件在同一算法下应得到相同值；它比“ETag 看起来没变”更明确。

## 用 HTTP 看最小操作集

S3 是一组 HTTP API，SDK 和 CLI 最终都在发这些请求。下面是概念化表示，签名头已省略：

```http
PUT /os-lab-alice-2026/raw/acme/readme.txt HTTP/1.1
Host: storage.example.test
Content-Type: text/plain
Content-Length: 5

hello
```

成功通常返回 `200 OK`，并给出 `ETag`。读取是 `GET`；只读取头部（大小、类型、ETag、metadata）使用 `HEAD`；列举使用 `GET /bucket?list-type=2&prefix=raw/acme/`；删除使用 `DELETE`。覆盖相同 key 时，默认语义通常是替换当前对象，而不是追加内容。因此应用应使用对象 ID 或不可变版本 key，避免两个写入者不知不觉互相覆盖。

范围读取能避免下载整个大文件：

```http
GET /os-lab-alice-2026/video.mp4 HTTP/1.1
Range: bytes=0-1023
```

服务若支持会返回 `206 Partial Content` 与 `Content-Range`。这适合媒体预览和断点续传，不代表可以就地修改第 1024 个字节。

## 为什么请求还要签名

如果任何人都能发送 `PUT` 或 `DELETE`，对象存储就只是公开匿名文件服务器。S3 常使用 Signature Version 4（SigV4）：客户端把 HTTP 方法、规范化 URI、查询参数、关键 headers、payload hash 和时间组成 canonical request，使用 secret key 派生签名；服务用同一规则验证。

这解释了几个常见故障：

- 本机时间偏差很大时，服务可能拒绝请求为过期或尚未生效。
- 代理若改写 `Host`、path 或 query，服务收到的请求与客户端签名的请求不同，会出现 `SignatureDoesNotMatch`。
- endpoint、region、path-style/virtual-host-style 配置不一致时，签名的目标也会不同。

不要自己拼签名，使用维护中的 SDK；理解它签的是“完整请求”即可。排查签名失败时，先比较客户端 endpoint、region、系统时间、代理重写和服务日志，最后才怀疑口令。

## 预签名 URL：短时、受限的委托

预签名 URL 是持有有效凭据的服务端提前签好的 URL。浏览器或手机无需得到 access key，便可在期限内执行某个 GET 或 PUT。它解决“让客户端直传文件”的问题，但 URL 本身就是可用凭据：泄漏给谁，谁就在有效期内可使用。

安全做法是：服务端先验证登录用户、对象 key 前缀、允许的 Content-Type/大小；只签一个随机且不可猜的 key；设置分钟级到小时级过期；上传完成后服务端 `HEAD` 校验大小和 checksum。不要把预签名 URL 写进长久日志、聊天记录或网页缓存，也不要误以为它会自动阻止用户上传超大或伪装类型的内容。

## Multipart upload：大文件不是一次 PUT

网络中断时重传 20 GiB 文件很浪费。multipart upload 将对象拆为多个 part：

```text
CreateMultipartUpload
  -> UploadPart(1), UploadPart(2), ...
  -> CompleteMultipartUpload
             或 AbortMultipartUpload
```

完成前，普通 `GET key` 看不到半成品；完成时服务按 part 列表组装为一个对象。每个 part 可以重试，但 part number 与 ETag 必须记录好；异常时应 Abort，否则未完成 part 会长期占空间。阈值、最小 part 大小和最大 part 数是服务约束，SDK 的 transfer manager 通常会代管它们。

## 本章检查

请能用自己的话回答：为什么 `logs/2026/` 不是目录？为什么 ETag 不适合作唯一完整性证据？为什么一个成功的 PUT 也不能证明授权设计安全？带着这三个答案进入下一章；下一章会让这些概念产生可观察的输出。
