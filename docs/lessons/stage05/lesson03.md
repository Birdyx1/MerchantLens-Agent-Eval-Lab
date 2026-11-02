# 5.3 四类指标

状态：指标计算代码已通过（教师实现，2026-11-02）；真实批量样本与安全裁判待补。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：四类指标回答不同问题

单一成功率会掩盖过程错误、成本激增和安全违规。本课把一条 Trial 拆成四类：

| 类别 | 本课指标 | 问题与分母 |
|---|---|---|
| 结果 | `result_success`、`overall_success` | 金额是否正确、三条 Rubric 是否全过；聚合时以**全部 Trial** 为分母，包括失败与超时 |
| 轨迹 | `trajectory_success` | 正确门店工具调用与答案证据链是否同时通过 |
| 成本 | 输入/输出/总 token、根 Span 延迟、工具调用次数 | 从 Trace 观测；缺字段用 `null`，均值同时报告 `observed` 数量 |
| 安全 | `security_rejections`、`safety_status` | 拒绝次数是观察信号；安全结论只有 `pass`、`violation`、`unknown` |

字节 Data Agent 的分层评测思路提醒我们不要只看终局；Anthropic 也建议同时观察任务结果、轨迹和开销。上述字段、分母与安全门禁是本项目定义，并非博客统一标准。[Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

**安全一票否决**：只要有已确认 `violation`，聚合 `release_gate=fail`；没有违规但存在 `unknown`，门禁为 `unknown`，不能报安全通过。工具返回 `security_rejected` 只能说明某次防线起效，不代表整个 Trial 安全。真正的安全判定在阶段 8 的 Negative Set 和专门裁判接入。

## 实践目标、输入输出

教师实现 [trial_metrics 与 aggregate_metrics](../../../src/merchant_agent/evaluation/metrics.py)。输入为同一 Trial 的记录、5.2 Code Evaluator 结果、项目根目录和可选安全结论。先核对 Trial ID、Task ID、Trace 文件哈希，再从可信 Trace 汇总 token、延迟与工具调用。输出单 Trial 指标字典及批量聚合字典。成本平均值只用实际观测值，同时给出 `observed`，避免把缺失当 0；结果率仍以全部 Trial 为分母，避免幸存者偏差。

本课的安全结论由调用方显式传入；默认 `unknown`。没有真实安全裁判或人工复核时不得传 `pass`。当前尚未有真实批量评测，因此不报告项目成功率、平均成本或安全通过率。

## 验收标准

- 正确样本能独立得到四类指标；答案正确但轨迹失败不能算总体通过。
- token 缺失时为未知，均值的观测样本数正确；失败 Trial 仍在结果分母。
- 一次安全拒绝不自动变成安全通过；一条已确认违规使发布门禁失败。

## 面试考点与踩坑

问：为何成本均值必须带样本数？答：部分 Trial 无 Trace，忽略它们会让均值代表的总体发生变化。问：`security_rejected` 是安全违规吗？答：不是，它是一次拒绝动作；还需判断是否有成功绕过。问：结果正确、轨迹错误怎么办？答：分项显示结果通过、轨迹失败，总体失败，供后续根因归类。问：为何安全未知不能当通过？答：缺少裁判证据，不能推断没有风险。

## 提交与评审记录

2026-11-02：教师实现四类单 Trial 指标与聚合、安全未知/违规门禁；专项测试 5 个，全套 pytest 163 passed。
