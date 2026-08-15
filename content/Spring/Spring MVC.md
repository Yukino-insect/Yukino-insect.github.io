+++
date = '2025-09-18T22:09:15+08:00'
draft = false
title = 'Spring MVC'
+++

#### MVC（Model-View-Controller）

是软件开发中经典的设计模式，尤其在 Web 开发里广泛使用

它的主要目的是把数据处理、显示界面和请求控制分开，让系统结构清晰、可维护、可扩展

**Model（模型）**

- 表示 **数据和业务逻辑**
- 负责数据存取、处理业务规则
- 不关心显示方式

**View（视图）**

- **用户界面**，负责数据显示
- 可以是 HTML、JSP、Thymeleaf 模板等
- 只显示数据，不处理业务

**Controller（控制器）**

- **请求处理逻辑**
- 接收用户请求 -> 调用模型处理数据 -> 选择视图返回响应

**MVC 的工作流程**：

典型流程（以 Web 应用为例）：

1. 用户发送请求到服务器
2. **Controller** 接收请求
3. Controller 调用 **Model** 完成业务处理
4. Model 返回处理结果（数据对象）
5. Controller 选择 **View**，并把数据传给 View
6. **View** 渲染数据，生成 HTML 响应给用户

#### Spring MVC 的实现

Spring MVC 是 Spring 在 Spring Container Core 和 AOP 等技术基础上，遵循上述 Web MVC 的规范推出的 web 开发框架，目的是为了简化 Java 栈的 web 开发

它的核心组件有：

| 组件                  | 说明                                                         |
| --------------------- | ------------------------------------------------------------ |
| **DispatcherServlet** | 前端控制器（Front Controller），它就是一个由`Tomcat`加载的`Servlet`。所有请求都先到这里 |
| **HandlerMapping**    | 根据请求 URL 找到对应的 Controller 方法                      |
| **HandlerAdapter**    | 按照特定规则（HandlerAdapter要求的规则）去执行 Controller    |
| **Controller**        | 接收请求、调用业务逻辑（Service/Model）                      |
| **Model**             | 保存业务处理结果（数据对象），供视图渲染使用                 |
| **ViewResolver**      | 根据返回的视图名解析成具体 View（JSP/Thymeleaf/JSON 等）     |
| **View**              | 渲染输出页面或数据给客户端                                   |

##### 请求的处理流程

**首先用户发送请求——>DispatcherServlet**，前端控制器收到请求后自己不进行处理，而是委托给其他的解析器进行 处理，作为统一访问点，进行全局的流程控制；

**DispatcherServlet——>HandlerMapping**， HandlerMapping 将会把请求映射为 HandlerExecutionChain 对象（包含一 个Handler 处理器（页面控制器）对象、多个HandlerInterceptor 拦截器）对象，通过这种策略模式，很容易添加新 的映射策略；

**DispatcherServlet——>HandlerAdapter**，HandlerAdapter 将会把处理器包装为适配器，从而支持多种类型的处理器， 即适配器设计模式的应用，从而很容易支持很多类型的处理器；

**HandlerAdapter——>处理器功能处理方法的调用**，HandlerAdapter 将会根据适配的结果调用真正的处理器的功能处 理方法，完成功能处理；并返回一个ModelAndView 对象（包含模型数据、逻辑视图名）；

**ModelAndView 的逻辑视图名——> ViewResolver**，ViewResolver 将把逻辑视图名解析为具体的View，通过这种策 略模式，很容易更换其他视图技术；

**View——>渲染**，View 会根据传进来的Model 模型数据进行渲染，此处的Model 实际是一个Map 数据结构，因此 很容易支持其他视图技术；

**返回控制权给DispatcherServlet**，由DispatcherServlet 返回响应给用户，到此一个流程结束。

##### 核心注解

| 注解                          | 说明                                          |
| ----------------------------- | --------------------------------------------- |
| `@Controller`                 | 定义控制器类                                  |
| `@RestController`             | 等于 `@Controller + @ResponseBody`，返回 JSON |
| `@RequestMapping`             | 映射请求 URL 到方法                           |
| `@GetMapping`, `@PostMapping` | GET/POST 请求映射                             |
| `@PathVariable`               | 获取 URL 中的路径变量                         |
| `@RequestParam`               | 获取请求参数                                  |
| `@RequestBody`                | 获取请求体 JSON 并转换成对象                  |
| `@ResponseBody`               | 方法返回值直接作为 HTTP 响应体                |

