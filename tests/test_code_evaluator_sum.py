import hashlib
import json
from pathlib import Path

from merchant_agent.evaluation.code_evaluator import evaluate_trial


ROOT = Path(__file__).resolve().parents[1]


def _case(tmp_path, *, answer="门店 A 和 B 的净收入合计为 20000 分",
          calls=(("A", 12000), ("B", 8000))):
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json", "schemas/span.schema.json",
        "rubrics/store_net_sum_v1.json", "fixtures/business_data/orders.csv",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task = tmp_path / "task.json"
    task.write_bytes((ROOT / "fixtures/eval_task_trap/trap_store_net_sum_ab_001.json").read_bytes())
    trace = tmp_path / "runs/trials/trial_001/trace.jsonl"
    trace.parent.mkdir(parents=True)
    root_span = {"trace_id": "a" * 32, "span_id": "b" * 16, "parent_span_id": None,
                 "name": "agent.request", "start_time": "2026-11-02T00:00:00Z",
                 "end_time": "2026-11-02T00:00:01Z",
                 "attributes": {"task_id": "trap_store_net_sum_ab_001", "termination_reason": "completed"}}
    tool_spans = []
    for index, (store_id, result_fen) in enumerate(calls):
        tool_spans.append({
            "trace_id": "a" * 32, "span_id": chr(ord("c") + index) * 16,
            "parent_span_id": "b" * 16, "name": "tool.get_store_net",
            "start_time": "2026-11-02T00:00:00Z", "end_time": "2026-11-02T00:00:01Z",
            "attributes": {"store_id": store_id, "outcome": "success", "result_fen": result_fen},
        })
    trace.write_text("".join(json.dumps(span) + "\n" for span in tool_spans + [root_span]))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"trial_id": "trial_001", "task_id": "trap_store_net_sum_ab_001",
              "task_sha256": digest(task),
              "fixture_sha256": digest(tmp_path / "fixtures/business_data/orders.csv"),
              "trace_path": "runs/trials/trial_001/trace.jsonl", "trace_sha256": digest(trace),
              "trace_id": "a" * 32, "status": "completed", "termination_reason": "completed",
              "final_answer": answer}
    return task, record


def test_two_calls_and_correct_sum_pass(tmp_path):
    task, record = _case(tmp_path)
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["passed"] is True
    assert result["answer_amount_fen"] == 20000
    assert [item["passed"] for item in result["criteria"]] == [True, True, True]


def test_single_call_fails_tool_requirement(tmp_path):
    task, record = _case(tmp_path, calls=(("A", 12000),))
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert [item["passed"] for item in result["criteria"]] == [True, False, False]
    assert result["passed"] is False


def test_wrong_total_fails_result(tmp_path):
    task, record = _case(tmp_path, answer="门店 A 和 B 的净收入合计为 18000 分")
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert [item["passed"] for item in result["criteria"]] == [False, True, False]
    assert result["passed"] is False


def test_answer_not_matching_tool_sum_fails(tmp_path):
    task, record = _case(tmp_path, calls=(("A", 12000), ("B", 8000)),
                         answer="门店 A 和 B 的净收入合计为 20000 分")
    # 合计与 Oracle 一致，但把 B 的工具返回值改成 9000，回答 20000 就不再等于工具和。
    trace = tmp_path / "runs/trials/trial_001/trace.jsonl"
    spans = [json.loads(line) for line in trace.read_text().splitlines()]
    for span in spans:
        if span.get("name") == "tool.get_store_net" and span["attributes"]["store_id"] == "B":
            span["attributes"]["result_fen"] = 9000
    trace.write_text("".join(json.dumps(span) + "\n" for span in spans))
    digest = hashlib.sha256(trace.read_bytes()).hexdigest()
    record["trace_sha256"] = digest
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["criteria"][2]["check_key"] == "answer_matches_tool_sum"
    assert result["criteria"][2]["passed"] is False


def test_answer_with_breakdown_and_total_passes(tmp_path):
    # 多步题合理答案会同时给分项和合计：应识别“合计”金额而不是判为多个金额。
    task, record = _case(
        tmp_path,
        answer="门店 A 与门店 B 的净收入合计为 20000 分（门店 A：12000 分；门店 B：8000 分）。",
    )
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["answer_amount_fen"] == 20000
    assert result["passed"] is True


def test_multiple_totals_are_rejected(tmp_path):
    task, record = _case(tmp_path, answer="合计 20000 分，另一个合计 30000 分。")
    result = evaluate_trial(record, task, project_root=tmp_path)
    assert result["answer_amount_fen"] is None
    assert result["passed"] is False
