# NL2SQL + 多维分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让商家经营分析 Agent 能自己写 SQL 回答任意经营问题，并建立结果导向的 NL2SQL 评测。

**Architecture:** 扩展 `orders` 为 7 列 schema（现有 4 列 CSV 与 sealed holdout 保持字节不变），新建中等规模分析数据集；新增只读 `run_sql` 工具（安全分层拒绝）；agent 通过 `run_sql` 自主查询；新增 `nl2sql` 题型以结果集比对 + 安全判据评测。

**Tech Stack:** Python 3.13、LangGraph、MCP SDK、SQLite、pytest

**Spec:** `docs/superpowers/specs/2026-11-03-nl2sql-analytics-design.md`

## Global Constraints

- Python 3.13；现有 **291 个测试不得回归**。
- 现有 5 个 4 列 CSV 与 `holdout/fixtures/reserved_orders.csv` 保持字节不变（30 个 Task 哈希与 `holdout/manifest.json` 不变）。
- `run_sql` 只读（`mode=ro`）+ 必须以 `SELECT`/`WITH` 开头 + 禁多语句（`;`）+ 禁 `sqlite_` + 行数上限 100。
- 写/DDL/系统表 = `security_rejected`（hard fail）；多语句/超长/非查询 = `invalid_input`（可重试）。
- 固定「当前日期：2026-11-03」注入 `PLANNING_INSTRUCTION`。
- `nl2sql` 单 Trial 预算 `max_steps=10`、`max_total_tokens=8192`，`harness_version` 记 budget 标记。
- 浮点容差 `1e-6`；列名精确匹配（大小写不敏感）。

## Review Focus

- `run_sql` 收到 `SELECT ...;`（末尾分号）：应判 `invalid_input` 可重试，不能判 `security_rejected`。
- `run_sql` 收到写语句（`INSERT/UPDATE/DROP`）：必须 `security_rejected`，只读连接兜底。
- 4 列 CSV 导入 7 列表：新列必须为 NULL，store_net 查询结果不变。
- 结果集 >100 行：`truncated=true`，评测直接失败，不静默比较前 100 行。
- nl2sql 题面期望 `0.31` 但模型输出 `0.3103`：浮点容差内应判通过。

---

### Task 1: 数据模型 7 列 + 可选 stores 表

**Files:**
- Modify: `src/merchant_agent/tools/sql/init_orders_db.py`
- Test: `tests/test_init_orders_db.py` (create)

**Interfaces:**
- Consumes: 现有 4 列 CSV（`order_id,store_id,paid_fen,refunded_fen`）。
- Produces: `create_orders_db(csv_path: str, db_path: str) -> None`（签名不变，行为扩展）；`orders` 表 7 列；若 `fixtures/business_data/stores.csv` 存在则建 `stores` 表。

- [ ] **Step 1: Write the failing test**

```python
def test_four_column_csv_fills_new_columns_with_null(tmp_path):
    csv_path = tmp_path / "o.csv"
    csv_path.write_text("order_id,store_id,paid_fen,refunded_fen\n1,A,100,0\n")
    db = tmp_path / "o.sqlite"
    create_orders_db(str(csv_path), str(db))
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT order_date, category, channel, paid_fen FROM orders").fetchone()
    assert row == (None, None, None, 100)

def test_seven_column_csv_keeps_dimensions(tmp_path):
    csv_path = tmp_path / "o.csv"
    csv_path.write_text("order_id,store_id,order_date,category,channel,paid_fen,refunded_fen\n"
                        "1,A,2026-10-01,饮品,外卖,100,0\n")
    db = tmp_path / "o.sqlite"
    create_orders_db(str(csv_path), str(db))
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT order_date, category, channel FROM orders").fetchone()
    assert row == ("2026-10-01", "饮品", "外卖")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_init_orders_db.py -v`
Expected: FAIL（`no such column: order_date`）

- [ ] **Step 3: Implement**

