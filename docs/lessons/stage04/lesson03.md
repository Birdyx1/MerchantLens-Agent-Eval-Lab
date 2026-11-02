# 4.3 Rubric 编写

状态：已通过（教师实现，2026-11-02）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论 1：把“好不好”拆成可判断的问题

Rubric 是对质量标准的显式约定。美团白皮书强调把模糊评价拆成可回答是／否的最小检查项，以提升标注者之间和人机之间的一致性；同时把端到端结果与执行过程分开。Anthropic 将一次任务交给多个 Grader，并建议有确定性证据时先用 Code Grader，开放主观问题再用模型裁判和人工校准。[美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html) · [Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

一条能执行的判据至少回答五件事：**检查什么、读哪份证据、怎样通过、证据缺失怎么办、什么情况会误判**。本项目为每条判据保存维度、是／否问题、`check_key`、证据来源、缺失策略、门禁级别及正反例。自然语言问题帮助人理解，`check_key` 让后续代码裁判准确选择实现；二者需要共同评审。

## 方法论 2：本题的三条独立判据

| 判据 | 维度 | 通过条件 | 典型失败 |
| --- | --- | --- | --- |
| `amount_correct` | 结果 | 最终回答的唯一明确金额等于 Task Oracle 的 12000 分 | 11000 分、无金额、多个未区分金额 |
| `correct_sql_call` | 轨迹 | 有成功的 `get_store_net(store_id=A)` Span | 蒙对 12000 但未查询，或查询 B |
| `answer_grounded` | 轨迹 | 回答金额与该次成功 SQL 返回金额一致 | SQL 返回 12000，回答 15000 |

这三项分别诊断答案、取数路径和证据使用。它们目前都是 `blocking`，缺证据按 `fail` 处理；未来评分应输出**每项结果和失败证据**，再决定总门禁，不能只给一个平均分。成本（token、延迟、调用次数）另作度量；安全负样例另有一票否决 Rubric，不能被本题的分数抵消。

Anthropic 提醒过度固定工具调用顺序会误伤有效解法。本题要求 SQL，是因为当前门店净收入的权威数据只通过该工具取得；Rubric 不要求模型按固定步数或固定顺序调用。若以后增加另一条同等可信的数据路径，必须重新评审过程判据，不能让旧规则把正确解法判错。[Anthropic Grader 设计建议](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

## 方法论 3：冻结标准并校准，而不是边跑边改

版本对比时，Task 和 Rubric 都应固定。本项目的 [Task 样例](../../../fixtures/eval_task_examples/store_net_a.json) 指向 `store_net_v1`，并保存 Rubric 文件的 SHA-256；若规则内容被静默改动，绑定校验会拒绝运行。正式数据集使用后要改规则，应建立新版本并重新比较旧版与新版结果；不能在同一个版本号下改分数口径。美团强调评测标准会随业务变化而需要校准，这属于有记录的版本演进。[美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html)

## 实践产物与代码路径

[Rubric Schema](../../../schemas/rubric.schema.json) 限定字段；[门店净收入 Rubric](../../../rubrics/store_net_v1.json) 写出三条判据和正反例；[加载器](../../../src/merchant_agent/evaluation/rubric.py) 检查文件名与 ID、三项覆盖、重复、维度与证据来源，并按 Task 保存的哈希确认未漂移。4.2 的入库器现在也会先验证 Task 绑定的 Rubric。

数据流：Task → `rubric_id` 和哈希 → 加载固定 Rubric → 之后由 Trial 的最终答案与 Trace 提供证据 → Code Grader 判定。**本课只完成判据资产与绑定，不声称评分器已经实现。**

## 验收、踩坑与面试考点

专项测试覆盖正确绑定、静默改规则、重复判据、错误证据来源和正反例相同；全套 pytest **129 passed**。

面试要解释：为什么 12000 分答对仍可能不通过？因为取数路径和证据使用有独立判据。为什么缺证据不能自动通过？因为 Trace 缺失会掩盖蒙对和工具故障。为什么仍需要双人标注？因为 JSON Schema 只能检查形状，不能证明自然语言判据公平、正反例覆盖充分；4.4～4.5 会检验并仲裁。

## 提交与评审记录

2026-11-02：教师实现 Rubric 资产、Schema、加载及 Task 绑定；新增 5 个专项测试，全套 pytest 129 passed。Task Schema 从 1.0 升到 1.1，增加 Rubric ID 与哈希。学员重点理解裁判设计，不计作独立编码成果。
