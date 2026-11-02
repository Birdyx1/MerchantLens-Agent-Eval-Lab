# 4.1 Task 数据契约

状态：已通过（教师实现，2026-11-02）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论 1：分清题目、运行和裁判

**Task（题目）**固定“给 Agent 什么问题、提供什么环境、怎样算成功”。**Trial（试验）**是某一模型与 Harness 对该 Task 的一次运行，产生答案、状态和 Trace。**Grader（裁判）**读取 Trial 与 Task 的判据并打分。同一 Task 可以运行多次以观察随机性，也可以交给不同模型与 Harness 做控制变量对比；不能把一次运行的输出写回 Task 当作真值。[Anthropic 的评测结构](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) · [PawBench 的模型 × Harness 设计](https://github.com/agentscope-ai/PawBench)

**合格 Task 的先决条件**：任务可解，输入不含隐含前提，判据足够明确，使两名领域专家独立判断时大体得出相同结论；最好有能通过所有检查的参考解。若题目本身歧义大，分数变化可能来自题目或裁判，而非 Agent 能力。[Anthropic 的任务设计建议](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

## 方法论 2：固定环境，拆开结果与过程

本项目 Task v1 的字段是**项目约定**，不是行业标准：

| 字段 | 作用 | 被测 Agent 是否可见 |
| --- | --- | --- |
| `task_id`、`schema_version` | 固定身份与契约版本，便于同题跨版本比较 | 不作为任务提示词传入 |
| `input.user_request` | 用户实际提出的问题 | 可见 |
| `environment.fixture_path`、`fixture_sha256` | 固定订单快照；哈希不同就拒绝加载 | 数据经工具访问，路径和哈希不传给模型 |
| `oracle.expected_amount_fen` | 结果真值，来自模拟订单口径 | 不可见 |
| `oracle.required_tool_call` | 过程判据：必须使用权威的门店净收入查询工具 | 判据不传给模型，调用会出现在 Trace |
| `provenance`、`label_status` | 记录来源和标注是否仲裁 | 不可见 |

固定环境是控制变量：如果订单数据变了，A 版本和 B 版本的得分差异就不能归因于 Agent 改动。美团强调固定评测集与执行环境；阿里 AgentLoop 实践强调冻结答案卷，并把完成度、红线和过程分开判断。[美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html) · [AgentLoop 实践](https://developer.aliyun.com/article/1758156)

**为何不能只看答案**：模型也可能直接猜出“12000 分”。本题的数值结果与 SQL 证据链应分开报告。后续 Code Grader 会检查最终答案、工具名与参数、工具返回值及根 Trace；仅出现一次工具名仍不足以证明答案确实来自该工具。`required_tool_call` 是本项目针对权威数据源的过程要求，正式入库前应由标注者确认它公平且与任务描述一致。

## 方法论 3：样本进入评测集前的质量门

本课样例为 `synthetic` 且 `draft`。它可用于调试契约，**不能直接宣称为黄金基准**。先由两名标注者独立核对口径与过程判据，再仲裁争议；通过后才考虑进入 Golden Set。Badcase 需保留真实回流来源，Negative Set 需标注风险类型；集合归属由后续物理目录与入库规则决定，不能靠 `provenance` 一个字段代替。这个边界防止回流样本直接污染黄金集。

## 实践产物与数据流

- [Task Schema](../../../schemas/eval_task.schema.json) 固定字段与类型；[样例 Task](../../../fixtures/eval_task_examples/store_net_a.json) 的参考数值为 12000 分，来源是本地模拟订单。
- [加载器](../../../src/merchant_agent/evaluation/task.py) 先做 Schema 校验，再检查文件位于项目内、确实存在且哈希一致；返回冻结的 `EvalTask`，包括不可修改的工具参数映射。
- 流水线调用 `agent_input()` 提取用户请求；评测器另读 `expected_amount_fen` 与 `required_tool_call`。当前方法提供清晰边界，后续批量执行器仍必须遵守这条边界，避免把整个 Task 序列化进模型提示词。

## 验收与面试考点

验收：样例可加载；模型输入不含预期数值；环境文件漂移、越界路径和私加 Oracle 字段均被拒绝；全套 pytest **119 passed**。

面试要能解释：为什么答案正确仍可能失败？因为结果分与过程证据分是两个维度。为什么固定文件哈希？因为环境漂移会破坏版本对比的可归因性。为什么 `draft` 不能直接进 Golden Set？因为预期值正确不等于判据已达成人员共识。为什么重复 Trial？因为模型输出有随机性，单次通过率不稳。

当前只覆盖 `store_net` 数值型 Task；安全拒绝、开放任务 Rubric、集合归属和参考解自动验证在后续课扩展。SHA-256 只能证明文件未变，不能证明 Oracle 标签本身正确。

## 提交与评审记录

2026-11-02：教师实现 Task Schema、样例和加载器；新增 4 个测试，全套 pytest 119 passed。学员负责理解契约与评测方法，不计作独立编码成果。

2026-11-02：按学员反馈补充 Task／Trial／Grader、环境冻结、结果与过程分评、标注质量门等方法论；同时修正冻结数据类中工具参数仍可变的问题。
