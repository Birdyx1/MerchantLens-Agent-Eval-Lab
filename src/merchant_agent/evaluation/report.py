"""同题双批次的首版规则评测报告。"""

from collections import Counter


def compare_batches(baseline: dict, candidate: dict, safety: dict | None = None) -> dict:
    """只比较同集合、同 Task 快照和同重复次数的完整批次。"""
    if baseline.get("status") != "completed" or candidate.get("status") != "completed":
        raise ValueError("只能比较完整批次")
    for key in ("collection", "repeats", "manifest"):
        if baseline.get(key) != candidate.get(key):
            raise ValueError("两个批次的集合、重复次数或 Task 快照不一致")
    for batch in (baseline, candidate):
        if len(batch.get("items", [])) != len(batch["manifest"]) * batch["repeats"]:
            raise ValueError("批次 Trial 数量不完整")
        if any(item.get("score") is None or item.get("metrics") is None for item in batch["items"]):
            raise ValueError("批次存在未评分 Trial")
    failures = Counter()
    for item in candidate["items"]:
        score = item["score"]
        if not score["passed"]:
            for criterion in score["criteria"]:
                if not criterion["passed"]:
                    failures[criterion["id"]] += 1
            if item["trial_status"] != "completed":
                failures[f"trial_status:{item['trial_status']}"] += 1
    old = baseline["aggregate"]["overall_success_rate"]
    new = candidate["aggregate"]["overall_success_rate"]
    return {
        "collection": candidate["collection"], "tasks": len(candidate["manifest"]),
        "repeats": candidate["repeats"],
        "baseline": {"batch_id": baseline["batch_id"], "model_version": baseline["model_version"],
                     "harness_version": baseline["harness_version"], "success_rate": old},
        "candidate": {"batch_id": candidate["batch_id"], "model_version": candidate["model_version"],
                      "harness_version": candidate["harness_version"], "success_rate": new},
        "delta_success_rate": new - old,
        "candidate_failures": dict(sorted(failures.items())),
        "candidate_safety_gate": candidate["aggregate"]["safety"]["release_gate"],
        "safety": safety,
        "evidence": [item["trial_id"] for item in candidate["items"]],
    }


def render_markdown(report: dict) -> str:
    """给出可以审阅的首版摘要；不把小样本差值写成显著提升。"""
    old, new = report["baseline"], report["candidate"]
    lines = ["# 首版 Agent 规则评测报告", ""]
    # 安全一票否决结论放在顶部：任何违规都比通过率优先。
    safety = report.get("safety")
    if safety:
        if safety.get("passed"):
            lines.append("> **安全门禁：PASS**（未发现安全违规）")
        else:
            lines.append("> **安全门禁：VETO**（以下违规一票否决本次发布）")
            for violation in safety.get("violations", []):
                lines.append(f"> - `{violation.get('case_id')}`：{violation.get('reason')}")
        lines.append("")
    lines += [
        f"集合：{report['collection']}；Task 数：{report['tasks']}；每题重复：{report['repeats']}。", "",
        "| 配置 | 模型 | Harness | 总体通过率 |", "|---|---|---|---:|",
        f"| 基线 | {old['model_version']} | {old['harness_version']} | {old['success_rate']:.1%} |",
        f"| 候选 | {new['model_version']} | {new['harness_version']} | {new['success_rate']:.1%} |", "",
        f"通过率差值：{report['delta_success_rate']:+.1%}。小样本差值不等于统计显著提升。", "",
        "## 候选版本失败判据", ""]
    lines.extend(f"- {key}: {count}" for key, count in report["candidate_failures"].items())
    if not report["candidate_failures"]:
        lines.append("- 无")
    lines += ["", f"安全门禁：{report['candidate_safety_gate']}。未知不得解释为安全通过。", "",
              f"证据批次：{old['batch_id']}、{new['batch_id']}。", ""]
    return "\n".join(lines)
