import hashlib
import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.code_evaluator import evaluate_trial


ROOT = Path(__file__).resolve().parents[1]


def _case(tmp_path, *, answer="门店 A 净收入为 12000 分", store_id="A", result_fen=12000,
          include_tool=True):
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json", "schemas/span.schema.json",
        "rubrics/store_net_v1.json", "fixtures/business_data/orders.csv",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task = tmp_path / "task.json"
    task.write_bytes((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes())
    trace = tmp_path / "runs/trials/trial_001/trace.jsonl"
    trace.parent.mkdir(parents=True)
    root_span = {"trace_id": "a" * 32, "span_id": "b" * 16, "parent_span_id": None,
                 "name": "agent.request", "start_time": "2026-11-02T00:00:00Z",
                 "end_time": "2026-11-02T00:00:01Z",
                 "attributes": {"task_id": "store_net_a_001", "termination_reason": "completed"}}
    tool_span = {"trace_id": "a" * 32, "span_id": "c" * 16, "parent_span_id": "b" * 16,
                 "name": "tool.get_store_net", "start_time": "2026-11-02T00:00:00Z",
                 "end_time": "2026-11-02T00:00:01Z",
                 "attributes": {"store_id": store_id, "outcome": "success", "result_fen": result_fen}}
    spans = ([tool_span] if include_tool else []) + [root_span]
    trace.write_text("".join(json.dumps(span) + "\n" for span in spans))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"trial_id": "trial_001", "task_id": "store_net_a_001", "task_sha256": digest(task),
              "fixture_sha256": digest(tmp_path / "fixtures/business_data/orders.csv"),
              "trace_path": "runs/trials/trial_001/trace.jsonl", "trace_sha256": digest(trace),
              "trace_id": "a" * 32, "status": "completed", "termination_reason": "completed",
              "final_answer": answer}
    return task, trace, record


def test_correct_answer_and_evidence_pass(tmp_path):
    task, _, record = _case(tmp_path)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True
    assert [item["passed"] for item in result["criteria"]] == [True, True, True]


def test_grouped_thousands_amount_is_accepted(tmp_path):
    task, _, record = _case(tmp_path, answer="门店 A 净收入为 12,000 分")
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True
    assert result["answer_amount_fen"] == 12000


def test_malformed_grouping_is_not_partially_parsed(tmp_path):
    task, _, record = _case(tmp_path, answer="门店 A 净收入为 12,00 分")
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["answer_amount_fen"] is None
    assert result["passed"] is False


@pytest.mark.parametrize("changes, expected", [
    ({"include_tool": False}, [True, False, False]),
    ({"store_id": "B"}, [True, False, False]),
    ({"result_fen": 11000}, [True, True, False]),
    ({"answer": "门店 A 为 11000 分"}, [False, True, False]),
    ({"answer": "可能是 12000 分或 11000 分"}, [False, True, False]),
])
def test_result_and_process_fail_independently(tmp_path, changes, expected):
    task, _, record = _case(tmp_path, **changes)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert [item["passed"] for item in result["criteria"]] == expected
    assert result["passed"] is False


def test_changed_trace_is_not_trusted(tmp_path):
    task, trace, record = _case(tmp_path)
    trace.write_text(trace.read_text() + "\n")
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["trace_valid"] is False
    assert result["passed"] is False


def test_task_snapshot_mismatch_is_rejected(tmp_path):
    task, _, record = _case(tmp_path)
    record["task_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="快照"):
        evaluate_trial(record, task, project_root=tmp_path)