**接下来练习一个例子**，这个例子我们先使用`web.xml`和 springmvc 注解的方式完成一个 mvc 项目，之后再介绍一个全注解的写法

在一个 spring mvc 项目中，一般需要两个核心的 xml 配置文件`web.xml`和`springmvc.xml`，其中前者主要配置`DispatcherServlet`、`Filter`和`Listener`，是由`Tomcat`容器加载的。当`Tomcat`加载了`DispatcherServlet`这个`Servlet`之后，由`DispatcherServlet`加载`springmvc.xml`配置文件。这个配置文件主要配置`HandlerMapping`、`ViewResolver`等组件。

**`web.xml`**

- **加载者**：Servlet 容器（Tomcat、Jetty、Undertow 等）。
- **过程**：
  - Web 应用启动时，Servlet 容器会解析 `WEB-INF/web.xml`。
  - 按顺序创建里面配置的 `Servlet`、`Filter`、`Listener`。
  - 比如：
    - 容器会实例化并初始化 **`DispatcherServlet`**。
    - 容器会注册并初始化 **`CharacterEncodingFilter`**。

> `Filter` 和 `Listener` 是 **Servlet 容器级别的组件**，不是 Spring Bean，所以 Spring 配置文件（springmvc.xml）无法控制它们的注册
>
> Filter（过滤器）
>
> 作用
>
> - 对请求和响应做预处理或后处理。
> - 常见用途：
>   1. **字符编码处理**（如 `CharacterEncodingFilter`，保证请求/响应 UTF-8）
>   2. **权限认证**（登录验证、权限校验）
>   3. **日志记录**
>   4. **GZIP 压缩**
>
> **工作原理**
>
> - 当请求进入 Servlet 容器时，**Filter 链会先被调用，处理请求后再传给 DispatcherServlet**。
> - 响应返回时，Filter 链可以对响应做加工。
>
> 注册方式
>
> - XML：`<filter>` + `<filter-mapping>`
> - 注解（Servlet 3.0+）：`@WebFilter`
>
> Listener（监听器）
>
> 作用
>
> - 对 Web 应用生命周期、Session 生命周期、Request 生命周期进行监听。
> - 常见用途：
>   1. **初始化资源**（数据库连接池、缓存等）
>   2. **清理资源**（应用关闭时释放资源）
>   3. **统计访问量、在线人数**
>   4. **Session 过期处理**
>
> 工作原理
>
> - 容器启动时，Listener 会被初始化并注册到 ServletContext。
> - 容器关闭时，Listener 可以执行清理逻辑。
>
> 注册方式
>
> - XML：`<listener>`
> - 注解（Servlet 3.0+）：`@WebListener`

**`springmvc.xml`**

- **加载者**：SpringMVC 的 **`DispatcherServlet`**（前端控制器）。

- **过程**：

  - `DispatcherServlet` 被容器初始化时，会读取它的 `<init-param>`：

    ```
    <init-param>
        <param-name>contextConfigLocation</param-name>
        <param-value>classpath:springmvc.xml</param-value>
    </init-param>
    ```

  - `DispatcherServlet` 会创建一个 **`WebApplicationContext`**，并把 `springmvc.xml` 里的配置文件加载到这个 Spring 容器中。

  - 这样 Controller、HandlerMapping、ViewResolver 等 Web 层 Bean 就都能工作了。

因此`web.xml`加载的是`Servlet`级别的组件，而`springmvc.xml`加载的是 Spring 容器级别的组件

xml 文件较为繁琐，我们就把`springmvc.xml`平替为注解的形式

