# 阶段 6：单裁判人工校准试点（2026-11-03）

## 样本与核验

对[真实 LLM 裁判试点](live_judge_pilot_2026-11-03.md)中的四条 Regression Trial 进行人工盲审。`reviewer_one`、`reviewer_two` 各提交四份标签。校准脚本验证每份记录的 reviewer ID、Trial ID、Task ID、Trial SHA-256、Rubric SHA-256、分数与理由，并核对原始 Trial 文件摘要；原始标签使用独占创建，不能覆盖。

盲审命令只展示固定 Rubric 与最终回答，不展示 Judge 或 Code 分数。参与者于 2026-11-03 确认：`reviewer_one`、`reviewer_two` 由两位真人独立盲审，未互看对方理由或 Judge 结果。这是**参与者确认的独立双标证据**；当前文件记录本身不能技术性证明真人身份或隔离过程。两份理由文本高度相似，后续应加强独立账号和访问审计。

私有机器可读记录：`runs/judge_pilot/c1d1e92347484bb4aef75ef8960338c3/calibration.json`。生成逻辑：[校准模块](../../src/merchant_agent/evaluation/single_judge_calibration.py)。

## 结果

| 指标 | 本次记录 |
| --- | ---: |
| Trial 数 | 4 |
| 双份标签原始同分率 | 4/4 = 100% |
| Judge 与同分标签精确一致率 | 4/4 = 100% |
| 0 / 1 / 2 分参考标签分布 | 0 / 0 / 4 |
| 需第三人仲裁 | 0 |

两位真人标签与 Judge 均给 2 分。这个 100% **不能作为 Judge 总体准确率**：样本仅四条、来自同一批次且全部是清晰成功答案，没有 0/1 分、含糊表达或金额矛盾的判别压力。也没有三裁判分歧数据。需补齐失败/边界样本后开展更有代表性的校准。
