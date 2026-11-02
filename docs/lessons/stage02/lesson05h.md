# 2.5h 三工具 stdio 运行配置

状态：已通过（教师代写）。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

MCP 服务的工具暴露范围由启动配置决定。SQL 路径、Tavily Key 和 Python 执行开关是服务端配置，模型调用时不能修改。stdio 子进程默认不会继承所有环境变量；需要由宿主显式传入所需变量。[官方传输文档](https://py.sdk.modelcontextprotocol.io/client/transports/#stdio)

## 实践任务

修改 `src/merchant_agent/mcp_stdio.py` 的 `main()`：

1. 保留 `MERCHANT_DB_PATH` 必填校验。
2. 若 `TAVILY_API_KEY` 存在且非空，创建 `TavilySearchProvider()` 并传给 `create_server`；否则不暴露搜索工具。
3. `MERCHANT_ENABLE_PYTHON` 仅允许 `"0"`、`"1"`，缺省为 `"0"`；其他值抛 `ValueError`。为 `"1"` 时将已有 `run_python` 作为 `python_executor` 传入；否则不暴露 Python 工具。
4. 不打印 Key，不将 Key 或 Docker 配置放入 MCP 工具参数。

## 验收标准

- 模拟环境下检查三种配置：仅 SQL；SQL+搜索；SQL+搜索+Python，工具发现符合预期。
- 无效 Python 开关在启动前报错；导入模块时仍不运行服务。
- 不在本课调用真实 Tavily 或 Docker；后续做完整三工具 stdio 烟测。

## 面试考点与踩坑

- 工具注册与服务启动是两个边界；配置在服务端，调用参数由模型控制。
- Python 执行工具使用明确开关，避免意外暴露。
- 不要把 Tavily Key 打印到 stdout；stdio 的 stdout 属于协议流。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：应学员要求，教师完成 stdio 三工具配置；配置矩阵、非法开关及缺失数据库校验通过。真实子进程中三种工具组合发现通过，SQL 工具调用返回 12000 分。搜索和 Python 未在本课通过 stdio 实际调用。