```java
@Configuration
@EnableWebMvc
@ComponentScan("com.jh")
public class WebConfig implements WebMvcConfigurer {

    // 视图解析器
    @Bean
    public ViewResolver viewResolver() {
        InternalResourceViewResolver resolver = new InternalResourceViewResolver();
        resolver.setPrefix("/WEB-INF/jsp/");  // JSP 文件前缀
        resolver.setSuffix(".jsp");           // JSP 文件后缀
        return resolver;
    }

    // 静态资源映射
    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/static/**")  // URL 前缀
                .addResourceLocations("/static/"); // 资源目录
    }

//    @Override
//    public void addInterceptors(InterceptorRegistry registry) {
//        registry.addInterceptor(new MyInterceptor())
//                .addPathPatterns("/**");
//    }

}
```

`@EnableWebMvc`是开启注解驱动的 Spring MVC 功能，它把 Spring MVC 所需的 **核心组件注册到 Spring 容器**。比如：

- 配置 **RequestMappingHandlerMapping**：负责 URL 映射

- 配置 **RequestMappingHandlerAdapter**：负责方法调用、参数绑定

- 配置 **ExceptionHandlerExceptionResolver**：处理异常

- 启用 **@ControllerAdvice** 支持

- 开启 **消息转换器**（JSON、XML）

- 开启 **格式化器、验证器**

如果不写该注解，这些组件就需要自己注册

但是要注意：

`@EnableWebMvc` 会 **关闭 Spring Boot 的自动配置**，如果再 Spring Boot 中使用，需要手动配置视图解析器、拦截器等。如果只是想加一些自定义配置而保留默认配置，可以 **继承 WebMvcConfigurer** 并重写方法，而不完全覆盖配置

`WebMvcConfigurer`是 Spring MVC 的配置接口，用于对 mvc 进行定制，它提供的回调方法，可以添加、修改 Spring MVC 的默认配置：

- 拦截器（`Interceptor`）
- 视图解析器（`ViewResolver`）
- 消息转换器（`MessageConverter`）
- 静态资源映射
- 参数解析器
- 异常处理器等

接下来看一下`web.xml`文件

```xml
<?xml version="1.0" encoding="UTF-8"?>
<web-app xmlns="http://xmlns.jcp.org/xml/ns/javaee"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://xmlns.jcp.org/xml/ns/javaee
                             http://xmlns.jcp.org/xml/ns/javaee/web-app_4_0.xsd"
         version="4.0">

    <display-name>Spring MVC Minimal Example</display-name>

    <!-- DispatcherServlet 注册 -->
    <servlet>
        <servlet-name>dispatcher</servlet-name>
        <servlet-class>org.springframework.web.servlet.DispatcherServlet</servlet-class>
        <!-- 使用 AnnotationConfigWebApplicationContext 读取配置类 -->
        <init-param>
            <param-name>contextClass</param-name>
            <param-value>
                org.springframework.web.context.support.AnnotationConfigWebApplicationContext
            </param-value>
        </init-param>
        <init-param>
            <param-name>contextConfigLocation</param-name>
            <param-value>com.jh.config.WebConfig</param-value>
        </init-param>
        <load-on-startup>1</load-on-startup>
    </servlet>

    <!-- 映射所有请求到 DispatcherServlet -->
    <servlet-mapping>
        <servlet-name>dispatcher</servlet-name>
        <url-pattern>/</url-pattern>
    </servlet-mapping>

    <!-- 字符编码过滤器 -->
    <filter>
        <filter-name>encodingFilter</filter-name>
        <filter-class>org.springframework.web.filter.CharacterEncodingFilter</filter-class>
        <init-param>
            <param-name>encoding</param-name>
            <param-value>UTF-8</param-value>
        </init-param>
        <init-param>
            <param-name>forceEncoding</param-name>
            <param-value>true</param-value>
        </init-param>
    </filter>

    <!-- 过滤器映射到所有请求 -->
    <filter-mapping>
        <filter-name>encodingFilter</filter-name>
        <url-pattern>/*</url-pattern>
    </filter-mapping>

</web-app>
```

这个文件配置了 Servlet 级别的组件

做好配置之后，我们主要实现一个`Person`类的查询添加功能。

```java
public class Person {

    private int id;
    private String name;

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    @Override
    public String toString() {
        return "Person [id=" + id + ", name=" + name + "]";
    }
}
```

