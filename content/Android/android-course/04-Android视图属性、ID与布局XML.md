+++
date = '2026-10-17T12:00:00+08:00'
draft = false
title = 'Android 视图属性、ID 与布局 XML：写出可预测的界面'
+++

现在我们已经知道：布局 XML 会创建 View 对象树，资源编译后由 `R` 提供入口。真正动手写页面时，最容易卡住的问题通常更具体——为什么每个控件都要写宽高？`layout_margin` 与 `padding` 谁作用于谁？`id` 到底是变量吗？本篇把这些“固定格式”还原为可推理的规则，并完成一个可直接放入传统 Java 项目的表单界面。

## 一段布局 XML 的固定骨架

布局文件是 XML 文档，第一行可写 XML 声明；根元素必须声明 Android 属性命名空间。之后每个标签表示一个 View 或 ViewGroup，属性以 `android:` 前缀使用系统定义的名称。

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="一行文字" />
</LinearLayout>
```

必须牢牢记住两项：

- 每个 View 都必须有 `android:layout_width` 和 `android:layout_height`。
- 根布局需要 `xmlns:android="http://schemas.android.com/apk/res/android"`，否则 `android:` 属性没有合法的命名空间。

这里的 URL 是 XML 命名空间标识，不是应用运行时会发出的网络请求。根标签可以是任何合适的 ViewGroup；标签若是完整类名，例如自定义 `com.example.myapp.ProfileView`，布局加载器会反射创建它。

## 属性分两类：View 自己的，与父容器解释的

判断一个属性前，先问“谁读取它”。这比死背属性名可靠。

### 普通 View 属性

普通属性由 View 自身或其父类读取，描述它自己的内容、可见性、背景等。

| 属性 | 作用对象 | 常见值 |
| ---- | -------- | ------ |
| `android:id` | View 身份 | `@+id/submit_button` |
| `android:text` | 可显示文字的 View | `@string/submit` |
| `android:hint` | 输入框的提示 | `@string/name_hint` |
| `android:background` | View 背景 | `@drawable/bg_card` |
| `android:visibility` | 是否参与显示 | `visible`、`invisible`、`gone` |
| `android:contentDescription` | 无障碍朗读描述 | `@string/avatar_description` |
| `android:padding` | 内容到自身边缘的内边距 | `16dp` |

`visibility` 的三个取值差异很重要：`visible` 正常显示；`invisible` 不显示但仍保留原来的布局空间；`gone` 不显示也不占空间。把 `gone` 当作“透明”会导致周边控件位置变化，这正是它的设计目的。

### `layout_` 属性

以 `layout_` 开头的属性由**父容器**读取，描述当前子 View 在父容器规则中的大小或位置。它不是子 View 自己决定的“绝对坐标”。

```xml
<TextView
    android:layout_width="0dp"
    android:layout_height="wrap_content"
    android:layout_weight="1"
    android:layout_marginStart="16dp"
    android:text="标题" />
```

这段里的 `layout_weight` 只有父容器是 `LinearLayout` 时才有意义，因为它是 LinearLayout 定义的布局规则。若把同样的子节点移到 `ConstraintLayout`，需要改用约束属性，如 `app:layout_constraintStart_toStartOf="parent"`。属性没有脱离父容器的普适“魔法效果”。

## 宽高、外边距和内边距

把一个 View 想成装内容的盒子：

```text
父容器边界
  [ margin（View 与兄弟/父边界的距离）
    [ View 边框 / background
      [ padding（内容与自身边界的距离）
        内容 ]]]
```

- `layout_width` / `layout_height`：这个盒子希望占多大空间。
- `layout_margin`：盒子**外面**留多大空白，由父容器摆放时使用。
- `padding`：盒子**里面**留多大空白，影响文字、图像等内容的位置。

例如要做一个有呼吸感的按钮：用 `layout_marginTop` 拉开它与上方控件的距离，用 `paddingStart`/`paddingEnd` 增加按钮文字到边缘的距离。不要用多个空 `TextView` 或一串空格来“撑开距离”；它们无法适配字体、屏幕和无障碍设置。

优先使用 `Start`/`End`，而不是 `Left`/`Right`，这样界面在从右到左（RTL）语言下可自动镜像。绝大多数长度用 `dp`，文本大小用 `sp`，原因与资源适配已在第 3 篇说明。

## ID：对象树里的资源化地址，不是 Java 变量

给 View 加上：

```xml
android:id="@+id/name_input"
```

会在资源表中声明 `R.id.name_input`。运行时，`findViewById(R.id.name_input)` 会从当前根 View 开始遍历树，返回匹配 ID 的对象。ID 的作用是让布局、代码和测试能指向同一个节点；它并不会自动创建 Java 成员变量，也不会自动让两个同名 View 同步状态。

首次定义使用 `@+id/`；随后引用同一个 ID 使用 `@id/`。常见规则如下：

```xml
<EditText
    android:id="@+id/name_input"
    android:layout_width="match_parent"
    android:layout_height="wrap_content" />

