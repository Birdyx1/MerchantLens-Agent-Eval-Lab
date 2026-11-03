"""扫描 Trial 异常，脱敏、去重并标来源（9.2 真实验证，教师代写）。"""

import json
from pathlib import Path

from merchant_agent.evaluation.anomaly import collect_anomalies, summarize
from merchant_agent.evaluation.sanitize import deduplicate, sanitize_trial, tag_source

ROOT = Path(__file__).resolve().parents[3]
TRIALS = ROOT / "runs" / "trials"


def main() -> dict:
    """异常 Trial 先脱敏再入库候选；同一 (task, 异常类型) 去重。"""
    findings = []
    for trial_path in sorted(TRIALS.glob("*/trial.json")):
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        trace_path = trial_path.parent / "trace.jsonl"
        spans = []
        if trace_path.is_file():
            spans = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
                     if line.strip()]
        anomalies = collect_anomalies(trial, spans)
        if not anomalies:
            continue
        clean_trial, _ = sanitize_trial(trial, spans)
        findings.append(tag_source({
            "trial_id": trial.get("trial_id"),
            "task_id": trial.get("task_id"),
            "anomalies": anomalies,
            "final_answer": clean_trial.get("final_answer"),
        }, source="synthetic"))
    deduped = deduplicate(findings)
    result = {
        "scanned_trials": len(list(TRIALS.glob("*/trial.json"))),
        "anomaly_findings": len(findings),
        "deduped_candidates": len(deduped),
        "removed_duplicates": len(findings) - len(deduped),
        "summary": summarize([a for f in deduped for a in f["anomalies"]]),
        "candidates": deduped[:10],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    return result


if __name__ == "__main__":
    main()