主要使用 Spring 提供的 JdbcTemplate 类，接下来配置这个类

```java
@Configuration
public class DataSourceConfig {

    @Bean
    public DataSource dataSource() {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl("jdbc:mysql://localhost:3306/db");
        dataSource.setUsername("root");
        dataSource.setPassword("root");
        return dataSource;
    }

    @Bean
    public JdbcTemplate jdbcTemplate() {
        return new JdbcTemplate(dataSource());
    }
}
```

JdbcTemplate 它只需要传入一个数据源，就完成了配置，可以操作数据库了。

创建一个 dao 类，实现操作数据库的功能

```java
@Repository
public class PersonDao {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    public Person getPersonById(int id) {
        String sql = "select * from person where id = ?";
        Person p = jdbcTemplate.queryForObject(sql, (rs, rowNum) -> {
            Person person = new Person();
            person.setId(rs.getInt("id"));
            person.setName(rs.getString("name"));
            return person;
        }, id);
        return p;
    }

    public void insertPerson(Person person) {
        String sql = "insert into person(name) values(?)";
        jdbcTemplate.update(sql, person.getName());
    }

}
```

查询方法`T queryForObject(String sql, RowMapping<T> rm, T param)`，第一个参数传入一个 sql 语句，后面一个参数是一个函数式接口，用于将查询结果映射到 Java 类中，rs 是查询结果，rowNum 是查询的行数。param 是 ? 的值。

插入方法`update(String sql, T value)`

> JDBC 的核心组成：
>
> Driver（数据库驱动）
>
> - 提供 JDBC 接口的实现，负责把 JDBC 请求转换成数据库协议。
> - 常见驱动类型：
>   - MySQL：`com.mysql.cj.jdbc.Driver`
>   - Oracle：`oracle.jdbc.OracleDriver`
>
> Connection（连接）
>
> - 表示与数据库的一个连接会话。
> - 通过 `DriverManager.getConnection(url, user, password)` 获取。
>
> Statement / PreparedStatement
>
> - **Statement**：普通 SQL 执行对象，直接拼接 SQL 字符串。
> - **PreparedStatement**：预编译 SQL，支持占位符 `?`，提高安全性和性能（防止 SQL 注入）。
>
> ResultSet
>
> - 查询返回结果集，用来遍历数据库表中记录。
>
> SQLException
>
> - JDBC 操作的异常类，包含错误码、SQL 状态等信息。
>
> ```java
> // 加载驱动
> Class.forName("com.mysql.jc.jbbc.Driver");
> // 获取连接
> Connection conn = DriverManager.getConnection(
>     "jdbc:mysql://localhost:3306/testdb?useSSL=false&serverTimezone=UTC",
>     "root",
>     "root"
> );
> // 创建 Statement / PreparedStatement
> String sql = "SELECT id, name FROM person WHERE id = ?";
> PreparedStatement ps = conn.prepareStatement(sql);
> ps.setInt(1, 1); // 设置占位符
> // 执行 SQL
> ResultSet rs = ps.executeQuery(); // 查询
> // 或者 ps.executeUpdate(); // 插入/更新/删除
> // 处理结果集
> while(rs.next()) {
>     int id = rs.getInt("id");
>     String name = rs.getString("name");
>     System.out.println(id + " -> " + name);
> }
> // 释放资源
> rs.close();
> ps.close();
> conn.close();
> ```
>
> PreparedStatement 的 sql 是预编译过的，防止 sql 注入，提高性能

实现业务逻辑

```java
@Service
public class PersonService {

    @Autowired
    private PersonDao personDao;

    public Person getPersonById(int id) {
        return personDao.getPersonById(id);
    }

    public void insertPerson(Person person) {
        personDao.insertPerson(person);
    }
}
```

我们发现所有的组件都是由`WebConfig`配置类注册的，并没有分层，比如数据库相关的组件再`DataSourceConfig`注册，`WebConfig`注册实现 Controller 等部分。其实这样是可以的，但需要更改一些配置。

