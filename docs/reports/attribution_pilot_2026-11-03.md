# 阶段 6/7：归因题（多步 SQL 拆解 + 关键事实）试点（2026-11-03）

## 目的

设计文档第二阶段要求「归因题：多步 SQL 拆解 + 关键事实匹配」。本试点验证：agent 能否先用 SQL 拆解出最高维度，再下钻到子维度，并让评测同时检查**关键事实**与**查询证据链**。

## 样本与方法

- 新题型 `attribution`，rubric 3 条判据：
  1. `facts_present`：最终答案包含全部关键事实（每组关键词）；
  2. `query_evidence_present`：成功 `run_sql` 覆盖 Oracle 要求的证据词；
  3. `no_security_rejection`：无越权尝试。
- 1 道 draft 题（`fixtures/eval_task_attribution/attribution_refund_rate_001.json`）：
  「哪个品类的退款率最高？该品类下哪个渠道的退款率最高？请用 SQL 逐步拆解。」
  - 事实：`零售` + `退款率`、`堂食`；
  - 证据：`category`、`channel` 各至少出现在一次成功 SQL 中。
- 真实运行 deepseek-flash，`max_steps=10 / max_total_tokens=8192`。
- 私有记录：`runs/attribution_probe/84a799d59c9c46418c0c7f73baf7e9c2/`。

## 结果：1/1 通过

| 判据 | 结果 |
| --- | --- |
| `facts_present` | True |
| `query_evidence_present` | True |
| `no_security_rejection` | True |

模型行为（真实 Trace 与答案）：
- 第一步按 `category` 聚合退款率，得到**零售 3.17%** 最高；
- 第二步在 `category='零售'` 条件按 `channel` 分组，得到**堂食 3.90%** 最高；
- 答案给出两个维度的明细表、拆解步骤、口径说明（金额口径 vs 订单口径）和建议。
- Trace 中两次成功 `run_sql` 分别覆盖 `category` 和 `channel` 证据。

## 关键发现

1. **多步拆解能力成立**：模型能自己规划「先总后分」的两步 SQL，并把两步结果整合为结论，而不是一次查询硬凑。
2. **评测能同时看结果与证据**：`facts_present` 保证结论正确，`query_evidence_present` 防止「猜对结论却没有证据」；单靠任一判据都不够。
3. 该题数据支持明确差异（零售 3.17% > 饮品 2.37% > 主食 2.11%；堂食 3.90% > 外卖 3.28% > 自提 2.22%），归因不是噪声。

## 局限

- 仅 1 道题、1 次运行，`draft` 未双标，不能推断稳定成功率。
- `required_query_evidence` 只检查关键词出现在 SQL 中，不检查 SQL 是否真的正确（由 `facts_present` 间接约束）；更强的 SQL 结构证据仍需设计。
- 归因题是「维度拆解」而非「时间因果」（数据只有单月），「为什么上月跌了」这类时间归因尚未覆盖。

## 下一步

1. 增加时间维度数据（跨月），做真正的时间归因题（如「为什么 10 月收入下降」）。
2. 扩大归因样本，统计事实匹配率与证据覆盖率。
3. 把归因题纳入正式集合前，先补真人双标与共识。
