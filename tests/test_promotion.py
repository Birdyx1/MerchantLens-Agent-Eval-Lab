from pathlib import Path

import pytest

from merchant_agent.evaluation.promotion import promote_badcase
from merchant_agent.evaluation.workbench import Candidate, submit_label


CAND = Candidate("t1__tool_failure", "t1", ("tool_failure",), None)


def _promote(tmp_path):
    return promote_badcase(
        CAND, labels_root=tmp_path / "labels", tasks_root=tmp_path / "tasks",
        task_type="negative_input", user_request="查询门店净收入",
        fixture_path="fixtures/business_data/orders.csv", fixture_sha256="abc",
        rubric_id="negative_input_v1", rubric_sha256="def",
    )


def _label(tmp_path, reviewer, badcase=True):
    submit_label(CAND, reviewer_id=reviewer, is_real_badcase=badcase,
                 root_cause="x", fix_direction="y", root=tmp_path / "labels")


def test_pending_candidate_rejected(tmp_path):
    with pytest.raises(ValueError, match="不是 agreed"):
        _promote(tmp_path)


def test_one_label_candidate_rejected(tmp_path):
    _label(tmp_path, "r1")
    with pytest.raises(ValueError, match="不是 agreed"):
        _promote(tmp_path)


def test_disputed_candidate_rejected(tmp_path):
    _label(tmp_path, "r1", True)
    _label(tmp_path, "r2", False)
    with pytest.raises(ValueError, match="不是 agreed"):
        _promote(tmp_path)


def test_agreed_non_badcase_rejected(tmp_path):
    _label(tmp_path, "r1", False)
    _label(tmp_path, "r2", False)
    with pytest.raises(ValueError, match="真实 badcase"):
        _promote(tmp_path)


def test_agreed_badcase_promotes(tmp_path):
    _label(tmp_path, "r1", True)
    _label(tmp_path, "r2", True)
    result = _promote(tmp_path)
    assert result.task_id == "badcase_t1__tool_failure"
    assert result.label_status == "agreed"
    assert result.task_path.exists()
    with pytest.raises(FileExistsError):
        _promote(tmp_path)
