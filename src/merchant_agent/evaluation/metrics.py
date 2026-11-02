"""从可信 Trial 证据计算结果、轨迹、成本与安全指标。"""

import hashlib
from pathlib import Path

from merchant_agent.tracing.reader import read_spans


def trial_metrics(trial: dict, score: dict, *, project_root: Path,
                  safety_verdict: str = "unknown") -> dict:
    """计算单次指标；证据缺失用 None 表示未知，不伪造零成本。"""
    if safety_verdict not in {"pass", "violation", "unknown"}:
        raise ValueError("安全结论必须是 pass、violation 或 unknown")
    if trial.get("trial_id") != score.get("trial_id") or trial.get("task_id") != score.get("task_id"):
        raise ValueError("Trial 与评分不匹配")
    root = project_root.resolve()
    relative = Path(trial["trace_path"])
    trace_path = (root / relative).resolve()
    if relative.is_absolute() or not trace_path.is_relative_to(root / "runs" / "trials"):
        raise ValueError("Trace 路径越界")
    trusted = bool(score.get("trace_valid")) and trace_path.is_file() and (
        hashlib.sha256(trace_path.read_bytes()).hexdigest() == trial.get("trace_sha256")
    )
    spans = read_spans(str(trace_path)) if trusted else []
    model_spans = [span for span in spans if span.get("name") == "model.plan"]
    tool_spans = [span for span in spans if str(span.get("name", "")).startswith("tool.")]
    root_spans = [span for span in spans if span.get("name") == "agent.request"]
    def token_sum(key: str) -> int | None:
        if not trusted or not model_spans:
            return None
        values = [span.get("attributes", {}).get(key) for span in model_spans]
        if any(type(value) is not int or value < 0 for value in values):
            return None
        return sum(values)
    input_tokens = token_sum("input_tokens")
    output_tokens = token_sum("output_tokens")
    latency = root_spans[0].get("attributes", {}).get("duration_ms") if trusted and len(root_spans) == 1 else None
    if type(latency) is not int or latency < 0:
        latency = None
    criteria = {item["check_key"]: item["passed"] for item in score.get("criteria", [])}
    trajectory = (bool(criteria.get("required_tool_call")) and
                  bool(criteria.get("answer_matches_tool_result")))
    return {
        "trial_id": trial["trial_id"],
        "task_id": trial["task_id"],
        "result_success": bool(criteria.get("answer_amount_equals_oracle")),
        "trajectory_success": trajectory,
        "overall_success": bool(score.get("passed")),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None,
        "latency_ms": latency,
        "tool_calls": len(tool_spans) if trusted else None,
        "security_rejections": sum(span.get("attributes", {}).get("outcome") == "security_rejected"
                                   for span in tool_spans) if trusted else None,
        "safety_status": safety_verdict,
    }


def aggregate_metrics(rows: list[dict]) -> dict:
    """按全部 Trial 作结果分母；成本仅在有观测值的样本上求均值。"""
    count = len(rows)
    def rate(key: str) -> float | None:
        return sum(bool(row[key]) for row in rows) / count if count else None
    def observed_mean(key: str) -> dict:
        values = [row[key] for row in rows if row[key] is not None]
        return {"mean": sum(values) / len(values) if values else None, "observed": len(values)}
    statuses = [row["safety_status"] for row in rows]
    return {
        "trials": count,
        "result_success_rate": rate("result_success"),
        "trajectory_success_rate": rate("trajectory_success"),
        "overall_success_rate": rate("overall_success"),
        "cost": {key: observed_mean(key) for key in ("total_tokens", "latency_ms", "tool_calls")},
        "safety": {
            "violations": statuses.count("violation"),
            "unknown": statuses.count("unknown"),
            "release_gate": "fail" if "violation" in statuses else (
                "unknown" if not statuses or "unknown" in statuses else "pass"
            ),
        },
    }
