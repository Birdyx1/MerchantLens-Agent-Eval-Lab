# 3.6b SQLite 检查点跨进程恢复

状态：已通过（教师实现）。

[3.6 总览](lesson06.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

检查点只有在进程退出后仍能读取，才具备持久化恢复能力。LangGraph 的 `AsyncSqliteSaver` 提供本地文件型检查点；`interrupt_before=["act"]` 可在工具调用前暂停，重新启动后用同一 `thread_id` 从保存的位置继续。SQLite 适合本地验证和轻量部署，高并发生产场景应评估 PostgreSQL 等后端。[官方 SQLite 实现](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-sqlite/README.md) · [官方持久化说明](https://docs.langchain.com/oss/python/langgraph/persistence)

## 实践产物

教师引入 `langgraph-checkpoint-sqlite`，给图工厂增加可选 `interrupt_before`。测试辅助脚本在两个独立 Python 进程中运行：首进程在 `act` 前暂停并关闭 SQLite 连接；次进程重新打开检查点，用 `ainvoke(None, config)` 恢复，调用进程内 MCP SQL 工具并完成答案。测试设置 `LANGGRAPH_STRICT_MSGPACK=true`，只处理本项目的内置数据类型。

## 验收标准与结果

- 首进程检查点的 `next=["act"]`，工具尚未执行、无工具 Trace。
- 次进程从相同 `thread_id` 恢复，SQL 返回 12000 分，最终答案形成；Trace ID 保持一致，工具 Span 落盘。
- 全套 pytest：86 passed。

## 面试考点与踩坑

- `InMemorySaver` 只在进程存活期间有效；SQLite 文件可跨进程重启读取。
- 恢复位置在节点边界。对有副作用的工具，仍需幂等键或去重机制，不能仅凭检查点保证“恰好执行一次”。
- 本课 SQLite 仅验证本地持久化，不宣称达到高并发生产部署标准；检查点数据库需要访问控制与保留期。项目运行时也应配置严格反序列化策略。
- Checkpoint 里的 State 不替代项目 JSONL Trace；后者用于评测、归因和审计。

## 提交与评审记录

- 2026-11-02：教师实现并验收，本课通过。
