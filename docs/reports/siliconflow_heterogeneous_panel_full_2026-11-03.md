# 阶段 6：硅基流动三模型面板六题试点（2026-11-03）

## 实验设置

使用同一固定 `judge_clarity_v1` Rubric，对[六条已经真人独立双标的虚构边界挑战](judge_challenge_calibration_2026-11-03.md)运行三模型裁判：`zai-org/GLM-5.3-Flash`、`tencent/Hy4-preview`、`Qwen/Qwen3.8-27B`。三者模型家族不同，供应商均为硅基流动。Qwen 设 `enable_thinking=false` 以避免先前默认思考模式的超时；其他模型沿用服务默认参数。参数差异需作为解释限制。

[运行器](../../src/merchant_agent/evaluation/live_siliconflow_panel_challenges.py)冻结挑战集、Rubric、人工参考分和裁判源码摘要。逐票结果、模型 ID、理由、token 与错误类型保存在私有记录 `runs/siliconflow_panels/753b0b9190534c47a6d654e29ec06bdb/results.json`。没有使用真实业务 Trial 或 Holdout。

三票齐全且至少两票同分才给多数结论；任一调用或格式校验失败则 `incomplete`，不采用剩余两票。人工参考分仅用于事后校准，未传给裁判。

## 逐题结果

| 案例 | 人工参考分 | GLM / Hy4 / Qwen | 面板状态与结论 |
| --- | ---: | --- | --- |
| `no_conclusion` | 0 | 0 / 0 / 0 | 多数 0，正确 |
| `contradictory_amounts` | 0 | 0 / 1 / 1 | 多数 1，**错误** |
| `missing_unit` | 1 | 1 / 1 / 格式或解析错误 | `incomplete`，无结论 |
| `missing_store` | 1 | 1 / 1 / 1 | 多数 1，正确 |
| `clear_fen` | 2 | 2 / 2 / 2 | 多数 2，正确 |
| `clear_conversion` | 2 | 2 / 2 / 2 | 多数 2，正确 |

18 个计划票中，17 票有效、1 票报 `ValueError`。五题可比较的多数结论中 4/5 与人工参考分一致；另 1 题没有面板结论，必须进入人工复核。成功返回票的 token 合计 **20,495**；失败调用的用量无法从本地结果获知，因此这不是完整账单成本。

## 根因与方法论

- `contradictory_amounts` 的两张 1 分票把“有结论但不够明确”置于“金额互相矛盾应为 0 分”之前，暴露 Rubric 优先级理解不一致。**多数票并不保证正确**。这条被归为裁判解释偏差，而非 Agent 结果错误。
- `missing_unit` 的 Qwen 票未通过裁判输出契约，面板没有使用剩余两票绕过三票协议。这是裁判可用性问题，不应计为分数错误；现有面板只保存 `ValueError` 类型，无法从本次记录还原具体格式错误，后续需细化安全的错误分类。
- 之前首题 GLM 曾给 `no_conclusion` 1 分，本轮给 0 分；同一模型也可能发生采样波动。六条人工构造案例规模太小，不能估计自然业务分布准确率。
- 三模型虽然不同家族，但共享同一供应商、请求路径和 Rubric，仍可能有平台故障与相关偏差。Qwen 非思考模式与其他默认模式也不是严格同参数实验。

保留原始 Rubric 和人工标签；若要澄清“金额矛盾优先判 0”，应创建 Rubric 新版本并重新双标、重跑，而不能事后修改本次结果。
