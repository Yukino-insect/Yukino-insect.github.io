+++
date = '2026-09-30T20:15:00+08:00'
draft = false
title = 'Maven 传递依赖与 Spring Boot 可执行 Jar：重复依赖为何不重复打包'
+++
多模块项目里，`framework` 和 `rag` 都声明了 `spring-boot-starter-web`，`agent` 又依赖 `rag`。于是很自然会产生疑问：最终可执行包会不会塞进两份 Spring MVC？每个模块是不是都应该自行引入 Web Starter？传递依赖能用，到底算不算合理的模块设计？

答案需要分两层看：**Maven 负责解析一张依赖图并按规则选择最终依赖；Spring Boot 打包插件再将选择后的运行时依赖写入可执行 JAR。**相同 Maven 坐标的同一版本不会因为被多个路径引用就被打进两份，但重复声明仍会影响依赖边界的清晰度。

## 一、从一张依赖图开始

设有如下模块关系：

```text
bootstrap
├─ rag
│  ├─ framework
│  │  └─ spring-boot-starter-web
│  └─ spring-boot-starter-web
└─ agent
   └─ rag
```

这里存在两条抵达 Web Starter 的路径：

```text
bootstrap → rag → spring-boot-starter-web
bootstrap → rag → framework → spring-boot-starter-web
```

这表示 POM 中有重复的“需求表达”，不是最终成品中必然存在两份字节完全相同的 JAR。Maven 会将依赖树解析为一组实际选中的坐标；Spring Boot 再基于这组运行时依赖打包。

## 二、Starter 本身是什么

`spring-boot-starter-web` 是一个依赖聚合入口，通常自身几乎没有业务实现。它会带来 Servlet Web 应用需要的一组依赖，例如 Spring MVC、嵌入式 Tomcat、JSON 序列化和校验集成。

可以粗略看作：

```text
spring-boot-starter-web
├─ spring-boot-starter
├─ spring-boot-starter-json
├─ spring-boot-starter-tomcat
└─ spring-webmvc
```

Starter 的价值是提供经过 Spring Boot 版本管理验证的一组依赖，而不是“让 Controller 自动成为 Bean”。Controller 的发现靠组件扫描，MVC 基础设施的创建靠自动配置。关于三者的边界，可参见[Spring Boot 自动配置、组件扫描与 @Import：三种装配机制](/spring/spring-boot-自动配置组件扫描与-@import三种装配机制/)。

## 三、传递依赖为何能让下游模块编译

若 `agent` 依赖 `rag`，而 `rag` 传递带来了 Spring Web API，那么 `agent` 的源码通常也能使用：

```java
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
```

原因是 Maven 在 `compile` 作用域下会传递依赖。Maven 编译 `agent` 时，已将 `rag` 及其可传递的编译依赖放进编译 classpath。

但“能够编译”不等于“最佳依赖表达”。若 `agent` 的公开代码或大量实现直接使用 Spring MVC 类型，它对 Web API 就有直接的源码依赖。将这种直接依赖只隐藏在 `rag` 的传递依赖后面，会让读者误以为 `agent` 并不依赖 Web；一旦 `rag` 调整依赖，`agent` 可能突然无法编译。

一个实用的原则是：

- 模块直接使用某个库的公开 API，通常应直接声明相应依赖；
- 模块只使用自己的接口，不感知底层库时，可以由实现模块持有依赖；
- 聚合启动模块只放启动、装配和运行时必要配置时，不必为了“显得完整”重复声明每一个下游库。

这不是机械规则。模块边界的目标是让真实依赖关系清楚，而不是让每份 POM 的依赖数看起来最少。

## 四、为什么同一个 JAR 不会被重复打入

Maven 以依赖坐标识别构件，核心坐标包含：

```text
groupId : artifactId : type : classifier : version
```

当多条依赖路径最终指向完全相同的构件，例如同一版本的 `org.springframework:spring-webmvc`，依赖解析结果只会选择一个。Spring Boot Repackage 阶段会把选中的运行时依赖放进：

```text
BOOT-INF/lib/
```

