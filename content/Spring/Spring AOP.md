+++
date = '2025-09-17T20:41:57+08:00'
draft = false
title = 'Spring AOP'
+++

Spring 框架通过定义切面，通过拦截切点实现了不同业务模块的解耦，这个就叫**AOP 面向切面编程**

AOP 是一种设计思想，本质上是为了解耦

AOP 理念：将分散在各个业务逻辑代码中相同的代码通过**横向切割**的方式抽取到一个独立的模块中。它所面对的是处理过程的某个步骤或阶段，以获得逻辑过程的中各部分之间低耦合的隔离效果。

比如要实现一个日志功能，我们如果在每一个需要调用日志的地方加入日志代码，这样会很耦合和冗余。如果我们把日志单独抽取出来，在调用需要日志的方法的时候拦截该方法，调用日志模块。这样就实现了解耦。

#### AOP 术语

**连接点（Jointpoint）**：表示需要在程序中插入横切关注点的扩展点，**连接点可能是类初始化、方法执行、方法调用、字段调用或处理异常等等**，Spring只支持方法执行连接点，在AOP中表示为**在哪里干**；

**切入点（Pointcut）**： 选择一组相关连接点的模式，即可以认为连接点的集合，Spring支持perl5正则表达式和AspectJ切入点模式，Spring默认使用AspectJ语法，在AOP中表示为**在哪里干的集合**；

**通知（Advice）**：在连接点上执行的行为，通知提供了在AOP中需要在切入点所选择的连接点处进行扩展现有行为的手段；包括前置通知（before advice）、后置通知(after advice)、环绕通知（around advice），在Spring中通过代理模式实现AOP，并通过拦截器模式以环绕连接点的拦截器链织入通知；在AOP中表示为**干什么**；

**方面/切面（Aspect）**：横切关注点的模块化，比如上边提到的日志组件。可以认为是通知、引入和切入点的组合；在Spring中可以使用Schema和@AspectJ方式进行组织实现；在AOP中表示为**在哪干和干什么集合**；

**引入（inter-type declaration）**：也称为内部类型声明，为已有的类添加额外新的字段或方法，Spring允许引入新的接口（必须对应一个实现）到所有被代理对象（目标对象）, 在AOP中表示为**干什么（引入什么）**；

**目标对象（Target Object）**：需要被织入横切关注点的对象，即该对象是切入点选择的对象，需要被通知的对象，从而也可称为被通知对象；由于Spring AOP 通过代理模式实现，从而这个对象永远是被代理对象，在AOP中表示为**对谁干**；

**织入（Weaving）**：把切面连接到其它的应用程序类型或者对象上，并创建一个被通知的对象。这些可以在编译时（例如使用AspectJ编译器），类加载时和运行时完成。Spring和其他纯Java AOP框架一样，在运行时完成织入。在AOP中表示为**怎么实现的**；

**AOP代理（AOP Proxy）**：AOP框架使用代理模式创建的对象，从而实现在连接点处插入通知（即应用切面），就是通过代理来对目标对象应用切面。在Spring中，AOP代理可以用JDK动态代理或CGLIB代理实现，而通过拦截器模型应用切面。在AOP中表示为**怎么实现的一种典型方式**；

##### 通知类型

**前置通知（Before advice）**：在某连接点之前执行的通知，但这个通知不能阻止连接点之前的执行流程（除非它抛出一个异常）。

**后置通知（After returning advice）**：在某连接点正常完成后执行的通知：例如，一个方法没有抛出任何异常，正常返回。

**异常通知（After throwing advice）**：在方法抛出异常退出时执行的通知。

**最终通知（After (finally) advice）**：当某连接点退出的时候执行的通知（不论是正常返回还是异常退出）。

**环绕通知（Around Advice）**：包围一个连接点的通知，如方法调用。这是最强大的一种通知类型。环绕通知可以在方法调用前后完成自定义的行为。它也会选择是否继续执行连接点或直接返回它自己的返回值或抛出异常来结束执行。

**Spring AOP** 如何将需要的逻辑代码织入对应的方法呢。

它使用的是动态织入的方式。在程序运行时将要增强的代码织入到目标类中。它是通过动态代理的方式实现的，如 JDK 通过反射实现的动态代理、底层通过继承实现的CGLIB的动态代理

> **Spring 在实现 AOP 时的默认策略**：
>
> - 如果目标对象实现接口 -> 使用 JDK 动态代理
> - 如果目标对象没有接口 -> 使用 CGLIB 代理
> - 可通过 `@EnableAspectJAutoProxy(proxyTargetClass = true)` 强制使用 CGLIB

