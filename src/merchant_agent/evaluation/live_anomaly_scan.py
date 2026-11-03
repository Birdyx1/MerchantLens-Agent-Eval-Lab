"""扫描真实 Trial 目录，识别并汇总异常（教师代写，9.1 真实验证）。"""

import json
from pathlib import Path

from merchant_agent.evaluation.anomaly import collect_anomalies, summarize

ROOT = Path(__file__).resolve().parents[3]
TRIALS = ROOT / "runs" / "trials"


def main() -> dict:
    """只扫描存在 trace.jsonl 的 Trial；返回汇总与异常明细。"""
    findings = []
    for trial_path in sorted(TRIALS.glob("*/trial.json")):
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        trace_path = trial_path.parent / "trace.jsonl"
        spans = []
        if trace_path.is_file():
            spans = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
                     if line.strip()]
        anomalies = collect_anomalies(trial, spans)
        if anomalies:
            findings.append({"trial_id": trial.get("trial_id"),
                             "task_id": trial.get("task_id"), "anomalies": anomalies})
    all_anomalies = [a for finding in findings for a in finding["anomalies"]]
    result = {"scanned_trials": len(list(TRIALS.glob("*/trial.json"))),
              "trials_with_anomalies": len(findings),
              "summary": summarize(all_anomalies),
              "findings": findings}
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    return result


if __name__ == "__main__":
    main()
