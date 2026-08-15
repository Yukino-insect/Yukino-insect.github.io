+++
date = '2025-11-16T21:14:40+08:00'
draft = false
title = 'Spring MVC 异步请求和拦截器行为'
+++

Spring MVC 支持异步请求处理。它适合控制器需要等待耗时 IO、远程调用或外部回调结果，但又不希望长时间占用 Servlet 容器工作线程的场景。

## 一、常见返回类型

Spring MVC 常见异步返回类型包括：

1. `Callable`：把耗时逻辑交给后台线程池执行。
2. `WebAsyncTask`：在 `Callable` 基础上增加超时和回调配置。
3. `DeferredResult`：由外部线程或事件在未来某个时刻设置结果。
4. `CompletableFuture`：以异步计算结果作为响应。

## 二、Callable 的执行过程

当 Controller 返回 `Callable` 时，主请求线程不会一直阻塞等待业务执行完成。大致流程如下：

1. `DispatcherServlet` 接收到请求。
2. Controller 返回 `Callable`。
3. Spring MVC 把 `Callable` 提交给 `TaskExecutor`。
4. Servlet 容器线程退出，响应保持打开。
5. 后台线程执行完成后，Spring MVC 重新分派请求。
6. `DispatcherServlet` 处理异步结果并写回响应。

这里的“重新分派”很重要，它会影响过滤器和拦截器的执行表现。

## 三、拦截器会执行几次

普通 `HandlerInterceptor` 在异步请求中可能经历两段流程：

1. 初始请求阶段。
2. 异步结果重新分派阶段。

因此某些拦截器逻辑可能会被触发多次。对于鉴权、日志、计时、链路追踪等逻辑，要区分当前请求是否已经进入异步处理。

如果要精细处理异步生命周期，可以使用 `AsyncHandlerInterceptor`，关注 `afterConcurrentHandlingStarted` 方法。

## 四、DeferredResult 和 WebAsyncTask

`DeferredResult` 更适合事件驱动场景。例如请求进入后，需要等待 MQ 消息、长轮询结果或其他线程回调。

`WebAsyncTask` 更适合把本地耗时任务提交到后台线程池，并为该任务设置超时时间、超时回调和完成回调。

## 五、注意点

异步请求不是无限扩容能力。后台线程池仍然需要合理配置，否则只是把阻塞从 Servlet 线程转移到业务线程池。

同时，异步处理中的上下文传递也要注意，例如登录用户、traceId、MDC 日志上下文等，都可能因为线程切换而丢失。
