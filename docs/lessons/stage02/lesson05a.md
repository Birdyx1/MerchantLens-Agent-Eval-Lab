# 2.5a 暴露 SQL 工具

状态：已通过。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

MCP 的工具由服务端注册，客户端再发现和调用。官方 SDK 2.x 使用 `from mcp.server import MCPServer` 和 `@server.tool()`；工具名、说明及参数 Schema 来自 Python 函数。[官方文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

数据库路径是部署配置，不能让 Agent 在工具调用参数里随意指定。服务端固定路径，模型只提供 `store_id`。

## 实践任务

新建 `src/merchant_agent/mcp_server.py`，定义 `create_server(db_path: str) -> MCPServer`：

1. 创建名为 `merchant-tools` 的 `MCPServer`。
2. 在函数内部注册一个名为 `get_store_net` 的工具，参数仅 `store_id: str`，返回 `int | None`，有简短文档字符串。
3. 工具内部调用已有 `merchant_agent.tools.sql.sql_query.get_store_net(db_path, store_id)`；`db_path` 由外层固定，不作为 MCP 工具参数。
4. 返回服务对象。本课只创建服务，不启动端口或运行容器。

## 验收标准

- `create_server` 能返回 `MCPServer`，工具可以被 SDK 发现。
- 工具参数 Schema 只有 `store_id`，没有 `db_path`。
- 使用临时测试数据库调用工具能得到已知金额；后续小课再通过 MCP 客户端完整调用。

## 面试考点与踩坑

- MCP 服务是工具边界，Agent Harness 仍负责模型决策和调度。
- 工具参数要限制在模型真正需要控制的业务输入；数据库路径属于服务配置。
- SDK 1.x 的 `FastMCP` 示例和当前安装的 2.x `MCPServer` 接口不同，按项目锁定版本编写。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员完成服务注册；使用官方 SDK 2.3.0 的进程内客户端发现工具，确认输入 Schema 只有 `store_id`，临时数据库调用门店 A 返回 12000 分。本课通过。首次验收脚本误把 `ListToolsResult` 当列表，修正为读取 `.tools` 后通过；服务代码无缺陷。
