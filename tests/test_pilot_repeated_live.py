"""试点批次运行前必须冻结两个常规集合，且排除 Holdout。"""

from merchant_agent.evaluation.pilot_repeated_live import _freeze_plan


def test_pilot_plan_freezes_tasks_and_evaluators_without_holdout():
    plan = _freeze_plan("model-test", "harness-test")
    assert plan["repeats"] == 2
    assert plan["holdout_used"] is False
    assert len(plan["collections"]["golden"]) == 4
    assert len(plan["collections"]["regression"]) == 4
    assert "holdout" not in plan["collections"]
    assert all(len(digest) == 64 for digest in plan["evaluator_sha256"].values())
