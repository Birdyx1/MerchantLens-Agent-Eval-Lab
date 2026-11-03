# 同题双版本 Harness 试点报告（2026-11-03）

## 设计与证据

固定同一 DeepSeek `deepseek-flash`、Regression 4 道已仲裁 Task、环境快照、MCP 工具与评分器；每题每版本运行 2 次。两版 Harness 仅规划提示词不同：基线为原提示词，候选显式提醒工具返回后继续遵守 JSON 契约。实验前冻结 Task、评测器、源码与提示词 SHA-256。完整私有清单：`runs/same_task_harness/42e0792349af48fca35fbb12b89c2f2d/experiment.json`；该目录另有自动生成的 `comparison.md` 与顺序轨迹 `trajectory_audit.json`，各批次可追溯到 Trial/Trace。Holdout 未参与。

| 版本 | Trial | 规则通过 | 顺序轨迹通过 | 平均总 token | 安全状态 |
|---|---:|---:|---:|---:|---|
| 基线提示词 | 8 | 8/8 | 8/8 | 633.625（8/8 有观测） | unknown |
| 工具后 JSON 提醒 | 8 | 8/8 | 8/8 | 705.125（8/8 有观测） | unknown |

通过率观测差值为 **0**，候选平均多用 **71.5 token/Trial**。16 条 Trial 的顺序轨迹均通过，实际模型 Span ID 均为 `deepseek-flash`。这满足阶段 5 首版“同一冻结任务集上的双版本比较”交付，但样本只有四题、单一净收入业务，不能证明两版真实质量相同。两批按基线后候选的顺序运行，外部服务时间漂移和模型随机性未完全控制；本报告是描述性试点，不做显著性或因果宣称。

候选没有观测质量收益且 token 成本增加，**不提升为默认 Harness**。本报告也不是 7.5 的 Model × Harness 2×2：模型轴没有变化。所有安全状态为 unknown，不得解释为安全通过。
