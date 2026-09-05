+++
date = '2026-09-05T11:00:00+08:00'
draft = false
title = 'Spring Boot 文件上传：MultipartFile、原始请求体与对象存储直传'
+++

上传图片看上去只是“选择一个文件，再发给后端”。实际上，这条链路同时涉及浏览器编码、HTTP `Content-Type`、Spring 参数解析、文件大小限制、临时文件、存储位置、访问地址和安全校验。只写出 `MultipartFile file` 并不等于上传功能已经完成；那只是 Spring 替你打开了包裹的第一层。

本文以 Spring Boot 3 / Spring MVC 为例，先完整说明最常用的 `MultipartFile` 方案，再解释**不使用 `MultipartFile` 时如何上传图片**：仍使用 multipart 但改用 Servlet `Part`、发送原始二进制请求体，以及浏览器直传对象存储。每种方案都同时给出前端和后端的职责。

## 一、先理解：图片不是 JSON 字段

普通 JSON 请求可以这样表示：

```json
{
  "title": "春天的照片",
  "coverUrl": "https://example.com/cover.jpg"
}
```

但一张图片本质是二进制字节，不能直接塞进 JSON。浏览器上传本地文件时，最常用的请求格式是 `multipart/form-data`：请求体由多个 part 组成，每个 part 都有自己的头和内容。

```http
POST /api/files/images HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryabc

------WebKitFormBoundaryabc
Content-Disposition: form-data; name="file"; filename="avatar.png"
Content-Type: image/png

<图片二进制字节>
------WebKitFormBoundaryabc--
```

`boundary` 用于分隔每一段。Spring 的 multipart 解析器会先识别这种请求，再把名称为 `file` 的 part 交给 Controller。`MultipartFile` 就是 Spring MVC 对“文件 part”的抽象，而不是浏览器唯一的上传方式。

## 二、方案一：使用 MultipartFile 上传图片

这是业务系统最常用、可读性也最好的方案。浏览器把文件放进 `FormData`，后端使用 `@RequestParam` 或 `@RequestPart` 接收。

### 1. 前端：用 FormData 发送文件

下面以 Vue 3 的组件为例。原生 HTML、React 或任何能拿到 `File` 对象的前端框架，思路都相同。

```vue
<script setup lang="ts">
import { ref } from 'vue'

const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const uploading = ref(false)
const errorMessage = ref('')

function selectImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }

  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    errorMessage.value = '请选择 JPG、PNG 或 WebP 图片'
    input.value = ''
    return
  }

  if (file.size > 5 * 1024 * 1024) {
    errorMessage.value = '图片不能超过 5 MB'
    input.value = ''
    return
  }

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }

  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  errorMessage.value = ''
}

async function uploadImage() {
  const file = selectedFile.value
  if (!file || uploading.value) {
    return
  }

  const formData = new FormData()
  formData.append('file', file)

  uploading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch('/api/files/images', {
      method: 'POST',
      body: formData
    })

    const result = await response.json()
    if (!response.ok) {
      throw new Error(result.message || '上传失败')
    }

    console.info('图片地址：', result.data.url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '上传失败'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <section>
    <input
      type="file"
      accept="image/jpeg,image/png,image/webp"
      @change="selectImage"
    >
    <img v-if="previewUrl" :src="previewUrl" alt="待上传图片预览">
    <button :disabled="!selectedFile || uploading" @click="uploadImage">
      {{ uploading ? '上传中…' : '上传图片' }}
    </button>
    <p v-if="errorMessage">{{ errorMessage }}</p>
  </section>
</template>
```

这里有几个不能省略的细节：

- `input.files[0]` 是浏览器提供的 `File` 对象，继承自 `Blob`，包含名称、大小、媒体类型和字节内容。
- `accept` 与前端大小校验只改善体验，用户可以绕过它们；**后端仍必须校验**。
- `URL.createObjectURL` 用于本地预览，不会上传文件。替换或卸载预览时应调用 `URL.revokeObjectURL` 释放地址。
- 传 `FormData` 时，**不要手动设置 `Content-Type: multipart/form-data`**。浏览器会自动附带包含 boundary 的正确头；手动覆盖后通常缺少 boundary，服务端无法解析。
- 如果封装的 Axios 拦截器默认给所有请求加 `application/json`，上传接口必须排除这条默认规则。

