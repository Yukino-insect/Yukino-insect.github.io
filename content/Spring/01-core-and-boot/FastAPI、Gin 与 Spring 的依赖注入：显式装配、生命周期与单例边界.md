+++
date = '2026-09-29T20:00:00+08:00'
draft = false
title = 'FastAPI、Gin 与 Spring 的依赖注入：显式装配、生命周期与单例边界'
+++

从 Spring 转去写 FastAPI 或 Gin 时，很多人都会有一个相当自然的疑问：为什么 `Service`、数据库连接池之类的对象，似乎要自己创建，再作为参数传给路由或处理器？Spring 里只要把类标成 `@Service`，再在构造器中声明依赖，容器就会替我们完成这一切；难道 Python 和 Go 的 Web 框架没有依赖注入吗？

结论先说：**它们并不是“没有依赖注入”，而是把依赖图的声明和对象装配放在了不同位置。**Spring 倾向于用 IoC 容器集中登记、按类型解析并管理对象生命周期；FastAPI 提供以 `Depends` 为核心、面向请求的依赖解析；Gin 则没有内建的通用 DI 容器，通常由应用启动代码显式创建对象并通过构造器、结构体或闭包传入。这种显式传参本身就是依赖注入的一种形式，通常称为**手动依赖注入**。

真正需要区分的不是“有没有参数”，而是以下几个问题：对象由谁创建、何时创建、同一次请求是否复用、何时释放，以及业务代码是否清楚地表达了自己依赖什么。把这些混成一个叫“单例”的词，问题自然会变得暧昧；而暧昧在工程里通常不是什么优点。

## 一、先澄清：参数传递、DI、IoC 与单例不是同一个概念

这几个概念经常一起出现，却分别回答不同的问题。

| 概念 | 回答的问题 | 典型表现 |
| --- | --- | --- |
| 依赖 | 一个对象要完成工作需要什么协作者？ | `UserService` 需要 `UserRepository` |
| 依赖注入（DI） | 协作者怎样进入对象？ | 构造器参数、函数参数、框架注入 |
| 控制反转（IoC） | 谁控制对象创建和调用流程？ | Spring 容器、Web 框架调用路由函数 |
| 单例 / 单例作用域 | 同一作用域内保留几个对象实例？ | 一个应用一个连接池、一个容器一个 Bean |
| 生命周期 | 对象何时创建和销毁？ | 应用启动、一次请求、一次事务 |

例如下面的 Go 代码中，`NewUserHandler` 的参数就是依赖注入：`UserHandler` 没有自己 `new` 一个服务，而是由外部提供。

```go
type UserService interface {
    Find(ctx context.Context, id int64) (*User, error)
}

type UserHandler struct {
    service UserService
}

func NewUserHandler(service UserService) *UserHandler {
    return &UserHandler{service: service}
}
```

它没有 Spring 那样的容器自动扫描，也没有根据类型自动寻找对象；但“对象不负责创建自己的依赖，而是由外部交给它”这一点已经满足 DI 的核心定义。反过来，若类里直接 `new UserService()`，对象创建和业务逻辑纠缠在一起，才更接近没有 DI 的写法。

```java
// 不推荐：业务类自己决定具体实现和创建时机。
public class UserController {
    private final UserService service = new UserService(new JdbcUserRepository());
}
```

还要特别注意：**一个对象以参数形式出现，不等于每次都会创建一个新对象。**参数只是引用传递的通道。传入的可以是应用启动时唯一创建的连接池，也可以是每个请求新建的数据库会话；二者的生命周期由组装代码和框架作用域决定，而不是由参数长得像不像参数决定。

## 二、Spring：容器集中装配，构造器参数仍然是依赖声明

Spring 的便利之处，不是让依赖凭空消失，而是将“发现候选对象、创建对象、解析依赖、管理作用域、应用 AOP 代理”等工作交给 `ApplicationContext`。业务类通常只保留构造器参数：

```java
@Repository
public class JdbcUserRepository implements UserRepository {
    // 省略 JDBC 或 JPA 细节
}

@Service
public class UserService {
    private final UserRepository repository;

    public UserService(UserRepository repository) {
        this.repository = repository;
    }

    public UserDto find(long id) {
        return UserDto.from(repository.findById(id));
    }
}

@RestController
@RequestMapping("/users")
public class UserController {
    private final UserService service;

    public UserController(UserService service) {
        this.service = service;
    }

    @GetMapping("/{id}")
    public UserDto get(@PathVariable long id) {
        return service.find(id);
    }
}
```

