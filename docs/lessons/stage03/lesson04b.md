# 3.4b 观察后再规划的有界循环

状态：已通过（教师实现）。

[3.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

ReAct 不停在“调用工具”：工具观察要作为新消息进入 State，再回到规划节点。LangGraph 用条件边实现循环，节点仍只返回局部更新。循环必须有退出条件；预算耗尽时显式记录原因，不伪造最终答案。

## 实践产物

教师新增 `build_observation_loop_graph`：`START → plan`；规划选择工具进入 `act`，工具返回后在预算内回到 `plan`；规划给出答案或步骤预算耗尽时结束。State 新增 `termination_reason`，`completed` 表示有最终答案，`max_steps` 表示预算耗尽。`max_steps` 是本项目的步骤预算，后续 3.7 再补成本、时间和框架递归限制协调。

## 验收标准与结果

- 真实进程内 MCP SQL 工具观察进入第二次模型调用，模型可读取工具结果并生成答案。
- 重复工具决策在 `max_steps` 为 1、2、3 时均按预算停下；未执行的工具不产生 Span。
- 预算耗尽时 `final_answer` 为 `None`，`termination_reason=max_steps`；全套 pytest 71 passed。

## 面试考点与踩坑

- State 中的工具消息由 `messages` reducer 追加，下一次规划可见；不要把完整历史重新返回给 reducer。
- 步骤预算是应用层限制；LangGraph 自身还有递归步数限制，高预算时需要协调配置。
- 本课只覆盖工具正常返回的观察循环；MCP 异常仍会中断图，故障反思与有界重试在 3.5。

## 提交与评审记录

- 2026-11-02：教师实现并验收，本课通过。
