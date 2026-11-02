# 3.2 短期状态定义

状态：已通过（教师实现）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

LangGraph 的 State 是节点共享的数据结构；节点通常返回局部更新，框架按各字段的 reducer 合并。项目用 `TypedDict` 定义 State：`messages`、步骤数、重试数和 token 用量使用加法 reducer；计划、工具选择、最近结果与最终答案使用默认覆盖语义。这样节点只提交增量，无需复制整个状态。[官方 State 与 Reducer 文档](https://docs.langchain.com/oss/python/langgraph/graph-api#state)

## 实践任务

教师实现 `src/merchant_agent/agent/state.py` 的 `AgentState` 与 `initial_state`，并用最小 LangGraph 图验证节点更新语义。State 保存原始任务数据、Trace 关联 ID、消息历史、规划与工具结果、成本和步骤预算。本课不调用模型或 MCP 工具。

## 验收标准

1. 初始状态包含任务、Trace、根 Span、用户请求、预算和空的运行字段。
2. 最小图的节点仅返回局部更新；消息、步骤和 token 用量正确累加。
3. 空请求和无效 `max_steps` 被拒绝；全套 pytest 52 passed。

## 面试考点与踩坑

Reducer 决定“追加”还是“覆盖”；向 `messages` 返回完整历史会重复追加。State 应存原始数据，提示词在节点中按需构造。`max_steps` 只是预算字段，真正的终止判断将在 3.7 接入。

## 提交与评审记录

- 2026-11-01：教师实现并验收。LangGraph 1.2.19 已安装并锁定在 `uv.lock`；全套 pytest 52 passed。首次测试使用 `request` 参数名与 pytest 内置 fixture 冲突，改为 `user_text` 后通过。
- 2026-11-01：按学员要求补充 `AgentState` 的中文注释，解释 Trace 关联、原始请求、追加与覆盖、增量计数和入口校验；本课 5 个测试复跑通过。
