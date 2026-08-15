+++
date = '2025-10-02T22:25:43+08:00'
draft = false
title = 'MinIO'
+++

>  **MinIO** 属于 **对象存储软件**，它和一类相似的软件/服务一起解决了 **海量文件存储与访问** 的问题

**MinIO** 是一个高性能的 **对象存储服务**（Object Storage），兼容 **Amazon S3 API**。

可以用来存储 **图片、视频、日志、备份、文件** 等非结构化数据。

核心特性：

- 部署简单，支持单机 / 集群
- 100% 兼容 Amazon S3 SDK
- 性能强，适合大数据、机器学习场景
- 免费开源

#### 它有三大基本概念

**Bucket（桶）**：相当于一个文件夹，存放一类对象。

**Object（对象）**：实际存储的文件，比如图片、视频、文档。

**Policy（策略）**：权限控制，支持私有/公有/自定义。

MinIO 需要部署在自己的服务器上，启动后会提供两个接口

**API 端口（默认 9000）** -> 用于客户端/服务端上传下载文件

**控制台端口（默认 9001）** -> Web 界面，方便你管理 Bucket、文件

#### MinIO 的功能

##### 存储客户端上传的文件

用户上传头像、商品图片、视频、日志等

客户端访问后端 API，调用 MinIO。后端把文件存到 MinIO 的某个 **Bucket** 里

##### 供客户端访问文件

可以通过 **URL 直链** 或 **临时签名 URL** 提供访问权限

- 例如：

  - 公共资源 -> 直接用公开 URL 访问
  - 私有资源 -> 生成带签名的 **临时链接**，比如 1 小时有效

  > 这样既能保证安全，又能让客户端方便获取

典型架构

```bash
[客户端 App] ←-> [你的后端服务] ←-> [MinIO Server]
                           ↑
                           |  API（上传/下载）
                           |
                       [MinIO Console 管理]
```

### Java 集成 MinIO

引入依赖

```java
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.2</version>
</dependency>
```

初始化客户端

```java
MinioClient minioClient =
    MinioClient.builder()
        .endpoint("http://127.0.0.1:9000")
        .credentials("minioadmin", "minioadmin")
        .build();
```

创建桶

```java
if (!minioClient.bucketExists(BucketExistsArgs.builder().bucket("mybucket").build())) {
    minioClient.makeBucket(MakeBucketArgs.builder().bucket("mybucket").build());
}
```

上传文件

```java
minioClient.uploadObject(
    UploadObjectArgs.builder()
        .bucket("mybucket")
        .object("hello.jpg")       // 存储对象名
        .filename("D:/hello.jpg")  // 本地路径
        .build());
```

下载文件

```java
minioClient.downloadObject(
    DownloadObjectArgs.builder()
        .bucket("mybucket")
        .object("hello.jpg")
        .filename("D:/downloaded.jpg")
        .build());
```

获取文件

```java
String url = minioClient.getPresignedObjectUrl(
    GetPresignedObjectUrlArgs.builder()
        .method(Method.GET)
        .bucket("mybucket")
        .object("hello.jpg")
        .expiry(60 * 60) // 链接1小时有效
        .build());
System.out.println("文件访问地址: " + url);
```

### 在 SpringBoot 项目中集成

引入依赖

```xml
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.2</version>
</dependency>
```

配置 `apolication.yml`

```yaml
minio:
  endpoint: http://127.0.0.1:9000     # MinIO API地址
  accessKey: minioadmin               # 账号
  secretKey: minioadmin               # 密码
  bucketName: mybucket                # 默认桶
```

配置类 MinioConfig

```java
@Configuration
public class MinioConfig {
    @Value("${minio.endpoint}")
    private String endpoint;

    @Value("${minio.accessKey}")
    private String accessKey;

    @Value("${minio.secretKey}")
    private String secretKey;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }
}
```

封装工具类 MinioService

```java
@Service
public class MinioService {
    private final MinioClient minioClient;

    @Value("${minio.bucketName}")
    private String bucketName;

    public MinioService(MinioClient minioClient) {
        this.minioClient = minioClient;
    }

    /** 创建桶 */
    public void createBucket(String bucket) throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(bucket).build()
        );
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
        }
    }

    /** 上传文件 */
    public void uploadFile(MultipartFile file, String objectName) throws Exception {
        createBucket(bucketName);
        try (InputStream inputStream = file.getInputStream()) {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucketName)
                            .object(objectName)
                            .stream(inputStream, file.getSize(), -1)
                            .contentType(file.getContentType())
                            .build()
            );
        }
    }

    /** 获取临时访问链接 */
    public String getFileUrl(String objectName) throws Exception {
        return minioClient.getPresignedObjectUrl(
                GetPresignedObjectUrlArgs.builder()
                        .bucket(bucketName)
                        .object(objectName)
                        .method(Method.GET)
                        .expiry(60 * 60)  // 有效期1小时
                        .build()
        );
    }
}
```
