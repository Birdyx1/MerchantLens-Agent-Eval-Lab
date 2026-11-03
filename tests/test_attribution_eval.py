import hashlib
import json
from pathlib import Path

from merchant_agent.evaluation.code_evaluator import evaluate_trial


ROOT = Path(__file__).resolve().parents[1]
FACTS = [
    {"label": "最高退款率品类=零售", "all_of": ["零售", "退款率"]},
    {"label": "零售下最高渠道=堂食", "all_of": ["堂食"]},
]


def _prepare(tmp_path, *, answer, queries, security=False):
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json",
        "schemas/span.schema.json", "rubrics/attribution_v1.json",
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
        "task_id": "attribution_test_001",
        "task_type": "attribution",
        "rubric_id": "attribution_v1",
        "rubric_sha256": hashlib.sha256((ROOT / "rubrics/attribution_v1.json").read_bytes()).hexdigest(),
        "input": {"user_request": "哪个品类退款率最高，该品类下哪个渠道最高？"},
        "environment": {"fixture_path": "fixtures/business_data/analytics_orders.csv",
                        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
        "oracle": {"expected_facts": FACTS,
                   "required_query_evidence": ["category", "channel"]},
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
        "attributes": {"task_id": "attribution_test_001", "termination_reason": "completed"},
    }]
    for index, query in enumerate(queries):
        common = {"operation_id": f"op{index}", "attempt": 1, "raw_status": "ok",
                  "duration_ms": 1, "query": query}
        if security:
            attributes = {**common, "outcome": "security_rejected"}
        else:
            attributes = {**common, "outcome": "success",
                          "result_set": {"outcome": "success",
                                         "columns": ["x"], "rows": [[1]],
                                         "row_count": 1, "truncated": False}}
        spans.append({"trace_id": "a" * 32, "span_id": f"{index + 0xC0:016x}",
                      "parent_span_id": "b" * 16, "name": "tool.run_sql",
                      "start_time": "2026-11-03T00:00:00Z",
                      "end_time": "2026-11-03T00:00:01Z", "attributes": attributes})
    trace.write_text("".join(json.dumps(span) + "\n" for span in spans))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"trial_id": "t1", "task_id": "attribution_test_001", "task_sha256": digest(task),
              "fixture_sha256": digest(fixture),
              "trace_path": "runs/trials/t1/trace.jsonl", "trace_sha256": digest(trace),
              "trace_id": "a" * 32, "status": "completed", "termination_reason": "completed",
              "final_answer": answer}
    return task, record


QUERIES = [
    "SELECT category, SUM(refunded_fen) * 1.0 / SUM(paid_fen) AS r FROM orders GROUP BY category",
    "SELECT channel, SUM(refunded_fen) * 1.0 / SUM(paid_fen) AS r FROM orders "
    "WHERE category = '零售' GROUP BY channel",
]
ANSWER = "零售品类退款率最高（3.17%），其中堂食渠道最高（3.90%）。"


def test_attribution_facts_and_evidence_pass(tmp_path):
    task, record = _prepare(tmp_path, answer=ANSWER, queries=QUERIES)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True


def test_attribution_missing_fact_fails(tmp_path):
    task, record = _prepare(tmp_path, answer="零售品类退款率最高（3.17%）。", queries=QUERIES)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is False


def test_attribution_missing_query_evidence_fails(tmp_path):
    # 只查了 category，没有 channel 证据 → 失败。
    task, record = _prepare(tmp_path, answer=ANSWER, queries=[QUERIES[0]])
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is False


def test_attribution_security_rejection_fails(tmp_path):
    task, record = _prepare(tmp_path, answer=ANSWER, queries=QUERIES, security=True)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is False