这里并不是“不写参数”。恰恰相反，推荐的构造器注入要求显式写出参数；不同的是，调用构造器的人从应用代码变成了 Spring 容器。容器根据 Bean 定义和类型信息找到 `UserRepository` 的实现，先创建仓储，再创建服务，最后创建控制器。

```text
组件扫描 / @Bean 方法
          -> BeanDefinition
          -> Spring 容器按依赖关系创建 Bean
          -> JdbcUserRepository
          -> UserService(repository)
          -> UserController(service)
          -> DispatcherServlet 调用 Controller
```

### 1. `singleton` 是 Spring 的默认 Bean 作用域，不是全局变量

Spring 中未指定作用域的 Bean 默认是 `singleton`。它表示**同一个 Spring 容器中通常只有一个该 Bean 实例**，而不是 JVM 中绝对只有一个对象，更不表示它天然线程安全。

因此，下面的对象通常适合单例作用域：

- 无状态的 `Service`、`Repository`、配置对象；
- 线程安全且昂贵的 HTTP 客户端、连接池、序列化器；
- 由 Spring 代理管理的事务、缓存或安全相关组件。

而把当前用户、当前请求的数据库会话、可变的订单草稿放进单例 Bean，往往会造成请求间数据串扰或并发问题。Spring 另有 `request`、`session`、`prototype` 等作用域；默认单例只是一个常用选择，不是一条把所有对象都做成全局共享状态的许可。

### 2. Spring 替你承担了哪些成本

容器带来的能力包括自动装配、条件化注册、配置绑定、生命周期回调、循环依赖诊断以及 AOP 代理。大型 Java 应用中，这能显著减少样板化组装代码。

相应的代价也应坦率承认：对象是从哪里注册的、为什么注入了某个实现、代理究竟包在谁外面，有时需要沿着自动配置和容器日志追踪。容器不是魔法，只是把组装过程放到了一个更强大的幕后系统里。

## 三、FastAPI：有 DI，但它主要围绕请求依赖图工作

FastAPI 的 `Depends` 就是官方提供的依赖注入机制。路由函数和依赖函数都声明参数，框架会在处理请求时解析参数、调用依赖提供者，并将结果注入目标函数。依赖还可以继续依赖其他依赖，形成树状图。

下面用 SQLAlchemy 风格的伪业务代码说明一个常见分层。为突出重点，省略了模型和异常处理。

```python
from typing import Annotated, Generator

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

app = FastAPI()

# 应用级资源：启动时创建一次，多个请求共享连接池。
engine = create_engine("postgresql+psycopg://app:secret@localhost/blog")
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Generator[Session, None, None]:
    # 请求级资源：每次请求获得一个 Session，结束后关闭。
    with SessionLocal() as session:
        yield session


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, user_id: int) -> dict | None:
        # 这里应查询数据库；用字典只是简化示例。
        return {"id": user_id, "name": "Yukino"}


def get_user_service(
    session: Annotated[Session, Depends(get_session)],
) -> UserService:
    return UserService(session)


@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    service: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    user = service.find(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user
```

这条依赖链不是手工逐层调用的：请求到达后，FastAPI 会先解析 `get_session`，再以它的结果调用 `get_user_service`，最后调用路由函数。`yield` 前的代码用于取得资源，`yield` 后或 `finally` 中的代码用于清理资源。对同一路由的一次请求，公共子依赖的结果会被缓存和复用；这是一种**请求内缓存**，不等于应用级单例。

```text
一次 GET /users/42
  -> get_session()：创建本请求的 Session
  -> get_user_service(session)：创建使用该 Session 的服务
  -> get_user(42, service)：处理业务
  -> get_session() 的退出逻辑：关闭 Session
```

### 1. 不要把 FastAPI 的所有依赖都误当成单例

上例里至少有三种不同的生命周期：

