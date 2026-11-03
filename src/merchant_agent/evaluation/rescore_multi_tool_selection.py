"""用修正后的评分器重评已冻结输出，不重新调用模型。"""

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.evaluation.multi_tool_selection import (
    build_report,
    load_cases,
    score_selection,
    summarize_results,
)


ROOT = Path(__file__).resolve().parents[3]
SCORER_PATH = ROOT / "src/merchant_agent/evaluation/multi_tool_selection.py"


def rescore_record(record: dict) -> dict:
    """保留原评分与评分器摘要，只替换同一输出上的新评分。"""
    _, cases = load_cases()
    case_map = {case["id"]: case for case in cases}
    rescored = copy.deepcopy(record)
    rescored["original_scorer_source_sha256"] = record.get("scorer_source_sha256")
    rescored["original_summary"] = record.get("summary")
    rescored["scorer_source_sha256"] = hashlib.sha256(SCORER_PATH.read_bytes()).hexdigest()
    rescored["rescored_at"] = datetime.now(timezone.utc).isoformat()
    changes = []
    for entry in rescored.get("results", []):
        if entry.get("status") != "scored":
            continue
        original = entry.get("score")
        entry["original_score"] = original
        entry["score"] = score_selection(case_map[entry["case_id"]], entry["output"])
        if original != entry["score"]:
            changes.append({
                "model": entry["model"], "case_id": entry["case_id"],
                "repeat_index": entry["repeat_index"],
                "from": original, "to": entry["score"],
            })
    rescored["rescore_changes"] = changes
    rescored["summary"] = summarize_results(rescored)
    return rescored


def main() -> Path:
    parser = argparse.ArgumentParser(description="重评多工具选择运行记录")
    parser.add_argument("results", type=Path, help="原始 results.json 路径")
    arguments = parser.parse_args()
    source = arguments.results.resolve()
    record = json.loads(source.read_text(encoding="utf-8"))
    rescored = rescore_record(record)
    destination = source.with_name("results_rescored.json")
    destination.write_text(json.dumps(rescored, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    os.chmod(destination, 0o600)
    report_path = source.with_name("report_rescored.md")
    report_path.write_text(build_report(rescored), encoding="utf-8")
    os.chmod(report_path, 0o600)
    return destination


if __name__ == "__main__":
    print(f"重评记录：{main()}")
