+++
date = '2025-08-04T20:36:03+08:00'
draft = false
title = 'SpringBoot解决跨域问题'
+++

## 配置CorsFilter（全局跨域）

通过手动配置`CorsFilter`

```java
@Configuration
public class WebGlobalConfig {
    @Bean
    public CorsFilter corsFilter() {
        
    }
}
```

## 重写WebMvcConfigurer（全局跨域）

`WebMvcConfigurer`接口时SpringBoot提供的用于配置SpringMVC的一些特性的

```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {
    
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        
    }
}
```

## 使用注解@CorssOrigin（局部跨域）

可以在类上使用，也可以在方法上使用
