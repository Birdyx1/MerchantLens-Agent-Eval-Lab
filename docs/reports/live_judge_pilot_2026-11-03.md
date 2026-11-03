# 阶段 6：真实 LLM 裁判小样本试点（2026-11-03）

## 方法

- 对象：冻结 Regression 批次 `5c34fc4ea2cc4a0db191596f6dd04ecd`，每题取 `repeat_index=0`，共 4 条真实 Trial。原始 Trial 和 Code 评分未被修改。
- 裁判：DeepSeek `deepseek-flash`；固定 `judge_clarity_v1` Rubric（SHA-256：`ce3e8e38720137867722c9b8d174c708b476733d5cef2847bd747645f41fb804`）。仅评最终回答的对象、金额、单位是否表达清楚，不能替代金额真值、轨迹或安全裁判。
- 审计：运行器保存批次、Trial、Rubric、裁判源码摘要，逐条保存模型 ID、评分理由和 token 用量。私有原始记录：`runs/judge_pilot/c1d1e92347484bb4aef75ef8960338c3/results.json`。
- 样本选择在调用前固定为每题首轮，未因分数筛选；Holdout 未参与。

## 结果

| 题目 | Code 通过 | 清晰度分数 | Judge token |
| --- | --- | ---: | ---: |
| `coverage_store_net_p_001` | 是 | 2 | 377 |
| `coverage_store_net_q_001` | 是 | 2 | 384 |
| `pilot_store_net_e_001` | 是 | 2 | 388 |
| `pilot_store_net_g_001` | 是 | 2 | 391 |

总 Judge token 为 1,540；四条裁判均返回有效 JSON 和具体理由。当前样本全为 Code 通过且表达清楚，不能由此估计 Judge 对失败答案的识别率，也不能计算人与 Judge 的一致率。

## 下一步验收

1. 在同一固定 Rubric 下加入表达不清、格式不合格和金额矛盾的冻结 Trial，报告各分数层的表现。
2. 由两位真人盲审抽样 Trial；分歧由第三人仲裁；再计算原始双标一致率、Judge 与人工标签一致率和混淆矩阵。
3. 三裁判投票与 Agent 裁判分别运行并记录分歧、工具核验与额外成本。相同模型的不同调用实例不等于独立模型家族。
