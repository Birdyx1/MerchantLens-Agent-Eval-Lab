import pytest

from merchant_agent.evaluation.judge_calibration import calibrate_panel, select_calibration_sample


def _panels():
    return [
        {"trial_id": "a", "status": "majority", "score": 2},
        {"trial_id": "b", "status": "majority", "score": 1},
        {"trial_id": "c", "status": "disagreement", "score": None},
        {"trial_id": "d", "status": "incomplete", "score": None},
    ]


def _label(trial_id, first, second, arbitration=None):
    return {"trial_id": trial_id,
            "first": {"reviewer_id": "human_a", "score": first},
            "second": {"reviewer_id": "human_b", "score": second},
            "adjudication": arbitration}


def test_sampling_is_reproducible_and_covers_flagged_first():
    first = select_calibration_sample(_panels(), sample_size=3, seed=9)
    second = select_calibration_sample(list(reversed(_panels())), sample_size=3, seed=9)
    assert first == second
    assert {"c", "d"} <= set(first["trial_ids"])
    assert first["population_flagged"] == 2 and first["sample_flagged"] == 2


def test_calibration_reports_human_agreement_and_judge_confusion():
    sample = {"trial_ids": ["a", "b"], "sample_size": 2}
    labels = [_label("a", 2, 2), _label("b", 2, 1,
              {"reviewer_id": "human_c", "score": 1, "reason": "对象不清楚"})]
    report = calibrate_panel(sample, _panels(), labels)
    assert report["human_raw_agreement"] == 0.5
    assert report["judge_exact_agreement"] == 1.0
    assert report["judge_comparable"] == 2
    assert all(not row["needs_review"] for row in report["review"])


def test_human_disagreement_requires_third_reviewer():
    sample = {"trial_ids": ["a"], "sample_size": 1}
    with pytest.raises(ValueError, match="第三人"):
        calibrate_panel(sample, _panels(), [_label("a", 1, 2)])


def test_unresolved_panel_is_not_counted_as_judge_agreement():
    sample = {"trial_ids": ["c"], "sample_size": 1}
    report = calibrate_panel(sample, _panels(), [_label("c", 2, 2)])
    assert report["judge_exact_agreement"] is None
    assert report["judge_comparable"] == 0
    assert report["review"][0]["needs_review"] is True
