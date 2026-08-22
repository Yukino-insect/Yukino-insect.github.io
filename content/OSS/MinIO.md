+++
date = '2025-10-02T22:25:43+08:00'
draft = false
title = 'MinIO'
+++

MinIO 是一个高性能对象存储服务，兼容 Amazon S3 API。它常用来保存图片、视频、文档、日志、备份包等**非结构化数据**。

在业务系统里，MinIO 通常不直接替代数据库。数据库负责结构化业务数据，MinIO 负责保存文件本体，数据库里只保存对象路径、文件名、大小、类型、业务归属等元数据。把大文件硬塞进数据库，当然也不是不能做，只是多数时候都像是在用餐刀挖地基，姿势很努力，结果很难看。

## 核心概念

对象存储最重要的是三个概念：

| 概念 | 说明 |
| ---- | ---- |
| Bucket | 桶，用来存放一类对象，类似顶层目录 |
| Object | 对象，真正保存的文件，例如图片、视频、PDF |
| Policy | 访问策略，用来控制桶或对象的读写权限 |

MinIO 启动后通常提供两个入口：

| 端口 | 作用 |
| ---- | ---- |
| `9000` | S3 API 端口，应用程序通过它上传、下载和管理对象 |
| `9001` | Console 控制台端口，用于在浏览器中管理桶和对象 |

一次典型的文件访问流程如下：

```text
客户端
  -> 后端服务
  -> MinIO API
  -> Bucket / Object
```

如果文件是公开资源，可以直接返回公开访问地址。如果文件是私有资源，更常见的做法是由后端生成一个有过期时间的**预签名 URL**，客户端在有效期内通过这个 URL 访问文件。

```text
客户端请求文件
  -> 后端校验权限
  -> 后端生成预签名 URL
  -> 客户端使用 URL 下载对象
```

这样客户端不需要知道 MinIO 的账号密钥，也不会拿到永久有效的访问入口。

## 适用场景

MinIO 适合保存不需要关系型查询的文件数据：

- 用户头像、商品图片、文章封面。
- 视频、音频、附件、合同文件。
- 日志归档、数据库备份、导出文件。
- 机器学习数据集或大文件中间结果。

不适合放入 MinIO 的内容：

- 需要复杂事务的业务记录。
- 需要频繁按字段查询和关联的数据。
- 高频修改的小片段状态数据。
- 没有访问控制设计的敏感文件。

对象存储擅长的是“按对象名读写文件”。如果你希望它像 MySQL 一样 `where status = 1`，那只能说明你需要的不是对象存储。

## 本地部署

开发环境可以用 Docker 启动一个单节点 MinIO：

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin123 \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"
```

启动后访问控制台：

```text
http://127.0.0.1:9001
```

应用程序连接 API 地址：

```text
http://127.0.0.1:9000
```

开发环境可以使用简单账号，生产环境不要继续使用 `minioadmin` 这类默认凭据。默认账号留在生产环境里，和把门钥匙插在门上差不多，只是表达方式更云原生一点。

## Java SDK 集成

引入 MinIO Java SDK：

```xml
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.2</version>
</dependency>
```

初始化客户端：

```java
MinioClient minioClient = MinioClient.builder()
        .endpoint("http://127.0.0.1:9000")
        .credentials("minioadmin", "minioadmin123")
        .build();
```

创建桶：

```java
String bucketName = "demo";

boolean exists = minioClient.bucketExists(
        BucketExistsArgs.builder()
                .bucket(bucketName)
                .build()
);

