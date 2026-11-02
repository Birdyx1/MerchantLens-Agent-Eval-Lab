"""多裁判结果的分层人工抽样与参考标签校准。"""

import random
from collections import Counter


def select_calibration_sample(panels: list[dict], *, sample_size: int, seed: int) -> dict:
    """优先覆盖分歧/不完整样本，其余从多数样本随机抽取。"""
    if type(sample_size) is not int or sample_size < 1 or sample_size > len(panels):
        raise ValueError("抽样数必须在 1 到候选 Trial 数之间")
    ids = [panel["trial_id"] for panel in panels]
    if len(set(ids)) != len(ids):
        raise ValueError("候选 Trial ID 重复")
    rng = random.Random(seed)
    flagged = sorted((panel for panel in panels if panel["status"] != "majority"),
                     key=lambda item: item["trial_id"])
    ordinary = sorted((panel for panel in panels if panel["status"] == "majority"),
                      key=lambda item: item["trial_id"])
    chosen_flagged = rng.sample(flagged, min(sample_size, len(flagged)))
    remaining = sample_size - len(chosen_flagged)
    chosen_ordinary = rng.sample(ordinary, remaining)
    return {"seed": seed, "population": len(panels), "sample_size": sample_size,
            "population_flagged": len(flagged), "sample_flagged": len(chosen_flagged),
            "trial_ids": sorted(item["trial_id"] for item in chosen_flagged + chosen_ordinary)}


def calibrate_panel(sample: dict, panels: list[dict], labels: list[dict]) -> dict:
    """只接受双人独立标签；分歧须第三人仲裁，报告原始一致性。"""
    selected = set(sample["trial_ids"])
    if len(selected) != sample["sample_size"]:
        raise ValueError("抽样 Trial ID 重复")
    panel_by_id = {panel["trial_id"]: panel for panel in panels}
    label_by_id = {label["trial_id"]: label for label in labels}
    if len(label_by_id) != len(labels) or set(label_by_id) != selected or not selected <= set(panel_by_id):
        raise ValueError("人工标签与抽样 Trial 不一一对应")
    raw_agreements = 0
    comparable = 0
    matches = 0
    confusion = Counter()
    review = []
    for trial_id in sorted(selected):
        label = label_by_id[trial_id]
        first, second = label["first"], label["second"]
        if (first["reviewer_id"] == second["reviewer_id"]
                or any(type(item["score"]) is not int or item["score"] not in {0, 1, 2}
                       for item in (first, second))):
            raise ValueError("人工双标身份或分数无效")
        agreed = first["score"] == second["score"]
        raw_agreements += agreed
        if agreed:
            if label.get("adjudication") is not None:
                raise ValueError("一致标签不应被仲裁覆盖")
            truth = first["score"]
        else:
            arbiter = label.get("adjudication")
            if (not isinstance(arbiter, dict)
                    or arbiter.get("reviewer_id") in {first["reviewer_id"], second["reviewer_id"]}
                    or not arbiter.get("reviewer_id") or type(arbiter.get("score")) is not int
                    or arbiter["score"] not in {0, 1, 2}
                    or not isinstance(arbiter.get("reason"), str) or not arbiter["reason"].strip()):
                raise ValueError("人工分歧必须第三人显式仲裁")
            truth = arbiter["score"]
        panel = panel_by_id[trial_id]
        prediction = panel.get("score") if panel.get("status") == "majority" else None
        if prediction is not None:
            comparable += 1
            matches += prediction == truth
            confusion[(truth, prediction)] += 1
        review.append({"trial_id": trial_id, "human_score": truth,
                       "panel_score": prediction, "human_agreed": agreed,
                       "needs_review": prediction != truth})
    return {"sample_size": len(selected), "human_raw_agreement": raw_agreements / len(selected),
            "judge_exact_agreement": matches / comparable if comparable else None,
            "judge_comparable": comparable,
            "confusion": [{"human": human, "judge": judge, "count": count}
                          for (human, judge), count in sorted(confusion.items())],
            "review": review,
            "sampling_note": "分歧样本优先抽取；这些比例只描述样本，不是总体无偏估计"}