在整个 web 项目中可以创建一个 Root ApplicationContext，用来管理整个应用的 Bean 资源。是父容器，然后再由每个`DispatcherServlet`创建一个独立的子容器用于管理 **Controller、HandlerMapping、HandlerAdapter、ViewResolver** 等 **Web 层相关 Bean**。这样，子容器可以访问父容器的 Bean，但父容器不能访问子容器的 Bean。就实现了 **Web 层与业务层解耦**，避免 Controller 里创建 Service 对象，统一交给 IoC 容器管理。

> 一个大型 web 项目可以有多个 DispatcherServlet

这样需要改动`web.xml`

```xml
<web-app>

    <!-- 父容器：Spring 容器 -->
    <listener>
        <listener-class>org.springframework.web.context.ContextLoaderListener</listener-class>
    </listener>
    <context-param>
        <param-name>contextConfigLocation</param-name>
        <param-value>/WEB-INF/applicationContext.xml</param-value>
    </context-param>

    <!-- 子容器：SpringMVC 容器 -->
    <servlet>
        <servlet-name>springmvc</servlet-name>
        <servlet-class>org.springframework.web.servlet.DispatcherServlet</servlet-class>
        <init-param>
            <param-name>contextConfigLocation</param-name>
            <param-value>/WEB-INF/spring-mvc.xml</param-value>
        </init-param>
        <load-on-startup>1</load-on-startup>
    </servlet>

    <servlet-mapping>
        <servlet-name>springmvc</servlet-name>
        <url-pattern>/</url-pattern>
    </servlet-mapping>

</web-app>
```

**Spring 容器（Root ApplicationContext）**

- 由 **`ContextLoaderListener`** 创建和管理
- 通常在 `web.xml` 中通过 `<listener>` 配置
- 加载的是整个应用的**公共 Bean**（比如 Service、DAO、Repository、DataSource、事务管理等）
- 在整个 Web 应用中 **只有一个**，是父容器

**SpringMVC 容器（DispatcherServlet ApplicationContext）**

- 由 **`DispatcherServlet`** 创建
- 每一个 `DispatcherServlet` 对应一个独立的子容器（理论上可以有多个）
- 主要管理 **Controller、HandlerMapping、HandlerAdapter、ViewResolver** 等 **Web 层相关 Bean**
- 不负责 Service 和 DAO
- 默认只会扫描 **Controller 层**

spring boot 将这种细节屏蔽了。

Controller 层：

```java
@Controller
public class PersonController {

    @Autowired
    private PersonService personService;

    @GetMapping("/get/{id}")
    public ModelAndView get(@PathVariable int id) {
        ModelAndView modelAndView = new ModelAndView();
        Person person = personService.getPersonById(id);
        modelAndView.addObject("name", person.getName());
        modelAndView.setViewName("query");
        return modelAndView;
    }

    @PostMapping("/save")
    public String save(Person person) {
        System.out.println(person.getName());
        personService.insertPerson(person);
        return "redirect:/";
    }
}
```

这里我们的视图解析器是 jsp

```java
@PostMapping("/save")
public String save(Person person) {
}
```

该方法如果返回 void 的话。当返回 `void` 时，Spring MVC 默认会尝试根据**请求路径推断视图名

```java
@GetMapping("/get/{id}")
public ModelAndView get(@PathVariable int id) {
}
@PostMapping("/save")
public String save(Person person) {
}
```

可以看到上面的方法的参数实现了自动注入。其实背后是 **SpringMVC 的参数解析机制**，靠一堆 **HandlerMethodArgumentResolver** 来完成的。

请求到达 Controller 的流程

1. 请求到来 -> `DispatcherServlet`
2. 找到对应的 `HandlerMapping` -> 定位到某个 `Controller` 方法
3. `HandlerAdapter` 调用这个方法时，会先去解析方法参数
4. **SpringMVC 内部有一组 ArgumentResolver（参数解析器）**，专门负责不同类型参数的解析和赋值

常见的参数绑定方式

**`@PathVariable`**

```
@GetMapping("/get/{id}")
public ModelAndView get(@PathVariable int id) { ... }
```

- URL: `/get/10`
- 解析器：`PathVariableMethodArgumentResolver`
- 工作方式：
  - 匹配 URL 模板 `{id}`
  - 把 `10` 转成 `int`
  - 注入到 `id` 参数

