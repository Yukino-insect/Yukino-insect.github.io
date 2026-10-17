+++
date = '2026-10-17T10:00:00+08:00'
draft = false
title = 'Android 工程结构与 Gradle 配置：代码如何变成 APK'
+++

上一篇把一个页面看成 Activity 管理的 View 对象树。本篇换一个角度：这些 Java 文件、XML、图片和依赖库如何被组织，又如何被构建成可安装的 APK。若把 Android Studio 只当作“点运行的 IDE”，遇到依赖下载、包名、版本冲突时就很难判断问题的位置；而 Gradle 正是这一过程的编排者。

## 一个 Android 工程的基本层级

新建项目后，磁盘上的常见结构大致如下。Android Studio 的 “Android” 视图会把它重新分组，排查路径问题时应以实际文件系统结构为准。

```text
MyApp/
├── settings.gradle
├── build.gradle
├── gradle.properties
├── gradle/wrapper/
├── gradlew
└── app/
    ├── build.gradle
    ├── proguard-rules.pro
    └── src/
        └── main/
            ├── AndroidManifest.xml
            ├── java/com/example/myapp/MainActivity.java
            └── res/
                ├── layout/activity_main.xml
                ├── values/strings.xml
                └── mipmap-*/
```

- **工程根目录**：管理所有模块与共同构建规则。
- **模块**：可独立参与构建的单元。大多数小项目只有 `app`，大型项目还可能有 `feature`、`core` 等库模块。
- `app/src/main`：应用的正式源集（source set）。其中的 Java、资源和清单会进入正式安装包。
- `app/src/test`：在本机 JVM 上运行的单元测试，通常不依赖真实设备。
- `app/src/androidTest`：需要模拟器或真机的仪器测试。

不要把 Java 包名、模块名和应用 ID 混为一谈。`com.example.myapp` 可以是 Java 文件的包名；`app` 是模块名；`applicationId` 才是安装到设备与应用商店时识别应用的唯一 ID。

## Manifest：向系统声明应用组件

`AndroidManifest.xml` 不是普通配置备忘录，而是系统安装和启动应用时要读取的声明。它会登记 Activity、权限、应用图标与入口页面等信息。

下面是可启动一个传统 Java Activity 的最小示例。实际项目通常还会由构建工具合并依赖库中的 Manifest。

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:theme="@style/Theme.MyApp">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

`MAIN` 加 `LAUNCHER` 表示“可以从桌面图标启动”。Android 12（API 31）及以后，带有 intent filter 的组件必须明确声明 `android:exported`；缺失会导致构建错误。`android:name=".MainActivity"` 的前导点表示相对应用命名空间的类名。

权限也在这里声明，例如联网功能：

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

声明权限不等于一定已经获得权限。危险权限还需要在运行时向用户请求；`INTERNET` 属于普通权限，不需要弹窗。把所有权限都先写上，是一种不必要也不负责任的习惯。

## Gradle 是什么，它在构建中做了什么

Gradle 是构建自动化工具。Android Gradle Plugin（AGP）在 Gradle 的基础上增加了编译资源、处理 Manifest、打包 APK/AAB、签名、安装等 Android 专用任务。

可以把一次调试构建概括为：

```text
Java 源码 + XML/图片资源 + Manifest + 依赖
  -> Gradle 读取构建脚本
  -> 生成 R 类、编译 Java、处理资源与 Manifest
  -> DEX 字节码、打包、签名
  -> app-debug.apk
  -> 安装到设备或模拟器
```

Java 编译器输出的是 JVM 字节码，而 Android 设备运行的是 DEX（Dalvik Executable）格式字节码；这也是“Java 能写 Android”却不能把普通 Java jar 原样丢进手机运行的原因之一。

### 根工程与模块脚本

不同 Android Studio/AGP 版本生成的脚本样式有所不同：旧项目常用 Groovy 的 `build.gradle`，新项目也可能使用 Kotlin DSL 的 `build.gradle.kts`。语法不同，职责相同：根工程定位插件和仓库，模块脚本描述这个模块如何编译与打包。

下面以常见 Groovy 风格的 `app/build.gradle` 为例，版本号仅作示意；应以项目实际生成的兼容版本为准。

```groovy
plugins {
    id 'com.android.application'
}

android {
    namespace 'com.example.myapp'
    compileSdk 36

    defaultConfig {
        applicationId 'com.example.myapp'
        minSdk 23
        targetSdk 36
        versionCode 1
        versionName '1.0'
    }

    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'),
                    'proguard-rules.pro'
        }
    }
}

dependencies {
    implementation 'androidx.appcompat:appcompat:1.7.1'
    implementation 'com.google.android.material:material:1.12.0'
}
```

### 必须区分的版本字段

