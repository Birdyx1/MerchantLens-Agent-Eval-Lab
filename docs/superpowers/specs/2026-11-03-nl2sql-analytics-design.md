# 商家经营分析 Agent：NL2SQL + 多维分析 设计文档

日期：2026-11-03 · 状态：待用户批准（第二轮，已处理 builder check）

## Intent / Why

当前 `merchant_agent` 是**预制工具集**：7 个硬编码 SQL 指标，只能问固定问题。三个问题：

1. 能力上限是手写工具清单，问不了「上月退款率最高的 3 家门店」「哪个品类拖累收入」；
2. 数据模型太薄（一张 `orders`、4 字段，无时间/品类/渠道）；
3. 评测只测预制题型，缺真实分析难度。

目标：让 agent 具备 **NL2SQL**（自己写 SQL 回答任意经营问题），数据模型做厚到支持**多维拆解与归因**，并建立**结果导向评测**。

## Goals

- **G1 数据模型做厚**：`orders` 统一为 7 列 schema（加 `order_date/category/channel`）；新增 `stores` 维度表；**新建中等规模分析数据集**（约 8 门店 × 30 天 × 每店每天 3–5 单 ≈ 1000+ 订单）。
- **G2 NL2SQL 工具**：只读 `run_sql(query)`，返回结构化结果集。
- **G3 Agent 自主查询**：用 `run_sql` 回答任意聚合/筛选/分组问题。
- **G4 归因分析**：多步 `run_sql`（维度拆解、对比）回答「为什么 X 变化」。
- **G5 结果导向评测**：以期望结果集比对 + 安全判据。

## Non-goals

- 不做预测/ML/时间序列建模；不做图表可视化；不接真实线上数据。
- **不改动现有 5 个 CSV 与 30 个 Task 的 fixture 哈希，不退役 sealed holdout**。
- 不改现有 `store_net`/`store_net_sum` 的 oracle/rubric 结构。
- 不做多轮对话（后续评估）。

## Anti-goals

- agent 的 SQL 能改动数据或读取白名单外表。
- 评测只验证「SQL 能执行」，不验证结果。
- 归因无 SQL 证据链支撑。
- 为通过评测把答案硬编码进提示词。

## Constraints

- Python 3.13、LangGraph、MCP SDK、SQLite（只读 URI）。
- 现有 **291 个测试不得回归**；现有 Task 快照与 holdout 密封不变。
- `deepseek-flash` 可用；数据仍为虚构，标 `synthetic`。

## Approaches（已选定）

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 数据模型 | **统一 7 列 schema；现有 CSV 不动，新建分析数据集** | 现有 Task/holdout 零改动；分析数据足够做多维 |
| NL2SQL 安全 | **只读连接 + SELECT/WITH + 表白名单** | 与现有 SQL 工具一致，最小够用 |
| 评测 | **结果导向** | 同一问题有多种正确 SQL 写法 |

数据规模的最终决定：**新建中等规模分析数据集**（reviewer 问题 1）。现有 5 个 CSV 只有 3–11 行，加列保行数仍是玩具。

## 数据模型

### orders（统一 7 列 schema）

| 列 | 类型 | 说明 |
| --- | --- | --- |
| order_id | TEXT PK | 订单号 |
| store_id | TEXT | 门店 ID |
| order_date | TEXT | ISO 日期；**可为 NULL**（现有 4 列 CSV 导入时） |
| category | TEXT | 品类：饮品/主食/零售；可为 NULL |
| channel | TEXT | 渠道：堂食/外卖/自提；可为 NULL |
| paid_fen | INTEGER | 已支付，分 |
| refunded_fen | INTEGER | 已退款，分 |

**兼容策略（reviewer 问题 2）**：`create_orders_db` 建 7 列表，用 `csv.DictReader` 读；CSV 有 `order_date/category/channel` 列时写入，缺列时写 NULL。**现有 5 个 CSV 与 sealed holdout 保持 4 列不动**，所以 30 个 Task 哈希与 holdout 密封全部不变，不触发退役。

### stores（新增，可选）

| 列 | 类型 |
| --- | --- |
| store_id | TEXT PK |
| store_name | TEXT |
| region | TEXT |
| city | TEXT |

固定维度数据 `fixtures/business_data/stores.csv`；`create_orders_db` 若发现该文件存在则建表，不存在则跳过（测试用 `tmp_path` 不受影响）。

### 新建分析数据集

`fixtures/business_data/analytics_orders.csv`（7 列）：
- 8 门店（复用现有 `store_id`），30 天（2026-10-01 至 2026-10-31），每店每天 3–5 单，约 1000+ 行。
- `category` ∈ {饮品, 主食, 零售}；`channel` ∈ {堂食, 外卖, 自提}；金额确定性生成。
- 生成脚本落盘，便于复算；CSV 本身作为冻结快照（`sha256` 钉在 analytics 题型的 environment）。

## NL2SQL 工具与安全

### `run_sql(query: str) -> dict`

返回 `{"columns": [str], "rows": [[...]], "row_count": int, "truncated": bool}`。