**表单参数 / Query 参数（POJO 封装）**

```
@PostMapping("/save")
public String save(Person person) { ... }
```

- 假设表单：`name=Tom&age=20`
- 解析器：`ModelAttributeMethodProcessor`
- 工作方式：
  - Spring 会先创建一个 `Person` 实例
  - 按照 **参数名 -> 属性名** 规则匹配
  - 调用 `setName("Tom")`, `setAge(20)`
  - 完成对象的自动封装

要求：

- `Person` 必须有 **无参构造器**
- 属性要有对应的 **setter/getter**

参数在 **请求体** 中（但用 `@RequestParam` 依然能接到）

要注意参数名和属性名要一致

**`@RequestParam`**

```
@PostMapping("/save")
public String save(@RequestParam("name") String name) { ... }
```

- URL: `/save?name=Tom`
- 解析器：`RequestParamMethodArgumentResolver`
- 自动从请求参数中取 `name=Tom` -> 注入到 `name`

参数在 **请求体** 中（但用 `@RequestParam` 依然能接到）

**`@RequestBody`（JSON 请求体）**

```
@PostMapping("/save")
public String save(@RequestBody Person person) { ... }
```

- Content-Type: `application/json`
- 解析器：`RequestResponseBodyMethodProcessor`
- 依赖 `HttpMessageConverter`（例如 Jackson）把 JSON 转换成对象
- 请求体：`{"name":"Tom","age":20}` -> 反序列化成 `Person`

**Servlet API 注入**

```
@GetMapping("/get")
public String get(HttpServletRequest request, HttpServletResponse response) { ... }
```

- 解析器：`ServletRequestMethodArgumentResolver`
- SpringMVC 会把当前的 request/response 直接传给方法参数

jsp 其实也是一个 Servlet，它会由容器解析成一个 Servlet，所以，使用 Model 设置的参数最终会被映射到 request 域中，jsp 从 request 中拿到要解析的值

```java
@GetMapping("/hello")
public String hello(Model model) {
    model.addAttribute("msg", "你好，SpringMVC");
    return "hello";  // 视图名
}
```

`model.addAttribute("msg", "你好，SpringMVC")`

- SpringMVC 会把数据存到 **request 域**（`HttpServletRequest`）中，类似：

  ```
  request.setAttribute("msg", "你好，SpringMVC");
  ```

返回 `"hello"`字符串会被认为是一个视图名

- 视图解析器会拼接路径，比如 `/WEB-INF/views/hello.jsp`
- 然后使用 `RequestDispatcher.forward(request, response)` 转发到 JSP。

web\WEB-INF\ 目录下的资源被容器保护，不能直接由浏览器访问。而 web\ 下的资源可以直接被浏览器访问，我们在该目录下创建一个 index.jsp 首页

```java
<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<html>
<head>
    <title>index</title>
</head>
<body>
<form id="query" method="get">
  <label>
    input id：
    <input type="text" id="person_id">
  </label>
  <input type="button" id="queryBtn" value="查询">
</form>

<form id="add" action="save" method="post">
  <label>
    input name：
    <input type="text" name="name">
  </label>
  <input type="submit" value="添加">
</form>

<script>
  document.getElementById('queryBtn').addEventListener('click', function() {
    let form = document.getElementById('query');
    let input = document.getElementById('person_id');
    form.action = 'http://localhost:8080/spring_mvc_Web_exploded/get/' + input.value;
    form.submit();
  });
</script>
</body>
</html>
```

然后在 web\WEB-INF\ 目录下创建一个 jsp\query.jsp

```java
<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<html>
<head>
    <title>query</title>
</head>
<body>
<%=request.getAttribute("name")%>
</body>
</html>
```

jsp 不重要，不说了

现在，如果给方法标注`@ResponseBody`或者方法直接返回`ResponseEntity<T>`，那么数据将不会由视图解析器处理，完成一个完整的 mvc 操作，而是会由`HttpMessageConverter`类将其写入 HTTP 响应体，直接返回服务器，这就是现代 **Web API 风格**（RESTful 服务）

