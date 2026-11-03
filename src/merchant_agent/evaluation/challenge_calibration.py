"""对虚构边界挑战的真人双标与真实 Judge 结果做摘要核验和分层校准。"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from merchant_agent.evaluation.llm_judge import RUBRIC_PATH
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = Path("fixtures/judge_clarity_challenges_v1.json")
REVIEWERS = ("reviewer_one", "reviewer_two")


def calibrate_challenges(result_path: Path, *, project_root: Path = ROOT) -> dict:
    """同分标签作为本次参考分；有分歧的案例只进入仲裁清单。"""
    root = project_root.resolve()
    source = result_path.resolve()
    if not source.is_relative_to(root / "runs/judge_challenges"):
        raise ValueError("只接受项目内挑战运行记录")
    result_bytes = source.read_bytes()
    result = json.loads(result_bytes)
    fixture_bytes = (root / FIXTURE_PATH).read_bytes()
    fixture = json.loads(fixture_bytes)
    rubric_hash = hashlib.sha256((root / RUBRIC_PATH).read_bytes()).hexdigest()
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    if (result.get("status") != "completed" or result.get("fixture_id") != fixture.get("fixture_id")
            or result.get("fixture_sha256") != fixture_hash
            or result.get("rubric_sha256") != rubric_hash):
        raise ValueError("挑战运行记录与冻结输入不一致")
    cases = {case["case_id"]: case for case in fixture["cases"]}
    judged = {item["case_id"]: item for item in result["results"]}
    if (len(cases) != len(fixture["cases"]) or len(judged) != len(result["results"])
            or set(cases) != set(judged)):
        raise ValueError("挑战案例与裁判记录不一一对应")
    rows = []
    for case_id in sorted(cases):
        labels = []
        for reviewer_id in REVIEWERS:
            path = root / "runs/judge_challenge_reviews" / fixture["fixture_id"] / reviewer_id / f"{case_id}.json"
            raw = path.read_bytes()
            label = json.loads(raw)
            if (label.get("fixture_id") != fixture["fixture_id"] or label.get("case_id") != case_id
                    or label.get("fixture_sha256") != fixture_hash
                    or label.get("rubric_sha256") != rubric_hash
                    or label.get("reviewer_id") != reviewer_id
                    or type(label.get("score")) is not int or label["score"] not in {0, 1, 2}
                    or not isinstance(label.get("reason"), str) or not label["reason"].strip()):
                raise ValueError(f"人工标签无效：{reviewer_id}/{case_id}")
            labels.append({"reviewer_id": reviewer_id, "score": label["score"],
                           "label_sha256": hashlib.sha256(raw).hexdigest()})
        judge = judged[case_id]["judge"]
        if (judge.get("status") != "scored"
                or judge.get("trial_id") != f"synthetic-{case_id}"
                or judge.get("rubric_sha256") != rubric_hash
                or type(judge.get("score")) is not int or judge["score"] not in {0, 1, 2}):
            raise ValueError(f"裁判记录无效：{case_id}")
        agreed = labels[0]["score"] == labels[1]["score"]
        reference = labels[0]["score"] if agreed else None
        rows.append({"case_id": case_id, "designed_score": cases[case_id]["designed_score"],
                     "human_labels": labels, "human_agreed": agreed,
                     "reference_score": reference, "judge_score": judge["score"],
                     "requires_adjudication": not agreed})
    comparable = [row for row in rows if row["reference_score"] is not None]
    confusion = Counter((row["reference_score"], row["judge_score"]) for row in comparable)
    return {"fixture_id": fixture["fixture_id"], "fixture_sha256": fixture_hash,
            "rubric_sha256": rubric_hash,
            "judge_result_sha256": hashlib.sha256(result_bytes).hexdigest(),
            "sample_size": len(rows),
            "human_raw_agreement": sum(row["human_agreed"] for row in rows) / len(rows),
            "judge_comparable": len(comparable),
            "judge_exact_agreement": (sum(row["reference_score"] == row["judge_score"] for row in comparable)
                                      / len(comparable) if comparable else None),
            "by_reference_score": {str(score): {
                "n": sum(row["reference_score"] == score for row in comparable),
                "judge_matches": sum(row["reference_score"] == score and row["judge_score"] == score
                                     for row in comparable)} for score in (0, 1, 2)},
            "confusion": [{"human": human, "judge": judge, "count": count}
                          for (human, judge), count in sorted(confusion.items())],
            "rows": rows,
            "limitations": ["人工构造的虚构挑战，不代表自然生成 Trial 的分布",
                            "真人身份及盲审独立性依赖参与者确认，文件摘要不能独立证明"]}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="边界挑战双标与 Judge 分层校准")
    parser.add_argument("result_path", type=Path)
    args = parser.parse_args(argv)
    report = calibrate_challenges(args.result_path)
    target = args.result_path.resolve().parent / "calibration.json"
    _save(target, report)
    print(f"边界校准记录：{target}")


if __name__ == "__main__":
    main()