而另一种则是静态织入的方式，ApectJ 采用的就是这种。在编译其间，使用AspectJ的acj编译器(类似javac)把aspect类编译成class字节码后，在java目标类编译时织入，即先编译aspect类再编译目标类。

### 配置 AOP

在这里，我们只介绍使用注解的方式配置 AOP

**开启注解 AOP**

```java
@Configuration
@EnableAspectJAutoProxy  // 开启 AOP 注解支持
public class AppConfig {}
```

在配置类中使用 **@EnableAspectJAutoProxy** 启用 Spring AOP 注解支持

可选属性：

- `proxyTargetClass = true`：强制使用 CGLIB 代理（即使目标对象实现了接口）

**定义切面类**

```java
@Aspect               // 标记这是一个切面类
@Component            // 将切面注册到 Spring 容器
public class LogAspect {
    ...
}
```

**定义通知（Advice）**

Spring 提供的通知类型

| 注解              | 作用                                                     |
| ----------------- | -------------------------------------------------------- |
| `@Before`         | 前置通知，方法调用前执行                                 |
| `@After`          | 后置通知，方法调用后执行（无论异常与否）                 |
| `@AfterReturning` | 返回通知，方法正常返回后执行                             |
| `@AfterThrowing`  | 异常通知，方法抛出异常后执行                             |
| `@Around`         | 环绕通知，可在方法前后执行逻辑，甚至决定是否执行目标方法 |

**切点表达式（Pointcut）**

**格式**：`execution(modifiers-pattern? ret-type-pattern declaring-type-pattern? name-pattern(param-pattern) throws-pattern?)`

```java
@Before("execution(* com.example.service.UserService.*(..))")
```

定义可重用切点

```java
@Pointcut("execution(* com.example.service.*.*(..))")
public void serviceMethods() {}

@Before("serviceMethods()")
public void beforeService() {
    System.out.println("方法执行前日志");
}
```

> 切面类必须是 **Spring 管理的 Bean**（`@Component` 或通过 `@Bean` 注册）
>
> 目标对象也必须是 **Spring 管理的 Bean**
>
> 注入 AOP 后：
>
> - 对目标对象的调用会被代理
> - 执行切面逻辑
>
> 多种增强通知的顺序：
>
> 当有**多个切面**同时作用于同一个方法时，Spring 会按照**切面的优先级**执行
>
> 我们可以通过`@Order`注解设置优先级（值越小，优先级越高）
>
> ```java
> @Aspect
> @Component
> @Order(1) // 优先级高
> public class LogAspect {}
> 
> @Aspect
> @Component
> @Order(2) // 优先级低
> public class TransactionAspect {}
> 
> ```

接下来我们使用 AOP 和 Redis 来实现一个缓存：

我们要实现的是，当调用`get()`方法查询数据库时，如果有缓存则立即返回缓存，不执行查询方法。

首先创建一个 maven 项目，配置 pom 依赖

```pom
<dependencies>
    <!-- Spring 核心容器 -->
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-context</artifactId>
        <version>5.3.39</version>
    </dependency>

    <!-- Spring AOP -->
    <dependency>
        <groupId>org.springframework</groupId>
        <artifactId>spring-aop</artifactId>
        <version>5.3.39</version>
    </dependency>

    <!-- AspectJ 支持 -->
    <dependency>
        <groupId>org.aspectj</groupId>
        <artifactId>aspectjweaver</artifactId>
        <version>1.9.22.1</version>
    </dependency>
    
    <!-- Spring Data Redis -->
    <dependency>
        <groupId>org.springframework.data</groupId>
        <artifactId>spring-data-redis</artifactId>
        <version>2.7.18</version>
    </dependency>

    <!-- Lettuce 驱动 -->
    <dependency>
        <groupId>io.lettuce</groupId>
        <artifactId>lettuce-core</artifactId>
        <version>6.5.0.RELEASE</version>
    </dependency>

    <!-- Jackson：序列化对象 -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
        <version>2.18.1</version>
    </dependency>
</dependencies>
```

这里只使用 Spring 的基础架构实现。

引入`spring-context`，`spring-aop`，`aspectjweaver`核心类库。

使用`spring-data-redis`客户端操作 redis。

`spring-aop`依赖`aspectjweaver`。

Spring AOP 使用 AspectJ 的 `aspectjweaver` 来解析注解（`@Aspect`、`@Around`、`@Before` 等）并生成代理类

