+++
date = '2025-10-03T01:03:55+08:00'
draft = false
title = 'Captcha'
+++

Captcha = **Completely Automated Public Turing test to tell Computers and Humans Apart**
 意思是：一种 **全自动区分计算机和人类的测试**，通过生成随机、难以被机器识别的内容，让用户输入，来确认操作者是人类而非程序

验证码最常见的用途就是：

- **防止恶意注册/刷号**

- **防止暴力破解密码**

- **防止接口被批量调用**

- **提高安全性（区分人机行为）**

#### 常见验证码类型

1. **图形验证码**

   最常见（数字 + 字母混合，带干扰线/噪点），例如 `3g9X`

2. **算术验证码**

   出题目让用户计算，比如 `8 + 5 = ?`。简单且防 OCR

3. **滑块验证码**

   用户拖动滑块拼合图像，腾讯/极验常见

4. **点击式验证码**

   例如“请点击所有包含小猫的图片”

5. **短信/邮箱验证码（OTP）**

   发送一次性密码（One-Time Password），常见于登录/支付

现在看一下如何在项目中使用 `anji-plus/captcha`

首先在 Spring Boot 中引入依赖

```xml
<dependency>
    <groupId>com.anji-plus</groupId>
    <artifactId>captcha</artifactId>
    <version>1.3.0</version> 
</dependency>
```

**`anji-plus/captcha`**，这是国内用得比较多的 **行为验证码组件**，支持滑块验证码、点击文字验证码，比传统图形验证码更安全。

##### 配置 `application.yml`

```yaml
aj:
  captcha:
    type: blockPuzzle         # 验证码类型：blockPuzzle(滑块拼图) 或 clickWord(点选文字)
    cache-type: local         # 存储方式：local(本地内存)，redis(推荐生产环境)
    slip-offset: 5            # 容错范围（像素），拖动误差小于这个值算成功
    aes-status: true          # 是否启用 AES 加密
    interference-options: 2   # 干扰项，增加复杂度
    font-type: 宋体           # 字体
```

##### 启动类

```java
@SpringBootApplication
public class CaptchaDemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(CaptchaDemoApplication.class, args);
    }
}
```

启动后 anji-plus 会自动加载验证码服务。

##### 控制器：获取和校验验证码

```java
@RestController
@RequestMapping("/captcha")
public class CaptchaController {

    @Autowired
    private CaptchaService captchaService;

    /**
     * 获取验证码
     */
    @GetMapping("/get")
    public ResponseModel get(@RequestParam(value = "type", defaultValue = "blockPuzzle") String type) {
        // 调用 anji-plus 封装好的服务，返回验证码图片 + token
        return captchaService.get(type);
    }

    /**
     * 校验验证码
     */
    @PostMapping("/check")
    public ResponseModel check(@RequestBody Map<String, String> params) {
        // 前端提交拖动的坐标/点击点坐标，后端校验是否正确
        return captchaService.check(params);
    }
}
```

- `captchaService.get(type)`：生成验证码，返回一张带缺口的背景图、缺口图，以及验证码 token。
- `captchaService.check(params)`：校验前端传回来的坐标是否与 token 匹配。
- 返回类型是 `ResponseModel`，内含 `repCode`、`repMsg`，成功时 `repCode=0000`。

##### 前后端交互流程

1. **前端调用 `/captcha/get`**
   - 返回结果包含：背景图、滑块图、验证码 token。
   - 前端渲染出验证码。
2. **用户拖动/点击完成**
   - 前端把拖动的坐标/点击结果 + token 提交到 `/captcha/check`。
3. **后端校验**
   - 如果成功，返回 `"repCode":"0000"`；
   - 前端即可允许继续业务请求（如登录/注册）。

`CaptchaService`，不是自己写的类，而是 **anji-plus/captcha** 提供的一个核心 **服务接口**，Spring Boot 启动后会自动注入到容器里

`CaptchaService` 的作用是**验证码的核心业务服务接口**，主要负责：

- 生成验证码（滑块拼图、点击文字等）
- 校验验证码
- 二次校验（用于一些场景，比如先通过一次验证码后，登录接口需要再次验证 token）

