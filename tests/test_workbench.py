import json

import pytest

from merchant_agent.evaluation.workbench import (
    Candidate,
    label_status,
    load_candidates,
    submit_label,
)


def _candidate():
    return Candidate(candidate_id="t1__tool_failure", task_id="t1",
                     anomaly_types=("tool_failure",), final_answer="12000 分")


def _label(tmp_path, reviewer="r1", badcase=True):
    return submit_label(_candidate(), reviewer_id=reviewer, is_real_badcase=badcase,
                        root_cause="工具参数错误", fix_direction="补参数校验",
                        root=tmp_path)


def test_load_candidates_builds_unique_id():
    findings = [{"task_id": "t1", "anomalies": [{"type": "b"}, {"type": "a"}],
                 "final_answer": "x"}]
    candidates = load_candidates(findings)
    assert candidates[0].candidate_id == "t1__a-b"
    assert candidates[0].anomaly_types == ("a", "b")


def test_submit_label_writes_and_immutable(tmp_path):
    path = _label(tmp_path)
    assert path.exists()
    with pytest.raises(FileExistsError):
        _label(tmp_path)


def test_pending_when_no_labels(tmp_path):
    assert label_status(_candidate(), root=tmp_path)["status"] == "pending"


def test_one_label_status(tmp_path):
    _label(tmp_path, "r1")
    assert label_status(_candidate(), root=tmp_path)["status"] == "one_label"


def test_agreed_status(tmp_path):
    _label(tmp_path, "r1", True)
    _label(tmp_path, "r2", True)
    assert label_status(_candidate(), root=tmp_path)["status"] == "agreed"


def test_disputed_status(tmp_path):
    _label(tmp_path, "r1", True)
    _label(tmp_path, "r2", False)
    assert label_status(_candidate(), root=tmp_path)["status"] == "disputed"


def test_empty_reason_rejected(tmp_path):
    with pytest.raises(ValueError):
        submit_label(_candidate(), reviewer_id="r1", is_real_badcase=True,
                     root_cause=" ", fix_direction="x", root=tmp_path)
