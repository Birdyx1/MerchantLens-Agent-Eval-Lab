# 3.6a 任务线程检查点语义

状态：已通过（教师实现）。

[3.6 总览](lesson06.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

LangGraph Checkpointer 保存某个 `thread_id` 的图状态快照，支持查看历史与后续恢复；Store 则面向跨线程的长期数据。本项目的 `AgentState` 属于任务内短期记忆。`thread_id` 是运行配置中的任务线程标识，`trace_id` 是评测 Trace 标识，两者用途不同。[官方持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)

## 实践产物

教师给 `build_observation_loop_graph` 增加可注入 `checkpointer` 参数，以 `graph.compile(checkpointer=...)` 组装。测试使用官方 `InMemorySaver`：两个任务线程分别运行，读取 `aget_state` 与 `aget_state_history`，确认状态隔离和历史存在；不传 `thread_id` 时运行失败。

## 验收标准与结果

- `task-a`、`task-b` 的最终答案和 Trace ID 互不混淆。
- 同一任务线程可读取多个检查点；缺少 `thread_id` 被拒绝。
- 全套 pytest：85 passed。

## 面试考点与踩坑

- Checkpoint 是可恢复的**运行状态**；项目 JSONL Trace 是评测与审计证据，不能互相替代。
- 当前 `InMemorySaver` 只用于语义验证，进程重启后丢失；下一小课接文件型持久化实现。
- 本项目暂按“一个任务一个 thread_id”使用；把多个独立任务塞进同一线程会累加步骤与消息，需先设计任务重置边界。

## 提交与评审记录

- 2026-11-02：教师实现并验收，本课通过。