使用 Axios 时也一样：

```ts
const formData = new FormData()
formData.append('file', file)

await axios.post('/api/files/images', formData)
```

浏览器环境中通常同样不需要手动填写 multipart 的 `Content-Type`。

### 2. 后端：Controller 接收 MultipartFile

先定义一个稳定的响应对象。这里省略项目已有的统一返回体也可以，但不要直接把服务器磁盘路径返回给前端。

```java
public record UploadedFileResponse(
        String fileId,
        String url,
        String originalFilename,
        long size
) {
}
```

Controller 只处理 HTTP 参数和响应；写磁盘或上传对象存储的动作放在 Service：

```java
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/files")
public class FileController {

    private final ImageStorageService imageStorageService;

    public FileController(ImageStorageService imageStorageService) {
        this.imageStorageService = imageStorageService;
    }

    @PostMapping("/images")
    public ResponseEntity<UploadedFileResponse> uploadImage(
            @RequestParam("file") MultipartFile file) throws IOException {

        UploadedFileResponse result = imageStorageService.store(file);
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }
}
```

`@RequestParam("file")` 中的名称必须与前端 `formData.append('file', file)` 的第一个参数一致。前端叫 `image`、后端写 `file`，Spring 并不会替你猜测它们是同一个东西。

### 3. 后端：校验并安全保存文件

下面是保存到本机目录的示例。生产中更常见的最终存储位置是对象存储，后文会说明；本地存储适合开发环境、单机工具或由共享文件系统承载的明确场景。

```java
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;

@Service
public class ImageStorageService {

    private static final long MAX_IMAGE_SIZE = 5 * 1024 * 1024;

    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            MediaType.IMAGE_JPEG_VALUE,
            MediaType.IMAGE_PNG_VALUE,
            "image/webp"
    );

    private final Path uploadRoot;
    private final String publicBaseUrl;

    public ImageStorageService(
            @Value("${app.upload.root}") String uploadRoot,
            @Value("${app.upload.public-base-url}") String publicBaseUrl) {
        this.uploadRoot = Path.of(uploadRoot).toAbsolutePath().normalize();
        this.publicBaseUrl = publicBaseUrl.replaceAll("/$", "");
    }

    public UploadedFileResponse store(MultipartFile file) throws IOException {
        validate(file);

        String extension = extensionByContentType(file.getContentType());
        String storedName = UUID.randomUUID() + extension;
        String relativeDirectory = "images/" + LocalDate.now();
        Path directory = uploadRoot.resolve(relativeDirectory).normalize();
        Path target = directory.resolve(storedName).normalize();

        if (!target.startsWith(uploadRoot)) {
            throw new IllegalArgumentException("非法的保存路径");
        }

        Files.createDirectories(directory);
        try (var input = file.getInputStream()) {
            Files.copy(input, target, StandardCopyOption.REPLACE_EXISTING);
        }

        String url = publicBaseUrl + "/" + relativeDirectory + "/" + storedName;
        return new UploadedFileResponse(
                storedName,
                url,
                safeOriginalFilename(file.getOriginalFilename()),
                file.getSize()
        );
    }

    private static void validate(MultipartFile file) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("请选择图片");
        }

        if (file.getSize() > MAX_IMAGE_SIZE) {
            throw new IllegalArgumentException("图片不能超过 5 MB");
        }

        if (!ALLOWED_CONTENT_TYPES.contains(file.getContentType())) {
            throw new IllegalArgumentException("只支持 JPG、PNG、WebP 图片");
        }
    }

    private static String extensionByContentType(String contentType) {
        return switch (contentType) {
            case MediaType.IMAGE_JPEG_VALUE -> ".jpg";
            case MediaType.IMAGE_PNG_VALUE -> ".png";
            case "image/webp" -> ".webp";
            default -> throw new IllegalArgumentException("不支持的图片类型");
        };
    }

    private static String safeOriginalFilename(String originalFilename) {
        return originalFilename == null ? "" : Path.of(originalFilename).getFileName().toString();
    }
}
```

