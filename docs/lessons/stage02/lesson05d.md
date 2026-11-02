# 2.5d 暴露网页检索工具

状态：已通过（教师协助修正返回类型）。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

MCP 工具只暴露业务输入。搜索服务的具体实现由创建服务的一方注入，测试时用 `FakeSearchProvider`，真实运行时用 `TavilySearchProvider`。这样 MCP 参数不包含 API Key 或提供商配置。官方 SDK 从工具函数签名生成参数 Schema。[官方文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

## 实践任务

修改 `src/merchant_agent/mcp_server.py`：

1. 将工厂签名改为 `create_server(db_path: str, search_provider: SearchProvider | None = None) -> MCPServer`，保留原 SQL 工具行为。
2. 仅当传入 `search_provider` 时注册 `search_web(query: str, limit: int) -> dict` 工具。
3. 工具调用 `search_provider.search(query, limit)`，然后调用 `make_search_snapshot(query, results)` 返回快照。不要把 API Key、提供商对象或数据库路径暴露为 MCP 参数。

## 验收标准

- 不传搜索服务时，旧的 SQL 工具发现和调用仍通过。
- 传入固定模拟搜索服务时，客户端发现 `search_web`，参数 Schema 只有 `query` 和 `limit`。
- 客户端调用后从 `structured_content` 得到查询词和结果快照；无需真实联网。
- 搜索异常保持为工具错误，不返回空结果伪装成功。

## 面试考点与踩坑

- 依赖注入让同一个 MCP 服务可在测试与真实配置间切换。
- MCP 参数 Schema 是模型可控制的输入边界，密钥和服务配置不在其中。
- 工具错误与空搜索结果必须区分；完整错误分类与 Trace 在 2.6 继续。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员已完成注入与注册，旧 SQL 行为、工具发现及参数 Schema 均通过；MCP SDK 2.3.0 将泛型 `dict` 返回放入文本内容，`structured_content=None`。用 `TypedDict` 明确返回类型的本地探针可得到结构化内容。请在 `search_snapshot.py` 定义 `SearchSnapshot(TypedDict)`，字段 `query: str` 与 `results: list[dict[str, str]]`；让 `make_search_snapshot` 和 MCP `search_web` 的返回注解都改为 `SearchSnapshot`。运行时数据结构保持原样，等待复评。
- 2026-11-01：按学员要求，教师补充 `SearchSnapshot(TypedDict)` 并更新两个返回注解；进程内 MCP 客户端得到结构化快照，参数 Schema 仅有 query 和 limit，原 SQL 工具仍返回 12000 分。本课通过。
