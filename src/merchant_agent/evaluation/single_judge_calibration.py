"""核验真实单裁判盲审记录，生成有限范围的人工一致性报告。"""

import argparse
import hashlib
import json
from pathlib import Path

from merchant_agent.evaluation.llm_judge import RUBRIC_PATH
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
REVIEWERS = ("reviewer_one", "reviewer_two")


def calibrate(result_path: Path, *, project_root: Path = ROOT) -> dict:
    """逐条核验 Trial、Rubric 和双份标签，不推断标注者的真实身份。"""
    root = project_root.resolve()
    source = result_path.resolve()
    if not source.is_relative_to(root / "runs/judge_pilot"):
        raise ValueError("只接受项目内真实 Judge 试点记录")
    raw_result = source.read_bytes()
    result = json.loads(raw_result)
    if result.get("status") != "completed" or not result.get("results"):
        raise ValueError("裁判记录未完成")
    if hashlib.sha256((root / RUBRIC_PATH).read_bytes()).hexdigest() != result["rubric_sha256"]:
        raise ValueError("当前 Rubric 与裁判记录摘要不一致")
    if len({item["trial_id"] for item in result["results"]}) != len(result["results"]):
        raise ValueError("裁判记录存在重复 Trial")
    review_base = root / "runs" / "judge_reviews" / source.parent.name
    items = []
    human_agree = judge_match = 0
    for item in result["results"]:
        trial_id = item["trial_id"]
        trial_path = root / "runs" / "trials" / trial_id / "trial.json"
        if hashlib.sha256(trial_path.read_bytes()).hexdigest() != item["trial_sha256"]:
            raise ValueError(f"Trial 内容发生变化：{trial_id}")
        labels = []
        for reviewer_id in REVIEWERS:
            path = review_base / reviewer_id / f"{trial_id}.json"
            raw = path.read_bytes()
            label = json.loads(raw)
            if (label.get("trial_id") != trial_id or label.get("task_id") != item["task_id"]
                    or label.get("reviewer_id") != reviewer_id
                    or label.get("trial_sha256") != item["trial_sha256"]
                    or label.get("rubric_sha256") != result["rubric_sha256"]
                    or type(label.get("score")) is not int or label["score"] not in {0, 1, 2}
                    or not isinstance(label.get("reason"), str) or not label["reason"].strip()):
                raise ValueError(f"人工标签无效：{reviewer_id}/{trial_id}")
            labels.append({"reviewer_id": reviewer_id, "score": label["score"],
                           "label_sha256": hashlib.sha256(raw).hexdigest()})
        agreed = labels[0]["score"] == labels[1]["score"]
        human_agree += agreed
        reference = labels[0]["score"] if agreed else None
        judge = item["judge"]
        if (judge.get("status") != "scored" or judge.get("trial_id") != trial_id
                or judge.get("rubric_sha256") != result["rubric_sha256"]
                or type(judge.get("score")) is not int or judge["score"] not in {0, 1, 2}):
            raise ValueError(f"裁判评分无效：{trial_id}")
        match = judge["score"] == reference if reference is not None else None
        judge_match += match is True
        items.append({"task_id": item["task_id"], "trial_id": trial_id,
                      "human_labels": labels, "human_agreed": agreed,
                      "reference_score": reference, "judge_score": judge["score"],
                      "judge_matches_reference": match,
                      "requires_adjudication": not agreed})
    comparable = sum(item["reference_score"] is not None for item in items)
    return {"judge_result_sha256": hashlib.sha256(raw_result).hexdigest(),
            "rubric_sha256": result["rubric_sha256"], "sample_size": len(items),
            "human_raw_agreement": human_agree / len(items),
            "judge_exact_agreement": judge_match / comparable if comparable else None,
            "judge_comparable": comparable,
            "score_distribution": {str(score): sum(item["reference_score"] == score for item in items)
                                   for score in (0, 1, 2)},
            "items": items,
            "limitations": ["只核验 reviewer_id 与文件摘要，不证明真人身份或独立性",
                            "本次是单裁判、非随机样本；一致率只描述该批样本",
                            "双人分歧的参考分必须由第三人仲裁后另行生成"]}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="真实单裁判盲审校准")
    parser.add_argument("result_path", type=Path)
    args = parser.parse_args(argv)
    report = calibrate(args.result_path)
    target = args.result_path.resolve().parent / "calibration.json"
    _save(target, report)
    print(f"校准记录：{target}")


if __name__ == "__main__":
    main()