建表 SQL 扩为 `order_id, store_id, order_date, category, channel, paid_fen, refunded_fen`（`order_date/category/channel` 允许 NULL）。用 `csv.DictReader`，`row.get("order_date")` 等缺列时返回 `None`。另：若 `Path(__file__).parents[3]/"fixtures/business_data/stores.csv"` 存在，则建 `stores(store_id, store_name, region, city)` 并导入；不存在则跳过。

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_init_orders_db.py -v` 然后 `.venv/bin/python -m pytest -q`
Expected: 全绿（含原有 291 条）

- [ ] **Step 5: Commit**

```bash
git add src/merchant_agent/tools/sql/init_orders_db.py tests/test_init_orders_db.py
git commit -m "feat: extend orders schema to 7 columns with optional stores table"
```

---

### Task 2: 生成中等规模分析数据集

**Files:**
- Create: `scripts/generate_analytics_data.py`
- Create: `fixtures/business_data/analytics_orders.csv`
- Create: `fixtures/business_data/stores.csv`
- Test: `tests/test_analytics_data.py` (create)

**Interfaces:**
- Consumes: 无。
- Produces: `analytics_orders.csv`（7 列，≥1000 行，8 门店，日期 2026-10-01..10-31，`category` ∈ {饮品,主食,零售}、`channel` ∈ {堂食,外卖,自提}）；`stores.csv`（8 门店 + region/city）。

- [ ] **Step 1: Write the failing test**

```python
def test_analytics_csv_shape():
    path = ROOT / "fixtures/business_data/analytics_orders.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) >= 1000
    assert {r["store_id"] for r in rows} == {f"S{i}" for i in range(1, 9)}
    assert {r["order_date"][:7] for r in rows} == {"2026-10"}
    assert all(r["category"] in {"饮品", "主食", "零售"} for r in rows)
    assert all(r["channel"] in {"堂食", "外卖", "自提"} for r in rows)
    assert all(int(r["paid_fen"]) > 0 for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_analytics_data.py -v`
Expected: FAIL（文件不存在）

- [ ] **Step 3: Implement generator and generate CSVs**

`scripts/generate_analytics_data.py`：用 `random.Random(20261103)` 固定 seed；8 门店 `S1..S8`、30 天、每店每天 `randint(3,5)` 单；金额 `randint(1000, 20000)`，退款 `randint(0, paid//3)`；写入 `analytics_orders.csv`。`stores.csv` 固定映射（8 行）。

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_analytics_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_analytics_data.py fixtures/business_data/analytics_orders.csv fixtures/business_data/stores.csv tests/test_analytics_data.py
git commit -m "feat: generate deterministic analytics dataset"
```

---

### Task 3: run_sql 工具（安全分层）

**Files:**
- Create: `src/merchant_agent/tools/sql/run_sql.py`
- Test: `tests/test_run_sql.py` (create)

**Interfaces:**
- Consumes: `db_path`（SQLite）。
- Produces: `run_sql(db_path: str, query: str) -> dict`；成功返回 `{"outcome": "success", "columns": [...], "rows": [...], "row_count": int, "truncated": bool}`；拒绝返回 `{"outcome": "security_rejected"|"invalid_input"|"program_error", "message": str}`。

- [ ] **Step 1: Write the failing test**

```python
def test_select_returns_result_set(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT COUNT(*) AS c FROM orders")
    assert result["outcome"] == "success"
    assert result["columns"] == ["c"]
    assert result["rows"] == [[3]]

def test_trailing_semicolon_is_invalid_not_security(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT COUNT(*) FROM orders;")
    assert result["outcome"] == "invalid_input"

def test_write_statement_is_security_rejected(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "DROP TABLE orders")
    assert result["outcome"] == "security_rejected"

def test_system_table_is_security_rejected(tmp_path):
    db = _seed_db(tmp_path)
    result = run_sql(str(db), "SELECT * FROM sqlite_master")
    assert result["outcome"] == "security_rejected"

def test_row_cap_truncates(tmp_path):
    db = _seed_big_db(tmp_path, n=150)
    result = run_sql(str(db), "SELECT * FROM orders")
    assert result["row_count"] == 100 and result["truncated"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_run_sql.py -v`
Expected: FAIL（`run_sql` 不存在）

- [ ] **Step 3: Implement run_sql**

校验顺序：长度 ≤2000；`strip()` 后 `upper().startswith(("SELECT","WITH"))`；写关键字正则（`\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE)\b`）→ security；含 `sqlite_` → security；含 `;` → invalid_input。用 `sqlite3.connect(uri+"?mode=ro", uri=True)`，`fetchmany(100)`，超 100 标 `truncated=True`。执行异常 → `program_error`。

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_run_sql.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/merchant_agent/tools/sql/run_sql.py tests/test_run_sql.py
git commit -m "feat: add read-only run_sql tool with layered rejection"
```

---

### Task 4: MCP / planning / action / observed 集成 run_sql

**Files:**
- Modify: `src/merchant_agent/mcp_server.py`
- Modify: `src/merchant_agent/agent/planning.py`
- Modify: `src/merchant_agent/agent/action.py`
- Modify: `src/merchant_agent/tracing/observed_sql.py`
- Test: `tests/test_run_sql_integration.py` (create)

**Interfaces:**
- Consumes: `run_sql(db_path, query)`。
- Produces: MCP 工具 `run_sql(query: str) -> dict`；`valid_tool_arguments("run_sql", {"query": ...})`；`call_run_sql_observed(client, query, *, trace...) -> dict`；Span `tool.run_sql` 的 `attributes.result_set` 为完整结果（≤100 行）。

- [ ] **Step 1: Write the failing test**

```python
def test_valid_tool_arguments_accepts_run_sql():
    assert valid_tool_arguments("run_sql", {"query": "SELECT 1"}) is True
    assert valid_tool_arguments("run_sql", {"query": ""}) is False

def test_call_run_sql_observed_records_result_set(tmp_path):
    # 用真实 MCP Client(create_server(db)) 调 run_sql，断言 span 含 result_set 与 query
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_run_sql_integration.py -v`
Expected: FAIL

- [ ] **Step 3: Implement integration**

`mcp_server.py` 加 `@server.tool() def run_sql(query: str) -> dict: return sql.run_sql(db_path, query)`；`planning.py` 的 `valid_tool_arguments` 加 `run_sql` 分支（`{"query"}` 非空 str，长度 ≤2000），`PLANNING_INSTRUCTION` 加两表 schema 与「当前日期：2026-11-03」；`action.py` 加 `run_sql` 分支，调用 `call_run_sql_observed`；`observed_sql.py` 新增 `call_run_sql_observed`：成功时 `span["attributes"]["result_set"]=result`（去掉 outcome 字段），失败时记 `outcome` 与 `message`。

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_run_sql_integration.py tests/test_mcp_stdio.py -v` 然后 `.venv/bin/python -m pytest -q`
Expected: 全绿（MCP stdio 工具发现断言需加 `run_sql`）

- [ ] **Step 5: Commit**

```bash
git add src/merchant_agent/mcp_server.py src/merchant_agent/agent/planning.py src/merchant_agent/agent/action.py src/merchant_agent/tracing/observed_sql.py tests/test_run_sql_integration.py tests/test_mcp_stdio.py
git commit -m "feat: wire run_sql through MCP, planning, action and tracing"
```

---

### Task 5: 真实 Agent smoke

**Files:**
- Create: `src/merchant_agent/evaluation/live_nl2sql_smoke.py`
- Test: 手动真实运行（不进入 pytest）

**Interfaces:**
- Consumes: `invoke_live_agent`、`initial_state`、`create_orders_db`、`analytics_orders.csv`。
- Produces: `main() -> list[dict]`，打印每题的工具调用与最终答案。

- [ ] **Step 1: Write the smoke script**

复用 `live_metric_smoke.py` 结构：用 `analytics_orders.csv` 建库，跑 3 个问题（按品类聚合、按渠道对比、时间筛选），记录 `tools_called` 与 `final_answer`。

- [ ] **Step 2: Run against real DeepSeek**

Run: `PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_nl2sql_smoke`
Expected: 3 题都调用 `tool.run_sql` 并给出可核对的答案

- [ ] **Step 3: Commit**

```bash
git add src/merchant_agent/evaluation/live_nl2sql_smoke.py
git commit -m "feat: add real NL2SQL smoke script"
```

---

### Task 6: nl2sql 题型 + 结果导向评测

**Files:**
- Modify: `schemas/eval_task.schema.json`
- Modify: `schemas/rubric.schema.json`
- Create: `rubrics/nl2sql_v1.json`
- Modify: `src/merchant_agent/evaluation/task.py`
- Modify: `src/merchant_agent/evaluation/rubric.py`
- Modify: `src/merchant_agent/evaluation/code_evaluator.py`
- Modify: `src/merchant_agent/evaluation/trajectory_evaluator.py`
- Test: `tests/test_nl2sql_eval.py` (create)

**Interfaces:**
- Consumes: Trace 中 `tool.run_sql` 的 `result_set`。
- Produces: `EvalTask` 增加 `expected_columns: tuple[str,...]`、`expected_rows: tuple[tuple,...]`；`evaluate_trial` 对 `task_type=="nl2sql"` 返回 3 条判据：`result_set_matches_oracle`、`no_security_rejection`、`answer_grounded`。

- [ ] **Step 1: Write the failing test**

```python
def test_nl2sql_result_set_match_passes(tmp_path):
    # 构造 Trace：tool.run_sql 的 result_set = columns ["store_id","refund_rate"], rows [["B",0.31],["A",0.2]]
    # Oracle 相同 → passed True
    ...

def test_nl2sql_float_tolerance_passes(tmp_path):
    # result_set 0.3103 vs Oracle 0.31，容差 1e-6 内应通过
    ...

def test_nl2sql_truncated_result_fails(tmp_path):
    # result_set.truncated=True → 失败并注明截断
    ...

def test_nl2sql_security_rejection_fails(tmp_path):
    # Trace 含 outcome=security_rejected 的 run_sql span → 失败
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_nl2sql_eval.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

schema：`task_type` enum 加 `nl2sql`；`oracle` `$defs` 加 `nl2sql_oracle`（`expected_columns`、`expected_rows`、可选 `column_tolerance`）。`rubric.schema.json` 加 3 个 `check_key`。`task.py` 读 nl2sql oracle。`rubric.py` 加 `nl2sql` contracts。`code_evaluator.py` 加 `_nl2sql_checks`：取列集合匹配的 result_set；truncated→fail；列名精确匹配；按第一列排序后逐行比较，浮点容差 1e-6；任一 `security_rejected` span→fail。`trajectory_evaluator.py` 加 nl2sql 分支（同样的 3 条）。

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/python -m pytest tests/test_nl2sql_eval.py -v` 然后 `.venv/bin/python -m pytest -q`
Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add schemas/eval_task.schema.json schemas/rubric.schema.json rubrics/nl2sql_v1.json src/merchant_agent/evaluation/ tests/test_nl2sql_eval.py
git commit -m "feat: add nl2sql task type with result-set evaluation"
```

---

### Task 7: 真实 NL2SQL Trial

**Files:**
- Create: `fixtures/eval_task_nl2sql/*.json`（2–3 题）
- Create: `src/merchant_agent/evaluation/live_nl2sql_probe.py`
- Test: 手动真实运行

**Interfaces:**
- Consumes: Task 3–6 的全部能力。
- Produces: 真实 Trial 记录（`runs/`，私有）。

- [ ] **Step 1: Write tasks and probe script**

2–3 道 `nl2sql` 题（按品类聚合、按渠道退款率、时间段筛选），`label_status=draft`；probe 脚本复用 `live_failure_probe.py` 结构，用 `max_steps=10, max_total_tokens=8192`。

- [ ] **Step 2: Run**

Run: `PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_nl2sql_probe`
Expected: 记录每题 `result_set` 与评分

- [ ] **Step 3: Commit**

```bash
git add fixtures/eval_task_nl2sql/ src/merchant_agent/evaluation/live_nl2sql_probe.py
git commit -m "feat: add draft nl2sql tasks and real probe"
```
