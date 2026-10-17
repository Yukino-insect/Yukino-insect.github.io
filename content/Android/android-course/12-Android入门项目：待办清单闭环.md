+++
date = '2026-10-17T09:24:00+08:00'
draft = false
title = 'Android 入门项目：待办清单闭环'
+++
最后用一个极小的待办清单把课程中的对象真正接起来。项目不追求架构名词齐全，而要验证一条完整数据流：用户输入文本，点击按钮，监听器读取 View 状态，Java 代码更新内存模型，再把模型渲染回列表。只要这条链路清楚，后续接数据库、网络和 ViewModel 才有可靠的位置。

## 目标与边界

本章使用 Java、XML、`Activity`、`RecyclerView` 和 `SharedPreferences`。它支持新增、勾选完成和在旋转屏幕后恢复；数据只适合少量简单文本，不能代替正式数据库。创建 Android Studio 的 Empty Views Activity 项目后，按向导加入 `RecyclerView` 依赖即可；AndroidX 版本应由 IDE/项目的版本目录统一管理，不要从教程中盲贴旧版本号。

```text
用户输入 -> EditText
点击“添加” -> OnClickListener
更新 List<Task> -> Adapter 通知列表
用户看到新行 -> onPause 保存 JSON
下次创建/旋转 -> onCreate 读取并再次渲染
```

## 资源与布局

先在 `res/values/strings.xml` 放可翻译文字，避免把界面文案散落在 Java 中：

```xml
<resources>
    <string name="app_name">待办清单</string>
    <string name="hint_task">例如：完成 Android 布局练习</string>
    <string name="add_task">添加</string>
</resources>
```

`res/layout/activity_main.xml` 可以使用纵向 `LinearLayout`：上方是输入与按钮，下方是列表。为简洁起见，输入区继续使用第 9 篇的横向布局；列表必须给出剩余高度。

```xml
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal">

        <EditText
            android:id="@+id/input_task"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:hint="@string/hint_task" />

        <Button
            android:id="@+id/button_add"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="@string/add_task" />
    </LinearLayout>

    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/list_tasks"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:layout_marginTop="12dp" />
</LinearLayout>
```

列表行 `res/layout/item_task.xml` 只含一个复选框。`RecyclerView` 会复用屏幕外的行 View，因此每次绑定时必须根据模型完整设置文字和选中状态，不能假设 View 保留着“正确的旧状态”。

```xml
<CheckBox xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/check_task"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_marginVertical="6dp"
    android:textSize="16sp" />
```

## 模型、适配器与 Activity 各管什么

`Task` 只表示数据，`TaskAdapter` 只把数据绑定到行 View，`MainActivity` 只协调界面事件和保存恢复。这个分工并不是为了形式漂亮，而是为了不让每一行的点击逻辑、资源查找和持久化细节挤进同一个类。

```java
public final class Task {
    public final String text;
    public boolean done;

    public Task(String text, boolean done) {
        this.text = text;
        this.done = done;
    }
}
```

Activity 的核心流程如下。`findViewById` 用 `R.id` 找到 XML 创建的对象；点击回调读取输入、更新模型、通知适配器；没有输入时不修改状态。

```java
public class MainActivity extends AppCompatActivity {
    private final List<Task> tasks = new ArrayList<>();
    private TaskAdapter adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        EditText input = findViewById(R.id.input_task);
        RecyclerView list = findViewById(R.id.list_tasks);
        adapter = new TaskAdapter(tasks, this::saveTasks);
        list.setLayoutManager(new LinearLayoutManager(this));
        list.setAdapter(adapter);

        findViewById(R.id.button_add).setOnClickListener(v -> {
            String text = input.getText().toString().trim();
            if (text.isEmpty()) {
                input.setError("请输入待办事项");
                return;
            }
            tasks.add(new Task(text, false));
            adapter.notifyItemInserted(tasks.size() - 1);
            input.setText("");
            saveTasks();
        });
    }
}
```

示例中的 `notifyItemInserted` 告诉列表“末尾新增了一项”，比不分情况调用 `notifyDataSetChanged()` 更精确。实际项目可以使用 `ListAdapter` 与 `DiffUtil`，让列表根据新旧不可变数据计算差异；在理解这条最小闭环以前，没有必要把它们当成魔法咒语。

## 适配器中的监听器陷阱

绑定 `CheckBox` 时，先暂时清除旧监听器，再设置 `checked`，最后注册新监听器。否则复用 View 时，`setChecked` 也可能触发上一行留下的监听器。

```java
@Override
public void onBindViewHolder(TaskHolder holder, int position) {
    Task task = tasks.get(position);
    holder.checkBox.setOnCheckedChangeListener(null);
    holder.checkBox.setText(task.text);
    holder.checkBox.setChecked(task.done);
    holder.checkBox.setOnCheckedChangeListener((button, checked) -> {
        task.done = checked;
        onTaskChanged.run();
    });
}
```

这是回调与可复用 UI 相遇时的典型边界：监听器知道“状态变了”，模型决定“变的是哪项数据”，保存函数决定“怎样落盘”。三者各自保持职责，错误会少得多。

## 生命周期与保存策略

旋转屏幕会销毁并新建 Activity，因此只靠字段 `tasks` 不够。短暂、可序列化的界面状态适合放 `onSaveInstanceState`；想让应用下次启动仍保留少量数据，可以在 `onPause` 或每次改动后用 `SharedPreferences` 保存 JSON。保存失败或数据量增长后，应迁移到 DataStore/Room，而不是无限增大一个 JSON 字符串。

网络同步则必须放后台线程，并在回调返回主线程更新列表；不能因为示例目前没有网络，就忘记第 8 篇和第 11 篇的线程规则。

## 验收清单

1. 新增空文本时有错误提示，列表不增加空行。
2. 新增两条文本后，列表显示两条，勾选任一项不会改变另一项。
3. 旋转设备后，当前文本和勾选状态仍正确。
4. 关闭再打开应用后，少量数据仍能恢复；若未实现持久化，明确知道这是当前边界。
5. 用大字体和窄屏模拟器测试，输入区与列表没有重叠或裁切。

## 总结

- 一个 Android 功能闭环至少包含资源、布局、View ID、事件回调、内存状态、渲染和生命周期边界。
- `RecyclerView` 的关键不是“显示列表”这么简单，而是复用 View 时始终从模型完整绑定状态。
- `Activity` 适合协调界面，但不应独自承担所有数据和业务职责；随着项目增长，应将状态与持久化逐步移出它。
- 至此你已经拥有继续学习 Fragment、Navigation、ViewModel、Room、网络层与 Compose 的地基。新技术只会替换链路中的某些表达方式，不会推翻你已经理解的系统边界。
