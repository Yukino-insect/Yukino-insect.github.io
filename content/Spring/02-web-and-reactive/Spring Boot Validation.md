+++
date = '2026-01-10T19:58:14+08:00'
draft = false
title = 'Spring Boot Validation'
+++

参数校验的目标不是少写几个 `if`，而是把**结构性规则**从业务流程里拆出来：字段不能为空、长度不能超限、邮箱格式正确、嵌套对象也要校验、创建和更新场景规则不同。这类规则适合交给 Bean Validation。

Spring Boot 对 Bean Validation 做了集成。实际使用时，通常是 Bean Validation 规范、Hibernate Validator 实现和 Spring MVC 方法参数校验三者一起工作。

## 一、依赖与基本概念

Spring Boot 2.3 之后，`spring-boot-starter-web` 不再默认携带 Validation 依赖，通常需要显式引入：

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
</dependency>
```

几个概念要先分清：

| 名称 | 说明 |
| --- | --- |
| Bean Validation | Java 的参数校验规范 |
| Hibernate Validator | Bean Validation 最常用的实现 |
| `@Valid` | 标准注解，可触发 Bean 校验，也可用于嵌套校验 |
| `@Validated` | Spring 扩展注解，支持分组校验，也可用于类或方法参数 |
| `ConstraintValidator` | 自定义校验器接口 |

Spring Boot 做的是自动装配校验器，并把校验能力接入 Spring MVC、方法校验和异常体系。规范、实现和框架集成不是同一件事，混在一起看，就很容易得出一些看似正确但实际模糊的结论。

## 二、DTO 字段校验

最常见的写法是在请求 DTO 上声明字段规则：

```java
public class UserCreateRequest {

    @NotBlank(message = "用户名不能为空")
    @Size(max = 128, message = "用户名长度不能超过 128 个字符")
    private String userName;

    @Email(message = "邮箱格式不正确")
    private String email;

    @NotNull(message = "年龄不能为空")
    @Min(value = 18, message = "年龄不能小于 18")
    @Max(value = 60, message = "年龄不能大于 60")
    private Integer age;

    @NotEmpty(message = "兴趣爱好不能为空")
    @Size(max = 5, message = "兴趣爱好最多 5 个")
    private List<String> hobbies;
}
```

Controller 中使用 `@Valid` 或 `@Validated` 触发校验：

```java
@PostMapping("/users")
public void createUser(@RequestBody @Valid UserCreateRequest request) {
    userService.create(request);
}
```

如果不在方法参数上加 `@Valid` / `@Validated`，DTO 字段上的注解只是在类上安静地存在，不会自动生效。注解不会自己走进执行链路，真遗憾。

## 三、常用注解

常见约束可以按类型理解：

| 注解 | 适用类型 | 含义 |
| --- | --- | --- |
| `@NotNull` | 任意对象 | 不能为 `null` |
| `@NotEmpty` | 字符串、集合、数组、Map | 不能为 `null` 且长度或大小大于 0 |
| `@NotBlank` | 字符串 | 不能为 `null`，且去掉空白后不能为空 |
| `@Size` | 字符串、集合、数组、Map | 限制长度或大小 |
| `@Min` / `@Max` | 数字 | 限制最小值和最大值 |
| `@DecimalMin` / `@DecimalMax` | 数字、字符串数字 | 支持小数边界 |
| `@Email` | 字符串 | 校验邮箱格式 |
| `@Pattern` | 字符串 | 使用正则表达式校验 |
| `@Past` / `@Future` | 日期时间 | 必须是过去或未来时间 |

`@NotNull`、`@NotEmpty`、`@NotBlank` 的边界尤其常见：

- `@NotNull` 只关心是不是 `null`。
- `@NotEmpty` 还要求集合或字符串长度大于 0。
- `@NotBlank` 会把空白字符串也判为非法。

用户名、标题这类文本通常用 `@NotBlank`；集合参数通常用 `@NotEmpty`；数字、枚举、日期对象通常用 `@NotNull`。

## 四、`@Valid` 与 `@Validated`

这两个注解最容易被说乱。准确一点：

- `@Valid` 是标准注解，常用于方法参数、字段嵌套校验。
- `@Validated` 是 Spring 注解，常用于方法参数、类上方法校验、分组校验。
- DTO 中的嵌套字段要继续校验，必须在字段上使用 `@Valid`。
- Controller 类上加 `@Validated` 可以启用普通方法参数校验。

对照表如下：

| 对比点 | `@Valid` | `@Validated` |
| --- | --- | --- |
| 来源 | Bean Validation 标准 | Spring 扩展 |
| 方法参数校验 | 支持 | 支持 |
| Controller 类上统一启用方法校验 | 不适合 | 支持 |
| 嵌套字段校验 | 支持 | 不用于嵌套字段 |
| 分组校验 | 不直接指定分组 | 支持 |

## 五、三种典型用法

### 1. 请求体 DTO 校验

```java
@PostMapping("/users")
public void create(@RequestBody @Valid UserCreateRequest request) {
}
```

这是最常见、最推荐的入口。`@RequestBody` 负责读取 JSON，`@Valid` 负责触发 DTO 字段校验。

### 2. 普通参数校验

如果直接校验方法参数，需要在 Controller 类上启用 `@Validated`：

```java
@RestController
@Validated
public class UserController {

