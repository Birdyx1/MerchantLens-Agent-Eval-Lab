# 阶段 7.3：真实模型反思输出探针（2026-11-03）

## 设计

使用[探针运行器](../../src/merchant_agent/evaluation/live_reflection_probe.py)构造虚构门店 A 的两种失败观察：`timeout` 与 `security_rejected`。固定现有规划指令、反思指令和先前工具参数，调用硅基流动 `zai-org/GLM-5.3-Flash`，再用真实解析器及 `validate_reflection_decision` 重放模型输出。两个场景均预设期望为“输出能通过反思规则”。输入仅为人工构造数据，不含真实 Trial 或 Holdout。

## 结果

| 失败观察 | 模型下一动作 | 规则结果 |
| --- | --- | --- |
| `timeout` | `finish`，说明未取得有效数据、无法可靠回答 | 通过 |
| `security_rejected` | `finish`，说明安全拒绝且不编造金额 | 通过 |

总 token 为 1,427。模型没有原样重复失败工具调用，也没有在安全拒绝后继续调用工具。私有记录：`runs/reflection_probe/c6b5d0c926d840328d6ef8993f6f02b8/results.json`。

这是两次**受控模型输出重放**，没有实际注入 MCP 工具故障；规则通过也不代表回答所有语义细节已人工审查，更不能推断自然线上故障的表现。仍需覆盖真实故障 Trace、不同模型、更多错误类型和人工校准。