校验与拒绝分层（reviewer 问题 4）：

| 层 | 情形 | outcome | 是否 hard fail |
| --- | --- | --- | --- |
| 写/DDL | `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/REPLACE` | `security_rejected` | **是** |
| 系统表 | 含 `sqlite_` | `security_rejected` | **是** |
| 表外访问 | 查白名单外对象 | `security_rejected` | **是** |
| 多语句 | 含 `;` | `invalid_input` | 否，可重试 |
| 超长 | `len > 2000` | `invalid_input` | 否 |
| 非查询 | 不以 `SELECT`/`WITH` 开头 | `invalid_input` | 否 |
| 执行错误 | SQLite 语法/运行时错误 | `program_error` | 否 |

只有 `security_rejected` 触发「一次越权即失败」安全判据；其余按普通失败允许重试（避免「末尾分号」误判）。

**plumbing（我能定）**：新增 `SecurityRejected` 异常类，从 `run_sql` 抛出，MCP 层映射为 `is_error`，`call_sql_tool_observed` 捕获后设 `outcome="security_rejected"`。这样 Trace 可区分策略拒绝与数据库故障。

`mode=ro` 仍作为数据库层兜底。行数上限 100，超限截断并标 `truncated: true`。

### Trace 与证据（reviewer 问题 3）

- **完整结果集写入 Span**：`result_field="result_set"`，`call_sql_tool_observed` 在成功时把 `{"columns","rows","row_count","truncated"}` 写进 `span.attributes.result_set`（≤100 行）。
- 这是**评测唯一证据源**（「评测只看 Trace」不变）。
- `truncated=true` 的结果**不可评测**：题目设计须保证正确结果 ≤100 行；评测遇到 truncated 直接判失败并注明原因。
- Span 同时记录 `query`（截断 500 字符）。

## Agent 集成

- `planning.py`：`valid_tool_arguments` 增加 `run_sql`（`{"query": str}`）；`PLANNING_INSTRUCTION` 增加两张表 schema 说明与 `run_sql` 用法。
- `action.py`：`run_sql` 单独分支（返回 dict，非单值）。
- **「今天」注入（reviewer 问题 5）**：`PLANNING_INSTRUCTION` 固定注入「当前日期：2026-11-03」，相对时间可解；不依赖 task 文本。
- **预算（reviewer 问题 6）**：nl2sql 单 Trial 用 `max_steps=10`、`max_total_tokens=8192`，并在 trial 记录里通过 `harness_version` 区分（如 `...:budget:max10/tok8192`），保持与现有基线可比性。

## 评测设计

### 新题型 `nl2sql`

```json
"oracle": {
  "expected_columns": ["store_id", "refund_rate"],
  "expected_rows": [["B", 0.31], ["A", 0.2]],
  "column_tolerance": 1e-6
}
```

### 题面契约（reviewer 问题 7）

- 题面**明确指定输出列名与舍入**，例如：「输出 store_id、refund_rate 两列，退款率保留 4 位小数」。
- 评测**精确匹配列名**（大小写不敏感）；浮点用容差。
- SQLite 整数除法问题由题面约束（要求 `* 1.0` 或 `CAST`）解决；模型写错即自然失败。

### 评测逻辑

1. 从 Trace 取 `run_sql` 结果：**优先取列集合与 `expected_columns` 匹配的成功结果**；无匹配退回最后一次成功结果。
2. `truncated=true` → 直接失败（注明截断）。
3. 列集合一致后，按 Oracle 声明的排序列排序（默认第一列升序），逐行比较；浮点容差。
4. **安全判据**：Trace 出现任一 `security_rejected` → 直接失败（过程一票否决）。
5. 最终答案记录但不作为主判据。

### 归因题（第二阶段）

Oracle 为**关键事实列表**（如「饮品收入下降」「外卖退款率上升」），评测检查最终答案是否包含这些事实，并检查 Trace 有无对应 SQL 证据。本轮先做单查询结果集评测。

## 分阶段实现

1. **数据模型**：`create_orders_db` 7 列 + 可选 `stores` 表；生成 `analytics_orders.csv` + `stores.csv`；现有 4 列 CSV 不动；291 测试全绿。
2. **NL2SQL 工具**：`run_sql` + `SecurityRejected` 分类 + MCP 注册 + planning/action + 观测封装；单测覆盖正常/写/多语句/系统表/截断。
3. **Agent 验证**：真实 smoke（聚合/分组/时间筛选）。
4. **结果导向评测**：`nl2sql` 题型 + rubric + code_evaluator 分支；2–3 道真实 Trial（draft，不入正式集合）。

## 留给 builder 的决定

- `analytics_orders.csv` 的确定性生成算法与具体行数（目标 ≥1000 行）。
- `stores.csv` 的门店-区域映射值。
- 浮点容差具体值（建议 1e-6）。
- 行数上限是否按题型可配（默认 100）。
- 单查询题 Oracle 排序规则（默认第一列升序）。
- 表白名单的具体实现（SQL 解析 or 固定表名集合）。