配置示例：

```yaml
spring:
  servlet:
    multipart:
      max-file-size: 5MB
      max-request-size: 6MB

app:
  upload:
    root: /data/blog-uploads
    public-base-url: https://static.example.com/uploads
```

`max-file-size` 限制单个文件，`max-request-size` 限制整个 multipart 请求。后者应略大于前者，因为表单字段和 multipart 分隔符也占用请求大小。

### 4. @RequestParam、@RequestPart 与多个文件

只有一个文件时，`@RequestParam MultipartFile file` 最直接。如果一次请求还要上传 JSON 元数据，推荐 `@RequestPart`：

```java
public record CreatePostRequest(String title, String summary) {
}

@PostMapping("/posts")
public ResponseEntity<Void> createPost(
        @RequestPart("data") CreatePostRequest data,
        @RequestPart("cover") MultipartFile cover) {
    // 保存文章元数据和封面
    return ResponseEntity.status(HttpStatus.CREATED).build();
}
```

前端要将 JSON part 显式包装为 `application/json`：

```ts
const formData = new FormData()
formData.append(
  'data',
  new Blob([JSON.stringify({ title: 'Spring 上传', summary: '封面示例' })], {
    type: 'application/json'
  })
)
formData.append('cover', file)

await fetch('/api/posts', {
  method: 'POST',
  body: formData
})
```

多个同名文件可用 `List<MultipartFile>` 接收：

```java
@PostMapping("/images/batch")
public List<UploadedFileResponse> uploadImages(
        @RequestParam("files") List<MultipartFile> files) throws IOException {
    return files.stream()
            .map(file -> {
                try {
                    return imageStorageService.store(file);
                } catch (IOException exception) {
                    throw new UncheckedIOException(exception);
                }
            })
            .toList();
}
```

前端重复追加相同字段名：

```ts
const formData = new FormData()
for (const file of selectedFiles) {
  formData.append('files', file)
}
```

批量上传还要提前设计失败语义：是任意一个失败就整体失败，还是返回每个文件的独立结果。没有这一约定，前端只能靠猜测重试，后端则会得到重复文件；两边都会很不愉快。

## 三、不使用 MultipartFile，不代表只有一种做法

“不用 `MultipartFile` 怎么上传图片”至少有三种完全不同的含义：

| 方案 | 浏览器请求格式 | Spring 接收方式 | 适合场景 |
| ---- | -------------- | --------------- | -------- |
| Servlet `Part` | `multipart/form-data` | `Part` | 保留 multipart，但不依赖 Spring 的 `MultipartFile` 抽象 |
| 原始二进制流 | `image/png` 或 `application/octet-stream` | `HttpServletRequest.getInputStream()` | 单文件、协议可控、需要流式转发 |
| Base64 JSON | `application/json` | `@RequestBody` | 小图片、已有纯 JSON 协议；通常不推荐 |
| 对象存储直传 | 浏览器直接 `PUT` / `POST` 到存储服务 | 后端只签名、确认元数据 | 大文件、高并发、生产环境首选 |

前三种仍可能让应用服务器接触文件字节；对象存储直传则让文件绕过业务应用服务器。先选清楚链路，再讨论 Controller 参数类型，才不会本末倒置。

## 四、方案二：仍使用 multipart，但改用 Servlet Part

`Part` 是 Servlet 标准 API，Spring MVC 可以直接注入。它依然要求前端使用 `FormData`，因此浏览器请求并没有变化；变化仅在后端不再接收 `MultipartFile`。

### 1. 前端：与 MultipartFile 方案相同

```ts
const formData = new FormData()
formData.append('file', file)

await fetch('/api/files/images-part', {
  method: 'POST',
  body: formData
})
```