    @GetMapping("/users")
    public void list(@RequestParam @Min(1) Integer pageNo) {
    }
}
```

没有类上的 `@Validated` 时，`@Min` 这类直接标在普通参数上的约束通常不会按预期生效。

### 3. 嵌套对象校验

DTO 内部包含另一个对象或集合时，需要在字段上继续加 `@Valid`：

```java
public class OrderCreateRequest {

    @NotBlank(message = "订单号不能为空")
    private String orderNo;

    @Valid
    @NotEmpty(message = "商品明细不能为空")
    private List<OrderItemRequest> items;
}

public class OrderItemRequest {

    @NotNull(message = "商品 ID 不能为空")
    private Long skuId;

    @Min(value = 1, message = "购买数量至少为 1")
    private Integer quantity;
}
```

如果缺少字段上的 `@Valid`，`items` 本身可能通过校验，但 `OrderItemRequest` 里的规则不会继续执行。

## 六、分组校验

创建和更新经常使用同一个 DTO，但规则不同。例如创建时不需要传 `id`，更新时必须传 `id`。

先定义分组接口：

```java
public interface CreateGroup {
}

public interface UpdateGroup {
}
```

在 DTO 上声明不同分组：

```java
public class UserSaveRequest {

    @NotNull(message = "用户 ID 不能为空", groups = UpdateGroup.class)
    private Long id;

    @NotBlank(message = "用户名不能为空", groups = {CreateGroup.class, UpdateGroup.class})
    private String userName;
}
```

在 Controller 入口指定分组：

```java
@PostMapping("/users")
public void create(@RequestBody @Validated(CreateGroup.class) UserSaveRequest request) {
}

@PutMapping("/users/{id}")
public void update(@RequestBody @Validated(UpdateGroup.class) UserSaveRequest request) {
}
```

分组校验适合处理“同一个字段在不同接口规则不同”的情况。如果规则差异已经很大，直接拆成不同 DTO 往往更清楚。

## 七、自定义枚举校验

业务中经常要校验某个字段必须属于指定枚举值。可以定义自定义注解：

```java
@Documented
@Constraint(validatedBy = EnumValueValidator.class)
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
public @interface EnumValue {

    String message() default "枚举值不合法";

    int[] values();

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
```

实现校验器：

```java
public class EnumValueValidator implements ConstraintValidator<EnumValue, Integer> {

    private Set<Integer> allowedValues;

    @Override
    public void initialize(EnumValue annotation) {
        this.allowedValues = Arrays.stream(annotation.values())
                .boxed()
                .collect(Collectors.toSet());
    }

    @Override
    public boolean isValid(Integer value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;
        }
        return allowedValues.contains(value);
    }
}
```

使用方式：

```java
public class UserCreateRequest {

