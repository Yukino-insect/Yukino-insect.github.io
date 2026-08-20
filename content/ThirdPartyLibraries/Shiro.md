+++
date = '2025-08-09T16:09:04+08:00'
draft = false
title = 'Shiro'
+++

Apache Shiro 是一个 Java 安全框架，主要用于身份认证、授权、加密和会话管理。它可以用于 JavaSE，也可以用于 Java Web 项目。

## 一、核心能力

Shiro 的核心能力包括：

1. Authentication：身份认证，判断用户是谁。
2. Authorization：授权，判断用户能做什么。
3. Session Management：会话管理。
4. Cryptography：加密和密码处理。

其中最常见的是登录认证和权限校验。

## 二、权限模型

权限管理常见模型有三种：

1. 基于页面的权限控制：不同用户进入不同页面。
2. 基于用户和权限的控制：用户直接绑定权限。
3. 基于角色的访问控制：用户绑定角色，角色绑定权限。

RBAC 是实际项目中更常见的方式。它通常包含用户表、角色表、权限表、用户角色关联表和角色权限关联表。

## 三、Shiro 的核心对象

Shiro 中常见对象包括：

1. `Subject`：当前操作用户。
2. `SecurityManager`：安全管理核心。
3. `Realm`：连接业务用户、角色、权限数据的组件。

登录时，Shiro 会把用户提交的身份信息交给 Realm 校验。授权时，也会通过 Realm 查询用户拥有的角色和权限。

## 四、和 Spring Security 的选择

Shiro API 相对简单，学习成本低。Spring Security 和 Spring 生态集成更深，功能更完整，也更适合 Spring Boot、OAuth2、资源服务器等复杂场景。

如果项目较老或权限模型简单，Shiro 仍然可用。如果新项目基于 Spring Boot，并且需要和 OAuth2、JWT、网关鉴权等能力集成，Spring Security 通常更合适。
