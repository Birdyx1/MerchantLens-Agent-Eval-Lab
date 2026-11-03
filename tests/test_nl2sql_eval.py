import hashlib
import json
from pathlib import Path

from merchant_agent.evaluation.code_evaluator import evaluate_trial


ROOT = Path(__file__).resolve().parents[1]


def _prepare(tmp_path, *, runs, oracle_columns=("store_id", "refund_rate"),
             tolerance=1e-3):
    """runs: list of (columns, rows, truncated, security)."""
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json",
        "schemas/span.schema.json", "rubrics/nl2sql_v1.json",
        "fixtures/business_data/analytics_orders.csv",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    fixture = tmp_path / "fixtures/business_data/analytics_orders.csv"
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "schema_version": "1.2",
        "task_id": "nl2sql_test_001",
        "task_type": "nl2sql",
        "rubric_id": "nl2sql_v1",
        "rubric_sha256": hashlib.sha256((ROOT / "rubrics/nl2sql_v1.json").read_bytes()).hexdigest(),
        "input": {"user_request": "按门店列出退款率，保留 4 位小数。"},
        "environment": {"fixture_path": "fixtures/business_data/analytics_orders.csv",
                        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
        "oracle": {"expected_columns": list(oracle_columns),
                   "expected_rows": [["A", 0.2], ["B", 0.31]],
                   "column_tolerance": tolerance},
        "provenance": {"kind": "synthetic", "source_ref": "fixtures/business_data/analytics_orders.csv"},
        "label_status": "draft",
    }, ensure_ascii=False), encoding="utf-8")

    trial_dir = tmp_path / "runs/trials/t1"
    trial_dir.mkdir(parents=True)
    trace = trial_dir / "trace.jsonl"
    spans = [{
        "trace_id": "a" * 32, "span_id": "b" * 16, "parent_span_id": None,
        "name": "agent.request", "start_time": "2026-11-03T00:00:00Z",
        "end_time": "2026-11-03T00:00:01Z",
        "attributes": {"task_id": "nl2sql_test_001", "termination_reason": "completed"},
    }]
    for index, (columns, rows, truncated, security) in enumerate(runs):
        common = {"operation_id": f"op{index}", "attempt": 1, "raw_status": "ok",
                  "duration_ms": 1, "query": "SELECT ..."}
        if security:
            attributes = {**common, "outcome": "security_rejected"}
        else:
            attributes = {**common, "outcome": "success",
                          "result_set": {"outcome": "success", "columns": list(columns),
                                         "rows": rows, "row_count": len(rows),
                                         "truncated": truncated}}
        spans.append({"trace_id": "a" * 32, "span_id": f"{index + 0xC0:016x}",
                      "parent_span_id": "b" * 16, "name": "tool.run_sql",
                      "start_time": "2026-11-03T00:00:00Z",
                      "end_time": "2026-11-03T00:00:01Z", "attributes": attributes})
    trace.write_text("".join(json.dumps(span) + "\n" for span in spans))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"trial_id": "t1", "task_id": "nl2sql_test_001", "task_sha256": digest(task),
              "fixture_sha256": digest(fixture),
              "trace_path": "runs/trials/t1/trace.jsonl", "trace_sha256": digest(trace),
              "trace_id": "a" * 32, "status": "completed", "termination_reason": "completed",
              "final_answer": "A: 20%, B: 31%"}
    return task, record


def test_nl2sql_result_set_match_passes(tmp_path):
    task, record = _prepare(tmp_path, runs=[(["store_id", "refund_rate"],
                                              [["B", 0.31], ["A", 0.2]], False, False)])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True


def test_nl2sql_rounding_tolerance_passes(tmp_path):
    # 4 位小数舍入：模型给未舍入 0.3103，Oracle 0.31，容差 1e-3 内应通过。
    task, record = _prepare(tmp_path, runs=[(["store_id", "refund_rate"],
                                              [["B", 0.3103], ["A", 0.2]], False, False)])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True


def test_nl2sql_column_case_insensitive_passes(tmp_path):
    # 列名大小写不敏感：模型输出 Category/Refund_Rate，Oracle 是 Category/Refund_Rate。
    task, record = _prepare(
        tmp_path,
        oracle_columns=("category", "refund_rate"),
        runs=[(["Category", "Refund_Rate"], [["B", 0.31], ["A", 0.2]], False, False)],
    )
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True


def test_nl2sql_truncated_probe_then_correct_wins(tmp_path):
    # 先跑一个被截断的同列查询，再跑正确查询：应取正确的非截断结果。
    task, record = _prepare(tmp_path, runs=[
        (["store_id", "refund_rate"], [["X", 9.9]], True, False),
        (["store_id", "refund_rate"], [["B", 0.31], ["A", 0.2]], False, False),
    ])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True


def test_nl2sql_truncated_result_fails(tmp_path):
    task, record = _prepare(tmp_path, runs=[(["store_id", "refund_rate"],
                                              [["B", 0.31], ["A", 0.2]], True, False)])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is False


def test_nl2sql_security_rejection_fails(tmp_path):
    task, record = _prepare(tmp_path, runs=[
        (["store_id", "refund_rate"], [["B", 0.31], ["A", 0.2]], False, False),
        (["store_id", "refund_rate"], [], False, True),
    ])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is False
