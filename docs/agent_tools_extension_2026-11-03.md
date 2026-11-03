# Agent 业务工具集扩展（2026-11-03）

状态：教师代写，两轮扩展。共新增 6 个业务指标工具（保留 `get_store_net` 不变）并通过真实运行 smoke；**评测题型与测试集留到后续扩展**（按用户「先扩展 agent 功能，后续再扩展测试集」的要求）。

## 工具集（门店指标参数均为 `store_id`）

| 工具 | 口径 | 返回 |
| --- | --- | --- |
| `get_store_net`（原有） | 净收入 `SUM(paid-refunded)` | int（分） |
| `get_store_order_count` | 订单数 `COUNT(*)` | int |
| `get_store_refund_rate` | 退款率 `SUM(refunded)/SUM(paid)`，四舍五入 6 位 | float（0–1） |
| `get_store_aov` | 客单价 `SUM(paid)/COUNT(*)`，向下取整 | int（分） |
| `get_store_paid_total` | 支付总额 `SUM(paid)` | int（分） |
| `get_store_refunded_total` | 退款总额 `SUM(refunded)` | int（分） |
| `get_store_refunded_order_count` | 有退款的订单数 `COUNT(refunded>0)` | int |

门店不存在时统一返回空值。

## 改动位置

- `src/merchant_agent/tools/sql/sql_query.py`：各指标查询函数 + 只读连接复用。
- `src/merchant_agent/mcp_server.py`：注册 7 个门店指标工具。
- `src/merchant_agent/agent/planning.py`：`STORE_ID_TOOLS` 统一参数校验；`PLANNING_INSTRUCTION` 列出全部工具与返回语义。
- `src/merchant_agent/tracing/observed_sql.py`：泛化为 `call_sql_tool_observed`（result_field + 类型校验），`call_store_net_observed` 变薄封装，保持原 Trace 契约兼容。
- `src/merchant_agent/agent/action.py`：用 `SQL_METRICS` 映射统一分派。

## 验证

- 测试：**291 passed**（两轮共新增 24 条工具/规划测试；并同步更新 MCP stdio 工具发现断言）。
- 真实运行 smoke：`src/merchant_agent/evaluation/live_metric_smoke.py`，deepseek-flash 对 6 个指标各跑一次：

| 问题 | 工具选择 | 结果 |
| --- | --- | --- |
| 门店 A 订单数 | `get_store_order_count` ✓ | **失败**：把「门店 A」当 store_id，查空 |
| 门店 A 退款率 | `get_store_refund_rate` ✓ | **失败**：把「门店 A」当 store_id，查空 |
| 门店 A 客单价 | `get_store_aov` ✓ | 7500 分，正确 |
| 门店 A 支付总额 | `get_store_paid_total` ✓ | 15000 分，正确 |
| 门店 A 退款总额 | `get_store_refunded_total` ✓ | 3000 分，正确 |
| 门店 A 退款订单数 | `get_store_refunded_order_count` ✓ | 2 笔，正确 |

**工具选择 6/6 正确**；但 **2/6 出现参数提取错误**（把「门店 A」整串当 `store_id`）。

## 关键发现：参数提取是当前主要脆弱点

- 6 次 smoke 中 2 次把用户表述「门店 A」直接作为 `store_id` 传入，工具查空后模型如实回答「无法查询」。这与早先 `store_net_sum` ab 题、以及 [边界探针](reports/failure_probe_2026-11-03.md) 的问题同源。
- 这不是工具选择错误，而是**参数规范化缺失**：用户说「门店 A」/「门店A」，系统 ID 是 `A`，agent 没有稳定地做提取。6 次中 2 次（约 33%）出现，高于单次探针的偶发水平，值得作为下一个能力缺口。

## 边界与局限

- smoke 样本仅 6 条、同一门店、单次运行，不构成能力结论；「约 33%」只是本次观测。
- 新工具尚未接入正式评测题型/Rubric；`store_metric` 类题型、Oracle 与答案解析（单数/比率/分单位不同）留到后续「扩展测试集」时设计。
- 客单价整数向下取整、退款率为浮点，未来评分契约需为不同单位分别定义解析与容差，不能复用「恰好一个分金额」的 store_net 解析。

## 下一步候选

1. **参数规范化**：在工具调用前把「门店 A」规范化为 `A`（或提示模型只传纯 ID），直接针对本次发现的脆弱点。
2. 更多业务指标（如支付/退款按订单分布）。
3. 或开始为现有 7 个工具设计评测题型（测试集扩展）。