在 `com.anji.captcha.service.CaptchaService` 接口中，最常用的有三个方法：

```java
public interface CaptchaService {

    /**
     * 生成验证码
     * @param captchaType 验证码类型（blockPuzzle=滑块，clickWord=点选文字）
     * @return ResponseModel 内含图片的Base64数据、token 等
     */
    ResponseModel get(String captchaType);

    /**
     * 校验验证码
     * @param paramMap 前端提交的数据（包含 token 和 pointJson）
     * @return ResponseModel 验证成功/失败
     */
    ResponseModel check(Map<String, String> paramMap);

    /**
     * 二次校验
     * 通常在重要业务接口里使用（如登录），避免验证码绕过
     */
    ResponseModel verification(Map<String, String> paramMap);
}
```

在 `anji-plus/captcha` 里，验证码不仅要生成，还需要 **存储验证码的状态**（比如验证码的 `token`、滑块位置、有效期等），否则校验时就对不上了。

我们看一下以下接口

```java
public interface CaptchaCacheService {
    void set(String var1, String var2, long var3);

    boolean exists(String var1);

    void delete(String var1);

    String get(String var1);

    String type();

    default Long increment(String key, long val) {
        return 0L;
    }
}
```

这个接口就是 **anji-plus/captcha 的缓存抽象层**，也是 **验证码存储策略的 SPI 接口**

`CaptchaCacheService` 的作用

验证码有生命周期（生成 -> 缓存 -> 校验 -> 删除），这就要求框架必须有一个地方来存验证码相关的数据。

- **单机模式** -> 用内存存储（`CaptchaCacheServiceMemImpl`）。
- **分布式模式** -> 用 Redis 存储（`CaptchaCacheServiceRedisImpl`）。

为了兼容不同存储方式，anji-plus 定义了这个接口，只要实现它，就能把验证码存到任何你想要的地方。

#### 方法解析

`void set(String key, String value, long expires)`

- 保存验证码数据
- 参数：
  - `key`：验证码唯一标识（token）
  - `value`：验证码内容（比如滑块位置坐标 JSON）
  - `expires`：过期时间（秒）
- 实现：Redis 就会调用 `SETEX key value expires`

`boolean exists(String key)`

- 判断验证码是否存在
- 防止重复使用同一个验证码，或者检查验证码是否已过期。

`void delete(String key)`

- 删除验证码缓存
- 验证码一旦校验通过，就要删除，避免被重复使用。

`String get(String key)`

- 获取验证码对应的内容
- 在校验阶段使用：比如取出之前存的“正确答案”与用户提交的结果对比。

`String type()`

- 返回实现类型，比如 `"local"` 或 `"redis"`。
- 用于标识当前项目使用哪种存储方式。

`default Long increment(String key, long val)`

- 默认实现返回 `0L`，但可以被重写。
- **用途：防止暴力破解**。
  - 每次用户校验失败，可以调用 `increment("failCount:userId", 1)` 来记录次数。
  - 如果失败次数超过阈值，就锁定该用户或 IP。

**Java SPI 机制**（Service Provider Interface），是 `CaptchaCacheService` 能够灵活切换内存实现 / Redis 实现的核心。

那么，什么是 SPI？

**SPI（Service Provider Interface）** 是 **Java 内置的一种服务发现机制**，它允许：

- **定义一个接口**（约定能力），
- **在 META-INF/services 里声明实现类**，
- **运行时由 ServiceLoader 自动加载实现类**。

换句话说，SPI 提供了一种 **解耦合的插件化机制**，可以让别人扩展自己的接口实现，而不用改代码。

#### 运行机制

1. **定义接口**（服务接口）

   ```java
   public interface CaptchaCacheService {
       void set(String key, String value, long expire);
       String get(String key);
       void delete(String key);
       boolean exists(String key);
       String type();
   }
   ```

2. **实现接口**（服务提供者）

   ```java
   public class CaptchaCacheServiceRedisImpl implements CaptchaCacheService {
       @Override
       public void set(String key, String value, long expire) {
           // 存到 Redis
       }
       // 其他方法省略
       @Override
       public String type() {
           return "redis";
       }
   }
   ```