### 2. 后端：使用 Part

```java
import jakarta.servlet.http.Part;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

@RestController
public class PartUploadController {

    @PostMapping("/api/files/images-part")
    public ResponseEntity<String> uploadByPart(@RequestParam("file") Part file)
            throws IOException {
        if (file.getSize() == 0 || file.getSize() > 5 * 1024 * 1024) {
            return ResponseEntity.badRequest().body("图片大小不合法");
        }

        String contentType = file.getContentType();
        if (!"image/jpeg".equals(contentType) && !"image/png".equals(contentType)) {
            return ResponseEntity.badRequest().body("只支持 JPG 和 PNG");
        }

        Path directory = Path.of("/data/blog-uploads/images").toAbsolutePath().normalize();
        Files.createDirectories(directory);

        Path target = directory.resolve(UUID.randomUUID() + ".bin");
        try (var input = file.getInputStream()) {
            Files.copy(input, target, StandardCopyOption.REPLACE_EXISTING);
        }

        return ResponseEntity.status(HttpStatus.CREATED).body("上传成功");
    }
}
```

`Part` 的常用方法包括 `getInputStream()`、`getSubmittedFileName()`、`getSize()` 和 `getContentType()`。它适合需要直接面向 Servlet 标准 API 的场景，但在 Spring Boot 项目里，`MultipartFile` 通常代码更简洁，也更容易与校验、测试和第三方存储 SDK 集成。

需要特别澄清：**改成 `Part` 不是绕过 multipart 解析和临时存储的魔法**。请求仍是 multipart，Servlet 容器仍需要解析它。它解决的是 API 依赖选择，不是“大文件不落盘”或“内存一定更省”的问题。

## 五、方案三：发送原始二进制请求体，不使用 multipart

如果一个接口只上传一个文件，并且元数据很少，可以让 HTTP 请求体直接就是图片字节。此时请求不是 `multipart/form-data`，后端也不能再用 `MultipartFile` 或 `Part` 解析文件字段。

```text
POST /api/files/raw-image
Content-Type: image/png
X-File-Name: avatar.png

<图片二进制字节>
```

### 1. 前端：File 直接作为 body

```ts
async function uploadRawImage(file: File) {
  const response = await fetch('/api/files/raw-image', {
    method: 'POST',
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
      'X-File-Name': encodeURIComponent(file.name)
    },
    body: file
  })

  if (!response.ok) {
    throw new Error('上传失败')
  }

  return response.json()
}
```

`File` 可以直接作为 `fetch` 的 `body`，不必先读成字符串。若前后端不同源，`X-File-Name` 是自定义请求头，服务端的 CORS 配置必须允许它；否则预检请求会失败。

### 2. 后端：从输入流复制，而不是读成 byte[]

不要写成 `@RequestBody byte[] bytes` 来处理大图片。它会先把整个请求体放入 JVM 堆内存：十个 20 MB 的并发上传，很容易把“文件上传”写成一次内存压测。

下面直接从 `HttpServletRequest` 读取流，并在复制时强制限制字节数：

```java
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Set;
import java.util.UUID;

@RestController
@RequestMapping("/api/files")
public class RawImageUploadController {

    private static final long MAX_IMAGE_SIZE = 5 * 1024 * 1024;
    private static final Set<String> ALLOWED_TYPES = Set.of(
            "image/jpeg", "image/png", "image/webp"
    );

    @PostMapping("/raw-image")
    public ResponseEntity<String> uploadRawImage(HttpServletRequest request)
            throws IOException {
        String contentType = request.getContentType();
        long contentLength = request.getContentLengthLong();

        if (!ALLOWED_TYPES.contains(contentType)) {
            return ResponseEntity.badRequest().body("不支持的图片类型");
        }

        if (contentLength == 0 || contentLength > MAX_IMAGE_SIZE) {
            return ResponseEntity.badRequest().body("图片大小不合法");
        }

        Path directory = Path.of("/data/blog-uploads/raw-images").toAbsolutePath().normalize();
        Files.createDirectories(directory);

        Path target = directory.resolve(UUID.randomUUID() + ".upload");
        try (InputStream input = request.getInputStream();
             OutputStream output = Files.newOutputStream(
                     target,
                     StandardOpenOption.CREATE_NEW,
                     StandardOpenOption.WRITE)) {
            copyAtMost(input, output, MAX_IMAGE_SIZE);
        } catch (IOException exception) {
            Files.deleteIfExists(target);
            throw exception;
        }

        return ResponseEntity.status(HttpStatus.CREATED).body("上传成功");
    }

    private static void copyAtMost(InputStream input, OutputStream output, long maxBytes)
            throws IOException {
        byte[] buffer = new byte[8192];
        long total = 0;
        int read;

        while ((read = input.read(buffer)) != -1) {
            total += read;
            if (total > maxBytes) {
                throw new IOException("图片超过大小限制");
            }
            output.write(buffer, 0, read);
        }

        if (total == 0) {
            throw new IOException("图片为空");
        }
    }
}
```