    @NotNull(message = "性别不能为空")
    @EnumValue(values = {1, 2}, message = "性别值不合法")
    private Integer gender;
}
```

自定义校验器通常不做空校验，让 `@NotNull` 负责必填规则。这样每个注解职责更单一。

## 八、业务校验不要都塞进 Validation

Bean Validation 适合处理结构性规则，但不适合处理所有业务规则。

适合放进 Validation 的规则：

- 字段必填
- 长度范围
- 数字范围
- 格式校验
- 枚举值校验
- 嵌套对象结构校验

不适合硬塞进 Validation 的规则：

- 用户名是否已存在
- 当前用户是否能操作该资源
- 订单状态是否允许取消
- 库存是否足够
- 多个聚合对象之间的一致性检查

这类规则更适合放在 Service 层，或者用明确的业务校验器表达。

例如定义业务校验接口：

```java
public interface BusinessChecker {
    void check();
}
```

DTO 实现业务校验：

```java
public class CatalogSaveRequest implements BusinessChecker {

    @NotNull(message = "目录类型不能为空")
    private Integer type;

    private String name;

    private List<CatalogSaveRequest> children;

    @Override
    public void check() {
        if (type == 1 && !StringUtils.hasText(name)) {
            throw new IllegalArgumentException("章名称不能为空");
        }
        if (children == null || children.isEmpty()) {
            throw new IllegalArgumentException("不能出现空章");
        }
    }
}
```

再在 Service 或 AOP 中调用：

```java
public void saveCatalog(@Valid CatalogSaveRequest request) {
    request.check();
    catalogRepository.save(request);
}
```

AOP 可以做成统一入口，但不要滥用。业务校验如果太隐蔽，调试时会让人怀疑自己正在和空气斗智。

## 九、异常处理

Spring MVC 中参数校验失败时，常见异常有：

| 场景 | 常见异常 |
| --- | --- |
| `@RequestBody @Valid DTO` 失败 | `MethodArgumentNotValidException` |
| 普通方法参数校验失败 | `ConstraintViolationException` |
| 绑定表单对象失败 | `BindException` |

可以用 `@RestControllerAdvice` 统一返回错误信息：

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Map<String, String> handleMethodArgumentNotValid(MethodArgumentNotValidException ex) {
        return ex.getBindingResult()
                .getFieldErrors()
                .stream()
                .collect(Collectors.toMap(
                        FieldError::getField,
                        FieldError::getDefaultMessage,
                        (left, right) -> left
                ));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public List<String> handleConstraintViolation(ConstraintViolationException ex) {
        return ex.getConstraintViolations()
                .stream()
                .map(ConstraintViolation::getMessage)
                .toList();
    }
}
```

实际项目中应返回统一响应结构，例如业务码、提示信息、字段错误列表和请求追踪 ID。不要直接把框架异常原样抛给前端。

## 十、常见问题

### 1. DTO 上写了注解但不生效

检查 Controller 参数上是否有 `@Valid` 或 `@Validated`：

```java
public void create(@RequestBody @Valid UserCreateRequest request) {
}
```

如果是普通参数，检查 Controller 类上是否有 `@Validated`。

### 2. 嵌套对象不校验

检查嵌套字段上是否有 `@Valid`：

```java
@Valid
private AddressRequest address;
```

集合中的元素也一样，需要在集合字段上声明 `@Valid`。

### 3. 分组校验没有执行

检查入口是否使用 `@Validated(Group.class)`，只写 `@Valid` 不能指定 Spring 的分组入口：

```java
public void update(@RequestBody @Validated(UpdateGroup.class) UserSaveRequest request) {
}
```

### 4. `@NotBlank` 用在 Integer 上报错

`@NotBlank` 只能用于字符串。数字类型用 `@NotNull`、`@Min`、`@Max`。

### 5. Controller 类上有 `@Validated`，DTO 还要不要 `@Valid`

普通参数校验可以依赖类上的 `@Validated`，但请求体 DTO 仍建议在参数上显式写 `@Valid` 或 `@Validated`。嵌套字段始终需要 `@Valid`。

## 十一、总结

Spring Boot Validation 可以按下面几条记：

- DTO 字段规则用 Bean Validation 注解表达。
- Controller 请求 DTO 参数上写 `@Valid` 或 `@Validated` 触发校验。
- 普通参数校验通常需要 Controller 类上有 `@Validated`。
- 嵌套对象和集合字段必须使用 `@Valid`。
- 分组校验使用 `@Validated(Group.class)`。
- 自定义校验器适合处理稳定、结构化的字段规则。
- 复杂业务校验应放在 Service 或明确的业务校验器里。

校验的边界越清楚，Controller 和 Service 就越干净。否则所有规则都会混成一团，最后只剩下一种朴素的维护方式：祈祷没人改它。
