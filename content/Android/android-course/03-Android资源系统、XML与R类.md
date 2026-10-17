+++
date = '2026-10-17T11:00:00+08:00'
draft = false
title = 'Android 资源系统、XML 与 R 类：界面文件如何被代码找到'
+++

前两篇中，我们已经在 Java 里写过 `R.layout.activity_main`，也在 XML 里写过 `@string/app_name`。它们看起来像互相引用，却不需要手动创建 `R.java`。这一点并不神秘：Android 的资源系统会把 `res/` 中符合规则的文件编译为资源表，再生成稳定的 Java/Kotlin 访问符号。本篇解释这条链路，并建立“什么放代码、什么放资源”的判断标准。

## 资源系统解决什么问题

资源（resource）是应用随安装包携带、但不直接写死在 Java 逻辑中的内容：文本、颜色、尺寸、布局、图片、动画、主题等。把它们集中在 `res/` 目录有三项直接收益：

- **复用**：按钮文案、间距和颜色可在多个页面引用。
- **适配**：系统可按语言、屏幕密度、夜间模式等条件选择最合适的一份资源。
- **分离**：Java 关注行为，XML/资源关注初始界面与展示数据。

资源不是“XML 文件的别名”。一张 PNG、一段字符串、一个颜色值都可以是资源；XML 只是表达结构化资源的一种格式。

## `res` 的目录就是资源类型

`app/src/main/res/` 下的一级目录名具有固定含义，不能随意改成 `images` 或 `my_layout`。构建工具根据目录判断资源类型，并在 `R` 中生成相应内部类。

| 目录 | 放什么 | Java 中的典型访问 |
| ---- | ------ | ----------------- |
| `layout/` | View 层级 XML | `R.layout.activity_main` |
| `values/` | 字符串、颜色、尺寸、样式等值型 XML | `R.string.app_name` |
| `drawable/` | 矢量图、形状 XML、普通位图 | `R.drawable.ic_logo` |
| `mipmap-*/` | 各密度应用图标 | `R.mipmap.ic_launcher` |
| `color/` | 颜色值或颜色状态列表 XML | `R.color.brand_primary` |
| `menu/` | 菜单 XML | `R.menu.main_menu` |
| `navigation/` | 导航图 XML | `R.navigation.main_nav` |
| `anim/`、`animator/` | 补间动画、属性动画资源 | `R.anim.fade_in` |
| `xml/` | 不属于其他类型的通用 XML | `R.xml.network_security_config` |
| `raw/` | 原样打包的音频、JSON 等文件 | `R.raw.welcome_audio` |

`values/` 比较特殊：文件名不直接决定资源名，XML 内部元素的 `name` 才决定。相反，`layout/activity_main.xml` 的资源名就是 `activity_main`。资源名必须由小写字母、数字和下划线组成，不能有大写字母、连字符或空格。

## XML 有两种常见角色

初学时很容易把所有 XML 看成同一种东西。实际上，至少要区分两类：

1. **布局 XML**：根标签是 `LinearLayout`、`ConstraintLayout` 等 View 类，描述要创建的对象树。
2. **值资源 XML**：根标签通常是 `<resources>`，每个子元素定义一个可被引用的值。

例如，`res/values/strings.xml`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">问候应用</string>
    <string name="greeting_format">你好，%1$s！</string>
    <string name="name_required">名字不能为空</string>
</resources>
```

`%1$s` 表示第一个参数按字符串格式填入。Java 中应通过资源系统格式化，而不是把用户可见文本散落在代码里：

```java
String message = getString(R.string.greeting_format, name);
resultText.setText(message);
```

这里的输入是资源 ID 和参数，输出是当前语言环境下已经格式化的 `String`。以后新增英文翻译时，只需补充对应语言限定目录中的同名资源，而不用改这段业务代码。

## 引用资源的两种符号

XML 中最常见的两个前缀分别代表“引用已有资源”和“在这里创建一个 ID”：

| 写法 | 含义 | 示例 |
| ---- | ---- | ---- |
| `@类型/名称` | 使用已经定义的资源 | `@string/app_name` |
| `@+id/名称` | 首次声明并使用一个 View ID | `@+id/greet_button` |

下面是一个布局资源。`android:text` 接收的是文本资源引用，`android:background` 接收的是 drawable 引用；属性期望的资源类型不同，不能因为都以 `@` 开头就互换。

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="@dimen/page_padding">

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="@string/app_name" />

    <Button
        android:id="@+id/greet_button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:background="@drawable/bg_primary_button"
        android:text="@string/greet" />
</LinearLayout>
```

对应的 `res/values/dimens.xml` 与 `res/values/colors.xml` 可以是：

```xml
<resources>
    <dimen name="page_padding">24dp</dimen>
</resources>
```

```xml
<resources>
    <color name="brand_primary">#1565C0</color>
</resources>
```