这里即使已经检查了 `Content-Length`，仍在 `copyAtMost` 中限制实际读取长度。因为 HTTP 请求可以使用分块传输，`Content-Length` 可能未知（`-1`），也不能把客户端提供的长度当作绝对可信的安全边界。

原始流上传的优点是协议简单、可以持续流式转发到其他服务；缺点是文件名、业务字段、校验参数都要另行放在 URL、请求头或额外接口中，而且通用表单工具支持较弱。对于带多个文件和多项字段的页面，multipart 通常更合适。

## 六、方案四：Base64 放进 JSON，能用但通常不该优先选择

浏览器可以把图片读为 Base64 字符串，再放进 JSON：

```ts
function readAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const dataUrl = await readAsDataUrl(file)

await fetch('/api/files/base64-image', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: file.name,
    image: dataUrl
  })
})
```

`dataUrl` 形如 `data:image/png;base64,iVBORw0...`。后端要先验证前缀并去掉 `data:image/...;base64,`，再进行 Base64 解码：

```java
public record Base64ImageRequest(String filename, String image) {
}

@PostMapping("/api/files/base64-image")
public ResponseEntity<String> uploadBase64Image(
        @RequestBody Base64ImageRequest request) throws IOException {
    String prefix = "data:image/png;base64,";
    if (request.image() == null || !request.image().startsWith(prefix)) {
        return ResponseEntity.badRequest().body("只支持 PNG Data URL");
    }

    byte[] bytes = Base64.getDecoder().decode(request.image().substring(prefix.length()));
    if (bytes.length == 0 || bytes.length > 5 * 1024 * 1024) {
        return ResponseEntity.badRequest().body("图片大小不合法");
    }

    Path target = Path.of("/data/blog-uploads/base64", UUID.randomUUID() + ".png");
    Files.createDirectories(target.getParent());
    Files.write(target, bytes, StandardOpenOption.CREATE_NEW);
    return ResponseEntity.status(HttpStatus.CREATED).body("上传成功");
}
```

这个方案的主要问题不在于“能不能解码”，而是成本：Base64 让数据体积约增加三分之一，前端需要把完整文件读进内存，后端 JSON 反序列化和 Base64 解码也会产生大对象。上面的示例只适合严格限制大小的小图片或历史协议兼容。

不要把“JSON 比 multipart 熟悉”误当成选择理由。对于真实文件上传，它通常是更昂贵、更脆弱的编码方式。

## 七、方案五：浏览器直传对象存储，生产环境更常见

当图片或文件较大、上传并发高、应用部署了多个实例时，让每个文件都先经过 Spring 应用，会占用应用服务器的带宽、线程、临时磁盘与网络出口。更合理的结构通常是：后端负责鉴权和签发短期上传凭证，浏览器直接上传到 S3、OSS、COS、MinIO 等对象存储。

```text
浏览器                    Spring 应用                 对象存储
  |  1. 请求上传凭证            |                         |
  | -------------------------> |                         |
  |  2. 校验身份、生成对象键和签名 |                         |
  | <------------------------- |                         |
  |  3. PUT / POST 图片（直传）  | ---------------------> |
  |  4. 通知业务接口确认上传       |                         |
  | -------------------------> |                         |
```

