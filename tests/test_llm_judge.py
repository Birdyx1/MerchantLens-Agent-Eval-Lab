import asyncio
import json
from pathlib import Path

import pytest

from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.evaluation.llm_judge import judge_answer_clarity


ROOT = Path(__file__).resolve().parents[1]


class FakeJudge:
    def __init__(self, text):
        self.text = text
        self.messages = None

    async def generate(self, messages):
        self.messages = messages
        return ModelResponse(self.text, "judge-test-v1", 15, 6)


def _inputs(answer="门店 A 净收入为 12000 分"):
    return ({"trial_id": "trial_1", "task_id": "task_1", "final_answer": answer},
            {"trial_id": "trial_1", "task_id": "task_1", "passed": False})


def test_judge_uses_fixed_rubric_and_keeps_code_score_separate():
    trial, code_score = _inputs()
    judge = FakeJudge(json.dumps({"score": 2, "reason": "对象、金额和单位清楚"}))
    result = asyncio.run(judge_answer_clarity(trial, code_score, project_root=ROOT, model=judge))
    assert result["score"] == 2
    assert code_score["passed"] is False
    assert result["rubric_sha256"] and result["judge_model_id"] == "judge-test-v1"
    assert judge.messages[0]["role"] == "system"
    assert json.loads(judge.messages[1]["content"])["answer_to_judge"] == trial["final_answer"]


def test_missing_answer_is_deterministically_zero_without_model_call():
    trial, code_score = _inputs(None)
    judge = FakeJudge("unused")
    result = asyncio.run(judge_answer_clarity(trial, code_score, project_root=ROOT, model=judge))
    assert result["score"] == 0 and judge.messages is None


@pytest.mark.parametrize("text", ["不是 JSON", '{"score": 3, "reason": "好"}',
                                   '{"score": true, "reason": "好"}',
                                   '{"score": 2, "reason": ""}',
                                   '{"score": 2, "reason": "好", "extra": 1}'])
def test_malformed_judge_output_is_rejected(text):
    trial, code_score = _inputs()
    with pytest.raises(ValueError, match="裁判输出"):
        asyncio.run(judge_answer_clarity(trial, code_score, project_root=ROOT,
                                         model=FakeJudge(text)))


def test_mismatched_trial_is_rejected():
    trial, code_score = _inputs()
    code_score["trial_id"] = "other"
    with pytest.raises(ValueError, match="不一致"):
        asyncio.run(judge_answer_clarity(trial, code_score, project_root=ROOT,
                                         model=FakeJudge("{}")))