而`spring-data-redis`依赖`lettuce-core`

**Spring Data Redis** 是一个 Redis 客户端抽象层，提供：

- RedisTemplate
- RedisConnection
- 高级操作（List、Set、Hash）

它本身不直接实现网络通信，需要底层客户端：

1. **Lettuce**（默认异步、线程安全、Netty 实现）
2. **Jedis**（同步阻塞客户端）

`spring-data-redis` 默认选择 **Lettuce** 作为依赖：

- 异步、线程安全
- 支持 Reactive Redis（响应式编程）
- 不用开发者手动管理连接池

然后，我们通过注解作为 aop 的切点。定义以下切点

```java
// 查询时添加缓存
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface AddCache {

    String keySpel() default "";

    public long ttl() default 300;
}
// 更新缓存
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface DeleteCache {

    public String keySpel() default "";
}
// 删除缓存
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface UpdateCache {

    public String keySpel() default "";

    public long ttl() default 300;
}
```

> 注解：
>
> 注解的作用
>
> 1. **编译时检查**
>    - 比如 `@Override` 检查方法是否正确重写
> 2. **代码生成 / 提示**
>    - 比如 `@Getter`, `@Setter`（Lombok）自动生成方法
> 3. **运行时处理**
>    - 框架利用反射读取注解来执行逻辑
>    - 例子：
>      - Spring 的 `@Autowired`, `@Service`
>      - JPA 的 `@Entity`, `@Column`
>      - AOP 的 `@Aspect`, `@Around`
>
> 注解的分类
>
> 按保留策略分：
>
> | 策略    | 保留阶段 | 作用                                                      |
> | ------- | -------- | --------------------------------------------------------- |
> | SOURCE  | 源码     | 编译后丢弃，IDE 可用，比如 `@Override`                    |
> | CLASS   | 编译期   | 编译成 `.class` 文件，但 JVM 不保留，常用作字节码工具分析 |
> | RUNTIME | 运行时   | JVM 可通过反射读取，框架使用最多（Spring、JPA、Jackson）  |
>
> 我们最常用的就是 RUNTIME
>
> ```java
> @Retention(RetentionPolicy.RUNTIME)
> public @interface MyAnnotation {}
> ```
>
> 按目标分：
>
> | 目标            | 描述           |
> | --------------- | -------------- |
> | TYPE            | 类、接口、枚举 |
> | METHOD          | 方法           |
> | FIELD           | 字段           |
> | PARAMETER       | 方法参数       |
> | CONSTRUCTOR     | 构造方法       |
> | PACKAGE         | 包             |
> | LOCAL_VARIABLE  | 局部变量       |
> | ANNOTATION_TYPE | 注解本身       |
>
> ```java
> @Target({ElementType.METHOD, ElementType.FIELD})
> public @interface MyAnnotation {}
> ```
>
> 注解中可以定义元素，本质上是注解接口的方法。元素默认是`public bastract`
>
> 注解编译之后等效于
>
> ```java
> public interface MyAnnotation extends java.lang.annotation.Annotation {
>     public abstract String value();
>     public abstract int count();
> }
> ```
>
> 定义一个注解需要写明保留策略和目标

定义好切点后，写一个 redis 工具类，用来操作 redis

在这之前现配置 spring data redis

```java
@Configuration
public class RedisConfig {

    @Bean
    public RedisConnectionFactory redisConnectionFactory() {
        return new LettuceConnectionFactory("192.168.254.128", 6379);
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> redisTemplate = new RedisTemplate<>();
        redisTemplate.setConnectionFactory(connectionFactory);
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(new GenericJackson2JsonRedisSerializer());
        return redisTemplate;
    }
}
```

配置一个 spring data redis 需要配置它的 redis 连接和 `RedisTemplate`

```java
@Bean
public RedisConnectionFactory redisConnectionFactory() {
    
    return new LettuceConnectionFactory("192.168.254.128", 6379);
}
```

上面说过了 spring data redis 是一个 Redis 客户端抽象层，本身并不提供网络通信，需要底层客户端实现，这里使用一个`LettuceConnectionFactory`

然后配置`RedisTemplate`

```java
    RedisTemplate<String, Object> redisTemplate = new RedisTemplate<>();
    redisTemplate.setConnectionFactory(connectionFactory);
    redisTemplate.setKeySerializer(new StringRedisSerializer());
    redisTemplate.setValueSerializer(new GenericJackson2JsonRedisSerializer());
```

这里直接设置客户端连接`RedisConnectionFactory`，给 redis 的 key 和 value 设置序列化方式。

