+++
date = '2025-09-21T16:48:14+08:00'
draft = false
title = 'Jackson'
+++

`spring-boot-starter-json` 是为 Spring Boot 提供 **JSON 序列化和反序列化** 功能，默认使用 Jackson

引入该依赖后，会自动带上一下依赖

| 依赖                           | 作用                                                  |
| ------------------------------ | ----------------------------------------------------- |
| jackson-databind               | 核心的 JSON 处理类库，负责序列化/反序列化             |
| jackson-core                   | 提供底层解析和生成 JSON 的功能                        |
| jackson-annotations            | 提供注解支持，如 @JsonProperty、@JsonIgnore 等        |
| jackson-datatype-jsr310        | 支持 Java 8 日期/时间类型（LocalDate, LocalDateTime） |
| jackson-module-parameter-names | 支持通过构造函数参数名反序列化对象                    |

当使用有关 Spring Web 相关的 starter 后，如 `spring-boot-starter-web`，它内部会自动包含 `spring-boot-starter-json`

#### 自动配置

Spring Boot 对 `spring-boot-starter-json` 提供了自动配置，它会**自动注册 ObjectMapper**。Spring Boot 会创建一个全局唯一的 `ObjectMapper` Bean，可直接注入使用。

```java
@Autowired
private ObjectMapper objectMapper;
```

它的序列化**默认配置**

- 对于**未知字段**会忽略

- 时间默认按照 ISO-8601（如 `2025-09-21T15:00:00`）格式化

- 它默认不序列化空子段（可通过配置修改）

这些默认配置可通过配置定制段

```properties
spring.jackson.date-format=yyyy-MM-dd HH:mm:ss
spring.jackson.serialization.indent_output=true
spring.jackson.default-property-inclusion=non_null
```

#### ObjectMapper 的使用

```java
ObjectMapper mapper = new ObjectMapper();

// Java 对象 -> JSON
String json = mapper.writeValueAsString(user);

// JSON -> Java 对象
User user2 = mapper.readValue(json, User.class);
```

对于实体类可以通过 **注解** 控制 json 的序列化

- `@JsonProperty("name")` 映射字段名

- `@JsonIgnore` 忽略序列化/反序列化

- `@JsonFormat(pattern="yyyy-MM-dd")` 日期格式化

- `@JsonInclude(JsonInclude.Include.NON_NULL)` 空字段不序列化

#### 在一些 Web 场景中

Controller 返回对象自动转换为 JSON 响应

```bash
Controller 方法返回对象
		|
	   \|/
HttpMessageConverter（MappingJackson2HttpMessageConverter）拦截
		|
	   \|/
ObjectMapper 将对象序列化为 JSON
		|
	   \|/
响应发送给客户端
```

**MappingJackson2HttpMessageConverter** 是 Spring MVC 内置的 HTTP 消息转换器（MessageConverter），专门处理 JSON。

它使用全局的 **ObjectMapper**（由 `spring-boot-starter-json` 提供并自动配置）完成序列化。

只需要在 Controller 中返回对象，Spring Boot 就会自动生成 JSON 响应。

REST API，接收 JSON 请求体并映射为 Java 对象

```bash
客户端发送 JSON 请求
  		|
  	   \|/
HttpMessageConverter（MappingJackson2HttpMessageConverter）拦截
  		|
  	   \|/
ObjectMapper 将 JSON 反序列化为 Java 对象
  		|
  	   \|/
Controller 方法接收对象
```
