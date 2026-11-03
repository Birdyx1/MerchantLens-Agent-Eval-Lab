"""标准评测报告：把批次、安全门禁、退化告警与数据飞轮证据汇总成一份可复现报告。"""

from datetime import datetime, timezone


def build_report(*, batch_id: str, safety: dict | None, degradation: dict | None,
                 anomaly_summary: dict | None, candidates: int,
                 repro_commands: list[str]) -> dict:
    """组装结构化报告；所有结论都必须来自传入的真实证据。"""
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "safety": safety,
        "degradation": degradation,
        "anomaly_summary": anomaly_summary,
        "candidates": candidates,
        "repro_commands": repro_commands,
    }


def render(report: dict) -> str:
    """渲染 Markdown；安全结论置顶，未提供的证据明确写「未提供」。"""
    lines = [f"# 标准评测报告：{report['batch_id']}", "",
             f"生成时间：{report['generated_at']}", ""]

    safety = report.get("safety")
    if safety:
        if safety.get("passed"):
            lines.append("> **安全门禁：PASS**")
        else:
            lines.append("> **安全门禁：VETO**")
            for violation in safety.get("violations", []):
                lines.append(f"> - `{violation.get('case_id')}`：{violation.get('reason')}")
    else:
        lines.append("> **安全门禁：未提供**（不得解释为安全通过）")
    lines.append("")

    degradation = report.get("degradation")
    if degradation:
        lines.append(f"> **退化告警：{'是' if degradation.get('degraded') else '无'}**")
        for alert in degradation.get("alerts", []):
            lines.append(f"> - [{alert['severity']}] {alert['type']}：{alert['detail']}")
    else:
        lines.append("> **退化告警：未提供**")
    lines.append("")

    anomaly = report.get("anomaly_summary")
    lines += ["## 数据飞轮", ""]
    if anomaly:
        lines.append(f"- 异常总数：{anomaly.get('total', 0)}")
        for kind, count in (anomaly.get("by_type") or {}).items():
            lines.append(f"  - {kind}: {count}")
    else:
        lines.append("- 异常统计：未提供")
    lines.append(f"- 待标注候选：{report.get('candidates', 0)}")
    lines.append("")

    lines += ["## 复现命令", ""]
    if report.get("repro_commands"):
        lines += ["```bash"] + list(report["repro_commands"]) + ["```"]
    else:
        lines.append("- 未提供")
    lines.append("")
    return "\n".join(lines)
