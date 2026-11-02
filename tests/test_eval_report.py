import pytest

from merchant_agent.evaluation.report import compare_batches, render_markdown


def _batch(name, success):
    return {"batch_id": name, "status": "completed", "collection": "golden", "repeats": 2,
            "manifest": [{"task_id": "task_001", "sha256": "abc"}],
            "model_version": name, "harness_version": "h1",
            "aggregate": {"overall_success_rate": success, "safety": {"release_gate": "unknown"}},
            "items": [{"trial_id": f"{name}_trial_{index}", "trial_status": "completed",
                       "metrics": {"overall_success": bool(success)},
                       "score": {"passed": bool(success), "criteria": [
                           {"id": "amount_correct", "passed": bool(success)}]}}
                      for index in range(2)]}


def test_report_compares_same_manifest_and_lists_failure():
    report = compare_batches(_batch("baseline", 1.0), _batch("candidate", 0.0))
    assert report["delta_success_rate"] == -1.0
    assert report["candidate_failures"] == {"amount_correct": 2}
    text = render_markdown(report)
    assert "小样本差值不等于统计显著提升" in text
    assert "安全门禁：unknown" in text


def test_report_rejects_changed_task_snapshot():
    candidate = _batch("candidate", 0.0)
    candidate["manifest"][0]["sha256"] = "different"
    with pytest.raises(ValueError, match="不一致"):
        compare_batches(_batch("baseline", 1.0), candidate)
