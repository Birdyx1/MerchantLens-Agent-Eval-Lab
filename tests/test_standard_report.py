from merchant_agent.evaluation.standard_report import build_report, render


def _report(**overrides):
    base = dict(batch_id="b1", safety={"passed": True, "violations": []},
                degradation={"degraded": False, "alerts": []},
                anomaly_summary={"total": 3, "by_type": {"tool_failure": 3}},
                candidates=2, repro_commands=["pytest -q"])
    base.update(overrides)
    return build_report(**base)


def test_safety_veto_rendered_at_top():
    text = render(_report(safety={"passed": False,
                                  "violations": [{"case_id": "c1", "reason": "write"}]}))
    assert "安全门禁：VETO" in text
    assert text.index("VETO") < text.index("## 数据飞轮")


def test_missing_safety_is_not_pass():
    text = render(_report(safety=None))
    assert "安全门禁：未提供" in text
    assert "安全门禁：PASS" not in text


def test_degradation_alerts_rendered():
    text = render(_report(degradation={"degraded": True, "alerts": [
        {"severity": "critical", "type": "safety_regression", "detail": "x"}]}))
    assert "退化告警：是" in text
    assert "[critical] safety_regression" in text


def test_repro_commands_rendered():
    text = render(_report(repro_commands=["pytest -q", "uvicorn api:app"]))
    assert "pytest -q" in text
    assert "uvicorn api:app" in text


def test_anomaly_summary_rendered():
    text = render(_report())
    assert "异常总数：3" in text
    assert "tool_failure: 3" in text
