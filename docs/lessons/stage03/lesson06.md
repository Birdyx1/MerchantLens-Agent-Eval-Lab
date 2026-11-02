# 3.6 记忆与检查点

状态：已通过；[3.6a 任务线程检查点语义](lesson06a.md)、[3.6b SQLite 跨进程恢复](lesson06b.md) 已通过（教师实现）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

短期 State 保存任务执行中的消息、计划和工具观察；Checkpointer 在节点边界保存快照，便于任务内恢复。持久化与状态语义分小课验收。

## 实践任务

[3.6a](lesson06a.md)、[3.6b](lesson06b.md) 已完成；下一课进入终止与预算。

## 验收标准

各小课单独验收。

## 面试考点与踩坑

区分短期 Checkpointer、长期 Store 与评测 Trace；线程 ID 是控制面配置。

## 提交与评审记录

- 2026-11-02：3.6a 教师实现并通过，全套 pytest 85 passed。
- 2026-11-02：3.6b 教师实现 SQLite 检查点跨进程暂停与恢复，全套 pytest 86 passed。