3. **在 `resources/META-INF/services` 下建一个文件**

   - 文件名：接口的全限定类名

     ```
     com.anji.captcha.service.CaptchaCacheService
     ```

   - 文件内容：实现类的全限定类名（可以写多个，换行分隔）

     ```
     com.anji.captcha.service.impl.CaptchaCacheServiceMemImpl
     com.mall4j.cloud.auth.adapter.CaptchaCacheServiceRedisImpl
     ```

4. **使用 ServiceLoader 加载实现类**

   ```java
   ServiceLoader<CaptchaCacheService> loader = 
       ServiceLoader.load(CaptchaCacheService.class);
   
   for (CaptchaCacheService service : loader) {
       System.out.println("找到实现: " + service.type());
   }
   ```

运行时就会自动把 `MemImpl` 和 `RedisImpl` 加载进来。

#### SPI 的优点

- **解耦合**：接口和实现分离，框架不需要关心具体实现。
- **扩展性强**：只要在 `META-INF/services` 下加个实现类，就能“无感”扩展。
- **常用于插件化/中间件**：比如 JDBC、日志、验证码缓存、RPC 框架。

#### 现实中的例子

1. **JDBC Driver**

   直接写 `DriverManager.getConnection("jdbc:mysql://...")`，JDBC 并不知道 MySQL 怎么实现。是因为 `META-INF/services/java.sql.Driver` 文件里声明了 MySQL 驱动实现类。

2. **日志框架**（SLF4J、Log4j）

   统一接口，不同厂商可以实现自己的 Logger。

3. **anji-plus/captcha**

   定义了 `CaptchaCacheService` 接口，内置内存实现（`MemImpl`），你自己可以写 Redis 实现（`RedisImpl`），框架自动发现并使用合适的实现。

****

默认情况下 **anji-plus/captcha 已经内置了一批图片**，直接就能用：

框架自带的 `captcha` 文件夹（通常在 jar 包里）里就放了几张 **背景图** 和 **模板图**。

引入依赖后，**开箱即用**，不需要额外提供图片。

生成验证码时，会自动随机从这些内置图片里选一张。

#### 也可以自己提供照片，这样可以

1. **自定义风格**

   - 比如想用商城的商品图、公司品牌风格的背景。
   - 或者想让验证码看起来更贴近你的网站 UI。

2. **增强安全性**

   默认图片公开可见，攻击者可能提前准备训练集。如果提供 **大量私有的背景图和模板**，破解难度会大大提升。

3. **多样性需求**

   默认图片数量有限，如果访问量很大，用户可能会经常看到重复的验证码。提供更多图片，能增加随机性。

#### 如何提供自定义图片？

在配置文件 `application.yml` 中指定路径即可，例如：

```yaml
aj:
  captcha:
    # 自定义背景图路径（classpath 或绝对路径都可以）
    jigsaw: classpath:images/captcha/jigsaw
    pic-click: classpath:images/captcha/pic-click
```

- `jigsaw`：滑块拼图的背景图目录
- `pic-click`：点选验证码的背景图目录

只要把自己的图片放到对应目录，Captcha 就会从提供的目录里取。

在此之前，需要配置一下 `CaptchaService` 类

```java
@Configuration
public class CaptchaConfig {

	@Bean
	public CaptchaService captchaService() {
        // 这里用一个 Properties 来存验证码的配置项
		Properties config = new Properties();
        // 设置缓存类型，验证码数据存放在 Redis
		config.put(Const.CAPTCHA_CACHETYPE, "redis");
        // 设置图片上的水印，这里表示不设水印
		config.put(Const.CAPTCHA_WATER_MARK, "");
		// 指定验证码类型为 滑块拼图
		config.put(Const.CAPTCHA_TYPE, CaptchaTypeEnum.BLOCKPUZZLE.getCodeValue());
        // 用来指定 验证码底图和模板图 的路径，如果不设置，默认是 jar 包下的图片
	    config.put(Const.ORIGINAL_PATH_JIGSAW, FileUtil.getAbsolutePath("classpath:captcha"));
        // 生成对应的 CaptchaService 类
		return CaptchaServiceFactory.getInstance(config);
	}
}
```