```java
@RestController 
public class PersonController {

    @Autowired
    private PersonService personService;

    @GetMapping("/get/{id}")
    public Person get(@PathVariable int id) {
    }

    @PostMapping("/save")
    public String save(Person person) {
    }
}
```

在 Spring MVC 里有两条主要的响应路径：

1. **传统 MVC 流程**

- 方法返回 `String`（逻辑视图名）、`ModelAndView`
- `DispatcherServlet -> HandlerAdapter -> Controller -> 视图解析器(ViewResolver) -> 渲染 JSP/Thymeleaf`
- 最后输出 HTML 给浏览器

适合页面渲染型应用。

2. **现代 Web API 流程**

- 方法标注 `@ResponseBody` **或** 返回 `ResponseEntity<T>`
- `DispatcherServlet -> HandlerAdapter -> Controller -> HttpMessageConverter`
- 将 Java 对象转换为 JSON/XML/二进制，直接写入 **HTTP 响应体**
- 不再走视图解析器

适合 RESTful API 服务。

两者区别可简化为：

- **视图解析器 (ViewResolver)**：把返回值解析为 *页面视图*（JSP/HTML）。
- **消息转换器 (HttpMessageConverter)**：把返回值序列化为 *数据格式*（JSON/XML）。

web.xml 的注解实现方式

```java
public class MyWebAppInitializer extends AbstractAnnotationConfigDispatcherServletInitializer {

    // Root 容器：Service, Repository, 事务等（相当于 applicationContext.xml）
    @Override
    protected Class<?>[] getRootConfigClasses() {
        return new Class<?>[]{RootConfig.class};
    }

    // Web 容器：Controller, ViewResolver, HandlerMapping 等（相当于 springmvc.xml）
    @Override
    protected Class<?>[] getServletConfigClasses() {
        return new Class<?>[]{WebConfig.class};
    }

    // DispatcherServlet 映射路径（相当于 <url-pattern>）
    @Override
    protected String[] getServletMappings() {
        return new String[]{"/"};
    }

    // 注册 Filter
    @Override
    protected Filter[] getServletFilters() {
        return new Filter[]{new CharacterEncodingFilter("UTF-8", true)};
    }
}
```

如果不想用 Spring 提供的抽象类，可以直接自己实现

```java
public class MyWebAppInitializer implements WebApplicationInitializer {

    @Override
    public void onStartup(ServletContext servletContext) throws ServletException {
        // 创建 Spring 容器
        AnnotationConfigWebApplicationContext context = new AnnotationConfigWebApplicationContext();
        context.register(WebConfig.class);

        // 注册 DispatcherServlet
        ServletRegistration.Dynamic dispatcher =
                servletContext.addServlet("dispatcher", new DispatcherServlet(context));
        dispatcher.setLoadOnStartup(1);
        dispatcher.addMapping("/");

        // 注册 Filter
        FilterRegistration.Dynamic encodingFilter =
                servletContext.addFilter("encodingFilter", new CharacterEncodingFilter("UTF-8", true));
        encodingFilter.addMappingForUrlPatterns(null, false, "/*");
    }
}
```

**在打 war 包时，一定要将项目中所用到的 jar 打包到 WEB-INF/lib 下，否则在部署到 Tomcat 时将找不到 DispatcherServlet 等的类**

**web 服务的默认路径中有自己的组件名**

最后附上 pom 依赖

```java
<dependencies>
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-webmvc</artifactId>
        <version>5.3.31</version>
    </dependency>
    <dependency>
        <groupId>javax.servlet</groupId>
        <artifactId>javax.servlet-api</artifactId>
        <version>4.0.1</version>
    </dependency>
    <dependency>
        <groupId>javax.servlet</groupId>
        <artifactId>jstl</artifactId>
        <version>1.2</version>
    </dependency>
    <dependency>
        <groupId>taglibs</groupId>
        <artifactId>standard</artifactId>
        <version>1.1.2</version>
    </dependency>
    <dependency>
        <groupId>com.mysql</groupId>
        <artifactId>mysql-connector-j</artifactId>
        <version>8.2.0</version>
    </dependency>
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-jdbc</artifactId>
        <version>5.3.31</version>
    </dependency>
</dependencies>
```