> redis 的 key 和 value 的默认 JDK 序列化，它会把值序列化成二进制数据存储在 redis 中，这样不方便读取。因此需要自己设置序列化的方式

redis 工具类

```java
@Component
public class RedisUtil {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    public void set(String key, Object value) {
        redisTemplate.opsForValue().setIfAbsent(key, value);
    }

    public void set(String key, Object value, long ttl) {
        redisTemplate.opsForValue().setIfAbsent(key, value, ttl, TimeUnit.SECONDS);
    }

    public void update(String key, Object value, long ttl) {
        redisTemplate.opsForValue().set(key, value, ttl, TimeUnit.SECONDS);
    }

    public Object get(String key) {
        return redisTemplate.opsForValue().get(key);
    }

    public void del(String key) {
        redisTemplate.delete(key);
    }
}
```

使用`redisTemplate.opsForValue().set(key, value, ttl, TimeUnit.SECONDS)`设置值，新值会覆盖旧值。在更新缓存时适合，但是在设置值的时候不太合适，因此可以使用`redisTemplate.opsForValue().setIfAbsent(key, value)`。

接下来实现 aop 

```java
@org.aspectj.lang.annotation.Aspect
@Component
public class Aspect {

    @Autowired
    private RedisUtil redisUtil;

    private final ExpressionParser parser = new SpelExpressionParser();

    private String parseKey(String keySpel, MethodSignature methodSignature, JoinPoint joinPoint) {
        String[] paramNames = methodSignature.getParameterNames();
        StandardEvaluationContext context = new StandardEvaluationContext();
//        Object[] args = methodSignature.getMethod().getParameters();
        Object[] args = joinPoint.getArgs();
        for (int i = 0; i < paramNames.length; i++) {
            context.setVariable(paramNames[i], args[i]);
        }
        return parser.parseExpression(keySpel).getValue(context, String.class);
    }

    @Pointcut("@annotation(com.jh.annotation.AddCache)")
    public void addCache() {

    }

    @Pointcut("@annotation(com.jh.annotation.DeleteCache)")
    public void deleteCache() {

    }

    @Pointcut("@annotation(com.jh.annotation.UpdateCache)")
    public void updateCache() {

    }

    @Around("addCache()")
    public Object addCache(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        AddCache annotation = signature.getMethod().getAnnotation(AddCache.class);
        if (annotation == null) {
            return joinPoint.proceed();
        }
        String key = parseKey(annotation.keySpel(), signature, joinPoint);
        Object result = redisUtil.get(key);
        if (result != null) {
            return result;
        }
        result = joinPoint.proceed();
        redisUtil.set(key, result, annotation.ttl());
        return result;
    }

    @AfterReturning(pointcut = "updateCache()", returning = "result")
    public void updateCache(JoinPoint joinPoint, Object result) {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        UpdateCache annotation = signature.getMethod().getAnnotation(UpdateCache.class);
        if (annotation != null) {
            String key = parseKey(annotation.keySpel(), signature, joinPoint);
            redisUtil.update(key, result, annotation.ttl());
        }
    }
    
    // AfterReturning 是方法返回之后执行增强逻辑，注解中定义该元素 returning = "result"
    // 增强方法参数列表中的 result 就会被自动注入返回值.

    @AfterReturning("deleteCache()")
    public void deleteCache(JoinPoint joinPoint) {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        DeleteCache annotation = signature.getMethod().getAnnotation(DeleteCache.class);
        if (annotation != null) {
            redisUtil.del(parseKey(annotation.keySpel(), signature, joinPoint));
        }
    }
}
```

为了更灵活的设置 key 值，使用了 spring el 表达式

```java
private final ExpressionParser parser = new SpelExpressionParser();

private String parseKey(String keySpel, MethodSignature methodSignature, JoinPoint joinPoint) {
    String[] paramNames = methodSignature.getParameterNames();
    StandardEvaluationContext context = new StandardEvaluationContext();
//        Object[] args = methodSignature.getMethod().getParameters(); 通过反射获得的都是参数类型，而不是具体的值
    Object[] args = joinPoint.getArgs();
    for (int i = 0; i < paramNames.length; i++) {
        context.setVariable(paramNames[i], args[i]);
    }
    return parser.parseExpression(keySpel).getValue(context, String.class);
}
```

**什么是 SpEL**

**Spring Expression Language** 是 Spring 提供的表达式语言，用于在运行时解析字符串表达式。

功能：

