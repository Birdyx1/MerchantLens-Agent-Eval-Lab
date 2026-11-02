# 3.11 Agent 端到端轨迹验收

状态：已通过（教师实现，2026-11-02）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

端到端验收需要证明答案来自工具证据，而非模型碰巧猜中。本课的测试模型只有看到 SQL 工具观察后才给出数值答案；同一次运行形成“模型规划 → MCP SQL → 模型回答 → 根请求”四条 Span。

## 实践任务

用本地 SQLite 数据库和 MCP 客户端运行完整 LangGraph 图；从最终 State 和 JSONL Trace 分别检查答案、调用顺序、父子关系及模型用量。

## 验收标准

- SQL 返回 12000 分，第二次模型调用根据实际观察生成答案。
- 两条模型 Span、一条工具 Span、一条根 Span 共享 Trace ID，均通过 JSON Schema 与当前跨记录校验。
- `step_count=3`，token 用量等于两次模型调用之和；全套 pytest 通过。

## 面试考点与踩坑

这个测试证明 Harness 能把工具观察送回模型，也证明 Trace 可串起完整路径。另用 DeepSeek 真实模型做一次烟雾测试，证明这次请求选对 SQL 工具并根据观察回答；不能把单次成功当作模型稳定成功率。当前通用 `validate_trace` 只检查 Trace ID 和 Span ID，完整轨迹语义还需后续评测器校验。

## 提交与评审记录

2026-11-02：教师实现；新增 1 个端到端测试，全套 pytest 113 passed。

2026-11-02：真实 DeepSeek + MCP SQL 烟雾测试成功：2 条模型 Span、1 条 SQL Span、1 条根 Span，最终答案包含 12000 分；四条 Span 通过 Schema 与基础跨记录校验。Trace 存于本地 Git 忽略的 `runs/`。写盘器权限加固后全套 pytest 115 passed。
