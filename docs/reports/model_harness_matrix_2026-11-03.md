# 阶段 7.5：真实 Model × Harness 四格试点（2026-11-03）

## 实验设计

经用户明确授权，在同一 Regression 集合四道已仲裁 `store_net` Task 上，交叉运行两个模型与两版规划提示词 Harness：`deepseek-flash`、`zai-org/GLM-5.3-Flash` × `baseline`、`explicit_json_after_tool`。每题每格重复两次，共 **32 条真实 Trial**。Task 路径和 SHA-256、模型配置、Harness 源码与提示词摘要、评估器摘要、随机种子 `20261103` 及完整调度顺序在调用前冻结。每个 `(task_id, repeat_index)` 内固定随机打乱四格顺序，减少固定运行顺序的时间偏差；两模型的本地 MCP SQL 工具与业务快照相同。Holdout 未使用。

四格运行器见[源码](../../src/merchant_agent/evaluation/model_harness_live_matrix.py)，分析器见[四格比较](../../src/merchant_agent/evaluation/model_harness_matrix.py)。机器可读私有清单：`runs/model_harness_matrix/489a0692a3e34f5396ba3a4b43466f25/experiment.json`，指向四个完整 Batch、32 条 Trial 及 Trace。所有 Trial 均正常结束；Code Trace 校验与额外顺序轨迹评测均通过。Trace 中模型实际 ID 与各格配置一致。

GLM 使用硅基流动 Chat Completions 与 JSON 模式，DeepSeek 使用 Responses 接口。故“模型轴”在本试点中实际是**模型 + 提供商接口适配 + 解码配置**的组合，不能把差值纯粹归因于基座权重。

## 四格结果

| 模型 | Harness | 结果/轨迹/整体通过 | 平均 token | 平均延迟 | 平均工具调用 |
| --- | --- | ---: | ---: | ---: | ---: |
| DeepSeek | baseline | 8/8 | 606.4 | 2708.5 ms | 1.0 |
| DeepSeek | explicit JSON after tool | 8/8 | 696.5 | 2550.5 ms | 1.0 |
| GLM | baseline | 8/8 | 848.9 | 14464.2 ms | 1.0 |
| GLM | explicit JSON after tool | 8/8 | 811.4 | 10473.1 ms | 1.0 |

每格安全状态均为 `unknown`，**不能视为安全通过**。在整体成功率上，两个 Harness 下的模型差值、两个模型下的 Harness 差值和交互差值都为 **0**；这是样本全部成功导致的观测结果，不是“模型等价”或“无交互”的证据。每题仅 2/2 成功，对应单题 Wilson 95% 区间约为 **[0.342, 1.0]**，不确定性仍很大；四题同属一种业务能力，任务层自助法在全对时退化为 `[1,1]`，不能据此宣称稳定泛化。

成本呈现不同方向：候选 Harness 相对 baseline 在 DeepSeek 上平均多 **90.1 token**，在 GLM 上平均少 **37.5 token**；两条变化的观测差为约 **−127.6 token**。不同提供商的 token 口径及价格未统一，这些只是各自 API 报告的 token 数，不能直接推出人民币成本优劣。延迟也受服务端负载和网络影响，本试点不能作因果解释。

## 结论与后续

本次完成了真正的四格同题运行和可追溯比较，验证运行器能够把模型与 Harness 两个轴分开记录。但现有任务过少、过于同质且全部达到满分，**无法识别能力差异或失败归因**。后续应扩充不同工具、反思与脏数据任务；保留同题、同快照和随机交错顺序，增加重复轮次与配对不确定性分析，再决定模型或 Harness 版本取舍。当前不推荐据此替换基座或提示词。
