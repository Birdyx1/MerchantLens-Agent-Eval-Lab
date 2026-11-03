# 4.4 双人独立标注

状态：流程代码与 8 道正式题、2 道 Holdout 题的双份人工标注试点已完成；用户于 2026-11-03 确认两位不同真人独立完成。本地 ID 仍不能技术证明身份。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：先独立判断，再讨论分歧

Golden Set 的答案与判据不能只靠一名设计者拍板。美团把“人人一致”视为评测量具是否可靠的条件；Anthropic 建议任务应清楚到两名领域专家能独立得到相近判断，并将标注者间一致性作为人工评测手段。[美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html) · [Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

本课标注的是 **Task 参考真值**，不是给某次 Agent Trial 打分。两名标注者先各自读用户问题和同一份订单快照，分别提交：题目是否可解、计算出的金额、目标门店、证据说明。提交前不展示已有 Oracle、Rubric 正反例或另一人的结果；否则会产生锚定偏差，所谓“双人一致”可能只是互相抄到了同一答案。4.5 才比较两份原始记录并仲裁。

独立性还要求：两份记录来自不同的人、基于相同 Task 和环境版本、提交后不可覆盖。`reviewer_id` 只能区分文件名，**不能证明真实身份或没有私下讨论**；真实工作台需要账号权限与操作审计。本项目暂不把测试中的两种 ID 说成真实人工标注。

## 实践产物与数据流

- [盲标包和提交器](../../../src/merchant_agent/evaluation/annotation.py)：读取已校验 Task，仅生成题目、订单文件位置及快照哈希；不包含 Oracle。记录绑定 Task SHA-256 和环境 SHA-256。
- [记录 Schema](../../../schemas/task_annotation.schema.json)：要求可解性、金额或空值、门店 ID、证据说明、标注者 ID 与时间。不可解时禁止硬填金额。
- [命令入口](../../../src/merchant_agent/evaluation/annotation_cli.py)：`show` 只展示盲标包；`submit` 将每人的记录写入 Git 忽略的 `runs/annotations/<task_id>/<reviewer_id>.json`。同一人重复提交被拒绝，目录权限 `700`、文件权限 `600`。

示例使用方式（两位真实标注者分别操作，金额由本人计算）：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.annotation_cli show fixtures/eval_task_examples/store_net_a.json
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.annotation_cli submit fixtures/eval_task_examples/store_net_a.json --reviewer-id reviewer_a --amount-fen AMOUNT_FEN --store-id STORE_ID --evidence-note '订单行与计算过程'
```

提交前把 `AMOUNT_FEN` 和 `STORE_ID` 换成自己独立得出的值。第二人须使用自己的 ID，不能先看第一人的记录。若判断不可解，用 `--unsolvable` 并省略金额与门店 ID，仍需写明理由。

## 验收、踩坑与面试考点

自动测试验证盲标包不含 12000 或 Rubric ID、两份模拟提交独立保存、相同标注者不能覆盖、非法“不可解但填写金额”被拒绝；全套 pytest **134 passed**。这证明的是**工作流代码**，尚未证明真实人际一致性。正式 Golden 入库仍需 4.5 的一致性计算和争议仲裁。

面试重点：为什么先盲标？防锚定偏差。为什么记录 Task 与环境哈希？题目或数据变了，旧标注不能继续用。为什么保留原始分歧？争议本身可能说明任务歧义或 Rubric 需要修改，不能直接取平均数掩盖问题。

## 提交与评审记录

2026-11-02：教师实现盲标包、提交记录与 CLI；新增 5 个测试，全套 pytest 134 passed。测试中使用的 reviewer ID 是模拟身份，没有真实双人标注结果。

2026-11-03：D/E/F/G/L/M/P/Q 八道正式题及 H/J 两道 Holdout 题均有两份不同 ID 的记录，用户确认由两名真人独立完成。初始测试记录保留为历史，当前证据见[数据闭环](../../data_closure_pilot.md)与[补齐清单](../../stage01_07_gap_closure.md)。