所以最终产物不会是：

```text
BOOT-INF/lib/
├─ spring-webmvc-6.x.jar
└─ spring-webmvc-6.x.jar
```

而是单独一份：

```text
BOOT-INF/lib/
└─ spring-webmvc-6.x.jar
```

因此，两个模块都声明同一个 Starter 的主要成本是 POM 信息重复，而不是 Web MVC 的包体积翻倍。真正让可执行包变大的，是最终依赖集中原本不存在的**唯一构件**，例如文档解析库、云 SDK、向量数据库客户端或可观测性 SDK。

## 五、版本不同并不等于“两份都安全共存”

如果依赖图中出现两个版本，例如：

```text
bootstrap → module-a → library-x:1.0
bootstrap → module-b → library-x:2.0
```

Maven 也不会默认把它们都当成两套并存运行库。它会应用依赖调解规则，常见概括是“路径最近者优先”；处于相同深度时，声明顺序也可能影响选择结果。最终只会选择一个版本进入普通 classpath。

这并不意味着问题被解决了。若 `module-a` 编译时期待 1.0 的方法，而最终选择 2.0 且该方法已删除，运行期可能发生 `NoSuchMethodError`。这类错误比编译错误更麻烦，因为它说明各模块各自能编译，组合运行时却不兼容。

因此应使用 Maven 的依赖树检查实际选择结果：

```bash
mvn dependency:tree
```

只关注 POM 中“写了什么”不够；真正重要的是最终解析后的依赖树“选中了什么”。对于 Spring Boot 应用，优先采用 Boot 提供的依赖管理版本，避免业务模块各自硬编码 Spring 家族的版本。

## 六、scope 会改变 classpath 与最终包

依赖能否被传递、能否进入运行时 classpath、能否打进可执行包，还受 scope 影响：

| scope | 编译可见 | 运行可见 | 通常会被打进 Boot 可执行 JAR |
| --- | --- | --- | --- |
| `compile` | 是 | 是 | 是 |
| `runtime` | 否 | 是 | 是 |
| `provided` | 是 | 通常否 | 否 |
| `test` | 仅测试 | 仅测试 | 否 |

例如数据库驱动若声明为 `runtime`，业务代码不直接引用它的类依然可以正常运行；但如果代码里显式使用该驱动提供的 API，就无法仅靠 `runtime` 在编译期通过。又如把某个真正运行必需的模块错误标为 `test`，组件扫描时它根本不在生产 classpath，自然无法注册其中的 Bean。

## 七、如何验证最终包，而非凭感觉判断

对于“会不会打两份”“某模块是否真的在包内”的问题，最可靠的答案来自构建产物。完成打包后，可检查 JAR 内容：

```bash
jar tf bootstrap/target/bootstrap-*.jar
```

在 Windows PowerShell 中也可使用：

```powershell
jar tf .\bootstrap\target\bootstrap-*.jar |
    Select-String 'BOOT-INF/lib/(spring-webmvc|rag|agent|framework)'
```

你应当看到每个最终选中的模块/依赖各一份。若看到多个不同版本的相似库，或发现某个预期模块缺失，再回到 `mvn dependency:tree` 检查冲突、排除规则与 scope。

需要额外说明的是，Spring Boot 的嵌套 JAR 布局由其专用类加载器处理；不要因为在 `BOOT-INF/lib` 中看见很多 JAR，就手动把它们解压或复制到其他目录。让 Maven 和构建插件维持依赖图，通常更可重复也更容易排查。

## 八、总结

多模块项目里，Web Starter 的重复声明不会让相同的 MVC JAR 重复打进最终可执行包；Maven 会对相同坐标进行依赖解析和选择，Spring Boot 再将最终运行时依赖打包。

不过，依赖去重不是鼓励随意依赖的理由。应让 POM 尽量表达模块真实使用的 API，统一管理版本，定期用 `mvn dependency:tree` 观察实际依赖树，并在需要时检查 `BOOT-INF/lib`。这样才能同时获得清晰的模块边界、可控的包体积和稳定的运行 classpath。
