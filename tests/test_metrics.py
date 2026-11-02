import hashlib
import json

import pytest

from merchant_agent.evaluation.metrics import aggregate_metrics, trial_metrics


def _evidence(tmp_path, *, missing_tokens=False, rejection=False):
    trace = tmp_path / "runs/trials/trial_001/trace.jsonl"
    trace.parent.mkdir(parents=True)
    model_attrs = {"input_tokens": 12, "output_tokens": 4}
    if missing_tokens:
        model_attrs.pop("input_tokens")
    spans = [
        {"name": "model.plan", "attributes": model_attrs},
        {"name": "tool.get_store_net", "attributes": {"outcome": "security_rejected" if rejection else "success"}},
        {"name": "agent.request", "attributes": {"duration_ms": 85}},
    ]
    trace.write_text("".join(json.dumps(span) + "\n" for span in spans))
    trial = {"trial_id": "trial_001", "task_id": "task_001",
             "trace_path": "runs/trials/trial_001/trace.jsonl",
             "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}
    score = {"trial_id": "trial_001", "task_id": "task_001", "trace_valid": True,
             "passed": True, "criteria": [
                 {"check_key": "answer_amount_equals_oracle", "passed": True},
                 {"check_key": "required_tool_call", "passed": True},
                 {"check_key": "answer_matches_tool_result", "passed": True},
             ]}
    return trial, score


def test_four_metric_families_and_unknown_safety(tmp_path):
    trial, score = _evidence(tmp_path)
    row = trial_metrics(trial, score, project_root=tmp_path)
    assert (row["result_success"], row["trajectory_success"], row["overall_success"]) == (True, True, True)
    assert (row["input_tokens"], row["output_tokens"], row["total_tokens"]) == (12, 4, 16)
    assert (row["latency_ms"], row["tool_calls"], row["security_rejections"]) == (85, 1, 0)
    assert row["safety_status"] == "unknown"
    assert aggregate_metrics([row])["safety"]["release_gate"] == "unknown"


def test_missing_token_evidence_is_unknown_not_zero(tmp_path):
    trial, score = _evidence(tmp_path, missing_tokens=True)
    row = trial_metrics(trial, score, project_root=tmp_path)
    assert row["input_tokens"] is None and row["total_tokens"] is None
    summary = aggregate_metrics([row])
    assert summary["cost"]["total_tokens"] == {"mean": None, "observed": 0}


def test_security_rejection_does_not_mean_safety_pass(tmp_path):
    trial, score = _evidence(tmp_path, rejection=True)
    row = trial_metrics(trial, score, project_root=tmp_path)
    assert row["security_rejections"] == 1
    assert row["safety_status"] == "unknown"
    violation = {**row, "trial_id": "trial_002", "safety_status": "violation"}
    assert aggregate_metrics([row, violation])["safety"]["release_gate"] == "fail"


def test_failure_stays_in_denominator_and_untrusted_cost_is_missing(tmp_path):
    trial, score = _evidence(tmp_path)
    passed = trial_metrics(trial, score, project_root=tmp_path, safety_verdict="pass")
    failed_trial = {**trial, "trial_id": "trial_002", "trace_sha256": "0" * 64}
    failed_score = {**score, "trial_id": "trial_002", "trace_valid": False, "passed": False,
                    "criteria": [{"check_key": item["check_key"], "passed": False}
                                 for item in score["criteria"]]}
    failed = trial_metrics(failed_trial, failed_score, project_root=tmp_path, safety_verdict="unknown")
    summary = aggregate_metrics([passed, failed])
    assert summary["trials"] == 2
    assert summary["overall_success_rate"] == 0.5
    assert summary["cost"]["total_tokens"] == {"mean": 16.0, "observed": 1}


def test_score_trial_identity_mismatch_is_rejected(tmp_path):
    trial, score = _evidence(tmp_path)
    score["task_id"] = "different"
    with pytest.raises(ValueError, match="不匹配"):
        trial_metrics(trial, score, project_root=tmp_path)
