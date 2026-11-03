"""从单次 Trial 与 Trace 识别异常候选，供后续标注与入库。"""

import re


_AMOUNT_PATTERN = re.compile(r"\d[\d,]*\s*分")
_FAILURE_OUTCOMES = frozenset({
    "invalid_input", "timeout", "dependency_error", "program_error", "security_rejected",
})
_BUDGET_REASONS = frozenset({"max_steps", "max_tokens"})


def collect_anomalies(trial: dict, spans: list[dict]) -> list[dict]:
    """返回异常列表；每条含 type/severity/detail。只识别，不判定业务对错。"""
    anomalies = []
    status = trial.get("status")
    if status != "completed":
        anomalies.append({"type": "trial_not_completed", "severity": "high",
                          "detail": status})
    reason = trial.get("termination_reason")
    if reason in _BUDGET_REASONS:
        anomalies.append({"type": "budget_exhausted", "severity": "medium",
                          "detail": reason})
    tool_spans = [span for span in spans if str(span.get("name", "")).startswith("tool.")]
    for span in tool_spans:
        outcome = span.get("attributes", {}).get("outcome")
        if outcome == "security_rejected":
            anomalies.append({"type": "security_rejected", "severity": "critical",
                              "detail": {"tool": span.get("name")}})
        elif outcome in _FAILURE_OUTCOMES:
            anomalies.append({"type": "tool_failure", "severity": "high",
                              "detail": {"tool": span.get("name"), "outcome": outcome}})
    # 无证据答案：回答里有金额，但没有任何成功的工具调用支撑。
    answer = trial.get("final_answer")
    if (isinstance(answer, str) and _AMOUNT_PATTERN.search(answer)
            and not any(span.get("attributes", {}).get("outcome") == "success"
                        for span in tool_spans)):
        anomalies.append({"type": "ungrounded_answer", "severity": "high",
                          "detail": "回答含金额但无成功工具调用"})
    return anomalies


def summarize(anomalies: list[dict]) -> dict:
    """按类型与严重度汇总，供批次级报告。"""
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for anomaly in anomalies:
        by_type[anomaly["type"]] = by_type.get(anomaly["type"], 0) + 1
        by_severity[anomaly["severity"]] = by_severity.get(anomaly["severity"], 0) + 1
    return {"total": len(anomalies), "by_type": by_type, "by_severity": by_severity}
