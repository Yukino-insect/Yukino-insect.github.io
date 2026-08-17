+++
date = '2026-02-19T12:15:06+08:00'
draft = false
title = 'Java 原生url操作'
+++

Java 原生（JDK 自带）的 URL/URI 操作主要分两套：**`java.net.URL`** 和 **`java.net.URI`**。再加上从 JDK 11 开始的 **`java.net.http.HttpClient`**。平时拼 URL / 解析 / 编码 / 转换文件路径最优雅的是 **URI**，URL 多用于能直接打开连接的定位符。

#### A. 解析 URL/URI

```java
URI u = URI.create("https://example.com/a/b.png?x=1#top");

u.getScheme();    // https
u.getHost();      // example.com
u.getPath();      // /a/b.png
u.getQuery();     // x=1
u.getFragment();  // top
```

#### B. 优雅拼接路径：`resolve`

```java
URI base = URI.create("https://cdn.example.com/models/");
URI file = base.resolve("30909800.glb");
// => https://cdn.example.com/models/30909800.glb
```

如果 base 没带尾部 `/`，`resolve` 的语义会不一样，所以通常 base 设计成目录时最好以 `/` 结尾。

#### C. 拼 Query 参数

```java
String q = "name=" + URLEncoder.encode("张三", StandardCharsets.UTF_8)
         + "&page=" + 1;

URI uri = new URI("https", "example.com", "/api", q, null);
// => https://example.com/api?name=%E5%BC%A0%E4%B8%89&page=1
```

#### D. URL 与文件路径互转

- 文件路径 -> URI：

```java
Path p = Path.of("D:/data/a b.png");
URI fileUri = p.toUri();  // file:///D:/data/a%20b.png
```

- URI -> Path：

```java
Path p2 = Path.of(fileUri);   // JDK 11+ OK
```