### 1. 后端：只签发受控的上传信息

后端生成对象键时应完全自行决定目录和文件名，例如 `images/2026/09/<uuid>.png`；不要让前端指定任意对象键，更不能把云存储长期密钥发给浏览器。

下面用伪代码表达签名接口，具体 SDK 因对象存储厂商不同而不同：

```java
public record CreateUploadRequest(String contentType, long size) {
}

public record UploadTicket(
        String objectKey,
        String uploadUrl,
        Instant expiresAt,
        Map<String, String> requiredHeaders
) {
}

@PostMapping("/api/uploads/tickets")
public UploadTicket createUploadTicket(@RequestBody CreateUploadRequest request) {
    uploadPolicy.validate(request.contentType(), request.size());

    String extension = uploadPolicy.extensionByContentType(request.contentType());
    String objectKey = "images/" + LocalDate.now() + "/" + UUID.randomUUID() + extension;

    return objectStorage.createPresignedPutUrl(
            objectKey,
            request.contentType(),
            Duration.ofMinutes(5)
    );
}
```

签名中应约束至少这些内容：对象键、请求方法、有效期、允许的 `Content-Type`、文件大小范围，以及必要时的校验和。上传成功后，前端调用“确认上传”接口，后端根据对象键检查对象是否存在、大小是否符合预期，再将它关联到文章、用户头像等业务数据。不要仅凭前端说“我上传完成了”就把文件记为可用。

### 2. 前端：先拿凭证，再直接 PUT 文件

```ts
type UploadTicket = {
  objectKey: string
  uploadUrl: string
  requiredHeaders: Record<string, string>
}

async function uploadDirectly(file: File) {
  const ticketResponse = await fetch('/api/uploads/tickets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contentType: file.type,
      size: file.size
    })
  })

  if (!ticketResponse.ok) {
    throw new Error('无法获取上传凭证')
  }

  const ticket = await ticketResponse.json() as UploadTicket
  const uploadResponse = await fetch(ticket.uploadUrl, {
    method: 'PUT',
    headers: ticket.requiredHeaders,
    body: file
  })

  if (!uploadResponse.ok) {
    throw new Error('图片上传到存储服务失败')
  }

  const confirmResponse = await fetch('/api/uploads/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ objectKey: ticket.objectKey })
  })

  if (!confirmResponse.ok) {
    throw new Error('上传结果确认失败')
  }

  return confirmResponse.json()
}
```

对象存储必须配置 CORS，允许前端站点的 Origin、`PUT` 或 `POST` 方法，以及签名需要的请求头（例如 `Content-Type`、校验和或厂商特定头）。配置时应限制到实际域名，不要为了省事设置任意 Origin 和任意请求头。

直传的关键收益是：**大文件字节不穿过 Spring 应用服务器**。Spring 仍然负责认证、授权、签名策略、上传确认与业务关联，安全边界并没有消失，只是职责被放回了合适的位置。

## 八、文件校验与存储：不要相信文件名和 Content-Type

无论使用哪种传输方式，下面这些规则都适用：

### 1. 先限制大小、数量和请求频率

- 在网关、Web 服务器和 Spring 中设置大小限制，不能只依赖其中一层。
- 限制单次文件数与单个用户的上传频率、总配额。
- 对超大文件使用分片或对象存储的 multipart upload，而不是无限提高 JVM 和反向代理限制。

### 2. MIME 类型只是客户端声明

`file.getContentType()`、请求头 `Content-Type` 和文件后缀都可被伪造。它们可以作为第一层快速过滤，但高风险场景还应读取文件头（magic number）或使用可靠的内容检测库，并真正解析图片。

例如 PNG 文件起始字节应为：

```text
89 50 4E 47 0D 0A 1A 0A
```

JPEG 通常以：

```text
FF D8 FF
```

