# 3.7a 步骤、尝试与 token 预算

状态：已通过（教师实现）。

[3.7 总览](lesson07.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

Agent 终止预算至少覆盖步骤数、工具尝试次数与模型 token 用量。项目的 `max_steps` 统计规划和工具行动；`max_tool_attempts` 限制同一操作的自动重试；`max_total_tokens` 限制累计模型用量。LangGraph 的 `recursion_limit` 是框架 super-step 上限，不能直接当项目步骤预算，两者应由运行入口协调。[官方递归上限说明](https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit)

## 实践产物

教师在 State 中加入 `max_total_tokens`，规划后检查累计输入与输出 token；达到阈值时进入 `tokens` 终止节点，`termination_reason=max_tokens` 且 `final_answer=None`。新增 `run_agent` 入口，根据项目 `max_steps` 设置足够高的框架 `recursion_limit`，避免框架先于业务预算截断。

## 验收标准与结果

- 模型一次调用后达到 token 阈值，工具节点不执行，保留真实 token 用量与 `max_tokens` 原因。
- `max_steps=30` 的循环由项目预算正常结束，不抛 `GraphRecursionError`。
- 无效 token 预算在入口被拒绝；全套 pytest 91 passed。

## 面试考点与踩坑

- 模型返回后才能知道本次实际 token 用量，当前阈值会阻止**后续**动作，不能保证单次调用不超额；硬限额需模型适配器传入输出上限并处理提供商差异。
- token 超限时即使模型文本含答案，也不把它标为成功最终答案；评测可以独立统计预算违规。
- 本课未覆盖墙钟时间、货币成本和外部取消；下一小课继续。

## 提交与评审记录

- 2026-11-02：教师实现并验收，本课通过。