| 对象 | 建议生命周期 | 原因 |
| --- | --- | --- |
| `Engine` / HTTP 连接池 | 应用级 | 创建昂贵、通常线程安全、应复用连接池 |
| `Session` | 请求或工作单元级 | 包含事务和状态，不应跨请求共享 |
| `UserService` | 常常是请求级或短生命周期 | 若持有 `Session`，必须与其同生共死 |
| 认证后的当前用户 | 请求级 | 不同请求对应不同身份 |

如果某个依赖提供函数每次调用都 `return SomeService()`，它默认不会自动变成单例。相反，若把可变的 `Session` 放到模块全局变量中，多个并发请求可能互相污染事务状态。表面上少写了几行，实际上只是把问题塞进了未来的事故报告里。

对于真正的应用级初始化和收尾，例如创建连接池、加载机器学习模型、关闭客户端，FastAPI 推荐使用应用的 `lifespan`。它在应用开始接收请求前执行初始化，并在停止时执行清理；这与依赖函数中的 `yield` 相似，但作用域是整个应用而不是某次请求。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_model()
    try:
        yield
    finally:
        app.state.model.close()


app = FastAPI(lifespan=lifespan)
```

`app.state` 可以保存应用级资源，但不应成为随意从任何地方取对象的“全局抽屉”。更清晰的做法是：在依赖提供函数中读取应用级资源，再将其以明确的类型传给服务；业务核心仍然通过构造器接收自己需要的协作者。

### 2. FastAPI 的参数有两类，别把它们混在一起

路由函数的参数同时承担两种职责：

- `user_id: int`、`q: str | None` 这类参数描述**外部输入**，FastAPI 从路径、查询串、请求体或请求头中解析它们；
- `service: Annotated[UserService, Depends(get_user_service)]` 描述**内部依赖**，FastAPI 调用提供者并注入结果。

只写 `service: UserService` 并不会让 FastAPI 像 Spring 一样从容器里按类型寻找 Bean。需要用 `Depends` 明确给出提供者，或将一个可调用对象 / 类作为提供者。它牺牲了一点隐式便利，换来的是路由签名上可以直接看见请求处理依赖了什么。

### 3. 测试时覆盖依赖，而不是连接真实数据库

FastAPI 的显式提供者有一个很实用的优点：测试可以覆盖特定依赖。

```python
def get_fake_user_service() -> UserService:
    return FakeUserService()


app.dependency_overrides[get_user_service] = get_fake_user_service
```

测试结束后应清理 `app.dependency_overrides`，避免覆盖影响后续用例。这个机制与 Spring 的测试上下文、`@MockBean` 所解决的问题相似，只是替换入口从容器中的 Bean 变成了依赖提供函数。

## 四、Gin：框架负责 HTTP 流程，应用负责对象组装

Gin 的核心是路由、`gin.Context` 和中间件链，并没有像 Spring 或 FastAPI 那样的内建通用 DI 解析器。Gin 会调用符合 `gin.HandlerFunc` 签名的处理函数，但它不会看到某个参数类型就自动创建 `UserService`。

因此，Go 项目最常见也最可靠的模式是：在 `main` 或专门的 `wire` / `bootstrap` 包中完成对象图组装，再将依赖传入 Handler。这个位置常被称为 **composition root（组合根）**。

```go
package main

import (
    "database/sql"
    "log"
    "net/http"

    "github.com/gin-gonic/gin"
)

func main() {
    db, err := sql.Open("pgx", "postgres://app:secret@localhost/blog")
    if err != nil {
        log.Fatal(err)
    }
    defer db.Close()

    repository := NewPostgresUserRepository(db)
    service := NewUserService(repository)
    handler := NewUserHandler(service)

    router := gin.New()
    router.Use(gin.Logger(), gin.Recovery())
    registerUserRoutes(router, handler)

    if err := router.Run(":8080"); err != nil && err != http.ErrServerClosed {
        log.Fatal(err)
    }
}

func registerUserRoutes(router gin.IRoutes, handler *UserHandler) {
    router.GET("/users/:id", handler.Get)
}
```

对应的 Handler 不创建数据库、不读取全局服务定位器，只保存它确实要使用的接口：

```go
type UserHandler struct {
    service UserService
}

func NewUserHandler(service UserService) *UserHandler {
    return &UserHandler{service: service}
}

