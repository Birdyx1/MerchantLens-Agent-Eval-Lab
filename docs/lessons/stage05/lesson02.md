# 5.2 Code Evaluator

状态：规则评分代码已通过（教师实现，2026-11-02）；真实 Trial 运行与评分接线待补。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：先用可复算规则裁判

Code Evaluator 适合金额、参数、JSON 结构、工具返回等有确定答案的判据。它便宜、可复现，且可以指出具体哪条规则失败；开放式质量判断留给后续 LLM/Agent 裁判。美团和 Anthropic 都强调按任务性质选择评估器，不能让一个主观总分替代可验证证据。[美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html) · [Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

当前 [固定 Rubric](../../../rubrics/store_net_v1.json)有三条**阻断性**判据：

1. `amount_correct`：最终回答必须明确出现**唯一一个以分为单位的金额**，且等于 Task Oracle。
2. `correct_sql_call`：Trace 中至少一次成功调用 `get_store_net`，`store_id` 等于 Oracle 要求的门店。
3. `answer_grounded`：答案金额等于上述有效 SQL 调用的返回金额。

三条必须全过。答案为 `12000 分` 却没有 SQL Trace：结果判据通过、过程两条失败，总体失败。这就是“答案对但链路错误”的可观测例子。金额提取只支持当前明确的“整数＋分”格式；“120 元”、模糊范围或多个“分”金额先失败，后续如需支持等价表达，要扩展有版本的解析规则，不能临时手工放过。

## 输入、输出与证据门禁

[evaluate_trial](../../../src/merchant_agent/evaluation/code_evaluator.py)接收 Trial 记录、Task 路径和项目根目录，输出逐判据布尔结果、金额、Trace 有效性及总体结果。它先核对 Task/环境哈希，再核对 Trace 文件哈希、Span Schema、单一根 Span、Trace ID、父子关系和根 Span 终止原因。Trial 非 `completed` 或 Trace 不可信时三条规则均失败；缺证据不推断通过。

当前是单次 Trial 的规则评分函数，尚未自动写评分文件或批量执行。Trace 检查覆盖本课需要的基本结构；复杂跨 Span 时序、重试因果链与危险动作在阶段 7～8 继续评测。SQL 成功 Span 来自实际 Trace，但本课没有外部签名机制防止有文件写权限者同时篡改 Trial 与 Trace；生产环境还需不可篡改存储或签名。

## 验收标准

- 正确答案、正确门店调用、返回金额一致才全过。
- 答案蒙对但无调用、查错门店、工具结果与答案不符、多个金额均按各自判据失败。
- Trace 或 Task 快照被改动，不能通过评分。

## 面试考点与踩坑

问：为何不只比最终答案？答：可能蒙对、引用旧值或绕过必需工具。问：缺失 Trace 怎么处理？答：证据不足即失败，不能把缺失当作没有违规。问：为什么先 Code 再 LLM Judge？答：确定性问题用代码更稳定，主观判断才需要模型与人工校准。问：规则评分是否覆盖全部质量？答：没有；它只回答 Rubric 中可编码的三条问题。

## 提交与评审记录

2026-11-02：教师实现三条固定判据及 Task/Trace 证据门禁；专项测试 8 个，全套 pytest 158 passed。
