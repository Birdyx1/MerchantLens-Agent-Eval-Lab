# 3.3b LangGraph 条件边与一轮图

状态：已通过（教师实现）。

[3.3 总览](lesson03.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

`add_conditional_edges` 根据路由函数的返回值选择下一节点。规划节点输出已校验的 State 更新；路由函数只读 State，返回 `tool` 或 `finish`。图通过 `compile()` 后才能调用。此处把行动节点作为依赖注入，下一课可以接真实 MCP，而不改规划器。[LangGraph 官方条件边说明](https://docs.langchain.com/oss/python/langgraph/graph-api#conditional-edges)

## 实践产物

教师新增 `agent/graph.py` 的 `build_single_turn_graph(model, tool_node)`：`START → plan`，规划后 `tool → act`、`finish → END`，行动后到 `END`。这是一轮规划和可选行动；工具分支结束时可能尚无最终答案，后续反思循环会继续运行。

## 验收标准与结果

- 真实编译的 LangGraph 图，合法工具决策进入行动节点，状态增量正确累计。
- 结束决策跳过行动节点；非法工具决策在行动前报错。
- 全套 pytest：63 passed。

## 面试考点与踩坑

- Node 负责工作，Edge 负责下一步；路由不应再次解析原始模型文本。
- `tool_node` 注入让 Harness 与 MCP 工具执行解耦。
- 本课未接真实 MCP，也未形成反思重试循环；不应把一轮图称为完整 ReAct Agent。

## 提交与评审记录

- 2026-11-02：教师实现并验证，本课通过。
