# 归因题双人独立标注指南

本指南用于对 4 道 `attribution` draft 题做**两位真人独立盲标**。目标：两人各自从 CSV 独立算出关键事实，比对一致性，为 Oracle 提供人工依据。

## 准备

- 在项目根目录执行；命令用 `.venv/bin/python`。
- 两位真人**分别**完成全部 4 题，各自使用不同 `reviewer_id`（如 `reviewer_one` / `reviewer_two`）。
- **不要**打开 `fixtures/eval_task_attribution/*.json`（含 Oracle 答案），也**不要**看对方提交的记录。
- `runs/attribution_annotations/` 已被 git 忽略，记录不会进入仓库。

## 通用步骤（每题重复）

1. 看题面：
```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.attribution_annotation_cli show fixtures/eval_task_attribution/<task>.json
```
2. 用 Python/pandas 或 Excel 直接读 `fixture_path` 指向的 CSV，自己算。
3. 提交答案（`--answer` 可多次，每题传你算出的关键事实）：
```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.attribution_annotation_cli submit fixtures/eval_task_attribution/<task>.json \
  --reviewer-id reviewer_one \
  --answer <你的答案1> --answer <你的答案2> \
  --evidence-note "<你怎么算的，一句话>"
```

## 四道题与计算口径

### 1. attribution_refund_rate_001
- 题面：哪个品类退款率最高？该品类下哪个渠道退款率最高？
- 数据：`fixtures/business_data/analytics_orders.csv`
- 口径：退款率 = `SUM(refunded_fen) / SUM(paid_fen)`。
- 提交：`--answer <品类> --answer <渠道>`。

### 2. attribution_month_drop_001
- 题面：2026 年 10 月比 9 月净收入变化如何？拖累最大的品类是？
- 数据：`fixtures/business_data/analytics_orders_2m.csv`
- 口径：净收入 = `SUM(paid_fen - refunded_fen)`；月份取 `order_date` 前 7 位。
- 提交：`--answer <拖累最大的品类>`。

### 3. attribution_channel_product_001
- 题面：哪个渠道净收入最高？该渠道下哪个品类净收入贡献最大？
- 数据：`fixtures/business_data/analytics_orders.csv`
- 口径：净收入 = `SUM(paid_fen - refunded_fen)`。
- 提交：`--answer <渠道> --answer <品类>`。

### 4. attribution_store_refund_001
- 题面：哪个门店退款率最高？
- 数据：`fixtures/business_data/analytics_orders.csv`
- 口径：退款率 = `SUM(refunded_fen) / SUM(paid_fen)`，按 `store_id` 分组。
- 提交：`--answer <门店 ID>`。

## 提交后

- 每位真人应得到 4 份记录（每题一个 `<reviewer_id>.json`）。
- 同一人对同一题**不可覆盖**提交；写错需换新的 `reviewer_id` 或人工删除记录后重提。
- 两人都提交完成后告诉我，我会比对一致性并汇总分歧。