func (h *UserHandler) Get(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"message": "invalid user id"})
        return
    }

    user, err := h.service.Find(c.Request.Context(), id)
    if errors.Is(err, ErrUserNotFound) {
        c.JSON(http.StatusNotFound, gin.H{"message": "user not found"})
        return
    }
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"message": "internal error"})
        return
    }

    c.JSON(http.StatusOK, user)
}
```

这里的 `handler`、`service`、`repository` 通常在进程启动时各创建一次，效果上很像 Spring 的单例 Bean；区别在于生命周期、关闭顺序和替换实现都由 Go 应用代码明确控制。`sql.DB` 也不是“一条数据库连接”，而是一个应长期复用的连接池句柄，所以启动时创建一次是合理的。

### 1. 中间件闭包也能注入依赖

认证器、日志器、限流器等横切能力，适合通过中间件工厂接收依赖并返回 `gin.HandlerFunc`：

```go
func AuthMiddleware(tokens TokenVerifier) gin.HandlerFunc {
    return func(c *gin.Context) {
        token := strings.TrimPrefix(c.GetHeader("Authorization"), "Bearer ")
        principal, err := tokens.Verify(c.Request.Context(), token)
        if err != nil {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"message": "unauthorized"})
            return
        }

        c.Set("principal", principal)
        c.Next()
    }
}

// 组合根中：router.Use(AuthMiddleware(tokenVerifier))
```

`c.Set` 适合把**当前请求**产生的认证结果等数据传给后续中间件或 Handler；它不适合作为应用服务的通用容器。用字符串键从 `gin.Context` 任意取服务，会弱化类型检查和依赖可见性，最终写成 Go 版本的服务定位器。它当然能运行，就像把文件都塞到桌面上也能找到；只是没有必要把可维护性一并丢掉。

还要注意，`gin.Context` 是请求对象。Gin 为性能会复用它，不能把它保存到长生命周期对象或在新 goroutine 中直接长期使用；需要异步工作时应传递必要的不可变数据和标准 `context.Context`，并遵守取消、超时与资源所有权的边界。

## 五、三种模型的本质对比

| 维度 | Spring | FastAPI | Gin |
| --- | --- | --- | --- |
| 依赖声明 | 构造器参数、`@Bean`、注解 | `Depends`、依赖函数 / 可调用对象 | 构造器参数、字段、闭包 |
| 默认装配者 | Spring IoC 容器 | FastAPI 请求依赖解析器 | 应用启动代码 |
| 按类型自动查找对象 | 是，受候选 Bean、限定符等规则约束 | 否，需明确提供者 | 否，需显式传入 |
| 常见默认生命周期 | Bean 默认容器级单例 | 依赖通常按请求解析，公共子依赖可请求内复用 | 由创建位置决定，常在进程启动时创建长生命周期对象 |
| 请求级资源 | `request` scope、事务绑定资源等 | `yield` 依赖、请求状态 | `gin.Context`、`Request.Context()`、中间件 |
| 测试替换点 | 容器 Bean / 测试配置 | `dependency_overrides` | 构造器传入 fake 或 mock |

所以，不能简单地说“Spring 是依赖注入，Gin 是手动传参”。更准确的说法是：

- Spring 使用**容器驱动、集中管理的 DI**；
- FastAPI 使用**声明式、请求驱动的 DI**，同时需要应用代码管理应用级资源；
- Gin 常使用**显式、手动组装的 DI**。

三者都可以写出清晰、可测试的分层应用；差异主要在于自动化程度、显式程度和生命周期管理的归属。

## 六、不要把 Web 框架参数当成业务层的唯一注入方式

一个常见误区是：既然 FastAPI 路由参数和 Gin Handler 都能拿到对象，就把所有业务逻辑都写在路由函数里。这样依赖虽然“被传进来了”，分层却消失了。

更稳妥的边界如下：

```text
HTTP 层
  -> 解析路径、请求体、鉴权结果，转换 HTTP 错误
  -> 调用应用服务

应用服务层
  -> 组织用例、事务边界、权限规则
  -> 依赖领域接口或仓储接口

基础设施层
  -> 数据库、缓存、第三方 HTTP、消息队列的具体实现

组合根 / 容器
  -> 选择具体实现并完成装配
