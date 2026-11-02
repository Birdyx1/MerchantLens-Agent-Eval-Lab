# 3.4a MCP 工具行动节点

状态：已通过（教师实现）。

[3.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

ReAct 的行动节点消费**已校验**的工具选择和参数，调用 MCP 后把观察结果写回 State，供后续模型决策使用。工具实际执行与客户端 Trace 包装在阶段 2 已完成，LangGraph 节点负责分派和状态更新。每次工具调用有独立 Span；同一逻辑操作的重试沿用 `operation_id`，递增 `tool_attempt`。

## 实践产物

教师新增 `agent/action.py` 的 `make_tool_node(client, trace_path)`。节点再次校验工具名与参数，分派到 SQL、搜索或 Python 的观测调用，返回 `last_tool_result`、一条工具消息、尝试序号和步骤增量。规划节点先在 State 中创建 `operation_id`，行动节点只读取它；这样工具抛错时，操作 ID 已存在于上一步的 State 更新中。

## 验收标准与结果

- 同一 LangGraph 图通过真实**进程内** MCP 协议调用三类工具；搜索与 Python 使用注入的模拟依赖。
- SQL 成功、搜索成功和 Python 程序错误均形成结构化观察，类别与工具 Span 一致。
- 状态被篡改为带 `db_path` 的工具参数时，行动前拒绝调用；全套 pytest 67 passed。

## 面试考点与踩坑

- 模型规划校验和行动前校验是两道不同边界：后者防止 State 被其他节点错误改写。
- MCP 调用成功不代表 Python 程序成功；`program_error` 是有效观察，供反思节点处理。
- MCP 传输异常目前会在留下工具 Span 后继续抛出，整轮图中断；失败尝试序号尚未更新到 State。下一课设计受控恢复，不应吞掉 Trace 写盘失败。

## 提交与评审记录

- 2026-11-02：教师实现并验收；下一小课补观察后的规划循环。
