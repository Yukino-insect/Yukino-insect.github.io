+++
date = '2026-10-17T10:10:00+08:00'
draft = false
title = 'Android Activity：页面宿主、生命周期与组件通信'
+++
Android 应用不像 Java `main` 方法那样由开发者从头到尾顺序调用。系统负责创建进程、选择要展示的页面、暂停不可见页面，甚至在内存紧张时销毁进程；应用把可恢复的页面逻辑交给 `Activity`。因此，`Activity` 不是“所有业务代码都该放进去的主类”，而是**一个与用户交互的页面宿主和生命周期协调者**。

本章把一个页面放回完整链路：启动入口如何到达 Activity、XML 中的 View 如何由它装配、两个页面怎样传递数据，以及为何异步任务不能忽略页面已离开的事实。

## Activity 在架构中的位置

一个传统 View 应用可先这样理解：

```text
Android 系统
  -> 启动 Launcher Activity
    -> Activity 创建 Window 和 View 树
      -> Activity 把事件交给 View，并协调导航
        -> ViewModel / Repository 执行状态与数据工作
```

`Activity` 应负责：选择布局、绑定控件、处理用户意图、发起页面导航、观察状态并渲染。它不适合长期持有网络请求、数据库连接或大块业务规则；这些工作应放在更容易测试和复用的状态持有者或数据层。即使刚入门，也先把“页面协调”与“业务计算”分开，后面学习 ViewModel 时不会推倒重来。

## 启动入口与 Manifest 的对应关系

系统通过 `AndroidManifest.xml` 找到可启动页面。一个最小入口声明如下：

```xml
<application android:label="@string/app_name">
    <activity
        android:name=".DetailActivity"
        android:exported="false" />

    <activity
        android:name=".MainActivity"
        android:exported="true">
        <intent-filter>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent-filter>
    </activity>
</application>
```

`MAIN` + `LAUNCHER` 表示桌面图标启动时的入口。`exported="false"` 表示其他应用不能显式启动 `DetailActivity`；不是为外部调用准备的页面，默认不导出更安全。`Activity` 的 Java 类本身不会因为存在于源码目录就自动成为页面，必须由 Manifest（或相应构建配置）向系统声明。

## 生命周期不是固定“流程图”，而是状态变化通知

最常见的状态转换可简化为：

```text
首次打开：onCreate -> onStart -> onResume
被遮挡：  onPause -> onStop
重新回来：onRestart -> onStart -> onResume
关闭页面：onPause -> onStop -> onDestroy（通常）
```

系统不承诺每次都会调用 `onDestroy`，例如进程可能被直接回收。因此真正需要恢复的数据必须在合适的持久层保存，而不是只赌 `onDestroy` 会执行。各回调的职责可以这样分：

| 回调 | 页面状态 | 适合做什么 |
| --- | --- | --- |
| `onCreate` | 实例首次建立 | `setContentView`、绑定 View、恢复轻量状态 |
| `onStart` | 已可见但未必可交互 | 注册与可见性相关的观察者 |
| `onResume` | 前台可交互 | 恢复相机预览、输入等前台资源 |
| `onPause` | 即将失去焦点 | 快速提交编辑、暂停短暂工作 |
| `onStop` | 不再可见 | 停止较耗资源的 UI 工作 |
| `onDestroy` | 实例结束时通常调用 | 释放只属于该实例的资源，不能承担持久化保证 |

配置变化（例如旋转屏幕）可能销毁旧 Activity 后重建新实例。把只属于界面的对象重新绑定到新布局；不要让后台回调永久抓住旧 Activity 引用，否则会内存泄漏，也可能更新一张已经消失的页面。

## 一个可运行的双页面例子

首页让用户输入昵称并进入详情页。布局 `res/layout/activity_main.xml`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:gravity="center"
    android:orientation="vertical"
    android:padding="24dp">

    <EditText
        android:id="@+id/nameInput"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="请输入昵称"
        android:inputType="textPersonName" />

    <Button
        android:id="@+id/openDetailButton"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="查看欢迎语" />
</LinearLayout>
```

`MainActivity` 负责读取当前 UI 状态并构造导航意图：

```java
package com.example.activitydemo;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    public static final String EXTRA_NAME = "com.example.activitydemo.NAME";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        EditText nameInput = findViewById(R.id.nameInput);
        Button openDetailButton = findViewById(R.id.openDetailButton);
        openDetailButton.setOnClickListener(view -> {
            String name = nameInput.getText().toString().trim();
            Intent intent = new Intent(MainActivity.this, DetailActivity.class);
            intent.putExtra(EXTRA_NAME, name);
            startActivity(intent);
        });
    }
}
```

详情布局 `res/layout/activity_detail.xml` 只需放一个 `TextView`，其 id 为 `welcomeText`。详情页面读取输入并渲染：

```java
package com.example.activitydemo;

import android.os.Bundle;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class DetailActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_detail);

        String name = getIntent().getStringExtra(MainActivity.EXTRA_NAME);
        if (name == null || name.isEmpty()) {
            name = "访客";
        }
        TextView welcomeText = findViewById(R.id.welcomeText);
        welcomeText.setText("你好，" + name + "！");
    }
}
```

`Intent` 是 Android 用来描述一次操作的消息对象。这里的显式 Intent 明确写出了目标 `DetailActivity`；`putExtra` 放的是小而可序列化的导航参数，不应把大对象、密码或数据库连接塞进去。详情页应把 Intent 数据当作外部输入校验，即使来源是自家 Activity——以后它可能变为深链接或外部入口。

## 返回结果、组件边界与线程

如果详情页需要把选择结果交回首页，可使用 Activity Result API：由调用方注册一个回调，再启动选择页。它取代了容易与生命周期纠缠的旧 `onActivityResult` 模式。无论采用哪种 API，通信本质都是：**调用方声明自己怎样消费结果，页面只返回结果数据，不直接操纵调用方的 View。**

同样的边界适用于后台任务。网络线程可以得到用户资料，但不能直接执行 `textView.setText(...)`；View 只能在 UI 主线程修改。并且回调到达时，Activity 可能已 `onStop` 或已经销毁。实际项目应使用生命周期感知的状态层（例如 ViewModel + LiveData/Flow），由当前可见页面观察并渲染状态；不要让 Repository 持有 Activity 或 TextView。

## 常见误解

- `onCreate` 不等于“应用只执行一次”。旋转屏幕、进程重建都会再次创建 Activity。
- `onPause` 后不代表一定立刻销毁；但它也不再适合启动长时间的 UI 交互。
- `Activity` 不是应用全局单例。不要用 `static Activity` 传递对象。
- `finish()` 请求关闭当前页面；实际的生命周期回调仍由系统调度。

## 小结

- `Activity` 是一个页面的宿主与协调者，不是所有业务逻辑的容器。
- Manifest 声明系统可以启动的组件；显式 Intent 用目标类传递页面参数。
- 生命周期表示页面可见、可交互和可能销毁的状态变化，异步工作必须尊重它。
- 所有 View 更新都在主线程进行；页面之间传递数据而非彼此的控件引用。
