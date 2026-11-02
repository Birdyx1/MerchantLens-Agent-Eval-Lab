"""三名独立配置裁判的固定 Rubric 投票。"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from merchant_agent.agent.model_port import ModelPort
from merchant_agent.evaluation.llm_judge import judge_answer_clarity


@dataclass(frozen=True, slots=True)
class JudgeSpec:
    """调用方提供不同的裁判实例与审计 ID。"""

    judge_id: str
    model: ModelPort


async def run_judge_panel(trial: dict, code_score: dict, *, project_root: Path,
                          judges: list[JudgeSpec]) -> dict:
    """逐名独立评分；三票齐全才形成多数结论。"""
    if len(judges) != 3 or len({item.judge_id for item in judges}) != 3:
        raise ValueError("必须提供三个不同 ID 的裁判")
    if any(not item.judge_id.strip() for item in judges):
        raise ValueError("裁判 ID 不能为空")
    if len({id(item.model) for item in judges}) != 3:
        raise ValueError("三个裁判必须使用不同的模型实例")
    votes = []
    for judge in judges:
        try:
            result = await judge_answer_clarity(trial, code_score, project_root=project_root,
                                                model=judge.model)
            votes.append({"judge_id": judge.judge_id, **result})
        except Exception as exc:
            votes.append({"judge_id": judge.judge_id, "status": "error",
                          "error_type": type(exc).__name__})
    valid = [item for item in votes if item["status"] == "scored"]
    if len(valid) != 3:
        status, score, agreement = "incomplete", None, None
    else:
        rubric_hashes = {item["rubric_sha256"] for item in valid}
        if len(rubric_hashes) != 1:
            raise ValueError("裁判使用的 Rubric 版本不一致")
        counts = Counter(item["score"] for item in valid)
        most_common, frequency = counts.most_common(1)[0]
        status = "majority" if frequency >= 2 else "disagreement"
        score = most_common if frequency >= 2 else None
        agreement = frequency / 3
    return {"trial_id": trial["trial_id"], "task_id": trial["task_id"],
            "status": status, "score": score, "agreement_rate": agreement,
            "votes": votes, "requires_human_review": status != "majority",
            "code_passed": bool(code_score.get("passed"))}