把颜色写为 `#1565C0` 并非永远错误，但若它在多个地方重复出现，就应该抽取为 `@color/brand_primary`，否则后续换主题时容易漏改。

## `R` 类从哪里来

`R` 是 Android 构建过程根据资源表自动生成的类。它可以概念化为：

```java
public final class R {
    public static final class layout {
        public static final int activity_main = ...;
    }

    public static final class string {
        public static final int app_name = ...;
    }

    public static final class id {
        public static final int greet_button = ...;
    }
}
```

省略号不是让你填写的数字。资源 ID 是构建工具分配的整数标识，应用代码应只使用 `R.layout.activity_main` 这样的符号。手工创建、编辑或从别的模块复制 `R.java`，等于在和构建工具争夺唯一的事实来源，通常只会制造更混乱的错误。

链路可以这样记忆：

```text
res/layout/activity_main.xml
  -> 资源编译器登记类型 layout、名称 activity_main
  -> 生成 R.layout.activity_main
  -> setContentView 使用该 ID 加载并解析布局
```

Java 中的 `R` 应来自当前应用的 `namespace`。如果 IDE 自动导入了 `android.R`，你会发现自己定义的 `R.layout.activity_main` 或 `R.id.xxx` 不存在。此时应删除错误的 `import android.R;`，再确认资源本身没有 XML 错误。

## 限定符：同名资源如何适配不同设备

资源目录可以在类型名后加限定符，系统会依据当前设备配置挑选最匹配的一份。例如：

```text
res/
├── values/strings.xml          # 默认语言
├── values-zh-rCN/strings.xml   # 简体中文（中国）
├── values-en/strings.xml       # 英文
├── values-night/colors.xml     # 夜间模式颜色
├── drawable/icon.png           # 默认密度图
├── drawable-hdpi/icon.png      # 高密度图
└── drawable-xxhdpi/icon.png    # 超高密度图
```

同一资源名如 `app_name` 或 `icon` 可以在不同限定目录出现；它们共同组成一个资源的多个配置版本。系统优先选择最具体且匹配当前配置的版本，若不存在就回退到默认目录。因此每类需要适配的资源都应保留无限定符的默认版本，否则某些设备上可能找不到资源。

语言目录的目标是本地化，并不是“把所有字符串复制一份”。不同语言文件应保持需要使用的资源键一致；缺键时系统会回退到默认资源。对于可翻译文本，优先写在 `strings.xml`，避免把中文直接硬编码在布局和 Java 里。

## `dp`、`sp` 与值资源

设备的像素密度不同，`100px` 在两台手机上的物理大小可能不同。布局长度通常使用 `dp`（density-independent pixel），文字大小通常使用 `sp`（scale-independent pixel）：

```text
实际像素 px = dp × 屏幕密度系数
文字实际像素 px = sp × 屏幕密度系数 × 用户字体缩放系数
```

如果某设备密度系数为 3，`24dp` 大约对应 72px；用户把系统字体放大时，`16sp` 还会随字体缩放变化。用 `sp` 定义文本是为了尊重可访问性设置。以下值资源可供布局复用：

```xml
<resources>
    <dimen name="title_text_size">20sp</dimen>
    <dimen name="content_spacing">12dp</dimen>
</resources>
```

## 资源合并与常见错误

最终应用的资源不只来自 `app/res`，还可能来自依赖库和不同构建变体。构建时会合并这些资源，名称冲突、格式错误或引用循环会让生成 `R` 失败。看到大量 `R cannot be resolved` 时，不应先手动导入或新建 `R`，而应按下面顺序检查：

1. 查看 Build 输出中更早出现的资源/XML 错误，例如未闭合标签、非法资源名。
2. 检查 `res` 一级目录和文件名是否符合规则，尤其是大写字母与 `-`。
3. 执行 Gradle Sync 并重新构建，确认依赖和构建脚本已生效。
4. 确认 Java 文件没有导入 `android.R`，并且使用的是本模块资源。
5. 若是多模块工程，确认依赖关系和资源可见性是否符合设计。

“Clean Project 能解决一切”是常见误解。清理只能删除构建产物；它不能修复非法 XML、错误导入或资源命名错误。先读第一个真实错误，远比反复清理有效。

## 本篇小结

- `res/` 是由构建工具理解的资源目录；一级目录名决定资源类型，名称必须使用小写和下划线。
- 布局 XML 描述 View 树，`values` XML 定义字符串、颜色、尺寸等可复用值。
- `@string/name` 用已有资源，`@+id/name` 首次声明一个 View ID。
- `R` 是资源编译自动生成的访问入口，绝不应手工维护；错误导入 `android.R` 是常见故障源。
- 通过语言、夜间模式、密度等限定符，同名资源可在不同设备配置下自动适配。
