# 5.1 Trial 与环境重置

状态：基础 Trial 执行契约已通过（教师实现，2026-11-02）；真实模型与 MCP 运行器接线待补。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：Trial 是最小可比较单位

一次 Trial = **一个固定 Task × 一个模型版本 × 一个 Harness 版本 × 一份独立环境快照 × 一次 Agent 运行**。后续重复试验、版本对比和置信区间都建立在 Trial 上。只记录最终答案无法解释“答对但工具链路错误”；因此 Trial 必须关联 Trace ID 和完整轨迹。Anthropic 将 agent eval 的 task、trial、grader 区分开，并强调多次运行与环境状态；本项目的文件字段和目录是工程取舍。[Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

环境重置不是把 Python 变量清零。本项目的 SQL 环境以冻结 CSV 为输入，**每次重建全新 SQLite**；Agent 用全新的 `initial_state`、`trace_id` 和 LangGraph `thread_id`。运行前后计算数据库哈希；若工具或测试代码改写数据库，该 Trial 标记 `contaminated`，不能当作普通结果参与比较。网页检索与外部模型仍可能随时间变化，未来应记录响应快照、模型配置和种子，不能仅凭数据库重置宣称完全可复现。

评测流量标记保留在控制面 `traffic`，Agent 只接收用户请求。Trial 的任务文件哈希、环境哈希、模型与 Harness 版本、时间、终止原因、Trace 路径和错误类型落到 `runs/trials/<trial_id>/trial.json`；失败也落盘，避免只统计成功样本造成幸存者偏差。

## 实践目标、输入输出

教师实现 [run_trial](../../../src/merchant_agent/evaluation/trial.py)。输入：已登记 Task 路径、项目根目录、异步 `invoke` 适配器、模型/Harness 版本，可选时限。适配器收到新初始状态、独立数据库路径、Trace 路径和 thread ID，负责调用现有 LangGraph/MCP。输出：结构化 Trial 记录及独立 SQLite、Trace 文件。

状态语义：`completed` 仅表示 Agent 自报完成且有同 Trace ID 的非空轨迹；`incomplete` 是正常返回但未完成；`error`、`timeout` 是执行失败；`missing_trace` 是自报完成却缺少轨迹；`contaminated` 是数据库前后哈希不同。**本课只做轨迹存在与 ID 的入口检查，Span Schema 和跨 Span 语义在后续评分流水线验证**。不能把 `completed` 直接等同于任务成功，5.2 才核验结果与过程。

## 验收标准

- 两次运行的数据库初始数据相同，Trace ID、thread ID、输出目录不同。
- 数据库被修改时为 `contaminated`；抛异常仍保存 Trial 记录；无 Trace 不能是 `completed`。
- 控制面标记不在 Agent 请求中；记录权限为 `600`。

## 面试考点与踩坑

问：为什么要每次重建数据库？答：前一个 Trial 的工具副作用可能影响下一个 Trial，导致顺序相关偏差。问：为什么 `completed` 不等于成功？答：Agent 结束只说明执行流程结束，答案、工具参数和证据链要由 grader 校验。问：为何保存失败 Trial？答：否则成功率分母被缩小。问：一个环境哈希够吗？答：不够；外部检索、模型版本、提示词、工具版本也要冻结或记录。

## 提交与评审记录

2026-11-02：教师实现单次 Trial 契约、数据库重建、隔离身份、污染与缺 Trace 状态；专项测试 4 个，全套 pytest 150 passed。真实 DeepSeek/MCP 运行器尚未接入本模块。
