# 阶段 6：清晰度裁判边界挑战（2026-11-03）

## 方法

为补齐原先四条真实 Trial 全部为 2 分的问题，运行[固定挑战集](../../fixtures/judge_clarity_challenges_v1.json)：六条**人工构造、虚构门店**的最终回答，设计分数 0/1/2 各两条。它们不是 Agent 产生的 Trial，不进入 Golden、Regression、Badcase 或 Holdout，也不用于计算业务成功率。

在调用前固定挑战集与 `judge_clarity_v1` Rubric 摘要。真实 DeepSeek `deepseek-flash` 只接收固定 Rubric 和虚构回答。运行记录保存在私有目录 `runs/judge_challenges/9bb83c88363545acaaf41a646543785a/results.json`；挑战集 SHA-256 为 `ff78bc38516ee0cf000a705da6caccfc4be96d7033ad462225e37c04f4d9bbef`。代码见[边界挑战运行器](../../src/merchant_agent/evaluation/live_judge_challenges.py)。

## 结果

| 挑战 | 设计分数 | Judge 分数 | 诊断点 |
| --- | ---: | ---: | --- |
| 无结论 | 0 | 0 | 没有净收入结论 |
| 金额矛盾 | 0 | 0 | 同一对象出现两个不一致金额 |
| 缺单位 | 1 | 1 | 金额存在但单位缺失 |
| 缺门店 | 1 | 1 | 金额和单位存在但对象缺失 |
| 明确金额分 | 2 | 2 | 对象、金额和单位齐全 |
| 明确换算 | 2 | 2 | 换算一致且表达清楚 |

六条调用均返回有效 JSON 和理由，Judge 总 token 为 2,168。与**设计分数**一致为 6/6；设计分数由本项目编写者给出，未经两名真人独立盲标，不能称为 Judge 对人工真值的准确率。样本刻意简短且边界清楚，也不能反映自然生成回答中的模糊表达、提示注入或模型方差。

下一步应由真人独立复核这些挑战的 Rubric 适用性，并收集真实 Agent 产生的 0/1 分 Trial。只有覆盖自然失败分布后，才可报告更有意义的 Judge 校准结果。

已准备[挑战盲审入口](../../src/merchant_agent/evaluation/judge_challenge_review.py)：只显示 Rubric 与回答，不显示设计分数或 Judge 分数；两位真人分别运行以下命令，提交记录不可覆盖：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.judge_challenge_review --reviewer-id reviewer_one
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.judge_challenge_review --reviewer-id reviewer_two
```

盲审中途输错分数可重新运行同一命令，已保存的有效案例会跳过。2026-11-03 的一次 `reviewer_one` 提交在 `missing_unit` 遇到终端不可编码字符，程序留下了损坏的半写入文件；该文件已隔离为 `missing_unit.partial-invalid.json`，原两条有效记录保留。写入逻辑现已改为**先完整编码，再独占创建文件**，编码错误不会占用正式记录路径。

两位真人各六条有效记录已齐全；[双标校准报告](judge_challenge_calibration_2026-11-03.md)已生成。分数输错或理由出现无法编码字符时，命令现在会在当前题原地提示重输，不会直接退出。
