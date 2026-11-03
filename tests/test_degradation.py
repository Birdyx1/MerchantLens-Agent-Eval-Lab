from merchant_agent.evaluation.degradation import detect_degradation


def _report(*, delta, old=1.0, new=1.0, safety=None, failures=None):
    return {
        "baseline": {"success_rate": old},
        "candidate": {"success_rate": new},
        "delta_success_rate": delta,
        "safety": safety,
        "candidate_failures": failures or {},
    }


def test_no_degradation_when_clean():
    result = detect_degradation(_report(delta=0.0))
    assert result["degraded"] is False


def test_success_rate_drop_is_degradation():
    result = detect_degradation(_report(delta=-0.25, old=1.0, new=0.75))
    assert result["degraded"] is True
    assert result["alerts"][0]["type"] == "success_rate_regression"


def test_safety_veto_is_critical_and_degraded():
    result = detect_degradation(_report(
        delta=0.0, safety={"passed": False, "violations": [{"case_id": "c1"}]}))
    assert result["degraded"] is True
    assert result["alerts"][0]["severity"] == "critical"
    assert result["alerts"][0]["type"] == "safety_regression"


def test_safety_pass_does_not_alert():
    result = detect_degradation(_report(delta=0.0, safety={"passed": True, "violations": []}))
    assert result["degraded"] is False


def test_candidate_failures_are_info_only():
    result = detect_degradation(_report(delta=0.0, failures={"amount_correct": 2}))
    assert result["degraded"] is False
    assert result["alerts"][0]["severity"] == "info"


def test_safety_veto_wins_over_positive_delta():
    result = detect_degradation(_report(
        delta=0.1, safety={"passed": False, "violations": []}))
    assert result["degraded"] is True
    assert result["alerts"][0]["severity"] == "critical"
