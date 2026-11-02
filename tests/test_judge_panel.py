import asyncio
import json
from pathlib import Path

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.judge_panel import JudgeSpec, run_judge_panel


ROOT = Path(__file__).resolve().parents[1]


class FakeJudge:
    def __init__(self, score):
        self.score = score

    async def generate(self, messages):
        if self.score == "error":
            raise RuntimeError("simulated judge failure")
        return ModelResponse(json.dumps({"score": self.score, "reason": "表达判断"}),
                             "judge-test", 10, 3)


def _run(scores):
    trial = {"trial_id": "trial_1", "task_id": "task_1", "final_answer": "门店 A 净收入 12000 分"}
    code = {"trial_id": "trial_1", "task_id": "task_1", "passed": False}
    judges = [JudgeSpec(f"judge_{index}", FakeJudge(score)) for index, score in enumerate(scores)]
    return asyncio.run(run_judge_panel(trial, code, project_root=ROOT, judges=judges))


def test_two_of_three_is_majority_but_does_not_override_code():
    result = _run([2, 2, 1])
    assert result["status"] == "majority" and result["score"] == 2
    assert result["agreement_rate"] == pytest.approx(2 / 3)
    assert result["code_passed"] is False
    assert [vote["reason"] for vote in result["votes"]] == ["表达判断"] * 3


def test_three_way_split_needs_human_review():
    result = _run([0, 1, 2])
    assert result["status"] == "disagreement"
    assert result["score"] is None and result["requires_human_review"] is True


def test_failed_judge_makes_panel_incomplete():
    result = _run([2, 2, "error"])
    assert result["status"] == "incomplete" and result["score"] is None
    assert result["votes"][2]["error_type"] == "RuntimeError"


def test_duplicate_judge_ids_are_rejected():
    trial = {"trial_id": "trial_1", "task_id": "task_1", "final_answer": "答案"}
    code = {"trial_id": "trial_1", "task_id": "task_1", "passed": False}
    with pytest.raises(ValueError, match="不同 ID"):
        asyncio.run(run_judge_panel(trial, code, project_root=ROOT,
                                   judges=[JudgeSpec("same", FakeJudge(1)) for _ in range(3)]))
