+++

date = '2026-08-19T18:28:00+08:00'
draft = false
title = '高阶函数：reduce'

+++

`reduce` 是 JavaScript 数组最强大的高阶函数之一，核心逻辑是将数组中的所有元素通过一个累加器（accumulator）逐步计算，最终**合并/归纳为一个单一的值**。

------

### 一、 基本语法

JavaScript

```javascript
array.reduce((accumulator, currentValue, currentIndex, array) => {
  // 返回更新后的 accumulator
}, initialValue);
```

**关键参数：**

- **`accumulator`（累加器/暂存值）：** 上一次回调函数返回的结果。
- **`currentValue`（当前项）：** 数组正在处理的当前元素。
- **`initialValue`（初始值，建议必传）：** 第一次执行回调时 `accumulator` 的初始值。

------

### 二、 核心机制解析

如果不传 `initialValue`，`reduce` 会默认将数组的第 0 个元素作为初始值，并从第 1 个元素开始遍历；**如果数组为空且未提供初始值，程序会直接报错**（`TypeError`）。

为了代码稳健，**强烈建议始终明确指定 `initialValue`**。

#### 执行过程示例：数组求和

JavaScript

```javascript
const nums = [10, 20, 30];

const sum = nums.reduce((acc, cur) => {
  return acc + cur;
}, 0); // 初始值 acc = 0
```

| **轮次**    | **acc (累加器)** | **cur (当前项)** | **返回值 (acc + cur)** |
| ----------- | ---------------- | ---------------- | ---------------------- |
| **第 1 轮** | `0` (初始值)     | `10`             | `10`                   |
| **第 2 轮** | `10`             | `20`             | `30`                   |
| **第 3 轮** | `30`             | `30`             | `60`                   |

------

### 三、 常见应用场景

`reduce` 不仅能算数字，它的结果可以是对象、数组甚至函数。

**1. 按属性分组（Group By）**

JavaScript

```javascript
const users = [
  { name: 'Alice', role: 'admin' },
  { name: 'Bob', role: 'user' },
  { name: 'Charlie', role: 'admin' }
];

const grouped = users.reduce((acc, user) => {
  const role = user.role;
  if (!acc[role]) acc[role] = [];
  acc[role].push(user);
  return acc; // 切记：每轮必须返回 acc
}, {});

// 输出: { admin: [{...}, {...}], user: [{...}] }
```

**2. 统计元素出现次数**

JavaScript

```javascript
const fruits = ['apple', 'banana', 'apple', 'orange', 'banana'];

const countMap = fruits.reduce((acc, fruit) => {
  acc[fruit] = (acc[fruit] || 0) + 1;
  return acc;
}, {});

// 输出: { apple: 2, banana: 2, orange: 1 }
```

**3. 数组扁平化（替代简单的 flat）**

JavaScript

```javascript
const nested = [[1, 2], [3, 4], [5]];
const flat = nested.reduce((acc, cur) => acc.concat(cur), []);
// 输出: [1, 2, 3, 4, 5]
```

------

### 四、 最佳实践与注意事项

- **必回返回值：** 回调函数内部**必须**返回 `accumulator`，否则下一轮循环中 `acc` 会变成 `undefined`。
- **切勿过度使用：** 如果只是简单的转换（如提取某个字段），用 `map` 更清晰；如果只是筛除元素，用 `filter` 更直接。强行把简单逻辑写成复杂的 `reduce` 会降低代码可读性。