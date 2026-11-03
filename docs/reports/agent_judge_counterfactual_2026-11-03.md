# 阶段 6.4：受控错误轨迹的 Agent 裁判验证（2026-11-03）

## 设计

以公开示例 Task `store_net_a_001` 和示例订单文件构造一条**人工反事实轨迹**：门店 A 的真实净收入为 12000 分；轨迹中的 `tool.get_store_net` 返回 13000 分，最终回答也写成 13000 分。该轨迹不是被测 Agent 自然生成，保存在 `runs/trials` 私有目录，不进入 Golden、Regression、Badcase 或 Holdout。

[构造与运行入口](../../src/merchant_agent/evaluation/live_agent_judge_counterfactual.py)先让正式 Code Evaluator 评分：Trace 格式及跨记录校验通过；`correct_sql_call=true`、`answer_grounded=true`，但 `amount_correct=false`，所以整体 `passed=false`。这刻意覆盖“回答与错误工具返回相符，但业务真值不符”的情况。

随后使用真实硅基流动 `zai-org/GLM-5.3-Flash` Agent 裁判。裁判能看到人工轨迹与回答，只能请求受控工具；示例订单文件仍在本地复算。私有机器记录：`runs/trials/f38060dc5d7942e68e693c6d7d45d961/agent_judge_counterfactual.json`。

## 逐步结果

| 步骤 | 动作 | 观察或裁决 |
| ---: | --- | --- |
| 1 | `verify_store_net(store_id="A")` | 本地独立复算 12000 分 |
| 2 | `finish(verdict="fail")` | 说明 Trace 和回答均为 13000 分，但与冻结订单真值不符 |

Agent 裁判与 Code 均判失败；`requires_human_review=false`。Judge 总 token 为 **1,157**。本次模型没有调用 `inspect_span`，但完整人工轨迹已在初始输入中供其读取。它没有把“工具与回答一致”误判为业务正确。

## 方法论边界

这是**有意构造的负控制**，用于验证裁判工具核验链路和冲突解释；不能作为真实 Agent 错误分布中的命中率。下一步仍需在授权边界内收集自然失败 Trial，覆盖错误工具选择、错误参数、工具返回异常、提示注入和裁判动作越界。这个反例也提示结果指标与轨迹指标应分开：回答可扎根于工具结果，却仍因工具结果错误而不正确。
