"""离线审计公开基准实验：核对逐条原始记录并用固定官方评分逻辑重算。"""

import argparse
import json
import sqlite3
from pathlib import Path

from merchant_agent.evaluation.benchmark_data import MANIFEST, database_path, digest, json_digest
from merchant_agent.evaluation.public_benchmark import (
    bfcl_checker, bfcl_messages, bird_checker, bird_messages, run_readonly_sql, score_bfcl,
)
from merchant_agent.evaluation.public_benchmark_cli import (
    build_schedule, load_manifest, now, preflight, save, source_fingerprints,
)


def validate_rows(schedule: list[dict], rows: list[dict]) -> None:
    indexes = [row["index"] for row in rows]
    if len(set(indexes)) != len(indexes) or set(indexes) != set(range(len(schedule))):
        raise ValueError("Trial 存在重复或缺失")
    planned = {slot["index"]: slot for slot in schedule}
    for row in rows:
        if any(row.get(key) != value for key, value in planned[row["index"]].items()):
            raise ValueError("Trial 与预先冻结的调度不一致")
        if row.get("status") not in {"scored", "error"} or type(row.get("passed")) is not bool:
            raise ValueError("Trial 未完成或通过标记无效")
        if row["status"] == "error" and row["passed"]:
            raise ValueError("错误 Trial 不能计为通过")


def audit(directory: Path) -> dict:
    manifest = load_manifest()
    gold = preflight(manifest)
    record = json.loads((directory / "experiment.json").read_text())
    rows = json.loads((directory / "results.json").read_text())
    if record["status"] != "completed":
        raise ValueError("实验尚未完成")
    if record["manifest_sha256"] != digest(MANIFEST.read_bytes()):
        raise ValueError("实验清单哈希发生变化")
    if record["source_fingerprints"] != source_fingerprints():
        raise ValueError("实验源码发生变化；请恢复到运行时版本")
    if record["schedule"] != build_schedule(manifest):
        raise ValueError("实验调度不匹配")
    validate_rows(record["schedule"], rows)
    cases = {case["id"]: case for case in manifest["cases"]}
    fc_check, sql_check = bfcl_checker(), bird_checker()
    rescored = 0
    for row in rows:
        original = json.loads((directory / "trials" / f"{row['index']:04d}.json").read_text())
        if original != row:
            raise ValueError(f"汇总与原始 Trial 不一致：{row['index']}")
        case = cases[row["case_id"]]
        messages = bfcl_messages(case) if row["benchmark"] == "bfcl" else bird_messages(case, row["arm"])
        if messages != row["initial_messages"] or json_digest(messages) != row["input_sha256"]:
            raise ValueError("输入来源或上下文不一致")
        if row["status"] == "error":
            continue
        if row["benchmark"] == "bfcl":
            output = next(item["output"] for item in row["trace"] if item["type"] == "model")
            passed = score_bfcl(case, output, fc_check)["passed"]
        else:
            passed = False
            if row.get("final_sql") is not None:
                try:
                    predicted = run_readonly_sql(database_path(case["db_id"]), row["final_sql"])
                    passed = bool(sql_check(predicted["rows"], gold[case["id"]]["rows"]))
                except (ValueError, sqlite3.Error):
                    pass
        if passed != row["passed"]:
            raise ValueError(f"离线重评分不一致：{row['index']}")
        rescored += 1
    result = {"audited_at": now(), "run_id": record["run_id"], "passed": True,
              "trials_verified": len(rows), "scored_trials_recomputed": rescored,
              "error_trials_preserved": len(rows) - rescored,
              "manifest_sha256": record["manifest_sha256"],
              "results_sha256": digest((directory / "results.json").read_bytes()),
              "auditor_sha256": digest(Path(__file__).read_bytes()),
              "note": "离线检查原始记录、来源及评分一致性，不会重新调用模型；不保证模型重跑输出逐字一致。"}
    save(directory / "audit.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.run_dir), ensure_ascii=False, indent=2))
