# 9.3 标注工作台

状态：进行中（核心实现与候选清单完成，真人标注与仲裁待补）；教师实现，2026-11-03。

课时定位：阶段 9 主线，在 9.2 脱敏去重之后、9.4 Badcase 入库之前完成并验收。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

工作台把「异常候选」变成「可标注、可复核、可仲裁」的记录：

- **候选**：由 9.2 去重后的 finding 生成，`candidate_id = task_id + 异常类型组`，同一组合唯一；
- **标注**：标注者填写 `is_real_badcase`、`root_cause`、`fix_direction`；同一人对同一候选**不可覆盖**；
- **状态机**：`pending`（无标注）→ `one_label`（一人）→ `agreed`（两人一致）/ `disputed`（分歧，需仲裁）。

## 实践任务

实现 `workbench.py`（`load_candidates` / `submit_label` / `label_status`），并用 9.2 的真实候选生成工作台清单。

## 验收标准

- 7 条单元测试覆盖候选生成、不可覆盖、四种状态与空理由拒绝；
- 真实候选清单可生成（14 条）。

## 真实候选（2026-11-03）

由 147 个 Trial 的异常经脱敏去重得到 **14 条候选**，写入 `runs/workbench/candidates.json`（Git 忽略），例如：

- `attribution_channel_product_001__trial_not_completed`
- `attribution_refund_rate_001__tool_failure`
- `nl2sql_date_count_001__tool_failure-trial_not_completed`

候选只描述异常类型，不预设「谁对谁错」，根因与修复方向由标注者判断。

## 面试考点与踩坑

- 问：为什么标注不可覆盖？答：覆盖会抹掉证据；写错应换 reviewer_id 或人工删除后重提，保留可审计性。
- 问：`disputed` 后怎么办？答：进入第三人仲裁，仲裁结论与理由都要落盘；不能由其中一位标注者改判。
- 坑：`candidate_id` 用 task+类型组，不同 trial 的同类异常会合并；若需逐 trial 追踪，应在 finding 上保留 trial_id。

## 提交与评审记录

2026-11-03：教师实现 `workbench.py`、7 条测试，生成 14 条真实候选。真人标注与仲裁待补。
