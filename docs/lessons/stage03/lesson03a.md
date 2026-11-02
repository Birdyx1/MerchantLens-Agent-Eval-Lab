# 3.3a 规划决策与路由契约

状态：已通过（教师实现）。

[3.3 总览](lesson03.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

ReAct 的“思考”在工程实现中应产出可执行的**决策摘要**，而不是依赖任意自然语言解析。模型给出 JSON 计划与下一动作；代码检查工具名、参数和结束条件，再由路由函数决定下一节点。模型输出是不可信输入，不能直接当作工具调用。`plan` 是本项目的显式步骤摘要，不要求也不存储隐藏推理。

## 实践产物

教师实现 `agent/planning.py`：`parse_planning_decision` 校验模型 JSON；`make_plan_node(model)` 注入 `ModelPort` 并返回异步规划节点；`route_after_plan` 返回 `tool` 或 `finish`。State 新增 `last_model_id`，节点返回 token 用量增量与一次模型消息。此课不执行工具，也不构建完整 LangGraph 图。

## 验收标准与结果

- 合法 SQL 工具决策与直接结束决策通过。
- 未注册工具、额外 `db_path`、布尔值 `limit`、超范围执行时限及空答案均拒绝。
- 模型版本与 token 用量进入状态更新；全套 pytest 60 passed。

## 面试考点与踩坑

- 规划器只建议动作，代码负责权限和参数边界。
- 路由函数只看已校验 State，不重新解析模型文本。
- `ModelPort` 与 LangGraph 节点分离，后续可固定模型版本比较不同 Harness。
- 模型调用的独立 Trace Span 和节点级错误恢复将在后续小课接入；本课尚未把模型输出落盘。

## 提交与评审记录

- 2026-11-01：教师实现并验证，本课通过。
