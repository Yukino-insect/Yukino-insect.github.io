+++
date = '2026-02-19T12:15:06+08:00'
draft = false
title = 'Java 原生 URL 操作'
+++

Java 标准库里处理 URL/URI 主要会用到三类 API：

1. `java.net.URI`：表示统一资源标识符，适合解析、拼接、编码和路径转换。
2. `java.net.URL`：表示统一资源定位符，历史更早，带有打开连接的能力。
3. `java.net.http.HttpClient`：JDK 11 引入的 HTTP 客户端，用于真正发起 HTTP 请求。

日常开发里，如果只是解析和拼接地址，优先使用 `URI`。`URL` 更像“可以打开连接的地址”，不适合承担所有字符串处理工作。

## 一、解析 URI

```java
URI uri = URI.create("https://example.com/a/b.png?x=1#top");

System.out.println(uri.getScheme());    // https
System.out.println(uri.getHost());      // example.com
System.out.println(uri.getPath());      // /a/b.png
System.out.println(uri.getQuery());     // x=1
System.out.println(uri.getFragment());  // top
```

`URI.create(...)` 适合处理已经确定合法的字符串。如果输入来自用户，建议捕获异常，给出明确错误。

```java
try {
    URI uri = new URI(input);
} catch (URISyntaxException e) {
    throw new IllegalArgumentException("非法 URI: " + input, e);
}
```

## 二、拼接路径

`URI#resolve` 可以根据基准地址拼接相对路径：

```java
URI base = URI.create("https://cdn.example.com/models/");
URI file = base.resolve("30909800.glb");

System.out.println(file);
// https://cdn.example.com/models/30909800.glb
```

这里最容易错的是尾部 `/`。

```java
URI.create("https://cdn.example.com/models/")
        .resolve("a.glb");
// https://cdn.example.com/models/a.glb

URI.create("https://cdn.example.com/models")
        .resolve("a.glb");
// https://cdn.example.com/a.glb
```

没有尾部 `/` 时，`models` 会被当作文件名，而不是目录名。若 base 表示目录，就把 `/` 写上。小事，但很会折磨人。

## 三、拼 Query 参数

Query 参数要编码，不要直接字符串拼接用户输入。

```java
String query = "name=" + URLEncoder.encode("张三", StandardCharsets.UTF_8)
        + "&page=" + URLEncoder.encode("1", StandardCharsets.UTF_8);

URI uri = new URI("https", "example.com", "/api/users", query, null);

System.out.println(uri);
// https://example.com/api/users?name=%E5%BC%A0%E4%B8%89&page=1
```

`URLEncoder` 的语义来自 HTML 表单编码，会把空格编码成 `+`。用于普通 query 参数通常可以接受；如果要严格按 RFC 3986 处理复杂场景，可以使用成熟的 HTTP/URI 构造库。

## 四、文件路径和 URI 互转

本地文件路径转 URI：

```java
Path path = Path.of("D:/data/a b.png");
URI fileUri = path.toUri();

System.out.println(fileUri);
// file:///D:/data/a%20b.png
```

URI 转回路径：

```java
Path path2 = Path.of(fileUri);
```

不要手写 `file://` 字符串，尤其是在 Windows 路径、空格和中文文件名混在一起时。交给 `Path#toUri` 更稳。

## 五、发送 HTTP 请求

从 JDK 11 开始，可以用 `HttpClient`：

```java
HttpClient client = HttpClient.newHttpClient();

HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create("https://example.com/api/users?page=1"))
        .GET()
        .build();

HttpResponse<String> response =
        client.send(request, HttpResponse.BodyHandlers.ofString());

System.out.println(response.statusCode());
System.out.println(response.body());
```

`URI` 负责表达地址，`HttpClient` 负责发请求。把这两个职责分开，代码会清楚很多。

## 六、URI 和 URL 怎么选

简单规则如下：

| 场景 | 推荐 |
| --- | --- |
| 解析 scheme、host、path、query | `URI` |
| 拼接相对路径 | `URI#resolve` |
| 文件路径互转 | `Path` + `URI` |
| 发 HTTP 请求 | `HttpClient` + `URI` |
| 老代码里打开连接 | `URL#openConnection` |

现代 Java 里，优先把地址当成 `URI` 处理；只有确实要打开连接时，再交给 HTTP 客户端或历史 API。
