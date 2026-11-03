# 8.1b Negative Task 契约与盲标

状态：契约、盲标包和独立提交入口通过（教师实现，2026-11-03）；真人双标、仲裁、正式入库与 Trial 评分待下一小课。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论

原 `EvalTask` 与 Rubric 只表达门店净收入金额，不能正确表达“输入歧义时应澄清”或“脏 ID 应拒绝”。本课新增独立的 [Negative Task Schema](../../../schemas/negative_task.schema.json) 与 [安全 Rubric](../../../rubrics/negative_input_v1.json)。Task 冻结题面、环境哈希、来源和评测侧 Oracle；Oracle 由 `category/expected_behavior/forbidden_tools` 组成，不传给被测模型。

标注者只看用户请求与环境位置，独立写类别、应澄清还是拒绝、禁止调用哪些工具及理由。[盲标包](../../../src/merchant_agent/evaluation/negative_task.py)故意排除 Oracle 和 Rubric 正反例；[提交器](../../../src/merchant_agent/evaluation/negative_annotation.py)绑定题面与环境摘要，一人一题不可覆盖。旧公开的负样例候选已暴露预期行为，不能再当独立盲标题；新建 4 道不同题面的草稿位于 `fixtures/negative_task_drafts/`，仍不得打开原始 JSON 让标注者看到 Oracle。

安全评分分两步：Code Evaluator 检查 Trace 有效及是否调用禁用工具；回答是否**真正**澄清或拒绝，由固定 Rubric 的语义 Judge 与人工复核。非空回答不能自动得出安全通过。当前只是 Task 与标注契约，下一课才处理两人一致性、仲裁、入库及可信 Trace 接线。即使两份记录 ID 不同，也不能从技术上证明现实中的两个人独立作答。

## 实践任务与验收

教师实现负样例 Task 加载、环境与 Rubric 哈希校验、盲标展示和独立提交 CLI；标注者不查看 Oracle，自行判断并提交。专项测试覆盖 4 份草稿加载、盲标字段不泄露和不可覆盖提交。草稿不能冒充 Negative Set 成绩。

## 面试考点与踩坑

- 问：为什么不复用数值题 Oracle？答：安全行为的真值是动作约束与语义行为，不是金额。
- 问：只要没有工具调用就安全吗？答：不能；模型可能直接编造金额或给出不恰当拒绝，仍需语义裁判。
- 坑：标注者看到预填 `expected_behavior` 会被锚定；必须只看盲标包。
- 坑：若任务/环境变更，旧标签必须因摘要不符而失效。

## 提交与评审记录

2026-11-03：教师实现两份 Schema、固定 Rubric、负样例加载与盲标 CLI；专项 pytest 3 passed。真实人工标注待补。
