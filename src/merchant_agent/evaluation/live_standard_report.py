"""生成标准评测报告（10.1）：汇总安全门禁、异常统计与候选清单。"""

import json
from pathlib import Path

from merchant_agent.evaluation.anomaly import collect_anomalies, summarize
from merchant_agent.evaluation.safety_gate import safety_gate
from merchant_agent.evaluation.standard_report import build_report, render

ROOT = Path(__file__).resolve().parents[3]
TRIALS = ROOT / "runs" / "trials"


def _latest(root: Path) -> Path:
    return max((path for path in root.iterdir() if path.is_dir()),
               key=lambda path: path.stat().st_mtime)


def _safety() -> dict:
    """复用 8.1a/8.2/8.3 的真实结果做安全门禁。"""
    items = []
    neg_dir = _latest(ROOT / "runs" / "negative_input_probe")
    semantic = {row["case_id"]: row.get("semantic")
                for row in json.loads((neg_dir / "semantic.json").read_text(encoding="utf-8"))}
    for row in json.loads((neg_dir / "results.json").read_text(encoding="utf-8"))["items"]:
        item = dict(row)
        if semantic.get(row["case_id"]):
            item["semantic"] = semantic[row["case_id"]]
        items.append(item)
    for name in ("prompt_injection_probe", "dangerous_action_probe"):
        latest = _latest(ROOT / "runs" / name)
        items += json.loads((latest / "results.json").read_text(encoding="utf-8"))["items"]
    return safety_gate(items)


def main() -> Path:
    anomalies = []
    for trial_path in sorted(TRIALS.glob("*/trial.json")):
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        trace = trial_path.parent / "trace.jsonl"
        spans = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()
                 if line.strip()] if trace.is_file() else []
        anomalies += collect_anomalies(trial, spans)
    candidates = json.loads((ROOT / "runs/workbench/candidates.json").read_text(encoding="utf-8"))
    report = build_report(
        batch_id="2026-11-03-multitype",
        safety=_safety(),
        degradation=None,
        anomaly_summary=summarize(anomalies),
        candidates=len(candidates),
        repro_commands=[
            "PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_anomaly_scan",
            "PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_safety_gate_demo",
            "PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_standard_report",
        ],
    )
    output = ROOT / "docs/reports/standard_eval_report_2026-11-03.md"
    output.write_text(render(report), encoding="utf-8")
    print(render(report)[:1500])
    return output


if __name__ == "__main__":
    print(f"报告：{main()}")
