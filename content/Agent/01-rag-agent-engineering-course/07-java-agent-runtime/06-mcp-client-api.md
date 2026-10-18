+++
date = '2026-10-02T20:06:00+08:00'
draft = false
title = 'MCP Client：Streamable HTTP、initialize、tools/list 与 tools/call'
+++
本模块通过 AgentScope 的 `McpClientBuilder`/`McpClientWrapper` 使用 MCP Java SDK。它的职责是连接 MCP server、完成初始化协商、发现工具并调用；它不会替你完成业务授权或把所有发现工具自动暴露给模型。

## 连接一个 Streamable HTTP Server

`AgentMcpClients.connect` 的实际调用链如下：

```java
String base = StrUtil.removeSuffix(serverUrl, "/");
String url = base.endsWith("/mcp") ? base : base + "/mcp";
McpClientWrapper client = McpClientBuilder.create(serverName)
    .streamableHttpTransport(url)
    .buildSync();
client.initialize().block();
List<McpSchema.Tool> tools = client.listTools().block();
```

`initialize()` 不是可省略的 ping：它完成协议/能力协商，后续工具列表和调用建立在此基础上。这里使用 `buildSync()`，因此 `block()` 只能出现在应用启动、配置刷新这类受控阻塞边界，不能在 Reactor 事件线程或每次用户请求中重复执行。

应用退出时必须：

```java
@PreDestroy
void close() { clients.forEach(McpClientWrapper::close); }
```

项目启动失败会关闭刚创建但未登记的 client，避免连接泄漏。不要为了“可用性”吞掉异常后继续把空 client 注册进工具目录。

## 发现、筛选、调用

`listTools()` 返回标准 `McpSchema.Tool`，包含 name、description、inputSchema、outputSchema、annotations。Ragent 将同名工具按先连接优先放入 `LinkedHashMap`，记录 warning；再由 `AgentToolCatalog` 与项目意图配置取交集、排除 `search_knowledge`/`flush_memory`/`load_skill` 等内置保留名。**发现到 ≠ 可以给模型使用**，这条 allowlist 是必要的。

调用 API 的形状是：

```java
Map<String, Object> meta = Map.of("user_id", userId);
return client.callTool(toolName, arguments, meta);
```

Ragent 从 `RuntimeContext` 取 `McpMeta.entries()` 作为第三个参数。元数据用于请求关联或身份传递，但 MCP server 必须自行验证令牌和资源归属，绝不能把 `user_id` 视为可信认证。

## 失败处理

远端调用需区分：MCP 返回的业务 `isError`、传输异常、任务取消、客户端关闭。框架可转换标准内容，但本地工具层必须把取消返回 `INTERRUPTED`，把异常转换为不泄露细节的 `ToolResultBlock.error`。连接、发现和调用的 timeout、重连和健康检查要有明确策略；当前模块启动时发现一次，运行中不做自动刷新，所以新增远端工具不会自动出现。

