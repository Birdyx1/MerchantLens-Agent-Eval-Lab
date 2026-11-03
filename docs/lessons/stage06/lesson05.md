# 6.5 人工抽样校准

状态：抽样与校准代码已通过（教师实现，2026-11-02）；4 条真实 Trial 的双份标签已提交并生成[校准试点报告](../../reports/judge_calibration_2026-11-03.md)，参与者确认两位真人独立盲审。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论

Judge 一致不等于 Judge 正确。定期人工校准应同时检查：两名人类标注者是否一致、裁判多数票是否与仲裁后的人工参考分相符、哪些分歧集中在特定分数。Anthropic 的评测实践强调对 grader 进行人工校准；本课的抽样和汇总字段是项目约定。[Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

抽样采用“分歧或不完整样本优先，其余随机”的**审计样本**。固定随机种子使选择可复现，并记录总体与抽样中的分歧数量。该抽样刻意放大疑难样本，所得一致率只能描述本次样本，不能直接称作总体 Judge 准确率。人工参考分由两名不同 ID 的标注者独立给出；分歧必须由第三名不同 ID 的仲裁者给出分数和理由。人类原始一致率与 Judge 对人工参考分的精确一致率分别报告。

## 实践目标与验收

教师实现 [抽样与校准](../../../src/merchant_agent/evaluation/judge_calibration.py)：输入多裁判结果、抽样数量和种子，输出待复核 Trial ID；输入两份人工分数及必要仲裁，输出人工一致率、Judge 一致率、混淆表与逐例复核清单。专项测试覆盖顺序无关的可复现抽样、双人一致性、缺少第三方仲裁、裁判无结论时不伪造一致率。

当前测试身份及标签均为模拟数据，**没有真实校准结论**。[盲审命令入口](../../../src/merchant_agent/evaluation/judge_blind_review.py)已针对 [6.1 的真实裁判记录](../../reports/live_judge_pilot_2026-11-03.md)准备：只显示 Rubric 与最终回答，不显示 Judge 分数、理由和 Code 结果；每份标签绑定 Trial 与 Rubric 摘要，使用独占创建防止覆盖。身份独立性仍需真人流程保证；阶段 9 标注工作台负责账号与审计等生产化能力。

两位真人各自独立运行以下命令，使用不同的 `reviewer-id`；请勿查看 `results.json` 内容或彼此记录：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.judge_blind_review --reviewer-id reviewer_one runs/judge_pilot/c1d1e92347484bb4aef75ef8960338c3/results.json
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.judge_blind_review --reviewer-id reviewer_two runs/judge_pilot/c1d1e92347484bb4aef75ef8960338c3/results.json
```

这四条均为表达清楚的真实成功回答，预计无法覆盖全部分数层；校准报告应标注样本偏斜。已有两条无最终回答的运行错误，不能替代含糊或矛盾回答的真实样本。

2026-11-03：收到两组各 4 份盲审标签；摘要和身份字段校验通过，原始同分率 4/4，Judge 与同分标签一致 4/4，均为 2 分。参与者确认由两位真人独立盲审；系统尚不能技术性证明身份和隔离，理由文本高度相似仍作为审计注意项。

2026-11-03：另完成[六条人工构造边界挑战的双人盲审校准](../../reports/judge_challenge_calibration_2026-11-03.md)：0/1/2 分各两条，人人同分 6/6，Judge 与人工同分参考标签一致 6/6。它补齐了受控案例的分数层覆盖，仍缺真实 Agent 失败回答的自然分布验证。

## 面试考点与踩坑

问：为什么先看人人一致？答：参考标签本身若不可靠，Judge 对它的一致率没有意义。问：为何优先抽分歧？答：提高发现 Rubric 模糊与裁判失败的效率。问：能否把该抽样一致率当总体准确率？答：不能，抽样不是等概率。问：三裁判无多数票如何计？答：记为无可比较预测，进入人工复核，不算预测正确。

## 提交与评审记录

2026-11-02：教师实现分歧优先抽样、双人参考标签与第三方仲裁校准；专项测试 4 个，全套 pytest 199 passed。