<TextView
    android:labelFor="@id/name_input"
    android:layout_width="wrap_content"
    android:layout_height="wrap_content" />
```

`labelFor` 是对已存在 ID 的引用，所以没有加号。每个被 Java 操作、被约束引用或需要无障碍关联的控件通常都应有稳定、语义化的 ID；纯装饰且不会被引用的 View 可以没有 ID。命名可用名词加角色，例如 `name_input`、`save_button`、`result_text`，不要用 `button1` 这种很快失去含义的名字。

## 一个完整的最小表单布局

下面的 `res/layout/activity_profile.xml` 只使用基础 `LinearLayout`，因而特别适合观察属性。它在任何配置了 AndroidX AppCompat 的传统 Java 项目中都接近可运行。

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
        android:text="创建个人资料"
        android:textSize="22sp"
        android:textStyle="bold" />

    <TextView
        android:id="@+id/name_label"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="20dp"
        android:labelFor="@id/name_input"
        android:text="姓名" />

    <EditText
        android:id="@+id/name_input"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:hint="请输入姓名"
        android:inputType="textPersonName"
        android:maxLines="1" />

    <Button
        android:id="@+id/save_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="16dp"
        android:text="保存" />

    <TextView
        android:id="@+id/status_text"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="12dp"
        android:visibility="gone" />
</LinearLayout>
```

为了突出结构，示例把少量文本直接写在 XML 中；真实需要多语言的应用应把它们抽到 `strings.xml`。`inputType="textPersonName"` 不只是限制字符，它还会给输入法提供“这是姓名”的语义提示。`maxLines="1"` 则让单行姓名不因回车扩展为多行。

下面的 Activity 完成“读取、校验、显示结果”的闭环。先设置布局，再找 ID；泛型返回类型可由 Java 推断，因此不必强制转换。

```java
package com.example.myapp;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class ProfileActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_profile);

        EditText nameInput = findViewById(R.id.name_input);
        Button saveButton = findViewById(R.id.save_button);
        TextView statusText = findViewById(R.id.status_text);

        saveButton.setOnClickListener(view -> {
            String name = nameInput.getText().toString().trim();
            if (name.isEmpty()) {
                nameInput.setError("请输入姓名");
                return;
            }

            statusText.setText("已保存：" + name);
            statusText.setVisibility(View.VISIBLE);
        });
    }
}
```

点击前，`status_text` 是 `gone`，不占高度；点击且校验通过后，代码显式将它改为 `VISIBLE`。这也说明 XML 主要表达初始状态，后续 UI 状态可以由 Java 响应事件改变。

## ConstraintLayout 的属性为何多一个 `app:`

当页面的相对关系较复杂，`ConstraintLayout` 可减少多层 LinearLayout 嵌套。它的约束属性来自 AndroidX 库而非系统 `android` 命名空间，因此根节点还需要声明 `app`：

```xml
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <Button
        android:id="@+id/save_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="保存"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />
</androidx.constraintlayout.widget.ConstraintLayout>
```

这表示按钮的底边约束到父容器底边、末端约束到父容器末端。约束不是 `margin` 的替代品：约束先定义“相对谁”，margin 再定义与该目标之间留多远。若约束缺失，编辑器可能显示预览位置，但运行时布局会不符合预期。

## 常见误解与检查清单

- **把 `id` 当作 Java 对象**：`R.id.save_button` 是整数资源标识；真正的 `Button` 要通过 `findViewById` 取得。
- **只写 `layout_width` 不写高度**：两个尺寸属性都必填，资源编译会直接报错。
- **在 LinearLayout 中给 `layout_weight` 配 `wrap_content`**：若目的是分配剩余空间，沿排列方向通常把对应尺寸设为 `0dp`，再用 weight 分配；否则效果容易与预期不同。
- **把颜色、文字和间距全写死**：一次性原型可以接受，正式页面应优先使用 `@color`、`@string`、`@dimen`，便于适配与维护。
- **用 `px` 定尺寸**：这会在不同密度屏幕上呈现不同物理大小；通常用 `dp`，文字用 `sp`。
- **用 `invisible` 和 `gone` 不加区分**：前者保留位置，后者移除布局空间。

## 本篇小结

- XML 布局的固定基础是根节点命名空间，以及每个 View 必须有的 `layout_width`、`layout_height`。
- 普通属性描述 View 自己，`layout_` 属性由父容器解释；换容器时布局属性往往需要随之改变。
- `margin` 在 View 外部，`padding` 在内容与自身边缘之间；长度用 `dp`，字体用 `sp`。
- `@+id` 声明资源化 ID，`findViewById` 才能找到运行时对象；ID 不会自动变成变量。
- XML 给出初始 UI，Java 通过事件读取输入、校验并更新 View，二者共同构成传统 Android 的界面闭环。
