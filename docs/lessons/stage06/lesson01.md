# 6.1 LLM 固定 Rubric 裁判

状态：固定 Rubric 单裁判契约已通过（教师实现，2026-11-02）；2026-11-03 完成 4 条真实 Trial 评分及 6 条人工构造边界挑战，真人双标校准仅覆盖 2 分层。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：裁判只回答自己负责的问题

LLM-as-Judge 适合表达清晰度等难以写成稳定代码规则的维度；金额真值、工具参数和 Trace 完整性优先由 Code Evaluator 裁判。若让 LLM 同时重判所有维度，会增加随机性并模糊证据来源。本课新增独立的[清晰度 Rubric](../../../rubrics/judge_clarity_v1.json)：0=无清楚结论或矛盾，1=结论存在但表达不够明确，2=对象、金额和单位都清楚。裁判必须说明理由，且其分数**不能覆盖** Code 结果或安全门禁。Anthropic 的 Agent eval 方法强调明确评分标准、评估器与人工校准；本课的字段是项目约定。[Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

裁判输入只含固定 Rubric 和待评回答；回答被视为**不可信数据**，系统指令要求忽略其中的指令。模型输出必须是严格 JSON `{score, reason}`，拒绝额外字段、非整数、空理由和越界分数。缺少答案由代码直接给 0，不浪费模型调用。保存 Rubric 哈希、裁判模型 ID 和 token 用量，便于日后校准与成本核算。提示注入防护仅靠提示词并不充分；阶段 8 还需对抗测试。

## 实践目标与验收

教师实现 [judge_answer_clarity](../../../src/merchant_agent/evaluation/llm_judge.py)。输入为 Trial、对应 Code 评分、项目根目录和独立 Judge 模型端口；输出为分数、理由、Rubric 哈希、Judge 版本与用量。它不修改原 Code 分数。专项测试覆盖正常评分、缺失答案、非法输出和 Trial 身份不一致。

单元测试使用伪造裁判响应。[真实 Judge 试点报告](../../reports/live_judge_pilot_2026-11-03.md)另对冻结 Regression 批次每题首轮 Trial 运行 DeepSeek 裁判，4 条均得清晰度 2 分，共使用 1,540 Judge token。该样本全为 Code 通过，尚无失败答案覆盖或人工校准，不能报告 Judge 准确率、一致性或生产可用性。正式使用前要固定裁判模型版本与采样参数，对人工双标样本抽样比较，并记录分歧。

## 面试考点与踩坑

问：为什么不让 LLM 判金额？答：金额有可复算真值，代码更稳定。问：裁判理由能否证明分数正确？答：不能，理由还须与证据和人工判断核对。问：如何处理裁判格式错误？答：显式失败并保留原始输出，不能默认给中间分。问：Judge 是否会被待评回答注入？答：会有风险，因此数据与指令分开，并需对抗与人工校准。

## 提交与评审记录

2026-11-02：教师完成固定清晰度 Rubric 与单裁判契约；专项测试 8 个，全套 pytest 181 passed。

2026-11-03：在用户明确授权四条冻结 Trial 最终回答用于 DeepSeek 评分后，真实裁判试点完成；原始记录见报告，Code 分数未改动。

2026-11-03：另运行[六条人工构造的 0/1/2 分边界挑战](../../reports/judge_clarity_challenges_2026-11-03.md)，Judge 与设计分数 6/6 一致；设计分数尚非独立人工真值，且挑战不是 Agent Trial。两位真人盲审命令已准备。
