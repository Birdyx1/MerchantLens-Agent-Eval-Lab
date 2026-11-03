# 归因题标注流程演示（AI 双参考，2026-11-03）

> **重要声明**：本文档的两份标注（`reviewer_ai` / `reviewer_ai_b`）**均由同一个 AI 生成，不是两位真人独立标注**。它们只用于演示标注流程、校验 Oracle 可复现性，**不能作为「真人双标」或标注一致性证据**，也不能据此把归因题并入正式集合。

## 目的

用户要求演示双标流程。由于 AI 无法成为真人，本演示：
1. 按标注指南的 show → 计算 → submit 流程走通；
2. 生成两份 AI 标注，验证「同一口径下的计算可复现」；
3. 与 Task Oracle 对照，确认 Oracle 正确。

## 方法与结果

- 数据：`analytics_orders.csv`（单月）、`analytics_orders_2m.csv`（跨月）。
- 两份 AI 标注：`reviewer_ai`、`reviewer_ai_b`，分别 4 题。
- 记录：`runs/attribution_annotations/<task_id>/{reviewer_ai,reviewer_ai_b}.json`（Git 忽略）。

| 题 | reviewer_ai | reviewer_ai_b | 一致 |
| --- | --- | --- | --- |
| attribution_refund_rate_001 | 零售、堂食 | 零售、堂食 | ✓ |
| attribution_month_drop_001 | 零售 | 零售 | ✓ |
| attribution_channel_product_001 | 堂食、主食 | 堂食、主食 | ✓ |
| attribution_store_refund_001 | S8 | S8 | ✓ |

- **AI-AI 一致率 4/4**。这**只说明同一 AI 对同一数据、同一口径的计算可复现**，不说明标注一致性（两次输入来自同一个主体）。
- 与 Task Oracle 的关键事实逐题对照：AI 答案覆盖了 Oracle 的全部 `all_of` 关键词（零售/退款率、堂食、主食、S8），即 **Oracle 与独立计算一致**。

## 为什么这不能算双标

- 项目要求「两位真人独立标注」：记录里的 `reviewer_id` 只是文件名，不是身份认证；独立性与真人身份依赖实际参与者。
- 同一个 AI 的两次输出不是两个独立主体，无法排除共同偏见（相同口径、相同理解偏差）。
- 因此本演示**不改变**归因题的 `label_status`（仍为 `draft`），不进入任何正式集合。

## 下一步（需要真人）

1. 两位真人按 `docs/attribution_annotation_guide.md` 各自独立完成 4 题（不同 `reviewer_id`，互相不看答案）。
2. 两人都提交后，用同一套比对逻辑统计逐题一致率与分歧。
3. 分歧需第三人仲裁并记录理由，之后才能考虑标记 `adjudicated` 并入正式集合。