| 字段 | 决定什么 | 不决定什么 |
| ---- | -------- | ---------- |
| `compileSdk` | 编译时可使用的 Android API 上限 | 用户设备最低版本 |
| `minSdk` | 允许安装应用的最低 API 级别 | 编译时可引用的全部 API |
| `targetSdk` | 应用声明适配的 Android 行为版本 | 应用实际只能运行的最高系统版本 |
| `versionCode` | 商店更新比较用的递增整数 | 用户看到的版本文案 |
| `versionName` | 用户可见版本，如 `1.0` | 升级顺序判断 |

例如 `minSdk 23` 表示 API 22 设备无法安装。即使 `compileSdk` 很新，也不能在 API 23 上无条件调用更高版本新增的方法；此时要做版本判断、使用兼容库，或提高 `minSdk`。

### namespace 与 applicationId

`namespace` 是构建阶段生成 `R` 类等代码所使用的命名空间，通常与代码包名一致。`applicationId` 是最终安装标识。调试版本有时会加后缀，例如 `com.example.myapp.debug`，以便与正式版同时安装。

它们可以不同，但入门项目最好保持一致，减少“我导入的是哪个 `R`”这类不必要的困惑。重命名 Java 包也不会自动安全地改变线上应用 ID；已发布应用修改 `applicationId` 会被商店视为另一个应用。

## 依赖、仓库与配置名称

`dependencies` 中的每一条记录都说明模块需要什么库。以：

```text
group:artifact:version
```

这样的坐标定位远程库。`implementation` 表示本模块编译和运行需要它，但尽量不把它暴露为其他模块的编译 API；库模块在确实需要向依赖者暴露类型时才使用 `api`。此外还有：

- `testImplementation`：只供本地单元测试使用。
- `androidTestImplementation`：只供设备测试使用。
- `debugImplementation`：只进入 debug 构建。

Gradle Sync 是 IDE 根据脚本下载依赖、解析任务模型的过程，不等于已经生成 APK。Sync 失败常见于网络、仓库地址、AGP/Gradle/JDK 版本不兼容，先看报错中第一个明确的 `Caused by`，不要只盯最后一行“build failed”。

## 构建变体：debug 与 release

`buildTypes` 让同一份代码按不同规则产出安装包。最常见的两种是：

- `debug`：开发调试使用，通常自动使用 debug 签名并允许调试器连接。
- `release`：发布使用，必须由正式签名密钥签名，通常会开启资源压缩与代码混淆/优化。

构建任务名往往把模块、变体和动作组合起来：

```bash
./gradlew :app:assembleDebug
```

在 Windows PowerShell 中通常写为：

```powershell
.\gradlew.bat :app:assembleDebug
```

该命令会生成 debug APK，但是否自动安装由任务决定。Android Studio 的 Run 按钮还会选择设备并执行安装启动。

## 一个能运行的最小工程链路

假设已经用 Android Studio 创建了 Empty Views Activity 项目，下面三处形成最小闭环：

1. Manifest 将 `MainActivity` 声明为启动入口。
2. `MainActivity` 在 `onCreate` 调用 `setContentView(R.layout.activity_main)`。
3. `res/layout/activity_main.xml` 定义根布局和控件。

`MainActivity.java` 可以是：

```java
package com.example.myapp;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
    }
}
```

当 Run 成功后，系统根据 Manifest 找到入口 Activity；Activity 根据 `R.layout.activity_main` 找到编译好的布局资源；布局再生成上一章所说的 View 树。第 3 篇会解释 `R` 为什么存在、资源目录名称为何不能随意写。

## 常见误解与排查顺序

- **“改了 `build.gradle`，为什么代码仍报错？”** 先执行 Gradle Sync；依赖没有解析完成，IDE 不知道新增类来自哪里。
- **“升级 `compileSdk` 就能支持旧设备吗？”** 不能。旧设备是否可安装看 `minSdk`，运行期是否安全还看 API 检查。
- **“Manifest 中声明了权限就完成了？”** 危险权限还必须在运行时请求，并处理用户拒绝。
- **“`app` 目录就是包名吗？”** 不是。它是模块目录；包名位于 `src/main/java` 下的路径与 `package` 声明中。
- **“我可以随便改版本号吗？”** 发布更新时 `versionCode` 必须比商店已有版本大，且签名与应用 ID 必须延续。

## 本篇小结

- 工程由根配置与一个或多个模块构成，`app/src/main` 放正式的代码、资源和 Manifest。
- Manifest 向系统声明组件和权限；Gradle/AGP 则把全部输入编排成 APK 或 AAB。
- `compileSdk`、`minSdk`、`targetSdk` 分别回答“按什么 API 编译”“最低可安装版本”“按哪个行为版本适配”。
- `namespace` 服务于构建与生成代码，`applicationId` 是设备和商店识别应用的身份。
- 遇到构建问题，先区分 Sync、编译、打包、安装中的哪一个阶段失败。