开头。文件头匹配也不等于绝对安全；若需要进一步处理图片，应限制像素尺寸、解码耗时和内存，防止畸形图片或解压炸弹消耗资源。

### 3. 永远不要使用原始文件名作为服务器路径

下面的写法存在路径穿越和覆盖风险：

```java
Path target = uploadRoot.resolve(file.getOriginalFilename());
```

攻击者可以提交包含 `../` 的文件名，或反复使用同一个名称。正确做法是：后端生成不可预测的存储名，保留原始文件名时仅作为数据库展示字段，并去掉路径信息。

### 4. 上传目录不要等同于应用静态资源目录

不要把用户文件写到 classpath、`src/main/resources/static` 或已打包的应用目录。这些目录在重启、重新部署或多实例环境中都不可靠。

可行做法是：

- 应用写入独立挂载目录，再由 Nginx 映射为只读访问路径。
- 使用共享文件系统，并明确备份、容量、权限与多实例一致性策略。
- 使用对象存储，通过 CDN 或受控下载接口提供访问。

如果上传内容可能包含 HTML、SVG 或其他可执行内容，不要直接与主站同源公开访问；应单独域名、设置安全响应头，并优先只允许必要的图片格式。

### 5. 记录可追踪信息并处理失败清理

数据库中建议记录文件 ID、存储键、原始文件名、探测后的类型、大小、上传者、创建时间、状态和引用关系。写入文件成功但业务保存失败时，要么删除孤立对象，要么记录为待清理状态并由定时任务回收。

上传接口的日志只记录文件 ID、对象键、大小、类型、用户和 trace ID；不要打印完整 Base64 内容、Cookie、Authorization 或签名 URL。日志是为了定位问题，不是为了把敏感数据复制到更多地方。

## 九、如何选择方案

| 需求 | 更合适的方案 | 原因 |
| ---- | ------------ | ---- |
| 后台表单上传头像、文章封面 | `MultipartFile` + `FormData` | API 清晰，开发和维护成本低 |
| 上传时还有 JSON 元数据 | `@RequestPart` + `MultipartFile` | 文件与结构化字段可在一个请求中表达 |
| 需要 Servlet 标准 API | `Part` | 不依赖 Spring 的文件抽象，但仍是 multipart |
| 单文件、需要流式代理到别的服务 | 原始二进制请求体 + `InputStream` | 无需 multipart，避免整体读入内存 |
| 旧协议必须全是 JSON，且图片很小 | Base64 JSON | 可兼容，但体积和内存成本较高 |
| 大文件、高并发、多实例生产系统 | 浏览器直传对象存储 | 文件不经过应用服务器，扩展性最好 |

大多数普通 Spring Boot 管理后台，先选择 `MultipartFile` 就够了。只有当协议约束、流式处理或基础设施条件明确要求时，才需要绕开它。为了显得“底层”而放弃框架提供的清晰抽象，通常只会多得到一些不必要的边界条件；系统并不会因此更成熟。

## 十、总结

`MultipartFile` 是 Spring MVC 接收 multipart 文件的便利抽象，前端对应 `FormData`，这是最常见且适合多数业务图片上传的组合。实现时要记住：

- 前端传 `FormData` 时不手动设置 multipart `Content-Type`。
- 后端字段名必须与前端 form 字段名一致，并设置 Spring 的文件与请求大小限制。
- 文件名、后缀和客户端 MIME 类型都不可信；保存名由后端生成，必要时检查文件真实内容。
- 不使用 `MultipartFile` 时，可以用 `Part` 接 multipart、用 `InputStream` 接原始二进制流，或让浏览器直传对象存储。
- Base64 JSON 虽然可行，但有明显体积与内存代价，通常只适合小文件兼容场景。
- 生产环境还必须考虑权限、CORS、签名、隔离访问、失败清理、日志脱敏和可追踪性。

文件上传从来不只是“把字节保存下来”。真正完整的实现，是让文件能安全抵达、可被正确访问、失败时可恢复，并且在问题出现时能够知道它究竟停在了哪一段链路上。
