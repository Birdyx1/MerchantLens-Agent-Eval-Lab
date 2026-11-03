# 阶段 6.4：真实 Agent 裁判证据核验试点（2026-11-03）

## 对象与边界

经用户明确授权，选取已冻结 Regression 批次 `5c34fc4ea2cc4a0db191596f6dd04ecd` 中 `pilot_store_net_e_001` 的首轮 Trial，交由硅基流动 `zai-org/GLM-5.3-Flash` 裁判。发送给模型的内容限定为完整 Trace、最终回答、Task ID 与目标门店 ID；订单 CSV 不上传，只由评测侧工具在本地复算。

运行器在调用前验证批次、Task 和 Trial 身份及 SHA-256，Agent 裁判再次检查 Code 评估的 Trace 合法性、Trace 路径、摘要、大小与非空内容。裁判最多四步，只能 `inspect_span`、`verify_store_net`、`finish`；必须成功执行 `verify_store_net` 后才能裁决。原始私有记录：`runs/agent_judge_pilot/df2b4f08306e4d1db0ea592aa4e69d46/result.json`。实现见[Agent 裁判](../../src/merchant_agent/evaluation/agent_judge.py)和[真实运行入口](../../src/merchant_agent/evaluation/live_agent_judge_pilot.py)。

## 逐步结果

| 步骤 | 裁判动作 | 评测侧观察 |
| ---: | --- | --- |
| 1 | `verify_store_net(store_id="E")` | 冻结订单本地复算结果为 11500 分，并附环境文件摘要 |
| 2 | `finish(verdict="pass")` | 理由指向复算值、Trace 工具值和最终回答的一致性 |

冻结 Trace 的 `tool.get_store_net` Span 返回门店 E 的 `result_fen=11500`，最终回答为 11500 分（115.00 元）；Code 评分为通过。Agent 裁判给 `pass`，与 Code 一致，`requires_human_review=false`。Judge token：输入 2,200，输出 358，合计 **2,558**。

## 解释与限制

本次是真实模型按动作协议请求工具、接收独立复算观察后再裁决，满足本项目的**有界 Agent 裁判**验收。它在初始输入中读取了完整 Trace，但**没有主动调用 `inspect_span`**；不能把这次运行描述成逐 Span 工具核验。一个正例也不能证明它能识别错误链路、提示注入或错误最终答案。下一步应在保持原始证据不变的条件下，用受控错误轨迹和真实失败 Trial 分别测试工具选择、拒绝越界与冲突升级。
