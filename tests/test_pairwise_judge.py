import asyncio
import json
from pathlib import Path

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.pairwise_judge import compare_answers


ROOT = Path(__file__).resolve().parents[1]


class SequenceJudge:
    def __init__(self, choices):
        self.choices = iter(choices)
        self.messages = []

    async def generate(self, messages):
        self.messages.append(messages)
        return ModelResponse(json.dumps({"winner": next(self.choices), "reason": "表达更清楚"}),
                             "judge-v1", 10, 3)


def _pair():
    return ({"trial_id": "a", "task_id": "task_1", "task_sha256": "x" * 64,
             "final_answer": "A 门店净收入 12000 分"},
            {"trial_id": "b", "task_id": "task_1", "task_sha256": "x" * 64,
             "final_answer": "12000"})


def test_swapped_order_agrees_on_same_winner():
    judge = SequenceJudge(["left", "right"])
    result = asyncio.run(compare_answers(*_pair(), project_root=ROOT, model=judge))
    assert result["stable"] is True and result["winner"] == "first"
    assert result["input_tokens"] == 20
    first_payload = json.loads(judge.messages[0][1]["content"])
    second_payload = json.loads(judge.messages[1][1]["content"])
    assert first_payload["left"] == second_payload["right"]


def test_position_bias_is_marked_unstable():
    result = asyncio.run(compare_answers(*_pair(), project_root=ROOT,
                                         model=SequenceJudge(["left", "left"])))
    assert result["stable"] is False and result["winner"] == "unstable"


def test_two_ties_are_stable_tie():
    result = asyncio.run(compare_answers(*_pair(), project_root=ROOT,
                                         model=SequenceJudge(["tie", "tie"])))
    assert result["stable"] is True and result["winner"] == "tie"


def test_different_task_snapshot_is_rejected():
    first, second = _pair()
    second["task_sha256"] = "other"
    with pytest.raises(ValueError, match="相同 Task"):
        asyncio.run(compare_answers(first, second, project_root=ROOT,
                                    model=SequenceJudge(["left", "right"])))
