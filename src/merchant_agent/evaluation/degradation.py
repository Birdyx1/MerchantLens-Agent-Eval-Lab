"""回归与退化告警：比较版本变化，检测通过率下降与安全退化。"""


def detect_degradation(report: dict) -> dict:
    """根据 compare_batches 的 report 检测退化并给出告警。

    规则：
    - 安全门禁 veto → critical（一票否决，优先于通过率）；
    - 通过率下降 → warning；
    - 候选出现失败判据 → info。
    任一 critical 或通过率下降即视为 degraded。
    """
    alerts = []
    safety = report.get("safety")
    if safety and not safety.get("passed"):
        alerts.append({
            "type": "safety_regression",
            "severity": "critical",
            "detail": f"安全门禁 VETO（{len(safety.get('violations', []))} 条违规）",
        })
    delta = report.get("delta_success_rate", 0.0)
    if delta < 0:
        alerts.append({
            "type": "success_rate_regression",
            "severity": "warning",
            "detail": (f"通过率 {report['baseline']['success_rate']:.1%} → "
                       f"{report['candidate']['success_rate']:.1%}（{delta:+.1%}）"),
        })
    failures = report.get("candidate_failures") or {}
    if failures:
        alerts.append({
            "type": "candidate_failures",
            "severity": "info",
            "detail": failures,
        })
    degraded = any(alert["severity"] == "critical" for alert in alerts) or delta < 0
    return {"degraded": degraded, "alerts": alerts}
