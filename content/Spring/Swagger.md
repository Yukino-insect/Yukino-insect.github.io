+++
date = '2025-09-21T10:55:02+08:00'
draft = false
title = 'Swagger'
+++

**Swagger** 是一个 **RESTful API 文档生成工具**，用来自动生成接口文档，并提供可视化 UI 方便调试接口。

它解决的问题：

- 后端写完接口后，文档难以维护
- 前端调试需要了解接口参数和返回
- 测试人员需要接口说明

有了 Swagger，写好接口注解后，文档会自动生成，访问 `/swagger-ui.html` 或 `/swagger-ui/index.html` 就能看到可视化界面。

#### Swagger 主要组成

1. **Swagger-Core**：提供 Java 注解支持（在代码里加注解描述接口）
2. **Swagger-UI**：自动生成的网页 UI，方便调试
3. **OpenAPI/Swagger 规范**：API 描述的 JSON/YAML 标准格式

> 什么是 Swagger
>
> - **Swagger** 最初是一个 RESTful API 描述规范和工具集
> - 它的作用：
>   - **定义接口**：描述 URL、请求方法、请求参数、响应格式、状态码等
>   - **生成文档**：自动生成可视化文档和测试界面（Swagger UI）
>   - **辅助开发**：前端、测试人员、第三方都能根据文档调试接口
>
> 什么是 OpenAPI
>
> - **OpenAPI Specification (OAS)** 是 Swagger 的演进版本
> - 原理：
>   - 由 Linux 基金会接管，成为 **开放标准**
>   - 当前主流版本是 **OpenAPI 3.0 / 3.1**
> - 它用 **JSON 或 YAML** 来描述整个 REST API，包括：
>   - 路径（Paths）
>   - 请求参数（Parameters）
>   - 请求体（Request Body）
>   - 响应体（Responses）
>   - 安全认证（Security Schemes）
>   - 元信息（Info：标题、版本、描述）

### Spring Boot 中集成 Swagger

方式一：`springfox-swagger`

比较老的方案 Spring Boot 2.x 常用

```xml
<!-- Springfox 2.x 的版本 -->
<!--swagger依赖-->
<dependency>
    <groupId>io.springfox</groupId>
    <artifactId>springfox-swagger2</artifactId>
    <version>2.9.2</version>
</dependency>
<!--swagger ui-->
<dependency>
    <groupId>io.springfox</groupId>
    <artifactId>springfox-swagger-ui</artifactId>
    <version>2.9.2</version>
</dependency>
```

```xml
<!-- Springfox 2.x 的版本 -->
<dependency>
    <groupId>io.springfox</groupId>
    <artifactId>springfox-boot-starter</artifactId>
    <version>3.0.0</version>
</dependency>
```

配置类

```java
@Configuration
@EnableSwagger2
public class SwaggerConfig {

    @Bean
    public Docket api() {
        return new Docket(DocumentationType.SWAGGER_2)
                .apiInfo(apiInfo())
                .select()
                // 扫描指定包下的 Controller
                .apis(RequestHandlerSelectors.basePackage("com.example.controller"))
                .paths(PathSelectors.any())
                .build();
    }

    private ApiInfo apiInfo() {
        return new ApiInfoBuilder()
                .title("示例 API 文档")
                .description("Spring Boot + Swagger2 示例配置")
                .version("1.0.0")
                .build();
    }
}
```

controller 接口

```java
@RestController
@Api(tags = "用户模块", description = "用户相关接口")
public class UserController {

    @GetMapping("/users")
    @ApiOperation(value = "获取用户列表", notes = "返回所有用户信息")
    public String getUsers() {
        return "用户列表示例";
    }
}
```

接口文档 JSON: `http://localhost:8080/v2/api-docs`

Swagger UI: `http://localhost:8080/swagger-ui/index.html`

注解使用

- @Api：用于标注一个Controller
- @ApiOperation：用于请求方法上，说明方法的用途和作用
- @ApiImplicitParams与@ApiImplicitParam：它们两个都是作用在方法上用来设置参数，不过不同的是@ApiImplicitParams可以包含多个@ApiImplicitParam用来设置多个参数，而@ApiImplicitParam仅仅只是用来设置一个参数。
- @ApiModel：主要用于实体类上，对整个实体类进行描述
- @ApiModelProperty：主要用于实体类的字段上，对其属性进行描述

方式二：

**Spring Boot 3.x 推荐**（支持 OpenAPI 3 标准）

```xml
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>2.6.0</version>
</dependency>
```

无需额外配置即可访问

文档 UI: `http://localhost:8080/swagger-ui.html`

OpenAPI JSON: `http://localhost:8080/v3/api-docs`

它会**自动生成 OpenAPI 3 文档**

- 扫描你的 Spring MVC Controller、请求方法和 DTO，生成接口描述 JSON。

**自带 Swagger UI 前端**

- 提供可视化界面，通过浏览器访问 `/swagger-ui.html` 调试接口。

自动配置功能

引入依赖后，几乎不用写配置类就可以直接用：

- 扫描 Controller
- 生成 OpenAPI 文档 JSON（`/v3/api-docs`）
- 提供 Swagger UI 页面 (`/swagger-ui.html`)

> 如果需要定制，可以通过 `application.yml` 或配置类进一步修改文档信息，比如标题、版本、描述等。

`application.yml`配置

```yaml
springdoc:
  api-docs:
    path: /v3/api-docs       # OpenAPI JSON 文档访问路径
  swagger-ui:
    path: /swagger-ui.html   # Swagger UI 页面访问路径
```

`/v3/api-docs` -> JSON 格式接口文档

`/swagger-ui.html` -> 可视化界面

Swagger 配置类

```java
@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("示例 API 文档")
                        .version("1.0.0")
                        .description("这是一个示例的 Spring Boot Swagger/OpenAPI 配置")
                        .contact(new Contact().name("开发者").email("dev@example.com"))
                );
    }
}
```

controller 接口

```java
@RestController
@Tag(name = "用户模块", description = "用户相关接口")
public class UserController {

    @GetMapping("/users")
    @Operation(summary = "获取用户列表", description = "返回所有用户信息")
    public String getUsers() {
        return "用户列表示例";
    }
}
```

注解介绍：

类级别注解

`@Tag`描述一个模块或 Controller 的功能分组

```java
@Tag(name="用户模块", description="用户相关接口") 
```

`@SecurityRequirement`指定整个 Controller 需要的安全策略

```java
@SecurityRequirement(name="bearerAuth")
```

> **使用场景**：用在 Controller 类上，对整个类的接口进行统一说明或安全要求。

方法级别注解

`@Operation`描述接口的功能、摘要、备注等

```java
@Operation(summary="获取用户列表", description="返回所有用户信息")
```

`@ApiResponses`描述接口的返回状态码及说明

```java
@ApiResponses({ @ApiResponse(responseCode="200", description="成功") })
```
