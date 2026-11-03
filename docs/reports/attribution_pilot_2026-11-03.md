# 阶段 6/7：归因题（多步 SQL 拆解 + 关键事实）试点（2026-11-03）

## 目的

设计文档第二阶段要求「归因题：多步 SQL 拆解 + 关键事实匹配」。本试点验证：agent 能否先用 SQL 拆解出最高维度，再下钻到子维度，并让评测同时检查**关键事实**与**查询证据链**；同时扩到时间归因与门店维度。

## 样本与方法

- 新题型 `attribution`，rubric 3 条判据：
  1. `facts_present`：最终答案包含全部关键事实（每组关键词）；
  2. `query_evidence_present`：成功 `run_sql` 覆盖 Oracle 要求的证据词；
  3. `no_security_rejection`：无越权尝试。
- 4 道 draft 题：
  | 题 | 问题 | 事实/证据 |
  | --- | --- | --- |
  | refund_rate | 退款率最高的品类，及其最高渠道 | 零售、退款率、堂食；category、channel |
  | month_drop | 10 月比 9 月净收入变化，拖累最大品类 | 零售；category（跨月数据） |
  | channel_product | 净收入最高渠道，及其最大品类 | 堂食、主食；channel、category |
  | store_refund | 退款率最高的门店 | S8；store_id |
- 跨月数据 `analytics_orders_2m.csv`：9 月正常、10 月零售金额减半（9 月净收入 14,852,663 → 10 月 12,235,134，零售 -2,944,371 拖累最大）。
- 真实运行 deepseek-flash，`max_steps=10 / max_total_tokens=8192`。

## 结果：修复截断后 4/4 通过

| 题 | 结果 |
| --- | --- |
| refund_rate | 通过 |
| month_drop | 通过（修复后） |
| channel_product | 通过（修复后） |
| store_refund | 通过 |

模型行为（真实 Trace）：
- refund_rate：两步（按品类 → 按渠道），零售 3.17% / 堂食 3.90%，并给订单与金额两种口径；
- month_drop：10 月环比 -17.6%，按品类拆解，指出零售单项减少 29,443.71 元、超过全店净减少额，主食为唯一正增长；
- channel_product：堂食净收入最高，其下主食贡献最大；
- store_refund：S8 退款率最高。

## 关键问题与修复：长 SQL 导致 JSON 截断

- 首轮 4 题中 2 题偶发 `error`（不同题、不同次）：`model.plan` 输出的 JSON **在末尾被截断**（缺闭合 `}`），`parse_planning_decision` 抛 `ValueError`。
- 根因：模型生成复杂 SQL（多级 CTE / 窗口函数 / UNION）时输出过长被截断。**请求已带 `max_output_tokens=4096` 但 DeepSeek Responses 未生效**（仍截断）。
- 修复：`PLANNING_INSTRUCTION` 提示「SQL 尽量简洁，能用单层聚合就不要用多级 CTE/窗口函数」。修复后同一批 4 题 **4/4 completed 且通过**。

## 关键发现

1. **多步拆解能力成立**：模型能自己规划「先总后分」的两步 SQL，并把结果整合为结论；时间归因能从 `order_date` 提取月份对比。
2. **评测能同时看结果与证据**：`facts_present` 保证结论正确，`query_evidence_present` 防止「猜对结论却没有证据」。
3. **输出长度是真实约束**：复杂 SQL 容易触发截断，提示简洁比单纯调 `max_output_tokens` 更有效（后者在 DeepSeek 上未生效）。

## 局限

- 4 道题、少量运行，`draft` 未双标，不能推断稳定成功率。
- `required_query_evidence` 只查关键词出现在 SQL 中，不验证 SQL 结构正确（由 `facts_present` 间接约束）。
- 时间归因只有 2 个月、单一「零售下降」设定，未覆盖多因素交互。

## 下一步

1. 扩大归因样本（多组维度/多个月），统计事实匹配率与证据覆盖率。
2. 把归因题纳入正式集合前，先补真人双标与共识。
3. 更稳的截断处理：解析层对「括号不平衡」做明确报错分类，而不是笼统 `error`。