1. 访问对象属性、方法
2. 调用静态方法和常量
3. 集合操作（List、Map、数组）
4. 条件判断和逻辑运算
5. 支持模板表达式（字符串拼接）

这里只讲解模板表达式。

SpEl 可以使用`#value`引用变量

模板表达式使用`#{}` 或 `'...' + ...` 拼接参数

```java
'user:' + #id       // 拼接字符串
'user:#{#id}'       // 模板方式
```

通过 SpEl 

```java
@AddCache(keySpel = "'user:' + #id")
public User getUser(int id) { ... }
```

就可以灵活的获得一个 key 值 `user:id`

有了表达式我们需要正确解析才能获取想要的值，否则上面的`#id`程序根本不知道是什么

选择一个解析器`ExpressionParser parser = new SpelExpressionParser()`
设置正确的上下文环境`StandardEvaluationContext context = new StandardEvaluationContext()`，解析器就是根据这里面的值才能正确匹配`#id`的值

然后就可以解析获取想要的值了`parser.parseExpression(keySpel).getValue(context, String.class)`

**接下来讲一下`addCache`的逻辑：**

定义一个独立的切点

```java
@Pointcut("@annotation(com.jh.annotation.AddCache)")
public void addCache() {
}
```

`@Pointcut("@annotation(com.jh.annotation.AddCache)")`的意思是把标注有`AddCache`注解的方法视为切点。

```java
@Around("addCache()")
public Object addCache(ProceedingJoinPoint joinPoint) throws Throwable {
    MethodSignature signature = (MethodSignature) joinPoint.getSignature(); // 获取方法签名
    AddCache annotation = signature.getMethod().getAnnotation(AddCache.class);// 获取方法上的注解
    if (annotation == null) {
        return joinPoint.proceed(); // 放方法执行进行
    }
    String key = parseKey(annotation.keySpel(), signature, joinPoint);
    Object result = redisUtil.get(key);
    if (result != null) {
        return result;
    }
    result = joinPoint.proceed();
    redisUtil.set(key, result, annotation.ttl());
    return result;
}
```

该切点要具体增强的方法逻辑：

这是一个环绕通知，在方法执行前`joinPoint.proceed()`，判断 redis 中是否有值，如果有直接返回缓存，如果没有，执行`joinPoint.proceed()`，得到返回值存入 redis 中。

在 **Spring AOP** 中，`JoinPoint` 和 `ProceedingJoinPoint` 是两个非常核心的接口，它们的区别和使用场景值得搞清楚。

**JoinPoint**

- **概念**：表示一个被切面的 **连接点**（方法调用、构造器调用等）。
- **作用**：提供方法签名、参数、目标对象等信息，但 **不能控制方法执行**。

| 方法             | 说明                            |
| ---------------- | ------------------------------- |
| `getArgs()`      | 获取方法参数数组                |
| `getTarget()`    | 获取目标对象（被代理对象）      |
| `getThis()`      | 获取当前代理对象                |
| `getSignature()` | 获取方法签名（MethodSignature） |

方法签名中就可以获取 `Method` 等信息

> `JoinPoint` 只提供 **观察信息**，无法改变方法执行或获取返回值

**ProceedingJoinPoint**

- **概念**：`ProceedingJoinPoint` 是 `JoinPoint` 的子接口，用于 **环绕通知（@Around）**。
- **作用**：
  1. 可以获取方法信息（继承自 JoinPoint）
  2. 可以控制方法执行（通过 `proceed()` 方法）
  3. 可以修改返回值或者捕获异常

| 方法                     | 说明                         |
| ------------------------ | ---------------------------- |
| `proceed()`              | 执行目标方法，返回方法返回值 |
| `proceed(Object[] args)` | 执行方法并替换参数           |

最后可以验证一下

模拟数据库

```java
@Service
public class UserService {

    private List<String> db = new ArrayList<>();

    {
        db.add("雪之下雪乃");
    }

    @AddCache(keySpel = "'user:' + #id")
    public String getUser(int id) {
        System.out.println("调用 getUser()");
        return db.get(id);
    }
}
```

然后运行

```java
@Configuration
@ComponentScan(basePackages = "com.jh") // 纯 Spring 项目必须写
@EnableAspectJAutoProxy // 启动 AOP
public class App {

    public static void main(String[] args) {
        ApplicationContext context = new AnnotationConfigApplicationContext(App.class);
        UserService userService = context.getBean(UserService.class);
        System.out.println("第一次调用" + userService.getUser(0));
        System.out.println("第二次调用" + userService.getUser(0));
    }
}
```