if (!exists) {
    minioClient.makeBucket(
            MakeBucketArgs.builder()
                    .bucket(bucketName)
                    .build()
    );
}
```

上传本地文件：

```java
minioClient.uploadObject(
        UploadObjectArgs.builder()
                .bucket("demo")
                .object("avatar/user-1.jpg")
                .filename("D:/upload/avatar.jpg")
                .contentType("image/jpeg")
                .build()
);
```

下载文件：

```java
minioClient.downloadObject(
        DownloadObjectArgs.builder()
                .bucket("demo")
                .object("avatar/user-1.jpg")
                .filename("D:/download/user-1.jpg")
                .build()
);
```

生成临时访问链接：

```java
String url = minioClient.getPresignedObjectUrl(
        GetPresignedObjectUrlArgs.builder()
                .method(Method.GET)
                .bucket("demo")
                .object("avatar/user-1.jpg")
                .expiry(60 * 60)
                .build()
);
```

预签名 URL 的过期时间应该按业务场景控制。头像、公开图片可以走公开读或 CDN；合同、证件、私有附件应该使用短时间有效的预签名 URL。

## Spring Boot 集成

先在 `application.yml` 中配置 MinIO 连接信息：

```yaml
minio:
  endpoint: http://127.0.0.1:9000
  access-key: minioadmin
  secret-key: minioadmin123
  bucket-name: demo
```

定义配置属性类：

```java
@ConfigurationProperties(prefix = "minio")
public class MinioProperties {

    private String endpoint;
    private String accessKey;
    private String secretKey;
    private String bucketName;

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getAccessKey() {
        return accessKey;
    }

    public void setAccessKey(String accessKey) {
        this.accessKey = accessKey;
    }

    public String getSecretKey() {
        return secretKey;
    }

    public void setSecretKey(String secretKey) {
        this.secretKey = secretKey;
    }

    public String getBucketName() {
        return bucketName;
    }

    public void setBucketName(String bucketName) {
        this.bucketName = bucketName;
    }
}
```

注册 `MinioClient`：

```java
@Configuration
@EnableConfigurationProperties(MinioProperties.class)
public class MinioConfig {

    @Bean
    public MinioClient minioClient(MinioProperties properties) {
        return MinioClient.builder()
                .endpoint(properties.getEndpoint())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .build();
    }
}
```

封装文件服务：

```java
@Service
public class MinioService {

    private final MinioClient minioClient;
    private final MinioProperties properties;

    public MinioService(MinioClient minioClient, MinioProperties properties) {
        this.minioClient = minioClient;
        this.properties = properties;
    }

    public void upload(MultipartFile file, String objectName) throws Exception {
        createBucketIfAbsent(properties.getBucketName());

        try (InputStream inputStream = file.getInputStream()) {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(properties.getBucketName())
                            .object(objectName)
                            .stream(inputStream, file.getSize(), -1)
                            .contentType(resolveContentType(file))
                            .build()
            );
        }
    }

    public String getPresignedUrl(String objectName) throws Exception {
        return minioClient.getPresignedObjectUrl(
                GetPresignedObjectUrlArgs.builder()
                        .method(Method.GET)
                        .bucket(properties.getBucketName())
                        .object(objectName)
                        .expiry(60 * 60)
                        .build()
        );
    }

    private void createBucketIfAbsent(String bucketName) throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder()
                        .bucket(bucketName)
                        .build()
        );

        if (!exists) {
            minioClient.makeBucket(
                    MakeBucketArgs.builder()
                            .bucket(bucketName)
                            .build()
            );
        }
    }

    private String resolveContentType(MultipartFile file) {
        String contentType = file.getContentType();
        if (contentType == null || contentType.isBlank()) {
            return "application/octet-stream";
        }
        return contentType;
    }
}
```

控制器示例：

```java
@RestController
@RequestMapping("/files")
public class FileController {

    private final MinioService minioService;

    public FileController(MinioService minioService) {
        this.minioService = minioService;
    }

    @PostMapping
    public void upload(@RequestParam("file") MultipartFile file) throws Exception {
        String objectName = "upload/" + UUID.randomUUID() + "-" + file.getOriginalFilename();
        minioService.upload(file, objectName);
    }

