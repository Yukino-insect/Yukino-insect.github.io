+++
date = '2026-10-17T10:00:00+08:00'
draft = false
title = 'Android WebView：网络权限、内置网页客户端与安全边界'
+++
有些应用既要保留原生页面的流畅交互，又要展示活动页、帮助中心或已有的 Web 系统。`WebView` 就是 Android 提供的内置网页渲染控件：它把一个浏览器内核嵌入到普通 `View` 树中。它不是“能访问网络的 `TextView`”，而是一个会解析 HTML、执行 JavaScript、处理跳转和存储数据的复杂客户端。

本章目标是做一个只允许访问自家 HTTPS 帮助页的最小页面，并理解权限、线程和安全配置分别解决什么问题。示例采用传统 Java + XML/View 写法，最低原则是：**需要什么能力才开启什么能力，来自网页的数据不能直接取得原生应用的信任。**

## 先建立整体模型

一次加载网页大致经过下面这条链路：

```text
Activity 创建布局
  -> WebView.loadUrl(HTTPS 地址)
  -> WebView 向网络发起请求
  -> WebViewClient 决定链接是否留在应用内
  -> 内核解析 HTML/CSS/JavaScript
  -> 结果绘制到 WebView 这个 View
```

`INTERNET` 权限控制的是“应用进程能否建立网络连接”；`WebViewClient` 控制的是“某次导航由谁处理”；`WebSettings` 控制的是网页运行环境中的一部分能力。它们不应混为一谈。声明网络权限并不会自动允许 HTTP 明文流量，也不会让网页自动获得相机、定位或原生 Java 方法的权限。

## 声明网络能力：Manifest 是安装前的能力清单

在 `app/src/main/AndroidManifest.xml` 的 `<manifest>` 下声明权限：

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:theme="@style/Theme.MyApp"
        android:usesCleartextTraffic="false">
        <activity
            android:name=".HelpActivity"
            android:exported="false" />
    </application>
</manifest>
```

`INTERNET` 是安装时授予的普通权限，不需要像相机、定位那样在运行时弹窗请求。`android:usesCleartextTraffic="false"` 表达了一个更重要的默认值：本应用不应通过未加密的 `http://` 传输内容。现代 Android 面向较新 API 时默认也会限制明文流量，但把策略写清楚比依赖默认行为可靠。

如果确实只能连接某个旧 HTTP 域名，不要把全局策略改为允许明文；应建立 `res/xml/network_security_config.xml`，只为该域名配置例外，并安排迁移到 HTTPS。公共网络中的 HTTP 内容可被替换，网页里一段被替换的脚本就可能改变整个页面的行为。

## 把 WebView 放进 XML，并让页面保持原生

先创建 `res/layout/activity_help.xml`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <WebView
        android:id="@+id/helpWebView"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
</FrameLayout>
```

`@+id/helpWebView` 会在构建时生成整数资源标识，Java 代码通过 `R.id.helpWebView` 找到同一个对象。XML 只是描述 View 树；真正的 `WebView` 实例由布局填充（inflate）时创建，随后属于当前 `Activity`。

下面是对应的 `HelpActivity`。为突出核心逻辑，假定项目已经使用 AndroidX 的 `AppCompatActivity`。

```java
package com.example.webdemo;

import android.annotation.SuppressLint;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

public class HelpActivity extends AppCompatActivity {
    private WebView helpWebView;

