+++
date = '2026-02-19T16:02:28+08:00'
draft = false
title = 'spring 的 @ModelAttribute 注解'
+++

今天再来认识一个注解 `@ModelAttribute`

## 一、`@ModelAttribute` 是什么？

`@ModelAttribute` 是 **Spring Framework** MVC 中的一个参数绑定注解。

它的作用是：

> 把请求参数（query、form 表单）绑定到一个 Java 对象上。

------

## 二、为什么不加 `@ModelAttribute` 也能用？

因为在 Spring MVC 里有一个规则：

### 规则：

- 简单类型（String、int、Long…）默认按 `@RequestParam` 处理
- 复杂对象（自定义类）默认按 `@ModelAttribute` 处理（GET 请求时）

所以：

```java
public CommonResult<String> test(Param param)
```

等价于：

```java
public CommonResult<String> test(@ModelAttribute Param param)
```

在 GET 场景下完全一样。

------

## 三、它底层是怎么工作的？

假设请求是：

```http
GET /api?param=123
```

Spring 做了什么：

1. 创建一个 `Param` 对象
2. 找到 query 参数里的 `param`
3. 调用 `setParam("123")`
4. 把对象传给 controller

本质是通过 **数据绑定器（DataBinder）** 自动反射赋值。

------

## 四、和 `@RequestParam` 的区别

### 单参数场景

```java
public void test(@RequestParam String param)
```

特点：

- 直接绑定一个字段
- 默认 required = true
- 更精确控制

------

### 多参数场景

```java
public void test(@ModelAttribute Param param)
```

特点：

- 自动封装成对象
- 更清晰
- 更适合参数多的场景

------

## 五、`@PathVariable`

在 Spring 里常用的是：

```java
@GetMapping("/user/{id}")
public void get(@PathVariable Long id)
```

URL 是：

```http
/user/100
```

区别：

| 注解            | 参数来源                  |
| --------------- | ------------------------- |
| @RequestParam   | ?id=100                   |
| @PathVariable   | /user/100                 |
| @ModelAttribute | 自动封装 query 参数到对象 |

------

## 六、GET vs POST 时的行为

### GET 请求

- 复杂对象默认按 `@ModelAttribute` 处理

### POST + JSON

- 必须用 `@RequestBody`

```java
@PostMapping("/api")
public void test(@RequestBody Param param)
```

否则 Spring 不会从 JSON 里解析对象。

------

## 七、`@ModelAttribute` 还有一个隐藏能力

它不仅能绑定参数，还能：

### 在方法上使用

```java
@ModelAttribute
public void init(Model model) {
    model.addAttribute("user", getUser());
}
```

作用：

> 在每个 Controller 方法执行前，向 Model 里预放数据

这个功能很多人不知道。

------

## 八、关键区别总结

| 场景         | 推荐            |
| ------------ | --------------- |
| 少量简单参数 | @RequestParam   |
| 多参数封装   | @ModelAttribute |
| 路径参数     | @PathVariable   |
| JSON 请求体  | @RequestBody    |

------

## 九、一个重要注意点

`@ModelAttribute` 绑定的是：

- query 参数
- 表单数据（x-www-form-urlencoded）

不是 JSON。
