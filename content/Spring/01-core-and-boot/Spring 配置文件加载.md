+++
date = '2026-03-02T22:52:53+08:00'
draft = false
title = 'Spring 配置文件加载'
+++

我们的一般认知是 Spring 的配置文件加载优先级是 `application-dev.yaml` 大于 `application.yaml` 的，但是今天在项目中却发现使用 `@Value` 注解注入的配置文件中的值是 `application.yaml` 的，现已经定位问题。

我使用 Spring  `ConfigurableEnvironment` 容器打印出配置数据源（`Environment` 没有实现相应的方法，需要强转），代码如下：

```java
@Component
public class EnvironmentLogger {

    @Resource
    private Environment environment;

    @Value("${hmac}")
    private Boolean isBootUpKws;

    @PostConstruct
    public void init() {
        System.out.println("Environment Logger=================================");
        printEnvironment();
    }

    private void printEnvironment() {

        System.out.println("isBootUpKws=" + isBootUpKws);

        ConfigurableEnvironment env = (ConfigurableEnvironment) environment;
        String key = "hmac";
        for (PropertySource<?> propertySource : env.getPropertySources()) {
            System.out.println("propertySource.getName: " + propertySource.getName());
            System.out.println(key + ": " + propertySource.getProperty(key));
        }
    }
}
```

`application.yaml` 配置文件内容是 

```yaml
spring:
  application:
    name: server

  profiles:
    active: dev

  config:
    import:
      - optional:classpath:application-${spring.profiles.active}.yaml
hmac: false
```

`application-dev.yaml` 配置文件内容是

```yaml
hmac: true
```

启动项目后，控制台打印，一下内容

```bash
Environment Logger=================================
isBootUpKws=false
propertySource.getName: configurationProperties
hmac: false
propertySource.getName: servletConfigInitParams
hmac: null
propertySource.getName: servletContextInitParams
hmac: null
propertySource.getName: systemProperties
hmac: null
propertySource.getName: systemEnvironment
hmac: null
propertySource.getName: random
hmac: null
propertySource.getName: cachedrandom
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #4)
hmac: false
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #3)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #2)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #1)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #8)
hmac: true
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #7)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #6)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #5)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #4)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #3)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #2)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #1)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:application-dev.yaml' (document #0)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #0)
hmac: null
propertySource.getName: springCloudClientHostInfo
hmac: null
propertySource.getName: applicationInfo
hmac: null
```

> 打印的 `PropertySource<?>` 先后顺序，就是 Spring 配置文件读取的优先级。

可以发现，`application.yaml` 的配置明显在前面 

```bash
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #8)
hmac: true
```

而 `application-dev.yaml` 虽然被加载了，但是优先级明显低于 `application.yaml`。如果同一个配置，`application.yaml` 的配置将会优先加载。经过查证，问题就是出现在了 `spring.config.import`。

感兴趣可以阅读 [Spring Boot 的官方文档](https://docs.spring.io/spring-boot/reference/features/external-config.html#features.external-config.files.profile-specific)，这篇文档讲的很清楚。文档中明说 **如果指定了多个配置文件，则采用后加生效策略**。并且也提到，`spring.config.import` 导入文件中的值将优先于原始文件中的值触发，原始文件就是配置了 `spring.config.import` 的文件。根据后生效策略，如果有一个相同的配置，原始文件 `application.yaml` 的值就会覆盖 `spring.config.import` 的值。

这也就是为什么我们上面的配置会发生莫名其妙的值覆盖问题。我们使用 `spring.config.import` 导入的 `application-dev.yaml` 被当作外部配置文件先导入，而不是作为 `spring.profiles.active`。解决办法就是删除 `- optional:classpath:application-${spring.profiles.active}.yaml` 这行，只使用 Spring 官方指定的方式配置 `spring.profiles.active`，也就是 

```yaml
spring:
  profiles:
    active: dev
```

这样，`application-dev.yaml` 将会成为后导入的活跃配置文件。

这时再执行上述代码，控制台将会打印：

```bash
Environment Logger=================================
isBootUpKws=true
propertySource.getName: configurationProperties
hmac: true
propertySource.getName: servletConfigInitParams
hmac: null
propertySource.getName: servletContextInitParams
hmac: null
propertySource.getName: systemProperties
hmac: null
propertySource.getName: systemEnvironment
hmac: null
propertySource.getName: random
hmac: null
propertySource.getName: cachedrandom
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #8)
hmac: true
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #7)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #6)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #5)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #4)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #3)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #2)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #1)
hmac: null
propertySource.getName: Config resource 'class path resource [application-dev.yaml]' via location 'optional:classpath:/' (document #0)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #4)
hmac: false
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #3)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #2)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #1)
hmac: null
propertySource.getName: Config resource 'class path resource [application.yaml]' via location 'optional:classpath:/' (document #0)
hmac: null
propertySource.getName: springCloudClientHostInfo
hmac: null
propertySource.getName: applicationInfo
hmac: null
```

`application-dev.yaml` 文件优先级高于 `application.yaml`。