    @SuppressLint("SetJavaScriptEnabled") // 本例明确说明了启用理由和边界
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_help);

        helpWebView = findViewById(R.id.helpWebView);
        WebSettings settings = helpWebView.getSettings();
        settings.setJavaScriptEnabled(true); // 只有目标站点依赖 JS 时才开启
        settings.setDomStorageEnabled(true); // 网站需要 localStorage 时才开启
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);

        helpWebView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("https://help.example.com/")) {
                    return false; // false：继续交给当前 WebView 加载
                }
                return true; // 拒绝未知站点，避免无意跳到不可信网页
            }
        });

        helpWebView.loadUrl("https://help.example.com/start");
    }

    @Override
    public void onBackPressed() {
        if (helpWebView.canGoBack()) {
            helpWebView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        helpWebView.destroy();
        super.onDestroy();
    }
}
```

这个例子中，网页加载和 `WebView` 的方法调用都必须发生在 UI 主线程。通常 `onCreate`、点击回调和生命周期回调已运行在主线程，所以可以直接调用；若下载器在工作线程得到一个 URL 或 HTML，必须先切换回主线程，再调用 `loadUrl` 或修改任何 View。下一篇会说明这种“页面的生命周期”和“界面的唯一线程”约束从哪里来。

## `WebViewClient` 与 `WebChromeClient` 各管什么

初学者常把两个名字相近的类混在一起。可以按“导航”与“浏览器界面能力”区分：

| 对象 | 主要职责 | 常见回调 |
| --- | --- | --- |
| `WebViewClient` | 页面请求、跳转、错误、SSL 错误 | `shouldOverrideUrlLoading`、`onReceivedError` |
| `WebChromeClient` | 标题、加载进度、JS 弹窗、文件选择等浏览器能力 | `onProgressChanged`、`onReceivedTitle` |

没有设置 `WebViewClient` 时，链接可能交给系统浏览器或其他应用处理；设置它的目的不是“让网页能联网”，而是让应用明确导航政策。对于登录、支付、深链接等特殊 URL，应按协议和受信任域名逐项处理，而不是用 `contains("example.com")` 这种容易被伪造子串绕过的判断。

## JavaScript、桥接对象与文件访问的安全边界

`setJavaScriptEnabled(true)` 只应为确实依赖 JavaScript 的、受信任的页面打开。它不是现代网页的“通用必选项”：静态帮助页完全可以关闭它。更危险的是下面这种把原生对象暴露给任意网页的做法：

```java
helpWebView.addJavascriptInterface(new DeviceBridge(), "Android");
```

这样网页脚本可能调用暴露对象中带 `@JavascriptInterface` 的方法。只要 WebView 能跳转到攻击者页面，或受信任站点存在脚本注入漏洞，桥接接口就会成为原生应用的入口。因此默认不要使用它；确有双向通信需求时，至少同时满足：仅加载自己控制的 HTTPS 页面、严格阻止外链跳转、接口极小且不提供文件/账户/命令执行能力，并审计每个传入参数。

同样应避免为“先跑起来”打开下面这些开关：

- `setAllowFileAccess(true)`：网页可能读取应用可访问的文件资源。
- 忽略 `onReceivedSslError` 后继续加载：这等于放弃 HTTPS 身份校验。
- 允许任意 `intent://`、`tel:` 或自定义 scheme：应先验证数据并只处理业务允许的协议。
- 直接 `loadData` 服务器返回的未净化 HTML：它仍可能执行脚本或发起网络请求。

`WebView` 中的 Cookie、缓存、登录态也属于隐私数据。注销时应根据产品要求清除会话；不应把令牌拼接进 URL，因为 URL 会出现在历史记录、日志或引用头中。

## 失败时怎样定位问题

先按层次检查，而不是不停切换设置：

1. 网络请求完全失败：确认 Manifest 有 `INTERNET`，设备网络正常，地址是 HTTPS。
2. 只有 HTTP 地址失败：检查明文流量策略，优先修复服务端 HTTPS。
3. 页面能开、点击链接却跑到外部：检查是否设置了 `WebViewClient` 和 URL 白名单。
4. 页面白屏但没有网络异常：用远程调试或服务端日志检查 JavaScript、CSP、Cookie 与响应内容；不要为了排错关闭所有安全限制。
5. 后台线程更新网页报错：把 `loadUrl`、`evaluateJavascript` 等 View 操作投递回主线程。

## 小结

- `WebView` 是嵌入在 View 树中的网页客户端；`INTERNET`、导航策略和脚本能力是三件不同的事。
- 默认使用 HTTPS，禁止明文流量，并用 `WebViewClient` 只允许预期的域名和路径。
- JavaScript、DOM 存储、文件访问和 JavaScript 原生桥接都应按需启用；网页内容不能天然信任。
- `WebView` 和其他 View 一样只能在主线程操作，并受其 `Activity` 生命周期约束。
