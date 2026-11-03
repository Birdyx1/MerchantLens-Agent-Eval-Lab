# 阶段 6/7：NL2SQL 结果导向评测试点（2026-11-03）

## 目的

验证新增的 NL2SQL 能力（`run_sql` + 多维数据）能否用**结果导向判据**评测，并观察真实模型在「自己写 SQL 回答任意经营问题」上的表现与失败模式。

## 样本与方法

- 3 道 `nl2sql` draft 题（`fixtures/eval_task_nl2sql/`），基于 `analytics_orders.csv`（1488 单、8 门店、2026-10 全月、品类/渠道维度）：
  1. 按品类列出净收入合计（降序）；
  2. 按渠道列出退款率（4 位小数，降序）；
  3. 统计 2026-10-15 当天订单数。
- Oracle 为**期望结果集**（列名 + 行），评测比较排序后的行、浮点容差 1e-6、安全判据（无越权）。
- 2 次运行、每次 3 题 = 6 个真实 Trial；`max_steps=10`、`max_total_tokens=8192`。
- 私有记录：`runs/nl2sql_probe/42ed5b6d0a024323af2c875dc71bb712/`、`runs/nl2sql_probe/43f36dd48f9f4c04beb77029ef486f3a/`。

## 结果：完成 Trial 结果集 4/4 正确，模型格式违规 2/6

| 运行 | category_net | channel_refund_rate | date_count |
| --- | --- | --- | --- |
| run 1 | 格式失败 | **通过** | 网络故障 |
| run 2 | **通过** | 格式失败 | **通过** |

- **成功完成的 4 个 Trial，结果集 4/4 与 Oracle 一致**（result_set_matches_oracle 全 True）。
- **模型格式违规 2 次**：模型拿到 `run_sql` 结果后，直接输出 Markdown 表格与解释，**不符合 JSON 规划格式**（`{"plan":…,"action":{"type":"finish",…}}`），`parse_planning_decision` 抛 `ValueError`，Trial 记为 error。
- **网络故障 1 次**：`SSLError`（与历史 ConnectionError 同类，环境噪声，不是能力失败）。

## 关键发现

1. **结果导向评测可用**：只要 Trial 正常完成，结果集判据能准确判定正确性（4/4），且能识别列名/排序/容差。
2. **当前主要失败模式是格式契约，而非 SQL 能力**：模型能写出正确 SQL（含 `ROUND`、`NULLIF`、`ORDER BY`），但在拿到结果后「直接答人话」，破坏 JSON 规划契约。2/6 次稳定复现，说明这是 agent 的**格式遵循缺陷**，不是数据或评测缺陷。
3. **该缺陷会被结果导向评测捕获**：这类 Trial 记为 error → ineligible → 判失败，不会把「答对但格式坏」误判为通过。

## 格式契约修复与重跑

`parse_planning_decision` 已容错：模型在拿到工具结果后直接输出自然语言答案（Markdown 表格）时，视为 finish（`action=finish`），而不是抛 `ValueError` 让整个 Trial 报 error；Markdown 代码块包裹的 JSON、坏 JSON、不像答案的短文本仍被拒绝。

修复后重跑 3 题：**3/3 completed 且结果集全部匹配**（私有记录 `runs/nl2sql_probe/9257a1a4def44f3ba34150f6b9a49457/`）。对比修复前 2/6 格式失败（当时这些 Trial 记为 error），这是明确的改善。

## 局限

- 样本仅 3 题 × 2 次，`draft`、未双标共识，不入正式集合，不能据此推断稳定成功率。
- 网络故障使 1 个 Trial 无效；2 次运行结果不完全可复现（格式违规随机出现）。
- 归因题（多步拆解）尚未接入评测，本报告只覆盖单查询结果集。

## 下一步

1. **修格式契约的鲁棒性**：例如允许模型在 `finish` 时返回自然语言（把答案放进 `answer` 字段即可），或在解析失败时给出一次可恢复提示，而不是直接 error；这属于 agent 能力改进，需单独设计。
2. 扩大 nl2sql 样本（不同聚合/分组/时间窗口），统计格式违规率与结果错误率。
3. 归因题（多步 SQL + 关键事实匹配）作为第二阶段。
