+++
date = '2026-10-17T09:00:00+08:00'
draft = false
title = 'Android 应用架构与 UI 对象树：从 Activity 到常见 View'
+++

学习 Android 的第一道门槛往往不是 Java，而是“代码究竟在和谁协作”。一个 Android 应用不是从 `main` 方法开始、在一个窗口中一直运行的普通 Java 程序；系统会创建页面、分发事件、在需要时回收进程。界面则由一棵对象树描述。理解这两个事实以后，XML、`findViewById` 和布局属性才不会显得像偶然出现的咒语。

本文使用传统的 **View/XML** 界面体系和 Java。它仍然大量存在于存量项目、后台管理类 App 与面试场景中。Jetpack Compose 是较新的声明式 UI 方案，但它不改变 Android 的组件、资源与生命周期基础；本系列先把这些基础讲清楚。

## Android 应用由哪些部分组成

Android 系统并不要求应用有一个可见的 `main` 方法。它通过清单文件中登记的组件，在恰当的时机启动应用代码。初学阶段最需要认识下面四种组件：

| 组件 | 解决的问题 | 是否有界面 | 常见例子 |
| ---- | ---------- | ---------- | -------- |
| `Activity` | 承载一个可交互的页面 | 通常有 | 登录页、设置页 |
| `Service` | 在后台持续执行任务 | 没有 | 音乐播放、数据同步 |
| `BroadcastReceiver` | 响应系统或应用广播 | 没有 | 网络状态变化、开机完成 |
| `ContentProvider` | 按统一接口共享数据 | 没有 | 读取联系人、向其他应用提供数据 |

这四者都由系统调度。对于一个“输入姓名并显示问候语”的页面，我们的主角是 `Activity`：它创建窗口中的 UI，并接收用户点击。

### Activity、窗口与根视图

可以把一次页面显示理解为以下关系：

```text
Android 系统
  -> Activity（页面控制器）
      -> Window（系统提供的页面窗口）
          -> DecorView（窗口中的顶层 View）
              -> 你通过 setContentView 放入的根布局
                  -> TextView、EditText、Button 等子 View
```

`Activity` 不是一个按钮，也不是布局容器；它是管理一个页面状态与生命周期的 Java 对象。`Window` 和 `DecorView` 是框架为页面准备的外层容器。开发者最常操作的是自己设置的**内容根视图**，通常是一个 `LinearLayout`、`ConstraintLayout` 或 `FrameLayout`。

因此，`setContentView(R.layout.activity_main)` 的意思不是“打开 XML 文件”，而是：让框架根据这个布局资源创建一棵 `View` 对象树，并将其作为当前 Activity 的内容显示出来。

### 生命周期为什么重要

手机旋转、切到后台、系统内存紧张，都会让页面状态改变。Activity 至少会经历下面的常见阶段：

```text
onCreate -> onStart -> onResume
                         | 用户正在交互
onPause -> onStop -> onDestroy
```

- `onCreate`：创建页面时调用，适合加载布局、初始化 View、恢复必要状态。
- `onStart`：页面变得可见。
- `onResume`：页面可交互，通常从这里开始接收前台输入。
- `onPause`：即将失去前台焦点，应暂停短暂、可恢复的工作。
- `onStop`：页面不可见，应停止不需要继续占用的资源。
- `onDestroy`：Activity 被销毁前的清理机会，但不能把它当作唯一的数据保存点。

一个常见误解是“按返回键后对象永远存在”。事实上，停止的 Activity 及进程都可能被系统回收；重要数据应保存到磁盘、数据库或可恢复的状态容器中，而不能只放在成员变量里。

## View 与 ViewGroup：UI 对象树的两类节点

传统 Android UI 中，绝大多数界面对象都继承自 `android.view.View`。`View` 的输入是尺寸约束、属性与事件，输出是屏幕上的绘制结果以及可访问性信息。文字、图片、按钮都是 View。

`ViewGroup` 是 `View` 的子类，它额外拥有“容纳并摆放子 View”的能力。也就是说：

- 普通 `View` 主要负责显示或交互，例如 `TextView`、`Button`、`ImageView`；
- `ViewGroup` 既可以显示自己，也负责测量、布局子节点，例如 `LinearLayout`、`FrameLayout`。

下面的 XML 会产生一棵非常小的对象树：

```text
LinearLayout（根 ViewGroup，竖直摆放）
├── TextView（显示标题）
├── EditText（接收文本输入）
├── Button（接收点击）
└── TextView（显示结果）
```

树结构不是排版的装饰。触摸事件通常从父容器向子 View 分发；父容器也会先测量和定位孩子。层级越深，测量、绘制与事件处理就越复杂，所以不要为了“分组好看”无意义地嵌套很多布局。

## 常见 UI 类及其职责

### 文本、输入与按钮

