+++
date = '2025-10-22T19:18:57+08:00'
draft = false
title = 'CompletableFuture'
+++

`CompletableFuture` 是 Java 8 引入的异步编排工具。它实现了 `Future`，但比传统 `Future` 更适合表达任务之间的依赖、组合、汇总和异常处理。

传统 `Future` 主要是“提交任务，然后阻塞获取结果”。`CompletableFuture` 更像是“任务完成后，继续执行下一段流程”。

## 一、创建异步任务

无返回值任务使用 `runAsync`：

```java
CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
    System.out.println("run async");
});

future.join();
```

有返回值任务使用 `supplyAsync`：

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    return "hello";
});

String result = future.join();
```

默认情况下，未指定线程池的异步任务会使用 `ForkJoinPool.commonPool()`。业务项目中更推荐传入自定义线程池，尤其是任务里包含数据库、RPC、文件 IO 等阻塞操作时。

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    return queryUserName();
}, bizExecutor);
```

## 二、串行编排

`thenApply` 接收上一步结果，并返回新结果：

```java
CompletableFuture<String> future = CompletableFuture
        .supplyAsync(() -> "hello", bizExecutor)
        .thenApply(value -> value + " world");
```

`thenAccept` 接收结果，但不返回新值：

```java
CompletableFuture<Void> future = CompletableFuture
        .supplyAsync(() -> "hello", bizExecutor)
        .thenAccept(value -> System.out.println(value));
```

`thenRun` 不关心上一步结果，只在上一步完成后继续执行：

```java
CompletableFuture<Void> future = CompletableFuture
        .supplyAsync(() -> "hello", bizExecutor)
        .thenRun(() -> System.out.println("finished"));
```

如果回调方法名带 `Async`，例如 `thenApplyAsync`，表示回调会异步执行。没有 `Async` 的回调，可能由完成上一步任务的线程直接执行。

## 三、组合两个任务

两个任务都完成后合并结果，用 `thenCombine`：

```java
CompletableFuture<String> userFuture =
        CompletableFuture.supplyAsync(() -> queryUser(), bizExecutor);

CompletableFuture<Integer> scoreFuture =
        CompletableFuture.supplyAsync(() -> queryScore(), bizExecutor);

CompletableFuture<String> resultFuture = userFuture.thenCombine(scoreFuture,
        (user, score) -> user + ":" + score);
```

如果第二个任务依赖第一个任务的结果，并且第二个任务本身也返回 `CompletableFuture`，使用 `thenCompose` 避免嵌套：

```java
CompletableFuture<Order> orderFuture = CompletableFuture
        .supplyAsync(() -> queryUserId(), bizExecutor)
        .thenCompose(userId -> CompletableFuture.supplyAsync(
                () -> queryOrder(userId), bizExecutor));
```

## 四、等待多个任务

`allOf` 等待所有任务完成：

```java
CompletableFuture<User> userFuture =
        CompletableFuture.supplyAsync(() -> queryUser(), bizExecutor);

CompletableFuture<Order> orderFuture =
        CompletableFuture.supplyAsync(() -> queryOrder(), bizExecutor);

CompletableFuture<Void> all = CompletableFuture.allOf(userFuture, orderFuture);
all.join();

User user = userFuture.join();
Order order = orderFuture.join();
```

`anyOf` 任意一个任务完成后返回：

```java
CompletableFuture<Object> first = CompletableFuture.anyOf(
        CompletableFuture.supplyAsync(() -> queryFromCache(), bizExecutor),
        CompletableFuture.supplyAsync(() -> queryFromRemote(), bizExecutor)
);
```

`allOf` 返回的是 `CompletableFuture<Void>`，不会自动帮你收集每个任务的结果。结果仍然要从原来的 future 中取。

## 五、异常处理

常用异常处理方法有三个：

| 方法 | 作用 |
| --- | --- |
| `exceptionally` | 发生异常时返回兜底值 |
| `handle` | 成功或失败都会执行，并返回新结果 |
| `whenComplete` | 成功或失败都会执行，通常用于记录日志，不改变原结果 |

示例：

```java
CompletableFuture<String> future = CompletableFuture
        .supplyAsync(() -> queryRemote(), bizExecutor)
        .exceptionally(ex -> {
            log.warn("query remote failed", ex);
            return "fallback";
        });
```

`join()` 和 `get()` 都能获取结果，但异常包装不同：

- `get()` 抛出受检异常，例如 `ExecutionException`。
- `join()` 抛出运行时异常 `CompletionException`。

## 六、常见坑

- 不要让阻塞 IO 任务长期占用 `ForkJoinPool.commonPool()`。
- 不要忘记处理异常，否则异步任务失败时可能只在最终 `join` 才暴露。
- 不要无限制创建大量异步任务，本质上仍然会消耗线程池和队列资源。
- 注意没有 `Async` 后缀的回调可能在当前完成线程中执行，回调太重会拖慢上游任务。
- 多个任务并行时，要明确超时、降级和取消策略。

## 七、总结

`CompletableFuture` 适合表达异步流程：串行依赖用 `thenApply`、`thenCompose`，并行合并用 `thenCombine`、`allOf`，异常兜底用 `exceptionally` 或 `handle`。它能让异步代码少一点回调泥潭，但前提是线程池、异常和超时都被认真处理。
