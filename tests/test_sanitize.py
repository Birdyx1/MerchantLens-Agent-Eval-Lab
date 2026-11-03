import pytest

from merchant_agent.evaluation.sanitize import (
    deduplicate,
    sanitize_text,
    sanitize_trial,
    tag_source,
)


def test_sanitize_text_masks_key_phone_email():
    text = "key=sk-abc12345 phone=13812345678 mail=a@b.com"
    cleaned = sanitize_text(text)
    assert "sk-abc12345" not in cleaned
    assert "13812345678" not in cleaned
    assert "a@b.com" not in cleaned
    assert cleaned.count("[REDACTED_KEY]") == 1


def test_sanitize_text_leaves_normal_text():
    assert sanitize_text("门店 A 净收入 12000 分") == "门店 A 净收入 12000 分"


def test_sanitize_trial_does_not_mutate_input():
    trial = {"final_answer": "key=sk-abc12345"}
    spans = [{"attributes": {"query": "SELECT 1", "note": "a@b.com"}}]
    cleaned_trial, cleaned_spans = sanitize_trial(trial, spans)
    assert "sk-abc12345" not in cleaned_trial["final_answer"]
    assert trial["final_answer"] == "key=sk-abc12345"
    assert "a@b.com" not in cleaned_spans[0]["attributes"]["note"]


def test_deduplicate_collapses_same_task_and_types():
    findings = [
        {"task_id": "t1", "anomalies": [{"type": "tool_failure"}]},
        {"task_id": "t1", "anomalies": [{"type": "tool_failure"}]},
        {"task_id": "t2", "anomalies": [{"type": "tool_failure"}]},
    ]
    deduped = deduplicate(findings)
    assert len(deduped) == 2
    assert deduped[0]["duplicates"] == 2


def test_tag_source_validates():
    assert tag_source({"task_id": "t1"}, source="synthetic")["source"] == "synthetic"
    with pytest.raises(ValueError):
        tag_source({"task_id": "t1"}, source="unknown")
