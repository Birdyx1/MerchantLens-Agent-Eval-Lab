# 2.5b MCP 客户端发现工具

状态：已通过。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—20 分钟。

## 知识点

MCP 客户端先发现服务端提供的工具，再按名称调用。官方 SDK 2.x 支持 `Client(server)` 在同一进程内测试，无需监听端口。[官方文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

当前 SDK 的 `client.list_tools()` 返回 `ListToolsResult`；工具列表在 `.tools` 属性里，而不是返回值本身。

## 实践任务

新建 `src/merchant_agent/mcp_client_demo.py`，定义：

```python
async def list_tool_names(db_path: str) -> list[str]:
    ...
```

用 `create_server(db_path)` 创建服务，再用 `async with Client(server) as client` 连接；调用 `await client.list_tools()`，返回工具名称列表。`Client` 从 `mcp` 导入。本课不调用 SQL 工具，也不启动网络服务。

## 验收标准

1. 用 `anyio.run` 调用函数，返回列表中包含 `get_store_net`。
2. 读取 `ListToolsResult.tools`，不把返回对象直接当列表遍历。
3. 客户端连接正常关闭；数据库路径不作为模型工具参数。

## 面试考点与踩坑

- 工具发现与工具调用是两步；发现结果包含名称、描述和参数 Schema。
- 进程内客户端用于集成测试，后续还要验证实际传输方式。
- 不要把服务端函数的直接 Python 调用当作 MCP 协议验收。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员实现进程内客户端工具发现；`anyio.run` 返回 `get_store_net`，客户端正常退出。本课通过。
