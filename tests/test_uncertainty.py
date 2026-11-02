import pytest

from merchant_agent.evaluation.uncertainty import summarize_repeats, wilson_interval


def _rows():
    return [
        {"trial_id": f"a{i}", "task_id": "task_a", "overall_success": value}
        for i, value in enumerate((True, True, False))
    ] + [
        {"trial_id": f"b{i}", "task_id": "task_b", "overall_success": value}
        for i, value in enumerate((False, False, False))
    ]


def test_wilson_interval_is_bounded_at_extremes():
    assert wilson_interval(0, 3)[0] == 0
    assert wilson_interval(3, 3)[1] == 1
    assert wilson_interval(2, 3)[0] < 2 / 3 < wilson_interval(2, 3)[1]


def test_repeated_task_macro_and_seed_are_reproducible():
    first = summarize_repeats(_rows(), expected_repeats=3, seed=7)
    second = summarize_repeats(list(reversed(_rows())), expected_repeats=3, seed=7)
    assert first == second
    assert first["macro_success_rate"] == pytest.approx(1 / 3)
    assert first["tasks"] == 2 and first["trials"] == 6
    assert first["macro_task_bootstrap_interval"] is not None


def test_one_task_does_not_claim_cross_task_interval():
    result = summarize_repeats(_rows()[:3], expected_repeats=3)
    assert result["macro_task_bootstrap_interval"] is None
    assert result["per_task"][0]["wilson_interval"][0] < 2 / 3


def test_missing_repeat_or_duplicate_trial_is_rejected():
    with pytest.raises(ValueError, match="重复次数"):
        summarize_repeats(_rows()[:-1], expected_repeats=3)
    rows = _rows()
    rows[1]["trial_id"] = rows[0]["trial_id"]
    with pytest.raises(ValueError, match="重复 Trial ID"):
        summarize_repeats(rows, expected_repeats=3)
