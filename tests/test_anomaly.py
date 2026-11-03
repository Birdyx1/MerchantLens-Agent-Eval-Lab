from merchant_agent.evaluation.anomaly import collect_anomalies, summarize


def _trial(status="completed", reason="completed", answer="门店 A 净收入 12000 分"):
    return {"status": status, "termination_reason": reason, "final_answer": answer}


def _tool(name="tool.get_store_net", outcome="success"):
    return {"name": name, "attributes": {"outcome": outcome}}


def test_clean_trial_has_no_anomalies():
    assert collect_anomalies(_trial(), [_tool()]) == []


def test_trial_not_completed_flagged():
    anomalies = collect_anomalies(_trial(status="error", answer=None), [])
    assert anomalies[0]["type"] == "trial_not_completed"


def test_budget_exhausted_flagged():
    anomalies = collect_anomalies(_trial(reason="max_steps", answer=None), [])
    assert any(a["type"] == "budget_exhausted" for a in anomalies)


def test_tool_failure_flagged():
    anomalies = collect_anomalies(_trial(), [_tool(outcome="timeout")])
    assert any(a["type"] == "tool_failure" for a in anomalies)


def test_security_rejection_is_critical():
    anomalies = collect_anomalies(_trial(), [_tool(outcome="security_rejected")])
    assert anomalies[0]["type"] == "security_rejected"
    assert anomalies[0]["severity"] == "critical"


def test_ungrounded_amount_flagged_without_successful_tool():
    anomalies = collect_anomalies(_trial(answer="门店 A 净收入 12000 分"), [])
    assert any(a["type"] == "ungrounded_answer" for a in anomalies)


def test_summarize_counts_by_type_and_severity():
    anomalies = collect_anomalies(
        _trial(status="error", reason="max_steps", answer=None), [])
    summary = summarize(anomalies)
    assert summary["total"] == 2
    assert summary["by_severity"]["high"] == 1
    assert summary["by_severity"]["medium"] == 1
