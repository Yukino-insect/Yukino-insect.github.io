+++
date = '2026-10-17T09:18:00+08:00'
draft = false
title = 'Android 布局：约束、线性、帧与定位'
+++
上一章说明了事件怎样抵达一个 `View`。事件能不能落到正确位置，前提却是 View 先被测量、摆放和绘制出来。本章讨论的布局就是这件事：**父容器根据规则为子 View 计算尺寸和坐标**。它和 CSS 布局有相似之处，但并不是浏览器的盒模型；Android 的每个 View 都运行在同一棵由父到子的对象树中。

## 一个 View 从 XML 到屏幕经历了什么

`setContentView(R.layout.activity_main)` 加载 XML 后，系统得到一棵 View 树。随后一次布局过程大致分为三步：

```text
measure：父容器把可用空间和限制传给子 View，子 View 报告自己希望的宽高
layout ：父容器决定每个子 View 的 left、top、right、bottom
draw   ：背景、内容和子 View 依次画入窗口的画布
```

例如屏幕可用宽度为 360dp，父容器左右各有 16dp 内边距，那么子项最多可用 328dp。`match_parent` 表示“在父亲给我的约束下尽量占满”，`wrap_content` 表示“按内容所需尺寸”，并不表示无限大。`dp` 是随屏幕密度换算的逻辑像素，`sp` 用于文字，能随用户的字体大小设置缩放；不要把 `px` 当成常规 UI 尺寸。

## 先掌握三种结构容器

### LinearLayout：一维顺序排列

`LinearLayout` 适合明确的横排或竖排关系。`orientation="vertical"` 表示从上到下；`horizontal` 表示从左到右。权重 `layout_weight` 用来分配**剩余空间**，因此参与权重分配的一维通常把对应尺寸设为 `0dp`。

```xml
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="horizontal"
    android:padding="16dp">

    <EditText
        android:id="@+id/input_task"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_weight="1"
        android:hint="输入待办事项" />

    <Button
        android:id="@+id/button_add"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginStart="8dp"
        android:text="添加" />
</LinearLayout>
```

这里输入框取得剩余宽度，按钮保留自身所需宽度。嵌套多层 `LinearLayout` 虽然能实现大多数界面，却会增加测量和阅读成本；能平铺的关系不要为了“看着整齐”套很多层。

### FrameLayout：叠放与单一内容槽

`FrameLayout` 的子项默认从左上角开始叠放，后添加的子项在更上层。它适合图片上覆盖角标、页面的加载遮罩，或 Activity/Fragment 的单一内容容器。

```xml
<FrameLayout
    android:layout_width="match_parent"
    android:layout_height="180dp">

    <ImageView
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:scaleType="centerCrop"
        android:src="@drawable/banner" />

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="bottom|end"
        android:layout_margin="12dp"
        android:text="今日推荐" />
</FrameLayout>
```

不要把 `FrameLayout` 误解成“自由绝对定位容器”。它只有有限的 `layout_gravity` 对齐能力；复杂的相对关系应交给约束布局。

### ConstraintLayout：多数页面的默认选择

`ConstraintLayout` 以“边和谁相连”描述二维位置。每个非容器子项至少应在水平方向和垂直方向各建立足够约束；否则编辑器会提示它在运行时落到左上角。`0dp` 在约束布局中叫 **match constraints**：尺寸由两侧约束决定，含义和 `match_parent` 不同。

```xml
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:padding="16dp">

    <TextView
        android:id="@+id/title"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:text="今天要完成什么？"
        android:textSize="20sp"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintTop_toTopOf="parent" />

    <Button
        android:id="@+id/button_add"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="添加"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintTop_toBottomOf="@id/title"
        android:layout_marginTop="16dp" />
</androidx.constraintlayout.widget.ConstraintLayout>
```

`title` 的左右均约束到父容器，因此 `0dp` 会填满中间可用宽度。按钮的顶部约束到标题底部，右侧约束到父容器右侧。约束描述的是**关系**，比写死 `marginTop="137dp"` 更能应对屏幕尺寸、语言长度与字体缩放变化。

## Android 布局与 CSS 的对应和差异

| 想解决的问题 | Web 常见方式 | Android 常见方式 |
| --- | --- | --- |
| 一维排列 | Flexbox | `LinearLayout` 或约束链 |
| 二维相对位置 | Grid / 定位 | `ConstraintLayout` |
| 叠放 | `position`、层叠上下文 | `FrameLayout`、elevation |
| 间距 | margin / padding | `layout_margin` / `padding` |
| 响应不同宽度 | media query | 资源限定符、约束、`sw<N>dp` |

最大的差异是，CSS 常由浏览器根据样式规则完成排版；Android 的 XML 属性会构造 Java/Kotlin 对象，容器类在运行时执行明确的 `onMeasure` 和 `onLayout`。因此 `layout_` 前缀属性通常由**父容器**解释，普通属性（如 `text`、`background`）由 View 自己解释。

## 避免脆弱布局的规则

- 优先用 `ConstraintLayout` 的约束和 `wrap_content`，不要用大量固定 dp 模拟坐标。
- 为文本预留扩展空间；翻译、无障碍字体放大和动态数据都会改变长度。
- 先使用 Material/AndroidX 提供的组件与主题尺寸，少依赖硬编码颜色和高度。
- 列表数据使用 `RecyclerView`，不要把未知数量的子项不断塞进 `ScrollView` 内的 `LinearLayout`。
- 用 Layout Inspector 查看真实 View 树，用不同尺寸模拟器、横竖屏与大字体检查，而不是只看设计预览。

## 本章小练习

把第 12 篇的待办输入区用 `LinearLayout` 完成，再尝试用 `ConstraintLayout` 重写一次。把按钮文字改为“添加一条新的待办事项”，再把系统字体调大。若控件重叠或被裁切，说明布局仍把某个偶然的尺寸当成了规则。

## 总结

- Android 布局的本质是父容器对 View 树执行测量、摆放和绘制。
- `LinearLayout` 用于一维顺序，`FrameLayout` 用于叠放或内容槽，`ConstraintLayout` 适合表达大多数二维关系。
- `0dp` 的含义要看父容器：在线性布局中常配合权重，在约束布局中表示由约束确定大小。
- 自适应界面依赖关系和资源限定符，而不是一串恰好在当前手机上好看的固定坐标。