    @GetMapping("/url")
    public String getUrl(@RequestParam String objectName) throws Exception {
        return minioService.getPresignedUrl(objectName);
    }
}
```

这个示例只展示接入方式。真实项目里不建议直接使用原始文件名作为对象名，也不建议把异常原样抛给前端。

## 对象命名

对象名不是普通文件名，它更像一个全局访问路径。常见命名方式：

```text
业务类型/日期/业务ID/随机ID.扩展名
```

例如：

```text
avatar/2026/08/22/user-10001-a8f3.jpg
contract/2026/08/22/order-90001.pdf
export/2026/08/22/report-6d21.xlsx
```

命名时要注意：

- 避免直接使用用户上传的原始文件名。
- 保留扩展名，方便浏览器识别和下载。
- 对象名要能表达业务归属，方便排查。
- 不要把敏感业务信息暴露在公开 URL 里。

如果对象名只叫 `1.jpg`、`2.jpg`，短期很清爽，长期会让排查问题的人体验到一种朴素的绝望。

## 访问控制

MinIO 常见访问方式有三种：

| 方式 | 适用场景 | 说明 |
| ---- | -------- | ---- |
| 私有桶 | 默认推荐 | 后端校验权限后生成预签名 URL |
| 公开读 | 头像、商品图、公开附件 | 任何人拿到地址都可以访问 |
| 反向代理 | 统一域名、HTTPS、缓存 | 通过 Nginx、网关或 CDN 对外暴露 |

推荐策略：

- 私有文件使用私有桶和预签名 URL。
- 公开静态资源可以使用公开读，再配合 CDN。
- 上传接口必须经过业务鉴权和文件校验。
- 管理控制台不要暴露到公网。
- 访问密钥不要写死在代码仓库里。

## 生产注意事项

生产环境使用 MinIO 时，需要重点关注：

- **高可用**：生产环境通常需要多节点和多磁盘部署。
- **数据可靠性**：关注纠删码、磁盘故障、节点故障和备份策略。
- **网络入口**：API 和 Console 分开暴露，Console 应限制访问来源。
- **HTTPS**：公网访问必须使用 HTTPS，避免预签名 URL 被窃听。
- **生命周期**：临时导出文件、日志归档文件可以配置过期清理。
- **监控告警**：关注磁盘容量、节点状态、请求错误率和延迟。
- **权限治理**：不同应用使用不同账号，按桶或路径控制权限。

MinIO 能把文件存起来，但它不会替你决定哪些文件应该被谁访问、保留多久、出了故障由谁负责。对象存储只是工具，治理才是系统。

## 常见问题

### 控制台能打开，但程序连不上

检查应用连接的是 API 端口 `9000`，不是 Console 端口 `9001`。

### 上传成功，但浏览器无法访问

检查桶策略是否允许公开读。如果桶是私有的，需要通过后端生成预签名 URL。

### 预签名 URL 访问失败

检查：

- URL 是否已过期。
- 对象名是否完全一致。
- MinIO 服务端时间和应用服务器时间是否偏差过大。
- 客户端访问的域名是否和签名时使用的 endpoint 一致。

### 文件下载时类型不正确

上传时设置正确的 `contentType`。如果不设置，浏览器可能按二进制流处理。

### 对象覆盖了旧文件

同一个 Bucket 下对象名相同会覆盖原对象。上传前应该生成足够唯一的对象名，或者按业务规则明确允许覆盖。

## 使用建议

- 数据库保存文件元数据，MinIO 保存文件本体。
- 私有文件优先使用预签名 URL。
- 对象名按业务维度规划，不要直接使用原始文件名。
- 生产环境不要使用默认账号和弱密码。
- Console 和 API 分开治理，Console 不要直接暴露公网。
- 上传接口要限制文件大小、文件类型和用户权限。
- 重要文件要有备份、生命周期和删除恢复策略。

MinIO 的定位很清楚：它负责可靠地保存和访问对象。把数据库、业务权限、对象命名、访问策略和运维治理搭好，它就是一个很好用的文件底座；这些边界没有想清楚，它也只会诚实地放大混乱。倒也公平，软件通常不会替人类承担设计偷懒的后果。
