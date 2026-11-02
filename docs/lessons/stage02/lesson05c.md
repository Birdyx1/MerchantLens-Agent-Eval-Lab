# 2.5c MCP 客户端调用 SQL 工具

状态：已通过。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

工具发现之后，客户端用工具名称和参数发起 `tools/call`。官方 SDK 2.x 的 `CallToolResult` 提供 `is_error` 和 `structured_content`；本项目的整数返回值位于 `structured_content["result"]`。这属于当前 SDK 返回结构，后续升级时要复测。[官方文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

## 实践任务

在 `src/merchant_agent/mcp_client_demo.py` 新增：

```python
async def call_store_net(db_path: str, store_id: str) -> int | None:
    ...
```

用 `create_server(db_path)` 和进程内 `Client`，调用 `await client.call_tool("get_store_net", {"store_id": store_id})`。若 `is_error` 为真，抛 `RuntimeError`；否则读取结构化结果的 `result` 字段并返回。不要从文本内容解析数字，也不要把 `db_path` 放进工具参数。

## 验收标准

1. 临时数据库中门店 A 返回 12000 分，B 返回 8000 分；不存在门店返回 `None`。
2. 调用参数只有 `store_id`；`is_error` 为真时不能按成功处理。
3. 通过 MCP 客户端调用，不直接调用 SQL 函数。

## 面试考点与踩坑

- `tools/list` 只证明工具可发现；`tools/call` 才覆盖协议调用链路。
- `is_error` 与 Python 异常是两种错误信号，都要考虑。
- 结构化结果比解析文本稳健，升级 SDK 时需要验证返回契约。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员完成进程内 MCP 调用；临时数据库中 A=12000、B=8000、不存在门店=None。缺失数据库时工具错误被转为 RuntimeError；SDK 会在本地日志打印服务端堆栈，后续 2.6 处理日志边界。本课通过。
