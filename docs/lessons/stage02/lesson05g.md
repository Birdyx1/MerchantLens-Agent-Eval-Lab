# 2.5g 跨进程 stdio 调用

状态：已通过（教师代写）。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

进程内 `Client(server)` 验证协议处理，stdio 还要验证子进程启动与消息传输。官方 SDK 用 `StdioServerParameters(command, args, env)` 描述服务进程，再交给 `Client`。[官方传输文档](https://py.sdk.modelcontextprotocol.io/client/transports/#stdio)

SDK 的 stdio 子进程只继承一小部分环境变量；本项目依赖 `PYTHONPATH=src`，因此需要在 `env` 中显式传入 `MERCHANT_DB_PATH` 与绝对 `PYTHONPATH`。不要把 Tavily Key 传给本课仅含 SQL 的服务。

## 实践任务

新建 `src/merchant_agent/mcp_stdio_smoke.py`，实现：

```python
async def smoke_stdio(db_path: str) -> int | None:
    ...
```

使用 `sys.executable` 作为命令，参数为 `-m merchant_agent.mcp_stdio`；用 `Path(__file__).resolve().parents[1]` 得到 `src` 的绝对路径并设置 `PYTHONPATH`。通过 `async with Client(StdioServerParameters(...))` 连接，先发现 `get_store_net`，再调用门店 A，返回 `structured_content["result"]`。检查 `is_error`，错误时抛 `RuntimeError`。

## 验收标准

1. 临时数据库通过真实 stdio 子进程调用，返回 12000 分。
2. 客户端能发现 SQL 工具；子进程在退出客户端上下文后关闭。
3. 不通过进程内 `Client(server)` 替代本课验证；不把数据库路径作为工具参数。

## 面试考点与踩坑

- 进程内测试与 stdio 传输测试覆盖不同故障边界。
- 子进程环境需显式配置；缺少 `PYTHONPATH` 会导致模块导入失败。
- stdout 是 MCP 协议流，服务端调试日志应写 stderr。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：应学员要求，教师实现真实 stdio 客户端脚本；临时数据库由独立 MCP 子进程读取，客户端发现并调用 get_store_net，门店 A 返回 12000 分。本课通过。
