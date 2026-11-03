import pytest

from merchant_agent.evaluation.regression import derive_regression, verify_fix


def test_fix_verified_when_failed_then_passed():
    assert verify_fix(before_passed=False, after_passed=True)["status"] == "fixed"


def test_fix_not_verified_when_still_failing():
    assert verify_fix(before_passed=False, after_passed=False)["status"] == "not_fixed"


def test_reject_case_that_already_passed():
    with pytest.raises(ValueError, match="不是可回测"):
        verify_fix(before_passed=True, after_passed=True)


def _badcase(status="adjudicated"):
    return {"task_id": "badcase_t1", "task_type": "negative_input",
            "label_status": status, "rubric_id": "negative_input_v1"}


def test_derive_regression_from_adjudicated():
    regression = derive_regression(_badcase())
    assert regression["task_id"] == "regression_badcase_t1"
    assert regression["provenance"] == {"kind": "regression",
                                        "source_ref": "badcase_t1"}
    assert regression["rubric_id"] == "negative_input_v1"


def test_derive_regression_rejects_draft():
    with pytest.raises(ValueError, match="adjudicated"):
        derive_regression(_badcase(status="draft"))