```

在 Spring 中，组合根大部分是 `@Configuration`、自动配置与容器；在 FastAPI 中，是应用初始化代码加依赖提供函数；在 Gin 中，常常就是 `main` 或 `wire` 包。让 HTTP 层依赖应用服务，让应用服务依赖抽象接口，而不是让业务层到处认识 `Request`、`gin.Context` 或 `FastAPI`，测试和迁移都会轻松得多。

## 七、何时应共享，何时必须新建

判断“要不要单例”时，不要先看框架，而应先问对象是否有可变的请求状态、是否线程安全、创建成本是否高，以及关闭责任属于谁。

### 1. 通常适合应用级共享的对象

- 数据库连接池、HTTP 客户端、Redis 客户端；
- 不保存请求状态的配置、序列化器、校验器；
- 无状态的业务服务和仓储实现；
- 只读模型或只读缓存，前提是底层库支持并发访问。

### 2. 通常必须限定在请求或工作单元内的对象

- ORM `Session`、事务对象、数据库游标；
- 当前用户、租户、语言、Trace ID；
- 未完成的响应对象、文件上传流；
- 持有请求上下文或可变业务草稿的对象。

### 3. 无状态不等于绝对安全

一个 Spring 单例 Service、Go 的全局服务实例或 Python 模块级客户端，即使字段看起来很少，也可能持有非线程安全的第三方客户端、可变缓存或懒初始化状态。共享前仍要阅读其并发语义。反之，数据库连接池可以共享，不代表从池中取得的每个连接或事务也可以共享。

这条边界比“框架会不会自动注入”更重要。错误的作用域会让看似优雅的自动注入变成跨请求的数据泄漏；正确的作用域即使由手工代码管理，也完全可以稳定而清楚。

## 八、从 Spring 迁移时的一套落地步骤

若你习惯 Spring，可以按下面的顺序在 FastAPI 或 Gin 中组织项目。

1. 列出每个对象的依赖和生命周期，例如连接池是应用级，`Session` 是请求级。
2. 保留构造器注入：服务接收仓储接口，Handler 接收服务，不在业务类内部创建具体实现。
3. 选一个组合根：FastAPI 用 `lifespan`、应用工厂和依赖提供函数；Gin 用 `main` 或 `wire` 包。
4. 将请求级资源放进 FastAPI `yield` 依赖，或从 Gin 的请求上下文向下传递；不要塞进全局单例。
5. 用框架边界处理鉴权、日志、追踪和 HTTP 错误，用应用服务处理业务规则。
6. 为构造器依赖提供 fake / mock；FastAPI 覆盖 provider，Gin 直接构造测试用 Handler，Spring 则替换测试上下文中的 Bean。

如果项目规模很大，Go 也可以使用 Wire、Fx 等装配工具，Python 也有第三方 DI 容器。它们能减少组合根的样板代码，但不应先于清晰的生命周期设计。工具可以生成接线图，却无法替你判断一把数据库会话能否跨请求复用；这一点仍然需要工程师自己负责，真是令人遗憾地无法外包。

## 九、总结

“FastAPI 或 Gin 需要手动把单例写成参数”并不表示它们落后于 Spring，而是三者把对象管理分配给了不同层次。

- Spring 的构造器注入依然是参数注入，只是容器自动解析并创建 Bean；默认单例是容器作用域，不是全局线程安全保证。
- FastAPI 明确提供 `Depends` DI 系统。它尤其适合表达请求依赖、认证、校验和资源清理；应用级资源则应通过 `lifespan` 等启动逻辑管理。
- Gin 不提供通用容器，推荐在组合根显式创建连接池、仓储、服务和 Handler，再用构造器或闭包传入。这正是手动 DI，而不是没有 DI。
- 参数的存在不决定对象数量。连接池可以是应用级共享，数据库会话和当前用户必须是请求级；先设计生命周期，再决定注入方式。

当依赖关系能在构造器、提供函数或组合根中被一眼看见时，代码并没有失去 Spring 的工程性，反而获得了一种很朴素的可追踪性。自动装配适合降低规模化成本，显式装配适合保持边界可见；选哪一种，应由项目复杂度和团队习惯决定，而不是由谁少写了一行 `new` 决定。

## 参考资料

- [FastAPI：Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI：Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [FastAPI：Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Gin：Middleware](https://gin-gonic.com/en/docs/middleware/)
- [Gin：在中间件中启动 goroutine](https://gin-gonic.com/en/docs/middleware/goroutines-inside-a-middleware/)