| 类 | 输入与输出 | 适用场景 | 初学者容易误解的点 |
| --- | ---------- | -------- | ------------------ |
| `TextView` | 文本 -> 屏幕文字 | 标题、说明、结果 | 不负责编辑文本 |
| `EditText` | 用户输入 -> `Editable` 文本 | 姓名、密码、搜索词 | 它是可编辑的 `TextView` 子类 |
| `Button` | 点击事件 -> 回调 | 提交、确认、跳转 | 按钮行为需由代码或声明绑定 |
| `ImageView` | 图片资源 -> 屏幕图像 | 图标、封面 | 需要考虑缩放方式与内容描述 |

例如，从 `EditText` 读取输入时，得到的不是自动去空格的 Java `String`，而是可编辑文本对象；通常应显式转换并处理空白：

```java
String name = nameInput.getText().toString().trim();
```

### 常见容器

| 容器 | 布局规则 | 最合适的场景 | 边界 |
| ---- | -------- | ------------ | ---- |
| `LinearLayout` | 沿水平或垂直方向依次排列 | 简单表单、少量控件 | 复杂界面容易嵌套过深 |
| `FrameLayout` | 子项可重叠，后者覆盖前者 | 页面容器、加载蒙层 | 不自动表达复杂相对关系 |
| `ScrollView` | 提供单一直接子项的滚动 | 长表单、详情页 | 不要在其中再放同方向的列表 |
| `ConstraintLayout` | 用约束表达相对位置 | 较复杂的单屏页面 | 初学时需要理解约束关系 |
| `RecyclerView` | 复用列表项来展示数据集 | 消息、商品、文章列表 | 它不是普通静态容器，需要 Adapter |

`RecyclerView` 也是 View，但它的“子项”由 `Adapter` 根据数据按需创建和复用。几十条消息不应手写几十个 `TextView`，否则内存和绘制都会被浪费。

## 从 XML 到一次点击：最小页面

先看布局文件 `res/layout/activity_main.xml`。这里的标签名大多就是要实例化的 Java 类名，属性则是创建后要设置的初始状态。

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="24dp">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="请输入你的名字" />

    <EditText
        android:id="@+id/name_input"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="例如：小林"
        android:inputType="textPersonName" />

    <Button
        android:id="@+id/greet_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="问候" />

    <TextView
        android:id="@+id/result_text"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp" />
</LinearLayout>
```

对应的 `MainActivity.java` 如下。`onCreate` 中先 `setContentView`，再通过 `id` 找到这棵树中的节点；顺序不能颠倒，因为布局尚未创建时没有可查找的 View。

```java
package com.example.helloui;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        EditText nameInput = findViewById(R.id.name_input);
        Button greetButton = findViewById(R.id.greet_button);
        TextView resultText = findViewById(R.id.result_text);

        greetButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    nameInput.setError("名字不能为空");
                    return;
                }
                resultText.setText("你好，" + name + "！");
            }
        });
    }
}
```

数据流是：用户在 `EditText` 输入字符，点击事件由 `Button` 触发，监听器读取输入，最后调用 `TextView.setText` 改变显示。这里没有“自动双向绑定”；传统 View 的状态同步需要你在适当的事件中显式编写。

## View 的测量、布局与绘制

当屏幕要显示或尺寸变化时，根 View 会经历一个简化流程：

```text
父容器给约束
  -> measure：每个 View 决定想要的宽高
  -> layout：父容器确定子 View 的位置
  -> draw：背景、内容与子 View 被绘制到屏幕
```

`layout_width` 与 `layout_height` 正是在描述测量要求。常见值是：

- `match_parent`：尽量占满父容器允许的尺寸。
- `wrap_content`：根据自身内容取合适尺寸。
- `48dp`：指定一个与屏幕密度无关的具体长度。

注意，`wrap_content` 并不等于“总能完整显示”。父容器给出的约束仍然优先；而一段很长的文字可能换行、截断或需要滚动。尺寸与属性的完整规则会在第 4 篇展开。

## Compose 与本系列的边界

Compose 使用 Java/Kotlin 函数描述“状态应该呈现为何种 UI”，不再依赖 XML 与 `findViewById`。它适合新项目，尤其在 Kotlin 主导的团队中。但 Compose 仍运行在 Activity、Window、资源和 Android 生命周期之上，也可以嵌入传统 View 页面。

本系列先采用 View/XML，是因为它能清楚展示资源编译、对象树、属性归属和事件监听这些基础。学完后再看 Compose，会发现差异主要在 UI 的声明和状态更新方式，而不是 Android 平台被彻底换了一套。

## 本篇小结

- `Activity` 管理一个页面及其生命周期，`setContentView` 把布局对象树放进当前窗口。
- 所有传统控件都是 `View`；能容纳和摆放子节点的控件是 `ViewGroup`。
- `TextView`、`EditText`、`Button` 负责不同的显示或交互，容器决定它们如何排列。
- XML 定义初始 UI 树，Java 在 `onCreate` 中取得 View、注册事件并更新状态。
- 不要把成员变量当成永久存储，也不要靠无限嵌套布局来解决复杂界面。
